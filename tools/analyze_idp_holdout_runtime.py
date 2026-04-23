#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


STAGE_SUFFIXES: List[Tuple[str, str]] = [
    ("train_eval", "_train_eval_summary.json"),
    ("branch_dataset", "_train_branch_dataset_summary.json"),
    ("train_branch", "_train_branch_summary.json"),
    ("eval_baseline", "_eval_baseline_summary.json"),
    ("gate_baseline", "_gate_baseline_summary.json"),
    ("eval_corrected", "_eval_corrected_summary.json"),
    ("gate_corrected", "_gate_corrected_summary.json"),
]

PROGRESS_SUFFIXES: Dict[str, str] = {
    "train_eval": "_train_eval_progress.json",
    "train_branch": "_train_branch_progress.json",
    "eval_baseline": "_eval_baseline_progress.json",
    "eval_corrected": "_eval_corrected_progress.json",
}

FOLD_RE = re.compile(r"^(?P<prefix>.+?)_fold(?P<fold>\d+)_(?P<holdout>.+)$")
MAX_FALLBACK_STAGE_SEC = 300.0


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _fmt_sec(sec: float) -> str:
    return str(dt.timedelta(seconds=int(max(sec, 0.0))))


def _find_fold_bases(prefix: str) -> List[Tuple[int, str, str]]:
    found: Dict[Tuple[int, str], str] = {}
    pattern = prefix + "_fold*_gate_corrected_summary.json"
    for path in glob.glob(pattern):
        base = path[: -len("_gate_corrected_summary.json")]
        m = FOLD_RE.match(base)
        if not m:
            continue
        fold = int(m.group("fold"))
        holdout = m.group("holdout")
        found[(fold, holdout)] = base
    return [(fold, holdout, base) for (fold, holdout), base in sorted(found.items())]


def _mtime(path: str) -> Optional[float]:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _stage_elapsed_from_progress(base: str, stage: str) -> Optional[float]:
    suffix = PROGRESS_SUFFIXES.get(stage)
    if not suffix:
        return None
    payload = _read_json(base + suffix)
    if not payload:
        return None
    try:
        return float(payload.get("elapsed_sec", 0.0) or 0.0)
    except Exception:
        return None


def _stage_elapsed_from_summary(base: str, stage: str) -> Optional[float]:
    summary_path = f"{base}_{stage}_summary.json"
    payload = _read_json(summary_path)
    if not payload:
        return None
    try:
        runtime = payload.get("runtime_timing", {}) or {}
        if stage in {"train_eval", "eval_baseline", "eval_corrected"}:
            sec = float(runtime.get("target_total_sec", 0.0) or 0.0)
            return sec if sec > 0.0 else None
        if stage == "train_branch":
            sec = float(payload.get("training_time_sec", payload.get("elapsed_sec", 0.0)) or 0.0)
            return sec if sec > 0.0 else None
        if stage == "branch_dataset":
            sec = float(payload.get("elapsed_sec", 0.0) or 0.0)
            return sec if sec > 0.0 else None
    except Exception:
        return None
    return None


def _stage_times(base: str) -> Dict[str, float]:
    stage_mtimes: Dict[str, float] = {}
    for stage, suffix in STAGE_SUFFIXES:
        ts = _mtime(base + suffix)
        if ts is not None:
            stage_mtimes[stage] = ts
    if not stage_mtimes:
        return {}
    times: Dict[str, float] = {}
    # Prefer explicit stage timing recorded in summary/progress files. This is
    # robust to resumed runs where file mtimes can jump far ahead of earlier stages.
    for stage, _suffix in STAGE_SUFFIXES:
        direct = _stage_elapsed_from_summary(base, stage)
        if direct is not None:
            times[stage] = direct
            continue
        progress_elapsed = _stage_elapsed_from_progress(base, stage)
        if progress_elapsed is not None and progress_elapsed > 0.0:
            times[stage] = progress_elapsed

    # Fall back to mtime deltas only for stages without explicit timing. Use
    # canonical stage order rather than sorted mtimes so resumed/replayed folds
    # do not inflate earlier stages.
    prev_ts: Optional[float] = None
    for stage, _suffix in STAGE_SUFFIXES:
        ts = stage_mtimes.get(stage)
        if ts is None:
            continue
        if stage in times:
            prev_ts = ts
            continue
        if prev_ts is None or ts < prev_ts:
            times[stage] = 0.0
        else:
            delta = max(ts - prev_ts, 0.0)
            times[stage] = delta if delta <= MAX_FALLBACK_STAGE_SEC else 0.0
        prev_ts = ts
    return times


def _extract_eval_rows(base: str, stage: str) -> int:
    path = f"{base}_{stage}_summary.json"
    payload = _read_json(path)
    if not payload:
        return 0
    try:
        return int(payload.get("target_count", 0) or 0)
    except Exception:
        return 0


def _extract_train_epochs(base: str) -> Dict[str, Any]:
    payload = _read_json(base + "_train_branch_summary.json") or {}
    return {
        "epochs_completed": int(payload.get("epochs_completed", 0) or 0),
        "max_epochs": int(payload.get("max_epochs", 0) or 0),
        "stopped_early": bool(payload.get("stopped_early", False)),
    }


