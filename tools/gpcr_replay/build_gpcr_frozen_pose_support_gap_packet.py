#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_SCORES_CSV = (
    "runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv"
)
DEFAULT_LABEL_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_OUT_JSON = "runs/gpcr_frozen_pose_support_gap_packet_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_frozen_pose_support_gap_packet_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_frozen_pose_support_gap_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = [dict(row) for row in csv.DictReader(fh)]
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def _label_map(label_csv: str | Path) -> dict[tuple[str, str], bool]:
    labels: dict[tuple[str, str], bool] = {}
    for row in _read_csv(label_csv):
        key = (str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip())
        value = str(row.get("is_binder", "")).strip().lower()
        labels[key] = value in {"1", "true", "yes", "binder", "positive"}
    return labels


def _mean(rows: list[dict[str, str]], col: str) -> float:
    if not rows:
        return 0.0
    return float(sum(_safe_float(row.get(col)) for row in rows) / len(rows))


def _blockers(*, positive: dict[str, str], above: list[dict[str, str]]) -> list[str]:
    support = _safe_float(positive.get("label_free_support_pressure"))
    weak_support = _safe_float(positive.get("weak_base_rescue_support_pressure"))
    pose_support = _safe_float(positive.get("pose_preservation_support"))
    pose_rmsd = _safe_float(positive.get("coarse_centroid_preservation_rmsd_A_mean"))
    base_score = _safe_float(positive.get("base_score"))
    blockers: list[str] = []
    if above:
        blockers.append("target_decoys_above_positive")
    if support < 0.05 and weak_support < 0.05:
        blockers.append("positive_anchor_support_missing")
    if pose_rmsd > 6.0 or pose_support < 0.20:
        blockers.append("positive_pose_backmapping_collapse")
    elif pose_support < 0.50:
        blockers.append("positive_pose_preservation_borderline")
    if above and _mean(above[:50], "base_score") < base_score - 1.0:
        blockers.append("base_score_decoy_intrusion")
    if above and _mean(above[:50], "multipolar_basic_pressure") > max(0.20, _safe_float(positive.get("multipolar_basic_pressure")) + 0.10):
        blockers.append("multipolar_decoy_pressure_not_sufficient")
    if above and _mean(above[:50], "label_free_support_pressure") > support + 0.10 and support < 0.10:
        blockers.append("decoy_anchor_support_exceeds_positive")
    return blockers


