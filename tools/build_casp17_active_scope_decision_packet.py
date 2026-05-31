#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "casp17/casp17_active_scope_decision_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_active_scope_decision_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ACTIVE_SCOPE_DECISION.md"

ROW_COLUMNS = ["lane", "participation_status", "priority", "reason", "next_action"]

DEFAULT_REASON = (
    "operator_not_pi_capri_registration_requires_pi_or_research_group_lead"
)
CLAIM_BOUNDARY = (
    "Local scope-decision packet only. It records operator participation scope for CASP17/CAPRI planning, "
    "does not register for CASP or CAPRI, does not submit models, and does not claim official performance."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    capri_status = args.capri_participation_status
    reason = args.capri_hold_reason
    rows = [
        {
            "lane": "casp17_historical_benchmark",
            "participation_status": "active",
            "priority": 1,
            "reason": "required_to_raise_scaffold_score_from_65_to_90",
            "next_action": "clear historical non-CASP17 target identity, no-leak provenance, native files, and prediction files",
        },
        {
            "lane": "casp17_competitive_floor",
            "participation_status": "active",
            "priority": 2,
            "reason": "required_to_raise_competitive_proof_from_15_25_to_85_90",
            "next_action": "fill the 15-row competitive-floor batch after cleared historical identities are available",
        },
        {
            "lane": "casp17_3d_object_library",
            "participation_status": "active",
            "priority": 3,
            "reason": "required_for_per-object_review_and_submission_readiness",
            "next_action": "keep per-protein folders, per-chain viewers, projections, and audits green",
        },
        {
            "lane": "capri_round65",
            "participation_status": capri_status,
            "priority": 0,
            "reason": reason,
            "next_action": "preserve CAPRI artifacts as context only until a PI or research-group lead confirms registration",
        },
    ]
    summary = {
        "packet_type": "casp17_active_scope_decision",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope_decision_status": "casp17_only_active",
        "active_competition_scope": "casp17_only",
        "casp17_continuation_status": "active",
        "casp17_priority_status": "historical_benchmark_then_competitive_floor",
        "capri_round65_participation_status": capri_status,
        "capri_round65_hold_reason": reason,
        "capri_round65_artifact_policy": "preserve_context_no_registration_no_submission",
        "capri_round65_not_active_blocker": True,
        "active_lane_count": sum(1 for row in rows if row["participation_status"] == "active"),
        "deferred_lane_count": sum(1 for row in rows if str(row["participation_status"]).startswith("deferred")),
        "row_count": len(rows),
        "first_next_action": rows[0]["next_action"],
        "out_json": _artifact(args.out_json),
        "out_csv": _artifact(args.out_csv),
        "out_md": _artifact(args.out_md),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Active Scope Decision",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- scope decision: `{summary['active_competition_scope']}`",
        f"- CASP17 continuation: `{summary['casp17_continuation_status']}`",
        f"- CASP17 priority: `{summary['casp17_priority_status']}`",
        f"- CAPRI Round 65 participation: `{summary['capri_round65_participation_status']}`",
        f"- CAPRI hold reason: `{summary['capri_round65_hold_reason']}`",
        f"- CAPRI artifact policy: `{summary['capri_round65_artifact_policy']}`",
        f"- next action: {summary['first_next_action']}",
        "",
        "## Lane Policy",
        "",
        "| lane | status | priority | reason | next action |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane']}` | `{row['participation_status']}` | {row['priority']} | "
            f"`{row['reason']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CASP17 active scope decision packet.")
    parser.add_argument("--capri-participation-status", default="deferred_pi_required")
    parser.add_argument("--capri-hold-reason", default=DEFAULT_REASON)
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
