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

DEFAULT_PREDICTION_DIR = "runs/casp17_historical_benchmark_predictions_current"
DEFAULT_NATIVE_DIR = "runs/casp17_historical_benchmark_natives_current"
DEFAULT_EXISTING_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_current.csv"
DEFAULT_PROVENANCE_CSV = "runs/casp17_historical_benchmark_provenance_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_historical_benchmark_manifest_scaffold_current.json"
DEFAULT_OUT_CSV = "runs/casp17_historical_benchmark_manifest_scaffold_current.csv"
DEFAULT_OUT_MD = "runs/casp17_historical_benchmark_manifest_scaffold_current.md"
DEFAULT_OUT_PROVENANCE_TEMPLATE_CSV = "runs/casp17_historical_benchmark_provenance_template_current.csv"

LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
REQUIRED_COLUMNS = ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"]
PROVENANCE_COLUMNS = [
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
OUTPUT_COLUMNS = REQUIRED_COLUMNS + PROVENANCE_COLUMNS
OPTIONAL_ABLATION_LAYER_NAMES = [
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
OPTIONAL_ABLATION_LAYER_COLUMNS = [f"{layer}_prediction_pdb" for layer in OPTIONAL_ABLATION_LAYER_NAMES]
STATUS_COLUMNS = {"manifest_ready_status", "promotion_status", "blockers"}
TARGET_PATTERN = re.compile(r"([A-Z][0-9]{4})")


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


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for key in OUTPUT_COLUMNS + OPTIONAL_ABLATION_LAYER_COLUMNS + ["manifest_ready_status", "blockers"]:
        if key not in fieldnames:
            fieldnames.append(key)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_provenance_template_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> str:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["benchmark_id", "target_id", "scope", "split", "leakage_clearance", *PROVENANCE_COLUMNS, *OPTIONAL_ABLATION_LAYER_COLUMNS]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "benchmark_id": _text(row.get("benchmark_id")),
                    "target_id": _text(row.get("target_id")),
                    "scope": _text(row.get("scope")),
                    "split": _text(row.get("split")) or "historical",
                    "leakage_clearance": _text(row.get("leakage_clearance")) or "REQUIRED_NO_LEAK_CLEARANCE",
                    "prediction_method": _text(row.get("prediction_method")) or "REQUIRED_INTERNAL_METHOD",
                    "prediction_created_at": _text(row.get("prediction_created_at")) or "YYYY-MM-DD",
                    "native_release_date": _text(row.get("native_release_date")) or "YYYY-MM-DD",
                    "prediction_generated_before_native_release": _text(row.get("prediction_generated_before_native_release"))
                    or "REQUIRED_TRUE_CONFIRMATION",
                    "public_template_or_native_used_for_prediction": _text(row.get("public_template_or_native_used_for_prediction"))
                    or "REQUIRED_FALSE_CONFIRMATION",
                    "other_team_model_used": _text(row.get("other_team_model_used")) or "REQUIRED_FALSE_CONFIRMATION",
                    "post_release_information_used": _text(row.get("post_release_information_used")) or "REQUIRED_FALSE_CONFIRMATION",
                    "current_casp17_target": _text(row.get("current_casp17_target")) or "REQUIRED_FALSE_CONFIRMATION",
                    "operator_clearance": _text(row.get("operator_clearance")) or "REQUIRED_OPERATOR_CLEARANCE",
                    **{column: _text(row.get(column)) for column in OPTIONAL_ABLATION_LAYER_COLUMNS},
                }
            )
    return _artifact(path)


def _target_id_from_path(path: Path) -> str:
    match = TARGET_PATTERN.search(path.stem.upper())
    return match.group(1) if match else path.stem.upper()


def _scope_for_target(target_id: str, fallback: str = "") -> str:
    fallback = fallback.lower()
    if fallback in {"monomer", "complex"}:
        return fallback
    return "complex" if target_id.upper().startswith("H") else "monomer"


def _scan_pdbs(path_like: str | Path) -> dict[str, Path]:
    root = _resolve(path_like)
    if not root.exists():
        return {}
    paths: dict[str, Path] = {}
    for path in sorted(root.glob("*.pdb")):
        target_id = _target_id_from_path(path)
        paths.setdefault(target_id, path)
    return paths


def _normalize_row(row: dict[str, str], *, index: int) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).upper() or _text(row.get("benchmark_id")).upper() or f"BENCHMARK_{index}"
    prediction_pdb = _text(row.get("prediction_pdb") or row.get("prediction_file"))
    native_pdb = _text(row.get("native_pdb") or row.get("native_file"))
    leakage = _text(row.get("leakage_clearance") or row.get("no_leak_status"))
    normalized = {
        "benchmark_id": _text(row.get("benchmark_id")) or f"hist_{target_id}",
        "target_id": target_id,
        "scope": _scope_for_target(target_id, _text(row.get("scope"))),
        "split": _text(row.get("split")) or "historical",
        "prediction_pdb": _artifact(prediction_pdb) if prediction_pdb else "",
        "native_pdb": _artifact(native_pdb) if native_pdb else "",
        "leakage_clearance": leakage or "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": _text(row.get("prediction_method")),
        "prediction_created_at": _text(row.get("prediction_created_at")),
        "native_release_date": _text(row.get("native_release_date")),
        "prediction_generated_before_native_release": _text(row.get("prediction_generated_before_native_release")),
        "public_template_or_native_used_for_prediction": _text(row.get("public_template_or_native_used_for_prediction")),
        "other_team_model_used": _text(row.get("other_team_model_used")),
        "post_release_information_used": _text(row.get("post_release_information_used")),
        "current_casp17_target": _text(row.get("current_casp17_target")),
        "operator_clearance": _text(row.get("operator_clearance")),
    }
    for key, value in row.items():
        if key and key not in normalized and key not in STATUS_COLUMNS:
            normalized[key] = _text(value)
    return _with_status(normalized)


