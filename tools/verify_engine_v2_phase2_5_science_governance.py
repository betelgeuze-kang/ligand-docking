#!/usr/bin/env python3
"""Verify the frozen, non-executing Engine V2 Phase 2-5 authority contract."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


POLICY_SCHEMA_ID = "betelgeuze.engine_v2_phase2_5_science_governance/1.0.0"
EXPECTED_POLICY_SHA256 = (
    "686533aeec0c3af0f2d22701a7990ae030b0706797b9b7fff194de1c6e06e1e3"
)
EXPECTED_BASE_COMMIT_SHA1 = "e782fb2dadd83ce4b9e41fc1af5b970fe63e28ca"
EXPECTED_D0_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6M73_FNR",
    "6T88_MWQ",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_D0_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
EXPECTED_D0_EVIDENCE_ARCHIVE_SHA256 = (
    "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc"
)
EXPECTED_D2_REGISTRY_SHA256 = (
    "89a58e6fbadd7e249df20bdf8db36f317e3e2e2dd6f32c32879d1a989dd28f31"
)
EXPECTED_D2_CASE_IDS_SHA256 = (
    "110c9ccc37255c39df3dae5b0213e4cf158cccfaf30071cb5ec9eb8e269ef349"
)
EXPECTED_FRESH_MANIFEST_SHA256 = (
    "459303a54cb1e8ebaf2bfa4320ad2287536d0e20a916fe5d2bac60edbdffdfba"
)
EXPECTED_FRESH_CASE_IDS_SHA256 = (
    "ecc91c660896245f62ad8b583cfa4f45e50038cf513c384f6bdb56d406278248"
)
EXPECTED_CLEARANCE_POLICY_SHA256 = (
    "e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad"
)
EXPECTED_ACTIVATION_POLICY_SHA256 = (
    "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c"
)
EXPECTED_HISTORICAL_CASE_SOURCE_AUTHORITY_SHA256 = (
    "4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc"
)
EXPECTED_POSEBUSTERS_CHECK_SET_SHA256 = (
    "3b4797c8eb95f6471f3dce0977b95b83fd0ed2630d6079607609fbcb2c1d8b93"
)
EXPECTED_PHASE2_GO_DECISION = {
    "all_guardrails_required": [
        {
            "baseline_case_ids_must_equal": ["6M73_FNR"],
            "baseline_value": 1,
            "experimental_case_ids_must_equal": ["6M73_FNR"],
            "metric": "preparation_failure_case_ids",
            "operator": "baseline_and_experimental_exact",
        },
        {
            "baseline_case_ids": ["6T88_MWQ"],
            "baseline_value": 1,
            "denominator": 8,
            "metric": "top1_recovery_case_ids",
            "operator": "baseline_subset_of_experimental",
        },
        {
            "baseline_case_ids": ["6T88_MWQ"],
            "baseline_value": 1,
            "denominator": 8,
            "metric": "top5_recovery_case_ids",
            "operator": "baseline_subset_of_experimental",
        },
        {
            "exact_value_per_arm": 512,
            "metric": "candidate_denominator",
            "operator": "exact",
        },
        {"metric": "source_proposal_control_preserved", "operator": "is_true"},
        {"metric": "score_term_semantics_fully_verified", "operator": "is_true"},
        {"metric": "result_dependent_allocation", "operator": "is_false"},
    ],
    "at_least_one_primary_gain_required": [
        {
            "case_scope": "previously_uncovered_case_ids",
            "metric": "new_exact_valid_candidate_case_count",
            "minimum_experimental_value": 1,
        },
        {
            "baseline_value": 1,
            "denominator": 8,
            "metric": "proposal_oracle_recovery_case_count",
            "minimum_experimental_value": 2,
        },
        {
            "baseline_value": 5,
            "denominator": 8,
            "maximum_experimental_value": 4,
            "metric": "invalid_top1_case_count",
        },
    ],
    "no_go_trigger_precedence": True,
}
EXPECTED_PHASE2_NO_GO_DECISION = {
    "any_trigger_closes_local_torsion_clearance_epic": True,
    "terminal_decision_id": "no_go_close_local_torsion_clearance_epic",
    "triggers": [
        {
            "all_conditions": [
                "shadow_eligible_candidate_count_gt_0",
                "new_case_recovery_count_eq_0",
            ],
            "id": "eligible_without_new_case_recovery",
        },
        {
            "id": "no_exact_valid_case_increase",
            "metric": "exact_valid_case_count_delta",
            "operator": "lte",
            "value": 0,
        },
        {
            "id": "no_invalid_top1_decrease",
            "metric": "invalid_top1_case_count_delta",
            "operator": "gte",
            "value": 0,
        },
        {
            "any_conditions": [
                {
                    "baseline_case_ids": ["6T88_MWQ"],
                    "experimental_metric": "top1_recovery_case_ids",
                    "metric": "baseline_top1_recovery_case_loss",
                    "operator": "baseline_not_subset_of_experimental",
                },
                {
                    "baseline_case_ids": ["6T88_MWQ"],
                    "experimental_metric": "top5_recovery_case_ids",
                    "metric": "baseline_top5_recovery_case_loss",
                    "operator": "baseline_not_subset_of_experimental",
                },
            ],
            "id": "existing_recovery_regression",
        },
        {
            "all_conditions": [
                {
                    "metric": "selected_replacement_minimum_vdw_gap",
                    "operator": "lt",
                    "value": 0,
                },
                {
                    "identity_join": [
                        "case_id",
                        "proposal_index",
                        "source_proposal_fingerprint_sha256",
                    ],
                    "metric": "selected_replacement_posebusters_validity_changed",
                    "operator": "is_false",
                },
            ],
            "evaluation_scope": "each_selected_replacement_candidate_case_pair",
            "quantifier": "any",
            "id": "selected_state_remains_penetrating_without_validity_change",
        },
    ],
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_payload(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{name} is not valid canonicalizable JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_bool(value: object, *, name: str, expected: bool) -> None:
    _require(type(value) is bool and value is expected, f"{name} must be {expected}")


def _require_int(value: object, *, name: str, expected: int) -> None:
    _require(type(value) is int and value == expected, f"{name} must be {expected}")


def _require_exact_payload(observed: object, expected: object, *, name: str) -> None:
    _require(
        _canonical_bytes(observed) == _canonical_bytes(expected),
        f"{name} drifted",
    )


def _verify_self_hash(
    payload: dict[str, Any],
    *,
    field: str,
    expected: str,
    name: str,
) -> None:
    observed = payload.get(field)
    _require(observed == expected, f"{name} {field} is not the frozen identity")
    projection = dict(payload)
    projection.pop(field, None)
    _require(
        _sha256_payload(projection) == observed,
        f"{name} {field} does not authenticate its payload",
    )


def _literal_assignment(path: Path, name: str) -> object:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise ValueError(f"cannot inspect D0 authority source: {exc}") from exc
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            try:
                return ast.literal_eval(node.value)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"D0 authority constant {name} is not literal"
                ) from exc
    raise ValueError(f"D0 authority constant {name} is absent")


def _resolve_reference(repo_root: Path, value: object, *, name: str) -> Path:
    _require(isinstance(value, str) and bool(value), f"{name} must be a path")
    root = repo_root.resolve()
    path = (root / str(value)).resolve()
    _require(path.is_relative_to(root), f"{name} escapes the repository")
    _require(path.is_file(), f"{name} does not exist")
    return path


def _verify_d0_authority(policy: dict[str, Any], repo_root: Path) -> None:
    d0 = policy["phase4_corpus_authority"]["d0_diagnostic_9"]
    source = d0["source_authority"]
    path = _resolve_reference(repo_root, source["path"], name="D0 authority path")
    _require(
        tuple(_literal_assignment(path, source["case_ids_constant"]))
        == EXPECTED_D0_CASE_IDS,
        "D0 authority case IDs drifted",
    )
    _require(
        _literal_assignment(path, source["case_ids_sha256_constant"])
        == EXPECTED_D0_CASE_IDS_SHA256,
        "D0 authority case-ID hash drifted",
    )
    _require(
        _literal_assignment(path, source["evidence_archive_sha256_constant"])
        == EXPECTED_D0_EVIDENCE_ARCHIVE_SHA256,
        "D0 evidence archive identity drifted",
    )
    _require_int(d0["case_count"], name="D0 case_count", expected=9)
    _require(d0["case_ids_sha256"] == EXPECTED_D0_CASE_IDS_SHA256, "D0 hash drifted")
    _require_bool(
        d0["promotion_authority"], name="D0 promotion authority", expected=False
    )
    _require_bool(
        d0["new_execution_authorized"],
        name="D0 new execution authority",
        expected=False,
    )


def _verify_d2_registry(policy: dict[str, Any], repo_root: Path) -> None:
    d2 = policy["phase4_corpus_authority"]["d2_historical_contaminated_300"]
    registry_path = _resolve_reference(
        repo_root, d2["registry_path"], name="D2 contamination registry"
    )
    registry = _load_json(registry_path, name="D2 contamination registry")
    _verify_self_hash(
        registry,
        field="registry_sha256",
        expected=EXPECTED_D2_REGISTRY_SHA256,
        name="D2 contamination registry",
    )
    _require(
        registry.get("schema_id")
        == "betelgeuze.engine_v2_public_redocking_contamination_registry/1.1.0",
        "D2 registry schema drifted",
    )
    _require_int(
        registry.get("contaminated_development_case_count"),
        name="D2 registry case count",
        expected=300,
    )
    _require(
        registry.get("contaminated_development_case_ids_sha256")
        == EXPECTED_D2_CASE_IDS_SHA256,
        "D2 registry case IDs drifted",
    )
    _require(
        registry.get("historical_300_claim_role") == "development_and_diagnostic_only",
        "D2 claim role drifted",
    )
    _require_bool(d2["claim_authority"], name="D2 claim authority", expected=False)
    _require_bool(
        d2["new_execution_authorized"],
        name="D2 new execution authority",
        expected=False,
    )


def _verify_fresh_manifest(policy: dict[str, Any], repo_root: Path) -> None:
    fresh = policy["phase4_corpus_authority"]["fresh_128"]
    manifest_path = _resolve_reference(
        repo_root, fresh["manifest_path"], name="Fresh-128 manifest"
    )
    manifest = _load_json(manifest_path, name="Fresh-128 manifest")
    _verify_self_hash(
        manifest,
        field="manifest_sha256",
        expected=EXPECTED_FRESH_MANIFEST_SHA256,
        name="Fresh-128 manifest",
    )
    _require(
        manifest.get("schema_id")
        == "betelgeuze.engine_v2_fresh_redocking_holdout_manifest/1.0.0",
        "Fresh-128 manifest schema drifted",
    )
    _require_int(manifest.get("case_count"), name="Fresh-128 case count", expected=128)
    cases = manifest.get("cases")
    _require(isinstance(cases, list) and len(cases) == 128, "Fresh-128 cases drifted")
    case_ids = [row.get("case_id") for row in cases if isinstance(row, dict)]
    _require(
        len(case_ids) == 128 and len(set(case_ids)) == 128,
        "Fresh-128 case IDs must be complete and unique",
    )
    _require(
        _sha256_payload(case_ids) == EXPECTED_FRESH_CASE_IDS_SHA256,
        "Fresh-128 ordered case-ID hash drifted",
    )
    _require(
        manifest.get("case_ids_sha256") == EXPECTED_FRESH_CASE_IDS_SHA256,
        "Fresh-128 manifest case-ID hash drifted",
    )
    _require_bool(
        manifest.get("result_values_inspected_before_freeze"),
        name="Fresh-128 pre-freeze result inspection",
        expected=False,
    )
    for field in (
        "exactly_once_required",
        "stage0_admission_required_before_execution",
    ):
        _require_bool(fresh[field], name=f"Fresh-128 {field}", expected=True)
    for field in (
        "execution_authorized",
        "post_result_tuning_allowed",
        "development_set_transfer_allowed",
        "result_values_inspected",
    ):
        _require_bool(fresh[field], name=f"Fresh-128 {field}", expected=False)


def _verify_phase2(policy: dict[str, Any]) -> None:
    phase2 = policy["phase2_historical_one_shot_ab"]
    cohort = phase2["cohort"]
    candidate = phase2["candidate_denominator"]
    execution = phase2["lifetime_execution"]
    _require_exact_payload(
        cohort,
        {
            "case_count": 9,
            "case_ids_sha256": EXPECTED_D0_CASE_IDS_SHA256,
            "ordered_case_ids": list(EXPECTED_D0_CASE_IDS),
            "preparation_failure_case_ids": ["6M73_FNR"],
            "previously_uncovered_case_ids": [
                "5SD5_HWI",
                "5SIS_JSM",
                "6M2B_EZO",
                "6TW5_9M2",
                "6TW7_NZB",
                "6VTA_AKN",
                "6WTN_RXT",
            ],
            "recovered_control_case_ids": ["6T88_MWQ"],
        },
        name="Phase 2 cohort",
    )
    _require(
        _sha256_payload(cohort["ordered_case_ids"]) == EXPECTED_D0_CASE_IDS_SHA256,
        "Phase 2 case-ID hash is invalid",
    )
    _require_exact_payload(
        candidate,
        {
            "baseline_candidate_slots": 512,
            "candidate_slots_per_scored_case": 64,
            "experimental_candidate_slots": 512,
            "failure_rows_preserved": True,
            "scored_case_count": 8,
        },
        name="Phase 2 candidate denominator",
    )
    _require_exact_payload(
        phase2["comparison"],
        {
            "baseline": {
                "refiner_profile": "current_v7",
                "selected_state_replacement": "none",
            },
            "experimental": {
                "refiner_profile": "current_v7",
                "selected_state_replacement": (
                    "predeclared_clearance_shadow_decision_only"
                ),
            },
            "clearance_policy_sha256": EXPECTED_CLEARANCE_POLICY_SHA256,
            "result_dependent_allocation_allowed": False,
            "source_proposal_control_required": True,
        },
        name="Phase 2 comparison",
    )
    _require_exact_payload(
        phase2["evidence_requirements"],
        {
            "activated_state_independent_rederivation_required": True,
            "activation_policy_schema_id": (
                "betelgeuze.engine_v2_source_paired_clearance_activation_policy/1.2.0"
            ),
            "activation_policy_self_hash_verification_required": True,
            "activation_policy_sha256": EXPECTED_ACTIVATION_POLICY_SHA256,
            "activation_receipt_schema_id": (
                "betelgeuze.engine_v2_source_paired_clearance_selection_"
                "activation_receipt/2.0.0"
            ),
            "activation_snapshot_schema_id": (
                "betelgeuze.engine_v2_source_paired_torsion_rescue_activation_"
                "snapshot/1.2.0"
            ),
            "all_allocated_targets_required": True,
            "authenticated_geometry_independent_clearance_rederivation_required": (
                True
            ),
            "authenticated_rmsd_receipts_required": True,
            "authenticated_torsion_move_replay_required": True,
            "case_source_frozen_archive_member_authority_required": True,
            "case_source_receipt_schema_id": (
                "betelgeuze.engine_v2_source_paired_clearance_case_source_receipt/1.0.0"
            ),
            "complete_internal_validity_context_and_pose_binding_required": True,
            "complete_posebusters_validity_required": True,
            "complete_scorer_v1_terms_receipts_required": True,
            "current_v7_candidate_full_64_slot_lineage_required": True,
            "current_v7_lineage_receipt_schema_id": (
                "betelgeuze.engine_v2_source_paired_clearance_current_v7_lineage/1.0.0"
            ),
            "exact_rank_recomputation_required": True,
            "exact_snapshot_runtime_type_required": True,
            "exact_source_v11_receipt_required": True,
            "historical_case_source_authority_sha256": (
                EXPECTED_HISTORICAL_CASE_SOURCE_AUTHORITY_SHA256
            ),
            "historical_v11_archive_score_rank_evidence_admissible": False,
            "non_target_and_retained_target_evidence_equality_required": True,
            "posebusters_required_check_set_sha256": (
                EXPECTED_POSEBUSTERS_CHECK_SET_SHA256
            ),
            "score_term_semantics_fully_reverifiable_required": True,
            "scorer_authority_bound_to_authenticated_input_required": True,
            "source_proposal_receipt_full_64_slot_lineage_required": True,
            "source_proposal_receipt_schema_id": (
                "betelgeuze.engine_v2_source_paired_torsion_rescue_proposal_"
                "receipt/1.0.0"
            ),
        },
        name="Phase 2 evidence requirements",
    )
    _require_exact_payload(
        execution,
        {
            "atomic_consume_implementation_available": False,
            "completed_runs": 0,
            "execution_authorized": False,
            "external_authority_available": False,
            "external_authority_receipt_sha256": None,
            "external_authority_type": "append_only_worm_atomic_single_consume",
            "failed_or_partial_attempt_consumes_run": True,
            "maximum_runs": 1,
            "overwrite_allowed": False,
            "partial_result_aggregate_replacement_allowed": False,
            "rerun_allowed": False,
            "resume_allowed": False,
            "run_budget_consumed": False,
        },
        name="Phase 2 lifetime execution authority",
    )
    _require_exact_payload(
        phase2["go_decision"],
        EXPECTED_PHASE2_GO_DECISION,
        name="Phase 2 Go decision",
    )
    _require_bool(
        phase2["go_decision"]["no_go_trigger_precedence"],
        name="Phase 2 No-Go precedence",
        expected=True,
    )
    _require_exact_payload(
        phase2["no_go_decision"],
        EXPECTED_PHASE2_NO_GO_DECISION,
        name="Phase 2 No-Go decision",
    )
    _require_bool(
        phase2["no_go_decision"]["any_trigger_closes_local_torsion_clearance_epic"],
        name="Phase 2 any-trigger terminal precedence",
        expected=True,
    )
    _require(phase2["status"] == "blocked_preexecution", "Phase 2 status drifted")


def _verify_phase3_to_phase5(policy: dict[str, Any]) -> None:
    phase3 = policy["phase3_global_orientation_track"]
    activation = phase3["activation"]
    _require(
        activation["required_phase2_terminal_decision_id"]
        == "no_go_close_local_torsion_clearance_epic",
        "Phase 3 activation condition drifted",
    )
    for field in (
        "phase2_terminal_decision_present",
        "implementation_authorized",
        "execution_authorized",
    ):
        _require_bool(activation[field], name=f"Phase 3 {field}", expected=False)
    quotas = phase3["proposed_profile"]["lane_quotas"]
    _require(
        quotas
        == {
            "pocket_centered_controls": 8,
            "uniform_source_controls": 16,
            "independent_orientation_variants": 12,
            "true_conformer_independent_orientation": 8,
            "donor_acceptor_single_anchor": 8,
            "charge_aromatic_shape_single_anchor": 8,
            "retained_paired_controls": 4,
        },
        "Phase 3 lane quotas drifted",
    )
    _require(sum(quotas.values()) == 64, "Phase 3 lane quotas do not sum to 64")
    _require_bool(
        phase3["multi_anchor"]["included_in_profile"],
        name="Phase 3 multi-anchor inclusion",
        expected=False,
    )
    _require_bool(
        phase3["geometric_prefilter"]["slot_denominator_preserved"],
        name="Phase 3 prefilter denominator preservation",
        expected=True,
    )
    _require_bool(
        phase3["geometric_prefilter"]["candidate_deletion_allowed"],
        name="Phase 3 candidate deletion",
        expected=False,
    )

    d1 = policy["phase4_corpus_authority"]["d1_fixed_decision_32"]
    _require_int(d1["case_count"], name="D1 case count", expected=32)
    for field in ("case_ids", "case_ids_sha256", "selection_rule_sha256"):
        _require(d1[field] is None, f"D1 {field} must remain null until frozen")
    for field in ("execution_authorized", "promotion_authority"):
        _require_bool(d1[field], name=f"D1 {field}", expected=False)
    _require_bool(
        d1["case_ids_may_be_invented_or_derived_from_results"],
        name="D1 result-derived IDs",
        expected=False,
    )

    phase5 = policy["phase5_scorer_v2_gate"]
    entry = phase5["entry_conditions"]
    _require_int(
        entry["minimum_oracle_case_count"], name="Scorer v2 oracle gate", expected=20
    )
    _require(
        entry["admissible_oracle_case_count"] is None,
        "Scorer v2 oracle count must be unclaimed",
    )
    _require(
        entry["valid_case_coverage_definition"] is None,
        "Scorer v2 coverage definition must be missing",
    )
    for field in (
        "admissible_oracle_case_count_verified",
        "proposal_profile_frozen",
        "valid_case_coverage_definition_frozen",
        "valid_case_coverage_sufficient",
    ):
        _require_bool(entry[field], name=f"Scorer v2 {field}", expected=False)
    for field in (
        "scorer_v1_replacement_authorized",
        "scorer_v2_implementation_authorized",
        "scorer_v2_training_authorized",
    ):
        _require_bool(phase5[field], name=f"Scorer v2 {field}", expected=False)
    _require_bool(
        phase5["scorer_v1_deterministic_reference_retained"],
        name="Scorer v1 retention",
        expected=True,
    )


def verify_phase2_5_science_governance(policy_path: Path, repo_root: Path) -> str:
    policy = _load_json(policy_path, name="Phase 2-5 governance policy")
    _require(
        set(policy)
        == {
            "authority_boundary",
            "base_commit_sha1",
            "phase2_historical_one_shot_ab",
            "phase3_global_orientation_track",
            "phase4_corpus_authority",
            "phase5_scorer_v2_gate",
            "policy_id",
            "policy_sha256",
            "schema_id",
        },
        "Phase 2-5 governance top-level fields drifted",
    )
    _require(policy["schema_id"] == POLICY_SCHEMA_ID, "policy schema drifted")
    _require(
        policy["base_commit_sha1"] == EXPECTED_BASE_COMMIT_SHA1, "base commit drifted"
    )
    _verify_self_hash(
        policy,
        field="policy_sha256",
        expected=EXPECTED_POLICY_SHA256,
        name="Phase 2-5 governance policy",
    )
    boundary = policy["authority_boundary"]
    for field, value in boundary.items():
        _require_bool(value, name=f"authority boundary {field}", expected=False)
    _verify_phase2(policy)
    _verify_phase3_to_phase5(policy)
    _verify_d0_authority(policy, repo_root)
    _verify_d2_registry(policy, repo_root)
    _verify_fresh_manifest(policy, repo_root)
    return str(policy["policy_sha256"])


def _parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument(
        "--policy",
        type=Path,
        default=repo_root / "config/engine_v2_phase2_5_science_governance.json",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        identity = verify_phase2_5_science_governance(
            arguments.policy.resolve(), arguments.repo_root.resolve()
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(identity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
