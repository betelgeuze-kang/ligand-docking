#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import math
from pathlib import Path
from typing import Any

import numpy as np

from tools.lib.artifacts import (
    artifact as _artifact,
    read_csv as _read_csv,
    read_json as _read_json,
    resolve as _resolve,
    summary as _summary,
    write_csv as _write_csv,
    write_json as _write_json,
)

DEFAULT_SCORES_CSV = "runs/gpcr_drd2_weakbase_false_support_shadow_replay_scores_current.csv"
DEFAULT_SCORE_COL = "binding_score_composite_v7_htr2a_oprm1_drd2_weakbase_false_support_shadow"
DEFAULT_POSE_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
DEFAULT_A1_QUEUE_JSON = "runs/gpcr_a1_accuracy_repair_queue_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_guarded_shadow_claim_review_current.json"
DEFAULT_OUT_MD = "runs/gpcr_guarded_shadow_claim_review_current.md"
DEFAULT_OUT_ROWS_CSV = "runs/gpcr_guarded_shadow_claim_review_rows_current.csv"

DEFAULT_POSITIVES = {
    "CHEMBL217_DRD2_HUMAN": "CHEMBL301265",
    "CHEMBL224_HTR2A_HUMAN": "CHEMBL83894",
    "CHEMBL233_OPRM1_HUMAN": "CHEMBL331883",
}

DEFAULT_PR_AUC_MIN = 0.55
DEFAULT_PR_AUC_CI_LOW_MIN = 0.45
DEFAULT_TOP20_POSITIVE_RECALL_MIN = 1.0
DEFAULT_TOPK = 20


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive_pairs(pose_gap: dict[str, Any], extra_pairs: list[str] | None = None) -> dict[str, str]:
    pairs = dict(DEFAULT_POSITIVES)
    rows = pose_gap.get("target_summaries", [])
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            target = _text(row.get("target"))
            ligand_id = _text(row.get("ligand_id"))
            if target in pairs and ligand_id:
                pairs[target] = ligand_id
    for spec in extra_pairs or []:
        if "=" not in spec:
            continue
        target, ligand_id = spec.split("=", 1)
        target = target.strip()
        ligand_id = ligand_id.strip()
        if target and ligand_id:
            pairs[target] = ligand_id
    return pairs


def _is_positive(row: dict[str, Any], positives: dict[str, str]) -> bool:
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    return bool(target and ligand_id and positives.get(target) == ligand_id)


def _average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    y = labels.astype(np.int64)
    n_pos = int(np.sum(y == 1))
    if n_pos <= 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ys = y[order]
    tp = np.cumsum(ys == 1)
    precision = tp / np.maximum(np.arange(len(ys), dtype=np.float64) + 1.0, 1.0)
    ap = float(np.sum(precision[ys == 1]) / float(n_pos))
    return ap


def _bootstrap_ap_ci(
    labels: np.ndarray,
    scores: np.ndarray,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    point = _average_precision(labels, scores)
    if int(n_boot) <= 0:
        return {
            "low": point,
            "high": point,
            "mean": point,
            "std": 0.0,
            "n": 0,
            "method": "disabled_point_estimate",
        }
    rng = np.random.default_rng(int(seed))
    n = int(len(labels))
    vals: list[float] = []
    y = labels.astype(np.int64)
    s = scores.astype(np.float64)
    for _ in range(int(n_boot)):
        idx = rng.integers(0, n, size=n)
        yb = y[idx]
        if int(np.sum(yb == 1)) <= 0 or int(np.sum(yb == 0)) <= 0:
            continue
        vals.append(_average_precision(yb, s[idx]))
    if not vals:
        return {
            "low": None,
            "high": None,
            "mean": None,
            "std": None,
            "n": 0,
            "method": "row_bootstrap_percentile_95",
        }
    arr = np.asarray(vals, dtype=np.float64)
    return {
        "low": float(np.percentile(arr, 2.5)),
        "high": float(np.percentile(arr, 97.5)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=0)),
        "n": int(len(arr)),
        "method": "row_bootstrap_percentile_95",
    }


