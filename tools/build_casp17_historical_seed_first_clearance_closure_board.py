#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_KIT_JSON = "casp17/casp17_historical_seed_first_clearance_operator_kit_current.json"
DEFAULT_NO_LEAK_GATE_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_gate_current.json"
DEFAULT_EVIDENCE_PACKET_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_packet_current.json"
DEFAULT_EVIDENCE_REVIEW_GATE_JSON = (
    "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_review_gate_current.json"
)
DEFAULT_EVIDENCE_SYNC_PLAN_JSON = (
    "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_sync_plan_current.json"
)
DEFAULT_CLEARANCE_TO_IDENTITY_SYNC_JSON = "casp17/casp17_historical_seed_clearance_to_identity_intake_sync_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_first_clearance_closure_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_first_clearance_closure_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_FIRST_CLEARANCE_CLOSURE_BOARD.md"

ROW_COLUMNS = [
    "stage_order",
    "stage_id",
    "label",
    "source_status",
    "stage_status",
    "ready_count",
    "blocked_count",
    "total_count",
    "artifact_path",
    "first_blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 first historical seed clearance closure board only. It aggregates existing "
    "first-clearance no-leak kit, evidence, review, sync, gate, promotion-preview, and identity-sync "
    "status into an ordered operator runway. It does not fill operator values, approve provenance, "
    "compute CASP metrics, mutate intake CSVs, push remotes, or submit to CASP."
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _stage(
    order: int,
    stage_id: str,
    label: str,
    source_status: str,
    ready: bool,
    ready_count: int,
    blocked_count: int,
    total_count: int,
    artifact_path: str,
    first_blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "stage_order": order,
        "stage_id": stage_id,
        "label": label,
        "source_status": source_status,
        "stage_status": "stage_ready" if ready else "stage_blocked",
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "total_count": total_count,
        "artifact_path": _artifact(artifact_path),
        "first_blocker": first_blocker,
        "next_action": next_action,
    }


def _build_rows(args: argparse.Namespace, summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    kit = summaries["kit"]
    gate = summaries["gate"]
    packet = summaries["packet"]
    review = summaries["review"]
    sync = summaries["sync"]
    identity = summaries["identity"]
    kit_ready = _text(kit.get("first_clearance_kit_status")) == "operator_no_leak_intake_ready"
    packet_ready = (
        _text(packet.get("first_clearance_no_leak_evidence_packet_status"))
        == "first_clearance_no_leak_evidence_packet_ready_for_review"
    )
    review_ready = (
        _text(review.get("first_clearance_no_leak_evidence_review_gate_status"))
        == "first_clearance_no_leak_evidence_ready_for_operator_fill"
    )
    sync_ready = _text(sync.get("first_clearance_no_leak_evidence_sync_plan_status")) in {
        "first_clearance_no_leak_evidence_sync_ready_dry_run",
        "first_clearance_no_leak_evidence_sync_applied",
    }
    gate_ready = (
        _text(gate.get("first_clearance_no_leak_gate_status"))
        == "first_clearance_no_leak_ready_for_promotion_review"
    )
    preview_ready = _text(kit.get("promotion_preview_status")) in {
        "promotion_preview_ready",
        "ready_for_promotion_review",
    }
    identity_ready = _text(identity.get("seed_to_identity_sync_status")) in {
        "ready_to_sync",
        "seed_to_identity_sync_ready_dry_run",
        "seed_to_identity_sync_applied",
    }
    return [
        _stage(
            1,
            "operator_kit",
            "First clearance operator kit exists",
            _text(kit.get("first_clearance_kit_status")),
            kit_ready,
            _int(kit.get("ready_candidate_field_count")),
            _int(kit.get("no_leak_field_count")),
            _int(kit.get("total_field_count")),
            args.operator_kit_json,
            "" if kit_ready else "operator_kit_not_ready",
            _text(kit.get("next_action")),
        ),
        _stage(
            2,
            "evidence_packet",
            "Collect independent no-leak evidence",
            _text(packet.get("first_clearance_no_leak_evidence_packet_status")),
            packet_ready,
            _int(packet.get("ready_field_count")),
            _int(packet.get("open_field_count")),
            _int(packet.get("field_count")),
            args.evidence_packet_json,
            _text(packet.get("first_blocker")) or _text(packet.get("first_open_kind")),
            _text(packet.get("next_action")),
        ),
        _stage(
            3,
            "evidence_review_gate",
            "Review filled no-leak evidence template and stubs",
            _text(review.get("first_clearance_no_leak_evidence_review_gate_status")),
            review_ready,
            _int(review.get("ready_field_count")),
            _int(review.get("blocked_field_count")),
            _int(review.get("field_count")),
            args.evidence_review_gate_json,
            _text(review.get("first_blocker")),
            _text(review.get("next_action")),
        ),
        _stage(
            4,
            "evidence_sync_plan",
            "Dry-run/apply reviewed evidence into no-leak intake",
            _text(sync.get("first_clearance_no_leak_evidence_sync_plan_status")),
            sync_ready,
            _int(sync.get("ready_action_count")),
            _int(sync.get("blocked_action_count")),
            _int(sync.get("action_count")),
            args.evidence_sync_plan_json,
            _text(sync.get("first_blocker")),
            _text(sync.get("next_action")),
        ),
        _stage(
            5,
            "no_leak_gate",
            "Validate no-leak intake after evidence sync",
            _text(gate.get("first_clearance_no_leak_gate_status")),
            gate_ready,
            _int(gate.get("ready_field_count")),
            _int(gate.get("blocked_field_count")),
            _int(gate.get("field_count")),
            args.no_leak_gate_json,
            _text(gate.get("first_blocker")),
            _text(gate.get("next_action")),
        ),
        _stage(
            6,
            "promotion_preview",
            "Review promotion preview for cleared seed manifest",
            _text(kit.get("promotion_preview_status")),
            preview_ready,
            1 if preview_ready else 0,
            0 if preview_ready else 1,
            1,
            _text(kit.get("promotion_preview_csv")),
            "" if preview_ready else _text(kit.get("promotion_preview_status")),
            "review promotion preview after no-leak gate is ready",
        ),
        _stage(
            7,
            "identity_intake_sync",
            "Sync cleared first seed into competitive identity intake",
            _text(identity.get("seed_to_identity_sync_status")),
            identity_ready,
            _int(identity.get("ready_to_sync_count")),
            _int(identity.get("waiting_intake_count")) + _int(identity.get("blocked_count")),
            _int(identity.get("intake_row_count")),
            args.clearance_to_identity_sync_json,
            _text(identity.get("first_blocker")) or _text(identity.get("seed_to_identity_sync_status")),
            _text(identity.get("first_next_action")),
        ),
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payloads = {
        "kit": _read_json(args.operator_kit_json),
        "gate": _read_json(args.no_leak_gate_json),
        "packet": _read_json(args.evidence_packet_json),
        "review": _read_json(args.evidence_review_gate_json),
        "sync": _read_json(args.evidence_sync_plan_json),
        "identity": _read_json(args.clearance_to_identity_sync_json),
    }
    summaries = {key: _summary(payload) for key, payload in payloads.items()}
    input_blockers = [
        f"{name}_json_missing"
        for name, path in [
            ("operator_kit", args.operator_kit_json),
            ("no_leak_gate", args.no_leak_gate_json),
            ("evidence_packet", args.evidence_packet_json),
            ("evidence_review_gate", args.evidence_review_gate_json),
            ("evidence_sync_plan", args.evidence_sync_plan_json),
            ("clearance_to_identity_sync", args.clearance_to_identity_sync_json),
        ]
        if not _resolve(path).exists()
    ]
    rows = [] if input_blockers else _build_rows(args, summaries)
    ready_rows = [row for row in rows if row["stage_status"] == "stage_ready"]
    blocked_rows = [row for row in rows if row["stage_status"] != "stage_ready"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    status = "first_clearance_closure_ready_for_identity_sync"
    if input_blockers:
        status = "blocked_missing_inputs"
    elif blocked_rows:
        status = "awaiting_first_clearance_no_leak_closure"
    summary = {
        "packet_type": "casp17_historical_seed_first_clearance_closure_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_clearance_closure_board_status": status,
        "target_id": _text(summaries["kit"].get("target_id")) or _text(summaries["gate"].get("target_id")),
        "benchmark_id": _text(summaries["kit"].get("benchmark_id")) or _text(summaries["gate"].get("benchmark_id")),
        "stage_count": len(rows),
        "ready_stage_count": len(ready_rows),
        "blocked_stage_count": len(blocked_rows),
        "first_blocked_stage_id": _text(first_blocked.get("stage_id")),
        "first_blocked_stage_status": _text(first_blocked.get("source_status")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "next_action": _text(first_blocked.get("next_action")) if blocked_rows else "sync cleared seed into competitive identity intake",
        "operator_kit_status": _text(summaries["kit"].get("first_clearance_kit_status")),
        "no_leak_gate_status": _text(summaries["gate"].get("first_clearance_no_leak_gate_status")),
        "evidence_packet_status": _text(
            summaries["packet"].get("first_clearance_no_leak_evidence_packet_status")
        ),
        "evidence_review_gate_status": _text(
            summaries["review"].get("first_clearance_no_leak_evidence_review_gate_status")
        ),
        "evidence_sync_plan_status": _text(
            summaries["sync"].get("first_clearance_no_leak_evidence_sync_plan_status")
        ),
        "promotion_preview_status": _text(summaries["kit"].get("promotion_preview_status")),
        "identity_sync_status": _text(summaries["identity"].get("seed_to_identity_sync_status")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed First Clearance Closure Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_clearance_closure_board_status']}`",
        f"- target/benchmark: `{summary['target_id']}` `{summary['benchmark_id']}`",
        f"- stages ready/blocked/total: `{summary['ready_stage_count']}/{summary['blocked_stage_count']}/{summary['stage_count']}`",
        f"- first blocked: `{summary['first_blocked_stage_id'] or '-'}` `{summary['first_blocked_stage_status'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action'] or '-'}",
        "",
        "## Stages",
        "",
        "| order | stage | status | ready | blocked | total | first blocker | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage_order']}` | `{row['stage_id']}` | `{row['source_status']}` | "
            f"`{row['ready_count']}` | `{row['blocked_count']}` | `{row['total_count']}` | "
            f"`{row['first_blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | missing input artifacts |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first historical seed clearance closure board.")
    parser.add_argument("--operator-kit-json", default=DEFAULT_OPERATOR_KIT_JSON)
    parser.add_argument("--no-leak-gate-json", default=DEFAULT_NO_LEAK_GATE_JSON)
    parser.add_argument("--evidence-packet-json", default=DEFAULT_EVIDENCE_PACKET_JSON)
    parser.add_argument("--evidence-review-gate-json", default=DEFAULT_EVIDENCE_REVIEW_GATE_JSON)
    parser.add_argument("--evidence-sync-plan-json", default=DEFAULT_EVIDENCE_SYNC_PLAN_JSON)
    parser.add_argument("--clearance-to-identity-sync-json", default=DEFAULT_CLEARANCE_TO_IDENTITY_SYNC_JSON)
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
