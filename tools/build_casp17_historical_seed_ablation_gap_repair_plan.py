#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ABLATION_CANDIDATES_JSON = "casp17/casp17_historical_seed_ablation_candidate_manifests_current.json"
DEFAULT_TOP5_CANDIDATE_POOLS_JSON = "casp17/casp17_historical_seed_top5_candidate_pools_current.json"
DEFAULT_REPAIR_DIR = "casp17/historical_seed_ablation_gap_repair_plan"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_ablation_gap_repair_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_ablation_gap_repair_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_ABLATION_GAP_REPAIR_PLAN.md"

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "repair_status",
    "repair_csv",
    "selected_prediction_present",
    "native_reference_present",
    "real_ablation_candidate_count",
    "missing_real_ablation_candidate_count",
    "top5_review_decoy_count",
    "top5_selected_copy_count",
    "next_action",
    "blockers",
]

REPAIR_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "candidate_kind",
    "role",
    "path",
    "exists",
    "coordinate_valid",
    "atom_count",
    "sha256_16",
    "candidate_rank",
    "generation_method",
    "source_path",
    "can_satisfy_ablation_manifest_ref",
    "notes",
]

REAL_ABLATION_ROLES = {"same_run_step_candidate", "pre_minimization_candidate"}

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed ablation gap repair plan only. It distinguishes real same-run/pre-minimization "
    "ablation-layer candidates from top-5 review decoys. Top-5 deterministic perturbations are listed as review "
    "context only and are not treated as operator-approved ablation evidence. This packet does not mutate operator "
    "CSVs, clear no-leak provenance, approve ablation coverage, run predictors, fetch structures, or submit to CASP."
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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y"}


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


def _by_target(payload: dict[str, Any], key: str) -> dict[str, list[dict[str, Any]]]:
    raw = payload.get(key)
    if not isinstance(raw, dict):
        return {}
    return {str(target).upper(): [row for row in rows if isinstance(row, dict)] for target, rows in raw.items() if isinstance(rows, list)}


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown"


