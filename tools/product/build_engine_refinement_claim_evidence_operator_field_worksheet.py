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
    DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON,
    DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_JSON,
    DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_JSON,
    DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_JSON,
    DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_JSON,
    DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
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
from tools.product.build_refine_tier_public_benchmark_readiness import (
    DEFAULT_OUT_METRIC_EVIDENCE_CSV as DEFAULT_PUBLIC_BENCHMARK_METRIC_EVIDENCE_CSV,
    DEFAULT_OUT_RECEPTOR_COORDINATE_INTAKE_CSV as DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_INTAKE_CSV,
    DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV as DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_VALIDATION_CSV,
    METRIC_EVIDENCE_COLUMNS,
    RECEPTOR_COORDINATE_INTAKE_COLUMNS,
    RECEPTOR_COORDINATE_VALIDATION_COLUMNS,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt import (
    DEFAULT_OUT_JSON as DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_JSON,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    DEFAULT_OUT_JSON as DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON,
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
    "dockq_source_artifact",
    "lddt_pli_source_artifact",
    "internal_deltaG_source_artifact",
    "deltaG_experimental_kcal_mol",
]
STATISTICAL_SUPPORT_FALLBACK_FIELDS = [
    "benchmark_id",
    "target_id",
    "split",
    "license_ok",
    "pose_rmsd_A",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "dockq_source_artifact",
    "lddt_pli_source_artifact",
    "internal_deltaG_source_artifact",
    "deltaG_experimental_kcal_mol",
    "receptor_coordinate_artifact",
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
    "dockq_source_artifact": "Point to the local reviewed artifact used to compute or verify DockQ.",
    "lddt_pli_source_artifact": "Point to the local reviewed artifact used to compute or verify lDDT-PLI.",
    "internal_deltaG_source_artifact": "Point to the local reviewed artifact used to compute or verify internal refine ΔG.",
    "deltaG_experimental_kcal_mol": "Fill the public experimental free-energy value.",
    "split": "Keep the required split for this statistical-support expansion slot.",
    "receptor_coordinate_artifact": "Point to the validated public receptor or complex coordinate artifact.",
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


def _rows_by_work_order_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("work_order_id")): row
        for row in rows
        if _text(row.get("work_order_id"))
    }


def _count_rows_with_value(rows: list[dict[str, Any]], field_name: str, expected: str) -> int:
    return len([row for row in rows if _text(row.get(field_name)) == expected])


def _count_rows_without_true(rows: list[dict[str, Any]], field_name: str) -> int:
    return len([row for row in rows if not _bool_text(row.get(field_name))])


