#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FIELD_BOARD_JSON = "casp17/casp17_strict_blind_source_gate_field_board_current.json"
DEFAULT_PACKET_DIR = "casp17/strict_blind_source_gate_operator_packet"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_gate_operator_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_GATE_OPERATOR_PACKET.md"

OPERATOR_COLUMNS = [
    "field_key",
    "fill_kind",
    "operator_value",
    "operator_evidence_ref",
    "required_format",
    "current_value",
    "destination",
    "blocked_checks",
    "operator_status",
    "next_action",
]
PATCH_COLUMNS = [
    "patch_id",
    "patch_kind",
    "manifest_column",
    "source_field_key",
    "current_value",
    "proposed_value",
    "destination",
    "patch_status",
    "blockers",
    "next_action",
]
MANIFEST_COLUMNS = {
    "source_id",
    "prediction_pdb",
    "prediction_created_at",
    "native_release_date",
    "native_authority_ref",
    "creation_evidence_ref",
    "no_leak_evidence_ref",
    "method_summary",
    "operator_clearance",
}
CLEARANCE_VALUES = {"approved", "clear", "cleared", "true", "yes", "operator_clear", "operator_approved"}
EXTERNAL_SOURCE_PREFIXES = ("official_archive", "casp_official", "massivefold_external")
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-gate operator packet only. It turns the first-slot source-gate field "
    "board into an operator-fill CSV and manifest patch preview. It preserves existing operator values, but it "
    "does not apply them to the manifest, copy files, approve provenance, compute CASP metrics, push remotes, or "
    "submit to CASP."
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


def _date(value: str) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


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
    if not path.exists() or not path.is_file():
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


def _pdb_has_atom_records(path_like: str) -> bool:
    if not path_like:
        return False
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return any(line.startswith(("ATOM  ", "HETATM")) for line in handle)
    except OSError:
        return False


def _required_format(field_key: str) -> str:
    return {
        "source_id": "internal source id; must not start official_archive/casp_official/massivefold_external",
        "prediction_pdb": "local pre-native prediction PDB path with ATOM/HETATM records",
        "prediction_pdb_dropzone": "first-slot prediction dropzone PDB copy path",
        "prediction_created_at": "YYYY-MM-DD prediction creation date",
        "native_release_date": "YYYY-MM-DD authoritative native release date",
        "prediction_created_at/native_release_date": "derived: prediction_created_at < native_release_date",
        "native_authority_ref": "artifact path or URI for authoritative native source",
        "creation_evidence_ref": "artifact path or URI for independent prediction timestamp evidence",
        "no_leak_evidence_ref": "artifact path or URI for no-leak provenance evidence",
        "method_summary": "short internal prediction method/source summary",
        "operator_clearance": "approved/clear/cleared/true/yes/operator_clear/operator_approved",
    }.get(field_key, "operator supplied value")


def _input_blockers(args: argparse.Namespace) -> list[str]:
    return ["source_gate_field_board_json_missing"] if not _resolve(args.field_board_json).exists() else []


def _packet_folder(args: argparse.Namespace, summary: dict[str, Any]) -> Path:
    benchmark_id = _text(summary.get("required_benchmark_id")) or "hist_REQUIRED_MONOMER_001"
    return _resolve(args.packet_dir) / benchmark_id


def _operator_csv_path(args: argparse.Namespace, summary: dict[str, Any]) -> Path:
    return _packet_folder(args, summary) / "source_gate_operator_values.csv"


