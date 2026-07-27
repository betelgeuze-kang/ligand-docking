"""Offline evaluation of externally supplied public redocking poses.

The evaluator consumes a previously verified materialization manifest and
caller-supplied canonical molecular systems. It performs no network access and
retains one ordered success/failure row per materialization case. A successful
evaluation computes direct receptor-frame, symmetry-aware heavy-atom RMSD,
complete bounded pose validity, and the frozen primary conjunction
``RMSD <= 2 Å and bounded_pose_valid == 1``.

The resulting report is operational evidence only. It never grants scientific
validation, benchmark equivalence, product qualification, customer execution,
or claim safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Mapping, Sequence

import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import (
    DockingBudget,
    DockingProblemIdentity,
    PoseValidityConfig,
    PoseValidityContext,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    symmetry_aware_rmsd,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
)

from .public_materializer import (
    PublicBenchmarkCaseMaterialization,
    PublicBenchmarkMaterializationManifest,
    exact_graph_isomorphisms,
)


PUBLIC_BENCHMARK_EVALUATOR_ID = (
    "betelgeuze_offline_public_redocking_evaluator/1.0.0"
)
PUBLIC_BENCHMARK_EVALUATION_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_evaluation_row/1.0.0"
)
PUBLIC_BENCHMARK_EVALUATION_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_evaluation_report/1.0.0"
)
PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION = (
    "reference_position_to_candidate_position"
)
PUBLIC_BENCHMARK_PRIMARY_RMSD_THRESHOLD_ANGSTROM = 2.0
MAX_PUBLIC_EVALUATION_CASES = 4_096

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class PublicBenchmarkEvaluationError(ValueError):
    """Offline public evaluation input is incomplete or cross-wired."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicBenchmarkEvaluationError(
            "public evaluation payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PublicBenchmarkEvaluationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_commit(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise PublicBenchmarkEvaluationError(
            f"{name} must be a lowercase 40-character Git SHA"
        )
    return value


def _frame(system: AllAtomSystem, *, name: str) -> torch.Tensor:
    if not isinstance(system, AllAtomSystem):
        raise TypeError(f"{name} must be AllAtomSystem")
    if system.model_count != 1:
        raise PublicBenchmarkEvaluationError(
            f"{name} must contain exactly one coordinate model"
        )
    frame = (
        system.coordinates[0]
        .detach()
        .to(dtype=torch.float64, device="cpu")
        .clone()
        .contiguous()
        .requires_grad_(False)
    )
    if frame.shape != (system.atom_count, 3) or not bool(
        torch.isfinite(frame).all().item()
    ):
        raise PublicBenchmarkEvaluationError(
            f"{name} coordinates are invalid"
        )
    return frame


def _coordinates(value: object, *, name: str) -> torch.Tensor:
    if (
        not isinstance(value, torch.Tensor)
        or value.ndim != 2
        or value.shape[-1] != 3
        or not value.is_floating_point()
        or not bool(torch.isfinite(value).all().item())
    ):
        raise PublicBenchmarkEvaluationError(
            f"{name} must contain finite floating coordinates with shape [N,3]"
        )
    result = (
        value.detach()
        .to(dtype=torch.float64, device="cpu")
        .clone()
        .contiguous()
        .requires_grad_(False)
    )
    if int(result.shape[0]) < 1:
        raise PublicBenchmarkEvaluationError(f"{name} must be non-empty")
    return result


def _vector3(value: object, *, name: str) -> torch.Tensor:
    tensor = torch.as_tensor(value, dtype=torch.float64, device="cpu").reshape(-1)
    if tensor.shape != (3,) or not bool(torch.isfinite(tensor).all().item()):
        raise PublicBenchmarkEvaluationError(
            f"{name} must contain three finite coordinates"
        )
    return tensor.clone().contiguous().requires_grad_(False)


def _ordered_topology_projection(system: AllAtomSystem) -> dict[str, object]:
    return {
        "schema_id": "betelgeuze.engine_v2_ordered_topology_projection/1.0.0",
        "atoms": [
            {
                "index": int(atom.index),
                "element": atom.element,
                "atomic_number": int(atom.atomic_number),
                "formal_charge": int(atom.formal_charge),
                "isotope_mass_number": atom.isotope_mass_number,
                "aromatic": bool(atom.aromatic),
                "stereo": atom.stereo,
            }
            for atom in system.atoms
        ],
        "bonds": [
            {
                "atom_i": int(bond.atom_i),
                "atom_j": int(bond.atom_j),
                "order_hex": float(bond.order).hex(),
                "aromatic": bool(bond.aromatic),
                "stereo": bond.stereo,
            }
            for bond in system.bonds
        ],
    }


