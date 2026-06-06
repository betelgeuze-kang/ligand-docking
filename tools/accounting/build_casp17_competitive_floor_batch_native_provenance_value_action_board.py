#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from tools import build_casp17_competitive_floor_batch_native_provenance_value_gate as gate


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_VALUE_GATE_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_value_gate_current.json"
DEFAULT_OUT_DIR = "casp17/competitive_floor_batch_native_provenance_value_action_board"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_value_action_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_batch_native_provenance_value_action_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_BATCH_NATIVE_PROVENANCE_VALUE_ACTION_BOARD.md"

ROW_COLUMNS = [
    "action_id",
    "queue_rank",
    "target_id",
    "target_name",
    "target_action_folder",
    "field_name",
    "field_group",
    "field_status",
    "action_status",
    "blocker",
    "required_value_policy",
    "current_value",
    "operator_fill_intake_csv",
    "verify_command",
    "next_action",
    "competitive_proof_eligible",
    "author_serialized",
]
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor batch native/provenance value action board only. It expands the dry value gate "
    "into field-level operator actions and target-named folders. It does not fill values, fetch native structures, "
    "copy coordinate files, clear no-leak provenance, compute native accuracy, serialize a CASP author code, or "
    "submit to CASP."
)

FIELD_BLOCKER_MAP = {
    "native_source_pdb_required": ("native_source_pdb", "native_file", "local protein PDB path distinct from prediction"),
    "native_source_pdb_missing": ("native_source_pdb", "native_file", "existing local protein PDB path"),
    "native_source_pdb_not_file": ("native_source_pdb", "native_file", "local file path"),
    "native_source_pdb_has_no_atom_records": ("native_source_pdb", "native_file", "PDB with ATOM records"),
    "native_source_pdb_has_no_protein_atom_records": ("native_source_pdb", "native_file", "PDB with protein ATOM records"),
    "native_source_pdb_coordinates_invalid": ("native_source_pdb", "native_file", "PDB with valid XYZ coordinates"),
    "native_pdb_same_path_as_prediction_pdb": ("native_source_pdb", "native_file", "native path distinct from prediction"),
    "native_pdb_identical_to_prediction_pdb": ("native_source_pdb", "native_file", "native content distinct from prediction"),
    "no_leak_evidence_ref_required": ("no_leak_evidence_ref", "evidence", "local no-leak evidence file"),
    "no_leak_evidence_ref_missing": ("no_leak_evidence_ref", "evidence", "existing local evidence file"),
    "no_leak_evidence_ref_must_be_local_file": ("no_leak_evidence_ref", "evidence", "local evidence file, not URL"),
    "no_leak_evidence_ref_empty": ("no_leak_evidence_ref", "evidence", "non-empty no-leak evidence"),
    "no_leak_evidence_target_id_missing": ("no_leak_evidence_ref", "evidence", "evidence mentioning target id"),
    "no_leak_evidence_marker_missing": ("no_leak_evidence_ref", "evidence", "evidence containing no-leak marker"),
    "no_leak_evidence_is_request_template": ("no_leak_evidence_ref", "evidence", "completed evidence, not request template"),
    "leakage_clearance_required": ("leakage_clearance", "clearance", "cleared/no_leak style clearance value"),
    "operator_clearance_required": ("operator_clearance", "clearance", "operator-cleared value"),
    "operator_required": ("operator", "operator", "operator id"),
    "prediction_created_at_required_iso_date": ("prediction_created_at", "date", "ISO date before native release"),
    "native_release_date_required_iso_date": ("native_release_date", "date", "ISO native release date"),
    "prediction_date_not_before_native_release": ("prediction_created_at", "date", "prediction date before native release"),
    "prediction_generated_before_native_release_required": (
        "prediction_generated_before_native_release",
        "boolean",
        "true confirmation",
    ),
    "public_template_or_native_used_for_prediction_must_be_false": (
        "public_template_or_native_used_for_prediction",
        "boolean",
        "false confirmation",
    ),
    "other_team_model_used_must_be_false": ("other_team_model_used", "boolean", "false confirmation"),
    "post_release_information_used_must_be_false": ("post_release_information_used", "boolean", "false confirmation"),
    "current_casp17_target_must_be_false": ("current_casp17_target", "boolean", "false confirmation"),
}


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


