from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = "tier_beta_biodiscovery_screening_v1"
CLAIM_SCOPE = "restricted_local_delivery_tier_beta_screening"


class FailureCode(str, Enum):
    NONE = "none"
    EMPTY_PROTEIN_INPUT = "empty_protein_input"
    PROTEIN_PARSE_FAILED = "protein_parse_failed"
    PROTEIN_INVALID = "protein_invalid"
    PLACEHOLDER_TOPOLOGY = "placeholder_topology"
    UNSUPPORTED_METAL = "unsupported_metal"
    UNSUPPORTED_COFACTOR = "unsupported_cofactor_or_bound_ligand"
    EMPTY_LIGAND_INPUT = "empty_ligand_input"
    LIGAND_PARSE_FAILED = "ligand_parse_failed"
    LIGAND_INVALID = "ligand_invalid"
    UNASSIGNED_LIGAND_CHIRALITY = "unassigned_ligand_chirality"
    EMPTY_LIGAND_TOPOLOGY = "empty_ligand_topology"
    LIGAND_CONFORMER_GENERATION_FAILED = "ligand_conformer_generation_failed"
    ZERO_CONFORMERS_GENERATED = "zero_conformers_generated"
    INVALID_POCKET_RESIDUE_INDICES = "invalid_pocket_residue_indices"
    EMPTY_POCKET_RESOLUTION = "empty_pocket_resolution"
    DENSE_DIAGNOSTIC_BLOCKED = "dense_diagnostic_blocked"
    NEIGHBOR_OVERFLOW = "neighbor_overflow"
    REFERENCE_NXN_BLOCKED = "reference_nxn_blocked"
    FORCEFIELD_EVALUATION_BLOCKED = "forcefield_evaluation_blocked"
    NO_POSES_SCORED = "no_poses_scored"
    STABILITY_FAILED = "stability_failed"
    UNSIGNED_RESULT_MANIFEST = "unsigned_result_manifest"
    SCREENING_CLAIM_NOT_SAFE = "screening_claim_not_safe"
    RESTRICTED_TIER_BETA_UNVALIDATED = "restricted_tier_beta_unvalidated"


@dataclass(frozen=True)
class StageRecord:
    stage_id: str
    schema_version: str
    status: str
    failure_code: str = FailureCode.NONE.value
    message: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TierBetaScreeningInput:
    protein_input_kind: str
    ligand_input_kind: str
    pose_count: int
    top_k: int
    stability_steps: int
    seed: int
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TierBetaScreeningOutput:
    ok: bool
    failure_code: str
    blocked_reason: str
    protein_residue_count: int
    ligand_atom_count: int
    poses_generated: int
    poses_scored: int
    top_k: int
    manifest_hash: str
    scientific_decision_available: bool = False
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def failure_code_for_reason(reason: str) -> str:
    text = str(reason or "")
    if not text:
        return FailureCode.NONE.value
    if "unsupported_metal" in text:
        return FailureCode.UNSUPPORTED_METAL.value
    if "unsupported_cofactor" in text:
        return FailureCode.UNSUPPORTED_COFACTOR.value
    if "unassigned_ligand_chirality" in text:
        return FailureCode.UNASSIGNED_LIGAND_CHIRALITY.value
    if "NxN" in text or "reference" in text:
        return FailureCode.REFERENCE_NXN_BLOCKED.value
    for code in FailureCode:
        if code is FailureCode.NONE:
            continue
        if code.value in text:
            return code.value
    return FailureCode.SCREENING_CLAIM_NOT_SAFE.value
