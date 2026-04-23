#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, resolve, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_JSON = "runs/wetlab_broad_screen_bulk_result_source_schema_current.json"
DEFAULT_SOURCE_MD = "runs/wetlab_broad_screen_bulk_results_source_current.md"
DEFAULT_ROWS_JSON = "runs/wetlab_broad_screen_bulk_result_row_examples_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_actual_append_current.md"
DEFAULT_BATCH_MD = "runs/wetlab_broad_screen_actual_append_batch_current.md"
DEFAULT_MERGE_SCRIPT = "tools/build_wetlab_broad_screen_bulk_results_source_merge.py"
DEFAULT_MINIMAL_FOLLOWUP_SCRIPTS = [
    "tools/build_wetlab_broad_screen_bulk_results.py",
    "tools/build_wetlab_broad_screen_repurposing_autofill.py",
    "tools/build_wetlab_priority3_repurposing_fill_map.py",
    "tools/build_wetlab_next3_repurposing_fill_map.py",
    "tools/build_wetlab_stk17b_repurposing_fill_map.py",
    "tools/build_wetlab_lbdhodh_repurposing_fill_map.py",
    "tools/build_wetlab_cathepsin_k_repurposing_fill_map.py",
    "tools/build_wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map.py",
    "tools/build_wetlab_dpre1_repurposing_fill_map.py",
    "tools/build_wetlab_tcruzi_krs1_repurposing_fill_map.py",
    "tools/build_wetlab_lrrk2_repurposing_fill_map.py",
    "tools/build_wetlab_broad_screen_target_rerank.py",
    "tools/build_wetlab_broad_screen_stability_score.py",
    "tools/build_wetlab_broad_screen_antitarget_queue.py",
    "tools/build_wetlab_broad_screen_antitarget_execution_queue.py",
    "tools/build_wetlab_broad_screen_antitarget_runtime_runbook.py",
    "tools/build_wetlab_broad_screen_next_target_extension.py",
    "tools/build_wetlab_broad_screen_precision_monitor.py",
]
DEFAULT_FULL_FOLLOWUP_SCRIPTS = [
    *DEFAULT_MINIMAL_FOLLOWUP_SCRIPTS,
    "tools/build_wetlab_engineering_progress.py",
    "tools/build_wetlab_final_campaign_summary.py",
    "tools/build_wetlab_master_handoff_dashboard.py",
    "tools/build_wetlab_partnering_stack.py",
]


def _read_rows_payload(path_like: str) -> dict[str, Any]:
    path = resolve(path_like)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if isinstance(payload, list):
        return {"rows": payload}
    if isinstance(payload, dict):
        return payload
    raise TypeError(f"unsupported rows payload: {type(payload)!r}")


def _batch_json_path(batch_md: str) -> str:
    return str(resolve(batch_md).with_suffix(".json"))


def _load_batch_payload(batch_md: str) -> dict[str, Any]:
    return maybe_load_json(_batch_json_path(batch_md))


