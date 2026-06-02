#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WORKLIST_JSON = "casp17/casp17_organic_ligand_metric_operator_fill_worklist_current.json"
DEFAULT_OUT_DIR = "casp17/organic_ligand_metric_first_operator_fill_kit"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_metric_first_operator_fill_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_metric_first_operator_fill_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_METRIC_FIRST_OPERATOR_FILL_KIT.md"

READY_STATUS = "field_ready_for_review_gate"
RERUN_COMMANDS = [
    "python3 tools/build_casp17_organic_ligand_metric_evidence_review_gate.py",
    "python3 tools/build_casp17_organic_ligand_metric_operator_fill_worklist.py",
    "python3 tools/build_casp17_organic_ligand_metric_first_operator_fill_kit.py",
    "python3 tools/build_casp17_organic_ligand_metric_evidence_sync_plan.py",
    "python3 tools/build_casp17_workbench_index.py",
]
FIELD_COLUMNS = [
    "fill_id",
    "candidate_rank",
    "candidate_id",
    "target_id",
    "ligand_id",
    "field_order",
    "field_key",
    "required_operator_value_format",
    "source_operator_template_csv",
    "source_evidence_stub_md",
    "linked_action_md",
    "operator_value",
    "operator_evidence_ref",
    "operator_clearance",
    "operator_id",
    "fill_status",
    "first_blocker",
    "next_action",
]
ROW_COLUMNS = [
    "candidate_id",
    "target_id",
    "ligand_id",
    "kit_status",
    "kit_folder",
    "operator_fill_template_csv",
    "field_action_csv",
    "rerun_commands_md",
    "kit_manifest_json",
    "field_count",
    "field_ready_count",
    "field_blocked_count",
    "operator_value_missing_count",
    "operator_evidence_ref_missing_count",
    "operator_clearance_missing_count",
    "operator_id_missing_count",
    "source_template_count",
    "source_stub_count",
    "linked_action_count",
    "first_field_key",
    "first_blocker",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 organic ligand metric first-operator-fill kit only. It focuses the first blocked organic "
    "ligand candidate into one manual fill folder with source template, evidence stub, linked action, and "
    "rerun commands. It does not mutate evidence templates, fill operator values, approve no-leak provenance, "
    "compute LDDT-PLI or BiSyRMSD, mark competitive proof, serialize a CASP author code, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
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
    slug = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value).strip("_")
    return slug[:140] or "organic_ligand_candidate"


def _selected_candidate_id(args: argparse.Namespace, rows: list[dict[str, Any]]) -> str:
    explicit = _text(args.candidate_id)
    if explicit:
        return explicit
    first_blocked = next((row for row in rows if _text(row.get("fill_status")) != READY_STATUS), {})
    if first_blocked:
        return _text(first_blocked.get("candidate_id"))
    return _text(rows[0].get("candidate_id")) if rows else ""


def _candidate_rows(rows: list[dict[str, Any]], candidate_id: str) -> list[dict[str, Any]]:
    selected = [row for row in rows if _text(row.get("candidate_id")) == candidate_id]
    return sorted(selected, key=lambda row: (_int(row.get("field_order")), _text(row.get("field_key"))))


def _field_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{column: _text(row.get(column)) for column in FIELD_COLUMNS} for row in rows]


