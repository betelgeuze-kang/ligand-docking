"""Complete candidate-level artifact audit for the one-shot clearance A/B.

The legacy evidence envelopes retain receipt identities only.  This module binds
those identities to complete candidate and case receipt bytes, independently
rederives arm/cross-arm summaries, and offers the only result-construction path
that is eligible for the historical operator CLI.  It does not run docking or
grant fresh, Stage 0, product, pose-delivery, promotion, or claim authority.
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
from betelgeuze_engine_v2.docking.scorer_v1 import SCORER_V1_TERMS_SCHEMA_ID

from .source_paired_clearance_activation import (
    INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_SET_SHA256,
    SOURCE_PAIRED_CLEARANCE_ACTIVATION_SNAPSHOT_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR,
    SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256,
    SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
    SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID,
    _frozen_case_source_authority,
)
from .source_paired_clearance_one_shot_ab import (
    EXPECTED_POLICY_SHA256,
    OneShotABAuthorityError,
    _is_sha256,
)


FULL_CANDIDATE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_"
    "full_candidate_binding/1.0.0"
)
FULL_ARM_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_"
    "full_arm_evidence/1.0.0"
)
FULL_COMPARISON_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_"
    "full_comparison_evidence/1.0.0"
)
EXPECTED_BASELINE_PROFILE_ID = "current_v7"
EXPECTED_EXPERIMENTAL_PROFILE_ID = (
    "current_v7_with_only_predeclared_clearance_shadow_selected_states_replaced"
)
MAX_FULL_EVIDENCE_BYTES = 512 * 1024 * 1024
_RMSD_THRESHOLD_ANGSTROM = 2.0
_ARM_ROLES = (
    ("baseline_arm", "baseline_current_v7", EXPECTED_BASELINE_PROFILE_ID),
    (
        "experimental_arm",
        "experimental_clearance_shadow",
        EXPECTED_EXPERIMENTAL_PROFILE_ID,
    ),
)
_AUTHORITY_FALSE_KEYS = (
    "fresh_holdout_execution_authorized",
    "stage0_admission_authority",
    "profile_promotion_authority",
    "product_execution_authorized",
    "customer_pose_emission_authorized",
    "public_or_scientific_claim_authorized",
)


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
        raise OneShotABAuthorityError(
            "full evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _copy(value: object) -> object:
    return json.loads(_canonical_bytes(value).decode("ascii"))


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OneShotABAuthorityError(f"{name} must be an object")
    copied = _copy(value)
    assert isinstance(copied, dict)
    return copied


def _sequence(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise OneShotABAuthorityError(f"{name} must be an array")
    copied = _copy(value)
    assert isinstance(copied, list)
    return copied


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        raise OneShotABAuthorityError(f"{name} key set is invalid")


def _digest(value: object, *, name: str) -> str:
    if not _is_sha256(value):
        raise OneShotABAuthorityError(f"{name} must be a lowercase SHA-256")
    return str(value)


def _git_sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OneShotABAuthorityError(f"{name} must be a lowercase Git SHA-1")
    return value


def _float_from_hex(value: object, *, name: str, minimum: float | None = None) -> float:
    if not isinstance(value, str):
        raise OneShotABAuthorityError(f"{name} must be binary64 hex")
    try:
        observed = float.fromhex(value)
    except ValueError as exc:
        raise OneShotABAuthorityError(f"{name} must be binary64 hex") from exc
    if not math.isfinite(observed) or (minimum is not None and observed < minimum):
        raise OneShotABAuthorityError(f"{name} is outside the finite range")
    if observed.hex() != value:
        raise OneShotABAuthorityError(f"{name} is not canonical binary64 hex")
    return observed


def _verify_self_hash(
    value: object,
    *,
    hash_field: str,
    name: str,
    schema_id: str | None = None,
) -> dict[str, Any]:
    copied = _mapping(value, name=name)
    observed = copied.pop(hash_field, None)
    _digest(observed, name=f"{name} {hash_field}")
    if schema_id is not None and copied.get("schema_id") != schema_id:
        raise OneShotABAuthorityError(f"{name} schema is invalid")
    if observed != _sha256(copied):
        raise OneShotABAuthorityError(f"{name} self-hash is invalid")
    copied[hash_field] = observed
    return copied


def _seal(value: Mapping[str, Any], *, hash_field: str = "receipt_sha256") -> dict[str, Any]:
    copied = _mapping(dict(value), name="seal input")
    copied.pop(hash_field, None)
    copied[hash_field] = _sha256(copied)
    return copied


def _run_bindings(run_start: Mapping[str, Any]) -> dict[str, str]:
    policy_sha256 = _digest(
        run_start.get("policy_sha256"),
        name="run-start policy_sha256",
    )
    if policy_sha256 != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError("run-start policy is cross-wired")
    if run_start.get("required_scorer_backend") != "rust_cpu_required":
        raise OneShotABAuthorityError("full evidence requires the Rust CPU scorer")
    if run_start.get("expected_scored_candidate_rows") != 1024:
        raise OneShotABAuthorityError("run-start candidate denominator drifted")
    return {
        "policy_sha256": policy_sha256,
        "run_start_receipt_sha256": _digest(
            run_start.get("receipt_sha256"),
            name="run-start receipt_sha256",
        ),
        "source_commit_git_sha1": _git_sha(
            run_start.get("source_commit_git_sha1"),
            name="run-start source_commit_git_sha1",
        ),
        "execution_environment_sha256": _digest(
            run_start.get("execution_environment_sha256"),
            name="run-start execution_environment_sha256",
        ),
    }


def _verify_scorer_terms(
    value: object,
    *,
    candidate_fingerprint: str,
    authority_input_receipt_sha256: str,
) -> tuple[dict[str, Any], float]:
    scorer = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name="ScorerV1Terms",
        schema_id=SCORER_V1_TERMS_SCHEMA_ID,
    )
    expected_keys = {
        "schema_id",
        "score_id",
        "proposal_fingerprint_sha256",
        "authority_input_receipt_sha256",
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "backend_receipt_sha256",
        "typed_vdw_binary64_hex",
        "electrostatics_binary64_hex",
        "directional_hbond_binary64_hex",
        "hydrophobic_contact_binary64_hex",
        "desolvation_proxy_binary64_hex",
        "torsion_energy_binary64_hex",
        "ligand_strain_binary64_hex",
        "weak_pocket_prior_binary64_hex",
        "total_score_binary64_hex",
        "receptor_candidate_pair_count",
        "ligand_pair_count",
        "hbond_count",
        "hydrophobic_contact_count",
        "buried_polar_count",
        "calibrated",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }
    _exact_keys(scorer, expected_keys, name="ScorerV1Terms")
    if scorer.get("proposal_fingerprint_sha256") != candidate_fingerprint:
        raise OneShotABAuthorityError("ScorerV1Terms is cross-wired to another candidate")
    if scorer.get("authority_input_receipt_sha256") != authority_input_receipt_sha256:
        raise OneShotABAuthorityError("ScorerV1Terms is cross-wired to another source")
    for field in (
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "backend_receipt_sha256",
    ):
        _digest(scorer.get(field), name=f"ScorerV1Terms {field}")
    terms = tuple(
        _float_from_hex(scorer.get(f"{name}_binary64_hex"), name=name)
        for name in (
            "typed_vdw",
            "electrostatics",
            "directional_hbond",
            "hydrophobic_contact",
            "desolvation_proxy",
            "torsion_energy",
            "ligand_strain",
            "weak_pocket_prior",
        )
    )
    total = _float_from_hex(
        scorer.get("total_score_binary64_hex"),
        name="total_score",
    )
    if not math.isclose(total, sum(terms), rel_tol=0.0, abs_tol=1.0e-12):
        raise OneShotABAuthorityError("ScorerV1Terms total does not rederive")
    for field in (
        "receptor_candidate_pair_count",
        "ligand_pair_count",
        "hbond_count",
        "hydrophobic_contact_count",
        "buried_polar_count",
    ):
        observed = scorer.get(field)
        if type(observed) is not int or observed < 0:
            raise OneShotABAuthorityError(f"ScorerV1Terms {field} is invalid")
    if any(
        scorer.get(field) is not False
        for field in ("calibrated", "scientifically_validated", "claim_safe")
    ):
        raise OneShotABAuthorityError("ScorerV1Terms exceeds its claim boundary")
    return scorer, total


def _verify_internal_validity(
    value: object,
    *,
    candidate_fingerprint: str,
    coordinate_sha256: str,
    pose_artifact_sha256: str,
    case_source: Mapping[str, Any],
) -> tuple[dict[str, Any], bool, dict[str, bool]]:
    evidence = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name="internal validity evidence",
        schema_id=SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID,
    )
    if (
        evidence.get("proposal_fingerprint_sha256") != candidate_fingerprint
        or evidence.get("coordinate_sha256") != coordinate_sha256
        or evidence.get("pose_artifact_sha256") != pose_artifact_sha256
        or evidence.get("authority_input_receipt_sha256")
        != case_source.get("authenticated_input_receipt_sha256")
        or evidence.get("problem_fingerprint_sha256")
        != case_source.get("problem_fingerprint_sha256")
    ):
        raise OneShotABAuthorityError("internal validity evidence is cross-wired")
    for field in (
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "evaluator_implementation_sha256",
    ):
        _digest(evidence.get(field), name=f"internal validity {field}")
    if tuple(evidence.get("required_check_names", ())) != tuple(
        INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES
    ) or evidence.get("required_check_set_sha256") != _sha256(
        list(INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES)
    ):
        raise OneShotABAuthorityError("internal validity check set drifted")
    result = _mapping(evidence.get("result"), name="internal validity result")
    checks = _mapping(result.get("checks"), name="internal validity checks")
    evaluated = _mapping(
        result.get("evaluated_checks"),
        name="internal validity evaluated checks",
    )
    if (
        tuple(checks) != tuple(INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES)
        or tuple(evaluated) != tuple(INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES)
        or any(type(item) is not bool for item in checks.values())
        or any(item is not True for item in evaluated.values())
    ):
        raise OneShotABAuthorityError("internal validity check observations are incomplete")
    expected_valid = all(checks.values())
    if (
        result.get("complete") is not True
        or result.get("valid_within_evaluated_scope") is not expected_valid
        or result.get("valid") is not expected_valid
        or evidence.get("complete") is not True
        or evidence.get("valid") is not expected_valid
        or evidence.get("claim_safe") is not False
    ):
        raise OneShotABAuthorityError("internal validity result does not rederive")
    reasons = result.get("not_evaluated_reasons")
    if not isinstance(reasons, dict) or reasons:
        raise OneShotABAuthorityError("internal validity has unevaluated checks")
    return evidence, expected_valid, {str(key): bool(item) for key, item in checks.items()}


def _verify_posebusters(
    value: object,
    *,
    candidate_fingerprint: str,
    coordinate_sha256: str,
    pose_artifact_sha256: str,
    case_source: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    evidence = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name="PoseBusters evidence",
        schema_id=SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID,
    )
    if (
        evidence.get("proposal_fingerprint_sha256") != candidate_fingerprint
        or evidence.get("coordinate_sha256") != coordinate_sha256
        or evidence.get("pose_artifact_sha256") != pose_artifact_sha256
        or evidence.get("native_pose_artifact_sha256")
        != case_source.get("native_pose_artifact_sha256")
        or evidence.get("receptor_artifact_sha256")
        != case_source.get("receptor_artifact_sha256")
    ):
        raise OneShotABAuthorityError("PoseBusters evidence is cross-wired")
    if (
        evidence.get("posebusters_version") != "0.3.1"
        or evidence.get("mode") != "redock"
        or tuple(evidence.get("required_check_names", ()))
        != tuple(POSEBUSTERS_REQUIRED_CHECK_NAMES)
        or evidence.get("required_check_set_sha256")
        != POSEBUSTERS_REQUIRED_CHECK_SET_SHA256
    ):
        raise OneShotABAuthorityError("PoseBusters execution profile drifted")
    checks = _mapping(evidence.get("check_results"), name="PoseBusters checks")
    if (
        set(checks) != set(POSEBUSTERS_REQUIRED_CHECK_NAMES)
        or any(type(item) is not bool for item in checks.values())
    ):
        raise OneShotABAuthorityError("PoseBusters 22-check set is incomplete")
    expected_valid = all(checks.values())
    if (
        evidence.get("complete") is not True
        or evidence.get("valid") is not expected_valid
        or evidence.get("claim_safe") is not False
    ):
        raise OneShotABAuthorityError("PoseBusters validity does not rederive")
    return evidence, expected_valid


def _verify_rmsd(
    value: object,
    *,
    candidate_fingerprint: str,
    coordinate_sha256: str,
    pose_artifact_sha256: str,
    case_source: Mapping[str, Any],
) -> tuple[dict[str, Any], float]:
    evidence = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name="RMSD evidence",
        schema_id=SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID,
    )
    if (
        evidence.get("proposal_fingerprint_sha256") != candidate_fingerprint
        or evidence.get("coordinate_sha256") != coordinate_sha256
        or evidence.get("pose_artifact_sha256") != pose_artifact_sha256
        or evidence.get("native_pose_artifact_sha256")
        != case_source.get("native_pose_artifact_sha256")
        or evidence.get("receptor_artifact_sha256")
        != case_source.get("receptor_artifact_sha256")
        or evidence.get("method_id") != "posebusters_redock_symmetry_aware_rmsd"
        or evidence.get("complete") is not True
        or evidence.get("claim_safe") is not False
    ):
        raise OneShotABAuthorityError("RMSD evidence is incomplete or cross-wired")
    rmsd = _float_from_hex(
        evidence.get("rmsd_angstrom_binary64_hex"),
        name="rmsd_angstrom",
        minimum=0.0,
    )
    return evidence, rmsd


def _verify_candidate(
    value: object,
    *,
    expected_index: int,
    case_source: Mapping[str, Any],
) -> dict[str, Any]:
    candidate = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name="candidate evidence",
        schema_id=SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID,
    )
    expected_keys = {
        "schema_id",
        "candidate_id",
        "proposal_index",
        "candidate_proposal_fingerprint_sha256",
        "source_proposal_fingerprint_sha256",
        "coordinate_sha256",
        "pose_artifact_sha256",
        "raw_score_binary64_hex",
        "scorer_v1_terms",
        "internal_pose_validity",
        "posebusters",
        "rmsd",
        "rmsd_angstrom_binary64_hex",
        "exact_valid",
        "raw_score_rank",
        "receipt_sha256",
    }
    _exact_keys(candidate, expected_keys, name="candidate evidence")
    if candidate.get("proposal_index") != expected_index:
        raise OneShotABAuthorityError("candidate proposal index is outside the exact grid")
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise OneShotABAuthorityError("candidate_id is invalid")
    candidate_fingerprint = _digest(
        candidate.get("candidate_proposal_fingerprint_sha256"),
        name="candidate proposal fingerprint",
    )
    _digest(
        candidate.get("source_proposal_fingerprint_sha256"),
        name="source proposal fingerprint",
    )
    coordinate_sha256 = _digest(
        candidate.get("coordinate_sha256"),
        name="candidate coordinate_sha256",
    )
    pose_artifact_sha256 = _digest(
        candidate.get("pose_artifact_sha256"),
        name="candidate pose_artifact_sha256",
    )
    scorer, score = _verify_scorer_terms(
        candidate.get("scorer_v1_terms"),
        candidate_fingerprint=candidate_fingerprint,
        authority_input_receipt_sha256=str(
            case_source.get("authenticated_input_receipt_sha256")
        ),
    )
    internal, internal_valid, internal_checks = _verify_internal_validity(
        candidate.get("internal_pose_validity"),
        candidate_fingerprint=candidate_fingerprint,
        coordinate_sha256=coordinate_sha256,
        pose_artifact_sha256=pose_artifact_sha256,
        case_source=case_source,
    )
    posebusters, posebusters_valid = _verify_posebusters(
        candidate.get("posebusters"),
        candidate_fingerprint=candidate_fingerprint,
        coordinate_sha256=coordinate_sha256,
        pose_artifact_sha256=pose_artifact_sha256,
        case_source=case_source,
    )
    rmsd_evidence, rmsd = _verify_rmsd(
        candidate.get("rmsd"),
        candidate_fingerprint=candidate_fingerprint,
        coordinate_sha256=coordinate_sha256,
        pose_artifact_sha256=pose_artifact_sha256,
        case_source=case_source,
    )
    if (
        candidate.get("raw_score_binary64_hex") != score.hex()
        or candidate.get("rmsd_angstrom_binary64_hex") != rmsd.hex()
    ):
        raise OneShotABAuthorityError("candidate score or RMSD projection drifted")
    exact_valid = bool(
        rmsd <= _RMSD_THRESHOLD_ANGSTROM
        and internal_valid
        and posebusters_valid
    )
    if candidate.get("exact_valid") is not exact_valid:
        raise OneShotABAuthorityError("candidate exact-valid state does not rederive")
    rank = candidate.get("raw_score_rank")
    if type(rank) is not int or not 1 <= rank <= SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR:
        raise OneShotABAuthorityError("candidate raw score rank is invalid")
    return {
        "payload": candidate,
        "receipt_sha256": candidate["receipt_sha256"],
        "candidate_id": candidate_id,
        "proposal_index": expected_index,
        "candidate_fingerprint": candidate_fingerprint,
        "source_fingerprint": candidate["source_proposal_fingerprint_sha256"],
        "score": score,
        "rank": rank,
        "rmsd": rmsd,
        "internal_valid": internal_valid,
        "internal_checks": internal_checks,
        "posebusters_valid": posebusters_valid,
        "exact_valid": exact_valid,
        "scorer": scorer,
        "internal": internal,
        "posebusters": posebusters,
        "rmsd_evidence": rmsd_evidence,
    }


def _verify_case_source(value: object, *, case_id: str) -> dict[str, Any]:
    case_source = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name=f"{case_id} case source",
        schema_id=SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID,
    )
    if case_source.get("case_id") != case_id:
        raise OneShotABAuthorityError("case source ID is cross-wired")
    authority = _frozen_case_source_authority(case_id)
    if authority is None:
        raise OneShotABAuthorityError("case source authority is absent")
    for field, expected in authority.items():
        if case_source.get(field) != expected:
            raise OneShotABAuthorityError(
                f"{case_id} case source does not match frozen authority"
            )
    if (
        case_source.get("case_source_authority_sha256")
        != SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256
        or case_source.get("member_manifest_membership_verified") is not True
        or case_source.get("historical_archive_full_scorer_terms_available") is not False
        or case_source.get("historical_archive_score_rank_semantics_authorized") is not False
        or case_source.get("claim_safe") is not False
    ):
        raise OneShotABAuthorityError("case source authority boundary drifted")
    for field in (
        "problem_fingerprint_sha256",
        "native_pose_artifact_sha256",
        "receptor_artifact_sha256",
        "authenticated_input_receipt_sha256",
        "source_proposal_receipt_sha256",
        "allocation_receipt_sha256",
        "current_v7_candidate_lineage_sha256",
    ):
        _digest(case_source.get(field), name=f"case source {field}")
    return case_source


def _verify_ranking(
    value: object,
    *,
    expected_arm: str,
    case_source: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    ranking = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name=f"{expected_arm} ranking",
        schema_id=SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID,
    )
    if ranking.get("arm") != expected_arm or ranking.get("candidate_denominator") != 64:
        raise OneShotABAuthorityError("arm ranking identity or denominator drifted")
    candidate_values = _sequence(
        ranking.get("candidate_rows_by_proposal_index"),
        name="candidate rows",
    )
    if len(candidate_values) != SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR:
        raise OneShotABAuthorityError("arm ranking does not retain 64 candidates")
    rows = tuple(
        _verify_candidate(item, expected_index=index, case_source=case_source)
        for index, item in enumerate(candidate_values)
    )
    if len({str(row["candidate_id"]) for row in rows}) != len(rows):
        raise OneShotABAuthorityError("candidate IDs are not unique within a case arm")
    ranked = tuple(sorted(rows, key=lambda row: (row["score"], row["proposal_index"])))
    if tuple(row["rank"] for row in ranked) != tuple(range(1, 65)):
        raise OneShotABAuthorityError("candidate ranks do not rederive from scores")
    if ranking.get("raw_rank_order_proposal_indices") != [
        row["proposal_index"] for row in ranked
    ]:
        raise OneShotABAuthorityError("rank-order proposal indices drifted")
    ranked_hashes = [str(row["receipt_sha256"]) for row in ranked]
    if (
        ranking.get("raw_rank_order_receipt_sha256") != _sha256(ranked_hashes)
        or ranking.get("top1_candidate_receipt_sha256") != ranked_hashes[0]
        or ranking.get("top5_candidate_receipt_sha256s") != ranked_hashes[:5]
    ):
        raise OneShotABAuthorityError("Top-1/Top-5 receipt identities do not rederive")
    scorer_profile = _mapping(
        ranking.get("scorer_execution_profile"),
        name="scorer execution profile",
    )
    first_scorer = rows[0]["scorer"]
    expected_profile = {
        field: first_scorer[field]
        for field in (
            "authority_input_receipt_sha256",
            "context_fingerprint_sha256",
            "config_fingerprint_sha256",
            "backend_receipt_sha256",
        )
    }
    if (
        scorer_profile != expected_profile
        or ranking.get("scorer_execution_profile_sha256") != _sha256(expected_profile)
        or any(
            any(row["scorer"][field] != expected for field, expected in expected_profile.items())
            for row in rows
        )
    ):
        raise OneShotABAuthorityError("scorer execution authority is not uniform")
    if (
        ranking.get("score_term_semantics_fully_rederivable") is not True
        or ranking.get("validity_semantics_fully_rederivable") is not True
        or ranking.get("claim_safe") is not False
    ):
        raise OneShotABAuthorityError("arm ranking evidence boundary drifted")
    return ranking, rows


def _scientific_candidate_projection(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _copy(value)
        for key, value in candidate.items()
        if key not in {"schema_id", "raw_score_rank", "receipt_sha256"}
    }


def _penetrating_without_posebusters_change(
    baseline: Mapping[str, Any],
    experimental: Mapping[str, Any],
) -> bool:
    checks = experimental["internal_checks"]
    penetrating = checks.get("receptor_ligand_clash_free") is False
    return bool(
        penetrating
        and baseline["posebusters_valid"] == experimental["posebusters_valid"]
    )


def _verify_case_activation_receipt(value: object, *, case_id: str) -> dict[str, Any]:
    receipt = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name=f"{case_id} activation receipt",
        schema_id=SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID,
    )
    expected_keys = {
        "schema_id",
        "case_id",
        "case_source",
        "source_proposal_receipt",
        "source_proposal_receipt_sha256",
        "current_v7_lineage",
        "current_v7_candidate_lineage_sha256",
        "allocation_receipt",
        "allocation_receipt_sha256",
        "activation_target_count",
        "activation_targets",
        "selected_replacement_proposal_indices",
        "baseline_arm_ranking",
        "experimental_arm_ranking",
        "full_scoring_and_validity_evidence",
        "full_source_proposal_lineage_verified",
        "full_current_v7_candidate_lineage_verified",
        "full_posebusters_check_set_verified",
        "authenticated_rmsd_receipts_verified",
        "score_term_semantics_fully_rederivable",
        "top1_top5_semantics_fully_rederivable",
        "decision_sealed_before_score_rank_validity",
        "historical_ab_execution_authorized",
        "fresh_holdout_execution_authorized",
        "product_or_claim_authority",
        "receipt_sha256",
    }
    _exact_keys(receipt, expected_keys, name="case activation receipt")
    if receipt.get("case_id") != case_id:
        raise OneShotABAuthorityError("case activation receipt is cross-wired")
    case_source = _verify_case_source(receipt.get("case_source"), case_id=case_id)

    proposal_receipt = _verify_self_hash(
        receipt.get("source_proposal_receipt"),
        hash_field="receipt_sha256",
        name="source proposal receipt",
        schema_id=SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID,
    )
    if (
        proposal_receipt["receipt_sha256"]
        != receipt.get("source_proposal_receipt_sha256")
        or proposal_receipt["receipt_sha256"]
        != case_source.get("source_proposal_receipt_sha256")
    ):
        raise OneShotABAuthorityError("source proposal receipt is cross-wired")
    slots = _sequence(proposal_receipt.get("candidate_slots"), name="source candidate slots")
    if len(slots) != 64 or any(
        not isinstance(slot, dict) or slot.get("proposal_index") != index
        for index, slot in enumerate(slots)
    ):
        raise OneShotABAuthorityError("source proposal receipt lacks the exact 64-slot grid")

    lineage = _verify_self_hash(
        receipt.get("current_v7_lineage"),
        hash_field="receipt_sha256",
        name="current-V7 lineage",
        schema_id=SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID,
    )
    if (
        lineage.get("current_v7_candidate_lineage_sha256")
        != receipt.get("current_v7_candidate_lineage_sha256")
        or lineage.get("current_v7_candidate_lineage_sha256")
        != case_source.get("current_v7_candidate_lineage_sha256")
    ):
        raise OneShotABAuthorityError("current-V7 lineage is cross-wired")
    lineage_rows = _sequence(
        lineage.get("current_v7_candidate_lineage_rows"),
        name="current-V7 lineage rows",
    )
    if len(lineage_rows) != 64:
        raise OneShotABAuthorityError("current-V7 lineage lacks 64 rows")

    allocation = _verify_self_hash(
        receipt.get("allocation_receipt"),
        hash_field="allocation_sha256",
        name="allocation receipt",
    )
    if (
        allocation["allocation_sha256"] != receipt.get("allocation_receipt_sha256")
        or allocation["allocation_sha256"] != case_source.get("allocation_receipt_sha256")
    ):
        raise OneShotABAuthorityError("allocation receipt is cross-wired")

    baseline_ranking, baseline_rows = _verify_ranking(
        receipt.get("baseline_arm_ranking"),
        expected_arm="baseline_current_v7",
        case_source=case_source,
    )
    experimental_ranking, experimental_rows = _verify_ranking(
        receipt.get("experimental_arm_ranking"),
        expected_arm="experimental_clearance_shadow",
        case_source=case_source,
    )
    for index, (slot, baseline, experimental) in enumerate(
        zip(slots, baseline_rows, experimental_rows, strict=True)
    ):
        if (
            baseline["candidate_id"] != slot.get("candidate_id")
            or experimental["candidate_id"] != slot.get("candidate_id")
            or baseline["source_fingerprint"] != slot.get("proposal_fingerprint_sha256")
            or experimental["source_fingerprint"]
            != slot.get("proposal_fingerprint_sha256")
        ):
            raise OneShotABAuthorityError(
                f"case candidate slot {index} is not source bound"
            )

    target_values = _sequence(receipt.get("activation_targets"), name="activation targets")
    selected_values = receipt.get("selected_replacement_proposal_indices")
    if not isinstance(selected_values, list) or any(type(item) is not int for item in selected_values):
        raise OneShotABAuthorityError("selected replacement indices are invalid")
    selected_indices = tuple(selected_values)
    if selected_indices != tuple(sorted(set(selected_indices))) or any(
        not 0 <= index < 64 for index in selected_indices
    ):
        raise OneShotABAuthorityError("selected replacement indices are invalid")
    if receipt.get("activation_target_count") != len(target_values):
        raise OneShotABAuthorityError("activation target count drifted")
    target_indices: list[int] = []
    selected_from_states: list[int] = []
    shadow_eligible_count = 0
    for target_value in target_values:
        target = _mapping(target_value, name="activation target")
        index = target.get("proposal_index")
        if type(index) is not int or not 0 <= index < 64 or index in target_indices:
            raise OneShotABAuthorityError("activation target index is invalid")
        target_indices.append(index)
        snapshot = _verify_self_hash(
            target.get("source_snapshot"),
            hash_field="snapshot_sha256",
            name="activation source snapshot",
            schema_id=SOURCE_PAIRED_CLEARANCE_ACTIVATION_SNAPSHOT_SCHEMA_ID,
        )
        state = _verify_self_hash(
            target.get("activated_state"),
            hash_field="state_sha256",
            name="activated state",
            schema_id=SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
        )
        if snapshot.get("proposal_index") != index or state.get("proposal_index") != index:
            raise OneShotABAuthorityError("activation target is cross-wired")
        if target.get("baseline_candidate") != baseline_rows[index]["payload"] or target.get(
            "selected_or_retained_candidate"
        ) != experimental_rows[index]["payload"]:
            raise OneShotABAuthorityError("activation target candidate bytes are cross-wired")
        if state.get("shadow_selection_eligible") is True:
            shadow_eligible_count += 1
        elif state.get("shadow_selection_eligible") is not False:
            raise OneShotABAuthorityError("shadow-selection eligibility is invalid")
        if state.get("selection_applied") is True:
            selected_from_states.append(index)
        elif state.get("selection_applied") is not False:
            raise OneShotABAuthorityError("activation selection state is invalid")
        if state.get("result_dependent_allocation") is not False:
            raise OneShotABAuthorityError("result-dependent allocation was observed")
    if tuple(sorted(target_indices)) != tuple(target_indices):
        raise OneShotABAuthorityError("activation targets are not ordered")
    if tuple(selected_from_states) != selected_indices:
        raise OneShotABAuthorityError("selected indices do not rederive from states")

    changed_indices: list[int] = []
    penetrating_without_change = 0
    for index, (baseline, experimental) in enumerate(
        zip(baseline_rows, experimental_rows, strict=True)
    ):
        changed = _scientific_candidate_projection(baseline["payload"]) != (
            _scientific_candidate_projection(experimental["payload"])
        )
        if changed:
            changed_indices.append(index)
            if _penetrating_without_posebusters_change(baseline, experimental):
                penetrating_without_change += 1
        if index not in target_indices and changed:
            raise OneShotABAuthorityError("experimental arm changed a non-target candidate")
    if tuple(changed_indices) != selected_indices:
        raise OneShotABAuthorityError("changed candidates do not equal predeclared selections")

    for field in (
        "full_scoring_and_validity_evidence",
        "full_source_proposal_lineage_verified",
        "full_current_v7_candidate_lineage_verified",
        "full_posebusters_check_set_verified",
        "authenticated_rmsd_receipts_verified",
        "score_term_semantics_fully_rederivable",
        "top1_top5_semantics_fully_rederivable",
        "decision_sealed_before_score_rank_validity",
    ):
        if receipt.get(field) is not True:
            raise OneShotABAuthorityError(f"case receipt {field} is not verified")
    if (
        receipt.get("historical_ab_execution_authorized") is not False
        or receipt.get("fresh_holdout_execution_authorized") is not False
        or receipt.get("product_or_claim_authority") is not False
    ):
        raise OneShotABAuthorityError("case receipt exceeds its authority")
    return {
        "payload": receipt,
        "receipt_sha256": receipt["receipt_sha256"],
        "case_source": case_source,
        "baseline_ranking": baseline_ranking,
        "experimental_ranking": experimental_ranking,
        "baseline_rows": baseline_rows,
        "experimental_rows": experimental_rows,
        "selected_indices": selected_indices,
        "shadow_eligible_count": shadow_eligible_count,
        "penetrating_without_validity_change_count": penetrating_without_change,
    }


def _candidate_binding(
    *,
    bindings: Mapping[str, str],
    case_id: str,
    case_receipt_sha256: str,
    arm_role: str,
    profile_id: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema_id": FULL_CANDIDATE_BINDING_SCHEMA_ID,
        **dict(bindings),
        "case_id": case_id,
        "case_activation_receipt_sha256": case_receipt_sha256,
        "arm_role": arm_role,
        "profile_id": profile_id,
        "proposal_index": row["proposal_index"],
        "candidate_receipt_sha256": row["receipt_sha256"],
        "candidate_receipt": row["payload"],
    }
    return _seal(payload)


def _arm_artifact(
    *,
    arm_key: str,
    arm_role: str,
    profile_id: str,
    bindings: Mapping[str, str],
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_bindings: list[dict[str, Any]] = []
    case_hashes: list[str] = []
    row_key = "baseline_rows" if arm_key == "baseline_arm" else "experimental_rows"
    for case_id, case in zip(SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS, cases, strict=True):
        case_hash = str(case["receipt_sha256"])
        case_hashes.append(case_hash)
        for row in case[row_key]:
            candidate_bindings.append(
                _candidate_binding(
                    bindings=bindings,
                    case_id=case_id,
                    case_receipt_sha256=case_hash,
                    arm_role=arm_role,
                    profile_id=profile_id,
                    row=row,
                )
            )
    return _seal(
        {
            "schema_id": FULL_ARM_EVIDENCE_SCHEMA_ID,
            **dict(bindings),
            "arm_role": arm_role,
            "profile_id": profile_id,
            "case_activation_receipt_sha256s": case_hashes,
            "candidate_bindings": candidate_bindings,
            "candidate_binding_receipt_sha256s": [
                item["receipt_sha256"] for item in candidate_bindings
            ],
            "candidate_count": 512,
        }
    )


def build_full_comparison_evidence_artifact(
    *,
    run_start: Mapping[str, Any],
    case_activation_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one complete immutable artifact from eight full case receipts."""

    bindings = _run_bindings(run_start)
    values = tuple(case_activation_receipts)
    if len(values) != len(SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS):
        raise OneShotABAuthorityError("full evidence requires eight case receipts")
    cases = tuple(
        _verify_case_activation_receipt(value, case_id=case_id)
        for case_id, value in zip(
            SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
            values,
            strict=True,
        )
    )
    baseline = _arm_artifact(
        arm_key="baseline_arm",
        arm_role="baseline_current_v7",
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
        bindings=bindings,
        cases=cases,
    )
    experimental = _arm_artifact(
        arm_key="experimental_arm",
        arm_role="experimental_clearance_shadow",
        profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
        bindings=bindings,
        cases=cases,
    )
    artifact = _seal(
        {
            "schema_id": FULL_COMPARISON_EVIDENCE_SCHEMA_ID,
            **bindings,
            "case_activation_receipts": [case["payload"] for case in cases],
            "case_activation_receipt_sha256s": [
                case["receipt_sha256"] for case in cases
            ],
            "baseline_arm": baseline,
            "experimental_arm": experimental,
            "historical_ab_execution_authorized": False,
            **{key: False for key in _AUTHORITY_FALSE_KEYS},
        }
    )
    verify_full_comparison_evidence_artifact(
        artifact,
        run_start=run_start,
    )
    return artifact


