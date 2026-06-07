#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


RUN_RE = re.compile(r"(.+?)(?:_p(\d+))?_n(\d+)_r(\d+)_summary\.json$")
RUN_STAGE_UNITS = 8.0


@dataclass
class RunState:
    run_prefix: str
    pos: int
    size: int
    rep: int
    done: bool
    stage: str
    stage_order: int
    mtime: float
    anchor_mtime: float
    summary_path: str
    gate_pass: Optional[bool]
    gate_fail_count: Optional[int]
    gate_first_fail: str
    ece: Optional[float]
    auc: Optional[float]


def _parse_int_list(spec: str) -> List[int]:
    out: List[int] = []
    for tok in str(spec).split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok))
        except Exception:
            continue
    return out


def _discover_positive_counts(prefix: str) -> List[int]:
    found: List[int] = []
    # 1) Prefer active orchestrator command line, if available.
    try:
        out = subprocess.check_output(["pgrep", "-af", "run_ligand_stress_validation.py"], text=True).strip()
    except Exception:
        out = ""
    if out:
        pref = str(prefix).strip()
        pref_b = os.path.basename(pref)
        for ln in out.splitlines():
            if ("--out-prefix" not in ln) or ("--positive-count-sweep" not in ln):
                continue
            # Guard: only parse lines for this monitor prefix.
            if (pref not in ln) and (pref_b not in ln):
                continue
            m = re.search(r"--positive-count-sweep\s+([0-9,\s]+)", ln)
            if not m:
                continue
            for tok in str(m.group(1)).replace(" ", "").split(","):
                if not tok:
                    continue
                try:
                    found.append(int(tok))
                except Exception:
                    continue
    if found:
        return sorted(set(found))

    # 2) Fallback to artifact scan.
    base_prefix = os.path.basename(str(prefix))
    patt = re.compile(rf"^{re.escape(base_prefix)}_p(\d+)_n\d+_r\d+_")
    for p in glob.glob(f"{prefix}_p*_n*_r*_*"):
        base = os.path.basename(p)
        m = patt.match(base)
        if not m:
            continue
        try:
            found.append(int(m.group(1)))
        except Exception:
            continue
    if found:
        return sorted(set(found))

    runs_csv = f"{prefix}_runs.csv"
    if os.path.exists(runs_csv):
        try:
            with open(runs_csv, "r", encoding="utf-8", errors="ignore") as f:
                header = f.readline().strip().split(",")
                if "positive_target_count" in header:
                    idx = header.index("positive_target_count")
                    for ln in f:
                        cols = ln.strip().split(",")
                        if idx >= len(cols):
                            continue
                        try:
                            found.append(int(float(cols[idx])))
                        except Exception:
                            continue
        except Exception:
            pass
    return sorted(set(found)) if found else [0]


def _resolve_run_prefix(prefix: str, pos: int, size: int, rep: int) -> str:
    direct_probe_suffixes = (
        "_summary.json",
        "_stage1_summary.json",
        "_stage2_summary.json",
        "_stage2_traj_progress.json",
        "_stage3_summary.json",
        "_stage45_integrity_summary.json",
        "_stage5_ranking_summary.json",
    )
    for suf in direct_probe_suffixes:
        if os.path.exists(f"{prefix}{suf}"):
            return str(prefix)

    candidates = [f"{prefix}_p{pos}_n{size}_r{rep}"]
    if int(pos) == 0:
        candidates.append(f"{prefix}_n{size}_r{rep}")
    probe_suffixes = (
        "_summary.json",
        "_stage1_summary.json",
        "_stage2_traj_progress.json",
        "_stage2_summary.json",
        "_stage0_leakage_summary.json",
    )
    for cand in candidates:
        for suf in probe_suffixes:
            if os.path.exists(f"{cand}{suf}"):
                return cand
    return candidates[0]


