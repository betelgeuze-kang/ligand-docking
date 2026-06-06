from __future__ import annotations

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient


def test_api_app_imports_with_cleanup_router() -> None:
    from api.main import app

    paths = {route.path for route in app.routes}
    assert "/cleanup/operations" in paths
    assert "/cleanup/approval-gate" in paths
    assert "/cleanup/completion" in paths
    assert "/cleanup/postcheck" in paths
    assert "/cleanup/payloads" in paths
    assert "/cleanup/protected-ligand-heavy-review" in paths
    assert "/cleanup/protected-policy" in paths

    client = TestClient(app)
    operations = client.get("/cleanup/operations").json()
    approval = client.get("/cleanup/approval-gate").json()
    completion = client.get("/cleanup/completion").json()
    postcheck = client.get("/cleanup/postcheck").json()
    payloads = client.get("/cleanup/payloads").json()
    deep_review = client.get("/cleanup/protected-ligand-heavy-review").json()
    protected = client.get("/cleanup/protected-policy").json()

    assert operations["status"] == "cleanup_completion_gate_ready"
    assert operations["cleanup_complete"] is True
    assert operations["authorized_row_count"] == 5
    assert operations["awaiting_operator_approval_row_count"] == 0
    assert operations["total_reclaim_size_gb"] == 49.216
    assert operations["protected_payload_size_gb"] == 0.0
    assert operations["postcheck_contract_ready"] is True
    assert operations["postcheck_row_count"] == 5
    assert operations["completion_postcheck_contract_ready"] is True
    assert operations["completion_postcheck_row_count"] == 5
    assert operations["completion_postcheck_blocked_row_count"] == 0
    assert operations["completion_postcheck_global_refresh_command_count"] >= 1
    assert operations["postcheck_global_refresh_command_count"] >= 1
    assert "operator_approval_token" in operations["operator_approval_required_columns"]
    assert operations["operator_approval_valid_decisions"] == ["approve", "skip"]
    assert operations["delete_executed"] is False
    assert operations["external_state_mutated"] is False

    assert approval["status"] == "cleanup_execution_operator_approval_gate_ready"
    assert approval["operator_template_csv"].endswith("runs/cleanup_execution_operator_approval_template_current.csv")
    assert approval["operator_approval_csv"].endswith("runs/cleanup_execution_operator_approval_intake.csv")
    assert "payload_fingerprint_sha256" in approval["required_columns"]
    assert approval["valid_decisions"] == ["approve", "skip"]
    assert "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS" in approval["approval_tokens_required"]
    assert approval["authorized_row_count"] == 5
    assert approval["awaiting_operator_approval_row_count"] == 0
    assert approval["delete_executed"] is False
    assert approval["external_state_mutated"] is False

    assert completion["status"] == "cleanup_completion_gate_ready"
    assert completion["cleanup_complete"] is True
    assert completion["stage_count"] == 5
    assert completion["blocked_stage_count"] == 0
    assert completion["approval_ready"] is True
    assert completion["postcheck_contract_ready"] is True
    assert completion["postcheck_row_count"] == 5
    assert completion["postcheck_blocked_row_count"] == 0
    assert completion["postcheck_global_refresh_command_count"] >= 1
    assert completion["transition_cleanup_complete"] is True
    assert completion["ligand_heavy_cleanup_complete"] is True
    assert completion["protected_policy_resolved"] is True
    assert completion["delete_executed"] is False
    assert completion["external_state_mutated"] is False

    assert postcheck["status"] == "cleanup_postcheck_contract_ready"
    assert postcheck["postcheck_contract_ready"] is True
    assert postcheck["approval_row_count"] == 5
    assert postcheck["protected_policy_row_count"] == 0
    assert postcheck["row_count"] == 5
    assert postcheck["global_refresh_command_count"] >= 1
    assert postcheck["delete_executed"] is False
    assert postcheck["archive_executed"] is False
    assert postcheck["externalize_executed"] is False
    assert postcheck["external_state_mutated"] is False

    assert payloads["status"] == "large_cleanup_surface_drilldown_ready"
    assert payloads["dry_run_delete_payload_row_count"] == 0
    assert payloads["dry_run_delete_payload_size_gb"] == 0.0
    assert payloads["dry_run_protected_payload_size_gb"] == 0.0
    assert payloads["protected_ligand_heavy_deep_review_status"] == "protected_ligand_heavy_payload_deep_review_ready"
    assert payloads["protected_ligand_heavy_known_payload_child_count"] == 0
    assert payloads["protected_ligand_heavy_known_payload_child_size_gb"] == 0.0
    assert payloads["delete_executed"] is False
    assert payloads["external_state_mutated"] is False

    assert deep_review["status"] == "protected_ligand_heavy_payload_deep_review_ready"
    assert deep_review["known_payload_child_count"] == 0
    assert deep_review["known_payload_child_size_gb"] == 0.0
    assert deep_review["preservation_sibling_count"] == 0
    assert deep_review["approval_promoted_count"] == 0
    assert deep_review["delete_executed"] is False
    assert deep_review["external_state_mutated"] is False

    assert protected["status"] == "protected_cleanup_policy_decision_gate_ready"
    assert protected["policy_resolved"] is True
    assert protected["protected_payload_size_gb"] == 0.0
    assert protected["operator_policy_csv_present"] is True
    assert protected["delete_executed"] is False
    assert protected["external_state_mutated"] is False
