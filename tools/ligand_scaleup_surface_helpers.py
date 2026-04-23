from __future__ import annotations

from typing import Any

DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON = "runs/ligand_scaleup_suite_status_current.json"
DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON = "runs/ligand_scaleup_benchmark_summary_current.json"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _value(payload: dict[str, Any], key: str, default: Any = "") -> Any:
    summary = dict(payload.get("summary", {}) or {})
    if key in payload:
        return payload[key]
    if key in summary:
        return summary[key]
    return default


def _slowest_task(payload: dict[str, Any]) -> dict[str, Any]:
    direct = payload.get("slowest_task_at_1m")
    if isinstance(direct, dict) and direct:
        return direct
    kpi_summary = _value(payload, "kpi_summary", {})
    if isinstance(kpi_summary, dict):
        nested = kpi_summary.get("slowest_task_at_1m")
        if isinstance(nested, dict) and nested:
            return nested
    return {}


def summarize_ligand_scaleup_blocker(
    suite_status_payload: dict[str, Any] | None = None,
    benchmark_summary_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    suite_status_payload = dict(suite_status_payload or {})
    benchmark_summary_payload = dict(benchmark_summary_payload or {})
    suite_summary = dict(suite_status_payload.get("summary", {}) or {})
    suite_rows = list(suite_status_payload.get("rows", []) or [])
    slowest_task = _slowest_task(benchmark_summary_payload)

    suite_count = _int(suite_summary.get("suite_count", len(suite_rows)))
    ready_suite_count = _int(suite_summary.get("ready_suite_count", 0))
    comparison_ready_suite_count = _int(suite_summary.get("comparison_ready_suite_count", 0))
    commercialization_ready_suite_count = _int(suite_summary.get("commercialization_ready_suite_count", 0))
    pending_suite_ids = [
        _text(suite_id)
        for suite_id in suite_summary.get("pending_suite_ids", []) or []
        if _text(suite_id)
    ]
    benchmark_stage = _text(_value(benchmark_summary_payload, "benchmark_stage"))
    claim_safe = _value(benchmark_summary_payload, "claim_safe", "")
    claim_safe_status = _text(_value(benchmark_summary_payload, "claim_safe_status"))
    recommended_next_action = _text(_value(benchmark_summary_payload, "recommended_next_action"))

    if not recommended_next_action:
        pending_row = next(
            (
                row
                for row in suite_rows
                if (
                    not bool(row.get("commercialization_ready"))
                    or _text(row.get("claim_safe_status")) in {"", "pending"}
                )
                and _text(row.get("recommended_next_action"))
            ),
            {},
        )
        recommended_next_action = _text(pending_row.get("recommended_next_action"))

    slowest_domain = _text(slowest_task.get("domain"))
    slowest_task_id = _text(slowest_task.get("task_id"))
    slowest_task_projected_1m_wall_hr = slowest_task.get("projected_1m_wall_hr", "")

    blocked = bool(suite_summary or benchmark_summary_payload) and (
        (suite_count > 0 and commercialization_ready_suite_count < suite_count)
        or claim_safe is False
        or claim_safe_status in {
            "pending",
            "regression_guardrail_failed",
            "claim_safe_but_speedup_guardrail_failed",
            "claim_safe_pending_speed_evidence",
        }
    )

    signal_parts = []
    if suite_count:
        signal_parts.extend(
            [
                f"ligand_scaleup_ready={ready_suite_count}/{suite_count}",
                f"ligand_scaleup_comparison_ready={comparison_ready_suite_count}/{suite_count}",
                f"ligand_scaleup_commercialization_ready={commercialization_ready_suite_count}/{suite_count}",
            ]
        )
    if pending_suite_ids:
        signal_parts.append(f"ligand_scaleup_pending_suites={','.join(pending_suite_ids)}")
    if benchmark_stage:
        signal_parts.append(f"ligand_scaleup_benchmark_stage={benchmark_stage}")
    if claim_safe_status:
        signal_parts.append(f"ligand_scaleup_claim_safe_status={claim_safe_status}")
    if slowest_domain:
        signal_parts.append(f"ligand_scaleup_slowest_domain={slowest_domain}")
    if slowest_task_id:
        signal_parts.append(f"ligand_scaleup_slowest_task_id={slowest_task_id}")
    blocker_signal = "; ".join(signal_parts)

    blocker_details = []
    if suite_count:
        blocker_details.append(
            f"{commercialization_ready_suite_count}/{suite_count} ligand scale-up suites are commercialization-ready"
        )
        blocker_details.append(
            f"{comparison_ready_suite_count}/{suite_count} suites are comparison-ready"
        )
    if benchmark_stage:
        stage_note = f"benchmark_stage={benchmark_stage}"
        if claim_safe_status:
            stage_note += f", claim_safe_status={claim_safe_status}"
        blocker_details.append(stage_note)
    elif claim_safe_status:
        blocker_details.append(f"claim_safe_status={claim_safe_status}")
    if slowest_domain and slowest_task_id:
        blocker_details.append(f"{slowest_domain}::{slowest_task_id} remains the slowest 1M pacing task")
    blocker_note = (
        ("Local engine commercialization remains blocked: " if blocked else "Local engine commercialization signal: ")
        + "; ".join(part for part in blocker_details if part)
        + "."
        if blocker_details
        else ""
    )

    next_required_step = ""
    if recommended_next_action or pending_suite_ids:
        action = recommended_next_action or "clear the remaining ligand scale-up suites before claiming commercialization"
        if action and action[-1] not in ".!?":
            action += "."
        pending_clause = (
            f" Pending suites: {', '.join(pending_suite_ids)}."
            if pending_suite_ids
            else ""
        )
        next_required_step = f"For the local engine, {action}{pending_clause}"

    return {
        "ligand_scaleup_blocker_ready": bool(suite_summary or benchmark_summary_payload),
        "ligand_scaleup_blocked": blocked,
        "ligand_scaleup_suite_count": suite_count,
        "ligand_scaleup_ready_suite_count": ready_suite_count,
        "ligand_scaleup_comparison_ready_suite_count": comparison_ready_suite_count,
        "ligand_scaleup_commercialization_ready_suite_count": commercialization_ready_suite_count,
        "ligand_scaleup_pending_suite_ids": pending_suite_ids,
        "ligand_scaleup_benchmark_stage": benchmark_stage,
        "ligand_scaleup_claim_safe": claim_safe,
        "ligand_scaleup_claim_safe_status": claim_safe_status,
        "ligand_scaleup_slowest_domain": slowest_domain,
        "ligand_scaleup_slowest_task_id": slowest_task_id,
        "ligand_scaleup_slowest_task_projected_1m_wall_hr": slowest_task_projected_1m_wall_hr,
        "ligand_scaleup_recommended_next_action": recommended_next_action,
        "ligand_scaleup_blocker_signal": blocker_signal,
        "ligand_scaleup_blocker_note": blocker_note,
        "ligand_scaleup_next_required_step": next_required_step,
    }


def ligand_scaleup_summary_from_source(summary_source: dict[str, Any] | None = None) -> dict[str, Any]:
    summary_source = dict(summary_source or {})
    keys = [
        "ligand_scaleup_blocker_ready",
        "ligand_scaleup_blocked",
        "ligand_scaleup_suite_count",
        "ligand_scaleup_ready_suite_count",
        "ligand_scaleup_comparison_ready_suite_count",
        "ligand_scaleup_commercialization_ready_suite_count",
        "ligand_scaleup_pending_suite_ids",
        "ligand_scaleup_benchmark_stage",
        "ligand_scaleup_claim_safe",
        "ligand_scaleup_claim_safe_status",
        "ligand_scaleup_slowest_domain",
        "ligand_scaleup_slowest_task_id",
        "ligand_scaleup_slowest_task_projected_1m_wall_hr",
        "ligand_scaleup_recommended_next_action",
        "ligand_scaleup_blocker_signal",
        "ligand_scaleup_blocker_note",
        "ligand_scaleup_next_required_step",
    ]
    hydrated = {key: summary_source.get(key, "" if key != "ligand_scaleup_pending_suite_ids" else []) for key in keys}
    hydrated["ligand_scaleup_blocker_ready"] = bool(summary_source.get("ligand_scaleup_blocker_ready", False))
    hydrated["ligand_scaleup_blocked"] = bool(summary_source.get("ligand_scaleup_blocked", False))
    return hydrated
