#!/usr/bin/env python3
"""Read-only R9 bootstrap recovery queue for public-benchmark statistical support."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    _bootstrap_spearman_interval,
    _spearman_values,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATE_FILL_JSON = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.json"
)
DEFAULT_EXISTING_MATERIALIZATION_CSV = "runs/refine_tier_public_benchmark_metric_source_materialization_current.csv"
DEFAULT_GAP_AUDIT_JSON = "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json"
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_recovery_queue_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_bootstrap_recovery_queue_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_recovery_queue_current.md"

MATERIAL_P05_DELTA = 0.05
RANK_ERROR_REVIEW_THRESHOLD = 8

CLAIM_BOUNDARY = (
    "R9 bootstrap recovery queue only re-reads existing materialized and candidate-fill public-benchmark "
    "pairs to rank review targets that most affect bootstrap Spearman p05. It does not compute new metric "
    "values, write metric payload JSON, approve receipts, promote canonical intake, change production "
    "scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, str]], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)], True


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any) -> float | None:
    try:
        out = float(_text(value))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.12g}"


def _rank_map(values: list[float]) -> list[int]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0] * len(values)
    for rank, index in enumerate(order, start=1):
        ranks[index] = rank
    return ranks


def _existing_pairs(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in rows:
        if _text(row.get("metric_materialization_status")) not in {"", "pass"}:
            continue
        proxy = _float(row.get("deltaG_mm_gbsa_kcal_mol"))
        reference = _float(row.get("deltaG_experimental_kcal_mol"))
        if proxy is None or reference is None:
            continue
        pairs.append(
            {
                "source_class": "existing_materialized",
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": _text(row.get("target_id")),
                "pose_id": _text(row.get("pose_id")),
                "split": _text(row.get("split")) or "unknown",
                "proxy": float(proxy),
                "reference": float(reference),
                "dockq": _text(row.get("dockq")),
                "lddt_pli": _text(row.get("lddt_pli")),
            }
        )
    return pairs


def _candidate_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in rows:
        if _text(row.get("candidate_status")) != "pass":
            continue
        proxy = _float(row.get("deltaG_candidate_kcal_mol"))
        reference = _float(row.get("deltaG_experimental_kcal_mol"))
        if proxy is None or reference is None:
            continue
        pairs.append(
            {
                "source_class": "candidate_fill_preview",
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": _text(row.get("target_id")),
                "pose_id": _text(row.get("pose_id")),
                "split": _text(row.get("split")) or "unknown",
                "proxy": float(proxy),
                "reference": float(reference),
                "dockq": _text(row.get("dockq")),
                "lddt_pli": _text(row.get("lddt_pli")),
            }
        )
    return pairs


def _bootstrap_low(pairs: list[dict[str, Any]], *, iterations: int, seed: int) -> dict[str, Any]:
    return _bootstrap_spearman_interval(pairs, iterations=iterations, seed=seed)


def _review_class(delta_p05: float | None, rank_abs_error: int, split: str) -> str:
    delta = float(delta_p05 or 0.0)
    if delta >= MATERIAL_P05_DELTA:
        return "bootstrap_p05_fragility_driver"
    if rank_abs_error >= RANK_ERROR_REVIEW_THRESHOLD:
        return "rank_order_conflict_review"
    if split == "holdout" and delta > 0.0:
        return "holdout_bootstrap_sensitivity_review"
    if delta < 0.0:
        return "supportive_pair_monitor"
    return "neutral_pair_monitor"


def _next_action(review_class: str, source_class: str) -> str:
    if review_class == "bootstrap_p05_fragility_driver":
        return (
            "Review this pair's internal_deltaG value, metric method, input artifact hashes, pose assignment, "
            "and experimental deltaG mapping before relying on it for claim-grade bootstrap support."
        )
    if review_class == "rank_order_conflict_review":
        return "Review rank-order conflict against public experimental deltaG before rerunning bootstrap gates."
    if review_class == "holdout_bootstrap_sensitivity_review":
        return "Review holdout evidence quality and split assignment because this row changes bootstrap tail risk."
    if source_class == "candidate_fill_preview":
        return "Keep as candidate-only evidence until operator-reviewed metric source payload receipt exists."
    return "Keep as monitored materialized evidence while higher-impact p05 drivers are reviewed."


def build_refine_tier_public_benchmark_bootstrap_recovery_queue(
    *,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    gap_audit_json: str | Path = DEFAULT_GAP_AUDIT_JSON,
    root: str | Path = ROOT,
    iterations: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    existing_rows, existing_present = _read_csv(existing_materialization_csv, root=root_path)
    gap_payload, gap_present = _read_json(gap_audit_json, root=root_path)
    candidate_summary = _summary(candidate_payload)
    gap_summary = _summary(gap_payload)
    bootstrap_iterations = int(iterations or candidate_summary.get("bootstrap_iteration_count") or BOOTSTRAP_ITERATIONS)
    bootstrap_seed = int(seed or candidate_summary.get("bootstrap_seed") or BOOTSTRAP_SEED)

    pairs = [*_existing_pairs(existing_rows), *_candidate_pairs(_rows(candidate_payload, "candidate_pairs"))]
    full_spearman = _spearman_values([pair["proxy"] for pair in pairs], [pair["reference"] for pair in pairs])
    full_bootstrap = _bootstrap_low(pairs, iterations=bootstrap_iterations, seed=bootstrap_seed)
    full_p05 = _float(full_bootstrap.get("free_energy_spearman_bootstrap_p05"))
    proxy_ranks = _rank_map([pair["proxy"] for pair in pairs]) if pairs else []
    reference_ranks = _rank_map([pair["reference"] for pair in pairs]) if pairs else []

    queue_rows: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs):
        reduced = [candidate for row_index, candidate in enumerate(pairs) if row_index != index]
        loo_spearman = _spearman_values(
            [candidate["proxy"] for candidate in reduced],
            [candidate["reference"] for candidate in reduced],
        )
        loo_bootstrap = _bootstrap_low(reduced, iterations=bootstrap_iterations, seed=bootstrap_seed)
        loo_p05 = _float(loo_bootstrap.get("free_energy_spearman_bootstrap_p05"))
        delta_p05 = None if full_p05 is None or loo_p05 is None else float(loo_p05 - full_p05)
        proxy_rank = proxy_ranks[index]
        reference_rank = reference_ranks[index]
        rank_abs_error = abs(proxy_rank - reference_rank)
        review_class = _review_class(delta_p05, rank_abs_error, _text(pair.get("split")))
        queue_rows.append(
            {
                "recovery_priority_rank": 0,
                "source_class": pair["source_class"],
                "work_order_id": pair["work_order_id"],
                "target_id": pair["target_id"],
                "pose_id": pair["pose_id"],
                "split": pair["split"],
                "deltaG_proxy_kcal_mol": _format_float(pair["proxy"]),
                "deltaG_experimental_kcal_mol": _format_float(pair["reference"]),
                "dockq": _text(pair.get("dockq")),
                "lddt_pli": _text(pair.get("lddt_pli")),
                "proxy_rank": proxy_rank,
                "reference_rank": reference_rank,
                "rank_abs_error": rank_abs_error,
                "full_spearman": _format_float(full_spearman),
                "leave_one_out_spearman": _format_float(loo_spearman),
                "full_bootstrap_p05": _format_float(full_p05),
                "leave_one_out_bootstrap_p05": _format_float(loo_p05),
                "bootstrap_p05_delta_if_removed": _format_float(delta_p05),
                "review_class": review_class,
                "next_science_step": _next_action(review_class, pair["source_class"]),
                "payload_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
        )

    queue_rows = sorted(
        queue_rows,
        key=lambda row: (
            _float(row.get("bootstrap_p05_delta_if_removed")) or -999.0,
            int(row.get("rank_abs_error") or 0),
            row.get("source_class") == "candidate_fill_preview",
        ),
        reverse=True,
    )
    for rank, row in enumerate(queue_rows, start=1):
        row["recovery_priority_rank"] = rank

    top_row = queue_rows[0] if queue_rows else {}
    p05_delta_values = [_float(row.get("bootstrap_p05_delta_if_removed")) for row in queue_rows]
    positive_delta_values = [value for value in p05_delta_values if value is not None and value > 0.0]
    material_delta_values = [value for value in p05_delta_values if value is not None and value >= MATERIAL_P05_DELTA]
    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_recovery_queue",
        "status": (
            "refine_tier_public_benchmark_bootstrap_recovery_queue_ready"
            if candidate_present and existing_present and queue_rows
            else "blocked_refine_tier_public_benchmark_bootstrap_recovery_queue"
        ),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_json_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "existing_materialization_csv_present": existing_present,
        "gap_audit_json": _display(gap_audit_json, root=root_path),
        "gap_audit_json_present": gap_present,
        "gap_audit_top_statistical_gap_id": gap_summary.get("top_statistical_gap_id", ""),
        "queue_row_count": len(queue_rows),
        "existing_materialized_pair_count": sum(1 for row in queue_rows if row["source_class"] == "existing_materialized"),
        "candidate_fill_pair_count": sum(1 for row in queue_rows if row["source_class"] == "candidate_fill_preview"),
        "full_combined_spearman": full_spearman,
        "full_bootstrap_p05": full_p05,
        "full_bootstrap_p50": _float(full_bootstrap.get("free_energy_spearman_bootstrap_p50")),
        "full_bootstrap_p95": _float(full_bootstrap.get("free_energy_spearman_bootstrap_p95")),
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "bootstrap_p05_deficit": (
            max(0.0, MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - full_p05) if full_p05 is not None else None
        ),
        "leave_one_out_improves_p05_count": len(positive_delta_values),
        "material_bootstrap_p05_driver_count": len(material_delta_values),
        "rank_order_conflict_review_count": sum(
            1 for row in queue_rows if row["review_class"] == "rank_order_conflict_review"
        ),
        "top_recovery_target_id": top_row.get("target_id", ""),
        "top_recovery_pose_id": top_row.get("pose_id", ""),
        "top_recovery_source_class": top_row.get("source_class", ""),
        "top_recovery_review_class": top_row.get("review_class", ""),
        "top_recovery_bootstrap_p05_delta_if_removed": _float(top_row.get("bootstrap_p05_delta_if_removed")),
        "max_rank_abs_error": max([int(row.get("rank_abs_error") or 0) for row in queue_rows], default=0),
        "bootstrap_iteration_count": bootstrap_iterations,
        "bootstrap_seed": bootstrap_seed,
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review the highest positive leave-one-out p05 drivers and rank-order conflicts before writing "
            "reviewed metric payloads or rerunning claim-grade bootstrap gates."
        ),
    }
    return {"summary": summary, "recovery_rows": queue_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Recovery Queue",
        "",
        f"- status: `{s['status']}`",
        f"- queue_row_count: `{s['queue_row_count']}`",
        f"- existing_materialized_pair_count: `{s['existing_materialized_pair_count']}`",
        f"- candidate_fill_pair_count: `{s['candidate_fill_pair_count']}`",
        f"- full_combined_spearman: `{s['full_combined_spearman']}`",
        f"- full_bootstrap_p05: `{s['full_bootstrap_p05']}`",
        f"- bootstrap_p05_deficit: `{s['bootstrap_p05_deficit']}`",
        f"- leave_one_out_improves_p05_count: `{s['leave_one_out_improves_p05_count']}`",
        f"- material_bootstrap_p05_driver_count: `{s['material_bootstrap_p05_driver_count']}`",
        f"- top_recovery_target_id: `{s['top_recovery_target_id']}`",
        f"- top_recovery_pose_id: `{s['top_recovery_pose_id']}`",
        f"- top_recovery_review_class: `{s['top_recovery_review_class']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Top Recovery Rows",
        "",
        "| rank | source | target | pose | split | proxy | experimental | rank err | p05 delta if removed | class | next |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["recovery_rows"][:12]:
        lines.append(
            f"| `{row['recovery_priority_rank']}` | `{row['source_class']}` | `{row['target_id']}` | "
            f"`{row['pose_id']}` | `{row['split']}` | `{row['deltaG_proxy_kcal_mol']}` | "
            f"`{row['deltaG_experimental_kcal_mol']}` | `{row['rank_abs_error']}` | "
            f"`{row['bootstrap_p05_delta_if_removed']}` | `{row['review_class']}` | "
            f"{row['next_science_step']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 bootstrap recovery queue.")
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--gap-audit-json", default=DEFAULT_GAP_AUDIT_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_recovery_queue(
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        gap_audit_json=args.gap_audit_json,
        root=root,
        iterations=args.iterations,
        seed=args.seed,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["recovery_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
