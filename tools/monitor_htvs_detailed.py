#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from core.gpu_metrics import sample_gpu_metrics
except Exception:  # pragma: no cover
    def sample_gpu_metrics() -> Dict[str, Any]:
        return {"ok": False, "backend": "none", "util_percent": 0.0, "mem_util_percent": 0.0}


def _read_json(path: str) -> Dict[str, Any]:
    if not path or (not os.path.exists(path)):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _pgrep_lines(pattern: str) -> List[str]:
    p = subprocess.run(["bash", "-lc", f'pgrep -af "{pattern}"'], text=True, capture_output=True)
    return [ln for ln in (p.stdout or "").splitlines() if ln.strip()]


def _clear() -> None:
    print("\033[2J\033[H", end="")


def _extract_max_jobs_from_cmd(lines: List[str]) -> int:
    if not lines:
        return 0
    cmd = lines[0]
    m = re.search(r"--max-jobs\s+(\d+)", cmd)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0


def _extract_cmd_arg(cmd: str, arg_name: str) -> str:
    m = re.search(rf"{re.escape(arg_name)}\s+([^\s]+)", cmd)
    return str(m.group(1)).strip() if m else ""


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


def _discover_run_prefixes(stress_prefix: str) -> List[str]:
    run_prefixes: Dict[str, float] = {}
    pat = re.compile(r"(.+?)_(?:stage\d+.*|summary\.json)$")
    for p in glob.glob(f"{stress_prefix}_p*_n*_r*_*"):
        b = os.path.basename(p)
        m = pat.match(b)
        if not m:
            continue
        rp = os.path.join(os.path.dirname(p), m.group(1))
        try:
            mt = os.path.getmtime(p)
        except Exception:
            mt = 0.0
        run_prefixes[rp] = max(run_prefixes.get(rp, 0.0), mt)
    if not run_prefixes:
        for p in glob.glob(f"{stress_prefix}_n*_r*_*"):
            b = os.path.basename(p)
            m = pat.match(b)
            if not m:
                continue
            rp = os.path.join(os.path.dirname(p), m.group(1))
            try:
                mt = os.path.getmtime(p)
            except Exception:
                mt = 0.0
            run_prefixes[rp] = max(run_prefixes.get(rp, 0.0), mt)
    return [k for k, _ in sorted(run_prefixes.items(), key=lambda kv: kv[1], reverse=True)]


def _has_single_run_artifacts(prefix: str) -> bool:
    for s in (
        "_stage1_summary.json",
        "_stage2_traj_progress.json",
        "_stage2_summary.json",
        "_stage3_summary.json",
        "_stage4_calibration_summary.json",
        "_stage5_ranking_summary.json",
        "_summary.json",
    ):
        if os.path.exists(f"{prefix}{s}"):
            return True
    return False


def _infer_plan_from_stress_cmd(prefix: str) -> Tuple[int, int]:
    lines = _pgrep_lines("run_ligand_stress_validation.py")
    if not lines:
        return 0, 0
    pref = str(prefix).strip()
    pref_b = os.path.basename(pref)
    for ln in lines:
        if "--out-prefix" not in ln:
            continue
        outp = _extract_cmd_arg(ln, "--out-prefix")
        if outp not in {pref, pref_b} and (pref not in ln):
            continue
        sizes = _parse_int_list(_extract_cmd_arg(ln, "--ligand-sizes"))
        repeats = 0
        try:
            repeats = int(_extract_cmd_arg(ln, "--repeats") or 0)
        except Exception:
            repeats = 0
        pos = _parse_int_list(_extract_cmd_arg(ln, "--positive-count-sweep"))
        if not sizes:
            sizes = [64, 1000, 5000, 10000]
        if repeats <= 0:
            repeats = 3
        pos_n = len(pos) if pos else 1
        return len(sizes) * repeats * pos_n, repeats
    return 0, 0


def _active_run_prefix_from_pipeline(stress_prefix: str, date_tag: str = "") -> Optional[str]:
    lines = _pgrep_lines("run_ligand_htvs_pipeline.py")
    if not lines:
        return None
    pref = str(stress_prefix).strip()
    pref_b = os.path.basename(pref)
    best_pid = -1
    best_out = None
    for ln in lines:
        if date_tag and (f"--date-tag {date_tag}" not in ln):
            continue
        outp = _extract_cmd_arg(ln, "--out-prefix")
        if not outp:
            continue
        # Only consider children belonging to this stress run.
        if (not outp.startswith(pref + "_")) and (not outp.startswith(pref_b + "_")) and (pref not in ln):
            continue
        try:
            pid = int(ln.split(" ", 1)[0].strip())
        except Exception:
            pid = -1
        if pid > best_pid:
            best_pid = pid
            best_out = outp
    return best_out


