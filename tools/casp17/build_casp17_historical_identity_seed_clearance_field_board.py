#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_historical_identity_seed_clearance_field_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_identity_seed_clearance_field_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_IDENTITY_SEED_CLEARANCE_FIELD_BOARD.md"

CLEAR_VALUES = {"no_leak", "cleared", "ready_for_row_fill", "internal_no_leak", "true", "yes", "approved"}
TRUE_VALUES = {"true", "yes", "1", "y"}
FALSE_VALUES = {"false", "no", "0", "n"}
PLACEHOLDER_TOKENS = ("REQUIRED", "YYYY-MM-DD")
NO_LEAK_FIELDS = [
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
]
CALIBRATION_FIELDS = [
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
]
ABLATION_FIELDS = ["ablation_manifest_ref"]
FIELD_COLUMNS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "field_board_status",
    "core_file_status",
    "prediction_pdb_exists",
    "native_pdb_exists",
    "prediction_native_distinct",
    "prediction_atom_count",
    "native_atom_count",
    "prediction_coordinate_valid",
    "native_coordinate_valid",
    "no_leak_open_count",
    "calibration_open_count",
    "ablation_open_count",
    "total_open_field_count",
    "open_fields",
    "first_open_field",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 historical seed-clearance field board only. It audits local seed prediction/native files and "
    "operator-fill fields needed before the cleared seed manifest can be emitted. It does not clear no-leak "
    "provenance, infer chronology, fetch native structures, score native accuracy, mutate operator CSVs, mutate "
    "competitive-floor identity intake, run predictors, or submit to CASP."
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


def _norm(value: Any) -> str:
    return _text(value).lower()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _floatable(value: Any) -> bool:
    try:
        float(_text(value))
    except (TypeError, ValueError):
        return False
    return True


def _placeholder(value: Any) -> bool:
    text = _text(value)
    if not text:
        return True
    upper = text.upper()
    return any(token in upper for token in PLACEHOLDER_TOKENS)


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{_artifact(path)}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fields:
        blockers.append(f"{_artifact(path)}_header_missing")
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
        resolved = FIELD_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _path_ready(value: Any) -> bool:
    return bool(_text(value)) and _resolve(_text(value)).is_file()


def _path_or_ref_ready(value: Any) -> bool:
    text = _text(value)
    if _placeholder(text):
        return False
    if "://" in text or "#" in text:
        return True
    return _resolve(text).exists()


def _date_ready(value: Any) -> bool:
    text = _text(value)
    if _placeholder(text):
        return False
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _bool_true_ready(value: Any) -> bool:
    return _norm(value) in TRUE_VALUES


def _bool_false_ready(value: Any) -> bool:
    return _norm(value) in FALSE_VALUES


def _rank_ready(value: Any) -> bool:
    value_int = _int(value)
    return 1 <= value_int <= 5 and _text(value) == str(value_int)


def _field_ready(field: str, value: Any) -> bool:
    if field in {"no_leak_evidence_ref", "ablation_manifest_ref"}:
        return _path_or_ref_ready(value)
    if field in {"leakage_clearance", "operator_clearance"}:
        return _norm(value) in CLEAR_VALUES
    if field == "operator":
        return not _placeholder(value)
    if field in {"prediction_created_at", "native_release_date"}:
        return _date_ready(value)
    if field == "prediction_generated_before_native_release":
        return _bool_true_ready(value)
    if field in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return _bool_false_ready(value)
    if field in {"selected_model_rank", "best_model_rank"}:
        return _rank_ready(value)
    if field in {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}:
        return _floatable(value) and not _placeholder(value)
    return not _placeholder(value)


def _open_fields(row: dict[str, str], fields: list[str]) -> list[str]:
    return [field for field in fields if not _field_ready(field, row.get(field))]


