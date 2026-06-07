from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

FETCH_APPROVAL_TOKEN = "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
FETCH_APPROVAL_DECISION = "approve"
SKIP_DECISION = "skip"
VALID_DECISIONS = {FETCH_APPROVAL_DECISION, SKIP_DECISION}
CLAIM_BOUNDARY = (
    "CAMEO official result fetch preflight only; it validates operator-provided official result URL metadata before a "
    "separate fetch/retrieval step. It does not open network connections, fetch official CAMEO pages, parse remote "
    "content, use local native accuracy, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def build_official_result_fetch_preflight(
    *,
    operations_dossier_packet: dict[str, Any],
    operator_fetch_rows: list[dict[str, Any]],
    operator_fetch_csv_present: bool,
    operator_fetch_csv: str = "",
    template_csv: str = "",
) -> dict[str, Any]:
    operations = _summary(operations_dossier_packet)
    blockers: list[dict[str, str]] = []
    operations_surface_ready = (
        _text(operations.get("status")) in {
            "blocked_cameo_validation_operations_dossier",
            "cameo_validation_operations_dossier_ready",
        }
        and _bool(operations.get("outbound_email_enabled")) is False
        and _bool(operations.get("external_state_mutated")) is False
    )
    receiver_ready = _text(operations.get("receiver_smoke_status")) == "cameo_receiver_smoke_ready"

    if not operations_surface_ready:
        blockers.append(_blocker("operations_dossier_not_ready", "CAMEO operations dossier must exist with clear external mutation flags."))
    if not receiver_ready:
        blockers.append(_blocker("receiver_smoke_not_ready", "Receiver smoke should be ready before official result fetch planning."))
    if not operator_fetch_csv_present:
        blockers.append(_blocker("operator_fetch_csv_missing", "Operator official-result fetch CSV is required."))
    if len(operator_fetch_rows) > 1:
        blockers.append(_blocker("duplicate_operator_fetch_rows", "Exactly zero or one official-result fetch row is expected."))

    row_input = operator_fetch_rows[0] if operator_fetch_rows else {}
    decision = _text(row_input.get("operator_decision")).lower()
    approval_token = _text(row_input.get("fetch_approval_token"))
    target_id = _text(row_input.get("target_id") or operations.get("target_id"))
    result_source_url = _text(row_input.get("result_source_url"))
    result_record_id = _text(row_input.get("result_record_id"))
    expected_candidate_id = _text(row_input.get("expected_candidate_id"))
    expected_model_rank = _text(row_input.get("expected_cameo_model_rank") or "1")
    operator_note = _text(row_input.get("operator_note"))
    row_blockers: list[str] = []

    if not row_input:
        gate_status = "awaiting_operator_fetch_approval"
        row_blockers.append("operator_decision_missing")
    elif decision not in VALID_DECISIONS:
        gate_status = "blocked_before_fetch"
        row_blockers.append("operator_decision_invalid")
    elif decision == SKIP_DECISION:
        gate_status = "skipped_by_operator"
    else:
        gate_status = "approved_for_separate_operator_fetch"
        if approval_token != FETCH_APPROVAL_TOKEN:
            row_blockers.append("fetch_approval_token_mismatch")
        if not target_id:
            row_blockers.append("target_id_missing")
        if not _valid_url(result_source_url):
            row_blockers.append("result_source_url_invalid")
        if not result_record_id:
            row_blockers.append("result_record_id_missing")
        if not expected_candidate_id:
            row_blockers.append("expected_candidate_id_missing")
        if expected_model_rank != "1":
            row_blockers.append("expected_cameo_model_rank_not_model1")
        if row_blockers:
            gate_status = "blocked_before_fetch"

    blockers.extend(_blocker(code, "Operator official-result fetch row is incomplete or invalid.") for code in row_blockers)
    ready = gate_status == "approved_for_separate_operator_fetch" and not blockers
    skipped = gate_status == "skipped_by_operator" and not row_blockers
    status = "cameo_official_result_fetch_preflight_ready" if ready else "blocked_cameo_official_result_fetch_preflight"

    row = {
        "target_id": target_id,
        "fetch_preflight_status": gate_status,
        "operator_decision": decision,
        "fetch_approval_token_required": FETCH_APPROVAL_TOKEN,
        "fetch_approval_token_present": bool(approval_token),
        "result_source_url_present": bool(result_source_url),
        "result_record_id_present": bool(result_record_id),
        "expected_candidate_id_present": bool(expected_candidate_id),
        "expected_cameo_model_rank": expected_model_rank,
        "operator_note_present": bool(operator_note),
        "blockers": ",".join(row_blockers),
        "network_request_opened": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }

    return {
        "summary": {
            "packet_type": "cameo_official_result_fetch_preflight",
            "status": status,
            "source_operations_dossier_status": _text(operations.get("status")),
            "operator_fetch_csv": operator_fetch_csv,
            "operator_fetch_csv_present": bool(operator_fetch_csv_present),
            "operator_template_csv": template_csv,
            "target_id": target_id,
            "operations_surface_ready": operations_surface_ready,
            "receiver_smoke_ready": receiver_ready,
            "authorized_for_separate_operator_fetch": ready,
            "authorized_row_count": 1 if ready else 0,
            "awaiting_operator_fetch_approval_row_count": 1 if gate_status == "awaiting_operator_fetch_approval" else 0,
            "skipped_row_count": 1 if skipped else 0,
            "blocked_row_count": 1 if blockers else 0,
            "blocker_count": len(blockers),
            "blockers": sorted({blocker["code"] for blocker in blockers}),
            "fetch_approval_token_required": FETCH_APPROVAL_TOKEN,
            "network_request_opened": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": (
                "Use the approved metadata only in a separate operator-run fetch/retrieval step, then fill the official-results intake CSV."
                if ready
                else "Fill the operator fetch preflight CSV before any separate official-result retrieval step."
            ),
        },
        "blockers": blockers,
        "rows": [row],
    }
