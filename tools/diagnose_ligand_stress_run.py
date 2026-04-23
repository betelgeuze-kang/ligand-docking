#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _mtime(path: str) -> float:
    try:
        return float(os.path.getmtime(path))
    except Exception:
        return 0.0


def _age(path: str) -> Optional[float]:
    mt = _mtime(path)
    if mt <= 0.0:
        return None
    return max(0.0, time.time() - mt)


def _pgrep_lines(pattern: str) -> List[str]:
    try:
        out = subprocess.check_output(["pgrep", "-af", pattern], text=True).strip()
    except Exception:
        return []
    if not out:
        return []
    return [ln for ln in out.splitlines() if "pgrep -af" not in ln]


def _pid_alive(pid: str) -> bool:
    p = str(pid or "").strip()
    return p.isdigit() and os.path.exists(f"/proc/{p}")


def _classify(state: Dict[str, Any]) -> Dict[str, Any]:
    prefix = str(state.get("prefix", "") or "")
    state_json = f"{prefix}_state.json"
    lock_path = f"{prefix}.lock"
    state_obj = _read_json(state_json)
    current = state_obj.get("current", {}) if isinstance(state_obj.get("current"), dict) else {}
    run_prefix = str(current.get("run_prefix", "") or "").strip()
    state_status = str(current.get("status", "") or "").strip()
    hard_prog = _read_json(f"{prefix}_hard_decoy_progress.json")
    stage2_prog = _read_json(f"{run_prefix}_stage2_traj_progress.json") if run_prefix else {}
    stage2_summary = _read_json(f"{run_prefix}_stage2_traj_summary.json") if run_prefix else {}
    summary = _read_json(f"{prefix}_summary.json")

    procs = _pgrep_lines(prefix) + _pgrep_lines(os.path.basename(prefix))
    procs = sorted(set(procs))
    proc_alive = len(procs) > 0

    lock_owner = ""
    if os.path.exists(lock_path):
        try:
            lock_owner = Path(lock_path).read_text(encoding="utf-8").strip()
        except Exception:
            lock_owner = ""

    stage2_done = bool(stage2_summary)
    stage2_progress_done = int(stage2_prog.get("processed_rows", 0) or 0) >= int(stage2_prog.get("queue_rows_total", 0) or 1)
    pre_done = bool(hard_prog.get("status") == "done" or state_obj.get("pre_stage_state", {}).get("done"))
    final_done = bool(summary)

    classification = "idle"
    reason = "no active signals"
    recommendation = "none"

    if final_done:
        classification = "completed"
        reason = "final summary exists"
        recommendation = "consume summary and post artifacts"
    elif proc_alive:
        if stage2_progress_done and not stage2_done:
            classification = "finalizing_stage2"
            reason = "stage2 processed all rows but summary/manifest not written yet"
            recommendation = "wait for writer drain and manifest flush"
        elif state_status == "pre_stage_running" or (not pre_done):
            classification = "pre_stage_running"
            reason = "hard-decoy pre-stage still active"
            recommendation = "wait for pre-stage completion"
        else:
            classification = "running"
            reason = f"active process + state_status={state_status or '-'}"
            recommendation = "monitor active artifact ages"
    elif os.path.exists(lock_path) and lock_owner and (not _pid_alive(lock_owner)):
        classification = "stale_lock"
        reason = f"lock owner pid {lock_owner} is not alive"
        recommendation = "remove stale lock and resume"
    elif stage2_progress_done and not stage2_done:
        classification = "stalled_stage2_finalize"
        reason = "stage2 progress complete but summary missing and no active process"
        recommendation = "resume from stage2 finalize or rerun stage2 safely"
    elif pre_done and not proc_alive and not final_done:
        classification = "stopped_mid_run"
        reason = f"pre-stage done, final summary missing, no active process, state_status={state_status or '-'}"
        recommendation = "resume current run from saved state"

    return {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "prefix": prefix,
        "classification": classification,
        "reason": reason,
        "recommendation": recommendation,
        "state_status": state_status,
        "lock_path": lock_path,
        "lock_owner": lock_owner,
        "lock_owner_alive": _pid_alive(lock_owner),
        "process_lines": procs,
        "paths": {
            "state_json": state_json,
            "hard_decoy_progress_json": f"{prefix}_hard_decoy_progress.json",
            "summary_json": f"{prefix}_summary.json",
            "run_prefix": run_prefix,
            "stage2_progress_json": f"{run_prefix}_stage2_traj_progress.json" if run_prefix else "",
            "stage2_summary_json": f"{run_prefix}_stage2_traj_summary.json" if run_prefix else "",
        },
        "ages_sec": {
            "state_json": _age(state_json),
            "hard_decoy_progress_json": _age(f"{prefix}_hard_decoy_progress.json"),
            "summary_json": _age(f"{prefix}_summary.json"),
            "stage2_progress_json": _age(f"{run_prefix}_stage2_traj_progress.json") if run_prefix else None,
            "stage2_summary_json": _age(f"{run_prefix}_stage2_traj_summary.json") if run_prefix else None,
        },
        "snapshots": {
            "state_current": current,
            "pre_stage": hard_prog,
            "stage2_progress": stage2_prog,
            "stage2_summary_present": bool(stage2_summary),
            "final_summary_present": bool(summary),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Diagnose a ligand stress run state without mutating it.")
    p.add_argument("--prefix", type=str, required=True)
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = _classify({"prefix": str(args.prefix)})
    out_json = str(args.out_json).strip()
    out_md = str(args.out_md).strip()
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
    if out_md:
        os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
        lines = [
            "# Ligand Stress Run Diagnosis",
            "",
            f"- prefix: `{payload['prefix']}`",
            f"- classification: `{payload['classification']}`",
            f"- reason: `{payload['reason']}`",
            f"- recommendation: `{payload['recommendation']}`",
            f"- state_status: `{payload['state_status']}`",
            f"- lock_owner: `{payload['lock_owner']}`",
            f"- process_count: `{len(payload['process_lines'])}`",
        ]
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
