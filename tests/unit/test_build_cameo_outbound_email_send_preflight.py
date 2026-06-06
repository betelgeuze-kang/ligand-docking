from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.cameo import build_cameo_outbound_email_send_preflight as mod


def _draft(tmp_path: Path) -> dict:
    draft_eml = tmp_path / "draft.eml"
    draft_eml.write_text("Subject: CAMEO\n\nbody\n", encoding="utf-8")
    return {
        "summary": {
            "status": "cameo_outbound_email_draft_ready",
            "target_id": "CAMEO_TEST_001",
            "sender_email": "operator@example.org",
            "recipient_email": "results@example.org",
            "draft_eml_path": str(draft_eml),
            "draft_eml_written": True,
            "email_sent": False,
            "smtp_connection_opened": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _registration() -> dict:
    return {
        "summary": {
            "status": "cameo_public_registration_approval_gate_ready",
            "target_id": "CAMEO_TEST_001",
            "authorized_for_registration_review": True,
            "server_registration_mutated": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _send_row() -> dict[str, str]:
    return {
        "target_id": "CAMEO_TEST_001",
        "operator_decision": "approve",
        "outbound_email_approval_token": "APPROVE_CAMEO_OUTBOUND_EMAIL",
        "smtp_profile_id": "operator-reviewed-smtp",
        "smtp_host": "smtp.example.org",
        "smtp_port": "587",
        "envelope_sender": "operator@example.org",
        "envelope_recipient": "results@example.org",
        "operator_note": "reviewed",
    }


def test_cameo_outbound_email_send_preflight_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    draft_json = tmp_path / "draft.json"
    registration_json = tmp_path / "registration.json"
    send_csv = tmp_path / "send.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "send_preflight.json"
    out_csv = tmp_path / "send_preflight.csv"
    out_md = tmp_path / "send_preflight.md"
    draft_json.write_text(json.dumps(_draft(tmp_path)) + "\n", encoding="utf-8")
    registration_json.write_text(json.dumps(_registration()) + "\n", encoding="utf-8")
    with send_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_send_row().keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(_send_row())

    mod.main(
        [
            "--draft-json",
            str(draft_json),
            "--registration-approval-json",
            str(registration_json),
            "--operator-send-csv",
            str(send_csv),
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

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "cameo_outbound_email_send_preflight_ready"
    assert summary["smtp_connection_opened"] is False
    assert summary["email_sent"] is False
    assert template_csv.read_text(encoding="utf-8").startswith("target_id,operator_decision,")
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,send_preflight_status,")
    assert "CAMEO Outbound Email Send Preflight" in out_md.read_text(encoding="utf-8")
