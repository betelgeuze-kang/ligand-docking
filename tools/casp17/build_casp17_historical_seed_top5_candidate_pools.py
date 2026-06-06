#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_POOL_DIR = "casp17/historical_seed_top5_candidate_pools"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_top5_candidate_pools_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_top5_candidate_pools_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_TOP5_CANDIDATE_POOLS.md"

AMPLITUDES = [0.0, 0.12, 0.24, 0.36, 0.48]

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "pool_status",
    "candidate_pool_csv",
    "candidate_pool_dir",
    "candidate_model_count",
    "top5_candidate_pool_ready",
    "selected_source_pdb",
    "selected_source_present",
    "generated_perturbation_count",
    "next_action",
    "blockers",
]

CANDIDATE_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "candidate_rank",
    "role",
    "path",
    "exists",
    "atom_count",
    "coordinate_valid",
    "sha256_16",
    "generation_method",
    "source_path",
    "amplitude_angstrom",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed top-5 candidate-pool scaffolding only. Perturbation candidates are "
    "deterministic review decoys derived from already-local historical selected predictions. They are not "
    "independent predictor outputs, do not compute native accuracy, do not clear leakage provenance, do not "
    "fetch native structures, and do not submit to CASP."
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


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb_stats(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    stats: dict[str, Any] = {
        "exists": path.is_file(),
        "atom_count": 0,
        "coordinate_valid": False,
        "sha256_16": "",
    }
    if not path.is_file():
        return stats
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    atom_count = 0
    coordinate_valid = True
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
    stats["sha256_16"] = digest.hexdigest()[:16]
    return stats


def _perturb_line(line: str, atom_index: int, amplitude: float, variant_rank: int) -> str:
    if amplitude <= 0 or not line.startswith(("ATOM  ", "HETATM")):
        return line
    if len(line) < 54:
        return line
    try:
        x = float(line[30:38])
        y = float(line[38:46])
        z = float(line[46:54])
    except ValueError:
        return line
    phase = atom_index + (variant_rank * 17)
    dx = amplitude * math.sin(phase * 1.371)
    dy = amplitude * math.cos(phase * 0.917)
    dz = amplitude * math.sin(phase * 0.531 + variant_rank)
    return f"{line[:30]}{x + dx:8.3f}{y + dy:8.3f}{z + dz:8.3f}{line[54:]}"


def _normalize_line(line: str) -> str:
    return line.rstrip(" \t\r\n") + "\n"


def _write_candidate_model(source_pdb: str, out_pdb: Path, amplitude: float, variant_rank: int) -> None:
    source = _resolve(source_pdb)
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    atom_index = 0
    lines: list[str] = []
    with source.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(("ATOM  ", "HETATM")):
                atom_index += 1
            lines.append(_normalize_line(_perturb_line(line, atom_index, amplitude, variant_rank)))
    out_pdb.write_text("".join(lines), encoding="utf-8")


def _merge_rows(operator_rows: list[dict[str, str]], seed_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seed_by_target = {_text(row.get("target_id")).upper(): row for row in seed_rows}
    merged_rows: list[dict[str, str]] = []
    for row in operator_rows:
        target_id = _text(row.get("target_id")).upper()
        merged = dict(seed_by_target.get(target_id, {}))
        merged.update(row)
        merged_rows.append(merged)
    return merged_rows


def _build_pool_for_row(row: dict[str, str], row_rank: int, pool_dir: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(row.get("target_id")).upper()
    benchmark_id = _text(row.get("benchmark_id"))
    scope = _text(row.get("scope"))
    selected_source = _text(row.get("prediction_pdb"))
    selected_stats = _pdb_stats(selected_source)
    target_dir = _resolve(pool_dir) / f"{row_rank:02d}_{_safe_name(target_id)}"
    candidate_csv = target_dir / "candidate_pool.csv"
    candidates: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not selected_stats["exists"] or not selected_stats["coordinate_valid"]:
        blockers.append("selected_source_pdb_missing_or_invalid")
    else:
        for index, amplitude in enumerate(AMPLITUDES, start=1):
            role = "selected_prediction_copy" if index == 1 else f"deterministic_perturbation_{index}"
            out_pdb = target_dir / f"model_{index}_{role}.pdb"
            _write_candidate_model(selected_source, out_pdb, amplitude, index)
            stats = _pdb_stats(out_pdb)
            candidates.append(
                {
                    "target_id": target_id,
                    "benchmark_id": benchmark_id,
                    "scope": scope,
                    "candidate_rank": index,
                    "role": role,
                    "path": _artifact(out_pdb),
                    "exists": bool(stats["exists"]),
                    "atom_count": _int(stats["atom_count"]),
                    "coordinate_valid": bool(stats["coordinate_valid"]),
                    "sha256_16": _text(stats["sha256_16"]),
                    "generation_method": "copy_selected" if index == 1 else "deterministic_coordinate_perturbation",
                    "source_path": _artifact(selected_source),
                    "amplitude_angstrom": f"{amplitude:.2f}",
                    "notes": "local top-5 review candidate; not an independent predictor output",
                }
            )
    complete_count = sum(1 for item in candidates if item["exists"] and item["coordinate_valid"])
    top5_ready = complete_count >= 5
    if not top5_ready:
        blockers.append("top5_candidate_pool_incomplete")
    status = "top5_candidate_pool_ready_for_review" if top5_ready else "blocked_selected_source_missing"
    _write_csv(candidate_csv, candidates, CANDIDATE_COLUMNS)
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "pool_status": status,
        "candidate_pool_csv": _artifact(candidate_csv),
        "candidate_pool_dir": _artifact(target_dir),
        "candidate_model_count": complete_count,
        "top5_candidate_pool_ready": top5_ready,
        "selected_source_pdb": _artifact(selected_source),
        "selected_source_present": bool(selected_stats["exists"] and selected_stats["coordinate_valid"]),
        "generated_perturbation_count": sum(
            1
            for item in candidates
            if item["exists"] and item["coordinate_valid"] and item["generation_method"] == "deterministic_coordinate_perturbation"
        ),
        "next_action": (
            "feed candidate pool into calibration ledger, then attach native oracle metrics and internal scores"
            if top5_ready
            else "provide a coordinate-valid selected prediction before generating top-5 candidates"
        ),
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    return summary_row, candidates


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_blockers = _read_csv(args.operator_clearance_csv)
    seed_rows, seed_blockers = _read_csv(args.seed_manifest_csv)
    rows: list[dict[str, Any]] = []
    candidate_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(_merge_rows(operator_rows, seed_rows), start=1):
        summary_row, candidates = _build_pool_for_row(row, index, args.pool_dir)
        rows.append(summary_row)
        candidate_rows_by_target[_text(summary_row.get("target_id"))] = candidates
    input_blockers = operator_blockers + seed_blockers
    complete_top5 = sum(1 for row in rows if row.get("top5_candidate_pool_ready") is True)
    blocked_source = sum(1 for row in rows if row.get("selected_source_present") is not True)
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_operator_rows"
    elif blocked_source:
        status = "blocked_selected_source_missing"
    else:
        status = "top5_candidate_pool_ready_for_review"
    first_open = next((row for row in rows if row.get("top5_candidate_pool_ready") is not True), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_historical_seed_top5_candidate_pools",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "top5_candidate_pool_status": status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "pool_dir": _artifact(args.pool_dir),
        "seed_row_count": len(rows),
        "pool_count": sum(1 for row in rows if _text(row.get("candidate_pool_csv"))),
        "candidate_model_count": sum(_int(row.get("candidate_model_count")) for row in rows),
        "complete_top5_pool_count": complete_top5,
        "candidate_pool_gap_count": len(rows) - complete_top5,
        "selected_source_present_count": sum(1 for row in rows if row.get("selected_source_present") is True),
        "generated_perturbation_count": sum(_int(row.get("generated_perturbation_count")) for row in rows),
        "blocked_selected_source_count": blocked_source,
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide seed operator rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "candidate_rows_by_target": candidate_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Top-5 Candidate Pools",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- top5_candidate_pool_status: `{summary['top5_candidate_pool_status']}`",
        f"- seed rows/pools/models: `{summary['seed_row_count']}/{summary['pool_count']}/{summary['candidate_model_count']}`",
        f"- complete/gap/source-present/source-blocked: `{summary['complete_top5_pool_count']}/{summary['candidate_pool_gap_count']}/{summary['selected_source_present_count']}/{summary['blocked_selected_source_count']}`",
        f"- generated perturbations: `{summary['generated_perturbation_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | candidates | top5 | perturbations | pool | blockers |",
        "| ---: | --- | --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['pool_status']}` | "
            f"{row['candidate_model_count']} | `{row['top5_candidate_pool_ready']}` | "
            f"{row['generated_perturbation_count']} | `{row['candidate_pool_csv']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_operator_rows` | 0 | - | 0 | - | provide operator CSV |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed top-5 candidate pools.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--pool-dir", default=DEFAULT_POOL_DIR)
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
