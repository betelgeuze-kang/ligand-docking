#!/usr/bin/env python3
"""Read-only backfill packet for seeded R9 metric payload receipt coverage."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAYLOAD_PRIORITY_JSON = (
    "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
)
DEFAULT_OUT_JSON = (
    "config/refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_current.json"
)
DEFAULT_OUT_CSV = (
    "config/refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_template_current.csv"
)
DEFAULT_OUT_MD = (
    "docs/refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_current.md"
)

REQUIRED_PAYLOAD_FIELDS = (
    "metric_name",
    "target_id",
    "pose_id",
    "value",
    "method",
    "input_artifacts",
    "input_artifact_sha256s",
    "operator_id",
    "reviewed_at_utc",
    "license_ok",
    "external_engine_calls",
)
OPERATOR_PENDING_FIELDS = (
    "operator_decision",
    "metric_value_reviewed",
    "method_reviewed",
    "input_artifacts_reviewed",
    "input_artifact_sha256s_reviewed",
    "metric_source_artifact_reviewed",
    "payload_schema_reviewed",
    "license_ok_reviewed",
    "operator_id",
    "reviewed_at_utc",
    "approval_token",
)

CLAIM_BOUNDARY = (
    "R9 seeded metric payload receipt backfill packet only validates existing local seeded metric JSON "
    "artifacts and emits an operator-fill template for missing receipt coverage. It does not modify the "
    "canonical operator receipt, write metric payload JSON, approve receipts, promote canonical intake, "
    "change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate "
    "external state."
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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _float_valid(value: Any) -> bool:
    try:
        float(_text(value))
    except (TypeError, ValueError):
        return False
    return True


def _split_payload_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reviewed_at_valid(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _artifact_sha256(path_like: str, *, root: Path) -> str:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return ""
    return _sha256_file(path)


def _validate_payload(
    payload: dict[str, Any],
    *,
    priority_row: dict[str, Any],
    artifact_path: str,
    root: Path,
) -> tuple[str, list[str], dict[str, Any]]:
    blockers: list[str] = []
    missing_fields = [field for field in REQUIRED_PAYLOAD_FIELDS if field not in payload]
    if missing_fields:
        blockers.append("missing_required_payload_fields")
    if _text(payload.get("metric_name")) != _text(priority_row.get("metric_name")):
        blockers.append("metric_name_mismatch")
    if _text(payload.get("target_id")).lower() != _text(priority_row.get("target_id")).lower():
        blockers.append("target_id_mismatch")
    if _text(payload.get("pose_id")) != _text(priority_row.get("pose_id")):
        blockers.append("pose_id_mismatch")
    if not _float_valid(payload.get("value")):
        blockers.append("metric_value_missing_or_invalid")
    if not _text(payload.get("method")):
        blockers.append("method_missing")
    if _bool(payload.get("license_ok")) is not True:
        blockers.append("license_not_ok")
    if _int(payload.get("external_engine_calls")) != 0:
        blockers.append("external_engine_calls_not_zero")
    if not _reviewed_at_valid(payload.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")

    input_artifacts = _split_payload_list(payload.get("input_artifacts"))
    input_hashes = _split_payload_list(payload.get("input_artifact_sha256s"))
    if not input_artifacts:
        blockers.append("input_artifacts_missing")
    if len(input_artifacts) != len(input_hashes):
        blockers.append("input_artifact_sha256_count_mismatch")
    present_count = 0
    verified_count = 0
    for artifact, expected_hash in zip(input_artifacts, input_hashes):
        if "::" in artifact:
            blockers.append("tar_member_input_artifact_not_supported_for_backfill_precheck")
            continue
        path = _resolve(artifact, root=root)
        if not path.is_file():
            blockers.append("input_artifact_missing")
            continue
        present_count += 1
        if _sha256_file(path) == expected_hash:
            verified_count += 1
        else:
            blockers.append("input_artifact_sha256_mismatch")

    artifact_sha256 = _artifact_sha256(artifact_path, root=root)
    if not artifact_sha256:
        blockers.append("metric_source_artifact_missing")

    details = {
        "input_artifacts": ";".join(input_artifacts),
        "input_artifact_sha256s": ";".join(input_hashes),
        "input_artifact_count": len(input_artifacts),
        "input_artifact_present_count": present_count,
        "input_artifact_sha256_verified_count": verified_count,
        "metric_source_artifact_sha256": artifact_sha256,
        "missing_payload_fields": ";".join(missing_fields),
    }
    return ("pass" if not blockers else "blocked"), sorted(set(blockers)), details


def _seeded_priority_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("priority_rows")
    if not isinstance(rows, list):
        return []
    return [
        dict(row)
        for row in rows
        if isinstance(row, dict)
        and _text(row.get("operator_gap_class")) == "existing_metric_payload_present_without_operator_receipt"
    ]


def build_refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet(
    *,
    payload_priority_json: str | Path = DEFAULT_PAYLOAD_PRIORITY_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    priority_payload, priority_present = _read_json(payload_priority_json, root=root_path)
    priority_summary = priority_payload.get("summary") if isinstance(priority_payload.get("summary"), dict) else {}
    seeded_rows = _seeded_priority_rows(priority_payload)
    template_rows: list[dict[str, Any]] = []
    for index, priority_row in enumerate(seeded_rows, start=1):
        artifact = _text(priority_row.get("metric_source_artifact"))
        payload, artifact_present = _read_json(artifact, root=root_path)
        validation_status, blockers, validation_details = _validate_payload(
            payload,
            priority_row=priority_row,
            artifact_path=artifact,
            root=root_path,
        ) if artifact_present else ("blocked", ["metric_source_artifact_missing"], {})
        template_rows.append(
            {
                "backfill_id": f"r9_seeded_metric_payload_receipt_backfill_{index:03d}",
                "payload_priority_rank": _int(priority_row.get("payload_priority_rank")),
                "target_id": _text(priority_row.get("target_id")),
                "pose_id": _text(priority_row.get("pose_id")),
                "work_order_id": _text(priority_row.get("work_order_id")),
                "split": _text(priority_row.get("split")),
                "metric_name": _text(priority_row.get("metric_name")),
                "metric_source_artifact": artifact,
                "metric_source_artifact_present": artifact_present,
                "metric_source_artifact_sha256": validation_details.get("metric_source_artifact_sha256", ""),
                "payload_validation_status": validation_status,
                "payload_validation_blockers": ";".join(blockers),
                "existing_metric_value": _text(payload.get("value")),
                "existing_metric_method": _text(payload.get("method")),
                "existing_operator_id": _text(payload.get("operator_id")),
                "existing_reviewed_at_utc": _text(payload.get("reviewed_at_utc")),
                "existing_license_ok": _text(payload.get("license_ok")),
                "existing_external_engine_calls": _text(payload.get("external_engine_calls")),
                "input_artifacts": validation_details.get("input_artifacts", ""),
                "input_artifact_sha256s": validation_details.get("input_artifact_sha256s", ""),
                "input_artifact_count": validation_details.get("input_artifact_count", 0),
                "input_artifact_present_count": validation_details.get("input_artifact_present_count", 0),
                "input_artifact_sha256_verified_count": validation_details.get(
                    "input_artifact_sha256_verified_count", 0
                ),
                "missing_payload_fields": validation_details.get("missing_payload_fields", ""),
                "operator_decision": "OPERATOR_FILL_ACCEPT_OR_REJECT",
                "metric_value_reviewed": "OPERATOR_CONFIRM_TRUE",
                "method_reviewed": "OPERATOR_CONFIRM_TRUE",
                "input_artifacts_reviewed": "OPERATOR_CONFIRM_TRUE",
                "input_artifact_sha256s_reviewed": "OPERATOR_CONFIRM_TRUE",
                "metric_source_artifact_reviewed": "OPERATOR_CONFIRM_TRUE",
                "payload_schema_reviewed": "OPERATOR_CONFIRM_TRUE",
                "license_ok_reviewed": "OPERATOR_CONFIRM_TRUE",
                "operator_id": "OPERATOR_FILL_OPERATOR_ID",
                "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
                "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
                "approval_token_required": APPROVAL_TOKEN,
                "operator_manual_pending_field_count": len(OPERATOR_PENDING_FIELDS),
                "operator_manual_pending_fields": ";".join(OPERATOR_PENDING_FIELDS),
                "canonical_receipt_write_allowed": False,
                "payload_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
        )

    valid_rows = [row for row in template_rows if row["payload_validation_status"] == "pass"]
    target_ids = sorted({_text(row.get("target_id")) for row in template_rows if _text(row.get("target_id"))})
    summary = {
        "packet_type": "refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet",
        "status": (
            "refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_ready"
            if priority_present and template_rows
            else "blocked_refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet"
        ),
        "payload_priority_json": _display(payload_priority_json, root=root_path),
        "payload_priority_json_present": priority_present,
        "locked_cv_model_id": priority_summary.get("locked_cv_model_id", ""),
        "locked_cv_bootstrap_p05": priority_summary.get("locked_cv_bootstrap_p05"),
        "locked_cv_bootstrap_p05_gap_to_claim_grade": priority_summary.get(
            "locked_cv_bootstrap_p05_gap_to_claim_grade"
        ),
        "seeded_backfill_row_count": len(template_rows),
        "seeded_backfill_target_count": len(target_ids),
        "seeded_backfill_targets": ";".join(target_ids),
        "metric_source_artifact_present_count": sum(1 for row in template_rows if row["metric_source_artifact_present"]),
        "payload_schema_valid_count": len(valid_rows),
        "payload_schema_blocked_count": len(template_rows) - len(valid_rows),
        "input_artifact_sha256_verified_row_count": sum(
            1
            for row in template_rows
            if _int(row.get("input_artifact_count"))
            and _int(row.get("input_artifact_count")) == _int(row.get("input_artifact_sha256_verified_count"))
        ),
        "operator_manual_pending_field_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in template_rows
        ),
        "operator_receipt_backfill_ready": False,
        "canonical_receipt_write_allowed": False,
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "approval_token_required": APPROVAL_TOKEN,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator must review the backfill template rows, confirm existing seeded metric values, input artifacts, "
            "hashes, payload schema, license, and approval token, then use a separate explicit procedure to extend "
            "canonical receipt coverage. This packet does not write that canonical receipt."
        ),
    }
    return {"summary": summary, "backfill_template_rows": template_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Seeded Metric Payload Receipt Backfill Packet",
        "",
        f"- status: `{s['status']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_bootstrap_p05: `{s['locked_cv_bootstrap_p05']}`",
        f"- seeded_backfill_row_count: `{s['seeded_backfill_row_count']}`",
        f"- seeded_backfill_target_count: `{s['seeded_backfill_target_count']}`",
        f"- seeded_backfill_targets: `{s['seeded_backfill_targets']}`",
        f"- metric_source_artifact_present_count: `{s['metric_source_artifact_present_count']}`",
        f"- payload_schema_valid_count: `{s['payload_schema_valid_count']}`",
        f"- input_artifact_sha256_verified_row_count: `{s['input_artifact_sha256_verified_row_count']}`",
        f"- operator_manual_pending_field_count: `{s['operator_manual_pending_field_count']}`",
        f"- operator_receipt_backfill_ready: `{s['operator_receipt_backfill_ready']}`",
        f"- canonical_receipt_write_allowed: `{s['canonical_receipt_write_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Backfill Rows",
        "",
        "| rank | target | pose | metric | validation | value | method | pending fields |",
        "| ---: | --- | --- | --- | --- | ---: | --- | ---: |",
    ]
    for row in payload["backfill_template_rows"]:
        lines.append(
            f"| `{row['payload_priority_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['payload_validation_status']}` | "
            f"`{row['existing_metric_value']}` | `{row['existing_metric_method']}` | "
            f"`{row['operator_manual_pending_field_count']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 seeded metric payload backfill packet.")
    parser.add_argument("--payload-priority-json", default=DEFAULT_PAYLOAD_PRIORITY_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet(
        payload_priority_json=args.payload_priority_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["backfill_template_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
