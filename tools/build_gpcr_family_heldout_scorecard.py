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

DEFAULT_ROWS_CSVS = [
    "runs/external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv",
    "runs/external_validation_2026-04-14_biorxiv_v7mlrefresh1_set2_expanded_ood_gpcr_chembl50_full_p0_n10000_r1_stage5_ranking_rows.csv",
]
DEFAULT_SUMMARY_JSONS = [
    "runs/external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json",
    "runs/external_validation_2026-04-14_biorxiv_v7mlrefresh1_set2_expanded_ood_gpcr_chembl50_full_p0_n10000_r1_stage5_ranking_summary.json",
]
DEFAULT_OUT_JSON = "runs/gpcr_family_heldout_scorecard_current.json"
DEFAULT_OUT_MD = "runs/gpcr_family_heldout_scorecard_current.md"

MINIMUM_GPCR_POSITIVE_COUNT = 9
MINIMUM_DISTINCT_GPCR_POSITIVE_TARGETS = 2
GPCR_TARGET_MARKERS = (
    "GPCR",
    "ADRB",
    "DRD",
    "HTR",
    "OPRM",
    "OPRD",
    "OPRK",
    "CHRM",
    "CCR",
    "CXCR",
    "SSTR",
    "HRH",
    "P2RY",
    "CHEMBL217",
    "CHEMBL224",
    "CHEMBL233",
)


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _target_family(target: str) -> str:
    upper = target.upper()
    if any(marker in upper for marker in GPCR_TARGET_MARKERS):
        return "gpcr"
    if "KINASE" in upper:
        return "kinase"
    if "TRPV" in upper or "ION" in upper:
        return "ion_channel"
    return "unknown"


def _score_column(rows: list[dict[str, str]], summary: dict[str, Any]) -> str:
    for key in ("score_col", "probability_score_col", "probability_score_col_used"):
        direct = _text(summary.get(key))
        if direct:
            return direct
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    for key in ("score_col", "probability_score_col", "probability_score_col_used"):
        direct = _text(metrics.get(key))
        if direct:
            return direct
    for row in rows:
        for key in row:
            if key.startswith("binding_score_"):
                return key
    return ""


def _summary_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    metrics_ci = summary.get("metrics_ci") if isinstance(summary.get("metrics_ci"), dict) else {}
    pr_auc_ci = metrics_ci.get("pr_auc_unique_key") or metrics_ci.get("pr_auc") or {}
    if not isinstance(pr_auc_ci, dict):
        pr_auc_ci = {}
    return {
        "ranking_pr_auc": _as_float(metrics.get("pr_auc_unique_key", metrics.get("pr_auc"))),
        "ranking_pr_auc_ci_low": _as_float(pr_auc_ci.get("low")),
        "ranking_top20_hit_rate": _as_float(metrics.get("top20_hit_rate")),
        "positive_count": _as_float(metrics.get("positive_count_unique_key", metrics.get("positive_count"))),
    }


def _dataset_row(
    *,
    rows_path: Path | None,
    summary_path: Path | None,
) -> dict[str, Any]:
    rows = _read_csv(rows_path)
    summary = _read_json(summary_path)
    score_col = _score_column(rows, summary)
    families: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    positive_target_counts: dict[str, int] = {}
    missing_score_rows = 0
    duplicate_keys: set[tuple[str, str]] = set()
    seen_keys: set[tuple[str, str]] = set()
    positive_ligands: list[str] = []

    for row in rows:
        target = _text(row.get("target")) or "unknown"
        ligand_id = _text(row.get("ligand_id")) or "unknown"
        family = _target_family(target)
        families[family] = families.get(family, 0) + 1
        target_counts[target] = target_counts.get(target, 0) + 1
        key = (target, ligand_id)
        if key in seen_keys:
            duplicate_keys.add(key)
        seen_keys.add(key)
        if score_col and _as_float(row.get(score_col)) is None:
            missing_score_rows += 1
        if _is_positive(row):
            positive_target_counts[target] = positive_target_counts.get(target, 0) + 1
            if len(positive_ligands) < 12:
                positive_ligands.append(ligand_id)

    positive_count = sum(positive_target_counts.values())
    negative_count = max(len(rows) - positive_count, 0)
    return {
        "rows_csv": str(rows_path) if rows_path else None,
        "summary_json": str(summary_path) if summary_path else None,
        "rows_available": bool(rows),
        "summary_available": bool(summary),
        "row_count": int(len(rows)),
        "positive_count": int(positive_count),
        "negative_count": int(negative_count),
        "score_column": score_col or None,
        "missing_or_non_finite_score_rows": int(missing_score_rows if score_col else len(rows)),
        "families": dict(sorted(families.items())),
        "target_counts": dict(sorted(target_counts.items())),
        "positive_target_counts": dict(sorted(positive_target_counts.items())),
        "distinct_positive_target_count": int(len(positive_target_counts)),
        "duplicate_row_identity_count": int(len(duplicate_keys)),
        "positive_ligand_sample": positive_ligands,
        "metrics": _summary_metrics(summary),
    }