def build_packet(
    *,
    input_scores_csv: str | Path = DEFAULT_INPUT_SCORES_CSV,
    label_csv: str | Path = DEFAULT_LABEL_CSV,
    score_col: str = "binding_score_composite_v7_residual_shadow",
    top_decoy_count: int = 50,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    rows = _read_csv(input_scores_csv)
    labels = _label_map(label_csv)
    if score_col not in rows[0]:
        raise ValueError(f"score column not found: {score_col}")
    ranked = sorted(rows, key=lambda row: _safe_float(row.get(score_col), 1.0e9))
    target_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ranked:
        target_rows[str(row.get("target", "")).strip()].append(row)

    global_rank_by_key = {
        (str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip()): rank
        for rank, row in enumerate(ranked, start=1)
    }
    target_summaries: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    for target, target_ranked in sorted(target_rows.items()):
        positives = [
            row
            for row in target_ranked
            if labels.get((target, str(row.get("ligand_id", "")).strip()), False)
        ]
        for positive in positives:
            key = (target, str(positive.get("ligand_id", "")).strip())
            target_rank = target_ranked.index(positive) + 1
            above = [
                row
                for row in target_ranked[: target_rank - 1]
                if not labels.get((target, str(row.get("ligand_id", "")).strip()), False)
            ]
            selected_above = above[: max(1, int(top_decoy_count))]
            blockers = _blockers(positive=positive, above=above)
            blocker_counts.update(blockers)
            target_summaries.append(
                {
                    "target": target,
                    "ligand_id": key[1],
                    "global_rank": global_rank_by_key[key],
                    "target_rank": target_rank,
                    "decoys_above_positive": len(above),
                    "shadow_score": _safe_float(positive.get(score_col)),
                    "base_score": _safe_float(positive.get("base_score")),
                    "label_free_support_pressure": _safe_float(positive.get("label_free_support_pressure")),
                    "weak_base_rescue_support_pressure": _safe_float(positive.get("weak_base_rescue_support_pressure")),
                    "pose_preservation_support": _safe_float(positive.get("pose_preservation_support")),
                    "coarse_centroid_preservation_rmsd_A_mean": _safe_float(
                        positive.get("coarse_centroid_preservation_rmsd_A_mean")
                    ),
                    "basic_amine_count": _safe_float(positive.get("basic_amine_count")),
                    "multipolar_basic_pressure": _safe_float(positive.get("multipolar_basic_pressure")),
                    "v12_synthetic_anchor_saturation_pressure": _safe_float(
                        positive.get("gpcr_synthetic_anchor_saturation_pressure_v12")
                    ),
                    "v12_moderate_multi_basic_weakbase_support": _safe_float(
                        positive.get("gpcr_moderate_multi_basic_weakbase_support_v12")
                    ),
                    "top_decoy_count_analyzed": len(selected_above),
                    "top_decoy_base_score_mean": _mean(selected_above, "base_score"),
                    "top_decoy_shadow_score_mean": _mean(selected_above, score_col),
                    "top_decoy_label_free_support_mean": _mean(selected_above, "label_free_support_pressure"),
                    "top_decoy_pose_preservation_mean": _mean(selected_above, "pose_preservation_support"),
                    "top_decoy_multipolar_basic_pressure_mean": _mean(selected_above, "multipolar_basic_pressure"),
                    "blockers": blockers,
                }
            )

    top20_positive_count = sum(
        1
        for row in ranked[:20]
        if labels.get((str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip()), False)
    )
    status = "blocked_pose_support_gap_claim_locked"
    if target_summaries and not blocker_counts and top20_positive_count == len(target_summaries):
        status = "pose_support_gap_green_claim_locked"
    next_required_step = (
        "Repair target-portable anchor occupancy and pose-survival support for positives with missing support "
        "before any guarded 100k rerun. Keep v12 shadow-only and active-score locked."
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_scores_csv": str(_resolve(input_scores_csv)),
        "label_csv": str(_resolve(label_csv)),
        "score_col": score_col,
        "input_rows": len(rows),
        "positive_count": len(target_summaries),
        "top20_positive_count": top20_positive_count,
        "blocked_positive_count": sum(1 for row in target_summaries if row["blockers"]),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "broad_gpcr_claim_allowed": False,
        "labels_used_for_review_only": True,
        "labels_used_for_scoring": False,
        "threshold_relaxation_allowed": False,
        "fake_pass_allowed": False,
        "next_required_step": next_required_step,
    }
    return {
        "packet_type": "gpcr_frozen_pose_support_gap_packet",
        "summary": summary,
        "target_summaries": target_summaries,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "labels_used_for_scoring": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Pose Support Gap Packet",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- input_rows: `{summary['input_rows']}`",
        f"- positive_count: `{summary['positive_count']}`",
        f"- top20_positive_count: `{summary['top20_positive_count']}`",
        f"- blocked_positive_count: `{summary['blocked_positive_count']}`",
        "- claim_promotion_allowed: `false`",
        "- scorer_apply_allowed: `false`",
        "",
        "## Blocker Counts",
        "",
    ]
    if summary["blocker_counts"]:
        for blocker, count in summary["blocker_counts"].items():
            lines.append(f"- `{blocker}`: `{count}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Target Summaries", ""])
    for row in payload["target_summaries"]:
        blockers = ", ".join(f"`{item}`" for item in row["blockers"]) or "none"
        lines.append(
            f"- `{row['target']}` / `{row['ligand_id']}`: global_rank `{row['global_rank']}`, "
            f"target_rank `{row['target_rank']}`, decoys_above `{row['decoys_above_positive']}`, "
            f"support `{row['label_free_support_pressure']:.4f}`, weak_support "
            f"`{row['weak_base_rescue_support_pressure']:.4f}`, pose_support "
            f"`{row['pose_preservation_support']:.4f}`, pose_rmsd "
            f"`{row['coarse_centroid_preservation_rmsd_A_mean']:.4f}`, blockers {blockers}"
        )
    lines.extend(["", "## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a claim-locked GPCR frozen pose-support gap packet.")
    parser.add_argument("--input-scores-csv", default=DEFAULT_INPUT_SCORES_CSV)
    parser.add_argument("--label-csv", default=DEFAULT_LABEL_CSV)
    parser.add_argument("--score-col", default="binding_score_composite_v7_residual_shadow")
    parser.add_argument("--top-decoy-count", type=int, default=50)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_packet(
        input_scores_csv=args.input_scores_csv,
        label_csv=args.label_csv,
        score_col=args.score_col,
        top_decoy_count=args.top_decoy_count,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["target_summaries"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
