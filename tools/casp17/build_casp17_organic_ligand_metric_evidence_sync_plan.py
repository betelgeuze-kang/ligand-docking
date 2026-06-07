#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REVIEW_GATE_JSON = "casp17/casp17_organic_ligand_metric_evidence_review_gate_current.json"
DEFAULT_OUT_DIR = "casp17/organic_ligand_metric_evidence_sync_plan"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_metric_evidence_sync_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_metric_evidence_sync_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_METRIC_EVIDENCE_SYNC_PLAN.md"

READY_REVIEW_STATUS = "field_ready_for_organic_ligand_metric_review"
READY_GATE_STATUS = "organic_ligand_metric_evidence_review_ready"

ACTION_COLUMNS = [
    "sync_action_id",
    "sync_mode",
    "candidate_rank",
    "candidate_id",
    "target_id",
    "ligand_id",
    "field_order",
    "field_key",
    "review_gate_status",
    "linked_action_md",
    "destination_action_exists",
    "source_operator_value",
    "source_operator_evidence_ref",
    "source_operator_clearance",
    "source_operator_id",
    "proposed_action_status",
    "proposed_evidence_ref",
    "action_status",
    "blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 organic ligand metric evidence sync plan only. It maps reviewed organic ligand "
    "operator evidence toward the linked promotion actions using dry-run planning. It does not mutate "
    "promotion action files, fill operator values, approve no-leak provenance, compute LDDT-PLI or "
    "BiSyRMSD, mark competitive proof, serialize a CASP author code, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
        return ""
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] = ACTION_COLUMNS) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _gate_ready(summary: dict[str, Any]) -> bool:
    return _text(summary.get("organic_ligand_metric_evidence_review_gate_status")) == READY_GATE_STATUS


def _action_status(
    gate_ready: bool,
    review_row: dict[str, Any],
    destination_exists: bool,
) -> tuple[str, str]:
    if not gate_ready:
        return "blocked_review_gate_not_ready", _text(review_row.get("first_blocker")) or "review_gate_not_ready"
    if _text(review_row.get("review_gate_status")) != READY_REVIEW_STATUS:
        return "blocked_review_field_not_ready", _text(review_row.get("first_blocker")) or "review_field_not_ready"
    if not destination_exists:
        return "blocked_destination_action_missing", "destination_action_missing"
    if not _text(review_row.get("template_operator_value")):
        return "blocked_source_operator_value_missing", "source_operator_value_missing"
    if not _text(review_row.get("template_operator_evidence_ref")):
        return "blocked_source_operator_evidence_ref_missing", "source_operator_evidence_ref_missing"
    if not _text(review_row.get("template_operator_clearance")):
        return "blocked_source_operator_clearance_missing", "source_operator_clearance_missing"
    if not _text(review_row.get("template_operator_id")):
        return "blocked_source_operator_id_missing", "source_operator_id_missing"
    return "ready_to_sync", ""


def _proposed_action_status(row: dict[str, Any], action_status: str) -> str:
    if action_status != "ready_to_sync":
        return ""
    field_key = _text(row.get("field_key"))
    if field_key == "strict_blind_slot_mapping":
        return "ready_for_strict_blind_slot_review"
    return "operator_evidence_ready_for_metric_review"


def _next_action(row: dict[str, Any], action_status: str, blocker: str) -> str:
    field_key = _text(row.get("field_key"))
    if action_status == "ready_to_sync":
        return f"sync reviewed {field_key} evidence into linked organic ligand promotion action"
    if action_status == "blocked_review_gate_not_ready":
        return "complete organic ligand metric evidence review gate before sync"
    if action_status == "blocked_review_field_not_ready":
        return _text(row.get("next_action")) or f"complete review field {field_key}"
    if action_status == "blocked_destination_action_missing":
        return f"restore linked promotion action for {field_key}"
    if blocker:
        return f"resolve {blocker} for {field_key} before sync"
    return f"repair {field_key} before sync"


