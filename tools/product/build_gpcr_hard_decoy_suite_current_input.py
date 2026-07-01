#!/usr/bin/env python3
"""Build the current GPCR hard-decoy suite input CSV from actual artifacts.

This is a read-only extractor. It does not run scoring, generate decoys, or
promote claims. It materializes the aggregate CSV consumed by
build_gpcr_hard_decoy_suite_report.py from the current actual 100k GPCR
independent-repeat artifacts. If the detailed ranking rows are unavailable, it
keeps target-internal separation fields blank so the downstream evaluator
fail-closes instead of inferring a clean decoy separation.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.product import build_gpcr_hard_decoy_suite_report as report

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RANKING_SUMMARY_JSON = (
    "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_ranking_summary_current.json"
)
DEFAULT_HARD_DECOY_SUMMARY_JSON = (
    "runs/external_validation_2026-05-10_coverage_v1_family_balanced100k_r1_"
    "set1_core_blind_gpcr_core_full_hard_decoy_summary.json"
)
DEFAULT_OUT_CSV = "config/gpcr_hard_decoy_suite_current.csv"
DEFAULT_OUT_PROVENANCE_JSON = "runs/gpcr_hard_decoy_suite_current_input_provenance.json"
DEFAULT_PREREGISTERED_REPLAY_JSON = ""

TARGET_MAP = (
    ("DRD2", "CHEMBL217_DRD2_HUMAN"),
    ("HTR2A", "CHEMBL224_HTR2A_HUMAN"),
    ("OPRM1", "CHEMBL233_OPRM1_HUMAN"),
)

INPUT_COLUMNS = [
    *report.REQUIRED_INPUT_COLUMNS,
    *report.OPTIONAL_NUMERIC_COLUMNS,
    report.DECOY_CLASS_COUNTS_COLUMN,
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _top20_hit_rate(summary: dict[str, Any]) -> float | None:
    for key in ("topk_unique", "topk"):
        for item in summary.get(key) or []:
            if int(item.get("k", -1)) == 20:
                return _as_float(item.get("hit_rate"))
    return None


def _ranking_metrics(summary: dict[str, Any]) -> dict[str, float | None]:
    metrics = summary.get("metrics_unique") or summary.get("metrics") or {}
    metrics_ci = summary.get("metrics_ci_unique") or summary.get("metrics_ci") or {}
    return {
        "ranking_pr_auc": _as_float(metrics.get("pr_auc")),
        "ranking_pr_auc_ci_low": _as_float((metrics_ci.get("pr_auc") or {}).get("low")),
        "top20_hit_rate": _top20_hit_rate(summary),
    }


def _hard_decoy_stats(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for item in summary.get("target_hard_decoy_stats") or []:
        target = str(item.get("target") or "").strip()
        if target:
            stats[target] = item
    return stats


def _retained_top_rank_paths(path: Path) -> list[Path]:
    paths: list[Path] = []
    if path.name.endswith("_unique.csv"):
        paths.append(path.with_name(path.name.replace("_unique.csv", "_unique_top_rank_retained_top50_current.csv")))
    if path.name.endswith("_unique_current.csv"):
        paths.append(
            path.with_name(path.name.replace("_unique_current.csv", "_unique_top_rank_retained_top50_current.csv"))
        )
    if path.name.endswith("_ranking_rows.csv"):
        paths.append(
            path.with_name(path.name.replace("_ranking_rows.csv", "_ranking_unique_top_rank_retained_top50_current.csv"))
        )
        paths.append(
            path.with_name(path.name.replace("_ranking_rows.csv", "_ranking_rows_top_rank_retained_top50_current.csv"))
        )
    if path.name.endswith("_ranking_rows_current.csv"):
        paths.append(
            path.with_name(
                path.name.replace("_ranking_rows_current.csv", "_ranking_unique_top_rank_retained_top50_current.csv")
            )
        )
        paths.append(
            path.with_name(
                path.name.replace("_ranking_rows_current.csv", "_ranking_rows_top_rank_retained_top50_current.csv")
            )
        )
    paths.append(path.with_name(path.stem + "_top_rank_retained_top50_current.csv"))
    deduped: list[Path] = []
    for candidate in paths:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _ranking_rows_path(summary: dict[str, Any], override: str) -> tuple[Path | None, str, bool]:
    if override:
        path = _resolve(override)
        return (path, "override_full_rows", True) if path.exists() else (None, "missing", False)
    artifacts = summary.get("artifacts") or {}
    for key in ("unique_csv", "detail_csv"):
        raw = artifacts.get(key)
        if not raw:
            continue
        path = _resolve(raw)
        if path.exists():
            return path, key, True
        for retained in _retained_top_rank_paths(path):
            if retained.exists():
                return retained, f"{key}_retained_top_rank_top50", False
    return None, "missing", False


def _target_separation_from_rows(
    rows_csv: Path,
    *,
    score_col: str,
    lower_better: bool,
    complete_rows: bool,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    with rows_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            target = str(row.get("target") or "").strip()
            score = _as_float(row.get(score_col))
            if not target or score is None:
                continue
            copied = dict(row)
            copied["_score"] = score
            copied["_is_binder"] = _as_bool(row.get("is_binder"))
            copied["_anchor_distance_a"] = _as_float(row.get("mean_min_distance_A"))
            grouped.setdefault(target, []).append(copied)

    separation: dict[str, dict[str, Any]] = {}
    for target, rows in grouped.items():
        ranked = sorted(rows, key=lambda item: item["_score"], reverse=not lower_better)
        retained_positive_count = sum(1 for row in ranked if row["_is_binder"])
        retained_decoy_count = sum(1 for row in ranked if not row["_is_binder"])
        first_positive_rank = None
        first_positive = None
        for index, row in enumerate(ranked, start=1):
            if row["_is_binder"]:
                first_positive_rank = index
                first_positive = row
                break
        top_decoy = next((row for row in ranked if not row["_is_binder"]), None)
        if first_positive_rank is None or first_positive is None:
            if complete_rows:
                separation[target] = {
                    "retained_target_row_count": len(ranked),
                    "retained_positive_count": retained_positive_count,
                    "top_decoy_retained_count": retained_decoy_count,
                }
            else:
                separation[target] = {
                    "decoys_above_positive_count": retained_decoy_count if retained_decoy_count > 0 else "",
                    "positive_target_rank": "",
                    "positive_anchor_distance_a": "",
                    "top_decoy_anchor_distance_a": (
                        None if top_decoy is None else top_decoy["_anchor_distance_a"]
                    ),
                    "retained_target_row_count": len(ranked),
                    "retained_positive_count": retained_positive_count,
                    "top_decoy_retained_count": retained_decoy_count,
                    "rank_evidence_note": "positive_missing_from_retained_top_rank_rows",
                }
            continue
        decoys_above = sum(1 for row in ranked[: first_positive_rank - 1] if not row["_is_binder"])
        separation[target] = {
            "decoys_above_positive_count": decoys_above,
            "positive_target_rank": first_positive_rank,
            "positive_anchor_distance_a": first_positive["_anchor_distance_a"],
            "top_decoy_anchor_distance_a": (
                None if top_decoy is None else top_decoy["_anchor_distance_a"]
            ),
            "retained_target_row_count": len(ranked),
            "retained_positive_count": retained_positive_count,
            "top_decoy_retained_count": retained_decoy_count,
        }
    return separation


def _csv_value(value: Any) -> Any:
    return "" if value is None else value


def _target_metric_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("runner_replay_target_metric_rows")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        target_id = str(item.get("target_id") or "").strip()
        if target_id:
            out[target_id] = item
    return out


def _preregistered_replay_rows(payload: dict[str, Any], source_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metrics = payload.get("runner_replay_target_heldout")
    if not isinstance(metrics, dict):
        raise ValueError("preregistered replay JSON missing runner_replay_target_heldout")
    target_rows = metrics.get("target_rows")
    if not isinstance(target_rows, dict):
        raise ValueError("preregistered replay JSON missing runner_replay_target_heldout.target_rows")
    target_metric_rows = _target_metric_by_id(payload)

    rows: list[dict[str, Any]] = []
    for target_id, _source_target in TARGET_MAP:
        target_separation = target_rows.get(target_id)
        if not isinstance(target_separation, dict):
            target_separation = {}
        target_metrics = target_metric_rows.get(target_id, {})
        row_count = _as_float(target_metrics.get("row_count"))
        positive_count = _as_float(target_metrics.get("positive_count"))
        rows.append(
            {
                "target_id": target_id,
                "positive_count": "" if positive_count is None else int(positive_count),
                "ranking_pr_auc": metrics.get("ranking_pr_auc"),
                "ranking_pr_auc_ci_low": metrics.get("ranking_pr_auc_ci_low"),
                "top20_hit_rate": metrics.get("top20_hit_rate"),
                "decoys_above_positive_count": target_separation.get("decoys_above_positive_count", ""),
                "positive_target_rank": target_separation.get("positive_target_rank", ""),
                "positive_anchor_distance_a": target_separation.get("positive_anchor_distance_a", ""),
                "top_decoy_anchor_distance_a": target_separation.get("top_decoy_anchor_distance_a", ""),
                "retained_target_row_count": "" if row_count is None else int(row_count),
                "retained_positive_count": "" if positive_count is None else int(positive_count),
                "top_decoy_retained_count": (
                    ""
                    if row_count is None or positive_count is None
                    else int(max(0.0, row_count - positive_count))
                ),
                "decoy_class_counts": json.dumps({}),
            }
        )

    provenance = {
        "packet_type": "gpcr_hard_decoy_suite_current_input_provenance",
        "schema_version": "gpcr_hard_decoy_suite_current_input_provenance_v1",
        "status": "gpcr_hard_decoy_suite_current_input_ready",
        "source_mode": "adora2a_preregistered_runner_replay",
        "preregistered_replay_json": str(source_path),
        "preregistered_replay_status": payload.get("status", ""),
        "pre_registered_runner_replay_complete": payload.get("pre_registered_runner_replay_complete") is True,
        "runner_replay_closure_gate_pass": payload.get("runner_replay_closure_gate_pass") is True,
        "score_matches_probe": (
            payload.get("score_matches_probe") is True
            or payload.get("runner_replay_matches_probe_score") is True
        ),
        "claim_promotion_allowed": payload.get("claim_promotion_allowed") is True,
        "claim_locked_source": payload.get("claim_promotion_allowed") is False,
        "claim_boundary": payload.get("claim_boundary", ""),
        "metrics": {
            "ranking_pr_auc": metrics.get("ranking_pr_auc"),
            "ranking_pr_auc_ci_low": metrics.get("ranking_pr_auc_ci_low"),
            "top20_hit_rate": metrics.get("top20_hit_rate"),
        },
        "target_map": [
            {"target_id": target_id, "source_target": source_target}
            for target_id, source_target in TARGET_MAP
        ],
        "read_only": {
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
        },
    }
    return rows, provenance


def build_current_input_artifact(
    ranking_summary_json: str | Path,
    hard_decoy_summary_json: str | Path,
    *,
    ranking_rows_csv: str = "",
    preregistered_replay_json: str | Path = DEFAULT_PREREGISTERED_REPLAY_JSON,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if str(preregistered_replay_json or "").strip():
        replay_path = _resolve(preregistered_replay_json)
        replay_payload = _load_json(replay_path)
        return _preregistered_replay_rows(replay_payload, replay_path)

    ranking_summary_path = _resolve(ranking_summary_json)
    hard_decoy_summary_path = _resolve(hard_decoy_summary_json)
    ranking_summary = _load_json(ranking_summary_path)
    hard_decoy_summary = _load_json(hard_decoy_summary_path)

    metrics = _ranking_metrics(ranking_summary)
    hard_stats = _hard_decoy_stats(hard_decoy_summary)
    rows_path, rank_evidence_mode, complete_rows = _ranking_rows_path(ranking_summary, ranking_rows_csv)
    score_col = str(ranking_summary.get("score_col") or "")
    lower_better = bool(ranking_summary.get("lower_better", True))
    separation = (
        _target_separation_from_rows(
            rows_path,
            score_col=score_col,
            lower_better=lower_better,
            complete_rows=complete_rows,
        )
        if rows_path is not None and score_col
        else {}
    )

    rows: list[dict[str, Any]] = []
    for target_id, source_target in TARGET_MAP:
        stats = hard_stats.get(source_target, {})
        target_separation = separation.get(source_target, {})
        rows.append(
            {
                "target_id": target_id,
                "positive_count": stats.get("binders", ""),
                "ranking_pr_auc": metrics["ranking_pr_auc"],
                "ranking_pr_auc_ci_low": metrics["ranking_pr_auc_ci_low"],
                "top20_hit_rate": metrics["top20_hit_rate"],
                "decoys_above_positive_count": target_separation.get(
                    "decoys_above_positive_count", ""
                ),
                "positive_target_rank": target_separation.get("positive_target_rank", ""),
                "positive_anchor_distance_a": target_separation.get("positive_anchor_distance_a", ""),
                "top_decoy_anchor_distance_a": target_separation.get(
                    "top_decoy_anchor_distance_a", ""
                ),
                "retained_target_row_count": target_separation.get("retained_target_row_count", ""),
                "retained_positive_count": target_separation.get("retained_positive_count", ""),
                "top_decoy_retained_count": target_separation.get("top_decoy_retained_count", ""),
                "decoy_class_counts": json.dumps({}),
            }
        )

    provenance = {
        "packet_type": "gpcr_hard_decoy_suite_current_input_provenance",
        "schema_version": "gpcr_hard_decoy_suite_current_input_provenance_v1",
        "status": "gpcr_hard_decoy_suite_current_input_ready",
        "source_mode": "ranking_summary_and_hard_decoy_summary",
        "ranking_summary_json": str(ranking_summary_path),
        "hard_decoy_summary_json": str(hard_decoy_summary_path),
        "ranking_rows_csv": "" if rows_path is None else str(rows_path),
        "ranking_rows_available": rows_path is not None,
        "ranking_rows_complete": complete_rows,
        "rank_evidence_mode": rank_evidence_mode,
        "ranking_rows_source_missing_fail_closed": rows_path is None,
        "score_col": score_col,
        "lower_better": lower_better,
        "metrics": metrics,
        "target_map": [
            {"target_id": target_id, "source_target": source_target}
            for target_id, source_target in TARGET_MAP
        ],
        "read_only": {
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
        },
    }
    return rows, provenance


def write_current_input_csv(out_csv: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(out_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in INPUT_COLUMNS})


def write_provenance(out_json: str | Path, provenance: dict[str, Any]) -> None:
    path = _resolve(out_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build current GPCR hard-decoy suite input CSV from actual artifacts."
    )
    parser.add_argument("--ranking-summary-json", default=DEFAULT_RANKING_SUMMARY_JSON)
    parser.add_argument("--hard-decoy-summary-json", default=DEFAULT_HARD_DECOY_SUMMARY_JSON)
    parser.add_argument("--ranking-rows-csv", default="")
    parser.add_argument("--preregistered-replay-json", default=DEFAULT_PREREGISTERED_REPLAY_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-provenance-json", default=DEFAULT_OUT_PROVENANCE_JSON)
    args = parser.parse_args(argv)

    rows, provenance = build_current_input_artifact(
        args.ranking_summary_json,
        args.hard_decoy_summary_json,
        ranking_rows_csv=args.ranking_rows_csv,
        preregistered_replay_json=args.preregistered_replay_json,
    )
    write_current_input_csv(args.out_csv, rows)
    write_provenance(args.out_provenance_json, provenance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