def _rank_rows(rows: list[dict[str, Any]], score_col: str) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        score = _float(row.get(score_col))
        if score is None:
            continue
        enriched = dict(row)
        enriched["_source_index"] = idx
        enriched["_score"] = score
        ranked.append(enriched)
    ranked.sort(key=lambda row: (float(row["_score"]), _text(row.get("target")), _text(row.get("ligand_id"))))
    for rank, row in enumerate(ranked, start=1):
        row["_global_rank"] = rank
    target_groups: dict[str, list[dict[str, Any]]] = {}
    for row in ranked:
        target_groups.setdefault(_text(row.get("target")), []).append(row)
    for target_rows in target_groups.values():
        target_rows.sort(key=lambda row: (float(row["_score"]), _text(row.get("ligand_id"))))
        for target_rank, row in enumerate(target_rows, start=1):
            row["_target_rank"] = target_rank
    return ranked


def _positive_summaries(
    ranked_rows: list[dict[str, Any]],
    positives: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    by_pair = {(_text(row.get("target")), _text(row.get("ligand_id"))): row for row in ranked_rows}
    summaries: list[dict[str, Any]] = []
    missing: list[str] = []
    for target, ligand_id in positives.items():
        row = by_pair.get((target, ligand_id))
        if row is None:
            missing.append(f"{target}={ligand_id}")
            continue
        target_rank = int(row["_target_rank"])
        summaries.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "global_rank": int(row["_global_rank"]),
                "target_rank": target_rank,
                "decoys_above_positive": int(max(0, target_rank - 1)),
                "score": float(row["_score"]),
            }
        )
    summaries.sort(key=lambda row: (int(row["global_rank"]), _text(row.get("target"))))
    return summaries, missing


def _review_rows(
    ranked_rows: list[dict[str, Any]],
    positives: dict[str, str],
    *,
    score_col: str,
    topk: int,
) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for row in ranked_rows[: int(max(1, topk))]:
        selected[(_text(row.get("target")), _text(row.get("ligand_id")))] = row
    for row in ranked_rows:
        if _is_positive(row, positives):
            selected[(_text(row.get("target")), _text(row.get("ligand_id")))] = row
    out: list[dict[str, Any]] = []
    for row in sorted(selected.values(), key=lambda item: int(item["_global_rank"])):
        is_pos = _is_positive(row, positives)
        in_topk = int(row["_global_rank"]) <= int(topk)
        if is_pos and in_topk:
            row_kind = "topk_positive"
        elif is_pos:
            row_kind = "positive"
        else:
            row_kind = "topk_decoy"
        target_rank = int(row.get("_target_rank") or 0)
        out.append(
            {
                "row_kind": row_kind,
                "global_rank": int(row["_global_rank"]),
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "is_positive": int(is_pos),
                "score_col": score_col,
                "score": float(row["_score"]),
                "target_rank": target_rank,
                "decoys_above_positive": int(max(0, target_rank - 1)) if is_pos else "",
            }
        )
    return out


