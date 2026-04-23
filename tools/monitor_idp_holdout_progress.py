#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

from tools.monitor_ui import (
    BOLD,
    BLUE,
    CYAN,
    DIM,
    GRAY,
    GREEN,
    MAGENTA,
    RED,
    RESET,
    YELLOW,
    human_duration as _ui_human_duration,
    shorten as _ui_shorten,
    style as _ui_style,
)


STAGE_PATTERNS = {
    "train_eval": "*_train_eval_summary.json",
    "branch_dataset": "*_train_branch_dataset_summary.json",
    "train_branch": "*_train_branch_summary.json",
    "eval_baseline": "*_eval_baseline_summary.json",
    "gate_baseline": "*_gate_baseline_summary.json",
    "eval_corrected": "*_eval_corrected_summary.json",
    "gate_corrected": "*_gate_corrected_summary.json",
}

PROGRESS_STAGE_SUFFIXES = [
    ("train_branch_summary", "train_branch"),
    ("train_eval", "train_eval"),
    ("eval_baseline", "eval_baseline"),
    ("eval_corrected", "eval_corrected"),
]


def _glob_count(prefix: str, pattern: str) -> int:
    return len(glob.glob(prefix + "_fold*" + pattern[1:]))


def _latest_files(prefix: str, limit: int = 8) -> List[str]:
    files = glob.glob(prefix + "*")
    files = [p for p in files if os.path.isfile(p)]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[:limit]


STAGE_BRIEFS = {
    "train_eval": "tr",
    "branch_dataset": "ds",
    "train_branch": "br",
    "eval_baseline": "e0",
    "gate_baseline": "g0",
    "eval_corrected": "e1",
    "gate_corrected": "g1",
}


def _fold_brief(name: str) -> str:
    match = re.match(r"fold(\d+)_", name)
    if match:
        return f"f{match.group(1)}"
    return name[:12]


def _latest_entry_brief(prefix: str, path: str) -> str:
    age_sec = max(0, int(time.time() - os.path.getmtime(path)))
    base = os.path.basename(path)
    pref = os.path.basename(prefix) + "_"
    if base.startswith(pref):
        stem = base[len(pref) :]
        stage_patterns = [
            ("_train_branch_dataset_summary", "ds"),
            ("_train_branch_summary", "br"),
            ("_train_eval_progress", "tr"),
            ("_train_eval_summary", "tr"),
            ("_eval_baseline_progress", "e0"),
            ("_eval_baseline_summary", "e0"),
            ("_gate_baseline_summary", "g0"),
            ("_eval_corrected_progress", "e1"),
            ("_eval_corrected_summary", "e1"),
            ("_gate_corrected_summary", "g1"),
        ]
        for token, stage_brief in stage_patterns:
            for suffix in (".json", ".md", ".csv"):
                full = token + suffix
                if stem.endswith(full):
                    fold_name = stem[: -len(full)]
                    return f"{age_sec}s {_fold_brief(fold_name)}/{stage_brief}"
    return f"{age_sec}s {_ui_shorten(base, 18)}"


def _latest_file_brief(prefix: str, limit: int = 4) -> str:
    parts: List[str] = []
    seen: set[str] = set()
    for path in _latest_files(prefix, limit=limit):
        item = _latest_entry_brief(prefix, path)
        if item in seen:
            continue
        seen.add(item)
        parts.append(item)
        if len(parts) >= limit:
            break
    return " | ".join(parts) if parts else "-"


PROC_MATCHES = {
    "run_idp_3bead_holdout_pipeline.py",
    "run_idp_3bead_evaluator.py",
    "build_idp_branch_dataset.py",
    "train_idp_branch_model.py",
    "run_idp_3bead_benchmark_gate.py",
}


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
        if not any(any(token in part for token in PROC_MATCHES) for part in parts):
            continue
        cmdline = " ".join(parts)
        if prefix not in cmdline:
            continue
        lines.append(f"{pid} {cmdline}")
    lines.sort()
    return lines


def _proc_roles(lines: List[str]) -> Tuple[int, str]:
    roles: List[str] = []
    mapping = {
        "run_idp_3bead_holdout_pipeline.py": "holdout",
        "run_idp_3bead_evaluator.py": "evaluator",
        "build_idp_branch_dataset.py": "dataset",
        "train_idp_branch_model.py": "train",
        "run_idp_3bead_benchmark_gate.py": "gate",
    }
    for line in lines:
        for token, label in mapping.items():
            if token in line and label not in roles:
                roles.append(label)
    return len(lines), ",".join(roles) if roles else "-"


