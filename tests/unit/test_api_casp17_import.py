from __future__ import annotations

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient


def test_api_app_imports_with_casp17_router() -> None:
    from api.main import app

    paths = {route.path for route in app.routes}
    assert "/casp17/upload" in paths
    assert "/casp17/transition" in paths

    client = TestClient(app)
    upload = client.get("/casp17/upload").json()
    transition = client.get("/casp17/transition").json()

    assert upload["status"] == "current_upload_operator_action_runway_ready_for_human_decisions"
    assert upload["operator_decision_required_count"] == 8
    assert upload["ready_for_runtime_upload_count"] == 0
    assert upload["stale_folder_count"] == 38
    assert upload["stale_readonly_count"] == 38
    assert upload["operator_decision_written"] is False
    assert upload["upload_executed"] is False
    assert upload["native_accuracy_computed"] is False
    assert upload["external_state_mutated"] is False

    assert transition["status"] == "ready_for_operator_fill"
    assert transition["active_competition_scope"] == "casp17_only"
    assert transition["current_upload_operator_decision_required_count"] == 8
    assert transition["current_upload_ready_for_runtime_upload_count"] == 0
    assert transition["stale_generated_folder_count"] == 38
    assert transition["large_cleanup_known_payload_size_gb"] == 0.0
    assert transition["cleanup_execution_approval_gate_status"] == "cleanup_execution_operator_approval_gate_ready"
    assert transition["cleanup_execution_awaiting_operator_approval_row_count"] == 0
    assert transition["cleanup_execution_authorized_reclaim_size_gb"] == 49.216
    assert transition["cleanup_execution_total_reclaim_size_gb"] == 49.216
    assert transition["cleanup_execution_operator_approval_csv_present"] is True
    assert transition["cleanup_postcheck_contract_status"] == "cleanup_postcheck_contract_ready"
    assert transition["cleanup_postcheck_contract_ready"] is True
    assert transition["cleanup_postcheck_row_count"] == 5
    assert transition["cleanup_postcheck_blocked_row_count"] == 0
    assert transition["cleanup_completion_gate_status"] == "cleanup_completion_gate_ready"
    assert transition["cleanup_completion_complete"] is True
    assert transition["cleanup_completion_blocked_stage_count"] == 0
    assert transition["cleanup_completion_approval_ready"] is True
    assert transition["cleanup_completion_transition_cleanup_complete"] is True
    assert transition["cleanup_completion_ligand_heavy_cleanup_complete"] is True
    assert transition["cleanup_completion_protected_policy_resolved"] is True
    assert transition["goal_release_status"] == "blocked_goal_release_decision"
    assert transition["release_allowed"] is False
    assert transition["cleanup_objective_ready"] is True
    assert transition["delete_executed"] is False
    assert transition["upload_executed"] is False
    assert transition["external_state_mutated"] is False
