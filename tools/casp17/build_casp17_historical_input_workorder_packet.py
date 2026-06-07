#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PREFLIGHT_JSON = "runs/casp17_historical_input_preflight_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_historical_input_workorder_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_historical_input_workorder_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_historical_input_workorder_packet_current.md"
DEFAULT_OUT_TEMPLATE_CSV = "runs/casp17_historical_benchmark_manifest_operator_template_current.csv"

REQUIRED_MANIFEST_COLUMNS = ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"]
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

BLOCKER_ACTIONS = {
    "placeholder_target_id": "replace placeholder with a cleared non-current historical target id",
    "prediction_pdb_missing": "set prediction_pdb to a local internally generated prediction PDB",
    "prediction_pdb_not_found": "place the local internally generated prediction PDB at prediction_pdb",
    "native_pdb_missing": "set native_pdb to a local historical native PDB",
    "native_pdb_not_found": "place the local historical native PDB at native_pdb",
    "leakage_clearance_required": "set leakage_clearance only after no-leak review",
    "prediction_method_required": "record the internal prediction method",
    "prediction_created_at_required_iso_date": "record prediction_created_at as YYYY-MM-DD",
    "native_release_date_required_iso_date": "record native_release_date as YYYY-MM-DD",
    "prediction_date_not_before_native_release": "use only predictions generated before native release",
    "prediction_generated_before_native_release_required": "confirm prediction_generated_before_native_release=true",
    "public_template_or_native_used_for_prediction_must_be_false": "confirm no public/template/native structure was used for prediction",
    "other_team_model_used_must_be_false": "confirm no other-team model was used",
    "post_release_information_used_must_be_false": "confirm no post-release information was used",
    "current_casp17_target_must_be_false": "confirm the benchmark row is not a current CASP17 target",
    "current_casp17_target_not_allowed": "remove current CASP17 targets from historical benchmark inputs",
    "operator_clearance_required": "record operator_clearance only after no-leak review",
}


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
        fieldnames = ["workorder_id", "target_id", "workorder_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _split_csv(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(",") if part.strip()]


def _parse_json_dict(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    text = _text(value)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items()}


def _path_exists(path_text: str) -> bool:
    return bool(path_text and _resolve(path_text).exists())


def _blocker_actions(blockers: list[str]) -> list[str]:
    actions: list[str] = []
    for blocker in blockers:
        actions.append(BLOCKER_ACTIONS.get(blocker, f"resolve blocker: {blocker}"))
    return actions


def _row_status(row: dict[str, Any], blockers: list[str], missing_layers: list[str]) -> str:
    if row.get("historical_ready") is True and row.get("ablation_ready") is True:
        return "complete"
    if not blockers and missing_layers:
        return "ablation_inputs_needed"
    return "core_inputs_needed"


def _workorder_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    blockers = _split_csv(row.get("blockers"))
    missing_layers = _split_csv(row.get("missing_ablation_layers"))
    layer_paths = _parse_json_dict(row.get("layer_prediction_paths_json"))
    prediction_pdb = _text(row.get("prediction_pdb"))
    native_pdb = _text(row.get("native_pdb"))
    status = _row_status(row, blockers, missing_layers)
    missing_core_files = int(not _path_exists(prediction_pdb)) + int(not _path_exists(native_pdb))
    actions = _blocker_actions(blockers)
    if missing_layers:
        actions.append("populate missing ablation layer prediction PDBs or layer-specific manifest columns")
    next_action = "row already ready for historical and ablation scoring"
    if status == "core_inputs_needed":
        next_action = "fill local prediction/native files plus no-leak provenance, then rerun scaffold/promotion/preflight"
    elif status == "ablation_inputs_needed":
        next_action = "add per-layer historical prediction PDBs for refinement-ablation evidence"
    return {
        "workorder_rank": index,
        "workorder_id": f"{_text(row.get('benchmark_id')) or 'hist_unknown'}_input_workorder",
        "workorder_status": status,
        "row_source": _text(row.get("row_source")),
        "benchmark_id": _text(row.get("benchmark_id")),
        "target_id": _text(row.get("target_id")),
        "scope": _text(row.get("scope")),
        "prediction_pdb": prediction_pdb,
        "prediction_pdb_exists": _path_exists(prediction_pdb),
        "native_pdb": native_pdb,
        "native_pdb_exists": _path_exists(native_pdb),
        "missing_core_file_count": missing_core_files,
        "missing_ablation_layer_count": len(missing_layers),
        "missing_ablation_layers": ",".join(missing_layers),
        "required_actions": "; ".join(actions),
        "operator_next_action": next_action,
        "historical_ready": bool(row.get("historical_ready")),
        "ablation_ready": bool(row.get("ablation_ready")),
        "blockers": ",".join(blockers),
        "layer_prediction_paths_json": json.dumps(layer_paths, sort_keys=True),
    }


def _template_row(row: dict[str, Any]) -> dict[str, str]:
    layer_paths = _parse_json_dict(row.get("layer_prediction_paths_json"))
    template = {
        "benchmark_id": _text(row.get("benchmark_id")) or "hist_REQUIRED_TARGET",
        "target_id": _text(row.get("target_id")) or "REQUIRED_TARGET",
        "scope": _text(row.get("scope")) or "REQUIRED_SCOPE",
        "split": "historical",
        "prediction_pdb": _text(row.get("prediction_pdb")),
        "native_pdb": _text(row.get("native_pdb")),
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "REQUIRED_INTERNAL_METHOD",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
    }
    for layer in ABLATION_LAYER_NAMES:
        template[f"{layer}_prediction_pdb"] = layer_paths.get(layer, "")
    return template


def _write_template_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> str:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = REQUIRED_MANIFEST_COLUMNS + PROVENANCE_COLUMNS + [f"{layer}_prediction_pdb" for layer in ABLATION_LAYER_NAMES]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_template_row(row))
    return _artifact(path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    preflight = _read_json(args.preflight_json)
    source_rows = preflight.get("rows") if isinstance(preflight.get("rows"), list) else []
    rows = [_workorder_row(row, index) for index, row in enumerate(source_rows, start=1) if isinstance(row, dict)]
    template_csv = _write_template_csv(args.out_template_csv, source_rows)
    core_rows = [row for row in rows if row["workorder_status"] == "core_inputs_needed"]
    ablation_rows = [row for row in rows if row["workorder_status"] == "ablation_inputs_needed"]
    complete_rows = [row for row in rows if row["workorder_status"] == "complete"]
    preflight_summary = preflight.get("summary") if isinstance(preflight.get("summary"), dict) else {}
    summary = {
        "packet_type": "casp17_historical_input_workorder_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "workorder_status": "ready" if rows else "blocked",
        "preflight_json": _artifact(args.preflight_json),
        "preflight_status": preflight_summary.get("preflight_status", ""),
        "source_mode": preflight_summary.get("source_mode", ""),
        "source_artifact": preflight_summary.get("source_artifact", ""),
        "workorder_count": len(rows),
        "core_input_workorder_count": len(core_rows),
        "ablation_input_workorder_count": len(ablation_rows),
        "complete_workorder_count": len(complete_rows),
        "missing_core_file_count": sum(int(row["missing_core_file_count"]) for row in rows),
        "missing_ablation_layer_count": sum(int(row["missing_ablation_layer_count"]) for row in rows),
        "operator_template_csv": template_csv,
        "claim_boundary": "Local no-leak historical input workorder only; it does not fetch native structures, clear provenance, activate manifests, score accuracy, or submit to CASP.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Input Workorder Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- workorder_status: `{summary['workorder_status']}`",
        f"- preflight_status: `{summary['preflight_status'] or '-'}`",
        f"- source_mode: `{summary['source_mode'] or '-'}`",
        f"- workorders/core/ablation/complete: `{summary['workorder_count']}/{summary['core_input_workorder_count']}/{summary['ablation_input_workorder_count']}/{summary['complete_workorder_count']}`",
        f"- missing core files: `{summary['missing_core_file_count']}`",
        f"- missing ablation layer files: `{summary['missing_ablation_layer_count']}`",
        f"- operator template csv: `{summary['operator_template_csv']}`",
        "",
        "## Operator Sequence",
        "",
        "1. Replace placeholder target IDs with cleared non-current historical targets.",
        "2. Place local internally generated prediction PDBs at `prediction_pdb` paths.",
        "3. Place local historical native PDBs at `native_pdb` paths.",
        "4. Fill provenance only after no-leak review: prediction method/date, native release date, before-release confirmation, no public/template/native use, no other-team model, no post-release information, non-current CASP17 target, and operator clearance.",
        "5. Add optional per-layer prediction PDBs before running refinement-ablation evidence.",
        "6. Rerun scaffold, promotion, preflight, historical benchmark, sidechain-native benchmark, refinement-ablation, and model-selection calibration packets.",
        "",
        "## Workorders",
        "",
        "| rank | benchmark | target | scope | status | prediction exists | native exists | missing layers | next action | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['workorder_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['workorder_status']}` | `{row['prediction_pdb_exists']}` | `{row['native_pdb_exists']}` | "
            f"{row['missing_ablation_layer_count']} | {row['operator_next_action']} | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | - | `blocked` | `False` | `False` | 0 | no preflight rows | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build operator workorders for CASP17 no-leak historical benchmark inputs.")
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-template-csv", default=DEFAULT_OUT_TEMPLATE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