def _extract_config_json_from_lines(lines: List[str]) -> str:
    for line in lines:
        if "run_idp_3bead_holdout_pipeline.py" not in line:
            continue
        parts = line.split()
        for idx, token in enumerate(parts):
            if token == "--config-json" and idx + 1 < len(parts):
                return parts[idx + 1]
    return ""


def _safe_load_json(path_like: str) -> Dict[str, object]:
    path = Path(path_like)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _infer_total_folds(prefix: str, requested_total_folds: int) -> int:
    if requested_total_folds and requested_total_folds > 0:
        return int(requested_total_folds)
    summary_json = prefix + "_summary.json"
    summary = _safe_load_json(summary_json)
    if summary:
        fold_count = int(summary.get("fold_count", 0) or 0)
        if fold_count > 0:
            return fold_count
    proc_lines = _proc_lines(prefix)
    config_json = _extract_config_json_from_lines(proc_lines)
    if config_json:
        cfg = _safe_load_json(config_json)
        targets = list(cfg.get("targets", [])) if isinstance(cfg.get("targets", []), list) else []
        split_groups = {str(row.get("split_group", "")).strip() for row in targets if str(row.get("split_group", "")).strip()}
        if split_groups:
            return len(split_groups)
    observed_fold_ids: set[str] = set()
    for path in glob.glob(prefix + "_fold*_*"):
        match = re.search(r"_fold(\d+)_", path)
        if match:
            observed_fold_ids.add(match.group(1))
    if observed_fold_ids:
        return len(observed_fold_ids)
    return 20


def _ansi(enabled: bool, code: str) -> str:
    return code if enabled else ""


def _style(enabled: bool, text: str, *codes: str) -> str:
    return _ui_style(enabled, text, *codes)


def _extract_current_fold(lines: List[str]) -> str:
    pattern = re.compile(r"(fold\d+_[A-Za-z0-9_]+)")
    for line in lines:
        match = pattern.search(line)
        if match:
            return match.group(1)
    return "-"


def _counts(prefix: str) -> Dict[str, int]:
    return {name: _glob_count(prefix, pattern) for name, pattern in STAGE_PATTERNS.items()}


def _progress_bar(done: int, total: int, width: int = 36) -> str:
    total = max(total, 1)
    frac = min(max(done / total, 0.0), 1.0)
    fill = int(round(width * frac))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def _completed_gate_files(prefix: str) -> List[str]:
    files = glob.glob(prefix + "_fold*_gate_corrected_summary.json")
    files.sort(key=lambda p: os.path.getmtime(p))
    return files


def _read_json(path: str) -> Dict[str, object]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _recent_completed_folds(prefix: str, limit: int = 5) -> List[Tuple[str, int]]:
    pattern = re.compile(r"_fold(\d+)_([^/]+?)_gate_corrected_summary\.json$")
    out: List[Tuple[str, int]] = []
    for path in _completed_gate_files(prefix)[-limit:]:
        m = pattern.search(path)
        if not m:
            continue
        fold_name = f"fold{m.group(1)}_{m.group(2)}"
        age_sec = max(0, int(time.time() - os.path.getmtime(path)))
        out.append((_fold_brief(fold_name), age_sec))
    return out


def _recent_completed_fold_metrics(prefix: str, limit: int = 5) -> List[Tuple[str, Dict[str, object]]]:
    pattern = re.compile(r"_fold(\d+)_([^/]+?)_gate_corrected_summary\.json$")
    out: List[Tuple[str, Dict[str, object]]] = []
    for path in _completed_gate_files(prefix)[-limit:]:
        m = pattern.search(path)
        if not m:
            continue
        fold_name = _fold_brief(f"fold{m.group(1)}_{m.group(2)}")
        payload = _read_json(path)
        metrics = payload.get("classification_metrics", {}) if isinstance(payload, dict) else {}
        ranking = payload.get("ranking_metrics", {}) if isinstance(payload, dict) else {}
        if not isinstance(metrics, dict):
            metrics = {}
        if not isinstance(ranking, dict):
            ranking = {}
        out.append(
            (
                fold_name,
                {
                    "pass": payload.get("pass", "-"),
                    "state_acc": metrics.get("dominant_state_accuracy", "-"),
                    "llps_pr_auc": metrics.get("llps_flag_pr_auc", "-"),
                    "llps_rel_pr_auc": metrics.get("llps_relevant_pr_auc", "-"),
                    "agg_pr_auc": metrics.get("aggregation_flag_pr_auc", "-"),
                    "agg_rel_pr_auc": metrics.get("aggregation_relevant_pr_auc", "-"),
                    "compact_auc": ranking.get("compactness_rank_auc", "-"),
                    "helicity_auc": ranking.get("helicity_rank_auc", "-"),
                    "condense_auc": ranking.get("condensation_rank_auc", "-"),
                },
            )
        )
    return out


