from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_cameo_public_registration_approval_gate as mod


def _capability(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "cameo_public_registration_preflight_ready" if ready else "blocked_cameo_capability_preflight",
            "public_registration_allowed": ready,
        }
    }


def _operations(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "cameo_validation_operations_dossier_ready" if ready else "blocked_cameo_validation_operations_dossier",
            "target_id": "CAMEO_TARGET",
            "validation_ready": ready,
            "official_cameo_results_used": ready,
            "receiver_smoke_status": "cameo_receiver_smoke_ready" if ready else "blocked_cameo_receiver_smoke",
        }
    }


def _approval_row(**overrides: str) -> dict[str, str]:
    row = {
        "target_id": "CAMEO_TARGET",
        "operator_decision": "approve",
        "registration_approval_token": "APPROVE_CAMEO_SERVER_REGISTRATION",
        "outbound_email_approval_token": "APPROVE_CAMEO_OUTBOUND_EMAIL",
        "public_endpoint_url": "https://example.org/cameo/targets",
        "results_email": "results@example.org",
        "contact_email": "contact@example.org",
    }
    row.update(overrides)
    return row


def test_cameo_public_registration_approval_gate_blocks_current_unready_lane() -> None:
    payload = mod.build_cameo_public_registration_approval_gate(
        capability_packet=_capability(False),
        operations_dossier_packet=_operations(False),
        operator_approval_rows=[],
        operator_approval_csv_present=False,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_cameo_public_registration_approval_gate"
    assert summary["capability_public_registration_ready"] is False
    assert summary["official_cameo_validation_evidence_ready"] is False
    assert summary["receiver_smoke_ready"] is False
    assert summary["operator_approval_csv_present"] is False
    assert "operator_approval_csv_missing" in summary["blockers"]
    assert "operator_decision_missing" in summary["blockers"]
    assert summary["server_registration_mutated"] is False
    assert summary["outbound_email_enabled"] is False


def test_cameo_public_registration_approval_gate_authorizes_only_separate_review() -> None:
    payload = mod.build_cameo_public_registration_approval_gate(
        capability_packet=_capability(True),
        operations_dossier_packet=_operations(True),
        operator_approval_rows=[_approval_row()],
        operator_approval_csv_present=True,
    )

    assert payload["summary"]["status"] == "cameo_public_registration_approval_gate_ready"
    assert payload["summary"]["authorized_for_registration_review"] is True
    assert payload["summary"]["authorized_row_count"] == 1
    assert payload["summary"]["server_registration_mutated"] is False
    assert payload["summary"]["outbound_email_enabled"] is False
    assert payload["rows"][0]["approval_gate_status"] == "approved_for_separate_registration_review"


def test_cameo_public_registration_approval_gate_blocks_bad_metadata_and_tokens() -> None:
    payload = mod.build_cameo_public_registration_approval_gate(
        capability_packet=_capability(True),
        operations_dossier_packet=_operations(True),
        operator_approval_rows=[
            _approval_row(
                registration_approval_token="WRONG",
                outbound_email_approval_token="WRONG",
                public_endpoint_url="localhost:8000",
                results_email="missing-at",
                contact_email="contact",
            )
        ],
        operator_approval_csv_present=True,
    )

    blockers = set(payload["summary"]["blockers"])
    assert payload["summary"]["status"] == "blocked_cameo_public_registration_approval_gate"
    assert "registration_approval_token_mismatch" in blockers
    assert "outbound_email_approval_token_mismatch" in blockers
    assert "public_endpoint_url_invalid" in blockers
    assert "results_email_invalid" in blockers
    assert "contact_email_invalid" in blockers
    assert payload["rows"][0]["approval_gate_status"] == "blocked_before_registration"


def test_cameo_public_registration_approval_gate_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    capability_json = tmp_path / "capability.json"
    operations_json = tmp_path / "operations.json"
    approval_csv = tmp_path / "approval.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    capability_json.write_text(json.dumps(_capability(True)) + "\n", encoding="utf-8")
    operations_json.write_text(json.dumps(_operations(True)) + "\n", encoding="utf-8")
    with approval_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_approval_row().keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(_approval_row())

    mod.main(
        [
            "--capability-json",
            str(capability_json),
            "--operations-dossier-json",
            str(operations_json),
            "--operator-approval-csv",
            str(approval_csv),
            "--template-csv",
            str(template_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_public_registration_approval_gate_ready"
    assert template_csv.read_text(encoding="utf-8").startswith("target_id,operator_decision,")
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,approval_gate_status,")
    assert "CAMEO Public Registration Approval Gate" in out_md.read_text(encoding="utf-8")
