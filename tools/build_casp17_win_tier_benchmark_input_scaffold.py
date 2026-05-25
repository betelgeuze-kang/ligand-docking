#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/casp17_win_tier_benchmark_operator_template_current.csv"
DEFAULT_OPERATOR_DASHBOARD_JSON = "runs/casp17_win_tier_benchmark_operator_dashboard_current.json"
DEFAULT_EVIDENCE_FILL_KIT_CSV = "runs/casp17_win_tier_benchmark_evidence_fill_kit_current.csv"
DEFAULT_OUT_DIR = "runs/casp17_win_tier_benchmark_input_scaffold_current"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_input_scaffold_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_input_scaffold_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_input_scaffold_current.md"
DEFAULT_OUT_MANIFEST_DRAFT_CSV = "runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv"
DEFAULT_OUT_CALIBRATION_DRAFT_CSV = "runs/casp17_model_selection_calibration_draft_from_operator_current.csv"

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

CALIBRATION_COLUMNS = [
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
]

MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    *PROVENANCE_COLUMNS,
    *[f"{layer}_prediction_pdb" for layer in ABLATION_LAYER_NAMES],
]

CALIBRATION_DRAFT_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "leakage_clearance",
    *CALIBRATION_COLUMNS,
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


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "row"


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, fieldnames, blockers


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


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
        fieldnames = ["row_rank", "benchmark_id", "target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _rows_by_rank(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        rank = _int(row.get("row_rank"))
        if rank:
            result[rank] = row
    return result


def _fill_counts_by_rank(rows: list[dict[str, str]]) -> dict[int, dict[str, int]]:
    result: dict[int, dict[str, int]] = {}
    for row in rows:
        rank = _int(row.get("row_rank"))
        if not rank:
            continue
        counts = result.setdefault(rank, {"missing": 0, "native_metric_gate": 0})
        if _text(row.get("completion_status")) != "filled":
            counts["missing"] += 1
        if _text(row.get("evidence_class")) == "native_metric_gate":
            counts["native_metric_gate"] += 1
    return result


def _metric_profile(scope: str) -> str:
    if scope == "complex":
        return "TM,interface_F1,DockQ,QSbest,IPS"
    return "TM,GDT_TS,CA_lDDT"


def _expected_files(template_row: dict[str, str]) -> list[dict[str, str]]:
    files = [
        {
            "file_role": "prediction_pdb",
            "template_column": "prediction_pdb",
            "expected_path": _text(template_row.get("prediction_pdb")),
        },
        {
            "file_role": "native_pdb",
            "template_column": "native_pdb",
            "expected_path": _text(template_row.get("native_pdb")),
        },
    ]
    for layer in ABLATION_LAYER_NAMES:
        column = f"{layer}_prediction_pdb"
        files.append(
            {
                "file_role": f"ablation_{layer}_prediction_pdb",
                "template_column": column,
                "expected_path": _text(template_row.get(column)),
            }
        )
    return files


def _write_row_readme(row_dir: Path, row: dict[str, Any], expected_files: list[dict[str, str]]) -> str:
    row_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# CASP17 Win-Tier Historical Benchmark Slot {row['row_rank']}",
        "",
        f"- benchmark_id: `{row['benchmark_id']}`",
        f"- target_id: `{row['target_id']}`",
        f"- scope: `{row['scope']}`",
        f"- metric_profile: `{row['metric_profile']}`",
        f"- current_status: `{row['operator_row_status']}`",
        f"- missing_evidence_items: `{row['missing_evidence_item_count']}`",
        "",
        "## Stop Conditions",
        "",
        "- Do not use a current CASP17 target native structure.",
        "- Do not use public/template/native structures to create the prediction.",
        "- Do not use other-team models.",
        "- Do not use post-native-release information for prediction or model selection.",
        "- Keep this slot blocked until the prediction date is before the native release date.",
        "",
        "## Required Files",
        "",
        "| role | template column | expected path |",
        "| --- | --- | --- |",
    ]
    for item in expected_files:
        lines.append(
            f"| `{item['file_role']}` | `{item['template_column']}` | `{item['expected_path'] or '-'}` |"
        )
    lines.extend(
        [
            "",
            "## Required Provenance Fields",
            "",
            "| field | required value |",
            "| --- | --- |",
            "| `leakage_clearance` | `no_leak` or equivalent cleared value |",
            "| `prediction_method` | internal method identifier |",
            "| `prediction_created_at` | ISO date before native release |",
            "| `native_release_date` | ISO date after prediction creation |",
            "| `prediction_generated_before_native_release` | `true` |",
            "| `public_template_or_native_used_for_prediction` | `false` |",
            "| `other_team_model_used` | `false` |",
            "| `post_release_information_used` | `false` |",
            "| `current_casp17_target` | `false` |",
            "| `operator_clearance` | `no_leak` or equivalent cleared value |",
            "",
            "## After Filling This Slot",
            "",
            "1. Update the operator template row with the real target ID, benchmark ID, file paths, provenance, and calibration values.",
            "2. Run operator preflight/import so only ready no-leak rows are promoted.",
            "3. Run historical benchmark, refinement-ablation, sidechain-native, and model-selection calibration packets.",
            "",
            "This scaffold is local bookkeeping only. It does not fetch natives, score accuracy, use external predictors, or submit to CASP.",
            "",
        ]
    )
    path = row_dir / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(path)