def build_review(
    *,
    scores_csv: str | Path = DEFAULT_SCORES_CSV,
    score_col: str = DEFAULT_SCORE_COL,
    pose_gap_json: str | Path = DEFAULT_POSE_GAP_JSON,
    a1_queue_json: str | Path = DEFAULT_A1_QUEUE_JSON,
    positive_pair: list[str] | None = None,
    topk: int = DEFAULT_TOPK,
    bootstrap_n: int = 400,
    bootstrap_seed: int = 20260509,
    pr_auc_min: float = DEFAULT_PR_AUC_MIN,
    pr_auc_ci_low_min: float = DEFAULT_PR_AUC_CI_LOW_MIN,
    top20_positive_recall_min: float = DEFAULT_TOP20_POSITIVE_RECALL_MIN,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = _read_csv(scores_csv)
    pose_gap = _read_json(pose_gap_json)
    a1_queue = _read_json(a1_queue_json)
    positives = _positive_pairs(pose_gap, positive_pair)
    ranked = _rank_rows(rows, score_col)
    if not ranked:
        raise ValueError(f"No finite rows found for score column `{score_col}` in {scores_csv}")

    labels = np.asarray([1 if _is_positive(row, positives) else 0 for row in ranked], dtype=np.int64)
    scores = np.asarray([float(row["_score"]) for row in ranked], dtype=np.float64)
    positive_count = int(np.sum(labels == 1))
    negative_count = int(np.sum(labels == 0))
    pr_auc = _average_precision(labels, scores)
    ci = _bootstrap_ap_ci(labels, scores, n_boot=int(bootstrap_n), seed=int(bootstrap_seed))
    positive_summaries, missing_positive_pairs = _positive_summaries(ranked, positives)

    kk = int(min(max(1, topk), len(ranked)))
    top_labels = labels[:kk]
    top_positive_count = int(np.sum(top_labels == 1))
    top_positive_recall = float(top_positive_count / positive_count) if positive_count > 0 else float("nan")
    top_slot_hit_rate = float(top_positive_count / kk) if kk > 0 else float("nan")
    top_missing = [
        row
        for row in positive_summaries
        if int(row.get("global_rank") or 0) > kk
    ]

    a1_summary = _summary(a1_queue)
    pre_review_ready = bool(a1_summary.get("guarded_100k_rerun_allowed_now"))

    blockers: list[str] = []
    if positive_count <= 0 or negative_count <= 0:
        blockers.append("positive_or_negative_labels_missing")
    if missing_positive_pairs:
        blockers.append("positive_reference_rows_missing")
    if not pre_review_ready:
        blockers.append("pre_review_repair_gates_not_completed")
    if not math.isfinite(pr_auc) or pr_auc < float(pr_auc_min):
        blockers.append("ranking_pr_auc_below_threshold")
    ci_low = ci.get("low")
    if ci_low is None or not math.isfinite(float(ci_low)) or float(ci_low) < float(pr_auc_ci_low_min):
        blockers.append("ranking_pr_auc_ci_low_below_threshold")
    if not math.isfinite(top_positive_recall) or top_positive_recall < float(top20_positive_recall_min):
        blockers.append("top20_positive_recall_below_threshold")
    if any(int(row.get("target_rank") or 0) != 1 for row in positive_summaries):
        blockers.append("target_internal_positive_rank_not_1")

    diagnostic_warnings: list[str] = [
        "claim_locked_shadow_review_only_not_active_scorer",
    ]
    if int(len(ranked)) < 100000:
        diagnostic_warnings.append("shadow_input_not_full_100k_scale")
    if positive_count < kk:
        diagnostic_warnings.append("top20_slot_hit_rate_limited_by_three_positive_diagnostic_set")

    if blockers == ["ranking_pr_auc_ci_low_below_threshold"]:
        status = "blocked_guarded_shadow_claim_review_ci_low"
    elif blockers:
        status = "blocked_guarded_shadow_claim_review"
    else:
        status = "guarded_shadow_claim_review_green_diagnostic_only"

    if "ranking_pr_auc_ci_low_below_threshold" in blockers:
        next_required_step = (
            "Expand non-leaky GPCR positive coverage and rerun the guarded 100k review; current shadow replay recovers "
            "the three target positives but does not certify PR-AUC CI-low stability."
        )
    elif blockers:
        next_required_step = (
            "Resolve the listed guarded shadow review blockers before any claim/scorer promotion; keep thresholds and "
            "target-identity leakage locked."
        )
    else:
        next_required_step = (
            "Use this only as diagnostic evidence, then run the full guarded 100k claim review and regenerate the "
            "accuracy parity scorecard before considering promotion."
        )

    review_rows = _review_rows(ranked, positives, score_col=score_col, topk=kk)
    payload = {
        "packet_type": "gpcr_guarded_shadow_claim_review",
        "summary": {
            "generated_at_local": generated_at_local
            or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": status,
            "input_rows": int(len(ranked)),
            "score_col": score_col,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "ranking_pr_auc": pr_auc,
            "ranking_pr_auc_ci_low": ci.get("low"),
            "ranking_pr_auc_ci_high": ci.get("high"),
            "ranking_pr_auc_ci_mean": ci.get("mean"),
            "ranking_pr_auc_ci_std": ci.get("std"),
            "ranking_pr_auc_ci_n": ci.get("n"),
            "ranking_pr_auc_ci_method": ci.get("method"),
            "ranking_pr_auc_min": float(pr_auc_min),
            "ranking_pr_auc_ci_low_min": float(pr_auc_ci_low_min),
            "topk": kk,
            "top20_positive_count": top_positive_count,
            "top20_positive_recall": top_positive_recall,
            "top20_slot_hit_rate": top_slot_hit_rate,
            "top20_positive_recall_min": float(top20_positive_recall_min),
            "all_positive_target_rank_1": bool(
                positive_summaries and all(int(row.get("target_rank") or 0) == 1 for row in positive_summaries)
            ),
            "pre_review_repair_gates_completed": pre_review_ready,
            "missing_positive_pairs": missing_positive_pairs,
            "top20_missing_positives": top_missing,
            "blockers": blockers,
            "diagnostic_warnings": diagnostic_warnings,
            "guarded_shadow_claim_review_passed": not blockers,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "next_required_step": next_required_step,
        },
        "positive_pairs": positives,
        "positive_summaries": positive_summaries,
        "source_artifacts": {
            "scores_csv": _artifact(scores_csv),
            "pose_gap_json": _artifact(pose_gap_json),
            "a1_queue_json": _artifact(a1_queue_json),
        },
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "active_scorer_apply_allowed": False,
            "target_identity_feature_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "shadow_review_only": True,
            "full_100k_claim_review_required": True,
        },
    }
    return payload, review_rows


