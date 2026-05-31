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
DEFAULT_PROTEIN_OBJECT_LIBRARY_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_protein_object_library_completion_audit_current.json"
)
DEFAULT_PROTEIN_OBJECT_LIBRARY_NAVIGATION_CATALOG_JSON = (
    "casp17/casp17_protein_object_library_navigation_catalog_current.json"
)
DEFAULT_RAW_RANKED_MODEL_QUARANTINE_JSON = "casp17/casp17_raw_ranked_model_quarantine_audit_current.json"
DEFAULT_WIN_GAP_CLOSURE_JSON = "runs/casp17_win_gap_closure_packet_current.json"
DEFAULT_WIN_TIER_GOAL_SCORECARD_JSON = "runs/casp17_win_tier_goal_scorecard_current.json"
DEFAULT_WIN_TIER_METRIC_SURFACE_CONTRACT_JSON = "casp17/casp17_win_tier_metric_surface_contract_current.json"
DEFAULT_WIN_TIER_CRITICAL_PATH_BOARD_JSON = "casp17/casp17_win_tier_critical_path_board_current.json"
DEFAULT_ORGANIC_LIGAND_SLOT_CANDIDATE_PACKET_JSON = (
    "casp17/casp17_organic_ligand_slot_candidate_packet_current.json"
)
DEFAULT_ORGANIC_LIGAND_SLOT_PROMOTION_ACTION_BOARD_JSON = (
    "casp17/casp17_organic_ligand_slot_promotion_action_board_current.json"
)
DEFAULT_ACTIVE_SCOPE_DECISION_JSON = "casp17/casp17_active_scope_decision_current.json"
DEFAULT_ORGANIZER_NOTICE_PACKET_JSON = "casp17/casp17_organizer_notice_packet_current.json"
DEFAULT_MASSIVEFOLD_EXTERNAL_POOL_INTAKE_JSON = "casp17/casp17_massivefold_external_pool_intake_current.json"
DEFAULT_RNA_HYBRID_MASSIVEFOLD_PRIORITY_QUEUE_JSON = (
    "casp17/casp17_rna_hybrid_massivefold_priority_queue_current.json"
)
DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_PRIORITY_QUEUE_JSON = (
    "casp17/casp17_protein_complex_massivefold_priority_queue_current.json"
)
DEFAULT_MASSIVEFOLD_ACQUISITION_VERIFICATION_BOARD_JSON = (
    "casp17/casp17_massivefold_acquisition_verification_board_current.json"
)
DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_ACQUISITION_VERIFICATION_BOARD_JSON = (
    "casp17/casp17_protein_complex_massivefold_acquisition_verification_board_current.json"
)
DEFAULT_MASSIVEFOLD_MODEL_POOL_INDEX_JSON = "casp17/casp17_massivefold_model_pool_index_current.json"
DEFAULT_MASSIVEFOLD_REPRESENTATIVE_VIEWER_PACKET_JSON = (
    "casp17/casp17_massivefold_representative_viewer_packet_current.json"
)
DEFAULT_MASSIVEFOLD_REPRESENTATIVE_RERANK_PACKET_JSON = (
    "casp17/casp17_massivefold_representative_rerank_packet_current.json"
)
DEFAULT_MASSIVEFOLD_RNA_MODEL_SELECTION_COVERAGE_JSON = (
    "casp17/casp17_massivefold_rna_model_selection_coverage_current.json"
)
DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_MODEL_SELECTION_COVERAGE_JSON = (
    "casp17/casp17_protein_complex_massivefold_model_selection_coverage_current.json"
)
DEFAULT_CAPRI_ROUND65_READINESS_JSON = "casp17/capri_round65/capri_round65_readiness_current.json"
DEFAULT_CAPRI_ROUND65_FORMAT_PREFLIGHT_JSON = "casp17/capri_round65/capri_round65_format_preflight_current.json"
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
DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_FIELD_BOARD_JSON = (
    "casp17/casp17_historical_identity_seed_clearance_field_board_current.json"
)
DEFAULT_HISTORICAL_SEED_NO_LEAK_PROVENANCE_DOSSIERS_JSON = (
    "casp17/casp17_historical_seed_no_leak_provenance_dossiers_current.json"
)
DEFAULT_HISTORICAL_SEED_NO_LEAK_GAP_REPAIR_PLAN_JSON = (
    "casp17/casp17_historical_seed_no_leak_gap_repair_plan_current.json"
)
DEFAULT_HISTORICAL_SEED_CURRENT_TARGET_PREFILL_JSON = (
    "casp17/casp17_historical_seed_current_target_prefill_current.json"
)
DEFAULT_HISTORICAL_SEED_NATIVE_AUTHORITY_AUDIT_JSON = (
    "casp17/casp17_historical_seed_native_authority_audit_current.json"
)
DEFAULT_HISTORICAL_SEED_NATIVE_REPLACEMENT_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_native_replacement_candidates_current.json"
)
DEFAULT_HISTORICAL_SEED_COMPLEX_SOURCE_AUTHORITY_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_complex_source_authority_candidates_current.json"
)
DEFAULT_HISTORICAL_SEED_CHRONOLOGY_CANDIDATE_BOARD_JSON = (
    "casp17/casp17_historical_seed_chronology_candidate_board_current.json"
)
DEFAULT_HISTORICAL_SEED_AUTHORITATIVE_CHRONOLOGY_AUDIT_JSON = (
    "casp17/casp17_historical_seed_authoritative_chronology_audit_current.json"
)
DEFAULT_HISTORICAL_SEED_LANE_DECISION_PACKET_JSON = (
    "casp17/casp17_historical_seed_lane_decision_packet_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_QUEUE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_queue_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_INTAKE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_DROPZONES_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_ACTION_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_action_board_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_QUALITY_AUDIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_quality_audit_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_IMPORT_GATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_evidence_import_gate_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_OPERATOR_VALUE_GATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_OPERATOR_ACTION_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_operator_action_board_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_PROMOTION_GATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_promotion_gate_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_CYCLE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_cycle_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_LOCAL_CANDIDATE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_CANDIDATE_REPAIR_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_REPAIR_FEASIBILITY_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_SOURCE_ROUTE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.json"
)
DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_OFFICIAL_ARCHIVE_SOURCE_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_current.json"
)
DEFAULT_HISTORICAL_SEED_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON = (
    "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
)
DEFAULT_STRICT_BLIND_FIRST_SLOT_SOURCE_BRIDGE_JSON = (
    "casp17/casp17_strict_blind_first_slot_source_bridge_current.json"
)
DEFAULT_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_AUDIT_JSON = (
    "casp17/casp17_strict_blind_internal_prediction_source_audit_current.json"
)
DEFAULT_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_GATE_JSON = (
    "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
)
DEFAULT_STRICT_BLIND_SOURCE_GATE_FIELD_BOARD_JSON = (
    "casp17/casp17_strict_blind_source_gate_field_board_current.json"
)
DEFAULT_STRICT_BLIND_SOURCE_GATE_OPERATOR_PACKET_JSON = (
    "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
)
DEFAULT_STRICT_BLIND_SOURCE_GATE_SOURCE_REQUEST_PACKET_JSON = (
    "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
)
DEFAULT_STRICT_BLIND_SOURCE_REQUEST_FULFILLMENT_GATE_JSON = (
    "casp17/casp17_strict_blind_source_request_fulfillment_gate_current.json"
)
DEFAULT_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_FILL_WORKLIST_JSON = (
    "casp17/casp17_strict_blind_source_request_operator_fill_worklist_current.json"
)
DEFAULT_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_SYNC_PLAN_JSON = (
    "casp17/casp17_strict_blind_source_request_operator_sync_plan_current.json"
)
DEFAULT_STRICT_BLIND_SOURCE_REQUEST_CLOSURE_BOARD_JSON = (
    "casp17/casp17_strict_blind_source_request_closure_board_current.json"
)
DEFAULT_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_APPLY_PLAN_JSON = (
    "casp17/casp17_strict_blind_internal_prediction_source_apply_plan_current.json"
)
DEFAULT_STRICT_BLIND_FIRST_SLOT_CLOSURE_KIT_JSON = (
    "casp17/casp17_strict_blind_first_slot_closure_kit_current.json"
)
DEFAULT_STRICT_BLIND_BATCH_CLOSURE_RUNWAY_JSON = (
    "casp17/casp17_strict_blind_batch_closure_runway_current.json"
)
DEFAULT_HISTORICAL_SEED_ABLATION_CANDIDATE_MANIFESTS_JSON = (
    "casp17/casp17_historical_seed_ablation_candidate_manifests_current.json"
)
DEFAULT_HISTORICAL_SEED_ABLATION_GAP_REPAIR_PLAN_JSON = (
    "casp17/casp17_historical_seed_ablation_gap_repair_plan_current.json"
)
DEFAULT_HISTORICAL_SEED_TOP5_CANDIDATE_POOLS_JSON = (
    "casp17/casp17_historical_seed_top5_candidate_pools_current.json"
)
DEFAULT_HISTORICAL_SEED_INTERNAL_SCORE_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_internal_score_candidates_current.json"
)
DEFAULT_HISTORICAL_SEED_NATIVE_ORACLE_METRIC_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_native_oracle_metric_candidates_current.json"
)
DEFAULT_HISTORICAL_SEED_CALIBRATION_CANDIDATE_LEDGERS_JSON = (
    "casp17/casp17_historical_seed_calibration_candidate_ledgers_current.json"
)
DEFAULT_HISTORICAL_SEED_CALIBRATION_FIELD_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_calibration_field_candidates_current.json"
)
DEFAULT_HISTORICAL_SEED_CLEARANCE_FILL_CANDIDATE_PACKET_JSON = (
    "casp17/casp17_historical_seed_clearance_fill_candidate_packet_current.json"
)
DEFAULT_HISTORICAL_SEED_CLEARANCE_EXECUTION_BOARD_JSON = (
    "casp17/casp17_historical_seed_clearance_execution_board_current.json"
)
DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_OPERATOR_KIT_JSON = (
    "casp17/casp17_historical_seed_first_clearance_operator_kit_current.json"
)
DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_GATE_JSON = (
    "casp17/casp17_historical_seed_first_clearance_no_leak_gate_current.json"
)
DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_PACKET_JSON = (
    "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_packet_current.json"
)
DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_REVIEW_GATE_JSON = (
    "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_review_gate_current.json"
)
DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_SYNC_PLAN_JSON = (
    "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_sync_plan_current.json"
)
DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_CLOSURE_BOARD_JSON = (
    "casp17/casp17_historical_seed_first_clearance_closure_board_current.json"
)
DEFAULT_HISTORICAL_SEED_CLEARANCE_TO_IDENTITY_INTAKE_SYNC_JSON = (
    "casp17/casp17_historical_seed_clearance_to_identity_intake_sync_current.json"
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
    protein_object_library_completion_audit_payload = _read_json(
        args.protein_object_library_completion_audit_json
    )
    protein_object_library_navigation_catalog_payload = _read_json(
        args.protein_object_library_navigation_catalog_json
    )
    raw_ranked_model_quarantine_payload = _read_json(args.raw_ranked_model_quarantine_json)
    closure_payload = _read_json(args.win_gap_closure_json)
    goal_scorecard_payload = _read_json(args.win_tier_goal_scorecard_json)
    win_tier_metric_surface_contract_payload = _read_json(args.win_tier_metric_surface_contract_json)
    win_tier_critical_path_board_payload = _read_json(args.win_tier_critical_path_board_json)
    organic_ligand_slot_candidate_packet_payload = _read_json(
        args.organic_ligand_slot_candidate_packet_json
    )
    organic_ligand_slot_promotion_action_board_payload = _read_json(
        args.organic_ligand_slot_promotion_action_board_json
    )
    active_scope_decision_payload = _read_json(args.active_scope_decision_json)
    organizer_notice_payload = _read_json(args.organizer_notice_packet_json)
    massivefold_external_pool_intake_payload = _read_json(args.massivefold_external_pool_intake_json)
    rna_hybrid_massivefold_priority_queue_payload = _read_json(
        args.rna_hybrid_massivefold_priority_queue_json
    )
    protein_complex_massivefold_priority_queue_payload = _read_json(
        args.protein_complex_massivefold_priority_queue_json
    )
    massivefold_acquisition_verification_board_payload = _read_json(
        args.massivefold_acquisition_verification_board_json
    )
    protein_complex_massivefold_acquisition_verification_board_payload = _read_json(
        args.protein_complex_massivefold_acquisition_verification_board_json
    )
    massivefold_model_pool_index_payload = _read_json(args.massivefold_model_pool_index_json)
    massivefold_representative_viewer_packet_payload = _read_json(
        args.massivefold_representative_viewer_packet_json
    )
    massivefold_representative_rerank_packet_payload = _read_json(
        args.massivefold_representative_rerank_packet_json
    )
    massivefold_rna_model_selection_coverage_payload = _read_json(
        args.massivefold_rna_model_selection_coverage_json
    )
    protein_complex_massivefold_model_selection_coverage_payload = _read_json(
        args.protein_complex_massivefold_model_selection_coverage_json
    )
    capri_round65_readiness_payload = _read_json(args.capri_round65_readiness_json)
    capri_round65_format_preflight_payload = _read_json(args.capri_round65_format_preflight_json)
    scaffold_payload = _read_json(args.input_scaffold_json)
    inventory_payload = _read_json(args.input_inventory_json)
    dashboard_payload = _read_json(args.operator_dashboard_json)
    historical_identity_seed_inventory_payload = _read_json(args.historical_identity_seed_inventory_json)
    historical_identity_seed_clearance_payload = _read_json(args.historical_identity_seed_clearance_json)
    historical_identity_seed_clearance_action_bundle_payload = _read_json(
        args.historical_identity_seed_clearance_action_bundle_json
    )
    historical_identity_seed_clearance_field_board_payload = _read_json(
        args.historical_identity_seed_clearance_field_board_json
    )
    historical_seed_no_leak_provenance_dossiers_payload = _read_json(
        args.historical_seed_no_leak_provenance_dossiers_json
    )
    historical_seed_no_leak_gap_repair_plan_payload = _read_json(
        args.historical_seed_no_leak_gap_repair_plan_json
    )
    historical_seed_current_target_prefill_payload = _read_json(
        args.historical_seed_current_target_prefill_json
    )
    historical_seed_native_authority_audit_payload = _read_json(
        args.historical_seed_native_authority_audit_json
    )
    historical_seed_native_replacement_candidates_payload = _read_json(
        args.historical_seed_native_replacement_candidates_json
    )
    historical_seed_complex_source_authority_candidates_payload = _read_json(
        args.historical_seed_complex_source_authority_candidates_json
    )
    historical_seed_chronology_candidate_board_payload = _read_json(
        args.historical_seed_chronology_candidate_board_json
    )
    historical_seed_authoritative_chronology_audit_payload = _read_json(
        args.historical_seed_authoritative_chronology_audit_json
    )
    historical_seed_lane_decision_packet_payload = _read_json(
        args.historical_seed_lane_decision_packet_json
    )
    historical_seed_strict_blind_replacement_queue_payload = _read_json(
        args.historical_seed_strict_blind_replacement_queue_json
    )
    historical_seed_strict_blind_replacement_intake_payload = _read_json(
        args.historical_seed_strict_blind_replacement_intake_json
    )
    historical_seed_strict_blind_replacement_evidence_dropzones_payload = _read_json(
        args.historical_seed_strict_blind_replacement_evidence_dropzones_json
    )
    historical_seed_strict_blind_replacement_evidence_action_board_payload = _read_json(
        args.historical_seed_strict_blind_replacement_evidence_action_board_json
    )
    historical_seed_strict_blind_replacement_evidence_quality_audit_payload = _read_json(
        args.historical_seed_strict_blind_replacement_evidence_quality_audit_json
    )
    historical_seed_strict_blind_replacement_evidence_import_gate_payload = _read_json(
        args.historical_seed_strict_blind_replacement_evidence_import_gate_json
    )
    historical_seed_strict_blind_replacement_operator_value_gate_payload = _read_json(
        args.historical_seed_strict_blind_replacement_operator_value_gate_json
    )
    historical_seed_strict_blind_replacement_operator_action_board_payload = _read_json(
        args.historical_seed_strict_blind_replacement_operator_action_board_json
    )
    historical_seed_strict_blind_replacement_promotion_gate_payload = _read_json(
        args.historical_seed_strict_blind_replacement_promotion_gate_json
    )
    historical_seed_strict_blind_replacement_cycle_payload = _read_json(
        args.historical_seed_strict_blind_replacement_cycle_json
    )
    historical_seed_strict_blind_replacement_first_slot_kit_payload = _read_json(
        args.historical_seed_strict_blind_replacement_first_slot_kit_json
    )
    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_payload = _read_json(
        args.historical_seed_strict_blind_replacement_first_slot_local_candidate_board_json
    )
    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_payload = _read_json(
        args.historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_json
    )
    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_payload = _read_json(
        args.historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_json
    )
    historical_seed_strict_blind_replacement_first_slot_source_route_board_payload = _read_json(
        args.historical_seed_strict_blind_replacement_first_slot_source_route_board_json
    )
    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_payload = _read_json(
        args.historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_json
    )
    historical_seed_official_archive_baseline_lane_payload = _read_json(
        args.historical_seed_official_archive_baseline_lane_json
    )
    strict_blind_first_slot_source_bridge_payload = _read_json(
        args.strict_blind_first_slot_source_bridge_json
    )
    strict_blind_internal_prediction_source_audit_payload = _read_json(
        args.strict_blind_internal_prediction_source_audit_json
    )
    strict_blind_internal_prediction_source_gate_payload = _read_json(
        args.strict_blind_internal_prediction_source_gate_json
    )
    strict_blind_source_gate_field_board_payload = _read_json(
        args.strict_blind_source_gate_field_board_json
    )
    strict_blind_source_gate_operator_packet_payload = _read_json(
        args.strict_blind_source_gate_operator_packet_json
    )
    strict_blind_source_gate_source_request_packet_payload = _read_json(
        args.strict_blind_source_gate_source_request_packet_json
    )
    strict_blind_source_request_fulfillment_gate_payload = _read_json(
        args.strict_blind_source_request_fulfillment_gate_json
    )
    strict_blind_source_request_operator_fill_worklist_payload = _read_json(
        args.strict_blind_source_request_operator_fill_worklist_json
    )
    strict_blind_source_request_operator_sync_plan_payload = _read_json(
        args.strict_blind_source_request_operator_sync_plan_json
    )
    strict_blind_source_request_closure_board_payload = _read_json(
        args.strict_blind_source_request_closure_board_json
    )
    strict_blind_internal_prediction_source_apply_plan_payload = _read_json(
        args.strict_blind_internal_prediction_source_apply_plan_json
    )
    strict_blind_first_slot_closure_kit_payload = _read_json(
        args.strict_blind_first_slot_closure_kit_json
    )
    strict_blind_batch_closure_runway_payload = _read_json(
        args.strict_blind_batch_closure_runway_json
    )
    historical_seed_ablation_candidate_manifests_payload = _read_json(
        args.historical_seed_ablation_candidate_manifests_json
    )
    historical_seed_ablation_gap_repair_plan_payload = _read_json(
        args.historical_seed_ablation_gap_repair_plan_json
    )
    historical_seed_top5_candidate_pools_payload = _read_json(
        args.historical_seed_top5_candidate_pools_json
    )
    historical_seed_internal_score_candidates_payload = _read_json(
        args.historical_seed_internal_score_candidates_json
    )
    historical_seed_native_oracle_metric_candidates_payload = _read_json(
        args.historical_seed_native_oracle_metric_candidates_json
    )
    historical_seed_calibration_candidate_ledgers_payload = _read_json(
        args.historical_seed_calibration_candidate_ledgers_json
    )
    historical_seed_calibration_field_candidates_payload = _read_json(
        args.historical_seed_calibration_field_candidates_json
    )
    historical_seed_clearance_fill_candidate_packet_payload = _read_json(
        args.historical_seed_clearance_fill_candidate_packet_json
    )
    historical_seed_clearance_execution_board_payload = _read_json(
        args.historical_seed_clearance_execution_board_json
    )
    historical_seed_first_clearance_operator_kit_payload = _read_json(
        args.historical_seed_first_clearance_operator_kit_json
    )
    historical_seed_first_clearance_no_leak_gate_payload = _read_json(
        args.historical_seed_first_clearance_no_leak_gate_json
    )
    historical_seed_first_clearance_no_leak_evidence_packet_payload = _read_json(
        args.historical_seed_first_clearance_no_leak_evidence_packet_json
    )
    historical_seed_first_clearance_no_leak_evidence_review_gate_payload = _read_json(
        args.historical_seed_first_clearance_no_leak_evidence_review_gate_json
    )
    historical_seed_first_clearance_no_leak_evidence_sync_plan_payload = _read_json(
        args.historical_seed_first_clearance_no_leak_evidence_sync_plan_json
    )
    historical_seed_first_clearance_closure_board_payload = _read_json(
        args.historical_seed_first_clearance_closure_board_json
    )
    historical_seed_clearance_to_identity_intake_sync_payload = _read_json(
        args.historical_seed_clearance_to_identity_intake_sync_json
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
    protein_object_library_completion_audit_summary = _summary(protein_object_library_completion_audit_payload)
    protein_object_library_navigation_catalog_summary = _summary(protein_object_library_navigation_catalog_payload)
    raw_ranked_model_quarantine_summary = _summary(raw_ranked_model_quarantine_payload)
    closure_summary = _summary(closure_payload)
    goal_scorecard_summary = _summary(goal_scorecard_payload)
    win_tier_metric_surface_contract_summary = _summary(win_tier_metric_surface_contract_payload)
    win_tier_critical_path_board_summary = _summary(win_tier_critical_path_board_payload)
    organic_ligand_slot_candidate_packet_summary = _summary(
        organic_ligand_slot_candidate_packet_payload
    )
    organic_ligand_slot_promotion_action_board_summary = _summary(
        organic_ligand_slot_promotion_action_board_payload
    )
    active_scope_decision_summary = _summary(active_scope_decision_payload)
    organizer_notice_summary = _summary(organizer_notice_payload)
    massivefold_external_pool_intake_summary = _summary(massivefold_external_pool_intake_payload)
    rna_hybrid_massivefold_priority_queue_summary = _summary(
        rna_hybrid_massivefold_priority_queue_payload
    )
    protein_complex_massivefold_priority_queue_summary = _summary(
        protein_complex_massivefold_priority_queue_payload
    )
    massivefold_acquisition_verification_board_summary = _summary(
        massivefold_acquisition_verification_board_payload
    )
    protein_complex_massivefold_acquisition_verification_board_summary = _summary(
        protein_complex_massivefold_acquisition_verification_board_payload
    )
    massivefold_model_pool_index_summary = _summary(massivefold_model_pool_index_payload)
    massivefold_representative_viewer_packet_summary = _summary(
        massivefold_representative_viewer_packet_payload
    )
    massivefold_representative_rerank_packet_summary = _summary(
        massivefold_representative_rerank_packet_payload
    )
    massivefold_rna_model_selection_coverage_summary = _summary(
        massivefold_rna_model_selection_coverage_payload
    )
    protein_complex_massivefold_model_selection_coverage_summary = _summary(
        protein_complex_massivefold_model_selection_coverage_payload
    )
    capri_round65_readiness_summary = _summary(capri_round65_readiness_payload)
    capri_round65_format_preflight_summary = _summary(capri_round65_format_preflight_payload)
    capri_round65_deferred = _text(
        active_scope_decision_summary.get("capri_round65_participation_status")
    ).startswith("deferred")
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
    historical_identity_seed_clearance_field_board_summary = _summary(
        historical_identity_seed_clearance_field_board_payload
    )
    historical_seed_no_leak_provenance_dossiers_summary = _summary(
        historical_seed_no_leak_provenance_dossiers_payload
    )
    historical_seed_no_leak_gap_repair_plan_summary = _summary(
        historical_seed_no_leak_gap_repair_plan_payload
    )
    historical_seed_current_target_prefill_summary = _summary(historical_seed_current_target_prefill_payload)
    historical_seed_native_authority_audit_summary = _summary(historical_seed_native_authority_audit_payload)
    historical_seed_native_replacement_candidates_summary = _summary(
        historical_seed_native_replacement_candidates_payload
    )
    historical_seed_complex_source_authority_candidates_summary = _summary(
        historical_seed_complex_source_authority_candidates_payload
    )
    historical_seed_chronology_candidate_board_summary = _summary(
        historical_seed_chronology_candidate_board_payload
    )
    historical_seed_authoritative_chronology_audit_summary = _summary(
        historical_seed_authoritative_chronology_audit_payload
    )
    historical_seed_lane_decision_packet_summary = _summary(historical_seed_lane_decision_packet_payload)
    historical_seed_strict_blind_replacement_queue_summary = _summary(
        historical_seed_strict_blind_replacement_queue_payload
    )
    historical_seed_strict_blind_replacement_intake_summary = _summary(
        historical_seed_strict_blind_replacement_intake_payload
    )
    historical_seed_strict_blind_replacement_evidence_dropzones_summary = _summary(
        historical_seed_strict_blind_replacement_evidence_dropzones_payload
    )
    historical_seed_strict_blind_replacement_evidence_action_board_summary = _summary(
        historical_seed_strict_blind_replacement_evidence_action_board_payload
    )
    historical_seed_strict_blind_replacement_evidence_quality_audit_summary = _summary(
        historical_seed_strict_blind_replacement_evidence_quality_audit_payload
    )
    historical_seed_strict_blind_replacement_evidence_import_gate_summary = _summary(
        historical_seed_strict_blind_replacement_evidence_import_gate_payload
    )
    historical_seed_strict_blind_replacement_operator_value_gate_summary = _summary(
        historical_seed_strict_blind_replacement_operator_value_gate_payload
    )
    historical_seed_strict_blind_replacement_operator_action_board_summary = _summary(
        historical_seed_strict_blind_replacement_operator_action_board_payload
    )
    historical_seed_strict_blind_replacement_promotion_gate_summary = _summary(
        historical_seed_strict_blind_replacement_promotion_gate_payload
    )
    historical_seed_strict_blind_replacement_cycle_summary = _summary(
        historical_seed_strict_blind_replacement_cycle_payload
    )
    historical_seed_strict_blind_replacement_first_slot_kit_summary = _summary(
        historical_seed_strict_blind_replacement_first_slot_kit_payload
    )
    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary = _summary(
        historical_seed_strict_blind_replacement_first_slot_local_candidate_board_payload
    )
    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary = _summary(
        historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_payload
    )
    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary = _summary(
        historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_payload
    )
    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary = _summary(
        historical_seed_strict_blind_replacement_first_slot_source_route_board_payload
    )
    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary = _summary(
        historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_payload
    )
    historical_seed_official_archive_baseline_lane_summary = _summary(
        historical_seed_official_archive_baseline_lane_payload
    )
    strict_blind_first_slot_source_bridge_summary = _summary(
        strict_blind_first_slot_source_bridge_payload
    )
    strict_blind_internal_prediction_source_audit_summary = _summary(
        strict_blind_internal_prediction_source_audit_payload
    )
    strict_blind_internal_prediction_source_gate_summary = _summary(
        strict_blind_internal_prediction_source_gate_payload
    )
    strict_blind_source_gate_field_board_summary = _summary(
        strict_blind_source_gate_field_board_payload
    )
    strict_blind_source_gate_operator_packet_summary = _summary(
        strict_blind_source_gate_operator_packet_payload
    )
    strict_blind_source_gate_source_request_packet_summary = _summary(
        strict_blind_source_gate_source_request_packet_payload
    )
    strict_blind_source_request_fulfillment_gate_summary = _summary(
        strict_blind_source_request_fulfillment_gate_payload
    )
    strict_blind_source_request_operator_fill_worklist_summary = _summary(
        strict_blind_source_request_operator_fill_worklist_payload
    )
    strict_blind_source_request_operator_sync_plan_summary = _summary(
        strict_blind_source_request_operator_sync_plan_payload
    )
    strict_blind_source_request_closure_board_summary = _summary(
        strict_blind_source_request_closure_board_payload
    )
    strict_blind_internal_prediction_source_apply_plan_summary = _summary(
        strict_blind_internal_prediction_source_apply_plan_payload
    )
    strict_blind_first_slot_closure_kit_summary = _summary(
        strict_blind_first_slot_closure_kit_payload
    )
    strict_blind_batch_closure_runway_summary = _summary(
        strict_blind_batch_closure_runway_payload
    )
    historical_seed_ablation_candidate_manifests_summary = _summary(
        historical_seed_ablation_candidate_manifests_payload
    )
    historical_seed_ablation_gap_repair_plan_summary = _summary(
        historical_seed_ablation_gap_repair_plan_payload
    )
    historical_seed_top5_candidate_pools_summary = _summary(historical_seed_top5_candidate_pools_payload)
    historical_seed_internal_score_candidates_summary = _summary(
        historical_seed_internal_score_candidates_payload
    )
    historical_seed_native_oracle_metric_candidates_summary = _summary(
        historical_seed_native_oracle_metric_candidates_payload
    )
    historical_seed_calibration_candidate_ledgers_summary = _summary(
        historical_seed_calibration_candidate_ledgers_payload
    )
    historical_seed_calibration_field_candidates_summary = _summary(
        historical_seed_calibration_field_candidates_payload
    )
    historical_seed_clearance_fill_candidate_packet_summary = _summary(
        historical_seed_clearance_fill_candidate_packet_payload
    )
    historical_seed_clearance_execution_board_summary = _summary(
        historical_seed_clearance_execution_board_payload
    )
    historical_seed_first_clearance_operator_kit_summary = _summary(
        historical_seed_first_clearance_operator_kit_payload
    )
    historical_seed_first_clearance_no_leak_gate_summary = _summary(
        historical_seed_first_clearance_no_leak_gate_payload
    )
    historical_seed_first_clearance_no_leak_evidence_packet_summary = _summary(
        historical_seed_first_clearance_no_leak_evidence_packet_payload
    )
    historical_seed_first_clearance_no_leak_evidence_review_gate_summary = _summary(
        historical_seed_first_clearance_no_leak_evidence_review_gate_payload
    )
    historical_seed_first_clearance_no_leak_evidence_sync_plan_summary = _summary(
        historical_seed_first_clearance_no_leak_evidence_sync_plan_payload
    )
    historical_seed_first_clearance_closure_board_summary = _summary(
        historical_seed_first_clearance_closure_board_payload
    )
    historical_seed_clearance_to_identity_intake_sync_summary = _summary(
        historical_seed_clearance_to_identity_intake_sync_payload
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
            "protein_object_library_completion_audit",
            "Completion audit for protein-name folders and per-object 3D molecular assets",
            _text(protein_object_library_completion_audit_summary.get("completion_audit_status")),
            args.protein_object_library_completion_audit_json,
            ready_count=_int(protein_object_library_completion_audit_summary.get("object_pass_count")),
            blocked_count=_int(protein_object_library_completion_audit_summary.get("object_blocked_count")),
            total_count=_int(protein_object_library_completion_audit_summary.get("object_folder_count")),
            next_action=_text(protein_object_library_completion_audit_summary.get("next_action")),
            blockers=(
                "proteins:"
                + str(protein_object_library_completion_audit_summary.get("protein_folder_pass_count", ""))
                + "/"
                + str(protein_object_library_completion_audit_summary.get("protein_folder_blocked_count", ""))
                + "/"
                + str(protein_object_library_completion_audit_summary.get("protein_folder_count", ""))
                + ",assets:"
                + str(protein_object_library_completion_audit_summary.get("model_file_present_count", ""))
                + "/"
                + str(protein_object_library_completion_audit_summary.get("projection_file_present_count", ""))
                + "/"
                + str(protein_object_library_completion_audit_summary.get("viewer_file_present_count", ""))
                + ",manifests:"
                + str(protein_object_library_completion_audit_summary.get("object_manifest_present_count", ""))
                + "/"
                + str(protein_object_library_completion_audit_summary.get("protein_manifest_present_count", ""))
                + ",first_blocked:"
                + (_text(protein_object_library_completion_audit_summary.get("first_blocked_blockers")) or "-")
            ),
        ),
        _artifact_row(
            "protein_object_library_navigation_catalog",
            "Navigation catalog for protein-name 3D object folders and viewers",
            _text(protein_object_library_navigation_catalog_summary.get("navigation_catalog_status")),
            args.protein_object_library_navigation_catalog_json,
            ready_count=_int(protein_object_library_navigation_catalog_summary.get("object_pass_count")),
            blocked_count=_int(protein_object_library_navigation_catalog_summary.get("object_blocked_count")),
            total_count=_int(protein_object_library_navigation_catalog_summary.get("object_count")),
            next_action=_text(protein_object_library_navigation_catalog_summary.get("next_action")),
            blockers=(
                "proteins:"
                + str(protein_object_library_navigation_catalog_summary.get("protein_pass_count", ""))
                + "/"
                + str(protein_object_library_navigation_catalog_summary.get("protein_blocked_count", ""))
                + "/"
                + str(protein_object_library_navigation_catalog_summary.get("protein_count", ""))
                + ",links:"
                + str(protein_object_library_navigation_catalog_summary.get("protein_readme_link_count", ""))
                + "/"
                + str(protein_object_library_navigation_catalog_summary.get("protein_manifest_link_count", ""))
                + ",largest:"
                + (_text(protein_object_library_navigation_catalog_summary.get("largest_protein_key")) or "-")
                + "/"
                + str(protein_object_library_navigation_catalog_summary.get("largest_object_count", ""))
                + ",html:"
                + (_text(protein_object_library_navigation_catalog_summary.get("html_catalog_path")) or "-")
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
            "win_tier_metric_surface_contract",
            "CASP17 win-tier official-like metric surface input/output contract",
            _text(win_tier_metric_surface_contract_summary.get("metric_surface_contract_status")),
            args.win_tier_metric_surface_contract_json,
            ready_count=_int(win_tier_metric_surface_contract_summary.get("ready_metric_row_count")),
            blocked_count=_int(win_tier_metric_surface_contract_summary.get("blocked_metric_row_count")),
            total_count=_int(win_tier_metric_surface_contract_summary.get("metric_surface_row_count")),
            next_action=_text(win_tier_metric_surface_contract_summary.get("next_action")),
            blockers=(
                "metrics:"
                + str(win_tier_metric_surface_contract_summary.get("covered_required_metric_count", ""))
                + "/"
                + str(win_tier_metric_surface_contract_summary.get("required_metric_count", ""))
                + ",slots:"
                + str(win_tier_metric_surface_contract_summary.get("ready_slot_count", ""))
                + "/"
                + str(win_tier_metric_surface_contract_summary.get("blocked_slot_count", ""))
                + "/"
                + str(win_tier_metric_surface_contract_summary.get("strict_blind_slot_count", ""))
                + ",rows:"
                + str(win_tier_metric_surface_contract_summary.get("ready_metric_row_count", ""))
                + "/"
                + str(win_tier_metric_surface_contract_summary.get("blocked_metric_row_count", ""))
                + "/"
                + str(win_tier_metric_surface_contract_summary.get("metric_surface_row_count", ""))
                + ",ligand_slots:"
                + str(win_tier_metric_surface_contract_summary.get("organic_ligand_slot_count", ""))
                + ",official_archive:"
                + _text(win_tier_metric_surface_contract_summary.get("official_archive_baseline_policy"))
            ),
        ),
        _artifact_row(
            "win_tier_critical_path_board",
            "CASP17 win-tier critical path board",
            _text(win_tier_critical_path_board_summary.get("critical_path_status")),
            args.win_tier_critical_path_board_json,
            ready_count=_int(win_tier_critical_path_board_summary.get("stage_ready_count")),
            blocked_count=_int(win_tier_critical_path_board_summary.get("stage_blocked_count")),
            total_count=_int(win_tier_critical_path_board_summary.get("stage_count")),
            next_action=_text(win_tier_critical_path_board_summary.get("first_next_action")),
            blockers=(
                "3d:"
                + str(win_tier_critical_path_board_summary.get("three_d_object_ready_count", ""))
                + "/"
                + str(win_tier_critical_path_board_summary.get("three_d_object_count", ""))
                + ",external:"
                + str(win_tier_critical_path_board_summary.get("external_model_selection_ready_target_count", ""))
                + "/"
                + str(win_tier_critical_path_board_summary.get("external_model_selection_target_count", ""))
                + ",model1/top5:"
                + str(win_tier_critical_path_board_summary.get("external_model_selection_model1_count", ""))
                + "/"
                + str(win_tier_critical_path_board_summary.get("external_model_selection_top5_count", ""))
                + ",strict:"
                + str(win_tier_critical_path_board_summary.get("strict_blind_ready_slot_count", ""))
                + "/"
                + str(win_tier_critical_path_board_summary.get("strict_blind_slot_count", ""))
                + ",missing_files:"
                + str(win_tier_critical_path_board_summary.get("strict_blind_evidence_file_missing_count", ""))
                + ",operator_open:"
                + str(win_tier_critical_path_board_summary.get("strict_blind_operator_open_value_count", ""))
                + ",first:"
                + _text(win_tier_critical_path_board_summary.get("first_blocked_stage_id"))
            ),
        ),
        _artifact_row(
            "organic_ligand_slot_candidate_packet",
            "CASP17 organic ligand-protein historical slot candidate packet",
            _text(organic_ligand_slot_candidate_packet_summary.get("organic_ligand_slot_candidate_status")),
            args.organic_ligand_slot_candidate_packet_json,
            ready_count=_int(organic_ligand_slot_candidate_packet_summary.get("review_ready_candidate_count")),
            blocked_count=_int(
                organic_ligand_slot_candidate_packet_summary.get("strict_blind_promotion_blocked_count")
            ),
            total_count=_int(organic_ligand_slot_candidate_packet_summary.get("candidate_count")),
            next_action=_text(organic_ligand_slot_candidate_packet_summary.get("next_action")),
            blockers=(
                "chembl/bindingdb:"
                + str(organic_ligand_slot_candidate_packet_summary.get("chembl_candidate_count", ""))
                + "/"
                + str(organic_ligand_slot_candidate_packet_summary.get("bindingdb_candidate_count", ""))
                + ",proof_eligible:"
                + str(organic_ligand_slot_candidate_packet_summary.get("competitive_proof_eligible_count", ""))
                + ",strict_blocked:"
                + str(
                    organic_ligand_slot_candidate_packet_summary.get(
                        "strict_blind_promotion_blocked_count",
                        "",
                    )
                )
                + ",files:"
                + str(organic_ligand_slot_candidate_packet_summary.get("local_reference_present_count", ""))
                + "/"
                + str(organic_ligand_slot_candidate_packet_summary.get("prediction_present_count", ""))
                + "/"
                + str(organic_ligand_slot_candidate_packet_summary.get("ligand_mol2_present_count", ""))
                + ",metrics:"
                + str(organic_ligand_slot_candidate_packet_summary.get("lddt_pli_required_count", ""))
                + "/"
                + str(organic_ligand_slot_candidate_packet_summary.get("bisyrmsd_required_count", ""))
                + ",metric_ligand_slots:"
                + str(
                    organic_ligand_slot_candidate_packet_summary.get(
                        "metric_contract_ligand_slot_gap_count",
                        "",
                    )
                )
            ),
        ),
        _artifact_row(
            "organic_ligand_slot_promotion_action_board",
            "CASP17 organic ligand strict-blind promotion evidence action board",
            _text(
                organic_ligand_slot_promotion_action_board_summary.get(
                    "organic_ligand_slot_promotion_action_board_status"
                )
            ),
            args.organic_ligand_slot_promotion_action_board_json,
            ready_count=_int(
                organic_ligand_slot_promotion_action_board_summary.get(
                    "reference_file_preflight_pass_count"
                )
            ),
            blocked_count=_int(
                organic_ligand_slot_promotion_action_board_summary.get("open_action_count")
            ),
            total_count=_int(
                organic_ligand_slot_promotion_action_board_summary.get("action_count")
            ),
            next_action=_text(organic_ligand_slot_promotion_action_board_summary.get("next_action")),
            blockers=(
                "candidates:"
                + str(organic_ligand_slot_promotion_action_board_summary.get("candidate_count", ""))
                + ",operator:"
                + str(
                    organic_ligand_slot_promotion_action_board_summary.get(
                        "operator_evidence_required_count",
                        "",
                    )
                )
                + ",numeric:"
                + str(
                    organic_ligand_slot_promotion_action_board_summary.get(
                        "numeric_value_required_count",
                        "",
                    )
                )
                + ",affinity_source:"
                + str(
                    organic_ligand_slot_promotion_action_board_summary.get(
                        "affinity_source_required_count",
                        "",
                    )
                )
                + ",metric:"
                + str(
                    organic_ligand_slot_promotion_action_board_summary.get(
                        "metric_input_required_count",
                        "",
                    )
                )
                + ",slot:"
                + str(
                    organic_ligand_slot_promotion_action_board_summary.get(
                        "slot_mapping_required_count",
                        "",
                    )
                )
                + ",proof_ready:"
                + str(
                    organic_ligand_slot_promotion_action_board_summary.get(
                        "proof_ready_candidate_count",
                        "",
                    )
                )
            ),
        ),
        _artifact_row(
            "active_scope_decision",
            "CASP17 active scope and CAPRI hold decision",
            _text(active_scope_decision_summary.get("scope_decision_status")),
            args.active_scope_decision_json,
            ready_count=_int(active_scope_decision_summary.get("active_lane_count")),
            blocked_count=0,
            total_count=_int(active_scope_decision_summary.get("row_count")),
            next_action=_text(active_scope_decision_summary.get("first_next_action")),
            blockers=(
                "scope:"
                + _text(active_scope_decision_summary.get("active_competition_scope"))
                + ",capri:"
                + _text(active_scope_decision_summary.get("capri_round65_participation_status"))
            ),
        ),
        _artifact_row(
            "organizer_notice_packet",
            "CASP17 organizer notice intake and MassiveFold external model-pool guardrails",
            _text(organizer_notice_summary.get("organizer_notice_status")),
            args.organizer_notice_packet_json,
            ready_count=_int(organizer_notice_summary.get("massivefold_link_count")),
            blocked_count=0,
            total_count=_int(organizer_notice_summary.get("massivefold_link_count")),
            next_action=_text(organizer_notice_summary.get("next_action")),
            blockers=(
                "r2345_first:"
                + _text(organizer_notice_summary.get("r2345_first_request_status"))
                + ",r2345_second:"
                + _text(organizer_notice_summary.get("r2345_replacement_request_status"))
                + ",scope:"
                + _text(organizer_notice_summary.get("massivefold_generation_scope"))
                + ",massivefold_rna_hybrid:"
                + str(organizer_notice_summary.get("massivefold_rna_hybrid_link_count", ""))
                + ",r2341:"
                + str(organizer_notice_summary.get("massivefold_r2341_link_present", ""))
                + ",r2345:"
                + str(organizer_notice_summary.get("massivefold_r2345_link_present", ""))
                + ",policy:"
                + _text(organizer_notice_summary.get("massivefold_internal_prediction_policy"))
            ),
        ),
        _artifact_row(
            "massivefold_external_pool_intake",
            "CASP17 MassiveFold external pool acquisition and rerank guardrail lane",
            _text(massivefold_external_pool_intake_summary.get("massivefold_external_pool_intake_status")),
            args.massivefold_external_pool_intake_json,
            ready_count=_int(massivefold_external_pool_intake_summary.get("ready_pool_count")),
            blocked_count=_int(massivefold_external_pool_intake_summary.get("blocked_pool_count")),
            total_count=_int(massivefold_external_pool_intake_summary.get("massivefold_pool_count")),
            next_action=_text(massivefold_external_pool_intake_summary.get("next_action")),
            blockers=(
                "rna_hybrid:"
                + str(massivefold_external_pool_intake_summary.get("rna_hybrid_pool_count", ""))
                + ",protein_complex:"
                + str(massivefold_external_pool_intake_summary.get("protein_complex_pool_count", ""))
                + ",proof_eligible:"
                + str(massivefold_external_pool_intake_summary.get("competitive_proof_eligible_count", ""))
                + ",internal_blocked:"
                + str(massivefold_external_pool_intake_summary.get("internal_prediction_blocked_count", ""))
                + ",r2341:"
                + str(massivefold_external_pool_intake_summary.get("r2341_pool_present", ""))
                + ",r2345:"
                + str(massivefold_external_pool_intake_summary.get("r2345_pool_present", ""))
                + ",largest:"
                + _text(massivefold_external_pool_intake_summary.get("largest_model_set_id"))
            ),
        ),
        _artifact_row(
            "rna_hybrid_massivefold_priority_queue",
            "CASP17 RNA/hybrid MassiveFold external-pool priority and sequence-guard queue",
            _text(
                rna_hybrid_massivefold_priority_queue_summary.get(
                    "rna_hybrid_massivefold_priority_queue_status"
                )
            ),
            args.rna_hybrid_massivefold_priority_queue_json,
            ready_count=_int(rna_hybrid_massivefold_priority_queue_summary.get("ready_queue_row_count")),
            blocked_count=_int(rna_hybrid_massivefold_priority_queue_summary.get("blocked_queue_row_count")),
            total_count=_int(rna_hybrid_massivefold_priority_queue_summary.get("queue_row_count")),
            next_action=_text(rna_hybrid_massivefold_priority_queue_summary.get("next_action")),
            blockers=(
                "first:"
                + _text(rna_hybrid_massivefold_priority_queue_summary.get("first_priority_target_id"))
                + ",r2341_rank:"
                + str(rna_hybrid_massivefold_priority_queue_summary.get("r2341_queue_rank", ""))
                + ",r2345_rank:"
                + str(rna_hybrid_massivefold_priority_queue_summary.get("r2345_queue_rank", ""))
                + ",r2345_invalid:"
                + _text(rna_hybrid_massivefold_priority_queue_summary.get("r2345_invalid_request_status"))
                + ",r2345_active:"
                + _text(rna_hybrid_massivefold_priority_queue_summary.get("r2345_active_request_status"))
                + ",proof_eligible:"
                + str(
                    rna_hybrid_massivefold_priority_queue_summary.get(
                        "competitive_proof_eligible_count",
                        "",
                    )
                )
                + ",internal_blocked:"
                + str(
                    rna_hybrid_massivefold_priority_queue_summary.get(
                        "internal_prediction_blocked_count",
                        "",
                    )
                )
            ),
        ),
        _artifact_row(
            "protein_complex_massivefold_priority_queue",
            "CASP17 protein/complex MassiveFold external-pool priority queue",
            _text(
                protein_complex_massivefold_priority_queue_summary.get(
                    "protein_complex_massivefold_priority_queue_status"
                )
            ),
            args.protein_complex_massivefold_priority_queue_json,
            ready_count=_int(
                protein_complex_massivefold_priority_queue_summary.get("ready_queue_row_count")
            ),
            blocked_count=_int(
                protein_complex_massivefold_priority_queue_summary.get("blocked_queue_row_count")
            ),
            total_count=_int(
                protein_complex_massivefold_priority_queue_summary.get("queue_row_count")
            ),
            next_action=_text(protein_complex_massivefold_priority_queue_summary.get("next_action")),
            blockers=(
                "first:"
                + _text(protein_complex_massivefold_priority_queue_summary.get("first_priority_target_id"))
                + ",model_set:"
                + _text(
                    protein_complex_massivefold_priority_queue_summary.get(
                        "first_priority_model_set_id"
                    )
                )
                + ",largest:"
                + _text(protein_complex_massivefold_priority_queue_summary.get("largest_model_set_id"))
                + ",proof_eligible:"
                + str(
                    protein_complex_massivefold_priority_queue_summary.get(
                        "competitive_proof_eligible_count",
                        "",
                    )
                )
                + ",internal_blocked:"
                + str(
                    protein_complex_massivefold_priority_queue_summary.get(
                        "internal_prediction_blocked_count",
                        "",
                    )
                )
            ),
        ),
        _artifact_row(
            "massivefold_acquisition_verification_board",
            "CASP17 MassiveFold external-pool tarball hash and listing verification board",
            _text(
                massivefold_acquisition_verification_board_summary.get(
                    "massivefold_acquisition_verification_status"
                )
            ),
            args.massivefold_acquisition_verification_board_json,
            ready_count=_int(
                massivefold_acquisition_verification_board_summary.get("verified_pool_count")
            ),
            blocked_count=_int(
                massivefold_acquisition_verification_board_summary.get(
                    "open_acquisition_action_count"
                )
            ),
            total_count=_int(
                massivefold_acquisition_verification_board_summary.get("acquisition_pool_count")
            ),
            next_action=_text(massivefold_acquisition_verification_board_summary.get("next_action")),
            blockers=(
                "first:"
                + _text(massivefold_acquisition_verification_board_summary.get("first_priority_target_id"))
                + ",download:"
                + str(massivefold_acquisition_verification_board_summary.get("tarball_present_count", ""))
                + ",hash:"
                + str(
                    massivefold_acquisition_verification_board_summary.get(
                        "sha256_record_present_count",
                        "",
                    )
                )
                + ",listing:"
                + str(massivefold_acquisition_verification_board_summary.get("listing_present_count", ""))
                + ",verified:"
                + str(massivefold_acquisition_verification_board_summary.get("verified_pool_count", ""))
                + ",r2341:"
                + _text(massivefold_acquisition_verification_board_summary.get("r2341_verification_status"))
                + ",r2345:"
                + _text(massivefold_acquisition_verification_board_summary.get("r2345_verification_status"))
            ),
        ),
        _artifact_row(
            "protein_complex_massivefold_acquisition_verification_board",
            "CASP17 protein/complex MassiveFold tarball hash and listing verification board",
            _text(
                protein_complex_massivefold_acquisition_verification_board_summary.get(
                    "massivefold_acquisition_verification_status"
                )
            ),
            args.protein_complex_massivefold_acquisition_verification_board_json,
            ready_count=_int(
                protein_complex_massivefold_acquisition_verification_board_summary.get(
                    "verified_pool_count"
                )
            ),
            blocked_count=_int(
                protein_complex_massivefold_acquisition_verification_board_summary.get(
                    "open_acquisition_action_count"
                )
            ),
            total_count=_int(
                protein_complex_massivefold_acquisition_verification_board_summary.get(
                    "acquisition_pool_count"
                )
            ),
            next_action=_text(
                protein_complex_massivefold_acquisition_verification_board_summary.get("next_action")
            ),
            blockers=(
                "first:"
                + _text(
                    protein_complex_massivefold_acquisition_verification_board_summary.get(
                        "first_priority_target_id"
                    )
                )
                + ",open:"
                + _text(
                    protein_complex_massivefold_acquisition_verification_board_summary.get(
                        "first_open_target_id"
                    )
                )
                + ",status:"
                + _text(
                    protein_complex_massivefold_acquisition_verification_board_summary.get(
                        "first_open_status"
                    )
                )
                + ",download:"
                + str(
                    protein_complex_massivefold_acquisition_verification_board_summary.get(
                        "tarball_present_count",
                        "",
                    )
                )
                + ",hash:"
                + str(
                    protein_complex_massivefold_acquisition_verification_board_summary.get(
                        "sha256_record_present_count",
                        "",
                    )
                )
                + ",listing:"
                + str(
                    protein_complex_massivefold_acquisition_verification_board_summary.get(
                        "listing_present_count",
                        "",
                    )
                )
            ),
        ),
        _artifact_row(
            "massivefold_model_pool_index",
            "CASP17 MassiveFold verified model-pool index and balanced representative extraction board",
            _text(massivefold_model_pool_index_summary.get("massivefold_model_pool_index_status")),
            args.massivefold_model_pool_index_json,
            ready_count=_int(massivefold_model_pool_index_summary.get("selected_extracted_count")),
            blocked_count=_int(massivefold_model_pool_index_summary.get("selected_extract_pending_count")),
            total_count=_int(massivefold_model_pool_index_summary.get("selected_extract_count")),
            next_action=_text(massivefold_model_pool_index_summary.get("next_action")),
            blockers=(
                "target:"
                + _text(massivefold_model_pool_index_summary.get("target_id"))
                + ",models:"
                + str(massivefold_model_pool_index_summary.get("model_count", ""))
                + ",protocols:"
                + str(massivefold_model_pool_index_summary.get("protocol_bucket_count", ""))
                + ",selected:"
                + str(massivefold_model_pool_index_summary.get("selected_extract_count", ""))
                + ",extracted:"
                + str(massivefold_model_pool_index_summary.get("selected_extracted_count", ""))
                + ",pending:"
                + str(massivefold_model_pool_index_summary.get("selected_extract_pending_count", ""))
                + ",sha:"
                + _text(massivefold_model_pool_index_summary.get("tarball_sha256"))[:12]
            ),
        ),
        _artifact_row(
            "massivefold_representative_viewer_packet",
            "CASP17 MassiveFold representative CIF folders, projections, and local 3D viewers",
            _text(
                massivefold_representative_viewer_packet_summary.get(
                    "massivefold_representative_viewer_status"
                )
            ),
            args.massivefold_representative_viewer_packet_json,
            ready_count=_int(massivefold_representative_viewer_packet_summary.get("viewer_ready_count")),
            blocked_count=_int(massivefold_representative_viewer_packet_summary.get("viewer_blocked_count")),
            total_count=_int(massivefold_representative_viewer_packet_summary.get("selected_model_count")),
            next_action=_text(massivefold_representative_viewer_packet_summary.get("next_action")),
            blockers=(
                "target:"
                + _text(massivefold_representative_viewer_packet_summary.get("target_id"))
                + ",models:"
                + str(massivefold_representative_viewer_packet_summary.get("selected_model_count", ""))
                + ",viewers:"
                + str(massivefold_representative_viewer_packet_summary.get("viewer_ready_count", ""))
                + ",blocked:"
                + str(massivefold_representative_viewer_packet_summary.get("viewer_blocked_count", ""))
                + ",coordinates:"
                + str(massivefold_representative_viewer_packet_summary.get("coordinate_valid_count", ""))
                + ",model_cif:"
                + str(massivefold_representative_viewer_packet_summary.get("model_cif_present_count", ""))
                + ",projection:"
                + str(massivefold_representative_viewer_packet_summary.get("projection_ready_count", ""))
                + ",first:"
                + _text(massivefold_representative_viewer_packet_summary.get("first_viewer_html"))
            ),
        ),
        _artifact_row(
            "massivefold_representative_rerank_packet",
            "CASP17 MassiveFold representative review-only model1/top5 rerank board",
            _text(
                massivefold_representative_rerank_packet_summary.get(
                    "massivefold_representative_rerank_status"
                )
            ),
            args.massivefold_representative_rerank_packet_json,
            ready_count=_int(massivefold_representative_rerank_packet_summary.get("top5_candidate_count")),
            blocked_count=max(
                0,
                _int(massivefold_representative_rerank_packet_summary.get("candidate_count"))
                - _int(massivefold_representative_rerank_packet_summary.get("top5_candidate_count")),
            ),
            total_count=_int(massivefold_representative_rerank_packet_summary.get("candidate_count")),
            next_action=_text(massivefold_representative_rerank_packet_summary.get("next_action")),
            blockers=(
                "target:"
                + _text(massivefold_representative_rerank_packet_summary.get("target_id"))
                + ",candidates:"
                + str(massivefold_representative_rerank_packet_summary.get("candidate_count", ""))
                + ",model1:"
                + str(massivefold_representative_rerank_packet_summary.get("model1_candidate_count", ""))
                + ",top5:"
                + str(massivefold_representative_rerank_packet_summary.get("top5_candidate_count", ""))
                + ",top5_protocols:"
                + str(massivefold_representative_rerank_packet_summary.get("top5_protocol_count", ""))
                + ",proof_eligible:"
                + str(
                    massivefold_representative_rerank_packet_summary.get(
                        "competitive_proof_eligible_count",
                        "",
                    )
                )
                + ",model1_file:"
                + _text(massivefold_representative_rerank_packet_summary.get("model1_filename"))
            ),
        ),
        _artifact_row(
            "massivefold_rna_model_selection_coverage",
            "CASP17 MassiveFold RNA target acquisition, viewer, and review-only rerank coverage",
            _text(
                massivefold_rna_model_selection_coverage_summary.get(
                    "massivefold_rna_model_selection_coverage_status"
                )
            ),
            args.massivefold_rna_model_selection_coverage_json,
            ready_count=_int(massivefold_rna_model_selection_coverage_summary.get("ready_target_count")),
            blocked_count=_int(massivefold_rna_model_selection_coverage_summary.get("partial_target_count")),
            total_count=_int(massivefold_rna_model_selection_coverage_summary.get("target_count")),
            next_action=_text(massivefold_rna_model_selection_coverage_summary.get("next_action")),
            blockers=(
                "targets:"
                + str(massivefold_rna_model_selection_coverage_summary.get("target_count", ""))
                + ",ready:"
                + str(massivefold_rna_model_selection_coverage_summary.get("ready_target_count", ""))
                + ",verified:"
                + str(massivefold_rna_model_selection_coverage_summary.get("verified_acquisition_count", ""))
                + ",index:"
                + str(
                    massivefold_rna_model_selection_coverage_summary.get(
                        "representative_extracted_target_count",
                        "",
                    )
                )
                + ",viewers:"
                + str(massivefold_rna_model_selection_coverage_summary.get("viewer_ready_target_count", ""))
                + ",rerank:"
                + str(massivefold_rna_model_selection_coverage_summary.get("rerank_ready_target_count", ""))
                + ",models:"
                + str(massivefold_rna_model_selection_coverage_summary.get("selected_model_count", ""))
                + "/"
                + str(massivefold_rna_model_selection_coverage_summary.get("extracted_model_count", ""))
                + "/"
                + str(massivefold_rna_model_selection_coverage_summary.get("viewer_ready_model_count", ""))
                + ",model1/top5:"
                + str(massivefold_rna_model_selection_coverage_summary.get("model1_candidate_count", ""))
                + "/"
                + str(massivefold_rna_model_selection_coverage_summary.get("top5_candidate_count", ""))
                + ",first_partial:"
                + _text(massivefold_rna_model_selection_coverage_summary.get("first_partial_target_id"))
            ),
        ),
        _artifact_row(
            "protein_complex_massivefold_model_selection_coverage",
            "CASP17 MassiveFold protein/complex acquisition, viewer, and review-only rerank coverage",
            _text(
                protein_complex_massivefold_model_selection_coverage_summary.get(
                    "protein_complex_massivefold_model_selection_coverage_status"
                )
            ),
            args.protein_complex_massivefold_model_selection_coverage_json,
            ready_count=_int(
                protein_complex_massivefold_model_selection_coverage_summary.get("ready_target_count")
            ),
            blocked_count=_int(
                protein_complex_massivefold_model_selection_coverage_summary.get("partial_target_count")
            ),
            total_count=_int(
                protein_complex_massivefold_model_selection_coverage_summary.get("target_count")
            ),
            next_action=_text(
                protein_complex_massivefold_model_selection_coverage_summary.get("next_action")
            ),
            blockers=(
                "targets:"
                + str(protein_complex_massivefold_model_selection_coverage_summary.get("target_count", ""))
                + ",ready:"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "ready_target_count",
                        "",
                    )
                )
                + ",verified:"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "verified_acquisition_count",
                        "",
                    )
                )
                + ",index:"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "representative_extracted_target_count",
                        "",
                    )
                )
                + ",viewers:"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "viewer_ready_target_count",
                        "",
                    )
                )
                + ",rerank:"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "rerank_ready_target_count",
                        "",
                    )
                )
                + ",models:"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "selected_model_count",
                        "",
                    )
                )
                + "/"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "extracted_model_count",
                        "",
                    )
                )
                + "/"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "viewer_ready_model_count",
                        "",
                    )
                )
                + ",model1/top5:"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "model1_candidate_count",
                        "",
                    )
                )
                + "/"
                + str(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "top5_candidate_count",
                        "",
                    )
                )
                + ",first_partial:"
                + _text(
                    protein_complex_massivefold_model_selection_coverage_summary.get(
                        "first_partial_target_id"
                    )
                )
            ),
        ),
        _artifact_row(
            "capri_round65_readiness",
            "CAPRI Round 65 registration, role-selection, and format-preflight gate",
            (
                _text(active_scope_decision_summary.get("capri_round65_participation_status"))
                if capri_round65_deferred
                else _text(capri_round65_readiness_summary.get("capri_readiness_status"))
            ),
            args.capri_round65_readiness_json,
            ready_count=0 if capri_round65_deferred else _int(capri_round65_readiness_summary.get("format_preflight_target_count")),
            blocked_count=0 if capri_round65_deferred else _int(capri_round65_readiness_summary.get("blocked_target_count")),
            total_count=_int(capri_round65_readiness_summary.get("target_count")),
            next_action=(
                "preserve CAPRI context only; continue CASP17 historical benchmark and competitive-floor work"
                if capri_round65_deferred
                else _text(capri_round65_readiness_summary.get("first_next_action"))
            ),
            blockers=(
                (
                    "not_active_scope,reason:"
                    + _text(active_scope_decision_summary.get("capri_round65_hold_reason"))
                )
                if capri_round65_deferred
                else (
                    "registration:"
                    + _text(capri_round65_readiness_summary.get("registration_gate_status"))
                    + ",days:"
                    + str(capri_round65_readiness_summary.get("registration_days_remaining", ""))
                    + ",roles:"
                    + _text(capri_round65_readiness_summary.get("role_selection_status"))
                    + ",scorer:"
                    + str(capri_round65_readiness_summary.get("scorer_priority_target_count", ""))
                    + ",predictor:"
                    + str(capri_round65_readiness_summary.get("predictor_priority_target_count", ""))
                )
            ),
        ),
        _artifact_row(
            "capri_round65_format_preflight",
            "CAPRI Round 65 local PDB format and online-validator preflight",
            (
                _text(active_scope_decision_summary.get("capri_round65_participation_status"))
                if capri_round65_deferred
                else _text(capri_round65_format_preflight_summary.get("format_preflight_status"))
            ),
            args.capri_round65_format_preflight_json,
            ready_count=0 if capri_round65_deferred else _int(capri_round65_format_preflight_summary.get("local_pass_count")),
            blocked_count=0 if capri_round65_deferred else _int(capri_round65_format_preflight_summary.get("blocked_target_count")),
            total_count=_int(capri_round65_format_preflight_summary.get("target_count")),
            next_action=(
                "skip CAPRI format preflight while Round 65 participation is on PI-required hold"
                if capri_round65_deferred
                else _text(capri_round65_format_preflight_summary.get("first_next_action"))
            ),
            blockers=(
                (
                    "not_active_scope,capri:"
                    + _text(active_scope_decision_summary.get("capri_round65_participation_status"))
                )
                if capri_round65_deferred
                else (
                    "checked:"
                    + str(capri_round65_format_preflight_summary.get("checked_submission_count", ""))
                    + ",template_missing:"
                    + str(capri_round65_format_preflight_summary.get("target_template_missing_count", ""))
                    + ",candidate_missing:"
                    + str(capri_round65_format_preflight_summary.get("candidate_submission_missing_count", ""))
                    + ",format_errors:"
                    + str(capri_round65_format_preflight_summary.get("format_error_count", ""))
                )
            ),
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
            "historical_identity_seed_clearance_field_board",
            "Lane-level field board for historical seed clearance inputs",
            _text(historical_identity_seed_clearance_field_board_summary.get("field_board_status")),
            args.historical_identity_seed_clearance_field_board_json,
            ready_count=_int(
                historical_identity_seed_clearance_field_board_summary.get(
                    "ready_for_cleared_seed_manifest_count"
                )
            ),
            blocked_count=(
                _int(
                    historical_identity_seed_clearance_field_board_summary.get(
                        "operator_field_fill_required_count"
                    )
                )
                + _int(historical_identity_seed_clearance_field_board_summary.get("blocked_core_file_count"))
            ),
            total_count=_int(historical_identity_seed_clearance_field_board_summary.get("seed_row_count")),
            next_action=_text(historical_identity_seed_clearance_field_board_summary.get("first_next_action")),
            blockers=(
                "core:"
                + str(historical_identity_seed_clearance_field_board_summary.get("core_file_pass_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_field_board_summary.get("blocked_core_file_count", ""))
                + ",open_fields:"
                + str(historical_identity_seed_clearance_field_board_summary.get("no_leak_open_field_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_field_board_summary.get("calibration_open_field_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_field_board_summary.get("ablation_open_field_count", ""))
                + "/"
                + str(historical_identity_seed_clearance_field_board_summary.get("total_open_field_count", ""))
                + ",ready:"
                + str(
                    historical_identity_seed_clearance_field_board_summary.get(
                        "ready_for_cleared_seed_manifest_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_no_leak_provenance_dossiers",
            "Fail-closed no-leak provenance dossiers for historical seed rows",
            _text(historical_seed_no_leak_provenance_dossiers_summary.get("no_leak_dossier_status")),
            args.historical_seed_no_leak_provenance_dossiers_json,
            ready_count=_int(
                historical_seed_no_leak_provenance_dossiers_summary.get(
                    "ready_for_no_leak_clearance_count"
                )
            ),
            blocked_count=_int(
                historical_seed_no_leak_provenance_dossiers_summary.get(
                    "operator_review_required_count"
                )
            ),
            total_count=_int(historical_seed_no_leak_provenance_dossiers_summary.get("seed_row_count")),
            next_action=_text(historical_seed_no_leak_provenance_dossiers_summary.get("first_next_action")),
            blockers=(
                "core:"
                + str(historical_seed_no_leak_provenance_dossiers_summary.get("core_input_pass_count", ""))
                + ",current_false:"
                + str(historical_seed_no_leak_provenance_dossiers_summary.get("current_target_prefilled_false_count", ""))
                + ",open_fields:"
                + str(historical_seed_no_leak_provenance_dossiers_summary.get("operator_required_open_field_count", ""))
                + ",chronology_gaps:"
                + str(historical_seed_no_leak_provenance_dossiers_summary.get("chronology_evidence_gap_count", ""))
                + ",negative_control_gaps:"
                + str(historical_seed_no_leak_provenance_dossiers_summary.get("negative_leakage_control_gap_count", ""))
                + ",mtime_risk:"
                + str(historical_seed_no_leak_provenance_dossiers_summary.get("mtime_order_risk_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_no_leak_gap_repair_plan",
            "No-leak provenance repair plan separating operator-required fields from weak local hints",
            _text(historical_seed_no_leak_gap_repair_plan_summary.get("no_leak_gap_repair_status")),
            args.historical_seed_no_leak_gap_repair_plan_json,
            ready_count=0,
            blocked_count=_int(historical_seed_no_leak_gap_repair_plan_summary.get("seed_row_count")),
            total_count=_int(historical_seed_no_leak_gap_repair_plan_summary.get("seed_row_count")),
            next_action=_text(historical_seed_no_leak_gap_repair_plan_summary.get("first_next_action")),
            blockers=(
                "fields:"
                + str(historical_seed_no_leak_gap_repair_plan_summary.get("field_count", ""))
                + ",operator_required:"
                + str(historical_seed_no_leak_gap_repair_plan_summary.get("operator_required_field_count", ""))
                + ",weak:"
                + str(historical_seed_no_leak_gap_repair_plan_summary.get("weak_local_candidate_field_count", ""))
                + ",authoritative:"
                + str(historical_seed_no_leak_gap_repair_plan_summary.get("authoritative_candidate_field_count", ""))
                + ",mtime_risk:"
                + str(historical_seed_no_leak_gap_repair_plan_summary.get("mtime_risk_row_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_current_target_prefill",
            "Fail-closed current-target=false prefill for historical seed rows",
            _text(historical_seed_current_target_prefill_summary.get("prefill_status")),
            args.historical_seed_current_target_prefill_json,
            ready_count=(
                _int(historical_seed_current_target_prefill_summary.get("applied_count"))
                + _int(historical_seed_current_target_prefill_summary.get("already_safe_false_count"))
            ),
            blocked_count=(
                _int(historical_seed_current_target_prefill_summary.get("ready_to_apply_count"))
                + _int(historical_seed_current_target_prefill_summary.get("blocked_count"))
            ),
            total_count=_int(historical_seed_current_target_prefill_summary.get("row_count")),
            next_action=_text(historical_seed_current_target_prefill_summary.get("first_next_action")),
            blockers=(
                "mode:"
                + str(historical_seed_current_target_prefill_summary.get("apply_mode", ""))
                + ",collisions:"
                + str(historical_seed_current_target_prefill_summary.get("current_target_collision_count", ""))
                + ",remaining_open:"
                + str(historical_seed_current_target_prefill_summary.get("remaining_open_current_target_count", ""))
                + ",hist_prefix:"
                + str(historical_seed_current_target_prefill_summary.get("hist_prefix_pass_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_native_authority_audit",
            "Native/reference authority audit for historical seed benchmark rows",
            _text(historical_seed_native_authority_audit_summary.get("native_authority_audit_status")),
            args.historical_seed_native_authority_audit_json,
            ready_count=_int(historical_seed_native_authority_audit_summary.get("native_authority_pass_count")),
            blocked_count=_int(historical_seed_native_authority_audit_summary.get("native_authority_blocked_count")),
            total_count=_int(historical_seed_native_authority_audit_summary.get("seed_row_count")),
            next_action=_text(historical_seed_native_authority_audit_summary.get("first_blocked_next_action")),
            blockers=(
                "placeholder:"
                + str(historical_seed_native_authority_audit_summary.get("placeholder_native_count", ""))
                + ",ca_only:"
                + str(historical_seed_native_authority_audit_summary.get("ca_only_native_count", ""))
                + ",local_generated_no_authority:"
                + str(
                    historical_seed_native_authority_audit_summary.get(
                        "local_generated_native_without_authority_count", ""
                    )
                )
                + ",ref_missing:"
                + str(historical_seed_native_authority_audit_summary.get("authority_ref_missing_count", ""))
                + ",first:"
                + _text(historical_seed_native_authority_audit_summary.get("first_blocked_target_id"))
            ),
        ),
        _artifact_row(
            "historical_seed_native_replacement_candidates",
            "RCSB public native replacement candidates for historical seed placeholders",
            _text(
                historical_seed_native_replacement_candidates_summary.get(
                    "native_replacement_candidate_status"
                )
            ),
            args.historical_seed_native_replacement_candidates_json,
            ready_count=_int(
                historical_seed_native_replacement_candidates_summary.get("operator_review_ready_count")
            ),
            blocked_count=(
                _int(
                    historical_seed_native_replacement_candidates_summary.get(
                        "source_download_required_count"
                    )
                )
                + _int(
                    historical_seed_native_replacement_candidates_summary.get(
                        "candidate_file_blocked_count"
                    )
                )
                + _int(
                    historical_seed_native_replacement_candidates_summary.get(
                        "complex_authority_required_count"
                    )
                )
            ),
            total_count=_int(historical_seed_native_replacement_candidates_summary.get("candidate_row_count")),
            next_action=_text(
                historical_seed_native_replacement_candidates_summary.get("first_blocked_next_action")
            ),
            blockers=(
                "review_ready:"
                + str(historical_seed_native_replacement_candidates_summary.get("operator_review_ready_count", ""))
                + ",download:"
                + str(
                    historical_seed_native_replacement_candidates_summary.get(
                        "source_download_required_count", ""
                    )
                )
                + ",file_blocked:"
                + str(
                    historical_seed_native_replacement_candidates_summary.get(
                        "candidate_file_blocked_count", ""
                    )
                )
                + ",complex_authority:"
                + str(
                    historical_seed_native_replacement_candidates_summary.get(
                        "complex_authority_required_count", ""
                    )
                )
                + ",dir:"
                + _text(historical_seed_native_replacement_candidates_summary.get("candidate_dir"))
            ),
        ),
        _artifact_row(
            "historical_seed_complex_source_authority_candidates",
            "Complex source-authority review packet for generated T. cruzi PDE historical seeds",
            _text(
                historical_seed_complex_source_authority_candidates_summary.get(
                    "complex_source_authority_candidate_status"
                )
            ),
            args.historical_seed_complex_source_authority_candidates_json,
            ready_count=_int(
                historical_seed_complex_source_authority_candidates_summary.get("operator_review_ready_count")
            ),
            blocked_count=_int(
                historical_seed_complex_source_authority_candidates_summary.get(
                    "source_authority_blocked_count"
                )
            ),
            total_count=_int(
                historical_seed_complex_source_authority_candidates_summary.get("candidate_row_count")
            ),
            next_action=_text(historical_seed_complex_source_authority_candidates_summary.get("first_next_action")),
            blockers=(
                "direct:"
                + str(
                    historical_seed_complex_source_authority_candidates_summary.get(
                        "direct_source_authority_ready_count", ""
                    )
                )
                + ",homolog:"
                + str(
                    historical_seed_complex_source_authority_candidates_summary.get(
                        "homolog_source_authority_ready_count", ""
                    )
                )
                + ",operator_apply:"
                + str(
                    historical_seed_complex_source_authority_candidates_summary.get(
                        "operator_apply_allowed_count", ""
                    )
                )
                + ",claim_promotion:"
                + str(
                    historical_seed_complex_source_authority_candidates_summary.get(
                        "claim_promotion_allowed_count", ""
                    )
                )
                + ",protein:"
                + _text(historical_seed_complex_source_authority_candidates_summary.get("protein_authority_ref"))
            ),
        ),
        _artifact_row(
            "historical_seed_chronology_candidate_board",
            "Operator chronology candidate board for historical seed rows",
            _text(historical_seed_chronology_candidate_board_summary.get("chronology_board_status")),
            args.historical_seed_chronology_candidate_board_json,
            ready_count=(
                _int(historical_seed_chronology_candidate_board_summary.get("operator_chronology_ready_count"))
                + _int(historical_seed_chronology_candidate_board_summary.get("operator_ready_mtime_warning_count"))
            ),
            blocked_count=(
                _int(historical_seed_chronology_candidate_board_summary.get("operator_evidence_required_count"))
                + _int(historical_seed_chronology_candidate_board_summary.get("blocked_chronology_conflict_count"))
            ),
            total_count=_int(historical_seed_chronology_candidate_board_summary.get("row_count")),
            next_action=_text(historical_seed_chronology_candidate_board_summary.get("first_next_action")),
            blockers=(
                "path_dates:"
                + str(historical_seed_chronology_candidate_board_summary.get("prediction_path_date_count", ""))
                + ",mtimes:"
                + str(historical_seed_chronology_candidate_board_summary.get("file_mtime_candidate_count", ""))
                + ",mtime_risk:"
                + str(historical_seed_chronology_candidate_board_summary.get("file_mtime_order_risk_count", ""))
                + ",conflicts:"
                + str(historical_seed_chronology_candidate_board_summary.get("blocked_chronology_conflict_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_authoritative_chronology_audit",
            "Authority-date chronology audit for historical seed rows",
            _text(
                historical_seed_authoritative_chronology_audit_summary.get(
                    "authoritative_chronology_audit_status"
                )
            ),
            args.historical_seed_authoritative_chronology_audit_json,
            ready_count=_int(
                historical_seed_authoritative_chronology_audit_summary.get("before_native_candidate_count")
            ),
            blocked_count=(
                _int(historical_seed_authoritative_chronology_audit_summary.get("post_native_blocked_count"))
                + _int(historical_seed_authoritative_chronology_audit_summary.get("evidence_required_count"))
            ),
            total_count=_int(historical_seed_authoritative_chronology_audit_summary.get("seed_row_count")),
            next_action=_text(historical_seed_authoritative_chronology_audit_summary.get("first_next_action")),
            blockers=(
                "native_dates:"
                + str(historical_seed_authoritative_chronology_audit_summary.get("native_authority_date_count", ""))
                + ",prediction_dates:"
                + str(historical_seed_authoritative_chronology_audit_summary.get("prediction_date_candidate_count", ""))
                + ",before_native:"
                + str(historical_seed_authoritative_chronology_audit_summary.get("before_native_candidate_count", ""))
                + ",post_native:"
                + str(historical_seed_authoritative_chronology_audit_summary.get("post_native_blocked_count", ""))
                + ",evidence_required:"
                + str(historical_seed_authoritative_chronology_audit_summary.get("evidence_required_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_lane_decision_packet",
            "Lane decision packet separating strict blind proof from retrospective review",
            _text(historical_seed_lane_decision_packet_summary.get("lane_decision_status")),
            args.historical_seed_lane_decision_packet_json,
            ready_count=_int(historical_seed_lane_decision_packet_summary.get("competitive_proof_allowed_count")),
            blocked_count=_int(
                historical_seed_lane_decision_packet_summary.get("strict_blind_replacement_required_count")
            ),
            total_count=_int(historical_seed_lane_decision_packet_summary.get("seed_row_count")),
            next_action=_text(historical_seed_lane_decision_packet_summary.get("first_next_action")),
            blockers=(
                "strict_blind:"
                + str(historical_seed_lane_decision_packet_summary.get("strict_blind_eligible_count", ""))
                + ",retrospective:"
                + str(historical_seed_lane_decision_packet_summary.get("retrospective_calibration_review_count", ""))
                + ",authority_required:"
                + str(historical_seed_lane_decision_packet_summary.get("authority_or_replacement_required_count", ""))
                + ",competitive:"
                + str(historical_seed_lane_decision_packet_summary.get("competitive_proof_allowed_count", ""))
                + ",replacement_required:"
                + str(historical_seed_lane_decision_packet_summary.get("strict_blind_replacement_required_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_queue",
            "Strict-blind replacement queue for the 40-row historical benchmark scaffold",
            _text(
                historical_seed_strict_blind_replacement_queue_summary.get(
                    "strict_blind_replacement_queue_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_queue_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_queue_summary.get("competitive_proof_allowed_slot_count")
            ),
            blocked_count=_int(
                historical_seed_strict_blind_replacement_queue_summary.get(
                    "strict_blind_replacement_required_count"
                )
            ),
            total_count=_int(historical_seed_strict_blind_replacement_queue_summary.get("scaffold_slot_count")),
            next_action=_text(historical_seed_strict_blind_replacement_queue_summary.get("first_next_action")),
            blockers=(
                "slots:"
                + str(historical_seed_strict_blind_replacement_queue_summary.get("scaffold_slot_count", ""))
                + ",monomer_complex:"
                + str(historical_seed_strict_blind_replacement_queue_summary.get("monomer_slot_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_queue_summary.get("complex_slot_count", ""))
                + ",replacement_required:"
                + str(
                    historical_seed_strict_blind_replacement_queue_summary.get(
                        "strict_blind_replacement_required_count", ""
                    )
                )
                + ",current_seed_competitive:"
                + str(
                    historical_seed_strict_blind_replacement_queue_summary.get(
                        "current_seed_competitive_allowed_count", ""
                    )
                )
                + ",fields:"
                + str(historical_seed_strict_blind_replacement_queue_summary.get("requirement_field_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_intake",
            "Strict-blind replacement intake and fail-closed preflight for queued scaffold slots",
            _text(
                historical_seed_strict_blind_replacement_intake_summary.get(
                    "strict_blind_replacement_intake_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_intake_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_intake_summary.get("ready_for_preflight_count")
            ),
            blocked_count=_int(
                historical_seed_strict_blind_replacement_intake_summary.get("blocked_or_awaiting_count")
            ),
            total_count=_int(historical_seed_strict_blind_replacement_intake_summary.get("intake_slot_count")),
            next_action=_text(historical_seed_strict_blind_replacement_intake_summary.get("first_next_action")),
            blockers=(
                "slots:"
                + str(historical_seed_strict_blind_replacement_intake_summary.get("intake_slot_count", ""))
                + ",ready:"
                + str(historical_seed_strict_blind_replacement_intake_summary.get("ready_for_preflight_count", ""))
                + ",awaiting:"
                + str(historical_seed_strict_blind_replacement_intake_summary.get("blocked_or_awaiting_count", ""))
                + ",filled:"
                + str(historical_seed_strict_blind_replacement_intake_summary.get("filled_field_count", ""))
                + ",missing:"
                + str(historical_seed_strict_blind_replacement_intake_summary.get("missing_field_count", ""))
                + ",fields:"
                + str(historical_seed_strict_blind_replacement_intake_summary.get("required_field_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_evidence_dropzones",
            "Strict-blind replacement evidence dropzones and intake patch previews",
            _text(
                historical_seed_strict_blind_replacement_evidence_dropzones_summary.get(
                    "strict_blind_replacement_evidence_dropzone_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_evidence_dropzones_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_evidence_dropzones_summary.get(
                    "ready_for_intake_patch_count"
                )
            ),
            blocked_count=_int(
                historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("awaiting_file_count")
            ),
            total_count=_int(historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("dropzone_count")),
            next_action=_text(
                historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("first_next_action")
            ),
            blockers=(
                "dropzones:"
                + str(historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("dropzone_count", ""))
                + ",ready:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_dropzones_summary.get(
                        "ready_for_intake_patch_count", ""
                    )
                )
                + ",awaiting:"
                + str(historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("awaiting_file_count", ""))
                + ",files_present:"
                + str(historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("file_present_count", ""))
                + ",files_missing:"
                + str(historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("file_missing_count", ""))
                + ",files_required:"
                + str(historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("file_required_count", ""))
                + ",operator_values:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_dropzones_summary.get(
                        "operator_value_required_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_evidence_action_board",
            "Strict-blind replacement evidence file placement action board",
            _text(
                historical_seed_strict_blind_replacement_evidence_action_board_summary.get(
                    "strict_blind_replacement_evidence_action_board_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_evidence_action_board_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_evidence_action_board_summary.get(
                    "ready_for_quality_audit_count"
                )
            ),
            blocked_count=(
                _int(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("open_missing_file_count"))
                + _int(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("blocked_count"))
            ),
            total_count=_int(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("action_count")),
            next_action=_text(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("first_next_action")),
            blockers=(
                "actions:"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("action_count", ""))
                + ",ready:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_action_board_summary.get(
                        "ready_for_quality_audit_count", ""
                    )
                )
                + ",open:"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("open_missing_file_count", ""))
                + ",blocked:"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("blocked_count", ""))
                + ",missing_by_field:"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("prediction_pdb_missing_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("native_pdb_missing_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("native_authority_missing_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("no_leak_evidence_missing_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("ablation_manifest_missing_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_action_board_summary.get("calibration_values_missing_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_evidence_quality_audit",
            "Strict-blind replacement evidence file quality audit",
            _text(
                historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                    "strict_blind_replacement_evidence_quality_audit_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_evidence_quality_audit_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                    "ready_for_quality_review_count"
                )
            ),
            blocked_count=(
                _int(historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("slot_count"))
                - _int(
                    historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                        "ready_for_quality_review_count"
                    )
                )
            ),
            total_count=_int(historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("slot_count")),
            next_action=_text(
                historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("first_next_action")
            ),
            blockers=(
                "ready:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                        "ready_for_quality_review_count", ""
                    )
                )
                + ",awaiting:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                        "awaiting_evidence_files_count", ""
                    )
                )
                + ",blocked:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                        "blocked_evidence_quality_count", ""
                    )
                )
                + ",files:"
                + str(historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("file_present_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("file_missing_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("file_required_count", ""))
                + ",pdb_slots:"
                + str(historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("pdb_valid_slot_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("pdb_invalid_slot_count", ""))
                + ",distinct:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                        "prediction_native_distinct_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_evidence_import_gate",
            "Strict-blind replacement evidence import gate from dropzone patch previews into intake CSVs",
            _text(
                historical_seed_strict_blind_replacement_evidence_import_gate_summary.get(
                    "strict_blind_replacement_evidence_import_gate_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_evidence_import_gate_json,
            ready_count=(
                _int(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("ready_for_apply_count"))
                + _int(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("applied_count"))
                + _int(
                    historical_seed_strict_blind_replacement_evidence_import_gate_summary.get(
                        "already_applied_count"
                    )
                )
            ),
            blocked_count=(
                _int(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("awaiting_file_count"))
                + _int(
                    historical_seed_strict_blind_replacement_evidence_import_gate_summary.get(
                        "awaiting_operator_value_count"
                    )
                )
                + _int(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("blocked_count"))
            ),
            total_count=_int(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("action_count")),
            next_action=_text(
                historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("first_next_action")
            ),
            blockers=(
                "mode:"
                + str(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("apply_mode", ""))
                + ",actions:"
                + str(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("action_count", ""))
                + ",file_operator:"
                + str(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("file_action_count", ""))
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_evidence_import_gate_summary.get(
                        "operator_value_action_count", ""
                    )
                )
                + ",ready:"
                + str(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("ready_for_apply_count", ""))
                + ",awaiting_file:"
                + str(historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("awaiting_file_count", ""))
                + ",awaiting_operator:"
                + str(
                    historical_seed_strict_blind_replacement_evidence_import_gate_summary.get(
                        "awaiting_operator_value_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_operator_value_gate",
            "Strict-blind replacement operator-value templates and apply gate",
            _text(
                historical_seed_strict_blind_replacement_operator_value_gate_summary.get(
                    "strict_blind_replacement_operator_value_gate_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_operator_value_gate_json,
            ready_count=(
                _int(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("ready_for_apply_count"))
                + _int(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("applied_count"))
                + _int(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("already_applied_count"))
            ),
            blocked_count=(
                _int(
                    historical_seed_strict_blind_replacement_operator_value_gate_summary.get(
                        "awaiting_operator_value_count"
                    )
                )
                + _int(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("awaiting_evidence_ref_count"))
                + _int(
                    historical_seed_strict_blind_replacement_operator_value_gate_summary.get(
                        "awaiting_operator_clearance_count"
                    )
                )
                + _int(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("blocked_count"))
            ),
            total_count=_int(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("action_count")),
            next_action=_text(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("first_next_action")),
            blockers=(
                "mode:"
                + str(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("apply_mode", ""))
                + ",templates:"
                + str(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("template_count", ""))
                + ",actions:"
                + str(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("action_count", ""))
                + ",ready:"
                + str(historical_seed_strict_blind_replacement_operator_value_gate_summary.get("ready_for_apply_count", ""))
                + ",awaiting_value:"
                + str(
                    historical_seed_strict_blind_replacement_operator_value_gate_summary.get(
                        "awaiting_operator_value_count", ""
                    )
                )
                + ",awaiting_evidence:"
                + str(
                    historical_seed_strict_blind_replacement_operator_value_gate_summary.get(
                        "awaiting_evidence_ref_count", ""
                    )
                )
                + ",awaiting_clearance:"
                + str(
                    historical_seed_strict_blind_replacement_operator_value_gate_summary.get(
                        "awaiting_operator_clearance_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_operator_action_board",
            "Strict-blind replacement operator value action board",
            _text(
                historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                    "strict_blind_replacement_operator_action_board_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_operator_action_board_json,
            ready_count=(
                _int(historical_seed_strict_blind_replacement_operator_action_board_summary.get("ready_for_apply_count"))
                + _int(historical_seed_strict_blind_replacement_operator_action_board_summary.get("applied_count"))
                + _int(historical_seed_strict_blind_replacement_operator_action_board_summary.get("already_applied_count"))
            ),
            blocked_count=(
                _int(historical_seed_strict_blind_replacement_operator_action_board_summary.get("open_operator_value_count"))
                + _int(historical_seed_strict_blind_replacement_operator_action_board_summary.get("blocked_count"))
            ),
            total_count=_int(historical_seed_strict_blind_replacement_operator_action_board_summary.get("action_count")),
            next_action=_text(historical_seed_strict_blind_replacement_operator_action_board_summary.get("first_next_action")),
            blockers=(
                "actions:"
                + str(historical_seed_strict_blind_replacement_operator_action_board_summary.get("action_count", ""))
                + ",ready:"
                + str(historical_seed_strict_blind_replacement_operator_action_board_summary.get("ready_for_apply_count", ""))
                + ",open_value:"
                + str(historical_seed_strict_blind_replacement_operator_action_board_summary.get("open_operator_value_count", ""))
                + ",open_evidence:"
                + str(historical_seed_strict_blind_replacement_operator_action_board_summary.get("open_evidence_ref_count", ""))
                + ",open_clearance:"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "open_operator_clearance_count", ""
                    )
                )
                + ",missing_by_field:"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "replacement_target_id_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "replacement_benchmark_id_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "target_identity_non_current_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "prediction_created_at_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "native_release_date_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "prediction_before_native_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "public_template_false_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "other_team_false_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "post_release_false_missing_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                        "operator_clearance_value_missing_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_promotion_gate",
            "Strict-blind replacement promotion gate for competitive proof entry",
            _text(
                historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                    "strict_blind_replacement_promotion_gate_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_promotion_gate_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                    "ready_for_competitive_proof_count"
                )
            ),
            blocked_count=(
                _int(
                    historical_seed_strict_blind_replacement_promotion_gate_summary.get("slot_count")
                )
                - _int(
                    historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                        "ready_for_competitive_proof_count"
                    )
                )
            ),
            total_count=_int(historical_seed_strict_blind_replacement_promotion_gate_summary.get("slot_count")),
            next_action=_text(historical_seed_strict_blind_replacement_promotion_gate_summary.get("first_next_action")),
            blockers=(
                "ready:"
                + str(
                    historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                        "ready_for_competitive_proof_count", ""
                    )
                )
                + ",awaiting_file:"
                + str(historical_seed_strict_blind_replacement_promotion_gate_summary.get("awaiting_file_evidence_count", ""))
                + ",awaiting_operator:"
                + str(
                    historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                        "awaiting_operator_values_count", ""
                    )
                )
                + ",awaiting_apply:"
                + str(historical_seed_strict_blind_replacement_promotion_gate_summary.get("awaiting_apply_count", ""))
                + ",awaiting_intake:"
                + str(
                    historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                        "awaiting_intake_preflight_count", ""
                    )
                )
                + ",blocked_review:"
                + str(historical_seed_strict_blind_replacement_promotion_gate_summary.get("blocked_review_count", ""))
                + ",complete_slots:"
                + str(historical_seed_strict_blind_replacement_promotion_gate_summary.get("intake_ready_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_promotion_gate_summary.get("file_complete_slot_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_promotion_gate_summary.get("operator_complete_slot_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_cycle",
            "Strict-blind replacement cycle across queue, evidence, quality, operator, action-board, and promotion gates",
            _text(
                historical_seed_strict_blind_replacement_cycle_summary.get(
                    "strict_blind_replacement_cycle_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_cycle_json,
            ready_count=_int(historical_seed_strict_blind_replacement_cycle_summary.get("promotion_ready_count")),
            blocked_count=(
                _int(historical_seed_strict_blind_replacement_cycle_summary.get("slot_count"))
                - _int(historical_seed_strict_blind_replacement_cycle_summary.get("promotion_ready_count"))
            ),
            total_count=_int(historical_seed_strict_blind_replacement_cycle_summary.get("slot_count")),
            next_action=_text(historical_seed_strict_blind_replacement_cycle_summary.get("first_next_action")),
            blockers=(
                "stage:"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("first_blocking_stage", ""))
                + ",promotion:"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("promotion_ready_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("slot_count", ""))
                + ",files:"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("evidence_file_present_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("evidence_file_missing_count", ""))
                + ",quality:"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("quality_ready_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("quality_awaiting_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("quality_blocked_count", ""))
                + ",operator_awaiting:"
                + str(historical_seed_strict_blind_replacement_cycle_summary.get("operator_awaiting_value_count", ""))
                + ",operator_board:"
                + str(
                    historical_seed_strict_blind_replacement_cycle_summary.get(
                        "operator_action_board_open_value_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_cycle_summary.get(
                        "operator_action_board_open_evidence_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_cycle_summary.get(
                        "operator_action_board_open_clearance_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_first_slot_kit",
            "First strict-blind replacement slot evidence and operator execution kit",
            _text(
                historical_seed_strict_blind_replacement_first_slot_kit_summary.get(
                    "strict_blind_replacement_first_slot_kit_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_first_slot_kit_json,
            ready_count=(
                _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_ready_count"))
                + _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_ready_count"))
            ),
            blocked_count=(
                _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_open_count"))
                + _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_open_count"))
                + _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_blocked_count"))
                + _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_blocked_count"))
            ),
            total_count=(
                _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_action_count"))
                + _int(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_action_count"))
            ),
            next_action=_text(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("first_next_action")),
            blockers=(
                "benchmark:"
                + str(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("required_benchmark_id", ""))
                + ",evidence:"
                + str(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_ready_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_open_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_blocked_count", ""))
                + ",operator:"
                + str(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_ready_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_open_count", ""))
                + "/"
                + str(historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_blocked_count", ""))
                + ",operator_open:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_kit_summary.get(
                        "operator_open_value_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_kit_summary.get(
                        "operator_open_evidence_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_kit_summary.get(
                        "operator_open_clearance_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_first_slot_local_candidate_board",
            "Local candidate source board for the first strict-blind replacement slot",
            _text(
                historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                    "strict_blind_replacement_first_slot_local_candidate_board_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_first_slot_local_candidate_board_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                    "ready_for_first_slot_count"
                )
            ),
            blocked_count=(
                _int(historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get("candidate_count"))
                - _int(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "ready_for_first_slot_count"
                    )
                )
            ),
            total_count=_int(
                historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get("candidate_count")
            ),
            next_action=_text(
                historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                    "first_review_next_action"
                )
            ),
            blockers=(
                "candidates:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "ready_for_first_slot_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "strict_blind_eligible_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "material_present_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "candidate_count", ""
                    )
                )
                + ",present:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "prediction_present_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "native_present_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "native_authority_present_count", ""
                    )
                )
                + ",blocked:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "blocked_chronology_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "blocked_no_leak_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "blocked_ablation_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                        "blocked_calibration_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board",
            "Repair action board for first strict-blind replacement slot local candidates",
            _text(
                historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                    "strict_blind_replacement_first_slot_candidate_repair_board_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_json,
            ready_count=0,
            blocked_count=(
                _int(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "open_repair_action_count"
                    )
                )
                + _int(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "blocked_action_count"
                    )
                )
            ),
            total_count=_int(
                historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get("action_count")
            ),
            next_action=_text(
                historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                    "first_next_action"
                )
            ),
            blockers=(
                "actions:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "open_repair_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "blocked_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "action_count", ""
                    )
                )
                + ",classes:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "chronology_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "no_leak_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "ablation_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "calibration_action_count", ""
                    )
                )
                + ",source:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "prediction_file_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "native_file_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "native_authority_action_count", ""
                    )
                )
                + ",eligibility:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                        "eligibility_action_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board",
            "Feasibility gate for first strict-blind replacement slot repair actions",
            _text(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "strict_blind_replacement_first_slot_repair_feasibility_board_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "repairable_operator_source_required_count"
                )
            )
            + _int(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "repairable_operator_evidence_required_count"
                )
            )
            + _int(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "needs_chronology_date_evidence_count"
                )
            ),
            blocked_count=_int(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "external_pre_native_artifact_required_action_count"
                )
            )
            + _int(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "blocked_by_primary_repairs_count"
                )
            ),
            total_count=_int(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "action_count"
                )
            ),
            next_action=_text(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "first_external_next_route"
                )
            )
            or _text(
                historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                    "first_actionable_required_input"
                )
            ),
            blockers=(
                "post_native:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "not_repairable_with_current_prediction_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "blocked_by_post_native_prediction_count", ""
                    )
                )
                + ",external:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "external_pre_native_artifact_required_action_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "external_pre_native_artifact_required_target_count", ""
                    )
                )
                + ",repairable:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "repairable_operator_source_required_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "repairable_operator_evidence_required_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "needs_chronology_date_evidence_count", ""
                    )
                )
                + ",primary:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                        "blocked_by_primary_repairs_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_first_slot_source_route_board",
            "Source-route decision board for the first strict-blind replacement slot",
            _text(
                historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                    "strict_blind_replacement_first_slot_source_route_board_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_first_slot_source_route_board_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                    "allowed_for_first_slot_count"
                )
            ),
            blocked_count=_int(
                historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                    "in_scope_external_required_count"
                )
            ),
            total_count=_int(
                historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get("route_count")
            ),
            next_action=_text(
                historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                    "first_external_next_action"
                )
            ),
            blockers=(
                "scope:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "in_scope_route_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "out_of_scope_route_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "route_count", ""
                    )
                )
                + ",allowed:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "allowed_for_first_slot_count", ""
                    )
                )
                + ",external:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "in_scope_external_required_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "in_scope_external_action_count", ""
                    )
                )
                + ",out_scope_repair:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "out_of_scope_source_required_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                        "out_of_scope_date_required_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates",
            "Official CASP15/16 archive source candidates for the first strict-blind monomer slot",
            _text(
                historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                    "strict_blind_replacement_first_slot_official_archive_source_candidates_status"
                )
            ),
            args.historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_json,
            ready_count=_int(
                historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                    "ready_candidate_count"
                )
            ),
            blocked_count=_int(
                historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                    "blocked_candidate_count"
                )
            ),
            total_count=_int(
                historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                    "candidate_count"
                )
            ),
            next_action=(
                "keep official archive submissions in the baseline replay lane; source internal pre-native predictions separately"
            ),
            blockers=(
                "sources:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "source_count", ""
                    )
                )
                + ",candidates:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "ready_candidate_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "blocked_candidate_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "candidate_count", ""
                    )
                )
                + ",native:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "native_authority_ready_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "native_authority_lookup_required_count", ""
                    )
                )
                + ",pdb:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "native_pdb_download_ready_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "native_mmcif_only_count", ""
                    )
                )
                + ",metadata:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "targetlist_metadata_present_count", ""
                    )
                )
                + ",capri_deferred:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "targetlist_capri_marker_count", ""
                    )
                )
                + ",cat:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "regular_monomer_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "domain_subunit_count", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "variant_count", ""
                    )
                )
                + ",first:"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "first_ready_competition", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "first_ready_target_id", ""
                    )
                )
                + "/"
                + str(
                    historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                        "first_ready_native_pdb_code", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_official_archive_baseline_lane",
            "Official CASP archive baseline replay lane kept outside strict-blind competitive proof",
            _text(historical_seed_official_archive_baseline_lane_summary.get("official_archive_baseline_lane_status")),
            args.historical_seed_official_archive_baseline_lane_json,
            ready_count=_int(historical_seed_official_archive_baseline_lane_summary.get("ready_count")),
            blocked_count=_int(historical_seed_official_archive_baseline_lane_summary.get("blocked_count")),
            total_count=_int(historical_seed_official_archive_baseline_lane_summary.get("baseline_candidate_count")),
            next_action=_text(historical_seed_official_archive_baseline_lane_summary.get("next_action")),
            blockers=(
                "source_ready:"
                + str(historical_seed_official_archive_baseline_lane_summary.get("source_ready_candidate_count", ""))
                + "/"
                + str(historical_seed_official_archive_baseline_lane_summary.get("source_candidate_count", ""))
                + ",proof_eligible:"
                + str(historical_seed_official_archive_baseline_lane_summary.get("competitive_proof_eligible_count", ""))
                + ",strict_blind_blocked:"
                + str(historical_seed_official_archive_baseline_lane_summary.get("strict_blind_import_blocked_count", ""))
                + ",other_team_baseline:"
                + str(historical_seed_official_archive_baseline_lane_summary.get("other_team_model_baseline_only_count", ""))
                + ",first:"
                + str(historical_seed_official_archive_baseline_lane_summary.get("first_competition", ""))
                + "/"
                + str(historical_seed_official_archive_baseline_lane_summary.get("first_target_id", ""))
                + "/"
                + str(historical_seed_official_archive_baseline_lane_summary.get("first_native_pdb_code", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_first_slot_source_bridge",
            "First strict-blind slot source bridge for native authority and operator-only fields",
            _text(strict_blind_first_slot_source_bridge_summary.get("source_bridge_status")),
            args.strict_blind_first_slot_source_bridge_json,
            ready_count=_int(strict_blind_first_slot_source_bridge_summary.get("native_authority_bridge_ready_count")),
            blocked_count=(
                _int(strict_blind_first_slot_source_bridge_summary.get("operator_only_field_count"))
                + _int(strict_blind_first_slot_source_bridge_summary.get("internal_prediction_blocked_count"))
            ),
            total_count=_int(strict_blind_first_slot_source_bridge_summary.get("bridge_row_count")),
            next_action=_text(strict_blind_first_slot_source_bridge_summary.get("first_next_action")),
            blockers=(
                "official:"
                + str(strict_blind_first_slot_source_bridge_summary.get("official_ready_candidate_count", ""))
                + "/"
                + str(strict_blind_first_slot_source_bridge_summary.get("official_candidate_count", ""))
                + ",native_bridge:"
                + str(strict_blind_first_slot_source_bridge_summary.get("native_authority_bridge_ready_count", ""))
                + ",baseline_only:"
                + str(strict_blind_first_slot_source_bridge_summary.get("official_prediction_baseline_only_count", ""))
                + ",strict_blocked:"
                + str(strict_blind_first_slot_source_bridge_summary.get("strict_blind_import_blocked_count", ""))
                + ",operator_only:"
                + str(strict_blind_first_slot_source_bridge_summary.get("operator_only_field_count", ""))
                + ",internal_prediction_blocked:"
                + str(strict_blind_first_slot_source_bridge_summary.get("internal_prediction_blocked_count", ""))
                + ",auto_apply:"
                + str(strict_blind_first_slot_source_bridge_summary.get("auto_apply_allowed_count", ""))
                + ",first:"
                + str(strict_blind_first_slot_source_bridge_summary.get("first_candidate_competition", ""))
                + "/"
                + str(strict_blind_first_slot_source_bridge_summary.get("first_candidate_target_id", ""))
                + "/"
                + str(strict_blind_first_slot_source_bridge_summary.get("first_candidate_native_pdb_code", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_internal_prediction_source_audit",
            "First strict-blind slot internal prediction source audit and operator template",
            _text(strict_blind_internal_prediction_source_audit_summary.get("internal_prediction_source_audit_status")),
            args.strict_blind_internal_prediction_source_audit_json,
            ready_count=_int(strict_blind_internal_prediction_source_audit_summary.get("allowed_internal_source_count")),
            blocked_count=_int(
                strict_blind_internal_prediction_source_audit_summary.get("internal_prediction_blocked_count")
            ),
            total_count=_int(strict_blind_internal_prediction_source_audit_summary.get("row_count")),
            next_action=_text(strict_blind_internal_prediction_source_audit_summary.get("next_action")),
            blockers=(
                "local:"
                + str(strict_blind_internal_prediction_source_audit_summary.get("local_strict_blind_eligible_count", ""))
                + "/"
                + str(strict_blind_internal_prediction_source_audit_summary.get("local_candidate_count", ""))
                + ",routes:"
                + str(strict_blind_internal_prediction_source_audit_summary.get("source_route_allowed_count", ""))
                + "/"
                + str(strict_blind_internal_prediction_source_audit_summary.get("source_route_count", ""))
                + ",official_blocked:"
                + str(strict_blind_internal_prediction_source_audit_summary.get("official_strict_blind_blocked_count", ""))
                + ",native_bridge:"
                + str(strict_blind_internal_prediction_source_audit_summary.get("native_authority_bridge_ready_count", ""))
                + ",internal_blocked:"
                + str(strict_blind_internal_prediction_source_audit_summary.get("internal_prediction_blocked_count", ""))
                + ",template:"
                + str(strict_blind_internal_prediction_source_audit_summary.get("template_count", ""))
                + ",first:"
                + _text(strict_blind_internal_prediction_source_audit_summary.get("first_blocker"))
            ),
        ),
        _artifact_row(
            "strict_blind_internal_prediction_source_gate",
            "First strict-blind slot internal prediction source manifest and PDB gate",
            _text(strict_blind_internal_prediction_source_gate_summary.get("internal_prediction_source_gate_status")),
            args.strict_blind_internal_prediction_source_gate_json,
            ready_count=_int(strict_blind_internal_prediction_source_gate_summary.get("pass_count")),
            blocked_count=_int(strict_blind_internal_prediction_source_gate_summary.get("blocked_count")),
            total_count=_int(strict_blind_internal_prediction_source_gate_summary.get("check_count")),
            next_action=_text(strict_blind_internal_prediction_source_gate_summary.get("first_next_action")),
            blockers=(
                "manifest_rows:"
                + str(strict_blind_internal_prediction_source_gate_summary.get("manifest_row_count", ""))
                + ",source:"
                + str(strict_blind_internal_prediction_source_gate_summary.get("source_id", ""))
                + ",prediction:"
                + str(strict_blind_internal_prediction_source_gate_summary.get("manifest_prediction_pdb", ""))
                + ",dropzone:"
                + str(strict_blind_internal_prediction_source_gate_summary.get("prediction_dropzone", ""))
                + ",first:"
                + str(strict_blind_internal_prediction_source_gate_summary.get("first_blocked_check", ""))
                + "/"
                + str(strict_blind_internal_prediction_source_gate_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_source_gate_field_board",
            "First strict-blind slot source-gate unique field action board",
            _text(strict_blind_source_gate_field_board_summary.get("source_gate_field_board_status")),
            args.strict_blind_source_gate_field_board_json,
            ready_count=0,
            blocked_count=_int(strict_blind_source_gate_field_board_summary.get("field_action_count")),
            total_count=_int(strict_blind_source_gate_field_board_summary.get("field_action_count")),
            next_action=_text(strict_blind_source_gate_field_board_summary.get("first_next_action")),
            blockers=(
                "checks:"
                + str(strict_blind_source_gate_field_board_summary.get("source_gate_pass_count", ""))
                + "/"
                + str(strict_blind_source_gate_field_board_summary.get("source_gate_blocked_count", ""))
                + "/"
                + str(strict_blind_source_gate_field_board_summary.get("source_gate_check_count", ""))
                + ",actions:"
                + str(strict_blind_source_gate_field_board_summary.get("manifest_value_action_count", ""))
                + "/"
                + str(strict_blind_source_gate_field_board_summary.get("file_action_count", ""))
                + "/"
                + str(strict_blind_source_gate_field_board_summary.get("manifest_file_action_count", ""))
                + "/"
                + str(strict_blind_source_gate_field_board_summary.get("field_action_count", ""))
                + ",covered:"
                + str(strict_blind_source_gate_field_board_summary.get("blocked_check_covered_count", ""))
                + ",first:"
                + str(strict_blind_source_gate_field_board_summary.get("first_field_key", ""))
                + "/"
                + str(strict_blind_source_gate_field_board_summary.get("first_blockers", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_source_gate_operator_packet",
            "First strict-blind slot source-gate operator value packet",
            _text(strict_blind_source_gate_operator_packet_summary.get("source_gate_operator_packet_status")),
            args.strict_blind_source_gate_operator_packet_json,
            ready_count=_int(strict_blind_source_gate_operator_packet_summary.get("operator_ready_count")),
            blocked_count=_int(strict_blind_source_gate_operator_packet_summary.get("operator_awaiting_count")),
            total_count=_int(strict_blind_source_gate_operator_packet_summary.get("field_action_count")),
            next_action=_text(strict_blind_source_gate_operator_packet_summary.get("first_next_action")),
            blockers=(
                "operator:"
                + str(strict_blind_source_gate_operator_packet_summary.get("operator_ready_count", ""))
                + "/"
                + str(strict_blind_source_gate_operator_packet_summary.get("operator_awaiting_count", ""))
                + "/"
                + str(strict_blind_source_gate_operator_packet_summary.get("field_action_count", ""))
                + ",patch:"
                + str(strict_blind_source_gate_operator_packet_summary.get("patch_ready_count", ""))
                + "/"
                + str(strict_blind_source_gate_operator_packet_summary.get("patch_awaiting_count", ""))
                + ",actions:"
                + str(strict_blind_source_gate_operator_packet_summary.get("manifest_patch_count", ""))
                + "/"
                + str(strict_blind_source_gate_operator_packet_summary.get("file_copy_count", ""))
                + "/"
                + str(strict_blind_source_gate_operator_packet_summary.get("derived_check_count", ""))
                + ",first:"
                + str(strict_blind_source_gate_operator_packet_summary.get("first_field_key", ""))
                + "/"
                + str(strict_blind_source_gate_operator_packet_summary.get("first_operator_status", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_source_gate_source_request_packet",
            "First strict-blind slot source-gate source acquisition requests",
            _text(strict_blind_source_gate_source_request_packet_summary.get("source_request_packet_status")),
            args.strict_blind_source_gate_source_request_packet_json,
            ready_count=0,
            blocked_count=_int(strict_blind_source_gate_source_request_packet_summary.get("request_count")),
            total_count=_int(strict_blind_source_gate_source_request_packet_summary.get("request_count")),
            next_action=_text(strict_blind_source_gate_source_request_packet_summary.get("first_next_action")),
            blockers=(
                "requests:"
                + str(strict_blind_source_gate_source_request_packet_summary.get("pre_native_source_required_count", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("candidate_replacement_required_count", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("operator_evidence_repair_required_count", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("request_count", ""))
                + ",scope:"
                + str(strict_blind_source_gate_source_request_packet_summary.get("monomer_request_count", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("complex_request_count", ""))
                + ",templates:"
                + str(strict_blind_source_gate_source_request_packet_summary.get("operator_template_ready_count", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("operator_template_awaiting_count", ""))
                + ",fields:"
                + str(strict_blind_source_gate_source_request_packet_summary.get("operator_field_filled_count", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("operator_field_missing_count", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("operator_field_count", ""))
                + ",first:"
                + str(strict_blind_source_gate_source_request_packet_summary.get("first_request_id", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("first_request_target_id", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("first_request_kind", ""))
                + "/"
                + str(strict_blind_source_gate_source_request_packet_summary.get("first_request_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_source_request_fulfillment_gate",
            "First strict-blind slot source request fulfillment gate",
            _text(strict_blind_source_request_fulfillment_gate_summary.get("source_request_fulfillment_gate_status")),
            args.strict_blind_source_request_fulfillment_gate_json,
            ready_count=_int(strict_blind_source_request_fulfillment_gate_summary.get("ready_request_count")),
            blocked_count=_int(strict_blind_source_request_fulfillment_gate_summary.get("blocked_request_count")),
            total_count=_int(strict_blind_source_request_fulfillment_gate_summary.get("request_count")),
            next_action=_text(strict_blind_source_request_fulfillment_gate_summary.get("first_next_action")),
            blockers=(
                "fields:"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("operator_field_filled_count", ""))
                + "/"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("operator_field_missing_count", ""))
                + "/"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("operator_field_count", ""))
                + ",evidence:"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("operator_evidence_ref_count", ""))
                + "/"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("operator_evidence_ref_missing_count", ""))
                + ",validation:"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("prediction_pdb_valid_count", ""))
                + "/"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("chronology_pass_count", ""))
                + "/"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("internal_source_pass_count", ""))
                + ",first:"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("first_blocked_request_id", ""))
                + "/"
                + str(strict_blind_source_request_fulfillment_gate_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_source_request_operator_fill_worklist",
            "First strict-blind slot source request operator fill worklist",
            _text(strict_blind_source_request_operator_fill_worklist_summary.get("source_request_operator_fill_worklist_status")),
            args.strict_blind_source_request_operator_fill_worklist_json,
            ready_count=_int(strict_blind_source_request_operator_fill_worklist_summary.get("field_ready_count")),
            blocked_count=_int(strict_blind_source_request_operator_fill_worklist_summary.get("operator_value_missing_count")),
            total_count=_int(strict_blind_source_request_operator_fill_worklist_summary.get("field_action_count")),
            next_action=_text(strict_blind_source_request_operator_fill_worklist_summary.get("first_next_action")),
            blockers=(
                "fields:"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("field_ready_count", ""))
                + "/"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("operator_value_missing_count", ""))
                + "/"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("operator_evidence_missing_count", ""))
                + "/"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("field_action_count", ""))
                + ",candidate:"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("candidate_replacement_field_count", ""))
                + ",first:"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("first_fill_id", ""))
                + "/"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("first_request_id", ""))
                + "/"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("first_field_key", ""))
                + "/"
                + str(strict_blind_source_request_operator_fill_worklist_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_source_request_operator_sync_plan",
            "First strict-blind slot source request to operator packet sync plan",
            _text(strict_blind_source_request_operator_sync_plan_summary.get("source_request_operator_sync_plan_status")),
            args.strict_blind_source_request_operator_sync_plan_json,
            ready_count=_int(strict_blind_source_request_operator_sync_plan_summary.get("ready_sync_action_count")),
            blocked_count=_int(strict_blind_source_request_operator_sync_plan_summary.get("blocked_sync_action_count")),
            total_count=_int(strict_blind_source_request_operator_sync_plan_summary.get("sync_action_count")),
            next_action=_text(strict_blind_source_request_operator_sync_plan_summary.get("first_next_action")),
            blockers=(
                "mode:"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("sync_mode", ""))
                + ",fulfillment:"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("ready_request_count", ""))
                + "/"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("blocked_request_count", ""))
                + ",actions:"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("ready_sync_action_count", ""))
                + "/"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("blocked_sync_action_count", ""))
                + "/"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("applied_sync_action_count", ""))
                + "/"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("sync_action_count", ""))
                + ",selected:"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("selected_request_id", ""))
                + "/"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("selected_target_id", ""))
                + ",first:"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("first_action_id", ""))
                + "/"
                + str(strict_blind_source_request_operator_sync_plan_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_source_request_closure_board",
            "First strict-blind slot source request closure board",
            _text(
                strict_blind_source_request_closure_board_summary.get(
                    "strict_blind_source_request_closure_board_status"
                )
            ),
            args.strict_blind_source_request_closure_board_json,
            ready_count=_int(strict_blind_source_request_closure_board_summary.get("ready_stage_count")),
            blocked_count=_int(strict_blind_source_request_closure_board_summary.get("blocked_stage_count")),
            total_count=_int(strict_blind_source_request_closure_board_summary.get("stage_count")),
            next_action=_text(strict_blind_source_request_closure_board_summary.get("next_action")),
            blockers=(
                "required:"
                + str(strict_blind_source_request_closure_board_summary.get("required_benchmark_id", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("required_target_id", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("required_scope", ""))
                + ",stages:"
                + str(strict_blind_source_request_closure_board_summary.get("ready_stage_count", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("blocked_stage_count", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("stage_count", ""))
                + ",statuses:"
                + str(strict_blind_source_request_closure_board_summary.get("source_request_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("fulfillment_gate_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("operator_fill_worklist_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("operator_sync_plan_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("source_gate_operator_packet_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("internal_prediction_source_gate_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("internal_prediction_apply_plan_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("first_slot_closure_kit_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("batch_closure_runway_status", ""))
                + ",first:"
                + str(strict_blind_source_request_closure_board_summary.get("first_blocked_stage_id", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("first_blocked_stage_status", ""))
                + "/"
                + str(strict_blind_source_request_closure_board_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_internal_prediction_source_apply_plan",
            "First strict-blind slot internal prediction source apply plan",
            _text(
                strict_blind_internal_prediction_source_apply_plan_summary.get(
                    "internal_prediction_source_apply_plan_status"
                )
            ),
            args.strict_blind_internal_prediction_source_apply_plan_json,
            ready_count=_int(strict_blind_internal_prediction_source_apply_plan_summary.get("ready_action_count")),
            blocked_count=_int(strict_blind_internal_prediction_source_apply_plan_summary.get("blocked_action_count")),
            total_count=_int(strict_blind_internal_prediction_source_apply_plan_summary.get("action_count")),
            next_action=_text(strict_blind_internal_prediction_source_apply_plan_summary.get("first_next_action")),
            blockers=(
                "gate:"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("gate_status", ""))
                + ",file/operator/supp:"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("file_action_count", ""))
                + "/"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("operator_value_action_count", ""))
                + "/"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("supplemental_evidence_action_count", ""))
                + ",prediction:"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("prediction_source", ""))
                + "->"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("prediction_destination", ""))
                + ",first:"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("first_blocked_action_id", ""))
                + "/"
                + str(strict_blind_internal_prediction_source_apply_plan_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_first_slot_closure_kit",
            "First strict-blind slot closure kit",
            _text(strict_blind_first_slot_closure_kit_summary.get("first_slot_closure_kit_status")),
            args.strict_blind_first_slot_closure_kit_json,
            ready_count=_int(strict_blind_first_slot_closure_kit_summary.get("step_ready_count")),
            blocked_count=_int(strict_blind_first_slot_closure_kit_summary.get("step_blocked_count")),
            total_count=_int(strict_blind_first_slot_closure_kit_summary.get("step_count")),
            next_action=_text(strict_blind_first_slot_closure_kit_summary.get("first_next_action")),
            blockers=(
                "source/apply/dropzone/operator/intake:"
                + str(strict_blind_first_slot_closure_kit_summary.get("source_gate_status", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("apply_plan_status", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("dropzone_status", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("operator_gate_status", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("intake_preflight_status", ""))
                + ",fills:"
                + str(strict_blind_first_slot_closure_kit_summary.get("source_gate_fill_count", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("source_request_fill_count", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("file_fill_count", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("operator_fill_count", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("fill_item_count", ""))
                + ",first:"
                + str(strict_blind_first_slot_closure_kit_summary.get("first_blocked_step", ""))
                + "/"
                + str(strict_blind_first_slot_closure_kit_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "strict_blind_batch_closure_runway",
            "Strict-blind 40-slot batch closure runway",
            _text(strict_blind_batch_closure_runway_summary.get("batch_closure_runway_status")),
            args.strict_blind_batch_closure_runway_json,
            ready_count=_int(strict_blind_batch_closure_runway_summary.get("ready_slot_count")),
            blocked_count=_int(strict_blind_batch_closure_runway_summary.get("blocked_slot_count")),
            total_count=_int(strict_blind_batch_closure_runway_summary.get("slot_count")),
            next_action=_text(strict_blind_batch_closure_runway_summary.get("first_next_action")),
            blockers=(
                "source/evidence/operator/intake:"
                + str(strict_blind_batch_closure_runway_summary.get("source_gate_blocked_count", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("evidence_file_blocked_count", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("operator_value_blocked_count", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("intake_preflight_blocked_count", ""))
                + ",files:"
                + str(strict_blind_batch_closure_runway_summary.get("file_present_count", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("file_missing_count", ""))
                + ",operators:"
                + str(strict_blind_batch_closure_runway_summary.get("operator_ready_count", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("operator_open_count", ""))
                + ",first:"
                + str(strict_blind_batch_closure_runway_summary.get("first_blocked_rank", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("first_blocked_benchmark_id", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("first_blocking_stage", ""))
                + "/"
                + str(strict_blind_batch_closure_runway_summary.get("first_blocker", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_ablation_candidate_manifests",
            "Fail-closed ablation candidate manifests for historical seed rows",
            _text(historical_seed_ablation_candidate_manifests_summary.get("ablation_candidate_status")),
            args.historical_seed_ablation_candidate_manifests_json,
            ready_count=_int(
                historical_seed_ablation_candidate_manifests_summary.get(
                    "ready_for_operator_reference_count"
                )
            ),
            blocked_count=_int(
                historical_seed_ablation_candidate_manifests_summary.get(
                    "operator_review_required_count"
                )
            ),
            total_count=_int(historical_seed_ablation_candidate_manifests_summary.get("seed_row_count")),
            next_action=_text(historical_seed_ablation_candidate_manifests_summary.get("first_next_action")),
            blockers=(
                "selected:"
                + str(historical_seed_ablation_candidate_manifests_summary.get("selected_prediction_present_count", ""))
                + ",native:"
                + str(historical_seed_ablation_candidate_manifests_summary.get("native_reference_present_count", ""))
                + ",manifests:"
                + str(historical_seed_ablation_candidate_manifests_summary.get("candidate_manifest_count", ""))
                + ",baseline_candidates:"
                + str(historical_seed_ablation_candidate_manifests_summary.get("baseline_candidate_present_count", ""))
                + ",layer_gaps:"
                + str(historical_seed_ablation_candidate_manifests_summary.get("layer_evidence_gap_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_ablation_gap_repair_plan",
            "Ablation gap repair plan separating real layer candidates from top-5 review decoys",
            _text(historical_seed_ablation_gap_repair_plan_summary.get("ablation_gap_repair_status")),
            args.historical_seed_ablation_gap_repair_plan_json,
            ready_count=_int(historical_seed_ablation_gap_repair_plan_summary.get("ready_for_operator_review_count")),
            blocked_count=(
                _int(historical_seed_ablation_gap_repair_plan_summary.get("gap_repair_required_count"))
                + _int(historical_seed_ablation_gap_repair_plan_summary.get("blocked_core_ablation_input_count"))
            ),
            total_count=_int(historical_seed_ablation_gap_repair_plan_summary.get("seed_row_count")),
            next_action=_text(historical_seed_ablation_gap_repair_plan_summary.get("first_next_action")),
            blockers=(
                "real:"
                + str(historical_seed_ablation_gap_repair_plan_summary.get("real_ablation_candidate_count", ""))
                + ",missing_real:"
                + str(historical_seed_ablation_gap_repair_plan_summary.get("missing_real_ablation_candidate_count", ""))
                + ",top5_decoys:"
                + str(historical_seed_ablation_gap_repair_plan_summary.get("top5_review_decoy_count", ""))
                + ",top5_copy:"
                + str(historical_seed_ablation_gap_repair_plan_summary.get("top5_selected_copy_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_top5_candidate_pools",
            "Local top-5 candidate pools for historical seed model-selection calibration",
            _text(historical_seed_top5_candidate_pools_summary.get("top5_candidate_pool_status")),
            args.historical_seed_top5_candidate_pools_json,
            ready_count=_int(historical_seed_top5_candidate_pools_summary.get("complete_top5_pool_count")),
            blocked_count=_int(historical_seed_top5_candidate_pools_summary.get("blocked_selected_source_count")),
            total_count=_int(historical_seed_top5_candidate_pools_summary.get("seed_row_count")),
            next_action=_text(historical_seed_top5_candidate_pools_summary.get("first_next_action")),
            blockers=(
                "models:"
                + str(historical_seed_top5_candidate_pools_summary.get("candidate_model_count", ""))
                + ",complete_top5:"
                + str(historical_seed_top5_candidate_pools_summary.get("complete_top5_pool_count", ""))
                + ",gaps:"
                + str(historical_seed_top5_candidate_pools_summary.get("candidate_pool_gap_count", ""))
                + ",generated:"
                + str(historical_seed_top5_candidate_pools_summary.get("generated_perturbation_count", ""))
                + ",source_blocked:"
                + str(historical_seed_top5_candidate_pools_summary.get("blocked_selected_source_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_internal_score_candidates",
            "Internal score candidates for historical seed top-5 model-selection calibration",
            _text(historical_seed_internal_score_candidates_summary.get("internal_score_candidate_status")),
            args.historical_seed_internal_score_candidates_json,
            ready_count=_int(
                historical_seed_internal_score_candidates_summary.get("top5_scored_ready_count")
            ),
            blocked_count=_int(
                historical_seed_internal_score_candidates_summary.get("blocked_candidate_input_count")
            ),
            total_count=_int(historical_seed_internal_score_candidates_summary.get("seed_row_count")),
            next_action=_text(historical_seed_internal_score_candidates_summary.get("first_next_action")),
            blockers=(
                "models:"
                + str(historical_seed_internal_score_candidates_summary.get("candidate_count", ""))
                + ",scored:"
                + str(historical_seed_internal_score_candidates_summary.get("scored_candidate_count", ""))
                + ",top5_scored:"
                + str(historical_seed_internal_score_candidates_summary.get("top5_scored_ready_count", ""))
                + ",selected_scores:"
                + str(historical_seed_internal_score_candidates_summary.get("selected_score_candidate_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_native_oracle_metric_candidates",
            "Native metric candidates for historical seed top-5 model-selection calibration",
            _text(historical_seed_native_oracle_metric_candidates_summary.get("native_metric_candidate_status")),
            args.historical_seed_native_oracle_metric_candidates_json,
            ready_count=_int(
                historical_seed_native_oracle_metric_candidates_summary.get("top5_native_metric_ready_count")
            ),
            blocked_count=_int(
                historical_seed_native_oracle_metric_candidates_summary.get("blocked_candidate_input_count")
            ),
            total_count=_int(historical_seed_native_oracle_metric_candidates_summary.get("seed_row_count")),
            next_action=_text(historical_seed_native_oracle_metric_candidates_summary.get("first_next_action")),
            blockers=(
                "models:"
                + str(historical_seed_native_oracle_metric_candidates_summary.get("candidate_count", ""))
                + ",metric_ready:"
                + str(historical_seed_native_oracle_metric_candidates_summary.get("metric_candidate_count", ""))
                + ",top5_native:"
                + str(historical_seed_native_oracle_metric_candidates_summary.get("top5_native_metric_ready_count", ""))
                + ",selected_native:"
                + str(historical_seed_native_oracle_metric_candidates_summary.get("selected_native_metric_candidate_count", ""))
                + ",best_native:"
                + str(historical_seed_native_oracle_metric_candidates_summary.get("best_native_metric_candidate_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_calibration_candidate_ledgers",
            "Fail-closed model-selection calibration candidate ledgers for historical seed rows",
            _text(historical_seed_calibration_candidate_ledgers_summary.get("calibration_candidate_status")),
            args.historical_seed_calibration_candidate_ledgers_json,
            ready_count=_int(
                historical_seed_calibration_candidate_ledgers_summary.get("ready_for_calibration_fill_count")
            ),
            blocked_count=_int(
                historical_seed_calibration_candidate_ledgers_summary.get("operator_review_required_count")
            ),
            total_count=_int(historical_seed_calibration_candidate_ledgers_summary.get("seed_row_count")),
            next_action=_text(historical_seed_calibration_candidate_ledgers_summary.get("first_next_action")),
            blockers=(
                "models:"
                + str(historical_seed_calibration_candidate_ledgers_summary.get("candidate_model_count", ""))
                + ",top5_ready:"
                + str(historical_seed_calibration_candidate_ledgers_summary.get("top5_candidate_pool_ready_count", ""))
                + ",selected_rank:"
                + str(historical_seed_calibration_candidate_ledgers_summary.get("selected_model_rank_candidate_count", ""))
                + ",native_metrics:"
                + str(historical_seed_calibration_candidate_ledgers_summary.get("native_oracle_metric_available_count", ""))
                + ",internal_scores:"
                + str(historical_seed_calibration_candidate_ledgers_summary.get("internal_score_available_count", ""))
                + ",open_fields:"
                + str(historical_seed_calibration_candidate_ledgers_summary.get("open_calibration_field_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_calibration_field_candidates",
            "Operator-review calibration field candidates from historical seed ledgers",
            _text(historical_seed_calibration_field_candidates_summary.get("calibration_field_candidate_status")),
            args.historical_seed_calibration_field_candidates_json,
            ready_count=_int(historical_seed_calibration_field_candidates_summary.get("ready_to_apply_row_count")),
            blocked_count=_int(historical_seed_calibration_field_candidates_summary.get("blocked_row_count")),
            total_count=_int(historical_seed_calibration_field_candidates_summary.get("seed_row_count")),
            next_action=_text(historical_seed_calibration_field_candidates_summary.get("first_next_action")),
            blockers=(
                "fields:"
                + str(historical_seed_calibration_field_candidates_summary.get("field_candidate_count", ""))
                + ",proposed:"
                + str(historical_seed_calibration_field_candidates_summary.get("proposed_field_count", ""))
                + ",matching:"
                + str(historical_seed_calibration_field_candidates_summary.get("already_matching_field_count", ""))
                + ",conflicts:"
                + str(historical_seed_calibration_field_candidates_summary.get("conflict_field_count", ""))
                + ",blocked_fields:"
                + str(historical_seed_calibration_field_candidates_summary.get("blocked_field_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_clearance_fill_candidate_packet",
            "Consolidated operator-review fill candidates for historical seed clearance fields",
            _text(historical_seed_clearance_fill_candidate_packet_summary.get("clearance_fill_candidate_status")),
            args.historical_seed_clearance_fill_candidate_packet_json,
            ready_count=_int(historical_seed_clearance_fill_candidate_packet_summary.get("partial_candidate_row_count")),
            blocked_count=_int(historical_seed_clearance_fill_candidate_packet_summary.get("blocked_row_count")),
            total_count=_int(historical_seed_clearance_fill_candidate_packet_summary.get("seed_row_count")),
            next_action=_text(historical_seed_clearance_fill_candidate_packet_summary.get("first_next_action")),
            blockers=(
                "fields:"
                + str(historical_seed_clearance_fill_candidate_packet_summary.get("field_count", ""))
                + ",proposed:"
                + str(historical_seed_clearance_fill_candidate_packet_summary.get("proposed_field_count", ""))
                + ",operator_required:"
                + str(historical_seed_clearance_fill_candidate_packet_summary.get("operator_required_field_count", ""))
                + ",blocked_fields:"
                + str(historical_seed_clearance_fill_candidate_packet_summary.get("blocked_field_count", ""))
                + ",calibration:"
                + str(historical_seed_clearance_fill_candidate_packet_summary.get("calibration_candidate_count", ""))
                + ",ablation:"
                + str(historical_seed_clearance_fill_candidate_packet_summary.get("ablation_candidate_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_clearance_execution_board",
            "Shortest-path execution board for the first cleared historical seed row",
            _text(historical_seed_clearance_execution_board_summary.get("execution_board_status")),
            args.historical_seed_clearance_execution_board_json,
            ready_count=_int(historical_seed_clearance_execution_board_summary.get("operator_no_leak_only_row_count")),
            blocked_count=_int(historical_seed_clearance_execution_board_summary.get("ablation_repair_required_row_count")),
            total_count=_int(historical_seed_clearance_execution_board_summary.get("seed_row_count")),
            next_action=_text(historical_seed_clearance_execution_board_summary.get("first_execution_next_action")),
            blockers=(
                "first:"
                + _text(historical_seed_clearance_execution_board_summary.get("first_execution_target_id"))
                + ",status:"
                + _text(historical_seed_clearance_execution_board_summary.get("first_execution_status"))
                + ",no_leak_fields:"
                + str(historical_seed_clearance_execution_board_summary.get("operator_no_leak_field_count", ""))
                + ",blocked_ablation:"
                + str(historical_seed_clearance_execution_board_summary.get("blocked_ablation_field_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_first_clearance_operator_kit",
            "Operator no-leak intake and promotion preview for the first historical seed row",
            _text(historical_seed_first_clearance_operator_kit_summary.get("first_clearance_kit_status")),
            args.historical_seed_first_clearance_operator_kit_json,
            ready_count=_int(historical_seed_first_clearance_operator_kit_summary.get("ready_candidate_field_count")),
            blocked_count=_int(historical_seed_first_clearance_operator_kit_summary.get("no_leak_field_count")),
            total_count=_int(historical_seed_first_clearance_operator_kit_summary.get("total_field_count")),
            next_action=_text(historical_seed_first_clearance_operator_kit_summary.get("next_action")),
            blockers=(
                "target:"
                + _text(historical_seed_first_clearance_operator_kit_summary.get("target_id"))
                + ",preview:"
                + _text(historical_seed_first_clearance_operator_kit_summary.get("promotion_preview_status"))
                + ",weak:"
                + str(historical_seed_first_clearance_operator_kit_summary.get("weak_hint_count", ""))
                + ",kit:"
                + _text(historical_seed_first_clearance_operator_kit_summary.get("kit_folder"))
            ),
        ),
        _artifact_row(
            "historical_seed_first_clearance_no_leak_gate",
            "Fail-closed readiness gate for the first historical seed no-leak operator intake",
            _text(
                historical_seed_first_clearance_no_leak_gate_summary.get(
                    "first_clearance_no_leak_gate_status"
                )
            ),
            args.historical_seed_first_clearance_no_leak_gate_json,
            ready_count=_int(historical_seed_first_clearance_no_leak_gate_summary.get("ready_field_count")),
            blocked_count=_int(
                historical_seed_first_clearance_no_leak_gate_summary.get("blocked_field_count")
            ),
            total_count=_int(historical_seed_first_clearance_no_leak_gate_summary.get("field_count")),
            next_action=_text(historical_seed_first_clearance_no_leak_gate_summary.get("next_action")),
            blockers=(
                "first:"
                + _text(historical_seed_first_clearance_no_leak_gate_summary.get("first_blocked_field"))
                + ",blocker:"
                + _text(historical_seed_first_clearance_no_leak_gate_summary.get("first_blocker"))
                + ",values_missing:"
                + str(
                    historical_seed_first_clearance_no_leak_gate_summary.get(
                        "operator_value_missing_count", ""
                    )
                )
                + ",clearance_missing:"
                + str(
                    historical_seed_first_clearance_no_leak_gate_summary.get(
                        "operator_clearance_missing_count", ""
                    )
                )
                + ",weak:"
                + str(historical_seed_first_clearance_no_leak_gate_summary.get("weak_hint_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_first_clearance_no_leak_evidence_packet",
            "Operator evidence collection packet for the first historical seed no-leak gate",
            _text(
                historical_seed_first_clearance_no_leak_evidence_packet_summary.get(
                    "first_clearance_no_leak_evidence_packet_status"
                )
            ),
            args.historical_seed_first_clearance_no_leak_evidence_packet_json,
            ready_count=_int(
                historical_seed_first_clearance_no_leak_evidence_packet_summary.get("ready_field_count")
            ),
            blocked_count=_int(
                historical_seed_first_clearance_no_leak_evidence_packet_summary.get("open_field_count")
            ),
            total_count=_int(historical_seed_first_clearance_no_leak_evidence_packet_summary.get("field_count")),
            next_action=_text(historical_seed_first_clearance_no_leak_evidence_packet_summary.get("next_action")),
            blockers=(
                "first:"
                + _text(historical_seed_first_clearance_no_leak_evidence_packet_summary.get("first_open_field"))
                + ",kind:"
                + _text(historical_seed_first_clearance_no_leak_evidence_packet_summary.get("first_open_kind"))
                + ",stubs:"
                + str(
                    historical_seed_first_clearance_no_leak_evidence_packet_summary.get(
                        "evidence_stub_count", ""
                    )
                )
                + ",weak:"
                + str(historical_seed_first_clearance_no_leak_evidence_packet_summary.get("weak_hint_count", ""))
                + ",folder:"
                + _text(historical_seed_first_clearance_no_leak_evidence_packet_summary.get("packet_folder"))
            ),
        ),
        _artifact_row(
            "historical_seed_first_clearance_no_leak_evidence_review_gate",
            "Review gate for filled first-clearance no-leak evidence packet values and stubs",
            _text(
                historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                    "first_clearance_no_leak_evidence_review_gate_status"
                )
            ),
            args.historical_seed_first_clearance_no_leak_evidence_review_gate_json,
            ready_count=_int(
                historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("ready_field_count")
            ),
            blocked_count=_int(
                historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                    "blocked_field_count"
                )
            ),
            total_count=_int(
                historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("field_count")
            ),
            next_action=_text(
                historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("next_action")
            ),
            blockers=(
                "first:"
                + _text(
                    historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                        "first_blocked_field"
                    )
                )
                + ",blocker:"
                + _text(
                    historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                        "first_blocker"
                    )
                )
                + ",template_missing:"
                + str(
                    historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                        "template_operator_value_missing_count", ""
                    )
                )
                + ",stub_evidence_missing:"
                + str(
                    historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                        "stub_evidence_missing_count", ""
                    )
                )
                + ",policy_blocked:"
                + str(
                    historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                        "policy_blocked_count", ""
                    )
                )
            ),
        ),
        _artifact_row(
            "historical_seed_first_clearance_no_leak_evidence_sync_plan",
            "Dry-run/apply plan from reviewed first-clearance no-leak evidence into the intake",
            _text(
                historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get(
                    "first_clearance_no_leak_evidence_sync_plan_status"
                )
            ),
            args.historical_seed_first_clearance_no_leak_evidence_sync_plan_json,
            ready_count=_int(
                historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("ready_action_count")
            ),
            blocked_count=_int(
                historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("blocked_action_count")
            ),
            total_count=_int(historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("action_count")),
            next_action=_text(historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("next_action")),
            blockers=(
                "mode:"
                + _text(historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("sync_mode"))
                + ",review:"
                + _text(historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("review_gate_status"))
                + ",first:"
                + _text(historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("first_blocked_field"))
                + ",blocker:"
                + _text(historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("first_blocker"))
                + ",applied:"
                + str(historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("applied_action_count", ""))
            ),
        ),
        _artifact_row(
            "historical_seed_first_clearance_closure_board",
            "Ordered closure board for first historical seed no-leak clearance",
            _text(
                historical_seed_first_clearance_closure_board_summary.get(
                    "first_clearance_closure_board_status"
                )
            ),
            args.historical_seed_first_clearance_closure_board_json,
            ready_count=_int(historical_seed_first_clearance_closure_board_summary.get("ready_stage_count")),
            blocked_count=_int(historical_seed_first_clearance_closure_board_summary.get("blocked_stage_count")),
            total_count=_int(historical_seed_first_clearance_closure_board_summary.get("stage_count")),
            next_action=_text(historical_seed_first_clearance_closure_board_summary.get("next_action")),
            blockers=(
                "first:"
                + _text(historical_seed_first_clearance_closure_board_summary.get("first_blocked_stage_id"))
                + ",status:"
                + _text(historical_seed_first_clearance_closure_board_summary.get("first_blocked_stage_status"))
                + ",blocker:"
                + _text(historical_seed_first_clearance_closure_board_summary.get("first_blocker"))
                + ",kit:"
                + _text(historical_seed_first_clearance_closure_board_summary.get("operator_kit_status"))
                + ",gate:"
                + _text(historical_seed_first_clearance_closure_board_summary.get("no_leak_gate_status"))
            ),
        ),
        _artifact_row(
            "historical_seed_clearance_to_identity_intake_sync",
            "Dry-run bridge from cleared historical seed manifest into competitive identity intake",
            _text(historical_seed_clearance_to_identity_intake_sync_summary.get("seed_to_identity_sync_status")),
            args.historical_seed_clearance_to_identity_intake_sync_json,
            ready_count=_int(historical_seed_clearance_to_identity_intake_sync_summary.get("ready_to_sync_count")),
            blocked_count=(
                _int(historical_seed_clearance_to_identity_intake_sync_summary.get("waiting_intake_count"))
                + _int(historical_seed_clearance_to_identity_intake_sync_summary.get("blocked_count"))
            ),
            total_count=_int(historical_seed_clearance_to_identity_intake_sync_summary.get("intake_row_count")),
            next_action=_text(historical_seed_clearance_to_identity_intake_sync_summary.get("first_next_action")),
            blockers=(
                "cleared_seed_rows:"
                + str(historical_seed_clearance_to_identity_intake_sync_summary.get("seed_manifest_row_count", ""))
                + ",eligible:"
                + str(historical_seed_clearance_to_identity_intake_sync_summary.get("eligible_seed_row_count", ""))
                + ",ready:"
                + str(historical_seed_clearance_to_identity_intake_sync_summary.get("ready_to_sync_count", ""))
                + ",waiting:"
                + str(historical_seed_clearance_to_identity_intake_sync_summary.get("waiting_intake_count", ""))
                + ",applied:"
                + str(historical_seed_clearance_to_identity_intake_sync_summary.get("applied_count", ""))
                + ",mode:"
                + str(historical_seed_clearance_to_identity_intake_sync_summary.get("apply_mode", ""))
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
        "protein_object_library_completion_status": _text(
            protein_object_library_completion_audit_summary.get("completion_audit_status")
        ),
        "protein_object_library_completion_protein_pass_count": _int(
            protein_object_library_completion_audit_summary.get("protein_folder_pass_count")
        ),
        "protein_object_library_completion_protein_blocked_count": _int(
            protein_object_library_completion_audit_summary.get("protein_folder_blocked_count")
        ),
        "protein_object_library_completion_protein_count": _int(
            protein_object_library_completion_audit_summary.get("protein_folder_count")
        ),
        "protein_object_library_completion_object_pass_count": _int(
            protein_object_library_completion_audit_summary.get("object_pass_count")
        ),
        "protein_object_library_completion_object_blocked_count": _int(
            protein_object_library_completion_audit_summary.get("object_blocked_count")
        ),
        "protein_object_library_completion_object_count": _int(
            protein_object_library_completion_audit_summary.get("object_folder_count")
        ),
        "protein_object_library_completion_model_count": _int(
            protein_object_library_completion_audit_summary.get("model_file_present_count")
        ),
        "protein_object_library_completion_projection_count": _int(
            protein_object_library_completion_audit_summary.get("projection_file_present_count")
        ),
        "protein_object_library_completion_viewer_count": _int(
            protein_object_library_completion_audit_summary.get("viewer_file_present_count")
        ),
        "protein_object_library_completion_object_manifest_count": _int(
            protein_object_library_completion_audit_summary.get("object_manifest_present_count")
        ),
        "protein_object_library_completion_protein_manifest_count": _int(
            protein_object_library_completion_audit_summary.get("protein_manifest_present_count")
        ),
        "protein_object_library_navigation_status": _text(
            protein_object_library_navigation_catalog_summary.get("navigation_catalog_status")
        ),
        "protein_object_library_navigation_protein_pass_count": _int(
            protein_object_library_navigation_catalog_summary.get("protein_pass_count")
        ),
        "protein_object_library_navigation_protein_blocked_count": _int(
            protein_object_library_navigation_catalog_summary.get("protein_blocked_count")
        ),
        "protein_object_library_navigation_protein_count": _int(
            protein_object_library_navigation_catalog_summary.get("protein_count")
        ),
        "protein_object_library_navigation_object_pass_count": _int(
            protein_object_library_navigation_catalog_summary.get("object_pass_count")
        ),
        "protein_object_library_navigation_object_blocked_count": _int(
            protein_object_library_navigation_catalog_summary.get("object_blocked_count")
        ),
        "protein_object_library_navigation_object_count": _int(
            protein_object_library_navigation_catalog_summary.get("object_count")
        ),
        "protein_object_library_navigation_readme_link_count": _int(
            protein_object_library_navigation_catalog_summary.get("protein_readme_link_count")
        ),
        "protein_object_library_navigation_manifest_link_count": _int(
            protein_object_library_navigation_catalog_summary.get("protein_manifest_link_count")
        ),
        "protein_object_library_navigation_largest_protein_key": _text(
            protein_object_library_navigation_catalog_summary.get("largest_protein_key")
        ),
        "protein_object_library_navigation_largest_object_count": _int(
            protein_object_library_navigation_catalog_summary.get("largest_object_count")
        ),
        "protein_object_library_navigation_html": _text(
            protein_object_library_navigation_catalog_summary.get("html_catalog_path")
        ),
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
        "win_tier_metric_surface_contract_status": _text(
            win_tier_metric_surface_contract_summary.get("metric_surface_contract_status")
        ),
        "win_tier_metric_surface_contract_required_metric_count": _int(
            win_tier_metric_surface_contract_summary.get("required_metric_count")
        ),
        "win_tier_metric_surface_contract_covered_metric_count": _int(
            win_tier_metric_surface_contract_summary.get("covered_required_metric_count")
        ),
        "win_tier_metric_surface_contract_slot_count": _int(
            win_tier_metric_surface_contract_summary.get("strict_blind_slot_count")
        ),
        "win_tier_metric_surface_contract_ready_slot_count": _int(
            win_tier_metric_surface_contract_summary.get("ready_slot_count")
        ),
        "win_tier_metric_surface_contract_blocked_slot_count": _int(
            win_tier_metric_surface_contract_summary.get("blocked_slot_count")
        ),
        "win_tier_metric_surface_contract_metric_row_count": _int(
            win_tier_metric_surface_contract_summary.get("metric_surface_row_count")
        ),
        "win_tier_metric_surface_contract_ready_metric_row_count": _int(
            win_tier_metric_surface_contract_summary.get("ready_metric_row_count")
        ),
        "win_tier_metric_surface_contract_blocked_metric_row_count": _int(
            win_tier_metric_surface_contract_summary.get("blocked_metric_row_count")
        ),
        "win_tier_metric_surface_contract_ligand_slot_count": _int(
            win_tier_metric_surface_contract_summary.get("organic_ligand_slot_count")
        ),
        "win_tier_metric_surface_contract_official_archive_policy": _text(
            win_tier_metric_surface_contract_summary.get("official_archive_baseline_policy")
        ),
        "win_tier_metric_surface_contract_first_blocked_metric": _text(
            win_tier_metric_surface_contract_summary.get("first_blocked_metric")
        ),
        "win_tier_metric_surface_contract_first_blocked_benchmark": _text(
            win_tier_metric_surface_contract_summary.get("first_blocked_benchmark_id")
        ),
        "win_tier_critical_path_status": _text(
            win_tier_critical_path_board_summary.get("critical_path_status")
        ),
        "win_tier_critical_path_stage_ready_count": _int(
            win_tier_critical_path_board_summary.get("stage_ready_count")
        ),
        "win_tier_critical_path_stage_blocked_count": _int(
            win_tier_critical_path_board_summary.get("stage_blocked_count")
        ),
        "win_tier_critical_path_stage_count": _int(
            win_tier_critical_path_board_summary.get("stage_count")
        ),
        "win_tier_critical_path_3d_ready_count": _int(
            win_tier_critical_path_board_summary.get("three_d_object_ready_count")
        ),
        "win_tier_critical_path_3d_count": _int(
            win_tier_critical_path_board_summary.get("three_d_object_count")
        ),
        "win_tier_critical_path_external_ready_target_count": _int(
            win_tier_critical_path_board_summary.get("external_model_selection_ready_target_count")
        ),
        "win_tier_critical_path_external_target_count": _int(
            win_tier_critical_path_board_summary.get("external_model_selection_target_count")
        ),
        "win_tier_critical_path_external_model1_count": _int(
            win_tier_critical_path_board_summary.get("external_model_selection_model1_count")
        ),
        "win_tier_critical_path_external_top5_count": _int(
            win_tier_critical_path_board_summary.get("external_model_selection_top5_count")
        ),
        "win_tier_critical_path_strict_ready_slot_count": _int(
            win_tier_critical_path_board_summary.get("strict_blind_ready_slot_count")
        ),
        "win_tier_critical_path_strict_slot_count": _int(
            win_tier_critical_path_board_summary.get("strict_blind_slot_count")
        ),
        "win_tier_critical_path_missing_evidence_file_count": _int(
            win_tier_critical_path_board_summary.get("strict_blind_evidence_file_missing_count")
        ),
        "win_tier_critical_path_operator_open_value_count": _int(
            win_tier_critical_path_board_summary.get("strict_blind_operator_open_value_count")
        ),
        "win_tier_critical_path_first_blocked_stage": _text(
            win_tier_critical_path_board_summary.get("first_blocked_stage_id")
        ),
        "win_tier_critical_path_first_blocker": _text(
            win_tier_critical_path_board_summary.get("first_blocker")
        ),
        "organic_ligand_slot_candidate_status": _text(
            organic_ligand_slot_candidate_packet_summary.get("organic_ligand_slot_candidate_status")
        ),
        "organic_ligand_slot_candidate_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("candidate_count")
        ),
        "organic_ligand_slot_candidate_chembl_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("chembl_candidate_count")
        ),
        "organic_ligand_slot_candidate_bindingdb_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("bindingdb_candidate_count")
        ),
        "organic_ligand_slot_candidate_review_ready_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("review_ready_candidate_count")
        ),
        "organic_ligand_slot_candidate_proof_eligible_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("competitive_proof_eligible_count")
        ),
        "organic_ligand_slot_candidate_strict_blocked_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("strict_blind_promotion_blocked_count")
        ),
        "organic_ligand_slot_candidate_reference_present_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("local_reference_present_count")
        ),
        "organic_ligand_slot_candidate_prediction_present_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("prediction_present_count")
        ),
        "organic_ligand_slot_candidate_ligand_mol2_present_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("ligand_mol2_present_count")
        ),
        "organic_ligand_slot_candidate_ligand_template_present_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("ligand_template_present_count")
        ),
        "organic_ligand_slot_candidate_lddt_pli_required_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("lddt_pli_required_count")
        ),
        "organic_ligand_slot_candidate_bisyrmsd_required_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("bisyrmsd_required_count")
        ),
        "organic_ligand_slot_candidate_affinity_label_candidate_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("affinity_label_candidate_count")
        ),
        "organic_ligand_slot_candidate_metric_contract_ligand_slot_gap_count": _int(
            organic_ligand_slot_candidate_packet_summary.get("metric_contract_ligand_slot_gap_count")
        ),
        "organic_ligand_slot_candidate_first_target_id": _text(
            organic_ligand_slot_candidate_packet_summary.get("first_candidate_target_id")
        ),
        "organic_ligand_slot_candidate_first_ligand_id": _text(
            organic_ligand_slot_candidate_packet_summary.get("first_candidate_ligand_id")
        ),
        "organic_ligand_slot_promotion_action_board_status": _text(
            organic_ligand_slot_promotion_action_board_summary.get(
                "organic_ligand_slot_promotion_action_board_status"
            )
        ),
        "organic_ligand_slot_promotion_candidate_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get("candidate_count")
        ),
        "organic_ligand_slot_promotion_action_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get("action_count")
        ),
        "organic_ligand_slot_promotion_open_action_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get("open_action_count")
        ),
        "organic_ligand_slot_promotion_reference_preflight_pass_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get(
                "reference_file_preflight_pass_count"
            )
        ),
        "organic_ligand_slot_promotion_operator_evidence_required_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get(
                "operator_evidence_required_count"
            )
        ),
        "organic_ligand_slot_promotion_numeric_value_required_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get(
                "numeric_value_required_count"
            )
        ),
        "organic_ligand_slot_promotion_affinity_source_required_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get(
                "affinity_source_required_count"
            )
        ),
        "organic_ligand_slot_promotion_metric_input_required_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get("metric_input_required_count")
        ),
        "organic_ligand_slot_promotion_slot_mapping_required_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get("slot_mapping_required_count")
        ),
        "organic_ligand_slot_promotion_proof_ready_candidate_count": _int(
            organic_ligand_slot_promotion_action_board_summary.get("proof_ready_candidate_count")
        ),
        "organic_ligand_slot_promotion_first_open_action_id": _text(
            organic_ligand_slot_promotion_action_board_summary.get("first_open_action_id")
        ),
        "organic_ligand_slot_promotion_first_open_target_id": _text(
            organic_ligand_slot_promotion_action_board_summary.get("first_open_target_id")
        ),
        "organic_ligand_slot_promotion_first_open_action_type": _text(
            organic_ligand_slot_promotion_action_board_summary.get("first_open_action_type")
        ),
        "active_scope_decision_status": _text(active_scope_decision_summary.get("scope_decision_status")),
        "active_competition_scope": _text(active_scope_decision_summary.get("active_competition_scope")),
        "active_scope_casp17_continuation_status": _text(
            active_scope_decision_summary.get("casp17_continuation_status")
        ),
        "active_scope_casp17_priority_status": _text(active_scope_decision_summary.get("casp17_priority_status")),
        "active_scope_capri_round65_participation_status": _text(
            active_scope_decision_summary.get("capri_round65_participation_status")
        ),
        "active_scope_capri_round65_hold_reason": _text(
            active_scope_decision_summary.get("capri_round65_hold_reason")
        ),
        "active_scope_capri_round65_artifact_policy": _text(
            active_scope_decision_summary.get("capri_round65_artifact_policy")
        ),
        "active_scope_next_action": _text(active_scope_decision_summary.get("first_next_action")),
        "active_scope_active_lane_count": _int(active_scope_decision_summary.get("active_lane_count")),
        "active_scope_deferred_lane_count": _int(active_scope_decision_summary.get("deferred_lane_count")),
        "active_scope_row_count": _int(active_scope_decision_summary.get("row_count")),
        "organizer_notice_status": _text(organizer_notice_summary.get("organizer_notice_status")),
        "organizer_notice_source_ref": _text(organizer_notice_summary.get("source_notice_ref")),
        "organizer_notice_r2345_first_request_status": _text(
            organizer_notice_summary.get("r2345_first_request_status")
        ),
        "organizer_notice_r2345_replacement_request_status": _text(
            organizer_notice_summary.get("r2345_replacement_request_status")
        ),
        "organizer_notice_r2345_sequence_validation_gate": _text(
            organizer_notice_summary.get("r2345_sequence_validation_gate")
        ),
        "organizer_notice_massivefold_generation_scope": _text(
            organizer_notice_summary.get("massivefold_generation_scope")
        ),
        "organizer_notice_massivefold_first_rna_hybrid_set_target_id": _text(
            organizer_notice_summary.get("massivefold_first_rna_hybrid_set_target_id")
        ),
        "organizer_notice_massivefold_link_count": _int(organizer_notice_summary.get("massivefold_link_count")),
        "organizer_notice_massivefold_rna_hybrid_link_count": _int(
            organizer_notice_summary.get("massivefold_rna_hybrid_link_count")
        ),
        "organizer_notice_massivefold_protein_complex_link_count": _int(
            organizer_notice_summary.get("massivefold_protein_complex_link_count")
        ),
        "organizer_notice_massivefold_r2341_link_present": _text(
            organizer_notice_summary.get("massivefold_r2341_link_present")
        ),
        "organizer_notice_massivefold_r2345_link_present": _text(
            organizer_notice_summary.get("massivefold_r2345_link_present")
        ),
        "organizer_notice_massivefold_model_pool_policy": _text(
            organizer_notice_summary.get("massivefold_model_pool_policy")
        ),
        "organizer_notice_massivefold_internal_prediction_policy": _text(
            organizer_notice_summary.get("massivefold_internal_prediction_policy")
        ),
        "organizer_notice_large_download_policy": _text(
            organizer_notice_summary.get("large_download_policy")
        ),
        "organizer_notice_next_action": _text(organizer_notice_summary.get("next_action")),
        "massivefold_external_pool_intake_status": _text(
            massivefold_external_pool_intake_summary.get("massivefold_external_pool_intake_status")
        ),
        "massivefold_external_pool_count": _int(
            massivefold_external_pool_intake_summary.get("massivefold_pool_count")
        ),
        "massivefold_external_pool_ready_count": _int(
            massivefold_external_pool_intake_summary.get("ready_pool_count")
        ),
        "massivefold_external_pool_blocked_count": _int(
            massivefold_external_pool_intake_summary.get("blocked_pool_count")
        ),
        "massivefold_external_pool_rna_hybrid_count": _int(
            massivefold_external_pool_intake_summary.get("rna_hybrid_pool_count")
        ),
        "massivefold_external_pool_protein_complex_count": _int(
            massivefold_external_pool_intake_summary.get("protein_complex_pool_count")
        ),
        "massivefold_external_pool_proof_eligible_count": _int(
            massivefold_external_pool_intake_summary.get("competitive_proof_eligible_count")
        ),
        "massivefold_external_pool_internal_blocked_count": _int(
            massivefold_external_pool_intake_summary.get("internal_prediction_blocked_count")
        ),
        "massivefold_external_pool_total_size_bytes": _int(
            massivefold_external_pool_intake_summary.get("total_declared_size_bytes")
        ),
        "massivefold_external_pool_largest_model_set_id": _text(
            massivefold_external_pool_intake_summary.get("largest_model_set_id")
        ),
        "massivefold_external_pool_r2341_present": _text(
            massivefold_external_pool_intake_summary.get("r2341_pool_present")
        ),
        "massivefold_external_pool_r2345_present": _text(
            massivefold_external_pool_intake_summary.get("r2345_pool_present")
        ),
        "massivefold_external_pool_download_policy": _text(
            massivefold_external_pool_intake_summary.get("download_policy")
        ),
        "rna_hybrid_massivefold_priority_queue_status": _text(
            rna_hybrid_massivefold_priority_queue_summary.get(
                "rna_hybrid_massivefold_priority_queue_status"
            )
        ),
        "rna_hybrid_massivefold_priority_queue_count": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("queue_row_count")
        ),
        "rna_hybrid_massivefold_priority_queue_ready_count": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("ready_queue_row_count")
        ),
        "rna_hybrid_massivefold_priority_queue_blocked_count": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("blocked_queue_row_count")
        ),
        "rna_hybrid_massivefold_priority_queue_first_target_id": _text(
            rna_hybrid_massivefold_priority_queue_summary.get("first_priority_target_id")
        ),
        "rna_hybrid_massivefold_priority_queue_first_reason": _text(
            rna_hybrid_massivefold_priority_queue_summary.get("first_priority_reason")
        ),
        "rna_hybrid_massivefold_priority_queue_r2341_rank": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("r2341_queue_rank")
        ),
        "rna_hybrid_massivefold_priority_queue_r2345_rank": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("r2345_queue_rank")
        ),
        "rna_hybrid_massivefold_priority_queue_r2345_invalid_status": _text(
            rna_hybrid_massivefold_priority_queue_summary.get("r2345_invalid_request_status")
        ),
        "rna_hybrid_massivefold_priority_queue_r2345_active_status": _text(
            rna_hybrid_massivefold_priority_queue_summary.get("r2345_active_request_status")
        ),
        "rna_hybrid_massivefold_priority_queue_r2345_sequence_guard": _text(
            rna_hybrid_massivefold_priority_queue_summary.get("r2345_sequence_guard")
        ),
        "rna_hybrid_massivefold_priority_queue_proof_eligible_count": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("competitive_proof_eligible_count")
        ),
        "rna_hybrid_massivefold_priority_queue_internal_blocked_count": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("internal_prediction_blocked_count")
        ),
        "rna_hybrid_massivefold_priority_queue_total_size_bytes": _int(
            rna_hybrid_massivefold_priority_queue_summary.get("total_declared_size_bytes")
        ),
        "rna_hybrid_massivefold_priority_queue_download_policy": _text(
            rna_hybrid_massivefold_priority_queue_summary.get("download_policy")
        ),
        "protein_complex_massivefold_priority_queue_status": _text(
            protein_complex_massivefold_priority_queue_summary.get(
                "protein_complex_massivefold_priority_queue_status"
            )
        ),
        "protein_complex_massivefold_priority_queue_count": _int(
            protein_complex_massivefold_priority_queue_summary.get("queue_row_count")
        ),
        "protein_complex_massivefold_priority_queue_ready_count": _int(
            protein_complex_massivefold_priority_queue_summary.get("ready_queue_row_count")
        ),
        "protein_complex_massivefold_priority_queue_blocked_count": _int(
            protein_complex_massivefold_priority_queue_summary.get("blocked_queue_row_count")
        ),
        "protein_complex_massivefold_priority_queue_first_target_id": _text(
            protein_complex_massivefold_priority_queue_summary.get("first_priority_target_id")
        ),
        "protein_complex_massivefold_priority_queue_first_model_set_id": _text(
            protein_complex_massivefold_priority_queue_summary.get("first_priority_model_set_id")
        ),
        "protein_complex_massivefold_priority_queue_first_reason": _text(
            protein_complex_massivefold_priority_queue_summary.get("first_priority_reason")
        ),
        "protein_complex_massivefold_priority_queue_largest_model_set_id": _text(
            protein_complex_massivefold_priority_queue_summary.get("largest_model_set_id")
        ),
        "protein_complex_massivefold_priority_queue_largest_size_bytes": _int(
            protein_complex_massivefold_priority_queue_summary.get("largest_pool_size_bytes")
        ),
        "protein_complex_massivefold_priority_queue_total_size_bytes": _int(
            protein_complex_massivefold_priority_queue_summary.get("total_declared_size_bytes")
        ),
        "protein_complex_massivefold_priority_queue_proof_eligible_count": _int(
            protein_complex_massivefold_priority_queue_summary.get("competitive_proof_eligible_count")
        ),
        "protein_complex_massivefold_priority_queue_internal_blocked_count": _int(
            protein_complex_massivefold_priority_queue_summary.get("internal_prediction_blocked_count")
        ),
        "protein_complex_massivefold_priority_queue_download_policy": _text(
            protein_complex_massivefold_priority_queue_summary.get("download_policy")
        ),
        "massivefold_acquisition_verification_status": _text(
            massivefold_acquisition_verification_board_summary.get(
                "massivefold_acquisition_verification_status"
            )
        ),
        "massivefold_acquisition_verification_pool_count": _int(
            massivefold_acquisition_verification_board_summary.get("acquisition_pool_count")
        ),
        "massivefold_acquisition_verification_verified_count": _int(
            massivefold_acquisition_verification_board_summary.get("verified_pool_count")
        ),
        "massivefold_acquisition_verification_open_count": _int(
            massivefold_acquisition_verification_board_summary.get("open_acquisition_action_count")
        ),
        "massivefold_acquisition_verification_tarball_present_count": _int(
            massivefold_acquisition_verification_board_summary.get("tarball_present_count")
        ),
        "massivefold_acquisition_verification_sha256_record_count": _int(
            massivefold_acquisition_verification_board_summary.get("sha256_record_present_count")
        ),
        "massivefold_acquisition_verification_sha256_verified_count": _int(
            massivefold_acquisition_verification_board_summary.get("sha256_verified_count")
        ),
        "massivefold_acquisition_verification_listing_present_count": _int(
            massivefold_acquisition_verification_board_summary.get("listing_present_count")
        ),
        "massivefold_acquisition_verification_listing_entry_count": _int(
            massivefold_acquisition_verification_board_summary.get("listing_entry_count")
        ),
        "massivefold_acquisition_verification_first_priority_target_id": _text(
            massivefold_acquisition_verification_board_summary.get("first_priority_target_id")
        ),
        "massivefold_acquisition_verification_first_open_target_id": _text(
            massivefold_acquisition_verification_board_summary.get("first_open_target_id")
        ),
        "massivefold_acquisition_verification_first_open_status": _text(
            massivefold_acquisition_verification_board_summary.get("first_open_status")
        ),
        "massivefold_acquisition_verification_r2341_status": _text(
            massivefold_acquisition_verification_board_summary.get("r2341_verification_status")
        ),
        "massivefold_acquisition_verification_r2345_status": _text(
            massivefold_acquisition_verification_board_summary.get("r2345_verification_status")
        ),
        "massivefold_acquisition_verification_download_policy": _text(
            massivefold_acquisition_verification_board_summary.get("download_policy")
        ),
        "protein_complex_massivefold_acquisition_verification_status": _text(
            protein_complex_massivefold_acquisition_verification_board_summary.get(
                "massivefold_acquisition_verification_status"
            )
        ),
        "protein_complex_massivefold_acquisition_verification_pool_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get("acquisition_pool_count")
        ),
        "protein_complex_massivefold_acquisition_verification_verified_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get("verified_pool_count")
        ),
        "protein_complex_massivefold_acquisition_verification_open_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get(
                "open_acquisition_action_count"
            )
        ),
        "protein_complex_massivefold_acquisition_verification_tarball_present_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get("tarball_present_count")
        ),
        "protein_complex_massivefold_acquisition_verification_sha256_record_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get(
                "sha256_record_present_count"
            )
        ),
        "protein_complex_massivefold_acquisition_verification_sha256_verified_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get("sha256_verified_count")
        ),
        "protein_complex_massivefold_acquisition_verification_listing_present_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get("listing_present_count")
        ),
        "protein_complex_massivefold_acquisition_verification_listing_entry_count": _int(
            protein_complex_massivefold_acquisition_verification_board_summary.get("listing_entry_count")
        ),
        "protein_complex_massivefold_acquisition_verification_first_priority_target_id": _text(
            protein_complex_massivefold_acquisition_verification_board_summary.get(
                "first_priority_target_id"
            )
        ),
        "protein_complex_massivefold_acquisition_verification_first_open_target_id": _text(
            protein_complex_massivefold_acquisition_verification_board_summary.get("first_open_target_id")
        ),
        "protein_complex_massivefold_acquisition_verification_first_open_status": _text(
            protein_complex_massivefold_acquisition_verification_board_summary.get("first_open_status")
        ),
        "protein_complex_massivefold_acquisition_verification_download_policy": _text(
            protein_complex_massivefold_acquisition_verification_board_summary.get("download_policy")
        ),
        "massivefold_model_pool_index_status": _text(
            massivefold_model_pool_index_summary.get("massivefold_model_pool_index_status")
        ),
        "massivefold_model_pool_index_target_id": _text(
            massivefold_model_pool_index_summary.get("target_id")
        ),
        "massivefold_model_pool_index_model_count": _int(
            massivefold_model_pool_index_summary.get("model_count")
        ),
        "massivefold_model_pool_index_protocol_count": _int(
            massivefold_model_pool_index_summary.get("protocol_bucket_count")
        ),
        "massivefold_model_pool_index_selected_count": _int(
            massivefold_model_pool_index_summary.get("selected_extract_count")
        ),
        "massivefold_model_pool_index_extracted_count": _int(
            massivefold_model_pool_index_summary.get("selected_extracted_count")
        ),
        "massivefold_model_pool_index_pending_count": _int(
            massivefold_model_pool_index_summary.get("selected_extract_pending_count")
        ),
        "massivefold_model_pool_index_basic_count": _int(
            massivefold_model_pool_index_summary.get("basic_count")
        ),
        "massivefold_model_pool_index_wo_templates_count": _int(
            massivefold_model_pool_index_summary.get("wo_templates_count")
        ),
        "massivefold_model_pool_index_wo_unpaired_count": _int(
            massivefold_model_pool_index_summary.get("wo_unpaired_count")
        ),
        "massivefold_model_pool_index_wo_paired_count": _int(
            massivefold_model_pool_index_summary.get("wo_paired_count")
        ),
        "massivefold_model_pool_index_first_selected_model": _text(
            massivefold_model_pool_index_summary.get("first_selected_model")
        ),
        "massivefold_model_pool_index_first_selected_protocol": _text(
            massivefold_model_pool_index_summary.get("first_selected_protocol")
        ),
        "massivefold_model_pool_index_extraction_manifest": _text(
            massivefold_model_pool_index_summary.get("extraction_manifest")
        ),
        "massivefold_representative_viewer_status": _text(
            massivefold_representative_viewer_packet_summary.get("massivefold_representative_viewer_status")
        ),
        "massivefold_representative_viewer_target_id": _text(
            massivefold_representative_viewer_packet_summary.get("target_id")
        ),
        "massivefold_representative_viewer_selected_count": _int(
            massivefold_representative_viewer_packet_summary.get("selected_model_count")
        ),
        "massivefold_representative_viewer_ready_count": _int(
            massivefold_representative_viewer_packet_summary.get("viewer_ready_count")
        ),
        "massivefold_representative_viewer_blocked_count": _int(
            massivefold_representative_viewer_packet_summary.get("viewer_blocked_count")
        ),
        "massivefold_representative_viewer_coordinate_count": _int(
            massivefold_representative_viewer_packet_summary.get("coordinate_valid_count")
        ),
        "massivefold_representative_viewer_model_cif_count": _int(
            massivefold_representative_viewer_packet_summary.get("model_cif_present_count")
        ),
        "massivefold_representative_viewer_projection_count": _int(
            massivefold_representative_viewer_packet_summary.get("projection_ready_count")
        ),
        "massivefold_representative_viewer_atom_count": _int(
            massivefold_representative_viewer_packet_summary.get("atom_count_total")
        ),
        "massivefold_representative_viewer_display_atom_count": _int(
            massivefold_representative_viewer_packet_summary.get("display_atom_count_total")
        ),
        "massivefold_representative_viewer_residue_count": _int(
            massivefold_representative_viewer_packet_summary.get("residue_count_total")
        ),
        "massivefold_representative_viewer_protocol_count": _int(
            massivefold_representative_viewer_packet_summary.get("protocol_bucket_count")
        ),
        "massivefold_representative_viewer_first_html": _text(
            massivefold_representative_viewer_packet_summary.get("first_viewer_html")
        ),
        "massivefold_representative_viewer_gallery_html": _text(
            massivefold_representative_viewer_packet_summary.get("gallery_html_path")
        ),
        "massivefold_representative_rerank_status": _text(
            massivefold_representative_rerank_packet_summary.get("massivefold_representative_rerank_status")
        ),
        "massivefold_representative_rerank_target_id": _text(
            massivefold_representative_rerank_packet_summary.get("target_id")
        ),
        "massivefold_representative_rerank_candidate_count": _int(
            massivefold_representative_rerank_packet_summary.get("candidate_count")
        ),
        "massivefold_representative_rerank_model1_count": _int(
            massivefold_representative_rerank_packet_summary.get("model1_candidate_count")
        ),
        "massivefold_representative_rerank_top5_count": _int(
            massivefold_representative_rerank_packet_summary.get("top5_candidate_count")
        ),
        "massivefold_representative_rerank_top5_protocol_count": _int(
            massivefold_representative_rerank_packet_summary.get("top5_protocol_count")
        ),
        "massivefold_representative_rerank_review_candidate_count": _int(
            massivefold_representative_rerank_packet_summary.get("review_candidate_count")
        ),
        "massivefold_representative_rerank_proof_eligible_count": _int(
            massivefold_representative_rerank_packet_summary.get("competitive_proof_eligible_count")
        ),
        "massivefold_representative_rerank_confidence_min": _text(
            massivefold_representative_rerank_packet_summary.get("confidence_score_min")
        ),
        "massivefold_representative_rerank_confidence_max": _text(
            massivefold_representative_rerank_packet_summary.get("confidence_score_max")
        ),
        "massivefold_representative_rerank_model1_file": _text(
            massivefold_representative_rerank_packet_summary.get("model1_filename")
        ),
        "massivefold_representative_rerank_model1_protocol": _text(
            massivefold_representative_rerank_packet_summary.get("model1_protocol")
        ),
        "massivefold_representative_rerank_model1_score": _text(
            massivefold_representative_rerank_packet_summary.get("model1_confidence_score")
        ),
        "massivefold_representative_rerank_model1_viewer": _text(
            massivefold_representative_rerank_packet_summary.get("model1_viewer_html")
        ),
        "massivefold_representative_rerank_top5_manifest": _text(
            massivefold_representative_rerank_packet_summary.get("top5_manifest_csv")
        ),
        "massivefold_rna_model_selection_coverage_status": _text(
            massivefold_rna_model_selection_coverage_summary.get(
                "massivefold_rna_model_selection_coverage_status"
            )
        ),
        "massivefold_rna_model_selection_coverage_target_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("target_count")
        ),
        "massivefold_rna_model_selection_coverage_ready_target_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("ready_target_count")
        ),
        "massivefold_rna_model_selection_coverage_partial_target_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("partial_target_count")
        ),
        "massivefold_rna_model_selection_coverage_verified_acquisition_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("verified_acquisition_count")
        ),
        "massivefold_rna_model_selection_coverage_representative_extracted_target_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("representative_extracted_target_count")
        ),
        "massivefold_rna_model_selection_coverage_viewer_ready_target_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("viewer_ready_target_count")
        ),
        "massivefold_rna_model_selection_coverage_rerank_ready_target_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("rerank_ready_target_count")
        ),
        "massivefold_rna_model_selection_coverage_selected_model_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("selected_model_count")
        ),
        "massivefold_rna_model_selection_coverage_extracted_model_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("extracted_model_count")
        ),
        "massivefold_rna_model_selection_coverage_viewer_ready_model_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("viewer_ready_model_count")
        ),
        "massivefold_rna_model_selection_coverage_top5_candidate_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("top5_candidate_count")
        ),
        "massivefold_rna_model_selection_coverage_model1_candidate_count": _int(
            massivefold_rna_model_selection_coverage_summary.get("model1_candidate_count")
        ),
        "massivefold_rna_model_selection_coverage_first_partial_target_id": _text(
            massivefold_rna_model_selection_coverage_summary.get("first_partial_target_id")
        ),
        "protein_complex_massivefold_model_selection_coverage_status": _text(
            protein_complex_massivefold_model_selection_coverage_summary.get(
                "protein_complex_massivefold_model_selection_coverage_status"
            )
        ),
        "protein_complex_massivefold_model_selection_coverage_target_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("target_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_ready_target_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("ready_target_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_partial_target_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("partial_target_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_verified_acquisition_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("verified_acquisition_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_representative_extracted_target_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get(
                "representative_extracted_target_count"
            )
        ),
        "protein_complex_massivefold_model_selection_coverage_viewer_ready_target_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("viewer_ready_target_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_rerank_ready_target_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("rerank_ready_target_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_selected_model_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("selected_model_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_extracted_model_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("extracted_model_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_viewer_ready_model_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("viewer_ready_model_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_top5_candidate_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("top5_candidate_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_model1_candidate_count": _int(
            protein_complex_massivefold_model_selection_coverage_summary.get("model1_candidate_count")
        ),
        "protein_complex_massivefold_model_selection_coverage_first_partial_target_id": _text(
            protein_complex_massivefold_model_selection_coverage_summary.get("first_partial_target_id")
        ),
        "capri_round65_readiness_status": _text(
            capri_round65_readiness_summary.get("capri_readiness_status")
        ),
        "capri_round65_round_status": _text(capri_round65_readiness_summary.get("round_status")),
        "capri_round65_registration_end": _text(capri_round65_readiness_summary.get("registration_end")),
        "capri_round65_registration_days_remaining": _int(
            capri_round65_readiness_summary.get("registration_days_remaining")
        ),
        "capri_round65_registration_gate_status": _text(
            capri_round65_readiness_summary.get("registration_gate_status")
        ),
        "capri_round65_registration_ready_field_count": _int(
            capri_round65_readiness_summary.get("registration_ready_field_count")
        ),
        "capri_round65_registration_required_field_count": _int(
            capri_round65_readiness_summary.get("registration_required_field_count")
        ),
        "capri_round65_role_selection_status": _text(
            capri_round65_readiness_summary.get("role_selection_status")
        ),
        "capri_round65_target_count": _int(capri_round65_readiness_summary.get("target_count")),
        "capri_round65_active_target_count": _int(capri_round65_readiness_summary.get("active_target_count")),
        "capri_round65_closed_target_count": _int(capri_round65_readiness_summary.get("closed_target_count")),
        "capri_round65_scorer_priority_target_count": _int(
            capri_round65_readiness_summary.get("scorer_priority_target_count")
        ),
        "capri_round65_predictor_priority_target_count": _int(
            capri_round65_readiness_summary.get("predictor_priority_target_count")
        ),
        "capri_round65_blocked_target_count": _int(capri_round65_readiness_summary.get("blocked_target_count")),
        "capri_round65_readiness_format_preflight_target_count": _int(
            capri_round65_readiness_summary.get("format_preflight_target_count")
        ),
        "capri_round65_target_folder_count": _int(capri_round65_readiness_summary.get("target_folder_count")),
        "capri_round65_first_open_target_id": _text(capri_round65_readiness_summary.get("first_open_target_id")),
        "capri_round65_first_next_action": _text(capri_round65_readiness_summary.get("first_next_action")),
        "capri_round65_format_preflight_status": _text(
            capri_round65_format_preflight_summary.get("format_preflight_status")
        ),
        "capri_round65_format_preflight_target_count": _int(
            capri_round65_format_preflight_summary.get("target_count")
        ),
        "capri_round65_format_preflight_active_target_count": _int(
            capri_round65_format_preflight_summary.get("active_target_count")
        ),
        "capri_round65_format_preflight_closed_target_count": _int(
            capri_round65_format_preflight_summary.get("closed_target_count")
        ),
        "capri_round65_format_preflight_local_pass_count": _int(
            capri_round65_format_preflight_summary.get("local_pass_count")
        ),
        "capri_round65_format_preflight_blocked_count": _int(
            capri_round65_format_preflight_summary.get("blocked_target_count")
        ),
        "capri_round65_format_preflight_checked_count": _int(
            capri_round65_format_preflight_summary.get("checked_submission_count")
        ),
        "capri_round65_format_preflight_template_missing_count": _int(
            capri_round65_format_preflight_summary.get("target_template_missing_count")
        ),
        "capri_round65_format_preflight_candidate_missing_count": _int(
            capri_round65_format_preflight_summary.get("candidate_submission_missing_count")
        ),
        "capri_round65_format_preflight_error_count": _int(
            capri_round65_format_preflight_summary.get("format_error_count")
        ),
        "capri_round65_format_preflight_first_blocked_target_id": _text(
            capri_round65_format_preflight_summary.get("first_blocked_target_id")
        ),
        "capri_round65_format_preflight_first_next_action": _text(
            capri_round65_format_preflight_summary.get("first_next_action")
        ),
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
        "historical_identity_seed_clearance_field_board_status": _text(
            historical_identity_seed_clearance_field_board_summary.get("field_board_status")
        ),
        "historical_identity_seed_clearance_field_board_seed_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("seed_row_count")
        ),
        "historical_identity_seed_clearance_field_board_core_pass_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("core_file_pass_count")
        ),
        "historical_identity_seed_clearance_field_board_blocked_core_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("blocked_core_file_count")
        ),
        "historical_identity_seed_clearance_field_board_operator_fill_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("operator_field_fill_required_count")
        ),
        "historical_identity_seed_clearance_field_board_ready_count": _int(
            historical_identity_seed_clearance_field_board_summary.get(
                "ready_for_cleared_seed_manifest_count"
            )
        ),
        "historical_identity_seed_clearance_field_board_no_leak_open_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("no_leak_open_field_count")
        ),
        "historical_identity_seed_clearance_field_board_calibration_open_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("calibration_open_field_count")
        ),
        "historical_identity_seed_clearance_field_board_ablation_open_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("ablation_open_field_count")
        ),
        "historical_identity_seed_clearance_field_board_total_open_count": _int(
            historical_identity_seed_clearance_field_board_summary.get("total_open_field_count")
        ),
        "historical_identity_seed_clearance_field_board_first_target_id": _text(
            historical_identity_seed_clearance_field_board_summary.get("first_open_target_id")
        ),
        "historical_identity_seed_clearance_field_board_first_field": _text(
            historical_identity_seed_clearance_field_board_summary.get("first_open_field")
        ),
        "historical_identity_seed_clearance_field_board_first_next_action": _text(
            historical_identity_seed_clearance_field_board_summary.get("first_next_action")
        ),
        "historical_seed_no_leak_provenance_dossiers_status": _text(
            historical_seed_no_leak_provenance_dossiers_summary.get("no_leak_dossier_status")
        ),
        "historical_seed_no_leak_provenance_dossiers_seed_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("seed_row_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_dossier_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("dossier_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_core_pass_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("core_input_pass_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_current_false_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("current_target_prefilled_false_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_operator_review_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("operator_review_required_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_ready_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("ready_for_no_leak_clearance_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_open_field_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("operator_required_open_field_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_chronology_gap_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("chronology_evidence_gap_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_negative_control_gap_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("negative_leakage_control_gap_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_mtime_risk_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("mtime_order_risk_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_core_blocked_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("blocked_core_provenance_input_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_current_risk_count": _int(
            historical_seed_no_leak_provenance_dossiers_summary.get("blocked_current_target_risk_count")
        ),
        "historical_seed_no_leak_provenance_dossiers_first_target_id": _text(
            historical_seed_no_leak_provenance_dossiers_summary.get("first_open_target_id")
        ),
        "historical_seed_no_leak_provenance_dossiers_first_next_action": _text(
            historical_seed_no_leak_provenance_dossiers_summary.get("first_next_action")
        ),
        "historical_seed_no_leak_gap_repair_plan_status": _text(
            historical_seed_no_leak_gap_repair_plan_summary.get("no_leak_gap_repair_status")
        ),
        "historical_seed_no_leak_gap_repair_plan_seed_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("seed_row_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_repair_csv_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("repair_csv_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_field_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("field_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_operator_required_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("operator_required_field_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_weak_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("weak_local_candidate_field_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_authoritative_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("authoritative_candidate_field_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_chronology_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("chronology_field_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_negative_control_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("negative_control_field_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_clearance_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("clearance_field_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_mtime_risk_count": _int(
            historical_seed_no_leak_gap_repair_plan_summary.get("mtime_risk_row_count")
        ),
        "historical_seed_no_leak_gap_repair_plan_first_target_id": _text(
            historical_seed_no_leak_gap_repair_plan_summary.get("first_open_target_id")
        ),
        "historical_seed_no_leak_gap_repair_plan_first_next_action": _text(
            historical_seed_no_leak_gap_repair_plan_summary.get("first_next_action")
        ),
        "historical_seed_current_target_prefill_status": _text(
            historical_seed_current_target_prefill_summary.get("prefill_status")
        ),
        "historical_seed_current_target_prefill_apply_mode": _text(
            historical_seed_current_target_prefill_summary.get("apply_mode")
        ),
        "historical_seed_current_target_prefill_row_count": _int(
            historical_seed_current_target_prefill_summary.get("row_count")
        ),
        "historical_seed_current_target_prefill_ready_to_apply_count": _int(
            historical_seed_current_target_prefill_summary.get("ready_to_apply_count")
        ),
        "historical_seed_current_target_prefill_applied_count": _int(
            historical_seed_current_target_prefill_summary.get("applied_count")
        ),
        "historical_seed_current_target_prefill_already_count": _int(
            historical_seed_current_target_prefill_summary.get("already_safe_false_count")
        ),
        "historical_seed_current_target_prefill_blocked_count": _int(
            historical_seed_current_target_prefill_summary.get("blocked_count")
        ),
        "historical_seed_current_target_prefill_collision_count": _int(
            historical_seed_current_target_prefill_summary.get("current_target_collision_count")
        ),
        "historical_seed_current_target_prefill_remaining_open_count": _int(
            historical_seed_current_target_prefill_summary.get("remaining_open_current_target_count")
        ),
        "historical_seed_current_target_prefill_hist_prefix_count": _int(
            historical_seed_current_target_prefill_summary.get("hist_prefix_pass_count")
        ),
        "historical_seed_current_target_prefill_first_next_action": _text(
            historical_seed_current_target_prefill_summary.get("first_next_action")
        ),
        "historical_seed_native_authority_audit_status": _text(
            historical_seed_native_authority_audit_summary.get("native_authority_audit_status")
        ),
        "historical_seed_native_authority_audit_seed_count": _int(
            historical_seed_native_authority_audit_summary.get("seed_row_count")
        ),
        "historical_seed_native_authority_audit_pass_count": _int(
            historical_seed_native_authority_audit_summary.get("native_authority_pass_count")
        ),
        "historical_seed_native_authority_audit_blocked_count": _int(
            historical_seed_native_authority_audit_summary.get("native_authority_blocked_count")
        ),
        "historical_seed_native_authority_audit_placeholder_count": _int(
            historical_seed_native_authority_audit_summary.get("placeholder_native_count")
        ),
        "historical_seed_native_authority_audit_ca_only_count": _int(
            historical_seed_native_authority_audit_summary.get("ca_only_native_count")
        ),
        "historical_seed_native_authority_audit_local_generated_no_authority_count": _int(
            historical_seed_native_authority_audit_summary.get(
                "local_generated_native_without_authority_count"
            )
        ),
        "historical_seed_native_authority_audit_ref_missing_count": _int(
            historical_seed_native_authority_audit_summary.get("authority_ref_missing_count")
        ),
        "historical_seed_native_authority_audit_first_target_id": _text(
            historical_seed_native_authority_audit_summary.get("first_blocked_target_id")
        ),
        "historical_seed_native_authority_audit_first_next_action": _text(
            historical_seed_native_authority_audit_summary.get("first_blocked_next_action")
        ),
        "historical_seed_native_replacement_candidates_status": _text(
            historical_seed_native_replacement_candidates_summary.get("native_replacement_candidate_status")
        ),
        "historical_seed_native_replacement_candidates_candidate_count": _int(
            historical_seed_native_replacement_candidates_summary.get("candidate_row_count")
        ),
        "historical_seed_native_replacement_candidates_ready_count": _int(
            historical_seed_native_replacement_candidates_summary.get("operator_review_ready_count")
        ),
        "historical_seed_native_replacement_candidates_download_required_count": _int(
            historical_seed_native_replacement_candidates_summary.get("source_download_required_count")
        ),
        "historical_seed_native_replacement_candidates_file_blocked_count": _int(
            historical_seed_native_replacement_candidates_summary.get("candidate_file_blocked_count")
        ),
        "historical_seed_native_replacement_candidates_complex_authority_count": _int(
            historical_seed_native_replacement_candidates_summary.get("complex_authority_required_count")
        ),
        "historical_seed_native_replacement_candidates_monomer_count": _int(
            historical_seed_native_replacement_candidates_summary.get("monomer_candidate_count")
        ),
        "historical_seed_native_replacement_candidates_candidate_dir": _text(
            historical_seed_native_replacement_candidates_summary.get("candidate_dir")
        ),
        "historical_seed_native_replacement_candidates_first_target_id": _text(
            historical_seed_native_replacement_candidates_summary.get("first_blocked_target_id")
        ),
        "historical_seed_native_replacement_candidates_first_next_action": _text(
            historical_seed_native_replacement_candidates_summary.get("first_blocked_next_action")
        ),
        "historical_seed_complex_source_authority_candidates_status": _text(
            historical_seed_complex_source_authority_candidates_summary.get(
                "complex_source_authority_candidate_status"
            )
        ),
        "historical_seed_complex_source_authority_candidates_candidate_count": _int(
            historical_seed_complex_source_authority_candidates_summary.get("candidate_row_count")
        ),
        "historical_seed_complex_source_authority_candidates_review_ready_count": _int(
            historical_seed_complex_source_authority_candidates_summary.get("operator_review_ready_count")
        ),
        "historical_seed_complex_source_authority_candidates_direct_count": _int(
            historical_seed_complex_source_authority_candidates_summary.get(
                "direct_source_authority_ready_count"
            )
        ),
        "historical_seed_complex_source_authority_candidates_homolog_count": _int(
            historical_seed_complex_source_authority_candidates_summary.get(
                "homolog_source_authority_ready_count"
            )
        ),
        "historical_seed_complex_source_authority_candidates_blocked_count": _int(
            historical_seed_complex_source_authority_candidates_summary.get("source_authority_blocked_count")
        ),
        "historical_seed_complex_source_authority_candidates_operator_apply_count": _int(
            historical_seed_complex_source_authority_candidates_summary.get("operator_apply_allowed_count")
        ),
        "historical_seed_complex_source_authority_candidates_claim_promotion_count": _int(
            historical_seed_complex_source_authority_candidates_summary.get("claim_promotion_allowed_count")
        ),
        "historical_seed_complex_source_authority_candidates_protein_ref": _text(
            historical_seed_complex_source_authority_candidates_summary.get("protein_authority_ref")
        ),
        "historical_seed_complex_source_authority_candidates_first_target_id": _text(
            historical_seed_complex_source_authority_candidates_summary.get("first_blocked_target_id")
        ),
        "historical_seed_complex_source_authority_candidates_first_next_action": _text(
            historical_seed_complex_source_authority_candidates_summary.get("first_next_action")
        ),
        "historical_seed_chronology_candidate_board_status": _text(
            historical_seed_chronology_candidate_board_summary.get("chronology_board_status")
        ),
        "historical_seed_chronology_candidate_board_row_count": _int(
            historical_seed_chronology_candidate_board_summary.get("row_count")
        ),
        "historical_seed_chronology_candidate_board_ready_count": _int(
            historical_seed_chronology_candidate_board_summary.get("operator_chronology_ready_count")
        ),
        "historical_seed_chronology_candidate_board_warning_count": _int(
            historical_seed_chronology_candidate_board_summary.get("operator_ready_mtime_warning_count")
        ),
        "historical_seed_chronology_candidate_board_evidence_required_count": _int(
            historical_seed_chronology_candidate_board_summary.get("operator_evidence_required_count")
        ),
        "historical_seed_chronology_candidate_board_conflict_count": _int(
            historical_seed_chronology_candidate_board_summary.get("blocked_chronology_conflict_count")
        ),
        "historical_seed_chronology_candidate_board_path_date_count": _int(
            historical_seed_chronology_candidate_board_summary.get("prediction_path_date_count")
        ),
        "historical_seed_chronology_candidate_board_mtime_count": _int(
            historical_seed_chronology_candidate_board_summary.get("file_mtime_candidate_count")
        ),
        "historical_seed_chronology_candidate_board_mtime_risk_count": _int(
            historical_seed_chronology_candidate_board_summary.get("file_mtime_order_risk_count")
        ),
        "historical_seed_chronology_candidate_board_first_target_id": _text(
            historical_seed_chronology_candidate_board_summary.get("first_open_target_id")
        ),
        "historical_seed_chronology_candidate_board_first_next_action": _text(
            historical_seed_chronology_candidate_board_summary.get("first_next_action")
        ),
        "historical_seed_authoritative_chronology_audit_status": _text(
            historical_seed_authoritative_chronology_audit_summary.get("authoritative_chronology_audit_status")
        ),
        "historical_seed_authoritative_chronology_audit_seed_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("seed_row_count")
        ),
        "historical_seed_authoritative_chronology_audit_native_date_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("native_authority_date_count")
        ),
        "historical_seed_authoritative_chronology_audit_prediction_date_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("prediction_date_candidate_count")
        ),
        "historical_seed_authoritative_chronology_audit_before_native_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("before_native_candidate_count")
        ),
        "historical_seed_authoritative_chronology_audit_post_native_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("post_native_blocked_count")
        ),
        "historical_seed_authoritative_chronology_audit_evidence_required_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("evidence_required_count")
        ),
        "historical_seed_authoritative_chronology_audit_native_not_pass_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("native_authority_not_pass_count")
        ),
        "historical_seed_authoritative_chronology_audit_missing_native_date_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("missing_native_authority_date_count")
        ),
        "historical_seed_authoritative_chronology_audit_missing_prediction_date_count": _int(
            historical_seed_authoritative_chronology_audit_summary.get("missing_prediction_date_count")
        ),
        "historical_seed_authoritative_chronology_audit_first_target_id": _text(
            historical_seed_authoritative_chronology_audit_summary.get("first_blocked_target_id")
        ),
        "historical_seed_authoritative_chronology_audit_first_next_action": _text(
            historical_seed_authoritative_chronology_audit_summary.get("first_next_action")
        ),
        "historical_seed_lane_decision_packet_status": _text(
            historical_seed_lane_decision_packet_summary.get("lane_decision_status")
        ),
        "historical_seed_lane_decision_packet_seed_count": _int(
            historical_seed_lane_decision_packet_summary.get("seed_row_count")
        ),
        "historical_seed_lane_decision_packet_strict_blind_count": _int(
            historical_seed_lane_decision_packet_summary.get("strict_blind_eligible_count")
        ),
        "historical_seed_lane_decision_packet_retrospective_count": _int(
            historical_seed_lane_decision_packet_summary.get("retrospective_calibration_review_count")
        ),
        "historical_seed_lane_decision_packet_authority_required_count": _int(
            historical_seed_lane_decision_packet_summary.get("authority_or_replacement_required_count")
        ),
        "historical_seed_lane_decision_packet_competitive_count": _int(
            historical_seed_lane_decision_packet_summary.get("competitive_proof_allowed_count")
        ),
        "historical_seed_lane_decision_packet_identity_count": _int(
            historical_seed_lane_decision_packet_summary.get("identity_intake_allowed_count")
        ),
        "historical_seed_lane_decision_packet_sidechain_count": _int(
            historical_seed_lane_decision_packet_summary.get("sidechain_native_benchmark_allowed_count")
        ),
        "historical_seed_lane_decision_packet_replacement_required_count": _int(
            historical_seed_lane_decision_packet_summary.get("strict_blind_replacement_required_count")
        ),
        "historical_seed_lane_decision_packet_operator_decision_count": _int(
            historical_seed_lane_decision_packet_summary.get("operator_decision_required_count")
        ),
        "historical_seed_lane_decision_packet_first_target_id": _text(
            historical_seed_lane_decision_packet_summary.get("first_blocked_target_id")
        ),
        "historical_seed_lane_decision_packet_first_next_action": _text(
            historical_seed_lane_decision_packet_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_queue_status": _text(
            historical_seed_strict_blind_replacement_queue_summary.get("strict_blind_replacement_queue_status")
        ),
        "historical_seed_strict_blind_replacement_queue_slot_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("scaffold_slot_count")
        ),
        "historical_seed_strict_blind_replacement_queue_monomer_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("monomer_slot_count")
        ),
        "historical_seed_strict_blind_replacement_queue_complex_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("complex_slot_count")
        ),
        "historical_seed_strict_blind_replacement_queue_replacement_required_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("strict_blind_replacement_required_count")
        ),
        "historical_seed_strict_blind_replacement_queue_ready_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("strict_blind_ready_slot_count")
        ),
        "historical_seed_strict_blind_replacement_queue_competitive_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("competitive_proof_allowed_slot_count")
        ),
        "historical_seed_strict_blind_replacement_queue_requirement_field_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("requirement_field_count")
        ),
        "historical_seed_strict_blind_replacement_queue_current_seed_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("current_seed_count")
        ),
        "historical_seed_strict_blind_replacement_queue_current_seed_strict_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("current_seed_strict_blind_count")
        ),
        "historical_seed_strict_blind_replacement_queue_current_seed_retrospective_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("current_seed_retrospective_count")
        ),
        "historical_seed_strict_blind_replacement_queue_current_seed_authority_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("current_seed_authority_required_count")
        ),
        "historical_seed_strict_blind_replacement_queue_current_seed_competitive_count": _int(
            historical_seed_strict_blind_replacement_queue_summary.get("current_seed_competitive_allowed_count")
        ),
        "historical_seed_strict_blind_replacement_queue_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_queue_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_queue_first_next_action": _text(
            historical_seed_strict_blind_replacement_queue_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_intake_status": _text(
            historical_seed_strict_blind_replacement_intake_summary.get(
                "strict_blind_replacement_intake_status"
            )
        ),
        "historical_seed_strict_blind_replacement_intake_slot_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("intake_slot_count")
        ),
        "historical_seed_strict_blind_replacement_intake_required_field_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("required_field_count")
        ),
        "historical_seed_strict_blind_replacement_intake_filled_field_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("filled_field_count")
        ),
        "historical_seed_strict_blind_replacement_intake_missing_field_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("missing_field_count")
        ),
        "historical_seed_strict_blind_replacement_intake_ready_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("ready_for_preflight_count")
        ),
        "historical_seed_strict_blind_replacement_intake_blocked_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("blocked_or_awaiting_count")
        ),
        "historical_seed_strict_blind_replacement_intake_created_template_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("created_template_count")
        ),
        "historical_seed_strict_blind_replacement_intake_preserved_template_count": _int(
            historical_seed_strict_blind_replacement_intake_summary.get("preserved_template_count")
        ),
        "historical_seed_strict_blind_replacement_intake_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_intake_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_intake_first_next_action": _text(
            historical_seed_strict_blind_replacement_intake_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_status": _text(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get(
                "strict_blind_replacement_evidence_dropzone_status"
            )
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("dropzone_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_ready_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("ready_for_intake_patch_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_awaiting_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("awaiting_file_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_file_required_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("file_required_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_file_present_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("file_present_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_file_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("file_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_operator_value_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("operator_value_required_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_patch_preview_count": _int(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("patch_preview_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_evidence_dropzones_first_next_action": _text(
            historical_seed_strict_blind_replacement_evidence_dropzones_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_status": _text(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get(
                "strict_blind_replacement_evidence_action_board_status"
            )
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_action_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("action_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_ready_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("ready_for_quality_audit_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_open_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("open_missing_file_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_blocked_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("blocked_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_prediction_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("prediction_pdb_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_native_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("native_pdb_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_authority_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("native_authority_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_no_leak_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("no_leak_evidence_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_ablation_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("ablation_manifest_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_calibration_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("calibration_values_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_first_action_id": _text(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("first_open_action_id")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_first_field": _text(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("first_open_field")
        ),
        "historical_seed_strict_blind_replacement_evidence_action_board_first_next_action": _text(
            historical_seed_strict_blind_replacement_evidence_action_board_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_status": _text(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                "strict_blind_replacement_evidence_quality_audit_status"
            )
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_slot_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("slot_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_ready_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                "ready_for_quality_review_count"
            )
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_awaiting_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("awaiting_evidence_files_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_blocked_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("blocked_evidence_quality_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_file_required_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("file_required_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_file_present_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("file_present_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_file_missing_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("file_missing_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_pdb_valid_slot_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("pdb_valid_slot_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_pdb_invalid_slot_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("pdb_invalid_slot_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_supporting_valid_slot_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("supporting_valid_slot_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_supporting_invalid_slot_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("supporting_invalid_slot_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_distinct_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                "prediction_native_distinct_count"
            )
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_identical_count": _int(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get(
                "prediction_native_identical_count"
            )
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_first_status": _text(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("first_open_status")
        ),
        "historical_seed_strict_blind_replacement_evidence_quality_audit_first_next_action": _text(
            historical_seed_strict_blind_replacement_evidence_quality_audit_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_status": _text(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get(
                "strict_blind_replacement_evidence_import_gate_status"
            )
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_apply_mode": _text(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("apply_mode")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_action_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("action_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_file_action_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("file_action_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_operator_action_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("operator_value_action_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_ready_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("ready_for_apply_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_applied_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("applied_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_already_applied_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("already_applied_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_awaiting_file_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("awaiting_file_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_awaiting_operator_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("awaiting_operator_value_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_blocked_count": _int(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("blocked_count")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_first_field": _text(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("first_open_field")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_first_status": _text(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("first_open_status")
        ),
        "historical_seed_strict_blind_replacement_evidence_import_gate_first_next_action": _text(
            historical_seed_strict_blind_replacement_evidence_import_gate_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_status": _text(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get(
                "strict_blind_replacement_operator_value_gate_status"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_apply_mode": _text(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("apply_mode")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_template_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("template_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_created_template_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("created_template_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_preserved_template_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("preserved_template_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_action_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("action_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_ready_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("ready_for_apply_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_applied_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("applied_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_already_applied_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("already_applied_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_awaiting_value_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("awaiting_operator_value_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_awaiting_evidence_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("awaiting_evidence_ref_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_awaiting_clearance_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("awaiting_operator_clearance_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_blocked_count": _int(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("blocked_count")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_first_field": _text(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("first_open_field")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_first_status": _text(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("first_open_status")
        ),
        "historical_seed_strict_blind_replacement_operator_value_gate_first_next_action": _text(
            historical_seed_strict_blind_replacement_operator_value_gate_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_status": _text(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "strict_blind_replacement_operator_action_board_status"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_action_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("action_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_ready_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("ready_for_apply_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_applied_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("applied_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_already_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("already_applied_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_open_value_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("open_operator_value_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_open_evidence_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("open_evidence_ref_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_open_clearance_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("open_operator_clearance_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_blocked_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("blocked_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_target_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "replacement_target_id_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_benchmark_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "replacement_benchmark_id_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_non_current_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "target_identity_non_current_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_prediction_date_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "prediction_created_at_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_native_date_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("native_release_date_missing_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_before_native_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "prediction_before_native_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_public_false_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "public_template_false_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_other_team_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("other_team_false_missing_count")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_post_release_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "post_release_false_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_operator_clearance_missing_count": _int(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get(
                "operator_clearance_value_missing_count"
            )
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_first_action_id": _text(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("first_open_action_id")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_first_field": _text(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("first_open_field")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_first_status": _text(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("first_open_status")
        ),
        "historical_seed_strict_blind_replacement_operator_action_board_first_next_action": _text(
            historical_seed_strict_blind_replacement_operator_action_board_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_status": _text(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                "strict_blind_replacement_promotion_gate_status"
            )
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_slot_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("slot_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_ready_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get(
                "ready_for_competitive_proof_count"
            )
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_awaiting_file_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("awaiting_file_evidence_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_awaiting_operator_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("awaiting_operator_values_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_awaiting_apply_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("awaiting_apply_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_awaiting_intake_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("awaiting_intake_preflight_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_blocked_review_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("blocked_review_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_intake_ready_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("intake_ready_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_file_complete_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("file_complete_slot_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_operator_complete_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("operator_complete_slot_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_file_awaiting_action_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("file_awaiting_action_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_operator_awaiting_action_count": _int(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("operator_awaiting_action_count")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_first_phase": _text(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("first_open_phase")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_first_status": _text(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("first_open_status")
        ),
        "historical_seed_strict_blind_replacement_promotion_gate_first_next_action": _text(
            historical_seed_strict_blind_replacement_promotion_gate_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_cycle_status": _text(
            historical_seed_strict_blind_replacement_cycle_summary.get("strict_blind_replacement_cycle_status")
        ),
        "historical_seed_strict_blind_replacement_cycle_slot_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("slot_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_promotion_ready_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("promotion_ready_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_evidence_file_present_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("evidence_file_present_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_evidence_file_missing_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("evidence_file_missing_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_quality_ready_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("quality_ready_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_quality_awaiting_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("quality_awaiting_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_quality_blocked_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("quality_blocked_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_import_ready_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("import_ready_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_import_awaiting_file_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("import_awaiting_file_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_import_awaiting_operator_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("import_awaiting_operator_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_operator_ready_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("operator_ready_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_operator_awaiting_value_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("operator_awaiting_value_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_operator_action_board_ready_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("operator_action_board_ready_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_operator_action_board_action_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("operator_action_board_action_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_operator_action_board_open_value_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("operator_action_board_open_value_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_operator_action_board_open_evidence_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("operator_action_board_open_evidence_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_operator_action_board_open_clearance_count": _int(
            historical_seed_strict_blind_replacement_cycle_summary.get("operator_action_board_open_clearance_count")
        ),
        "historical_seed_strict_blind_replacement_cycle_first_blocking_stage": _text(
            historical_seed_strict_blind_replacement_cycle_summary.get("first_blocking_stage")
        ),
        "historical_seed_strict_blind_replacement_cycle_first_benchmark_id": _text(
            historical_seed_strict_blind_replacement_cycle_summary.get("first_open_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_cycle_first_next_action": _text(
            historical_seed_strict_blind_replacement_cycle_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_status": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get(
                "strict_blind_replacement_first_slot_kit_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_benchmark_id": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("required_benchmark_id")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("required_target_id")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_scope": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("scope")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_evidence_ready_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_ready_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_evidence_open_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_open_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_evidence_blocked_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_blocked_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_evidence_action_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("evidence_action_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_operator_ready_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_ready_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_operator_open_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_open_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_operator_blocked_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_blocked_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_operator_action_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_action_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_operator_open_value_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_open_value_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_operator_open_evidence_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_open_evidence_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_operator_open_clearance_count": _int(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("operator_open_clearance_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_first_action_group": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("first_open_action_group")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_first_action_id": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("first_open_action_id")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_first_field": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("first_open_field")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_first_status": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("first_open_status")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_kit_folder": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("kit_folder")
        ),
        "historical_seed_strict_blind_replacement_first_slot_kit_first_next_action": _text(
            historical_seed_strict_blind_replacement_first_slot_kit_summary.get("first_next_action")
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_status": _text(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "strict_blind_replacement_first_slot_local_candidate_board_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_required_benchmark_id": _text(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "required_benchmark_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_candidate_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get("candidate_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_ready_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "ready_for_first_slot_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_strict_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "strict_blind_eligible_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_material_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "material_present_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_prediction_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "prediction_present_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_native_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "native_present_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_authority_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "native_authority_present_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_chronology_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "blocked_chronology_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_no_leak_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "blocked_no_leak_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_ablation_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "blocked_ablation_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_calibration_count": _int(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "blocked_calibration_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_first_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "first_review_target_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_first_status": _text(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "first_review_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_local_candidate_board_first_next_action": _text(
            historical_seed_strict_blind_replacement_first_slot_local_candidate_board_summary.get(
                "first_review_next_action"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_status": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "strict_blind_replacement_first_slot_candidate_repair_board_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_required_benchmark_id": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "required_benchmark_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_action_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get("action_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_open_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "open_repair_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_blocked_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "blocked_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_chronology_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "chronology_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_no_leak_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "no_leak_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_ablation_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "ablation_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_calibration_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "calibration_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_prediction_file_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "prediction_file_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_native_file_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "native_file_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_native_authority_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "native_authority_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_eligibility_count": _int(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "eligibility_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_action_id": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "first_open_action_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "first_open_target_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_repair_class": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "first_open_repair_class"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_blocker": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "first_open_blocker"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_status": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "first_open_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_next_action": _text(
            historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_summary.get(
                "first_next_action"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_status": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "strict_blind_replacement_first_slot_repair_feasibility_board_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_required_benchmark_id": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "required_benchmark_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_action_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get("action_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_post_native_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "not_repairable_with_current_prediction_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_post_native_eligibility_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "blocked_by_post_native_prediction_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_external_action_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "external_pre_native_artifact_required_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_external_target_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "external_pre_native_artifact_required_target_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_source_required_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "repairable_operator_source_required_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_evidence_required_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "repairable_operator_evidence_required_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_date_required_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "needs_chronology_date_evidence_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_primary_blocked_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "blocked_by_primary_repairs_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_pre_native_count": _int(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "repairable_current_prediction_pre_native_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_action_id": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "first_external_action_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "first_external_target_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_blocker": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "first_external_blocker"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_next_route": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "first_external_next_route"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_actionable_action_id": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "first_actionable_action_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_actionable_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "first_actionable_target_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_actionable_status": _text(
            historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_summary.get(
                "first_actionable_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_status": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "strict_blind_replacement_first_slot_source_route_board_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_required_benchmark_id": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "required_benchmark_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_required_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get("required_target_id")
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_required_scope": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get("required_scope")
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_route_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get("route_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_in_scope_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get("in_scope_route_count")
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_out_of_scope_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "out_of_scope_route_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_allowed_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "allowed_for_first_slot_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_external_required_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "in_scope_external_required_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_external_action_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "in_scope_external_action_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_out_scope_source_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "out_of_scope_source_required_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_out_scope_date_count": _int(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "out_of_scope_date_required_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_route_id": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "first_external_route_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "first_external_target_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_prediction_created_at": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "first_external_prediction_created_at"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_native_release_date": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "first_external_native_release_date"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_next_action": _text(
            historical_seed_strict_blind_replacement_first_slot_source_route_board_summary.get(
                "first_external_next_action"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_status": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "strict_blind_replacement_first_slot_official_archive_source_candidates_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_required_benchmark_id": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "required_benchmark_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_required_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "required_target_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_required_scope": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "required_scope"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_source_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "source_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_source_competitions": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "source_competitions"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_candidate_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "candidate_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_pre_native_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "pre_native_candidate_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_ready_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "ready_candidate_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_blocked_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "blocked_candidate_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_ready_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "native_authority_ready_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_lookup_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "native_authority_lookup_required_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_pdb_ready_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "native_pdb_download_ready_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_mmcif_only_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "native_mmcif_only_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_metadata_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "targetlist_metadata_present_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_capri_marker_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "targetlist_capri_marker_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_special_mode_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "targetlist_special_mode_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_regular_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "regular_monomer_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_domain_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "domain_subunit_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_variant_count": _int(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "variant_count"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_candidate_id": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_candidate_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_competition": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_competition"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_target_id": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_target_id"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_prediction_at": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_prediction_archive_modified_at"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_anchor": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_native_public_anchor_date"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_tarball": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_prediction_tarball_url"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_pdb_code": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_native_pdb_code"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_pdb_url": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_native_pdb_url"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_structure_file_url": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_native_structure_file_url"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_structure_file_format": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_native_structure_file_format"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_download_status": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_native_pdb_download_status"
            )
        ),
        "historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_targetlist_url": _text(
            historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_summary.get(
                "first_ready_targetlist_target_url"
            )
        ),
        "historical_seed_official_archive_baseline_lane_status": _text(
            historical_seed_official_archive_baseline_lane_summary.get("official_archive_baseline_lane_status")
        ),
        "historical_seed_official_archive_baseline_lane_source_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("source_candidate_count")
        ),
        "historical_seed_official_archive_baseline_lane_source_ready_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("source_ready_candidate_count")
        ),
        "historical_seed_official_archive_baseline_lane_candidate_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("baseline_candidate_count")
        ),
        "historical_seed_official_archive_baseline_lane_ready_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("ready_count")
        ),
        "historical_seed_official_archive_baseline_lane_blocked_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("blocked_count")
        ),
        "historical_seed_official_archive_baseline_lane_proof_eligible_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("competitive_proof_eligible_count")
        ),
        "historical_seed_official_archive_baseline_lane_strict_blind_blocked_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("strict_blind_import_blocked_count")
        ),
        "historical_seed_official_archive_baseline_lane_other_team_count": _int(
            historical_seed_official_archive_baseline_lane_summary.get("other_team_model_baseline_only_count")
        ),
        "historical_seed_official_archive_baseline_lane_policy": _text(
            historical_seed_official_archive_baseline_lane_summary.get("strict_blind_intake_policy")
        ),
        "historical_seed_official_archive_baseline_lane_first_candidate_id": _text(
            historical_seed_official_archive_baseline_lane_summary.get("first_baseline_candidate_id")
        ),
        "historical_seed_official_archive_baseline_lane_first_competition": _text(
            historical_seed_official_archive_baseline_lane_summary.get("first_competition")
        ),
        "historical_seed_official_archive_baseline_lane_first_target_id": _text(
            historical_seed_official_archive_baseline_lane_summary.get("first_target_id")
        ),
        "historical_seed_official_archive_baseline_lane_first_native_pdb_code": _text(
            historical_seed_official_archive_baseline_lane_summary.get("first_native_pdb_code")
        ),
        "historical_seed_official_archive_baseline_lane_first_manifest": _text(
            historical_seed_official_archive_baseline_lane_summary.get("first_acquisition_manifest")
        ),
        "strict_blind_first_slot_source_bridge_status": _text(
            strict_blind_first_slot_source_bridge_summary.get("source_bridge_status")
        ),
        "strict_blind_first_slot_source_bridge_required_benchmark_id": _text(
            strict_blind_first_slot_source_bridge_summary.get("required_benchmark_id")
        ),
        "strict_blind_first_slot_source_bridge_required_target_id": _text(
            strict_blind_first_slot_source_bridge_summary.get("required_target_id")
        ),
        "strict_blind_first_slot_source_bridge_required_scope": _text(
            strict_blind_first_slot_source_bridge_summary.get("required_scope")
        ),
        "strict_blind_first_slot_source_bridge_official_candidate_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("official_candidate_count")
        ),
        "strict_blind_first_slot_source_bridge_official_ready_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("official_ready_candidate_count")
        ),
        "strict_blind_first_slot_source_bridge_native_ready_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("native_authority_bridge_ready_count")
        ),
        "strict_blind_first_slot_source_bridge_baseline_only_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("official_prediction_baseline_only_count")
        ),
        "strict_blind_first_slot_source_bridge_strict_blocked_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("strict_blind_import_blocked_count")
        ),
        "strict_blind_first_slot_source_bridge_operator_only_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("operator_only_field_count")
        ),
        "strict_blind_first_slot_source_bridge_internal_prediction_blocked_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("internal_prediction_blocked_count")
        ),
        "strict_blind_first_slot_source_bridge_auto_apply_count": _int(
            strict_blind_first_slot_source_bridge_summary.get("auto_apply_allowed_count")
        ),
        "strict_blind_first_slot_source_bridge_first_candidate_competition": _text(
            strict_blind_first_slot_source_bridge_summary.get("first_candidate_competition")
        ),
        "strict_blind_first_slot_source_bridge_first_candidate_target_id": _text(
            strict_blind_first_slot_source_bridge_summary.get("first_candidate_target_id")
        ),
        "strict_blind_first_slot_source_bridge_first_candidate_native_pdb_code": _text(
            strict_blind_first_slot_source_bridge_summary.get("first_candidate_native_pdb_code")
        ),
        "strict_blind_first_slot_source_bridge_first_blocker": _text(
            strict_blind_first_slot_source_bridge_summary.get("first_blocker")
        ),
        "strict_blind_first_slot_source_bridge_bridge_folder": _text(
            strict_blind_first_slot_source_bridge_summary.get("bridge_folder")
        ),
        "strict_blind_internal_prediction_source_audit_status": _text(
            strict_blind_internal_prediction_source_audit_summary.get("internal_prediction_source_audit_status")
        ),
        "strict_blind_internal_prediction_source_audit_required_benchmark_id": _text(
            strict_blind_internal_prediction_source_audit_summary.get("required_benchmark_id")
        ),
        "strict_blind_internal_prediction_source_audit_required_target_id": _text(
            strict_blind_internal_prediction_source_audit_summary.get("required_target_id")
        ),
        "strict_blind_internal_prediction_source_audit_required_scope": _text(
            strict_blind_internal_prediction_source_audit_summary.get("required_scope")
        ),
        "strict_blind_internal_prediction_source_audit_first_open_field": _text(
            strict_blind_internal_prediction_source_audit_summary.get("first_open_field")
        ),
        "strict_blind_internal_prediction_source_audit_local_candidate_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("local_candidate_count")
        ),
        "strict_blind_internal_prediction_source_audit_local_eligible_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("local_strict_blind_eligible_count")
        ),
        "strict_blind_internal_prediction_source_audit_source_route_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("source_route_count")
        ),
        "strict_blind_internal_prediction_source_audit_source_route_allowed_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("source_route_allowed_count")
        ),
        "strict_blind_internal_prediction_source_audit_official_baseline_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("official_baseline_candidate_count")
        ),
        "strict_blind_internal_prediction_source_audit_official_blocked_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("official_strict_blind_blocked_count")
        ),
        "strict_blind_internal_prediction_source_audit_native_ready_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("native_authority_bridge_ready_count")
        ),
        "strict_blind_internal_prediction_source_audit_internal_blocked_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("internal_prediction_blocked_count")
        ),
        "strict_blind_internal_prediction_source_audit_allowed_internal_source_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("allowed_internal_source_count")
        ),
        "strict_blind_internal_prediction_source_audit_template_count": _int(
            strict_blind_internal_prediction_source_audit_summary.get("template_count")
        ),
        "strict_blind_internal_prediction_source_audit_manifest_template": _text(
            strict_blind_internal_prediction_source_audit_summary.get("internal_source_manifest_template")
        ),
        "strict_blind_internal_prediction_source_audit_first_blocker": _text(
            strict_blind_internal_prediction_source_audit_summary.get("first_blocker")
        ),
        "strict_blind_internal_prediction_source_gate_status": _text(
            strict_blind_internal_prediction_source_gate_summary.get("internal_prediction_source_gate_status")
        ),
        "strict_blind_internal_prediction_source_gate_required_benchmark_id": _text(
            strict_blind_internal_prediction_source_gate_summary.get("required_benchmark_id")
        ),
        "strict_blind_internal_prediction_source_gate_required_target_id": _text(
            strict_blind_internal_prediction_source_gate_summary.get("required_target_id")
        ),
        "strict_blind_internal_prediction_source_gate_required_scope": _text(
            strict_blind_internal_prediction_source_gate_summary.get("required_scope")
        ),
        "strict_blind_internal_prediction_source_gate_manifest_row_count": _int(
            strict_blind_internal_prediction_source_gate_summary.get("manifest_row_count")
        ),
        "strict_blind_internal_prediction_source_gate_pass_count": _int(
            strict_blind_internal_prediction_source_gate_summary.get("pass_count")
        ),
        "strict_blind_internal_prediction_source_gate_blocked_count": _int(
            strict_blind_internal_prediction_source_gate_summary.get("blocked_count")
        ),
        "strict_blind_internal_prediction_source_gate_check_count": _int(
            strict_blind_internal_prediction_source_gate_summary.get("check_count")
        ),
        "strict_blind_internal_prediction_source_gate_manifest_csv": _text(
            strict_blind_internal_prediction_source_gate_summary.get("manifest_csv")
        ),
        "strict_blind_internal_prediction_source_gate_source_id": _text(
            strict_blind_internal_prediction_source_gate_summary.get("source_id")
        ),
        "strict_blind_internal_prediction_source_gate_prediction_pdb": _text(
            strict_blind_internal_prediction_source_gate_summary.get("manifest_prediction_pdb")
        ),
        "strict_blind_internal_prediction_source_gate_prediction_dropzone": _text(
            strict_blind_internal_prediction_source_gate_summary.get("prediction_dropzone")
        ),
        "strict_blind_internal_prediction_source_gate_first_blocked_check": _text(
            strict_blind_internal_prediction_source_gate_summary.get("first_blocked_check")
        ),
        "strict_blind_internal_prediction_source_gate_first_blocker": _text(
            strict_blind_internal_prediction_source_gate_summary.get("first_blocker")
        ),
        "strict_blind_source_gate_field_board_status": _text(
            strict_blind_source_gate_field_board_summary.get("source_gate_field_board_status")
        ),
        "strict_blind_source_gate_field_board_required_benchmark_id": _text(
            strict_blind_source_gate_field_board_summary.get("required_benchmark_id")
        ),
        "strict_blind_source_gate_field_board_required_target_id": _text(
            strict_blind_source_gate_field_board_summary.get("required_target_id")
        ),
        "strict_blind_source_gate_field_board_required_scope": _text(
            strict_blind_source_gate_field_board_summary.get("required_scope")
        ),
        "strict_blind_source_gate_field_board_field_action_count": _int(
            strict_blind_source_gate_field_board_summary.get("field_action_count")
        ),
        "strict_blind_source_gate_field_board_manifest_value_action_count": _int(
            strict_blind_source_gate_field_board_summary.get("manifest_value_action_count")
        ),
        "strict_blind_source_gate_field_board_file_action_count": _int(
            strict_blind_source_gate_field_board_summary.get("file_action_count")
        ),
        "strict_blind_source_gate_field_board_manifest_file_action_count": _int(
            strict_blind_source_gate_field_board_summary.get("manifest_file_action_count")
        ),
        "strict_blind_source_gate_field_board_blocked_check_covered_count": _int(
            strict_blind_source_gate_field_board_summary.get("blocked_check_covered_count")
        ),
        "strict_blind_source_gate_field_board_first_field_key": _text(
            strict_blind_source_gate_field_board_summary.get("first_field_key")
        ),
        "strict_blind_source_gate_field_board_first_blockers": _text(
            strict_blind_source_gate_field_board_summary.get("first_blockers")
        ),
        "strict_blind_source_gate_field_board_dir": _text(
            strict_blind_source_gate_field_board_summary.get("board_dir")
        ),
        "strict_blind_source_gate_operator_packet_status": _text(
            strict_blind_source_gate_operator_packet_summary.get("source_gate_operator_packet_status")
        ),
        "strict_blind_source_gate_operator_packet_required_benchmark_id": _text(
            strict_blind_source_gate_operator_packet_summary.get("required_benchmark_id")
        ),
        "strict_blind_source_gate_operator_packet_required_target_id": _text(
            strict_blind_source_gate_operator_packet_summary.get("required_target_id")
        ),
        "strict_blind_source_gate_operator_packet_required_scope": _text(
            strict_blind_source_gate_operator_packet_summary.get("required_scope")
        ),
        "strict_blind_source_gate_operator_packet_field_action_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("field_action_count")
        ),
        "strict_blind_source_gate_operator_packet_operator_ready_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("operator_ready_count")
        ),
        "strict_blind_source_gate_operator_packet_operator_awaiting_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("operator_awaiting_count")
        ),
        "strict_blind_source_gate_operator_packet_manifest_patch_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("manifest_patch_count")
        ),
        "strict_blind_source_gate_operator_packet_file_copy_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("file_copy_count")
        ),
        "strict_blind_source_gate_operator_packet_derived_check_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("derived_check_count")
        ),
        "strict_blind_source_gate_operator_packet_patch_ready_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("patch_ready_count")
        ),
        "strict_blind_source_gate_operator_packet_patch_awaiting_count": _int(
            strict_blind_source_gate_operator_packet_summary.get("patch_awaiting_count")
        ),
        "strict_blind_source_gate_operator_packet_first_field_key": _text(
            strict_blind_source_gate_operator_packet_summary.get("first_field_key")
        ),
        "strict_blind_source_gate_operator_packet_first_operator_status": _text(
            strict_blind_source_gate_operator_packet_summary.get("first_operator_status")
        ),
        "strict_blind_source_gate_operator_packet_first_next_action": _text(
            strict_blind_source_gate_operator_packet_summary.get("first_next_action")
        ),
        "strict_blind_source_gate_operator_packet_operator_csv": _text(
            strict_blind_source_gate_operator_packet_summary.get("operator_csv")
        ),
        "strict_blind_source_gate_operator_packet_dir": _text(
            strict_blind_source_gate_operator_packet_summary.get("packet_dir")
        ),
        "strict_blind_source_gate_source_request_packet_status": _text(
            strict_blind_source_gate_source_request_packet_summary.get("source_request_packet_status")
        ),
        "strict_blind_source_gate_source_request_packet_required_benchmark_id": _text(
            strict_blind_source_gate_source_request_packet_summary.get("required_benchmark_id")
        ),
        "strict_blind_source_gate_source_request_packet_required_target_id": _text(
            strict_blind_source_gate_source_request_packet_summary.get("required_target_id")
        ),
        "strict_blind_source_gate_source_request_packet_required_scope": _text(
            strict_blind_source_gate_source_request_packet_summary.get("required_scope")
        ),
        "strict_blind_source_gate_source_request_packet_request_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("request_count")
        ),
        "strict_blind_source_gate_source_request_packet_pre_native_source_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("pre_native_source_required_count")
        ),
        "strict_blind_source_gate_source_request_packet_candidate_replacement_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("candidate_replacement_required_count")
        ),
        "strict_blind_source_gate_source_request_packet_operator_repair_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("operator_evidence_repair_required_count")
        ),
        "strict_blind_source_gate_source_request_packet_operator_template_ready_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("operator_template_ready_count")
        ),
        "strict_blind_source_gate_source_request_packet_operator_template_awaiting_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("operator_template_awaiting_count")
        ),
        "strict_blind_source_gate_source_request_packet_operator_field_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("operator_field_count")
        ),
        "strict_blind_source_gate_source_request_packet_operator_field_filled_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("operator_field_filled_count")
        ),
        "strict_blind_source_gate_source_request_packet_operator_field_missing_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("operator_field_missing_count")
        ),
        "strict_blind_source_gate_source_request_packet_monomer_request_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("monomer_request_count")
        ),
        "strict_blind_source_gate_source_request_packet_complex_request_count": _int(
            strict_blind_source_gate_source_request_packet_summary.get("complex_request_count")
        ),
        "strict_blind_source_gate_source_request_packet_first_request_id": _text(
            strict_blind_source_gate_source_request_packet_summary.get("first_request_id")
        ),
        "strict_blind_source_gate_source_request_packet_first_target_id": _text(
            strict_blind_source_gate_source_request_packet_summary.get("first_request_target_id")
        ),
        "strict_blind_source_gate_source_request_packet_first_kind": _text(
            strict_blind_source_gate_source_request_packet_summary.get("first_request_kind")
        ),
        "strict_blind_source_gate_source_request_packet_first_blocker": _text(
            strict_blind_source_gate_source_request_packet_summary.get("first_request_blocker")
        ),
        "strict_blind_source_gate_source_request_packet_first_missing_operator_field": _text(
            strict_blind_source_gate_source_request_packet_summary.get("first_missing_operator_field")
        ),
        "strict_blind_source_gate_source_request_packet_dir": _text(
            strict_blind_source_gate_source_request_packet_summary.get("request_dir")
        ),
        "strict_blind_source_request_fulfillment_gate_status": _text(
            strict_blind_source_request_fulfillment_gate_summary.get("source_request_fulfillment_gate_status")
        ),
        "strict_blind_source_request_fulfillment_gate_request_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("request_count")
        ),
        "strict_blind_source_request_fulfillment_gate_ready_request_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("ready_request_count")
        ),
        "strict_blind_source_request_fulfillment_gate_blocked_request_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("blocked_request_count")
        ),
        "strict_blind_source_request_fulfillment_gate_operator_field_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("operator_field_count")
        ),
        "strict_blind_source_request_fulfillment_gate_operator_field_filled_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("operator_field_filled_count")
        ),
        "strict_blind_source_request_fulfillment_gate_operator_field_missing_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("operator_field_missing_count")
        ),
        "strict_blind_source_request_fulfillment_gate_operator_evidence_ref_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("operator_evidence_ref_count")
        ),
        "strict_blind_source_request_fulfillment_gate_operator_evidence_ref_missing_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("operator_evidence_ref_missing_count")
        ),
        "strict_blind_source_request_fulfillment_gate_prediction_pdb_valid_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("prediction_pdb_valid_count")
        ),
        "strict_blind_source_request_fulfillment_gate_chronology_pass_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("chronology_pass_count")
        ),
        "strict_blind_source_request_fulfillment_gate_internal_source_pass_count": _int(
            strict_blind_source_request_fulfillment_gate_summary.get("internal_source_pass_count")
        ),
        "strict_blind_source_request_fulfillment_gate_first_blocked_request_id": _text(
            strict_blind_source_request_fulfillment_gate_summary.get("first_blocked_request_id")
        ),
        "strict_blind_source_request_fulfillment_gate_first_blocked_target_id": _text(
            strict_blind_source_request_fulfillment_gate_summary.get("first_blocked_target_id")
        ),
        "strict_blind_source_request_fulfillment_gate_first_blocker": _text(
            strict_blind_source_request_fulfillment_gate_summary.get("first_blocker")
        ),
        "strict_blind_source_request_operator_fill_worklist_status": _text(
            strict_blind_source_request_operator_fill_worklist_summary.get("source_request_operator_fill_worklist_status")
        ),
        "strict_blind_source_request_operator_fill_worklist_request_count": _int(
            strict_blind_source_request_operator_fill_worklist_summary.get("request_count")
        ),
        "strict_blind_source_request_operator_fill_worklist_field_action_count": _int(
            strict_blind_source_request_operator_fill_worklist_summary.get("field_action_count")
        ),
        "strict_blind_source_request_operator_fill_worklist_field_ready_count": _int(
            strict_blind_source_request_operator_fill_worklist_summary.get("field_ready_count")
        ),
        "strict_blind_source_request_operator_fill_worklist_operator_value_missing_count": _int(
            strict_blind_source_request_operator_fill_worklist_summary.get("operator_value_missing_count")
        ),
        "strict_blind_source_request_operator_fill_worklist_operator_evidence_missing_count": _int(
            strict_blind_source_request_operator_fill_worklist_summary.get("operator_evidence_missing_count")
        ),
        "strict_blind_source_request_operator_fill_worklist_candidate_replacement_field_count": _int(
            strict_blind_source_request_operator_fill_worklist_summary.get("candidate_replacement_field_count")
        ),
        "strict_blind_source_request_operator_fill_worklist_first_fill_id": _text(
            strict_blind_source_request_operator_fill_worklist_summary.get("first_fill_id")
        ),
        "strict_blind_source_request_operator_fill_worklist_first_request_id": _text(
            strict_blind_source_request_operator_fill_worklist_summary.get("first_request_id")
        ),
        "strict_blind_source_request_operator_fill_worklist_first_target_id": _text(
            strict_blind_source_request_operator_fill_worklist_summary.get("first_target_id")
        ),
        "strict_blind_source_request_operator_fill_worklist_first_field_key": _text(
            strict_blind_source_request_operator_fill_worklist_summary.get("first_field_key")
        ),
        "strict_blind_source_request_operator_fill_worklist_first_blocker": _text(
            strict_blind_source_request_operator_fill_worklist_summary.get("first_blocker")
        ),
        "strict_blind_source_request_operator_sync_plan_status": _text(
            strict_blind_source_request_operator_sync_plan_summary.get("source_request_operator_sync_plan_status")
        ),
        "strict_blind_source_request_operator_sync_plan_mode": _text(
            strict_blind_source_request_operator_sync_plan_summary.get("sync_mode")
        ),
        "strict_blind_source_request_operator_sync_plan_ready_request_count": _int(
            strict_blind_source_request_operator_sync_plan_summary.get("ready_request_count")
        ),
        "strict_blind_source_request_operator_sync_plan_blocked_request_count": _int(
            strict_blind_source_request_operator_sync_plan_summary.get("blocked_request_count")
        ),
        "strict_blind_source_request_operator_sync_plan_selected_request_id": _text(
            strict_blind_source_request_operator_sync_plan_summary.get("selected_request_id")
        ),
        "strict_blind_source_request_operator_sync_plan_selected_target_id": _text(
            strict_blind_source_request_operator_sync_plan_summary.get("selected_target_id")
        ),
        "strict_blind_source_request_operator_sync_plan_destination_operator_csv": _text(
            strict_blind_source_request_operator_sync_plan_summary.get("destination_operator_csv")
        ),
        "strict_blind_source_request_operator_sync_plan_sync_action_count": _int(
            strict_blind_source_request_operator_sync_plan_summary.get("sync_action_count")
        ),
        "strict_blind_source_request_operator_sync_plan_ready_sync_action_count": _int(
            strict_blind_source_request_operator_sync_plan_summary.get("ready_sync_action_count")
        ),
        "strict_blind_source_request_operator_sync_plan_blocked_sync_action_count": _int(
            strict_blind_source_request_operator_sync_plan_summary.get("blocked_sync_action_count")
        ),
        "strict_blind_source_request_operator_sync_plan_applied_sync_action_count": _int(
            strict_blind_source_request_operator_sync_plan_summary.get("applied_sync_action_count")
        ),
        "strict_blind_source_request_operator_sync_plan_first_action_id": _text(
            strict_blind_source_request_operator_sync_plan_summary.get("first_action_id")
        ),
        "strict_blind_source_request_operator_sync_plan_first_blocker": _text(
            strict_blind_source_request_operator_sync_plan_summary.get("first_blocker")
        ),
        "strict_blind_source_request_closure_board_status": _text(
            strict_blind_source_request_closure_board_summary.get("strict_blind_source_request_closure_board_status")
        ),
        "strict_blind_source_request_closure_board_required_benchmark_id": _text(
            strict_blind_source_request_closure_board_summary.get("required_benchmark_id")
        ),
        "strict_blind_source_request_closure_board_required_target_id": _text(
            strict_blind_source_request_closure_board_summary.get("required_target_id")
        ),
        "strict_blind_source_request_closure_board_required_scope": _text(
            strict_blind_source_request_closure_board_summary.get("required_scope")
        ),
        "strict_blind_source_request_closure_board_stage_count": _int(
            strict_blind_source_request_closure_board_summary.get("stage_count")
        ),
        "strict_blind_source_request_closure_board_ready_stage_count": _int(
            strict_blind_source_request_closure_board_summary.get("ready_stage_count")
        ),
        "strict_blind_source_request_closure_board_blocked_stage_count": _int(
            strict_blind_source_request_closure_board_summary.get("blocked_stage_count")
        ),
        "strict_blind_source_request_closure_board_first_blocked_stage_id": _text(
            strict_blind_source_request_closure_board_summary.get("first_blocked_stage_id")
        ),
        "strict_blind_source_request_closure_board_first_blocked_stage_status": _text(
            strict_blind_source_request_closure_board_summary.get("first_blocked_stage_status")
        ),
        "strict_blind_source_request_closure_board_first_blocker": _text(
            strict_blind_source_request_closure_board_summary.get("first_blocker")
        ),
        "strict_blind_source_request_closure_board_next_action": _text(
            strict_blind_source_request_closure_board_summary.get("next_action")
        ),
        "strict_blind_source_request_closure_board_source_request_status": _text(
            strict_blind_source_request_closure_board_summary.get("source_request_status")
        ),
        "strict_blind_source_request_closure_board_fulfillment_gate_status": _text(
            strict_blind_source_request_closure_board_summary.get("fulfillment_gate_status")
        ),
        "strict_blind_source_request_closure_board_operator_fill_worklist_status": _text(
            strict_blind_source_request_closure_board_summary.get("operator_fill_worklist_status")
        ),
        "strict_blind_source_request_closure_board_operator_sync_plan_status": _text(
            strict_blind_source_request_closure_board_summary.get("operator_sync_plan_status")
        ),
        "strict_blind_source_request_closure_board_source_gate_operator_packet_status": _text(
            strict_blind_source_request_closure_board_summary.get("source_gate_operator_packet_status")
        ),
        "strict_blind_source_request_closure_board_internal_prediction_source_gate_status": _text(
            strict_blind_source_request_closure_board_summary.get("internal_prediction_source_gate_status")
        ),
        "strict_blind_source_request_closure_board_internal_prediction_apply_plan_status": _text(
            strict_blind_source_request_closure_board_summary.get("internal_prediction_apply_plan_status")
        ),
        "strict_blind_source_request_closure_board_first_slot_closure_kit_status": _text(
            strict_blind_source_request_closure_board_summary.get("first_slot_closure_kit_status")
        ),
        "strict_blind_source_request_closure_board_batch_closure_runway_status": _text(
            strict_blind_source_request_closure_board_summary.get("batch_closure_runway_status")
        ),
        "strict_blind_internal_prediction_source_apply_plan_status": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get(
                "internal_prediction_source_apply_plan_status"
            )
        ),
        "strict_blind_internal_prediction_source_apply_plan_required_benchmark_id": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("required_benchmark_id")
        ),
        "strict_blind_internal_prediction_source_apply_plan_required_target_id": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("required_target_id")
        ),
        "strict_blind_internal_prediction_source_apply_plan_required_scope": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("required_scope")
        ),
        "strict_blind_internal_prediction_source_apply_plan_gate_status": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("gate_status")
        ),
        "strict_blind_internal_prediction_source_apply_plan_ready_action_count": _int(
            strict_blind_internal_prediction_source_apply_plan_summary.get("ready_action_count")
        ),
        "strict_blind_internal_prediction_source_apply_plan_blocked_action_count": _int(
            strict_blind_internal_prediction_source_apply_plan_summary.get("blocked_action_count")
        ),
        "strict_blind_internal_prediction_source_apply_plan_action_count": _int(
            strict_blind_internal_prediction_source_apply_plan_summary.get("action_count")
        ),
        "strict_blind_internal_prediction_source_apply_plan_file_action_count": _int(
            strict_blind_internal_prediction_source_apply_plan_summary.get("file_action_count")
        ),
        "strict_blind_internal_prediction_source_apply_plan_operator_value_action_count": _int(
            strict_blind_internal_prediction_source_apply_plan_summary.get("operator_value_action_count")
        ),
        "strict_blind_internal_prediction_source_apply_plan_supplemental_action_count": _int(
            strict_blind_internal_prediction_source_apply_plan_summary.get("supplemental_evidence_action_count")
        ),
        "strict_blind_internal_prediction_source_apply_plan_prediction_source": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("prediction_source")
        ),
        "strict_blind_internal_prediction_source_apply_plan_prediction_destination": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("prediction_destination")
        ),
        "strict_blind_internal_prediction_source_apply_plan_first_blocked_action_id": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("first_blocked_action_id")
        ),
        "strict_blind_internal_prediction_source_apply_plan_first_blocker": _text(
            strict_blind_internal_prediction_source_apply_plan_summary.get("first_blocker")
        ),
        "strict_blind_first_slot_closure_kit_status": _text(
            strict_blind_first_slot_closure_kit_summary.get("first_slot_closure_kit_status")
        ),
        "strict_blind_first_slot_closure_kit_required_benchmark_id": _text(
            strict_blind_first_slot_closure_kit_summary.get("required_benchmark_id")
        ),
        "strict_blind_first_slot_closure_kit_required_target_id": _text(
            strict_blind_first_slot_closure_kit_summary.get("required_target_id")
        ),
        "strict_blind_first_slot_closure_kit_required_scope": _text(
            strict_blind_first_slot_closure_kit_summary.get("required_scope")
        ),
        "strict_blind_first_slot_closure_kit_step_ready_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("step_ready_count")
        ),
        "strict_blind_first_slot_closure_kit_step_blocked_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("step_blocked_count")
        ),
        "strict_blind_first_slot_closure_kit_step_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("step_count")
        ),
        "strict_blind_first_slot_closure_kit_source_gate_fill_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("source_gate_fill_count")
        ),
        "strict_blind_first_slot_closure_kit_source_request_fill_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("source_request_fill_count")
        ),
        "strict_blind_first_slot_closure_kit_file_fill_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("file_fill_count")
        ),
        "strict_blind_first_slot_closure_kit_operator_fill_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("operator_fill_count")
        ),
        "strict_blind_first_slot_closure_kit_fill_item_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("fill_item_count")
        ),
        "strict_blind_first_slot_closure_kit_source_gate_status": _text(
            strict_blind_first_slot_closure_kit_summary.get("source_gate_status")
        ),
        "strict_blind_first_slot_closure_kit_source_request_packet_status": _text(
            strict_blind_first_slot_closure_kit_summary.get("source_gate_source_request_packet_status")
        ),
        "strict_blind_first_slot_closure_kit_source_request_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("source_gate_source_request_count")
        ),
        "strict_blind_first_slot_closure_kit_source_request_pre_native_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("source_gate_pre_native_source_request_count")
        ),
        "strict_blind_first_slot_closure_kit_source_request_candidate_replacement_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("source_gate_candidate_replacement_request_count")
        ),
        "strict_blind_first_slot_closure_kit_source_request_operator_repair_count": _int(
            strict_blind_first_slot_closure_kit_summary.get("source_gate_operator_evidence_repair_request_count")
        ),
        "strict_blind_first_slot_closure_kit_apply_plan_status": _text(
            strict_blind_first_slot_closure_kit_summary.get("apply_plan_status")
        ),
        "strict_blind_first_slot_closure_kit_dropzone_status": _text(
            strict_blind_first_slot_closure_kit_summary.get("dropzone_status")
        ),
        "strict_blind_first_slot_closure_kit_operator_gate_status": _text(
            strict_blind_first_slot_closure_kit_summary.get("operator_gate_status")
        ),
        "strict_blind_first_slot_closure_kit_intake_preflight_status": _text(
            strict_blind_first_slot_closure_kit_summary.get("intake_preflight_status")
        ),
        "strict_blind_first_slot_closure_kit_first_blocked_step": _text(
            strict_blind_first_slot_closure_kit_summary.get("first_blocked_step")
        ),
        "strict_blind_first_slot_closure_kit_first_blocker": _text(
            strict_blind_first_slot_closure_kit_summary.get("first_blocker")
        ),
        "strict_blind_first_slot_closure_kit_folder": _text(
            strict_blind_first_slot_closure_kit_summary.get("kit_folder")
        ),
        "strict_blind_batch_closure_runway_status": _text(
            strict_blind_batch_closure_runway_summary.get("batch_closure_runway_status")
        ),
        "strict_blind_batch_closure_runway_slot_count": _int(
            strict_blind_batch_closure_runway_summary.get("slot_count")
        ),
        "strict_blind_batch_closure_runway_ready_slot_count": _int(
            strict_blind_batch_closure_runway_summary.get("ready_slot_count")
        ),
        "strict_blind_batch_closure_runway_blocked_slot_count": _int(
            strict_blind_batch_closure_runway_summary.get("blocked_slot_count")
        ),
        "strict_blind_batch_closure_runway_source_gate_blocked_count": _int(
            strict_blind_batch_closure_runway_summary.get("source_gate_blocked_count")
        ),
        "strict_blind_batch_closure_runway_evidence_blocked_count": _int(
            strict_blind_batch_closure_runway_summary.get("evidence_file_blocked_count")
        ),
        "strict_blind_batch_closure_runway_operator_blocked_count": _int(
            strict_blind_batch_closure_runway_summary.get("operator_value_blocked_count")
        ),
        "strict_blind_batch_closure_runway_intake_blocked_count": _int(
            strict_blind_batch_closure_runway_summary.get("intake_preflight_blocked_count")
        ),
        "strict_blind_batch_closure_runway_file_present_count": _int(
            strict_blind_batch_closure_runway_summary.get("file_present_count")
        ),
        "strict_blind_batch_closure_runway_file_missing_count": _int(
            strict_blind_batch_closure_runway_summary.get("file_missing_count")
        ),
        "strict_blind_batch_closure_runway_operator_ready_count": _int(
            strict_blind_batch_closure_runway_summary.get("operator_ready_count")
        ),
        "strict_blind_batch_closure_runway_operator_open_count": _int(
            strict_blind_batch_closure_runway_summary.get("operator_open_count")
        ),
        "strict_blind_batch_closure_runway_intake_filled_count": _int(
            strict_blind_batch_closure_runway_summary.get("intake_filled_count")
        ),
        "strict_blind_batch_closure_runway_intake_missing_count": _int(
            strict_blind_batch_closure_runway_summary.get("intake_missing_count")
        ),
        "strict_blind_batch_closure_runway_first_blocked_rank": _int(
            strict_blind_batch_closure_runway_summary.get("first_blocked_rank")
        ),
        "strict_blind_batch_closure_runway_first_blocked_benchmark_id": _text(
            strict_blind_batch_closure_runway_summary.get("first_blocked_benchmark_id")
        ),
        "strict_blind_batch_closure_runway_first_stage": _text(
            strict_blind_batch_closure_runway_summary.get("first_blocking_stage")
        ),
        "strict_blind_batch_closure_runway_first_blocker": _text(
            strict_blind_batch_closure_runway_summary.get("first_blocker")
        ),
        "historical_seed_ablation_candidate_manifests_status": _text(
            historical_seed_ablation_candidate_manifests_summary.get("ablation_candidate_status")
        ),
        "historical_seed_ablation_candidate_manifests_seed_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("seed_row_count")
        ),
        "historical_seed_ablation_candidate_manifests_manifest_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("candidate_manifest_count")
        ),
        "historical_seed_ablation_candidate_manifests_candidate_row_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("candidate_row_count")
        ),
        "historical_seed_ablation_candidate_manifests_selected_present_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("selected_prediction_present_count")
        ),
        "historical_seed_ablation_candidate_manifests_native_present_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("native_reference_present_count")
        ),
        "historical_seed_ablation_candidate_manifests_baseline_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("baseline_candidate_present_count")
        ),
        "historical_seed_ablation_candidate_manifests_layer_gap_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("layer_evidence_gap_count")
        ),
        "historical_seed_ablation_candidate_manifests_operator_review_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("operator_review_required_count")
        ),
        "historical_seed_ablation_candidate_manifests_ready_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("ready_for_operator_reference_count")
        ),
        "historical_seed_ablation_candidate_manifests_core_blocked_count": _int(
            historical_seed_ablation_candidate_manifests_summary.get("blocked_core_candidate_input_count")
        ),
        "historical_seed_ablation_candidate_manifests_first_target_id": _text(
            historical_seed_ablation_candidate_manifests_summary.get("first_open_target_id")
        ),
        "historical_seed_ablation_candidate_manifests_first_next_action": _text(
            historical_seed_ablation_candidate_manifests_summary.get("first_next_action")
        ),
        "historical_seed_ablation_gap_repair_plan_status": _text(
            historical_seed_ablation_gap_repair_plan_summary.get("ablation_gap_repair_status")
        ),
        "historical_seed_ablation_gap_repair_plan_seed_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("seed_row_count")
        ),
        "historical_seed_ablation_gap_repair_plan_repair_csv_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("repair_csv_count")
        ),
        "historical_seed_ablation_gap_repair_plan_real_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("real_ablation_candidate_count")
        ),
        "historical_seed_ablation_gap_repair_plan_missing_real_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("missing_real_ablation_candidate_count")
        ),
        "historical_seed_ablation_gap_repair_plan_top5_decoy_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("top5_review_decoy_count")
        ),
        "historical_seed_ablation_gap_repair_plan_top5_copy_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("top5_selected_copy_count")
        ),
        "historical_seed_ablation_gap_repair_plan_ready_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("ready_for_operator_review_count")
        ),
        "historical_seed_ablation_gap_repair_plan_gap_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("gap_repair_required_count")
        ),
        "historical_seed_ablation_gap_repair_plan_core_blocked_count": _int(
            historical_seed_ablation_gap_repair_plan_summary.get("blocked_core_ablation_input_count")
        ),
        "historical_seed_ablation_gap_repair_plan_first_target_id": _text(
            historical_seed_ablation_gap_repair_plan_summary.get("first_open_target_id")
        ),
        "historical_seed_ablation_gap_repair_plan_first_next_action": _text(
            historical_seed_ablation_gap_repair_plan_summary.get("first_next_action")
        ),
        "historical_seed_top5_candidate_pools_status": _text(
            historical_seed_top5_candidate_pools_summary.get("top5_candidate_pool_status")
        ),
        "historical_seed_top5_candidate_pools_seed_count": _int(
            historical_seed_top5_candidate_pools_summary.get("seed_row_count")
        ),
        "historical_seed_top5_candidate_pools_pool_count": _int(
            historical_seed_top5_candidate_pools_summary.get("pool_count")
        ),
        "historical_seed_top5_candidate_pools_candidate_model_count": _int(
            historical_seed_top5_candidate_pools_summary.get("candidate_model_count")
        ),
        "historical_seed_top5_candidate_pools_complete_count": _int(
            historical_seed_top5_candidate_pools_summary.get("complete_top5_pool_count")
        ),
        "historical_seed_top5_candidate_pools_gap_count": _int(
            historical_seed_top5_candidate_pools_summary.get("candidate_pool_gap_count")
        ),
        "historical_seed_top5_candidate_pools_source_present_count": _int(
            historical_seed_top5_candidate_pools_summary.get("selected_source_present_count")
        ),
        "historical_seed_top5_candidate_pools_generated_perturbation_count": _int(
            historical_seed_top5_candidate_pools_summary.get("generated_perturbation_count")
        ),
        "historical_seed_top5_candidate_pools_blocked_source_count": _int(
            historical_seed_top5_candidate_pools_summary.get("blocked_selected_source_count")
        ),
        "historical_seed_top5_candidate_pools_first_target_id": _text(
            historical_seed_top5_candidate_pools_summary.get("first_open_target_id")
        ),
        "historical_seed_top5_candidate_pools_first_next_action": _text(
            historical_seed_top5_candidate_pools_summary.get("first_next_action")
        ),
        "historical_seed_internal_score_candidates_status": _text(
            historical_seed_internal_score_candidates_summary.get("internal_score_candidate_status")
        ),
        "historical_seed_internal_score_candidates_seed_count": _int(
            historical_seed_internal_score_candidates_summary.get("seed_row_count")
        ),
        "historical_seed_internal_score_candidates_candidate_count": _int(
            historical_seed_internal_score_candidates_summary.get("candidate_count")
        ),
        "historical_seed_internal_score_candidates_scored_count": _int(
            historical_seed_internal_score_candidates_summary.get("scored_candidate_count")
        ),
        "historical_seed_internal_score_candidates_top5_scored_count": _int(
            historical_seed_internal_score_candidates_summary.get("top5_scored_ready_count")
        ),
        "historical_seed_internal_score_candidates_selected_score_count": _int(
            historical_seed_internal_score_candidates_summary.get("selected_score_candidate_count")
        ),
        "historical_seed_internal_score_candidates_blocked_count": _int(
            historical_seed_internal_score_candidates_summary.get("blocked_candidate_input_count")
        ),
        "historical_seed_internal_score_candidates_first_target_id": _text(
            historical_seed_internal_score_candidates_summary.get("first_open_target_id")
        ),
        "historical_seed_internal_score_candidates_first_next_action": _text(
            historical_seed_internal_score_candidates_summary.get("first_next_action")
        ),
        "historical_seed_native_oracle_metric_candidates_status": _text(
            historical_seed_native_oracle_metric_candidates_summary.get("native_metric_candidate_status")
        ),
        "historical_seed_native_oracle_metric_candidates_seed_count": _int(
            historical_seed_native_oracle_metric_candidates_summary.get("seed_row_count")
        ),
        "historical_seed_native_oracle_metric_candidates_candidate_count": _int(
            historical_seed_native_oracle_metric_candidates_summary.get("candidate_count")
        ),
        "historical_seed_native_oracle_metric_candidates_metric_count": _int(
            historical_seed_native_oracle_metric_candidates_summary.get("metric_candidate_count")
        ),
        "historical_seed_native_oracle_metric_candidates_top5_ready_count": _int(
            historical_seed_native_oracle_metric_candidates_summary.get("top5_native_metric_ready_count")
        ),
        "historical_seed_native_oracle_metric_candidates_selected_count": _int(
            historical_seed_native_oracle_metric_candidates_summary.get("selected_native_metric_candidate_count")
        ),
        "historical_seed_native_oracle_metric_candidates_best_count": _int(
            historical_seed_native_oracle_metric_candidates_summary.get("best_native_metric_candidate_count")
        ),
        "historical_seed_native_oracle_metric_candidates_blocked_count": _int(
            historical_seed_native_oracle_metric_candidates_summary.get("blocked_candidate_input_count")
        ),
        "historical_seed_native_oracle_metric_candidates_first_target_id": _text(
            historical_seed_native_oracle_metric_candidates_summary.get("first_open_target_id")
        ),
        "historical_seed_native_oracle_metric_candidates_first_next_action": _text(
            historical_seed_native_oracle_metric_candidates_summary.get("first_next_action")
        ),
        "historical_seed_calibration_candidate_ledgers_status": _text(
            historical_seed_calibration_candidate_ledgers_summary.get("calibration_candidate_status")
        ),
        "historical_seed_calibration_candidate_ledgers_seed_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("seed_row_count")
        ),
        "historical_seed_calibration_candidate_ledgers_ledger_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("ledger_count")
        ),
        "historical_seed_calibration_candidate_ledgers_candidate_model_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("candidate_model_count")
        ),
        "historical_seed_calibration_candidate_ledgers_top5_ready_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("top5_candidate_pool_ready_count")
        ),
        "historical_seed_calibration_candidate_ledgers_selected_prediction_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("selected_prediction_candidate_count")
        ),
        "historical_seed_calibration_candidate_ledgers_selected_rank_candidate_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("selected_model_rank_candidate_count")
        ),
        "historical_seed_calibration_candidate_ledgers_native_metric_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("native_oracle_metric_available_count")
        ),
        "historical_seed_calibration_candidate_ledgers_internal_score_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("internal_score_available_count")
        ),
        "historical_seed_calibration_candidate_ledgers_ready_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("ready_for_calibration_fill_count")
        ),
        "historical_seed_calibration_candidate_ledgers_operator_review_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("operator_review_required_count")
        ),
        "historical_seed_calibration_candidate_ledgers_blocked_selected_prediction_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("blocked_selected_prediction_count")
        ),
        "historical_seed_calibration_candidate_ledgers_open_field_count": _int(
            historical_seed_calibration_candidate_ledgers_summary.get("open_calibration_field_count")
        ),
        "historical_seed_calibration_candidate_ledgers_first_target_id": _text(
            historical_seed_calibration_candidate_ledgers_summary.get("first_open_target_id")
        ),
        "historical_seed_calibration_candidate_ledgers_first_next_action": _text(
            historical_seed_calibration_candidate_ledgers_summary.get("first_next_action")
        ),
        "historical_seed_calibration_field_candidates_status": _text(
            historical_seed_calibration_field_candidates_summary.get("calibration_field_candidate_status")
        ),
        "historical_seed_calibration_field_candidates_seed_count": _int(
            historical_seed_calibration_field_candidates_summary.get("seed_row_count")
        ),
        "historical_seed_calibration_field_candidates_field_count": _int(
            historical_seed_calibration_field_candidates_summary.get("field_candidate_count")
        ),
        "historical_seed_calibration_field_candidates_proposed_count": _int(
            historical_seed_calibration_field_candidates_summary.get("proposed_field_count")
        ),
        "historical_seed_calibration_field_candidates_matching_count": _int(
            historical_seed_calibration_field_candidates_summary.get("already_matching_field_count")
        ),
        "historical_seed_calibration_field_candidates_conflict_count": _int(
            historical_seed_calibration_field_candidates_summary.get("conflict_field_count")
        ),
        "historical_seed_calibration_field_candidates_blocked_field_count": _int(
            historical_seed_calibration_field_candidates_summary.get("blocked_field_count")
        ),
        "historical_seed_calibration_field_candidates_ready_count": _int(
            historical_seed_calibration_field_candidates_summary.get("ready_to_apply_row_count")
        ),
        "historical_seed_calibration_field_candidates_blocked_row_count": _int(
            historical_seed_calibration_field_candidates_summary.get("blocked_row_count")
        ),
        "historical_seed_calibration_field_candidates_first_target_id": _text(
            historical_seed_calibration_field_candidates_summary.get("first_open_target_id")
        ),
        "historical_seed_calibration_field_candidates_first_next_action": _text(
            historical_seed_calibration_field_candidates_summary.get("first_next_action")
        ),
        "historical_seed_clearance_fill_candidate_packet_status": _text(
            historical_seed_clearance_fill_candidate_packet_summary.get("clearance_fill_candidate_status")
        ),
        "historical_seed_clearance_fill_candidate_packet_seed_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("seed_row_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_field_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("field_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_proposed_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("proposed_field_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_matching_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("already_matching_field_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_operator_required_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("operator_required_field_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_blocked_field_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("blocked_field_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_conflict_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("conflict_field_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_calibration_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("calibration_candidate_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_ablation_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("ablation_candidate_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_no_leak_manual_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("no_leak_manual_field_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_partial_row_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("partial_candidate_row_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_full_ready_row_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("full_clearance_ready_row_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_blocked_row_count": _int(
            historical_seed_clearance_fill_candidate_packet_summary.get("blocked_row_count")
        ),
        "historical_seed_clearance_fill_candidate_packet_first_target_id": _text(
            historical_seed_clearance_fill_candidate_packet_summary.get("first_open_target_id")
        ),
        "historical_seed_clearance_fill_candidate_packet_first_next_action": _text(
            historical_seed_clearance_fill_candidate_packet_summary.get("first_next_action")
        ),
        "historical_seed_clearance_execution_board_status": _text(
            historical_seed_clearance_execution_board_summary.get("execution_board_status")
        ),
        "historical_seed_clearance_execution_board_seed_count": _int(
            historical_seed_clearance_execution_board_summary.get("seed_row_count")
        ),
        "historical_seed_clearance_execution_board_no_leak_only_count": _int(
            historical_seed_clearance_execution_board_summary.get("operator_no_leak_only_row_count")
        ),
        "historical_seed_clearance_execution_board_ablation_repair_count": _int(
            historical_seed_clearance_execution_board_summary.get("ablation_repair_required_row_count")
        ),
        "historical_seed_clearance_execution_board_operator_no_leak_field_count": _int(
            historical_seed_clearance_execution_board_summary.get("operator_no_leak_field_count")
        ),
        "historical_seed_clearance_execution_board_proposed_field_count": _int(
            historical_seed_clearance_execution_board_summary.get("proposed_field_count")
        ),
        "historical_seed_clearance_execution_board_calibration_count": _int(
            historical_seed_clearance_execution_board_summary.get("calibration_candidate_count")
        ),
        "historical_seed_clearance_execution_board_ablation_count": _int(
            historical_seed_clearance_execution_board_summary.get("ablation_candidate_count")
        ),
        "historical_seed_clearance_execution_board_blocked_ablation_count": _int(
            historical_seed_clearance_execution_board_summary.get("blocked_ablation_field_count")
        ),
        "historical_seed_clearance_execution_board_first_target_id": _text(
            historical_seed_clearance_execution_board_summary.get("first_execution_target_id")
        ),
        "historical_seed_clearance_execution_board_first_status": _text(
            historical_seed_clearance_execution_board_summary.get("first_execution_status")
        ),
        "historical_seed_clearance_execution_board_first_next_action": _text(
            historical_seed_clearance_execution_board_summary.get("first_execution_next_action")
        ),
        "historical_seed_clearance_execution_board_first_folder": _text(
            historical_seed_clearance_execution_board_summary.get("first_execution_folder")
        ),
        "historical_seed_first_clearance_operator_kit_status": _text(
            historical_seed_first_clearance_operator_kit_summary.get("first_clearance_kit_status")
        ),
        "historical_seed_first_clearance_operator_kit_target_id": _text(
            historical_seed_first_clearance_operator_kit_summary.get("target_id")
        ),
        "historical_seed_first_clearance_operator_kit_benchmark_id": _text(
            historical_seed_first_clearance_operator_kit_summary.get("benchmark_id")
        ),
        "historical_seed_first_clearance_operator_kit_no_leak_count": _int(
            historical_seed_first_clearance_operator_kit_summary.get("no_leak_field_count")
        ),
        "historical_seed_first_clearance_operator_kit_ready_count": _int(
            historical_seed_first_clearance_operator_kit_summary.get("ready_candidate_field_count")
        ),
        "historical_seed_first_clearance_operator_kit_total_count": _int(
            historical_seed_first_clearance_operator_kit_summary.get("total_field_count")
        ),
        "historical_seed_first_clearance_operator_kit_calibration_count": _int(
            historical_seed_first_clearance_operator_kit_summary.get("calibration_candidate_count")
        ),
        "historical_seed_first_clearance_operator_kit_ablation_count": _int(
            historical_seed_first_clearance_operator_kit_summary.get("ablation_candidate_count")
        ),
        "historical_seed_first_clearance_operator_kit_weak_count": _int(
            historical_seed_first_clearance_operator_kit_summary.get("weak_hint_count")
        ),
        "historical_seed_first_clearance_operator_kit_preview_status": _text(
            historical_seed_first_clearance_operator_kit_summary.get("promotion_preview_status")
        ),
        "historical_seed_first_clearance_operator_kit_folder": _text(
            historical_seed_first_clearance_operator_kit_summary.get("kit_folder")
        ),
        "historical_seed_first_clearance_operator_kit_intake_csv": _text(
            historical_seed_first_clearance_operator_kit_summary.get("no_leak_operator_intake_csv")
        ),
        "historical_seed_first_clearance_operator_kit_next_action": _text(
            historical_seed_first_clearance_operator_kit_summary.get("next_action")
        ),
        "historical_seed_first_clearance_no_leak_gate_status": _text(
            historical_seed_first_clearance_no_leak_gate_summary.get("first_clearance_no_leak_gate_status")
        ),
        "historical_seed_first_clearance_no_leak_gate_target_id": _text(
            historical_seed_first_clearance_no_leak_gate_summary.get("target_id")
        ),
        "historical_seed_first_clearance_no_leak_gate_benchmark_id": _text(
            historical_seed_first_clearance_no_leak_gate_summary.get("benchmark_id")
        ),
        "historical_seed_first_clearance_no_leak_gate_field_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("field_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_ready_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("ready_field_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_blocked_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("blocked_field_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_value_present_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("operator_value_present_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_value_missing_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("operator_value_missing_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_clearance_present_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("operator_clearance_present_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_clearance_missing_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("operator_clearance_missing_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_policy_pass_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("policy_pass_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_policy_blocked_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("policy_blocked_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_weak_count": _int(
            historical_seed_first_clearance_no_leak_gate_summary.get("weak_hint_count")
        ),
        "historical_seed_first_clearance_no_leak_gate_first_blocked_field": _text(
            historical_seed_first_clearance_no_leak_gate_summary.get("first_blocked_field")
        ),
        "historical_seed_first_clearance_no_leak_gate_first_blocker": _text(
            historical_seed_first_clearance_no_leak_gate_summary.get("first_blocker")
        ),
        "historical_seed_first_clearance_no_leak_gate_intake_csv": _text(
            historical_seed_first_clearance_no_leak_gate_summary.get("no_leak_operator_intake_csv")
        ),
        "historical_seed_first_clearance_no_leak_gate_next_action": _text(
            historical_seed_first_clearance_no_leak_gate_summary.get("next_action")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_status": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get(
                "first_clearance_no_leak_evidence_packet_status"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_target_id": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("target_id")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_benchmark_id": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("benchmark_id")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_field_count": _int(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_ready_count": _int(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("ready_field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_open_count": _int(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("open_field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_stub_count": _int(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("evidence_stub_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_weak_count": _int(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("weak_hint_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_first_open_field": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("first_open_field")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_first_open_kind": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("first_open_kind")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_folder": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("packet_folder")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_template_csv": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get(
                "operator_evidence_template_csv"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_action_md": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("action_md")
        ),
        "historical_seed_first_clearance_no_leak_evidence_packet_next_action": _text(
            historical_seed_first_clearance_no_leak_evidence_packet_summary.get("next_action")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_status": _text(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                "first_clearance_no_leak_evidence_review_gate_status"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_target_id": _text(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("target_id")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_benchmark_id": _text(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("benchmark_id")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_field_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_ready_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("ready_field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_blocked_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("blocked_field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_template_value_missing_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                "template_operator_value_missing_count"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_template_clearance_missing_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                "template_operator_clearance_missing_count"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_template_operator_missing_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                "template_operator_id_missing_count"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_stub_present_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("stub_present_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_stub_evidence_missing_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                "stub_evidence_missing_count"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_policy_pass_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("policy_pass_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_policy_blocked_count": _int(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("policy_blocked_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_first_blocked_field": _text(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("first_blocked_field")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_first_blocker": _text(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("first_blocker")
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_template_csv": _text(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get(
                "operator_evidence_template_csv"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_review_gate_next_action": _text(
            historical_seed_first_clearance_no_leak_evidence_review_gate_summary.get("next_action")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_status": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get(
                "first_clearance_no_leak_evidence_sync_plan_status"
            )
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_mode": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("sync_mode")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_review_status": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("review_gate_status")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_target_id": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("target_id")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_benchmark_id": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("benchmark_id")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_action_count": _int(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("action_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_ready_count": _int(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("ready_action_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_blocked_count": _int(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("blocked_action_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_applied_count": _int(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("applied_action_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_review_ready_count": _int(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("review_ready_field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_review_blocked_count": _int(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("review_blocked_field_count")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_first_blocked_field": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("first_blocked_field")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_first_blocker": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("first_blocker")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_destination_intake_csv": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("destination_intake_csv")
        ),
        "historical_seed_first_clearance_no_leak_evidence_sync_plan_next_action": _text(
            historical_seed_first_clearance_no_leak_evidence_sync_plan_summary.get("next_action")
        ),
        "historical_seed_first_clearance_closure_board_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("first_clearance_closure_board_status")
        ),
        "historical_seed_first_clearance_closure_board_target_id": _text(
            historical_seed_first_clearance_closure_board_summary.get("target_id")
        ),
        "historical_seed_first_clearance_closure_board_benchmark_id": _text(
            historical_seed_first_clearance_closure_board_summary.get("benchmark_id")
        ),
        "historical_seed_first_clearance_closure_board_stage_count": _int(
            historical_seed_first_clearance_closure_board_summary.get("stage_count")
        ),
        "historical_seed_first_clearance_closure_board_ready_count": _int(
            historical_seed_first_clearance_closure_board_summary.get("ready_stage_count")
        ),
        "historical_seed_first_clearance_closure_board_blocked_count": _int(
            historical_seed_first_clearance_closure_board_summary.get("blocked_stage_count")
        ),
        "historical_seed_first_clearance_closure_board_first_stage": _text(
            historical_seed_first_clearance_closure_board_summary.get("first_blocked_stage_id")
        ),
        "historical_seed_first_clearance_closure_board_first_stage_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("first_blocked_stage_status")
        ),
        "historical_seed_first_clearance_closure_board_first_blocker": _text(
            historical_seed_first_clearance_closure_board_summary.get("first_blocker")
        ),
        "historical_seed_first_clearance_closure_board_operator_kit_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("operator_kit_status")
        ),
        "historical_seed_first_clearance_closure_board_no_leak_gate_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("no_leak_gate_status")
        ),
        "historical_seed_first_clearance_closure_board_evidence_packet_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("evidence_packet_status")
        ),
        "historical_seed_first_clearance_closure_board_evidence_review_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("evidence_review_gate_status")
        ),
        "historical_seed_first_clearance_closure_board_evidence_sync_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("evidence_sync_plan_status")
        ),
        "historical_seed_first_clearance_closure_board_promotion_preview_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("promotion_preview_status")
        ),
        "historical_seed_first_clearance_closure_board_identity_sync_status": _text(
            historical_seed_first_clearance_closure_board_summary.get("identity_sync_status")
        ),
        "historical_seed_first_clearance_closure_board_next_action": _text(
            historical_seed_first_clearance_closure_board_summary.get("next_action")
        ),
        "historical_seed_clearance_to_identity_intake_sync_status": _text(
            historical_seed_clearance_to_identity_intake_sync_summary.get("seed_to_identity_sync_status")
        ),
        "historical_seed_clearance_to_identity_intake_sync_apply_mode": _text(
            historical_seed_clearance_to_identity_intake_sync_summary.get("apply_mode")
        ),
        "historical_seed_clearance_to_identity_intake_sync_intake_row_count": _int(
            historical_seed_clearance_to_identity_intake_sync_summary.get("intake_row_count")
        ),
        "historical_seed_clearance_to_identity_intake_sync_seed_row_count": _int(
            historical_seed_clearance_to_identity_intake_sync_summary.get("seed_manifest_row_count")
        ),
        "historical_seed_clearance_to_identity_intake_sync_eligible_count": _int(
            historical_seed_clearance_to_identity_intake_sync_summary.get("eligible_seed_row_count")
        ),
        "historical_seed_clearance_to_identity_intake_sync_ready_count": _int(
            historical_seed_clearance_to_identity_intake_sync_summary.get("ready_to_sync_count")
        ),
        "historical_seed_clearance_to_identity_intake_sync_waiting_count": _int(
            historical_seed_clearance_to_identity_intake_sync_summary.get("waiting_intake_count")
        ),
        "historical_seed_clearance_to_identity_intake_sync_blocked_count": _int(
            historical_seed_clearance_to_identity_intake_sync_summary.get("blocked_count")
        ),
        "historical_seed_clearance_to_identity_intake_sync_applied_count": _int(
            historical_seed_clearance_to_identity_intake_sync_summary.get("applied_count")
        ),
        "historical_seed_clearance_to_identity_intake_sync_first_next_action": _text(
            historical_seed_clearance_to_identity_intake_sync_summary.get("first_next_action")
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
        f"- protein object library completion audit: `{summary['protein_object_library_completion_status'] or '-'}` proteins pass/blocked/total `{summary['protein_object_library_completion_protein_pass_count']}/{summary['protein_object_library_completion_protein_blocked_count']}/{summary['protein_object_library_completion_protein_count']}` objects pass/blocked/total `{summary['protein_object_library_completion_object_pass_count']}/{summary['protein_object_library_completion_object_blocked_count']}/{summary['protein_object_library_completion_object_count']}` assets model/projection/viewer `{summary['protein_object_library_completion_model_count']}/{summary['protein_object_library_completion_projection_count']}/{summary['protein_object_library_completion_viewer_count']}` manifests object/protein `{summary['protein_object_library_completion_object_manifest_count']}/{summary['protein_object_library_completion_protein_manifest_count']}`",
        f"- protein object library navigation catalog: `{summary['protein_object_library_navigation_status'] or '-'}` proteins pass/blocked/total `{summary['protein_object_library_navigation_protein_pass_count']}/{summary['protein_object_library_navigation_protein_blocked_count']}/{summary['protein_object_library_navigation_protein_count']}` objects pass/blocked/total `{summary['protein_object_library_navigation_object_pass_count']}/{summary['protein_object_library_navigation_object_blocked_count']}/{summary['protein_object_library_navigation_object_count']}` readme/manifest links `{summary['protein_object_library_navigation_readme_link_count']}/{summary['protein_object_library_navigation_manifest_link_count']}` largest `{summary['protein_object_library_navigation_largest_protein_key'] or '-'}` `{summary['protein_object_library_navigation_largest_object_count']}` html `{summary['protein_object_library_navigation_html'] or '-'}`",
        f"- raw-ranked model quarantine: `{summary['raw_ranked_model_quarantine_status'] or '-'}` targets/models/top5 `{summary['raw_ranked_model_quarantine_target_count']}/{summary['raw_ranked_model_quarantine_model_count']}/{summary['raw_ranked_model_quarantine_top5_count']}` quarantined/linked/author-present `{summary['raw_ranked_model_quarantine_quarantined_count']}/{summary['raw_ranked_model_quarantine_linked_count']}/{summary['raw_ranked_model_quarantine_author_present_count']}` atoms `{summary['raw_ranked_model_quarantine_atom_count']}`",
        f"- benchmark rows ready/total: `{summary['benchmark_rows_ready_count']}/{summary['benchmark_rows_total']}`",
        f"- win-tier goal scorecard: `{summary['win_tier_goal_scorecard_status'] or '-'}` pass/partial/blocked `{summary['win_tier_goal_scorecard_pass_count']}/{summary['win_tier_goal_scorecard_partial_count']}/{summary['win_tier_goal_scorecard_blocked_count']}` first blocked `{summary['win_tier_goal_scorecard_first_blocked_gate'] or '-'}`",
        f"- win-tier metric surface contract: `{summary['win_tier_metric_surface_contract_status'] or '-'}` metrics covered/required `{summary['win_tier_metric_surface_contract_covered_metric_count']}/{summary['win_tier_metric_surface_contract_required_metric_count']}` slots ready/blocked/total `{summary['win_tier_metric_surface_contract_ready_slot_count']}/{summary['win_tier_metric_surface_contract_blocked_slot_count']}/{summary['win_tier_metric_surface_contract_slot_count']}` rows ready/blocked/total `{summary['win_tier_metric_surface_contract_ready_metric_row_count']}/{summary['win_tier_metric_surface_contract_blocked_metric_row_count']}/{summary['win_tier_metric_surface_contract_metric_row_count']}` ligand slots `{summary['win_tier_metric_surface_contract_ligand_slot_count']}` official archive `{summary['win_tier_metric_surface_contract_official_archive_policy'] or '-'}` first `{summary['win_tier_metric_surface_contract_first_blocked_benchmark'] or '-'}` `{summary['win_tier_metric_surface_contract_first_blocked_metric'] or '-'}`",
        f"- win-tier critical path board: `{summary['win_tier_critical_path_status'] or '-'}` stages ready/blocked/total `{summary['win_tier_critical_path_stage_ready_count']}/{summary['win_tier_critical_path_stage_blocked_count']}/{summary['win_tier_critical_path_stage_count']}` 3D objects `{summary['win_tier_critical_path_3d_ready_count']}/{summary['win_tier_critical_path_3d_count']}` external targets `{summary['win_tier_critical_path_external_ready_target_count']}/{summary['win_tier_critical_path_external_target_count']}` model1/top5 `{summary['win_tier_critical_path_external_model1_count']}/{summary['win_tier_critical_path_external_top5_count']}` strict slots `{summary['win_tier_critical_path_strict_ready_slot_count']}/{summary['win_tier_critical_path_strict_slot_count']}` missing evidence/operator-open `{summary['win_tier_critical_path_missing_evidence_file_count']}/{summary['win_tier_critical_path_operator_open_value_count']}` first `{summary['win_tier_critical_path_first_blocked_stage'] or '-'}` `{summary['win_tier_critical_path_first_blocker'] or '-'}`",
        f"- organic ligand slot candidates: `{summary['organic_ligand_slot_candidate_status'] or '-'}` review/proof/total `{summary['organic_ligand_slot_candidate_review_ready_count']}/{summary['organic_ligand_slot_candidate_proof_eligible_count']}/{summary['organic_ligand_slot_candidate_count']}` ChEMBL/BindingDB `{summary['organic_ligand_slot_candidate_chembl_count']}/{summary['organic_ligand_slot_candidate_bindingdb_count']}` strict-blocked `{summary['organic_ligand_slot_candidate_strict_blocked_count']}` files reference/prediction/ligand/template `{summary['organic_ligand_slot_candidate_reference_present_count']}/{summary['organic_ligand_slot_candidate_prediction_present_count']}/{summary['organic_ligand_slot_candidate_ligand_mol2_present_count']}/{summary['organic_ligand_slot_candidate_ligand_template_present_count']}` metrics LDDT-PLI/BiSyRMSD `{summary['organic_ligand_slot_candidate_lddt_pli_required_count']}/{summary['organic_ligand_slot_candidate_bisyrmsd_required_count']}` affinity labels `{summary['organic_ligand_slot_candidate_affinity_label_candidate_count']}` metric ligand slots `{summary['organic_ligand_slot_candidate_metric_contract_ligand_slot_gap_count']}` first `{summary['organic_ligand_slot_candidate_first_target_id'] or '-'}` `{summary['organic_ligand_slot_candidate_first_ligand_id'] or '-'}`",
        f"- organic ligand strict-blind promotion board: `{summary['organic_ligand_slot_promotion_action_board_status'] or '-'}` candidates/actions/open `{summary['organic_ligand_slot_promotion_candidate_count']}/{summary['organic_ligand_slot_promotion_action_count']}/{summary['organic_ligand_slot_promotion_open_action_count']}` reference-preflight `{summary['organic_ligand_slot_promotion_reference_preflight_pass_count']}` operator/numeric/affinity-source `{summary['organic_ligand_slot_promotion_operator_evidence_required_count']}/{summary['organic_ligand_slot_promotion_numeric_value_required_count']}/{summary['organic_ligand_slot_promotion_affinity_source_required_count']}` metric/slot `{summary['organic_ligand_slot_promotion_metric_input_required_count']}/{summary['organic_ligand_slot_promotion_slot_mapping_required_count']}` proof-ready `{summary['organic_ligand_slot_promotion_proof_ready_candidate_count']}` first `{summary['organic_ligand_slot_promotion_first_open_action_id'] or '-'}` `{summary['organic_ligand_slot_promotion_first_open_target_id'] or '-'}` `{summary['organic_ligand_slot_promotion_first_open_action_type'] or '-'}`",
        f"- active competition scope: `{summary['active_competition_scope'] or '-'}` CASP17 `{summary['active_scope_casp17_continuation_status'] or '-'}` priority `{summary['active_scope_casp17_priority_status'] or '-'}` CAPRI `{summary['active_scope_capri_round65_participation_status'] or '-'}` reason `{summary['active_scope_capri_round65_hold_reason'] or '-'}` next `{summary['active_scope_next_action'] or '-'}`",
        f"- organizer notice intake: `{summary['organizer_notice_status'] or '-'}` source `{summary['organizer_notice_source_ref'] or '-'}` R2345 first/second `{summary['organizer_notice_r2345_first_request_status'] or '-'}`/`{summary['organizer_notice_r2345_replacement_request_status'] or '-'}` sequence gate `{summary['organizer_notice_r2345_sequence_validation_gate'] or '-'}` MassiveFold scope `{summary['organizer_notice_massivefold_generation_scope'] or '-'}` first RNA/hybrid `{summary['organizer_notice_massivefold_first_rna_hybrid_set_target_id'] or '-'}` links RNA-hybrid/protein-total `{summary['organizer_notice_massivefold_rna_hybrid_link_count']}/{summary['organizer_notice_massivefold_protein_complex_link_count']}/{summary['organizer_notice_massivefold_link_count']}` R2341/R2345 `{summary['organizer_notice_massivefold_r2341_link_present'] or '-'}`/`{summary['organizer_notice_massivefold_r2345_link_present'] or '-'}` policy `{summary['organizer_notice_massivefold_internal_prediction_policy'] or '-'}` download `{summary['organizer_notice_large_download_policy'] or '-'}`",
        f"- MassiveFold external pool intake: `{summary['massivefold_external_pool_intake_status'] or '-'}` pools ready/blocked/total `{summary['massivefold_external_pool_ready_count']}/{summary['massivefold_external_pool_blocked_count']}/{summary['massivefold_external_pool_count']}` RNA-hybrid/protein-complex `{summary['massivefold_external_pool_rna_hybrid_count']}/{summary['massivefold_external_pool_protein_complex_count']}` proof/internal-blocked `{summary['massivefold_external_pool_proof_eligible_count']}/{summary['massivefold_external_pool_internal_blocked_count']}` R2341/R2345 `{summary['massivefold_external_pool_r2341_present'] or '-'}`/`{summary['massivefold_external_pool_r2345_present'] or '-'}` largest `{summary['massivefold_external_pool_largest_model_set_id'] or '-'}` bytes `{summary['massivefold_external_pool_total_size_bytes']}` download `{summary['massivefold_external_pool_download_policy'] or '-'}`",
        f"- RNA/hybrid MassiveFold priority queue: `{summary['rna_hybrid_massivefold_priority_queue_status'] or '-'}` rows ready/blocked/total `{summary['rna_hybrid_massivefold_priority_queue_ready_count']}/{summary['rna_hybrid_massivefold_priority_queue_blocked_count']}/{summary['rna_hybrid_massivefold_priority_queue_count']}` first `{summary['rna_hybrid_massivefold_priority_queue_first_target_id'] or '-'}` `{summary['rna_hybrid_massivefold_priority_queue_first_reason'] or '-'}` R2341/R2345 rank `{summary['rna_hybrid_massivefold_priority_queue_r2341_rank']}/{summary['rna_hybrid_massivefold_priority_queue_r2345_rank']}` R2345 invalid/active `{summary['rna_hybrid_massivefold_priority_queue_r2345_invalid_status'] or '-'}`/`{summary['rna_hybrid_massivefold_priority_queue_r2345_active_status'] or '-'}` guard `{summary['rna_hybrid_massivefold_priority_queue_r2345_sequence_guard'] or '-'}` proof/internal-blocked `{summary['rna_hybrid_massivefold_priority_queue_proof_eligible_count']}/{summary['rna_hybrid_massivefold_priority_queue_internal_blocked_count']}` bytes `{summary['rna_hybrid_massivefold_priority_queue_total_size_bytes']}` download `{summary['rna_hybrid_massivefold_priority_queue_download_policy'] or '-'}`",
        f"- Protein/complex MassiveFold priority queue: `{summary['protein_complex_massivefold_priority_queue_status'] or '-'}` rows ready/blocked/total `{summary['protein_complex_massivefold_priority_queue_ready_count']}/{summary['protein_complex_massivefold_priority_queue_blocked_count']}/{summary['protein_complex_massivefold_priority_queue_count']}` first `{summary['protein_complex_massivefold_priority_queue_first_target_id'] or '-'}` `{summary['protein_complex_massivefold_priority_queue_first_model_set_id'] or '-'}` reason `{summary['protein_complex_massivefold_priority_queue_first_reason'] or '-'}` largest `{summary['protein_complex_massivefold_priority_queue_largest_model_set_id'] or '-'}` bytes `{summary['protein_complex_massivefold_priority_queue_largest_size_bytes']}` proof/internal-blocked `{summary['protein_complex_massivefold_priority_queue_proof_eligible_count']}/{summary['protein_complex_massivefold_priority_queue_internal_blocked_count']}` total bytes `{summary['protein_complex_massivefold_priority_queue_total_size_bytes']}` download `{summary['protein_complex_massivefold_priority_queue_download_policy'] or '-'}`",
        f"- MassiveFold acquisition verification: `{summary['massivefold_acquisition_verification_status'] or '-'}` pools verified/open/total `{summary['massivefold_acquisition_verification_verified_count']}/{summary['massivefold_acquisition_verification_open_count']}/{summary['massivefold_acquisition_verification_pool_count']}` tarball/hash/listing `{summary['massivefold_acquisition_verification_tarball_present_count']}/{summary['massivefold_acquisition_verification_sha256_record_count']}/{summary['massivefold_acquisition_verification_listing_present_count']}` sha-verified/listing-entries `{summary['massivefold_acquisition_verification_sha256_verified_count']}/{summary['massivefold_acquisition_verification_listing_entry_count']}` first/open `{summary['massivefold_acquisition_verification_first_priority_target_id'] or '-'}`/`{summary['massivefold_acquisition_verification_first_open_target_id'] or '-'}` `{summary['massivefold_acquisition_verification_first_open_status'] or '-'}` R2341/R2345 `{summary['massivefold_acquisition_verification_r2341_status'] or '-'}`/`{summary['massivefold_acquisition_verification_r2345_status'] or '-'}`",
        f"- Protein/complex MassiveFold acquisition verification: `{summary['protein_complex_massivefold_acquisition_verification_status'] or '-'}` pools verified/open/total `{summary['protein_complex_massivefold_acquisition_verification_verified_count']}/{summary['protein_complex_massivefold_acquisition_verification_open_count']}/{summary['protein_complex_massivefold_acquisition_verification_pool_count']}` tarball/hash/listing `{summary['protein_complex_massivefold_acquisition_verification_tarball_present_count']}/{summary['protein_complex_massivefold_acquisition_verification_sha256_record_count']}/{summary['protein_complex_massivefold_acquisition_verification_listing_present_count']}` sha-verified/listing-entries `{summary['protein_complex_massivefold_acquisition_verification_sha256_verified_count']}/{summary['protein_complex_massivefold_acquisition_verification_listing_entry_count']}` first/open `{summary['protein_complex_massivefold_acquisition_verification_first_priority_target_id'] or '-'}`/`{summary['protein_complex_massivefold_acquisition_verification_first_open_target_id'] or '-'}` `{summary['protein_complex_massivefold_acquisition_verification_first_open_status'] or '-'}` download `{summary['protein_complex_massivefold_acquisition_verification_download_policy'] or '-'}`",
        f"- MassiveFold model pool index: `{summary['massivefold_model_pool_index_status'] or '-'}` target `{summary['massivefold_model_pool_index_target_id'] or '-'}` models/protocols `{summary['massivefold_model_pool_index_model_count']}/{summary['massivefold_model_pool_index_protocol_count']}` selected/extracted/pending `{summary['massivefold_model_pool_index_selected_count']}/{summary['massivefold_model_pool_index_extracted_count']}/{summary['massivefold_model_pool_index_pending_count']}` basic/woTemplates/woUnpaired/woPaired `{summary['massivefold_model_pool_index_basic_count']}/{summary['massivefold_model_pool_index_wo_templates_count']}/{summary['massivefold_model_pool_index_wo_unpaired_count']}/{summary['massivefold_model_pool_index_wo_paired_count']}` first `{summary['massivefold_model_pool_index_first_selected_model'] or '-'}` `{summary['massivefold_model_pool_index_first_selected_protocol'] or '-'}` manifest `{summary['massivefold_model_pool_index_extraction_manifest'] or '-'}`",
        f"- MassiveFold representative viewers: `{summary['massivefold_representative_viewer_status'] or '-'}` target `{summary['massivefold_representative_viewer_target_id'] or '-'}` selected/ready/blocked `{summary['massivefold_representative_viewer_selected_count']}/{summary['massivefold_representative_viewer_ready_count']}/{summary['massivefold_representative_viewer_blocked_count']}` coordinate/model/projection `{summary['massivefold_representative_viewer_coordinate_count']}/{summary['massivefold_representative_viewer_model_cif_count']}/{summary['massivefold_representative_viewer_projection_count']}` atoms/displayed/residues `{summary['massivefold_representative_viewer_atom_count']}/{summary['massivefold_representative_viewer_display_atom_count']}/{summary['massivefold_representative_viewer_residue_count']}` protocols `{summary['massivefold_representative_viewer_protocol_count']}` first `{summary['massivefold_representative_viewer_first_html'] or '-'}` gallery `{summary['massivefold_representative_viewer_gallery_html'] or '-'}`",
        f"- MassiveFold representative rerank: `{summary['massivefold_representative_rerank_status'] or '-'}` target `{summary['massivefold_representative_rerank_target_id'] or '-'}` candidates/model1/top5 `{summary['massivefold_representative_rerank_candidate_count']}/{summary['massivefold_representative_rerank_model1_count']}/{summary['massivefold_representative_rerank_top5_count']}` top5 protocols `{summary['massivefold_representative_rerank_top5_protocol_count']}` review/proof-eligible `{summary['massivefold_representative_rerank_review_candidate_count']}/{summary['massivefold_representative_rerank_proof_eligible_count']}` confidence min/max `{summary['massivefold_representative_rerank_confidence_min'] or '-'}`/`{summary['massivefold_representative_rerank_confidence_max'] or '-'}` model1 `{summary['massivefold_representative_rerank_model1_file'] or '-'}` `{summary['massivefold_representative_rerank_model1_protocol'] or '-'}` score `{summary['massivefold_representative_rerank_model1_score'] or '-'}` top5 `{summary['massivefold_representative_rerank_top5_manifest'] or '-'}`",
        f"- MassiveFold RNA model-selection coverage: `{summary['massivefold_rna_model_selection_coverage_status'] or '-'}` targets ready/partial/total `{summary['massivefold_rna_model_selection_coverage_ready_target_count']}/{summary['massivefold_rna_model_selection_coverage_partial_target_count']}/{summary['massivefold_rna_model_selection_coverage_target_count']}` acquisition/index/viewer/rerank `{summary['massivefold_rna_model_selection_coverage_verified_acquisition_count']}/{summary['massivefold_rna_model_selection_coverage_representative_extracted_target_count']}/{summary['massivefold_rna_model_selection_coverage_viewer_ready_target_count']}/{summary['massivefold_rna_model_selection_coverage_rerank_ready_target_count']}` models selected/extracted/viewer `{summary['massivefold_rna_model_selection_coverage_selected_model_count']}/{summary['massivefold_rna_model_selection_coverage_extracted_model_count']}/{summary['massivefold_rna_model_selection_coverage_viewer_ready_model_count']}` model1/top5 `{summary['massivefold_rna_model_selection_coverage_model1_candidate_count']}/{summary['massivefold_rna_model_selection_coverage_top5_candidate_count']}` first partial `{summary['massivefold_rna_model_selection_coverage_first_partial_target_id'] or '-'}`",
        f"- Protein/complex MassiveFold model-selection coverage: `{summary['protein_complex_massivefold_model_selection_coverage_status'] or '-'}` targets ready/partial/total `{summary['protein_complex_massivefold_model_selection_coverage_ready_target_count']}/{summary['protein_complex_massivefold_model_selection_coverage_partial_target_count']}/{summary['protein_complex_massivefold_model_selection_coverage_target_count']}` acquisition/index/viewer/rerank `{summary['protein_complex_massivefold_model_selection_coverage_verified_acquisition_count']}/{summary['protein_complex_massivefold_model_selection_coverage_representative_extracted_target_count']}/{summary['protein_complex_massivefold_model_selection_coverage_viewer_ready_target_count']}/{summary['protein_complex_massivefold_model_selection_coverage_rerank_ready_target_count']}` models selected/extracted/viewer `{summary['protein_complex_massivefold_model_selection_coverage_selected_model_count']}/{summary['protein_complex_massivefold_model_selection_coverage_extracted_model_count']}/{summary['protein_complex_massivefold_model_selection_coverage_viewer_ready_model_count']}` model1/top5 `{summary['protein_complex_massivefold_model_selection_coverage_model1_candidate_count']}/{summary['protein_complex_massivefold_model_selection_coverage_top5_candidate_count']}` first partial `{summary['protein_complex_massivefold_model_selection_coverage_first_partial_target_id'] or '-'}`",
        (
            f"- CAPRI Round 65 readiness context: `{summary['active_scope_capri_round65_participation_status'] or '-'}` not active blocker; preserved targets active/closed/total `{summary['capri_round65_active_target_count']}/{summary['capri_round65_closed_target_count']}/{summary['capri_round65_target_count']}` artifact policy `{summary['active_scope_capri_round65_artifact_policy'] or '-'}`"
            if summary["active_scope_capri_round65_participation_status"].startswith("deferred")
            else f"- CAPRI Round 65 readiness: `{summary['capri_round65_readiness_status'] or '-'}` round `{summary['capri_round65_round_status'] or '-'}` registration-end `{summary['capri_round65_registration_end'] or '-'}` days `{summary['capri_round65_registration_days_remaining']}` registration fields `{summary['capri_round65_registration_ready_field_count']}/{summary['capri_round65_registration_required_field_count']}` active/closed/total `{summary['capri_round65_active_target_count']}/{summary['capri_round65_closed_target_count']}/{summary['capri_round65_target_count']}` scorer/predictor `{summary['capri_round65_scorer_priority_target_count']}/{summary['capri_round65_predictor_priority_target_count']}` blocked/preflight `{summary['capri_round65_blocked_target_count']}/{summary['capri_round65_readiness_format_preflight_target_count']}` first `{summary['capri_round65_first_open_target_id'] or '-'}` `{summary['capri_round65_first_next_action'] or '-'}`"
        ),
        (
            f"- CAPRI Round 65 format preflight context: `{summary['active_scope_capri_round65_participation_status'] or '-'}` skipped while CAPRI is PI-required hold; local-pass/blocked/checked preserved as context `{summary['capri_round65_format_preflight_local_pass_count']}/{summary['capri_round65_format_preflight_blocked_count']}/{summary['capri_round65_format_preflight_checked_count']}`"
            if summary["active_scope_capri_round65_participation_status"].startswith("deferred")
            else f"- CAPRI Round 65 format preflight: `{summary['capri_round65_format_preflight_status'] or '-'}` active/closed/total `{summary['capri_round65_format_preflight_active_target_count']}/{summary['capri_round65_format_preflight_closed_target_count']}/{summary['capri_round65_format_preflight_target_count']}` local-pass/blocked/checked `{summary['capri_round65_format_preflight_local_pass_count']}/{summary['capri_round65_format_preflight_blocked_count']}/{summary['capri_round65_format_preflight_checked_count']}` missing template/candidate/errors `{summary['capri_round65_format_preflight_template_missing_count']}/{summary['capri_round65_format_preflight_candidate_missing_count']}/{summary['capri_round65_format_preflight_error_count']}` first `{summary['capri_round65_format_preflight_first_blocked_target_id'] or '-'}` `{summary['capri_round65_format_preflight_first_next_action'] or '-'}`"
        ),
        f"- win gap closure: `{summary['win_gap_closure_status'] or '-'}` closed/open `{summary['win_gap_closed_count']}/{summary['win_gap_not_closed_count']}` missing win rows `{summary['benchmark_missing_win_total_rows']}`",
        f"- historical benchmark workorders: `{summary['historical_input_workorder_count']}` core `{summary['historical_core_workorder_count']}` missing core/ablation `{summary['historical_missing_core_file_count']}/{summary['historical_missing_ablation_layer_file_count']}` operator ready/blocked `{summary['benchmark_operator_ready_count']}/{summary['benchmark_operator_blocked_count']}`",
        f"- operator dashboard: `{summary['operator_dashboard_status'] or '-'}` rows ready/blocked/total `{summary['operator_dashboard_ready_count']}/{summary['operator_dashboard_blocked_count']}/{summary['operator_dashboard_row_count']}` needs target/core/ablation/calibration/provenance `{summary['operator_dashboard_needs_target_replacement_count']}/{summary['operator_dashboard_needs_core_file_count']}/{summary['operator_dashboard_needs_ablation_layer_count']}/{summary['operator_dashboard_needs_calibration_count']}/{summary['operator_dashboard_needs_provenance_count']}`",
        f"- historical identity seed inventory: `{summary['historical_identity_seed_inventory_status'] or '-'}` candidates monomer/complex/total `{summary['historical_identity_seed_monomer_count']}/{summary['historical_identity_seed_complex_count']}/{summary['historical_identity_seed_candidate_count']}` eligible `{summary['historical_identity_seed_eligible_monomer_count']}/{summary['historical_identity_seed_eligible_complex_count']}` batch/manifest `{summary['historical_identity_seed_batch_slot_count']}/{summary['historical_identity_seed_manifest_row_count']}` clearance-required `{summary['historical_identity_seed_operator_clearance_required_count']}` first `{summary['historical_identity_seed_first_target_id'] or '-'}` manifest `{summary['historical_identity_seed_manifest_csv'] or '-'}`",
        f"- historical identity seed clearance: `{summary['historical_identity_seed_clearance_status'] or '-'}` template `{summary['historical_identity_seed_clearance_template_status'] or '-'}` ready/awaiting/total `{summary['historical_identity_seed_clearance_ready_count']}/{summary['historical_identity_seed_clearance_awaiting_count']}/{summary['historical_identity_seed_clearance_seed_count']}` cleared manifest `{summary['historical_identity_seed_clearance_cleared_manifest_count']}` open identity/core/provenance/calibration/ablation `{summary['historical_identity_seed_clearance_identity_open_count']}/{summary['historical_identity_seed_clearance_core_files_open_count']}/{summary['historical_identity_seed_clearance_no_leak_open_count']}/{summary['historical_identity_seed_clearance_calibration_open_count']}/{summary['historical_identity_seed_clearance_ablation_open_count']}` blocking fields `{summary['historical_identity_seed_clearance_blocking_field_count']}` first `{summary['historical_identity_seed_clearance_first_target_id'] or '-'}` operator `{summary['historical_identity_seed_clearance_operator_csv'] or '-'}` cleared `{summary['historical_identity_seed_clearance_cleared_manifest_csv'] or '-'}`",
        f"- historical identity seed clearance action bundle: `{summary['historical_identity_seed_clearance_action_bundle_status'] or '-'}` targets/actions/open `{summary['historical_identity_seed_clearance_action_bundle_target_count']}/{summary['historical_identity_seed_clearance_action_bundle_action_count']}/{summary['historical_identity_seed_clearance_action_bundle_open_count']}` files/folders `{summary['historical_identity_seed_clearance_action_bundle_file_count']}/{summary['historical_identity_seed_clearance_action_bundle_folder_count']}` identity/core/no-leak/calibration/ablation `{summary['historical_identity_seed_clearance_action_bundle_identity_count']}/{summary['historical_identity_seed_clearance_action_bundle_core_count']}/{summary['historical_identity_seed_clearance_action_bundle_no_leak_count']}/{summary['historical_identity_seed_clearance_action_bundle_calibration_count']}/{summary['historical_identity_seed_clearance_action_bundle_ablation_count']}` first `{summary['historical_identity_seed_clearance_action_bundle_first_action'] or '-'}`",
        f"- historical identity seed clearance field board: `{summary['historical_identity_seed_clearance_field_board_status'] or '-'}` rows operator-fill/ready/total `{summary['historical_identity_seed_clearance_field_board_operator_fill_count']}/{summary['historical_identity_seed_clearance_field_board_ready_count']}/{summary['historical_identity_seed_clearance_field_board_seed_count']}` core pass/blocked `{summary['historical_identity_seed_clearance_field_board_core_pass_count']}/{summary['historical_identity_seed_clearance_field_board_blocked_core_count']}` open no-leak/calibration/ablation/total `{summary['historical_identity_seed_clearance_field_board_no_leak_open_count']}/{summary['historical_identity_seed_clearance_field_board_calibration_open_count']}/{summary['historical_identity_seed_clearance_field_board_ablation_open_count']}/{summary['historical_identity_seed_clearance_field_board_total_open_count']}` first `{summary['historical_identity_seed_clearance_field_board_first_target_id'] or '-'}` `{summary['historical_identity_seed_clearance_field_board_first_field'] or '-'}` `{summary['historical_identity_seed_clearance_field_board_first_next_action'] or '-'}`",
        f"- historical seed no-leak dossiers: `{summary['historical_seed_no_leak_provenance_dossiers_status'] or '-'}` seeds/dossiers `{summary['historical_seed_no_leak_provenance_dossiers_seed_count']}/{summary['historical_seed_no_leak_provenance_dossiers_dossier_count']}` core/current-false `{summary['historical_seed_no_leak_provenance_dossiers_core_pass_count']}/{summary['historical_seed_no_leak_provenance_dossiers_current_false_count']}` ready/review/core-blocked/current-risk `{summary['historical_seed_no_leak_provenance_dossiers_ready_count']}/{summary['historical_seed_no_leak_provenance_dossiers_operator_review_count']}/{summary['historical_seed_no_leak_provenance_dossiers_core_blocked_count']}/{summary['historical_seed_no_leak_provenance_dossiers_current_risk_count']}` open-fields/chronology/negative-control/mtime-risk `{summary['historical_seed_no_leak_provenance_dossiers_open_field_count']}/{summary['historical_seed_no_leak_provenance_dossiers_chronology_gap_count']}/{summary['historical_seed_no_leak_provenance_dossiers_negative_control_gap_count']}/{summary['historical_seed_no_leak_provenance_dossiers_mtime_risk_count']}` first `{summary['historical_seed_no_leak_provenance_dossiers_first_target_id'] or '-'}` `{summary['historical_seed_no_leak_provenance_dossiers_first_next_action'] or '-'}`",
        f"- historical seed no-leak gap repair: `{summary['historical_seed_no_leak_gap_repair_plan_status'] or '-'}` seeds/repair-csvs `{summary['historical_seed_no_leak_gap_repair_plan_seed_count']}/{summary['historical_seed_no_leak_gap_repair_plan_repair_csv_count']}` fields/operator-required/weak/authoritative `{summary['historical_seed_no_leak_gap_repair_plan_field_count']}/{summary['historical_seed_no_leak_gap_repair_plan_operator_required_count']}/{summary['historical_seed_no_leak_gap_repair_plan_weak_count']}/{summary['historical_seed_no_leak_gap_repair_plan_authoritative_count']}` chronology/negative/clearance/mtime-risk `{summary['historical_seed_no_leak_gap_repair_plan_chronology_count']}/{summary['historical_seed_no_leak_gap_repair_plan_negative_control_count']}/{summary['historical_seed_no_leak_gap_repair_plan_clearance_count']}/{summary['historical_seed_no_leak_gap_repair_plan_mtime_risk_count']}` first `{summary['historical_seed_no_leak_gap_repair_plan_first_target_id'] or '-'}` `{summary['historical_seed_no_leak_gap_repair_plan_first_next_action'] or '-'}`",
        f"- historical seed current-target prefill: `{summary['historical_seed_current_target_prefill_status'] or '-'}` mode `{summary['historical_seed_current_target_prefill_apply_mode'] or '-'}` ready/applied/already/blocked/total `{summary['historical_seed_current_target_prefill_ready_to_apply_count']}/{summary['historical_seed_current_target_prefill_applied_count']}/{summary['historical_seed_current_target_prefill_already_count']}/{summary['historical_seed_current_target_prefill_blocked_count']}/{summary['historical_seed_current_target_prefill_row_count']}` collisions/remaining-open/hist-prefix `{summary['historical_seed_current_target_prefill_collision_count']}/{summary['historical_seed_current_target_prefill_remaining_open_count']}/{summary['historical_seed_current_target_prefill_hist_prefix_count']}` first `{summary['historical_seed_current_target_prefill_first_next_action'] or '-'}`",
        f"- historical seed native authority audit: `{summary['historical_seed_native_authority_audit_status'] or '-'}` pass/blocked/total `{summary['historical_seed_native_authority_audit_pass_count']}/{summary['historical_seed_native_authority_audit_blocked_count']}/{summary['historical_seed_native_authority_audit_seed_count']}` placeholder/CA-only/local-no-authority/ref-missing `{summary['historical_seed_native_authority_audit_placeholder_count']}/{summary['historical_seed_native_authority_audit_ca_only_count']}/{summary['historical_seed_native_authority_audit_local_generated_no_authority_count']}/{summary['historical_seed_native_authority_audit_ref_missing_count']}` first `{summary['historical_seed_native_authority_audit_first_target_id'] or '-'}` `{summary['historical_seed_native_authority_audit_first_next_action'] or '-'}`",
        f"- historical seed native replacement candidates: `{summary['historical_seed_native_replacement_candidates_status'] or '-'}` review-ready/download/file-blocked/complex-authority/total `{summary['historical_seed_native_replacement_candidates_ready_count']}/{summary['historical_seed_native_replacement_candidates_download_required_count']}/{summary['historical_seed_native_replacement_candidates_file_blocked_count']}/{summary['historical_seed_native_replacement_candidates_complex_authority_count']}/{summary['historical_seed_native_replacement_candidates_candidate_count']}` monomer `{summary['historical_seed_native_replacement_candidates_monomer_count']}` dir `{summary['historical_seed_native_replacement_candidates_candidate_dir'] or '-'}` first `{summary['historical_seed_native_replacement_candidates_first_target_id'] or '-'}` `{summary['historical_seed_native_replacement_candidates_first_next_action'] or '-'}`",
        f"- historical seed complex source-authority candidates: `{summary['historical_seed_complex_source_authority_candidates_status'] or '-'}` review-ready/direct/homolog/blocked/total `{summary['historical_seed_complex_source_authority_candidates_review_ready_count']}/{summary['historical_seed_complex_source_authority_candidates_direct_count']}/{summary['historical_seed_complex_source_authority_candidates_homolog_count']}/{summary['historical_seed_complex_source_authority_candidates_blocked_count']}/{summary['historical_seed_complex_source_authority_candidates_candidate_count']}` operator-apply/claim-promotion `{summary['historical_seed_complex_source_authority_candidates_operator_apply_count']}/{summary['historical_seed_complex_source_authority_candidates_claim_promotion_count']}` protein `{summary['historical_seed_complex_source_authority_candidates_protein_ref'] or '-'}` first `{summary['historical_seed_complex_source_authority_candidates_first_target_id'] or '-'}` `{summary['historical_seed_complex_source_authority_candidates_first_next_action'] or '-'}`",
        f"- historical seed chronology candidates: `{summary['historical_seed_chronology_candidate_board_status'] or '-'}` ready/warning/evidence-required/conflict/total `{summary['historical_seed_chronology_candidate_board_ready_count']}/{summary['historical_seed_chronology_candidate_board_warning_count']}/{summary['historical_seed_chronology_candidate_board_evidence_required_count']}/{summary['historical_seed_chronology_candidate_board_conflict_count']}/{summary['historical_seed_chronology_candidate_board_row_count']}` path-date/mtime/risk `{summary['historical_seed_chronology_candidate_board_path_date_count']}/{summary['historical_seed_chronology_candidate_board_mtime_count']}/{summary['historical_seed_chronology_candidate_board_mtime_risk_count']}` first `{summary['historical_seed_chronology_candidate_board_first_target_id'] or '-'}` `{summary['historical_seed_chronology_candidate_board_first_next_action'] or '-'}`",
        f"- historical seed authoritative chronology audit: `{summary['historical_seed_authoritative_chronology_audit_status'] or '-'}` before/post/evidence/total `{summary['historical_seed_authoritative_chronology_audit_before_native_count']}/{summary['historical_seed_authoritative_chronology_audit_post_native_count']}/{summary['historical_seed_authoritative_chronology_audit_evidence_required_count']}/{summary['historical_seed_authoritative_chronology_audit_seed_count']}` native-date/prediction-date `{summary['historical_seed_authoritative_chronology_audit_native_date_count']}/{summary['historical_seed_authoritative_chronology_audit_prediction_date_count']}` missing native/prediction `{summary['historical_seed_authoritative_chronology_audit_missing_native_date_count']}/{summary['historical_seed_authoritative_chronology_audit_missing_prediction_date_count']}` first `{summary['historical_seed_authoritative_chronology_audit_first_target_id'] or '-'}` `{summary['historical_seed_authoritative_chronology_audit_first_next_action'] or '-'}`",
        f"- historical seed lane decision: `{summary['historical_seed_lane_decision_packet_status'] or '-'}` strict/retrospective/authority/total `{summary['historical_seed_lane_decision_packet_strict_blind_count']}/{summary['historical_seed_lane_decision_packet_retrospective_count']}/{summary['historical_seed_lane_decision_packet_authority_required_count']}/{summary['historical_seed_lane_decision_packet_seed_count']}` competitive/identity/sidechain `{summary['historical_seed_lane_decision_packet_competitive_count']}/{summary['historical_seed_lane_decision_packet_identity_count']}/{summary['historical_seed_lane_decision_packet_sidechain_count']}` replacement/operator-decision `{summary['historical_seed_lane_decision_packet_replacement_required_count']}/{summary['historical_seed_lane_decision_packet_operator_decision_count']}` first `{summary['historical_seed_lane_decision_packet_first_target_id'] or '-'}` `{summary['historical_seed_lane_decision_packet_first_next_action'] or '-'}`",
        f"- historical seed strict-blind replacement queue: `{summary['historical_seed_strict_blind_replacement_queue_status'] or '-'}` slots monomer/complex/total `{summary['historical_seed_strict_blind_replacement_queue_monomer_count']}/{summary['historical_seed_strict_blind_replacement_queue_complex_count']}/{summary['historical_seed_strict_blind_replacement_queue_slot_count']}` replacement/ready/competitive `{summary['historical_seed_strict_blind_replacement_queue_replacement_required_count']}/{summary['historical_seed_strict_blind_replacement_queue_ready_count']}/{summary['historical_seed_strict_blind_replacement_queue_competitive_count']}` current seed strict/retrospective/authority/competitive `{summary['historical_seed_strict_blind_replacement_queue_current_seed_strict_count']}/{summary['historical_seed_strict_blind_replacement_queue_current_seed_retrospective_count']}/{summary['historical_seed_strict_blind_replacement_queue_current_seed_authority_count']}/{summary['historical_seed_strict_blind_replacement_queue_current_seed_competitive_count']}` fields `{summary['historical_seed_strict_blind_replacement_queue_requirement_field_count']}` first `{summary['historical_seed_strict_blind_replacement_queue_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_queue_first_next_action'] or '-'}`",
        f"- historical seed strict-blind replacement intake: `{summary['historical_seed_strict_blind_replacement_intake_status'] or '-'}` slots ready/awaiting/total `{summary['historical_seed_strict_blind_replacement_intake_ready_count']}/{summary['historical_seed_strict_blind_replacement_intake_blocked_count']}/{summary['historical_seed_strict_blind_replacement_intake_slot_count']}` fields filled/missing/required `{summary['historical_seed_strict_blind_replacement_intake_filled_field_count']}/{summary['historical_seed_strict_blind_replacement_intake_missing_field_count']}/{summary['historical_seed_strict_blind_replacement_intake_required_field_count']}` templates created/preserved `{summary['historical_seed_strict_blind_replacement_intake_created_template_count']}/{summary['historical_seed_strict_blind_replacement_intake_preserved_template_count']}` first `{summary['historical_seed_strict_blind_replacement_intake_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_intake_first_next_action'] or '-'}`",
        f"- historical seed strict-blind evidence dropzones: `{summary['historical_seed_strict_blind_replacement_evidence_dropzones_status'] or '-'}` dropzones ready/awaiting/total `{summary['historical_seed_strict_blind_replacement_evidence_dropzones_ready_count']}/{summary['historical_seed_strict_blind_replacement_evidence_dropzones_awaiting_count']}/{summary['historical_seed_strict_blind_replacement_evidence_dropzones_count']}` files present/missing/required `{summary['historical_seed_strict_blind_replacement_evidence_dropzones_file_present_count']}/{summary['historical_seed_strict_blind_replacement_evidence_dropzones_file_missing_count']}/{summary['historical_seed_strict_blind_replacement_evidence_dropzones_file_required_count']}` operator-values `{summary['historical_seed_strict_blind_replacement_evidence_dropzones_operator_value_count']}` patch-previews `{summary['historical_seed_strict_blind_replacement_evidence_dropzones_patch_preview_count']}` first `{summary['historical_seed_strict_blind_replacement_evidence_dropzones_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_evidence_dropzones_first_next_action'] or '-'}`",
        f"- historical seed strict-blind evidence action board: `{summary['historical_seed_strict_blind_replacement_evidence_action_board_status'] or '-'}` actions ready/open/blocked/total `{summary['historical_seed_strict_blind_replacement_evidence_action_board_ready_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_open_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_blocked_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_action_count']}` missing prediction/native/authority/no-leak/ablation/calibration `{summary['historical_seed_strict_blind_replacement_evidence_action_board_prediction_missing_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_native_missing_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_authority_missing_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_no_leak_missing_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_ablation_missing_count']}/{summary['historical_seed_strict_blind_replacement_evidence_action_board_calibration_missing_count']}` first `{summary['historical_seed_strict_blind_replacement_evidence_action_board_first_action_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_evidence_action_board_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_evidence_action_board_first_field'] or '-'}`",
        f"- historical seed strict-blind evidence quality audit: `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_status'] or '-'}` slots ready/awaiting/blocked/total `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_ready_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_awaiting_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_blocked_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_slot_count']}` files present/missing/required `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_file_present_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_file_missing_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_file_required_count']}` pdb slots valid/invalid `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_pdb_valid_slot_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_pdb_invalid_slot_count']}` supporting slots valid/invalid `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_supporting_valid_slot_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_supporting_invalid_slot_count']}` pred/native distinct/identical `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_distinct_count']}/{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_identical_count']}` first `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_evidence_quality_audit_first_status'] or '-'}`",
        f"- historical seed strict-blind evidence import gate: `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_status'] or '-'}` mode `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_apply_mode'] or '-'}` actions file/operator/total `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_file_action_count']}/{summary['historical_seed_strict_blind_replacement_evidence_import_gate_operator_action_count']}/{summary['historical_seed_strict_blind_replacement_evidence_import_gate_action_count']}` ready/applied/already `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_ready_count']}/{summary['historical_seed_strict_blind_replacement_evidence_import_gate_applied_count']}/{summary['historical_seed_strict_blind_replacement_evidence_import_gate_already_applied_count']}` awaiting file/operator `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_awaiting_file_count']}/{summary['historical_seed_strict_blind_replacement_evidence_import_gate_awaiting_operator_count']}` blocked `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_blocked_count']}` first `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_first_field'] or '-'}` `{summary['historical_seed_strict_blind_replacement_evidence_import_gate_first_status'] or '-'}`",
        f"- historical seed strict-blind operator value gate: `{summary['historical_seed_strict_blind_replacement_operator_value_gate_status'] or '-'}` mode `{summary['historical_seed_strict_blind_replacement_operator_value_gate_apply_mode'] or '-'}` templates created/preserved/total `{summary['historical_seed_strict_blind_replacement_operator_value_gate_created_template_count']}/{summary['historical_seed_strict_blind_replacement_operator_value_gate_preserved_template_count']}/{summary['historical_seed_strict_blind_replacement_operator_value_gate_template_count']}` actions ready/applied/already/total `{summary['historical_seed_strict_blind_replacement_operator_value_gate_ready_count']}/{summary['historical_seed_strict_blind_replacement_operator_value_gate_applied_count']}/{summary['historical_seed_strict_blind_replacement_operator_value_gate_already_applied_count']}/{summary['historical_seed_strict_blind_replacement_operator_value_gate_action_count']}` awaiting value/evidence/clearance `{summary['historical_seed_strict_blind_replacement_operator_value_gate_awaiting_value_count']}/{summary['historical_seed_strict_blind_replacement_operator_value_gate_awaiting_evidence_count']}/{summary['historical_seed_strict_blind_replacement_operator_value_gate_awaiting_clearance_count']}` blocked `{summary['historical_seed_strict_blind_replacement_operator_value_gate_blocked_count']}` first `{summary['historical_seed_strict_blind_replacement_operator_value_gate_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_operator_value_gate_first_field'] or '-'}` `{summary['historical_seed_strict_blind_replacement_operator_value_gate_first_status'] or '-'}`",
        f"- historical seed strict-blind operator action board: `{summary['historical_seed_strict_blind_replacement_operator_action_board_status'] or '-'}` actions ready/applied/already/total `{summary['historical_seed_strict_blind_replacement_operator_action_board_ready_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_applied_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_already_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_action_count']}` open value/evidence/clearance `{summary['historical_seed_strict_blind_replacement_operator_action_board_open_value_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_open_evidence_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_open_clearance_count']}` missing target/benchmark/non-current/pred-date/native-date/before-native `{summary['historical_seed_strict_blind_replacement_operator_action_board_target_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_benchmark_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_non_current_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_prediction_date_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_native_date_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_before_native_missing_count']}` false-controls/operator-clearance `{summary['historical_seed_strict_blind_replacement_operator_action_board_public_false_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_other_team_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_post_release_missing_count']}/{summary['historical_seed_strict_blind_replacement_operator_action_board_operator_clearance_missing_count']}` first `{summary['historical_seed_strict_blind_replacement_operator_action_board_first_action_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_operator_action_board_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_operator_action_board_first_field'] or '-'}` `{summary['historical_seed_strict_blind_replacement_operator_action_board_first_status'] or '-'}`",
        f"- historical seed strict-blind promotion gate: `{summary['historical_seed_strict_blind_replacement_promotion_gate_status'] or '-'}` slots ready/total `{summary['historical_seed_strict_blind_replacement_promotion_gate_ready_count']}/{summary['historical_seed_strict_blind_replacement_promotion_gate_slot_count']}` awaiting file/operator/apply/intake `{summary['historical_seed_strict_blind_replacement_promotion_gate_awaiting_file_count']}/{summary['historical_seed_strict_blind_replacement_promotion_gate_awaiting_operator_count']}/{summary['historical_seed_strict_blind_replacement_promotion_gate_awaiting_apply_count']}/{summary['historical_seed_strict_blind_replacement_promotion_gate_awaiting_intake_count']}` blocked review `{summary['historical_seed_strict_blind_replacement_promotion_gate_blocked_review_count']}` complete intake/file/operator `{summary['historical_seed_strict_blind_replacement_promotion_gate_intake_ready_count']}/{summary['historical_seed_strict_blind_replacement_promotion_gate_file_complete_count']}/{summary['historical_seed_strict_blind_replacement_promotion_gate_operator_complete_count']}` awaiting actions file/operator `{summary['historical_seed_strict_blind_replacement_promotion_gate_file_awaiting_action_count']}/{summary['historical_seed_strict_blind_replacement_promotion_gate_operator_awaiting_action_count']}` first `{summary['historical_seed_strict_blind_replacement_promotion_gate_first_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_promotion_gate_first_phase'] or '-'}` `{summary['historical_seed_strict_blind_replacement_promotion_gate_first_status'] or '-'}`",
        f"- historical seed strict-blind replacement cycle: `{summary['historical_seed_strict_blind_replacement_cycle_status'] or '-'}` promotion ready/total `{summary['historical_seed_strict_blind_replacement_cycle_promotion_ready_count']}/{summary['historical_seed_strict_blind_replacement_cycle_slot_count']}` files present/missing `{summary['historical_seed_strict_blind_replacement_cycle_evidence_file_present_count']}/{summary['historical_seed_strict_blind_replacement_cycle_evidence_file_missing_count']}` quality ready/awaiting/blocked `{summary['historical_seed_strict_blind_replacement_cycle_quality_ready_count']}/{summary['historical_seed_strict_blind_replacement_cycle_quality_awaiting_count']}/{summary['historical_seed_strict_blind_replacement_cycle_quality_blocked_count']}` import ready/file/operator `{summary['historical_seed_strict_blind_replacement_cycle_import_ready_count']}/{summary['historical_seed_strict_blind_replacement_cycle_import_awaiting_file_count']}/{summary['historical_seed_strict_blind_replacement_cycle_import_awaiting_operator_count']}` operator ready/awaiting `{summary['historical_seed_strict_blind_replacement_cycle_operator_ready_count']}/{summary['historical_seed_strict_blind_replacement_cycle_operator_awaiting_value_count']}` operator-board ready/open-value/open-evidence/open-clearance `{summary['historical_seed_strict_blind_replacement_cycle_operator_action_board_ready_count']}/{summary['historical_seed_strict_blind_replacement_cycle_operator_action_board_open_value_count']}/{summary['historical_seed_strict_blind_replacement_cycle_operator_action_board_open_evidence_count']}/{summary['historical_seed_strict_blind_replacement_cycle_operator_action_board_open_clearance_count']}` first `{summary['historical_seed_strict_blind_replacement_cycle_first_blocking_stage'] or '-'}` `{summary['historical_seed_strict_blind_replacement_cycle_first_benchmark_id'] or '-'}`",
        f"- historical seed strict-blind first slot kit: `{summary['historical_seed_strict_blind_replacement_first_slot_kit_status'] or '-'}` benchmark/target/scope `{summary['historical_seed_strict_blind_replacement_first_slot_kit_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_kit_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_kit_scope'] or '-'}` evidence ready/open/blocked/total `{summary['historical_seed_strict_blind_replacement_first_slot_kit_evidence_ready_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_evidence_open_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_evidence_blocked_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_evidence_action_count']}` operator ready/open/blocked/total `{summary['historical_seed_strict_blind_replacement_first_slot_kit_operator_ready_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_operator_open_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_operator_blocked_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_operator_action_count']}` operator open value/evidence/clearance `{summary['historical_seed_strict_blind_replacement_first_slot_kit_operator_open_value_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_operator_open_evidence_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_kit_operator_open_clearance_count']}` kit `{summary['historical_seed_strict_blind_replacement_first_slot_kit_kit_folder'] or '-'}` first `{summary['historical_seed_strict_blind_replacement_first_slot_kit_first_action_group'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_kit_first_action_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_kit_first_field'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_kit_first_status'] or '-'}`",
        f"- historical seed strict-blind first slot local candidates: `{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_status'] or '-'}` required `{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_required_benchmark_id'] or '-'}` candidates ready/strict/material/total `{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_ready_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_strict_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_material_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_candidate_count']}` present prediction/native/authority `{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_prediction_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_native_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_authority_count']}` blocked chronology/no-leak/ablation/calibration `{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_chronology_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_no_leak_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_ablation_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_blocked_calibration_count']}` first `{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_first_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_local_candidate_board_first_status'] or '-'}`",
        f"- historical seed strict-blind first slot candidate repairs: `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_status'] or '-'}` required `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_required_benchmark_id'] or '-'}` actions open/blocked/total `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_open_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_blocked_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_action_count']}` classes chronology/no-leak/ablation/calibration `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_chronology_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_no_leak_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_ablation_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_calibration_count']}` source prediction/native/authority `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_prediction_file_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_native_file_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_native_authority_count']}` eligibility `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_eligibility_count']}` first `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_action_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_repair_class'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_blocker'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_first_status'] or '-'}`",
        f"- historical seed strict-blind first slot repair feasibility: `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_status'] or '-'}` required `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_required_benchmark_id'] or '-'}` actions `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_action_count']}` post-native/eligibility `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_post_native_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_post_native_eligibility_count']}` external actions/targets `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_external_action_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_external_target_count']}` repairable source/evidence/date `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_source_required_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_evidence_required_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_date_required_count']}` primary/pre-native `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_primary_blocked_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_pre_native_count']}` first external `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_action_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_blocker'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_external_next_route'] or '-'}` first actionable `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_actionable_action_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_actionable_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_first_actionable_status'] or '-'}`",
        f"- historical seed strict-blind first slot source route: `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_status'] or '-'}` required `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_required_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_required_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_required_scope'] or '-'}` routes in/out/total `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_in_scope_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_out_of_scope_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_route_count']}` allowed `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_allowed_count']}` external targets/actions `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_external_required_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_external_action_count']}` out-scope source/date `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_out_scope_source_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_out_scope_date_count']}` first external `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_route_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_target_id'] or '-'}` prediction/native `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_prediction_created_at'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_source_route_board_first_external_native_release_date'] or '-'}`",
        f"- historical seed strict-blind first slot official archive sources: `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_status'] or '-'}` required `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_required_benchmark_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_required_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_required_scope'] or '-'}` sources `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_source_count']}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_source_competitions'] or '-'}` candidates ready/blocked/total `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_ready_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_blocked_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_candidate_count']}` pre/native-ready/lookup `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_pre_native_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_ready_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_lookup_count']}` native PDB/mmCIF `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_pdb_ready_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_native_mmcif_only_count']}` metadata/CAPRI/special `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_metadata_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_capri_marker_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_special_mode_count']}` regular/domain/variant `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_regular_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_domain_count']}/{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_variant_count']}` first `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_candidate_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_competition'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_target_id'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_pdb_code'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_download_status'] or '-'}` prediction/native `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_prediction_at'] or '-'}` `{summary['historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_first_native_anchor'] or '-'}`",
        f"- historical seed official archive baseline lane: `{summary['historical_seed_official_archive_baseline_lane_status'] or '-'}` source ready/total `{summary['historical_seed_official_archive_baseline_lane_source_ready_count']}/{summary['historical_seed_official_archive_baseline_lane_source_count']}` baseline ready/blocked/total `{summary['historical_seed_official_archive_baseline_lane_ready_count']}/{summary['historical_seed_official_archive_baseline_lane_blocked_count']}/{summary['historical_seed_official_archive_baseline_lane_candidate_count']}` proof-eligible/strict-blocked/other-team `{summary['historical_seed_official_archive_baseline_lane_proof_eligible_count']}/{summary['historical_seed_official_archive_baseline_lane_strict_blind_blocked_count']}/{summary['historical_seed_official_archive_baseline_lane_other_team_count']}` policy `{summary['historical_seed_official_archive_baseline_lane_policy'] or '-'}` first `{summary['historical_seed_official_archive_baseline_lane_first_candidate_id'] or '-'}` `{summary['historical_seed_official_archive_baseline_lane_first_competition'] or '-'}` `{summary['historical_seed_official_archive_baseline_lane_first_target_id'] or '-'}` `{summary['historical_seed_official_archive_baseline_lane_first_native_pdb_code'] or '-'}` manifest `{summary['historical_seed_official_archive_baseline_lane_first_manifest'] or '-'}`",
        f"- strict-blind first slot source bridge: `{summary['strict_blind_first_slot_source_bridge_status'] or '-'}` required `{summary['strict_blind_first_slot_source_bridge_required_benchmark_id'] or '-'}` `{summary['strict_blind_first_slot_source_bridge_required_target_id'] or '-'}` `{summary['strict_blind_first_slot_source_bridge_required_scope'] or '-'}` official ready/total `{summary['strict_blind_first_slot_source_bridge_official_ready_count']}/{summary['strict_blind_first_slot_source_bridge_official_candidate_count']}` native-bridge `{summary['strict_blind_first_slot_source_bridge_native_ready_count']}` baseline-only/strict-blocked `{summary['strict_blind_first_slot_source_bridge_baseline_only_count']}/{summary['strict_blind_first_slot_source_bridge_strict_blocked_count']}` operator-only/internal-blocked `{summary['strict_blind_first_slot_source_bridge_operator_only_count']}/{summary['strict_blind_first_slot_source_bridge_internal_prediction_blocked_count']}` auto-apply `{summary['strict_blind_first_slot_source_bridge_auto_apply_count']}` first `{summary['strict_blind_first_slot_source_bridge_first_candidate_competition'] or '-'}` `{summary['strict_blind_first_slot_source_bridge_first_candidate_target_id'] or '-'}` `{summary['strict_blind_first_slot_source_bridge_first_candidate_native_pdb_code'] or '-'}` blocker `{summary['strict_blind_first_slot_source_bridge_first_blocker'] or '-'}` folder `{summary['strict_blind_first_slot_source_bridge_bridge_folder'] or '-'}`",
        f"- strict-blind internal prediction source audit: `{summary['strict_blind_internal_prediction_source_audit_status'] or '-'}` required `{summary['strict_blind_internal_prediction_source_audit_required_benchmark_id'] or '-'}` `{summary['strict_blind_internal_prediction_source_audit_required_target_id'] or '-'}` `{summary['strict_blind_internal_prediction_source_audit_required_scope'] or '-'}` first-field `{summary['strict_blind_internal_prediction_source_audit_first_open_field'] or '-'}` local eligible/total `{summary['strict_blind_internal_prediction_source_audit_local_eligible_count']}/{summary['strict_blind_internal_prediction_source_audit_local_candidate_count']}` routes allowed/total `{summary['strict_blind_internal_prediction_source_audit_source_route_allowed_count']}/{summary['strict_blind_internal_prediction_source_audit_source_route_count']}` official blocked/total `{summary['strict_blind_internal_prediction_source_audit_official_blocked_count']}/{summary['strict_blind_internal_prediction_source_audit_official_baseline_count']}` native/internal-blocked `{summary['strict_blind_internal_prediction_source_audit_native_ready_count']}/{summary['strict_blind_internal_prediction_source_audit_internal_blocked_count']}` allowed/template `{summary['strict_blind_internal_prediction_source_audit_allowed_internal_source_count']}/{summary['strict_blind_internal_prediction_source_audit_template_count']}` blocker `{summary['strict_blind_internal_prediction_source_audit_first_blocker'] or '-'}` template `{summary['strict_blind_internal_prediction_source_audit_manifest_template'] or '-'}`",
        f"- strict-blind internal prediction source gate: `{summary['strict_blind_internal_prediction_source_gate_status'] or '-'}` required `{summary['strict_blind_internal_prediction_source_gate_required_benchmark_id'] or '-'}` `{summary['strict_blind_internal_prediction_source_gate_required_target_id'] or '-'}` `{summary['strict_blind_internal_prediction_source_gate_required_scope'] or '-'}` manifest rows `{summary['strict_blind_internal_prediction_source_gate_manifest_row_count']}` checks pass/blocked/total `{summary['strict_blind_internal_prediction_source_gate_pass_count']}/{summary['strict_blind_internal_prediction_source_gate_blocked_count']}/{summary['strict_blind_internal_prediction_source_gate_check_count']}` source `{summary['strict_blind_internal_prediction_source_gate_source_id'] or '-'}` prediction/dropzone `{summary['strict_blind_internal_prediction_source_gate_prediction_pdb'] or '-'}` `{summary['strict_blind_internal_prediction_source_gate_prediction_dropzone'] or '-'}` first `{summary['strict_blind_internal_prediction_source_gate_first_blocked_check'] or '-'}` `{summary['strict_blind_internal_prediction_source_gate_first_blocker'] or '-'}` manifest `{summary['strict_blind_internal_prediction_source_gate_manifest_csv'] or '-'}`",
        f"- strict-blind source gate field board: `{summary['strict_blind_source_gate_field_board_status'] or '-'}` required `{summary['strict_blind_source_gate_field_board_required_benchmark_id'] or '-'}` `{summary['strict_blind_source_gate_field_board_required_target_id'] or '-'}` `{summary['strict_blind_source_gate_field_board_required_scope'] or '-'}` actions manifest/file/manifest-file/total `{summary['strict_blind_source_gate_field_board_manifest_value_action_count']}/{summary['strict_blind_source_gate_field_board_file_action_count']}/{summary['strict_blind_source_gate_field_board_manifest_file_action_count']}/{summary['strict_blind_source_gate_field_board_field_action_count']}` blocked checks covered `{summary['strict_blind_source_gate_field_board_blocked_check_covered_count']}` first `{summary['strict_blind_source_gate_field_board_first_field_key'] or '-'}` `{summary['strict_blind_source_gate_field_board_first_blockers'] or '-'}` folder `{summary['strict_blind_source_gate_field_board_dir'] or '-'}`",
        f"- strict-blind source gate operator packet: `{summary['strict_blind_source_gate_operator_packet_status'] or '-'}` required `{summary['strict_blind_source_gate_operator_packet_required_benchmark_id'] or '-'}` `{summary['strict_blind_source_gate_operator_packet_required_target_id'] or '-'}` `{summary['strict_blind_source_gate_operator_packet_required_scope'] or '-'}` operator ready/awaiting/total `{summary['strict_blind_source_gate_operator_packet_operator_ready_count']}/{summary['strict_blind_source_gate_operator_packet_operator_awaiting_count']}/{summary['strict_blind_source_gate_operator_packet_field_action_count']}` patch ready/awaiting `{summary['strict_blind_source_gate_operator_packet_patch_ready_count']}/{summary['strict_blind_source_gate_operator_packet_patch_awaiting_count']}` actions manifest/file/derived `{summary['strict_blind_source_gate_operator_packet_manifest_patch_count']}/{summary['strict_blind_source_gate_operator_packet_file_copy_count']}/{summary['strict_blind_source_gate_operator_packet_derived_check_count']}` first `{summary['strict_blind_source_gate_operator_packet_first_field_key'] or '-'}` `{summary['strict_blind_source_gate_operator_packet_first_operator_status'] or '-'}` csv `{summary['strict_blind_source_gate_operator_packet_operator_csv'] or '-'}` folder `{summary['strict_blind_source_gate_operator_packet_dir'] or '-'}`",
        f"- strict-blind source gate source requests: `{summary['strict_blind_source_gate_source_request_packet_status'] or '-'}` required `{summary['strict_blind_source_gate_source_request_packet_required_benchmark_id'] or '-'}` `{summary['strict_blind_source_gate_source_request_packet_required_target_id'] or '-'}` `{summary['strict_blind_source_gate_source_request_packet_required_scope'] or '-'}` requests pre-native/replacement/operator-repair/total `{summary['strict_blind_source_gate_source_request_packet_pre_native_source_count']}/{summary['strict_blind_source_gate_source_request_packet_candidate_replacement_count']}/{summary['strict_blind_source_gate_source_request_packet_operator_repair_count']}/{summary['strict_blind_source_gate_source_request_packet_request_count']}` templates ready/awaiting `{summary['strict_blind_source_gate_source_request_packet_operator_template_ready_count']}/{summary['strict_blind_source_gate_source_request_packet_operator_template_awaiting_count']}` fields filled/missing/total `{summary['strict_blind_source_gate_source_request_packet_operator_field_filled_count']}/{summary['strict_blind_source_gate_source_request_packet_operator_field_missing_count']}/{summary['strict_blind_source_gate_source_request_packet_operator_field_count']}` monomer/complex `{summary['strict_blind_source_gate_source_request_packet_monomer_request_count']}/{summary['strict_blind_source_gate_source_request_packet_complex_request_count']}` first `{summary['strict_blind_source_gate_source_request_packet_first_request_id'] or '-'}` `{summary['strict_blind_source_gate_source_request_packet_first_target_id'] or '-'}` `{summary['strict_blind_source_gate_source_request_packet_first_kind'] or '-'}` `{summary['strict_blind_source_gate_source_request_packet_first_blocker'] or '-'}` missing `{summary['strict_blind_source_gate_source_request_packet_first_missing_operator_field'] or '-'}` folder `{summary['strict_blind_source_gate_source_request_packet_dir'] or '-'}`",
        f"- strict-blind source request fulfillment gate: `{summary['strict_blind_source_request_fulfillment_gate_status'] or '-'}` requests ready/blocked/total `{summary['strict_blind_source_request_fulfillment_gate_ready_request_count']}/{summary['strict_blind_source_request_fulfillment_gate_blocked_request_count']}/{summary['strict_blind_source_request_fulfillment_gate_request_count']}` fields filled/missing/total `{summary['strict_blind_source_request_fulfillment_gate_operator_field_filled_count']}/{summary['strict_blind_source_request_fulfillment_gate_operator_field_missing_count']}/{summary['strict_blind_source_request_fulfillment_gate_operator_field_count']}` evidence present/missing `{summary['strict_blind_source_request_fulfillment_gate_operator_evidence_ref_count']}/{summary['strict_blind_source_request_fulfillment_gate_operator_evidence_ref_missing_count']}` validation pdb/chronology/internal-source `{summary['strict_blind_source_request_fulfillment_gate_prediction_pdb_valid_count']}/{summary['strict_blind_source_request_fulfillment_gate_chronology_pass_count']}/{summary['strict_blind_source_request_fulfillment_gate_internal_source_pass_count']}` first `{summary['strict_blind_source_request_fulfillment_gate_first_blocked_request_id'] or '-'}` `{summary['strict_blind_source_request_fulfillment_gate_first_blocked_target_id'] or '-'}` `{summary['strict_blind_source_request_fulfillment_gate_first_blocker'] or '-'}`",
        f"- strict-blind source request operator fill worklist: `{summary['strict_blind_source_request_operator_fill_worklist_status'] or '-'}` fields ready/value-missing/evidence-missing/total `{summary['strict_blind_source_request_operator_fill_worklist_field_ready_count']}/{summary['strict_blind_source_request_operator_fill_worklist_operator_value_missing_count']}/{summary['strict_blind_source_request_operator_fill_worklist_operator_evidence_missing_count']}/{summary['strict_blind_source_request_operator_fill_worklist_field_action_count']}` candidate fields `{summary['strict_blind_source_request_operator_fill_worklist_candidate_replacement_field_count']}` first `{summary['strict_blind_source_request_operator_fill_worklist_first_fill_id'] or '-'}` `{summary['strict_blind_source_request_operator_fill_worklist_first_request_id'] or '-'}` `{summary['strict_blind_source_request_operator_fill_worklist_first_target_id'] or '-'}` `{summary['strict_blind_source_request_operator_fill_worklist_first_field_key'] or '-'}` `{summary['strict_blind_source_request_operator_fill_worklist_first_blocker'] or '-'}`",
        f"- strict-blind source request operator sync plan: `{summary['strict_blind_source_request_operator_sync_plan_status'] or '-'}` mode `{summary['strict_blind_source_request_operator_sync_plan_mode'] or '-'}` fulfillment ready/blocked `{summary['strict_blind_source_request_operator_sync_plan_ready_request_count']}/{summary['strict_blind_source_request_operator_sync_plan_blocked_request_count']}` actions ready/blocked/applied/total `{summary['strict_blind_source_request_operator_sync_plan_ready_sync_action_count']}/{summary['strict_blind_source_request_operator_sync_plan_blocked_sync_action_count']}/{summary['strict_blind_source_request_operator_sync_plan_applied_sync_action_count']}/{summary['strict_blind_source_request_operator_sync_plan_sync_action_count']}` selected `{summary['strict_blind_source_request_operator_sync_plan_selected_request_id'] or '-'}` `{summary['strict_blind_source_request_operator_sync_plan_selected_target_id'] or '-'}` first `{summary['strict_blind_source_request_operator_sync_plan_first_action_id'] or '-'}` `{summary['strict_blind_source_request_operator_sync_plan_first_blocker'] or '-'}` destination `{summary['strict_blind_source_request_operator_sync_plan_destination_operator_csv'] or '-'}`",
        f"- strict-blind source request closure board: `{summary['strict_blind_source_request_closure_board_status'] or '-'}` required `{summary['strict_blind_source_request_closure_board_required_benchmark_id'] or '-'}` `{summary['strict_blind_source_request_closure_board_required_target_id'] or '-'}` `{summary['strict_blind_source_request_closure_board_required_scope'] or '-'}` stages ready/blocked/total `{summary['strict_blind_source_request_closure_board_ready_stage_count']}/{summary['strict_blind_source_request_closure_board_blocked_stage_count']}/{summary['strict_blind_source_request_closure_board_stage_count']}` source/fulfill/fill/sync/operator/gate/apply/slot/batch `{summary['strict_blind_source_request_closure_board_source_request_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_fulfillment_gate_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_operator_fill_worklist_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_operator_sync_plan_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_source_gate_operator_packet_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_internal_prediction_source_gate_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_internal_prediction_apply_plan_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_first_slot_closure_kit_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_batch_closure_runway_status'] or '-'}` first `{summary['strict_blind_source_request_closure_board_first_blocked_stage_id'] or '-'}` `{summary['strict_blind_source_request_closure_board_first_blocked_stage_status'] or '-'}` `{summary['strict_blind_source_request_closure_board_first_blocker'] or '-'}` next `{summary['strict_blind_source_request_closure_board_next_action'] or '-'}`",
        f"- strict-blind internal prediction source apply plan: `{summary['strict_blind_internal_prediction_source_apply_plan_status'] or '-'}` required `{summary['strict_blind_internal_prediction_source_apply_plan_required_benchmark_id'] or '-'}` `{summary['strict_blind_internal_prediction_source_apply_plan_required_target_id'] or '-'}` `{summary['strict_blind_internal_prediction_source_apply_plan_required_scope'] or '-'}` gate `{summary['strict_blind_internal_prediction_source_apply_plan_gate_status'] or '-'}` actions ready/blocked/total `{summary['strict_blind_internal_prediction_source_apply_plan_ready_action_count']}/{summary['strict_blind_internal_prediction_source_apply_plan_blocked_action_count']}/{summary['strict_blind_internal_prediction_source_apply_plan_action_count']}` file/operator/supp `{summary['strict_blind_internal_prediction_source_apply_plan_file_action_count']}/{summary['strict_blind_internal_prediction_source_apply_plan_operator_value_action_count']}/{summary['strict_blind_internal_prediction_source_apply_plan_supplemental_action_count']}` prediction `{summary['strict_blind_internal_prediction_source_apply_plan_prediction_source'] or '-'}` `->{summary['strict_blind_internal_prediction_source_apply_plan_prediction_destination'] or '-'}` first `{summary['strict_blind_internal_prediction_source_apply_plan_first_blocked_action_id'] or '-'}` `{summary['strict_blind_internal_prediction_source_apply_plan_first_blocker'] or '-'}`",
        f"- strict-blind first slot closure kit: `{summary['strict_blind_first_slot_closure_kit_status'] or '-'}` required `{summary['strict_blind_first_slot_closure_kit_required_benchmark_id'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_required_target_id'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_required_scope'] or '-'}` steps ready/blocked/total `{summary['strict_blind_first_slot_closure_kit_step_ready_count']}/{summary['strict_blind_first_slot_closure_kit_step_blocked_count']}/{summary['strict_blind_first_slot_closure_kit_step_count']}` fills source-gate/source-request/file/operator/total `{summary['strict_blind_first_slot_closure_kit_source_gate_fill_count']}/{summary['strict_blind_first_slot_closure_kit_source_request_fill_count']}/{summary['strict_blind_first_slot_closure_kit_file_fill_count']}/{summary['strict_blind_first_slot_closure_kit_operator_fill_count']}/{summary['strict_blind_first_slot_closure_kit_fill_item_count']}` source/source-request/apply/dropzone/operator/intake `{summary['strict_blind_first_slot_closure_kit_source_gate_status'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_source_request_packet_status'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_apply_plan_status'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_dropzone_status'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_operator_gate_status'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_intake_preflight_status'] or '-'}` source-requests `{summary['strict_blind_first_slot_closure_kit_source_request_pre_native_count']}/{summary['strict_blind_first_slot_closure_kit_source_request_candidate_replacement_count']}/{summary['strict_blind_first_slot_closure_kit_source_request_operator_repair_count']}/{summary['strict_blind_first_slot_closure_kit_source_request_count']}` first `{summary['strict_blind_first_slot_closure_kit_first_blocked_step'] or '-'}` `{summary['strict_blind_first_slot_closure_kit_first_blocker'] or '-'}` folder `{summary['strict_blind_first_slot_closure_kit_folder'] or '-'}`",
        f"- strict-blind batch closure runway: `{summary['strict_blind_batch_closure_runway_status'] or '-'}` slots ready/blocked/total `{summary['strict_blind_batch_closure_runway_ready_slot_count']}/{summary['strict_blind_batch_closure_runway_blocked_slot_count']}/{summary['strict_blind_batch_closure_runway_slot_count']}` blocked source/evidence/operator/intake `{summary['strict_blind_batch_closure_runway_source_gate_blocked_count']}/{summary['strict_blind_batch_closure_runway_evidence_blocked_count']}/{summary['strict_blind_batch_closure_runway_operator_blocked_count']}/{summary['strict_blind_batch_closure_runway_intake_blocked_count']}` files present/missing `{summary['strict_blind_batch_closure_runway_file_present_count']}/{summary['strict_blind_batch_closure_runway_file_missing_count']}` operators ready/open `{summary['strict_blind_batch_closure_runway_operator_ready_count']}/{summary['strict_blind_batch_closure_runway_operator_open_count']}` intake filled/missing `{summary['strict_blind_batch_closure_runway_intake_filled_count']}/{summary['strict_blind_batch_closure_runway_intake_missing_count']}` first `{summary['strict_blind_batch_closure_runway_first_blocked_rank']}` `{summary['strict_blind_batch_closure_runway_first_blocked_benchmark_id'] or '-'}` `{summary['strict_blind_batch_closure_runway_first_stage'] or '-'}` `{summary['strict_blind_batch_closure_runway_first_blocker'] or '-'}`",
        f"- historical seed ablation candidates: `{summary['historical_seed_ablation_candidate_manifests_status'] or '-'}` seeds/manifests/candidate-rows `{summary['historical_seed_ablation_candidate_manifests_seed_count']}/{summary['historical_seed_ablation_candidate_manifests_manifest_count']}/{summary['historical_seed_ablation_candidate_manifests_candidate_row_count']}` selected/native `{summary['historical_seed_ablation_candidate_manifests_selected_present_count']}/{summary['historical_seed_ablation_candidate_manifests_native_present_count']}` baseline/gaps `{summary['historical_seed_ablation_candidate_manifests_baseline_count']}/{summary['historical_seed_ablation_candidate_manifests_layer_gap_count']}` ready/review/core-blocked `{summary['historical_seed_ablation_candidate_manifests_ready_count']}/{summary['historical_seed_ablation_candidate_manifests_operator_review_count']}/{summary['historical_seed_ablation_candidate_manifests_core_blocked_count']}` first `{summary['historical_seed_ablation_candidate_manifests_first_target_id'] or '-'}` `{summary['historical_seed_ablation_candidate_manifests_first_next_action'] or '-'}`",
        f"- historical seed ablation gap repair: `{summary['historical_seed_ablation_gap_repair_plan_status'] or '-'}` seeds/repair-csvs `{summary['historical_seed_ablation_gap_repair_plan_seed_count']}/{summary['historical_seed_ablation_gap_repair_plan_repair_csv_count']}` real/missing-real/top5-decoys/top5-copy `{summary['historical_seed_ablation_gap_repair_plan_real_count']}/{summary['historical_seed_ablation_gap_repair_plan_missing_real_count']}/{summary['historical_seed_ablation_gap_repair_plan_top5_decoy_count']}/{summary['historical_seed_ablation_gap_repair_plan_top5_copy_count']}` ready/gap/core-blocked `{summary['historical_seed_ablation_gap_repair_plan_ready_count']}/{summary['historical_seed_ablation_gap_repair_plan_gap_count']}/{summary['historical_seed_ablation_gap_repair_plan_core_blocked_count']}` first `{summary['historical_seed_ablation_gap_repair_plan_first_target_id'] or '-'}` `{summary['historical_seed_ablation_gap_repair_plan_first_next_action'] or '-'}`",
        f"- historical seed top5 pools: `{summary['historical_seed_top5_candidate_pools_status'] or '-'}` seeds/pools/models `{summary['historical_seed_top5_candidate_pools_seed_count']}/{summary['historical_seed_top5_candidate_pools_pool_count']}/{summary['historical_seed_top5_candidate_pools_candidate_model_count']}` complete/gaps/source-present/source-blocked `{summary['historical_seed_top5_candidate_pools_complete_count']}/{summary['historical_seed_top5_candidate_pools_gap_count']}/{summary['historical_seed_top5_candidate_pools_source_present_count']}/{summary['historical_seed_top5_candidate_pools_blocked_source_count']}` generated `{summary['historical_seed_top5_candidate_pools_generated_perturbation_count']}` first `{summary['historical_seed_top5_candidate_pools_first_target_id'] or '-'}` `{summary['historical_seed_top5_candidate_pools_first_next_action'] or '-'}`",
        f"- historical seed internal scores: `{summary['historical_seed_internal_score_candidates_status'] or '-'}` seeds/candidates/scored `{summary['historical_seed_internal_score_candidates_seed_count']}/{summary['historical_seed_internal_score_candidates_candidate_count']}/{summary['historical_seed_internal_score_candidates_scored_count']}` top5-scored/selected-scores/blocked `{summary['historical_seed_internal_score_candidates_top5_scored_count']}/{summary['historical_seed_internal_score_candidates_selected_score_count']}/{summary['historical_seed_internal_score_candidates_blocked_count']}` first `{summary['historical_seed_internal_score_candidates_first_target_id'] or '-'}` `{summary['historical_seed_internal_score_candidates_first_next_action'] or '-'}`",
        f"- historical seed native metrics: `{summary['historical_seed_native_oracle_metric_candidates_status'] or '-'}` seeds/candidates/metric-ready `{summary['historical_seed_native_oracle_metric_candidates_seed_count']}/{summary['historical_seed_native_oracle_metric_candidates_candidate_count']}/{summary['historical_seed_native_oracle_metric_candidates_metric_count']}` top5/selected/best/blocked `{summary['historical_seed_native_oracle_metric_candidates_top5_ready_count']}/{summary['historical_seed_native_oracle_metric_candidates_selected_count']}/{summary['historical_seed_native_oracle_metric_candidates_best_count']}/{summary['historical_seed_native_oracle_metric_candidates_blocked_count']}` first `{summary['historical_seed_native_oracle_metric_candidates_first_target_id'] or '-'}` `{summary['historical_seed_native_oracle_metric_candidates_first_next_action'] or '-'}`",
        f"- historical seed calibration candidates: `{summary['historical_seed_calibration_candidate_ledgers_status'] or '-'}` seeds/ledgers/models `{summary['historical_seed_calibration_candidate_ledgers_seed_count']}/{summary['historical_seed_calibration_candidate_ledgers_ledger_count']}/{summary['historical_seed_calibration_candidate_ledgers_candidate_model_count']}` top5/selected/rank `{summary['historical_seed_calibration_candidate_ledgers_top5_ready_count']}/{summary['historical_seed_calibration_candidate_ledgers_selected_prediction_count']}/{summary['historical_seed_calibration_candidate_ledgers_selected_rank_candidate_count']}` native/internal `{summary['historical_seed_calibration_candidate_ledgers_native_metric_count']}/{summary['historical_seed_calibration_candidate_ledgers_internal_score_count']}` ready/review/blocked-selected/open-fields `{summary['historical_seed_calibration_candidate_ledgers_ready_count']}/{summary['historical_seed_calibration_candidate_ledgers_operator_review_count']}/{summary['historical_seed_calibration_candidate_ledgers_blocked_selected_prediction_count']}/{summary['historical_seed_calibration_candidate_ledgers_open_field_count']}` first `{summary['historical_seed_calibration_candidate_ledgers_first_target_id'] or '-'}` `{summary['historical_seed_calibration_candidate_ledgers_first_next_action'] or '-'}`",
        f"- historical seed calibration field candidates: `{summary['historical_seed_calibration_field_candidates_status'] or '-'}` seeds/fields/proposed/matching `{summary['historical_seed_calibration_field_candidates_seed_count']}/{summary['historical_seed_calibration_field_candidates_field_count']}/{summary['historical_seed_calibration_field_candidates_proposed_count']}/{summary['historical_seed_calibration_field_candidates_matching_count']}` ready/blocked/conflicts/blocked-fields `{summary['historical_seed_calibration_field_candidates_ready_count']}/{summary['historical_seed_calibration_field_candidates_blocked_row_count']}/{summary['historical_seed_calibration_field_candidates_conflict_count']}/{summary['historical_seed_calibration_field_candidates_blocked_field_count']}` first `{summary['historical_seed_calibration_field_candidates_first_target_id'] or '-'}` `{summary['historical_seed_calibration_field_candidates_first_next_action'] or '-'}`",
        f"- historical seed clearance fill candidates: `{summary['historical_seed_clearance_fill_candidate_packet_status'] or '-'}` seeds/fields/proposed/manual/blocked `{summary['historical_seed_clearance_fill_candidate_packet_seed_count']}/{summary['historical_seed_clearance_fill_candidate_packet_field_count']}/{summary['historical_seed_clearance_fill_candidate_packet_proposed_count']}/{summary['historical_seed_clearance_fill_candidate_packet_operator_required_count']}/{summary['historical_seed_clearance_fill_candidate_packet_blocked_field_count']}` calibration/ablation/no-leak-manual/conflicts `{summary['historical_seed_clearance_fill_candidate_packet_calibration_count']}/{summary['historical_seed_clearance_fill_candidate_packet_ablation_count']}/{summary['historical_seed_clearance_fill_candidate_packet_no_leak_manual_count']}/{summary['historical_seed_clearance_fill_candidate_packet_conflict_count']}` partial/full-ready/blocked rows `{summary['historical_seed_clearance_fill_candidate_packet_partial_row_count']}/{summary['historical_seed_clearance_fill_candidate_packet_full_ready_row_count']}/{summary['historical_seed_clearance_fill_candidate_packet_blocked_row_count']}` first `{summary['historical_seed_clearance_fill_candidate_packet_first_target_id'] or '-'}` `{summary['historical_seed_clearance_fill_candidate_packet_first_next_action'] or '-'}`",
        f"- historical seed clearance execution board: `{summary['historical_seed_clearance_execution_board_status'] or '-'}` seeds/no-leak-only/ablation-repair `{summary['historical_seed_clearance_execution_board_seed_count']}/{summary['historical_seed_clearance_execution_board_no_leak_only_count']}/{summary['historical_seed_clearance_execution_board_ablation_repair_count']}` no-leak/proposed/calibration/ablation/blocked-ablation `{summary['historical_seed_clearance_execution_board_operator_no_leak_field_count']}/{summary['historical_seed_clearance_execution_board_proposed_field_count']}/{summary['historical_seed_clearance_execution_board_calibration_count']}/{summary['historical_seed_clearance_execution_board_ablation_count']}/{summary['historical_seed_clearance_execution_board_blocked_ablation_count']}` first `{summary['historical_seed_clearance_execution_board_first_target_id'] or '-'}` `{summary['historical_seed_clearance_execution_board_first_status'] or '-'}` `{summary['historical_seed_clearance_execution_board_first_next_action'] or '-'}` folder `{summary['historical_seed_clearance_execution_board_first_folder'] or '-'}`",
        f"- historical seed first clearance kit: `{summary['historical_seed_first_clearance_operator_kit_status'] or '-'}` target `{summary['historical_seed_first_clearance_operator_kit_target_id'] or '-'}` benchmark `{summary['historical_seed_first_clearance_operator_kit_benchmark_id'] or '-'}` no-leak/ready/weak `{summary['historical_seed_first_clearance_operator_kit_no_leak_count']}/{summary['historical_seed_first_clearance_operator_kit_ready_count']}/{summary['historical_seed_first_clearance_operator_kit_weak_count']}` calibration/ablation `{summary['historical_seed_first_clearance_operator_kit_calibration_count']}/{summary['historical_seed_first_clearance_operator_kit_ablation_count']}` preview `{summary['historical_seed_first_clearance_operator_kit_preview_status'] or '-'}` intake `{summary['historical_seed_first_clearance_operator_kit_intake_csv'] or '-'}`",
        f"- historical seed first clearance no-leak gate: `{summary['historical_seed_first_clearance_no_leak_gate_status'] or '-'}` target `{summary['historical_seed_first_clearance_no_leak_gate_target_id'] or '-'}` benchmark `{summary['historical_seed_first_clearance_no_leak_gate_benchmark_id'] or '-'}` fields ready/blocked/total `{summary['historical_seed_first_clearance_no_leak_gate_ready_count']}/{summary['historical_seed_first_clearance_no_leak_gate_blocked_count']}/{summary['historical_seed_first_clearance_no_leak_gate_field_count']}` values present/missing `{summary['historical_seed_first_clearance_no_leak_gate_value_present_count']}/{summary['historical_seed_first_clearance_no_leak_gate_value_missing_count']}` clearance present/missing `{summary['historical_seed_first_clearance_no_leak_gate_clearance_present_count']}/{summary['historical_seed_first_clearance_no_leak_gate_clearance_missing_count']}` policy pass/blocked `{summary['historical_seed_first_clearance_no_leak_gate_policy_pass_count']}/{summary['historical_seed_first_clearance_no_leak_gate_policy_blocked_count']}` first `{summary['historical_seed_first_clearance_no_leak_gate_first_blocked_field'] or '-'}` `{summary['historical_seed_first_clearance_no_leak_gate_first_blocker'] or '-'}` intake `{summary['historical_seed_first_clearance_no_leak_gate_intake_csv'] or '-'}`",
        f"- historical seed first clearance no-leak evidence packet: `{summary['historical_seed_first_clearance_no_leak_evidence_packet_status'] or '-'}` target `{summary['historical_seed_first_clearance_no_leak_evidence_packet_target_id'] or '-'}` benchmark `{summary['historical_seed_first_clearance_no_leak_evidence_packet_benchmark_id'] or '-'}` fields ready/open/total `{summary['historical_seed_first_clearance_no_leak_evidence_packet_ready_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_packet_open_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_packet_field_count']}` stubs/weak `{summary['historical_seed_first_clearance_no_leak_evidence_packet_stub_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_packet_weak_count']}` first `{summary['historical_seed_first_clearance_no_leak_evidence_packet_first_open_field'] or '-'}` `{summary['historical_seed_first_clearance_no_leak_evidence_packet_first_open_kind'] or '-'}` folder `{summary['historical_seed_first_clearance_no_leak_evidence_packet_folder'] or '-'}` template `{summary['historical_seed_first_clearance_no_leak_evidence_packet_template_csv'] or '-'}`",
        f"- historical seed first clearance no-leak evidence review gate: `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_status'] or '-'}` target `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_target_id'] or '-'}` benchmark `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_benchmark_id'] or '-'}` fields ready/blocked/total `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_ready_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_blocked_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_field_count']}` template missing value/clearance/operator `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_template_value_missing_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_template_clearance_missing_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_template_operator_missing_count']}` stubs present/evidence-missing `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_stub_present_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_stub_evidence_missing_count']}` policy pass/blocked `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_policy_pass_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_policy_blocked_count']}` first `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_first_blocked_field'] or '-'}` `{summary['historical_seed_first_clearance_no_leak_evidence_review_gate_first_blocker'] or '-'}`",
        f"- historical seed first clearance no-leak evidence sync plan: `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_status'] or '-'}` mode `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_mode'] or '-'}` review `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_review_status'] or '-'}` target `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_target_id'] or '-'}` benchmark `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_benchmark_id'] or '-'}` actions ready/blocked/applied/total `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_ready_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_blocked_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_applied_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_action_count']}` review ready/blocked `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_review_ready_count']}/{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_review_blocked_count']}` first `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_first_blocked_field'] or '-'}` `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_first_blocker'] or '-'}` intake `{summary['historical_seed_first_clearance_no_leak_evidence_sync_plan_destination_intake_csv'] or '-'}`",
        f"- historical seed first clearance closure board: `{summary['historical_seed_first_clearance_closure_board_status'] or '-'}` target `{summary['historical_seed_first_clearance_closure_board_target_id'] or '-'}` benchmark `{summary['historical_seed_first_clearance_closure_board_benchmark_id'] or '-'}` stages ready/blocked/total `{summary['historical_seed_first_clearance_closure_board_ready_count']}/{summary['historical_seed_first_clearance_closure_board_blocked_count']}/{summary['historical_seed_first_clearance_closure_board_stage_count']}` first `{summary['historical_seed_first_clearance_closure_board_first_stage'] or '-'}` `{summary['historical_seed_first_clearance_closure_board_first_stage_status'] or '-'}` `{summary['historical_seed_first_clearance_closure_board_first_blocker'] or '-'}` kit/gate/evidence/review/sync `{summary['historical_seed_first_clearance_closure_board_operator_kit_status'] or '-'}` `{summary['historical_seed_first_clearance_closure_board_no_leak_gate_status'] or '-'}` `{summary['historical_seed_first_clearance_closure_board_evidence_packet_status'] or '-'}` `{summary['historical_seed_first_clearance_closure_board_evidence_review_status'] or '-'}` `{summary['historical_seed_first_clearance_closure_board_evidence_sync_status'] or '-'}`",
        f"- historical seed clearance to identity intake sync: `{summary['historical_seed_clearance_to_identity_intake_sync_status'] or '-'}` mode `{summary['historical_seed_clearance_to_identity_intake_sync_apply_mode'] or '-'}` seed eligible/total `{summary['historical_seed_clearance_to_identity_intake_sync_eligible_count']}/{summary['historical_seed_clearance_to_identity_intake_sync_seed_row_count']}` intake ready/waiting/blocked/total `{summary['historical_seed_clearance_to_identity_intake_sync_ready_count']}/{summary['historical_seed_clearance_to_identity_intake_sync_waiting_count']}/{summary['historical_seed_clearance_to_identity_intake_sync_blocked_count']}/{summary['historical_seed_clearance_to_identity_intake_sync_intake_row_count']}` applied `{summary['historical_seed_clearance_to_identity_intake_sync_applied_count']}` first `{summary['historical_seed_clearance_to_identity_intake_sync_first_next_action'] or '-'}`",
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
    parser.add_argument(
        "--protein-object-library-completion-audit-json",
        default=DEFAULT_PROTEIN_OBJECT_LIBRARY_COMPLETION_AUDIT_JSON,
    )
    parser.add_argument(
        "--protein-object-library-navigation-catalog-json",
        default=DEFAULT_PROTEIN_OBJECT_LIBRARY_NAVIGATION_CATALOG_JSON,
    )
    parser.add_argument("--raw-ranked-model-quarantine-json", default=DEFAULT_RAW_RANKED_MODEL_QUARANTINE_JSON)
    parser.add_argument("--win-gap-closure-json", default=DEFAULT_WIN_GAP_CLOSURE_JSON)
    parser.add_argument("--win-tier-goal-scorecard-json", default=DEFAULT_WIN_TIER_GOAL_SCORECARD_JSON)
    parser.add_argument("--win-tier-metric-surface-contract-json", default=DEFAULT_WIN_TIER_METRIC_SURFACE_CONTRACT_JSON)
    parser.add_argument("--win-tier-critical-path-board-json", default=DEFAULT_WIN_TIER_CRITICAL_PATH_BOARD_JSON)
    parser.add_argument(
        "--organic-ligand-slot-candidate-packet-json",
        default=DEFAULT_ORGANIC_LIGAND_SLOT_CANDIDATE_PACKET_JSON,
    )
    parser.add_argument(
        "--organic-ligand-slot-promotion-action-board-json",
        default=DEFAULT_ORGANIC_LIGAND_SLOT_PROMOTION_ACTION_BOARD_JSON,
    )
    parser.add_argument("--active-scope-decision-json", default=DEFAULT_ACTIVE_SCOPE_DECISION_JSON)
    parser.add_argument("--organizer-notice-packet-json", default=DEFAULT_ORGANIZER_NOTICE_PACKET_JSON)
    parser.add_argument(
        "--massivefold-external-pool-intake-json",
        default=DEFAULT_MASSIVEFOLD_EXTERNAL_POOL_INTAKE_JSON,
    )
    parser.add_argument(
        "--rna-hybrid-massivefold-priority-queue-json",
        default=DEFAULT_RNA_HYBRID_MASSIVEFOLD_PRIORITY_QUEUE_JSON,
    )
    parser.add_argument(
        "--protein-complex-massivefold-priority-queue-json",
        default=DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_PRIORITY_QUEUE_JSON,
    )
    parser.add_argument(
        "--massivefold-acquisition-verification-board-json",
        default=DEFAULT_MASSIVEFOLD_ACQUISITION_VERIFICATION_BOARD_JSON,
    )
    parser.add_argument(
        "--protein-complex-massivefold-acquisition-verification-board-json",
        default=DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_ACQUISITION_VERIFICATION_BOARD_JSON,
    )
    parser.add_argument(
        "--massivefold-model-pool-index-json",
        default=DEFAULT_MASSIVEFOLD_MODEL_POOL_INDEX_JSON,
    )
    parser.add_argument(
        "--massivefold-representative-viewer-packet-json",
        default=DEFAULT_MASSIVEFOLD_REPRESENTATIVE_VIEWER_PACKET_JSON,
    )
    parser.add_argument(
        "--massivefold-representative-rerank-packet-json",
        default=DEFAULT_MASSIVEFOLD_REPRESENTATIVE_RERANK_PACKET_JSON,
    )
    parser.add_argument(
        "--massivefold-rna-model-selection-coverage-json",
        default=DEFAULT_MASSIVEFOLD_RNA_MODEL_SELECTION_COVERAGE_JSON,
    )
    parser.add_argument(
        "--protein-complex-massivefold-model-selection-coverage-json",
        default=DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_MODEL_SELECTION_COVERAGE_JSON,
    )
    parser.add_argument("--capri-round65-readiness-json", default=DEFAULT_CAPRI_ROUND65_READINESS_JSON)
    parser.add_argument("--capri-round65-format-preflight-json", default=DEFAULT_CAPRI_ROUND65_FORMAT_PREFLIGHT_JSON)
    parser.add_argument("--input-scaffold-json", default=DEFAULT_INPUT_SCAFFOLD_JSON)
    parser.add_argument("--input-inventory-json", default=DEFAULT_INPUT_INVENTORY_JSON)
    parser.add_argument("--operator-dashboard-json", default=DEFAULT_OPERATOR_DASHBOARD_JSON)
    parser.add_argument("--historical-identity-seed-inventory-json", default=DEFAULT_HISTORICAL_IDENTITY_SEED_INVENTORY_JSON)
    parser.add_argument("--historical-identity-seed-clearance-json", default=DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_JSON)
    parser.add_argument(
        "--historical-identity-seed-clearance-action-bundle-json",
        default=DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_ACTION_BUNDLE_JSON,
    )
    parser.add_argument(
        "--historical-identity-seed-clearance-field-board-json",
        default=DEFAULT_HISTORICAL_IDENTITY_SEED_CLEARANCE_FIELD_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-no-leak-provenance-dossiers-json",
        default=DEFAULT_HISTORICAL_SEED_NO_LEAK_PROVENANCE_DOSSIERS_JSON,
    )
    parser.add_argument(
        "--historical-seed-no-leak-gap-repair-plan-json",
        default=DEFAULT_HISTORICAL_SEED_NO_LEAK_GAP_REPAIR_PLAN_JSON,
    )
    parser.add_argument(
        "--historical-seed-current-target-prefill-json",
        default=DEFAULT_HISTORICAL_SEED_CURRENT_TARGET_PREFILL_JSON,
    )
    parser.add_argument(
        "--historical-seed-native-authority-audit-json",
        default=DEFAULT_HISTORICAL_SEED_NATIVE_AUTHORITY_AUDIT_JSON,
    )
    parser.add_argument(
        "--historical-seed-native-replacement-candidates-json",
        default=DEFAULT_HISTORICAL_SEED_NATIVE_REPLACEMENT_CANDIDATES_JSON,
    )
    parser.add_argument(
        "--historical-seed-complex-source-authority-candidates-json",
        default=DEFAULT_HISTORICAL_SEED_COMPLEX_SOURCE_AUTHORITY_CANDIDATES_JSON,
    )
    parser.add_argument(
        "--historical-seed-chronology-candidate-board-json",
        default=DEFAULT_HISTORICAL_SEED_CHRONOLOGY_CANDIDATE_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-authoritative-chronology-audit-json",
        default=DEFAULT_HISTORICAL_SEED_AUTHORITATIVE_CHRONOLOGY_AUDIT_JSON,
    )
    parser.add_argument(
        "--historical-seed-lane-decision-packet-json",
        default=DEFAULT_HISTORICAL_SEED_LANE_DECISION_PACKET_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-queue-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_QUEUE_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-intake-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_INTAKE_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-evidence-dropzones-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_DROPZONES_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-evidence-action-board-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_ACTION_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-evidence-quality-audit-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_QUALITY_AUDIT_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-evidence-import-gate-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_IMPORT_GATE_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-operator-value-gate-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_OPERATOR_VALUE_GATE_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-operator-action-board-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_OPERATOR_ACTION_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-promotion-gate-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_PROMOTION_GATE_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-cycle-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_CYCLE_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-first-slot-kit-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_KIT_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-first-slot-local-candidate-board-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_LOCAL_CANDIDATE_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-first-slot-candidate-repair-board-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_CANDIDATE_REPAIR_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-first-slot-repair-feasibility-board-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_REPAIR_FEASIBILITY_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-first-slot-source-route-board-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_SOURCE_ROUTE_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-strict-blind-replacement-first-slot-official-archive-source-candidates-json",
        default=DEFAULT_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_OFFICIAL_ARCHIVE_SOURCE_CANDIDATES_JSON,
    )
    parser.add_argument(
        "--historical-seed-official-archive-baseline-lane-json",
        default=DEFAULT_HISTORICAL_SEED_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON,
    )
    parser.add_argument(
        "--strict-blind-first-slot-source-bridge-json",
        default=DEFAULT_STRICT_BLIND_FIRST_SLOT_SOURCE_BRIDGE_JSON,
    )
    parser.add_argument(
        "--strict-blind-internal-prediction-source-audit-json",
        default=DEFAULT_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_AUDIT_JSON,
    )
    parser.add_argument(
        "--strict-blind-internal-prediction-source-gate-json",
        default=DEFAULT_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_GATE_JSON,
    )
    parser.add_argument(
        "--strict-blind-source-gate-field-board-json",
        default=DEFAULT_STRICT_BLIND_SOURCE_GATE_FIELD_BOARD_JSON,
    )
    parser.add_argument(
        "--strict-blind-source-gate-operator-packet-json",
        default=DEFAULT_STRICT_BLIND_SOURCE_GATE_OPERATOR_PACKET_JSON,
    )
    parser.add_argument(
        "--strict-blind-source-gate-source-request-packet-json",
        default=DEFAULT_STRICT_BLIND_SOURCE_GATE_SOURCE_REQUEST_PACKET_JSON,
    )
    parser.add_argument(
        "--strict-blind-source-request-fulfillment-gate-json",
        default=DEFAULT_STRICT_BLIND_SOURCE_REQUEST_FULFILLMENT_GATE_JSON,
    )
    parser.add_argument(
        "--strict-blind-source-request-operator-fill-worklist-json",
        default=DEFAULT_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_FILL_WORKLIST_JSON,
    )
    parser.add_argument(
        "--strict-blind-source-request-operator-sync-plan-json",
        default=DEFAULT_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_SYNC_PLAN_JSON,
    )
    parser.add_argument(
        "--strict-blind-source-request-closure-board-json",
        default=DEFAULT_STRICT_BLIND_SOURCE_REQUEST_CLOSURE_BOARD_JSON,
    )
    parser.add_argument(
        "--strict-blind-internal-prediction-source-apply-plan-json",
        default=DEFAULT_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_APPLY_PLAN_JSON,
    )
    parser.add_argument(
        "--strict-blind-first-slot-closure-kit-json",
        default=DEFAULT_STRICT_BLIND_FIRST_SLOT_CLOSURE_KIT_JSON,
    )
    parser.add_argument(
        "--strict-blind-batch-closure-runway-json",
        default=DEFAULT_STRICT_BLIND_BATCH_CLOSURE_RUNWAY_JSON,
    )
    parser.add_argument(
        "--historical-seed-ablation-candidate-manifests-json",
        default=DEFAULT_HISTORICAL_SEED_ABLATION_CANDIDATE_MANIFESTS_JSON,
    )
    parser.add_argument(
        "--historical-seed-ablation-gap-repair-plan-json",
        default=DEFAULT_HISTORICAL_SEED_ABLATION_GAP_REPAIR_PLAN_JSON,
    )
    parser.add_argument(
        "--historical-seed-top5-candidate-pools-json",
        default=DEFAULT_HISTORICAL_SEED_TOP5_CANDIDATE_POOLS_JSON,
    )
    parser.add_argument(
        "--historical-seed-internal-score-candidates-json",
        default=DEFAULT_HISTORICAL_SEED_INTERNAL_SCORE_CANDIDATES_JSON,
    )
    parser.add_argument(
        "--historical-seed-native-oracle-metric-candidates-json",
        default=DEFAULT_HISTORICAL_SEED_NATIVE_ORACLE_METRIC_CANDIDATES_JSON,
    )
    parser.add_argument(
        "--historical-seed-calibration-candidate-ledgers-json",
        default=DEFAULT_HISTORICAL_SEED_CALIBRATION_CANDIDATE_LEDGERS_JSON,
    )
    parser.add_argument(
        "--historical-seed-calibration-field-candidates-json",
        default=DEFAULT_HISTORICAL_SEED_CALIBRATION_FIELD_CANDIDATES_JSON,
    )
    parser.add_argument(
        "--historical-seed-clearance-fill-candidate-packet-json",
        default=DEFAULT_HISTORICAL_SEED_CLEARANCE_FILL_CANDIDATE_PACKET_JSON,
    )
    parser.add_argument(
        "--historical-seed-clearance-execution-board-json",
        default=DEFAULT_HISTORICAL_SEED_CLEARANCE_EXECUTION_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-first-clearance-operator-kit-json",
        default=DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_OPERATOR_KIT_JSON,
    )
    parser.add_argument(
        "--historical-seed-first-clearance-no-leak-gate-json",
        default=DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_GATE_JSON,
    )
    parser.add_argument(
        "--historical-seed-first-clearance-no-leak-evidence-packet-json",
        default=DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_PACKET_JSON,
    )
    parser.add_argument(
        "--historical-seed-first-clearance-no-leak-evidence-review-gate-json",
        default=DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_REVIEW_GATE_JSON,
    )
    parser.add_argument(
        "--historical-seed-first-clearance-no-leak-evidence-sync-plan-json",
        default=DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_SYNC_PLAN_JSON,
    )
    parser.add_argument(
        "--historical-seed-first-clearance-closure-board-json",
        default=DEFAULT_HISTORICAL_SEED_FIRST_CLEARANCE_CLOSURE_BOARD_JSON,
    )
    parser.add_argument(
        "--historical-seed-clearance-to-identity-intake-sync-json",
        default=DEFAULT_HISTORICAL_SEED_CLEARANCE_TO_IDENTITY_INTAKE_SYNC_JSON,
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
