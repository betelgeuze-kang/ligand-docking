#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SEQUENCE_PACKET_JSON = "runs/casp17_sequence_packet_current.json"
DEFAULT_SUBMISSION_GATE_JSON = "runs/casp17_submission_gate_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_target_work_queue_current.json"
DEFAULT_OUT_CSV = "runs/casp17_target_work_queue_current.csv"
DEFAULT_OUT_MD = "runs/casp17_target_work_queue_current.md"


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "lane",
        "recommended_action",
        "work_priority",
        "days_to_human_expiration",
        "residue_count",
        "sequence_entry_count",
        "risk_tier",
        "submission_decision",
        "next_required_step",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _sequence_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    return {_text(row.get("target_id")): row for row in rows if isinstance(row, dict)}


def _submission_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("target_rows")
    if not isinstance(rows, list):
        return {}
    return {_text(row.get("target_id")): row for row in rows if isinstance(row, dict)}


def _complexity_risk(residue_count: int, sequence_entry_count: int, description: str) -> tuple[str, int]:
    desc = description.lower()
    penalty = residue_count // 10 + max(sequence_entry_count - 1, 0) * 40
    if any(token in desc for token in ("antibody", "fab", "complex")):
        penalty += 45
    if residue_count >= 1200 or sequence_entry_count >= 5:
        return "high", penalty + 80
    if residue_count >= 700 or sequence_entry_count >= 3:
        return "medium", penalty + 35
    return "low", penalty


def _recommend_action(
    *,
    days_to_human: int,
    sequence_ready: bool,
    risk_tier: str,
    lane: str,
    submission_decision: str,
) -> tuple[str, str, int]:
    if not sequence_ready:
        return "materialize_sequence_first", "Run build_casp17_sequence_packet.py for this target.", 0
    if days_to_human < 0:
        return "closed_do_not_submit", "Target human deadline has passed.", 0
    if days_to_human <= 1:
        return (
            "dry_run_only_deadline_too_close",
            "Use only as a pipeline rehearsal; do not begin public submission unless a prediction is already validated.",
            50,
        )
    if lane == "organic_ligand_protein_complexes":
        return (
            "primary_lane_attempt_when_prediction_ready",
            "Generate ligand-aware TS/LG candidate, run TS/LG validation, then re-run submission gate.",
            320,
        )
    if risk_tier == "low":
        return (
            "first_internal_attempt",
            "Generate TS model 1, run TS validation, geometry sanity, confidence calibration, then re-run submission gate.",
            260,
        )
    if risk_tier == "medium":
        return (
            "second_wave_complex_attempt",
            "Attempt after the first low-risk internal target has a validated end-to-end packet.",
            180,
        )
    if submission_decision == "submission_go":
        return "submission_review_required", "Human review required before any external submission.", 200
    return (
        "defer_high_complexity_complex",
        "Keep in watchlist; needs complex-specific modeling/validation capacity before public submission.",
        90,
    )