def _manifest_repair_rows(manifest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in manifest_rows:
        role = _text(item.get("role"))
        if role not in REAL_ABLATION_ROLES:
            continue
        exists = _bool(item.get("exists"))
        coordinate_valid = _bool(item.get("coordinate_valid"))
        ready = exists and coordinate_valid and bool(_text(item.get("sha256_16")))
        rows.append(
            {
                "target_id": _text(item.get("target_id")).upper(),
                "benchmark_id": _text(item.get("benchmark_id")),
                "scope": _text(item.get("scope")),
                "candidate_kind": "real_ablation_layer_candidate" if ready else "missing_real_ablation_layer_candidate",
                "role": role,
                "path": _text(item.get("path")),
                "exists": exists,
                "coordinate_valid": coordinate_valid,
                "atom_count": _int(item.get("atom_count")),
                "sha256_16": _text(item.get("sha256_16")),
                "candidate_rank": "",
                "generation_method": "",
                "source_path": "",
                "can_satisfy_ablation_manifest_ref": ready,
                "notes": _text(item.get("notes")),
            }
        )
    return rows


def _top5_repair_rows(top5_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in top5_rows:
        exists = _bool(item.get("exists"))
        coordinate_valid = _bool(item.get("coordinate_valid"))
        role = _text(item.get("role"))
        kind = "top5_selected_copy" if role == "selected_prediction_copy" else "top5_review_decoy"
        rows.append(
            {
                "target_id": _text(item.get("target_id")).upper(),
                "benchmark_id": _text(item.get("benchmark_id")),
                "scope": _text(item.get("scope")),
                "candidate_kind": kind,
                "role": role,
                "path": _text(item.get("path")),
                "exists": exists,
                "coordinate_valid": coordinate_valid,
                "atom_count": _int(item.get("atom_count")),
                "sha256_16": _text(item.get("sha256_16")),
                "candidate_rank": _text(item.get("candidate_rank")),
                "generation_method": _text(item.get("generation_method")),
                "source_path": _text(item.get("source_path")),
                "can_satisfy_ablation_manifest_ref": False,
                "notes": "review context only; deterministic top-5 candidates are not ablation clearance evidence",
            }
        )
    return rows


def _build_target_row(
    ablation_row: dict[str, Any],
    manifest_rows: list[dict[str, Any]],
    top5_rows: list[dict[str, Any]],
    row_rank: int,
    repair_dir: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(ablation_row.get("target_id")).upper()
    repair_rows = _manifest_repair_rows(manifest_rows) + _top5_repair_rows(top5_rows)
    real_count = sum(1 for row in repair_rows if row["candidate_kind"] == "real_ablation_layer_candidate")
    missing_real_count = sum(1 for row in repair_rows if row["candidate_kind"] == "missing_real_ablation_layer_candidate")
    decoy_count = sum(1 for row in repair_rows if row["candidate_kind"] == "top5_review_decoy")
    selected_copy_count = sum(1 for row in repair_rows if row["candidate_kind"] == "top5_selected_copy")
    selected_present = _bool(ablation_row.get("selected_prediction_present"))
    native_present = _bool(ablation_row.get("native_reference_present"))
    blockers: list[str] = []
    if not selected_present:
        blockers.append("selected_prediction_missing_or_invalid")
    if not native_present:
        blockers.append("native_reference_missing_or_invalid")
    if real_count <= 0:
        blockers.append("real_ablation_layer_candidate_missing")
    if decoy_count:
        blockers.append("top5_decoys_not_clearance_evidence")
    if not selected_present or not native_present:
        status = "blocked_core_ablation_inputs"
        next_action = "repair selected prediction/native reference before ablation review"
    elif real_count > 0:
        status = "ablation_reference_candidate_ready_for_operator_review"
        next_action = "operator may review real ablation candidate manifest after no-leak provenance clearance"
    else:
        status = "ablation_gap_repair_required"
        next_action = "generate or attach true same-run/pre-minimization ablation layers; keep top5 decoys as review-only context"
    repair_csv = _resolve(repair_dir) / f"{row_rank:02d}_{_safe_name(target_id)}" / "ablation_gap_repair_candidates.csv"
    _write_csv(repair_csv, repair_rows, REPAIR_COLUMNS)
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": _text(ablation_row.get("benchmark_id")),
        "scope": _text(ablation_row.get("scope")),
        "repair_status": status,
        "repair_csv": _artifact(repair_csv),
        "selected_prediction_present": selected_present,
        "native_reference_present": native_present,
        "real_ablation_candidate_count": real_count,
        "missing_real_ablation_candidate_count": missing_real_count,
        "top5_review_decoy_count": decoy_count,
        "top5_selected_copy_count": selected_copy_count,
        "next_action": next_action,
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    return summary_row, repair_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    ablation_payload = _read_json(args.ablation_candidates_json)
    top5_payload = _read_json(args.top5_candidate_pools_json)
    ablation_rows = _rows(ablation_payload)
    manifest_by_target = _by_target(ablation_payload, "manifest_rows_by_target")
    top5_by_target = _by_target(top5_payload, "candidate_rows_by_target")
    rows: list[dict[str, Any]] = []
    repair_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, ablation_row in enumerate(ablation_rows, start=1):
        target_id = _text(ablation_row.get("target_id")).upper()
        summary_row, repair_rows = _build_target_row(
            ablation_row,
            manifest_by_target.get(target_id, []),
            top5_by_target.get(target_id, []),
            index,
            args.repair_dir,
        )
        rows.append(summary_row)
        repair_rows_by_target[target_id] = repair_rows
    input_blockers: list[str] = []
    if not _resolve(args.ablation_candidates_json).exists():
        input_blockers.append("ablation_candidates_json_missing")
    if not _resolve(args.top5_candidate_pools_json).exists():
        input_blockers.append("top5_candidate_pools_json_missing")
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_ablation_rows"
    elif any(row["repair_status"] == "blocked_core_ablation_inputs" for row in rows):
        status = "blocked_core_ablation_inputs"
    elif any(row["repair_status"] == "ablation_gap_repair_required" for row in rows):
        status = "ablation_gap_repair_required"
    else:
        status = "ablation_reference_candidates_ready_for_operator_review"
    first_open = next(
        (row for row in rows if row["repair_status"] != "ablation_reference_candidate_ready_for_operator_review"),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_historical_seed_ablation_gap_repair_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "ablation_gap_repair_status": status,
        "ablation_candidates_json": _artifact(args.ablation_candidates_json),
        "top5_candidate_pools_json": _artifact(args.top5_candidate_pools_json),
        "repair_dir": _artifact(args.repair_dir),
        "seed_row_count": len(rows),
        "repair_csv_count": sum(1 for row in rows if _text(row.get("repair_csv"))),
        "real_ablation_candidate_count": sum(_int(row.get("real_ablation_candidate_count")) for row in rows),
        "missing_real_ablation_candidate_count": sum(
            _int(row.get("missing_real_ablation_candidate_count")) for row in rows
        ),
        "top5_review_decoy_count": sum(_int(row.get("top5_review_decoy_count")) for row in rows),
        "top5_selected_copy_count": sum(_int(row.get("top5_selected_copy_count")) for row in rows),
        "ready_for_operator_review_count": sum(
            1 for row in rows if row["repair_status"] == "ablation_reference_candidate_ready_for_operator_review"
        ),
        "gap_repair_required_count": sum(1 for row in rows if row["repair_status"] == "ablation_gap_repair_required"),
        "blocked_core_ablation_input_count": sum(
            1 for row in rows if row["repair_status"] == "blocked_core_ablation_inputs"
        ),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide ablation candidate manifests",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "repair_rows_by_target": repair_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Ablation Gap Repair Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- ablation_gap_repair_status: `{summary['ablation_gap_repair_status']}`",
        f"- seed rows/repair csvs: `{summary['seed_row_count']}/{summary['repair_csv_count']}`",
        f"- real/missing-real/top5-decoy/top5-copy: `{summary['real_ablation_candidate_count']}/{summary['missing_real_ablation_candidate_count']}/{summary['top5_review_decoy_count']}/{summary['top5_selected_copy_count']}`",
        f"- ready/gap/core-blocked: `{summary['ready_for_operator_review_count']}/{summary['gap_repair_required_count']}/{summary['blocked_core_ablation_input_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | real | missing real | decoys | copy | csv | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['repair_status']}` | "
            f"{row['real_ablation_candidate_count']} | {row['missing_real_ablation_candidate_count']} | "
            f"{row['top5_review_decoy_count']} | {row['top5_selected_copy_count']} | "
            f"`{row['repair_csv']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_ablation_rows` | 0 | 0 | 0 | 0 | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed ablation gap repair plan.")
    parser.add_argument("--ablation-candidates-json", default=DEFAULT_ABLATION_CANDIDATES_JSON)
    parser.add_argument("--top5-candidate-pools-json", default=DEFAULT_TOP5_CANDIDATE_POOLS_JSON)
    parser.add_argument("--repair-dir", default=DEFAULT_REPAIR_DIR)
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
