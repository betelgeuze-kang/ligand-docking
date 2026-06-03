from __future__ import annotations

from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO validation readiness gate only; it audits local CAMEO benchmark-readiness artifacts. "
    "It does not submit predictions, send email, use local native accuracy, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _blocker(code: str, reason: str, stage: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "stage": stage, "reason": reason}


def _stage_row(stage: str, path: str, packet: dict[str, Any], expected_status_key: str, expected_status: str) -> dict[str, Any]:
    summary = _summary(packet)
    status_value = _text(summary.get(expected_status_key))
    present = bool(packet)
    return {
        "stage": stage,
        "path": path,
        "present": present,
        "status_key": expected_status_key,
        "status_value": status_value,
        "expected_status": expected_status,
        "ready": bool(present and status_value == expected_status),
        "native_or_external_accuracy_used": summary.get("native_or_external_accuracy_used"),
        "native_local_accuracy_used": summary.get("native_local_accuracy_used"),
        "outbound_email_enabled": summary.get("outbound_email_enabled"),
        "external_state_mutated": summary.get("external_state_mutated"),
    }


def _append_stage_blockers(row: dict[str, Any], blockers: list[dict[str, str]]) -> None:
    stage = _text(row.get("stage"))
    if not row.get("present"):
        blockers.append(_blocker(f"{stage}_artifact_missing", f"{stage} artifact is missing.", stage))
        return
    if not row.get("ready"):
        blockers.append(
            _blocker(
                f"{stage}_not_ready",
                f"{stage} status `{row.get('status_value')}` did not match `{row.get('expected_status')}`.",
                stage,
            )
        )
    if row.get("native_or_external_accuracy_used") is not None and row.get("native_or_external_accuracy_used") is not False:
        blockers.append(_blocker(f"{stage}_claim_boundary_invalid", f"{stage} must not use native or external accuracy.", stage))
    if row.get("native_local_accuracy_used") is not None and row.get("native_local_accuracy_used") is not False:
        blockers.append(_blocker(f"{stage}_local_native_accuracy_invalid", f"{stage} must not use local native accuracy.", stage))
    if row.get("outbound_email_enabled") is not None and row.get("outbound_email_enabled") is not False:
        blockers.append(_blocker(f"{stage}_outbound_email_enabled", f"{stage} must keep outbound email disabled.", stage))
    if row.get("external_state_mutated") is not None and row.get("external_state_mutated") is not False:
        blockers.append(_blocker(f"{stage}_external_state_mutated", f"{stage} must not mutate external state.", stage))


def build_cameo_validation_readiness_gate(
    *,
    selection_packet: dict[str, Any],
    format_packet: dict[str, Any],
    handoff_packet: dict[str, Any],
    performance_packet: dict[str, Any],
    selection_path: str = "",
    format_path: str = "",
    handoff_path: str = "",
    performance_path: str = "",
) -> dict[str, Any]:
    rows = [
        _stage_row("selection", selection_path, selection_packet, "selection_status", "cameo_model1_selection_ready"),
        _stage_row("format", format_path, format_packet, "status", "cameo_format_validation_ready"),
        _stage_row("handoff", handoff_path, handoff_packet, "status", "cameo_handoff_dry_run_ready"),
    ]
    performance_summary = _summary(performance_packet)
    performance_status = _text(performance_summary.get("status"))
    performance_present = bool(performance_packet)
    performance_ready = performance_status in {
        "cameo_performance_evidence_ready",
        "cameo_performance_pending_official_results",
    }
    rows.append(
        {
            "stage": "performance",
            "path": performance_path,
            "present": performance_present,
            "status_key": "status",
            "status_value": performance_status,
            "expected_status": "cameo_performance_evidence_ready|cameo_performance_pending_official_results",
            "ready": performance_ready,
            "native_or_external_accuracy_used": performance_summary.get("native_or_external_accuracy_used"),
            "native_local_accuracy_used": performance_summary.get("native_local_accuracy_used"),
            "outbound_email_enabled": performance_summary.get("outbound_email_enabled"),
            "external_state_mutated": performance_summary.get("external_state_mutated"),
        }
    )

    blockers: list[dict[str, str]] = []
    for row in rows:
        _append_stage_blockers(row, blockers)

    target_id = (
        _text(_summary(handoff_packet).get("target_id"))
        or _text(_summary(selection_packet).get("target_id"))
        or _text(_summary(performance_packet).get("target_id"))
    )
    if blockers:
        status = "blocked_cameo_validation_readiness"
    elif performance_status == "cameo_performance_pending_official_results":
        status = "cameo_validation_pending_official_results"
    else:
        status = "cameo_validation_evidence_ready"

    summary = {
        "packet_type": "cameo_validation_readiness_gate",
        "status": status,
        "target_id": target_id,
        "stage_count": len(rows),
        "ready_stage_count": sum(1 for row in rows if row["ready"]),
        "missing_stage_count": sum(1 for row in rows if not row["present"]),
        "blocker_count": len(blockers),
        "performance_status": performance_status,
        "official_cameo_results_used": performance_summary.get("official_cameo_results_used") is True,
        "native_or_external_accuracy_used": False,
        "native_local_accuracy_used": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "CAMEO validation chain is ready with official benchmark evidence."
            if status == "cameo_validation_evidence_ready"
            else (
                "Wait for official CAMEO result rows and regenerate the performance scorecard."
                if status == "cameo_validation_pending_official_results"
                else "Generate or repair missing CAMEO selection, format, handoff, and performance artifacts."
            )
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