def _fmt(value: Any, digits: int = 6) -> str:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f"{float(value):.{digits}g}"
    if value is None:
        return "None"
    return str(value)


def _render_md(payload: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Guarded Shadow Claim Review",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- input_rows: `{summary['input_rows']}`",
        f"- score_col: `{summary['score_col']}`",
        f"- ranking_pr_auc: `{_fmt(summary['ranking_pr_auc'])}`",
        f"- ranking_pr_auc_ci_low: `{_fmt(summary['ranking_pr_auc_ci_low'])}`",
        f"- top20_positive_count: `{summary['top20_positive_count']}`",
        f"- top20_positive_recall: `{_fmt(summary['top20_positive_recall'])}`",
        f"- top20_slot_hit_rate: `{_fmt(summary['top20_slot_hit_rate'])}`",
        f"- all_positive_target_rank_1: `{str(summary['all_positive_target_rank_1']).lower()}`",
        f"- pre_review_repair_gates_completed: `{str(summary['pre_review_repair_gates_completed']).lower()}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- blockers: `{', '.join(summary['blockers']) or 'none'}`",
        "",
        "## Positives",
        "",
        "| Target | Ligand | Global rank | Target rank | Decoys above | Score |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["positive_summaries"]:
        lines.append(
            f"| `{row['target']}` | `{row['ligand_id']}` | {row['global_rank']} | {row['target_rank']} | "
            f"{row['decoys_above_positive']} | {_fmt(row['score'])} |"
        )
    lines.extend(
        [
            "",
            "## Top Rows",
            "",
            "| Rank | Kind | Target | Ligand | Positive | Score |",
            "|---:|---|---|---|---:|---:|",
        ]
    )
    for row in rows[: int(summary["topk"])]:
        lines.append(
            f"| {row['global_rank']} | `{row['row_kind']}` | `{row['target']}` | `{row['ligand_id']}` | "
            f"{row['is_positive']} | {_fmt(row['score'])} |"
        )
    lines.extend(["", f"## Next Required Step", "", summary["next_required_step"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a claim-locked GPCR guarded shadow review packet.")
    parser.add_argument("--scores-csv", default=DEFAULT_SCORES_CSV)
    parser.add_argument("--score-col", default=DEFAULT_SCORE_COL)
    parser.add_argument("--pose-gap-json", default=DEFAULT_POSE_GAP_JSON)
    parser.add_argument("--a1-queue-json", default=DEFAULT_A1_QUEUE_JSON)
    parser.add_argument(
        "--positive-pair",
        action="append",
        default=[],
        help="Override/add a positive pair as TARGET=LIGAND. May be repeated.",
    )
    parser.add_argument("--topk", type=int, default=DEFAULT_TOPK)
    parser.add_argument("--bootstrap-n", type=int, default=400)
    parser.add_argument("--bootstrap-seed", type=int, default=20260509)
    parser.add_argument("--pr-auc-min", type=float, default=DEFAULT_PR_AUC_MIN)
    parser.add_argument("--pr-auc-ci-low-min", type=float, default=DEFAULT_PR_AUC_CI_LOW_MIN)
    parser.add_argument("--top20-positive-recall-min", type=float, default=DEFAULT_TOP20_POSITIVE_RECALL_MIN)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-rows-csv", default=DEFAULT_OUT_ROWS_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, rows = build_review(
        scores_csv=args.scores_csv,
        score_col=args.score_col,
        pose_gap_json=args.pose_gap_json,
        a1_queue_json=args.a1_queue_json,
        positive_pair=args.positive_pair,
        topk=args.topk,
        bootstrap_n=args.bootstrap_n,
        bootstrap_seed=args.bootstrap_seed,
        pr_auc_min=args.pr_auc_min,
        pr_auc_ci_low_min=args.pr_auc_ci_low_min,
        top20_positive_recall_min=args.top20_positive_recall_min,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_rows_csv, rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload, rows), encoding="utf-8")
    import json

    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
