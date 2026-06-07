#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_SOURCE_JSON = "runs/wetlab_broad_screen_bulk_results_source_current.json"
DEFAULT_PROGRESS_JSON = "runs/wetlab_broad_screen_progress_current.json"
DEFAULT_RERANK_JSON = "runs/wetlab_broad_screen_target_rerank_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_stability_score_current.md"


def _is_bootstrap(row: dict[str, Any]) -> bool:
    return str(row.get("seed_status", "")).strip().lower().startswith("bootstrap_")


def _queue_targets(queue_payload: dict[str, Any] | None) -> tuple[list[str], dict[str, int]]:
    ordered: list[str] = []
    counts: dict[str, int] = {}
    for row in ((queue_payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        if target_id not in counts:
            ordered.append(target_id)
            counts[target_id] = 0
        counts[target_id] += 1
    return ordered, counts


def _source_rows_by_target(source_payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in ((source_payload or {}).get("rows", []) or []):
        row = dict(raw)
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(row)
    for target_id, rows in grouped.items():
        grouped[target_id] = sorted(
            rows,
            key=lambda row: (
                int(row.get("bulk_rank", 10**9) or 10**9),
                -float(row.get("bulk_score", 0.0) or 0.0),
                str(row.get("compound_name", "")).strip().lower(),
            ),
        )
    return grouped


def _completed_shards(progress_payload: dict[str, Any] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in ((progress_payload or {}).get("rows", []) or []):
        if str(row.get("queue_status", "")).strip() != "result_ready":
            continue
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        counts[target_id] = counts.get(target_id, 0) + 1
    return counts


def _rerank_by_target(rerank_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in ((rerank_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }


def _margin_fraction(actual_top3: list[dict[str, Any]]) -> float:
    scores = [float(row.get("bulk_score", 0.0) or 0.0) for row in actual_top3[:3]]
    if len(scores) < 2:
        return 0.0
    spread = max(scores) - min(scores)
    return max(0.0, min(spread / 10.0, 1.0))


def _stability_band(score: float, rerank_status: str) -> str:
    if score >= 85.0 and rerank_status == "full_bulk_top3_ready":
        return "stable_high_confidence"
    if score >= 70.0 and rerank_status == "full_bulk_top3_ready":
        return "stable_provisional"
    if score >= 50.0:
        return "emerging"
    if score > 0.0:
        return "early_signal"
    return "no_actual_signal"


def build_payload(
    queue_payload: dict[str, Any] | None = None,
    source_payload: dict[str, Any] | None = None,
    progress_payload: dict[str, Any] | None = None,
    rerank_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ordered_targets, target_total_shards = _queue_targets(queue_payload)
    source_rows = _source_rows_by_target(source_payload)
    completed_shard_counts = _completed_shards(progress_payload)
    rerank_rows = _rerank_by_target(rerank_payload)

    all_targets = ordered_targets[:]
    for target_id in sorted(set(source_rows) | set(rerank_rows)):
        if target_id not in all_targets:
            all_targets.append(target_id)

    rows: list[dict[str, Any]] = []
    stable_high_confidence_target_count = 0
    stable_provisional_target_count = 0
    highest_score = -1.0
    highest_target = ""

    for target_id in all_targets:
        ranked = source_rows.get(target_id, [])
        top3 = ranked[:3]
        actual_top3 = [row for row in top3 if not _is_bootstrap(row)]
        actual_top3_count = len(actual_top3)
        bootstrap_top3_count = max(0, len(top3) - actual_top3_count)
        total_shards = target_total_shards.get(target_id, 0)
        completed_shards = completed_shard_counts.get(target_id, 0)
        completed_fraction = min(completed_shards / total_shards, 1.0) if total_shards else 0.0
        actual_fraction = actual_top3_count / 3.0
        nonbootstrap_fraction = 1.0 - min(bootstrap_top3_count / 3.0, 1.0)
        unique_actual_top3_shards = len({str(row.get("shard_id", "")).strip() for row in actual_top3 if str(row.get("shard_id", "")).strip()})
        shard_diversity_fraction = unique_actual_top3_shards / 3.0
        margin_fraction = _margin_fraction(actual_top3)
        rerank_status = str(rerank_rows.get(target_id, {}).get("rerank_status", "bootstrap_only")).strip() or "bootstrap_only"

        stability_score = round(
            100.0
            * (
                0.35 * actual_fraction
                + 0.25 * completed_fraction
                + 0.15 * nonbootstrap_fraction
                + 0.15 * shard_diversity_fraction
                + 0.10 * margin_fraction
            ),
            1,
        )
        band = _stability_band(stability_score, rerank_status)
        if band == "stable_high_confidence":
            stable_high_confidence_target_count += 1
        elif band == "stable_provisional":
            stable_provisional_target_count += 1
        if stability_score > highest_score:
            highest_score = stability_score
            highest_target = target_id

        rows.append(
            {
                "target_id": target_id,
                "total_shard_count": total_shards,
                "completed_shard_count": completed_shards,
                "actual_top3_count": actual_top3_count,
                "bootstrap_top3_count": bootstrap_top3_count,
                "unique_actual_top3_shard_count": unique_actual_top3_shards,
                "rerank_status": rerank_status,
                "completed_fraction": round(completed_fraction, 3),
                "actual_fraction": round(actual_fraction, 3),
                "shard_diversity_fraction": round(shard_diversity_fraction, 3),
                "score_margin_fraction": round(margin_fraction, 3),
                "stability_score": stability_score,
                "stability_band": band,
                "stability_method": "proxy_from_completed_shards_actual_top3_diversity_and_margin",
            }
        )

    return {
        "summary": {
            "status": "wetlab_broad_screen_stability_score_ready",
            "target_count": len(rows),
            "stable_high_confidence_target_count": stable_high_confidence_target_count,
            "stable_provisional_target_count": stable_provisional_target_count,
            "highest_stability_target_id": highest_target,
            "highest_stability_score": max(highest_score, 0.0),
            "score_method": "proxy_until_per_shard_topk_history_exists",
            "next_required_step": "Keep completing shards and merging actual rows; use this stability score with rerank status before treating bulk top-3 packets as steady rather than merely available.",
        },
        "structured": {
            "queue_artifact": "runs/wetlab_broad_screen_queue_current.md",
            "progress_artifact": "runs/wetlab_broad_screen_progress_current.md",
            "source_artifact": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "rerank_artifact": "runs/wetlab_broad_screen_target_rerank_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build target-level stability scores for the broad-screen repurposing rerank.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--rerank-json", default=DEFAULT_RERANK_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Stability Score",
        build_payload(
            queue_payload=maybe_load_json(args.queue_json),
            source_payload=maybe_load_json(args.source_json),
            progress_payload=maybe_load_json(args.progress_json),
            rerank_payload=maybe_load_json(args.rerank_json),
        ),
    )
