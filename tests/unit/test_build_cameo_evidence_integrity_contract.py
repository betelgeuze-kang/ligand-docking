from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cameo.official_results import DISALLOWED_LOCAL_ACCURACY_COLUMNS, METRIC_COLUMNS, REQUIRED_COLUMNS
from tools import build_cameo_evidence_integrity_contract as mod


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_build_cameo_evidence_integrity_contract_tool_writes_outputs(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    architecture = tmp_path / "architecture.json"
    operations = tmp_path / "operations.json"
    registration = tmp_path / "registration.json"
    out_json = tmp_path / "integrity.json"
    out_csv = tmp_path / "integrity.csv"
    out_md = tmp_path / "integrity.md"
    _write_json(
        official,
        {
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
        },
    )
    _write_json(
        architecture,
        {
            "summary": {
                "local_validation_protocol_ready": True,
                "cameo_service_boundary_ready": True,
                "cameo_api_contract_ready": True,
                "official_cameo_results_used": False,
                "native_local_accuracy_used": False,
                "server_registration_mutated": False,
                "prediction_generation_enabled": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            }
        },
    )
    _write_json(
        operations,
        {
            "summary": {
                "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
                "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
                "native_local_accuracy_used": False,
                "server_registration_mutated": False,
                "prediction_generation_enabled": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            }
        },
    )
    _write_json(registration, {"summary": {"status": "blocked_cameo_public_registration_approval_gate", "server_registration_mutated": False}})

    mod.main(
        [
            "--official-results-json",
            str(official),
            "--architecture-validation-json",
            str(architecture),
            "--operations-json",
            str(operations),
            "--registration-json",
            str(registration),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "cameo_evidence_integrity_contract_ready"
    assert payload["summary"]["official_results_pending_honest"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "CAMEO Evidence Integrity Contract" in out_md.read_text(encoding="utf-8")
