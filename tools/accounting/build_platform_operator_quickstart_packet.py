#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.operator_surface_contracts import IDP_SAFE_SCOPE_CONTROLLED_PRETEST

RUNS = Path("runs")

PLATFORM_INDEX_JSON = RUNS / "platform_packet_index_current.json"
EXECUTION_DASHBOARD_JSON = RUNS / "execution_handoff_dashboard_current.json"

OUT_JSON = RUNS / "platform_operator_quickstart_packet_current.json"
OUT_CSV = RUNS / "platform_operator_quickstart_packet_current.csv"
OUT_MD = RUNS / "platform_operator_quickstart_packet_current.md"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def build_rows(execution_dashboard: dict) -> list[dict]:
    rows: list[dict] = []
    for row in execution_dashboard["rows"]:
        family = row["family"]
        lane = row["priority_lane"]
        blocker = row["primary_blocker"] or "none"
        action = row["next_required_step"]

        if lane == "run_now":
            do_now = f"Run only within `{row['runtime_scope_now']}`."
        elif lane == "prepare_next":
            if family == "non_kinase_enzyme_ca2":
                do_now = "Keep CA2 in review-only/conflict closure; do not treat it as authoritative negative closure or promote to run-now."
            else:
                do_now = "Close evidence and packet blockers; do not promote to run-now yet."
        else:
            do_now = "Keep in reviewer-only flow; do not convert draft packets into authoritative apply."

        rows.append(
            {
                "family": family,
                "lane": lane,
                "scope_now": row["runtime_scope_now"],
                "current_state": row["current_state"],
                "primary_blocker": blocker,
                "operator_action": do_now,
                "next_required_step": action,
            }
        )
    return rows


def build_summary(platform_index: dict, execution_dashboard: dict) -> dict:
    idx = platform_index["summary"]
    exe = execution_dashboard["summary"]
    return {
        "packet_count": idx["packet_count"],
        "run_now_count": exe["run_now_count"],
        "prepare_next_count": exe["prepare_next_count"],
        "manual_review_only_count": exe["manual_review_only_count"],
        "core_commercial_lane_score": exe["core_commercial_lane_score"],
        "all_category_expansion_score": exe["all_category_expansion_score"],
        "highest_gap_family": exe["highest_gap_family"],
        "operator_rule": "Protect the commercial core, advance only scoped run-now lanes, and keep expansion families inside evidence-closure or manual-review lanes until their blockers are explicitly cleared.",
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def render_family_list(rows: list[dict], lane: str) -> list[str]:
    return [f"`{row['family']}`" for row in rows if row["lane"] == lane]


def write_md(path: Path, summary: dict, rows: list[dict]) -> None:
    run_now = [row for row in rows if row["lane"] == "run_now"]
    prepare_next = [row for row in rows if row["lane"] == "prepare_next"]
    manual_review = [row for row in rows if row["lane"] == "manual_review_only"]

    lines = [
        "# Platform Operator Quickstart Packet",
        "",
        f"- run_now_count: `{summary['run_now_count']}`",
        f"- prepare_next_count: `{summary['prepare_next_count']}`",
        f"- manual_review_only_count: `{summary['manual_review_only_count']}`",
        f"- core_commercial_lane_score: `{summary['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{summary['all_category_expansion_score']}`",
        f"- highest_gap_family: `{summary['highest_gap_family']}`",
        "",
        "## Operator Rule",
        "",
        f"- {summary['operator_rule']}",
        "",
        "## Run-Now Lanes",
        "",
        f"- Families: {', '.join(render_family_list(rows, 'run_now'))}",
        "",
    ]
    for row in run_now:
        lines.append(
            f"- `{row['family']}`: {row['operator_action']} Blocker: `{row['primary_blocker']}`."
        )

    lines.extend(["", "## Prepare-Next Lanes", ""])
    lines.append(f"- Families: {', '.join(render_family_list(rows, 'prepare_next'))}")
    lines.append("")
    for row in prepare_next:
        if row["family"] == "non_kinase_enzyme_ca2":
            lines.append(
                f"- `{row['family']}`: {row['operator_action']} Main blocker: `{row['primary_blocker']}`. Treat CA2 as review-only/conflict closure, not authoritative negative closure."
            )
        else:
            lines.append(
                f"- `{row['family']}`: {row['operator_action']} Main blocker: `{row['primary_blocker']}`."
            )

    lines.extend(["", "## Manual-Review Lane", ""])
    lines.append(f"- Families: {', '.join(render_family_list(rows, 'manual_review_only'))}")
    lines.append("")
    for row in manual_review:
        lines.append(
            f"- `{row['family']}`: {row['operator_action']} Main blocker: `{row['primary_blocker']}`."
        )

    lines.extend(
        [
            "",
            "## What Not To Do",
            "",
            "- Do not reopen the GPCR 100k router while the current endpoint remains router-blocked.",
            f"- Do not broaden IDP beyond `{IDP_SAFE_SCOPE_CONTROLLED_PRETEST}`.",
            "- Do not reinterpret CA2 as authoritative negative closure or promote CA2/PXR from partial authoritative rows into run-now lanes before replacement binding fields close.",
            "- Do not convert transporter draft packets or reviewer notes into authoritative apply.",
            "",
            "## Open Next",
            "",
            "- `runs/platform_packet_index_current.md`",
            "- `runs/execution_handoff_dashboard_current.md`",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    platform_index = load_json(PLATFORM_INDEX_JSON)
    execution_dashboard = load_json(EXECUTION_DASHBOARD_JSON)

    rows = build_rows(execution_dashboard)
    summary = build_summary(platform_index, execution_dashboard)
    payload = {"summary": summary, "rows": rows}

    write_json(OUT_JSON, payload)
    write_csv(OUT_CSV, rows)
    write_md(OUT_MD, summary, rows)


if __name__ == "__main__":
    main()