def _build_row(index: int, args: argparse.Namespace, gate_ready: bool, review_row: dict[str, Any]) -> dict[str, Any]:
    linked_action_md = _text(review_row.get("linked_action_md"))
    destination_exists = _resolve(linked_action_md).is_file() if linked_action_md else False
    action_status, blocker = _action_status(gate_ready, review_row, destination_exists)
    return {
        "sync_action_id": f"organic_ligand_metric_evidence_sync_{index:03d}",
        "sync_mode": args.mode,
        "candidate_rank": _int(review_row.get("candidate_rank")),
        "candidate_id": _text(review_row.get("candidate_id")),
        "target_id": _text(review_row.get("target_id")),
        "ligand_id": _text(review_row.get("ligand_id")),
        "field_order": _int(review_row.get("field_order")),
        "field_key": _text(review_row.get("field_key")),
        "review_gate_status": _text(review_row.get("review_gate_status")),
        "linked_action_md": _artifact(linked_action_md),
        "destination_action_exists": str(destination_exists),
        "source_operator_value": _text(review_row.get("template_operator_value")),
        "source_operator_evidence_ref": _text(review_row.get("template_operator_evidence_ref")),
        "source_operator_clearance": _text(review_row.get("template_operator_clearance")),
        "source_operator_id": _text(review_row.get("template_operator_id")),
        "proposed_action_status": _proposed_action_status(review_row, action_status),
        "proposed_evidence_ref": _text(review_row.get("template_operator_evidence_ref")),
        "action_status": action_status,
        "blocker": blocker,
        "next_action": _next_action(review_row, action_status, blocker),
    }


