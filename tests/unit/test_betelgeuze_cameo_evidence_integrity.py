from __future__ import annotations

from betelgeuze_cameo.evidence_integrity import build_cameo_evidence_integrity_contract
from betelgeuze_cameo.official_results import DISALLOWED_LOCAL_ACCURACY_COLUMNS, METRIC_COLUMNS, REQUIRED_COLUMNS


def _official_pending() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_official_results_intake",
            "accepted_official_result_count": 0,
            "model1_official_result_ready": False,
            "blocker_codes": ["official_result_rows_missing"],
            "operator_template_csv": "runs/cameo_official_results_operator_template_current.csv",
            "operator_intake_csv": "runs/cameo_official_results_operator_intake.csv",
            "required_columns": list(REQUIRED_COLUMNS),
            "official_metric_columns": list(METRIC_COLUMNS),
            "disallowed_local_accuracy_columns": list(DISALLOWED_LOCAL_ACCURACY_COLUMNS),
            "missing_required_columns": list(REQUIRED_COLUMNS),
            "native_local_accuracy_used": False,
            "official_results_fetched": False,
            "external_state_mutated": False,
        }
    }


def _architecture(official_used: bool = False) -> dict:
    return {
        "summary": {
            "local_validation_protocol_ready": True,
            "cameo_service_boundary_ready": True,
            "cameo_api_contract_ready": True,
            "official_cameo_results_used": official_used,
            "native_local_accuracy_used": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _operations() -> dict:
    return {
        "summary": {
            "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
            "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
            "native_local_accuracy_used": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _registration() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_public_registration_approval_gate",
            "server_registration_mutated": False,
            "external_state_mutated": False,
        }
    }


def test_cameo_evidence_integrity_ready_when_official_results_are_honestly_pending() -> None:
    payload = build_cameo_evidence_integrity_contract(
        official_results_packet=_official_pending(),
        architecture_validation_packet=_architecture(),
        operations_packet=_operations(),
        registration_packet=_registration(),
    )
    summary = payload["summary"]

    assert summary["status"] == "cameo_evidence_integrity_contract_ready"
    assert summary["evidence_integrity_ready"] is True
    assert summary["official_results_ready"] is False
    assert summary["official_results_pending_honest"] is True
    assert summary["official_result_schema_visible"] is True
    assert summary["no_local_native_accuracy_substitution"] is True
    assert summary["external_mutation_flags_clear"] is True
    assert summary["registration_and_email_gated"] is True
    assert summary["local_protocol_connected"] is True
    assert summary["official_results_fetched"] is False
    assert summary["native_local_accuracy_used"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_cameo_evidence_integrity_blocks_pretend_official_usage() -> None:
    payload = build_cameo_evidence_integrity_contract(
        official_results_packet=_official_pending(),
        architecture_validation_packet=_architecture(official_used=True),
        operations_packet=_operations(),
        registration_packet=_registration(),
    )

    assert payload["summary"]["status"] == "blocked_cameo_evidence_integrity_contract"
    assert any(blocker["code"] == "no_local_native_accuracy_substitution_not_ready" for blocker in payload["blockers"])
