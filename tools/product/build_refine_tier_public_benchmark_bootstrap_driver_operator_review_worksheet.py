#!/usr/bin/env python3
"""Read-only operator review worksheet for top R9 bootstrap drivers."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRIVER_AUDIT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_evidence_audit_current.json"
DEFAULT_CANDIDATE_FILL_JSON = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.json"
)
DEFAULT_BACKFILL_JSON = (
    "config/refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_current.json"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_current.json"
DEFAULT_OUT_CSV = "config/refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_current.md"

CANDIDATE_PENDING_FIELDS = (
    "operator_decision",
    "metric_value_reviewed",
    "method_reviewed",
    "input_artifacts_reviewed",
    "input_artifact_sha256s_reviewed",
    "expected_metric_source_artifact_reviewed",
    "payload_schema_reviewed",
    "license_ok_reviewed",
    "operator_id",
    "reviewed_at_utc",
    "approval_token",
)

CLAIM_BOUNDARY = (
    "R9 bootstrap driver operator review worksheet only expands the top bootstrap-driver evidence audit "
    "into metric-row review templates. It does not write metric source payload JSON, approve receipts, "
    "extend canonical receipt coverage, promote canonical intake, change production scoring, run docking/MD, "
    "download, upload, email, delete, commit, push, or mutate external state."
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
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _key(row)
        if key[0] and key[1]:
            grouped[key].append(row)
    return dict(grouped)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_hashes_verified(artifacts_text: Any, hashes_text: Any, *, root: Path) -> bool:
    artifacts = _split_semicolon(artifacts_text)
    hashes = _split_semicolon(hashes_text)
    if not artifacts or len(artifacts) != len(hashes):
        return False
    for artifact, digest in zip(artifacts, hashes):
        if "::" in artifact:
            return False
        path = _resolve(artifact, root=root)
        if not path.is_file() or _sha256_file(path) != digest:
            return False
    return True


def _candidate_review_rows(
    *,
    audit_row: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
    start_index: int,
    root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset, candidate in enumerate(sorted(candidate_rows, key=lambda row: _text(row.get("metric_name"))), start=0):
        worksheet_index = start_index + offset
        input_hashes_verified = _input_hashes_verified(
            candidate.get("candidate_input_artifacts"),
            candidate.get("candidate_input_artifact_sha256s"),
            root=root,
        )
        rows.append(
            {
                "worksheet_id": f"r9_bootstrap_driver_operator_review_{worksheet_index:03d}",
                "driver_audit_rank": _int(audit_row.get("driver_audit_rank")),
                "recovery_priority_rank": _int(audit_row.get("recovery_priority_rank")),
                "target_id": _text(candidate.get("target_id")),
                "pose_id": _text(candidate.get("pose_id")),
                "work_order_id": _text(audit_row.get("work_order_id")),
                "split": _text(audit_row.get("split")),
                "metric_name": _text(candidate.get("metric_name")),
                "review_surface": "candidate_preview_payload_write_review",
                "driver_audit_class": _text(audit_row.get("audit_class")),
                "bootstrap_p05_delta_if_removed": _text(audit_row.get("bootstrap_p05_delta_if_removed")),
                "rank_abs_error": _int(audit_row.get("rank_abs_error")),
                "metric_value_under_review": _text(candidate.get("metric_value_candidate")),
                "method_under_review": _text(candidate.get("method_candidate")),
                "expected_metric_source_artifact": _text(candidate.get("expected_metric_source_artifact")),
                "expected_metric_source_artifact_present": _bool(
                    candidate.get("expected_metric_source_artifact_present")
                ),
                "metric_source_artifact_sha256": "",
                "payload_validation_status": "candidate_payload_not_written",
                "input_artifacts": _text(candidate.get("candidate_input_artifacts")),
                "input_artifact_sha256s": _text(candidate.get("candidate_input_artifact_sha256s")),
                "input_artifact_sha256_verified": input_hashes_verified,
                "operator_decision": "OPERATOR_FILL_ACCEPT_OR_REJECT",
                "metric_value_reviewed": "OPERATOR_CONFIRM_TRUE",
                "method_reviewed": "OPERATOR_CONFIRM_TRUE",
                "input_artifacts_reviewed": "OPERATOR_CONFIRM_TRUE",
                "input_artifact_sha256s_reviewed": "OPERATOR_CONFIRM_TRUE",
                "expected_metric_source_artifact_reviewed": "OPERATOR_CONFIRM_TRUE",
                "payload_schema_reviewed": "OPERATOR_CONFIRM_TRUE",
                "license_ok_reviewed": "OPERATOR_CONFIRM_TRUE",
                "operator_id": "OPERATOR_FILL_OPERATOR_ID",
                "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
                "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
                "approval_token_required": APPROVAL_TOKEN,
                "operator_manual_pending_field_count": len(CANDIDATE_PENDING_FIELDS),
                "operator_manual_pending_fields": ";".join(CANDIDATE_PENDING_FIELDS),
                "payload_write_allowed": False,
                "canonical_receipt_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
        )
    return rows


def _backfill_review_rows(
    *,
    audit_row: dict[str, Any],
    backfill_rows: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset, backfill in enumerate(sorted(backfill_rows, key=lambda row: _int(row.get("payload_priority_rank"))), start=0):
        worksheet_index = start_index + offset
        rows.append(
            {
                "worksheet_id": f"r9_bootstrap_driver_operator_review_{worksheet_index:03d}",
                "driver_audit_rank": _int(audit_row.get("driver_audit_rank")),
                "recovery_priority_rank": _int(audit_row.get("recovery_priority_rank")),
                "target_id": _text(backfill.get("target_id")),
                "pose_id": _text(backfill.get("pose_id")),
                "work_order_id": _text(backfill.get("work_order_id")) or _text(audit_row.get("work_order_id")),
                "split": _text(backfill.get("split")) or _text(audit_row.get("split")),
                "metric_name": _text(backfill.get("metric_name")),
                "review_surface": "existing_payload_backfill_receipt_review",
                "driver_audit_class": _text(audit_row.get("audit_class")),
                "bootstrap_p05_delta_if_removed": _text(audit_row.get("bootstrap_p05_delta_if_removed")),
                "rank_abs_error": _int(audit_row.get("rank_abs_error")),
                "metric_value_under_review": _text(backfill.get("existing_metric_value")),
                "method_under_review": _text(backfill.get("existing_metric_method")),
                "expected_metric_source_artifact": _text(backfill.get("metric_source_artifact")),
                "expected_metric_source_artifact_present": _bool(backfill.get("metric_source_artifact_present")),
                "metric_source_artifact_sha256": _text(backfill.get("metric_source_artifact_sha256")),
                "payload_validation_status": _text(backfill.get("payload_validation_status")),
                "input_artifacts": _text(backfill.get("input_artifacts")),
                "input_artifact_sha256s": _text(backfill.get("input_artifact_sha256s")),
                "input_artifact_sha256_verified": bool(
                    _int(backfill.get("input_artifact_count"))
                    and _int(backfill.get("input_artifact_count"))
                    == _int(backfill.get("input_artifact_sha256_verified_count"))
                ),
                "operator_decision": _text(backfill.get("operator_decision")),
                "metric_value_reviewed": _text(backfill.get("metric_value_reviewed")),
                "method_reviewed": _text(backfill.get("method_reviewed")),
                "input_artifacts_reviewed": _text(backfill.get("input_artifacts_reviewed")),
                "input_artifact_sha256s_reviewed": _text(backfill.get("input_artifact_sha256s_reviewed")),
                "expected_metric_source_artifact_reviewed": _text(backfill.get("metric_source_artifact_reviewed")),
                "payload_schema_reviewed": _text(backfill.get("payload_schema_reviewed")),
                "license_ok_reviewed": _text(backfill.get("license_ok_reviewed")),
                "operator_id": _text(backfill.get("operator_id")),
                "reviewed_at_utc": _text(backfill.get("reviewed_at_utc")),
                "approval_token": _text(backfill.get("approval_token")),
                "approval_token_required": _text(backfill.get("approval_token_required")) or APPROVAL_TOKEN,
                "operator_manual_pending_field_count": _int(backfill.get("operator_manual_pending_field_count")),
                "operator_manual_pending_fields": _text(backfill.get("operator_manual_pending_fields")),
                "payload_write_allowed": False,
                "canonical_receipt_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
        )
    return rows


def build_refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet(
    *,
    driver_audit_json: str | Path = DEFAULT_DRIVER_AUDIT_JSON,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    backfill_json: str | Path = DEFAULT_BACKFILL_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    audit_payload, audit_present = _read_json(driver_audit_json, root=root_path)
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    backfill_payload, backfill_present = _read_json(backfill_json, root=root_path)
    candidate_by_key = _group_rows(_rows(candidate_payload, "rows"))
    backfill_by_key = _group_rows(_rows(backfill_payload, "backfill_template_rows"))

    worksheet_rows: list[dict[str, Any]] = []
    for audit_row in sorted(_rows(audit_payload, "audit_rows"), key=lambda row: _int(row.get("driver_audit_rank"))):
        key = (_text(audit_row.get("target_id")), _text(audit_row.get("pose_id")))
        start_index = len(worksheet_rows) + 1
        if _text(audit_row.get("audit_class")) == "candidate_preview_payload_not_written":
            worksheet_rows.extend(
                _candidate_review_rows(
                    audit_row=audit_row,
                    candidate_rows=candidate_by_key.get(key, []),
                    start_index=start_index,
                    root=root_path,
                )
            )
        elif _text(audit_row.get("audit_class")) == "existing_payload_receipt_backfill_pending":
            worksheet_rows.extend(
                _backfill_review_rows(
                    audit_row=audit_row,
                    backfill_rows=backfill_by_key.get(key, []),
                    start_index=start_index,
                )
            )

    candidate_rows = [row for row in worksheet_rows if row["review_surface"] == "candidate_preview_payload_write_review"]
    backfill_rows = [row for row in worksheet_rows if row["review_surface"] == "existing_payload_backfill_receipt_review"]
    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_ready"
            if audit_present and candidate_present and backfill_present and worksheet_rows
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet"
        ),
        "driver_audit_json": _display(driver_audit_json, root=root_path),
        "driver_audit_json_present": audit_present,
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_json_present": candidate_present,
        "backfill_json": _display(backfill_json, root=root_path),
        "backfill_json_present": backfill_present,
        "worksheet_row_count": len(worksheet_rows),
        "candidate_preview_review_row_count": len(candidate_rows),
        "existing_payload_backfill_review_row_count": len(backfill_rows),
        "candidate_preview_input_hash_verified_row_count": sum(
            1 for row in candidate_rows if bool(row.get("input_artifact_sha256_verified"))
        ),
        "existing_payload_validation_pass_row_count": sum(
            1 for row in backfill_rows if row.get("payload_validation_status") == "pass"
        ),
        "existing_payload_input_hash_verified_row_count": sum(
            1 for row in backfill_rows if bool(row.get("input_artifact_sha256_verified"))
        ),
        "expected_metric_source_artifact_present_row_count": sum(
            1 for row in worksheet_rows if bool(row.get("expected_metric_source_artifact_present"))
        ),
        "operator_manual_pending_field_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in worksheet_rows
        ),
        "approval_token_required": APPROVAL_TOKEN,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator must review the six top-driver metric rows, confirm values/methods/input hashes/license, "
            "and provide the approval token in a separate approved procedure before any payload or receipt write."
        ),
    }
    return {"summary": summary, "worksheet_rows": worksheet_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Operator Review Worksheet",
        "",
        f"- status: `{s['status']}`",
        f"- worksheet_row_count: `{s['worksheet_row_count']}`",
        f"- candidate_preview_review_row_count: `{s['candidate_preview_review_row_count']}`",
        f"- existing_payload_backfill_review_row_count: `{s['existing_payload_backfill_review_row_count']}`",
        f"- candidate_preview_input_hash_verified_row_count: `{s['candidate_preview_input_hash_verified_row_count']}`",
        f"- existing_payload_validation_pass_row_count: `{s['existing_payload_validation_pass_row_count']}`",
        f"- existing_payload_input_hash_verified_row_count: `{s['existing_payload_input_hash_verified_row_count']}`",
        f"- operator_manual_pending_field_count: `{s['operator_manual_pending_field_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Worksheet Rows",
        "",
        "| worksheet | target | pose | metric | surface | value | method | hash verified | pending fields |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | ---: |",
    ]
    for row in payload["worksheet_rows"]:
        lines.append(
            f"| `{row['worksheet_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['review_surface']}` | "
            f"`{row['metric_value_under_review']}` | `{row['method_under_review']}` | "
            f"`{row['input_artifact_sha256_verified']}` | `{row['operator_manual_pending_field_count']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 bootstrap-driver operator review worksheet.")
    parser.add_argument("--driver-audit-json", default=DEFAULT_DRIVER_AUDIT_JSON)
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--backfill-json", default=DEFAULT_BACKFILL_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet(
        driver_audit_json=args.driver_audit_json,
        candidate_fill_json=args.candidate_fill_json,
        backfill_json=args.backfill_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["worksheet_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