def _merge_family_context(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    gpcr_targets: dict[str, int] = {}
    gpcr_positive_targets: dict[str, int] = {}
    row_count = 0
    positive_count = 0
    dataset_count = 0
    for dataset in datasets:
        if "gpcr" not in dataset.get("families", {}):
            continue
        dataset_count += 1
        row_count += int(dataset.get("families", {}).get("gpcr", 0))
        for target, count in dataset.get("target_counts", {}).items():
            if _target_family(_text(target)) == "gpcr":
                gpcr_targets[target] = gpcr_targets.get(target, 0) + int(count)
        for target, count in dataset.get("positive_target_counts", {}).items():
            if _target_family(_text(target)) == "gpcr":
                gpcr_positive_targets[target] = gpcr_positive_targets.get(target, 0) + int(count)
                positive_count += int(count)
    return {
        "dataset_count": int(dataset_count),
        "row_count": int(row_count),
        "positive_count": int(positive_count),
        "minimum_positive_count": MINIMUM_GPCR_POSITIVE_COUNT,
        "positive_count_gate_pass": positive_count >= MINIMUM_GPCR_POSITIVE_COUNT,
        "distinct_targets": sorted(gpcr_targets),
        "distinct_positive_targets": sorted(gpcr_positive_targets),
        "distinct_positive_target_count": int(len(gpcr_positive_targets)),
        "minimum_distinct_positive_targets": MINIMUM_DISTINCT_GPCR_POSITIVE_TARGETS,
        "family_held_out_gate_pass": len(gpcr_positive_targets) >= MINIMUM_DISTINCT_GPCR_POSITIVE_TARGETS,
        "positive_target_counts": dict(sorted(gpcr_positive_targets.items())),
    }


def _warning_rows(datasets: list[dict[str, Any]], gpcr: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if not datasets or not any(dataset.get("rows_available") for dataset in datasets):
        warnings.append(
            {
                "family": "gpcr",
                "reason": "missing_artifact",
                "severity": "blocking",
                "note": "No ranking rows were available for family-held-out scorecard construction.",
            }
        )
    if gpcr["dataset_count"] == 0:
        warnings.append(
            {
                "family": "gpcr",
                "reason": "missing_required_family",
                "severity": "blocking",
                "note": "No GPCR rows were found in the provided validation artifacts.",
            }
        )
    if gpcr["positive_count"] <= 0 or all(dataset.get("negative_count", 0) <= 0 for dataset in datasets):
        warnings.append(
            {
                "family": "gpcr",
                "reason": "single_class_labels",
                "severity": "blocking",
                "note": "Both positive and negative labels are required for a scorecard.",
            }
        )
    if gpcr["positive_count"] < MINIMUM_GPCR_POSITIVE_COUNT:
        warnings.append(
            {
                "family": "gpcr",
                "reason": "insufficient_gpcr_positive_count",
                "severity": "blocking",
                "observed": gpcr["positive_count"],
                "threshold": MINIMUM_GPCR_POSITIVE_COUNT,
                "note": "Do not freeze a 100k rerun packet before positive_count >= 9.",
            }
        )
    if gpcr["distinct_positive_target_count"] < MINIMUM_DISTINCT_GPCR_POSITIVE_TARGETS:
        warnings.append(
            {
                "family": "gpcr",
                "reason": "insufficient_distinct_gpcr_positive_targets",
                "severity": "blocking",
                "observed": gpcr["distinct_positive_target_count"],
                "threshold": MINIMUM_DISTINCT_GPCR_POSITIVE_TARGETS,
                "positive_target_counts": gpcr["positive_target_counts"],
                "note": "ADRB2-only recovery is not GPCR family generalization.",
            }
        )
    if set(gpcr["distinct_positive_targets"]) == {"ADRB2_GPCR_BLIND"}:
        warnings.append(
            {
                "family": "gpcr",
                "reason": "target_specific_adrb2_bias_risk",
                "severity": "blocking",
                "positive_target_counts": gpcr["positive_target_counts"],
                "note": "Router/platform claim remains forbidden while positives are ADRB2-only.",
            }
        )
    for dataset in datasets:
        if dataset.get("duplicate_row_identity_count", 0) > 0:
            warnings.append(
                {
                    "family": "gpcr",
                    "reason": "duplicate_row_identity",
                    "severity": "blocking",
                    "rows_csv": dataset.get("rows_csv"),
                    "observed": dataset.get("duplicate_row_identity_count"),
                }
            )
        if dataset.get("rows_available") and dataset.get("missing_or_non_finite_score_rows", 0) > 0:
            warnings.append(
                {
                    "family": "gpcr",
                    "reason": "missing_or_non_finite_scores",
                    "severity": "blocking",
                    "rows_csv": dataset.get("rows_csv"),
                    "observed": dataset.get("missing_or_non_finite_score_rows"),
                }
            )
    return warnings


def build_scorecard(
    *,
    rows_csvs: list[str | Path] | None = None,
    summary_jsons: list[str | Path] | None = None,
) -> dict[str, Any]:
    row_inputs = DEFAULT_ROWS_CSVS if rows_csvs is None else rows_csvs
    summary_inputs = DEFAULT_SUMMARY_JSONS if summary_jsons is None else summary_jsons
    row_paths = [_resolve(path) for path in row_inputs]
    summary_paths = [_resolve(path) for path in summary_inputs]
    if len(summary_paths) < len(row_paths):
        summary_paths.extend([None] * (len(row_paths) - len(summary_paths)))
    datasets = [
        _dataset_row(rows_path=row_path, summary_path=summary_paths[idx] if idx < len(summary_paths) else None)
        for idx, row_path in enumerate(row_paths)
    ]
    gpcr_context = _merge_family_context(datasets)
    warnings = _warning_rows(datasets, gpcr_context)
    blocking_warnings = [row for row in warnings if row.get("severity") == "blocking"]
    green = (
        gpcr_context["positive_count_gate_pass"]
        and gpcr_context["family_held_out_gate_pass"]
        and not blocking_warnings
    )
    return {
        "packet_type": "gpcr_family_heldout_scorecard",
        "generated_at_local": dt.datetime.now().replace(microsecond=0).isoformat(),
        "source_artifacts": {
            "rows_csvs": [str(path) if path else None for path in row_paths],
            "summary_jsons": [str(path) if path else None for path in summary_paths[: len(row_paths)]],
        },
        "summary": {
            "scorecard_level_status": "pass" if green else "fail",
            "acceptance_overall_pass": bool(green),
            "family_held_out_green": bool(green),
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "gpcr_positive_count": gpcr_context["positive_count"],
            "minimum_gpcr_positive_count": MINIMUM_GPCR_POSITIVE_COUNT,
            "gpcr_distinct_positive_target_count": gpcr_context["distinct_positive_target_count"],
            "minimum_distinct_gpcr_positive_targets": MINIMUM_DISTINCT_GPCR_POSITIVE_TARGETS,
            "blocker_count": int(len(blocking_warnings)),
            "next_required_step": (
                "Run full 100k guarded readiness review; scorecard alone does not promote claim."
                if green
                else "Add non-ADRB2, non-leaky GPCR positive evidence and rerun this scorecard."
            ),
        },
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "router_platform_claim_allowed": False,
            "scorecard_alone_does_not_make_claim_safe": True,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
        "families": {"gpcr": gpcr_context},
        "datasets": datasets,
        "warnings": warnings,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    gpcr = payload["families"]["gpcr"]
    warnings = payload.get("warnings", [])
    lines = [
        "# GPCR Family-Held-Out Scorecard",
        "",
        "## Summary",
        f"- scorecard_level_status: `{summary['scorecard_level_status']}`",
        f"- acceptance_overall_pass: `{str(summary['acceptance_overall_pass']).lower()}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- router_claim_allowed: `{str(summary['router_claim_allowed']).lower()}`",
        f"- platform_claim_allowed: `{str(summary['platform_claim_allowed']).lower()}`",
        f"- gpcr_positive_count: `{summary['gpcr_positive_count']}`",
        f"- gpcr_distinct_positive_target_count: `{summary['gpcr_distinct_positive_target_count']}`",
        "",
        "## GPCR Coverage",
        f"- positive_count_gate_pass: `{str(gpcr['positive_count_gate_pass']).lower()}`",
        f"- family_held_out_gate_pass: `{str(gpcr['family_held_out_gate_pass']).lower()}`",
        f"- distinct_positive_targets: `{', '.join(gpcr['distinct_positive_targets'])}`",
        "",
        "## Blocking Warnings",
        "",
        "| reason | severity | note |",
        "| --- | --- | --- |",
    ]
    if warnings:
        for row in warnings:
            lines.append(
                "| `{reason}` | `{severity}` | {note} |".format(
                    reason=row.get("reason"),
                    severity=row.get("severity"),
                    note=_text(row.get("note")),
                )
            )
    else:
        lines.append("| `none` | `none` | scorecard has no blocking warnings |")
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    *,
    rows_csvs: list[str | Path] | None,
    summary_jsons: list[str | Path] | None,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_scorecard(rows_csvs=rows_csvs, summary_jsons=summary_jsons)
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR family-held-out scorecard from local ranking rows.")
    parser.add_argument("--rows-csv", action="append", dest="rows_csvs")
    parser.add_argument("--summary-json", action="append", dest="summary_jsons")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        rows_csvs=args.rows_csvs,
        summary_jsons=args.summary_jsons,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
