#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.casp17 import build_casp17_internal_scorecard_batch as scorecard_builder
from tools.casp17 import build_casp17_prediction_import_packet as import_builder
from tools import build_casp17_prediction_validation_batch as validation_builder
from tools.casp17 import build_casp17_submission_gate_packet as submission_gate_builder
from tools import convert_casp17_ts_prediction_from_pdb as converter


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_seed_with_sequences_current.csv"
DEFAULT_STRUCTURE_DIR = "runs/casp17_existing_structures_current"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_current"
DEFAULT_PROVENANCE_CSV = "runs/casp17_existing_structure_provenance_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_existing_structure_intake_builder_current.json"
DEFAULT_OUT_CSV = "runs/casp17_existing_structure_intake_builder_current.csv"
DEFAULT_OUT_MD = "runs/casp17_existing_structure_intake_builder_current.md"
DEFAULT_OUT_INTAKE_CSV = "runs/casp17_target_intake_existing_structure_current.csv"

DEFAULT_IMPORT_JSON = "runs/casp17_prediction_import_packet_current.json"
DEFAULT_IMPORT_CSV = "runs/casp17_prediction_import_packet_current.csv"
DEFAULT_IMPORT_MD = "runs/casp17_prediction_import_packet_current.md"
DEFAULT_IMPORTED_INTAKE_CSV = "runs/casp17_target_intake_prediction_imported_current.csv"
DEFAULT_VALIDATION_DIR = "runs/casp17_validations_current"
DEFAULT_VALIDATION_JSON = "runs/casp17_prediction_validation_batch_current.json"
DEFAULT_VALIDATION_CSV = "runs/casp17_prediction_validation_batch_current.csv"
DEFAULT_VALIDATION_MD = "runs/casp17_prediction_validation_batch_current.md"
DEFAULT_VALIDATED_INTAKE_CSV = "runs/casp17_target_intake_validated_current.csv"
DEFAULT_SCORECARD_DIR = "runs/casp17_internal_scorecards_current"
DEFAULT_SCORECARD_JSON = "runs/casp17_internal_scorecard_batch_current.json"
DEFAULT_SCORECARD_CSV = "runs/casp17_internal_scorecard_batch_current.csv"
DEFAULT_SCORECARD_MD = "runs/casp17_internal_scorecard_batch_current.md"
DEFAULT_SCORED_INTAKE_CSV = "runs/casp17_target_intake_scored_current.csv"
DEFAULT_SUBMISSION_GATE_JSON = "runs/casp17_submission_gate_packet_current.json"
DEFAULT_SUBMISSION_GATE_CSV = "runs/casp17_submission_gate_packet_current.csv"
DEFAULT_SUBMISSION_GATE_MD = "runs/casp17_submission_gate_packet_current.md"

CANDIDATE_SUFFIXES = {".pdb", ".ent", ".ts", ".casp", ".model", ".txt"}
STOP_ORDER = ("attach", "import", "validation", "scorecard", "submission_gate")
PASS_VALUES = {"pass", "passed", "green", "ready", "ok", "true", "1", "complete", "clear", "cleared", "approved"}
FALSE_VALUES = {"false", "0", "no", "n", "none", "absent", "not_used", "unused"}
TRUE_VALUES = {"true", "1", "yes", "y", "used", "present"}
INTERNAL_SOURCE_HINTS = {"internal", "local", "target_specific", "custom_backend", "de_novo", "own_prediction"}
PUBLIC_SOURCE_HINTS = {"public", "external", "third_party", "other_team", "post_release", "pdb", "afdb", "alphafold_db"}
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

AA3_TO_1 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "SEC": "U",
    "PYL": "O",
    "ASX": "B",
    "GLX": "Z",
    "UNK": "X",
    "MSE": "M",
}


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _header_value(line: str) -> str:
    parts = line.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _bool_value(value: Any) -> bool | None:
    text = _text(value).lower()
    if text in TRUE_VALUES or text in PASS_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


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


def _append_note(existing: str, note: str) -> str:
    existing = _text(existing)
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_files(structure_dir: str | Path) -> list[Path]:
    root = _resolve(structure_dir)
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in CANDIDATE_SUFFIXES and not path.name.startswith(".")
    )


def _provenance_path_value(row: dict[str, str]) -> str:
    for key in ("candidate_path", "structure_path", "source_path", "prediction_candidate_path", "path"):
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _path_matches(row_path: str, candidate: Path) -> bool:
    if not row_path:
        return True
    candidate_resolved = candidate.resolve()
    if row_path == _artifact(candidate):
        return True
    path = Path(row_path)
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.resolve() == candidate_resolved
    except OSError:
        return False


