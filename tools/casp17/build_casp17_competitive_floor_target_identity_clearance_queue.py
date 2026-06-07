#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DISCOVERY_JSON = "casp17/casp17_competitive_floor_target_identity_discovery_packet_current.json"
DEFAULT_EXISTING_STRUCTURE_CHECKLIST_CSV = "runs/casp17_existing_structure_file_checklist_current.csv"
DEFAULT_EXISTING_STRUCTURE_PROVENANCE_CSV = "runs/casp17_existing_structure_provenance_current.csv"
DEFAULT_HISTORICAL_NATIVE_DIR = "runs/casp17_historical_benchmark_natives_current"
DEFAULT_EXISTING_STRUCTURE_DIR = "runs/casp17_existing_structures_current"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_queue_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_queue_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_QUEUE.md"

CLEAR_VALUES = {"cleared", "no_leak", "ready_for_row_fill", "internal_no_leak", "true", "yes"}
FALSE_VALUES = {"0", "false", "no", "n"}
CLEARANCE_COLUMNS = [
    "target_id",
    "target_name",
    "scope",
    "identity_discovery_status",
    "candidate_use_status",
    "identity_discovery_blockers",
    "identity_discovery_next_action",
    "prediction_status",
    "prediction_pdb",
    "ts_prediction_status",
    "ts_prediction_pdb",
    "native_status",
    "native_pdb",
    "provenance_status",
    "provenance_cleared",
    "clearance_status",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor target identity clearance queue only. It converts local target identity discoveries "
    "into operator clearance work items and checks local prediction/native/provenance files. It does not choose "
    "historical targets, clear no-leak provenance, fetch native structures, score native accuracy, mutate intake "
    "CSV files, or submit to CASP."
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
        return int(float(str(value).strip()))
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLEARANCE_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _by_target(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _existing_artifact(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = _resolve(text)
    return _artifact(path) if path.exists() else ""


def _first_existing(paths: list[str | Path]) -> str:
    for path in paths:
        artifact = _existing_artifact(path)
        if artifact:
            return artifact
    return ""


def _prediction_candidates(target_id: str, checklist_row: dict[str, str]) -> tuple[str, str]:
    raw_candidates = [
        f"runs/casp17_prediction_jobs_current/{target_id}/{target_id}_model_1.pdb",
        f"runs/casp17_prediction_jobs_quality_current/{target_id}/{target_id}_model_1.pdb",
        f"runs/casp17_prediction_jobs_recursive_current/{target_id}/{target_id}_model_1.pdb",
    ]
    ts_candidates = [
        _text(checklist_row.get("canonical_ts_path")),
        f"runs/casp17_predictions_current/{target_id}TS.pdb",
        f"runs/casp17_predictions_quality_current/{target_id}TS.pdb",
        f"runs/casp17_predictions_recursive_current/{target_id}TS.pdb",
    ]
    return _first_existing(raw_candidates), _first_existing(ts_candidates)


def _native_candidate(target_id: str, args: argparse.Namespace) -> str:
    native_roots = [_resolve(args.historical_native_dir), _resolve(args.existing_structure_dir)]
    for root in native_roots:
        if not root.exists():
            continue
        for pattern in [f"{target_id}*.pdb", f"{target_id.lower()}*.pdb"]:
            matches = sorted(root.glob(pattern))
            if matches:
                return _artifact(matches[0])
    return ""


def _scope_for_target(target_id: str, checklist_row: dict[str, str]) -> str:
    name = _text(checklist_row.get("target_name"))
    if "complex" in name.lower() or target_id.upper().startswith("H"):
        return "complex"
    return "monomer"


def _provenance_cleared(row: dict[str, str]) -> bool:
    status = _text(row.get("provenance_status")).lower()
    if status not in CLEAR_VALUES:
        return False
    for column in ["public_or_external_source_used", "other_team_structure_used", "post_release_structure_used"]:
        value = _text(row.get(column)).lower()
        if value not in FALSE_VALUES:
            return False
    return bool(_text(row.get("operator")))


def _blockers(prediction_pdb: str, ts_prediction_pdb: str, native_pdb: str, provenance_cleared: bool) -> list[str]:
    blockers: list[str] = []
    if not prediction_pdb and not ts_prediction_pdb:
        blockers.append("local_prediction_missing")
    if not native_pdb:
        blockers.append("native_pdb_missing")
    if not provenance_cleared:
        blockers.append("no_leak_provenance_not_cleared")
        blockers.append("operator_clearance_required")
    return blockers


def _clearance_status(blockers: list[str]) -> str:
    if not blockers:
        return "ready_for_manifest_scaffold_review"
    if "local_prediction_missing" in blockers:
        return "awaiting_prediction_or_ts"
    if "native_pdb_missing" in blockers:
        return "awaiting_native_or_clearance"
    return "awaiting_no_leak_clearance"


def _next_action(clearance_status: str) -> str:
    if clearance_status == "ready_for_manifest_scaffold_review":
        return "operator may copy this row into the historical manifest scaffold for final promotion checks"
    if clearance_status == "awaiting_prediction_or_ts":
        return "provide a local internal prediction PDB or CASP TS file before using this target"
    if clearance_status == "awaiting_native_or_clearance":
        return "provide a cleared native PDB and complete no-leak/operator provenance review"
    return "complete no-leak/operator provenance review before manifest promotion"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    discovery_payload = _read_json(args.discovery_json)
    discovery_summary = _summary(discovery_payload)
    checklist_by_target = _by_target(_read_csv(args.existing_structure_checklist_csv))
    provenance_by_target = _by_target(_read_csv(args.existing_structure_provenance_csv))
    rows: list[dict[str, Any]] = []
    for discovery in _rows(discovery_payload):
        if _text(discovery.get("candidate_use_status")) != "operator_review_required":
            continue
        target_id = _text(discovery.get("target_id")).upper()
        checklist_row = checklist_by_target.get(target_id, {})
        provenance_row = provenance_by_target.get(target_id, {})
        prediction_pdb, ts_prediction_pdb = _prediction_candidates(target_id, checklist_row)
        native_pdb = _native_candidate(target_id, args)
        provenance_cleared = _provenance_cleared(provenance_row)
        blockers = _blockers(prediction_pdb, ts_prediction_pdb, native_pdb, provenance_cleared)
        clearance_status = _clearance_status(blockers)
        rows.append(
            {
                "target_id": target_id,
                "target_name": _text(checklist_row.get("target_name")) or _text(discovery.get("description")),
                "scope": _scope_for_target(target_id, checklist_row),
                "identity_discovery_status": _text(discovery.get("identity_discovery_status")),
                "candidate_use_status": _text(discovery.get("candidate_use_status")),
                "identity_discovery_blockers": _text(discovery.get("blockers")),
                "identity_discovery_next_action": _text(discovery.get("next_action")),
                "prediction_status": "present" if prediction_pdb or ts_prediction_pdb else "missing",
                "prediction_pdb": prediction_pdb,
                "ts_prediction_status": "present" if ts_prediction_pdb else "missing",
                "ts_prediction_pdb": ts_prediction_pdb,
                "native_status": "present" if native_pdb else "missing",
                "native_pdb": native_pdb,
                "provenance_status": _text(provenance_row.get("provenance_status")) or "missing",
                "provenance_cleared": str(provenance_cleared).lower(),
                "clearance_status": clearance_status,
                "blockers": ",".join(blockers),
                "next_action": _next_action(clearance_status),
            }
        )
    by_status = Counter(_text(row.get("clearance_status")) for row in rows)
    first_open = next(
        (
            row
            for row in rows
            if _text(row.get("clearance_status")) != "ready_for_manifest_scaffold_review"
        ),
        rows[0] if rows else {},
    )
    ready_count = by_status["ready_for_manifest_scaffold_review"]
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_queue_status": "ready_for_manifest_scaffold_review"
        if rows and ready_count == len(rows)
        else ("awaiting_target_identity_clearance" if rows else "missing_target_identity_discovery"),
        "discovery_json": _artifact(args.discovery_json),
        "discovery_status": _text(discovery_summary.get("target_identity_discovery_status")),
        "existing_structure_checklist_csv": _artifact(args.existing_structure_checklist_csv),
        "existing_structure_provenance_csv": _artifact(args.existing_structure_provenance_csv),
        "review_target_count": len(rows),
        "prediction_present_count": sum(1 for row in rows if _text(row.get("prediction_status")) == "present"),
        "ts_prediction_present_count": sum(1 for row in rows if _text(row.get("ts_prediction_status")) == "present"),
        "native_present_count": sum(1 for row in rows if _text(row.get("native_status")) == "present"),
        "provenance_cleared_count": sum(1 for row in rows if _text(row.get("provenance_cleared")) == "true"),
        "identity_discovery_blocker_count": sum(1 for row in rows if _text(row.get("identity_discovery_blockers"))),
        "ready_for_manifest_scaffold_count": ready_count,
        "awaiting_prediction_or_ts_count": by_status["awaiting_prediction_or_ts"],
        "awaiting_native_or_clearance_count": by_status["awaiting_native_or_clearance"],
        "awaiting_no_leak_clearance_count": by_status["awaiting_no_leak_clearance"],
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_status": _text(first_open.get("clearance_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_queue_status: `{summary['clearance_queue_status']}`",
        f"- discovery_status: `{summary['discovery_status'] or '-'}`",
        f"- review targets: `{summary['review_target_count']}`",
        f"- prediction/TS/native/provenance-cleared: `{summary['prediction_present_count']}/{summary['ts_prediction_present_count']}/{summary['native_present_count']}/{summary['provenance_cleared_count']}`",
        f"- identity discovery blockers: `{summary['identity_discovery_blocker_count']}`",
        f"- ready for manifest scaffold: `{summary['ready_for_manifest_scaffold_count']}`",
        f"- awaiting prediction/native-or-clearance/no-leak: `{summary['awaiting_prediction_or_ts_count']}/{summary['awaiting_native_or_clearance_count']}/{summary['awaiting_no_leak_clearance_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Queue",
        "",
        "| target | scope | clearance | identity blockers | prediction | TS | native | provenance | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['scope']}` | `{row['clearance_status']}` | "
            f"`{row['identity_discovery_blockers'] or '-'}` | "
            f"`{row['prediction_status']}` | `{row['ts_prediction_status']}` | `{row['native_status']}` | "
            f"`{row['provenance_status']}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `missing_target_identity_discovery` | - | - | - | - | - | `review_targets_missing` | rerun target identity discovery |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 target identity no-leak clearance queue.")
    parser.add_argument("--discovery-json", default=DEFAULT_DISCOVERY_JSON)
    parser.add_argument("--existing-structure-checklist-csv", default=DEFAULT_EXISTING_STRUCTURE_CHECKLIST_CSV)
    parser.add_argument("--existing-structure-provenance-csv", default=DEFAULT_EXISTING_STRUCTURE_PROVENANCE_CSV)
    parser.add_argument("--historical-native-dir", default=DEFAULT_HISTORICAL_NATIVE_DIR)
    parser.add_argument("--existing-structure-dir", default=DEFAULT_EXISTING_STRUCTURE_DIR)
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
