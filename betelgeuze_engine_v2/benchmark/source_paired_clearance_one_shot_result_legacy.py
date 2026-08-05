"""Result binding for the single historical source-paired clearance A/B.

The actual molecular calculation is performed by an external operator/runtime.
This module validates the compact result summary against the reserved one-shot
run, binds both complete-arm evidence artifacts, derives the frozen Go/No-Go
verdict, and writes the result exactly once. It cannot authorize fresh data,
Stage 0, product execution, pose delivery, profile promotion, or public claims.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .source_paired_clearance_one_shot_ab import (
    EXPECTED_CASE_IDS,
    EXPECTED_OUTPUT_ROOT,
    EXPECTED_POLICY_SHA256,
    OneShotABAuthorityError,
    OneShotABVerdictInputs,
    RUN_START_SCHEMA_ID,
    _is_sha256,
    _mapping,
    _write_exclusive_json,
    build_verdict,
    resolve_output_root,
    sha256_payload,
    verify_self_hash,
)


ARM_SUMMARY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_arm/1.0.0"
)
RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_result/1.0.0"
)
EXPECTED_BASELINE_PROFILE_ID = "current_v7"
EXPECTED_EXPERIMENTAL_PROFILE_ID = (
    "current_v7_with_only_predeclared_clearance_shadow_selected_states_replaced"
)
_RESULT_KEYS = {
    "baseline_arm",
    "cross_arm",
    "customer_pose_emission_authorized",
    "execution_environment_sha256",
    "experimental_arm",
    "fresh_holdout_execution_authorized",
    "policy_sha256",
    "product_execution_authorized",
    "profile_promotion_authority",
    "public_or_scientific_claim_authorized",
    "required_scorer_backend",
    "result_sha256",
    "run_start_receipt_sha256",
    "schema_id",
    "source_commit_git_sha1",
    "stage0_admission_authority",
    "verdict",
}
_CROSS_ARM_KEYS = {
    "changed_slot_count",
    "changed_slots_sha256",
    "cross_arm_evidence_sha256",
    "result_dependent_allocation_observed",
    "selected_penetrating_without_validity_change_count",
    "shadow_eligible_candidate_count",
    "source_control_preserved",
}


def _ordered_case_ids(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(type(item) is not str for item in value):
        raise OneShotABAuthorityError(f"{name} must be an array of case IDs")
    ordered = tuple(value)
    if tuple(sorted(ordered)) != ordered or len(set(ordered)) != len(ordered):
        raise OneShotABAuthorityError(f"{name} must be sorted and unique")
    if any(case_id not in EXPECTED_CASE_IDS for case_id in ordered):
        raise OneShotABAuthorityError(f"{name} contains a case outside the frozen cohort")
    return ordered


def verify_arm_summary(
    arm: Mapping[str, Any],
    *,
    expected_profile_id: str,
) -> None:
    expected_keys = {
        "arm_evidence_file_sha256",
        "arm_evidence_self_sha256",
        "candidate_count",
        "candidate_denominator_verified",
        "candidate_receipt_count",
        "complete_scorer_v1_terms_verified",
        "exact_valid_case_ids",
        "invalid_top1_case_ids",
        "preparation_failure_case_ids",
        "profile_id",
        "proposal_oracle_case_ids",
        "schema_id",
        "scored_case_count",
        "top1_recovery_case_ids",
        "top5_recovery_case_ids",
    }
    if set(arm) != expected_keys:
        raise OneShotABAuthorityError("arm summary key set is invalid")
    if arm.get("schema_id") != ARM_SUMMARY_SCHEMA_ID:
        raise OneShotABAuthorityError("arm summary schema is invalid")
    if arm.get("profile_id") != expected_profile_id:
        raise OneShotABAuthorityError("arm profile identity is invalid")
    if arm.get("scored_case_count") != 8:
        raise OneShotABAuthorityError("arm scored-case denominator must equal eight")
    if arm.get("candidate_count") != 512 or arm.get("candidate_receipt_count") != 512:
        raise OneShotABAuthorityError("arm candidate denominator must equal 512")
    if arm.get("candidate_denominator_verified") is not True:
        raise OneShotABAuthorityError("arm candidate denominator is not verified")
    if arm.get("complete_scorer_v1_terms_verified") is not True:
        raise OneShotABAuthorityError("complete ScorerV1Terms evidence is required")
    if not _is_sha256(arm.get("arm_evidence_file_sha256")):
        raise OneShotABAuthorityError("arm evidence file SHA-256 is invalid")
    if not _is_sha256(arm.get("arm_evidence_self_sha256")):
        raise OneShotABAuthorityError("arm evidence self SHA-256 is invalid")

    preparation = _ordered_case_ids(
        arm.get("preparation_failure_case_ids"),
        name="preparation_failure_case_ids",
    )
    if preparation != ("6M73_FNR",):
        raise OneShotABAuthorityError("arm preparation-failure roster drifted")
    for field in (
        "top1_recovery_case_ids",
        "top5_recovery_case_ids",
        "exact_valid_case_ids",
        "proposal_oracle_case_ids",
        "invalid_top1_case_ids",
    ):
        observed = _ordered_case_ids(arm.get(field), name=field)
        if "6M73_FNR" in observed:
            raise OneShotABAuthorityError(f"{field} includes the preparation failure")


def build_arm_summary(
    *,
    profile_id: str,
    preparation_failure_case_ids: tuple[str, ...],
    top1_recovery_case_ids: tuple[str, ...],
    top5_recovery_case_ids: tuple[str, ...],
    exact_valid_case_ids: tuple[str, ...],
    proposal_oracle_case_ids: tuple[str, ...],
    invalid_top1_case_ids: tuple[str, ...],
    arm_evidence_file_sha256: str,
    arm_evidence_self_sha256: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_id": ARM_SUMMARY_SCHEMA_ID,
        "profile_id": profile_id,
        "scored_case_count": 8,
        "candidate_count": 512,
        "candidate_receipt_count": 512,
        "candidate_denominator_verified": True,
        "complete_scorer_v1_terms_verified": True,
        "preparation_failure_case_ids": sorted(preparation_failure_case_ids),
        "top1_recovery_case_ids": sorted(top1_recovery_case_ids),
        "top5_recovery_case_ids": sorted(top5_recovery_case_ids),
        "exact_valid_case_ids": sorted(exact_valid_case_ids),
        "proposal_oracle_case_ids": sorted(proposal_oracle_case_ids),
        "invalid_top1_case_ids": sorted(invalid_top1_case_ids),
        "arm_evidence_file_sha256": arm_evidence_file_sha256,
        "arm_evidence_self_sha256": arm_evidence_self_sha256,
    }
    verify_arm_summary(payload, expected_profile_id=profile_id)
    return payload


def _validate_cross_arm_values(
    *,
    source_control_preserved: object,
    result_dependent_allocation_observed: object,
    shadow_eligible_candidate_count: object,
    selected_penetrating_without_validity_change_count: object,
    changed_slot_count: object,
    changed_slots_sha256: object,
    cross_arm_evidence_sha256: object,
) -> None:
    if type(source_control_preserved) is not bool:
        raise OneShotABAuthorityError("source_control_preserved must be boolean")
    if type(result_dependent_allocation_observed) is not bool:
        raise OneShotABAuthorityError(
            "result_dependent_allocation_observed must be boolean"
        )
    for name, value in (
        ("shadow_eligible_candidate_count", shadow_eligible_candidate_count),
        (
            "selected_penetrating_without_validity_change_count",
            selected_penetrating_without_validity_change_count,
        ),
        ("changed_slot_count", changed_slot_count),
    ):
        if type(value) is not int or value < 0 or value > 512:
            raise OneShotABAuthorityError(f"{name} is invalid")
    assert isinstance(shadow_eligible_candidate_count, int)
    assert isinstance(selected_penetrating_without_validity_change_count, int)
    assert isinstance(changed_slot_count, int)
    if changed_slot_count > shadow_eligible_candidate_count:
        raise OneShotABAuthorityError(
            "changed slots cannot exceed shadow-eligible candidates"
        )
    if selected_penetrating_without_validity_change_count > changed_slot_count:
        raise OneShotABAuthorityError(
            "penetrating selected states cannot exceed changed slots"
        )
    if not _is_sha256(changed_slots_sha256):
        raise OneShotABAuthorityError("changed-slot digest is invalid")
    if not _is_sha256(cross_arm_evidence_sha256):
        raise OneShotABAuthorityError("cross-arm evidence SHA-256 is invalid")


def build_result_document(
    *,
    run_start: Mapping[str, Any],
    baseline_arm: Mapping[str, Any],
    experimental_arm: Mapping[str, Any],
    source_control_preserved: bool,
    result_dependent_allocation_observed: bool,
    shadow_eligible_candidate_count: int,
    selected_penetrating_without_validity_change_count: int,
    changed_slot_count: int,
    changed_slots_sha256: str,
    cross_arm_evidence_sha256: str,
) -> dict[str, Any]:
    verify_self_hash(run_start, hash_field="receipt_sha256", name="run-start receipt")
    if run_start.get("schema_id") != RUN_START_SCHEMA_ID:
        raise OneShotABAuthorityError("run-start schema is invalid")
    if run_start.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError("run-start policy cross-wire")
    if run_start.get("durable_output_root") != EXPECTED_OUTPUT_ROOT.as_posix():
        raise OneShotABAuthorityError("run-start output-root identity drifted")
    if run_start.get("required_scorer_backend") != "rust_cpu_required":
        raise OneShotABAuthorityError("result requires the Rust CPU scorer")
    if run_start.get("expected_scored_candidate_rows") != 1024:
        raise OneShotABAuthorityError("run-start two-arm denominator drifted")

    baseline = _mapping(baseline_arm, name="baseline arm")
    experimental = _mapping(experimental_arm, name="experimental arm")
    verify_arm_summary(baseline, expected_profile_id=EXPECTED_BASELINE_PROFILE_ID)
    verify_arm_summary(
        experimental,
        expected_profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
    )
    _validate_cross_arm_values(
        source_control_preserved=source_control_preserved,
        result_dependent_allocation_observed=result_dependent_allocation_observed,
        shadow_eligible_candidate_count=shadow_eligible_candidate_count,
        selected_penetrating_without_validity_change_count=(
            selected_penetrating_without_validity_change_count
        ),
        changed_slot_count=changed_slot_count,
        changed_slots_sha256=changed_slots_sha256,
        cross_arm_evidence_sha256=cross_arm_evidence_sha256,
    )

    verdict_inputs = OneShotABVerdictInputs(
        preparation_failure_case_ids=tuple(
            experimental["preparation_failure_case_ids"]
        ),
        baseline_top1_recovery_case_ids=tuple(baseline["top1_recovery_case_ids"]),
        experimental_top1_recovery_case_ids=tuple(
            experimental["top1_recovery_case_ids"]
        ),
        baseline_top5_recovery_case_ids=tuple(baseline["top5_recovery_case_ids"]),
        experimental_top5_recovery_case_ids=tuple(
            experimental["top5_recovery_case_ids"]
        ),
        baseline_exact_valid_case_ids=tuple(baseline["exact_valid_case_ids"]),
        experimental_exact_valid_case_ids=tuple(
            experimental["exact_valid_case_ids"]
        ),
        baseline_proposal_oracle_case_ids=tuple(
            baseline["proposal_oracle_case_ids"]
        ),
        experimental_proposal_oracle_case_ids=tuple(
            experimental["proposal_oracle_case_ids"]
        ),
        baseline_invalid_top1_case_ids=tuple(baseline["invalid_top1_case_ids"]),
        experimental_invalid_top1_case_ids=tuple(
            experimental["invalid_top1_case_ids"]
        ),
        baseline_candidate_count=int(baseline["candidate_count"]),
        experimental_candidate_count=int(experimental["candidate_count"]),
        source_control_preserved=source_control_preserved,
        score_term_semantics_fully_verified=(
            baseline["complete_scorer_v1_terms_verified"] is True
            and experimental["complete_scorer_v1_terms_verified"] is True
        ),
        result_dependent_allocation_observed=result_dependent_allocation_observed,
        shadow_eligible_candidate_count=shadow_eligible_candidate_count,
        selected_penetrating_without_validity_change_count=(
            selected_penetrating_without_validity_change_count
        ),
    )
    verdict = build_verdict(verdict_inputs, policy_sha256=EXPECTED_POLICY_SHA256)
    result: dict[str, Any] = {
        "schema_id": RESULT_SCHEMA_ID,
        "policy_sha256": EXPECTED_POLICY_SHA256,
        "run_start_receipt_sha256": run_start["receipt_sha256"],
        "source_commit_git_sha1": run_start["source_commit_git_sha1"],
        "execution_environment_sha256": run_start[
            "execution_environment_sha256"
        ],
        "required_scorer_backend": "rust_cpu_required",
        "baseline_arm": dict(baseline),
        "experimental_arm": dict(experimental),
        "cross_arm": {
            "source_control_preserved": source_control_preserved,
            "result_dependent_allocation_observed": (
                result_dependent_allocation_observed
            ),
            "shadow_eligible_candidate_count": shadow_eligible_candidate_count,
            "selected_penetrating_without_validity_change_count": (
                selected_penetrating_without_validity_change_count
            ),
            "changed_slot_count": changed_slot_count,
            "changed_slots_sha256": changed_slots_sha256,
            "cross_arm_evidence_sha256": cross_arm_evidence_sha256,
        },
        "verdict": verdict,
        "fresh_holdout_execution_authorized": False,
        "stage0_admission_authority": False,
        "profile_promotion_authority": False,
        "product_execution_authorized": False,
        "customer_pose_emission_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }
    result["result_sha256"] = sha256_payload(result)
    return result


def verify_result_document(
    result: Mapping[str, Any],
    *,
    run_start: Mapping[str, Any],
) -> None:
    if set(result) != _RESULT_KEYS:
        raise OneShotABAuthorityError("result key set is invalid")
    verify_self_hash(result, hash_field="result_sha256", name="one-shot result")
    if result.get("schema_id") != RESULT_SCHEMA_ID:
        raise OneShotABAuthorityError("result schema is invalid")
    if result.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError("result policy identity is invalid")
    if result.get("run_start_receipt_sha256") != run_start.get("receipt_sha256"):
        raise OneShotABAuthorityError("result/run-start cross-wire")
    if result.get("source_commit_git_sha1") != run_start.get("source_commit_git_sha1"):
        raise OneShotABAuthorityError("result source-commit cross-wire")
    if result.get("execution_environment_sha256") != run_start.get(
        "execution_environment_sha256"
    ):
        raise OneShotABAuthorityError("result environment cross-wire")
    if result.get("required_scorer_backend") != "rust_cpu_required":
        raise OneShotABAuthorityError("result backend is invalid")

    cross_arm = _mapping(result.get("cross_arm"), name="cross_arm")
    if set(cross_arm) != _CROSS_ARM_KEYS:
        raise OneShotABAuthorityError("cross-arm key set is invalid")
    expected = build_result_document(
        run_start=run_start,
        baseline_arm=_mapping(result.get("baseline_arm"), name="baseline arm"),
        experimental_arm=_mapping(
            result.get("experimental_arm"), name="experimental arm"
        ),
        source_control_preserved=cross_arm["source_control_preserved"],
        result_dependent_allocation_observed=cross_arm[
            "result_dependent_allocation_observed"
        ],
        shadow_eligible_candidate_count=cross_arm[
            "shadow_eligible_candidate_count"
        ],
        selected_penetrating_without_validity_change_count=cross_arm[
            "selected_penetrating_without_validity_change_count"
        ],
        changed_slot_count=cross_arm["changed_slot_count"],
        changed_slots_sha256=cross_arm["changed_slots_sha256"],
        cross_arm_evidence_sha256=cross_arm["cross_arm_evidence_sha256"],
    )
    if dict(result) != expected:
        raise OneShotABAuthorityError(
            "result does not equal the independently rederived document"
        )


def write_result_once(
    *,
    policy: Mapping[str, Any],
    run_start: Mapping[str, Any],
    result: Mapping[str, Any],
    repository_root: Path,
) -> None:
    verify_result_document(result, run_start=run_start)
    execution = _mapping(policy.get("execution"), name="execution")
    if policy.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError("writer policy identity is invalid")
    output_root = resolve_output_root(policy, repository_root=repository_root)
    result_path = output_root / str(execution.get("result_filename"))
    _write_exclusive_json(
        result_path,
        result,
        repository_root=repository_root,
    )


__all__ = [
    "ARM_SUMMARY_SCHEMA_ID",
    "RESULT_SCHEMA_ID",
    "build_arm_summary",
    "build_result_document",
    "verify_arm_summary",
    "verify_result_document",
    "write_result_once",
]
