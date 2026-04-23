#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from typing import Dict, List, Tuple


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"


STAGES: List[Tuple[str, str]] = [
    ("train_eval", "_train_eval_summary.json"),
    ("branch_dataset", "_train_branch_dataset_summary.json"),
    ("train_branch", "_train_branch_summary.json"),
    ("eval_corrected", "_eval_corrected_summary.json"),
    ("gate_corrected", "_gate_corrected_summary.json"),
]

EVAL_PROGRESS_FILES = {
    "train_eval": "_train_eval_progress.json",
    "train_branch": "_train_branch_progress.json",
    "eval_corrected": "_eval_corrected_progress.json",
}

PROC_MATCHES = (
    "run_idp_3bead_evaluator.py",
    "build_idp_branch_dataset.py",
    "train_idp_branch_model.py",
    "run_idp_3bead_benchmark_gate.py",
)


def _style(enabled: bool, text: str, *codes: str) -> str:
    if not enabled or not codes:
        return text
    return "".join(codes) + text + RESET


def _read_json(path: str) -> Dict[str, object]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _file_age(path: str) -> str:
    if not os.path.exists(path):
        return "-"
    age = max(0, int(time.time() - os.path.getmtime(path)))
    return str(dt.timedelta(seconds=age))


def _proc_lines(prefix: str) -> List[str]:
    lines: List[str] = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        cmdline_path = os.path.join("/proc", pid, "cmdline")
        try:
            with open(cmdline_path, "rb") as f:
                raw = f.read()
        except OSError:
            continue
        if not raw:
            continue
        parts = [chunk.decode("utf-8", errors="replace") for chunk in raw.split(b"\x00") if chunk]
        if not parts:
            continue
        cmdline = " ".join(parts)
        if prefix not in cmdline and not any(token in cmdline for token in PROC_MATCHES):
            continue
        if any(token in cmdline for token in PROC_MATCHES) or prefix in cmdline:
            lines.append(f"{pid} {cmdline}")
    lines.sort()
    return lines


def _current_stage(prefix: str, procs: List[str]) -> str:
    proc_text = "\n".join(procs)
    if "run_idp_3bead_benchmark_gate.py" in proc_text:
        return "gate_corrected"
    if "train_idp_branch_model.py" in proc_text:
        return "train_branch"
    if "build_idp_branch_dataset.py" in proc_text:
        return "branch_dataset"
    if "run_idp_3bead_evaluator.py" in proc_text:
        if os.path.exists(prefix + "_train_branch_summary.json"):
            return "eval_corrected"
        return "train_eval"
    for name, suffix in reversed(STAGES):
        if os.path.exists(prefix + suffix):
            return name
    return "-"


def _stage_lines(prefix: str, color: bool) -> List[str]:
    active = _current_stage(prefix, _proc_lines(prefix))
    out: List[str] = []
    for idx, (name, suffix) in enumerate(STAGES, start=1):
        path = prefix + suffix
        exists = os.path.exists(path)
        if exists:
            icon = _style(color, "OK", GREEN, BOLD)
        elif name == active:
            icon = _style(color, "RUN", YELLOW, BOLD)
        else:
            icon = _style(color, "..", DIM)
        out.append(
            f"{idx}. {name:<15} {icon:<12} age={_file_age(path):<10} file={os.path.basename(path)}"
        )
    return out


def _progress(prefix: str) -> Tuple[int, int]:
    done = 0
    for _name, suffix in STAGES:
        if os.path.exists(prefix + suffix):
            done += 1
    return done, len(STAGES)


def _bar(done: int, total: int, width: int = 32) -> str:
    frac = done / max(total, 1)
    fill = int(round(width * frac))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def _latest_files(prefix: str, limit: int = 8) -> List[str]:
    base_dir = os.path.dirname(prefix)
    stem = os.path.basename(prefix)
    files = []
    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)
        if not os.path.isfile(path):
            continue
        if name.startswith(stem):
            files.append(path)
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[:limit]


def _tail_line(path: str) -> str:
    if not os.path.exists(path):
        return "-"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.rstrip() for line in f.readlines() if line.strip()]
    except OSError:
        return "-"
    return lines[-1] if lines else "-"


