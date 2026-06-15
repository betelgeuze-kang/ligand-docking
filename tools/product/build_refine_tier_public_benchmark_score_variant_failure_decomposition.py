#!/usr/bin/env python3
"""Read-only R9 score-variant failure decomposition packet."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCORE_VARIANT_JSON = "config/refine_tier_public_benchmark_score_variant_probe_current.json"
DEFAULT_CV_JSON = "config/refine_tier_public_benchmark_calibration_cross_validation_probe_current.json"
DEFAULT_RESIDUAL_PRIORITY_JSON = (
    "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_score_variant_failure_decomposition_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_score_variant_failure_decomposition_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_score_variant_failure_decomposition_current.md"

CLAIM_BOUNDARY = (
    "R9 score-variant failure decomposition only joins existing score-variant, cross-validation, "
    "and metric-payload priority packets to explain residual movement. It does not train models, "
    "rewrite scores, write reviewed metric payloads, approve receipts, promote canonical intake, "
    "change production scoring, run docking/MD, download, upload, email, delete, commit, push, "
    "or mutate external state."
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(_text(value))
    except (TypeError, ValueError):
        return None


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.12g}"


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")))


def _index_rows(rows: Any) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _key(row)
        if key[0] and key[1]:
            result[key] = row
    return result


def _group_priority_rows(rows: Any) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _key(row)
        if key[0] and key[1]:
            grouped[key].append(row)
    return dict(grouped)


def _gap_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(_text(row.get("operator_gap_class")) or "unknown" for row in rows)


def _metric_names(rows: list[dict[str, Any]]) -> str:
    return ";".join(_text(row.get("metric_name")) for row in rows if _text(row.get("metric_name")))


def _first_priority(rows: list[dict[str, Any]]) -> str:
    ranks = [_int(row.get("payload_priority_rank")) for row in rows if _int(row.get("payload_priority_rank"))]
    return str(min(ranks)) if ranks else ""


def _choose(*rows: dict[str, Any], field: str) -> str:
    for row in rows:
        value = _text(row.get(field))
        if value:
            return value
    return ""


def _variant_effect(delta: int) -> str:
    if delta < 0:
        return "improved"
    if delta > 0:
        return "worsened"
    return "unchanged"


def _decomposition_class(
    *,
    best_error: int,
    best_delta: int,
    locked_error: int,
    locked_delta: int,
    split: str,
    payload_rows: list[dict[str, Any]],
) -> str:
    gaps = _gap_counts(payload_rows)
    if best_error >= 10 and best_delta > 0:
        return "score_variant_worsens_high_error"
    if best_delta < 0 and locked_error >= 10:
        return "score_variant_improves_but_cv_high_error"
    if best_error >= 10 and gaps:
        return "score_variant_high_error_payload_review"
    if split == "holdout" and max(best_error, locked_error) >= 8:
        return "holdout_variant_cv_generalization_review"
    if locked_delta > 0:
        return "cv_regression_after_score_variant"
    if best_delta < 0:
        return "score_variant_improvement_monitor"
    return "monitor"


def _next_step(*, decomposition_class: str, payload_rows: list[dict[str, Any]]) -> str:
    gaps = _gap_counts(payload_rows)
    if gaps.get("existing_metric_payload_present_without_operator_receipt"):
        return "Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence."
    if gaps.get("operator_receipt_blocked_placeholders"):
        return "Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose."
    if decomposition_class == "score_variant_worsens_high_error":
        return "Audit whether contact-density correction over-ranks this target before adding stronger calibration terms."
    if "holdout" in decomposition_class:
        return "Add independent reviewed holdout evidence before using this descriptor hypothesis for scoring."
    if "cv" in decomposition_class:
        return "Audit target-held-out descriptor scaling and receptor/pose assembly for this row."
    return "Monitor after high-priority payload and CV failure rows are closed."


def _priority_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, int, str]:
    return (
        1 if row.get("decomposition_class") in {
            "score_variant_worsens_high_error",
            "score_variant_improves_but_cv_high_error",
            "score_variant_high_error_payload_review",
        } else 0,
        max(_int(row.get("best_variant_rank_abs_error")), _int(row.get("locked_cv_rank_abs_error"))),
        max(0, _int(row.get("best_variant_rank_error_delta_from_baseline"))),
        _int(row.get("operator_receipt_blocked_payload_count"))
        + _int(row.get("operator_receipt_missing_payload_count")),
        1 if row.get("split") == "holdout" else 0,
        _text(row.get("target_id")),
    )


def build_refine_tier_public_benchmark_score_variant_failure_decomposition(
    *,
    score_variant_json: str | Path = DEFAULT_SCORE_VARIANT_JSON,
    cv_json: str | Path = DEFAULT_CV_JSON,
    residual_priority_json: str | Path = DEFAULT_RESIDUAL_PRIORITY_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    score_payload, score_present = _read_json(score_variant_json, root=root_path)
    cv_payload, cv_present = _read_json(cv_json, root=root_path)
    priority_payload, priority_present = _read_json(residual_priority_json, root=root_path)
    score_summary = score_payload.get("summary") if isinstance(score_payload.get("summary"), dict) else {}
    cv_summary = cv_payload.get("summary") if isinstance(cv_payload.get("summary"), dict) else {}
    priority_summary = (
        priority_payload.get("summary") if isinstance(priority_payload.get("summary"), dict) else {}
    )
    score_baseline = _index_rows(score_payload.get("baseline_rank_residual_rows"))
    best_variant = _index_rows(score_payload.get("best_variant_rank_residual_rows"))
    cv_baseline = _index_rows(cv_payload.get("baseline_rank_residual_rows"))
    locked_cv = _index_rows(cv_payload.get("locked_cv_rank_residual_rows"))
    priority_rows = _group_priority_rows(priority_payload.get("priority_rows"))
    keys = sorted(set(score_baseline) | set(best_variant) | set(cv_baseline) | set(locked_cv) | set(priority_rows))

    rows: list[dict[str, Any]] = []
    for key in keys:
        baseline = score_baseline.get(key, {})
        variant = best_variant.get(key, {})
        cv_base = cv_baseline.get(key, {})
        locked = locked_cv.get(key, {})
        payload_rows = priority_rows.get(key, [])
        gaps = _gap_counts(payload_rows)
        baseline_error = _int(baseline.get("rank_abs_error"))
        best_error = _int(variant.get("rank_abs_error"))
        cv_baseline_error = _int(cv_base.get("rank_abs_error"))
        locked_error = _int(locked.get("rank_abs_error"))
        best_delta = best_error - baseline_error
        locked_delta = locked_error - cv_baseline_error
        split = _choose(variant, locked, baseline, cv_base, field="split")
        klass = _decomposition_class(
            best_error=best_error,
            best_delta=best_delta,
            locked_error=locked_error,
            locked_delta=locked_delta,
            split=split,
            payload_rows=payload_rows,
        )
        rows.append(
            {
                "decomposition_priority_rank": 0,
                "target_id": key[0],
                "pose_id": key[1],
                "split": split,
                "source": _choose(variant, locked, baseline, cv_base, field="source"),
                "reference_deltaG": _choose(variant, locked, baseline, cv_base, field="reference"),
                "baseline_proxy": _choose(baseline, variant, locked, cv_base, field="baseline_proxy"),
                "best_variant_proxy": _text(variant.get("variant_proxy")),
                "locked_cv_proxy": _text(locked.get("variant_proxy")),
                "reference_rank": _int(variant.get("reference_rank") or locked.get("reference_rank")),
                "baseline_rank": _int(baseline.get("variant_rank")),
                "best_variant_rank": _int(variant.get("variant_rank")),
                "locked_cv_rank": _int(locked.get("variant_rank")),
                "baseline_rank_abs_error": baseline_error,
                "best_variant_rank_abs_error": best_error,
                "best_variant_rank_error_delta_from_baseline": best_delta,
                "best_variant_effect": _variant_effect(best_delta),
                "cv_baseline_rank_abs_error": cv_baseline_error,
                "locked_cv_rank_abs_error": locked_error,
                "locked_cv_rank_error_delta_from_baseline": locked_delta,
                "locked_cv_effect": _variant_effect(locked_delta),
                "contact_per_atom": _choose(variant, locked, baseline, cv_base, field="contact_per_atom"),
                "pose_atom_count": _choose(variant, locked, baseline, cv_base, field="pose_atom_count"),
                "decomposition_class": klass,
                "metric_payload_priority_row_count": len(payload_rows),
                "first_payload_priority_rank": _first_priority(payload_rows),
                "required_metric_names": _metric_names(payload_rows),
                "operator_receipt_blocked_payload_count": gaps.get("operator_receipt_blocked_placeholders", 0),
                "operator_receipt_missing_payload_count": sum(
                    count for gap, count in gaps.items() if "missing" in gap or "without_operator_receipt" in gap
                ),
                "existing_metric_source_artifact_present_without_receipt_count": gaps.get(
                    "existing_metric_payload_present_without_operator_receipt", 0
                ),
                "operator_gap_classes": ";".join(f"{gap}:{count}" for gap, count in sorted(gaps.items())),
                "next_science_step": _next_step(decomposition_class=klass, payload_rows=payload_rows),
                "payload_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
        )

    sorted_rows = sorted(rows, key=_priority_sort_key, reverse=True)
    for index, row in enumerate(sorted_rows, start=1):
        row["decomposition_priority_rank"] = index

    improved_rows = [row for row in sorted_rows if row["best_variant_effect"] == "improved"]
    worsened_rows = [row for row in sorted_rows if row["best_variant_effect"] == "worsened"]
    high_after_variant_rows = [row for row in sorted_rows if _int(row.get("best_variant_rank_abs_error")) >= 10]
    high_locked_cv_rows = [row for row in sorted_rows if _int(row.get("locked_cv_rank_abs_error")) >= 10]
    persistent_high_rows = [
        row
        for row in sorted_rows
        if _int(row.get("best_variant_rank_abs_error")) >= 10
        and _int(row.get("locked_cv_rank_abs_error")) >= 10
    ]
    payload_matched_rows = [row for row in sorted_rows if _int(row.get("metric_payload_priority_row_count"))]
    best_p05 = _float(score_summary.get("best_variant_bootstrap_p05"))
    locked_cv_p05 = _float(cv_summary.get("locked_cv_bootstrap_p05"))
    locked_cv_gap = _float(cv_summary.get("locked_cv_bootstrap_p05_gap_to_claim_grade"))
    if locked_cv_gap is None and locked_cv_p05 is not None:
        locked_cv_gap = MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - locked_cv_p05
    summary = {
        "packet_type": "refine_tier_public_benchmark_score_variant_failure_decomposition",
        "status": (
            "refine_tier_public_benchmark_score_variant_failure_decomposition_ready"
            if score_present and cv_present and priority_present and sorted_rows
            else "blocked_refine_tier_public_benchmark_score_variant_failure_decomposition"
        ),
        "score_variant_json": _display(score_variant_json, root=root_path),
        "score_variant_json_present": score_present,
        "cv_json": _display(cv_json, root=root_path),
        "cv_json_present": cv_present,
        "residual_priority_json": _display(residual_priority_json, root=root_path),
        "residual_priority_json_present": priority_present,
        "best_variant_id": score_summary.get("best_variant_id", ""),
        "best_variant_bootstrap_p05": best_p05,
        "best_variant_bootstrap_p05_delta": score_summary.get("best_variant_bootstrap_p05_delta"),
        "best_variant_bootstrap_p05_gap_to_claim_grade": (
            None if best_p05 is None else MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - best_p05
        ),
        "locked_cv_model_id": cv_summary.get("locked_cv_model_id", ""),
        "locked_cv_bootstrap_p05": locked_cv_p05,
        "locked_cv_bootstrap_p05_gap_to_claim_grade": locked_cv_gap,
        "decomposition_row_count": len(sorted_rows),
        "variant_improved_row_count": len(improved_rows),
        "variant_worsened_row_count": len(worsened_rows),
        "variant_unchanged_row_count": len(sorted_rows) - len(improved_rows) - len(worsened_rows),
        "best_variant_high_error_row_count": len(high_after_variant_rows),
        "locked_cv_high_error_row_count": len(high_locked_cv_rows),
        "persistent_high_error_row_count": len(persistent_high_rows),
        "payload_priority_matched_row_count": len(payload_matched_rows),
        "metric_payload_priority_row_count": int(
            priority_summary.get("metric_payload_priority_row_count") or sum(
                _int(row.get("metric_payload_priority_row_count")) for row in sorted_rows
            )
        ),
        "operator_receipt_blocked_payload_count": sum(
            _int(row.get("operator_receipt_blocked_payload_count")) for row in sorted_rows
        ),
        "operator_receipt_missing_payload_count": sum(
            _int(row.get("operator_receipt_missing_payload_count")) for row in sorted_rows
        ),
        "existing_metric_source_artifact_present_without_receipt_count": sum(
            _int(row.get("existing_metric_source_artifact_present_without_receipt_count"))
            for row in sorted_rows
        ),
        "top_decomposition_target_id": sorted_rows[0].get("target_id", "") if sorted_rows else "",
        "top_decomposition_pose_id": sorted_rows[0].get("pose_id", "") if sorted_rows else "",
        "top_decomposition_class": sorted_rows[0].get("decomposition_class", "") if sorted_rows else "",
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the top decomposition rows to decide whether the next R9 work is descriptor calibration "
            "or metric payload receipt review; keep claim promotion blocked until reviewed payload evidence "
            "and bootstrap p05 >= 0.5 are both true."
        ),
    }
    return {"summary": summary, "decomposition_rows": sorted_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Score-Variant Failure Decomposition",
        "",
        f"- status: `{s['status']}`",
        f"- best_variant_id: `{s['best_variant_id']}`",
        f"- best_variant_bootstrap_p05: `{s['best_variant_bootstrap_p05']}`",
        f"- best_variant_bootstrap_p05_gap_to_claim_grade: `{s['best_variant_bootstrap_p05_gap_to_claim_grade']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_bootstrap_p05: `{s['locked_cv_bootstrap_p05']}`",
        f"- decomposition_row_count: `{s['decomposition_row_count']}`",
        f"- variant_improved/worsened/unchanged: `{s['variant_improved_row_count']}/"
        f"{s['variant_worsened_row_count']}/{s['variant_unchanged_row_count']}`",
        f"- best_variant_high_error_row_count: `{s['best_variant_high_error_row_count']}`",
        f"- locked_cv_high_error_row_count: `{s['locked_cv_high_error_row_count']}`",
        f"- persistent_high_error_row_count: `{s['persistent_high_error_row_count']}`",
        f"- payload_priority_matched_row_count: `{s['payload_priority_matched_row_count']}`",
        f"- operator_receipt_blocked_payload_count: `{s['operator_receipt_blocked_payload_count']}`",
        f"- operator_receipt_missing_payload_count: `{s['operator_receipt_missing_payload_count']}`",
        "",
        "## Top Decomposition Rows",
        "",
        "| rank | target | pose | split | class | baseline err | best err | best delta | cv err | cv delta | gaps | next |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["decomposition_rows"][:12]:
        lines.append(
            f"| `{row['decomposition_priority_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['split']}` | `{row['decomposition_class']}` | `{row['baseline_rank_abs_error']}` | "
            f"`{row['best_variant_rank_abs_error']}` | "
            f"`{row['best_variant_rank_error_delta_from_baseline']}` | "
            f"`{row['locked_cv_rank_abs_error']}` | `{row['locked_cv_rank_error_delta_from_baseline']}` | "
            f"`{row['operator_gap_classes']}` | {row['next_science_step']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 score-variant failure decomposition packet.")
    parser.add_argument("--score-variant-json", default=DEFAULT_SCORE_VARIANT_JSON)
    parser.add_argument("--cv-json", default=DEFAULT_CV_JSON)
    parser.add_argument("--residual-priority-json", default=DEFAULT_RESIDUAL_PRIORITY_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_score_variant_failure_decomposition(
        score_variant_json=args.score_variant_json,
        cv_json=args.cv_json,
        residual_priority_json=args.residual_priority_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["decomposition_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
