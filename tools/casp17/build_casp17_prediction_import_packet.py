#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_seed_with_sequences_current.csv"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_current"
DEFAULT_OUT_JSON = "runs/casp17_prediction_import_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_prediction_import_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_prediction_import_packet_current.md"
DEFAULT_OUT_INTAKE_CSV = "runs/casp17_target_intake_prediction_imported_current.csv"

CANDIDATE_SUFFIXES = {".pdb", ".ent", ".txt", ".ts", ".model", ".casp"}
PLACEHOLDER_PATTERNS = [
    "placeholder",
    "dummy",
    "fake",
    "lorem",
    "not a prediction",
    "example only",
    "template only",
    "todo prediction",
]


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


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _read_prediction_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _nonempty_lines(text: str) -> list[str]:
    return [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _header_value(line: str) -> str:
    parts = line.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _target_line_matches(lines: list[str], target_id: str) -> bool:
    target_upper = target_id.upper()
    for line in lines[:80]:
        if _record(line) == "TARGET" and _header_value(line).upper() == target_upper:
            return True
    return False


def _target_line_values(lines: list[str]) -> list[str]:
    values: list[str] = []
    for line in lines[:80]:
        if _record(line) == "TARGET":
            values.append(_header_value(line))
    return values


def _candidate_files(prediction_dir: str | Path) -> list[Path]:
    root = _resolve(prediction_dir)
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in CANDIDATE_SUFFIXES and not path.name.startswith(".")
    )


def _candidate_match(candidate: Path, target_id: str) -> tuple[bool, str]:
    target_upper = target_id.upper()
    if target_upper in candidate.stem.upper() or target_upper in candidate.name.upper():
        return True, "filename"
    try:
        text = _read_prediction_text(candidate)
    except OSError:
        return False, ""
    lines = _nonempty_lines(text)
    if _target_line_matches(lines, target_id):
        return True, "content"
    return False, ""


def _assessment(candidate: Path, target_id: str, matched_by: str) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    try:
        stat = candidate.stat()
        text = _read_prediction_text(candidate)
    except OSError as exc:
        return {
            "path": _artifact(candidate),
            "matched_by": matched_by,
            "import_status": "blocked",
            "score": 0,
            "blockers": [f"candidate_unreadable:{type(exc).__name__}"],
            "warnings": [],
            "byte_size": 0,
            "atom_count": 0,
            "model_count": 0,
        }
    lines = _nonempty_lines(text)
    records = [_record(line) for line in lines]
    lowered = text.lower()
    placeholder_hits = [pattern for pattern in PLACEHOLDER_PATTERNS if pattern in lowered]
    if placeholder_hits:
        blockers.append("placeholder_or_fake_prediction_content")
    if stat.st_size < 80:
        warnings.append("candidate_file_very_small")
    if not lines:
        blockers.append("candidate_empty")
    elif _record(lines[0]) != "PFRMAT" or _header_value(lines[0]).upper() != "TS":
        blockers.append("pfrmat_ts_missing_first_line")
    if not _target_line_matches(lines, target_id):
        values = _target_line_values(lines)
        blockers.append("target_record_missing_or_mismatch" if values else "target_record_missing")
    if "MODEL" not in records:
        blockers.append("model_record_missing")
    atom_count = sum(1 for line in lines if _record(line) == "ATOM")
    if atom_count == 0:
        blockers.append("atom_records_missing")
    if "AUTHOR" not in records[:5]:
        warnings.append("author_record_not_near_top")
    if "METHOD" not in records:
        warnings.append("method_record_missing")
    score = (
        (30 if not blockers else 0)
        + (20 if matched_by == "filename" else 10)
        + min(atom_count, 5000) // 100
        + (5 if "PFRMAT" in records[:1] else 0)
        + (5 if "MODEL" in records else 0)
    )
    return {
        "path": _artifact(candidate),
        "matched_by": matched_by,
        "import_status": "ready" if not blockers else "blocked",
        "score": score,
        "blockers": blockers,
        "warnings": warnings,
        "byte_size": stat.st_size,
        "atom_count": atom_count,
        "model_count": records.count("MODEL"),
        "target_records": _target_line_values(lines),
    }