def _verify_candidate_binding(
    value: object,
    *,
    expected_bindings: Mapping[str, str],
    expected_case_id: str,
    expected_case_receipt_sha256: str,
    expected_arm_role: str,
    expected_profile_id: str,
    expected_row: Mapping[str, Any],
) -> dict[str, Any]:
    binding = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name="full candidate binding",
        schema_id=FULL_CANDIDATE_BINDING_SCHEMA_ID,
    )
    expected_keys = {
        "schema_id",
        *expected_bindings.keys(),
        "case_id",
        "case_activation_receipt_sha256",
        "arm_role",
        "profile_id",
        "proposal_index",
        "candidate_receipt_sha256",
        "candidate_receipt",
        "receipt_sha256",
    }
    _exact_keys(binding, expected_keys, name="full candidate binding")
    if any(binding.get(key) != expected for key, expected in expected_bindings.items()):
        raise OneShotABAuthorityError("candidate binding is reused across runs")
    if (
        binding.get("case_id") != expected_case_id
        or binding.get("case_activation_receipt_sha256")
        != expected_case_receipt_sha256
        or binding.get("arm_role") != expected_arm_role
        or binding.get("profile_id") != expected_profile_id
        or binding.get("proposal_index") != expected_row["proposal_index"]
        or binding.get("candidate_receipt_sha256") != expected_row["receipt_sha256"]
        or binding.get("candidate_receipt") != expected_row["payload"]
    ):
        raise OneShotABAuthorityError("candidate binding is cross-wired or fabricated")
    return binding


