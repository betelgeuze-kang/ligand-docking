#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INTAKE_CSV = "config/customer_shadow_evidence_intake_template.csv"
DEFAULT_OUT_JSON = "runs/customer_shadow_evidence_status_current.json"
DEFAULT_OUT_CSV = "runs/customer_shadow_evidence_status_current.csv"
DEFAULT_OUT_MD = "runs/customer_shadow_evidence_status_current.md"

MIN_COMPLETED_CASES = 3
PAID_PILOT_REQUIREMENT_IDS = [
    "customer_shadow_intake_schema_ready",
    "completed_customer_shadow_cases",
    "real_customer_shadow_rows",
    "customer_retained_raw_data",
    "redistribution_allowed_false",
    "anonymized_result_summary",
    "reviewer_signoff",
    "no_invalid_customer_shadow_rows",
    "customer_raw_data_not_stored_in_repo",
    "redistribution_allowed_required_value_false",
    "customer_shadow_work_order_closed",
    "paid_pilot_evidence_ready",
    "paid_pilot_claim_allowed",
    "commercial_readiness_promotion_allowed",
]
REQUIRED_COLUMNS = [
    "case_id",
    "row_kind",
    "raw_data_custody",
    "customer_retained_raw_data",
    "redistribution_allowed",
    "raw_data_stored_in_repo",
    "derived_metadata_fields",
    "anonymized_result_summary",
    "reviewer_signoff_status",
    "reviewer_id",
    "reviewed_at_utc",
    "source_artifact_fingerprint",
]
REQUIRED_DERIVED_METADATA_FIELDS = {
    "case_domain",
    "input_size_class",
    "runner_profile",
    "result_metric_summary",
    "artifact_fingerprint",
}
ALLOWED_ROW_KINDS = {"customer_shadow", "mock_fixture", "redacted_mock_fixture"}
MOCK_ROW_KINDS = {"mock_fixture", "redacted_mock_fixture"}
DISALLOWED_PRIVATE_COLUMNS = {
    "customer_name",
    "customer_email",
    "contact_email",
    "patient_id",
    "subject_id",
    "raw_data_path",
    "raw_data_uri",
    "private_payload",
    "private_raw_data",
    "pii",
    "author_code",
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

CLAIM_BOUNDARY = (
    "Customer shadow evidence status only; it validates a privacy-preserving intake schema for customer-retained "
    "raw data, derived metadata, anonymized summaries, and reviewer signoff. It does not ingest private customer "
    "raw data, fabricate customer evidence, approve readiness, promote commercial claims, upload, email, deploy, "
    "or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool | None:
    text = _text(value).lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _split_fields(value: Any) -> set[str]:
    text = _text(value)
    if not text:
        return set()
    return {part.strip() for part in re.split(r"[;,]", text) if part.strip()}


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[str], list[dict[str, str]]]:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{str(k or ""): _text(v) for k, v in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def _reviewed_at_valid(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _private_column_blockers(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    for column in DISALLOWED_PRIVATE_COLUMNS:
        if _text(row.get(column)):
            blockers.append(f"private_column_present:{column}")
    return blockers


def _row_status(row: dict[str, str], *, row_index: int, schema_ready: bool) -> dict[str, Any]:
    case_id = _text(row.get("case_id")) or f"row_{row_index}"
    row_kind = _text(row.get("row_kind"))
    blockers: list[str] = []
    if not schema_ready:
        blockers.append("schema_missing_required_columns")
    if not _text(row.get("case_id")):
        blockers.append("case_id_missing")
    if row_kind not in ALLOWED_ROW_KINDS:
        blockers.append("row_kind_invalid")

    raw_data_custody = _text(row.get("raw_data_custody")).lower()
    if raw_data_custody != "customer_retained":
        blockers.append("raw_data_custody_not_customer_retained")
    if _bool(row.get("customer_retained_raw_data")) is not True:
        blockers.append("customer_retained_raw_data_not_true")
    if _bool(row.get("redistribution_allowed")) is not False:
        blockers.append("redistribution_allowed_not_false")
    if _bool(row.get("raw_data_stored_in_repo")) is not False:
        blockers.append("raw_data_stored_in_repo_not_false")

    derived_fields = _split_fields(row.get("derived_metadata_fields"))
    missing_derived = sorted(REQUIRED_DERIVED_METADATA_FIELDS - derived_fields)
    if missing_derived:
        blockers.append("derived_metadata_fields_missing:" + ",".join(missing_derived))

    anonymized_summary = _text(row.get("anonymized_result_summary"))
    if len(anonymized_summary) < 24:
        blockers.append("anonymized_result_summary_too_short")
    if EMAIL_RE.search(anonymized_summary):
        blockers.append("anonymized_result_summary_contains_email")

    if _text(row.get("reviewer_signoff_status")).lower() != "approved":
        blockers.append("reviewer_signoff_not_approved")
    if not _text(row.get("reviewer_id")):
        blockers.append("reviewer_id_missing")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if not SHA256_RE.match(_text(row.get("source_artifact_fingerprint")).lower()):
        blockers.append("source_artifact_fingerprint_not_sha256")
    blockers.extend(_private_column_blockers(row))

    is_mock_fixture = row_kind in MOCK_ROW_KINDS or case_id.lower().startswith("mock_")
    completed_schema_valid = not blockers
    counts_toward_minimum = completed_schema_valid and not is_mock_fixture and row_kind == "customer_shadow"
    return {
        "case_id": case_id,
        "row_kind": row_kind,
        "status": "pass" if completed_schema_valid else "fail",
        "completed_schema_valid": completed_schema_valid,
        "counts_toward_minimum": counts_toward_minimum,
        "is_mock_fixture": is_mock_fixture,
        "blockers": ";".join(blockers),
        "blocker_count": len(blockers),
        "raw_data_custody": _text(row.get("raw_data_custody")),
        "customer_retained_raw_data": _text(row.get("customer_retained_raw_data")),
        "redistribution_allowed": _text(row.get("redistribution_allowed")),
        "raw_data_stored_in_repo": _text(row.get("raw_data_stored_in_repo")),
        "reviewer_signoff_status": _text(row.get("reviewer_signoff_status")),
        "next_action": (
            "Accepted as schema-valid mock fixture; does not count toward customer minimum."
            if completed_schema_valid and is_mock_fixture
            else (
                "Accepted as completed customer-shadow metadata row."
                if counts_toward_minimum
                else "Fill only derived metadata/anonymized summary/signoff fields; keep raw data customer-retained."
            )
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _build_work_order_rows(
    *,
    missing_case_count: int,
    completed_case_count: int,
    intake_csv: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    required_fields = sorted(REQUIRED_DERIVED_METADATA_FIELDS)
    for offset in range(missing_case_count):
        slot_number = completed_case_count + offset + 1
        rows.append(
            {
                "work_order_id": f"customer_shadow_case_slot_{slot_number}",
                "case_slot_id": f"customer_shadow_case_{slot_number}",
                "status": "missing_customer_shadow_evidence",
                "required_row_kind": "customer_shadow",
                "operator_csv": intake_csv,
                "required_action": (
                    "Add one reviewed real customer-shadow metadata row; keep raw data "
                    "customer-retained and out of repo."
                ),
                "required_raw_data_custody": "customer_retained",
                "required_customer_retained_raw_data": True,
                "required_redistribution_allowed": False,
                "required_raw_data_stored_in_repo": False,
                "required_derived_metadata_fields": required_fields,
                "required_anonymized_result_summary": (
                    "At least 24 characters, aggregate only, with no email or private identifiers."
                ),
                "required_reviewer_signoff_status": "approved",
                "required_reviewer_id": "non-empty reviewer id",
                "required_reviewed_at_utc": "timezone-aware ISO timestamp",
                "required_source_artifact_fingerprint": "sha256",
                "execution_enabled": False,
                "external_state_mutated": False,
                "paid_pilot_claim_allowed": False,
                "commercial_readiness_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def _paid_pilot_requirement_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    required = _int(summary.get("required_completed_customer_shadow_case_count")) or MIN_COMPLETED_CASES
    next_required_step = _text(summary.get("next_required_step"))
    summary_present = bool(summary)
    rows: list[dict[str, Any]] = []

    def count_row(
        requirement_id: str,
        observed_key: str,
        blocker_id: str,
        operator_action: str,
    ) -> None:
        observed = _int(summary.get(observed_key))
        ready = summary_present and observed >= required
        rows.append(
            {
                "requirement_id": requirement_id,
                "requirement_type": "minimum_count",
                "ready": ready,
                "observed_count": observed,
                "required_count": required,
                "observed_value": str(observed),
                "required_value": str(required),
                "blocker": "" if ready else f"{blocker_id}:{observed}/{required}",
                "operator_action": "" if ready else operator_action,
                "paid_pilot_wording_allowed": False,
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )

    def bool_row(
        requirement_id: str,
        ready: bool,
        observed_value: Any,
        required_value: Any,
        blocker_id: str,
        operator_action: str,
    ) -> None:
        rows.append(
            {
                "requirement_id": requirement_id,
                "requirement_type": "boolean",
                "ready": ready,
                "observed_count": 1 if ready else 0,
                "required_count": 1,
                "observed_value": str(observed_value).lower(),
                "required_value": str(required_value).lower(),
                "blocker": "" if ready else blocker_id,
                "operator_action": "" if ready else operator_action,
                "paid_pilot_wording_allowed": False,
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )

    bool_row(
        "customer_shadow_intake_schema_ready",
        summary_present and summary.get("customer_shadow_intake_schema_ready") is True,
        summary.get("customer_shadow_intake_schema_ready"),
        True,
        "customer_shadow_intake_schema_not_ready",
        "Rebuild the customer-shadow evidence status with the required intake schema.",
    )
    count_row(
        "completed_customer_shadow_cases",
        "completed_customer_shadow_case_count",
        "completed_customer_shadow_cases_below_required",
        "Collect reviewed customer-shadow rows that count toward the minimum.",
    )
    count_row(
        "real_customer_shadow_rows",
        "real_customer_shadow_row_count",
        "real_customer_shadow_rows_below_required",
        "Replace mock or placeholder rows with real reviewed customer-shadow rows.",
    )
    count_row(
        "customer_retained_raw_data",
        "customer_retained_raw_data_count",
        "customer_retained_raw_data_rows_below_required",
        "Keep customer raw data customer-retained and record only derived metadata.",
    )
    count_row(
        "redistribution_allowed_false",
        "redistribution_allowed_false_count",
        "redistribution_false_rows_below_required",
        "Set redistribution_allowed=false on every counted customer-shadow row.",
    )
    count_row(
        "anonymized_result_summary",
        "anonymized_result_summary_count",
        "anonymized_summary_rows_below_required",
        "Attach anonymized result summaries for counted customer-shadow rows.",
    )
    count_row(
        "reviewer_signoff",
        "reviewer_signoff_count",
        "reviewer_signoff_rows_below_required",
        "Add reviewer signoff for each counted customer-shadow row.",
    )
    bool_row(
        "no_invalid_customer_shadow_rows",
        summary_present and _int(summary.get("invalid_row_count")) == 0,
        _int(summary.get("invalid_row_count")),
        0,
        f"invalid_customer_shadow_rows:{_int(summary.get('invalid_row_count'))}",
        "Repair invalid customer-shadow rows before paid pilot wording.",
    )
    bool_row(
        "customer_raw_data_not_stored_in_repo",
        summary_present and summary.get("customer_raw_data_stored_in_repo") is False,
        summary.get("customer_raw_data_stored_in_repo"),
        False,
        "customer_raw_data_stored_in_repo",
        "Remove customer raw data from repo-managed artifacts and retain it with the customer.",
    )
    bool_row(
        "redistribution_allowed_required_value_false",
        summary_present and summary.get("redistribution_allowed_required_value") is False,
        summary.get("redistribution_allowed_required_value"),
        False,
        "redistribution_allowed_required_value_not_false",
        "Keep the required redistribution_allowed value set to false.",
    )
    bool_row(
        "customer_shadow_work_order_closed",
        summary_present and _int(summary.get("customer_shadow_work_order_row_count")) == 0,
        _int(summary.get("customer_shadow_work_order_row_count")),
        0,
        f"customer_shadow_work_order_rows_open:{_int(summary.get('customer_shadow_work_order_row_count'))}",
        next_required_step or "Close all customer-shadow work-order rows.",
    )
    bool_row(
        "paid_pilot_evidence_ready",
        summary.get("paid_pilot_evidence_ready") is True,
        summary.get("paid_pilot_evidence_ready"),
        True,
        "paid_pilot_evidence_not_ready",
        next_required_step or "Complete paid-pilot customer-shadow evidence.",
    )
    bool_row(
        "paid_pilot_claim_allowed",
        summary.get("paid_pilot_claim_allowed") is True,
        summary.get("paid_pilot_claim_allowed"),
        True,
        "paid_pilot_claim_not_approved",
        "Keep paid pilot wording disabled until review explicitly approves the claim.",
    )
    bool_row(
        "commercial_readiness_promotion_allowed",
        summary.get("commercial_readiness_promotion_allowed") is True,
        summary.get("commercial_readiness_promotion_allowed"),
        True,
        "commercial_readiness_promotion_not_approved",
        "Keep commercial readiness promotion disabled until reviewed evidence passes.",
    )
    return rows


def build_customer_shadow_evidence_status(
    *,
    intake_csv: str = DEFAULT_INTAKE_CSV,
    root: Path = ROOT,
    min_completed_cases: int = MIN_COMPLETED_CASES,
) -> dict[str, Any]:
    fieldnames, raw_rows = _read_csv(intake_csv, root=root)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    schema_ready = not missing_columns
    rows = [_row_status(row, row_index=index + 1, schema_ready=schema_ready) for index, row in enumerate(raw_rows)]
    real_customer_shadow_rows = [
        (raw_row, row)
        for raw_row, row in zip(raw_rows, rows)
        if row["row_kind"] == "customer_shadow" and not row["is_mock_fixture"]
    ]
    completed_case_count = sum(1 for row in rows if row["counts_toward_minimum"])
    mock_fixture_count = sum(1 for row in rows if row["is_mock_fixture"])
    invalid_row_count = sum(1 for row in rows if row["status"] != "pass")
    raw_data_stored_in_repo_observed = any(_bool(row.get("raw_data_stored_in_repo")) is True for row in raw_rows)
    customer_retained_raw_data_count = sum(
        1
        for raw_row, _row in real_customer_shadow_rows
        if _text(raw_row.get("raw_data_custody")).lower() == "customer_retained"
        and _bool(raw_row.get("customer_retained_raw_data")) is True
        and _bool(raw_row.get("raw_data_stored_in_repo")) is False
    )
    redistribution_allowed_false_count = sum(
        1 for raw_row, _row in real_customer_shadow_rows if _bool(raw_row.get("redistribution_allowed")) is False
    )
    anonymized_result_summary_count = sum(
        1
        for raw_row, _row in real_customer_shadow_rows
        if len(_text(raw_row.get("anonymized_result_summary"))) >= 24
        and not EMAIL_RE.search(_text(raw_row.get("anonymized_result_summary")))
    )
    reviewer_signoff_count = sum(
        1
        for raw_row, _row in real_customer_shadow_rows
        if _text(raw_row.get("reviewer_signoff_status")).lower() == "approved"
        and bool(_text(raw_row.get("reviewer_id")))
        and _reviewed_at_valid(raw_row.get("reviewed_at_utc"))
    )
    missing_case_count = max(0, min_completed_cases - completed_case_count)
    work_order_rows = _build_work_order_rows(
        missing_case_count=missing_case_count,
        completed_case_count=completed_case_count,
        intake_csv=intake_csv,
    )
    primary_work_order_row = work_order_rows[0] if work_order_rows else {}
    ready = schema_ready and invalid_row_count == 0 and completed_case_count >= min_completed_cases
    summary = {
        "packet_type": "customer_shadow_evidence_status",
        "status": "customer_shadow_evidence_status_ready" if ready else "blocked_customer_shadow_evidence_status",
        "customer_shadow_intake_schema_ready": schema_ready,
        "required_column_count": len(REQUIRED_COLUMNS),
        "missing_required_columns": missing_columns,
        "row_count": len(rows),
        "real_customer_shadow_row_count": len(real_customer_shadow_rows),
        "completed_customer_shadow_case_count": completed_case_count,
        "required_completed_customer_shadow_case_count": min_completed_cases,
        "missing_completed_customer_shadow_case_count": missing_case_count,
        "mock_fixture_row_count": mock_fixture_count,
        "invalid_row_count": invalid_row_count,
        "customer_retained_raw_data_count": customer_retained_raw_data_count,
        "redistribution_allowed_false_count": redistribution_allowed_false_count,
        "anonymized_result_summary_count": anonymized_result_summary_count,
        "reviewer_signoff_count": reviewer_signoff_count,
        "customer_shadow_minimum_met": completed_case_count >= min_completed_cases,
        "customer_shadow_work_order_ready": not work_order_rows,
        "customer_shadow_work_order_row_count": len(work_order_rows),
        "customer_shadow_work_order_missing_case_count": missing_case_count,
        "customer_shadow_work_order_primary_case_slot_id": _text(
            primary_work_order_row.get("case_slot_id")
        ),
        "customer_shadow_work_order_primary_required_action": _text(
            primary_work_order_row.get("required_action")
        ),
        "customer_shadow_work_order_primary_operator_csv": _text(
            primary_work_order_row.get("operator_csv")
        ),
        "customer_shadow_work_order_primary_required_row_kind": _text(
            primary_work_order_row.get("required_row_kind")
        ),
        "customer_shadow_work_order_primary_required_raw_data_custody": _text(
            primary_work_order_row.get("required_raw_data_custody")
        ),
        "customer_shadow_work_order_primary_required_customer_retained_raw_data": (
            primary_work_order_row.get("required_customer_retained_raw_data") is True
        ),
        "customer_shadow_work_order_primary_required_redistribution_allowed": (
            primary_work_order_row.get("required_redistribution_allowed") is True
        ),
        "customer_shadow_work_order_primary_required_raw_data_stored_in_repo": (
            primary_work_order_row.get("required_raw_data_stored_in_repo") is True
        ),
        "customer_shadow_work_order_primary_required_derived_metadata_fields": list(
            primary_work_order_row.get("required_derived_metadata_fields", [])
        ),
        "customer_shadow_work_order_primary_required_reviewer_signoff_status": _text(
            primary_work_order_row.get("required_reviewer_signoff_status")
        ),
        "customer_shadow_work_order_primary_required_source_artifact_fingerprint": _text(
            primary_work_order_row.get("required_source_artifact_fingerprint")
        ),
        "customer_raw_data_stored_in_repo": raw_data_stored_in_repo_observed,
        "redistribution_allowed_required_value": False,
        "paid_pilot_evidence_ready": ready,
        "paid_pilot_claim_allowed": False,
        "commercial_readiness_promotion_allowed": False,
        "readiness_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Keep the schema frozen and review the three completed customer-shadow rows."
            if ready
            else "Collect three real customer-shadow rows with customer-retained raw data, redistribution_allowed=false, derived metadata, anonymized summaries, and reviewer signoff."
        ),
    }
    blockers = [row for row in rows if row["status"] != "pass"]
    if not schema_ready:
        blockers.append(
            {
                "case_id": "schema",
                "row_kind": "schema",
                "status": "fail",
                "blockers": "missing_required_columns:" + ",".join(missing_columns),
                "blocker_count": len(missing_columns),
                "counts_toward_minimum": False,
                "is_mock_fixture": False,
                "next_action": "Add the missing required intake columns.",
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    if missing_case_count:
        blockers.append(
            {
                "case_id": "minimum_completed_cases",
                "row_kind": "minimum",
                "status": "fail",
                "blockers": f"missing_completed_customer_shadow_case_count:{missing_case_count}",
                "blocker_count": 1,
                "counts_toward_minimum": False,
                "is_mock_fixture": False,
                "next_action": "Add reviewed real customer-shadow metadata rows; mock fixtures do not count.",
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    summary["blocker_count"] = len(blockers)
    paid_pilot_requirement_rows = _paid_pilot_requirement_rows(summary)
    paid_pilot_requirement_blocked_rows = [
        row for row in paid_pilot_requirement_rows if not row["ready"]
    ]
    paid_pilot_requirement_primary_row = (
        paid_pilot_requirement_blocked_rows[0]
        if paid_pilot_requirement_blocked_rows
        else {}
    )
    summary.update(
        {
            "paid_pilot_requirement_ids": list(PAID_PILOT_REQUIREMENT_IDS),
            "paid_pilot_requirement_row_count": len(paid_pilot_requirement_rows),
            "paid_pilot_requirement_ready_row_count": (
                len(paid_pilot_requirement_rows) - len(paid_pilot_requirement_blocked_rows)
            ),
            "paid_pilot_requirement_blocked_row_count": len(
                paid_pilot_requirement_blocked_rows
            ),
            "paid_pilot_requirement_primary_id": _text(
                paid_pilot_requirement_primary_row.get("requirement_id")
            ),
            "paid_pilot_requirement_primary_blocker": _text(
                paid_pilot_requirement_primary_row.get("blocker")
            ),
            "paid_pilot_requirement_primary_action": _text(
                paid_pilot_requirement_primary_row.get("operator_action")
            ),
        }
    )
    return {
        "summary": summary,
        "rows": rows,
        "blockers": blockers,
        "customer_shadow_work_order_rows": work_order_rows,
        "paid_pilot_requirement_rows": paid_pilot_requirement_rows,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Customer Shadow Evidence Status",
        "",
        f"- status: `{s['status']}`",
        f"- customer_shadow_intake_schema_ready: `{s['customer_shadow_intake_schema_ready']}`",
        f"- real_customer_shadow_row_count: `{s['real_customer_shadow_row_count']}`",
        f"- completed_customer_shadow_case_count: `{s['completed_customer_shadow_case_count']}`",
        f"- required_completed_customer_shadow_case_count: `{s['required_completed_customer_shadow_case_count']}`",
        f"- missing_completed_customer_shadow_case_count: `{s['missing_completed_customer_shadow_case_count']}`",
        f"- mock_fixture_row_count: `{s['mock_fixture_row_count']}`",
        f"- invalid_row_count: `{s['invalid_row_count']}`",
        f"- customer_retained_raw_data_count: `{s['customer_retained_raw_data_count']}`",
        f"- redistribution_allowed_false_count: `{s['redistribution_allowed_false_count']}`",
        f"- anonymized_result_summary_count: `{s['anonymized_result_summary_count']}`",
        f"- reviewer_signoff_count: `{s['reviewer_signoff_count']}`",
        f"- customer_shadow_work_order_ready: `{s['customer_shadow_work_order_ready']}`",
        f"- customer_shadow_work_order_row_count: `{s['customer_shadow_work_order_row_count']}`",
        f"- customer_shadow_work_order_primary_case_slot_id: `{s['customer_shadow_work_order_primary_case_slot_id']}`",
        f"- customer_shadow_work_order_primary_operator_csv: `{s['customer_shadow_work_order_primary_operator_csv']}`",
        f"- customer_shadow_work_order_primary_required_raw_data_custody: `{s['customer_shadow_work_order_primary_required_raw_data_custody']}`",
        f"- customer_shadow_work_order_primary_required_redistribution_allowed: `{s['customer_shadow_work_order_primary_required_redistribution_allowed']}`",
        f"- paid_pilot_requirement_blocked_row_count: `{s['paid_pilot_requirement_blocked_row_count']}`",
        f"- paid_pilot_requirement_primary_id: `{s['paid_pilot_requirement_primary_id']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- commercial_readiness_promotion_allowed: `{s['commercial_readiness_promotion_allowed']}`",
        "",
        "## Rows",
        "",
        "| case | kind | status | counts | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['row_kind']}` | `{row['status']}` | `{row['counts_toward_minimum']}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Customer Shadow Work Order",
            "",
            "| slot | status | row kind | raw custody | redistribution | required action | operator csv |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["customer_shadow_work_order_rows"]:
        lines.append(
            f"| `{row['case_slot_id']}` | `{row['status']}` | `{row['required_row_kind']}` | "
            f"`{row['required_raw_data_custody']}` | `{row['required_redistribution_allowed']}` | "
            f"{row['required_action']} | `{row['operator_csv']}` |"
        )
    lines.extend(
        [
            "",
            "## Paid Pilot Requirement Checklist",
            "",
            "| requirement | ready | observed | required | blocker | action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["paid_pilot_requirement_rows"]:
        lines.append(
            f"| `{row['requirement_id']}` | `{row['ready']}` | `{row['observed_value']}` | "
            f"`{row['required_value']}` | `{row['blocker'] or '-'}` | {row['operator_action'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build customer shadow evidence intake status.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--min-completed-cases", type=int, default=MIN_COMPLETED_CASES)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_customer_shadow_evidence_status(
        intake_csv=args.intake_csv,
        min_completed_cases=args.min_completed_cases,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