def _pdb_stats(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    stats = {"exists": path.is_file(), "atom_count": 0, "coordinate_valid": False}
    if not path.is_file():
        return stats
    coordinate_valid = True
    atom_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            atom_count += 1
            try:
                float(line[30:38])
                float(line[38:46])
                float(line[46:54])
            except ValueError:
                coordinate_valid = False
    stats["atom_count"] = atom_count
    stats["coordinate_valid"] = coordinate_valid and atom_count > 0
    return stats


def _core_status(row: dict[str, str]) -> tuple[str, dict[str, Any], list[str]]:
    prediction = _pdb_stats(_text(row.get("prediction_pdb")))
    native = _pdb_stats(_text(row.get("native_pdb")))
    blockers: list[str] = []
    if not prediction["exists"]:
        blockers.append("prediction_pdb_missing")
    if not native["exists"]:
        blockers.append("native_pdb_missing")
    if prediction["exists"] and not prediction["coordinate_valid"]:
        blockers.append("prediction_coordinates_invalid")
    if native["exists"] and not native["coordinate_valid"]:
        blockers.append("native_coordinates_invalid")
    if _text(row.get("prediction_pdb")) == _text(row.get("native_pdb")):
        blockers.append("prediction_native_paths_must_differ")
    status = "pass" if not blockers else "blocked_core_files"
    return status, {"prediction": prediction, "native": native}, blockers


def _row_status(core_status: str, no_leak_open: list[str], calibration_open: list[str], ablation_open: list[str]) -> str:
    if core_status != "pass":
        return "blocked_core_files"
    if not no_leak_open and not calibration_open and not ablation_open:
        return "ready_for_cleared_seed_manifest"
    return "operator_field_fill_required"


def _next_action(status: str, first_open_field: str) -> str:
    if status == "blocked_core_files":
        return "repair missing or invalid local prediction/native PDB inputs before operator clearance"
    if status == "ready_for_cleared_seed_manifest":
        return "rerun the seed clearance workorder to emit this row into the cleared manifest"
    if first_open_field in NO_LEAK_FIELDS:
        return "fill no-leak evidence, chronology, leakage controls, and operator clearance first"
    if first_open_field in CALIBRATION_FIELDS:
        return "fill selected/best ranks, native metrics, and internal scores from verified scoring evidence"
    if first_open_field in ABLATION_FIELDS:
        return "attach the local ablation manifest reference"
    return "review this seed clearance row"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_blockers = _read_csv(args.operator_clearance_csv)
    _seed_rows, seed_blockers = _read_csv(args.seed_manifest_csv)
    rows: list[dict[str, Any]] = []
    for row in operator_rows:
        no_leak_open = _open_fields(row, NO_LEAK_FIELDS)
        calibration_open = _open_fields(row, CALIBRATION_FIELDS)
        ablation_open = _open_fields(row, ABLATION_FIELDS)
        core_status, core_stats, core_blockers = _core_status(row)
        all_open = no_leak_open + calibration_open + ablation_open + core_blockers
        status = _row_status(core_status, no_leak_open, calibration_open, ablation_open)
        first_open = all_open[0] if all_open else ""
        rows.append(
            {
                "seed_rank": _int(row.get("seed_rank")),
                "batch_slot": _int(row.get("batch_slot")),
                "benchmark_id": _text(row.get("benchmark_id")),
                "target_id": _text(row.get("target_id")),
                "scope": _text(row.get("scope")),
                "field_board_status": status,
                "core_file_status": core_status,
                "prediction_pdb_exists": bool(core_stats["prediction"]["exists"]),
                "native_pdb_exists": bool(core_stats["native"]["exists"]),
                "prediction_native_distinct": _text(row.get("prediction_pdb")) != _text(row.get("native_pdb")),
                "prediction_atom_count": _int(core_stats["prediction"]["atom_count"]),
                "native_atom_count": _int(core_stats["native"]["atom_count"]),
                "prediction_coordinate_valid": bool(core_stats["prediction"]["coordinate_valid"]),
                "native_coordinate_valid": bool(core_stats["native"]["coordinate_valid"]),
                "no_leak_open_count": len(no_leak_open),
                "calibration_open_count": len(calibration_open),
                "ablation_open_count": len(ablation_open),
                "total_open_field_count": len(all_open),
                "open_fields": ",".join(all_open),
                "first_open_field": first_open,
                "next_action": _next_action(status, first_open),
            }
        )
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["field_board_status"]] = status_counts.get(row["field_board_status"], 0) + 1
    if operator_blockers or seed_blockers:
        board_status = "blocked_missing_input"
    elif status_counts.get("ready_for_cleared_seed_manifest", 0) == len(rows) and rows:
        board_status = "ready_for_cleared_seed_manifest"
    elif status_counts.get("blocked_core_files", 0):
        board_status = "blocked_core_files"
    else:
        board_status = "operator_field_fill_required"
    first_open_row = next((row for row in rows if row["field_board_status"] != "ready_for_cleared_seed_manifest"), {})
    summary = {
        "packet_type": "casp17_historical_identity_seed_clearance_field_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "field_board_status": board_status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "seed_row_count": len(rows),
        "core_file_pass_count": sum(1 for row in rows if row["core_file_status"] == "pass"),
        "blocked_core_file_count": status_counts.get("blocked_core_files", 0),
        "operator_field_fill_required_count": status_counts.get("operator_field_fill_required", 0),
        "ready_for_cleared_seed_manifest_count": status_counts.get("ready_for_cleared_seed_manifest", 0),
        "no_leak_open_field_count": sum(_int(row["no_leak_open_count"]) for row in rows),
        "calibration_open_field_count": sum(_int(row["calibration_open_count"]) for row in rows),
        "ablation_open_field_count": sum(_int(row["ablation_open_count"]) for row in rows),
        "total_open_field_count": sum(_int(row["total_open_field_count"]) for row in rows),
        "first_open_target_id": _text(first_open_row.get("target_id")),
        "first_open_field": _text(first_open_row.get("first_open_field")),
        "first_next_action": _text(first_open_row.get("next_action")),
        "input_blockers": ",".join(operator_blockers + seed_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Identity Seed Clearance Field Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- field_board_status: `{summary['field_board_status']}`",
        f"- seed rows: `{summary['seed_row_count']}`",
        f"- core files pass/blocked: `{summary['core_file_pass_count']}/{summary['blocked_core_file_count']}`",
        f"- rows operator-fill/ready: `{summary['operator_field_fill_required_count']}/{summary['ready_for_cleared_seed_manifest_count']}`",
        f"- open fields no-leak/calibration/ablation/total: `{summary['no_leak_open_field_count']}/{summary['calibration_open_field_count']}/{summary['ablation_open_field_count']}/{summary['total_open_field_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_field'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Field Rows",
        "",
        "| slot | target | scope | status | core | atoms pred/native | open no-leak/calibration/ablation | first open | next action |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['batch_slot']} | `{row['target_id']}` | `{row['scope']}` | `{row['field_board_status']}` | "
            f"`{row['core_file_status']}` | {row['prediction_atom_count']}/{row['native_atom_count']} | "
            f"{row['no_leak_open_count']}/{row['calibration_open_count']}/{row['ablation_open_count']} | "
            f"`{row['first_open_field'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_input` | - | 0/0 | 0/0/0 | - | provide input CSVs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=FIELD_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 historical seed-clearance field board.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
