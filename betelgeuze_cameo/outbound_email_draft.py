from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from typing import Any

OUTBOUND_EMAIL_APPROVAL_TOKEN = "APPROVE_CAMEO_OUTBOUND_EMAIL"
CLAIM_BOUNDARY = (
    "CAMEO outbound email draft only; it assembles a local RFC 5322 .eml draft from the dry-run handoff attachments. "
    "It does not connect to SMTP, send email, register CAMEO, submit predictions, run prediction generation, or mutate "
    "external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _valid_email(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1] and not any(ch.isspace() for ch in value)


def _safe_subject(value: str) -> str:
    return " ".join(value.split())[:180]


def _attachment_rows(handoff_packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in handoff_packet.get("rows", []) or [] if isinstance(row, dict)]


def build_outbound_email_draft(
    *,
    handoff_packet: dict[str, Any],
    recipient_email: str,
    sender_email: str,
    draft_eml_path: str,
    root: str | Path = ".",
    subject_prefix: str = "CAMEO prediction dry-run",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    summary = handoff_packet.get("summary") if isinstance(handoff_packet.get("summary"), dict) else {}
    rows = _attachment_rows(handoff_packet)
    blockers: list[dict[str, str]] = []

    if summary.get("status") != "cameo_handoff_dry_run_ready":
        blockers.append(_blocker("handoff_packet_not_ready", "CAMEO dry-run handoff must be ready before email draft assembly."))
    if summary.get("outbound_email_enabled") is not False:
        blockers.append(_blocker("handoff_outbound_email_flag_invalid", "Dry-run handoff must keep outbound_email_enabled=false."))
    if not _valid_email(recipient_email):
        blockers.append(_blocker("recipient_email_invalid", "Recipient/results email must be a syntactically valid address for draft review."))
    if not _valid_email(sender_email):
        blockers.append(_blocker("sender_email_invalid", "Sender/contact email must be a syntactically valid address for draft review."))

    ranks = [_int(row.get("cameo_model_rank")) for row in rows]
    if not rows:
        blockers.append(_blocker("no_handoff_attachments", "At least one dry-run handoff attachment is required."))
    if len(rows) > 5:
        blockers.append(_blocker("too_many_handoff_attachments", "CAMEO outbound draft supports at most five ranked model attachments."))
    if ranks.count(1) != 1:
        blockers.append(_blocker("model1_attachment_missing_or_duplicated", "Exactly one model1 attachment is required."))
    if len(ranks) != len(set(ranks)):
        blockers.append(_blocker("duplicate_attachment_rank", "Attachment ranks must be unique."))

    attachment_payloads: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (_int(item.get("cameo_model_rank")), _text(item.get("candidate_id")))):
        model_path_text = _text(row.get("model_path"))
        model_path = Path(model_path_text)
        if not model_path.is_absolute():
            model_path = root_path / model_path
        filename = _text(row.get("attachment_filename")) or model_path.name
        exists = model_path.is_file()
        size = model_path.stat().st_size if exists else 0
        if not exists:
            blockers.append(_blocker("attachment_model_file_missing", f"Attachment source file is missing: {model_path_text}"))
        attachment_payloads.append(
            {
                "target_id": _text(row.get("target_id")),
                "candidate_id": _text(row.get("candidate_id")),
                "cameo_model_rank": _int(row.get("cameo_model_rank")),
                "attachment_filename": filename,
                "model_path": model_path_text,
                "source_file_present": exists,
                "source_size_bytes": size,
                "detected_format": _text(row.get("detected_format")),
            }
        )

    status = "cameo_outbound_email_draft_ready" if not blockers else "blocked_cameo_outbound_email_draft"
    target_id = _text(summary.get("target_id")) or (attachment_payloads[0]["target_id"] if attachment_payloads else "")
    draft_written = False
    draft_size = 0
    if status == "cameo_outbound_email_draft_ready":
        message = EmailMessage()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = _safe_subject(f"{subject_prefix} {target_id}".strip())
        message.set_content(
            "\n".join(
                [
                    "CAMEO prediction draft generated for operator review.",
                    "",
                    f"target_id: {target_id}",
                    f"attachment_count: {len(attachment_payloads)}",
                    "",
                    "This is a local draft. No email was sent by this tool.",
                    "",
                ]
            )
        )
        for attachment in attachment_payloads:
            model_path = Path(attachment["model_path"])
            if not model_path.is_absolute():
                model_path = root_path / model_path
            message.add_attachment(
                model_path.read_bytes(),
                maintype="application",
                subtype="octet-stream",
                filename=attachment["attachment_filename"],
            )
        draft_path = Path(draft_eml_path)
        if not draft_path.is_absolute():
            draft_path = root_path / draft_path
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_bytes(bytes(message))
        draft_written = True
        draft_size = draft_path.stat().st_size

    return {
        "summary": {
            "packet_type": "cameo_outbound_email_draft",
            "status": status,
            "target_id": target_id,
            "recipient_email": recipient_email,
            "sender_email": sender_email,
            "draft_eml_path": draft_eml_path,
            "draft_eml_written": draft_written,
            "draft_eml_size_bytes": draft_size,
            "attachment_count": len(attachment_payloads),
            "model1_attachment_count": sum(1 for row in attachment_payloads if row["cameo_model_rank"] == 1),
            "blocker_count": len(blockers),
            "approval_token_required_for_future_send": OUTBOUND_EMAIL_APPROVAL_TOKEN,
            "outbound_email_enabled": False,
            "email_sent": False,
            "smtp_connection_opened": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": (
                "Operator may inspect the local .eml draft; actual CAMEO result email remains disabled until explicit outbound-email approval and sender wiring."
                if status == "cameo_outbound_email_draft_ready"
                else "Repair handoff, email metadata, or attachment blockers before generating a CAMEO outbound email draft."
            ),
        },
        "blockers": blockers,
        "rows": attachment_payloads,
    }
