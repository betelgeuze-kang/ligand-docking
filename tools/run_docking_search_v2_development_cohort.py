#!/usr/bin/env python3
"""Run the frozen nine-case Docking Search v2 development cohort.

This is benchmark/oracle tooling, not a product dispatch surface.  Reference
coordinates are consumed only to seal the predeclared known pocket and later
by the external evaluator.  The native generator receives only the receptor,
the ligand start conformer, and the sealed pocket.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from importlib import metadata
from io import BytesIO
import math
import numbers
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from types import MappingProxyType

from benchmarks.docking_search_v2.protocol import (
    CANDIDATE_SLOTS_PER_SCORED_CASE,
    CASE_IDS,
    EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
    EXTERNAL_RMSD_FACT_ORIGIN,
    EVALUATION_BATCH_SCHEMA_ID,
    EVALUATION_SIDECAR_SCHEMA_ID,
    FIXED_ALLOCATION_POLICY_ID,
    FROZEN_NATIVE_CARGO_LOCK_SHA256,
    FROZEN_NATIVE_EXTENSION_SHA256,
    FROZEN_NATIVE_SOURCE_CLOSURE_SHA256,
    FROZEN_POSEBUSTERS_EVALUATOR_SOURCE_SHA256,
    FROZEN_CASES,
    FROZEN_PROTOCOL_SHA256,
    GENERATION_POLICY_ID,
    KNOWN_POCKET_POLICY_ID,
    NATIVE_EXTENSION_VERSION,
    POSEBUSTERS_FACT_SCHEMA_ID,
    POSEBUSTERS_RMSD_METHOD_ID,
    POSEBUSTERS_EVALUATOR_ID,
    POSEBUSTERS_VERSION,
    PREPARATION_FAILURE_CASE_ID,
    PREPARATION_FAILURE_CODE,
    RESULT_SCHEMA_ID,
    ROSTER_SHA256,
    RANK_POLICY_ID,
    RANK_RECEIPT_SCHEMA_ID,
    RMSD_FACT_SCHEMA_ID,
    SEARCH_CRATE_ID,
    SEARCH_BINDING_SCHEMA_ID,
    SCORED_CASE_IDS,
    SOURCE_ARCHIVE_SHA256,
    canonical_json_bytes,
    evaluate_development_result,
    frozen_allocation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    PUBLIC_REDOCKING_ARCHIVE_SIZE_BYTES,
    PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
    PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
    PublicRedockingBenchmarkError,
    VerifiedPublicRedockingArchive,
    frozen_public_redocking_materialization_receipt_sha256,
)


RUN_SCHEMA_ID = "betelgeuze.docking_search_v2_development_cohort_run/1.1.0"
POCKET_RECEIPT_SCHEMA_ID = "betelgeuze.docking_search_v2_known_pocket/1.0.0"
GENERATION_INPUT_SCHEMA_ID = (
    "betelgeuze.docking_search_v2_generation_input_receipt/1.0.0"
)
COORDINATE_ARTIFACT_SCHEMA_ID = "betelgeuze.coordinates.f64le_xyz/1.0.0"
RDKIT_VERSION = "2022.09.5"
POCKET_MINIMUM_RADIUS_ANGSTROM = 6.0
POCKET_MARGIN_ANGSTROM = 4.0
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
_SHA256_ZERO = "0" * 64

_CHECK_IDS = (
    *PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
    *PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
)
_EPSILON_BY_ELEMENT = MappingProxyType(
    {
        "H": 0.02,
        "C": 0.12,
        "N": 0.17,
        "O": 0.20,
        "F": 0.06,
        "P": 0.20,
        "S": 0.25,
        "CL": 0.15,
        "BR": 0.18,
        "I": 0.22,
        "NA": 0.03,
        "MG": 0.06,
        "CA": 0.08,
        "CO": 0.15,
        "ZN": 0.12,
        "FE": 0.15,
    }
)

_STATUS_MAP = {
    "coarse_pruned": "pruned_coarse",
    "detailed_pruned": "pruned_detailed",
    "refinement_failed": "refinement_failed",
    "physical_rejected": "rejected_physical",
    "cluster_member": "clustered_out",
    "cluster_representative": "physical_valid_unclustered",
    "top_k": "retained_top_k",
}
_EXPECTED_REASON = {
    "coarse_pruned": frozenset({"coarse_budget"}),
    "detailed_pruned": frozenset({"detailed_budget"}),
    "refinement_failed": frozenset({"evaluator_failure", "non_finite_evaluation"}),
    "physical_rejected": frozenset(
        {
            "non_finite_coordinate",
            "coordinate_out_of_bounds",
            "ligand_self_overlap",
            "receptor_clash",
        }
    ),
    "cluster_member": frozenset({"clustered_into_representative"}),
    "cluster_representative": frozenset({"top_k_budget"}),
    "top_k": frozenset({None}),
}


class CohortRunnerError(RuntimeError):
    """A cohort input, native row, evaluator fact, or output failed closed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"{self.code}: {self.detail}")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sealed(projection: Mapping[str, object]) -> dict[str, object]:
    row = dict(projection)
    row["receipt_sha256"] = _sha256_json(row)
    return row