def _derive_arm_summary(cases: Sequence[Mapping[str, Any]], *, row_key: str) -> dict[str, Any]:
    top1: list[str] = []
    top5: list[str] = []
    exact_valid: list[str] = []
    proposal_oracle: list[str] = []
    invalid_top1: list[str] = []
    candidate_receipts: list[str] = []
    for case_id, case in zip(SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS, cases, strict=True):
        rows = tuple(case[row_key])
        ranked = tuple(sorted(rows, key=lambda row: row["rank"]))
        candidate_receipts.extend(str(row["receipt_sha256"]) for row in rows)
        if ranked[0]["rmsd"] <= _RMSD_THRESHOLD_ANGSTROM:
            top1.append(case_id)
        if any(row["rmsd"] <= _RMSD_THRESHOLD_ANGSTROM for row in ranked[:5]):
            top5.append(case_id)
        if any(bool(row["exact_valid"]) for row in rows):
            exact_valid.append(case_id)
        if any(row["rmsd"] <= _RMSD_THRESHOLD_ANGSTROM for row in rows):
            proposal_oracle.append(case_id)
        if not (
            bool(ranked[0]["internal_valid"])
            and bool(ranked[0]["posebusters_valid"])
        ):
            invalid_top1.append(case_id)
    return {
        "preparation_failure_case_ids": ("6M73_FNR",),
        "top1_recovery_case_ids": tuple(top1),
        "top5_recovery_case_ids": tuple(top5),
        "exact_valid_case_ids": tuple(exact_valid),
        "proposal_oracle_case_ids": tuple(proposal_oracle),
        "invalid_top1_case_ids": tuple(invalid_top1),
        "candidate_receipt_sha256s": tuple(candidate_receipts),
    }


