#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]


def resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def load_json(path_like: str) -> dict[str, Any]:
    with resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def maybe_load_json(path_like: str) -> dict[str, Any]:
    path = resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def queue_status_is_resolved(queue_status: Any) -> bool:
    status = str(queue_status).strip()
    return "result_ready" in status or "explicit_hold" in status


def queue_status_to_execution_state(queue_status: Any) -> str:
    status = str(queue_status).strip()
    if not status:
        return ""
    if status in {"blocked_on_previous_review", "blocked_on_target_content"}:
        return status
    if queue_status_is_resolved(status):
        if "explicit_hold" in status:
            return "explicit_hold"
        return "result_ready"
    if status.startswith("ready"):
        return "ready_to_launch"
    if "running" in status:
        return "running"
    return status


def first_unresolved_row(rows: list[dict[str, Any]], *, status_key: str = "queue_status") -> dict[str, Any] | None:
    for row in rows:
        if not queue_status_is_resolved(row.get(status_key, "")):
            return dict(row)
    return None


def wetlab_run_record_state(run_record: dict[str, Any] | None) -> dict[str, Any]:
    record_summary = dict((run_record or {}).get("summary", {}) or {})
    raw_status = str(record_summary.get("execution_state", record_summary.get("status", ""))).strip()
    explicit_hold = bool(record_summary.get("explicit_hold", False)) or raw_status == "explicit_hold"
    result_review_ready = bool(record_summary.get("result_review_ready", False)) or raw_status in {"completed", "result_ready", "explicit_hold"}
    run_started = bool(record_summary.get("run_started", False)) or raw_status in {"running", "completed", "result_ready", "explicit_hold"}

    if raw_status == "blocked_on_previous_review":
        execution_state = "blocked_on_previous_review"
    elif explicit_hold:
        execution_state = "explicit_hold"
    elif result_review_ready:
        execution_state = "result_ready"
    elif run_started:
        execution_state = "running"
    else:
        execution_state = "ready_to_launch"

    return {
        "summary": record_summary,
        "detected": bool(record_summary),
        "status": raw_status or "not_detected",
        "explicit_hold": explicit_hold,
        "result_review_ready": result_review_ready,
        "run_started": run_started,
        "execution_state": execution_state,
    }


def rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", ""))
    }


def rows_by_track(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("track_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("track_id", ""))
    }


def bulk_repurposing_rows_for_target(payload: dict[str, Any] | None, target_id: str) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in ((payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == str(target_id).strip()
    ]
    return sorted(
        rows,
        key=lambda row: (
            _safe_int(row.get("slot_rank", row.get("rank", 0)), 0),
            str(row.get("compound_name", row.get("preferred_name", ""))).strip().lower(),
        ),
    )


def materialize_repurposing_rows(
    *,
    target_id: str,
    manual_rows: list[dict[str, Any]],
    bulk_autofill_payload: dict[str, Any] | None,
    target_brief_artifact: str,
    first_contact_packet_artifact: str,
    track_label: str,
    default_outreach_track_id: str = "",
) -> tuple[list[dict[str, Any]], bool]:
    bulk_rows = bulk_repurposing_rows_for_target(bulk_autofill_payload, target_id)
    if len(bulk_rows) >= 3:
        materialized: list[dict[str, Any]] = []
        for idx, raw in enumerate(bulk_rows[:3], start=1):
            slot_rank = _safe_int(raw.get("slot_rank", raw.get("rank", idx)), idx)
            row = dict(raw)
            row["target_id"] = target_id
            row["slot_rank"] = slot_rank
            row.setdefault("priority_rank", raw.get("priority_rank", slot_rank))
            row.setdefault("outreach_track_id", default_outreach_track_id)
            row.setdefault("brief_slot_name", f"repurposing_{slot_rank}")
            row.setdefault("seed_status", "bulk_screen_autofill")
            row.setdefault("first_contact_use_mode", "proceed_now" if slot_rank == 1 else "comparator_only")
            row.setdefault("vendor_check_required", False)
            row.setdefault("cost_check_required", False)
            row.setdefault(
                "selectivity_note",
                "Bulk-screen-derived repurposing row; keep target-specific anti-target and condition-aware filters in the first packet.",
            )
            row.setdefault(
                "usage_rationale",
                "Automatically lifted from the broad-screen rerank as one of the current top repurposing rows for this target.",
            )
            row.setdefault(
                "must_not_do",
                "Do not present this as a validated hit before the target-specific wet-lab packet and counterscreens are run.",
            )
            row.setdefault("source_anchor", "broad_screen_repurposing_autofill")
            row.setdefault("source_url", "runs/wetlab_broad_screen_repurposing_autofill_current.md")
            row["target_brief_artifact"] = target_brief_artifact
            row["first_contact_packet_artifact"] = first_contact_packet_artifact
            row["track_label"] = track_label
            row["row_status"] = "bulk_override_ready"
            materialized.append(row)
        return materialized, True

    materialized = []
    for raw in manual_rows:
        row = dict(raw)
        row["target_id"] = target_id
        if default_outreach_track_id and not str(row.get("outreach_track_id", "")).strip():
            row["outreach_track_id"] = default_outreach_track_id
        row["target_brief_artifact"] = target_brief_artifact
        row["first_contact_packet_artifact"] = first_contact_packet_artifact
        row["track_label"] = track_label
        row["row_status"] = "ready"
        materialized.append(row)
    return materialized, False


def payload_summary(status: str, target_id: str, artifact_kind: str, row_count: int, next_required_step: str) -> dict[str, Any]:
    return {
        "status": status,
        "target_id": target_id,
        "artifact_kind": artifact_kind,
        "row_count": row_count,
        "next_required_step": next_required_step,
    }


def write_artifact(md_path_like: str, title: str, payload: dict[str, Any]) -> None:
    md_path = resolve(md_path_like)
    json_path = md_path.with_suffix(".json")
    csv_path = md_path.with_suffix(".csv")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(csv_path, payload.get("rows", []) or [])

    summary = payload.get("summary", {}) or {}
    structured = payload.get("structured", {}) or {}
    rows = payload.get("rows", []) or []
    lines = [f"# {title}", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    if structured:
        lines.extend(["", "## Structured", ""])
        for key, value in structured.items():
            lines.append(f"- {key}: `{value}`")
    if rows:
        headers = list(rows[0].keys())
        lines.extend(["", "## Rows", "", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"])
        for row in rows:
            values = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(values) + " |")
    if summary.get("next_required_step"):
        lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
