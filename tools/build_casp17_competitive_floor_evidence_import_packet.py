#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DROPZONE_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_evidence_import_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_evidence_import_audit_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_IMPORT.md"

FILE_CLASSES = {"core_file", "ablation_file"}
CLEAR_VALUES = {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
LEDGER_COLUMNS = [
    "template_column",
    "evidence_class",
    "current_value",
    "proposed_value",
    "evidence_ref",
    "operator_clearance",
    "ledger_status",
    "next_action",
]
IMPORT_COLUMNS = [
    "dropzone_id",
    "action_rank",
    "operator_priority",
    "row_rank",
    "benchmark_id",
    "target_id",
    "scope",
    "evidence_class",
    "template_column",
    "source_row_fill_csv",
    "dropzone_class_folder",
    "import_kind",
    "source_path",
    "drop_filename",
    "proposed_value",
    "expected_value_rule",
    "evidence_ref",
    "operator_clearance",
    "operator_note",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor evidence import only. It creates and audits a single import CSV for cleared "
    "historical benchmark evidence, and optional --apply copies local PDB files into dropzones or updates "
    "FIELD_VALUE_LEDGER.csv rows. It does not choose targets, clear no-leak provenance, fetch native structures, "
    "score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP."
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    if not resolved:
        resolved = ["dropzone_id", "template_column", "import_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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


def _date_ok(value: Any) -> bool:
    text = _text(value)
    if _contains_placeholder(text):
        return False
    try:
        dt.date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True


def _numeric_ok(value: Any) -> bool:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return False
    return math.isfinite(parsed)


def _rank_ok(value: Any) -> bool:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return False
    return 1 <= parsed <= 5


def _expected_value_rule(column: str) -> str:
    if column in {"benchmark_id", "target_id"}:
        return "cleared historical non-current identifier"
    if column in {"leakage_clearance", "operator_clearance"}:
        return "one of no_leak, cleared, internal_no_leak, or ready_for_row_fill"
    if column == "prediction_method":
        return "non-placeholder internal method identifier"
    if column in {"prediction_created_at", "native_release_date"}:
        return "ISO date YYYY-MM-DD"
    if column == "prediction_generated_before_native_release":
        return "true"
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return "false"
    if column in {"selected_model_rank", "best_model_rank"}:
        return "integer 1..5"
    if column in {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}:
        return "finite numeric value"
    return "non-placeholder cleared value"


def _value_blocker(column: str, proposed: str) -> str:
    lower = proposed.lower()
    if column in {"benchmark_id", "target_id", "prediction_method"}:
        return "" if not _contains_placeholder(proposed) else f"{column}_required"
    if column in {"leakage_clearance", "operator_clearance"}:
        return "" if lower in CLEAR_VALUES else f"{column}_requires_no_leak_clearance"
    if column in {"prediction_created_at", "native_release_date"}:
        return "" if _date_ok(proposed) else f"{column}_requires_iso_date"
    if column == "prediction_generated_before_native_release":
        return "" if lower in TRUE_VALUES else "prediction_generated_before_native_release_must_be_true"
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return "" if lower in FALSE_VALUES else f"{column}_must_be_false"
    if column in {"selected_model_rank", "best_model_rank"}:
        return "" if _rank_ok(proposed) else f"{column}_requires_rank_1_to_5"
    if column in {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}:
        return "" if _numeric_ok(proposed) else f"{column}_requires_numeric_value"
    return "" if not _contains_placeholder(proposed) else f"{column}_required"


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return _text(row.get("dropzone_id")), _text(row.get("template_column"))


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
                if record in {"ATOM", "HETATM", "MODEL", "HEADER", "TITLE", "REMARK", "TER", "END"}:
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
    blocked_roots = [
        ROOT / "casp17" / "targets_current",
    ]
    for root in blocked_roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _import_kind(action: dict[str, Any]) -> str:
    return "file" if _text(action.get("evidence_class")) in FILE_CLASSES else "value"


def _import_rows_by_key(import_csv: str | Path) -> dict[tuple[str, str], dict[str, str]]:
    rows, blockers = _read_csv(import_csv)
    if blockers:
        return {}
    return {
        _key(row): row
        for row in rows
        if _text(row.get("dropzone_id")) and _text(row.get("template_column"))
    }


def _target_file(action: dict[str, Any], import_row: dict[str, str]) -> Path:
    class_folder = _resolve(_text(action.get("dropzone_class_folder")))
    drop_filename = _text(import_row.get("drop_filename"))
    if drop_filename:
        return class_folder / Path(drop_filename).name
    source = _text(import_row.get("source_path"))
    if source:
        return class_folder / Path(source).name
    drop_path = _text(action.get("drop_path"))
    if drop_path and "<HISTORICAL_TARGET_ID>" not in drop_path:
        return _resolve(drop_path)
    return class_folder / f"{_text(action.get('template_column')) or 'evidence'}.pdb"


def _ledger_path(action: dict[str, Any]) -> Path:
    dropzone_folder = _text(action.get("dropzone_folder"))
    batch_folder = _resolve(dropzone_folder).parent if dropzone_folder else _resolve(".")
    return batch_folder / "FIELD_VALUE_LEDGER.csv"


def _ledger_update_status(action: dict[str, Any], import_row: dict[str, str]) -> str:
    ledger_path = _ledger_path(action)
    rows, blockers = _read_csv(ledger_path)
    if blockers:
        return "ledger_unavailable"
    column = _text(action.get("template_column"))
    proposed = _text(import_row.get("proposed_value"))
    evidence_ref = _text(import_row.get("evidence_ref"))
    clearance = _text(import_row.get("operator_clearance"))
    for row in rows:
        if _text(row.get("template_column")) != column:
            continue
        if (
            _text(row.get("proposed_value")) == proposed
            and _text(row.get("evidence_ref")) == evidence_ref
            and _text(row.get("operator_clearance")).lower() == clearance.lower()
        ):
            return "already_imported"
        return "ready_to_update_ledger"
    return "ledger_row_missing"


def _update_ledger(action: dict[str, Any], import_row: dict[str, str]) -> bool:
    ledger_path = _ledger_path(action)
    rows, blockers = _read_csv(ledger_path)
    if blockers:
        return False
    column = _text(action.get("template_column"))
    updated = False
    for row in rows:
        if _text(row.get("template_column")) != column:
            continue
        row["proposed_value"] = _text(import_row.get("proposed_value"))
        row["evidence_ref"] = _text(import_row.get("evidence_ref"))
        row["operator_clearance"] = _text(import_row.get("operator_clearance"))
        row["ledger_status"] = "ready_for_row_fill"
        updated = True
        break
    if not updated:
        return False
    _write_csv(ledger_path, rows, fieldnames=LEDGER_COLUMNS)
    return True


def _status_for_file(action: dict[str, Any], import_row: dict[str, str], *, overwrite: bool) -> tuple[str, str, str, str]:
    source_text = _text(import_row.get("source_path"))
    if _contains_placeholder(source_text):
        return "awaiting_import_file", "source_path_required", "", ""
    source_path = _resolve(source_text)
    if not source_path.is_file():
        return "blocked_missing_source_file", "source_path_not_found", "", ""
    if _is_current_target_source(source_path):
        return "blocked_current_target_source", "current_casp17_target_files_are_not_historical_evidence", "", ""
    if source_path.suffix.lower() != ".pdb":
        return "blocked_not_pdb", "source_path_must_be_pdb", "", ""
    if not _looks_like_pdb(source_path):
        return "blocked_invalid_pdb", "source_pdb_has_no_atom_records", "", ""
    target_path = _target_file(action, import_row)
    source_digest = _sha256(source_path)
    if target_path.exists():
        target_digest = _sha256(target_path)
        if target_digest == source_digest:
            return "already_imported", "", _artifact(target_path), source_digest
        if not overwrite:
            return "blocked_existing_destination", "destination_exists_with_different_content", _artifact(target_path), source_digest
    return "ready_to_copy", "", _artifact(target_path), source_digest


def _status_for_value(action: dict[str, Any], import_row: dict[str, str]) -> tuple[str, str]:
    proposed = _text(import_row.get("proposed_value"))
    if _contains_placeholder(proposed):
        return "awaiting_import_value", "proposed_value_required"
    value_blocker = _value_blocker(_text(action.get("template_column")), proposed)
    if value_blocker:
        return "blocked_invalid_import_value", value_blocker
    clearance = _text(import_row.get("operator_clearance")).lower()
    if clearance not in CLEAR_VALUES:
        return "awaiting_clearance", "operator_clearance_required"
    if not _text(import_row.get("evidence_ref")):
        return "awaiting_evidence_ref", "evidence_ref_required"
    ledger_status = _ledger_update_status(action, import_row)
    if ledger_status == "already_imported":
        return "already_imported", ""
    if ledger_status == "ready_to_update_ledger":
        return "ready_to_update_ledger", ""
    return "blocked_" + ledger_status, ledger_status


def _audit_row(action: dict[str, Any], import_row: dict[str, str], *, overwrite: bool) -> dict[str, Any]:
    kind = _import_kind(action)
    if kind == "file":
        status, blocker, destination, digest = _status_for_file(action, import_row, overwrite=overwrite)
    else:
        status, blocker = _status_for_value(action, import_row)
        destination = _artifact(_ledger_path(action))
        digest = ""
    batch_folder = _resolve(_text(action.get("dropzone_folder"))).parent if _text(action.get("dropzone_folder")) else _resolve(".")
    import_csv = batch_folder / "EVIDENCE_IMPORT.csv"
    import_md = batch_folder / "EVIDENCE_IMPORT.md"
    return {
        "dropzone_id": _text(action.get("dropzone_id")),
        "action_rank": _int(action.get("action_rank")),
        "operator_priority": _int(action.get("operator_priority")),
        "row_rank": _int(action.get("row_rank")),
        "benchmark_id": _text(action.get("benchmark_id")),
        "target_id": _text(action.get("target_id")),
        "scope": _text(action.get("scope")),
        "evidence_class": _text(action.get("evidence_class")),
        "template_column": _text(action.get("template_column")),
        "source_row_fill_csv": _text(action.get("source_row_fill_csv")),
        "dropzone_class_folder": _text(action.get("dropzone_class_folder")),
        "import_kind": kind,
        "source_path": _text(import_row.get("source_path")),
        "drop_filename": _text(import_row.get("drop_filename")),
        "proposed_value": _text(import_row.get("proposed_value")),
        "expected_value_rule": _expected_value_rule(_text(action.get("template_column"))),
        "evidence_ref": _text(import_row.get("evidence_ref")),
        "operator_clearance": _text(import_row.get("operator_clearance")),
        "destination_path": destination,
        "source_sha256": digest,
        "import_status": status,
        "blocker": blocker,
        "per_row_import_csv": _artifact(import_csv),
        "per_row_import_md": _artifact(import_md),
        "next_action": _next_action(status, kind),
    }


def _next_action(status: str, kind: str) -> str:
    if status == "ready_to_copy":
        return "run this tool with --apply after review to copy the PDB into the dropzone"
    if status == "ready_to_update_ledger":
        return "run this tool with --apply after review to update FIELD_VALUE_LEDGER.csv"
    if status == "already_imported":
        return "rerun value-ledger and evidence-intake packets to surface patch candidates"
    if status == "awaiting_import_file":
        return "enter source_path for the cleared local historical PDB in the import CSV"
    if status == "awaiting_import_value":
        return "enter proposed_value, evidence_ref, and operator_clearance in the import CSV"
    if status == "awaiting_clearance":
        return "set operator_clearance to no_leak, cleared, internal_no_leak, or ready_for_row_fill"
    if status == "awaiting_evidence_ref":
        return "add a local evidence_ref that supports this imported value"
    if status == "blocked_invalid_import_value":
        return "correct proposed_value to match the expected field rule"
    if status.startswith("blocked"):
        return "resolve the import blocker before applying"
    return "review this import row"


def _apply_imports(rows: list[dict[str, Any]], actions_by_key: dict[tuple[str, str], dict[str, Any]]) -> int:
    applied_count = 0
    for row in rows:
        action = actions_by_key.get(_key(row))
        if not action:
            continue
        if row["import_status"] == "ready_to_copy":
            source_path = _resolve(_text(row.get("source_path")))
            destination = _resolve(_text(row.get("destination_path")))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            row["import_status"] = "copied_to_dropzone"
            applied_count += 1
        elif row["import_status"] == "ready_to_update_ledger":
            if _update_ledger(action, {key: _text(row.get(key)) for key in row}):
                row["import_status"] = "ledger_updated"
                applied_count += 1
    return applied_count


def _status_from_counts(rows: list[dict[str, Any]], by_status: dict[str, int]) -> str:
    if not rows:
        return "ready"
    if any(status.startswith("blocked") for status in by_status):
        return "blocked"
    if by_status["ready_to_copy"] or by_status["ready_to_update_ledger"]:
        return "ready_for_apply"
    if (
        by_status["awaiting_import_file"]
        or by_status["awaiting_import_value"]
        or by_status["awaiting_clearance"]
        or by_status["awaiting_evidence_ref"]
    ):
        return "awaiting_import"
    return "ready_for_intake"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dropzone_payload = _read_json(args.dropzone_json)
    dropzone_summary = _summary(dropzone_payload)
    actions = _rows(dropzone_payload)
    import_rows = _import_rows_by_key(args.import_csv)
    audit_rows = [
        _audit_row(action, import_rows.get(_key(action), {}), overwrite=args.overwrite)
        for action in actions
    ]
    actions_by_key = {_key(action): action for action in actions}
    applied_count = _apply_imports(audit_rows, actions_by_key) if args.apply else 0
    by_status = defaultdict(int)
    by_kind = defaultdict(int)
    dropzone_ids: set[str] = set()
    for row in audit_rows:
        by_status[str(row["import_status"])] += 1
        by_kind[str(row["import_kind"])] += 1
        if row["dropzone_id"]:
            dropzone_ids.add(str(row["dropzone_id"]))
    blocked_count = sum(count for status, count in by_status.items() if status.startswith("blocked"))
    first_open = next(
        (
            row
            for row in audit_rows
            if row["import_status"] not in {"already_imported", "copied_to_dropzone", "ledger_updated"}
        ),
        audit_rows[0] if audit_rows else {},
    )
    summary = {
        "packet_type": "casp17_competitive_floor_evidence_import",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "import_status": _status_from_counts(audit_rows, by_status),
        "apply_mode": "applied" if args.apply else "dry_run",
        "dropzone_json": _artifact(args.dropzone_json),
        "dropzone_status": _text(dropzone_summary.get("dropzone_status")),
        "import_csv": _artifact(args.import_csv),
        "row_count": len(dropzone_ids),
        "action_count": len(audit_rows),
        "file_action_count": by_kind["file"],
        "value_action_count": by_kind["value"],
        "ready_to_copy_count": by_status["ready_to_copy"],
        "ready_to_update_ledger_count": by_status["ready_to_update_ledger"],
        "ready_for_apply_count": by_status["ready_to_copy"] + by_status["ready_to_update_ledger"],
        "applied_count": applied_count,
        "already_imported_count": by_status["already_imported"],
        "copied_to_dropzone_count": by_status["copied_to_dropzone"],
        "ledger_updated_count": by_status["ledger_updated"],
        "awaiting_import_file_count": by_status["awaiting_import_file"],
        "awaiting_import_value_count": by_status["awaiting_import_value"],
        "awaiting_clearance_count": by_status["awaiting_clearance"],
        "awaiting_evidence_ref_count": by_status["awaiting_evidence_ref"],
        "blocked_count": blocked_count,
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _text(first_open.get("import_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": audit_rows}


def _template_row(action: dict[str, Any], existing: dict[str, str]) -> dict[str, Any]:
    kind = _import_kind(action)
    return {
        "dropzone_id": _text(action.get("dropzone_id")),
        "action_rank": _int(action.get("action_rank")),
        "operator_priority": _int(action.get("operator_priority")),
        "row_rank": _int(action.get("row_rank")),
        "benchmark_id": _text(action.get("benchmark_id")),
        "target_id": _text(action.get("target_id")),
        "scope": _text(action.get("scope")),
        "evidence_class": _text(action.get("evidence_class")),
        "template_column": _text(action.get("template_column")),
        "source_row_fill_csv": _text(action.get("source_row_fill_csv")),
        "dropzone_class_folder": _text(action.get("dropzone_class_folder")),
        "import_kind": kind,
        "source_path": _text(existing.get("source_path")),
        "drop_filename": _text(existing.get("drop_filename")),
        "proposed_value": _text(existing.get("proposed_value")),
        "expected_value_rule": _expected_value_rule(_text(action.get("template_column"))),
        "evidence_ref": _text(existing.get("evidence_ref")),
        "operator_clearance": _text(existing.get("operator_clearance")),
        "operator_note": _text(existing.get("operator_note")) or _template_next_action(kind),
    }


def _template_next_action(kind: str) -> str:
    if kind == "file":
        return "fill source_path with a cleared local historical PDB path; drop_filename is optional"
    return "fill proposed_value, evidence_ref, and operator_clearance"


def _write_import_template(args: argparse.Namespace, dropzone_payload: dict[str, Any]) -> None:
    existing = _import_rows_by_key(args.import_csv)
    rows = [_template_row(action, existing.get(_key(action), {})) for action in _rows(dropzone_payload)]
    _write_csv(args.import_csv, rows, fieldnames=IMPORT_COLUMNS)


def _write_per_row_imports(payload: dict[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        grouped[_text(row.get("dropzone_id"))].append(row)
    for dropzone_id, rows in grouped.items():
        if not dropzone_id or not rows:
            continue
        rows.sort(key=lambda row: int(row["action_rank"]))
        import_csv = _resolve(rows[0]["per_row_import_csv"])
        import_md = _resolve(rows[0]["per_row_import_md"])
        _write_csv(import_csv, rows)
        lines = [
            "# CASP17 Competitive-Floor Evidence Import",
            "",
            f"- dropzone_id: `{dropzone_id}`",
            f"- row_fill_csv: `{rows[0]['source_row_fill_csv']}`",
            f"- per_row_import_csv: `{_artifact(import_csv)}`",
            f"- action count: `{len(rows)}`",
            "",
            "| rank | kind | class | column | status | source/proposed | destination | next action |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            source_or_value = row["source_path"] if row["import_kind"] == "file" else row["proposed_value"]
            lines.append(
                f"| {row['action_rank']} | `{row['import_kind']}` | `{row['evidence_class']}` | "
                f"`{row['template_column']}` | `{row['import_status']}` | `{source_or_value or '-'}` | "
                f"`{row['destination_path'] or '-'}` | {row['next_action']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        import_md.parent.mkdir(parents=True, exist_ok=True)
        import_md.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Evidence Import",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- import_status: `{summary['import_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- import_csv: `{summary['import_csv']}`",
        f"- rows/actions: `{summary['row_count']}/{summary['action_count']}`",
        f"- file/value actions: `{summary['file_action_count']}/{summary['value_action_count']}`",
        f"- ready copy/update/apply: `{summary['ready_to_copy_count']}/{summary['ready_to_update_ledger_count']}/{summary['ready_for_apply_count']}`",
        f"- applied/copied/ledger-updated: `{summary['applied_count']}/{summary['copied_to_dropzone_count']}/{summary['ledger_updated_count']}`",
        f"- awaiting file/value/clearance/ref: `{summary['awaiting_import_file_count']}/{summary['awaiting_import_value_count']}/{summary['awaiting_clearance_count']}/{summary['awaiting_evidence_ref_count']}`",
        f"- blocked: `{summary['blocked_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_column'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Import Rows",
        "",
        "| rank | dropzone | kind | class | column | status | source/proposed | destination | blocker |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        source_or_value = row["source_path"] if row["import_kind"] == "file" else row["proposed_value"]
        lines.append(
            f"| {row['action_rank']} | `{row['dropzone_id']}` | `{row['import_kind']}` | "
            f"`{row['evidence_class']}` | `{row['template_column']}` | `{row['import_status']}` | "
            f"`{source_or_value or '-'}` | `{row['destination_path'] or '-'}` | `{row['blocker'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | `ready` | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    dropzone_payload = _read_json(args.dropzone_json)
    if args.write_import_template:
        _write_import_template(args, dropzone_payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.write_guides:
        _write_per_row_imports(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or apply a central CASP17 competitive-floor evidence import packet.")
    parser.add_argument("--dropzone-json", default=DEFAULT_DROPZONE_JSON)
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--write-import-template", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--write-guides", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
