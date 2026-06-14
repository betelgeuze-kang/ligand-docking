#!/usr/bin/env python3
"""Validate operator-filled refine-tier benchmark work orders before intake apply."""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_readiness import (
    CLAIM_BOUNDARY,
    DEFAULT_INPUT_CSV,
    DEFAULT_OUT_METRIC_EVIDENCE_CSV,
    DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV,
    DEFAULT_OUT_WORK_ORDER_CSV,
    MIN_RECEPTOR_COORDINATE_ATOM_RECORDS,
    MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES,
    MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS,
    MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES,
    METRIC_EVIDENCE_COLUMNS,
    RECEPTOR_COORDINATE_VALIDATION_COLUMNS,
    REQUIRED_COLUMNS,
    REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN,
    WORK_ORDER_COLUMNS,
    build_refine_tier_public_benchmark_readiness,
    _coordinate_record_counts,
    _input_artifact_entries,
    _input_artifact_reference_matches,
    _input_artifact_sha256,
    _matches_target_receptor_coordinate,
    _metric_source_payload_validation,
    _metric_source_present,
    _pose_id_from_work_order_row,
    _read_coordinate_artifact_text,
    _row_status,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_work_order_apply_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_intake_candidate_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_work_order_apply_current.md"
DEFAULT_READINESS_COMMAND = "python3 tools/product/build_refine_tier_public_benchmark_readiness.py"
DEFAULT_WRITE_INTAKE_COMMAND = (
    "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py "
    f"--write-intake --approval-token {REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN}"
)

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(_text(value).startswith(PLACEHOLDER_PREFIXES) for value in row.values())


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _float(value: Any) -> float | None:
    try:
        return float(_text(value))
    except (TypeError, ValueError):
        return None


def _same_float(left: Any, right: Any) -> bool:
    left_value = _float(left)
    right_value = _float(right)
    return left_value is not None and right_value is not None and abs(left_value - right_value) <= 1e-9


def _validation_rows_by_work_order_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        work_order_id = _text(row.get("work_order_id"))
        if work_order_id:
            by_id[work_order_id] = row
    return by_id


def _metric_evidence_rows_by_work_order_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        work_order_id = _text(row.get("work_order_id"))
        if work_order_id:
            by_id[work_order_id] = row
    return by_id


def _intake_row_from_work_order(row: dict[str, Any]) -> dict[str, Any]:
    return {column: row.get(column, "") for column in REQUIRED_COLUMNS}


def _coordinate_artifact_matches_target(artifact: str, target_id: str) -> bool:
    artifact = _text(artifact)
    target = _text(target_id).lower()
    if not artifact or not target:
        return False
    candidate_name = artifact.split("::", 1)[1] if "::" in artifact else artifact
    return _matches_target_receptor_coordinate(candidate_name, target)


def _receptor_coordinate_validation_contract_blockers(
    work_order_row: dict[str, Any],
    validation_row: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    target_id = _text(work_order_row.get("target_id"))
    pose_id = _pose_id_from_work_order_row(work_order_row)
    if _text(validation_row.get("target_id")) != target_id:
        blockers.append("receptor_coordinate_validation_target_mismatch")
    if pose_id and _text(validation_row.get("pose_id")) != pose_id:
        blockers.append("receptor_coordinate_validation_pose_mismatch")

    artifact = _text(validation_row.get("receptor_coordinate_artifact"))
    if not artifact or not _bool(validation_row.get("receptor_coordinate_artifact_present")):
        blockers.append("receptor_coordinate_validation_artifact_missing")
        return blockers
    if not _coordinate_artifact_matches_target(artifact, target_id):
        blockers.append("receptor_coordinate_validation_artifact_target_mismatch")
    expected_sha256 = _text(validation_row.get("receptor_coordinate_artifact_sha256"))
    actual_sha256 = _input_artifact_sha256(artifact)
    if not expected_sha256:
        blockers.append("receptor_coordinate_validation_artifact_sha256_missing")
    elif not actual_sha256 or actual_sha256 != expected_sha256:
        blockers.append("receptor_coordinate_validation_artifact_sha256_mismatch")

    text, _source_kind, read_status = _read_coordinate_artifact_text(artifact)
    if read_status != "read":
        blockers.append(f"receptor_coordinate_validation_{read_status}")
        return blockers
    counts = _coordinate_record_counts(text)
    if counts["coordinate_atom_record_count"] < MIN_RECEPTOR_COORDINATE_ATOM_RECORDS:
        blockers.append("receptor_coordinate_validation_atom_record_count_below_min")
    if (
        counts["coordinate_macromolecule_atom_record_count"]
        < MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS
        or counts["coordinate_distinct_residue_count"] < MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES
    ):
        blockers.append("receptor_coordinate_validation_macromolecule_record_count_below_min")
    if counts["coordinate_protein_like_residue_count"] < MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES:
        blockers.append("receptor_coordinate_validation_protein_like_residue_count_below_min")
    return blockers


def _metric_evidence_contract_blockers(
    work_order_row: dict[str, Any],
    metric_evidence_row: dict[str, Any],
    validation_row: dict[str, Any] | None = None,
) -> list[str]:
    blockers: list[str] = []
    target_id = _text(work_order_row.get("target_id"))
    pose_id = _pose_id_from_work_order_row(work_order_row)
    if _text(metric_evidence_row.get("target_id")) != target_id:
        blockers.append("metric_evidence_target_mismatch")
    if pose_id and _text(metric_evidence_row.get("pose_id")) != pose_id:
        blockers.append("metric_evidence_pose_mismatch")
    for field in ("dockq", "lddt_pli", "deltaG_mm_gbsa_kcal_mol"):
        if not _same_float(work_order_row.get(field), metric_evidence_row.get(field)):
            blockers.append(f"metric_evidence_{field}_value_mismatch")
    for field in ("dockq_source_artifact", "lddt_pli_source_artifact", "internal_deltaG_source_artifact"):
        if _text(work_order_row.get(field)) != _text(metric_evidence_row.get(field)):
            blockers.append(f"metric_evidence_{field}_mismatch")
    for field in ("dockq_source_payload_valid", "lddt_pli_source_payload_valid", "internal_deltaG_source_payload_valid"):
        if not _bool(metric_evidence_row.get(field)):
            blockers.append(f"metric_evidence_{field}_not_true")

    missing_required_inputs = _text(metric_evidence_row.get("missing_required_metric_input_artifacts"))
    required_input_artifacts = _input_artifact_entries(metric_evidence_row.get("required_metric_input_artifacts"))
    required_input_hashes = _input_artifact_entries(metric_evidence_row.get("required_metric_input_artifact_sha256s"))
    if missing_required_inputs:
        blockers.append("metric_evidence_required_input_artifacts_missing")
    if not required_input_artifacts:
        blockers.append("metric_evidence_required_input_artifacts_empty")
    else:
        actual_hashes = [_input_artifact_sha256(artifact) for artifact in required_input_artifacts]
        if not all(actual_hashes):
            blockers.append("metric_evidence_required_input_artifact_sha256_missing")
        elif required_input_hashes != actual_hashes:
            blockers.append("metric_evidence_required_input_artifact_sha256_mismatch")

    validation_row = validation_row or {}
    receptor_artifact = _text(validation_row.get("receptor_coordinate_artifact"))
    receptor_sha256 = _text(validation_row.get("receptor_coordinate_artifact_sha256"))
    if receptor_artifact and not any(
        _input_artifact_reference_matches(artifact, receptor_artifact)
        for artifact in required_input_artifacts
    ):
        blockers.append("metric_evidence_required_input_receptor_coordinate_missing")
    if receptor_sha256 and receptor_sha256 not in required_input_hashes:
        blockers.append("metric_evidence_required_input_receptor_coordinate_sha256_missing")

    for metric_name, source_field, value_field in (
        ("dockq", "dockq_source_artifact", "dockq"),
        ("lddt_pli", "lddt_pli_source_artifact", "lddt_pli"),
        ("internal_deltaG", "internal_deltaG_source_artifact", "deltaG_mm_gbsa_kcal_mol"),
    ):
        source_validation = _metric_source_payload_validation(
            metric_evidence_row.get(source_field),
            expected_metric_name=metric_name,
            expected_target_id=target_id,
            expected_pose_id=pose_id,
            expected_value=work_order_row.get(value_field),
            expected_input_artifacts=required_input_artifacts,
        )
        if not bool(source_validation.get("payload_valid")):
            blockers.append(f"metric_evidence_{source_field}_payload_revalidation_failed")
    return blockers


def apply_refine_tier_public_benchmark_work_order(
    *,
    work_order_csv: str | Path = DEFAULT_OUT_WORK_ORDER_CSV,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    target_intake_csv: str | Path = DEFAULT_INPUT_CSV,
    receptor_coordinate_validation_csv: str | Path = DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV,
    metric_evidence_csv: str | Path = DEFAULT_OUT_METRIC_EVIDENCE_CSV,
    write_intake: bool = False,
    approval_token: str = "",
    max_pose_rmsd_a: float = 2.5,
    min_dockq: float = 0.23,
    min_lddt_pli: float = 0.5,
) -> dict[str, Any]:
    rows, columns, present = _read_csv(work_order_csv)
    validation_rows, validation_columns, validation_present = _read_csv(receptor_coordinate_validation_csv)
    metric_evidence_rows, metric_evidence_columns, metric_evidence_present = _read_csv(metric_evidence_csv)
    validation_missing_columns = (
        [column for column in RECEPTOR_COORDINATE_VALIDATION_COLUMNS if column not in validation_columns]
        if validation_present
        else list(RECEPTOR_COORDINATE_VALIDATION_COLUMNS)
    )
    metric_evidence_missing_columns = (
        [column for column in METRIC_EVIDENCE_COLUMNS if column not in metric_evidence_columns]
        if metric_evidence_present
        else list(METRIC_EVIDENCE_COLUMNS)
    )
    validation_by_work_order_id = _validation_rows_by_work_order_id(validation_rows)
    metric_evidence_by_work_order_id = _metric_evidence_rows_by_work_order_id(metric_evidence_rows)
    missing_work_order_columns = [column for column in WORK_ORDER_COLUMNS if column not in columns] if present else list(WORK_ORDER_COLUMNS)
    intake_rows: list[dict[str, Any]] = []
    row_reports: list[dict[str, Any]] = []
    target_intake_text = str(target_intake_csv)
    benchmark_ids = [_text(row.get("benchmark_id")) for row in rows if _text(row.get("benchmark_id"))]
    duplicate_benchmark_ids = sorted({benchmark_id for benchmark_id in benchmark_ids if benchmark_ids.count(benchmark_id) > 1})

    for idx, row in enumerate(rows):
        intake_row = _intake_row_from_work_order(row)
        work_order_id = _text(row.get("work_order_id"))
        coordinate_validation = validation_by_work_order_id.get(work_order_id, {})
        coordinate_validation_status = _text(coordinate_validation.get("coordinate_validation_status"))
        coordinate_validation_blockers = _text(coordinate_validation.get("blockers"))
        coordinate_validation_contract_blockers = (
            _receptor_coordinate_validation_contract_blockers(row, coordinate_validation)
            if validation_present and not validation_missing_columns and coordinate_validation
            else []
        )
        metric_evidence = metric_evidence_by_work_order_id.get(work_order_id, {})
        metric_evidence_status = _text(metric_evidence.get("metric_evidence_status"))
        metric_evidence_blockers = _text(metric_evidence.get("blockers"))
        metric_evidence_contract_blockers = (
            _metric_evidence_contract_blockers(row, metric_evidence, coordinate_validation)
            if metric_evidence_present and not metric_evidence_missing_columns and metric_evidence
            else []
        )
        dockq_source_present = _metric_source_present(row.get("dockq_source_artifact"))
        lddt_pli_source_present = _metric_source_present(row.get("lddt_pli_source_artifact"))
        internal_delta_g_source_present = _metric_source_present(row.get("internal_deltaG_source_artifact"))
        placeholder_present = _has_placeholder(intake_row)
        status = _row_status(
            intake_row,
            max_pose_rmsd_a=max_pose_rmsd_a,
            min_dockq=min_dockq,
            min_lddt_pli=min_lddt_pli,
        )
        blockers: list[str] = []
        if placeholder_present:
            blockers.append("operator_placeholders_unfilled")
        if _text(row.get("target_input_csv")) and _text(row.get("target_input_csv")) != target_intake_text:
            blockers.append("target_input_csv_mismatch")
        if _text(row.get("operator_action")) != "append_validated_public_benchmark_row":
            blockers.append("operator_action_unaccepted")
        if _bool(row.get("external_state_mutated")):
            blockers.append("external_state_mutation_declared")
        if _text(row.get("benchmark_id")) in duplicate_benchmark_ids:
            blockers.append("duplicate_benchmark_id")
        if not validation_present:
            blockers.append("receptor_coordinate_validation_csv_missing")
        elif validation_missing_columns:
            blockers.append("receptor_coordinate_validation_columns_missing")
        elif not coordinate_validation:
            blockers.append("receptor_coordinate_validation_row_missing")
        elif coordinate_validation_status != "pass":
            blockers.append("receptor_coordinate_validation_not_pass")
        elif coordinate_validation_contract_blockers:
            blockers.extend(coordinate_validation_contract_blockers)
        if not metric_evidence_present:
            blockers.append("metric_evidence_csv_missing")
        elif metric_evidence_missing_columns:
            blockers.append("metric_evidence_columns_missing")
        elif not metric_evidence:
            blockers.append("metric_evidence_row_missing")
        elif metric_evidence_status != "pass":
            blockers.append("metric_evidence_not_pass")
        elif metric_evidence_contract_blockers:
            blockers.extend(metric_evidence_contract_blockers)
        if not dockq_source_present:
            blockers.append("dockq_source_artifact_missing")
        if not lddt_pli_source_present:
            blockers.append("lddt_pli_source_artifact_missing")
        if not internal_delta_g_source_present:
            blockers.append("internal_deltaG_source_artifact_missing")
        if status["blockers"]:
            blockers.extend(str(status["blockers"]).split(";"))
        row_report = {
            "row_index": idx + 1,
            "work_order_id": work_order_id,
            "row_status": "pass" if not blockers else "blocked",
            "blockers": ";".join(blocker for blocker in blockers if blocker),
            "placeholder_present": placeholder_present,
            "receptor_coordinate_validation_status": coordinate_validation_status,
            "receptor_coordinate_validation_blockers": coordinate_validation_blockers,
            "receptor_coordinate_validation_contract_blockers": ";".join(coordinate_validation_contract_blockers),
            "metric_evidence_status": metric_evidence_status,
            "metric_evidence_blockers": metric_evidence_blockers,
            "metric_evidence_contract_blockers": ";".join(metric_evidence_contract_blockers),
            "required_metric_input_artifacts": metric_evidence.get("required_metric_input_artifacts", ""),
            "required_metric_input_artifact_sha256s": metric_evidence.get(
                "required_metric_input_artifact_sha256s", ""
            ),
            "missing_required_metric_input_artifacts": metric_evidence.get(
                "missing_required_metric_input_artifacts", ""
            ),
            "dockq_source_artifact": row.get("dockq_source_artifact", ""),
            "lddt_pli_source_artifact": row.get("lddt_pli_source_artifact", ""),
            "internal_deltaG_source_artifact": row.get("internal_deltaG_source_artifact", ""),
            "dockq_source_artifact_present": dockq_source_present,
            "lddt_pli_source_artifact_present": lddt_pli_source_present,
            "internal_deltaG_source_artifact_present": internal_delta_g_source_present,
            "dockq_source_payload_valid": bool(status.get("dockq_source_payload_valid")),
            "lddt_pli_source_payload_valid": bool(status.get("lddt_pli_source_payload_valid")),
            "internal_deltaG_source_payload_valid": bool(status.get("internal_deltaG_source_payload_valid")),
            "dockq_source_payload_blockers": status.get("dockq_source_payload_blockers", ""),
            "lddt_pli_source_payload_blockers": status.get("lddt_pli_source_payload_blockers", ""),
            "internal_deltaG_source_payload_blockers": status.get("internal_deltaG_source_payload_blockers", ""),
            "target_input_csv": row.get("target_input_csv", ""),
            **intake_row,
        }
        row_reports.append(row_report)
        if not blockers:
            intake_rows.append(intake_row)

    blockers: list[str] = []
    if not present:
        blockers.append("work_order_csv_missing")
    if missing_work_order_columns:
        blockers.append("work_order_columns_missing:" + ",".join(missing_work_order_columns))
    if not validation_present:
        blockers.append("receptor_coordinate_validation_csv_missing")
    if validation_present and validation_missing_columns:
        blockers.append("receptor_coordinate_validation_columns_missing:" + ",".join(validation_missing_columns))
    if not metric_evidence_present:
        blockers.append("metric_evidence_csv_missing")
    if metric_evidence_present and metric_evidence_missing_columns:
        blockers.append("metric_evidence_columns_missing:" + ",".join(metric_evidence_missing_columns))
    if not rows:
        blockers.append("work_order_rows_missing")
    blocked_rows = [row for row in row_reports if row["row_status"] != "pass"]
    if blocked_rows:
        blockers.append("blocked_work_order_rows_present")
    validation_pass_rows = [
        row for row in row_reports if _text(row.get("receptor_coordinate_validation_status")) == "pass"
    ]
    validation_missing_rows = [
        row for row in row_reports if not _text(row.get("receptor_coordinate_validation_status"))
    ]
    validation_contract_blocked_rows = [
        row for row in row_reports if _text(row.get("receptor_coordinate_validation_contract_blockers"))
    ]
    metric_evidence_pass_rows = [
        row for row in row_reports if _text(row.get("metric_evidence_status")) == "pass"
    ]
    metric_evidence_missing_rows = [
        row for row in row_reports if not _text(row.get("metric_evidence_status"))
    ]
    metric_evidence_contract_blocked_rows = [
        row for row in row_reports if _text(row.get("metric_evidence_contract_blockers"))
    ]
    metric_evidence_missing_required_input_artifact_rows = [
        row for row in row_reports if _text(row.get("missing_required_metric_input_artifacts"))
    ]
    metric_evidence_missing_required_receptor_input_rows = [
        row
        for row in row_reports
        if "metric_evidence_required_input_receptor_coordinate_missing"
        in _text(row.get("metric_evidence_contract_blockers")).split(";")
    ]
    metric_evidence_required_input_sha256_mismatch_rows = [
        row
        for row in row_reports
        if "metric_evidence_required_input_artifact_sha256_mismatch"
        in _text(row.get("metric_evidence_contract_blockers")).split(";")
        or "metric_evidence_required_input_artifact_sha256_missing"
        in _text(row.get("metric_evidence_contract_blockers")).split(";")
        or "metric_evidence_required_input_receptor_coordinate_sha256_missing"
        in _text(row.get("metric_evidence_contract_blockers")).split(";")
    ]
    missing_dockq_source_rows = [row for row in row_reports if not row["dockq_source_artifact_present"]]
    missing_lddt_source_rows = [row for row in row_reports if not row["lddt_pli_source_artifact_present"]]
    missing_internal_delta_g_source_rows = [
        row for row in row_reports if not row["internal_deltaG_source_artifact_present"]
    ]
    invalid_dockq_source_payload_rows = [
        row
        for row in row_reports
        if row["dockq_source_artifact_present"] and not row["dockq_source_payload_valid"]
    ]
    invalid_lddt_source_payload_rows = [
        row
        for row in row_reports
        if row["lddt_pli_source_artifact_present"] and not row["lddt_pli_source_payload_valid"]
    ]
    invalid_internal_delta_g_source_payload_rows = [
        row
        for row in row_reports
        if row["internal_deltaG_source_artifact_present"] and not row["internal_deltaG_source_payload_valid"]
    ]

    candidate_readiness_summary: dict[str, Any] = {}
    if present and rows and not blockers:
        with tempfile.TemporaryDirectory(prefix="refine_tier_public_benchmark_apply_") as tmpdir:
            tmp_csv = Path(tmpdir) / "candidate.csv"
            write_csv_rows(tmp_csv, intake_rows)
            candidate_readiness_summary = build_refine_tier_public_benchmark_readiness(input_csv=tmp_csv)["summary"]
        if not bool(candidate_readiness_summary.get("claim_grade_public_benchmark_ready")):
            blockers.append("candidate_readiness_gate_not_ready")
    approval_token_present = bool(_text(approval_token))
    approval_token_accepted = _text(approval_token) == REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN
    if write_intake and not approval_token_accepted:
        blockers.append("write_intake_approval_token_missing_or_invalid")
    if write_intake and blockers:
        blockers.append("write_intake_blocked_until_work_order_rows_pass")

    ready = bool(present and rows and not blockers)
    candidate_path = _resolve(out_csv)
    candidate_written = False
    intake_written = False
    if ready:
        write_csv_rows(candidate_path, intake_rows)
        candidate_written = True
        if write_intake:
            write_csv_rows(_resolve(target_intake_csv), intake_rows)
            intake_written = True
    if intake_written:
        next_required_step = "Rerun the refine-tier public benchmark readiness builder against the updated tracked intake CSV."
    elif ready:
        next_required_step = "Review the candidate intake CSV, then rerun the apply tool with --write-intake to update the tracked intake CSV."
    elif "candidate_readiness_gate_not_ready" in blockers:
        next_required_step = "Add enough valid fit and holdout/test public benchmark rows for the aggregate readiness gate, then rerun the apply tool."
    elif "write_intake_approval_token_missing_or_invalid" in blockers and not blocked_rows:
        next_required_step = "Rerun the apply tool with the required approval token after candidate readiness is green."
    else:
        next_required_step = "Fill or repair blocked work-order rows, then rerun the apply tool before touching the tracked intake CSV."

    summary = {
        "packet_type": "refine_tier_public_benchmark_work_order_apply",
        "status": (
            "refine_tier_public_benchmark_intake_written"
            if intake_written
            else "refine_tier_public_benchmark_work_order_apply_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_work_order_apply"
        ),
        "apply_ready": ready,
        "work_order_csv": str(work_order_csv),
        "work_order_csv_present": present,
        "work_order_row_count": len(rows),
        "duplicate_benchmark_ids": duplicate_benchmark_ids,
        "duplicate_benchmark_id_count": len(duplicate_benchmark_ids),
        "receptor_coordinate_validation_csv": str(receptor_coordinate_validation_csv),
        "receptor_coordinate_validation_csv_present": validation_present,
        "receptor_coordinate_validation_required": True,
        "receptor_coordinate_validation_row_count": len(validation_rows),
        "receptor_coordinate_validation_missing_column_count": len(validation_missing_columns),
        "receptor_coordinate_validation_pass_row_count": len(validation_pass_rows),
        "receptor_coordinate_validation_blocked_row_count": len(row_reports) - len(validation_pass_rows),
        "receptor_coordinate_validation_missing_row_count": len(validation_missing_rows),
        "receptor_coordinate_validation_contract_blocked_row_count": len(validation_contract_blocked_rows),
        "metric_evidence_csv": str(metric_evidence_csv),
        "metric_evidence_csv_present": metric_evidence_present,
        "metric_evidence_required": True,
        "metric_evidence_row_count": len(metric_evidence_rows),
        "metric_evidence_missing_column_count": len(metric_evidence_missing_columns),
        "metric_evidence_pass_row_count": len(metric_evidence_pass_rows),
        "metric_evidence_blocked_row_count": len(row_reports) - len(metric_evidence_pass_rows),
        "metric_evidence_missing_row_count": len(metric_evidence_missing_rows),
        "metric_evidence_contract_blocked_row_count": len(metric_evidence_contract_blocked_rows),
        "metric_evidence_missing_required_input_artifact_row_count": len(
            metric_evidence_missing_required_input_artifact_rows
        ),
        "metric_evidence_missing_required_receptor_input_row_count": len(
            metric_evidence_missing_required_receptor_input_rows
        ),
        "metric_evidence_required_input_sha256_blocked_row_count": len(
            metric_evidence_required_input_sha256_mismatch_rows
        ),
        "metric_evidence_missing_dockq_source_row_count": len(missing_dockq_source_rows),
        "metric_evidence_missing_lddt_pli_source_row_count": len(missing_lddt_source_rows),
        "metric_evidence_missing_internal_deltaG_source_row_count": len(missing_internal_delta_g_source_rows),
        "metric_evidence_invalid_dockq_source_payload_row_count": len(invalid_dockq_source_payload_rows),
        "metric_evidence_invalid_lddt_pli_source_payload_row_count": len(invalid_lddt_source_payload_rows),
        "metric_evidence_invalid_internal_deltaG_source_payload_row_count": len(
            invalid_internal_delta_g_source_payload_rows
        ),
        "candidate_intake_csv": str(out_csv),
        "candidate_intake_written": candidate_written,
        "aggregate_readiness_required": True,
        "candidate_readiness_checked": bool(candidate_readiness_summary),
        "candidate_readiness_status": candidate_readiness_summary.get("status", ""),
        "candidate_claim_grade_public_benchmark_ready": bool(
            candidate_readiness_summary.get("claim_grade_public_benchmark_ready", False)
        ),
        "candidate_readiness_blockers": candidate_readiness_summary.get("blockers", []),
        "target_intake_csv": str(target_intake_csv),
        "write_intake_requested": bool(write_intake),
        "approval_token_required": REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN if write_intake else "",
        "approval_token_present": approval_token_present,
        "approval_token_accepted": approval_token_accepted if write_intake else False,
        "intake_written": intake_written,
        "valid_intake_row_count": len(intake_rows),
        "blocked_row_count": len(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "readiness_command": DEFAULT_READINESS_COMMAND,
        "write_intake_command": DEFAULT_WRITE_INTAKE_COMMAND,
        "next_required_step": next_required_step,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": row_reports,
        "intake_rows": intake_rows,
        "required_columns": REQUIRED_COLUMNS,
        "work_order_columns": WORK_ORDER_COLUMNS,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Refine Tier Public Benchmark Work Order Apply",
        "",
        f"- status: `{summary['status']}`",
        f"- apply_ready: `{summary['apply_ready']}`",
        f"- work-order rows: `{summary['work_order_row_count']}`",
        f"- valid intake rows: `{summary['valid_intake_row_count']}`",
        f"- blocked rows: `{summary['blocked_row_count']}`",
        f"- receptor_coordinate_validation_csv: `{summary['receptor_coordinate_validation_csv']}`",
        f"- receptor coordinate validation pass/blocked/missing rows: `{summary['receptor_coordinate_validation_pass_row_count']}/{summary['receptor_coordinate_validation_blocked_row_count']}/{summary['receptor_coordinate_validation_missing_row_count']}`",
        f"- metric_evidence_csv: `{summary['metric_evidence_csv']}`",
        f"- metric evidence pass/blocked/missing rows: `{summary['metric_evidence_pass_row_count']}/{summary['metric_evidence_blocked_row_count']}/{summary['metric_evidence_missing_row_count']}`",
        f"- metric evidence missing DockQ/lDDT/internal ΔG sources: `{summary['metric_evidence_missing_dockq_source_row_count']}/{summary['metric_evidence_missing_lddt_pli_source_row_count']}/{summary['metric_evidence_missing_internal_deltaG_source_row_count']}`",
        f"- candidate_intake_written: `{summary['candidate_intake_written']}`",
        f"- candidate_readiness_checked: `{summary['candidate_readiness_checked']}`",
        f"- candidate_readiness_status: `{summary['candidate_readiness_status']}`",
        f"- intake_written: `{summary['intake_written']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- approval_token_accepted: `{summary['approval_token_accepted']}`",
        f"- blockers: `{summary['blocker_count']}`",
        f"- next_required_step: `{summary['next_required_step']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate and optionally apply refine-tier public benchmark work-order rows.")
    parser.add_argument("--work-order-csv", default=DEFAULT_OUT_WORK_ORDER_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--target-intake-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--receptor-coordinate-validation-csv", default=DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV)
    parser.add_argument("--metric-evidence-csv", default=DEFAULT_OUT_METRIC_EVIDENCE_CSV)
    parser.add_argument("--write-intake", action="store_true")
    parser.add_argument("--approval-token", default="")
    args = parser.parse_args(argv)
    payload = apply_refine_tier_public_benchmark_work_order(
        work_order_csv=args.work_order_csv,
        out_csv=args.out_csv,
        target_intake_csv=args.target_intake_csv,
        receptor_coordinate_validation_csv=args.receptor_coordinate_validation_csv,
        metric_evidence_csv=args.metric_evidence_csv,
        write_intake=bool(args.write_intake),
        approval_token=args.approval_token,
    )
    _write_json(args.out_json, payload)
    if payload["summary"]["apply_ready"] and not payload["summary"]["candidate_intake_written"]:
        write_csv_rows(_resolve(args.out_csv), payload["intake_rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
