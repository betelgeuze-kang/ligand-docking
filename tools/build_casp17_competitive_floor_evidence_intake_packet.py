#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DROPZONE_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_evidence_intake_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_evidence_intake_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_INTAKE.md"

FILE_CLASSES = {"core_file", "ablation_file"}
CLAIM_BOUNDARY = (
    "Local competitive-floor evidence intake only. It audits files and operator-filled fields already placed in "
    "dropzones and writes row_fill patch candidates; it does not choose targets, fetch native structures, clear "
    "provenance, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP."
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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
        fieldnames = ["dropzone_id", "action_rank", "template_column", "intake_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, blockers


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _row_fill_rows_by_path(actions: list[dict[str, Any]]) -> dict[str, tuple[dict[str, str], list[str]]]:
    result: dict[str, tuple[dict[str, str], list[str]]] = {}
    for action in actions:
        row_fill_csv = _text(action.get("source_row_fill_csv"))
        if not row_fill_csv or row_fill_csv in result:
            continue
        rows, blockers = _read_csv(row_fill_csv)
        result[row_fill_csv] = (rows[0] if rows else {}, blockers)
    return result


def _candidate_files(action: dict[str, Any]) -> list[str]:
    expected = _text(action.get("drop_path"))
    if expected and "<HISTORICAL_TARGET_ID>" not in expected and _resolve(expected).is_file():
        return [_artifact(expected)]
    class_folder = _resolve(_text(action.get("dropzone_class_folder")))
    if not class_folder.is_dir():
        return []
    column = _text(action.get("template_column"))
    if column == "prediction_pdb":
        patterns = ["*_prediction.pdb", "*.pdb"]
    elif column == "native_pdb":
        patterns = ["*_native.pdb", "*.pdb"]
    else:
        patterns = ["*.pdb"]
    matches: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(class_folder.glob(pattern)):
            if path.is_file() and path not in seen:
                matches.append(path)
                seen.add(path)
        if matches:
            break
    return [_artifact(path) for path in matches]


def _row_fill_file_present(row_fill_value: str) -> bool:
    return bool(row_fill_value) and not _contains_placeholder(row_fill_value) and _resolve(row_fill_value).is_file()


def _intake_row(action: dict[str, Any], row_fill: dict[str, str], row_fill_blockers: list[str]) -> dict[str, Any]:
    evidence_class = _text(action.get("evidence_class"))
    column = _text(action.get("template_column"))
    row_fill_value = _text(row_fill.get(column))
    candidates = _candidate_files(action) if evidence_class in FILE_CLASSES else []
    candidate_path = candidates[0] if len(candidates) == 1 else ""
    if row_fill_blockers:
        status = "row_fill_blocked"
        recommended_value = ""
    elif evidence_class in FILE_CLASSES:
        if _row_fill_file_present(row_fill_value):
            status = "row_fill_file_present"
            recommended_value = row_fill_value
        elif len(candidates) == 1:
            status = "patch_candidate"
            recommended_value = candidate_path
        elif len(candidates) > 1:
            status = "ambiguous_file_candidates"
            recommended_value = ""
        else:
            status = "awaiting_dropzone_file"
            recommended_value = ""
    elif _contains_placeholder(row_fill_value):
        status = "awaiting_operator_value"
        recommended_value = ""
    else:
        status = "field_present_needs_worklist_rerun"
        recommended_value = row_fill_value
    dropzone_folder = _text(action.get("dropzone_folder"))
    batch_folder = _resolve(dropzone_folder).parent if dropzone_folder else _resolve(".")
    patch_csv = batch_folder / "ROW_FILL_PATCH_CANDIDATE.csv"
    guide_md = batch_folder / "EVIDENCE_INTAKE.md"
    return {
        "dropzone_id": _text(action.get("dropzone_id")),
        "action_rank": _int(action.get("action_rank")),
        "operator_priority": _int(action.get("operator_priority")),
        "row_rank": _int(action.get("row_rank")),
        "benchmark_id": _text(action.get("benchmark_id")),
        "target_id": _text(action.get("target_id")),
        "scope": _text(action.get("scope")),
        "evidence_class": evidence_class,
        "template_column": column,
        "blocker": _text(action.get("blocker")),
        "source_row_fill_csv": _text(action.get("source_row_fill_csv")),
        "row_fill_value": row_fill_value,
        "dropzone_class_folder": _text(action.get("dropzone_class_folder")),
        "expected_drop_path": _text(action.get("drop_path")),
        "candidate_count": len(candidates),
        "candidate_paths": ";".join(candidates),
        "recommended_value": recommended_value,
        "patch_candidate_csv": _artifact(patch_csv),
        "intake_guide_md": _artifact(guide_md),
        "intake_status": status,
        "next_action": _next_action(status, column),
    }


def _next_action(status: str, column: str) -> str:
    if status == "patch_candidate":
        return f"copy recommended_value into {column} in row_fill.csv, then rerun row-fill status and worklist"
    if status == "row_fill_file_present":
        return "rerun row-fill status and operator-template validation"
    if status == "ambiguous_file_candidates":
        return "leave exactly one intended local PDB in this dropzone folder or update row_fill.csv manually"
    if status == "awaiting_dropzone_file":
        return "place the validated no-leak local PDB in the indicated dropzone folder"
    if status == "field_present_needs_worklist_rerun":
        return "rerun row-fill worklist to validate this operator-filled field"
    if status == "row_fill_blocked":
        return "repair row_fill.csv before ingesting dropzone evidence"
    return f"fill {column} in row_fill.csv from cleared local evidence"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dropzone_payload = _read_json(args.dropzone_json)
    dropzone_summary = _summary(dropzone_payload)
    actions = _rows(dropzone_payload)
    row_fills = _row_fill_rows_by_path(actions)
    rows: list[dict[str, Any]] = []
    for action in actions:
        row_fill_csv = _text(action.get("source_row_fill_csv"))
        row_fill, blockers = row_fills.get(row_fill_csv, ({}, ["row_fill_csv_missing"]))
        rows.append(_intake_row(action, row_fill, blockers))
    by_status = defaultdict(int)
    by_class = defaultdict(int)
    dropzone_ids: set[str] = set()
    for row in rows:
        by_status[str(row["intake_status"])] += 1
        by_class[str(row["evidence_class"])] += 1
        if row["dropzone_id"]:
            dropzone_ids.add(str(row["dropzone_id"]))
    first_open = next(
        (
            row
            for row in rows
            if row["intake_status"]
            not in {"row_fill_file_present", "field_present_needs_worklist_rerun"}
        ),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_competitive_floor_evidence_intake",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_status": _intake_status(rows, by_status),
        "dropzone_json": _artifact(args.dropzone_json),
        "dropzone_status": _text(dropzone_summary.get("dropzone_status")),
        "dropzone_count": len(dropzone_ids),
        "action_count": len(rows),
        "file_action_count": by_class["core_file"] + by_class["ablation_file"],
        "field_action_count": len(rows) - by_class["core_file"] - by_class["ablation_file"],
        "patch_candidate_count": by_status["patch_candidate"],
        "row_fill_file_present_count": by_status["row_fill_file_present"],
        "ambiguous_file_candidate_count": by_status["ambiguous_file_candidates"],
        "awaiting_dropzone_file_count": by_status["awaiting_dropzone_file"],
        "field_present_count": by_status["field_present_needs_worklist_rerun"],
        "awaiting_operator_value_count": by_status["awaiting_operator_value"],
        "row_fill_blocked_count": by_status["row_fill_blocked"],
        "patch_candidate_row_count": len({row["dropzone_id"] for row in rows if row["intake_status"] == "patch_candidate"}),
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _text(first_open.get("intake_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _intake_status(rows: list[dict[str, Any]], by_status: dict[str, int]) -> str:
    if not rows:
        return "ready"
    if by_status["patch_candidate"] or by_status["row_fill_file_present"] or by_status["field_present_needs_worklist_rerun"]:
        return "ready_for_operator_patch"
    return "awaiting_evidence"


def _write_intake_guides(payload: dict[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        grouped[_text(row.get("dropzone_id"))].append(row)
    for dropzone_id, rows in grouped.items():
        if not dropzone_id or not rows:
            continue
        rows.sort(key=lambda row: int(row["action_rank"]))
        guide = _resolve(rows[0]["intake_guide_md"])
        patch_csv = _resolve(rows[0]["patch_candidate_csv"])
        patch_rows = [
            {
                "template_column": row["template_column"],
                "current_value": row["row_fill_value"],
                "recommended_value": row["recommended_value"],
                "intake_status": row["intake_status"],
                "candidate_count": row["candidate_count"],
                "next_action": row["next_action"],
            }
            for row in rows
        ]
        _write_csv(patch_csv, patch_rows)
        lines = [
            "# CASP17 Competitive-Floor Evidence Intake",
            "",
            f"- dropzone_id: `{dropzone_id}`",
            f"- row_fill_csv: `{rows[0]['source_row_fill_csv']}`",
            f"- patch_candidate_csv: `{_artifact(patch_csv)}`",
            f"- open intake rows: `{len(rows)}`",
            "",
            "| rank | class | column | status | recommended value | next action |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| {row['action_rank']} | `{row['evidence_class']}` | `{row['template_column']}` | "
                f"`{row['intake_status']}` | `{row['recommended_value'] or '-'}` | {row['next_action']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Evidence Intake",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- intake_status: `{summary['intake_status']}`",
        f"- dropzones: `{summary['dropzone_count']}`",
        f"- actions: `{summary['action_count']}`",
        f"- file/field actions: `{summary['file_action_count']}/{summary['field_action_count']}`",
        f"- patch candidates: `{summary['patch_candidate_count']}` rows `{summary['patch_candidate_row_count']}`",
        f"- row_fill files already present: `{summary['row_fill_file_present_count']}`",
        f"- awaiting files/operator values: `{summary['awaiting_dropzone_file_count']}/{summary['awaiting_operator_value_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_column'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Intake Rows",
        "",
        "| rank | dropzone | class | column | status | candidates | recommended | next action |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | `{row['dropzone_id']}` | `{row['evidence_class']}` | "
            f"`{row['template_column']}` | `{row['intake_status']}` | {row['candidate_count']} | "
            f"`{row['recommended_value'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | - | - | 0 | - | no open intake rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.write_guides:
        _write_intake_guides(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit competitive-floor evidence dropzones and emit row_fill patch candidates.")
    parser.add_argument("--dropzone-json", default=DEFAULT_DROPZONE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--write-guides", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
