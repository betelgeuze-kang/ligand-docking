#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_AUDIT_JSON = "casp17/casp17_strict_blind_internal_prediction_source_audit_current.json"
DEFAULT_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_SOURCE_BRIDGE_JSON = "casp17/casp17_strict_blind_first_slot_source_bridge_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_internal_prediction_source_apply_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_internal_prediction_source_apply_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_APPLY_PLAN.md"
DEFAULT_PLAN_DIR = "casp17/strict_blind_internal_prediction_source_apply_plan"

ROW_COLUMNS = [
    "action_id",
    "action_type",
    "field_name",
    "action_status",
    "source_value",
    "destination",
    "evidence_ref",
    "operator_clearance",
    "blockers",
    "next_action",
]
REQUIRED_SUPPLEMENTAL_FILES = [
    ("native_pdb", "native PDB file selected from accepted historical target identity"),
    ("native_authority_ref", "native authority/source reference markdown"),
    ("no_leak_evidence_ref", "independent no-leak provenance evidence"),
    ("ablation_manifest_ref", "same-run/pre-minimization ablation manifest"),
    ("calibration_values_ref", "model1/best-of-5 calibration values"),
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind internal prediction source apply plan only. It maps a gate-passed internal "
    "prediction source manifest to first-slot dropzone and operator-value actions. It is fail-closed: when the "
    "source gate is not ready, every action remains blocked. It does not copy files, mutate operator/intake CSVs, "
    "approve provenance, compute CASP metrics, push remotes, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
        return ""
    path = _resolve(path_like).resolve()
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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _first_slot_row(first_slot_rows: list[dict[str, Any]], field_name: str) -> dict[str, Any]:
    for row in first_slot_rows:
        if _text(row.get("field_name")) == field_name:
            return row
    return {}


def _gate_blockers(gate_summary: dict[str, Any]) -> list[str]:
    if _text(gate_summary.get("internal_prediction_source_gate_status")) == (
        "internal_prediction_source_ready_for_first_slot_dropzone"
    ):
        return []
    blockers = ["internal_prediction_source_gate_not_ready"]
    first = _text(gate_summary.get("first_blocker"))
    if first:
        blockers.append(first)
    return blockers


def _manifest_row(manifest_csv: str) -> dict[str, str]:
    rows = _read_csv_rows(manifest_csv)
    return rows[0] if rows else {}


def _action(
    index: int,
    action_type: str,
    field_name: str,
    source_value: str,
    destination: str,
    evidence_ref: str,
    operator_clearance: str,
    blockers: list[str],
    next_action: str,
) -> dict[str, str]:
    return {
        "action_id": f"internal_prediction_apply_{index:03d}",
        "action_type": action_type,
        "field_name": field_name,
        "action_status": "ready_for_operator_apply" if not blockers else "blocked",
        "source_value": source_value,
        "destination": destination,
        "evidence_ref": evidence_ref,
        "operator_clearance": operator_clearance,
        "blockers": ",".join(blockers),
        "next_action": "" if not blockers else next_action,
    }


def _operator_value_actions(
    start_index: int,
    manifest: dict[str, str],
    first_slot_rows: list[dict[str, Any]],
    gate_blockers: list[str],
) -> list[dict[str, str]]:
    operator_values_csv = _text(_first_slot_row(first_slot_rows, "replacement_target_id").get("operator_values_csv"))
    destination_intake = _text(_first_slot_row(first_slot_rows, "replacement_target_id").get("destination_intake_csv"))
    fields = [
        ("replacement_target_id", _text(manifest.get("replacement_target_id")), _text(manifest.get("creation_evidence_ref"))),
        ("replacement_benchmark_id", _text(manifest.get("source_id")), _text(manifest.get("creation_evidence_ref"))),
        ("target_identity_non_current_historical", "true", _text(manifest.get("native_authority_ref"))),
        ("prediction_created_at", _text(manifest.get("prediction_created_at")), _text(manifest.get("creation_evidence_ref"))),
        ("native_release_date", _text(manifest.get("native_release_date")), _text(manifest.get("native_authority_ref"))),
        ("prediction_generated_before_native_release", "true", _text(manifest.get("creation_evidence_ref"))),
        ("public_template_or_native_used_for_prediction", "false", _text(manifest.get("no_leak_evidence_ref"))),
        ("other_team_model_used", "false", _text(manifest.get("no_leak_evidence_ref"))),
        ("post_release_information_used", "false", _text(manifest.get("no_leak_evidence_ref"))),
        ("operator_clearance", _text(manifest.get("operator_clearance")), _text(manifest.get("creation_evidence_ref"))),
    ]
    rows: list[dict[str, str]] = []
    for offset, (field_name, value, evidence_ref) in enumerate(fields):
        blockers = list(gate_blockers)
        if not value:
            blockers.append(f"{field_name}_value_missing")
        if not operator_values_csv:
            blockers.append("operator_values_csv_missing")
        rows.append(
            _action(
                start_index + offset,
                "operator_value",
                field_name,
                value,
                operator_values_csv or destination_intake,
                evidence_ref,
                _text(manifest.get("operator_clearance")),
                blockers,
                "fill and clear replacement_operator_values.csv after source gate passes",
            )
        )
    return rows


def _file_actions(
    manifest: dict[str, str],
    first_slot_rows: list[dict[str, Any]],
    gate_summary: dict[str, Any],
    gate_blockers: list[str],
) -> list[dict[str, str]]:
    prediction_destination = _text(_first_slot_row(first_slot_rows, "prediction_pdb").get("source_path")) or _text(
        gate_summary.get("prediction_dropzone")
    )
    source_prediction = _text(manifest.get("prediction_pdb")) or _text(gate_summary.get("manifest_prediction_pdb"))
    blockers = list(gate_blockers)
    if not source_prediction:
        blockers.append("prediction_pdb_source_missing")
    if not prediction_destination:
        blockers.append("prediction_dropzone_missing")
    return [
        _action(
            1,
            "file_copy",
            "prediction_pdb",
            source_prediction,
            prediction_destination,
            _text(manifest.get("creation_evidence_ref")),
            _text(manifest.get("operator_clearance")),
            blockers,
            "copy verified internal prediction PDB into the first-slot prediction dropzone",
        )
    ]


def _supplemental_actions(
    start_index: int,
    first_slot_rows: list[dict[str, Any]],
    gate_blockers: list[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for offset, (field_name, description) in enumerate(REQUIRED_SUPPLEMENTAL_FILES):
        destination = _text(_first_slot_row(first_slot_rows, field_name).get("source_path"))
        blockers = list(gate_blockers) + [f"{field_name}_supplemental_evidence_required"]
        rows.append(
            _action(
                start_index + offset,
                "supplemental_evidence",
                field_name,
                "",
                destination,
                "",
                "",
                blockers,
                f"attach {description}",
            )
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_payload = _read_json(args.gate_json)
    audit_payload = _read_json(args.audit_json)
    first_slot_payload = _read_json(args.first_slot_kit_json)
    source_bridge_payload = _read_json(args.source_bridge_json)
    gate_summary = _summary(gate_payload)
    audit_summary = _summary(audit_payload)
    bridge_summary = _summary(source_bridge_payload)
    manifest_csv = _text(gate_summary.get("manifest_csv")) or _text(audit_summary.get("internal_source_manifest_template"))
    manifest = _manifest_row(manifest_csv)
    first_slot_rows = _rows(first_slot_payload)
    input_blockers = []
    for name in ["gate_json", "audit_json", "first_slot_kit_json", "source_bridge_json"]:
        if not _resolve(getattr(args, name)).exists():
            input_blockers.append(f"{name}_missing")
    if not manifest_csv or not _resolve(manifest_csv).exists():
        input_blockers.append("internal_source_manifest_csv_missing")
    blockers = input_blockers + _gate_blockers(gate_summary)
    rows = []
    rows.extend(_file_actions(manifest, first_slot_rows, gate_summary, blockers))
    rows.extend(_operator_value_actions(len(rows) + 1, manifest, first_slot_rows, blockers))
    rows.extend(_supplemental_actions(len(rows) + 1, first_slot_rows, blockers))
    ready_rows = [row for row in rows if row["action_status"] == "ready_for_operator_apply"]
    first_blocked = next((row for row in rows if row["action_status"] != "ready_for_operator_apply"), {})
    status = "internal_prediction_apply_plan_ready_for_operator_apply" if ready_rows and len(ready_rows) == len(rows) else (
        "blocked_missing_inputs" if input_blockers else "blocked_until_internal_prediction_source_gate_passes"
    )
    summary = {
        "packet_type": "casp17_strict_blind_internal_prediction_source_apply_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "internal_prediction_source_apply_plan_status": status,
        "required_benchmark_id": _text(gate_summary.get("required_benchmark_id") or audit_summary.get("required_benchmark_id")),
        "required_target_id": _text(gate_summary.get("required_target_id") or audit_summary.get("required_target_id")),
        "required_scope": _text(gate_summary.get("required_scope") or audit_summary.get("required_scope")),
        "gate_status": _text(gate_summary.get("internal_prediction_source_gate_status")),
        "source_bridge_status": _text(bridge_summary.get("source_bridge_status")),
        "manifest_csv": _artifact(manifest_csv),
        "action_count": len(rows),
        "ready_action_count": len(ready_rows),
        "blocked_action_count": len(rows) - len(ready_rows),
        "file_action_count": sum(1 for row in rows if row["action_type"] == "file_copy"),
        "operator_value_action_count": sum(1 for row in rows if row["action_type"] == "operator_value"),
        "supplemental_evidence_action_count": sum(1 for row in rows if row["action_type"] == "supplemental_evidence"),
        "first_blocked_action_id": _text(first_blocked.get("action_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if _text(first_blocked.get("blockers")) else "",
        "first_next_action": _text(first_blocked.get("next_action")),
        "prediction_source": _text(manifest.get("prediction_pdb") or gate_summary.get("manifest_prediction_pdb")),
        "prediction_destination": _text(gate_summary.get("prediction_dropzone")),
        "native_authority_ref": _text(manifest.get("native_authority_ref")),
        "operator_clearance": _text(manifest.get("operator_clearance")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_plan_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(args.plan_dir) / (summary["required_benchmark_id"] or "hist_REQUIRED_MONOMER_001")
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "internal_prediction_source_apply_plan.csv", payload["rows"], ROW_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind Internal Prediction Source Apply Plan",
        "",
        f"- status: `{summary['internal_prediction_source_apply_plan_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- gate: `{summary['gate_status']}`",
        f"- actions ready/blocked/total: `{summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['action_count']}`",
        f"- first blocker: `{summary['first_blocked_action_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "INTERNAL_PREDICTION_SOURCE_APPLY_PLAN.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Internal Prediction Source Apply Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['internal_prediction_source_apply_plan_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- gate/source bridge: `{summary['gate_status']}` `{summary['source_bridge_status']}`",
        f"- actions ready/blocked/total: `{summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['action_count']}`",
        f"- file/operator/supplemental actions: `{summary['file_action_count']}/{summary['operator_value_action_count']}/{summary['supplemental_evidence_action_count']}`",
        f"- prediction source/destination: `{summary['prediction_source'] or '-'}` `{summary['prediction_destination'] or '-'}`",
        f"- first blocker: `{summary['first_blocked_action_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Actions",
        "",
        "| action | type | field | status | source | destination | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['action_type']}` | `{row['field_name']}` | "
            f"`{row['action_status']}` | `{row['source_value']}` | `{row['destination']}` | "
            f"`{row['blockers'] or '-'}` | {row['next_action'] or '-'} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_plan_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict-blind internal prediction source apply plan.")
    parser.add_argument("--gate-json", default=DEFAULT_GATE_JSON)
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--first-slot-kit-json", default=DEFAULT_FIRST_SLOT_KIT_JSON)
    parser.add_argument("--source-bridge-json", default=DEFAULT_SOURCE_BRIDGE_JSON)
    parser.add_argument("--plan-dir", default=DEFAULT_PLAN_DIR)
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
