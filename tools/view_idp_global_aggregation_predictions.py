#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import pandas as pd


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _resolve_predictions_csv(args: argparse.Namespace) -> str:
    csv_path = str(args.predictions_csv).strip()
    if csv_path:
        return csv_path
    manifest_json = str(args.manifest_json).strip()
    if not manifest_json:
        raise ValueError("provide either --predictions-csv or --manifest-json")
    manifest = _load_json(manifest_json)
    diag = dict(manifest.get("diagnostic_artifacts", {}) or {})
    csv_path = str(diag.get("global_aggregation_predictions_csv", "")).strip()
    if not csv_path:
        raise ValueError(f"manifest missing diagnostic_artifacts.global_aggregation_predictions_csv: {manifest_json}")
    return csv_path


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def run(args: argparse.Namespace) -> Dict[str, Any]:
    predictions_csv = _resolve_predictions_csv(args)
    df = pd.read_csv(predictions_csv)
    if "pred_aggregation_risk_global" not in df.columns:
        raise ValueError(f"missing pred_aggregation_risk_global column: {predictions_csv}")
    if "pred_aggregation_prob" in df.columns:
        df["risk_gap"] = df["pred_aggregation_risk_global"].astype(float) - df["pred_aggregation_prob"].astype(float)
    else:
        df["risk_gap"] = df["pred_aggregation_risk_global"].astype(float)

    branch = str(args.branch).strip()
    if branch:
        df = df.loc[df["branch_label"] == branch].copy()
    holdout = str(args.holdout).strip()
    if holdout:
        df = df.loc[df["__holdout"] == holdout].copy()
    condition = str(args.condition_group).strip()
    if condition:
        df = df.loc[df["condition_group"] == condition].copy()
    target = str(args.target).strip()
    if target:
        df = df.loc[df["target"] == target].copy()

    sort_by = str(args.sort_by).strip() or "pred_aggregation_risk_global"
    ascending = bool(int(args.ascending))
    if sort_by not in df.columns:
        raise ValueError(f"sort column not found: {sort_by}")
    df = df.sort_values(sort_by, ascending=ascending, kind="mergesort").reset_index(drop=True)
    top_k = max(int(args.top_k), 1)
    top_df = df.head(top_k).copy()

    branch_summary = (
        df.groupby("branch_label", dropna=False)
        .agg(
            rows=("branch_label", "size"),
            positives=("true_aggregation_flag", "sum"),
            mean_raw_prob=("pred_aggregation_prob", "mean"),
            mean_global_risk=("pred_aggregation_risk_global", "mean"),
            mean_risk_gap=("risk_gap", "mean"),
        )
        .reset_index()
        .sort_values("mean_global_risk", ascending=False, kind="mergesort")
    )

    holdout_summary = (
        df.groupby("__holdout", dropna=False)
        .agg(
            rows=("__holdout", "size"),
            positives=("true_aggregation_flag", "sum"),
            mean_raw_prob=("pred_aggregation_prob", "mean"),
            mean_global_risk=("pred_aggregation_risk_global", "mean"),
            mean_risk_gap=("risk_gap", "mean"),
        )
        .reset_index()
        .sort_values("mean_global_risk", ascending=False, kind="mergesort")
    )

    payload: Dict[str, Any] = {
        "predictions_csv": predictions_csv,
        "row_count": int(len(df)),
        "filters": {
            "branch": branch,
            "holdout": holdout,
            "condition_group": condition,
            "target": target,
        },
        "sort_by": sort_by,
        "ascending": ascending,
        "top_rows": top_df[
            [
                "__fold_index",
                "__holdout",
                "target",
                "condition_group",
                "branch_label",
                "pred_state",
                "true_aggregation_flag",
                "pred_aggregation_prob",
                "pred_aggregation_risk_global",
                "risk_gap",
                "pred_rank_compactness",
                "pred_rank_helicity",
                "pred_rank_condensation",
            ]
        ].to_dict(orient="records"),
        "branch_summary": branch_summary.to_dict(orient="records"),
        "holdout_summary": holdout_summary.to_dict(orient="records"),
    }

    out_csv = str(args.out_csv).strip()
    if out_csv:
        _ensure_parent(out_csv)
        df.to_csv(out_csv, index=False)
        payload["out_csv"] = out_csv
    return payload


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description="View or export calibrated global aggregation predictions.")
    p.add_argument("--predictions-csv", default="", type=str)
    p.add_argument("--manifest-json", default="", type=str)
    p.add_argument("--branch", default="", type=str)
    p.add_argument("--holdout", default="", type=str)
    p.add_argument("--condition-group", default="", type=str)
    p.add_argument("--target", default="", type=str)
    p.add_argument("--sort-by", default="pred_aggregation_risk_global", type=str)
    p.add_argument("--ascending", type=int, default=0)
    p.add_argument("--top-k", type=int, default=12)
    p.add_argument("--out-csv", default="", type=str)
    args = p.parse_args(argv)

    payload = run(args)
    print("# IDP Global Aggregation Predictions")
    print(f"- predictions_csv: {payload['predictions_csv']}")
    print(f"- row_count: {payload['row_count']}")
    print(f"- filters: {payload['filters']}")
    print(f"- sort_by: {payload['sort_by']}")
    print("")
    print("## Branch Summary")
    for row in payload["branch_summary"]:
        print(
            "- "
            + ", ".join(
                [
                    f"branch={row['branch_label']}",
                    f"rows={row['rows']}",
                    f"positives={row['positives']}",
                    f"mean_raw={_fmt(row['mean_raw_prob'])}",
                    f"mean_global={_fmt(row['mean_global_risk'])}",
                    f"mean_gap={_fmt(row['mean_risk_gap'])}",
                ]
            )
        )
    print("")
    print("## Top Rows")
    for row in payload["top_rows"]:
        print(
            "- "
            + ", ".join(
                [
                    f"fold={row['__fold_index']}",
                    f"holdout={row['__holdout']}",
                    f"condition={row['condition_group']}",
                    f"branch={row['branch_label']}",
                    f"state={row['pred_state']}",
                    f"true_agg={row['true_aggregation_flag']}",
                    f"raw={_fmt(row['pred_aggregation_prob'])}",
                    f"global={_fmt(row['pred_aggregation_risk_global'])}",
                    f"gap={_fmt(row['risk_gap'])}",
                ]
            )
        )
    if payload.get("out_csv"):
        print("")
        print(f"- out_csv: {payload['out_csv']}")


if __name__ == "__main__":
    main()
