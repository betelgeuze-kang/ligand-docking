#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_BOARD_DIR = "casp17/strict_blind_source_gate_field_board"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_gate_field_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_gate_field_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_GATE_FIELD_BOARD.md"

ROW_COLUMNS = [
    "field_key",
    "fill_kind",
    "field_status",
    "affected_check_ids",
    "blocked_check_count",
    "pass_check_count",
    "current_value",
    "destination",
    "source_manifest",
    "blockers",
    "next_action",
]
CHECK_FIELD_MAP = {
    "manifest_exists": ("internal_source_manifest", "manifest_file"),
    "source_id_internal": ("source_id", "manifest_value"),
    "target_id_present": ("target_id", "manifest_value"),
    "scope_matches": ("scope", "manifest_value"),
    "manifest_prediction_pdb_present": ("prediction_pdb", "file"),
    "manifest_prediction_pdb_exists": ("prediction_pdb", "file"),
    "dropzone_prediction_pdb_exists": ("prediction_pdb_dropzone", "file"),
    "prediction_pdb_has_atom_records": ("prediction_pdb", "file"),
    "prediction_created_at_present": ("prediction_created_at", "manifest_value"),
    "native_release_date_present": ("native_release_date", "manifest_value"),
    "prediction_before_native": ("prediction_created_at/native_release_date", "manifest_value"),
    "native_authority_ref_present": ("native_authority_ref", "manifest_value"),
    "creation_evidence_ref_present": ("creation_evidence_ref", "manifest_value"),
    "no_leak_evidence_ref_present": ("no_leak_evidence_ref", "manifest_value"),
    "method_summary_present": ("method_summary", "manifest_value"),
    "operator_clearance_present": ("operator_clearance", "manifest_value"),
}
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-gate field board only. It condenses internal prediction source-gate "
    "checks into unique field/file actions for the first strict-blind slot. It does not fill operator values, "
    "copy evidence files, approve provenance, compute CASP metrics, push remotes, or submit to CASP."
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _input_blockers(args: argparse.Namespace) -> list[str]:
    return ["source_gate_json_missing"] if not _resolve(args.source_gate_json).exists() else []


def _unique_join(values: list[str]) -> str:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return ",".join(out)


def _group_rows(gate_summary: dict[str, Any], gate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in gate_rows:
        if _text(row.get("check_status")) == "pass":
            continue
        check_id = _text(row.get("check_id"))
        field_key, fill_kind = CHECK_FIELD_MAP.get(check_id, (check_id, "manifest_value"))
        groups.setdefault((field_key, fill_kind), []).append(row)

    rows: list[dict[str, Any]] = []
    manifest_csv = _text(gate_summary.get("manifest_csv"))
    dropzone = _text(gate_summary.get("prediction_dropzone"))
    for (field_key, fill_kind), check_rows in groups.items():
        check_ids = [_text(row.get("check_id")) for row in check_rows]
        blockers = [_text(row.get("blocker")) for row in check_rows]
        next_actions = [_text(row.get("next_action")) for row in check_rows]
        actuals = [_text(row.get("actual_value")) for row in check_rows]
        destination = manifest_csv
        if field_key == "prediction_pdb_dropzone":
            destination = dropzone
        elif fill_kind == "file":
            destination = _unique_join([value for value in actuals if value])
        rows.append(
            {
                "field_key": field_key,
                "fill_kind": fill_kind,
                "field_status": "blocked",
                "affected_check_ids": _unique_join(check_ids),
                "blocked_check_count": len(check_rows),
                "pass_check_count": 0,
                "current_value": _unique_join(actuals),
                "destination": destination,
                "source_manifest": manifest_csv,
                "blockers": _unique_join(blockers),
                "next_action": "; ".join(action for action in next_actions if action),
            }
        )
    return rows


def _status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if rows:
        return "awaiting_source_gate_field_fills"
    return "source_gate_field_board_clear"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_payload = _read_json(args.source_gate_json)
    gate_summary = _summary(gate_payload)
    input_blockers = _input_blockers(args)
    rows = _group_rows(gate_summary, _rows(gate_payload))
    first = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_strict_blind_source_gate_field_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_gate_field_board_status": _status(input_blockers, rows),
        "source_gate_status": _text(gate_summary.get("internal_prediction_source_gate_status")),
        "required_benchmark_id": _text(gate_summary.get("required_benchmark_id")),
        "required_target_id": _text(gate_summary.get("required_target_id")),
        "required_scope": _text(gate_summary.get("required_scope")),
        "manifest_csv": _text(gate_summary.get("manifest_csv")),
        "source_gate_check_count": len(_rows(gate_payload)),
        "source_gate_pass_count": int(gate_summary.get("pass_count") or 0),
        "source_gate_blocked_count": int(gate_summary.get("blocked_count") or 0),
        "field_action_count": len(rows),
        "manifest_value_action_count": sum(1 for row in rows if row["fill_kind"] == "manifest_value"),
        "file_action_count": sum(1 for row in rows if row["fill_kind"] == "file"),
        "manifest_file_action_count": sum(1 for row in rows if row["fill_kind"] == "manifest_file"),
        "blocked_check_covered_count": sum(int(row["blocked_check_count"]) for row in rows),
        "first_field_key": _text(first.get("field_key")),
        "first_fill_kind": _text(first.get("fill_kind")),
        "first_blockers": _text(first.get("blockers")),
        "first_next_action": _text(first.get("next_action")),
        "board_dir": _artifact(_resolve(args.board_dir) / (_text(gate_summary.get("required_benchmark_id")) or "hist_REQUIRED_MONOMER_001")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_board_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(args.board_dir) / (summary["required_benchmark_id"] or "hist_REQUIRED_MONOMER_001")
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "source_gate_field_board.csv", payload["rows"], ROW_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind Source Gate Field Board",
        "",
        f"- status: `{summary['source_gate_field_board_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- source gate: `{summary['source_gate_status']}` checks pass/blocked/total `{summary['source_gate_pass_count']}/{summary['source_gate_blocked_count']}/{summary['source_gate_check_count']}`",
        f"- field actions manifest/file/manifest-file/total: `{summary['manifest_value_action_count']}/{summary['file_action_count']}/{summary['manifest_file_action_count']}/{summary['field_action_count']}`",
        f"- first field: `{summary['first_field_key'] or '-'}` `{summary['first_blockers'] or '-'}`",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "SOURCE_GATE_FIELD_BOARD.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Gate Field Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_gate_field_board_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- manifest: `{summary['manifest_csv'] or '-'}`",
        f"- source gate: `{summary['source_gate_status']}` checks pass/blocked/total `{summary['source_gate_pass_count']}/{summary['source_gate_blocked_count']}/{summary['source_gate_check_count']}`",
        f"- field actions manifest/file/manifest-file/total: `{summary['manifest_value_action_count']}/{summary['file_action_count']}/{summary['manifest_file_action_count']}/{summary['field_action_count']}`",
        f"- blocked checks covered: `{summary['blocked_check_covered_count']}`",
        f"- first field: `{summary['first_field_key'] or '-'}` `{summary['first_fill_kind'] or '-'}` `{summary['first_blockers'] or '-'}`",
        "",
        "## Field Actions",
        "",
        "| field | kind | checks | blockers | destination | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_key']}` | `{row['fill_kind']}` | `{row['affected_check_ids']}` | "
            f"`{row['blockers']}` | `{row['destination']}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_board_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build first-slot strict-blind source-gate field board.")
    parser.add_argument("--source-gate-json", default=DEFAULT_GATE_JSON)
    parser.add_argument("--board-dir", default=DEFAULT_BOARD_DIR)
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
