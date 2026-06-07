#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv"
DEFAULT_WORKORDER_JSON = "runs/casp17_sidechain_native_input_workorder_current.json"
DEFAULT_TARGET_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_OUT_MANIFEST_CSV = "runs/casp17_sidechain_native_manifest_candidate_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_sidechain_native_manifest_sync_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_sidechain_native_manifest_sync_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_sidechain_native_manifest_sync_packet_current.md"

CORE_COLUMNS = ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"]
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
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}


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


def _json_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_manifest(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], ["manifest_csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    missing = [column for column in CORE_COLUMNS if column not in fieldnames]
    if missing:
        blockers.append(f"required_columns_missing:{','.join(missing)}")
    if not rows:
        blockers.append("manifest_csv_empty")
    return rows, fieldnames, blockers


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
        resolved = ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text or "YYYY-MM-DD" in text.upper() or text.upper().startswith("REQUIRED_"):
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or text.upper().startswith("REQUIRED_") or "YYYY-MM-DD" in text.upper()


def _atom_record_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line[:6].strip().upper() == "ATOM":
            count += 1
    return count


def _current_open_targets(watchlist: dict[str, Any]) -> set[str]:
    current: set[str] = set()
    for row in _json_rows(watchlist):
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True:
            current.add(target_id)
    return current


def _normalized_manifest_row(row: dict[str, str], fieldnames: list[str]) -> dict[str, Any]:
    normalized = {key: _text(row.get(key)) for key in fieldnames if key}
    normalized.update(
        {
            "benchmark_id": _text(row.get("benchmark_id")),
            "target_id": _text(row.get("target_id")).upper(),
            "scope": _text(row.get("scope")).lower(),
            "split": _text(row.get("split")) or "historical",
            "prediction_pdb": _artifact(row.get("prediction_pdb", "")) if _text(row.get("prediction_pdb")) else "",
            "native_pdb": _artifact(row.get("native_pdb", "")) if _text(row.get("native_pdb")) else "",
            "leakage_clearance": _text(row.get("leakage_clearance")),
        }
    )
    return normalized


def _evaluate_provenance(row: dict[str, Any], blockers: list[str]) -> None:
    if _text(row.get("leakage_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if _is_placeholder(row.get("prediction_method")):
        blockers.append("prediction_method_required")
    prediction_created_at = _date_or_none(row.get("prediction_created_at"))
    native_release_date = _date_or_none(row.get("native_release_date"))
    if prediction_created_at is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_release_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_created_at is not None and native_release_date is not None and prediction_created_at >= native_release_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    if _text(row.get("operator_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("operator_clearance_required")


def _evaluate_row(row: dict[str, str], fieldnames: list[str], current_targets: set[str]) -> dict[str, Any]:
    evaluated = _normalized_manifest_row(row, fieldnames)
    blockers: list[str] = []
    target_id = _text(evaluated.get("target_id")).upper()
    scope = _text(evaluated.get("scope")).lower()
    prediction = _text(evaluated.get("prediction_pdb"))
    native = _text(evaluated.get("native_pdb"))

    if not _text(evaluated.get("benchmark_id")):
        blockers.append("benchmark_id_missing")
    if not target_id:
        blockers.append("target_id_missing")
    if target_id.startswith("REQUIRED_"):
        blockers.append("placeholder_target_id")
    if target_id in current_targets:
        blockers.append("current_casp17_target_not_allowed_for_historical_benchmark")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    if not prediction:
        blockers.append("prediction_pdb_missing")
    elif not _resolve(prediction).exists():
        blockers.append("prediction_pdb_not_found")
    elif _atom_record_count(prediction) == 0:
        blockers.append("prediction_pdb_has_no_atom_records")
    if not native:
        blockers.append("native_pdb_missing")
    elif not _resolve(native).exists():
        blockers.append("native_pdb_not_found")
    elif _atom_record_count(native) == 0:
        blockers.append("native_pdb_has_no_atom_records")
    if prediction and native and _resolve(prediction).resolve() == _resolve(native).resolve():
        blockers.append("prediction_native_same_file")
    _evaluate_provenance(evaluated, blockers)

    evaluated["prediction_atom_record_count"] = _atom_record_count(prediction) if prediction else 0
    evaluated["native_atom_record_count"] = _atom_record_count(native) if native else 0
    evaluated["sync_status"] = "ready_for_sidechain_native_scoring" if not blockers else "blocked"
    evaluated["blockers"] = ",".join(sorted(set(blockers)))
    return evaluated


def _blocker_histogram(rows: list[dict[str, Any]], manifest_blockers: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for blocker in manifest_blockers:
        counts[blocker] = counts.get(blocker, 0) + 1
    for row in rows:
        for blocker in str(row.get("blockers", "")).split(","):
            blocker = blocker.strip()
            if blocker:
                counts[blocker] = counts.get(blocker, 0) + 1
    return dict(sorted(counts.items()))


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    manifest_rows, fieldnames, manifest_blockers = _read_manifest(args.manifest_csv)
    current_targets = _current_open_targets(_read_json(args.target_watchlist_json))
    workorder_payload = _read_json(args.workorder_json)
    workorder_summary = _summary(workorder_payload)
    workorder_rows = _json_rows(workorder_payload)

    rows = [_evaluate_row(row, fieldnames, current_targets) for row in manifest_rows] if not manifest_blockers else []
    ready_rows = [row for row in rows if row["sync_status"] == "ready_for_sidechain_native_scoring"]
    blocked_rows = [row for row in rows if row["sync_status"] != "ready_for_sidechain_native_scoring"]
    ready_monomer = sum(1 for row in ready_rows if row.get("scope") == "monomer")
    ready_complex = sum(1 for row in ready_rows if row.get("scope") == "complex")
    threshold_blockers: list[str] = []
    if len(ready_rows) < int(args.min_ready_total):
        threshold_blockers.append("ready_total_below_threshold")
    if ready_monomer < int(args.min_ready_monomer):
        threshold_blockers.append("ready_monomer_below_threshold")
    if ready_complex < int(args.min_ready_complex):
        threshold_blockers.append("ready_complex_below_threshold")

    first_blocked = blocked_rows[0] if blocked_rows else {}
    if manifest_blockers:
        sync_status = "blocked"
    elif not rows:
        sync_status = "blocked"
    elif blocked_rows or threshold_blockers:
        sync_status = "blocked"
    else:
        sync_status = "ready_for_sidechain_native_scoring"

    candidate_fieldnames = list(fieldnames)
    for column in CORE_COLUMNS + PROVENANCE_COLUMNS:
        if column not in candidate_fieldnames:
            candidate_fieldnames.append(column)
    _write_csv(args.out_manifest_csv, ready_rows, fieldnames=candidate_fieldnames)

    open_workorder_rows = [row for row in workorder_rows if _text(row.get("action_status")).lower() != "closed"]
    first_workorder = open_workorder_rows[0] if open_workorder_rows else {}
    summary = {
        "packet_type": "casp17_sidechain_native_manifest_sync_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sync_status": sync_status,
        "manifest_csv": _artifact(args.manifest_csv),
        "workorder_json": _artifact(args.workorder_json),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "candidate_manifest_csv": _artifact(args.out_manifest_csv),
        "source_row_count": len(manifest_rows),
        "ready_row_count": len(ready_rows),
        "blocked_row_count": len(blocked_rows),
        "ready_monomer_count": ready_monomer,
        "ready_complex_count": ready_complex,
        "min_ready_total": int(args.min_ready_total),
        "min_ready_monomer": int(args.min_ready_monomer),
        "min_ready_complex": int(args.min_ready_complex),
        "current_target_exclusion_count": len(current_targets),
        "manifest_blockers": ",".join(manifest_blockers),
        "threshold_blockers": ",".join(threshold_blockers),
        "blocker_histogram": _blocker_histogram(rows, manifest_blockers),
        "first_blocked_benchmark_id": _text(first_blocked.get("benchmark_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_blockers": _text(first_blocked.get("blockers")),
        "workorder_status": _text(workorder_summary.get("sidechain_native_benchmark_status")),
        "workorder_action_count": int(workorder_summary.get("workorder_action_count") or len(workorder_rows)),
        "workorder_open_action_count": int(
            workorder_summary.get("open_workorder_action_count") or len(open_workorder_rows)
        ),
        "first_open_workorder_action_id": _text(first_workorder.get("action_id")),
        "first_open_workorder_next_action": _text(first_workorder.get("next_action")),
        "claim_boundary": (
            "Local sidechain-native manifest sync only. It validates existing operator-filled manifest rows and writes "
            "ready candidate rows; it does not fetch natives, infer provenance, score sidechain accuracy, overwrite "
            "the active manifest, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows, "candidate_manifest_rows": ready_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Sidechain-Native Manifest Sync Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- sync_status: `{summary['sync_status']}`",
        f"- source/ready/blocked rows: `{summary['source_row_count']}/{summary['ready_row_count']}/{summary['blocked_row_count']}`",
        f"- ready monomer/complex: `{summary['ready_monomer_count']}/{summary['ready_complex_count']}`",
        f"- thresholds total/monomer/complex: `{summary['min_ready_total']}/{summary['min_ready_monomer']}/{summary['min_ready_complex']}`",
        f"- threshold_blockers: `{summary['threshold_blockers'] or '-'}`",
        f"- manifest_blockers: `{summary['manifest_blockers'] or '-'}`",
        f"- candidate_manifest_csv: `{summary['candidate_manifest_csv']}`",
        f"- workorder open/action: `{summary['workorder_open_action_count']}/{summary['workorder_action_count']}`",
        f"- first_workorder_action: `{summary['first_open_workorder_action_id'] or '-'}` {summary['first_open_workorder_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| benchmark | target | scope | sync | pred atoms | native atoms | blockers |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['benchmark_id'] or '-'}` | `{row['target_id'] or '-'}` | `{row['scope'] or '-'}` | "
            f"`{row['sync_status']}` | {row['prediction_atom_record_count']} | {row['native_atom_record_count']} | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked` | 0 | 0 | `manifest_rows_missing` |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and materialize ready CASP17 sidechain-native manifest rows.")
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--target-watchlist-json", default=DEFAULT_TARGET_WATCHLIST_JSON)
    parser.add_argument("--min-ready-total", type=int, default=40)
    parser.add_argument("--min-ready-monomer", type=int, default=25)
    parser.add_argument("--min-ready-complex", type=int, default=15)
    parser.add_argument("--out-manifest-csv", default=DEFAULT_OUT_MANIFEST_CSV)
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
    if payload["summary"]["sync_status"] != "ready_for_sidechain_native_scoring":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
