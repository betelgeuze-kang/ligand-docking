#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_SCORES_CSV = (
    "runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_16500_shadow_replay_scores_current.csv"
)
DEFAULT_INPUT_SUMMARY_JSON = (
    "runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_16500_shadow_replay_summary_current.json"
)
DEFAULT_LABEL_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_OUT_JSON = "runs/gpcr_cationic_weakbase_v11_frozen_shadow_replay_review_current.json"
DEFAULT_OUT_MD = "runs/gpcr_cationic_weakbase_v11_frozen_shadow_replay_review_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = [dict(row) for row in csv.DictReader(fh)]
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def _label_map(label_csv: str | Path) -> dict[tuple[str, str], bool]:
    labels: dict[tuple[str, str], bool] = {}
    for row in _read_rows(label_csv):
        key = (str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip())
        value = str(row.get("is_binder", "")).strip().lower()
        labels[key] = value in {"1", "true", "yes", "binder", "positive"}
    return labels


def _score_summary(
    rows: list[dict[str, str]],
    *,
    labels: dict[tuple[str, str], bool],
    score_col: str,
) -> dict[str, Any]:
    if score_col not in rows[0]:
        raise ValueError(f"score column not found: {score_col}")
    ranked = sorted(rows, key=lambda row: _safe_float(row.get(score_col), default=1.0e9))
    target_ranked: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ranked:
        target_ranked[str(row.get("target", "")).strip()].append(row)

    positive_ranks: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked, start=1):
        key = (str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip())
        if labels.get(key, False):
            positive_ranks.append(
                {
                    "global_rank": rank,
                    "target": key[0],
                    "ligand_id": key[1],
                    "score": _safe_float(row.get(score_col)),
                }
            )

    target_positive_ranks: dict[str, list[dict[str, Any]]] = {}
    for target, target_rows in sorted(target_ranked.items()):
        target_pos: list[dict[str, Any]] = []
        for rank, row in enumerate(target_rows, start=1):
            key = (target, str(row.get("ligand_id", "")).strip())
            if labels.get(key, False):
                target_pos.append(
                    {
                        "target_rank": rank,
                        "ligand_id": key[1],
                        "score": _safe_float(row.get(score_col)),
                        "decoys_above_positive": rank - 1,
                    }
                )
        if target_pos:
            target_positive_ranks[target] = target_pos

    return {
        "score_col": score_col,
        "positive_count": len(positive_ranks),
        "positive_ranks": positive_ranks,
        "target_positive_ranks": target_positive_ranks,
        "top20_positive_count": sum(1 for row in ranked[:20] if labels.get((row.get("target", ""), row.get("ligand_id", "")), False)),
        "top20_decoy_count": sum(1 for row in ranked[:20] if not labels.get((row.get("target", ""), row.get("ligand_id", "")), False)),
        "top10": [
            {
                "rank": rank,
                "target": str(row.get("target", "")).strip(),
                "ligand_id": str(row.get("ligand_id", "")).strip(),
                "is_positive": labels.get((str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip()), False),
                "score": _safe_float(row.get(score_col)),
                "basic_amine_count": _safe_float(row.get("basic_amine_count")),
                "label_free_support_pressure": _safe_float(row.get("label_free_support_pressure")),
                "weak_base_rescue_support_pressure": _safe_float(row.get("weak_base_rescue_support_pressure")),
            }
            for rank, row in enumerate(ranked[:10], start=1)
        ],
    }