def _heavy_indices(system: AllAtomSystem) -> tuple[int, ...]:
    indices = tuple(
        index
        for index, atom in enumerate(system.atoms)
        if atom.element.upper() != "H"
    )
    if not indices:
        raise PublicBenchmarkEvaluationError("ligand contains no heavy atoms")
    return indices


def _reference_to_seed_mappings(
    reference_system: AllAtomSystem,
    seed_system: AllAtomSystem,
) -> tuple[
    tuple[tuple[int, ...], ...],
    tuple[tuple[int, ...], ...],
]:
    full_mappings = exact_graph_isomorphisms(reference_system, seed_system)
    if not full_mappings:
        raise PublicBenchmarkEvaluationError(
            "reference and ligand seed are not exact labeled-graph isomorphs"
        )
    reference_heavy = _heavy_indices(reference_system)
    seed_heavy = _heavy_indices(seed_system)
    if len(reference_heavy) != len(seed_heavy):
        raise PublicBenchmarkEvaluationError("heavy-atom counts differ")
    seed_heavy_position = {
        atom_index: position for position, atom_index in enumerate(seed_heavy)
    }
    heavy_mappings: list[tuple[int, ...]] = []
    for mapping in full_mappings:
        projected = tuple(
            seed_heavy_position[int(mapping[reference_atom])]
            for reference_atom in reference_heavy
        )
        if sorted(projected) != list(range(len(seed_heavy))):
            raise PublicBenchmarkEvaluationError(
                "reference-to-seed heavy-atom mapping is not a bijection"
            )
        heavy_mappings.append(projected)
    return tuple(sorted(set(full_mappings))), tuple(sorted(set(heavy_mappings)))


def _invert_permutation(row: Sequence[int]) -> tuple[int, ...]:
    values = tuple(int(value) for value in row)
    if sorted(values) != list(range(len(values))):
        raise PublicBenchmarkEvaluationError(
            "materialized symmetry permutation is not a bijection"
        )
    inverse = [0] * len(values)
    for source_position, target_position in enumerate(values):
        inverse[target_position] = source_position
    return tuple(inverse)


def _materialized_metric_mappings(
    materialization: PublicBenchmarkCaseMaterialization,
) -> tuple[tuple[int, ...], ...]:
    document = materialization.to_dict()
    direction = document.get("symmetry_permutation_direction")
    rows = tuple(
        tuple(int(value) for value in row)
        for row in materialization.symmetry_permutations
    )
    if direction == PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION:
        return rows
    if direction is None:
        # Legacy result-free receipts encoded seed-position -> reference-position.
        # The evaluator never consumes that direction directly; it inverts it and
        # records the legacy provenance as a blocker in the final report.
        return tuple(sorted(_invert_permutation(row) for row in rows))
    raise PublicBenchmarkEvaluationError(
        "materialization declares an unsupported symmetry permutation direction"
    )


def _reference_in_seed_order(
    reference_coordinates: torch.Tensor,
    seed_atom_count: int,
    mapping: Sequence[int],
) -> torch.Tensor:
    if len(mapping) != int(reference_coordinates.shape[0]):
        raise PublicBenchmarkEvaluationError(
            "full reference-to-seed mapping has an invalid atom count"
        )
    ordered = torch.empty(
        (seed_atom_count, 3), dtype=torch.float64, device="cpu"
    )
    for reference_index, seed_index in enumerate(mapping):
        ordered[int(seed_index)] = reference_coordinates[reference_index]
    return ordered.contiguous().requires_grad_(False)


def _pocket_definition_sha256(
    center: torch.Tensor,
    radius_angstrom: float,
) -> str:
    return _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_public_evaluation_pocket/1.0.0",
            "center_hex": [float(value).hex() for value in center.tolist()],
            "radius_angstrom_hex": float(radius_angstrom).hex(),
        }
    )


def _bond_pairs(system: AllAtomSystem) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            {
                tuple(sorted((int(bond.atom_i), int(bond.atom_j))))
                for bond in system.bonds
            }
        )
    )


