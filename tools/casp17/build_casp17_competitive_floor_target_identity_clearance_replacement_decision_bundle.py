#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DUPLICATE_RESOLUTION_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_duplicate_resolution_current.json"
)
DEFAULT_OUT_DIR = "casp17/competitive_floor_target_identity_clearance_replacement_decisions"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_bundle_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_decision_bundle_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_DECISION_BUNDLE.md"

SAFE_UNIQUE_STATUS = "safe_unique_ready_candidate"
OPEN_DECISION_ACTION = (
    "fill the new unique candidate intake template or explicitly approve duplicate candidate reuse with no-leak "
    "rationale, then rerun replacement workorders"
)
CLAIM_BOUNDARY = (
    "Local CASP17 replacement decision bundle only. It creates operator-facing decision files for duplicate "
    "replacement blockers, including a new-unique-candidate intake template and a duplicate-reuse exception "
    "template. It does not choose a new target, approve duplicate reuse, fetch native structures, clear no-leak "
    "provenance, score native accuracy, mutate replacement workorders, or submit to CASP."
)

DECISION_COLUMNS = [
    "replace_target_id",
    "replace_target_name",
    "decision_status",
    "decision_folder",
    "candidate_resolution_csv",
    "new_unique_candidate_intake_csv",
    "duplicate_reuse_exception_csv",
    "decision_md",
    "candidate_row_count",
    "safe_unique_ready_candidate_count",
    "duplicate_ready_candidate_count",
    "blocked_candidate_count",
    "duplicate_candidate_ids",
    "safe_unique_candidate_ids",
    "first_blocked_candidate_id",
    "next_action",
    "blockers",
]

NEW_UNIQUE_COLUMNS = [
    "replace_target_id",
    "replace_target_name",
    "proposed_candidate_target_id",
    "proposed_candidate_name",
    "closed_protein_target",
    "current_target_collision_checked",
    "cancellation_checked",
    "local_prediction_pdb",
    "raw_validation_json",
    "scorecard_json",
    "native_dropzone_pdb",
    "no_leak_evidence_ref",
    "operator_clearance",
    "operator",
    "decision_notes",
]

DUPLICATE_EXCEPTION_COLUMNS = [
    "replace_target_id",
    "replace_target_name",
    "duplicate_candidate_target_id",
    "duplicate_candidate_name",
    "already_assigned_replace_target_ids",
    "allow_duplicate_reuse",
    "no_leak_evidence_ref",
    "operator_clearance",
    "operator",
    "approval_date",
    "rationale",
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


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


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "target"


def _group_by_replace(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        replace_id = _text(row.get("replace_target_id")).upper()
        if replace_id:
            grouped[replace_id].append(row)
    return {
        key: sorted(value, key=lambda row: (_int(row.get("candidate_rank")) or 9999, _text(row.get("candidate_target_id"))))
        for key, value in grouped.items()
    }


def _decision_status(rows: list[dict[str, Any]]) -> str:
    if any(_text(row.get("resolution_status")) == SAFE_UNIQUE_STATUS for row in rows):
        return "ready_for_unique_replacement_workorder"
    if rows:
        return "open_operator_decision"
    return "no_duplicate_decision_required"


def _duplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _text(row.get("duplicate_candidate")) == "true"]


def _safe_unique_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _text(row.get("resolution_status")) == SAFE_UNIQUE_STATUS]


def _new_unique_template_row(replace_id: str, replace_name: str) -> dict[str, str]:
    return {
        "replace_target_id": replace_id,
        "replace_target_name": replace_name,
        "proposed_candidate_target_id": "REQUIRED_NEW_CLOSED_PROTEIN_TARGET_ID",
        "proposed_candidate_name": "REQUIRED_TARGET_NAME",
        "closed_protein_target": "REQUIRED_TRUE_CONFIRMATION",
        "current_target_collision_checked": "REQUIRED_TRUE_CONFIRMATION",
        "cancellation_checked": "REQUIRED_TRUE_CONFIRMATION",
        "local_prediction_pdb": "REQUIRED_LOCAL_PREDICTION_PDB",
        "raw_validation_json": "REQUIRED_RAW_VALIDATION_JSON",
        "scorecard_json": "REQUIRED_INTERNAL_SCORECARD_JSON",
        "native_dropzone_pdb": f"casp17/native_candidate_downloads/REQUIRED_TARGET_ID/REQUIRED_TARGET_ID_native.pdb",
        "no_leak_evidence_ref": "REQUIRED_NO_LEAK_EVIDENCE_REF",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "operator": "REQUIRED_OPERATOR_ID",
        "decision_notes": "Use this path when a safe unique non-colliding closed protein target is available.",
    }


