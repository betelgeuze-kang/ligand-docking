#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MONITOR_JSON = ROOT / "runs/wetlab_broad_screen_precision_monitor_current.json"
DEFAULT_BUILDER = ROOT / "tools/build_wetlab_broad_screen_precision_monitor.py"


def _refresh() -> None:
    subprocess.run([sys.executable, str(DEFAULT_BUILDER)], cwd=ROOT, check=True)


def _render() -> str:
    payload = json.loads(DEFAULT_MONITOR_JSON.read_text())
    summary = payload.get("summary", {})
    rows = payload.get("rows", [])
    focus_target = summary.get("focus_target_id", summary.get("active_target_id", ""))
    focus_shard = summary.get("focus_shard_id", summary.get("active_shard_id", ""))
    focus_mode = summary.get("focus_mode", "idle")
    focus_status = summary.get("focus_queue_status", "")
    focus_elapsed = summary.get("focus_elapsed_minutes", summary.get("active_elapsed_minutes", 0))
    focus_stage = summary.get("focus_active_stage_label", "-")
    focus_hb = summary.get("focus_heartbeat_count", 0)
    focus_ev = summary.get("focus_event_count", 0)
    focus_shard_pct = summary.get("focus_estimated_running_shard_pct", 0)
    focus_runtime_baseline = summary.get("focus_runtime_baseline_minutes", summary.get("runtime_baseline_minutes", 0))
    lines = [
        "Wet-Lab Broad Screen Precision Monitor",
        "",
        f"overall: {summary.get('resolved_shards', 0)}/{summary.get('total_shards', 0)} resolved "
        f"({summary.get('completion_pct', 0)}%), running={summary.get('running_shards', 0)}, pending={summary.get('pending_shards', 0)}",
        f"focus: {focus_target} {focus_shard} "
        f"(mode={focus_mode}, status={focus_status}, stage={focus_stage}, hb={focus_hb}, ev={focus_ev}, shard~={focus_shard_pct}%, elapsed={focus_elapsed} min, baseline={focus_runtime_baseline} min, target={summary.get('focus_target_completion_pct', summary.get('active_target_completion_pct', 0))}%)",
        f"quality: full_bulk_ready_targets={summary.get('full_bulk_ready_target_count', 0)}, "
        f"partial_actual_targets={summary.get('partial_actual_target_count', 0)}",
        f"eta: avg_shard={summary.get('average_completed_shard_minutes', 0)} min, baseline={summary.get('runtime_baseline_minutes', 0)} min, "
        f"remaining≈{summary.get('estimated_remaining_minutes', 0)} min",
        "",
        "top targets:",
    ]
    ranked = sorted(
        rows,
        key=lambda row: (
            -int(row.get("running_shards", 0) or 0),
            -float(row.get("completion_pct", 0.0) or 0.0),
            str(row.get("target_id", "")).lower(),
        ),
    )
    for row in ranked[:8]:
        lines.append(
            f"- {row.get('target_id','')}: {row.get('completed_shards',0)}/{row.get('total_shards',0)} "
            f"({row.get('completion_pct',0)}%), running={row.get('current_running_shard','') or '-'}, "
            f"actual_top3={row.get('actual_top3_count',0)}, rerank={row.get('rerank_status','')}"
        )
    lines.extend(["", f"next: {summary.get('next_required_step', '')}"])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the wet-lab broad-screen precision monitor in the terminal.")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--clear-screen", action="store_true")
    return parser.parse_args()


def run_monitor(args: argparse.Namespace) -> None:
    while True:
        if args.refresh:
            _refresh()
        text = _render()
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        print(text)
        if not args.loop:
            break
        time.sleep(max(args.interval_sec, 0.5))


if __name__ == "__main__":
    run_monitor(parse_args())
