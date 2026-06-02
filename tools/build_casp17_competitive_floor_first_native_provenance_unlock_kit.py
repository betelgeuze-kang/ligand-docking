#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BRIDGE_JSON = "casp17/casp17_competitive_floor_native_provenance_metric_unlock_bridge_current.json"
DEFAULT_OPERATOR_PACKET_JSON = "casp17/casp17_competitive_floor_native_provenance_operator_packet_current.json"
DEFAULT_OPERATOR_PACKET_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_native_provenance_operator_packet_completion_audit_current.json"
)
DEFAULT_WORKORDER_AUDIT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
DEFAULT_ACTION_BUNDLE_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_action_bundle_current.json"
DEFAULT_OPERATOR_INTAKE_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.csv"
DEFAULT_OUT_DIR = "casp17/competitive_floor_first_native_provenance_unlock_kit"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_first_native_provenance_unlock_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_first_native_provenance_unlock_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_FIRST_NATIVE_PROVENANCE_UNLOCK_KIT.md"

INTAKE_COLUMNS = [
    "target_id",
    "native_source_pdb",
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "notes",
]
ACTION_COLUMNS = [
    "action_rank",
    "lane",
    "required_field",
    "required_artifact",
    "action_status",
    "blockers",
    "recommended_action",
    "unlocks",
    "verification_command",
    "action_md",
    "request_md",
]
ROW_COLUMNS = [
    "target_id",
    "target_name",
    "kit_status",
    "kit_folder",
    "readme_md",
    "operator_fill_intake_csv",
    "required_actions_csv",
    "rerun_commands_md",
    "kit_manifest_json",
    "required_field_count",
    "required_action_count",
    "action_bundle_action_count",
    "packet_file_pass",
    "metric_runway_ready",
    "workorder_audit_pass",
    "prediction_present",
    "ts_prediction_present",
    "native_file_present",
    "native_dropzone_path_present",
    "provenance_template_present",
    "manifest_stub_present",
    "metric_runway_present",
    "workorder_present",
    "provenance_ready",
    "evidence_ref_verified",
    "identity_discovery_cleared",
    "competitive_proof_eligible",
    "author_serialized",
    "coordinate_copy_count",
    "prediction_pdb",
    "ts_prediction_pdb",
    "native_dropzone_pdb",
    "provenance_template_csv",
    "manifest_stub_csv",
    "packet_folder",
    "packet_actions_csv",
    "packet_native_candidates_csv",
    "metric_runway_md",
    "first_blocker",
    "blockers",
    "next_action",
]
RERUN_COMMANDS = [
    "python3 tools/build_casp17_competitive_floor_target_identity_clearance_operator_intake.py",
    "python3 tools/sync_casp17_competitive_floor_target_identity_clearance_manifest_stub.py",
    "python3 tools/build_casp17_competitive_floor_target_identity_clearance_workorder_audit.py",
    "python3 tools/build_casp17_competitive_floor_target_identity_metric_runway.py",
    "python3 tools/build_casp17_competitive_floor_native_provenance_operator_packet.py",
    "python3 tools/build_casp17_competitive_floor_native_provenance_operator_packet_completion_audit.py",
    "python3 tools/build_casp17_competitive_floor_native_provenance_metric_unlock_bridge.py",
    "python3 tools/build_casp17_competitive_floor_first_native_provenance_unlock_kit.py",
    "python3 tools/build_casp17_workbench_index.py",
]
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor first native/provenance unlock operator kit only. It collects the first blocked "
    "target's native dropzone, no-leak evidence, provenance intake fields, manifest stub, action links, and rerun "
    "commands for operator fill. It does not fetch native structures, copy coordinates, fill or trust provenance, "
    "clear no-leak evidence, compute native accuracy, serialize a CASP author code, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    text = str(path_like or "").strip()
    if not text:
        return ""
    path = _resolve(text).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return slug[:140] or "target"


