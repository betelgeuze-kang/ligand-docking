#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/casp17_ts_prediction_validation_current.json"
DEFAULT_OUT_CSV = "runs/casp17_ts_prediction_validation_current.csv"
DEFAULT_OUT_MD = "runs/casp17_ts_prediction_validation_current.md"


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


def _read_text(path_like: str | Path) -> str:
    return _resolve(path_like).read_text(encoding="utf-8")


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "format_check_status",
        "blocker_count",
        "warning_count",
        "model_count",
        "atom_count",
        "predicted_residue_count",
        "sequence_residue_count",
        "b_factor_unique_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 TS Prediction Validation",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- prediction file: `{summary['prediction_file_path']}`",
        f"- sequence file: `{summary['sequence_path']}`",
        f"- format check: `{summary['format_check_status']}`",
        f"- models: `{summary['model_count']}`",
        f"- atoms: `{summary['atom_count']}`",
        f"- predicted residues: `{summary['predicted_residue_count']}`",
        f"- sequence residues: `{summary['sequence_residue_count']}`",
        f"- blocker/warning count: `{summary['blocker_count']}/{summary['warning_count']}`",
        "",
        "## Blockers",
        "",
    ]
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if payload["warnings"]:
        lines.extend(f"- `{warning['code']}`: {warning['reason']}" for warning in payload["warnings"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _fasta_residue_count(path_like: str | Path) -> tuple[int, int]:
    text = _read_text(path_like)
    entries = 0
    residues = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            entries += 1
            continue
        residues += len(re.sub(r"[^A-Za-z*.-]", "", stripped))
    return entries, residues


def _float_or_none(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _pdb_float(line: str, start: int, end: int, fallback_index: int) -> float | None:
    if len(line) >= end:
        parsed = _float_or_none(line[start:end])
        if parsed is not None:
            return parsed
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _header_value(line: str) -> str:
    parts = line.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _warning(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "warning", "reason": reason}


def _parse_models(lines: list[str]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for idx, line in enumerate(lines, start=1):
        rec = _record(line)
        if rec == "MODEL":
            if current is not None:
                current["unterminated"] = True
                models.append(current)
            current = {"model_line": idx, "model_record": line, "lines": [], "end_line": None}
            continue
        if current is not None:
            current["lines"].append((idx, line))
        if rec == "END" and current is not None:
            current["end_line"] = idx
            models.append(current)
            current = None
    if current is not None:
        current["unterminated"] = True
        models.append(current)
    return models


def _model_index(model_record: str) -> int | None:
    parts = model_record.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def validate_prediction(*, target_id: str, prediction_file: str | Path, sequence_path: str | Path) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    prediction_path = _resolve(prediction_file)
    fasta_path = _resolve(sequence_path)

    if not prediction_path.exists():
        blockers.append(_blocker("prediction_file_missing", f"Prediction file `{_artifact(prediction_path)}` is missing."))
    if not fasta_path.exists():
        blockers.append(_blocker("sequence_file_missing", f"Sequence file `{_artifact(fasta_path)}` is missing."))
    if blockers:
        return _payload(target_id, prediction_path, fasta_path, blockers, warnings, {}, [])

    text = _read_text(prediction_path)
    lines = [line.rstrip("\n\r") for line in text.splitlines() if line.strip()]
    fasta_entries, sequence_residue_count = _fasta_residue_count(fasta_path)
    if fasta_entries == 0 or sequence_residue_count == 0:
        blockers.append(_blocker("sequence_not_valid_fasta", "Sequence file has no FASTA entries or residues."))
    if not lines:
        blockers.append(_blocker("prediction_file_empty", "Prediction file is empty."))
        return _payload(target_id, prediction_path, fasta_path, blockers, warnings, {"sequence_residue_count": sequence_residue_count}, [])

    if _record(lines[0]) != "PFRMAT" or _header_value(lines[0]).upper() != "TS":
        blockers.append(_blocker("pfrmat_ts_missing_first_line", "First non-empty line must be `PFRMAT TS`."))
    if len(lines) < 2 or _record(lines[1]) != "TARGET" or _header_value(lines[1]).upper() != target_id.upper():
        blockers.append(_blocker("target_record_mismatch", f"Second non-empty line must be `TARGET {target_id}`."))
    if len(lines) < 3 or _record(lines[2]) != "AUTHOR":
        blockers.append(_blocker("author_record_missing_third_line", "Third non-empty line must be `AUTHOR ...`."))

    records = [_record(line) for line in lines]
    first_model_idx = records.index("MODEL") if "MODEL" in records else -1
    if first_model_idx < 0:
        blockers.append(_blocker("model_record_missing", "At least one MODEL block is required."))
    else:
        header_records = records[:first_model_idx]
        if "METHOD" not in header_records:
            blockers.append(_blocker("method_record_missing_before_model", "At least one METHOD record is required before the first MODEL."))
        if records[:3] != ["PFRMAT", "TARGET", "AUTHOR"]:
            blockers.append(_blocker("mandatory_header_order_invalid", "Mandatory header must start with PFRMAT, TARGET, AUTHOR."))

    models = _parse_models(lines)
    if not models:
        models = []
    model_indices = [_model_index(str(model.get("model_record", ""))) for model in models]
    if len(models) > 6:
        blockers.append(_blocker("too_many_models", "TS submission contains more than six MODEL blocks."))
    if 1 not in model_indices:
        blockers.append(_blocker("model_1_missing", "MODEL 1 is required because CASP focuses primarily on model index 1."))
    if len([idx for idx in model_indices if idx is not None]) != len(set(idx for idx in model_indices if idx is not None)):
        blockers.append(_blocker("duplicate_model_index", "MODEL indices must be unique."))
    for index in model_indices:
        if index is None:
            blockers.append(_blocker("model_index_not_integer", "Every MODEL record must include an integer model index."))
        elif index < 1 or index > 6:
            blockers.append(_blocker("model_index_out_of_range", "MODEL index must be between 1 and 6 for CASP17 TS predictions."))

    metrics = _model_metrics(models)
    atom_count = metrics["atom_count"]
    if atom_count == 0:
        blockers.append(_blocker("atom_records_missing", "TS prediction must contain ATOM records."))
    if metrics["model_without_parent_count"] > 0:
        blockers.append(_blocker("parent_record_missing", "Each TS MODEL block must contain at least one PARENT record."))
    if metrics["model_without_ter_count"] > 0:
        blockers.append(_blocker("ter_record_missing", "Each TS MODEL block with atoms must contain a TER record."))
    if metrics["model_chain_parent_shortfall_count"] > 0:
        blockers.append(_blocker("parent_record_missing_for_chain", "Each atom-containing chain segment in a TS MODEL block must have a PARENT record."))
    if metrics["model_chain_ter_shortfall_count"] > 0:
        blockers.append(_blocker("ter_record_missing_for_chain", "Each atom-containing chain segment in a TS MODEL block must be terminated with a TER record."))
    if metrics["unterminated_model_count"] > 0:
        blockers.append(_blocker("model_block_not_terminated", "Every MODEL block must end with END."))
    if metrics["duplicate_atom_key_count"] > 0:
        blockers.append(_blocker("duplicate_atom_records", "MODEL blocks contain duplicate atom records for the same chain/residue/atom."))
    if metrics["invalid_occupancy_count"] > 0:
        blockers.append(_blocker("occupancy_out_of_range", "ATOM occupancy values must be in the 0.00 to 1.00 range."))
    if metrics["invalid_b_factor_count"] > 0:
        blockers.append(_blocker("b_factor_out_of_range", "ATOM B-factor confidence values must be in the 0 to 100 range."))
    if metrics["b_factor_unique_count"] <= 1 and atom_count > 1:
        blockers.append(_blocker("uniform_b_factor_confidence", "CASP17 TS predictions with uniform B-factor confidence values can be rejected."))
    if metrics["short_atom_line_count"] > 0:
        warnings.append(_warning("atom_line_shorter_than_80_columns", "Some ATOM records are shorter than the 80-column legacy PDB recommendation."))
    if sequence_residue_count and metrics["predicted_residue_count"] > sequence_residue_count * 1.20:
        blockers.append(
            _blocker(
                "predicted_residue_count_exceeds_sequence",
                "Predicted unique residue count substantially exceeds the FASTA residue count.",
            )
        )
    if sequence_residue_count and metrics["predicted_residue_count"] < max(1, int(sequence_residue_count * 0.10)):
        warnings.append(_warning("very_low_sequence_coverage", "Predicted residue count is below 10% of the FASTA residue count."))

    metrics.update(
        {
            "sequence_entry_count": fasta_entries,
            "sequence_residue_count": sequence_residue_count,
            "model_count": len(models),
            "model_indices": [idx for idx in model_indices if idx is not None],
        }
    )
    return _payload(target_id, prediction_path, fasta_path, blockers, warnings, metrics, models)


def _atom_key(line: str) -> tuple[str, str, str, str]:
    if len(line) >= 27:
        atom_name = line[12:16].strip()
        chain_id = line[21].strip() or "_"
        residue_id = line[22:26].strip()
        insertion_code = line[26].strip() or "_"
        return chain_id, residue_id, insertion_code, atom_name
    fields = line.split()
    atom_name = fields[2] if len(fields) > 2 else "?"
    chain_id = fields[4] if len(fields) > 4 else "_"
    residue_id = fields[5] if len(fields) > 5 else "?"
    return chain_id, residue_id, "_", atom_name


def _residue_key(line: str) -> tuple[str, str, str]:
    chain_id, residue_id, insertion_code, _atom_name = _atom_key(line)
    return chain_id, residue_id, insertion_code


def _model_metrics(models: list[dict[str, Any]]) -> dict[str, Any]:
    atom_count = 0
    b_factors: list[float] = []
    predicted_residues: set[tuple[int, str, str, str]] = set()
    duplicate_atom_key_count = 0
    invalid_occupancy_count = 0
    invalid_b_factor_count = 0
    short_atom_line_count = 0
    model_without_parent_count = 0
    model_without_ter_count = 0
    model_chain_parent_shortfall_count = 0
    model_chain_ter_shortfall_count = 0
    unterminated_model_count = 0

    for model_number, model in enumerate(models, start=1):
        lines = [line for _line_no, line in model.get("lines", [])]
        records = [_record(line) for line in lines]
        if "PARENT" not in records:
            model_without_parent_count += 1
        model_atoms = [line for line in lines if _record(line) == "ATOM"]
        if model_atoms and "TER" not in records:
            model_without_ter_count += 1
        if model.get("unterminated") or model.get("end_line") is None:
            unterminated_model_count += 1
        chain_segments = _atom_chain_segments(model_atoms)
        parent_count = records.count("PARENT")
        ter_count = records.count("TER")
        if parent_count < chain_segments:
            model_chain_parent_shortfall_count += chain_segments - parent_count
        if ter_count < chain_segments:
            model_chain_ter_shortfall_count += chain_segments - ter_count

        seen_atom_keys: set[tuple[str, str, str, str]] = set()
        for line in model_atoms:
            atom_count += 1
            if len(line) < 80:
                short_atom_line_count += 1
            atom_key = _atom_key(line)
            if atom_key in seen_atom_keys:
                duplicate_atom_key_count += 1
            seen_atom_keys.add(atom_key)
            predicted_residues.add((model_number, *_residue_key(line)))
            occupancy = _pdb_float(line, 54, 60, 9)
            if occupancy is None or occupancy < 0.0 or occupancy > 1.0:
                invalid_occupancy_count += 1
            b_factor = _pdb_float(line, 60, 66, 10)
            if b_factor is None or b_factor < 0.0 or b_factor > 100.0:
                invalid_b_factor_count += 1
            elif math.isfinite(b_factor):
                b_factors.append(round(b_factor, 3))

    return {
        "atom_count": atom_count,
        "predicted_residue_count": len(predicted_residues),
        "b_factor_unique_count": len(set(b_factors)),
        "duplicate_atom_key_count": duplicate_atom_key_count,
        "invalid_occupancy_count": invalid_occupancy_count,
        "invalid_b_factor_count": invalid_b_factor_count,
        "short_atom_line_count": short_atom_line_count,
        "model_without_parent_count": model_without_parent_count,
        "model_without_ter_count": model_without_ter_count,
        "model_chain_parent_shortfall_count": model_chain_parent_shortfall_count,
        "model_chain_ter_shortfall_count": model_chain_ter_shortfall_count,
        "unterminated_model_count": unterminated_model_count,
    }


def _atom_chain_segments(atom_lines: list[str]) -> int:
    segments = 0
    previous_chain = None
    for line in atom_lines:
        chain_id = _atom_key(line)[0]
        if chain_id != previous_chain:
            segments += 1
            previous_chain = chain_id
    return segments


def _payload(
    target_id: str,
    prediction_path: Path,
    fasta_path: Path,
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
    metrics: dict[str, Any],
    models: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = {
        "packet_type": "casp17_ts_prediction_validation",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_id": target_id,
        "prediction_file_path": _artifact(prediction_path),
        "sequence_path": _artifact(fasta_path),
        "format_check_status": "fail" if blockers else "pass",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "model_count": metrics.get("model_count", len(models)),
        "model_indices": metrics.get("model_indices", []),
        "atom_count": metrics.get("atom_count", 0),
        "predicted_residue_count": metrics.get("predicted_residue_count", 0),
        "sequence_entry_count": metrics.get("sequence_entry_count", 0),
        "sequence_residue_count": metrics.get("sequence_residue_count", 0),
        "b_factor_unique_count": metrics.get("b_factor_unique_count", 0),
        "claim_boundary": "CASP17 TS format validation only; not geometry accuracy, scientific correctness, or accepted submission evidence.",
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "metrics": metrics}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a CASP17 TS prediction file before fail-closed submission gating.")
    parser.add_argument("--target-id", required=True, help="CASP17 target id, e.g. H1340.")
    parser.add_argument("--prediction-file", required=True, help="Prediction file to validate.")
    parser.add_argument("--sequence-path", required=True, help="Target FASTA file.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = validate_prediction(target_id=args.target_id, prediction_file=args.prediction_file, sequence_path=args.sequence_path)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [payload["summary"]])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
