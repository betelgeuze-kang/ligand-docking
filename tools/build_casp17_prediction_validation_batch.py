#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools import validate_casp17_ts_prediction as ts_validator
from tools import validate_casp17_geometry_sanity as geometry_validator
from tools import validate_casp17_confidence_calibration as confidence_validator


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_prediction_imported_current.csv"
DEFAULT_OUT_DIR = "runs/casp17_validations_current"
DEFAULT_OUT_JSON = "runs/casp17_prediction_validation_batch_current.json"
DEFAULT_OUT_CSV = "runs/casp17_prediction_validation_batch_current.csv"
DEFAULT_OUT_MD = "runs/casp17_prediction_validation_batch_current.md"
DEFAULT_OUT_INTAKE_CSV = "runs/casp17_target_intake_validated_current.csv"

PASS_VALUES = {"pass", "passed", "green", "ready", "ok", "true", "1", "complete"}


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


def _status(value: Any) -> str:
    text = _text(value).lower()
    if text in PASS_VALUES:
        return "pass"
    if not text:
        return "missing"
    return text


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


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Prediction Validation Batch",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- intake CSV: `{summary['intake_csv']}`",
        f"- target rows: `{summary['target_row_count']}`",
        f"- validated/skipped/failed: `{summary['validated_count']}/{summary['skipped_count']}/{summary['failed_count']}`",
        f"- format pass/fail: `{summary['format_pass_count']}/{summary['format_fail_count']}`",
        f"- geometry pass/fail/skipped: `{summary['geometry_pass_count']}/{summary['geometry_fail_count']}/{summary['geometry_skipped_count']}`",
        f"- confidence pass/fail/skipped: `{summary['confidence_pass_count']}/{summary['confidence_fail_count']}/{summary['confidence_skipped_count']}`",
        f"- enriched intake: `{summary['out_intake_csv']}`",
        "",
        "## Rows",
        "",
        "| target | format | status | format | geometry | confidence | blockers | next step |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['submission_format']}` | `{row['validation_status']}` | "
            f"`{row['format_check_status']}` | `{row['geometry_sanity_status']}` | "
            f"`{row['confidence_calibration_status']}` | {row['blocker_count']} | {row['next_required_step']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `no_rows` | - | 0 | Add CASP17 intake rows. |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _target_validation_paths(out_dir: Path, target_id: str, fmt: str) -> tuple[Path, Path, Path]:
    stem = f"{target_id}_{fmt.lower()}_validation"
    return out_dir / f"{stem}.json", out_dir / f"{stem}.csv", out_dir / f"{stem}.md"


def _target_geometry_paths(out_dir: Path, target_id: str) -> tuple[Path, Path, Path]:
    stem = f"{target_id}_geometry_sanity"
    return out_dir / f"{stem}.json", out_dir / f"{stem}.csv", out_dir / f"{stem}.md"


def _target_confidence_paths(out_dir: Path, target_id: str) -> tuple[Path, Path, Path]:
    stem = f"{target_id}_confidence_calibration"
    return out_dir / f"{stem}.json", out_dir / f"{stem}.csv", out_dir / f"{stem}.md"


def _should_validate(row: dict[str, str], *, include_lg: bool) -> tuple[bool, str]:
    fmt = _text(row.get("submission_format")).upper()
    prediction_file = _text(row.get("prediction_file_path"))
    sequence_path = _text(row.get("sequence_path"))
    if fmt == "TS":
        if not prediction_file:
            return False, "missing_prediction_file_path"
        if not sequence_path:
            return False, "missing_sequence_path"
        return True, ""
    if fmt == "LG" and include_lg:
        return False, "lg_validation_not_implemented"
    if fmt == "QA":
        return False, "qa_validation_not_implemented"
    return False, f"unsupported_or_skipped_format:{fmt or 'missing'}"


