from __future__ import annotations

import shlex
from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO repair execution preflight only; it validates local artifact rebuild commands and checked operator inputs. "
    "It does not run CAMEO artifact builders, run predictions, submit targets, send email, use local native accuracy, "
    "or mutate external state."
)
READY_INPUT_STATUSES = {
    "cameo_operator_inputs_ready_pending_official_results",
    "cameo_operator_inputs_ready_with_official_results",
}
READY_REPAIR_STATUS = "cameo_validation_repair_work_order_ready"
NOT_REQUIRED_REPAIR_STATUS = "cameo_validation_repair_not_required"
ACCEPTABLE_REPAIR_STATUSES = {READY_REPAIR_STATUS, NOT_REQUIRED_REPAIR_STATUS}
ALLOWED_STEP_ENTRYPOINTS = {
    "selection": "tools/build_cameo_model1_selection_packet.py",
    "format": "tools/build_cameo_format_validation_packet.py",
    "handoff": "tools/build_cameo_dry_run_handoff_packet.py",
    "performance": "tools/build_cameo_performance_scorecard.py",
    "readiness_refresh": "tools/build_cameo_validation_readiness_gate.py",
}


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


def _blocker(code: str, reason: str, *, step: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "hard", "reason": reason}
    if step:
        payload["step"] = step
    return payload


def _parts(command: Any) -> list[str]:
    if isinstance(command, list):
        return [_text(part) for part in command if _text(part)]
    text = _text(command)
    return shlex.split(text) if text else []


def _contains_placeholder(value: Any) -> bool:
    return "OPERATOR_FILL" in _text(value)


def _entrypoint_seen(parts: list[str], entrypoint: str) -> bool:
    return any(part.replace("\\", "/") == entrypoint or part.replace("\\", "/").endswith(f"/{entrypoint}") for part in parts)


def _has_flag(parts: list[str], flag: str) -> bool:
    return flag in parts


def _step_command_blockers(row: dict[str, Any]) -> list[str]:
    step = _text(row.get("step"))
    command = _text(row.get("command"))
    parts = _parts(command)
    blockers: list[str] = []
    entrypoint = ALLOWED_STEP_ENTRYPOINTS.get(step)
    if not command:
        blockers.append("command_missing")
    elif entrypoint and not _entrypoint_seen(parts, entrypoint):
        blockers.append("command_entrypoint_unrecognized")
    if _contains_placeholder(command) or _contains_placeholder(row.get("input_value")):
        blockers.append("operator_placeholder_present")
    if row.get("action_executed") is not False:
        blockers.append("row_action_executed_invalid")
    if step == "selection" and not _has_flag(parts, "--candidates-csv"):
        blockers.append("selection_candidates_csv_missing")
    if step == "format" and not _has_flag(parts, "--models-csv"):
        blockers.append("format_models_csv_missing")
    if step == "performance" and _text(row.get("input_value")) and not _has_flag(parts, "--results-csv"):
        blockers.append("performance_results_csv_missing")
    if step not in ALLOWED_STEP_ENTRYPOINTS:
        blockers.append("unknown_repair_step")
    return blockers


def build_repair_execution_preflight(repair_work_order: dict[str, Any], operator_input_validation: dict[str, Any]) -> dict[str, Any]:
    repair_summary = _summary(repair_work_order)
    input_summary = _summary(operator_input_validation)
    repair_rows = [row for row in repair_work_order.get("rows", []) or [] if isinstance(row, dict)]
    blockers: list[dict[str, str]] = []

    repair_status = _text(repair_summary.get("status"))
    input_status = _text(input_summary.get("status"))
    if repair_status not in ACCEPTABLE_REPAIR_STATUSES:
        blockers.append(
            _blocker(
                "repair_work_order_not_ready",
                (
                    f"Repair work order must be {READY_REPAIR_STATUS} or {NOT_REQUIRED_REPAIR_STATUS}; "
                    f"current status is {repair_status or 'missing'}."
                ),
            )
        )
    if input_status not in READY_INPUT_STATUSES:
        blockers.append(
            _blocker(
                "operator_inputs_not_ready",
                "Operator input validation must pass before local CAMEO artifact rebuild commands can run.",
            )
        )
    for flag_name in ("action_executed", "outbound_email_enabled", "external_state_mutated", "native_local_accuracy_used"):
        if repair_summary.get(flag_name) is not False:
            blockers.append(_blocker(f"repair_{flag_name}_invalid", f"Repair work order must keep {flag_name}=false."))
        if input_summary.get(flag_name) is not False:
            blockers.append(_blocker(f"input_{flag_name}_invalid", f"Operator input validation must keep {flag_name}=false."))
    if not repair_rows and repair_status != NOT_REQUIRED_REPAIR_STATUS:
        blockers.append(_blocker("repair_rows_missing", "Repair work order must include local artifact-build command rows."))

    row_checks: list[dict[str, Any]] = []
    for row in repair_rows:
        step = _text(row.get("step"))
        row_blockers = _step_command_blockers(row)
        for code in row_blockers:
            blockers.append(_blocker("repair_command_row_blocked", f"Repair command row failed preflight: {code}", step=step))
        row_checks.append(
            {
                "step": step,
                "needed_now": bool(row.get("needed_now", False)),
                "input_required": _text(row.get("input_required")),
                "input_value": _text(row.get("input_value")),
                "command": _text(row.get("command")),
                "preflight_status": "fail" if row_blockers else "pass",
                "blockers": ",".join(row_blockers),
                "action_executed": False,
            }
        )

    if blockers:
        status = "blocked_cameo_repair_execution_preflight"
    elif repair_status == NOT_REQUIRED_REPAIR_STATUS:
        status = "cameo_repair_execution_not_required"
    else:
        status = "cameo_repair_execution_preflight_ready"
    summary = {
        "packet_type": "cameo_repair_execution_preflight",
        "status": status,
        "source_repair_status": repair_status,
        "source_operator_input_validation_status": input_status,
        "command_count": len(repair_rows),
        "blocker_count": len(blockers),
        "input_blocker_count": _int(input_summary.get("blocker_count")),
        "action_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "native_local_accuracy_used": False,
        "validated_without_execution": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the local CAMEO artifact rebuild commands in order, then refresh CAMEO validation readiness."
            if status == "cameo_repair_execution_preflight_ready"
            else (
                "No local CAMEO repair execution is required for the current readiness state."
                if status == "cameo_repair_execution_not_required"
                else "Fill/validate CAMEO operator inputs and regenerate the repair work order with real CSV paths before running rebuild commands."
            )
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": row_checks}
