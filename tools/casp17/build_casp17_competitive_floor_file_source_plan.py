#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_IDENTITY_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_IDENTITY_KIT_CSV = "casp17/casp17_competitive_floor_identity_unlock_kit_current.csv"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_file_source_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_file_source_plan_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_FILE_SOURCE_PLAN.md"

FILE_CLASSES = {"core_file", "ablation_file"}
CLEAR_VALUES = {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak"}
PLAN_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "file_rank",
    "evidence_class",
    "template_column",
    "identity_status",
    "proposed_target_id",
    "source_path",
    "recommended_drop_filename",
    "canonical_destination_path",
    "file_source_status",
    "blocker",
    "source_sha256",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor file source plan only. It maps cleared historical target identities to required "
    "prediction, native, and ablation PDB source-path actions and audits local file readiness. It does not choose "
    "historical targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, "
    "mutate row_fill.csv, copy files, or submit to CASP."
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
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, fieldnames, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    if not resolved:
        resolved = PLAN_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _identity_rows(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    payload = _read_json(args.identity_kit_json)
    rows = payload.get("rows")
    if isinstance(rows, list):
        return {_text(row.get("dropzone_id")): row for row in rows if isinstance(row, dict) and _text(row.get("dropzone_id"))}
    csv_rows, _fieldnames, blockers = _read_csv(args.identity_kit_csv)
    if blockers:
        return {}
    return {_text(row.get("dropzone_id")): row for row in csv_rows if _text(row.get("dropzone_id"))}


def _current_targets(path_like: str | Path) -> set[str]:
    rows, _fieldnames, blockers = _read_csv(path_like)
    if blockers:
        return set()
    return {_text(row.get("target_id")).upper() for row in rows if _text(row.get("target_id"))}


def _file_import_rows(path_like: str | Path) -> list[dict[str, str]]:
    rows, _fieldnames, blockers = _read_csv(path_like)
    if blockers:
        return []
    return [
        row
        for row in rows
        if _text(row.get("import_kind")) == "file" or _text(row.get("evidence_class")) in FILE_CLASSES
    ]


def _recommended_drop_filename(column: str, target_id: str) -> str:
    if not target_id:
        return ""
    if column == "prediction_pdb":
        return f"{target_id}_prediction.pdb"
    if column == "native_pdb":
        return f"{target_id}_native.pdb"
    if column.endswith("_prediction_pdb"):
        return f"{target_id}TS.pdb"
    return f"{target_id}_{column}.pdb"


def _canonical_destination(column: str, target_id: str) -> str:
    if not target_id:
        return ""
    if column == "prediction_pdb":
        return f"runs/casp17_historical_benchmark_predictions_current/{target_id}_prediction.pdb"
    if column == "native_pdb":
        return f"runs/casp17_historical_benchmark_natives_current/{target_id}_native.pdb"
    if column.endswith("_prediction_pdb"):
        layer = column.removesuffix("_prediction_pdb")
        return f"runs/casp17_historical_ablation_predictions_current/{layer}/{target_id}TS.pdb"
    return ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_like_pdb(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for index, line in enumerate(handle):
                record = line[:6].strip().upper()
                if record in {"ATOM", "HETATM"}:
                    return True
                if index >= 500:
                    break
    except OSError:
        return False
    return False


def _is_current_target_source(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    parts = resolved.parts
    if any(left == "casp17" and right == "targets_current" for left, right in zip(parts, parts[1:])):
        return True
    try:
        resolved.relative_to((ROOT / "casp17" / "targets_current").resolve())
    except ValueError:
        return False
    return True


def _identity_status(identity: dict[str, Any], current_targets: set[str]) -> tuple[str, str]:
    target_id = _text(identity.get("proposed_target_id")).upper()
    benchmark_id = _text(identity.get("proposed_benchmark_id"))
    clearance = _text(identity.get("operator_clearance")).lower()
    evidence_ref = _text(identity.get("evidence_ref"))
    declared = _text(identity.get("identity_status"))
    if declared == "ready_for_import":
        return "ready_for_import", target_id
    if _contains_placeholder(target_id) or _contains_placeholder(benchmark_id) or not evidence_ref or clearance not in CLEAR_VALUES:
        return "awaiting_identity", target_id
    if target_id in current_targets:
        return "blocked_identity", target_id
    return "ready_for_import", target_id


def _status_for_file(row: dict[str, Any], identity_status: str, target_id: str) -> tuple[str, str, str]:
    if identity_status == "blocked_identity":
        return "blocked_identity", "identity_row_blocked", ""
    if identity_status != "ready_for_import" or _contains_placeholder(target_id):
        return "waiting_on_identity", "target_identity_required", ""
    source_text = _text(row.get("source_path"))
    if _contains_placeholder(source_text):
        return "awaiting_source_path", "source_path_required", ""
    source_path = _resolve(source_text)
    if not source_path.is_file():
        return "blocked_missing_source_file", "source_path_not_found", ""
    if _is_current_target_source(source_path):
        return "blocked_current_target_source", "current_casp17_target_files_are_not_historical_evidence", ""
    if source_path.suffix.lower() != ".pdb":
        return "blocked_not_pdb", "source_path_must_be_pdb", ""
    if not _looks_like_pdb(source_path):
        return "blocked_invalid_pdb", "source_pdb_has_no_atom_records", ""
    digest = _sha256(source_path)
    destination = _canonical_destination(_text(row.get("template_column")), target_id)
    if destination:
        destination_path = _resolve(destination)
        if destination_path.exists() and _sha256(destination_path) == digest:
            return "already_imported", "", digest
        if destination_path.exists():
            return "blocked_existing_destination", "destination_exists_with_different_content", digest
    return "ready_for_import", "", digest


def _next_action(status: str) -> str:
    if status == "waiting_on_identity":
        return "fill and apply the compact identity unlock kit first"
    if status == "blocked_identity":
        return "fix the identity row blockers before collecting file sources"
    if status == "awaiting_source_path":
        return "enter a cleared local historical PDB source_path in the evidence import CSV"
    if status == "ready_for_import":
        return "review this source path, then run the evidence round with --apply-import"
    if status == "already_imported":
        return "rerun evidence intake to surface row_fill patch candidates"
    if status.startswith("blocked"):
        return "resolve the file source blocker before applying"
    return "review this file source action"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    current_targets = _current_targets(args.current_target_csv)
    identities = _identity_rows(args)
    rows: list[dict[str, Any]] = []
    for file_rank, row in enumerate(_file_import_rows(args.import_csv), start=1):
        dropzone_id = _text(row.get("dropzone_id"))
        identity = identities.get(dropzone_id, {})
        status, target_id = _identity_status(identity, current_targets)
        column = _text(row.get("template_column"))
        file_status, blocker, digest = _status_for_file(row, status, target_id)
        rows.append(
            {
                "dropzone_id": dropzone_id,
                "operator_priority": _int(row.get("operator_priority")),
                "row_rank": _int(row.get("row_rank")),
                "scope": _text(row.get("scope")),
                "file_rank": file_rank,
                "evidence_class": _text(row.get("evidence_class")),
                "template_column": column,
                "identity_status": status,
                "proposed_target_id": target_id,
                "source_path": _text(row.get("source_path")),
                "recommended_drop_filename": _recommended_drop_filename(column, target_id),
                "canonical_destination_path": _canonical_destination(column, target_id),
                "file_source_status": file_status,
                "blocker": blocker,
                "source_sha256": digest,
                "next_action": _next_action(file_status),
            }
        )
    by_status = Counter(str(row["file_source_status"]) for row in rows)
    row_ids = {row["dropzone_id"] for row in rows if row["dropzone_id"]}
    blocked_count = sum(count for status, count in by_status.items() if status.startswith("blocked"))
    first_open = next(
        (
            row
            for row in rows
            if row["file_source_status"] not in {"ready_for_import", "already_imported"}
        ),
        rows[0] if rows else {},
    )
    if not rows:
        plan_status = "ready"
    elif blocked_count:
        plan_status = "blocked"
    elif by_status["ready_for_import"]:
        plan_status = "ready_for_import"
    elif by_status["waiting_on_identity"] or by_status["blocked_identity"]:
        plan_status = "waiting_on_identity"
    elif by_status["awaiting_source_path"]:
        plan_status = "awaiting_source_paths"
    elif by_status["already_imported"] == len(rows):
        plan_status = "complete"
    else:
        plan_status = "awaiting_source_paths"
    summary = {
        "packet_type": "casp17_competitive_floor_file_source_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "file_source_status": plan_status,
        "import_csv": _artifact(args.import_csv),
        "identity_kit_json": _artifact(args.identity_kit_json),
        "identity_kit_csv": _artifact(args.identity_kit_csv),
        "current_target_csv": _artifact(args.current_target_csv),
        "row_count": len(row_ids),
        "file_action_count": len(rows),
        "waiting_on_identity_count": by_status["waiting_on_identity"],
        "identity_blocked_file_count": by_status["blocked_identity"],
        "awaiting_source_path_count": by_status["awaiting_source_path"],
        "ready_for_import_count": by_status["ready_for_import"],
        "already_imported_count": by_status["already_imported"],
        "blocked_file_source_count": blocked_count,
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _text(first_open.get("file_source_status")),
        "first_open_blocker": _text(first_open.get("blocker")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor File Source Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- file_source_status: `{summary['file_source_status']}`",
        f"- rows/file actions: `{summary['row_count']}/{summary['file_action_count']}`",
        f"- waiting on identity: `{summary['waiting_on_identity_count']}`",
        f"- awaiting source paths: `{summary['awaiting_source_path_count']}`",
        f"- ready/imported/blocked: `{summary['ready_for_import_count']}/{summary['already_imported_count']}/{summary['blocked_file_source_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_column'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## File Source Actions",
        "",
        "| rank | dropzone | column | identity | target | status | source | destination | blocker | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['file_rank']} | `{row['dropzone_id']}` | `{row['template_column']}` | "
            f"`{row['identity_status']}` | `{row['proposed_target_id'] or '-'}` | `{row['file_source_status']}` | "
            f"`{row['source_path'] or '-'}` | `{row['canonical_destination_path'] or '-'}` | "
            f"`{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | `ready` | - | - | - | no file source actions |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=PLAN_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 competitive-floor file source plan.")
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--identity-kit-json", default=DEFAULT_IDENTITY_KIT_JSON)
    parser.add_argument("--identity-kit-csv", default=DEFAULT_IDENTITY_KIT_CSV)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
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