@dataclass(frozen=True, slots=True)
class PublicBenchmarkEvaluationCaseInput:
    case_id: str
    materialization: PublicBenchmarkCaseMaterialization
    receptor_artifact_sha256: str
    reference_artifact_sha256: str
    ligand_identity_seed_artifact_sha256: str
    candidate_artifact_sha256: str
    receptor_system_sha256: str
    reference_system: AllAtomSystem
    ligand_identity_seed_system: AllAtomSystem
    candidate_system: AllAtomSystem
    receptor_coordinates: torch.Tensor
    pocket_center: torch.Tensor
    pocket_radius_angstrom: float
    excluded_nonbonded_pairs: tuple[tuple[int, int], ...]
    chirality_centers: tuple[tuple[int, int, int, int], ...] = ()
    _metric_permutations: tuple[tuple[int, ...], ...] = field(
        init=False, repr=False
    )
    _ordered_reference_coordinates: torch.Tensor = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise PublicBenchmarkEvaluationError("case_id must be non-empty")
        if not isinstance(
            self.materialization, PublicBenchmarkCaseMaterialization
        ):
            raise TypeError(
                "materialization must be PublicBenchmarkCaseMaterialization"
            )
        if self.materialization.case_id != self.case_id:
            raise PublicBenchmarkEvaluationError(
                "evaluation case and materialization case IDs differ"
            )
        for name in (
            "receptor_artifact_sha256",
            "reference_artifact_sha256",
            "ligand_identity_seed_artifact_sha256",
            "candidate_artifact_sha256",
            "receptor_system_sha256",
        ):
            object.__setattr__(
                self, name, _require_sha256(getattr(self, name), name=name)
            )
        if self.receptor_artifact_sha256 != self.materialization.receptor_sha256:
            raise PublicBenchmarkEvaluationError(
                "receptor artifact identity is cross-wired"
            )
        if (
            self.reference_artifact_sha256
            != self.materialization.reference_ligands_sha256
        ):
            raise PublicBenchmarkEvaluationError(
                "reference artifact identity is cross-wired"
            )
        if (
            self.ligand_identity_seed_artifact_sha256
            != self.materialization.ligand_identity_seed_sha256
        ):
            raise PublicBenchmarkEvaluationError(
                "ligand seed artifact identity is cross-wired"
            )

        reference = _frame(self.reference_system, name="reference_system")
        seed = _frame(
            self.ligand_identity_seed_system,
            name="ligand_identity_seed_system",
        )
        candidate = _frame(self.candidate_system, name="candidate_system")
        if _ordered_topology_projection(self.candidate_system) != (
            _ordered_topology_projection(self.ligand_identity_seed_system)
        ):
            raise PublicBenchmarkEvaluationError(
                "candidate topology/order differs from the ligand identity seed"
            )
        if (
            canonical_topology_sha256(self.reference_system)
            != self.materialization.selected_reference_topology_sha256
            or canonical_coordinates_sha256(self.reference_system)
            != self.materialization.selected_reference_coordinates_sha256
        ):
            raise PublicBenchmarkEvaluationError(
                "reference topology or coordinates do not match the materialization receipt"
            )
        if int(candidate.shape[0]) != int(seed.shape[0]):
            raise PublicBenchmarkEvaluationError(
                "candidate and ligand seed atom counts differ"
            )

        full_mappings, metric_mappings = _reference_to_seed_mappings(
            self.reference_system,
            self.ligand_identity_seed_system,
        )
        materialized_mappings = _materialized_metric_mappings(
            self.materialization
        )
        if materialized_mappings != metric_mappings:
            raise PublicBenchmarkEvaluationError(
                "materialized symmetry mappings disagree with exact graph matching"
            )
        if len(_heavy_indices(self.reference_system)) != (
            self.materialization.heavy_atom_count
        ):
            raise PublicBenchmarkEvaluationError(
                "materialization heavy-atom count is cross-wired"
            )
        ordered_reference = _reference_in_seed_order(
            reference,
            self.ligand_identity_seed_system.atom_count,
            full_mappings[0],
        )
        receptor = _coordinates(
            self.receptor_coordinates,
            name="receptor_coordinates",
        )
        center = _vector3(self.pocket_center, name="pocket_center")
        radius = float(self.pocket_radius_angstrom)
        if not math.isfinite(radius) or radius <= 0.0:
            raise PublicBenchmarkEvaluationError(
                "pocket_radius_angstrom must be positive and finite"
            )
        bonds = set(_bond_pairs(self.ligand_identity_seed_system))
        exclusions = tuple(
            sorted(
                {
                    tuple(sorted((int(first), int(second))))
                    for first, second in self.excluded_nonbonded_pairs
                }
            )
        )
        if not bonds.issubset(set(exclusions)):
            raise PublicBenchmarkEvaluationError(
                "excluded_nonbonded_pairs must include every ligand bond"
            )
        object.__setattr__(self, "receptor_coordinates", receptor)
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "pocket_radius_angstrom", radius)
        object.__setattr__(self, "excluded_nonbonded_pairs", exclusions)
        object.__setattr__(
            self,
            "chirality_centers",
            tuple(
                tuple(int(value) for value in row)
                for row in self.chirality_centers
            ),
        )
        object.__setattr__(self, "_metric_permutations", metric_mappings)
        object.__setattr__(
            self, "_ordered_reference_coordinates", ordered_reference
        )