def _extract_train_progress(base: str) -> Dict[str, Any]:
    payload = _read_json(base + "_train_branch_progress.json") or {}
    return {
        "best_epoch": payload.get("best_epoch"),
        "best_score": payload.get("best_score"),
        "train_rows": payload.get("train_rows"),
        "val_rows": payload.get("val_rows"),
    }


def _aggregate_target_hotspots(prefix: str) -> List[Tuple[str, float, int]]:
    files = glob.glob(prefix + "_fold*_train_eval_progress.json") + glob.glob(prefix + "_fold*_eval_corrected_progress.json")
    totals: Dict[str, List[float]] = collections.defaultdict(list)
    for path in files:
        payload = _read_json(path)
        if not payload:
            continue
        target = str(payload.get("current_target", "") or "").strip()
        elapsed = float(payload.get("elapsed_sec", 0.0) or 0.0)
        processed = int(payload.get("processed_targets", 0) or 0)
        if not target or processed <= 0 or elapsed <= 0.0:
            continue
        approx_per_target = elapsed / max(processed, 1)
        totals[target].append(approx_per_target)
    out: List[Tuple[str, float, int]] = []
    for target, vals in totals.items():
        out.append((target, sum(vals) / len(vals), len(vals)))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def analyze(prefix: str) -> Dict[str, Any]:
    folds = _find_fold_bases(prefix)
    fold_rows: List[Dict[str, Any]] = []
    stage_totals: Dict[str, float] = collections.defaultdict(float)
    for fold, holdout, base in folds:
        times = _stage_times(base)
        for stage, sec in times.items():
            stage_totals[stage] += sec
        train_epochs = _extract_train_epochs(base)
        train_progress = _extract_train_progress(base)
        corrected_gate = _read_json(base + "_gate_corrected_summary.json") or {}
        baseline_gate = _read_json(base + "_gate_baseline_summary.json") or {}
        fold_rows.append(
            {
                "fold": fold,
                "holdout": holdout,
                "base": base,
                "pass": bool(corrected_gate.get("pass", False)),
                "baseline_pass": bool(baseline_gate.get("pass", False)),
                "stage_times_sec": times,
                "total_stage_sec": float(sum(times.values())),
                "train_epochs": train_epochs,
                "train_progress": train_progress,
                "eval_rows_baseline": _extract_eval_rows(base, "eval_baseline"),
                "eval_rows_corrected": _extract_eval_rows(base, "eval_corrected"),
            }
        )
    fold_rows.sort(key=lambda row: row["total_stage_sec"], reverse=True)
    hotspots = _aggregate_target_hotspots(prefix)
    return {
        "prefix": prefix,
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "fold_count": len(folds),
        "stage_totals_sec": dict(stage_totals),
        "slowest_folds": fold_rows[:10],
        "target_hotspots": [
            {"target": target, "approx_sec_per_target": sec, "samples": samples}
            for target, sec, samples in hotspots[:15]
        ],
    }


def _render_md(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# IDP Holdout Runtime Analysis")
    lines.append("")
    lines.append(f"- prefix: `{payload['prefix']}`")
    lines.append(f"- fold_count: {payload['fold_count']}")
    lines.append("")
    lines.append("## Stage Totals")
    for stage, sec in sorted((payload.get("stage_totals_sec") or {}).items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- {stage}: {_fmt_sec(float(sec))} ({float(sec):.1f}s)")
    lines.append("")
    lines.append("## Slowest Folds")
    for row in payload.get("slowest_folds", []):
        lines.append(
            f"- fold{row['fold']} `{row['holdout']}`: {_fmt_sec(float(row['total_stage_sec']))} "
            f"(pass={row['pass']}, baseline_pass={row['baseline_pass']}, "
            f"epochs={row['train_epochs']['epochs_completed']}/{row['train_epochs']['max_epochs']})"
        )
        for stage, sec in sorted((row.get("stage_times_sec") or {}).items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - {stage}: {_fmt_sec(float(sec))} ({float(sec):.1f}s)")
    lines.append("")
    lines.append("## Target Hotspots")
    for row in payload.get("target_hotspots", []):
        lines.append(
            f"- `{row['target']}`: ~{_fmt_sec(float(row['approx_sec_per_target']))} per target "
            f"({float(row['approx_sec_per_target']):.1f}s, samples={row['samples']})"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze IDP holdout runtime bottlenecks from fold artifacts.")
    ap.add_argument("--prefix", required=True, help="Holdout run prefix, e.g. runs/idp_3bead_holdout_v7_on1_2026-03-15_r4")
    ap.add_argument("--out-json", default="", help="Optional output JSON path")
    ap.add_argument("--out-md", default="", help="Optional output Markdown path")
    args = ap.parse_args()

    payload = analyze(str(args.prefix))
    if str(args.out_json).strip():
        with open(str(args.out_json), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    if str(args.out_md).strip():
        with open(str(args.out_md), "w", encoding="utf-8") as f:
            f.write(_render_md(payload))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