def _provenance_row(provenance_rows: list[dict[str, str]], target_id: str, candidate: Path) -> dict[str, str] | None:
    target_upper = target_id.upper()
    target_rows = [row for row in provenance_rows if _text(row.get("target_id")).upper() == target_upper]
    exact_rows = [row for row in target_rows if _provenance_path_value(row) and _path_matches(_provenance_path_value(row), candidate)]
    if exact_rows:
        return exact_rows[0]
    target_only_rows = [row for row in target_rows if not _provenance_path_value(row)]
    return target_only_rows[0] if target_only_rows else None


def _required_false_flag(row: dict[str, str], keys: tuple[str, ...], blocker_stem: str) -> list[str]:
    present_values = [(key, _bool_value(row.get(key))) for key in keys if _text(row.get(key))]
    if not present_values:
        return [f"{blocker_stem}_clearance_missing"]
    blockers: list[str] = []
    for key, value in present_values:
        if value is not False:
            blockers.append(f"{key}_not_false")
    return blockers


def _provenance_check(args: argparse.Namespace, target_id: str, candidate: Path) -> dict[str, Any]:
    provenance_path = _resolve(args.provenance_csv)
    if not provenance_path.exists():
        if args.allow_missing_provenance:
            return {
                "provenance_status": "skipped_allow_missing",
                "blockers": [],
                "row": {},
                "provenance_csv": _artifact(provenance_path),
            }
        return {
            "provenance_status": "blocked",
            "blockers": ["provenance_csv_missing"],
            "row": {},
            "provenance_csv": _artifact(provenance_path),
        }

    row = _provenance_row(getattr(args, "provenance_rows", []), target_id, candidate)
    if not row:
        if args.allow_missing_provenance:
            return {
                "provenance_status": "skipped_allow_missing",
                "blockers": [],
                "row": {},
                "provenance_csv": _artifact(provenance_path),
            }
        return {
            "provenance_status": "blocked",
            "blockers": ["provenance_clearance_missing"],
            "row": {},
            "provenance_csv": _artifact(provenance_path),
        }

    blockers: list[str] = []
    clearance_status = _text(row.get("provenance_status") or row.get("clearance_status") or row.get("status")).lower()
    if clearance_status not in PASS_VALUES:
        blockers.append("provenance_status_not_cleared")

    source_class = _text(row.get("source_class") or row.get("provenance_source_class")).lower()
    if not source_class:
        blockers.append("provenance_source_class_missing")
    elif any(hint in source_class for hint in PUBLIC_SOURCE_HINTS):
        blockers.append("provenance_source_class_public_or_external")
    elif not any(hint in source_class for hint in INTERNAL_SOURCE_HINTS):
        blockers.append("provenance_source_class_not_internal")

    target_specific = _bool_value(row.get("target_specific") or row.get("created_for_target") or row.get("made_for_target"))
    if target_specific is not True:
        blockers.append("target_specific_clearance_not_true")

    blockers.extend(
        _required_false_flag(
            row,
            ("public_or_external_source_used", "public_structure_used", "external_structure_used"),
            "public_or_external_source_used",
        )
    )
    blockers.extend(
        _required_false_flag(
            row,
            ("other_team_structure_used", "other_team_source_used"),
            "other_team_structure_used",
        )
    )
    blockers.extend(
        _required_false_flag(
            row,
            ("post_release_structure_used", "post_release_source_used", "after_public_release_structure_used"),
            "post_release_structure_used",
        )
    )
    if _provenance_path_value(row) and not _path_matches(_provenance_path_value(row), candidate):
        blockers.append("provenance_candidate_path_mismatch")

    return {
        "provenance_status": "cleared" if not blockers else "blocked",
        "blockers": list(dict.fromkeys(blockers)),
        "row": dict(row),
        "provenance_csv": _artifact(provenance_path),
    }


