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
    assert status["readiness_status"] == "blocked_goal_readiness"
    assert status["operator_action_board_status"] == "operator_actions_required"
    assert status["operator_intake_kit_status"] == "goal_operator_intake_kit_ready"
    assert status["release_decision_status"] == "blocked_goal_release_decision"
    assert status["release_burndown_status"] == "goal_release_burndown_work_order_ready"
    assert status["goal_api_surface_contract_status"] == "goal_api_surface_contract_ready"
    assert status["goal_api_surface_ready"] is True
    assert status["release_allowed"] is False
    assert status["commercial_independent_product_ready"] is False
    assert status["cameo_architecture_validation_ready"] is False
    assert status["cleanup_objective_ready"] is True
    assert status["release_blocker_count"] == 9
    assert status["operator_action_count"] == 3
    assert status["operator_approval_required_count"] == 0
    assert status["operator_intake_kit_release_burndown_linked_entry_count"] == 4
    assert status["operator_template_missing_count"] == 0
    assert status["all_required_templates_present"] is True
    assert status["approval_token_count"] == 4
    assert "APPROVE_PRODUCT_DOCKING_EXECUTION" in status["approval_tokens"]
    assert "APPROVE_CAMEO_SERVER_REGISTRATION" in status["approval_tokens"]
    assert "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS" not in status["approval_tokens"]
    assert status["approval_reclaim_size_gb"] == 0.0
    assert status["protected_cleanup_payload_size_gb"] == 0.0
    assert status["product_cli_status_set_status"] == "blocked_product_cli_status_set"
    assert status["product_cli_approval_token_count"] == 2
    assert status["product_cli_operations_blocked_stage_count"] == 5
    assert status["product_operational_quality_ready"] is True
    assert status["product_operational_quality_status"] == "product_operational_quality_contract_ready"
    assert status["product_operational_quality_blocker_count"] == 0
    assert status["product_cli_authorized_for_execution"] is False
    assert status["product_cli_delivery_ready_claim_allowed"] is False
    assert status["cameo_cli_status_set_status"] == "blocked_cameo_cli_status_set"
    assert status["cameo_cli_approval_token_count"] == 2
    assert status["cameo_cli_official_result_required"] is True
    assert status["cameo_cli_receiver_smoke_status"] == "cameo_receiver_smoke_ready"
    assert status["cameo_evidence_integrity_ready"] is True
    assert status["cameo_evidence_integrity_status"] == "cameo_evidence_integrity_contract_ready"
    assert status["cameo_evidence_integrity_blocker_count"] == 0
    assert status["cameo_official_results_pending_honest"] is True
    assert status["cameo_no_local_native_accuracy_substitution"] is True
    assert status["cleanup_cli_status_set_status"] == "cleanup_cli_status_set_ready"
    assert status["cleanup_cli_approval_token_count"] == 4
    assert status["cleanup_cli_approval_reclaim_size_gb"] == 49.216
    assert status["cleanup_cli_postcheck_contract_ready"] is True
    assert status["cleanup_cli_protected_payload_size_gb"] == 0.0
    assert status["cleanup_cli_protected_policy_change_required_count"] == 0
    assert status["execution_enabled"] is False
    assert status["action_executed"] is False
    assert status["delete_executed"] is False
    assert status["archive_executed"] is False
    assert status["externalize_executed"] is False
    assert status["upload_executed"] is False
    assert status["docking_results_emitted"] is False
    assert status["prediction_generation_enabled"] is False
    assert status["server_registration_mutated"] is False
    assert status["outbound_email_enabled"] is False
    assert status["external_state_mutated"] is False

    assert readiness["status"] == "blocked_goal_readiness"
    assert readiness["lane_count"] == 5
    assert readiness["product_cli_status_set_status"] == "blocked_product_cli_status_set"
    assert readiness["cameo_cli_status_set_status"] == "blocked_cameo_cli_status_set"
    assert readiness["cleanup_cli_status_set_status"] == "cleanup_cli_status_set_ready"
    assert readiness["product_operational_quality_ready"] is True
    assert readiness["cameo_evidence_integrity_ready"] is True
    assert readiness["cameo_no_local_native_accuracy_substitution"] is True
    assert len(readiness["rows"]) == 5
    assert readiness["execution_enabled"] is False
    assert readiness["delete_executed"] is False
    assert readiness["outbound_email_enabled"] is False
    assert readiness["external_state_mutated"] is False

    assert actions["status"] == "operator_actions_required"
    assert actions["action_count"] == 3
    assert actions["goal_release_check_count"] == 15
    assert actions["source_goal_api_surface_contract_status"] == "goal_api_surface_contract_ready"
    assert actions["goal_api_surface_ready"] is True
    assert actions["goal_api_surface_check_count"] == 7
    assert actions["goal_api_surface_blocker_count"] == 0
    assert actions["operator_intake_kit_status"] == "goal_operator_intake_kit_ready"
    assert actions["operator_intake_kit_template_missing_count"] == 0
    assert actions["operator_intake_kit_approval_token_count"] == 4
    assert actions["product_cli_operational_quality_ready"] is True
    assert actions["cameo_cli_evidence_integrity_ready"] is True
    assert len(actions["actions"]) == 3
    assert actions["action_executed"] is False
    assert actions["delete_executed"] is False
    assert actions["external_state_mutated"] is False

    assert intake_kit["status"] == "goal_operator_intake_kit_ready"
    assert intake_kit["entry_count"] == 8
    assert intake_kit["release_burndown_linked_entry_count"] == 4
    assert len(intake_kit["entries"]) == 8
    assert any(entry["kit_entry_id"] == "product_execution" for entry in intake_kit["entries"])
    assert intake_kit["execution_enabled"] is False
    assert intake_kit["delete_executed"] is False
    assert intake_kit["external_state_mutated"] is False

    assert release["status"] == "blocked_goal_release_decision"
    assert release["release_allowed"] is False
    assert release["blocker_count"] == 9
    assert release["check_count"] == 15
    assert release["product_cli_status_set_status"] == "blocked_product_cli_status_set"
    assert release["cameo_cli_status_set_status"] == "blocked_cameo_cli_status_set"
    assert release["cleanup_cli_status_set_status"] == "cleanup_cli_status_set_ready"
    assert release["cleanup_objective_ready"] is True
    assert release["product_operational_quality_ready"] is True
    assert release["cameo_evidence_integrity_ready"] is True
    assert len(release["checks"]) == 15
    assert release["execution_enabled"] is False
    assert release["delete_executed"] is False
    assert release["external_state_mutated"] is False

    assert burndown["status"] == "goal_release_burndown_work_order_ready"
    assert burndown["source_release_allowed"] is False
    assert burndown["work_item_count"] == 5
    assert burndown["approval_token_count"] == 3
    assert burndown["product_operational_quality_ready"] is True
    assert burndown["cameo_evidence_integrity_ready"] is True
    assert len(burndown["work_items"]) == 5
    assert burndown["execution_enabled"] is False
    assert burndown["delete_executed"] is False
    assert burndown["outbound_email_enabled"] is False
    assert burndown["external_state_mutated"] is False

    assert bottlenecks["status"] == "goal_bottleneck_briefing_ready"
    assert bottlenecks["bottleneck_count"] == 5
    assert bottlenecks["primary_bottleneck_kind"] == "operator_action_board_not_clear"
    assert bottlenecks["primary_bottleneck_phase"] == "P1_product_execution_and_bundle_validation"
    assert len(bottlenecks["bottlenecks"]) == 5
    assert bottlenecks["execution_enabled"] is False
    assert bottlenecks["delete_executed"] is False
    assert bottlenecks["outbound_email_enabled"] is False
    assert bottlenecks["external_state_mutated"] is False

    assert api_contract["status"] == "goal_api_surface_contract_ready"
    assert api_contract["surface_ready"] is True
    assert api_contract["check_count"] == 7
    assert api_contract["expected_endpoint_count"] == 8
    assert api_contract["blocker_count"] == 0
    assert len(api_contract["checks"]) == 7
    assert api_contract["execution_enabled"] is False
    assert api_contract["delete_executed"] is False
    assert api_contract["outbound_email_enabled"] is False
    assert api_contract["external_state_mutated"] is False
