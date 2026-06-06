#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.casp17 import build_casp17_competitive_floor_first_native_provenance_unlock_kit as first


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BRIDGE_JSON = first.DEFAULT_BRIDGE_JSON
DEFAULT_OPERATOR_PACKET_JSON = first.DEFAULT_OPERATOR_PACKET_JSON
DEFAULT_OPERATOR_PACKET_COMPLETION_AUDIT_JSON = first.DEFAULT_OPERATOR_PACKET_COMPLETION_AUDIT_JSON
DEFAULT_WORKORDER_AUDIT_JSON = first.DEFAULT_WORKORDER_AUDIT_JSON
DEFAULT_ACTION_BUNDLE_JSON = first.DEFAULT_ACTION_BUNDLE_JSON
DEFAULT_OPERATOR_INTAKE_CSV = first.DEFAULT_OPERATOR_INTAKE_CSV
DEFAULT_OUT_DIR = "casp17/competitive_floor_batch_native_provenance_unlock_kit"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_unlock_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_batch_native_provenance_unlock_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_BATCH_NATIVE_PROVENANCE_UNLOCK_KIT.md"

BATCH_ACTION_COLUMNS = ["target_id", *first.ACTION_COLUMNS]
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor batch native/provenance unlock operator kit only. It collects all blocked "
    "native/provenance target packets into one operator-fill workspace with per-target folders, a batch intake "
    "CSV, action matrix, and rerun commands. It does not fetch native structures, copy coordinates, fill or trust "
    "provenance, clear no-leak evidence, compute native accuracy, serialize a CASP author code, or submit to CASP."
)


def _target_ids(args: argparse.Namespace, bridge_rows: list[dict[str, Any]]) -> list[str]:
    explicit = [first._text(target_id).upper() for target_id in (args.target_id or []) if first._text(target_id)]
    if explicit:
        return list(dict.fromkeys(explicit))
    return [
        first._text(row.get("target_id")).upper()
        for row in bridge_rows
        if first._text(row.get("target_id")) and first._text(row.get("bridge_status")) != "ready_for_metric_execution"
    ]


def _batch_paths(out_dir: str | Path) -> dict[str, str]:
    root = first._resolve(out_dir)
    return {
        "batch_folder": first._artifact(root),
        "batch_readme_md": first._artifact(root / "README.md"),
        "batch_operator_fill_intake_csv": first._artifact(root / "operator_fill_intake_batch.csv"),
        "batch_required_actions_csv": first._artifact(root / "required_actions_batch.csv"),
        "batch_rerun_commands_md": first._artifact(root / "rerun_commands.md"),
        "batch_manifest_json": first._artifact(root / "batch_manifest.json"),
    }


def _as_bool_text(value: Any) -> bool:
    return first._text(value).lower() == "true"


def _empty_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = _batch_paths(args.out_dir)
    summary = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_unlock_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_unlock_kit_status": (
            "casp17_competitive_floor_batch_native_provenance_unlock_kit_blocked_no_blocked_targets"
        ),
        "bridge_json": first._artifact(args.bridge_json),
        "operator_packet_json": first._artifact(args.operator_packet_json),
        "operator_packet_completion_audit_json": first._artifact(args.operator_packet_completion_audit_json),
        "workorder_audit_json": first._artifact(args.workorder_audit_json),
        "action_bundle_json": first._artifact(args.action_bundle_json),
        "operator_intake_csv": first._artifact(args.operator_intake_csv),
        **paths,
        "target_count": 0,
        "target_ready_for_operator_fill_count": 0,
        "target_blocked_count": 0,
        "required_field_per_target_count": len(first.INTAKE_COLUMNS) - 1,
        "required_field_total_count": 0,
        "required_action_count": 0,
        "action_bundle_action_count": 0,
        "packet_file_pass_count": 0,
        "metric_runway_ready_count": 0,
        "workorder_audit_pass_count": 0,
        "prediction_present_count": 0,
        "ts_prediction_present_count": 0,
        "native_dropzone_path_present_count": 0,
        "native_file_present_count": 0,
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
        "first_target_id": "",
        "first_blocked_target_id": "",
        "first_blocker": "no_blocked_targets",
        "target_ids": "",
        "next_action": "Wait for blocked native/provenance bridge rows or pass --target-id explicitly.",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": [],
        "operator_fill_rows": [],
        "action_rows": [],
        "rerun_commands": _batch_rerun_commands(),
    }


