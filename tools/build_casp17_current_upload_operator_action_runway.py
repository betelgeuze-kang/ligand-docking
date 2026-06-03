#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_RULE_GATE_JSON = "casp17/casp17_current_upload_decision_rule_gate_current.json"
DEFAULT_OPERATOR_DECISION_KIT_JSON = "casp17/casp17_current_upload_operator_decision_kit_current.json"
DEFAULT_OPERATOR_DECISION_KIT_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_current_upload_operator_decision_kit_completion_audit_current.json"
)
DEFAULT_ACTIVE_MANIFEST_LOCK_JSON = "casp17/casp17_current_upload_active_manifest_lock_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_current_upload_operator_action_runway_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_upload_operator_action_runway_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_UPLOAD_OPERATOR_ACTION_RUNWAY.md"

OPERATOR_DECISION_INTAKE = "casp17/current_upload_operator_decision_kit/operator_decision_intake.csv"
ROW_COLUMNS = [
    "queue_rank",
    "target_id",
    "official_target_id",
    "urgency",
    "human_expiration",
    "days_to_deadline",
    "action_status",
    "technical_gate_status",
    "decision_rule_status",
    "recommendation",
    "operator_decision",
    "author_serialization_status",
    "required_operator_fields",
    "fill_surface",
    "decision_md",
    "review_md",
    "candidate_pdb",
    "candidate_sha256",
    "object_count",
    "chain_ids",
    "blockers",
    "next_operator_action",
]
CLAIM_BOUNDARY = (
    "CASP17 current upload operator action runway only. It merges the active decision-rule gate, "
    "operator decision kit, completion audit, and active-manifest lock into a human fill plan. It does "
    "not enter approve/hold/reject decisions, serialize a CASP author code, create final upload files, "
    "submit to CASP, compute native accuracy, or mark strict-blind competitive proof."
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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


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


def _action_status(gate: dict[str, Any], decision: dict[str, Any]) -> tuple[str, str, str]:
    technical_status = _text(gate.get("technical_gate_status"))
    decision_status = _text(gate.get("decision_rule_status"))
    operator_decision = _text(decision.get("operator_decision")).lower()
    author_status = _text(decision.get("author_serialization_status")).lower()
    blockers = _text(gate.get("blockers"))
    if technical_status != "technical_upload_candidate":
        return (
            "technical_blocked",
            "repair technical gate blockers before editing operator approval fields",
            blockers,
        )
    if not operator_decision:
        return (
            "operator_decision_required",
            "enter approve, hold, or reject in the active operator decision intake row",
            blockers or "operator_decision_missing",
        )
    if operator_decision not in {"approve", "hold", "reject"}:
        return (
            "operator_decision_invalid",
            "replace operator_decision with approve, hold, or reject",
            blockers or "operator_decision_invalid",
        )
    if operator_decision == "approve" and author_status != "author_serialized":
        return (
            "author_serialization_required",
            "serialize runtime CASP author code before creating a final upload filename",
            blockers or "author_serialization_missing",
        )
    if decision_status == "operator_approved_ready_for_runtime_upload":
        return (
            "ready_for_human_controlled_runtime_upload",
            "perform final human-controlled CASP portal upload step before deadline",
            blockers,
        )
    return (
        f"operator_{operator_decision}",
        f"honor operator {operator_decision} decision for this upload window",
        blockers,
    )


def _required_fields(action_status: str) -> str:
    if action_status == "operator_decision_required":
        return "operator_decision,operator_id,operator_decision_ref,operator_notes_optional"
    if action_status == "author_serialization_required":
        return "author_serialization_status,final_upload_filename"
    if action_status == "ready_for_human_controlled_runtime_upload":
        return "final_human_upload_confirmation_outside_git"
    if action_status == "technical_blocked":
        return "technical_gate_repair"
    return "none"


def _build_row(gate: dict[str, Any], decision_by_target: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target_id = _text(gate.get("target_id")).upper()
    decision = decision_by_target.get(target_id, {})
    action_status, next_action, blockers = _action_status(gate, decision)
    return {
        "queue_rank": _int(gate.get("queue_rank")),
        "target_id": target_id,
        "official_target_id": _text(gate.get("official_target_id")) or _text(decision.get("official_target_id")),
        "urgency": _text(gate.get("urgency")) or _text(decision.get("urgency")),
        "human_expiration": _text(gate.get("human_expiration")) or _text(decision.get("official_human_expiration")),
        "days_to_deadline": _int(gate.get("days_to_deadline")),
        "action_status": action_status,
        "technical_gate_status": _text(gate.get("technical_gate_status")),
        "decision_rule_status": _text(gate.get("decision_rule_status")),
        "recommendation": _text(gate.get("recommendation")),
        "operator_decision": _text(decision.get("operator_decision")),
        "author_serialization_status": _text(decision.get("author_serialization_status")),
        "required_operator_fields": _required_fields(action_status),
        "fill_surface": OPERATOR_DECISION_INTAKE,
        "decision_md": _text(decision.get("decision_md")),
        "review_md": _text(decision.get("review_md")),
        "candidate_pdb": _text(decision.get("candidate_pdb")),
        "candidate_sha256": _text(decision.get("candidate_sha256")),
        "object_count": _int(decision.get("object_count")),
        "chain_ids": _text(decision.get("chain_ids")),
        "blockers": blockers,
        "next_operator_action": next_action,
    }


def _status(missing_inputs: bool, rows: list[dict[str, Any]]) -> str:
    if missing_inputs:
        return "blocked_current_upload_operator_action_runway_missing_inputs"
    if not rows:
        return "blocked_current_upload_operator_action_runway_no_active_rows"
    if any(row["action_status"] == "technical_blocked" for row in rows):
        return "current_upload_operator_action_runway_technical_blocked"
    if any(row["action_status"] == "operator_decision_required" for row in rows):
        return "current_upload_operator_action_runway_ready_for_human_decisions"
    if any(row["action_status"] == "author_serialization_required" for row in rows):
        return "current_upload_operator_action_runway_awaiting_author_serialization"
    if any(row["action_status"] == "ready_for_human_controlled_runtime_upload" for row in rows):
        return "current_upload_operator_action_runway_contains_runtime_upload_candidates"
    return "current_upload_operator_action_runway_no_open_upload_actions"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_payload = _read_json(args.decision_rule_gate_json)
    decision_payload = _read_json(args.operator_decision_kit_json)
    audit_payload = _read_json(args.operator_decision_kit_completion_audit_json)
    lock_payload = _read_json(args.active_manifest_lock_json)
    gate_summary = _summary(gate_payload)
    decision_summary = _summary(decision_payload)
    audit_summary = _summary(audit_payload)
    lock_summary = _summary(lock_payload)
    decision_by_target = _by_target(_rows(decision_payload))
    rows = [
        _build_row(row, decision_by_target)
        for row in sorted(_rows(gate_payload), key=lambda item: (_int(item.get("queue_rank")), _text(item.get("target_id"))))
    ]
    missing_inputs = not all([gate_payload, decision_payload, audit_payload, lock_payload])
    first_action = next(
        (
            row
            for row in rows
            if row["action_status"]
            in {
                "operator_decision_required",
                "author_serialization_required",
                "technical_blocked",
                "operator_decision_invalid",
            }
        ),
        rows[0] if rows else {},
    )
    operator_required = [row for row in rows if row["action_status"] == "operator_decision_required"]
    author_required = [row for row in rows if row["action_status"] == "author_serialization_required"]
    ready_upload = [row for row in rows if row["action_status"] == "ready_for_human_controlled_runtime_upload"]
    technical_blocked = [row for row in rows if row["action_status"] == "technical_blocked"]
    summary = {
        "packet_type": "casp17_current_upload_operator_action_runway",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "operator_action_runway_status": _status(missing_inputs, rows),
        "active_target_count": len(rows),
        "technical_upload_candidate_count": sum(
            1 for row in rows if row["technical_gate_status"] == "technical_upload_candidate"
        ),
        "technical_blocked_count": len(technical_blocked),
        "operator_decision_required_count": len(operator_required),
        "author_serialization_required_count": len(author_required),
        "ready_for_runtime_upload_count": len(ready_upload),
        "approve_count": sum(1 for row in rows if _text(row.get("operator_decision")).lower() == "approve"),
        "hold_count": sum(1 for row in rows if _text(row.get("operator_decision")).lower() == "hold"),
        "reject_count": sum(1 for row in rows if _text(row.get("operator_decision")).lower() == "reject"),
        "urgency_today_count": sum(1 for row in rows if row["urgency"] == "today"),
        "urgency_soon_count": sum(1 for row in rows if row["urgency"] == "soon"),
        "urgency_future_count": sum(1 for row in rows if row["urgency"] == "future"),
        "first_target_id": _text(first_action.get("target_id")),
        "first_action_status": _text(first_action.get("action_status")),
        "first_required_operator_fields": _text(first_action.get("required_operator_fields")),
        "first_fill_surface": _text(first_action.get("fill_surface")),
        "first_decision_md": _text(first_action.get("decision_md")),
        "first_blockers": _text(first_action.get("blockers")),
        "decision_rule_gate_status": _text(gate_summary.get("upload_decision_rule_gate_status")),
        "decision_kit_status": _text(decision_summary.get("current_upload_operator_decision_kit_status"))
        or _text(decision_summary.get("decision_kit_status")),
        "decision_kit_completion_audit_status": _text(
            audit_summary.get("current_upload_operator_decision_kit_completion_audit_status")
        )
        or _text(audit_summary.get("completion_audit_status")),
        "active_manifest_lock_status": _text(lock_summary.get("active_manifest_lock_status")),
        "next_action": (
            f"start with {_text(first_action.get('target_id'))}; "
            f"{_text(first_action.get('next_operator_action'))}"
            if first_action
            else "regenerate active upload operator surfaces"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
        "source_files": {
            "decision_rule_gate_json": _artifact(args.decision_rule_gate_json),
            "operator_decision_kit_json": _artifact(args.operator_decision_kit_json),
            "operator_decision_kit_completion_audit_json": _artifact(
                args.operator_decision_kit_completion_audit_json
            ),
            "active_manifest_lock_json": _artifact(args.active_manifest_lock_json),
        },
    }


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = _summary(payload)
    rows = _rows(payload)
    lines = [
        "# CASP17 Current Upload Operator Action Runway",
        "",
        f"- status: `{summary.get('operator_action_runway_status', '-')}`",
        (
            "- active/technical/blocked: "
            f"`{summary.get('active_target_count', 0)}/"
            f"{summary.get('technical_upload_candidate_count', 0)}/"
            f"{summary.get('technical_blocked_count', 0)}`"
        ),
        (
            "- operator/author/runtime-ready: "
            f"`{summary.get('operator_decision_required_count', 0)}/"
            f"{summary.get('author_serialization_required_count', 0)}/"
            f"{summary.get('ready_for_runtime_upload_count', 0)}`"
        ),
        (
            "- urgency today/soon/future: "
            f"`{summary.get('urgency_today_count', 0)}/"
            f"{summary.get('urgency_soon_count', 0)}/"
            f"{summary.get('urgency_future_count', 0)}`"
        ),
        (
            "- first action: "
            f"`{summary.get('first_target_id', '-')}` "
            f"`{summary.get('first_action_status', '-')}` "
            f"`{summary.get('first_required_operator_fields', '-')}` "
            f"`{summary.get('first_blockers', '-')}`"
        ),
        f"- fill surface: `{summary.get('first_fill_surface', '-')}`",
        f"- next action: {summary.get('next_action', '-')}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
        "## Action Rows",
        "",
        "| rank | target | urgency | action status | required fields | blockers | decision file |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("queue_rank", "")),
                    f"`{row.get('target_id', '')}`",
                    f"`{row.get('urgency', '')}`",
                    f"`{row.get('action_status', '')}`",
                    f"`{row.get('required_operator_fields', '')}`",
                    f"`{row.get('blockers', '') or '-'}`",
                    f"`{row.get('decision_md', '')}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Files", ""])
    source_files = payload.get("source_files")
    if isinstance(source_files, dict):
        for key, value in source_files.items():
            lines.append(f"- {key}: `{value}`")
    lines.append("")
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-rule-gate-json", default=DEFAULT_DECISION_RULE_GATE_JSON)
    parser.add_argument("--operator-decision-kit-json", default=DEFAULT_OPERATOR_DECISION_KIT_JSON)
    parser.add_argument(
        "--operator-decision-kit-completion-audit-json",
        default=DEFAULT_OPERATOR_DECISION_KIT_COMPLETION_AUDIT_JSON,
    )
    parser.add_argument("--active-manifest-lock-json", default=DEFAULT_ACTIVE_MANIFEST_LOCK_JSON)
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