def _duplicate_exception_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in _duplicate_rows(rows):
        out.append(
            {
                "replace_target_id": _text(row.get("replace_target_id")),
                "replace_target_name": _text(row.get("replace_target_name")),
                "duplicate_candidate_target_id": _text(row.get("candidate_target_id")),
                "duplicate_candidate_name": _text(row.get("candidate_target_name")),
                "already_assigned_replace_target_ids": _text(row.get("duplicate_candidate_for_replace_target_ids")),
                "allow_duplicate_reuse": "REQUIRED_FALSE_UNLESS_EXPLICITLY_APPROVED",
                "no_leak_evidence_ref": "REQUIRED_NO_LEAK_EVIDENCE_REF",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
                "approval_date": "YYYY-MM-DD",
                "rationale": "REQUIRED_RATIONALE_FOR_REUSING_ONE_CANDIDATE_IN_MULTIPLE_REPLACEMENT_SLOTS",
            }
        )
    return out


def _write_decision_md(path_like: str | Path, row: dict[str, Any], candidate_rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# {row['replace_target_id']} Replacement Decision",
        "",
        f"- decision_status: `{row['decision_status']}`",
        f"- candidate rows: `{row['candidate_row_count']}`",
        f"- safe unique ready candidates: `{row['safe_unique_ready_candidate_count']}` `{row['safe_unique_candidate_ids'] or '-'}`",
        f"- duplicate ready candidates: `{row['duplicate_ready_candidate_count']}` `{row['duplicate_candidate_ids'] or '-'}`",
        f"- next_action: {row['next_action']}",
        "",
        "## Decision Paths",
        "",
        f"- new unique candidate intake: `{row['new_unique_candidate_intake_csv']}`",
        f"- duplicate reuse exception: `{row['duplicate_reuse_exception_csv']}`",
        "",
        "## Candidate Evidence",
        "",
        "| rank | candidate | resolution | queue | source | blockers |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidate_rows:
        lines.append(
            f"| {candidate.get('candidate_rank', 0)} | `{candidate.get('candidate_target_id', '-')}` "
            f"{candidate.get('candidate_target_name', '')} | `{candidate.get('resolution_status', '-')}` | "
            f"`{candidate.get('queue_candidate_status', '-')}` | `{candidate.get('source_repair_status', '-')}` | "
            f"`{candidate.get('blockers', '-') or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_decision_rows(args: argparse.Namespace, duplicate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for replace_id, candidate_rows in _group_by_replace(duplicate_rows).items():
        replace_name = _text(candidate_rows[0].get("replace_target_name")) if candidate_rows else ""
        safe_rows = _safe_unique_rows(candidate_rows)
        duplicate_rows_for_target = _duplicate_rows(candidate_rows)
        decision_status = _decision_status(candidate_rows)
        folder = _resolve(args.out_dir) / f"{replace_id}_{_slug(replace_name[:80])}"
        candidate_resolution_csv = folder / "candidate_resolution.csv"
        new_unique_csv = folder / "new_unique_candidate_intake.csv"
        duplicate_exception_csv = folder / "duplicate_reuse_exception.csv"
        decision_md = folder / "DECISION.md"
        blocked_candidates = [
            row
            for row in candidate_rows
            if _text(row.get("resolution_status")) != SAFE_UNIQUE_STATUS
        ]
        row = {
            "replace_target_id": replace_id,
            "replace_target_name": replace_name,
            "decision_status": decision_status,
            "decision_folder": _artifact(folder),
            "candidate_resolution_csv": _artifact(candidate_resolution_csv),
            "new_unique_candidate_intake_csv": _artifact(new_unique_csv),
            "duplicate_reuse_exception_csv": _artifact(duplicate_exception_csv),
            "decision_md": _artifact(decision_md),
            "candidate_row_count": len(candidate_rows),
            "safe_unique_ready_candidate_count": len(safe_rows),
            "duplicate_ready_candidate_count": sum(
                1
                for candidate in duplicate_rows_for_target
                if _text(candidate.get("queue_candidate_status")) == "candidate_ready_for_operator_clearance"
            ),
            "blocked_candidate_count": len(blocked_candidates),
            "duplicate_candidate_ids": ";".join(_text(candidate.get("candidate_target_id")) for candidate in duplicate_rows_for_target),
            "safe_unique_candidate_ids": ";".join(_text(candidate.get("candidate_target_id")) for candidate in safe_rows),
            "first_blocked_candidate_id": _text(blocked_candidates[0].get("candidate_target_id")) if blocked_candidates else "",
            "next_action": (
                "materialize a replacement workorder for the safe unique candidate"
                if safe_rows
                else OPEN_DECISION_ACTION
            ),
            "blockers": (
                "safe_unique_candidate_ready"
                if safe_rows
                else "safe_unique_candidate_missing,operator_decision_required"
            ),
        }
        _write_csv(candidate_resolution_csv, candidate_rows, list(candidate_rows[0].keys()) if candidate_rows else ["replace_target_id"])
        _write_csv(new_unique_csv, [_new_unique_template_row(replace_id, replace_name)], NEW_UNIQUE_COLUMNS)
        duplicate_exception_rows = _duplicate_exception_rows(candidate_rows)
        if not duplicate_exception_rows:
            duplicate_exception_rows = _duplicate_exception_rows(
                [
                    {
                        "replace_target_id": replace_id,
                        "replace_target_name": replace_name,
                        "candidate_target_id": "",
                        "candidate_target_name": "",
                        "duplicate_candidate_for_replace_target_ids": "",
                    }
                ]
            )
        _write_csv(duplicate_exception_csv, duplicate_exception_rows, DUPLICATE_EXCEPTION_COLUMNS)
        _write_decision_md(decision_md, row, candidate_rows)
        out.append(row)
    return out


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    duplicate_payload = _read_json(args.duplicate_resolution_json)
    duplicate_rows = _rows(duplicate_payload)
    rows = _build_decision_rows(args, duplicate_rows)
    ready_count = sum(1 for row in rows if row["decision_status"] == "ready_for_unique_replacement_workorder")
    open_count = sum(1 for row in rows if row["decision_status"] == "open_operator_decision")
    if not rows:
        status = "no_duplicate_decision_required"
    elif open_count:
        status = "open_operator_decision"
    elif ready_count == len(rows):
        status = "ready_for_unique_replacement_workorder"
    else:
        status = "blocked"
    first_open = next((row for row in rows if row["decision_status"] != "ready_for_unique_replacement_workorder"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_decision_bundle",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision_bundle_status": status,
        "duplicate_resolution_json": _artifact(args.duplicate_resolution_json),
        "duplicate_resolution_status": _text(_summary(duplicate_payload).get("duplicate_resolution_status")),
        "out_dir": _artifact(args.out_dir),
        "decision_target_count": len(rows),
        "ready_decision_count": ready_count,
        "open_decision_count": open_count,
        "decision_folder_count": len(rows),
        "candidate_resolution_csv_count": len(rows),
        "new_unique_template_count": len(rows),
        "duplicate_exception_template_count": len(rows),
        "candidate_row_count": sum(_int(row.get("candidate_row_count")) for row in rows),
        "safe_unique_ready_candidate_count": sum(_int(row.get("safe_unique_ready_candidate_count")) for row in rows),
        "duplicate_ready_candidate_count": sum(_int(row.get("duplicate_ready_candidate_count")) for row in rows),
        "first_open_replace_target_id": _text(first_open.get("replace_target_id")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Replacement Decision Bundle",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- decision_bundle_status: `{summary['decision_bundle_status']}`",
        f"- duplicate_resolution_status: `{summary['duplicate_resolution_status'] or '-'}`",
        f"- decisions ready/open/total: `{summary['ready_decision_count']}/{summary['open_decision_count']}/{summary['decision_target_count']}`",
        f"- folders/candidate-csv/new-unique/duplicate-exception: `{summary['decision_folder_count']}/{summary['candidate_resolution_csv_count']}/{summary['new_unique_template_count']}/{summary['duplicate_exception_template_count']}`",
        f"- candidates safe-unique/duplicate-ready/total: `{summary['safe_unique_ready_candidate_count']}/{summary['duplicate_ready_candidate_count']}/{summary['candidate_row_count']}`",
        f"- first open: `{summary['first_open_replace_target_id'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Decisions",
        "",
        "| replace | status | candidates | safe unique | duplicate ready | folder | next action | blockers |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['replace_target_id']}` | `{row['decision_status']}` | {row['candidate_row_count']} | "
            f"{row['safe_unique_ready_candidate_count']} | {row['duplicate_ready_candidate_count']} | "
            f"`{row['decision_folder']}` | {row['next_action']} | `{row['blockers']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_duplicate_decision_required` | 0 | 0 | 0 | - | no action | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], DECISION_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 replacement duplicate decision bundle.")
    parser.add_argument("--duplicate-resolution-json", default=DEFAULT_DUPLICATE_RESOLUTION_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