def _batch_rerun_commands() -> list[str]:
    return [
        "python3 tools/casp17/build_casp17_competitive_floor_target_identity_clearance_operator_intake.py",
        "python3 tools/casp17/sync_casp17_competitive_floor_target_identity_clearance_manifest_stub.py",
        "python3 tools/casp17/build_casp17_competitive_floor_target_identity_clearance_workorder_audit.py",
        "python3 tools/casp17/build_casp17_competitive_floor_target_identity_metric_runway.py",
        "python3 tools/casp17/build_casp17_competitive_floor_native_provenance_operator_packet.py",
        "python3 tools/casp17/build_casp17_competitive_floor_native_provenance_operator_packet_completion_audit.py",
        "python3 tools/casp17/build_casp17_competitive_floor_native_provenance_metric_unlock_bridge.py",
        "python3 tools/casp17/build_casp17_competitive_floor_first_native_provenance_unlock_kit.py",
        "python3 tools/build_casp17_competitive_floor_batch_native_provenance_unlock_kit.py",
        "python3 tools/build_casp17_workbench_index.py",
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    bridge_payload = first._read_json(args.bridge_json)
    packet_payload = first._read_json(args.operator_packet_json)
    packet_audit_payload = first._read_json(args.operator_packet_completion_audit_json)
    workorder_audit_payload = first._read_json(args.workorder_audit_json)
    action_bundle_payload = first._read_json(args.action_bundle_json)
    bridge_rows = first._rows(bridge_payload)
    target_ids = _target_ids(args, bridge_rows)
    if not target_ids:
        return _empty_payload(args)

    bridge_by_target = first._by_target(bridge_rows)
    packet_by_target = first._by_target(first._rows(packet_payload))
    packet_audit_by_target = first._by_target(first._rows(packet_audit_payload))
    workorder_audit_by_target = first._by_target(first._rows(workorder_audit_payload))
    action_bundle_rows = first._rows(action_bundle_payload)
    rows: list[dict[str, Any]] = []
    operator_fill_rows: list[dict[str, str]] = []
    action_rows: list[dict[str, Any]] = []
    for target_id in target_ids:
        target_actions = first._target_action_rows(action_bundle_rows, target_id)
        row = first._build_row(
            args=args,
            target_id=target_id,
            bridge_row=bridge_by_target.get(target_id, {}),
            packet_row=packet_by_target.get(target_id, {}),
            packet_audit_row=packet_audit_by_target.get(target_id, {}),
            workorder_audit_row=workorder_audit_by_target.get(target_id, {}),
            action_rows=target_actions,
        )
        rows.append(row)
        operator_fill_rows.append(
            first._operator_fill_row(first._existing_intake_row(args.operator_intake_csv, target_id), target_id)
        )
        action_rows.extend({**action, "target_id": target_id} for action in target_actions)

    ready_status = "casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill"
    ready_rows = [row for row in rows if row["kit_status"] == ready_status]
    coordinate_count = sum(first._coordinate_file_count(row["kit_folder"]) for row in rows)
    status = "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
    if len(ready_rows) != len(rows):
        status = "casp17_competitive_floor_batch_native_provenance_unlock_kit_blocked_missing_inputs"
    if coordinate_count:
        status = "casp17_competitive_floor_batch_native_provenance_unlock_kit_blocked_coordinate_copy_present"
    paths = _batch_paths(args.out_dir)
    summary = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_unlock_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_unlock_kit_status": status,
        "bridge_json": first._artifact(args.bridge_json),
        "operator_packet_json": first._artifact(args.operator_packet_json),
        "operator_packet_completion_audit_json": first._artifact(args.operator_packet_completion_audit_json),
        "workorder_audit_json": first._artifact(args.workorder_audit_json),
        "action_bundle_json": first._artifact(args.action_bundle_json),
        "operator_intake_csv": first._artifact(args.operator_intake_csv),
        **paths,
        "target_count": len(rows),
        "target_ready_for_operator_fill_count": len(ready_rows),
        "target_blocked_count": len(rows) - len(ready_rows),
        "required_field_per_target_count": len(first.INTAKE_COLUMNS) - 1,
        "required_field_total_count": (len(first.INTAKE_COLUMNS) - 1) * len(rows),
        "required_action_count": sum(first._int(row.get("required_action_count")) for row in rows),
        "action_bundle_action_count": sum(first._int(row.get("action_bundle_action_count")) for row in rows),
        "packet_file_pass_count": sum(1 for row in rows if _as_bool_text(row.get("packet_file_pass"))),
        "metric_runway_ready_count": sum(1 for row in rows if _as_bool_text(row.get("metric_runway_ready"))),
        "workorder_audit_pass_count": sum(1 for row in rows if _as_bool_text(row.get("workorder_audit_pass"))),
        "prediction_present_count": sum(first._int(row.get("prediction_present")) for row in rows),
        "ts_prediction_present_count": sum(first._int(row.get("ts_prediction_present")) for row in rows),
        "native_dropzone_path_present_count": sum(first._int(row.get("native_dropzone_path_present")) for row in rows),
        "native_file_present_count": sum(first._int(row.get("native_file_present")) for row in rows),
        "provenance_template_present_count": sum(first._int(row.get("provenance_template_present")) for row in rows),
        "manifest_stub_present_count": sum(first._int(row.get("manifest_stub_present")) for row in rows),
        "metric_runway_present_count": sum(first._int(row.get("metric_runway_present")) for row in rows),
        "workorder_present_count": sum(first._int(row.get("workorder_present")) for row in rows),
        "provenance_ready_count": sum(1 for row in rows if _as_bool_text(row.get("provenance_ready"))),
        "evidence_ref_verified_count": sum(1 for row in rows if _as_bool_text(row.get("evidence_ref_verified"))),
        "identity_discovery_cleared_count": sum(1 for row in rows if _as_bool_text(row.get("identity_discovery_cleared"))),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "coordinate_copy_count": coordinate_count,
        "first_target_id": rows[0]["target_id"],
        "first_blocked_target_id": rows[0]["target_id"] if rows else "",
        "first_blocker": first._text(rows[0].get("first_blocker")) if rows else "",
        "target_ids": ",".join(row["target_id"] for row in rows),
        "next_action": "Fill the batch native_source_pdb and no-leak provenance rows, then rerun the listed commands.",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": rows,
        "operator_fill_rows": operator_fill_rows,
        "action_rows": action_rows,
        "rerun_commands": _batch_rerun_commands(),
    }


