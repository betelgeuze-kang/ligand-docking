#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROWS_CSV = "runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_hard_decoy_penalty_envelope_grid_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_drd2_hard_decoy_penalty_envelope_current.md"
DEFAULT_GRID = "0,1,2,4,6,8,10,12,16,20"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return float(default)
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return out if math.isfinite(out) else float(default)


def _truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "t", "yes", "y"}


def _parse_grid(text: str) -> list[float]:
    values: list[float] = []
    for item in str(text or "").split(","):
        item = item.strip()
        if not item:
            continue
        values.append(float(item))
    return sorted(set(values))


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _score_row(row: dict[str, str], penalty_weight: float, support_weight: float) -> float:
    return (
        _float(row.get("base_score"))
        + float(penalty_weight) * _float(row.get("label_free_penalty_pressure"))
        - float(support_weight) * _float(row.get("label_free_support_pressure"))
    )


def _evaluate(rows: list[dict[str, str]], *, penalty_weight: float, support_weight: float) -> dict[str, Any]:
    scored = []
    for row in rows:
        is_positive = _truthy(row.get("is_positive"))
        score = _score_row(row, penalty_weight, support_weight)
        scored.append(
            {
                "candidate_score": score,
                "ligand_id": _text(row.get("ligand_id")),
                "is_positive": is_positive,
                "slice_label_text": _text(row.get("slice_label_text")),
            }
        )
    scored.sort(key=lambda row: (row["candidate_score"], row["ligand_id"]))
    positive_index = next((idx for idx, row in enumerate(scored) if row["is_positive"]), None)
    positive_rank = int(positive_index + 1) if positive_index is not None else 0
    above = scored[:positive_index] if positive_index is not None else scored
    def count_label(label: str) -> int:
        return sum(1 for row in above if label in row.get("slice_label_text", "").split(","))

    positive_score = scored[positive_index]["candidate_score"] if positive_index is not None else None
    return {
        "penalty_weight": float(penalty_weight),
        "support_weight": float(support_weight),
        "max_abs_weight": float(max(abs(penalty_weight), abs(support_weight))),
        "positive_rank": positive_rank,
        "decoys_above_positive_count": int(len(above)),
        "invalid_close_overanchor_above_positive_count": count_label("invalid_close_overanchor_no_basic"),
        "hydrophobic_close_overanchor_above_positive_count": count_label("hydrophobic_close_overanchor"),
        "multipolar_basic_overanchor_above_positive_count": count_label("multipolar_basic_overanchor"),
        "valid_anchor_challenge_above_positive_count": count_label("valid_anchor_challenge"),
        "uncategorized_hard_decoy_above_positive_count": count_label("uncategorized_hard_decoy"),
        "positive_candidate_score": positive_score,
        "top1_ligand_id": scored[0]["ligand_id"] if scored else "",
        "top1_slice_label_text": scored[0]["slice_label_text"] if scored else "",
        "top1_candidate_score": scored[0]["candidate_score"] if scored else None,
    }


