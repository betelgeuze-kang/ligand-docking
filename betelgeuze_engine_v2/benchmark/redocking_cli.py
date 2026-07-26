"""Installable, claim-closed redocking diagnostic for prepared canonical inputs.

The command in this module deliberately starts *after* chemistry preparation.
It accepts exact Engine v2 canonical molecular JSON documents, recenters the
receptor on an explicit spherical pocket, removes the ligand input translation,
applies a fixed non-identity orientation, and executes authenticated proposal
search.  A verified ligand-preparation receipt enables bridge-only global
torsion sampling with Haar-uniform rotations, receptor-steric-field-guided
translation placement, the
interpretable pose scorer v0, chemistry validity v2, and bounded rigid-plus-
torsion local refinement; otherwise the command retains the geometry-only
diagnostic without refinement.  This is a usable wiring and receipt boundary,
not a calibrated docking engine or evidence of supported chemistry.
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
from typing import Mapping, Sequence, cast

import torch

from betelgeuze_engine_v2 import DISTRIBUTION_NAME, DISTRIBUTION_VERSION
from betelgeuze_engine_v2.ai import axis_angle_matrix
from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import (
    CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256,
    CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID,
    DOCKING_NUMERIC_POLICY_SCHEMA_ID,
    DOCKING_PROPOSAL_SAMPLING_STATE_SCHEMA_ID,
    DOCKING_SAMPLING_POLICY_ID,
    DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID,
    DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID,
    DOCKING_TRANSLATION_PLACEMENT_RECEIPT_SCHEMA_ID,
    DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID,
    GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
    MOLECULAR_TORSION_SEARCH_RECEIPT_SCHEMA_ID,
    RIGID_SEARCH_SPACE_DERIVATION_POLICY_ID,
    STERIC_FIELD_PLACEMENT_PLAN_SCHEMA_ID,
    ChemistryAwarePoseValidityV2Config,
    ChemistryAwarePoseValidityV2Context,
    DockingBudget,
    DockingNumericPolicy,
    DockingProblemInput,
    ElementGeometryDiagnosticScoreConfig,
    ElementGeometryDiagnosticScorer,
    INTERPRETABLE_LOCAL_REFINEMENT_V0_RECEIPT_SCHEMA_ID,
    InterpretableLocalPoseRefinerV0,
    InterpretableLocalRefinementConfig,
    InterpretablePoseScoreConfig,
    InterpretablePoseScorerV0,
    MolecularTorsionSearchConfig,
    MolecularTorsionSearchReceipt,
    PocketDefinition,
    PoseValidityConfig,
    PoseValidityContext,
    StericFieldPlacementConfig,
    StericFieldPlacementPlan,
    bind_molecular_torsion_search_space,
    build_authenticated_rigid_search_space,
    build_molecular_torsion_search_space,
    build_steric_field_placement_plan,
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


REDOCKING_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_prepared_redocking_diagnostic/1.5.0"
)
REDOCKING_DIAGNOSTIC_ALGORITHM_ID = (
    "authenticated_prepared_input_conditional_pose_search/1.5.0"
)
REDOCKING_DIAGNOSTIC_COORDINATE_FRAME_ID = (
    "explicit_cli_pocket_centered_receptor_frame/1.0.0"
)
REDOCKING_DIAGNOSTIC_POCKET_POLICY_ID = (
    "explicit_cli_spherical_pocket_center_and_radius/1.0.0"
)
MAX_REDOCKING_DIAGNOSTIC_REPORT_BYTES = 64 * 1024 * 1024
MAX_REDOCKING_DIAGNOSTIC_CANDIDATES = 1_024
MAX_REDOCKING_DIAGNOSTIC_LIGAND_ATOMS = 4_096
MAX_REDOCKING_DIAGNOSTIC_TORSIONS = 64
MAX_REDOCKING_DIAGNOSTIC_POCKET_RADIUS_ANGSTROM = 30.0
MAX_REDOCKING_DIAGNOSTIC_REFINEMENT_MOVE_EVALUATIONS = 250_000

_FIXED_PREORIENTATION_AXIS = (1.0, 2.0, 3.0)
_FIXED_PREORIENTATION_ANGLE_RADIANS = 1.23456789

REDOCKING_DIAGNOSTIC_BLOCKERS = (
    "prepared_canonical_inputs_required",
    "rdkit_openff_preparation_not_scientifically_validated",
    "protonation_and_tautomer_selection_not_scientifically_validated",
    "receptor_chemistry_preparation_receipt_missing",
    "pose_generation_not_scientifically_validated",
    "haar_rotation_sampling_not_statistically_validated",
    "steric_field_guidance_not_scientifically_validated",
    "pose_score_not_force_field_energy",
    "interpretable_pose_scorer_v0_not_calibrated_or_validated",
    "validated_force_field_pose_minimizer_missing",
    "chemistry_aware_pose_validity_v2_not_calibrated_or_validated",
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
_MISSING_INTERPRETABLE_SCORER_BLOCKERS = (
    "interpretable_pose_scorer_v0_requires_verified_ligand_preparation",
)
_MISSING_CHEMISTRY_VALIDITY_V2_BLOCKERS = (
    "chemistry_aware_pose_validity_v2_requires_verified_ligand_preparation",
)
_MISSING_INTERPRETABLE_REFINER_BLOCKERS = (
    "interpretable_local_refiner_v0_requires_verified_ligand_preparation",
)
_MISSING_GLOBAL_TORSION_BLOCKERS = (
    "global_torsion_pose_generation_requires_verified_preparation_and_positive_budget",
)
_MISSING_STERIC_FIELD_BLOCKERS = (
    "steric_field_guided_proposals_require_verified_preparation",
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


def _decode_embedded_plain_json_value(
    value: object,
    *,
    name: str,
) -> object:
    """Decode canonical float tags before verifying plain-JSON subreceipts."""

    if isinstance(value, list):
        return [
            _decode_embedded_plain_json_value(item, name=name) for item in value
        ]
    if not isinstance(value, dict):
        return value
    if "$float_hex" in value:
        if set(value) != {"$float_hex"} or not isinstance(
            value["$float_hex"],
            str,
        ):
            raise RedockingDiagnosticError(
                f"{name} contains an invalid canonical float token"
            )
        token = value["$float_hex"]
        try:
            number = float.fromhex(token)
        except ValueError as exc:
            raise RedockingDiagnosticError(
                f"{name} contains an invalid canonical float token"
            ) from exc
        if not math.isfinite(number) or number.hex() != token:
            raise RedockingDiagnosticError(
                f"{name} contains a non-canonical float token"
            )
        return number
    return {
        str(key): _decode_embedded_plain_json_value(item, name=name)
        for key, item in value.items()
    }


def _embedded_plain_json_digest(value: object, *, name: str) -> str:
    decoded = _decode_embedded_plain_json_value(value, name=name)
    try:
        raw = json.dumps(
            decoded,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise RedockingDiagnosticError(
            f"{name} is not canonical plain-JSON receipt data"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


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


def _canonical_float_from_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise RedockingDiagnosticError(f"{name} must be a float-hex string")
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise RedockingDiagnosticError(f"{name} is invalid float hex") from exc
    if not math.isfinite(number) or number.hex() != value:
        raise RedockingDiagnosticError(f"{name} is not canonical finite float hex")
    return number


@dataclass(frozen=True, slots=True)
class RedockingDiagnosticConfig:
    """Bounded proposal and selection configuration for one CLI execution."""

    candidate_count: int = 64
    top_k: int = 10
    max_torsions: int = 32
    translation_radius_angstrom: float = 4.0
    diversity_rmsd_angstrom: float = 0.5
    max_refinement_steps: int = 6
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
        max_torsions = _exact_int(
            self.max_torsions,
            name="max_torsions",
            minimum=0,
            maximum=MAX_REDOCKING_DIAGNOSTIC_TORSIONS,
        )
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
        max_refinement_steps = _exact_int(
            self.max_refinement_steps,
            name="max_refinement_steps",
            minimum=0,
            maximum=32,
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
            max_torsions=max_torsions,
            max_refinement_steps=max_refinement_steps,
            translation_radius_angstrom=translation,
            seed=seed,
        )
        object.__setattr__(self, "candidate_count", candidate_count)
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(self, "max_torsions", max_torsions)
        object.__setattr__(
            self,
            "translation_radius_angstrom",
            translation,
        )
        object.__setattr__(self, "diversity_rmsd_angstrom", diversity)
        object.__setattr__(
            self,
            "max_refinement_steps",
            max_refinement_steps,
        )
        object.__setattr__(self, "seed", seed)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "max_torsions": self.max_torsions,
            "max_refinement_steps": self.max_refinement_steps,
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
        raise RedockingDiagnosticError(
            f"{role} must contain exactly one coordinate model"
        )
    if system.coordinate_unit != "angstrom":
        raise RedockingDiagnosticError(f"{role} coordinates must use angstrom")
    if system.cell is not None and any(system.cell.periodic):
        raise RedockingDiagnosticError(
            f"{role} must be non-periodic for this diagnostic"
        )
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
    if (
        not isinstance(readiness, Mapping)
        or not isinstance(runtime, Mapping)
        or not isinstance(config, Mapping)
    ):
        raise RedockingDiagnosticError(
            "verified ligand preparation receipt is incomplete"
        )
    openff = runtime.get("openff")
    if not isinstance(openff, Mapping):
        raise RedockingDiagnosticError("verified ligand OpenFF admission is incomplete")
    if readiness.get("diagnostic_redocking_ready") is not True:
        raise RedockingDiagnosticError(
            "ligand preparation receipt does not admit diagnostic redocking"
        )
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
        raise RedockingDiagnosticError(
            "verified ligand preparation blockers are incomplete"
        )
    return (
        {
            "present": True,
            "verified": True,
            "schema_id": receipt["schema_id"],
            "receipt_sha256": receipt_sha256,
            "config_sha256": config_sha256,
            "diagnostic_redocking_ready": True,
            "openff_status": openff.get("status"),
            "openff_molecule_admitted": (
                readiness.get("openff_molecule_admitted") is True
            ),
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
    return [
        [float(row[0]).hex(), float(row[1]).hex(), float(row[2]).hex()]
        for row in values
    ]


def _merge_blockers(*groups: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(item) for group in groups for item in group if str(item))
    )


def _finalize_report(payload: Mapping[str, object]) -> dict[str, object]:
    report = dict(payload)
    if "receipt_sha256" in report:
        raise RedockingDiagnosticError(
            "receipt payload must not predeclare receipt_sha256"
        )
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
    """Execute authenticated prepared redocking and return a claim-closed receipt."""

    _require_prepared_system(receptor, role="receptor")
    _require_prepared_system(ligand, role="ligand")
    (
        ligand_preparation,
        ligand_preparation_blockers,
    ) = _ligand_preparation_summary(ligand)
    if ligand.atom_count > MAX_REDOCKING_DIAGNOSTIC_LIGAND_ATOMS:
        raise RedockingDiagnosticError(
            "ligand atom count exceeds the redocking diagnostic capacity"
        )
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
        raise RedockingDiagnosticError(
            "pocket_radius_angstrom exceeds the diagnostic capacity"
        )
    active = RedockingDiagnosticConfig() if config is None else config
    if not isinstance(active, RedockingDiagnosticConfig):
        raise TypeError("config must be RedockingDiagnosticConfig")
    preparation_verified = ligand_preparation["verified"] is True
    if active.translation_radius_angstrom > radius:
        raise RedockingDiagnosticError(
            "translation radius must not exceed the pocket radius"
        )

    receptor_input_sha256 = canonical_system_sha256(receptor)
    ligand_input_sha256 = canonical_system_sha256(ligand)
    center_tensor = torch.tensor(center, dtype=torch.float64)
    receptor_coordinates = (
        receptor.coordinates[0].detach().to(dtype=torch.float64, device="cpu")
        - center_tensor
    )
    ligand_coordinates = (
        ligand.coordinates[0]
        .detach()
        .to(
            dtype=torch.float64,
            device="cpu",
        )
    )
    heavy_atom_indices = tuple(
        atom.index for atom in ligand.atoms if atom.atomic_number != 1
    )
    if not heavy_atom_indices:
        heavy_atom_indices = tuple(range(ligand.atom_count))
    heavy_index_tensor = torch.tensor(heavy_atom_indices, dtype=torch.long)
    ligand_center = ligand_coordinates.index_select(
        0,
        heavy_index_tensor,
    ).mean(dim=0)
    preorientation = _fixed_preorientation(torch.float64)
    prepared_ligand_coordinates = (
        ligand_coordinates - ligand_center
    ) @ preorientation.T

    preparation_payload = {
        "schema_id": (
            "betelgeuze.engine_v2_redocking_cli_coordinate_preparation/1.0.0"
        ),
        "receptor_input_system_sha256": receptor_input_sha256,
        "ligand_input_system_sha256": ligand_input_sha256,
        "receptor_artifact_sha256": receptor_artifact_digest,
        "ligand_artifact_sha256": ligand_artifact_digest,
        "pocket_center_angstrom": list(center),
        "ligand_centering_atom_indices": list(heavy_atom_indices),
        "ligand_input_center_angstrom": [
            float(value) for value in ligand_center.tolist()
        ],
        "fixed_preorientation_axis": list(_FIXED_PREORIENTATION_AXIS),
        "fixed_preorientation_angle_radians": (_FIXED_PREORIENTATION_ANGLE_RADIANS),
        "fixed_preorientation_matrix": [
            [float(value) for value in row] for row in preorientation.tolist()
        ],
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
            "receptor_prepared_system_sha256": canonical_system_sha256(
                receptor_prepared
            ),
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
    proposal_torsion_config: MolecularTorsionSearchConfig | None = None
    proposal_torsion_receipt: MolecularTorsionSearchReceipt | None = None
    proposal_generation_blockers: tuple[str, ...]
    effective_max_torsions = 0
    if preparation_verified and active.max_torsions > 0:
        proposal_torsion_config = MolecularTorsionSearchConfig(
            max_atoms=MAX_REDOCKING_DIAGNOSTIC_LIGAND_ATOMS,
            max_bonds=16_384,
            max_rotatable_bonds=active.max_torsions,
            reconstruction_tolerance_angstrom=1.0e-10,
        )
        search_space, proposal_torsion_receipt = (
            build_molecular_torsion_search_space(
                ligand_prepared,
                config=proposal_torsion_config,
            )
        )
        search_space_derivation = bind_molecular_torsion_search_space(
            ligand_prepared,
            search_space,
            proposal_torsion_receipt,
        )
        proposal_generation_blockers = proposal_torsion_receipt.blockers
        effective_max_torsions = active.max_torsions
    else:
        search_space, search_space_derivation = (
            build_authenticated_rigid_search_space(
                ligand_prepared,
                source_receipt_sha256=preparation_receipt_sha256,
            )
        )
        proposal_generation_blockers = _MISSING_GLOBAL_TORSION_BLOCKERS
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
    torsion_generation_blockers = proposal_generation_blockers
    steric_field_config: StericFieldPlacementConfig | None = None
    translation_placement_plan: StericFieldPlacementPlan | None = None
    if preparation_verified:
        steric_field_config = StericFieldPlacementConfig(
            translation_radius_angstrom=active.translation_radius_angstrom,
            grid_spacing_angstrom=(
                min(1.5, active.translation_radius_angstrom)
                if active.translation_radius_angstrom > 0.0
                else 1.5
            ),
        )
        translation_placement_plan = build_steric_field_placement_plan(
            problem,
            config=steric_field_config,
        )
        translation_placement_blockers = translation_placement_plan.blockers
    else:
        translation_placement_blockers = _MISSING_STERIC_FIELD_BLOCKERS
    proposal_generation_blockers = _merge_blockers(
        torsion_generation_blockers,
        translation_placement_blockers,
    )

    geometry_config = ElementGeometryDiagnosticScoreConfig(
        pocket_radius_angstrom=radius,
        receptor_shell_radius_angstrom=max(18.0, radius + 8.0),
    )
    scorer_selection_blockers: tuple[str, ...] = ()
    scorer: ElementGeometryDiagnosticScorer | InterpretablePoseScorerV0
    if preparation_verified:
        scorer = InterpretablePoseScorerV0(
            receptor_prepared,
            ligand_prepared,
            problem.identity,
            config=InterpretablePoseScoreConfig(
                base_geometry=geometry_config,
            ),
        )
    else:
        scorer = ElementGeometryDiagnosticScorer(
            receptor_coordinates,
            tuple(atom.atomic_number for atom in receptor.atoms),
            tuple(atom.atomic_number for atom in ligand.atoms),
            problem.identity,
            config=geometry_config,
        )
        scorer_selection_blockers = _MISSING_INTERPRETABLE_SCORER_BLOCKERS
    refiner_selection_blockers: tuple[str, ...] = ()
    refinement_config: InterpretableLocalRefinementConfig | None = None
    refiner: InterpretableLocalPoseRefinerV0 | None = None
    effective_refinement_steps = 0
    if preparation_verified:
        if not isinstance(scorer, InterpretablePoseScorerV0):
            raise RedockingDiagnosticError(
                "verified preparation did not select the interpretable scorer"
            )
        refinement_config = InterpretableLocalRefinementConfig(
            maximum_steps=max(1, active.max_refinement_steps),
        )
        refiner = InterpretableLocalPoseRefinerV0(
            scorer,
            config=refinement_config,
        )
        if (
            proposal_torsion_receipt is not None
            and refiner.torsion_search_space_sha256
            != search_space.fingerprint_sha256
        ):
            raise RedockingDiagnosticError(
                "proposal and refinement torsion search spaces disagree"
            )
        effective_refinement_steps = active.max_refinement_steps
    else:
        refiner_selection_blockers = _MISSING_INTERPRETABLE_REFINER_BLOCKERS
    refinement_move_count_per_step = (
        0 if refiner is None else 12 + 2 * refiner.rotatable_bond_count
    )
    estimated_refinement_move_evaluations = (
        active.candidate_count
        * effective_refinement_steps
        * refinement_move_count_per_step
    )
    if estimated_refinement_move_evaluations > (
        MAX_REDOCKING_DIAGNOSTIC_REFINEMENT_MOVE_EVALUATIONS
    ):
        raise RedockingDiagnosticError(
            "redocking local-refinement move-evaluation capacity exceeded"
        )
    validity_selection_blockers: tuple[str, ...] = ()
    validity_context: PoseValidityContext
    chemistry_validity_config: ChemistryAwarePoseValidityV2Config | None = None
    if preparation_verified:
        chemistry_validity_config = ChemistryAwarePoseValidityV2Config(
            receptor_shell_radius_angstrom=max(18.0, radius + 8.0),
        )
        validity_context = ChemistryAwarePoseValidityV2Context.from_prepared_systems(
            receptor_prepared,
            ligand_prepared,
            ligand,
            problem.identity,
            pocket_center=torch.zeros(3, dtype=torch.float64),
            pocket_radius_angstrom=radius,
            chemistry_config=chemistry_validity_config,
        )
        validity_context_blockers = validity_context.context_blockers
    else:
        validity_defaults = PoseValidityConfig()
        validity_radius = radius + validity_defaults.receptor_ligand_clash_angstrom
        validity_mask = (
            torch.linalg.vector_norm(receptor_coordinates, dim=1) <= validity_radius
        )
        validity_receptor = receptor_coordinates[validity_mask]
        if int(validity_receptor.shape[0]) < 1:
            raise RedockingDiagnosticError(
                "no receptor atoms fall within the bounded validity shell"
            )
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
        validity_context_blockers = ()
        validity_selection_blockers = _MISSING_CHEMISTRY_VALIDITY_V2_BLOCKERS
    budget = DockingBudget(
        candidate_count=active.candidate_count,
        top_k=active.top_k,
        max_torsions=effective_max_torsions,
        max_refinement_steps=effective_refinement_steps,
        translation_radius_angstrom=active.translation_radius_angstrom,
        seed=active.seed,
    )
    proposal_numeric_policy = DockingNumericPolicy(
        coordinate_dtype="float64",
        sampling_policy_id=(
            DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID
            if translation_placement_plan is not None
            else DOCKING_SAMPLING_POLICY_ID
        ),
        translation_placement_policy_id=(
            DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
            if translation_placement_plan is not None
            else DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID
        ),
        translation_placement_plan_sha256=(
            ""
            if translation_placement_plan is None
            else translation_placement_plan.fingerprint_sha256
        ),
    )
    search = run_bounded_docking_search(
        search_space,
        budget,
        scorer,
        refiner=refiner,
        validity_context=validity_context,
        diversity_rmsd_angstrom=active.diversity_rmsd_angstrom,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=(tuple(range(ligand.atom_count)),),
        problem=problem,
        translation_placement_plan=translation_placement_plan,
    )
    if search.numeric_policy_sha256 != proposal_numeric_policy.fingerprint_sha256:
        raise RedockingDiagnosticError(
            "redocking search numeric policy disagrees with proposal generation"
        )

    top_poses: list[dict[str, object]] = []
    for rank, row in enumerate(search.top_rows, start=1):
        if row.proposal is None or row.score is None:
            raise RedockingDiagnosticError(
                "selected redocking row is missing its proposal or score"
            )
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
                "score_breakdown": (
                    None
                    if row.score_breakdown is None
                    else row.score_breakdown.to_dict()
                ),
                "pose_validity": (
                    None if row.pose_validity is None else row.pose_validity.to_dict()
                ),
                "proposal_fingerprint_sha256": (row.proposal.fingerprint_sha256),
                "pose_system_sha256": canonical_system_sha256(pose_system),
                "coordinate_frame_id": "canonical_receptor_input_frame",
                "coordinates_angstrom_hex": _hex_coordinates(
                    receptor_frame_coordinates
                ),
            }
        )

    scientific_blockers = _merge_blockers(
        REDOCKING_DIAGNOSTIC_BLOCKERS,
        ligand_preparation_blockers,
        proposal_generation_blockers,
        scorer_selection_blockers,
        refiner_selection_blockers,
        validity_selection_blockers,
        validity_context_blockers,
        scorer.blockers,
        () if refiner is None else refiner.blockers,
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
                "python_version": (
                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
                ),
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
                "rdkit_openff_preparation_receipt_verified": bool(
                    ligand_preparation["verified"]
                ),
                "arbitrary_pdb_or_sdf_accepted": False,
            },
            "source_artifacts": {
                "receptor_canonical_json_sha256": (receptor_artifact_digest),
                "ligand_canonical_json_sha256": ligand_artifact_digest,
                "receptor_input_system_sha256": receptor_input_sha256,
                "ligand_input_system_sha256": ligand_input_sha256,
                "ligand_preparation_receipt_sha256": (
                    ligand_preparation["receipt_sha256"]
                ),
            },
            "ligand_preparation": ligand_preparation,
            "coordinate_preparation": {
                **preparation_payload,
                "receipt_sha256": preparation_receipt_sha256,
                "receptor_prepared_system_sha256": (
                    canonical_system_sha256(receptor_prepared)
                ),
                "ligand_prepared_system_sha256": (
                    canonical_system_sha256(ligand_prepared)
                ),
            },
            "config": {
                **active.to_dict(),
                "config_sha256": active.fingerprint_sha256,
                "pocket_center_angstrom": list(center),
                "pocket_radius_angstrom": radius,
                "geometry_score": geometry_config.to_dict(),
                "proposal_generation": {
                    "selection_policy_id": (
                        "verified_preparation_molecular_torsion_else_rigid/1.0.0"
                    ),
                    "preparation_gate_satisfied": preparation_verified,
                    "mode": (
                        "molecular_torsion_haar"
                        if proposal_torsion_receipt is not None
                        else "rigid_haar"
                    ),
                    "requested_max_torsions": active.max_torsions,
                    "effective_max_torsions": effective_max_torsions,
                    "materialized_torsion_count": search_space.torsion_count,
                    "global_torsion_sampling_enabled": (
                        proposal_torsion_receipt is not None
                    ),
                    "haar_rotation_sampling_enabled": True,
                    "steric_field_guidance_enabled": (
                        translation_placement_plan is not None
                    ),
                    "translation_placement_policy_id": (
                        proposal_numeric_policy.translation_placement_policy_id
                    ),
                    "translation_placement_plan_sha256": (
                        proposal_numeric_policy.translation_placement_plan_sha256
                    ),
                    "numeric_policy": proposal_numeric_policy.to_dict(),
                    "numeric_policy_sha256": (
                        proposal_numeric_policy.fingerprint_sha256
                    ),
                    "search_space_sha256": search_space.fingerprint_sha256,
                    "search_space_derivation_receipt_sha256": (
                        search_space_derivation.fingerprint_sha256
                    ),
                    "search_space_derivation_policy_id": (
                        search_space_derivation.derivation_policy_id
                    ),
                    "molecular_torsion_config": (
                        None
                        if proposal_torsion_config is None
                        else proposal_torsion_config.to_dict()
                    ),
                    "molecular_torsion_config_sha256": (
                        None
                        if proposal_torsion_config is None
                        else proposal_torsion_config.fingerprint_sha256
                    ),
                    "molecular_torsion_receipt": (
                        None
                        if proposal_torsion_receipt is None
                        else proposal_torsion_receipt.to_dict()
                    ),
                    "steric_field_config": (
                        None
                        if steric_field_config is None
                        else steric_field_config.to_dict()
                    ),
                    "steric_field_config_sha256": (
                        None
                        if steric_field_config is None
                        else steric_field_config.fingerprint_sha256
                    ),
                    "steric_field_plan": (
                        None
                        if translation_placement_plan is None
                        else translation_placement_plan.to_dict()
                    ),
                    "torsion_blockers": list(torsion_generation_blockers),
                    "translation_placement_blockers": list(
                        translation_placement_blockers
                    ),
                    "scientifically_validated": False,
                    "blockers": list(proposal_generation_blockers),
                },
                "pose_score": {
                    "selection_policy_id": (
                        "verified_rdkit_openff_ligand_preparation_gate/1.0.0"
                    ),
                    "preparation_gate_satisfied": preparation_verified,
                    "scorer_id": scorer.scorer_id,
                    "scorer_version": scorer.scorer_version,
                    "scorer_contract_fingerprint_sha256": (
                        search.scorer_contract_fingerprint_sha256
                    ),
                    "scorer_config_fingerprint_sha256": (
                        scorer.config_fingerprint_sha256
                    ),
                    "parameter_source_sha256": scorer.parameter_source_sha256,
                    "feature_binding_sha256": getattr(
                        scorer,
                        "feature_binding_sha256",
                        None,
                    ),
                    "score_descriptor": scorer.score_descriptor.to_dict(),
                    "chemistry_scope": scorer.chemistry_scope,
                    "receptor_shell_atom_count": scorer.receptor_shell_atom_count,
                    "validated_for_docking_ranking": False,
                    "blockers": list(scorer.blockers),
                },
                "pose_refinement": {
                    "selection_policy_id": (
                        "verified_rdkit_openff_ligand_preparation_refiner_gate/1.0.0"
                    ),
                    "preparation_gate_satisfied": preparation_verified,
                    "requested_max_refinement_steps": (
                        active.max_refinement_steps
                    ),
                    "effective_max_refinement_steps": (
                        effective_refinement_steps
                    ),
                    "performed": effective_refinement_steps > 0,
                    "move_count_per_step": refinement_move_count_per_step,
                    "estimated_move_evaluations": (
                        estimated_refinement_move_evaluations
                    ),
                    "maximum_move_evaluations": (
                        MAX_REDOCKING_DIAGNOSTIC_REFINEMENT_MOVE_EVALUATIONS
                    ),
                    "refiner_id": None if refiner is None else refiner.refiner_id,
                    "refiner_version": (
                        None if refiner is None else refiner.refiner_version
                    ),
                    "refiner_contract_fingerprint_sha256": (
                        None
                        if refiner is None
                        else search.refiner_contract_fingerprint_sha256
                    ),
                    "refiner_config": (
                        None
                        if refinement_config is None
                        else refinement_config.to_dict()
                    ),
                    "refiner_config_fingerprint_sha256": (
                        None
                        if refiner is None
                        else refiner.config_fingerprint_sha256
                    ),
                    "torsion_search_space_sha256": (
                        None
                        if refiner is None
                        else refiner.torsion_search_space_sha256
                    ),
                    "torsion_search_receipt": (
                        None
                        if refiner is None
                        else refiner.torsion_search_receipt.to_dict()
                    ),
                    "objective_is_force_field_energy": False,
                    "analytic_forces_available": False,
                    "scientifically_validated": False,
                    "blockers": list(
                        refiner_selection_blockers
                        if refiner is None
                        else refiner.blockers
                    ),
                },
                "pose_validity": {
                    "selection_policy_id": (
                        "verified_rdkit_openff_ligand_preparation_validity_gate/1.0.0"
                    ),
                    "preparation_gate_satisfied": preparation_verified,
                    "context_schema_id": (
                        "betelgeuze.engine_v2_chemistry_aware_pose_validity_v2_context/1.0.0"
                        if preparation_verified
                        else "betelgeuze.engine_v2_pose_validity_context/1.0.0"
                    ),
                    "result_schema_id": (
                        CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID
                        if preparation_verified
                        else None
                    ),
                    "context_fingerprint_sha256": (validity_context.fingerprint_sha256),
                    "profile_sha256": (
                        CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256
                        if preparation_verified
                        else None
                    ),
                    "chemistry_config": (
                        None
                        if chemistry_validity_config is None
                        else chemistry_validity_config.to_dict()
                    ),
                    "chemistry_config_fingerprint_sha256": (
                        None
                        if chemistry_validity_config is None
                        else chemistry_validity_config.fingerprint_sha256
                    ),
                    "base_config": validity_context.config.to_dict(),
                    "thresholds_calibrated": False,
                    "scientifically_validated": False,
                    "blockers": list(validity_context_blockers),
                },
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
                "all_candidate_rows_retained": (
                    len(search.rows) == active.candidate_count
                ),
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
        raise RedockingDiagnosticError(
            "redocking diagnostic receipt exceeds the byte limit"
        )

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
        raise RedockingDiagnosticError(
            "redocking diagnostic receipt must be UTF-8 JSON"
        ) from exc
    if not isinstance(document, dict):
        raise RedockingDiagnosticError("redocking diagnostic receipt must be an object")
    if raw != canonical_json_bytes(document):
        raise RedockingDiagnosticError(
            "redocking diagnostic receipt is not exact canonical JSON"
        )
    if document.get("schema_id") != REDOCKING_DIAGNOSTIC_SCHEMA_ID:
        raise RedockingDiagnosticError(
            "unsupported redocking diagnostic receipt schema"
        )
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
        raise RedockingDiagnosticError(
            "redocking diagnostic receipt fields are not canonical"
        )
    if document.get("claims") != _CLAIM_FLAGS:
        raise RedockingDiagnosticError(
            "redocking diagnostic claim flags cannot be promoted"
        )
    blockers = document.get("scientific_blockers")
    if (
        not isinstance(blockers, list)
        or any(not isinstance(blocker, str) or not blocker for blocker in blockers)
        or len(blockers) != len(set(blockers))
        or not set(REDOCKING_DIAGNOSTIC_BLOCKERS).issubset(blockers)
    ):
        raise RedockingDiagnosticError(
            "redocking diagnostic scientific blockers are incomplete"
        )
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
        config_report = document.get("config")
        if (
            not isinstance(summary, dict)
            or not isinstance(search, dict)
            or not isinstance(top_poses, list)
            or not isinstance(problem, dict)
            or not isinstance(input_contract, dict)
            or not isinstance(source_artifacts, dict)
            or not isinstance(ligand_preparation, dict)
            or not isinstance(config_report, dict)
            or summary.get("candidate_count") != search.get("candidate_count")
            or summary.get("top_pose_count") != len(top_poses)
            or summary.get("all_candidate_rows_retained") is not True
            or search.get("claim_safe") is not False
            or problem.get("authenticated_to_concrete_molecular_state") is not True
            or input_contract.get("arbitrary_pdb_or_sdf_accepted") is not False
        ):
            raise RedockingDiagnosticError(
                "redocking diagnostic success summary is inconsistent"
            )
        chemistry_preparation_performed = input_contract.get(
            "chemistry_preparation_performed"
        )
        preparation_verified = input_contract.get(
            "rdkit_openff_preparation_receipt_verified"
        )
        if (
            not isinstance(chemistry_preparation_performed, bool)
            or preparation_verified is not chemistry_preparation_performed
            or ligand_preparation.get("present") is not chemistry_preparation_performed
            or ligand_preparation.get("verified") is not chemistry_preparation_performed
            or ligand_preparation.get("diagnostic_redocking_ready")
            is not chemistry_preparation_performed
            or ligand_preparation.get("openff_parameterization_ready") is not False
        ):
            raise RedockingDiagnosticError(
                "redocking ligand preparation binding is inconsistent"
            )
        proposal_generation = config_report.get("proposal_generation")
        requested_max_torsions = config_report.get("max_torsions")
        search_budget = search.get("budget")
        search_space_derivation = problem.get("search_space_derivation")
        proposal_numeric_policy = (
            proposal_generation.get("numeric_policy")
            if isinstance(proposal_generation, dict)
            else None
        )
        distribution = document.get("distribution")
        if (
            not isinstance(proposal_generation, dict)
            or isinstance(requested_max_torsions, bool)
            or not isinstance(requested_max_torsions, int)
            or not 0 <= requested_max_torsions <= MAX_REDOCKING_DIAGNOSTIC_TORSIONS
            or not isinstance(search_budget, dict)
            or not isinstance(search_space_derivation, dict)
            or not isinstance(proposal_numeric_policy, dict)
            or not isinstance(distribution, dict)
        ):
            raise RedockingDiagnosticError(
                "redocking proposal-generation receipt is incomplete"
            )
        proposal_generation_enabled = bool(
            chemistry_preparation_performed and requested_max_torsions > 0
        )
        effective_max_torsions = (
            requested_max_torsions if proposal_generation_enabled else 0
        )
        materialized_torsion_count = proposal_generation.get(
            "materialized_torsion_count"
        )
        proposal_generation_blockers = proposal_generation.get("blockers")
        torsion_generation_blockers = proposal_generation.get(
            "torsion_blockers"
        )
        translation_placement_blockers = proposal_generation.get(
            "translation_placement_blockers"
        )
        steric_field_guidance_enabled = bool(
            chemistry_preparation_performed
        )
        expected_sampling_policy_id = (
            DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID
            if steric_field_guidance_enabled
            else DOCKING_SAMPLING_POLICY_ID
        )
        expected_placement_policy_id = (
            DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
            if steric_field_guidance_enabled
            else DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID
        )
        expected_placement_plan_sha256 = proposal_generation.get(
            "translation_placement_plan_sha256"
        )
        if (
            proposal_generation.get("selection_policy_id")
            != "verified_preparation_molecular_torsion_else_rigid/1.0.0"
            or proposal_generation.get("preparation_gate_satisfied")
            is not chemistry_preparation_performed
            or proposal_generation.get("requested_max_torsions")
            != requested_max_torsions
            or proposal_generation.get("effective_max_torsions")
            != effective_max_torsions
            or proposal_generation.get("global_torsion_sampling_enabled")
            is not proposal_generation_enabled
            or proposal_generation.get("haar_rotation_sampling_enabled") is not True
            or proposal_generation.get("steric_field_guidance_enabled")
            is not steric_field_guidance_enabled
            or proposal_generation.get("translation_placement_policy_id")
            != expected_placement_policy_id
            or set(proposal_numeric_policy)
            != {
                "schema_id",
                "coordinate_dtype",
                "accumulation_policy",
                "integer_index_dtype",
                "device",
                "torch_version",
                "rng_engine_id",
                "sampling_policy_id",
                "translation_placement_policy_id",
                "translation_placement_plan_sha256",
                "candidate_zero_policy",
                "torsion_sampling",
                "rotation_sampling",
                "quaternion_component_order",
                "translation_direction_sampling",
                "translation_radius_sampling",
                "translation_site_selection",
                "per_candidate_draw_order",
                "deterministic_algorithms_enabled",
            }
            or proposal_numeric_policy.get("schema_id")
            != DOCKING_NUMERIC_POLICY_SCHEMA_ID
            or proposal_numeric_policy.get("coordinate_dtype") != "float64"
            or proposal_numeric_policy.get("device") != "cpu"
            or proposal_numeric_policy.get("integer_index_dtype") != "int64"
            or proposal_numeric_policy.get("rng_engine_id")
            != "torch_cpu_default_generator_state/1.0.0"
            or proposal_numeric_policy.get("sampling_policy_id")
            != expected_sampling_policy_id
            or proposal_numeric_policy.get("translation_placement_policy_id")
            != expected_placement_policy_id
            or proposal_numeric_policy.get("translation_placement_plan_sha256")
            != expected_placement_plan_sha256
            or proposal_generation.get("translation_placement_policy_id")
            != proposal_numeric_policy.get("translation_placement_policy_id")
            or proposal_numeric_policy.get("rotation_sampling")
            != "shoemake_three_independent_uniforms_unit_quaternion_haar_so3"
            or proposal_numeric_policy.get("quaternion_component_order")
            != "x_y_z_w"
            or proposal_numeric_policy.get("translation_direction_sampling")
            != (
                None
                if steric_field_guidance_enabled
                else "normalized_three_normal_draws"
            )
            or proposal_numeric_policy.get("translation_radius_sampling")
            != (
                None
                if steric_field_guidance_enabled
                else "cube_root_uniform_volume_ball"
            )
            or proposal_numeric_policy.get("translation_site_selection")
            != (
                "deterministic_orientation_conditioned_steric_field_rank_cycle"
                if steric_field_guidance_enabled
                else None
            )
            or proposal_numeric_policy.get("per_candidate_draw_order")
            != (
                "torsions_then_haar_u1_u2_u3_then_steric_field_site_selection"
                if steric_field_guidance_enabled
                else "torsions_then_haar_u1_u2_u3_then_translation_direction_then_radius"
            )
            or not isinstance(
                proposal_numeric_policy.get("deterministic_algorithms_enabled"),
                bool,
            )
            or proposal_numeric_policy.get("torch_version")
            != distribution.get("torch_version")
            or proposal_generation.get("numeric_policy_sha256")
            != _embedded_plain_json_digest(
                proposal_numeric_policy,
                name="proposal numeric policy",
            )
            or proposal_generation.get("numeric_policy_sha256")
            != search.get("numeric_policy_sha256")
            or search.get("translation_placement_policy_id")
            != expected_placement_policy_id
            or search.get("translation_placement_plan_sha256")
            != expected_placement_plan_sha256
            or search_budget.get("max_torsions") != effective_max_torsions
            or proposal_generation.get("search_space_sha256")
            != search.get("search_space_fingerprint_sha256")
            or proposal_generation.get("search_space_sha256")
            != problem.get("search_space_sha256")
            or proposal_generation.get(
                "search_space_derivation_receipt_sha256"
            )
            != search_space_derivation.get("receipt_sha256")
            or proposal_generation.get("search_space_derivation_policy_id")
            != search_space_derivation.get("derivation_policy_id")
            or isinstance(materialized_torsion_count, bool)
            or not isinstance(materialized_torsion_count, int)
            or not 0 <= materialized_torsion_count <= effective_max_torsions
            or proposal_generation.get("scientifically_validated") is not False
            or not isinstance(proposal_generation_blockers, list)
            or not isinstance(torsion_generation_blockers, list)
            or not isinstance(translation_placement_blockers, list)
            or any(
                not isinstance(blocker, str) or not blocker
                for blocker in proposal_generation_blockers
            )
            or len(proposal_generation_blockers)
            != len(set(proposal_generation_blockers))
            or len(torsion_generation_blockers)
            != len(set(torsion_generation_blockers))
            or len(translation_placement_blockers)
            != len(set(translation_placement_blockers))
            or any(
                not isinstance(blocker, str) or not blocker
                for blocker in torsion_generation_blockers
            )
            or any(
                not isinstance(blocker, str) or not blocker
                for blocker in translation_placement_blockers
            )
            or set(proposal_generation_blockers)
            != set(torsion_generation_blockers)
            | set(translation_placement_blockers)
            or not set(proposal_generation_blockers).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "redocking proposal-generation binding is inconsistent"
            )
        raw_steric_field_config = proposal_generation.get(
            "steric_field_config"
        )
        raw_steric_field_plan = proposal_generation.get("steric_field_plan")
        steric_plan_sites_by_id: dict[str, dict[str, object]] = {}
        steric_retained_site_count = 0
        if steric_field_guidance_enabled:
            decoded_steric_field_config = _decode_embedded_plain_json_value(
                raw_steric_field_config,
                name="steric-field placement config",
            )
            decoded_steric_field_plan = _decode_embedded_plain_json_value(
                raw_steric_field_plan,
                name="steric-field placement plan",
            )
            if (
                not isinstance(decoded_steric_field_config, dict)
                or not isinstance(decoded_steric_field_plan, dict)
            ):
                raise RedockingDiagnosticError(
                    "steric-field placement plan is incomplete"
                )
            steric_plan_receipt_sha256 = _require_digest(
                decoded_steric_field_plan.get("receipt_sha256"),
                name="steric_field_plan_receipt_sha256",
            )
            unsigned_steric_plan = dict(decoded_steric_field_plan)
            unsigned_steric_plan.pop("receipt_sha256")
            plan_config = decoded_steric_field_plan.get("config")
            plan_sites = decoded_steric_field_plan.get("sites")
            retained_site_count = decoded_steric_field_plan.get(
                "retained_site_count"
            )
            source_grid_point_count = decoded_steric_field_plan.get(
                "source_grid_point_count"
            )
            if (
                steric_plan_receipt_sha256
                != _embedded_plain_json_digest(
                    unsigned_steric_plan,
                    name="steric-field placement plan",
                )
                or steric_plan_receipt_sha256
                != expected_placement_plan_sha256
                or decoded_steric_field_plan.get("schema_id")
                != STERIC_FIELD_PLACEMENT_PLAN_SCHEMA_ID
                or decoded_steric_field_plan.get("placement_policy_id")
                != expected_placement_policy_id
                or decoded_steric_field_plan.get("problem_fingerprint_sha256")
                != problem.get("docking_problem_fingerprint_sha256")
                or decoded_steric_field_plan.get(
                    "problem_input_fingerprint_sha256"
                )
                != problem.get("input_fingerprint_sha256")
                or decoded_steric_field_plan.get(
                    "search_space_fingerprint_sha256"
                )
                != problem.get("search_space_sha256")
                or decoded_steric_field_plan.get("receptor_system_sha256")
                != problem.get("receptor_system_sha256")
                or decoded_steric_field_plan.get("ligand_system_sha256")
                != problem.get("ligand_system_sha256")
                or decoded_steric_field_plan.get("pocket_definition_sha256")
                != problem.get("pocket_definition_sha256")
                or decoded_steric_field_plan.get("radius_profile_sha256")
                != GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256
                or decoded_steric_field_plan.get("config_sha256")
                != _embedded_plain_json_digest(
                    plan_config,
                    name="steric-field embedded config",
                )
                or proposal_generation.get("steric_field_config_sha256")
                != _embedded_plain_json_digest(
                    decoded_steric_field_config,
                    name="steric-field placement config",
                )
                or proposal_generation.get("steric_field_config_sha256")
                != decoded_steric_field_plan.get("config_sha256")
                or decoded_steric_field_config != plan_config
                or decoded_steric_field_plan.get("scientifically_validated")
                is not False
                or decoded_steric_field_plan.get("claim_safe") is not False
                or decoded_steric_field_plan.get("blockers")
                != translation_placement_blockers
                or any(
                    blocker in blockers
                    for blocker in _MISSING_STERIC_FIELD_BLOCKERS
                )
                or isinstance(retained_site_count, bool)
                or not isinstance(retained_site_count, int)
                or not 1 <= retained_site_count <= 256
                or isinstance(source_grid_point_count, bool)
                or not isinstance(source_grid_point_count, int)
                or source_grid_point_count < retained_site_count
                or not isinstance(plan_sites, list)
                or len(plan_sites) != retained_site_count
            ):
                raise RedockingDiagnosticError(
                    "steric-field placement plan binding is inconsistent"
                )
            config_translation_radius = _canonical_float_from_hex(
                decoded_steric_field_config.get(
                    "translation_radius_angstrom_hex"
                ),
                name="steric-field translation radius",
            )
            decoded_report_translation_radius = (
                _decode_embedded_plain_json_value(
                    config_report.get("translation_radius_angstrom"),
                    name="redocking translation radius",
                )
            )
            decoded_pocket_radius = _decode_embedded_plain_json_value(
                config_report.get("pocket_radius_angstrom"),
                name="redocking pocket radius",
            )
            plan_pocket_radius = _canonical_float_from_hex(
                decoded_steric_field_plan.get(
                    "pocket_radius_angstrom_hex"
                ),
                name="steric-field pocket radius",
            )
            if (
                isinstance(decoded_report_translation_radius, bool)
                or not isinstance(
                    decoded_report_translation_radius,
                    (int, float),
                )
                or config_translation_radius
                != float(decoded_report_translation_radius)
                or isinstance(decoded_pocket_radius, bool)
                or not isinstance(decoded_pocket_radius, (int, float))
                or plan_pocket_radius != float(decoded_pocket_radius)
                or decoded_steric_field_plan.get("pocket_center_angstrom_hex")
                != problem.get("pocket", {}).get("center_angstrom_hex")
            ):
                raise RedockingDiagnosticError(
                    "steric-field geometry binding is inconsistent"
                )
            observed_site_ids: list[str] = []
            zero_site_present = False
            for expected_site_index, site in enumerate(plan_sites):
                if not isinstance(site, dict):
                    raise RedockingDiagnosticError(
                        "steric-field site row is invalid"
                    )
                translation_hex = site.get("translation_angstrom_hex")
                anchor_overlap_pair_count = site.get(
                    "anchor_overlap_pair_count"
                )
                if (
                    set(site)
                    != {
                        "schema_id",
                        "site_id",
                        "site_index",
                        "translation_angstrom_hex",
                        "anchor_overlap_pair_count",
                        "anchor_overlap_penalty_hex",
                    }
                    or site.get("schema_id")
                    != "betelgeuze.engine_v2_steric_field_translation_site/1.0.0"
                    or site.get("site_index") != expected_site_index
                    or not isinstance(site.get("site_id"), str)
                    or not site.get("site_id")
                    or not isinstance(translation_hex, list)
                    or len(translation_hex) != 3
                    or isinstance(anchor_overlap_pair_count, bool)
                    or not isinstance(anchor_overlap_pair_count, int)
                    or anchor_overlap_pair_count < 0
                ):
                    raise RedockingDiagnosticError(
                        "steric-field site row is incomplete"
                    )
                site_translation = tuple(
                    _canonical_float_from_hex(
                        value,
                        name="steric-field site translation",
                    )
                    for value in translation_hex
                )
                anchor_penalty = _canonical_float_from_hex(
                    site.get("anchor_overlap_penalty_hex"),
                    name="steric-field anchor overlap penalty",
                )
                if (
                    anchor_penalty < 0.0
                    or math.sqrt(
                        math.fsum(value * value for value in site_translation)
                    )
                    > config_translation_radius + 1.0e-12
                ):
                    raise RedockingDiagnosticError(
                        "steric-field site geometry is invalid"
                    )
                zero_site_present = zero_site_present or all(
                    value == 0.0 for value in site_translation
                )
                observed_site_ids.append(site["site_id"])
            if (
                len(set(observed_site_ids)) != len(observed_site_ids)
                or not zero_site_present
            ):
                raise RedockingDiagnosticError(
                    "steric-field site identities are inconsistent"
                )
            steric_plan_sites_by_id = {
                str(site["site_id"]): site for site in plan_sites
            }
            steric_retained_site_count = retained_site_count
        elif (
            raw_steric_field_config is not None
            or proposal_generation.get("steric_field_config_sha256") is not None
            or raw_steric_field_plan is not None
            or expected_placement_plan_sha256 != ""
            or translation_placement_blockers
            != list(_MISSING_STERIC_FIELD_BLOCKERS)
            or not set(_MISSING_STERIC_FIELD_BLOCKERS).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "steric-field fallback binding is inconsistent"
            )
        proposal_molecular_torsion_receipt: dict[str, object] | None = None
        proposal_torsion_atom_indices: tuple[int, ...] = ()
        if proposal_generation_enabled:
            decoded_molecular_torsion_config = (
                _decode_embedded_plain_json_value(
                    proposal_generation.get("molecular_torsion_config"),
                    name="proposal molecular torsion config",
                )
            )
            raw_molecular_torsion_receipt = proposal_generation.get(
                "molecular_torsion_receipt"
            )
            decoded_molecular_torsion_receipt = (
                _decode_embedded_plain_json_value(
                    raw_molecular_torsion_receipt,
                    name="proposal molecular torsion receipt",
                )
            )
            if (
                proposal_generation.get("mode") != "molecular_torsion_haar"
                or not isinstance(decoded_molecular_torsion_config, dict)
                or not isinstance(decoded_molecular_torsion_receipt, dict)
            ):
                raise RedockingDiagnosticError(
                    "prepared proposal torsion materialization is incomplete"
                )
            proposal_molecular_torsion_receipt = (
                decoded_molecular_torsion_receipt
            )
            molecular_torsion_config_sha256 = _require_digest(
                proposal_generation.get("molecular_torsion_config_sha256"),
                name="proposal_molecular_torsion_config_sha256",
            )
            molecular_receipt_sha256 = _require_digest(
                proposal_molecular_torsion_receipt.get("receipt_sha256"),
                name="proposal_molecular_torsion_receipt_sha256",
            )
            unsigned_molecular_receipt = dict(
                proposal_molecular_torsion_receipt
            )
            unsigned_molecular_receipt.pop("receipt_sha256")
            molecular_bond_rows = proposal_molecular_torsion_receipt.get(
                "bond_rows"
            )
            if not isinstance(molecular_bond_rows, list):
                raise RedockingDiagnosticError(
                    "proposal molecular torsion bond rows are incomplete"
                )
            selected_child_indices = tuple(
                row.get("child_atom_index")
                for row in molecular_bond_rows
                if isinstance(row, dict) and row.get("status") == "selected"
            )
            if (
                molecular_receipt_sha256
                != _embedded_plain_json_digest(
                    unsigned_molecular_receipt,
                    name="proposal molecular torsion receipt",
                )
                or proposal_molecular_torsion_receipt.get("schema_id")
                != MOLECULAR_TORSION_SEARCH_RECEIPT_SCHEMA_ID
                or molecular_torsion_config_sha256
                != _embedded_plain_json_digest(
                    decoded_molecular_torsion_config,
                    name="proposal molecular torsion config",
                )
                or decoded_molecular_torsion_config.get("max_rotatable_bonds")
                != requested_max_torsions
                or proposal_molecular_torsion_receipt.get("search_space_sha256")
                != proposal_generation.get("search_space_sha256")
                or proposal_molecular_torsion_receipt.get("config_sha256")
                != molecular_torsion_config_sha256
                or proposal_molecular_torsion_receipt.get("system_sha256")
                != search_space_derivation.get("ligand_system_sha256")
                or proposal_molecular_torsion_receipt.get("topology_sha256")
                != search_space_derivation.get("ligand_topology_sha256")
                or proposal_molecular_torsion_receipt.get(
                    "input_coordinate_sha256"
                )
                != search_space_derivation.get(
                    "ligand_coordinate_fingerprint_sha256"
                )
                or proposal_molecular_torsion_receipt.get(
                    "rotatable_bond_count"
                )
                != materialized_torsion_count
                or len(selected_child_indices) != materialized_torsion_count
                or any(
                    isinstance(index, bool)
                    or not isinstance(index, int)
                    or index < 0
                    for index in selected_child_indices
                )
                or len(set(selected_child_indices)) != len(selected_child_indices)
                or search_space_derivation.get(
                    "parent_derivation_receipt_sha256"
                )
                != molecular_receipt_sha256
                or not str(
                    search_space_derivation.get("derivation_policy_id", "")
                ).startswith("bounded_molecular_graph_torsion_tree/")
                or proposal_molecular_torsion_receipt.get(
                    "scientifically_validated"
                )
                is not False
                or proposal_molecular_torsion_receipt.get("claim_safe") is not False
                or torsion_generation_blockers
                != proposal_molecular_torsion_receipt.get("blockers")
                or any(
                    blocker in blockers
                    for blocker in _MISSING_GLOBAL_TORSION_BLOCKERS
                )
            ):
                raise RedockingDiagnosticError(
                    "prepared proposal torsion binding is inconsistent"
                )
            proposal_torsion_atom_indices = tuple(
                sorted(cast(tuple[int, ...], selected_child_indices))
            )
        elif (
            proposal_generation.get("mode") != "rigid_haar"
            or materialized_torsion_count != 0
            or proposal_generation.get("molecular_torsion_config") is not None
            or proposal_generation.get("molecular_torsion_config_sha256") is not None
            or proposal_generation.get("molecular_torsion_receipt") is not None
            or search_space_derivation.get("derivation_policy_id")
            != RIGID_SEARCH_SPACE_DERIVATION_POLICY_ID
            or not set(_MISSING_GLOBAL_TORSION_BLOCKERS).issubset(blockers)
            or torsion_generation_blockers
            != list(_MISSING_GLOBAL_TORSION_BLOCKERS)
        ):
            raise RedockingDiagnosticError(
                "rigid proposal-generation fallback is inconsistent"
            )
        pose_score = config_report.get("pose_score")
        expected_scorer_id = (
            "interpretable-pose-scorer-v0"
            if chemistry_preparation_performed
            else "element-geometry-diagnostic"
        )
        expected_term_ids = (
            (
                "element_radius_contact_reward",
                "element_radius_overlap_penalty",
                "element_radius_deep_penetration_penalty",
                "pocket_centroid_restraint",
                "ligand_bond_length_strain",
                "ligand_angle_strain",
                "ligand_torsion_displacement",
                "directional_hydrogen_bond_reward",
                "hydrophobic_contact_reward",
            )
            if chemistry_preparation_performed
            else (
                "element_radius_contact_reward",
                "element_radius_overlap_penalty",
                "element_radius_deep_penetration_penalty",
                "pocket_centroid_restraint",
                "rigid_ligand_internal_strain",
            )
        )
        if not isinstance(pose_score, dict):
            raise RedockingDiagnosticError("redocking pose-score receipt is incomplete")
        pose_score_blockers = pose_score.get("blockers")
        pose_score_descriptor = pose_score.get("score_descriptor")
        receptor_shell_atom_count = pose_score.get("receptor_shell_atom_count")
        if (
            pose_score.get("selection_policy_id")
            != "verified_rdkit_openff_ligand_preparation_gate/1.0.0"
            or pose_score.get("preparation_gate_satisfied")
            is not chemistry_preparation_performed
            or pose_score.get("scorer_id") != expected_scorer_id
            or pose_score.get("scorer_id") != search.get("scorer_id")
            or pose_score.get("scorer_version") != search.get("scorer_version")
            or pose_score.get("scorer_contract_fingerprint_sha256")
            != search.get("scorer_contract_fingerprint_sha256")
            or pose_score_descriptor != search.get("score_descriptor")
            or not isinstance(pose_score_descriptor, dict)
            or pose_score_descriptor.get("calibrated") is not False
            or pose_score.get("validated_for_docking_ranking") is not False
            or not isinstance(pose_score.get("chemistry_scope"), dict)
            or isinstance(receptor_shell_atom_count, bool)
            or not isinstance(receptor_shell_atom_count, int)
            or receptor_shell_atom_count < 1
            or not isinstance(pose_score_blockers, list)
            or any(
                not isinstance(blocker, str) or not blocker
                for blocker in pose_score_blockers
            )
            or len(pose_score_blockers) != len(set(pose_score_blockers))
            or not set(pose_score_blockers).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "redocking pose-score binding is inconsistent"
            )
        for name in (
            "scorer_contract_fingerprint_sha256",
            "scorer_config_fingerprint_sha256",
            "parameter_source_sha256",
        ):
            _require_digest(pose_score.get(name), name=name)
        if chemistry_preparation_performed:
            _require_digest(
                pose_score.get("feature_binding_sha256"),
                name="feature_binding_sha256",
            )
            if any(
                blocker in blockers
                for blocker in _MISSING_INTERPRETABLE_SCORER_BLOCKERS
            ):
                raise RedockingDiagnosticError(
                    "verified preparation did not enable the interpretable scorer"
                )
        else:
            if pose_score.get("feature_binding_sha256") is not None:
                raise RedockingDiagnosticError(
                    "geometry-only scorer cannot declare a feature binding"
                )
            if not set(_MISSING_INTERPRETABLE_SCORER_BLOCKERS).issubset(blockers):
                raise RedockingDiagnosticError(
                    "missing preparation did not block the interpretable scorer"
                )
        pose_refinement = config_report.get("pose_refinement")
        requested_refinement_steps = config_report.get("max_refinement_steps")
        if (
            not isinstance(pose_refinement, dict)
            or isinstance(requested_refinement_steps, bool)
            or not isinstance(requested_refinement_steps, int)
            or not 0 <= requested_refinement_steps <= 32
        ):
            raise RedockingDiagnosticError(
                "redocking pose-refinement receipt is incomplete"
            )
        effective_refinement_steps = (
            requested_refinement_steps if chemistry_preparation_performed else 0
        )
        refinement_blockers = pose_refinement.get("blockers")
        search_budget = search.get("budget")
        refinement_move_count_per_step = pose_refinement.get(
            "move_count_per_step"
        )
        estimated_refinement_move_evaluations = pose_refinement.get(
            "estimated_move_evaluations"
        )
        maximum_refinement_move_evaluations = pose_refinement.get(
            "maximum_move_evaluations"
        )
        search_candidate_count = search.get("candidate_count")
        if (
            pose_refinement.get("selection_policy_id")
            != "verified_rdkit_openff_ligand_preparation_refiner_gate/1.0.0"
            or pose_refinement.get("preparation_gate_satisfied")
            is not chemistry_preparation_performed
            or pose_refinement.get("requested_max_refinement_steps")
            != requested_refinement_steps
            or pose_refinement.get("effective_max_refinement_steps")
            != effective_refinement_steps
            or pose_refinement.get("performed")
            is not (effective_refinement_steps > 0)
            or pose_refinement.get("objective_is_force_field_energy") is not False
            or pose_refinement.get("analytic_forces_available") is not False
            or pose_refinement.get("scientifically_validated") is not False
            or not isinstance(search_budget, dict)
            or search_budget.get("max_refinement_steps")
            != effective_refinement_steps
            or isinstance(search_candidate_count, bool)
            or not isinstance(search_candidate_count, int)
            or search_candidate_count < 1
            or isinstance(refinement_move_count_per_step, bool)
            or not isinstance(refinement_move_count_per_step, int)
            or refinement_move_count_per_step < 0
            or isinstance(estimated_refinement_move_evaluations, bool)
            or not isinstance(estimated_refinement_move_evaluations, int)
            or estimated_refinement_move_evaluations < 0
            or maximum_refinement_move_evaluations
            != MAX_REDOCKING_DIAGNOSTIC_REFINEMENT_MOVE_EVALUATIONS
            or estimated_refinement_move_evaluations
            > maximum_refinement_move_evaluations
            or not isinstance(refinement_blockers, list)
            or any(
                not isinstance(blocker, str) or not blocker
                for blocker in refinement_blockers
            )
            or len(refinement_blockers) != len(set(refinement_blockers))
            or not set(refinement_blockers).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "redocking pose-refinement binding is inconsistent"
            )
        torsion_search_receipt: dict[str, object] | None = None
        if chemistry_preparation_performed:
            if (
                pose_refinement.get("refiner_id")
                != "interpretable-local-pose-coordinate-descent-v0"
                or pose_refinement.get("refiner_id") != search.get("refiner_id")
                or pose_refinement.get("refiner_version") != "1.0.0"
                or pose_refinement.get("refiner_contract_fingerprint_sha256")
                != search.get("refiner_contract_fingerprint_sha256")
                or not isinstance(pose_refinement.get("refiner_config"), dict)
                or pose_refinement["refiner_config"].get("maximum_steps")
                != max(1, requested_refinement_steps)
                or not isinstance(
                    pose_refinement.get("torsion_search_receipt"),
                    dict,
                )
                or any(
                    blocker in blockers
                    for blocker in _MISSING_INTERPRETABLE_REFINER_BLOCKERS
                )
            ):
                raise RedockingDiagnosticError(
                    "verified preparation did not enable local pose refinement"
                )
            for name in (
                "refiner_contract_fingerprint_sha256",
                "refiner_config_fingerprint_sha256",
                "torsion_search_space_sha256",
            ):
                _require_digest(pose_refinement.get(name), name=name)
            decoded_torsion_search_receipt = _decode_embedded_plain_json_value(
                pose_refinement["torsion_search_receipt"],
                name="torsion_search_receipt",
            )
            if not isinstance(decoded_torsion_search_receipt, dict):
                raise RedockingDiagnosticError(
                    "redocking torsion-search receipt is invalid"
                )
            torsion_search_receipt = decoded_torsion_search_receipt
            torsion_receipt_sha256 = _require_digest(
                torsion_search_receipt.get("receipt_sha256"),
                name="torsion_search_receipt_sha256",
            )
            unsigned_torsion_receipt = dict(torsion_search_receipt)
            unsigned_torsion_receipt.pop("receipt_sha256")
            rotatable_bond_count = torsion_search_receipt.get(
                "rotatable_bond_count"
            )
            if (
                torsion_receipt_sha256
                != _embedded_plain_json_digest(
                    unsigned_torsion_receipt,
                    name="torsion_search_receipt",
                )
                or torsion_search_receipt.get("search_space_sha256")
                != pose_refinement.get("torsion_search_space_sha256")
                or (
                    proposal_generation_enabled
                    and pose_refinement.get("torsion_search_space_sha256")
                    != proposal_generation.get("search_space_sha256")
                )
                or torsion_search_receipt.get("scientifically_validated") is not False
                or torsion_search_receipt.get("claim_safe") is not False
                or isinstance(
                    rotatable_bond_count,
                    bool,
                )
                or not isinstance(rotatable_bond_count, int)
                or cast(int, rotatable_bond_count) < 0
                or refinement_move_count_per_step
                != 12
                + 2 * cast(int, rotatable_bond_count)
                or estimated_refinement_move_evaluations
                != search_candidate_count
                * effective_refinement_steps
                * refinement_move_count_per_step
            ):
                raise RedockingDiagnosticError(
                    "redocking torsion-search receipt is inconsistent"
                )
        elif (
            pose_refinement.get("refiner_id") is not None
            or pose_refinement.get("refiner_version") is not None
            or pose_refinement.get("refiner_contract_fingerprint_sha256") is not None
            or pose_refinement.get("refiner_config") is not None
            or pose_refinement.get("refiner_config_fingerprint_sha256") is not None
            or pose_refinement.get("torsion_search_space_sha256") is not None
            or pose_refinement.get("torsion_search_receipt") is not None
            or search.get("refiner_id") != ""
            or search.get("refiner_contract_fingerprint_sha256") != ""
            or refinement_move_count_per_step != 0
            or estimated_refinement_move_evaluations != 0
            or not set(_MISSING_INTERPRETABLE_REFINER_BLOCKERS).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "missing preparation did not block local pose refinement"
            )
        pose_validity = config_report.get("pose_validity")
        if not isinstance(pose_validity, dict):
            raise RedockingDiagnosticError(
                "redocking pose-validity receipt is incomplete"
            )
        pose_validity_blockers = pose_validity.get("blockers")
        expected_validity_context_schema = (
            "betelgeuze.engine_v2_chemistry_aware_pose_validity_v2_context/1.0.0"
            if chemistry_preparation_performed
            else "betelgeuze.engine_v2_pose_validity_context/1.0.0"
        )
        if (
            pose_validity.get("selection_policy_id")
            != "verified_rdkit_openff_ligand_preparation_validity_gate/1.0.0"
            or pose_validity.get("preparation_gate_satisfied")
            is not chemistry_preparation_performed
            or pose_validity.get("context_schema_id")
            != expected_validity_context_schema
            or pose_validity.get("context_fingerprint_sha256")
            != search.get("validity_context_fingerprint_sha256")
            or not isinstance(pose_validity.get("base_config"), dict)
            or pose_validity.get("thresholds_calibrated") is not False
            or pose_validity.get("scientifically_validated") is not False
            or not isinstance(pose_validity_blockers, list)
            or any(
                not isinstance(blocker, str) or not blocker
                for blocker in pose_validity_blockers
            )
            or len(pose_validity_blockers) != len(set(pose_validity_blockers))
            or not set(pose_validity_blockers).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "redocking pose-validity binding is inconsistent"
            )
        _require_digest(
            pose_validity.get("context_fingerprint_sha256"),
            name="validity_context_fingerprint_sha256",
        )
        if chemistry_preparation_performed:
            if (
                pose_validity.get("result_schema_id")
                != CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID
                or pose_validity.get("profile_sha256")
                != CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256
                or not isinstance(pose_validity.get("chemistry_config"), dict)
            ):
                raise RedockingDiagnosticError(
                    "verified preparation did not enable chemistry-aware validity v2"
                )
            _require_digest(
                pose_validity.get("chemistry_config_fingerprint_sha256"),
                name="chemistry_validity_config_fingerprint_sha256",
            )
            if any(
                blocker in blockers
                for blocker in _MISSING_CHEMISTRY_VALIDITY_V2_BLOCKERS
            ):
                raise RedockingDiagnosticError(
                    "verified preparation retained a missing validity v2 blocker"
                )
        elif (
            pose_validity.get("result_schema_id") is not None
            or pose_validity.get("profile_sha256") is not None
            or pose_validity.get("chemistry_config") is not None
            or pose_validity.get("chemistry_config_fingerprint_sha256") is not None
            or not set(_MISSING_CHEMISTRY_VALIDITY_V2_BLOCKERS).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "missing preparation did not block chemistry-aware validity v2"
            )
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
                or any(
                    blocker in blockers
                    for blocker in _MISSING_LIGAND_PREPARATION_BLOCKERS
                )
            ):
                raise RedockingDiagnosticError(
                    "redocking verified ligand preparation is inconsistent"
                )
        elif (
            preparation_digest is not None
            or ligand_preparation.get("receipt_sha256") is not None
            or ligand_preparation.get("config_sha256") is not None
            or ligand_preparation.get("schema_id") is not None
            or not set(_MISSING_LIGAND_PREPARATION_BLOCKERS).issubset(blockers)
        ):
            raise RedockingDiagnosticError(
                "redocking missing ligand preparation is inconsistent"
            )
        rows = search.get("rows")
        top_candidate_ids = search.get("top_candidate_ids")
        if (
            not isinstance(rows, list)
            or len(rows) != search.get("candidate_count")
            or tuple(
                row.get("proposal_index") if isinstance(row, dict) else None
                for row in rows
            )
            != tuple(range(len(rows)))
            or any(
                not isinstance(row, dict)
                or not isinstance(row.get("candidate_id"), str)
                or not row.get("candidate_id")
                for row in rows
            )
            or not isinstance(top_candidate_ids, list)
            or top_candidate_ids
            != [
                pose.get("candidate_id") for pose in top_poses if isinstance(pose, dict)
            ]
        ):
            raise RedockingDiagnosticError(
                "redocking diagnostic candidate rows are incomplete"
            )
        if len({row["candidate_id"] for row in rows}) != len(rows):
            raise RedockingDiagnosticError(
                "redocking diagnostic candidate IDs are not unique"
            )
        decoded_translation_radius = _decode_embedded_plain_json_value(
            config_report.get("translation_radius_angstrom"),
            name="translation_radius_angstrom",
        )
        if (
            isinstance(decoded_translation_radius, bool)
            or not isinstance(decoded_translation_radius, (int, float))
            or not math.isfinite(float(decoded_translation_radius))
            or float(decoded_translation_radius) < 0.0
        ):
            raise RedockingDiagnosticError(
                "redocking translation radius is invalid"
            )
        for expected_proposal_index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise RedockingDiagnosticError(
                    "redocking diagnostic candidate row is invalid"
                )
            sampling_state = row.get("proposal_sampling_state")
            if not isinstance(sampling_state, dict):
                raise RedockingDiagnosticError(
                    "redocking proposal sampling-state receipt is missing"
                )
            expected_sampling_state_fields = {
                "schema_id",
                "candidate_id",
                "proposal_fingerprint_sha256",
                "numeric_policy_sha256",
                "rng_state_before_sha256",
                "rng_state_after_sha256",
                "torsion_variable_count",
                "nonzero_torsion_count",
                "torsion_angle_rows",
                "rotation_matrix_hex",
                "translation_angstrom_hex",
                "translation_placement_receipt",
                "receipt_sha256",
            }
            sampling_receipt_sha256 = _require_digest(
                sampling_state.get("receipt_sha256"),
                name="proposal_sampling_state_receipt_sha256",
            )
            unsigned_sampling_state = dict(sampling_state)
            unsigned_sampling_state.pop("receipt_sha256")
            torsion_angle_rows = sampling_state.get("torsion_angle_rows")
            rotation_matrix_hex = sampling_state.get("rotation_matrix_hex")
            translation_hex = sampling_state.get("translation_angstrom_hex")
            placement_receipt = sampling_state.get(
                "translation_placement_receipt"
            )
            if (
                set(sampling_state) != expected_sampling_state_fields
                or sampling_receipt_sha256
                != _embedded_plain_json_digest(
                    unsigned_sampling_state,
                    name="proposal sampling-state receipt",
                )
                or sampling_state.get("schema_id")
                != DOCKING_PROPOSAL_SAMPLING_STATE_SCHEMA_ID
                or sampling_state.get("candidate_id") != row.get("candidate_id")
                or sampling_state.get("proposal_fingerprint_sha256")
                != row.get("proposal_fingerprint_sha256")
                or sampling_state.get("numeric_policy_sha256")
                != row.get("numeric_policy_sha256")
                or sampling_state.get("numeric_policy_sha256")
                != proposal_generation.get("numeric_policy_sha256")
                or sampling_state.get("rng_state_before_sha256")
                != row.get("rng_state_before_sha256")
                or sampling_state.get("rng_state_after_sha256")
                != row.get("rng_state_after_sha256")
                or sampling_state.get("torsion_variable_count")
                != materialized_torsion_count
                or not isinstance(torsion_angle_rows, list)
                or len(torsion_angle_rows) != materialized_torsion_count
                or not isinstance(rotation_matrix_hex, list)
                or len(rotation_matrix_hex) != 3
                or any(
                    not isinstance(matrix_row, list) or len(matrix_row) != 3
                    for matrix_row in rotation_matrix_hex
                )
                or not isinstance(translation_hex, list)
                or len(translation_hex) != 3
                or not isinstance(placement_receipt, dict)
            ):
                raise RedockingDiagnosticError(
                    "redocking proposal sampling-state binding is inconsistent"
                )
            expected_placement_receipt_fields = {
                "schema_id",
                "proposal_index",
                "placement_policy_id",
                "placement_plan_sha256",
                "problem_fingerprint_sha256",
                "search_space_fingerprint_sha256",
                "site_id",
                "site_index",
                "selected_rank",
                "evaluated_site_count",
                "translation_angstrom_hex",
                "steric_overlap_penalty_hex",
                "overlap_pair_count",
                "deep_overlap_pair_count",
                "pocket_outside_atom_count",
                "pocket_boundary_penalty_hex",
                "minimum_surface_separation_angstrom_hex",
                "scientifically_validated",
                "claim_safe",
                "blockers",
                "receipt_sha256",
            }
            placement_receipt_sha256 = _require_digest(
                placement_receipt.get("receipt_sha256"),
                name="translation_placement_receipt_sha256",
            )
            unsigned_placement_receipt = dict(placement_receipt)
            unsigned_placement_receipt.pop("receipt_sha256")
            placement_blockers = placement_receipt.get("blockers")
            if (
                set(placement_receipt)
                != expected_placement_receipt_fields
                or placement_receipt_sha256
                != _embedded_plain_json_digest(
                    unsigned_placement_receipt,
                    name="translation placement receipt",
                )
                or placement_receipt.get("schema_id")
                != DOCKING_TRANSLATION_PLACEMENT_RECEIPT_SCHEMA_ID
                or placement_receipt.get("proposal_index")
                != expected_proposal_index
                or placement_receipt.get("placement_policy_id")
                != expected_placement_policy_id
                or placement_receipt.get("placement_plan_sha256")
                != expected_placement_plan_sha256
                or placement_receipt.get("problem_fingerprint_sha256")
                != row.get("problem_fingerprint_sha256")
                or placement_receipt.get("search_space_fingerprint_sha256")
                != row.get("search_space_fingerprint_sha256")
                or placement_receipt.get("translation_angstrom_hex")
                != translation_hex
                or placement_receipt.get("scientifically_validated") is not False
                or placement_receipt.get("claim_safe") is not False
                or not isinstance(placement_blockers, list)
                or not placement_blockers
                or any(
                    not isinstance(blocker, str) or not blocker
                    for blocker in placement_blockers
                )
                or len(placement_blockers) != len(set(placement_blockers))
                or not set(placement_blockers).issubset(blockers)
                or not isinstance(placement_receipt.get("site_id"), str)
                or not placement_receipt.get("site_id")
            ):
                raise RedockingDiagnosticError(
                    "redocking translation placement receipt is inconsistent"
                )
            if steric_field_guidance_enabled:
                site_id = placement_receipt["site_id"]
                bound_site = steric_plan_sites_by_id.get(site_id)
                site_index = placement_receipt.get("site_index")
                selected_rank = placement_receipt.get("selected_rank")
                evaluated_site_count = placement_receipt.get(
                    "evaluated_site_count"
                )
                count_fields = (
                    "overlap_pair_count",
                    "deep_overlap_pair_count",
                    "pocket_outside_atom_count",
                )
                metric_fields = (
                    "steric_overlap_penalty_hex",
                    "pocket_boundary_penalty_hex",
                    "minimum_surface_separation_angstrom_hex",
                )
                if (
                    not isinstance(bound_site, dict)
                    or isinstance(site_index, bool)
                    or not isinstance(site_index, int)
                    or bound_site.get("site_index") != site_index
                    or bound_site.get("translation_angstrom_hex")
                    != translation_hex
                    or isinstance(selected_rank, bool)
                    or not isinstance(selected_rank, int)
                    or not 0 <= selected_rank < steric_retained_site_count
                    or evaluated_site_count != steric_retained_site_count
                    or any(
                        isinstance(placement_receipt.get(name), bool)
                        or not isinstance(placement_receipt.get(name), int)
                        or placement_receipt[name] < 0
                        for name in count_fields
                    )
                ):
                    raise RedockingDiagnosticError(
                        "redocking steric-field placement selection is invalid"
                    )
                placement_metrics = {
                    name: _canonical_float_from_hex(
                        placement_receipt.get(name),
                        name=f"translation placement {name}",
                    )
                    for name in metric_fields
                }
                if (
                    placement_metrics["steric_overlap_penalty_hex"] < 0.0
                    or placement_metrics["pocket_boundary_penalty_hex"] < 0.0
                    or placement_blockers != translation_placement_blockers
                    or (
                        expected_proposal_index == 0
                        and any(
                            _canonical_float_from_hex(
                                value,
                                name="baseline steric-field translation",
                            )
                            != 0.0
                            for value in translation_hex
                        )
                    )
                ):
                    raise RedockingDiagnosticError(
                        "redocking steric-field placement metrics are invalid"
                    )
            elif (
                placement_receipt.get("site_index") != -1
                or placement_receipt.get("selected_rank") != -1
                or placement_receipt.get("evaluated_site_count") != 0
                or placement_receipt.get("steric_overlap_penalty_hex") is not None
                or placement_receipt.get("overlap_pair_count") is not None
                or placement_receipt.get("deep_overlap_pair_count") is not None
                or placement_receipt.get("pocket_outside_atom_count") is not None
                or placement_receipt.get("pocket_boundary_penalty_hex") is not None
                or placement_receipt.get(
                    "minimum_surface_separation_angstrom_hex"
                )
                is not None
            ):
                raise RedockingDiagnosticError(
                    "uniform translation receipt claimed steric-field evaluation"
                )
            observed_torsion_indices: list[int] = []
            observed_torsion_angles: list[float] = []
            for torsion_row in torsion_angle_rows:
                if (
                    not isinstance(torsion_row, dict)
                    or set(torsion_row) != {"atom_index", "angle_radians_hex"}
                    or isinstance(torsion_row.get("atom_index"), bool)
                    or not isinstance(torsion_row.get("atom_index"), int)
                ):
                    raise RedockingDiagnosticError(
                        "redocking sampled torsion row is invalid"
                    )
                observed_torsion_indices.append(torsion_row["atom_index"])
                observed_torsion_angles.append(
                    _canonical_float_from_hex(
                        torsion_row.get("angle_radians_hex"),
                        name="sampled torsion angle",
                    )
                )
            if (
                tuple(observed_torsion_indices) != proposal_torsion_atom_indices
                or any(
                    angle < -math.pi or angle >= math.pi
                    for angle in observed_torsion_angles
                )
                or sampling_state.get("nonzero_torsion_count")
                != sum(angle != 0.0 for angle in observed_torsion_angles)
            ):
                raise RedockingDiagnosticError(
                    "redocking sampled torsion values are inconsistent"
                )
            rotation_matrix = tuple(
                tuple(
                    _canonical_float_from_hex(
                        value,
                        name="sampled rotation value",
                    )
                    for value in matrix_row
                )
                for matrix_row in rotation_matrix_hex
            )
            translation = tuple(
                _canonical_float_from_hex(
                    value,
                    name="sampled translation value",
                )
                for value in translation_hex
            )
            gram = tuple(
                tuple(
                    math.fsum(
                        rotation_matrix[row_index][first_column]
                        * rotation_matrix[row_index][second_column]
                        for row_index in range(3)
                    )
                    for second_column in range(3)
                )
                for first_column in range(3)
            )
            determinant = (
                rotation_matrix[0][0]
                * (
                    rotation_matrix[1][1] * rotation_matrix[2][2]
                    - rotation_matrix[1][2] * rotation_matrix[2][1]
                )
                - rotation_matrix[0][1]
                * (
                    rotation_matrix[1][0] * rotation_matrix[2][2]
                    - rotation_matrix[1][2] * rotation_matrix[2][0]
                )
                + rotation_matrix[0][2]
                * (
                    rotation_matrix[1][0] * rotation_matrix[2][1]
                    - rotation_matrix[1][1] * rotation_matrix[2][0]
                )
            )
            if (
                any(
                    abs(
                        gram[first_column][second_column]
                        - (1.0 if first_column == second_column else 0.0)
                    )
                    > 1.0e-10
                    for first_column in range(3)
                    for second_column in range(3)
                )
                or abs(determinant - 1.0) > 1.0e-10
                or math.sqrt(math.fsum(value * value for value in translation))
                > float(decoded_translation_radius) + 1.0e-12
            ):
                raise RedockingDiagnosticError(
                    "redocking sampled rigid transform is invalid"
                )
            proposal_index = row.get("proposal_index")
            if proposal_index != expected_proposal_index:
                raise RedockingDiagnosticError(
                    "redocking proposal row order is inconsistent"
                )
            if proposal_index == 0 and (
                any(angle != 0.0 for angle in observed_torsion_angles)
                or rotation_matrix
                != (
                    (1.0, 0.0, 0.0),
                    (0.0, 1.0, 0.0),
                    (0.0, 0.0, 1.0),
                )
                or any(value != 0.0 for value in translation)
                or row.get("rng_state_before_sha256")
                != row.get("rng_state_after_sha256")
            ):
                raise RedockingDiagnosticError(
                    "redocking baseline proposal sampling state is invalid"
                )
            row_refined = row.get("refined")
            row_refinement_receipt_sha256 = row.get(
                "refinement_receipt_sha256"
            )
            row_refinement_receipt = row.get("refinement_receipt")
            if effective_refinement_steps == 0:
                if (
                    row_refined is not False
                    or row_refinement_receipt_sha256 != ""
                    or row_refinement_receipt is not None
                ):
                    raise RedockingDiagnosticError(
                        "zero-step redocking row unexpectedly declares refinement"
                    )
            elif row_refined is True:
                if not isinstance(row_refinement_receipt, dict):
                    raise RedockingDiagnosticError(
                        "refined redocking row is missing its refinement receipt"
                    )
                refinement_receipt_sha256 = _require_digest(
                    row_refinement_receipt_sha256,
                    name="refinement_receipt_sha256",
                )
                if (
                    row_refinement_receipt.get("receipt_sha256")
                    != refinement_receipt_sha256
                ):
                    raise RedockingDiagnosticError(
                        "refinement receipt identity is inconsistent"
                    )
                decoded_refinement_receipt = _decode_embedded_plain_json_value(
                    row_refinement_receipt,
                    name="refinement_receipt",
                )
                if not isinstance(decoded_refinement_receipt, dict):
                    raise RedockingDiagnosticError(
                        "redocking local-refinement receipt is invalid"
                    )
                row_refinement_receipt = decoded_refinement_receipt
                unsigned_refinement_receipt = dict(row_refinement_receipt)
                unsigned_refinement_receipt.pop("receipt_sha256")
                refinement_steps = row_refinement_receipt.get("steps")
                score_trace = row_refinement_receipt.get("score_trace")
                coordinate_trace = row_refinement_receipt.get(
                    "coordinate_sha256_trace"
                )
                term_deltas = row_refinement_receipt.get("term_deltas")
                refinement_blockers = row_refinement_receipt.get("blockers")
                tolerance = row_refinement_receipt.get(
                    "constraint_residual_tolerance"
                )
                maximum_bond_residual = row_refinement_receipt.get(
                    "maximum_bond_length_residual_angstrom"
                )
                maximum_angle_residual = row_refinement_receipt.get(
                    "maximum_angle_residual_radians"
                )
                executed_step_count = row_refinement_receipt.get(
                    "executed_step_count"
                )
                accepted_step_count = row_refinement_receipt.get(
                    "accepted_step_count"
                )
                rejected_step_count = row_refinement_receipt.get(
                    "rejected_step_count"
                )
                total_evaluated_move_count = row_refinement_receipt.get(
                    "evaluated_move_count"
                )
                total_rejected_move_count = row_refinement_receipt.get(
                    "rejected_move_count"
                )
                initial_refinement_score = row_refinement_receipt.get(
                    "initial_score"
                )
                final_refinement_score = row_refinement_receipt.get(
                    "final_score"
                )
                if (
                    refinement_receipt_sha256
                    != _embedded_plain_json_digest(
                        unsigned_refinement_receipt,
                        name="refinement_receipt",
                    )
                    or row_refinement_receipt.get("schema_id")
                    != INTERPRETABLE_LOCAL_REFINEMENT_V0_RECEIPT_SCHEMA_ID
                    or row_refinement_receipt.get(
                        "parent_proposal_fingerprint_sha256"
                    )
                    != row.get("proposal_fingerprint_sha256")
                    or row_refinement_receipt.get("problem_fingerprint_sha256")
                    != row.get("problem_fingerprint_sha256")
                    or row_refinement_receipt.get(
                        "scorer_config_fingerprint_sha256"
                    )
                    != pose_score.get("scorer_config_fingerprint_sha256")
                    or row_refinement_receipt.get("feature_binding_sha256")
                    != pose_score.get("feature_binding_sha256")
                    or row_refinement_receipt.get(
                        "refiner_config_fingerprint_sha256"
                    )
                    != pose_refinement.get(
                        "refiner_config_fingerprint_sha256"
                    )
                    or row_refinement_receipt.get(
                        "torsion_search_space_sha256"
                    )
                    != pose_refinement.get("torsion_search_space_sha256")
                    or not isinstance(torsion_search_receipt, dict)
                    or row_refinement_receipt.get(
                        "torsion_search_receipt_sha256"
                    )
                    != torsion_search_receipt.get("receipt_sha256")
                    or row_refinement_receipt.get("requested_steps")
                    != effective_refinement_steps
                    or isinstance(executed_step_count, bool)
                    or not isinstance(executed_step_count, int)
                    or not 1 <= executed_step_count <= effective_refinement_steps
                    or not isinstance(refinement_steps, list)
                    or len(refinement_steps) != executed_step_count
                    or not isinstance(score_trace, list)
                    or len(score_trace) != executed_step_count + 1
                    or not isinstance(coordinate_trace, list)
                    or len(coordinate_trace) != executed_step_count + 1
                    or isinstance(accepted_step_count, bool)
                    or not isinstance(accepted_step_count, int)
                    or accepted_step_count < 0
                    or isinstance(rejected_step_count, bool)
                    or not isinstance(rejected_step_count, int)
                    or rejected_step_count < 0
                    or accepted_step_count + rejected_step_count
                    != executed_step_count
                    or isinstance(total_evaluated_move_count, bool)
                    or not isinstance(total_evaluated_move_count, int)
                    or total_evaluated_move_count < 12
                    or isinstance(total_rejected_move_count, bool)
                    or not isinstance(total_rejected_move_count, int)
                    or total_rejected_move_count < 0
                    or not isinstance(term_deltas, list)
                    or tuple(
                        term.get("term_id") if isinstance(term, dict) else None
                        for term in term_deltas
                    )
                    != expected_term_ids
                    or isinstance(tolerance, bool)
                    or not isinstance(tolerance, (int, float))
                    or not math.isfinite(float(tolerance))
                    or float(tolerance) <= 0.0
                    or isinstance(maximum_bond_residual, bool)
                    or not isinstance(maximum_bond_residual, (int, float))
                    or not 0.0 <= float(maximum_bond_residual) <= float(tolerance)
                    or isinstance(maximum_angle_residual, bool)
                    or not isinstance(maximum_angle_residual, (int, float))
                    or not 0.0 <= float(maximum_angle_residual) <= float(tolerance)
                    or row_refinement_receipt.get(
                        "objective_is_force_field_energy"
                    )
                    is not False
                    or row_refinement_receipt.get("analytic_forces_available")
                    is not False
                    or row_refinement_receipt.get(
                        "tangent_force_residual_available"
                    )
                    is not False
                    or row_refinement_receipt.get("scientifically_validated")
                    is not False
                    or row_refinement_receipt.get("claim_safe") is not False
                    or not isinstance(refinement_blockers, list)
                    or any(
                        not isinstance(blocker, str) or not blocker
                        for blocker in refinement_blockers
                    )
                    or not set(refinement_blockers).issubset(blockers)
                    or refinement_blockers != pose_refinement.get("blockers")
                    or isinstance(initial_refinement_score, bool)
                    or not isinstance(initial_refinement_score, (int, float))
                    or not math.isfinite(float(initial_refinement_score))
                    or isinstance(final_refinement_score, bool)
                    or not isinstance(final_refinement_score, (int, float))
                    or not math.isfinite(float(final_refinement_score))
                    or float(final_refinement_score)
                    > float(initial_refinement_score)
                    or row_refinement_receipt.get("improved")
                    is not (
                        float(final_refinement_score)
                        < float(initial_refinement_score)
                    )
                    or row_refinement_receipt.get("initial_coordinate_sha256")
                    != coordinate_trace[0]
                    or row_refinement_receipt.get("final_coordinate_sha256")
                    != coordinate_trace[-1]
                ):
                    raise RedockingDiagnosticError(
                        "redocking local-refinement row is inconsistent"
                    )
                if (
                    any(
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(float(value))
                        for value in score_trace
                    )
                    or score_trace[0]
                    != row_refinement_receipt.get("initial_score")
                    or score_trace[-1]
                    != row_refinement_receipt.get("final_score")
                    or any(
                        second > first
                        for first, second in zip(score_trace, score_trace[1:])
                    )
                    or any(
                        not isinstance(value, str)
                        or len(value) != 64
                        or any(
                            character not in "0123456789abcdef"
                            for character in value
                        )
                        for value in coordinate_trace
                    )
                ):
                    raise RedockingDiagnosticError(
                        "redocking local-refinement score or coordinate trace is invalid"
                    )
                observed_accepted_steps = 0
                observed_rejected_steps = 0
                observed_evaluated_moves = 0
                observed_rejected_moves = 0
                observed_maximum_bond_residual = 0.0
                observed_maximum_angle_residual = 0.0
                for index, step in enumerate(refinement_steps, start=1):
                    if not isinstance(step, dict):
                        raise RedockingDiagnosticError(
                            "redocking local-refinement iteration trace is invalid"
                        )
                    outcome = step.get("outcome")
                    move_id = step.get("move_id")
                    score_before = step.get("score_before")
                    score_after = step.get("score_after")
                    evaluated_moves = step.get("evaluated_move_count")
                    rejected_moves = step.get("rejected_move_count")
                    step_bond_residual = step.get(
                        "maximum_bond_length_residual_angstrom"
                    )
                    step_angle_residual = step.get(
                        "maximum_angle_residual_radians"
                    )
                    if (
                        step.get("iteration") != index
                        or outcome not in {"accepted", "rejected_reduce_steps"}
                        or not isinstance(move_id, str)
                        or (outcome == "accepted" and not move_id)
                        or (outcome != "accepted" and bool(move_id))
                        or isinstance(score_before, bool)
                        or not isinstance(score_before, (int, float))
                        or not math.isfinite(float(score_before))
                        or isinstance(score_after, bool)
                        or not isinstance(score_after, (int, float))
                        or not math.isfinite(float(score_after))
                        or float(score_before) != float(score_trace[index - 1])
                        or float(score_after) != float(score_trace[index])
                        or float(score_after) > float(score_before)
                        or (
                            outcome == "accepted"
                            and float(score_after) >= float(score_before)
                        )
                        or (
                            outcome == "rejected_reduce_steps"
                            and float(score_after) != float(score_before)
                        )
                        or isinstance(evaluated_moves, bool)
                        or not isinstance(evaluated_moves, int)
                        or evaluated_moves != refinement_move_count_per_step
                        or isinstance(rejected_moves, bool)
                        or not isinstance(rejected_moves, int)
                        or rejected_moves
                        != evaluated_moves - (1 if outcome == "accepted" else 0)
                        or step.get("coordinate_sha256") != coordinate_trace[index]
                        or any(
                            isinstance(step.get(name), bool)
                            or not isinstance(step.get(name), (int, float))
                            or not math.isfinite(float(step[name]))
                            or float(step[name]) <= 0.0
                            for name in (
                                "translation_step_angstrom",
                                "rotation_step_radians",
                                "torsion_step_radians",
                            )
                        )
                        or isinstance(step_bond_residual, bool)
                        or not isinstance(step_bond_residual, (int, float))
                        or not 0.0 <= float(step_bond_residual) <= float(tolerance)
                        or isinstance(step_angle_residual, bool)
                        or not isinstance(step_angle_residual, (int, float))
                        or not 0.0 <= float(step_angle_residual) <= float(tolerance)
                    ):
                        raise RedockingDiagnosticError(
                            "redocking local-refinement iteration trace is invalid"
                        )
                    observed_accepted_steps += outcome == "accepted"
                    observed_rejected_steps += outcome == "rejected_reduce_steps"
                    observed_evaluated_moves += evaluated_moves
                    observed_rejected_moves += rejected_moves
                    observed_maximum_bond_residual = max(
                        observed_maximum_bond_residual,
                        float(step_bond_residual),
                    )
                    observed_maximum_angle_residual = max(
                        observed_maximum_angle_residual,
                        float(step_angle_residual),
                    )
                if (
                    observed_accepted_steps != accepted_step_count
                    or observed_rejected_steps != rejected_step_count
                    or observed_evaluated_moves != total_evaluated_move_count
                    or observed_rejected_moves != total_rejected_move_count
                    or observed_maximum_bond_residual
                    != float(maximum_bond_residual)
                    or observed_maximum_angle_residual
                    != float(maximum_angle_residual)
                ):
                    raise RedockingDiagnosticError(
                        "redocking local-refinement trace totals are inconsistent"
                    )
                initial_term_contributions: list[float] = []
                final_term_contributions: list[float] = []
                for term_delta in term_deltas:
                    if not isinstance(term_delta, dict):
                        raise RedockingDiagnosticError(
                            "redocking local-refinement term delta is invalid"
                        )
                    numeric_values = tuple(
                        term_delta.get(name)
                        for name in (
                            "initial_raw_value",
                            "initial_contribution",
                            "final_raw_value",
                            "final_contribution",
                            "contribution_delta",
                        )
                    )
                    if any(
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(float(value))
                        for value in numeric_values
                    ):
                        raise RedockingDiagnosticError(
                            "redocking local-refinement term delta is invalid"
                        )
                    initial_contribution = float(
                        cast(int | float, numeric_values[1])
                    )
                    final_contribution = float(
                        cast(int | float, numeric_values[3])
                    )
                    if float(cast(int | float, numeric_values[4])) != (
                        final_contribution - initial_contribution
                    ):
                        raise RedockingDiagnosticError(
                            "redocking local-refinement term delta is inconsistent"
                        )
                    initial_term_contributions.append(initial_contribution)
                    final_term_contributions.append(final_contribution)
                if (
                    math.fsum(initial_term_contributions)
                    != float(initial_refinement_score)
                    or math.fsum(final_term_contributions)
                    != float(final_refinement_score)
                ):
                    raise RedockingDiagnosticError(
                        "redocking local-refinement term totals are inconsistent"
                    )
                if row.get("succeeded") is True and (
                    row_refinement_receipt.get("final_score")
                    != _decode_embedded_plain_json_value(
                        row.get("score"),
                        name="redocking row score",
                    )
                ):
                    raise RedockingDiagnosticError(
                        "refined row score disagrees with its refinement receipt"
                    )
            elif (
                row_refined is not False
                or row_refinement_receipt_sha256 != ""
                or row_refinement_receipt is not None
                or row.get("succeeded") is True
            ):
                raise RedockingDiagnosticError(
                    "successful prepared redocking row was not refined"
                )
            if row.get("succeeded") is not True:
                continue
            score_breakdown = row.get("score_breakdown")
            terms = (
                score_breakdown.get("terms")
                if isinstance(score_breakdown, dict)
                else None
            )
            if (
                not isinstance(terms, list)
                or tuple(
                    term.get("term_id") if isinstance(term, dict) else None
                    for term in terms
                )
                != expected_term_ids
            ):
                raise RedockingDiagnosticError(
                    "redocking score-term receipt is inconsistent"
                )
            validity = row.get("pose_validity")
            if not isinstance(validity, dict):
                raise RedockingDiagnosticError("redocking pose-validity row is missing")
            if chemistry_preparation_performed:
                checks = validity.get("checks")
                evaluated_checks = validity.get("evaluated_checks")
                required_v2_checks = {
                    "verified_ligand_preparation_bound",
                    "supported_atomic_number_scope",
                    "formal_charge_within_supported_range",
                    "reference_relative_bond_geometry_within_limit",
                    "reference_relative_angle_geometry_within_limit",
                    "declared_chirality_preserved",
                    "declared_double_bond_stereo_preserved",
                    "ligand_element_scaled_self_clash_free",
                    "receptor_ligand_element_scaled_penetration_free",
                }
                if (
                    validity.get("schema_id")
                    != CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID
                    or validity.get("claim_safe") is not False
                    or validity.get("scientifically_validated") is not False
                    or validity.get("thresholds_calibrated") is not False
                    or validity.get("complete") is not True
                    or validity.get("validity_context_fingerprint_sha256")
                    != pose_validity.get("context_fingerprint_sha256")
                    or validity.get("problem_fingerprint_sha256")
                    != row.get("problem_fingerprint_sha256")
                    or validity.get("proposal_fingerprint_sha256")
                    != row.get("result_proposal_fingerprint_sha256")
                    or validity.get("ligand_preparation_receipt_sha256")
                    != preparation_digest
                    or not isinstance(checks, dict)
                    or not required_v2_checks.issubset(checks)
                    or not isinstance(evaluated_checks, dict)
                    or set(checks) != set(evaluated_checks)
                    or any(value is not True for value in evaluated_checks.values())
                ):
                    raise RedockingDiagnosticError(
                        "redocking chemistry-aware validity v2 row is inconsistent"
                    )
            elif "schema_id" in validity or validity.get("claim_safe") is not False:
                raise RedockingDiagnosticError(
                    "geometry-only validity row is inconsistent"
                )
        for name in (
            "receptor_canonical_json_sha256",
            "ligand_canonical_json_sha256",
            "receptor_input_system_sha256",
            "ligand_input_system_sha256",
        ):
            _require_digest(source_artifacts.get(name), name=name)
        derivation = problem.get("search_space_derivation")
        atom_count = (
            derivation.get("atom_count") if isinstance(derivation, dict) else None
        )
        if (
            isinstance(atom_count, bool)
            or not isinstance(atom_count, int)
            or atom_count < 1
        ):
            raise RedockingDiagnosticError(
                "redocking diagnostic ligand atom count is invalid"
            )
        for pose in top_poses:
            if not isinstance(pose, dict):
                raise RedockingDiagnosticError(
                    "redocking diagnostic top pose is invalid"
                )
            coordinates = pose.get("coordinates_angstrom_hex")
            if not isinstance(coordinates, list) or len(coordinates) != atom_count:
                raise RedockingDiagnosticError(
                    "redocking diagnostic top-pose atom count is inconsistent"
                )
            for row in coordinates:
                if not isinstance(row, list) or len(row) != 3:
                    raise RedockingDiagnosticError(
                        "redocking diagnostic top-pose coordinates are invalid"
                    )
                for token in row:
                    if not isinstance(token, str):
                        raise RedockingDiagnosticError(
                            "redocking diagnostic coordinate token is invalid"
                        )
                    try:
                        number = float.fromhex(token)
                    except ValueError as exc:
                        raise RedockingDiagnosticError(
                            "redocking diagnostic coordinate token is invalid"
                        ) from exc
                    if not math.isfinite(number) or token != number.hex():
                        raise RedockingDiagnosticError(
                            "redocking diagnostic coordinate token is not canonical"
                        )
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
            raise RedockingDiagnosticError(
                "redocking diagnostic failure receipt is incomplete"
            )
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
        raise RedockingDiagnosticError(
            "redocking input could not be opened as a regular file"
        ) from exc
    if stat.S_ISLNK(path_before.st_mode) or not stat.S_ISREG(path_before.st_mode):
        raise RedockingDiagnosticError(
            "redocking input must be a non-symlink regular file"
        )
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise RedockingDiagnosticError(
            "redocking input could not be opened as a regular file"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RedockingDiagnosticError("redocking input must be a regular file")
        if before.st_dev != path_before.st_dev or before.st_ino != path_before.st_ino:
            raise RedockingDiagnosticError(
                "redocking input path changed before it was opened"
            )
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
            raise RedockingDiagnosticError(
                "redocking input path changed while it was being read"
            ) from exc
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
            raise RedockingDiagnosticError(
                "redocking input changed while it was being read"
            )
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
        raise RedockingDiagnosticError(
            "redocking diagnostic receipt exceeds the byte limit"
        )
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
            raise RedockingDiagnosticError(
                "redocking diagnostic output already exists"
            ) from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a claim-closed prepared redocking diagnostic from exact "
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
        "--max-torsions",
        type=int,
        default=32,
    )
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
    parser.add_argument(
        "--max-refinement-steps",
        type=int,
        default=6,
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
                max_torsions=args.max_torsions,
                translation_radius_angstrom=args.translation_radius,
                diversity_rmsd_angstrom=args.diversity_rmsd,
                max_refinement_steps=args.max_refinement_steps,
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
            + (
                "a failure receipt was written"
                if output is not None
                else "no output path was replaced"
            ),
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
    "MAX_REDOCKING_DIAGNOSTIC_REFINEMENT_MOVE_EVALUATIONS",
    "MAX_REDOCKING_DIAGNOSTIC_TORSIONS",
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