def validate_rows_payload(payload: dict[str, Any], schema_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    schema_rows = (schema_payload or {}).get("rows", []) or []
    required_fields = [
        str(row.get("field_name", "")).strip()
        for row in schema_rows
        if bool(row.get("required", False)) and str(row.get("field_name", "")).strip()
    ] or ["target_id", "compound_name", "bulk_rank", "bulk_score"]

    rows = [dict(row) for row in (payload.get("rows", []) or [])]
    missing_fields: list[str] = []
    for row in rows:
        for field in required_fields:
            if row.get(field, "") in {"", None}:
                missing_fields.append(field)
    return {
        "row_count": len(rows),
        "required_fields": required_fields,
        "missing_field_count": len(missing_fields),
        "is_valid": len(rows) > 0 and not missing_fields,
        "target_count": len({str(row.get("target_id", "")).strip() for row in rows if str(row.get("target_id", "")).strip()}),
    }


def _followup_scripts(refresh_tier: str) -> list[str]:
    normalized = str(refresh_tier or "full").strip().lower()
    return list(DEFAULT_MINIMAL_FOLLOWUP_SCRIPTS if normalized == "minimal" else DEFAULT_FULL_FOLLOWUP_SCRIPTS)


def build_step_commands(
    python_bin: str,
    rows_json: str,
    source_md: str,
    *,
    refresh_tier: str = "full",
    merge_only: bool = False,
) -> list[list[str]]:
    commands = [[python_bin, str(ROOT / DEFAULT_MERGE_SCRIPT), "--source-md", source_md, "--rows-json", rows_json]]
    if not merge_only:
        commands.extend([[python_bin, str(ROOT / script)] for script in _followup_scripts(refresh_tier)])
    return commands


def _empty_batch_payload(*, last_flushed_entry_count: int = 0, last_flushed_row_count: int = 0, last_refresh_tier: str = "") -> dict[str, Any]:
    return {
        "summary": {
            "status": "wetlab_broad_screen_actual_append_batch_ready",
            "pending_entry_count": 0,
            "pending_row_count": 0,
            "pending_target_count": 0,
            "last_flushed_entry_count": int(last_flushed_entry_count or 0),
            "last_flushed_row_count": int(last_flushed_row_count or 0),
            "last_refresh_tier": str(last_refresh_tier or "").strip(),
            "next_required_step": "Enqueue more shard result rows or flush the current batch into a single rerank/autofill refresh.",
        },
        "structured": {
            "batch_mode": "enqueue_or_flush",
        },
        "rows": [],
    }


def _write_batch_payload(batch_md: str, payload: dict[str, Any]) -> None:
    write_artifact(batch_md, "Wet-Lab Broad Screen Actual Append Batch", payload)


def _enqueue_batch_entry(*, rows_json: str, validation: dict[str, Any], batch_md: str, refresh_tier: str) -> dict[str, Any]:
    batch_payload = _load_batch_payload(batch_md) or _empty_batch_payload()
    batch_rows = [dict(row) for row in (batch_payload.get("rows", []) or [])]
    batch_rows.append(
        {
            "enqueue_rank": len(batch_rows) + 1,
            "rows_json": str(resolve(rows_json)),
            "row_count": int(validation.get("row_count", 0) or 0),
            "target_count": int(validation.get("target_count", 0) or 0),
            "refresh_tier": str(refresh_tier or "full").strip(),
            "queued_at": datetime.now().isoformat(timespec="seconds"),
            "entry_state": "pending",
        }
    )
    payload = {
        "summary": {
            "status": "wetlab_broad_screen_actual_append_batch_ready",
            "pending_entry_count": len(batch_rows),
            "pending_row_count": sum(int(row.get("row_count", 0) or 0) for row in batch_rows),
            "pending_target_count": len({str(row.get("rows_json", "")).strip() for row in batch_rows if str(row.get("rows_json", "")).strip()}),
            "last_flushed_entry_count": int(batch_payload.get("summary", {}).get("last_flushed_entry_count", 0) or 0),
            "last_flushed_row_count": int(batch_payload.get("summary", {}).get("last_flushed_row_count", 0) or 0),
            "last_refresh_tier": str(batch_payload.get("summary", {}).get("last_refresh_tier", "")).strip(),
            "next_required_step": "Flush the pending append batch to merge all queued shard rows and rebuild rerank/autofill surfaces once.",
        },
        "structured": {
            "batch_mode": "enqueue_or_flush",
            "latest_rows_json": str(resolve(rows_json)),
        },
        "rows": batch_rows,
    }
    _write_batch_payload(batch_md, payload)
    return payload


def _run_commands(commands: list[list[str]], *, python_bin: str) -> None:
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)


def _collect_followup_summaries() -> dict[str, dict[str, Any]]:
    return {
        "merge": dict(maybe_load_json("runs/wetlab_broad_screen_bulk_results_source_merge_current.json").get("summary", {}) or {}),
        "source": dict(maybe_load_json("runs/wetlab_broad_screen_bulk_results_source_current.json").get("summary", {}) or {}),
        "autofill": dict(maybe_load_json("runs/wetlab_broad_screen_repurposing_autofill_current.json").get("summary", {}) or {}),
        "rerank": dict(maybe_load_json("runs/wetlab_broad_screen_target_rerank_current.json").get("summary", {}) or {}),
        "stability": dict(maybe_load_json("runs/wetlab_broad_screen_stability_score_current.json").get("summary", {}) or {}),
        "antitarget": dict(maybe_load_json("runs/wetlab_broad_screen_antitarget_queue_current.json").get("summary", {}) or {}),
        "precision": dict(maybe_load_json("runs/wetlab_broad_screen_precision_monitor_current.json").get("summary", {}) or {}),
        "engineering": dict(maybe_load_json("runs/wetlab_engineering_progress_current.json").get("summary", {}) or {}),
        "stack": dict(maybe_load_json("runs/wetlab_partnering_stack_current.json").get("summary", {}) or {}),
    }


