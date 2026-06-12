from __future__ import annotations

import json
from pathlib import Path

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

ROOT = Path(__file__).resolve().parents[2]


def _artifact_summary(name: str) -> dict:
    path = ROOT / "runs" / name
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def test_api_app_imports_with_goal_router() -> None:
    from api.main import app

    paths = {route.path for route in app.routes}
    assert "/goal/status" in paths
    assert "/goal/readiness" in paths
    assert "/goal/actions" in paths
    assert "/goal/operator-intake-kit" in paths
    assert "/goal/release-decision" in paths
    assert "/goal/burndown" in paths
    assert "/goal/bottlenecks" in paths
    assert "/goal/api-contract" in paths

    release_artifact = _artifact_summary("goal_release_decision_gate_current.json")
    readiness_artifact = _artifact_summary("goal_readiness_rollup_current.json")
    burndown_artifact = _artifact_summary("goal_release_burndown_work_order_current.json")
    bottlenecks_artifact = _artifact_summary("goal_bottleneck_briefing_current.json")
    actions_artifact = _artifact_summary("goal_operator_action_board_current.json")
    intake_artifact = _artifact_summary("goal_operator_intake_kit_current/manifest.json")
    api_contract_artifact = _artifact_summary("goal_api_surface_contract_current.json")
    full_matrix_artifact = _artifact_summary(
        "product_full_commercial_blocker_evidence_matrix_current.json"
    )

    client = TestClient(app)
    status = client.get("/goal/status").json()
    readiness = client.get("/goal/readiness").json()
    actions = client.get("/goal/actions").json()
    intake_kit = client.get("/goal/operator-intake-kit").json()
    release = client.get("/goal/release-decision").json()
    burndown = client.get("/goal/burndown").json()
    bottlenecks = client.get("/goal/bottlenecks").json()
    api_contract = client.get("/goal/api-contract").json()

    assert status["status"] == release_artifact.get("status")
    assert status["release_allowed"] is (release_artifact.get("release_allowed") is True)
    assert status["release_blocker_count"] == int(release_artifact.get("blocker_count") or 0)
    assert status["release_decision_status"] == release_artifact.get("status")
    assert status["readiness_status"] == readiness_artifact.get("status")
    assert status["release_burndown_status"] == burndown_artifact.get("status")
    assert status["commercial_independent_product_ready"] is True
    assert status["cleanup_objective_ready"] is True
    assert status["goal_api_surface_ready"] is True
    assert status["bottleneck_count"] == int(bottlenecks_artifact.get("bottleneck_count") or 0)
    primary_source = (
        bottlenecks_artifact
        if int(bottlenecks_artifact.get("current_bottleneck_count") or bottlenecks_artifact.get("bottleneck_count") or 0)
        and bottlenecks_artifact.get("primary_action_id")
        else intake_artifact
    )
    assert status["primary_action_id"] == primary_source.get("primary_action_id")
    assert status["primary_action_status"] == primary_source.get("primary_action_status")
    assert status["primary_action_required_input"] == primary_source.get("primary_action_required_input")
    assert status["primary_action_command"] == primary_source.get("primary_action_command")
    assert status["release_complete_vs_operator_pending_lane"] == readiness_artifact.get(
        "release_complete_vs_operator_pending_lane"
    )
    expected_full_commercial_blockers = [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
    ]
    assert status["expected_full_commercial_release_blocker_ids"] == expected_full_commercial_blockers
    assert status["full_commercial_release_blocker_ids"] == expected_full_commercial_blockers
    assert status["full_commercial_release_blocker_count"] == len(expected_full_commercial_blockers)
    assert status["missing_full_commercial_release_blocker_ids"] == []
    assert status["full_commercial_release_blocker_visibility_ready"] is True
    assert status["completion_audit_release_blocker_bottleneck_count"] == int(
        bottlenecks_artifact.get("completion_audit_release_blocker_bottleneck_count") or 0
    )
    assert status["irreducible_external_return_bottleneck_count"] == int(
        bottlenecks_artifact.get("irreducible_external_return_bottleneck_count") or 0
    )
    assert status["primary_bottleneck_post_return_acceptance_artifact"] == bottlenecks_artifact.get(
        "primary_bottleneck_post_return_acceptance_artifact"
    )
    assert status["commercial_readiness_handoff_bundle_status"] == (
        "product_commercial_readiness_handoff_bundle_ready"
    )
    assert status["commercial_readiness_handoff_bundle_ready"] is True
    assert status["commercial_readiness_handoff_bundle_artifact_reference_count"] == 26
    assert status["commercial_readiness_handoff_bundle_local_missing_artifact_reference_count"] == 0
    assert status["full_commercial_blocker_evidence_matrix_status"] == full_matrix_artifact.get(
        "status"
    )
    assert status["full_commercial_blocker_evidence_matrix_ready"] is (
        full_matrix_artifact.get("full_commercial_blocker_evidence_matrix_ready") is True
    )
    assert status["full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready"] is (
        full_matrix_artifact.get("release_blocker_visibility_ready") is True
    )
    assert status["full_commercial_blocker_evidence_matrix_row_count"] == int(
        full_matrix_artifact.get("matrix_row_count") or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_blocked_row_count"] == int(
        full_matrix_artifact.get("blocked_matrix_row_count") or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_approval_token_count"] == int(
        full_matrix_artifact.get("approval_token_count") or 0
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id"] == (
        full_matrix_artifact.get("first_blocked_release_blocker_id")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id"] == (
        full_matrix_artifact.get("first_blocked_evidence_row_id")
    )
    assert status["full_commercial_blocker_evidence_matrix_first_blocked_acceptance_artifact"] == (
        full_matrix_artifact.get("first_blocked_acceptance_artifact")
    )
    assert status["goal_completion_audit_goal_complete"] == readiness_artifact.get(
        "goal_completion_audit_goal_complete"
    )
    assert status["release_complete_lane_ready"] == readiness_artifact.get("release_complete_lane_ready")
    assert status["operator_pending_lane_ready"] == readiness_artifact.get("operator_pending_lane_ready")

    assert readiness["status"] == readiness_artifact.get("status")
    assert readiness["blocked_lane_count"] == int(readiness_artifact.get("blocked_lane_count") or 0)
    assert readiness["operator_approval_pending_count"] == int(
        readiness_artifact.get("operator_approval_pending_count") or 0
    )
    assert readiness["external_results_pending_count"] == int(
        readiness_artifact.get("external_results_pending_count") or 0
    )
    assert readiness["release_complete_vs_operator_pending_lane"] == readiness_artifact.get(
        "release_complete_vs_operator_pending_lane"
    )
    assert readiness["goal_completion_audit_goal_complete"] is readiness_artifact.get(
        "goal_completion_audit_goal_complete"
    )
    assert readiness["release_complete_lane_ready"] is readiness_artifact.get("release_complete_lane_ready")
    assert readiness["operator_pending_lane_ready"] is False
    assert len(readiness["rows"]) == int(readiness_artifact.get("lane_count") or 0)

    assert actions["status"] == actions_artifact.get("status")
    assert actions["action_count"] == int(actions_artifact.get("action_count") or 0)
    assert len(actions["actions"]) == int(actions_artifact.get("action_count") or 0)

    assert intake_kit["status"] == intake_artifact.get("status")
    assert intake_kit["entry_count"] == int(intake_artifact.get("entry_count") or 0)
    assert len(intake_kit["entries"]) == int(intake_artifact.get("entry_count") or 0)

    assert release["status"] == release_artifact.get("status")
    assert release["release_allowed"] is (release_artifact.get("release_allowed") is True)
    assert release["blocker_count"] == int(release_artifact.get("blocker_count") or 0)
    assert len(release["checks"]) == int(release_artifact.get("check_count") or 0)

    assert burndown["status"] == burndown_artifact.get("status")
    assert burndown["work_item_count"] == int(burndown_artifact.get("work_item_count") or 0)
    assert len(burndown["work_items"]) == int(burndown_artifact.get("work_item_count") or 0)

    assert bottlenecks["status"] == bottlenecks_artifact.get("status")
    assert bottlenecks["bottleneck_count"] == int(bottlenecks_artifact.get("bottleneck_count") or 0)
    assert len(bottlenecks["bottlenecks"]) == int(bottlenecks_artifact.get("bottleneck_count") or 0)

    assert api_contract["status"] == api_contract_artifact.get("status")
    assert api_contract["surface_ready"] is True
    assert api_contract["blocker_count"] == 0

    for payload in (status, readiness, actions, intake_kit, release, burndown, bottlenecks, api_contract):
        assert payload["execution_enabled"] is False
        assert payload["delete_executed"] is False
        assert payload["external_state_mutated"] is False