def _split_nonempty(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _count_rows_with_missing_required_metric_inputs(rows: list[dict[str, Any]]) -> int:
    return len([row for row in rows if _text(row.get("missing_required_metric_input_artifacts"))])


def _count_rows_with_missing_required_metric_input_hashes(rows: list[dict[str, Any]]) -> int:
    blocked_rows = []
    for row in rows:
        required_artifacts = _split_nonempty(row.get("required_metric_input_artifacts"))
        required_hashes = _split_nonempty(row.get("required_metric_input_artifact_sha256s"))
        if required_artifacts and len(required_hashes) < len(required_artifacts):
            blocked_rows.append(row)
    return len(blocked_rows)


def _materialized_metric_ready(materialization: dict[str, Any]) -> bool:
    row_count = _int(materialization.get("materialized_row_count"))
    return bool(
        _text(materialization.get("status")) == "refine_tier_public_benchmark_metric_sources_materialized"
        and row_count > 0
        and _int(materialization.get("blocked_row_count")) == 0
        and _int(materialization.get("metric_evidence_pass_row_count")) >= row_count
        and materialization.get("free_energy_spearman_gate_ready") is True
        and _int(materialization.get("external_engine_calls")) == 0
        and materialization.get("external_state_mutated") is False
    )


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
    if field_name in {"dockq_source_artifact", "lddt_pli_source_artifact", "internal_deltaG_source_artifact"}:
        return "local reviewed metric evidence artifact path"
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
    receptor_intake_row: dict[str, Any],
    receptor_validation_row: dict[str, Any],
    metric_evidence_row: dict[str, Any],
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
        "receptor_coordinate_intake_current_artifact": _text(
            receptor_intake_row.get("current_receptor_coordinate_artifact")
        ),
        "receptor_coordinate_intake_artifact_present": _bool_text(
            receptor_intake_row.get("receptor_coordinate_artifact_present")
        ),
        "receptor_coordinate_accepted_offline_coordinate_patterns": _text(
            receptor_intake_row.get("accepted_offline_coordinate_patterns")
        ),
        "receptor_coordinate_expected_archive_member_examples": _text(
            receptor_intake_row.get("expected_archive_member_examples")
        ),
        "receptor_coordinate_suggested_public_coordinate_urls": _text(
            receptor_intake_row.get("suggested_public_coordinate_urls")
        ),
        "receptor_coordinate_suggested_local_coordinate_paths": _text(
            receptor_intake_row.get("suggested_local_coordinate_paths")
        ),
        "receptor_coordinate_operator_source_review_required": _text(
            receptor_intake_row.get("operator_coordinate_source_review_required")
        ),
        "receptor_coordinate_intake_next_operator_action": _text(
            receptor_intake_row.get("next_operator_action")
        ),
        "receptor_coordinate_validation_status": _text(
            receptor_validation_row.get("coordinate_validation_status")
        ),
        "receptor_coordinate_validation_blockers": _text(receptor_validation_row.get("blockers")),
        "receptor_coordinate_artifact": _text(receptor_validation_row.get("receptor_coordinate_artifact")),
        "receptor_coordinate_artifact_present": _bool_text(
            receptor_validation_row.get("receptor_coordinate_artifact_present")
        ),
        "receptor_coordinate_next_required_science_input": _text(
            receptor_validation_row.get("next_required_science_input")
        ),
        "metric_evidence_status": _text(metric_evidence_row.get("metric_evidence_status")),
        "metric_evidence_blockers": _text(metric_evidence_row.get("blockers")),
        "metric_next_required_science_input": _text(metric_evidence_row.get("next_required_science_input")),
        "metric_expected_dockq_source_artifact": _text(
            metric_evidence_row.get("expected_dockq_source_artifact")
        ),
        "metric_expected_lddt_pli_source_artifact": _text(
            metric_evidence_row.get("expected_lddt_pli_source_artifact")
        ),
        "metric_expected_internal_deltaG_source_artifact": _text(
            metric_evidence_row.get("expected_internal_deltaG_source_artifact")
        ),
        "metric_required_input_artifacts": _text(
            metric_evidence_row.get("required_metric_input_artifacts")
        ),
        "metric_required_input_artifact_sha256s": _text(
            metric_evidence_row.get("required_metric_input_artifact_sha256s")
        ),
        "metric_missing_required_input_artifacts": _text(
            metric_evidence_row.get("missing_required_metric_input_artifacts")
        ),
        "metric_required_source_payload_fields": _text(
            metric_evidence_row.get("required_metric_source_payload_fields")
        ),
        "metric_evidence_next_operator_action": _text(
            metric_evidence_row.get("metric_evidence_next_operator_action")
        ),
        "metric_dockq_source_artifact_present": _bool_text(
            metric_evidence_row.get("dockq_source_artifact_present")
        ),
        "metric_lddt_pli_source_artifact_present": _bool_text(
            metric_evidence_row.get("lddt_pli_source_artifact_present")
        ),
        "metric_internal_deltaG_source_artifact_present": _bool_text(
            metric_evidence_row.get("internal_deltaG_source_artifact_present")
        ),
        "metric_dockq_source_payload_valid": _bool_text(
            metric_evidence_row.get("dockq_source_payload_valid")
        ),
        "metric_lddt_pli_source_payload_valid": _bool_text(
            metric_evidence_row.get("lddt_pli_source_payload_valid")
        ),
        "metric_internal_deltaG_source_payload_valid": _bool_text(
            metric_evidence_row.get("internal_deltaG_source_payload_valid")
        ),
        "metric_dockq_source_payload_blockers": _text(
            metric_evidence_row.get("dockq_source_payload_blockers")
        ),
        "metric_lddt_pli_source_payload_blockers": _text(
            metric_evidence_row.get("lddt_pli_source_payload_blockers")
        ),
        "metric_internal_deltaG_source_payload_blockers": _text(
            metric_evidence_row.get("internal_deltaG_source_payload_blockers")
        ),
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


def _statistical_support_fields(row: dict[str, Any]) -> list[str]:
    fields = _split_nonempty(row.get("required_fields"))
    return fields or list(STATISTICAL_SUPPORT_FALLBACK_FIELDS)


def _statistical_support_current_value(field_name: str, slot_row: dict[str, Any]) -> str:
    if field_name == "split":
        return _text(slot_row.get("required_split"))
    return ""


def _expected_statistical_support_value(field_name: str, slot_row: dict[str, Any]) -> str:
    if field_name == "split":
        return _text(slot_row.get("required_split")) or "fit_or_holdout or holdout"
    if field_name == "receptor_coordinate_artifact":
        return "validated public receptor or complex coordinate artifact path"
    if field_name in {"dockq_source_artifact", "lddt_pli_source_artifact", "internal_deltaG_source_artifact"}:
        return "schema-valid local metric source JSON path"
    return _expected_work_order_value(field_name)


def _statistical_support_field_status(field_name: str, value: Any) -> tuple[str, str]:
    if field_name == "split":
        return ("ready", "") if _text(value) else ("operator_fill_pending", "required_split_missing")
    return _work_order_field_status(field_name, value)


def _statistical_support_expansion_field_row(
    field_name: str,
    *,
    row_index: int,
    slot_row: dict[str, Any],
    priority_summary: dict[str, Any],
    statistical_support_summary: dict[str, Any],
) -> dict[str, Any]:
    slot_id = _text(slot_row.get("expansion_slot_id")) or f"stat_support_expansion_{row_index}"
    value = _statistical_support_current_value(field_name, slot_row)
    status, blocker = _statistical_support_field_status(field_name, value)
    return {
        "worksheet_section": "public_benchmark_statistical_support_expansion",
        "source_row_id": slot_id,
        "source_row_index": row_index,
        "field_name": field_name,
        "gate_id": "public_benchmark_statistical_support_not_claim_grade",
        "receipt_column_present": True,
        "required_for_operator_receipt": False,
        "top_blocker_field": True,
        "current_value": value,
        "observed_source_value": _text(statistical_support_summary.get("status")),
        "expected_value_hint": _expected_statistical_support_value(field_name, slot_row),
        "expected_true_fields": "claim_grade_public_benchmark_statistical_support_ready",
        "field_status": status,
        "blocker": blocker,
        "operator_input_required": status == "operator_fill_pending",
        "top_blocker_id": _text(priority_summary.get("top_blocker_id")),
        "top_priority_bucket": _text(priority_summary.get("top_priority_bucket")),
        "required_split": _text(slot_row.get("required_split")),
        "required_benchmark_family": _text(slot_row.get("required_benchmark_family")),
        "required_new_pair_count_credit": _int(slot_row.get("required_new_pair_count_credit")),
        "required_holdout_pair_count_credit": _int(slot_row.get("required_holdout_pair_count_credit")),
        "required_metric_source_payloads": _text(slot_row.get("required_metric_source_payloads")),
        "acceptance_rule": _text(slot_row.get("acceptance_rule")),
        "operator_action": FIELD_ACTIONS.get(field_name) or _text(slot_row.get("operator_action")),
        "canonical_intake_promotion_allowed": _bool_text(
            slot_row.get("canonical_intake_promotion_allowed")
        ),
        "external_engine_calls_allowed": _bool_text(slot_row.get("external_engine_calls_allowed")),
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
    public_benchmark_materialization_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    public_benchmark_materialized_work_order_csv: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    public_benchmark_materialized_apply_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    public_benchmark_statistical_support_work_order_json: str | Path = (
        DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON
    ),
    public_benchmark_statistical_support_metric_materialization_readiness_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_JSON,
    public_benchmark_statistical_support_coordinate_intake_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_JSON,
    public_benchmark_statistical_support_metric_source_templates_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_JSON,
    public_benchmark_statistical_support_metric_source_payload_operator_receipt_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON,
    public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_JSON,
    public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_JSON,
    public_benchmark_receptor_coordinate_intake_csv: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_INTAKE_CSV,
    public_benchmark_receptor_coordinate_validation_csv: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_VALIDATION_CSV,
    public_benchmark_metric_evidence_csv: str | Path = DEFAULT_PUBLIC_BENCHMARK_METRIC_EVIDENCE_CSV,
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
    materialization_packet, materialization_present = _read_json(
        public_benchmark_materialization_json,
        root=root_path,
    )
    materialized_work_order_rows, _, materialized_work_order_present = _read_csv(
        public_benchmark_materialized_work_order_csv,
        root=root_path,
        required_columns=WORK_ORDER_OPERATOR_FIELDS,
    )
    materialized_apply_packet, materialized_apply_present = _read_json(
        public_benchmark_materialized_apply_json,
        root=root_path,
    )
    statistical_support_work_order_packet, statistical_support_work_order_present = _read_json(
        public_benchmark_statistical_support_work_order_json,
        root=root_path,
    )
    (
        statistical_support_metric_materialization_packet,
        statistical_support_metric_materialization_present,
    ) = _read_json(
        public_benchmark_statistical_support_metric_materialization_readiness_json,
        root=root_path,
    )
    (
        statistical_support_coordinate_intake_packet,
        statistical_support_coordinate_intake_present,
    ) = _read_json(
        public_benchmark_statistical_support_coordinate_intake_json,
        root=root_path,
    )
    (
        statistical_support_metric_source_templates_packet,
        statistical_support_metric_source_templates_present,
    ) = _read_json(
        public_benchmark_statistical_support_metric_source_templates_json,
        root=root_path,
    )
    (
        statistical_support_metric_source_payload_operator_receipt_packet,
        statistical_support_metric_source_payload_operator_receipt_present,
    ) = _read_json(
        public_benchmark_statistical_support_metric_source_payload_operator_receipt_json,
        root=root_path,
    )
    (
        statistical_support_coordinate_fetch_r4_packet,
        statistical_support_coordinate_fetch_r4_present,
    ) = _read_json(
        public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json,
        root=root_path,
    )
    (
        statistical_support_coordinate_fetch_operator_receipt_packet,
        statistical_support_coordinate_fetch_operator_receipt_present,
    ) = _read_json(
        public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json,
        root=root_path,
    )
    receptor_intake_rows, receptor_intake_missing_columns, receptor_intake_csv_present = _read_csv(
        public_benchmark_receptor_coordinate_intake_csv,
        root=root_path,
        required_columns=RECEPTOR_COORDINATE_INTAKE_COLUMNS,
    )
    receptor_validation_rows, receptor_validation_missing_columns, receptor_validation_csv_present = _read_csv(
        public_benchmark_receptor_coordinate_validation_csv,
        root=root_path,
        required_columns=RECEPTOR_COORDINATE_VALIDATION_COLUMNS,
    )
    metric_evidence_rows, metric_evidence_missing_columns, metric_evidence_csv_present = _read_csv(
        public_benchmark_metric_evidence_csv,
        root=root_path,
        required_columns=METRIC_EVIDENCE_COLUMNS,
    )
    receipt_summary = _summary(receipt_packet)
    priority_summary = _summary(priority_packet)
    public_summary = _summary(public_packet)
    work_order_apply_summary = _summary(work_order_apply_packet)
    materialization_summary = _summary(materialization_packet)
    materialized_apply_summary = _summary(materialized_apply_packet)
    statistical_support_work_order_summary = _summary(statistical_support_work_order_packet)
    statistical_support_metric_materialization_summary = _summary(
        statistical_support_metric_materialization_packet
    )
    statistical_support_coordinate_intake_summary = _summary(
        statistical_support_coordinate_intake_packet
    )
    statistical_support_metric_source_templates_summary = _summary(
        statistical_support_metric_source_templates_packet
    )
    statistical_support_metric_source_payload_operator_receipt_summary = _summary(
        statistical_support_metric_source_payload_operator_receipt_packet
    )
    statistical_support_coordinate_fetch_r4_summary = _summary(
        statistical_support_coordinate_fetch_r4_packet
    )
    statistical_support_coordinate_fetch_operator_receipt_summary = _summary(
        statistical_support_coordinate_fetch_operator_receipt_packet
    )
    materialized_metric_ready = _materialized_metric_ready(materialization_summary)
    materialized_apply_ready = bool(materialized_apply_summary.get("apply_ready") is True)
    materialized_science_evidence_complete = bool(materialized_metric_ready and materialized_apply_ready)
    materialized_statistical_support_ready = bool(
        materialization_summary.get("claim_grade_public_benchmark_statistical_support_ready")
        is True
    )
    statistical_support_work_order_ready = bool(
        statistical_support_work_order_summary.get("work_order_ready") is True
    )
    statistical_support_metric_materialization_readiness_ready = bool(
        statistical_support_metric_materialization_summary.get("metric_materialization_readiness_ready")
        is True
    )
    statistical_support_coordinate_intake_ready = bool(
        statistical_support_coordinate_intake_summary.get("coordinate_intake_ready") is True
    )
    statistical_support_metric_source_templates_ready = bool(
        statistical_support_metric_source_templates_summary.get("metric_source_templates_ready")
        is True
    )
    statistical_support_metric_source_payload_operator_receipt_ready = bool(
        statistical_support_metric_source_payload_operator_receipt_summary.get("operator_receipt_ready")
        is True
    )
    statistical_support_coordinate_fetch_r4_preflight_ready = bool(
        statistical_support_coordinate_fetch_r4_summary.get("r4_preflight_ready") is True
    )
    statistical_support_coordinate_fetch_operator_receipt_ready = bool(
        statistical_support_coordinate_fetch_operator_receipt_summary.get("operator_receipt_ready")
        is True
    )
    receipt_report_by_blocker = {
        _text(row.get("blocker_id")): row for row in _rows(receipt_packet)
    }
    work_order_report_by_id = {
        _text(row.get("work_order_id")): row for row in _rows(work_order_apply_packet)
    }
    receptor_intake_by_work_order_id = _rows_by_work_order_id(receptor_intake_rows)
    receptor_validation_by_work_order_id = _rows_by_work_order_id(receptor_validation_rows)
    metric_evidence_by_work_order_id = _rows_by_work_order_id(metric_evidence_rows)
    missing_receptor_intake_work_order_count = len(
        [
            row
            for row in work_order_rows
            if _text(row.get("work_order_id")) not in receptor_intake_by_work_order_id
        ]
    )
    missing_receptor_validation_work_order_count = len(
        [
            row
            for row in work_order_rows
            if _text(row.get("work_order_id")) not in receptor_validation_by_work_order_id
        ]
    )
    missing_metric_evidence_work_order_count = len(
        [
            row
            for row in work_order_rows
            if _text(row.get("work_order_id")) not in metric_evidence_by_work_order_id
        ]
    )
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
            receptor_intake_row=receptor_intake_by_work_order_id.get(
                _text(work_order_row.get("work_order_id")),
                {},
            ),
            receptor_validation_row=receptor_validation_by_work_order_id.get(
                _text(work_order_row.get("work_order_id")),
                {},
            ),
            metric_evidence_row=metric_evidence_by_work_order_id.get(
                _text(work_order_row.get("work_order_id")),
                {},
            ),
            priority_summary=priority_summary,
        )
        for row_index, work_order_row in enumerate(work_order_rows, start=1)
        for field_name in WORK_ORDER_OPERATOR_FIELDS
    ]
    statistical_support_slot_rows = _rows(statistical_support_work_order_packet)
    statistical_support_expansion_field_rows = [
        _statistical_support_expansion_field_row(
            field_name,
            row_index=row_index,
            slot_row=slot_row,
            priority_summary=priority_summary,
            statistical_support_summary=statistical_support_work_order_summary,
        )
        for row_index, slot_row in enumerate(statistical_support_slot_rows, start=1)
        for field_name in _statistical_support_fields(slot_row)
    ]
    worksheet_rows = receipt_field_rows + work_order_field_rows + statistical_support_expansion_field_rows
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
    statistical_support_expansion_pending_rows = [
        row
        for row in statistical_support_expansion_field_rows
        if row["field_status"] == "operator_fill_pending"
    ]
    statistical_support_expansion_ready_rows = [
        row for row in statistical_support_expansion_field_rows if row["field_status"] == "ready"
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
    if not receptor_intake_csv_present:
        source_blockers.append("public_benchmark_receptor_coordinate_intake_csv_missing")
    if receptor_intake_missing_columns:
        source_blockers.append("public_benchmark_receptor_coordinate_intake_columns_missing")
    if work_order_rows and not receptor_intake_rows:
        source_blockers.append("public_benchmark_receptor_coordinate_intake_rows_missing")
    if missing_receptor_intake_work_order_count:
        source_blockers.append("public_benchmark_receptor_coordinate_intake_work_order_rows_missing")
    if not receptor_validation_csv_present:
        source_blockers.append("public_benchmark_receptor_coordinate_validation_csv_missing")
    if receptor_validation_missing_columns:
        source_blockers.append("public_benchmark_receptor_coordinate_validation_columns_missing")
    if work_order_rows and not receptor_validation_rows:
        source_blockers.append("public_benchmark_receptor_coordinate_validation_rows_missing")
    if missing_receptor_validation_work_order_count:
        source_blockers.append("public_benchmark_receptor_coordinate_validation_work_order_rows_missing")
    if not metric_evidence_csv_present:
        source_blockers.append("public_benchmark_metric_evidence_csv_missing")
    if metric_evidence_missing_columns:
        source_blockers.append("public_benchmark_metric_evidence_columns_missing")
    if work_order_rows and not metric_evidence_rows:
        source_blockers.append("public_benchmark_metric_evidence_rows_missing")
    if missing_metric_evidence_work_order_count:
        source_blockers.append("public_benchmark_metric_evidence_work_order_rows_missing")
    if (
        materialized_science_evidence_complete
        and not materialized_statistical_support_ready
        and not statistical_support_work_order_present
    ):
        source_blockers.append("public_benchmark_statistical_support_work_order_artifact_missing")
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and not statistical_support_metric_materialization_present
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_metric_materialization_readiness_missing"
        )
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and statistical_support_metric_materialization_present
        and not statistical_support_coordinate_intake_present
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_coordinate_intake_missing"
        )
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and statistical_support_coordinate_intake_present
        and not statistical_support_coordinate_intake_ready
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_coordinate_intake_not_ready"
        )
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and statistical_support_metric_materialization_present
        and not statistical_support_metric_source_templates_present
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_metric_source_templates_missing"
        )
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and statistical_support_metric_source_templates_present
        and not statistical_support_metric_source_templates_ready
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_metric_source_templates_not_ready"
        )
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and statistical_support_metric_source_templates_ready
        and not statistical_support_metric_source_payload_operator_receipt_present
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_missing"
        )
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and statistical_support_metric_materialization_present
        and not statistical_support_coordinate_fetch_r4_present
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_missing"
        )
    if (
        materialized_science_evidence_complete
        and statistical_support_work_order_ready
        and statistical_support_coordinate_fetch_r4_preflight_ready
        and not statistical_support_coordinate_fetch_operator_receipt_present
    ):
        source_blockers.append(
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_missing"
        )
    worksheet_ready = not source_blockers
    receptor_validation_pass_row_count = _count_rows_with_value(
        receptor_validation_rows,
        "coordinate_validation_status",
        "pass",
    )
    metric_evidence_pass_row_count = _count_rows_with_value(metric_evidence_rows, "metric_evidence_status", "pass")
    receptor_validation_blocked_row_count = _count_rows_with_value(
        receptor_validation_rows,
        "coordinate_validation_status",
        "blocked",
    )
    metric_evidence_blocked_row_count = _count_rows_with_value(
        metric_evidence_rows,
        "metric_evidence_status",
        "blocked",
    )
    metric_evidence_missing_required_input_artifact_row_count = (
        _count_rows_with_missing_required_metric_inputs(metric_evidence_rows)
    )
    metric_evidence_missing_required_input_artifact_sha256_row_count = (
        _count_rows_with_missing_required_metric_input_hashes(metric_evidence_rows)
    )
    science_evidence_complete = (
        bool(work_order_rows)
        and missing_receptor_validation_work_order_count == 0
        and missing_metric_evidence_work_order_count == 0
        and receptor_validation_blocked_row_count == 0
        and metric_evidence_blocked_row_count == 0
        and receptor_validation_pass_row_count >= len(work_order_rows)
        and metric_evidence_pass_row_count >= len(work_order_rows)
    )
    operator_fill_complete = worksheet_ready and not pending_rows and not invalid_rows and science_evidence_complete
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
        "public_benchmark_materialization_artifact": _display_path(
            public_benchmark_materialization_json,
            root=root_path,
        ),
        "public_benchmark_materialized_work_order_csv": _display_path(
            public_benchmark_materialized_work_order_csv,
            root=root_path,
        ),
        "public_benchmark_materialized_work_order_apply_artifact": _display_path(
            public_benchmark_materialized_apply_json,
            root=root_path,
        ),
        "public_benchmark_statistical_support_work_order_artifact": _display_path(
            public_benchmark_statistical_support_work_order_json,
            root=root_path,
        ),
        "public_benchmark_materialization_artifact_present": materialization_present,
        "public_benchmark_materialized_work_order_csv_present": materialized_work_order_present,
        "public_benchmark_materialized_work_order_apply_artifact_present": materialized_apply_present,
        "public_benchmark_statistical_support_work_order_artifact_present": (
            statistical_support_work_order_present
        ),
        "public_benchmark_statistical_support_work_order_ready": statistical_support_work_order_ready,
        "public_benchmark_statistical_support_work_order_status": _text(
            statistical_support_work_order_summary.get("status")
        ),
        "public_benchmark_statistical_support_work_order_expansion_slot_count": _int(
            statistical_support_work_order_summary.get("expansion_slot_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_pair_count": _int(
            statistical_support_work_order_summary.get("minimum_new_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count": _int(
            statistical_support_work_order_summary.get("minimum_new_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count": _int(
            statistical_support_work_order_summary.get("minimum_new_fit_or_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_bootstrap_spearman_p05_deficit": (
            statistical_support_work_order_summary.get("bootstrap_spearman_p05_deficit")
        ),
        "public_benchmark_statistical_support_work_order_bootstrap_retest_required": bool(
            statistical_support_work_order_summary.get("bootstrap_retest_required") is True
        ),
        "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed": bool(
            statistical_support_work_order_summary.get("canonical_intake_promotion_allowed") is True
        ),
        "public_benchmark_statistical_support_metric_materialization_readiness_artifact": (
            _display_path(
                public_benchmark_statistical_support_metric_materialization_readiness_json,
                root=root_path,
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_readiness_artifact_present": (
            statistical_support_metric_materialization_present
        ),
        "public_benchmark_statistical_support_metric_materialization_readiness_ready": (
            statistical_support_metric_materialization_readiness_ready
        ),
        "public_benchmark_statistical_support_metric_materialization_status": _text(
            statistical_support_metric_materialization_summary.get("status")
        ),
        "public_benchmark_statistical_support_metric_materialization_row_count": _int(
            statistical_support_metric_materialization_summary.get("metric_materialization_row_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_candidate_ready_count": _int(
            statistical_support_metric_materialization_summary.get(
                "metric_materialization_candidate_ready_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count": _int(
            statistical_support_metric_materialization_summary.get(
                "metric_materialization_candidate_blocked_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready": bool(
            statistical_support_metric_materialization_summary.get(
                "metric_materialization_input_artifact_contract_ready"
            )
            is True
        ),
        "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count": _int(
            statistical_support_metric_materialization_summary.get(
                "required_metric_input_artifact_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count": _int(
            statistical_support_metric_materialization_summary.get(
                "present_required_metric_input_artifact_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count": _int(
            statistical_support_metric_materialization_summary.get(
                "missing_required_metric_input_artifact_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count": _int(
            statistical_support_metric_materialization_summary.get(
                "missing_required_metric_input_artifact_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count": _int(
            statistical_support_metric_materialization_summary.get("coordinate_validation_pass_row_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count": _int(
            statistical_support_metric_materialization_summary.get(
                "coordinate_validation_blocked_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count": _int(
            statistical_support_metric_materialization_summary.get(
                "planned_metric_source_payload_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count": _int(
            statistical_support_metric_materialization_summary.get(
                "existing_metric_source_payload_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads": _text(
            statistical_support_metric_materialization_summary.get("required_metric_source_payloads")
        ),
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count": _int(
            statistical_support_metric_materialization_summary.get(
                "required_metric_source_payload_field_count"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields": _text(
            statistical_support_metric_materialization_summary.get(
                "required_metric_source_payload_fields"
            )
        ),
        "public_benchmark_statistical_support_metric_materialization_claim_grade_statistical_support_ready": bool(
            statistical_support_metric_materialization_summary.get(
                "claim_grade_statistical_support_ready"
            )
            is True
        ),
        "public_benchmark_statistical_support_metric_materialization_next_required_step": _text(
            statistical_support_metric_materialization_summary.get("next_required_step")
        ),
        "public_benchmark_statistical_support_coordinate_intake_artifact": (
            _display_path(
                public_benchmark_statistical_support_coordinate_intake_json,
                root=root_path,
            )
        ),
        "public_benchmark_statistical_support_coordinate_intake_artifact_present": (
            statistical_support_coordinate_intake_present
        ),
        "public_benchmark_statistical_support_coordinate_intake_ready": (
            statistical_support_coordinate_intake_ready
        ),
        "public_benchmark_statistical_support_coordinate_intake_status": _text(
            statistical_support_coordinate_intake_summary.get("status")
        ),
        "public_benchmark_statistical_support_coordinate_intake_row_count": _int(
            statistical_support_coordinate_intake_summary.get("coordinate_intake_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count": _int(
            statistical_support_coordinate_intake_summary.get(
                "coordinate_intake_artifact_present_row_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_intake_missing_row_count": _int(
            statistical_support_coordinate_intake_summary.get("coordinate_intake_missing_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count": _int(
            statistical_support_coordinate_intake_summary.get(
                "coordinate_intake_suggested_local_path_candidate_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count": _int(
            statistical_support_coordinate_intake_summary.get(
                "coordinate_intake_suggested_local_path_present_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count": _int(
            statistical_support_coordinate_intake_summary.get(
                "coordinate_intake_suggested_local_path_present_target_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count": _int(
            statistical_support_coordinate_intake_summary.get(
                "coordinate_intake_suggested_local_path_missing_target_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count": _int(
            statistical_support_coordinate_intake_summary.get(
                "coordinate_intake_expected_archive_member_example_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count": _int(
            statistical_support_coordinate_intake_summary.get("coordinate_validation_pass_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count": _int(
            statistical_support_coordinate_intake_summary.get(
                "coordinate_validation_blocked_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_artifact": (
            _display_path(
                public_benchmark_statistical_support_metric_source_templates_json,
                root=root_path,
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_artifact_present": (
            statistical_support_metric_source_templates_present
        ),
        "public_benchmark_statistical_support_metric_source_templates_ready": (
            statistical_support_metric_source_templates_ready
        ),
        "public_benchmark_statistical_support_metric_source_templates_status": _text(
            statistical_support_metric_source_templates_summary.get("status")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_row_count": _int(
            statistical_support_metric_source_templates_summary.get("template_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count": _int(
            statistical_support_metric_source_templates_summary.get("template_candidate_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_metric_name_count": _int(
            statistical_support_metric_source_templates_summary.get("template_metric_name_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_metric_source_artifact_path_row_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "template_metric_source_artifact_path_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_payload_required_fields_present_row_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "template_payload_required_fields_present_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "metric_source_payload_fill_ready_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "metric_source_payload_fill_blocked_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "coordinate_validation_blocked_template_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "missing_required_input_template_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "existing_metric_source_payload_present_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_value_count": _int(
            statistical_support_metric_source_templates_summary.get("placeholder_value_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_method_count": _int(
            statistical_support_metric_source_templates_summary.get("placeholder_method_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_operator_id_count": _int(
            statistical_support_metric_source_templates_summary.get("placeholder_operator_id_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_reviewed_at_utc_count": _int(
            statistical_support_metric_source_templates_summary.get(
                "placeholder_reviewed_at_utc_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_license_ok_count": _int(
            statistical_support_metric_source_templates_summary.get("placeholder_license_ok_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total": _int(
            statistical_support_metric_source_templates_summary.get("external_engine_calls_total")
        ),
        "public_benchmark_statistical_support_metric_source_templates_canonical_intake_promotion_allowed": bool(
            statistical_support_metric_source_templates_summary.get(
                "canonical_intake_promotion_allowed"
            )
            is True
        ),
        "public_benchmark_statistical_support_metric_source_templates_next_required_step": _text(
            statistical_support_metric_source_templates_summary.get("next_required_step")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact": (
            _display_path(
                public_benchmark_statistical_support_metric_source_payload_operator_receipt_json,
                root=root_path,
            )
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact_present": (
            statistical_support_metric_source_payload_operator_receipt_present
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": (
            statistical_support_metric_source_payload_operator_receipt_ready
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": _text(
            statistical_support_metric_source_payload_operator_receipt_summary.get("status")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv_present": bool(
            statistical_support_metric_source_payload_operator_receipt_summary.get("receipt_csv_present")
            is True
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get("receipt_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get("required_template_count")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get("pass_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get("blocked_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get("approved_payload_count")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get(
                "coordinate_validation_pass_payload_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get(
                "coordinate_validation_blocked_payload_row_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required": bool(
            statistical_support_metric_source_payload_operator_receipt_summary.get(
                "metric_source_template_row_fingerprint_required"
            )
            is True
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get(
                "metric_source_template_row_fingerprint_verified_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get(
                "metric_source_template_row_fingerprint_mismatch_count"
            )
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed": bool(
            statistical_support_metric_source_payload_operator_receipt_summary.get("payload_write_allowed")
            is True
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_canonical_intake_promotion_allowed": bool(
            statistical_support_metric_source_payload_operator_receipt_summary.get(
                "canonical_intake_promotion_allowed"
            )
            is True
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_claim_promotion_allowed": bool(
            statistical_support_metric_source_payload_operator_receipt_summary.get("claim_promotion_allowed")
            is True
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_state_mutated": bool(
            statistical_support_metric_source_payload_operator_receipt_summary.get("external_state_mutated")
            is True
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": _text(
            statistical_support_metric_source_payload_operator_receipt_summary.get("first_blocked_template_id")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name": _text(
            statistical_support_metric_source_payload_operator_receipt_summary.get("first_blocked_metric_name")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": _text(
            statistical_support_metric_source_payload_operator_receipt_summary.get("most_common_row_blocker")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": _text(
            statistical_support_metric_source_payload_operator_receipt_summary.get("approval_token_required")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count": _int(
            statistical_support_metric_source_payload_operator_receipt_summary.get("blocker_count")
        ),
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_next_required_step": _text(
            statistical_support_metric_source_payload_operator_receipt_summary.get("next_required_step")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_artifact": (
            _display_path(
                public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json,
                root=root_path,
            )
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_artifact_present": (
            statistical_support_coordinate_fetch_r4_present
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready": (
            statistical_support_coordinate_fetch_r4_preflight_ready
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status": _text(
            statistical_support_coordinate_fetch_r4_summary.get("status")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_row_count": _int(
            statistical_support_coordinate_fetch_r4_summary.get("r4_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count": _int(
            statistical_support_coordinate_fetch_r4_summary.get("ready_for_r4_review_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count": _int(
            statistical_support_coordinate_fetch_r4_summary.get("blocked_r4_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count": _int(
            statistical_support_coordinate_fetch_r4_summary.get("fetch_required_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count": _int(
            statistical_support_coordinate_fetch_r4_summary.get(
                "metric_materialization_blocked_row_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count": _int(
            statistical_support_coordinate_fetch_r4_summary.get(
                "planned_metric_source_payload_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download": bool(
            statistical_support_coordinate_fetch_r4_summary.get("authorized_for_external_download")
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_download_executed": bool(
            statistical_support_coordinate_fetch_r4_summary.get("download_executed") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated": bool(
            statistical_support_coordinate_fetch_r4_summary.get("external_state_mutated") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required": _text(
            statistical_support_coordinate_fetch_r4_summary.get("approval_token_required")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_execute_command": _text(
            statistical_support_coordinate_fetch_r4_summary.get("execute_command")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact": (
            _display_path(
                public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json,
                root=root_path,
            )
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact_present": (
            statistical_support_coordinate_fetch_operator_receipt_present
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready": (
            statistical_support_coordinate_fetch_operator_receipt_ready
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("status")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_csv_present": bool(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("receipt_csv_present")
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("receipt_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("required_r4_review_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("pass_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("blocked_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("approved_fetch_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required": bool(
            statistical_support_coordinate_fetch_operator_receipt_summary.get(
                "r4_preflight_row_fingerprint_required"
            )
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get(
                "r4_preflight_row_fingerprint_verified_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get(
                "r4_preflight_row_fingerprint_mismatch_count"
            )
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download": bool(
            statistical_support_coordinate_fetch_operator_receipt_summary.get(
                "authorized_for_external_download"
            )
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed": bool(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("download_executed")
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_canonical_intake_promotion_allowed": bool(
            statistical_support_coordinate_fetch_operator_receipt_summary.get(
                "canonical_intake_promotion_allowed"
            )
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_claim_promotion_allowed": bool(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("claim_promotion_allowed")
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_external_state_mutated": bool(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("external_state_mutated")
            is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("first_blocked_review_id")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("first_blocked_target_id")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("first_blocked_pose_id")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("most_common_row_blocker")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("approval_token_required")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_execute_command": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("execute_command")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count": _int(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("blocker_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_next_required_step": _text(
            statistical_support_coordinate_fetch_operator_receipt_summary.get("next_required_step")
        ),
        "public_benchmark_statistical_support_expansion_slot_row_count": len(
            statistical_support_slot_rows
        ),
        "public_benchmark_statistical_support_expansion_holdout_slot_count": len(
            [
                row
                for row in statistical_support_slot_rows
                if _text(row.get("required_split")) == "holdout"
            ]
        ),
        "public_benchmark_statistical_support_expansion_fit_or_holdout_slot_count": len(
            [
                row
                for row in statistical_support_slot_rows
                if _text(row.get("required_split")) == "fit_or_holdout"
            ]
        ),
        "public_benchmark_statistical_support_expansion_field_count": len(
            statistical_support_expansion_field_rows
        ),
        "public_benchmark_statistical_support_expansion_pending_field_count": len(
            statistical_support_expansion_pending_rows
        ),
        "public_benchmark_statistical_support_expansion_ready_field_count": len(
            statistical_support_expansion_ready_rows
        ),
        "public_benchmark_materialized_metric_ready": materialized_metric_ready,
        "public_benchmark_materialized_apply_ready": materialized_apply_ready,
        "public_benchmark_materialized_science_evidence_complete": materialized_science_evidence_complete,
        "public_benchmark_materialized_work_order_row_count": len(materialized_work_order_rows),
        "public_benchmark_materialized_metric_evidence_pass_row_count": _int(
            materialization_summary.get("metric_evidence_pass_row_count")
        ),
        "public_benchmark_materialized_metric_evidence_blocked_row_count": _int(
            materialization_summary.get("metric_evidence_blocked_row_count")
        ),
        "public_benchmark_materialized_free_energy_pair_count": _int(
            materialization_summary.get("free_energy_pair_count")
        ),
        "public_benchmark_materialized_free_energy_spearman": materialization_summary.get(
            "free_energy_spearman"
        ),
        "public_benchmark_materialized_free_energy_spearman_gate_ready": bool(
            materialization_summary.get("free_energy_spearman_gate_ready") is True
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p05": materialization_summary.get(
            "free_energy_spearman_bootstrap_p05"
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p50": materialization_summary.get(
            "free_energy_spearman_bootstrap_p50"
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p95": materialization_summary.get(
            "free_energy_spearman_bootstrap_p95"
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_ready": bool(
            materialization_summary.get("claim_grade_public_benchmark_statistical_support_ready")
            is True
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blocker_count": _int(
            materialization_summary.get("claim_grade_public_benchmark_statistical_support_blocker_count")
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blockers": (
            materialization_summary.get("claim_grade_public_benchmark_statistical_support_blockers") or []
        ),
        "public_benchmark_materialized_apply_status": _text(materialized_apply_summary.get("status")),
        "public_benchmark_materialized_apply_blocked_row_count": _int(
            materialized_apply_summary.get("blocked_row_count")
        ),
        "public_benchmark_receptor_coordinate_intake_csv": _display_path(
            public_benchmark_receptor_coordinate_intake_csv,
            root=root_path,
        ),
        "public_benchmark_receptor_coordinate_validation_csv": _display_path(
            public_benchmark_receptor_coordinate_validation_csv,
            root=root_path,
        ),
        "public_benchmark_metric_evidence_csv": _display_path(
            public_benchmark_metric_evidence_csv,
            root=root_path,
        ),
        "receipt_csv_present": receipt_csv_present,
        "receipt_artifact_present": receipt_artifact_present,
        "priority_packet_artifact_present": priority_artifact_present,
        "public_benchmark_readiness_artifact_present": public_artifact_present,
        "public_benchmark_work_order_csv_present": work_order_csv_present,
        "public_benchmark_work_order_apply_artifact_present": work_order_apply_present,
        "public_benchmark_receptor_coordinate_intake_csv_present": receptor_intake_csv_present,
        "public_benchmark_receptor_coordinate_validation_csv_present": receptor_validation_csv_present,
        "public_benchmark_metric_evidence_csv_present": metric_evidence_csv_present,
        "receipt_row_count": len(receipt_rows),
        "receipt_field_row_count": len(receipt_field_rows),
        "required_receipt_field_count": len(
            [row for row in receipt_field_rows if row["required_for_operator_receipt"]]
        ),
        "receipt_operator_fill_pending_field_count": len(receipt_pending_rows),
        "public_benchmark_work_order_row_count": len(work_order_rows),
        "public_benchmark_work_order_field_count": len(work_order_field_rows),
        "public_benchmark_work_order_pending_field_count": len(work_order_pending_rows),
        "public_benchmark_receptor_coordinate_intake_row_count": len(receptor_intake_rows),
        "public_benchmark_receptor_coordinate_intake_artifact_present_row_count": len(
            [
                row
                for row in receptor_intake_rows
                if _bool_text(row.get("receptor_coordinate_artifact_present"))
            ]
        ),
        "public_benchmark_receptor_coordinate_intake_missing_work_order_row_count": (
            missing_receptor_intake_work_order_count
        ),
        "public_benchmark_receptor_coordinate_validation_row_count": len(receptor_validation_rows),
        "public_benchmark_receptor_coordinate_validation_pass_row_count": receptor_validation_pass_row_count,
        "public_benchmark_receptor_coordinate_validation_blocked_row_count": receptor_validation_blocked_row_count,
        "public_benchmark_receptor_coordinate_validation_missing_work_order_row_count": (
            missing_receptor_validation_work_order_count
        ),
        "public_benchmark_metric_evidence_row_count": len(metric_evidence_rows),
        "public_benchmark_metric_evidence_pass_row_count": metric_evidence_pass_row_count,
        "public_benchmark_metric_evidence_blocked_row_count": metric_evidence_blocked_row_count,
        "public_benchmark_metric_evidence_missing_work_order_row_count": (
            missing_metric_evidence_work_order_count
        ),
        "public_benchmark_metric_evidence_missing_required_input_artifact_row_count": (
            metric_evidence_missing_required_input_artifact_row_count
        ),
        "public_benchmark_metric_evidence_missing_required_input_artifact_sha256_row_count": (
            metric_evidence_missing_required_input_artifact_sha256_row_count
        ),
        "public_benchmark_metric_evidence_missing_dockq_source_row_count": _count_rows_without_true(
            metric_evidence_rows,
            "dockq_source_artifact_present",
        ),
        "public_benchmark_metric_evidence_missing_lddt_pli_source_row_count": _count_rows_without_true(
            metric_evidence_rows,
            "lddt_pli_source_artifact_present",
        ),
        "public_benchmark_metric_evidence_missing_internal_deltaG_source_row_count": _count_rows_without_true(
            metric_evidence_rows,
            "internal_deltaG_source_artifact_present",
        ),
        "public_benchmark_metric_evidence_invalid_dockq_source_payload_row_count": len(
            [
                row
                for row in metric_evidence_rows
                if _bool_text(row.get("dockq_source_artifact_present"))
                and not _bool_text(row.get("dockq_source_payload_valid"))
            ]
        ),
        "public_benchmark_metric_evidence_invalid_lddt_pli_source_payload_row_count": len(
            [
                row
                for row in metric_evidence_rows
                if _bool_text(row.get("lddt_pli_source_artifact_present"))
                and not _bool_text(row.get("lddt_pli_source_payload_valid"))
            ]
        ),
        "public_benchmark_metric_evidence_invalid_internal_deltaG_source_payload_row_count": len(
            [
                row
                for row in metric_evidence_rows
                if _bool_text(row.get("internal_deltaG_source_artifact_present"))
                and not _bool_text(row.get("internal_deltaG_source_payload_valid"))
            ]
        ),
        "public_benchmark_science_evidence_complete": science_evidence_complete,
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
            else (
                "Review the R4 coordinate-fetch preflight "
                f"(r4_ready_for_review_row_count="
                f"{_int(statistical_support_coordinate_fetch_r4_summary.get('ready_for_r4_review_row_count'))}, "
                f"r4_blocked_row_count="
                f"{_int(statistical_support_coordinate_fetch_r4_summary.get('blocked_r4_row_count'))}, "
                f"fetch_required_row_count="
                f"{_int(statistical_support_coordinate_fetch_r4_summary.get('fetch_required_row_count'))}, "
                f"approval_token_required="
                f"{_text(statistical_support_coordinate_fetch_r4_summary.get('approval_token_required'))}) "
                "and fill/approve the 17-row coordinate fetch operator receipt "
                f"(receipt_blocked_row_count="
                f"{_int(statistical_support_coordinate_fetch_operator_receipt_summary.get('blocked_row_count'))}, "
                f"fingerprint_verified_count="
                f"{_int(statistical_support_coordinate_fetch_operator_receipt_summary.get('r4_preflight_row_fingerprint_verified_count'))}); "
                "after explicit operator approval, stage and validate coordinates for "
                f"{_int(statistical_support_metric_materialization_summary.get('metric_materialization_row_count'))} "
                "statistical-support candidates "
                f"(coordinate_validation_pass_row_count="
                f"{_int(statistical_support_metric_materialization_summary.get('coordinate_validation_pass_row_count'))}, "
                "metric_materialization_candidate_ready_count="
                f"{_int(statistical_support_metric_materialization_summary.get('metric_materialization_candidate_ready_count'))}, "
                "required_input_artifacts="
                f"{_int(statistical_support_metric_materialization_summary.get('required_metric_input_artifact_count'))}/"
                f"{_int(statistical_support_metric_materialization_summary.get('present_required_metric_input_artifact_count'))}/"
                f"{_int(statistical_support_metric_materialization_summary.get('missing_required_metric_input_artifact_count'))}, "
                "local_coordinate_path_candidates="
                f"{_int(statistical_support_coordinate_intake_summary.get('coordinate_intake_suggested_local_path_candidate_count'))}, "
                "local_coordinate_present_targets="
                f"{_int(statistical_support_coordinate_intake_summary.get('coordinate_intake_suggested_local_path_present_target_count'))}, "
                "local_coordinate_missing_targets="
                f"{_int(statistical_support_coordinate_intake_summary.get('coordinate_intake_suggested_local_path_missing_target_count'))}, "
                "planned_metric_source_payload_count="
                f"{_int(statistical_support_metric_materialization_summary.get('planned_metric_source_payload_count'))}); "
                "then fill/approve the 51-row metric payload operator receipt "
                f"(receipt_blocked_row_count="
                f"{_int(statistical_support_metric_source_payload_operator_receipt_summary.get('blocked_row_count'))}, "
                f"approval_token_required="
                f"{_text(statistical_support_metric_source_payload_operator_receipt_summary.get('approval_token_required'))}) "
                "and materialize DockQ/lDDT-PLI/internal DeltaG source payloads before rerunning "
                "bootstrap Spearman p05 ahead of any R9 claim receipt or canonical intake promotion."
            )
            if (
                materialized_science_evidence_complete
                and not materialized_statistical_support_ready
                and statistical_support_work_order_ready
                and statistical_support_metric_materialization_readiness_ready
            )
            else (
                "Fill "
                f"{_int(statistical_support_work_order_summary.get('expansion_slot_count'))} additional reviewed "
                "public benchmark-pair expansion slots, including at least "
                f"{_int(statistical_support_work_order_summary.get('minimum_new_holdout_pair_count'))} holdout "
                "slots, then rebuild materialization and require bootstrap Spearman p05 >= 0.5 before any R9 "
                "claim receipt or canonical intake promotion."
            )
            if (
                materialized_science_evidence_complete
                and not materialized_statistical_support_ready
                and statistical_support_work_order_ready
            )
            else "Build the R9 public-benchmark statistical-support work-order before deciding on canonical intake."
            if materialized_science_evidence_complete and not materialized_statistical_support_ready
            else "Materialized R9 science evidence is complete; review the materialized work-order/apply candidate "
            "and decide whether to explicitly promote it to canonical intake before filling the R9 receipt."
            if materialized_science_evidence_complete
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
            str(public_benchmark_materialization_json),
            str(public_benchmark_materialized_work_order_csv),
            str(public_benchmark_materialized_apply_json),
            str(public_benchmark_statistical_support_work_order_json),
            str(public_benchmark_statistical_support_metric_materialization_readiness_json),
            str(public_benchmark_statistical_support_coordinate_intake_json),
            str(public_benchmark_statistical_support_metric_source_templates_json),
            str(public_benchmark_statistical_support_metric_source_payload_operator_receipt_json),
            str(public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json),
            str(public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json),
            str(public_benchmark_receptor_coordinate_intake_csv),
            str(public_benchmark_receptor_coordinate_validation_csv),
            str(public_benchmark_metric_evidence_csv),
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
        f"- public_benchmark_materialized_science_evidence_complete: `{summary['public_benchmark_materialized_science_evidence_complete']}`",
        f"- public_benchmark_materialized_work_order_row_count: `{summary['public_benchmark_materialized_work_order_row_count']}`",
        "- public_benchmark_materialized_free_energy_spearman: "
        f"`{summary['public_benchmark_materialized_free_energy_spearman']}`",
        "- public_benchmark_materialized_spearman_bootstrap_p05: "
        f"`{summary['public_benchmark_materialized_free_energy_spearman_bootstrap_p05']}`",
        "- public_benchmark_materialized_claim_grade_statistical_support_ready: "
        f"`{summary['public_benchmark_materialized_claim_grade_statistical_support_ready']}`",
        "- public_benchmark_statistical_support_work_order_ready: "
        f"`{summary['public_benchmark_statistical_support_work_order_ready']}`",
        "- public_benchmark_statistical_support_work_order_expansion_slot_count: "
        f"`{summary['public_benchmark_statistical_support_work_order_expansion_slot_count']}`",
        "- public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count: "
        f"`{summary['public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count']}`",
        "- public_benchmark_statistical_support_metric_materialization_candidate_ready_count: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_candidate_ready_count']}`",
        "- public_benchmark_statistical_support_metric_materialization_candidate_blocked_count: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_candidate_blocked_count']}`",
        "- public_benchmark_statistical_support_metric_materialization_required_input_present_missing: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_required_input_artifact_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count']}`",
        "- public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count']}`",
        "- public_benchmark_statistical_support_coordinate_intake_local_path_candidates/present_targets/missing_targets: "
        f"`{summary['public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count']}`",
        "- public_benchmark_statistical_support_metric_source_templates_ready: "
        f"`{summary['public_benchmark_statistical_support_metric_source_templates_ready']}`",
        "- public_benchmark_statistical_support_metric_source_templates_row/fill_ready/fill_blocked: "
        f"`{summary['public_benchmark_statistical_support_metric_source_templates_template_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count']}`",
        "- public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready: "
        f"`{summary['public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready']}`",
        "- public_benchmark_statistical_support_metric_source_payload_operator_receipt_row/pass/blocked: "
        f"`{summary['public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count']}`",
        "- public_benchmark_statistical_support_metric_source_payload_operator_receipt_fingerprint_verified/mismatch: "
        f"`{summary['public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row/pass/blocked: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_operator_receipt_fingerprint_verified/mismatch: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count']}`",
        "- public_benchmark_receptor_coordinate_intake_artifact_present_row_count: "
        f"`{summary['public_benchmark_receptor_coordinate_intake_artifact_present_row_count']}`",
        "- public_benchmark_receptor_coordinate_validation_blocked_row_count: "
        f"`{summary['public_benchmark_receptor_coordinate_validation_blocked_row_count']}`",
        f"- public_benchmark_metric_evidence_blocked_row_count: `{summary['public_benchmark_metric_evidence_blocked_row_count']}`",
        "- public_benchmark_metric_evidence_missing_source_row_counts: "
        f"`dockq={summary['public_benchmark_metric_evidence_missing_dockq_source_row_count']};"
        f"lddt_pli={summary['public_benchmark_metric_evidence_missing_lddt_pli_source_row_count']};"
        f"internal_deltaG={summary['public_benchmark_metric_evidence_missing_internal_deltaG_source_row_count']}`",
        "- public_benchmark_metric_evidence_missing_required_input_artifact_row_count: "
        f"`{summary['public_benchmark_metric_evidence_missing_required_input_artifact_row_count']}`",
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
    parser.add_argument(
        "--public-benchmark-materialization-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    )
    parser.add_argument(
        "--public-benchmark-materialized-work-order-csv",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    )
    parser.add_argument(
        "--public-benchmark-materialized-apply-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-work-order-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-metric-materialization-readiness-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-coordinate-intake-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-metric-source-templates-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-metric-source-payload-operator-receipt-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-coordinate-fetch-r4-preflight-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-coordinate-fetch-operator-receipt-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_JSON,
    )
    parser.add_argument(
        "--public-benchmark-receptor-coordinate-intake-csv",
        default=DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_INTAKE_CSV,
    )
    parser.add_argument(
        "--public-benchmark-receptor-coordinate-validation-csv",
        default=DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_VALIDATION_CSV,
    )
    parser.add_argument("--public-benchmark-metric-evidence-csv", default=DEFAULT_PUBLIC_BENCHMARK_METRIC_EVIDENCE_CSV)
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
        public_benchmark_materialization_json=args.public_benchmark_materialization_json,
        public_benchmark_materialized_work_order_csv=args.public_benchmark_materialized_work_order_csv,
        public_benchmark_materialized_apply_json=args.public_benchmark_materialized_apply_json,
        public_benchmark_statistical_support_work_order_json=(
            args.public_benchmark_statistical_support_work_order_json
        ),
        public_benchmark_statistical_support_metric_materialization_readiness_json=(
            args.public_benchmark_statistical_support_metric_materialization_readiness_json
        ),
        public_benchmark_statistical_support_coordinate_intake_json=(
            args.public_benchmark_statistical_support_coordinate_intake_json
        ),
        public_benchmark_statistical_support_metric_source_templates_json=(
            args.public_benchmark_statistical_support_metric_source_templates_json
        ),
        public_benchmark_statistical_support_metric_source_payload_operator_receipt_json=(
            args.public_benchmark_statistical_support_metric_source_payload_operator_receipt_json
        ),
        public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json=(
            args.public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json
        ),
        public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json=(
            args.public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json
        ),
        public_benchmark_receptor_coordinate_intake_csv=args.public_benchmark_receptor_coordinate_intake_csv,
        public_benchmark_receptor_coordinate_validation_csv=args.public_benchmark_receptor_coordinate_validation_csv,
        public_benchmark_metric_evidence_csv=args.public_benchmark_metric_evidence_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
