#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DROPZONES_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_import_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_import_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_IMPORT_GATE.md"

FILE_FIELDS = {
    "prediction_pdb",
    "native_pdb",
    "native_authority_ref",
    "no_leak_evidence_ref",
    "ablation_manifest_ref",
    "calibration_values_ref",
}
OPERATOR_VALUE_FIELDS = {
    "replacement_target_id",
    "replacement_benchmark_id",
    "target_identity_non_current_historical",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "operator_clearance",
}
ROW_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "field_name",
    "field_kind",
    "current_value",
    "recommended_value",
    "source_status",
    "import_status",
    "apply_mode",
    "applied",
    "source_path",
    "destination_intake_csv",
    "blocker",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind replacement evidence import gate only. It audits dropzone patch previews and can "
    "optionally copy file evidence paths into replacement_candidate_intake.csv placeholders. It does not fill "
    "operator-only values, approve no-leak provenance, choose replacement targets, create evidence, compute CASP "
    "metrics, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    if not _text(path_like):
        return [], [], ["csv_path_missing"]
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    if not path.is_file():
        return [], [], [f"{path.name}_not_file"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, fieldnames, blockers


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _intake_first_row(path_like: str | Path) -> tuple[dict[str, str], list[dict[str, str]], list[str], list[str]]:
    rows, fieldnames, blockers = _read_csv(path_like)
    return (rows[0] if rows else {}, rows, fieldnames, blockers)


def _patch_preview_rows(dropzone_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dropzone in dropzone_rows:
        patch_csv = _text(dropzone.get("patch_preview_csv"))
        patch_rows, _, blockers = _read_csv(patch_csv)
        if blockers:
            rows.append(
                {
                    "queue_rank": _text(dropzone.get("queue_rank")),
                    "required_benchmark_id": _text(dropzone.get("required_benchmark_id")),
                    "field_name": "",
                    "field_kind": "",
                    "recommended_value": "",
                    "source_status": "blocked",
                    "source_path": "",
                    "destination_intake_csv": "",
                    "blocker": ",".join(blockers),
                }
            )
            continue
        rows.extend(patch_rows)
    return rows


def _status_for(patch: dict[str, str], current_value: str, intake_blockers: list[str]) -> tuple[str, str]:
    field_name = _text(patch.get("field_name"))
    field_kind = _text(patch.get("field_kind"))
    recommended = _text(patch.get("recommended_value"))
    source_path = _text(patch.get("source_path"))
    source_status = _text(patch.get("source_status"))
    if intake_blockers:
        return "blocked_intake_csv", ",".join(intake_blockers)
    if field_kind == "file":
        if field_name not in FILE_FIELDS:
            return "blocked_unknown_file_field", "field_name_not_allowed_for_file_import"
        if source_status != "present":
            return "awaiting_file", source_status or "source_file_missing"
        if not recommended:
            return "blocked_missing_recommended_value", "recommended_value_required"
        source = _resolve(source_path or recommended)
        if not source.is_file():
            return "awaiting_file", "source_file_missing"
        if current_value == recommended:
            return "already_applied", ""
        if _is_placeholder(current_value):
            return "ready_to_apply", ""
        return "blocked_conflict", "intake_field_has_non_placeholder_value"
    if field_kind == "operator_value":
        if field_name not in OPERATOR_VALUE_FIELDS:
            return "blocked_unknown_operator_field", "field_name_not_allowed_for_operator_value"
        if _is_placeholder(current_value):
            return "awaiting_operator_value", "operator_value_required"
        return "operator_value_present", ""
    return "blocked_unknown_field_kind", "field_kind_required"


def _next_action(status: str, field_name: str) -> str:
    if status == "ready_to_apply":
        return f"run this gate with --apply to copy the cleared file path into {field_name}"
    if status == "already_applied":
        return "rerun strict-blind replacement intake preflight"
    if status == "operator_value_present":
        return "rerun strict-blind replacement intake preflight after all operator values and files are present"
    if status == "awaiting_file":
        return "place the missing evidence file in the strict-blind dropzone and rerun dropzones/import gate"
    if status == "awaiting_operator_value":
        return f"fill {field_name} in replacement_candidate_intake.csv"
    if status == "blocked_conflict":
        return f"review the existing {field_name} value before applying the dropzone recommendation"
    return "repair the dropzone patch preview or destination intake CSV"


def _audit_row(patch: dict[str, str], apply: bool) -> dict[str, Any]:
    intake_csv = _text(patch.get("destination_intake_csv"))
    intake_row, _, _, intake_blockers = _intake_first_row(intake_csv)
    field_name = _text(patch.get("field_name"))
    current_value = _text(intake_row.get(field_name))
    status, blocker = _status_for(patch, current_value, intake_blockers)
    applied = False
    if apply and status == "ready_to_apply":
        _apply_patch_row(patch, field_name)
        applied = True
        current_value = _text(patch.get("recommended_value"))
        status = "applied"
    return {
        "queue_rank": _int(patch.get("queue_rank")),
        "required_benchmark_id": _text(patch.get("required_benchmark_id")),
        "field_name": field_name,
        "field_kind": _text(patch.get("field_kind")),
        "current_value": current_value,
        "recommended_value": _text(patch.get("recommended_value")),
        "source_status": _text(patch.get("source_status")),
        "import_status": status,
        "apply_mode": "apply" if apply else "dry_run",
        "applied": "true" if applied else "false",
        "source_path": _text(patch.get("source_path")),
        "destination_intake_csv": intake_csv,
        "blocker": blocker,
        "next_action": _next_action(status, field_name),
    }


def _apply_patch_row(patch: dict[str, str], field_name: str) -> None:
    intake_csv = _text(patch.get("destination_intake_csv"))
    rows, fieldnames, blockers = _read_csv(intake_csv)
    if blockers or not rows:
        return
    if field_name not in fieldnames:
        fieldnames.append(field_name)
    rows[0][field_name] = _text(patch.get("recommended_value"))
    _write_csv(intake_csv, rows, fieldnames)


def _status(rows: list[dict[str, Any]], input_blockers: list[str], *, apply: bool) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "blocked_missing_patch_rows"
    ready = sum(1 for row in rows if row["import_status"] == "ready_to_apply")
    applied = sum(1 for row in rows if row["import_status"] == "applied")
    blocked = sum(1 for row in rows if str(row["import_status"]).startswith("blocked"))
    awaiting = sum(1 for row in rows if str(row["import_status"]).startswith("awaiting"))
    if apply and applied:
        return "applied_file_paths_pending_operator_values"
    if ready:
        return "ready_for_file_path_apply"
    if blocked:
        return "blocked_import_conflicts"
    if awaiting:
        return "awaiting_strict_blind_evidence_import"
    return "strict_blind_evidence_import_gate_clear"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dropzones_payload = _read_json(args.dropzones_json)
    dropzones_summary = _summary(dropzones_payload)
    dropzone_rows = _rows(dropzones_payload)
    input_blockers: list[str] = []
    if not _resolve(args.dropzones_json).exists():
        input_blockers.append("strict_blind_replacement_evidence_dropzones_json_missing")
    patch_rows = _patch_preview_rows(dropzone_rows)
    rows = [_audit_row(row, args.apply) for row in patch_rows]
    first_open = next((row for row in rows if row["import_status"] not in {"already_applied", "operator_value_present"}), {})
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_evidence_import_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_evidence_import_gate_status": _status(rows, input_blockers, apply=args.apply),
        "apply_mode": "apply" if args.apply else "dry_run",
        "dropzones_json": _artifact(args.dropzones_json),
        "dropzone_status": _text(
            dropzones_summary.get("strict_blind_replacement_evidence_dropzone_status")
        ),
        "dropzone_count": _int(dropzones_summary.get("dropzone_count")),
        "action_count": len(rows),
        "file_action_count": sum(1 for row in rows if row["field_kind"] == "file"),
        "operator_value_action_count": sum(1 for row in rows if row["field_kind"] == "operator_value"),
        "ready_for_apply_count": sum(1 for row in rows if row["import_status"] == "ready_to_apply"),
        "applied_count": sum(1 for row in rows if row["import_status"] == "applied"),
        "already_applied_count": sum(1 for row in rows if row["import_status"] == "already_applied"),
        "operator_value_present_count": sum(1 for row in rows if row["import_status"] == "operator_value_present"),
        "awaiting_file_count": sum(1 for row in rows if row["import_status"] == "awaiting_file"),
        "awaiting_operator_value_count": sum(1 for row in rows if row["import_status"] == "awaiting_operator_value"),
        "blocked_count": sum(1 for row in rows if str(row["import_status"]).startswith("blocked")),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_open_field": _text(first_open.get("field_name")),
        "first_open_status": _text(first_open.get("import_status")),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind evidence dropzones",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Evidence Import Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_evidence_import_gate_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- dropzone status: `{summary['dropzone_status'] or '-'}`",
        f"- actions file/operator/total: `{summary['file_action_count']}/{summary['operator_value_action_count']}/{summary['action_count']}`",
        f"- ready/applied/already: `{summary['ready_for_apply_count']}/{summary['applied_count']}/{summary['already_applied_count']}`",
        f"- awaiting file/operator: `{summary['awaiting_file_count']}/{summary['awaiting_operator_value_count']}`",
        f"- blocked: `{summary['blocked_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}` `{summary['first_open_field'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Import Rows",
        "",
        "| rank | benchmark | field | kind | status | applied | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['required_benchmark_id']}` | `{row['field_name']}` | "
            f"`{row['field_kind']}` | `{row['import_status']}` | `{row['applied']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked_missing_patch_rows` | false | provide dropzone patch previews |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind replacement evidence import gate.")
    parser.add_argument("--dropzones-json", default=DEFAULT_DROPZONES_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
