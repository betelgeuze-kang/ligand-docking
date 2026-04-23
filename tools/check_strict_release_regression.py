#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, Optional, Sequence

import pandas as pd


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _resolve_accuracy_csv(summary_payload: Dict[str, Any]) -> str:
    artifacts = summary_payload.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return ""
    path = str(artifacts.get("accuracy_external_csv", "")).strip()
    if path:
        return path
    return str(artifacts.get("accuracy_csv", "")).strip()


def _read_metric_mean(csv_path: str, column: str) -> Optional[float]:
    if not csv_path:
        return None
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    if column not in df.columns:
        return None
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.mean())


def _fail(
    failures: list[Dict[str, Any]],
    metric: str,
    baseline: Any,
    candidate: Any,
    threshold: Any,
    condition: str,
) -> None:
    failures.append(
        {
            "metric": str(metric),
            "baseline": baseline,
            "candidate": candidate,
            "threshold": threshold,
            "condition": str(condition),
        }
    )


def run_check(args: argparse.Namespace) -> Dict[str, Any]:
    baseline = _load_json(str(args.baseline_summary_json))
    candidate = _load_json(str(args.candidate_summary_json))

    baseline_acc_csv = str(args.baseline_accuracy_csv).strip() or _resolve_accuracy_csv(baseline)
    candidate_acc_csv = str(args.candidate_accuracy_csv).strip() or _resolve_accuracy_csv(candidate)

    b_summary = baseline.get("summary", {})
    c_summary = candidate.get("summary", {})
    b_gates = baseline.get("gates", {})
    c_gates = candidate.get("gates", {})
    b_acc_gate = b_gates.get("accuracy_gate", {})
    c_acc_gate = c_gates.get("accuracy_gate", {})
    b_speed = b_gates.get("speed", {})
    c_speed = c_gates.get("speed", {})

    b_speedup = _safe_float(b_speed.get("avg_speedup_on_vs_off"), default=0.0)
    c_speedup = _safe_float(c_speed.get("avg_speedup_on_vs_off"), default=0.0)
    b_e2e_rmse = _safe_float(b_acc_gate.get("avg_e2e_rmse_raw"), default=0.0)
    c_e2e_rmse = _safe_float(c_acc_gate.get("avg_e2e_rmse_raw"), default=0.0)
    b_e2e_rel = _safe_float(b_acc_gate.get("avg_e2e_rel_rmse_mean_clipped"), default=0.0)
    c_e2e_rel = _safe_float(c_acc_gate.get("avg_e2e_rel_rmse_mean_clipped"), default=0.0)
    b_jaccard = _safe_float(b_acc_gate.get("avg_neighbor_jaccard"), default=0.0)
    c_jaccard = _safe_float(c_acc_gate.get("avg_neighbor_jaccard"), default=0.0)

    b_rmsd_aligned = _read_metric_mean(baseline_acc_csv, "avg_rmsd_aligned")
    c_rmsd_aligned = _read_metric_mean(candidate_acc_csv, "avg_rmsd_aligned")
    b_rmsd_native_aligned = _read_metric_mean(baseline_acc_csv, "avg_rmsd_vs_native_aligned")
    c_rmsd_native_aligned = _read_metric_mean(candidate_acc_csv, "avg_rmsd_vs_native_aligned")

    failures: list[Dict[str, Any]] = []

    if bool(args.require_candidate_pass) and (not bool(c_summary.get("pass", False))):
        _fail(
            failures,
            metric="candidate_summary.pass",
            baseline=bool(b_summary.get("pass", False)),
            candidate=bool(c_summary.get("pass", False)),
            threshold=True,
            condition="candidate must pass strict summary gate",
        )

    min_speed = b_speedup * float(args.min_speedup_ratio)
    if c_speedup < min_speed:
        _fail(
            failures,
            metric="avg_speedup_on_vs_off",
            baseline=b_speedup,
            candidate=c_speedup,
            threshold=min_speed,
            condition="candidate >= baseline * min_speedup_ratio",
        )

    e2e_rmse_increase = c_e2e_rmse - b_e2e_rmse
    if e2e_rmse_increase > float(args.max_avg_e2e_rmse_increase):
        _fail(
            failures,
            metric="avg_e2e_rmse_raw",
            baseline=b_e2e_rmse,
            candidate=c_e2e_rmse,
            threshold=float(args.max_avg_e2e_rmse_increase),
            condition="candidate - baseline <= max_avg_e2e_rmse_increase",
        )

    e2e_rel_increase = c_e2e_rel - b_e2e_rel
    if e2e_rel_increase > float(args.max_avg_e2e_rel_rmse_increase):
        _fail(
            failures,
            metric="avg_e2e_rel_rmse_mean_clipped",
            baseline=b_e2e_rel,
            candidate=c_e2e_rel,
            threshold=float(args.max_avg_e2e_rel_rmse_increase),
            condition="candidate - baseline <= max_avg_e2e_rel_rmse_increase",
        )

    jaccard_drop = b_jaccard - c_jaccard
    if jaccard_drop > float(args.max_avg_neighbor_jaccard_drop):
        _fail(
            failures,
            metric="avg_neighbor_jaccard",
            baseline=b_jaccard,
            candidate=c_jaccard,
            threshold=float(args.max_avg_neighbor_jaccard_drop),
            condition="baseline - candidate <= max_avg_neighbor_jaccard_drop",
        )

    rmsd_aligned_increase = None
    if (b_rmsd_aligned is not None) and (c_rmsd_aligned is not None):
        rmsd_aligned_increase = float(c_rmsd_aligned - b_rmsd_aligned)
        if rmsd_aligned_increase > float(args.max_avg_rmsd_aligned_increase):
            _fail(
                failures,
                metric="avg_rmsd_aligned",
                baseline=b_rmsd_aligned,
                candidate=c_rmsd_aligned,
                threshold=float(args.max_avg_rmsd_aligned_increase),
                condition="candidate - baseline <= max_avg_rmsd_aligned_increase",
            )

    rmsd_native_aligned_increase = None
    if (b_rmsd_native_aligned is not None) and (c_rmsd_native_aligned is not None):
        rmsd_native_aligned_increase = float(c_rmsd_native_aligned - b_rmsd_native_aligned)
        if rmsd_native_aligned_increase > float(args.max_avg_rmsd_vs_native_aligned_increase):
            _fail(
                failures,
                metric="avg_rmsd_vs_native_aligned",
                baseline=b_rmsd_native_aligned,
                candidate=c_rmsd_native_aligned,
                threshold=float(args.max_avg_rmsd_vs_native_aligned_increase),
                condition="candidate - baseline <= max_avg_rmsd_vs_native_aligned_increase",
            )

    summary = {
        "pass": len(failures) == 0,
        "failure_count": int(len(failures)),
        "candidate_pass": bool(c_summary.get("pass", False)),
        "baseline_pass": bool(b_summary.get("pass", False)),
    }

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "baseline_summary_json": str(args.baseline_summary_json),
            "candidate_summary_json": str(args.candidate_summary_json),
            "baseline_accuracy_csv": baseline_acc_csv,
            "candidate_accuracy_csv": candidate_acc_csv,
        },
        "thresholds": {
            "min_speedup_ratio": float(args.min_speedup_ratio),
            "max_avg_e2e_rmse_increase": float(args.max_avg_e2e_rmse_increase),
            "max_avg_e2e_rel_rmse_increase": float(args.max_avg_e2e_rel_rmse_increase),
            "max_avg_neighbor_jaccard_drop": float(args.max_avg_neighbor_jaccard_drop),
            "max_avg_rmsd_aligned_increase": float(args.max_avg_rmsd_aligned_increase),
            "max_avg_rmsd_vs_native_aligned_increase": float(args.max_avg_rmsd_vs_native_aligned_increase),
            "require_candidate_pass": bool(args.require_candidate_pass),
        },
        "metrics": {
            "speedup": {"baseline": b_speedup, "candidate": c_speedup, "delta": float(c_speedup - b_speedup)},
            "e2e_rmse_raw": {"baseline": b_e2e_rmse, "candidate": c_e2e_rmse, "delta": float(e2e_rmse_increase)},
            "e2e_rel_rmse_clipped": {
                "baseline": b_e2e_rel,
                "candidate": c_e2e_rel,
                "delta": float(e2e_rel_increase),
            },
            "neighbor_jaccard": {"baseline": b_jaccard, "candidate": c_jaccard, "delta": float(c_jaccard - b_jaccard)},
            "avg_rmsd_aligned": {
                "baseline": b_rmsd_aligned,
                "candidate": c_rmsd_aligned,
                "delta": rmsd_aligned_increase,
            },
            "avg_rmsd_vs_native_aligned": {
                "baseline": b_rmsd_native_aligned,
                "candidate": c_rmsd_native_aligned,
                "delta": rmsd_native_aligned_increase,
            },
        },
        "summary": summary,
        "failures": failures,
    }

    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    pd.DataFrame(
        [
            {
                "pass": bool(summary["pass"]),
                "failure_count": int(summary["failure_count"]),
                "speedup_baseline": b_speedup,
                "speedup_candidate": c_speedup,
                "speedup_delta": float(c_speedup - b_speedup),
                "e2e_rmse_baseline": b_e2e_rmse,
                "e2e_rmse_candidate": c_e2e_rmse,
                "e2e_rmse_delta": float(e2e_rmse_increase),
                "rmsd_aligned_baseline": b_rmsd_aligned,
                "rmsd_aligned_candidate": c_rmsd_aligned,
                "rmsd_aligned_delta": rmsd_aligned_increase,
                "rmsd_vs_native_aligned_baseline": b_rmsd_native_aligned,
                "rmsd_vs_native_aligned_candidate": c_rmsd_native_aligned,
                "rmsd_vs_native_aligned_delta": rmsd_native_aligned_increase,
            }
        ]
    ).to_csv(str(args.out_csv), index=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Compare strict-release candidate vs baseline and fail on speed/accuracy regression thresholds."
    )
    p.add_argument("--baseline-summary-json", type=str, required=True)
    p.add_argument("--candidate-summary-json", type=str, required=True)
    p.add_argument("--baseline-accuracy-csv", type=str, default="")
    p.add_argument("--candidate-accuracy-csv", type=str, default="")
    p.add_argument("--min-speedup-ratio", type=float, default=0.95)
    p.add_argument("--max-avg-e2e-rmse-increase", type=float, default=0.005)
    p.add_argument("--max-avg-e2e-rel-rmse-increase", type=float, default=1e-6)
    p.add_argument("--max-avg-neighbor-jaccard-drop", type=float, default=0.0)
    p.add_argument("--max-avg-rmsd-aligned-increase", type=float, default=0.02)
    p.add_argument("--max-avg-rmsd-vs-native-aligned-increase", type=float, default=0.01)
    p.add_argument("--require-candidate-pass", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-json", type=str, default=f"runs/strict_release_regression_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/strict_release_regression_{stamp}.csv")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_check(args)
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote CSV: {args.out_csv}")
    if not bool(payload.get("summary", {}).get("pass", False)):
        sys.exit(2)


if __name__ == "__main__":
    main()