@dataclass(frozen=True, slots=True)
class PublicBenchmarkEvaluationRow:
    ordinal: int
    case_id: str
    status: str
    materialization_sha256: str
    candidate_artifact_sha256: str
    rmsd_angstrom: float | None = None
    bounded_pose_valid: bool | None = None
    primary_pose_success: bool | None = None
    pose_validity: Mapping[str, object] | None = None
    error_code: str = ""
    error_message: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == "success" and self.rmsd_angstrom is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": PUBLIC_BENCHMARK_EVALUATION_ROW_SCHEMA_ID,
            "ordinal": self.ordinal,
            "case_id": self.case_id,
            "status": self.status,
            "succeeded": self.succeeded,
            "materialization_sha256": self.materialization_sha256,
            "candidate_artifact_sha256": self.candidate_artifact_sha256,
            "rmsd_angstrom": self.rmsd_angstrom,
            "bounded_pose_valid": self.bounded_pose_valid,
            "primary_pose_success": self.primary_pose_success,
            "pose_validity": (
                None if self.pose_validity is None else dict(self.pose_validity)
            ),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": self.private_error_byte_length,
        }


@dataclass(frozen=True, slots=True)
class PublicBenchmarkEvaluationReport:
    protocol_sha256: str
    materialization_manifest_sha256: str
    engine_commit: str
    environment_fingerprint_sha256: str
    command: tuple[str, ...]
    seed: int
    rows: tuple[PublicBenchmarkEvaluationRow, ...]
    legacy_materialization_direction_present: bool
    report_sha256: str

    @property
    def success_count(self) -> int:
        return sum(row.succeeded for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    @property
    def primary_success_count(self) -> int:
        return sum(row.primary_pose_success is True for row in self.rows)

    @property
    def primary_success_rate_all_cases(self) -> float:
        return self.primary_success_count / len(self.rows)

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": PUBLIC_BENCHMARK_EVALUATION_REPORT_SCHEMA_ID,
            "evaluator_id": PUBLIC_BENCHMARK_EVALUATOR_ID,
            "protocol_sha256": self.protocol_sha256,
            "materialization_manifest_sha256": (
                self.materialization_manifest_sha256
            ),
            "engine_commit": self.engine_commit,
            "environment_fingerprint_sha256": (
                self.environment_fingerprint_sha256
            ),
            "command": list(self.command),
            "seed": self.seed,
            "case_count": len(self.rows),
            "evaluation_success_count": self.success_count,
            "evaluation_failure_count": self.failure_count,
            "primary_success_count": self.primary_success_count,
            "primary_success_rate_all_cases": (
                self.primary_success_rate_all_cases
            ),
            "failure_rows_retained": True,
            "denominator": "all_materialization_manifest_cases",
            "rmsd_method": (
                "minimum_direct_receptor_frame_heavy_atom_rmsd_over_"
                "exact_reference_to_candidate_bijections"
            ),
            "rmsd_threshold_angstrom": (
                PUBLIC_BENCHMARK_PRIMARY_RMSD_THRESHOLD_ANGSTROM
            ),
            "symmetry_permutation_direction": (
                PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION
            ),
            "legacy_materialization_direction_present": (
                self.legacy_materialization_direction_present
            ),
            "network_fetch_performed": False,
            "ligand_only_alignment_performed": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
            "rows": [row.to_dict() for row in self.rows],
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "report_sha256": self.report_sha256}