def _gpu_line() -> str:
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showuse", "--showmemuse", "--csv"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip().splitlines()
    except Exception:
        return "rocm-smi unavailable"
    if len(out) < 2:
        return "rocm-smi unavailable"
    return out[1]


def _stage_progress_payload(prefix: str, stage: str) -> Dict[str, object]:
    suffix = EVAL_PROGRESS_FILES.get(stage)
    if not suffix:
        return {}
    return _read_json(prefix + suffix)


def _eta_from_progress(payload: Dict[str, object]) -> str:
    try:
        processed = int(payload.get("processed_targets", 0) or 0)
        total = int(payload.get("total_targets", 0) or 0)
        elapsed = float(payload.get("elapsed_sec", 0.0) or 0.0)
    except Exception:
        return "-"
    if processed <= 0 or total <= 0 or processed >= total or elapsed <= 0.0:
        return "-"
    remaining = total - processed
    eta = int((elapsed / max(processed, 1)) * remaining)
    return str(dt.timedelta(seconds=max(eta, 0)))


def _phase_bar(step: int, total: int, width: int = 24) -> str:
    frac = step / max(total, 1)
    fill = int(round(width * frac))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def _eta_from_epoch_progress(payload: Dict[str, object]) -> str:
    try:
        epoch = int(payload.get("epoch", 0) or 0)
        total = int(payload.get("total_epochs", 0) or 0)
        elapsed = float(payload.get("elapsed_sec", 0.0) or 0.0)
    except Exception:
        return "-"
    if epoch <= 0 or total <= 0 or epoch >= total or elapsed <= 0.0:
        return "-"
    remaining = total - epoch
    eta = int((elapsed / max(epoch, 1)) * remaining)
    return str(dt.timedelta(seconds=max(eta, 0)))


def _target_bar(processed: int, total: int, width: int = 28) -> str:
    frac = processed / max(total, 1)
    fill = int(round(width * frac))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def _summary_metrics(prefix: str) -> List[str]:
    gate = _read_json(prefix + "_gate_corrected_summary.json")
    metrics = gate.get("classification_metrics", {}) if isinstance(gate, dict) else {}
    ranking = gate.get("ranking_metrics", {}) if isinstance(gate, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}
    if not isinstance(ranking, dict):
        ranking = {}
    rows = [
        f"pass={gate.get('pass', '-')}",
        f"branch_f1={metrics.get('branch_macro_f1', '-')}",
        f"state_acc={metrics.get('dominant_state_accuracy', '-')}",
        f"llps_pr_auc={metrics.get('llps_flag_pr_auc', '-')}",
        f"llps_rel_pr_auc={metrics.get('llps_relevant_pr_auc', '-')}",
        f"agg_pr_auc={metrics.get('aggregation_flag_pr_auc', '-')}",
        f"agg_rel_pr_auc={metrics.get('aggregation_relevant_pr_auc', '-')}",
        f"compact_auc={ranking.get('compactness_rank_auc', '-')}",
        f"helicity_auc={ranking.get('helicity_rank_auc', '-')}",
        f"condense_auc={ranking.get('condensation_rank_auc', '-')}",
    ]
    return rows