def build_review(
    *,
    input_scores_csv: str | Path = DEFAULT_INPUT_SCORES_CSV,
    input_summary_json: str | Path = DEFAULT_INPUT_SUMMARY_JSON,
    label_csv: str | Path = DEFAULT_LABEL_CSV,
    base_score_col: str = "base_score",
    shadow_score_col: str = "binding_score_composite_v7_residual_shadow",
    expected_complete_rows: int = 30000,
) -> dict[str, Any]:
    scores_path = _resolve(input_scores_csv)
    summary_path = _resolve(input_summary_json)
    rows = _read_rows(scores_path)
    labels = _label_map(label_csv)
    replay_summary: dict[str, Any] = {}
    if summary_path.exists():
        replay_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    replay = replay_summary.get("summary", {}) if isinstance(replay_summary.get("summary", {}), dict) else {}
    active_locked = bool(replay.get("active_score_locked_to_base", False))
    base = _score_summary(rows, labels=labels, score_col=base_score_col)
    shadow = _score_summary(rows, labels=labels, score_col=shadow_score_col)

    blockers: list[str] = []
    if replay.get("status") != "ready_for_evaluation":
        blockers.append("replay_status_not_ready_for_evaluation")
    if not active_locked:
        blockers.append("active_score_not_locked_to_base")
    if len(rows) < int(expected_complete_rows):
        blockers.append("partial_frozen_coverage_only")
    if shadow["top20_positive_count"] <= 0:
        blockers.append("shadow_top20_has_no_positive")
    for target, target_pos in shadow["target_positive_ranks"].items():
        for positive in target_pos:
            if int(positive["decoys_above_positive"]) > 0:
                blockers.append(f"{target}_decoys_above_positive:{positive['decoys_above_positive']}")

    status = "blocked_frozen_shadow_review_claim_locked" if blockers else "frozen_shadow_green_claim_locked"
    payload = {
        "packet_type": "gpcr_cationic_weakbase_frozen_shadow_replay_review",
        "summary": {
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": status,
            "input_scores_csv": str(scores_path),
            "input_summary_json": str(summary_path),
            "label_csv": str(_resolve(label_csv)),
            "input_rows": len(rows),
            "expected_complete_rows": int(expected_complete_rows),
            "active_score_locked_to_base": active_locked,
            "base_score_col": base_score_col,
            "shadow_score_col": shadow_score_col,
            "base_score_summary": base,
            "shadow_score_summary": shadow,
            "blockers": blockers,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "next_required_step": (
                "Keep v11 claim-locked. Reduce all_basic synthetic-anchor overpromotion or replace it with a "
                "portable atom-anchor contract before any guarded 100k rerun."
            ),
        },
        "claim_boundary": {
            "labels_used_for_review_only": True,
            "labels_used_for_scoring": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "claim_promotion_allowed": False,
        },
    }
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    shadow = summary["shadow_score_summary"]
    base = summary["base_score_summary"]
    lines = [
        "# GPCR Cationic Weakbase Frozen Shadow Replay Review",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- input_rows: `{summary['input_rows']}`",
        f"- expected_complete_rows: `{summary['expected_complete_rows']}`",
        f"- active_score_locked_to_base: `{str(summary['active_score_locked_to_base']).lower()}`",
        f"- base_top20_positive_count: `{base['top20_positive_count']}`",
        f"- shadow_top20_positive_count: `{shadow['top20_positive_count']}`",
        "- claim_promotion_allowed: `false`",
        "- scorer_apply_allowed: `false`",
        "",
        "## Positive Ranks",
        "",
        f"- base: `{base['positive_ranks']}`",
        f"- shadow: `{shadow['positive_ranks']}`",
        "",
        "## Blockers",
        "",
    ]
    if summary["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Required Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review v11 frozen weakbase shadow replay with labels used only for evaluation.")
    parser.add_argument("--input-scores-csv", default=DEFAULT_INPUT_SCORES_CSV)
    parser.add_argument("--input-summary-json", default=DEFAULT_INPUT_SUMMARY_JSON)
    parser.add_argument("--label-csv", default=DEFAULT_LABEL_CSV)
    parser.add_argument("--base-score-col", default="base_score")
    parser.add_argument("--shadow-score-col", default="binding_score_composite_v7_residual_shadow")
    parser.add_argument("--expected-complete-rows", type=int, default=30000)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_review(
        input_scores_csv=args.input_scores_csv,
        input_summary_json=args.input_summary_json,
        label_csv=args.label_csv,
        base_score_col=args.base_score_col,
        shadow_score_col=args.shadow_score_col,
        expected_complete_rows=int(args.expected_complete_rows),
    )
    _write_json(_resolve(args.out_json), payload)
    _write_markdown(_resolve(args.out_md), payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