def _verify_arm_artifact(
    value: object,
    *,
    arm_key: str,
    expected_arm_role: str,
    expected_profile_id: str,
    expected_bindings: Mapping[str, str],
    cases: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    arm = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name=f"{arm_key} full evidence",
        schema_id=FULL_ARM_EVIDENCE_SCHEMA_ID,
    )
    if any(arm.get(key) != expected for key, expected in expected_bindings.items()):
        raise OneShotABAuthorityError("full arm evidence is reused across runs")
    if (
        arm.get("arm_role") != expected_arm_role
        or arm.get("profile_id") != expected_profile_id
        or arm.get("candidate_count") != 512
    ):
        raise OneShotABAuthorityError("full arm identity or denominator drifted")
    case_hashes = [str(case["receipt_sha256"]) for case in cases]
    if arm.get("case_activation_receipt_sha256s") != case_hashes:
        raise OneShotABAuthorityError("full arm case receipts are cross-wired")
    bindings = _sequence(arm.get("candidate_bindings"), name="candidate bindings")
    binding_hashes = _sequence(
        arm.get("candidate_binding_receipt_sha256s"),
        name="candidate binding hashes",
    )
    if len(bindings) != 512 or len(binding_hashes) != 512:
        raise OneShotABAuthorityError("full arm does not contain 512 candidates")
    row_key = "baseline_rows" if arm_key == "baseline_arm" else "experimental_rows"
    verified: list[dict[str, Any]] = []
    cursor = 0
    for case_id, case in zip(SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS, cases, strict=True):
        for row in case[row_key]:
            verified.append(
                _verify_candidate_binding(
                    bindings[cursor],
                    expected_bindings=expected_bindings,
                    expected_case_id=case_id,
                    expected_case_receipt_sha256=str(case["receipt_sha256"]),
                    expected_arm_role=expected_arm_role,
                    expected_profile_id=expected_profile_id,
                    expected_row=row,
                )
            )
            cursor += 1
    observed_hashes = [item["receipt_sha256"] for item in verified]
    if binding_hashes != observed_hashes or len(set(observed_hashes)) != 512:
        raise OneShotABAuthorityError("candidate binding identities are missing or duplicated")
    summary = _derive_arm_summary(cases, row_key=row_key)
    if len(set(summary["candidate_receipt_sha256s"])) != 512:
        raise OneShotABAuthorityError("candidate receipt identities are reused within an arm")
    return arm, summary


