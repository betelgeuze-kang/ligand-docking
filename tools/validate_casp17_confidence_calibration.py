#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/casp17_confidence_calibration_current.json"
DEFAULT_OUT_CSV = "runs/casp17_confidence_calibration_current.csv"
DEFAULT_OUT_MD = "runs/casp17_confidence_calibration_current.md"

MIN_UNIQUE_CONFIDENCE_VALUES = 3
MIN_STDDEV = 1.0
MIN_RESIDUE_COVERAGE_FRACTION = 0.10
MAX_EXTREME_FRACTION = 0.98


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _float_slice(line: str, start: int, end: int, fallback_index: int) -> float | None:
    value = None
    if len(line) >= end:
        value = _float_or_none(line[start:end])
    if value is not None:
        return value
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


def _float_or_none(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _residue_key(line: str) -> tuple[str, str, str]:
    if len(line) >= 27:
        return line[21].strip() or "_", line[22:26].strip(), line[26].strip() or "_"
    fields = line.split()
    chain = fields[4] if len(fields) > 4 else "_"
    resseq = fields[5] if len(fields) > 5 else "?"
    return chain, resseq, "_"


def _read_first_model_b_factors(path_like: str | Path) -> tuple[list[float], dict[tuple[str, str, str], list[float]]]:
    lines = _resolve(path_like).read_text(encoding="utf-8").splitlines()
    in_first_model = False
    seen_model = False
    b_factors: list[float] = []
    residue_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for line in lines:
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec != "ATOM" or (seen_model and not in_first_model):
            continue
        b_factor = _float_slice(line, 60, 66, 10)
        if b_factor is None or not math.isfinite(b_factor):
            continue
        b_factors.append(b_factor)
        residue_values[_residue_key(line)].append(b_factor)
    return b_factors, residue_values


def _fasta_residue_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    residues = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        residues += sum(1 for char in stripped if char.isalpha() or char in {"*", ".", "-"})
    return residues


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _warning(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "warning", "reason": reason}


def validate_confidence(
    *,
    target_id: str,
    prediction_file: str | Path,
    sequence_path: str | Path = "",
) -> dict[str, Any]:
    prediction_path = _resolve(prediction_file)
    sequence_residue_count = _fasta_residue_count(sequence_path) if str(sequence_path).strip() else 0
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not prediction_path.exists():
        blockers.append(_blocker("prediction_file_missing", f"Prediction file `{_artifact(prediction_path)}` is missing."))
        return _payload(target_id, prediction_path, sequence_path, blockers, warnings, {})

    b_factors, residue_values = _read_first_model_b_factors(prediction_path)
    residue_means = [statistics.fmean(values) for values in residue_values.values() if values]
    if not b_factors:
        blockers.append(_blocker("confidence_values_missing", "No ATOM B-factor confidence values were found in model 1."))
        return _payload(target_id, prediction_path, sequence_path, blockers, warnings, {"sequence_residue_count": sequence_residue_count})

    out_of_range_count = sum(1 for value in b_factors if value < 0.0 or value > 100.0)
    if out_of_range_count:
        blockers.append(_blocker("confidence_values_out_of_range", "Confidence B-factors must remain in the 0 to 100 range."))

    unique_count = len({round(value, 3) for value in b_factors})
    if unique_count < MIN_UNIQUE_CONFIDENCE_VALUES:
        blockers.append(_blocker("confidence_not_nonuniform", "Confidence values must be target-specific and non-uniform."))
    stddev = statistics.pstdev(b_factors) if len(b_factors) > 1 else 0.0
    if stddev < MIN_STDDEV:
        blockers.append(_blocker("confidence_variance_too_low", "Confidence values have too little variance for a useful CASP confidence track."))

    extreme_count = sum(1 for value in b_factors if value <= 1.0 or value >= 99.0)
    extreme_fraction = extreme_count / len(b_factors)
    if extreme_fraction > MAX_EXTREME_FRACTION:
        blockers.append(_blocker("confidence_extreme_saturation", "Nearly all confidence values are saturated at the confidence range extremes."))

    residue_count = len(residue_values)
    residue_coverage_fraction = residue_count / sequence_residue_count if sequence_residue_count else 0.0
    if sequence_residue_count and residue_coverage_fraction < MIN_RESIDUE_COVERAGE_FRACTION:
        blockers.append(_blocker("confidence_residue_coverage_too_low", "Residue-level confidence coverage is too small relative to the target sequence."))
    if not sequence_residue_count:
        warnings.append(_warning("sequence_count_unavailable", "Sequence residue count was unavailable; residue coverage gate was skipped."))

    metrics = {
        "target_id": target_id,
        "atom_confidence_count": len(b_factors),
        "residue_confidence_count": residue_count,
        "sequence_residue_count": sequence_residue_count,
        "residue_coverage_fraction": round(residue_coverage_fraction, 6),
        "confidence_min": round(min(b_factors), 3),
        "confidence_p10": _round_or_none(_quantile(b_factors, 0.10)),
        "confidence_median": _round_or_none(_quantile(b_factors, 0.50)),
        "confidence_p90": _round_or_none(_quantile(b_factors, 0.90)),
        "confidence_max": round(max(b_factors), 3),
        "confidence_unique_count": unique_count,
        "confidence_stddev": round(stddev, 6),
        "confidence_extreme_fraction": round(extreme_fraction, 6),
        "residue_confidence_unique_count": len({round(value, 3) for value in residue_means}),
    }
    return _payload(target_id, prediction_path, sequence_path, blockers, warnings, metrics)


def _round_or_none(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def _payload(
    target_id: str,
    prediction_path: Path,
    sequence_path: str | Path,
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    summary = {
        "packet_type": "casp17_confidence_calibration",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_id": target_id,
        "prediction_file_path": _artifact(prediction_path),
        "sequence_path": _artifact(sequence_path) if str(sequence_path).strip() else "",
        "confidence_calibration_status": "fail" if blockers else "pass",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "atom_confidence_count": metrics.get("atom_confidence_count", 0),
        "residue_confidence_count": metrics.get("residue_confidence_count", 0),
        "sequence_residue_count": metrics.get("sequence_residue_count", 0),
        "confidence_unique_count": metrics.get("confidence_unique_count", 0),
        "confidence_stddev": metrics.get("confidence_stddev", 0.0),
        "confidence_extreme_fraction": metrics.get("confidence_extreme_fraction", 0.0),
        "claim_boundary": "CASP17 confidence calibration sanity only; not true accuracy calibration or accepted submission evidence.",
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "metrics": metrics}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "confidence_calibration_status",
        "blocker_count",
        "warning_count",
        "atom_confidence_count",
        "residue_confidence_count",
        "sequence_residue_count",
        "confidence_unique_count",
        "confidence_stddev",
        "confidence_extreme_fraction",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Confidence Calibration",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- prediction file: `{summary['prediction_file_path']}`",
        f"- sequence file: `{summary['sequence_path'] or '-'}`",
        f"- confidence status: `{summary['confidence_calibration_status']}`",
        f"- confidence values: `{summary['atom_confidence_count']}`",
        f"- residue confidence count: `{summary['residue_confidence_count']}`",
        f"- unique confidence values: `{summary['confidence_unique_count']}`",
        f"- stddev: `{summary['confidence_stddev']}`",
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CASP17 TS B-factor confidence calibration sanity.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--prediction-file", required=True)
    parser.add_argument("--sequence-path", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = validate_confidence(
        target_id=args.target_id,
        prediction_file=args.prediction_file,
        sequence_path=args.sequence_path,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [payload["summary"]])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