def _write_row_csvs(row_dir: Path, template_row: dict[str, str]) -> tuple[str, str, str]:
    file_rows = _expected_files(template_row)
    files_csv = row_dir / "required_files.csv"
    _write_csv(files_csv, file_rows, fieldnames=["file_role", "template_column", "expected_path"])

    provenance_csv = row_dir / "provenance_template.csv"
    _write_csv(
        provenance_csv,
        [{column: _text(template_row.get(column)) for column in PROVENANCE_COLUMNS}],
        fieldnames=PROVENANCE_COLUMNS,
    )

    calibration_csv = row_dir / "calibration_template.csv"
    _write_csv(
        calibration_csv,
        [{column: _text(template_row.get(column)) for column in CALIBRATION_COLUMNS}],
        fieldnames=CALIBRATION_COLUMNS,
    )
    return _artifact(files_csv), _artifact(provenance_csv), _artifact(calibration_csv)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win-Tier Benchmark Input Scaffold",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- scaffold_status: `{summary['scaffold_status']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- ready/blocked rows: `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- required files: prediction/native/ablation `{summary['required_prediction_file_count']}/{summary['required_native_file_count']}/{summary['required_ablation_file_count']}`",
        f"- missing evidence items: `{summary['missing_evidence_item_count']}/{summary['evidence_item_count']}`",
        f"- native metric gate items: `{summary['native_metric_gate_count']}`",
        f"- manifest draft: `{summary['manifest_draft_csv']}`",
        f"- calibration draft: `{summary['calibration_draft_csv']}`",
        "",
        "## Rows",
        "",
        "| rank | benchmark | target | scope | metrics | files | missing evidence | row folder |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['metric_profile']}` | {row['required_file_count']} | {row['missing_evidence_item_count']} | "
            f"`{row['row_dir']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    template_rows, template_fields, template_blockers = _read_csv(args.operator_template_csv)
    fill_rows, _fill_fields, fill_blockers = _read_csv(args.evidence_fill_kit_csv)
    dashboard_payload = _read_json(args.operator_dashboard_json)
    dashboard_rows = _json_rows(dashboard_payload)
    dashboard_by_rank = _rows_by_rank(dashboard_rows)
    fill_counts = _fill_counts_by_rank(fill_rows)

    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []

    for index, template_row in enumerate(template_rows, start=1):
        dashboard_row = dashboard_by_rank.get(index, {})
        scope = _text(template_row.get("scope") or dashboard_row.get("scope")).lower() or "monomer"
        target_id = _text(template_row.get("target_id") or dashboard_row.get("target_id")).upper()
        benchmark_id = _text(template_row.get("benchmark_id") or dashboard_row.get("benchmark_id"))
        metric_profile = _text(dashboard_row.get("metric_profile") or dashboard_row.get("required_metric_profile")) or _metric_profile(scope)
        row_dir = out_dir / f"row_{index:03d}_{_slug(target_id)}"
        expected_files = _expected_files(template_row)
        files_csv, provenance_csv, calibration_csv = _write_row_csvs(row_dir, template_row)
        row_readme = _write_row_readme(
            row_dir,
            {
                "row_rank": index,
                "benchmark_id": benchmark_id,
                "target_id": target_id,
                "scope": scope,
                "metric_profile": metric_profile,
                "operator_row_status": _text(dashboard_row.get("operator_row_status")) or "blocked",
                "missing_evidence_item_count": fill_counts.get(index, {}).get("missing", 0),
            },
            expected_files,
        )
        required_ablation_file_count = len(ABLATION_LAYER_NAMES)
        row = {
            "row_rank": index,
            "benchmark_id": benchmark_id,
            "target_id": target_id,
            "scope": scope,
            "split": _text(template_row.get("split")) or "historical",
            "metric_profile": metric_profile,
            "operator_row_status": _text(dashboard_row.get("operator_row_status")) or "blocked",
            "row_dir": _artifact(row_dir),
            "row_readme": row_readme,
            "required_files_csv": files_csv,
            "provenance_template_csv": provenance_csv,
            "calibration_template_csv": calibration_csv,
            "prediction_pdb": _text(template_row.get("prediction_pdb")),
            "native_pdb": _text(template_row.get("native_pdb")),
            "required_prediction_file_count": 1,
            "required_native_file_count": 1,
            "required_ablation_file_count": required_ablation_file_count,
            "required_file_count": 2 + required_ablation_file_count,
            "missing_evidence_item_count": fill_counts.get(index, {}).get("missing", 0),
            "native_metric_gate_count": fill_counts.get(index, {}).get("native_metric_gate", 0),
            "needs_target_replacement": _boolish(dashboard_row.get("needs_target_replacement")),
            "needs_core_files": _boolish(dashboard_row.get("needs_core_files")),
            "needs_ablation_layers": _boolish(dashboard_row.get("needs_ablation_layers")),
            "needs_calibration": _boolish(dashboard_row.get("needs_calibration")),
            "needs_provenance": _boolish(dashboard_row.get("needs_provenance")),
            "next_action": _text(dashboard_row.get("next_action")),
            "blockers": _text(dashboard_row.get("blockers")),
        }
        rows.append(row)
        manifest_rows.append({column: _text(template_row.get(column)) for column in MANIFEST_COLUMNS})
        calibration_rows.append({column: _text(template_row.get(column)) for column in CALIBRATION_DRAFT_COLUMNS})

    _write_csv(args.out_manifest_draft_csv, manifest_rows, fieldnames=MANIFEST_COLUMNS)
    _write_csv(args.out_calibration_draft_csv, calibration_rows, fieldnames=CALIBRATION_DRAFT_COLUMNS)

    ready_count = sum(1 for row in rows if row["operator_row_status"] == "ready")
    missing_evidence_item_count = sum(int(row["missing_evidence_item_count"]) for row in rows)
    native_metric_gate_count = sum(int(row["native_metric_gate_count"]) for row in rows)
    evidence_item_count = len(fill_rows)
    source_blockers = sorted(set(template_blockers + fill_blockers))
    summary = {
        "packet_type": "casp17_win_tier_benchmark_input_scaffold",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scaffold_status": "ready" if rows and not source_blockers else "blocked",
        "operator_template_csv": _artifact(args.operator_template_csv),
        "operator_dashboard_json": _artifact(args.operator_dashboard_json),
        "evidence_fill_kit_csv": _artifact(args.evidence_fill_kit_csv),
        "out_dir": _artifact(args.out_dir),
        "manifest_draft_csv": _artifact(args.out_manifest_draft_csv),
        "calibration_draft_csv": _artifact(args.out_calibration_draft_csv),
        "row_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": len(rows) - ready_count,
        "monomer_row_count": sum(1 for row in rows if row["scope"] == "monomer"),
        "complex_row_count": sum(1 for row in rows if row["scope"] == "complex"),
        "required_prediction_file_count": sum(int(row["required_prediction_file_count"]) for row in rows),
        "required_native_file_count": sum(int(row["required_native_file_count"]) for row in rows),
        "required_ablation_file_count": sum(int(row["required_ablation_file_count"]) for row in rows),
        "required_total_file_count": sum(int(row["required_file_count"]) for row in rows),
        "evidence_item_count": evidence_item_count,
        "missing_evidence_item_count": missing_evidence_item_count,
        "native_metric_gate_count": native_metric_gate_count,
        "source_blockers": ",".join(source_blockers),
        "claim_boundary": (
            "Local input scaffold only. It creates row folders and draft CSVs for no-leak historical benchmark "
            "intake; it does not fetch native structures, fill provenance, score accuracy, use external predictors, "
            "or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build row-level input scaffolds for CASP17 win-tier historical benchmarks.")
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--operator-dashboard-json", default=DEFAULT_OPERATOR_DASHBOARD_JSON)
    parser.add_argument("--evidence-fill-kit-csv", default=DEFAULT_EVIDENCE_FILL_KIT_CSV)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-manifest-draft-csv", default=DEFAULT_OUT_MANIFEST_DRAFT_CSV)
    parser.add_argument("--out-calibration-draft-csv", default=DEFAULT_OUT_CALIBRATION_DRAFT_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
