#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"


def _stale_rows(payload: dict[str, Any], status_key: str = "queue_status") -> list[dict[str, Any]]:
    return [dict(row) for row in (payload.get("rows", []) or []) if "stale_running" in str(row.get(status_key, "")).strip()]


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def recover(primary_queue: dict[str, Any], antitarget_queue: dict[str, Any], python_bin: str) -> dict[str, Any]:
    primary_rows = _stale_rows(primary_queue)
    antitarget_rows = _stale_rows(antitarget_queue)

    for row in primary_rows:
        _run([
            python_bin,
            str(ROOT / "tools/run_wetlab_broad_screen_runtime_event.py"),
            "--target-id", str(row.get("target_id", "")).strip(),
            "--shard-id", str(row.get("shard_id", "")).strip(),
            "--event", "reset",
        ])

    for row in antitarget_rows:
        _run([
            python_bin,
            str(ROOT / "tools/run_wetlab_broad_screen_antitarget_runtime_event.py"),
            "--primary-target-id", str(row.get("primary_target_id", "")).strip(),
            "--anti-target-id", str(row.get("anti_target_id", "")).strip(),
            "--shard-id", str(row.get("primary_shard_id", "")).strip(),
            "--event", "reset",
        ])

    return {
        "primary_recovered_count": len(primary_rows),
        "antitarget_recovered_count": len(antitarget_rows),
        "primary_rows": primary_rows,
        "antitarget_rows": antitarget_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset stale wet-lab broad-screen rows back to ready state.")
    parser.add_argument("--primary-queue-json", default=DEFAULT_PRIMARY_QUEUE_JSON)
    parser.add_argument("--antitarget-queue-json", default=DEFAULT_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--python-bin", default=sys.executable)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(
        recover(
            primary_queue=load_json(args.primary_queue_json),
            antitarget_queue=load_json(args.antitarget_queue_json),
            python_bin=args.python_bin,
        )
    )
