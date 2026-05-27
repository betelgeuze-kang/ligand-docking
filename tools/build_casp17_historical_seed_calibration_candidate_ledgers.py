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
DEFAULT_ABLATION_CANDIDATE_JSON = "casp17/casp17_historical_seed_ablation_candidate_manifests_current.json"
DEFAULT_TOP5_CANDIDATE_POOL_JSON = "casp17/casp17_historical_seed_top5_candidate_pools_current.json"
DEFAULT_LEDGER_DIR = "casp17/historical_seed_calibration_candidate_ledgers"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_calibration_candidate_ledgers_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_calibration_candidate_ledgers_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_CALIBRATION_CANDIDATE_LEDGERS.md"

CALIBRATION_FIELDS = [
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
]

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "ledger_status",
    "candidate_ledger_csv",
    "candidate_count",
    "top5_candidate_pool_ready",
    "selected_prediction_candidate_count",
    "native_oracle_metric_available_count",
    "internal_score_available_count",
    "selected_model_rank_candidate",
    "best_model_rank_candidate",
    "selected_native_metric_candidate",
    "best_native_metric_candidate",
    "selected_score_candidate",
    "best_score_candidate",
    "open_calibration_field_count",
    "open_calibration_fields",
    "next_action",
    "blockers",
]

LEDGER_COLUMNS = [
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
    "selected_model_rank_candidate",
    "internal_score_candidate",
    "native_metric_candidate",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed model-selection calibration candidate ledgers only. They enumerate existing "
    "local candidate models and calibration gaps for operator review. They do not compute oracle native metrics, "
    "choose best-of-5, fill selected/best score fields, clear leakage provenance, fetch native structures, run "
    "predictors, mutate operator CSVs, or submit to CASP."
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


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown_target"


def _ablation_rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = payload.get("manifest_rows_by_target")
    if isinstance(grouped, dict):
        return {
            _text(target).upper(): [row for row in rows if isinstance(row, dict)]
            for target, rows in grouped.items()
            if isinstance(rows, list)
        }
    return {}


def _top5_rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = payload.get("candidate_rows_by_target")
    if isinstance(grouped, dict):
        return {
            _text(target).upper(): [row for row in rows if isinstance(row, dict)]
            for target, rows in grouped.items()
            if isinstance(rows, list)
        }
    return {}


def _fallback_candidate_rows(row: dict[str, str]) -> list[dict[str, Any]]:
    prediction_pdb = _text(row.get("prediction_pdb"))
    stats = _pdb_stats(prediction_pdb)
    return [
        {
            "target_id": _text(row.get("target_id")).upper(),
            "benchmark_id": _text(row.get("benchmark_id")),
            "scope": _text(row.get("scope")),
            "role": "selected_prediction",
            "path": _artifact(prediction_pdb),
            "exists": bool(stats["exists"]),
            "atom_count": _int(stats["atom_count"]),
            "coordinate_valid": bool(stats["coordinate_valid"]),
            "sha256_16": _text(stats["sha256_16"]),
            "notes": "fallback from operator seed prediction_pdb",
        }
    ]


def _candidate_pool(
    row: dict[str, str],
    ablation_by_target: dict[str, list[dict[str, Any]]],
    top5_by_target: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    target_id = _text(row.get("target_id")).upper()
    raw_rows = list(ablation_by_target.get(target_id) or [])
    raw_rows.extend(top5_by_target.get(target_id) or [])
    if not raw_rows:
        raw_rows = _fallback_candidate_rows(row)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_selected_prediction_seen = False
    for raw in raw_rows:
        role = _text(raw.get("role"))
        if role == "native_reference":
            continue
        exists = raw.get("exists")
        exists_bool = exists if isinstance(exists, bool) else _text(exists).lower() == "true"
        coordinate_valid = raw.get("coordinate_valid")
        coordinate_bool = coordinate_valid if isinstance(coordinate_valid, bool) else _text(coordinate_valid).lower() == "true"
        if role == "selected_prediction_copy" and valid_selected_prediction_seen:
            continue
        path = _text(raw.get("path"))
        sha = _text(raw.get("sha256_16"))
        dedupe_key = sha or path
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        candidates.append(
            {
                "target_id": target_id,
                "benchmark_id": _text(row.get("benchmark_id")) or _text(raw.get("benchmark_id")),
                "scope": _text(row.get("scope")) or _text(raw.get("scope")),
                "candidate_rank": len(candidates) + 1,
                "role": role,
                "path": path,
                "exists": bool(exists_bool),
                "atom_count": _int(raw.get("atom_count")),
                "coordinate_valid": bool(coordinate_bool),
                "sha256_16": sha,
                "selected_model_rank_candidate": (
                    1
                    if role in {"selected_prediction", "selected_prediction_copy"} and exists_bool and coordinate_bool
                    else ""
                ),
                "internal_score_candidate": "",
                "native_metric_candidate": "",
                "notes": _text(raw.get("notes")) or "candidate model for model-selection review",
            }
        )
        if role == "selected_prediction" and exists_bool and coordinate_bool:
            valid_selected_prediction_seen = True
    return candidates


def _field_ready(row: dict[str, str], field: str) -> bool:
    text = _text(row.get(field))
    if not text or text.upper().startswith("REQUIRED"):
        return False
    if field in {"selected_model_rank", "best_model_rank"}:
        value = _int(text)
        return 1 <= value <= 5 and text == str(value)
    try:
        float(text)
    except ValueError:
        return False
    return True


def _build_seed_ledger(
    row: dict[str, str],
    ablation_by_target: dict[str, list[dict[str, Any]]],
    top5_by_target: dict[str, list[dict[str, Any]]],
    ledger_dir: str | Path,
    row_rank: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(row.get("target_id")).upper()
    candidates = _candidate_pool(row, ablation_by_target, top5_by_target)
    existing_candidates = [item for item in candidates if item["exists"] and item["coordinate_valid"]]
    selected_candidates = [
        item for item in existing_candidates if item["role"] in {"selected_prediction", "selected_prediction_copy"}
    ]
    top5_ready = len(existing_candidates) >= 5
    open_fields = [field for field in CALIBRATION_FIELDS if not _field_ready(row, field)]
    blockers: list[str] = []
    if not selected_candidates:
        blockers.append("selected_prediction_candidate_missing")
    if not top5_ready:
        blockers.append("best_of_5_candidate_pool_missing")
    blockers.append("native_oracle_metrics_required")
    blockers.append("internal_score_candidates_required")
    if open_fields:
        blockers.append("operator_calibration_fields_required")
    status = "operator_calibration_review_required"
    if not selected_candidates:
        status = "blocked_selected_prediction_missing"
    ledger_csv = _resolve(ledger_dir) / f"{row_rank:02d}_{_safe_name(target_id)}_calibration_candidates.csv"
    _write_csv(ledger_csv, candidates, LEDGER_COLUMNS)
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": _text(row.get("benchmark_id")),
        "scope": _text(row.get("scope")),
        "ledger_status": status,
        "candidate_ledger_csv": _artifact(ledger_csv),
        "candidate_count": len(existing_candidates),
        "top5_candidate_pool_ready": top5_ready,
        "selected_prediction_candidate_count": len(selected_candidates),
        "native_oracle_metric_available_count": sum(1 for item in candidates if _text(item.get("native_metric_candidate"))),
        "internal_score_available_count": sum(1 for item in candidates if _text(item.get("internal_score_candidate"))),
        "selected_model_rank_candidate": "1" if selected_candidates else "",
        "best_model_rank_candidate": "REQUIRES_NATIVE_ORACLE",
        "selected_native_metric_candidate": "REQUIRES_NATIVE_ORACLE",
        "best_native_metric_candidate": "REQUIRES_NATIVE_ORACLE",
        "selected_score_candidate": "REQUIRES_INTERNAL_SCORE",
        "best_score_candidate": "REQUIRES_INTERNAL_SCORE",
        "open_calibration_field_count": len(open_fields),
        "open_calibration_fields": ",".join(open_fields),
        "next_action": (
            "attach native oracle metrics and internal scores before filling calibration fields"
            if top5_ready
            else "attach top-5 candidate pool, internal scores, and native oracle metrics before filling calibration fields"
        ),
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    return summary_row, candidates


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_blockers = _read_csv(args.operator_clearance_csv)
    seed_rows, seed_blockers = _read_csv(args.seed_manifest_csv)
    ablation_payload = _read_json(args.ablation_candidate_json)
    top5_payload = _read_json(args.top5_candidate_pool_json)
    ablation_by_target = _ablation_rows_by_target(ablation_payload)
    top5_by_target = _top5_rows_by_target(top5_payload)
    seed_by_target = {_text(row.get("target_id")).upper(): row for row in seed_rows}
    rows: list[dict[str, Any]] = []
    candidate_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(operator_rows, start=1):
        target_id = _text(row.get("target_id")).upper()
        merged = dict(seed_by_target.get(target_id, {}))
        merged.update(row)
        report, candidates = _build_seed_ledger(merged, ablation_by_target, top5_by_target, args.ledger_dir, index)
        rows.append(report)
        candidate_rows_by_target[target_id] = candidates
    status_counts: dict[str, int] = {}
    for row in rows:
        status = _text(row.get("ledger_status"))
        status_counts[status] = status_counts.get(status, 0) + 1
    input_blockers = operator_blockers + seed_blockers
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_operator_rows"
    elif status_counts.get("blocked_selected_prediction_missing", 0):
        status = "blocked_selected_prediction_missing"
    else:
        status = "operator_calibration_review_required"
    first_open = next((row for row in rows if row["ledger_status"] != "ready_for_calibration_fill"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_historical_seed_calibration_candidate_ledgers",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "calibration_candidate_status": status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "ablation_candidate_json": _artifact(args.ablation_candidate_json),
        "top5_candidate_pool_json": _artifact(args.top5_candidate_pool_json),
        "ledger_dir": _artifact(args.ledger_dir),
        "seed_row_count": len(rows),
        "ledger_count": sum(1 for row in rows if _text(row.get("candidate_ledger_csv"))),
        "candidate_model_count": sum(_int(row.get("candidate_count")) for row in rows),
        "selected_prediction_candidate_count": sum(_int(row.get("selected_prediction_candidate_count")) for row in rows),
        "top5_candidate_pool_ready_count": sum(1 for row in rows if row.get("top5_candidate_pool_ready") is True),
        "candidate_pool_gap_count": sum(1 for row in rows if row.get("top5_candidate_pool_ready") is not True),
        "native_oracle_metric_available_count": sum(_int(row.get("native_oracle_metric_available_count")) for row in rows),
        "internal_score_available_count": sum(_int(row.get("internal_score_available_count")) for row in rows),
        "selected_model_rank_candidate_count": sum(1 for row in rows if _text(row.get("selected_model_rank_candidate")) == "1"),
        "operator_review_required_count": len(rows),
        "ready_for_calibration_fill_count": 0,
        "open_calibration_field_count": sum(_int(row.get("open_calibration_field_count")) for row in rows),
        "blocked_selected_prediction_count": status_counts.get("blocked_selected_prediction_missing", 0),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide seed operator rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "candidate_rows_by_target": candidate_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Calibration Candidate Ledgers",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- calibration_candidate_status: `{summary['calibration_candidate_status']}`",
        f"- seed rows/ledgers/candidate models: `{summary['seed_row_count']}/{summary['ledger_count']}/{summary['candidate_model_count']}`",
        f"- selected rank candidates/top5-ready/pool gaps: `{summary['selected_model_rank_candidate_count']}/{summary['top5_candidate_pool_ready_count']}/{summary['candidate_pool_gap_count']}`",
        f"- native oracle metrics/internal scores: `{summary['native_oracle_metric_available_count']}/{summary['internal_score_available_count']}`",
        f"- ready/operator-review/open fields: `{summary['ready_for_calibration_fill_count']}/{summary['operator_review_required_count']}/{summary['open_calibration_field_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | ledger | candidates | selected rank | top5 | native/internal | open fields | blockers |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['ledger_status']}` | "
            f"`{row['candidate_ledger_csv']}` | {row['candidate_count']} | "
            f"`{row['selected_model_rank_candidate'] or '-'}` | `{row['top5_candidate_pool_ready']}` | "
            f"`{row['native_oracle_metric_available_count']}/{row['internal_score_available_count']}` | "
            f"{row['open_calibration_field_count']} | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_operator_rows` | - | 0 | - | - | 0/0 | 0 | provide operator CSV |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed calibration candidate ledgers.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--ablation-candidate-json", default=DEFAULT_ABLATION_CANDIDATE_JSON)
    parser.add_argument("--top5-candidate-pool-json", default=DEFAULT_TOP5_CANDIDATE_POOL_JSON)
    parser.add_argument("--ledger-dir", default=DEFAULT_LEDGER_DIR)
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
