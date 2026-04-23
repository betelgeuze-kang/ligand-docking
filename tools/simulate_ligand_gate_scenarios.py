#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _parse_float_list(spec: str) -> List[float]:
    out: List[float] = []
    for tok in str(spec).split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(float(tok))
        except Exception:
            continue
    return out


def _run_pass(row: pd.Series, t: Dict[str, float]) -> bool:
    checks = [
        ("ranking_unique_auc", ">=", t["auc_unique_min"]),
        ("ranking_ood_unique_auc", ">=", t["auc_ood_min"]),
        ("ranking_pr_auc", ">=", t["pr_auc_min"]),
        ("ranking_ef1", ">=", t["ef1_min"]),
        ("ranking_bedroc", ">=", t["bedroc_min"]),
        ("ranking_brier", "<=", t["brier_max"]),
        ("ranking_ece", "<=", t["ece_max"]),
        ("ranking_roc_auc_ci_low", ">=", t["roc_auc_ci_low_min"]),
        ("ranking_pr_auc_ci_low", ">=", t["pr_auc_ci_low_min"]),
        ("ranking_ef1_ci_low", ">=", t["ef1_ci_low_min"]),
        ("ranking_topk_hit_rate", ">=", t["topk_hit_min"]),
    ]
    for col, op, thr in checks:
        v = row.get(col, None)
        if v is None or pd.isna(v):
            return False
        if op == ">=" and not (float(v) >= float(thr)):
            return False
        if op == "<=" and not (float(v) <= float(thr)):
            return False
    return True


def _first_fail_metric(row: pd.Series, t: Dict[str, float]) -> str:
    ordered = [
        ("ranking_unique_auc", ">=", t["auc_unique_min"]),
        ("ranking_ood_unique_auc", ">=", t["auc_ood_min"]),
        ("ranking_pr_auc", ">=", t["pr_auc_min"]),
        ("ranking_ef1", ">=", t["ef1_min"]),
        ("ranking_bedroc", ">=", t["bedroc_min"]),
        ("ranking_brier", "<=", t["brier_max"]),
        ("ranking_ece", "<=", t["ece_max"]),
        ("ranking_roc_auc_ci_low", ">=", t["roc_auc_ci_low_min"]),
        ("ranking_pr_auc_ci_low", ">=", t["pr_auc_ci_low_min"]),
        ("ranking_ef1_ci_low", ">=", t["ef1_ci_low_min"]),
        ("ranking_topk_hit_rate", ">=", t["topk_hit_min"]),
    ]
    for col, op, thr in ordered:
        v = row.get(col, None)
        if v is None or pd.isna(v):
            return f"{col}:missing"
        if op == ">=" and not (float(v) >= float(thr)):
            return f"{col}:{float(v):.6g}<{float(thr):.6g}"
        if op == "<=" and not (float(v) <= float(thr)):
            return f"{col}:{float(v):.6g}>{float(thr):.6g}"
    return ""


