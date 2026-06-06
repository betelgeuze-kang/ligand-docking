#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NONE_POSITIVE_CACHE_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_current.csv"
DEFAULT_ALLBASIC_POSITIVE_CACHE_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_allbasic_current.csv"
DEFAULT_NONE_PARTIAL_REPLAY_SCORES_CSV = "runs/gpcr_cationic_pose_distortion_v10_frozen_partial_shadow_replay_scores_current.csv"
DEFAULT_ALLBASIC_PARTIAL_REPLAY_SCORES_CSV = "runs/gpcr_cationic_pose_distortion_v10_frozen_allbasic_partial_shadow_replay_scores_current.csv"
DEFAULT_LABELS_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_OUT_JSON = "runs/gpcr_cationic_pose_distortion_frozen_cache_mode_review_current.json"
DEFAULT_OUT_MD = "runs/gpcr_cationic_pose_distortion_frozen_cache_mode_review_current.md"
DEFAULT_SCORE_COL = "binding_score_composite_v7_residual_shadow"
DEFAULT_POSITIVE_LIGAND_ID = "CHEMBL301265"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def _label_lookup(labels_csv: str | Path) -> dict[tuple[str, str], bool]:
    out: dict[tuple[str, str], bool] = {}
    for row in _read_csv(labels_csv):
        out[(str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip())] = str(
            row.get("is_binder", "")
        ).strip().lower() in {"1", "true", "yes", "y"}
    return out


def _first_row(rows: list[dict[str, str]], ligand_id: str) -> dict[str, str]:
    for row in rows:
        if str(row.get("ligand_id", "")).strip() == ligand_id:
            return row
    return {}


def _partial_replay_rank_summary(scores_csv: str | Path, labels_csv: str | Path, score_col: str) -> dict[str, Any]:
    rows = _read_csv(scores_csv)
    labels = _label_lookup(labels_csv)
    ranked = sorted(rows, key=lambda row: _float(row.get(score_col), 1.0e9))
    positive_ranks: list[int] = []
    top10_decoy_count = 0
    for index, row in enumerate(ranked, start=1):
        key = (str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip())
        is_positive = bool(labels.get(key, False))
        if is_positive:
            positive_ranks.append(index)
        if index <= 10 and not is_positive:
            top10_decoy_count += 1
    return {
        "rows": len(rows),
        "positive_count": len(positive_ranks),
        "positive_ranks": positive_ranks,
        "first_positive_rank": min(positive_ranks) if positive_ranks else None,
        "top10_decoy_count": top10_decoy_count,
        "top_ligand_id": ranked[0].get("ligand_id", "") if ranked else "",
        "top_is_positive": bool(labels.get((ranked[0].get("target", ""), ranked[0].get("ligand_id", "")), False))
        if ranked
        else False,
    }