def _run_ts_validation(row: dict[str, str], out_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    target_id = _text(row.get("target_id"))
    fmt = _text(row.get("submission_format")).upper()
    out_json, out_csv, out_md = _target_validation_paths(out_dir, target_id, fmt)
    payload = ts_validator.validate_prediction(
        target_id=target_id,
        prediction_file=_text(row.get("prediction_file_path")),
        sequence_path=_text(row.get("sequence_path")),
    )
    ts_validator._write_json(out_json, payload)
    ts_validator._write_csv(out_csv, [payload["summary"]])
    ts_validator._write_md(out_md, payload)
    enriched = dict(row)
    enriched["validation_json_path"] = _artifact(out_json)
    enriched["format_check_status"] = payload["summary"]["format_check_status"]
    return payload, enriched


def _run_geometry_validation(row: dict[str, str], out_dir: Path) -> tuple[dict[str, Any], str]:
    target_id = _text(row.get("target_id"))
    out_json, out_csv, out_md = _target_geometry_paths(out_dir, target_id)
    payload = geometry_validator.validate_geometry(
        target_id=target_id,
        prediction_file=_text(row.get("prediction_file_path")),
    )
    geometry_validator._write_json(out_json, payload)
    geometry_validator._write_csv(out_csv, [payload["summary"]])
    geometry_validator._write_md(out_md, payload)
    return payload, _artifact(out_json)


def _run_confidence_validation(row: dict[str, str], out_dir: Path) -> tuple[dict[str, Any], str]:
    target_id = _text(row.get("target_id"))
    out_json, out_csv, out_md = _target_confidence_paths(out_dir, target_id)
    payload = confidence_validator.validate_confidence(
        target_id=target_id,
        prediction_file=_text(row.get("prediction_file_path")),
        sequence_path=_text(row.get("sequence_path")),
    )
    confidence_validator._write_json(out_json, payload)
    confidence_validator._write_csv(out_csv, [payload["summary"]])
    confidence_validator._write_md(out_md, payload)
    return payload, _artifact(out_json)


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = [row for row in _read_csv(args.intake_csv) if _text(row.get("target_id"))]
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    enriched_rows: list[dict[str, str]] = []
    batch_rows: list[dict[str, Any]] = []

    for row in rows:
        target_id = _text(row.get("target_id"))
        fmt = _text(row.get("submission_format")).upper()
        should_validate, skip_reason = _should_validate(row, include_lg=args.include_lg)
        enriched = dict(row)
        if not should_validate:
            batch_rows.append(
                {
                    "target_id": target_id,
                    "submission_format": fmt,
                    "validation_status": "skipped",
                    "validation_json_path": _text(row.get("validation_json_path")),
                    "format_check_status": _status(row.get("format_check_status")),
                    "geometry_sanity_status": _status(row.get("geometry_sanity_status")),
                    "geometry_validation_json_path": _text(row.get("geometry_validation_json_path")),
                    "confidence_calibration_status": _status(row.get("confidence_calibration_status")),
                    "confidence_validation_json_path": _text(row.get("confidence_validation_json_path")),
                    "blocker_count": "",
                    "warning_count": "",
                    "skip_reason": skip_reason,
                    "next_required_step": _skip_next_step(skip_reason),
                }
            )
            enriched_rows.append(enriched)
            continue

        payload, enriched = _run_ts_validation(row, out_dir)
        summary = payload["summary"]
        geometry_payload: dict[str, Any] | None = None
        geometry_json_path = _text(row.get("geometry_validation_json_path"))
        confidence_payload: dict[str, Any] | None = None
        confidence_json_path = _text(row.get("confidence_validation_json_path"))
        if summary["format_check_status"] == "pass":
            geometry_payload, geometry_json_path = _run_geometry_validation(enriched, out_dir)
            enriched["geometry_sanity_status"] = geometry_payload["summary"]["geometry_sanity_status"]
            enriched["geometry_validation_json_path"] = geometry_json_path
            if enriched["geometry_sanity_status"] == "pass":
                confidence_payload, confidence_json_path = _run_confidence_validation(enriched, out_dir)
                enriched["confidence_calibration_status"] = confidence_payload["summary"]["confidence_calibration_status"]
                enriched["confidence_validation_json_path"] = confidence_json_path
            else:
                enriched["confidence_calibration_status"] = "blocked_by_geometry_failure"
        else:
            enriched["geometry_sanity_status"] = "blocked_by_format_failure"
            enriched["confidence_calibration_status"] = "blocked_by_format_failure"
        batch_rows.append(
            {
                "target_id": target_id,
                "submission_format": fmt,
                "validation_status": "validated",
                "validation_json_path": enriched["validation_json_path"],
                "format_check_status": summary["format_check_status"],
                "geometry_sanity_status": enriched.get("geometry_sanity_status", _status(row.get("geometry_sanity_status"))),
                "geometry_validation_json_path": geometry_json_path,
                "confidence_calibration_status": enriched.get(
                    "confidence_calibration_status",
                    _status(row.get("confidence_calibration_status")),
                ),
                "confidence_validation_json_path": confidence_json_path,
                "blocker_count": summary["blocker_count"],
                "warning_count": summary["warning_count"],
                "skip_reason": "",
                "next_required_step": _validated_next_step(summary, geometry_payload, confidence_payload),
            }
        )
        enriched_rows.append(enriched)

    validated_count = sum(1 for row in batch_rows if row["validation_status"] == "validated")
    skipped_count = sum(1 for row in batch_rows if row["validation_status"] == "skipped")
    format_pass_count = sum(1 for row in batch_rows if row["format_check_status"] == "pass")
    format_fail_count = sum(1 for row in batch_rows if row["format_check_status"] == "fail")
    geometry_pass_count = sum(1 for row in batch_rows if row.get("geometry_sanity_status") == "pass")
    geometry_fail_count = sum(1 for row in batch_rows if row.get("geometry_sanity_status") == "fail")
    geometry_skipped_count = sum(
        1 for row in batch_rows if row.get("geometry_sanity_status") in {"missing", "", "blocked_by_format_failure"}
    )
    confidence_pass_count = sum(1 for row in batch_rows if row.get("confidence_calibration_status") == "pass")
    confidence_fail_count = sum(1 for row in batch_rows if row.get("confidence_calibration_status") == "fail")
    confidence_skipped_count = sum(
        1
        for row in batch_rows
        if row.get("confidence_calibration_status")
        in {"missing", "", "blocked_by_format_failure", "blocked_by_geometry_failure"}
    )
    failed_count = sum(
        1 for row in batch_rows if row["validation_status"] == "validated" and row["format_check_status"] != "pass"
    )
    summary = {
        "packet_type": "casp17_prediction_validation_batch",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_csv": _artifact(args.intake_csv),
        "out_dir": _artifact(out_dir),
        "out_intake_csv": _artifact(args.out_intake_csv),
        "target_row_count": len(batch_rows),
        "validated_count": validated_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "format_pass_count": format_pass_count,
        "format_fail_count": format_fail_count,
        "geometry_pass_count": geometry_pass_count,
        "geometry_fail_count": geometry_fail_count,
        "geometry_skipped_count": geometry_skipped_count,
        "confidence_pass_count": confidence_pass_count,
        "confidence_fail_count": confidence_fail_count,
        "confidence_skipped_count": confidence_skipped_count,
        "claim_boundary": "Batch format/geometry/confidence sanity validation and intake enrichment only; not structure accuracy or accepted CASP17 submission evidence.",
    }
    return {"summary": summary, "rows": batch_rows}, enriched_rows


def _skip_next_step(reason: str) -> str:
    if reason == "missing_prediction_file_path":
        return "Generate or attach a target-specific prediction file before validation."
    if reason == "missing_sequence_path":
        return "Materialize CASP17 target sequence with build_casp17_sequence_packet.py."
    if reason == "qa_validation_not_implemented":
        return "Add QA-specific validation before enabling accuracy-estimation submission."
    if reason == "lg_validation_not_implemented":
        return "Add LG-specific validation before enabling ligand-only submission."
    return "Review submission_format and target intake row."


def _validated_next_step(
    summary: dict[str, Any],
    geometry_payload: dict[str, Any] | None = None,
    confidence_payload: dict[str, Any] | None = None,
) -> str:
    if summary.get("format_check_status") == "pass":
        if geometry_payload and geometry_payload.get("summary", {}).get("geometry_sanity_status") == "pass":
            if confidence_payload and confidence_payload.get("summary", {}).get("confidence_calibration_status") == "pass":
                return "Run internal scorecard, then re-run submission gate."
            return "Fix confidence calibration blockers, regenerate validation batch, then re-run submission gate."
        return "Fix geometry sanity blockers, regenerate validation batch, then re-run submission gate."
    return "Fix CASP17 format blockers, regenerate validation JSON, then re-run submission gate."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-validate CASP17 prediction files and enrich the intake CSV.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-intake-csv", default=DEFAULT_OUT_INTAKE_CSV)
    parser.add_argument("--include-lg", action="store_true", help="Reserve flag for future LG validation; currently records skipped LG rows.")
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
