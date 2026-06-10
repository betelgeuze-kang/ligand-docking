#!/usr/bin/env python3
"""Operator-facing external competition track status (CAMEO live / CASP external)."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/competition_external_operator_track_current.json"
DEFAULT_OUT_MD = "docs/competition_benchmark_external_operator_runbook.md"

CLAIM_BOUNDARY = (
    "Competition external operator track only; it documents separate operator actions for live CAMEO and "
    "external CASP credibility without submitting predictions, sending email, or mutating external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_competition_external_operator_track() -> dict[str, Any]:
    rollup = _summary(_read_json("runs/competition_benchmark_rollup_current.json"))
    registration = _summary(_read_json("runs/cameo_public_registration_approval_gate_current.json"))
    email = _summary(_read_json("runs/cameo_outbound_email_send_preflight_current.json"))
    rollout = _summary(_read_json("runs/product_rollout_execution_readiness_current.json"))
    report = _summary(_read_json("runs/architecture_validation_package_report_current.json"))
    rows = [
        {
            "track_id": "CAMEO-LIVE-REGISTRATION",
            "phase": "C-P1",
            "status": "ready_for_separate_operator_review"
            if registration.get("authorized_for_registration_review") is True
            else "blocked",
            "next_action": "Operator reviews registration approval intake; no auto-registration is performed.",
            "artifact": "runs/cameo_public_registration_approval_gate_current.json",
        },
        {
            "track_id": "CAMEO-LIVE-EMAIL",
            "phase": "C-P1",
            "status": "ready_for_separate_operator_send"
            if email.get("authorized_for_separate_operator_send") is True
            else "blocked",
            "next_action": "Operator reviews outbound email send preflight before any separate SMTP send.",
            "artifact": "runs/cameo_outbound_email_send_preflight_current.json",
        },
        {
            "track_id": "CAMEO-LIVE-DEPLOY",
            "phase": "C-P1",
            "status": "ready" if _text(rollout.get("status")) == "product_rollout_execution_readiness_ready" else "blocked",
            "next_action": "Execute separate operator-approved rollout using deploy/product_rollout_runbook.md.",
            "artifact": "runs/product_rollout_execution_readiness_current.json",
        },
        {
            "track_id": "CAMEO-OFFICIAL-RESULTS",
            "phase": "C-P2",
            "status": "local_intake_ready" if rollup.get("cameo_official_results_used") is True else "blocked",
            "next_action": "Add official CAMEO assessment rows to runs/cameo_official_results_operator_intake.csv from organizer pages.",
            "artifact": "runs/cameo_official_results_operator_intake.csv",
        },
        {
            "track_id": "CASP-STRICT-BLIND-EXTERNAL",
            "phase": "C-P3",
            "status": "local_gate_ready" if rollup.get("casp_strict_blind_first_slot_ready") is True else "blocked",
            "next_action": "Replace replay placeholder PDBs with verified pre-native predictions before any external CASP claim.",
            "artifact": "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json",
        },
        {
            "track_id": "CASP-WINNER-BAND-EXTERNAL",
            "phase": "C-P4",
            "status": "local_review_ready" if int(rollup.get("casp_winner_band_unblocked_count") or 0) > 0 else "blocked",
            "next_action": "Promote only after row-level metric surface and no-leak replay evidence pass architecture validation depth checks.",
            "artifact": "casp17/casp17_historical_winner_normalized_bands_current.json",
        },
    ]
    blocked = [row for row in rows if row["status"] == "blocked"]
    summary = {
        "packet_type": "competition_external_operator_track",
        "status": "competition_external_operator_track_ready",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "track_count": len(rows),
        "blocked_track_count": len(blocked),
        "architecture_validation_status": _text(report.get("status")),
        "evidence_depth_tier": _text(report.get("evidence_depth_tier")),
        "overclaim_warning_count": int(report.get("overclaim_warning_count") or 0),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": blocked[0]["next_action"] if blocked else "All external operator tracks have local preflight artifacts; external actions remain operator-only.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Competition Benchmark External Operator Runbook",
        "",
        "Separate operator actions for **live CAMEO** and **external CASP credibility**. Local builders do not perform these steps.",
        "",
        f"- status: `{s['status']}`",
        f"- architecture_validation_status: `{s['architecture_validation_status']}`",
        f"- evidence_depth_tier: `{s['evidence_depth_tier']}`",
        f"- overclaim_warning_count: `{s['overclaim_warning_count']}`",
        "",
        "## Tracks",
        "",
        "| track_id | phase | status | artifact | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['track_id']}` | `{row['phase']}` | `{row['status']}` | `{row['artifact']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build external competition operator track status.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_competition_external_operator_track()
    _resolve(args.out_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