def _nonempty_lines(path: Path) -> list[str]:
    return [line.rstrip("\r\n") for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def _target_record_values(lines: list[str]) -> list[str]:
    values: list[str] = []
    for line in lines[:100]:
        if _record(line) == "TARGET":
            values.append(_header_value(line))
    return values


def _target_record_matches(lines: list[str], target_id: str) -> bool:
    target_upper = target_id.upper()
    return any(value.upper() == target_upper for value in _target_record_values(lines))


def _candidate_match(candidate: Path, target_id: str) -> tuple[bool, str]:
    target_upper = target_id.upper()
    if target_upper in candidate.stem.upper() or target_upper in candidate.name.upper():
        return True, "filename"
    try:
        lines = _nonempty_lines(candidate)
    except OSError:
        return False, ""
    if _target_record_matches(lines, target_id):
        return True, "content"
    return False, ""


def _detect_source_format(lines: list[str]) -> str:
    if lines and _record(lines[0]) == "PFRMAT" and _header_value(lines[0]).upper() == "TS":
        return "ts"
    if any(_record(line) == "ATOM" for line in lines):
        return "raw_pdb"
    return "unsupported"


def _read_fasta_sequences(path_like: str | Path) -> list[str]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    sequences: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            if current:
                sequences.append("".join(current))
                current = []
            continue
        current.append(re.sub(r"[^A-Za-z]", "", stripped).upper())
    if current:
        sequences.append("".join(current))
    return [sequence for sequence in sequences if sequence]


def _atom_lines_first_model(lines: list[str]) -> list[str]:
    in_first_model = False
    seen_model = False
    atoms: list[str] = []
    for line in lines:
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec in {"END", "ENDMDL"} and in_first_model:
            break
        if rec == "ATOM" and (in_first_model or not seen_model):
            atoms.append(line)
    return atoms


def _pdb_residue_sequences(lines: list[str]) -> list[str]:
    chain_residues: dict[str, list[str]] = defaultdict(list)
    seen_residue_keys: set[tuple[str, str, str]] = set()
    chain_order: list[str] = []
    for line in _atom_lines_first_model(lines):
        if len(line) >= 27:
            chain = line[21].strip() or "_"
            resseq = line[22:26].strip()
            icode = line[26].strip() or "_"
            resname = line[17:20].strip().upper()
        else:
            fields = line.split()
            chain = fields[4] if len(fields) > 4 else "_"
            resseq = fields[5] if len(fields) > 5 else "?"
            icode = "_"
            resname = fields[3].upper() if len(fields) > 3 else "UNK"
        key = (chain, resseq, icode)
        if key in seen_residue_keys:
            continue
        seen_residue_keys.add(key)
        if chain not in chain_residues:
            chain_order.append(chain)
        chain_residues[chain].append(AA3_TO_1.get(resname, "X"))
    return ["".join(chain_residues[chain]) for chain in chain_order if chain_residues[chain]]


def _sequence_check(lines: list[str], sequence_path: str | Path) -> dict[str, Any]:
    fasta_sequences = _read_fasta_sequences(sequence_path)
    structure_sequences = _pdb_residue_sequences(lines)
    blockers: list[str] = []
    status = "pass"
    match_mode = ""
    if not fasta_sequences:
        blockers.append("sequence_file_missing_or_empty")
    if not structure_sequences:
        blockers.append("structure_sequence_missing")
    if not blockers:
        fasta_sorted = sorted(fasta_sequences)
        structure_sorted = sorted(structure_sequences)
        if structure_sorted == fasta_sorted:
            match_mode = "chain_multiset_exact"
        elif len(fasta_sequences) == 1 and all(sequence == fasta_sequences[0] for sequence in structure_sequences):
            match_mode = "single_fasta_repeated_chain_exact"
        elif "".join(structure_sequences) == "".join(fasta_sequences):
            match_mode = "concatenated_exact"
        else:
            blockers.append("structure_sequence_mismatch")
    if blockers:
        status = "blocked"
    return {
        "sequence_check_status": status,
        "match_mode": match_mode,
        "blockers": blockers,
        "fasta_entry_count": len(fasta_sequences),
        "fasta_lengths": [len(sequence) for sequence in fasta_sequences],
        "structure_chain_count": len(structure_sequences),
        "structure_chain_lengths": [len(sequence) for sequence in structure_sequences],
    }


def _assess_candidate(candidate: Path, target_id: str, sequence_path: str, matched_by: str) -> dict[str, Any]:
    try:
        stat = candidate.stat()
        text = candidate.read_text(encoding="utf-8", errors="replace")
        lines = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
    except OSError as exc:
        return {
            "path": _artifact(candidate),
            "matched_by": matched_by,
            "source_format": "unreadable",
            "status": "blocked",
            "score": 0,
            "blockers": [f"candidate_unreadable:{type(exc).__name__}"],
            "warnings": [],
        }

    source_format = _detect_source_format(lines)
    blockers: list[str] = []
    warnings: list[str] = []
    lowered = text.lower()
    placeholder_hits = [pattern for pattern in PLACEHOLDER_PATTERNS if pattern in lowered]
    if placeholder_hits:
        blockers.append("placeholder_or_fake_prediction_content")
    if stat.st_size < 80:
        warnings.append("candidate_file_very_small")
    if source_format == "unsupported":
        blockers.append("unsupported_structure_file_format")
    if source_format == "ts" and not _target_record_matches(lines, target_id):
        blockers.append("target_record_missing_or_mismatch")

    sequence_payload = _sequence_check(lines, sequence_path)
    blockers.extend(sequence_payload["blockers"])
    atom_count = sum(1 for line in lines if _record(line) == "ATOM")
    if atom_count == 0:
        blockers.append("atom_records_missing")
    score = (
        (50 if not blockers else 0)
        + (20 if source_format == "ts" else 10 if source_format == "raw_pdb" else 0)
        + (10 if matched_by == "filename" else 5)
        + min(atom_count, 5000) // 100
    )
    return {
        "path": _artifact(candidate),
        "matched_by": matched_by,
        "source_format": source_format,
        "status": "ready" if not blockers else "blocked",
        "score": score,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": warnings,
        "byte_size": stat.st_size,
        "atom_count": atom_count,
        "target_records": _target_record_values(lines),
        **sequence_payload,
    }


def _candidate_assessments(row: dict[str, str], candidates: list[Path]) -> list[dict[str, Any]]:
    target_id = _text(row.get("target_id")).upper()
    sequence_path = _text(row.get("sequence_path"))
    assessments: list[dict[str, Any]] = []
    for candidate in candidates:
        matched, matched_by = _candidate_match(candidate, target_id)
        if not matched:
            continue
        assessments.append(_assess_candidate(candidate, target_id, sequence_path, matched_by))
    return sorted(assessments, key=lambda item: (-int(item["score"]), item["path"]))


def _copy_or_confirm(candidate_path: Path, out_pdb: Path, *, overwrite: bool) -> tuple[bool, str, list[str]]:
    blockers: list[str] = []
    if out_pdb.exists():
        if candidate_path.resolve() == out_pdb.resolve():
            return True, "already_canonical", blockers
        if _sha256(candidate_path) == _sha256(out_pdb):
            return True, "canonical_identical_exists", blockers
        if not overwrite:
            blockers.append("canonical_prediction_exists_different_content")
            return False, "blocked_existing_output", blockers
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_path, out_pdb)
    return True, "copied_to_canonical_prediction_path", blockers


