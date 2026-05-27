#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPLACEMENT_QUEUE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_queue_current.json"
)
DEFAULT_REPLACEMENT_WORKORDER_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_current.json"
)
DEFAULT_REPLACEMENT_SOURCE_REPAIR_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.json"
)
DEFAULT_OUT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_duplicate_resolution_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_duplicate_resolution_current.csv"
)
DEFAULT_OUT_MD = (
    "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DUPLICATE_RESOLUTION.md"
)

READY_STATUS = "candidate_ready_for_operator_clearance"
SOURCE_READY_STATUS = "source_ready"
DUPLICATE_STATUS = "blocked_duplicate_candidate_assignment"
NO_SAFE_UNIQUE_ACTION = (
    "choose a new non-colliding closed protein replacement target or explicitly approve duplicate candidate reuse "
    "with no-leak rationale"
)
CLAIM_BOUNDARY = (
    "Local CASP17 replacement duplicate-resolution packet only. It audits duplicate replacement workorder blockers "
    "against the replacement queue and source-repair packet, identifies whether a safe unique ready candidate exists, "
    "and leaves unsafe duplicate reuse fail-closed. It does not mutate replacement workorders, fetch native structures, "
    "clear no-leak provenance, score native accuracy, import rows into identity intake, or submit to CASP."
)

