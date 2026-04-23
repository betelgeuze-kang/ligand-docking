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
                str(args.delta_g_col): "",
                str(args.state_jsd_col): "",
                str(args.pmf_emd_col): "",
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
        str(args.delta_g_col),
        str(args.state_jsd_col),
        str(args.pmf_emd_col),
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    weight_col = str(args.weight_col).strip()
    use_weight = bool(weight_col and (weight_col in df.columns))

    work = df.copy()
    work["_target"] = work[str(args.target_col)].astype(str)
    work["_delta_g"] = pd.to_numeric(work[str(args.delta_g_col)], errors="coerce")
    work["_state_jsd"] = pd.to_numeric(work[str(args.state_jsd_col)], errors="coerce")
    work["_pmf_emd"] = pd.to_numeric(work[str(args.pmf_emd_col)], errors="coerce")
    if use_weight:
        work["_w"] = pd.to_numeric(work[weight_col], errors="coerce").fillna(0.0)
    else:
        work["_w"] = 1.0

    per_target_rows: List[Dict[str, Any]] = []
    for target, g in work.groupby("_target", as_index=False):
        delta_vals: List[float] = []
        delta_w: List[float] = []
        jsd_vals: List[float] = []
        jsd_w: List[float] = []
        pmf_vals: List[float] = []
        pmf_w: List[float] = []
        rows_total = int(len(g))
        rows_used = 0

        for _, row in g.iterrows():
            delta_g = _safe_float(row["_delta_g"])
            state_jsd = _safe_float(row["_state_jsd"])
            pmf_emd = _safe_float(row["_pmf_emd"])
            w = _safe_float(row["_w"])
            if w is None or w <= 0.0:
                continue
            if (delta_g is None) or (state_jsd is None) or (pmf_emd is None):
                continue
            rows_used += 1
            delta_vals.append(float(delta_g))
            delta_w.append(float(w))
            jsd_vals.append(float(state_jsd))
            jsd_w.append(float(w))
            pmf_vals.append(float(pmf_emd))
            pmf_w.append(float(w))

        m_delta = _weighted_mean(delta_vals, delta_w)
        m_jsd = _weighted_mean(jsd_vals, jsd_w)
        m_pmf = _weighted_mean(pmf_vals, pmf_w)

        pass_delta = (m_delta is not None) and (m_delta <= float(args.delta_g_threshold))
        pass_jsd = (m_jsd is not None) and (m_jsd <= float(args.state_jsd_threshold))
        pass_pmf = (m_pmf is not None) and (m_pmf <= float(args.pmf_emd_threshold))
        per_target_rows.append(
            {
                "target": str(target),
                "rows_total": int(rows_total),
                "rows_used": int(rows_used),
                "deltaG_rmse_kcal_mol": m_delta,
                "state_population_jsd": m_jsd,
                "pmf_1d_emd": m_pmf,
                "pass_deltaG_rmse_kcal_mol": bool(pass_delta),
                "pass_state_population_jsd": bool(pass_jsd),
                "pass_pmf_1d_emd": bool(pass_pmf),
                "pass_all": bool(pass_delta and pass_jsd and pass_pmf),
            }
        )

    out_df = pd.DataFrame(per_target_rows).sort_values("target")
    used_df = out_df.dropna(
        subset=["deltaG_rmse_kcal_mol", "state_population_jsd", "pmf_1d_emd"]
    ).copy()
    if used_df.empty:
        raise ValueError("no valid thermodynamics rows after filtering")

    global_delta = float(pd.to_numeric(used_df["deltaG_rmse_kcal_mol"], errors="coerce").mean())
    global_jsd = float(pd.to_numeric(used_df["state_population_jsd"], errors="coerce").mean())
    global_pmf = float(pd.to_numeric(used_df["pmf_1d_emd"], errors="coerce").mean())

    metrics = {
        "deltaG_rmse_kcal_mol": global_delta,
        "state_population_jsd": global_jsd,
        "pmf_1d_emd": global_pmf,
    }
    summary = {
        "targets_total": int(len(out_df)),
        "targets_with_metrics": int(len(used_df)),
        "targets_pass_all": int(used_df["pass_all"].sum()),
        "pass_rate_all": float(used_df["pass_all"].mean()),
        "deltaG_rmse_kcal_mol": float(global_delta),
        "state_population_jsd": float(global_jsd),
        "pmf_1d_emd": float(global_pmf),
        "delta_g_threshold": float(args.delta_g_threshold),
        "state_jsd_threshold": float(args.state_jsd_threshold),
        "pmf_emd_threshold": float(args.pmf_emd_threshold),
    }

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "build_metrics",
        "inputs": {
            "input_csv": src,
            "target_col": str(args.target_col),
            "delta_g_col": str(args.delta_g_col),
            "state_jsd_col": str(args.state_jsd_col),
            "pmf_emd_col": str(args.pmf_emd_col),
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
            "Build thermodynamics-equivalence metrics JSON "
            "(deltaG_rmse_kcal_mol, state_population_jsd, pmf_1d_emd)."
        )
    )
    p.add_argument("--input-csv", type=str, default="")
    p.add_argument("--scaffold-template", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--scaffold-targets", type=str, default="all")

    p.add_argument("--target-col", type=str, default="target")
    p.add_argument("--delta-g-col", type=str, default="deltaG_rmse_kcal_mol")
    p.add_argument("--state-jsd-col", type=str, default="state_population_jsd")
    p.add_argument("--pmf-emd-col", type=str, default="pmf_1d_emd")
    p.add_argument("--weight-col", type=str, default="")

    p.add_argument("--delta-g-threshold", type=float, default=0.50)
    p.add_argument("--state-jsd-threshold", type=float, default=0.05)
    p.add_argument("--pmf-emd-threshold", type=float, default=0.20)
    p.add_argument("--fail-on-threshold", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--out-json", type=str, default=f"runs/thermo_equivalence_metrics_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/thermo_equivalence_metrics_{stamp}.csv")
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