def _evaluate_case(
    ordinal: int,
    case: PublicBenchmarkEvaluationCaseInput,
) -> PublicBenchmarkEvaluationRow:
    reference_coordinates = _frame(case.reference_system, name="reference_system")
    candidate_coordinates = _frame(case.candidate_system, name="candidate_system")
    reference_heavy = reference_coordinates[
        torch.tensor(_heavy_indices(case.reference_system), dtype=torch.long)
    ]
    candidate_heavy = candidate_coordinates[
        torch.tensor(
            _heavy_indices(case.ligand_identity_seed_system), dtype=torch.long
        )
    ]
    rmsd = symmetry_aware_rmsd(
        reference_heavy,
        candidate_heavy,
        permutations=case._metric_permutations,
        align=False,
    ).rmsd_angstrom

    problem = DockingProblemIdentity(
        receptor_system_sha256=case.receptor_system_sha256,
        ligand_system_sha256=canonical_system_sha256(
            case.ligand_identity_seed_system
        ),
        pocket_definition_sha256=_pocket_definition_sha256(
            case.pocket_center,
            case.pocket_radius_angstrom,
        ),
        coordinate_frame_id="public-receptor-frame-v1",
    )
    atom_count = case.ligand_identity_seed_system.atom_count
    search_space = TorsionSearchSpace(
        local_offsets=torch.zeros((atom_count, 3), dtype=torch.float64),
        parent=torch.full((atom_count,), -1, dtype=torch.long),
        local_axes=torch.tensor(
            [[0.0, 0.0, 1.0]] * atom_count,
            dtype=torch.float64,
        ),
        rotatable_mask=torch.zeros(atom_count, dtype=torch.bool),
        root_positions=case._ordered_reference_coordinates,
    )
    baseline = generate_bounded_docking_proposals(
        search_space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=0.0,
            seed=0,
        ),
        problem=problem,
    )[0]
    proposal = baseline.with_refined_coordinates(
        candidate_coordinates,
        refiner_id="offline-public-benchmark-evaluator",
        refiner_version="1.0.0",
    )
    validity_context = PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=case._ordered_reference_coordinates,
        bond_pairs=_bond_pairs(case.ligand_identity_seed_system),
        excluded_nonbonded_pairs=case.excluded_nonbonded_pairs,
        receptor_coordinates=case.receptor_coordinates,
        pocket_center=case.pocket_center,
        chirality_centers=case.chirality_centers,
        config=PoseValidityConfig(
            pocket_radius_angstrom=case.pocket_radius_angstrom
        ),
    )
    validity = validity_context.evaluate(proposal)
    primary = bool(
        rmsd <= PUBLIC_BENCHMARK_PRIMARY_RMSD_THRESHOLD_ANGSTROM
        and validity.valid
    )
    return PublicBenchmarkEvaluationRow(
        ordinal=ordinal,
        case_id=case.case_id,
        status="success",
        materialization_sha256=case.materialization.materialization_sha256,
        candidate_artifact_sha256=case.candidate_artifact_sha256,
        rmsd_angstrom=float(rmsd),
        bounded_pose_valid=bool(validity.valid),
        primary_pose_success=primary,
        pose_validity=MappingProxyType(validity.to_dict()),
    )


