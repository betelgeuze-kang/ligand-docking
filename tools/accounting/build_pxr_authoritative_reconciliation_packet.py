#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_INTAKE_JSON = RUNS / "pxr_unresolved_evidence_capture_intake_current.json"
DEFAULT_REQUEST_JSON = RUNS / "pxr_blocked_evidence_request_packet_current.json"
DEFAULT_GATE_JSON = RUNS / "pxr_blocked_row_promotion_gate_current.json"
DEFAULT_FILL_READINESS_JSON = RUNS / "pxr_packet_fill_readiness_current.json"
DEFAULT_WORKBOOK_JSON = RUNS / "pxr_packet_replacement_workbook_current.json"
DEFAULT_OUT_JSON = RUNS / "pxr_authoritative_reconciliation_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_authoritative_reconciliation_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_authoritative_reconciliation_packet_current.md"

CLAIM_BOUNDARY = (
    "PXR authoritative reconciliation packet only; reconciles capture/intake acceptance, packet-fill readiness, "
    "blocked-row evidence requests, and promotion gates. It does not authoritatively apply rows, promote PXR scope, "
    "run docking, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _rows_by_step(payload: dict[str, Any], key: str = "rows") -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get(key, []) or []
        if isinstance(row, dict) and _text(row.get("packet_step"))
    }


def _readiness_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _rows_by_step(payload, "readiness_rows")


def _workbook_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _rows_by_step(payload, "workbook_rows")


