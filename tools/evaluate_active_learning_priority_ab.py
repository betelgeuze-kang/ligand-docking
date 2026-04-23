#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Set

import pandas as pd


def _norm_target(name: Any) -> str:
    s = str(name).strip()
    if not s:
        return ""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _read_csv(path: str) -> pd.DataFrame:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return pd.DataFrame()
    try:
        return pd.read_csv(src)
    except Exception:
        return pd.DataFrame()


def _targets_set(df: pd.DataFrame) -> Set[str]:
    if df.empty or ("target" not in df.columns):
        return set()
    out: Set[str] = set()
    for v in df["target"].tolist():
        k = _norm_target(v)
        if k:
            out.add(k)
    return out


def _ood_high_rmsd_targets(df: pd.DataFrame, *, min_rmsd: float) -> Set[str]:
    if df.empty or ("target" not in df.columns):
        return set()
    work = df.copy()
    if "paired" in work.columns:
        work["paired_i"] = pd.to_numeric(work["paired"], errors="coerce").fillna(0).astype(int)
        work = work[work["paired_i"] == 1]
    rmsd_col = "rmsd_aligned_A" if "rmsd_aligned_A" in work.columns else ""
    if not rmsd_col:
        return set()
    work["rmsd_f"] = pd.to_numeric(work[rmsd_col], errors="coerce")
    work = work[work["rmsd_f"] >= float(min_rmsd)]
    out: Set[str] = set()
    for v in work["target"].tolist():
        k = _norm_target(v)
        if k:
            out.add(k)
    return out


def evaluate_ab(
    *,
    baseline_csv: str,
    candidate_csv: str,
    ood_pair_csv: str,
    ood_min_rmsd: float,
    out_json: str,
    out_csv: str,
) -> Dict[str, Any]:
    base_df = _read_csv(baseline_csv)
    cand_df = _read_csv(candidate_csv)
    ood_df = _read_csv(ood_pair_csv)

    a = _targets_set(base_df)
    b = _targets_set(cand_df)
    inter = a & b
    union = a | b
    add_b = sorted(list(b - a))
    del_b = sorted(list(a - b))
    jaccard = float(len(inter) / max(len(union), 1))

    high_rmsd = _ood_high_rmsd_targets(ood_df, min_rmsd=float(ood_min_rmsd))
    cov_a = None
    cov_b = None
    cov_delta = None
    if len(high_rmsd) > 0:
        cov_a = float(len(a & high_rmsd) / len(high_rmsd))
        cov_b = float(len(b & high_rmsd) / len(high_rmsd))
        cov_delta = float(cov_b - cov_a)

    feature_selected = 0
    if (not cand_df.empty) and ("priority_source" in cand_df.columns):
        feature_selected = int((cand_df["priority_source"].astype(str) == "feature_control_hardcase").sum())

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "baseline_csv": str(baseline_csv),
            "candidate_csv": str(candidate_csv),
            "ood_pair_csv": str(ood_pair_csv),
            "ood_min_rmsd": float(ood_min_rmsd),
        },
        "summary": {
            "baseline_count": int(len(a)),
            "candidate_count": int(len(b)),
            "intersection_count": int(len(inter)),
            "union_count": int(len(union)),
            "jaccard": float(jaccard),
            "added_in_candidate_count": int(len(add_b)),
            "removed_in_candidate_count": int(len(del_b)),
            "feature_selected_in_candidate": int(feature_selected),
            "ood_high_rmsd_count": int(len(high_rmsd)),
            "ood_coverage_baseline": cov_a,
            "ood_coverage_candidate": cov_b,
            "ood_coverage_delta": cov_delta,
        },
        "details": {
            "added_in_candidate": add_b,
            "removed_in_candidate": del_b,
        },
    }

    os.makedirs(os.path.dirname(str(out_json)) or ".", exist_ok=True)
    with open(str(out_json), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    os.makedirs(os.path.dirname(str(out_csv)) or ".", exist_ok=True)
    with open(str(out_csv), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "baseline_count",
                "candidate_count",
                "intersection_count",
                "union_count",
                "jaccard",
                "added_in_candidate_count",
                "removed_in_candidate_count",
                "feature_selected_in_candidate",
                "ood_high_rmsd_count",
                "ood_coverage_baseline",
                "ood_coverage_candidate",
                "ood_coverage_delta",
            ],
        )
        w.writeheader()
        w.writerow(summary["summary"])
    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Evaluate baseline vs feature-augmented active-learning priority targets."
    )
    p.add_argument("--baseline-csv", type=str, required=True)
    p.add_argument("--candidate-csv", type=str, required=True)
    p.add_argument("--ood-pair-csv", type=str, default="")
    p.add_argument("--ood-min-rmsd", type=float, default=8.0)
    p.add_argument("--out-json", type=str, default=f"runs/active_learning_priority_ab_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/active_learning_priority_ab_{stamp}.csv")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = evaluate_ab(
        baseline_csv=str(args.baseline_csv),
        candidate_csv=str(args.candidate_csv),
        ood_pair_csv=str(args.ood_pair_csv),
        ood_min_rmsd=float(args.ood_min_rmsd),
        out_json=str(args.out_json),
        out_csv=str(args.out_csv),
    )
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