def build_review(
    *,
    none_positive_cache_csv: str | Path = DEFAULT_NONE_POSITIVE_CACHE_CSV,
    allbasic_positive_cache_csv: str | Path = DEFAULT_ALLBASIC_POSITIVE_CACHE_CSV,
    none_partial_replay_scores_csv: str | Path = DEFAULT_NONE_PARTIAL_REPLAY_SCORES_CSV,
    allbasic_partial_replay_scores_csv: str | Path = DEFAULT_ALLBASIC_PARTIAL_REPLAY_SCORES_CSV,
    labels_csv: str | Path = DEFAULT_LABELS_CSV,
    score_col: str = DEFAULT_SCORE_COL,
    positive_ligand_id: str = DEFAULT_POSITIVE_LIGAND_ID,
) -> dict[str, Any]:
    none_positive = _first_row(_read_csv(none_positive_cache_csv), positive_ligand_id)
    allbasic_positive = _first_row(_read_csv(allbasic_positive_cache_csv), positive_ligand_id)
    none_rank = _partial_replay_rank_summary(none_partial_replay_scores_csv, labels_csv, score_col)
    allbasic_rank = _partial_replay_rank_summary(allbasic_partial_replay_scores_csv, labels_csv, score_col)
    none_support = _float(none_positive.get("label_free_support_pressure"), 0.0)
    allbasic_support = _float(allbasic_positive.get("label_free_support_pressure"), 0.0)
    blockers: list[str] = []
    if none_support <= 0.0:
        blockers.append("label_free_none_anchor_mode_does_not_rescue_drd2_positive")
    if allbasic_rank["top10_decoy_count"] > 0:
        blockers.append("all_basic_anchor_mode_overpromotes_decoys_in_partial_replay")
    if allbasic_support > none_support and blockers:
        blockers.append("selected_slice_positive_only_anchor_is_not_label_free_portable")
    status = "blocked_feature_contract_not_portable_yet" if blockers else "portable_feature_mode_candidate_ready"
    return {
        "packet_type": "gpcr_cationic_pose_distortion_frozen_cache_mode_review",
        "summary": {
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": status,
            "positive_ligand_id": positive_ligand_id,
            "none_positive_support_pressure": none_support,
            "none_positive_penalty_pressure": _float(none_positive.get("label_free_penalty_pressure"), 0.0),
            "none_positive_cationic_window_fraction": _float(
                none_positive.get("cationic_center_contact_fraction_2p8_4p2A"),
                0.0,
            ),
            "allbasic_positive_support_pressure": allbasic_support,
            "allbasic_positive_penalty_pressure": _float(allbasic_positive.get("label_free_penalty_pressure"), 0.0),
            "allbasic_positive_cationic_window_fraction": _float(
                allbasic_positive.get("cationic_center_contact_fraction_2p8_4p2A"),
                0.0,
            ),
            "none_partial_replay": none_rank,
            "allbasic_partial_replay": allbasic_rank,
            "blockers": blockers,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "next_required_step": (
                "Design a label-free anchor placement/pose-survival mode that rescues DRD2 positive geometry "
                "without all-basic decoy overpromotion, then rerun frozen-row shadow replay before any guarded 100k claim review."
            ),
        },
        "claim_boundary": {
            "selected_slice_green_is_not_claim_evidence": True,
            "partial_frozen_cache_is_not_claim_evidence": True,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Cationic Pose-Distortion Frozen Cache Mode Review",
        "",
        f"- status: `{summary['status']}`",
        f"- none_positive_support_pressure: `{summary['none_positive_support_pressure']}`",
        f"- allbasic_positive_support_pressure: `{summary['allbasic_positive_support_pressure']}`",
        f"- none_partial_first_positive_rank: `{summary['none_partial_replay']['first_positive_rank']}`",
        f"- allbasic_partial_first_positive_rank: `{summary['allbasic_partial_replay']['first_positive_rank']}`",
        f"- allbasic_partial_top10_decoy_count: `{summary['allbasic_partial_replay']['top10_decoy_count']}`",
        "- claim_promotion_allowed: `false`",
        "",
        "## Blockers",
        "",
    ]
    if summary["blockers"]:
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review label-free v10 frozen cache anchor modes.")
    parser.add_argument("--none-positive-cache-csv", default=DEFAULT_NONE_POSITIVE_CACHE_CSV)
    parser.add_argument("--allbasic-positive-cache-csv", default=DEFAULT_ALLBASIC_POSITIVE_CACHE_CSV)
    parser.add_argument("--none-partial-replay-scores-csv", default=DEFAULT_NONE_PARTIAL_REPLAY_SCORES_CSV)
    parser.add_argument("--allbasic-partial-replay-scores-csv", default=DEFAULT_ALLBASIC_PARTIAL_REPLAY_SCORES_CSV)
    parser.add_argument("--labels-csv", default=DEFAULT_LABELS_CSV)
    parser.add_argument("--score-col", default=DEFAULT_SCORE_COL)
    parser.add_argument("--positive-ligand-id", default=DEFAULT_POSITIVE_LIGAND_ID)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_review(
        none_positive_cache_csv=args.none_positive_cache_csv,
        allbasic_positive_cache_csv=args.allbasic_positive_cache_csv,
        none_partial_replay_scores_csv=args.none_partial_replay_scores_csv,
        allbasic_partial_replay_scores_csv=args.allbasic_partial_replay_scores_csv,
        labels_csv=args.labels_csv,
        score_col=args.score_col,
        positive_ligand_id=args.positive_ligand_id,
    )
    _write_json(args.out_json, payload)
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
