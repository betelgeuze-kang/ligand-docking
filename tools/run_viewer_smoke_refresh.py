#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path("/home/betelgeuze/분자동역학")
OUT_JSON = ROOT / "runs" / "viewer_smoke_refresh_current.json"
OUT_MD = ROOT / "runs" / "viewer_smoke_refresh_current.md"
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_RETRY_DELAY_SEC = 1.0


def _run(cmd: list[str]) -> dict:
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "elapsed_sec": round(time.time() - started, 3),
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def _run_with_retries(cmd: list[str], *, max_attempts: int, retry_delay_sec: float) -> dict:
    attempts: list[dict] = []
    for attempt_index in range(1, max(1, int(max_attempts)) + 1):
        result = _run(cmd)
        result["attempt"] = attempt_index
        attempts.append(result)
        if result["ok"]:
            break
        if attempt_index < max(1, int(max_attempts)):
            time.sleep(max(0.0, float(retry_delay_sec)))
    final = dict(attempts[-1])
    final["attempt_count"] = len(attempts)
    final["retry_recovered"] = len(attempts) > 1 and bool(final["ok"])
    final["attempts"] = attempts
    return final


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh viewer smoke artifacts with transient-readiness retry.")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--retry-delay-sec", type=float, default=DEFAULT_RETRY_DELAY_SEC)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    steps = [
        ("protein_motion_smoke", [sys.executable, "tools/run_viewer_protein_atom_smoke.py"]),
        ("compare_writeback_smoke", [sys.executable, "tools/run_viewer_compare_writeback_smoke.py"]),
        ("viewer_smoke_index", [sys.executable, "tools/build_viewer_smoke_index.py"]),
    ]
    results = []
    for name, cmd in steps:
        entry = {
            "step": name,
            **_run_with_retries(
                cmd,
                max_attempts=args.max_attempts,
                retry_delay_sec=args.retry_delay_sec,
            ),
        }
        results.append(entry)

    overall_ok = all(entry["ok"] for entry in results)
    retry_recovered_step_count = sum(1 for entry in results if entry.get("retry_recovered"))
    failed_step_count = sum(1 for entry in results if not entry.get("ok"))
    compare_smoke = _read_json(ROOT / "runs" / "viewer_compare_writeback_smoke" / "compare_writeback_browser_smoke_current.json")
    index_smoke = _read_json(ROOT / "runs" / "viewer_smoke_index_current.json")
    payload = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "overall_ok": overall_ok,
        "step_count": len(results),
        "failed_step_count": failed_step_count,
        "retry_recovered_step_count": retry_recovered_step_count,
        "steps": results,
        "artifacts": {
            "viewer_smoke_index_json": str(ROOT / "runs" / "viewer_smoke_index_current.json"),
            "protein_motion_smoke_json": str(ROOT / "runs" / "viewer_protein_atom_smoke" / "protein_atom_frames_browser_smoke_current.json"),
            "compare_writeback_smoke_json": str(ROOT / "runs" / "viewer_compare_writeback_smoke" / "compare_writeback_browser_smoke_current.json"),
        },
        "summary": {
            "compare_writeback_debug_readiness_line": compare_smoke.get("compare_debug_readiness_line", ""),
            "compare_writeback_geometry_status_line": ((index_smoke.get("summary") or {}).get("compare_writeback_geometry_status_line", "")),
            "compare_writeback_index_readiness_line": ((index_smoke.get("summary") or {}).get("compare_writeback_debug_readiness_line", "")),
            "compare_writeback_geometry_burndown_status_line": ((index_smoke.get("summary") or {}).get("compare_writeback_geometry_burndown_status_line", "")),
            "compare_writeback_geometry_burndown_next_required_step": ((index_smoke.get("summary") or {}).get("compare_writeback_geometry_burndown_next_required_step", "")),
            "compare_writeback_compare_pane_state_rep_count": ((index_smoke.get("summary") or {}).get("compare_writeback_compare_pane_state_rep_count", 0)),
            "compare_writeback_wrapper_gap_count": ((index_smoke.get("summary") or {}).get("compare_writeback_wrapper_gap_count", 0)),
            "compare_writeback_mesh_probe_unavailable_count": ((index_smoke.get("summary") or {}).get("compare_writeback_mesh_probe_unavailable_count", 0)),
        },
        "geometry_access": (index_smoke.get("geometry_access") or {}),
        "geometry_probe": (index_smoke.get("geometry_probe") or {}),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(
        "\n".join(
            [
                "# Viewer Smoke Refresh",
                "",
                f"- generated_at_local: `{payload['generated_at_local']}`",
                f"- overall_ok: `{payload['overall_ok']}`",
                f"- failed_step_count: `{payload['failed_step_count']}`",
                f"- retry_recovered_step_count: `{payload['retry_recovered_step_count']}`",
                f"- compare_writeback_debug_readiness_line: `{payload['summary']['compare_writeback_debug_readiness_line']}`",
                f"- compare_writeback_geometry_status_line: `{payload['summary']['compare_writeback_geometry_status_line']}`",
                f"- compare_writeback_geometry_burndown_status_line: `{payload['summary']['compare_writeback_geometry_burndown_status_line']}`",
                f"- compare_writeback_geometry_burndown_next_required_step: `{payload['summary']['compare_writeback_geometry_burndown_next_required_step']}`",
                f"- compare_writeback_compare_pane_state_rep_count: `{payload['summary']['compare_writeback_compare_pane_state_rep_count']}`",
                f"- compare_writeback_wrapper_gap_count: `{payload['summary']['compare_writeback_wrapper_gap_count']}`",
                f"- compare_writeback_mesh_probe_unavailable_count: `{payload['summary']['compare_writeback_mesh_probe_unavailable_count']}`",
                *[
                    f"- {entry['step']}: `{'ok' if entry['ok'] else 'fail'}` "
                    f"({entry['elapsed_sec']}s; attempts={entry['attempt_count']})"
                    for entry in results
                ],
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