def _convert_raw(candidate_path: Path, row: dict[str, str], out_pdb: Path, args: argparse.Namespace) -> tuple[bool, str, list[str], dict[str, Any]]:
    blockers: list[str] = []
    if out_pdb.exists():
        if candidate_path.resolve() == out_pdb.resolve():
            blockers.append("raw_candidate_path_equals_ts_output_path")
            return False, "blocked_existing_output", blockers, {}
        if not args.overwrite:
            blockers.append("canonical_prediction_exists_different_content")
            return False, "blocked_existing_output", blockers, {}
    if not _text(args.author_code):
        blockers.append("missing_author_code_for_raw_conversion")
        return False, "blocked_missing_author_code", blockers, {}

    convert_args = argparse.Namespace(
        target_id=_text(row.get("target_id")).upper(),
        input_pdb=str(candidate_path),
        sequence_path=_text(row.get("sequence_path")),
        author_code=_text(args.author_code),
        method=_text(args.method)
        or "Internal CASP17 existing target-specific structure import; raw PDB converted to TS format.",
        parent=_text(args.parent) or "N/A",
        out_pdb=str(out_pdb),
    )
    payload = converter.convert_prediction(convert_args)
    conversion_blockers = [blocker["code"] for blocker in payload.get("blockers", []) if isinstance(blocker, dict)]
    if conversion_blockers:
        blockers.extend(conversion_blockers)
        return False, "blocked_conversion_failed", blockers, payload
    return True, "converted_raw_to_canonical_ts", blockers, payload


