#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Set

import numpy as np
import pandas as pd

from core.definitions import ResearchConstants


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _parse_targets(spec: str) -> Optional[Set[str]]:
    s = str(spec).strip().lower()
    if (not s) or (s == "all"):
        return None
    out: Set[str] = set()
    for token in str(spec).split(","):
        key = _normalize_target_key(token)
        if key:
            out.add(key)
    return out or None


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


def _read_optional_csv(path: str) -> pd.DataFrame:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return pd.DataFrame()
    try:
        df = pd.read_csv(src)
    except Exception:
        return pd.DataFrame()
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _pick_existing_col(df: pd.DataFrame, candidates: Sequence[str]) -> str:
    for c in candidates:
        cc = str(c).strip()
        if cc and cc in df.columns:
            return cc
    return ""


def _add_row(
    rows: List[Dict[str, Any]],
    seen: Set[str],
    *,
    target: str,
    source: str,
    score: float,
    reason: str,
    allowed_targets: Optional[Set[str]],
) -> bool:
    name = str(target).strip()
    key = _normalize_target_key(name)
    if not key:
        return False
    if (allowed_targets is not None) and (key not in allowed_targets):
        return False
    if key in seen:
        return False
    seen.add(key)
    rows.append(
        {
            "target": name,
            "priority_source": str(source),
            "priority_score": float(score),
            "reason": str(reason),
        }
    )
    return True


