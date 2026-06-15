#!/usr/bin/env python3
"""Triage R9 bootstrap-driver worksheet fields into machine-supported and operator-only lanes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply import (
    DEFAULT_OUT_JSON as DEFAULT_STAGING_APPLY_JSON,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_current.json"
DEFAULT_OUT_CSV = "config/refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_current.md"

MACHINE_SUPPORTED_REVIEW_FIELDS = [
    "metric_value_reviewed",
    "method_reviewed",
    "input_artifacts_reviewed",
    "input_artifact_sha256s_reviewed",
    "expected_metric_source_artifact_reviewed",
    "payload_schema_reviewed",
]
OPERATOR_ONLY_FIELDS = [
    "operator_decision",
    "license_ok_reviewed",
    "operator_id",
    "reviewed_at_utc",
    "approval_token",
]

CLAIM_BOUNDARY = (
    "R9 bootstrap-driver operator field triage only classifies pending worksheet fields by whether "
    "current local evidence already supports an operator review confirmation or whether explicit "
    "operator/legal/approval attestation is still required. It does not mark fields reviewed, write "
    "metric payload JSON, copy canonical receipts, promote canonical intake, change production scoring, "
    "run docking/MD, download, upload, email, delete, commit, push, or mutate external state."
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


def _float_valid(value: Any) -> bool:
    try:
        float(_text(value))
    except (TypeError, ValueError):
        return False
    return True


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _machine_support_map(row: dict[str, Any]) -> dict[str, bool]:
    review_surface = _text(row.get("review_surface"))
    metric_source_state_consistent = (
        review_surface == "candidate_preview_payload_write_review"
        and _bool(row.get("expected_metric_source_artifact_present")) is False
    ) or (
        review_surface == "existing_payload_backfill_receipt_review"
        and _bool(row.get("expected_metric_source_artifact_present")) is True
    )
    payload_schema_supported = (
        review_surface == "candidate_preview_payload_write_review"
        and _float_valid(row.get("metric_value_under_review"))
        and bool(_text(row.get("method_under_review")))
        and _bool(row.get("input_artifact_sha256_verified")) is True
    ) or (
        review_surface == "existing_payload_backfill_receipt_review"
        and _bool(row.get("existing_payload_schema_revalidated")) is True
    )
    return {
        "metric_value_reviewed": _float_valid(row.get("metric_value_under_review")),
        "method_reviewed": bool(_text(row.get("method_under_review"))),
        "input_artifacts_reviewed": _bool(row.get("input_artifact_sha256_verified")) is True,
        "input_artifact_sha256s_reviewed": _bool(row.get("input_artifact_sha256_verified")) is True,
        "expected_metric_source_artifact_reviewed": metric_source_state_consistent,
        "payload_schema_reviewed": payload_schema_supported,
    }


def _triage_row(row: dict[str, Any]) -> dict[str, Any]:
    pending_fields = _split_semicolon(row.get("operator_manual_pending_fields"))
    machine_support = _machine_support_map(row)
    machine_supported_pending = [
        field for field in MACHINE_SUPPORTED_REVIEW_FIELDS if field in pending_fields and machine_support.get(field)
    ]
    machine_gap_pending = [
        field for field in MACHINE_SUPPORTED_REVIEW_FIELDS if field in pending_fields and not machine_support.get(field)
    ]
    operator_only_pending = [field for field in OPERATOR_ONLY_FIELDS if field in pending_fields]
    unclassified_pending = [
        field
        for field in pending_fields
        if field not in MACHINE_SUPPORTED_REVIEW_FIELDS and field not in OPERATOR_ONLY_FIELDS
    ]
    return {
        "worksheet_id": _text(row.get("worksheet_id")),
        "target_id": _text(row.get("target_id")),
        "pose_id": _text(row.get("pose_id")),
        "work_order_id": _text(row.get("work_order_id")),
        "split": _text(row.get("split")),
        "metric_name": _text(row.get("metric_name")),
        "review_surface": _text(row.get("review_surface")),
        "source_row_status": _text(row.get("row_status")),
        "source_blockers": _text(row.get("blockers")),
        "manual_pending_field_count": len(pending_fields),
        "machine_supported_pending_field_count": len(machine_supported_pending),
        "machine_supported_pending_fields": ";".join(machine_supported_pending),
        "machine_gap_pending_field_count": len(machine_gap_pending),
        "machine_gap_pending_fields": ";".join(machine_gap_pending),
        "operator_only_pending_field_count": len(operator_only_pending),
        "operator_only_pending_fields": ";".join(operator_only_pending),
        "unclassified_pending_field_count": len(unclassified_pending),
        "unclassified_pending_fields": ";".join(unclassified_pending),
        "metric_value_numeric": machine_support["metric_value_reviewed"],
        "method_present": machine_support["method_reviewed"],
        "input_artifact_sha256_verified": machine_support["input_artifact_sha256s_reviewed"],
        "metric_source_artifact_state_consistent": machine_support["expected_metric_source_artifact_reviewed"],
        "payload_schema_support_ready": machine_support["payload_schema_reviewed"],
        "license_requires_operator_review": "license_ok_reviewed" in operator_only_pending,
        "approval_token_required": APPROVAL_TOKEN,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage(
    *,
    staging_apply_json: str | Path = DEFAULT_STAGING_APPLY_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    staging_payload, staging_present = _read_json(staging_apply_json, root=root_path)
    staging_summary = staging_payload.get("summary") if isinstance(staging_payload.get("summary"), dict) else {}
    source_rows = [
        dict(row) for row in staging_payload.get("rows", []) if isinstance(row, dict)
    ] if isinstance(staging_payload.get("rows"), list) else []
    rows = [_triage_row(row) for row in source_rows]

    blockers: list[str] = []
    if not staging_present:
        blockers.append("staging_apply_json_missing")
    if not source_rows:
        blockers.append("staging_apply_rows_missing")
    if any(_int(row.get("machine_gap_pending_field_count")) for row in rows):
        blockers.append("machine_supported_review_field_evidence_gaps_present")
    if any(_int(row.get("unclassified_pending_field_count")) for row in rows):
        blockers.append("unclassified_pending_fields_present")

    machine_supported_count = sum(_int(row.get("machine_supported_pending_field_count")) for row in rows)
    operator_only_count = sum(_int(row.get("operator_only_pending_field_count")) for row in rows)
    machine_gap_count = sum(_int(row.get("machine_gap_pending_field_count")) for row in rows)
    unclassified_count = sum(_int(row.get("unclassified_pending_field_count")) for row in rows)
    manual_count = sum(_int(row.get("manual_pending_field_count")) for row in rows)
    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_operator_field_triage",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_ready"
            if staging_present and source_rows and not blockers
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage"
        ),
        "staging_apply_json": _display(staging_apply_json, root=root_path),
        "staging_apply_json_present": staging_present,
        "staging_apply_status": _text(staging_summary.get("status")),
        "staging_apply_blocked_row_count": _int(staging_summary.get("blocked_row_count")),
        "staging_apply_pass_row_count": _int(staging_summary.get("pass_row_count")),
        "row_count": len(rows),
        "candidate_preview_row_count": sum(
            1 for row in rows if row.get("review_surface") == "candidate_preview_payload_write_review"
        ),
        "existing_payload_backfill_row_count": sum(
            1 for row in rows if row.get("review_surface") == "existing_payload_backfill_receipt_review"
        ),
        "manual_pending_field_count": manual_count,
        "machine_supported_pending_field_count": machine_supported_count,
        "operator_only_pending_field_count": operator_only_count,
        "machine_gap_pending_field_count": machine_gap_count,
        "unclassified_pending_field_count": unclassified_count,
        "machine_supported_field_ratio": (
            round(machine_supported_count / manual_count, 6) if manual_count else 0.0
        ),
        "operator_only_field_ratio": round(operator_only_count / manual_count, 6) if manual_count else 0.0,
        "input_artifact_sha256_verified_row_count": sum(
            1 for row in rows if row.get("input_artifact_sha256_verified") is True
        ),
        "metric_source_artifact_state_consistent_row_count": sum(
            1 for row in rows if row.get("metric_source_artifact_state_consistent") is True
        ),
        "payload_schema_support_ready_row_count": sum(
            1 for row in rows if row.get("payload_schema_support_ready") is True
        ),
        "license_requires_operator_review_row_count": sum(
            1 for row in rows if row.get("license_requires_operator_review") is True
        ),
        "approval_token_required": APPROVAL_TOKEN,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Machine-supported review fields have current local evidence, but they remain unreviewed until "
            "an operator records decisions, license review, operator identity, timestamp, and approval token; "
            "then rerun the staging apply preview before any payload or receipt write."
        ),
    }
    return {
        "summary": summary,
        "rows": rows,
        "machine_supported_review_fields": MACHINE_SUPPORTED_REVIEW_FIELDS,
        "operator_only_fields": OPERATOR_ONLY_FIELDS,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Operator Field Triage",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- manual_pending_field_count: `{s['manual_pending_field_count']}`",
        f"- machine_supported_pending_field_count: `{s['machine_supported_pending_field_count']}`",
        f"- operator_only_pending_field_count: `{s['operator_only_pending_field_count']}`",
        f"- machine_gap_pending_field_count: `{s['machine_gap_pending_field_count']}`",
        f"- input_artifact_sha256_verified_row_count: `{s['input_artifact_sha256_verified_row_count']}`",
        f"- payload_schema_support_ready_row_count: `{s['payload_schema_support_ready_row_count']}`",
        f"- license_requires_operator_review_row_count: `{s['license_requires_operator_review_row_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Rows",
        "",
        "| worksheet | target | pose | metric | machine-supported | operator-only | machine gaps |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['worksheet_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['machine_supported_pending_field_count']}` | "
            f"`{row['operator_only_pending_field_count']}` | `{row['machine_gap_pending_field_count']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R9 bootstrap-driver operator field triage.")
    parser.add_argument("--staging-apply-json", default=DEFAULT_STAGING_APPLY_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage(
        staging_apply_json=args.staging_apply_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
