"""Installable, claim-closed redocking diagnostic for prepared canonical inputs.

The command in this module deliberately starts *after* chemistry preparation.
It accepts exact Engine v2 canonical molecular JSON documents, recenters the
receptor on an explicit spherical pocket, removes the ligand input translation,
applies a fixed non-identity orientation, and executes the authenticated rigid
geometry search.  It is a usable wiring and receipt boundary, not a calibrated
docking engine or evidence of supported chemistry.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral, Real
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Mapping, Sequence

import torch

from betelgeuze_engine_v2 import DISTRIBUTION_NAME, DISTRIBUTION_VERSION
from betelgeuze_engine_v2.ai import axis_angle_matrix
from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import (
    DockingBudget,
    DockingProblemInput,
    ElementGeometryDiagnosticScoreConfig,
    ElementGeometryDiagnosticScorer,
    PocketDefinition,
    PoseValidityConfig,
    PoseValidityContext,
    build_authenticated_rigid_search_space,
    run_bounded_docking_search,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    MAX_CANONICAL_SYSTEM_JSON_BYTES,
    RDKIT_OPENFF_PREPARATION_METADATA_KEY,
    all_atom_system_from_canonical_json,
    canonical_json_bytes,
    canonical_system_sha256,
    require_valid_all_atom_system,
    sha256_canonical,
    verify_rdkit_openff_prepared_system,
)


REDOCKING_DIAGNOSTIC_SCHEMA_ID = "betelgeuze.engine_v2_prepared_redocking_diagnostic/1.0.0"
REDOCKING_DIAGNOSTIC_ALGORITHM_ID = "authenticated_prepared_input_rigid_geometry_search/1.0.0"
REDOCKING_DIAGNOSTIC_COORDINATE_FRAME_ID = "explicit_cli_pocket_centered_receptor_frame/1.0.0"
REDOCKING_DIAGNOSTIC_POCKET_POLICY_ID = "explicit_cli_spherical_pocket_center_and_radius/1.0.0"
MAX_REDOCKING_DIAGNOSTIC_REPORT_BYTES = 64 * 1024 * 1024
MAX_REDOCKING_DIAGNOSTIC_CANDIDATES = 1_024
MAX_REDOCKING_DIAGNOSTIC_LIGAND_ATOMS = 4_096
MAX_REDOCKING_DIAGNOSTIC_POCKET_RADIUS_ANGSTROM = 30.0

_FIXED_PREORIENTATION_AXIS = (1.0, 2.0, 3.0)
_FIXED_PREORIENTATION_ANGLE_RADIANS = 1.23456789

REDOCKING_DIAGNOSTIC_BLOCKERS = (
    "prepared_canonical_inputs_required",
    "rdkit_openff_preparation_not_scientifically_validated",
    "protonation_and_tautomer_selection_not_scientifically_validated",
    "rigid_body_only_torsion_sampling_missing",
    "haar_rotation_sampling_not_implemented",
    "steric_field_guided_proposals_not_implemented",
    "geometry_only_score_not_force_field_energy",
    "interpretable_pose_scorer_v0_not_implemented",
    "local_minimization_refiner_not_implemented",
    "chemistry_aware_pose_validity_v2_not_implemented",
    "chemical_symmetry_permutations_not_prepared",
    "public_redocking_benchmark_not_validated",
    "vina_gnina_smina_same_input_receipts_missing",
    "confidence_calibration_and_ood_abstention_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)
_MISSING_LIGAND_PREPARATION_BLOCKERS = (
    "rdkit_openff_preparation_receipt_missing",
    "protonation_and_tautomer_enumeration_receipt_missing",
)

_CLAIM_FLAGS = {
    "benchmark_validated": False,
    "calibrated_docking_engine": False,
    "claim_safe": False,
    "customer_execution_enabled": False,
    "scientifically_validated": False,
    "supported_chemistry_validated": False,
}


class RedockingDiagnosticError(ValueError):
    """Prepared redocking input, execution, or receipt is invalid."""


def _canonical_digest(value: object) -> str:
    return sha256_canonical(value)


def _require_digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RedockingDiagnosticError(f"{name} must be a lowercase SHA-256")
    return value


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise RedockingDiagnosticError(f"{name} must be an integer")
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise RedockingDiagnosticError(f"{name} must be at least {minimum}{upper}")
    return result


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise RedockingDiagnosticError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise RedockingDiagnosticError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise RedockingDiagnosticError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise RedockingDiagnosticError(f"{name} must be non-negative")
    return result


def _vector3(value: Sequence[float], *, name: str) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)) or len(value) != 3:
        raise RedockingDiagnosticError(f"{name} must contain three values")
    result = tuple(_finite(item, name=name) for item in value)
    return (result[0], result[1], result[2])


@dataclass(frozen=True, slots=True)
class RedockingDiagnosticConfig:
    """Bounded proposal and selection configuration for one CLI execution."""

    candidate_count: int = 64
    top_k: int = 10
    translation_radius_angstrom: float = 4.0
    diversity_rmsd_angstrom: float = 0.5
    seed: int = 7_301

    def __post_init__(self) -> None:
        candidate_count = _exact_int(
            self.candidate_count,
            name="candidate_count",
            minimum=1,
            maximum=MAX_REDOCKING_DIAGNOSTIC_CANDIDATES,
        )
        top_k = _exact_int(
            self.top_k,
            name="top_k",
            minimum=1,
            maximum=128,
        )
        if top_k > candidate_count:
            raise RedockingDiagnosticError("top_k must not exceed candidate_count")
        translation = _finite(
            self.translation_radius_angstrom,
            name="translation_radius_angstrom",
            nonnegative=True,
        )
        diversity = _finite(
            self.diversity_rmsd_angstrom,
            name="diversity_rmsd_angstrom",
            nonnegative=True,
        )
        seed = _exact_int(
            self.seed,
            name="seed",
            minimum=0,
            maximum=2**63 - 1,
        )
        # Reuse the proposal layer's own capacity and cross-field validation.
        DockingBudget(
            candidate_count=candidate_count,
            top_k=top_k,
            max_torsions=0,
            max_refinement_steps=0,
            translation_radius_angstrom=translation,
            seed=seed,
        )
        object.__setattr__(self, "candidate_count", candidate_count)
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(
            self,
            "translation_radius_angstrom",
            translation,
        )
        object.__setattr__(self, "diversity_rmsd_angstrom", diversity)
        object.__setattr__(self, "seed", seed)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "max_torsions": 0,
            "max_refinement_steps": 0,
            "translation_radius_angstrom": self.translation_radius_angstrom,
            "diversity_rmsd_angstrom": self.diversity_rmsd_angstrom,
            "diversity_metric": "symmetry_aware_direct_rmsd",
            "seed": self.seed,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_digest(self.to_dict())


def _require_prepared_system(
    system: AllAtomSystem,
    *,
    role: str,
) -> None:
    if not isinstance(system, AllAtomSystem):
        raise TypeError(f"{role} must be AllAtomSystem")
    require_valid_all_atom_system(system)
    if system.model_count != 1:
        raise RedockingDiagnosticError(f"{role} must contain exactly one coordinate model")
    if system.coordinate_unit != "angstrom":
        raise RedockingDiagnosticError(f"{role} coordinates must use angstrom")
    if system.cell is not None and any(system.cell.periodic):
        raise RedockingDiagnosticError(f"{role} must be non-periodic for this diagnostic")
    coordinates = system.coordinates
    if coordinates.device.type != "cpu":
        raise RedockingDiagnosticError(f"{role} coordinates must use CPU")


def _ligand_preparation_summary(
    ligand: AllAtomSystem,
) -> tuple[dict[str, object], tuple[str, ...]]:
    if RDKIT_OPENFF_PREPARATION_METADATA_KEY not in ligand.metadata:
        return (
            {
                "present": False,
                "verified": False,
                "schema_id": None,
                "receipt_sha256": None,
                "config_sha256": None,
                "diagnostic_redocking_ready": False,
                "openff_status": None,
                "openff_molecule_admitted": False,
                "openff_parameterization_ready": False,
            },
            _MISSING_LIGAND_PREPARATION_BLOCKERS,
        )
    receipt = verify_rdkit_openff_prepared_system(ligand)
    readiness = receipt.get("readiness")
    runtime = receipt.get("runtime")
    config = receipt.get("config")
    if not isinstance(readiness, Mapping) or not isinstance(runtime, Mapping) or not isinstance(config, Mapping):
        raise RedockingDiagnosticError("verified ligand preparation receipt is incomplete")
    openff = runtime.get("openff")
    if not isinstance(openff, Mapping):
        raise RedockingDiagnosticError("verified ligand OpenFF admission is incomplete")
    if readiness.get("diagnostic_redocking_ready") is not True:
        raise RedockingDiagnosticError("ligand preparation receipt does not admit diagnostic redocking")
    receipt_sha256 = _require_digest(
        receipt.get("receipt_sha256"),
        name="ligand_preparation_receipt_sha256",
    )
    config_sha256 = _require_digest(
        config.get("config_sha256"),
        name="ligand_preparation_config_sha256",
    )
    raw_blockers = receipt.get("scientific_blockers")
    if (
        isinstance(raw_blockers, (str, bytes))
        or not isinstance(raw_blockers, Sequence)
        or any(not isinstance(item, str) or not item for item in raw_blockers)
    ):
        raise RedockingDiagnosticError("verified ligand preparation blockers are incomplete")
    return (
        {
            "present": True,
            "verified": True,
            "schema_id": receipt["schema_id"],
            "receipt_sha256": receipt_sha256,
            "config_sha256": config_sha256,
            "diagnostic_redocking_ready": True,
            "openff_status": openff.get("status"),
            "openff_molecule_admitted": (readiness.get("openff_molecule_admitted") is True),
            "openff_parameterization_ready": False,
        },
        tuple(raw_blockers),
    )


def _fixed_preorientation(dtype: torch.dtype) -> torch.Tensor:
    axis = torch.tensor(_FIXED_PREORIENTATION_AXIS, dtype=dtype)
    angle = torch.tensor(_FIXED_PREORIENTATION_ANGLE_RADIANS, dtype=dtype)
    return axis_angle_matrix(axis.unsqueeze(0), angle.unsqueeze(0))[0]


def _hex_coordinates(coordinates: torch.Tensor) -> list[list[str]]:
    values = coordinates.detach().to(dtype=torch.float64, device="cpu").tolist()
    return [[float(row[0]).hex(), float(row[1]).hex(), float(row[2]).hex()] for row in values]


def _merge_blockers(*groups: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for group in groups for item in group if str(item)))


def _finalize_report(payload: Mapping[str, object]) -> dict[str, object]:
    report = dict(payload)
    if "receipt_sha256" in report:
        raise RedockingDiagnosticError("receipt payload must not predeclare receipt_sha256")
    report["receipt_sha256"] = _canonical_digest(report)
    return report


def _failure_report(exc: BaseException) -> dict[str, object]:
    failure = failure_receipt(
        exc,
        public_message="prepared redocking diagnostic failed",
    )
    return _finalize_report(
        {
            "schema_id": REDOCKING_DIAGNOSTIC_SCHEMA_ID,
            "algorithm_id": REDOCKING_DIAGNOSTIC_ALGORITHM_ID,
            "status": "failure",
            "distribution": {
                "name": DISTRIBUTION_NAME,
                "version": DISTRIBUTION_VERSION,
            },
            "claims": dict(_CLAIM_FLAGS),
            "scientific_blockers": list(REDOCKING_DIAGNOSTIC_BLOCKERS),
            "failure": failure.to_dict(),
        }
    )


def run_prepared_redocking_diagnostic(
    receptor: AllAtomSystem,
    ligand: AllAtomSystem,
    *,
    receptor_artifact_sha256: str,
    ligand_artifact_sha256: str,
    pocket_center_angstrom: Sequence[float],
    pocket_radius_angstrom: float,
    config: RedockingDiagnosticConfig | None = None,
) -> dict[str, object]:
    """Execute authenticated rigid redocking and return a claim-closed receipt."""

    _require_prepared_system(receptor, role="receptor")
    _require_prepared_system(ligand, role="ligand")
    (
        ligand_preparation,
        ligand_preparation_blockers,
    ) = _ligand_preparation_summary(ligand)
    if ligand.atom_count > MAX_REDOCKING_DIAGNOSTIC_LIGAND_ATOMS:
        raise RedockingDiagnosticError("ligand atom count exceeds the redocking diagnostic capacity")
    receptor_artifact_digest = _require_digest(
        receptor_artifact_sha256,
        name="receptor_artifact_sha256",
    )
    ligand_artifact_digest = _require_digest(
        ligand_artifact_sha256,
        name="ligand_artifact_sha256",
    )
    center = _vector3(
        pocket_center_angstrom,
        name="pocket_center_angstrom",
    )
    radius = _finite(
        pocket_radius_angstrom,
        name="pocket_radius_angstrom",
        positive=True,
    )
    if radius > MAX_REDOCKING_DIAGNOSTIC_POCKET_RADIUS_ANGSTROM:
        raise RedockingDiagnosticError("pocket_radius_angstrom exceeds the diagnostic capacity")
    active = RedockingDiagnosticConfig() if config is None else config
    if not isinstance(active, RedockingDiagnosticConfig):
        raise TypeError("config must be RedockingDiagnosticConfig")
    if active.translation_radius_angstrom > radius:
        raise RedockingDiagnosticError("translation radius must not exceed the pocket radius")

    receptor_input_sha256 = canonical_system_sha256(receptor)
    ligand_input_sha256 = canonical_system_sha256(ligand)
    center_tensor = torch.tensor(center, dtype=torch.float64)
    receptor_coordinates = receptor.coordinates[0].detach().to(dtype=torch.float64, device="cpu") - center_tensor
    ligand_coordinates = (
        ligand.coordinates[0]
        .detach()
        .to(
            dtype=torch.float64,
            device="cpu",
        )
    )
    heavy_atom_indices = tuple(atom.index for atom in ligand.atoms if atom.atomic_number != 1)
    if not heavy_atom_indices:
        heavy_atom_indices = tuple(range(ligand.atom_count))
    heavy_index_tensor = torch.tensor(heavy_atom_indices, dtype=torch.long)
    ligand_center = ligand_coordinates.index_select(
        0,
        heavy_index_tensor,
    ).mean(dim=0)
    preorientation = _fixed_preorientation(torch.float64)
    prepared_ligand_coordinates = (ligand_coordinates - ligand_center) @ preorientation.T

    preparation_payload = {
        "schema_id": ("betelgeuze.engine_v2_redocking_cli_coordinate_preparation/1.0.0"),
        "receptor_input_system_sha256": receptor_input_sha256,
        "ligand_input_system_sha256": ligand_input_sha256,
        "receptor_artifact_sha256": receptor_artifact_digest,
        "ligand_artifact_sha256": ligand_artifact_digest,
        "pocket_center_angstrom": list(center),
        "ligand_centering_atom_indices": list(heavy_atom_indices),
        "ligand_input_center_angstrom": [float(value) for value in ligand_center.tolist()],
        "fixed_preorientation_axis": list(_FIXED_PREORIENTATION_AXIS),
        "fixed_preorientation_angle_radians": (_FIXED_PREORIENTATION_ANGLE_RADIANS),
        "fixed_preorientation_matrix": [[float(value) for value in row] for row in preorientation.tolist()],
        "coordinate_dtype": "float64",
        "chemistry_preparation_performed": False,
    }
    preparation_receipt_sha256 = _canonical_digest(preparation_payload)
    receptor_prepared = receptor.with_coordinates(
        receptor_coordinates.unsqueeze(0),
        operation="redocking_cli_explicit_pocket_center_shift",
        operation_evidence_sha256=preparation_receipt_sha256,
    )
    ligand_prepared = ligand.with_coordinates(
        prepared_ligand_coordinates.unsqueeze(0),
        operation="redocking_cli_heavy_center_fixed_preorientation",
        operation_evidence_sha256=preparation_receipt_sha256,
    )

    pocket_source_receipt_sha256 = _canonical_digest(
        {
            "schema_id": ("betelgeuze.engine_v2_redocking_cli_explicit_pocket/1.0.0"),
            "receptor_input_system_sha256": receptor_input_sha256,
            "receptor_prepared_system_sha256": canonical_system_sha256(receptor_prepared),
            "center_angstrom": list(center),
            "radius_angstrom": radius,
            "coordinate_frame_id": REDOCKING_DIAGNOSTIC_COORDINATE_FRAME_ID,
            "derivation_policy_id": (REDOCKING_DIAGNOSTIC_POCKET_POLICY_ID),
        }
    )
    pocket = PocketDefinition(
        receptor_system_sha256=canonical_system_sha256(receptor_prepared),
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=radius,
        coordinate_frame_id=REDOCKING_DIAGNOSTIC_COORDINATE_FRAME_ID,
        derivation_policy_id=REDOCKING_DIAGNOSTIC_POCKET_POLICY_ID,
        source_receipt_sha256=pocket_source_receipt_sha256,
        metadata={
            "input_coordinate_frame": "canonical_receptor_input_frame",
            "input_pocket_center_angstrom": list(center),
            "input_pocket_radius_angstrom": radius,
            "native_reference_used": False,
        },
    )
    search_space, search_space_derivation = build_authenticated_rigid_search_space(
        ligand_prepared,
        source_receipt_sha256=preparation_receipt_sha256,
    )
    problem = DockingProblemInput(
        receptor=receptor_prepared,
        ligand=ligand_prepared,
        pocket=pocket,
        search_space=search_space,
        search_space_derivation=search_space_derivation,
        source_artifact_sha256_by_role={
            "ligand_canonical_json": ligand_artifact_digest,
            "receptor_canonical_json": receptor_artifact_digest,
        },
    )

    geometry_config = ElementGeometryDiagnosticScoreConfig(
        pocket_radius_angstrom=radius,
        receptor_shell_radius_angstrom=max(18.0, radius + 8.0),
    )
    scorer = ElementGeometryDiagnosticScorer(
        receptor_coordinates,
        tuple(atom.atomic_number for atom in receptor.atoms),
        tuple(atom.atomic_number for atom in ligand.atoms),
        problem.identity,
        config=geometry_config,
    )
    validity_defaults = PoseValidityConfig()
    validity_radius = radius + validity_defaults.receptor_ligand_clash_angstrom
    validity_mask = torch.linalg.vector_norm(receptor_coordinates, dim=1) <= validity_radius
    validity_receptor = receptor_coordinates[validity_mask]
    if int(validity_receptor.shape[0]) < 1:
        raise RedockingDiagnosticError("no receptor atoms fall within the bounded validity shell")
    bond_pairs = tuple((bond.atom_i, bond.atom_j) for bond in ligand.bonds)
    validity_context = PoseValidityContext(
        problem_fingerprint_sha256=problem.identity.fingerprint_sha256,
        reference_coordinates=prepared_ligand_coordinates,
        bond_pairs=bond_pairs,
        excluded_nonbonded_pairs=bond_pairs,
        receptor_coordinates=validity_receptor,
        pocket_center=torch.zeros(3, dtype=torch.float64),
        chirality_centers=(),
        config=PoseValidityConfig(pocket_radius_angstrom=radius),
    )
    budget = DockingBudget(
        candidate_count=active.candidate_count,
        top_k=active.top_k,
        max_torsions=0,
        max_refinement_steps=0,
        translation_radius_angstrom=active.translation_radius_angstrom,
        seed=active.seed,
    )
    search = run_bounded_docking_search(
        search_space,
        budget,
        scorer,
        validity_context=validity_context,
        diversity_rmsd_angstrom=active.diversity_rmsd_angstrom,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=(tuple(range(ligand.atom_count)),),
        problem=problem,
    )

    top_poses: list[dict[str, object]] = []
    for rank, row in enumerate(search.top_rows, start=1):
        if row.proposal is None or row.score is None:
            raise RedockingDiagnosticError("selected redocking row is missing its proposal or score")
        receptor_frame_coordinates = row.proposal.coordinates + center_tensor
        pose_system = ligand.with_coordinates(
            receptor_frame_coordinates.unsqueeze(0),
            operation="redocking_cli_selected_pose_in_receptor_frame",
            operation_evidence_sha256=row.proposal.fingerprint_sha256,
        )
        top_poses.append(
            {
                "rank": rank,
                "candidate_id": row.candidate_id,
                "score": float(row.score),
                "score_breakdown": (None if row.score_breakdown is None else row.score_breakdown.to_dict()),
                "pose_validity": (None if row.pose_validity is None else row.pose_validity.to_dict()),
                "proposal_fingerprint_sha256": (row.proposal.fingerprint_sha256),
                "pose_system_sha256": canonical_system_sha256(pose_system),
                "coordinate_frame_id": "canonical_receptor_input_frame",
                "coordinates_angstrom_hex": _hex_coordinates(receptor_frame_coordinates),
            }
        )

    scientific_blockers = _merge_blockers(
        REDOCKING_DIAGNOSTIC_BLOCKERS,
        ligand_preparation_blockers,
        scorer.blockers,
        search.blockers,
    )
    report = _finalize_report(
        {
            "schema_id": REDOCKING_DIAGNOSTIC_SCHEMA_ID,
            "algorithm_id": REDOCKING_DIAGNOSTIC_ALGORITHM_ID,
            "status": "diagnostic_complete",
            "distribution": {
                "name": DISTRIBUTION_NAME,
                "version": DISTRIBUTION_VERSION,
                "python_version": (f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
                "torch_version": str(torch.__version__),
            },
            "input_contract": {
                "receptor_format": ("exact_engine_v2_canonical_system_json"),
                "ligand_format": (
                    "exact_engine_v2_canonical_system_json_with_rdkit_openff_preparation_receipt"
                    if ligand_preparation["verified"]
                    else "exact_engine_v2_canonical_system_json"
                ),
                "single_model_required": True,
                "nonperiodic_required": True,
                "coordinate_unit": "angstrom",
                "chemistry_preparation_performed": bool(ligand_preparation["verified"]),
                "rdkit_openff_preparation_receipt_verified": bool(ligand_preparation["verified"]),
                "arbitrary_pdb_or_sdf_accepted": False,
            },
            "source_artifacts": {
                "receptor_canonical_json_sha256": (receptor_artifact_digest),
                "ligand_canonical_json_sha256": ligand_artifact_digest,
                "receptor_input_system_sha256": receptor_input_sha256,
                "ligand_input_system_sha256": ligand_input_sha256,
                "ligand_preparation_receipt_sha256": (ligand_preparation["receipt_sha256"]),
            },
            "ligand_preparation": ligand_preparation,
            "coordinate_preparation": {
                **preparation_payload,
                "receipt_sha256": preparation_receipt_sha256,
                "receptor_prepared_system_sha256": (canonical_system_sha256(receptor_prepared)),
                "ligand_prepared_system_sha256": (canonical_system_sha256(ligand_prepared)),
            },
            "config": {
                **active.to_dict(),
                "config_sha256": active.fingerprint_sha256,
                "pocket_center_angstrom": list(center),
                "pocket_radius_angstrom": radius,
                "geometry_score": geometry_config.to_dict(),
            },
            "authenticated_problem_input": problem.to_dict(),
            "search": search.to_dict(),
            "top_poses": top_poses,
            "summary": {
                "candidate_count": len(search.rows),
                "success_count": search.success_count,
                "failure_count": search.failure_count,
                "selection_eligible_count": (search.selection_eligible_count),
                "valid_pose_count": search.valid_pose_count,
                "top_pose_count": len(top_poses),
                "all_candidate_rows_retained": (len(search.rows) == active.candidate_count),
                "diagnostic_execution_enabled": True,
            },
            "claims": dict(_CLAIM_FLAGS),
            "scientific_blockers": list(scientific_blockers),
        }
    )
    verify_redocking_diagnostic_report(canonical_json_bytes(report))
    return report


def verify_redocking_diagnostic_report(
    source: str | bytes,
) -> dict[str, object]:
    """Strictly parse and verify one success or failure receipt."""

    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise TypeError("redocking receipt source must be str or bytes")
    if len(raw) > MAX_REDOCKING_DIAGNOSTIC_REPORT_BYTES:
        raise RedockingDiagnosticError("redocking diagnostic receipt exceeds the byte limit")

    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise RedockingDiagnosticError(f"duplicate JSON object key {key!r}")
            result[key] = value
        return result

    def reject_nonfinite_constant(value: str) -> None:
        raise RedockingDiagnosticError(f"non-standard JSON numeric constant {value!r}")

    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_constant,
        )
    except RedockingDiagnosticError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RedockingDiagnosticError("redocking diagnostic receipt must be UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise RedockingDiagnosticError("redocking diagnostic receipt must be an object")
    if raw != canonical_json_bytes(document):
        raise RedockingDiagnosticError("redocking diagnostic receipt is not exact canonical JSON")
    if document.get("schema_id") != REDOCKING_DIAGNOSTIC_SCHEMA_ID:
        raise RedockingDiagnosticError("unsupported redocking diagnostic receipt schema")
    if document.get("algorithm_id") != REDOCKING_DIAGNOSTIC_ALGORITHM_ID:
        raise RedockingDiagnosticError("unsupported redocking diagnostic algorithm")
    status = document.get("status")
    if status not in {"diagnostic_complete", "failure"}:
        raise RedockingDiagnosticError("invalid redocking diagnostic receipt status")
    expected_fields = (
        {
            "schema_id",
            "algorithm_id",
            "status",
            "distribution",
            "claims",
            "scientific_blockers",
            "failure",
            "receipt_sha256",
        }
        if status == "failure"
        else {
            "schema_id",
            "algorithm_id",
            "status",
            "distribution",
            "input_contract",
            "source_artifacts",
            "ligand_preparation",
            "coordinate_preparation",
            "config",
            "authenticated_problem_input",
            "search",
            "top_poses",
            "summary",
            "claims",
            "scientific_blockers",
            "receipt_sha256",
        }
    )
    if set(document) != expected_fields:
        raise RedockingDiagnosticError("redocking diagnostic receipt fields are not canonical")
    if document.get("claims") != _CLAIM_FLAGS:
        raise RedockingDiagnosticError("redocking diagnostic claim flags cannot be promoted")
    blockers = document.get("scientific_blockers")
    if not isinstance(blockers, list) or not set(REDOCKING_DIAGNOSTIC_BLOCKERS).issubset(blockers):
        raise RedockingDiagnosticError("redocking diagnostic scientific blockers are incomplete")
    receipt_sha256 = _require_digest(
        document.get("receipt_sha256"),
        name="receipt_sha256",
    )
    unsigned = dict(document)
    unsigned.pop("receipt_sha256")
    if receipt_sha256 != _canonical_digest(unsigned):
        raise RedockingDiagnosticError("redocking diagnostic receipt SHA-256 mismatch")
    if status == "diagnostic_complete":
        summary = document.get("summary")
        search = document.get("search")
        top_poses = document.get("top_poses")
        problem = document.get("authenticated_problem_input")
        input_contract = document.get("input_contract")
        source_artifacts = document.get("source_artifacts")
        ligand_preparation = document.get("ligand_preparation")
        if (
            not isinstance(summary, dict)
            or not isinstance(search, dict)
            or not isinstance(top_poses, list)
            or not isinstance(problem, dict)
            or not isinstance(input_contract, dict)
            or not isinstance(source_artifacts, dict)
            or not isinstance(ligand_preparation, dict)
            or summary.get("candidate_count") != search.get("candidate_count")
            or summary.get("top_pose_count") != len(top_poses)
            or summary.get("all_candidate_rows_retained") is not True
            or search.get("claim_safe") is not False
            or problem.get("authenticated_to_concrete_molecular_state") is not True
            or input_contract.get("arbitrary_pdb_or_sdf_accepted") is not False
        ):
            raise RedockingDiagnosticError("redocking diagnostic success summary is inconsistent")
        chemistry_preparation_performed = input_contract.get("chemistry_preparation_performed")
        preparation_verified = input_contract.get("rdkit_openff_preparation_receipt_verified")
        if (
            not isinstance(chemistry_preparation_performed, bool)
            or preparation_verified is not chemistry_preparation_performed
            or ligand_preparation.get("present") is not chemistry_preparation_performed
            or ligand_preparation.get("verified") is not chemistry_preparation_performed
            or ligand_preparation.get("diagnostic_redocking_ready") is not chemistry_preparation_performed
            or ligand_preparation.get("openff_parameterization_ready") is not False
        ):
            raise RedockingDiagnosticError("redocking ligand preparation binding is inconsistent")
        preparation_digest = source_artifacts.get("ligand_preparation_receipt_sha256")
        if chemistry_preparation_performed:
            verified_digest = _require_digest(
                ligand_preparation.get("receipt_sha256"),
                name="ligand_preparation_receipt_sha256",
            )
            _require_digest(
                ligand_preparation.get("config_sha256"),
                name="ligand_preparation_config_sha256",
            )
            if (
                preparation_digest != verified_digest
                or not isinstance(ligand_preparation.get("schema_id"), str)
                or not ligand_preparation.get("schema_id")
                or any(blocker in blockers for blocker in _MISSING_LIGAND_PREPARATION_BLOCKERS)
            ):
                raise RedockingDiagnosticError("redocking verified ligand preparation is inconsistent")
        elif (
            preparation_digest is not None
            or ligand_preparation.get("receipt_sha256") is not None
            or ligand_preparation.get("config_sha256") is not None
            or ligand_preparation.get("schema_id") is not None
            or not set(_MISSING_LIGAND_PREPARATION_BLOCKERS).issubset(blockers)
        ):
            raise RedockingDiagnosticError("redocking missing ligand preparation is inconsistent")
        rows = search.get("rows")
        top_candidate_ids = search.get("top_candidate_ids")
        if (
            not isinstance(rows, list)
            or len(rows) != search.get("candidate_count")
            or not isinstance(top_candidate_ids, list)
            or top_candidate_ids != [pose.get("candidate_id") for pose in top_poses if isinstance(pose, dict)]
        ):
            raise RedockingDiagnosticError("redocking diagnostic candidate rows are incomplete")
        for name in (
            "receptor_canonical_json_sha256",
            "ligand_canonical_json_sha256",
            "receptor_input_system_sha256",
            "ligand_input_system_sha256",
        ):
            _require_digest(source_artifacts.get(name), name=name)
        derivation = problem.get("search_space_derivation")
        atom_count = derivation.get("atom_count") if isinstance(derivation, dict) else None
        if isinstance(atom_count, bool) or not isinstance(atom_count, int) or atom_count < 1:
            raise RedockingDiagnosticError("redocking diagnostic ligand atom count is invalid")
        for pose in top_poses:
            if not isinstance(pose, dict):
                raise RedockingDiagnosticError("redocking diagnostic top pose is invalid")
            coordinates = pose.get("coordinates_angstrom_hex")
            if not isinstance(coordinates, list) or len(coordinates) != atom_count:
                raise RedockingDiagnosticError("redocking diagnostic top-pose atom count is inconsistent")
            for row in coordinates:
                if not isinstance(row, list) or len(row) != 3:
                    raise RedockingDiagnosticError("redocking diagnostic top-pose coordinates are invalid")
                for token in row:
                    if not isinstance(token, str):
                        raise RedockingDiagnosticError("redocking diagnostic coordinate token is invalid")
                    try:
                        number = float.fromhex(token)
                    except ValueError as exc:
                        raise RedockingDiagnosticError("redocking diagnostic coordinate token is invalid") from exc
                    if not math.isfinite(number) or token != number.hex():
                        raise RedockingDiagnosticError("redocking diagnostic coordinate token is not canonical")
    else:
        failure = document.get("failure")
        if (
            not isinstance(failure, dict)
            or set(failure)
            != {
                "public_error_code",
                "public_message",
                "private_error_sha256",
                "private_error_byte_length",
            }
            or not isinstance(failure.get("public_error_code"), str)
            or not failure.get("public_error_code")
            or failure.get("public_message") != "prepared redocking diagnostic failed"
            or isinstance(failure.get("private_error_byte_length"), bool)
            or not isinstance(failure.get("private_error_byte_length"), int)
            or failure.get("private_error_byte_length", -1) < 0
        ):
            raise RedockingDiagnosticError("redocking diagnostic failure receipt is incomplete")
        _require_digest(
            failure.get("private_error_sha256"),
            name="private_error_sha256",
        )
    return document


def _read_regular_file(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
) -> bytes:
    source = Path(path)
    try:
        path_before = os.lstat(source)
    except OSError as exc:
        raise RedockingDiagnosticError("redocking input could not be opened as a regular file") from exc
    if stat.S_ISLNK(path_before.st_mode) or not stat.S_ISREG(path_before.st_mode):
        raise RedockingDiagnosticError("redocking input must be a non-symlink regular file")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise RedockingDiagnosticError("redocking input could not be opened as a regular file") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RedockingDiagnosticError("redocking input must be a regular file")
        if before.st_dev != path_before.st_dev or before.st_ino != path_before.st_ino:
            raise RedockingDiagnosticError("redocking input path changed before it was opened")
        if before.st_size < 0 or before.st_size > maximum_bytes:
            raise RedockingDiagnosticError("redocking input exceeds the byte limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, maximum_bytes + 1 - total),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise RedockingDiagnosticError("redocking input exceeds the byte limit")
        after = os.fstat(descriptor)
        try:
            path_after = os.lstat(source)
        except OSError as exc:
            raise RedockingDiagnosticError("redocking input path changed while it was being read") from exc
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        path_after_identity = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_size,
            path_after.st_mtime_ns,
            path_after.st_ctime_ns,
        )
        if (
            stat.S_ISLNK(path_after.st_mode)
            or before_identity != after_identity
            or before_identity != path_after_identity
            or total != before.st_size
        ):
            raise RedockingDiagnosticError("redocking input changed while it was being read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def write_redocking_diagnostic_report(
    report: Mapping[str, object],
    output_path: str | os.PathLike[str],
) -> Path:
    """Write one mode-0600 canonical receipt without replacing any path."""

    raw = canonical_json_bytes(dict(report))
    verify_redocking_diagnostic_report(raw)
    if len(raw) > MAX_REDOCKING_DIAGNOSTIC_REPORT_BYTES:
        raise RedockingDiagnosticError("redocking diagnostic receipt exceeds the byte limit")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise RedockingDiagnosticError("redocking diagnostic output already exists") from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a claim-closed rigid redocking diagnostic from exact prepared "
            "Engine v2 canonical molecular JSON inputs."
        ),
    )
    parser.add_argument(
        "--receptor-canonical-json",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--ligand-canonical-json",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--pocket-center",
        required=True,
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
    )
    parser.add_argument(
        "--pocket-radius",
        required=True,
        type=float,
    )
    parser.add_argument(
        "--candidate-count",
        type=int,
        default=64,
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--translation-radius",
        type=float,
        default=4.0,
    )
    parser.add_argument(
        "--diversity-rmsd",
        type=float,
        default=0.5,
    )
    parser.add_argument("--seed", type=int, default=7_301)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receptor_source = _read_regular_file(
            args.receptor_canonical_json,
            maximum_bytes=MAX_CANONICAL_SYSTEM_JSON_BYTES,
        )
        ligand_source = _read_regular_file(
            args.ligand_canonical_json,
            maximum_bytes=MAX_CANONICAL_SYSTEM_JSON_BYTES,
        )
        receptor = all_atom_system_from_canonical_json(
            receptor_source,
            device="cpu",
        )
        ligand = all_atom_system_from_canonical_json(
            ligand_source,
            device="cpu",
        )
        report = run_prepared_redocking_diagnostic(
            receptor,
            ligand,
            receptor_artifact_sha256=hashlib.sha256(receptor_source).hexdigest(),
            ligand_artifact_sha256=hashlib.sha256(ligand_source).hexdigest(),
            pocket_center_angstrom=args.pocket_center,
            pocket_radius_angstrom=args.pocket_radius,
            config=RedockingDiagnosticConfig(
                candidate_count=args.candidate_count,
                top_k=args.top_k,
                translation_radius_angstrom=args.translation_radius,
                diversity_rmsd_angstrom=args.diversity_rmsd,
                seed=args.seed,
            ),
        )
        output = write_redocking_diagnostic_report(report, args.output)
    except Exception as exc:
        failure = _failure_report(exc)
        try:
            output = write_redocking_diagnostic_report(
                failure,
                args.output,
            )
        except Exception:
            output = None
        receipt = failure["failure"]
        assert isinstance(receipt, dict)
        print(
            "prepared redocking diagnostic failed "
            f"({receipt['public_error_code']}); "
            + ("a failure receipt was written" if output is not None else "no output path was replaced"),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "receipt_sha256": report["receipt_sha256"],
                "status": report["status"],
            },
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_REDOCKING_DIAGNOSTIC_CANDIDATES",
    "MAX_REDOCKING_DIAGNOSTIC_LIGAND_ATOMS",
    "MAX_REDOCKING_DIAGNOSTIC_POCKET_RADIUS_ANGSTROM",
    "MAX_REDOCKING_DIAGNOSTIC_REPORT_BYTES",
    "REDOCKING_DIAGNOSTIC_ALGORITHM_ID",
    "REDOCKING_DIAGNOSTIC_BLOCKERS",
    "REDOCKING_DIAGNOSTIC_SCHEMA_ID",
    "RedockingDiagnosticConfig",
    "RedockingDiagnosticError",
    "main",
    "run_prepared_redocking_diagnostic",
    "verify_redocking_diagnostic_report",
    "write_redocking_diagnostic_report",
]