def _scanned_row(target_id: str, prediction: Path | None, native: Path | None) -> dict[str, Any]:
    row = {
        "benchmark_id": f"hist_{target_id}",
        "target_id": target_id,
        "scope": _scope_for_target(target_id),
        "split": "historical",
        "prediction_pdb": _artifact(prediction) if prediction else "",
        "native_pdb": _artifact(native) if native else "",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "",
        "prediction_created_at": "",
        "native_release_date": "",
        "prediction_generated_before_native_release": "",
        "public_template_or_native_used_for_prediction": "",
        "other_team_model_used": "",
        "post_release_information_used": "",
        "current_casp17_target": "",
        "operator_clearance": "",
    }
    return _with_status(row)


def _lookup_keys(row: dict[str, Any]) -> set[str]:
    keys = {_text(row.get("target_id")).upper(), _text(row.get("benchmark_id")).upper()}
    return {key for key in keys if key}


def _provenance_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        for key in _lookup_keys(row):
            lookup.setdefault(key, row)
    return lookup


def _merge_provenance(row: dict[str, Any], lookup: dict[str, dict[str, str]]) -> tuple[dict[str, Any], bool]:
    provenance: dict[str, str] | None = None
    for key in _lookup_keys(row):
        provenance = lookup.get(key)
        if provenance is not None:
            break
    if provenance is None:
        return row, False
    merged = dict(row)
    for column in [
        "benchmark_id",
        "scope",
        "split",
        "leakage_clearance",
        *PROVENANCE_COLUMNS,
        *OPTIONAL_ABLATION_LAYER_COLUMNS,
    ]:
        value = _text(provenance.get(column))
        if value:
            merged[column] = value
    return _with_status(merged), True


def _placeholder_rows() -> list[dict[str, Any]]:
    return [
        _with_status(
            {
                "benchmark_id": "hist_REQUIRED_MONOMER",
                "target_id": "REQUIRED_MONOMER",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": f"{DEFAULT_PREDICTION_DIR}/REQUIRED_MONOMER_prediction.pdb",
                "native_pdb": f"{DEFAULT_NATIVE_DIR}/REQUIRED_MONOMER_native.pdb",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "prediction_method": "REQUIRED_INTERNAL_METHOD",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "true",
                "public_template_or_native_used_for_prediction": "false",
                "other_team_model_used": "false",
                "post_release_information_used": "false",
                "current_casp17_target": "false",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
            }
        ),
        _with_status(
            {
                "benchmark_id": "hist_REQUIRED_COMPLEX",
                "target_id": "REQUIRED_COMPLEX",
                "scope": "complex",
                "split": "historical",
                "prediction_pdb": f"{DEFAULT_PREDICTION_DIR}/REQUIRED_COMPLEX_prediction.pdb",
                "native_pdb": f"{DEFAULT_NATIVE_DIR}/REQUIRED_COMPLEX_native.pdb",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "prediction_method": "REQUIRED_INTERNAL_METHOD",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "true",
                "public_template_or_native_used_for_prediction": "false",
                "other_team_model_used": "false",
                "post_release_information_used": "false",
                "current_casp17_target": "false",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
            }
        ),
    ]


