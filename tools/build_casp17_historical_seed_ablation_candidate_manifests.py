#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_MANIFEST_DIR = "casp17/historical_seed_ablation_candidate_manifests"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_ablation_candidate_manifests_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_ablation_candidate_manifests_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_ABLATION_CANDIDATE_MANIFESTS.md"

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "candidate_manifest_status",
    "candidate_manifest_csv",
    "selected_prediction_present",
    "native_reference_present",
    "baseline_candidate_count",
    "candidate_row_count",
    "sha256_16_set",
    "next_action",
    "blockers",
]

MANIFEST_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "role",
    "path",
    "exists",
    "atom_count",
    "coordinate_valid",
    "sha256_16",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed ablation candidate manifests only. These files fingerprint existing local "
    "prediction/native paths and obvious same-run candidate layers for operator review. They do not fill "
    "ablation_manifest_ref, prove ablation coverage, clear no-leak provenance, score native accuracy, mutate "
    "operator CSVs, fetch native structures, run predictors, or submit to CASP."
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
    coordinate_valid = True
    atom_count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
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


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown_target"


def _candidate_layer_paths(prediction_pdb: str, native_pdb: str) -> list[tuple[str, Path, str]]:
    prediction = _resolve(prediction_pdb)
    native = _resolve(native_pdb)
    candidates: list[tuple[str, Path, str]] = []
    seen = {prediction.resolve() if prediction.exists() else prediction, native.resolve() if native.exists() else native}

    name = prediction.name
    if "step00020" in name:
        for replacement in ("step00010", "step00000"):
            candidate = prediction.with_name(name.replace("step00020", replacement))
            key = candidate.resolve() if candidate.exists() else candidate
            if key not in seen:
                candidates.append(("same_run_step_candidate", candidate, f"derived from {name} via {replacement}"))
                seen.add(key)

    if name.endswith("_minimized.pdb"):
        candidate = prediction.with_name(name.replace("_minimized.pdb", ".pdb"))
        key = candidate.resolve() if candidate.exists() else candidate
        if key not in seen:
            candidates.append(("pre_minimization_candidate", candidate, "same folder pre-minimization candidate"))
            seen.add(key)

    return candidates


def _manifest_row(target_id: str, benchmark_id: str, scope: str, role: str, path_like: str | Path, notes: str) -> dict[str, Any]:
    stats = _pdb_stats(path_like)
    return {
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "role": role,
        "path": _artifact(path_like),
        "exists": bool(stats["exists"]),
        "atom_count": _int(stats["atom_count"]),
        "coordinate_valid": bool(stats["coordinate_valid"]),
        "sha256_16": _text(stats["sha256_16"]),
        "notes": notes,
    }