def _build_report_payload(
    *,
    status: str,
    mode: str,
    refresh_tier: str,
    incoming_row_count: int,
    incoming_target_count: int,
    batch_summary: dict[str, Any],
    batch_md: str,
    summaries: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summaries = summaries or {}
    merge_summary = summaries.get("merge", {})
    source_summary = summaries.get("source", {})
    autofill_summary = summaries.get("autofill", {})
    rerank_summary = summaries.get("rerank", {})
    stability_summary = summaries.get("stability", {})
    antitarget_summary = summaries.get("antitarget", {})
    precision_summary = summaries.get("precision", {})
    engineering_summary = summaries.get("engineering", {})
    stack_summary = summaries.get("stack", {})

    return {
        "summary": {
            "status": status,
            "mode": mode,
            "refresh_tier": refresh_tier,
            "incoming_row_count": int(incoming_row_count or 0),
            "incoming_target_count": int(incoming_target_count or 0),
            "queued_pending_entry_count": int(batch_summary.get("pending_entry_count", 0) or 0),
            "queued_pending_row_count": int(batch_summary.get("pending_row_count", 0) or 0),
            "merge_overwritten_row_count": int(merge_summary.get("overwritten_row_count", 0) or 0),
            "actual_row_count_after_merge": int(source_summary.get("actual_row_count", 0) or 0),
            "override_target_count_after_append": int(autofill_summary.get("override_target_count", 0) or 0),
            "full_bulk_ready_target_count_after_append": int(rerank_summary.get("full_bulk_ready_target_count", 0) or 0),
            "stable_target_count_after_append": int(stability_summary.get("stable_high_confidence_target_count", 0) or 0)
            + int(stability_summary.get("stable_provisional_target_count", 0) or 0),
            "antitarget_ready_now_row_count": int(antitarget_summary.get("ready_now_row_count", 0) or 0),
            "precision_running_shard_count": int(precision_summary.get("running_shards", 0) or 0),
            "engineering_auto_append_ready": bool(str(engineering_summary.get("status", "")).strip() == "wetlab_engineering_progress_ready"),
            "stack_ready": bool(str(stack_summary.get("status", "")).strip() == "wetlab_partnering_stack_ready"),
            "next_required_step": (
                "Continue enqueueing shard rows and flush the batch when you want one consolidated rerank/autofill refresh."
                if mode == "enqueue"
                else "Continue the active shard or append the next actual result rows; the requested refresh tier has already rebuilt the downstream surfaces."
            ),
        },
        "structured": {
            "rows_json": "" if mode == "flush" else "batch_or_single_input",
            "schema_artifact": "runs/wetlab_broad_screen_bulk_result_source_schema_current.md",
            "batch_artifact": batch_md,
            "merge_report_artifact": "runs/wetlab_broad_screen_bulk_results_source_merge_current.md",
            "rerank_artifact": "runs/wetlab_broad_screen_target_rerank_current.md",
            "stability_artifact": "runs/wetlab_broad_screen_stability_score_current.md",
            "antitarget_queue_artifact": "runs/wetlab_broad_screen_antitarget_queue_current.md",
        },
        "rows": [],
    }


def run_pipeline(
    *,
    rows_json: str,
    source_md: str,
    out_md: str,
    python_bin: str = sys.executable,
    mode: str = "immediate",
    refresh_tier: str = "full",
    batch_md: str = DEFAULT_BATCH_MD,
) -> dict[str, Any]:
    normalized_mode = str(mode or "immediate").strip().lower()
    normalized_tier = str(refresh_tier or "full").strip().lower()
    if normalized_mode not in {"immediate", "enqueue", "flush"}:
        raise ValueError(f"unsupported append mode: {mode}")
    if normalized_tier not in {"minimal", "full"}:
        raise ValueError(f"unsupported refresh tier: {refresh_tier}")

    schema_payload = maybe_load_json(DEFAULT_SCHEMA_JSON)

    if normalized_mode == "flush":
        batch_payload = _load_batch_payload(batch_md) or _empty_batch_payload()
        batch_rows = [dict(row) for row in (batch_payload.get("rows", []) or []) if str(row.get("entry_state", "pending")).strip() == "pending"]
        total_rows = sum(int(row.get("row_count", 0) or 0) for row in batch_rows)
        for row in batch_rows:
            commands = build_step_commands(python_bin, str(row.get("rows_json", "")), source_md, refresh_tier=normalized_tier, merge_only=True)
            _run_commands(commands, python_bin=python_bin)
        if batch_rows:
            followup = [[python_bin, str(ROOT / script)] for script in _followup_scripts(normalized_tier)]
            _run_commands(followup, python_bin=python_bin)
        cleared_batch = _empty_batch_payload(
            last_flushed_entry_count=len(batch_rows),
            last_flushed_row_count=total_rows,
            last_refresh_tier=normalized_tier,
        )
        _write_batch_payload(batch_md, cleared_batch)
        summaries = _collect_followup_summaries() if batch_rows else {}
        payload = _build_report_payload(
            status="wetlab_broad_screen_actual_append_ready",
            mode="flush",
            refresh_tier=normalized_tier,
            incoming_row_count=total_rows,
            incoming_target_count=sum(int(row.get("target_count", 0) or 0) for row in batch_rows),
            batch_summary=cleared_batch["summary"],
            batch_md=batch_md,
            summaries=summaries,
        )
        write_artifact(out_md, "Wet-Lab Broad Screen Actual Append", payload)
        return payload

    rows_payload = _read_rows_payload(rows_json)
    validation = validate_rows_payload(rows_payload, schema_payload)
    if not validation["is_valid"]:
        raise ValueError(f"invalid broad-screen rows payload: {validation}")

    if normalized_mode == "enqueue":
        batch_payload = _enqueue_batch_entry(rows_json=rows_json, validation=validation, batch_md=batch_md, refresh_tier=normalized_tier)
        payload = _build_report_payload(
            status="wetlab_broad_screen_actual_append_enqueued",
            mode="enqueue",
            refresh_tier=normalized_tier,
            incoming_row_count=int(validation["row_count"] or 0),
            incoming_target_count=int(validation["target_count"] or 0),
            batch_summary=batch_payload["summary"],
            batch_md=batch_md,
            summaries={},
        )
        write_artifact(out_md, "Wet-Lab Broad Screen Actual Append", payload)
        return payload

    commands = build_step_commands(python_bin, rows_json, source_md, refresh_tier=normalized_tier)
    _run_commands(commands, python_bin=python_bin)
    batch_payload = _load_batch_payload(batch_md) or _empty_batch_payload()
    summaries = _collect_followup_summaries()
    payload = _build_report_payload(
        status="wetlab_broad_screen_actual_append_ready",
        mode="immediate",
        refresh_tier=normalized_tier,
        incoming_row_count=int(validation["row_count"] or 0),
        incoming_target_count=int(validation["target_count"] or 0),
        batch_summary=batch_payload.get("summary", {}),
        batch_md=batch_md,
        summaries=summaries,
    )
    write_artifact(out_md, "Wet-Lab Broad Screen Actual Append", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append actual broad-screen shard rows and refresh downstream rerank/autofill surfaces.")
    parser.add_argument("--rows-json", default=DEFAULT_ROWS_JSON)
    parser.add_argument("--source-md", default=DEFAULT_SOURCE_MD)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--mode", choices=("immediate", "enqueue", "flush"), default="immediate")
    parser.add_argument("--refresh-tier", choices=("minimal", "full"), default="full")
    parser.add_argument("--batch-md", default=DEFAULT_BATCH_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        rows_json=args.rows_json,
        source_md=args.source_md,
        out_md=args.out_md,
        python_bin=args.python_bin,
        mode=args.mode,
        refresh_tier=args.refresh_tier,
        batch_md=args.batch_md,
    )
