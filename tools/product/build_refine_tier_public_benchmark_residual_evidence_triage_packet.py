#!/usr/bin/env python3
"""Read-only R9 residual evidence triage packet."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAYLOAD_PRIORITY_JSON = (
    "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
)
DEFAULT_FEATURE_EXTRAPOLATION_JSON = (
    "config/refine_tier_public_benchmark_cv_feature_extrapolation_probe_current.json"
)
DEFAULT_MODEL_EXTENSION_JSON = "config/refine_tier_public_benchmark_cv_model_extension_probe_current.json"
DEFAULT_SEEDED_BACKFILL_JSON = (
    "config/refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_current.json"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_residual_evidence_triage_packet_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_residual_evidence_triage_packet_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_residual_evidence_triage_packet_current.md"

CLAIM_BOUNDARY = (
    "R9 residual evidence triage packet only joins existing residual, feature-extrapolation, "
    "model-extension, and metric-payload priority artifacts to choose the next review lane per "
    "target/pose. It does not compute metrics, write metric payload JSON, approve receipts, promote "
    "canonical intake, change production scoring, run docking/MD, download, upload, email, delete, "
    "commit, push, or mutate external state."
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
    return "" if value is None else str(value).strip()


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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")))


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _index_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _key(row)
        if key[0] and key[1]:
            out[key] = row
    return out


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _key(row)
        if key[0] and key[1]:
            grouped[key].append(row)
    return dict(grouped)


def _group_backfill_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    return _group_rows(rows)


def _gap_counter(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(_text(row.get("operator_gap_class")) or "unknown" for row in rows)


def _metric_names(rows: list[dict[str, Any]]) -> str:
    return ";".join(_text(row.get("metric_name")) for row in rows if _text(row.get("metric_name")))


def _priority_rank(rows: list[dict[str, Any]]) -> int:
    ranks = [_int(row.get("payload_priority_rank")) for row in rows if _int(row.get("payload_priority_rank"))]
    return min(ranks) if ranks else 0


def _next_lane(
    *,
    feature_class: str,
    gaps: Counter[str],
    cv_worse: bool,
    leverage: bool,
) -> tuple[str, str]:
    if gaps.get("existing_metric_payload_present_without_operator_receipt"):
        return (
            "seeded_payload_receipt_coverage_first",
            "Add operator receipt coverage for existing seeded metric JSON before using it as reviewed evidence.",
        )
    if feature_class == "high_error_in_distribution":
        return (
            "metric_payload_pose_model_form_review",
            "Review metric payload values, pose assignment, and model-form assumptions; feature range alone does not explain this residual.",
        )
    if feature_class == "high_error_feature_extrapolation":
        return (
            "descriptor_coverage_target_heldout_evidence",
            "Add target-held-out evidence or descriptor coverage near this feature range before stronger calibration terms.",
        )
    if leverage:
        return (
            "leverage_payload_review",
            "Review all DockQ/lDDT-PLI/internal_deltaG payloads for this leverage row before rerunning bootstrap gates.",
        )
    if cv_worse:
        return (
            "cv_regression_payload_review",
            "Review CV regression payloads and fold scaling before another calibration attempt.",
        )
    if gaps.get("operator_receipt_blocked_placeholders"):
        return (
            "blocked_receipt_fill",
            "Fill blocked metric-source receipt placeholders and keep claim promotion closed.",
        )
    return ("monitor_after_top_rows", "Monitor after higher-priority residual evidence rows are closed.")


def _seeded_backfill_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_count = len(rows)
    valid_count = sum(1 for row in rows if _text(row.get("payload_validation_status")) == "pass")
    hash_verified_count = sum(
        1
        for row in rows
        if _int(row.get("input_artifact_count"))
        and _int(row.get("input_artifact_count")) == _int(row.get("input_artifact_sha256_verified_count"))
    )
    pending_count = sum(_int(row.get("operator_manual_pending_field_count")) for row in rows)
    return {
        "seeded_backfill_template_row_count": row_count,
        "seeded_backfill_payload_schema_valid_count": valid_count,
        "seeded_backfill_input_sha256_verified_count": hash_verified_count,
        "seeded_backfill_operator_manual_pending_field_count": pending_count,
        "seeded_backfill_template_ready": bool(row_count and valid_count == row_count and hash_verified_count == row_count),
    }


def _sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    lane_weight = {
        "metric_payload_pose_model_form_review": 6,
        "descriptor_coverage_target_heldout_evidence": 6,
        "seeded_payload_receipt_coverage_first": 5,
        "leverage_payload_review": 4,
        "cv_regression_payload_review": 3,
        "blocked_receipt_fill": 2,
        "monitor_after_top_rows": 1,
    }.get(_text(row.get("next_review_lane")), 0)
    return (
        lane_weight,
        _int(row.get("locked_cv_rank_abs_error")),
        _int(row.get("operator_receipt_blocked_payload_count")) + _int(row.get("operator_receipt_missing_payload_count")),
        1 if _bool(row.get("leave_one_out_leverage")) else 0,
        _text(row.get("target_id")),
    )


def build_refine_tier_public_benchmark_residual_evidence_triage_packet(
    *,
    payload_priority_json: str | Path = DEFAULT_PAYLOAD_PRIORITY_JSON,
    feature_extrapolation_json: str | Path = DEFAULT_FEATURE_EXTRAPOLATION_JSON,
    model_extension_json: str | Path = DEFAULT_MODEL_EXTENSION_JSON,
    seeded_backfill_json: str | Path = DEFAULT_SEEDED_BACKFILL_JSON,
    root: str | Path = ROOT,
    top_n: int = 12,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    priority_payload, priority_present = _read_json(payload_priority_json, root=root_path)
    feature_payload, feature_present = _read_json(feature_extrapolation_json, root=root_path)
    model_payload, model_present = _read_json(model_extension_json, root=root_path)
    seeded_backfill_payload, seeded_backfill_present = _read_json(seeded_backfill_json, root=root_path)
    priority_summary = priority_payload.get("summary") if isinstance(priority_payload.get("summary"), dict) else {}
    feature_summary = feature_payload.get("summary") if isinstance(feature_payload.get("summary"), dict) else {}
    model_summary = model_payload.get("summary") if isinstance(model_payload.get("summary"), dict) else {}
    payload_rows = _rows(priority_payload, "priority_rows")
    feature_rows = _rows(feature_payload, "feature_extrapolation_rows")
    seeded_backfill_rows = _rows(seeded_backfill_payload, "backfill_template_rows")
    feature_by_key = _index_rows(feature_rows)
    payload_by_key = _group_rows(payload_rows)
    seeded_backfill_by_key = _group_backfill_rows(seeded_backfill_rows)

    triage_rows: list[dict[str, Any]] = []
    for key, grouped in payload_by_key.items():
        feature = feature_by_key.get(key, {})
        first = sorted(grouped, key=lambda row: _int(row.get("payload_priority_rank")))[0]
        gaps = _gap_counter(grouped)
        cv_worse = _text(first.get("cv_rank_error_vs_baseline")) == "worse" or _text(
            feature.get("cv_rank_error_vs_baseline")
        ) == "worse"
        leverage = any(_bool(row.get("leave_one_out_leverage")) for row in grouped) or _bool(
            feature.get("leave_one_out_leverage")
        )
        feature_class = _text(feature.get("feature_extrapolation_residual_class"))
        next_lane, next_step = _next_lane(
            feature_class=feature_class,
            gaps=gaps,
            cv_worse=cv_worse,
            leverage=leverage,
        )
        seeded_backfill = _seeded_backfill_summary(seeded_backfill_by_key.get(key, []))
        if next_lane == "seeded_payload_receipt_coverage_first" and seeded_backfill["seeded_backfill_template_ready"]:
            next_step = (
                "Review the generated seeded-payload backfill template rows, then extend canonical receipt coverage "
                "through a separate approved procedure."
            )
        row = {
            "triage_priority_rank": 0,
            "target_id": key[0],
            "pose_id": key[1],
            "work_order_id": _text(first.get("work_order_id")),
            "split": _text(first.get("split")) or _text(feature.get("split")),
            "next_review_lane": next_lane,
            "next_science_step": next_step,
            "feature_extrapolation_residual_class": feature_class,
            "feature_extrapolation": _bool(feature.get("feature_extrapolation")),
            "top_feature_shift_name": _text(feature.get("top_feature_shift_name")),
            "top_feature_shift_abs_z": _text(feature.get("top_feature_shift_abs_z")),
            "outside_train_range_features": _text(feature.get("outside_train_range_features")),
            "locked_cv_rank_abs_error": _text(feature.get("locked_cv_rank_abs_error"))
            or _text(first.get("locked_cv_rank_abs_error")),
            "baseline_rank_abs_error": _text(feature.get("baseline_rank_abs_error"))
            or _text(first.get("baseline_rank_abs_error")),
            "cv_rank_error_vs_baseline": "worse" if cv_worse else _text(first.get("cv_rank_error_vs_baseline")),
            "leave_one_out_leverage": leverage,
            "leave_one_out_bootstrap_p05_delta": _text(first.get("leave_one_out_bootstrap_p05_delta")),
            "metric_payload_priority_row_count": len(grouped),
            "first_payload_priority_rank": _priority_rank(grouped),
            "required_metric_names": _metric_names(grouped),
            "operator_gap_classes": ";".join(f"{gap}:{count}" for gap, count in sorted(gaps.items())),
            "operator_receipt_blocked_payload_count": gaps.get("operator_receipt_blocked_placeholders", 0),
            "operator_receipt_missing_payload_count": sum(
                count for gap, count in gaps.items() if "missing" in gap or "without_operator_receipt" in gap
            ),
            "existing_metric_source_artifact_present_without_receipt_count": gaps.get(
                "existing_metric_payload_present_without_operator_receipt", 0
            ),
            "candidate_value_present_payload_artifact_missing_count": gaps.get(
                "candidate_value_present_payload_artifact_missing", 0
            ),
            "operator_manual_pending_field_count": sum(
                _int(row.get("operator_manual_pending_field_count")) for row in grouped
            ),
            "model_extension_generalization_ready": bool(
                model_summary.get("model_extension_generalization_ready", False)
            ),
            "best_extension_model_id": _text(model_summary.get("best_extension_model_id")),
            "best_extension_bootstrap_p05_delta_from_locked_cv": _format_float(
                _float(model_summary.get("best_extension_bootstrap_p05_delta_from_locked_cv"))
            ),
            **seeded_backfill,
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
        }
        triage_rows.append(row)

    sorted_rows = sorted(triage_rows, key=_sort_key, reverse=True)
    if top_n > 0:
        sorted_rows = sorted_rows[:top_n]
    for index, row in enumerate(sorted_rows, start=1):
        row["triage_priority_rank"] = index

    lane_counts = Counter(_text(row.get("next_review_lane")) for row in sorted_rows)
    top_row = sorted_rows[0] if sorted_rows else {}
    summary = {
        "packet_type": "refine_tier_public_benchmark_residual_evidence_triage_packet",
        "status": (
            "refine_tier_public_benchmark_residual_evidence_triage_packet_ready"
            if priority_present and feature_present and model_present and sorted_rows
            else "blocked_refine_tier_public_benchmark_residual_evidence_triage_packet"
        ),
        "payload_priority_json": _display(payload_priority_json, root=root_path),
        "payload_priority_json_present": priority_present,
        "feature_extrapolation_json": _display(feature_extrapolation_json, root=root_path),
        "feature_extrapolation_json_present": feature_present,
        "model_extension_json": _display(model_extension_json, root=root_path),
        "model_extension_json_present": model_present,
        "seeded_backfill_json": _display(seeded_backfill_json, root=root_path),
        "seeded_backfill_json_present": seeded_backfill_present,
        "locked_cv_model_id": priority_summary.get("locked_cv_model_id") or feature_summary.get("locked_cv_model_id"),
        "locked_cv_bootstrap_p05": priority_summary.get("locked_cv_bootstrap_p05")
        or feature_summary.get("locked_cv_bootstrap_p05"),
        "locked_cv_bootstrap_p05_gap_to_claim_grade": priority_summary.get("locked_cv_bootstrap_p05_gap_to_claim_grade")
        or feature_summary.get("locked_cv_bootstrap_p05_gap_to_claim_grade"),
        "model_extension_generalization_ready": bool(model_summary.get("model_extension_generalization_ready", False)),
        "best_extension_model_id": model_summary.get("best_extension_model_id", ""),
        "best_extension_bootstrap_p05_delta_from_locked_cv": model_summary.get(
            "best_extension_bootstrap_p05_delta_from_locked_cv"
        ),
        "payload_priority_row_count": len(payload_rows),
        "triage_row_count": len(sorted_rows),
        "in_distribution_high_error_triage_count": lane_counts.get("metric_payload_pose_model_form_review", 0),
        "feature_extrapolation_high_error_triage_count": lane_counts.get(
            "descriptor_coverage_target_heldout_evidence", 0
        ),
        "seeded_payload_receipt_gap_triage_count": lane_counts.get("seeded_payload_receipt_coverage_first", 0),
        "seeded_backfill_template_ready_triage_count": sum(
            1 for row in sorted_rows if bool(row.get("seeded_backfill_template_ready"))
        ),
        "seeded_backfill_template_ready_payload_count": sum(
            _int(row.get("seeded_backfill_template_row_count"))
            for row in sorted_rows
            if bool(row.get("seeded_backfill_template_ready"))
        ),
        "seeded_backfill_operator_manual_pending_field_count": sum(
            _int(row.get("seeded_backfill_operator_manual_pending_field_count")) for row in sorted_rows
        ),
        "cv_regression_payload_review_count": lane_counts.get("cv_regression_payload_review", 0),
        "blocked_receipt_fill_count": lane_counts.get("blocked_receipt_fill", 0),
        "operator_receipt_blocked_payload_count": sum(
            _int(row.get("operator_receipt_blocked_payload_count")) for row in sorted_rows
        ),
        "operator_receipt_missing_payload_count": sum(
            _int(row.get("operator_receipt_missing_payload_count")) for row in sorted_rows
        ),
        "existing_metric_source_artifact_present_without_receipt_count": sum(
            _int(row.get("existing_metric_source_artifact_present_without_receipt_count")) for row in sorted_rows
        ),
        "operator_manual_pending_field_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in sorted_rows
        ),
        "top_triage_target_id": top_row.get("target_id", ""),
        "top_triage_pose_id": top_row.get("pose_id", ""),
        "top_triage_review_lane": top_row.get("next_review_lane", ""),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this target/pose triage to close the highest-leverage R9 evidence lanes: review in-distribution "
            "metric payload and pose/model-form rows first, add seeded-payload receipt coverage where JSON already "
            "exists, and add descriptor coverage for feature-extrapolation rows before rerunning CV/bootstrap gates."
        ),
    }
    return {"summary": summary, "triage_rows": sorted_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Residual Evidence Triage Packet",
        "",
        f"- status: `{s['status']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_bootstrap_p05: `{s['locked_cv_bootstrap_p05']}`",
        f"- locked_cv_bootstrap_p05_gap_to_claim_grade: `{s['locked_cv_bootstrap_p05_gap_to_claim_grade']}`",
        f"- model_extension_generalization_ready: `{s['model_extension_generalization_ready']}`",
        f"- triage_row_count: `{s['triage_row_count']}`",
        f"- in_distribution_high_error_triage_count: `{s['in_distribution_high_error_triage_count']}`",
        f"- feature_extrapolation_high_error_triage_count: `{s['feature_extrapolation_high_error_triage_count']}`",
        f"- seeded_payload_receipt_gap_triage_count: `{s['seeded_payload_receipt_gap_triage_count']}`",
        f"- seeded_backfill_template_ready_triage_count: `{s['seeded_backfill_template_ready_triage_count']}`",
        f"- seeded_backfill_template_ready_payload_count: `{s['seeded_backfill_template_ready_payload_count']}`",
        f"- seeded_backfill_operator_manual_pending_field_count: `{s['seeded_backfill_operator_manual_pending_field_count']}`",
        f"- operator_receipt_blocked_payload_count: `{s['operator_receipt_blocked_payload_count']}`",
        f"- operator_receipt_missing_payload_count: `{s['operator_receipt_missing_payload_count']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Top Triage Rows",
        "",
        "| rank | target | pose | lane | residual class | cv err | p05 delta if removed | payload gaps | next |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["triage_rows"]:
        lines.append(
            f"| `{row['triage_priority_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['next_review_lane']}` | `{row['feature_extrapolation_residual_class']}` | "
            f"`{row['locked_cv_rank_abs_error']}` | `{row['leave_one_out_bootstrap_p05_delta']}` | "
            f"`{row['operator_gap_classes']}` | {row['next_science_step']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 residual evidence triage packet.")
    parser.add_argument("--payload-priority-json", default=DEFAULT_PAYLOAD_PRIORITY_JSON)
    parser.add_argument("--feature-extrapolation-json", default=DEFAULT_FEATURE_EXTRAPOLATION_JSON)
    parser.add_argument("--model-extension-json", default=DEFAULT_MODEL_EXTENSION_JSON)
    parser.add_argument("--seeded-backfill-json", default=DEFAULT_SEEDED_BACKFILL_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_residual_evidence_triage_packet(
        payload_priority_json=args.payload_priority_json,
        feature_extrapolation_json=args.feature_extrapolation_json,
        model_extension_json=args.model_extension_json,
        seeded_backfill_json=args.seeded_backfill_json,
        root=root,
        top_n=args.top_n,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["triage_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