def _count_csv_rows(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            n = sum(1 for _ in f)
        return max(n - 1, 0)
    except Exception:
        return 0


def render(prefix: str, date_tag: str = "", clear_screen: bool = False) -> None:
    if clear_screen:
        _clear()
    now = dt.datetime.now().strftime("%F %T")
    effective_prefix = str(prefix)
    run_prefixes: List[str] = []
    total_runs = 0
    done_runs = 0
    pass_runs = 0
    fail_runs = 0

    if not _has_single_run_artifacts(str(prefix)):
        run_prefixes = _discover_run_prefixes(str(prefix))
        active = _active_run_prefix_from_pipeline(str(prefix), str(date_tag))
        if active:
            effective_prefix = str(active)
        elif run_prefixes:
            effective_prefix = str(run_prefixes[0])
        total_inferred, _ = _infer_plan_from_stress_cmd(str(prefix))
        if total_inferred > 0:
            total_runs = total_inferred
        elif run_prefixes:
            total_runs = len(run_prefixes)
        if run_prefixes:
            done_runs = sum(1 for rp in run_prefixes if os.path.exists(f"{rp}_summary.json"))
            for rp in run_prefixes:
                sm = _read_json(f"{rp}_summary.json")
                if not sm:
                    continue
                if bool(sm.get("pass")):
                    pass_runs += 1
                else:
                    fail_runs += 1

    pipe_pat = (
        f"run_ligand_htvs_pipeline.py --run-scope full --date-tag {date_tag}"
        if date_tag
        else (
            f"run_ligand_htvs_pipeline.py --out-prefix {prefix}_"
            if (effective_prefix != str(prefix))
            else f"run_ligand_htvs_pipeline.py --out-prefix {effective_prefix}"
        )
    )
    traj_pat = f"generate_ligand_trajectory_engine.py --queue-csv {effective_prefix}_stage1_queue.csv"
    stage3_pat = f"run_ligand_backmapping_scoring.py --queue-csv {effective_prefix}_stage1_queue.csv"
    stage4_pat = f"calibrate_ligand_mmpbsa_proxy.py --scores-csv {effective_prefix}_stage3_scores.csv"
    stage5_pat = f"evaluate_ligand_ranking_metrics.py --scores-csv {effective_prefix}_stage4_calibration_scores.csv"
    pipe = _pgrep_lines(pipe_pat)
    traj = _pgrep_lines(traj_pat)
    s3 = _pgrep_lines(stage3_pat)
    s4 = _pgrep_lines(stage4_pat)
    s5p = _pgrep_lines(stage5_pat)
    p2 = _read_json(f"{effective_prefix}_stage2_traj_progress.json")
    p5 = _read_json(f"{effective_prefix}_stage5_ranking_summary.json")
    final = _read_json(f"{effective_prefix}_summary.json")
    sla = _read_json(f"{effective_prefix}_sla_summary.json")
    gpu = sample_gpu_metrics()

    print("=== HTVS DETAILED MONITOR ===")
    print(f"time: {now}")
    print("-" * 112)
    print(f"prefix_input: {prefix}")
    print(f"active_run_prefix: {effective_prefix}")
    if total_runs > 0:
        pct = 100.0 * float(done_runs) / float(max(total_runs, 1))
        print(f"overall_progress: {done_runs}/{total_runs} ({pct:.2f}%)  pass={pass_runs} fail={fail_runs}")
    print(f"pipeline_running: {bool(pipe)}")
    if pipe:
        print(f"pipeline_pid: {pipe[0].split()[0]}")
    print(f"traj_running: {bool(traj)}")
    if traj:
        print(f"traj_pid: {traj[0].split()[0]}")
    print(f"stage3_running: {bool(s3)}")
    if s3:
        print(f"stage3_pid: {s3[0].split()[0]}")
    print(f"stage4_running: {bool(s4)}")
    if s4:
        print(f"stage4_pid: {s4[0].split()[0]}")
    print(f"stage5_running: {bool(s5p)}")
    if s5p:
        print(f"stage5_pid: {s5p[0].split()[0]}")
    print(
        "gpu: "
        f"ok={bool(gpu.get('ok', False))} "
        f"util={float(gpu.get('util_percent', 0.0)):.1f}% "
        f"mem={float(gpu.get('mem_util_percent', 0.0)):.1f}% "
        f"backend={gpu.get('backend', 'none')}"
    )

    if p2:
        total = max(int(p2.get("queue_rows_total", 0)), 1)
        done = int(p2.get("processed_rows", 0))
        ok = int(p2.get("ok_rows", 0))
        fail = int(p2.get("failed_rows", 0))
        ratio = 100.0 * float(done) / float(total)
        print("-" * 112)
        print(f"stage2_status: {p2.get('status')}  progress: {done}/{total} ({ratio:.2f}%)  ok={ok} fail={fail}")
        print(f"current_target: {p2.get('current_target', '-')}")
        print(f"current_ligand: {p2.get('current_ligand_id', '-')}")
        last_err = str(p2.get("last_error", "") or "").strip()
        if last_err:
            print(f"last_error: {last_err}")
    else:
        print("-" * 112)
        print("stage2_status: pending")

    # Stage3 progress (score json files)
    print("-" * 112)
    stage3_delivery_root = f"{effective_prefix}_stage3_delivery"
    if isinstance(final.get("artifacts"), dict):
        heavy_run_dir = str((final.get("artifacts") or {}).get("heavy_run_dir", "")).strip()
        if heavy_run_dir:
            cand = os.path.join(heavy_run_dir, "stage3_delivery")
            if os.path.isdir(cand):
                stage3_delivery_root = cand
    stage3_jobs_dir = os.path.join(stage3_delivery_root, "jobs")
    stage3_zip = os.path.join(stage3_delivery_root, "ligand_delivery_bundle.zip")
    stage3_summary_json = f"{effective_prefix}_stage3_summary.json"
    score_json_files = glob.glob(os.path.join(stage3_jobs_dir, "*", "score_*.json"))
    done3 = len(score_json_files)
    queue_rows = _count_csv_rows(f"{effective_prefix}_stage1_queue.csv")
    max_jobs = _extract_max_jobs_from_cmd(s3)
    total3 = max_jobs if max_jobs > 0 else queue_rows
    if total3 > 0:
        pct3 = 100.0 * float(done3) / float(max(total3, 1))
        print(f"stage3_progress: {done3}/{total3} ({pct3:.2f}%)")
    else:
        print(f"stage3_progress: {done3}/-")
    if bool(s3):
        if os.path.exists(stage3_summary_json):
            print("stage3_phase: bundling_zip")
        else:
            print("stage3_phase: scoring_jobs")
    if os.path.exists(stage3_zip):
        try:
            zsz = os.path.getsize(stage3_zip)
            zmb = zsz / (1024.0 * 1024.0)
            print(f"stage3_zip: {zmb:.1f} MB")
        except Exception:
            pass
    if done3 > 0:
        try:
            latest = max(score_json_files, key=os.path.getmtime)
            print(f"stage3_latest_score_json: {os.path.basename(latest)}")
        except Exception:
            pass

    # Stage4/5 status from artifact existence if process not running
    s4_json = f"{effective_prefix}_stage4_calibration_summary.json"
    s5_json = f"{effective_prefix}_stage5_ranking_summary.json"
    s6_json = f"{effective_prefix}_summary.json"
    print(f"stage4_status: {'running' if s4 else ('done' if os.path.exists(s4_json) else 'pending')}")
    print(f"stage5_status: {'running' if s5p else ('done' if os.path.exists(s5_json) else 'pending')}")
    print(f"stage6_status: {'done' if os.path.exists(s6_json) else 'pending'}")
    print(f"stage6_summary_abs: {os.path.abspath(s6_json)}")

    print("-" * 112)
    stages = [
        "stage0_leakage_summary.json",
        "stage1_summary.json",
        "stage2_traj_summary.json",
        "stage2_summary.json",
        "stage3_summary.json",
        "stage4_calibration_summary.json",
        "stage45_integrity_summary.json",
        "stage5_ranking_summary.json",
        "summary.json",
    ]
    for s in stages:
        p = f"{effective_prefix}_{s}"
        print(f"{os.path.basename(p):58s} {'OK' if os.path.exists(p) else '-'}")

    if p5:
        m = p5.get("metrics", {}) if isinstance(p5.get("metrics"), dict) else {}
        print("-" * 112)
        print(
            "stage5_metrics: "
            f"auc={m.get('roc_auc_unique_key')}  "
            f"pr_auc={m.get('pr_auc_unique_key')}  "
            f"bedroc={m.get('bedroc_unique_key')}  "
            f"brier={m.get('brier_unique_key')}  "
            f"ece={m.get('ece_unique_key')}"
        )

    if final:
        stage6 = ((final.get("stages") or {}).get("stage6_operational_gate") or {})
        if (not sla) and isinstance(final.get("stages"), dict):
            st8 = ((final.get("stages") or {}).get("stage8_sla") or {})
            if isinstance(st8, dict) and st8:
                sla = st8
        print("-" * 112)
        print(f"final_pass: {final.get('pass')}  failed_stage: {final.get('failed_stage')}")
        if isinstance(stage6, dict) and stage6:
            print(f"stage6_pass: {stage6.get('pass')}  failed_metrics: {len(stage6.get('failed_metrics', []))}")
    if sla:
        print("-" * 112)
        print(
            "sla: "
            f"total_latency_sec={sla.get('total_latency_sec')}  "
            f"stage2_rate={sla.get('queue_rate_stage2_rows_per_sec')} rows/s  "
            f"stage3_rate={sla.get('queue_rate_stage3_rows_per_sec')} rows/s  "
            f"gate_failure_rate_proxy={sla.get('gate_failure_rate_proxy')}"
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Detailed monitor for ligand HTVS full pipeline run.")
    p.add_argument("--prefix", type=str, required=True)
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--loop", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--interval-sec", type=float, default=2.0)
    p.add_argument("--clear-screen", action=argparse.BooleanOptionalAction, default=True)
    return p


def main() -> None:
    args = build_parser().parse_args()
    if bool(args.loop):
        while True:
            render(prefix=str(args.prefix), date_tag=str(args.date_tag), clear_screen=bool(args.clear_screen))
            time.sleep(max(float(args.interval_sec), 0.2))
    else:
        render(prefix=str(args.prefix), date_tag=str(args.date_tag), clear_screen=bool(args.clear_screen))


if __name__ == "__main__":
    main()
