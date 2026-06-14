#!/usr/bin/env python3
"""Build operator-fill templates for R9 statistical-support metric source payloads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness import (
    DEFAULT_OUT_JSON as DEFAULT_METRIC_MATERIALIZATION_READINESS_JSON,
    REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS,
    REQUIRED_METRIC_SOURCE_PAYLOADS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
)
DEFAULT_OUT_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.csv"
)
DEFAULT_OUT_MD = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.md"
)

CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support metric source templates only; it expands "
    "read-only metric materialization readiness rows into one operator-fill template row per planned "
    "DockQ/lDDT-PLI/internal DeltaG source payload. It does not download coordinates, run docking or "
    "MD, compute metrics, write metric payload JSON files, write canonical intake, approve receipts, "
    "promote claims, upload, email, delete, commit, push, or mutate external state."
)

PLACEHOLDER_VALUE = "OPERATOR_FILL_NUMERIC_METRIC_VALUE"
PLACEHOLDER_METHOD = "OPERATOR_FILL_METHOD_OR_TOOL"
PLACEHOLDER_OPERATOR_ID = "OPERATOR_FILL_OPERATOR_ID"
PLACEHOLDER_REVIEWED_AT_UTC = "OPERATOR_FILL_REVIEWED_AT_UTC"
PLACEHOLDER_LICENSE_OK = "OPERATOR_CONFIRM_TRUE"


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _field_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (bool, int, float)):
        return True
    return _text(value) != ""


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _metric_path(readiness_row: dict[str, Any], metric_name: str) -> str:
    key = f"{metric_name}_source_artifact"
    return _text(readiness_row.get(key))


def _template_payload(readiness_row: dict[str, Any], metric_name: str) -> dict[str, Any]:
    return {
        "metric_name": metric_name,
        "target_id": _text(readiness_row.get("target_id")),
        "pose_id": _text(readiness_row.get("pose_id")),
        "value": PLACEHOLDER_VALUE,
        "method": PLACEHOLDER_METHOD,
        "input_artifacts": _text(readiness_row.get("required_metric_input_artifacts")),
        "input_artifact_sha256s": _text(
            readiness_row.get("required_metric_input_artifact_sha256s")
        ),
        "operator_id": PLACEHOLDER_OPERATOR_ID,
        "reviewed_at_utc": PLACEHOLDER_REVIEWED_AT_UTC,
        "license_ok": PLACEHOLDER_LICENSE_OK,
        "external_engine_calls": 0,
    }


def _template_row(
    readiness_row: dict[str, Any],
    metric_name: str,
    *,
    index: int,
    root: Path,
) -> dict[str, Any]:
    payload = _template_payload(readiness_row, metric_name)
    metric_source_artifact = _metric_path(readiness_row, metric_name)
    coordinate_pass = _text(readiness_row.get("coordinate_validation_status")) == "pass"
    missing_input_count = _int(readiness_row.get("missing_required_metric_input_artifact_count"))
    existing_payload_present = bool(
        metric_source_artifact and _resolve(metric_source_artifact, root=root).is_file()
    )
    blockers: list[str] = []
    if not metric_source_artifact:
        blockers.append("metric_source_artifact_path_missing")
    if not coordinate_pass:
        blockers.append("coordinate_validation_not_pass")
    if missing_input_count:
        blockers.append("required_metric_input_artifacts_missing")
    missing_payload_fields = [
        field
        for field in REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS
        if field not in payload or not _field_present(payload[field])
    ]
    if missing_payload_fields:
        blockers.append("template_payload_required_fields_missing")
    fill_ready = bool(coordinate_pass and not missing_input_count and metric_source_artifact)
    return {
        "template_id": f"r9_statistical_support_metric_source_template_{index:03d}",
        "candidate_queue_id": _text(readiness_row.get("candidate_queue_id")),
        "expansion_slot_id": _text(readiness_row.get("expansion_slot_id")),
        "suggested_work_order_id": _text(readiness_row.get("suggested_work_order_id")),
        "target_id": _text(readiness_row.get("target_id")),
        "pose_id": _text(readiness_row.get("pose_id")),
        "required_split": _text(readiness_row.get("required_split")),
        "suggested_split": _text(readiness_row.get("suggested_split")),
        "metric_name": metric_name,
        "metric_source_artifact": metric_source_artifact,
        "template_payload_json": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        "required_metric_source_payload_fields": ";".join(REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS),
        "required_metric_source_payload_field_count": len(REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS),
        "required_metric_input_artifacts": _text(
            readiness_row.get("required_metric_input_artifacts")
        ),
        "required_metric_input_artifact_sha256s": _text(
            readiness_row.get("required_metric_input_artifact_sha256s")
        ),
        "required_metric_input_artifact_count": _int(
            readiness_row.get("required_metric_input_artifact_count")
        ),
        "present_required_metric_input_artifact_count": _int(
            readiness_row.get("present_required_metric_input_artifact_count")
        ),
        "missing_required_metric_input_artifact_count": missing_input_count,
        "coordinate_validation_status": _text(
            readiness_row.get("coordinate_validation_status")
        ),
        "metric_materialization_status": _text(
            readiness_row.get("metric_materialization_status")
        ),
        "metric_materialization_candidate_ready": _bool(
            readiness_row.get("metric_materialization_candidate_ready")
        ),
        "template_payload_required_fields_present": not missing_payload_fields,
        "existing_metric_source_payload_present": existing_payload_present,
        "metric_source_payload_fill_ready": fill_ready,
        "template_status": (
            "ready_for_operator_metric_source_payload_fill"
            if fill_ready
            else "blocked_until_coordinate_validation_passes"
        ),
        "template_blockers": ";".join(blockers),
        "value": PLACEHOLDER_VALUE,
        "method": PLACEHOLDER_METHOD,
        "operator_id": PLACEHOLDER_OPERATOR_ID,
        "reviewed_at_utc": PLACEHOLDER_REVIEWED_AT_UTC,
        "license_ok": PLACEHOLDER_LICENSE_OK,
        "external_engine_calls": 0,
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_metric_source_templates(
    *,
    metric_materialization_readiness_json: str | Path = DEFAULT_METRIC_MATERIALIZATION_READINESS_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    readiness_payload, readiness_present = _read_json(
        metric_materialization_readiness_json,
        root=root,
    )
    readiness_summary = _summary(readiness_payload)
    readiness_rows = _rows(readiness_payload)
    rows: list[dict[str, Any]] = []
    for readiness_row in readiness_rows:
        for metric_name in REQUIRED_METRIC_SOURCE_PAYLOADS:
            rows.append(_template_row(readiness_row, metric_name, index=len(rows) + 1, root=root))

    blockers: list[str] = []
    if not readiness_present:
        blockers.append("metric_materialization_readiness_missing")
    if (
        readiness_summary.get("status")
        != "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
    ):
        blockers.append("metric_materialization_readiness_not_ready")
    if not rows:
        blockers.append("metric_source_template_rows_missing")

    ready = bool(readiness_present and rows and not blockers)
    fill_ready_rows = [row for row in rows if row["metric_source_payload_fill_ready"] is True]
    blocked_rows = [row for row in rows if row["metric_source_payload_fill_ready"] is not True]
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_metric_source_templates",
        "status": (
            "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_statistical_support_metric_source_templates"
        ),
        "metric_source_templates_ready": ready,
        "metric_materialization_readiness": _display(
            metric_materialization_readiness_json,
            root=root,
        ),
        "metric_materialization_readiness_present": readiness_present,
        "metric_materialization_readiness_ready": bool(
            readiness_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
        ),
        "metric_materialization_row_count": _int(
            readiness_summary.get("metric_materialization_row_count")
        ),
        "metric_materialization_candidate_ready_count": _int(
            readiness_summary.get("metric_materialization_candidate_ready_count")
        ),
        "metric_materialization_candidate_blocked_count": _int(
            readiness_summary.get("metric_materialization_candidate_blocked_count")
        ),
        "coordinate_validation_pass_row_count": _int(
            readiness_summary.get("coordinate_validation_pass_row_count")
        ),
        "coordinate_validation_blocked_row_count": _int(
            readiness_summary.get("coordinate_validation_blocked_row_count")
        ),
        "planned_metric_source_payload_count": _int(
            readiness_summary.get("planned_metric_source_payload_count")
        ),
        "existing_metric_source_payload_count": _int(
            readiness_summary.get("existing_metric_source_payload_count")
        ),
        "template_row_count": len(rows),
        "template_candidate_row_count": len({_text(row.get("candidate_queue_id")) for row in rows}),
        "template_metric_name_count": len({_text(row.get("metric_name")) for row in rows}),
        "template_metric_source_artifact_path_row_count": sum(
            1 for row in rows if _text(row.get("metric_source_artifact"))
        ),
        "template_payload_required_fields_present_row_count": sum(
            1 for row in rows if row["template_payload_required_fields_present"] is True
        ),
        "metric_source_payload_fill_ready_row_count": len(fill_ready_rows),
        "metric_source_payload_fill_blocked_row_count": len(blocked_rows),
        "coordinate_validation_blocked_template_row_count": sum(
            1 for row in rows if row["coordinate_validation_status"] != "pass"
        ),
        "missing_required_input_template_row_count": sum(
            1 for row in rows if _int(row.get("missing_required_metric_input_artifact_count"))
        ),
        "existing_metric_source_payload_present_row_count": sum(
            1 for row in rows if row["existing_metric_source_payload_present"] is True
        ),
        "required_metric_source_payloads": ";".join(REQUIRED_METRIC_SOURCE_PAYLOADS),
        "required_metric_source_payload_count": len(REQUIRED_METRIC_SOURCE_PAYLOADS),
        "required_metric_source_payload_fields": ";".join(REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS),
        "required_metric_source_payload_field_count": len(REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS),
        "placeholder_value_count": len(rows),
        "placeholder_method_count": len(rows),
        "placeholder_operator_id_count": len(rows),
        "placeholder_reviewed_at_utc_count": len(rows),
        "placeholder_license_ok_count": len(rows),
        "external_engine_calls_total": sum(_int(row.get("external_engine_calls")) for row in rows),
        "canonical_intake_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "With coordinate fetch and validation ready, replace each operator placeholder "
            "with reviewed DockQ/lDDT-PLI/internal DeltaG values while preserving input artifact "
            "paths, hashes, license_ok=true, and external_engine_calls=0."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# R9 Statistical Support Metric Source Templates",
        "",
        f"- status: `{summary['status']}`",
        f"- template_row_count: `{summary['template_row_count']}`",
        f"- metric_source_payload_fill_ready_row_count: `{summary['metric_source_payload_fill_ready_row_count']}`",
        f"- metric_source_payload_fill_blocked_row_count: `{summary['metric_source_payload_fill_blocked_row_count']}`",
        f"- coordinate_validation_blocked_template_row_count: `{summary['coordinate_validation_blocked_template_row_count']}`",
        f"- missing_required_input_template_row_count: `{summary['missing_required_input_template_row_count']}`",
        f"- required_metric_source_payload_fields: `{summary['required_metric_source_payload_fields']}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Next Required Step",
        "",
        summary["next_required_step"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Build read-only operator-fill templates for R9 statistical-support metric sources."
    )
    parser.add_argument(
        "--metric-materialization-readiness-json",
        default=DEFAULT_METRIC_MATERIALIZATION_READINESS_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_statistical_support_metric_source_templates(
        metric_materialization_readiness_json=args.metric_materialization_readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