def _queue_row(row: dict[str, Any], sequence_row: dict[str, Any] | None, submission_row: dict[str, Any] | None) -> dict[str, Any]:
    sequence_row = sequence_row or {}
    submission_row = submission_row or {}
    target_id = _text(row.get("target_id"))
    lane = _text(row.get("lane_recommendation"))
    days_to_human = _int(row.get("days_to_human_expiration"), default=-999)
    sequence_ready = _text(sequence_row.get("sequence_status")) == "ready"
    residue_count = _int(sequence_row.get("residue_count") or row.get("residues"), default=0)
    sequence_entry_count = _int(sequence_row.get("entry_count"), default=0)
    risk_tier, complexity_penalty = _complexity_risk(residue_count, sequence_entry_count, _text(row.get("description")))
    submission_decision = _text(submission_row.get("submission_decision")) or "not_gated"
    recommended_action, next_required_step, base_priority = _recommend_action(
        days_to_human=days_to_human,
        sequence_ready=sequence_ready,
        risk_tier=risk_tier,
        lane=lane,
        submission_decision=submission_decision,
    )
    urgency_bonus = max(0, 14 - max(days_to_human, 0)) * 4 if days_to_human >= 0 else 0
    work_priority = max(0, base_priority + urgency_bonus - complexity_penalty)
    if recommended_action == "dry_run_only_deadline_too_close":
        work_priority = min(work_priority, 40)
    if recommended_action.startswith("defer"):
        work_priority = min(work_priority, 60)
    return {
        "target_id": target_id,
        "description": _text(row.get("description")),
        "lane": lane,
        "recommended_action": recommended_action,
        "work_priority": work_priority,
        "days_to_human_expiration": days_to_human,
        "human_expiration": _text(row.get("human_expiration")),
        "qa_expiration": _text(row.get("qa_expiration")),
        "residue_count": residue_count,
        "sequence_entry_count": sequence_entry_count,
        "risk_tier": risk_tier,
        "sequence_status": _text(sequence_row.get("sequence_status")) or "missing",
        "sequence_path": _text(sequence_row.get("sequence_path")),
        "submission_decision": submission_decision,
        "submission_blockers": _text(submission_row.get("blockers")),
        "next_required_step": next_required_step,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    watchlist = _read_json(args.watchlist_json)
    sequence_packet = _read_json(args.sequence_packet_json)
    submission_gate = _read_json(args.submission_gate_json)
    sequence_by_target = _sequence_index(sequence_packet)
    submission_by_target = _submission_index(submission_gate)
    watch_rows = watchlist.get("rows")
    if not isinstance(watch_rows, list):
        watch_rows = []
    selected_rows = [
        row
        for row in watch_rows
        if isinstance(row, dict)
        and row.get("human_open") is True
        and row.get("lane_recommendation") in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}
    ]
    queue_rows = [
        _queue_row(row, sequence_by_target.get(_text(row.get("target_id"))), submission_by_target.get(_text(row.get("target_id"))))
        for row in selected_rows
    ]
    queue_rows.sort(key=lambda row: (-_int(row.get("work_priority")), _int(row.get("days_to_human_expiration")), row.get("target_id", "")))
    action_counts: dict[str, int] = defaultdict_int()
    for row in queue_rows:
        action_counts[row["recommended_action"]] += 1
    summary = {
        "packet_type": "casp17_target_work_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "watchlist_json": _artifact(args.watchlist_json),
        "sequence_packet_json": _artifact(args.sequence_packet_json),
        "submission_gate_json": _artifact(args.submission_gate_json),
        "selected_target_count": len(queue_rows),
        "top_target_id": queue_rows[0]["target_id"] if queue_rows else "",
        "top_action": queue_rows[0]["recommended_action"] if queue_rows else "",
        "action_counts": dict(action_counts),
        "claim_boundary": "Internal CASP17 work ordering only; not a submission recommendation without a green target gate.",
    }
    return {"summary": summary, "rows": queue_rows}


def defaultdict_int() -> dict[str, int]:
    return defaultdict(int)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Work Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- selected targets: `{summary['selected_target_count']}`",
        f"- top target: `{summary['top_target_id']}`",
        f"- top action: `{summary['top_action']}`",
        "",
        "## Queue",
        "",
        "| target | action | priority | days left | residues | chains | risk | gate | next step |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"][:20]:
        lines.append(
            f"| `{row['target_id']}` | `{row['recommended_action']}` | {row['work_priority']} | "
            f"{row['days_to_human_expiration']} | {row['residue_count']} | {row['sequence_entry_count']} | "
            f"`{row['risk_tier']}` | `{row['submission_decision']}` | {row['next_required_step']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_open_selected_lane_targets` | 0 | 0 | 0 | 0 | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a ranked internal CASP17 target work queue.")
    parser.add_argument("--watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--sequence-packet-json", default=DEFAULT_SEQUENCE_PACKET_JSON)
    parser.add_argument("--submission-gate-json", default=DEFAULT_SUBMISSION_GATE_JSON)
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


if __name__ == "__main__":
    main()
