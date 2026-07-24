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
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping, Sequence

import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import (
    DockingBudget,
    DockingIdentityError,
    DockingProblemInput,
    DockingProblemInputError,
    DockingProposalError,
    PocketDefinition,
    PoseMetricError,
    PoseValidityConfig,
    PoseValidityContext,
    PoseValidityError,
    build_authenticated_rigid_search_space,
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
    "betelgeuze_offline_public_redocking_evaluator/2.0.0"
)
PUBLIC_BENCHMARK_EVALUATION_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_evaluation_row/2.0.0"
)
PUBLIC_BENCHMARK_EVALUATION_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_evaluation_report/2.0.0"
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


class PublicBenchmarkEvaluatorDefect(RuntimeError):
    """The evaluator itself failed; this is never counted as a case failure."""


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


def _reference_to_seed_mapping_pairs(
    reference_system: AllAtomSystem,
    seed_system: AllAtomSystem,
) -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
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
    mapping_pairs: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for mapping in full_mappings:
        full_mapping = tuple(int(value) for value in mapping)
        projected = tuple(
            seed_heavy_position[int(full_mapping[reference_atom])]
            for reference_atom in reference_heavy
        )
        if sorted(projected) != list(range(len(seed_heavy))):
            raise PublicBenchmarkEvaluationError(
                "reference-to-seed heavy-atom mapping is not a bijection"
            )
        mapping_pairs.append((full_mapping, projected))
    return tuple(
        sorted(
            set(mapping_pairs),
            key=lambda pair: (pair[1], pair[0]),
        )
    )


