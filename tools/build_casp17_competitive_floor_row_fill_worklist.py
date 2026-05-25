#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BATCH_JSON = "casp17/casp17_competitive_floor_batch_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_row_fill_worklist_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_row_fill_worklist_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_ROW_FILL_WORKLIST.md"

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
BASE_COLUMNS = ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb"]
REQUIRED_COLUMNS = BASE_COLUMNS + PROVENANCE_COLUMNS + ABLATION_COLUMNS + CALIBRATION_COLUMNS

CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
CLASS_ORDER = {
    "target_identity": 10,
    "core_file": 20,
    "provenance": 30,
    "ablation_file": 40,
    "calibration": 50,
    "row_file": 60,
}
CLAIM_BOUNDARY = (
    "Local competitive-floor row-fill worklist only. It turns row_fill.csv placeholders and local-file blockers "
    "into operator actions; it does not choose historical targets, fetch native structures, clear provenance, "
    "score native accuracy, use external predictors, or submit to CASP."
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
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        blockers.append("required_columns_missing:" + ",".join(missing))
    return rows, blockers


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
        fieldnames = ["operator_priority", "row_rank", "evidence_class", "template_column"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
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


def _column_class(column: str) -> str:
    if column in {"benchmark_id", "target_id", "scope", "split"}:
        return "target_identity"
    if column in {"prediction_pdb", "native_pdb"}:
        return "core_file"
    if column in ABLATION_COLUMNS:
        return "ablation_file"
    if column in PROVENANCE_COLUMNS:
        return "provenance"
    if column in CALIBRATION_COLUMNS:
        return "calibration"
    return "row_file"


def _expected_value(column: str, scope: str) -> str:
    if column == "benchmark_id":
        return "stable hist_* ID for a cleared historical benchmark row"
    if column == "target_id":
        return "cleared historical non-CASP17 target ID"
    if column == "scope":
        return "monomer or complex"
    if column == "split":
        return "historical"
    if column == "prediction_pdb":
        return "local internally generated prediction PDB made before native release"
    if column == "native_pdb":
        return "local released historical native PDB after no-leak review"
    if column in ABLATION_COLUMNS:
        layer = column.removesuffix("_prediction_pdb")
        return f"local {layer} ablation prediction PDB for the same historical target"
    if column in {"leakage_clearance", "operator_clearance"}:
        return "no_leak / cleared / internal_no_leak"
    if column == "prediction_method":
        return "internal method identifier"
    if column in {"prediction_created_at", "native_release_date"}:
        return "YYYY-MM-DD"
    if column == "prediction_generated_before_native_release":
        return "true"
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return "false"
    if column in {"selected_model_rank", "best_model_rank"}:
        return "integer 1..5"
    if column in {"selected_native_metric", "best_native_metric"}:
        return "numeric native metric for selected/oracle model"
    if column in {"selected_score", "best_score"}:
        return "numeric internal score for selected/oracle model"
    return f"required {scope} value"


def _destination_hint(column: str, target_id: str) -> str:
    target = target_id if target_id and not target_id.upper().startswith("REQUIRED_") else "<HISTORICAL_TARGET_ID>"
    if column == "prediction_pdb":
        return f"runs/casp17_historical_benchmark_predictions_current/{target}_prediction.pdb"
    if column == "native_pdb":
        return f"runs/casp17_historical_benchmark_natives_current/{target}_native.pdb"
    if column in ABLATION_COLUMNS:
        layer = column.removesuffix("_prediction_pdb")
        return f"runs/casp17_historical_ablation_predictions_current/{layer}/{target}TS.pdb"
    return ""


def _blocker_for(column: str, value: Any, row: dict[str, str]) -> str:
    text = _text(value)
    lower = text.lower()
    if column in {"benchmark_id", "target_id"}:
        return f"{column}_placeholder" if _contains_placeholder(text) else ""
    if column == "scope":
        return "" if lower in {"monomer", "complex"} else "scope_required"
    if column == "split":
        return "" if lower == "historical" else "split_must_be_historical"
    if column in {"prediction_pdb", "native_pdb"} | set(ABLATION_COLUMNS):
        if _contains_placeholder(text):
            return f"{column}_placeholder"
        if not _resolve(text).is_file():
            return f"{column}_file_not_found"
        return ""
    if column in {"leakage_clearance", "operator_clearance"}:
        return "" if lower in CLEAR_VALUES else f"{column}_requires_no_leak_clearance"
    if column == "prediction_method":
        return "" if not _contains_placeholder(text) else "prediction_method_required"
    if column in {"prediction_created_at", "native_release_date"}:
        return "" if _date_or_none(text) else f"{column}_requires_iso_date"
    if column == "prediction_generated_before_native_release":
        return "" if lower in TRUE_VALUES else "prediction_before_native_release_confirmation_required"
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return "" if lower in FALSE_VALUES else f"{column}_must_be_false"
    if column in {"selected_model_rank", "best_model_rank"}:
        return "" if _rank_ok(text) else f"{column}_requires_rank_1_to_5"
    if column in {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}:
        return "" if _float_or_none(text) is not None else f"{column}_requires_numeric"
    return "" if not _contains_placeholder(text) else f"{column}_required"


def _recommended_action(column: str, blocker: str, target_id: str) -> str:
    if not blocker:
        return ""
    if column == "benchmark_id":
        return "replace with a stable hist_* ID for the chosen cleared historical target"
    if column == "target_id":
        return "replace placeholder with a cleared historical non-current CASP target ID"
    if column in {"prediction_pdb", "native_pdb"} | set(ABLATION_COLUMNS):
        hint = _destination_hint(column, target_id)
        return f"place a validated local PDB at {hint} and update row_fill.csv"
    if column in {"leakage_clearance", "operator_clearance"}:
        return "record no_leak/cleared only after no-leak provenance review"
    if column == "prediction_method":
        return "record the internal prediction method used before native release"
    if column in {"prediction_created_at", "native_release_date"}:
        return "replace with an ISO date and ensure prediction_created_at is before native_release_date"
    if column == "prediction_generated_before_native_release":
        return "set to true only when the date/provenance evidence supports it"
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return "set to false only after the no-leak review supports that confirmation"
    if column in {"selected_model_rank", "best_model_rank"}:
        return "fill with a model rank from 1 to 5"
    if column in {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}:
        return "fill with a numeric calibration value from the historical scoring packet"
    return "fill this required field in row_fill.csv"


def _date_order_action(row: dict[str, str]) -> dict[str, str] | None:
    prediction_date = _date_or_none(row.get("prediction_created_at"))
    native_date = _date_or_none(row.get("native_release_date"))
    if not prediction_date or not native_date or prediction_date < native_date:
        return None
    return {
        "template_column": "prediction_created_at,native_release_date",
        "current_value": f"{row.get('prediction_created_at', '')},{row.get('native_release_date', '')}",
        "expected_value": "prediction_created_at before native_release_date",
        "blocker": "prediction_date_not_before_native_release",
        "recommended_action": "choose a historical row whose internal prediction predates native release, or correct the dates",
        "local_destination_hint": "",
        "evidence_class": "provenance",
    }


def _action_rows_for_batch_row(batch_row: dict[str, Any], action_start: int) -> tuple[list[dict[str, Any]], str]:
    batch_folder = _resolve(batch_row.get("batch_folder", ""))
    row_fill = batch_folder / "row_fill.csv"
    guide_md = batch_folder / "FIELD_GUIDE.md"
    source_rows, csv_blockers = _read_csv(row_fill)
    row = source_rows[0] if source_rows else {}
    target_id = _text(row.get("target_id")) or _text(batch_row.get("target_id"))
    scope = (_text(row.get("scope")) or _text(batch_row.get("scope"))).lower()
    benchmark_id = _text(row.get("benchmark_id")) or _text(batch_row.get("benchmark_id"))
    actions: list[dict[str, Any]] = []
    if csv_blockers:
        actions.append(
            {
                "action_rank": action_start,
                "operator_priority": int(batch_row.get("operator_priority") or 0),
                "row_rank": int(batch_row.get("row_rank") or 0),
                "benchmark_id": benchmark_id,
                "target_id": target_id,
                "scope": scope,
                "row_fill_csv": _artifact(row_fill),
                "field_guide_md": _artifact(guide_md),
                "evidence_class": "row_file",
                "template_column": "row_fill.csv",
                "current_value": "",
                "expected_value": "row_fill.csv with required columns and one filled row",
                "blocker": ",".join(csv_blockers),
                "recommended_action": "create row_fill.csv from row_fill_template.csv and keep the required header",
                "local_destination_hint": _artifact(row_fill),
            }
        )
        return actions, _artifact(guide_md)

    action_rank = action_start
    for column in REQUIRED_COLUMNS:
        blocker = _blocker_for(column, row.get(column), row)
        if not blocker:
            continue
        actions.append(
            {
                "action_rank": action_rank,
                "operator_priority": int(batch_row.get("operator_priority") or 0),
                "row_rank": int(batch_row.get("row_rank") or 0),
                "benchmark_id": benchmark_id,
                "target_id": target_id,
                "scope": scope,
                "row_fill_csv": _artifact(row_fill),
                "field_guide_md": _artifact(guide_md),
                "evidence_class": _column_class(column),
                "template_column": column,
                "current_value": _text(row.get(column)),
                "expected_value": _expected_value(column, scope),
                "blocker": blocker,
                "recommended_action": _recommended_action(column, blocker, target_id),
                "local_destination_hint": _destination_hint(column, target_id),
            }
        )
        action_rank += 1
    date_action = _date_order_action(row)
    if date_action:
        actions.append(
            {
                "action_rank": action_rank,
                "operator_priority": int(batch_row.get("operator_priority") or 0),
                "row_rank": int(batch_row.get("row_rank") or 0),
                "benchmark_id": benchmark_id,
                "target_id": target_id,
                "scope": scope,
                "row_fill_csv": _artifact(row_fill),
                "field_guide_md": _artifact(guide_md),
                **date_action,
            }
        )
    actions.sort(key=lambda item: (CLASS_ORDER.get(str(item["evidence_class"]), 99), int(item["action_rank"])))
    for index, action in enumerate(actions, start=action_start):
        action["action_rank"] = index
    return actions, _artifact(guide_md)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    batch_payload = _read_json(args.batch_json)
    all_actions: list[dict[str, Any]] = []
    guide_paths: list[str] = []
    next_rank = 1
    for batch_row in _rows(batch_payload):
        actions, guide_path = _action_rows_for_batch_row(batch_row, next_rank)
        guide_paths.append(guide_path)
        all_actions.extend(actions)
        next_rank += len(actions)
    by_class = defaultdict(int)
    for action in all_actions:
        by_class[str(action["evidence_class"])] += 1
    first_action = all_actions[0] if all_actions else {}
    summary = {
        "packet_type": "casp17_competitive_floor_row_fill_worklist",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "worklist_status": "ready" if not all_actions else "open_actions",
        "batch_json": _artifact(args.batch_json),
        "row_count": len(_rows(batch_payload)),
        "guide_md_count": len(guide_paths),
        "open_action_count": len(all_actions),
        "target_identity_action_count": by_class["target_identity"],
        "core_file_action_count": by_class["core_file"],
        "provenance_action_count": by_class["provenance"],
        "ablation_file_action_count": by_class["ablation_file"],
        "calibration_action_count": by_class["calibration"],
        "row_file_action_count": by_class["row_file"],
        "first_action_row_fill_csv": _text(first_action.get("row_fill_csv")),
        "first_action_column": _text(first_action.get("template_column")),
        "first_action_blocker": _text(first_action.get("blocker")),
        "first_action_recommended_action": _text(first_action.get("recommended_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": all_actions, "guide_paths": guide_paths}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Row Fill Worklist",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- worklist_status: `{summary['worklist_status']}`",
        f"- row guides: `{summary['guide_md_count']}/{summary['row_count']}`",
        f"- open actions: `{summary['open_action_count']}`",
        f"- identity/core/provenance/ablation/calibration actions: `{summary['target_identity_action_count']}/{summary['core_file_action_count']}/{summary['provenance_action_count']}/{summary['ablation_file_action_count']}/{summary['calibration_action_count']}`",
        f"- first action column: `{summary['first_action_column'] or '-'}`",
        f"- first action blocker: `{summary['first_action_blocker'] or '-'}`",
        f"- first action: {summary['first_action_recommended_action'] or '-'}",
        "",
        "## Actions",
        "",
        "| rank | priority | benchmark | target | class | column | blocker | action |",
        "| ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | {row['operator_priority']} | `{row['benchmark_id']}` | `{row['target_id']}` | "
            f"`{row['evidence_class']}` | `{row['template_column']}` | `{row['blocker']}` | {row['recommended_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `ready` | - | - | no open row_fill actions |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_guides(payload: dict[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        grouped[_text(row.get("field_guide_md"))].append(row)
    for guide_path in payload.get("guide_paths", []):
        rows = grouped.get(guide_path, [])
        title = "CASP17 Competitive-Floor Row Fill Field Guide"
        lines = [
            f"# {title}",
            "",
            f"- row_fill_csv: `{rows[0]['row_fill_csv'] if rows else '-'}`",
            f"- open actions: `{len(rows)}`",
            "",
            "| rank | class | column | current | expected | action |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| {row['action_rank']} | `{row['evidence_class']}` | `{row['template_column']}` | "
                f"`{row['current_value'] or '-'}` | {row['expected_value']} | {row['recommended_action']} |"
            )
        if not rows:
            lines.append("| - | `ready` | - | - | - | no open row_fill actions |")
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        path = _resolve(guide_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.write_guides:
        _write_guides(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a field-level worklist for competitive-floor row_fill.csv files.")
    parser.add_argument("--batch-json", default=DEFAULT_BATCH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--write-guides", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
