#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_UPLOAD_QUEUE_JSON = "casp17/casp17_current_upload_queue_current.json"
DEFAULT_UPLOAD_REVIEW_PACKET_JSON = "casp17/casp17_current_upload_review_packet_current.json"
DEFAULT_UPLOAD_OPERATOR_DECISION_KIT_JSON = "casp17/casp17_current_upload_operator_decision_kit_current.json"
DEFAULT_UPLOAD_ACTIVE_MANIFEST_LOCK_JSON = "casp17/casp17_current_upload_active_manifest_lock_current.json"
DEFAULT_SUBMISSION_PACKAGE_PREFLIGHT_JSON = "casp17/casp17_current_submission_package_preflight_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_current_upload_decision_rule_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_upload_decision_rule_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_UPLOAD_DECISION_RULE_GATE.md"

ROW_COLUMNS = [
    "queue_rank",
    "target_id",
    "official_target_id",
    "urgency",
    "human_expiration",
    "days_to_deadline",
    "technical_gate_status",
    "decision_rule_status",
    "recommendation",
    "active_manifest_lock_status",
    "review_status",
    "package_preflight_status",
    "sidechain_repack_status",
    "format_check_status",
    "author_record_status",
    "operator_decision",
    "author_serialization_status",
    "candidate_sha256_match",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "CASP17 current upload decision-rule gate only. It evaluates active upload rows against deadline, "
    "manifest-lock, package-preflight, sidechain, format, operator-decision, and author-serialization "
    "conditions. It recommends queue handling but does not enter operator decisions, serialize an author "
    "code, submit to CASP, compute native accuracy, or mark strict-blind competitive proof."
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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _technical_gate(
    queue: dict[str, Any],
    review: dict[str, Any],
    decision: dict[str, Any],
    lock: dict[str, Any],
    preflight: dict[str, Any],
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if _int(queue.get("queue_rank")) <= 0:
        blockers.append("not_active_upload_queue")
    if _int(decision.get("days_to_official_human_expiration")) < 0:
        blockers.append("deadline_expired")
    if _text(lock.get("lock_status")) != "active_manifest_locked_awaiting_operator_decision":
        blockers.append("active_manifest_lock_not_ready")
    if _text(review.get("review_status")) != "ready":
        blockers.append("upload_review_not_ready")
    if _text(preflight.get("package_preflight_status")) != "ready":
        blockers.append("package_preflight_not_ready")
    if _text(preflight.get("sidechain_repack_status")) != "pass":
        blockers.append("sidechain_repack_not_pass")
    if _text(preflight.get("format_check_status")) != "pass":
        blockers.append("format_check_not_pass")
    q_sha = _text(queue.get("candidate_sha256"))
    d_sha = _text(decision.get("candidate_sha256"))
    p_sha = _text(preflight.get("candidate_sha256"))
    if not q_sha or not d_sha or not p_sha or len({q_sha, d_sha, p_sha}) != 1:
        blockers.append("candidate_sha256_mismatch")
    return ("technical_upload_candidate" if not blockers else "technical_gate_blocked", blockers)


def _decision_rule(row: dict[str, Any], technical_blockers: list[str]) -> tuple[str, str, list[str], str]:
    blockers = list(technical_blockers)
    if technical_blockers:
        return (
            "hold_technical_gate_blocked",
            "hold",
            blockers,
            "repair technical gate blockers before operator decision",
        )
    decision = _text(row.get("operator_decision")).lower()
    author_serialization = _text(row.get("author_serialization_status")).lower()
    if not decision:
        blockers.append("operator_decision_missing")
    elif decision not in {"approve", "hold", "reject"}:
        blockers.append("operator_decision_invalid")
    if decision == "approve" and author_serialization != "author_serialized":
        blockers.append("author_serialization_missing")
    if not decision:
        return (
            "awaiting_operator_decision",
            "conditional_approve_after_operator_review_and_author_serialization",
            blockers,
            "operator must enter approve, hold, or reject in the active intake row",
        )
    if decision == "approve" and author_serialization != "author_serialized":
        return (
            "awaiting_author_serialization",
            "hold_until_author_serialized",
            blockers,
            "serialize runtime CASP author code before upload",
        )
    if decision == "approve":
        return (
            "operator_approved_ready_for_runtime_upload",
            "approve_runtime_upload_candidate",
            blockers,
            "perform final human-controlled CASP upload step before deadline",
        )
    if decision == "hold":
        return ("operator_hold", "hold", blockers, "resolve operator hold reason before upload")
    if decision == "reject":
        return ("operator_reject", "reject", blockers, "keep target out of current upload")
    return ("blocked_invalid_operator_decision", "hold", blockers, "use approve, hold, or reject")


def _build_row(
    queue: dict[str, Any],
    review_by_target: dict[str, dict[str, Any]],
    decision_by_target: dict[str, dict[str, Any]],
    lock_by_target: dict[str, dict[str, Any]],
    preflight_by_target: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_id = _text(queue.get("target_id")).upper()
    review = review_by_target.get(target_id, {})
    decision = decision_by_target.get(target_id, {})
    lock = lock_by_target.get(target_id, {})
    preflight = preflight_by_target.get(target_id, {})
    technical_status, technical_blockers = _technical_gate(queue, review, decision, lock, preflight)
    row = {
        "queue_rank": _int(queue.get("queue_rank")),
        "target_id": target_id,
        "official_target_id": _text(queue.get("official_target_id")),
        "urgency": _text(review.get("urgency")),
        "human_expiration": _text(queue.get("official_human_expiration")) or _text(decision.get("official_human_expiration")),
        "days_to_deadline": _int(decision.get("days_to_official_human_expiration")),
        "technical_gate_status": technical_status,
        "active_manifest_lock_status": _text(lock.get("lock_status")),
        "review_status": _text(review.get("review_status")),
        "package_preflight_status": _text(preflight.get("package_preflight_status")),
        "sidechain_repack_status": _text(preflight.get("sidechain_repack_status")),
        "format_check_status": _text(preflight.get("format_check_status")),
        "author_record_status": _text(preflight.get("author_record_status")),
        "operator_decision": _text(decision.get("operator_decision")),
        "author_serialization_status": _text(decision.get("author_serialization_status")),
        "candidate_sha256_match": str(not any(blocker == "candidate_sha256_mismatch" for blocker in technical_blockers)),
    }
    status, recommendation, blockers, next_action = _decision_rule({**row, **decision}, technical_blockers)
    row["decision_rule_status"] = status
    row["recommendation"] = recommendation
    row["blockers"] = ";".join(blockers)
    row["next_action"] = next_action
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    queue_payload = _read_json(args.upload_queue_json)
    review_payload = _read_json(args.upload_review_packet_json)
    decision_payload = _read_json(args.upload_operator_decision_kit_json)
    lock_payload = _read_json(args.upload_active_manifest_lock_json)
    preflight_payload = _read_json(args.submission_package_preflight_json)
    active_queue_rows = [row for row in _rows(queue_payload) if _int(row.get("queue_rank")) > 0]
    review_by_target = _by_target(_rows(review_payload))
    decision_by_target = _by_target(_rows(decision_payload))
    lock_by_target = _by_target([row for row in _rows(lock_payload) if row.get("row_kind") == "active_upload_target"])
    preflight_by_target = _by_target(_rows(preflight_payload))
    rows = [
        _build_row(row, review_by_target, decision_by_target, lock_by_target, preflight_by_target)
        for row in sorted(active_queue_rows, key=lambda item: (_int(item.get("queue_rank")), _text(item.get("target_id"))))
    ]
    missing_inputs = not all([queue_payload, review_payload, decision_payload, lock_payload, preflight_payload])
    technical_ready = [row for row in rows if row["technical_gate_status"] == "technical_upload_candidate"]
    conditional = [
        row
        for row in rows
        if row["recommendation"] == "conditional_approve_after_operator_review_and_author_serialization"
    ]
    author_missing = [
        row
        for row in rows
        if row["decision_rule_status"] == "awaiting_author_serialization"
        or (
            row["technical_gate_status"] == "technical_upload_candidate"
            and not _text(row.get("author_serialization_status"))
        )
    ]
    blocked = [row for row in rows if row["decision_rule_status"].startswith("hold_") or row["decision_rule_status"].startswith("blocked_")]
    first_open = next((row for row in rows if row["decision_rule_status"] != "operator_approved_ready_for_runtime_upload"), rows[0] if rows else {})
    if missing_inputs:
        status = "blocked_upload_decision_rule_gate_missing_inputs"
    elif not rows:
        status = "blocked_upload_decision_rule_gate_no_active_targets"
    elif blocked:
        status = "current_upload_decision_rule_gate_technical_blocked"
    elif conditional:
        status = "current_upload_decision_rule_gate_ready_for_operator_decisions"
    elif author_missing:
        status = "current_upload_decision_rule_gate_awaiting_author_serialization"
    else:
        status = "current_upload_decision_rule_gate_ready_for_runtime_upload"
    summary = {
        "packet_type": "casp17_current_upload_decision_rule_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "upload_decision_rule_gate_status": status,
        "active_target_count": len(rows),
        "technical_upload_candidate_count": len(technical_ready),
        "technical_blocked_count": len(rows) - len(technical_ready),
        "conditional_approve_after_operator_count": len(conditional),
        "author_serialization_missing_count": len(author_missing),
        "operator_decision_missing_count": sum(1 for row in rows if not _text(row.get("operator_decision"))),
        "approve_count": sum(1 for row in rows if _text(row.get("operator_decision")).lower() == "approve"),
        "hold_count": sum(1 for row in rows if _text(row.get("operator_decision")).lower() == "hold"),
        "reject_count": sum(1 for row in rows if _text(row.get("operator_decision")).lower() == "reject"),
        "first_target_id": _text(first_open.get("target_id")),
        "first_status": _text(first_open.get("decision_rule_status")),
        "first_recommendation": _text(first_open.get("recommendation")),
        "first_blockers": _text(first_open.get("blockers")),
        "upload_queue_status": _text(_summary(queue_payload).get("upload_queue_status")),
        "review_packet_status": _text(_summary(review_payload).get("review_packet_status")),
        "decision_kit_status": _text(_summary(decision_payload).get("decision_kit_status")),
        "active_manifest_lock_status": _text(_summary(lock_payload).get("active_manifest_lock_status")),
        "submission_package_preflight_status": _text(_summary(preflight_payload).get("package_preflight_status")),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_action": "start with H1344, enter operator decision, then serialize runtime CASP author code before any upload",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Upload Decision Rule Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['upload_decision_rule_gate_status']}`",
        f"- active/technical/blocked: `{summary['active_target_count']}/{summary['technical_upload_candidate_count']}/{summary['technical_blocked_count']}`",
        f"- conditional approve after operator: `{summary['conditional_approve_after_operator_count']}`",
        f"- missing operator decision/author serialization: `{summary['operator_decision_missing_count']}/{summary['author_serialization_missing_count']}`",
        f"- decisions approve/hold/reject: `{summary['approve_count']}/{summary['hold_count']}/{summary['reject_count']}`",
        f"- first: `{summary['first_target_id'] or '-'}` `{summary['first_status'] or '-'}` `{summary['first_recommendation'] or '-'}` `{summary['first_blockers'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Rows",
        "",
        "| rank | target | technical | rule | recommendation | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['target_id']}` | `{row['technical_gate_status']}` | "
            f"`{row['decision_rule_status']}` | `{row['recommendation']}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `blocked_no_rows` | `blocked_no_rows` | `hold` | `no_rows` | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 current upload decision-rule gate.")
    parser.add_argument("--upload-queue-json", default=DEFAULT_UPLOAD_QUEUE_JSON)
    parser.add_argument("--upload-review-packet-json", default=DEFAULT_UPLOAD_REVIEW_PACKET_JSON)
    parser.add_argument("--upload-operator-decision-kit-json", default=DEFAULT_UPLOAD_OPERATOR_DECISION_KIT_JSON)
    parser.add_argument("--upload-active-manifest-lock-json", default=DEFAULT_UPLOAD_ACTIVE_MANIFEST_LOCK_JSON)
    parser.add_argument("--submission-package-preflight-json", default=DEFAULT_SUBMISSION_PACKAGE_PREFLIGHT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
