#!/usr/bin/env python3
"""Preview and optionally apply operator-filled R9 claim-evidence receipts."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.apply_refine_tier_public_benchmark_work_order import (
    apply_refine_tier_public_benchmark_work_order,
)
from tools.product.build_engine_refinement_claim_evidence_operator_field_worksheet import (
    DEFAULT_OUT_JSON as DEFAULT_FIELD_WORKSHEET_JSON,
)
from tools.product.build_engine_refinement_claim_evidence_priority_packet import (
    DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
    DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV,
)
from tools.product.build_engine_refinement_claim_evidence_receipt import (
    APPROVAL_TOKEN,
    DEFAULT_ACTION_BOARD_CSV,
    DEFAULT_RECEIPT_CSV,
    REQUIRED_COLUMNS,
    build_engine_refinement_claim_evidence_receipt,
)
from tools.product.build_refine_tier_public_benchmark_readiness import (
    DEFAULT_INPUT_CSV as DEFAULT_PUBLIC_BENCHMARK_INTAKE_CSV,
    DEFAULT_OUT_METRIC_EVIDENCE_CSV,
    DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV,
    REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN,
    WORK_ORDER_COLUMNS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGING_RECEIPT_CSV = DEFAULT_RECEIPT_CSV
DEFAULT_LIVE_RECEIPT_CSV = DEFAULT_RECEIPT_CSV
DEFAULT_STAGING_PUBLIC_BENCHMARK_WORK_ORDER_CSV = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV
DEFAULT_TARGET_PUBLIC_BENCHMARK_INTAKE_CSV = DEFAULT_PUBLIC_BENCHMARK_INTAKE_CSV
DEFAULT_OUT_JSON = "runs/engine_refinement_claim_evidence_operator_staging_apply_current.json"
DEFAULT_OUT_CSV = "runs/engine_refinement_claim_evidence_operator_staging_apply_current.csv"
DEFAULT_OUT_MD = "runs/engine_refinement_claim_evidence_operator_staging_apply_current.md"
DEFAULT_CANDIDATE_RECEIPT_CSV = "runs/engine_refinement_claim_evidence_receipt_candidate_current.csv"
DEFAULT_CANDIDATE_PUBLIC_BENCHMARK_INTAKE_CSV = (
    "runs/engine_refinement_claim_evidence_public_benchmark_intake_candidate_current.csv"
)

CLAIM_BOUNDARY = (
    "Engine refinement claim evidence operator staging apply only; it validates operator-filled R9 "
    "claim-evidence receipt rows and public-benchmark work-order rows before canonical receipt or "
    "tracked intake writes. Preview mode does not download data, run docking or MD, call external "
    "engines, promote claims, upload, email, delete, commit, push, or mutate external state."
)


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


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


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


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(_text(value).startswith(("OPERATOR_FILL", "OPERATOR_CONFIRM")) for value in row.values())


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


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


def _candidate_receipt_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{column: row.get(column, "") for column in REQUIRED_COLUMNS} for row in rows]


def _row_reports(
    *,
    receipt_rows: list[dict[str, Any]],
    work_order_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for idx, row in enumerate(receipt_rows, start=1):
        reports.append(
            {
                "staging_section": "claim_evidence_receipt",
                "staging_row_index": idx,
                "source_row_id": _text(row.get("blocker_id")),
                "candidate_row_status": _text(row.get("row_status")),
                "candidate_blockers": _text(row.get("blockers")),
                "candidate_observed_status": _text(row.get("observed_evidence_status")),
                "candidate_expected_status": _text(row.get("expected_evidence_status")),
                "candidate_missing_true_fields": _text(row.get("missing_true_fields")),
                "candidate_copy_allowed": _text(row.get("row_status")) == "pass",
                "claim_promoted": False,
                "external_engine_calls_executed": False,
                "external_state_mutated": False,
            }
        )
    for idx, row in enumerate(work_order_rows, start=1):
        reports.append(
            {
                "staging_section": "public_benchmark_work_order",
                "staging_row_index": idx,
                "source_row_id": _text(row.get("work_order_id")),
                "candidate_row_status": _text(row.get("row_status")),
                "candidate_blockers": _text(row.get("blockers")),
                "candidate_observed_status": _text(row.get("benchmark_id")),
                "candidate_expected_status": "valid_public_benchmark_intake_row",
                "candidate_missing_true_fields": "",
                "candidate_copy_allowed": _text(row.get("row_status")) == "pass",
                "claim_promoted": False,
                "external_engine_calls_executed": False,
                "external_state_mutated": False,
            }
        )
    return reports


def build_engine_refinement_claim_evidence_operator_staging_apply(
    *,
    staging_receipt_csv: str | Path = DEFAULT_STAGING_RECEIPT_CSV,
    live_receipt_csv: str | Path = DEFAULT_LIVE_RECEIPT_CSV,
    action_board_csv: str | Path = DEFAULT_ACTION_BOARD_CSV,
    field_worksheet_json: str | Path = DEFAULT_FIELD_WORKSHEET_JSON,
    staging_public_benchmark_work_order_csv: str | Path = DEFAULT_STAGING_PUBLIC_BENCHMARK_WORK_ORDER_CSV,
    materialized_public_benchmark_work_order_csv: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    materialized_public_benchmark_materialization_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    materialized_public_benchmark_apply_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    receptor_coordinate_validation_csv: str | Path = DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV,
    metric_evidence_csv: str | Path = DEFAULT_OUT_METRIC_EVIDENCE_CSV,
    target_public_benchmark_intake_csv: str | Path = DEFAULT_TARGET_PUBLIC_BENCHMARK_INTAKE_CSV,
    candidate_receipt_csv: str | Path = DEFAULT_CANDIDATE_RECEIPT_CSV,
    candidate_public_benchmark_intake_csv: str | Path = DEFAULT_CANDIDATE_PUBLIC_BENCHMARK_INTAKE_CSV,
    mode: str = "preview",
    write_canonical_receipt: bool = False,
    write_public_benchmark_intake: bool = False,
    approval_token: str = "",
    public_benchmark_approval_token: str = "",
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    staging_rows, staging_columns, staging_present = _read_csv(staging_receipt_csv, root=root_path)
    live_rows, _, live_present = _read_csv(live_receipt_csv, root=root_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in staging_columns] if staging_present else list(REQUIRED_COLUMNS)
    work_order_rows, work_order_columns, work_order_present = _read_csv(
        staging_public_benchmark_work_order_csv,
        root=root_path,
    )
    missing_work_order_columns = (
        [column for column in WORK_ORDER_COLUMNS if column not in work_order_columns]
        if work_order_present
        else list(WORK_ORDER_COLUMNS)
    )
    field_worksheet_packet, field_worksheet_present = _read_json(field_worksheet_json, root=root_path)
    field_worksheet = _summary(field_worksheet_packet)
    existing_work_order_apply_packet, existing_work_order_apply_present = _read_json(
        DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON,
        root=root_path,
    )
    existing_work_order_apply = _summary(existing_work_order_apply_packet)
    materialized_work_order_rows, _, materialized_work_order_present = _read_csv(
        materialized_public_benchmark_work_order_csv,
        root=root_path,
    )
    materialization_packet, materialization_present = _read_json(
        materialized_public_benchmark_materialization_json,
        root=root_path,
    )
    materialization_summary = _summary(materialization_packet)
    materialized_apply_packet, materialized_apply_present = _read_json(
        materialized_public_benchmark_apply_json,
        root=root_path,
    )
    materialized_apply_summary = _summary(materialized_apply_packet)
    materialized_metric_ready = _materialized_metric_ready(materialization_summary)
    materialized_apply_ready = bool(materialized_apply_summary.get("apply_ready") is True)
    materialized_candidate_ready = bool(materialized_metric_ready and materialized_apply_ready)

    candidate_receipt_payload = build_engine_refinement_claim_evidence_receipt(
        receipt_csv=staging_receipt_csv,
        action_board_csv=action_board_csv,
        root=root_path,
    )
    candidate_receipt_summary = candidate_receipt_payload["summary"]
    candidate_receipt_ready = bool(
        candidate_receipt_summary.get("claim_promotion_evidence_receipt_ready") is True
    )
    candidate_work_order_payload = apply_refine_tier_public_benchmark_work_order(
        work_order_csv=_resolve(staging_public_benchmark_work_order_csv, root=root_path),
        out_csv=_resolve(candidate_public_benchmark_intake_csv, root=root_path),
        target_intake_csv=_resolve(target_public_benchmark_intake_csv, root=root_path),
        receptor_coordinate_validation_csv=_resolve(receptor_coordinate_validation_csv, root=root_path),
        metric_evidence_csv=_resolve(metric_evidence_csv, root=root_path),
        write_intake=False,
        approval_token="",
    )
    candidate_work_order_summary = candidate_work_order_payload["summary"]
    candidate_work_order_ready = bool(candidate_work_order_summary.get("apply_ready") is True)

    receipt_placeholder_row_count = sum(1 for row in staging_rows if _has_placeholder(row))
    work_order_placeholder_row_count = sum(1 for row in work_order_rows if _has_placeholder(row))
    approval_token_present = bool(_text(approval_token))
    approval_token_accepted = _text(approval_token) == APPROVAL_TOKEN
    public_benchmark_approval_token_present = bool(_text(public_benchmark_approval_token))
    public_benchmark_approval_token_accepted = (
        _text(public_benchmark_approval_token)
        == REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN
    )
    live_copy_allowed = (
        mode == "live_apply"
        and candidate_receipt_ready
        and not missing_columns
        and staging_present
        and approval_token_accepted
    )
    public_benchmark_intake_write_allowed = (
        mode == "live_apply"
        and candidate_work_order_ready
        and not missing_work_order_columns
        and work_order_present
        and public_benchmark_approval_token_accepted
    )
    field_metric_source_templates_artifact = _text(
        field_worksheet.get("public_benchmark_statistical_support_metric_source_templates_artifact")
    )
    field_metric_source_templates_template_row_count = _int(
        field_worksheet.get("public_benchmark_statistical_support_metric_source_templates_template_row_count")
    )
    field_metric_source_templates_fill_ready_row_count = _int(
        field_worksheet.get(
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count"
        )
    )
    field_metric_source_templates_fill_blocked_row_count = _int(
        field_worksheet.get(
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
        )
    )
    field_coordinate_intake_artifact = _text(
        field_worksheet.get("public_benchmark_statistical_support_coordinate_intake_artifact")
    )
    field_metric_source_payload_receipt_artifact = _text(
        field_worksheet.get(
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact"
        )
    )
    field_metric_source_payload_receipt_blocked_row_count = _int(
        field_worksheet.get(
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count"
        )
    )
    field_metric_source_payload_receipt_approval_token_required = _text(
        field_worksheet.get(
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required"
        )
    )
    field_coordinate_fetch_operator_receipt_artifact = _text(
        field_worksheet.get(
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact"
        )
    )
    field_coordinate_fetch_operator_receipt_blocked_row_count = _int(
        field_worksheet.get(
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count"
        )
    )
    field_coordinate_fetch_operator_receipt_review_surface_ready_count = _int(
        field_worksheet.get(
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count"
        )
    )
    field_coordinate_fetch_operator_receipt_review_surface_blocked_count = _int(
        field_worksheet.get(
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count"
        )
    )
    field_coordinate_fetch_operator_receipt_manual_field_pending_count = _int(
        field_worksheet.get(
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count"
        )
    )
    field_coordinate_fetch_operator_receipt_approval_token_required = _text(
        field_worksheet.get(
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required"
        )
    )

    blockers: list[str] = []
    if not staging_present:
        blockers.append("staging_receipt_csv_missing")
    if missing_columns:
        blockers.append("staging_receipt_columns_missing:" + ",".join(missing_columns))
    if not staging_rows:
        blockers.append("staging_receipt_rows_missing")
    if not work_order_present:
        blockers.append("staging_public_benchmark_work_order_csv_missing")
    if missing_work_order_columns:
        blockers.append("staging_public_benchmark_work_order_columns_missing:" + ",".join(missing_work_order_columns))
    if not work_order_rows:
        blockers.append("staging_public_benchmark_work_order_rows_missing")
    if not field_worksheet_present:
        blockers.append("operator_field_worksheet_missing")
    if not candidate_receipt_ready:
        blockers.append("candidate_receipt_not_ready")
    if not candidate_work_order_ready:
        blockers.append("candidate_public_benchmark_work_order_not_ready")
    if write_canonical_receipt and not approval_token_accepted:
        blockers.append("write_canonical_receipt_approval_token_missing_or_invalid")
    if write_canonical_receipt and not live_copy_allowed:
        blockers.append("write_canonical_receipt_blocked_until_candidate_ready")
    if write_public_benchmark_intake and not public_benchmark_approval_token_accepted:
        blockers.append("write_public_benchmark_intake_approval_token_missing_or_invalid")
    if write_public_benchmark_intake and not public_benchmark_intake_write_allowed:
        blockers.append("write_public_benchmark_intake_blocked_until_candidate_ready")

    candidate_receipt_written = False
    canonical_receipt_written = False
    public_benchmark_intake_written = False
    if candidate_receipt_ready:
        write_csv_rows(_resolve(candidate_receipt_csv, root=root_path), _candidate_receipt_rows(staging_rows))
        candidate_receipt_written = True
    if write_canonical_receipt and live_copy_allowed:
        write_csv_rows(_resolve(live_receipt_csv, root=root_path), _candidate_receipt_rows(staging_rows))
        canonical_receipt_written = True
        live_rows = _candidate_receipt_rows(staging_rows)
    if write_public_benchmark_intake and public_benchmark_intake_write_allowed:
        public_apply_payload = apply_refine_tier_public_benchmark_work_order(
            work_order_csv=_resolve(staging_public_benchmark_work_order_csv, root=root_path),
            out_csv=_resolve(candidate_public_benchmark_intake_csv, root=root_path),
            target_intake_csv=_resolve(target_public_benchmark_intake_csv, root=root_path),
            receptor_coordinate_validation_csv=_resolve(receptor_coordinate_validation_csv, root=root_path),
            metric_evidence_csv=_resolve(metric_evidence_csv, root=root_path),
            write_intake=True,
            approval_token=public_benchmark_approval_token,
        )
        public_benchmark_intake_written = bool(public_apply_payload["summary"].get("intake_written") is True)

    if canonical_receipt_written or public_benchmark_intake_written:
        status = "engine_refinement_claim_evidence_operator_staging_live_written"
        next_required_step = "Canonical R9 receipt or benchmark intake was written; rerun public benchmark readiness, receipt, priority packet, goal audit, and source-of-truth gates."
    elif live_copy_allowed or public_benchmark_intake_write_allowed:
        status = "engine_refinement_claim_evidence_operator_staging_apply_ready_for_live_copy"
        next_required_step = "Candidate receipt or public benchmark intake is ready. Rerun live_apply with explicit write flags only after operator review."
    elif candidate_receipt_ready or candidate_work_order_ready:
        status = "engine_refinement_claim_evidence_operator_staging_preview_ready"
        next_required_step = "Review the candidate artifacts, then use live_apply mode with the matching approval token before canonical writes."
    elif materialized_candidate_ready:
        status = "blocked_engine_refinement_claim_evidence_operator_staging_apply"
        if field_metric_source_templates_template_row_count:
            next_required_step = (
                "Materialized public benchmark science candidate is ready but not claim-grade: "
                "review the R4 coordinate-fetch preflight, fill/approve "
                f"{field_coordinate_fetch_operator_receipt_blocked_row_count} coordinate fetch receipt rows "
                f"(operator_review_surface_ready_count="
                f"{field_coordinate_fetch_operator_receipt_review_surface_ready_count}, "
                f"receipt_manual_field_pending_count="
                f"{field_coordinate_fetch_operator_receipt_manual_field_pending_count}, "
                f"{field_coordinate_fetch_operator_receipt_approval_token_required}), "
                "then validate the 17 statistical-support coordinates, "
                f"then replace {field_metric_source_templates_fill_blocked_row_count} blocked metric source "
                "template placeholders and fill/approve "
                f"{field_metric_source_payload_receipt_blocked_row_count} metric payload receipt rows "
                f"({field_metric_source_payload_receipt_approval_token_required}) before any canonical "
                "R9 receipt or public benchmark intake promotion."
            )
        else:
            next_required_step = (
                "Materialized public benchmark science candidate is ready, but the canonical staging receipt/work-order "
                "still blocks. Review the materialized candidate, then use the explicit intake/receipt promotion path."
            )
    else:
        status = "blocked_engine_refinement_claim_evidence_operator_staging_apply"
        next_required_step = "Fill or repair R9 claim-evidence receipt rows and public benchmark work-order rows before touching canonical receipt or intake CSVs."

    summary = {
        "packet_type": "engine_refinement_claim_evidence_operator_staging_apply",
        "status": status,
        "mode": mode,
        "staging_receipt_csv": _display_path(staging_receipt_csv, root=root_path),
        "staging_receipt_csv_present": staging_present,
        "staging_receipt_row_count": len(staging_rows),
        "staging_receipt_missing_required_column_count": len(missing_columns),
        "staging_receipt_placeholder_row_count": receipt_placeholder_row_count,
        "live_receipt_csv": _display_path(live_receipt_csv, root=root_path),
        "live_receipt_csv_present": live_present,
        "live_receipt_row_count": len(live_rows),
        "candidate_receipt_csv": _display_path(candidate_receipt_csv, root=root_path),
        "candidate_receipt_written": candidate_receipt_written,
        "candidate_receipt_ready": candidate_receipt_ready,
        "candidate_receipt_status": _text(candidate_receipt_summary.get("status")),
        "candidate_receipt_pass_row_count": int(candidate_receipt_summary.get("pass_row_count") or 0),
        "candidate_receipt_blocked_row_count": int(candidate_receipt_summary.get("blocked_row_count") or 0),
        "candidate_receipt_blocker_count": int(candidate_receipt_summary.get("blocker_count") or 0),
        "candidate_first_blocked_blocker_id": _text(candidate_receipt_summary.get("first_blocked_blocker_id")),
        "candidate_first_blocked_evidence_artifact": _text(candidate_receipt_summary.get("first_blocked_evidence_artifact")),
        "candidate_first_blocked_expected_evidence_status": _text(
            candidate_receipt_summary.get("first_blocked_expected_evidence_status")
        ),
        "candidate_first_blocked_observed_evidence_status": _text(
            candidate_receipt_summary.get("first_blocked_observed_evidence_status")
        ),
        "candidate_most_common_row_blocker": _text(candidate_receipt_summary.get("most_common_row_blocker")),
        "staging_public_benchmark_work_order_csv": _display_path(
            staging_public_benchmark_work_order_csv,
            root=root_path,
        ),
        "staging_public_benchmark_work_order_csv_present": work_order_present,
        "staging_public_benchmark_work_order_row_count": len(work_order_rows),
        "staging_public_benchmark_work_order_missing_required_column_count": len(missing_work_order_columns),
        "staging_public_benchmark_work_order_placeholder_row_count": work_order_placeholder_row_count,
        "candidate_public_benchmark_intake_csv": _display_path(
            candidate_public_benchmark_intake_csv,
            root=root_path,
        ),
        "candidate_public_benchmark_work_order_ready": candidate_work_order_ready,
        "candidate_public_benchmark_work_order_status": _text(candidate_work_order_summary.get("status")),
        "candidate_public_benchmark_valid_intake_row_count": int(
            candidate_work_order_summary.get("valid_intake_row_count") or 0
        ),
        "candidate_public_benchmark_blocked_row_count": int(
            candidate_work_order_summary.get("blocked_row_count") or 0
        ),
        "candidate_public_benchmark_receptor_coordinate_validation_contract_blocked_row_count": int(
            candidate_work_order_summary.get("receptor_coordinate_validation_contract_blocked_row_count") or 0
        ),
        "candidate_public_benchmark_metric_evidence_contract_blocked_row_count": int(
            candidate_work_order_summary.get("metric_evidence_contract_blocked_row_count") or 0
        ),
        "candidate_public_benchmark_metric_evidence_missing_required_input_artifact_row_count": int(
            candidate_work_order_summary.get("metric_evidence_missing_required_input_artifact_row_count") or 0
        ),
        "candidate_public_benchmark_metric_evidence_missing_required_receptor_input_row_count": int(
            candidate_work_order_summary.get("metric_evidence_missing_required_receptor_input_row_count") or 0
        ),
        "candidate_public_benchmark_metric_evidence_required_input_sha256_blocked_row_count": int(
            candidate_work_order_summary.get("metric_evidence_required_input_sha256_blocked_row_count") or 0
        ),
        "candidate_public_benchmark_candidate_intake_written": bool(
            candidate_work_order_summary.get("candidate_intake_written") is True
        ),
        "materialized_public_benchmark_work_order_csv": _display_path(
            materialized_public_benchmark_work_order_csv,
            root=root_path,
        ),
        "materialized_public_benchmark_materialization_artifact": _display_path(
            materialized_public_benchmark_materialization_json,
            root=root_path,
        ),
        "materialized_public_benchmark_apply_artifact": _display_path(
            materialized_public_benchmark_apply_json,
            root=root_path,
        ),
        "materialized_public_benchmark_work_order_csv_present": materialized_work_order_present,
        "materialized_public_benchmark_materialization_artifact_present": materialization_present,
        "materialized_public_benchmark_apply_artifact_present": materialized_apply_present,
        "materialized_public_benchmark_metric_ready": materialized_metric_ready,
        "materialized_public_benchmark_apply_ready": materialized_apply_ready,
        "materialized_public_benchmark_candidate_ready": materialized_candidate_ready,
        "materialized_public_benchmark_work_order_row_count": len(materialized_work_order_rows),
        "materialized_public_benchmark_metric_evidence_pass_row_count": _int(
            materialization_summary.get("metric_evidence_pass_row_count")
        ),
        "materialized_public_benchmark_metric_evidence_blocked_row_count": _int(
            materialization_summary.get("metric_evidence_blocked_row_count")
        ),
        "materialized_public_benchmark_free_energy_pair_count": _int(
            materialization_summary.get("free_energy_pair_count")
        ),
        "materialized_public_benchmark_free_energy_spearman": materialization_summary.get(
            "free_energy_spearman"
        ),
        "materialized_public_benchmark_free_energy_spearman_gate_ready": bool(
            materialization_summary.get("free_energy_spearman_gate_ready") is True
        ),
        "materialized_public_benchmark_free_energy_spearman_bootstrap_p05": materialization_summary.get(
            "free_energy_spearman_bootstrap_p05"
        ),
        "materialized_public_benchmark_free_energy_spearman_bootstrap_p50": materialization_summary.get(
            "free_energy_spearman_bootstrap_p50"
        ),
        "materialized_public_benchmark_free_energy_spearman_bootstrap_p95": materialization_summary.get(
            "free_energy_spearman_bootstrap_p95"
        ),
        "materialized_public_benchmark_claim_grade_statistical_support_ready": bool(
            materialization_summary.get("claim_grade_public_benchmark_statistical_support_ready") is True
        ),
        "materialized_public_benchmark_claim_grade_statistical_support_blocker_count": _int(
            materialization_summary.get("claim_grade_public_benchmark_statistical_support_blocker_count")
        ),
        "materialized_public_benchmark_claim_grade_statistical_support_blockers": (
            materialization_summary.get("claim_grade_public_benchmark_statistical_support_blockers") or []
        ),
        "materialized_public_benchmark_apply_status": _text(materialized_apply_summary.get("status")),
        "materialized_public_benchmark_apply_blocked_row_count": _int(
            materialized_apply_summary.get("blocked_row_count")
        ),
        "materialized_public_benchmark_candidate_intake_written": bool(
            materialized_apply_summary.get("candidate_intake_written") is True
        ),
        "existing_public_benchmark_work_order_apply_artifact_present": existing_work_order_apply_present,
        "existing_public_benchmark_work_order_apply_status": _text(existing_work_order_apply.get("status")),
        "field_worksheet_artifact": _display_path(field_worksheet_json, root=root_path),
        "field_worksheet_present": field_worksheet_present,
        "field_worksheet_status": _text(field_worksheet.get("status")),
        "field_worksheet_pending_field_count": int(field_worksheet.get("operator_fill_pending_field_count") or 0),
        "field_worksheet_receipt_pending_field_count": int(
            field_worksheet.get("receipt_operator_fill_pending_field_count") or 0
        ),
        "field_worksheet_work_order_pending_field_count": int(
            field_worksheet.get("public_benchmark_work_order_pending_field_count") or 0
        ),
        "field_worksheet_top_blocker_id": _text(field_worksheet.get("top_blocker_id")),
        "field_worksheet_top_priority_bucket": _text(field_worksheet.get("top_priority_bucket")),
        "field_worksheet_top_blocker_pending_field_count": int(
            field_worksheet.get("top_blocker_pending_field_count") or 0
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_artifact": (
            field_metric_source_templates_artifact
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_artifact_present": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_templates_artifact_present"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready": bool(
            field_worksheet.get("public_benchmark_statistical_support_metric_source_templates_ready")
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": _text(
            field_worksheet.get("public_benchmark_statistical_support_metric_source_templates_status")
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": (
            field_metric_source_templates_template_row_count
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_metric_name_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_templates_template_metric_name_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": (
            field_metric_source_templates_fill_ready_row_count
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": (
            field_metric_source_templates_fill_blocked_row_count
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_artifact": (
            field_coordinate_intake_artifact
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_artifact_present": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_artifact_present"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_ready": bool(
            field_worksheet.get("public_benchmark_statistical_support_coordinate_intake_ready")
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_status": _text(
            field_worksheet.get("public_benchmark_statistical_support_coordinate_intake_status")
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_row_count": _int(
            field_worksheet.get("public_benchmark_statistical_support_coordinate_intake_row_count")
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_missing_row_count": _int(
            field_worksheet.get("public_benchmark_statistical_support_coordinate_intake_missing_row_count")
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact": (
            field_coordinate_fetch_operator_receipt_artifact
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact_present": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact_present"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count": (
            field_coordinate_fetch_operator_receipt_blocked_row_count
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count": (
            field_coordinate_fetch_operator_receipt_review_surface_ready_count
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count": (
            field_coordinate_fetch_operator_receipt_review_surface_blocked_count
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count": (
            field_coordinate_fetch_operator_receipt_manual_field_pending_count
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required": (
            field_coordinate_fetch_operator_receipt_approval_token_required
        ),
        "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact": (
            field_metric_source_payload_receipt_artifact
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact_present": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact_present"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": (
            field_metric_source_payload_receipt_blocked_row_count
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_ready_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_ready_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_blocked_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_blocked_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_metric_source_artifact_path_present_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_metric_source_artifact_path_present_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_list_present_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_list_present_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_present_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_present_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_complete_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_complete_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_source_payload_fields_present_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_source_payload_fields_present_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_engine_calls_zero_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_engine_calls_zero_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_manual_field_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_manual_field_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_metric_value_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_metric_value_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_method_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_method_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_input_artifacts_reviewed_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_input_artifacts_reviewed_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_input_artifact_sha256s_reviewed_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_input_artifact_sha256s_reviewed_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_metric_source_artifact_reviewed_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_metric_source_artifact_reviewed_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_payload_schema_reviewed_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_payload_schema_reviewed_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_license_ok_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_license_ok_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_operator_id_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_operator_id_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_reviewed_at_utc_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_reviewed_at_utc_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_approval_token_pending_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_approval_token_pending_count"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed": bool(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed"
            )
            is True
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": _text(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker"
            )
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
            field_metric_source_payload_receipt_approval_token_required
        ),
        "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count": _int(
            field_worksheet.get(
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count"
            )
        ),
        "approval_token_required": APPROVAL_TOKEN if mode == "live_apply" or write_canonical_receipt else "",
        "approval_token_present": approval_token_present,
        "approval_token_accepted": approval_token_accepted if mode == "live_apply" or write_canonical_receipt else False,
        "public_benchmark_approval_token_required": (
            REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN
            if mode == "live_apply" or write_public_benchmark_intake
            else ""
        ),
        "public_benchmark_approval_token_present": public_benchmark_approval_token_present,
        "public_benchmark_approval_token_accepted": (
            public_benchmark_approval_token_accepted
            if mode == "live_apply" or write_public_benchmark_intake
            else False
        ),
        "live_copy_allowed": live_copy_allowed,
        "public_benchmark_intake_write_allowed": public_benchmark_intake_write_allowed,
        "write_canonical_receipt_requested": bool(write_canonical_receipt),
        "write_public_benchmark_intake_requested": bool(write_public_benchmark_intake),
        "canonical_receipt_written": canonical_receipt_written,
        "public_benchmark_intake_written": public_benchmark_intake_written,
        "claim_promotion_allowed": False,
        "claim_promoted": False,
        "external_engine_calls_executed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
        "source_artifacts": [
            str(staging_receipt_csv),
            str(live_receipt_csv),
            str(action_board_csv),
            str(field_worksheet_json),
            str(staging_public_benchmark_work_order_csv),
            str(materialized_public_benchmark_work_order_csv),
            str(materialized_public_benchmark_materialization_json),
            str(materialized_public_benchmark_apply_json),
            str(receptor_coordinate_validation_csv),
            str(metric_evidence_csv),
            str(target_public_benchmark_intake_csv),
            *([field_metric_source_templates_artifact] if field_metric_source_templates_artifact else []),
            *([field_coordinate_intake_artifact] if field_coordinate_intake_artifact else []),
            *(
                [field_coordinate_fetch_operator_receipt_artifact]
                if field_coordinate_fetch_operator_receipt_artifact
                else []
            ),
            *(
                [field_metric_source_payload_receipt_artifact]
                if field_metric_source_payload_receipt_artifact
                else []
            ),
        ],
    }
    return {
        "summary": summary,
        "rows": _row_reports(
            receipt_rows=candidate_receipt_payload["rows"],
            work_order_rows=candidate_work_order_payload["rows"],
        ),
        "candidate_receipt_rows": _candidate_receipt_rows(staging_rows),
        "candidate_receipt_summary": candidate_receipt_summary,
        "candidate_public_benchmark_summary": candidate_work_order_summary,
        "required_receipt_columns": list(REQUIRED_COLUMNS),
        "required_work_order_columns": list(WORK_ORDER_COLUMNS),
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Engine Refinement Claim Evidence Operator Staging Apply",
        "",
        f"- status: `{summary['status']}`",
        f"- mode: `{summary['mode']}`",
        f"- candidate_receipt_ready: `{summary['candidate_receipt_ready']}`",
        f"- candidate receipt pass/blocked: `{summary['candidate_receipt_pass_row_count']}/{summary['candidate_receipt_blocked_row_count']}`",
        f"- candidate_public_benchmark_work_order_ready: `{summary['candidate_public_benchmark_work_order_ready']}`",
        f"- candidate_public_benchmark_blocked_row_count: `{summary['candidate_public_benchmark_blocked_row_count']}`",
        "- candidate_public_benchmark_metric_evidence_missing_required_input_artifact_row_count: "
        f"`{summary['candidate_public_benchmark_metric_evidence_missing_required_input_artifact_row_count']}`",
        f"- materialized_public_benchmark_candidate_ready: `{summary['materialized_public_benchmark_candidate_ready']}`",
        f"- materialized_public_benchmark_work_order_row_count: `{summary['materialized_public_benchmark_work_order_row_count']}`",
        "- materialized_public_benchmark_free_energy_spearman: "
        f"`{summary['materialized_public_benchmark_free_energy_spearman']}`",
        "- materialized_public_benchmark_spearman_bootstrap_p05: "
        f"`{summary['materialized_public_benchmark_free_energy_spearman_bootstrap_p05']}`",
        "- materialized_public_benchmark_claim_grade_statistical_support_ready: "
        f"`{summary['materialized_public_benchmark_claim_grade_statistical_support_ready']}`",
        f"- staging_receipt_placeholder_row_count: `{summary['staging_receipt_placeholder_row_count']}`",
        f"- staging_public_benchmark_work_order_placeholder_row_count: `{summary['staging_public_benchmark_work_order_placeholder_row_count']}`",
        f"- field_worksheet_pending_field_count: `{summary['field_worksheet_pending_field_count']}`",
        "- field_worksheet_metric_source_templates_ready: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready']}`",
        "- field_worksheet_metric_source_templates_row/fill_ready/fill_blocked: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count']}`",
        "- field_worksheet_coordinate_intake_ready: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_intake_ready']}`",
        "- field_worksheet_coordinate_intake_row/present/missing: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_intake_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_intake_missing_row_count']}`",
        "- field_worksheet_coordinate_intake_local_path_candidate/present_target/missing_target: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count']}`",
        "- field_worksheet_coordinate_fetch_operator_receipt_ready: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready']}`",
        "- field_worksheet_coordinate_fetch_operator_receipt_row/pass/blocked: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count']}`",
        "- field_worksheet_coordinate_fetch_operator_receipt_fingerprint_verified/mismatch: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count']}`",
        "- field_worksheet_coordinate_fetch_operator_receipt_review_surface_ready/blocked: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count']}`",
        "- field_worksheet_coordinate_fetch_operator_receipt_manual_field_pending_count: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count']}`",
        "- field_worksheet_metric_source_payload_operator_receipt_ready: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready']}`",
        "- field_worksheet_metric_source_payload_operator_receipt_row/pass/blocked: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count']}`",
        "- field_worksheet_metric_source_payload_operator_receipt_fingerprint_verified/mismatch: "
        f"`{summary['field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count']}/"
        f"{summary['field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count']}`",
        f"- live_copy_allowed: `{summary['live_copy_allowed']}`",
        f"- public_benchmark_intake_write_allowed: `{summary['public_benchmark_intake_write_allowed']}`",
        f"- canonical_receipt_written: `{summary['canonical_receipt_written']}`",
        f"- public_benchmark_intake_written: `{summary['public_benchmark_intake_written']}`",
        "",
        "## Paths",
        "",
        f"- staging_receipt_csv: `{summary['staging_receipt_csv']}`",
        f"- live_receipt_csv: `{summary['live_receipt_csv']}`",
        f"- staging_public_benchmark_work_order_csv: `{summary['staging_public_benchmark_work_order_csv']}`",
        f"- materialized_public_benchmark_work_order_csv: `{summary['materialized_public_benchmark_work_order_csv']}`",
        f"- candidate_receipt_csv: `{summary['candidate_receipt_csv']}`",
        f"- candidate_public_benchmark_intake_csv: `{summary['candidate_public_benchmark_intake_csv']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(["", "## Rows", "", "| section | row | status | blockers |", "| --- | --- | --- | --- |"])
    for row in payload["rows"]:
        lines.append(
            f"| `{row['staging_section']}` | `{row['source_row_id']}` | "
            f"`{row['candidate_row_status']}` | `{row['candidate_blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview and optionally apply operator-filled R9 claim-evidence receipt and work-order rows."
    )
    parser.add_argument("--staging-receipt-csv", default=DEFAULT_STAGING_RECEIPT_CSV)
    parser.add_argument("--live-receipt-csv", default=DEFAULT_LIVE_RECEIPT_CSV)
    parser.add_argument("--action-board-csv", default=DEFAULT_ACTION_BOARD_CSV)
    parser.add_argument("--field-worksheet-json", default=DEFAULT_FIELD_WORKSHEET_JSON)
    parser.add_argument(
        "--staging-public-benchmark-work-order-csv",
        default=DEFAULT_STAGING_PUBLIC_BENCHMARK_WORK_ORDER_CSV,
    )
    parser.add_argument(
        "--materialized-public-benchmark-work-order-csv",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_WORK_ORDER_CSV,
    )
    parser.add_argument(
        "--materialized-public-benchmark-materialization-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    )
    parser.add_argument(
        "--materialized-public-benchmark-apply-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    )
    parser.add_argument(
        "--receptor-coordinate-validation-csv",
        default=DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV,
    )
    parser.add_argument("--metric-evidence-csv", default=DEFAULT_OUT_METRIC_EVIDENCE_CSV)
    parser.add_argument(
        "--target-public-benchmark-intake-csv",
        default=DEFAULT_TARGET_PUBLIC_BENCHMARK_INTAKE_CSV,
    )
    parser.add_argument("--candidate-receipt-csv", default=DEFAULT_CANDIDATE_RECEIPT_CSV)
    parser.add_argument(
        "--candidate-public-benchmark-intake-csv",
        default=DEFAULT_CANDIDATE_PUBLIC_BENCHMARK_INTAKE_CSV,
    )
    parser.add_argument("--mode", choices=("preview", "live_apply"), default="preview")
    parser.add_argument("--write-canonical-receipt", action="store_true")
    parser.add_argument("--write-public-benchmark-intake", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--public-benchmark-approval-token", default="")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_engine_refinement_claim_evidence_operator_staging_apply(
        staging_receipt_csv=args.staging_receipt_csv,
        live_receipt_csv=args.live_receipt_csv,
        action_board_csv=args.action_board_csv,
        field_worksheet_json=args.field_worksheet_json,
        staging_public_benchmark_work_order_csv=args.staging_public_benchmark_work_order_csv,
        materialized_public_benchmark_work_order_csv=args.materialized_public_benchmark_work_order_csv,
        materialized_public_benchmark_materialization_json=(
            args.materialized_public_benchmark_materialization_json
        ),
        materialized_public_benchmark_apply_json=args.materialized_public_benchmark_apply_json,
        receptor_coordinate_validation_csv=args.receptor_coordinate_validation_csv,
        metric_evidence_csv=args.metric_evidence_csv,
        target_public_benchmark_intake_csv=args.target_public_benchmark_intake_csv,
        candidate_receipt_csv=args.candidate_receipt_csv,
        candidate_public_benchmark_intake_csv=args.candidate_public_benchmark_intake_csv,
        mode=args.mode,
        write_canonical_receipt=bool(args.write_canonical_receipt),
        write_public_benchmark_intake=bool(args.write_public_benchmark_intake),
        approval_token=args.approval_token,
        public_benchmark_approval_token=args.public_benchmark_approval_token,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
