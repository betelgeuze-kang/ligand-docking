#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FILL_CANDIDATES_JSON = "casp17/casp17_historical_seed_clearance_fill_candidate_packet_current.json"
DEFAULT_NO_LEAK_REPAIR_JSON = "casp17/casp17_historical_seed_no_leak_gap_repair_plan_current.json"
DEFAULT_ABLATION_REPAIR_JSON = "casp17/casp17_historical_seed_ablation_gap_repair_plan_current.json"
DEFAULT_BOARD_DIR = "casp17/historical_seed_clearance_execution_board"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_clearance_execution_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_clearance_execution_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_CLEARANCE_EXECUTION_BOARD.md"

ROW_COLUMNS = [
    "execution_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "execution_status",
    "operator_no_leak_field_count",
    "proposed_field_count",
    "calibration_candidate_count",
    "ablation_candidate_count",
    "blocked_ablation_field_count",
    "field_candidate_csv",
    "no_leak_repair_csv",
    "ablation_repair_csv",
    "execution_folder",
    "next_action",
    "blockers",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed clearance execution board only. It ranks existing fill candidates by "
    "shortest local path to a cleared historical benchmark row. It does not mutate operator CSVs, clear "
    "no-leak provenance, approve ablation evidence, compute official CASP metrics, or submit to CASP."
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
        return int(float(_text(value)))
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _repair_csv_by_target(payload: dict[str, Any], key: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in _rows(payload):
        target_id = _text(row.get("target_id"))
        repair_csv = _text(row.get(key))
        if target_id and repair_csv:
            result[target_id] = repair_csv
    return result


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown"


def _status(row: dict[str, Any]) -> tuple[str, str, str]:
    operator_required = _int(row.get("operator_required_field_count"))
    blocked = _int(row.get("blocked_field_count"))
    ablation = _int(row.get("ablation_candidate_count"))
    if operator_required == 0 and blocked == 0:
        return "ready_for_clearance_apply", "apply reviewed field candidates into operator clearance intake", ""
    if blocked == 0:
        return (
            "operator_no_leak_only",
            "fill operator no-leak evidence fields, then apply prepared calibration and ablation candidates",
            "operator_no_leak_evidence_required",
        )
    blockers = ["operator_no_leak_evidence_required"]
    if ablation <= 0:
        blockers.append("real_ablation_layer_required")
    return (
        "ablation_repair_then_operator_no_leak",
        "repair real ablation layer evidence, then fill operator no-leak evidence fields",
        ",".join(blockers),
    )


def _execution_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int]:
    status_weight = {
        "ready_for_clearance_apply": 0,
        "operator_no_leak_only": 1,
        "ablation_repair_then_operator_no_leak": 2,
    }.get(_text(row.get("execution_status")), 9)
    return (
        status_weight,
        _int(row.get("blocked_ablation_field_count")),
        _int(row.get("operator_no_leak_field_count")),
        _int(row.get("row_rank")),
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    fill_payload = _read_json(args.fill_candidates_json)
    no_leak_repair_payload = _read_json(args.no_leak_repair_json)
    ablation_repair_payload = _read_json(args.ablation_repair_json)
    no_leak_repair_by_target = _repair_csv_by_target(no_leak_repair_payload, "repair_csv")
    ablation_repair_by_target = _repair_csv_by_target(ablation_repair_payload, "repair_csv")

    unsorted_rows: list[dict[str, Any]] = []
    for row in _rows(fill_payload):
        target_id = _text(row.get("target_id"))
        status, next_action, blockers = _status(row)
        folder = _resolve(args.board_dir) / f"{int(_int(row.get('row_rank'))):02d}_{_safe_name(target_id)}"
        unsorted_rows.append(
            {
                "row_rank": _int(row.get("row_rank")),
                "target_id": target_id,
                "benchmark_id": _text(row.get("benchmark_id")),
                "scope": _text(row.get("scope")),
                "execution_status": status,
                "operator_no_leak_field_count": _int(row.get("operator_required_field_count")),
                "proposed_field_count": _int(row.get("proposed_field_count")),
                "calibration_candidate_count": _int(row.get("calibration_candidate_count")),
                "ablation_candidate_count": _int(row.get("ablation_candidate_count")),
                "blocked_ablation_field_count": _int(row.get("blocked_field_count")),
                "field_candidate_csv": _text(row.get("field_candidate_csv")),
                "no_leak_repair_csv": no_leak_repair_by_target.get(target_id, ""),
                "ablation_repair_csv": ablation_repair_by_target.get(target_id, ""),
                "execution_folder": _artifact(folder),
                "next_action": next_action,
                "blockers": blockers,
            }
        )

    rows = sorted(unsorted_rows, key=_execution_sort_key)
    for index, row in enumerate(rows, start=1):
        row["execution_rank"] = index

    first = rows[0] if rows else {}
    no_leak_only_rows = [row for row in rows if row["execution_status"] == "operator_no_leak_only"]
    ablation_repair_rows = [row for row in rows if row["execution_status"] == "ablation_repair_then_operator_no_leak"]
    summary = {
        "packet_type": "casp17_historical_seed_clearance_execution_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "execution_board_status": "first_row_operator_no_leak_only" if no_leak_only_rows else "ablation_repair_required",
        "seed_row_count": len(rows),
        "operator_no_leak_only_row_count": len(no_leak_only_rows),
        "ablation_repair_required_row_count": len(ablation_repair_rows),
        "operator_no_leak_field_count": sum(_int(row.get("operator_no_leak_field_count")) for row in rows),
        "proposed_field_count": sum(_int(row.get("proposed_field_count")) for row in rows),
        "calibration_candidate_count": sum(_int(row.get("calibration_candidate_count")) for row in rows),
        "ablation_candidate_count": sum(_int(row.get("ablation_candidate_count")) for row in rows),
        "blocked_ablation_field_count": sum(_int(row.get("blocked_ablation_field_count")) for row in rows),
        "first_execution_target_id": _text(first.get("target_id")),
        "first_execution_status": _text(first.get("execution_status")),
        "first_execution_next_action": _text(first.get("next_action")),
        "first_execution_folder": _text(first.get("execution_folder")),
        "fill_candidates_json": _artifact(args.fill_candidates_json),
        "no_leak_repair_json": _artifact(args.no_leak_repair_json),
        "ablation_repair_json": _artifact(args.ablation_repair_json),
        "board_dir": _artifact(args.board_dir),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_row_folders(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        folder = _resolve(row["execution_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "execution_inputs.csv", [row], ROW_COLUMNS)
        lines = [
            f"# CASP17 Historical Seed Clearance Execution {row['execution_rank']}: {row['target_id']}",
            "",
            f"- status: `{row['execution_status']}`",
            f"- scope: `{row['scope']}`",
            f"- operator no-leak fields: `{row['operator_no_leak_field_count']}`",
            f"- proposed fields ready: `{row['proposed_field_count']}`",
            f"- calibration candidates: `{row['calibration_candidate_count']}`",
            f"- ablation candidates: `{row['ablation_candidate_count']}`",
            f"- blocked ablation fields: `{row['blocked_ablation_field_count']}`",
            f"- fill candidates: `{row['field_candidate_csv'] or '-'}`",
            f"- no-leak repair CSV: `{row['no_leak_repair_csv'] or '-'}`",
            f"- ablation repair CSV: `{row['ablation_repair_csv'] or '-'}`",
            f"- next action: {row['next_action']}",
            f"- blockers: `{row['blockers'] or '-'}`",
            "",
            "## Guardrail",
            "",
            "Do not promote this row into the cleared manifest until operator no-leak evidence and required "
            "negative-control confirmations are filled with independent evidence.",
            "",
        ]
        (folder / "ACTION.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Clearance Execution Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['execution_board_status']}`",
        f"- seed rows: `{summary['seed_row_count']}`",
        f"- operator no-leak-only rows: `{summary['operator_no_leak_only_row_count']}`",
        f"- ablation-repair rows: `{summary['ablation_repair_required_row_count']}`",
        f"- operator no-leak fields: `{summary['operator_no_leak_field_count']}`",
        f"- proposed fields: `{summary['proposed_field_count']}`",
        f"- calibration/ablation candidates: `{summary['calibration_candidate_count']}/{summary['ablation_candidate_count']}`",
        f"- blocked ablation fields: `{summary['blocked_ablation_field_count']}`",
        f"- first execution target: `{summary['first_execution_target_id']}` `{summary['first_execution_status']}`",
        f"- next action: {summary['first_execution_next_action']}",
        "",
        "## Execution Rows",
        "",
        "| rank | target | scope | status | no-leak fields | proposed | ablation blocked | folder | next action |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['execution_rank']} | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['execution_status']}` | {row['operator_no_leak_field_count']} | "
            f"{row['proposed_field_count']} | {row['blocked_ablation_field_count']} | "
            f"`{row['execution_folder']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_row_folders(payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed clearance execution board.")
    parser.add_argument("--fill-candidates-json", default=DEFAULT_FILL_CANDIDATES_JSON)
    parser.add_argument("--no-leak-repair-json", default=DEFAULT_NO_LEAK_REPAIR_JSON)
    parser.add_argument("--ablation-repair-json", default=DEFAULT_ABLATION_REPAIR_JSON)
    parser.add_argument("--board-dir", default=DEFAULT_BOARD_DIR)
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
