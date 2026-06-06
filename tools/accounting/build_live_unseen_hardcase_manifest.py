#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _norm(text: Any) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def _norm_candidate(text: Any) -> str:
    token = _norm(text)
    if token.startswith("liveauto"):
        token = "live" + token[len("liveauto") :]
    return token


def _extract_failure_candidates(
    df: pd.DataFrame,
    *,
    min_fail_count: float,
) -> Dict[str, float]:
    score_by_candidate: Dict[str, float] = {}
    fail_col = "fail_count" if "fail_count" in df.columns else None
    candidate_cols = [c for c in ["target", "source_target", "protein_id", "uniprot_id"] if c in df.columns]
    if not candidate_cols:
        return score_by_candidate
    for _, row in df.iterrows():
        raw_fail = row.get(fail_col, 1.0) if fail_col else 1.0
        try:
            fail_count = float(raw_fail)
        except Exception:
            fail_count = 1.0
        if fail_count < float(min_fail_count):
            continue
        for col in candidate_cols:
            cand = _norm_candidate(row.get(col, ""))
            if not cand:
                continue
            prev = float(score_by_candidate.get(cand, 0.0))
            if fail_count > prev:
                score_by_candidate[cand] = float(fail_count)
    return score_by_candidate


def _match_score(target_norm: str, candidates: Dict[str, float]) -> float:
    if not target_norm:
        return 0.0
    best = 0.0
    for cand, score in candidates.items():
        if (cand in target_norm) or (target_norm in cand):
            best = max(best, float(score))
    return best


def _pick_targets(
    manifest_df: pd.DataFrame,
    *,
    candidates: Dict[str, float],
    max_targets: int,
    fallback_all: bool,
) -> Tuple[List[str], Dict[str, float], bool]:
    target_norms = {
        str(target): _norm(target) for target in manifest_df.get("target", pd.Series([], dtype="object")).astype(str)
    }
    score_by_target: Dict[str, float] = {}
    for target, target_norm in target_norms.items():
        score = _match_score(target_norm, candidates)
        if score > 0.0:
            score_by_target[target] = float(score)

    used_fallback = False
    if not score_by_target and fallback_all:
        used_fallback = True
        for target in target_norms.keys():
            score_by_target[target] = 1.0

    ranked = sorted(score_by_target.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    if int(max_targets) > 0:
        ranked = ranked[: int(max_targets)]
    selected_targets = [t for t, _ in ranked]
    return selected_targets, score_by_target, used_fallback


def build_manifest(
    *,
    live_manifest_csv: str,
    failure_breakdown_csv: str,
    out_manifest_csv: str,
    out_summary_json: str,
    min_fail_count: float = 1.0,
    max_targets: int = 0,
    skip_missing_output_npz: bool = True,
    fallback_all_targets: bool = True,
) -> Dict[str, Any]:
    if not os.path.exists(str(live_manifest_csv)):
        raise FileNotFoundError(f"live manifest not found: {live_manifest_csv}")
    manifest_df = pd.read_csv(str(live_manifest_csv))
    required = {"target", "split", "output_npz"}
    if not required.issubset(set(manifest_df.columns)):
        raise ValueError(f"live manifest missing required columns {required}: {live_manifest_csv}")

    source_rows = int(len(manifest_df))
    if bool(skip_missing_output_npz):
        exists_mask = manifest_df["output_npz"].astype(str).map(os.path.exists)
        manifest_df = manifest_df[exists_mask].copy()

    fail_df: Optional[pd.DataFrame] = None
    if os.path.exists(str(failure_breakdown_csv)):
        try:
            fail_df = pd.read_csv(str(failure_breakdown_csv))
        except pd.errors.EmptyDataError:
            fail_df = pd.DataFrame()
    else:
        fail_df = pd.DataFrame()
    failure_rows = int(len(fail_df)) if fail_df is not None else 0
    candidates = _extract_failure_candidates(
        fail_df if fail_df is not None else pd.DataFrame(),
        min_fail_count=float(min_fail_count),
    )
    selected_targets, score_by_target, used_fallback = _pick_targets(
        manifest_df,
        candidates=candidates,
        max_targets=int(max_targets),
        fallback_all=bool(fallback_all_targets),
    )
    if selected_targets:
        out_df = manifest_df[manifest_df["target"].astype(str).isin(set(selected_targets))].copy()
    else:
        out_df = manifest_df.iloc[0:0].copy()

    _ensure_parent(str(out_manifest_csv))
    out_df.to_csv(str(out_manifest_csv), index=False)

    rows_by_target = (
        out_df.groupby("target")["output_npz"]
        .count()
        .reset_index(name="rows")
        .sort_values("rows", ascending=False)
        .to_dict(orient="records")
    )
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "live_manifest_csv": str(live_manifest_csv),
        "failure_breakdown_csv": str(failure_breakdown_csv),
        "source_rows_before_filter": int(source_rows),
        "source_rows_after_filter": int(len(manifest_df)),
        "failure_rows": int(failure_rows),
        "candidate_keys": int(len(candidates)),
        "selected_targets_count": int(len(selected_targets)),
        "selected_targets": selected_targets,
        "used_fallback_all_targets": bool(used_fallback),
        "max_targets": int(max_targets),
        "min_fail_count": float(min_fail_count),
        "skip_missing_output_npz": bool(skip_missing_output_npz),
        "rows_total": int(len(out_df)),
        "rows_by_target": rows_by_target,
        "score_by_target": {k: float(v) for k, v in score_by_target.items()},
        "out_manifest_csv": str(out_manifest_csv),
        "pass": bool(len(out_df) > 0),
    }
    _ensure_parent(str(out_summary_json))
    with open(str(out_summary_json), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Build active-learning hardcase manifest from live_unseen distilled manifest + "
            "rolling failure breakdown."
        )
    )
    p.add_argument("--live-manifest-csv", type=str, default="runs/distilled_residual_manifest_live_unseen.csv")
    p.add_argument("--failure-breakdown-csv", type=str, default="runs/live_unseen_failure_breakdown_rolling.csv")
    p.add_argument("--min-fail-count", type=float, default=1.0)
    p.add_argument("--max-targets", type=int, default=32)
    p.add_argument("--skip-missing-output-npz", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--fallback-all-targets", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--out-manifest-csv",
        type=str,
        default=f"runs/active_learning_live_unseen_hardcase_manifest_{stamp}.csv",
    )
    p.add_argument(
        "--out-summary-json",
        type=str,
        default=f"runs/active_learning_live_unseen_hardcase_manifest_{stamp}.json",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    summary = build_manifest(
        live_manifest_csv=str(args.live_manifest_csv),
        failure_breakdown_csv=str(args.failure_breakdown_csv),
        out_manifest_csv=str(args.out_manifest_csv),
        out_summary_json=str(args.out_summary_json),
        min_fail_count=float(args.min_fail_count),
        max_targets=int(args.max_targets),
        skip_missing_output_npz=bool(args.skip_missing_output_npz),
        fallback_all_targets=bool(args.fallback_all_targets),
    )
    print(
        json.dumps(
            {
                "pass": bool(summary.get("pass", False)),
                "rows_total": int(summary.get("rows_total", 0)),
                "selected_targets_count": int(summary.get("selected_targets_count", 0)),
                "out_manifest_csv": str(summary.get("out_manifest_csv", "")),
                "out_summary_json": str(args.out_summary_json),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not bool(summary.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

