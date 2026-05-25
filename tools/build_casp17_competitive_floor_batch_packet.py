#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FILL_PRIORITY_JSON = "runs/casp17_win_tier_benchmark_fill_priority_packet_current.json"
DEFAULT_OUT_DIR = "casp17/competitive_floor_batch_current"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_batch_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_batch_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_BATCH.md"
CLAIM_BOUNDARY = (
    "Local competitive-floor batch packet only. It organizes the first no-leak historical benchmark rows to fill; "
    "it does not fetch natives, clear provenance, score accuracy, use external predictors, or submit to CASP."
)
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
ROW_FILL_COLUMNS = (
    ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb"]
    + PROVENANCE_COLUMNS
    + ABLATION_COLUMNS
    + CALIBRATION_COLUMNS
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["operator_priority", "benchmark_id", "target_id", "batch_row_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _batch_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in _rows(payload) if _text(row.get("fill_batch")) == "competitive_floor_batch"]
    return sorted(rows, key=lambda row: (_int(row.get("operator_priority")), _int(row.get("row_rank"))))


def _copy_row_dir(source_text: str, dest_dir: Path) -> tuple[str, str]:
    source = _resolve(source_text)
    if not source_text:
        return "", "row_dir_missing"
    if not source.is_dir():
        return "", "row_dir_not_found"
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(source, dest_dir)
    return _artifact(dest_dir), ""


def _write_metadata_template(row: dict[str, Any], folder: Path) -> str:
    path = folder / "row_metadata_template.csv"
    fieldnames = ["benchmark_id", "target_id", "scope", "split"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": _text(row.get("benchmark_id")),
                "target_id": _text(row.get("target_id")),
                "scope": _text(row.get("scope")),
                "split": "historical",
            }
        )
    return _artifact(path)


def _required_file_map(scaffold_dir: Path) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for row in _read_csv(scaffold_dir / "required_files.csv"):
        column = _text(row.get("template_column"))
        if column:
            mapped[column] = _text(row.get("expected_path"))
    return mapped


def _first_csv_row(path: Path) -> dict[str, str]:
    rows = _read_csv(path)
    return rows[0] if rows else {}


def _write_row_fill_template(row: dict[str, Any], folder: Path) -> str:
    scaffold_dir = folder / "row_scaffold"
    required_map = _required_file_map(scaffold_dir)
    provenance = _first_csv_row(scaffold_dir / "provenance_template.csv")
    calibration = _first_csv_row(scaffold_dir / "calibration_template.csv")
    template_row: dict[str, str] = {
        "benchmark_id": _text(row.get("benchmark_id")),
        "target_id": _text(row.get("target_id")),
        "scope": _text(row.get("scope")),
        "split": "historical",
        "prediction_pdb": required_map.get("prediction_pdb", _text(row.get("prediction_pdb"))),
        "native_pdb": required_map.get("native_pdb", _text(row.get("native_pdb"))),
    }
    for column in PROVENANCE_COLUMNS:
        template_row[column] = _text(provenance.get(column))
    for column in ABLATION_COLUMNS:
        template_row[column] = _text(required_map.get(column, ""))
    for column in CALIBRATION_COLUMNS:
        template_row[column] = _text(calibration.get(column))
    path = folder / "row_fill_template.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FILL_COLUMNS)
        writer.writeheader()
        writer.writerow(template_row)
    return _artifact(path)


def _task_text(row: dict[str, Any], copied_row_dir: str, metadata_template: str, row_fill_template: str) -> str:
    expected_scope = "monomer" if _text(row.get("scope")) == "monomer" else "complex"
    metric_profile = _text(row.get("metric_profile"))
    lines = [
        f"# Competitive-Floor Batch Row {row.get('operator_priority')}: {row.get('benchmark_id')}",
        "",
        f"- target placeholder: `{row.get('target_id')}`",
        f"- expected scope: `{expected_scope}`",
        f"- metric profile: `{metric_profile}`",
        f"- source row folder: `{row.get('row_dir')}`",
        f"- copied row folder: `{copied_row_dir or '-'}`",
        f"- metadata template: `{metadata_template or '-'}`",
        f"- single-file fill template: `{row_fill_template or '-'}`",
        f"- missing evidence items: `{row.get('missing_evidence_item_count')}`",
        f"- next action: {row.get('next_action') or '-'}",
        "",
        "## Fill Checklist",
        "",
        "- Replace placeholder target/benchmark IDs with a cleared historical non-current CASP protein target.",
        "- Copy `row_fill_template.csv` to `row_fill.csv` and fill that one file if you want the fastest path into operator preflight.",
        "- Fill `row_metadata.csv` from the metadata template with the cleared historical benchmark ID, target ID, scope, and split.",
        "- Add the internal prediction PDB generated before native release.",
        "- Add the released historical native PDB only after no-leak provenance review.",
        "- Add all 10 layer-specific internal ablation prediction PDBs.",
        "- Fill no-leak provenance fields, including false confirmations for public/template/native use, other-team model use, post-release information use, and current CASP17 target use.",
        "- Fill selected/best top-5 rank, native metric, and internal score calibration fields.",
        "- Re-run input inventory, operator preflight/import, historical benchmark, model-selection calibration, refinement ablation, and readiness dashboard.",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    return "\n".join(lines)


def _materialize_row(row: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    priority = _int(row.get("operator_priority"))
    target_id = _text(row.get("target_id")) or "UNKNOWN"
    folder = out_dir / f"priority_{priority:03d}_{target_id}"
    copied_row_dir, copy_blocker = _copy_row_dir(_text(row.get("row_dir")), folder / "row_scaffold")
    folder.mkdir(parents=True, exist_ok=True)
    metadata_template = _write_metadata_template(row, folder)
    row_fill_template = _write_row_fill_template(row, folder)
    task_path = folder / "TASK.md"
    task_path.write_text(_task_text(row, copied_row_dir, metadata_template, row_fill_template), encoding="utf-8")
    blockers = [copy_blocker] if copy_blocker else []
    if _text(row.get("target_id")).upper().startswith("REQUIRED_"):
        blockers.append("placeholder_target_id")
    if _int(row.get("missing_evidence_item_count")):
        blockers.append("evidence_items_missing")
    return {
        "operator_priority": priority,
        "row_rank": _int(row.get("row_rank")),
        "benchmark_id": _text(row.get("benchmark_id")),
        "target_id": target_id,
        "scope": _text(row.get("scope")),
        "metric_profile": _text(row.get("metric_profile")),
        "batch_row_status": "ready_for_fill" if copied_row_dir else "blocked",
        "batch_folder": _artifact(folder),
        "copied_row_scaffold": copied_row_dir,
        "row_metadata_template_csv": metadata_template,
        "row_fill_template_csv": row_fill_template,
        "task_md": _artifact(task_path),
        "missing_evidence_item_count": _int(row.get("missing_evidence_item_count")),
        "missing_file_count": _int(row.get("missing_file_count")),
        "missing_ablation_layer_file_count": _int(row.get("missing_ablation_layer_file_count")),
        "missing_provenance_field_count": _int(row.get("missing_provenance_field_count")),
        "missing_calibration_field_count": _int(row.get("missing_calibration_field_count")),
        "missing_native_metric_gate_count": _int(row.get("missing_native_metric_gate_count")),
        "next_action": _text(row.get("next_action")),
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    fill_priority = _read_json(args.fill_priority_json)
    fill_summary = _summary(fill_priority)
    selected = _batch_rows(fill_priority)
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_materialize_row(row, out_dir) for row in selected]
    monomer_count = sum(1 for row in rows if row["scope"] == "monomer")
    complex_count = sum(1 for row in rows if row["scope"] == "complex")
    copied_count = sum(1 for row in rows if row["copied_row_scaffold"])
    row_fill_template_count = sum(1 for row in rows if row["row_fill_template_csv"])
    summary = {
        "packet_type": "casp17_competitive_floor_batch",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_status": "ready_for_fill" if selected and copied_count == len(selected) else "blocked",
        "fill_priority_json": _artifact(args.fill_priority_json),
        "fill_priority_status": _text(fill_summary.get("fill_priority_status")),
        "out_dir": _artifact(out_dir),
        "row_count": len(rows),
        "copied_row_scaffold_count": copied_count,
        "row_fill_template_count": row_fill_template_count,
        "monomer_row_count": monomer_count,
        "complex_row_count": complex_count,
        "missing_evidence_item_count": sum(_int(row.get("missing_evidence_item_count")) for row in rows),
        "missing_file_count": sum(_int(row.get("missing_file_count")) for row in rows),
        "missing_ablation_layer_file_count": sum(_int(row.get("missing_ablation_layer_file_count")) for row in rows),
        "missing_provenance_field_count": sum(_int(row.get("missing_provenance_field_count")) for row in rows),
        "missing_calibration_field_count": sum(_int(row.get("missing_calibration_field_count")) for row in rows),
        "missing_native_metric_gate_count": sum(_int(row.get("missing_native_metric_gate_count")) for row in rows),
        "first_priority_task": rows[0]["task_md"] if rows else "",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Batch",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- batch_status: `{summary['batch_status']}`",
        f"- output directory: `{summary['out_dir']}`",
        f"- rows monomer/complex/total: `{summary['monomer_row_count']}/{summary['complex_row_count']}/{summary['row_count']}`",
        f"- copied row scaffolds: `{summary['copied_row_scaffold_count']}`",
        f"- single-file fill templates: `{summary['row_fill_template_count']}`",
        f"- missing evidence/file/ablation/provenance/calibration/native-metric: `{summary['missing_evidence_item_count']}/{summary['missing_file_count']}/{summary['missing_ablation_layer_file_count']}/{summary['missing_provenance_field_count']}/{summary['missing_calibration_field_count']}/{summary['missing_native_metric_gate_count']}`",
        f"- first priority task: `{summary['first_priority_task'] or '-'}`",
        "",
        "## Rows",
        "",
        "| priority | benchmark | target | scope | status | task | missing evidence | next action |",
        "| ---: | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['batch_row_status']}` | `{row['task_md']}` | {row['missing_evidence_item_count']} | "
            f"{row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the first CASP17 competitive-floor benchmark fill batch.")
    parser.add_argument("--fill-priority-json", default=DEFAULT_FILL_PRIORITY_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["batch_status"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