def build_payload(
    *,
    intake_payload: dict[str, Any],
    request_payload: dict[str, Any],
    gate_payload: dict[str, Any],
    fill_readiness_payload: dict[str, Any],
    workbook_payload: dict[str, Any],
) -> dict[str, Any]:
    intake = _summary(intake_payload)
    request = _summary(request_payload)
    gate = _summary(gate_payload)
    readiness = _summary(fill_readiness_payload)
    request_by_step = _rows_by_step(request_payload)
    gate_by_step = _rows_by_step(gate_payload)
    readiness_by_step = _readiness_by_step(fill_readiness_payload)
    workbook_by_step = _workbook_by_step(workbook_payload)

    rows: list[dict[str, Any]] = []
    for rank, packet_step in enumerate(sorted(request_by_step), start=1):
        request_row = request_by_step[packet_step]
        gate_row = gate_by_step.get(packet_step, {})
        readiness_row = readiness_by_step.get(packet_step, {})
        workbook_row = workbook_by_step.get(packet_step, {})
        authoritative_allowed = gate_row.get("authoritative_apply_allowed") is True
        claim_ready = gate_row.get("claim_safe_quantitative_ready") is True
        ready_for_apply = _text(readiness_row.get("ready_for_apply")).lower() == "yes"
        missing = _text(gate_row.get("readiness_missing_fields")) or _text(readiness_row.get("required_missing_fields")) or _text(
            workbook_row.get("required_missing_fields")
        )
        reconciliation_status = (
            "authoritative_apply_allowed"
            if authoritative_allowed
            else "capture_or_workbook_present_but_authoritative_apply_blocked"
        )
        rows.append(
            {
                "rank": rank,
                "packet_step": packet_step,
                "candidate_name": _text(request_row.get("candidate_name")) or _text(gate_row.get("ligand")),
                "current_label": _text(request_row.get("current_binder_label")),
                "review_bucket": _text(gate_row.get("review_bucket")) or _text(request_row.get("review_bucket")),
                "request_mode": _text(request_row.get("request_mode")),
                "readiness_ready_for_apply": ready_for_apply,
                "readiness_missing_fields": missing,
                "workbook_replacement_ligand_id": _text(workbook_row.get("replacement_ligand_id")),
                "workbook_row_ready_for_apply": _text(workbook_row.get("row_ready_for_apply")),
                "gate_authoritative_apply_allowed": authoritative_allowed,
                "gate_claim_safe_quantitative_ready": claim_ready,
                "fail_closed_blockers": _text(gate_row.get("fail_closed_blockers")) or _text(request_row.get("fail_closed_blockers")),
                "reconciliation_status": reconciliation_status,
                "capture_intake_applied": intake.get("intake_applied") is True,
                "scope_promotion_allowed": False,
                "next_required_action": (
                    "Resolve this blocked row with exact human NR1I2/PXR quantitative evidence, then rerun fill-readiness and promotion gates."
                ),
            }
        )

    blocked_rows = [row for row in rows if not row["gate_authoritative_apply_allowed"]]
    ready_but_blocked_rows = [row for row in blocked_rows if row["readiness_ready_for_apply"]]
    request_count_matches_gate = _int(request.get("request_row_count")) == _int(gate.get("blocked_row_count")) == len(rows)
    no_blocked_rows = (
        _int(readiness.get("blocked_row_count")) == 0
        and _int(gate.get("blocked_row_count")) == 0
        and _int(readiness.get("ready_for_apply_row_count")) > 0
    )
    authoritative_allowed_count = (
        _int(readiness.get("ready_for_apply_row_count"))
        if no_blocked_rows
        else _int(gate.get("authoritative_apply_allowed_count"))
    )
    claim_safe_count = (
        _int(readiness.get("ready_for_apply_row_count"))
        if no_blocked_rows
        else _int(gate.get("claim_safe_quantitative_ready_count"))
    )
    summary = {
        "packet_type": "pxr_authoritative_reconciliation_packet",
        "reconciliation_packet_ready": True,
        "intake_applied": intake.get("intake_applied") is True,
        "manual_commit_override_count": _int(intake.get("manual_commit_override_count")),
        "captured_supportive_count": _int(intake.get("captured_supportive_count")),
        "request_row_count": _int(request.get("request_row_count")),
        "gate_blocked_row_count": _int(gate.get("blocked_row_count")),
        "reconciled_blocked_row_count": len(rows),
        "request_count_matches_gate": request_count_matches_gate,
        "fill_ready_for_apply_row_count": _int(readiness.get("ready_for_apply_row_count")),
        "fill_blocked_row_count": _int(readiness.get("blocked_row_count")),
        "authoritative_apply_allowed_count": authoritative_allowed_count,
        "claim_safe_quantitative_ready_count": claim_safe_count,
        "ready_but_blocked_row_count": len(ready_but_blocked_rows),
        "authoritative_promotion_allowed": no_blocked_rows,
        "scope_promotion_allowed": no_blocked_rows,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "PXR authoritative replacement workbook has no blocked rows; rerun exact-review, source-modality, curated freeze/materialization, and scope breadth gates."
            if no_blocked_rows
            else "Keep PXR scope blocked: capture/intake acceptance is not authoritative apply. Resolve the six blocked rows with exact human NR1I2/PXR quantitative evidence."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# PXR Authoritative Reconciliation Packet",
        "",
        f"- reconciliation_packet_ready: `{s['reconciliation_packet_ready']}`",
        f"- intake_applied: `{s['intake_applied']}`",
        f"- manual_commit_override_count: `{s['manual_commit_override_count']}`",
        f"- captured_supportive_count: `{s['captured_supportive_count']}`",
        f"- request_row_count: `{s['request_row_count']}`",
        f"- gate_blocked_row_count: `{s['gate_blocked_row_count']}`",
        f"- reconciled_blocked_row_count: `{s['reconciled_blocked_row_count']}`",
        f"- request_count_matches_gate: `{s['request_count_matches_gate']}`",
        f"- fill_ready_for_apply_row_count: `{s['fill_ready_for_apply_row_count']}`",
        f"- fill_blocked_row_count: `{s['fill_blocked_row_count']}`",
        f"- authoritative_apply_allowed_count: `{s['authoritative_apply_allowed_count']}`",
        f"- claim_safe_quantitative_ready_count: `{s['claim_safe_quantitative_ready_count']}`",
        f"- authoritative_promotion_allowed: `{s['authoritative_promotion_allowed']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Reconciled Blocked Rows",
        "",
        "| rank | step | candidate | bucket | mode | missing | allowed | status |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['review_bucket']}` | `{row['request_mode']}` | `{row['readiness_missing_fields'] or '-'}` | "
            f"`{row['gate_authoritative_apply_allowed']}` | `{row['reconciliation_status']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PXR authoritative reconciliation packet.")
    parser.add_argument("--intake-json", default=str(DEFAULT_INTAKE_JSON))
    parser.add_argument("--request-json", default=str(DEFAULT_REQUEST_JSON))
    parser.add_argument("--gate-json", default=str(DEFAULT_GATE_JSON))
    parser.add_argument("--fill-readiness-json", default=str(DEFAULT_FILL_READINESS_JSON))
    parser.add_argument("--workbook-json", default=str(DEFAULT_WORKBOOK_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        intake_payload=_load_json(args.intake_json),
        request_payload=_load_json(args.request_json),
        gate_payload=_load_json(args.gate_json),
        fill_readiness_payload=_load_json(args.fill_readiness_json),
        workbook_payload=_load_json(args.workbook_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
