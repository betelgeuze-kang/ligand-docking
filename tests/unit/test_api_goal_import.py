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
    assert status["primary_action_id"] == intake_artifact.get("primary_action_id")
    assert status["primary_action_status"] == intake_artifact.get("primary_action_status")
    assert status["primary_action_required_input"] == intake_artifact.get("primary_action_required_input")
    assert "generate_ligand_trajectory_engine.py" in status["primary_action_command"]
    assert status["release_complete_vs_operator_pending_lane"] == readiness_artifact.get(
        "release_complete_vs_operator_pending_lane"
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
    assert readiness["goal_completion_audit_goal_complete"] is True
    assert readiness["release_complete_lane_ready"] is True
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
