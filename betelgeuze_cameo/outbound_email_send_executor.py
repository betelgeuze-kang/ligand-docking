"""Fail-closed CAMEO outbound email send executor scaffold."""

from __future__ import annotations

from typing import Any

from betelgeuze_cameo.outbound_email_send_preflight import build_outbound_email_send_preflight

CLAIM_BOUNDARY = (
    "CAMEO outbound email send executor scaffold only. Actual SMTP send remains disabled until operator approval "
    "and send preflight are green."
)


def execute_outbound_email_send(
    *,
    draft_packet: dict[str, Any],
    registration_approval_packet: dict[str, Any] | None = None,
    operator_send_rows: list[dict[str, Any]] | None = None,
    operator_send_csv_present: bool = False,
) -> dict[str, Any]:
    preflight = build_outbound_email_send_preflight(
        draft_packet=draft_packet,
        registration_approval_packet=registration_approval_packet or {},
        operator_send_rows=operator_send_rows or [],
        operator_send_csv_present=operator_send_csv_present,
    )
    summary = preflight.get("summary", {}) if isinstance(preflight.get("summary"), dict) else {}
    authorized = summary.get("status") == "cameo_outbound_email_send_ready"
    return {
        "summary": {
            "status": "cameo_outbound_email_send_executor_ready" if authorized else "blocked_cameo_outbound_email_send_executor",
            "executor_ready": True,
            "send_executed": False,
            "smtp_connection_opened": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
            "preflight_status": summary.get("status", ""),
            "authorized_for_send": authorized,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": summary.get(
                "next_required_step",
                "Complete outbound email send preflight and operator approval before actual send.",
            ),
        },
        "preflight": preflight,
    }