def _line_count_minus_header(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            n = sum(1 for _ in f)
        return max(0, int(n - 1))
    except Exception:
        return 0


def _run_anchor_mtime(run_prefix: str) -> float:
    anchor = 0.0
    for p in (
        f"{run_prefix}_stage0_leakage_summary.json",
        f"{run_prefix}_stage0_leakage_summary.csv",
        f"{run_prefix}_stage0_leakage_summary.md",
    ):
        if os.path.exists(p):
            try:
                anchor = max(anchor, float(os.path.getmtime(p)))
            except Exception:
                pass
    return float(anchor)


def _stage_for_prefix(run_prefix: str, min_mtime: float = 0.0) -> Tuple[str, int, float]:
    stage_map = [
        ("stage5", 8, f"{run_prefix}_stage5_ranking_summary.json"),
        ("stage45", 7, f"{run_prefix}_stage45_integrity_summary.json"),
        ("stage4", 6, f"{run_prefix}_stage4_calibration_summary.json"),
        ("stage3", 5, f"{run_prefix}_stage3_summary.json"),
        ("stage2_meta", 4, f"{run_prefix}_stage2_summary.json"),
        ("stage2_traj", 3, f"{run_prefix}_stage2_traj_summary.json"),
        ("stage1", 2, f"{run_prefix}_stage1_summary.json"),
        ("stage0", 1, f"{run_prefix}_stage0_leakage_summary.json"),
    ]
    best_name = "pending"
    best_order = 0
    best_mtime = 0.0
    for name, order, path in stage_map:
        if os.path.exists(path):
            mt = os.path.getmtime(path)
            if mt < float(min_mtime):
                continue
            if order > best_order or (order == best_order and mt > best_mtime):
                best_name = name
                best_order = order
                best_mtime = mt

    progress_json = f"{run_prefix}_stage2_traj_progress.json"
    if best_order < 3 and os.path.exists(progress_json):
        mt = os.path.getmtime(progress_json)
        if mt >= float(min_mtime):
            best_name = "stage2_traj"
            best_order = 3
            best_mtime = max(best_mtime, mt)

    # Fallback for in-progress directory-heavy phase.
    traj_root = f"{run_prefix}_stage2_traj_frames"
    if best_order < 3 and os.path.isdir(traj_root):
        mt = os.path.getmtime(traj_root)
        if (mt >= float(min_mtime)) and (mt > best_mtime):
            best_name = "stage2_traj"
            best_order = 3
            best_mtime = mt

    return best_name, best_order, best_mtime


def _read_json(path: str) -> Dict[str, object]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _safe_mtime(path: str) -> float:
    try:
        if os.path.exists(path):
            return float(os.path.getmtime(path))
    except Exception:
        return 0.0
    return 0.0


def _fmt_age(sec: Optional[float]) -> str:
    if sec is None:
        return "-"
    try:
        v = float(sec)
    except Exception:
        return "-"
    if v < 0:
        v = 0.0
    if v < 60.0:
        return f"{int(v)}s"
    if v < 3600.0:
        return f"{int(v // 60)}m"
    h = int(v // 3600)
    m = int((v % 3600) // 60)
    return f"{h}h {m}m"


def _load_monitor_state(prefix: str) -> Dict[str, object]:
    state_json = f"{prefix}_state.json"
    obj = _read_json(state_json) if os.path.exists(state_json) else {}
    current = obj.get("current", {}) if isinstance(obj.get("current"), dict) else {}
    updated_at_local = str(obj.get("updated_at_local", "") or "").strip()
    state_mtime = _safe_mtime(state_json)
    age_sec = (time.time() - state_mtime) if state_mtime > 0.0 else None
    return {
        "path": state_json,
        "exists": os.path.exists(state_json),
        "mtime": state_mtime,
        "age_sec": age_sec,
        "updated_at_local": updated_at_local,
        "current": current,
        "status": str(current.get("status", "") or "").strip(),
        "run_prefix": str(current.get("run_prefix", "") or "").strip(),
        "run_key": str(current.get("run_key", "") or "").strip(),
    }


def _next_stage_name(stage_name: str) -> str:
    order = [
        "pre_stage",
        "stage0",
        "stage1",
        "stage2_traj",
        "stage2_meta",
        "stage3",
        "stage4",
        "stage45",
        "stage5",
        "done",
    ]
    cur = str(stage_name or "").strip()
    if cur not in order:
        return "stage1"
    idx = order.index(cur)
    if idx >= (len(order) - 1):
        return "complete"
    return order[idx + 1]


def _artifact_snapshot(prefix: str, run_prefix: str, current_stage_name: str) -> Dict[str, Dict[str, object]]:
    paths = {
        "state": f"{prefix}_state.json",
        "pre_stage_progress": f"{prefix}_hard_decoy_progress.json",
        "pre_stage_summary": f"{prefix}_hard_decoy_summary.json",
        "stage1": f"{run_prefix}_stage1_summary.json",
        "stage2_progress": f"{run_prefix}_stage2_traj_progress.json",
        "stage2_summary": f"{run_prefix}_stage2_traj_summary.json",
        "stage3": f"{run_prefix}_stage3_summary.json",
        "stage4": f"{run_prefix}_stage4_calibration_summary.json",
        "stage45": f"{run_prefix}_stage45_integrity_summary.json",
        "stage5": f"{run_prefix}_stage5_ranking_summary.json",
        "summary": f"{run_prefix}_summary.json",
    }
    out: Dict[str, Dict[str, object]] = {}
    now = time.time()
    for key, path in paths.items():
        mt = _safe_mtime(path)
        out[key] = {
            "path": path,
            "exists": bool(mt > 0.0),
            "mtime": mt,
            "age_sec": (now - mt) if mt > 0.0 else None,
        }
    if str(current_stage_name) == "pre_stage":
        out["active"] = out.get("pre_stage_progress", {})
    elif str(current_stage_name) == "stage2_traj":
        out["active"] = out.get("stage2_progress", {})
    elif str(current_stage_name) == "stage3":
        out["active"] = out.get("stage3", {})
    else:
        out["active"] = out.get(str(current_stage_name), {})
    return out


def _stringify_first_fail(failed_metrics: Any) -> str:
    if not isinstance(failed_metrics, list) or len(failed_metrics) <= 0:
        return ""
    fm = failed_metrics[0]
    if not isinstance(fm, dict):
        return str(fm)
    metric = str(fm.get("metric", "metric"))
    val = fm.get("value", None)
    thr = fm.get("threshold", None)
    return f"{metric}: {val} / {thr}"


def _proc_pids(grep_key: str, prefix_filter: str = "") -> List[str]:
    try:
        out = subprocess.check_output(["pgrep", "-af", grep_key], text=True).strip()
    except Exception:
        return []
    if not out:
        return []
    pids: List[str] = []
    pref = str(prefix_filter or "").strip()
    pref_base = os.path.basename(pref) if pref else ""
    for ln in out.splitlines():
        low = str(ln).lower()
        if ("pgrep -af" in low) or ("monitor_ligand_stress_progress.py" in low):
            continue
        if pref and (pref not in ln) and (pref_base not in ln):
            continue
        pid = ln.split(" ", 1)[0].strip()
        if pid.isdigit():
            pids.append(pid)
    return pids


def _proc_pids_fallback(prefix_filter: str = "") -> List[str]:
    generic = (
        "run_ligand_stress_validation.py|run_ligand_htvs_pipeline.py|"
        "run_ligand_backmapping_scoring.py|evaluate_ligand_ranking_metrics.py|"
        "generate_ligand_trajectory_engine.py|generate_ligand_trajectory_batch.py|"
        "build_ligand_mapping_queue.py|audit_ligand_leakage.py|"
        "validate_ligand_eval_integrity.py|calibrate_ligand_mmpbsa_proxy.py"
    )
    return _proc_pids(generic, prefix_filter=prefix_filter)


def _proc_lines(grep_key: str, prefix_filter: str = "") -> List[str]:
    try:
        out = subprocess.check_output(["pgrep", "-af", grep_key], text=True).strip()
    except Exception:
        return []
    if not out:
        return []
    lines: List[str] = []
    pref = str(prefix_filter or "").strip()
    pref_base = os.path.basename(pref) if pref else ""
    for ln in out.splitlines():
        low = str(ln).lower()
        if ("pgrep -af" in low) or ("monitor_ligand_stress_progress.py" in low):
            continue
        if pref and (pref not in ln) and (pref_base not in ln):
            continue
        lines.append(ln)
    return lines


def _proc_lines_fallback(prefix_filter: str = "") -> List[str]:
    generic = (
        "run_ligand_stress_validation.py|run_ligand_htvs_pipeline.py|"
        "run_ligand_backmapping_scoring.py|evaluate_ligand_ranking_metrics.py|"
        "generate_ligand_trajectory_engine.py|generate_ligand_trajectory_batch.py|"
        "build_ligand_mapping_queue.py|audit_ligand_leakage.py|"
        "validate_ligand_eval_integrity.py|calibrate_ligand_mmpbsa_proxy.py"
    )
    return _proc_lines(generic, prefix_filter=prefix_filter)


def _prestage_hard_decoy_status(prefix: str) -> Dict[str, object]:
    summary_json = f"{prefix}_hard_decoy_summary.json"
    progress_json = f"{prefix}_hard_decoy_progress.json"
    prog: Dict[str, object] = {}
    if os.path.exists(progress_json):
        try:
            with open(progress_json, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                prog = obj
        except Exception:
            prog = {}
    progress_mtime = 0.0
    if os.path.exists(progress_json):
        try:
            progress_mtime = float(os.path.getmtime(progress_json))
        except Exception:
            progress_mtime = 0.0
    state_json = f"{prefix}_state.json"
    state_obj = _read_json(state_json) if os.path.exists(state_json) else {}
    current_obj = state_obj.get("current", {}) if isinstance(state_obj.get("current"), dict) else {}
    state_status = str(current_obj.get("status", "") or "").strip().lower()

    if os.path.exists(summary_json):
        return {
            "enabled": True,
            "running": False,
            "done": True,
            "label": "DONE",
            "phase": str(prog.get("phase", "complete") or "complete"),
            "summary_json": summary_json,
            "progress_json": progress_json,
            "progress_ratio": 1.0,
            "requested_total": int(float(prog.get("requested_total", 0) or 0)),
            "generated_total": int(float(prog.get("generated_total", 0) or 0)),
            "current_target": str(prog.get("current_target", "") or ""),
            "target_index": int(float(prog.get("target_index", 0) or 0)),
            "target_total": int(float(prog.get("target_total", 0) or 0)),
            "progress_mtime": progress_mtime,
        }
    running = False
    proc_lines = _proc_lines("build_hard_decoy_benchmark.py", prefix_filter=str(prefix))
    if proc_lines:
        for ln in proc_lines:
            if (f"{prefix}_hard_decoy_summary.json" in ln) or (f"{prefix}_hard_decoy_labels.csv" in ln):
                running = True
                break
    if (not running) and prog:
        # Pre-stage can still be active even when the dedicated builder subprocess
        # is no longer visible; the parent stress process may still be finalizing.
        if state_status == "pre_stage_running":
            running = True
        elif progress_mtime > 0.0 and (time.time() - progress_mtime) <= 300.0:
            running = True

    if running:
        req = int(float(prog.get("requested_total", 0) or 0))
        gen = int(float(prog.get("generated_total", 0) or 0))
        ratio = float(prog.get("progress_ratio", 0.0) or 0.0)
        if req > 0:
            ratio = max(ratio, min(1.0, float(gen) / float(req)))
        phase = str(prog.get("phase", "") or "").strip()
        label = "RUNNING"
        # Distinguish "generation done, post-processing in progress" from real no-progress.
        if (ratio >= 0.999) and (req > 0):
            label = "FINALIZING"
        return {
            "enabled": True,
            "running": True,
            "done": False,
            "label": label,
            "phase": phase,
            "summary_json": summary_json,
            "progress_json": progress_json,
            "progress_ratio": max(0.0, min(1.0, ratio)),
            "requested_total": req,
            "generated_total": gen,
            "current_target": str(prog.get("current_target", "") or ""),
            "target_index": int(float(prog.get("target_index", 0) or 0)),
            "target_total": int(float(prog.get("target_total", 0) or 0)),
            "progress_mtime": progress_mtime,
        }
    return {
        "enabled": False,
        "running": False,
        "done": False,
        "label": "N/A",
        "phase": "",
        "summary_json": summary_json,
        "progress_json": progress_json,
        "progress_ratio": 0.0,
        "requested_total": 0,
        "generated_total": 0,
        "current_target": "",
        "target_index": 0,
        "target_total": 0,
        "progress_mtime": 0.0,
    }


def _detect_active_stage_for_run(run_prefix: str) -> Optional[Dict[str, str]]:
    try:
        out = subprocess.check_output(["pgrep", "-af", run_prefix], text=True).strip()
    except Exception:
        out = ""
    if not out:
        run_base = os.path.basename(str(run_prefix))
        if not run_base:
            return None
        try:
            out = subprocess.check_output(["pgrep", "-af", run_base], text=True).strip()
        except Exception:
            return None
    if not out:
        return None
    lines = [ln for ln in out.splitlines() if ("monitor_ligand_stress_progress.py" not in ln)]
    if not lines:
        lines = _proc_lines_fallback(prefix_filter=run_prefix)
    if not lines:
        return None
    order = [
        ("evaluate_ligand_ranking_metrics.py", "stage5"),
        ("validate_ligand_eval_integrity.py", "stage45"),
        ("calibrate_ligand_mmpbsa_proxy.py", "stage4"),
        ("run_ligand_backmapping_scoring.py", "stage3"),
        ("product/run_ligand_residual_meta_cycle.py", "stage2_meta"),
        ("generate_ligand_trajectory_engine.py", "stage2_traj"),
        ("generate_ligand_trajectory_batch.py", "stage2_traj"),
        ("build_ligand_mapping_queue.py", "stage1"),
        ("audit_ligand_leakage.py", "stage0"),
    ]
    for script, stage in order:
        for ln in lines:
            if script in ln:
                pid = ln.split(" ", 1)[0].strip()
                return {"stage": stage, "pid": pid, "cmd": ln}
    return None


def _pid_elapsed_seconds(pid: str) -> Optional[float]:
    p = str(pid or "").strip()
    if (not p) or (not p.isdigit()):
        return None
    try:
        out = subprocess.check_output(["ps", "-p", p, "-o", "etimes="], text=True).strip()
        if not out:
            return None
        return float(int(out))
    except Exception:
        return None


def _estimate_stage_duration_seconds(run_prefix: str, stage_name: str) -> float:
    defaults = {
        "stage0": 45.0,
        "stage1": 180.0,
        "stage2_traj": 1200.0,
        "stage2_meta": 300.0,
        "stage3": 600.0,
        "stage4": 120.0,
        "stage45": 60.0,
        "stage5": 180.0,
    }
    key_map = {
        "stage0": "stage0_leakage_audit_sec",
        "stage1": "stage1_mapping_sec",
        "stage2_traj": "stage2_trajectory_sec",
        "stage2_meta": "stage2_residual_meta_sec",
        "stage3": "stage3_backmapping_scoring_sec",
        "stage4": "stage4_calibration_sec",
        "stage45": "stage45_integrity_sec",
        "stage5": "stage5_ranking_sec",
    }
    stage_key = key_map.get(str(stage_name), "")
    if not stage_key:
        return float(defaults.get(str(stage_name), 120.0))
    base = re.sub(r"_p\d+_n\d+_r\d+$", "", str(run_prefix))
    patterns = [
        f"{base}_p*_n*_r*_sla_summary.json",
        f"{base}_n*_r*_sla_summary.json",
    ]
    vals: List[float] = []
    seen: set[str] = set()
    for pat in patterns:
        for p in glob.glob(pat):
            if p in seen:
                continue
            seen.add(p)
            obj = _read_json(p)
            d = obj.get("durations_sec", {}) if isinstance(obj.get("durations_sec"), dict) else {}
            try:
                v = float(d.get(stage_key, 0.0) or 0.0)
            except Exception:
                v = 0.0
            if v > 1.0:
                vals.append(v)
    if vals:
        try:
            return float(max(5.0, statistics.median(vals)))
        except Exception:
            return float(max(5.0, statistics.mean(vals)))
    return float(defaults.get(str(stage_name), 120.0))


def _stage2_progress(run_prefix: str, min_mtime: float = 0.0) -> Tuple[float, str]:
    progress_json = f"{run_prefix}_stage2_traj_progress.json"
    queue_total = 0
    queue_summary = f"{run_prefix}_stage1_summary.json"
    queue_csv = f"{run_prefix}_stage1_queue.csv"
    if os.path.exists(queue_summary) and (os.path.getmtime(queue_summary) >= float(min_mtime)):
        p = _read_json(queue_summary)
        queue_total = int(float(p.get("queue_rows", 0) or 0))
    if queue_total <= 0 and os.path.exists(queue_csv) and (os.path.getmtime(queue_csv) >= float(min_mtime)):
        queue_total = _line_count_minus_header(queue_csv)

    if os.path.exists(progress_json) and (os.path.getmtime(progress_json) >= float(min_mtime)):
        p = _read_json(progress_json)
        total = int(float(p.get("queue_rows_total", 0) or 0))
        done = int(float(p.get("processed_rows", 0) or 0))
        ok = int(float(p.get("ok_rows", 0) or 0))
        failed = int(float(p.get("failed_rows", 0) or 0))
        status = str(p.get("status", "") or "")
        if total <= 0:
            total = int(queue_total)
        frac = (float(done) / float(total)) if total > 0 else 0.0
        frac = max(0.0, min(1.0, frac))
        detail = f"{done}/{total} ok={ok} fail={failed} status={status}" if total > 0 else f"ok={ok} fail={failed} status={status}"
        return frac, detail

    traj_root = f"{run_prefix}_stage2_traj_frames"
    if os.path.isdir(traj_root):
        try:
            done_dirs = 0
            for ent in os.scandir(traj_root):
                if not ent.is_dir():
                    continue
                try:
                    mt = ent.stat().st_mtime
                except Exception:
                    mt = 0.0
                if mt >= float(min_mtime):
                    done_dirs += 1
            if done_dirs > 0 and queue_total > 0:
                frac = max(0.0, min(1.0, float(done_dirs) / float(queue_total)))
                return frac, f"fresh_dirs={done_dirs}/{queue_total}"
            if done_dirs > 0:
                return 0.0, f"fresh_dirs={done_dirs}"
        except Exception:
            return 0.0, ""

    return 0.0, ""


def _stage2_abort_reason(run_prefix: str, min_mtime: float = 0.0) -> str:
    progress_json = f"{run_prefix}_stage2_traj_progress.json"
    if (not os.path.exists(progress_json)) or (os.path.getmtime(progress_json) < float(min_mtime)):
        return ""
    p = _read_json(progress_json)
    status = str(p.get("status", "") or "").strip().lower()
    if status != "aborted":
        return ""
    last_error = str(p.get("last_error", "") or "").strip()
    if last_error:
        return f"stage2_traj_aborted: {last_error}"
    return "stage2_traj_aborted"


def _stage3_progress(run_prefix: str, min_mtime: float = 0.0) -> Tuple[float, str]:
    queue_total = 0
    queue_summary = f"{run_prefix}_stage1_summary.json"
    queue_csv = f"{run_prefix}_stage1_queue.csv"
    if os.path.exists(queue_summary):
        p = _read_json(queue_summary)
        queue_total = int(float(p.get("queue_rows", 0) or 0))
    if queue_total <= 0 and os.path.exists(queue_csv):
        queue_total = _line_count_minus_header(queue_csv)

    jobs_root = f"{run_prefix}_stage3_delivery/jobs"
    if not os.path.isdir(jobs_root):
        scores_csv = f"{run_prefix}_stage3_scores.csv"
        if os.path.exists(scores_csv):
            try:
                score_rows = _line_count_minus_header(scores_csv)
            except Exception:
                score_rows = 0
            if queue_total > 0 and score_rows > 0:
                frac = max(0.0, min(1.0, float(score_rows) / float(queue_total)))
                return frac, f"scores={score_rows}/{queue_total}"
            if score_rows > 0:
                return 0.0, f"scores={score_rows}"
        return 0.0, ""
    try:
        done_scores = len(glob.glob(os.path.join(jobs_root, "**", "score_*.json"), recursive=True))
    except Exception:
        done_scores = 0
    if queue_total > 0:
        frac = max(0.0, min(1.0, float(done_scores) / float(queue_total)))
        return frac, f"scores={done_scores}/{queue_total}"
    return 0.0, f"scores={done_scores}"


def _collect_states(prefix: str, sizes: List[int], repeats: int, pos_counts: List[int]) -> List[RunState]:
    states: List[RunState] = []
    for pos in pos_counts:
        for size in sizes:
            for rep in range(1, repeats + 1):
                run_prefix = _resolve_run_prefix(prefix, int(pos), int(size), int(rep))
                anchor_mtime = _run_anchor_mtime(run_prefix)
                summ = f"{run_prefix}_summary.json"
                summ_fresh = os.path.exists(summ) and (
                    (anchor_mtime <= 0.0) or (os.path.getmtime(summ) >= float(anchor_mtime))
                )
                if summ_fresh:
                    p = _read_json(summ)
                    summary_valid = bool(p) and (("pass" in p) or ("stages" in p))
                else:
                    p = {}
                    summary_valid = False
                if summ_fresh and summary_valid:
                    stage6 = ((p.get("stages") or {}).get("stage6_operational_gate") or {})
                    fail_metrics = stage6.get("failed_metrics") or []
                    states.append(
                        RunState(
                            run_prefix=run_prefix,
                            pos=int(pos),
                            size=size,
                            rep=rep,
                            done=True,
                            stage="done",
                            stage_order=9,
                            mtime=os.path.getmtime(summ),
                            anchor_mtime=anchor_mtime,
                            summary_path=summ,
                            gate_pass=bool(stage6.get("pass", p.get("pass"))),
                            gate_fail_count=len(fail_metrics) if isinstance(fail_metrics, list) else None,
                            gate_first_fail=_stringify_first_fail(fail_metrics),
                            ece=_to_float(stage6.get("ranking_ece")),
                            auc=_to_float(stage6.get("ranking_unique_auc")),
                        )
                    )
                else:
                    st_name, st_ord, st_mt = _stage_for_prefix(run_prefix, min_mtime=anchor_mtime)
                    states.append(
                        RunState(
                            run_prefix=run_prefix,
                            pos=int(pos),
                            size=size,
                            rep=rep,
                            done=False,
                            stage=st_name,
                            stage_order=st_ord,
                            mtime=st_mt,
                            anchor_mtime=anchor_mtime,
                            summary_path=summ,
                            gate_pass=None,
                            gate_fail_count=None,
                            gate_first_fail="",
                            ece=None,
                            auc=None,
                        )
                    )
    return states


def _to_float(v: object) -> Optional[float]:
    try:
        x = float(v)  # type: ignore[arg-type]
        if x != x:
            return None
        return x
    except Exception:
        return None


def _estimate_eta(states: List[RunState], prefix: str) -> Optional[float]:
    durs: List[float] = []
    for st in states:
        if not st.done:
            continue
        run_prefix = st.run_prefix
        s1 = f"{run_prefix}_stage1_summary.json"
        if os.path.exists(s1) and os.path.exists(st.summary_path):
            s1_mt = os.path.getmtime(s1)
            if st.anchor_mtime > 0.0 and s1_mt < float(st.anchor_mtime):
                continue
            d = os.path.getmtime(st.summary_path) - s1_mt
            if d > 1.0:
                durs.append(float(d))
    if not durs:
        return None
    rem = sum(1 for s in states if not s.done)
    if rem <= 0:
        return 0.0
    return float(statistics.mean(durs) * rem)


def _fmt_eta(sec: Optional[float]) -> str:
    if sec is None:
        return "-"
    if sec <= 0:
        return "0m"
    m = int(round(sec / 60.0))
    h, mm = divmod(m, 60)
    return f"{h}h {mm}m" if h > 0 else f"{mm}m"


def _load_latest_run_sla(states: List[RunState]) -> Dict[str, object]:
    dones = [s for s in states if s.done]
    if not dones:
        return {}
    dones.sort(key=lambda x: x.mtime, reverse=True)
    for st in dones:
        p = f"{st.run_prefix}_sla_summary.json"
        if not os.path.exists(p):
            continue
        obj = _read_json(p)
        if isinstance(obj, dict) and obj:
            obj["_path"] = p
            return obj
    return {}


def _load_aggregate_sla(prefix: str) -> Dict[str, object]:
    path = f"{prefix}_aggregate.csv"
    if not os.path.exists(path):
        return {}
    try:
        best: Dict[str, str] = {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if not row:
                    continue
                if not best:
                    best = row
                    continue
                # Prefer larger ligand_size, then larger positive_count_target.
                def _i(d: Dict[str, str], k: str) -> int:
                    try:
                        return int(float(str(d.get(k, "0") or "0")))
                    except Exception:
                        return 0
                if (_i(row, "ligand_size"), _i(row, "positive_count_target")) >= (
                    _i(best, "ligand_size"),
                    _i(best, "positive_count_target"),
                ):
                    best = row
        if not best:
            return {}
        out: Dict[str, object] = {"_path": path}
        for k in [
            "positive_count_target",
            "ligand_size",
            "runs",
            "pass_rate",
            "sla_total_latency_sec_mean",
            "sla_queue_rate_stage2_rows_per_sec_mean",
            "sla_queue_rate_stage3_rows_per_sec_mean",
            "sla_gate_failure_rate_proxy_mean",
        ]:
            if k in best:
                out[k] = best.get(k)
        return out
    except Exception:
        return {}


def _bar(pct: float, width: int = 28) -> str:
    pct = max(0.0, min(1.0, pct))
    n = int(round(width * pct))
    return "[" + "#" * n + "-" * (width - n) + "]"


def _render(
    prefix: str,
    sizes: List[int],
    repeats: int,
    pos_counts: List[int],
    grep_key: str,
    color: bool,
    clear_screen: bool,
) -> str:
    states = _collect_states(prefix, sizes, repeats, pos_counts)
    state_info = _load_monitor_state(prefix)
    pre = _prestage_hard_decoy_status(prefix)
    done = sum(1 for s in states if s.done)
    total = len(states)
    pct_runs = (done / total) if total > 0 else 0.0
    pre_total = 1 if bool(pre.get("enabled", False)) else 0
    pre_ratio = float(pre.get("progress_ratio", 0.0) or 0.0)
    pre_units = 1.0 if bool(pre.get("done", False)) else max(0.0, min(1.0, pre_ratio))
    pids = _proc_pids(grep_key, prefix_filter=str(prefix))
    if not pids:
        pids = _proc_pids_fallback(prefix_filter=str(prefix))
    eta = _estimate_eta(states, prefix)
    now = dt.datetime.now().isoformat(timespec="seconds")

    current = None
    incompletes = [s for s in states if not s.done]
    if incompletes:
        incompletes.sort(key=lambda x: (x.stage_order, x.mtime), reverse=True)
        current = incompletes[0]
    state_run_prefix = str(state_info.get("run_prefix", "") or "").strip()
    if state_run_prefix:
        matched = next((s for s in states if s.run_prefix == state_run_prefix), None)
        if matched is not None and (
            current is None
            or current.stage_order <= 0
            or (not bool(pre.get("enabled", False)) and str(state_info.get("status", "")) == "run_running")
        ):
            current = matched

    stage_order_map = {
        "pending": 0,
        "pre_stage": 0,
        "stage0": 1,
        "stage1": 2,
        "stage2_traj": 3,
        "stage2_meta": 4,
        "stage3": 5,
        "stage4": 6,
        "stage45": 7,
        "stage5": 8,
        "done": 9,
    }
    current_stage_name = current.stage if current else ""
    current_stage_order = int(current.stage_order) if current else 0
    current_stage_fraction = 0.0
    current_stage_detail = ""
    active_pid = ""
    state_status = str(state_info.get("status", "") or "").strip()
    if current is not None:
        active_stage = _detect_active_stage_for_run(current.run_prefix)
        if active_stage:
            current_stage_name = str(active_stage.get("stage", "") or current_stage_name)
            current_stage_order = int(stage_order_map.get(current_stage_name, current_stage_order))
            active_pid = str(active_stage.get("pid", "") or "")
        if current_stage_name == "stage2_traj":
            frac, detail = _stage2_progress(current.run_prefix, min_mtime=current.anchor_mtime)
            current_stage_fraction = float(max(0.0, min(1.0, frac)))
            current_stage_detail = str(detail)
            stage2_summary = f"{current.run_prefix}_stage2_traj_summary.json"
            summary_ready = os.path.exists(stage2_summary) and (
                (current.anchor_mtime <= 0.0) or (os.path.getmtime(stage2_summary) >= float(current.anchor_mtime))
            )
            if (active_stage is not None) and (str(active_stage.get("stage", "")) == "stage2_traj") and (not summary_ready):
                if current_stage_fraction >= 0.999:
                    current_stage_fraction = 0.99
                    if current_stage_detail:
                        current_stage_detail = f"{current_stage_detail} (finalizing)"
                    else:
                        current_stage_detail = "finalizing"
            if (active_stage is not None) and (str(active_stage.get("stage", "")) == "stage2_traj") and current_stage_fraction <= 0.0:
                # If active but progress source not yet available, keep it above 0%.
                current_stage_fraction = 0.01
                if not current_stage_detail:
                    current_stage_detail = "running (progress signal pending)"
        elif current_stage_name == "stage3":
            frac, detail = _stage3_progress(current.run_prefix, min_mtime=current.anchor_mtime)
            current_stage_fraction = float(max(0.0, min(1.0, frac)))
            current_stage_detail = str(detail)
            stage3_summary = f"{current.run_prefix}_stage3_summary.json"
            summary_ready = os.path.exists(stage3_summary) and (
                (current.anchor_mtime <= 0.0) or (os.path.getmtime(stage3_summary) >= float(current.anchor_mtime))
            )
            if (active_stage is not None) and (str(active_stage.get("stage", "")) == "stage3") and (not summary_ready):
                if current_stage_fraction >= 0.999:
                    current_stage_fraction = 0.99
                    if current_stage_detail:
                        current_stage_detail = f"{current_stage_detail} (finalizing)"
                    else:
                        current_stage_detail = "finalizing"
            if (active_stage is not None) and (str(active_stage.get("stage", "")) == "stage3") and current_stage_fraction <= 0.0:
                current_stage_fraction = 0.01
                if not current_stage_detail:
                    current_stage_detail = "running (progress signal pending)"
        elif active_pid:
            elapsed = _pid_elapsed_seconds(active_pid)
            est = _estimate_stage_duration_seconds(current.run_prefix, current_stage_name)
            if (elapsed is not None) and (est > 0):
                frac = max(0.01, min(0.95, float(elapsed) / float(est)))
                current_stage_fraction = max(current_stage_fraction, frac)
                if not current_stage_detail:
                    current_stage_detail = f"elapsed={int(elapsed)}s est={int(est)}s"
            elif current_stage_fraction <= 0.0:
                current_stage_fraction = 0.01
                if not current_stage_detail:
                    current_stage_detail = "running"
        elif state_status == "run_running":
            if current_stage_order <= 0:
                current_stage_name = "stage1"
                current_stage_order = 1
            if not current_stage_detail:
                current_stage_detail = "queued/dispatching"

    if (
        current is not None
        and current_stage_order <= 0
        and bool(pre.get("enabled", False))
        and (not bool(pre.get("done", False)))
    ):
        current_stage_name = "pre_stage"
        current_stage_fraction = float(max(0.0, min(1.0, pre_units)))
        if not current_stage_detail:
            pre_phase = str(pre.get("phase", "") or "").strip()
            current_stage_detail = pre_phase or str(pre.get("label", "running"))

    stage_units = float(pre_units)
    for st in states:
        if st.done:
            stage_units += float(RUN_STAGE_UNITS)
            continue
        ord_i = int(max(0, min(int(RUN_STAGE_UNITS), st.stage_order)))
        frac_i = 0.0
        if (current is not None) and (st.pos == current.pos) and (st.size == current.size) and (st.rep == current.rep):
            ord_i = int(max(0, min(int(RUN_STAGE_UNITS), current_stage_order)))
            frac_i = float(max(0.0, min(1.0, current_stage_fraction)))
        if ord_i <= 0:
            continue
        stage_units += float(max(0, ord_i - 1)) + frac_i
    stage_total = max(1, int(total * RUN_STAGE_UNITS + pre_total))
    pct_stage = float(stage_units) / float(stage_total)
    run_progress_units = 0.0
    if current is not None:
        if current_stage_name == "pre_stage":
            pct_run_current = float(max(0.0, min(1.0, pre_units / float(RUN_STAGE_UNITS + pre_total))))
        else:
            run_progress_units = float(max(0, current_stage_order - 1)) + float(current_stage_fraction)
            pct_run_current = float(max(0.0, min(1.0, run_progress_units / float(RUN_STAGE_UNITS))))
    else:
        pct_run_current = 0.0

    latest_done = None
    dones = [s for s in states if s.done]
    if dones:
        dones.sort(key=lambda x: x.mtime, reverse=True)
        latest_done = dones[0]

    latest_fail = None
    fail_dones = [s for s in dones if s.gate_pass is False]
    if fail_dones:
        fail_dones.sort(key=lambda x: x.mtime, reverse=True)
        latest_fail = fail_dones[0]

    def c(code: str, text: str) -> str:
        if not color:
            return text
        return f"\033[{code}m{text}\033[0m"

    artifact_info = _artifact_snapshot(prefix, current.run_prefix if current is not None else prefix, current_stage_name)
    active_art = artifact_info.get("active", {}) if isinstance(artifact_info.get("active"), dict) else {}
    next_stage = _next_stage_name(current_stage_name if current is not None else ("pre_stage" if bool(pre.get("enabled", False)) and not bool(pre.get("done", False)) else "done"))

    lines: List[str] = []
    if clear_screen:
        lines.append("\033[2J\033[H")
    lines.append(c("1;36", "LIGAND STRESS VALIDATION MONITOR"))
    lines.append(f"generated_at: {now}")
    lines.append(f"prefix: {prefix}")
    lines.append("-" * 96)
    lines.append(
        f"Loop     : {c('1;32','RUNNING') if pids else c('1;31','STOPPED')}   "
        f"PID(s): {pids if pids else '-'}"
    )
    if bool(state_info.get("exists", False)):
        lines.append(
            f"State    : {state_status or '-'}  "
            f"updated={state_info.get('updated_at_local') or '-'}  "
            f"age={_fmt_age(state_info.get('age_sec'))}"
        )
    if bool(pre.get("enabled", False)):
        pl = str(pre.get("label", "N/A"))
        if pl == "RUNNING":
            ptxt = c("1;33", pl)
        elif pl == "FINALIZING":
            ptxt = c("1;35", pl)
        elif pl == "DONE":
            ptxt = c("1;32", pl)
        else:
            ptxt = pl
        req = int(pre.get("requested_total", 0) or 0)
        gen = int(pre.get("generated_total", 0) or 0)
        tcur = str(pre.get("current_target", "") or "")
        ti = int(pre.get("target_index", 0) or 0)
        tt = int(pre.get("target_total", 0) or 0)
        phase = str(pre.get("phase", "") or "").strip()
        pmt = float(pre.get("progress_mtime", 0.0) or 0.0)
        age_sec = max(0.0, (time.time() - pmt)) if pmt > 0 else 0.0
        age_txt = f"age={int(age_sec)}s" if pmt > 0 else "age=-"
        pct_pre = max(0.0, min(100.0, float(pre_ratio) * 100.0))
        phase_txt = f" phase={phase}" if phase else ""
        if req > 0:
            lines.append(
                f"PreStage : hard_decoy={ptxt}  {gen}/{req} ({pct_pre:0.1f}%)  target {ti}/{tt} {tcur}{phase_txt}  {age_txt}"
            )
        else:
            lines.append(f"PreStage : hard_decoy={ptxt}{phase_txt}  {age_txt}")
    lines.append(f"Progress : runs  {done}/{total}  {_bar(pct_runs)}  {pct_runs*100:0.1f}%")
    if current is not None:
        lines.append(
            f"           run p={current.pos} n={current.size} r={current.rep}  {_bar(pct_run_current)}  {pct_run_current*100:0.1f}%"
        )
    lines.append(f"           overall {stage_units:0.2f}/{stage_total}  {_bar(pct_stage)}  {pct_stage*100:0.1f}%")
    lines.append(f"ETA      : {_fmt_eta(eta)}")
    if current:
        lines.append(f"Now Run  : p={current.pos} n={current.size} r={current.rep}  stage={current_stage_name}")
        if current_stage_detail:
            lines.append(f"Now Stage: {current_stage_detail}")
        lines.append(
            f"Next     : {next_stage}  "
            f"active_artifact={active_art.get('path', '-') if isinstance(active_art, dict) else '-'}"
        )
        lines.append(
            f"Artifacts: state={_fmt_age(artifact_info.get('state', {}).get('age_sec') if isinstance(artifact_info.get('state'), dict) else None)}  "
            f"pre={_fmt_age(artifact_info.get('pre_stage_progress', {}).get('age_sec') if isinstance(artifact_info.get('pre_stage_progress'), dict) else None)}  "
            f"s2={_fmt_age(artifact_info.get('stage2_progress', {}).get('age_sec') if isinstance(artifact_info.get('stage2_progress'), dict) else None)}  "
            f"s3={_fmt_age(artifact_info.get('stage3', {}).get('age_sec') if isinstance(artifact_info.get('stage3'), dict) else None)}  "
            f"final={_fmt_age(artifact_info.get('summary', {}).get('age_sec') if isinstance(artifact_info.get('summary'), dict) else None)}"
        )
    else:
        lines.append("Now Run  : -")
    if latest_done:
        lines.append(
            f"Last Done: p={latest_done.pos} n={latest_done.size} r={latest_done.rep} "
            f"(AUC={latest_done.auc if latest_done.auc is not None else '-'}, "
            f"ECE={latest_done.ece if latest_done.ece is not None else '-'})"
        )
    if latest_fail:
        lines.append(
            f"Last Fail: p={latest_fail.pos} n={latest_fail.size} r={latest_fail.rep} "
            f"({latest_fail.gate_first_fail or 'failed_metric_unknown'})"
        )
    latest_sla = _load_latest_run_sla(states)
    if latest_sla:
        lines.append(
            "Last SLA : "
            f"lat={latest_sla.get('total_latency_sec')}s  "
            f"s2_rate={latest_sla.get('queue_rate_stage2_rows_per_sec')}  "
            f"s3_rate={latest_sla.get('queue_rate_stage3_rows_per_sec')}  "
            f"fail_proxy={latest_sla.get('gate_failure_rate_proxy')}"
        )
    agg_sla = _load_aggregate_sla(prefix)
    if agg_sla:
        lines.append(
            "Agg SLA  : "
            f"p={agg_sla.get('positive_count_target','-')} n={agg_sla.get('ligand_size','-')}  "
            f"pass_rate={agg_sla.get('pass_rate','-')}  "
            f"lat_mean={agg_sla.get('sla_total_latency_sec_mean','-')}s  "
            f"s2_mean={agg_sla.get('sla_queue_rate_stage2_rows_per_sec_mean','-')}  "
            f"s3_mean={agg_sla.get('sla_queue_rate_stage3_rows_per_sec_mean','-')}  "
            f"fail_mean={agg_sla.get('sla_gate_failure_rate_proxy_mean','-')}"
        )
    lines.append("-" * 96)

    multi_pos = len(pos_counts) > 1 or any(int(p) != 0 for p in pos_counts)
    for size in sizes:
        for pos in pos_counts:
            row_states = sorted(
                [s for s in states if (s.size == size and s.pos == int(pos))],
                key=lambda x: x.rep,
            )
            marks: List[str] = []
            for st in row_states:
                if st.done:
                    ok = (st.gate_pass is True)
                    marks.append(c("1;32", "P") if ok else c("1;31", "F"))
                elif st.stage_order > 0:
                    stage_name = st.stage
                    if (
                        current is not None
                        and st.size == current.size
                        and st.rep == current.rep
                        and st.pos == current.pos
                        and current_stage_name
                    ):
                        stage_name = current_stage_name
                    marks.append(c("1;33", f"{st.rep}:{stage_name}"))
                else:
                    marks.append(".")
            completed = sum(1 for s in row_states if s.done)
            pass_cnt = sum(1 for s in row_states if s.done and s.gate_pass is True)
            fail_cnt = sum(1 for s in row_states if s.done and s.gate_pass is False)
            auc_vals = [float(s.auc) for s in row_states if s.done and s.auc is not None]
            ece_vals = [float(s.ece) for s in row_states if s.done and s.ece is not None]
            auc_mean = f"{statistics.mean(auc_vals):.4f}" if auc_vals else "-"
            ece_mean = f"{statistics.mean(ece_vals):.4f}" if ece_vals else "-"
            left = f"p={int(pos):<3} n={size:<5}" if multi_pos else f"n={size:<5}"
            denom = len(row_states) if row_states else repeats
            lines.append(
                f"{left}  completed={completed}/{denom}  pass={pass_cnt} fail={fail_cnt}  "
                f"AUCmean={auc_mean} ECEmean={ece_mean}"
            )
            lines.append(f"         steps: {', '.join(marks) if marks else '-'}")

    final_summary = f"{prefix}_summary.json"
    final_summary_abs = os.path.abspath(final_summary)
    runs_csv_abs = os.path.abspath(f"{prefix}_runs.csv")
    agg_csv_abs = os.path.abspath(f"{prefix}_aggregate.csv")
    lines.append("-" * 96)
    lines.append(f"Final Summary: {final_summary} ({'exists' if os.path.exists(final_summary) else 'pending'})")
    lines.append(f"Runs CSV     : {prefix}_runs.csv")
    lines.append(f"Aggregate CSV: {prefix}_aggregate.csv")
    lines.append(f"Final Summary Abs: {final_summary_abs}")
    lines.append(f"Runs CSV Abs     : {runs_csv_abs}")
    lines.append(f"Aggregate CSV Abs: {agg_csv_abs}")
    if current is not None:
        abort_reason = _stage2_abort_reason(current.run_prefix, min_mtime=current.anchor_mtime)
        if abort_reason:
            lines.append(f"Last Abort   : {abort_reason}")
    if (not pids) and done < total:
        lines.append("ALERT        : process stopped before completion")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Monitor staged ligand stress validation progress.")
    p.add_argument("--prefix", type=str, default="runs/ligand_stress_commercial_full")
    p.add_argument("--sizes", type=str, default="64,1000,5000,10000")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument(
        "--positive-counts",
        type=str,
        default="",
        help="Comma-separated positive target counts (e.g. 50,100). Empty => auto-discover.",
    )
    p.add_argument(
        "--grep-key",
        type=str,
        default="run_ligand_stress_validation.py",
    )
    p.add_argument("--loop", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--interval-sec", type=float, default=3.0)
    p.add_argument("--color", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--clear-screen", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    sizes = _parse_int_list(args.sizes)
    if not sizes:
        sizes = [64, 1000, 5000, 10000]
    pos_counts = _parse_int_list(str(args.positive_counts).strip()) if str(args.positive_counts).strip() else _discover_positive_counts(str(args.prefix))
    if not pos_counts:
        pos_counts = [0]

    def _write_snapshot(rendered: str) -> None:
        out_json = str(args.out_json).strip()
        out_md = str(args.out_md).strip()
        if out_json:
            state_info = _load_monitor_state(str(args.prefix))
            pre = _prestage_hard_decoy_status(str(args.prefix))
            obj = {
                "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
                "prefix": str(args.prefix),
                "sizes": sizes,
                "positive_counts": pos_counts,
                "repeats": int(max(args.repeats, 1)),
                "state": state_info,
                "pre_stage": pre,
                "screen": rendered,
            }
            os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False)
        if out_md:
            os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
            with open(out_md, "w", encoding="utf-8") as f:
                f.write("```\n" + rendered + "\n```\n")

    if not bool(args.loop):
        rendered = _render(
            prefix=str(args.prefix),
            sizes=sizes,
            repeats=int(max(args.repeats, 1)),
            pos_counts=pos_counts,
            grep_key=str(args.grep_key),
            color=bool(args.color),
            clear_screen=bool(args.clear_screen),
        )
        _write_snapshot(rendered)
        print(rendered)
        return

    try:
        while True:
            rendered = _render(
                prefix=str(args.prefix),
                sizes=sizes,
                repeats=int(max(args.repeats, 1)),
                pos_counts=pos_counts,
                grep_key=str(args.grep_key),
                color=bool(args.color),
                clear_screen=bool(args.clear_screen),
            )
            _write_snapshot(rendered)
            print(rendered)
            time.sleep(float(max(args.interval_sec, 0.5)))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
