from __future__ import annotations

from pathlib import Path

from betelgeuze_cameo.outbound_email_send_preflight import build_outbound_email_send_preflight


def _draft(tmp_path: Path, ready: bool = True) -> dict:
    draft_eml = tmp_path / "draft.eml"
    if ready:
        draft_eml.write_text("Subject: CAMEO\n\nbody\n", encoding="utf-8")
    return {
        "summary": {
            "status": "cameo_outbound_email_draft_ready" if ready else "blocked_cameo_outbound_email_draft",
            "target_id": "CAMEO_TEST_001",
            "sender_email": "operator@example.org",
            "recipient_email": "results@example.org",
            "draft_eml_path": str(draft_eml),
            "draft_eml_written": ready,
            "email_sent": False,
            "smtp_connection_opened": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _registration(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "cameo_public_registration_approval_gate_ready" if ready else "blocked_cameo_public_registration_approval_gate",
            "target_id": "CAMEO_TEST_001",
            "authorized_for_registration_review": ready,
            "server_registration_mutated": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _send_row(**overrides: str) -> dict[str, str]:
    row = {
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
    row.update(overrides)
    return row


def test_outbound_email_send_preflight_blocks_current_missing_operator_row(tmp_path: Path) -> None:
    payload = build_outbound_email_send_preflight(
        draft_packet=_draft(tmp_path),
        registration_approval_packet=_registration(False),
        operator_send_rows=[],
        operator_send_csv_present=False,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_cameo_outbound_email_send_preflight"
    assert summary["draft_ready"] is True
    assert summary["draft_eml_present"] is True
    assert summary["registration_email_approval_ready"] is False
    assert "registration_email_approval_gate_not_ready" in summary["blockers"]
    assert "operator_send_csv_missing" in summary["blockers"]
    assert summary["smtp_connection_opened"] is False
    assert summary["email_sent"] is False
    assert summary["external_state_mutated"] is False


def test_outbound_email_send_preflight_ready_for_separate_operator_send_only(tmp_path: Path) -> None:
    payload = build_outbound_email_send_preflight(
        draft_packet=_draft(tmp_path),
        registration_approval_packet=_registration(True),
        operator_send_rows=[_send_row()],
        operator_send_csv_present=True,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "cameo_outbound_email_send_preflight_ready"
    assert summary["authorized_for_separate_operator_send"] is True
    assert summary["blocker_count"] == 0
    assert summary["smtp_connection_opened"] is False
    assert summary["email_sent"] is False
    assert summary["outbound_email_enabled"] is False
    assert payload["rows"][0]["send_preflight_status"] == "approved_for_separate_operator_send"


def test_outbound_email_send_preflight_blocks_bad_smtp_and_token(tmp_path: Path) -> None:
    payload = build_outbound_email_send_preflight(
        draft_packet=_draft(tmp_path),
        registration_approval_packet=_registration(True),
        operator_send_rows=[
            _send_row(
                outbound_email_approval_token="WRONG",
                smtp_profile_id="",
                smtp_host="https://smtp.example.org",
                smtp_port="70000",
                envelope_sender="bad",
                envelope_recipient="also-bad",
            )
        ],
        operator_send_csv_present=True,
        root=tmp_path,
    )

    blockers = set(payload["summary"]["blockers"])
    assert payload["summary"]["status"] == "blocked_cameo_outbound_email_send_preflight"
    assert "outbound_email_approval_token_mismatch" in blockers
    assert "smtp_profile_id_missing" in blockers
    assert "smtp_host_invalid" in blockers
    assert "smtp_port_invalid" in blockers
    assert "envelope_sender_invalid" in blockers
    assert "envelope_recipient_invalid" in blockers