def _existing_values(path: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv_rows(path)
    return {_text(row.get("field_key")): row for row in rows if _text(row.get("field_key"))}


def _operator_status(field_key: str, value: str, rows_by_field: dict[str, dict[str, Any]]) -> tuple[str, str]:
    if field_key == "prediction_created_at/native_release_date":
        pred = _date(_text(rows_by_field.get("prediction_created_at", {}).get("operator_value")))
        native = _date(_text(rows_by_field.get("native_release_date", {}).get("operator_value")))
        if pred and native and pred < native:
            return "ready", ""
        return "awaiting_derived_date_order", "prediction_not_before_native_or_dates_missing"
    if field_key == "prediction_pdb":
        if _pdb_has_atom_records(value):
            return "ready", ""
        return "awaiting_operator_value", "prediction_pdb_missing_or_invalid"
    if field_key == "prediction_pdb_dropzone":
        if value and _resolve(value).is_file():
            return "ready", ""
        return "awaiting_file_copy", "dropzone_prediction_pdb_missing"
    if field_key == "source_id":
        if value and not value.startswith(EXTERNAL_SOURCE_PREFIXES):
            return "ready", ""
        return "awaiting_operator_value", "internal_source_id_missing_or_external"
    if field_key == "operator_clearance":
        if value.lower() in CLEARANCE_VALUES:
            return "ready", ""
        return "awaiting_operator_value", "operator_clearance_missing"
    if value:
        return "ready", ""
    return "awaiting_operator_value", f"{field_key}_missing"


def _build_operator_rows(args: argparse.Namespace, board_summary: dict[str, Any], board_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = _existing_values(_operator_csv_path(args, board_summary))
    rows: list[dict[str, Any]] = []
    for row in board_rows:
        field_key = _text(row.get("field_key"))
        preserved = existing.get(field_key, {})
        operator_value = _text(preserved.get("operator_value")) or _text(row.get("current_value"))
        out = {
            "field_key": field_key,
            "fill_kind": _text(row.get("fill_kind")),
            "operator_value": operator_value,
            "operator_evidence_ref": _text(preserved.get("operator_evidence_ref")),
            "required_format": _required_format(field_key),
            "current_value": _text(row.get("current_value")),
            "destination": _text(row.get("destination")),
            "blocked_checks": _text(row.get("affected_check_ids")),
            "operator_status": "awaiting_operator_value",
            "next_action": _text(row.get("next_action")),
        }
        rows.append(out)
    rows_by_field = {row["field_key"]: row for row in rows}
    for row in rows:
        status, blocker = _operator_status(row["field_key"], row["operator_value"], rows_by_field)
        row["operator_status"] = status
        if blocker and not row["next_action"]:
            row["next_action"] = blocker
    return rows


def _manifest_patch_rows(operator_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    index = 1
    for row in operator_rows:
        field_key = row["field_key"]
        if field_key in MANIFEST_COLUMNS:
            patch_status = "ready_to_patch" if row["operator_status"] == "ready" else "awaiting_operator_value"
            rows.append(
                {
                    "patch_id": f"source_gate_patch_{index:03d}",
                    "patch_kind": "manifest_value",
                    "manifest_column": field_key,
                    "source_field_key": field_key,
                    "current_value": row["current_value"],
                    "proposed_value": row["operator_value"],
                    "destination": row["destination"],
                    "patch_status": patch_status,
                    "blockers": "" if patch_status == "ready_to_patch" else f"{field_key}_operator_value_missing",
                    "next_action": "review and apply to internal_prediction_source_manifest_template.csv",
                }
            )
            index += 1
        elif field_key == "prediction_pdb_dropzone":
            rows.append(
                {
                    "patch_id": f"source_gate_patch_{index:03d}",
                    "patch_kind": "file_copy",
                    "manifest_column": "prediction_pdb",
                    "source_field_key": field_key,
                    "current_value": row["current_value"],
                    "proposed_value": row["operator_value"],
                    "destination": row["destination"],
                    "patch_status": "ready_to_copy" if row["operator_status"] == "ready" else "awaiting_file_copy",
                    "blockers": "" if row["operator_status"] == "ready" else "dropzone_prediction_pdb_missing",
                    "next_action": "copy verified prediction PDB into first-slot prediction dropzone",
                }
            )
            index += 1
        elif field_key == "prediction_created_at/native_release_date":
            rows.append(
                {
                    "patch_id": f"source_gate_patch_{index:03d}",
                    "patch_kind": "derived_check",
                    "manifest_column": "prediction_before_native",
                    "source_field_key": field_key,
                    "current_value": row["current_value"],
                    "proposed_value": row["operator_value"],
                    "destination": row["destination"],
                    "patch_status": "ready_derived_check" if row["operator_status"] == "ready" else "awaiting_date_order",
                    "blockers": "" if row["operator_status"] == "ready" else "prediction_not_before_native_or_dates_missing",
                    "next_action": "verify prediction_created_at is before native_release_date",
                }
            )
            index += 1
    return rows


def _status(input_blockers: list[str], operator_rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not operator_rows:
        return "source_gate_operator_packet_clear"
    if all(row["operator_status"] == "ready" for row in operator_rows):
        return "source_gate_operator_packet_ready_for_review"
    return "awaiting_source_gate_operator_values"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    board_payload = _read_json(args.field_board_json)
    board_summary = _summary(board_payload)
    input_blockers = _input_blockers(args)
    operator_rows = _build_operator_rows(args, board_summary, _rows(board_payload)) if not input_blockers else []
    patch_rows = _manifest_patch_rows(operator_rows)
    first = next((row for row in operator_rows if row["operator_status"] != "ready"), operator_rows[0] if operator_rows else {})
    summary = {
        "packet_type": "casp17_strict_blind_source_gate_operator_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_gate_operator_packet_status": _status(input_blockers, operator_rows),
        "source_gate_field_board_status": _text(board_summary.get("source_gate_field_board_status")),
        "required_benchmark_id": _text(board_summary.get("required_benchmark_id")),
        "required_target_id": _text(board_summary.get("required_target_id")),
        "required_scope": _text(board_summary.get("required_scope")),
        "operator_csv": _artifact(_operator_csv_path(args, board_summary)),
        "manifest_csv": _text(board_summary.get("manifest_csv")),
        "field_action_count": len(operator_rows),
        "operator_ready_count": sum(1 for row in operator_rows if row["operator_status"] == "ready"),
        "operator_awaiting_count": sum(1 for row in operator_rows if row["operator_status"] != "ready"),
        "manifest_patch_count": sum(1 for row in patch_rows if row["patch_kind"] == "manifest_value"),
        "file_copy_count": sum(1 for row in patch_rows if row["patch_kind"] == "file_copy"),
        "derived_check_count": sum(1 for row in patch_rows if row["patch_kind"] == "derived_check"),
        "patch_ready_count": sum(1 for row in patch_rows if row["patch_status"].startswith("ready")),
        "patch_awaiting_count": sum(1 for row in patch_rows if not row["patch_status"].startswith("ready")),
        "first_field_key": _text(first.get("field_key")),
        "first_operator_status": _text(first.get("operator_status")),
        "first_next_action": _text(first.get("next_action")),
        "packet_dir": _artifact(_packet_folder(args, board_summary)),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "operator_rows": operator_rows, "patch_rows": patch_rows}


def _write_packet_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(summary["packet_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "source_gate_operator_values.csv", payload["operator_rows"], OPERATOR_COLUMNS)
    _write_csv(folder / "source_gate_manifest_patch_preview.csv", payload["patch_rows"], PATCH_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind Source Gate Operator Packet",
        "",
        f"- status: `{summary['source_gate_operator_packet_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- operator ready/awaiting/total: `{summary['operator_ready_count']}/{summary['operator_awaiting_count']}/{summary['field_action_count']}`",
        f"- patch ready/awaiting: `{summary['patch_ready_count']}/{summary['patch_awaiting_count']}`",
        f"- manifest/file/derived actions: `{summary['manifest_patch_count']}/{summary['file_copy_count']}/{summary['derived_check_count']}`",
        f"- first field: `{summary['first_field_key'] or '-'}` `{summary['first_operator_status'] or '-'}`",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "SOURCE_GATE_OPERATOR_PACKET.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Gate Operator Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_gate_operator_packet_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- operator CSV: `{summary['operator_csv']}`",
        f"- manifest: `{summary['manifest_csv'] or '-'}`",
        f"- operator ready/awaiting/total: `{summary['operator_ready_count']}/{summary['operator_awaiting_count']}/{summary['field_action_count']}`",
        f"- patch ready/awaiting: `{summary['patch_ready_count']}/{summary['patch_awaiting_count']}`",
        f"- manifest/file/derived actions: `{summary['manifest_patch_count']}/{summary['file_copy_count']}/{summary['derived_check_count']}`",
        f"- first field: `{summary['first_field_key'] or '-'}` `{summary['first_operator_status'] or '-'}`",
        "",
        "## Operator Fields",
        "",
        "| field | kind | status | required format | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["operator_rows"]:
        lines.append(
            f"| `{row['field_key']}` | `{row['fill_kind']}` | `{row['operator_status']}` | "
            f"{row['required_format']} | {row['next_action'] or '-'} |"
        )
    if not payload["operator_rows"]:
        lines.append("| - | - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["operator_rows"], OPERATOR_COLUMNS)
    _write_md(args.out_md, payload)
    _write_packet_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build first-slot strict-blind source-gate operator packet.")
    parser.add_argument("--field-board-json", default=DEFAULT_FIELD_BOARD_JSON)
    parser.add_argument("--packet-dir", default=DEFAULT_PACKET_DIR)
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
