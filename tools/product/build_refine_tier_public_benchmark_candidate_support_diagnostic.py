#!/usr/bin/env python3
"""Diagnose R9 candidate-fill statistical support without promoting claims."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    _bootstrap_spearman_interval,
    _spearman_values,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATE_FILL_JSON = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.json"
)
DEFAULT_EXISTING_MATERIALIZATION_CSV = "runs/refine_tier_public_benchmark_metric_source_materialization_current.csv"
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_candidate_support_diagnostic_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_candidate_support_leave_one_out_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_candidate_support_diagnostic_current.md"

CLAIM_BOUNDARY = (
    "R9 candidate support diagnostic only; it reads the local candidate-fill preview and existing "
    "materialization rows to identify rank sensitivity and outlier candidates. It does not drop rows, "
    "rewrite metric values, write reviewed payloads, approve receipts, promote canonical intake, run "
    "docking/MD, download, upload, email, delete, commit, push, or mutate external state."
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
    return (payload if isinstance(payload, dict) else {}), True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        out = float(_text(value))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _format_float(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{float(value):.12g}"


def _existing_pairs(path_like: str | Path, *, root: Path) -> list[dict[str, Any]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return []
    pairs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            proxy = _float(row.get("deltaG_mm_gbsa_kcal_mol"))
            reference = _float(row.get("deltaG_experimental_kcal_mol"))
            if proxy is None or reference is None:
                continue
            pairs.append(
                {
                    "source": "existing_materialized",
                    "work_order_id": _text(row.get("work_order_id")),
                    "target_id": _text(row.get("target_id")),
                    "pose_id": _text(row.get("pose_id")),
                    "split": _text(row.get("split")) or "unknown",
                    "proxy": float(proxy),
                    "reference": float(reference),
                }
            )
    return pairs


def _candidate_pairs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("candidate_pairs", [])
    if not isinstance(rows, list):
        return []
    pairs: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("candidate_status") != "pass":
            continue
        proxy = _float(row.get("deltaG_candidate_kcal_mol"))
        reference = _float(row.get("deltaG_experimental_kcal_mol"))
        if proxy is None or reference is None:
            continue
        pairs.append(
            {
                "source": "candidate_fill_preview",
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": _text(row.get("target_id")),
                "pose_id": _text(row.get("pose_id")),
                "split": _text(row.get("split")) or "unknown",
                "proxy": float(proxy),
                "reference": float(reference),
            }
        )
    return pairs


def _rank_residual_rows(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proxy_order = sorted(range(len(pairs)), key=lambda index: float(pairs[index]["proxy"]))
    reference_order = sorted(range(len(pairs)), key=lambda index: float(pairs[index]["reference"]))
    proxy_rank = {index: rank + 1 for rank, index in enumerate(proxy_order)}
    reference_rank = {index: rank + 1 for rank, index in enumerate(reference_order)}
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs):
        rows.append(
            {
                "source": pair["source"],
                "work_order_id": pair["work_order_id"],
                "target_id": pair["target_id"],
                "pose_id": pair["pose_id"],
                "split": pair["split"],
                "proxy": _format_float(pair["proxy"]),
                "reference": _format_float(pair["reference"]),
                "proxy_rank": proxy_rank[index],
                "reference_rank": reference_rank[index],
                "rank_abs_error": abs(proxy_rank[index] - reference_rank[index]),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["rank_abs_error"]), str(row["target_id"])))


def _leave_one_out_rows(pairs: list[dict[str, Any]], *, baseline_p05: float | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs):
        subset = [candidate for subset_index, candidate in enumerate(pairs) if subset_index != index]
        spearman = _spearman_values(
            [float(candidate["proxy"]) for candidate in subset],
            [float(candidate["reference"]) for candidate in subset],
        )
        bootstrap = _bootstrap_spearman_interval(subset)
        p05 = _float(bootstrap.get("free_energy_spearman_bootstrap_p05"))
        rows.append(
            {
                "removed_source": pair["source"],
                "removed_work_order_id": pair["work_order_id"],
                "removed_target_id": pair["target_id"],
                "removed_pose_id": pair["pose_id"],
                "removed_split": pair["split"],
                "removed_proxy": _format_float(pair["proxy"]),
                "removed_reference": _format_float(pair["reference"]),
                "spearman_without_pair": _format_float(spearman),
                "bootstrap_p05_without_pair": _format_float(p05),
                "bootstrap_p05_delta": _format_float(
                    None if baseline_p05 is None or p05 is None else p05 - baseline_p05
                ),
                "claim_grade_p05_without_pair": bool(
                    p05 is not None and p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
                ),
            }
        )
    return sorted(rows, key=lambda row: (float(row["bootstrap_p05_delta"] or "-inf"), row["removed_target_id"]), reverse=True)


def build_refine_tier_public_benchmark_candidate_support_diagnostic(
    *,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    existing = _existing_pairs(existing_materialization_csv, root=root_path)
    candidates = _candidate_pairs(candidate_payload)
    pairs = [*existing, *candidates]
    spearman = _spearman_values([float(pair["proxy"]) for pair in pairs], [float(pair["reference"]) for pair in pairs])
    bootstrap = _bootstrap_spearman_interval(pairs)
    p05 = _float(bootstrap.get("free_energy_spearman_bootstrap_p05"))
    rank_rows = _rank_residual_rows(pairs) if pairs else []
    leave_one_out_rows = _leave_one_out_rows(pairs, baseline_p05=p05) if pairs else []
    best_removal = leave_one_out_rows[0] if leave_one_out_rows else {}
    worst_rank = rank_rows[0] if rank_rows else {}
    best_removal_p05 = _float(best_removal.get("bootstrap_p05_without_pair"))
    summary = {
        "packet_type": "refine_tier_public_benchmark_candidate_support_diagnostic",
        "status": (
            "refine_tier_public_benchmark_candidate_support_diagnostic_ready"
            if candidate_present and pairs
            else "blocked_refine_tier_public_benchmark_candidate_support_diagnostic"
        ),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "existing_pair_count": len(existing),
        "candidate_pair_count": len(candidates),
        "combined_pair_count": len(pairs),
        "combined_free_energy_spearman": spearman,
        **bootstrap,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "claim_grade_p05_ready": bool(p05 is not None and p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW),
        "best_single_pair_removal_target_id": best_removal.get("removed_target_id", ""),
        "best_single_pair_removal_work_order_id": best_removal.get("removed_work_order_id", ""),
        "best_single_pair_removal_bootstrap_p05": best_removal_p05,
        "best_single_pair_removal_claim_grade_p05_ready": bool(
            best_removal_p05 is not None
            and best_removal_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "top_rank_residual_target_id": worst_rank.get("target_id", ""),
        "top_rank_residual_work_order_id": worst_rank.get("work_order_id", ""),
        "top_rank_residual_abs_error": int(worst_rank.get("rank_abs_error") or 0),
        "diagnostic_policy": (
            "leave_one_out_is_sensitivity_only_do_not_drop_pairs_without_independent_scientific_review"
        ),
        "next_required_step": (
            "Do not promote or cherry-pick rows from this diagnostic. Prioritize score/model improvements "
            "for the largest rank-residual pairs, then rerun candidate fill and require bootstrap p05 >= 0.5 "
            "plus operator-reviewed metric payload receipts."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "external_state_mutated": False,
    }
    return {
        "summary": summary,
        "top_leave_one_out_rows": leave_one_out_rows[:25],
        "top_rank_residual_rows": rank_rows[:25],
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Candidate Support Diagnostic",
        "",
        f"- status: `{s['status']}`",
        f"- combined_pair_count: `{s['combined_pair_count']}`",
        f"- combined_spearman: `{s['combined_free_energy_spearman']}`",
        f"- bootstrap_p05/p50/p95: `{s['free_energy_spearman_bootstrap_p05']}/{s['free_energy_spearman_bootstrap_p50']}/{s['free_energy_spearman_bootstrap_p95']}`",
        f"- best_single_pair_removal: `{s['best_single_pair_removal_target_id']}` p05=`{s['best_single_pair_removal_bootstrap_p05']}`",
        f"- best_single_pair_removal_claim_grade_p05_ready: `{s['best_single_pair_removal_claim_grade_p05_ready']}`",
        f"- top_rank_residual: `{s['top_rank_residual_target_id']}` rank_abs_error=`{s['top_rank_residual_abs_error']}`",
        f"- diagnostic_policy: `{s['diagnostic_policy']}`",
        "",
        "## Top Leave-One-Out Rows",
        "",
        "| target | pose | source | split | p05 without pair | p05 delta | claim-grade p05 |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["top_leave_one_out_rows"][:10]:
        lines.append(
            f"| `{row['removed_target_id']}` | `{row['removed_pose_id']}` | `{row['removed_source']}` | "
            f"`{row['removed_split']}` | `{row['bootstrap_p05_without_pair']}` | "
            f"`{row['bootstrap_p05_delta']}` | `{row['claim_grade_p05_without_pair']}` |"
        )
    lines.extend(["", "## Top Rank Residual Rows", "", "| target | pose | source | proxy rank | reference rank | rank abs error |", "| --- | --- | --- | ---: | ---: | ---: |"])
    for row in payload["top_rank_residual_rows"][:10]:
        lines.append(
            f"| `{row['target_id']}` | `{row['pose_id']}` | `{row['source']}` | "
            f"`{row['proxy_rank']}` | `{row['reference_rank']}` | `{row['rank_abs_error']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R9 candidate-fill statistical support diagnostics.")
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_candidate_support_diagnostic(
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["top_leave_one_out_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