def _build_seed_manifest(row: dict[str, str], manifest_dir: str | Path, row_rank: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(row.get("target_id")).upper()
    benchmark_id = _text(row.get("benchmark_id"))
    scope = _text(row.get("scope"))
    prediction_pdb = _text(row.get("prediction_pdb"))
    native_pdb = _text(row.get("native_pdb"))
    manifest_rows = [
        _manifest_row(target_id, benchmark_id, scope, "selected_prediction", prediction_pdb, "operator seed selected prediction"),
        _manifest_row(target_id, benchmark_id, scope, "native_reference", native_pdb, "reference path only; not an ablation layer"),
    ]
    for role, candidate_path, notes in _candidate_layer_paths(prediction_pdb, native_pdb):
        manifest_rows.append(_manifest_row(target_id, benchmark_id, scope, role, candidate_path, notes))

    selected_present = bool(manifest_rows[0]["exists"] and manifest_rows[0]["coordinate_valid"])
    native_present = bool(manifest_rows[1]["exists"] and manifest_rows[1]["coordinate_valid"])
    baseline_rows = [
        item
        for item in manifest_rows[2:]
        if item["exists"] and item["coordinate_valid"] and _text(item["sha256_16"])
    ]
    blockers: list[str] = []
    if not selected_present:
        blockers.append("selected_prediction_missing_or_invalid")
    if not native_present:
        blockers.append("native_reference_missing_or_invalid")
    if not baseline_rows:
        blockers.append("ablation_layer_evidence_missing")
    blockers.append("operator_ablation_review_required")
    status = "operator_ablation_review_required"
    if not selected_present or not native_present:
        status = "blocked_core_candidate_inputs"
    elif not baseline_rows:
        status = "operator_ablation_layer_evidence_missing"
    manifest_csv = _resolve(manifest_dir) / f"{row_rank:02d}_{_safe_name(target_id)}_ablation_candidates.csv"
    _write_csv(manifest_csv, manifest_rows, MANIFEST_COLUMNS)
    sha_set = sorted({_text(item["sha256_16"]) for item in manifest_rows if _text(item["sha256_16"])})
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "candidate_manifest_status": status,
        "candidate_manifest_csv": _artifact(manifest_csv),
        "selected_prediction_present": selected_present,
        "native_reference_present": native_present,
        "baseline_candidate_count": len(baseline_rows),
        "candidate_row_count": len(manifest_rows),
        "sha256_16_set": ",".join(sha_set),
        "next_action": "attach real ablation layer evidence before setting ablation_manifest_ref",
        "blockers": ",".join(blockers),
    }
    return summary_row, manifest_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_blockers = _read_csv(args.operator_clearance_csv)
    seed_rows, seed_blockers = _read_csv(args.seed_manifest_csv)
    seed_by_target = {_text(row.get("target_id")).upper(): row for row in seed_rows}
    rows: list[dict[str, Any]] = []
    manifest_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(operator_rows, start=1):
        target_id = _text(row.get("target_id")).upper()
        merged = dict(seed_by_target.get(target_id, {}))
        merged.update(row)
        summary_row, manifest_rows = _build_seed_manifest(merged, args.manifest_dir, index)
        rows.append(summary_row)
        manifest_rows_by_target[target_id] = manifest_rows

    status_counts: dict[str, int] = {}
    for row in rows:
        status = _text(row.get("candidate_manifest_status"))
        status_counts[status] = status_counts.get(status, 0) + 1
    input_blockers = operator_blockers + seed_blockers
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_operator_rows"
    elif status_counts.get("blocked_core_candidate_inputs", 0):
        status = "blocked_core_candidate_inputs"
    else:
        status = "operator_ablation_review_required"
    first_open = next(
        (
            row
            for row in rows
            if _text(row.get("candidate_manifest_status")) != "ready_for_operator_reference"
        ),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_historical_seed_ablation_candidate_manifests",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "ablation_candidate_status": status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "manifest_dir": _artifact(args.manifest_dir),
        "seed_row_count": len(rows),
        "candidate_manifest_count": sum(1 for row in rows if _text(row.get("candidate_manifest_csv"))),
        "candidate_row_count": sum(_int(row.get("candidate_row_count")) for row in rows),
        "selected_prediction_present_count": sum(1 for row in rows if row.get("selected_prediction_present")),
        "native_reference_present_count": sum(1 for row in rows if row.get("native_reference_present")),
        "baseline_candidate_present_count": sum(_int(row.get("baseline_candidate_count")) for row in rows),
        "operator_review_required_count": len(rows),
        "ready_for_operator_reference_count": 0,
        "layer_evidence_gap_count": sum(
            1 for row in rows if "ablation_layer_evidence_missing" in _text(row.get("blockers")).split(",")
        ),
        "blocked_core_candidate_input_count": status_counts.get("blocked_core_candidate_inputs", 0),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide seed operator rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "manifest_rows_by_target": manifest_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Ablation Candidate Manifests",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- ablation_candidate_status: `{summary['ablation_candidate_status']}`",
        f"- seed rows/manifests/candidate rows: `{summary['seed_row_count']}/{summary['candidate_manifest_count']}/{summary['candidate_row_count']}`",
        f"- selected prediction/native present: `{summary['selected_prediction_present_count']}/{summary['native_reference_present_count']}`",
        f"- baseline candidates/layer gaps: `{summary['baseline_candidate_present_count']}/{summary['layer_evidence_gap_count']}`",
        f"- ready/operator-review/core-blocked: `{summary['ready_for_operator_reference_count']}/{summary['operator_review_required_count']}/{summary['blocked_core_candidate_input_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | manifest | selected/native | baseline candidates | next action | blockers |",
        "| ---: | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['candidate_manifest_status']}` | `{row['candidate_manifest_csv']}` | "
            f"`{row['selected_prediction_present']}`/`{row['native_reference_present']}` | "
            f"{row['baseline_candidate_count']} | {row['next_action']} | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_operator_rows` | - | - | 0 | provide operator CSV | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed ablation candidate manifests.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)
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