def _bool_text(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "pass", "ready", "cleared", "verified", "present"}


def _status_bool(row: dict[str, Any], key: str, expected: str) -> bool:
    return _text(row.get(key)) == expected


def _coordinate_file_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".pdb", ".cif"})


def _select_target_id(args: argparse.Namespace, bridge_summary: dict[str, Any], bridge_rows: list[dict[str, Any]]) -> str:
    explicit = _text(args.target_id).upper()
    if explicit:
        return explicit
    first_blocked = _text(bridge_summary.get("first_blocked_target_id")).upper()
    if first_blocked:
        return first_blocked
    for row in bridge_rows:
        if _text(row.get("bridge_status")) != "ready_for_metric_execution":
            return _text(row.get("target_id")).upper()
    return ""


def _existing_intake_row(path_like: str | Path, target_id: str) -> dict[str, str]:
    for row in _read_csv_rows(path_like):
        if _text(row.get("target_id")).upper() == target_id:
            return row
    return {}


def _operator_fill_row(existing: dict[str, str], target_id: str) -> dict[str, str]:
    defaults = {
        "target_id": target_id,
        "native_source_pdb": "REQUIRED_OPERATOR_NATIVE_PDB_SOURCE_PATH",
        "no_leak_evidence_ref": "REQUIRED_LOCAL_NO_LEAK_EVIDENCE_FILE",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "operator": "REQUIRED_OPERATOR_ID",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "notes": "Fill locally, then rerun the listed CASP17 competitive-floor commands.",
    }
    return {column: _text(existing.get(column)) or defaults[column] for column in INTAKE_COLUMNS}


def _target_action_rows(action_rows: list[dict[str, Any]], target_id: str) -> list[dict[str, Any]]:
    rows = [row for row in action_rows if _text(row.get("target_id")).upper() == target_id]
    return sorted(rows, key=lambda row: _int(row.get("action_rank")))


def _kit_paths(out_dir: str | Path, target_id: str, target_name: str) -> dict[str, str]:
    folder = _resolve(out_dir) / _safe_slug(f"{target_id}_{target_name}")
    return {
        "kit_folder": _artifact(folder),
        "readme_md": _artifact(folder / "README.md"),
        "operator_fill_intake_csv": _artifact(folder / "operator_fill_intake.csv"),
        "required_actions_csv": _artifact(folder / "required_actions.csv"),
        "rerun_commands_md": _artifact(folder / "rerun_commands.md"),
        "kit_manifest_json": _artifact(folder / "kit_manifest.json"),
    }