def _require_digest(value: object, *, name: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise CohortRunnerError("invalid_sha256", f"{name} is not lowercase SHA-256")
    return text


def _require_frozen_versions() -> dict[str, object]:
    try:
        from rdkit import rdBase
    except ImportError as exc:
        raise CohortRunnerError("rdkit_unavailable", "RDKit is required") from exc
    try:
        posebusters_version = metadata.version("posebusters")
    except metadata.PackageNotFoundError as exc:
        raise CohortRunnerError(
            "posebusters_unavailable", "PoseBusters is required"
        ) from exc
    if rdBase.rdkitVersion != RDKIT_VERSION:
        raise CohortRunnerError(
            "rdkit_version_mismatch", f"RDKit {RDKIT_VERSION} is required"
        )
    if posebusters_version != POSEBUSTERS_VERSION:
        raise CohortRunnerError(
            "posebusters_version_mismatch",
            f"PoseBusters {POSEBUSTERS_VERSION} is required",
        )
    evaluator_path = Path(__file__).with_name("run_engine_v2_public_redocking_300.py")
    evaluator_source_sha256 = _sha256_path(evaluator_path)
    if evaluator_source_sha256 != FROZEN_POSEBUSTERS_EVALUATOR_SOURCE_SHA256:
        raise CohortRunnerError(
            "evaluator_source_mismatch",
            "PoseBusters evaluator source is not the frozen implementation",
        )
    return {
        "rdkit_version": RDKIT_VERSION,
        "posebusters_version": POSEBUSTERS_VERSION,
        "runner_source_sha256": _sha256_path(Path(__file__)),
        "authenticated_evaluator_source_sha256": evaluator_source_sha256,
    }


@dataclass(frozen=True, slots=True)
class SearchPocket:
    center_angstrom: tuple[float, float, float]
    radius_angstrom: float
    policy_id: str
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """The complete generator-visible boundary; deliberately no native pose."""

    invocation_id: str
    source_seed_hex: str
    receptor_pdb: bytes
    ligand_start_sdf: bytes
    receptor_artifact_sha256: str
    ligand_start_artifact_sha256: str
    pocket: SearchPocket
    generation_input_receipt_sha256: str
    candidate_slots: int = CANDIDATE_SLOTS_PER_SCORED_CASE


@dataclass(frozen=True, slots=True)
class NativeCandidate:
    slot_index: int
    status: str
    reason: str | None
    coordinates_angstrom: tuple[tuple[float, float, float], ...]
    final_rank: int | None
    energy_kcal_per_mol: float | None
    detailed_score: float | None
    coarse_score: float | None
    native_row: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SearchResponse:
    candidates: tuple[NativeCandidate, ...]
    search_implementation_sha256: str
    native_extension_sha256: str
    search_config_sha256: str
    native_search_receipt: Mapping[str, object]
    native_backend_receipt: Mapping[str, object]
    native_result_sha256: str
    external_solver_used: bool = False


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    slot_index: int
    full_report_facts: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class EvaluationBatch:
    report_columns: tuple[str, ...]
    observations: tuple[EvaluationObservation, ...]
    evaluator_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class CandidateArtifact:
    slot_index: int
    sdf_bytes: bytes
    coordinate_bytes: bytes
    native_coordinate_sha256: str
    proposal_artifact_sha256: str
    coordinate_sha256: str
    search_status: str
    search_failure_code: str | None
    score_rank: int
    native_row: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DevelopmentCohortRun:
    result: Mapping[str, object]
    evidence: Mapping[str, object]
    run_receipt: Mapping[str, object]
    candidate_artifacts: Mapping[str, tuple[CandidateArtifact, ...]]


def derive_predeclared_known_pocket(
    native_sdf: bytes,
    *,
    case_id: str,
    native_artifact_sha256: str,
    runner_source_sha256: str,
) -> tuple[SearchPocket, dict[str, object]]:
    """Consume authenticated native coordinates and return only a sealed sphere."""

    from rdkit import Chem, rdBase

    if rdBase.rdkitVersion != RDKIT_VERSION:
        raise CohortRunnerError(
            "rdkit_version_mismatch", "pocket derivation is unpinned"
        )
    if _sha256_bytes(native_sdf) != native_artifact_sha256:
        raise CohortRunnerError(
            "native_artifact_mismatch", f"{case_id} native bytes changed"
        )
    supplier = Chem.ForwardSDMolSupplier(
        BytesIO(native_sdf), sanitize=False, removeHs=False, strictParsing=False
    )
    molecules = tuple(molecule for molecule in supplier if molecule is not None)
    if len(molecules) != 1 or molecules[0].GetNumConformers() != 1:
        raise CohortRunnerError(
            "known_pocket_input_invalid", f"{case_id} native ligand is not singular"
        )
    molecule = molecules[0]
    conformer = molecule.GetConformer()
    points = [
        tuple(float(value) for value in conformer.GetAtomPosition(atom.GetIdx()))
        for atom in molecule.GetAtoms()
        if atom.GetAtomicNum() > 1
    ]
    if not points:
        raise CohortRunnerError(
            "known_pocket_input_invalid", f"{case_id} has no heavy atoms"
        )
    center = tuple(
        math.fsum(point[axis] for point in points) / len(points) for axis in range(3)
    )
    radius = max(
        POCKET_MINIMUM_RADIUS_ANGSTROM,
        max(math.dist(point, center) for point in points) + POCKET_MARGIN_ANGSTROM,
    )
    projection: dict[str, object] = {
        "schema_id": POCKET_RECEIPT_SCHEMA_ID,
        "case_id": case_id,
        "policy_id": KNOWN_POCKET_POLICY_ID,
        "coordinate_frame_id": "posebusters-receptor-frame-v1",
        "source_role": "authenticated_native_reference_ligand",
        "source_artifact_sha256": native_artifact_sha256,
        "heavy_atom_count": len(points),
        "center_angstrom_binary64_hex": [float(value).hex() for value in center],
        "radius_angstrom_binary64_hex": radius.hex(),
        "minimum_radius_angstrom_binary64_hex": POCKET_MINIMUM_RADIUS_ANGSTROM.hex(),
        "margin_angstrom_binary64_hex": POCKET_MARGIN_ANGSTROM.hex(),
        "derived_before_search": True,
        "implementation_source_sha256": runner_source_sha256,
    }
    receipt = _sealed(projection)
    return (
        SearchPocket(
            center_angstrom=center,  # type: ignore[arg-type]
            radius_angstrom=radius,
            policy_id=KNOWN_POCKET_POLICY_ID,
            receipt_sha256=str(receipt["receipt_sha256"]),
        ),
        receipt,
    )


def _generation_request(
    *,
    case_id: str,
    case_seed: int,
    source_receipt_sha256: str,
    payloads: Mapping[str, bytes],
    pocket: SearchPocket,
) -> tuple[SearchRequest, dict[str, object]]:
    if set(payloads) != {"receptor", "reference", "native", "seed"}:
        raise CohortRunnerError(
            "materialization_roles_invalid", f"{case_id} roles changed"
        )
    projection: dict[str, object] = {
        "schema_id": GENERATION_INPUT_SCHEMA_ID,
        "case_id": case_id,
        "source_receipt_sha256": source_receipt_sha256,
        "receptor_artifact_sha256": _sha256_bytes(payloads["receptor"]),
        "ligand_start_artifact_sha256": _sha256_bytes(payloads["seed"]),
        "known_pocket_receipt_sha256": pocket.receipt_sha256,
        "case_seed": case_seed,
        "candidate_slots": CANDIDATE_SLOTS_PER_SCORED_CASE,
        "allocation_policy_id": FIXED_ALLOCATION_POLICY_ID,
        "allowed_generation_input_roles": [
            "authenticated_protein_structure",
            "authenticated_ligand_start_conformer",
            "predeclared_known_pocket",
            "public_force_field_parameters",
        ],
        "reference_pose_bytes_exposed_to_search": False,
        "rmsd_exposed_to_search": False,
        "posebusters_exposed_to_search": False,
        "baseline_outcomes_exposed_to_search": False,
    }
    receipt = _sealed(projection)
    source_seed = _sha256_json(
        {
            "case_seed": case_seed,
            "generation_input_receipt_sha256": receipt["receipt_sha256"],
        }
    )
    request = SearchRequest(
        invocation_id=_sha256_json(
            {"generation_input_receipt_sha256": receipt["receipt_sha256"]}
        ),
        source_seed_hex=source_seed,
        receptor_pdb=bytes(payloads["receptor"]),
        ligand_start_sdf=bytes(payloads["seed"]),
        receptor_artifact_sha256=str(projection["receptor_artifact_sha256"]),
        ligand_start_artifact_sha256=str(projection["ligand_start_artifact_sha256"]),
        pocket=pocket,
        generation_input_receipt_sha256=str(receipt["receipt_sha256"]),
    )
    return request, receipt


def _vector(
    first: Sequence[float], second: Sequence[float]
) -> tuple[float, float, float]:
    return tuple(float(first[index]) - float(second[index]) for index in range(3))  # type: ignore[return-value]


def _unit(value: Sequence[float], *, fallback_index: int) -> tuple[float, float, float]:
    norm = math.sqrt(math.fsum(float(component) ** 2 for component in value))
    if norm <= 1.0e-12:
        axis = fallback_index % 3
        return tuple(1.0 if index == axis else 0.0 for index in range(3))  # type: ignore[return-value]
    return tuple(float(component) / norm for component in value)  # type: ignore[return-value]


class BetelgeuzeNativeSearchAdapter:
    """Localized adapter for the product-owned Rust/native search facade."""

    def __init__(self) -> None:
        from betelgeuze_engine_v2.docking import (
            DockingSearchV2Config,
            DockingShortRangeV2Config,
        )

        self._config = DockingSearchV2Config(
            orientation_count=64,
            generated_candidate_limit=64,
            coarse_keep=64,
            refinement_keep=64,
            top_k=10,
        )
        self._short_range_config = DockingShortRangeV2Config()
        self.search_config_sha256 = _sha256_json(
            {
                "generation_policy_id": GENERATION_POLICY_ID,
                "search_config": self._config.to_native_dict(),
                "short_range_config": self._short_range_config.to_native_dict(),
                "parameter_policy": "scorer_v1_common_element_proxy/1.0.0",
                "anchor_surface_policy": "pocket_local_element_surface/1.0.0",
            }
        )

    def search(self, request: SearchRequest) -> SearchResponse:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        import torch

        from betelgeuze_engine_v2.docking import (
            DockingSearchV2Input,
            DockingSearchV2Error,
            VdwContactPolicy,
            run_docking_search_v2,
        )
        from betelgeuze_engine_v2.io import parse_pdb, parse_sdf_v2000

        receptor = parse_pdb(
            request.receptor_pdb, dtype=torch.float64, unit_cell_policy="ignore"
        )
        ligand = parse_sdf_v2000(request.ligand_start_sdf, dtype=torch.float64)
        ligand_coordinates = tuple(
            tuple(float(value) for value in row)
            for row in ligand.coordinates[0].tolist()
        )
        receptor_coordinates_all = tuple(
            tuple(float(value) for value in row)
            for row in receptor.coordinates[0].tolist()
        )
        center = request.pocket.center_angstrom
        receptor_indices = tuple(
            index
            for index, point in enumerate(receptor_coordinates_all)
            if math.dist(point, center) <= request.pocket.radius_angstrom + 4.0
        )
        if not receptor_indices:
            raise CohortRunnerError(
                "empty_pocket_receptor", "no receptor atoms are pocket-local"
            )
        radii = VdwContactPolicy().radii_angstrom

        supplier = Chem.ForwardSDMolSupplier(
            BytesIO(request.ligand_start_sdf),
            sanitize=True,
            removeHs=False,
            strictParsing=True,
        )
        rdkit_ligands = tuple(molecule for molecule in supplier if molecule is not None)
        if (
            len(rdkit_ligands) != 1
            or rdkit_ligands[0].GetNumAtoms() != ligand.atom_count
        ):
            raise CohortRunnerError(
                "ligand_preparation_failed", "start conformer changed"
            )
        rdkit_ligand = rdkit_ligands[0]
        AllChem.ComputeGasteigerCharges(
            rdkit_ligand, nIter=12, throwOnParamFailure=True
        )
        ligand_charges = [
            float(atom.GetProp("_GasteigerCharge"))
            + (
                float(atom.GetProp("_GasteigerHCharge"))
                if atom.HasProp("_GasteigerHCharge")
                else 0.0
            )
            for atom in rdkit_ligand.GetAtoms()
        ]
        residual = float(sum(atom.formal_charge for atom in ligand.atoms)) - math.fsum(
            ligand_charges
        )
        ligand_charges[
            max(range(len(ligand_charges)), key=lambda i: abs(ligand_charges[i]))
        ] += residual

        ligand_center = tuple(
            math.fsum(point[axis] for point in ligand_coordinates)
            / len(ligand_coordinates)
            for axis in range(3)
        )
        ligand_anchor_rows: list[tuple[int, int, tuple[float, float, float], str]] = []
        for atom in ligand.atoms:
            element = atom.element.upper()
            kinds: list[str] = []
            if atom.formal_charge > 0:
                kinds.append("positive")
            if atom.formal_charge < 0:
                kinds.append("negative")
            if element == "N":
                kinds.append("hydrogen_bond_donor")
            if element in {"N", "O", "S"}:
                kinds.append("hydrogen_bond_acceptor")
            if element in {"C", "S", "F", "CL", "BR", "I"}:
                kinds.append("hydrophobe")
            if atom.aromatic:
                kinds.append("aromatic")
            direction = _unit(
                _vector(ligand_coordinates[atom.index], ligand_center),
                fallback_index=atom.index,
            )
            for kind in dict.fromkeys(kinds):
                ligand_anchor_rows.append(
                    (len(ligand_anchor_rows), atom.index, direction, kind)
                )
        if not ligand_anchor_rows or len(ligand_anchor_rows) > 256:
            raise CohortRunnerError(
                "ligand_anchor_preparation_failed", "anchor count is invalid"
            )

        receptor_charges = [float(atom.formal_charge) for atom in receptor.atoms]
        surface_rows: list[
            tuple[int, tuple[float, float, float], tuple[float, float, float], str]
        ] = []
        for receptor_index in receptor_indices:
            atom = receptor.atoms[receptor_index]
            element = atom.element.upper()
            normal = _unit(
                _vector(center, receptor_coordinates_all[receptor_index]),
                fallback_index=receptor_index,
            )
            radius = float(radii.get(element, 0.0))
            if radius <= 0.0 or element not in _EPSILON_BY_ELEMENT:
                raise CohortRunnerError("unsupported_vdw_element", element)
            position = tuple(
                receptor_coordinates_all[receptor_index][axis] + radius * normal[axis]
                for axis in range(3)
            )
            kinds: list[str] = []
            if atom.formal_charge > 0:
                kinds.append("positive")
            if atom.formal_charge < 0:
                kinds.append("negative")
            if element == "N":
                kinds.append("hydrogen_bond_acceptor")
            if element in {"O", "S"}:
                kinds.append("hydrogen_bond_donor")
            if element in {"C", "S", "F", "CL", "BR", "I"}:
                kinds.append("hydrophobe")
            for kind in dict.fromkeys(kinds):
                surface_rows.append((len(surface_rows), position, normal, kind))
        if not surface_rows:
            raise CohortRunnerError(
                "surface_preparation_failed", "surface count is invalid"
            )

        # Bound the compatible single-pair denominator before the Rust core
        # constructs O(P^2) dual-anchor combinations.  Selection is geometric
        # (nearest pocket-facing samples), fixed before any score is observed.
        compatible_ligand_kind = {
            "hydrogen_bond_donor": "hydrogen_bond_acceptor",
            "hydrogen_bond_acceptor": "hydrogen_bond_donor",
            "hydrophobe": "hydrophobe",
            "aromatic": "aromatic",
            "positive": "negative",
            "negative": "positive",
        }
        ligand_kind_counts = {
            kind: sum(row[3] == kind for row in ligand_anchor_rows)
            for kind in compatible_ligand_kind.values()
        }
        rows_by_kind = {
            kind: [row for row in surface_rows if row[3] == kind]
            for kind in compatible_ligand_kind
        }
        active_kinds = tuple(
            kind
            for kind in compatible_ligand_kind
            if rows_by_kind[kind]
            and ligand_kind_counts[compatible_ligand_kind[kind]] > 0
        )
        if not active_kinds:
            raise CohortRunnerError(
                "surface_preparation_failed",
                "no compatible pocket-local surface exists",
            )
        pair_budget_per_kind = 192 // len(active_kinds)
        selected_surface_rows = []
        for kind in active_kinds:
            compatible_count = ligand_kind_counts[compatible_ligand_kind[kind]]
            take = max(1, pair_budget_per_kind // compatible_count)
            ordered = sorted(
                rows_by_kind[kind],
                key=lambda row: (math.dist(row[1], center), row[0]),
            )
            selected_surface_rows.extend(ordered[:take])
        surface_rows = [
            (index, row[1], row[2], row[3])
            for index, row in enumerate(selected_surface_rows)
        ]
        compatible_pair_count = sum(
            ligand_kind_counts[compatible_ligand_kind[row[3]]] for row in surface_rows
        )
        if not 1 <= compatible_pair_count <= 192 or len(surface_rows) > 4096:
            raise CohortRunnerError(
                "surface_preparation_failed", "compatible anchor-pair budget is invalid"
            )

        search_input = DockingSearchV2Input(
            source_seed=request.source_seed_hex,
            ligand_coordinates_angstrom=ligand_coordinates,
            ligand_vdw_radii_angstrom=[
                float(radii[atom.element.upper()]) for atom in ligand.atoms
            ],
            ligand_epsilon_kcal_per_mol=[
                float(_EPSILON_BY_ELEMENT[atom.element.upper()])
                for atom in ligand.atoms
            ],
            ligand_charge_elementary=ligand_charges,
            ligand_anchor_ids=[row[0] for row in ligand_anchor_rows],
            ligand_anchor_atom_indices=[row[1] for row in ligand_anchor_rows],
            ligand_anchor_directions=[row[2] for row in ligand_anchor_rows],
            ligand_anchor_kinds=[row[3] for row in ligand_anchor_rows],
            receptor_coordinates_angstrom=[
                receptor_coordinates_all[index] for index in receptor_indices
            ],
            receptor_vdw_radii_angstrom=[
                float(radii[receptor.atoms[index].element.upper()])
                for index in receptor_indices
            ],
            receptor_epsilon_kcal_per_mol=[
                float(_EPSILON_BY_ELEMENT[receptor.atoms[index].element.upper()])
                for index in receptor_indices
            ],
            receptor_charge_elementary=[
                receptor_charges[index] for index in receptor_indices
            ],
            surface_ids=[row[0] for row in surface_rows],
            surface_positions_angstrom=[row[1] for row in surface_rows],
            surface_outward_normals=[row[2] for row in surface_rows],
            surface_anchor_kinds=[row[3] for row in surface_rows],
        )
        try:
            native = run_docking_search_v2(
                search_input,
                config=self._config,
                short_range_config=self._short_range_config,
            )
        except DockingSearchV2Error as exc:
            raise CohortRunnerError("native_search_failed", str(exc)) from exc
        document = native.to_dict()
        if (
            document.get("claim_safe") is not False
            or document.get("claim_blockers")
            != ["public_development_cohort_gate_not_passed"]
            or len(native.candidate_rows) != CANDIDATE_SLOTS_PER_SCORED_CASE
        ):
            raise CohortRunnerError(
                "native_result_invalid", "native result widened or changed"
            )
        backend = dict(native.native_backend_receipt)
        candidates = tuple(
            NativeCandidate(
                slot_index=row.slot_index,
                status=row.status,
                reason=row.reason,
                coordinates_angstrom=row.coordinates_angstrom,
                final_rank=row.final_rank,
                energy_kcal_per_mol=row.energy_kcal_per_mol,
                detailed_score=row.detailed_score,
                coarse_score=row.coarse_score,
                native_row=row.to_dict(),
            )
            for row in native.candidate_rows
        )
        return SearchResponse(
            candidates=candidates,
            search_implementation_sha256=_require_digest(
                backend.get("native_source_closure_sha256"),
                name="native source closure",
            ),
            native_extension_sha256=_require_digest(
                backend.get("extension_sha256"), name="native extension"
            ),
            search_config_sha256=self.search_config_sha256,
            native_search_receipt=dict(native.search_receipt),
            native_backend_receipt=backend,
            native_result_sha256=_sha256_json(document),
            external_solver_used=False,
        )


def _canonical_report_scalar(value: object) -> object:
    if value is None or isinstance(value, str):
        return value
    if (
        type(value).__name__ == "NAType"
        and type(value).__module__ == "pandas._libs.missing"
    ):
        return {"missing_scalar": "pandas.NA"}
    if isinstance(value, bool) or (
        type(value).__name__ == "bool_" and type(value).__module__.startswith("numpy")
    ):
        return bool(value)
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        if math.isfinite(number):
            return number
        return {"non_finite_float": number.hex()}
    raise CohortRunnerError(
        "posebusters_fact_type_unsupported",
        f"unsupported report scalar {type(value)!r}",
    )


class PoseBusters031Evaluator:
    def __init__(self, *, implementation_source_sha256: str) -> None:
        self._source_sha256 = _require_digest(
            implementation_source_sha256, name="evaluator source"
        )

    def evaluate(
        self,
        *,
        candidate_sdf_payload: bytes,
        native_sdf: bytes,
        receptor_pdb: bytes,
        expected_count: int,
    ) -> EvaluationBatch:
        from tools.run_engine_v2_public_redocking_300 import (
            _load_posebusters,
            _posebusters_molecules,
        )

        predicted, native, receptor = _posebusters_molecules(
            output_payload=candidate_sdf_payload,
            native_payload=native_sdf,
            receptor_payload=receptor_pdb,
            expected_pose_count=expected_count,
        )
        report = _load_posebusters()(config="redock", top_n=expected_count).bust(
            predicted, native, receptor, full_report=True
        )
        columns = tuple(str(column) for column in report.columns)
        if len(report) != expected_count or not {"rmsd", *_CHECK_IDS}.issubset(columns):
            raise CohortRunnerError(
                "posebusters_report_incomplete", "full report changed"
            )
        observations = tuple(
            EvaluationObservation(
                slot_index=index,
                full_report_facts={
                    column: _canonical_report_scalar(report.iloc[index][column])
                    for column in columns
                },
            )
            for index in range(expected_count)
        )
        return EvaluationBatch(
            report_columns=columns,
            observations=observations,
            evaluator_identity={
                "evaluator_id": POSEBUSTERS_EVALUATOR_ID,
                "posebusters_version": POSEBUSTERS_VERSION,
                "rmsd_method_id": POSEBUSTERS_RMSD_METHOD_ID,
                "full_report": True,
                "implementation_source_sha256": self._source_sha256,
                "external_solver_used_for_generation": False,
            },
        )


def _rank_candidates(
    candidates: Sequence[NativeCandidate],
    *,
    case_id: str,
) -> tuple[dict[int, int], dict[str, object]]:
    """Rank solely from sealed native fields; no oracle values are accepted."""

    def finite_or_infinity(value: float | None) -> float:
        if value is None or not math.isfinite(float(value)):
            return math.inf
        return float(value)

    final_ranks = [row.final_rank for row in candidates if row.final_rank is not None]
    if len(final_ranks) != len(set(final_ranks)) or any(
        rank is None or rank < 1 for rank in final_ranks
    ):
        raise CohortRunnerError(
            "native_rank_invalid", "final ranks are not unique positive"
        )

    def key(row: NativeCandidate) -> tuple[object, ...]:
        if row.final_rank is not None:
            return (0, row.final_rank, row.slot_index)
        return (
            1,
            finite_or_infinity(row.energy_kcal_per_mol),
            finite_or_infinity(row.detailed_score),
            finite_or_infinity(row.coarse_score),
            row.slot_index,
        )

    ordered_slots = tuple(row.slot_index for row in sorted(candidates, key=key))
    if tuple(sorted(ordered_slots)) != tuple(range(CANDIDATE_SLOTS_PER_SCORED_CASE)):
        raise CohortRunnerError(
            "native_slot_set_invalid", "slots are not exactly 0..63"
        )
    ranks = {slot: index + 1 for index, slot in enumerate(ordered_slots)}
    receipt = _sealed(
        {
            "schema_id": RANK_RECEIPT_SCHEMA_ID,
            "case_id": case_id,
            "policy_id": RANK_POLICY_ID,
            "candidate_count": CANDIDATE_SLOTS_PER_SCORED_CASE,
            "ranked_candidates": [
                {
                    "score_rank": rank,
                    "slot_index": slot,
                    "native_row_sha256": _sha256_json(
                        dict(candidates[slot].native_row)
                    ),
                }
                for rank, slot in enumerate(ordered_slots, start=1)
            ],
            "oracle_fields_used": [],
            "native_fields_used": [
                "final_rank",
                "energy_kcal_per_mol",
                "detailed_score",
                "coarse_score",
                "slot_index",
            ],
        }
    )
    return ranks, receipt


def _coordinate_bytes(
    coordinates: Sequence[Sequence[float]],
) -> bytes:
    rows = tuple(tuple(float(component) for component in row) for row in coordinates)
    if not rows or any(
        len(row) != 3 or any(not math.isfinite(component) for component in row)
        for row in rows
    ):
        raise CohortRunnerError(
            "candidate_coordinates_invalid", "coordinates are not finite [N,3]"
        )
    output = bytearray(b"BGCOORD1\0")
    output.extend(struct.pack("<Q", len(rows)))
    for row in rows:
        output.extend(struct.pack("<ddd", *row))
    return bytes(output)


def _serialize_candidate_sdf(
    ligand_start_sdf: bytes,
    coordinates: Sequence[Sequence[float]],
    *,
    case_id: str,
    slot_index: int,
) -> tuple[bytes, bytes, str]:
    from rdkit import Chem, rdBase
    import torch

    from betelgeuze_engine_v2.io import parse_sdf_v2000

    if rdBase.rdkitVersion != RDKIT_VERSION:
        raise CohortRunnerError(
            "rdkit_version_mismatch", "SDF serialization is unpinned"
        )
    supplier = Chem.ForwardSDMolSupplier(
        BytesIO(ligand_start_sdf), sanitize=True, removeHs=False, strictParsing=True
    )
    molecules = tuple(molecule for molecule in supplier if molecule is not None)
    if len(molecules) != 1 or len(coordinates) != molecules[0].GetNumAtoms():
        raise CohortRunnerError(
            "candidate_topology_mismatch", f"{case_id} slot {slot_index}"
        )
    molecule = Chem.Mol(molecules[0])
    molecule.RemoveAllConformers()
    conformer = Chem.Conformer(molecule.GetNumAtoms())
    for atom_index, row in enumerate(coordinates):
        if len(row) != 3 or any(not math.isfinite(float(value)) for value in row):
            raise CohortRunnerError(
                "candidate_coordinates_invalid", f"{case_id} slot {slot_index}"
            )
        conformer.SetAtomPosition(atom_index, tuple(float(value) for value in row))
    molecule.AddConformer(conformer, assignId=True)
    molecule.SetProp("_Name", f"{case_id}_docking_search_v2_slot_{slot_index:02d}")
    block = Chem.MolToMolBlock(molecule, confId=0, includeStereo=True, kekulize=True)
    sdf_bytes = (block.rstrip("\n") + "\n$$$$\n").encode("ascii")
    if len(sdf_bytes) > MAX_ARTIFACT_BYTES or b"\r" in sdf_bytes:
        raise CohortRunnerError("candidate_sdf_invalid", f"{case_id} slot {slot_index}")
    parsed = parse_sdf_v2000(sdf_bytes, dtype=torch.float64)
    if parsed.atom_count != molecule.GetNumAtoms():
        raise CohortRunnerError(
            "candidate_sdf_roundtrip_failed", f"{case_id} slot {slot_index}"
        )
    evaluated_coordinates = tuple(
        tuple(float(value) for value in row) for row in parsed.coordinates[0].tolist()
    )
    coordinate_bytes = _coordinate_bytes(evaluated_coordinates)
    native_coordinate_sha256 = _sha256_bytes(_coordinate_bytes(coordinates))
    return sdf_bytes, coordinate_bytes, native_coordinate_sha256


def _validate_native_candidate(
    row: NativeCandidate, *, expected_slot: int
) -> tuple[str, str | None]:
    if row.slot_index != expected_slot or row.status not in _STATUS_MAP:
        raise CohortRunnerError(
            "native_candidate_schema_invalid", f"slot {expected_slot}"
        )
    expected_reasons = _EXPECTED_REASON[row.status]
    if row.reason not in expected_reasons:
        raise CohortRunnerError(
            "native_status_reason_mismatch",
            f"slot {expected_slot} status={row.status!r} reason={row.reason!r}",
        )
    status = _STATUS_MAP[row.status]
    failure_code = (
        row.reason if status in {"refinement_failed", "rejected_physical"} else None
    )
    return status, failure_code


def _seal_candidate_artifacts(
    *,
    case_id: str,
    ligand_start_sdf: bytes,
    generation_input_receipt_sha256: str,
    known_pocket_receipt_sha256: str,
    response: SearchResponse,
) -> tuple[tuple[CandidateArtifact, ...], dict[str, object], dict[str, object]]:
    if response.external_solver_used:
        raise CohortRunnerError(
            "external_solver_generation_forbidden",
            "native response declared an external solver",
        )
    if len(response.candidates) != CANDIDATE_SLOTS_PER_SCORED_CASE:
        raise CohortRunnerError(
            "native_candidate_budget_mismatch", f"{case_id} is not 64 slots"
        )
    ranks, rank_receipt = _rank_candidates(response.candidates, case_id=case_id)
    provisional: list[dict[str, object]] = []
    for expected_slot, row in enumerate(response.candidates):
        status, failure_code = _validate_native_candidate(
            row, expected_slot=expected_slot
        )
        sdf_bytes, coordinate_bytes, native_coordinate_sha256 = (
            _serialize_candidate_sdf(
                ligand_start_sdf,
                row.coordinates_angstrom,
                case_id=case_id,
                slot_index=expected_slot,
            )
        )
        provisional.append(
            {
                "slot_index": expected_slot,
                "sdf_bytes": sdf_bytes,
                "coordinate_bytes": coordinate_bytes,
                "native_coordinate_sha256": native_coordinate_sha256,
                "proposal_artifact_sha256": _sha256_bytes(sdf_bytes),
                "coordinate_sha256": _sha256_bytes(coordinate_bytes),
                "search_status": status,
                "search_failure_code": failure_code,
                "score_rank": ranks[expected_slot],
                "native_row": dict(row.native_row),
            }
        )
    search_projection: dict[str, object] = {
        "schema_id": SEARCH_BINDING_SCHEMA_ID,
        "case_id": case_id,
        "generation_policy_id": GENERATION_POLICY_ID,
        "generation_input_receipt_sha256": _require_digest(
            generation_input_receipt_sha256, name="generation input receipt"
        ),
        "known_pocket_receipt_sha256": _require_digest(
            known_pocket_receipt_sha256, name="known pocket receipt"
        ),
        "search_config_sha256": response.search_config_sha256,
        "search_implementation_sha256": response.search_implementation_sha256,
        "native_extension_sha256": response.native_extension_sha256,
        "native_backend_receipt_sha256": response.native_backend_receipt.get(
            "receipt_sha256"
        ),
        "native_search_receipt_sha256": _sha256_json(
            dict(response.native_search_receipt)
        ),
        "native_search_receipt": dict(response.native_search_receipt),
        "native_result_sha256": response.native_result_sha256,
        "rank_receipt_sha256": rank_receipt["receipt_sha256"],
        "candidate_count": CANDIDATE_SLOTS_PER_SCORED_CASE,
        "candidate_subjects": [
            {
                "slot_index": row["slot_index"],
                "proposal_artifact_sha256": row["proposal_artifact_sha256"],
                "coordinate_sha256": row["coordinate_sha256"],
                "native_coordinate_sha256": row["native_coordinate_sha256"],
                "native_row_sha256": _sha256_json(row["native_row"]),
                "score_rank": row["score_rank"],
                "search_status": row["search_status"],
                "search_failure_code": row["search_failure_code"],
            }
            for row in provisional
        ],
        "external_solver_used": False,
        "rmsd_used_for_ranking": False,
        "posebusters_used_for_ranking": False,
    }
    search_receipt = _sealed(search_projection)
    artifacts = tuple(
        CandidateArtifact(**row)  # type: ignore[arg-type]
        for row in provisional
    )
    return artifacts, search_receipt, rank_receipt


def _bind_evaluation(
    *,
    case_id: str,
    artifacts: Sequence[CandidateArtifact],
    batch: EvaluationBatch,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    columns = tuple(batch.report_columns)
    if (
        len(columns) != len(set(columns))
        or not {"rmsd", *_CHECK_IDS}.issubset(columns)
        or len(batch.observations) != len(artifacts)
    ):
        raise CohortRunnerError(
            "external_evaluation_incomplete", f"{case_id} report changed"
        )
    identity = dict(batch.evaluator_identity)
    if identity != {
        "evaluator_id": POSEBUSTERS_EVALUATOR_ID,
        "posebusters_version": POSEBUSTERS_VERSION,
        "rmsd_method_id": POSEBUSTERS_RMSD_METHOD_ID,
        "full_report": True,
        "implementation_source_sha256": identity.get("implementation_source_sha256"),
        "external_solver_used_for_generation": False,
    }:
        raise CohortRunnerError(
            "external_evaluator_identity_invalid", f"{case_id} evaluator changed"
        )
    _require_digest(identity["implementation_source_sha256"], name="evaluator source")
    protocol_rows: list[dict[str, object]] = []
    sidecars: list[dict[str, object]] = []
    for artifact, observation in zip(artifacts, batch.observations, strict=True):
        if observation.slot_index != artifact.slot_index:
            raise CohortRunnerError(
                "external_fact_slot_mismatch", f"{case_id} facts reordered"
            )
        facts = dict(observation.full_report_facts)
        if set(facts) != set(columns):
            raise CohortRunnerError(
                "external_fact_columns_mismatch", f"{case_id} facts incomplete"
            )
        rmsd_value = facts["rmsd"]
        if isinstance(rmsd_value, bool) or not isinstance(rmsd_value, numbers.Real):
            raise CohortRunnerError(
                "external_rmsd_invalid", f"{case_id} RMSD is not numeric"
            )
        rmsd = float(rmsd_value)
        if not math.isfinite(rmsd) or rmsd < 0.0:
            raise CohortRunnerError(
                "external_rmsd_invalid", f"{case_id} RMSD is invalid"
            )
        checks = {check_id: facts[check_id] for check_id in _CHECK_IDS}
        if any(type(value) is not bool for value in checks.values()):
            raise CohortRunnerError(
                "posebusters_check_invalid", f"{case_id} check is not boolean"
            )
        exact_valid = all(checks.values())
        subject = {
            "proposal_artifact_sha256": artifact.proposal_artifact_sha256,
            "coordinate_sha256": artifact.coordinate_sha256,
        }
        rmsd_receipt = _sealed(
            {
                "schema_id": RMSD_FACT_SCHEMA_ID,
                "case_id": case_id,
                "slot_index": artifact.slot_index,
                "origin": EXTERNAL_RMSD_FACT_ORIGIN,
                **subject,
                "rmsd_angstrom": rmsd,
                "evaluator_identity": identity,
            }
        )
        posebusters_receipt = _sealed(
            {
                "schema_id": POSEBUSTERS_FACT_SCHEMA_ID,
                "case_id": case_id,
                "slot_index": artifact.slot_index,
                "origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
                **subject,
                "posebusters_exact_valid": exact_valid,
                "chemical_check_ids": list(
                    PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS
                ),
                "geometric_check_ids": list(
                    PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS
                ),
                "check_facts": checks,
                "full_report_columns": list(columns),
                "full_report_facts": facts,
                "evaluator_identity": identity,
            }
        )
        sidecars.append(
            {
                "slot_index": artifact.slot_index,
                "native_coordinate_sha256": artifact.native_coordinate_sha256,
                "rmsd_fact": rmsd_receipt,
                "posebusters_fact": posebusters_receipt,
            }
        )
        protocol_rows.append(
            {
                "slot_index": artifact.slot_index,
                "score_rank": artifact.score_rank,
                "search_status": artifact.search_status,
                "search_failure_code": artifact.search_failure_code,
                "proposal_artifact_sha256": artifact.proposal_artifact_sha256,
                "coordinate_sha256": artifact.coordinate_sha256,
                "native_coordinate_sha256": artifact.native_coordinate_sha256,
                "native_row_sha256": _sha256_json(dict(artifact.native_row)),
                "candidate_search_receipt_sha256": "",
                "rmsd_angstrom": rmsd,
                "rmsd_fact_origin": EXTERNAL_RMSD_FACT_ORIGIN,
                "rmsd_subject_proposal_artifact_sha256": artifact.proposal_artifact_sha256,
                "rmsd_subject_coordinate_sha256": artifact.coordinate_sha256,
                "rmsd_fact_receipt_sha256": rmsd_receipt["receipt_sha256"],
                "posebusters_exact_valid": exact_valid,
                "posebusters_fact_origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
                "posebusters_subject_proposal_artifact_sha256": artifact.proposal_artifact_sha256,
                "posebusters_subject_coordinate_sha256": artifact.coordinate_sha256,
                "posebusters_fact_receipt_sha256": posebusters_receipt[
                    "receipt_sha256"
                ],
            }
        )
    batch_receipt = _sealed(
        {
            "schema_id": EVALUATION_BATCH_SCHEMA_ID,
            "case_id": case_id,
            "candidate_count": len(sidecars),
            "report_columns": list(columns),
            "candidate_fact_receipt_sha256s": [
                {
                    "slot_index": row["slot_index"],
                    "rmsd_fact_receipt_sha256": row["rmsd_fact"]["receipt_sha256"],
                    "posebusters_fact_receipt_sha256": row["posebusters_fact"][
                        "receipt_sha256"
                    ],
                }
                for row in sidecars
            ],
            "evaluator_identity": identity,
        }
    )
    evaluation_sidecar = _sealed(
        {
            "schema_id": EVALUATION_SIDECAR_SCHEMA_ID,
            "case_id": case_id,
            "batch_receipt": batch_receipt,
            "candidate_facts": sidecars,
        }
    )
    return protocol_rows, evaluation_sidecar


@dataclass(frozen=True, slots=True)
class _PreparedCase:
    case_id: str
    case_seed: int
    source_receipt_sha256: str
    materialization_receipt: Mapping[str, object]
    payloads: Mapping[str, bytes]
    pocket: SearchPocket
    pocket_receipt: Mapping[str, object]
    request: SearchRequest
    generation_input_receipt: Mapping[str, object]


def _load_and_prepare_cases(
    archive_path: Path,
    *,
    runner_source_sha256: str,
) -> tuple[_PreparedCase, ...]:
    if PUBLIC_REDOCKING_ARCHIVE_SIZE_BYTES != 53_660_397:
        raise CohortRunnerError(
            "archive_size_contract_changed", "frozen byte count changed"
        )
    prepared: list[_PreparedCase] = []
    try:
        with VerifiedPublicRedockingArchive.open(archive_path) as archive:
            if archive.archive_sha256 != SOURCE_ARCHIVE_SHA256:
                raise CohortRunnerError(
                    "archive_hash_mismatch", "source archive changed"
                )
            materialized = []
            for frozen in FROZEN_CASES:
                receipt, raw_payloads = archive.verified_case(frozen.case_id)
                expected_receipt = (
                    frozen_public_redocking_materialization_receipt_sha256(
                        frozen.case_id
                    )
                )
                if (
                    expected_receipt != frozen.source_receipt_sha256
                    or receipt.receipt_sha256 != expected_receipt
                    or receipt.source_archive_sha256 != SOURCE_ARCHIVE_SHA256
                ):
                    raise CohortRunnerError(
                        "source_receipt_mismatch", f"{frozen.case_id} receipt changed"
                    )
                payloads = {
                    role: bytes(payload) for role, payload in raw_payloads.items()
                }
                if set(payloads) != {"receptor", "reference", "native", "seed"}:
                    raise CohortRunnerError(
                        "materialization_roles_invalid",
                        f"{frozen.case_id} roles changed",
                    )
                observed = {
                    role: _sha256_bytes(payload) for role, payload in payloads.items()
                }
                if observed != receipt.input_artifact_sha256s_by_role:
                    raise CohortRunnerError(
                        "materialization_payload_mismatch",
                        f"{frozen.case_id} payload changed",
                    )
                materialized.append((frozen, receipt, payloads))
            if archive.verify_complete_sha256() != SOURCE_ARCHIVE_SHA256:
                raise CohortRunnerError(
                    "archive_hash_mismatch", "archive changed after reads"
                )
    except PublicRedockingBenchmarkError as exc:
        raise CohortRunnerError("archive_verification_failed", str(exc)) from exc

    # Seal every pocket and every fixed request before the first search call.
    for frozen, receipt, payloads in materialized:
        pocket, pocket_receipt = derive_predeclared_known_pocket(
            payloads["native"],
            case_id=frozen.case_id,
            native_artifact_sha256=receipt.native_artifact_sha256,
            runner_source_sha256=runner_source_sha256,
        )
        request, generation_receipt = _generation_request(
            case_id=frozen.case_id,
            case_seed=receipt.frozen_case_seed,
            source_receipt_sha256=receipt.receipt_sha256,
            payloads=payloads,
            pocket=pocket,
        )
        prepared.append(
            _PreparedCase(
                case_id=frozen.case_id,
                case_seed=receipt.frozen_case_seed,
                source_receipt_sha256=receipt.receipt_sha256,
                materialization_receipt=receipt.to_dict(),
                payloads=MappingProxyType(payloads),
                pocket=pocket,
                pocket_receipt=pocket_receipt,
                request=request,
                generation_input_receipt=generation_receipt,
            )
        )
    if tuple(row.case_id for row in prepared) != CASE_IDS:
        raise CohortRunnerError("cohort_order_mismatch", "nine-case roster changed")
    return tuple(prepared)


def run_development_cohort(
    source_archive: str | Path,
) -> DevelopmentCohortRun:
    """Run exactly eight 64-slot native searches and then external evaluation."""

    environment = _require_frozen_versions()
    archive_path = Path(source_archive).resolve()
    cases = _load_and_prepare_cases(
        archive_path,
        runner_source_sha256=str(environment["runner_source_sha256"]),
    )
    active_search = BetelgeuzeNativeSearchAdapter()
    active_evaluator = PoseBusters031Evaluator(
        implementation_source_sha256=str(
            environment["authenticated_evaluator_source_sha256"]
        )
    )

    # Generation is completed and sealed for all cases before any oracle call.
    searches: dict[str, SearchResponse] = {}
    artifacts_by_case: dict[str, tuple[CandidateArtifact, ...]] = {}
    search_receipts: dict[str, dict[str, object]] = {}
    rank_receipts: dict[str, dict[str, object]] = {}
    for prepared in cases:
        if prepared.case_id == PREPARATION_FAILURE_CASE_ID:
            continue
        response = active_search.search(prepared.request)
        artifacts, search_receipt, rank_receipt = _seal_candidate_artifacts(
            case_id=prepared.case_id,
            ligand_start_sdf=prepared.payloads["seed"],
            generation_input_receipt_sha256=str(
                prepared.generation_input_receipt["receipt_sha256"]
            ),
            known_pocket_receipt_sha256=prepared.pocket.receipt_sha256,
            response=response,
        )
        searches[prepared.case_id] = response
        artifacts_by_case[prepared.case_id] = artifacts
        search_receipts[prepared.case_id] = search_receipt
        rank_receipts[prepared.case_id] = rank_receipt
    if tuple(searches) != SCORED_CASE_IDS:
        raise CohortRunnerError("scored_case_order_mismatch", "native searches changed")

    identities = {
        (
            response.search_implementation_sha256,
            response.native_extension_sha256,
            response.search_config_sha256,
            response.external_solver_used,
        )
        for response in searches.values()
    }
    if len(identities) != 1:
        raise CohortRunnerError(
            "native_identity_drift", "case searches used different builds"
        )
    search_impl, native_extension, search_config, external_used = next(iter(identities))
    if external_used:
        raise CohortRunnerError(
            "external_solver_generation_forbidden", "identity widened"
        )
    _require_digest(search_impl, name="search implementation")
    _require_digest(native_extension, name="native extension")
    _require_digest(search_config, name="search config")
    if (
        search_impl != FROZEN_NATIVE_SOURCE_CLOSURE_SHA256
        or native_extension != FROZEN_NATIVE_EXTENSION_SHA256
    ):
        raise CohortRunnerError(
            "native_identity_mismatch",
            "native search does not match the frozen source closure and extension",
        )
    native_backend_receipts = [
        dict(response.native_backend_receipt) for response in searches.values()
    ]
    native_backend_receipt = native_backend_receipts[0]
    if any(row != native_backend_receipt for row in native_backend_receipts[1:]):
        raise CohortRunnerError(
            "native_identity_drift", "case searches used different backend receipts"
        )
    if (
        native_backend_receipt.get("native_source_closure_sha256") != search_impl
        or native_backend_receipt.get("extension_sha256") != native_extension
        or native_backend_receipt.get("cargo_lock_sha256")
        != FROZEN_NATIVE_CARGO_LOCK_SHA256
        or native_backend_receipt.get("test_double") is not False
        or native_backend_receipt.get("implicit_fallback_allowed") is not False
        or native_backend_receipt.get("receipt_sha256")
        != _sha256_json(
            {
                key: value
                for key, value in native_backend_receipt.items()
                if key != "receipt_sha256"
            }
        )
    ):
        raise CohortRunnerError(
            "native_backend_receipt_invalid", "facade backend receipt is not sealed"
        )

    protocol_cases: list[dict[str, object]] = []
    evaluation_receipts: dict[str, dict[str, object]] = {}
    for prepared in cases:
        if prepared.case_id == PREPARATION_FAILURE_CASE_ID:
            protocol_cases.append(
                {
                    "case_id": prepared.case_id,
                    "source_receipt_sha256": prepared.source_receipt_sha256,
                    "generation_input_receipt_sha256": prepared.generation_input_receipt[
                        "receipt_sha256"
                    ],
                    "known_pocket_receipt_sha256": prepared.pocket.receipt_sha256,
                    "search_receipt_sha256": None,
                    "search_receipt": None,
                    "rank_receipt": None,
                    "evaluation_receipt": None,
                    "preparation_status": "failed",
                    "preparation_failure_code": PREPARATION_FAILURE_CODE,
                    "candidates": [],
                }
            )
            continue
        artifacts = artifacts_by_case[prepared.case_id]
        batch = active_evaluator.evaluate(
            candidate_sdf_payload=b"".join(row.sdf_bytes for row in artifacts),
            native_sdf=prepared.payloads["native"],
            receptor_pdb=prepared.payloads["receptor"],
            expected_count=CANDIDATE_SLOTS_PER_SCORED_CASE,
        )
        candidate_rows, evaluation_receipt = _bind_evaluation(
            case_id=prepared.case_id,
            artifacts=artifacts,
            batch=batch,
        )
        search_receipt_sha256 = search_receipts[prepared.case_id]["receipt_sha256"]
        for candidate in candidate_rows:
            candidate["candidate_search_receipt_sha256"] = search_receipt_sha256
        protocol_cases.append(
            {
                "case_id": prepared.case_id,
                "source_receipt_sha256": prepared.source_receipt_sha256,
                "generation_input_receipt_sha256": prepared.generation_input_receipt[
                    "receipt_sha256"
                ],
                "known_pocket_receipt_sha256": prepared.pocket.receipt_sha256,
                "search_receipt_sha256": search_receipt_sha256,
                "search_receipt": search_receipts[prepared.case_id],
                "rank_receipt": rank_receipts[prepared.case_id],
                "evaluation_receipt": evaluation_receipt,
                "preparation_status": "success",
                "preparation_failure_code": None,
                "candidates": candidate_rows,
            }
        )
        evaluation_receipts[prepared.case_id] = evaluation_receipt

    implementation = {
        "engine_id": "betelgeuze",
        "search_crate_id": SEARCH_CRATE_ID,
        "search_implementation_sha256": search_impl,
        "native_extension_version": NATIVE_EXTENSION_VERSION,
        "native_extension_sha256": native_extension,
        "native_backend_receipt": native_backend_receipt,
        "generation_backend": "betelgeuze_rust_native",
        "external_solver_used": False,
    }
    generation_boundary = {
        "policy_id": GENERATION_POLICY_ID,
        "known_pocket_policy_id": KNOWN_POCKET_POLICY_ID,
        "fixed_candidate_slots_per_scored_case": CANDIDATE_SLOTS_PER_SCORED_CASE,
        "allocation_sealed_before_results": True,
        "result_dependent_allocation": False,
        "external_solver_used": False,
        "full_reference_pose_used_by_search": False,
        "rmsd_used_by_search": False,
        "posebusters_used_by_search": False,
        "baseline_outcomes_used_by_search": False,
        "known_pocket_derived_from_reference_before_search": True,
        "allowed_generation_input_roles": [
            "authenticated_protein_structure",
            "authenticated_ligand_start_conformer",
            "predeclared_known_pocket",
            "public_force_field_parameters",
        ],
        "search_config_sha256": search_config,
    }
    claim_boundary = {
        "development_only": True,
        "retrospective": True,
        "product_dispatch_authorized": False,
        "product_promotion_eligible": False,
        "public_claim_eligible": False,
        "scientific_validation_claimed": False,
    }
    result: dict[str, object] = {
        "schema_id": RESULT_SCHEMA_ID,
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "roster_sha256": ROSTER_SHA256,
        "allocation": frozen_allocation_receipt(),
        "implementation": implementation,
        "generation_boundary": generation_boundary,
        "cases": protocol_cases,
        "claim_boundary": claim_boundary,
    }
    evidence = evaluate_development_result(result)
    run_projection: dict[str, object] = {
        "schema_id": RUN_SCHEMA_ID,
        "runner_environment": environment,
        "source": {
            "archive_path": str(archive_path),
            "archive_size_bytes": PUBLIC_REDOCKING_ARCHIVE_SIZE_BYTES,
            "archive_sha256": SOURCE_ARCHIVE_SHA256,
            "ordered_case_ids": list(CASE_IDS),
            "ordered_materialization_receipts": [
                {
                    "case_id": row.case_id,
                    "receipt_sha256": row.source_receipt_sha256,
                }
                for row in cases
            ],
        },
        "phase_order": [
            "verify_all_nine_materializations",
            "derive_and_seal_all_known_pockets",
            "seal_fixed_8x64_allocation",
            "run_and_seal_all_native_proposals",
            "evaluate_external_rmsd_and_posebusters_facts",
        ],
        "implementation": implementation,
        "generation_boundary": generation_boundary,
        "case_receipts": [
            {
                "case_id": row.case_id,
                "materialization_receipt": dict(row.materialization_receipt),
                "known_pocket_receipt": dict(row.pocket_receipt),
                "generation_input_receipt": dict(row.generation_input_receipt),
                "search_receipt": search_receipts.get(row.case_id),
                "rank_receipt": rank_receipts.get(row.case_id),
                "evaluation_receipt": evaluation_receipts.get(row.case_id),
            }
            for row in cases
        ],
        "result_sha256": _sha256_json(result),
        "evidence_sha256": _sha256_json(evidence),
        "candidate_artifact_count": sum(
            len(rows) for rows in artifacts_by_case.values()
        ),
        "external_solver_used_for_generation": False,
        "claim_boundary": claim_boundary,
    }
    run_receipt = _sealed(run_projection)
    return DevelopmentCohortRun(
        result=result,
        evidence=evidence,
        run_receipt=run_receipt,
        candidate_artifacts=MappingProxyType(artifacts_by_case),
    )


def _write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def persist_run(run: DevelopmentCohortRun, output_root: str | Path) -> Path:
    """Publish a complete canonical directory without overwriting prior evidence."""

    target = Path(output_root).resolve()
    if target.exists():
        raise CohortRunnerError("output_exists", f"refusing to overwrite {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent)
    )
    try:
        _write_exclusive(
            staging / "development-result.json", canonical_json_bytes(run.result)
        )
        _write_exclusive(
            staging / "development-evidence.json", canonical_json_bytes(run.evidence)
        )
        _write_exclusive(
            staging / "run-receipt.json", canonical_json_bytes(run.run_receipt)
        )
        artifacts_root = staging / "candidate-artifacts"
        artifacts_root.mkdir(mode=0o700)
        for case_id, artifacts in run.candidate_artifacts.items():
            case_root = artifacts_root / case_id
            case_root.mkdir(mode=0o700)
            for artifact in artifacts:
                stem = f"slot-{artifact.slot_index:02d}"
                _write_exclusive(case_root / f"{stem}.sdf", artifact.sdf_bytes)
                _write_exclusive(
                    case_root / f"{stem}.coordinates.f64le", artifact.coordinate_bytes
                )
        os.rename(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-archive",
        type=Path,
        required=True,
        help="exact 53,660,397-byte PoseBusters archive",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root used only for an identity/scope check",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="new exclusive directory for result, evidence, receipts, and artifacts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    expected_repo_root = Path(__file__).resolve().parents[1]
    if arguments.repo_root.resolve() != expected_repo_root:
        print(
            "docking_search_v2_development_cohort=blocked:repo_root_mismatch",
            file=sys.stderr,
        )
        return 2
    try:
        run = run_development_cohort(arguments.source_archive)
        output = persist_run(run, arguments.output_root)
    except (
        CohortRunnerError,
        PublicRedockingBenchmarkError,
        OSError,
        ValueError,
    ) as exc:
        print(f"docking_search_v2_development_cohort=blocked:{exc}", file=sys.stderr)
        return 2
    print(f"docking_search_v2_development_cohort={run.evidence['decision']}")
    print(f"output_root={output}")
    print(f"run_receipt_sha256={run.run_receipt['receipt_sha256']}")
    return 0 if run.evidence["decision"] == "pass" else 3


if __name__ == "__main__":
    raise SystemExit(main())
