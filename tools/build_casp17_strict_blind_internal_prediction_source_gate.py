#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_AUDIT_JSON = "casp17/casp17_strict_blind_internal_prediction_source_audit_current.json"
DEFAULT_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_GATE_DIR = "casp17/strict_blind_internal_prediction_source_gate"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_INTERNAL_PREDICTION_SOURCE_GATE.md"

ROW_COLUMNS = [
    "check_id",
    "check_status",
    "required_value",
    "actual_value",
    "blocker",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind internal prediction source gate only. It validates operator-provided manifest fields, "
    "prediction PDB presence, basic PDB atom records, chronology, no-leak evidence, and operator clearance for the "
    "first historical strict-blind slot. It does not create or copy prediction files, approve provenance, mutate "
    "strict-blind intake CSVs, compute CASP metrics, push remotes, or submit to CASP."
)
CLEARANCE_VALUES = {"approved", "clear", "cleared", "true", "yes", "operator_clear", "operator_approved"}


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


def _date(value: Any) -> dt.date | None:
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


def _first_slot_prediction_dropzone(first_slot_rows: list[dict[str, Any]]) -> str:
    for row in first_slot_rows:
        if _text(row.get("field_name")) == "prediction_pdb":
            return _text(row.get("source_path"))
    return ""


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


def _check(check_id: str, passed: bool, required: str, actual: str, blocker: str, next_action: str) -> dict[str, str]:
    return {
        "check_id": check_id,
        "check_status": "pass" if passed else "blocked",
        "required_value": required,
        "actual_value": actual,
        "blocker": "" if passed else blocker,
        "next_action": "" if passed else next_action,
    }


def _manifest_path(args: argparse.Namespace, audit_summary: dict[str, Any]) -> str:
    return _text(args.manifest_csv) or _text(audit_summary.get("internal_source_manifest_template"))


def _input_blockers(args: argparse.Namespace, manifest_csv: str) -> list[str]:
    blockers = []
    if not _resolve(args.audit_json).exists():
        blockers.append("audit_json_missing")
    if not _resolve(args.first_slot_kit_json).exists():
        blockers.append("first_slot_kit_json_missing")
    if not manifest_csv or not _resolve(manifest_csv).exists():
        blockers.append("internal_source_manifest_csv_missing")
    return blockers


def _build_checks(
    audit_summary: dict[str, Any],
    first_slot_rows: list[dict[str, Any]],
    manifest_csv: str,
    manifest_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, str]]:
    row = manifest_rows[0] if manifest_rows else {}
    dropzone = _first_slot_prediction_dropzone(first_slot_rows)
    prediction = _text(row.get("prediction_pdb"))
    source_id = _text(row.get("source_id"))
    target_id = _text(row.get("target_id"))
    scope = _text(row.get("scope"))
    prediction_created = _text(row.get("prediction_created_at"))
    native_release = _text(row.get("native_release_date"))
    prediction_date = _date(prediction_created)
    native_date = _date(native_release)
    source_is_official = source_id.startswith(("official_archive", "casp_official", "massivefold_external"))
    clearance = _text(row.get("operator_clearance")).lower()
    checks = [
        _check(
            "manifest_exists",
            bool(manifest_rows),
            "one internal source manifest row",
            _artifact(manifest_csv) if manifest_rows else "",
            "manifest_missing_or_empty",
            "fill internal_prediction_source_manifest_template.csv",
        ),
        _check(
            "source_id_internal",
            bool(source_id) and not source_is_official,
            "non-official internal source_id",
            source_id,
            "internal_source_id_missing_or_external",
            "set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool",
        ),
        _check(
            "target_id_present",
            bool(target_id),
            "target_id present",
            target_id,
            "target_id_missing",
            "set target_id or replacement target identity for this strict-blind slot",
        ),
        _check(
            "scope_matches",
            scope == _text(audit_summary.get("required_scope")),
            _text(audit_summary.get("required_scope")),
            scope,
            "scope_mismatch",
            "set manifest scope to the first-slot required scope",
        ),
        _check(
            "manifest_prediction_pdb_present",
            bool(prediction),
            "prediction_pdb path",
            prediction,
            "prediction_pdb_missing",
            "point prediction_pdb at the verified internal prediction PDB",
        ),
        _check(
            "manifest_prediction_pdb_exists",
            bool(prediction) and _resolve(prediction).exists(),
            "existing local prediction PDB",
            _artifact(prediction),
            "prediction_pdb_not_found",
            "place the internal prediction PDB at the manifest path",
        ),
        _check(
            "dropzone_prediction_pdb_exists",
            bool(dropzone) and _resolve(dropzone).exists(),
            "first-slot prediction dropzone PDB present",
            _artifact(dropzone),
            "dropzone_prediction_pdb_missing",
            "copy the verified internal prediction PDB into the first-slot prediction dropzone",
        ),
        _check(
            "prediction_pdb_has_atom_records",
            _pdb_has_atom_records(prediction),
            "ATOM or HETATM records",
            _artifact(prediction),
            "prediction_pdb_has_no_atom_records",
            "provide a structurally valid PDB with atom records",
        ),
        _check(
            "prediction_created_at_present",
            prediction_date is not None,
            "ISO date",
            prediction_created,
            "prediction_created_at_missing_or_invalid",
            "enter a verifiable prediction creation date before native release",
        ),
        _check(
            "native_release_date_present",
            native_date is not None,
            "ISO date",
            native_release,
            "native_release_date_missing_or_invalid",
            "enter the authoritative native public release date",
        ),
        _check(
            "prediction_before_native",
            bool(prediction_date and native_date and prediction_date < native_date),
            "prediction_created_at < native_release_date",
            f"{prediction_created}/{native_release}",
            "prediction_not_before_native",
            "use only prediction evidence created before the native structure was public",
        ),
        _check(
            "native_authority_ref_present",
            bool(_text(row.get("native_authority_ref"))),
            "native authority reference",
            _text(row.get("native_authority_ref")),
            "native_authority_ref_missing",
            "attach authoritative native source reference",
        ),
        _check(
            "creation_evidence_ref_present",
            bool(_text(row.get("creation_evidence_ref"))),
            "prediction creation evidence reference",
            _text(row.get("creation_evidence_ref")),
            "creation_evidence_ref_missing",
            "attach independent timestamp evidence for the internal prediction",
        ),
        _check(
            "no_leak_evidence_ref_present",
            bool(_text(row.get("no_leak_evidence_ref"))),
            "no-leak evidence reference",
            _text(row.get("no_leak_evidence_ref")),
            "no_leak_evidence_ref_missing",
            "attach no-leak provenance for the internal prediction source",
        ),
        _check(
            "method_summary_present",
            bool(_text(row.get("method_summary"))),
            "method summary",
            _text(row.get("method_summary")),
            "method_summary_missing",
            "summarize the internal prediction method and source package",
        ),
        _check(
            "operator_clearance_present",
            clearance in CLEARANCE_VALUES,
            "operator clearance approved/clear",
            clearance,
            "operator_clearance_missing",
            "set operator_clearance after reviewing the prediction source and provenance",
        ),
    ]
    return checks, {"manifest_prediction_pdb": prediction, "prediction_dropzone": dropzone, "source_id": source_id}