def _status(input_missing: bool, rows: list[dict[str, Any]], mode: str) -> str:
    if input_missing:
        return "blocked_organic_ligand_metric_evidence_review_gate_missing"
    if not rows:
        return "blocked_organic_ligand_metric_evidence_sync_rows_missing"
    if any(row["action_status"] == "blocked_review_gate_not_ready" for row in rows):
        return "awaiting_organic_ligand_metric_evidence_review"
    if any(row["action_status"].startswith("blocked") for row in rows):
        return "blocked_organic_ligand_metric_evidence_sync"
    if mode == "dry_run":
        return "organic_ligand_metric_evidence_sync_ready_dry_run"
    return "organic_ligand_metric_evidence_sync_ready"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_path = _resolve(args.review_gate_json)
    review_payload = _read_json(review_path)
    review_summary = _summary(review_payload)
    review_rows = _rows(review_payload)
    gate_ready = _gate_ready(review_summary)
    rows = [] if not review_path.exists() else [
        _build_row(index, args, gate_ready, row) for index, row in enumerate(review_rows, start=1)
    ]
    ready_rows = [row for row in rows if row["action_status"] == "ready_to_sync"]
    blocked_rows = [row for row in rows if row["action_status"].startswith("blocked")]
    candidate_ids = list(dict.fromkeys(row["candidate_id"] for row in rows if row["candidate_id"]))
    ready_candidate_ids = {
        candidate_id
        for candidate_id in candidate_ids
        if all(row["action_status"] == "ready_to_sync" for row in rows if row["candidate_id"] == candidate_id)
    }
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_organic_ligand_metric_evidence_sync_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_metric_evidence_sync_plan_status": _status(not review_path.exists(), rows, args.mode),
        "sync_mode": args.mode,
        "review_gate_json": _artifact(args.review_gate_json),
        "review_gate_status": _text(
            review_summary.get("organic_ligand_metric_evidence_review_gate_status")
        ),
        "candidate_count": len(candidate_ids),
        "ready_candidate_count": len(ready_candidate_ids),
        "blocked_candidate_count": len(candidate_ids) - len(ready_candidate_ids),
        "action_count": len(rows),
        "ready_action_count": len(ready_rows),
        "blocked_action_count": len(blocked_rows),
        "destination_action_present_count": sum(1 for row in rows if row["destination_action_exists"] == "True"),
        "destination_action_missing_count": sum(1 for row in rows if row["destination_action_exists"] != "True"),
        "source_value_missing_count": sum(1 for row in rows if not row["source_operator_value"]),
        "source_evidence_ref_missing_count": sum(1 for row in rows if not row["source_operator_evidence_ref"]),
        "source_clearance_missing_count": sum(1 for row in rows if not row["source_operator_clearance"]),
        "source_operator_id_missing_count": sum(1 for row in rows if not row["source_operator_id"]),
        "review_gate_blocked_action_count": sum(
            1 for row in rows if row["action_status"] == "blocked_review_gate_not_ready"
        ),
        "review_field_blocked_action_count": sum(
            1 for row in rows if row["action_status"] == "blocked_review_field_not_ready"
        ),
        "first_blocked_candidate_id": _text(first_blocked.get("candidate_id")),
        "first_blocked_field_key": _text(first_blocked.get("field_key")),
        "first_blocker": _text(first_blocked.get("blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "sync_plan_folder": _artifact(args.out_dir),
        "candidate_sync_folder_count": len(candidate_ids),
        "next_action": (
            "Complete organic ligand metric evidence review, then rerun this dry-run sync plan before "
            "promoting any ligand field into metric computation."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Metric Evidence Sync Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_metric_evidence_sync_plan_status']}`",
        f"- mode: `{summary['sync_mode']}`",
        f"- candidates ready/blocked/total: `{summary['ready_candidate_count']}/{summary['blocked_candidate_count']}/{summary['candidate_count']}`",
        f"- actions ready/blocked/total: `{summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['action_count']}`",
        f"- destination actions present/missing: `{summary['destination_action_present_count']}/{summary['destination_action_missing_count']}`",
        f"- source missing value/evidence/clearance/operator: `{summary['source_value_missing_count']}/{summary['source_evidence_ref_missing_count']}/{summary['source_clearance_missing_count']}/{summary['source_operator_id_missing_count']}`",
        f"- review gate/field blocked actions: `{summary['review_gate_blocked_action_count']}/{summary['review_field_blocked_action_count']}`",
        f"- candidate sync folders: `{summary['candidate_sync_folder_count']}` in `{summary['sync_plan_folder']}`",
        f"- first blocked: `{summary['first_blocked_candidate_id'] or '-'}` `{summary['first_blocked_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Sync Actions",
        "",
        "| action | candidate | field | status | blocker | destination |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sync_action_id']}` | `{row['candidate_id']}` | `{row['field_key']}` | "
            f"`{row['action_status']}` | `{row['blocker'] or '-'}` | `{row['linked_action_md'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_candidate_folders(out_dir: str | Path, payload: dict[str, Any]) -> None:
    root = _resolve(out_dir)
    rows_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for row in payload["rows"]:
        candidate_id = _text(row.get("candidate_id")) or "unknown_candidate"
        rows_by_candidate.setdefault(candidate_id, []).append(row)
    for index, (candidate_id, rows) in enumerate(rows_by_candidate.items(), start=1):
        folder = root / f"{index:02d}_{candidate_id}"
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "sync_rows.csv", rows)
        ready_count = sum(1 for row in rows if row["action_status"] == "ready_to_sync")
        first_blocked = next((row for row in rows if row["action_status"].startswith("blocked")), {})
        lines = [
            f"# {candidate_id} Organic Ligand Metric Evidence Sync",
            "",
            f"- sync mode: `{payload['summary']['sync_mode']}`",
            f"- actions ready/blocked/total: `{ready_count}/{len(rows) - ready_count}/{len(rows)}`",
            f"- first blocker: `{first_blocked.get('field_key', '-') or '-'}` `{first_blocked.get('blocker', '-') or '-'}`",
            "",
            "## Actions",
            "",
            "| action | field | status | blocker | next action |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['sync_action_id']}` | `{row['field_key']}` | `{row['action_status']}` | "
                f"`{row['blocker'] or '-'}` | {row['next_action']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "SYNC.md").write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_candidate_folders(args.out_dir, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand metric evidence sync plan.")
    parser.add_argument("--review-gate-json", default=DEFAULT_REVIEW_GATE_JSON)
    parser.add_argument("--mode", choices=["dry_run"], default="dry_run")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
