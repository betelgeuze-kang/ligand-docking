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
DEFAULT_COMPETITIVE_EVIDENCE_INTAKE_JSON = "casp17/casp17_competitive_floor_evidence_intake_current.json"
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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
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
    competitive_evidence_intake_payload = _read_json(args.competitive_evidence_intake_json)
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
    competitive_evidence_intake_summary = _summary(competitive_evidence_intake_payload)
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
        f"- competitive evidence intake: `{summary['competitive_evidence_intake_status'] or '-'}` actions `{summary['competitive_evidence_intake_action_count']}` patch candidates `{summary['competitive_evidence_intake_patch_candidate_count']}` awaiting files/values `{summary['competitive_evidence_intake_awaiting_file_count']}/{summary['competitive_evidence_intake_awaiting_value_count']}`",
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
    parser.add_argument("--competitive-evidence-intake-json", default=DEFAULT_COMPETITIVE_EVIDENCE_INTAKE_JSON)
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
