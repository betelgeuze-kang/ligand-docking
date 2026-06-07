#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
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
                str(args.nmr_noe_col): "",
                str(args.cryoem_cc_col): "",
                str(args.saxs_chi2_col): "",
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
        str(args.nmr_noe_col),
        str(args.cryoem_cc_col),
        str(args.saxs_chi2_col),
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    weight_col = str(args.weight_col).strip()
    use_weight = bool(weight_col and (weight_col in df.columns))

    work = df.copy()
    work["_target"] = work[str(args.target_col)].astype(str)
    work["_nmr_noe"] = pd.to_numeric(work[str(args.nmr_noe_col)], errors="coerce")
    work["_cryoem_cc"] = pd.to_numeric(work[str(args.cryoem_cc_col)], errors="coerce")
    work["_saxs_chi2"] = pd.to_numeric(work[str(args.saxs_chi2_col)], errors="coerce")
    if use_weight:
        work["_w"] = pd.to_numeric(work[weight_col], errors="coerce").fillna(0.0)
    else:
        work["_w"] = 1.0

    per_target_rows: List[Dict[str, Any]] = []
    for target, g in work.groupby("_target", as_index=False):
        nmr_vals: List[float] = []
        nmr_w: List[float] = []
        cc_vals: List[float] = []
        cc_w: List[float] = []
        saxs_vals: List[float] = []
        saxs_w: List[float] = []
        rows_total = int(len(g))
        rows_used = 0

        for _, row in g.iterrows():
            nmr_noe = _safe_float(row["_nmr_noe"])
            cryoem_cc = _safe_float(row["_cryoem_cc"])
            saxs_chi2 = _safe_float(row["_saxs_chi2"])
            w = _safe_float(row["_w"])
            if w is None or w <= 0.0:
                continue
            if (nmr_noe is None) or (cryoem_cc is None) or (saxs_chi2 is None):
                continue
            rows_used += 1
            nmr_vals.append(float(nmr_noe))
            nmr_w.append(float(w))
            cc_vals.append(float(cryoem_cc))
            cc_w.append(float(w))
            saxs_vals.append(float(saxs_chi2))
            saxs_w.append(float(w))

        m_nmr = _weighted_mean(nmr_vals, nmr_w)
        m_cc = _weighted_mean(cc_vals, cc_w)
        m_saxs = _weighted_mean(saxs_vals, saxs_w)

        pass_nmr = (m_nmr is not None) and (m_nmr <= float(args.nmr_noe_threshold))
        pass_cc = (m_cc is not None) and (m_cc >= float(args.cryoem_cc_threshold))
        pass_saxs = (m_saxs is not None) and (m_saxs <= float(args.saxs_chi2_threshold))
        per_target_rows.append(
            {
                "target": str(target),
                "rows_total": int(rows_total),
                "rows_used": int(rows_used),
                "nmr_noe_violation_rate": m_nmr,
                "cryoem_map_cc": m_cc,
                "saxs_chi2": m_saxs,
                "pass_nmr_noe_violation_rate": bool(pass_nmr),
                "pass_cryoem_map_cc": bool(pass_cc),
                "pass_saxs_chi2": bool(pass_saxs),
                "pass_all": bool(pass_nmr and pass_cc and pass_saxs),
            }
        )

    out_df = pd.DataFrame(per_target_rows).sort_values("target")
    used_df = out_df.dropna(subset=["nmr_noe_violation_rate", "cryoem_map_cc", "saxs_chi2"]).copy()
    if used_df.empty:
        raise ValueError("no valid experiment rows after filtering")

    global_nmr = float(pd.to_numeric(used_df["nmr_noe_violation_rate"], errors="coerce").mean())
    global_cc = float(pd.to_numeric(used_df["cryoem_map_cc"], errors="coerce").mean())
    global_saxs = float(pd.to_numeric(used_df["saxs_chi2"], errors="coerce").mean())

    metrics = {
        "nmr_noe_violation_rate": global_nmr,
        "cryoem_map_cc": global_cc,
        "saxs_chi2": global_saxs,
    }
    summary = {
        "targets_total": int(len(out_df)),
        "targets_with_metrics": int(len(used_df)),
        "targets_pass_all": int(used_df["pass_all"].sum()),
        "pass_rate_all": float(used_df["pass_all"].mean()),
        "nmr_noe_violation_rate": float(global_nmr),
        "cryoem_map_cc": float(global_cc),
        "saxs_chi2": float(global_saxs),
        "nmr_noe_threshold": float(args.nmr_noe_threshold),
        "cryoem_cc_threshold": float(args.cryoem_cc_threshold),
        "saxs_chi2_threshold": float(args.saxs_chi2_threshold),
    }

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "build_metrics",
        "inputs": {
            "input_csv": src,
            "target_col": str(args.target_col),
            "nmr_noe_col": str(args.nmr_noe_col),
            "cryoem_cc_col": str(args.cryoem_cc_col),
            "saxs_chi2_col": str(args.saxs_chi2_col),
            "weight_col": weight_col if use_weight else None,
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
        description=(
            "Build experiment-consistency metrics JSON "
            "(nmr_noe_violation_rate, cryoem_map_cc, saxs_chi2)."
        )
    )
    p.add_argument("--input-csv", type=str, default="")
    p.add_argument("--scaffold-template", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--scaffold-targets", type=str, default="all")

    p.add_argument("--target-col", type=str, default="target")
    p.add_argument("--nmr-noe-col", type=str, default="nmr_noe_violation_rate")
    p.add_argument("--cryoem-cc-col", type=str, default="cryoem_map_cc")
    p.add_argument("--saxs-chi2-col", type=str, default="saxs_chi2")
    p.add_argument("--weight-col", type=str, default="")

    p.add_argument("--nmr-noe-threshold", type=float, default=0.10)
    p.add_argument("--cryoem-cc-threshold", type=float, default=0.85)
    p.add_argument("--saxs-chi2-threshold", type=float, default=1.50)
    p.add_argument("--fail-on-threshold", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--out-json", type=str, default=f"runs/experiment_consistency_metrics_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/experiment_consistency_metrics_{stamp}.csv")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    summary = payload.get("summary", {})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote CSV: {args.out_csv}")

    if bool(args.fail_on_threshold) and (not bool(args.scaffold_template)):
        pass_rate = _safe_float(summary.get("pass_rate_all"))
        if (pass_rate is None) or (pass_rate < 1.0):
            sys.exit(2)


if __name__ == "__main__":
    main()
