#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRODUCT_PILOT_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_PRODUCT_ARCHITECTURE_JSON = "runs/product_architecture_contract_current.json"
DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_SELF_HOSTED_LICENSE_DISTRIBUTION_AUDIT_JSON = (
    "runs/self_hosted_license_distribution_audit_current.json"
)
DEFAULT_THIRD_PARTY_LICENSE_REVIEW_GATE_JSON = "runs/third_party_license_review_gate_current.json"
DEFAULT_CAMEO_VALIDATION_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_CAMEO_CAPABILITY_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON = "runs/cameo_public_registration_approval_gate_current.json"
DEFAULT_CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_JSON = (
    "runs/cameo_official_result_fetch_preflight_current.json"
)
DEFAULT_GOAL_ROLLUP_JSON = "runs/goal_readiness_rollup_current.json"
DEFAULT_OPERATOR_ACTION_BOARD_JSON = "runs/goal_operator_action_board_current.json"
DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON = "runs/transition_cleanup_execution_preflight_current.json"
DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON = "runs/ligand_heavy_cleanup_execution_preflight_current.json"
DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON = "runs/protected_cleanup_policy_decision_gate_current.json"
DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON = "runs/cleanup_postcheck_contract_current.json"
DEFAULT_CLEANUP_COMPLETION_GATE_JSON = "runs/cleanup_completion_gate_current.json"
DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON = "runs/goal_api_surface_contract_current.json"
DEFAULT_GOAL_BOTTLENECK_BRIEFING_JSON = "runs/goal_bottleneck_briefing_current.json"
DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_PACKET_JSON = (
    "runs/production_ai_registry_promotion_priority_packet_current.json"
)
DEFAULT_PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON = (
    "runs/product_production_ai_checkpoint_readiness_current.json"
)
DEFAULT_PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_JSON = (
    "runs/product_production_ai_promotion_workbench_current.json"
)
DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON = "runs/product_ai_architecture_gap_closure_current.json"
DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON = "runs/product_ai_architecture_execution_backlog_current.json"
DEFAULT_PRODUCT_RELEASE_SOURCE_OF_TRUTH_JSON = "runs/product_release_source_of_truth_gate_current.json"
DEFAULT_PRODUCT_QUALITY_GATE_VERIFICATION_JSON = "runs/product_quality_gate_verification_current.json"
DEFAULT_PRODUCT_POSE_SAMPLING_READINESS_JSON = "runs/product_pose_sampling_readiness_current.json"
DEFAULT_PRODUCT_LEDGER_PRIVACY_SCAN_JSON = "runs/product_ledger_privacy_scan_current.json"
DEFAULT_API_CUSTOMER_FLOW_RELEASE_EVIDENCE_JSON = "runs/api_customer_flow_release_evidence_current.json"
DEFAULT_API_RUNNER_PROFILE_PROMOTION_OPERATOR_RECEIPT_JSON = (
    "runs/api_runner_profile_promotion_operator_receipt_current.json"
)
DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON = (
    "runs/product_scope_breadth_evidence_receipt_current.json"
)
DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_JSON = (
    "runs/engine_refinement_claim_evidence_receipt_current.json"
)
DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_JSON = (
    "runs/engine_refinement_claim_evidence_priority_packet_current.json"
)
R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
)
DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_READINESS_JSON = (
    "runs/refine_tier_public_benchmark_readiness_current.json"
)
DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON = (
    "runs/refine_tier_public_benchmark_work_order_apply_current.json"
)
DEFAULT_PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON = (
    "runs/product_full_commercial_blocker_evidence_matrix_current.json"
)
DEFAULT_PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_JSON = (
    "runs/product_rollout_execution_smoke_receipt_current.json"
)
DEFAULT_ACCURACY_PARITY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_SCIENCE_CLAIM_PROMOTION_GAP_CLOSURE_JSON = "runs/science_claim_promotion_gap_closure_current.json"
DEFAULT_MASTER_GAP_CLOSURE_ROLLUP_JSON = "runs/master_gap_closure_rollup_current.json"
DEFAULT_OUT_JSON = "runs/goal_release_decision_gate_current.json"
DEFAULT_OUT_CSV = "runs/goal_release_decision_gate_current.csv"
DEFAULT_OUT_MD = "runs/goal_release_decision_gate_current.md"

