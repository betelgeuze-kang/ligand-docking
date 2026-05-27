#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_TARGET_OBJECT_FOLDER_AUDIT_JSON = "casp17/casp17_target_object_folder_audit_current.json"
DEFAULT_TARGET_OBJECT_VIEWER_SMOKE_JSON = "casp17/casp17_target_object_viewer_smoke_current.json"
DEFAULT_TARGET_OBJECT_MODEL_REVIEW_JSON = "casp17/casp17_target_object_model_review_current.json"
DEFAULT_PROTEIN_OBJECT_LIBRARY_JSON = "casp17/casp17_protein_object_library_current.json"
DEFAULT_RAW_RANKED_MODEL_QUARANTINE_JSON = "casp17/casp17_raw_ranked_model_quarantine_audit_current.json"
DEFAULT_WIN_GAP_CLOSURE_JSON = "runs/casp17_win_gap_closure_packet_current.json"
DEFAULT_WIN_TIER_GOAL_SCORECARD_JSON = "runs/casp17_win_tier_goal_scorecard_current.json"
DEFAULT_INPUT_SCAFFOLD_JSON = "runs/casp17_win_tier_benchmark_input_scaffold_current.json"
DEFAULT_INPUT_INVENTORY_JSON = "runs/casp17_win_tier_benchmark_input_inventory_current.json"
DEFAULT_OPERATOR_DASHBOARD_JSON = "runs/casp17_win_tier_benchmark_operator_dashboard_current.json"
DEFAULT_HISTORICAL_IDENTITY_SEED_INVENTORY_JSON = "runs/casp17_historical_identity_seed_inventory_current.json"
DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_JSON = (
    "runs/casp17_historical_identity_seed_clearance_workorder_current.json"
)
DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_ACTION_BUNDLE_JSON = (
    "casp17/casp17_historical_identity_seed_clearance_action_bundle_current.json"
)
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_COMPETITIVE_BATCH_JSON = "casp17/casp17_competitive_floor_batch_current.json"
DEFAULT_COMPETITIVE_ROW_FILL_STATUS_JSON = "casp17/casp17_competitive_floor_row_fill_status_current.json"
DEFAULT_COMPETITIVE_ROW_FILL_WORKLIST_JSON = "casp17/casp17_competitive_floor_row_fill_worklist_current.json"
DEFAULT_COMPETITIVE_EVIDENCE_DROPZONE_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_COMPETITIVE_EVIDENCE_IMPORT_JSON = "casp17/casp17_competitive_floor_evidence_import_current.json"
DEFAULT_COMPETITIVE_EVIDENCE_ROUND_JSON = "casp17/casp17_competitive_floor_evidence_round_current.json"
DEFAULT_COMPETITIVE_UNLOCK_PRIORITY_JSON = "casp17/casp17_competitive_floor_evidence_unlock_priority_current.json"
DEFAULT_COMPETITIVE_IDENTITY_UNLOCK_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_COMPETITIVE_IDENTITY_UNLOCK_ROUND_JSON = "casp17/casp17_competitive_floor_identity_unlock_round_current.json"
DEFAULT_COMPETITIVE_IDENTITY_INTAKE_BUNDLE_JSON = "casp17/casp17_competitive_floor_identity_intake_bundle_current.json"
DEFAULT_COMPETITIVE_IDENTITY_INTAKE_SYNC_JSON = "casp17/casp17_competitive_floor_identity_intake_sync_current.json"
DEFAULT_COMPETITIVE_IDENTITY_CANDIDATE_JSON = "casp17/casp17_competitive_floor_identity_candidate_packet_current.json"
DEFAULT_COMPETITIVE_IDENTITY_SOURCE_REPAIR_JSON = "casp17/casp17_competitive_floor_identity_source_repair_plan_current.json"
DEFAULT_COMPETITIVE_FLOOR_UNBLOCK_MAP_JSON = "casp17/casp17_competitive_floor_unblock_map_current.json"
DEFAULT_COMPETITIVE_TARGET_IDENTITY_DISCOVERY_JSON = (
    "casp17/casp17_competitive_floor_target_identity_discovery_packet_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_QUEUE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_queue_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_WORKORDER_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_OPERATOR_INTAKE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_NATIVE_CANDIDATE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_native_candidate_packet_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_ADJUDICATION_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_adjudication_packet_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_QUEUE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_queue_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SOURCE_REPAIR_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SCORECARD_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_WORKORDER_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_WORKORDER_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_audit_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_PICKUP_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_pickup_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DUPLICATE_RESOLUTION_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_duplicate_resolution_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DECISION_BUNDLE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_bundle_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DECISION_PREFLIGHT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_preflight_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_MANIFEST_SYNC_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_WORKORDER_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_ACTION_BOARD_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_ACTION_BUNDLE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_action_bundle_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_PROMOTION_PLAN_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_INTAKE_STAGING_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_CANDIDATE_INTAKE_SYNC_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_CYCLE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_cycle_current.json"
)
DEFAULT_COMPETITIVE_IDENTITY_CYCLE_JSON = "casp17/casp17_competitive_floor_identity_cycle_current.json"
DEFAULT_COMPETITIVE_FILE_SOURCE_PLAN_JSON = "casp17/casp17_competitive_floor_file_source_plan_current.json"
DEFAULT_COMPETITIVE_VALUE_ENTRY_PLAN_JSON = "casp17/casp17_competitive_floor_value_entry_plan_current.json"
DEFAULT_COMPETITIVE_EXECUTION_BOARD_JSON = "casp17/casp17_competitive_floor_execution_board_current.json"
DEFAULT_COMPETITIVE_READINESS_GATE_JSON = "casp17/casp17_competitive_floor_readiness_gate_current.json"
DEFAULT_COMPETITIVE_VALUE_LEDGER_JSON = "casp17/casp17_competitive_floor_value_ledger_current.json"
DEFAULT_COMPETITIVE_EVIDENCE_INTAKE_JSON = "casp17/casp17_competitive_floor_evidence_intake_current.json"
DEFAULT_COMPETITIVE_PATCH_GATE_JSON = "casp17/casp17_competitive_floor_row_fill_patch_gate_current.json"
DEFAULT_COMPETITIVE_APPLY_PLAN_JSON = "casp17/casp17_competitive_floor_row_fill_apply_plan_current.json"
DEFAULT_COMPETITIVE_OPERATOR_TEMPLATE_JSON = "casp17/casp17_competitive_floor_batch_operator_template_current.json"
DEFAULT_COMPETITIVE_OPERATOR_PREFLIGHT_JSON = "casp17/casp17_competitive_floor_batch_operator_preflight_current.json"
DEFAULT_DATA_BUNDLE_JSON = "casp17/casp17_data_bundle_manifest_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_workbench_index_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_workbench_index_current.csv"
DEFAULT_OUT_MD = "casp17/WORKBENCH.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _status_rank(status: str) -> int:
    normalized = status.strip().lower()
    if normalized in {"pass", "ready"}:
        return 0
    if normalized in {"partial", "blocked_input"}:
        return 1
    if normalized in {"blocked", "missing"}:
        return 2
    return 3


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["artifact_id", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _artifact_row(
    artifact_id: str,
    label: str,
    status: str,
    path_like: str | Path,
    *,
    ready_count: int = 0,
    blocked_count: int = 0,
    total_count: int = 0,
    next_action: str = "",
    blockers: str = "",
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "label": label,
        "status": status or "missing",
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "total_count": total_count,
        "path": _artifact(path_like),
        "next_action": next_action,
        "blockers": blockers,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target_payload = _read_json(args.target_model_folders_json)
    target_object_folder_audit_payload = _read_json(args.target_object_folder_audit_json)
    target_object_viewer_smoke_payload = _read_json(args.target_object_viewer_smoke_json)
    target_object_model_review_payload = _read_json(args.target_object_model_review_json)
    protein_object_library_payload = _read_json(args.protein_object_library_json)
    raw_ranked_model_quarantine_payload = _read_json(args.raw_ranked_model_quarantine_json)
    closure_payload = _read_json(args.win_gap_closure_json)
    goal_scorecard_payload = _read_json(args.win_tier_goal_scorecard_json)
    scaffold_payload = _read_json(args.input_scaffold_json)
    inventory_payload = _read_json(args.input_inventory_json)
    dashboard_payload = _read_json(args.operator_dashboard_json)
    historical_identity_seed_inventory_payload = _read_json(args.historical_identity_seed_inventory_json)
    historical_identity_seed_clearance_payload = _read_json(args.historical_identity_seed_clearance_json)
    historical_identity_seed_clearance_action_bundle_payload = _read_json(
        args.historical_identity_seed_clearance_action_bundle_json
    )
    sidechain_native_benchmark_payload = _read_json(args.sidechain_native_benchmark_json)
    competitive_batch_payload = _read_json(args.competitive_batch_json)
    competitive_row_fill_status_payload = _read_json(args.competitive_row_fill_status_json)
    competitive_row_fill_worklist_payload = _read_json(args.competitive_row_fill_worklist_json)
    competitive_evidence_dropzone_payload = _read_json(args.competitive_evidence_dropzone_json)
    competitive_evidence_import_payload = _read_json(args.competitive_evidence_import_json)
    competitive_evidence_round_payload = _read_json(args.competitive_evidence_round_json)
    competitive_unlock_priority_payload = _read_json(args.competitive_unlock_priority_json)
    competitive_identity_unlock_payload = _read_json(args.competitive_identity_unlock_json)
    competitive_identity_round_payload = _read_json(args.competitive_identity_round_json)
    competitive_identity_intake_payload = _read_json(args.competitive_identity_intake_json)
    competitive_identity_sync_payload = _read_json(args.competitive_identity_sync_json)
    competitive_identity_candidate_payload = _read_json(args.competitive_identity_candidate_json)
    competitive_identity_source_repair_payload = _read_json(args.competitive_identity_source_repair_json)
    competitive_floor_unblock_map_payload = _read_json(args.competitive_floor_unblock_map_json)
    competitive_target_identity_discovery_payload = _read_json(args.competitive_target_identity_discovery_json)
    competitive_target_identity_clearance_payload = _read_json(args.competitive_target_identity_clearance_queue_json)
    competitive_target_identity_clearance_workorder_payload = _read_json(
        args.competitive_target_identity_clearance_workorder_json
    )
    competitive_target_identity_clearance_operator_intake_payload = _read_json(
        args.competitive_target_identity_clearance_operator_intake_json
    )
    competitive_target_identity_clearance_native_candidate_payload = _read_json(
        args.competitive_target_identity_clearance_native_candidate_json
    )
    competitive_target_identity_clearance_adjudication_payload = _read_json(
        args.competitive_target_identity_clearance_adjudication_json
    )
    competitive_target_identity_clearance_replacement_queue_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_queue_json
    )
    competitive_target_identity_clearance_replacement_source_repair_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_source_repair_json
    )
    competitive_target_identity_clearance_replacement_scorecard_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_scorecard_json
    )
    competitive_target_identity_clearance_replacement_workorder_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_workorder_json
    )
    competitive_target_identity_clearance_replacement_workorder_audit_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_workorder_audit_json
    )
    competitive_target_identity_clearance_replacement_pickup_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_pickup_json
    )
    competitive_target_identity_clearance_replacement_duplicate_resolution_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_duplicate_resolution_json
    )
    competitive_target_identity_clearance_replacement_decision_bundle_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_decision_bundle_json
    )
    competitive_target_identity_clearance_replacement_decision_preflight_payload = _read_json(
        args.competitive_target_identity_clearance_replacement_decision_preflight_json
    )
    competitive_target_identity_clearance_manifest_sync_payload = _read_json(
        args.competitive_target_identity_clearance_manifest_sync_json
    )
    competitive_target_identity_clearance_workorder_audit_payload = _read_json(
        args.competitive_target_identity_clearance_workorder_audit_json
    )
    competitive_target_identity_clearance_action_board_payload = _read_json(
        args.competitive_target_identity_clearance_action_board_json
    )
    competitive_target_identity_clearance_action_bundle_payload = _read_json(
        args.competitive_target_identity_clearance_action_bundle_json
    )
    competitive_target_identity_clearance_promotion_payload = _read_json(
        args.competitive_target_identity_clearance_promotion_plan_json
    )
    competitive_target_identity_clearance_intake_staging_payload = _read_json(
        args.competitive_target_identity_clearance_intake_staging_json
    )
    competitive_target_identity_clearance_candidate_intake_sync_payload = _read_json(
        args.competitive_target_identity_clearance_candidate_intake_sync_json
    )
    competitive_target_identity_clearance_cycle_payload = _read_json(
        args.competitive_target_identity_clearance_cycle_json
    )
    competitive_identity_cycle_payload = _read_json(args.competitive_identity_cycle_json)
    competitive_file_source_plan_payload = _read_json(args.competitive_file_source_plan_json)
    competitive_value_entry_plan_payload = _read_json(args.competitive_value_entry_plan_json)
    competitive_execution_board_payload = _read_json(args.competitive_execution_board_json)
    competitive_readiness_gate_payload = _read_json(args.competitive_readiness_gate_json)
    competitive_value_ledger_payload = _read_json(args.competitive_value_ledger_json)
    competitive_evidence_intake_payload = _read_json(args.competitive_evidence_intake_json)
    competitive_patch_gate_payload = _read_json(args.competitive_patch_gate_json)
    competitive_apply_plan_payload = _read_json(args.competitive_apply_plan_json)
    competitive_operator_template_payload = _read_json(args.competitive_operator_template_json)
    competitive_operator_preflight_payload = _read_json(args.competitive_operator_preflight_json)
    data_bundle_payload = _read_json(args.data_bundle_json)

    target_summary = _summary(target_payload)
    target_object_folder_audit_summary = _summary(target_object_folder_audit_payload)
    target_object_viewer_smoke_summary = _summary(target_object_viewer_smoke_payload)
    target_object_model_review_summary = _summary(target_object_model_review_payload)
    protein_object_library_summary = _summary(protein_object_library_payload)
    raw_ranked_model_quarantine_summary = _summary(raw_ranked_model_quarantine_payload)
    closure_summary = _summary(closure_payload)
    goal_scorecard_summary = _summary(goal_scorecard_payload)
    scaffold_summary = _summary(scaffold_payload)
    inventory_summary = _summary(inventory_payload)
    dashboard_summary = _summary(dashboard_payload)
    historical_identity_seed_inventory_summary = _summary(historical_identity_seed_inventory_payload)
    historical_identity_seed_clearance_summary = _summary(historical_identity_seed_clearance_payload)
    historical_identity_seed_clearance_phase_open_counts = historical_identity_seed_clearance_summary.get(
        "phase_open_counts"
    )
    if not isinstance(historical_identity_seed_clearance_phase_open_counts, dict):
        historical_identity_seed_clearance_phase_open_counts = {}
    historical_identity_seed_clearance_action_bundle_summary = _summary(
        historical_identity_seed_clearance_action_bundle_payload
    )
    sidechain_native_benchmark_summary = _summary(sidechain_native_benchmark_payload)
    competitive_batch_summary = _summary(competitive_batch_payload)
    competitive_row_fill_status_summary = _summary(competitive_row_fill_status_payload)
    competitive_row_fill_worklist_summary = _summary(competitive_row_fill_worklist_payload)
    competitive_evidence_dropzone_summary = _summary(competitive_evidence_dropzone_payload)
    competitive_evidence_import_summary = _summary(competitive_evidence_import_payload)
    competitive_evidence_round_summary = _summary(competitive_evidence_round_payload)
    competitive_unlock_priority_summary = _summary(competitive_unlock_priority_payload)
    competitive_identity_unlock_summary = _summary(competitive_identity_unlock_payload)
    competitive_identity_round_summary = _summary(competitive_identity_round_payload)
    competitive_identity_intake_summary = _summary(competitive_identity_intake_payload)
    competitive_identity_sync_summary = _summary(competitive_identity_sync_payload)
    competitive_identity_candidate_summary = _summary(competitive_identity_candidate_payload)
    competitive_identity_source_repair_summary = _summary(competitive_identity_source_repair_payload)
    competitive_floor_unblock_map_summary = _summary(competitive_floor_unblock_map_payload)
    competitive_floor_unblock_map_phase_open_counts = competitive_floor_unblock_map_summary.get("phase_open_counts")
    if not isinstance(competitive_floor_unblock_map_phase_open_counts, dict):
        competitive_floor_unblock_map_phase_open_counts = {}
    competitive_target_identity_discovery_summary = _summary(competitive_target_identity_discovery_payload)
    competitive_target_identity_clearance_summary = _summary(competitive_target_identity_clearance_payload)
    competitive_target_identity_clearance_workorder_summary = _summary(
        competitive_target_identity_clearance_workorder_payload
    )
    competitive_target_identity_clearance_operator_intake_summary = _summary(
        competitive_target_identity_clearance_operator_intake_payload
    )
    competitive_target_identity_clearance_native_candidate_summary = _summary(
        competitive_target_identity_clearance_native_candidate_payload
    )
    competitive_target_identity_clearance_adjudication_summary = _summary(
        competitive_target_identity_clearance_adjudication_payload
    )
    competitive_target_identity_clearance_replacement_queue_summary = _summary(
        competitive_target_identity_clearance_replacement_queue_payload
    )
    competitive_target_identity_clearance_replacement_source_repair_summary = _summary(
        competitive_target_identity_clearance_replacement_source_repair_payload
    )
    competitive_target_identity_clearance_replacement_source_repair_ready_count = (
        _int(competitive_target_identity_clearance_replacement_source_repair_summary.get("source_ready_count"))
        + _int(competitive_target_identity_clearance_replacement_source_repair_summary.get("ready_for_prediction_count"))
        + _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get(
                "ready_for_validation_scorecard_count"
            )
        )
    )
    competitive_target_identity_clearance_replacement_scorecard_summary = _summary(
        competitive_target_identity_clearance_replacement_scorecard_payload
    )
    competitive_target_identity_clearance_replacement_workorder_summary = _summary(
        competitive_target_identity_clearance_replacement_workorder_payload
    )
    competitive_target_identity_clearance_replacement_workorder_audit_summary = _summary(
        competitive_target_identity_clearance_replacement_workorder_audit_payload
    )
    competitive_target_identity_clearance_replacement_pickup_summary = _summary(
        competitive_target_identity_clearance_replacement_pickup_payload
    )
    competitive_target_identity_clearance_replacement_duplicate_resolution_summary = _summary(
        competitive_target_identity_clearance_replacement_duplicate_resolution_payload
    )
    competitive_target_identity_clearance_replacement_decision_bundle_summary = _summary(
        competitive_target_identity_clearance_replacement_decision_bundle_payload
    )
    competitive_target_identity_clearance_replacement_decision_preflight_summary = _summary(
        competitive_target_identity_clearance_replacement_decision_preflight_payload
    )
    competitive_target_identity_clearance_manifest_sync_summary = _summary(
        competitive_target_identity_clearance_manifest_sync_payload
    )
    competitive_target_identity_clearance_workorder_audit_summary = _summary(
        competitive_target_identity_clearance_workorder_audit_payload
    )
    competitive_target_identity_clearance_action_board_summary = _summary(
        competitive_target_identity_clearance_action_board_payload
    )
    competitive_target_identity_clearance_action_bundle_summary = _summary(
        competitive_target_identity_clearance_action_bundle_payload
    )
    competitive_target_identity_clearance_promotion_summary = _summary(
        competitive_target_identity_clearance_promotion_payload
    )
    competitive_target_identity_clearance_intake_staging_summary = _summary(
        competitive_target_identity_clearance_intake_staging_payload
    )
    competitive_target_identity_clearance_candidate_intake_sync_summary = _summary(
        competitive_target_identity_clearance_candidate_intake_sync_payload
    )
    competitive_target_identity_clearance_cycle_summary = _summary(
        competitive_target_identity_clearance_cycle_payload
    )
    competitive_identity_cycle_summary = _summary(competitive_identity_cycle_payload)
    competitive_file_source_plan_summary = _summary(competitive_file_source_plan_payload)
    competitive_value_entry_plan_summary = _summary(competitive_value_entry_plan_payload)
    competitive_execution_board_summary = _summary(competitive_execution_board_payload)
    competitive_readiness_gate_summary = _summary(competitive_readiness_gate_payload)
    competitive_value_ledger_summary = _summary(competitive_value_ledger_payload)
    competitive_evidence_intake_summary = _summary(competitive_evidence_intake_payload)
    competitive_patch_gate_summary = _summary(competitive_patch_gate_payload)
    competitive_apply_plan_summary = _summary(competitive_apply_plan_payload)
    competitive_operator_template_summary = _summary(competitive_operator_template_payload)
    competitive_operator_preflight_summary = _summary(competitive_operator_preflight_payload)
    data_bundle_summary = _summary(data_bundle_payload)

    target_rows = _rows(target_payload)
    missing_target_folders = [
        row.get("target_id", "")
        for row in target_rows
        if _text(row.get("folder_status")) != "ready"
    ]
    missing_target_folders = [target for target in missing_target_folders if target]

    first_operator_action = _text(closure_summary.get("first_operator_input_action_id"))
    first_operator_blockers = _text(closure_summary.get("first_operator_input_blockers"))
    first_fill_action = ""
    dashboard_rows = _rows(dashboard_payload)
    if dashboard_rows:
        ordered = sorted(dashboard_rows, key=lambda row: (_status_rank(_text(row.get("operator_row_status"))), _int(row.get("row_rank"))))
        first_fill_action = _text(ordered[0].get("next_action")) if ordered else ""
    target_object_folder_audit_blockers = (
        "protein_atom_objects:"
        + str(target_object_folder_audit_summary.get("protein_atom_pass_count", ""))
        + ",coordinate_valid_objects:"
        + str(target_object_folder_audit_summary.get("coordinate_valid_pass_count", ""))
        + ",total_protein_atoms:"
        + str(target_object_folder_audit_summary.get("total_protein_atom_count", ""))
    )
    first_object_folder_blockers = _text(target_object_folder_audit_summary.get("first_blocked_blockers"))
    if first_object_folder_blockers:
        target_object_folder_audit_blockers += ",first_blocked:" + first_object_folder_blockers

    artifact_rows = [
        _artifact_row(
            "target_model_folders",
            "Per-target 3D model folders",
            _text(target_summary.get("packet_type")) and ("ready" if _int(target_summary.get("blocked_count")) == 0 else "blocked"),
            args.target_model_folders_json,
            ready_count=_int(target_summary.get("ready_count")),
            blocked_count=_int(target_summary.get("blocked_count")),
            total_count=_int(target_summary.get("target_count")),
            next_action="Use per-protein folders for local visual review and submission-readiness inspection.",
            blockers=",".join(missing_target_folders),
        ),
        _artifact_row(
            "target_object_catalog",
            "Per-object chain-level 3D model catalog",
            "ready"
            if _int(target_summary.get("total_object_count"))
            and _int(target_summary.get("total_object_count")) == _int(target_summary.get("total_object_projection_files"))
            and _int(target_summary.get("total_object_count")) == _int(target_summary.get("total_object_viewer_files"))
            else "blocked",
            _text(target_summary.get("object_catalog_md")) or "casp17/casp17_target_object_models_current.md",
            ready_count=min(
                _int(target_summary.get("total_object_projection_files")),
                _int(target_summary.get("total_object_viewer_files")),
            ),
            blocked_count=max(
                0,
                _int(target_summary.get("total_object_count"))
                - min(
                    _int(target_summary.get("total_object_projection_files")),
                    _int(target_summary.get("total_object_viewer_files")),
                ),
            ),
            total_count=_int(target_summary.get("total_object_count")),
            next_action="Open the per-object catalog for chain-level PDB, projection, and local viewer review.",
            blockers=(
                "projection_missing_count:"
                + str(
                    max(
                        0,
                        _int(target_summary.get("total_object_count"))
                        - _int(target_summary.get("total_object_projection_files")),
                    )
                )
                + ",viewer_missing_count:"
                + str(
                    max(
                        0,
                        _int(target_summary.get("total_object_count"))
                        - _int(target_summary.get("total_object_viewer_files")),
                    )
                )
            ),
        ),
        _artifact_row(
            "target_object_folder_audit",
            "Audit for per-protein object folders and chain-level 3D files",
            _text(target_object_folder_audit_summary.get("folder_audit_status")),
            args.target_object_folder_audit_json,
            ready_count=_int(target_object_folder_audit_summary.get("pass_count")),
            blocked_count=_int(target_object_folder_audit_summary.get("blocked_count")),
            total_count=_int(target_object_folder_audit_summary.get("object_row_count")),
            next_action="Keep this pass before treating per-protein object folders as independently reviewable.",
            blockers=target_object_folder_audit_blockers,
        ),
        _artifact_row(
            "target_object_viewer_smoke",
            "Smoke audit for per-object local 3D viewers",
            _text(target_object_viewer_smoke_summary.get("smoke_status")),
            args.target_object_viewer_smoke_json,
            ready_count=_int(target_object_viewer_smoke_summary.get("pass_count")),
            blocked_count=_int(target_object_viewer_smoke_summary.get("blocked_count")),
            total_count=_int(target_object_viewer_smoke_summary.get("object_row_count")),
            next_action="Keep this pass before relying on per-object viewer artifacts for review.",
            blockers=_text(target_object_viewer_smoke_summary.get("first_blocked_blockers")),
        ),
        _artifact_row(
            "target_object_model_review",
            "Per-object molecular geometry review packet",
            _text(target_object_model_review_summary.get("object_model_review_status")),
            args.target_object_model_review_json,
            ready_count=_int(target_object_model_review_summary.get("pass_count")),
            blocked_count=_int(target_object_model_review_summary.get("blocked_count")),
            total_count=_int(target_object_model_review_summary.get("object_count")),
            next_action="Open object review markdown files for per-chain molecular geometry inspection.",
            blockers=(
                "review_md:"
                + str(target_object_model_review_summary.get("review_md_count", ""))
                + ",viewer_local:"
                + str(target_object_model_review_summary.get("viewer_local_pass_count", ""))
                + ",protein_atoms:"
                + str(target_object_model_review_summary.get("protein_atom_count", ""))
                + ",radius:"
                + str(target_object_model_review_summary.get("min_radius_of_gyration", ""))
                + "-"
                + str(target_object_model_review_summary.get("max_radius_of_gyration", ""))
                + ",gallery:"
                + str(target_object_model_review_summary.get("gallery_status", ""))
            ),
        ),
        _artifact_row(
            "protein_object_library",
            "Protein-name folders for individual 3D object model review",
            _text(protein_object_library_summary.get("protein_object_library_status")),
            args.protein_object_library_json,
            ready_count=_int(protein_object_library_summary.get("pass_count")),
            blocked_count=_int(protein_object_library_summary.get("blocked_count")),
            total_count=_int(protein_object_library_summary.get("object_folder_count")),
            next_action="Use the protein-name library folders for object-by-object molecular review.",
            blockers=(
                "protein_folders:"
                + str(protein_object_library_summary.get("protein_folder_count", ""))
                + ",model_projection_viewer:"
                + str(protein_object_library_summary.get("model_pointer_count", ""))
                + "/"
                + str(protein_object_library_summary.get("projection_pointer_count", ""))
                + "/"
                + str(protein_object_library_summary.get("viewer_pointer_count", ""))
                + ",first_blocked:"
                + (_text(protein_object_library_summary.get("first_blocked_blockers")) or "-")
            ),
        ),
        _artifact_row(
            "raw_ranked_model_quarantine",
            "Quarantine audit for untracked raw-ranked internal model PDBs",
            _text(raw_ranked_model_quarantine_summary.get("raw_ranked_model_quarantine_status")),
            args.raw_ranked_model_quarantine_json,
            ready_count=_int(raw_ranked_model_quarantine_summary.get("linked_object_library_count")),
            blocked_count=max(
                0,
                _int(raw_ranked_model_quarantine_summary.get("raw_ranked_model_count"))
                - _int(raw_ranked_model_quarantine_summary.get("linked_object_library_count")),
            ),
            total_count=_int(raw_ranked_model_quarantine_summary.get("raw_ranked_model_count")),
            next_action=(
                "Keep raw-ranked PDBs quarantined and use reviewed protein/object folders for commit-safe inspection."
            ),
            blockers=(
                "targets:"
                + str(raw_ranked_model_quarantine_summary.get("target_count", ""))
                + ",top5:"
                + str(raw_ranked_model_quarantine_summary.get("complete_top5_target_count", ""))
                + ",quarantined:"
                + str(raw_ranked_model_quarantine_summary.get("quarantined_count", ""))
                + ",author_present:"
                + str(raw_ranked_model_quarantine_summary.get("author_record_present_count", ""))
                + ",atoms:"
                + str(raw_ranked_model_quarantine_summary.get("total_atom_record_count", ""))
            ),
        ),
        _artifact_row(
            "win_gap_closure",
            "CASP17 win-gap closure state",
            _text(closure_summary.get("closure_status")),
            args.win_gap_closure_json,
            ready_count=_int(closure_summary.get("closed_count")),
            blocked_count=_int(closure_summary.get("not_closed_count")),
            total_count=_int(closure_summary.get("requirement_count")),
            next_action=first_operator_action or _text(closure_summary.get("first_open_action_id")),
            blockers=first_operator_blockers or _text(closure_summary.get("first_open_blockers")),
        ),
        _artifact_row(
            "win_tier_goal_scorecard",
            "CASP17 scaffold/proof/category win-tier goal scorecard",
            _text(goal_scorecard_summary.get("scorecard_status")),
            args.win_tier_goal_scorecard_json,
            ready_count=_int(goal_scorecard_summary.get("pass_count")),
            blocked_count=(
                _int(goal_scorecard_summary.get("partial_count"))
                + _int(goal_scorecard_summary.get("blocked_count"))
            ),
            total_count=_int(goal_scorecard_summary.get("row_count")),
            next_action=_text(goal_scorecard_summary.get("first_blocked_next_action")),
            blockers=_text(goal_scorecard_summary.get("first_blocked_gate")),
        ),
        _artifact_row(
            "benchmark_input_scaffold",
            "No-leak historical benchmark row folders",
            _text(scaffold_summary.get("scaffold_status")),
            args.input_scaffold_json,
            ready_count=_int(scaffold_summary.get("ready_count")),
            blocked_count=_int(scaffold_summary.get("blocked_count")),
            total_count=_int(scaffold_summary.get("row_count")),
            next_action="Fill row folders with cleared historical target identity, internal predictions, native files, provenance, and calibration values.",
            blockers="missing_evidence_items:" + str(scaffold_summary.get("missing_evidence_item_count", "")),
        ),
        _artifact_row(
            "benchmark_input_inventory",
            "No-leak benchmark input inventory",
            _text(inventory_summary.get("inventory_status")),
            args.input_inventory_json,
            ready_count=_int(inventory_summary.get("ready_row_count")),
            blocked_count=_int(inventory_summary.get("blocked_row_count")),
            total_count=_int(inventory_summary.get("row_count")),
            next_action=first_fill_action or "Replace placeholder rows and populate required files/provenance/calibration.",
            blockers="missing_files:" + str(inventory_summary.get("missing_file_count", "")),
        ),
        _artifact_row(
            "operator_dashboard",
            "Operator dashboard for 40 benchmark rows",
            _text(dashboard_summary.get("dashboard_status")),
            args.operator_dashboard_json,
            ready_count=_int(dashboard_summary.get("ready_count")),
            blocked_count=_int(dashboard_summary.get("blocked_count")),
            total_count=_int(dashboard_summary.get("row_count")),
            next_action=first_fill_action,
            blockers=_text(dashboard_summary.get("source_blockers")),
        ),
        _artifact_row(
            "historical_identity_seed_inventory",
            "Local historical identity seed candidates for operator no-leak review",
            _text(historical_identity_seed_inventory_summary.get("seed_inventory_status")),
            args.historical_identity_seed_inventory_json,
            ready_count=_int(historical_identity_seed_inventory_summary.get("batch_seed_slot_count")),
            blocked_count=_int(historical_identity_seed_inventory_summary.get("operator_clearance_required_count")),
            total_count=_int(historical_identity_seed_inventory_summary.get("seed_candidate_count")),
            next_action=_text(historical_identity_seed_inventory_summary.get("first_next_action")),
            blockers=(
                "monomer_complex:"
                + str(historical_identity_seed_inventory_summary.get("monomer_seed_candidate_count", ""))
                + "/"
                + str(historical_identity_seed_inventory_summary.get("complex_seed_candidate_count", ""))
                + ",eligible:"
                + str(historical_identity_seed_inventory_summary.get("eligible_monomer_seed_count", ""))
                + "/"
                + str(historical_identity_seed_inventory_summary.get("eligible_complex_seed_count", ""))
                + ",batch:"
                + str(historical_identity_seed_inventory_summary.get("batch_seed_slot_count", ""))
                + ",manifest:"
                + str(historical_identity_seed_inventory_summary.get("candidate_manifest_row_count", ""))
            ),
        ),
        _artifact_row(
            "historical_identity_seed_clearance_workorder",
            "Operator clearance gate for historical identity seed candidates",
            _text(historical_identity_seed_clearance_summary.get("seed_clearance_status")),
            args.historical_identity_seed_clearance_json,
            ready_count=_int(historical_identity_seed_clearance_summary.get("ready_seed_count")),
            blocked_count=_int(historical_identity_seed_clearance_summary.get("awaiting_seed_count")),
            total_count=_int(historical_identity_seed_clearance_summary.get("seed_row_count")),
            next_action=_text(historical_identity_seed_clearance_summary.get("first_open_next_action")),
            blockers=(
                "phase_open:"
                + str(historical_identity_seed_clearance_phase_open_counts.get("identity", ""))
                + "/"
                + str(historical_identity_seed_clearance_phase_open_counts.get("core_files", ""))
                + "/"
                + str(historical_identity_seed_clearance_phase_open_counts.get("no_leak_provenance", ""))
                + "/"
                + str(historical_identity_seed_clearance_phase_open_counts.get("calibration", ""))
                + "/"
                + str(historical_identity_seed_clearance_phase_open_counts.get("ablation", ""))
                + ",cleared_manifest:"
                + str(historical_identity_seed_clearance_summary.get("cleared_manifest_row_count", ""))
                + ",blocking_fields:"
                + str(historical_identity_seed_clearance_summary.get("blocking_field_count", ""))
            ),
        ),
        _artifact_row(
            "historical_identity_seed_clearance_action_bundle",
            "Per-seed request folders for historical identity seed clearance",
            _text(historical_identity_seed_clearance_action_bundle_summary.get("seed_clearance_action_bundle_status")),
            args.historical_identity_seed_clearance_action_bundle_json,
            ready_count=(
                _int(historical_identity_seed_clearance_action_bundle_summary.get("action_count"))
                - _int(historical_identity_seed_clearance_action_bundle_summary.get("open_action_count"))
            ),
            blocked_count=_int(historical_identity_seed_clearance_action_bundle_summary.get("open_action_count")),
            total_count=_int(historical_identity_seed_clearance_action_bundle_summary.get("action_count")),
            next_action=_text(historical_identity_seed_clearance_action_bundle_summary.get("first_open_action_md")),
            blockers=(
                "targets:"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("target_count", ""))
                + ",folders:"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("action_folder_count", ""))
                + ",files:"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("bundle_file_count", ""))
                + ",lanes:"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("identity_action_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("core_file_action_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("no_leak_action_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("calibration_action_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_action_bundle_summary.get("ablation_action_count", ""))
            ),
        ),
        _artifact_row(
            "sidechain_native_benchmark",
            "No-leak historical sidechain/native benchmark exactness and sidechain metric gate",
            _text(sidechain_native_benchmark_summary.get("sidechain_native_benchmark_status")),
            args.sidechain_native_benchmark_json,
            ready_count=_int(sidechain_native_benchmark_summary.get("pass_count")),
            blocked_count=_int(sidechain_native_benchmark_summary.get("blocked_count")),
            total_count=_int(sidechain_native_benchmark_summary.get("benchmark_count")),
            next_action=_text(sidechain_native_benchmark_summary.get("first_open_next_action")),
            blockers=_text(
                sidechain_native_benchmark_summary.get("first_blocked_blockers")
                or sidechain_native_benchmark_summary.get("manifest_blockers")
            ),
        ),
        _artifact_row(
            "competitive_floor_batch",
            "First 15 no-leak benchmark rows for competitive-floor unlock",
            _text(competitive_batch_summary.get("batch_status")),
            args.competitive_batch_json,
            ready_count=_int(competitive_batch_summary.get("copied_row_scaffold_count")),
            blocked_count=max(
                0,
                _int(competitive_batch_summary.get("row_count"))
                - _int(competitive_batch_summary.get("copied_row_scaffold_count")),
            ),
            total_count=_int(competitive_batch_summary.get("row_count")),
            next_action="Fill the copied competitive-floor task folders before expanding to the full 40-row win-tier set.",
            blockers="missing_evidence_items:" + str(competitive_batch_summary.get("missing_evidence_item_count", "")),
        ),
        _artifact_row(
            "competitive_floor_row_fill_status",
            "Single-file row_fill completion status for competitive-floor rows",
            _text(competitive_row_fill_status_summary.get("row_fill_status")),
            args.competitive_row_fill_status_json,
            ready_count=_int(competitive_row_fill_status_summary.get("ready_for_operator_template_count")),
            blocked_count=_int(competitive_row_fill_status_summary.get("blocked_or_awaiting_count")),
            total_count=_int(competitive_row_fill_status_summary.get("row_count")),
            next_action=_text(competitive_row_fill_status_summary.get("first_open_next_action")),
            blockers=(
                "filled:"
                + str(competitive_row_fill_status_summary.get("row_fill_filled_count", ""))
                + ",missing_fields:"
                + str(competitive_row_fill_status_summary.get("missing_required_field_count", ""))
                + ",placeholders:"
                + str(competitive_row_fill_status_summary.get("placeholder_field_count", ""))
                + ",missing_files:"
                + str(competitive_row_fill_status_summary.get("missing_local_file_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_row_fill_worklist",
            "Field-level operator action list for competitive-floor row_fill files",
            _text(competitive_row_fill_worklist_summary.get("worklist_status")),
            args.competitive_row_fill_worklist_json,
            ready_count=max(
                0,
                _int(competitive_row_fill_worklist_summary.get("row_count"))
                - _int(competitive_row_fill_worklist_summary.get("open_action_count")),
            ),
            blocked_count=_int(competitive_row_fill_worklist_summary.get("open_action_count")),
            total_count=_int(competitive_row_fill_worklist_summary.get("row_count")),
            next_action=_text(competitive_row_fill_worklist_summary.get("first_action_recommended_action")),
            blockers=_text(competitive_row_fill_worklist_summary.get("first_action_blocker")),
        ),
        _artifact_row(
            "competitive_floor_evidence_dropzone",
            "Per-row evidence dropzones for competitive-floor file and field fills",
            _text(competitive_evidence_dropzone_summary.get("dropzone_status")),
            args.competitive_evidence_dropzone_json,
            ready_count=max(
                0,
                _int(competitive_evidence_dropzone_summary.get("dropzone_count"))
                - _int(competitive_evidence_dropzone_summary.get("open_action_count")),
            ),
            blocked_count=_int(competitive_evidence_dropzone_summary.get("open_action_count")),
            total_count=_int(competitive_evidence_dropzone_summary.get("dropzone_count")),
            next_action=_text(competitive_evidence_dropzone_summary.get("first_action_note")),
            blockers=_text(competitive_evidence_dropzone_summary.get("first_action_blocker")),
        ),
        _artifact_row(
            "competitive_floor_evidence_import",
            "Central import CSV for competitive-floor file copies and value-ledger updates",
            _text(competitive_evidence_import_summary.get("import_status")),
            args.competitive_evidence_import_json,
            ready_count=_int(competitive_evidence_import_summary.get("ready_for_apply_count"))
            + _int(competitive_evidence_import_summary.get("applied_count"))
            + _int(competitive_evidence_import_summary.get("already_imported_count")),
            blocked_count=(
                _int(competitive_evidence_import_summary.get("awaiting_import_file_count"))
                + _int(competitive_evidence_import_summary.get("awaiting_import_value_count"))
                + _int(competitive_evidence_import_summary.get("awaiting_clearance_count"))
                + _int(competitive_evidence_import_summary.get("awaiting_evidence_ref_count"))
                + _int(competitive_evidence_import_summary.get("blocked_count"))
            ),
            total_count=_int(competitive_evidence_import_summary.get("action_count")),
            next_action=_text(competitive_evidence_import_summary.get("first_open_next_action")),
            blockers=_text(competitive_evidence_import_summary.get("first_open_status")),
        ),
        _artifact_row(
            "competitive_floor_evidence_round",
            "One-shot evidence import/intake/patch/apply-plan round",
            _text(competitive_evidence_round_summary.get("round_status")),
            args.competitive_evidence_round_json,
            ready_count=(
                _int(competitive_evidence_round_summary.get("import_ready_for_apply_count"))
                + _int(competitive_evidence_round_summary.get("intake_patch_candidate_count"))
                + _int(competitive_evidence_round_summary.get("patch_gate_ready_to_patch_count"))
                + _int(competitive_evidence_round_summary.get("apply_plan_planned_patch_count"))
            ),
            blocked_count=(
                _int(competitive_evidence_round_summary.get("import_awaiting_file_count"))
                + _int(competitive_evidence_round_summary.get("import_awaiting_value_count"))
            ),
            total_count=_int(competitive_evidence_round_summary.get("stage_count")),
            next_action=_text(competitive_evidence_round_summary.get("first_next_action")),
            blockers=_text(competitive_evidence_round_summary.get("round_status")),
        ),
        _artifact_row(
            "competitive_floor_unlock_priority",
            "Unlock priority for competitive-floor evidence imports",
            _text(competitive_unlock_priority_summary.get("unlock_status")),
            args.competitive_unlock_priority_json,
            ready_count=(
                _int(competitive_unlock_priority_summary.get("phase_row_count"))
                if not _int(competitive_unlock_priority_summary.get("identity_open_action_count"))
                else 0
            ),
            blocked_count=(
                _int(competitive_unlock_priority_summary.get("identity_open_action_count"))
                + _int(competitive_unlock_priority_summary.get("file_actions_waiting_on_identity_count"))
            ),
            total_count=_int(competitive_unlock_priority_summary.get("phase_row_count")),
            next_action=_text(competitive_unlock_priority_summary.get("first_open_next_action")),
            blockers=_text(competitive_unlock_priority_summary.get("first_open_phase")),
        ),
        _artifact_row(
            "competitive_floor_identity_unlock_kit",
            "Compact identity unlock CSV for benchmark_id and target_id imports",
            _text(competitive_identity_unlock_summary.get("identity_unlock_status")),
            args.competitive_identity_unlock_json,
            ready_count=_int(competitive_identity_unlock_summary.get("ready_for_import_count")),
            blocked_count=(
                _int(competitive_identity_unlock_summary.get("awaiting_identity_count"))
                + _int(competitive_identity_unlock_summary.get("blocked_identity_count"))
            ),
            total_count=_int(competitive_identity_unlock_summary.get("row_count")),
            next_action="Fill proposed_benchmark_id/proposed_target_id/evidence_ref/operator_clearance, then apply the kit.",
            blockers=_text(competitive_identity_unlock_summary.get("first_open_blockers")),
        ),
        _artifact_row(
            "competitive_floor_identity_unlock_round",
            "One-shot identity kit/import/unlock-priority round",
            _text(competitive_identity_round_summary.get("identity_round_status")),
            args.competitive_identity_round_json,
            ready_count=(
                _int(competitive_identity_round_summary.get("identity_ready_for_import_count"))
                + _int(competitive_identity_round_summary.get("import_ready_for_apply_count"))
            ),
            blocked_count=(
                _int(competitive_identity_round_summary.get("identity_awaiting_count"))
                + _int(competitive_identity_round_summary.get("identity_blocked_count"))
                + _int(competitive_identity_round_summary.get("target_id_open_count"))
            ),
            total_count=_int(competitive_identity_round_summary.get("row_count")),
            next_action=_text(competitive_identity_round_summary.get("first_next_action")),
            blockers=(
                "identity_open:"
                + str(competitive_identity_round_summary.get("identity_open_action_count", ""))
                + ",files_waiting:"
                + str(competitive_identity_round_summary.get("file_actions_waiting_on_identity_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_identity_intake_bundle",
            "Operator identity intake bundle for clearing the competitive-floor identity gate",
            _text(competitive_identity_intake_summary.get("identity_intake_status")),
            args.competitive_identity_intake_json,
            ready_count=_int(competitive_identity_intake_summary.get("ready_for_identity_apply_count")),
            blocked_count=(
                _int(competitive_identity_intake_summary.get("awaiting_identity_count"))
                + _int(competitive_identity_intake_summary.get("blocked_identity_count"))
            ),
            total_count=_int(competitive_identity_intake_summary.get("row_count")),
            next_action=_text(competitive_identity_intake_summary.get("first_open_next_action")),
            blockers="missing_fields:" + str(competitive_identity_intake_summary.get("missing_field_count", "")),
        ),
        _artifact_row(
            "competitive_floor_identity_intake_sync",
            "Dry-run/apply bridge from identity intake bundle into identity unlock kit",
            _text(competitive_identity_sync_summary.get("identity_intake_sync_status")),
            args.competitive_identity_sync_json,
            ready_count=(
                _int(competitive_identity_sync_summary.get("synced_count"))
                + _int(competitive_identity_sync_summary.get("ready_to_sync_count"))
            ),
            blocked_count=(
                _int(competitive_identity_sync_summary.get("awaiting_intake_count"))
                + _int(competitive_identity_sync_summary.get("blocked_count"))
            ),
            total_count=_int(competitive_identity_sync_summary.get("row_count")),
            next_action=_text(competitive_identity_sync_summary.get("first_open_next_action")),
            blockers="missing_fields:" + str(competitive_identity_sync_summary.get("missing_field_count", "")),
        ),
        _artifact_row(
            "competitive_floor_identity_candidate_packet",
            "Local historical/operator manifest candidates for identity intake",
            _text(competitive_identity_candidate_summary.get("identity_candidate_status")),
            args.competitive_identity_candidate_json,
            ready_count=_int(competitive_identity_candidate_summary.get("ready_for_intake_count")),
            blocked_count=_int(competitive_identity_candidate_summary.get("awaiting_candidate_source_count")),
            total_count=_int(competitive_identity_candidate_summary.get("row_count")),
            next_action=_text(competitive_identity_candidate_summary.get("first_open_next_action")),
            blockers=(
                "source_ready:"
                + str(competitive_identity_candidate_summary.get("source_ready_candidate_count", ""))
                + ",source_blocked:"
                + str(competitive_identity_candidate_summary.get("source_blocked_candidate_count", ""))
                + ",operator_preflight:"
                + str(competitive_identity_candidate_summary.get("operator_preflight_status", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_unblock_map",
            "Compact blocker map for the first 15 competitive-floor rows",
            _text(competitive_floor_unblock_map_summary.get("unblock_map_status")),
            args.competitive_floor_unblock_map_json,
            ready_count=_int(competitive_floor_unblock_map_summary.get("ready_for_intake_count")),
            blocked_count=_int(competitive_floor_unblock_map_summary.get("awaiting_candidate_source_count")),
            total_count=_int(competitive_floor_unblock_map_summary.get("row_count")),
            next_action=_text(competitive_floor_unblock_map_summary.get("first_open_next_action")),
            blockers=(
                "phase_open:"
                + str(competitive_floor_unblock_map_phase_open_counts.get("target_identity", ""))
                + "/"
                + str(competitive_floor_unblock_map_phase_open_counts.get("core_files", ""))
                + "/"
                + str(competitive_floor_unblock_map_phase_open_counts.get("no_leak_provenance", ""))
                + "/"
                + str(competitive_floor_unblock_map_phase_open_counts.get("ablation_files", ""))
                + "/"
                + str(competitive_floor_unblock_map_phase_open_counts.get("calibration_values", ""))
                + ",blocking_fields:"
                + str(competitive_floor_unblock_map_summary.get("blocking_field_count", ""))
                + ",source_ready:"
                + str(competitive_floor_unblock_map_summary.get("source_ready_candidate_count", ""))
                + ",source_blocked:"
                + str(competitive_floor_unblock_map_summary.get("source_blocked_candidate_count", ""))
                + ",source_total:"
                + str(competitive_floor_unblock_map_summary.get("source_candidate_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_identity_source_repair_plan",
            "Repair phases for blocked local identity candidate sources",
            _text(competitive_identity_source_repair_summary.get("source_repair_status")),
            args.competitive_identity_source_repair_json,
            ready_count=_int(competitive_identity_source_repair_summary.get("source_ready_candidate_count")),
            blocked_count=_int(competitive_identity_source_repair_summary.get("repair_action_count")),
            total_count=_int(competitive_identity_source_repair_summary.get("source_candidate_count")),
            next_action=_text(competitive_identity_source_repair_summary.get("first_open_next_action")),
            blockers=(
                "identity:"
                + str(competitive_identity_source_repair_summary.get("target_identity_action_count", ""))
                + ",core:"
                + str(competitive_identity_source_repair_summary.get("core_file_action_count", ""))
                + ",provenance:"
                + str(competitive_identity_source_repair_summary.get("provenance_action_count", ""))
                + ",ablation:"
                + str(competitive_identity_source_repair_summary.get("ablation_action_count", ""))
                + ",calibration:"
                + str(competitive_identity_source_repair_summary.get("calibration_action_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_discovery",
            "Local validation-derived target identity discovery",
            _text(competitive_target_identity_discovery_summary.get("target_identity_discovery_status")),
            args.competitive_target_identity_discovery_json,
            ready_count=_int(competitive_target_identity_discovery_summary.get("ready_for_identity_intake_count")),
            blocked_count=max(
                0,
                _int(competitive_target_identity_discovery_summary.get("discovered_target_count"))
                - _int(competitive_target_identity_discovery_summary.get("ready_for_identity_intake_count")),
            ),
            total_count=_int(competitive_target_identity_discovery_summary.get("discovered_target_count")),
            next_action=_text(competitive_target_identity_discovery_summary.get("first_open_next_action")),
            blockers=(
                "operator_review:"
                + str(competitive_target_identity_discovery_summary.get("operator_review_target_count", ""))
                + ",current:"
                + str(competitive_target_identity_discovery_summary.get("open_current_target_count", ""))
                + ",closed:"
                + str(competitive_target_identity_discovery_summary.get("closed_watchlist_target_count", ""))
                + ",unknown:"
                + str(competitive_target_identity_discovery_summary.get("unknown_local_target_count", ""))
                + ",synthetic:"
                + str(competitive_target_identity_discovery_summary.get("synthetic_test_artifact_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_queue",
            "No-leak/native/provenance clearance queue for discovered target identities",
            _text(competitive_target_identity_clearance_summary.get("clearance_queue_status")),
            args.competitive_target_identity_clearance_queue_json,
            ready_count=_int(competitive_target_identity_clearance_summary.get("ready_for_manifest_scaffold_count")),
            blocked_count=max(
                0,
                _int(competitive_target_identity_clearance_summary.get("review_target_count"))
                - _int(competitive_target_identity_clearance_summary.get("ready_for_manifest_scaffold_count")),
            ),
            total_count=_int(competitive_target_identity_clearance_summary.get("review_target_count")),
            next_action=_text(competitive_target_identity_clearance_summary.get("first_open_next_action")),
            blockers=(
                "prediction:"
                + str(competitive_target_identity_clearance_summary.get("prediction_present_count", ""))
                + ",ts:"
                + str(competitive_target_identity_clearance_summary.get("ts_prediction_present_count", ""))
                + ",native:"
                + str(competitive_target_identity_clearance_summary.get("native_present_count", ""))
                + ",provenance:"
                + str(competitive_target_identity_clearance_summary.get("provenance_cleared_count", ""))
                + ",await_native:"
                + str(competitive_target_identity_clearance_summary.get("awaiting_native_or_clearance_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_workorder",
            "Per-target native dropzones and no-leak provenance workorders",
            _text(competitive_target_identity_clearance_workorder_summary.get("clearance_workorder_status")),
            args.competitive_target_identity_clearance_workorder_json,
            ready_count=_int(competitive_target_identity_clearance_workorder_summary.get("ready_for_manifest_stub_count")),
            blocked_count=max(
                0,
                _int(competitive_target_identity_clearance_workorder_summary.get("workorder_count"))
                - _int(competitive_target_identity_clearance_workorder_summary.get("ready_for_manifest_stub_count")),
            ),
            total_count=_int(competitive_target_identity_clearance_workorder_summary.get("workorder_count")),
            next_action=_text(competitive_target_identity_clearance_workorder_summary.get("first_open_next_action")),
            blockers=(
                "native_provenance:"
                + str(
                    competitive_target_identity_clearance_workorder_summary.get(
                        "native_and_provenance_required_count", ""
                    )
                )
                + ",native:"
                + str(competitive_target_identity_clearance_workorder_summary.get("native_required_count", ""))
                + ",provenance:"
                + str(competitive_target_identity_clearance_workorder_summary.get("provenance_required_count", ""))
                + ",dropzones:"
                + str(competitive_target_identity_clearance_workorder_summary.get("native_dropzone_count", ""))
                + ",templates_preserved:"
                + str(
                    competitive_target_identity_clearance_workorder_summary.get(
                        "provenance_template_preserved_count", ""
                    )
                )
                + ",stubs_preserved:"
                + str(competitive_target_identity_clearance_workorder_summary.get("manifest_stub_preserved_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_operator_intake",
            "Fail-closed operator intake bridge for native PDB and provenance evidence",
            _text(competitive_target_identity_clearance_operator_intake_summary.get("operator_intake_status")),
            args.competitive_target_identity_clearance_operator_intake_json,
            ready_count=_int(competitive_target_identity_clearance_operator_intake_summary.get("ready_to_apply_count"))
            + _int(competitive_target_identity_clearance_operator_intake_summary.get("applied_count")),
            blocked_count=_int(
                competitive_target_identity_clearance_operator_intake_summary.get("awaiting_input_count")
            )
            + _int(competitive_target_identity_clearance_operator_intake_summary.get("blocked_count")),
            total_count=_int(competitive_target_identity_clearance_operator_intake_summary.get("row_count")),
            next_action=_text(
                competitive_target_identity_clearance_operator_intake_summary.get("first_open_next_action")
            ),
            blockers=(
                "ready:"
                + str(competitive_target_identity_clearance_operator_intake_summary.get("ready_to_apply_count", ""))
                + ",awaiting:"
                + str(competitive_target_identity_clearance_operator_intake_summary.get("awaiting_input_count", ""))
                + ",blocked:"
                + str(competitive_target_identity_clearance_operator_intake_summary.get("blocked_count", ""))
                + ",applied:"
                + str(competitive_target_identity_clearance_operator_intake_summary.get("applied_count", ""))
                + ",native_copied:"
                + str(competitive_target_identity_clearance_operator_intake_summary.get("native_copied_count", ""))
                + ",provenance_patched:"
                + str(
                    competitive_target_identity_clearance_operator_intake_summary.get(
                        "provenance_patched_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_native_candidates",
            "RCSB native candidate search and current-target collision guard",
            _text(
                competitive_target_identity_clearance_native_candidate_summary.get(
                    "native_candidate_packet_status"
                )
            ),
            args.competitive_target_identity_clearance_native_candidate_json,
            ready_count=_int(
                competitive_target_identity_clearance_native_candidate_summary.get(
                    "operator_review_required_count"
                )
            )
            + _int(competitive_target_identity_clearance_native_candidate_summary.get("relaxed_review_count")),
            blocked_count=_int(
                competitive_target_identity_clearance_native_candidate_summary.get("blocked_candidate_count")
            )
            + _int(
                competitive_target_identity_clearance_native_candidate_summary.get("no_candidate_target_count")
            )
            + _int(competitive_target_identity_clearance_native_candidate_summary.get("search_prepared_count")),
            total_count=_int(competitive_target_identity_clearance_native_candidate_summary.get("candidate_row_count")),
            next_action=_text(
                competitive_target_identity_clearance_native_candidate_summary.get("first_open_next_action")
            ),
            blockers=(
                "operator_review:"
                + str(
                    competitive_target_identity_clearance_native_candidate_summary.get(
                        "operator_review_required_count", ""
                    )
                )
                + ",relaxed_review:"
                + str(competitive_target_identity_clearance_native_candidate_summary.get("relaxed_review_count", ""))
                + ",blocked:"
                + str(
                    competitive_target_identity_clearance_native_candidate_summary.get(
                        "blocked_candidate_count", ""
                    )
                )
                + ",collisions:"
                + str(
                    competitive_target_identity_clearance_native_candidate_summary.get(
                        "current_target_collision_count", ""
                    )
                )
                + ",no_candidate:"
                + str(
                    competitive_target_identity_clearance_native_candidate_summary.get(
                        "no_candidate_target_count", ""
                    )
                )
                + ",prepared:"
                + str(competitive_target_identity_clearance_native_candidate_summary.get("search_prepared_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_adjudication",
            "Target-level native/no-leak risk adjudication for clearance",
            _text(
                competitive_target_identity_clearance_adjudication_summary.get(
                    "adjudication_packet_status"
                )
            ),
            args.competitive_target_identity_clearance_adjudication_json,
            ready_count=_int(
                competitive_target_identity_clearance_adjudication_summary.get(
                    "safe_to_apply_operator_intake_count"
                )
            ),
            blocked_count=max(
                0,
                _int(competitive_target_identity_clearance_adjudication_summary.get("target_count"))
                - _int(
                    competitive_target_identity_clearance_adjudication_summary.get(
                        "safe_to_apply_operator_intake_count"
                    )
                )
                - _int(
                    competitive_target_identity_clearance_adjudication_summary.get(
                        "operator_intake_applied_count"
                    )
                ),
            ),
            total_count=_int(competitive_target_identity_clearance_adjudication_summary.get("target_count")),
            next_action=_text(
                competitive_target_identity_clearance_adjudication_summary.get("first_open_next_action")
            ),
            blockers=(
                "replacement:"
                + str(
                    competitive_target_identity_clearance_adjudication_summary.get(
                        "replacement_required_count", ""
                    )
                )
                + ",manual:"
                + str(
                    competitive_target_identity_clearance_adjudication_summary.get(
                        "manual_native_search_required_count", ""
                    )
                )
                + ",operator_review:"
                + str(
                    competitive_target_identity_clearance_adjudication_summary.get(
                        "operator_review_required_count", ""
                    )
                )
                + ",safe_apply:"
                + str(
                    competitive_target_identity_clearance_adjudication_summary.get(
                        "safe_to_apply_operator_intake_count", ""
                    )
                )
                + ",md:"
                + str(competitive_target_identity_clearance_adjudication_summary.get("adjudication_md_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_queue",
            "Replacement target queue for collision-blocked clearance rows",
            _text(
                competitive_target_identity_clearance_replacement_queue_summary.get(
                    "replacement_queue_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_queue_json,
            ready_count=_int(
                competitive_target_identity_clearance_replacement_queue_summary.get("ready_candidate_count")
            ),
            blocked_count=max(
                0,
                _int(competitive_target_identity_clearance_replacement_queue_summary.get("candidate_row_count"))
                - _int(competitive_target_identity_clearance_replacement_queue_summary.get("ready_candidate_count")),
            ),
            total_count=_int(competitive_target_identity_clearance_replacement_queue_summary.get("candidate_row_count")),
            next_action=_text(
                competitive_target_identity_clearance_replacement_queue_summary.get("first_open_next_action")
            ),
            blockers=(
                "replacement_targets:"
                + str(
                    competitive_target_identity_clearance_replacement_queue_summary.get(
                        "replacement_required_target_count", ""
                    )
                )
                + ",ready:"
                + str(competitive_target_identity_clearance_replacement_queue_summary.get("ready_candidate_count", ""))
                + ",missing_prediction:"
                + str(
                    competitive_target_identity_clearance_replacement_queue_summary.get(
                        "blocked_missing_prediction_count", ""
                    )
                )
                + ",current_collision:"
                + str(
                    competitive_target_identity_clearance_replacement_queue_summary.get(
                        "blocked_current_collision_count", ""
                    )
                )
                + ",source_repair:"
                + str(
                    competitive_target_identity_clearance_replacement_queue_summary.get(
                        "operator_source_repair_required_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_source_repair",
            "Source repair packet for replacement candidates before clearance review",
            _text(
                competitive_target_identity_clearance_replacement_source_repair_summary.get(
                    "replacement_source_repair_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_source_repair_json,
            ready_count=competitive_target_identity_clearance_replacement_source_repair_ready_count,
            blocked_count=max(
                0,
                _int(competitive_target_identity_clearance_replacement_source_repair_summary.get("candidate_count"))
                - competitive_target_identity_clearance_replacement_source_repair_ready_count,
            ),
            total_count=_int(
                competitive_target_identity_clearance_replacement_source_repair_summary.get("candidate_count")
            ),
            next_action=_text(
                competitive_target_identity_clearance_replacement_source_repair_summary.get(
                    "first_open_next_action"
                )
            ),
            blockers=(
                "source_ready:"
                + str(
                    competitive_target_identity_clearance_replacement_source_repair_summary.get(
                        "source_ready_count", ""
                    )
                )
                + ",ready_prediction:"
                + str(
                    competitive_target_identity_clearance_replacement_source_repair_summary.get(
                        "ready_for_prediction_count", ""
                    )
                )
                + ",ready_validation:"
                + str(
                    competitive_target_identity_clearance_replacement_source_repair_summary.get(
                        "ready_for_validation_scorecard_count", ""
                    )
                )
                + ",awaiting_sequence:"
                + str(
                    competitive_target_identity_clearance_replacement_source_repair_summary.get(
                        "awaiting_sequence_count", ""
                    )
                )
                + ",cancelled:"
                + str(
                    competitive_target_identity_clearance_replacement_source_repair_summary.get(
                        "blocked_cancelled_count", ""
                    )
                )
                + ",current_collision:"
                + str(
                    competitive_target_identity_clearance_replacement_source_repair_summary.get(
                        "blocked_current_collision_count", ""
                    )
                )
                + ",md:"
                + str(
                    competitive_target_identity_clearance_replacement_source_repair_summary.get(
                        "source_repair_md_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_scorecard",
            "Replacement source scorecards for clearance candidate evidence completeness",
            _text(
                competitive_target_identity_clearance_replacement_scorecard_summary.get(
                    "replacement_scorecard_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_scorecard_json,
            ready_count=_int(competitive_target_identity_clearance_replacement_scorecard_summary.get("pass_count")),
            blocked_count=_int(
                competitive_target_identity_clearance_replacement_scorecard_summary.get("blocked_count")
            ),
            total_count=_int(competitive_target_identity_clearance_replacement_scorecard_summary.get("candidate_count")),
            next_action=_text(
                competitive_target_identity_clearance_replacement_scorecard_summary.get("first_open_next_action")
            ),
            blockers=(
                "pass:"
                + str(competitive_target_identity_clearance_replacement_scorecard_summary.get("pass_count", ""))
                + ",blocked:"
                + str(competitive_target_identity_clearance_replacement_scorecard_summary.get("blocked_count", ""))
                + ",scorecard_json:"
                + str(
                    competitive_target_identity_clearance_replacement_scorecard_summary.get(
                        "scorecard_json_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_workorder",
            "Selected replacement clearance workorders with duplicate-candidate guard",
            _text(
                competitive_target_identity_clearance_replacement_workorder_summary.get(
                    "replacement_workorder_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_workorder_json,
            ready_count=_int(
                competitive_target_identity_clearance_replacement_workorder_summary.get("selected_workorder_count")
            ),
            blocked_count=(
                _int(
                    competitive_target_identity_clearance_replacement_workorder_summary.get(
                        "duplicate_candidate_blocked_count"
                    )
                )
                + _int(
                    competitive_target_identity_clearance_replacement_workorder_summary.get(
                        "no_ready_candidate_blocked_count"
                    )
                )
            ),
            total_count=_int(
                competitive_target_identity_clearance_replacement_workorder_summary.get("workorder_row_count")
            ),
            next_action=_text(
                competitive_target_identity_clearance_replacement_workorder_summary.get("first_open_next_action")
            ),
            blockers=(
                "selected:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_summary.get(
                        "selected_workorder_count", ""
                    )
                )
                + ",duplicate:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_summary.get(
                        "duplicate_candidate_blocked_count", ""
                    )
                )
                + ",no_ready:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_summary.get(
                        "no_ready_candidate_blocked_count", ""
                    )
                )
                + ",dropzones:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_summary.get(
                        "native_dropzone_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_workorder_audit",
            "Audit for replacement workorder native/provenance readiness",
            _text(
                competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                    "clearance_workorder_audit_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_workorder_audit_json,
            ready_count=_int(
                competitive_target_identity_clearance_replacement_workorder_audit_summary.get("audit_pass_count")
            ),
            blocked_count=_int(
                competitive_target_identity_clearance_replacement_workorder_audit_summary.get("audit_blocked_count")
            ),
            total_count=_int(
                competitive_target_identity_clearance_replacement_workorder_audit_summary.get("audit_target_count")
            ),
            next_action=_text(
                competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                    "first_blocked_next_action"
                )
            ),
            blockers=(
                "prediction:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                        "prediction_present_count", ""
                    )
                )
                + ",native:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                        "native_valid_count", ""
                    )
                )
                + ",provenance:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                        "provenance_ready_count", ""
                    )
                )
                + ",manifest:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                        "manifest_stub_ready_count", ""
                    )
                )
                + ",native_prediction_distinct:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                        "native_prediction_distinct_count", ""
                    )
                )
                + ",waiting:"
                + str(
                    competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                        "native_prediction_waiting_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_pickup",
            "Replacement clearance operator pickup packet",
            _text(competitive_target_identity_clearance_replacement_pickup_summary.get("replacement_pickup_status")),
            args.competitive_target_identity_clearance_replacement_pickup_json,
            ready_count=_int(
                competitive_target_identity_clearance_replacement_pickup_summary.get("ready_for_operator_intake_count")
            ),
            blocked_count=(
                _int(competitive_target_identity_clearance_replacement_pickup_summary.get("awaiting_operator_pickup_count"))
                + _int(competitive_target_identity_clearance_replacement_pickup_summary.get("blocked_selection_count"))
            ),
            total_count=_int(competitive_target_identity_clearance_replacement_pickup_summary.get("row_count")),
            next_action=_text(
                competitive_target_identity_clearance_replacement_pickup_summary.get("first_open_next_action")
            )
            or "rerun operator intake for ready replacement candidates",
            blockers=(
                "selected:"
                + str(competitive_target_identity_clearance_replacement_pickup_summary.get("selected_count", ""))
                + ",ready:"
                + str(
                    competitive_target_identity_clearance_replacement_pickup_summary.get(
                        "ready_for_operator_intake_count", ""
                    )
                )
                + ",awaiting:"
                + str(
                    competitive_target_identity_clearance_replacement_pickup_summary.get(
                        "awaiting_operator_pickup_count", ""
                    )
                )
                + ",blocked_selection:"
                + str(competitive_target_identity_clearance_replacement_pickup_summary.get("blocked_selection_count", ""))
                + ",native_missing:"
                + str(competitive_target_identity_clearance_replacement_pickup_summary.get("native_missing_count", ""))
                + ",required_fields:"
                + str(
                    competitive_target_identity_clearance_replacement_pickup_summary.get(
                        "provenance_required_field_count", ""
                    )
                )
                + ",operator_actions:"
                + str(competitive_target_identity_clearance_replacement_pickup_summary.get("operator_action_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_duplicate_resolution",
            "Duplicate-resolution packet for replacement clearance workorders",
            _text(
                competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                    "duplicate_resolution_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_duplicate_resolution_json,
            ready_count=_int(
                competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                    "safe_unique_ready_candidate_count"
                )
            ),
            blocked_count=max(
                0,
                _int(
                    competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                        "candidate_row_count"
                    )
                )
                - _int(
                    competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                        "safe_unique_ready_candidate_count"
                    )
                ),
            ),
            total_count=_int(
                competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                    "candidate_row_count"
                )
            ),
            next_action=_text(
                competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                    "first_open_next_action"
                )
            ),
            blockers=(
                "duplicates:"
                + str(
                    competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                        "blocked_duplicate_count", ""
                    )
                )
                + ",duplicate_ready:"
                + str(
                    competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                        "duplicate_ready_candidate_count", ""
                    )
                )
                + ",cancelled:"
                + str(
                    competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                        "blocked_cancelled_count", ""
                    )
                )
                + ",current_collision:"
                + str(
                    competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                        "blocked_current_collision_count", ""
                    )
                )
                + ",missing_prediction:"
                + str(
                    competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                        "blocked_missing_prediction_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_decision_bundle",
            "Operator decision bundle for replacement duplicate blockers",
            _text(
                competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                    "decision_bundle_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_decision_bundle_json,
            ready_count=_int(
                competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                    "ready_decision_count"
                )
            ),
            blocked_count=_int(
                competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                    "open_decision_count"
                )
            ),
            total_count=_int(
                competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                    "decision_target_count"
                )
            ),
            next_action=_text(
                competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                    "first_open_next_action"
                )
            ),
            blockers=(
                "folders:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                        "decision_folder_count", ""
                    )
                )
                + ",candidate_csv:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                        "candidate_resolution_csv_count", ""
                    )
                )
                + ",new_unique_templates:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                        "new_unique_template_count", ""
                    )
                )
                + ",duplicate_exception_templates:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                        "duplicate_exception_template_count", ""
                    )
                )
                + ",safe_unique:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                        "safe_unique_ready_candidate_count", ""
                    )
                )
                + ",duplicate_ready:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                        "duplicate_ready_candidate_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_replacement_decision_preflight",
            "Fail-closed preflight for filled replacement decision inputs",
            _text(
                competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                    "decision_preflight_status"
                )
            ),
            args.competitive_target_identity_clearance_replacement_decision_preflight_json,
            ready_count=(
                _int(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "ready_new_unique_count"
                    )
                )
                + _int(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "ready_duplicate_exception_count"
                    )
                )
            ),
            blocked_count=(
                _int(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "awaiting_operator_decision_count"
                    )
                )
                + _int(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "conflict_count"
                    )
                )
            ),
            total_count=_int(
                competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                    "decision_row_count"
                )
            ),
            next_action=_text(
                competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                    "first_open_next_action"
                )
            ),
            blockers=(
                "ready_new:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "ready_new_unique_count", ""
                    )
                )
                + ",ready_duplicate:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "ready_duplicate_exception_count", ""
                    )
                )
                + ",awaiting:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "awaiting_operator_decision_count", ""
                    )
                )
                + ",conflict:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "conflict_count", ""
                    )
                )
                + ",new_unique_blockers:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "new_unique_blocker_count", ""
                    )
                )
                + ",duplicate_exception_blockers:"
                + str(
                    competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                        "duplicate_exception_blocker_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_manifest_sync",
            "Fail-closed sync from cleared provenance templates into manifest stubs",
            _text(
                competitive_target_identity_clearance_manifest_sync_summary.get(
                    "clearance_manifest_sync_status"
                )
            ),
            args.competitive_target_identity_clearance_manifest_sync_json,
            ready_count=_int(competitive_target_identity_clearance_manifest_sync_summary.get("ready_to_sync_count"))
            + _int(competitive_target_identity_clearance_manifest_sync_summary.get("synced_count")),
            blocked_count=_int(competitive_target_identity_clearance_manifest_sync_summary.get("blocked_count"))
            + _int(competitive_target_identity_clearance_manifest_sync_summary.get("awaiting_provenance_count")),
            total_count=_int(competitive_target_identity_clearance_manifest_sync_summary.get("sync_row_count")),
            next_action=_text(competitive_target_identity_clearance_manifest_sync_summary.get("first_open_next_action")),
            blockers=(
                "ready:"
                + str(competitive_target_identity_clearance_manifest_sync_summary.get("ready_to_sync_count", ""))
                + ",awaiting_provenance:"
                + str(competitive_target_identity_clearance_manifest_sync_summary.get("awaiting_provenance_count", ""))
                + ",synced:"
                + str(competitive_target_identity_clearance_manifest_sync_summary.get("synced_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_workorder_audit",
            "Audit for per-target clearance workorder native/provenance readiness",
            _text(competitive_target_identity_clearance_workorder_audit_summary.get("clearance_workorder_audit_status")),
            args.competitive_target_identity_clearance_workorder_audit_json,
            ready_count=_int(competitive_target_identity_clearance_workorder_audit_summary.get("audit_pass_count")),
            blocked_count=_int(competitive_target_identity_clearance_workorder_audit_summary.get("audit_blocked_count")),
            total_count=_int(competitive_target_identity_clearance_workorder_audit_summary.get("audit_target_count")),
            next_action=_text(competitive_target_identity_clearance_workorder_audit_summary.get("first_blocked_next_action")),
            blockers=(
                "prediction:"
                + str(competitive_target_identity_clearance_workorder_audit_summary.get("prediction_present_count", ""))
                + ",prediction_protein_atoms:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "prediction_protein_atom_count", ""
                    )
                )
                + ",prediction_coordinate_valid:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "prediction_coordinate_valid_count", ""
                    )
                )
                + ",identity_discovery_blocked:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "identity_discovery_blocked_count", ""
                    )
                )
                + ",identity_discovery_cleared:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "identity_discovery_cleared_count", ""
                    )
                )
                + ",native:"
                + str(competitive_target_identity_clearance_workorder_audit_summary.get("native_valid_count", ""))
                + ",native_protein_atoms:"
                + str(competitive_target_identity_clearance_workorder_audit_summary.get("native_protein_atom_count", ""))
                + ",native_coordinate_valid:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "native_coordinate_valid_count", ""
                    )
                )
                + ",provenance:"
                + str(competitive_target_identity_clearance_workorder_audit_summary.get("provenance_ready_count", ""))
                + ",evidence_ref:"
                + str(competitive_target_identity_clearance_workorder_audit_summary.get("evidence_ref_present_count", ""))
                + ",evidence_ref_verified:"
                + str(competitive_target_identity_clearance_workorder_audit_summary.get("evidence_ref_verified_count", ""))
                + ",manifest:"
                + str(competitive_target_identity_clearance_workorder_audit_summary.get("manifest_stub_ready_count", ""))
                + ",manifest_provenance_matched:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "manifest_provenance_matched_count", ""
                    )
                )
                + ",manifest_provenance_mismatches:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "manifest_provenance_mismatch_count", ""
                    )
                )
                + ",native_prediction_distinct:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "native_prediction_distinct_count", ""
                    )
                )
                + ",native_prediction_same:"
                + str(
                    competitive_target_identity_clearance_workorder_audit_summary.get(
                        "native_prediction_same_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_action_board",
            "Operator action board for clearing target identity native/provenance blockers",
            _text(competitive_target_identity_clearance_action_board_summary.get("action_board_status")),
            args.competitive_target_identity_clearance_action_board_json,
            ready_count=max(
                0,
                _int(competitive_target_identity_clearance_action_board_summary.get("action_count"))
                - _int(competitive_target_identity_clearance_action_board_summary.get("open_action_count")),
            ),
            blocked_count=_int(competitive_target_identity_clearance_action_board_summary.get("open_action_count")),
            total_count=_int(competitive_target_identity_clearance_action_board_summary.get("action_count")),
            next_action=_text(competitive_target_identity_clearance_action_board_summary.get("first_open_next_action")),
            blockers=(
                "native:"
                + str(competitive_target_identity_clearance_action_board_summary.get("native_action_count", ""))
                + ",evidence:"
                + str(competitive_target_identity_clearance_action_board_summary.get("evidence_action_count", ""))
                + ",provenance:"
                + str(competitive_target_identity_clearance_action_board_summary.get("provenance_action_count", ""))
                + ",manifest:"
                + str(competitive_target_identity_clearance_action_board_summary.get("manifest_action_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_action_bundle",
            "Per-target request folders for target identity clearance actions",
            _text(competitive_target_identity_clearance_action_bundle_summary.get("action_bundle_status")),
            args.competitive_target_identity_clearance_action_bundle_json,
            ready_count=max(
                0,
                _int(competitive_target_identity_clearance_action_bundle_summary.get("action_count"))
                - _int(competitive_target_identity_clearance_action_bundle_summary.get("open_action_count")),
            ),
            blocked_count=_int(competitive_target_identity_clearance_action_bundle_summary.get("open_action_count")),
            total_count=_int(competitive_target_identity_clearance_action_bundle_summary.get("action_count")),
            next_action=_text(competitive_target_identity_clearance_action_bundle_summary.get("first_open_action_md")),
            blockers=(
                "targets:"
                + str(competitive_target_identity_clearance_action_bundle_summary.get("target_count", ""))
                + ",folders:"
                + str(competitive_target_identity_clearance_action_bundle_summary.get("action_folder_count", ""))
                + ",files:"
                + str(competitive_target_identity_clearance_action_bundle_summary.get("bundle_file_count", ""))
                + ",native:"
                + str(competitive_target_identity_clearance_action_bundle_summary.get("native_action_count", ""))
                + ",evidence:"
                + str(competitive_target_identity_clearance_action_bundle_summary.get("evidence_action_count", ""))
                + ",provenance:"
                + str(competitive_target_identity_clearance_action_bundle_summary.get("provenance_action_count", ""))
                + ",manifest:"
                + str(competitive_target_identity_clearance_action_bundle_summary.get("manifest_action_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_promotion_plan",
            "Fail-closed promotion plan for audited target identity manifest stubs",
            _text(competitive_target_identity_clearance_promotion_summary.get("clearance_promotion_status")),
            args.competitive_target_identity_clearance_promotion_plan_json,
            ready_count=_int(
                competitive_target_identity_clearance_promotion_summary.get(
                    "ready_for_operator_manifest_import_count"
                )
            ),
            blocked_count=_int(competitive_target_identity_clearance_promotion_summary.get("blocked_count")),
            total_count=_int(competitive_target_identity_clearance_promotion_summary.get("promotion_row_count")),
            next_action=_text(
                competitive_target_identity_clearance_promotion_summary.get("first_open_next_action")
            ),
            blockers=(
                "audit_pass:"
                + str(competitive_target_identity_clearance_promotion_summary.get("audit_pass_count", ""))
                + ",promoted:"
                + str(competitive_target_identity_clearance_promotion_summary.get("promoted_manifest_count", ""))
                + ",manifest:"
                + str(competitive_target_identity_clearance_promotion_summary.get("manifest_ready_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_intake_staging",
            "Fail-closed staging plan from cleared target identity manifest rows into identity intake slots",
            _text(
                competitive_target_identity_clearance_intake_staging_summary.get(
                    "clearance_intake_staging_status"
                )
            ),
            args.competitive_target_identity_clearance_intake_staging_json,
            ready_count=_int(
                competitive_target_identity_clearance_intake_staging_summary.get("staged_identity_count")
            ),
            blocked_count=_int(
                competitive_target_identity_clearance_intake_staging_summary.get("blocked_assignment_count")
            ),
            total_count=_int(
                competitive_target_identity_clearance_intake_staging_summary.get("promoted_manifest_row_count")
            ),
            next_action=_text(
                competitive_target_identity_clearance_intake_staging_summary.get("first_open_next_action")
            ),
            blockers=(
                "promoted:"
                + str(competitive_target_identity_clearance_intake_staging_summary.get("promoted_manifest_row_count", ""))
                + ",staged:"
                + str(competitive_target_identity_clearance_intake_staging_summary.get("staged_identity_count", ""))
                + ",open_slots:"
                + str(competitive_target_identity_clearance_intake_staging_summary.get("open_identity_intake_slot_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_candidate_intake_sync",
            "Fail-closed sync from reviewed clearance candidate intake rows into the live intake bundle",
            _text(
                competitive_target_identity_clearance_candidate_intake_sync_summary.get(
                    "candidate_intake_sync_status"
                )
            ),
            args.competitive_target_identity_clearance_candidate_intake_sync_json,
            ready_count=_int(
                competitive_target_identity_clearance_candidate_intake_sync_summary.get("ready_to_apply_count")
            )
            + _int(competitive_target_identity_clearance_candidate_intake_sync_summary.get("applied_row_count")),
            blocked_count=_int(
                competitive_target_identity_clearance_candidate_intake_sync_summary.get("blocked_count")
            )
            + _int(
                competitive_target_identity_clearance_candidate_intake_sync_summary.get(
                    "waiting_on_staged_identity_count"
                )
            ),
            total_count=_int(competitive_target_identity_clearance_candidate_intake_sync_summary.get("sync_row_count")),
            next_action=_text(
                competitive_target_identity_clearance_candidate_intake_sync_summary.get("first_open_next_action")
            ),
            blockers=(
                "ready:"
                + str(competitive_target_identity_clearance_candidate_intake_sync_summary.get("ready_to_apply_count", ""))
                + ",waiting:"
                + str(
                    competitive_target_identity_clearance_candidate_intake_sync_summary.get(
                        "waiting_on_staged_identity_count", ""
                    )
                )
                + ",applied:"
                + str(competitive_target_identity_clearance_candidate_intake_sync_summary.get("applied_row_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_target_identity_clearance_cycle",
            "One-shot downstream clearance cycle from manifest sync through workbench refresh",
            _text(competitive_target_identity_clearance_cycle_summary.get("clearance_cycle_status")),
            args.competitive_target_identity_clearance_cycle_json,
            ready_count=_int(competitive_target_identity_clearance_cycle_summary.get("ready_stage_count")),
            blocked_count=_int(competitive_target_identity_clearance_cycle_summary.get("blocked_stage_count")),
            total_count=_int(competitive_target_identity_clearance_cycle_summary.get("stage_count")),
            next_action=_text(competitive_target_identity_clearance_cycle_summary.get("first_next_action")),
            blockers=(
                "sync:"
                + str(competitive_target_identity_clearance_cycle_summary.get("manifest_sync_status", ""))
                + ",audit:"
                + str(competitive_target_identity_clearance_cycle_summary.get("audit_status", ""))
                + ",promotion:"
                + str(competitive_target_identity_clearance_cycle_summary.get("promotion_status", ""))
                + ",staged:"
                + str(competitive_target_identity_clearance_cycle_summary.get("staged_identity_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_identity_cycle",
            "One-shot identity progression cycle from intake sync to readiness gate and workbench refresh",
            _text(competitive_identity_cycle_summary.get("identity_cycle_status")),
            args.competitive_identity_cycle_json,
            ready_count=_int(competitive_identity_cycle_summary.get("ready_stage_count")),
            blocked_count=_int(competitive_identity_cycle_summary.get("blocked_stage_count")),
            total_count=_int(competitive_identity_cycle_summary.get("stage_count")),
            next_action=_text(competitive_identity_cycle_summary.get("first_next_action")),
            blockers=(
                "sync:"
                + str(competitive_identity_cycle_summary.get("sync_status", ""))
                + ",readiness:"
                + str(competitive_identity_cycle_summary.get("readiness_gate_status", ""))
                + ",missing_fields:"
                + str(competitive_identity_cycle_summary.get("sync_missing_field_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_file_source_plan",
            "Identity-aware source-path plan for prediction, native, and ablation PDB imports",
            _text(competitive_file_source_plan_summary.get("file_source_status")),
            args.competitive_file_source_plan_json,
            ready_count=(
                _int(competitive_file_source_plan_summary.get("ready_for_import_count"))
                + _int(competitive_file_source_plan_summary.get("already_imported_count"))
            ),
            blocked_count=(
                _int(competitive_file_source_plan_summary.get("waiting_on_identity_count"))
                + _int(competitive_file_source_plan_summary.get("identity_blocked_file_count"))
                + _int(competitive_file_source_plan_summary.get("awaiting_source_path_count"))
                + _int(competitive_file_source_plan_summary.get("blocked_file_source_count"))
            ),
            total_count=_int(competitive_file_source_plan_summary.get("file_action_count")),
            next_action=_text(competitive_file_source_plan_summary.get("first_open_next_action")),
            blockers=_text(competitive_file_source_plan_summary.get("first_open_blocker")),
        ),
        _artifact_row(
            "competitive_floor_value_entry_plan",
            "Identity-aware target/provenance/calibration value entry plan",
            _text(competitive_value_entry_plan_summary.get("value_entry_status")),
            args.competitive_value_entry_plan_json,
            ready_count=(
                _int(competitive_value_entry_plan_summary.get("ready_from_identity_kit_count"))
                + _int(competitive_value_entry_plan_summary.get("ready_for_import_count"))
            ),
            blocked_count=(
                _int(competitive_value_entry_plan_summary.get("waiting_on_identity_count"))
                + _int(competitive_value_entry_plan_summary.get("awaiting_value_count"))
                + _int(competitive_value_entry_plan_summary.get("awaiting_clearance_count"))
                + _int(competitive_value_entry_plan_summary.get("awaiting_evidence_ref_count"))
                + _int(competitive_value_entry_plan_summary.get("blocked_value_count"))
            ),
            total_count=_int(competitive_value_entry_plan_summary.get("value_action_count")),
            next_action=_text(competitive_value_entry_plan_summary.get("first_open_next_action")),
            blockers=_text(competitive_value_entry_plan_summary.get("first_open_blocker")),
        ),
        _artifact_row(
            "competitive_floor_execution_board",
            "Row-level competitive-floor execution board",
            _text(competitive_execution_board_summary.get("execution_board_status")),
            args.competitive_execution_board_json,
            ready_count=_int(competitive_execution_board_summary.get("total_ready_action_count")),
            blocked_count=_int(competitive_execution_board_summary.get("total_blocked_action_count")),
            total_count=_int(competitive_execution_board_summary.get("row_count")),
            next_action=_text(competitive_execution_board_summary.get("first_open_next_action")),
            blockers=_text(competitive_execution_board_summary.get("first_open_status")),
        ),
        _artifact_row(
            "competitive_floor_readiness_gate",
            "Gate for competitive-floor promotion from row-level execution evidence",
            _text(competitive_readiness_gate_summary.get("readiness_gate_status")),
            args.competitive_readiness_gate_json,
            ready_count=_int(competitive_readiness_gate_summary.get("pass_count")),
            blocked_count=_int(competitive_readiness_gate_summary.get("blocked_gate_count")),
            total_count=_int(competitive_readiness_gate_summary.get("gate_count")),
            next_action=_text(competitive_readiness_gate_summary.get("first_blocked_next_action")),
            blockers=_text(competitive_readiness_gate_summary.get("first_blocked_gate_id")),
        ),
        _artifact_row(
            "competitive_floor_value_ledger",
            "Per-row value ledgers for target identity, provenance, and calibration fields",
            _text(competitive_value_ledger_summary.get("value_ledger_status")),
            args.competitive_value_ledger_json,
            ready_count=_int(competitive_value_ledger_summary.get("ready_for_intake_count")),
            blocked_count=(
                _int(competitive_value_ledger_summary.get("awaiting_value_count"))
                + _int(competitive_value_ledger_summary.get("awaiting_clearance_count"))
                + _int(competitive_value_ledger_summary.get("awaiting_evidence_ref_count"))
                + _int(competitive_value_ledger_summary.get("blocked_count"))
            ),
            total_count=_int(competitive_value_ledger_summary.get("action_count")),
            next_action=_text(competitive_value_ledger_summary.get("first_open_next_action")),
            blockers=_text(competitive_value_ledger_summary.get("first_open_status")),
        ),
        _artifact_row(
            "competitive_floor_evidence_intake",
            "Dropzone intake audit and row_fill patch candidates",
            _text(competitive_evidence_intake_summary.get("intake_status")),
            args.competitive_evidence_intake_json,
            ready_count=(
                _int(competitive_evidence_intake_summary.get("patch_candidate_count"))
                + _int(competitive_evidence_intake_summary.get("row_fill_file_present_count"))
                + _int(competitive_evidence_intake_summary.get("field_present_count"))
            ),
            blocked_count=(
                _int(competitive_evidence_intake_summary.get("awaiting_dropzone_file_count"))
                + _int(competitive_evidence_intake_summary.get("awaiting_operator_value_count"))
                + _int(competitive_evidence_intake_summary.get("ambiguous_file_candidate_count"))
                + _int(competitive_evidence_intake_summary.get("row_fill_blocked_count"))
            ),
            total_count=_int(competitive_evidence_intake_summary.get("action_count")),
            next_action=_text(competitive_evidence_intake_summary.get("first_open_next_action")),
            blockers=_text(competitive_evidence_intake_summary.get("first_open_status")),
        ),
        _artifact_row(
            "competitive_floor_row_fill_patch_gate",
            "Dry-run gate for row_fill patch candidates before operator application",
            _text(competitive_patch_gate_summary.get("patch_gate_status")),
            args.competitive_patch_gate_json,
            ready_count=_int(competitive_patch_gate_summary.get("ready_to_patch_count")),
            blocked_count=(
                _int(competitive_patch_gate_summary.get("awaiting_evidence_count"))
                + _int(competitive_patch_gate_summary.get("conflict_count"))
                + _int(competitive_patch_gate_summary.get("blocked_count"))
            ),
            total_count=_int(competitive_patch_gate_summary.get("action_count")),
            next_action=_text(competitive_patch_gate_summary.get("first_open_next_action")),
            blockers=_text(competitive_patch_gate_summary.get("first_open_status")),
        ),
        _artifact_row(
            "competitive_floor_row_fill_apply_plan",
            "Apply-plan review for ready row_fill patch candidates",
            _text(competitive_apply_plan_summary.get("apply_plan_status")),
            args.competitive_apply_plan_json,
            ready_count=_int(competitive_apply_plan_summary.get("planned_patch_count")),
            blocked_count=(
                _int(competitive_apply_plan_summary.get("awaiting_evidence_count"))
                + _int(competitive_apply_plan_summary.get("blocked_count"))
            ),
            total_count=_int(competitive_apply_plan_summary.get("action_count")),
            next_action=_text(competitive_apply_plan_summary.get("first_open_next_action")),
            blockers=_text(competitive_apply_plan_summary.get("first_open_status")),
        ),
        _artifact_row(
            "competitive_floor_operator_template",
            "Candidate operator CSV assembled from filled competitive-floor batch folders",
            _text(competitive_operator_template_summary.get("template_status")),
            args.competitive_operator_template_json,
            ready_count=_int(competitive_operator_template_summary.get("ready_for_preflight_count")),
            blocked_count=_int(competitive_operator_template_summary.get("blocked_count")),
            total_count=_int(competitive_operator_template_summary.get("row_count")),
            next_action="Fill batch row metadata, required file paths, provenance, and calibration until this candidate is ready_for_preflight.",
            blockers=(
                "missing_files:"
                + str(competitive_operator_template_summary.get("missing_file_count", ""))
                + ",placeholder_paths:"
                + str(competitive_operator_template_summary.get("placeholder_file_path_count", ""))
                + ",provenance_blockers:"
                + str(competitive_operator_template_summary.get("provenance_blocker_count", ""))
                + ",calibration_blockers:"
                + str(competitive_operator_template_summary.get("calibration_blocker_count", ""))
                + ",row_fill_candidates:"
                + str(competitive_operator_template_summary.get("row_fill_candidate_count", ""))
            ),
        ),
        _artifact_row(
            "competitive_floor_operator_preflight",
            "Preflight audit for the competitive-floor operator CSV",
            _text(competitive_operator_preflight_summary.get("operator_preflight_status")),
            args.competitive_operator_preflight_json,
            ready_count=_int(competitive_operator_preflight_summary.get("ready_count")),
            blocked_count=_int(competitive_operator_preflight_summary.get("blocked_count")),
            total_count=_int(competitive_operator_preflight_summary.get("row_count")),
            next_action="Resolve the first blocked competitive-floor operator row, then rerun the preflight.",
            blockers=_text(competitive_operator_preflight_summary.get("first_blocked_blockers")),
        ),
        _artifact_row(
            "data_bundle",
            "CASP17 local data mirror",
            _text(data_bundle_summary.get("bundle_status")),
            args.data_bundle_json,
            ready_count=_int(data_bundle_summary.get("artifact_count")) - _int(data_bundle_summary.get("missing_bundle_count")),
            blocked_count=_int(data_bundle_summary.get("missing_bundle_count")),
            total_count=_int(data_bundle_summary.get("artifact_count")),
            next_action="Refresh after new CASP17 runtime artifacts are generated.",
            blockers="missing_bundle_count:" + str(data_bundle_summary.get("missing_bundle_count", "")),
        ),
    ]

    target_ready = _int(target_summary.get("ready_count"))
    target_count = _int(target_summary.get("target_count"))
    benchmark_rows_ready = _int(inventory_summary.get("ready_row_count"))
    benchmark_rows_total = _int(inventory_summary.get("row_count"))
    workbench_status = "ready_for_operator_fill" if target_count and target_ready == target_count else "blocked"
    if benchmark_rows_total and benchmark_rows_ready == benchmark_rows_total:
        workbench_status = "ready_for_win_tier_scoring"
    summary = {
        "packet_type": "casp17_workbench_index",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "workbench_status": workbench_status,
        "target_model_ready_count": target_ready,
        "target_model_count": target_count,
        "target_model_object_count": _int(target_summary.get("total_object_count")),
        "target_model_object_projection_count": _int(target_summary.get("total_object_projection_files")),
        "target_model_object_viewer_count": _int(target_summary.get("total_object_viewer_files")),
        "target_object_folder_audit_status": _text(
            target_object_folder_audit_summary.get("folder_audit_status")
        ),
        "target_object_folder_audit_pass_count": _int(target_object_folder_audit_summary.get("pass_count")),
        "target_object_folder_audit_total": _int(target_object_folder_audit_summary.get("object_row_count")),
        "target_object_folder_chain_isolation_pass_count": _int(
            target_object_folder_audit_summary.get("chain_isolation_pass_count")
        ),
        "target_object_folder_protein_atom_pass_count": _int(
            target_object_folder_audit_summary.get("protein_atom_pass_count")
        ),
        "target_object_folder_coordinate_valid_pass_count": _int(
            target_object_folder_audit_summary.get("coordinate_valid_pass_count")
        ),
        "target_object_folder_total_protein_atom_count": _int(
            target_object_folder_audit_summary.get("total_protein_atom_count")
        ),
        "target_object_viewer_smoke_status": _text(target_object_viewer_smoke_summary.get("smoke_status")),
        "target_object_viewer_smoke_pass_count": _int(target_object_viewer_smoke_summary.get("pass_count")),
        "target_object_viewer_smoke_total": _int(target_object_viewer_smoke_summary.get("object_row_count")),
        "target_object_model_review_status": _text(
            target_object_model_review_summary.get("object_model_review_status")
        ),
        "target_object_model_review_pass_count": _int(target_object_model_review_summary.get("pass_count")),
        "target_object_model_review_blocked_count": _int(target_object_model_review_summary.get("blocked_count")),
        "target_object_model_review_total": _int(target_object_model_review_summary.get("object_count")),
        "target_object_model_review_md_count": _int(target_object_model_review_summary.get("review_md_count")),
        "target_object_model_review_viewer_local_pass_count": _int(
            target_object_model_review_summary.get("viewer_local_pass_count")
        ),
        "target_object_model_review_protein_atom_count": _int(
            target_object_model_review_summary.get("protein_atom_count")
        ),
        "target_object_model_review_ca_atom_count": _int(target_object_model_review_summary.get("ca_atom_count")),
        "target_object_model_review_residue_count": _int(target_object_model_review_summary.get("residue_count")),
        "target_object_model_review_min_radius": target_object_model_review_summary.get("min_radius_of_gyration", 0),
        "target_object_model_review_max_radius": target_object_model_review_summary.get("max_radius_of_gyration", 0),
        "target_object_model_review_gallery_status": _text(target_object_model_review_summary.get("gallery_status")),
        "target_object_model_review_gallery_html": _text(target_object_model_review_summary.get("gallery_html_path")),
        "protein_object_library_status": _text(
            protein_object_library_summary.get("protein_object_library_status")
        ),
        "protein_object_library_protein_folder_count": _int(
            protein_object_library_summary.get("protein_folder_count")
        ),
        "protein_object_library_object_folder_count": _int(
            protein_object_library_summary.get("object_folder_count")
        ),
        "protein_object_library_pass_count": _int(protein_object_library_summary.get("pass_count")),
        "protein_object_library_blocked_count": _int(protein_object_library_summary.get("blocked_count")),
        "protein_object_library_model_pointer_count": _int(
            protein_object_library_summary.get("model_pointer_count")
        ),
        "protein_object_library_projection_pointer_count": _int(
            protein_object_library_summary.get("projection_pointer_count")
        ),
        "protein_object_library_viewer_pointer_count": _int(
            protein_object_library_summary.get("viewer_pointer_count")
        ),
        "protein_object_library_dir": _text(protein_object_library_summary.get("library_dir")),
        "raw_ranked_model_quarantine_status": _text(
            raw_ranked_model_quarantine_summary.get("raw_ranked_model_quarantine_status")
        ),
        "raw_ranked_model_quarantine_target_count": _int(raw_ranked_model_quarantine_summary.get("target_count")),
        "raw_ranked_model_quarantine_model_count": _int(
            raw_ranked_model_quarantine_summary.get("raw_ranked_model_count")
        ),
        "raw_ranked_model_quarantine_quarantined_count": _int(
            raw_ranked_model_quarantine_summary.get("quarantined_count")
        ),
        "raw_ranked_model_quarantine_linked_count": _int(
            raw_ranked_model_quarantine_summary.get("linked_object_library_count")
        ),
        "raw_ranked_model_quarantine_author_present_count": _int(
            raw_ranked_model_quarantine_summary.get("author_record_present_count")
        ),
        "raw_ranked_model_quarantine_top5_count": _int(
            raw_ranked_model_quarantine_summary.get("complete_top5_target_count")
        ),
        "raw_ranked_model_quarantine_atom_count": _int(
            raw_ranked_model_quarantine_summary.get("total_atom_record_count")
        ),
        "benchmark_rows_ready_count": benchmark_rows_ready,
        "benchmark_rows_total": benchmark_rows_total,
        "win_tier_goal_scorecard_status": _text(goal_scorecard_summary.get("scorecard_status")),
        "win_tier_goal_scorecard_pass_count": _int(goal_scorecard_summary.get("pass_count")),
        "win_tier_goal_scorecard_partial_count": _int(goal_scorecard_summary.get("partial_count")),
        "win_tier_goal_scorecard_blocked_count": _int(goal_scorecard_summary.get("blocked_count")),
        "win_tier_goal_scorecard_row_count": _int(goal_scorecard_summary.get("row_count")),
        "win_tier_goal_scorecard_first_blocked_gate": _text(goal_scorecard_summary.get("first_blocked_gate")),
        "win_gap_closure_status": _text(closure_summary.get("closure_status")),
        "win_gap_closed_count": _int(closure_summary.get("closed_count")),
        "win_gap_not_closed_count": _int(closure_summary.get("not_closed_count")),
        "historical_input_workorder_count": _int(closure_summary.get("historical_input_workorder_count")),
        "historical_core_workorder_count": _int(closure_summary.get("historical_core_workorder_count")),
        "historical_missing_core_file_count": _int(closure_summary.get("historical_missing_core_file_count")),
        "historical_missing_ablation_layer_file_count": _int(
            closure_summary.get("historical_missing_ablation_layer_file_count")
        ),
        "benchmark_operator_ready_count": _int(closure_summary.get("benchmark_operator_ready_count")),
        "benchmark_operator_blocked_count": _int(closure_summary.get("benchmark_operator_blocked_count")),
        "benchmark_missing_win_total_rows": _int(closure_summary.get("benchmark_missing_win_total_rows")),
        "operator_dashboard_status": _text(dashboard_summary.get("dashboard_status")),
        "operator_dashboard_row_count": _int(dashboard_summary.get("row_count")),
        "operator_dashboard_ready_count": _int(dashboard_summary.get("ready_count")),
        "operator_dashboard_blocked_count": _int(dashboard_summary.get("blocked_count")),
        "operator_dashboard_needs_target_replacement_count": _int(
            dashboard_summary.get("needs_target_replacement_count")
        ),
        "operator_dashboard_needs_core_file_count": _int(dashboard_summary.get("needs_core_file_count")),
        "operator_dashboard_needs_ablation_layer_count": _int(
            dashboard_summary.get("needs_ablation_layer_count")
        ),
        "operator_dashboard_needs_calibration_count": _int(
            dashboard_summary.get("needs_calibration_count")
        ),
        "operator_dashboard_needs_provenance_count": _int(
            dashboard_summary.get("needs_provenance_count")
        ),
        "historical_identity_seed_inventory_status": _text(
            historical_identity_seed_inventory_summary.get("seed_inventory_status")
        ),
        "historical_identity_seed_candidate_count": _int(
            historical_identity_seed_inventory_summary.get("seed_candidate_count")
        ),
        "historical_identity_seed_monomer_count": _int(
            historical_identity_seed_inventory_summary.get("monomer_seed_candidate_count")
        ),
        "historical_identity_seed_complex_count": _int(
            historical_identity_seed_inventory_summary.get("complex_seed_candidate_count")
        ),
        "historical_identity_seed_eligible_monomer_count": _int(
            historical_identity_seed_inventory_summary.get("eligible_monomer_seed_count")
        ),
        "historical_identity_seed_eligible_complex_count": _int(
            historical_identity_seed_inventory_summary.get("eligible_complex_seed_count")
        ),
        "historical_identity_seed_batch_slot_count": _int(
            historical_identity_seed_inventory_summary.get("batch_seed_slot_count")
        ),
        "historical_identity_seed_manifest_row_count": _int(
            historical_identity_seed_inventory_summary.get("candidate_manifest_row_count")
        ),
        "historical_identity_seed_operator_clearance_required_count": _int(
            historical_identity_seed_inventory_summary.get("operator_clearance_required_count")
        ),
        "historical_identity_seed_manifest_csv": _text(
            historical_identity_seed_inventory_summary.get("candidate_manifest_csv")
        ),
        "historical_identity_seed_first_target_id": _text(
            historical_identity_seed_inventory_summary.get("first_seed_target_id")
        ),
        "historical_identity_seed_clearance_status": _text(
            historical_identity_seed_clearance_summary.get("seed_clearance_status")
        ),
        "historical_identity_seed_clearance_template_status": _text(
            historical_identity_seed_clearance_summary.get("template_status")
        ),
        "historical_identity_seed_clearance_seed_count": _int(
            historical_identity_seed_clearance_summary.get("seed_row_count")
        ),
        "historical_identity_seed_clearance_ready_count": _int(
            historical_identity_seed_clearance_summary.get("ready_seed_count")
        ),
        "historical_identity_seed_clearance_awaiting_count": _int(
            historical_identity_seed_clearance_summary.get("awaiting_seed_count")
        ),
        "historical_identity_seed_clearance_cleared_manifest_count": _int(
            historical_identity_seed_clearance_summary.get("cleared_manifest_row_count")
        ),
        "historical_identity_seed_clearance_blocking_field_count": _int(
            historical_identity_seed_clearance_summary.get("blocking_field_count")
        ),
        "historical_identity_seed_clearance_identity_open_count": _int(
            historical_identity_seed_clearance_phase_open_counts.get("identity")
        ),
        "historical_identity_seed_clearance_core_files_open_count": _int(
            historical_identity_seed_clearance_phase_open_counts.get("core_files")
        ),
        "historical_identity_seed_clearance_no_leak_open_count": _int(
            historical_identity_seed_clearance_phase_open_counts.get("no_leak_provenance")
        ),
        "historical_identity_seed_clearance_calibration_open_count": _int(
            historical_identity_seed_clearance_phase_open_counts.get("calibration")
        ),
        "historical_identity_seed_clearance_ablation_open_count": _int(
            historical_identity_seed_clearance_phase_open_counts.get("ablation")
        ),
        "historical_identity_seed_clearance_first_target_id": _text(
            historical_identity_seed_clearance_summary.get("first_open_target_id")
        ),
        "historical_identity_seed_clearance_operator_csv": _text(
            historical_identity_seed_clearance_summary.get("operator_clearance_csv")
        ),
        "historical_identity_seed_clearance_cleared_manifest_csv": _text(
            historical_identity_seed_clearance_summary.get("cleared_manifest_csv")
        ),
        "historical_identity_seed_clearance_action_bundle_status": _text(
            historical_identity_seed_clearance_action_bundle_summary.get("seed_clearance_action_bundle_status")
        ),
        "historical_identity_seed_clearance_action_bundle_target_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("target_count")
        ),
        "historical_identity_seed_clearance_action_bundle_action_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("action_count")
        ),
        "historical_identity_seed_clearance_action_bundle_open_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("open_action_count")
        ),
        "historical_identity_seed_clearance_action_bundle_folder_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("action_folder_count")
        ),
        "historical_identity_seed_clearance_action_bundle_file_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("bundle_file_count")
        ),
        "historical_identity_seed_clearance_action_bundle_identity_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("identity_action_count")
        ),
        "historical_identity_seed_clearance_action_bundle_core_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("core_file_action_count")
        ),
        "historical_identity_seed_clearance_action_bundle_no_leak_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("no_leak_action_count")
        ),
        "historical_identity_seed_clearance_action_bundle_calibration_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("calibration_action_count")
        ),
        "historical_identity_seed_clearance_action_bundle_ablation_count": _int(
            historical_identity_seed_clearance_action_bundle_summary.get("ablation_action_count")
        ),
        "historical_identity_seed_clearance_action_bundle_first_action": _text(
            historical_identity_seed_clearance_action_bundle_summary.get("first_open_action_md")
        ),
        "sidechain_native_benchmark_status": _text(
            sidechain_native_benchmark_summary.get("sidechain_native_benchmark_status")
        ),
        "sidechain_native_benchmark_count": _int(sidechain_native_benchmark_summary.get("benchmark_count")),
        "sidechain_native_pass_count": _int(sidechain_native_benchmark_summary.get("pass_count")),
        "sidechain_native_blocked_count": _int(sidechain_native_benchmark_summary.get("blocked_count")),
        "sidechain_native_core_input_blocked_count": _int(
            sidechain_native_benchmark_summary.get("core_input_blocked_count")
        ),
        "sidechain_native_leakage_blocked_count": _int(
            sidechain_native_benchmark_summary.get("leakage_clearance_blocked_count")
        ),
        "sidechain_native_prediction_missing_count": _int(
            sidechain_native_benchmark_summary.get("prediction_pdb_missing_count")
        ),
        "sidechain_native_native_missing_count": _int(
            sidechain_native_benchmark_summary.get("native_pdb_missing_count")
        ),
        "sidechain_native_missing_core_file_count": _int(
            sidechain_native_benchmark_summary.get("missing_core_file_count")
        ),
        "sidechain_native_exactness_blocked_count": _int(
            sidechain_native_benchmark_summary.get("exactness_blocked_count")
        ),
        "sidechain_native_metric_blocked_count": _int(
            sidechain_native_benchmark_summary.get("metric_threshold_blocked_count")
        ),
        "sidechain_native_first_blocked_benchmark_id": _text(
            sidechain_native_benchmark_summary.get("first_blocked_benchmark_id")
        ),
        "sidechain_native_first_blocked_blockers": _text(
            sidechain_native_benchmark_summary.get("first_blocked_blockers")
            or sidechain_native_benchmark_summary.get("manifest_blockers")
        ),
        "sidechain_native_first_next_action": _text(
            sidechain_native_benchmark_summary.get("first_open_next_action")
        ),
        "sidechain_native_workorder_action_count": _int(
            sidechain_native_benchmark_summary.get("workorder_action_count")
        ),
        "sidechain_native_open_workorder_action_count": _int(
            sidechain_native_benchmark_summary.get("open_workorder_action_count")
        ),
        "sidechain_native_workorder_json": _text(sidechain_native_benchmark_summary.get("workorder_json")),
        "sidechain_native_workorder_md": _text(sidechain_native_benchmark_summary.get("workorder_md")),
        "competitive_batch_status": _text(competitive_batch_summary.get("batch_status")),
        "competitive_batch_row_count": _int(competitive_batch_summary.get("row_count")),
        "competitive_batch_missing_evidence_item_count": _int(
            competitive_batch_summary.get("missing_evidence_item_count")
        ),
        "competitive_row_fill_status": _text(competitive_row_fill_status_summary.get("row_fill_status")),
        "competitive_row_fill_filled_count": _int(competitive_row_fill_status_summary.get("row_fill_filled_count")),
        "competitive_row_fill_ready_count": _int(
            competitive_row_fill_status_summary.get("ready_for_operator_template_count")
        ),
        "competitive_row_fill_row_count": _int(competitive_row_fill_status_summary.get("row_count")),
        "competitive_row_fill_worklist_status": _text(
            competitive_row_fill_worklist_summary.get("worklist_status")
        ),
        "competitive_row_fill_worklist_open_action_count": _int(
            competitive_row_fill_worklist_summary.get("open_action_count")
        ),
        "competitive_row_fill_worklist_guide_count": _int(
            competitive_row_fill_worklist_summary.get("guide_md_count")
        ),
        "competitive_evidence_dropzone_status": _text(
            competitive_evidence_dropzone_summary.get("dropzone_status")
        ),
        "competitive_evidence_dropzone_count": _int(
            competitive_evidence_dropzone_summary.get("dropzone_count")
        ),
        "competitive_evidence_dropzone_manifest_count": _int(
            competitive_evidence_dropzone_summary.get("manifest_count")
        ),
        "competitive_evidence_dropzone_open_action_count": _int(
            competitive_evidence_dropzone_summary.get("open_action_count")
        ),
        "competitive_evidence_dropzone_file_action_count": _int(
            competitive_evidence_dropzone_summary.get("file_action_count")
        ),
        "competitive_evidence_import_status": _text(
            competitive_evidence_import_summary.get("import_status")
        ),
        "competitive_evidence_import_action_count": _int(
            competitive_evidence_import_summary.get("action_count")
        ),
        "competitive_evidence_import_ready_for_apply_count": _int(
            competitive_evidence_import_summary.get("ready_for_apply_count")
        ),
        "competitive_evidence_import_applied_count": _int(
            competitive_evidence_import_summary.get("applied_count")
        ),
        "competitive_evidence_import_awaiting_file_count": _int(
            competitive_evidence_import_summary.get("awaiting_import_file_count")
        ),
        "competitive_evidence_import_awaiting_value_count": _int(
            competitive_evidence_import_summary.get("awaiting_import_value_count")
        ),
        "competitive_evidence_import_blocked_count": _int(
            competitive_evidence_import_summary.get("blocked_count")
        ),
        "competitive_evidence_round_status": _text(
            competitive_evidence_round_summary.get("round_status")
        ),
        "competitive_evidence_round_stage_count": _int(
            competitive_evidence_round_summary.get("stage_count")
        ),
        "competitive_evidence_round_import_ready_for_apply_count": _int(
            competitive_evidence_round_summary.get("import_ready_for_apply_count")
        ),
        "competitive_evidence_round_import_applied_count": _int(
            competitive_evidence_round_summary.get("import_applied_count")
        ),
        "competitive_evidence_round_patch_candidate_count": _int(
            competitive_evidence_round_summary.get("intake_patch_candidate_count")
        ),
        "competitive_evidence_round_apply_plan_planned_patch_count": _int(
            competitive_evidence_round_summary.get("apply_plan_planned_patch_count")
        ),
        "competitive_unlock_priority_status": _text(
            competitive_unlock_priority_summary.get("unlock_status")
        ),
        "competitive_unlock_priority_phase_row_count": _int(
            competitive_unlock_priority_summary.get("phase_row_count")
        ),
        "competitive_unlock_priority_identity_open_action_count": _int(
            competitive_unlock_priority_summary.get("identity_open_action_count")
        ),
        "competitive_unlock_priority_target_id_open_count": _int(
            competitive_unlock_priority_summary.get("target_id_open_count")
        ),
        "competitive_unlock_priority_file_waiting_on_identity_count": _int(
            competitive_unlock_priority_summary.get("file_actions_waiting_on_identity_count")
        ),
        "competitive_identity_unlock_status": _text(
            competitive_identity_unlock_summary.get("identity_unlock_status")
        ),
        "competitive_identity_unlock_row_count": _int(
            competitive_identity_unlock_summary.get("row_count")
        ),
        "competitive_identity_unlock_ready_count": _int(
            competitive_identity_unlock_summary.get("ready_for_import_count")
        ),
        "competitive_identity_unlock_awaiting_count": _int(
            competitive_identity_unlock_summary.get("awaiting_identity_count")
        ),
        "competitive_identity_unlock_blocked_count": _int(
            competitive_identity_unlock_summary.get("blocked_identity_count")
        ),
        "competitive_identity_unlock_file_actions_unlocked_count": _int(
            competitive_identity_unlock_summary.get("file_actions_unlocked_count")
        ),
        "competitive_identity_round_status": _text(
            competitive_identity_round_summary.get("identity_round_status")
        ),
        "competitive_identity_round_row_count": _int(
            competitive_identity_round_summary.get("row_count")
        ),
        "competitive_identity_round_ready_for_import_count": _int(
            competitive_identity_round_summary.get("identity_ready_for_import_count")
        ),
        "competitive_identity_round_awaiting_count": _int(
            competitive_identity_round_summary.get("identity_awaiting_count")
        ),
        "competitive_identity_round_blocked_count": _int(
            competitive_identity_round_summary.get("identity_blocked_count")
        ),
        "competitive_identity_round_import_ready_for_apply_count": _int(
            competitive_identity_round_summary.get("import_ready_for_apply_count")
        ),
        "competitive_identity_round_import_applied_count": _int(
            competitive_identity_round_summary.get("import_applied_count")
        ),
        "competitive_identity_round_target_id_open_count": _int(
            competitive_identity_round_summary.get("target_id_open_count")
        ),
        "competitive_identity_round_file_waiting_on_identity_count": _int(
            competitive_identity_round_summary.get("file_actions_waiting_on_identity_count")
        ),
        "competitive_identity_intake_status": _text(
            competitive_identity_intake_summary.get("identity_intake_status")
        ),
        "competitive_identity_intake_row_count": _int(
            competitive_identity_intake_summary.get("row_count")
        ),
        "competitive_identity_intake_ready_count": _int(
            competitive_identity_intake_summary.get("ready_for_identity_apply_count")
        ),
        "competitive_identity_intake_awaiting_count": _int(
            competitive_identity_intake_summary.get("awaiting_identity_count")
        ),
        "competitive_identity_intake_blocked_count": _int(
            competitive_identity_intake_summary.get("blocked_identity_count")
        ),
        "competitive_identity_intake_missing_field_count": _int(
            competitive_identity_intake_summary.get("missing_field_count")
        ),
        "competitive_identity_intake_file_actions_unlocked_count": _int(
            competitive_identity_intake_summary.get("file_actions_unlocked_count")
        ),
        "competitive_identity_sync_status": _text(
            competitive_identity_sync_summary.get("identity_intake_sync_status")
        ),
        "competitive_identity_sync_row_count": _int(
            competitive_identity_sync_summary.get("row_count")
        ),
        "competitive_identity_sync_synced_count": _int(
            competitive_identity_sync_summary.get("synced_count")
        ),
        "competitive_identity_sync_ready_to_sync_count": _int(
            competitive_identity_sync_summary.get("ready_to_sync_count")
        ),
        "competitive_identity_sync_awaiting_count": _int(
            competitive_identity_sync_summary.get("awaiting_intake_count")
        ),
        "competitive_identity_sync_blocked_count": _int(
            competitive_identity_sync_summary.get("blocked_count")
        ),
        "competitive_identity_sync_missing_field_count": _int(
            competitive_identity_sync_summary.get("missing_field_count")
        ),
        "competitive_identity_sync_kit_mismatch_count": _int(
            competitive_identity_sync_summary.get("kit_mismatch_count")
        ),
        "competitive_identity_sync_applied_count": _int(
            competitive_identity_sync_summary.get("applied_sync_count")
        ),
        "competitive_identity_candidate_status": _text(
            competitive_identity_candidate_summary.get("identity_candidate_status")
        ),
        "competitive_identity_candidate_row_count": _int(
            competitive_identity_candidate_summary.get("row_count")
        ),
        "competitive_identity_candidate_ready_count": _int(
            competitive_identity_candidate_summary.get("ready_for_intake_count")
        ),
        "competitive_identity_candidate_awaiting_count": _int(
            competitive_identity_candidate_summary.get("awaiting_candidate_source_count")
        ),
        "competitive_identity_candidate_source_count": _int(
            competitive_identity_candidate_summary.get("source_candidate_count")
        ),
        "competitive_identity_candidate_source_ready_count": _int(
            competitive_identity_candidate_summary.get("source_ready_candidate_count")
        ),
        "competitive_identity_candidate_source_blocked_count": _int(
            competitive_identity_candidate_summary.get("source_blocked_candidate_count")
        ),
        "competitive_identity_candidate_applied_count": _int(
            competitive_identity_candidate_summary.get("applied_intake_count")
        ),
        "competitive_identity_candidate_operator_preflight_status": _text(
            competitive_identity_candidate_summary.get("operator_preflight_status")
        ),
        "competitive_floor_unblock_map_status": _text(
            competitive_floor_unblock_map_summary.get("unblock_map_status")
        ),
        "competitive_floor_unblock_map_row_count": _int(
            competitive_floor_unblock_map_summary.get("row_count")
        ),
        "competitive_floor_unblock_map_ready_count": _int(
            competitive_floor_unblock_map_summary.get("ready_for_intake_count")
        ),
        "competitive_floor_unblock_map_awaiting_count": _int(
            competitive_floor_unblock_map_summary.get("awaiting_candidate_source_count")
        ),
        "competitive_floor_unblock_map_source_count": _int(
            competitive_floor_unblock_map_summary.get("source_candidate_count")
        ),
        "competitive_floor_unblock_map_source_ready_count": _int(
            competitive_floor_unblock_map_summary.get("source_ready_candidate_count")
        ),
        "competitive_floor_unblock_map_source_blocked_count": _int(
            competitive_floor_unblock_map_summary.get("source_blocked_candidate_count")
        ),
        "competitive_floor_unblock_map_blocking_field_count": _int(
            competitive_floor_unblock_map_summary.get("blocking_field_count")
        ),
        "competitive_floor_unblock_map_blocking_phase_count": _int(
            competitive_floor_unblock_map_summary.get("blocking_phase_count")
        ),
        "competitive_floor_unblock_map_target_identity_open_count": _int(
            competitive_floor_unblock_map_phase_open_counts.get("target_identity")
        ),
        "competitive_floor_unblock_map_core_files_open_count": _int(
            competitive_floor_unblock_map_phase_open_counts.get("core_files")
        ),
        "competitive_floor_unblock_map_no_leak_provenance_open_count": _int(
            competitive_floor_unblock_map_phase_open_counts.get("no_leak_provenance")
        ),
        "competitive_floor_unblock_map_ablation_files_open_count": _int(
            competitive_floor_unblock_map_phase_open_counts.get("ablation_files")
        ),
        "competitive_floor_unblock_map_calibration_values_open_count": _int(
            competitive_floor_unblock_map_phase_open_counts.get("calibration_values")
        ),
        "competitive_floor_unblock_map_first_open_dropzone_id": _text(
            competitive_floor_unblock_map_summary.get("first_open_dropzone_id")
        ),
        "competitive_floor_unblock_map_first_open_phase": _text(
            competitive_floor_unblock_map_summary.get("first_open_phase")
        ),
        "competitive_identity_source_repair_status": _text(
            competitive_identity_source_repair_summary.get("source_repair_status")
        ),
        "competitive_identity_source_repair_action_count": _int(
            competitive_identity_source_repair_summary.get("repair_action_count")
        ),
        "competitive_identity_source_repair_blocked_source_count": _int(
            competitive_identity_source_repair_summary.get("blocked_source_row_count")
        ),
        "competitive_identity_source_repair_target_identity_count": _int(
            competitive_identity_source_repair_summary.get("target_identity_action_count")
        ),
        "competitive_identity_source_repair_core_file_count": _int(
            competitive_identity_source_repair_summary.get("core_file_action_count")
        ),
        "competitive_identity_source_repair_provenance_count": _int(
            competitive_identity_source_repair_summary.get("provenance_action_count")
        ),
        "competitive_identity_source_repair_ablation_count": _int(
            competitive_identity_source_repair_summary.get("ablation_action_count")
        ),
        "competitive_identity_source_repair_calibration_count": _int(
            competitive_identity_source_repair_summary.get("calibration_action_count")
        ),
        "competitive_identity_source_repair_first_phase": _text(
            competitive_identity_source_repair_summary.get("first_open_phase")
        ),
        "competitive_target_identity_discovery_status": _text(
            competitive_target_identity_discovery_summary.get("target_identity_discovery_status")
        ),
        "competitive_target_identity_discovery_count": _int(
            competitive_target_identity_discovery_summary.get("discovered_target_count")
        ),
        "competitive_target_identity_operator_review_count": _int(
            competitive_target_identity_discovery_summary.get("operator_review_target_count")
        ),
        "competitive_target_identity_open_current_count": _int(
            competitive_target_identity_discovery_summary.get("open_current_target_count")
        ),
        "competitive_target_identity_closed_watchlist_count": _int(
            competitive_target_identity_discovery_summary.get("closed_watchlist_target_count")
        ),
        "competitive_target_identity_unknown_local_count": _int(
            competitive_target_identity_discovery_summary.get("unknown_local_target_count")
        ),
        "competitive_target_identity_synthetic_count": _int(
            competitive_target_identity_discovery_summary.get("synthetic_test_artifact_count")
        ),
        "competitive_target_identity_ready_for_intake_count": _int(
            competitive_target_identity_discovery_summary.get("ready_for_identity_intake_count")
        ),
        "competitive_target_identity_clearance_status": _text(
            competitive_target_identity_clearance_summary.get("clearance_queue_status")
        ),
        "competitive_target_identity_clearance_review_count": _int(
            competitive_target_identity_clearance_summary.get("review_target_count")
        ),
        "competitive_target_identity_clearance_prediction_count": _int(
            competitive_target_identity_clearance_summary.get("prediction_present_count")
        ),
        "competitive_target_identity_clearance_ts_prediction_count": _int(
            competitive_target_identity_clearance_summary.get("ts_prediction_present_count")
        ),
        "competitive_target_identity_clearance_native_count": _int(
            competitive_target_identity_clearance_summary.get("native_present_count")
        ),
        "competitive_target_identity_clearance_provenance_count": _int(
            competitive_target_identity_clearance_summary.get("provenance_cleared_count")
        ),
        "competitive_target_identity_clearance_ready_count": _int(
            competitive_target_identity_clearance_summary.get("ready_for_manifest_scaffold_count")
        ),
        "competitive_target_identity_clearance_awaiting_prediction_count": _int(
            competitive_target_identity_clearance_summary.get("awaiting_prediction_or_ts_count")
        ),
        "competitive_target_identity_clearance_awaiting_native_count": _int(
            competitive_target_identity_clearance_summary.get("awaiting_native_or_clearance_count")
        ),
        "competitive_target_identity_clearance_awaiting_no_leak_count": _int(
            competitive_target_identity_clearance_summary.get("awaiting_no_leak_clearance_count")
        ),
        "competitive_target_identity_clearance_workorder_status": _text(
            competitive_target_identity_clearance_workorder_summary.get("clearance_workorder_status")
        ),
        "competitive_target_identity_clearance_workorder_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("workorder_count")
        ),
        "competitive_target_identity_clearance_workorder_ready_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("ready_for_manifest_stub_count")
        ),
        "competitive_target_identity_clearance_workorder_native_provenance_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("native_and_provenance_required_count")
        ),
        "competitive_target_identity_clearance_workorder_native_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("native_required_count")
        ),
        "competitive_target_identity_clearance_workorder_provenance_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("provenance_required_count")
        ),
        "competitive_target_identity_clearance_workorder_dropzone_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("native_dropzone_count")
        ),
        "competitive_target_identity_clearance_workorder_template_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("provenance_template_count")
        ),
        "competitive_target_identity_clearance_workorder_stub_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("manifest_stub_count")
        ),
        "competitive_target_identity_clearance_workorder_template_preserved_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("provenance_template_preserved_count")
        ),
        "competitive_target_identity_clearance_workorder_template_refreshed_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("provenance_template_refreshed_count")
        ),
        "competitive_target_identity_clearance_workorder_stub_preserved_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("manifest_stub_preserved_count")
        ),
        "competitive_target_identity_clearance_workorder_stub_refreshed_count": _int(
            competitive_target_identity_clearance_workorder_summary.get("manifest_stub_refreshed_count")
        ),
        "competitive_target_identity_clearance_operator_intake_status": _text(
            competitive_target_identity_clearance_operator_intake_summary.get("operator_intake_status")
        ),
        "competitive_target_identity_clearance_operator_intake_row_count": _int(
            competitive_target_identity_clearance_operator_intake_summary.get("row_count")
        ),
        "competitive_target_identity_clearance_operator_intake_ready_count": _int(
            competitive_target_identity_clearance_operator_intake_summary.get("ready_to_apply_count")
        ),
        "competitive_target_identity_clearance_operator_intake_awaiting_count": _int(
            competitive_target_identity_clearance_operator_intake_summary.get("awaiting_input_count")
        ),
        "competitive_target_identity_clearance_operator_intake_blocked_count": _int(
            competitive_target_identity_clearance_operator_intake_summary.get("blocked_count")
        ),
        "competitive_target_identity_clearance_operator_intake_applied_count": _int(
            competitive_target_identity_clearance_operator_intake_summary.get("applied_count")
        ),
        "competitive_target_identity_clearance_operator_intake_native_copied_count": _int(
            competitive_target_identity_clearance_operator_intake_summary.get("native_copied_count")
        ),
        "competitive_target_identity_clearance_operator_intake_provenance_patched_count": _int(
            competitive_target_identity_clearance_operator_intake_summary.get("provenance_patched_count")
        ),
        "competitive_target_identity_clearance_native_candidate_status": _text(
            competitive_target_identity_clearance_native_candidate_summary.get("native_candidate_packet_status")
        ),
        "competitive_target_identity_clearance_native_candidate_row_count": _int(
            competitive_target_identity_clearance_native_candidate_summary.get("candidate_row_count")
        ),
        "competitive_target_identity_clearance_native_candidate_operator_review_count": _int(
            competitive_target_identity_clearance_native_candidate_summary.get("operator_review_required_count")
        ),
        "competitive_target_identity_clearance_native_candidate_relaxed_review_count": _int(
            competitive_target_identity_clearance_native_candidate_summary.get("relaxed_review_count")
        ),
        "competitive_target_identity_clearance_native_candidate_blocked_count": _int(
            competitive_target_identity_clearance_native_candidate_summary.get("blocked_candidate_count")
        ),
        "competitive_target_identity_clearance_native_candidate_collision_count": _int(
            competitive_target_identity_clearance_native_candidate_summary.get("current_target_collision_count")
        ),
        "competitive_target_identity_clearance_native_candidate_no_candidate_count": _int(
            competitive_target_identity_clearance_native_candidate_summary.get("no_candidate_target_count")
        ),
        "competitive_target_identity_clearance_native_candidate_prepared_count": _int(
            competitive_target_identity_clearance_native_candidate_summary.get("search_prepared_count")
        ),
        "competitive_target_identity_clearance_adjudication_status": _text(
            competitive_target_identity_clearance_adjudication_summary.get("adjudication_packet_status")
        ),
        "competitive_target_identity_clearance_adjudication_target_count": _int(
            competitive_target_identity_clearance_adjudication_summary.get("target_count")
        ),
        "competitive_target_identity_clearance_adjudication_replacement_required_count": _int(
            competitive_target_identity_clearance_adjudication_summary.get("replacement_required_count")
        ),
        "competitive_target_identity_clearance_adjudication_manual_native_search_count": _int(
            competitive_target_identity_clearance_adjudication_summary.get("manual_native_search_required_count")
        ),
        "competitive_target_identity_clearance_adjudication_operator_review_count": _int(
            competitive_target_identity_clearance_adjudication_summary.get("operator_review_required_count")
        ),
        "competitive_target_identity_clearance_adjudication_safe_apply_count": _int(
            competitive_target_identity_clearance_adjudication_summary.get("safe_to_apply_operator_intake_count")
        ),
        "competitive_target_identity_clearance_adjudication_md_count": _int(
            competitive_target_identity_clearance_adjudication_summary.get("adjudication_md_count")
        ),
        "competitive_target_identity_clearance_replacement_queue_status": _text(
            competitive_target_identity_clearance_replacement_queue_summary.get("replacement_queue_status")
        ),
        "competitive_target_identity_clearance_replacement_queue_target_count": _int(
            competitive_target_identity_clearance_replacement_queue_summary.get("replacement_required_target_count")
        ),
        "competitive_target_identity_clearance_replacement_queue_candidate_count": _int(
            competitive_target_identity_clearance_replacement_queue_summary.get("candidate_row_count")
        ),
        "competitive_target_identity_clearance_replacement_queue_ready_count": _int(
            competitive_target_identity_clearance_replacement_queue_summary.get("ready_candidate_count")
        ),
        "competitive_target_identity_clearance_replacement_queue_missing_prediction_count": _int(
            competitive_target_identity_clearance_replacement_queue_summary.get("blocked_missing_prediction_count")
        ),
        "competitive_target_identity_clearance_replacement_queue_current_collision_count": _int(
            competitive_target_identity_clearance_replacement_queue_summary.get("blocked_current_collision_count")
        ),
        "competitive_target_identity_clearance_replacement_queue_source_repair_count": _int(
            competitive_target_identity_clearance_replacement_queue_summary.get(
                "operator_source_repair_required_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_source_repair_status": _text(
            competitive_target_identity_clearance_replacement_source_repair_summary.get(
                "replacement_source_repair_status"
            )
        ),
        "competitive_target_identity_clearance_replacement_source_repair_candidate_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get("candidate_count")
        ),
        "competitive_target_identity_clearance_replacement_source_repair_ready_count": (
            competitive_target_identity_clearance_replacement_source_repair_ready_count
        ),
        "competitive_target_identity_clearance_replacement_source_repair_source_ready_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get("source_ready_count")
        ),
        "competitive_target_identity_clearance_replacement_source_repair_ready_prediction_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get("ready_for_prediction_count")
        ),
        "competitive_target_identity_clearance_replacement_source_repair_ready_validation_scorecard_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get(
                "ready_for_validation_scorecard_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_source_repair_awaiting_sequence_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get("awaiting_sequence_count")
        ),
        "competitive_target_identity_clearance_replacement_source_repair_blocked_cancelled_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get("blocked_cancelled_count")
        ),
        "competitive_target_identity_clearance_replacement_source_repair_current_collision_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get(
                "blocked_current_collision_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_source_repair_md_count": _int(
            competitive_target_identity_clearance_replacement_source_repair_summary.get("source_repair_md_count")
        ),
        "competitive_target_identity_clearance_replacement_scorecard_status": _text(
            competitive_target_identity_clearance_replacement_scorecard_summary.get("replacement_scorecard_status")
        ),
        "competitive_target_identity_clearance_replacement_scorecard_candidate_count": _int(
            competitive_target_identity_clearance_replacement_scorecard_summary.get("candidate_count")
        ),
        "competitive_target_identity_clearance_replacement_scorecard_pass_count": _int(
            competitive_target_identity_clearance_replacement_scorecard_summary.get("pass_count")
        ),
        "competitive_target_identity_clearance_replacement_scorecard_blocked_count": _int(
            competitive_target_identity_clearance_replacement_scorecard_summary.get("blocked_count")
        ),
        "competitive_target_identity_clearance_replacement_scorecard_json_count": _int(
            competitive_target_identity_clearance_replacement_scorecard_summary.get("scorecard_json_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_status": _text(
            competitive_target_identity_clearance_replacement_workorder_summary.get("replacement_workorder_status")
        ),
        "competitive_target_identity_clearance_replacement_workorder_target_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get("replacement_target_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_row_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get("workorder_row_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_selected_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get("selected_workorder_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_duplicate_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get(
                "duplicate_candidate_blocked_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_workorder_no_ready_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get(
                "no_ready_candidate_blocked_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_workorder_dropzone_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get("native_dropzone_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_template_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get("provenance_template_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_stub_count": _int(
            competitive_target_identity_clearance_replacement_workorder_summary.get("manifest_stub_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_status": _text(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                "clearance_workorder_audit_status"
            )
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_target_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get("audit_target_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_pass_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get("audit_pass_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_blocked_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get("audit_blocked_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_prediction_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get("prediction_present_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_native_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get("native_valid_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_provenance_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get("provenance_ready_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_manifest_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get("manifest_stub_ready_count")
        ),
        "competitive_target_identity_clearance_replacement_workorder_audit_native_prediction_waiting_count": _int(
            competitive_target_identity_clearance_replacement_workorder_audit_summary.get(
                "native_prediction_waiting_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_pickup_status": _text(
            competitive_target_identity_clearance_replacement_pickup_summary.get("replacement_pickup_status")
        ),
        "competitive_target_identity_clearance_replacement_pickup_row_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("row_count")
        ),
        "competitive_target_identity_clearance_replacement_pickup_selected_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("selected_count")
        ),
        "competitive_target_identity_clearance_replacement_pickup_ready_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("ready_for_operator_intake_count")
        ),
        "competitive_target_identity_clearance_replacement_pickup_awaiting_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("awaiting_operator_pickup_count")
        ),
        "competitive_target_identity_clearance_replacement_pickup_blocked_selection_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("blocked_selection_count")
        ),
        "competitive_target_identity_clearance_replacement_pickup_native_missing_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("native_missing_count")
        ),
        "competitive_target_identity_clearance_replacement_pickup_required_field_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("provenance_required_field_count")
        ),
        "competitive_target_identity_clearance_replacement_pickup_operator_action_count": _int(
            competitive_target_identity_clearance_replacement_pickup_summary.get("operator_action_count")
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_status": _text(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "duplicate_resolution_status"
            )
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_target_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "duplicate_replace_target_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_candidate_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get("candidate_row_count")
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_safe_unique_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "safe_unique_ready_candidate_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_duplicate_ready_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "duplicate_ready_candidate_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_blocked_duplicate_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "blocked_duplicate_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_cancelled_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "blocked_cancelled_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_current_collision_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "blocked_current_collision_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_duplicate_resolution_missing_prediction_count": _int(
            competitive_target_identity_clearance_replacement_duplicate_resolution_summary.get(
                "blocked_missing_prediction_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_status": _text(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get("decision_bundle_status")
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_target_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get("decision_target_count")
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_ready_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get("ready_decision_count")
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_open_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get("open_decision_count")
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_folder_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get("decision_folder_count")
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_candidate_csv_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                "candidate_resolution_csv_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_new_unique_template_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                "new_unique_template_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_duplicate_exception_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                "duplicate_exception_template_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_candidate_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get("candidate_row_count")
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_safe_unique_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                "safe_unique_ready_candidate_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_bundle_duplicate_ready_count": _int(
            competitive_target_identity_clearance_replacement_decision_bundle_summary.get(
                "duplicate_ready_candidate_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_status": _text(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                "decision_preflight_status"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_row_count": _int(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get("decision_row_count")
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_ready_new_count": _int(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                "ready_new_unique_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_ready_duplicate_count": _int(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                "ready_duplicate_exception_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_awaiting_count": _int(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                "awaiting_operator_decision_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_conflict_count": _int(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get("conflict_count")
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_new_unique_blocker_count": _int(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                "new_unique_blocker_count"
            )
        ),
        "competitive_target_identity_clearance_replacement_decision_preflight_duplicate_exception_blocker_count": _int(
            competitive_target_identity_clearance_replacement_decision_preflight_summary.get(
                "duplicate_exception_blocker_count"
            )
        ),
        "competitive_target_identity_clearance_manifest_sync_status": _text(
            competitive_target_identity_clearance_manifest_sync_summary.get("clearance_manifest_sync_status")
        ),
        "competitive_target_identity_clearance_manifest_sync_row_count": _int(
            competitive_target_identity_clearance_manifest_sync_summary.get("sync_row_count")
        ),
        "competitive_target_identity_clearance_manifest_sync_ready_count": _int(
            competitive_target_identity_clearance_manifest_sync_summary.get("ready_to_sync_count")
        ),
        "competitive_target_identity_clearance_manifest_sync_awaiting_count": _int(
            competitive_target_identity_clearance_manifest_sync_summary.get("awaiting_provenance_count")
        ),
        "competitive_target_identity_clearance_manifest_sync_blocked_count": _int(
            competitive_target_identity_clearance_manifest_sync_summary.get("blocked_count")
        ),
        "competitive_target_identity_clearance_manifest_sync_synced_count": _int(
            competitive_target_identity_clearance_manifest_sync_summary.get("synced_count")
        ),
        "competitive_target_identity_clearance_manifest_sync_changed_count": _int(
            competitive_target_identity_clearance_manifest_sync_summary.get("changed_field_count")
        ),
        "competitive_target_identity_clearance_manifest_sync_applied_count": _int(
            competitive_target_identity_clearance_manifest_sync_summary.get("applied_field_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_status": _text(
            competitive_target_identity_clearance_workorder_audit_summary.get("clearance_workorder_audit_status")
        ),
        "competitive_target_identity_clearance_workorder_audit_target_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("audit_target_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_pass_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("audit_pass_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_blocked_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("audit_blocked_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_prediction_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("prediction_present_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_prediction_protein_atom_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("prediction_protein_atom_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_prediction_coordinate_valid_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("prediction_coordinate_valid_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_identity_discovery_blocked_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("identity_discovery_blocked_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_identity_discovery_cleared_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("identity_discovery_cleared_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_native_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("native_valid_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_native_protein_atom_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("native_protein_atom_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_native_coordinate_valid_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("native_coordinate_valid_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_provenance_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("provenance_ready_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_evidence_ref_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("evidence_ref_present_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_evidence_ref_blocked_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("evidence_ref_blocked_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_evidence_ref_waiting_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("evidence_ref_waiting_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_evidence_ref_verified_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("evidence_ref_verified_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_evidence_ref_content_blocked_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("evidence_ref_content_blocked_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_manifest_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("manifest_stub_ready_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_manifest_provenance_matched_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("manifest_provenance_matched_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_manifest_provenance_mismatch_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("manifest_provenance_mismatch_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_native_prediction_distinct_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("native_prediction_distinct_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_native_prediction_same_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("native_prediction_same_count")
        ),
        "competitive_target_identity_clearance_workorder_audit_native_prediction_waiting_count": _int(
            competitive_target_identity_clearance_workorder_audit_summary.get("native_prediction_waiting_count")
        ),
        "competitive_target_identity_clearance_action_board_status": _text(
            competitive_target_identity_clearance_action_board_summary.get("action_board_status")
        ),
        "competitive_target_identity_clearance_action_board_action_count": _int(
            competitive_target_identity_clearance_action_board_summary.get("action_count")
        ),
        "competitive_target_identity_clearance_action_board_open_count": _int(
            competitive_target_identity_clearance_action_board_summary.get("open_action_count")
        ),
        "competitive_target_identity_clearance_action_board_native_count": _int(
            competitive_target_identity_clearance_action_board_summary.get("native_action_count")
        ),
        "competitive_target_identity_clearance_action_board_evidence_count": _int(
            competitive_target_identity_clearance_action_board_summary.get("evidence_action_count")
        ),
        "competitive_target_identity_clearance_action_board_provenance_count": _int(
            competitive_target_identity_clearance_action_board_summary.get("provenance_action_count")
        ),
        "competitive_target_identity_clearance_action_board_manifest_count": _int(
            competitive_target_identity_clearance_action_board_summary.get("manifest_action_count")
        ),
        "competitive_target_identity_clearance_action_bundle_status": _text(
            competitive_target_identity_clearance_action_bundle_summary.get("action_bundle_status")
        ),
        "competitive_target_identity_clearance_action_bundle_action_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("action_count")
        ),
        "competitive_target_identity_clearance_action_bundle_open_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("open_action_count")
        ),
        "competitive_target_identity_clearance_action_bundle_file_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("bundle_file_count")
        ),
        "competitive_target_identity_clearance_action_bundle_folder_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("action_folder_count")
        ),
        "competitive_target_identity_clearance_action_bundle_target_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("target_count")
        ),
        "competitive_target_identity_clearance_action_bundle_native_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("native_action_count")
        ),
        "competitive_target_identity_clearance_action_bundle_evidence_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("evidence_action_count")
        ),
        "competitive_target_identity_clearance_action_bundle_provenance_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("provenance_action_count")
        ),
        "competitive_target_identity_clearance_action_bundle_manifest_count": _int(
            competitive_target_identity_clearance_action_bundle_summary.get("manifest_action_count")
        ),
        "competitive_target_identity_clearance_promotion_status": _text(
            competitive_target_identity_clearance_promotion_summary.get("clearance_promotion_status")
        ),
        "competitive_target_identity_clearance_promotion_row_count": _int(
            competitive_target_identity_clearance_promotion_summary.get("promotion_row_count")
        ),
        "competitive_target_identity_clearance_promotion_promoted_count": _int(
            competitive_target_identity_clearance_promotion_summary.get("promoted_manifest_count")
        ),
        "competitive_target_identity_clearance_promotion_blocked_count": _int(
            competitive_target_identity_clearance_promotion_summary.get("blocked_count")
        ),
        "competitive_target_identity_clearance_promotion_ready_count": _int(
            competitive_target_identity_clearance_promotion_summary.get("ready_for_operator_manifest_import_count")
        ),
        "competitive_target_identity_clearance_promotion_audit_pass_count": _int(
            competitive_target_identity_clearance_promotion_summary.get("audit_pass_count")
        ),
        "competitive_target_identity_clearance_intake_staging_status": _text(
            competitive_target_identity_clearance_intake_staging_summary.get("clearance_intake_staging_status")
        ),
        "competitive_target_identity_clearance_intake_staging_promoted_count": _int(
            competitive_target_identity_clearance_intake_staging_summary.get("promoted_manifest_row_count")
        ),
        "competitive_target_identity_clearance_intake_staging_staged_count": _int(
            competitive_target_identity_clearance_intake_staging_summary.get("staged_identity_count")
        ),
        "competitive_target_identity_clearance_intake_staging_blocked_count": _int(
            competitive_target_identity_clearance_intake_staging_summary.get("blocked_assignment_count")
        ),
        "competitive_target_identity_clearance_intake_staging_open_slot_count": _int(
            competitive_target_identity_clearance_intake_staging_summary.get("open_identity_intake_slot_count")
        ),
        "competitive_target_identity_clearance_intake_staging_candidate_row_count": _int(
            competitive_target_identity_clearance_intake_staging_summary.get("candidate_intake_row_count")
        ),
        "competitive_target_identity_clearance_candidate_intake_sync_status": _text(
            competitive_target_identity_clearance_candidate_intake_sync_summary.get("candidate_intake_sync_status")
        ),
        "competitive_target_identity_clearance_candidate_intake_sync_row_count": _int(
            competitive_target_identity_clearance_candidate_intake_sync_summary.get("sync_row_count")
        ),
        "competitive_target_identity_clearance_candidate_intake_sync_ready_count": _int(
            competitive_target_identity_clearance_candidate_intake_sync_summary.get("ready_to_apply_count")
        ),
        "competitive_target_identity_clearance_candidate_intake_sync_waiting_count": _int(
            competitive_target_identity_clearance_candidate_intake_sync_summary.get("waiting_on_staged_identity_count")
        ),
        "competitive_target_identity_clearance_candidate_intake_sync_blocked_count": _int(
            competitive_target_identity_clearance_candidate_intake_sync_summary.get("blocked_count")
        ),
        "competitive_target_identity_clearance_candidate_intake_sync_applied_count": _int(
            competitive_target_identity_clearance_candidate_intake_sync_summary.get("applied_row_count")
        ),
        "competitive_target_identity_clearance_cycle_status": _text(
            competitive_target_identity_clearance_cycle_summary.get("clearance_cycle_status")
        ),
        "competitive_target_identity_clearance_cycle_stage_count": _int(
            competitive_target_identity_clearance_cycle_summary.get("stage_count")
        ),
        "competitive_target_identity_clearance_cycle_ready_stage_count": _int(
            competitive_target_identity_clearance_cycle_summary.get("ready_stage_count")
        ),
        "competitive_target_identity_clearance_cycle_blocked_stage_count": _int(
            competitive_target_identity_clearance_cycle_summary.get("blocked_stage_count")
        ),
        "competitive_target_identity_clearance_cycle_manifest_sync_status": _text(
            competitive_target_identity_clearance_cycle_summary.get("manifest_sync_status")
        ),
        "competitive_target_identity_clearance_cycle_audit_status": _text(
            competitive_target_identity_clearance_cycle_summary.get("audit_status")
        ),
        "competitive_target_identity_clearance_cycle_promotion_status": _text(
            competitive_target_identity_clearance_cycle_summary.get("promotion_status")
        ),
        "competitive_target_identity_clearance_cycle_staged_count": _int(
            competitive_target_identity_clearance_cycle_summary.get("staged_identity_count")
        ),
        "competitive_identity_cycle_status": _text(
            competitive_identity_cycle_summary.get("identity_cycle_status")
        ),
        "competitive_identity_cycle_stage_count": _int(
            competitive_identity_cycle_summary.get("stage_count")
        ),
        "competitive_identity_cycle_ready_stage_count": _int(
            competitive_identity_cycle_summary.get("ready_stage_count")
        ),
        "competitive_identity_cycle_blocked_stage_count": _int(
            competitive_identity_cycle_summary.get("blocked_stage_count")
        ),
        "competitive_identity_cycle_sync_status": _text(
            competitive_identity_cycle_summary.get("sync_status")
        ),
        "competitive_identity_cycle_sync_ready_to_sync_count": _int(
            competitive_identity_cycle_summary.get("sync_ready_to_sync_count")
        ),
        "competitive_identity_cycle_sync_awaiting_count": _int(
            competitive_identity_cycle_summary.get("sync_awaiting_count")
        ),
        "competitive_identity_cycle_missing_field_count": _int(
            competitive_identity_cycle_summary.get("sync_missing_field_count")
        ),
        "competitive_identity_cycle_readiness_gate_status": _text(
            competitive_identity_cycle_summary.get("readiness_gate_status")
        ),
        "competitive_file_source_plan_status": _text(
            competitive_file_source_plan_summary.get("file_source_status")
        ),
        "competitive_file_source_plan_action_count": _int(
            competitive_file_source_plan_summary.get("file_action_count")
        ),
        "competitive_file_source_plan_waiting_on_identity_count": _int(
            competitive_file_source_plan_summary.get("waiting_on_identity_count")
        ),
        "competitive_file_source_plan_identity_blocked_count": _int(
            competitive_file_source_plan_summary.get("identity_blocked_file_count")
        ),
        "competitive_file_source_plan_awaiting_source_path_count": _int(
            competitive_file_source_plan_summary.get("awaiting_source_path_count")
        ),
        "competitive_file_source_plan_ready_for_import_count": _int(
            competitive_file_source_plan_summary.get("ready_for_import_count")
        ),
        "competitive_file_source_plan_already_imported_count": _int(
            competitive_file_source_plan_summary.get("already_imported_count")
        ),
        "competitive_file_source_plan_blocked_count": _int(
            competitive_file_source_plan_summary.get("blocked_file_source_count")
        ),
        "competitive_value_entry_plan_status": _text(
            competitive_value_entry_plan_summary.get("value_entry_status")
        ),
        "competitive_value_entry_plan_action_count": _int(
            competitive_value_entry_plan_summary.get("value_action_count")
        ),
        "competitive_value_entry_plan_target_identity_count": _int(
            competitive_value_entry_plan_summary.get("target_identity_action_count")
        ),
        "competitive_value_entry_plan_provenance_count": _int(
            competitive_value_entry_plan_summary.get("provenance_action_count")
        ),
        "competitive_value_entry_plan_calibration_count": _int(
            competitive_value_entry_plan_summary.get("calibration_action_count")
        ),
        "competitive_value_entry_plan_waiting_on_identity_count": _int(
            competitive_value_entry_plan_summary.get("waiting_on_identity_count")
        ),
        "competitive_value_entry_plan_ready_from_identity_kit_count": _int(
            competitive_value_entry_plan_summary.get("ready_from_identity_kit_count")
        ),
        "competitive_value_entry_plan_awaiting_value_count": _int(
            competitive_value_entry_plan_summary.get("awaiting_value_count")
        ),
        "competitive_value_entry_plan_awaiting_clearance_count": _int(
            competitive_value_entry_plan_summary.get("awaiting_clearance_count")
        ),
        "competitive_value_entry_plan_awaiting_ref_count": _int(
            competitive_value_entry_plan_summary.get("awaiting_evidence_ref_count")
        ),
        "competitive_value_entry_plan_ready_for_import_count": _int(
            competitive_value_entry_plan_summary.get("ready_for_import_count")
        ),
        "competitive_value_entry_plan_blocked_count": _int(
            competitive_value_entry_plan_summary.get("blocked_value_count")
        ),
        "competitive_execution_board_status": _text(
            competitive_execution_board_summary.get("execution_board_status")
        ),
        "competitive_execution_board_row_count": _int(
            competitive_execution_board_summary.get("row_count")
        ),
        "competitive_execution_board_awaiting_identity_row_count": _int(
            competitive_execution_board_summary.get("awaiting_identity_row_count")
        ),
        "competitive_execution_board_ready_for_identity_apply_row_count": _int(
            competitive_execution_board_summary.get("ready_for_identity_apply_row_count")
        ),
        "competitive_execution_board_awaiting_file_source_row_count": _int(
            competitive_execution_board_summary.get("awaiting_file_source_row_count")
        ),
        "competitive_execution_board_awaiting_value_row_count": _int(
            competitive_execution_board_summary.get("awaiting_value_row_count")
        ),
        "competitive_execution_board_ready_for_evidence_import_row_count": _int(
            competitive_execution_board_summary.get("ready_for_evidence_import_row_count")
        ),
        "competitive_execution_board_blocked_row_count": _int(
            competitive_execution_board_summary.get("blocked_row_count")
        ),
        "competitive_execution_board_total_file_action_count": _int(
            competitive_execution_board_summary.get("total_file_action_count")
        ),
        "competitive_execution_board_total_value_action_count": _int(
            competitive_execution_board_summary.get("total_value_action_count")
        ),
        "competitive_execution_board_total_ready_action_count": _int(
            competitive_execution_board_summary.get("total_ready_action_count")
        ),
        "competitive_execution_board_total_blocked_action_count": _int(
            competitive_execution_board_summary.get("total_blocked_action_count")
        ),
        "competitive_readiness_gate_status": _text(
            competitive_readiness_gate_summary.get("readiness_gate_status")
        ),
        "competitive_readiness_gate_count": _int(
            competitive_readiness_gate_summary.get("gate_count")
        ),
        "competitive_readiness_gate_pass_count": _int(
            competitive_readiness_gate_summary.get("pass_count")
        ),
        "competitive_readiness_gate_blocked_count": _int(
            competitive_readiness_gate_summary.get("blocked_gate_count")
        ),
        "competitive_readiness_gate_first_blocked_gate_id": _text(
            competitive_readiness_gate_summary.get("first_blocked_gate_id")
        ),
        "competitive_readiness_gate_first_blocked_status": _text(
            competitive_readiness_gate_summary.get("first_blocked_status")
        ),
        "competitive_value_ledger_status": _text(
            competitive_value_ledger_summary.get("value_ledger_status")
        ),
        "competitive_value_ledger_count": _int(
            competitive_value_ledger_summary.get("ledger_count")
        ),
        "competitive_value_ledger_action_count": _int(
            competitive_value_ledger_summary.get("action_count")
        ),
        "competitive_value_ledger_ready_for_intake_count": _int(
            competitive_value_ledger_summary.get("ready_for_intake_count")
        ),
        "competitive_value_ledger_awaiting_value_count": _int(
            competitive_value_ledger_summary.get("awaiting_value_count")
        ),
        "competitive_evidence_intake_status": _text(
            competitive_evidence_intake_summary.get("intake_status")
        ),
        "competitive_evidence_intake_action_count": _int(
            competitive_evidence_intake_summary.get("action_count")
        ),
        "competitive_evidence_intake_patch_candidate_count": _int(
            competitive_evidence_intake_summary.get("patch_candidate_count")
        ),
        "competitive_evidence_intake_awaiting_file_count": _int(
            competitive_evidence_intake_summary.get("awaiting_dropzone_file_count")
        ),
        "competitive_evidence_intake_awaiting_value_count": _int(
            competitive_evidence_intake_summary.get("awaiting_operator_value_count")
        ),
        "competitive_patch_gate_status": _text(
            competitive_patch_gate_summary.get("patch_gate_status")
        ),
        "competitive_patch_gate_action_count": _int(
            competitive_patch_gate_summary.get("action_count")
        ),
        "competitive_patch_gate_ready_to_patch_count": _int(
            competitive_patch_gate_summary.get("ready_to_patch_count")
        ),
        "competitive_patch_gate_awaiting_evidence_count": _int(
            competitive_patch_gate_summary.get("awaiting_evidence_count")
        ),
        "competitive_patch_gate_conflict_count": _int(
            competitive_patch_gate_summary.get("conflict_count")
        ),
        "competitive_apply_plan_status": _text(
            competitive_apply_plan_summary.get("apply_plan_status")
        ),
        "competitive_apply_plan_action_count": _int(
            competitive_apply_plan_summary.get("action_count")
        ),
        "competitive_apply_plan_planned_patch_count": _int(
            competitive_apply_plan_summary.get("planned_patch_count")
        ),
        "competitive_apply_plan_awaiting_evidence_count": _int(
            competitive_apply_plan_summary.get("awaiting_evidence_count")
        ),
        "competitive_apply_plan_applied_count": _int(
            competitive_apply_plan_summary.get("applied_count")
        ),
        "competitive_operator_template_status": _text(
            competitive_operator_template_summary.get("template_status")
        ),
        "competitive_operator_template_ready_count": _int(
            competitive_operator_template_summary.get("ready_for_preflight_count")
        ),
        "competitive_operator_template_row_count": _int(
            competitive_operator_template_summary.get("row_count")
        ),
        "competitive_operator_template_row_fill_count": _int(
            competitive_operator_template_summary.get("row_fill_candidate_count")
        ),
        "competitive_operator_preflight_status": _text(
            competitive_operator_preflight_summary.get("operator_preflight_status")
        ),
        "competitive_operator_preflight_ready_count": _int(
            competitive_operator_preflight_summary.get("ready_count")
        ),
        "competitive_operator_preflight_row_count": _int(
            competitive_operator_preflight_summary.get("row_count")
        ),
        "required_file_count": _int(inventory_summary.get("required_file_count")),
        "present_file_count": _int(inventory_summary.get("present_file_count")),
        "missing_file_count": _int(inventory_summary.get("missing_file_count")),
        "current_proven_level": _text(closure_summary.get("current_proven_level")),
        "next_unclosed_level": _text(closure_summary.get("next_unclosed_level")),
        "first_operator_input_action_id": first_operator_action,
        "first_operator_input_blockers": first_operator_blockers,
        "first_operator_fill_action": first_fill_action,
        "claim_boundary": (
            "Local CASP17 workbench index only. It links current target model folders, benchmark input scaffolds, "
            "and win-gap packets; it does not fetch native structures, use external predictors, prove native accuracy, "
            "or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": artifact_rows, "target_rows": target_rows[:]}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Workbench Index",
        "",
        "This is the local navigation surface for the current CASP17 internal-physics lane.",
        "",
        "- goal objective addendum: `casp17/CASP17_WIN_TIER_GOAL.md`",
        "- win-tier target: scaffold `65 -> 90`, competitive proof `15-25 -> 85-90`, "
        "leaderboard `top-5/top-3/top-1-2` by category.",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- workbench_status: `{summary['workbench_status']}`",
        f"- target model folders: `{summary['target_model_ready_count']}/{summary['target_model_count']}`",
        f"- target object folders: `{summary['target_model_object_count']}`",
        f"- target object projections: `{summary['target_model_object_projection_count']}`",
        f"- target object viewers: `{summary['target_model_object_viewer_count']}`",
        f"- target object folder audit: `{summary['target_object_folder_audit_status'] or '-'}` rows `{summary['target_object_folder_audit_pass_count']}/{summary['target_object_folder_audit_total']}` chain isolation `{summary['target_object_folder_chain_isolation_pass_count']}/{summary['target_object_folder_audit_total']}` protein atoms/coordinate-valid `{summary['target_object_folder_protein_atom_pass_count']}/{summary['target_object_folder_coordinate_valid_pass_count']}/{summary['target_object_folder_audit_total']}` total protein atoms `{summary['target_object_folder_total_protein_atom_count']}`",
        f"- target object viewer smoke: `{summary['target_object_viewer_smoke_status'] or '-'}` rows `{summary['target_object_viewer_smoke_pass_count']}/{summary['target_object_viewer_smoke_total']}`",
        f"- target object model review: `{summary['target_object_model_review_status'] or '-'}` pass/blocked/total `{summary['target_object_model_review_pass_count']}/{summary['target_object_model_review_blocked_count']}/{summary['target_object_model_review_total']}` review md/viewers `{summary['target_object_model_review_md_count']}/{summary['target_object_model_review_viewer_local_pass_count']}` protein/CA/residue `{summary['target_object_model_review_protein_atom_count']}/{summary['target_object_model_review_ca_atom_count']}/{summary['target_object_model_review_residue_count']}` radius `{summary['target_object_model_review_min_radius']}/{summary['target_object_model_review_max_radius']}` gallery `{summary['target_object_model_review_gallery_status'] or '-'}` `{summary['target_object_model_review_gallery_html'] or '-'}`",
        f"- protein object library: `{summary['protein_object_library_status'] or '-'}` protein/object folders `{summary['protein_object_library_protein_folder_count']}/{summary['protein_object_library_object_folder_count']}` pass/blocked `{summary['protein_object_library_pass_count']}/{summary['protein_object_library_blocked_count']}` model/projection/viewer pointers `{summary['protein_object_library_model_pointer_count']}/{summary['protein_object_library_projection_pointer_count']}/{summary['protein_object_library_viewer_pointer_count']}` `{summary['protein_object_library_dir'] or '-'}`",
        f"- raw-ranked model quarantine: `{summary['raw_ranked_model_quarantine_status'] or '-'}` targets/models/top5 `{summary['raw_ranked_model_quarantine_target_count']}/{summary['raw_ranked_model_quarantine_model_count']}/{summary['raw_ranked_model_quarantine_top5_count']}` quarantined/linked/author-present `{summary['raw_ranked_model_quarantine_quarantined_count']}/{summary['raw_ranked_model_quarantine_linked_count']}/{summary['raw_ranked_model_quarantine_author_present_count']}` atoms `{summary['raw_ranked_model_quarantine_atom_count']}`",
        f"- benchmark rows ready/total: `{summary['benchmark_rows_ready_count']}/{summary['benchmark_rows_total']}`",
        f"- win-tier goal scorecard: `{summary['win_tier_goal_scorecard_status'] or '-'}` pass/partial/blocked `{summary['win_tier_goal_scorecard_pass_count']}/{summary['win_tier_goal_scorecard_partial_count']}/{summary['win_tier_goal_scorecard_blocked_count']}` first blocked `{summary['win_tier_goal_scorecard_first_blocked_gate'] or '-'}`",
        f"- win gap closure: `{summary['win_gap_closure_status'] or '-'}` closed/open `{summary['win_gap_closed_count']}/{summary['win_gap_not_closed_count']}` missing win rows `{summary['benchmark_missing_win_total_rows']}`",
        f"- historical benchmark workorders: `{summary['historical_input_workorder_count']}` core `{summary['historical_core_workorder_count']}` missing core/ablation `{summary['historical_missing_core_file_count']}/{summary['historical_missing_ablation_layer_file_count']}` operator ready/blocked `{summary['benchmark_operator_ready_count']}/{summary['benchmark_operator_blocked_count']}`",
        f"- operator dashboard: `{summary['operator_dashboard_status'] or '-'}` rows ready/blocked/total `{summary['operator_dashboard_ready_count']}/{summary['operator_dashboard_blocked_count']}/{summary['operator_dashboard_row_count']}` needs target/core/ablation/calibration/provenance `{summary['operator_dashboard_needs_target_replacement_count']}/{summary['operator_dashboard_needs_core_file_count']}/{summary['operator_dashboard_needs_ablation_layer_count']}/{summary['operator_dashboard_needs_calibration_count']}/{summary['operator_dashboard_needs_provenance_count']}`",
        f"- historical identity seed inventory: `{summary['historical_identity_seed_inventory_status'] or '-'}` candidates monomer/complex/total `{summary['historical_identity_seed_monomer_count']}/{summary['historical_identity_seed_complex_count']}/{summary['historical_identity_seed_candidate_count']}` eligible `{summary['historical_identity_seed_eligible_monomer_count']}/{summary['historical_identity_seed_eligible_complex_count']}` batch/manifest `{summary['historical_identity_seed_batch_slot_count']}/{summary['historical_identity_seed_manifest_row_count']}` clearance-required `{summary['historical_identity_seed_operator_clearance_required_count']}` first `{summary['historical_identity_seed_first_target_id'] or '-'}` manifest `{summary['historical_identity_seed_manifest_csv'] or '-'}`",
        f"- historical identity seed clearance: `{summary['historical_identity_seed_clearance_status'] or '-'}` template `{summary['historical_identity_seed_clearance_template_status'] or '-'}` ready/awaiting/total `{summary['historical_identity_seed_clearance_ready_count']}/{summary['historical_identity_seed_clearance_awaiting_count']}/{summary['historical_identity_seed_clearance_seed_count']}` cleared manifest `{summary['historical_identity_seed_clearance_cleared_manifest_count']}` open identity/core/provenance/calibration/ablation `{summary['historical_identity_seed_clearance_identity_open_count']}/{summary['historical_identity_seed_clearance_core_files_open_count']}/{summary['historical_identity_seed_clearance_no_leak_open_count']}/{summary['historical_identity_seed_clearance_calibration_open_count']}/{summary['historical_identity_seed_clearance_ablation_open_count']}` blocking fields `{summary['historical_identity_seed_clearance_blocking_field_count']}` first `{summary['historical_identity_seed_clearance_first_target_id'] or '-'}` operator `{summary['historical_identity_seed_clearance_operator_csv'] or '-'}` cleared `{summary['historical_identity_seed_clearance_cleared_manifest_csv'] or '-'}`",
        f"- historical identity seed clearance action bundle: `{summary['historical_identity_seed_clearance_action_bundle_status'] or '-'}` targets/actions/open `{summary['historical_identity_seed_clearance_action_bundle_target_count']}/{summary['historical_identity_seed_clearance_action_bundle_action_count']}/{summary['historical_identity_seed_clearance_action_bundle_open_count']}` files/folders `{summary['historical_identity_seed_clearance_action_bundle_file_count']}/{summary['historical_identity_seed_clearance_action_bundle_folder_count']}` identity/core/no-leak/calibration/ablation `{summary['historical_identity_seed_clearance_action_bundle_identity_count']}/{summary['historical_identity_seed_clearance_action_bundle_core_count']}/{summary['historical_identity_seed_clearance_action_bundle_no_leak_count']}/{summary['historical_identity_seed_clearance_action_bundle_calibration_count']}/{summary['historical_identity_seed_clearance_action_bundle_ablation_count']}` first `{summary['historical_identity_seed_clearance_action_bundle_first_action'] or '-'}`",
        f"- sidechain-native benchmark: `{summary['sidechain_native_benchmark_status'] or '-'}` pass/blocked/total `{summary['sidechain_native_pass_count']}/{summary['sidechain_native_blocked_count']}/{summary['sidechain_native_benchmark_count']}` core/leakage/pred/native/missing-files `{summary['sidechain_native_core_input_blocked_count']}/{summary['sidechain_native_leakage_blocked_count']}/{summary['sidechain_native_prediction_missing_count']}/{summary['sidechain_native_native_missing_count']}/{summary['sidechain_native_missing_core_file_count']}` exactness/metric `{summary['sidechain_native_exactness_blocked_count']}/{summary['sidechain_native_metric_blocked_count']}` first `{summary['sidechain_native_first_blocked_benchmark_id'] or '-'}` blockers `{summary['sidechain_native_first_blocked_blockers'] or '-'}`",
        f"- sidechain-native workorder: actions/open `{summary['sidechain_native_workorder_action_count']}/{summary['sidechain_native_open_workorder_action_count']}` files `{summary['sidechain_native_workorder_json'] or '-'}` `{summary['sidechain_native_workorder_md'] or '-'}`",
        f"- competitive-floor batch: `{summary['competitive_batch_status'] or '-'}` rows `{summary['competitive_batch_row_count']}` missing evidence `{summary['competitive_batch_missing_evidence_item_count']}`",
        f"- competitive row_fill status: `{summary['competitive_row_fill_status'] or '-'}` filled/ready/total `{summary['competitive_row_fill_filled_count']}/{summary['competitive_row_fill_ready_count']}/{summary['competitive_row_fill_row_count']}`",
        f"- competitive row_fill worklist: `{summary['competitive_row_fill_worklist_status'] or '-'}` open actions `{summary['competitive_row_fill_worklist_open_action_count']}` guides `{summary['competitive_row_fill_worklist_guide_count']}`",
        f"- competitive evidence dropzones: `{summary['competitive_evidence_dropzone_status'] or '-'}` dropzones/manifests `{summary['competitive_evidence_dropzone_count']}/{summary['competitive_evidence_dropzone_manifest_count']}` open actions `{summary['competitive_evidence_dropzone_open_action_count']}` file actions `{summary['competitive_evidence_dropzone_file_action_count']}`",
        f"- competitive evidence import: `{summary['competitive_evidence_import_status'] or '-'}` actions `{summary['competitive_evidence_import_action_count']}` ready/applied `{summary['competitive_evidence_import_ready_for_apply_count']}/{summary['competitive_evidence_import_applied_count']}` awaiting files/values `{summary['competitive_evidence_import_awaiting_file_count']}/{summary['competitive_evidence_import_awaiting_value_count']}` blocked `{summary['competitive_evidence_import_blocked_count']}`",
        f"- competitive evidence round: `{summary['competitive_evidence_round_status'] or '-'}` stages `{summary['competitive_evidence_round_stage_count']}` import ready/applied `{summary['competitive_evidence_round_import_ready_for_apply_count']}/{summary['competitive_evidence_round_import_applied_count']}` patch candidates/planned `{summary['competitive_evidence_round_patch_candidate_count']}/{summary['competitive_evidence_round_apply_plan_planned_patch_count']}`",
        f"- competitive unlock priority: `{summary['competitive_unlock_priority_status'] or '-'}` phases `{summary['competitive_unlock_priority_phase_row_count']}` identity open `{summary['competitive_unlock_priority_identity_open_action_count']}` target_id open `{summary['competitive_unlock_priority_target_id_open_count']}` files waiting `{summary['competitive_unlock_priority_file_waiting_on_identity_count']}`",
        f"- competitive identity unlock kit: `{summary['competitive_identity_unlock_status'] or '-'}` rows `{summary['competitive_identity_unlock_ready_count']}/{summary['competitive_identity_unlock_awaiting_count']}/{summary['competitive_identity_unlock_blocked_count']}/{summary['competitive_identity_unlock_row_count']}` files unlocked `{summary['competitive_identity_unlock_file_actions_unlocked_count']}`",
        f"- competitive identity unlock round: `{summary['competitive_identity_round_status'] or '-'}` rows `{summary['competitive_identity_round_ready_for_import_count']}/{summary['competitive_identity_round_awaiting_count']}/{summary['competitive_identity_round_blocked_count']}/{summary['competitive_identity_round_row_count']}` import ready/applied `{summary['competitive_identity_round_import_ready_for_apply_count']}/{summary['competitive_identity_round_import_applied_count']}` target_id open `{summary['competitive_identity_round_target_id_open_count']}` files waiting `{summary['competitive_identity_round_file_waiting_on_identity_count']}`",
        f"- competitive identity intake bundle: `{summary['competitive_identity_intake_status'] or '-'}` rows `{summary['competitive_identity_intake_ready_count']}/{summary['competitive_identity_intake_awaiting_count']}/{summary['competitive_identity_intake_blocked_count']}/{summary['competitive_identity_intake_row_count']}` missing fields `{summary['competitive_identity_intake_missing_field_count']}` files unlocked `{summary['competitive_identity_intake_file_actions_unlocked_count']}`",
        f"- competitive identity intake sync: `{summary['competitive_identity_sync_status'] or '-'}` rows `{summary['competitive_identity_sync_synced_count']}/{summary['competitive_identity_sync_ready_to_sync_count']}/{summary['competitive_identity_sync_awaiting_count']}/{summary['competitive_identity_sync_blocked_count']}/{summary['competitive_identity_sync_row_count']}` missing fields `{summary['competitive_identity_sync_missing_field_count']}` mismatches `{summary['competitive_identity_sync_kit_mismatch_count']}` applied `{summary['competitive_identity_sync_applied_count']}`",
        f"- competitive identity candidates: `{summary['competitive_identity_candidate_status'] or '-'}` rows `{summary['competitive_identity_candidate_ready_count']}/{summary['competitive_identity_candidate_awaiting_count']}/{summary['competitive_identity_candidate_row_count']}` source ready/blocked/total `{summary['competitive_identity_candidate_source_ready_count']}/{summary['competitive_identity_candidate_source_blocked_count']}/{summary['competitive_identity_candidate_source_count']}` applied `{summary['competitive_identity_candidate_applied_count']}` operator preflight `{summary['competitive_identity_candidate_operator_preflight_status'] or '-'}`",
        f"- competitive floor unblock map: `{summary['competitive_floor_unblock_map_status'] or '-'}` rows ready/awaiting/total `{summary['competitive_floor_unblock_map_ready_count']}/{summary['competitive_floor_unblock_map_awaiting_count']}/{summary['competitive_floor_unblock_map_row_count']}` source ready/blocked/total `{summary['competitive_floor_unblock_map_source_ready_count']}/{summary['competitive_floor_unblock_map_source_blocked_count']}/{summary['competitive_floor_unblock_map_source_count']}` open target/core/provenance/ablation/calibration `{summary['competitive_floor_unblock_map_target_identity_open_count']}/{summary['competitive_floor_unblock_map_core_files_open_count']}/{summary['competitive_floor_unblock_map_no_leak_provenance_open_count']}/{summary['competitive_floor_unblock_map_ablation_files_open_count']}/{summary['competitive_floor_unblock_map_calibration_values_open_count']}` blocking fields/phases `{summary['competitive_floor_unblock_map_blocking_field_count']}/{summary['competitive_floor_unblock_map_blocking_phase_count']}` first `{summary['competitive_floor_unblock_map_first_open_dropzone_id'] or '-'}` `{summary['competitive_floor_unblock_map_first_open_phase'] or '-'}`",
        f"- competitive identity source repair: `{summary['competitive_identity_source_repair_status'] or '-'}` actions `{summary['competitive_identity_source_repair_action_count']}` blocked sources `{summary['competitive_identity_source_repair_blocked_source_count']}` phase identity/core/provenance/ablation/calibration `{summary['competitive_identity_source_repair_target_identity_count']}/{summary['competitive_identity_source_repair_core_file_count']}/{summary['competitive_identity_source_repair_provenance_count']}/{summary['competitive_identity_source_repair_ablation_count']}/{summary['competitive_identity_source_repair_calibration_count']}` first phase `{summary['competitive_identity_source_repair_first_phase'] or '-'}`",
        f"- competitive target identity discovery: `{summary['competitive_target_identity_discovery_status'] or '-'}` discovered `{summary['competitive_target_identity_discovery_count']}` operator/current/closed/unknown/synthetic `{summary['competitive_target_identity_operator_review_count']}/{summary['competitive_target_identity_open_current_count']}/{summary['competitive_target_identity_closed_watchlist_count']}/{summary['competitive_target_identity_unknown_local_count']}/{summary['competitive_target_identity_synthetic_count']}` ready intake `{summary['competitive_target_identity_ready_for_intake_count']}`",
        f"- competitive target identity clearance: `{summary['competitive_target_identity_clearance_status'] or '-'}` review `{summary['competitive_target_identity_clearance_review_count']}` prediction/TS/native/provenance `{summary['competitive_target_identity_clearance_prediction_count']}/{summary['competitive_target_identity_clearance_ts_prediction_count']}/{summary['competitive_target_identity_clearance_native_count']}/{summary['competitive_target_identity_clearance_provenance_count']}` ready `{summary['competitive_target_identity_clearance_ready_count']}` awaiting prediction/native/no-leak `{summary['competitive_target_identity_clearance_awaiting_prediction_count']}/{summary['competitive_target_identity_clearance_awaiting_native_count']}/{summary['competitive_target_identity_clearance_awaiting_no_leak_count']}`",
        f"- competitive target identity clearance workorders: `{summary['competitive_target_identity_clearance_workorder_status'] or '-'}` workorders `{summary['competitive_target_identity_clearance_workorder_count']}` ready/native+provenance/native/provenance `{summary['competitive_target_identity_clearance_workorder_ready_count']}/{summary['competitive_target_identity_clearance_workorder_native_provenance_count']}/{summary['competitive_target_identity_clearance_workorder_native_count']}/{summary['competitive_target_identity_clearance_workorder_provenance_count']}` dropzones/templates/stubs `{summary['competitive_target_identity_clearance_workorder_dropzone_count']}/{summary['competitive_target_identity_clearance_workorder_template_count']}/{summary['competitive_target_identity_clearance_workorder_stub_count']}` preserved templates/stubs `{summary['competitive_target_identity_clearance_workorder_template_preserved_count']}/{summary['competitive_target_identity_clearance_workorder_stub_preserved_count']}` refreshed templates/stubs `{summary['competitive_target_identity_clearance_workorder_template_refreshed_count']}/{summary['competitive_target_identity_clearance_workorder_stub_refreshed_count']}`",
        f"- competitive target identity clearance operator intake: `{summary['competitive_target_identity_clearance_operator_intake_status'] or '-'}` rows ready/awaiting/blocked/applied `{summary['competitive_target_identity_clearance_operator_intake_row_count']}/{summary['competitive_target_identity_clearance_operator_intake_ready_count']}/{summary['competitive_target_identity_clearance_operator_intake_awaiting_count']}/{summary['competitive_target_identity_clearance_operator_intake_blocked_count']}/{summary['competitive_target_identity_clearance_operator_intake_applied_count']}` native/provenance applied `{summary['competitive_target_identity_clearance_operator_intake_native_copied_count']}/{summary['competitive_target_identity_clearance_operator_intake_provenance_patched_count']}`",
        f"- competitive target identity clearance native candidates: `{summary['competitive_target_identity_clearance_native_candidate_status'] or '-'}` rows `{summary['competitive_target_identity_clearance_native_candidate_row_count']}` operator/relaxed/blocked/collision/no-candidate/prepared `{summary['competitive_target_identity_clearance_native_candidate_operator_review_count']}/{summary['competitive_target_identity_clearance_native_candidate_relaxed_review_count']}/{summary['competitive_target_identity_clearance_native_candidate_blocked_count']}/{summary['competitive_target_identity_clearance_native_candidate_collision_count']}/{summary['competitive_target_identity_clearance_native_candidate_no_candidate_count']}/{summary['competitive_target_identity_clearance_native_candidate_prepared_count']}`",
        f"- competitive target identity clearance adjudication: `{summary['competitive_target_identity_clearance_adjudication_status'] or '-'}` targets `{summary['competitive_target_identity_clearance_adjudication_target_count']}` replacement/manual/operator-review/safe/md `{summary['competitive_target_identity_clearance_adjudication_replacement_required_count']}/{summary['competitive_target_identity_clearance_adjudication_manual_native_search_count']}/{summary['competitive_target_identity_clearance_adjudication_operator_review_count']}/{summary['competitive_target_identity_clearance_adjudication_safe_apply_count']}/{summary['competitive_target_identity_clearance_adjudication_md_count']}`",
        f"- competitive target identity clearance replacement queue: `{summary['competitive_target_identity_clearance_replacement_queue_status'] or '-'}` targets/candidates `{summary['competitive_target_identity_clearance_replacement_queue_target_count']}/{summary['competitive_target_identity_clearance_replacement_queue_candidate_count']}` ready/missing-prediction/current-collision/source-repair `{summary['competitive_target_identity_clearance_replacement_queue_ready_count']}/{summary['competitive_target_identity_clearance_replacement_queue_missing_prediction_count']}/{summary['competitive_target_identity_clearance_replacement_queue_current_collision_count']}/{summary['competitive_target_identity_clearance_replacement_queue_source_repair_count']}`",
        f"- competitive target identity clearance replacement source repair: `{summary['competitive_target_identity_clearance_replacement_source_repair_status'] or '-'}` candidates/ready/md `{summary['competitive_target_identity_clearance_replacement_source_repair_candidate_count']}/{summary['competitive_target_identity_clearance_replacement_source_repair_ready_count']}/{summary['competitive_target_identity_clearance_replacement_source_repair_md_count']}` source-ready/predict/validate/sequence/cancelled/collision `{summary['competitive_target_identity_clearance_replacement_source_repair_source_ready_count']}/{summary['competitive_target_identity_clearance_replacement_source_repair_ready_prediction_count']}/{summary['competitive_target_identity_clearance_replacement_source_repair_ready_validation_scorecard_count']}/{summary['competitive_target_identity_clearance_replacement_source_repair_awaiting_sequence_count']}/{summary['competitive_target_identity_clearance_replacement_source_repair_blocked_cancelled_count']}/{summary['competitive_target_identity_clearance_replacement_source_repair_current_collision_count']}`",
        f"- competitive target identity clearance replacement scorecard: `{summary['competitive_target_identity_clearance_replacement_scorecard_status'] or '-'}` candidates/pass/blocked/json `{summary['competitive_target_identity_clearance_replacement_scorecard_candidate_count']}/{summary['competitive_target_identity_clearance_replacement_scorecard_pass_count']}/{summary['competitive_target_identity_clearance_replacement_scorecard_blocked_count']}/{summary['competitive_target_identity_clearance_replacement_scorecard_json_count']}`",
        f"- competitive target identity clearance replacement workorder: `{summary['competitive_target_identity_clearance_replacement_workorder_status'] or '-'}` targets/rows `{summary['competitive_target_identity_clearance_replacement_workorder_target_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_row_count']}` selected/duplicate/no-ready `{summary['competitive_target_identity_clearance_replacement_workorder_selected_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_duplicate_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_no_ready_count']}` dropzones/templates/stubs `{summary['competitive_target_identity_clearance_replacement_workorder_dropzone_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_template_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_stub_count']}`",
        f"- competitive target identity clearance replacement workorder audit: `{summary['competitive_target_identity_clearance_replacement_workorder_audit_status'] or '-'}` pass/blocked/total `{summary['competitive_target_identity_clearance_replacement_workorder_audit_pass_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_audit_blocked_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_audit_target_count']}` prediction/native/provenance/manifest `{summary['competitive_target_identity_clearance_replacement_workorder_audit_prediction_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_audit_native_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_audit_provenance_count']}/{summary['competitive_target_identity_clearance_replacement_workorder_audit_manifest_count']}` native/prediction waiting `{summary['competitive_target_identity_clearance_replacement_workorder_audit_native_prediction_waiting_count']}`",
        f"- competitive target identity clearance replacement pickup: `{summary['competitive_target_identity_clearance_replacement_pickup_status'] or '-'}` selected/ready/awaiting/blocked-selection `{summary['competitive_target_identity_clearance_replacement_pickup_selected_count']}/{summary['competitive_target_identity_clearance_replacement_pickup_ready_count']}/{summary['competitive_target_identity_clearance_replacement_pickup_awaiting_count']}/{summary['competitive_target_identity_clearance_replacement_pickup_blocked_selection_count']}` native-missing/required-fields/actions `{summary['competitive_target_identity_clearance_replacement_pickup_native_missing_count']}/{summary['competitive_target_identity_clearance_replacement_pickup_required_field_count']}/{summary['competitive_target_identity_clearance_replacement_pickup_operator_action_count']}`",
        f"- competitive target identity clearance replacement duplicate resolution: `{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_status'] or '-'}` targets/candidates `{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_target_count']}/{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_candidate_count']}` safe-unique/duplicate-ready `{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_safe_unique_count']}/{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_duplicate_ready_count']}` blocked duplicate/cancelled/current-collision/missing-prediction `{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_blocked_duplicate_count']}/{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_cancelled_count']}/{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_current_collision_count']}/{summary['competitive_target_identity_clearance_replacement_duplicate_resolution_missing_prediction_count']}`",
        f"- competitive target identity clearance replacement decision bundle: `{summary['competitive_target_identity_clearance_replacement_decision_bundle_status'] or '-'}` decisions ready/open/total `{summary['competitive_target_identity_clearance_replacement_decision_bundle_ready_count']}/{summary['competitive_target_identity_clearance_replacement_decision_bundle_open_count']}/{summary['competitive_target_identity_clearance_replacement_decision_bundle_target_count']}` folders/candidate-csv/new-unique/duplicate-exception `{summary['competitive_target_identity_clearance_replacement_decision_bundle_folder_count']}/{summary['competitive_target_identity_clearance_replacement_decision_bundle_candidate_csv_count']}/{summary['competitive_target_identity_clearance_replacement_decision_bundle_new_unique_template_count']}/{summary['competitive_target_identity_clearance_replacement_decision_bundle_duplicate_exception_count']}` candidates safe-unique/duplicate-ready/total `{summary['competitive_target_identity_clearance_replacement_decision_bundle_safe_unique_count']}/{summary['competitive_target_identity_clearance_replacement_decision_bundle_duplicate_ready_count']}/{summary['competitive_target_identity_clearance_replacement_decision_bundle_candidate_count']}`",
        f"- competitive target identity clearance replacement decision preflight: `{summary['competitive_target_identity_clearance_replacement_decision_preflight_status'] or '-'}` decisions ready-new/ready-duplicate/awaiting/conflict/total `{summary['competitive_target_identity_clearance_replacement_decision_preflight_ready_new_count']}/{summary['competitive_target_identity_clearance_replacement_decision_preflight_ready_duplicate_count']}/{summary['competitive_target_identity_clearance_replacement_decision_preflight_awaiting_count']}/{summary['competitive_target_identity_clearance_replacement_decision_preflight_conflict_count']}/{summary['competitive_target_identity_clearance_replacement_decision_preflight_row_count']}` blocker rows new-unique/duplicate-exception `{summary['competitive_target_identity_clearance_replacement_decision_preflight_new_unique_blocker_count']}/{summary['competitive_target_identity_clearance_replacement_decision_preflight_duplicate_exception_blocker_count']}`",
        f"- competitive target identity clearance manifest sync: `{summary['competitive_target_identity_clearance_manifest_sync_status'] or '-'}` rows ready/awaiting/blocked/synced `{summary['competitive_target_identity_clearance_manifest_sync_row_count']}/{summary['competitive_target_identity_clearance_manifest_sync_ready_count']}/{summary['competitive_target_identity_clearance_manifest_sync_awaiting_count']}/{summary['competitive_target_identity_clearance_manifest_sync_blocked_count']}/{summary['competitive_target_identity_clearance_manifest_sync_synced_count']}` changed/applied `{summary['competitive_target_identity_clearance_manifest_sync_changed_count']}/{summary['competitive_target_identity_clearance_manifest_sync_applied_count']}`",
        f"- competitive target identity clearance workorder audit: `{summary['competitive_target_identity_clearance_workorder_audit_status'] or '-'}` pass/blocked/total `{summary['competitive_target_identity_clearance_workorder_audit_pass_count']}/{summary['competitive_target_identity_clearance_workorder_audit_blocked_count']}/{summary['competitive_target_identity_clearance_workorder_audit_target_count']}` prediction/native/provenance/evidence/manifest `{summary['competitive_target_identity_clearance_workorder_audit_prediction_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_count']}/{summary['competitive_target_identity_clearance_workorder_audit_provenance_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_count']}/{summary['competitive_target_identity_clearance_workorder_audit_manifest_count']}` prediction protein-atoms/coordinate-valid `{summary['competitive_target_identity_clearance_workorder_audit_prediction_protein_atom_count']}/{summary['competitive_target_identity_clearance_workorder_audit_prediction_coordinate_valid_count']}` identity discovery blocked/cleared `{summary['competitive_target_identity_clearance_workorder_audit_identity_discovery_blocked_count']}/{summary['competitive_target_identity_clearance_workorder_audit_identity_discovery_cleared_count']}` native protein-atoms/coordinate-valid `{summary['competitive_target_identity_clearance_workorder_audit_native_protein_atom_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_coordinate_valid_count']}` evidence verified/content-blocked/blocked/waiting `{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_verified_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_content_blocked_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_blocked_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_waiting_count']}` manifest/provenance matched/mismatches `{summary['competitive_target_identity_clearance_workorder_audit_manifest_provenance_matched_count']}/{summary['competitive_target_identity_clearance_workorder_audit_manifest_provenance_mismatch_count']}` native/prediction distinct/same/waiting `{summary['competitive_target_identity_clearance_workorder_audit_native_prediction_distinct_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_prediction_same_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_prediction_waiting_count']}`",
        f"- competitive target identity clearance action board: `{summary['competitive_target_identity_clearance_action_board_status'] or '-'}` actions/open `{summary['competitive_target_identity_clearance_action_board_action_count']}/{summary['competitive_target_identity_clearance_action_board_open_count']}` native/evidence/provenance/manifest `{summary['competitive_target_identity_clearance_action_board_native_count']}/{summary['competitive_target_identity_clearance_action_board_evidence_count']}/{summary['competitive_target_identity_clearance_action_board_provenance_count']}/{summary['competitive_target_identity_clearance_action_board_manifest_count']}`",
        f"- competitive target identity clearance action bundle: `{summary['competitive_target_identity_clearance_action_bundle_status'] or '-'}` targets/actions/open `{summary['competitive_target_identity_clearance_action_bundle_target_count']}/{summary['competitive_target_identity_clearance_action_bundle_action_count']}/{summary['competitive_target_identity_clearance_action_bundle_open_count']}` files/folders `{summary['competitive_target_identity_clearance_action_bundle_file_count']}/{summary['competitive_target_identity_clearance_action_bundle_folder_count']}` native/evidence/provenance/manifest `{summary['competitive_target_identity_clearance_action_bundle_native_count']}/{summary['competitive_target_identity_clearance_action_bundle_evidence_count']}/{summary['competitive_target_identity_clearance_action_bundle_provenance_count']}/{summary['competitive_target_identity_clearance_action_bundle_manifest_count']}`",
        f"- competitive target identity clearance promotion: `{summary['competitive_target_identity_clearance_promotion_status'] or '-'}` rows/promoted/blocked `{summary['competitive_target_identity_clearance_promotion_row_count']}/{summary['competitive_target_identity_clearance_promotion_promoted_count']}/{summary['competitive_target_identity_clearance_promotion_blocked_count']}` ready/audit-pass `{summary['competitive_target_identity_clearance_promotion_ready_count']}/{summary['competitive_target_identity_clearance_promotion_audit_pass_count']}`",
        f"- competitive target identity clearance intake staging: `{summary['competitive_target_identity_clearance_intake_staging_status'] or '-'}` promoted/staged/blocked `{summary['competitive_target_identity_clearance_intake_staging_promoted_count']}/{summary['competitive_target_identity_clearance_intake_staging_staged_count']}/{summary['competitive_target_identity_clearance_intake_staging_blocked_count']}` open slots/candidate rows `{summary['competitive_target_identity_clearance_intake_staging_open_slot_count']}/{summary['competitive_target_identity_clearance_intake_staging_candidate_row_count']}`",
        f"- competitive target identity clearance candidate intake sync: `{summary['competitive_target_identity_clearance_candidate_intake_sync_status'] or '-'}` rows ready/waiting/blocked/applied `{summary['competitive_target_identity_clearance_candidate_intake_sync_row_count']}/{summary['competitive_target_identity_clearance_candidate_intake_sync_ready_count']}/{summary['competitive_target_identity_clearance_candidate_intake_sync_waiting_count']}/{summary['competitive_target_identity_clearance_candidate_intake_sync_blocked_count']}/{summary['competitive_target_identity_clearance_candidate_intake_sync_applied_count']}`",
        f"- competitive target identity clearance cycle: `{summary['competitive_target_identity_clearance_cycle_status'] or '-'}` stages `{summary['competitive_target_identity_clearance_cycle_ready_stage_count']}/{summary['competitive_target_identity_clearance_cycle_blocked_stage_count']}/{summary['competitive_target_identity_clearance_cycle_stage_count']}` sync/audit/promotion `{summary['competitive_target_identity_clearance_cycle_manifest_sync_status'] or '-'}`/`{summary['competitive_target_identity_clearance_cycle_audit_status'] or '-'}`/`{summary['competitive_target_identity_clearance_cycle_promotion_status'] or '-'}` staged `{summary['competitive_target_identity_clearance_cycle_staged_count']}`",
        f"- competitive identity cycle: `{summary['competitive_identity_cycle_status'] or '-'}` stages `{summary['competitive_identity_cycle_ready_stage_count']}/{summary['competitive_identity_cycle_blocked_stage_count']}/{summary['competitive_identity_cycle_stage_count']}` sync `{summary['competitive_identity_cycle_sync_status'] or '-'}` ready/awaiting `{summary['competitive_identity_cycle_sync_ready_to_sync_count']}/{summary['competitive_identity_cycle_sync_awaiting_count']}` missing fields `{summary['competitive_identity_cycle_missing_field_count']}` readiness `{summary['competitive_identity_cycle_readiness_gate_status'] or '-'}`",
        f"- competitive file source plan: `{summary['competitive_file_source_plan_status'] or '-'}` actions `{summary['competitive_file_source_plan_action_count']}` waiting identity/source `{summary['competitive_file_source_plan_waiting_on_identity_count']}/{summary['competitive_file_source_plan_awaiting_source_path_count']}` ready/imported/blocked `{summary['competitive_file_source_plan_ready_for_import_count']}/{summary['competitive_file_source_plan_already_imported_count']}/{summary['competitive_file_source_plan_blocked_count']}`",
        f"- competitive value entry plan: `{summary['competitive_value_entry_plan_status'] or '-'}` actions `{summary['competitive_value_entry_plan_action_count']}` target/provenance/calibration `{summary['competitive_value_entry_plan_target_identity_count']}/{summary['competitive_value_entry_plan_provenance_count']}/{summary['competitive_value_entry_plan_calibration_count']}` waiting identity/value/clearance/ref `{summary['competitive_value_entry_plan_waiting_on_identity_count']}/{summary['competitive_value_entry_plan_awaiting_value_count']}/{summary['competitive_value_entry_plan_awaiting_clearance_count']}/{summary['competitive_value_entry_plan_awaiting_ref_count']}` ready/blocked `{summary['competitive_value_entry_plan_ready_for_import_count']}/{summary['competitive_value_entry_plan_blocked_count']}`",
        f"- competitive execution board: `{summary['competitive_execution_board_status'] or '-'}` rows `{summary['competitive_execution_board_row_count']}` identity/apply/file/value/import/blocked `{summary['competitive_execution_board_awaiting_identity_row_count']}/{summary['competitive_execution_board_ready_for_identity_apply_row_count']}/{summary['competitive_execution_board_awaiting_file_source_row_count']}/{summary['competitive_execution_board_awaiting_value_row_count']}/{summary['competitive_execution_board_ready_for_evidence_import_row_count']}/{summary['competitive_execution_board_blocked_row_count']}` ready/blocked actions `{summary['competitive_execution_board_total_ready_action_count']}/{summary['competitive_execution_board_total_blocked_action_count']}`",
        f"- competitive readiness gate: `{summary['competitive_readiness_gate_status'] or '-'}` gates pass/blocked `{summary['competitive_readiness_gate_pass_count']}/{summary['competitive_readiness_gate_blocked_count']}` first blocked `{summary['competitive_readiness_gate_first_blocked_gate_id'] or '-'}` `{summary['competitive_readiness_gate_first_blocked_status'] or '-'}`",
        f"- competitive value ledgers: `{summary['competitive_value_ledger_status'] or '-'}` ledgers/actions `{summary['competitive_value_ledger_count']}/{summary['competitive_value_ledger_action_count']}` ready/awaiting `{summary['competitive_value_ledger_ready_for_intake_count']}/{summary['competitive_value_ledger_awaiting_value_count']}`",
        f"- competitive evidence intake: `{summary['competitive_evidence_intake_status'] or '-'}` actions `{summary['competitive_evidence_intake_action_count']}` patch candidates `{summary['competitive_evidence_intake_patch_candidate_count']}` awaiting files/values `{summary['competitive_evidence_intake_awaiting_file_count']}/{summary['competitive_evidence_intake_awaiting_value_count']}`",
        f"- competitive row_fill patch gate: `{summary['competitive_patch_gate_status'] or '-'}` actions `{summary['competitive_patch_gate_action_count']}` ready/awaiting/conflicts `{summary['competitive_patch_gate_ready_to_patch_count']}/{summary['competitive_patch_gate_awaiting_evidence_count']}/{summary['competitive_patch_gate_conflict_count']}`",
        f"- competitive row_fill apply plan: `{summary['competitive_apply_plan_status'] or '-'}` actions `{summary['competitive_apply_plan_action_count']}` planned/awaiting/applied `{summary['competitive_apply_plan_planned_patch_count']}/{summary['competitive_apply_plan_awaiting_evidence_count']}/{summary['competitive_apply_plan_applied_count']}`",
        f"- competitive operator template: `{summary['competitive_operator_template_status'] or '-'}` rows `{summary['competitive_operator_template_ready_count']}/{summary['competitive_operator_template_row_count']}`",
        f"- competitive row_fill candidates: `{summary['competitive_operator_template_row_fill_count']}`",
        f"- competitive operator preflight: `{summary['competitive_operator_preflight_status'] or '-'}` rows `{summary['competitive_operator_preflight_ready_count']}/{summary['competitive_operator_preflight_row_count']}`",
        f"- required files present/missing: `{summary['present_file_count']}/{summary['missing_file_count']}`",
        f"- current proven level: `{summary['current_proven_level'] or '-'}`",
        f"- next unclosed level: `{summary['next_unclosed_level'] or '-'}`",
        f"- first operator action: `{summary['first_operator_input_action_id'] or '-'}`",
        f"- first operator blockers: `{summary['first_operator_input_blockers'] or '-'}`",
        f"- first fill action: {summary['first_operator_fill_action'] or '-'}",
        "",
        "## Workbench Artifacts",
        "",
        "| artifact | status | ready | blocked | total | path | next action | blockers |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['status']}` | {row['ready_count']} | {row['blocked_count']} | "
            f"{row['total_count']} | `{row['path']}` | {row['next_action'] or '-'} | `{row['blockers'] or '-'}` |"
        )
    lines.extend(
        [
            "",
            "## Current Target Folders",
            "",
            "| target | status | protein/complex | folder |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["target_rows"]:
        lines.append(
            f"| `{row.get('target_id', '')}` | `{row.get('folder_status', '')}` | "
            f"{row.get('protein_name', '')} | `{row.get('folder_path', '')}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 local workbench index.")
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
    parser.add_argument("--target-object-folder-audit-json", default=DEFAULT_TARGET_OBJECT_FOLDER_AUDIT_JSON)
    parser.add_argument("--target-object-viewer-smoke-json", default=DEFAULT_TARGET_OBJECT_VIEWER_SMOKE_JSON)
    parser.add_argument("--target-object-model-review-json", default=DEFAULT_TARGET_OBJECT_MODEL_REVIEW_JSON)
    parser.add_argument("--protein-object-library-json", default=DEFAULT_PROTEIN_OBJECT_LIBRARY_JSON)
    parser.add_argument("--raw-ranked-model-quarantine-json", default=DEFAULT_RAW_RANKED_MODEL_QUARANTINE_JSON)
    parser.add_argument("--win-gap-closure-json", default=DEFAULT_WIN_GAP_CLOSURE_JSON)
    parser.add_argument("--win-tier-goal-scorecard-json", default=DEFAULT_WIN_TIER_GOAL_SCORECARD_JSON)
    parser.add_argument("--input-scaffold-json", default=DEFAULT_INPUT_SCAFFOLD_JSON)
    parser.add_argument("--input-inventory-json", default=DEFAULT_INPUT_INVENTORY_JSON)
    parser.add_argument("--operator-dashboard-json", default=DEFAULT_OPERATOR_DASHBOARD_JSON)
    parser.add_argument("--historical-identity-seed-inventory-json", default=DEFAULT_HISTORICAL_IDENTITY_SEED_INVENTORY_JSON)
    parser.add_argument("--historical-identity-seed-clearance-json", default=DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_JSON)
    parser.add_argument(
        "--historical-identity-seed-clearance-action-bundle-json",
        default=DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_ACTION_BUNDLE_JSON,
    )
    parser.add_argument("--sidechain-native-benchmark-json", default=DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON)
    parser.add_argument("--competitive-batch-json", default=DEFAULT_COMPETITIVE_BATCH_JSON)
    parser.add_argument("--competitive-row-fill-status-json", default=DEFAULT_COMPETITIVE_ROW_FILL_STATUS_JSON)
    parser.add_argument("--competitive-row-fill-worklist-json", default=DEFAULT_COMPETITIVE_ROW_FILL_WORKLIST_JSON)
    parser.add_argument("--competitive-evidence-dropzone-json", default=DEFAULT_COMPETITIVE_EVIDENCE_DROPZONE_JSON)
    parser.add_argument("--competitive-evidence-import-json", default=DEFAULT_COMPETITIVE_EVIDENCE_IMPORT_JSON)
    parser.add_argument("--competitive-evidence-round-json", default=DEFAULT_COMPETITIVE_EVIDENCE_ROUND_JSON)
    parser.add_argument("--competitive-unlock-priority-json", default=DEFAULT_COMPETITIVE_UNLOCK_PRIORITY_JSON)
    parser.add_argument(
        "--competitive-identity-unlock-kit-json",
        "--competitive-identity-unlock-json",
        dest="competitive_identity_unlock_json",
        default=DEFAULT_COMPETITIVE_IDENTITY_UNLOCK_KIT_JSON,
    )
    parser.add_argument("--competitive-identity-round-json", default=DEFAULT_COMPETITIVE_IDENTITY_UNLOCK_ROUND_JSON)
    parser.add_argument("--competitive-identity-intake-json", default=DEFAULT_COMPETITIVE_IDENTITY_INTAKE_BUNDLE_JSON)
    parser.add_argument("--competitive-identity-sync-json", default=DEFAULT_COMPETITIVE_IDENTITY_INTAKE_SYNC_JSON)
    parser.add_argument("--competitive-identity-candidate-json", default=DEFAULT_COMPETITIVE_IDENTITY_CANDIDATE_JSON)
    parser.add_argument("--competitive-identity-source-repair-json", default=DEFAULT_COMPETITIVE_IDENTITY_SOURCE_REPAIR_JSON)
    parser.add_argument("--competitive-floor-unblock-map-json", default=DEFAULT_COMPETITIVE_FLOOR_UNBLOCK_MAP_JSON)
    parser.add_argument(
        "--competitive-target-identity-discovery-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_DISCOVERY_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-queue-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_QUEUE_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-workorder-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_WORKORDER_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-operator-intake-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_OPERATOR_INTAKE_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-native-candidate-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_NATIVE_CANDIDATE_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-adjudication-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_ADJUDICATION_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-queue-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_QUEUE_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-source-repair-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SOURCE_REPAIR_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-scorecard-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SCORECARD_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-workorder-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_WORKORDER_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-workorder-audit-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_WORKORDER_AUDIT_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-pickup-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_PICKUP_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-duplicate-resolution-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DUPLICATE_RESOLUTION_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-decision-bundle-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DECISION_BUNDLE_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-replacement-decision-preflight-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DECISION_PREFLIGHT_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-manifest-sync-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_MANIFEST_SYNC_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-workorder-audit-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_WORKORDER_AUDIT_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-action-board-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_ACTION_BOARD_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-action-bundle-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_ACTION_BUNDLE_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-promotion-plan-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_PROMOTION_PLAN_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-intake-staging-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_INTAKE_STAGING_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-candidate-intake-sync-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_CANDIDATE_INTAKE_SYNC_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-cycle-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_CYCLE_JSON,
    )
    parser.add_argument("--competitive-identity-cycle-json", default=DEFAULT_COMPETITIVE_IDENTITY_CYCLE_JSON)
    parser.add_argument("--competitive-file-source-plan-json", default=DEFAULT_COMPETITIVE_FILE_SOURCE_PLAN_JSON)
    parser.add_argument("--competitive-value-entry-plan-json", default=DEFAULT_COMPETITIVE_VALUE_ENTRY_PLAN_JSON)
    parser.add_argument("--competitive-execution-board-json", default=DEFAULT_COMPETITIVE_EXECUTION_BOARD_JSON)
    parser.add_argument("--competitive-readiness-gate-json", default=DEFAULT_COMPETITIVE_READINESS_GATE_JSON)
    parser.add_argument("--competitive-value-ledger-json", default=DEFAULT_COMPETITIVE_VALUE_LEDGER_JSON)
    parser.add_argument("--competitive-evidence-intake-json", default=DEFAULT_COMPETITIVE_EVIDENCE_INTAKE_JSON)
    parser.add_argument("--competitive-patch-gate-json", default=DEFAULT_COMPETITIVE_PATCH_GATE_JSON)
    parser.add_argument("--competitive-apply-plan-json", default=DEFAULT_COMPETITIVE_APPLY_PLAN_JSON)
    parser.add_argument("--competitive-operator-template-json", default=DEFAULT_COMPETITIVE_OPERATOR_TEMPLATE_JSON)
    parser.add_argument("--competitive-operator-preflight-json", default=DEFAULT_COMPETITIVE_OPERATOR_PREFLIGHT_JSON)
    parser.add_argument("--data-bundle-json", default=DEFAULT_DATA_BUNDLE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