def _write_per_target_files(row: dict[str, Any], operator_fill_row: dict[str, str], actions: list[dict[str, Any]]) -> None:
    folder = first._resolve(row["kit_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    first._write_csv(row["operator_fill_intake_csv"], [operator_fill_row], first.INTAKE_COLUMNS)
    first._write_csv(row["required_actions_csv"], actions, first.ACTION_COLUMNS)
    command_lines = ["# CASP17 Batch Native/Provenance Unlock Rerun Commands", ""]
    command_lines.extend(f"```bash\n{command}\n```" for command in _batch_rerun_commands())
    command_lines.extend(["", CLAIM_BOUNDARY, ""])
    first._resolve(row["rerun_commands_md"]).write_text("\n\n".join(command_lines), encoding="utf-8")
    manifest = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_unlock_target_manifest",
        "target_id": row["target_id"],
        "target_name": row["target_name"],
        "required_field_count": row["required_field_count"],
        "required_action_count": row["required_action_count"],
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
    first._write_json(row["kit_manifest_json"], manifest)
    readme_lines = [
        f"# CASP17 Batch Native/Provenance Unlock Target Kit: {row['target_id']}",
        "",
        f"- status: `{row['kit_status']}`",
        f"- target: `{row['target_id']}` `{row['target_name']}`",
        f"- fields/actions/bundle: `{row['required_field_count']}/{row['required_action_count']}/{row['action_bundle_action_count']}`",
        f"- packet/workorder/runway: `{row['packet_file_pass']}`/`{row['workorder_audit_pass']}`/`{row['metric_runway_ready']}`",
        f"- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `{row['prediction_present']}/{row['ts_prediction_present']}/{row['native_dropzone_path_present']}/{row['native_file_present']}/{row['provenance_template_present']}/{row['manifest_stub_present']}/{row['metric_runway_present']}/{row['workorder_present']}`",
        f"- provenance/evidence/identity: `{row['provenance_ready']}`/`{row['evidence_ref_verified']}`/`{row['identity_discovery_cleared']}`",
        f"- proof/author: `{row['competitive_proof_eligible']}`/`{row['author_serialized']}`",
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
        CLAIM_BOUNDARY,
        "",
    ]
    first._resolve(row["readme_md"]).write_text("\n".join(readme_lines), encoding="utf-8")


def _write_batch_files(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    root = first._resolve(summary["batch_folder"])
    root.mkdir(parents=True, exist_ok=True)
    actions_by_target: dict[str, list[dict[str, Any]]] = {}
    for action in payload["action_rows"]:
        actions_by_target.setdefault(first._text(action.get("target_id")).upper(), []).append(action)
    fill_by_target = {row["target_id"]: row for row in payload["operator_fill_rows"]}
    for row in payload["rows"]:
        _write_per_target_files(row, fill_by_target.get(row["target_id"], {}), actions_by_target.get(row["target_id"], []))
    first._write_csv(summary["batch_operator_fill_intake_csv"], payload["operator_fill_rows"], first.INTAKE_COLUMNS)
    first._write_csv(summary["batch_required_actions_csv"], payload["action_rows"], BATCH_ACTION_COLUMNS)
    command_lines = ["# CASP17 Batch Native/Provenance Unlock Rerun Commands", ""]
    command_lines.extend(f"```bash\n{command}\n```" for command in payload["rerun_commands"])
    command_lines.extend(["", CLAIM_BOUNDARY, ""])
    first._resolve(summary["batch_rerun_commands_md"]).write_text("\n\n".join(command_lines), encoding="utf-8")
    manifest = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_unlock_kit_manifest",
        "target_ids": summary["target_ids"],
        "target_count": summary["target_count"],
        "required_field_total_count": summary["required_field_total_count"],
        "required_action_count": summary["required_action_count"],
        "rows": payload["rows"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    first._write_json(summary["batch_manifest_json"], manifest)
    readme_lines = [
        "# CASP17 Batch Native/Provenance Unlock Kit",
        "",
        f"- status: `{summary['batch_unlock_kit_status']}`",
        f"- targets ready/blocked/total: `{summary['target_ready_for_operator_fill_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- target ids: `{summary['target_ids'] or '-'}`",
        f"- fields per-target/total: `{summary['required_field_per_target_count']}/{summary['required_field_total_count']}`",
        f"- actions required/bundle: `{summary['required_action_count']}/{summary['action_bundle_action_count']}`",
        f"- packet/workorder/runway ready: `{summary['packet_file_pass_count']}/{summary['workorder_audit_pass_count']}/{summary['metric_runway_ready_count']}`",
        f"- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `{summary['prediction_present_count']}/{summary['ts_prediction_present_count']}/{summary['native_dropzone_path_present_count']}/{summary['native_file_present_count']}/{summary['provenance_template_present_count']}/{summary['manifest_stub_present_count']}/{summary['metric_runway_present_count']}/{summary['workorder_present_count']}`",
        f"- provenance/evidence/identity: `{summary['provenance_ready_count']}/{summary['evidence_ref_verified_count']}/{summary['identity_discovery_cleared_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        "",
        "## Operator Files",
        "",
        f"- fill intake batch: `{summary['batch_operator_fill_intake_csv']}`",
        f"- required actions batch: `{summary['batch_required_actions_csv']}`",
        f"- rerun commands: `{summary['batch_rerun_commands_md']}`",
        f"- manifest: `{summary['batch_manifest_json']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    first._resolve(summary["batch_readme_md"]).write_text("\n".join(readme_lines), encoding="utf-8")
    coordinate_count = first._coordinate_file_count(root)
    summary["coordinate_copy_count"] = coordinate_count
    for row in payload["rows"]:
        row["coordinate_copy_count"] = first._coordinate_file_count(row["kit_folder"])
    if coordinate_count:
        summary["batch_unlock_kit_status"] = (
            "casp17_competitive_floor_batch_native_provenance_unlock_kit_blocked_coordinate_copy_present"
        )


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Batch Native/Provenance Unlock Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_unlock_kit_status']}`",
        f"- targets ready/blocked/total: `{summary['target_ready_for_operator_fill_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- target ids: `{summary['target_ids'] or '-'}`",
        f"- fields per-target/total: `{summary['required_field_per_target_count']}/{summary['required_field_total_count']}`",
        f"- actions required/bundle: `{summary['required_action_count']}/{summary['action_bundle_action_count']}`",
        f"- packet/workorder/runway ready: `{summary['packet_file_pass_count']}/{summary['workorder_audit_pass_count']}/{summary['metric_runway_ready_count']}`",
        f"- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `{summary['prediction_present_count']}/{summary['ts_prediction_present_count']}/{summary['native_dropzone_path_present_count']}/{summary['native_file_present_count']}/{summary['provenance_template_present_count']}/{summary['manifest_stub_present_count']}/{summary['metric_runway_present_count']}/{summary['workorder_present_count']}`",
        f"- provenance/evidence/identity: `{summary['provenance_ready_count']}/{summary['evidence_ref_verified_count']}/{summary['identity_discovery_cleared_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- coordinate copies in kit: `{summary['coordinate_copy_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- batch folder: `{summary['batch_folder']}`",
        "",
        "## Targets",
        "",
        "| target | status | fields | actions | native | provenance | evidence | identity |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['kit_status']}` | `{row['required_field_count']}` | "
            f"`{row['required_action_count']}` | `{row['native_file_present']}` | `{row['provenance_ready']}` | "
            f"`{row['evidence_ref_verified']}` | `{row['identity_discovery_cleared']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = first._resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_batch_files(payload)
    first._write_json(args.out_json, {"summary": payload["summary"], "rows": payload["rows"]})
    first._write_csv(args.out_csv, payload["rows"], first.ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a batch CASP17 native/provenance unlock operator kit.")
    parser.add_argument("--bridge-json", default=DEFAULT_BRIDGE_JSON)
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument(
        "--operator-packet-completion-audit-json",
        default=DEFAULT_OPERATOR_PACKET_COMPLETION_AUDIT_JSON,
    )
    parser.add_argument("--workorder-audit-json", default=DEFAULT_WORKORDER_AUDIT_JSON)
    parser.add_argument("--action-bundle-json", default=DEFAULT_ACTION_BUNDLE_JSON)
    parser.add_argument("--operator-intake-csv", default=DEFAULT_OPERATOR_INTAKE_CSV)
    parser.add_argument("--target-id", action="append", default=[])
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
