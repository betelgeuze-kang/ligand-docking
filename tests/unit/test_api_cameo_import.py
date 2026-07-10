from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.route_compat import route_paths

TestClient = pytest.importorskip("fastapi.testclient").TestClient


def test_api_app_imports_with_cameo_router() -> None:
    from api.main import app

    paths = route_paths(app)
    assert "/cameo/targets" in paths
    assert "/cameo/operations" in paths
    assert "/cameo/architecture-validation" in paths
    assert "/cameo/official-results" in paths
    assert "/cameo/registration-approval" in paths
    assert "/cameo/api-contract" in paths
    assert "/cameo/service-boundary" in paths
    assert "/cameo/evidence-integrity" in paths

    client = TestClient(app)
    operations = client.get("/cameo/operations").json()
    architecture = client.get("/cameo/architecture-validation").json()
    official = client.get("/cameo/official-results").json()
    registration = client.get("/cameo/registration-approval").json()
    api_contract = client.get("/cameo/api-contract").json()
    service_boundary = client.get("/cameo/service-boundary").json()
    evidence_integrity = client.get("/cameo/evidence-integrity").json()

    assert operations["status"] == "blocked_cameo_validation_operations_dossier"
    assert operations["blocked_stage_count"] == 1
    assert operations["approval_required_stage_count"] == 1
    assert operations["first_blocked_stage_id"] == "official_result_fetch_preflight"
    assert operations["first_blocked_stage_source_status"] == "blocked_cameo_official_result_fetch_preflight"
    assert operations["first_blocked_stage_artifact"].endswith("runs/cameo_official_result_fetch_preflight_current.json")
    assert operations["first_blocked_stage_blocker_count"] == 2
    assert operations["first_approval_required_stage_id"] == "public_registration_and_email"
    assert operations["first_approval_required_stage_token_required"] == (
        "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL"
    )
    assert operations["official_results_intake_ready"] is True
    assert operations["official_model1_result_ready"] is True
    assert operations["official_cameo_results_used"] is True
    assert operations["public_registration_allowed"] is True
    assert operations["official_results_operator_template_csv"].endswith("runs/cameo_official_results_operator_template_current.csv")
    assert operations["official_results_operator_intake_csv"].endswith("runs/cameo_official_results_operator_intake.csv")
    assert "target_id" in operations["official_results_required_columns"]
    assert operations["official_results_missing_required_columns"] == []
    assert operations["official_results_blocker_count"] == 0
    assert operations["official_results_blocker_codes"] == []
    assert "lddt" in operations["official_results_metric_columns"]
    assert "native_accuracy" in operations["official_results_disallowed_local_accuracy_columns"]
    assert operations["evidence_integrity_status"] == "cameo_evidence_integrity_contract_ready"
    assert operations["evidence_integrity_ready"] is True
    assert operations["evidence_integrity_blocker_count"] == 0
    assert operations["official_results_pending_honest"] is True
    assert operations["no_local_native_accuracy_substitution"] is True
    assert operations["external_mutation_flags_clear"] is True
    assert operations["registration_operator_template_csv"].endswith("runs/cameo_public_registration_operator_approval_template_current.csv")
    assert "registration_approval_token" in operations["registration_required_columns"]
    assert operations["registration_valid_decisions"] == ["approve", "skip"]
    assert operations["registration_approval_token_required"] == "APPROVE_CAMEO_SERVER_REGISTRATION"
    assert operations["outbound_email_approval_token_required"] == "APPROVE_CAMEO_OUTBOUND_EMAIL"
    assert operations["prediction_generation_enabled"] is False
    assert operations["outbound_email_enabled"] is False
    assert operations["server_registration_mutated"] is False
    assert operations["external_state_mutated"] is False
    assert architecture["status"] == "cameo_architecture_validation_contract_ready"
    assert architecture["cameo_architecture_validation_ready"] is False
    assert architecture["blocked_lane_count"] == 0
    assert architecture["approval_required_lane_count"] == 0
    assert architecture["official_results_gate_status"] == "cameo_official_results_intake_ready"
    assert architecture["official_results_result_row_count"] == 1
    assert architecture["official_results_accepted_count"] == 1
    assert architecture["official_model1_result_ready"] is True
    assert architecture["official_results_operator_template_csv"].endswith("runs/cameo_official_results_operator_template_current.csv")
    assert architecture["official_results_operator_intake_csv"].endswith("runs/cameo_official_results_operator_intake.csv")
    assert "target_id" in architecture["official_results_required_columns"]
    assert architecture["official_results_missing_required_columns"] == []
    assert architecture["official_results_blocker_count"] == 0
    assert architecture["official_results_blocker_codes"] == []
    assert "lddt" in architecture["official_results_metric_columns"]
    assert "native_accuracy" in architecture["official_results_disallowed_local_accuracy_columns"]
    assert architecture["official_cameo_results_used"] is False
    assert architecture["public_registration_authorized"] is False
    assert architecture["server_registration_mutated"] is False
    assert architecture["prediction_generation_enabled"] is False
    assert architecture["outbound_email_enabled"] is False
    assert architecture["native_local_accuracy_used"] is False
    assert architecture["external_state_mutated"] is False
    assert official["status"] == "cameo_official_results_intake_ready"
    assert official["operator_template_csv"].endswith("runs/cameo_official_results_operator_template_current.csv")
    assert official["operator_intake_csv"].endswith("runs/cameo_official_results_operator_intake.csv")
    assert official["result_row_count"] == 1
    assert official["accepted_official_result_count"] == 1
    assert official["rejected_official_result_count"] == 0
    assert official["model1_official_result_ready"] is True
    assert official["blocker_count"] == 0
    assert official["blocker_codes"] == []
    assert "target_id" in official["required_columns"]
    assert official["missing_required_columns"] == []
    assert "lddt" in official["official_metric_columns"]
    assert "native_accuracy" in official["disallowed_local_accuracy_columns"]
    assert official["official_cameo_results_used"] is True
    assert official["native_local_accuracy_used"] is False
    assert official["external_state_mutated"] is False

    assert registration["status"] == "cameo_public_registration_approval_gate_ready"
    assert registration["operator_template_csv"].endswith("runs/cameo_public_registration_operator_approval_template_current.csv")
    assert registration["operator_approval_csv"].endswith("runs/cameo_public_registration_operator_approval_intake.csv")
    assert "public_endpoint_url" in registration["required_columns"]
    assert registration["valid_decisions"] == ["approve", "skip"]
    assert registration["authorized_for_registration_review"] is True
    assert registration["authorized_row_count"] == 1
    assert registration["blocker_count"] == 0
    assert registration["registration_approval_token_required"] == "APPROVE_CAMEO_SERVER_REGISTRATION"
    assert registration["outbound_email_approval_token_required"] == "APPROVE_CAMEO_OUTBOUND_EMAIL"
    assert registration["server_registration_mutated"] is False
    assert registration["outbound_email_enabled"] is False
    assert registration["prediction_generation_enabled"] is False
    assert registration["external_state_mutated"] is False

    assert api_contract["status"] == "cameo_api_contract_ready"
    assert api_contract["api_contract_ready"] is True
    assert api_contract["expected_route_count"] == 9
    assert api_contract["missing_route_count"] == 0
    assert api_contract["status_response_missing_key_count"] == 0
    assert api_contract["server_started"] is False
    assert api_contract["server_registration_mutated"] is False
    assert api_contract["prediction_generation_enabled"] is False
    assert api_contract["outbound_email_enabled"] is False
    assert api_contract["official_results_fetched"] is False
    assert api_contract["native_local_accuracy_used"] is False
    assert api_contract["external_state_mutated"] is False

    assert service_boundary["status"] == "cameo_service_boundary_contract_ready"
    assert service_boundary["service_boundary_ready"] is True
    assert service_boundary["api_route_count"] == 9
    assert service_boundary["expected_api_route_count"] == 9
    assert service_boundary["cli_command_count"] == 16
    assert service_boundary["expected_cli_command_count"] == 14
    assert service_boundary["artifact_registry_mismatch_count"] == 0
    assert service_boundary["console_script_ready"] is True
    assert service_boundary["server_started"] is False
    assert service_boundary["server_registration_mutated"] is False
    assert service_boundary["prediction_generation_enabled"] is False
    assert service_boundary["outbound_email_enabled"] is False
    assert service_boundary["official_results_fetched"] is False
    assert service_boundary["native_local_accuracy_used"] is False
    assert service_boundary["external_state_mutated"] is False

    assert evidence_integrity["status"] == "cameo_evidence_integrity_contract_ready"
    assert evidence_integrity["evidence_integrity_ready"] is True
    assert evidence_integrity["official_results_ready"] is False
    assert evidence_integrity["official_results_pending_honest"] is True
    assert evidence_integrity["official_result_schema_visible"] is True
    assert evidence_integrity["no_local_native_accuracy_substitution"] is True
    assert evidence_integrity["external_mutation_flags_clear"] is True
    assert evidence_integrity["registration_and_email_gated"] is True
    assert evidence_integrity["local_protocol_connected"] is True
    assert evidence_integrity["official_results_fetched"] is False
    assert evidence_integrity["native_local_accuracy_used"] is False
    assert evidence_integrity["external_state_mutated"] is False


def test_cameo_post_intake_persists_fail_closed_record(tmp_path: Path, monkeypatch) -> None:
    from api import cameo
    from api.main import app

    monkeypatch.setattr(cameo.settings, "results_storage_path", str(tmp_path))
    client = TestClient(app)
    response = client.post(
        "/cameo/targets",
        json={
            "target_id": "CAMEO_DRY_RUN_001",
            "results_email": "operator@example.org",
            "sequences": [{"id": "A", "sequence": "ACDEFGHIKLMNPQRSTVWY"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received_fail_closed"
    assert body["parsed_sequence_count"] == 1

    records = list((tmp_path / "cameo_jobs").glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text())
    assert record["target_id"] == "CAMEO_DRY_RUN_001"
    assert record["results_email_redacted"] == "o***@example.org"
    assert record["prediction_generation_enabled"] is False
    assert record["outbound_email_enabled"] is False
