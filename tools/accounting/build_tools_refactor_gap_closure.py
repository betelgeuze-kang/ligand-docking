#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.accounting.build_tools_package_batch3_review_plan import build_tools_package_batch3_review_plan
from tools.accounting.build_tools_package_other_review_classification_plan import (
    build_tools_package_other_review_classification_plan,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/tools_refactor_gap_closure_current.json"
DEFAULT_OUT_CSV = "runs/tools_refactor_gap_closure_current.csv"
DEFAULT_OUT_MD = "runs/tools_refactor_gap_closure_current.md"

CLAIM_BOUNDARY = (
    "Tools refactor gap closure status only; it audits other_review classification and batch3 review lane "
    "decomposition without moving files or rewriting imports."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _row(gap_id: str, gap: str, status: str, evidence: str, observed: str, next_action: str) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "gap": gap,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "release_blocker": status != "closed",
        "move_executed": False,
        "external_state_mutated": False,
    }


def build_tools_refactor_gap_closure(
    *,
    other_review_plan_packet: dict[str, Any] | None = None,
    batch3_plan_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    other_review = other_review_plan_packet or build_tools_package_other_review_classification_plan()
    batch3 = batch3_plan_packet or build_tools_package_batch3_review_plan()
    other_summary = _summary(other_review)
    batch3_summary = _summary(batch3)
    other_closed = bool(other_summary.get("plan_ready"))
    batch3_closed = bool(batch3_summary.get("plan_ready"))
    rows = [
        _row(
            "TOOLS-OTHER",
            "other_review package classification lane",
            "closed" if other_closed else "open",
            "runs/tools_package_other_review_classification_plan_current.json",
            f"candidate_count={other_summary.get('candidate_count')}; unclassified_count={other_summary.get('unclassified_count')}",
            "Apply reclassified package buckets in approved migration slices.",
        ),
        _row(
            "TOOLS-BATCH3",
            "batch3 high-reference review lane decomposition",
            "closed" if batch3_closed else "open",
            "runs/tools_package_batch3_review_plan_current.json",
            f"batch3_total_count={batch3_summary.get('batch3_total_count')}; first_slice_candidate_count={batch3_summary.get('first_slice_candidate_count')}",
            "Start with lane_a_zero_test_low_internal slice before manual high-reference lanes.",
        ),
    ]
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "tools_refactor_gap_closure",
        "status": "tools_refactor_gap_closure_complete" if not open_rows else "blocked_tools_refactor_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "closed_gap_ids": [row["gap_id"] for row in closed_rows],
        "open_gap_ids": [row["gap_id"] for row in open_rows],
        "current_primary_open_gap_id": first_open["gap_id"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All tools refactor planning gaps are closed.",
        "move_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Refactor Gap Closure",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build tools refactor gap closure status.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_tools_refactor_gap_closure()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
