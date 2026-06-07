from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from betelgeuze_cameo.outbound_email_draft import build_outbound_email_draft


def _handoff(model_path: Path) -> dict:
    return {
        "summary": {
            "status": "cameo_handoff_dry_run_ready",
            "target_id": "CAMEO_TEST_001",
            "outbound_email_enabled": False,
        },
        "rows": [
            {
                "target_id": "CAMEO_TEST_001",
                "candidate_id": "model1",
                "cameo_model_rank": 1,
                "model_path": str(model_path),
                "attachment_filename": "model_1_model1.pdb",
                "detected_format": "pdb",
            }
        ],
    }


def test_outbound_email_draft_writes_local_eml_without_sending(tmp_path: Path) -> None:
    model = tmp_path / "model1.pdb"
    model.write_text("ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 20.00           C\nEND\n", encoding="utf-8")
    draft = tmp_path / "draft.eml"

    payload = build_outbound_email_draft(
        handoff_packet=_handoff(model),
        recipient_email="results@example.invalid",
        sender_email="operator@example.invalid",
        draft_eml_path=str(draft),
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "cameo_outbound_email_draft_ready"
    assert summary["draft_eml_written"] is True
    assert summary["outbound_email_enabled"] is False
    assert summary["email_sent"] is False
    assert summary["smtp_connection_opened"] is False
    assert summary["external_state_mutated"] is False
    message = BytesParser(policy=default).parsebytes(draft.read_bytes())
    assert message["To"] == "results@example.invalid"
    assert any(part.get_filename() == "model_1_model1.pdb" for part in message.iter_attachments())


def test_outbound_email_draft_blocks_missing_attachment(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdb"
    payload = build_outbound_email_draft(
        handoff_packet=_handoff(missing),
        recipient_email="results@example.invalid",
        sender_email="operator@example.invalid",
        draft_eml_path=str(tmp_path / "draft.eml"),
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_cameo_outbound_email_draft"
    assert payload["summary"]["draft_eml_written"] is False
    assert any(blocker["code"] == "attachment_model_file_missing" for blocker in payload["blockers"])