def _kit_generation_blockers(
    *,
    target_id: str,
    bridge_row: dict[str, Any],
    packet_row: dict[str, Any],
    packet_audit_row: dict[str, Any],
    action_rows: list[dict[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    if not target_id:
        blockers.append("no_blocked_target")
    if target_id and not bridge_row:
        blockers.append("bridge_row_missing")
    if target_id and not packet_row:
        blockers.append("operator_packet_row_missing")
    if target_id and not packet_audit_row:
        blockers.append("operator_packet_completion_audit_row_missing")
    if packet_audit_row and _text(packet_audit_row.get("audit_status")) != "pass":
        blockers.append("operator_packet_completion_audit_not_pass")
    if target_id and not action_rows:
        blockers.append("target_action_bundle_rows_missing")
    return blockers


def _build_row(
    *,
    args: argparse.Namespace,
    target_id: str,
    bridge_row: dict[str, Any],
    packet_row: dict[str, Any],
    packet_audit_row: dict[str, Any],
    workorder_audit_row: dict[str, Any],
    action_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    target_name = _text(bridge_row.get("target_name") or packet_row.get("target_name") or target_id)
    paths = _kit_paths(args.out_dir, target_id, target_name)
    packet_pass = _text(packet_audit_row.get("audit_status")) == "pass"
    metric_ready = _text(bridge_row.get("metric_runway_status")) == "ready_for_metric_after_native_provenance"
    workorder_pass = _text(bridge_row.get("workorder_audit_status") or workorder_audit_row.get("audit_status")) == "pass"
    native_file_present = _int(bridge_row.get("native_file_present") or packet_audit_row.get("native_file_present"))
    provenance_ready = _status_bool(bridge_row, "provenance_status", "ready")
    evidence_verified = _status_bool(bridge_row, "evidence_ref_status", "verified")
    identity_cleared = _status_bool(bridge_row, "identity_discovery_status", "cleared")
    required_action_count = _int(bridge_row.get("packet_action_count") or packet_row.get("action_count"))
    action_bundle_action_count = len(action_rows)
    generation_blockers = _kit_generation_blockers(
        target_id=target_id,
        bridge_row=bridge_row,
        packet_row=packet_row,
        packet_audit_row=packet_audit_row,
        action_rows=action_rows,
    )
    target_blockers = [
        part
        for part in (_text(item) for item in _text(bridge_row.get("blockers")).split(","))
        if part
    ]
    kit_status = "casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill"
    if generation_blockers:
        kit_status = "casp17_competitive_floor_first_native_provenance_unlock_kit_blocked_missing_inputs"
    return {
        **paths,
        "target_id": target_id,
        "target_name": target_name,
        "kit_status": kit_status,
        "required_field_count": len(INTAKE_COLUMNS) - 1,
        "required_action_count": required_action_count,
        "action_bundle_action_count": action_bundle_action_count,
        "packet_file_pass": "true" if packet_pass else "false",
        "metric_runway_ready": "true" if metric_ready else "false",
        "workorder_audit_pass": "true" if workorder_pass else "false",
        "prediction_present": _int(bridge_row.get("prediction_present") or packet_audit_row.get("prediction_present")),
        "ts_prediction_present": _int(
            bridge_row.get("ts_prediction_present") or packet_audit_row.get("ts_prediction_present")
        ),
        "native_file_present": native_file_present,
        "native_dropzone_path_present": _int(
            bridge_row.get("native_dropzone_path_present") or packet_audit_row.get("native_dropzone_path_present")
        ),
        "provenance_template_present": _int(
            bridge_row.get("provenance_template_present") or packet_audit_row.get("provenance_template_present")
        ),
        "manifest_stub_present": _int(
            bridge_row.get("manifest_stub_present") or packet_audit_row.get("manifest_stub_present")
        ),
        "metric_runway_present": _int(
            bridge_row.get("metric_runway_present") or packet_audit_row.get("metric_runway_present")
        ),
        "workorder_present": _int(bridge_row.get("workorder_present") or packet_audit_row.get("workorder_folder_present")),
        "provenance_ready": "true" if provenance_ready else "false",
        "evidence_ref_verified": "true" if evidence_verified else "false",
        "identity_discovery_cleared": "true" if identity_cleared else "false",
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "coordinate_copy_count": 0,
        "prediction_pdb": _artifact(packet_row.get("prediction_pdb", "")),
        "ts_prediction_pdb": _artifact(packet_row.get("ts_prediction_pdb", "")),
        "native_dropzone_pdb": _artifact(bridge_row.get("native_dropzone_pdb") or packet_row.get("native_dropzone_pdb", "")),
        "provenance_template_csv": _artifact(
            bridge_row.get("provenance_template_csv") or packet_row.get("provenance_template_csv", "")
        ),
        "manifest_stub_csv": _artifact(bridge_row.get("manifest_stub_csv") or packet_row.get("manifest_stub_csv", "")),
        "packet_folder": _artifact(bridge_row.get("packet_folder") or packet_row.get("packet_folder", "")),
        "packet_actions_csv": _artifact(packet_row.get("actions_csv") or packet_audit_row.get("actions_csv", "")),
        "packet_native_candidates_csv": _artifact(
            packet_row.get("native_candidates_csv") or packet_audit_row.get("native_candidates_csv", "")
        ),
        "metric_runway_md": _artifact(bridge_row.get("metric_runway_md") or packet_row.get("metric_runway_md", "")),
        "first_blocker": _text(bridge_row.get("first_blocker")),
        "blockers": ",".join(dict.fromkeys(generation_blockers + target_blockers)),
        "next_action": _text(bridge_row.get("next_action") or packet_row.get("next_action")),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    bridge_payload = _read_json(args.bridge_json)
    packet_payload = _read_json(args.operator_packet_json)
    packet_audit_payload = _read_json(args.operator_packet_completion_audit_json)
    workorder_audit_payload = _read_json(args.workorder_audit_json)
    action_bundle_payload = _read_json(args.action_bundle_json)
    bridge_summary = _summary(bridge_payload)
    bridge_rows = _rows(bridge_payload)
    bridge_by_target = _by_target(bridge_rows)
    packet_by_target = _by_target(_rows(packet_payload))
    packet_audit_by_target = _by_target(_rows(packet_audit_payload))
    workorder_audit_by_target = _by_target(_rows(workorder_audit_payload))
    action_bundle_rows = _rows(action_bundle_payload)
    target_id = _select_target_id(args, bridge_summary, bridge_rows)
    if not target_id:
        status = "casp17_competitive_floor_first_native_provenance_unlock_kit_blocked_no_blocked_target"
        summary = {
            "packet_type": "casp17_competitive_floor_first_native_provenance_unlock_kit",
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "first_unlock_kit_status": status,
            "target_id": "",
            "target_name": "",
            "target_count": 0,
            "required_field_count": 0,
            "required_action_count": 0,
            "action_bundle_action_count": 0,
            "packet_file_pass": False,
            "metric_runway_ready": False,
            "workorder_audit_pass": False,
            "prediction_present_count": 0,
            "ts_prediction_present_count": 0,
            "native_file_present_count": 0,
            "native_dropzone_path_present_count": 0,
            "provenance_template_present_count": 0,
            "manifest_stub_present_count": 0,
            "metric_runway_present_count": 0,
            "workorder_present_count": 0,
            "provenance_ready_count": 0,
            "evidence_ref_verified_count": 0,
            "identity_discovery_cleared_count": 0,
            "competitive_proof_eligible_count": 0,
            "author_serialized_count": 0,
            "coordinate_copy_count": 0,
            "first_blocker": "no_blocked_target",
            "next_action": "Wait for a blocked target row or pass --target-id explicitly.",
            "claim_boundary": CLAIM_BOUNDARY,
        }
        return {"summary": summary, "rows": []}
    action_rows = _target_action_rows(action_bundle_rows, target_id)
    row = _build_row(
        args=args,
        target_id=target_id,
        bridge_row=bridge_by_target.get(target_id, {}),
        packet_row=packet_by_target.get(target_id, {}),
        packet_audit_row=packet_audit_by_target.get(target_id, {}),
        workorder_audit_row=workorder_audit_by_target.get(target_id, {}),
        action_rows=action_rows,
    )
    summary = {
        "packet_type": "casp17_competitive_floor_first_native_provenance_unlock_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_unlock_kit_status": row["kit_status"],
        "bridge_json": _artifact(args.bridge_json),
        "operator_packet_json": _artifact(args.operator_packet_json),
        "operator_packet_completion_audit_json": _artifact(args.operator_packet_completion_audit_json),
        "workorder_audit_json": _artifact(args.workorder_audit_json),
        "action_bundle_json": _artifact(args.action_bundle_json),
        "operator_intake_csv": _artifact(args.operator_intake_csv),
        "out_dir": _artifact(args.out_dir),
        "target_id": target_id,
        "target_name": row["target_name"],
        "target_count": 1,
        "required_field_count": row["required_field_count"],
        "required_action_count": row["required_action_count"],
        "action_bundle_action_count": row["action_bundle_action_count"],
        "packet_file_pass": _bool_text(row["packet_file_pass"]),
        "metric_runway_ready": _bool_text(row["metric_runway_ready"]),
        "workorder_audit_pass": _bool_text(row["workorder_audit_pass"]),
        "prediction_present_count": _int(row["prediction_present"]),
        "ts_prediction_present_count": _int(row["ts_prediction_present"]),
        "native_file_present_count": _int(row["native_file_present"]),
        "native_dropzone_path_present_count": _int(row["native_dropzone_path_present"]),
        "provenance_template_present_count": _int(row["provenance_template_present"]),
        "manifest_stub_present_count": _int(row["manifest_stub_present"]),
        "metric_runway_present_count": _int(row["metric_runway_present"]),
        "workorder_present_count": _int(row["workorder_present"]),
        "provenance_ready_count": 1 if _bool_text(row["provenance_ready"]) else 0,
        "evidence_ref_verified_count": 1 if _bool_text(row["evidence_ref_verified"]) else 0,
        "identity_discovery_cleared_count": 1 if _bool_text(row["identity_discovery_cleared"]) else 0,
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "coordinate_copy_count": 0,
        "kit_folder": row["kit_folder"],
        "operator_fill_intake_csv": row["operator_fill_intake_csv"],
        "required_actions_csv": row["required_actions_csv"],
        "rerun_commands_md": row["rerun_commands_md"],
        "kit_manifest_json": row["kit_manifest_json"],
        "first_blocker": row["first_blocker"],
        "blockers": row["blockers"],
        "next_action": row["next_action"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": [row],
        "operator_fill_rows": [_operator_fill_row(_existing_intake_row(args.operator_intake_csv, target_id), target_id)],
        "action_rows": action_rows,
        "rerun_commands": RERUN_COMMANDS,
    }


def _write_kit_files(payload: dict[str, Any]) -> None:
    rows = payload.get("rows") or []
    if not rows:
        return
    row = rows[0]
    summary = payload["summary"]
    folder = _resolve(row["kit_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(row["operator_fill_intake_csv"], payload["operator_fill_rows"], INTAKE_COLUMNS)
    _write_csv(row["required_actions_csv"], payload["action_rows"], ACTION_COLUMNS)
    commands_lines = ["# CASP17 First Native/Provenance Unlock Rerun Commands", ""]
    commands_lines.extend(f"```bash\n{command}\n```" for command in payload["rerun_commands"])
    commands_lines.extend(["", CLAIM_BOUNDARY, ""])
    _resolve(row["rerun_commands_md"]).write_text("\n\n".join(commands_lines), encoding="utf-8")
    manifest = {
        "packet_type": "casp17_competitive_floor_first_native_provenance_unlock_kit_manifest",
        "target_id": row["target_id"],
        "target_name": row["target_name"],
        "required_field_count": row["required_field_count"],
        "required_action_count": row["required_action_count"],
        "paths": {key: row[key] for key in row if key.endswith("_csv") or key.endswith("_md") or key.endswith("_json")},
        "source_paths": {
            "prediction_pdb": row["prediction_pdb"],
            "ts_prediction_pdb": row["ts_prediction_pdb"],
            "native_dropzone_pdb": row["native_dropzone_pdb"],
            "provenance_template_csv": row["provenance_template_csv"],
            "manifest_stub_csv": row["manifest_stub_csv"],
            "packet_folder": row["packet_folder"],
            "metric_runway_md": row["metric_runway_md"],
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _write_json(row["kit_manifest_json"], manifest)
    readme_lines = [
        f"# CASP17 First Native/Provenance Unlock Kit: {row['target_id']}",
        "",
        f"- status: `{row['kit_status']}`",
        f"- target: `{row['target_id']}` `{row['target_name']}`",
        f"- required fields/actions/bundle actions: `{row['required_field_count']}/{row['required_action_count']}/{row['action_bundle_action_count']}`",
        f"- packet/workorder/runway ready: `{row['packet_file_pass']}/{row['workorder_audit_pass']}/{row['metric_runway_ready']}`",
        f"- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `{row['prediction_present']}/{row['ts_prediction_present']}/{row['native_dropzone_path_present']}/{row['native_file_present']}/{row['provenance_template_present']}/{row['manifest_stub_present']}/{row['metric_runway_present']}/{row['workorder_present']}`",
        f"- provenance/evidence/identity: `{row['provenance_ready']}/{row['evidence_ref_verified']}/{row['identity_discovery_cleared']}`",
        f"- proof/author: `{row['competitive_proof_eligible']}/{row['author_serialized']}`",
        f"- first blocker: `{row['first_blocker'] or '-'}`",
        "",
        "## Operator Files",
        "",
        f"- fill intake row: `{row['operator_fill_intake_csv']}`",
        f"- required actions: `{row['required_actions_csv']}`",
        f"- rerun commands: `{row['rerun_commands_md']}`",
        f"- manifest: `{row['kit_manifest_json']}`",
        "",
        "## Source Links",
        "",
        f"- native dropzone: `{row['native_dropzone_pdb']}`",
        f"- provenance template: `{row['provenance_template_csv']}`",
        f"- manifest stub: `{row['manifest_stub_csv']}`",
        f"- packet folder: `{row['packet_folder']}`",
        f"- metric runway: `{row['metric_runway_md']}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
    ]
    _resolve(row["readme_md"]).write_text("\n".join(readme_lines), encoding="utf-8")
    coordinate_count = _coordinate_file_count(folder)
    row["coordinate_copy_count"] = coordinate_count
    summary["coordinate_copy_count"] = coordinate_count
    if coordinate_count:
        row["kit_status"] = "casp17_competitive_floor_first_native_provenance_unlock_kit_blocked_coordinate_copy_present"
        summary["first_unlock_kit_status"] = row["kit_status"]


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor First Native/Provenance Unlock Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_unlock_kit_status']}`",
        f"- target: `{summary['target_id'] or '-'}` `{summary['target_name'] or '-'}`",
        f"- required fields/actions/bundle actions: `{summary['required_field_count']}/{summary['required_action_count']}/{summary['action_bundle_action_count']}`",
        f"- packet/workorder/runway ready: `{summary['packet_file_pass']}/{summary['workorder_audit_pass']}/{summary['metric_runway_ready']}`",
        f"- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `{summary['prediction_present_count']}/{summary['ts_prediction_present_count']}/{summary['native_dropzone_path_present_count']}/{summary['native_file_present_count']}/{summary['provenance_template_present_count']}/{summary['manifest_stub_present_count']}/{summary['metric_runway_present_count']}/{summary['workorder_present_count']}`",
        f"- provenance/evidence/identity: `{summary['provenance_ready_count']}/{summary['evidence_ref_verified_count']}/{summary['identity_discovery_cleared_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- coordinate copies in kit: `{summary['coordinate_copy_count']}`",
        f"- first blocker: `{summary['first_blocker'] or '-'}`",
        f"- kit folder: `{summary.get('kit_folder', '') or '-'}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_kit_files(payload)
    _write_json(args.out_json, {"summary": payload["summary"], "rows": payload["rows"]})
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first CASP17 native/provenance unlock operator kit.")
    parser.add_argument("--bridge-json", default=DEFAULT_BRIDGE_JSON)
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument(
        "--operator-packet-completion-audit-json",
        default=DEFAULT_OPERATOR_PACKET_COMPLETION_AUDIT_JSON,
    )
    parser.add_argument("--workorder-audit-json", default=DEFAULT_WORKORDER_AUDIT_JSON)
    parser.add_argument("--action-bundle-json", default=DEFAULT_ACTION_BUNDLE_JSON)
    parser.add_argument("--operator-intake-csv", default=DEFAULT_OPERATOR_INTAKE_CSV)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