def _with_status(row: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    prediction = _text(row.get("prediction_pdb"))
    native = _text(row.get("native_pdb"))
    leakage = _text(row.get("leakage_clearance")).lower()
    if not prediction:
        blockers.append("prediction_pdb_missing")
    elif not _resolve(prediction).exists():
        blockers.append("prediction_pdb_not_found")
    if not native:
        blockers.append("native_pdb_missing")
    elif not _resolve(native).exists():
        blockers.append("native_pdb_not_found")
    if leakage not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if not _text(row.get("prediction_method")):
        blockers.append("prediction_method_required")
    prediction_created_at = _date_or_none(row.get("prediction_created_at"))
    native_release_date = _date_or_none(row.get("native_release_date"))
    if prediction_created_at is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_release_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_created_at is not None and native_release_date is not None and prediction_created_at >= native_release_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    if _text(row.get("operator_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    row["manifest_ready_status"] = "ready" if not blockers else "blocked"
    row["blockers"] = ",".join(blockers)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    manifest_rows = _read_csv(args.existing_manifest_csv)
    provenance_rows = _read_csv(args.provenance_csv)
    provenance_by_id = _provenance_lookup(provenance_rows)
    provenance_applied_count = 0
    if manifest_rows:
        rows = [_normalize_row(row, index=index + 1) for index, row in enumerate(manifest_rows)]
        source_mode = "existing_manifest"
    else:
        predictions = _scan_pdbs(args.prediction_dir)
        natives = _scan_pdbs(args.native_dir)
        target_ids = sorted(set(predictions) | set(natives))
        rows = []
        for target_id in target_ids:
            row, applied = _merge_provenance(_scanned_row(target_id, predictions.get(target_id), natives.get(target_id)), provenance_by_id)
            rows.append(row)
            provenance_applied_count += int(applied)
        source_mode = "scanned_local_dirs"
        if not rows:
            rows = _placeholder_rows()
            source_mode = "placeholder_required_inputs"
    provenance_template_csv = _write_provenance_template_csv(args.out_provenance_template_csv, rows)
    ready_count = sum(1 for row in rows if row["manifest_ready_status"] == "ready")
    blocked_count = len(rows) - ready_count
    monomer_count = sum(1 for row in rows if row.get("scope") == "monomer")
    complex_count = sum(1 for row in rows if row.get("scope") == "complex")
    preserved_extra_columns = sorted(
        {
            key
            for row in rows
            for key in row
            if key not in set(OUTPUT_COLUMNS) | STATUS_COLUMNS
        }
    )
    summary = {
        "packet_type": "casp17_historical_benchmark_manifest_scaffold",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "prediction_dir": _artifact(args.prediction_dir),
        "native_dir": _artifact(args.native_dir),
        "existing_manifest_csv": _artifact(args.existing_manifest_csv),
        "provenance_csv": _artifact(args.provenance_csv),
        "provenance_row_count": len(provenance_rows),
        "provenance_applied_count": provenance_applied_count,
        "provenance_template_csv": provenance_template_csv,
        "source_mode": source_mode,
        "candidate_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "monomer_candidate_count": monomer_count,
        "complex_candidate_count": complex_count,
        "scaffold_status": "ready" if rows and blocked_count == 0 else "blocked",
        "required_manifest_columns": ",".join(REQUIRED_COLUMNS),
        "required_provenance_columns": ",".join(PROVENANCE_COLUMNS),
        "optional_ablation_layer_columns": ",".join(OPTIONAL_ABLATION_LAYER_COLUMNS),
        "preserved_extra_columns": ",".join(preserved_extra_columns),
        "preserved_extra_column_count": len(preserved_extra_columns),
        "claim_boundary": "Local manifest scaffold only; it does not fetch native structures, clear provenance, score accuracy, or submit to CASP.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Benchmark Manifest Scaffold",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_mode: `{summary['source_mode']}`",
        f"- prediction_dir: `{summary['prediction_dir']}`",
        f"- native_dir: `{summary['native_dir']}`",
        f"- provenance_csv: `{summary['provenance_csv']}`",
        f"- provenance rows/applied/template: `{summary['provenance_row_count']}/{summary['provenance_applied_count']}/{summary['provenance_template_csv']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- ready/blocked: `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- monomer/complex candidates: `{summary['monomer_candidate_count']}/{summary['complex_candidate_count']}`",
        f"- scaffold_status: `{summary['scaffold_status']}`",
        "",
        "## Required Manifest Columns",
        "",
        f"`{summary['required_manifest_columns']}`",
        "",
        "## Required No-Leak Provenance Columns",
        "",
        f"`{summary['required_provenance_columns']}`",
        "",
        "## Preserved Extra Columns",
        "",
        f"`{summary['preserved_extra_columns'] or '-'}`",
        "",
        "## Optional Refinement-Ablation Layer Columns",
        "",
        f"`{summary['optional_ablation_layer_columns']}`",
        "",
        "## Checklist",
        "",
        "| benchmark | target | scope | ready | prediction_pdb | native_pdb | leakage | prediction/native dates | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | `{row['manifest_ready_status']}` | "
            f"`{row['prediction_pdb'] or '-'}` | `{row['native_pdb'] or '-'}` | `{row['leakage_clearance']}` | "
            f"`{row.get('prediction_created_at') or '-'}/{row.get('native_release_date') or '-'}` | {row['blockers'] or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Use",
            "",
            "Only rows with `manifest_ready_status=ready` should be copied into `runs/casp17_historical_benchmark_manifest_current.csv` for scoring.",
            "Every ready row still needs an operator-owned no-leak decision; do not mark current CASP17 targets or public/template-derived models as no-leak benchmark evidence.",
            "",
            "## Claim Boundary",
            "",
            str(summary["claim_boundary"]),
            "",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local-only CASP17 historical benchmark manifest scaffold/checklist.")
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--native-dir", default=DEFAULT_NATIVE_DIR)
    parser.add_argument("--existing-manifest-csv", default=DEFAULT_EXISTING_MANIFEST_CSV)
    parser.add_argument("--provenance-csv", default=DEFAULT_PROVENANCE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-provenance-template-csv", default=DEFAULT_OUT_PROVENANCE_TEMPLATE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
