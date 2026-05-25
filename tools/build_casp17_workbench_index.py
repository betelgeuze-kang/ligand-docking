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
DEFAULT_WIN_GAP_CLOSURE_JSON = "runs/casp17_win_gap_closure_packet_current.json"
DEFAULT_INPUT_SCAFFOLD_JSON = "runs/casp17_win_tier_benchmark_input_scaffold_current.json"
DEFAULT_INPUT_INVENTORY_JSON = "runs/casp17_win_tier_benchmark_input_inventory_current.json"
DEFAULT_OPERATOR_DASHBOARD_JSON = "runs/casp17_win_tier_benchmark_operator_dashboard_current.json"
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
DEFAULT_COMPETITIVE_TARGET_IDENTITY_DISCOVERY_JSON = (
    "casp17/casp17_competitive_floor_target_identity_discovery_packet_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_QUEUE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_queue_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_WORKORDER_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_MANIFEST_SYNC_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.json"
)
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_WORKORDER_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
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
    closure_payload = _read_json(args.win_gap_closure_json)
    scaffold_payload = _read_json(args.input_scaffold_json)
    inventory_payload = _read_json(args.input_inventory_json)
    dashboard_payload = _read_json(args.operator_dashboard_json)
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
    competitive_target_identity_discovery_payload = _read_json(args.competitive_target_identity_discovery_json)
    competitive_target_identity_clearance_payload = _read_json(args.competitive_target_identity_clearance_queue_json)
    competitive_target_identity_clearance_workorder_payload = _read_json(
        args.competitive_target_identity_clearance_workorder_json
    )
    competitive_target_identity_clearance_manifest_sync_payload = _read_json(
        args.competitive_target_identity_clearance_manifest_sync_json
    )
    competitive_target_identity_clearance_workorder_audit_payload = _read_json(
        args.competitive_target_identity_clearance_workorder_audit_json
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
    closure_summary = _summary(closure_payload)
    scaffold_summary = _summary(scaffold_payload)
    inventory_summary = _summary(inventory_payload)
    dashboard_summary = _summary(dashboard_payload)
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
    competitive_target_identity_discovery_summary = _summary(competitive_target_identity_discovery_payload)
    competitive_target_identity_clearance_summary = _summary(competitive_target_identity_clearance_payload)
    competitive_target_identity_clearance_workorder_summary = _summary(
        competitive_target_identity_clearance_workorder_payload
    )
    competitive_target_identity_clearance_manifest_sync_summary = _summary(
        competitive_target_identity_clearance_manifest_sync_payload
    )
    competitive_target_identity_clearance_workorder_audit_summary = _summary(
        competitive_target_identity_clearance_workorder_audit_payload
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
            blockers=_text(target_object_folder_audit_summary.get("first_blocked_blockers")),
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
        "target_object_viewer_smoke_status": _text(target_object_viewer_smoke_summary.get("smoke_status")),
        "target_object_viewer_smoke_pass_count": _int(target_object_viewer_smoke_summary.get("pass_count")),
        "target_object_viewer_smoke_total": _int(target_object_viewer_smoke_summary.get("object_row_count")),
        "benchmark_rows_ready_count": benchmark_rows_ready,
        "benchmark_rows_total": benchmark_rows_total,
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
        f"- generated: `{summary['generated_at_local']}`",
        f"- workbench_status: `{summary['workbench_status']}`",
        f"- target model folders: `{summary['target_model_ready_count']}/{summary['target_model_count']}`",
        f"- target object folders: `{summary['target_model_object_count']}`",
        f"- target object projections: `{summary['target_model_object_projection_count']}`",
        f"- target object viewers: `{summary['target_model_object_viewer_count']}`",
        f"- target object folder audit: `{summary['target_object_folder_audit_status'] or '-'}` rows `{summary['target_object_folder_audit_pass_count']}/{summary['target_object_folder_audit_total']}` chain isolation `{summary['target_object_folder_chain_isolation_pass_count']}/{summary['target_object_folder_audit_total']}`",
        f"- target object viewer smoke: `{summary['target_object_viewer_smoke_status'] or '-'}` rows `{summary['target_object_viewer_smoke_pass_count']}/{summary['target_object_viewer_smoke_total']}`",
        f"- benchmark rows ready/total: `{summary['benchmark_rows_ready_count']}/{summary['benchmark_rows_total']}`",
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
        f"- competitive identity source repair: `{summary['competitive_identity_source_repair_status'] or '-'}` actions `{summary['competitive_identity_source_repair_action_count']}` blocked sources `{summary['competitive_identity_source_repair_blocked_source_count']}` phase identity/core/provenance/ablation/calibration `{summary['competitive_identity_source_repair_target_identity_count']}/{summary['competitive_identity_source_repair_core_file_count']}/{summary['competitive_identity_source_repair_provenance_count']}/{summary['competitive_identity_source_repair_ablation_count']}/{summary['competitive_identity_source_repair_calibration_count']}` first phase `{summary['competitive_identity_source_repair_first_phase'] or '-'}`",
        f"- competitive target identity discovery: `{summary['competitive_target_identity_discovery_status'] or '-'}` discovered `{summary['competitive_target_identity_discovery_count']}` operator/current/closed/unknown/synthetic `{summary['competitive_target_identity_operator_review_count']}/{summary['competitive_target_identity_open_current_count']}/{summary['competitive_target_identity_closed_watchlist_count']}/{summary['competitive_target_identity_unknown_local_count']}/{summary['competitive_target_identity_synthetic_count']}` ready intake `{summary['competitive_target_identity_ready_for_intake_count']}`",
        f"- competitive target identity clearance: `{summary['competitive_target_identity_clearance_status'] or '-'}` review `{summary['competitive_target_identity_clearance_review_count']}` prediction/TS/native/provenance `{summary['competitive_target_identity_clearance_prediction_count']}/{summary['competitive_target_identity_clearance_ts_prediction_count']}/{summary['competitive_target_identity_clearance_native_count']}/{summary['competitive_target_identity_clearance_provenance_count']}` ready `{summary['competitive_target_identity_clearance_ready_count']}` awaiting prediction/native/no-leak `{summary['competitive_target_identity_clearance_awaiting_prediction_count']}/{summary['competitive_target_identity_clearance_awaiting_native_count']}/{summary['competitive_target_identity_clearance_awaiting_no_leak_count']}`",
        f"- competitive target identity clearance workorders: `{summary['competitive_target_identity_clearance_workorder_status'] or '-'}` workorders `{summary['competitive_target_identity_clearance_workorder_count']}` ready/native+provenance/native/provenance `{summary['competitive_target_identity_clearance_workorder_ready_count']}/{summary['competitive_target_identity_clearance_workorder_native_provenance_count']}/{summary['competitive_target_identity_clearance_workorder_native_count']}/{summary['competitive_target_identity_clearance_workorder_provenance_count']}` dropzones/templates/stubs `{summary['competitive_target_identity_clearance_workorder_dropzone_count']}/{summary['competitive_target_identity_clearance_workorder_template_count']}/{summary['competitive_target_identity_clearance_workorder_stub_count']}` preserved templates/stubs `{summary['competitive_target_identity_clearance_workorder_template_preserved_count']}/{summary['competitive_target_identity_clearance_workorder_stub_preserved_count']}` refreshed templates/stubs `{summary['competitive_target_identity_clearance_workorder_template_refreshed_count']}/{summary['competitive_target_identity_clearance_workorder_stub_refreshed_count']}`",
        f"- competitive target identity clearance manifest sync: `{summary['competitive_target_identity_clearance_manifest_sync_status'] or '-'}` rows ready/awaiting/blocked/synced `{summary['competitive_target_identity_clearance_manifest_sync_row_count']}/{summary['competitive_target_identity_clearance_manifest_sync_ready_count']}/{summary['competitive_target_identity_clearance_manifest_sync_awaiting_count']}/{summary['competitive_target_identity_clearance_manifest_sync_blocked_count']}/{summary['competitive_target_identity_clearance_manifest_sync_synced_count']}` changed/applied `{summary['competitive_target_identity_clearance_manifest_sync_changed_count']}/{summary['competitive_target_identity_clearance_manifest_sync_applied_count']}`",
        f"- competitive target identity clearance workorder audit: `{summary['competitive_target_identity_clearance_workorder_audit_status'] or '-'}` pass/blocked/total `{summary['competitive_target_identity_clearance_workorder_audit_pass_count']}/{summary['competitive_target_identity_clearance_workorder_audit_blocked_count']}/{summary['competitive_target_identity_clearance_workorder_audit_target_count']}` prediction/native/provenance/evidence/manifest `{summary['competitive_target_identity_clearance_workorder_audit_prediction_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_count']}/{summary['competitive_target_identity_clearance_workorder_audit_provenance_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_count']}/{summary['competitive_target_identity_clearance_workorder_audit_manifest_count']}` native protein-atoms/coordinate-valid `{summary['competitive_target_identity_clearance_workorder_audit_native_protein_atom_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_coordinate_valid_count']}` evidence verified/content-blocked/blocked/waiting `{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_verified_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_content_blocked_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_blocked_count']}/{summary['competitive_target_identity_clearance_workorder_audit_evidence_ref_waiting_count']}` manifest/provenance matched/mismatches `{summary['competitive_target_identity_clearance_workorder_audit_manifest_provenance_matched_count']}/{summary['competitive_target_identity_clearance_workorder_audit_manifest_provenance_mismatch_count']}` native/prediction distinct/same/waiting `{summary['competitive_target_identity_clearance_workorder_audit_native_prediction_distinct_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_prediction_same_count']}/{summary['competitive_target_identity_clearance_workorder_audit_native_prediction_waiting_count']}`",
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
    parser.add_argument("--win-gap-closure-json", default=DEFAULT_WIN_GAP_CLOSURE_JSON)
    parser.add_argument("--input-scaffold-json", default=DEFAULT_INPUT_SCAFFOLD_JSON)
    parser.add_argument("--input-inventory-json", default=DEFAULT_INPUT_INVENTORY_JSON)
    parser.add_argument("--operator-dashboard-json", default=DEFAULT_OPERATOR_DASHBOARD_JSON)
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
        "--competitive-target-identity-clearance-manifest-sync-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_MANIFEST_SYNC_JSON,
    )
    parser.add_argument(
        "--competitive-target-identity-clearance-workorder-audit-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_WORKORDER_AUDIT_JSON,
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