def _select_assessment(assessments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for assessment in assessments:
        if assessment["status"] == "ready":
            return assessment
    return assessments[0] if assessments else None


def _row_attach_result(row: dict[str, str], candidates: list[Path], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, str]]:
    target_id = _text(row.get("target_id")).upper()
    fmt = _text(row.get("submission_format")).upper()
    enriched = dict(row)
    enriched.setdefault("prediction_file_path", "")
    enriched.setdefault("prediction_import_status", "")
    enriched.setdefault("prediction_candidate_path", "")
    enriched.setdefault("prediction_import_blockers", "")
    enriched.setdefault("notes", "")

    if fmt != "TS":
        enriched["prediction_import_status"] = "skipped_unsupported_format"
        enriched["prediction_import_blockers"] = f"unsupported_submission_format:{fmt or 'missing'}"
        return (
            {
                "target_id": target_id,
                "submission_format": fmt,
                "attach_status": "skipped_unsupported_format",
                "source_format": "",
                "selected_candidate_path": "",
                "canonical_prediction_path": "",
                "candidate_count": 0,
                "blockers": [enriched["prediction_import_blockers"]],
                "warnings": [],
                "next_required_step": "Add a format-specific existing-structure import path.",
            },
            enriched,
        )

    if not _text(row.get("sequence_path")):
        enriched["prediction_import_status"] = "blocked_existing_structure_intake"
        enriched["prediction_import_blockers"] = "missing_sequence_path"
        return (
            {
                "target_id": target_id,
                "submission_format": fmt,
                "attach_status": "blocked",
                "source_format": "",
                "selected_candidate_path": "",
                "canonical_prediction_path": "",
                "candidate_count": 0,
                "blockers": ["missing_sequence_path"],
                "warnings": [],
                "next_required_step": "Materialize the CASP17 target FASTA before attaching structures.",
            },
            enriched,
        )

    assessments = _candidate_assessments(row, candidates)
    selected = _select_assessment(assessments)
    if not selected:
        enriched["prediction_file_path"] = ""
        enriched["prediction_import_status"] = "missing_candidate"
        enriched["prediction_candidate_path"] = ""
        enriched["prediction_import_blockers"] = "missing_existing_structure_candidate"
        return (
            {
                "target_id": target_id,
                "submission_format": fmt,
                "attach_status": "missing_candidate",
                "source_format": "",
                "selected_candidate_path": "",
                "canonical_prediction_path": "",
                "candidate_count": 0,
                "blockers": ["missing_existing_structure_candidate"],
                "warnings": [],
                "next_required_step": "Place a target-specific raw PDB or TS file in the existing-structure directory.",
            },
            enriched,
        )

    selected_path = _resolve(selected["path"])
    out_pdb = _resolve(args.prediction_dir) / f"{target_id}TS.pdb"
    operation = ""
    operation_payload: dict[str, Any] = {}
    operation_blockers: list[str] = []
    provenance_payload: dict[str, Any] = {
        "provenance_status": "",
        "blockers": [],
        "row": {},
        "provenance_csv": _artifact(args.provenance_csv),
    }
    attached = False
    if selected["status"] == "ready":
        provenance_payload = _provenance_check(args, target_id, selected_path)
        operation_blockers.extend(provenance_payload["blockers"])
        if not operation_blockers and selected["source_format"] == "ts":
            attached, operation, operation_blockers = _copy_or_confirm(selected_path, out_pdb, overwrite=args.overwrite)
        elif not operation_blockers and selected["source_format"] == "raw_pdb":
            attached, operation, operation_blockers, operation_payload = _convert_raw(selected_path, row, out_pdb, args)

    blockers = list(selected.get("blockers", [])) + operation_blockers
    if attached and not blockers:
        status = "attached_ts" if selected["source_format"] == "ts" else "converted_raw"
        enriched["prediction_file_path"] = _artifact(out_pdb)
        enriched["prediction_import_status"] = status
        enriched["prediction_candidate_path"] = selected["path"]
        enriched["prediction_import_blockers"] = ""
        enriched["prediction_provenance_status"] = provenance_payload["provenance_status"]
        enriched["prediction_provenance_blockers"] = ""
        enriched["notes"] = _append_note(
            _text(enriched.get("notes")),
            "Existing target-specific structure attached to CASP17 fail-closed validation lane.",
        )
        return (
            {
                "target_id": target_id,
                "submission_format": fmt,
                "attach_status": status,
                "source_format": selected["source_format"],
                "selected_candidate_path": selected["path"],
                "canonical_prediction_path": _artifact(out_pdb),
                "candidate_count": len(assessments),
                "blockers": [],
                "warnings": selected.get("warnings", []),
                "operation": operation,
                "provenance_status": provenance_payload["provenance_status"],
                "provenance_csv": provenance_payload["provenance_csv"],
                "provenance_blockers": provenance_payload["blockers"],
                "sequence_check_status": selected.get("sequence_check_status", ""),
                "sequence_match_mode": selected.get("match_mode", ""),
                "fasta_lengths": selected.get("fasta_lengths", []),
                "structure_chain_lengths": selected.get("structure_chain_lengths", []),
                "conversion_status": operation_payload.get("summary", {}).get("conversion_status", ""),
                "all_candidate_assessments": assessments,
                "next_required_step": "Run prediction import, validation, internal scorecard, and submission gate.",
            },
            enriched,
        )

    enriched["prediction_file_path"] = ""
    enriched["prediction_import_status"] = "blocked_existing_structure_intake"
    enriched["prediction_candidate_path"] = selected["path"]
    enriched["prediction_import_blockers"] = ";".join(dict.fromkeys(blockers))
    enriched["prediction_provenance_status"] = provenance_payload["provenance_status"]
    enriched["prediction_provenance_blockers"] = ";".join(provenance_payload["blockers"])
    enriched["notes"] = _append_note(_text(enriched.get("notes")), "Existing structure candidate blocked before attach/import.")
    return (
        {
            "target_id": target_id,
            "submission_format": fmt,
            "attach_status": "blocked",
            "source_format": selected.get("source_format", ""),
            "selected_candidate_path": selected["path"],
            "canonical_prediction_path": _artifact(out_pdb),
            "candidate_count": len(assessments),
            "blockers": list(dict.fromkeys(blockers)),
            "warnings": selected.get("warnings", []),
            "operation": operation,
            "provenance_status": provenance_payload["provenance_status"],
            "provenance_csv": provenance_payload["provenance_csv"],
            "provenance_blockers": provenance_payload["blockers"],
            "sequence_check_status": selected.get("sequence_check_status", ""),
            "sequence_match_mode": selected.get("match_mode", ""),
            "fasta_lengths": selected.get("fasta_lengths", []),
            "structure_chain_lengths": selected.get("structure_chain_lengths", []),
            "conversion_status": operation_payload.get("summary", {}).get("conversion_status", ""),
            "all_candidate_assessments": assessments,
            "next_required_step": "Replace the candidate or rerun with explicit approval flags if the canonical output is intentionally replaced.",
        },
        enriched,
    )


