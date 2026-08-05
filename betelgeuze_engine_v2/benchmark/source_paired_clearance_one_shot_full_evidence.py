"""Verify complete two-arm evidence for the historical one-shot clearance A/B.

The full bundle contains all eight case activation receipts and all 1,024
candidate receipts. Verification reconstructs the canonical scorer, validity,
PoseBusters, RMSD, candidate, ranking, and case-source contracts before deriving
the compact result inputs. It never reserves or executes the experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.docking.guided_placement import (
    SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID,
)
from betelgeuze_engine_v2.docking.scorer_v1 import (
    SCORER_V1_BACKEND_RECEIPT_SCHEMA_ID,
    SCORER_V1_SCORE_ID,
    SCORER_V1_TERMS_SCHEMA_ID,
    ScorerBackend,
    ScorerBackendReceipt,
    ScorerV1Terms,
)
from betelgeuze_engine_v2.docking.validity import PoseValidityResult

from .source_paired_clearance_activation import (
    INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_SET_SHA256,
    SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_ACTIVATION_SNAPSHOT_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR,
    SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
    SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID,
    SourcePairedClearanceArmRankingReceiptV1,
    SourcePairedClearanceCaseSourceReceiptV1,
    SourcePairedClearanceCandidateEvidenceV1,
    SourcePairedClearanceInternalValidityEvidenceV1,
    SourcePairedClearancePoseBustersEvidenceV1,
    SourcePairedClearanceRmsdEvidenceV1,
)
from .source_paired_clearance_one_shot_ab import (
    EXPECTED_POLICY_SHA256,
    OneShotABAuthorityError,
    _is_sha256,
    sha256_payload,
    verify_self_hash,
)
from .source_paired_clearance_one_shot_result import (
    EXPECTED_BASELINE_PROFILE_ID,
    EXPECTED_EXPERIMENTAL_PROFILE_ID,
    build_arm_summary,
)


FULL_EVIDENCE_BUNDLE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_full_evidence/1.0.0"
)
FULL_CASE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_full_case/1.0.0"
)
MAX_FULL_EVIDENCE_BYTES = 512 * 1024 * 1024
EXPECTED_ACTIVATION_POLICY_SHA256 = (
    "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c"
)
_REQUIRED_BACKEND = ScorerBackend.RUST_CPU_REQUIRED.value
_PREPARATION_FAILURE_CASE_IDS = ("6M73_FNR",)
_AUTHORITY_KEYS = (
    "customer_pose_emission_authorized",
    "fresh_holdout_execution_authorized",
    "product_execution_authorized",
    "profile_promotion_authority",
    "public_or_scientific_claim_authorized",
    "stage0_admission_authority",
)
_BUNDLE_KEYS = {
    "activation_policy_sha256",
    "authority",
    "baseline_arm_summary_projection",
    "case_evidence_rows",
    "cross_arm_projection",
    "execution_environment_sha256",
    "experimental_arm_summary_projection",
    "policy_sha256",
    "receipt_sha256",
    "required_scorer_backend",
    "scorer_backend_receipt",
    "run_start_receipt_sha256",
    "schema_id",
    "source_commit_git_sha1",
}
_CASE_EVIDENCE_KEYS = {
    "activation_policy_sha256",
    "case_id",
    "execution_environment_sha256",
    "policy_sha256",
    "receipt_sha256",
    "run_start_receipt_sha256",
    "schema_id",
    "scorer_backend_receipt_sha256",
    "selection_activation_receipt",
    "selection_activation_receipt_sha256",
    "source_commit_git_sha1",
}
_SELECTION_RECEIPT_KEYS = {
    "activation_target_count",
    "activation_targets",
    "allocation_receipt",
    "allocation_receipt_sha256",
    "authenticated_rmsd_receipts_verified",
    "baseline_arm_ranking",
    "case_id",
    "case_source",
    "current_v7_candidate_lineage_sha256",
    "current_v7_lineage",
    "decision_sealed_before_score_rank_validity",
    "experimental_arm_ranking",
    "fresh_holdout_execution_authorized",
    "full_current_v7_candidate_lineage_verified",
    "full_posebusters_check_set_verified",
    "full_scoring_and_validity_evidence",
    "full_source_proposal_lineage_verified",
    "historical_ab_execution_authorized",
    "product_or_claim_authority",
    "receipt_sha256",
    "schema_id",
    "score_term_semantics_fully_rederivable",
    "selected_replacement_proposal_indices",
    "source_proposal_receipt",
    "source_proposal_receipt_sha256",
    "top1_top5_semantics_fully_rederivable",
}
_SCORER_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
    "total_score",
)
_SCORER_COUNT_NAMES = (
    "receptor_candidate_pair_count",
    "ligand_pair_count",
    "hbond_count",
    "hydrophobic_contact_count",
    "buried_polar_count",
)
_SCORER_KEYS = {
    "authority_input_receipt_sha256",
    "backend_receipt_sha256",
    "buried_polar_count",
    "calibrated",
    "claim_safe",
    "config_fingerprint_sha256",
    "context_fingerprint_sha256",
    "directional_hbond_binary64_hex",
    "electrostatics_binary64_hex",
    "hbond_count",
    "hydrophobic_contact_binary64_hex",
    "hydrophobic_contact_count",
    "ligand_pair_count",
    "ligand_strain_binary64_hex",
    "proposal_fingerprint_sha256",
    "receptor_candidate_pair_count",
    "receipt_sha256",
    "schema_id",
    "scientifically_validated",
    "score_id",
    "total_score_binary64_hex",
    "torsion_energy_binary64_hex",
    "typed_vdw_binary64_hex",
    "weak_pocket_prior_binary64_hex",
    "desolvation_proxy_binary64_hex",
}
_VALIDITY_RESULT_KEYS = {
    "blockers",
    "checks",
    "claim_safe",
    "complete",
    "evaluated_checks",
    "measurements",
    "not_evaluated_reasons",
    "valid",
    "valid_within_evaluated_scope",
}
_INTERNAL_VALIDITY_KEYS = {
    "authority_input_receipt_sha256",
    "claim_safe",
    "complete",
    "config_fingerprint_sha256",
    "context_fingerprint_sha256",
    "coordinate_sha256",
    "evaluator_implementation_sha256",
    "pose_artifact_sha256",
    "problem_fingerprint_sha256",
    "proposal_fingerprint_sha256",
    "receipt_sha256",
    "required_check_names",
    "required_check_set_sha256",
    "result",
    "schema_id",
    "valid",
}
_POSEBUSTERS_KEYS = {
    "check_results",
    "claim_safe",
    "complete",
    "config_sha256",
    "coordinate_sha256",
    "implementation_sha256",
    "mode",
    "native_pose_artifact_sha256",
    "pose_artifact_sha256",
    "posebusters_version",
    "proposal_fingerprint_sha256",
    "receipt_sha256",
    "receptor_artifact_sha256",
    "report_artifact_sha256",
    "required_check_names",
    "required_check_set_sha256",
    "schema_id",
    "valid",
}
_RMSD_KEYS = {
    "atom_mapping_sha256",
    "claim_safe",
    "complete",
    "config_sha256",
    "coordinate_sha256",
    "implementation_sha256",
    "method_id",
    "native_pose_artifact_sha256",
    "pose_artifact_sha256",
    "proposal_fingerprint_sha256",
    "receipt_sha256",
    "receptor_artifact_sha256",
    "report_artifact_sha256",
    "rmsd_angstrom_binary64_hex",
    "schema_id",
    "symmetry_policy_sha256",
}
_CANDIDATE_KEYS = {
    "candidate_id",
    "candidate_proposal_fingerprint_sha256",
    "coordinate_sha256",
    "exact_valid",
    "internal_pose_validity",
    "pose_artifact_sha256",
    "posebusters",
    "proposal_index",
    "raw_score_binary64_hex",
    "raw_score_rank",
    "receipt_sha256",
    "rmsd",
    "rmsd_angstrom_binary64_hex",
    "schema_id",
    "scorer_v1_terms",
    "source_proposal_fingerprint_sha256",
}
_RANKING_KEYS = {
    "arm",
    "candidate_denominator",
    "candidate_rows_by_proposal_index",
    "claim_safe",
    "raw_rank_order_proposal_indices",
    "raw_rank_order_receipt_sha256",
    "receipt_sha256",
    "schema_id",
    "score_term_semantics_fully_rederivable",
    "scorer_execution_profile",
    "scorer_execution_profile_sha256",
    "top1_candidate_receipt_sha256",
    "top5_candidate_receipt_sha256s",
    "validity_semantics_fully_rederivable",
}
_CASE_SOURCE_KEYS = {
    "allocation_receipt_sha256",
    "authenticated_input_receipt_sha256",
    "case_id",
    "case_source_authority_sha256",
    "claim_safe",
    "cohort_case_ids_sha256",
    "current_v7_candidate_lineage_sha256",
    "historical_archive_full_scorer_terms_available",
    "historical_archive_score_rank_semantics_authorized",
    "input_artifact_set_sha256",
    "member_manifest_membership_verified",
    "native_pose_artifact_sha256",
    "problem_fingerprint_sha256",
    "receipt_sha256",
    "receptor_artifact_sha256",
    "schema_id",
    "source_case_member_path",
    "source_case_member_receipt_sha256",
    "source_case_member_sha256",
    "source_proposal_receipt_sha256",
    "source_v11_archive_sha256",
    "source_v11_bundle_sha256",
    "source_v11_member_manifest_sha256",
    "source_v11_report_sha256",
}
_CURRENT_V7_LINEAGE_KEYS = {
    "allocation_receipt_sha256",
    "authenticated_input_receipt_sha256",
    "candidate_denominator",
    "claim_safe",
    "current_v7_candidate_lineage_rows",
    "current_v7_candidate_lineage_sha256",
    "development_only",
    "full_source_lineage_verified",
    "problem_fingerprint_sha256",
    "receipt_sha256",
    "schema_id",
    "search_space_fingerprint_sha256",
    "source_proposal_receipt_sha256",
    "source_v11_receipts_by_proposal_index",
}
_TARGET_KEYS = {
    "activated_state",
    "baseline_candidate",
    "decision_sha256",
    "policy_sha256",
    "probe_input_sha256",
    "proposal_index",
    "selected_or_retained_candidate",
    "source_snapshot",
    "source_v11_receipt",
    "source_v11_receipt_sha256",
}
_CASE_SUMMARY_KEYS = {
    "case_id",
    "exact_valid_candidate_count",
    "failure_class",
    "invalid_top1",
    "proposal_oracle_recovered",
    "proposal_oracle_rmsd_binary64_hex",
    "selected_candidate_receipt_sha256",
    "top1_exact_valid",
    "top1_recovery",
    "top1_rmsd_binary64_hex",
    "top5_recovery",
    "valid_proposal_oracle_recovered",
    "valid_proposal_oracle_rmsd_binary64_hex",
}


@dataclass(frozen=True)
class VerifiedFullEvidence:
    file_sha256: str
    receipt_sha256: str
    baseline_summary: Mapping[str, Any]
    experimental_summary: Mapping[str, Any]
    cross_arm: Mapping[str, Any]
    case_receipt_sha256s: tuple[str, ...]
    candidate_receipt_sha256s: tuple[str, ...]


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OneShotABAuthorityError("full evidence is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        raise OneShotABAuthorityError(f"{name} key set is invalid")


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OneShotABAuthorityError(f"{name} must be an object")
    return value


def _sequence(value: object, *, count: int | None, name: str) -> list[Any]:
    if not isinstance(value, list) or (count is not None and len(value) != count):
        suffix = "" if count is None else f" with exactly {count} rows"
        raise OneShotABAuthorityError(f"{name} must be an array{suffix}")
    return value


def _digest(value: object, *, name: str) -> str:
    if not _is_sha256(value):
        raise OneShotABAuthorityError(f"{name} must be a lowercase SHA-256")
    return str(value)


def _sha1(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OneShotABAuthorityError(f"{name} must be a lowercase Git SHA-1")
    return value


def _float_from_hex(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
) -> float:
    if not isinstance(value, str):
        raise OneShotABAuthorityError(f"{name} must be binary64 hex")
    try:
        observed = float.fromhex(value)
    except (ValueError, OverflowError) as exc:
        raise OneShotABAuthorityError(f"{name} must be binary64 hex") from exc
    if (
        not math.isfinite(observed)
        or observed.hex() != value
        or (minimum is not None and observed < minimum)
    ):
        raise OneShotABAuthorityError(f"{name} is not canonical finite binary64")
    return observed


def _verify_hash(value: Mapping[str, Any], *, field: str, name: str) -> None:
    verify_self_hash(value, hash_field=field, name=name)


def _parse_backend_receipt(value: object) -> ScorerBackendReceipt:
    row = _mapping(value, name="scorer backend receipt")
    expected = {
        "backend",
        "backend_version",
        "build_flags",
        "cargo_lock_sha256",
        "extension_sha256",
        "implementation_source_sha256",
        "implicit_fallback_allowed",
        "options_fingerprint_sha256",
        "receipt_sha256",
        "rustc_version",
        "schema_id",
        "target_triple",
    }
    _exact_keys(row, expected, name="scorer backend receipt")
    receipt = ScorerBackendReceipt(
        backend=row["backend"],
        backend_version=row["backend_version"],
        implementation_source_sha256=row["implementation_source_sha256"],
        options_fingerprint_sha256=row["options_fingerprint_sha256"],
        extension_sha256=row["extension_sha256"],
        cargo_lock_sha256=row["cargo_lock_sha256"],
        rustc_version=row["rustc_version"],
        target_triple=row["target_triple"],
        build_flags=tuple(
            _sequence(row["build_flags"], count=None, name="build_flags")
        ),
    )
    if (
        row.get("schema_id") != SCORER_V1_BACKEND_RECEIPT_SCHEMA_ID
        or row.get("implicit_fallback_allowed") is not False
        or receipt.backend is not ScorerBackend.RUST_CPU_REQUIRED
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError(
            "scorer backend receipt is not canonical Rust CPU evidence"
        )
    return receipt


def _parse_scorer_terms(value: object) -> ScorerV1Terms:
    row = _mapping(value, name="ScorerV1Terms")
    _exact_keys(row, _SCORER_KEYS, name="ScorerV1Terms")
    terms = {
        name: _float_from_hex(row.get(f"{name}_binary64_hex"), name=name)
        for name in _SCORER_TERM_NAMES
    }
    counts: dict[str, int] = {}
    for name in _SCORER_COUNT_NAMES:
        observed = row.get(name)
        if type(observed) is not int or observed < 0:
            raise OneShotABAuthorityError(
                f"{name} must be a non-negative integer"
            )
        counts[name] = observed
    receipt = ScorerV1Terms(
        proposal_fingerprint_sha256=row["proposal_fingerprint_sha256"],
        authority_input_receipt_sha256=row["authority_input_receipt_sha256"],
        context_fingerprint_sha256=row["context_fingerprint_sha256"],
        config_fingerprint_sha256=row["config_fingerprint_sha256"],
        backend_receipt_sha256=row["backend_receipt_sha256"],
        **terms,
        **counts,
    )
    if (
        row.get("schema_id") != SCORER_V1_TERMS_SCHEMA_ID
        or row.get("score_id") != SCORER_V1_SCORE_ID
        or row.get("calibrated") is not False
        or row.get("scientifically_validated") is not False
        or row.get("claim_safe") is not False
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError(
            "ScorerV1Terms does not independently rederive"
        )
    return receipt


def _parse_validity_result(value: object) -> PoseValidityResult:
    row = _mapping(value, name="internal validity result")
    _exact_keys(row, _VALIDITY_RESULT_KEYS, name="internal validity result")
    result = PoseValidityResult(
        checks=_mapping(row["checks"], name="validity checks"),
        evaluated_checks=_mapping(
            row["evaluated_checks"], name="evaluated checks"
        ),
        complete=row["complete"],
        valid_within_evaluated_scope=row["valid_within_evaluated_scope"],
        measurements=_mapping(
            row["measurements"], name="validity measurements"
        ),
        blockers=tuple(
            _sequence(row["blockers"], count=None, name="validity blockers")
        ),
        not_evaluated_reasons=_mapping(
            row["not_evaluated_reasons"], name="not-evaluated reasons"
        ),
    )
    if result.to_dict() != row:
        raise OneShotABAuthorityError(
            "internal validity result does not rederive"
        )
    return result


def _parse_internal_validity(
    value: object,
) -> SourcePairedClearanceInternalValidityEvidenceV1:
    row = _mapping(value, name="internal validity evidence")
    _exact_keys(row, _INTERNAL_VALIDITY_KEYS, name="internal validity evidence")
    receipt = SourcePairedClearanceInternalValidityEvidenceV1(
        proposal_fingerprint_sha256=row["proposal_fingerprint_sha256"],
        coordinate_sha256=row["coordinate_sha256"],
        pose_artifact_sha256=row["pose_artifact_sha256"],
        authority_input_receipt_sha256=row["authority_input_receipt_sha256"],
        problem_fingerprint_sha256=row["problem_fingerprint_sha256"],
        context_fingerprint_sha256=row["context_fingerprint_sha256"],
        config_fingerprint_sha256=row["config_fingerprint_sha256"],
        evaluator_implementation_sha256=row[
            "evaluator_implementation_sha256"
        ],
        result=_parse_validity_result(row["result"]),
    )
    if (
        row.get("schema_id")
        != SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID
        or row.get("required_check_names")
        != list(INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES)
        or row.get("required_check_set_sha256")
        != _sha256(list(INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES))
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError(
            "internal validity evidence does not rederive"
        )
    return receipt


def _parse_posebusters(
    value: object,
) -> SourcePairedClearancePoseBustersEvidenceV1:
    row = _mapping(value, name="PoseBusters evidence")
    _exact_keys(row, _POSEBUSTERS_KEYS, name="PoseBusters evidence")
    receipt = SourcePairedClearancePoseBustersEvidenceV1(
        implementation_sha256=row["implementation_sha256"],
        config_sha256=row["config_sha256"],
        proposal_fingerprint_sha256=row["proposal_fingerprint_sha256"],
        coordinate_sha256=row["coordinate_sha256"],
        pose_artifact_sha256=row["pose_artifact_sha256"],
        native_pose_artifact_sha256=row["native_pose_artifact_sha256"],
        receptor_artifact_sha256=row["receptor_artifact_sha256"],
        report_artifact_sha256=row["report_artifact_sha256"],
        check_results=_mapping(
            row["check_results"], name="PoseBusters checks"
        ),
        posebusters_version=row["posebusters_version"],
        mode=row["mode"],
        complete=row["complete"],
    )
    if (
        row.get("schema_id")
        != SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID
        or row.get("required_check_names")
        != list(POSEBUSTERS_REQUIRED_CHECK_NAMES)
        or row.get("required_check_set_sha256")
        != POSEBUSTERS_REQUIRED_CHECK_SET_SHA256
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError(
            "PoseBusters evidence does not rederive"
        )
    return receipt


def _parse_rmsd(value: object) -> SourcePairedClearanceRmsdEvidenceV1:
    row = _mapping(value, name="RMSD evidence")
    _exact_keys(row, _RMSD_KEYS, name="RMSD evidence")
    receipt = SourcePairedClearanceRmsdEvidenceV1(
        implementation_sha256=row["implementation_sha256"],
        config_sha256=row["config_sha256"],
        proposal_fingerprint_sha256=row["proposal_fingerprint_sha256"],
        coordinate_sha256=row["coordinate_sha256"],
        pose_artifact_sha256=row["pose_artifact_sha256"],
        native_pose_artifact_sha256=row["native_pose_artifact_sha256"],
        receptor_artifact_sha256=row["receptor_artifact_sha256"],
        atom_mapping_sha256=row["atom_mapping_sha256"],
        symmetry_policy_sha256=row["symmetry_policy_sha256"],
        report_artifact_sha256=row["report_artifact_sha256"],
        rmsd_angstrom=_float_from_hex(
            row["rmsd_angstrom_binary64_hex"],
            name="rmsd_angstrom",
            minimum=0.0,
        ),
        method_id=row["method_id"],
        complete=row["complete"],
    )
    if (
        row.get("schema_id")
        != SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError("RMSD evidence does not rederive")
    return receipt


def _parse_candidate(
    value: object,
) -> SourcePairedClearanceCandidateEvidenceV1:
    row = _mapping(value, name="candidate evidence")
    _exact_keys(row, _CANDIDATE_KEYS, name="candidate evidence")
    receipt = SourcePairedClearanceCandidateEvidenceV1(
        candidate_id=row["candidate_id"],
        proposal_index=row["proposal_index"],
        candidate_proposal_fingerprint_sha256=row[
            "candidate_proposal_fingerprint_sha256"
        ],
        source_proposal_fingerprint_sha256=row[
            "source_proposal_fingerprint_sha256"
        ],
        coordinate_sha256=row["coordinate_sha256"],
        pose_artifact_sha256=row["pose_artifact_sha256"],
        scorer_terms=_parse_scorer_terms(row["scorer_v1_terms"]),
        internal_validity=_parse_internal_validity(
            row["internal_pose_validity"]
        ),
        posebusters=_parse_posebusters(row["posebusters"]),
        rmsd=_parse_rmsd(row["rmsd"]),
        raw_score_rank=row["raw_score_rank"],
    )
    if (
        row.get("schema_id")
        != SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID
        or row.get("raw_score_binary64_hex")
        != receipt.scorer_terms.total_score.hex()
        or row.get("rmsd_angstrom_binary64_hex")
        != receipt.rmsd.rmsd_angstrom.hex()
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError(
            "candidate evidence does not independently rederive"
        )
    return receipt


def _parse_ranking(
    value: object,
    *,
    expected_arm: str,
) -> SourcePairedClearanceArmRankingReceiptV1:
    row = _mapping(value, name=f"{expected_arm} ranking")
    _exact_keys(row, _RANKING_KEYS, name=f"{expected_arm} ranking")
    candidates = tuple(
        _parse_candidate(item)
        for item in _sequence(
            row["candidate_rows_by_proposal_index"],
            count=SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR,
            name=f"{expected_arm} candidate rows",
        )
    )
    receipt = SourcePairedClearanceArmRankingReceiptV1(
        arm=row["arm"],
        candidate_rows=candidates,
    )
    if (
        row.get("schema_id")
        != SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID
        or row.get("arm") != expected_arm
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError(
            f"{expected_arm} ranking does not rederive"
        )
    return receipt


def _parse_case_source(
    value: object,
) -> SourcePairedClearanceCaseSourceReceiptV1:
    row = _mapping(value, name="case source receipt")
    _exact_keys(row, _CASE_SOURCE_KEYS, name="case source receipt")
    receipt = SourcePairedClearanceCaseSourceReceiptV1(
        case_id=row["case_id"],
        source_case_member_path=row["source_case_member_path"],
        source_case_member_sha256=row["source_case_member_sha256"],
        source_case_member_receipt_sha256=row[
            "source_case_member_receipt_sha256"
        ],
        authenticated_input_receipt_sha256=row[
            "authenticated_input_receipt_sha256"
        ],
        problem_fingerprint_sha256=row["problem_fingerprint_sha256"],
        source_proposal_receipt_sha256=row[
            "source_proposal_receipt_sha256"
        ],
        allocation_receipt_sha256=row["allocation_receipt_sha256"],
        native_pose_artifact_sha256=row["native_pose_artifact_sha256"],
        receptor_artifact_sha256=row["receptor_artifact_sha256"],
        input_artifact_set_sha256=row["input_artifact_set_sha256"],
        current_v7_candidate_lineage_sha256=row[
            "current_v7_candidate_lineage_sha256"
        ],
        source_v11_archive_sha256=row["source_v11_archive_sha256"],
        source_v11_member_manifest_sha256=row[
            "source_v11_member_manifest_sha256"
        ],
        source_v11_bundle_sha256=row["source_v11_bundle_sha256"],
        source_v11_report_sha256=row["source_v11_report_sha256"],
        cohort_case_ids_sha256=row["cohort_case_ids_sha256"],
    )
    if (
        row.get("schema_id")
        != SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID
        or receipt.to_dict() != row
    ):
        raise OneShotABAuthorityError(
            "case source receipt does not rederive"
        )
    return receipt


def _scientific_projection(
    candidate: SourcePairedClearanceCandidateEvidenceV1,
) -> dict[str, object]:
    row = candidate.to_dict()
    return {
        key: value
        for key, value in row.items()
        if key not in {"raw_score_rank", "receipt_sha256", "schema_id"}
    }


def _derive_case_summary(
    case_id: str,
    ranking: SourcePairedClearanceArmRankingReceiptV1,
) -> dict[str, Any]:
    ranked = ranking.ranked_rows
    all_rows = tuple(ranking.candidate_rows)
    proposal_oracle = min(row.rmsd.rmsd_angstrom for row in all_rows)
    valid_rows = tuple(
        row
        for row in all_rows
        if row.internal_validity.valid and row.posebusters.valid
    )
    valid_oracle = (
        min(row.rmsd.rmsd_angstrom for row in valid_rows)
        if valid_rows
        else None
    )
    top1 = ranked[0]
    top5 = ranked[:5]
    proposal_recovered = proposal_oracle <= 2.0
    valid_recovered = valid_oracle is not None and valid_oracle <= 2.0
    if top1.exact_valid:
        failure_class = "success"
    elif not proposal_recovered:
        failure_class = "proposal_failure"
    elif not valid_recovered:
        failure_class = "validity_failure"
    else:
        failure_class = "ranking_failure"
    summary: dict[str, Any] = {
        "case_id": case_id,
        "proposal_oracle_rmsd_binary64_hex": proposal_oracle.hex(),
        "valid_proposal_oracle_rmsd_binary64_hex": (
            "" if valid_oracle is None else valid_oracle.hex()
        ),
        "top1_rmsd_binary64_hex": top1.rmsd.rmsd_angstrom.hex(),
        "proposal_oracle_recovered": proposal_recovered,
        "valid_proposal_oracle_recovered": bool(valid_recovered),
        "top1_recovery": top1.rmsd.rmsd_angstrom <= 2.0,
        "top5_recovery": any(
            row.rmsd.rmsd_angstrom <= 2.0 for row in top5
        ),
        "top1_exact_valid": top1.exact_valid,
        "invalid_top1": not (
            top1.internal_validity.valid and top1.posebusters.valid
        ),
        "exact_valid_candidate_count": sum(row.exact_valid for row in all_rows),
        "selected_candidate_receipt_sha256": top1.receipt_sha256,
        "failure_class": failure_class,
    }
    _exact_keys(summary, _CASE_SUMMARY_KEYS, name="derived case summary")
    return summary


def _arm_projection(
    *,
    profile_id: str,
    summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_case = {str(row["case_id"]): row for row in summaries}
    if tuple(by_case) != SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS:
        raise OneShotABAuthorityError("case summary order or coverage drifted")
    return {
        "schema_id": (
            "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_arm/1.0.0"
        ),
        "profile_id": profile_id,
        "scored_case_count": 8,
        "candidate_count": 512,
        "candidate_receipt_count": 512,
        "candidate_denominator_verified": True,
        "complete_scorer_v1_terms_verified": True,
        "preparation_failure_case_ids": list(_PREPARATION_FAILURE_CASE_IDS),
        "top1_recovery_case_ids": sorted(
            case_id
            for case_id, row in by_case.items()
            if row["top1_recovery"]
        ),
        "top5_recovery_case_ids": sorted(
            case_id
            for case_id, row in by_case.items()
            if row["top5_recovery"]
        ),
        "exact_valid_case_ids": sorted(
            case_id
            for case_id, row in by_case.items()
            if row["top1_exact_valid"]
        ),
        "proposal_oracle_case_ids": sorted(
            case_id
            for case_id, row in by_case.items()
            if row["proposal_oracle_recovered"]
        ),
        "invalid_top1_case_ids": sorted(
            case_id
            for case_id, row in by_case.items()
            if row["invalid_top1"]
        ),
    }


def _non_target_projection(
    case_source: SourcePairedClearanceCaseSourceReceiptV1,
    baseline: SourcePairedClearanceCandidateEvidenceV1,
    experimental: SourcePairedClearanceCandidateEvidenceV1,
) -> dict[str, object]:
    if (
        baseline.candidate_id != experimental.candidate_id
        or baseline.proposal_index != experimental.proposal_index
        or baseline.source_proposal_fingerprint_sha256
        != experimental.source_proposal_fingerprint_sha256
    ):
        raise OneShotABAuthorityError("cross-arm slot identity is cross-wired")
    fields = (
        "authority_input_receipt_sha256",
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "backend_receipt_sha256",
    )
    scorer = {}
    for name in fields:
        left = getattr(baseline.scorer_terms, name)
        right = getattr(experimental.scorer_terms, name)
        if left != right:
            raise OneShotABAuthorityError("cross-arm scorer authority differs")
        scorer[name] = left
    validity = {}
    for name in (
        "authority_input_receipt_sha256",
        "problem_fingerprint_sha256",
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "evaluator_implementation_sha256",
    ):
        left = getattr(baseline.internal_validity, name)
        right = getattr(experimental.internal_validity, name)
        if left != right:
            raise OneShotABAuthorityError("cross-arm validity authority differs")
        validity[name] = left
    posebusters = {}
    for name in (
        "implementation_sha256",
        "config_sha256",
        "native_pose_artifact_sha256",
        "receptor_artifact_sha256",
        "posebusters_version",
        "mode",
    ):
        left = getattr(baseline.posebusters, name)
        right = getattr(experimental.posebusters, name)
        if left != right:
            raise OneShotABAuthorityError(
                "cross-arm PoseBusters authority differs"
            )
        posebusters[name] = left
    rmsd = {}
    for name in (
        "implementation_sha256",
        "config_sha256",
        "native_pose_artifact_sha256",
        "receptor_artifact_sha256",
        "atom_mapping_sha256",
        "symmetry_policy_sha256",
        "method_id",
    ):
        left = getattr(baseline.rmsd, name)
        right = getattr(experimental.rmsd, name)
        if left != right:
            raise OneShotABAuthorityError("cross-arm RMSD authority differs")
        rmsd[name] = left
    if (
        scorer["authority_input_receipt_sha256"]
        != case_source.authenticated_input_receipt_sha256
        or validity["authority_input_receipt_sha256"]
        != case_source.authenticated_input_receipt_sha256
        or validity["problem_fingerprint_sha256"]
        != case_source.problem_fingerprint_sha256
        or posebusters["native_pose_artifact_sha256"]
        != case_source.native_pose_artifact_sha256
        or posebusters["receptor_artifact_sha256"]
        != case_source.receptor_artifact_sha256
        or rmsd["native_pose_artifact_sha256"]
        != case_source.native_pose_artifact_sha256
        or rmsd["receptor_artifact_sha256"]
        != case_source.receptor_artifact_sha256
    ):
        raise OneShotABAuthorityError(
            "candidate authority is not bound to its case source"
        )
    return {
        "case_source_receipt_sha256": case_source.receipt_sha256,
        "candidate_id": baseline.candidate_id,
        "proposal_index": baseline.proposal_index,
        "source_proposal_fingerprint_sha256": (
            baseline.source_proposal_fingerprint_sha256
        ),
        "scorer_authority": scorer,
        "validity_authority": validity,
        "posebusters_authority": posebusters,
        "rmsd_authority": rmsd,
    }


def _verify_generic_self_hash(
    value: object,
    *,
    field: str,
    schema_id: str | None,
    name: str,
) -> dict[str, Any]:
    row = _mapping(value, name=name)
    _verify_hash(row, field=field, name=name)
    if schema_id is not None and row.get("schema_id") != schema_id:
        raise OneShotABAuthorityError(f"{name} schema is invalid")
    return row


def _verify_selection_receipt(
    value: object,
) -> tuple[
    str,
    str,
    SourcePairedClearanceCaseSourceReceiptV1,
    SourcePairedClearanceArmRankingReceiptV1,
    SourcePairedClearanceArmRankingReceiptV1,
    dict[str, Any],
    dict[str, Any],
    tuple[dict[str, Any], ...],
    str,
    int,
    int,
]:
    row = _mapping(value, name="case activation receipt")
    _exact_keys(row, _SELECTION_RECEIPT_KEYS, name="case activation receipt")
    _verify_hash(row, field="receipt_sha256", name="case activation receipt")
    if (
        row.get("schema_id")
        != SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID
    ):
        raise OneShotABAuthorityError(
            "case activation receipt schema is invalid"
        )
    for key in (
        "full_scoring_and_validity_evidence",
        "full_source_proposal_lineage_verified",
        "full_current_v7_candidate_lineage_verified",
        "full_posebusters_check_set_verified",
        "authenticated_rmsd_receipts_verified",
        "score_term_semantics_fully_rederivable",
        "top1_top5_semantics_fully_rederivable",
        "decision_sealed_before_score_rank_validity",
    ):
        if row.get(key) is not True:
            raise OneShotABAuthorityError(f"{key} must remain true")
    for key in (
        "historical_ab_execution_authorized",
        "fresh_holdout_execution_authorized",
        "product_or_claim_authority",
    ):
        if row.get(key) is not False:
            raise OneShotABAuthorityError(f"{key} must remain false")

    case_source = _parse_case_source(row["case_source"])
    case_id = case_source.case_id
    if row.get("case_id") != case_id:
        raise OneShotABAuthorityError(
            "case activation receipt case_id is cross-wired"
        )

    proposal = _verify_generic_self_hash(
        row["source_proposal_receipt"],
        field="receipt_sha256",
        schema_id=SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID,
        name="source proposal receipt",
    )
    if (
        row.get("source_proposal_receipt_sha256")
        != proposal["receipt_sha256"]
        or case_source.source_proposal_receipt_sha256
        != proposal["receipt_sha256"]
    ):
        raise OneShotABAuthorityError(
            "source proposal receipt identity is cross-wired"
        )
    slots = _sequence(
        proposal.get("candidate_slots"),
        count=SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR,
        name="source proposal candidate slots",
    )

    lineage = _verify_generic_self_hash(
        row["current_v7_lineage"],
        field="receipt_sha256",
        schema_id=SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID,
        name="current-V7 lineage",
    )
    _exact_keys(lineage, _CURRENT_V7_LINEAGE_KEYS, name="current-V7 lineage")
    lineage_rows = _sequence(
        lineage["current_v7_candidate_lineage_rows"],
        count=SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR,
        name="current-V7 lineage rows",
    )
    lineage_identity = _sha256(lineage_rows)
    if (
        lineage.get("candidate_denominator")
        != SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
        or lineage.get("source_proposal_receipt_sha256")
        != proposal["receipt_sha256"]
        or lineage.get("authenticated_input_receipt_sha256")
        != case_source.authenticated_input_receipt_sha256
        or lineage.get("allocation_receipt_sha256")
        != case_source.allocation_receipt_sha256
        or lineage.get("problem_fingerprint_sha256")
        != case_source.problem_fingerprint_sha256
        or lineage.get("current_v7_candidate_lineage_sha256")
        != lineage_identity
        or row.get("current_v7_candidate_lineage_sha256")
        != lineage_identity
        or case_source.current_v7_candidate_lineage_sha256
        != lineage_identity
        or lineage.get("full_source_lineage_verified") is not True
        or lineage.get("development_only") is not True
        or lineage.get("claim_safe") is not False
    ):
        raise OneShotABAuthorityError("current-V7 lineage is cross-wired")

    allocation = _mapping(row["allocation_receipt"], name="allocation receipt")
    _verify_hash(
        allocation,
        field="allocation_sha256",
        name="allocation receipt",
    )
    if (
        row.get("allocation_receipt_sha256")
        != allocation["allocation_sha256"]
        or allocation["allocation_sha256"]
        != case_source.allocation_receipt_sha256
    ):
        raise OneShotABAuthorityError(
            "allocation receipt identity is cross-wired"
        )

    baseline = _parse_ranking(
        row["baseline_arm_ranking"], expected_arm="baseline_current_v7"
    )
    experimental = _parse_ranking(
        row["experimental_arm_ranking"],
        expected_arm="experimental_clearance_shadow",
    )
    backend_sha = baseline.candidate_rows[0].scorer_terms.backend_receipt_sha256
    if any(
        candidate.scorer_terms.backend_receipt_sha256 != backend_sha
        for candidate in (*baseline.candidate_rows, *experimental.candidate_rows)
    ):
        raise OneShotABAuthorityError(
            "candidate rows use multiple scorer backends"
        )

    for index, (slot, lineage_row, base, exp) in enumerate(
        zip(
            slots,
            lineage_rows,
            baseline.candidate_rows,
            experimental.candidate_rows,
            strict=True,
        )
    ):
        slot_map = _mapping(slot, name=f"source slot {index}")
        lineage_map = _mapping(lineage_row, name=f"lineage row {index}")
        if (
            slot_map.get("proposal_index") != index
            or lineage_map.get("proposal_index") != index
            or base.proposal_index != index
            or exp.proposal_index != index
            or base.candidate_id != slot_map.get("candidate_id")
            or exp.candidate_id != slot_map.get("candidate_id")
            or base.source_proposal_fingerprint_sha256
            != slot_map.get("proposal_fingerprint_sha256")
            or exp.source_proposal_fingerprint_sha256
            != slot_map.get("proposal_fingerprint_sha256")
            or lineage_map.get("source_proposal_fingerprint_sha256")
            != slot_map.get("proposal_fingerprint_sha256")
            or lineage_map.get(
                "current_v7_candidate_proposal_fingerprint_sha256"
            )
            != base.candidate_proposal_fingerprint_sha256
            or lineage_map.get("current_v7_coordinate_sha256")
            != base.coordinate_sha256
        ):
            raise OneShotABAuthorityError(
                f"candidate slot {index} is cross-wired"
            )
        _non_target_projection(case_source, base, exp)

    targets = _sequence(
        row["activation_targets"],
        count=row.get("activation_target_count"),
        name="activation targets",
    )
    selected_indices = tuple(
        _sequence(
            row["selected_replacement_proposal_indices"],
            count=None,
            name="selected replacement indices",
        )
    )
    if (
        len(set(selected_indices)) != len(selected_indices)
        or tuple(sorted(selected_indices)) != selected_indices
    ):
        raise OneShotABAuthorityError(
            "selected replacement indices are invalid"
        )
    target_by_index: dict[int, dict[str, Any]] = {}
    changed_rows: list[dict[str, Any]] = []
    shadow_eligible_count = 0
    penetrating_without_validity_change_count = 0
    for target in targets:
        target_map = _mapping(target, name="activation target")
        _exact_keys(target_map, _TARGET_KEYS, name="activation target")
        index = target_map.get("proposal_index")
        if (
            type(index) is not int
            or not 0 <= index < SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
            or index in target_by_index
        ):
            raise OneShotABAuthorityError(
                "activation target proposal_index is invalid"
            )
        snapshot = _verify_generic_self_hash(
            target_map["source_snapshot"],
            field="snapshot_sha256",
            schema_id=SOURCE_PAIRED_CLEARANCE_ACTIVATION_SNAPSHOT_SCHEMA_ID,
            name="activation snapshot",
        )
        state = _verify_generic_self_hash(
            target_map["activated_state"],
            field="state_sha256",
            schema_id=SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
            name="activated state",
        )
        source_v11 = _mapping(
            target_map["source_v11_receipt"], name="source V1.1 receipt"
        )
        _verify_hash(
            source_v11,
            field="receipt_sha256",
            name="source V1.1 receipt",
        )
        base = baseline.candidate_rows[index]
        exp = experimental.candidate_rows[index]
        duplicate_base = _parse_candidate(target_map["baseline_candidate"])
        duplicate_exp = _parse_candidate(
            target_map["selected_or_retained_candidate"]
        )
        if (
            duplicate_base.to_dict() != base.to_dict()
            or duplicate_exp.to_dict() != exp.to_dict()
            or target_map.get("source_v11_receipt_sha256")
            != source_v11.get("receipt_sha256")
            or snapshot.get("source_v11_receipt_sha256")
            != source_v11.get("receipt_sha256")
            or state.get("source_v11_receipt_sha256")
            != source_v11.get("receipt_sha256")
            or snapshot.get("proposal_index") != index
            or state.get("proposal_index") != index
            or state.get("source_snapshot_sha256")
            != snapshot.get("snapshot_sha256")
            or target_map.get("policy_sha256") != state.get("policy_sha256")
            or target_map.get("probe_input_sha256")
            != state.get("probe_input_sha256")
            or target_map.get("decision_sha256")
            != state.get("decision_sha256")
        ):
            raise OneShotABAuthorityError(
                "activation target receipts are cross-wired"
            )
        state_boundary = {
            "decision_sealed_before_scoring": True,
            "score_rank_rmsd_posebusters_native_or_case_identity_used": False,
            "result_dependent_allocation": False,
            "default_v7_output_changed": False,
            "historical_ab_execution_authorized": False,
            "historical_result_materialization_authorized": False,
            "generic_runner_cli_wired": False,
            "product_path_wired": False,
            "fresh_execution_authorized": False,
            "customer_pose_emission_authorized": False,
            "stage0_eligible": False,
            "public_or_scientific_claim_authorized": False,
            "development_only": True,
            "claim_safe": False,
        }
        if any(
            state.get(name) is not expected
            for name, expected in state_boundary.items()
        ):
            raise OneShotABAuthorityError(
                "activated state exceeds the frozen evidence-only authority"
            )
        if (
            snapshot.get("result_dependent_allocation") is not False
            or snapshot.get("default_v7_output_changed") is not False
            or snapshot.get("fresh_execution_authorized") is not False
            or snapshot.get("stage0_eligible") is not False
            or snapshot.get("development_only") is not True
            or snapshot.get("claim_safe") is not False
        ):
            raise OneShotABAuthorityError(
                "activation snapshot exceeds the frozen development boundary"
            )
        selection_applied = state.get("selection_applied")
        shadow_eligible = state.get("shadow_selection_eligible")
        if type(selection_applied) is not bool or type(shadow_eligible) is not bool:
            raise OneShotABAuthorityError(
                "activation selection flags are invalid"
            )
        if shadow_eligible:
            shadow_eligible_count += 1
        changed = _scientific_projection(base) != _scientific_projection(exp)
        if selection_applied:
            if (
                state.get("shadow_selection_eligible") is not True
                or not changed
                or index not in selected_indices
            ):
                raise OneShotABAuthorityError(
                    "selected target replacement is invalid"
                )
            changed_rows.append(
                {
                    "case_id": case_id,
                    "proposal_index": index,
                    "baseline_candidate_receipt_sha256": base.receipt_sha256,
                    "experimental_candidate_receipt_sha256": exp.receipt_sha256,
                    "non_target_projection_sha256": _sha256(
                        _non_target_projection(case_source, base, exp)
                    ),
                }
            )
            baseline_clash = (
                base.internal_validity.result.checks.get(
                    "receptor_ligand_clash_free"
                )
                is False
            )
            experimental_clash = (
                exp.internal_validity.result.checks.get(
                    "receptor_ligand_clash_free"
                )
                is False
            )
            if (
                baseline_clash
                and experimental_clash
                and base.posebusters.valid == exp.posebusters.valid
            ):
                penetrating_without_validity_change_count += 1
        elif changed or index in selected_indices:
            raise OneShotABAuthorityError(
                "retained target changed scientific evidence"
            )
        target_by_index[index] = target_map

    if set(selected_indices) != {
        int(item["proposal_index"]) for item in changed_rows
    }:
        raise OneShotABAuthorityError(
            "selected replacement roster is not rederived"
        )
    for index, (base, exp) in enumerate(
        zip(
            baseline.candidate_rows,
            experimental.candidate_rows,
            strict=True,
        )
    ):
        changed = _scientific_projection(base) != _scientific_projection(exp)
        if index not in target_by_index and changed:
            raise OneShotABAuthorityError(
                "experimental arm changed a non-target slot"
            )

    baseline_summary = _derive_case_summary(case_id, baseline)
    experimental_summary = _derive_case_summary(case_id, experimental)
    return (
        case_id,
        str(row["receipt_sha256"]),
        case_source,
        baseline,
        experimental,
        baseline_summary,
        experimental_summary,
        tuple(changed_rows),
        backend_sha,
        shadow_eligible_count,
        penetrating_without_validity_change_count,
    )


def _run_bindings(run_start: Mapping[str, Any]) -> dict[str, object]:
    receipt = _digest(
        run_start.get("receipt_sha256"), name="run-start receipt"
    )
    source = _sha1(
        run_start.get("source_commit_git_sha1"), name="source commit"
    )
    environment = _digest(
        run_start.get("execution_environment_sha256"),
        name="execution environment",
    )
    if (
        run_start.get("required_scorer_backend", _REQUIRED_BACKEND)
        != _REQUIRED_BACKEND
    ):
        raise OneShotABAuthorityError("run-start scorer backend is invalid")
    return {
        "run_start_receipt_sha256": receipt,
        "source_commit_git_sha1": source,
        "execution_environment_sha256": environment,
    }


def build_full_evidence_bundle(
    *,
    run_start: Mapping[str, Any],
    scorer_backend_receipt: Mapping[str, Any],
    case_activation_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    bindings = _run_bindings(run_start)
    backend = _parse_backend_receipt(scorer_backend_receipt)
    receipts = list(case_activation_receipts)
    if len(receipts) != 8:
        raise OneShotABAuthorityError(
            "full evidence requires eight case receipts"
        )
    baseline_summaries = []
    experimental_summaries = []
    changed_rows: list[dict[str, Any]] = []
    observed_case_ids = []
    shadow_eligible_count = 0
    penetrating_without_validity_change_count = 0
    for value in receipts:
        (
            case_id,
            _,
            _,
            _,
            _,
            baseline_summary,
            experimental_summary,
            case_changed,
            backend_sha,
            case_shadow_eligible,
            case_penetrating_without_change,
        ) = _verify_selection_receipt(value)
        if backend_sha != backend.receipt_sha256:
            raise OneShotABAuthorityError(
                "candidate rows are cross-wired to another scorer backend receipt"
            )
        observed_case_ids.append(case_id)
        baseline_summaries.append(baseline_summary)
        experimental_summaries.append(experimental_summary)
        changed_rows.extend(case_changed)
        shadow_eligible_count += case_shadow_eligible
        penetrating_without_validity_change_count += (
            case_penetrating_without_change
        )
    if tuple(observed_case_ids) != SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS:
        raise OneShotABAuthorityError(
            "full evidence case order or coverage is invalid"
        )

    baseline_projection = _arm_projection(
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
        summaries=baseline_summaries,
    )
    experimental_projection = _arm_projection(
        profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
        summaries=experimental_summaries,
    )
    changed_receipts = []
    for row in changed_rows:
        changed = dict(row)
        changed["receipt_sha256"] = _sha256(changed)
        changed_receipts.append(changed)
    cross_projection = {
        "source_control_preserved": True,
        "result_dependent_allocation_observed": False,
        "shadow_eligible_candidate_count": shadow_eligible_count,
        "selected_penetrating_without_validity_change_count": (
            penetrating_without_validity_change_count
        ),
        "changed_slot_count": len(changed_receipts),
        "changed_slots_sha256": _sha256(
            [row["receipt_sha256"] for row in changed_receipts]
        ),
        "changed_slot_rows": changed_receipts,
    }
    case_rows: list[dict[str, Any]] = []
    for case_id, receipt in zip(observed_case_ids, receipts, strict=True):
        selection_sha256 = _digest(
            receipt.get("receipt_sha256"),
            name=f"{case_id} selection activation receipt",
        )
        case_row: dict[str, Any] = {
            "schema_id": FULL_CASE_EVIDENCE_SCHEMA_ID,
            "case_id": case_id,
            **bindings,
            "policy_sha256": EXPECTED_POLICY_SHA256,
            "activation_policy_sha256": EXPECTED_ACTIVATION_POLICY_SHA256,
            "scorer_backend_receipt_sha256": backend.receipt_sha256,
            "selection_activation_receipt": receipt,
            "selection_activation_receipt_sha256": selection_sha256,
        }
        case_row["receipt_sha256"] = _sha256(case_row)
        case_rows.append(case_row)

    bundle: dict[str, Any] = {
        "schema_id": FULL_EVIDENCE_BUNDLE_SCHEMA_ID,
        "policy_sha256": EXPECTED_POLICY_SHA256,
        "activation_policy_sha256": EXPECTED_ACTIVATION_POLICY_SHA256,
        **bindings,
        "required_scorer_backend": _REQUIRED_BACKEND,
        "scorer_backend_receipt": backend.to_dict(),
        "case_evidence_rows": case_rows,
        "baseline_arm_summary_projection": baseline_projection,
        "experimental_arm_summary_projection": experimental_projection,
        "cross_arm_projection": cross_projection,
        "authority": {key: False for key in _AUTHORITY_KEYS},
    }
    bundle["receipt_sha256"] = _sha256(bundle)
    return bundle


def _read_pinned_regular_file(path: Path) -> bytes:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise OneShotABAuthorityError(
            f"full evidence cannot be opened safely: {exc}"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OneShotABAuthorityError(
                "full evidence must be a regular file"
            )
        if before.st_size <= 0 or before.st_size > MAX_FULL_EVIDENCE_BYTES:
            raise OneShotABAuthorityError(
                "full evidence size is outside the bounded envelope"
            )
        chunks = []
        observed_size = 0
        while True:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, MAX_FULL_EVIDENCE_BYTES + 1),
            )
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > MAX_FULL_EVIDENCE_BYTES:
                raise OneShotABAuthorityError(
                    "full evidence exceeds the bounded envelope"
                )
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    if identity_before != identity_after or observed_size != before.st_size:
        raise OneShotABAuthorityError(
            "full evidence changed while being read"
        )
    return b"".join(chunks)


def _verify_full_evidence_file_impl(
    path: Path,
    *,
    run_start: Mapping[str, Any],
) -> VerifiedFullEvidence:
    raw = _read_pinned_regular_file(path)
    file_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        bundle = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OneShotABAuthorityError(
            "full evidence is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(bundle, dict):
        raise OneShotABAuthorityError(
            "full evidence must be a JSON object"
        )
    _exact_keys(bundle, _BUNDLE_KEYS, name="full evidence bundle")
    _verify_hash(bundle, field="receipt_sha256", name="full evidence bundle")
    if (
        bundle.get("schema_id") != FULL_EVIDENCE_BUNDLE_SCHEMA_ID
        or bundle.get("policy_sha256") != EXPECTED_POLICY_SHA256
        or bundle.get("activation_policy_sha256")
        != EXPECTED_ACTIVATION_POLICY_SHA256
        or bundle.get("required_scorer_backend") != _REQUIRED_BACKEND
    ):
        raise OneShotABAuthorityError(
            "full evidence frozen identity is invalid"
        )
    for field, expected in _run_bindings(run_start).items():
        if bundle.get(field) != expected:
            raise OneShotABAuthorityError(
                f"full evidence {field} is cross-wired"
            )
    authority = _mapping(
        bundle.get("authority"), name="full evidence authority"
    )
    if set(authority) != set(_AUTHORITY_KEYS) or any(
        authority.get(key) is not False for key in _AUTHORITY_KEYS
    ):
        raise OneShotABAuthorityError(
            "full evidence authority escalation detected"
        )

    backend = _parse_backend_receipt(bundle.get("scorer_backend_receipt"))
    case_rows = _sequence(
        bundle.get("case_evidence_rows"),
        count=8,
        name="full case evidence rows",
    )
    receipts: list[dict[str, Any]] = []
    expected_bindings = _run_bindings(run_start)
    for expected_case_id, value in zip(
        SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
        case_rows,
        strict=True,
    ):
        case_row = _mapping(value, name="full case evidence row")
        _exact_keys(
            case_row,
            _CASE_EVIDENCE_KEYS,
            name="full case evidence row",
        )
        _verify_hash(
            case_row,
            field="receipt_sha256",
            name="full case evidence row",
        )
        if (
            case_row.get("schema_id") != FULL_CASE_EVIDENCE_SCHEMA_ID
            or case_row.get("case_id") != expected_case_id
            or case_row.get("policy_sha256") != EXPECTED_POLICY_SHA256
            or case_row.get("activation_policy_sha256")
            != EXPECTED_ACTIVATION_POLICY_SHA256
            or case_row.get("scorer_backend_receipt_sha256")
            != backend.receipt_sha256
        ):
            raise OneShotABAuthorityError(
                "full case evidence identity is invalid"
            )
        for field, expected in expected_bindings.items():
            if case_row.get(field) != expected:
                raise OneShotABAuthorityError(
                    f"full case evidence {field} is cross-wired"
                )
        selection = _mapping(
            case_row.get("selection_activation_receipt"),
            name="selection activation receipt",
        )
        if (
            case_row.get("selection_activation_receipt_sha256")
            != selection.get("receipt_sha256")
            or selection.get("case_id") != expected_case_id
        ):
            raise OneShotABAuthorityError(
                "full case evidence selection receipt is cross-wired"
            )
        receipts.append(selection)
    rebuilt = build_full_evidence_bundle(
        run_start=run_start,
        scorer_backend_receipt=backend.to_dict(),
        case_activation_receipts=receipts,
    )
    if rebuilt != bundle:
        raise OneShotABAuthorityError(
            "full evidence summaries or cross-arm metrics do not independently rederive"
        )
    baseline_projection = dict(bundle["baseline_arm_summary_projection"])
    experimental_projection = dict(
        bundle["experimental_arm_summary_projection"]
    )
    baseline_summary = build_arm_summary(
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
        preparation_failure_case_ids=tuple(
            baseline_projection["preparation_failure_case_ids"]
        ),
        top1_recovery_case_ids=tuple(
            baseline_projection["top1_recovery_case_ids"]
        ),
        top5_recovery_case_ids=tuple(
            baseline_projection["top5_recovery_case_ids"]
        ),
        exact_valid_case_ids=tuple(
            baseline_projection["exact_valid_case_ids"]
        ),
        proposal_oracle_case_ids=tuple(
            baseline_projection["proposal_oracle_case_ids"]
        ),
        invalid_top1_case_ids=tuple(
            baseline_projection["invalid_top1_case_ids"]
        ),
        arm_evidence_file_sha256=file_sha256,
        arm_evidence_self_sha256=str(bundle["receipt_sha256"]),
    )
    experimental_summary = build_arm_summary(
        profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
        preparation_failure_case_ids=tuple(
            experimental_projection["preparation_failure_case_ids"]
        ),
        top1_recovery_case_ids=tuple(
            experimental_projection["top1_recovery_case_ids"]
        ),
        top5_recovery_case_ids=tuple(
            experimental_projection["top5_recovery_case_ids"]
        ),
        exact_valid_case_ids=tuple(
            experimental_projection["exact_valid_case_ids"]
        ),
        proposal_oracle_case_ids=tuple(
            experimental_projection["proposal_oracle_case_ids"]
        ),
        invalid_top1_case_ids=tuple(
            experimental_projection["invalid_top1_case_ids"]
        ),
        arm_evidence_file_sha256=file_sha256,
        arm_evidence_self_sha256=str(bundle["receipt_sha256"]),
    )
    cross = dict(bundle["cross_arm_projection"])
    cross.pop("changed_slot_rows", None)
    cross["cross_arm_evidence_sha256"] = file_sha256

    case_hashes = []
    candidate_hashes = []
    arm_candidate_hashes: dict[str, list[str]] = {
        "baseline_arm_ranking": [],
        "experimental_arm_ranking": [],
    }
    for receipt in receipts:
        row = _mapping(receipt, name="case activation receipt")
        case_hashes.append(
            _digest(row.get("receipt_sha256"), name="case receipt")
        )
        for arm_name in arm_candidate_hashes:
            ranking = _mapping(row.get(arm_name), name=arm_name)
            for candidate in _sequence(
                ranking.get("candidate_rows_by_proposal_index"),
                count=64,
                name=f"{arm_name} candidates",
            ):
                identity = _digest(
                    _mapping(candidate, name="candidate").get(
                        "receipt_sha256"
                    ),
                    name="candidate receipt",
                )
                arm_candidate_hashes[arm_name].append(identity)
                candidate_hashes.append(identity)
    if len(set(case_hashes)) != 8 or any(
        len(set(rows)) != 512
        for rows in arm_candidate_hashes.values()
    ):
        raise OneShotABAuthorityError(
            "full evidence contains duplicate case or within-arm candidate receipts"
        )
    return VerifiedFullEvidence(
        file_sha256=file_sha256,
        receipt_sha256=str(bundle["receipt_sha256"]),
        baseline_summary=baseline_summary,
        experimental_summary=experimental_summary,
        cross_arm=cross,
        case_receipt_sha256s=tuple(case_hashes),
        candidate_receipt_sha256s=tuple(candidate_hashes),
    )


def verify_full_evidence_file(
    path: Path,
    *,
    run_start: Mapping[str, Any],
) -> VerifiedFullEvidence:
    """Verify one complete bundle and normalize canonical contract failures."""

    try:
        return _verify_full_evidence_file_impl(path, run_start=run_start)
    except OneShotABAuthorityError:
        raise
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise OneShotABAuthorityError(
            "full evidence canonical reconstruction failed: "
            f"{type(exc).__name__}"
        ) from exc


def build_external_evidence_envelope(
    *args: object,
    **kwargs: object,
) -> dict[str, Any]:
    """Reject the superseded hash-only manifest builder."""

    del args, kwargs
    raise OneShotABAuthorityError(
        "hash-only evidence manifests are not accepted; "
        "build a full evidence bundle"
    )


def verify_external_evidence_file(
    *args: object,
    **kwargs: object,
) -> dict[str, str]:
    """Reject the superseded per-role manifest verifier."""

    del args, kwargs
    raise OneShotABAuthorityError(
        "per-role hash manifests are not accepted; "
        "verify the full evidence bundle"
    )


__all__ = [
    "FULL_CASE_EVIDENCE_SCHEMA_ID",
    "FULL_EVIDENCE_BUNDLE_SCHEMA_ID",
    "MAX_FULL_EVIDENCE_BYTES",
    "VerifiedFullEvidence",
    "build_external_evidence_envelope",
    "build_full_evidence_bundle",
    "verify_external_evidence_file",
    "verify_full_evidence_file",
]
