#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DONOR_POLICY_JSON = "runs/transporter_fit_donor_policy_decision_current.json"
DEFAULT_AQP1_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_AQP1_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_GLUT1_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_GLUT1_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_READINESS_JSON = "runs/transporter_membrane_readiness_current.json"
DEFAULT_APPLY_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_BINDER_PROMOTION_GATE_JSON = "runs/transporter_binder_promotion_gate_current.json"
DEFAULT_OUT_JSON = "runs/transporter_donor_policy_reopen_checklist_current.json"
DEFAULT_OUT_CSV = "runs/transporter_donor_policy_reopen_checklist_current.csv"
DEFAULT_OUT_MD = "runs/transporter_donor_policy_reopen_checklist_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    donor_policy: dict[str, Any],
    aqp1_queue: dict[str, Any],
    aqp1_verdict: dict[str, Any],
    glut1_queue: dict[str, Any],
    glut1_verdict: dict[str, Any],
    readiness: dict[str, Any],
    apply_status: dict[str, Any] | None = None,
    binder_promotion_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    donor_summary = dict(donor_policy.get("summary", {}) or {})
    aqp1_queue_summary = dict(aqp1_queue.get("summary", {}) or {})
    aqp1_verdict_summary = dict(aqp1_verdict.get("summary", {}) or {})
    glut1_queue_summary = dict(glut1_queue.get("summary", {}) or {})
    glut1_verdict_summary = dict(glut1_verdict.get("summary", {}) or {})
    readiness_summary = dict(readiness.get("summary", {}) or {})
    apply_summary = dict((apply_status or {}).get("summary", {}) or {})
    binder_gate_summary = dict((binder_promotion_gate or {}).get("summary", {}) or {})

    aqp1_binder_defer = int(aqp1_queue_summary.get("defer_binder_count", 0) or 0)
    glut1_binder_defer = int(glut1_queue_summary.get("defer_binder_count", 0) or 0)
    p0_open_count = int(readiness_summary.get("p0_open_count", 0) or 0)
    aqp1_review_only = int(aqp1_verdict_summary.get("keep_review_only_count", 0) or 0)
    glut1_review_only = int(glut1_verdict_summary.get("keep_review_only_count", 0) or 0)
    placeholder_driven_rows = int(apply_summary.get("placeholder_driven_rows", 0) or 0)
    staged_non_authoritative_rows = int(apply_summary.get("staged_non_authoritative_rows", 0) or 0)
    ready_for_apply_rows = int(apply_summary.get("ready_for_apply_rows", 0) or 0)
    has_non_placeholder_packet_row = (
        bool(apply_summary)
        and placeholder_driven_rows == 0
        and (staged_non_authoritative_rows + ready_for_apply_rows) > 0
    )
    binder_promotion_ready = bool(binder_gate_summary.get("binder_promotion_ready", False))
    binder_gate_signal = (
        str(binder_gate_summary.get("primary_blocker_signal", "")).strip()
        or f"aqp1_keep_review_only={aqp1_review_only}; glut1_keep_review_only={glut1_review_only}"
    )

    rows = [
        {
            "check_id": "candidate_has_non_placeholder_packet_row",
            "status": "ready" if has_non_placeholder_packet_row else "blocked",
            "current_value": (
                f"placeholder_driven_rows={placeholder_driven_rows}; "
                f"staged_non_authoritative_rows={staged_non_authoritative_rows}; "
                f"ready_for_apply_rows={ready_for_apply_rows}"
                if apply_summary
                else f"aqp1_binder_defer={aqp1_binder_defer}; glut1_binder_defer={glut1_binder_defer}"
            ),
            "ready_when": "At least one transporter binder row is no longer placeholder-driven.",
        },
        {
            "check_id": "p0_scaffold_open_count_zero",
            "status": "blocked" if p0_open_count > 0 else "ready",
            "current_value": p0_open_count,
            "ready_when": "Transporter P0 open count reaches 0.",
        },
        {
            "check_id": "manual_review_only_is_not_authoritative_apply",
            "status": "ready" if binder_promotion_ready else "blocked",
            "current_value": binder_gate_signal,
            "ready_when": "A reviewed transporter candidate is upgraded from manual-review only to a claim-safe packet row with provenance.",
        },
    ]

    summary = {
        "decision_status": donor_summary.get("decision_status", ""),
        "scaffold_fit_donor_target": donor_summary.get("scaffold_fit_donor_target", ""),
        "ready_check_count": sum(1 for row in rows if row["status"] == "ready"),
        "blocked_check_count": sum(1 for row in rows if row["status"] == "blocked"),
        "reopen_ready": all(row["status"] == "ready" for row in rows),
        "next_required_step": (
            "Keep the transporter donor policy frozen for scaffold-only use. Re-open only after transporter P0 scaffold blockers are cleared "
            "and at least one binder row has claim-safe binding/kcal provenance plus a synchronized workbook row."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Donor Policy Reopen Checklist",
        "",
        f"- decision_status: `{summary['decision_status']}`",
        f"- scaffold_fit_donor_target: `{summary['scaffold_fit_donor_target']}`",
        f"- ready_check_count: `{summary['ready_check_count']}`",
        f"- blocked_check_count: `{summary['blocked_check_count']}`",
        f"- reopen_ready: `{summary['reopen_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Checks",
        "",
        "| check_id | status | current_value | ready_when |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['current_value']}` | {row['ready_when']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the transporter donor-policy reopen checklist.")
    parser.add_argument("--donor-policy-json", default=DEFAULT_DONOR_POLICY_JSON)
    parser.add_argument("--aqp1-queue-json", default=DEFAULT_AQP1_QUEUE_JSON)
    parser.add_argument("--aqp1-verdict-json", default=DEFAULT_AQP1_VERDICT_JSON)
    parser.add_argument("--glut1-queue-json", default=DEFAULT_GLUT1_QUEUE_JSON)
    parser.add_argument("--glut1-verdict-json", default=DEFAULT_GLUT1_VERDICT_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--apply-status-json", default=DEFAULT_APPLY_STATUS_JSON)
    parser.add_argument("--binder-promotion-gate-json", default=DEFAULT_BINDER_PROMOTION_GATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.donor_policy_json),
        _load_json(args.aqp1_queue_json),
        _load_json(args.aqp1_verdict_json),
        _load_json(args.glut1_queue_json),
        _load_json(args.glut1_verdict_json),
        _load_json(args.readiness_json),
        _load_json(args.apply_status_json),
        _load_json(args.binder_promotion_gate_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