def _build_attach_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = [row for row in _read_csv(args.intake_csv) if _text(row.get("target_id"))]
    candidates = _candidate_files(args.structure_dir)
    args.provenance_rows = _read_csv(args.provenance_csv)
    packet_rows: list[dict[str, Any]] = []
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        packet_row, enriched = _row_attach_result(row, candidates, args)
        packet_rows.append(packet_row)
        enriched_rows.append(enriched)

    attached_count = sum(1 for row in packet_rows if row["attach_status"] in {"attached_ts", "converted_raw"})
    converted_count = sum(1 for row in packet_rows if row["attach_status"] == "converted_raw")
    ts_count = sum(1 for row in packet_rows if row["attach_status"] == "attached_ts")
    blocked_count = sum(1 for row in packet_rows if row["attach_status"] == "blocked")
    missing_count = sum(1 for row in packet_rows if row["attach_status"] == "missing_candidate")
    skipped_count = sum(1 for row in packet_rows if row["attach_status"].startswith("skipped"))
    provenance_cleared_count = sum(1 for row in packet_rows if row.get("provenance_status") == "cleared")
    provenance_blocked_count = sum(1 for row in packet_rows if row.get("provenance_status") == "blocked")
    provenance_skipped_count = sum(1 for row in packet_rows if row.get("provenance_status") == "skipped_allow_missing")
    summary = {
        "packet_type": "casp17_existing_structure_intake_builder",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_csv": _artifact(args.intake_csv),
        "structure_dir": _artifact(args.structure_dir),
        "prediction_dir": _artifact(args.prediction_dir),
        "provenance_csv": _artifact(args.provenance_csv),
        "out_intake_csv": _artifact(args.out_intake_csv),
        "target_row_count": len(packet_rows),
        "candidate_file_count": len(candidates),
        "provenance_row_count": len(args.provenance_rows),
        "provenance_cleared_count": provenance_cleared_count,
        "provenance_blocked_count": provenance_blocked_count,
        "provenance_skipped_allow_missing_count": provenance_skipped_count,
        "attached_count": attached_count,
        "attached_ts_count": ts_count,
        "converted_raw_count": converted_count,
        "blocked_count": blocked_count,
        "missing_candidate_count": missing_count,
        "skipped_count": skipped_count,
        "stop_after": args.stop_after,
        "claim_boundary": "Existing-structure attach/import orchestration with operator provenance clearance only; not accepted CASP17 submission or structure accuracy evidence.",
    }
    return {"summary": summary, "rows": packet_rows, "pipeline_stages": []}, enriched_rows


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Existing Structure Intake Builder",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- intake CSV: `{summary['intake_csv']}`",
        f"- existing-structure directory: `{summary['structure_dir']}`",
        f"- prediction directory: `{summary['prediction_dir']}`",
        f"- provenance CSV: `{summary['provenance_csv']}`",
        f"- target rows: `{summary['target_row_count']}`",
        f"- candidates found: `{summary['candidate_file_count']}`",
        f"- provenance rows / cleared / blocked: "
        f"`{summary['provenance_row_count']}/{summary['provenance_cleared_count']}/{summary['provenance_blocked_count']}`",
        f"- attached TS / converted raw / blocked / missing / skipped: "
        f"`{summary['attached_ts_count']}/{summary['converted_raw_count']}/{summary['blocked_count']}/"
        f"{summary['missing_candidate_count']}/{summary['skipped_count']}`",
        f"- enriched intake: `{summary['out_intake_csv']}`",
        "",
        "## Rows",
        "",
        "| target | status | source | candidate | canonical | provenance | sequence | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(row.get("blockers", [])) if isinstance(row.get("blockers"), list) else str(row.get("blockers", ""))
        lines.append(
            f"| `{row['target_id']}` | `{row['attach_status']}` | `{row.get('source_format') or '-'}` | "
            f"`{row.get('selected_candidate_path') or '-'}` | `{row.get('canonical_prediction_path') or '-'}` | "
            f"`{row.get('provenance_status') or '-'}` | "
            f"`{row.get('sequence_check_status') or '-'}` | {blockers or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_rows` | - | - | - | - | - | Add CASP17 target rows. |")
    if payload.get("pipeline_stages"):
        lines.extend(["", "## Pipeline Stages", "", "| stage | status | artifact |", "| --- | --- | --- |"])
        for stage in payload["pipeline_stages"]:
            lines.append(f"| `{stage['stage']}` | `{stage['status']}` | `{stage.get('artifact') or '-'}` |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _stage_enabled(args: argparse.Namespace, stage: str) -> bool:
    return STOP_ORDER.index(stage) <= STOP_ORDER.index(args.stop_after)


def _run_downstream_stages(args: argparse.Namespace) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    if _stage_enabled(args, "import"):
        import_args = argparse.Namespace(
            intake_csv=args.out_intake_csv,
            prediction_dir=args.prediction_dir,
            out_json=args.import_json,
            out_csv=args.import_csv,
            out_md=args.import_md,
            out_intake_csv=args.imported_intake_csv,
        )
        payload, enriched_rows = import_builder.build_payload(import_args)
        import_builder._write_json(args.import_json, payload)
        import_builder._write_csv(args.import_csv, payload["rows"])
        import_builder._write_csv(args.imported_intake_csv, enriched_rows, fieldnames=list(enriched_rows[0].keys()) if enriched_rows else [])
        import_builder._write_md(args.import_md, payload)
        stages.append({"stage": "import", "status": "completed", "artifact": _artifact(args.import_json), "summary": payload["summary"]})

    if _stage_enabled(args, "validation"):
        validation_args = argparse.Namespace(
            intake_csv=args.imported_intake_csv,
            out_dir=args.validation_dir,
            out_json=args.validation_json,
            out_csv=args.validation_csv,
            out_md=args.validation_md,
            out_intake_csv=args.validated_intake_csv,
            include_lg=False,
        )
        payload, enriched_rows = validation_builder.build_payload(validation_args)
        validation_builder._write_json(args.validation_json, payload)
        validation_builder._write_csv(args.validation_csv, payload["rows"])
        validation_builder._write_csv(
            args.validated_intake_csv,
            enriched_rows,
            fieldnames=list(enriched_rows[0].keys()) if enriched_rows else [],
        )
        validation_builder._write_md(args.validation_md, payload)
        stages.append({"stage": "validation", "status": "completed", "artifact": _artifact(args.validation_json), "summary": payload["summary"]})

    if _stage_enabled(args, "scorecard"):
        scorecard_args = argparse.Namespace(
            intake_csv=args.validated_intake_csv,
            out_dir=args.scorecard_dir,
            out_json=args.scorecard_json,
            out_csv=args.scorecard_csv,
            out_md=args.scorecard_md,
            out_intake_csv=args.scored_intake_csv,
            local_delivery_verdict_json=args.local_delivery_verdict_json,
            local_engine_queue_json=args.local_engine_queue_json,
            accuracy_scorecard_json=args.accuracy_scorecard_json,
        )
        payload, enriched_rows = scorecard_builder.build_payload(scorecard_args)
        scorecard_builder._write_json(args.scorecard_json, payload)
        scorecard_builder._write_csv(args.scorecard_csv, payload["rows"])
        scorecard_builder._write_csv(
            args.scored_intake_csv,
            enriched_rows,
            fieldnames=list(enriched_rows[0].keys()) if enriched_rows else [],
        )
        scorecard_builder._write_md(args.scorecard_md, payload)
        stages.append({"stage": "scorecard", "status": "completed", "artifact": _artifact(args.scorecard_json), "summary": payload["summary"]})

    if _stage_enabled(args, "submission_gate"):
        gate_args = argparse.Namespace(
            root=str(ROOT),
            intake_csv=args.scored_intake_csv,
            local_delivery_verdict_json=args.local_delivery_verdict_json,
            local_engine_queue_json=args.local_engine_queue_json,
            accuracy_scorecard_json=args.accuracy_scorecard_json,
            pde_local_min_json=args.pde_local_min_json,
            selected_allatom_json=args.selected_allatom_json,
            shape_sanity_json=getattr(args, "shape_sanity_json", ""),
            out_json=args.submission_gate_json,
            out_csv=args.submission_gate_csv,
            out_md=args.submission_gate_md,
        )
        payload = submission_gate_builder.build_payload(gate_args)
        submission_gate_builder._write_json(args.submission_gate_json, payload, ROOT)
        submission_gate_builder._write_csv(args.submission_gate_csv, payload["target_rows"], ROOT)
        submission_gate_builder._write_md(args.submission_gate_md, payload, ROOT)
        stages.append({"stage": "submission_gate", "status": "completed", "artifact": _artifact(args.submission_gate_json), "summary": payload["summary"]})
    return stages


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, str]]]:
    payload, enriched_rows = _build_attach_payload(args)
    payload["pipeline_stages"] = [{"stage": "attach", "status": "completed", "artifact": _artifact(args.out_json), "summary": payload["summary"]}]
    return payload, enriched_rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attach target-specific existing CASP17 structures, convert raw PDBs to TS when allowed, and run the fail-closed gate chain."
    )
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--structure-dir", default=DEFAULT_STRUCTURE_DIR)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--provenance-csv", default=DEFAULT_PROVENANCE_CSV)
    parser.add_argument(
        "--allow-missing-provenance",
        action="store_true",
        help="Permit attach/import without provenance clearance; intended for local smoke tests only.",
    )
    parser.add_argument("--author-code", default="", help="Required when a selected raw PDB must be converted into CASP TS format.")
    parser.add_argument("--method", default="")
    parser.add_argument("--parent", default="N/A")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing canonical <TARGET>TS.pdb output.")
    parser.add_argument("--stop-after", choices=STOP_ORDER, default="submission_gate")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-intake-csv", default=DEFAULT_OUT_INTAKE_CSV)
    parser.add_argument("--import-json", default=DEFAULT_IMPORT_JSON)
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--import-md", default=DEFAULT_IMPORT_MD)
    parser.add_argument("--imported-intake-csv", default=DEFAULT_IMPORTED_INTAKE_CSV)
    parser.add_argument("--validation-dir", default=DEFAULT_VALIDATION_DIR)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--validation-csv", default=DEFAULT_VALIDATION_CSV)
    parser.add_argument("--validation-md", default=DEFAULT_VALIDATION_MD)
    parser.add_argument("--validated-intake-csv", default=DEFAULT_VALIDATED_INTAKE_CSV)
    parser.add_argument("--scorecard-dir", default=DEFAULT_SCORECARD_DIR)
    parser.add_argument("--scorecard-json", default=DEFAULT_SCORECARD_JSON)
    parser.add_argument("--scorecard-csv", default=DEFAULT_SCORECARD_CSV)
    parser.add_argument("--scorecard-md", default=DEFAULT_SCORECARD_MD)
    parser.add_argument("--scored-intake-csv", default=DEFAULT_SCORED_INTAKE_CSV)
    parser.add_argument("--submission-gate-json", default=DEFAULT_SUBMISSION_GATE_JSON)
    parser.add_argument("--submission-gate-csv", default=DEFAULT_SUBMISSION_GATE_CSV)
    parser.add_argument("--submission-gate-md", default=DEFAULT_SUBMISSION_GATE_MD)
    parser.add_argument("--local-delivery-verdict-json", default=scorecard_builder.DEFAULT_LOCAL_DELIVERY_VERDICT_JSON)
    parser.add_argument("--local-engine-queue-json", default=scorecard_builder.DEFAULT_LOCAL_ENGINE_QUEUE_JSON)
    parser.add_argument("--accuracy-scorecard-json", default=scorecard_builder.DEFAULT_ACCURACY_SCORECARD_JSON)
    parser.add_argument("--pde-local-min-json", default=submission_gate_builder.DEFAULT_PDE_LOCAL_MIN_JSON)
    parser.add_argument("--selected-allatom-json", default=submission_gate_builder.DEFAULT_SELECTED_ALLATOM_JSON)
    parser.add_argument("--shape-sanity-json", default="", help="Optional structure-shape sanity packet to require at submission-gate time.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, enriched_rows = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_csv(args.out_intake_csv, enriched_rows, fieldnames=list(enriched_rows[0].keys()) if enriched_rows else [])
    if args.stop_after != "attach":
        payload["pipeline_stages"].extend(_run_downstream_stages(args))
        _write_json(args.out_json, payload)
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
