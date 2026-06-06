#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/casp17_win_tier_benchmark_operator_template_current.csv"
DEFAULT_OPERATOR_PREFLIGHT_JSON = "runs/casp17_win_tier_benchmark_operator_preflight_current.json"
DEFAULT_OUT_HISTORICAL_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_candidate_current.csv"
DEFAULT_OUT_CALIBRATION_CSV = "runs/casp17_model_selection_calibration_candidate_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_operator_import_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_operator_import_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_operator_import_packet_current.md"

CORE_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
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
    "benchmark_id",
    "scope",
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
    "leakage_clearance",
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


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["operator_template_csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    required = CORE_COLUMNS + ABLATION_COLUMNS + [column for column in CALIBRATION_COLUMNS if column not in CORE_COLUMNS]
    missing = [column for column in required if column not in fieldnames]
    blockers = [f"required_columns_missing:{','.join(missing)}"] if missing else []
    if not rows:
        blockers.append("operator_template_csv_empty")
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


def _historical_row(row: dict[str, str]) -> dict[str, str]:
    output = {column: _text(row.get(column)) for column in CORE_COLUMNS + ABLATION_COLUMNS}
    output["target_id"] = output["target_id"].upper()
    output["scope"] = output["scope"].lower()
    output["split"] = output["split"] or "historical"
    return output


def _calibration_row(row: dict[str, str]) -> dict[str, str]:
    return {column: _text(row.get(column)) for column in CALIBRATION_COLUMNS}


def _packet_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "artifact": "historical_manifest_candidate",
            "status": summary["import_status"],
            "path": summary["historical_manifest_candidate_csv"],
            "row_count": summary["historical_manifest_candidate_row_count"],
            "blockers": summary["blockers"],
        },
        {
            "artifact": "model_selection_calibration_candidate",
            "status": summary["import_status"],
            "path": summary["model_selection_calibration_candidate_csv"],
            "row_count": summary["model_selection_calibration_candidate_row_count"],
            "blockers": summary["blockers"],
        },
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    template_rows, template_blockers = _read_csv(args.operator_template_csv)
    preflight = _summary(_read_json(args.operator_preflight_json))
    preflight_status = _text(preflight.get("operator_preflight_status"))
    blockers = list(template_blockers)
    if preflight_status != "pass":
        blockers.append("operator_preflight_not_pass")
    if int(preflight.get("ready_count") or 0) < int(args.min_ready_total):
        blockers.append("ready_count_below_import_threshold")

    import_ready = bool(template_rows and not blockers)
    historical_rows = [_historical_row(row) for row in template_rows] if import_ready else []
    calibration_rows = [_calibration_row(row) for row in template_rows] if import_ready else []
    _write_csv(
        args.out_historical_manifest_csv,
        historical_rows,
        fieldnames=CORE_COLUMNS + ABLATION_COLUMNS,
    )
    _write_csv(
        args.out_calibration_csv,
        calibration_rows,
        fieldnames=CALIBRATION_COLUMNS,
    )
    summary = {
        "packet_type": "casp17_win_tier_benchmark_operator_import_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "import_status": "pass" if import_ready else "blocked",
        "operator_template_csv": _artifact(args.operator_template_csv),
        "operator_preflight_json": _artifact(args.operator_preflight_json),
        "operator_preflight_status": preflight_status or "missing",
        "operator_preflight_ready_count": int(preflight.get("ready_count") or 0),
        "operator_preflight_blocked_count": int(preflight.get("blocked_count") or 0),
        "min_ready_total": int(args.min_ready_total),
        "source_template_row_count": len(template_rows),
        "historical_manifest_candidate_csv": _artifact(args.out_historical_manifest_csv),
        "historical_manifest_candidate_row_count": len(historical_rows),
        "model_selection_calibration_candidate_csv": _artifact(args.out_calibration_csv),
        "model_selection_calibration_candidate_row_count": len(calibration_rows),
        "blockers": ",".join(sorted(set(blockers))),
        "activation_note": (
            "Candidate CSVs are written for operator review. Copy or pass them into historical benchmark and calibration "
            "tools only after the import packet is pass and the no-leak provenance review remains valid."
        ),
        "claim_boundary": (
            "Local import packet only. It materializes candidate scorer inputs from a preflight-passing operator template; "
            "it does not fetch natives, clear provenance, score accuracy, overwrite active manifests, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": _packet_rows(summary)}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Tier Benchmark Operator Import Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- import_status: `{summary['import_status']}`",
        f"- operator_preflight_status: `{summary['operator_preflight_status']}`",
        f"- preflight ready/blocked: `{summary['operator_preflight_ready_count']}/{summary['operator_preflight_blocked_count']}`",
        f"- source_template_row_count: `{summary['source_template_row_count']}`",
        f"- historical_manifest_candidate: `{summary['historical_manifest_candidate_csv']}` rows `{summary['historical_manifest_candidate_row_count']}`",
        f"- calibration_candidate: `{summary['model_selection_calibration_candidate_csv']}` rows `{summary['model_selection_calibration_candidate_row_count']}`",
        f"- blockers: `{summary['blockers'] or '-'}`",
        "",
        "## Candidate Artifacts",
        "",
        "| artifact | status | rows | path | blockers |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact']}` | `{row['status']}` | {row['row_count']} | `{row['path']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(
        [
            "",
            "## Activation Note",
            "",
            str(summary["activation_note"]),
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
    parser = argparse.ArgumentParser(description="Import a preflight-passing CASP17 win-tier benchmark operator template into candidate scorer inputs.")
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--operator-preflight-json", default=DEFAULT_OPERATOR_PREFLIGHT_JSON)
    parser.add_argument("--min-ready-total", type=int, default=40)
    parser.add_argument("--out-historical-manifest-csv", default=DEFAULT_OUT_HISTORICAL_MANIFEST_CSV)
    parser.add_argument("--out-calibration-csv", default=DEFAULT_OUT_CALIBRATION_CSV)
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
    if payload["summary"]["import_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