def _reference_to_seed_mappings(
    reference_system: AllAtomSystem,
    seed_system: AllAtomSystem,
) -> tuple[
    tuple[tuple[int, ...], ...],
    tuple[tuple[int, ...], ...],
]:
    """Compatibility projection of the paired exact graph mappings."""

    pairs = _reference_to_seed_mapping_pairs(reference_system, seed_system)
    return (
        tuple(sorted({pair[0] for pair in pairs})),
        tuple(sorted({pair[1] for pair in pairs})),
    )


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
    receptor_system: AllAtomSystem
    reference_system: AllAtomSystem
    ligand_identity_seed_system: AllAtomSystem
    candidate_system: AllAtomSystem
    receptor_coordinates: torch.Tensor
    pocket_center: torch.Tensor
    pocket_radius_angstrom: float
    excluded_nonbonded_pairs: tuple[tuple[int, int], ...]
    chirality_centers: tuple[tuple[int, int, int, int], ...] = ()
    authenticated_input_sha256: str = ""
    _metric_permutations: tuple[tuple[int, ...], ...] = field(
        init=False, repr=False
    )
    _full_mapping_by_metric_permutation: tuple[tuple[int, ...], ...] = field(
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
        authenticated_input_sha256 = str(self.authenticated_input_sha256)
        if authenticated_input_sha256:
            authenticated_input_sha256 = _require_sha256(
                authenticated_input_sha256,
                name="authenticated_input_sha256",
            )
        object.__setattr__(
            self,
            "authenticated_input_sha256",
            authenticated_input_sha256,
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

        receptor_system_coordinates = _frame(
            self.receptor_system,
            name="receptor_system",
        )
        observed_receptor_system_sha256 = canonical_system_sha256(
            self.receptor_system
        )
        if observed_receptor_system_sha256 != self.receptor_system_sha256:
            raise PublicBenchmarkEvaluationError(
                "receptor system identity is cross-wired"
            )
        _frame(self.reference_system, name="reference_system")
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

        mapping_pairs = _reference_to_seed_mapping_pairs(
            self.reference_system,
            self.ligand_identity_seed_system,
        )
        metric_mappings = tuple(sorted({pair[1] for pair in mapping_pairs}))
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
        full_mapping_by_metric = tuple(
            min(
                full_mapping
                for full_mapping, projected_mapping in mapping_pairs
                if projected_mapping == metric_mapping
            )
            for metric_mapping in metric_mappings
        )
        receptor = _coordinates(
            self.receptor_coordinates,
            name="receptor_coordinates",
        )
        if not torch.equal(receptor, receptor_system_coordinates):
            raise PublicBenchmarkEvaluationError(
                "receptor_coordinates differ from the authenticated receptor system"
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
            self,
            "_full_mapping_by_metric_permutation",
            full_mapping_by_metric,
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
    authenticated_input_sha256: str = ""
    docking_problem_input_sha256: str = ""
    candidate_id: str = ""
    candidate_fingerprint_sha256: str = ""
    numeric_policy_sha256: str = ""
    rng_state_before_sha256: str = ""
    rng_state_after_sha256: str = ""
    symmetry_permutation_index: int | None = None
    symmetry_permutation_sha256: str = ""
    full_atom_mapping_sha256: str = ""
    mapping_applied_to_rmsd_and_validity: bool = False
    failure_class: str = ""
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
            "authenticated_input_sha256": self.authenticated_input_sha256,
            "docking_problem_input_sha256": (
                self.docking_problem_input_sha256
            ),
            "candidate_id": self.candidate_id,
            "candidate_fingerprint_sha256": (
                self.candidate_fingerprint_sha256
            ),
            "numeric_policy_sha256": self.numeric_policy_sha256,
            "rng_state_before_sha256": self.rng_state_before_sha256,
            "rng_state_after_sha256": self.rng_state_after_sha256,
            "symmetry_permutation_index": self.symmetry_permutation_index,
            "symmetry_permutation_sha256": (
                self.symmetry_permutation_sha256
            ),
            "full_atom_mapping_sha256": self.full_atom_mapping_sha256,
            "mapping_applied_to_rmsd_and_validity": (
                self.mapping_applied_to_rmsd_and_validity
            ),
            "failure_class": self.failure_class,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": self.private_error_byte_length,
        }


def public_benchmark_evaluation_policy_document() -> dict[str, object]:
    projection: dict[str, object] = {
        "schema_id": (
            "betelgeuze.engine_v2_public_benchmark_evaluation_policy/2.0.0"
        ),
        "evaluator_id": PUBLIC_BENCHMARK_EVALUATOR_ID,
        "metric": "symmetry_aware_direct_heavy_atom_rmsd",
        "metric_coordinate_dtype": "float64",
        "metric_device": "cpu",
        "symmetry_permutation_direction": (
            PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION
        ),
        "symmetry_selection": (
            "minimum_rmsd_then_canonical_permutation_order"
        ),
        "full_atom_mapping_selection": (
            "lexicographically_smallest_exact_full_mapping_for_selected_"
            "heavy_atom_permutation"
        ),
        "same_mapping_applied_to_rmsd_and_validity": True,
        "docking_problem_input_authenticated": True,
        "search_space_derivation_receipt_required": True,
        "numeric_policy_and_rng_identity_recorded": True,
        "case_input_failures_retained": True,
        "internal_evaluator_defects_are_fatal": True,
        "network_fetch_performed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    projection["policy_sha256"] = _sha256(projection)
    return projection


def _source_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PublicBenchmarkEvaluatorDefect(
            "evaluator source identity could not be authenticated"
        ) from exc


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
    authenticated_input_manifest_sha256: str
    authenticated_input_count: int
    all_supplied_case_inputs_authenticated: bool
    evaluator_source_sha256: str
    authentication_boundary_source_sha256: str
    evaluation_policy_sha256: str
    report_sha256: str

    @property
    def success_count(self) -> int:
        return sum(row.succeeded for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    @property
    def case_failure_count(self) -> int:
        return sum(row.failure_class == "case_failure" for row in self.rows)

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
            "case_failure_count": self.case_failure_count,
            "evaluator_defect_count": 0,
            "internal_evaluator_defects_are_fatal": True,
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
            "authenticated_input_manifest_sha256": (
                self.authenticated_input_manifest_sha256
            ),
            "authenticated_input_count": self.authenticated_input_count,
            "all_supplied_case_inputs_authenticated": (
                self.all_supplied_case_inputs_authenticated
            ),
            "evaluator_source_sha256": self.evaluator_source_sha256,
            "authentication_boundary_source_sha256": (
                self.authentication_boundary_source_sha256
            ),
            "evaluation_policy_sha256": self.evaluation_policy_sha256,
            "same_mapping_applied_to_rmsd_and_validity": True,
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
    try:
        reference_coordinates = _frame(
            case.reference_system,
            name="reference_system",
        )
        candidate_coordinates = _frame(
            case.candidate_system,
            name="candidate_system",
        )
        reference_heavy = reference_coordinates[
            torch.tensor(_heavy_indices(case.reference_system), dtype=torch.long)
        ]
        candidate_heavy = candidate_coordinates[
            torch.tensor(
                _heavy_indices(case.ligand_identity_seed_system),
                dtype=torch.long,
            )
        ]
        rmsd_result = symmetry_aware_rmsd(
            reference_heavy,
            candidate_heavy,
            permutations=case._metric_permutations,
            align=False,
        )
        selected_index = int(rmsd_result.symmetry_permutation_index)
        if not 0 <= selected_index < len(case._metric_permutations):
            raise PublicBenchmarkEvaluatorDefect(
                "symmetry metric returned an invalid permutation index"
            )
        selected_metric_mapping = case._metric_permutations[selected_index]
        selected_full_mapping = (
            case._full_mapping_by_metric_permutation[selected_index]
        )
        ordered_reference_coordinates = _reference_in_seed_order(
            reference_coordinates,
            case.ligand_identity_seed_system.atom_count,
            selected_full_mapping,
        )

        pocket = PocketDefinition(
            receptor_system_sha256=case.receptor_system_sha256,
            center_angstrom=tuple(
                float(value) for value in case.pocket_center.tolist()
            ),
            radius_angstrom=case.pocket_radius_angstrom,
            coordinate_frame_id="public-receptor-frame-v2",
            derivation_policy_id=(
                "authenticated_reference_heavy_atom_pocket/2.0.0"
            ),
            source_receipt_sha256=(
                case.materialization.materialization_sha256
            ),
            metadata={"case_id": case.case_id},
        )
        search_space, search_space_derivation = (
            build_authenticated_rigid_search_space(
                case.ligand_identity_seed_system,
                source_receipt_sha256=(
                    case.materialization.materialization_sha256
                ),
            )
        )
        problem_input = DockingProblemInput(
            receptor=case.receptor_system,
            ligand=case.ligand_identity_seed_system,
            pocket=pocket,
            search_space=search_space,
            search_space_derivation=search_space_derivation,
            source_artifact_sha256_by_role={
                "candidate": case.candidate_artifact_sha256,
                "ligand_identity_seed": (
                    case.ligand_identity_seed_artifact_sha256
                ),
                "receptor": case.receptor_artifact_sha256,
                "reference_ligands": case.reference_artifact_sha256,
            },
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
            problem=problem_input,
        )[0]
        proposal = baseline.with_refined_coordinates(
            candidate_coordinates,
            refiner_id="offline-public-benchmark-evaluator",
            refiner_version="2.0.0",
        )
        validity_context = PoseValidityContext(
            problem_fingerprint_sha256=(
                problem_input.identity.fingerprint_sha256
            ),
            reference_coordinates=ordered_reference_coordinates,
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
        rmsd = float(rmsd_result.rmsd_angstrom)
        primary = bool(
            rmsd <= PUBLIC_BENCHMARK_PRIMARY_RMSD_THRESHOLD_ANGSTROM
            and validity.valid
        )
        return PublicBenchmarkEvaluationRow(
            ordinal=ordinal,
            case_id=case.case_id,
            status="success",
            materialization_sha256=(
                case.materialization.materialization_sha256
            ),
            candidate_artifact_sha256=case.candidate_artifact_sha256,
            rmsd_angstrom=rmsd,
            bounded_pose_valid=bool(validity.valid),
            primary_pose_success=primary,
            pose_validity=MappingProxyType(validity.to_dict()),
            authenticated_input_sha256=case.authenticated_input_sha256,
            docking_problem_input_sha256=(
                problem_input.input_fingerprint_sha256
            ),
            candidate_id=proposal.candidate_id,
            candidate_fingerprint_sha256=proposal.fingerprint_sha256,
            numeric_policy_sha256=proposal.numeric_policy_sha256,
            rng_state_before_sha256=proposal.rng_state_before_sha256,
            rng_state_after_sha256=proposal.rng_state_after_sha256,
            symmetry_permutation_index=selected_index,
            symmetry_permutation_sha256=_sha256(
                {
                    "direction": (
                        PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION
                    ),
                    "mapping": list(selected_metric_mapping),
                }
            ),
            full_atom_mapping_sha256=_sha256(
                {
                    "direction": (
                        PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION
                    ),
                    "mapping": list(selected_full_mapping),
                }
            ),
            mapping_applied_to_rmsd_and_validity=True,
        )
    except PublicBenchmarkEvaluationError:
        raise
    except (
        DockingIdentityError,
        DockingProblemInputError,
        DockingProposalError,
        PoseMetricError,
        PoseValidityError,
    ) as exc:
        raise PublicBenchmarkEvaluationError(
            "case could not be evaluated under the frozen evaluator contract"
        ) from exc


def run_offline_public_benchmark_evaluation(
    materialization_manifest: PublicBenchmarkMaterializationManifest,
    case_inputs: Mapping[str, PublicBenchmarkEvaluationCaseInput],
    *,
    engine_commit: str,
    environment_fingerprint_sha256: str,
    command: Sequence[str],
    seed: int,
    authentication_boundary_source_sha256: str = "",
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
    for case_id, case in case_inputs.items():
        if not isinstance(case_id, str) or not isinstance(
            case,
            PublicBenchmarkEvaluationCaseInput,
        ):
            raise PublicBenchmarkEvaluationError(
                "case_inputs must map case IDs to prepared evaluation inputs"
            )
        if case_id != case.case_id:
            raise PublicBenchmarkEvaluationError(
                "case input key is cross-wired to another prepared input"
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
    boundary_source = str(authentication_boundary_source_sha256)
    if boundary_source:
        boundary_source = _require_sha256(
            boundary_source,
            name="authentication_boundary_source_sha256",
        )
    authenticated_input_rows = [
        {
            "ordinal": materialization_row.ordinal,
            "case_id": materialization_row.case_id,
            "authenticated_input_sha256": (
                ""
                if case_inputs.get(materialization_row.case_id) is None
                else case_inputs[
                    materialization_row.case_id
                ].authenticated_input_sha256
            ),
        }
        for materialization_row in materialization_manifest.rows
    ]
    authenticated_input_manifest_sha256 = _sha256(
        {
            "schema_id": (
                "betelgeuze.engine_v2_authenticated_evaluation_input_"
                "manifest/1.0.0"
            ),
            "materialization_manifest_sha256": (
                materialization_manifest.manifest_sha256
            ),
            "rows": authenticated_input_rows,
        }
    )
    authenticated_input_count = sum(
        bool(case.authenticated_input_sha256)
        for case in case_inputs.values()
    )
    all_supplied_case_inputs_authenticated = (
        authenticated_input_count == len(case_inputs)
    )
    evaluator_source_sha256 = _source_sha256(Path(__file__))
    evaluation_policy_sha256 = (
        public_benchmark_evaluation_policy_document()["policy_sha256"]
    )

    rows: list[PublicBenchmarkEvaluationRow] = []
    legacy_direction = False
    for materialization_row in materialization_manifest.rows:
        materialization = materialization_row.materialization
        if materialization is not None:
            legacy_direction = legacy_direction or (
                "symmetry_permutation_direction"
                not in materialization.to_dict()
            )
        case = case_inputs.get(materialization_row.case_id)
        try:
            if not materialization_row.succeeded or materialization is None:
                raise PublicBenchmarkEvaluationError(
                    "materialization row failed and cannot be evaluated"
                )
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
        except PublicBenchmarkEvaluationError as exc:
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
                        if case is None
                        else case.candidate_artifact_sha256
                    ),
                    authenticated_input_sha256=(
                        "" if case is None else case.authenticated_input_sha256
                    ),
                    failure_class="case_failure",
                    error_code=receipt.public_error_code,
                    error_message=receipt.public_message,
                    private_error_sha256=receipt.private_error_sha256,
                    private_error_byte_length=receipt.private_error_byte_length,
                )
            )
        except PublicBenchmarkEvaluatorDefect:
            raise
        except Exception as exc:
            raise PublicBenchmarkEvaluatorDefect(
                "internal evaluator defect while processing "
                f"case {materialization_row.case_id!r}"
            ) from exc

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
        authenticated_input_manifest_sha256=(
            authenticated_input_manifest_sha256
        ),
        authenticated_input_count=authenticated_input_count,
        all_supplied_case_inputs_authenticated=(
            all_supplied_case_inputs_authenticated
        ),
        evaluator_source_sha256=evaluator_source_sha256,
        authentication_boundary_source_sha256=boundary_source,
        evaluation_policy_sha256=str(evaluation_policy_sha256),
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
        authenticated_input_manifest_sha256=(
            authenticated_input_manifest_sha256
        ),
        authenticated_input_count=authenticated_input_count,
        all_supplied_case_inputs_authenticated=(
            all_supplied_case_inputs_authenticated
        ),
        evaluator_source_sha256=evaluator_source_sha256,
        authentication_boundary_source_sha256=boundary_source,
        evaluation_policy_sha256=str(evaluation_policy_sha256),
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
    "PublicBenchmarkEvaluatorDefect",
    "PublicBenchmarkEvaluationReport",
    "PublicBenchmarkEvaluationRow",
    "public_benchmark_evaluation_policy_document",
    "run_offline_public_benchmark_evaluation",
]