CLAIM_BOUNDARY = (
    "Goal release decision gate only; it audits whether the commercial product, CAMEO validation, and cleanup lanes "
    "are release-ready from existing local artifacts. It does not run docking, assemble bundles, submit CAMEO "
    "predictions, register a server, send email, delete, archive, externalize, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _primary_backlog_row(backlog_packet: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(backlog_packet)
    primary_id = _text(summary.get("primary_work_item_id"))
    rows = _rows(backlog_packet)
    for row in rows:
        if primary_id and _text(row.get("work_item_id")) == primary_id:
            return row
    return rows[0] if rows else {}


def _primary_backlog_detail(backlog_packet: dict[str, Any]) -> str:
    summary = _summary(backlog_packet)
    primary = _primary_backlog_row(backlog_packet)
    if not summary and not primary:
        return ""
    return (
        f"primary_backlog_work_item_id={_text(summary.get('primary_work_item_id'))};"
        f"primary_backlog_observed={_text(primary.get('observed'))};"
        f"primary_backlog_next_action={_text(primary.get('next_action'))}"
    )


def _row_by_id(rows: list[dict[str, Any]], key: str, row_id: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get(key)) == row_id:
            return row
    return {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, tuple):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _dict_get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else None


def _full_commercial_blocker_tier(blocker_id: str) -> str:
    if blocker_id == "R8_full_scope_claim_closure":
        return "full_commercial_scope"
    if blocker_id == "R9_engine_refinement_claim_promotion":
        return "full_commercial_science_claim"
    if blocker_id.startswith("MASTER:"):
        return "full_commercial_master_rollup"
    if blocker_id.startswith("ACCURACY:"):
        return "full_commercial_accuracy_parity"
    return ""


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _row(
    *,
    lane_id: str,
    check: str,
    artifact_path: str,
    observed: str,
    required: str,
    passed: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def build_goal_release_decision_gate(
    *,
    product_pilot_packet: dict[str, Any],
    product_architecture_packet: dict[str, Any] | None = None,
    product_commercial_independence_packet: dict[str, Any] | None = None,
    self_hosted_license_distribution_audit_packet: dict[str, Any] | None = None,
    third_party_license_review_gate_packet: dict[str, Any] | None = None,
    cameo_validation_packet: dict[str, Any],
    cameo_capability_packet: dict[str, Any],
    cameo_public_registration_approval_gate_packet: dict[str, Any] | None = None,
    cameo_official_result_fetch_preflight_packet: dict[str, Any] | None = None,
    goal_rollup_packet: dict[str, Any],
    operator_action_board_packet: dict[str, Any],
    transition_cleanup_preflight_packet: dict[str, Any],
    ligand_cleanup_preflight_packet: dict[str, Any],
    protected_cleanup_review_packet: dict[str, Any],
    protected_cleanup_policy_decision_gate_packet: dict[str, Any] | None = None,
    cleanup_postcheck_contract_packet: dict[str, Any] | None = None,
    cleanup_completion_gate_packet: dict[str, Any] | None = None,
    goal_api_surface_contract_packet: dict[str, Any] | None = None,
    goal_bottleneck_briefing_packet: dict[str, Any] | None = None,
    production_ai_registry_promotion_priority_packet: dict[str, Any] | None = None,
    product_production_ai_checkpoint_readiness_packet: dict[str, Any] | None = None,
    product_production_ai_promotion_workbench_packet: dict[str, Any] | None = None,
    product_ai_architecture_gap_packet: dict[str, Any] | None = None,
    product_ai_execution_backlog_packet: dict[str, Any] | None = None,
    product_release_source_of_truth_packet: dict[str, Any] | None = None,
    product_quality_gate_verification_packet: dict[str, Any] | None = None,
    product_pose_sampling_readiness_packet: dict[str, Any] | None = None,
    product_ledger_privacy_scan_packet: dict[str, Any] | None = None,
    api_customer_flow_release_evidence_packet: dict[str, Any] | None = None,
    api_runner_profile_promotion_operator_receipt_packet: dict[str, Any] | None = None,
    product_scope_breadth_evidence_receipt_packet: dict[str, Any] | None = None,
    engine_refinement_claim_evidence_receipt_packet: dict[str, Any] | None = None,
    engine_refinement_claim_evidence_priority_packet: dict[str, Any] | None = None,
    refine_tier_public_benchmark_readiness_packet: dict[str, Any] | None = None,
    refine_tier_public_benchmark_work_order_apply_packet: dict[str, Any] | None = None,
    product_full_commercial_blocker_evidence_matrix_packet: dict[str, Any] | None = None,
    product_rollout_execution_smoke_receipt_packet: dict[str, Any] | None = None,
    accuracy_parity_scorecard_packet: dict[str, Any] | None = None,
    science_claim_promotion_gap_packet: dict[str, Any] | None = None,
    master_gap_closure_rollup_packet: dict[str, Any] | None = None,
    product_pilot_path: str = DEFAULT_PRODUCT_PILOT_JSON,
    product_architecture_path: str = DEFAULT_PRODUCT_ARCHITECTURE_JSON,
    product_commercial_independence_path: str = DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON,
    self_hosted_license_distribution_audit_path: str = DEFAULT_SELF_HOSTED_LICENSE_DISTRIBUTION_AUDIT_JSON,
    third_party_license_review_gate_path: str = DEFAULT_THIRD_PARTY_LICENSE_REVIEW_GATE_JSON,
    cameo_validation_path: str = DEFAULT_CAMEO_VALIDATION_JSON,
    cameo_capability_path: str = DEFAULT_CAMEO_CAPABILITY_JSON,
    cameo_public_registration_approval_gate_path: str = DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON,
    cameo_official_result_fetch_preflight_path: str = DEFAULT_CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_JSON,
    goal_rollup_path: str = DEFAULT_GOAL_ROLLUP_JSON,
    operator_action_board_path: str = DEFAULT_OPERATOR_ACTION_BOARD_JSON,
    transition_cleanup_preflight_path: str = DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON,
    ligand_cleanup_preflight_path: str = DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON,
    protected_cleanup_review_path: str = DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON,
    protected_cleanup_policy_decision_gate_path: str = DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON,
    cleanup_postcheck_contract_path: str = DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON,
    cleanup_completion_gate_path: str = DEFAULT_CLEANUP_COMPLETION_GATE_JSON,
    goal_api_surface_contract_path: str = DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON,
    goal_bottleneck_briefing_path: str = DEFAULT_GOAL_BOTTLENECK_BRIEFING_JSON,
    production_ai_registry_promotion_priority_packet_path: str = (
        DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_PACKET_JSON
    ),
    product_production_ai_checkpoint_readiness_path: str = (
        DEFAULT_PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON
    ),
    product_production_ai_promotion_workbench_path: str = (
        DEFAULT_PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_JSON
    ),
    product_ai_architecture_gap_path: str = DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON,
    product_ai_execution_backlog_path: str = DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON,
    product_release_source_of_truth_path: str = DEFAULT_PRODUCT_RELEASE_SOURCE_OF_TRUTH_JSON,
    product_quality_gate_verification_path: str = DEFAULT_PRODUCT_QUALITY_GATE_VERIFICATION_JSON,
    product_pose_sampling_readiness_path: str = DEFAULT_PRODUCT_POSE_SAMPLING_READINESS_JSON,
    product_ledger_privacy_scan_path: str = DEFAULT_PRODUCT_LEDGER_PRIVACY_SCAN_JSON,
    api_customer_flow_release_evidence_path: str = DEFAULT_API_CUSTOMER_FLOW_RELEASE_EVIDENCE_JSON,
    api_runner_profile_promotion_operator_receipt_path: str = (
        DEFAULT_API_RUNNER_PROFILE_PROMOTION_OPERATOR_RECEIPT_JSON
    ),
    product_scope_breadth_evidence_receipt_path: str = (
        DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON
    ),
    engine_refinement_claim_evidence_receipt_path: str = (
        DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_JSON
    ),
    engine_refinement_claim_evidence_priority_packet_path: str = (
        DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_JSON
    ),
    refine_tier_public_benchmark_readiness_path: str = (
        DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_READINESS_JSON
    ),
    refine_tier_public_benchmark_work_order_apply_path: str = (
        DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON
    ),
    product_full_commercial_blocker_evidence_matrix_path: str = (
        DEFAULT_PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON
    ),
    product_rollout_execution_smoke_receipt_path: str = (
        DEFAULT_PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_JSON
    ),
    accuracy_parity_scorecard_path: str = DEFAULT_ACCURACY_PARITY_SCORECARD_JSON,
    science_claim_promotion_gap_path: str = DEFAULT_SCIENCE_CLAIM_PROMOTION_GAP_CLOSURE_JSON,
    master_gap_closure_rollup_path: str = DEFAULT_MASTER_GAP_CLOSURE_ROLLUP_JSON,
) -> dict[str, Any]:
    product = _summary(product_pilot_packet)
    product_architecture = _summary(product_architecture_packet or {})
    product_independence = _summary(product_commercial_independence_packet or {})
    self_hosted_license_audit = _summary(self_hosted_license_distribution_audit_packet or {})
    self_hosted_license_audit_gate_present = self_hosted_license_distribution_audit_packet is not None
    self_hosted_license_audit_dual_license_assets = _text_list(
        self_hosted_license_audit.get("third_party_dual_license_assets")
    )
    self_hosted_license_audit_hashes_match = bool(
        _text(self_hosted_license_audit.get("product_license_sha256"))
        and _text(self_hosted_license_audit.get("product_license_sha256"))
        == _text(self_hosted_license_audit.get("approved_license_text_source_sha256"))
    )
    self_hosted_license_audit_approved_source = _text(
        self_hosted_license_audit.get("approved_license_text_source")
    )
    self_hosted_license_audit_source_ready = self_hosted_license_audit_approved_source in {
        "LICENSE",
        "legal/proprietary-license-betelgeuze.txt",
    }
    self_hosted_license_audit_recorded = (
        _text(self_hosted_license_audit.get("status"))
        == "self_hosted_license_distribution_audit_recorded"
        and _text(self_hosted_license_audit.get("product_license_path")) == "LICENSE"
        and self_hosted_license_audit_source_ready
        and self_hosted_license_audit_hashes_match
        and _text(self_hosted_license_audit.get("spdx_license_id")) == "ProprietaryRef-Betelgeuze"
        and _text(self_hosted_license_audit.get("copyright_holder")) == "JIHOON KANG"
        and _int(self_hosted_license_audit.get("hard_blocker_count")) == 0
        and _int(self_hosted_license_audit.get("operator_review_item_count")) == 1
        and bool(self_hosted_license_audit.get("legal_advice_provided") is False)
        and _text(self_hosted_license_audit.get("third_party_license_review_gate_status"))
        == "third_party_license_review_gate_ready"
        and bool(self_hosted_license_audit.get("third_party_license_review_gate_ready") is True)
        and _int(self_hosted_license_audit.get("third_party_license_review_gate_blocker_count")) == 0
        and self_hosted_license_audit_dual_license_assets == ["jszip"]
        and _text(self_hosted_license_audit.get("viewer_third_party_notice_path"))
        == "viewer/vendor/THIRD_PARTY_NOTICES.md"
        and bool(self_hosted_license_audit.get("external_state_mutated") is False)
    )
    third_party_license_review = _summary(third_party_license_review_gate_packet or {})
    third_party_license_review_gate_present = third_party_license_review_gate_packet is not None
    third_party_license_review_approved_assets = _text_list(
        third_party_license_review.get("approved_assets")
    )
    third_party_license_review_allowed_license_paths = _text_list(
        third_party_license_review.get("allowed_license_paths")
    )
    third_party_license_review_ready = (
        _text(third_party_license_review.get("status")) == "third_party_license_review_gate_ready"
    )
    third_party_license_review_recorded = (
        third_party_license_review_ready
        and third_party_license_review_approved_assets == ["jszip"]
        and third_party_license_review_allowed_license_paths
        == ["GPL-3.0-or-later", "MIT", "remove_or_replace_asset"]
        and _int(third_party_license_review.get("expected_review_asset_count")) == 1
        and _int(third_party_license_review.get("review_row_count")) == 1
        and _int(third_party_license_review.get("approved_review_asset_count")) == 1
        and _int(third_party_license_review.get("missing_review_asset_count")) == 0
        and _int(third_party_license_review.get("deferred_review_asset_count")) == 0
        and _int(third_party_license_review.get("blocker_count")) == 0
        and _text(third_party_license_review.get("review_csv"))
        == "runs/third_party_license_review_operator_intake.csv"
        and bool(third_party_license_review.get("review_csv_present") is True)
        and _text(third_party_license_review.get("operator_template_csv"))
        == "runs/third_party_license_review_operator_template_current.csv"
        and _text(third_party_license_review.get("approval_token_required"))
        == "APPROVE_THIRD_PARTY_LICENSE_REVIEW"
        and _text(third_party_license_review.get("source_license_audit_status"))
        == "self_hosted_license_distribution_audit_recorded"
        and _int(third_party_license_review.get("source_hard_blocker_count")) == 0
        and _int(third_party_license_review.get("source_operator_review_item_count")) == 1
        and bool(third_party_license_review.get("legal_advice_provided") is False)
        and bool(third_party_license_review.get("asset_modified") is False)
        and bool(third_party_license_review.get("external_state_mutated") is False)
    )
    cameo_validation = _summary(cameo_validation_packet)
    cameo_capability = _summary(cameo_capability_packet)
    cameo_registration_gate = _summary(cameo_public_registration_approval_gate_packet or {})
    cameo_fetch_preflight = _summary(cameo_official_result_fetch_preflight_packet or {})
    cameo_fetch_preflight_gate_present = cameo_official_result_fetch_preflight_packet is not None
    cameo_fetch_preflight_recorded = (
        _text(cameo_fetch_preflight.get("status"))
        in {
            "blocked_cameo_official_result_fetch_preflight",
            "cameo_official_result_fetch_preflight_ready",
        }
        and _text(cameo_fetch_preflight.get("fetch_approval_token_required"))
        == "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
        and _text(cameo_fetch_preflight.get("operator_fetch_csv"))
        == "runs/cameo_official_result_fetch_operator_approval_intake.csv"
        and _text(cameo_fetch_preflight.get("operator_template_csv"))
        == "runs/cameo_official_result_fetch_operator_approval_template_current.csv"
        and bool(cameo_fetch_preflight.get("network_request_opened") is False)
        and bool(cameo_fetch_preflight.get("official_results_fetched") is False)
        and bool(cameo_fetch_preflight.get("native_local_accuracy_used") is False)
        and bool(cameo_fetch_preflight.get("outbound_email_enabled") is False)
        and bool(cameo_fetch_preflight.get("external_state_mutated") is False)
    )
    rollup = _summary(goal_rollup_packet)
    actions = _summary(operator_action_board_packet)
    transition_cleanup = _summary(transition_cleanup_preflight_packet)
    ligand_cleanup = _summary(ligand_cleanup_preflight_packet)
    protected_cleanup = _summary(protected_cleanup_review_packet)
    protected_policy_gate = _summary(protected_cleanup_policy_decision_gate_packet or {})
    cleanup_postcheck = _summary(cleanup_postcheck_contract_packet or {})
    cleanup_completion = _summary(cleanup_completion_gate_packet or {})
    goal_api_surface = _summary(goal_api_surface_contract_packet or {})
    api_runner_profile_receipt = _summary(api_runner_profile_promotion_operator_receipt_packet or {})
    api_runner_profile_receipt_gate_present = (
        api_runner_profile_promotion_operator_receipt_packet is not None
    )
    api_runner_profile_first_blocked_row_blockers = _text_list(
        api_runner_profile_receipt.get("first_blocked_row_blockers")
    )
    api_runner_profile_blockers = _text_list(api_runner_profile_receipt.get("blockers"))
    api_runner_profile_receipt_recorded = (
        _text(api_runner_profile_receipt.get("status"))
        in {
            "blocked_api_runner_profile_promotion_operator_receipt",
            "api_runner_profile_promotion_operator_receipt_ready",
        }
        and _text(api_runner_profile_receipt.get("readiness_status"))
        == "api_runner_profile_promotion_ready"
        and _int(api_runner_profile_receipt.get("profile_count")) >= 1
        and _int(api_runner_profile_receipt.get("receipt_row_count")) >= 1
        and _text(api_runner_profile_receipt.get("approval_token_required"))
        == "APPROVE_API_RUNNER_PROFILE_PROMOTION"
        and bool(api_runner_profile_receipt.get("profile_enabled_by_this_tool") is False)
        and bool(api_runner_profile_receipt.get("runner_executed") is False)
        and bool(api_runner_profile_receipt.get("external_state_mutated") is False)
    )
    product_scope_receipt = _summary(product_scope_breadth_evidence_receipt_packet or {})
    product_scope_receipt_gate_present = product_scope_breadth_evidence_receipt_packet is not None
    product_scope_receipt_first_blocked_row_blockers = _text_list(
        product_scope_receipt.get("first_blocked_row_blockers")
    )
    product_scope_receipt_recorded = (
        _text(product_scope_receipt.get("status"))
        in {
            "blocked_product_scope_breadth_evidence_receipt",
            "product_scope_breadth_evidence_receipt_ready",
        }
        and _int(product_scope_receipt.get("receipt_row_count")) >= 1
        and _int(product_scope_receipt.get("required_scope_blocker_count")) >= 1
        and _text(product_scope_receipt.get("approval_token_required"))
        == "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
        and bool(product_scope_receipt.get("external_state_mutated") is False)
    )
    engine_refinement_receipt = _summary(engine_refinement_claim_evidence_receipt_packet or {})
    engine_refinement_receipt_gate_present = (
        engine_refinement_claim_evidence_receipt_packet is not None
    )
    engine_refinement_receipt_first_blocked_row_blockers = _text_list(
        engine_refinement_receipt.get("first_blocked_row_blockers")
    )
    engine_refinement_receipt_recorded = (
        _text(engine_refinement_receipt.get("status"))
        in {
            "blocked_engine_refinement_claim_evidence_receipt",
            "engine_refinement_claim_evidence_receipt_ready",
        }
        and _int(engine_refinement_receipt.get("receipt_row_count")) >= 1
        and _int(engine_refinement_receipt.get("required_blocker_count")) >= 1
        and _text(engine_refinement_receipt.get("approval_token_required"))
        == "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
        and bool(engine_refinement_receipt.get("external_state_mutated") is False)
    )
    engine_refinement_priority = _summary(engine_refinement_claim_evidence_priority_packet or {})
    engine_refinement_priority_gate_present = (
        engine_refinement_claim_evidence_priority_packet is not None
    )
    engine_refinement_priority_recorded = (
        _text(engine_refinement_priority.get("status"))
        in {
            "blocked_engine_refinement_claim_evidence_priority_packet",
            "engine_refinement_claim_evidence_priority_packet_ready",
        }
        and bool(engine_refinement_priority.get("priority_packet_ready") is True)
        and _int(engine_refinement_priority.get("priority_item_count")) == 6
        and _int(engine_refinement_priority.get("operator_input_required_count")) == 6
        and _int(engine_refinement_priority.get("blocked_priority_item_count")) == 6
        and _int(engine_refinement_priority.get("required_blocker_count")) == 6
        and _int(engine_refinement_priority.get("missing_required_blocker_count")) == 0
        and _text(engine_refinement_priority.get("claim_evidence_receipt_status"))
        == "blocked_engine_refinement_claim_evidence_receipt"
        and bool(engine_refinement_priority.get("claim_evidence_receipt_ready") is False)
        and bool(engine_refinement_priority.get("claim_promotion_allowed") is False)
        and _text(engine_refinement_priority.get("public_benchmark_status"))
        == "blocked_refine_tier_public_benchmark_readiness"
        and bool(engine_refinement_priority.get("public_benchmark_gate_ready") is False)
        and bool(engine_refinement_priority.get("public_benchmark_work_order_present") is True)
        and _int(engine_refinement_priority.get("public_benchmark_work_order_row_count")) == 8
        and _text(engine_refinement_priority.get("public_benchmark_work_order_apply_status"))
        == "blocked_refine_tier_public_benchmark_work_order_apply"
        and bool(engine_refinement_priority.get("public_benchmark_work_order_apply_ready") is False)
        and _int(engine_refinement_priority.get("public_benchmark_work_order_apply_blocked_row_count")) == 8
        and _text(engine_refinement_priority.get("top_blocker_id")) == "public_benchmark_gate_not_ready"
        and _text(engine_refinement_priority.get("top_priority_bucket"))
        == "public_benchmark_work_order_apply_required"
        and _text(engine_refinement_priority.get("top_required_input"))
        == R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV
        and _text(engine_refinement_priority.get("top_acceptance_artifact"))
        == "runs/refine_tier_public_benchmark_readiness_current.json"
        and _text(engine_refinement_priority.get("approval_token_required"))
        == "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
        and bool(engine_refinement_priority.get("external_state_mutated") is False)
    )
    refine_tier_public_benchmark = _summary(refine_tier_public_benchmark_readiness_packet or {})
    refine_tier_public_benchmark_gate_present = (
        refine_tier_public_benchmark_readiness_packet is not None
    )
    refine_tier_public_benchmark_recorded = (
        _text(refine_tier_public_benchmark.get("status"))
        == "blocked_refine_tier_public_benchmark_readiness"
        and bool(refine_tier_public_benchmark.get("input_csv_present") is True)
        and bool(refine_tier_public_benchmark.get("claim_grade_public_benchmark_ready") is False)
        and bool(refine_tier_public_benchmark.get("benchmark_metric_surface_ready") is False)
        and _int(refine_tier_public_benchmark.get("row_count")) == 0
        and _int(refine_tier_public_benchmark.get("valid_row_count")) == 0
        and _int(refine_tier_public_benchmark.get("pose_metric_row_count")) == 0
        and _int(refine_tier_public_benchmark.get("pose_metric_pass_count")) == 0
        and _int(refine_tier_public_benchmark.get("free_energy_pair_count")) == 0
        and _int(refine_tier_public_benchmark.get("blocker_count")) == 6
        and _int(refine_tier_public_benchmark.get("min_total_rows_required")) == 8
        and _int(refine_tier_public_benchmark.get("min_pose_rows_required")) == 5
        and _int(refine_tier_public_benchmark.get("min_free_energy_pairs_required")) == 5
        and bool(refine_tier_public_benchmark.get("operator_work_order_ready") is True)
        and _int(refine_tier_public_benchmark.get("work_order_row_count")) == 8
        and _text(refine_tier_public_benchmark.get("input_csv"))
        == "config/refine_tier_public_benchmark_intake_current.csv"
        and _text(refine_tier_public_benchmark.get("work_order_csv"))
        == "runs/refine_tier_public_benchmark_work_order_current.csv"
        and _text(refine_tier_public_benchmark.get("write_intake_approval_token_required"))
        == "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
        and bool(refine_tier_public_benchmark.get("external_state_mutated") is False)
    )
    refine_tier_public_benchmark_work_order_apply = _summary(
        refine_tier_public_benchmark_work_order_apply_packet or {}
    )
    refine_tier_public_benchmark_work_order_apply_gate_present = (
        refine_tier_public_benchmark_work_order_apply_packet is not None
    )
    refine_tier_public_benchmark_work_order_apply_recorded = (
        _text(refine_tier_public_benchmark_work_order_apply.get("status"))
        == "blocked_refine_tier_public_benchmark_work_order_apply"
        and bool(refine_tier_public_benchmark_work_order_apply.get("aggregate_readiness_required") is True)
        and bool(refine_tier_public_benchmark_work_order_apply.get("apply_ready") is False)
        and bool(refine_tier_public_benchmark_work_order_apply.get("work_order_csv_present") is True)
        and _int(refine_tier_public_benchmark_work_order_apply.get("work_order_row_count")) == 8
        and _int(refine_tier_public_benchmark_work_order_apply.get("blocked_row_count")) == 8
        and _int(refine_tier_public_benchmark_work_order_apply.get("valid_intake_row_count")) == 0
        and _int(refine_tier_public_benchmark_work_order_apply.get("blocker_count")) == 1
        and _int(refine_tier_public_benchmark_work_order_apply.get("duplicate_benchmark_id_count")) == 0
        and bool(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_required"
            )
            is True
        )
        and bool(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_csv_present"
            )
            is True
        )
        and _int(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_pass_row_count"
            )
        )
        == 8
        and _int(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_blocked_row_count"
            )
        )
        == 0
        and _int(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_missing_row_count"
            )
        )
        == 0
        and bool(
            refine_tier_public_benchmark_work_order_apply.get("metric_evidence_required")
            is True
        )
        and bool(
            refine_tier_public_benchmark_work_order_apply.get("metric_evidence_csv_present")
            is True
        )
        and _int(refine_tier_public_benchmark_work_order_apply.get("metric_evidence_pass_row_count")) == 0
        and _int(refine_tier_public_benchmark_work_order_apply.get("metric_evidence_blocked_row_count")) == 8
        and _int(refine_tier_public_benchmark_work_order_apply.get("metric_evidence_missing_row_count")) == 0
        and bool(refine_tier_public_benchmark_work_order_apply.get("candidate_intake_written") is False)
        and bool(refine_tier_public_benchmark_work_order_apply.get("candidate_readiness_checked") is False)
        and bool(
            refine_tier_public_benchmark_work_order_apply.get(
                "candidate_claim_grade_public_benchmark_ready"
            )
            is False
        )
        and bool(refine_tier_public_benchmark_work_order_apply.get("intake_written") is False)
        and bool(refine_tier_public_benchmark_work_order_apply.get("write_intake_requested") is False)
        and bool(refine_tier_public_benchmark_work_order_apply.get("approval_token_present") is False)
        and bool(refine_tier_public_benchmark_work_order_apply.get("approval_token_accepted") is False)
        and _text(refine_tier_public_benchmark_work_order_apply.get("target_intake_csv"))
        == "config/refine_tier_public_benchmark_intake_current.csv"
        and _text(refine_tier_public_benchmark_work_order_apply.get("work_order_csv"))
        == "runs/refine_tier_public_benchmark_work_order_current.csv"
        and bool(refine_tier_public_benchmark_work_order_apply.get("external_state_mutated") is False)
    )
    goal_bottleneck_briefing = _summary(goal_bottleneck_briefing_packet or {})
    goal_bottleneck_briefing_gate_present = goal_bottleneck_briefing_packet is not None
    goal_bottleneck_full_commercial_receipts_recorded = (
        _text(goal_bottleneck_briefing.get("status")) == "goal_bottleneck_briefing_ready"
        and _int(goal_bottleneck_briefing.get("completion_audit_release_blocker_bottleneck_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_entry_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_operator_input_required_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_current_action_required_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_required_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_present_count")) == 2
        and _int(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_token_count")) == 2
        and _text(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_source_gate_statuses"))
        == (
            "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
            "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
        )
        and _text(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_required_inputs"))
        == (
            "config/product_scope_breadth_evidence_receipt_current.csv;"
            "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
        )
        and _text(goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_tokens"))
        == (
            "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
            "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
        )
        and bool(goal_bottleneck_briefing.get("execution_enabled") is False)
        and bool(goal_bottleneck_briefing.get("external_state_mutated") is False)
    )
    goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids = _text_list(
        goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_missing_gate_ids")
    )
    expected_production_ai_registry_promotion_missing_gate_ids = [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    expected_checkpoint_registry_promotion_missing_gate_ids = [
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
        "default_residual_mode_guarded",
    ]
    goal_bottleneck_production_ai_registry_promotion_priority_recorded = (
        _text(goal_bottleneck_briefing.get("status")) == "goal_bottleneck_briefing_ready"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_source_json"))
        == "runs/production_ai_registry_promotion_priority_packet_current.json"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_status"))
        == "blocked_production_ai_registry_promotion_priority_packet"
        and bool(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_packet_ready") is True)
        and bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_registry_promotion_ready")
            is False
        )
        and _int(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_operator_input_required_count"))
        == 3
        and _int(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_blocked_priority_item_count"))
        == 3
        and _int(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_missing_gate_count")) == 3
        and goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids
        == expected_production_ai_registry_promotion_missing_gate_ids
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_gate_id"))
        == "default_residual_mode_guarded"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_priority_bucket"))
        == "guarded_residual_mode_selection_required"
        and _text(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_acceptance_artifact"))
        == "runs/residual_model_registry_current.json"
        and bool(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_model_promoted") is False)
        and bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_customer_facing_mutation_enabled")
            is False
        )
        and bool(goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_external_state_mutated") is False)
    )
    production_ai_registry_priority = _summary(
        production_ai_registry_promotion_priority_packet or {}
    )
    production_ai_registry_priority_gate_present = (
        production_ai_registry_promotion_priority_packet is not None
    )
    production_ai_registry_priority_missing_gate_ids = _text_list(
        production_ai_registry_priority.get("registry_promotion_missing_gate_ids")
    )
    production_ai_registry_priority_observed_checkpoint_missing_gate_ids = _text_list(
        production_ai_registry_priority.get("observed_checkpoint_registry_promotion_missing_gate_ids")
    )
    production_ai_registry_priority_recorded = (
        _text(production_ai_registry_priority.get("status"))
        in {
            "blocked_production_ai_registry_promotion_priority_packet",
            "production_ai_registry_promotion_priority_packet_ready",
        }
        and bool(production_ai_registry_priority.get("priority_packet_ready") is True)
        and bool(production_ai_registry_priority.get("registry_promotion_ready") is False)
        and _int(production_ai_registry_priority.get("required_gate_count")) == 4
        and _int(production_ai_registry_priority.get("priority_item_count")) == 4
        and _int(production_ai_registry_priority.get("operator_input_required_count")) == 3
        and _int(production_ai_registry_priority.get("blocked_priority_item_count")) == 3
        and _int(production_ai_registry_priority.get("registry_promotion_missing_gate_count")) == 3
        and production_ai_registry_priority_missing_gate_ids
        == expected_production_ai_registry_promotion_missing_gate_ids
        and _text(production_ai_registry_priority.get("top_gate_id"))
        == "default_residual_mode_guarded"
        and _text(production_ai_registry_priority.get("top_priority_bucket"))
        == "guarded_residual_mode_selection_required"
        and _text(production_ai_registry_priority.get("top_acceptance_artifact"))
        == "runs/residual_model_registry_current.json"
        and _text(production_ai_registry_priority.get("approval_token_required"))
        == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
        and _text(production_ai_registry_priority.get("operator_receipt_artifact"))
        == "runs/production_ai_registry_promotion_operator_receipt_current.json"
        and bool(production_ai_registry_priority.get("operator_receipt_artifact_present") is True)
        and _text(production_ai_registry_priority.get("operator_receipt_csv"))
        == "config/production_ai_registry_promotion_operator_receipt_current.csv"
        and bool(production_ai_registry_priority.get("operator_receipt_csv_present") is True)
        and _text(production_ai_registry_priority.get("operator_receipt_status"))
        == "blocked_production_ai_registry_promotion_operator_receipt"
        and bool(production_ai_registry_priority.get("operator_receipt_ready") is False)
        and _text(production_ai_registry_priority.get("residual_registry_artifact"))
        == "runs/residual_model_registry_current.json"
        and bool(production_ai_registry_priority.get("residual_registry_artifact_present") is True)
        and _text(production_ai_registry_priority.get("checkpoint_readiness_artifact"))
        == "runs/product_production_ai_checkpoint_readiness_current.json"
        and bool(production_ai_registry_priority.get("checkpoint_readiness_artifact_present") is True)
        and _text(production_ai_registry_priority.get("promotion_workbench_artifact"))
        == "runs/product_production_ai_promotion_workbench_current.json"
        and bool(production_ai_registry_priority.get("promotion_workbench_artifact_present") is True)
        and _int(production_ai_registry_priority.get("observed_registry_trained_model_checkpoint_count")) == 1
        and _text(production_ai_registry_priority.get("observed_registry_default_residual_mode")) == "shadow"
        and bool(production_ai_registry_priority.get("observed_registry_production_promotion_allowed") is False)
        and bool(production_ai_registry_priority.get("observed_registry_customer_facing_mutation_flags_ready") is False)
        and bool(production_ai_registry_priority.get("observed_checkpoint_registry_promotion_currently_satisfied") is False)
        and bool(production_ai_registry_priority.get("model_promoted") is False)
        and bool(production_ai_registry_priority.get("customer_facing_mutation_enabled") is False)
        and bool(production_ai_registry_priority.get("registry_edited_by_this_tool") is False)
        and bool(production_ai_registry_priority.get("checkpoint_created_by_this_tool") is False)
        and bool(production_ai_registry_priority.get("execution_enabled") is False)
        and bool(production_ai_registry_priority.get("external_state_mutated") is False)
    )
    production_ai_checkpoint_readiness = _summary(
        product_production_ai_checkpoint_readiness_packet or {}
    )
    production_ai_checkpoint_readiness_gate_present = (
        product_production_ai_checkpoint_readiness_packet is not None
    )
    production_ai_checkpoint_readiness_missing_gate_ids = _text_list(
        production_ai_checkpoint_readiness.get("registry_promotion_missing_gate_ids")
    )
    production_ai_checkpoint_acceptance_blocked_stage_ids = _text_list(
        production_ai_checkpoint_readiness.get("production_inference_acceptance_blocked_stage_ids")
    )
    production_ai_checkpoint_readiness_recorded = (
        _text(production_ai_checkpoint_readiness.get("status"))
        == "blocked_product_production_ai_checkpoint_readiness"
        and bool(production_ai_checkpoint_readiness.get("product_model_layer_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("production_gpu_execution_environment_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("force_gpu_worker_return_receipt_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("delta_force_derivation_validation_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("selected_sidecar_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("checkpoint_preflight_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("production_training_data_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("production_output_heads_complete") is True)
        and bool(production_ai_checkpoint_readiness.get("production_inference_acceptance_matrix_ready") is True)
        and _int(production_ai_checkpoint_readiness.get("check_count")) == 8
        and _int(production_ai_checkpoint_readiness.get("pass_check_count")) == 7
        and _int(production_ai_checkpoint_readiness.get("fail_check_count")) == 1
        and _int(production_ai_checkpoint_readiness.get("production_inference_acceptance_stage_count")) == 8
        and _int(production_ai_checkpoint_readiness.get("production_inference_acceptance_ready_stage_count")) == 7
        and _int(production_ai_checkpoint_readiness.get("production_inference_acceptance_blocked_stage_count")) == 1
        and production_ai_checkpoint_acceptance_blocked_stage_ids == ["registry_guarded_promotion_acceptance"]
        and _text(production_ai_checkpoint_readiness.get("production_inference_actionable_blocker_stage_id"))
        == "registry_guarded_promotion_acceptance"
        and _text(production_ai_checkpoint_readiness.get("production_inference_actionable_blocker_check_id"))
        == "registry_customer_facing_promotion_allowed"
        and _text(production_ai_checkpoint_readiness.get("production_inference_actionable_blocker_artifact"))
        == "runs/residual_model_registry_current.json"
        and bool(production_ai_checkpoint_readiness.get("registry_promotion_upstream_acceptance_ready") is True)
        and bool(production_ai_checkpoint_readiness.get("registry_promotion_currently_satisfied") is False)
        and _int(production_ai_checkpoint_readiness.get("registry_promotion_missing_gate_count")) == 3
        and production_ai_checkpoint_readiness_missing_gate_ids
        == expected_checkpoint_registry_promotion_missing_gate_ids
        and _int(production_ai_checkpoint_readiness.get("trained_model_checkpoint_count")) == 1
        and _text(production_ai_checkpoint_readiness.get("default_residual_mode")) == "shadow"
        and bool(production_ai_checkpoint_readiness.get("production_ai_checkpoint_ready") is False)
        and bool(production_ai_checkpoint_readiness.get("production_ai_inference_subject_active") is False)
        and bool(production_ai_checkpoint_readiness.get("production_promotion_allowed") is False)
        and bool(production_ai_checkpoint_readiness.get("customer_facing_auto_correction_allowed") is False)
        and bool(production_ai_checkpoint_readiness.get("customer_facing_score_mutation_allowed") is False)
        and bool(production_ai_checkpoint_readiness.get("customer_facing_ranking_mutation_allowed") is False)
        and bool(production_ai_checkpoint_readiness.get("model_promoted") is False)
        and bool(production_ai_checkpoint_readiness.get("docking_results_emitted") is False)
        and bool(production_ai_checkpoint_readiness.get("execution_enabled") is False)
        and bool(production_ai_checkpoint_readiness.get("external_state_mutated") is False)
    )
    production_ai_promotion_workbench = _summary(
        product_production_ai_promotion_workbench_packet or {}
    )
    production_ai_promotion_workbench_gate_present = (
        product_production_ai_promotion_workbench_packet is not None
    )
    production_ai_promotion_workbench_missing_gate_ids = _text_list(
        production_ai_promotion_workbench.get("registry_promotion_missing_gate_ids")
    )
    production_ai_promotion_workbench_blocked_stage_ids = _text_list(
        production_ai_promotion_workbench.get("blocked_stage_ids")
    )
    production_ai_promotion_workbench_recorded = (
        _text(production_ai_promotion_workbench.get("status"))
        == "blocked_product_production_ai_promotion_workbench"
        and bool(production_ai_promotion_workbench.get("promotion_workbench_ready") is True)
        and _text(production_ai_promotion_workbench.get("checkpoint_readiness_artifact_path"))
        == "runs/product_production_ai_checkpoint_readiness_current.json"
        and _int(production_ai_promotion_workbench.get("post_return_promotion_ladder_stage_count")) == 10
        and _int(production_ai_promotion_workbench.get("post_return_promotion_ladder_ready_stage_count")) == 7
        and _int(production_ai_promotion_workbench.get("post_return_promotion_ladder_blocked_stage_count")) == 3
        and production_ai_promotion_workbench_blocked_stage_ids
        == [
            "residual_model_registry",
            "product_ai_architecture_gap_closure",
            "product_goal_completion_audit",
        ]
        and _text(production_ai_promotion_workbench.get("first_blocked_stage_id"))
        == "residual_model_registry"
        and _text(production_ai_promotion_workbench.get("first_blocked_stage_artifact"))
        == "runs/residual_model_registry_current.json"
        and _text(production_ai_promotion_workbench.get("first_blocked_stage_ready_key"))
        == "production_promotion_allowed"
        and bool(production_ai_promotion_workbench.get("registry_promotion_upstream_acceptance_ready") is True)
        and bool(production_ai_promotion_workbench.get("registry_promotion_currently_satisfied") is False)
        and _int(production_ai_promotion_workbench.get("registry_promotion_missing_gate_count")) == 3
        and production_ai_promotion_workbench_missing_gate_ids
        == expected_checkpoint_registry_promotion_missing_gate_ids
        and _int(production_ai_promotion_workbench.get("trained_model_checkpoint_count")) == 1
        and _text(production_ai_promotion_workbench.get("default_residual_mode")) == "shadow"
        and bool(production_ai_promotion_workbench.get("production_ai_promotion_ready") is False)
        and bool(production_ai_promotion_workbench.get("production_ai_checkpoint_ready") is False)
        and bool(production_ai_promotion_workbench.get("production_ai_inference_subject_active") is False)
        and bool(production_ai_promotion_workbench.get("production_promotion_allowed") is False)
        and bool(production_ai_promotion_workbench.get("model_promoted") is False)
        and bool(production_ai_promotion_workbench.get("docking_results_emitted") is False)
        and bool(production_ai_promotion_workbench.get("execution_enabled") is False)
        and bool(production_ai_promotion_workbench.get("external_state_mutated") is False)
    )
    release_source_of_truth = _summary(product_release_source_of_truth_packet or {})
    release_source_of_truth_gate_present = product_release_source_of_truth_packet is not None
    release_source_of_truth_ready = (
        _text(release_source_of_truth.get("status")) == "product_release_source_of_truth_gate_ready"
        and bool(release_source_of_truth.get("release_source_of_truth_ready") is True)
        and _int(release_source_of_truth.get("blocker_count")) == 0
    )
    product_quality_gate = _summary(product_quality_gate_verification_packet or {})
    product_quality_gate_present = product_quality_gate_verification_packet is not None
    product_quality_gate_verified = (
        _text(product_quality_gate.get("status")) == "product_quality_gate_verified"
        and bool(product_quality_gate.get("quality_gate_ready") is True)
        and _int(product_quality_gate.get("blocker_count")) == 0
        and _int(product_quality_gate.get("check_count")) == 4
        and _int(product_quality_gate.get("pass_count")) == 4
        and _text(product_quality_gate.get("source_contract_status"))
        == "product_operational_quality_contract_ready"
        and bool(product_quality_gate.get("execution_enabled") is False)
        and bool(product_quality_gate.get("external_state_mutated") is False)
    )
    product_pose_sampling = _summary(product_pose_sampling_readiness_packet or {})
    product_pose_sampling_gate_present = product_pose_sampling_readiness_packet is not None
    product_pose_sampling_recorded = (
        _text(product_pose_sampling.get("status")) == "product_pose_sampling_readiness_ready"
        and bool(product_pose_sampling.get("pose_sampling_readiness_ready") is True)
        and bool(product_pose_sampling.get("pose_generation_contract_ready") is True)
        and bool(product_pose_sampling.get("pocket_detection_ready") is True)
        and bool(product_pose_sampling.get("multi_start_pose_ensemble_ready") is True)
        and bool(product_pose_sampling.get("pose_centroid_pocket_bound_ready") is True)
        and bool(product_pose_sampling.get("pose_rmsd_diversity_surface_ready") is True)
        and bool(product_pose_sampling.get("bounded_cross_docking_induced_fit_guard_ready") is True)
        and bool(product_pose_sampling.get("pose_claim_boundary_guard_ready") is True)
        and _int(product_pose_sampling.get("check_count")) == 6
        and _int(product_pose_sampling.get("pass_count")) == 6
        and _int(product_pose_sampling.get("blocker_count")) == 0
        and _int(product_pose_sampling.get("requested_pose_start_count")) == 6
        and _int(product_pose_sampling.get("pose_count")) == 6
        and _int(product_pose_sampling.get("cross_docking_pose_count")) == 4
        and _int(product_pose_sampling.get("cluster_count")) >= 2
        and _text(product_pose_sampling.get("pocket_method")) == "ligand_guided"
        and bool(product_pose_sampling.get("claim_grade_pose_accuracy_ready") is False)
        and bool(product_pose_sampling.get("claim_grade_induced_fit_ready") is False)
        and bool(product_pose_sampling.get("claim_grade_cross_docking_ready") is False)
        and bool(product_pose_sampling.get("docking_results_emitted") is False)
        and bool(product_pose_sampling.get("execution_enabled") is False)
        and bool(product_pose_sampling.get("external_state_mutated") is False)
    )
    product_ledger_privacy_scan = _summary(product_ledger_privacy_scan_packet or {})
    product_ledger_privacy_scan_gate_present = product_ledger_privacy_scan_packet is not None
    product_ledger_privacy_scan_scan_file_count = _int(
        product_ledger_privacy_scan.get("scan_file_count")
    )
    product_ledger_privacy_scan_pass_count = _int(
        product_ledger_privacy_scan.get("pass_count")
    )
    product_ledger_privacy_scan_glob_count = len(
        product_ledger_privacy_scan.get("scan_globs")
        if isinstance(product_ledger_privacy_scan.get("scan_globs"), list)
        else []
    )
    product_ledger_privacy_scan_recorded = (
        _text(product_ledger_privacy_scan.get("status")) == "product_ledger_privacy_scan_ready"
        and bool(product_ledger_privacy_scan.get("ledger_privacy_scan_ready") is True)
        and product_ledger_privacy_scan_scan_file_count > 0
        and product_ledger_privacy_scan_pass_count == product_ledger_privacy_scan_scan_file_count
        and _int(product_ledger_privacy_scan.get("blocker_count")) == 0
        and _int(product_ledger_privacy_scan.get("leak_count")) == 0
        and _int(product_ledger_privacy_scan.get("invalid_json_count")) == 0
        and len(_text_list(product_ledger_privacy_scan.get("blocked_artifact_paths"))) == 0
        and len(_text_list(product_ledger_privacy_scan.get("invalid_json_paths"))) == 0
        and bool(product_ledger_privacy_scan.get("execution_enabled") is False)
        and bool(product_ledger_privacy_scan.get("external_state_mutated") is False)
    )
    api_customer_flow = _summary(api_customer_flow_release_evidence_packet or {})
    api_customer_flow_gate_present = api_customer_flow_release_evidence_packet is not None
    api_customer_flow_ready = (
        _text(api_customer_flow.get("status")) == "api_customer_flow_release_evidence_ready"
        and bool(api_customer_flow.get("formal_release_evidence_ready") is True)
        and bool(api_customer_flow.get("clean_install_flow_ready") is True)
        and bool(api_customer_flow.get("result_manifest_signature_verified") is True)
        and bool(api_customer_flow.get("bundle_validation_ready") is True)
        and bool(api_customer_flow.get("restricted_unattended_runtime_ready") is True)
        and _int(api_customer_flow.get("blocker_count")) == 0
    )
    full_commercial_matrix = _summary(product_full_commercial_blocker_evidence_matrix_packet or {})
    full_commercial_matrix_gate_present = (
        product_full_commercial_blocker_evidence_matrix_packet is not None
    )
    full_commercial_matrix_recorded = (
        _text(full_commercial_matrix.get("status"))
        in {
            "blocked_product_full_commercial_blocker_evidence_matrix",
            "product_full_commercial_blocker_evidence_matrix_ready",
        }
        and full_commercial_matrix.get("expected_release_blocker_ids")
        == ["R8_full_scope_claim_closure", "R9_engine_refinement_claim_promotion"]
        and bool(full_commercial_matrix.get("release_blocker_visibility_ready") is True)
        and _int(full_commercial_matrix.get("matrix_row_count")) >= 2
        and bool(full_commercial_matrix.get("execution_enabled") is False)
        and bool(full_commercial_matrix.get("external_state_mutated") is False)
    )
    rollout_smoke = _summary(product_rollout_execution_smoke_receipt_packet or {})
    rollout_smoke_gate_present = product_rollout_execution_smoke_receipt_packet is not None
    rollout_smoke_recorded = (
        _text(rollout_smoke.get("status"))
        in {
            "blocked_product_rollout_execution_smoke_receipt",
            "product_rollout_execution_smoke_receipt_ready",
        }
        and bool(rollout_smoke.get("source_authorized_for_separate_operator_execution") is True)
        and bool(rollout_smoke.get("rollout_executed") is False)
        and bool(rollout_smoke.get("external_state_mutated") is False)
    ) or (
        _text(rollout_smoke.get("status")) == "product_rollout_execution_smoke_receipt_ready"
        and bool(rollout_smoke.get("rollout_executed") is True)
        and bool(rollout_smoke.get("external_state_mutated") is True)
    )
    science_claim_gap = _summary(science_claim_promotion_gap_packet or {})
    science_claim_gap_rows = _rows(science_claim_promotion_gap_packet or {})
    science_claim_gap_gate_present = science_claim_promotion_gap_packet is not None
    science_claim_open_gap_ids = _text_list(science_claim_gap.get("open_gap_ids"))
    science_claim_primary_open_gap_id = _text(science_claim_gap.get("current_primary_open_gap_id"))
    science_claim_primary_open_gap = _row_by_id(
        science_claim_gap_rows,
        "gap_id",
        science_claim_primary_open_gap_id,
    )
    science_claim_closed_gap_ids = _text_list(science_claim_gap.get("closed_gap_ids"))
    science_claim_open_rows = [
        row for row in science_claim_gap_rows if _text(row.get("status")) == "open"
    ]
    science_claim_closed_rows = [
        row for row in science_claim_gap_rows if _text(row.get("status")) == "closed"
    ]
    science_claim_release_blocker_rows = [
        row for row in science_claim_gap_rows if bool(row.get("release_blocker") is True)
    ]
    science_claim_gpcr_gap = _row_by_id(science_claim_gap_rows, "gap_id", "SCI-GPCR")
    science_claim_openmm_gap = _row_by_id(science_claim_gap_rows, "gap_id", "SCI-OPENMM")
    expected_science_claim_open_gap_ids: list[str] = []
    expected_science_claim_closed_gap_ids = [
        "SCI-GPCR",
        "SCI-TRANS",
        "SCI-CA2-PXR",
        "SCI-WETLAB",
        "SCI-OPENMM",
    ]
    science_claim_gap_recorded = (
        _text(science_claim_gap.get("status")) == "science_claim_promotion_gap_closure_complete"
        and bool(science_claim_gap.get("all_gaps_closed") is True)
        and bool(science_claim_gap.get("claim_promotion_allowed") is False)
        and _int(science_claim_gap.get("gap_count")) == 5
        and _int(science_claim_gap.get("closed_gap_count")) == 5
        and _int(science_claim_gap.get("open_gap_count")) == 0
        and science_claim_open_gap_ids == expected_science_claim_open_gap_ids
        and science_claim_closed_gap_ids == expected_science_claim_closed_gap_ids
        and science_claim_primary_open_gap_id == "none"
        and len(science_claim_open_rows) == 0
        and len(science_claim_closed_rows) == 5
        and len(science_claim_release_blocker_rows) == 0
        and _text(science_claim_gpcr_gap.get("claim_promotion_status"))
        == "boundary_ready_comparison_only"
        and _text(science_claim_gpcr_gap.get("evidence"))
        == "runs/gpcr_conditional_prior_promotion_gate_current.json"
        and bool(science_claim_gpcr_gap.get("claim_promotion_allowed") is False)
        and bool(science_claim_gpcr_gap.get("release_blocker") is False)
        and bool(science_claim_gpcr_gap.get("execution_enabled") is False)
        and bool(science_claim_gpcr_gap.get("external_state_mutated") is False)
        and _text(science_claim_openmm_gap.get("claim_promotion_status")) == "restricted_2bead_only"
        and _text(science_claim_openmm_gap.get("evidence"))
        == "runs/wetlab_openmm_claim_promotion_boundary_current.json; runs/accuracy_parity_scorecard_current.json"
        and bool(science_claim_openmm_gap.get("claim_promotion_allowed") is False)
        and bool(science_claim_openmm_gap.get("release_blocker") is False)
        and bool(science_claim_openmm_gap.get("execution_enabled") is False)
        and bool(science_claim_openmm_gap.get("external_state_mutated") is False)
        and bool(science_claim_gap.get("execution_enabled") is False)
        and bool(science_claim_gap.get("external_state_mutated") is False)
    )
    accuracy_parity = _summary(accuracy_parity_scorecard_packet or {})
    accuracy_parity_rows = _rows(accuracy_parity_scorecard_packet or {})
    accuracy_parity_claim_boundary = (
        accuracy_parity_scorecard_packet.get("claim_boundary")
        if isinstance(accuracy_parity_scorecard_packet, dict)
        else {}
    )
    if not isinstance(accuracy_parity_claim_boundary, dict):
        accuracy_parity_claim_boundary = {}
    accuracy_parity_gate_present = accuracy_parity_scorecard_packet is not None
    accuracy_parity_top_blockers = _text_list(accuracy_parity.get("top_blockers"))
    accuracy_ligand_ranking = _row_by_id(accuracy_parity_rows, "axis", "ligand_ranking")
    accuracy_ligand_metrics = accuracy_ligand_ranking.get("metrics")
    if not isinstance(accuracy_ligand_metrics, dict):
        accuracy_ligand_metrics = {}
    accuracy_ligand_thresholds = accuracy_ligand_ranking.get("thresholds")
    if not isinstance(accuracy_ligand_thresholds, dict):
        accuracy_ligand_thresholds = {}
    accuracy_ligand_blockers = _text_list(accuracy_ligand_ranking.get("blockers"))
    accuracy_ligand_metric_blockers = [
        blocker
        for blocker in accuracy_ligand_blockers
        if blocker != "broad_gpcr_claim_not_allowed"
    ]
    accuracy_ligand_pr_auc = _float(accuracy_ligand_metrics.get("ranking_pr_auc"))
    accuracy_ligand_pr_auc_ci_low = _float(
        accuracy_ligand_metrics.get("ranking_pr_auc_ci_low")
    )
    accuracy_ligand_topk_hit_rate = _float(
        accuracy_ligand_metrics.get("ranking_topk_hit_rate")
    )
    accuracy_ligand_pr_auc_threshold = _float(
        accuracy_ligand_thresholds.get("ranking_pr_auc_min")
    )
    accuracy_ligand_pr_auc_ci_low_threshold = _float(
        accuracy_ligand_thresholds.get("ranking_pr_auc_ci_low_min")
    )
    accuracy_ligand_topk_hit_rate_threshold = _float(
        accuracy_ligand_thresholds.get("ranking_topk_hit_rate_min")
    )
    accuracy_ligand_metric_thresholds_present = (
        bool(accuracy_ligand_ranking)
        and "ranking_pr_auc" in accuracy_ligand_metrics
        and "ranking_pr_auc_ci_low" in accuracy_ligand_metrics
        and "ranking_topk_hit_rate" in accuracy_ligand_metrics
        and "ranking_pr_auc_min" in accuracy_ligand_thresholds
        and "ranking_pr_auc_ci_low_min" in accuracy_ligand_thresholds
        and "ranking_topk_hit_rate_min" in accuracy_ligand_thresholds
    )
    accuracy_ligand_metric_thresholds_pass = (
        accuracy_ligand_metric_thresholds_present
        and accuracy_ligand_pr_auc >= accuracy_ligand_pr_auc_threshold
        and accuracy_ligand_pr_auc_ci_low >= accuracy_ligand_pr_auc_ci_low_threshold
        and accuracy_ligand_topk_hit_rate >= accuracy_ligand_topk_hit_rate_threshold
    )
    accuracy_ligand_claim_scope_lock_only = (
        _text(accuracy_ligand_ranking.get("status")) == "restricted_pass"
        and accuracy_ligand_blockers == ["broad_gpcr_claim_not_allowed"]
        and accuracy_ligand_metric_thresholds_pass
        and accuracy_ligand_ranking.get("claim_promotion_allowed") is not True
        and accuracy_ligand_ranking.get("commercial_parity_claim_allowed") is not True
    )
    accuracy_parity_rows_accounted = (
        _int(accuracy_parity.get("pass_row_count"))
        + _int(accuracy_parity.get("restricted_pass_row_count"))
        + _int(accuracy_parity.get("blocked_row_count"))
        + _int(accuracy_parity.get("missing_row_count"))
    )
    accuracy_parity_scorecard_recorded = (
        _text(accuracy_parity.get("status")) in {"blocked_accuracy_parity", "green"}
        and _int(accuracy_parity.get("row_count")) >= 1
        and accuracy_parity_rows_accounted == _int(accuracy_parity.get("row_count"))
        and bool(accuracy_parity_claim_boundary.get("fake_pass_allowed") is False)
        and bool(accuracy_parity_claim_boundary.get("threshold_relaxation_allowed") is False)
        and bool(accuracy_parity_claim_boundary.get("scorecard_rows_must_map_to_frozen_artifacts") is True)
        and bool(accuracy_ligand_ranking)
    )
    accuracy_parity_full_commercial_blocked = (
        accuracy_parity_gate_present
        and not bool(accuracy_parity.get("overall_commercial_tool_accuracy_parity_allowed") is True)
    )
    master_gap_rollup = _summary(master_gap_closure_rollup_packet or {})
    master_gap_rows = _rows(master_gap_closure_rollup_packet or {})
    master_gap_rollup_gate_present = master_gap_closure_rollup_packet is not None
    master_gap_open_ids = [
        _text(item)
        for item in (master_gap_rollup.get("open_gap_ids") or [])
        if _text(item)
    ]
    master_gap_closed_ids = _text_list(master_gap_rollup.get("closed_gap_ids"))
    master_gap_science_claim_row = _row_by_id(master_gap_rows, "gap_id", "SCI-CLAIM")
    master_gap_release_blocker_rows = [
        row for row in master_gap_rows if bool(row.get("release_blocker") is True)
    ]
    expected_master_gap_product_ai_open_closed_ids = [
        "COMMERCIAL",
        "DATA-SCIENCE",
        "INFRA",
        "SCI-CLAIM",
        "DEPLOY-OPS",
        "STORAGE",
        "TOOLS",
        "API-RUNNER",
    ]
    expected_master_gap_complete_closed_ids = [
        "COMMERCIAL",
        "PRODUCT-AI",
        "DATA-SCIENCE",
        "INFRA",
        "SCI-CLAIM",
        "DEPLOY-OPS",
        "STORAGE",
        "TOOLS",
        "API-RUNNER",
    ]
    master_gap_science_claim_closed = (
        _text(master_gap_science_claim_row.get("status")) == "closed"
        and _text(master_gap_science_claim_row.get("rollup_status"))
        == "science_claim_promotion_gap_closure_complete"
        and _text(master_gap_science_claim_row.get("evidence"))
        == "runs/science_claim_promotion_gap_closure_current.json"
        and bool(master_gap_science_claim_row.get("release_blocker") is False)
        and bool(master_gap_science_claim_row.get("execution_enabled") is False)
        and bool(master_gap_science_claim_row.get("external_state_mutated") is False)
    )
    master_gap_complete_recorded = (
        _text(master_gap_rollup.get("status")) == "master_gap_closure_rollup_complete"
        and bool(master_gap_rollup.get("all_gaps_closed") is True)
        and bool(master_gap_rollup.get("claim_promotion_allowed") is False)
        and _int(master_gap_rollup.get("gap_count")) == 9
        and _int(master_gap_rollup.get("closed_gap_count")) == 9
        and _int(master_gap_rollup.get("open_gap_count")) == 0
        and master_gap_open_ids == []
        and master_gap_closed_ids == expected_master_gap_complete_closed_ids
        and _text(master_gap_rollup.get("current_primary_open_gap_id")) == "none"
        and len(master_gap_rows) == 9
        and len(master_gap_release_blocker_rows) == 0
        and master_gap_science_claim_closed
        and bool(master_gap_rollup.get("execution_enabled") is False)
        and bool(master_gap_rollup.get("external_state_mutated") is False)
    )
    master_gap_product_ai_open_recorded = (
        _text(master_gap_rollup.get("status")) == "blocked_master_gap_closure_rollup"
        and bool(master_gap_rollup.get("all_gaps_closed") is False)
        and bool(master_gap_rollup.get("claim_promotion_allowed") is False)
        and _int(master_gap_rollup.get("gap_count")) == 9
        and _int(master_gap_rollup.get("closed_gap_count")) == 8
        and _int(master_gap_rollup.get("open_gap_count")) == 1
        and master_gap_open_ids == ["PRODUCT-AI"]
        and master_gap_closed_ids == expected_master_gap_product_ai_open_closed_ids
        and _text(master_gap_rollup.get("current_primary_open_gap_id")) == "PRODUCT-AI"
        and len(master_gap_rows) == 9
        and len(master_gap_release_blocker_rows) == 0
        and master_gap_science_claim_closed
        and bool(master_gap_rollup.get("execution_enabled") is False)
        and bool(master_gap_rollup.get("external_state_mutated") is False)
    )
    master_gap_rollup_recorded = master_gap_complete_recorded or master_gap_product_ai_open_recorded
    product_ai_architecture_gate_present = (
        product_ai_architecture_gap_packet is not None or product_ai_execution_backlog_packet is not None
    )
    product_ai_architecture = _summary(product_ai_architecture_gap_packet or {})
    product_ai_backlog = _summary(product_ai_execution_backlog_packet or {})
    product_ai_backlog_detail = _primary_backlog_detail(product_ai_execution_backlog_packet or {})
    product_ai_scope_detail = _text(product_ai_backlog.get("scope_closure_detail"))
    product_ai_architecture_artifacts_present = (
        product_ai_architecture_gap_packet is not None and product_ai_execution_backlog_packet is not None
    )

    product_ready = bool(product.get("pilot_delivery_ready") is True)
    product_claim_allowed = bool(product.get("delivery_ready_claim_allowed") is True)
    product_bundle_validated = bool(product.get("bundle_validation_passed") is True)
    product_architecture_ready = bool(product_architecture.get("architecture_release_ready") is True)
    product_local_architecture_surface_ready = bool(product_architecture.get("local_architecture_surface_ready") is True)
    product_architecture_public_benchmark_ready = bool(product_architecture.get("public_benchmark_validation_ready") is True)
    product_architecture_public_benchmark_status = _text(product_architecture.get("public_benchmark_status"))
    product_architecture_public_benchmark_blocked_suite_count = _int(
        product_architecture.get("public_benchmark_blocked_suite_count")
    )
    product_architecture_public_benchmark_ready_required_suite_count = _int(
        product_architecture.get("public_benchmark_ready_required_suite_count")
    )
    product_architecture_public_benchmark_required_suite_count = _int(
        product_architecture.get("public_benchmark_required_suite_count")
    )
    product_architecture_public_benchmark_suite_materialization_manifest_count = _int(
        product_architecture.get("public_benchmark_suite_materialization_manifest_count")
    )
    product_architecture_public_benchmark_suite_scorecard_row_csv_count = _int(
        product_architecture.get("public_benchmark_suite_scorecard_row_csv_count")
    )
    product_architecture_public_benchmark_suite_threshold_count = _int(
        product_architecture.get("public_benchmark_suite_threshold_count")
    )
    product_architecture_public_benchmark_suite_blocker_count = _int(
        product_architecture.get("public_benchmark_suite_blocker_count")
    )
    product_architecture_public_benchmark_suite_run_command_count = _int(
        product_architecture.get("public_benchmark_suite_run_command_count")
    )
    product_architecture_public_benchmark_suite_materialization_run_command_count = _int(
        product_architecture.get("public_benchmark_suite_materialization_run_command_count")
    )
    product_architecture_public_benchmark_suite_no_external_dependency_count = _int(
        product_architecture.get("public_benchmark_suite_no_external_dependency_count")
    )
    product_architecture_cameo_official_evidence_ready = bool(
        product_architecture.get("cameo_official_validation_evidence_ready") is True
    )
    product_architecture_cameo_receiver_smoke_status = _text(product_architecture.get("cameo_receiver_smoke_status"))
    product_architecture_cameo_api_dependency_status = _text(product_architecture.get("cameo_api_dependency_status"))
    product_architecture_cameo_public_registration_blocker_count = _int(
        product_architecture.get("cameo_public_registration_blocker_count")
    )
    product_architecture_cameo_registration_tokens = list(
        product_architecture.get("cameo_registration_approval_tokens_required") or []
    )
    public_benchmark_required_for_product_release = True
    cameo_live_validation_channel = True
    cameo_live_validation_required_for_product_release = False
    cameo_registration_required_for_product_release = False
    cameo_official_results_required_for_product_release = False
    release_blocked_by_public_benchmark = not product_architecture_public_benchmark_ready
    release_blocked_by_cameo_live_validation = False
    product_commercial_independence_ready = (
        _text(product_independence.get("status")) == "product_commercial_independence_gate_ready"
        and bool(product_independence.get("commercial_independent_product_claim_allowed") is True)
    )

    cameo_evidence_ready = _text(cameo_validation.get("status")) == "cameo_validation_evidence_ready"
    cameo_official_used = bool(cameo_validation.get("official_cameo_results_used") is True)
    cameo_public_registration_allowed = bool(cameo_capability.get("public_registration_allowed") is True)
    cameo_capability_ready = _text(cameo_capability.get("status")) in {
        "cameo_development_capability_preflight_ready",
        "cameo_public_registration_preflight_ready",
    }
    cameo_registration_gate_ready = (
        _text(cameo_registration_gate.get("status")) == "cameo_public_registration_approval_gate_ready"
        and bool(cameo_registration_gate.get("authorized_for_registration_review") is True)
    )

    no_operator_actions = _text(actions.get("status")) == "goal_operator_actions_clear" and _int(actions.get("action_count")) == 0
    rollup_status = _text(rollup.get("status"))
    no_goal_blockers = rollup_status in {
        "goal_readiness_ready",
        "goal_readiness_evidence_ready",
        "goal_readiness_pending_operator_or_external_results",
        "goal_readiness_release_complete_operator_pending",
    } and _int(rollup.get("blocked_lane_count")) == 0
    goal_api_surface_ready = (
        _text(goal_api_surface.get("status")) == "goal_api_surface_contract_ready"
        and bool(goal_api_surface.get("surface_ready") is True)
        and _int(goal_api_surface.get("blocker_count")) == 0
    )
    product_ai_release_blocking_work_item_count = _int(
        product_ai_backlog.get(
            "release_blocking_work_item_count",
            product_ai_backlog.get(
                "work_item_count",
                1 if product_ai_architecture_gate_present else 0,
            ),
        )
    )
    product_ai_optional_work_item_count = max(
        0,
        _int(product_ai_backlog.get("work_item_count")) - product_ai_release_blocking_work_item_count,
    )
    product_ai_architecture_ready = (
        product_ai_architecture_artifacts_present
        and product_ai_release_blocking_work_item_count == 0
    )
    cleanup_postcheck_ready = (
        _text(cleanup_postcheck.get("status")) == "cleanup_postcheck_contract_ready"
        and bool(cleanup_postcheck.get("postcheck_contract_ready") is True)
        and _int(cleanup_postcheck.get("row_count")) > 0
        and _int(cleanup_postcheck.get("blocked_row_count")) == 0
    )
    cleanup_completion_ready = (
        _text(cleanup_completion.get("status")) == "cleanup_completion_gate_ready"
        and bool(cleanup_completion.get("cleanup_complete") is True)
    )
    cleanup_completion_blocked_stage_count = _int(cleanup_completion.get("blocked_stage_count"))
    cleanup_completion_total_reclaim_size_gb = round(_float(cleanup_completion.get("total_reclaim_size_gb")), 3)
    cleanup_completion_authorized_reclaim_size_gb = round(_float(cleanup_completion.get("authorized_reclaim_size_gb")), 3)
    cleanup_completion_awaiting_approval_count = _int(
        cleanup_completion.get("approval_awaiting_operator_approval_row_count")
    )
    cleanup_completion_blocked_approval_count = _int(cleanup_completion.get("approval_blocked_row_count"))
    cleanup_completion_ligand_candidate_size_gb = round(_float(cleanup_completion.get("ligand_heavy_candidate_size_gb")), 3)
    cleanup_completion_transition_reclaim_size_gb = round(
        _float(cleanup_completion.get("transition_approval_gated_reclaim_size_gb")), 3
    )
    transition_cleanup_done = (
        _text(transition_cleanup.get("status")) == "transition_cleanup_execution_complete"
        and bool(transition_cleanup.get("external_state_mutated") is True)
    ) or (
        cleanup_completion_ready
        and bool(
            cleanup_completion.get("transition_cleanup_complete") is True
            or cleanup_completion.get("cleanup_complete") is True
        )
    )
    ligand_cleanup_done = (
        _text(ligand_cleanup.get("status")) == "ligand_heavy_cleanup_execution_complete"
        and bool(ligand_cleanup.get("delete_executed") is True)
    ) or (
        cleanup_completion_ready
        and bool(
            cleanup_completion.get("ligand_heavy_cleanup_complete") is True
            or cleanup_completion.get("cleanup_complete") is True
        )
    )
    protected_policy_resolved_by_review = _int(protected_cleanup.get("policy_change_required_count")) == 0
    protected_policy_resolved_by_gate = (
        _text(protected_policy_gate.get("status")) == "protected_cleanup_policy_decision_gate_ready"
        and bool(protected_policy_gate.get("policy_resolved") is True)
        and _int(protected_policy_gate.get("policy_change_requested_row_count")) == 0
        and _int(protected_policy_gate.get("awaiting_policy_decision_row_count")) == 0
        and _int(protected_policy_gate.get("blocked_row_count")) == 0
    )
    protected_policy_resolved = protected_policy_resolved_by_review or protected_policy_resolved_by_gate or (
        cleanup_completion_ready and bool(cleanup_completion.get("protected_policy_resolved") is True)
    )

    rows = [
        _row(
            lane_id="commercial_product_release",
            check="product_architecture_release_ready",
            artifact_path=product_architecture_path,
            observed=(
                f"{_text(product_architecture.get('status')) or 'missing'};"
                f"local_surface={_bool_text(product_local_architecture_surface_ready)};"
                f"architecture_release_ready={_bool_text(product_architecture_ready)};"
                f"public_benchmark_ready={_bool_text(product_architecture_public_benchmark_ready)};"
                f"public_benchmark_status={product_architecture_public_benchmark_status or 'missing'};"
                f"public_benchmark_ready_required_suites={product_architecture_public_benchmark_ready_required_suite_count};"
                f"public_benchmark_required_suites={product_architecture_public_benchmark_required_suite_count};"
                f"public_benchmark_blocked_suites={product_architecture_public_benchmark_blocked_suite_count};"
                f"public_benchmark_suite_materialization_manifest_count={product_architecture_public_benchmark_suite_materialization_manifest_count};"
                f"public_benchmark_suite_scorecard_row_csv_count={product_architecture_public_benchmark_suite_scorecard_row_csv_count};"
                f"public_benchmark_suite_threshold_count={product_architecture_public_benchmark_suite_threshold_count};"
                f"public_benchmark_suite_blocker_count={product_architecture_public_benchmark_suite_blocker_count};"
                f"public_benchmark_suite_run_command_count={product_architecture_public_benchmark_suite_run_command_count};"
                f"public_benchmark_suite_materialization_run_command_count={product_architecture_public_benchmark_suite_materialization_run_command_count};"
                f"public_benchmark_suite_no_external_dependency_count={product_architecture_public_benchmark_suite_no_external_dependency_count};"
                f"cameo_official_evidence_ready={_bool_text(product_architecture_cameo_official_evidence_ready)};"
                f"cameo_receiver_smoke_status={product_architecture_cameo_receiver_smoke_status or 'missing'};"
                f"cameo_api_dependency_status={product_architecture_cameo_api_dependency_status or 'missing'};"
                f"cameo_public_registration_blocker_count={product_architecture_cameo_public_registration_blocker_count};"
                f"cameo_registration_tokens={';'.join(product_architecture_cameo_registration_tokens)}"
            ),
            required="product_architecture_contract_current.json with architecture_release_ready=true",
            passed=product_architecture_ready,
            reason="Full release requires the molecular-structure, ligand-docking, public benchmark, optional CAMEO surface, CASP17, and cleanup architecture contract to be release-ready.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="pilot_delivery_ready",
            artifact_path=product_pilot_path,
            observed=_bool_text(product_ready),
            required="true",
            passed=product_ready,
            reason="Pilot packet must be delivery-ready after approved execution, bundle assembly, and final validation.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="bundle_validation_passed",
            artifact_path=product_pilot_path,
            observed=_bool_text(product_bundle_validated),
            required="true",
            passed=product_bundle_validated,
            reason="Commercial independent-product release requires the final product bundle validator to pass.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="delivery_ready_claim_allowed",
            artifact_path=product_pilot_path,
            observed=_bool_text(product_claim_allowed),
            required="true",
            passed=product_claim_allowed,
            reason="Customer-facing delivery-ready wording must stay blocked until the product bundle is validated.",
        ),
        _row(
            lane_id="commercial_product_release",
            check="commercial_independence_gate_ready",
            artifact_path=product_commercial_independence_path,
            observed=(
                f"{_text(product_independence.get('status')) or 'missing'};"
                f"claim_allowed={_bool_text(product_commercial_independence_ready)}"
            ),
            required="product_commercial_independence_gate_ready",
            passed=product_commercial_independence_ready,
            reason="Commercial independent-product release requires license, reproducible core runtime dependencies, optional-profile separation, deployment evidence, and product API/package surfaces.",
        ),
        _row(
            lane_id="performance_validation",
            check="public_benchmark_validation_ready",
            artifact_path=product_architecture_path,
            observed=(
                f"public_benchmark_status={product_architecture_public_benchmark_status or 'missing'};"
                f"ready_required_suites={product_architecture_public_benchmark_ready_required_suite_count};"
                f"required_suites={product_architecture_public_benchmark_required_suite_count};"
                f"blocked_suites={product_architecture_public_benchmark_blocked_suite_count};"
                f"suite_materialization_manifest_count={product_architecture_public_benchmark_suite_materialization_manifest_count};"
                f"suite_scorecard_row_csv_count={product_architecture_public_benchmark_suite_scorecard_row_csv_count};"
                f"suite_threshold_count={product_architecture_public_benchmark_suite_threshold_count};"
                f"suite_blocker_count={product_architecture_public_benchmark_suite_blocker_count};"
                f"suite_run_command_count={product_architecture_public_benchmark_suite_run_command_count};"
                f"suite_materialization_run_command_count={product_architecture_public_benchmark_suite_materialization_run_command_count};"
                f"suite_no_external_dependency_count={product_architecture_public_benchmark_suite_no_external_dependency_count};"
                f"requires_24h_server={_bool_text(product_architecture.get('public_benchmark_requires_24h_server'))};"
                f"requires_competition_season={_bool_text(product_architecture.get('public_benchmark_requires_competition_season'))};"
                f"requires_paid_vps={_bool_text(product_architecture.get('public_benchmark_requires_paid_vps'))}"
            ),
            required="product_public_benchmark_contract_ready with all required suites passing",
            passed=product_architecture_public_benchmark_ready,
            reason="Architecture performance validation is now based on reproducible public benchmark scorecards rather than CAMEO server registration.",
        ),
        _row(
            lane_id="cleanup_release",
            check="cleanup_operator_actions_resolved",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else operator_action_board_path,
            observed=(
                f"operator_board={_text(actions.get('status')) or 'missing'};"
                f"action_count={_int(actions.get('action_count'))};"
                f"cleanup_completion={_text(cleanup_completion.get('status')) or 'missing'};"
                f"cleanup_complete={_bool_text(cleanup_completion_ready)}"
            ),
            required="cleanup_completion_gate_ready;cleanup_complete=true OR cleanup execution rows complete and action board clear",
            passed=cleanup_completion_ready or (no_operator_actions and transition_cleanup_done and ligand_cleanup_done and protected_policy_resolved),
            reason="Cleanup release cannot be claimed until cleanup-specific approvals, execution, postchecks, and policy resolution are complete.",
        ),
        _row(
            lane_id="cleanup_release",
            check="cleanup_postcheck_contract_ready",
            artifact_path=cleanup_postcheck_contract_path,
            observed=(
                f"{_text(cleanup_postcheck.get('status')) or 'missing'};"
                f"ready={_bool_text(cleanup_postcheck_ready)};"
                f"rows={_int(cleanup_postcheck.get('row_count'))};"
                f"blocked_rows={_int(cleanup_postcheck.get('blocked_row_count'))};"
                f"global_refresh_commands={_int(cleanup_postcheck.get('global_refresh_command_count'))}"
            ),
            required="cleanup_postcheck_contract_ready;postcheck_contract_ready=true;blocked_row_count=0",
            passed=cleanup_postcheck_ready,
            reason="Cleanup release needs row-specific postcheck evidence and refresh commands before cleanup completion can be claimed.",
        ),
        _row(
            lane_id="cleanup_release",
            check="transition_cleanup_complete",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else transition_cleanup_preflight_path,
            observed=(
                f"{_text(transition_cleanup.get('status')) or 'missing'};"
                f"completion_gate={_text(cleanup_completion.get('status')) or 'missing'};"
                f"transition_approval_gated_reclaim_size_gb={cleanup_completion_transition_reclaim_size_gb};"
                f"approval_awaiting={cleanup_completion_awaiting_approval_count};"
                f"approval_blocked={cleanup_completion_blocked_approval_count}"
            ),
            required="transition_cleanup_execution_complete OR cleanup_completion_gate_ready",
            passed=transition_cleanup_done,
            reason="CASP17-heavy transition cleanup must be explicitly executed or resolved before release.",
        ),
        _row(
            lane_id="cleanup_release",
            check="ligand_heavy_cleanup_complete",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else ligand_cleanup_preflight_path,
            observed=(
                f"{_text(ligand_cleanup.get('status')) or 'missing'};"
                f"completion_gate={_text(cleanup_completion.get('status')) or 'missing'};"
                f"ligand_heavy_candidate_size_gb={cleanup_completion_ligand_candidate_size_gb};"
                f"total_reclaim_size_gb={cleanup_completion_total_reclaim_size_gb}"
            ),
            required="ligand_heavy_cleanup_execution_complete OR cleanup_completion_gate_ready",
            passed=ligand_cleanup_done,
            reason="Stale ligand-heavy trajectory payload cleanup must be explicitly executed or resolved before release.",
        ),
        _row(
            lane_id="cleanup_release",
            check="protected_cleanup_policy_resolved",
            artifact_path=cleanup_completion_gate_path if cleanup_completion_gate_packet else (protected_cleanup_policy_decision_gate_path if protected_cleanup_policy_decision_gate_packet else protected_cleanup_review_path),
            observed=(
                f"policy_change_required_count={_int(protected_cleanup.get('policy_change_required_count'))};"
                f"policy_gate_status={_text(protected_policy_gate.get('status')) or 'missing'};"
                f"policy_resolved={bool(protected_policy_gate.get('policy_resolved') is True)};"
                f"known_payload_child_count={_int(protected_policy_gate.get('known_payload_child_count'))};"
                f"known_payload_child_size_gb={round(_float(protected_policy_gate.get('known_payload_child_size_gb')), 3)};"
                f"completion_gate={_text(cleanup_completion.get('status')) or 'missing'}"
            ),
            required="policy_change_required_count=0 OR protected_cleanup_policy_decision_gate_ready OR cleanup_completion_gate_ready",
            passed=protected_policy_resolved,
            reason="Protected heavy payload rows must be kept by explicit policy or promoted by an explicit cleanup-policy change.",
        ),
        _row(
            lane_id="goal_release",
            check="product_release_evidence_ready",
            artifact_path=goal_rollup_path,
            observed=(
                f"{rollup_status or 'missing'};"
                f"blocked_lane_count={_int(rollup.get('blocked_lane_count'))};"
                f"operator_approval_pending_count={_int(rollup.get('operator_approval_pending_count'))};"
                f"external_results_pending_count={_int(rollup.get('external_results_pending_count'))}"
            ),
            required="no blocked rollup lanes; optional/operator/external lanes may remain pending after product release evidence is ready",
            passed=no_goal_blockers,
            reason="Product release evidence may pass while optional CAMEO, cleanup, or execution-operation lanes remain tracked separately for approval or external results.",
        ),
        _row(
            lane_id="goal_release",
            check="goal_api_surface_contract_ready",
            artifact_path=goal_api_surface_contract_path,
            observed=(
                f"{_text(goal_api_surface.get('status')) or 'missing'};"
                f"surface_ready={_bool_text(goal_api_surface_ready)};"
                f"check_count={_int(goal_api_surface.get('check_count'))};"
                f"blocker_count={_int(goal_api_surface.get('blocker_count'))};"
                f"missing_endpoint_count={_int(goal_api_surface.get('missing_endpoint_count'))};"
                f"missing_status_key_count={_int(goal_api_surface.get('missing_status_key_count'))}"
            ),
            required="goal_api_surface_contract_ready;surface_ready=true;blocker_count=0",
            passed=goal_api_surface_ready,
            reason="The top-level local API must expose a verified read-only goal status surface before release can be claimed.",
        ),
    ]
    if cameo_fetch_preflight_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="cameo_official_result_fetch_preflight_recorded",
                artifact_path=cameo_official_result_fetch_preflight_path,
                observed=(
                    f"{_text(cameo_fetch_preflight.get('status')) or 'missing'};"
                    f"authorized_for_separate_operator_fetch="
                    f"{_bool_text(bool(cameo_fetch_preflight.get('authorized_for_separate_operator_fetch') is True))};"
                    f"operator_fetch_csv_present="
                    f"{_bool_text(bool(cameo_fetch_preflight.get('operator_fetch_csv_present') is True))};"
                    f"blocked_row_count={_int(cameo_fetch_preflight.get('blocked_row_count'))};"
                    f"blocker_count={_int(cameo_fetch_preflight.get('blocker_count'))};"
                    f"awaiting_operator_fetch_approval_row_count="
                    f"{_int(cameo_fetch_preflight.get('awaiting_operator_fetch_approval_row_count'))};"
                    f"fetch_approval_token_required="
                    f"{_text(cameo_fetch_preflight.get('fetch_approval_token_required'))};"
                    f"network_request_opened="
                    f"{_bool_text(bool(cameo_fetch_preflight.get('network_request_opened') is True))};"
                    f"official_results_fetched="
                    f"{_bool_text(bool(cameo_fetch_preflight.get('official_results_fetched') is True))};"
                    f"native_local_accuracy_used="
                    f"{_bool_text(bool(cameo_fetch_preflight.get('native_local_accuracy_used') is True))};"
                    f"outbound_email_enabled="
                    f"{_bool_text(bool(cameo_fetch_preflight.get('outbound_email_enabled') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(cameo_fetch_preflight.get('external_state_mutated') is True))}"
                ),
                required=(
                    "CAMEO official-result fetch preflight recorded with approval token, operator CSV boundary, "
                    "no network fetch, no local native substitution, and no external mutation"
                ),
                passed=cameo_fetch_preflight_recorded,
                reason=(
                    "Official CAMEO result retrieval must remain a separate operator-approved step; the release "
                    "decision should not hide whether the fetch preflight is blocked or ready."
                ),
            )
        )
    if api_runner_profile_receipt_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="api_runner_profile_promotion_operator_receipt_recorded",
                artifact_path=api_runner_profile_promotion_operator_receipt_path,
                observed=(
                    f"{_text(api_runner_profile_receipt.get('status')) or 'missing'};"
                    f"readiness_status={_text(api_runner_profile_receipt.get('readiness_status'))};"
                    f"operator_receipt_ready="
                    f"{_bool_text(bool(api_runner_profile_receipt.get('operator_receipt_ready') is True))};"
                    f"profile_count={_int(api_runner_profile_receipt.get('profile_count'))};"
                    f"receipt_row_count={_int(api_runner_profile_receipt.get('receipt_row_count'))};"
                    f"blocked_row_count={_int(api_runner_profile_receipt.get('blocked_row_count'))};"
                    f"first_blocked_profile_id={_text(api_runner_profile_receipt.get('first_blocked_profile_id'))};"
                    f"first_blocked_row_blocker={_text(api_runner_profile_receipt.get('first_blocked_row_blocker'))};"
                    f"approval_token_required={_text(api_runner_profile_receipt.get('approval_token_required'))};"
                    f"profile_enabled_by_this_tool="
                    f"{_bool_text(bool(api_runner_profile_receipt.get('profile_enabled_by_this_tool') is True))};"
                    f"runner_executed={_bool_text(bool(api_runner_profile_receipt.get('runner_executed') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(api_runner_profile_receipt.get('external_state_mutated') is True))}"
                ),
                required=(
                    "API runner profile promotion operator receipt recorded with approval token, "
                    "blocked-row detail, and no profile execution/mutation by this gate"
                ),
                passed=api_runner_profile_receipt_recorded,
                reason=(
                    "The final release decision must preserve that validated runner profiles are "
                    "promotion-ready but still require an explicit operator receipt before profile "
                    "promotion or runner execution can occur."
                ),
            )
        )
    if product_scope_receipt_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_scope_breadth_evidence_receipt_recorded",
                artifact_path=product_scope_breadth_evidence_receipt_path,
                observed=(
                    f"{_text(product_scope_receipt.get('status')) or 'missing'};"
                    f"receipt_ready="
                    f"{_bool_text(bool(product_scope_receipt.get('full_scope_evidence_receipt_ready') is True))};"
                    f"receipt_row_count={_int(product_scope_receipt.get('receipt_row_count'))};"
                    f"blocked_row_count={_int(product_scope_receipt.get('blocked_row_count'))};"
                    f"blocker_count={_int(product_scope_receipt.get('blocker_count'))};"
                    f"required_scope_blocker_count={_int(product_scope_receipt.get('required_scope_blocker_count'))};"
                    f"first_blocked_scope_blocker_id={_text(product_scope_receipt.get('first_blocked_scope_blocker_id'))};"
                    f"first_blocked_evidence_artifact={_text(product_scope_receipt.get('first_blocked_evidence_artifact'))};"
                    f"first_blocked_observed_evidence_status="
                    f"{_text(product_scope_receipt.get('first_blocked_observed_evidence_status'))};"
                    f"most_common_row_blocker={_text(product_scope_receipt.get('most_common_row_blocker'))};"
                    f"approval_token_required={_text(product_scope_receipt.get('approval_token_required'))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(product_scope_receipt.get('external_state_mutated') is True))}"
                ),
                required=(
                    "R8 product scope breadth evidence receipt recorded with blocked-row detail, "
                    "approval token, and no external mutation"
                ),
                passed=product_scope_receipt_recorded,
                reason=(
                    "The final release decision must preserve the R8 full-scope evidence receipt "
                    "placeholder/operator-input blocker, not only the collapsed R8 matrix row."
                ),
            )
        )
    if engine_refinement_receipt_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="engine_refinement_claim_evidence_receipt_recorded",
                artifact_path=engine_refinement_claim_evidence_receipt_path,
                observed=(
                    f"{_text(engine_refinement_receipt.get('status')) or 'missing'};"
                    f"receipt_ready="
                    f"{_bool_text(bool(engine_refinement_receipt.get('claim_promotion_evidence_receipt_ready') is True))};"
                    f"receipt_row_count={_int(engine_refinement_receipt.get('receipt_row_count'))};"
                    f"blocked_row_count={_int(engine_refinement_receipt.get('blocked_row_count'))};"
                    f"blocker_count={_int(engine_refinement_receipt.get('blocker_count'))};"
                    f"required_blocker_count={_int(engine_refinement_receipt.get('required_blocker_count'))};"
                    f"first_blocked_blocker_id={_text(engine_refinement_receipt.get('first_blocked_blocker_id'))};"
                    f"first_blocked_evidence_artifact={_text(engine_refinement_receipt.get('first_blocked_evidence_artifact'))};"
                    f"first_blocked_observed_evidence_status="
                    f"{_text(engine_refinement_receipt.get('first_blocked_observed_evidence_status'))};"
                    f"most_common_row_blocker={_text(engine_refinement_receipt.get('most_common_row_blocker'))};"
                    f"approval_token_required={_text(engine_refinement_receipt.get('approval_token_required'))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(engine_refinement_receipt.get('external_state_mutated') is True))}"
                ),
                required=(
                    "R9 engine refinement claim evidence receipt recorded with blocked-row detail, "
                    "approval token, and no external mutation"
                ),
                passed=engine_refinement_receipt_recorded,
                reason=(
                    "The final release decision must preserve the R9 OpenMM/Schrodinger-grade claim "
                    "evidence receipt blocker, not only the collapsed R9 matrix row."
                ),
            )
        )
    if engine_refinement_priority_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="engine_refinement_claim_evidence_priority_packet_recorded",
                artifact_path=engine_refinement_claim_evidence_priority_packet_path,
                observed=(
                    f"{_text(engine_refinement_priority.get('status')) or 'missing'};"
                    f"priority_packet_ready="
                    f"{_bool_text(bool(engine_refinement_priority.get('priority_packet_ready') is True))};"
                    f"claim_evidence_receipt_status="
                    f"{_text(engine_refinement_priority.get('claim_evidence_receipt_status'))};"
                    f"claim_evidence_receipt_ready="
                    f"{_bool_text(bool(engine_refinement_priority.get('claim_evidence_receipt_ready') is True))};"
                    f"claim_promotion_allowed="
                    f"{_bool_text(bool(engine_refinement_priority.get('claim_promotion_allowed') is True))};"
                    f"priority_item_count={_int(engine_refinement_priority.get('priority_item_count'))};"
                    f"operator_input_required_count="
                    f"{_int(engine_refinement_priority.get('operator_input_required_count'))};"
                    f"blocked_priority_item_count="
                    f"{_int(engine_refinement_priority.get('blocked_priority_item_count'))};"
                    f"required_blocker_count={_int(engine_refinement_priority.get('required_blocker_count'))};"
                    f"top_blocker_id={_text(engine_refinement_priority.get('top_blocker_id'))};"
                    f"top_priority_bucket={_text(engine_refinement_priority.get('top_priority_bucket'))};"
                    f"top_required_input={_text(engine_refinement_priority.get('top_required_input'))};"
                    f"top_acceptance_artifact={_text(engine_refinement_priority.get('top_acceptance_artifact'))};"
                    f"public_benchmark_status="
                    f"{_text(engine_refinement_priority.get('public_benchmark_status'))};"
                    f"public_benchmark_work_order_row_count="
                    f"{_int(engine_refinement_priority.get('public_benchmark_work_order_row_count'))};"
                    f"public_benchmark_work_order_apply_status="
                    f"{_text(engine_refinement_priority.get('public_benchmark_work_order_apply_status'))};"
                    f"public_benchmark_work_order_apply_blocked_row_count="
                    f"{_int(engine_refinement_priority.get('public_benchmark_work_order_apply_blocked_row_count'))};"
                    f"approval_token_required="
                    f"{_text(engine_refinement_priority.get('approval_token_required'))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(engine_refinement_priority.get('external_state_mutated') is True))}"
                ),
                required=(
                    "R9 engine refinement claim evidence priority packet recorded with the top "
                    "public-benchmark work-order blocker and approval token"
                ),
                passed=engine_refinement_priority_recorded,
                reason=(
                    "The final release decision must preserve the first R9 manual operator step: "
                    "fill and validate the public benchmark work-order rows before any claim promotion."
                ),
            )
        )
    if refine_tier_public_benchmark_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="refine_tier_public_benchmark_fail_closed_recorded",
                artifact_path=refine_tier_public_benchmark_readiness_path,
                observed=(
                    f"{_text(refine_tier_public_benchmark.get('status')) or 'missing'};"
                    f"input_csv_present="
                    f"{_bool_text(bool(refine_tier_public_benchmark.get('input_csv_present') is True))};"
                    f"claim_grade_public_benchmark_ready="
                    f"{_bool_text(bool(refine_tier_public_benchmark.get('claim_grade_public_benchmark_ready') is True))};"
                    f"benchmark_metric_surface_ready="
                    f"{_bool_text(bool(refine_tier_public_benchmark.get('benchmark_metric_surface_ready') is True))};"
                    f"row_count={_int(refine_tier_public_benchmark.get('row_count'))};"
                    f"valid_row_count={_int(refine_tier_public_benchmark.get('valid_row_count'))};"
                    f"pose_metric_pass_count="
                    f"{_int(refine_tier_public_benchmark.get('pose_metric_pass_count'))};"
                    f"free_energy_pair_count="
                    f"{_int(refine_tier_public_benchmark.get('free_energy_pair_count'))};"
                    f"blocker_count={_int(refine_tier_public_benchmark.get('blocker_count'))};"
                    f"operator_work_order_ready="
                    f"{_bool_text(bool(refine_tier_public_benchmark.get('operator_work_order_ready') is True))};"
                    f"work_order_row_count="
                    f"{_int(refine_tier_public_benchmark.get('work_order_row_count'))};"
                    f"write_intake_approval_token_required="
                    f"{_text(refine_tier_public_benchmark.get('write_intake_approval_token_required'))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(refine_tier_public_benchmark.get('external_state_mutated') is True))}"
                ),
                required=(
                    "blocked_refine_tier_public_benchmark_readiness with empty tracked intake, "
                    "8-row operator work order ready, claim-grade benchmark blocked, approval token "
                    "required for intake writes, and no external mutation"
                ),
                passed=refine_tier_public_benchmark_recorded,
                reason=(
                    "The final release decision must preserve the original public pose/free-energy "
                    "benchmark gate, not only the priority packet that summarizes the next R9 operator step."
                ),
            )
        )
    if refine_tier_public_benchmark_work_order_apply_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="refine_tier_public_benchmark_work_order_apply_fail_closed_recorded",
                artifact_path=refine_tier_public_benchmark_work_order_apply_path,
                observed=(
                    f"{_text(refine_tier_public_benchmark_work_order_apply.get('status')) or 'missing'};"
                    f"aggregate_readiness_required="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('aggregate_readiness_required') is True))};"
                    f"apply_ready="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('apply_ready') is True))};"
                    f"work_order_csv_present="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('work_order_csv_present') is True))};"
                    f"work_order_row_count="
                    f"{_int(refine_tier_public_benchmark_work_order_apply.get('work_order_row_count'))};"
                    f"blocked_row_count="
                    f"{_int(refine_tier_public_benchmark_work_order_apply.get('blocked_row_count'))};"
                    f"valid_intake_row_count="
                    f"{_int(refine_tier_public_benchmark_work_order_apply.get('valid_intake_row_count'))};"
                    f"receptor_coordinate_validation_required="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('receptor_coordinate_validation_required') is True))};"
                    f"receptor_coordinate_validation_pass_row_count="
                    f"{_int(refine_tier_public_benchmark_work_order_apply.get('receptor_coordinate_validation_pass_row_count'))};"
                    f"receptor_coordinate_validation_blocked_row_count="
                    f"{_int(refine_tier_public_benchmark_work_order_apply.get('receptor_coordinate_validation_blocked_row_count'))};"
                    f"metric_evidence_required="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('metric_evidence_required') is True))};"
                    f"metric_evidence_pass_row_count="
                    f"{_int(refine_tier_public_benchmark_work_order_apply.get('metric_evidence_pass_row_count'))};"
                    f"metric_evidence_blocked_row_count="
                    f"{_int(refine_tier_public_benchmark_work_order_apply.get('metric_evidence_blocked_row_count'))};"
                    f"candidate_intake_written="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('candidate_intake_written') is True))};"
                    f"intake_written="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('intake_written') is True))};"
                    f"write_intake_requested="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('write_intake_requested') is True))};"
                    f"approval_token_present="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('approval_token_present') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(refine_tier_public_benchmark_work_order_apply.get('external_state_mutated') is True))}"
                ),
                required=(
                    "blocked_refine_tier_public_benchmark_work_order_apply with 8 blocked placeholder "
                    "rows, 8/0 receptor-coordinate validation pass/blocked rows, 0/8 metric-evidence pass rows, "
                    "no candidate/tracked intake write, no approval token use, and no external mutation"
                ),
                passed=refine_tier_public_benchmark_work_order_apply_recorded,
                reason=(
                    "The final release decision must preserve the guarded apply step so public benchmark "
                    "intake cannot be silently written without operator approval."
                ),
            )
        )
    if goal_bottleneck_briefing_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="goal_bottleneck_briefing_full_commercial_receipts_recorded",
                artifact_path=goal_bottleneck_briefing_path,
                observed=(
                    f"{_text(goal_bottleneck_briefing.get('status')) or 'missing'};"
                    f"completion_audit_release_blocker_bottleneck_count={_int(goal_bottleneck_briefing.get('completion_audit_release_blocker_bottleneck_count'))};"
                    f"full_commercial_evidence_receipt_entry_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_entry_count'))};"
                    f"full_commercial_evidence_receipt_operator_input_required_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_operator_input_required_count'))};"
                    f"full_commercial_evidence_receipt_current_action_required_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_current_action_required_count'))};"
                    f"full_commercial_evidence_receipt_template_required_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_template_required_count'))};"
                    f"full_commercial_evidence_receipt_template_present_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_template_present_count'))};"
                    f"full_commercial_evidence_receipt_approval_token_count={_int(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_approval_token_count'))};"
                    f"full_commercial_evidence_receipt_source_gate_statuses={_text(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_source_gate_statuses'))};"
                    f"full_commercial_evidence_receipt_required_inputs={_text(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_required_inputs'))};"
                    f"full_commercial_evidence_receipt_approval_tokens={_text(goal_bottleneck_briefing.get('full_commercial_evidence_receipt_approval_tokens'))}"
                ),
                required=(
                    "goal_bottleneck_briefing_ready with R8/R9 completion blockers and full-commercial receipt "
                    "operator handoff summary recorded"
                ),
                passed=goal_bottleneck_full_commercial_receipts_recorded,
                reason=(
                    "The final release decision must preserve the bottleneck briefing's R8/R9 receipt "
                    "handoff summary, not only the downstream matrix diagnostics."
                ),
            )
        )
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded",
                artifact_path=goal_bottleneck_briefing_path,
                observed=(
                    f"{_text(goal_bottleneck_briefing.get('status')) or 'missing'};"
                    f"production_ai_registry_promotion_priority_status={_text(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_status'))};"
                    f"production_ai_registry_promotion_priority_packet_ready={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_packet_ready') is True))};"
                    f"production_ai_registry_promotion_priority_registry_promotion_ready={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_registry_promotion_ready') is True))};"
                    f"production_ai_registry_promotion_priority_operator_input_required_count={_int(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_operator_input_required_count'))};"
                    f"production_ai_registry_promotion_priority_blocked_priority_item_count={_int(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_blocked_priority_item_count'))};"
                    f"production_ai_registry_promotion_priority_missing_gate_count={_int(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_missing_gate_count'))};"
                    f"production_ai_registry_promotion_priority_missing_gate_ids={';'.join(goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids)};"
                    f"production_ai_registry_promotion_priority_top_gate_id={_text(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_top_gate_id'))};"
                    f"production_ai_registry_promotion_priority_top_priority_bucket={_text(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_top_priority_bucket'))};"
                    f"production_ai_registry_promotion_priority_model_promoted={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_model_promoted') is True))};"
                    f"production_ai_registry_promotion_priority_customer_facing_mutation_enabled={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_customer_facing_mutation_enabled') is True))};"
                    f"production_ai_registry_promotion_priority_external_state_mutated={_bool_text(bool(goal_bottleneck_briefing.get('production_ai_registry_promotion_priority_external_state_mutated') is True))}"
                ),
                required=(
                    "goal_bottleneck_briefing_ready with Production AI registry promotion priority packet "
                    "recorded and top gate default_residual_mode_guarded preserved"
                ),
                passed=goal_bottleneck_production_ai_registry_promotion_priority_recorded,
                reason=(
                    "The final release decision must preserve the bottleneck briefing's Production AI registry "
                    "promotion top gate so model-promotion work cannot disappear behind restricted-release readiness."
                ),
            )
        )
    if production_ai_registry_priority_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="production_ai_registry_promotion_priority_packet_recorded",
                artifact_path=production_ai_registry_promotion_priority_packet_path,
                observed=(
                    f"{_text(production_ai_registry_priority.get('status')) or 'missing'};"
                    f"priority_packet_ready="
                    f"{_bool_text(bool(production_ai_registry_priority.get('priority_packet_ready') is True))};"
                    f"registry_promotion_ready="
                    f"{_bool_text(bool(production_ai_registry_priority.get('registry_promotion_ready') is True))};"
                    f"priority_item_count={_int(production_ai_registry_priority.get('priority_item_count'))};"
                    f"operator_input_required_count="
                    f"{_int(production_ai_registry_priority.get('operator_input_required_count'))};"
                    f"blocked_priority_item_count="
                    f"{_int(production_ai_registry_priority.get('blocked_priority_item_count'))};"
                    f"missing_gate_count="
                    f"{_int(production_ai_registry_priority.get('registry_promotion_missing_gate_count'))};"
                    f"missing_gate_ids={';'.join(production_ai_registry_priority_missing_gate_ids)};"
                    f"top_gate_id={_text(production_ai_registry_priority.get('top_gate_id'))};"
                    f"top_priority_bucket={_text(production_ai_registry_priority.get('top_priority_bucket'))};"
                    f"observed_registry_trained_model_checkpoint_count="
                    f"{_int(production_ai_registry_priority.get('observed_registry_trained_model_checkpoint_count'))};"
                    f"observed_registry_default_residual_mode="
                    f"{_text(production_ai_registry_priority.get('observed_registry_default_residual_mode'))};"
                    f"observed_registry_production_promotion_allowed="
                    f"{_bool_text(bool(production_ai_registry_priority.get('observed_registry_production_promotion_allowed') is True))};"
                    f"observed_registry_customer_facing_mutation_flags_ready="
                    f"{_bool_text(bool(production_ai_registry_priority.get('observed_registry_customer_facing_mutation_flags_ready') is True))};"
                    f"operator_receipt_status="
                    f"{_text(production_ai_registry_priority.get('operator_receipt_status'))};"
                    f"operator_receipt_artifact="
                    f"{_text(production_ai_registry_priority.get('operator_receipt_artifact'))};"
                    f"operator_receipt_csv={_text(production_ai_registry_priority.get('operator_receipt_csv'))};"
                    f"approval_token_required="
                    f"{_text(production_ai_registry_priority.get('approval_token_required'))};"
                    f"model_promoted={_bool_text(bool(production_ai_registry_priority.get('model_promoted') is True))};"
                    f"registry_edited_by_this_tool="
                    f"{_bool_text(bool(production_ai_registry_priority.get('registry_edited_by_this_tool') is True))};"
                    f"checkpoint_created_by_this_tool="
                    f"{_bool_text(bool(production_ai_registry_priority.get('checkpoint_created_by_this_tool') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(production_ai_registry_priority.get('external_state_mutated') is True))}"
                ),
                required=(
                    "Production AI registry promotion priority packet recorded with observed registry gates, "
                    "operator receipt inputs, approval token, and no tool-side promotion"
                ),
                passed=production_ai_registry_priority_recorded,
                reason=(
                    "The final release decision must preserve the direct registry/checkpoint/customer-mutation "
                    "promotion blockers, not only the bottleneck-briefing rollup."
                ),
            )
        )
    if production_ai_checkpoint_readiness_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="production_ai_checkpoint_readiness_recorded",
                artifact_path=product_production_ai_checkpoint_readiness_path,
                observed=(
                    f"{_text(production_ai_checkpoint_readiness.get('status')) or 'missing'};"
                    f"checkpoint_ready="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('production_ai_checkpoint_ready') is True))};"
                    f"inference_subject_active="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('production_ai_inference_subject_active') is True))};"
                    f"gpu_environment_ready="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('production_gpu_execution_environment_ready') is True))};"
                    f"delta_force_derivation_validation_ready="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('delta_force_derivation_validation_ready') is True))};"
                    f"checkpoint_preflight_ready="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('checkpoint_preflight_ready') is True))};"
                    f"acceptance_ready_stage_count="
                    f"{_int(production_ai_checkpoint_readiness.get('production_inference_acceptance_ready_stage_count'))};"
                    f"acceptance_blocked_stage_count="
                    f"{_int(production_ai_checkpoint_readiness.get('production_inference_acceptance_blocked_stage_count'))};"
                    f"first_failed_check_id="
                    f"{_text(production_ai_checkpoint_readiness.get('first_failed_check_id'))};"
                    f"actionable_blocker_stage_id="
                    f"{_text(production_ai_checkpoint_readiness.get('production_inference_actionable_blocker_stage_id'))};"
                    f"registry_promotion_missing_gate_count="
                    f"{_int(production_ai_checkpoint_readiness.get('registry_promotion_missing_gate_count'))};"
                    f"registry_promotion_missing_gate_ids="
                    f"{';'.join(production_ai_checkpoint_readiness_missing_gate_ids)};"
                    f"trained_model_checkpoint_count="
                    f"{_int(production_ai_checkpoint_readiness.get('trained_model_checkpoint_count'))};"
                    f"default_residual_mode={_text(production_ai_checkpoint_readiness.get('default_residual_mode'))};"
                    f"production_promotion_allowed="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('production_promotion_allowed') is True))};"
                    f"customer_facing_mutation_flags="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('customer_facing_score_mutation_allowed') is True) and bool(production_ai_checkpoint_readiness.get('customer_facing_ranking_mutation_allowed') is True))};"
                    f"model_promoted="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('model_promoted') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(production_ai_checkpoint_readiness.get('external_state_mutated') is True))}"
                ),
                required=(
                    "Product production AI checkpoint readiness recorded with upstream acceptance ready, "
                    "registry guarded promotion as the only blocked acceptance stage, one trained checkpoint, "
                    "customer-facing mutation disabled, and no external mutation"
                ),
                passed=production_ai_checkpoint_readiness_recorded,
                reason=(
                    "The final release decision must preserve the original checkpoint-readiness blocker "
                    "so the Production AI transition is not represented only by the downstream priority packet."
                ),
            )
        )
    if production_ai_promotion_workbench_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="production_ai_promotion_workbench_recorded",
                artifact_path=product_production_ai_promotion_workbench_path,
                observed=(
                    f"{_text(production_ai_promotion_workbench.get('status')) or 'missing'};"
                    f"promotion_workbench_ready="
                    f"{_bool_text(bool(production_ai_promotion_workbench.get('promotion_workbench_ready') is True))};"
                    f"promotion_ready="
                    f"{_bool_text(bool(production_ai_promotion_workbench.get('production_ai_promotion_ready') is True))};"
                    f"checkpoint_readiness_artifact_path="
                    f"{_text(production_ai_promotion_workbench.get('checkpoint_readiness_artifact_path'))};"
                    f"post_return_ladder_stage_count="
                    f"{_int(production_ai_promotion_workbench.get('post_return_promotion_ladder_stage_count'))};"
                    f"post_return_ladder_ready_stage_count="
                    f"{_int(production_ai_promotion_workbench.get('post_return_promotion_ladder_ready_stage_count'))};"
                    f"post_return_ladder_blocked_stage_count="
                    f"{_int(production_ai_promotion_workbench.get('post_return_promotion_ladder_blocked_stage_count'))};"
                    f"blocked_stage_ids={';'.join(production_ai_promotion_workbench_blocked_stage_ids)};"
                    f"first_blocked_stage_id={_text(production_ai_promotion_workbench.get('first_blocked_stage_id'))};"
                    f"first_blocked_stage_ready_key="
                    f"{_text(production_ai_promotion_workbench.get('first_blocked_stage_ready_key'))};"
                    f"registry_promotion_missing_gate_count="
                    f"{_int(production_ai_promotion_workbench.get('registry_promotion_missing_gate_count'))};"
                    f"registry_promotion_missing_gate_ids="
                    f"{';'.join(production_ai_promotion_workbench_missing_gate_ids)};"
                    f"trained_model_checkpoint_count="
                    f"{_int(production_ai_promotion_workbench.get('trained_model_checkpoint_count'))};"
                    f"default_residual_mode={_text(production_ai_promotion_workbench.get('default_residual_mode'))};"
                    f"production_promotion_allowed="
                    f"{_bool_text(bool(production_ai_promotion_workbench.get('production_promotion_allowed') is True))};"
                    f"model_promoted={_bool_text(bool(production_ai_promotion_workbench.get('model_promoted') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(production_ai_promotion_workbench.get('external_state_mutated') is True))}"
                ),
                required=(
                    "Product production AI promotion workbench recorded with a ready workbench, blocked "
                    "residual registry/product-goal stages, one trained checkpoint, and no promotion/mutation"
                ),
                passed=production_ai_promotion_workbench_recorded,
                reason=(
                    "The final release decision must keep the post-return promotion ladder visible so a "
                    "restricted release cannot hide the registry and goal-completion stages that still block "
                    "Production AI promotion."
                ),
            )
        )
    if release_source_of_truth_gate_present:
        rows.append(
            _row(
                lane_id="goal_release",
                check="product_release_source_of_truth_ready",
                artifact_path=product_release_source_of_truth_path,
                observed=(
                    f"{_text(release_source_of_truth.get('status')) or 'missing'};"
                    f"ready={_bool_text(release_source_of_truth_ready)};"
                    f"blocker_count={_int(release_source_of_truth.get('blocker_count'))};"
                    f"stale_artifact_count={_int(release_source_of_truth.get('stale_artifact_count'))};"
                    f"readme_drift_count={_int(release_source_of_truth.get('readme_drift_count'))};"
                    f"missing_artifact_count={_int(release_source_of_truth.get('missing_artifact_count'))}"
                ),
                required="product_release_source_of_truth_gate_ready;release_source_of_truth_ready=true;blocker_count=0",
                passed=release_source_of_truth_ready,
                reason="Release must fail when any current artifact is stale against its source dependencies or README metrics drift from current JSON evidence.",
            )
        )
    if product_quality_gate_present:
        rows.append(
            _row(
                lane_id="goal_release",
                check="product_quality_gate_verification_recorded",
                artifact_path=product_quality_gate_verification_path,
                observed=(
                    f"{_text(product_quality_gate.get('status')) or 'missing'};"
                    f"quality_gate_ready={_bool_text(bool(product_quality_gate.get('quality_gate_ready') is True))};"
                    f"source_contract_status={_text(product_quality_gate.get('source_contract_status'))};"
                    f"check_count={_int(product_quality_gate.get('check_count'))};"
                    f"pass_count={_int(product_quality_gate.get('pass_count'))};"
                    f"source_contract_check_count={_int(product_quality_gate.get('source_contract_check_count'))};"
                    f"source_contract_pass_count={_int(product_quality_gate.get('source_contract_pass_count'))};"
                    f"blocker_count={_int(product_quality_gate.get('blocker_count'))};"
                    f"execution_enabled={_bool_text(bool(product_quality_gate.get('execution_enabled') is True))};"
                    f"external_state_mutated={_bool_text(bool(product_quality_gate.get('external_state_mutated') is True))}"
                ),
                required=(
                    "product_quality_gate_verified with quality_gate_ready=true, zero blockers, "
                    "4/4 verification checks, product_operational_quality_contract_ready source, "
                    "and no execution or external mutation"
                ),
                passed=product_quality_gate_verified,
                reason=(
                    "The final release decision must directly preserve the operational quality verifier "
                    "receipt, not only the source-of-truth or release-bundle rollup that references it."
                ),
            )
        )
    if product_pose_sampling_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_pose_sampling_readiness_recorded",
                artifact_path=product_pose_sampling_readiness_path,
                observed=(
                    f"{_text(product_pose_sampling.get('status')) or 'missing'};"
                    f"pose_sampling_readiness_ready="
                    f"{_bool_text(bool(product_pose_sampling.get('pose_sampling_readiness_ready') is True))};"
                    f"pose_generation_contract_ready="
                    f"{_bool_text(bool(product_pose_sampling.get('pose_generation_contract_ready') is True))};"
                    f"pocket_detection_ready="
                    f"{_bool_text(bool(product_pose_sampling.get('pocket_detection_ready') is True))};"
                    f"requested_pose_start_count={_int(product_pose_sampling.get('requested_pose_start_count'))};"
                    f"pose_count={_int(product_pose_sampling.get('pose_count'))};"
                    f"cluster_count={_int(product_pose_sampling.get('cluster_count'))};"
                    f"cross_docking_pose_count={_int(product_pose_sampling.get('cross_docking_pose_count'))};"
                    f"pocket_method={_text(product_pose_sampling.get('pocket_method'))};"
                    f"claim_grade_pose_accuracy_ready="
                    f"{_bool_text(bool(product_pose_sampling.get('claim_grade_pose_accuracy_ready') is True))};"
                    f"claim_grade_induced_fit_ready="
                    f"{_bool_text(bool(product_pose_sampling.get('claim_grade_induced_fit_ready') is True))};"
                    f"claim_grade_cross_docking_ready="
                    f"{_bool_text(bool(product_pose_sampling.get('claim_grade_cross_docking_ready') is True))};"
                    f"docking_results_emitted="
                    f"{_bool_text(bool(product_pose_sampling.get('docking_results_emitted') is True))};"
                    f"execution_enabled="
                    f"{_bool_text(bool(product_pose_sampling.get('execution_enabled') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(product_pose_sampling.get('external_state_mutated') is True))}"
                ),
                required=(
                    "product_pose_sampling_readiness_ready with 6 local starts, >=2 RMSD clusters, "
                    "bounded cross-docking/induced-fit guard, claim-grade pose accuracy/cross-target "
                    "claims blocked, and no docking result emission or external mutation"
                ),
                passed=product_pose_sampling_recorded,
                reason=(
                    "The final release decision must directly preserve the local pose-sampling smoke "
                    "receipt so ligand-docking readiness cannot be represented only by downstream "
                    "AI graph, release-bundle, or source-of-truth rollups."
                ),
            )
        )
    if product_ledger_privacy_scan_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_ledger_privacy_scan_recorded",
                artifact_path=product_ledger_privacy_scan_path,
                observed=(
                    f"{_text(product_ledger_privacy_scan.get('status')) or 'missing'};"
                    f"ledger_privacy_scan_ready="
                    f"{_bool_text(bool(product_ledger_privacy_scan.get('ledger_privacy_scan_ready') is True))};"
                    f"scan_file_count={product_ledger_privacy_scan_scan_file_count};"
                    f"scan_glob_count={product_ledger_privacy_scan_glob_count};"
                    f"pass_count={product_ledger_privacy_scan_pass_count};"
                    f"blocker_count={_int(product_ledger_privacy_scan.get('blocker_count'))};"
                    f"leak_count={_int(product_ledger_privacy_scan.get('leak_count'))};"
                    f"invalid_json_count={_int(product_ledger_privacy_scan.get('invalid_json_count'))};"
                    f"blocked_artifact_path_count="
                    f"{len(_text_list(product_ledger_privacy_scan.get('blocked_artifact_paths')))};"
                    f"invalid_json_path_count="
                    f"{len(_text_list(product_ledger_privacy_scan.get('invalid_json_paths')))};"
                    f"execution_enabled="
                    f"{_bool_text(bool(product_ledger_privacy_scan.get('execution_enabled') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(product_ledger_privacy_scan.get('external_state_mutated') is True))}"
                ),
                required=(
                    "product_ledger_privacy_scan_ready with every scanned local JSON artifact passing, "
                    "zero raw molecular payload leaks, zero invalid JSON files, and no execution or "
                    "external mutation"
                ),
                passed=product_ledger_privacy_scan_recorded,
                reason=(
                    "The final release decision must directly preserve the privacy scan receipt so raw "
                    "SMILES, inline PDB text, or ligand source values in goal-facing JSON artifacts "
                    "cannot be hidden behind source-of-truth or bundle rollups."
                ),
            )
        )
    if full_commercial_matrix_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_full_commercial_blocker_evidence_matrix_recorded",
                artifact_path=product_full_commercial_blocker_evidence_matrix_path,
                observed=(
                    f"{_text(full_commercial_matrix.get('status')) or 'missing'};"
                    f"matrix_ready={_bool_text(bool(full_commercial_matrix.get('full_commercial_blocker_evidence_matrix_ready') is True))};"
                    f"release_blocker_visibility_ready={_bool_text(bool(full_commercial_matrix.get('release_blocker_visibility_ready') is True))};"
                    f"matrix_row_count={_int(full_commercial_matrix.get('matrix_row_count'))};"
                    f"blocked_matrix_row_count={_int(full_commercial_matrix.get('blocked_matrix_row_count'))};"
                    f"approval_token_count={_int(full_commercial_matrix.get('approval_token_count'))};"
                    f"first_blocked_release_blocker_id={_text(full_commercial_matrix.get('first_blocked_release_blocker_id'))};"
                    f"first_blocked_evidence_row_id={_text(full_commercial_matrix.get('first_blocked_evidence_row_id'))};"
                    f"first_blocked_evidence_artifact={_text(full_commercial_matrix.get('first_blocked_evidence_artifact'))};"
                    f"first_blocked_expected_evidence_status={_text(full_commercial_matrix.get('first_blocked_expected_evidence_status'))};"
                    f"first_blocked_observed_evidence_status={_text(full_commercial_matrix.get('first_blocked_observed_evidence_status'))};"
                    f"first_blocked_row_blockers={_text(full_commercial_matrix.get('first_blocked_row_blockers'))};"
                    f"scope_receipt_most_common_row_blocker={_text(full_commercial_matrix.get('scope_receipt_most_common_row_blocker'))};"
                    f"engine_receipt_most_common_row_blocker={_text(full_commercial_matrix.get('engine_receipt_most_common_row_blocker'))}"
                ),
                required="R8/R9 full-commercial blocker matrix recorded with release blocker visibility and read-only flags",
                passed=full_commercial_matrix_recorded,
                reason="The final release decision must not hide R8/R9 full-commercial evidence receipt blockers even when restricted release source-of-truth is green.",
            )
        )
    if rollout_smoke_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_rollout_execution_smoke_receipt_recorded",
                artifact_path=product_rollout_execution_smoke_receipt_path,
                observed=(
                    f"{_text(rollout_smoke.get('status')) or 'missing'};"
                    f"receipt_ready={_bool_text(bool(rollout_smoke.get('rollout_execution_smoke_receipt_ready') is True))};"
                    f"receipt_csv_present={_bool_text(bool(rollout_smoke.get('receipt_csv_present') is True))};"
                    f"receipt_row_count={_int(rollout_smoke.get('receipt_row_count'))};"
                    f"blocker_count={_int(rollout_smoke.get('blocker_count'))};"
                    f"rollout_executed={_bool_text(bool(rollout_smoke.get('rollout_executed') is True))};"
                    f"external_state_mutated={_bool_text(bool(rollout_smoke.get('external_state_mutated') is True))};"
                    f"pager_provider_contacted={_bool_text(bool(rollout_smoke.get('pager_provider_contacted') is True))};"
                    f"ingress_certificate_verified_live={_bool_text(bool(rollout_smoke.get('ingress_certificate_verified_live') is True))}"
                ),
                required="R4 rollout execution smoke receipt status recorded without this decision gate executing rollout",
                passed=rollout_smoke_recorded,
                reason="The final release decision must not hide whether the separate R4/operator-approved rollout smoke has actually been executed.",
            )
        )
    if master_gap_rollup_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="master_gap_closure_rollup_recorded",
                artifact_path=master_gap_closure_rollup_path,
                observed=(
                    f"{_text(master_gap_rollup.get('status')) or 'missing'};"
                    f"all_gaps_closed={_bool_text(bool(master_gap_rollup.get('all_gaps_closed') is True))};"
                    f"claim_promotion_allowed={_bool_text(bool(master_gap_rollup.get('claim_promotion_allowed') is True))};"
                    f"open_gap_count={_int(master_gap_rollup.get('open_gap_count'))};"
                    f"open_gap_ids={';'.join(master_gap_open_ids)};"
                    f"closed_gap_count={_int(master_gap_rollup.get('closed_gap_count'))};"
                    f"closed_gap_ids={';'.join(master_gap_closed_ids)};"
                    f"release_blocker_row_count={len(master_gap_release_blocker_rows)};"
                    f"current_primary_open_gap_id={_text(master_gap_rollup.get('current_primary_open_gap_id'))};"
                    f"science_claim_rollup_status={_text(master_gap_science_claim_row.get('rollup_status'))};"
                    f"science_claim_evidence={_text(master_gap_science_claim_row.get('evidence'))};"
                    f"science_claim_release_blocker={_bool_text(bool(master_gap_science_claim_row.get('release_blocker') is True))}"
                ),
                required=(
                    "master gap closure rollup recorded complete with SCI-CLAIM closed, "
                    "no release-blocking master rows, and claim promotion still locked"
                ),
                passed=master_gap_rollup_recorded,
                reason=(
                    "The final release decision must show that science accounting is closed "
                    "without implying broad full-commercial claim promotion is allowed."
                ),
            )
        )
    if accuracy_parity_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="accuracy_parity_scorecard_recorded",
                artifact_path=accuracy_parity_scorecard_path,
                observed=(
                    f"{_text(accuracy_parity.get('status')) or 'missing'};"
                    f"overall_commercial_tool_accuracy_parity_allowed="
                    f"{_bool_text(bool(accuracy_parity.get('overall_commercial_tool_accuracy_parity_allowed') is True))};"
                    f"schrodinger_class_claim_allowed="
                    f"{_bool_text(bool(accuracy_parity.get('schrodinger_class_claim_allowed') is True))};"
                    f"row_count={_int(accuracy_parity.get('row_count'))};"
                    f"pass_row_count={_int(accuracy_parity.get('pass_row_count'))};"
                    f"restricted_pass_row_count={_int(accuracy_parity.get('restricted_pass_row_count'))};"
                    f"blocked_row_count={_int(accuracy_parity.get('blocked_row_count'))};"
                    f"top_blockers={';'.join(accuracy_parity_top_blockers)};"
                    f"ligand_ranking_status={_text(accuracy_ligand_ranking.get('status'))};"
                    f"ligand_ranking_pr_auc={accuracy_ligand_pr_auc};"
                    f"ligand_ranking_pr_auc_ci_low={accuracy_ligand_pr_auc_ci_low};"
                    f"ligand_ranking_topk_hit_rate={accuracy_ligand_topk_hit_rate};"
                    f"ligand_ranking_metric_thresholds_pass="
                    f"{_bool_text(accuracy_ligand_metric_thresholds_pass)};"
                    f"ligand_ranking_metric_blocker_count={len(accuracy_ligand_metric_blockers)};"
                    f"ligand_ranking_claim_scope_lock_only="
                    f"{_bool_text(accuracy_ligand_claim_scope_lock_only)};"
                    f"ligand_ranking_blockers={';'.join(accuracy_ligand_blockers)}"
                ),
                required=(
                    "accuracy parity scorecard recorded with frozen-row claim boundary and "
                    "ligand_ranking restricted-pass broad-claim lock visibility"
                ),
                passed=accuracy_parity_scorecard_recorded,
                reason=(
                    "The final release decision must preserve the broad GPCR/Schrodinger-class "
                    "claim lock even after the tracked ligand-ranking metrics clear."
                ),
            )
        )
    if science_claim_gap_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="science_claim_promotion_gap_closure_recorded",
                artifact_path=science_claim_promotion_gap_path,
                observed=(
                    f"{_text(science_claim_gap.get('status')) or 'missing'};"
                    f"all_gaps_closed={_bool_text(bool(science_claim_gap.get('all_gaps_closed') is True))};"
                    f"claim_promotion_allowed={_bool_text(bool(science_claim_gap.get('claim_promotion_allowed') is True))};"
                    f"open_gap_count={_int(science_claim_gap.get('open_gap_count'))};"
                    f"open_gap_ids={';'.join(science_claim_open_gap_ids)};"
                    f"closed_gap_count={_int(science_claim_gap.get('closed_gap_count'))};"
                    f"closed_gap_ids={';'.join(science_claim_closed_gap_ids)};"
                    f"release_blocker_row_count={len(science_claim_release_blocker_rows)};"
                    f"current_primary_open_gap_id={science_claim_primary_open_gap_id};"
                    f"primary_open_gap_area={_text(science_claim_primary_open_gap.get('area'))};"
                    f"primary_open_gap_claim_promotion_status={_text(science_claim_primary_open_gap.get('claim_promotion_status'))};"
                    f"primary_open_gap_evidence={_text(science_claim_primary_open_gap.get('evidence'))};"
                    f"gpcr_claim_promotion_status={_text(science_claim_gpcr_gap.get('claim_promotion_status'))};"
                    f"gpcr_evidence={_text(science_claim_gpcr_gap.get('evidence'))};"
                    f"gpcr_release_blocker={_bool_text(bool(science_claim_gpcr_gap.get('release_blocker') is True))};"
                    f"openmm_claim_promotion_status={_text(science_claim_openmm_gap.get('claim_promotion_status'))};"
                    f"openmm_evidence={_text(science_claim_openmm_gap.get('evidence'))};"
                    f"openmm_release_blocker={_bool_text(bool(science_claim_openmm_gap.get('release_blocker') is True))}"
                ),
                required=(
                    "science claim promotion gap closure recorded complete with SCI-GPCR and "
                    "SCI-OPENMM closed, no release-blocking science rows, and claim promotion still locked"
                ),
                passed=science_claim_gap_recorded,
                reason=(
                    "The final release decision must preserve the science-claim sub-gap accounting "
                    "without treating closed boundary rows as broad claim promotion."
                ),
            )
        )
    if api_customer_flow_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="api_customer_flow_release_evidence_ready",
                artifact_path=api_customer_flow_release_evidence_path,
                observed=(
                    f"{_text(api_customer_flow.get('status')) or 'missing'};"
                    f"formal_release_evidence_ready={_bool_text(api_customer_flow_ready)};"
                    f"clean_install_flow_ready={_bool_text(bool(api_customer_flow.get('clean_install_flow_ready') is True))};"
                    f"result_manifest_signature_verified={_bool_text(bool(api_customer_flow.get('result_manifest_signature_verified') is True))};"
                    f"bundle_validation_ready={_bool_text(bool(api_customer_flow.get('bundle_validation_ready') is True))};"
                    f"restricted_runtime={_bool_text(bool(api_customer_flow.get('restricted_unattended_runtime_ready') is True))};"
                    f"blocker_count={_int(api_customer_flow.get('blocker_count'))}"
                ),
                required="api_customer_flow_release_evidence_ready with live job, signed result manifest, bundle validation, and restricted runtime readiness",
                passed=api_customer_flow_ready,
                reason="Customer-facing API release claims require live end-to-end evidence, not only static wiring or synthetic ledger sync.",
            )
        )
    if product_ai_architecture_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="product_ai_architecture_gap_closure_ready",
                artifact_path=f"{product_ai_architecture_gap_path};{product_ai_execution_backlog_path}",
                observed=(
                    f"ai_gap_status={_text(product_ai_architecture.get('status')) or 'missing'};"
                    f"all_gaps_closed={_bool_text(bool(product_ai_architecture.get('all_gaps_closed') is True))};"
                    f"open_gap_count={_int(product_ai_architecture.get('open_gap_count'))};"
                    f"current_primary_open_gap={_text(product_ai_architecture.get('current_primary_open_gap')) or 'missing'};"
                    f"backlog_clear={_bool_text(bool(product_ai_backlog.get('backlog_clear') is True))};"
                    f"work_item_count={_int(product_ai_backlog.get('work_item_count'))};"
                    f"release_blocking_work_item_count={product_ai_release_blocking_work_item_count};"
                    f"optional_work_item_count={product_ai_optional_work_item_count};"
                    f"primary_work_item_id={_text(product_ai_backlog.get('primary_work_item_id')) or 'missing'};"
                    f"{product_ai_backlog_detail}"
                    + (f";{product_ai_scope_detail}" if product_ai_scope_detail else "")
                ),
                required=(
                    "release_blocking_work_item_count=0 with product AI gap/backlog artifacts present; "
                    "optional AI open gaps and backlog may remain deferred"
                ),
                passed=product_ai_architecture_ready,
                reason=(
                    (
                        "Product AI open gaps are optional/non-release-blocking for this physics-first release; "
                        "keep production AI promotion, score mutation, and broad scope expansion deferred. "
                    )
                    if product_ai_architecture_ready
                    else (
                        "Commercial release cannot be allowed while the product AI architecture has "
                        "release-blocking backlog items or missing evidence artifacts. "
                    )
                    + f"{product_ai_backlog_detail}"
                    + (f";{product_ai_scope_detail}" if product_ai_scope_detail else "")
                ).strip(),
            )
        )
    if self_hosted_license_audit_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="self_hosted_license_distribution_audit_recorded",
                artifact_path=self_hosted_license_distribution_audit_path,
                observed=(
                    f"{_text(self_hosted_license_audit.get('status')) or 'missing'};"
                    f"product_license_path={_text(self_hosted_license_audit.get('product_license_path'))};"
                    f"approved_license_text_source="
                    f"{_text(self_hosted_license_audit.get('approved_license_text_source'))};"
                    f"license_hashes_match={_bool_text(self_hosted_license_audit_hashes_match)};"
                    f"spdx_license_id={_text(self_hosted_license_audit.get('spdx_license_id'))};"
                    f"hard_blocker_count={_int(self_hosted_license_audit.get('hard_blocker_count'))};"
                    f"operator_review_item_count="
                    f"{_int(self_hosted_license_audit.get('operator_review_item_count'))};"
                    f"third_party_license_review_gate_status="
                    f"{_text(self_hosted_license_audit.get('third_party_license_review_gate_status'))};"
                    f"third_party_license_review_gate_ready="
                    f"{_bool_text(bool(self_hosted_license_audit.get('third_party_license_review_gate_ready') is True))};"
                    f"third_party_license_review_gate_blocker_count="
                    f"{_int(self_hosted_license_audit.get('third_party_license_review_gate_blocker_count'))};"
                    f"third_party_dual_license_assets={';'.join(self_hosted_license_audit_dual_license_assets)};"
                    f"viewer_third_party_notice_path="
                    f"{_text(self_hosted_license_audit.get('viewer_third_party_notice_path'))};"
                    f"legal_advice_provided="
                    f"{_bool_text(bool(self_hosted_license_audit.get('legal_advice_provided') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(self_hosted_license_audit.get('external_state_mutated') is True))}"
                ),
                required=(
                    "self-hosted license audit recorded with matching product license hash, "
                    "ProprietaryRef-Betelgeuze metadata, zero hard blockers, JSZip review linkage, "
                    "no legal advice claim, and no external mutation"
                ),
                passed=self_hosted_license_audit_recorded,
                reason=(
                    "The final release decision must preserve the technical license-distribution audit "
                    "boundary and the operator/legal review item instead of collapsing license readiness "
                    "into commercial-independence status alone."
                ),
            )
        )
    if third_party_license_review_gate_present:
        rows.append(
            _row(
                lane_id="commercial_product_release",
                check="third_party_license_review_gate_recorded",
                artifact_path=third_party_license_review_gate_path,
                observed=(
                    f"{_text(third_party_license_review.get('status')) or 'missing'};"
                    f"approved_assets={';'.join(third_party_license_review_approved_assets)};"
                    f"allowed_license_paths={';'.join(third_party_license_review_allowed_license_paths)};"
                    f"expected_review_asset_count="
                    f"{_int(third_party_license_review.get('expected_review_asset_count'))};"
                    f"review_row_count={_int(third_party_license_review.get('review_row_count'))};"
                    f"approved_review_asset_count="
                    f"{_int(third_party_license_review.get('approved_review_asset_count'))};"
                    f"missing_review_asset_count="
                    f"{_int(third_party_license_review.get('missing_review_asset_count'))};"
                    f"deferred_review_asset_count="
                    f"{_int(third_party_license_review.get('deferred_review_asset_count'))};"
                    f"blocker_count={_int(third_party_license_review.get('blocker_count'))};"
                    f"review_csv={_text(third_party_license_review.get('review_csv'))};"
                    f"review_csv_present="
                    f"{_bool_text(bool(third_party_license_review.get('review_csv_present') is True))};"
                    f"operator_template_csv="
                    f"{_text(third_party_license_review.get('operator_template_csv'))};"
                    f"approval_token_required="
                    f"{_text(third_party_license_review.get('approval_token_required'))};"
                    f"source_license_audit_status="
                    f"{_text(third_party_license_review.get('source_license_audit_status'))};"
                    f"source_hard_blocker_count="
                    f"{_int(third_party_license_review.get('source_hard_blocker_count'))};"
                    f"source_operator_review_item_count="
                    f"{_int(third_party_license_review.get('source_operator_review_item_count'))};"
                    f"legal_advice_provided="
                    f"{_bool_text(bool(third_party_license_review.get('legal_advice_provided') is True))};"
                    f"asset_modified="
                    f"{_bool_text(bool(third_party_license_review.get('asset_modified') is True))};"
                    f"external_state_mutated="
                    f"{_bool_text(bool(third_party_license_review.get('external_state_mutated') is True))}"
                ),
                required=(
                    "third-party license review gate ready for JSZip with operator intake, approval token, "
                    "zero blockers, no asset mutation, no legal advice claim, and no external mutation"
                ),
                passed=third_party_license_review_recorded,
                reason=(
                    "The final release decision must keep JSZip dual-license redistribution review visible "
                    "as an operator/legal boundary even when the technical review gate is ready."
                ),
            )
        )

    blocker_count = sum(1 for row in rows if row["release_blocker"])
    product_release_ready = (
        product_architecture_ready
        and product_ready
        and product_claim_allowed
        and product_bundle_validated
        and product_commercial_independence_ready
    )
    cameo_architecture_validation_ready = cameo_evidence_ready and cameo_official_used and (
        (cameo_public_registration_allowed and cameo_capability_ready) or cameo_registration_gate_ready
    )
    cleanup_objective_ready = (
        cleanup_postcheck_ready
        and transition_cleanup_done
        and ligand_cleanup_done
        and protected_policy_resolved
    )
    release_allowed = blocker_count == 0
    full_commercial_release_blocker_ids = (
        list(full_commercial_matrix.get("expected_release_blocker_ids") or [])
        if full_commercial_matrix_gate_present
        and _int(full_commercial_matrix.get("blocked_matrix_row_count")) > 0
        else []
    )
    if master_gap_rollup_gate_present and master_gap_open_ids:
        full_commercial_release_blocker_ids.extend(
            f"MASTER:{gap_id}" for gap_id in master_gap_open_ids if f"MASTER:{gap_id}" not in full_commercial_release_blocker_ids
        )
    if accuracy_parity_full_commercial_blocked:
        full_commercial_release_blocker_ids.append("ACCURACY:ligand_ranking")
    full_commercial_release_blocker_ids = list(dict.fromkeys(full_commercial_release_blocker_ids))
    primary_full_commercial_release_blocker_id = (
        _text(full_commercial_matrix.get("first_blocked_release_blocker_id"))
        or (f"MASTER:{master_gap_open_ids[0]}" if master_gap_open_ids else "")
    )
    primary_full_commercial_release_blocker_requirement_id = primary_full_commercial_release_blocker_id
    primary_full_commercial_release_blocker_blocked_row_count = _int(
        _dict_get(
            full_commercial_matrix.get("release_blocker_blocked_row_counts"),
            primary_full_commercial_release_blocker_id,
        )
    )
    primary_full_commercial_release_blocker_first_blocked_evidence_row_id = _text(
        _dict_get(
            full_commercial_matrix.get("release_blocker_first_blocked_evidence_row_ids"),
            primary_full_commercial_release_blocker_id,
        )
    )
    primary_full_commercial_release_blocker_receipt_csv = _text(
        _dict_get(
            full_commercial_matrix.get("release_blocker_receipt_csvs"),
            primary_full_commercial_release_blocker_id,
        )
    )
    primary_full_commercial_release_blocker_approval_token_required = _text(
        _dict_get(
            full_commercial_matrix.get("release_blocker_approval_tokens_required"),
            primary_full_commercial_release_blocker_id,
        )
    )
    primary_full_commercial_release_blocker_next_required_step = _text(
        _dict_get(
            full_commercial_matrix.get("release_blocker_next_required_steps"),
            primary_full_commercial_release_blocker_id,
        )
    ) or _text(full_commercial_matrix.get("next_required_step"))
    full_commercial_release_allowed = (
        release_allowed
        and (
            not full_commercial_matrix_gate_present
            or bool(full_commercial_matrix.get("full_commercial_blocker_evidence_matrix_ready") is True)
        )
        and (not master_gap_rollup_gate_present or bool(master_gap_rollup.get("all_gaps_closed") is True))
        and (
            not accuracy_parity_gate_present
            or bool(accuracy_parity.get("overall_commercial_tool_accuracy_parity_allowed") is True)
        )
    )
    next_required_items: list[str] = []
    if not product_bundle_validated or not product_ready or not product_claim_allowed:
        next_required_items.append("product bundle validation")
    if not product_commercial_independence_ready:
        next_required_items.append("commercial-independence packaging")
    if not product_architecture_public_benchmark_ready:
        next_required_items.append("public benchmark scorecards")
    if cameo_fetch_preflight_gate_present and not cameo_fetch_preflight_recorded:
        next_required_items.append("CAMEO official-result fetch preflight")
    if not cleanup_objective_ready:
        next_required_items.append("cleanup completion/postchecks")
    if not no_goal_blockers:
        next_required_items.append("product release evidence rollup")
    if not goal_api_surface_ready:
        next_required_items.append("goal API surface contract")
    if api_runner_profile_receipt_gate_present and not api_runner_profile_receipt_recorded:
        next_required_items.append("API runner profile promotion operator receipt")
    if product_scope_receipt_gate_present and not product_scope_receipt_recorded:
        next_required_items.append("product scope breadth evidence receipt")
    if engine_refinement_receipt_gate_present and not engine_refinement_receipt_recorded:
        next_required_items.append("engine refinement claim evidence receipt")
    if engine_refinement_priority_gate_present and not engine_refinement_priority_recorded:
        next_required_items.append("engine refinement claim evidence priority packet")
    if refine_tier_public_benchmark_gate_present and not refine_tier_public_benchmark_recorded:
        next_required_items.append("refine-tier public benchmark readiness fail-closed receipt")
    if (
        refine_tier_public_benchmark_work_order_apply_gate_present
        and not refine_tier_public_benchmark_work_order_apply_recorded
    ):
        next_required_items.append("refine-tier public benchmark work-order apply fail-closed receipt")
    if goal_bottleneck_briefing_gate_present and not goal_bottleneck_full_commercial_receipts_recorded:
        next_required_items.append("goal bottleneck full-commercial receipt briefing")
    if (
        goal_bottleneck_briefing_gate_present
        and not goal_bottleneck_production_ai_registry_promotion_priority_recorded
    ):
        next_required_items.append("goal bottleneck Production AI registry promotion priority briefing")
    if (
        production_ai_registry_priority_gate_present
        and not production_ai_registry_priority_recorded
    ):
        next_required_items.append("Production AI registry promotion priority packet")
    if (
        production_ai_checkpoint_readiness_gate_present
        and not production_ai_checkpoint_readiness_recorded
    ):
        next_required_items.append("Production AI checkpoint readiness")
    if (
        production_ai_promotion_workbench_gate_present
        and not production_ai_promotion_workbench_recorded
    ):
        next_required_items.append("Production AI promotion workbench")
    if release_source_of_truth_gate_present and not release_source_of_truth_ready:
        next_required_items.append("product release source-of-truth gate")
    if product_quality_gate_present and not product_quality_gate_verified:
        next_required_items.append("product quality gate verification receipt")
    if product_pose_sampling_gate_present and not product_pose_sampling_recorded:
        next_required_items.append("product pose sampling readiness receipt")
    if product_ledger_privacy_scan_gate_present and not product_ledger_privacy_scan_recorded:
        next_required_items.append("product ledger privacy scan receipt")
    if full_commercial_matrix_gate_present and not full_commercial_matrix_recorded:
        next_required_items.append("full-commercial blocker evidence matrix")
    if rollout_smoke_gate_present and not rollout_smoke_recorded:
        next_required_items.append("R4 rollout execution smoke receipt")
    if master_gap_rollup_gate_present and not master_gap_rollup_recorded:
        next_required_items.append("master gap closure rollup")
    if accuracy_parity_gate_present and not accuracy_parity_scorecard_recorded:
        next_required_items.append("accuracy parity scorecard")
    if science_claim_gap_gate_present and not science_claim_gap_recorded:
        next_required_items.append("science claim promotion gap closure")
    if api_customer_flow_gate_present and not api_customer_flow_ready:
        next_required_items.append("API customer-flow release evidence")
    if product_ai_architecture_gate_present and not product_ai_architecture_ready:
        next_required_items.append("product AI architecture gap closure")
    if self_hosted_license_audit_gate_present and not self_hosted_license_audit_recorded:
        next_required_items.append("self-hosted license distribution audit")
    if third_party_license_review_gate_present and not third_party_license_review_recorded:
        next_required_items.append("third-party license review gate")
    next_required_step = (
        "Release gate is clear; archive the evidence packet before customer-facing or public benchmark claims."
        if release_allowed
        else f"Clear {', '.join(next_required_items)} before release."
    )

    summary = {
        "packet_type": "goal_release_decision_gate",
        "status": "goal_release_ready" if release_allowed else "blocked_goal_release_decision",
        "release_allowed": release_allowed,
        "restricted_release_allowed": release_allowed,
        "full_commercial_release_allowed": full_commercial_release_allowed,
        "full_commercial_release_blocker_count": len(full_commercial_release_blocker_ids),
        "full_commercial_release_blocker_ids": full_commercial_release_blocker_ids,
        "primary_full_commercial_release_blocker_id": primary_full_commercial_release_blocker_id,
        "primary_full_commercial_release_blocker_requirement_id": (
            primary_full_commercial_release_blocker_requirement_id
        ),
        "primary_full_commercial_release_blocker_tier": _full_commercial_blocker_tier(
            primary_full_commercial_release_blocker_id
        ),
        "primary_full_commercial_release_blocker": _text(
            full_commercial_matrix.get("first_blocked_evidence_row_id")
        )
        or _text(master_gap_rollup.get("current_primary_open_gap_id")),
        "primary_full_commercial_release_blocker_blocked_row_count": (
            primary_full_commercial_release_blocker_blocked_row_count
        ),
        "primary_full_commercial_release_blocker_first_blocked_evidence_row_id": (
            primary_full_commercial_release_blocker_first_blocked_evidence_row_id
        ),
        "primary_full_commercial_release_blocker_receipt_csv": (
            primary_full_commercial_release_blocker_receipt_csv
        ),
        "primary_full_commercial_release_blocker_approval_token_required": (
            primary_full_commercial_release_blocker_approval_token_required
        ),
        "primary_full_commercial_release_blocker_next_required_step": (
            primary_full_commercial_release_blocker_next_required_step
        ),
        "full_commercial_release_next_required_step": (
            "Full-commercial release is clear."
            if full_commercial_release_allowed
            else (
                _text(full_commercial_matrix.get("next_required_step"))
                or _text(master_gap_rollup.get("current_next_action"))
                or "Close full-commercial release blockers before claiming full-commercial release."
            )
        ),
        "commercial_independent_product_ready": product_release_ready,
        "cameo_architecture_validation_ready": cameo_architecture_validation_ready,
        "cleanup_objective_ready": cleanup_objective_ready,
        "blocker_count": blocker_count,
        "check_count": len(rows),
        "source_product_pilot_status": _text(product.get("status")),
        "source_product_architecture_status": _text(product_architecture.get("status")),
        "product_architecture_local_surface_ready": product_local_architecture_surface_ready,
        "product_architecture_release_ready": product_architecture_ready,
        "product_architecture_public_benchmark_validation_ready": product_architecture_public_benchmark_ready,
        "product_architecture_public_benchmark_status": product_architecture_public_benchmark_status,
        "product_architecture_public_benchmark_required_suite_count": product_architecture_public_benchmark_required_suite_count,
        "product_architecture_public_benchmark_ready_required_suite_count": product_architecture_public_benchmark_ready_required_suite_count,
        "product_architecture_public_benchmark_blocked_suite_count": product_architecture_public_benchmark_blocked_suite_count,
        "product_architecture_public_benchmark_suite_materialization_manifest_count": product_architecture_public_benchmark_suite_materialization_manifest_count,
        "product_architecture_public_benchmark_suite_scorecard_row_csv_count": product_architecture_public_benchmark_suite_scorecard_row_csv_count,
        "product_architecture_public_benchmark_suite_threshold_count": product_architecture_public_benchmark_suite_threshold_count,
        "product_architecture_public_benchmark_suite_blocker_count": product_architecture_public_benchmark_suite_blocker_count,
        "product_architecture_public_benchmark_suite_run_command_count": product_architecture_public_benchmark_suite_run_command_count,
        "product_architecture_public_benchmark_suite_materialization_run_command_count": product_architecture_public_benchmark_suite_materialization_run_command_count,
        "product_architecture_public_benchmark_suite_no_external_dependency_count": product_architecture_public_benchmark_suite_no_external_dependency_count,
        "product_architecture_public_benchmark_requires_24h_server": bool(
            product_architecture.get("public_benchmark_requires_24h_server") is True
        ),
        "product_architecture_public_benchmark_requires_competition_season": bool(
            product_architecture.get("public_benchmark_requires_competition_season") is True
        ),
        "product_architecture_public_benchmark_requires_paid_vps": bool(
            product_architecture.get("public_benchmark_requires_paid_vps") is True
        ),
        "public_benchmark_required_for_product_release": public_benchmark_required_for_product_release,
        "release_blocked_by_public_benchmark": release_blocked_by_public_benchmark,
        "cameo_live_validation_channel": cameo_live_validation_channel,
        "cameo_live_validation_required_for_product_release": cameo_live_validation_required_for_product_release,
        "cameo_registration_required_for_product_release": cameo_registration_required_for_product_release,
        "cameo_official_results_required_for_product_release": cameo_official_results_required_for_product_release,
        "release_blocked_by_cameo_live_validation": release_blocked_by_cameo_live_validation,
        "product_architecture_cameo_official_validation_evidence_ready": product_architecture_cameo_official_evidence_ready,
        "product_architecture_cameo_receiver_smoke_status": product_architecture_cameo_receiver_smoke_status,
        "product_architecture_cameo_api_dependency_status": product_architecture_cameo_api_dependency_status,
        "product_architecture_cameo_public_registration_blocker_count": product_architecture_cameo_public_registration_blocker_count,
        "product_architecture_cameo_registration_approval_token_count": _int(
            product_architecture.get("cameo_registration_approval_token_count")
        ),
        "product_architecture_cameo_registration_approval_tokens_required": product_architecture_cameo_registration_tokens,
        "source_product_commercial_independence_status": _text(product_independence.get("status")),
        "product_commercial_independence_ready": product_commercial_independence_ready,
        "self_hosted_license_distribution_audit_gate_present": self_hosted_license_audit_gate_present,
        "self_hosted_license_distribution_audit_status": _text(
            self_hosted_license_audit.get("status")
        ),
        "self_hosted_license_distribution_audit_recorded": (
            self_hosted_license_audit_recorded if self_hosted_license_audit_gate_present else None
        ),
        "self_hosted_license_distribution_audit_product_license_path": _text(
            self_hosted_license_audit.get("product_license_path")
        ),
        "self_hosted_license_distribution_audit_approved_license_text_source": _text(
            self_hosted_license_audit.get("approved_license_text_source")
        ),
        "self_hosted_license_distribution_audit_product_license_hash_matches_approved_source": (
            self_hosted_license_audit_hashes_match
        ),
        "self_hosted_license_distribution_audit_spdx_license_id": _text(
            self_hosted_license_audit.get("spdx_license_id")
        ),
        "self_hosted_license_distribution_audit_copyright_holder": _text(
            self_hosted_license_audit.get("copyright_holder")
        ),
        "self_hosted_license_distribution_audit_hard_blocker_count": _int(
            self_hosted_license_audit.get("hard_blocker_count")
        ),
        "self_hosted_license_distribution_audit_operator_review_item_count": _int(
            self_hosted_license_audit.get("operator_review_item_count")
        ),
        "self_hosted_license_distribution_audit_legal_advice_provided": bool(
            self_hosted_license_audit.get("legal_advice_provided") is True
        ),
        "self_hosted_license_distribution_audit_third_party_license_review_gate_status": _text(
            self_hosted_license_audit.get("third_party_license_review_gate_status")
        ),
        "self_hosted_license_distribution_audit_third_party_license_review_gate_ready": bool(
            self_hosted_license_audit.get("third_party_license_review_gate_ready") is True
        ),
        "self_hosted_license_distribution_audit_third_party_license_review_gate_blocker_count": _int(
            self_hosted_license_audit.get("third_party_license_review_gate_blocker_count")
        ),
        "self_hosted_license_distribution_audit_third_party_dual_license_assets": (
            ";".join(self_hosted_license_audit_dual_license_assets)
        ),
        "self_hosted_license_distribution_audit_viewer_third_party_notice_path": _text(
            self_hosted_license_audit.get("viewer_third_party_notice_path")
        ),
        "self_hosted_license_distribution_audit_external_state_mutated": bool(
            self_hosted_license_audit.get("external_state_mutated") is True
        ),
        "third_party_license_review_gate_present": third_party_license_review_gate_present,
        "third_party_license_review_gate_status": _text(third_party_license_review.get("status")),
        "third_party_license_review_gate_ready": third_party_license_review_ready,
        "third_party_license_review_gate_recorded": (
            third_party_license_review_recorded if third_party_license_review_gate_present else None
        ),
        "third_party_license_review_gate_approved_assets": (
            ";".join(third_party_license_review_approved_assets)
        ),
        "third_party_license_review_gate_allowed_license_paths": (
            ";".join(third_party_license_review_allowed_license_paths)
        ),
        "third_party_license_review_gate_expected_review_asset_count": _int(
            third_party_license_review.get("expected_review_asset_count")
        ),
        "third_party_license_review_gate_review_row_count": _int(
            third_party_license_review.get("review_row_count")
        ),
        "third_party_license_review_gate_approved_review_asset_count": _int(
            third_party_license_review.get("approved_review_asset_count")
        ),
        "third_party_license_review_gate_missing_review_asset_count": _int(
            third_party_license_review.get("missing_review_asset_count")
        ),
        "third_party_license_review_gate_deferred_review_asset_count": _int(
            third_party_license_review.get("deferred_review_asset_count")
        ),
        "third_party_license_review_gate_blocker_count": _int(
            third_party_license_review.get("blocker_count")
        ),
        "third_party_license_review_gate_review_csv": _text(
            third_party_license_review.get("review_csv")
        ),
        "third_party_license_review_gate_review_csv_present": bool(
            third_party_license_review.get("review_csv_present") is True
        ),
        "third_party_license_review_gate_operator_template_csv": _text(
            third_party_license_review.get("operator_template_csv")
        ),
        "third_party_license_review_gate_approval_token_required": _text(
            third_party_license_review.get("approval_token_required")
        ),
        "third_party_license_review_gate_source_license_audit_status": _text(
            third_party_license_review.get("source_license_audit_status")
        ),
        "third_party_license_review_gate_source_hard_blocker_count": _int(
            third_party_license_review.get("source_hard_blocker_count")
        ),
        "third_party_license_review_gate_source_operator_review_item_count": _int(
            third_party_license_review.get("source_operator_review_item_count")
        ),
        "third_party_license_review_gate_legal_advice_provided": bool(
            third_party_license_review.get("legal_advice_provided") is True
        ),
        "third_party_license_review_gate_asset_modified": bool(
            third_party_license_review.get("asset_modified") is True
        ),
        "third_party_license_review_gate_external_state_mutated": bool(
            third_party_license_review.get("external_state_mutated") is True
        ),
        "source_cameo_validation_status": _text(cameo_validation.get("status")),
        "source_cameo_capability_status": _text(cameo_capability.get("status")),
        "source_cameo_public_registration_approval_gate_status": _text(cameo_registration_gate.get("status")),
        "cameo_public_registration_authorized_for_registration_review": bool(cameo_registration_gate.get("authorized_for_registration_review") is True),
        "cameo_official_result_fetch_preflight_gate_present": cameo_fetch_preflight_gate_present,
        "cameo_official_result_fetch_preflight_status": _text(
            cameo_fetch_preflight.get("status")
        ),
        "cameo_official_result_fetch_preflight_recorded": (
            cameo_fetch_preflight_recorded if cameo_fetch_preflight_gate_present else None
        ),
        "cameo_official_result_fetch_preflight_authorized": bool(
            cameo_fetch_preflight.get("authorized_for_separate_operator_fetch") is True
        ),
        "cameo_official_result_fetch_preflight_operator_fetch_csv": _text(
            cameo_fetch_preflight.get("operator_fetch_csv")
        ),
        "cameo_official_result_fetch_preflight_operator_fetch_csv_present": bool(
            cameo_fetch_preflight.get("operator_fetch_csv_present") is True
        ),
        "cameo_official_result_fetch_preflight_operator_template_csv": _text(
            cameo_fetch_preflight.get("operator_template_csv")
        ),
        "cameo_official_result_fetch_preflight_blocked_row_count": _int(
            cameo_fetch_preflight.get("blocked_row_count")
        ),
        "cameo_official_result_fetch_preflight_blocker_count": _int(
            cameo_fetch_preflight.get("blocker_count")
        ),
        "cameo_official_result_fetch_preflight_awaiting_operator_fetch_approval_row_count": _int(
            cameo_fetch_preflight.get("awaiting_operator_fetch_approval_row_count")
        ),
        "cameo_official_result_fetch_preflight_fetch_approval_token_required": _text(
            cameo_fetch_preflight.get("fetch_approval_token_required")
        ),
        "cameo_official_result_fetch_preflight_network_request_opened": bool(
            cameo_fetch_preflight.get("network_request_opened") is True
        ),
        "cameo_official_result_fetch_preflight_official_results_fetched": bool(
            cameo_fetch_preflight.get("official_results_fetched") is True
        ),
        "cameo_official_result_fetch_preflight_native_local_accuracy_used": bool(
            cameo_fetch_preflight.get("native_local_accuracy_used") is True
        ),
        "cameo_official_result_fetch_preflight_outbound_email_enabled": bool(
            cameo_fetch_preflight.get("outbound_email_enabled") is True
        ),
        "cameo_official_result_fetch_preflight_external_state_mutated": bool(
            cameo_fetch_preflight.get("external_state_mutated") is True
        ),
        "source_goal_rollup_status": _text(rollup.get("status")),
        "source_goal_api_surface_contract_status": _text(goal_api_surface.get("status")),
        "goal_api_surface_ready": goal_api_surface_ready,
        "api_runner_profile_promotion_operator_receipt_gate_present": api_runner_profile_receipt_gate_present,
        "api_runner_profile_promotion_operator_receipt_status": _text(
            api_runner_profile_receipt.get("status")
        ),
        "api_runner_profile_promotion_operator_receipt_recorded": (
            api_runner_profile_receipt_recorded
            if api_runner_profile_receipt_gate_present
            else None
        ),
        "api_runner_profile_promotion_operator_receipt_ready": bool(
            api_runner_profile_receipt.get("operator_receipt_ready") is True
        ),
        "api_runner_profile_promotion_operator_receipt_readiness_status": _text(
            api_runner_profile_receipt.get("readiness_status")
        ),
        "api_runner_profile_promotion_operator_receipt_profile_count": _int(
            api_runner_profile_receipt.get("profile_count")
        ),
        "api_runner_profile_promotion_operator_receipt_receipt_row_count": _int(
            api_runner_profile_receipt.get("receipt_row_count")
        ),
        "api_runner_profile_promotion_operator_receipt_pass_row_count": _int(
            api_runner_profile_receipt.get("pass_row_count")
        ),
        "api_runner_profile_promotion_operator_receipt_blocked_row_count": _int(
            api_runner_profile_receipt.get("blocked_row_count")
        ),
        "api_runner_profile_promotion_operator_receipt_blocker_count": _int(
            api_runner_profile_receipt.get("blocker_count")
        ),
        "api_runner_profile_promotion_operator_receipt_blockers": api_runner_profile_blockers,
        "api_runner_profile_promotion_operator_receipt_first_blocked_profile_id": _text(
            api_runner_profile_receipt.get("first_blocked_profile_id")
        ),
        "api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker": _text(
            api_runner_profile_receipt.get("first_blocked_row_blocker")
        ),
        "api_runner_profile_promotion_operator_receipt_first_blocked_row_blockers": (
            api_runner_profile_first_blocked_row_blockers
        ),
        "api_runner_profile_promotion_operator_receipt_most_common_row_blocker": _text(
            api_runner_profile_receipt.get("most_common_row_blocker")
        ),
        "api_runner_profile_promotion_operator_receipt_approval_token_required": _text(
            api_runner_profile_receipt.get("approval_token_required")
        ),
        "api_runner_profile_promotion_operator_receipt_operator_template_csv": _text(
            api_runner_profile_receipt.get("operator_template_csv")
        ),
        "api_runner_profile_promotion_operator_receipt_next_required_step": _text(
            api_runner_profile_receipt.get("next_required_step")
        ),
        "api_runner_profile_promotion_operator_receipt_profile_enabled_by_this_tool": bool(
            api_runner_profile_receipt.get("profile_enabled_by_this_tool") is True
        ),
        "api_runner_profile_promotion_operator_receipt_runner_executed": bool(
            api_runner_profile_receipt.get("runner_executed") is True
        ),
        "api_runner_profile_promotion_operator_receipt_external_state_mutated": bool(
            api_runner_profile_receipt.get("external_state_mutated") is True
        ),
        "product_scope_breadth_evidence_receipt_gate_present": product_scope_receipt_gate_present,
        "product_scope_breadth_evidence_receipt_status": _text(product_scope_receipt.get("status")),
        "product_scope_breadth_evidence_receipt_recorded": (
            product_scope_receipt_recorded if product_scope_receipt_gate_present else None
        ),
        "product_scope_breadth_evidence_receipt_ready": bool(
            product_scope_receipt.get("full_scope_evidence_receipt_ready") is True
        ),
        "product_scope_breadth_evidence_receipt_receipt_row_count": _int(
            product_scope_receipt.get("receipt_row_count")
        ),
        "product_scope_breadth_evidence_receipt_pass_row_count": _int(
            product_scope_receipt.get("pass_row_count")
        ),
        "product_scope_breadth_evidence_receipt_blocked_row_count": _int(
            product_scope_receipt.get("blocked_row_count")
        ),
        "product_scope_breadth_evidence_receipt_blocker_count": _int(
            product_scope_receipt.get("blocker_count")
        ),
        "product_scope_breadth_evidence_receipt_evidence_status_contract_present_count": _int(
            product_scope_receipt.get("evidence_status_contract_present_count")
        ),
        "product_scope_breadth_evidence_receipt_expected_true_fields_present_count": _int(
            product_scope_receipt.get("expected_true_fields_present_count")
        ),
        "product_scope_breadth_evidence_receipt_expected_quality_true_field_count": _int(
            product_scope_receipt.get("expected_quality_true_field_count")
        ),
        "product_scope_breadth_evidence_receipt_expected_int_min_field_count": _int(
            product_scope_receipt.get("expected_int_min_field_count")
        ),
        "product_scope_breadth_evidence_receipt_expected_false_field_count": _int(
            product_scope_receipt.get("expected_false_field_count")
        ),
        "product_scope_breadth_evidence_receipt_provenance_kind_accepted_count": _int(
            product_scope_receipt.get("provenance_kind_accepted_count")
        ),
        "product_scope_breadth_evidence_receipt_external_state_mutated_false_count": _int(
            product_scope_receipt.get("external_state_mutated_false_count")
        ),
        "product_scope_breadth_evidence_receipt_operator_attestation_accepted_count": _int(
            product_scope_receipt.get("operator_attestation_accepted_count")
        ),
        "product_scope_breadth_evidence_receipt_operator_review_surface_ready_count": _int(
            product_scope_receipt.get("operator_review_surface_ready_count")
        ),
        "product_scope_breadth_evidence_receipt_operator_review_surface_blocked_count": _int(
            product_scope_receipt.get("operator_review_surface_blocked_count")
        ),
        "product_scope_breadth_evidence_receipt_receipt_manual_field_pending_count": _int(
            product_scope_receipt.get("receipt_manual_field_pending_count")
        ),
        "product_scope_breadth_evidence_receipt_receipt_evidence_artifact_pending_count": _int(
            product_scope_receipt.get("receipt_evidence_artifact_pending_count")
        ),
        "product_scope_breadth_evidence_receipt_receipt_claim_ready_pending_count": _int(
            product_scope_receipt.get("receipt_claim_ready_pending_count")
        ),
        "product_scope_breadth_evidence_receipt_receipt_reviewer_pending_count": _int(
            product_scope_receipt.get("receipt_reviewer_pending_count")
        ),
        "product_scope_breadth_evidence_receipt_receipt_reviewed_at_utc_pending_count": _int(
            product_scope_receipt.get("receipt_reviewed_at_utc_pending_count")
        ),
        "product_scope_breadth_evidence_receipt_receipt_license_ok_pending_count": _int(
            product_scope_receipt.get("receipt_license_ok_pending_count")
        ),
        "product_scope_breadth_evidence_receipt_receipt_approval_token_pending_count": _int(
            product_scope_receipt.get("receipt_approval_token_pending_count")
        ),
        "product_scope_breadth_evidence_receipt_required_scope_blocker_count": _int(
            product_scope_receipt.get("required_scope_blocker_count")
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": _text(
            product_scope_receipt.get("first_blocked_scope_blocker_id")
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": _text(
            product_scope_receipt.get("first_blocked_evidence_artifact")
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": _text(
            product_scope_receipt.get("first_blocked_expected_evidence_status")
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": _text(
            product_scope_receipt.get("first_blocked_observed_evidence_status")
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_row_blockers": (
            product_scope_receipt_first_blocked_row_blockers
        ),
        "product_scope_breadth_evidence_receipt_most_common_row_blocker": _text(
            product_scope_receipt.get("most_common_row_blocker")
        ),
        "product_scope_breadth_evidence_receipt_approval_token_required": _text(
            product_scope_receipt.get("approval_token_required")
        ),
        "product_scope_breadth_evidence_receipt_csv": _text(
            product_scope_receipt.get("receipt_csv")
        ),
        "product_scope_breadth_evidence_receipt_external_state_mutated": bool(
            product_scope_receipt.get("external_state_mutated") is True
        ),
        "engine_refinement_claim_evidence_receipt_gate_present": engine_refinement_receipt_gate_present,
        "engine_refinement_claim_evidence_receipt_status": _text(
            engine_refinement_receipt.get("status")
        ),
        "engine_refinement_claim_evidence_receipt_recorded": (
            engine_refinement_receipt_recorded if engine_refinement_receipt_gate_present else None
        ),
        "engine_refinement_claim_evidence_receipt_ready": bool(
            engine_refinement_receipt.get("claim_promotion_evidence_receipt_ready") is True
        ),
        "engine_refinement_claim_evidence_receipt_receipt_row_count": _int(
            engine_refinement_receipt.get("receipt_row_count")
        ),
        "engine_refinement_claim_evidence_receipt_pass_row_count": _int(
            engine_refinement_receipt.get("pass_row_count")
        ),
        "engine_refinement_claim_evidence_receipt_blocked_row_count": _int(
            engine_refinement_receipt.get("blocked_row_count")
        ),
        "engine_refinement_claim_evidence_receipt_blocker_count": _int(
            engine_refinement_receipt.get("blocker_count")
        ),
        "engine_refinement_claim_evidence_receipt_required_blocker_count": _int(
            engine_refinement_receipt.get("required_blocker_count")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": _text(
            engine_refinement_receipt.get("first_blocked_blocker_id")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": _text(
            engine_refinement_receipt.get("first_blocked_evidence_artifact")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": _text(
            engine_refinement_receipt.get("first_blocked_expected_evidence_status")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": _text(
            engine_refinement_receipt.get("first_blocked_observed_evidence_status")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": (
            engine_refinement_receipt_first_blocked_row_blockers
        ),
        "engine_refinement_claim_evidence_receipt_most_common_row_blocker": _text(
            engine_refinement_receipt.get("most_common_row_blocker")
        ),
        "engine_refinement_claim_evidence_receipt_approval_token_required": _text(
            engine_refinement_receipt.get("approval_token_required")
        ),
        "engine_refinement_claim_evidence_receipt_csv": _text(
            engine_refinement_receipt.get("receipt_csv")
        ),
        "engine_refinement_claim_evidence_receipt_external_state_mutated": bool(
            engine_refinement_receipt.get("external_state_mutated") is True
        ),
        "engine_refinement_claim_evidence_priority_packet_gate_present": (
            engine_refinement_priority_gate_present
        ),
        "engine_refinement_claim_evidence_priority_packet_status": _text(
            engine_refinement_priority.get("status")
        ),
        "engine_refinement_claim_evidence_priority_packet_recorded": (
            engine_refinement_priority_recorded if engine_refinement_priority_gate_present else None
        ),
        "engine_refinement_claim_evidence_priority_packet_ready": bool(
            engine_refinement_priority.get("priority_packet_ready") is True
        ),
        "engine_refinement_claim_evidence_priority_packet_claim_evidence_receipt_status": _text(
            engine_refinement_priority.get("claim_evidence_receipt_status")
        ),
        "engine_refinement_claim_evidence_priority_packet_claim_evidence_receipt_ready": bool(
            engine_refinement_priority.get("claim_evidence_receipt_ready") is True
        ),
        "engine_refinement_claim_evidence_priority_packet_claim_promotion_allowed": bool(
            engine_refinement_priority.get("claim_promotion_allowed") is True
        ),
        "engine_refinement_claim_evidence_priority_packet_priority_item_count": _int(
            engine_refinement_priority.get("priority_item_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_operator_input_required_count": _int(
            engine_refinement_priority.get("operator_input_required_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_blocked_priority_item_count": _int(
            engine_refinement_priority.get("blocked_priority_item_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_required_blocker_count": _int(
            engine_refinement_priority.get("required_blocker_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_missing_required_blocker_count": _int(
            engine_refinement_priority.get("missing_required_blocker_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_blocker_count": _int(
            engine_refinement_priority.get("blocker_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_top_blocker_id": _text(
            engine_refinement_priority.get("top_blocker_id")
        ),
        "engine_refinement_claim_evidence_priority_packet_top_priority_bucket": _text(
            engine_refinement_priority.get("top_priority_bucket")
        ),
        "engine_refinement_claim_evidence_priority_packet_top_required_input": _text(
            engine_refinement_priority.get("top_required_input")
        ),
        "engine_refinement_claim_evidence_priority_packet_top_acceptance_artifact": _text(
            engine_refinement_priority.get("top_acceptance_artifact")
        ),
        "engine_refinement_claim_evidence_priority_packet_top_verification_command": _text(
            engine_refinement_priority.get("top_verification_command")
        ),
        "engine_refinement_claim_evidence_priority_packet_top_next_operator_step": _text(
            engine_refinement_priority.get("top_next_operator_step")
        ),
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_status": _text(
            engine_refinement_priority.get("public_benchmark_status")
        ),
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_gate_ready": bool(
            engine_refinement_priority.get("public_benchmark_gate_ready") is True
        ),
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_present": bool(
            engine_refinement_priority.get("public_benchmark_work_order_present") is True
        ),
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_row_count": _int(
            engine_refinement_priority.get("public_benchmark_work_order_row_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_status": _text(
            engine_refinement_priority.get("public_benchmark_work_order_apply_status")
        ),
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_ready": bool(
            engine_refinement_priority.get("public_benchmark_work_order_apply_ready") is True
        ),
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_blocked_row_count": _int(
            engine_refinement_priority.get("public_benchmark_work_order_apply_blocked_row_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_approval_token_required": _text(
            engine_refinement_priority.get("approval_token_required")
        ),
        "engine_refinement_claim_evidence_priority_packet_approval_token_count": _int(
            engine_refinement_priority.get("approval_token_count")
        ),
        "engine_refinement_claim_evidence_priority_packet_external_state_mutated": bool(
            engine_refinement_priority.get("external_state_mutated") is True
        ),
        "refine_tier_public_benchmark_gate_present": refine_tier_public_benchmark_gate_present,
        "refine_tier_public_benchmark_status": _text(
            refine_tier_public_benchmark.get("status")
        ),
        "refine_tier_public_benchmark_recorded": (
            refine_tier_public_benchmark_recorded
            if refine_tier_public_benchmark_gate_present
            else None
        ),
        "refine_tier_public_benchmark_input_csv": _text(
            refine_tier_public_benchmark.get("input_csv")
        ),
        "refine_tier_public_benchmark_input_csv_present": bool(
            refine_tier_public_benchmark.get("input_csv_present") is True
        ),
        "refine_tier_public_benchmark_claim_grade_public_benchmark_ready": bool(
            refine_tier_public_benchmark.get("claim_grade_public_benchmark_ready") is True
        ),
        "refine_tier_public_benchmark_benchmark_metric_surface_ready": bool(
            refine_tier_public_benchmark.get("benchmark_metric_surface_ready") is True
        ),
        "refine_tier_public_benchmark_row_count": _int(
            refine_tier_public_benchmark.get("row_count")
        ),
        "refine_tier_public_benchmark_valid_row_count": _int(
            refine_tier_public_benchmark.get("valid_row_count")
        ),
        "refine_tier_public_benchmark_pose_metric_row_count": _int(
            refine_tier_public_benchmark.get("pose_metric_row_count")
        ),
        "refine_tier_public_benchmark_pose_metric_pass_count": _int(
            refine_tier_public_benchmark.get("pose_metric_pass_count")
        ),
        "refine_tier_public_benchmark_free_energy_pair_count": _int(
            refine_tier_public_benchmark.get("free_energy_pair_count")
        ),
        "refine_tier_public_benchmark_blocker_count": _int(
            refine_tier_public_benchmark.get("blocker_count")
        ),
        "refine_tier_public_benchmark_min_total_rows_required": _int(
            refine_tier_public_benchmark.get("min_total_rows_required")
        ),
        "refine_tier_public_benchmark_min_pose_rows_required": _int(
            refine_tier_public_benchmark.get("min_pose_rows_required")
        ),
        "refine_tier_public_benchmark_min_free_energy_pairs_required": _int(
            refine_tier_public_benchmark.get("min_free_energy_pairs_required")
        ),
        "refine_tier_public_benchmark_operator_work_order_ready": bool(
            refine_tier_public_benchmark.get("operator_work_order_ready") is True
        ),
        "refine_tier_public_benchmark_work_order_csv": _text(
            refine_tier_public_benchmark.get("work_order_csv")
        ),
        "refine_tier_public_benchmark_work_order_row_count": _int(
            refine_tier_public_benchmark.get("work_order_row_count")
        ),
        "refine_tier_public_benchmark_write_intake_approval_token_required": _text(
            refine_tier_public_benchmark.get("write_intake_approval_token_required")
        ),
        "refine_tier_public_benchmark_external_state_mutated": bool(
            refine_tier_public_benchmark.get("external_state_mutated") is True
        ),
        "refine_tier_public_benchmark_next_required_step": _text(
            refine_tier_public_benchmark.get("next_required_step")
        ),
        "refine_tier_public_benchmark_work_order_apply_gate_present": (
            refine_tier_public_benchmark_work_order_apply_gate_present
        ),
        "refine_tier_public_benchmark_work_order_apply_status": _text(
            refine_tier_public_benchmark_work_order_apply.get("status")
        ),
        "refine_tier_public_benchmark_work_order_apply_recorded": (
            refine_tier_public_benchmark_work_order_apply_recorded
            if refine_tier_public_benchmark_work_order_apply_gate_present
            else None
        ),
        "refine_tier_public_benchmark_work_order_apply_aggregate_readiness_required": bool(
            refine_tier_public_benchmark_work_order_apply.get("aggregate_readiness_required")
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_apply_ready": bool(
            refine_tier_public_benchmark_work_order_apply.get("apply_ready") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_work_order_csv": _text(
            refine_tier_public_benchmark_work_order_apply.get("work_order_csv")
        ),
        "refine_tier_public_benchmark_work_order_apply_work_order_csv_present": bool(
            refine_tier_public_benchmark_work_order_apply.get("work_order_csv_present") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_work_order_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("work_order_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_blocked_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("blocked_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_valid_intake_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("valid_intake_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_blocker_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("blocker_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_duplicate_benchmark_id_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("duplicate_benchmark_id_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_required": bool(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_required"
            )
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_pass_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_pass_row_count"
            )
        ),
        "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_blocked_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_blocked_row_count"
            )
        ),
        "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_missing_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get(
                "receptor_coordinate_validation_missing_row_count"
            )
        ),
        "refine_tier_public_benchmark_work_order_apply_metric_evidence_required": bool(
            refine_tier_public_benchmark_work_order_apply.get("metric_evidence_required")
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_metric_evidence_pass_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("metric_evidence_pass_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_metric_evidence_blocked_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("metric_evidence_blocked_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_metric_evidence_missing_row_count": _int(
            refine_tier_public_benchmark_work_order_apply.get("metric_evidence_missing_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_candidate_intake_written": bool(
            refine_tier_public_benchmark_work_order_apply.get("candidate_intake_written") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_candidate_readiness_checked": bool(
            refine_tier_public_benchmark_work_order_apply.get("candidate_readiness_checked") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_candidate_claim_grade_public_benchmark_ready": bool(
            refine_tier_public_benchmark_work_order_apply.get(
                "candidate_claim_grade_public_benchmark_ready"
            )
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_intake_written": bool(
            refine_tier_public_benchmark_work_order_apply.get("intake_written") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_write_intake_requested": bool(
            refine_tier_public_benchmark_work_order_apply.get("write_intake_requested") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_approval_token_present": bool(
            refine_tier_public_benchmark_work_order_apply.get("approval_token_present") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_approval_token_accepted": bool(
            refine_tier_public_benchmark_work_order_apply.get("approval_token_accepted") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_target_intake_csv": _text(
            refine_tier_public_benchmark_work_order_apply.get("target_intake_csv")
        ),
        "refine_tier_public_benchmark_work_order_apply_external_state_mutated": bool(
            refine_tier_public_benchmark_work_order_apply.get("external_state_mutated") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_next_required_step": _text(
            refine_tier_public_benchmark_work_order_apply.get("next_required_step")
        ),
        "goal_bottleneck_briefing_gate_present": goal_bottleneck_briefing_gate_present,
        "source_goal_bottleneck_briefing_status": _text(goal_bottleneck_briefing.get("status")),
        "goal_bottleneck_briefing_full_commercial_receipts_recorded": (
            goal_bottleneck_full_commercial_receipts_recorded
            if goal_bottleneck_briefing_gate_present
            else None
        ),
        "goal_bottleneck_briefing_completion_audit_release_blocker_bottleneck_count": _int(
            goal_bottleneck_briefing.get("completion_audit_release_blocker_bottleneck_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_entry_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_operator_input_required_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_current_action_required_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_template_required_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_required_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_template_present_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count": _int(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_token_count")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses": _text(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_source_gate_statuses")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs": _text(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_required_inputs")
        ),
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens": _text(
            goal_bottleneck_briefing.get("full_commercial_evidence_receipt_approval_tokens")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded": (
            goal_bottleneck_production_ai_registry_promotion_priority_recorded
            if goal_bottleneck_briefing_gate_present
            else None
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_source_json": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_source_json")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_status": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_status")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_packet_ready": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_packet_ready") is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_registry_promotion_ready": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_registry_promotion_ready") is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_operator_input_required_count": _int(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_operator_input_required_count")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_blocked_priority_item_count": _int(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_blocked_priority_item_count")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count": _int(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_missing_gate_count")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_ids": (
            goal_bottleneck_production_ai_registry_promotion_priority_missing_gate_ids
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_gate_id")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_priority_bucket": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_priority_bucket")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_required_input": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_required_input")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_acceptance_artifact": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_acceptance_artifact")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_verification_command": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_verification_command")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_next_operator_step": _text(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_top_next_operator_step")
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_model_promoted": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_model_promoted") is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_customer_facing_mutation_enabled": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_customer_facing_mutation_enabled")
            is True
        ),
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_external_state_mutated": bool(
            goal_bottleneck_briefing.get("production_ai_registry_promotion_priority_external_state_mutated") is True
        ),
        "production_ai_registry_promotion_priority_packet_gate_present": (
            production_ai_registry_priority_gate_present
        ),
        "production_ai_registry_promotion_priority_packet_status": _text(
            production_ai_registry_priority.get("status")
        ),
        "production_ai_registry_promotion_priority_packet_recorded": (
            production_ai_registry_priority_recorded
            if production_ai_registry_priority_gate_present
            else None
        ),
        "production_ai_registry_promotion_priority_packet_ready": bool(
            production_ai_registry_priority.get("priority_packet_ready") is True
        ),
        "production_ai_registry_promotion_priority_registry_promotion_ready": bool(
            production_ai_registry_priority.get("registry_promotion_ready") is True
        ),
        "production_ai_registry_promotion_priority_required_gate_count": _int(
            production_ai_registry_priority.get("required_gate_count")
        ),
        "production_ai_registry_promotion_priority_priority_item_count": _int(
            production_ai_registry_priority.get("priority_item_count")
        ),
        "production_ai_registry_promotion_priority_operator_input_required_count": _int(
            production_ai_registry_priority.get("operator_input_required_count")
        ),
        "production_ai_registry_promotion_priority_blocked_priority_item_count": _int(
            production_ai_registry_priority.get("blocked_priority_item_count")
        ),
        "production_ai_registry_promotion_priority_missing_gate_count": _int(
            production_ai_registry_priority.get("registry_promotion_missing_gate_count")
        ),
        "production_ai_registry_promotion_priority_missing_gate_ids": (
            production_ai_registry_priority_missing_gate_ids
        ),
        "production_ai_registry_promotion_priority_top_gate_id": _text(
            production_ai_registry_priority.get("top_gate_id")
        ),
        "production_ai_registry_promotion_priority_top_priority_bucket": _text(
            production_ai_registry_priority.get("top_priority_bucket")
        ),
        "production_ai_registry_promotion_priority_top_acceptance_artifact": _text(
            production_ai_registry_priority.get("top_acceptance_artifact")
        ),
        "production_ai_registry_promotion_priority_top_required_input": _text(
            production_ai_registry_priority.get("top_required_input")
        ),
        "production_ai_registry_promotion_priority_top_verification_command": _text(
            production_ai_registry_priority.get("top_verification_command")
        ),
        "production_ai_registry_promotion_priority_top_next_operator_step": _text(
            production_ai_registry_priority.get("top_next_operator_step")
        ),
        "production_ai_registry_promotion_priority_approval_token_required": _text(
            production_ai_registry_priority.get("approval_token_required")
        ),
        "production_ai_registry_promotion_priority_approval_token_count": _int(
            production_ai_registry_priority.get("approval_token_count")
        ),
        "production_ai_registry_promotion_priority_operator_receipt_artifact": _text(
            production_ai_registry_priority.get("operator_receipt_artifact")
        ),
        "production_ai_registry_promotion_priority_operator_receipt_artifact_present": bool(
            production_ai_registry_priority.get("operator_receipt_artifact_present") is True
        ),
        "production_ai_registry_promotion_priority_operator_receipt_csv": _text(
            production_ai_registry_priority.get("operator_receipt_csv")
        ),
        "production_ai_registry_promotion_priority_operator_receipt_csv_present": bool(
            production_ai_registry_priority.get("operator_receipt_csv_present") is True
        ),
        "production_ai_registry_promotion_priority_operator_receipt_status": _text(
            production_ai_registry_priority.get("operator_receipt_status")
        ),
        "production_ai_registry_promotion_priority_operator_receipt_ready": bool(
            production_ai_registry_priority.get("operator_receipt_ready") is True
        ),
        "production_ai_registry_promotion_priority_residual_registry_artifact": _text(
            production_ai_registry_priority.get("residual_registry_artifact")
        ),
        "production_ai_registry_promotion_priority_residual_registry_artifact_present": bool(
            production_ai_registry_priority.get("residual_registry_artifact_present") is True
        ),
        "production_ai_registry_promotion_priority_checkpoint_readiness_artifact": _text(
            production_ai_registry_priority.get("checkpoint_readiness_artifact")
        ),
        "production_ai_registry_promotion_priority_checkpoint_readiness_artifact_present": bool(
            production_ai_registry_priority.get("checkpoint_readiness_artifact_present") is True
        ),
        "production_ai_registry_promotion_priority_promotion_workbench_artifact": _text(
            production_ai_registry_priority.get("promotion_workbench_artifact")
        ),
        "production_ai_registry_promotion_priority_promotion_workbench_artifact_present": bool(
            production_ai_registry_priority.get("promotion_workbench_artifact_present") is True
        ),
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": _int(
            production_ai_registry_priority.get("observed_registry_trained_model_checkpoint_count")
        ),
        "production_ai_registry_promotion_priority_observed_registry_default_residual_mode": _text(
            production_ai_registry_priority.get("observed_registry_default_residual_mode")
        ),
        "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed": bool(
            production_ai_registry_priority.get("observed_registry_production_promotion_allowed") is True
        ),
        "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready": bool(
            production_ai_registry_priority.get("observed_registry_customer_facing_mutation_flags_ready") is True
        ),
        "production_ai_registry_promotion_priority_observed_checkpoint_registry_promotion_currently_satisfied": bool(
            production_ai_registry_priority.get("observed_checkpoint_registry_promotion_currently_satisfied")
            is True
        ),
        "production_ai_registry_promotion_priority_observed_checkpoint_registry_promotion_missing_gate_ids": (
            production_ai_registry_priority_observed_checkpoint_missing_gate_ids
        ),
        "production_ai_registry_promotion_priority_model_promoted": bool(
            production_ai_registry_priority.get("model_promoted") is True
        ),
        "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": bool(
            production_ai_registry_priority.get("customer_facing_mutation_enabled") is True
        ),
        "production_ai_registry_promotion_priority_registry_edited_by_this_tool": bool(
            production_ai_registry_priority.get("registry_edited_by_this_tool") is True
        ),
        "production_ai_registry_promotion_priority_checkpoint_created_by_this_tool": bool(
            production_ai_registry_priority.get("checkpoint_created_by_this_tool") is True
        ),
        "production_ai_registry_promotion_priority_execution_enabled": bool(
            production_ai_registry_priority.get("execution_enabled") is True
        ),
        "production_ai_registry_promotion_priority_external_state_mutated": bool(
            production_ai_registry_priority.get("external_state_mutated") is True
        ),
        "production_ai_checkpoint_readiness_gate_present": (
            production_ai_checkpoint_readiness_gate_present
        ),
        "production_ai_checkpoint_readiness_status": _text(
            production_ai_checkpoint_readiness.get("status")
        ),
        "production_ai_checkpoint_readiness_recorded": (
            production_ai_checkpoint_readiness_recorded
            if production_ai_checkpoint_readiness_gate_present
            else None
        ),
        "production_ai_checkpoint_readiness_product_model_layer_ready": bool(
            production_ai_checkpoint_readiness.get("product_model_layer_ready") is True
        ),
        "production_ai_checkpoint_readiness_production_gpu_execution_environment_ready": bool(
            production_ai_checkpoint_readiness.get("production_gpu_execution_environment_ready") is True
        ),
        "production_ai_checkpoint_readiness_delta_force_derivation_validation_ready": bool(
            production_ai_checkpoint_readiness.get("delta_force_derivation_validation_ready") is True
        ),
        "production_ai_checkpoint_readiness_selected_sidecar_ready": bool(
            production_ai_checkpoint_readiness.get("selected_sidecar_ready") is True
        ),
        "production_ai_checkpoint_readiness_checkpoint_preflight_ready": bool(
            production_ai_checkpoint_readiness.get("checkpoint_preflight_ready") is True
        ),
        "production_ai_checkpoint_readiness_production_training_data_ready": bool(
            production_ai_checkpoint_readiness.get("production_training_data_ready") is True
        ),
        "production_ai_checkpoint_readiness_production_output_heads_complete": bool(
            production_ai_checkpoint_readiness.get("production_output_heads_complete") is True
        ),
        "production_ai_checkpoint_readiness_production_inference_acceptance_matrix_ready": bool(
            production_ai_checkpoint_readiness.get("production_inference_acceptance_matrix_ready") is True
        ),
        "production_ai_checkpoint_readiness_check_count": _int(
            production_ai_checkpoint_readiness.get("check_count")
        ),
        "production_ai_checkpoint_readiness_pass_check_count": _int(
            production_ai_checkpoint_readiness.get("pass_check_count")
        ),
        "production_ai_checkpoint_readiness_fail_check_count": _int(
            production_ai_checkpoint_readiness.get("fail_check_count")
        ),
        "production_ai_checkpoint_readiness_production_inference_acceptance_stage_count": _int(
            production_ai_checkpoint_readiness.get("production_inference_acceptance_stage_count")
        ),
        "production_ai_checkpoint_readiness_production_inference_acceptance_ready_stage_count": _int(
            production_ai_checkpoint_readiness.get("production_inference_acceptance_ready_stage_count")
        ),
        "production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_count": _int(
            production_ai_checkpoint_readiness.get("production_inference_acceptance_blocked_stage_count")
        ),
        "production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_ids": (
            ";".join(production_ai_checkpoint_acceptance_blocked_stage_ids)
        ),
        "production_ai_checkpoint_readiness_first_failed_check_id": _text(
            production_ai_checkpoint_readiness.get("first_failed_check_id")
        ),
        "production_ai_checkpoint_readiness_first_failed_source_artifact": _text(
            production_ai_checkpoint_readiness.get("first_failed_source_artifact")
        ),
        "production_ai_checkpoint_readiness_actionable_blocker_stage_id": _text(
            production_ai_checkpoint_readiness.get("production_inference_actionable_blocker_stage_id")
        ),
        "production_ai_checkpoint_readiness_actionable_blocker_check_id": _text(
            production_ai_checkpoint_readiness.get("production_inference_actionable_blocker_check_id")
        ),
        "production_ai_checkpoint_readiness_actionable_blocker_artifact": _text(
            production_ai_checkpoint_readiness.get("production_inference_actionable_blocker_artifact")
        ),
        "production_ai_checkpoint_readiness_registry_promotion_upstream_acceptance_ready": bool(
            production_ai_checkpoint_readiness.get("registry_promotion_upstream_acceptance_ready") is True
        ),
        "production_ai_checkpoint_readiness_registry_promotion_currently_satisfied": bool(
            production_ai_checkpoint_readiness.get("registry_promotion_currently_satisfied") is True
        ),
        "production_ai_checkpoint_readiness_registry_promotion_missing_gate_count": _int(
            production_ai_checkpoint_readiness.get("registry_promotion_missing_gate_count")
        ),
        "production_ai_checkpoint_readiness_registry_promotion_missing_gate_ids": (
            ";".join(production_ai_checkpoint_readiness_missing_gate_ids)
        ),
        "production_ai_checkpoint_readiness_candidate_checkpoint_count": _int(
            production_ai_checkpoint_readiness.get("candidate_checkpoint_count")
        ),
        "production_ai_checkpoint_readiness_ready_checkpoint_count": _int(
            production_ai_checkpoint_readiness.get("ready_checkpoint_count")
        ),
        "production_ai_checkpoint_readiness_trained_model_checkpoint_count": _int(
            production_ai_checkpoint_readiness.get("trained_model_checkpoint_count")
        ),
        "production_ai_checkpoint_readiness_default_residual_mode": _text(
            production_ai_checkpoint_readiness.get("default_residual_mode")
        ),
        "production_ai_checkpoint_readiness_production_ai_checkpoint_ready": bool(
            production_ai_checkpoint_readiness.get("production_ai_checkpoint_ready") is True
        ),
        "production_ai_checkpoint_readiness_production_ai_inference_subject_active": bool(
            production_ai_checkpoint_readiness.get("production_ai_inference_subject_active") is True
        ),
        "production_ai_checkpoint_readiness_production_promotion_allowed": bool(
            production_ai_checkpoint_readiness.get("production_promotion_allowed") is True
        ),
        "production_ai_checkpoint_readiness_customer_facing_auto_correction_allowed": bool(
            production_ai_checkpoint_readiness.get("customer_facing_auto_correction_allowed") is True
        ),
        "production_ai_checkpoint_readiness_customer_facing_score_mutation_allowed": bool(
            production_ai_checkpoint_readiness.get("customer_facing_score_mutation_allowed") is True
        ),
        "production_ai_checkpoint_readiness_customer_facing_ranking_mutation_allowed": bool(
            production_ai_checkpoint_readiness.get("customer_facing_ranking_mutation_allowed") is True
        ),
        "production_ai_checkpoint_readiness_model_promoted": bool(
            production_ai_checkpoint_readiness.get("model_promoted") is True
        ),
        "production_ai_checkpoint_readiness_docking_results_emitted": bool(
            production_ai_checkpoint_readiness.get("docking_results_emitted") is True
        ),
        "production_ai_checkpoint_readiness_execution_enabled": bool(
            production_ai_checkpoint_readiness.get("execution_enabled") is True
        ),
        "production_ai_checkpoint_readiness_external_state_mutated": bool(
            production_ai_checkpoint_readiness.get("external_state_mutated") is True
        ),
        "production_ai_promotion_workbench_gate_present": production_ai_promotion_workbench_gate_present,
        "production_ai_promotion_workbench_status": _text(
            production_ai_promotion_workbench.get("status")
        ),
        "production_ai_promotion_workbench_recorded": (
            production_ai_promotion_workbench_recorded
            if production_ai_promotion_workbench_gate_present
            else None
        ),
        "production_ai_promotion_workbench_ready": bool(
            production_ai_promotion_workbench.get("promotion_workbench_ready") is True
        ),
        "production_ai_promotion_workbench_checkpoint_readiness_artifact_path": _text(
            production_ai_promotion_workbench.get("checkpoint_readiness_artifact_path")
        ),
        "production_ai_promotion_workbench_post_return_ladder_stage_count": _int(
            production_ai_promotion_workbench.get("post_return_promotion_ladder_stage_count")
        ),
        "production_ai_promotion_workbench_post_return_ladder_ready_stage_count": _int(
            production_ai_promotion_workbench.get("post_return_promotion_ladder_ready_stage_count")
        ),
        "production_ai_promotion_workbench_post_return_ladder_blocked_stage_count": _int(
            production_ai_promotion_workbench.get("post_return_promotion_ladder_blocked_stage_count")
        ),
        "production_ai_promotion_workbench_blocked_stage_ids": (
            ";".join(production_ai_promotion_workbench_blocked_stage_ids)
        ),
        "production_ai_promotion_workbench_first_blocked_stage_id": _text(
            production_ai_promotion_workbench.get("first_blocked_stage_id")
        ),
        "production_ai_promotion_workbench_first_blocked_stage_artifact": _text(
            production_ai_promotion_workbench.get("first_blocked_stage_artifact")
        ),
        "production_ai_promotion_workbench_first_blocked_stage_ready_key": _text(
            production_ai_promotion_workbench.get("first_blocked_stage_ready_key")
        ),
        "production_ai_promotion_workbench_registry_promotion_upstream_acceptance_ready": bool(
            production_ai_promotion_workbench.get("registry_promotion_upstream_acceptance_ready") is True
        ),
        "production_ai_promotion_workbench_registry_promotion_currently_satisfied": bool(
            production_ai_promotion_workbench.get("registry_promotion_currently_satisfied") is True
        ),
        "production_ai_promotion_workbench_registry_promotion_missing_gate_count": _int(
            production_ai_promotion_workbench.get("registry_promotion_missing_gate_count")
        ),
        "production_ai_promotion_workbench_registry_promotion_missing_gate_ids": (
            ";".join(production_ai_promotion_workbench_missing_gate_ids)
        ),
        "production_ai_promotion_workbench_candidate_checkpoint_count": _int(
            production_ai_promotion_workbench.get("candidate_checkpoint_count")
        ),
        "production_ai_promotion_workbench_ready_checkpoint_count": _int(
            production_ai_promotion_workbench.get("ready_checkpoint_count")
        ),
        "production_ai_promotion_workbench_trained_model_checkpoint_count": _int(
            production_ai_promotion_workbench.get("trained_model_checkpoint_count")
        ),
        "production_ai_promotion_workbench_default_residual_mode": _text(
            production_ai_promotion_workbench.get("default_residual_mode")
        ),
        "production_ai_promotion_workbench_production_ai_promotion_ready": bool(
            production_ai_promotion_workbench.get("production_ai_promotion_ready") is True
        ),
        "production_ai_promotion_workbench_production_ai_checkpoint_ready": bool(
            production_ai_promotion_workbench.get("production_ai_checkpoint_ready") is True
        ),
        "production_ai_promotion_workbench_production_ai_inference_subject_active": bool(
            production_ai_promotion_workbench.get("production_ai_inference_subject_active") is True
        ),
        "production_ai_promotion_workbench_production_promotion_allowed": bool(
            production_ai_promotion_workbench.get("production_promotion_allowed") is True
        ),
        "production_ai_promotion_workbench_model_promoted": bool(
            production_ai_promotion_workbench.get("model_promoted") is True
        ),
        "production_ai_promotion_workbench_docking_results_emitted": bool(
            production_ai_promotion_workbench.get("docking_results_emitted") is True
        ),
        "production_ai_promotion_workbench_execution_enabled": bool(
            production_ai_promotion_workbench.get("execution_enabled") is True
        ),
        "production_ai_promotion_workbench_external_state_mutated": bool(
            production_ai_promotion_workbench.get("external_state_mutated") is True
        ),
        "product_release_source_of_truth_gate_present": release_source_of_truth_gate_present,
        "product_release_source_of_truth_status": _text(release_source_of_truth.get("status")),
        "product_release_source_of_truth_ready": release_source_of_truth_ready if release_source_of_truth_gate_present else None,
        "product_release_source_of_truth_blocker_count": _int(release_source_of_truth.get("blocker_count")),
        "product_release_source_of_truth_stale_artifact_count": _int(
            release_source_of_truth.get("stale_artifact_count")
        ),
        "product_release_source_of_truth_readme_drift_count": _int(
            release_source_of_truth.get("readme_drift_count")
        ),
        "product_quality_gate_verification_gate_present": product_quality_gate_present,
        "product_quality_gate_verification_status": _text(product_quality_gate.get("status")),
        "product_quality_gate_verification_recorded": (
            product_quality_gate_verified if product_quality_gate_present else None
        ),
        "product_quality_gate_verification_ready": bool(
            product_quality_gate.get("quality_gate_ready") is True
        ),
        "product_quality_gate_verification_source_contract_status": _text(
            product_quality_gate.get("source_contract_status")
        ),
        "product_quality_gate_verification_check_count": _int(
            product_quality_gate.get("check_count")
        ),
        "product_quality_gate_verification_pass_count": _int(
            product_quality_gate.get("pass_count")
        ),
        "product_quality_gate_verification_source_contract_check_count": _int(
            product_quality_gate.get("source_contract_check_count")
        ),
        "product_quality_gate_verification_source_contract_pass_count": _int(
            product_quality_gate.get("source_contract_pass_count")
        ),
        "product_quality_gate_verification_blocker_count": _int(
            product_quality_gate.get("blocker_count")
        ),
        "product_quality_gate_verification_execution_enabled": bool(
            product_quality_gate.get("execution_enabled") is True
        ),
        "product_quality_gate_verification_external_state_mutated": bool(
            product_quality_gate.get("external_state_mutated") is True
        ),
        "product_pose_sampling_readiness_gate_present": product_pose_sampling_gate_present,
        "product_pose_sampling_readiness_status": _text(product_pose_sampling.get("status")),
        "product_pose_sampling_readiness_recorded": (
            product_pose_sampling_recorded if product_pose_sampling_gate_present else None
        ),
        "product_pose_sampling_readiness_ready": bool(
            product_pose_sampling.get("pose_sampling_readiness_ready") is True
        ),
        "product_pose_sampling_readiness_pose_generation_contract_ready": bool(
            product_pose_sampling.get("pose_generation_contract_ready") is True
        ),
        "product_pose_sampling_readiness_pocket_detection_ready": bool(
            product_pose_sampling.get("pocket_detection_ready") is True
        ),
        "product_pose_sampling_readiness_multi_start_pose_ensemble_ready": bool(
            product_pose_sampling.get("multi_start_pose_ensemble_ready") is True
        ),
        "product_pose_sampling_readiness_pose_centroid_pocket_bound_ready": bool(
            product_pose_sampling.get("pose_centroid_pocket_bound_ready") is True
        ),
        "product_pose_sampling_readiness_pose_rmsd_diversity_surface_ready": bool(
            product_pose_sampling.get("pose_rmsd_diversity_surface_ready") is True
        ),
        "product_pose_sampling_readiness_bounded_cross_docking_induced_fit_guard_ready": bool(
            product_pose_sampling.get("bounded_cross_docking_induced_fit_guard_ready") is True
        ),
        "product_pose_sampling_readiness_pose_claim_boundary_guard_ready": bool(
            product_pose_sampling.get("pose_claim_boundary_guard_ready") is True
        ),
        "product_pose_sampling_readiness_check_count": _int(
            product_pose_sampling.get("check_count")
        ),
        "product_pose_sampling_readiness_pass_count": _int(
            product_pose_sampling.get("pass_count")
        ),
        "product_pose_sampling_readiness_blocker_count": _int(
            product_pose_sampling.get("blocker_count")
        ),
        "product_pose_sampling_readiness_requested_pose_start_count": _int(
            product_pose_sampling.get("requested_pose_start_count")
        ),
        "product_pose_sampling_readiness_pose_count": _int(
            product_pose_sampling.get("pose_count")
        ),
        "product_pose_sampling_readiness_cluster_count": _int(
            product_pose_sampling.get("cluster_count")
        ),
        "product_pose_sampling_readiness_cross_docking_pose_count": _int(
            product_pose_sampling.get("cross_docking_pose_count")
        ),
        "product_pose_sampling_readiness_pocket_method": _text(
            product_pose_sampling.get("pocket_method")
        ),
        "product_pose_sampling_readiness_claim_grade_pose_accuracy_ready": bool(
            product_pose_sampling.get("claim_grade_pose_accuracy_ready") is True
        ),
        "product_pose_sampling_readiness_claim_grade_induced_fit_ready": bool(
            product_pose_sampling.get("claim_grade_induced_fit_ready") is True
        ),
        "product_pose_sampling_readiness_claim_grade_cross_docking_ready": bool(
            product_pose_sampling.get("claim_grade_cross_docking_ready") is True
        ),
        "product_pose_sampling_readiness_docking_results_emitted": bool(
            product_pose_sampling.get("docking_results_emitted") is True
        ),
        "product_pose_sampling_readiness_execution_enabled": bool(
            product_pose_sampling.get("execution_enabled") is True
        ),
        "product_pose_sampling_readiness_external_state_mutated": bool(
            product_pose_sampling.get("external_state_mutated") is True
        ),
        "product_pose_sampling_readiness_next_required_step": _text(
            product_pose_sampling.get("next_required_step")
        ),
        "product_ledger_privacy_scan_gate_present": product_ledger_privacy_scan_gate_present,
        "product_ledger_privacy_scan_status": _text(product_ledger_privacy_scan.get("status")),
        "product_ledger_privacy_scan_recorded": (
            product_ledger_privacy_scan_recorded
            if product_ledger_privacy_scan_gate_present
            else None
        ),
        "product_ledger_privacy_scan_ready": bool(
            product_ledger_privacy_scan.get("ledger_privacy_scan_ready") is True
        ),
        "product_ledger_privacy_scan_scan_file_count": product_ledger_privacy_scan_scan_file_count,
        "product_ledger_privacy_scan_scan_glob_count": product_ledger_privacy_scan_glob_count,
        "product_ledger_privacy_scan_pass_count": product_ledger_privacy_scan_pass_count,
        "product_ledger_privacy_scan_blocker_count": _int(
            product_ledger_privacy_scan.get("blocker_count")
        ),
        "product_ledger_privacy_scan_leak_count": _int(
            product_ledger_privacy_scan.get("leak_count")
        ),
        "product_ledger_privacy_scan_invalid_json_count": _int(
            product_ledger_privacy_scan.get("invalid_json_count")
        ),
        "product_ledger_privacy_scan_blocked_artifact_path_count": len(
            _text_list(product_ledger_privacy_scan.get("blocked_artifact_paths"))
        ),
        "product_ledger_privacy_scan_invalid_json_path_count": len(
            _text_list(product_ledger_privacy_scan.get("invalid_json_paths"))
        ),
        "product_ledger_privacy_scan_execution_enabled": bool(
            product_ledger_privacy_scan.get("execution_enabled") is True
        ),
        "product_ledger_privacy_scan_external_state_mutated": bool(
            product_ledger_privacy_scan.get("external_state_mutated") is True
        ),
        "product_ledger_privacy_scan_next_required_step": _text(
            product_ledger_privacy_scan.get("next_required_step")
        ),
        "product_full_commercial_blocker_evidence_matrix_gate_present": full_commercial_matrix_gate_present,
        "product_full_commercial_blocker_evidence_matrix_status": _text(
            full_commercial_matrix.get("status")
        ),
        "product_full_commercial_blocker_evidence_matrix_ready": (
            bool(full_commercial_matrix.get("full_commercial_blocker_evidence_matrix_ready") is True)
            if full_commercial_matrix_gate_present
            else None
        ),
        "product_full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready": bool(
            full_commercial_matrix.get("release_blocker_visibility_ready") is True
        ),
        "product_full_commercial_blocker_evidence_matrix_row_count": _int(
            full_commercial_matrix.get("matrix_row_count")
        ),
        "product_full_commercial_blocker_evidence_matrix_blocked_row_count": _int(
            full_commercial_matrix.get("blocked_matrix_row_count")
        ),
        "product_full_commercial_blocker_evidence_matrix_approval_token_count": _int(
            full_commercial_matrix.get("approval_token_count")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id": _text(
            full_commercial_matrix.get("first_blocked_release_blocker_id")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id": _text(
            full_commercial_matrix.get("first_blocked_evidence_row_id")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact": _text(
            full_commercial_matrix.get("first_blocked_evidence_artifact")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status": _text(
            full_commercial_matrix.get("first_blocked_expected_evidence_status")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status": _text(
            full_commercial_matrix.get("first_blocked_observed_evidence_status")
        ),
        "product_full_commercial_blocker_evidence_matrix_first_blocked_row_blockers": _text(
            full_commercial_matrix.get("first_blocked_row_blockers")
        ),
        "product_full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker": _text(
            full_commercial_matrix.get("scope_receipt_most_common_row_blocker")
        ),
        "product_full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker": _text(
            full_commercial_matrix.get("engine_receipt_most_common_row_blocker")
        ),
        "product_full_commercial_blocker_evidence_matrix_r8_blocked_row_count": _int(
            _dict_get(
                full_commercial_matrix.get("release_blocker_blocked_row_counts"),
                "R8_full_scope_claim_closure",
            )
        ),
        "product_full_commercial_blocker_evidence_matrix_r8_first_blocked_evidence_row_id": _text(
            _dict_get(
                full_commercial_matrix.get("release_blocker_first_blocked_evidence_row_ids"),
                "R8_full_scope_claim_closure",
            )
        ),
        "product_full_commercial_blocker_evidence_matrix_r8_receipt_csv": _text(
            _dict_get(
                full_commercial_matrix.get("release_blocker_receipt_csvs"),
                "R8_full_scope_claim_closure",
            )
        ),
        "product_full_commercial_blocker_evidence_matrix_r8_approval_token_required": _text(
            _dict_get(
                full_commercial_matrix.get("release_blocker_approval_tokens_required"),
                "R8_full_scope_claim_closure",
            )
        ),
        "product_full_commercial_blocker_evidence_matrix_r9_blocked_row_count": _int(
            _dict_get(
                full_commercial_matrix.get("release_blocker_blocked_row_counts"),
                "R9_engine_refinement_claim_promotion",
            )
        ),
        "product_full_commercial_blocker_evidence_matrix_r9_first_blocked_evidence_row_id": _text(
            _dict_get(
                full_commercial_matrix.get("release_blocker_first_blocked_evidence_row_ids"),
                "R9_engine_refinement_claim_promotion",
            )
        ),
        "product_full_commercial_blocker_evidence_matrix_r9_receipt_csv": _text(
            _dict_get(
                full_commercial_matrix.get("release_blocker_receipt_csvs"),
                "R9_engine_refinement_claim_promotion",
            )
        ),
        "product_full_commercial_blocker_evidence_matrix_r9_approval_token_required": _text(
            _dict_get(
                full_commercial_matrix.get("release_blocker_approval_tokens_required"),
                "R9_engine_refinement_claim_promotion",
            )
        ),
        "product_rollout_execution_smoke_receipt_gate_present": rollout_smoke_gate_present,
        "product_rollout_execution_smoke_receipt_status": _text(rollout_smoke.get("status")),
        "product_rollout_execution_smoke_receipt_ready": (
            bool(rollout_smoke.get("rollout_execution_smoke_receipt_ready") is True)
            if rollout_smoke_gate_present
            else None
        ),
        "product_rollout_execution_smoke_receipt_csv_present": bool(
            rollout_smoke.get("receipt_csv_present") is True
        ),
        "product_rollout_execution_smoke_receipt_row_count": _int(
            rollout_smoke.get("receipt_row_count")
        ),
        "product_rollout_execution_smoke_receipt_blocker_count": _int(
            rollout_smoke.get("blocker_count")
        ),
        "product_rollout_execution_smoke_receipt_rollout_executed": bool(
            rollout_smoke.get("rollout_executed") is True
        ),
        "product_rollout_execution_smoke_receipt_external_state_mutated": bool(
            rollout_smoke.get("external_state_mutated") is True
        ),
        "product_rollout_execution_smoke_receipt_pager_provider_contacted": bool(
            rollout_smoke.get("pager_provider_contacted") is True
        ),
        "product_rollout_execution_smoke_receipt_ingress_certificate_verified_live": bool(
            rollout_smoke.get("ingress_certificate_verified_live") is True
        ),
        "master_gap_closure_rollup_gate_present": master_gap_rollup_gate_present,
        "master_gap_closure_rollup_status": _text(master_gap_rollup.get("status")),
        "master_gap_closure_rollup_recorded": (
            master_gap_rollup_recorded if master_gap_rollup_gate_present else None
        ),
        "master_gap_closure_rollup_all_gaps_closed": (
            bool(master_gap_rollup.get("all_gaps_closed") is True)
            if master_gap_rollup_gate_present
            else None
        ),
        "master_gap_closure_rollup_claim_promotion_allowed": bool(
            master_gap_rollup.get("claim_promotion_allowed") is True
        ),
        "master_gap_closure_rollup_open_gap_count": _int(master_gap_rollup.get("open_gap_count")),
        "master_gap_closure_rollup_open_gap_ids": master_gap_open_ids,
        "master_gap_closure_rollup_open_gap_ids_joined": ";".join(master_gap_open_ids),
        "master_gap_closure_rollup_closed_gap_count": _int(
            master_gap_rollup.get("closed_gap_count")
        ),
        "master_gap_closure_rollup_closed_gap_ids": master_gap_closed_ids,
        "master_gap_closure_rollup_closed_gap_ids_joined": ";".join(master_gap_closed_ids),
        "master_gap_closure_rollup_release_blocker_row_count": len(
            master_gap_release_blocker_rows
        ),
        "master_gap_closure_rollup_current_primary_open_gap_id": _text(
            master_gap_rollup.get("current_primary_open_gap_id")
        ),
        "master_gap_closure_rollup_science_claim_rollup_status": _text(
            master_gap_science_claim_row.get("rollup_status")
        ),
        "master_gap_closure_rollup_science_claim_evidence": _text(
            master_gap_science_claim_row.get("evidence")
        ),
        "master_gap_closure_rollup_science_claim_release_blocker": bool(
            master_gap_science_claim_row.get("release_blocker") is True
        ),
        "accuracy_parity_scorecard_gate_present": accuracy_parity_gate_present,
        "accuracy_parity_scorecard_status": _text(accuracy_parity.get("status")),
        "accuracy_parity_scorecard_recorded": (
            accuracy_parity_scorecard_recorded if accuracy_parity_gate_present else None
        ),
        "accuracy_parity_scorecard_row_count": _int(accuracy_parity.get("row_count")),
        "accuracy_parity_scorecard_pass_row_count": _int(accuracy_parity.get("pass_row_count")),
        "accuracy_parity_scorecard_restricted_pass_row_count": _int(
            accuracy_parity.get("restricted_pass_row_count")
        ),
        "accuracy_parity_scorecard_blocked_row_count": _int(accuracy_parity.get("blocked_row_count")),
        "accuracy_parity_scorecard_missing_row_count": _int(accuracy_parity.get("missing_row_count")),
        "accuracy_parity_scorecard_top_blocker_count": len(accuracy_parity_top_blockers),
        "accuracy_parity_scorecard_top_blockers": accuracy_parity_top_blockers,
        "accuracy_parity_scorecard_overall_commercial_tool_accuracy_parity_allowed": bool(
            accuracy_parity.get("overall_commercial_tool_accuracy_parity_allowed") is True
        ),
        "accuracy_parity_scorecard_schrodinger_class_claim_allowed": bool(
            accuracy_parity.get("schrodinger_class_claim_allowed") is True
        ),
        "accuracy_parity_scorecard_openmm_class_claim_allowed": bool(
            accuracy_parity.get("openmm_class_claim_allowed") is True
        ),
        "accuracy_parity_scorecard_current_broad_accuracy_parity_estimate_pct": _text(
            accuracy_parity.get("current_broad_accuracy_parity_estimate_pct")
        ),
        "accuracy_parity_scorecard_current_broad_commercial_platform_estimate_pct": _text(
            accuracy_parity.get("current_broad_commercial_platform_estimate_pct")
        ),
        "accuracy_parity_ligand_ranking_status": _text(accuracy_ligand_ranking.get("status")),
        "accuracy_parity_ligand_ranking_claim_promotion_allowed": bool(
            accuracy_ligand_ranking.get("claim_promotion_allowed") is True
        ),
        "accuracy_parity_ligand_ranking_commercial_parity_claim_allowed": bool(
            accuracy_ligand_ranking.get("commercial_parity_claim_allowed") is True
        ),
        "accuracy_parity_ligand_ranking_blocker_count": len(accuracy_ligand_blockers),
        "accuracy_parity_ligand_ranking_blockers": accuracy_ligand_blockers,
        "accuracy_parity_ligand_ranking_metric_thresholds_pass": (
            accuracy_ligand_metric_thresholds_pass
        ),
        "accuracy_parity_ligand_ranking_metric_blocker_count": len(
            accuracy_ligand_metric_blockers
        ),
        "accuracy_parity_ligand_ranking_metric_blockers": accuracy_ligand_metric_blockers,
        "accuracy_parity_ligand_ranking_claim_scope_lock_only": (
            accuracy_ligand_claim_scope_lock_only
        ),
        "accuracy_parity_ligand_ranking_pr_auc": accuracy_ligand_pr_auc,
        "accuracy_parity_ligand_ranking_pr_auc_ci_low": accuracy_ligand_pr_auc_ci_low,
        "accuracy_parity_ligand_ranking_topk_hit_rate": accuracy_ligand_topk_hit_rate,
        "accuracy_parity_ligand_ranking_positive_count": _int(
            accuracy_ligand_metrics.get("positive_count")
        ),
        "accuracy_parity_ligand_ranking_score_col_used": _text(
            accuracy_ligand_metrics.get("ranking_score_col_used")
        ),
        "accuracy_parity_ligand_ranking_pr_auc_threshold": accuracy_ligand_pr_auc_threshold,
        "accuracy_parity_ligand_ranking_pr_auc_ci_low_threshold": (
            accuracy_ligand_pr_auc_ci_low_threshold
        ),
        "accuracy_parity_ligand_ranking_topk_hit_rate_threshold": (
            accuracy_ligand_topk_hit_rate_threshold
        ),
        "accuracy_parity_ligand_ranking_next_required_step": _text(
            accuracy_ligand_ranking.get("next_required_step")
        ),
        "science_claim_promotion_gap_closure_gate_present": science_claim_gap_gate_present,
        "science_claim_promotion_gap_closure_status": _text(science_claim_gap.get("status")),
        "science_claim_promotion_gap_closure_recorded": (
            science_claim_gap_recorded if science_claim_gap_gate_present else None
        ),
        "science_claim_promotion_gap_closure_all_gaps_closed": (
            bool(science_claim_gap.get("all_gaps_closed") is True)
            if science_claim_gap_gate_present
            else None
        ),
        "science_claim_promotion_gap_closure_claim_promotion_allowed": bool(
            science_claim_gap.get("claim_promotion_allowed") is True
        ),
        "science_claim_promotion_gap_closure_open_gap_count": _int(
            science_claim_gap.get("open_gap_count")
        ),
        "science_claim_promotion_gap_closure_open_gap_ids": science_claim_open_gap_ids,
        "science_claim_promotion_gap_closure_open_gap_ids_joined": ";".join(
            science_claim_open_gap_ids
        ),
        "science_claim_promotion_gap_closure_closed_gap_count": _int(
            science_claim_gap.get("closed_gap_count")
        ),
        "science_claim_promotion_gap_closure_closed_gap_ids": science_claim_closed_gap_ids,
        "science_claim_promotion_gap_closure_closed_gap_ids_joined": ";".join(
            science_claim_closed_gap_ids
        ),
        "science_claim_promotion_gap_closure_release_blocker_row_count": len(
            science_claim_release_blocker_rows
        ),
        "science_claim_promotion_gap_closure_current_primary_open_gap_id": science_claim_primary_open_gap_id,
        "science_claim_promotion_gap_closure_current_next_action": _text(
            science_claim_gap.get("current_next_action")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_area": _text(
            science_claim_primary_open_gap.get("area")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status": _text(
            science_claim_primary_open_gap.get("claim_promotion_status")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_evidence": _text(
            science_claim_primary_open_gap.get("evidence")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_next_action": _text(
            science_claim_primary_open_gap.get("next_action")
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_release_blocker": bool(
            science_claim_primary_open_gap.get("release_blocker") is True
        ),
        "science_claim_promotion_gap_closure_gpcr_claim_promotion_status": _text(
            science_claim_gpcr_gap.get("claim_promotion_status")
        ),
        "science_claim_promotion_gap_closure_gpcr_evidence": _text(
            science_claim_gpcr_gap.get("evidence")
        ),
        "science_claim_promotion_gap_closure_gpcr_release_blocker": bool(
            science_claim_gpcr_gap.get("release_blocker") is True
        ),
        "science_claim_promotion_gap_closure_openmm_claim_promotion_status": _text(
            science_claim_openmm_gap.get("claim_promotion_status")
        ),
        "science_claim_promotion_gap_closure_openmm_evidence": _text(
            science_claim_openmm_gap.get("evidence")
        ),
        "science_claim_promotion_gap_closure_openmm_release_blocker": bool(
            science_claim_openmm_gap.get("release_blocker") is True
        ),
        "api_customer_flow_release_evidence_gate_present": api_customer_flow_gate_present,
        "api_customer_flow_release_evidence_status": _text(api_customer_flow.get("status")),
        "api_customer_flow_release_evidence_ready": api_customer_flow_ready if api_customer_flow_gate_present else None,
        "api_customer_flow_result_manifest_signature_verified": bool(
            api_customer_flow.get("result_manifest_signature_verified") is True
        ),
        "api_customer_flow_bundle_validation_ready": bool(api_customer_flow.get("bundle_validation_ready") is True),
        "api_customer_flow_restricted_runtime_ready": bool(
            api_customer_flow.get("restricted_unattended_runtime_ready") is True
        ),
        "api_customer_flow_blocker_count": _int(api_customer_flow.get("blocker_count")),
        "product_ai_architecture_gate_present": product_ai_architecture_gate_present,
        "product_ai_architecture_ready": product_ai_architecture_ready if product_ai_architecture_gate_present else None,
        "product_ai_architecture_open_gap_count": _int(product_ai_architecture.get("open_gap_count")),
        "product_ai_execution_backlog_work_item_count": _int(product_ai_backlog.get("work_item_count")),
        "product_ai_execution_backlog_release_blocking_work_item_count": product_ai_release_blocking_work_item_count,
        "product_ai_execution_backlog_optional_work_item_count": product_ai_optional_work_item_count,
        "product_ai_execution_backlog_primary_work_item_id": _text(product_ai_backlog.get("primary_work_item_id")),
        "product_ai_execution_backlog_primary_detail": product_ai_backlog_detail,
        "product_ai_execution_backlog_scope_closure_detail": product_ai_scope_detail,
        "goal_api_surface_check_count": _int(goal_api_surface.get("check_count")),
        "goal_api_surface_blocker_count": _int(goal_api_surface.get("blocker_count")),
        "goal_api_surface_missing_endpoint_count": _int(goal_api_surface.get("missing_endpoint_count")),
        "goal_api_surface_missing_status_key_count": _int(goal_api_surface.get("missing_status_key_count")),
        "source_operator_action_board_status": _text(actions.get("status")),
        "operator_action_count": _int(actions.get("action_count")),
        "operator_approval_required_count": _int(actions.get("approval_required_count")),
        "operator_review_required_count": _int(actions.get("review_required_count")),
        "approval_reclaim_size_gb": round(_float(actions.get("approval_reclaim_size_gb")), 3),
        "product_cli_status_set_status": _text(actions.get("product_cli_status_set_status")),
        "product_cli_approval_token_count": _int(actions.get("product_cli_approval_token_count")),
        "product_cli_operations_blocked_stage_count": _int(actions.get("product_cli_operations_blocked_stage_count")),
        "product_cli_operations_approval_required_stage_count": _int(
            actions.get("product_cli_operations_approval_required_stage_count")
        ),
        "product_cli_capability_surface_ready": bool(actions.get("product_cli_capability_surface_ready") is True),
        "product_cli_operational_quality_ready": bool(actions.get("product_cli_operational_quality_ready") is True),
        "product_operational_quality_ready": bool(
            actions.get("product_cli_operational_quality_ready") is True
            or actions.get("product_release_operations_operational_quality_ready") is True
        ),
        "product_operational_quality_status": _text(
            actions.get("product_release_operations_source_operational_quality_status")
        ),
        "product_operational_quality_blocker_count": _int(
            actions.get("product_release_operations_operational_quality_blocker_count")
        ),
        "product_operational_quality_artifact": _text(
            actions.get("product_release_operations_operational_quality_artifact")
        ),
        "product_cli_architecture_release_ready": bool(actions.get("product_cli_architecture_release_ready") is True),
        "product_cli_commercial_independence_ready": bool(actions.get("product_cli_commercial_independence_ready") is True),
        "product_cli_authorized_for_execution": bool(actions.get("product_cli_authorized_for_execution") is True),
        "product_cli_bundle_validation_passed": bool(actions.get("product_cli_bundle_validation_passed") is True),
        "product_cli_delivery_ready_claim_allowed": bool(actions.get("product_cli_delivery_ready_claim_allowed") is True),
        "cameo_cli_status_set_status": _text(actions.get("cameo_cli_status_set_status")),
        "cameo_cli_approval_token_count": _int(actions.get("cameo_cli_approval_token_count")),
        "cameo_cli_official_result_required": bool(actions.get("cameo_cli_official_result_required") is True),
        "cameo_cli_official_results_accepted_count": _int(actions.get("cameo_cli_official_results_accepted_count")),
        "cameo_cli_evidence_integrity_ready": bool(actions.get("cameo_cli_evidence_integrity_ready") is True),
        "cameo_cli_official_results_pending_honest": bool(
            actions.get("cameo_cli_official_results_pending_honest") is True
        ),
        "cameo_cli_no_local_native_accuracy_substitution": bool(
            actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
        ),
        "cameo_evidence_integrity_ready": bool(
            actions.get("cameo_cli_evidence_integrity_ready") is True
            or actions.get("cameo_validation_operations_evidence_integrity_ready") is True
        ),
        "cameo_evidence_integrity_status": _text(
            actions.get("cameo_validation_operations_evidence_integrity_status")
        ),
        "cameo_evidence_integrity_blocker_count": _int(
            actions.get("cameo_validation_operations_evidence_integrity_blocker_count")
        ),
        "cameo_evidence_integrity_artifact": _text(
            actions.get("cameo_validation_operations_evidence_integrity_artifact")
        ),
        "cameo_official_results_pending_honest": bool(
            actions.get("cameo_cli_official_results_pending_honest") is True
            or actions.get("cameo_validation_operations_official_results_pending_honest") is True
        ),
        "cameo_no_local_native_accuracy_substitution": bool(
            actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or actions.get("cameo_validation_operations_no_local_native_accuracy_substitution") is True
        ),
        "cameo_cli_api_install_approval_required": bool(actions.get("cameo_cli_api_install_approval_required") is True),
        "cameo_cli_receiver_smoke_status": _text(actions.get("cameo_cli_receiver_smoke_status")),
        "cameo_cli_public_registration_authorized": bool(actions.get("cameo_cli_public_registration_authorized") is True),
        "cleanup_cli_status_set_status": _text(actions.get("cleanup_cli_status_set_status")),
        "cleanup_cli_approval_token_count": _int(actions.get("cleanup_cli_approval_token_count")),
        "cleanup_cli_approval_reclaim_size_gb": round(_float(actions.get("cleanup_cli_approval_reclaim_size_gb")), 3),
        "cleanup_cli_postcheck_contract_ready": bool(actions.get("cleanup_cli_postcheck_contract_ready") is True),
        "cleanup_cli_postcheck_blocked_row_count": _int(actions.get("cleanup_cli_postcheck_blocked_row_count")),
        "cleanup_cli_protected_payload_size_gb": round(_float(actions.get("cleanup_cli_protected_payload_size_gb")), 3),
        "cleanup_cli_protected_policy_change_required_count": _int(
            actions.get("cleanup_cli_protected_policy_change_required_count")
        ),
        "cleanup_cli_protected_policy_resolved": bool(actions.get("cleanup_cli_protected_policy_resolved") is True),
        "protected_cleanup_payload_size_gb": round(_float(protected_cleanup.get("protected_payload_size_gb")), 3),
        "protected_cleanup_policy_change_required_count": _int(protected_cleanup.get("policy_change_required_count")),
        "protected_cleanup_policy_decision_gate_status": _text(protected_policy_gate.get("status")),
        "protected_cleanup_known_payload_child_count": _int(protected_policy_gate.get("known_payload_child_count")),
        "protected_cleanup_known_payload_child_size_gb": round(_float(protected_policy_gate.get("known_payload_child_size_gb")), 3),
        "protected_cleanup_preservation_sibling_count": _int(protected_policy_gate.get("preservation_sibling_count")),
        "protected_cleanup_policy_change_required_for_deletion_count": _int(
            protected_policy_gate.get("policy_change_required_for_deletion_count")
        ),
        "protected_cleanup_policy_resolved": protected_policy_resolved,
        "cleanup_postcheck_contract_status": _text(cleanup_postcheck.get("status")),
        "cleanup_postcheck_contract_ready": cleanup_postcheck_ready,
        "cleanup_postcheck_row_count": _int(cleanup_postcheck.get("row_count")),
        "cleanup_postcheck_blocked_row_count": _int(cleanup_postcheck.get("blocked_row_count")),
        "cleanup_postcheck_global_refresh_command_count": _int(cleanup_postcheck.get("global_refresh_command_count")),
        "cleanup_completion_gate_status": _text(cleanup_completion.get("status")),
        "cleanup_completion_complete": cleanup_completion_ready,
        "cleanup_completion_blocked_stage_count": cleanup_completion_blocked_stage_count,
        "cleanup_completion_total_reclaim_size_gb": cleanup_completion_total_reclaim_size_gb,
        "cleanup_completion_authorized_reclaim_size_gb": cleanup_completion_authorized_reclaim_size_gb,
        "cleanup_completion_awaiting_approval_count": cleanup_completion_awaiting_approval_count,
        "cleanup_completion_blocked_approval_count": cleanup_completion_blocked_approval_count,
        "cleanup_completion_transition_approval_gated_reclaim_size_gb": cleanup_completion_transition_reclaim_size_gb,
        "cleanup_completion_ligand_heavy_candidate_size_gb": cleanup_completion_ligand_candidate_size_gb,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Release Decision Gate",
        "",
        f"- status: `{s['status']}`",
        f"- release_allowed: `{s['release_allowed']}`",
        f"- restricted_release_allowed: `{s['restricted_release_allowed']}`",
        f"- full_commercial_release_allowed: `{s['full_commercial_release_allowed']}`",
        f"- full_commercial_release_blocker_count: `{s['full_commercial_release_blocker_count']}`",
        f"- full_commercial_release_blocker_ids: `{';'.join(s['full_commercial_release_blocker_ids'])}`",
        f"- primary_full_commercial_release_blocker_id: `{s['primary_full_commercial_release_blocker_id']}`",
        f"- primary_full_commercial_release_blocker_requirement_id: `{s['primary_full_commercial_release_blocker_requirement_id']}`",
        f"- primary_full_commercial_release_blocker_tier: `{s['primary_full_commercial_release_blocker_tier']}`",
        f"- primary_full_commercial_release_blocker: `{s['primary_full_commercial_release_blocker']}`",
        f"- primary_full_commercial_release_blocker_blocked_row_count: `{s['primary_full_commercial_release_blocker_blocked_row_count']}`",
        f"- primary_full_commercial_release_blocker_first_blocked_evidence_row_id: `{s['primary_full_commercial_release_blocker_first_blocked_evidence_row_id']}`",
        f"- primary_full_commercial_release_blocker_receipt_csv: `{s['primary_full_commercial_release_blocker_receipt_csv']}`",
        f"- primary_full_commercial_release_blocker_approval_token_required: `{s['primary_full_commercial_release_blocker_approval_token_required']}`",
        f"- primary_full_commercial_release_blocker_next_required_step: `{s['primary_full_commercial_release_blocker_next_required_step']}`",
        f"- commercial_independent_product_ready: `{s['commercial_independent_product_ready']}`",
        f"- product_architecture_local_surface_ready: `{s['product_architecture_local_surface_ready']}`",
        f"- product_architecture_release_ready: `{s['product_architecture_release_ready']}`",
        f"- product_architecture_public_benchmark_validation_ready: `{s['product_architecture_public_benchmark_validation_ready']}`",
        f"- product_architecture_public_benchmark_status: `{s['product_architecture_public_benchmark_status']}`",
        f"- product_architecture_public_benchmark_required_suite_count: `{s['product_architecture_public_benchmark_required_suite_count']}`",
        f"- product_architecture_public_benchmark_ready_required_suite_count: `{s['product_architecture_public_benchmark_ready_required_suite_count']}`",
        f"- product_architecture_public_benchmark_blocked_suite_count: `{s['product_architecture_public_benchmark_blocked_suite_count']}`",
        f"- product_architecture_public_benchmark_suite_materialization_manifest_count: `{s['product_architecture_public_benchmark_suite_materialization_manifest_count']}`",
        f"- product_architecture_public_benchmark_suite_scorecard_row_csv_count: `{s['product_architecture_public_benchmark_suite_scorecard_row_csv_count']}`",
        f"- product_architecture_public_benchmark_suite_threshold_count: `{s['product_architecture_public_benchmark_suite_threshold_count']}`",
        f"- product_architecture_public_benchmark_suite_blocker_count: `{s['product_architecture_public_benchmark_suite_blocker_count']}`",
        f"- product_architecture_public_benchmark_suite_run_command_count: `{s['product_architecture_public_benchmark_suite_run_command_count']}`",
        f"- product_architecture_public_benchmark_suite_materialization_run_command_count: `{s['product_architecture_public_benchmark_suite_materialization_run_command_count']}`",
        f"- product_architecture_public_benchmark_suite_no_external_dependency_count: `{s['product_architecture_public_benchmark_suite_no_external_dependency_count']}`",
        f"- product_architecture_public_benchmark_requires_24h_server: `{s['product_architecture_public_benchmark_requires_24h_server']}`",
        f"- product_architecture_public_benchmark_requires_competition_season: `{s['product_architecture_public_benchmark_requires_competition_season']}`",
        f"- product_architecture_public_benchmark_requires_paid_vps: `{s['product_architecture_public_benchmark_requires_paid_vps']}`",
        f"- public_benchmark_required_for_product_release: `{s['public_benchmark_required_for_product_release']}`",
        f"- release_blocked_by_public_benchmark: `{s['release_blocked_by_public_benchmark']}`",
        f"- cameo_live_validation_channel: `{s['cameo_live_validation_channel']}`",
        f"- cameo_live_validation_required_for_product_release: `{s['cameo_live_validation_required_for_product_release']}`",
        f"- cameo_registration_required_for_product_release: `{s['cameo_registration_required_for_product_release']}`",
        f"- cameo_official_results_required_for_product_release: `{s['cameo_official_results_required_for_product_release']}`",
        f"- release_blocked_by_cameo_live_validation: `{s['release_blocked_by_cameo_live_validation']}`",
        f"- product_architecture_cameo_official_validation_evidence_ready: `{s['product_architecture_cameo_official_validation_evidence_ready']}`",
        f"- product_architecture_cameo_receiver_smoke_status: `{s['product_architecture_cameo_receiver_smoke_status']}`",
        f"- product_architecture_cameo_api_dependency_status: `{s['product_architecture_cameo_api_dependency_status']}`",
        f"- product_architecture_cameo_public_registration_blocker_count: `{s['product_architecture_cameo_public_registration_blocker_count']}`",
        f"- product_architecture_cameo_registration_approval_token_count: `{s['product_architecture_cameo_registration_approval_token_count']}`",
        f"- product_architecture_cameo_registration_approval_tokens_required: `{';'.join(s['product_architecture_cameo_registration_approval_tokens_required'])}`",
        f"- cameo_official_result_fetch_preflight_recorded: `{s['cameo_official_result_fetch_preflight_recorded']}`",
        f"- cameo_official_result_fetch_preflight_status: `{s['cameo_official_result_fetch_preflight_status']}`",
        f"- cameo_official_result_fetch_preflight_blocked_row_count: `{s['cameo_official_result_fetch_preflight_blocked_row_count']}`",
        f"- cameo_official_result_fetch_preflight_fetch_approval_token_required: `{s['cameo_official_result_fetch_preflight_fetch_approval_token_required']}`",
        f"- cameo_official_result_fetch_preflight_network_request_opened: `{s['cameo_official_result_fetch_preflight_network_request_opened']}`",
        f"- cameo_official_result_fetch_preflight_official_results_fetched: `{s['cameo_official_result_fetch_preflight_official_results_fetched']}`",
        f"- cameo_official_result_fetch_preflight_native_local_accuracy_used: `{s['cameo_official_result_fetch_preflight_native_local_accuracy_used']}`",
        f"- product_commercial_independence_ready: `{s['product_commercial_independence_ready']}`",
        f"- self_hosted_license_distribution_audit_recorded: `{s['self_hosted_license_distribution_audit_recorded']}`",
        f"- self_hosted_license_distribution_audit_status: `{s['self_hosted_license_distribution_audit_status']}`",
        f"- self_hosted_license_distribution_audit_product_license_path: `{s['self_hosted_license_distribution_audit_product_license_path']}`",
        f"- self_hosted_license_distribution_audit_product_license_hash_matches_approved_source: `{s['self_hosted_license_distribution_audit_product_license_hash_matches_approved_source']}`",
        f"- self_hosted_license_distribution_audit_spdx_license_id: `{s['self_hosted_license_distribution_audit_spdx_license_id']}`",
        f"- self_hosted_license_distribution_audit_hard_blocker_count: `{s['self_hosted_license_distribution_audit_hard_blocker_count']}`",
        f"- self_hosted_license_distribution_audit_operator_review_item_count: `{s['self_hosted_license_distribution_audit_operator_review_item_count']}`",
        f"- self_hosted_license_distribution_audit_legal_advice_provided: `{s['self_hosted_license_distribution_audit_legal_advice_provided']}`",
        f"- self_hosted_license_distribution_audit_third_party_license_review_gate_status: `{s['self_hosted_license_distribution_audit_third_party_license_review_gate_status']}`",
        f"- self_hosted_license_distribution_audit_third_party_dual_license_assets: `{s['self_hosted_license_distribution_audit_third_party_dual_license_assets']}`",
        f"- third_party_license_review_gate_recorded: `{s['third_party_license_review_gate_recorded']}`",
        f"- third_party_license_review_gate_status: `{s['third_party_license_review_gate_status']}`",
        f"- third_party_license_review_gate_approved_assets: `{s['third_party_license_review_gate_approved_assets']}`",
        f"- third_party_license_review_gate_expected_review_asset_count: `{s['third_party_license_review_gate_expected_review_asset_count']}`",
        f"- third_party_license_review_gate_blocker_count: `{s['third_party_license_review_gate_blocker_count']}`",
        f"- third_party_license_review_gate_legal_advice_provided: `{s['third_party_license_review_gate_legal_advice_provided']}`",
        f"- third_party_license_review_gate_asset_modified: `{s['third_party_license_review_gate_asset_modified']}`",
        f"- third_party_license_review_gate_approval_token_required: `{s['third_party_license_review_gate_approval_token_required']}`",
        f"- cameo_architecture_validation_ready: `{s['cameo_architecture_validation_ready']}`",
        f"- cleanup_objective_ready: `{s['cleanup_objective_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- source_goal_api_surface_contract_status: `{s['source_goal_api_surface_contract_status']}`",
        f"- goal_api_surface_ready: `{s['goal_api_surface_ready']}`",
        f"- api_runner_profile_promotion_operator_receipt_gate_present: `{s['api_runner_profile_promotion_operator_receipt_gate_present']}`",
        f"- api_runner_profile_promotion_operator_receipt_status: `{s['api_runner_profile_promotion_operator_receipt_status']}`",
        f"- api_runner_profile_promotion_operator_receipt_recorded: `{s['api_runner_profile_promotion_operator_receipt_recorded']}`",
        f"- api_runner_profile_promotion_operator_receipt_ready: `{s['api_runner_profile_promotion_operator_receipt_ready']}`",
        f"- api_runner_profile_promotion_operator_receipt_profile_count: `{s['api_runner_profile_promotion_operator_receipt_profile_count']}`",
        f"- api_runner_profile_promotion_operator_receipt_blocked_row_count: `{s['api_runner_profile_promotion_operator_receipt_blocked_row_count']}`",
        f"- api_runner_profile_promotion_operator_receipt_first_blocked_profile_id: `{s['api_runner_profile_promotion_operator_receipt_first_blocked_profile_id']}`",
        f"- api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker: `{s['api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker']}`",
        f"- api_runner_profile_promotion_operator_receipt_approval_token_required: `{s['api_runner_profile_promotion_operator_receipt_approval_token_required']}`",
        f"- api_runner_profile_promotion_operator_receipt_runner_executed: `{s['api_runner_profile_promotion_operator_receipt_runner_executed']}`",
        f"- product_scope_breadth_evidence_receipt_status: `{s['product_scope_breadth_evidence_receipt_status']}`",
        f"- product_scope_breadth_evidence_receipt_recorded: `{s['product_scope_breadth_evidence_receipt_recorded']}`",
        f"- product_scope_breadth_evidence_receipt_ready: `{s['product_scope_breadth_evidence_receipt_ready']}`",
        f"- product_scope_breadth_evidence_receipt_blocked_row_count: `{s['product_scope_breadth_evidence_receipt_blocked_row_count']}`",
        "- product_scope_breadth_evidence_receipt_operator_review_surface_ready/blocked: "
        f"`{s['product_scope_breadth_evidence_receipt_operator_review_surface_ready_count']}/"
        f"{s['product_scope_breadth_evidence_receipt_operator_review_surface_blocked_count']}`",
        "- product_scope_breadth_evidence_receipt_receipt_manual_field_pending_count: "
        f"`{s['product_scope_breadth_evidence_receipt_receipt_manual_field_pending_count']}`",
        f"- product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id: `{s['product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id']}`",
        f"- product_scope_breadth_evidence_receipt_most_common_row_blocker: `{s['product_scope_breadth_evidence_receipt_most_common_row_blocker']}`",
        f"- product_scope_breadth_evidence_receipt_approval_token_required: `{s['product_scope_breadth_evidence_receipt_approval_token_required']}`",
        f"- engine_refinement_claim_evidence_receipt_status: `{s['engine_refinement_claim_evidence_receipt_status']}`",
        f"- engine_refinement_claim_evidence_receipt_recorded: `{s['engine_refinement_claim_evidence_receipt_recorded']}`",
        f"- engine_refinement_claim_evidence_receipt_ready: `{s['engine_refinement_claim_evidence_receipt_ready']}`",
        f"- engine_refinement_claim_evidence_receipt_blocked_row_count: `{s['engine_refinement_claim_evidence_receipt_blocked_row_count']}`",
        f"- engine_refinement_claim_evidence_receipt_first_blocked_blocker_id: `{s['engine_refinement_claim_evidence_receipt_first_blocked_blocker_id']}`",
        f"- engine_refinement_claim_evidence_receipt_most_common_row_blocker: `{s['engine_refinement_claim_evidence_receipt_most_common_row_blocker']}`",
        f"- engine_refinement_claim_evidence_receipt_approval_token_required: `{s['engine_refinement_claim_evidence_receipt_approval_token_required']}`",
        f"- engine_refinement_claim_evidence_priority_packet_recorded: `{s['engine_refinement_claim_evidence_priority_packet_recorded']}`",
        f"- engine_refinement_claim_evidence_priority_packet_status: `{s['engine_refinement_claim_evidence_priority_packet_status']}`",
        f"- engine_refinement_claim_evidence_priority_packet_top_blocker_id: `{s['engine_refinement_claim_evidence_priority_packet_top_blocker_id']}`",
        f"- engine_refinement_claim_evidence_priority_packet_top_priority_bucket: `{s['engine_refinement_claim_evidence_priority_packet_top_priority_bucket']}`",
        f"- engine_refinement_claim_evidence_priority_packet_top_required_input: `{s['engine_refinement_claim_evidence_priority_packet_top_required_input']}`",
        f"- engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_blocked_row_count: `{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_blocked_row_count']}`",
        f"- engine_refinement_claim_evidence_priority_packet_approval_token_required: `{s['engine_refinement_claim_evidence_priority_packet_approval_token_required']}`",
        f"- refine_tier_public_benchmark_recorded: `{s['refine_tier_public_benchmark_recorded']}`",
        f"- refine_tier_public_benchmark_status: `{s['refine_tier_public_benchmark_status']}`",
        f"- refine_tier_public_benchmark_claim_grade_public_benchmark_ready: `{s['refine_tier_public_benchmark_claim_grade_public_benchmark_ready']}`",
        f"- refine_tier_public_benchmark_row_count: `{s['refine_tier_public_benchmark_row_count']}`",
        f"- refine_tier_public_benchmark_valid_row_count: `{s['refine_tier_public_benchmark_valid_row_count']}`",
        f"- refine_tier_public_benchmark_blocker_count: `{s['refine_tier_public_benchmark_blocker_count']}`",
        f"- refine_tier_public_benchmark_operator_work_order_ready: `{s['refine_tier_public_benchmark_operator_work_order_ready']}`",
        f"- refine_tier_public_benchmark_work_order_row_count: `{s['refine_tier_public_benchmark_work_order_row_count']}`",
        f"- refine_tier_public_benchmark_write_intake_approval_token_required: `{s['refine_tier_public_benchmark_write_intake_approval_token_required']}`",
        f"- refine_tier_public_benchmark_work_order_apply_recorded: `{s['refine_tier_public_benchmark_work_order_apply_recorded']}`",
        f"- refine_tier_public_benchmark_work_order_apply_status: `{s['refine_tier_public_benchmark_work_order_apply_status']}`",
        f"- refine_tier_public_benchmark_work_order_apply_blocked_row_count: `{s['refine_tier_public_benchmark_work_order_apply_blocked_row_count']}`",
        f"- refine_tier_public_benchmark_work_order_apply_intake_written: `{s['refine_tier_public_benchmark_work_order_apply_intake_written']}`",
        f"- refine_tier_public_benchmark_work_order_apply_external_state_mutated: `{s['refine_tier_public_benchmark_work_order_apply_external_state_mutated']}`",
        f"- goal_bottleneck_briefing_gate_present: `{s['goal_bottleneck_briefing_gate_present']}`",
        f"- source_goal_bottleneck_briefing_status: `{s['source_goal_bottleneck_briefing_status']}`",
        f"- goal_bottleneck_briefing_full_commercial_receipts_recorded: `{s['goal_bottleneck_briefing_full_commercial_receipts_recorded']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count']}`",
        f"- goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs: `{s['goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_status: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_status']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id']}`",
        f"- goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count: `{s['goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count']}`",
        f"- production_ai_registry_promotion_priority_packet_recorded: `{s['production_ai_registry_promotion_priority_packet_recorded']}`",
        f"- production_ai_registry_promotion_priority_packet_status: `{s['production_ai_registry_promotion_priority_packet_status']}`",
        f"- production_ai_registry_promotion_priority_top_gate_id: `{s['production_ai_registry_promotion_priority_top_gate_id']}`",
        f"- production_ai_registry_promotion_priority_missing_gate_count: `{s['production_ai_registry_promotion_priority_missing_gate_count']}`",
        f"- production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count: `{s['production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count']}`",
        f"- production_ai_registry_promotion_priority_observed_registry_default_residual_mode: `{s['production_ai_registry_promotion_priority_observed_registry_default_residual_mode']}`",
        f"- production_ai_registry_promotion_priority_operator_receipt_status: `{s['production_ai_registry_promotion_priority_operator_receipt_status']}`",
        f"- production_ai_registry_promotion_priority_approval_token_required: `{s['production_ai_registry_promotion_priority_approval_token_required']}`",
        f"- production_ai_checkpoint_readiness_recorded: `{s['production_ai_checkpoint_readiness_recorded']}`",
        f"- production_ai_checkpoint_readiness_status: `{s['production_ai_checkpoint_readiness_status']}`",
        f"- production_ai_checkpoint_readiness_production_gpu_execution_environment_ready: `{s['production_ai_checkpoint_readiness_production_gpu_execution_environment_ready']}`",
        f"- production_ai_checkpoint_readiness_checkpoint_preflight_ready: `{s['production_ai_checkpoint_readiness_checkpoint_preflight_ready']}`",
        f"- production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_count: `{s['production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_count']}`",
        f"- production_ai_checkpoint_readiness_actionable_blocker_stage_id: `{s['production_ai_checkpoint_readiness_actionable_blocker_stage_id']}`",
        f"- production_ai_checkpoint_readiness_registry_promotion_missing_gate_ids: `{s['production_ai_checkpoint_readiness_registry_promotion_missing_gate_ids']}`",
        f"- production_ai_checkpoint_readiness_trained_model_checkpoint_count: `{s['production_ai_checkpoint_readiness_trained_model_checkpoint_count']}`",
        f"- production_ai_checkpoint_readiness_default_residual_mode: `{s['production_ai_checkpoint_readiness_default_residual_mode']}`",
        f"- production_ai_promotion_workbench_recorded: `{s['production_ai_promotion_workbench_recorded']}`",
        f"- production_ai_promotion_workbench_status: `{s['production_ai_promotion_workbench_status']}`",
        f"- production_ai_promotion_workbench_post_return_ladder_blocked_stage_count: `{s['production_ai_promotion_workbench_post_return_ladder_blocked_stage_count']}`",
        f"- production_ai_promotion_workbench_first_blocked_stage_id: `{s['production_ai_promotion_workbench_first_blocked_stage_id']}`",
        f"- production_ai_promotion_workbench_registry_promotion_missing_gate_ids: `{s['production_ai_promotion_workbench_registry_promotion_missing_gate_ids']}`",
        f"- product_release_source_of_truth_gate_present: `{s['product_release_source_of_truth_gate_present']}`",
        f"- product_release_source_of_truth_status: `{s['product_release_source_of_truth_status']}`",
        f"- product_release_source_of_truth_ready: `{s['product_release_source_of_truth_ready']}`",
        f"- product_release_source_of_truth_blocker_count: `{s['product_release_source_of_truth_blocker_count']}`",
        f"- product_release_source_of_truth_stale_artifact_count: `{s['product_release_source_of_truth_stale_artifact_count']}`",
        f"- product_release_source_of_truth_readme_drift_count: `{s['product_release_source_of_truth_readme_drift_count']}`",
        f"- product_quality_gate_verification_gate_present: `{s['product_quality_gate_verification_gate_present']}`",
        f"- product_quality_gate_verification_status: `{s['product_quality_gate_verification_status']}`",
        f"- product_quality_gate_verification_recorded: `{s['product_quality_gate_verification_recorded']}`",
        f"- product_quality_gate_verification_ready: `{s['product_quality_gate_verification_ready']}`",
        f"- product_quality_gate_verification_source_contract_status: `{s['product_quality_gate_verification_source_contract_status']}`",
        f"- product_quality_gate_verification_check_count: `{s['product_quality_gate_verification_check_count']}`",
        f"- product_quality_gate_verification_pass_count: `{s['product_quality_gate_verification_pass_count']}`",
        f"- product_quality_gate_verification_blocker_count: `{s['product_quality_gate_verification_blocker_count']}`",
        f"- product_quality_gate_verification_execution_enabled: `{s['product_quality_gate_verification_execution_enabled']}`",
        f"- product_quality_gate_verification_external_state_mutated: `{s['product_quality_gate_verification_external_state_mutated']}`",
        f"- product_pose_sampling_readiness_gate_present: `{s['product_pose_sampling_readiness_gate_present']}`",
        f"- product_pose_sampling_readiness_status: `{s['product_pose_sampling_readiness_status']}`",
        f"- product_pose_sampling_readiness_recorded: `{s['product_pose_sampling_readiness_recorded']}`",
        f"- product_pose_sampling_readiness_ready: `{s['product_pose_sampling_readiness_ready']}`",
        f"- product_pose_sampling_readiness_pose_generation_contract_ready: `{s['product_pose_sampling_readiness_pose_generation_contract_ready']}`",
        f"- product_pose_sampling_readiness_pose_count: `{s['product_pose_sampling_readiness_pose_count']}`",
        f"- product_pose_sampling_readiness_cluster_count: `{s['product_pose_sampling_readiness_cluster_count']}`",
        f"- product_pose_sampling_readiness_cross_docking_pose_count: `{s['product_pose_sampling_readiness_cross_docking_pose_count']}`",
        f"- product_pose_sampling_readiness_claim_grade_pose_accuracy_ready: `{s['product_pose_sampling_readiness_claim_grade_pose_accuracy_ready']}`",
        f"- product_pose_sampling_readiness_docking_results_emitted: `{s['product_pose_sampling_readiness_docking_results_emitted']}`",
        f"- product_pose_sampling_readiness_execution_enabled: `{s['product_pose_sampling_readiness_execution_enabled']}`",
        f"- product_pose_sampling_readiness_external_state_mutated: `{s['product_pose_sampling_readiness_external_state_mutated']}`",
        f"- product_ledger_privacy_scan_gate_present: `{s['product_ledger_privacy_scan_gate_present']}`",
        f"- product_ledger_privacy_scan_status: `{s['product_ledger_privacy_scan_status']}`",
        f"- product_ledger_privacy_scan_recorded: `{s['product_ledger_privacy_scan_recorded']}`",
        f"- product_ledger_privacy_scan_ready: `{s['product_ledger_privacy_scan_ready']}`",
        f"- product_ledger_privacy_scan_scan_file_count: `{s['product_ledger_privacy_scan_scan_file_count']}`",
        f"- product_ledger_privacy_scan_scan_glob_count: `{s['product_ledger_privacy_scan_scan_glob_count']}`",
        f"- product_ledger_privacy_scan_pass_count: `{s['product_ledger_privacy_scan_pass_count']}`",
        f"- product_ledger_privacy_scan_blocker_count: `{s['product_ledger_privacy_scan_blocker_count']}`",
        f"- product_ledger_privacy_scan_leak_count: `{s['product_ledger_privacy_scan_leak_count']}`",
        f"- product_ledger_privacy_scan_invalid_json_count: `{s['product_ledger_privacy_scan_invalid_json_count']}`",
        f"- product_ledger_privacy_scan_execution_enabled: `{s['product_ledger_privacy_scan_execution_enabled']}`",
        f"- product_ledger_privacy_scan_external_state_mutated: `{s['product_ledger_privacy_scan_external_state_mutated']}`",
        f"- product_full_commercial_blocker_evidence_matrix_gate_present: `{s['product_full_commercial_blocker_evidence_matrix_gate_present']}`",
        f"- product_full_commercial_blocker_evidence_matrix_status: `{s['product_full_commercial_blocker_evidence_matrix_status']}`",
        f"- product_full_commercial_blocker_evidence_matrix_ready: `{s['product_full_commercial_blocker_evidence_matrix_ready']}`",
        f"- product_full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready: `{s['product_full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready']}`",
        f"- product_full_commercial_blocker_evidence_matrix_row_count: `{s['product_full_commercial_blocker_evidence_matrix_row_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_blocked_row_count: `{s['product_full_commercial_blocker_evidence_matrix_blocked_row_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_approval_token_count: `{s['product_full_commercial_blocker_evidence_matrix_approval_token_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status']}`",
        f"- product_full_commercial_blocker_evidence_matrix_first_blocked_row_blockers: `{s['product_full_commercial_blocker_evidence_matrix_first_blocked_row_blockers']}`",
        f"- product_full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker: `{s['product_full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker']}`",
        f"- product_full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker: `{s['product_full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r8_blocked_row_count: `{s['product_full_commercial_blocker_evidence_matrix_r8_blocked_row_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r8_first_blocked_evidence_row_id: `{s['product_full_commercial_blocker_evidence_matrix_r8_first_blocked_evidence_row_id']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r8_receipt_csv: `{s['product_full_commercial_blocker_evidence_matrix_r8_receipt_csv']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r8_approval_token_required: `{s['product_full_commercial_blocker_evidence_matrix_r8_approval_token_required']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r9_blocked_row_count: `{s['product_full_commercial_blocker_evidence_matrix_r9_blocked_row_count']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r9_first_blocked_evidence_row_id: `{s['product_full_commercial_blocker_evidence_matrix_r9_first_blocked_evidence_row_id']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r9_receipt_csv: `{s['product_full_commercial_blocker_evidence_matrix_r9_receipt_csv']}`",
        f"- product_full_commercial_blocker_evidence_matrix_r9_approval_token_required: `{s['product_full_commercial_blocker_evidence_matrix_r9_approval_token_required']}`",
        f"- product_rollout_execution_smoke_receipt_gate_present: `{s['product_rollout_execution_smoke_receipt_gate_present']}`",
        f"- product_rollout_execution_smoke_receipt_status: `{s['product_rollout_execution_smoke_receipt_status']}`",
        f"- product_rollout_execution_smoke_receipt_ready: `{s['product_rollout_execution_smoke_receipt_ready']}`",
        f"- product_rollout_execution_smoke_receipt_csv_present: `{s['product_rollout_execution_smoke_receipt_csv_present']}`",
        f"- product_rollout_execution_smoke_receipt_row_count: `{s['product_rollout_execution_smoke_receipt_row_count']}`",
        f"- product_rollout_execution_smoke_receipt_blocker_count: `{s['product_rollout_execution_smoke_receipt_blocker_count']}`",
        f"- product_rollout_execution_smoke_receipt_rollout_executed: `{s['product_rollout_execution_smoke_receipt_rollout_executed']}`",
        f"- product_rollout_execution_smoke_receipt_external_state_mutated: `{s['product_rollout_execution_smoke_receipt_external_state_mutated']}`",
        f"- product_rollout_execution_smoke_receipt_pager_provider_contacted: `{s['product_rollout_execution_smoke_receipt_pager_provider_contacted']}`",
        f"- product_rollout_execution_smoke_receipt_ingress_certificate_verified_live: `{s['product_rollout_execution_smoke_receipt_ingress_certificate_verified_live']}`",
        f"- master_gap_closure_rollup_gate_present: `{s['master_gap_closure_rollup_gate_present']}`",
        f"- master_gap_closure_rollup_status: `{s['master_gap_closure_rollup_status']}`",
        f"- master_gap_closure_rollup_recorded: `{s['master_gap_closure_rollup_recorded']}`",
        f"- master_gap_closure_rollup_all_gaps_closed: `{s['master_gap_closure_rollup_all_gaps_closed']}`",
        f"- master_gap_closure_rollup_claim_promotion_allowed: `{s['master_gap_closure_rollup_claim_promotion_allowed']}`",
        f"- master_gap_closure_rollup_open_gap_count: `{s['master_gap_closure_rollup_open_gap_count']}`",
        f"- master_gap_closure_rollup_open_gap_ids: `{';'.join(s['master_gap_closure_rollup_open_gap_ids'])}`",
        f"- master_gap_closure_rollup_closed_gap_count: `{s['master_gap_closure_rollup_closed_gap_count']}`",
        f"- master_gap_closure_rollup_closed_gap_ids: `{';'.join(s['master_gap_closure_rollup_closed_gap_ids'])}`",
        f"- master_gap_closure_rollup_release_blocker_row_count: `{s['master_gap_closure_rollup_release_blocker_row_count']}`",
        f"- master_gap_closure_rollup_current_primary_open_gap_id: `{s['master_gap_closure_rollup_current_primary_open_gap_id']}`",
        f"- master_gap_closure_rollup_science_claim_rollup_status: `{s['master_gap_closure_rollup_science_claim_rollup_status']}`",
        f"- master_gap_closure_rollup_science_claim_evidence: `{s['master_gap_closure_rollup_science_claim_evidence']}`",
        f"- master_gap_closure_rollup_science_claim_release_blocker: `{s['master_gap_closure_rollup_science_claim_release_blocker']}`",
        f"- accuracy_parity_scorecard_gate_present: `{s['accuracy_parity_scorecard_gate_present']}`",
        f"- accuracy_parity_scorecard_status: `{s['accuracy_parity_scorecard_status']}`",
        f"- accuracy_parity_scorecard_recorded: `{s['accuracy_parity_scorecard_recorded']}`",
        f"- accuracy_parity_scorecard_row_count: `{s['accuracy_parity_scorecard_row_count']}`",
        f"- accuracy_parity_scorecard_pass_row_count: `{s['accuracy_parity_scorecard_pass_row_count']}`",
        f"- accuracy_parity_scorecard_blocked_row_count: `{s['accuracy_parity_scorecard_blocked_row_count']}`",
        f"- accuracy_parity_scorecard_top_blocker_count: `{s['accuracy_parity_scorecard_top_blocker_count']}`",
        f"- accuracy_parity_scorecard_top_blockers: `{';'.join(s['accuracy_parity_scorecard_top_blockers'])}`",
        f"- accuracy_parity_scorecard_schrodinger_class_claim_allowed: `{s['accuracy_parity_scorecard_schrodinger_class_claim_allowed']}`",
        f"- accuracy_parity_ligand_ranking_status: `{s['accuracy_parity_ligand_ranking_status']}`",
        f"- accuracy_parity_ligand_ranking_pr_auc: `{s['accuracy_parity_ligand_ranking_pr_auc']}`",
        f"- accuracy_parity_ligand_ranking_pr_auc_ci_low: `{s['accuracy_parity_ligand_ranking_pr_auc_ci_low']}`",
        f"- accuracy_parity_ligand_ranking_topk_hit_rate: `{s['accuracy_parity_ligand_ranking_topk_hit_rate']}`",
        f"- accuracy_parity_ligand_ranking_metric_thresholds_pass: `{s['accuracy_parity_ligand_ranking_metric_thresholds_pass']}`",
        f"- accuracy_parity_ligand_ranking_metric_blocker_count: `{s['accuracy_parity_ligand_ranking_metric_blocker_count']}`",
        f"- accuracy_parity_ligand_ranking_claim_scope_lock_only: `{s['accuracy_parity_ligand_ranking_claim_scope_lock_only']}`",
        f"- accuracy_parity_ligand_ranking_blocker_count: `{s['accuracy_parity_ligand_ranking_blocker_count']}`",
        f"- accuracy_parity_ligand_ranking_blockers: `{';'.join(s['accuracy_parity_ligand_ranking_blockers'])}`",
        f"- science_claim_promotion_gap_closure_gate_present: `{s['science_claim_promotion_gap_closure_gate_present']}`",
        f"- science_claim_promotion_gap_closure_status: `{s['science_claim_promotion_gap_closure_status']}`",
        f"- science_claim_promotion_gap_closure_recorded: `{s['science_claim_promotion_gap_closure_recorded']}`",
        f"- science_claim_promotion_gap_closure_open_gap_count: `{s['science_claim_promotion_gap_closure_open_gap_count']}`",
        f"- science_claim_promotion_gap_closure_open_gap_ids: `{';'.join(s['science_claim_promotion_gap_closure_open_gap_ids'])}`",
        f"- science_claim_promotion_gap_closure_closed_gap_count: `{s['science_claim_promotion_gap_closure_closed_gap_count']}`",
        f"- science_claim_promotion_gap_closure_closed_gap_ids: `{';'.join(s['science_claim_promotion_gap_closure_closed_gap_ids'])}`",
        f"- science_claim_promotion_gap_closure_release_blocker_row_count: `{s['science_claim_promotion_gap_closure_release_blocker_row_count']}`",
        f"- science_claim_promotion_gap_closure_current_primary_open_gap_id: `{s['science_claim_promotion_gap_closure_current_primary_open_gap_id']}`",
        f"- science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status: `{s['science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status']}`",
        f"- science_claim_promotion_gap_closure_gpcr_claim_promotion_status: `{s['science_claim_promotion_gap_closure_gpcr_claim_promotion_status']}`",
        f"- science_claim_promotion_gap_closure_gpcr_evidence: `{s['science_claim_promotion_gap_closure_gpcr_evidence']}`",
        f"- science_claim_promotion_gap_closure_gpcr_release_blocker: `{s['science_claim_promotion_gap_closure_gpcr_release_blocker']}`",
        f"- science_claim_promotion_gap_closure_openmm_claim_promotion_status: `{s['science_claim_promotion_gap_closure_openmm_claim_promotion_status']}`",
        f"- science_claim_promotion_gap_closure_openmm_evidence: `{s['science_claim_promotion_gap_closure_openmm_evidence']}`",
        f"- science_claim_promotion_gap_closure_openmm_release_blocker: `{s['science_claim_promotion_gap_closure_openmm_release_blocker']}`",
        f"- api_customer_flow_release_evidence_gate_present: `{s['api_customer_flow_release_evidence_gate_present']}`",
        f"- api_customer_flow_release_evidence_status: `{s['api_customer_flow_release_evidence_status']}`",
        f"- api_customer_flow_release_evidence_ready: `{s['api_customer_flow_release_evidence_ready']}`",
        f"- api_customer_flow_result_manifest_signature_verified: `{s['api_customer_flow_result_manifest_signature_verified']}`",
        f"- api_customer_flow_bundle_validation_ready: `{s['api_customer_flow_bundle_validation_ready']}`",
        f"- api_customer_flow_restricted_runtime_ready: `{s['api_customer_flow_restricted_runtime_ready']}`",
        f"- api_customer_flow_blocker_count: `{s['api_customer_flow_blocker_count']}`",
        f"- product_ai_architecture_gate_present: `{s['product_ai_architecture_gate_present']}`",
        f"- product_ai_architecture_ready: `{s['product_ai_architecture_ready']}`",
        f"- product_ai_architecture_open_gap_count: `{s['product_ai_architecture_open_gap_count']}`",
        f"- product_ai_execution_backlog_work_item_count: `{s['product_ai_execution_backlog_work_item_count']}`",
        f"- product_ai_execution_backlog_release_blocking_work_item_count: `{s['product_ai_execution_backlog_release_blocking_work_item_count']}`",
        f"- product_ai_execution_backlog_optional_work_item_count: `{s['product_ai_execution_backlog_optional_work_item_count']}`",
        f"- product_ai_execution_backlog_primary_work_item_id: `{s['product_ai_execution_backlog_primary_work_item_id']}`",
        f"- product_ai_execution_backlog_primary_detail: `{s['product_ai_execution_backlog_primary_detail']}`",
        f"- product_ai_execution_backlog_scope_closure_detail: `{s['product_ai_execution_backlog_scope_closure_detail']}`",
        f"- goal_api_surface_check_count: `{s['goal_api_surface_check_count']}`",
        f"- goal_api_surface_blocker_count: `{s['goal_api_surface_blocker_count']}`",
        f"- operator_action_count: `{s['operator_action_count']}`",
        f"- operator_approval_required_count: `{s['operator_approval_required_count']}`",
        f"- product_cli_status_set_status: `{s['product_cli_status_set_status']}`",
        f"- product_cli_approval_token_count: `{s['product_cli_approval_token_count']}`",
        f"- product_cli_operations_blocked_stage_count: `{s['product_cli_operations_blocked_stage_count']}`",
        f"- product_operational_quality_status: `{s['product_operational_quality_status']}`",
        f"- product_operational_quality_ready: `{s['product_operational_quality_ready']}`",
        f"- product_operational_quality_blocker_count: `{s['product_operational_quality_blocker_count']}`",
        f"- product_cli_architecture_release_ready: `{s['product_cli_architecture_release_ready']}`",
        f"- product_cli_authorized_for_execution: `{s['product_cli_authorized_for_execution']}`",
        f"- product_cli_delivery_ready_claim_allowed: `{s['product_cli_delivery_ready_claim_allowed']}`",
        f"- cameo_cli_status_set_status: `{s['cameo_cli_status_set_status']}`",
        f"- cameo_cli_approval_token_count: `{s['cameo_cli_approval_token_count']}`",
        f"- cameo_cli_official_result_required: `{s['cameo_cli_official_result_required']}`",
        f"- cameo_evidence_integrity_status: `{s['cameo_evidence_integrity_status']}`",
        f"- cameo_evidence_integrity_ready: `{s['cameo_evidence_integrity_ready']}`",
        f"- cameo_evidence_integrity_blocker_count: `{s['cameo_evidence_integrity_blocker_count']}`",
        f"- cameo_official_results_pending_honest: `{s['cameo_official_results_pending_honest']}`",
        f"- cameo_no_local_native_accuracy_substitution: `{s['cameo_no_local_native_accuracy_substitution']}`",
        f"- cameo_cli_receiver_smoke_status: `{s['cameo_cli_receiver_smoke_status']}`",
        f"- cleanup_cli_status_set_status: `{s['cleanup_cli_status_set_status']}`",
        f"- cleanup_cli_approval_token_count: `{s['cleanup_cli_approval_token_count']}`",
        f"- cleanup_cli_approval_reclaim_size_gb: `{s['cleanup_cli_approval_reclaim_size_gb']}`",
        f"- cleanup_cli_postcheck_contract_ready: `{s['cleanup_cli_postcheck_contract_ready']}`",
        f"- cleanup_cli_protected_payload_size_gb: `{s['cleanup_cli_protected_payload_size_gb']}`",
        f"- protected_cleanup_payload_size_gb: `{s['protected_cleanup_payload_size_gb']}`",
        f"- protected_cleanup_known_payload_child_count: `{s['protected_cleanup_known_payload_child_count']}`",
        f"- protected_cleanup_known_payload_child_size_gb: `{s['protected_cleanup_known_payload_child_size_gb']}`",
        f"- protected_cleanup_preservation_sibling_count: `{s['protected_cleanup_preservation_sibling_count']}`",
        f"- cleanup_postcheck_contract_status: `{s['cleanup_postcheck_contract_status']}`",
        f"- cleanup_postcheck_contract_ready: `{s['cleanup_postcheck_contract_ready']}`",
        f"- cleanup_postcheck_row_count: `{s['cleanup_postcheck_row_count']}`",
        f"- cleanup_postcheck_blocked_row_count: `{s['cleanup_postcheck_blocked_row_count']}`",
        f"- cleanup_postcheck_global_refresh_command_count: `{s['cleanup_postcheck_global_refresh_command_count']}`",
        f"- cleanup_completion_gate_status: `{s['cleanup_completion_gate_status']}`",
        f"- cleanup_completion_complete: `{s['cleanup_completion_complete']}`",
        f"- cleanup_completion_blocked_stage_count: `{s['cleanup_completion_blocked_stage_count']}`",
        f"- cleanup_completion_total_reclaim_size_gb: `{s['cleanup_completion_total_reclaim_size_gb']}`",
        f"- cleanup_completion_authorized_reclaim_size_gb: `{s['cleanup_completion_authorized_reclaim_size_gb']}`",
        f"- cleanup_completion_awaiting_approval_count: `{s['cleanup_completion_awaiting_approval_count']}`",
        f"- cleanup_completion_blocked_approval_count: `{s['cleanup_completion_blocked_approval_count']}`",
        f"- cleanup_completion_transition_approval_gated_reclaim_size_gb: `{s['cleanup_completion_transition_approval_gated_reclaim_size_gb']}`",
        f"- cleanup_completion_ligand_heavy_candidate_size_gb: `{s['cleanup_completion_ligand_heavy_candidate_size_gb']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| lane | check | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['check']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` | `{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full-goal release decision gate from current local artifacts.")
    parser.add_argument("--product-pilot-json", default=DEFAULT_PRODUCT_PILOT_JSON)
    parser.add_argument("--product-architecture-json", default=DEFAULT_PRODUCT_ARCHITECTURE_JSON)
    parser.add_argument("--product-commercial-independence-json", default=DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument(
        "--self-hosted-license-distribution-audit-json",
        default=DEFAULT_SELF_HOSTED_LICENSE_DISTRIBUTION_AUDIT_JSON,
    )
    parser.add_argument(
        "--third-party-license-review-gate-json",
        default=DEFAULT_THIRD_PARTY_LICENSE_REVIEW_GATE_JSON,
    )
    parser.add_argument("--cameo-validation-json", default=DEFAULT_CAMEO_VALIDATION_JSON)
    parser.add_argument("--cameo-capability-json", default=DEFAULT_CAMEO_CAPABILITY_JSON)
    parser.add_argument("--cameo-public-registration-approval-gate-json", default=DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON)
    parser.add_argument(
        "--cameo-official-result-fetch-preflight-json",
        default=DEFAULT_CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_JSON,
    )
    parser.add_argument("--goal-rollup-json", default=DEFAULT_GOAL_ROLLUP_JSON)
    parser.add_argument("--operator-action-board-json", default=DEFAULT_OPERATOR_ACTION_BOARD_JSON)
    parser.add_argument("--transition-cleanup-preflight-json", default=DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--ligand-cleanup-preflight-json", default=DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--protected-cleanup-review-json", default=DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON)
    parser.add_argument("--protected-cleanup-policy-decision-gate-json", default=DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON)
    parser.add_argument("--cleanup-postcheck-contract-json", default=DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON)
    parser.add_argument("--cleanup-completion-gate-json", default=DEFAULT_CLEANUP_COMPLETION_GATE_JSON)
    parser.add_argument("--goal-api-surface-contract-json", default=DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON)
    parser.add_argument("--goal-bottleneck-briefing-json", default=DEFAULT_GOAL_BOTTLENECK_BRIEFING_JSON)
    parser.add_argument(
        "--production-ai-registry-promotion-priority-packet-json",
        default=DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_PACKET_JSON,
    )
    parser.add_argument(
        "--product-production-ai-checkpoint-readiness-json",
        default=DEFAULT_PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON,
    )
    parser.add_argument(
        "--product-production-ai-promotion-workbench-json",
        default=DEFAULT_PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_JSON,
    )
    parser.add_argument("--product-ai-architecture-gap-json", default=DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON)
    parser.add_argument("--product-ai-execution-backlog-json", default=DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON)
    parser.add_argument("--product-release-source-of-truth-json", default=DEFAULT_PRODUCT_RELEASE_SOURCE_OF_TRUTH_JSON)
    parser.add_argument(
        "--product-quality-gate-verification-json",
        default=DEFAULT_PRODUCT_QUALITY_GATE_VERIFICATION_JSON,
    )
    parser.add_argument(
        "--product-pose-sampling-readiness-json",
        default=DEFAULT_PRODUCT_POSE_SAMPLING_READINESS_JSON,
    )
    parser.add_argument(
        "--product-ledger-privacy-scan-json",
        default=DEFAULT_PRODUCT_LEDGER_PRIVACY_SCAN_JSON,
    )
    parser.add_argument("--api-customer-flow-release-evidence-json", default=DEFAULT_API_CUSTOMER_FLOW_RELEASE_EVIDENCE_JSON)
    parser.add_argument(
        "--api-runner-profile-promotion-operator-receipt-json",
        default=DEFAULT_API_RUNNER_PROFILE_PROMOTION_OPERATOR_RECEIPT_JSON,
    )
    parser.add_argument(
        "--product-scope-breadth-evidence-receipt-json",
        default=DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON,
    )
    parser.add_argument(
        "--engine-refinement-claim-evidence-receipt-json",
        default=DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_JSON,
    )
    parser.add_argument(
        "--engine-refinement-claim-evidence-priority-packet-json",
        default=DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_JSON,
    )
    parser.add_argument(
        "--refine-tier-public-benchmark-readiness-json",
        default=DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_READINESS_JSON,
    )
    parser.add_argument(
        "--refine-tier-public-benchmark-work-order-apply-json",
        default=DEFAULT_REFINE_TIER_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
    )
    parser.add_argument(
        "--product-full-commercial-blocker-evidence-matrix-json",
        default=DEFAULT_PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_JSON,
    )
    parser.add_argument(
        "--product-rollout-execution-smoke-receipt-json",
        default=DEFAULT_PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_JSON,
    )
    parser.add_argument(
        "--accuracy-parity-scorecard-json",
        default=DEFAULT_ACCURACY_PARITY_SCORECARD_JSON,
    )
    parser.add_argument(
        "--science-claim-promotion-gap-json",
        default=DEFAULT_SCIENCE_CLAIM_PROMOTION_GAP_CLOSURE_JSON,
    )
    parser.add_argument(
        "--master-gap-closure-rollup-json",
        default=DEFAULT_MASTER_GAP_CLOSURE_ROLLUP_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_goal_release_decision_gate(
        product_pilot_packet=_read_json_if_present(args.product_pilot_json),
        product_architecture_packet=_read_json_if_present(args.product_architecture_json),
        product_commercial_independence_packet=_read_json_if_present(args.product_commercial_independence_json),
        self_hosted_license_distribution_audit_packet=_read_json_if_present(
            args.self_hosted_license_distribution_audit_json
        ),
        third_party_license_review_gate_packet=_read_json_if_present(
            args.third_party_license_review_gate_json
        ),
        cameo_validation_packet=_read_json_if_present(args.cameo_validation_json),
        cameo_capability_packet=_read_json_if_present(args.cameo_capability_json),
        cameo_public_registration_approval_gate_packet=_read_json_if_present(args.cameo_public_registration_approval_gate_json),
        cameo_official_result_fetch_preflight_packet=_read_json_if_present(
            args.cameo_official_result_fetch_preflight_json
        ),
        goal_rollup_packet=_read_json_if_present(args.goal_rollup_json),
        operator_action_board_packet=_read_json_if_present(args.operator_action_board_json),
        transition_cleanup_preflight_packet=_read_json_if_present(args.transition_cleanup_preflight_json),
        ligand_cleanup_preflight_packet=_read_json_if_present(args.ligand_cleanup_preflight_json),
        protected_cleanup_review_packet=_read_json_if_present(args.protected_cleanup_review_json),
        protected_cleanup_policy_decision_gate_packet=_read_json_if_present(args.protected_cleanup_policy_decision_gate_json),
        cleanup_postcheck_contract_packet=_read_json_if_present(args.cleanup_postcheck_contract_json),
        cleanup_completion_gate_packet=_read_json_if_present(args.cleanup_completion_gate_json),
        goal_api_surface_contract_packet=_read_json_if_present(args.goal_api_surface_contract_json),
        goal_bottleneck_briefing_packet=_read_json_if_present(args.goal_bottleneck_briefing_json),
        production_ai_registry_promotion_priority_packet=_read_json_if_present(
            args.production_ai_registry_promotion_priority_packet_json
        ),
        product_production_ai_checkpoint_readiness_packet=_read_json_if_present(
            args.product_production_ai_checkpoint_readiness_json
        ),
        product_production_ai_promotion_workbench_packet=_read_json_if_present(
            args.product_production_ai_promotion_workbench_json
        ),
        product_ai_architecture_gap_packet=_read_json_if_present(args.product_ai_architecture_gap_json),
        product_ai_execution_backlog_packet=_read_json_if_present(args.product_ai_execution_backlog_json),
        product_release_source_of_truth_packet=_read_json_if_present(args.product_release_source_of_truth_json),
        product_quality_gate_verification_packet=_read_json_if_present(
            args.product_quality_gate_verification_json
        ),
        product_pose_sampling_readiness_packet=_read_json_if_present(
            args.product_pose_sampling_readiness_json
        ),
        product_ledger_privacy_scan_packet=_read_json_if_present(
            args.product_ledger_privacy_scan_json
        ),
        api_customer_flow_release_evidence_packet=_read_json_if_present(
            args.api_customer_flow_release_evidence_json
        ),
        api_runner_profile_promotion_operator_receipt_packet=_read_json_if_present(
            args.api_runner_profile_promotion_operator_receipt_json
        ),
        product_scope_breadth_evidence_receipt_packet=_read_json_if_present(
            args.product_scope_breadth_evidence_receipt_json
        ),
        engine_refinement_claim_evidence_receipt_packet=_read_json_if_present(
            args.engine_refinement_claim_evidence_receipt_json
        ),
        engine_refinement_claim_evidence_priority_packet=_read_json_if_present(
            args.engine_refinement_claim_evidence_priority_packet_json
        ),
        refine_tier_public_benchmark_readiness_packet=_read_json_if_present(
            args.refine_tier_public_benchmark_readiness_json
        ),
        refine_tier_public_benchmark_work_order_apply_packet=_read_json_if_present(
            args.refine_tier_public_benchmark_work_order_apply_json
        ),
        product_full_commercial_blocker_evidence_matrix_packet=_read_json_if_present(
            args.product_full_commercial_blocker_evidence_matrix_json
        ),
        product_rollout_execution_smoke_receipt_packet=_read_json_if_present(
            args.product_rollout_execution_smoke_receipt_json
        ),
        accuracy_parity_scorecard_packet=_read_json_if_present(
            args.accuracy_parity_scorecard_json
        ),
        science_claim_promotion_gap_packet=_read_json_if_present(
            args.science_claim_promotion_gap_json
        ),
        master_gap_closure_rollup_packet=_read_json_if_present(
            args.master_gap_closure_rollup_json
        ),
        product_pilot_path=args.product_pilot_json,
        product_architecture_path=args.product_architecture_json,
        product_commercial_independence_path=args.product_commercial_independence_json,
        self_hosted_license_distribution_audit_path=args.self_hosted_license_distribution_audit_json,
        third_party_license_review_gate_path=args.third_party_license_review_gate_json,
        cameo_validation_path=args.cameo_validation_json,
        cameo_capability_path=args.cameo_capability_json,
        cameo_public_registration_approval_gate_path=args.cameo_public_registration_approval_gate_json,
        cameo_official_result_fetch_preflight_path=args.cameo_official_result_fetch_preflight_json,
        goal_rollup_path=args.goal_rollup_json,
        operator_action_board_path=args.operator_action_board_json,
        transition_cleanup_preflight_path=args.transition_cleanup_preflight_json,
        ligand_cleanup_preflight_path=args.ligand_cleanup_preflight_json,
        protected_cleanup_review_path=args.protected_cleanup_review_json,
        protected_cleanup_policy_decision_gate_path=args.protected_cleanup_policy_decision_gate_json,
        cleanup_postcheck_contract_path=args.cleanup_postcheck_contract_json,
        cleanup_completion_gate_path=args.cleanup_completion_gate_json,
        goal_api_surface_contract_path=args.goal_api_surface_contract_json,
        goal_bottleneck_briefing_path=args.goal_bottleneck_briefing_json,
        production_ai_registry_promotion_priority_packet_path=(
            args.production_ai_registry_promotion_priority_packet_json
        ),
        product_production_ai_checkpoint_readiness_path=(
            args.product_production_ai_checkpoint_readiness_json
        ),
        product_production_ai_promotion_workbench_path=(
            args.product_production_ai_promotion_workbench_json
        ),
        product_ai_architecture_gap_path=args.product_ai_architecture_gap_json,
        product_ai_execution_backlog_path=args.product_ai_execution_backlog_json,
        product_release_source_of_truth_path=args.product_release_source_of_truth_json,
        product_quality_gate_verification_path=args.product_quality_gate_verification_json,
        product_pose_sampling_readiness_path=args.product_pose_sampling_readiness_json,
        product_ledger_privacy_scan_path=args.product_ledger_privacy_scan_json,
        api_customer_flow_release_evidence_path=args.api_customer_flow_release_evidence_json,
        api_runner_profile_promotion_operator_receipt_path=(
            args.api_runner_profile_promotion_operator_receipt_json
        ),
        product_scope_breadth_evidence_receipt_path=(
            args.product_scope_breadth_evidence_receipt_json
        ),
        engine_refinement_claim_evidence_receipt_path=(
            args.engine_refinement_claim_evidence_receipt_json
        ),
        engine_refinement_claim_evidence_priority_packet_path=(
            args.engine_refinement_claim_evidence_priority_packet_json
        ),
        refine_tier_public_benchmark_readiness_path=(
            args.refine_tier_public_benchmark_readiness_json
        ),
        refine_tier_public_benchmark_work_order_apply_path=(
            args.refine_tier_public_benchmark_work_order_apply_json
        ),
        product_full_commercial_blocker_evidence_matrix_path=(
            args.product_full_commercial_blocker_evidence_matrix_json
        ),
        product_rollout_execution_smoke_receipt_path=(
            args.product_rollout_execution_smoke_receipt_json
        ),
        accuracy_parity_scorecard_path=args.accuracy_parity_scorecard_json,
        science_claim_promotion_gap_path=args.science_claim_promotion_gap_json,
        master_gap_closure_rollup_path=args.master_gap_closure_rollup_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