def run_offline_public_benchmark_evaluation(
    materialization_manifest: PublicBenchmarkMaterializationManifest,
    case_inputs: Mapping[str, PublicBenchmarkEvaluationCaseInput],
    *,
    engine_commit: str,
    environment_fingerprint_sha256: str,
    command: Sequence[str],
    seed: int,
) -> PublicBenchmarkEvaluationReport:
    """Evaluate all materialization cases offline and retain every failure row."""

    if not isinstance(
        materialization_manifest, PublicBenchmarkMaterializationManifest
    ):
        raise TypeError(
            "materialization_manifest must be PublicBenchmarkMaterializationManifest"
        )
    if not isinstance(case_inputs, Mapping):
        raise TypeError("case_inputs must be a mapping")
    if len(materialization_manifest.rows) > MAX_PUBLIC_EVALUATION_CASES:
        raise PublicBenchmarkEvaluationError(
            "materialization manifest exceeds the evaluator case bound"
        )
    expected_case_ids = {row.case_id for row in materialization_manifest.rows}
    unexpected = set(case_inputs) - expected_case_ids
    if unexpected:
        raise PublicBenchmarkEvaluationError(
            "case_inputs contains cases outside the materialization manifest"
        )
    commit = _require_commit(engine_commit, name="engine_commit")
    environment = _require_sha256(
        environment_fingerprint_sha256,
        name="environment_fingerprint_sha256",
    )
    argv = tuple(str(value) for value in command)
    if not argv or any(not value for value in argv):
        raise PublicBenchmarkEvaluationError("command must be non-empty")
    if type(seed) is not int or not 0 <= seed <= 2**63 - 1:
        raise PublicBenchmarkEvaluationError("seed must be in [0,2**63-1]")

    rows: list[PublicBenchmarkEvaluationRow] = []
    legacy_direction = False
    for materialization_row in materialization_manifest.rows:
        materialization = materialization_row.materialization
        if materialization is not None:
            legacy_direction = legacy_direction or (
                "symmetry_permutation_direction"
                not in materialization.to_dict()
            )
        try:
            if not materialization_row.succeeded or materialization is None:
                raise PublicBenchmarkEvaluationError(
                    "materialization row failed and cannot be evaluated"
                )
            case = case_inputs.get(materialization_row.case_id)
            if case is None:
                raise PublicBenchmarkEvaluationError(
                    "predicted pose input is missing for the materialized case"
                )
            if (
                case.materialization.materialization_sha256
                != materialization.materialization_sha256
            ):
                raise PublicBenchmarkEvaluationError(
                    "evaluation input is cross-wired to another materialization"
                )
            rows.append(_evaluate_case(materialization_row.ordinal, case))
        except Exception as exc:
            receipt = failure_receipt(
                exc,
                public_message="public benchmark case evaluation failed",
            )
            rows.append(
                PublicBenchmarkEvaluationRow(
                    ordinal=materialization_row.ordinal,
                    case_id=materialization_row.case_id,
                    status="failure",
                    materialization_sha256=(
                        ""
                        if materialization is None
                        else materialization.materialization_sha256
                    ),
                    candidate_artifact_sha256=(
                        ""
                        if case_inputs.get(materialization_row.case_id) is None
                        else case_inputs[
                            materialization_row.case_id
                        ].candidate_artifact_sha256
                    ),
                    error_code=receipt.public_error_code,
                    error_message=receipt.public_message,
                    private_error_sha256=receipt.private_error_sha256,
                    private_error_byte_length=receipt.private_error_byte_length,
                )
            )

    row_tuple = tuple(rows)
    provisional = PublicBenchmarkEvaluationReport(
        protocol_sha256=materialization_manifest.protocol_sha256,
        materialization_manifest_sha256=(
            materialization_manifest.manifest_sha256
        ),
        engine_commit=commit,
        environment_fingerprint_sha256=environment,
        command=argv,
        seed=seed,
        rows=row_tuple,
        legacy_materialization_direction_present=legacy_direction,
        report_sha256="0" * 64,
    )
    report_sha256 = _sha256(provisional._projection())
    return PublicBenchmarkEvaluationReport(
        protocol_sha256=materialization_manifest.protocol_sha256,
        materialization_manifest_sha256=(
            materialization_manifest.manifest_sha256
        ),
        engine_commit=commit,
        environment_fingerprint_sha256=environment,
        command=argv,
        seed=seed,
        rows=row_tuple,
        legacy_materialization_direction_present=legacy_direction,
        report_sha256=report_sha256,
    )


__all__ = [
    "MAX_PUBLIC_EVALUATION_CASES",
    "PUBLIC_BENCHMARK_EVALUATION_REPORT_SCHEMA_ID",
    "PUBLIC_BENCHMARK_EVALUATION_ROW_SCHEMA_ID",
    "PUBLIC_BENCHMARK_EVALUATOR_ID",
    "PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION",
    "PUBLIC_BENCHMARK_PRIMARY_RMSD_THRESHOLD_ANGSTROM",
    "PublicBenchmarkEvaluationCaseInput",
    "PublicBenchmarkEvaluationError",
    "PublicBenchmarkEvaluationReport",
    "PublicBenchmarkEvaluationRow",
    "run_offline_public_benchmark_evaluation",
]