def build_priority_targets(
    *,
    targets: str,
    ood_pair_csv: str,
    ood_min_rmsd: float,
    ood_topk: int,
    oversize_breakdown_csv: str,
    oversize_topk: int,
    oversize_target_col: str,
    feature_csv: str,
    feature_topk: int,
    feature_target_col: str,
    feature_rmsd_col: str,
    feature_violations_col: str,
    feature_control_prefix: str,
    feature_min_control_levels: float,
    out_csv: str,
    out_json: str,
) -> Dict[str, Any]:
    allowed_targets = _parse_targets(targets)
    if allowed_targets is None and str(targets).strip().lower() == "all":
        allowed_targets = {_normalize_target_key(t) for t in ResearchConstants.CHALLENGES.keys()}

    rows: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    ood_selected = 0
    oversize_selected = 0
    feature_selected = 0

    ood_df = _read_optional_csv(ood_pair_csv)
    if (not ood_df.empty) and ("target" in ood_df.columns):
        work = ood_df.copy()
        work["paired_i"] = pd.to_numeric(work.get("paired"), errors="coerce").fillna(0).astype(int)
        work["rmsd_f"] = pd.to_numeric(work.get("rmsd_aligned_A"), errors="coerce")
        work = work[(work["paired_i"] == 1) & (work["rmsd_f"].notna()) & (work["rmsd_f"] >= float(ood_min_rmsd))]
        work = work.sort_values(by=["rmsd_f"], ascending=[False])
        for _, row in work.iterrows():
            if ood_selected >= int(max(0, ood_topk)):
                break
            if _add_row(
                rows,
                seen,
                target=str(row.get("target", "")).strip(),
                source="ood_high_rmsd",
                score=float(row.get("rmsd_f", 0.0) or 0.0),
                reason=f"ood_rmsd>={float(ood_min_rmsd):.3f}",
                allowed_targets=allowed_targets,
            ):
                ood_selected += 1

    oversize_df = _read_optional_csv(oversize_breakdown_csv)
    if not oversize_df.empty:
        col_candidates = [str(oversize_target_col).strip(), "target", "source_target", "target_name", "protein_name"]
        col = ""
        for c in col_candidates:
            if c and c in oversize_df.columns:
                col = c
                break
        if col:
            work = oversize_df.copy()
            if "ca_count" in work.columns:
                work["ca_f"] = pd.to_numeric(work.get("ca_count"), errors="coerce").fillna(0.0)
                work = work.sort_values(by=["ca_f"], ascending=[False])
            for _, row in work.iterrows():
                if oversize_selected >= int(max(0, oversize_topk)):
                    break
                target_name = str(row.get(col, "")).strip()
                ca_score = _safe_float(row.get("ca_count"))
                score = float(ca_score) if ca_score is not None else 0.0
                if _add_row(
                    rows,
                    seen,
                    target=target_name,
                    source="oversize_backlog",
                    score=score,
                    reason="oversize_or_hard_cap",
                    allowed_targets=allowed_targets,
                ):
                    oversize_selected += 1

    feature_df = _read_optional_csv(feature_csv)
    if not feature_df.empty:
        target_col = _pick_existing_col(
            feature_df,
            [
                str(feature_target_col).strip(),
                "target",
                "target_name",
            ],
        )
        rmsd_col = _pick_existing_col(
            feature_df,
            [str(feature_rmsd_col).strip(), "observed_rmsd", "rmsd"],
        )
        viol_col = _pick_existing_col(
            feature_df,
            [str(feature_violations_col).strip(), "observed_violations", "violations"],
        )
        control_cols = [
            c
            for c in feature_df.columns
            if str(c).startswith(str(feature_control_prefix))
        ]
        if target_col:
            work = feature_df.copy()
            if rmsd_col:
                work["_rmsd_f"] = pd.to_numeric(work.get(rmsd_col), errors="coerce")
            else:
                work["_rmsd_f"] = np.nan
            if viol_col:
                work["_viol_f"] = pd.to_numeric(work.get(viol_col), errors="coerce").fillna(0.0)
            else:
                work["_viol_f"] = 0.0
            rows_scored: List[Dict[str, Any]] = []
            for tname, sub in work.groupby(target_col):
                if feature_selected >= int(max(0, feature_topk)):
                    break
                rmsd_vals = pd.to_numeric(sub["_rmsd_f"], errors="coerce").dropna()
                rmsd_p95 = float(rmsd_vals.quantile(0.95)) if not rmsd_vals.empty else 0.0
                viol_vals = pd.to_numeric(sub["_viol_f"], errors="coerce").fillna(0.0)
                viol_rate = float((viol_vals > 0.0).mean()) if len(viol_vals) > 0 else 0.0
                ctrl_levels: List[float] = []
                for c in control_cols:
                    uniq = int(sub[c].nunique(dropna=True))
                    if uniq > 0:
                        ctrl_levels.append(float(uniq))
                control_mean_levels = float(sum(ctrl_levels) / len(ctrl_levels)) if ctrl_levels else 0.0
                control_deficit = max(0.0, float(feature_min_control_levels) - float(control_mean_levels))
                priority_score = float((viol_rate * 100.0) + (0.5 * rmsd_p95) + (10.0 * control_deficit))
                rows_scored.append(
                    {
                        "target": str(tname),
                        "priority_score": priority_score,
                        "viol_rate": viol_rate,
                        "rmsd_p95": rmsd_p95,
                        "control_mean_levels": control_mean_levels,
                    }
                )
            rows_scored = sorted(rows_scored, key=lambda r: float(r.get("priority_score", 0.0)), reverse=True)
            for row in rows_scored:
                if feature_selected >= int(max(0, feature_topk)):
                    break
                if _add_row(
                    rows,
                    seen,
                    target=str(row.get("target", "")).strip(),
                    source="feature_control_hardcase",
                    score=float(row.get("priority_score", 0.0)),
                    reason=(
                        "feature_hardcase "
                        f"viol={float(row.get('viol_rate', 0.0)):.3f} "
                        f"rmsd_p95={float(row.get('rmsd_p95', 0.0)):.3f} "
                        f"control_levels={float(row.get('control_mean_levels', 0.0)):.2f}"
                    ),
                    allowed_targets=allowed_targets,
                ):
                    feature_selected += 1

    os.makedirs(os.path.dirname(str(out_csv)) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(str(out_json)) or ".", exist_ok=True)
    out_df = pd.DataFrame(rows, columns=["target", "priority_source", "priority_score", "reason"])
    out_df.to_csv(str(out_csv), index=False)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "targets": str(targets),
            "ood_pair_csv": str(ood_pair_csv),
            "ood_min_rmsd": float(ood_min_rmsd),
            "ood_topk": int(max(0, ood_topk)),
            "oversize_breakdown_csv": str(oversize_breakdown_csv),
            "oversize_topk": int(max(0, oversize_topk)),
            "oversize_target_col": str(oversize_target_col),
            "feature_csv": str(feature_csv),
            "feature_topk": int(max(0, feature_topk)),
            "feature_target_col": str(feature_target_col),
            "feature_rmsd_col": str(feature_rmsd_col),
            "feature_violations_col": str(feature_violations_col),
            "feature_control_prefix": str(feature_control_prefix),
            "feature_min_control_levels": float(feature_min_control_levels),
        },
        "summary": {
            "priority_targets_count": int(len(rows)),
            "ood_selected": int(ood_selected),
            "oversize_selected": int(oversize_selected),
            "feature_selected": int(feature_selected),
        },
        "artifacts": {
            "priority_targets_csv": str(out_csv),
            "summary_json": str(out_json),
        },
    }
    with open(str(out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Build priority target CSV for active-learning hard-mining from OOD and oversize signals."
    )
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--ood-pair-csv", type=str, default="")
    p.add_argument("--ood-min-rmsd", type=float, default=8.0)
    p.add_argument("--ood-topk", type=int, default=8)
    p.add_argument("--oversize-breakdown-csv", type=str, default="runs/live_unseen_failure_breakdown_rolling.csv")
    p.add_argument("--oversize-topk", type=int, default=8)
    p.add_argument("--oversize-target-col", type=str, default="source_target")
    p.add_argument("--feature-csv", type=str, default="")
    p.add_argument("--feature-topk", type=int, default=8)
    p.add_argument("--feature-target-col", type=str, default="target")
    p.add_argument("--feature-rmsd-col", type=str, default="auto")
    p.add_argument("--feature-violations-col", type=str, default="auto")
    p.add_argument("--feature-control-prefix", type=str, default="control_")
    p.add_argument("--feature-min-control-levels", type=float, default=2.0)
    p.add_argument("--out-csv", type=str, default=f"runs/active_learning_priority_targets_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/active_learning_priority_targets_{stamp}.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_priority_targets(
        targets=str(args.targets),
        ood_pair_csv=str(args.ood_pair_csv),
        ood_min_rmsd=float(args.ood_min_rmsd),
        ood_topk=int(args.ood_topk),
        oversize_breakdown_csv=str(args.oversize_breakdown_csv),
        oversize_topk=int(args.oversize_topk),
        oversize_target_col=str(args.oversize_target_col),
        feature_csv=str(args.feature_csv),
        feature_topk=int(args.feature_topk),
        feature_target_col=str(args.feature_target_col),
        feature_rmsd_col=str(args.feature_rmsd_col),
        feature_violations_col=str(args.feature_violations_col),
        feature_control_prefix=str(args.feature_control_prefix),
        feature_min_control_levels=float(args.feature_min_control_levels),
        out_csv=str(args.out_csv),
        out_json=str(args.out_json),
    )
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
