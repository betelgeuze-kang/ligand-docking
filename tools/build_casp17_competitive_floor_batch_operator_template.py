#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BATCH_JSON = "casp17/casp17_competitive_floor_batch_current.json"
DEFAULT_OUT_TEMPLATE_CSV = "casp17/casp17_competitive_floor_batch_operator_template_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_batch_operator_template_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_batch_operator_template_audit_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_OPERATOR_TEMPLATE.md"

PROVENANCE_COLUMNS = [
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]
ABLATION_LAYER_NAMES = [
    "recursive",
    "scored",
    "sidechain_scaffold",
    "sidechain_repacked",
    "sidechain_completed",
    "steric_relaxed",
    "rotamer_minimized",
    "polar_refined",
    "forcefield_minimized",
    "statistical_rotamer",
]
ABLATION_COLUMNS = [f"{layer}_prediction_pdb" for layer in ABLATION_LAYER_NAMES]
CALIBRATION_COLUMNS = [
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
]
OUTPUT_COLUMNS = (
    ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb"]
    + PROVENANCE_COLUMNS
    + ABLATION_COLUMNS
    + CALIBRATION_COLUMNS
)

CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}

CLAIM_BOUNDARY = (
    "Local competitive-floor operator-template builder only. It assembles a candidate operator CSV from filled "
    "batch folders and audits local placeholders/files; it does not fetch natives, clear provenance, score native "
    "accuracy, overwrite active benchmark manifests, use external predictors, or submit to CASP."
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


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
        resolved = ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if _contains_placeholder(text):
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(_text(value))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _rank_ok(value: Any) -> bool:
    try:
        parsed = int(_text(value))
    except ValueError:
        return False
    return 1 <= parsed <= 5


def _first_row(path_like: str | Path) -> tuple[dict[str, str], list[str]]:
    rows, blockers = _read_csv(path_like)
    return (rows[0] if rows else {}), blockers


def _candidate_from_row_fill(path: Path) -> tuple[dict[str, str], str, list[str]]:
    row, blockers = _first_row(path)
    candidate = {column: _text(row.get(column)) for column in OUTPUT_COLUMNS}
    candidate["target_id"] = candidate["target_id"].upper()
    candidate["scope"] = candidate["scope"].lower()
    candidate["split"] = candidate["split"] or "historical"
    return candidate, _artifact(path), blockers


def _metadata_for(batch_row: dict[str, Any], batch_folder: Path) -> tuple[dict[str, str], str, str, list[str]]:
    operator_path = batch_folder / "row_metadata.csv"
    template_path = batch_folder / "row_metadata_template.csv"
    for label, path in [("operator", operator_path), ("template", template_path)]:
        metadata, blockers = _first_row(path)
        if metadata:
            return metadata, _artifact(path), label, blockers
    fallback = {
        "benchmark_id": _text(batch_row.get("benchmark_id")),
        "target_id": _text(batch_row.get("target_id")),
        "scope": _text(batch_row.get("scope")),
        "split": "historical",
    }
    return fallback, "", "derived_from_batch_row", ["row_metadata_csv_missing"]


def _required_file_map(rows: list[dict[str, str]]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for row in rows:
        column = _text(row.get("template_column"))
        if column:
            mapped[column] = _text(row.get("expected_path"))
    return mapped


def _provenance_blockers(candidate: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    if _text(candidate.get("leakage_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("leakage_clearance_requires_no_leak_clearance")
    if _contains_placeholder(candidate.get("prediction_method")):
        blockers.append("prediction_method_required")
    prediction_created_at = _date_or_none(candidate.get("prediction_created_at"))
    native_release_date = _date_or_none(candidate.get("native_release_date"))
    if prediction_created_at is None:
        blockers.append("prediction_created_at_requires_iso_date")
    if native_release_date is None:
        blockers.append("native_release_date_requires_iso_date")
    if prediction_created_at and native_release_date and prediction_created_at >= native_release_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(candidate.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_before_native_release_confirmation_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(candidate.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    if _text(candidate.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_requires_no_leak_clearance")
    return blockers


def _calibration_blockers(candidate: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    if not _rank_ok(candidate.get("selected_model_rank")):
        blockers.append("selected_model_rank_requires_rank_1_to_5")
    if not _rank_ok(candidate.get("best_model_rank")):
        blockers.append("best_model_rank_requires_rank_1_to_5")
    selected_native = _float_or_none(candidate.get("selected_native_metric"))
    best_native = _float_or_none(candidate.get("best_native_metric"))
    if selected_native is None:
        blockers.append("selected_native_metric_requires_numeric")
    if best_native is None:
        blockers.append("best_native_metric_requires_numeric")
    if selected_native is not None and best_native is not None and selected_native > best_native + 1e-9:
        blockers.append("selected_native_metric_exceeds_oracle_metric")
    if _float_or_none(candidate.get("selected_score")) is None:
        blockers.append("selected_score_requires_numeric")
    if _float_or_none(candidate.get("best_score")) is None:
        blockers.append("best_score_requires_numeric")
    return blockers


def _file_blockers(candidate: dict[str, str]) -> tuple[list[str], int, int]:
    blockers: list[str] = []
    missing_count = 0
    placeholder_count = 0
    for column in ["prediction_pdb", "native_pdb"] + ABLATION_COLUMNS:
        path_text = _text(candidate.get(column))
        if _contains_placeholder(path_text):
            placeholder_count += 1
            blockers.append(f"{column}_placeholder")
        elif not _resolve(path_text).exists():
            missing_count += 1
            blockers.append(f"{column}_not_found")
    return blockers, missing_count, placeholder_count


def _candidate_from_batch_row(batch_row: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    batch_folder_text = _text(batch_row.get("batch_folder"))
    batch_folder = _resolve(batch_folder_text) if batch_folder_text else ROOT / "__missing_competitive_batch_folder__"
    scaffold_text = _text(batch_row.get("copied_row_scaffold"))
    scaffold = _resolve(scaffold_text) if scaffold_text else batch_folder / "row_scaffold"
    row_fill_csv = batch_folder / "row_fill.csv"
    blockers: list[str] = []
    if not batch_folder.is_dir():
        blockers.append("batch_folder_missing")

    candidate_source = ""
    candidate_source_type = ""
    if row_fill_csv.exists():
        candidate, candidate_source, fill_blockers = _candidate_from_row_fill(row_fill_csv)
        candidate_source_type = "row_fill_csv"
        blockers.extend(fill_blockers)
    else:
        if not scaffold.is_dir():
            blockers.append("row_scaffold_missing")

        metadata, metadata_source, metadata_source_type, metadata_blockers = _metadata_for(batch_row, batch_folder)
        required_files, required_file_blockers = _read_csv(scaffold / "required_files.csv")
        provenance, provenance_source_blockers = _first_row(scaffold / "provenance_template.csv")
        calibration, calibration_source_blockers = _first_row(scaffold / "calibration_template.csv")
        blockers.extend(metadata_blockers)
        blockers.extend(required_file_blockers)
        blockers.extend(provenance_source_blockers)
        blockers.extend(calibration_source_blockers)

        required_map = _required_file_map(required_files)
        candidate = {
            "benchmark_id": _text(metadata.get("benchmark_id")),
            "target_id": _text(metadata.get("target_id")).upper(),
            "scope": _text(metadata.get("scope")).lower(),
            "split": _text(metadata.get("split")) or "historical",
            "prediction_pdb": required_map.get("prediction_pdb", ""),
            "native_pdb": required_map.get("native_pdb", ""),
        }
        for column in PROVENANCE_COLUMNS:
            candidate[column] = _text(provenance.get(column))
        for column in ABLATION_COLUMNS:
            candidate[column] = _text(required_map.get(column, ""))
        for column in CALIBRATION_COLUMNS:
            candidate[column] = _text(calibration.get(column))
        candidate_source = metadata_source
        candidate_source_type = metadata_source_type

    if _contains_placeholder(candidate["benchmark_id"]):
        blockers.append("placeholder_benchmark_id")
    if _contains_placeholder(candidate["target_id"]):
        blockers.append("placeholder_target_id")
    if candidate["scope"] not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")

    file_blockers, missing_file_count, placeholder_file_path_count = _file_blockers(candidate)
    provenance_blockers = _provenance_blockers(candidate)
    calibration_blockers = _calibration_blockers(candidate)
    blockers.extend(file_blockers)
    blockers.extend(provenance_blockers)
    blockers.extend(calibration_blockers)

    unique_blockers = sorted({blocker for blocker in blockers if blocker})
    audit = {
        "operator_priority": _int(batch_row.get("operator_priority")),
        "row_rank": _int(batch_row.get("row_rank")),
        "benchmark_id": candidate["benchmark_id"],
        "target_id": candidate["target_id"],
        "scope": candidate["scope"],
        "template_row_status": "ready_for_preflight" if not unique_blockers else "blocked",
        "batch_folder": _artifact(batch_folder),
        "copied_row_scaffold": _artifact(scaffold),
        "candidate_source": candidate_source,
        "candidate_source_type": candidate_source_type,
        "row_fill_csv": _artifact(row_fill_csv),
        "missing_file_count": missing_file_count,
        "placeholder_file_path_count": placeholder_file_path_count,
        "provenance_blocker_count": len(provenance_blockers),
        "calibration_blocker_count": len(calibration_blockers),
        "blockers": ",".join(unique_blockers),
    }
    return candidate, audit


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    batch_payload = _read_json(args.batch_json)
    batch_summary = _summary(batch_payload)
    operator_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, Any]] = []
    for batch_row in _rows(batch_payload):
        candidate, audit = _candidate_from_batch_row(batch_row)
        operator_rows.append(candidate)
        audit_rows.append(audit)
    ready_rows = [row for row in audit_rows if row["template_row_status"] == "ready_for_preflight"]
    summary = {
        "packet_type": "casp17_competitive_floor_batch_operator_template",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "template_status": "ready_for_preflight" if operator_rows and len(ready_rows) == len(operator_rows) else "blocked",
        "batch_json": _artifact(args.batch_json),
        "batch_status": _text(batch_summary.get("batch_status")),
        "operator_template_csv": _artifact(args.out_template_csv),
        "audit_csv": _artifact(args.out_csv),
        "row_count": len(operator_rows),
        "ready_for_preflight_count": len(ready_rows),
        "blocked_count": len(operator_rows) - len(ready_rows),
        "row_fill_candidate_count": sum(1 for row in audit_rows if row["candidate_source_type"] == "row_fill_csv"),
        "monomer_row_count": sum(1 for row in audit_rows if row["scope"] == "monomer"),
        "complex_row_count": sum(1 for row in audit_rows if row["scope"] == "complex"),
        "missing_file_count": sum(int(row["missing_file_count"]) for row in audit_rows),
        "placeholder_file_path_count": sum(int(row["placeholder_file_path_count"]) for row in audit_rows),
        "provenance_blocker_count": sum(int(row["provenance_blocker_count"]) for row in audit_rows),
        "calibration_blocker_count": sum(int(row["calibration_blocker_count"]) for row in audit_rows),
        "operator_preflight_command": (
            "python3 tools/build_casp17_win_tier_benchmark_operator_preflight.py "
            f"--operator-template-csv {_artifact(args.out_template_csv)} "
            f"--min-ready-total {int(args.min_ready_total)} "
            f"--min-ready-monomer {int(args.min_ready_monomer)} "
            f"--min-ready-complex {int(args.min_ready_complex)}"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": audit_rows, "operator_rows": operator_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Operator Template",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- template_status: `{summary['template_status']}`",
        f"- rows ready/blocked/total: `{summary['ready_for_preflight_count']}/{summary['blocked_count']}/{summary['row_count']}`",
        f"- row_fill candidates: `{summary['row_fill_candidate_count']}`",
        f"- rows monomer/complex: `{summary['monomer_row_count']}/{summary['complex_row_count']}`",
        f"- missing files / placeholder paths: `{summary['missing_file_count']}/{summary['placeholder_file_path_count']}`",
        f"- provenance/calibration blockers: `{summary['provenance_blocker_count']}/{summary['calibration_blocker_count']}`",
        f"- operator_template_csv: `{summary['operator_template_csv']}`",
        f"- audit_csv: `{summary['audit_csv']}`",
        "",
        "## Next Command",
        "",
        f"`{summary['operator_preflight_command']}`",
        "",
        "## Rows",
        "",
        "| priority | benchmark | target | scope | status | source | missing files | placeholder paths | provenance blockers | calibration blockers | blockers |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['template_row_status']}` | `{row['candidate_source_type'] or '-'}` | {row['missing_file_count']} | {row['placeholder_file_path_count']} | "
            f"{row['provenance_blocker_count']} | {row['calibration_blocker_count']} | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-template candidate from filled competitive-floor batch folders.")
    parser.add_argument("--batch-json", default=DEFAULT_BATCH_JSON)
    parser.add_argument("--out-template-csv", default=DEFAULT_OUT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--min-ready-total", type=int, default=15)
    parser.add_argument("--min-ready-monomer", type=int, default=10)
    parser.add_argument("--min-ready-complex", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_csv(args.out_template_csv, payload["operator_rows"], fieldnames=OUTPUT_COLUMNS)
    _write_json(args.out_json, {"summary": payload["summary"], "rows": payload["rows"]})
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