def _status(input_missing: bool, selected_missing: bool, rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_organic_ligand_metric_operator_fill_worklist_missing"
    if selected_missing:
        return "blocked_organic_ligand_metric_first_candidate_missing"
    if not rows:
        return "blocked_organic_ligand_metric_first_fill_fields_missing"
    if any(_text(row.get("fill_status")) != READY_STATUS for row in rows):
        return "organic_ligand_metric_first_operator_fill_kit_ready_for_operator_fill"
    return "organic_ligand_metric_first_operator_fill_kit_complete"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    worklist_path = _resolve(args.worklist_json)
    worklist_payload = _read_json(worklist_path)
    worklist_summary = _summary(worklist_payload)
    worklist_rows = _rows(worklist_payload) if worklist_path.exists() else []
    candidate_id = _selected_candidate_id(args, worklist_rows)
    rows = _candidate_rows(worklist_rows, candidate_id) if candidate_id else []
    selected_missing = bool(candidate_id and not rows)
    ready_count = sum(1 for row in rows if _text(row.get("fill_status")) == READY_STATUS)
    blocked_rows = [row for row in rows if _text(row.get("fill_status")) != READY_STATUS]
    first = blocked_rows[0] if blocked_rows else (rows[0] if rows else {})
    ligand_id = _text(first.get("ligand_id")) or candidate_id
    target_id = _text(first.get("target_id"))
    kit_folder = _artifact(_resolve(args.out_dir) / f"{_safe_slug(candidate_id)}_{_safe_slug(ligand_id)}")
    status = _status(not worklist_path.exists(), selected_missing, rows)
    summary = {
        "packet_type": "casp17_organic_ligand_metric_first_operator_fill_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_metric_first_operator_fill_kit_status": status,
        "worklist_json": _artifact(args.worklist_json),
        "worklist_status": _text(worklist_summary.get("organic_ligand_metric_operator_fill_worklist_status")),
        "candidate_id": candidate_id,
        "target_id": target_id,
        "ligand_id": ligand_id,
        "kit_folder": kit_folder,
        "operator_fill_template_csv": _artifact(_resolve(kit_folder) / "operator_fill_template.csv"),
        "field_action_csv": _artifact(_resolve(kit_folder) / "field_actions.csv"),
        "rerun_commands_md": _artifact(_resolve(kit_folder) / "RERUN_COMMANDS.md"),
        "kit_manifest_json": _artifact(_resolve(kit_folder) / "kit_manifest.json"),
        "field_count": len(rows),
        "field_ready_count": ready_count,
        "field_blocked_count": len(rows) - ready_count,
        "operator_value_missing_count": sum(1 for row in rows if _text(row.get("value_status")) != "value_present"),
        "operator_evidence_ref_missing_count": sum(
            1 for row in rows if _text(row.get("evidence_ref_status")) != "evidence_ref_present"
        ),
        "operator_clearance_missing_count": sum(
            1 for row in rows if _text(row.get("clearance_status")) != "clearance_present"
        ),
        "operator_id_missing_count": sum(
            1 for row in rows if _text(row.get("operator_id_status")) != "operator_id_present"
        ),
        "source_template_count": len({row.get("source_operator_template_csv") for row in rows if row.get("source_operator_template_csv")}),
        "source_stub_count": len({row.get("source_evidence_stub_md") for row in rows if row.get("source_evidence_stub_md")}),
        "linked_action_count": len({row.get("linked_action_md") for row in rows if row.get("linked_action_md")}),
        "first_fill_id": _text(first.get("fill_id")),
        "first_field_key": _text(first.get("field_key")),
        "first_blocker": _text(first.get("first_blocker")),
        "first_next_action": _text(first.get("next_action")),
        "next_action": _text(first.get("next_action"))
        or "fill the first organic ligand operator evidence template, then rerun the listed commands",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": _field_rows(rows), "rerun_commands": RERUN_COMMANDS}


def _packet_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    return {column: summary.get(column, "") for column in ROW_COLUMNS}


def _write_kit_folder(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(summary["kit_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "operator_fill_template.csv", payload["rows"], FIELD_COLUMNS)
    _write_csv(folder / "field_actions.csv", payload["rows"], FIELD_COLUMNS)
    _write_json(
        folder / "kit_manifest.json",
        {
            "summary": summary,
            "claim_boundary": CLAIM_BOUNDARY,
            "rerun_commands": payload["rerun_commands"],
        },
    )
    (folder / "RERUN_COMMANDS.md").write_text(
        "\n".join(["# Rerun Commands", "", *[f"- `{command}`" for command in payload["rerun_commands"]], ""]),
        encoding="utf-8",
    )
    lines = [
        f"# {summary['candidate_id']} Organic Ligand First Operator Fill Kit",
        "",
        f"- status: `{summary['organic_ligand_metric_first_operator_fill_kit_status']}`",
        f"- target: `{summary['target_id'] or '-'}`",
        f"- ligand: `{summary['ligand_id'] or '-'}`",
        f"- fields ready/blocked/total: `{summary['field_ready_count']}/{summary['field_blocked_count']}/{summary['field_count']}`",
        f"- missing value/evidence/clearance/operator: `{summary['operator_value_missing_count']}/{summary['operator_evidence_ref_missing_count']}/{summary['operator_clearance_missing_count']}/{summary['operator_id_missing_count']}`",
        f"- first field: `{summary['first_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Fields",
        "",
        "| field | status | source template | evidence stub | linked action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_key']}` | `{row['fill_status']}` | "
            f"`{row['source_operator_template_csv'] or '-'}` | "
            f"`{row['source_evidence_stub_md'] or '-'}` | "
            f"`{row['linked_action_md'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Metric First Operator Fill Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_metric_first_operator_fill_kit_status']}`",
        f"- candidate: `{summary['candidate_id'] or '-'}`",
        f"- target: `{summary['target_id'] or '-'}`",
        f"- ligand: `{summary['ligand_id'] or '-'}`",
        f"- kit folder: `{summary['kit_folder']}`",
        f"- fields ready/blocked/total: `{summary['field_ready_count']}/{summary['field_blocked_count']}/{summary['field_count']}`",
        f"- missing value/evidence/clearance/operator: `{summary['operator_value_missing_count']}/{summary['operator_evidence_ref_missing_count']}/{summary['operator_clearance_missing_count']}/{summary['operator_id_missing_count']}`",
        f"- first field: `{summary['first_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Kit Files",
        "",
        f"- operator fill template: `{summary['operator_fill_template_csv']}`",
        f"- field actions: `{summary['field_action_csv']}`",
        f"- rerun commands: `{summary['rerun_commands_md']}`",
        f"- manifest: `{summary['kit_manifest_json']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_kit_folder(payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [_packet_row(payload)], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand metric first operator fill kit.")
    parser.add_argument("--worklist-json", default=DEFAULT_WORKLIST_JSON)
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