@dataclass(frozen=True, slots=True)
class VerifiedFullComparisonEvidence:
    artifact_receipt_sha256: str
    baseline_arm_receipt_sha256: str
    experimental_arm_receipt_sha256: str
    baseline_summary_inputs: Mapping[str, Any]
    experimental_summary_inputs: Mapping[str, Any]
    source_control_preserved: bool
    result_dependent_allocation_observed: bool
    shadow_eligible_candidate_count: int
    selected_penetrating_without_validity_change_count: int
    changed_slot_count: int
    changed_slots_sha256: str


def verify_full_comparison_evidence_artifact(
    value: object,
    *,
    run_start: Mapping[str, Any],
) -> VerifiedFullComparisonEvidence:
    bindings = _run_bindings(run_start)
    artifact = _verify_self_hash(
        value,
        hash_field="receipt_sha256",
        name="full comparison evidence",
        schema_id=FULL_COMPARISON_EVIDENCE_SCHEMA_ID,
    )
    expected_keys = {
        "schema_id",
        *bindings.keys(),
        "case_activation_receipts",
        "case_activation_receipt_sha256s",
        "baseline_arm",
        "experimental_arm",
        "historical_ab_execution_authorized",
        *_AUTHORITY_FALSE_KEYS,
        "receipt_sha256",
    }
    _exact_keys(artifact, expected_keys, name="full comparison evidence")
    if any(artifact.get(key) != expected for key, expected in bindings.items()):
        raise OneShotABAuthorityError("full comparison evidence is reused across runs")
    if artifact.get("historical_ab_execution_authorized") is not False or any(
        artifact.get(key) is not False for key in _AUTHORITY_FALSE_KEYS
    ):
        raise OneShotABAuthorityError("full evidence exceeds its authority boundary")
    case_values = _sequence(
        artifact.get("case_activation_receipts"),
        name="case activation receipts",
    )
    if len(case_values) != 8:
        raise OneShotABAuthorityError("full evidence requires eight case receipts")
    cases = tuple(
        _verify_case_activation_receipt(value, case_id=case_id)
        for case_id, value in zip(
            SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
            case_values,
            strict=True,
        )
    )
    case_hashes = [str(case["receipt_sha256"]) for case in cases]
    if artifact.get("case_activation_receipt_sha256s") != case_hashes or len(
        set(case_hashes)
    ) != 8:
        raise OneShotABAuthorityError("case receipt identities are missing or duplicated")
    baseline_arm, baseline_summary = _verify_arm_artifact(
        artifact.get("baseline_arm"),
        arm_key="baseline_arm",
        expected_arm_role="baseline_current_v7",
        expected_profile_id=EXPECTED_BASELINE_PROFILE_ID,
        expected_bindings=bindings,
        cases=cases,
    )
    experimental_arm, experimental_summary = _verify_arm_artifact(
        artifact.get("experimental_arm"),
        arm_key="experimental_arm",
        expected_arm_role="experimental_clearance_shadow",
        expected_profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
        expected_bindings=bindings,
        cases=cases,
    )

    changed_rows: list[dict[str, Any]] = []
    shadow_eligible_count = 0
    penetrating_count = 0
    for case_id, case in zip(SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS, cases, strict=True):
        shadow_eligible_count += int(case["shadow_eligible_count"])
        penetrating_count += int(
            case["penetrating_without_validity_change_count"]
        )
        for index in case["selected_indices"]:
            baseline = case["baseline_rows"][index]
            experimental = case["experimental_rows"][index]
            changed_rows.append(
                {
                    "case_id": case_id,
                    "proposal_index": index,
                    "baseline_candidate_receipt_sha256": baseline[
                        "receipt_sha256"
                    ],
                    "experimental_candidate_receipt_sha256": experimental[
                        "receipt_sha256"
                    ],
                }
            )
    return VerifiedFullComparisonEvidence(
        artifact_receipt_sha256=str(artifact["receipt_sha256"]),
        baseline_arm_receipt_sha256=str(baseline_arm["receipt_sha256"]),
        experimental_arm_receipt_sha256=str(experimental_arm["receipt_sha256"]),
        baseline_summary_inputs=baseline_summary,
        experimental_summary_inputs=experimental_summary,
        source_control_preserved=True,
        result_dependent_allocation_observed=False,
        shadow_eligible_candidate_count=shadow_eligible_count,
        selected_penetrating_without_validity_change_count=penetrating_count,
        changed_slot_count=len(changed_rows),
        changed_slots_sha256=_sha256(changed_rows),
    )


