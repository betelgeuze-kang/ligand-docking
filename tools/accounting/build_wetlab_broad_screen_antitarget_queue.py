#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_BROAD_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_COMPANION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_RERANK_JSON = "runs/wetlab_broad_screen_target_rerank_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_antitarget_queue_current.md"

ANTITARGET_PRESETS: dict[str, list[dict[str, str | int]]] = {
    "CA IX": [
        {"panel_rank": 1, "anti_target_id": "CA II", "goal": "Deselected canonical carbonic-anhydrase activity before oncology packet escalation."},
        {"panel_rank": 2, "anti_target_id": "CA XII", "goal": "Separate CA IX condition-aware signal from close family tumor-associated carbonic anhydrase behavior."},
    ],
    "SARS-CoV-2 Mpro": [
        {"panel_rank": 1, "anti_target_id": "host cysteine protease sanity panel", "goal": "Screen out generic host cysteine protease reactivity before antiviral promotion."},
    ],
    "T. cruzi PDE": [
        {"panel_rank": 1, "anti_target_id": "human PDE family mini-panel", "goal": "Keep parasite-vs-human PDE separation visible during bulk repurposing triage."},
    ],
    "Cruzain": [
        {"panel_rank": 1, "anti_target_id": "host cysteine protease counterscreen", "goal": "Reject generic cysteine protease binders early."},
        {"panel_rank": 2, "anti_target_id": "thiol-reactivity sanity set", "goal": "Down-rank sticky reactive protease hits before partner outreach."},
    ],
    "SARS-CoV-2 PLpro": [
        {"panel_rank": 1, "anti_target_id": "host DUB-like counterscreen", "goal": "Address host deubiquitinase-like liability for PLpro bulk hits."},
        {"panel_rank": 2, "anti_target_id": "host cysteine protease sanity panel", "goal": "Add a second host-reactivity filter for PLpro candidates."},
    ],
    "ALK2": [
        {"panel_rank": 1, "anti_target_id": "ALK2 wild-type comparator", "goal": "Preserve mutant-vs-wild-type selectivity in kinase outreach."},
        {"panel_rank": 2, "anti_target_id": "neighborhood kinase mini-panel", "goal": "Limit kinome spillover before open-science promotion."},
    ],
    "STK17B (DRAK2)": [
        {"panel_rank": 1, "anti_target_id": "open-probe negative control panel", "goal": "Keep dark-kinase signal anchored to the open-probe ecosystem."},
        {"panel_rank": 2, "anti_target_id": "neighborhood kinase mini-panel", "goal": "Show local kinase selectivity before SGC-style follow-up."},
    ],
    "Leishmania braziliensis DHODH": [
        {"panel_rank": 1, "anti_target_id": "host DHODH counterscreen", "goal": "Protect host-enzyme separation in neglected-disease enzyme discovery."},
    ],
    "Cathepsin K": [
        {"panel_rank": 1, "anti_target_id": "cathepsin family selectivity panel", "goal": "Separate Cathepsin K signal from close family acidic protease behavior."},
        {"panel_rank": 2, "anti_target_id": "acidic-pH specificity panel", "goal": "Keep pH-conditioned specificity explicit in osteology or oncology follow-up."},
    ],
    "Dengue NS2B-NS3 protease": [
        {"panel_rank": 1, "anti_target_id": "flaviviral protease orthogonal panel", "goal": "Test whether shallow-pocket hits generalize cleanly across related viral proteases."},
        {"panel_rank": 2, "anti_target_id": "shallow-pocket negative control panel", "goal": "Reject sticky surface-binding artifacts early."},
    ],
    "DprE1": [
        {"panel_rank": 1, "anti_target_id": "host-enzyme orthogonal panel", "goal": "Avoid over-interpreting target-only bacterial enzyme scores."},
        {"panel_rank": 2, "anti_target_id": "whole-cell orthogonal sanity panel", "goal": "Keep translational sanity attached to DprE1 bulk hits."},
    ],
    "T. cruzi KRS1": [
        {"panel_rank": 1, "anti_target_id": "host aaRS selectivity panel", "goal": "Maintain parasite-vs-host aaRS separation during repurposing triage."},
    ],
    "LRRK2": [
        {"panel_rank": 1, "anti_target_id": "kinase selectivity panel", "goal": "Keep broad kinase spillover visible for LRRK2 repurposing rows."},
        {"panel_rank": 2, "anti_target_id": "CNS liability sanity panel", "goal": "Add translational realism before neurodegeneration outreach."},
    ],
}