def run_sim(args: argparse.Namespace) -> Dict[str, Any]:
    runs_csv = str(args.runs_csv).strip()
    if (not runs_csv) or (not os.path.exists(runs_csv)):
        raise FileNotFoundError(f"runs csv not found: {runs_csv}")
    df = pd.read_csv(runs_csv)
    if df.empty:
        raise ValueError("runs csv is empty")
    req_cols = [
        "ligand_size",
        "repeat",
        "ranking_unique_auc",
        "ranking_ood_unique_auc",
        "ranking_pr_auc",
        "ranking_ef1",
        "ranking_bedroc",
        "ranking_brier",
        "ranking_ece",
        "ranking_roc_auc_ci_low",
        "ranking_pr_auc_ci_low",
        "ranking_ef1_ci_low",
    ]
    missing = [c for c in req_cols if c not in df.columns]
    if missing:
        raise ValueError(f"runs csv missing required columns: {missing}")
    if ("ranking_topk_hit_rate" not in df.columns) and ("topk_hit_rate" not in df.columns):
        raise ValueError("runs csv missing required columns: ['ranking_topk_hit_rate|topk_hit_rate']")

    # normalize legacy name
    if ("ranking_topk_hit_rate" not in df.columns) and ("topk_hit_rate" in df.columns):
        df["ranking_topk_hit_rate"] = pd.to_numeric(df["topk_hit_rate"], errors="coerce")
    if ("exists" in df.columns) and (not bool(args.include_pending)):
        df = df[df["exists"] == True].copy()  # noqa: E712
    if df.empty:
        raise ValueError("no completed rows available for simulation")

    grid = {
        "auc_unique_min": _parse_float_list(args.auc_unique_min_grid),
        "auc_ood_min": _parse_float_list(args.auc_ood_min_grid),
        "pr_auc_min": _parse_float_list(args.pr_auc_min_grid),
        "ef1_min": _parse_float_list(args.ef1_min_grid),
        "bedroc_min": _parse_float_list(args.bedroc_min_grid),
        "brier_max": _parse_float_list(args.brier_max_grid),
        "ece_max": _parse_float_list(args.ece_max_grid),
        "roc_auc_ci_low_min": _parse_float_list(args.roc_auc_ci_low_min_grid),
        "pr_auc_ci_low_min": _parse_float_list(args.pr_auc_ci_low_min_grid),
        "ef1_ci_low_min": _parse_float_list(args.ef1_ci_low_min_grid),
        "topk_hit_min": _parse_float_list(args.topk_hit_min_grid),
    }
    for k, vals in grid.items():
        if len(vals) <= 0:
            raise ValueError(f"empty threshold grid for {k}")

    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    scenario_rows: List[Dict[str, Any]] = []
    detail_rows: List[Dict[str, Any]] = []

    for idx, combo in enumerate(combos, start=1):
        t = {k: float(v) for k, v in zip(keys, combo)}
        pass_flags: List[bool] = []
        fail_metric_counter: Dict[str, int] = {}
        for _, r in df.iterrows():
            ok = _run_pass(r, t)
            pass_flags.append(bool(ok))
            fail_metric = ""
            if not ok:
                fail_metric = _first_fail_metric(r, t)
                fail_metric_counter[fail_metric] = int(fail_metric_counter.get(fail_metric, 0) + 1)
            detail_rows.append(
                {
                    "scenario_id": idx,
                    "ligand_size": int(r["ligand_size"]),
                    "repeat": int(r["repeat"]),
                    "pass": bool(ok),
                    "first_fail": fail_metric,
                }
            )
        pass_runs = int(sum(1 for x in pass_flags if x))
        total_runs = int(len(pass_flags))
        pass_rate = float(pass_runs / total_runs) if total_runs > 0 else 0.0
        primary_fail = ""
        if fail_metric_counter:
            primary_fail = sorted(fail_metric_counter.items(), key=lambda kv: kv[1], reverse=True)[0][0]
        strictness = (
            t["auc_unique_min"]
            + t["auc_ood_min"]
            + t["pr_auc_min"]
            + 0.05 * t["ef1_min"]
            + 0.05 * t["bedroc_min"]
            - 0.5 * t["brier_max"]
            - 0.5 * t["ece_max"]
            + 0.2 * t["roc_auc_ci_low_min"]
            + 0.2 * t["pr_auc_ci_low_min"]
            + 0.1 * t["ef1_ci_low_min"]
            + 0.1 * t["topk_hit_min"]
        )
        row = {
            "scenario_id": idx,
            "pass_runs": pass_runs,
            "total_runs": total_runs,
            "pass_rate": pass_rate,
            "primary_fail": primary_fail,
            "strictness_score": float(strictness),
        }
        row.update({f"thr_{k}": v for k, v in t.items()})
        scenario_rows.append(row)

    sdf = pd.DataFrame(scenario_rows).sort_values(
        ["pass_rate", "strictness_score"], ascending=[False, False]
    ).reset_index(drop=True)
    ddf = pd.DataFrame(detail_rows)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "runs_csv": runs_csv,
        "scenarios_tested": int(len(sdf)),
        "runs_count": int(len(df)),
        "best_scenario": sdf.iloc[0].to_dict() if not sdf.empty else {},
        "artifacts": {
            "scenario_csv": str(args.out_scenario_csv),
            "detail_csv": str(args.out_detail_csv),
            "summary_json": str(args.out_json),
            "summary_md": str(args.out_md),
        },
    }

    _ensure_parent(str(args.out_scenario_csv))
    sdf.to_csv(str(args.out_scenario_csv), index=False)
    _ensure_parent(str(args.out_detail_csv))
    ddf.to_csv(str(args.out_detail_csv), index=False)
    _ensure_parent(str(args.out_json))
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Ligand Gate Offline Simulation",
        "",
        f"- generated_at_local: {payload['generated_at_local']}",
        f"- runs_csv: `{runs_csv}`",
        f"- runs_count: {payload['runs_count']}",
        f"- scenarios_tested: {payload['scenarios_tested']}",
        f"- best_scenario: {payload['best_scenario']}",
        "",
        f"- scenario_csv: `{args.out_scenario_csv}`",
        f"- detail_csv: `{args.out_detail_csv}`",
        f"- summary_json: `{args.out_json}`",
    ]
    _ensure_parent(str(args.out_md))
    with open(str(args.out_md), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Offline gate threshold simulation using already completed run metrics.")
    p.add_argument("--runs-csv", type=str, default="runs/ligand_stress_commercial_full_runs.csv")
    p.add_argument("--include-pending", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--auc-unique-min-grid", type=str, default="0.85,0.90,0.95")
    p.add_argument("--auc-ood-min-grid", type=str, default="0.80,0.85,0.90")
    p.add_argument("--pr-auc-min-grid", type=str, default="0.55,0.60,0.65")
    p.add_argument("--ef1-min-grid", type=str, default="1.20,1.40,1.60")
    p.add_argument("--bedroc-min-grid", type=str, default="0.25,0.30,0.40")
    p.add_argument("--brier-max-grid", type=str, default="0.30,0.20,0.15")
    p.add_argument("--ece-max-grid", type=str, default="0.30,0.28,0.26")
    p.add_argument("--roc-auc-ci-low-min-grid", type=str, default="0.75,0.80,0.85")
    p.add_argument("--pr-auc-ci-low-min-grid", type=str, default="0.45,0.50,0.55")
    p.add_argument("--ef1-ci-low-min-grid", type=str, default="1.00,1.20")
    p.add_argument("--topk-hit-min-grid", type=str, default="0.20,0.50")
    p.add_argument("--out-scenario-csv", type=str, default="runs/ligand_gate_simulation_scenarios.csv")
    p.add_argument("--out-detail-csv", type=str, default="runs/ligand_gate_simulation_detail.csv")
    p.add_argument("--out-json", type=str, default="runs/ligand_gate_simulation_summary.json")
    p.add_argument("--out-md", type=str, default="runs/ligand_gate_simulation_summary.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    run_sim(args)


if __name__ == "__main__":
    main()