def _read_pinned_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise OneShotABAuthorityError(
            f"full evidence cannot be opened safely: {exc}"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OneShotABAuthorityError("full evidence must be a regular file")
        if before.st_size <= 0 or before.st_size > MAX_FULL_EVIDENCE_BYTES:
            raise OneShotABAuthorityError("full evidence size is outside the bound")
        chunks: list[bytes] = []
        observed_size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_FULL_EVIDENCE_BYTES + 1))
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > MAX_FULL_EVIDENCE_BYTES:
                raise OneShotABAuthorityError("full evidence exceeds the byte bound")
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_identity != after_identity or observed_size != before.st_size:
        raise OneShotABAuthorityError("full evidence changed while being read")
    return b"".join(chunks)


def build_result_document_from_full_evidence_file(
    path: Path,
    *,
    run_start: Mapping[str, Any],
) -> dict[str, Any]:
    """Independently derive the compact result from complete evidence bytes."""

    raw = _read_pinned_regular_file(path)
    file_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OneShotABAuthorityError("full evidence is not UTF-8 JSON") from exc
    verified = verify_full_comparison_evidence_artifact(
        artifact,
        run_start=run_start,
    )
    from .source_paired_clearance_one_shot_result import (
        build_arm_summary,
        build_result_document,
    )

    baseline_inputs = dict(verified.baseline_summary_inputs)
    experimental_inputs = dict(verified.experimental_summary_inputs)
    baseline_inputs.pop("candidate_receipt_sha256s", None)
    experimental_inputs.pop("candidate_receipt_sha256s", None)
    baseline = build_arm_summary(
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
        arm_evidence_file_sha256=file_sha256,
        arm_evidence_self_sha256=verified.baseline_arm_receipt_sha256,
        **baseline_inputs,
    )
    experimental = build_arm_summary(
        profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
        arm_evidence_file_sha256=file_sha256,
        arm_evidence_self_sha256=verified.experimental_arm_receipt_sha256,
        **experimental_inputs,
    )
    return build_result_document(
        run_start=run_start,
        baseline_arm=baseline,
        experimental_arm=experimental,
        source_control_preserved=verified.source_control_preserved,
        result_dependent_allocation_observed=(
            verified.result_dependent_allocation_observed
        ),
        shadow_eligible_candidate_count=verified.shadow_eligible_candidate_count,
        selected_penetrating_without_validity_change_count=(
            verified.selected_penetrating_without_validity_change_count
        ),
        changed_slot_count=verified.changed_slot_count,
        changed_slots_sha256=verified.changed_slots_sha256,
        cross_arm_evidence_sha256=file_sha256,
    )


__all__ = [
    "FULL_ARM_EVIDENCE_SCHEMA_ID",
    "FULL_CANDIDATE_BINDING_SCHEMA_ID",
    "FULL_COMPARISON_EVIDENCE_SCHEMA_ID",
    "MAX_FULL_EVIDENCE_BYTES",
    "VerifiedFullComparisonEvidence",
    "build_full_comparison_evidence_artifact",
    "build_result_document_from_full_evidence_file",
    "verify_full_comparison_evidence_artifact",
]
