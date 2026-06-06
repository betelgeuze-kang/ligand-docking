#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
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


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip().lower()
    if s == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    uniq: List[str] = []
    seen = set()
    for target in out:
        key = _normalize_target_key(target)
        if (not key) or (key in seen):
            continue
        seen.add(key)
        uniq.append(target)
    if not uniq:
        raise ValueError(f"no targets parsed from spec: {spec}")
    return uniq


def _read_optional_csv(path: str, *, required: bool = False) -> pd.DataFrame:
    src = str(path).strip()
    if not src:
        return pd.DataFrame()
    if not os.path.exists(src):
        if bool(required):
            raise FileNotFoundError(f"csv not found: {src}")
        return pd.DataFrame()
    df = pd.read_csv(src)
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _read_priority_targets(path: str, target_col: str = "target") -> Dict[str, str]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        df = pd.read_csv(src)
    except Exception:
        return {}
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    col = str(target_col).strip() or "target"
    if col not in df.columns:
        return {}
    out: Dict[str, str] = {}
    for _, row in df.iterrows():
        target = str(row.get(col, "")).strip()
        key = _normalize_target_key(target)
        if (not key) or (key in out):
            continue
        out[key] = target
    return out


def _pick_accuracy_rmsd(row: pd.Series) -> Optional[float]:
    for col in (
        "avg_rmsd_vs_native_aligned",
        "avg_rmsd_aligned",
        "avg_rmsd_vs_native",
        "avg_rmsd",
    ):
        if col not in row:
            continue
        fv = _safe_float(row.get(col))
        if fv is not None:
            return fv
    return None


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def build_hard_mining_target_weights(
    *,
    targets: str,
    ood_pair_csv: str,
    accuracy_external_csv: str,
    stage2_csv: str,
    topk: int,
    base_weight: float,
    max_weight: float,
    weight_scale: float,
    unpaired_boost: float,
    ood_rmsd_threshold: float,
    native_rmsd_threshold: float,
    uncertainty_threshold: float,
    fallback_ratio_threshold: float,
    physics_violations_threshold: float,
    uncertainty_weight: float,
    fallback_weight: float,
    physics_weight: float,
    out_target_weights_csv: str,
    out_score_csv: str,
    out_summary_json: str,
    priority_targets_csv: str = "",
    priority_target_col: str = "target",
    priority_bonus: float = 0.0,
) -> Dict[str, Any]:
    selected_targets = _parse_targets(targets)
    selected_norm = {_normalize_target_key(t) for t in selected_targets}

    pair_df = _read_optional_csv(ood_pair_csv, required=True)
    if pair_df.empty:
        raise ValueError(f"ood pair csv is empty: {ood_pair_csv}")
    if "target" not in pair_df.columns:
        raise ValueError(f"ood pair csv missing target column: {ood_pair_csv}")

    acc_df = _read_optional_csv(accuracy_external_csv, required=False)
    st2_df = _read_optional_csv(stage2_csv, required=False)
    priority_targets_map = _read_priority_targets(priority_targets_csv, target_col=priority_target_col)

    pair_map: Dict[str, pd.Series] = {}
    for _, row in pair_df.iterrows():
        target = str(row.get("target", "")).strip()
        key = _normalize_target_key(target)
        if (not key) or (key not in selected_norm):
            continue
        pair_map[key] = row

    acc_map: Dict[str, pd.Series] = {}
    if not acc_df.empty and ("target" in acc_df.columns):
        for _, row in acc_df.iterrows():
            target = str(row.get("target", "")).strip()
            key = _normalize_target_key(target)
            if (not key) or (key not in selected_norm):
                continue
            acc_map[key] = row

    st2_map: Dict[str, pd.Series] = {}
    if not st2_df.empty and ("target" in st2_df.columns):
        for _, row in st2_df.iterrows():
            target = str(row.get("target", "")).strip()
            key = _normalize_target_key(target)
            if (not key) or (key not in selected_norm):
                continue
            st2_map[key] = row

    rows: List[Dict[str, Any]] = []
    for target in selected_targets:
        key = _normalize_target_key(target)
        pair_row = pair_map.get(key)
        acc_row = acc_map.get(key)
        st2_row = st2_map.get(key)

        paired = int(float(pair_row.get("paired", 0))) if pair_row is not None else 0
        ood_rmsd = _safe_float(pair_row.get("rmsd_aligned_A")) if pair_row is not None else None
        ood_reason = str(pair_row.get("reason", "")) if pair_row is not None else "missing_pair_row"

        native_rmsd = _pick_accuracy_rmsd(acc_row) if acc_row is not None else None

        uncertainty_score = (
            _safe_float(st2_row.get("ai_uncertainty_score_on")) if st2_row is not None else None
        )
        fallback_ratio = (
            _safe_float(st2_row.get("ai_uncertainty_fallback_ratio_on")) if st2_row is not None else None
        )
        physics_violations = (
            _safe_float(st2_row.get("physics_violations_on")) if st2_row is not None else None
        )

        unpaired = int(paired != 1)
        comp_unpaired = float(unpaired_boost if unpaired else 0.0)
        comp_ood = 0.0
        if ood_rmsd is not None:
            comp_ood = max(0.0, (float(ood_rmsd) - float(ood_rmsd_threshold)) / max(float(ood_rmsd_threshold), 1e-12))
        comp_native = 0.0
        if native_rmsd is not None:
            comp_native = max(
                0.0,
                (float(native_rmsd) - float(native_rmsd_threshold)) / max(float(native_rmsd_threshold), 1e-12),
            )
        comp_uncertainty = 0.0
        if uncertainty_score is not None:
            comp_uncertainty = max(
                0.0,
                (float(uncertainty_score) - float(uncertainty_threshold))
                / max(float(uncertainty_threshold), 1e-12),
            )
        comp_fallback = 0.0
        if fallback_ratio is not None:
            comp_fallback = max(
                0.0,
                (float(fallback_ratio) - float(fallback_ratio_threshold))
                / max(float(fallback_ratio_threshold), 1e-12),
            )
        comp_physics = 0.0
        if physics_violations is not None:
            comp_physics = max(0.0, float(physics_violations) - float(physics_violations_threshold))
        priority_selected = int(key in priority_targets_map)
        comp_priority = float(priority_bonus) if priority_selected == 1 else 0.0

        hard_score = (
            comp_unpaired
            + comp_ood
            + comp_native
            + float(uncertainty_weight) * comp_uncertainty
            + float(fallback_weight) * comp_fallback
            + float(physics_weight) * comp_physics
            + comp_priority
        )
        rows.append(
            {
                "target": target,
                "paired": paired,
                "ood_reason": ood_reason,
                "ood_rmsd_aligned_A": ood_rmsd,
                "native_rmsd_aligned_A": native_rmsd,
                "ai_uncertainty_score_on": uncertainty_score,
                "ai_uncertainty_fallback_ratio_on": fallback_ratio,
                "physics_violations_on": physics_violations,
                "comp_unpaired": comp_unpaired,
                "comp_ood_rmsd": comp_ood,
                "comp_native_rmsd": comp_native,
                "comp_uncertainty": comp_uncertainty,
                "comp_fallback_ratio": comp_fallback,
                "comp_physics": comp_physics,
                "priority_selected": priority_selected,
                "comp_priority": comp_priority,
                "hard_score": float(hard_score),
            }
        )

    score_df = pd.DataFrame(rows)
    score_df = score_df.sort_values(by=["hard_score", "target"], ascending=[False, True]).reset_index(drop=True)

    nonzero_idx = score_df[score_df["hard_score"] > 0.0].index.tolist()
    if int(topk) > 0:
        picked_idx = nonzero_idx[: int(topk)]
    else:
        picked_idx = nonzero_idx
    selected_idx = set(int(i) for i in picked_idx)

    score_df["selected_for_hard_mining"] = [int(i in selected_idx) for i in score_df.index]
    multipliers: List[float] = []
    for i, row in score_df.iterrows():
        score = float(row.get("hard_score", 0.0) or 0.0)
        if i in selected_idx:
            weight = float(base_weight) + float(weight_scale) * score
            weight = min(float(max_weight), max(float(base_weight), weight))
        else:
            weight = float(base_weight)
        multipliers.append(float(weight))
    score_df["multiplier"] = multipliers

    weights_df = score_df[["target", "multiplier", "hard_score", "selected_for_hard_mining"]].copy()
    weights_df = weights_df.rename(columns={"selected_for_hard_mining": "selected"})

    _ensure_parent(out_score_csv)
    _ensure_parent(out_target_weights_csv)
    _ensure_parent(out_summary_json)
    score_df.to_csv(out_score_csv, index=False)
    weights_df.to_csv(out_target_weights_csv, index=False)

    selected_targets_final = score_df[score_df["selected_for_hard_mining"] == 1]["target"].astype(str).tolist()
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "targets": targets,
            "ood_pair_csv": ood_pair_csv,
            "accuracy_external_csv": accuracy_external_csv,
            "stage2_csv": stage2_csv,
            "topk": int(topk),
            "base_weight": float(base_weight),
            "max_weight": float(max_weight),
            "weight_scale": float(weight_scale),
            "unpaired_boost": float(unpaired_boost),
            "ood_rmsd_threshold": float(ood_rmsd_threshold),
            "native_rmsd_threshold": float(native_rmsd_threshold),
            "uncertainty_threshold": float(uncertainty_threshold),
            "fallback_ratio_threshold": float(fallback_ratio_threshold),
            "physics_violations_threshold": float(physics_violations_threshold),
            "uncertainty_weight": float(uncertainty_weight),
            "fallback_weight": float(fallback_weight),
            "physics_weight": float(physics_weight),
            "priority_targets_csv": str(priority_targets_csv),
            "priority_target_col": str(priority_target_col),
            "priority_bonus": float(priority_bonus),
        },
        "summary": {
            "targets_total": int(score_df.shape[0]),
            "targets_nonzero_score": int((score_df["hard_score"] > 0.0).sum()),
            "selected_targets_count": int(len(selected_targets_final)),
            "selected_targets": selected_targets_final,
            "max_hard_score": float(score_df["hard_score"].max()) if not score_df.empty else 0.0,
            "mean_hard_score": float(score_df["hard_score"].mean()) if not score_df.empty else 0.0,
            "ood_rows_available": int(len(pair_map)),
            "accuracy_rows_available": int(len(acc_map)),
            "stage2_rows_available": int(len(st2_map)),
            "priority_targets_available": int(len(priority_targets_map)),
            "priority_targets_matched": int(
                score_df["priority_selected"].sum() if ("priority_selected" in score_df.columns) else 0
            ),
        },
        "artifacts": {
            "score_csv": out_score_csv,
            "target_weights_csv": out_target_weights_csv,
            "summary_json": out_summary_json,
        },
    }
    with open(out_summary_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Build hard-mining target weight CSV from OOD pair metrics + accuracy + stage2 uncertainty signals."
        )
    )
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--ood-pair-csv", type=str, required=True)
    p.add_argument("--accuracy-external-csv", type=str, default="")
    p.add_argument("--stage2-csv", type=str, default="")
    p.add_argument("--topk", type=int, default=4)
    p.add_argument("--base-weight", type=float, default=1.0)
    p.add_argument("--max-weight", type=float, default=4.0)
    p.add_argument("--weight-scale", type=float, default=1.0)
    p.add_argument("--unpaired-boost", type=float, default=2.0)
    p.add_argument("--ood-rmsd-threshold", type=float, default=6.0)
    p.add_argument("--native-rmsd-threshold", type=float, default=0.5)
    p.add_argument("--uncertainty-threshold", type=float, default=0.3)
    p.add_argument("--fallback-ratio-threshold", type=float, default=0.05)
    p.add_argument("--physics-violations-threshold", type=float, default=0.0)
    p.add_argument("--uncertainty-weight", type=float, default=0.75)
    p.add_argument("--fallback-weight", type=float, default=0.50)
    p.add_argument("--physics-weight", type=float, default=0.50)
    p.add_argument("--priority-targets-csv", type=str, default="")
    p.add_argument("--priority-target-col", type=str, default="target")
    p.add_argument("--priority-bonus", type=float, default=0.0)
    p.add_argument("--out-target-weights-csv", type=str, default=f"runs/hard_mining_target_weights_{stamp}.csv")
    p.add_argument("--out-score-csv", type=str, default=f"runs/hard_mining_scores_{stamp}.csv")
    p.add_argument("--out-summary-json", type=str, default=f"runs/hard_mining_summary_{stamp}.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_hard_mining_target_weights(
        targets=str(args.targets),
        ood_pair_csv=str(args.ood_pair_csv),
        accuracy_external_csv=str(args.accuracy_external_csv),
        stage2_csv=str(args.stage2_csv),
        topk=int(args.topk),
        base_weight=float(args.base_weight),
        max_weight=float(args.max_weight),
        weight_scale=float(args.weight_scale),
        unpaired_boost=float(args.unpaired_boost),
        ood_rmsd_threshold=float(args.ood_rmsd_threshold),
        native_rmsd_threshold=float(args.native_rmsd_threshold),
        uncertainty_threshold=float(args.uncertainty_threshold),
        fallback_ratio_threshold=float(args.fallback_ratio_threshold),
        physics_violations_threshold=float(args.physics_violations_threshold),
        uncertainty_weight=float(args.uncertainty_weight),
        fallback_weight=float(args.fallback_weight),
        physics_weight=float(args.physics_weight),
        out_target_weights_csv=str(args.out_target_weights_csv),
        out_score_csv=str(args.out_score_csv),
        out_summary_json=str(args.out_summary_json),
        priority_targets_csv=str(args.priority_targets_csv),
        priority_target_col=str(args.priority_target_col),
        priority_bonus=float(args.priority_bonus),
    )
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