def _blockers(row: dict[str, Any]) -> list[str]:
    return [part for part in (_text(item) for item in _text(row.get("blockers")).split(",")) if part]


def _target_folder(out_dir: str | Path, row: dict[str, Any]) -> str:
    target_id = _text(row.get("target_id")).upper()
    target_name = _safe_slug(_text(row.get("target_name")) or target_id)
    return _artifact(_resolve(out_dir) / f"{target_id}_{target_name}")


def _current_value(row: dict[str, Any], field_name: str) -> str:
    if field_name == "no_leak_evidence_ref":
        return _text(row.get("no_leak_evidence_ref"))
    return _text(row.get(field_name))


def _action_row(
    row: dict[str, Any],
    *,
    blocker: str,
    queue_rank: int,
    out_dir: str | Path,
    batch_intake_csv: str,
) -> dict[str, Any]:
    field_name, field_group, policy = FIELD_BLOCKER_MAP.get(blocker, ("operator_review", "review", "manual review"))
    target_id = _text(row.get("target_id")).upper()
    return {
        "action_id": f"{target_id}_value_action_{queue_rank:03d}",
        "queue_rank": queue_rank,
        "target_id": target_id,
        "target_name": _text(row.get("target_name")),
        "target_action_folder": _target_folder(out_dir, row),
        "field_name": field_name,
        "field_group": field_group,
        "field_status": _text(row.get(f"{field_name}_status")) or "blocked",
        "action_status": "open_operator_value",
        "blocker": blocker,
        "required_value_policy": policy,
        "current_value": _current_value(row, field_name),
        "operator_fill_intake_csv": batch_intake_csv,
        "verify_command": "python3 tools/build_casp17_competitive_floor_batch_native_provenance_value_gate.py",
        "next_action": _next_action(field_name, policy, batch_intake_csv),
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }


def _next_action(field_name: str, policy: str, batch_intake_csv: str) -> str:
    return f"Fill {field_name} in {batch_intake_csv} with {policy}, then rerun the value gate."


