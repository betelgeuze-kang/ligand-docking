from __future__ import annotations

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient


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

    client = TestClient(app)
    status = client.get("/goal/status").json()
    readiness = client.get("/goal/readiness").json()
    actions = client.get("/goal/actions").json()
    intake_kit = client.get("/goal/operator-intake-kit").json()
    release = client.get("/goal/release-decision").json()
    burndown = client.get("/goal/burndown").json()
    bottlenecks = client.get("/goal/bottlenecks").json()
    api_contract = client.get("/goal/api-contract").json()

    assert status["status"] == "blocked_goal_release_decision"
    assert status["release_allowed"] is False
    assert status["release_blocker_count"] == 2
    assert status["release_decision_status"] == "blocked_goal_release_decision"
    assert status["release_burndown_status"] == "goal_release_burndown_work_order_ready"
    assert status["commercial_independent_product_ready"] is True
    assert status["cleanup_objective_ready"] is True
    assert status["readiness_status"] == "blocked_goal_readiness"
    assert status["goal_api_surface_ready"] is True
    assert status["work_item_count"] == 2
    assert status["bottleneck_count"] == 2
    assert status["primary_action_id"] == "product_ai_production:return_gpu_force_regeneration_receipt"
    assert status["primary_action_status"] == "required"
    assert status["primary_action_required_input"] == (
        "GPU full-regeneration summary and manifest with operator verification"
    )
    assert "generate_ligand_trajectory_engine.py" in status["primary_action_command"]
    assert "Run the full regeneration command on a GPU worker" in status["primary_action_recommended_action"]

    assert readiness["status"] == "blocked_goal_readiness"
    assert readiness["blocked_lane_count"] == 1
    assert readiness["operator_approval_pending_count"] == 3
    assert readiness["external_results_pending_count"] == 1
    assert readiness["product_architecture_release_ready"] is True
    assert readiness["product_cli_commercial_independence_ready"] is True
    assert len(readiness["rows"]) == 6

    assert actions["status"] == "operator_actions_required"
    assert actions["action_count"] == 5
    assert actions["approval_required_count"] == 1
    assert actions["review_required_count"] == 1
    assert actions["blocked_or_required_action_count"] == 3
    assert actions["product_cli_authorized_for_execution"] is True
    assert actions["product_cli_delivery_ready_claim_allowed"] is True
    assert actions["cleanup_completion_complete"] is True
    assert actions["cleanup_execution_authorized_reclaim_size_gb"] == 49.216
    assert len(actions["actions"]) == 5

    assert intake_kit["status"] == "goal_operator_intake_kit_ready"
    assert intake_kit["entry_count"] == 12
    assert intake_kit["release_burndown_linked_entry_count"] == 4
    assert intake_kit["operator_input_required_count"] == 7
    assert intake_kit["primary_action_id"] == "product_ai_production:return_gpu_force_regeneration_receipt"
    assert "generate_ligand_trajectory_engine.py" in intake_kit["primary_action_command"]
    assert len(intake_kit["entries"]) == 12

    assert release["status"] == "blocked_goal_release_decision"
    assert release["release_allowed"] is False
    assert release["blocker_count"] == 2
    assert release["check_count"] == 14
    assert release["commercial_independent_product_ready"] is True
    assert release["cleanup_objective_ready"] is True
    assert release["product_commercial_independence_ready"] is True
    assert release["product_architecture_release_ready"] is True
    assert release["product_ai_architecture_ready"] is False
    assert len(release["checks"]) == 14

    assert status["primary_bottleneck_root_cause_category"] == (
        "external_gpu_runtime_and_return_receipt"
    )
    assert status["primary_bottleneck_locally_closable_without_operator_return"] is False
    assert "visible_device_count>0" in status["primary_bottleneck_required_external_return"]

    assert burndown["status"] == "goal_release_burndown_work_order_ready"
    assert burndown["source_release_allowed"] is False
    assert burndown["work_item_count"] == 2
    assert burndown["approval_token_count"] == 0
    assert len(burndown["work_items"]) == 2

    assert bottlenecks["status"] == "goal_bottleneck_briefing_ready"
    assert bottlenecks["release_allowed"] is False
    assert bottlenecks["bottleneck_count"] == 2
    assert bottlenecks["approval_token_count"] == 0
    assert bottlenecks["primary_bottleneck_root_cause_category"] == (
        "external_gpu_runtime_and_return_receipt"
    )
    assert bottlenecks["primary_bottleneck_locally_closable_without_operator_return"] is False
    assert "visible_device_count>0" in bottlenecks["primary_bottleneck_required_external_return"]
    assert bottlenecks["primary_bottleneck_first_acceptance_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert bottlenecks["irreducible_external_return_bottleneck_count"] >= 1
    assert len(bottlenecks["bottlenecks"]) == 2

    assert api_contract["status"] == "goal_api_surface_contract_ready"
    assert api_contract["surface_ready"] is True
    assert api_contract["check_count"] == 8
    assert api_contract["expected_endpoint_count"] == 8
    assert api_contract["blocker_count"] == 0
    assert api_contract["goal_security_allowlist_permits_goal_prefix"] is True
    assert len(api_contract["checks"]) == 8

    for payload in (status, readiness, actions, intake_kit, release, burndown, bottlenecks, api_contract):
        assert payload["execution_enabled"] is False
        assert payload["delete_executed"] is False
        assert payload["external_state_mutated"] is False