def _print_once(prefix: str, color: bool) -> None:
    procs = _proc_lines(prefix)
    running = bool(procs)
    done, total = _progress(prefix)
    status = _style(color, "RUNNING", GREEN, BOLD) if running else _style(color, "STOPPED", RED, BOLD)
    active_stage_name = _current_stage(prefix, procs)
    stage = _style(color, active_stage_name, MAGENTA, BOLD)
    stage_progress = _stage_progress_payload(prefix, active_stage_name)
    print(_style(color, "=" * 120, CYAN))
    print(_style(color, "IDP FOLD RECHECK DASHBOARD", CYAN, BOLD))
    print(f"time        : {dt.datetime.now().isoformat(timespec='seconds')}")
    print(f"prefix      : {prefix}")
    print(f"status      : {status}")
    print(f"stage       : {stage}")
    print(f"progress    : {_bar(done, total)} {done}/{total}")
    if stage_progress:
        if "processed_targets" in stage_progress:
            try:
                processed = int(stage_progress.get("processed_targets", 0) or 0)
                total_targets = int(stage_progress.get("total_targets", 0) or 0)
                current_target = str(stage_progress.get("current_target", "") or "-")
                current_index = int(stage_progress.get("current_index", 0) or 0)
                elapsed = float(stage_progress.get("elapsed_sec", 0.0) or 0.0)
                stage_detail = str(stage_progress.get("stage_detail", "") or "-")
                phase_step = int(stage_progress.get("phase_step", 0) or 0)
                phase_total_steps = int(stage_progress.get("phase_total_steps", 0) or 0)
                target_subprogress_ratio = float(stage_progress.get("target_subprogress_ratio", 0.0) or 0.0)
            except Exception:
                processed = total_targets = current_index = phase_step = phase_total_steps = 0
                current_target = "-"
                elapsed = 0.0
                stage_detail = "-"
                target_subprogress_ratio = 0.0
            print(
                "target_prog : "
                f"{_target_bar(processed, total_targets)} "
                f"{processed}/{total_targets} "
                f"eta={_style(color, _eta_from_progress(stage_progress), YELLOW)}"
            )
            print(
                "target_now  : "
                f"{_style(color, current_target, BLUE, BOLD)} "
                f"(index={current_index}, elapsed={str(dt.timedelta(seconds=int(elapsed)))})"
            )
            print(
                "target_step : "
                f"{_style(color, stage_detail, MAGENTA, BOLD)} "
                f"{_target_bar(int(round(target_subprogress_ratio * 100)), 100)} "
                f"{target_subprogress_ratio * 100.0:5.1f}%"
            )
            if phase_total_steps > 0:
                print(
                    "phase_prog  : "
                    f"{_phase_bar(phase_step, phase_total_steps)} "
                    f"{phase_step}/{phase_total_steps}"
                )
        elif "epoch" in stage_progress:
            try:
                epoch = int(stage_progress.get("epoch", 0) or 0)
                total_epochs = int(stage_progress.get("total_epochs", 0) or 0)
                elapsed = float(stage_progress.get("elapsed_sec", 0.0) or 0.0)
                best_epoch = stage_progress.get("best_epoch", "-")
                best_score = stage_progress.get("best_score", "-")
                bad_epochs = int(stage_progress.get("bad_epochs", 0) or 0)
                patience = int(stage_progress.get("patience", 0) or 0)
            except Exception:
                epoch = total_epochs = bad_epochs = patience = 0
                elapsed = 0.0
                best_epoch = best_score = "-"
            print(
                "epoch_prog  : "
                f"{_target_bar(epoch, total_epochs)} "
                f"{epoch}/{total_epochs} "
                f"eta={_style(color, _eta_from_epoch_progress(stage_progress), YELLOW)}"
            )
            print(
                "epoch_meta  : "
                f"best_epoch={best_epoch} "
                f"best_score={best_score} "
                f"bad_epochs={bad_epochs}/{patience} "
                f"elapsed={str(dt.timedelta(seconds=int(elapsed)))}"
            )
    else:
        print("target_prog : -")
        print("target_now  : -")
    print(f"gpu         : {_style(color, _gpu_line(), BLUE)}")
    print(f"log_tail    : {_style(color, _tail_line(prefix + '_live.log'), YELLOW)}")
    print(_style(color, "-" * 120, GRAY))
    print(_style(color, "STAGES", BOLD))
    for line in _stage_lines(prefix, color):
        print(line)
    print(_style(color, "-" * 120, GRAY))
    print(_style(color, "PROCESSES", BOLD))
    if procs:
        for line in procs:
            print(line)
    else:
        print(_style(color, "(no matching processes)", DIM))
    print(_style(color, "-" * 120, GRAY))
    print(_style(color, "LATEST FILES", BOLD))
    for path in _latest_files(prefix):
        print(f"{_file_age(path):>10}  {_style(color, path, BLUE)}")
    gate_path = prefix + "_gate_corrected_summary.json"
    if os.path.exists(gate_path):
        print(_style(color, "-" * 120, GRAY))
        print(_style(color, "GATE SNAPSHOT", BOLD))
        for row in _summary_metrics(prefix):
            print(row)
    print(_style(color, "=" * 120, CYAN))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--clear-screen", action="store_true")
    parser.add_argument("--color", action="store_true")
    args = parser.parse_args()

    while True:
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        _print_once(args.prefix, args.color)
        if not args.loop:
            break
        time.sleep(max(args.interval_sec, 0.1))


if __name__ == "__main__":
    main()
