#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_REPAIR_JSON = "casp17/casp17_competitive_floor_identity_source_repair_plan_current.json"
DEFAULT_TARGET_WATCHLIST_CSV = "runs/casp17_target_watchlist_current.csv"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_RUNS_ROOT = "runs"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_discovery_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_discovery_packet_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_DISCOVERY_PACKET.md"

TARGET_RE = re.compile(r"\b[HT]\d{4}\b", re.IGNORECASE)
SYNTHETIC_TEST_TARGET_IDS = {"T8200", "T8201", "T8202"}
SCAN_GLOBS = [
    "casp17_validations*_current/*confidence_calibration.json",
    "casp17_internal_physics_raw_validations*_current/*confidence_calibration.json",
    "casp17_internal_scorecards*_current/*internal_scorecard.json",
]
DISCOVERY_COLUMNS = [
    "target_id",
    "identity_discovery_status",
    "watchlist_status",
    "open_flag",
    "deadline_class",
    "description",
    "evidence_artifact_count",
    "first_evidence_artifact",
    "evidence_packet_types",
    "candidate_use_status",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local target-identity discovery only. It scans existing local validation/scorecard artifacts for target IDs "
    "and cross-checks them against the current CASP17 watchlist and current target folders. It does not choose "
    "historical targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, "
    "edit intake/operator templates, or submit to CASP."
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


def _bool_text(value: Any) -> str:
    text = _text(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return "true"
    if text in {"false", "0", "no", "n"}:
        return "false"
    return ""


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
    return rows, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISCOVERY_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _watchlist(path_like: str | Path) -> dict[str, dict[str, str]]:
    rows, blockers = _read_csv(path_like)
    if blockers:
        return {}
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _current_targets(path_like: str | Path) -> set[str]:
    rows, blockers = _read_csv(path_like)
    if blockers:
        return set()
    return {_text(row.get("target_id")).upper() for row in rows if _text(row.get("target_id"))}


def _target_id_from_payload(path: Path, payload: dict[str, Any]) -> str:
    summary = _summary(payload)
    target_id = _text(summary.get("target_id") or payload.get("target_id")).upper()
    if target_id:
        return target_id
    match = TARGET_RE.search(path.name)
    return match.group(0).upper() if match else ""


def _evidence_status(payload: dict[str, Any]) -> str:
    summary = _summary(payload)
    for key in [
        "confidence_calibration_status",
        "scorecard_status",
        "internal_scorecard_status",
        "prediction_validation_status",
    ]:
        status = _text(summary.get(key) or payload.get(key))
        if status:
            return status
    return _text(summary.get("packet_type") or payload.get("packet_type")) or "present"


def _scan_evidence(args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    runs_root = _resolve(args.runs_root)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pattern in SCAN_GLOBS:
        for path in sorted(runs_root.glob(pattern)):
            payload = _read_json(path)
            target_id = _target_id_from_payload(path, payload)
            if not target_id:
                continue
            grouped[target_id].append(
                {
                    "artifact": _artifact(path),
                    "status": _evidence_status(payload),
                    "packet_type": _text(_summary(payload).get("packet_type") or payload.get("packet_type")),
                }
            )
    return grouped


def _watchlist_status(target_id: str, watch: dict[str, dict[str, str]], current_targets: set[str]) -> str:
    row = watch.get(target_id, {})
    if target_id in SYNTHETIC_TEST_TARGET_IDS:
        return "synthetic_test_artifact"
    if target_id in current_targets:
        return "current_target_folder"
    if not row:
        return "not_in_watchlist"
    is_open = any(_bool_text(row.get(column)) == "true" for column in ["server_open", "human_open", "qa_open"])
    return "open_casp17_watchlist" if is_open else "closed_casp17_watchlist"


def _identity_discovery_status(watch_status: str) -> str:
    if watch_status == "synthetic_test_artifact":
        return "synthetic_test_artifact"
    if watch_status in {"current_target_folder", "open_casp17_watchlist"}:
        return "open_current_target"
    if watch_status == "closed_casp17_watchlist":
        return "closed_casp17_watchlist"
    if watch_status == "not_in_watchlist":
        return "unknown_local_target"
    return "unknown_local_target"


def _candidate_use_status(identity_discovery_status: str) -> str:
    if identity_discovery_status == "open_current_target":
        return "blocked_current_casp17_target"
    if identity_discovery_status == "synthetic_test_artifact":
        return "blocked_synthetic_test_artifact"
    return "operator_review_required"


def _blockers(identity_discovery_status: str) -> str:
    if identity_discovery_status == "open_current_target":
        return "current_casp17_target_not_historical_evidence"
    if identity_discovery_status == "closed_casp17_watchlist":
        return "no_leak_clearance_required"
    if identity_discovery_status == "synthetic_test_artifact":
        return "synthetic_test_artifact"
    return "target_origin_review_required"


def _next_action(identity_discovery_status: str) -> str:
    if identity_discovery_status == "open_current_target":
        return "do not use this current CASP17 target for historical identity intake"
    if identity_discovery_status == "closed_casp17_watchlist":
        return "operator must confirm historical eligibility, native availability, and no-leak clearance"
    if identity_discovery_status == "synthetic_test_artifact":
        return "exclude this synthetic unit-test target from target identity intake"
    return "verify target origin, native availability, and no-leak provenance before using it"


def _open_flag(watch_status: str, watch_row: dict[str, str]) -> str:
    if watch_status in {"current_target_folder", "open_casp17_watchlist"}:
        return "true"
    if watch_status == "closed_casp17_watchlist":
        return "false"
    return ""


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    repair_summary = _summary(_read_json(args.source_repair_json))
    watch = _watchlist(args.target_watchlist_csv)
    current_targets = _current_targets(args.current_target_csv)
    evidence = _scan_evidence(args)
    rows: list[dict[str, Any]] = []
    for target_id in sorted(evidence):
        entries = evidence[target_id]
        watch_status = _watchlist_status(target_id, watch, current_targets)
        identity_discovery_status = _identity_discovery_status(watch_status)
        watch_row = watch.get(target_id, {})
        first = entries[0] if entries else {}
        packet_types = sorted({_text(entry.get("packet_type")) for entry in entries if _text(entry.get("packet_type"))})
        rows.append(
            {
                "target_id": target_id,
                "identity_discovery_status": identity_discovery_status,
                "watchlist_status": watch_status,
                "open_flag": _open_flag(watch_status, watch_row),
                "deadline_class": _text(watch_row.get("deadline_class")),
                "description": _text(watch_row.get("description")),
                "evidence_artifact_count": len(entries),
                "first_evidence_artifact": _text(first.get("artifact")),
                "evidence_packet_types": ";".join(packet_types) or "present",
                "candidate_use_status": _candidate_use_status(identity_discovery_status),
                "blockers": _blockers(identity_discovery_status),
                "next_action": _next_action(identity_discovery_status),
            }
        )
    by_status = Counter(_text(row.get("identity_discovery_status")) for row in rows)
    by_candidate_status = Counter(_text(row.get("candidate_use_status")) for row in rows)
    first_review = next(
        (
            row
            for row in rows
            if _text(row.get("candidate_use_status")) == "operator_review_required"
        ),
        rows[0] if rows else {},
    )
    if not rows:
        target_identity_discovery_status = "missing"
    elif by_candidate_status["operator_review_required"]:
        target_identity_discovery_status = "review_required"
    else:
        target_identity_discovery_status = "blocked_current_targets_only"
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_discovery",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_identity_discovery_status": target_identity_discovery_status,
        "source_repair_json": _artifact(args.source_repair_json),
        "source_repair_status": _text(repair_summary.get("source_repair_status")),
        "source_repair_target_identity_action_count": _int(repair_summary.get("target_identity_action_count")),
        "target_watchlist_csv": _artifact(args.target_watchlist_csv),
        "current_target_csv": _artifact(args.current_target_csv),
        "runs_root": _artifact(args.runs_root),
        "discovered_target_count": len(rows),
        "open_current_target_count": by_status["open_current_target"],
        "closed_watchlist_target_count": by_status["closed_casp17_watchlist"],
        "unknown_local_target_count": by_status["unknown_local_target"],
        "synthetic_test_artifact_count": by_status["synthetic_test_artifact"],
        "operator_review_target_count": by_candidate_status["operator_review_required"],
        "ready_for_identity_intake_count": 0,
        "first_open_target_id": _text(first_review.get("target_id")),
        "first_open_status": _text(first_review.get("identity_discovery_status")),
        "first_open_next_action": _text(first_review.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Discovery",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target_identity_discovery_status: `{summary['target_identity_discovery_status']}`",
        f"- source_repair_status: `{summary['source_repair_status'] or '-'}`",
        f"- source target-identity repair actions: `{summary['source_repair_target_identity_action_count']}`",
        f"- discovered targets: `{summary['discovered_target_count']}`",
        f"- current / closed-watchlist / unknown / synthetic: `{summary['open_current_target_count']}/{summary['closed_watchlist_target_count']}/{summary['unknown_local_target_count']}/{summary['synthetic_test_artifact_count']}`",
        f"- operator review target count: `{summary['operator_review_target_count']}`",
        f"- ready for identity intake: `{summary['ready_for_identity_intake_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Discovered Targets",
        "",
        "| target | identity status | candidate use | watchlist | evidence | first artifact | blockers | action |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['identity_discovery_status']}` | `{row['candidate_use_status']}` | `{row['watchlist_status']}` | "
            f"{row['evidence_artifact_count']} | `{row['first_evidence_artifact'] or '-'}` | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `missing` | `blocked` | - | 0 | - | `local_evidence_missing` | add local candidate evidence |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover local target IDs for CASP17 identity intake review.")
    parser.add_argument("--source-repair-json", default=DEFAULT_SOURCE_REPAIR_JSON)
    parser.add_argument("--target-watchlist-csv", default=DEFAULT_TARGET_WATCHLIST_CSV)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--runs-root", default=DEFAULT_RUNS_ROOT)
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
