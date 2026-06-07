#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_SCORES_CSV = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_scores_current.csv"
DEFAULT_INPUT_SUMMARY_JSON = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_review_current.json"
DEFAULT_OUT_MD = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_review_current.md"
DEFAULT_SHADOW_SCORE_COL = "binding_score_composite_v7_residual_shadow"
DEFAULT_POSITIVE_LIGAND_ID = "CHEMBL301265"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"scores CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError(f"scores CSV is empty: {path}")
    return rows


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def _is_positive(row: dict[str, str], positive_ligand_id: str) -> bool:
    if str(row.get("ligand_id", "")).strip() == positive_ligand_id:
        return True
    for key in ("is_binder", "label", "is_positive"):
        value = str(row.get(key, "")).strip().lower()
        if value in {"1", "true", "yes", "binder", "positive"}:
            return True
    return False


def build_review(
    *,
    input_scores_csv: str | Path = DEFAULT_INPUT_SCORES_CSV,
    input_summary_json: str | Path = DEFAULT_INPUT_SUMMARY_JSON,
    shadow_score_col: str = DEFAULT_SHADOW_SCORE_COL,
    positive_ligand_id: str = DEFAULT_POSITIVE_LIGAND_ID,
) -> dict[str, Any]:
    scores_path = _resolve(input_scores_csv)
    summary_path = _resolve(input_summary_json)
    rows = _read_rows(scores_path)
    if shadow_score_col not in rows[0]:
        raise ValueError(f"shadow score column not found: {shadow_score_col}")
    replay_summary: dict[str, Any] = {}
    if summary_path.exists():
        replay_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    ranked = sorted(rows, key=lambda row: _safe_float(row.get(shadow_score_col), default=1.0e9))
    positive_ids = {str(row.get("ligand_id", "")).strip() for row in rows if _is_positive(row, positive_ligand_id)}
    positive_ranks = [
        index
        for index, row in enumerate(ranked, start=1)
        if str(row.get("ligand_id", "")).strip() in positive_ids
    ]
    best_positive_rank = min(positive_ranks) if positive_ranks else None
    decoys_above = (best_positive_rank - 1) if best_positive_rank is not None else None
    top_row = ranked[0]
    summary = replay_summary.get("summary", {}) if isinstance(replay_summary.get("summary", {}), dict) else {}
    active_locked = bool(summary.get("active_score_locked_to_base", False))
    status = "selected_slice_shadow_green_claim_locked"
    blockers: list[str] = []
    if summary.get("status") != "ready_for_evaluation":
        blockers.append("replay_status_not_ready_for_evaluation")
    if not active_locked:
        blockers.append("active_score_not_locked_to_base")
    if best_positive_rank != 1:
        blockers.append("selected_slice_positive_not_top_ranked")
    if blockers:
        status = "blocked_internal_review"

    payload = {
        "packet_type": "gpcr_cationic_pose_distortion_shadow_replay_review",
        "summary": {
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": status,
            "input_scores_csv": str(scores_path),
            "input_summary_json": str(summary_path),
            "input_rows": len(rows),
            "shadow_score_col": shadow_score_col,
            "positive_ligand_id": positive_ligand_id,
            "positive_count": len(positive_ids),
            "selected_slice_positive_rank": best_positive_rank,
            "selected_slice_decoys_above_positive_count": decoys_above,
            "selected_slice_top_ligand_id": str(top_row.get("ligand_id", "")),
            "selected_slice_top_shadow_score": _safe_float(top_row.get(shadow_score_col)),
            "active_score_locked_to_base": active_locked,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "blockers": blockers,
            "next_required_step": (
                "Build equivalent label-free cationic-center and pose-distortion feature caches for frozen "
                "non-ADRB2 rows before any guarded 100k rerun or claim promotion."
            ),
        },
        "claim_boundary": {
            "selected_slice_green_is_not_claim_evidence": True,
            "full_100k_guarded_rerun_required": True,
            "family_held_out_scorecard_required": True,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Cationic Pose-Distortion Shadow Replay Review",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- input_rows: `{summary['input_rows']}`",
        f"- positive_ligand_id: `{summary['positive_ligand_id']}`",
        f"- selected_slice_positive_rank: `{summary['selected_slice_positive_rank']}`",
        f"- selected_slice_decoys_above_positive_count: `{summary['selected_slice_decoys_above_positive_count']}`",
        f"- active_score_locked_to_base: `{str(summary['active_score_locked_to_base']).lower()}`",
        "",
        "## Claim Boundary",
        "",
        "- claim_promotion_allowed: `false`",
        "- scorer_apply_allowed: `false`",
        "- router/platform/broad GPCR claim: `false`",
        "- selected-slice green is not enough for commercial GPCR/router claim.",
        "",
        "## Next Required Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    if summary["blockers"]:
        lines.extend(["## Blockers", ""])
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review the v10 DRD2 cationic pose-distortion shadow replay.")
    parser.add_argument("--input-scores-csv", default=DEFAULT_INPUT_SCORES_CSV)
    parser.add_argument("--input-summary-json", default=DEFAULT_INPUT_SUMMARY_JSON)
    parser.add_argument("--shadow-score-col", default=DEFAULT_SHADOW_SCORE_COL)
    parser.add_argument("--positive-ligand-id", default=DEFAULT_POSITIVE_LIGAND_ID)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_review(
        input_scores_csv=args.input_scores_csv,
        input_summary_json=args.input_summary_json,
        shadow_score_col=args.shadow_score_col,
        positive_ligand_id=args.positive_ligand_id,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    _write_json(out_json, payload)
    _write_markdown(out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