def _action_rows(gate_rows: list[dict[str, Any]], *, out_dir: str | Path, batch_intake_csv: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    queue_rank = 1
    for gate_row in gate_rows:
        for blocker in _blockers(gate_row):
            rows.append(
                _action_row(
                    gate_row,
                    blocker=blocker,
                    queue_rank=queue_rank,
                    out_dir=out_dir,
                    batch_intake_csv=batch_intake_csv,
                )
            )
            queue_rank += 1
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    value_gate_payload = _read_json(args.value_gate_json)
    value_gate_summary = _summary(value_gate_payload)
    gate_rows = _rows(value_gate_payload)
    input_blockers: list[str] = []
    if not _resolve(args.value_gate_json).exists():
        input_blockers.append("batch_native_provenance_value_gate_json_missing")
    batch_intake_csv = _text(value_gate_summary.get("batch_operator_fill_intake_csv"))
    if not batch_intake_csv:
        input_blockers.append("batch_operator_fill_intake_csv_missing")
    rows = _action_rows(gate_rows, out_dir=args.out_dir, batch_intake_csv=batch_intake_csv)
    summary = _build_summary(args, value_gate_summary, rows, input_blockers)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    value_gate_summary: dict[str, Any],
    rows: list[dict[str, Any]],
    input_blockers: list[str],
) -> dict[str, Any]:
    target_ids = sorted({row["target_id"] for row in rows})
    field_groups = {group: sum(1 for row in rows if row["field_group"] == group) for group in _field_group_order()}
    first = rows[0] if rows else {}
    status = "casp17_competitive_floor_batch_native_provenance_value_action_board_open_actions"
    if input_blockers:
        status = "casp17_competitive_floor_batch_native_provenance_value_action_board_blocked_missing_inputs"
    elif not rows:
        status = "casp17_competitive_floor_batch_native_provenance_value_action_board_ready_no_open_actions"
    return {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_value_action_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_native_provenance_value_action_board_status": status,
        "value_gate_json": _artifact(args.value_gate_json),
        "value_gate_status": _text(value_gate_summary.get("batch_native_provenance_value_gate_status")),
        "batch_operator_fill_intake_csv": _text(value_gate_summary.get("batch_operator_fill_intake_csv")),
        "out_dir": _artifact(args.out_dir),
        "target_count": _int(value_gate_summary.get("target_count")),
        "target_with_open_action_count": len(target_ids),
        "target_ready_count": max(0, _int(value_gate_summary.get("target_count")) - len(target_ids)),
        "action_count": len(rows),
        "open_action_count": len(rows),
        "native_action_count": field_groups["native_file"],
        "evidence_action_count": field_groups["evidence"],
        "clearance_action_count": field_groups["clearance"],
        "operator_action_count": field_groups["operator"],
        "date_action_count": field_groups["date"],
        "boolean_action_count": field_groups["boolean"],
        "review_action_count": field_groups["review"],
        "coordinate_copy_count": 0,
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_open_action_id": _text(first.get("action_id")),
        "first_open_target_id": _text(first.get("target_id")),
        "first_open_field": _text(first.get("field_name")),
        "first_open_blocker": _text(first.get("blocker")),
        "first_next_action": _text(first.get("next_action")),
        "input_blockers": ",".join(input_blockers),
        "next_action": _text(first.get("next_action")) or "rerun value gate after operator values are filled.",
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _field_group_order() -> list[str]:
    return ["native_file", "evidence", "clearance", "operator", "date", "boolean", "review"]


def _write_target_files(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(payload["summary"]["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for row in payload["rows"]:
        rows_by_target.setdefault(row["target_id"], []).append(row)
    for target_id, rows in rows_by_target.items():
        folder = _resolve(rows[0]["target_action_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "value_actions.csv", rows, ROW_COLUMNS)
        readme_lines = [
            f"# CASP17 Batch Native/Provenance Value Actions: {target_id}",
            "",
            f"- target: `{target_id}` `{rows[0]['target_name']}`",
            f"- open actions: `{len(rows)}`",
            f"- first blocker: `{rows[0]['blocker']}`",
            f"- intake CSV: `{rows[0]['operator_fill_intake_csv']}`",
            "",
            "## Actions",
            "",
            "| rank | field | group | blocker | next action |",
            "| ---: | --- | --- | --- | --- |",
        ]
        for row in rows:
            readme_lines.append(
                f"| `{row['queue_rank']}` | `{row['field_name']}` | `{row['field_group']}` | "
                f"`{row['blocker']}` | {row['next_action']} |"
            )
        readme_lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")
    manifest = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_value_action_board_manifest",
        "target_ids": sorted(rows_by_target),
        "action_count": len(payload["rows"]),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _write_json(out_dir / "manifest.json", manifest)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Batch Native/Provenance Value Action Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_native_provenance_value_action_board_status']}`",
        f"- targets open/ready/total: `{summary['target_with_open_action_count']}/{summary['target_ready_count']}/{summary['target_count']}`",
        f"- actions open/total: `{summary['open_action_count']}/{summary['action_count']}`",
        f"- lanes native/evidence/clearance/operator/date/boolean/review: `{summary['native_action_count']}/{summary['evidence_action_count']}/{summary['clearance_action_count']}/{summary['operator_action_count']}/{summary['date_action_count']}/{summary['boolean_action_count']}/{summary['review_action_count']}`",
        f"- coordinate copies: `{summary['coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_field'] or '-'}` `{summary['first_open_blocker'] or '-'}`",
        f"- out dir: `{summary['out_dir']}`",
        "",
        "## Actions",
        "",
        "| rank | target | field | group | blocker |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['queue_rank']}` | `{row['target_id']}` | `{row['field_name']}` | "
            f"`{row['field_group']}` | `{row['blocker']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_target_files(args, payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 batch native/provenance value action board.")
    parser.add_argument("--value-gate-json", default=DEFAULT_VALUE_GATE_JSON)
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
