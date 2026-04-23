#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from core.definitions import ResearchConstants


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip()
    if s.lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in s.split(",") if x.strip()]
    if not out:
        raise ValueError(f"no targets parsed from spec: {spec}")
    return out


def _validate_required_columns(df: pd.DataFrame) -> None:
    required = {
        "target",
        "ai_interval",
        "speedup_vs_interval1",
        "rmsd_vs_interval1_aligned",
    }
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"sweep target csv missing required columns: {missing}")


def _pick_baseline_interval(group: pd.DataFrame, baseline_interval: int) -> int:
    vals = sorted(set(int(x) for x in group["ai_interval"].tolist()))
    if int(baseline_interval) in vals:
        return int(baseline_interval)
    return int(vals[0])


def _pick_best_row(
    group: pd.DataFrame,
    min_speedup: float,
    max_aligned_loss: float,
    baseline_interval: int,
) -> Tuple[pd.Series, str]:
    g = group.copy()
    g["ai_interval"] = g["ai_interval"].astype(int)
    g["speedup_vs_interval1"] = g["speedup_vs_interval1"].astype(float)
    g["rmsd_vs_interval1_aligned"] = g["rmsd_vs_interval1_aligned"].astype(float)

    feasible = g[
        (g["speedup_vs_interval1"] >= float(min_speedup))
        & (g["rmsd_vs_interval1_aligned"] <= float(max_aligned_loss))
    ].copy()
    if not feasible.empty:
        feasible = feasible.sort_values(
            ["speedup_vs_interval1", "rmsd_vs_interval1_aligned", "ai_interval"],
            ascending=[False, True, True],
        )
        return feasible.iloc[0], "threshold_pass"

    base_rows = g[g["ai_interval"] == int(baseline_interval)].copy()
    if base_rows.empty:
        base_rows = g.sort_values(["ai_interval"], ascending=[True]).head(1)
    return base_rows.iloc[0], "fallback_baseline"


def build_policy_from_sweep_df(
    df: pd.DataFrame,
    targets: List[str],
    min_speedup: float,
    max_aligned_loss: float,
    baseline_interval: int,
) -> Tuple[pd.DataFrame, Dict[str, int], Dict[str, Any]]:
    _validate_required_columns(df)
    rows: List[Dict[str, Any]] = []
    policy: Dict[str, int] = {}
    targets_set = set(targets)

    for target in targets:
        sub = df[df["target"] == target].copy()
        if sub.empty:
            raise ValueError(f"target '{target}' not found in sweep target csv")
        base_i = _pick_baseline_interval(sub, baseline_interval=int(baseline_interval))
        best_row, reason = _pick_best_row(
            group=sub,
            min_speedup=float(min_speedup),
            max_aligned_loss=float(max_aligned_loss),
            baseline_interval=int(base_i),
        )
        chosen_interval = int(best_row["ai_interval"])
        policy[target] = chosen_interval
        rows.append(
            {
                "target": target,
                "selected_ai_interval": chosen_interval,
                "selection_reason": reason,
                "selected_speedup_vs_interval1": float(best_row["speedup_vs_interval1"]),
                "selected_rmsd_vs_interval1_aligned": float(best_row["rmsd_vs_interval1_aligned"]),
                "baseline_interval": int(base_i),
                "available_intervals": ",".join(str(x) for x in sorted(set(int(v) for v in sub["ai_interval"]))),
            }
        )

    out_df = pd.DataFrame(rows).sort_values("target").reset_index(drop=True)
    threshold_pass_targets = int((out_df["selection_reason"] == "threshold_pass").sum())
    summary = {
        "targets": int(len(targets)),
        "targets_requested": sorted(list(targets_set)),
        "targets_threshold_pass": threshold_pass_targets,
        "targets_fallback_baseline": int(len(targets) - threshold_pass_targets),
        "min_speedup": float(min_speedup),
        "max_aligned_loss": float(max_aligned_loss),
        "baseline_interval_default": int(baseline_interval),
        "avg_selected_speedup": float(out_df["selected_speedup_vs_interval1"].mean()),
        "avg_selected_rmsd_vs_interval1_aligned": float(out_df["selected_rmsd_vs_interval1_aligned"].mean()),
    }
    return out_df, policy, summary


def _policy_spec_string(policy: Dict[str, int]) -> str:
    return ",".join(f"{k}={int(v)}" for k, v in sorted(policy.items()))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build target-specific AI interval policy from sweep target CSV."
    )
    p.add_argument("--sweep-target-csv", type=str, required=True)
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--min-speedup", type=float, default=1.25)
    p.add_argument("--max-aligned-loss", type=float, default=0.20)
    p.add_argument("--baseline-interval", type=int, default=1)
    p.add_argument("--policy-name", type=str, default="auto_from_sweep_v1")
    p.add_argument("--out-csv", type=str, default="runs/target_ai_interval_policy_auto.csv")
    p.add_argument("--out-json", type=str, default="runs/target_ai_interval_policy_auto.json")
    p.add_argument("--out-spec", type=str, default="runs/target_ai_interval_policy_auto.spec.txt")
    return p


def run_build(args: argparse.Namespace) -> Dict[str, Any]:
    sweep_csv = os.path.abspath(str(args.sweep_target_csv))
    if not os.path.exists(sweep_csv):
        raise FileNotFoundError(f"sweep target csv not found: {sweep_csv}")

    targets = _parse_targets(str(args.targets))
    df = pd.read_csv(sweep_csv)
    rows_df, policy, summary = build_policy_from_sweep_df(
        df=df,
        targets=targets,
        min_speedup=float(args.min_speedup),
        max_aligned_loss=float(args.max_aligned_loss),
        baseline_interval=int(args.baseline_interval),
    )
    policy_spec = _policy_spec_string(policy)

    out_csv = os.path.abspath(str(args.out_csv))
    out_json = os.path.abspath(str(args.out_json))
    out_spec = os.path.abspath(str(args.out_spec))
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_spec) or ".", exist_ok=True)
    rows_df.to_csv(out_csv, index=False)
    with open(out_spec, "w", encoding="utf-8") as f:
        f.write(policy_spec + "\n")

    payload = {
        "meta": {
            "policy_name": str(args.policy_name),
            "source_sweep_target_csv": sweep_csv,
        },
        "summary": summary,
        "policy": policy,
        "policy_spec": policy_spec,
        "rows": rows_df.to_dict(orient="records"),
        "files": {
            "out_csv": out_csv,
            "out_spec": out_spec,
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_build(args)
    print(
        json.dumps(
            {
                "policy_name": payload["meta"]["policy_name"],
                "targets": payload["summary"]["targets"],
                "targets_threshold_pass": payload["summary"]["targets_threshold_pass"],
                "avg_selected_speedup": payload["summary"]["avg_selected_speedup"],
                "avg_selected_rmsd_vs_interval1_aligned": payload["summary"][
                    "avg_selected_rmsd_vs_interval1_aligned"
                ],
                "out_csv": payload["files"]["out_csv"],
                "out_json": os.path.abspath(str(args.out_json)),
                "out_spec": payload["files"]["out_spec"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
