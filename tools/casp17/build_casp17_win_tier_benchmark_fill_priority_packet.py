#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_INVENTORY_JSON = "runs/casp17_win_tier_benchmark_input_inventory_current.json"
DEFAULT_EVIDENCE_FILL_KIT_JSON = "runs/casp17_win_tier_benchmark_evidence_fill_kit_current.json"
DEFAULT_CLOSURE_PLAN_JSON = "runs/casp17_win_tier_benchmark_closure_plan_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_fill_priority_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_fill_priority_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_fill_priority_packet_current.md"

EVIDENCE_CLASSES = [
    "target_identity",
    "core_file",
    "provenance_field",
    "calibration_field",
    "ablation_layer_file",
    "native_metric_gate",
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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _priority_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("sidechain_native_priority_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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
        fieldnames = ["operator_priority", "benchmark_id", "target_id", "fill_batch", "next_action"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _missing_evidence_by_benchmark(fill_rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    by_benchmark: dict[str, dict[str, int]] = {}
    for row in fill_rows:
        benchmark_id = _text(row.get("benchmark_id"))
        if not benchmark_id:
            continue
        status = _text(row.get("completion_status")).lower()
        if status not in {"missing", "blocked", ""}:
            continue
        evidence_class = _text(row.get("evidence_class")) or "unknown"
        item = by_benchmark.setdefault(benchmark_id, {key: 0 for key in EVIDENCE_CLASSES})
        item[evidence_class] = item.get(evidence_class, 0) + 1
    return by_benchmark


def _scope_slot(row: dict[str, Any], counters: dict[str, int]) -> int:
    scope = _text(row.get("scope")).lower()
    counters[scope] = counters.get(scope, 0) + 1
    return counters[scope]


def _fill_batch(scope: str, scope_slot: int, closure: dict[str, Any]) -> str:
    competitive_monomer = _int(closure.get("competitive_required_monomer_rows"), 10)
    competitive_complex = _int(closure.get("competitive_required_complex_rows"), 5)
    win_monomer = _int(closure.get("win_required_monomer_rows"), 25)
    win_complex = _int(closure.get("win_required_complex_rows"), 15)
    if scope == "monomer" and scope_slot <= competitive_monomer:
        return "competitive_floor_batch"
    if scope == "complex" and scope_slot <= competitive_complex:
        return "competitive_floor_batch"
    if scope == "monomer" and scope_slot <= win_monomer:
        return "win_extension_batch"
    if scope == "complex" and scope_slot <= win_complex:
        return "win_extension_batch"
    return "overflow_not_required_for_current_thresholds"


def _next_action(row: dict[str, Any], missing: dict[str, int]) -> str:
    target_id = _text(row.get("target_id"))
    row_dir = _text(row.get("row_dir"))
    if target_id.upper().startswith("REQUIRED_") or missing.get("target_identity", 0):
        return f"Replace placeholder target identity and row metadata in {row_dir or 'row scaffold'} with a cleared historical non-current CASP target."
    if missing.get("core_file", 0):
        return "Add local internal prediction/native PDB files and update required_files/provenance templates."
    if missing.get("provenance_field", 0):
        return "Complete no-leak provenance fields before any metric promotion."
    if missing.get("calibration_field", 0):
        return "Fill selected/best rank and internal-score calibration fields from the local top-5 run."
    if missing.get("ablation_layer_file", 0):
        return "Populate all refinement-layer ablation PDBs for final-vs-baseline evidence."
    if missing.get("native_metric_gate", 0):
        return "Run historical/native scoring packets and verify the required native metric gates."
    return "Re-run input inventory, operator preflight, operator import, historical benchmark, calibration, and readiness dashboards."


def _priority_score(fill_batch: str, row: dict[str, Any], missing_total: int) -> tuple[int, int, int]:
    batch_rank = {
        "competitive_floor_batch": 0,
        "win_extension_batch": 1,
        "overflow_not_required_for_current_thresholds": 2,
    }.get(fill_batch, 3)
    return (batch_rank, _int(row.get("row_rank"), 999), missing_total)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    inventory_payload = _read_json(args.input_inventory_json)
    fill_payload = _read_json(args.evidence_fill_kit_json)
    closure_payload = _read_json(args.closure_plan_json)
    inventory_summary = _summary(inventory_payload)
    fill_summary = _summary(fill_payload)
    closure_summary = _summary(closure_payload)
    inventory_rows = _rows(inventory_payload)
    missing_by_benchmark = _missing_evidence_by_benchmark(_rows(fill_payload))
    sidechain_priority_rows = _priority_rows(fill_payload)
    sidechain_open_priority_rows = [
        row for row in sidechain_priority_rows if _text(row.get("completion_status")).lower() != "filled"
    ]
    first_sidechain_priority = sidechain_open_priority_rows[0] if sidechain_open_priority_rows else {}

    scope_counters: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for source in sorted(inventory_rows, key=lambda row: _int(row.get("row_rank"), 999)):
        scope = _text(source.get("scope")).lower()
        slot = _scope_slot(source, scope_counters)
        batch = _fill_batch(scope, slot, closure_summary)
        benchmark_id = _text(source.get("benchmark_id"))
        missing = missing_by_benchmark.get(benchmark_id, {key: 0 for key in EVIDENCE_CLASSES})
        missing_total = sum(int(missing.get(key, 0)) for key in EVIDENCE_CLASSES)
        row = {
            "operator_priority": 0,
            "fill_batch": batch,
            "row_rank": _int(source.get("row_rank")),
            "scope_slot": slot,
            "benchmark_id": benchmark_id,
            "target_id": _text(source.get("target_id")).upper(),
            "scope": scope,
            "metric_profile": _text(source.get("metric_profile")),
            "inventory_status": _text(source.get("inventory_status")),
            "row_dir": _text(source.get("row_dir")),
            "required_file_count": _int(source.get("required_file_count")),
            "present_file_count": _int(source.get("present_file_count")),
            "missing_file_count": _int(source.get("missing_file_count")),
            "prediction_file_present": bool(source.get("prediction_file_present")),
            "native_file_present": bool(source.get("native_file_present")),
            "ablation_layer_present_count": _int(source.get("ablation_layer_present_count")),
            "ablation_layer_required_count": _int(source.get("ablation_layer_required_count")),
            "provenance_status": _text(source.get("provenance_status")),
            "calibration_status": _text(source.get("calibration_status")),
            "missing_target_identity_count": int(missing.get("target_identity", 0)),
            "missing_core_file_count": int(missing.get("core_file", 0)),
            "missing_provenance_field_count": int(missing.get("provenance_field", 0)),
            "missing_calibration_field_count": int(missing.get("calibration_field", 0)),
            "missing_ablation_layer_file_count": int(missing.get("ablation_layer_file", 0)),
            "missing_native_metric_gate_count": int(missing.get("native_metric_gate", 0)),
            "missing_evidence_item_count": missing_total,
            "next_action": _next_action(source, missing),
            "blockers": _text(source.get("blockers")),
        }
        rows.append(row)
    rows.sort(key=lambda row: _priority_score(str(row["fill_batch"]), row, int(row["missing_evidence_item_count"])))
    for index, row in enumerate(rows, start=1):
        row["operator_priority"] = index

    competitive_rows = [row for row in rows if row["fill_batch"] == "competitive_floor_batch"]
    win_rows = [row for row in rows if row["fill_batch"] in {"competitive_floor_batch", "win_extension_batch"}]
    first_row = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_win_tier_benchmark_fill_priority_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "fill_priority_status": "ready" if rows else "blocked",
        "input_inventory_json": _artifact(args.input_inventory_json),
        "input_inventory_status": _text(inventory_summary.get("inventory_status")),
        "evidence_fill_kit_json": _artifact(args.evidence_fill_kit_json),
        "evidence_fill_kit_status": _text(fill_summary.get("fill_kit_status")),
        "closure_plan_json": _artifact(args.closure_plan_json),
        "closure_plan_status": _text(closure_summary.get("closure_plan_status")),
        "row_count": len(rows),
        "competitive_batch_row_count": len(competitive_rows),
        "competitive_batch_monomer_count": sum(1 for row in competitive_rows if row["scope"] == "monomer"),
        "competitive_batch_complex_count": sum(1 for row in competitive_rows if row["scope"] == "complex"),
        "win_required_row_count": len(win_rows),
        "win_required_monomer_count": sum(1 for row in win_rows if row["scope"] == "monomer"),
        "win_required_complex_count": sum(1 for row in win_rows if row["scope"] == "complex"),
        "competitive_batch_missing_evidence_item_count": sum(int(row["missing_evidence_item_count"]) for row in competitive_rows),
        "win_required_missing_evidence_item_count": sum(int(row["missing_evidence_item_count"]) for row in win_rows),
        "first_priority_benchmark_id": _text(first_row.get("benchmark_id")),
        "first_priority_target_id": _text(first_row.get("target_id")),
        "first_priority_scope": _text(first_row.get("scope")),
        "first_priority_next_action": _text(first_row.get("next_action")),
        "sidechain_native_priority_status": _text(fill_summary.get("sidechain_native_priority_status")),
        "sidechain_native_priority_action_count": _int(fill_summary.get("sidechain_native_priority_action_count")),
        "sidechain_native_priority_open_action_count": _int(
            fill_summary.get("sidechain_native_priority_open_action_count")
        ),
        "sidechain_native_priority_csv_path": _text(fill_summary.get("sidechain_native_priority_csv_path")),
        "sidechain_native_first_open_action_id": _text(first_sidechain_priority.get("action_id")),
        "sidechain_native_first_open_benchmark_id": _text(first_sidechain_priority.get("benchmark_id")),
        "sidechain_native_first_open_target_id": _text(first_sidechain_priority.get("target_id")),
        "sidechain_native_first_open_evidence_class": _text(first_sidechain_priority.get("evidence_class")),
        "sidechain_native_first_open_next_action": _text(first_sidechain_priority.get("next_action")),
        "missing_evidence_by_class": {
            key: sum(int(row.get(f"missing_{key}_count", 0)) for row in rows)
            for key in EVIDENCE_CLASSES
        },
        "post_fill_validation_commands": [
            "python3 tools/casp17/build_casp17_win_tier_benchmark_input_inventory.py",
            "python3 tools/casp17/build_casp17_win_tier_benchmark_operator_preflight.py",
            "python3 tools/casp17/build_casp17_win_tier_benchmark_operator_import_packet.py",
            "python3 tools/build_casp17_historical_benchmark_packet.py",
            "python3 tools/build_casp17_sidechain_native_manifest_sync_packet.py --manifest-csv runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv --workorder-json runs/casp17_sidechain_native_input_workorder_current.json",
            "python3 tools/build_casp17_sidechain_native_benchmark_packet.py --manifest-csv runs/casp17_sidechain_native_manifest_candidate_current.csv",
            "python3 tools/build_casp17_model_selection_calibration_packet.py",
            "python3 tools/casp17/build_casp17_refinement_ablation_packet.py",
            "python3 tools/casp17/build_casp17_readiness_dashboard.py",
        ],
        "claim_boundary": (
            "Local fill-priority planning only. It ranks no-leak historical benchmark inputs to unlock competitive and win-tier evidence; "
            "it does not fetch natives, clear provenance, score native accuracy, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win-Tier Benchmark Fill Priority Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- fill_priority_status: `{summary['fill_priority_status']}`",
        f"- competitive batch rows monomer/complex/total: `{summary['competitive_batch_monomer_count']}/{summary['competitive_batch_complex_count']}/{summary['competitive_batch_row_count']}`",
        f"- win required rows monomer/complex/total: `{summary['win_required_monomer_count']}/{summary['win_required_complex_count']}/{summary['win_required_row_count']}`",
        f"- competitive missing evidence items: `{summary['competitive_batch_missing_evidence_item_count']}`",
        f"- win missing evidence items: `{summary['win_required_missing_evidence_item_count']}`",
        f"- first priority: `{summary['first_priority_benchmark_id']}` `{summary['first_priority_target_id']}` `{summary['first_priority_scope']}`",
        f"- first action: {summary['first_priority_next_action'] or '-'}",
        f"- sidechain-native priority: `{summary['sidechain_native_priority_status'] or '-'}` open/action `{summary['sidechain_native_priority_open_action_count']}/{summary['sidechain_native_priority_action_count']}`",
        f"- sidechain-native first action: `{summary['sidechain_native_first_open_action_id'] or '-'}` {summary['sidechain_native_first_open_next_action'] or '-'}",
        f"- sidechain-native priority csv: `{summary['sidechain_native_priority_csv_path'] or '-'}`",
        "",
        "## Rows",
        "",
        "| priority | batch | rank | benchmark | target | scope | files | prov | calib | missing evidence | next action |",
        "| ---: | --- | ---: | --- | --- | --- | ---: | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['fill_batch']}` | {row['row_rank']} | `{row['benchmark_id']}` | "
            f"`{row['target_id']}` | `{row['scope']}` | {row['present_file_count']}/{row['required_file_count']} | "
            f"`{row['provenance_status']}` | `{row['calibration_status']}` | {row['missing_evidence_item_count']} | "
            f"{row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Post-Fill Validation Commands",
            "",
            *[f"- `{command}`" for command in summary["post_fill_validation_commands"]],
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
    parser = argparse.ArgumentParser(description="Build a fill-priority plan for CASP17 no-leak win-tier benchmark inputs.")
    parser.add_argument("--input-inventory-json", default=DEFAULT_INPUT_INVENTORY_JSON)
    parser.add_argument("--evidence-fill-kit-json", default=DEFAULT_EVIDENCE_FILL_KIT_JSON)
    parser.add_argument("--closure-plan-json", default=DEFAULT_CLOSURE_PLAN_JSON)
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
    if payload["summary"]["fill_priority_status"] != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