def _format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "-"
    return str(dt.timedelta(seconds=int(seconds)))


def _sub_bar(percent: float, width: int = 24) -> str:
    frac = min(max(percent / 100.0, 0.0), 1.0)
    fill = int(round(width * frac))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def _parse_progress_path(prefix: str, path: str) -> Tuple[str, str] | None:
    base = os.path.basename(path)
    pref = os.path.basename(prefix) + "_"
    if not base.startswith(pref) or not base.endswith("_progress.json"):
        return None
    stem = base[len(pref) : -len("_progress.json")]
    for suffix, stage_name in PROGRESS_STAGE_SUFFIXES:
        token = "_" + suffix
        if stem.endswith(token):
            fold_name = stem[: -len(token)]
            return fold_name, stage_name
    return None


def _progress_files(prefix: str) -> List[str]:
    return sorted(glob.glob(prefix + "_fold*_progress.json"))


def _active_progress(prefix: str) -> Tuple[str, str, Dict[str, object]] | None:
    candidates: List[Tuple[float, str, str, Dict[str, object]]] = []
    for path in _progress_files(prefix):
        parsed = _parse_progress_path(prefix, path)
        if not parsed:
            continue
        fold_name, stage_name = parsed
        payload = _read_json(path)
        if str(payload.get("status", "")).lower() != "running":
            continue
        candidates.append((os.path.getmtime(path), fold_name, stage_name, payload))
    if not candidates:
        return None
    _mtime, fold_name, stage_name, payload = max(candidates, key=lambda x: x[0])
    return fold_name, stage_name, payload


def _progress_ratio(payload: Dict[str, object]) -> float | None:
    try:
        if "progress_ratio" in payload:
            return float(payload["progress_ratio"])
    except Exception:
        return None
    try:
        if "processed_targets" in payload and "total_targets" in payload:
            total = max(float(payload["total_targets"]), 1.0)
            return max(0.0, min(float(payload["processed_targets"]) / total, 1.0))
    except Exception:
        return None
    try:
        if "epoch" in payload and "total_epochs" in payload:
            total = max(float(payload["total_epochs"]), 1.0)
            return max(0.0, min(float(payload["epoch"]) / total, 1.0))
    except Exception:
        return None
    return None


def _progress_elapsed(payload: Dict[str, object]) -> float:
    try:
        return max(float(payload.get("elapsed_sec", 0.0)), 0.0)
    except Exception:
        return 0.0


def _progress_eta(payload: Dict[str, object]) -> float | None:
    ratio = _progress_ratio(payload)
    elapsed = _progress_elapsed(payload)
    if ratio is None or ratio <= 0.0 or ratio >= 1.0:
        return None
    return elapsed * (1.0 - ratio) / ratio


def _fold_progress_payloads(prefix: str, fold_base: str) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for path in _progress_files(prefix):
        parsed = _parse_progress_path(prefix, path)
        if not parsed:
            continue
        fold_name, _stage_name = parsed
        if fold_name != fold_base:
            continue
        payload = _read_json(path)
        if payload:
            out.append(payload)
    return out


def _fold_elapsed_estimate(prefix: str, fold_base: str) -> float:
    payloads = _fold_progress_payloads(prefix, fold_base)
    total = 0.0
    for payload in payloads:
        total += _progress_elapsed(payload)
    return total


def _completed_fold_total_estimates(prefix: str) -> List[float]:
    pattern = re.compile(r"_fold(\d+)_([^/]+?)_gate_corrected_summary\.json$")
    totals: List[float] = []
    for gate_path in _completed_gate_files(prefix):
        m = pattern.search(gate_path)
        if not m:
            continue
        fold_base = f"fold{m.group(1)}_{m.group(2)}"
        total = _fold_elapsed_estimate(prefix, fold_base)
        if total > 0:
            totals.append(total)
    return totals


def _pass_fail_counts(prefix: str) -> Tuple[int, int]:
    passed = 0
    failed = 0
    for path in _completed_gate_files(prefix):
        payload = _read_json(path)
        if bool(payload.get("pass", False)):
            passed += 1
        else:
            failed += 1
    return passed, failed