def _queue_rows_by_target(queue_payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in ((queue_payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def _target_order(queue_payload: dict[str, Any] | None) -> list[str]:
    ordered: list[str] = []
    for row in ((queue_payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if target_id and target_id not in ordered:
            ordered.append(target_id)
    return ordered


def _companion_map(companion_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in ((companion_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }


def _rerank_map(rerank_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in ((rerank_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }


def build_payload(
    broad_queue_payload: dict[str, Any] | None = None,
    companion_payload: dict[str, Any] | None = None,
    rerank_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_rows_by_target = _queue_rows_by_target(broad_queue_payload)
    target_order = _target_order(broad_queue_payload)
    companion_rows = _companion_map(companion_payload)
    rerank_rows = _rerank_map(rerank_payload)

    rows: list[dict[str, Any]] = []
    queue_rank = 0
    first_actionable: dict[str, Any] | None = None
    primary_bulk_ready_target_count = 0

    for target_id in target_order:
        preset_rows = ANTITARGET_PRESETS.get(target_id, [])
        if not preset_rows:
            continue
        primary_queue_rows = queue_rows_by_target.get(target_id, [])
        companion_row = companion_rows.get(target_id, {})
        rerank_status = str(rerank_rows.get(target_id, {}).get("rerank_status", "bootstrap_only")).strip() or "bootstrap_only"
        primary_gate_open = rerank_status == "full_bulk_top3_ready"
        if primary_gate_open:
            primary_bulk_ready_target_count += 1

        for panel in preset_rows:
            anti_target_id = str(panel["anti_target_id"]).strip()
            panel_rank = int(panel["panel_rank"])
            for shard_index, primary_row in enumerate(primary_queue_rows, start=1):
                queue_rank += 1
                if not primary_gate_open:
                    queue_status = "blocked_on_primary_full_bulk_ready"
                elif first_actionable is None:
                    queue_status = "ready_after_primary_bulk_ready"
                elif first_actionable["primary_target_id"] != target_id:
                    queue_status = "blocked_on_previous_antitarget_target"
                elif first_actionable["anti_target_id"] != anti_target_id:
                    queue_status = "blocked_on_previous_antitarget_panel"
                else:
                    queue_status = "blocked_on_previous_antitarget_shard"

                row = {
                    "queue_rank": queue_rank,
                    "primary_target_id": target_id,
                    "wave": str(primary_row.get("wave", "")).strip(),
                    "primary_shard_id": str(primary_row.get("shard_id", "")).strip(),
                    "anti_target_id": anti_target_id,
                    "anti_target_panel_rank": panel_rank,
                    "panel_goal": str(panel["goal"]).strip(),
                    "primary_companion_panel": str(companion_row.get("primary_companion_panel", "")).strip(),
                    "primary_rerank_status": rerank_status,
                    "primary_gate_open": primary_gate_open,
                    "queue_status": queue_status,
                    "execution_state": (
                        "ready_to_launch" if queue_status.startswith("ready") else "blocked_on_primary_full_bulk_ready" if queue_status == "blocked_on_primary_full_bulk_ready" else "blocked"
                    ),
                }
                rows.append(row)
                if queue_status.startswith("ready") and first_actionable is None:
                    first_actionable = row

    ready_now_row_count = sum(1 for row in rows if str(row.get("queue_status", "")).startswith("ready"))
    blocked_on_primary_bulk_ready_count = sum(1 for row in rows if row.get("queue_status") == "blocked_on_primary_full_bulk_ready")

    if first_actionable:
        next_required_step = (
            f"Launch the anti-target counterscreen queue at {first_actionable['primary_target_id']} -> {first_actionable['anti_target_id']} shard {first_actionable['primary_shard_id']}."
        )
    else:
        next_required_step = "Keep driving primary-target bulk screens until at least one target reaches full_bulk_top3_ready, then open the matching anti-target counterscreen queue."

    return {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_queue_ready",
            "target_count": len({row['primary_target_id'] for row in rows}),
            "panel_count": len({(row['primary_target_id'], row['anti_target_id']) for row in rows}),
            "queue_row_count": len(rows),
            "primary_bulk_ready_target_count": primary_bulk_ready_target_count,
            "ready_now_row_count": ready_now_row_count,
            "blocked_on_primary_bulk_ready_count": blocked_on_primary_bulk_ready_count,
            "first_actionable_primary_target_id": str(first_actionable.get('primary_target_id', '')).strip() if first_actionable else "",
            "first_actionable_anti_target_id": str(first_actionable.get('anti_target_id', '')).strip() if first_actionable else "",
            "first_actionable_shard_id": str(first_actionable.get('primary_shard_id', '')).strip() if first_actionable else "",
            "next_required_step": next_required_step,
        },
        "structured": {
            "broad_queue_artifact": "runs/wetlab_broad_screen_queue_current.md",
            "companion_panel_artifact": "runs/wetlab_validation_companion_panels_current.md",
            "rerank_artifact": "runs/wetlab_broad_screen_target_rerank_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the anti-target counterscreen bulk queue gated by primary-target broad-screen readiness.")
    parser.add_argument("--broad-queue-json", default=DEFAULT_BROAD_QUEUE_JSON)
    parser.add_argument("--companion-json", default=DEFAULT_COMPANION_JSON)
    parser.add_argument("--rerank-json", default=DEFAULT_RERANK_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Anti-Target Queue",
        build_payload(
            broad_queue_payload=maybe_load_json(args.broad_queue_json),
            companion_payload=maybe_load_json(args.companion_json),
            rerank_payload=maybe_load_json(args.rerank_json),
        ),
    )
