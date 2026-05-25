#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_IMPORT_JSON = "runs/casp17_win_tier_benchmark_operator_import_packet_current.json"
DEFAULT_HISTORICAL_CANDIDATE_CSV = "runs/casp17_historical_benchmark_manifest_candidate_current.csv"
DEFAULT_CALIBRATION_CANDIDATE_CSV = "runs/casp17_model_selection_calibration_candidate_current.csv"
DEFAULT_TARGET_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_OUT_HISTORICAL_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_current.csv"
DEFAULT_OUT_CALIBRATION_CSV = "runs/casp17_model_selection_calibration_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_activation_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_activation_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_activation_packet_current.md"

LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
HISTORICAL_REQUIRED_COLUMNS = [
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
CALIBRATION_REQUIRED_COLUMNS = [
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


def _read_csv(path_like: str | Path, required_columns: list[str]) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        blockers.append(f"required_columns_missing:{','.join(missing)}")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, fieldnames, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_packet_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    _write_csv(path_like, rows, fieldnames or ["artifact", "status"])


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or text.upper().startswith("REQUIRED_") or "YYYY-MM-DD" in text.upper()


def _date_value(value: Any) -> dt.date | None:
    text = _text(value)
    if _is_placeholder(text):
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _numeric(value: Any) -> bool:
    try:
        float(_text(value))
    except ValueError:
        return False
    return True


def _rank(value: Any) -> bool:
    try:
        parsed = int(_text(value))
    except ValueError:
        return False
    return 1 <= parsed <= 5


def _current_targets(path_like: str | Path) -> set[str]:
    rows = _read_json(path_like).get("rows")
    if not isinstance(rows, list):
        return set()
    return {
        _text(row.get("target_id")).upper()
        for row in rows
        if isinstance(row, dict) and _text(row.get("target_id")) and row.get("human_open") is True
    }


def _pdb_ok(path_like: str) -> tuple[bool, str]:
    path = _resolve(path_like)
    if _is_placeholder(path_like):
        return False, "pdb_path_placeholder"
    if not path.exists():
        return False, "pdb_missing"
    if path.stat().st_size <= 0:
        return False, "pdb_empty"
    atom_count = 0
    ca_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(("ATOM", "HETATM")):
                atom_count += 1
                ca_count += int(line[12:16].strip() == "CA")
    if atom_count <= 0:
        return False, "pdb_atom_records_missing"
    if ca_count <= 0:
        return False, "pdb_ca_records_missing"
    return True, ""


def _validate_historical_row(row: dict[str, str], current_targets: set[str]) -> tuple[dict[str, str], list[str]]:
    out = {column: _text(row.get(column)) for column in HISTORICAL_REQUIRED_COLUMNS + ABLATION_COLUMNS}
    out["target_id"] = out["target_id"].upper()
    out["scope"] = out["scope"].lower()
    out["split"] = out["split"] or "historical"
    blockers: list[str] = []
    if _is_placeholder(out["benchmark_id"]):
        blockers.append("benchmark_id_missing_or_placeholder")
    if _is_placeholder(out["target_id"]):
        blockers.append("target_id_missing_or_placeholder")
    if out["target_id"] in current_targets:
        blockers.append("current_casp17_target_not_allowed")
    if out["scope"] not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    if out["leakage_clearance"].lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_not_clear")
    if out["operator_clearance"].lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("operator_clearance_not_clear")
    if _is_placeholder(out["prediction_method"]):
        blockers.append("prediction_method_missing")
    pred_date = _date_value(out["prediction_created_at"])
    native_date = _date_value(out["native_release_date"])
    if pred_date is None:
        blockers.append("prediction_created_at_invalid")
    if native_date is None:
        blockers.append("native_release_date_invalid")
    if pred_date is not None and native_date is not None and pred_date >= native_date:
        blockers.append("prediction_date_not_before_native_release")
    if out["prediction_generated_before_native_release"].lower() not in TRUE_VALUES:
        blockers.append("prediction_before_native_release_not_confirmed")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if out[column].lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    for column in ["prediction_pdb", "native_pdb", *ABLATION_COLUMNS]:
        ok, blocker = _pdb_ok(out[column])
        if not ok:
            blockers.append(f"{column}:{blocker}")
        else:
            out[column] = _artifact(out[column])
    return out, blockers


def _validate_calibration_row(row: dict[str, str], allowed_benchmark_ids: set[str]) -> tuple[dict[str, str], list[str]]:
    out = {column: _text(row.get(column)) for column in CALIBRATION_REQUIRED_COLUMNS}
    out["scope"] = out["scope"].lower()
    blockers: list[str] = []
    if out["benchmark_id"] not in allowed_benchmark_ids:
        blockers.append("benchmark_id_not_in_historical_manifest")
    if out["scope"] not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    if out["leakage_clearance"].lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_not_clear")
    for column in ["selected_model_rank", "best_model_rank"]:
        if not _rank(out[column]):
            blockers.append(f"{column}_invalid")
    for column in ["selected_native_metric", "best_native_metric", "selected_score", "best_score"]:
        if not _numeric(out[column]):
            blockers.append(f"{column}_not_numeric")
    return out, blockers


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    import_summary = _summary(_read_json(args.operator_import_json))
    historical_rows, historical_fields, historical_blockers = _read_csv(
        args.historical_manifest_candidate_csv,
        HISTORICAL_REQUIRED_COLUMNS + ABLATION_COLUMNS,
    )
    calibration_rows, calibration_fields, calibration_blockers = _read_csv(
        args.calibration_candidate_csv,
        CALIBRATION_REQUIRED_COLUMNS,
    )
    blockers = list(historical_blockers) + list(calibration_blockers)
    if import_summary.get("import_status") != "pass":
        blockers.append("operator_import_not_pass")
    current_targets = _current_targets(args.target_watchlist_json)

    validated_historical: list[dict[str, str]] = []
    historical_row_blockers: list[dict[str, Any]] = []
    for row in historical_rows:
        validated, row_blockers = _validate_historical_row(row, current_targets)
        if row_blockers:
            historical_row_blockers.append(
                {"benchmark_id": validated.get("benchmark_id", ""), "target_id": validated.get("target_id", ""), "blockers": ",".join(row_blockers)}
            )
        else:
            validated_historical.append(validated)

    allowed_benchmark_ids = {row["benchmark_id"] for row in validated_historical}
    validated_calibration: list[dict[str, str]] = []
    calibration_row_blockers: list[dict[str, Any]] = []
    for row in calibration_rows:
        validated, row_blockers = _validate_calibration_row(row, allowed_benchmark_ids)
        if row_blockers:
            calibration_row_blockers.append({"benchmark_id": validated.get("benchmark_id", ""), "blockers": ",".join(row_blockers)})
        else:
            validated_calibration.append(validated)

    if historical_row_blockers:
        blockers.append("historical_candidate_rows_blocked")
    if calibration_row_blockers:
        blockers.append("calibration_candidate_rows_blocked")
    if len(validated_historical) < int(args.min_ready_total):
        blockers.append("validated_historical_rows_below_threshold")
    if len(validated_calibration) < int(args.min_ready_total):
        blockers.append("validated_calibration_rows_below_threshold")

    activation_status = "pass" if not blockers else "blocked"
    if activation_status == "pass":
        _write_csv(
            args.out_historical_manifest_csv,
            validated_historical,
            HISTORICAL_REQUIRED_COLUMNS + ABLATION_COLUMNS,
        )
        _write_csv(args.out_calibration_csv, validated_calibration, CALIBRATION_REQUIRED_COLUMNS)

    summary = {
        "packet_type": "casp17_win_tier_benchmark_activation_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "activation_status": activation_status,
        "operator_import_json": _artifact(args.operator_import_json),
        "operator_import_status": import_summary.get("import_status", "missing"),
        "historical_manifest_candidate_csv": _artifact(args.historical_manifest_candidate_csv),
        "calibration_candidate_csv": _artifact(args.calibration_candidate_csv),
        "historical_candidate_row_count": len(historical_rows),
        "calibration_candidate_row_count": len(calibration_rows),
        "validated_historical_row_count": len(validated_historical),
        "validated_calibration_row_count": len(validated_calibration),
        "historical_row_blocked_count": len(historical_row_blockers),
        "calibration_row_blocked_count": len(calibration_row_blockers),
        "min_ready_total": int(args.min_ready_total),
        "active_historical_manifest_csv": _artifact(args.out_historical_manifest_csv),
        "active_calibration_csv": _artifact(args.out_calibration_csv),
        "active_files_written": activation_status == "pass",
        "blockers": ",".join(sorted(set(blockers))),
        "claim_boundary": (
            "Local activation packet only. It activates preflight/import-passing no-leak historical benchmark inputs "
            "for internal scoring; it does not fetch native structures, use current CASP17 natives, use external predictors, "
            "or prove current-target accuracy."
        ),
    }
    rows = [
        {
            "artifact": "historical_manifest_current",
            "status": activation_status,
            "candidate_rows": len(historical_rows),
            "validated_rows": len(validated_historical),
            "blocked_rows": len(historical_row_blockers),
            "path": summary["active_historical_manifest_csv"],
            "blockers": summary["blockers"],
        },
        {
            "artifact": "model_selection_calibration_current",
            "status": activation_status,
            "candidate_rows": len(calibration_rows),
            "validated_rows": len(validated_calibration),
            "blocked_rows": len(calibration_row_blockers),
            "path": summary["active_calibration_csv"],
            "blockers": summary["blockers"],
        },
    ]
    return {"summary": summary, "rows": rows, "historical_row_blockers": historical_row_blockers, "calibration_row_blockers": calibration_row_blockers}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Tier Benchmark Activation Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- activation_status: `{summary['activation_status']}`",
        f"- operator_import_status: `{summary['operator_import_status']}`",
        f"- historical validated/candidate: `{summary['validated_historical_row_count']}/{summary['historical_candidate_row_count']}`",
        f"- calibration validated/candidate: `{summary['validated_calibration_row_count']}/{summary['calibration_candidate_row_count']}`",
        f"- active_files_written: `{summary['active_files_written']}`",
        f"- blockers: `{summary['blockers'] or '-'}`",
        "",
        "## Active Artifacts",
        "",
        "| artifact | status | validated | blocked | path |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['artifact']}` | `{row['status']}` | {row['validated_rows']} | {row['blocked_rows']} | `{row['path']}` |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Activate preflight-passing CASP17 no-leak benchmark candidate CSVs for internal scoring.")
    parser.add_argument("--operator-import-json", default=DEFAULT_OPERATOR_IMPORT_JSON)
    parser.add_argument("--historical-manifest-candidate-csv", default=DEFAULT_HISTORICAL_CANDIDATE_CSV)
    parser.add_argument("--calibration-candidate-csv", default=DEFAULT_CALIBRATION_CANDIDATE_CSV)
    parser.add_argument("--target-watchlist-json", default=DEFAULT_TARGET_WATCHLIST_JSON)
    parser.add_argument("--min-ready-total", type=int, default=1)
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
    _write_packet_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["activation_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