def _branch_f1_stats(prefix: str) -> Tuple[str, List[Tuple[str, float]]]:
    pattern = re.compile(r"_fold(\d+)_([^/]+?)_gate_corrected_summary\.json$")
    values: List[Tuple[str, float]] = []
    for path in _completed_gate_files(prefix):
        payload = _read_json(path)
        metrics = payload.get("classification_metrics", {}) if isinstance(payload, dict) else {}
        value = None
        if isinstance(metrics, dict):
            raw = metrics.get("branch_macro_f1")
            if raw is not None:
                try:
                    value = float(raw)
                except Exception:
                    value = None
        if value is None:
            continue
        m = pattern.search(path)
        fold_name = f"fold{m.group(1)}_{m.group(2)}" if m else os.path.basename(path)
        fold_name = _fold_brief(fold_name)
        values.append((fold_name, value))
    if not values:
        return "-", []
    avg = sum(v for _n, v in values) / len(values)
    recent = values[-5:]
    return f"{avg:.3f}", recent


def _overall_eta_seconds(prefix: str, total_folds: int) -> float | None:
    files = _completed_gate_files(prefix)
    done = len(files)
    if done >= total_folds:
        return 0.0

    completed_totals = _completed_fold_total_estimates(prefix)
    avg_fold_sec = None
    if completed_totals:
        avg_fold_sec = sum(completed_totals) / len(completed_totals)
    elif done > 0:
        first = os.path.getmtime(files[0])
        avg_fold_sec = max(time.time() - first, 1.0)

    active = _active_progress(prefix)
    current_remaining = 0.0
    active_fold_base = None
    if active is not None:
        active_fold_base, _stage_name, payload = active
        if avg_fold_sec is not None:
            current_elapsed = _fold_elapsed_estimate(prefix, active_fold_base)
            if current_elapsed <= 0.0:
                current_elapsed = _progress_elapsed(payload)
            current_remaining = max(avg_fold_sec - current_elapsed, 0.0)
        else:
            current_remaining = _progress_eta(payload) or 0.0

    if avg_fold_sec is None and current_remaining <= 0.0:
        return None

    remaining_after_current = max(total_folds - done - (1 if active_fold_base else 0), 0)
    return current_remaining + (avg_fold_sec or 0.0) * remaining_after_current


def _summary_line(prefix: str, total_folds: int, color: bool) -> str:
    counts = _counts(prefix)
    completed = counts["gate_corrected"]
    pct = 100.0 * completed / max(total_folds, 1)
    bar = _progress_bar(completed, total_folds)
    return (
        f"{bar} {pct:5.1f}%   "
        f"train_eval={counts['train_eval']}  "
        f"ds={counts['branch_dataset']}  "
        f"train={counts['train_branch']}  "
        f"eval0={counts['eval_baseline']}  "
        f"gate0={counts['gate_baseline']}  "
        f"eval1={counts['eval_corrected']}  "
        f"gate1={_style(color, str(counts['gate_corrected']), GREEN if completed else YELLOW)}"
    )


def _compact_metric(value: object) -> str:
    try:
        if isinstance(value, bool):
            return str(value)
        num = float(value)
        return f"{num:.3f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _monitor_status(lines: List[str], *, final_exists: bool, has_active_progress: bool) -> Tuple[str, str]:
    if lines:
        return "RUNNING", GREEN
    if final_exists:
        return "COMPLETED", CYAN
    if has_active_progress:
        return "STALE", YELLOW
    return "STOPPED", RED


