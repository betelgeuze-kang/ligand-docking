from __future__ import annotations

from pathlib import Path
from typing import Any

OUTBOUND_EMAIL_APPROVAL_TOKEN = "APPROVE_CAMEO_OUTBOUND_EMAIL"
SEND_APPROVAL_DECISION = "approve"
SKIP_DECISION = "skip"
VALID_DECISIONS = {SEND_APPROVAL_DECISION, SKIP_DECISION}
CLAIM_BOUNDARY = (
    "CAMEO outbound email send preflight only; it validates local draft, approval, and SMTP metadata before a "
    "separate operator-run send step. It does not connect to SMTP, send email, register CAMEO, submit predictions, "
    "run prediction generation, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _valid_email(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1] and not any(ch.isspace() for ch in value)


def _valid_host(value: str) -> bool:
    return bool(value) and "://" not in value and not any(ch.isspace() for ch in value)


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _resolve(root: str | Path, path_like: str) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else Path(root).resolve() / path


def build_outbound_email_send_preflight(
    *,
    draft_packet: dict[str, Any],
    registration_approval_packet: dict[str, Any],
    operator_send_rows: list[dict[str, Any]],
    operator_send_csv_present: bool,
    root: str | Path = ".",
    operator_send_csv: str = "",
    template_csv: str = "",
) -> dict[str, Any]:
    draft = _summary(draft_packet)
    registration = _summary(registration_approval_packet)
    blockers: list[dict[str, str]] = []

    draft_ready = (
        _text(draft.get("status")) == "cameo_outbound_email_draft_ready"
        and _bool(draft.get("draft_eml_written"))
        and not _bool(draft.get("email_sent"))
        and not _bool(draft.get("smtp_connection_opened"))
        and not _bool(draft.get("outbound_email_enabled"))
        and not _bool(draft.get("external_state_mutated"))
    )
    draft_eml_path = _text(draft.get("draft_eml_path"))
    draft_eml_present = bool(draft_eml_path and _resolve(root, draft_eml_path).is_file())
    registration_ready = (
        _text(registration.get("status")) == "cameo_public_registration_approval_gate_ready"
        and _bool(registration.get("authorized_for_registration_review"))
        and not _bool(registration.get("server_registration_mutated"))
        and not _bool(registration.get("outbound_email_enabled"))
        and not _bool(registration.get("external_state_mutated"))
    )

    if not draft_ready:
        blockers.append(_blocker("outbound_email_draft_not_ready", "CAMEO outbound .eml draft must be ready and unsent."))
    if not draft_eml_present:
        blockers.append(_blocker("draft_eml_file_missing", "The local .eml draft file referenced by the draft packet must exist."))
    if not registration_ready:
        blockers.append(
            _blocker(
                "registration_email_approval_gate_not_ready",
                "Public registration/outbound-email approval gate must be ready before send preflight can pass.",
            )
        )
    if not operator_send_csv_present:
        blockers.append(_blocker("operator_send_csv_missing", "Operator send approval CSV is required for SMTP preflight."))
    if len(operator_send_rows) > 1:
        blockers.append(_blocker("duplicate_operator_send_rows", "Exactly zero or one operator send approval row is expected."))

    row_input = operator_send_rows[0] if operator_send_rows else {}
    decision = _text(row_input.get("operator_decision")).lower()
    approval_token = _text(row_input.get("outbound_email_approval_token"))
    smtp_host = _text(row_input.get("smtp_host"))
    smtp_port = _int(row_input.get("smtp_port"))
    smtp_profile_id = _text(row_input.get("smtp_profile_id"))
    envelope_sender = _text(row_input.get("envelope_sender") or draft.get("sender_email"))
    envelope_recipient = _text(row_input.get("envelope_recipient") or draft.get("recipient_email"))
    operator_note = _text(row_input.get("operator_note"))
    row_blockers: list[str] = []

    if not row_input:
        gate_status = "awaiting_operator_send_approval"
        row_blockers.append("operator_decision_missing")
    elif decision not in VALID_DECISIONS:
        gate_status = "blocked_before_send"
        row_blockers.append("operator_decision_invalid")
    elif decision == SKIP_DECISION:
        gate_status = "skipped_by_operator"
    else:
        gate_status = "approved_for_separate_operator_send"
        if approval_token != OUTBOUND_EMAIL_APPROVAL_TOKEN:
            row_blockers.append("outbound_email_approval_token_mismatch")
        if not smtp_profile_id:
            row_blockers.append("smtp_profile_id_missing")
        if not _valid_host(smtp_host):
            row_blockers.append("smtp_host_invalid")
        if smtp_port <= 0 or smtp_port > 65535:
            row_blockers.append("smtp_port_invalid")
        if not _valid_email(envelope_sender):
            row_blockers.append("envelope_sender_invalid")
        if not _valid_email(envelope_recipient):
            row_blockers.append("envelope_recipient_invalid")
        if row_blockers:
            gate_status = "blocked_before_send"

    blockers.extend(_blocker(code, "Operator send approval row is incomplete or invalid.") for code in row_blockers)
    ready = gate_status == "approved_for_separate_operator_send" and not blockers
    skipped = gate_status == "skipped_by_operator" and not row_blockers
    status = "cameo_outbound_email_send_preflight_ready" if ready else "blocked_cameo_outbound_email_send_preflight"

    row = {
        "target_id": _text(draft.get("target_id") or registration.get("target_id")),
        "send_preflight_status": gate_status,
        "operator_decision": decision,
        "outbound_email_approval_token_required": OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "outbound_email_approval_token_present": bool(approval_token),
        "smtp_profile_id_present": bool(smtp_profile_id),
        "smtp_host_present": bool(smtp_host),
        "smtp_port": smtp_port,
        "envelope_sender_present": bool(envelope_sender),
        "envelope_recipient_present": bool(envelope_recipient),
        "operator_note_present": bool(operator_note),
        "blockers": ",".join(row_blockers),
        "smtp_connection_opened": False,
        "email_sent": False,
        "outbound_email_enabled": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "external_state_mutated": False,
    }

    return {
        "summary": {
            "packet_type": "cameo_outbound_email_send_preflight",
            "status": status,
            "source_draft_status": _text(draft.get("status")),
            "source_registration_approval_status": _text(registration.get("status")),
            "operator_send_csv": operator_send_csv,
            "operator_send_csv_present": bool(operator_send_csv_present),
            "operator_template_csv": template_csv,
            "target_id": row["target_id"],
            "draft_ready": draft_ready,
            "draft_eml_path": draft_eml_path,
            "draft_eml_present": draft_eml_present,
            "registration_email_approval_ready": registration_ready,
            "authorized_for_separate_operator_send": ready,
            "authorized_row_count": 1 if ready else 0,
            "awaiting_operator_send_approval_row_count": 1 if gate_status == "awaiting_operator_send_approval" else 0,
            "skipped_row_count": 1 if skipped else 0,
            "blocked_row_count": 1 if blockers else 0,
            "blocker_count": len(blockers),
            "blockers": sorted({blocker["code"] for blocker in blockers}),
            "outbound_email_approval_token_required": OUTBOUND_EMAIL_APPROVAL_TOKEN,
            "smtp_connection_opened": False,
            "email_sent": False,
            "outbound_email_enabled": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": (
                "Use the approved metadata only in a separate operator-run send step; this preflight intentionally sent no email."
                if ready
                else "Fill the operator send approval CSV after registration/email approval, then rerun this preflight before any separate send step."
            ),
        },
        "blockers": blockers,
        "rows": [row],
    }
