#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return None


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip().lower()
    if s == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    seen = set()
    uniq: List[str] = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def _weighted_mean(values: List[float], weights: List[float]) -> Optional[float]:
    if len(values) == 0:
        return None
    if len(weights) != len(values):
        return None
    wsum = float(sum(weights))
    if wsum <= 0.0:
        return None
    return float(sum(v * w for v, w in zip(values, weights)) / wsum)


def _scaffold_template(args: argparse.Namespace) -> Dict[str, Any]:
    targets = _parse_targets(str(args.scaffold_targets))
    if len(targets) == 0:
        raise ValueError("scaffold targets are empty")

    rows: List[Dict[str, Any]] = []
    for t in targets:
        rows.append(
            {
                str(args.target_col): t,
                str(args.mfpt_pred_col): "",
                str(args.mfpt_ref_col): "",
                str(args.its_pred_col): "",
                str(args.its_ref_col): "",
                "notes": "",
            }
        )
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    df.to_csv(str(args.out_csv), index=False)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "scaffold_template",
        "targets": targets,
        "target_count": int(len(targets)),
        "out_csv": str(args.out_csv),
    }
    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def _build_metrics(args: argparse.Namespace) -> Dict[str, Any]:
    src = str(args.input_csv).strip()
    if not src:
        raise ValueError("--input-csv is required unless --scaffold-template is used")
    if not os.path.exists(src):
        raise FileNotFoundError(f"input csv not found: {src}")

    df = pd.read_csv(src)
    if df.empty:
        raise ValueError(f"input csv is empty: {src}")

    required_cols = [
        str(args.target_col),
        str(args.mfpt_pred_col),
        str(args.mfpt_ref_col),
        str(args.its_pred_col),
        str(args.its_ref_col),
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    weight_col = str(args.weight_col).strip()
    use_weight = bool(weight_col and (weight_col in df.columns))
    eps = float(args.min_positive_eps)

    work = df.copy()
    work["_target"] = work[str(args.target_col)].astype(str)
    work["_mfpt_pred"] = pd.to_numeric(work[str(args.mfpt_pred_col)], errors="coerce")
    work["_mfpt_ref"] = pd.to_numeric(work[str(args.mfpt_ref_col)], errors="coerce")
    work["_its_pred"] = pd.to_numeric(work[str(args.its_pred_col)], errors="coerce")
    work["_its_ref"] = pd.to_numeric(work[str(args.its_ref_col)], errors="coerce")
    if use_weight:
        work["_w"] = pd.to_numeric(work[weight_col], errors="coerce").fillna(0.0)
    else:
        work["_w"] = 1.0

    per_target_rows: List[Dict[str, Any]] = []
    for target, g in work.groupby("_target", as_index=False):
        mfpt_vals: List[float] = []
        mfpt_w: List[float] = []
        its_vals: List[float] = []
        its_w: List[float] = []
        rows_total = int(len(g))
        rows_used = 0

        for _, row in g.iterrows():
            mfpt_pred = _safe_float(row["_mfpt_pred"])
            mfpt_ref = _safe_float(row["_mfpt_ref"])
            its_pred = _safe_float(row["_its_pred"])
            its_ref = _safe_float(row["_its_ref"])
            w = _safe_float(row["_w"])
            if w is None or w <= 0.0:
                continue
            if (mfpt_pred is None) or (mfpt_ref is None) or (its_pred is None) or (its_ref is None):
                continue
            if (mfpt_pred <= 0.0) or (mfpt_ref <= 0.0):
                if bool(args.drop_nonpositive):
                    continue
            denom_mfpt_ref = max(abs(float(mfpt_ref)), eps)
            denom_its_ref = max(abs(float(its_ref)), eps)
            ratio = max(abs(float(mfpt_pred)) / denom_mfpt_ref, eps)
            log10_mfpt_error = abs(math.log10(ratio))
            implied_timescale_rel_error = abs(float(its_pred) - float(its_ref)) / denom_its_ref
            mfpt_vals.append(float(log10_mfpt_error))
            mfpt_w.append(float(w))
            its_vals.append(float(implied_timescale_rel_error))
            its_w.append(float(w))
            rows_used += 1

        m_mfpt = _weighted_mean(mfpt_vals, mfpt_w)
        m_its = _weighted_mean(its_vals, its_w)
        pass_mfpt = (m_mfpt is not None) and (m_mfpt <= float(args.mfpt_threshold))
        pass_its = (m_its is not None) and (m_its <= float(args.its_threshold))
        per_target_rows.append(
            {
                "target": str(target),
                "rows_total": int(rows_total),
                "rows_used": int(rows_used),
                "log10_mfpt_error": m_mfpt,
                "implied_timescale_rel_error": m_its,
                "pass_log10_mfpt_error": bool(pass_mfpt),
                "pass_implied_timescale_rel_error": bool(pass_its),
                "pass_both": bool(pass_mfpt and pass_its),
            }
        )

    out_df = pd.DataFrame(per_target_rows).sort_values("target")
    used_df = out_df.dropna(subset=["log10_mfpt_error", "implied_timescale_rel_error"]).copy()
    if used_df.empty:
        raise ValueError("no valid kinetics rows after filtering")

    global_log10_mfpt = float(pd.to_numeric(used_df["log10_mfpt_error"], errors="coerce").mean())
    global_its_rel = float(pd.to_numeric(used_df["implied_timescale_rel_error"], errors="coerce").mean())

    metrics = {
        "log10_mfpt_error": global_log10_mfpt,
        "implied_timescale_rel_error": global_its_rel,
    }
    summary = {
        "targets_total": int(len(out_df)),
        "targets_with_metrics": int(len(used_df)),
        "targets_pass_both": int(used_df["pass_both"].sum()),
        "pass_rate_both": float(used_df["pass_both"].mean()),
        "log10_mfpt_error": float(global_log10_mfpt),
        "implied_timescale_rel_error": float(global_its_rel),
        "mfpt_threshold": float(args.mfpt_threshold),
        "its_threshold": float(args.its_threshold),
    }

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "build_metrics",
        "inputs": {
            "input_csv": src,
            "target_col": str(args.target_col),
            "mfpt_pred_col": str(args.mfpt_pred_col),
            "mfpt_ref_col": str(args.mfpt_ref_col),
            "its_pred_col": str(args.its_pred_col),
            "its_ref_col": str(args.its_ref_col),
            "weight_col": weight_col if use_weight else None,
            "drop_nonpositive": bool(args.drop_nonpositive),
            "min_positive_eps": float(args.min_positive_eps),
        },
        "summary": summary,
        "metrics": metrics,
        "per_target": out_df.to_dict(orient="records"),
    }

    os.makedirs(os.path.dirname(str(args.out_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    out_df.to_csv(str(args.out_csv), index=False)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def run_build(args: argparse.Namespace) -> Dict[str, Any]:
    if bool(args.scaffold_template):
        return _scaffold_template(args)
    return _build_metrics(args)


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Build kinetics-equivalence metrics JSON (log10_mfpt_error, implied_timescale_rel_error)."
    )
    p.add_argument("--input-csv", type=str, default="")
    p.add_argument("--scaffold-template", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--scaffold-targets", type=str, default="all")

    p.add_argument("--target-col", type=str, default="target")
    p.add_argument("--mfpt-pred-col", type=str, default="mfpt_pred")
    p.add_argument("--mfpt-ref-col", type=str, default="mfpt_ref")
    p.add_argument("--its-pred-col", type=str, default="its_pred")
    p.add_argument("--its-ref-col", type=str, default="its_ref")
    p.add_argument("--weight-col", type=str, default="")
    p.add_argument("--drop-nonpositive", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--min-positive-eps", type=float, default=1e-12)

    p.add_argument("--mfpt-threshold", type=float, default=0.30)
    p.add_argument("--its-threshold", type=float, default=0.15)
    p.add_argument("--fail-on-threshold", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--out-json", type=str, default=f"runs/kinetics_equivalence_metrics_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/kinetics_equivalence_metrics_{stamp}.csv")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    summary = payload.get("summary", {})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote CSV: {args.out_csv}")

    if bool(args.fail_on_threshold) and (not bool(args.scaffold_template)):
        pass_rate = _safe_float(summary.get("pass_rate_both"))
        if (pass_rate is None) or (pass_rate < 1.0):
            sys.exit(2)


if __name__ == "__main__":
    main()