DUPLICATE_RESOLUTION_COLUMNS = [
    "replace_target_id",
    "replace_target_name",
    "candidate_rank",
    "candidate_target_id",
    "candidate_target_name",
    "queue_candidate_status",
    "source_repair_status",
    "resolution_status",
    "safe_unique_ready_candidate",
    "duplicate_candidate",
    "duplicate_candidate_for_replace_target_ids",
    "prediction_pdb",
    "ts_prediction_pdb",
    "raw_validation_json",
    "scorecard_json",
    "current_target_collision_ids",
    "cancellation_date",
    "blockers",
    "next_action",
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=DUPLICATE_RESOLUTION_COLUMNS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _split_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    for chunk in _text(value).replace(";", ",").split(","):
        token = chunk.strip()
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _source_by_candidate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = _text(row.get("candidate_target_id")).upper()
        if candidate_id:
            out[candidate_id] = row
    return out


def _queue_rows_by_replace(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        replace_id = _text(row.get("replace_target_id")).upper()
        if replace_id:
            grouped[replace_id].append(row)
    return {key: sorted(value, key=lambda row: (_int(row.get("candidate_rank")) or 9999, _text(row.get("candidate_target_id")))) for key, value in grouped.items()}


def _duplicate_workorder_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _text(row.get("selection_status")) == DUPLICATE_STATUS]


def _selected_candidate_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {
        _text(row.get("target_id")).upper()
        for row in rows
        if _text(row.get("selection_status")) == "selected_for_replacement_workorder"
        and _text(row.get("target_id"))
    }


def _is_safe_unique_ready_candidate(
    queue_row: dict[str, Any],
    source_row: dict[str, Any],
    *,
    selected_candidate_ids: set[str],
) -> bool:
    candidate_id = _text(queue_row.get("candidate_target_id")).upper()
    return (
        bool(candidate_id)
        and candidate_id not in selected_candidate_ids
        and _text(queue_row.get("candidate_status")) == READY_STATUS
        and _text(source_row.get("source_repair_status")) == SOURCE_READY_STATUS
        and not _split_tokens(queue_row.get("blockers"))
        and not _split_tokens(source_row.get("blockers"))
    )


def _resolution_status(
    queue_row: dict[str, Any],
    source_row: dict[str, Any],
    *,
    duplicate_candidate: bool,
    safe_unique_ready_candidate: bool,
) -> str:
    if safe_unique_ready_candidate:
        return "safe_unique_ready_candidate"
    if duplicate_candidate:
        return DUPLICATE_STATUS
    source_status = _text(source_row.get("source_repair_status"))
    if source_status:
        return source_status
    return _text(queue_row.get("candidate_status")) or "candidate_status_missing"


def _row_blockers(
    queue_row: dict[str, Any],
    source_row: dict[str, Any],
    *,
    duplicate_candidate: bool,
    safe_unique_ready_candidate: bool,
) -> list[str]:
    blockers: list[str] = []
    if duplicate_candidate and not safe_unique_ready_candidate:
        blockers.append("duplicate_candidate_target_id")
    blockers.extend(_split_tokens(queue_row.get("blockers")))
    blockers.extend(_split_tokens(source_row.get("blockers")))
    source_status = _text(source_row.get("source_repair_status"))
    if source_status and source_status not in {SOURCE_READY_STATUS, READY_STATUS}:
        blockers.append(source_status)
    if _text(queue_row.get("candidate_status")) != READY_STATUS:
        blockers.append(_text(queue_row.get("candidate_status")))
    return list(dict.fromkeys(blocker for blocker in blockers if blocker and not safe_unique_ready_candidate))


def _next_action(
    queue_row: dict[str, Any],
    source_row: dict[str, Any],
    *,
    safe_unique_ready_candidate: bool,
    duplicate_candidate: bool,
) -> str:
    if safe_unique_ready_candidate:
        return "materialize a replacement workorder for this unique candidate, then run native/no-leak operator intake"
    if duplicate_candidate:
        return NO_SAFE_UNIQUE_ACTION
    source_action = _text(source_row.get("next_action"))
    if source_action:
        return source_action
    return _text(queue_row.get("next_action")) or NO_SAFE_UNIQUE_ACTION


def _resolution_rows(
    *,
    queue_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    workorder_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped_queue = _queue_rows_by_replace(queue_rows)
    sources = _source_by_candidate(source_rows)
    selected_ids = _selected_candidate_ids(workorder_rows)
    out: list[dict[str, Any]] = []
    for duplicate_row in _duplicate_workorder_rows(workorder_rows):
        replace_id = _text(duplicate_row.get("replace_target_id")).upper()
        duplicate_candidate_id = _text(duplicate_row.get("target_id")).upper()
        duplicate_for = _text(duplicate_row.get("duplicate_candidate_for_replace_target_ids"))
        for queue_row in grouped_queue.get(replace_id, []):
            candidate_id = _text(queue_row.get("candidate_target_id")).upper()
            source_row = sources.get(candidate_id, {})
            duplicate_candidate = candidate_id == duplicate_candidate_id
            safe_unique_ready = _is_safe_unique_ready_candidate(
                queue_row,
                source_row,
                selected_candidate_ids=selected_ids,
            )
            blockers = _row_blockers(
                queue_row,
                source_row,
                duplicate_candidate=duplicate_candidate,
                safe_unique_ready_candidate=safe_unique_ready,
            )
            out.append(
                {
                    "replace_target_id": replace_id,
                    "replace_target_name": _text(queue_row.get("replace_target_name"))
                    or _text(duplicate_row.get("replace_target_name")),
                    "candidate_rank": _int(queue_row.get("candidate_rank")),
                    "candidate_target_id": candidate_id,
                    "candidate_target_name": _text(queue_row.get("candidate_target_name")),
                    "queue_candidate_status": _text(queue_row.get("candidate_status")),
                    "source_repair_status": _text(source_row.get("source_repair_status")),
                    "resolution_status": _resolution_status(
                        queue_row,
                        source_row,
                        duplicate_candidate=duplicate_candidate,
                        safe_unique_ready_candidate=safe_unique_ready,
                    ),
                    "safe_unique_ready_candidate": "true" if safe_unique_ready else "false",
                    "duplicate_candidate": "true" if duplicate_candidate else "false",
                    "duplicate_candidate_for_replace_target_ids": duplicate_for if duplicate_candidate else "",
                    "prediction_pdb": _text(queue_row.get("prediction_pdb")) or _text(source_row.get("prediction_pdb")),
                    "ts_prediction_pdb": _text(queue_row.get("ts_prediction_pdb")) or _text(source_row.get("ts_prediction_pdb")),
                    "raw_validation_json": _text(queue_row.get("raw_validation_json"))
                    or _text(source_row.get("raw_validation_json")),
                    "scorecard_json": _text(queue_row.get("scorecard_json")) or _text(source_row.get("scorecard_json")),
                    "current_target_collision_ids": _text(queue_row.get("current_target_collision_ids")),
                    "cancellation_date": _text(source_row.get("cancellation_date")),
                    "blockers": ",".join(blockers),
                    "next_action": _next_action(
                        queue_row,
                        source_row,
                        safe_unique_ready_candidate=safe_unique_ready,
                        duplicate_candidate=duplicate_candidate,
                    ),
                }
            )
    return out


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    queue_payload = _read_json(args.replacement_queue_json)
    workorder_payload = _read_json(args.replacement_workorder_json)
    source_repair_payload = _read_json(args.replacement_source_repair_json)
    queue_rows = _rows(queue_payload)
    workorder_rows = _rows(workorder_payload)
    source_rows = _rows(source_repair_payload)
    rows = _resolution_rows(
        queue_rows=queue_rows,
        source_rows=source_rows,
        workorder_rows=workorder_rows,
    )
    statuses = Counter(_text(row.get("resolution_status")) for row in rows)
    safe_unique_count = sum(1 for row in rows if _text(row.get("safe_unique_ready_candidate")) == "true")
    duplicate_ready_count = sum(
        1
        for row in rows
        if _text(row.get("duplicate_candidate")) == "true"
        and _text(row.get("queue_candidate_status")) == READY_STATUS
    )
    duplicate_replace_targets = sorted({_text(row.get("replace_target_id")) for row in rows if _text(row.get("replace_target_id"))})
    if not _duplicate_workorder_rows(workorder_rows):
        duplicate_resolution_status = "no_duplicates"
    elif safe_unique_count:
        duplicate_resolution_status = "ready_unique_replacement_available"
    else:
        duplicate_resolution_status = "operator_decision_required"
    first_open = next(
        (row for row in rows if _text(row.get("resolution_status")) != "safe_unique_ready_candidate"),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_duplicate_resolution",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "duplicate_resolution_status": duplicate_resolution_status,
        "replacement_queue_json": _artifact(args.replacement_queue_json),
        "replacement_queue_status": _text(_summary(queue_payload).get("replacement_queue_status")),
        "replacement_workorder_json": _artifact(args.replacement_workorder_json),
        "replacement_workorder_status": _text(_summary(workorder_payload).get("replacement_workorder_status")),
        "replacement_source_repair_json": _artifact(args.replacement_source_repair_json),
        "replacement_source_repair_status": _text(
            _summary(source_repair_payload).get("replacement_source_repair_status")
        ),
        "duplicate_replace_target_count": len(duplicate_replace_targets),
        "duplicate_replace_target_ids": ";".join(duplicate_replace_targets),
        "candidate_row_count": len(rows),
        "safe_unique_ready_candidate_count": safe_unique_count,
        "duplicate_ready_candidate_count": duplicate_ready_count,
        "blocked_duplicate_count": statuses[DUPLICATE_STATUS],
        "blocked_cancelled_count": statuses["blocked_cancelled_target"],
        "blocked_current_collision_count": statuses["blocked_current_target_collision"],
        "blocked_missing_prediction_count": sum(
            1 for row in rows if "local_prediction_missing" in _split_tokens(row.get("blockers"))
        ),
        "first_open_replace_target_id": _text(first_open.get("replace_target_id")),
        "first_open_candidate_target_id": _text(first_open.get("candidate_target_id")),
        "first_open_status": _text(first_open.get("resolution_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Replacement Duplicate Resolution",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- duplicate_resolution_status: `{summary['duplicate_resolution_status']}`",
        f"- duplicate targets: `{summary['duplicate_replace_target_count']}` `{summary['duplicate_replace_target_ids'] or '-'}`",
        f"- candidates/safe-unique/duplicate-ready: `{summary['candidate_row_count']}/{summary['safe_unique_ready_candidate_count']}/{summary['duplicate_ready_candidate_count']}`",
        f"- blocked duplicate/cancelled/current-collision/missing-prediction: `{summary['blocked_duplicate_count']}/{summary['blocked_cancelled_count']}/{summary['blocked_current_collision_count']}/{summary['blocked_missing_prediction_count']}`",
        f"- first open: `{summary['first_open_replace_target_id'] or '-'}` -> `{summary['first_open_candidate_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Candidate Resolution",
        "",
        "| replace | rank | candidate | resolution | safe unique | queue | source | blockers | next action |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['replace_target_id']}` | {row['candidate_rank']} | `{row['candidate_target_id'] or '-'}` "
            f"{row['candidate_target_name'] or ''} | `{row['resolution_status']}` | "
            f"`{row['safe_unique_ready_candidate']}` | `{row['queue_candidate_status'] or '-'}` | "
            f"`{row['source_repair_status'] or '-'}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | 0 | - | `no_duplicates` | `false` | - | - | - | no duplicate replacement workorder blocker |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 replacement duplicate-resolution packet.")
    parser.add_argument("--replacement-queue-json", default=DEFAULT_REPLACEMENT_QUEUE_JSON)
    parser.add_argument("--replacement-workorder-json", default=DEFAULT_REPLACEMENT_WORKORDER_JSON)
    parser.add_argument("--replacement-source-repair-json", default=DEFAULT_REPLACEMENT_SOURCE_REPAIR_JSON)
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
