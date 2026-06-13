#!/usr/bin/env python3
"""Field-level worksheet for engine-refinement claim evidence intake."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_engine_refinement_claim_evidence_priority_packet import (
    DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON,
    DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
    DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV,
    DEFAULT_RECEIPT_JSON,
    DEFAULT_OUT_JSON as DEFAULT_PRIORITY_PACKET_JSON,
)
from tools.product.build_engine_refinement_claim_evidence_receipt import (
    ALLOWED_PROVENANCE_KINDS,
    APPROVAL_TOKEN,
    DEFAULT_RECEIPT_CSV,
    EXPECTED_EVIDENCE,
    PLACEHOLDER_PREFIXES,
    REQUIRED_BLOCKERS,
    REQUIRED_COLUMNS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json"
DEFAULT_OUT_CSV = "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.csv"
DEFAULT_OUT_MD = "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.md"

WORK_ORDER_OPERATOR_FIELDS = [
    "benchmark_id",
    "target_id",
    "provenance_id",
    "license_ok",
    "pose_rmsd_A",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "deltaG_experimental_kcal_mol",
]
RECEIPT_OPTIONAL_FIELDS = {"notes"}
RECEIPT_TRUE_FIELDS = {"claim_ready", "license_ok"}
RECEIPT_TIMESTAMP_FIELDS = {"reviewed_at_utc"}
RECEIPT_REVIEW_FIELDS = {
    "evidence_artifact",
    "claim_ready",
    "reviewer",
    "reviewed_at_utc",
    "license_ok",
    "approval_token",
}

CLAIM_BOUNDARY = (
    "Engine refinement claim evidence operator field worksheet only; it expands the R9 claim evidence receipt "
    "and top public-benchmark work-order into field-level operator inputs. It does not download datasets, "
    "run docking or MD, write benchmark intake rows, approve tokens, promote claims, upload, email, delete, "
    "commit, push, or mutate external state."
)

FIELD_ACTIONS = {
    "blocker_id": "Keep one of the six required R9 blocker ids.",
    "evidence_artifact": "Replace the placeholder with a local reviewed evidence JSON path.",
    "evidence_status": "Keep the expected evidence status for the blocker row.",
    "claim_ready": "Confirm true only after the matching evidence packet is locally reviewed.",
    "reviewer": "Record the human/operator reviewer.",
    "reviewed_at_utc": "Record an ISO-8601 UTC review timestamp.",
    "provenance_kind": "Keep an accepted provenance kind.",
    "license_ok": "Confirm true only after public/source license review.",
    "external_engine_calls": "Keep 0; this path must not call external engines.",
    "approval_token": f"Use {APPROVAL_TOKEN} only after the R9 claim evidence review is approved.",
    "operator_attestation": "Keep reviewed_for_claim_promotion.",
    "notes": "Record caveats without changing claim state.",
    "benchmark_id": "Replace with a public benchmark pair id.",
    "target_id": "Replace with the target or complex id for the public benchmark row.",
    "provenance_id": "Replace with a public provenance id or source accession.",
    "pose_rmsd_A": "Fill a finite pose RMSD in Angstrom.",
    "dockq": "Fill a finite DockQ-like score.",
    "lddt_pli": "Fill a finite lDDT-PLI-like score.",
    "deltaG_mm_gbsa_kcal_mol": "Fill the internal refine free-energy estimate.",
    "deltaG_experimental_kcal_mol": "Fill the public experimental free-energy value.",
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display_path(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float_ok(value: Any) -> bool:
    try:
        return math.isfinite(float(_text(value)))
    except (TypeError, ValueError):
        return False


def _has_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or any(text.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _is_iso_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if packet.get("status") else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows") or [] if isinstance(row, dict)]


def _read_csv(
    path_like: str | Path,
    *,
    root: Path = ROOT,
    required_columns: list[str] | None = None,
) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], list(required_columns or []), False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    missing_columns = [column for column in (required_columns or []) if column not in fieldnames]
    return rows, missing_columns, True


def _expected_receipt_value(field_name: str, blocker_id: str) -> str:
    expected = EXPECTED_EVIDENCE.get(blocker_id, {})
    if field_name == "blocker_id":
        return "one required R9 blocker id"
    if field_name == "evidence_artifact":
        return "local reviewed evidence JSON"
    if field_name == "evidence_status":
        return _text(expected.get("status"))
    if field_name in RECEIPT_TRUE_FIELDS:
        return "true"
    if field_name == "reviewer":
        return "non-empty operator reviewer"
    if field_name == "reviewed_at_utc":
        return "ISO-8601 UTC timestamp"
    if field_name == "provenance_kind":
        return ",".join(sorted(ALLOWED_PROVENANCE_KINDS))
    if field_name == "external_engine_calls":
        return "0"
    if field_name == "approval_token":
        return APPROVAL_TOKEN
    if field_name == "operator_attestation":
        return "reviewed_for_claim_promotion"
    return ""


def _receipt_gate_id(field_name: str, blocker_id: str) -> str:
    if field_name in {"evidence_artifact", "evidence_status", "claim_ready"}:
        return blocker_id
    if field_name in {"reviewer", "reviewed_at_utc", "approval_token", "operator_attestation"}:
        return "operator_review"
    if field_name in {"license_ok", "provenance_kind"}:
        return "provenance_license_review"
    if field_name == "external_engine_calls":
        return "external_engine_call_guard"
    return ""


def _receipt_field_status(field_name: str, value: Any, blocker_id: str) -> tuple[str, str]:
    text = _text(value)
    if _has_placeholder(value):
        if field_name in RECEIPT_OPTIONAL_FIELDS:
            return "informational", ""
        return "operator_fill_pending", "operator_placeholder_or_empty"
    if field_name == "blocker_id":
        return ("ready", "") if text in REQUIRED_BLOCKERS else ("invalid", "blocker_id_missing_or_unrecognized")
    if field_name == "evidence_status":
        expected = _text(EXPECTED_EVIDENCE.get(blocker_id, {}).get("status"))
        return ("ready", "") if text == expected else ("invalid", "receipt_evidence_status_mismatch")
    if field_name in RECEIPT_TRUE_FIELDS:
        return ("ready", "") if _bool_text(value) else ("invalid", f"{field_name}_not_true")
    if field_name in RECEIPT_TIMESTAMP_FIELDS:
        return ("ready", "") if _is_iso_timestamp(value) else ("invalid", "reviewed_at_utc_missing_or_invalid")
    if field_name == "provenance_kind":
        return ("ready", "") if text in ALLOWED_PROVENANCE_KINDS else ("invalid", "provenance_kind_unaccepted")
    if field_name == "external_engine_calls":
        return ("ready", "") if _int(value) == 0 else ("invalid", "external_engine_calls_present")
    if field_name == "approval_token":
        return ("ready", "") if text == APPROVAL_TOKEN else ("invalid", "approval_token_missing_or_invalid")
    if field_name == "operator_attestation":
        return (
            ("ready", "")
            if text == "reviewed_for_claim_promotion"
            else ("invalid", "operator_attestation_missing_or_unaccepted")
        )
    if field_name in RECEIPT_OPTIONAL_FIELDS:
        return "informational", ""
    return ("ready", "") if text else ("operator_fill_pending", "operator_placeholder_or_empty")


def _receipt_field_row(
    field_name: str,
    *,
    row_index: int,
    column_present: bool,
    receipt_row: dict[str, str],
    receipt_report_row: dict[str, Any],
    priority_summary: dict[str, Any],
) -> dict[str, Any]:
    blocker_id = _text(receipt_row.get("blocker_id"))
    value = receipt_row.get(field_name, "")
    status, blocker = (
        _receipt_field_status(field_name, value, blocker_id)
        if column_present
        else ("missing_column", "receipt_column_missing")
    )
    expected = EXPECTED_EVIDENCE.get(blocker_id, {})
    expected_true_fields = ";".join(str(field) for field in expected.get("true_fields", []))
    return {
        "worksheet_section": "claim_evidence_receipt",
        "source_row_id": blocker_id or f"receipt_row_{row_index}",
        "source_row_index": row_index,
        "field_name": field_name,
        "gate_id": _receipt_gate_id(field_name, blocker_id),
        "receipt_column_present": column_present,
        "required_for_operator_receipt": field_name not in RECEIPT_OPTIONAL_FIELDS,
        "top_blocker_field": blocker_id == _text(priority_summary.get("top_blocker_id")),
        "current_value": _text(value),
        "observed_source_value": _text(receipt_report_row.get("observed_evidence_status")),
        "expected_value_hint": _expected_receipt_value(field_name, blocker_id),
        "expected_true_fields": expected_true_fields,
        "field_status": status,
        "blocker": blocker,
        "operator_input_required": status == "operator_fill_pending",
        "top_blocker_id": _text(priority_summary.get("top_blocker_id")),
        "top_priority_bucket": _text(priority_summary.get("top_priority_bucket")),
        "operator_action": FIELD_ACTIONS.get(field_name, ""),
        "claim_promoted": False,
        "external_engine_calls_executed": False,
        "external_state_mutated": False,
    }


def _expected_work_order_value(field_name: str) -> str:
    if field_name in {"pose_rmsd_A", "dockq", "lddt_pli", "deltaG_mm_gbsa_kcal_mol", "deltaG_experimental_kcal_mol"}:
        return "finite numeric value"
    if field_name == "license_ok":
        return "true"
    return "non-placeholder public benchmark value"


def _work_order_field_status(field_name: str, value: Any) -> tuple[str, str]:
    if _has_placeholder(value):
        return "operator_fill_pending", "operator_placeholder_or_empty"
    if field_name == "license_ok":
        return ("ready", "") if _bool_text(value) else ("invalid", "license_not_ok")
    if field_name in {"pose_rmsd_A", "dockq", "lddt_pli", "deltaG_mm_gbsa_kcal_mol", "deltaG_experimental_kcal_mol"}:
        return ("ready", "") if _float_ok(value) else ("invalid", f"{field_name}_not_numeric")
    return ("ready", "") if _text(value) else ("operator_fill_pending", "operator_placeholder_or_empty")


def _work_order_field_row(
    field_name: str,
    *,
    row_index: int,
    column_present: bool,
    work_order_row: dict[str, str],
    work_order_report_row: dict[str, Any],
    priority_summary: dict[str, Any],
) -> dict[str, Any]:
    work_order_id = _text(work_order_row.get("work_order_id")) or f"work_order_row_{row_index}"
    value = work_order_row.get(field_name, "")
    status, blocker = (
        _work_order_field_status(field_name, value)
        if column_present
        else ("missing_column", "work_order_column_missing")
    )
    return {
        "worksheet_section": "public_benchmark_work_order",
        "source_row_id": work_order_id,
        "source_row_index": row_index,
        "field_name": field_name,
        "gate_id": "public_benchmark_gate_not_ready",
        "receipt_column_present": column_present,
        "required_for_operator_receipt": False,
        "top_blocker_field": True,
        "current_value": _text(value),
        "observed_source_value": _text(work_order_report_row.get("row_status")),
        "expected_value_hint": _expected_work_order_value(field_name),
        "expected_true_fields": "claim_grade_public_benchmark_ready",
        "field_status": status,
        "blocker": blocker,
        "operator_input_required": status == "operator_fill_pending",
        "top_blocker_id": _text(priority_summary.get("top_blocker_id")),
        "top_priority_bucket": _text(priority_summary.get("top_priority_bucket")),
        "operator_action": FIELD_ACTIONS.get(field_name, ""),
        "claim_promoted": False,
        "external_engine_calls_executed": False,
        "external_state_mutated": False,
    }


def build_engine_refinement_claim_evidence_operator_field_worksheet(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    receipt_json: str | Path = DEFAULT_RECEIPT_JSON,
    priority_packet_json: str | Path = DEFAULT_PRIORITY_PACKET_JSON,
    public_benchmark_readiness_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON,
    public_benchmark_work_order_csv: str | Path = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV,
    public_benchmark_work_order_apply_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    receipt_rows, receipt_missing_columns, receipt_csv_present = _read_csv(
        receipt_csv,
        root=root_path,
        required_columns=REQUIRED_COLUMNS,
    )
    receipt_packet, receipt_artifact_present = _read_json(receipt_json, root=root_path)
    priority_packet, priority_artifact_present = _read_json(priority_packet_json, root=root_path)
    public_packet, public_artifact_present = _read_json(public_benchmark_readiness_json, root=root_path)
    work_order_rows, work_order_missing_columns, work_order_csv_present = _read_csv(
        public_benchmark_work_order_csv,
        root=root_path,
        required_columns=WORK_ORDER_OPERATOR_FIELDS,
    )
    work_order_apply_packet, work_order_apply_present = _read_json(
        public_benchmark_work_order_apply_json,
        root=root_path,
    )
    receipt_summary = _summary(receipt_packet)
    priority_summary = _summary(priority_packet)
    public_summary = _summary(public_packet)
    work_order_apply_summary = _summary(work_order_apply_packet)
    receipt_report_by_blocker = {
        _text(row.get("blocker_id")): row for row in _rows(receipt_packet)
    }
    work_order_report_by_id = {
        _text(row.get("work_order_id")): row for row in _rows(work_order_apply_packet)
    }
    receipt_field_rows = [
        _receipt_field_row(
            field_name,
            row_index=row_index,
            column_present=field_name not in receipt_missing_columns,
            receipt_row=receipt_row,
            receipt_report_row=receipt_report_by_blocker.get(_text(receipt_row.get("blocker_id")), {}),
            priority_summary=priority_summary,
        )
        for row_index, receipt_row in enumerate(receipt_rows, start=1)
        for field_name in REQUIRED_COLUMNS
    ]
    work_order_field_rows = [
        _work_order_field_row(
            field_name,
            row_index=row_index,
            column_present=field_name not in work_order_missing_columns,
            work_order_row=work_order_row,
            work_order_report_row=work_order_report_by_id.get(_text(work_order_row.get("work_order_id")), {}),
            priority_summary=priority_summary,
        )
        for row_index, work_order_row in enumerate(work_order_rows, start=1)
        for field_name in WORK_ORDER_OPERATOR_FIELDS
    ]
    worksheet_rows = receipt_field_rows + work_order_field_rows
    pending_rows = [row for row in worksheet_rows if row["field_status"] == "operator_fill_pending"]
    invalid_rows = [row for row in worksheet_rows if row["field_status"] in {"invalid", "missing_column"}]
    top_blocker_rows = [row for row in worksheet_rows if row.get("top_blocker_field") is True]
    top_blocker_pending_rows = [
        row for row in top_blocker_rows if row["field_status"] == "operator_fill_pending"
    ]
    receipt_pending_rows = [
        row for row in receipt_field_rows if row["field_status"] == "operator_fill_pending"
    ]
    work_order_pending_rows = [
        row for row in work_order_field_rows if row["field_status"] == "operator_fill_pending"
    ]
    source_blockers: list[str] = []
    if not receipt_csv_present:
        source_blockers.append("receipt_csv_missing")
    if receipt_missing_columns:
        source_blockers.append("receipt_columns_missing")
    if not receipt_rows:
        source_blockers.append("receipt_rows_missing")
    if not receipt_artifact_present:
        source_blockers.append("receipt_artifact_missing")
    if not priority_artifact_present:
        source_blockers.append("priority_packet_artifact_missing")
    if not public_artifact_present:
        source_blockers.append("public_benchmark_readiness_artifact_missing")
    if not work_order_csv_present:
        source_blockers.append("public_benchmark_work_order_csv_missing")
    if work_order_missing_columns:
        source_blockers.append("public_benchmark_work_order_columns_missing")
    if not work_order_rows:
        source_blockers.append("public_benchmark_work_order_rows_missing")
    if not work_order_apply_present:
        source_blockers.append("public_benchmark_work_order_apply_artifact_missing")
    worksheet_ready = not source_blockers
    operator_fill_complete = worksheet_ready and not pending_rows and not invalid_rows
    summary = {
        "packet_type": "engine_refinement_claim_evidence_operator_field_worksheet",
        "status": (
            "engine_refinement_claim_evidence_operator_field_worksheet_ready"
            if worksheet_ready
            else "blocked_engine_refinement_claim_evidence_operator_field_worksheet"
        ),
        "field_worksheet_ready": worksheet_ready,
        "operator_fill_complete": operator_fill_complete,
        "receipt_csv": _display_path(receipt_csv, root=root_path),
        "receipt_artifact": _display_path(receipt_json, root=root_path),
        "receipt_status": _text(receipt_summary.get("status")),
        "receipt_ready": bool(receipt_summary.get("claim_promotion_evidence_receipt_ready") is True),
        "priority_packet_artifact": _display_path(priority_packet_json, root=root_path),
        "priority_packet_status": _text(priority_summary.get("status")),
        "public_benchmark_readiness_artifact": _display_path(public_benchmark_readiness_json, root=root_path),
        "public_benchmark_status": _text(public_summary.get("status")),
        "public_benchmark_gate_ready": bool(public_summary.get("claim_grade_public_benchmark_ready") is True),
        "public_benchmark_work_order_csv": _display_path(public_benchmark_work_order_csv, root=root_path),
        "public_benchmark_work_order_apply_artifact": _display_path(
            public_benchmark_work_order_apply_json,
            root=root_path,
        ),
        "public_benchmark_work_order_apply_status": _text(work_order_apply_summary.get("status")),
        "public_benchmark_work_order_apply_ready": bool(work_order_apply_summary.get("apply_ready") is True),
        "receipt_csv_present": receipt_csv_present,
        "receipt_artifact_present": receipt_artifact_present,
        "priority_packet_artifact_present": priority_artifact_present,
        "public_benchmark_readiness_artifact_present": public_artifact_present,
        "public_benchmark_work_order_csv_present": work_order_csv_present,
        "public_benchmark_work_order_apply_artifact_present": work_order_apply_present,
        "receipt_row_count": len(receipt_rows),
        "receipt_field_row_count": len(receipt_field_rows),
        "required_receipt_field_count": len(
            [row for row in receipt_field_rows if row["required_for_operator_receipt"]]
        ),
        "receipt_operator_fill_pending_field_count": len(receipt_pending_rows),
        "public_benchmark_work_order_row_count": len(work_order_rows),
        "public_benchmark_work_order_field_count": len(work_order_field_rows),
        "public_benchmark_work_order_pending_field_count": len(work_order_pending_rows),
        "worksheet_field_row_count": len(worksheet_rows),
        "operator_fill_pending_field_count": len(pending_rows),
        "invalid_field_count": len(invalid_rows),
        "ready_field_count": len([row for row in worksheet_rows if row["field_status"] == "ready"]),
        "top_blocker_field_count": len(top_blocker_rows),
        "top_blocker_pending_field_count": len(top_blocker_pending_rows),
        "pending_field_names": [f"{row['source_row_id']}:{row['field_name']}" for row in pending_rows],
        "invalid_field_names": [f"{row['source_row_id']}:{row['field_name']}" for row in invalid_rows],
        "top_blocker_id": _text(priority_summary.get("top_blocker_id")),
        "top_priority_bucket": _text(priority_summary.get("top_priority_bucket")),
        "top_required_input": _text(priority_summary.get("top_required_input")),
        "top_acceptance_artifact": _text(priority_summary.get("top_acceptance_artifact")),
        "top_next_operator_step": _text(priority_summary.get("top_next_operator_step")),
        "top_verification_command": _text(priority_summary.get("top_verification_command")),
        "approval_token_required": APPROVAL_TOKEN,
        "public_benchmark_work_order_apply_blocked_row_count": _int(
            work_order_apply_summary.get("blocked_row_count")
        ),
        "claim_promotion_allowed": False,
        "claim_promoted": False,
        "intake_written": bool(work_order_apply_summary.get("intake_written") is True),
        "external_engine_calls_executed": False,
        "external_state_mutated": False,
        "blocker_count": len(source_blockers),
        "blockers": source_blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator fields are complete; rerun public benchmark apply/readiness, claim receipt, priority packet, "
            "and product-goal audit before any claim promotion."
            if operator_fill_complete
            else "Fill public benchmark work-order fields and matching claim evidence receipt fields, starting with "
            "the top R9 blocker, then rerun apply/readiness and receipt gates."
        ),
        "source_artifacts": [
            str(receipt_csv),
            str(receipt_json),
            str(priority_packet_json),
            str(public_benchmark_readiness_json),
            str(public_benchmark_work_order_csv),
            str(public_benchmark_work_order_apply_json),
        ],
    }
    return {"summary": summary, "rows": worksheet_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Engine Refinement Claim Evidence Operator Field Worksheet",
        "",
        f"- status: `{summary['status']}`",
        f"- field_worksheet_ready: `{summary['field_worksheet_ready']}`",
        f"- operator_fill_complete: `{summary['operator_fill_complete']}`",
        f"- operator_fill_pending_field_count: `{summary['operator_fill_pending_field_count']}`",
        f"- receipt_operator_fill_pending_field_count: `{summary['receipt_operator_fill_pending_field_count']}`",
        f"- public_benchmark_work_order_pending_field_count: `{summary['public_benchmark_work_order_pending_field_count']}`",
        f"- top_blocker_id: `{summary['top_blocker_id']}`",
        f"- top_priority_bucket: `{summary['top_priority_bucket']}`",
        f"- public_benchmark_work_order_apply_blocked_row_count: `{summary['public_benchmark_work_order_apply_blocked_row_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Rows",
        "",
        "| section | source row | field | gate | status | current | expected | action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['worksheet_section']}` | `{row['source_row_id']}` | `{row['field_name']}` | "
            f"`{row['gate_id']}` | `{row['field_status']}` | `{row['current_value']}` | "
            f"`{row['expected_value_hint']}` | `{row['operator_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build field-level worksheet for engine-refinement claim evidence receipt."
    )
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--receipt-json", default=DEFAULT_RECEIPT_JSON)
    parser.add_argument("--priority-packet-json", default=DEFAULT_PRIORITY_PACKET_JSON)
    parser.add_argument("--public-benchmark-readiness-json", default=DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON)
    parser.add_argument("--public-benchmark-work-order-csv", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV)
    parser.add_argument("--public-benchmark-work-order-apply-json", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_engine_refinement_claim_evidence_operator_field_worksheet(
        receipt_csv=args.receipt_csv,
        receipt_json=args.receipt_json,
        priority_packet_json=args.priority_packet_json,
        public_benchmark_readiness_json=args.public_benchmark_readiness_json,
        public_benchmark_work_order_csv=args.public_benchmark_work_order_csv,
        public_benchmark_work_order_apply_json=args.public_benchmark_work_order_apply_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
