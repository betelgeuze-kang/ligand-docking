#!/usr/bin/env python3
"""Read-only R9 target-pose residual review dossier."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRIAGE_JSON = "config/refine_tier_public_benchmark_residual_evidence_triage_packet_current.json"
DEFAULT_PAYLOAD_PRIORITY_JSON = (
    "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
)
DEFAULT_FEATURE_EXTRAPOLATION_JSON = (
    "config/refine_tier_public_benchmark_cv_feature_extrapolation_probe_current.json"
)
DEFAULT_SEEDED_BACKFILL_JSON = (
    "config/refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_current.json"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_residual_review_dossier_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_residual_review_dossier_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_residual_review_dossier_current.md"

CLAIM_BOUNDARY = (
    "R9 residual review dossier only joins existing triage, metric-payload priority, "
    "feature-extrapolation, and seeded-backfill artifacts into target-pose review packages. "
    "It does not compute metrics, write metric payload JSON, approve receipts, promote canonical "
    "intake, change production scoring, run docking/MD, download, upload, email, delete, commit, "
    "push, or mutate external state."
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


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")))


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _key(row)
        if key[0] and key[1]:
            grouped[key].append(row)
    return dict(grouped)


def _index_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _key(row)
        if key[0] and key[1]:
            indexed[key] = row
    return indexed


def _unique_join(values: list[Any]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return ";".join(out)


def _artifact_present(path_text: str, *, root: Path) -> bool:
    if not path_text:
        return False
    if "::" in path_text:
        archive, member = path_text.split("::", 1)
        return bool(member.strip()) and _resolve(archive.strip(), root=root).is_file()
    return _resolve(path_text, root=root).exists()


def _required_artifact_summary(priority_rows: list[dict[str, Any]], *, root: Path) -> dict[str, Any]:
    artifacts: list[str] = []
    hashes: list[str] = []
    for row in priority_rows:
        artifacts.extend(_split_semicolon(row.get("required_metric_input_artifacts")))
        hashes.extend(_split_semicolon(row.get("required_metric_input_artifact_sha256s")))
    unique_artifacts = sorted(set(artifacts))
    unique_hashes = sorted(set(hashes))
    return {
        "required_input_artifact_count": len(unique_artifacts),
        "required_input_artifact_present_count": sum(
            1 for artifact in unique_artifacts if _artifact_present(artifact, root=root)
        ),
        "required_input_artifact_sha256_count": len(unique_hashes),
        "required_input_artifact_sha256_list_complete": bool(unique_artifacts)
        and len(unique_hashes) >= len(unique_artifacts),
        "required_input_artifacts": ";".join(unique_artifacts),
    }


def _feature_diagnostics_brief(feature_row: dict[str, Any]) -> str:
    raw = _text(feature_row.get("feature_diagnostics_json"))
    if not raw:
        return ""
    try:
        diagnostics = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if not isinstance(diagnostics, list):
        return ""
    parts: list[str] = []
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        feature = _text(item.get("feature"))
        z_score = _text(item.get("z_score"))
        outside = _bool(item.get("outside_train_range"))
        range_gap = _text(item.get("range_gap"))
        if feature:
            parts.append(f"{feature}:z={z_score}:outside={outside}:gap={range_gap}")
    return ";".join(parts)


def _backfill_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_count = len(rows)
    valid_count = sum(1 for row in rows if _text(row.get("payload_validation_status")) == "pass")
    verified_count = sum(
        1
        for row in rows
        if _int(row.get("input_artifact_count"))
        and _int(row.get("input_artifact_count")) == _int(row.get("input_artifact_sha256_verified_count"))
    )
    return {
        "seeded_backfill_template_row_count": row_count,
        "seeded_backfill_payload_schema_valid_count": valid_count,
        "seeded_backfill_input_sha256_verified_count": verified_count,
        "seeded_backfill_operator_manual_pending_field_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in rows
        ),
        "seeded_backfill_template_ready": bool(row_count and valid_count == row_count and verified_count == row_count),
    }


def _review_action(triage_row: dict[str, Any], backfill: dict[str, Any]) -> str:
    lane = _text(triage_row.get("next_review_lane"))
    if lane == "metric_payload_pose_model_form_review":
        return (
            "Review DockQ/lDDT-PLI/internal_deltaG values, methods, input hashes, pose assignment, "
            "and model-form assumptions before changing calibration."
        )
    if lane == "descriptor_coverage_target_heldout_evidence":
        return (
            "Review descriptor range diagnostics and add target-held-out evidence near the out-of-range "
            "feature before stronger calibration terms."
        )
    if lane == "seeded_payload_receipt_coverage_first" and backfill.get("seeded_backfill_template_ready"):
        return (
            "Review the generated seeded-payload backfill template rows, then extend canonical receipt "
            "coverage through a separate approved procedure."
        )
    if lane == "seeded_payload_receipt_coverage_first":
        return "Create a seeded-payload receipt backfill surface before treating local metric JSON as reviewed."
    return _text(triage_row.get("next_science_step"))


def build_refine_tier_public_benchmark_residual_review_dossier(
    *,
    triage_json: str | Path = DEFAULT_TRIAGE_JSON,
    payload_priority_json: str | Path = DEFAULT_PAYLOAD_PRIORITY_JSON,
    feature_extrapolation_json: str | Path = DEFAULT_FEATURE_EXTRAPOLATION_JSON,
    seeded_backfill_json: str | Path = DEFAULT_SEEDED_BACKFILL_JSON,
    root: str | Path = ROOT,
    top_n: int = 6,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    triage_payload, triage_present = _read_json(triage_json, root=root_path)
    priority_payload, priority_present = _read_json(payload_priority_json, root=root_path)
    feature_payload, feature_present = _read_json(feature_extrapolation_json, root=root_path)
    backfill_payload, backfill_present = _read_json(seeded_backfill_json, root=root_path)
    triage_rows = _rows(triage_payload, "triage_rows")
    priority_rows = _rows(priority_payload, "priority_rows")
    feature_rows = _rows(feature_payload, "feature_extrapolation_rows")
    backfill_rows = _rows(backfill_payload, "backfill_template_rows")
    priority_by_key = _group_rows(priority_rows)
    feature_by_key = _index_rows(feature_rows)
    backfill_by_key = _group_rows(backfill_rows)

    selected_triage_rows = sorted(triage_rows, key=lambda row: _int(row.get("triage_priority_rank")))
    if top_n > 0:
        selected_triage_rows = selected_triage_rows[:top_n]

    dossier_rows: list[dict[str, Any]] = []
    for index, triage_row in enumerate(selected_triage_rows, start=1):
        key = _key(triage_row)
        grouped_priority = sorted(
            priority_by_key.get(key, []), key=lambda row: _int(row.get("payload_priority_rank"))
        )
        feature_row = feature_by_key.get(key, {})
        backfill = _backfill_summary(backfill_by_key.get(key, []))
        artifact_summary = _required_artifact_summary(grouped_priority, root=root_path)
        metric_count = len(grouped_priority)
        operator_surface_ready_count = sum(1 for row in grouped_priority if _bool(row.get("operator_review_surface_ready")))
        source_artifact_present_count = sum(1 for row in grouped_priority if _bool(row.get("metric_source_artifact_present")))
        candidate_value_count = sum(1 for row in grouped_priority if _text(row.get("metric_value_candidate")))
        existing_value_count = sum(1 for row in grouped_priority if _text(row.get("existing_metric_value")))
        gap_counts = Counter(_text(row.get("operator_gap_class")) or "unknown" for row in grouped_priority)
        lane = _text(triage_row.get("next_review_lane"))
        review_package_ready = (
            bool(metric_count)
            and artifact_summary["required_input_artifact_sha256_list_complete"]
            and artifact_summary["required_input_artifact_present_count"]
            == artifact_summary["required_input_artifact_count"]
            and (
                operator_surface_ready_count == metric_count
                or (lane == "seeded_payload_receipt_coverage_first" and backfill["seeded_backfill_template_ready"])
            )
        )
        row = {
            "dossier_rank": index,
            "target_id": key[0],
            "pose_id": key[1],
            "work_order_id": _text(triage_row.get("work_order_id")),
            "split": _text(triage_row.get("split")),
            "next_review_lane": lane,
            "review_package_ready": review_package_ready,
            "next_reviewer_action": _review_action(triage_row, backfill),
            "feature_extrapolation_residual_class": _text(triage_row.get("feature_extrapolation_residual_class")),
            "feature_extrapolation": _bool(triage_row.get("feature_extrapolation")),
            "outside_train_range_features": _text(triage_row.get("outside_train_range_features")),
            "top_feature_shift_name": _text(triage_row.get("top_feature_shift_name")),
            "top_feature_shift_abs_z": _text(triage_row.get("top_feature_shift_abs_z")),
            "feature_diagnostics_brief": _feature_diagnostics_brief(feature_row),
            "locked_cv_rank_abs_error": _text(triage_row.get("locked_cv_rank_abs_error")),
            "baseline_rank_abs_error": _text(triage_row.get("baseline_rank_abs_error")),
            "cv_rank_error_vs_baseline": _text(triage_row.get("cv_rank_error_vs_baseline")),
            "leave_one_out_bootstrap_p05_delta": _text(triage_row.get("leave_one_out_bootstrap_p05_delta")),
            "leave_one_out_leverage": _bool(triage_row.get("leave_one_out_leverage")),
            "rank_direction": _text(feature_row.get("rank_direction"))
            or _unique_join([row.get("rank_direction") for row in grouped_priority]),
            "required_metric_names": _text(triage_row.get("required_metric_names"))
            or _unique_join([row.get("metric_name") for row in grouped_priority]),
            "metric_payload_priority_row_count": metric_count,
            "payload_priority_ranks": ";".join(
                _text(row.get("payload_priority_rank")) for row in grouped_priority if _text(row.get("payload_priority_rank"))
            ),
            "metric_source_artifacts": _unique_join([row.get("metric_source_artifact") for row in grouped_priority]),
            "metric_source_artifact_present_count": source_artifact_present_count,
            "candidate_metric_value_count": candidate_value_count,
            "existing_metric_value_count": existing_value_count,
            "operator_review_surface_ready_payload_count": operator_surface_ready_count,
            "operator_gap_classes": ";".join(f"{gap}:{count}" for gap, count in sorted(gap_counts.items())),
            "operator_receipt_blocked_payload_count": _int(triage_row.get("operator_receipt_blocked_payload_count")),
            "operator_receipt_missing_payload_count": _int(triage_row.get("operator_receipt_missing_payload_count")),
            "operator_manual_pending_field_count": _int(triage_row.get("operator_manual_pending_field_count")),
            **artifact_summary,
            **backfill,
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
        }
        dossier_rows.append(row)

    lane_counts = Counter(_text(row.get("next_review_lane")) for row in dossier_rows)
    top_row = dossier_rows[0] if dossier_rows else {}
    summary = {
        "packet_type": "refine_tier_public_benchmark_residual_review_dossier",
        "status": (
            "refine_tier_public_benchmark_residual_review_dossier_ready"
            if triage_present and priority_present and feature_present and dossier_rows
            else "blocked_refine_tier_public_benchmark_residual_review_dossier"
        ),
        "triage_json": _display(triage_json, root=root_path),
        "triage_json_present": triage_present,
        "payload_priority_json": _display(payload_priority_json, root=root_path),
        "payload_priority_json_present": priority_present,
        "feature_extrapolation_json": _display(feature_extrapolation_json, root=root_path),
        "feature_extrapolation_json_present": feature_present,
        "seeded_backfill_json": _display(seeded_backfill_json, root=root_path),
        "seeded_backfill_json_present": backfill_present,
        "dossier_row_count": len(dossier_rows),
        "review_package_ready_count": sum(1 for row in dossier_rows if bool(row.get("review_package_ready"))),
        "metric_payload_pose_model_review_count": lane_counts.get("metric_payload_pose_model_form_review", 0),
        "descriptor_coverage_target_heldout_review_count": lane_counts.get(
            "descriptor_coverage_target_heldout_evidence", 0
        ),
        "seeded_backfill_review_count": lane_counts.get("seeded_payload_receipt_coverage_first", 0),
        "seeded_backfill_template_ready_review_count": sum(
            1 for row in dossier_rows if bool(row.get("seeded_backfill_template_ready"))
        ),
        "metric_payload_priority_row_count": sum(_int(row.get("metric_payload_priority_row_count")) for row in dossier_rows),
        "operator_receipt_blocked_payload_count": sum(
            _int(row.get("operator_receipt_blocked_payload_count")) for row in dossier_rows
        ),
        "operator_receipt_missing_payload_count": sum(
            _int(row.get("operator_receipt_missing_payload_count")) for row in dossier_rows
        ),
        "operator_manual_pending_field_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in dossier_rows
        ),
        "seeded_backfill_operator_manual_pending_field_count": sum(
            _int(row.get("seeded_backfill_operator_manual_pending_field_count")) for row in dossier_rows
        ),
        "required_input_artifact_present_count": sum(
            _int(row.get("required_input_artifact_present_count")) for row in dossier_rows
        ),
        "required_input_artifact_count": sum(_int(row.get("required_input_artifact_count")) for row in dossier_rows),
        "top_review_target_id": top_row.get("target_id", ""),
        "top_review_pose_id": top_row.get("pose_id", ""),
        "top_review_lane": top_row.get("next_review_lane", ""),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use these target-pose dossiers as the immediate R9 science-review queue: top metric/pose/model-form "
            "review first, feature-extrapolation coverage second, and seeded backfill template review third."
        ),
    }
    return {"summary": summary, "dossier_rows": dossier_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Residual Review Dossier",
        "",
        f"- status: `{s['status']}`",
        f"- dossier_row_count: `{s['dossier_row_count']}`",
        f"- review_package_ready_count: `{s['review_package_ready_count']}`",
        f"- metric_payload_pose_model_review_count: `{s['metric_payload_pose_model_review_count']}`",
        f"- descriptor_coverage_target_heldout_review_count: `{s['descriptor_coverage_target_heldout_review_count']}`",
        f"- seeded_backfill_review_count: `{s['seeded_backfill_review_count']}`",
        f"- seeded_backfill_template_ready_review_count: `{s['seeded_backfill_template_ready_review_count']}`",
        f"- operator_receipt_blocked_payload_count: `{s['operator_receipt_blocked_payload_count']}`",
        f"- operator_receipt_missing_payload_count: `{s['operator_receipt_missing_payload_count']}`",
        f"- seeded_backfill_operator_manual_pending_field_count: `{s['seeded_backfill_operator_manual_pending_field_count']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Target-Pose Dossiers",
        "",
        "| rank | target | pose | lane | package ready | residual class | metric rows | artifacts present | next action |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["dossier_rows"]:
        lines.append(
            f"| `{row['dossier_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['next_review_lane']}` | `{row['review_package_ready']}` | "
            f"`{row['feature_extrapolation_residual_class']}` | `{row['metric_payload_priority_row_count']}` | "
            f"`{row['required_input_artifact_present_count']}/{row['required_input_artifact_count']}` | "
            f"{row['next_reviewer_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 residual review dossier.")
    parser.add_argument("--triage-json", default=DEFAULT_TRIAGE_JSON)
    parser.add_argument("--payload-priority-json", default=DEFAULT_PAYLOAD_PRIORITY_JSON)
    parser.add_argument("--feature-extrapolation-json", default=DEFAULT_FEATURE_EXTRAPOLATION_JSON)
    parser.add_argument("--seeded-backfill-json", default=DEFAULT_SEEDED_BACKFILL_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--top-n", type=int, default=6)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_residual_review_dossier(
        triage_json=args.triage_json,
        payload_priority_json=args.payload_priority_json,
        feature_extrapolation_json=args.feature_extrapolation_json,
        seeded_backfill_json=args.seeded_backfill_json,
        root=root,
        top_n=args.top_n,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["dossier_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
