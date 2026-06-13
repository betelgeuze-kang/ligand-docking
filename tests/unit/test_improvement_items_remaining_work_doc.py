from __future__ import annotations

import json
from pathlib import Path

from deploy import product_release_bundle
from tools.product import build_product_release_source_of_truth_gate as source_of_truth


ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "improvement_items_remaining_work.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _summary(path: str) -> dict:
    payload = _payload(path)
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _payload(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_remaining_work_doc_tracks_current_release_metrics() -> None:
    text = _doc_text()
    bundle = product_release_bundle.build_release_bundle(release_id="doc-metric-check")
    refresh = _summary("runs/product_release_current_refresh_plan_current.json")
    action_board = _summary("runs/goal_operator_action_board_current.json")
    command_count = len(source_of_truth.RELEASE_REFRESH_COMMANDS)

    assert f"`artifact_count={bundle['artifact_count']}`" in text
    assert f"`check_count={bundle['check_count']}`" in text
    assert f"`pass_count={bundle['pass_count']}`" in text
    assert f"`product_release_current_refresh_verified`, `command_count={command_count}`" in text
    assert f"`executed_count={command_count}`" in text
    assert f"`release_refresh_command_count={command_count}`" in text
    assert f"`final_gate_count={refresh['final_gate_count']}`" in text
    assert f"`final_gate_blocker_count={refresh['final_gate_blocker_count']}`" in text
    assert (
        f"`goal_release_decision_gate_status={action_board['goal_release_decision_gate_status']}`"
        in text
    )
    assert f"`goal_release_allowed={str(action_board['goal_release_allowed']).lower()}`" in text
    assert f"`goal_release_blocker_count={action_board['goal_release_blocker_count']}`" in text

    assert "`artifact_count=28`" not in text
    assert "`check_count=21`" not in text
    assert "`pass_count=21`" not in text
    assert "`command_count=76`" not in text
    assert "`executed_count=76`" not in text
    assert "`release_refresh_command_count=79`" not in text
    assert "`final_gate_count=2`" not in text


def test_remaining_work_doc_tracks_current_third_party_license_review_gate() -> None:
    text = _doc_text()

    assert "`third_party_license_review_gate_ready`, `expected_review_asset_count=1`" in text
    assert "`review_csv_present=true`, `approved_review_asset_count=1`" in text
    assert "`missing_review_asset_count=0`, `blocker_count=0`" in text

    assert "`blocked_third_party_license_review_gate`" not in text
    assert "`review_csv_present=false`" not in text
    assert "`missing_review_asset_count=1`" not in text


def test_remaining_work_doc_tracks_current_full_commercial_bottleneck_matrix() -> None:
    text = _doc_text()
    matrix = _summary("runs/product_full_commercial_blocker_evidence_matrix_current.json")
    audit = _summary("runs/product_goal_completion_audit_current.json")
    bottleneck = _summary("runs/goal_bottleneck_briefing_current.json")

    assert f"`{matrix['status']}`" in text
    assert f"`release_blocker_visibility_ready={str(matrix['release_blocker_visibility_ready']).lower()}`" in text
    assert f"`matrix_row_count={matrix['matrix_row_count']}`" in text
    assert f"`blocked_matrix_row_count={matrix['blocked_matrix_row_count']}`" in text
    assert f"`approval_token_count={matrix['approval_token_count']}`" in text
    assert f"`release_blocker_fail_count={audit['release_blocker_fail_count']}`" in text
    assert f"`primary_release_blocker_requirement_id={audit['primary_release_blocker_requirement_id']}`" in text
    assert f"`completion_audit_release_blocker_bottleneck_count={bottleneck['completion_audit_release_blocker_bottleneck_count']}`" in text

    assert "`completion_audit_release_blocker_bottleneck_count=3`" not in text


def test_remaining_work_doc_tracks_current_production_ai_priority_bottleneck() -> None:
    text = _doc_text()
    priority = _summary("runs/production_ai_registry_promotion_priority_packet_current.json")

    assert f"`operator_input_required_count={priority['operator_input_required_count']}`" in text
    assert f"`top_gate_id={priority['top_gate_id']}`" in text
    assert f"`{priority['top_gate_id']}`" in text
    assert f"`{priority['top_priority_bucket']}`" in text
    assert "trained/preflight-ready checkpoint는 registry에" in text
    assert "`trained_model_checkpoint_count_positive`는 만족된 gate로 보존된다" in text


def test_remaining_work_doc_tracks_current_enabled_runner_profiles() -> None:
    text = _doc_text()
    payload = _payload("runs/api_runner_profile_enablement_work_order_current.json")
    summary = payload.get("summary", payload)
    enabled_profiles = sorted(
        row["profile_id"]
        for row in payload.get("rows", [])
        if isinstance(row, dict) and row.get("enabled") is True
    )

    assert f"enabled runner profile {summary['enabled_profile_count']}종" in text
    for profile_id in enabled_profiles:
        assert f"`{profile_id}`" in text

    assert "enabled runner profile 2종" not in text
    assert "API runner profile enable + evidence review" in text


def test_remaining_work_doc_tracks_product_readiness_script_entrypoints() -> None:
    text = _doc_text()

    assert "`scripts/check_independent_product_readiness.py`" in text
    assert "`independent_product_readiness_verified`" in text
    assert "`independent_restricted_product_ready=true`" in text
    assert "`full_commercial_claim_promotion_ready=false`" in text
    assert "`full_commercial_open_gap_ids=[SCI-GPCR, SCI-OPENMM]`" in text
    assert "`scripts/verify_quality_gate.py`" in text
    assert "`product_quality_gate_verified`" in text
    assert "`quality_gate_ready=true`" in text