def _status(input_blockers: list[str], rows: list[dict[str, str]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    blocked = [row for row in rows if row["check_status"] != "pass"]
    if not blocked:
        return "internal_prediction_source_ready_for_first_slot_dropzone"
    if any(row["check_id"] == "manifest_exists" and row["check_status"] != "pass" for row in rows):
        return "awaiting_internal_prediction_source_manifest"
    return "awaiting_internal_prediction_source_gate_fields"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    audit_payload = _read_json(args.audit_json)
    first_slot_payload = _read_json(args.first_slot_kit_json)
    audit_summary = _summary(audit_payload)
    manifest_csv = _manifest_path(args, audit_summary)
    input_blockers = _input_blockers(args, manifest_csv)
    manifest_rows = _read_csv_rows(manifest_csv)
    rows, pointers = _build_checks(audit_summary, _rows(first_slot_payload), manifest_csv, manifest_rows)
    blocked_rows = [row for row in rows if row["check_status"] != "pass"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_strict_blind_internal_prediction_source_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "internal_prediction_source_gate_status": _status(input_blockers, rows),
        "required_benchmark_id": _text(audit_summary.get("required_benchmark_id")),
        "required_target_id": _text(audit_summary.get("required_target_id")),
        "required_scope": _text(audit_summary.get("required_scope")),
        "manifest_csv": _artifact(manifest_csv),
        "manifest_row_count": len(manifest_rows),
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["check_status"] == "pass"),
        "blocked_count": len(blocked_rows),
        "manifest_prediction_pdb": _artifact(pointers["manifest_prediction_pdb"]),
        "prediction_dropzone": _artifact(pointers["prediction_dropzone"]),
        "source_id": pointers["source_id"],
        "first_blocker": _text(first_blocked.get("blocker")),
        "first_blocked_check": _text(first_blocked.get("check_id")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_gate_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    folder = _resolve(args.gate_dir) / (summary["required_benchmark_id"] or "hist_REQUIRED_MONOMER_001")
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "internal_prediction_source_gate.csv", payload["rows"], ROW_COLUMNS)
    lines = [
        "# CASP17 Strict-Blind Internal Prediction Source Gate",
        "",
        f"- status: `{summary['internal_prediction_source_gate_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- checks pass/blocked/total: `{summary['pass_count']}/{summary['blocked_count']}/{summary['check_count']}`",
        f"- manifest: `{summary['manifest_csv']}`",
        f"- prediction/dropzone: `{summary['manifest_prediction_pdb'] or '-'}` `{summary['prediction_dropzone'] or '-'}`",
        f"- first blocker: `{summary['first_blocked_check'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "INTERNAL_PREDICTION_SOURCE_GATE.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Internal Prediction Source Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['internal_prediction_source_gate_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- manifest rows: `{summary['manifest_row_count']}`",
        f"- checks pass/blocked/total: `{summary['pass_count']}/{summary['blocked_count']}/{summary['check_count']}`",
        f"- manifest: `{summary['manifest_csv']}`",
        f"- prediction/dropzone: `{summary['manifest_prediction_pdb'] or '-'}` `{summary['prediction_dropzone'] or '-'}`",
        f"- first blocker: `{summary['first_blocked_check'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Checks",
        "",
        "| check | status | required | actual | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['check_status']}` | `{row['required_value']}` | "
            f"`{row['actual_value']}` | `{row['blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_gate_folder(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict-blind internal prediction source gate.")
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--first-slot-kit-json", default=DEFAULT_FIRST_SLOT_KIT_JSON)
    parser.add_argument("--manifest-csv", default="")
    parser.add_argument("--gate-dir", default=DEFAULT_GATE_DIR)
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