def _print_once(prefix: str, total_folds: int, color: bool) -> None:
    lines = _proc_lines(prefix)
    counts = _counts(prefix)
    completed = counts["gate_corrected"]
    final_summary = f"{prefix}_summary.json"
    final_exists = os.path.exists(final_summary)
    active = _active_progress(prefix)
    status, status_col = _monitor_status(lines, final_exists=final_exists, has_active_progress=active is not None)
    current_fold = _extract_current_fold(lines)
    active_stage = "-"
    current_fold_eta = "-"
    current_fold_prog = "-"
    current_target = "-"
    current_detail = "-"
    current_phase_prog = "-"
    if active is not None and status != "COMPLETED":
        active_fold_base, active_stage, payload = active
        current_fold = active_fold_base
        ratio = _progress_ratio(payload)
        if ratio is not None:
            current_fold_prog = f"{ratio*100.0:.1f}%"
        current_fold_eta = _format_eta(_progress_eta(payload))
        current_target = str(payload.get("current_target", "") or "-")
        current_detail = str(payload.get("stage_detail", "") or "-")
        try:
            sub_ratio = 100.0 * float(payload.get("target_subprogress_ratio", 0.0) or 0.0)
            phase_step = int(payload.get("phase_step", 0) or 0)
            phase_total_steps = int(payload.get("phase_total_steps", 0) or 0)
            if phase_total_steps > 0:
                current_phase_prog = f"{_sub_bar(sub_ratio)} {sub_ratio:5.1f}%  step={phase_step}/{phase_total_steps}"
            else:
                current_phase_prog = f"{_sub_bar(sub_ratio)} {sub_ratio:5.1f}%"
        except Exception:
            current_phase_prog = "-"
    passed, failed = _pass_fail_counts(prefix)
    branch_f1_avg, branch_f1_recent = _branch_f1_stats(prefix)
    overall_eta = _format_eta(_overall_eta_seconds(prefix, total_folds))
    proc_count, proc_roles = _proc_roles(lines)
    latest_brief = _latest_file_brief(prefix)
    active_stage_brief = STAGE_BRIEFS.get(active_stage, active_stage)
    current_fold_brief = _fold_brief(current_fold)
    print(_style(color, "=" * 88, CYAN))
    print(_style(color, "IDP HOLDOUT", BOLD, CYAN) + f"  {_style(color, status, BOLD, status_col)}")
    print(
        f"fold {_style(color, current_fold_brief, BOLD, MAGENTA)}"
        f" | stage {_style(color, active_stage_brief, CYAN)}"
        f" | target {_style(color, current_target, BLUE)}"
        f" | detail {_style(color, current_detail, MAGENTA)}"
    )
    print(
        f"done {completed}/{total_folds}"
        f" | pass {_style(color, str(passed), GREEN)}"
        f" | fail {_style(color, str(failed), RED if failed else YELLOW)}"
        f" | eta_fold {_style(color, current_fold_eta, YELLOW)}"
        f" | eta_total {_style(color, overall_eta, YELLOW)}"
    )
    print(f"fold% {_style(color, current_fold_prog, BLUE)}  {_style(color, current_phase_prog, CYAN)}")
    print(f"all%  {_summary_line(prefix, total_folds, color)}")
    print(
        f"actors {proc_count} [{_style(color, proc_roles, GREEN if proc_count else DIM)}]"
        f" | branch_f1 {_style(color, branch_f1_avg, CYAN)}"
    )
    print(f"pulse {_style(color, latest_brief, BLUE)}")
    print(_style(color, "-" * 88, GRAY))
    print(_style(color, "recent", BOLD))
    recent = _recent_completed_folds(prefix, limit=6)
    if recent:
        print("  " + " | ".join(f"{_style(color, fold_name, GREEN)} {age_sec}s" for fold_name, age_sec in recent))
    else:
        print(f"  {_style(color, '(none yet)', DIM)}")
    recent_metrics = _recent_completed_fold_metrics(prefix, limit=3)
    if recent_metrics:
        print(_style(color, "-" * 88, GRAY))
        print(_style(color, "gate", BOLD))
        for fold_name, metric_payload in recent_metrics:
            print(
                "  "
                f"{_style(color, fold_name, MAGENTA)}   "
                f"pass={metric_payload['pass']}  "
                f"state={_compact_metric(metric_payload['state_acc'])}  "
                f"llps={_compact_metric(metric_payload['llps_pr_auc'])}  "
                f"agg={_compact_metric(metric_payload['agg_pr_auc'])}  "
                f"compact={_compact_metric(metric_payload['compact_auc'])}  "
                f"hel={_compact_metric(metric_payload['helicity_auc'])}  "
                f"cond={_compact_metric(metric_payload['condense_auc'])}"
            )
    if branch_f1_recent:
        print(_style(color, "-" * 88, GRAY))
        print(_style(color, "branch_f1_recent", BOLD))
        for fold_name, value in branch_f1_recent:
            color_code = GREEN if value >= 0.75 else YELLOW if value >= 0.5 else RED
            print(f"  {_style(color, fold_name, MAGENTA)}   f1={_style(color, f'{value:.3f}', color_code)}")
    print(_style(color, "-" * 88, GRAY))
    print(f"final_summary_exists {_style(color, str(final_exists), GREEN if final_exists else YELLOW)}")
    print(_style(color, "=" * 88, CYAN))


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor IDP holdout progress.")
    parser.add_argument("--prefix", required=True, type=str)
    parser.add_argument("--total-folds", type=int, default=0)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--clear-screen", action="store_true")
    parser.add_argument("--color", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()
    use_color = True
    if args.no_color:
        use_color = False
    elif args.color:
        use_color = True

    while True:
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        inferred_total_folds = _infer_total_folds(str(args.prefix), int(args.total_folds))
        _print_once(str(args.prefix), inferred_total_folds, use_color)
        if not args.loop:
            break
        time.sleep(max(float(args.interval_sec), 0.5))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