def build_envelope(
    *,
    rows_csv: str | Path = DEFAULT_ROWS_CSV,
    grid: str = DEFAULT_GRID,
    topk_threshold: int = 20,
    bounded_weight_ceiling: float = 20.0,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = _read_csv(rows_csv)
    weights = _parse_grid(grid)
    grid_rows = [
        _evaluate(rows, penalty_weight=penalty_weight, support_weight=support_weight)
        for penalty_weight in weights
        for support_weight in weights
    ]
    best = min(
        grid_rows,
        key=lambda row: (
            int(row["positive_rank"] or 10**9),
            int(row["decoys_above_positive_count"]),
            float(row["max_abs_weight"]),
            float(row["penalty_weight"]) + float(row["support_weight"]),
        ),
        default={},
    )
    bounded_candidates = [
        row for row in grid_rows if float(row.get("max_abs_weight", 0.0)) <= float(bounded_weight_ceiling)
    ]
    bounded_best = min(
        bounded_candidates,
        key=lambda row: (
            int(row["positive_rank"] or 10**9),
            int(row["decoys_above_positive_count"]),
            float(row["max_abs_weight"]),
            float(row["penalty_weight"]) + float(row["support_weight"]),
        ),
        default={},
    )
    if not bounded_best:
        status = "blocked_no_weight_grid"
    elif int(bounded_best.get("positive_rank") or 10**9) > int(topk_threshold):
        status = "blocked_penalty_envelope_insufficient"
    elif int(bounded_best.get("valid_anchor_challenge_above_positive_count") or 0) > 0:
        status = "blocked_valid_anchor_challenge_remaining"
    elif int(bounded_best.get("decoys_above_positive_count") or 0) > 0:
        status = "blocked_pairwise_decoys_remaining"
    else:
        status = "slice_pairwise_green_diagnostic_only"
    if status == "slice_pairwise_green_diagnostic_only":
        next_action = "build_claim_locked_cationic_pose_distortion_shadow_replay"
        next_required_step = (
            "The repaired selected DRD2 slice is pairwise-green under the bounded label-free pressure envelope. "
            "Promote only the feature contract, not the claim: add cationic-center geometry and pose-distortion "
            "pressure to a claim-locked shadow scorer, replay on frozen rows, and keep active score/router/platform "
            "claims locked until full guarded evidence clears CI-low/top20."
        )
    else:
        next_action = "add_valid_anchor_discriminator_before_full_100k_replay"
        next_required_step = (
            "The repaired slice should not be promoted from the penalty envelope alone. If valid-anchor challenge "
            "decoys remain above the positive, add a new label-free discriminator such as cationic-center geometry, "
            "aromatic-cage occupancy, pose-preservation RMSD, or local-minimization survival before another full "
            "100k claim review."
        )

    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "rows_csv": str(_resolve(rows_csv)),
        "row_count": len(rows),
        "grid": weights,
        "topk_threshold": int(topk_threshold),
        "bounded_weight_ceiling": float(bounded_weight_ceiling),
        "best_positive_rank": best.get("positive_rank"),
        "best_penalty_weight": best.get("penalty_weight"),
        "best_support_weight": best.get("support_weight"),
        "bounded_best_positive_rank": bounded_best.get("positive_rank"),
        "bounded_best_decoys_above_positive_count": bounded_best.get("decoys_above_positive_count"),
        "bounded_best_valid_anchor_challenge_above_positive_count": bounded_best.get(
            "valid_anchor_challenge_above_positive_count"
        ),
        "bounded_best_penalty_weight": bounded_best.get("penalty_weight"),
        "bounded_best_support_weight": bounded_best.get("support_weight"),
        "bounded_best_top1_slice_label_text": bounded_best.get("top1_slice_label_text"),
        "next_action": next_action,
        "next_required_step": next_required_step,
    }
    payload = {
        "packet_type": "gpcr_drd2_hard_decoy_penalty_envelope",
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "full_100k_claim_review_allowed": False,
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
        },
        "best_grid_row": best,
        "bounded_best_grid_row": bounded_best,
        "grid_rows": grid_rows,
    }
    return payload, grid_rows


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    return "\n".join(
        [
            "# GPCR DRD2 Hard-Decoy Penalty Envelope",
            "",
            f"- status: `{s['status']}`",
            f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
            f"- bounded_weight_ceiling: `{s['bounded_weight_ceiling']}`",
            f"- bounded_best_positive_rank: `{s['bounded_best_positive_rank']}`",
            f"- bounded_best_decoys_above_positive_count: `{s['bounded_best_decoys_above_positive_count']}`",
            f"- bounded_best_valid_anchor_challenge_above_positive_count: `{s['bounded_best_valid_anchor_challenge_above_positive_count']}`",
            f"- bounded_best_penalty_weight: `{s['bounded_best_penalty_weight']}`",
            f"- bounded_best_support_weight: `{s['bounded_best_support_weight']}`",
            f"- bounded_best_top1_slice_label_text: `{s['bounded_best_top1_slice_label_text']}`",
            f"- next_action: `{s['next_action']}`",
            "",
            "## Next Required Step",
            "",
            s["next_required_step"],
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a DRD2 hard-decoy penalty envelope on repaired selected rows.")
    parser.add_argument("--rows-csv", default=DEFAULT_ROWS_CSV)
    parser.add_argument("--grid", default=DEFAULT_GRID)
    parser.add_argument("--topk-threshold", type=int, default=20)
    parser.add_argument("--bounded-weight-ceiling", type=float, default=20.0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, grid_rows = build_envelope(
        rows_csv=args.rows_csv,
        grid=args.grid,
        topk_threshold=int(args.topk_threshold),
        bounded_weight_ceiling=float(args.bounded_weight_ceiling),
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, grid_rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
