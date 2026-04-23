#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path("/home/betelgeuze/분자동역학")
OUT_JSON = ROOT / "runs" / "viewer_smoke_refresh_current.json"
OUT_MD = ROOT / "runs" / "viewer_smoke_refresh_current.md"


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


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    steps = [
        ("protein_motion_smoke", [sys.executable, "tools/run_viewer_protein_atom_smoke.py"]),
        ("compare_writeback_smoke", [sys.executable, "tools/run_viewer_compare_writeback_smoke.py"]),
        ("viewer_smoke_index", [sys.executable, "tools/build_viewer_smoke_index.py"]),
    ]
    results = []
    for name, cmd in steps:
        entry = {"step": name, **_run(cmd)}
        results.append(entry)

    overall_ok = all(entry["ok"] for entry in results)
    compare_smoke = _read_json(ROOT / "runs" / "viewer_compare_writeback_smoke" / "compare_writeback_browser_smoke_current.json")
    index_smoke = _read_json(ROOT / "runs" / "viewer_smoke_index_current.json")
    payload = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "overall_ok": overall_ok,
        "step_count": len(results),
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
                f"- compare_writeback_debug_readiness_line: `{payload['summary']['compare_writeback_debug_readiness_line']}`",
                f"- compare_writeback_geometry_status_line: `{payload['summary']['compare_writeback_geometry_status_line']}`",
                f"- compare_writeback_geometry_burndown_status_line: `{payload['summary']['compare_writeback_geometry_burndown_status_line']}`",
                f"- compare_writeback_geometry_burndown_next_required_step: `{payload['summary']['compare_writeback_geometry_burndown_next_required_step']}`",
                f"- compare_writeback_compare_pane_state_rep_count: `{payload['summary']['compare_writeback_compare_pane_state_rep_count']}`",
                f"- compare_writeback_wrapper_gap_count: `{payload['summary']['compare_writeback_wrapper_gap_count']}`",
                f"- compare_writeback_mesh_probe_unavailable_count: `{payload['summary']['compare_writeback_mesh_probe_unavailable_count']}`",
                *[
                    f"- {entry['step']}: `{'ok' if entry['ok'] else 'fail'}` ({entry['elapsed_sec']}s)"
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