def _candidate_assessments(target_id: str, candidates: list[Path]) -> list[dict[str, Any]]:
    assessments: list[dict[str, Any]] = []
    for candidate in candidates:
        matched, matched_by = _candidate_match(candidate, target_id)
        if not matched:
            continue
        assessments.append(_assessment(candidate, target_id, matched_by))
    return sorted(assessments, key=lambda item: (-int(item["score"]), item["path"]))


def _select_candidate(target_id: str, candidates: list[Path]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    assessments = _candidate_assessments(target_id, candidates)
    for assessment in assessments:
        if assessment["import_status"] == "ready":
            return assessment, assessments
    return (assessments[0], assessments) if assessments else (None, assessments)


def _append_note(existing: str, note: str) -> str:
    existing = _text(existing)
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


def _row_import_result(row: dict[str, str], candidates: list[Path]) -> tuple[dict[str, Any], dict[str, str]]:
    target_id = _text(row.get("target_id"))
    fmt = _text(row.get("submission_format")).upper()
    enriched = dict(row)
    enriched.setdefault("prediction_import_status", "")
    enriched.setdefault("prediction_candidate_path", "")
    enriched.setdefault("prediction_import_blockers", "")
    if fmt != "TS":
        enriched["prediction_import_status"] = "skipped_unsupported_format"
        return (
            {
                "target_id": target_id,
                "submission_format": fmt,
                "prediction_import_status": "skipped_unsupported_format",
                "selected_candidate_path": "",
                "candidate_count": 0,
                "blockers": [f"unsupported_submission_format:{fmt or 'missing'}"],
                "warnings": [],
                "next_required_step": "Add a format-specific import/validation path before submission.",
            },
            enriched,
        )

    candidate_pool = list(candidates)
    existing_path_text = _text(row.get("prediction_file_path"))
    if existing_path_text:
        existing_path = _resolve(existing_path_text)
        candidate_pool = [existing_path] + [candidate for candidate in candidate_pool if candidate.resolve() != existing_path.resolve()]

    selected, assessments = _select_candidate(target_id, candidate_pool)
    if selected and selected["import_status"] == "ready":
        enriched["prediction_file_path"] = selected["path"]
        enriched["prediction_import_status"] = "imported" if not existing_path_text else "existing_ready"
        enriched["prediction_candidate_path"] = selected["path"]
        enriched["prediction_import_blockers"] = ""
        enriched["notes"] = _append_note(_text(enriched.get("notes")), "Prediction file imported into CASP17 fail-closed validation lane.")
        return (
            {
                "target_id": target_id,
                "submission_format": fmt,
                "prediction_import_status": enriched["prediction_import_status"],
                "selected_candidate_path": selected["path"],
                "candidate_count": len(assessments),
                "blockers": [],
                "warnings": selected.get("warnings", []),
                "byte_size": selected.get("byte_size", 0),
                "atom_count": selected.get("atom_count", 0),
                "model_count": selected.get("model_count", 0),
                "matched_by": selected.get("matched_by", ""),
                "next_required_step": "Run build_casp17_prediction_validation_batch.py against the imported intake.",
            },
            enriched,
        )

    if selected:
        blockers = list(selected.get("blockers", []))
        enriched["prediction_file_path"] = ""
        enriched["prediction_import_status"] = "blocked_placeholder_or_invalid"
        enriched["prediction_candidate_path"] = selected["path"]
        enriched["prediction_import_blockers"] = ";".join(blockers)
        enriched["notes"] = _append_note(_text(enriched.get("notes")), "Prediction candidate blocked before validation import.")
        return (
            {
                "target_id": target_id,
                "submission_format": fmt,
                "prediction_import_status": "blocked_placeholder_or_invalid",
                "selected_candidate_path": selected["path"],
                "candidate_count": len(assessments),
                "blockers": blockers,
                "warnings": selected.get("warnings", []),
                "byte_size": selected.get("byte_size", 0),
                "atom_count": selected.get("atom_count", 0),
                "model_count": selected.get("model_count", 0),
                "matched_by": selected.get("matched_by", ""),
                "next_required_step": "Replace the candidate with a target-specific CASP17 TS prediction file.",
            },
            enriched,
        )

    enriched["prediction_import_status"] = "missing_candidate"
    enriched["prediction_candidate_path"] = ""
    enriched["prediction_import_blockers"] = "missing_prediction_candidate"
    return (
        {
            "target_id": target_id,
            "submission_format": fmt,
            "prediction_import_status": "missing_candidate",
            "selected_candidate_path": "",
            "candidate_count": 0,
            "blockers": ["missing_prediction_candidate"],
            "warnings": [],
            "next_required_step": "Generate or attach a target-specific CASP17 TS prediction file.",
        },
        enriched,
    )


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = [row for row in _read_csv(args.intake_csv) if _text(row.get("target_id"))]
    candidates = _candidate_files(args.prediction_dir)
    packet_rows: list[dict[str, Any]] = []
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        packet_row, enriched = _row_import_result(row, candidates)
        packet_rows.append(packet_row)
        enriched_rows.append(enriched)

    imported_count = sum(1 for row in packet_rows if row["prediction_import_status"] in {"imported", "existing_ready"})
    blocked_count = sum(1 for row in packet_rows if row["prediction_import_status"] == "blocked_placeholder_or_invalid")
    missing_count = sum(1 for row in packet_rows if row["prediction_import_status"] == "missing_candidate")
    skipped_count = sum(1 for row in packet_rows if row["prediction_import_status"].startswith("skipped"))
    summary = {
        "packet_type": "casp17_prediction_import_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_csv": _artifact(args.intake_csv),
        "prediction_dir": _artifact(args.prediction_dir),
        "out_intake_csv": _artifact(args.out_intake_csv),
        "target_row_count": len(packet_rows),
        "candidate_file_count": len(candidates),
        "imported_count": imported_count,
        "blocked_placeholder_or_invalid_count": blocked_count,
        "missing_candidate_count": missing_count,
        "skipped_count": skipped_count,
        "claim_boundary": "Prediction file import and placeholder screening only; not CASP17 validation, scoring, or submission evidence.",
    }
    return {"summary": summary, "rows": packet_rows}, enriched_rows


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Prediction Import Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- intake CSV: `{summary['intake_csv']}`",
        f"- prediction directory: `{summary['prediction_dir']}`",
        f"- target rows: `{summary['target_row_count']}`",
        f"- candidates found: `{summary['candidate_file_count']}`",
        f"- imported/blocked/missing/skipped: `{summary['imported_count']}/{summary['blocked_placeholder_or_invalid_count']}/{summary['missing_candidate_count']}/{summary['skipped_count']}`",
        f"- enriched intake: `{summary['out_intake_csv']}`",
        "",
        "## Rows",
        "",
        "| target | format | import status | candidate | blockers | next step |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(row.get("blockers", [])) if isinstance(row.get("blockers"), list) else str(row.get("blockers", ""))
        lines.append(
            f"| `{row['target_id']}` | `{row['submission_format']}` | `{row['prediction_import_status']}` | "
            f"`{row.get('selected_candidate_path') or '-'}` | {blockers or '-'} | {row['next_required_step']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `no_rows` | - | - | Add CASP17 target intake rows. |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import CASP17 prediction files into the fail-closed validation intake.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-intake-csv", default=DEFAULT_OUT_INTAKE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, enriched_rows = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    fieldnames = list(enriched_rows[0].keys()) if enriched_rows else []
    _write_csv(args.out_intake_csv, enriched_rows, fieldnames=fieldnames)
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
