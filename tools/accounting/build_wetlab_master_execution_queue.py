#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import (
    first_unresolved_row,
    load_json,
    maybe_load_json,
    queue_status_is_resolved,
    queue_status_to_execution_state,
    write_artifact,
)

DEFAULT_PRIORITY3_QUEUE_JSON = "runs/wetlab_priority3_protein_run_queue_current.json"
DEFAULT_NEXT3_QUEUE_JSON = "runs/wetlab_next3_protein_run_queue_current.json"
DEFAULT_FINAL2_QUEUE_JSON = "runs/wetlab_final2_protein_run_queue_current.json"
DEFAULT_WAVE2_QUEUE_JSON = "runs/wetlab_wave2_protein_run_queue_current.json"
DEFAULT_PRIORITY3_FINAL_REVIEW_JSON = "runs/tcruzi_pde_result_review_current.json"
DEFAULT_LBDHODH_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_LBDHODH_LAUNCH_JSON = "runs/lbdhodh_launch_packet_current.json"
DEFAULT_OUT_MD = "runs/wetlab_master_execution_queue_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _first_text(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _wave2_gate_state(priority3_final_review: dict[str, Any] | None) -> dict[str, Any]:
    review_summary = _summary(priority3_final_review or {})
    gate_status = _first_text(review_summary, "wave2_release_gate_status")
    if "wave2_release_blocked" in review_summary:
        wave2_release_blocked = bool(review_summary.get("wave2_release_blocked"))
    else:
        gate_text = gate_status.lower()
        wave2_release_blocked = not gate_text or "blocked" in gate_text or "open" not in gate_text
    return {
        "wave2_release_gate_status": gate_status or "wave2_release_blocked",
        "wave2_release_blocked": wave2_release_blocked,
        "wave2_ready": not wave2_release_blocked,
        "wave2_queue_status": "ready_after_previous_review" if not wave2_release_blocked else "blocked_on_previous_review",
    }


def _chain_rows(payload: dict[str, Any], chain_id: str, chain_rank: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(payload.get("rows", []) or [], start=1):
        item = dict(row)
        item["chain_id"] = chain_id
        item["chain_rank"] = chain_rank
        item["global_queue_order"] = idx
        rows.append(item)
    return rows


def _renumber_global_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numbered: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        item["global_queue_order"] = idx
        numbered.append(item)
    return numbered


def _chain_gate_state(chain_rows: list[dict[str, Any]], chain_rank: int) -> dict[str, Any]:
    active_row = first_unresolved_row(chain_rows)
    return {
        "chain_rank": chain_rank,
        "queue_target_count": len(chain_rows),
        "resolved_target_count": sum(1 for row in chain_rows if queue_status_is_resolved(row.get("queue_status", ""))),
        "all_rows_resolved": active_row is None,
        "active_target_id": str(active_row.get("target_id", "")).strip() if active_row else "",
        "active_target_queue_status": str(active_row.get("queue_status", "")).strip() if active_row else "",
        "active_target_execution_state": queue_status_to_execution_state(active_row.get("queue_status", "")) if active_row else "",
    }


def build_payload(
    priority3_queue: dict[str, Any],
    next3_queue: dict[str, Any],
    final2_queue: dict[str, Any],
    wave2_queue: dict[str, Any] | None = None,
    priority3_final_review: dict[str, Any] | None = None,
    lbdhodh_review: dict[str, Any] | None = None,
    lbdhodh_launch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if priority3_final_review is None and wave2_queue is not None:
        legacy_wave2_summary = _summary(wave2_queue)
        if "wave2_release_gate_status" in legacy_wave2_summary or "wave2_release_blocked" in legacy_wave2_summary:
            priority3_final_review = wave2_queue
            wave2_queue = None

    p3s = _summary(priority3_queue)
    n3s = _summary(next3_queue)
    f2s = _summary(final2_queue)
    w2s = _summary(wave2_queue or {})
    wave2_state = _wave2_gate_state(priority3_final_review)
    if w2s:
        wave2_state = {
            "wave2_release_gate_status": _first_text(w2s, "upstream_final2_gate_status") or wave2_state["wave2_release_gate_status"],
            "wave2_release_blocked": not bool(w2s.get("upstream_final2_gate_open", False)),
            "wave2_ready": int(w2s.get("ready_now_target_count", 0) or 0) > 0,
            "wave2_queue_status": _first_text(w2s, "first_target_queue_status")
            or (
                str((wave2_queue or {}).get("rows", [{}])[0].get("queue_status", "")).strip()
                if (wave2_queue or {}).get("rows")
                else wave2_state["wave2_queue_status"]
            ),
        }

    rows = _renumber_global_queue([
        *_chain_rows(priority3_queue, "priority3", 1),
        *_chain_rows(next3_queue, "next3", 2),
        *_chain_rows(final2_queue, "final2", 3),
        *_chain_rows(wave2_queue or {}, "wave2", 4),
    ])
    first_actionable = next((row for row in rows if str(row.get("queue_status", "")).startswith("ready") or "running" in str(row.get("queue_status", ""))), None)
    chain_rows = {
        "priority3": [dict(row) for row in rows if row.get("chain_id") == "priority3"],
        "next3": [dict(row) for row in rows if row.get("chain_id") == "next3"],
        "final2": [dict(row) for row in rows if row.get("chain_id") == "final2"],
        "wave2": [dict(row) for row in rows if row.get("chain_id") == "wave2"],
    }
    stack_gate_states = {
        chain_id: _chain_gate_state(chain_rows[chain_id], chain_rank)
        for chain_id, chain_rank in (("priority3", 1), ("next3", 2), ("final2", 3), ("wave2", 4))
    }
    active_stack_level = ""
    active_stack_state: dict[str, Any] = {}
    for chain_id in ("priority3", "next3", "final2", "wave2"):
        state = stack_gate_states[chain_id]
        if state["active_target_id"]:
            active_stack_level = chain_id
            active_stack_state = state
            break
    lbdhodh_review_s = _summary(lbdhodh_review or {})
    lbdhodh_launch_s = _summary(lbdhodh_launch or {})
    if lbdhodh_review_s or lbdhodh_launch_s:
        lbdhodh_blockers = {
            "upstream_stk17b_result_review": "clear"
            if bool(lbdhodh_review_s.get("upstream_gate_open", False))
            else "blocked",
            "compound_fill": "clear"
            if str(lbdhodh_launch_s.get("launch_readiness", "")).strip() == "ready_for_serialized_execution"
            else "blocked",
        }
    else:
        lbdhodh_blockers = {
            "upstream_stk17b_result_review": "blocked"
            if str(chain_rows["final2"][0].get("queue_status", "")).strip() == "blocked_on_previous_review"
            else "clear",
            "compound_fill": "blocked"
            if str(chain_rows["final2"][1].get("queue_status", "")).strip() == "blocked_on_target_content"
            else "clear",
        }

    return {
        "summary": {
            "status": "wetlab_master_execution_queue_ready",
            "chain_count": 4,
            "queue_target_count": len(rows),
            "active_stack_level": active_stack_level,
            "active_target_id": str(active_stack_state.get("active_target_id", "")).strip(),
            "active_target_queue_status": str(active_stack_state.get("active_target_queue_status", "")).strip(),
            "active_target_execution_state": str(active_stack_state.get("active_target_execution_state", "")).strip(),
            "stack_gate_states": stack_gate_states,
            "lbdhodh_blockers": lbdhodh_blockers,
            "wave2_release_gate_status": wave2_state["wave2_release_gate_status"],
            "wave2_release_blocked": wave2_state["wave2_release_blocked"],
            "wave2_ready": wave2_state["wave2_ready"],
            "wave2_queue_status": wave2_state["wave2_queue_status"] or "blocked_on_previous_review",
            "ready_now_target_count": int(p3s.get("ready_now_target_count", 0) or 0) + int(n3s.get("ready_now_target_count", 0) or 0) + int(f2s.get("ready_now_target_count", 0) or 0) + int(w2s.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(p3s.get("blocked_on_previous_review_count", 0) or 0) + int(n3s.get("blocked_on_previous_review_count", 0) or 0) + int(f2s.get("blocked_on_previous_review_count", 0) or 0) + int(w2s.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(p3s.get("blocked_on_target_content_count", 0) or 0) + int(n3s.get("blocked_on_target_content_count", 0) or 0) + int(f2s.get("blocked_on_target_content_count", 0) or 0) + int(w2s.get("blocked_on_target_content_count", 0) or 0),
            "running_target_count": int(p3s.get("running_target_count", 0) or 0) + int(n3s.get("running_target_count", 0) or 0) + int(f2s.get("running_target_count", 0) or 0) + int(w2s.get("running_target_count", 0) or 0),
            "resolved_target_count": int(p3s.get("resolved_target_count", 0) or 0) + int(n3s.get("resolved_target_count", 0) or 0) + int(f2s.get("resolved_target_count", 0) or 0) + int(w2s.get("resolved_target_count", 0) or 0),
            "first_actionable_target": str(first_actionable.get("target_id", "")).strip() if first_actionable else "",
            "first_actionable_chain": str(first_actionable.get("chain_id", "")).strip() if first_actionable else "",
            "first_actionable_queue_status": str(first_actionable.get("queue_status", "")).strip() if first_actionable else "",
            "first_actionable_transition_status": str(first_actionable.get("transition_status", "")).strip() if first_actionable else "",
            "next_required_step": (
                f"Advance the serialized wet-lab chain with {first_actionable['target_id']} from {first_actionable['chain_id']}."
                if first_actionable
                else "No target is actionable yet; resolve the upstream result reviews before opening the next serialized slot."
            ),
        },
        "structured": {
            "priority3_queue_artifact": "runs/wetlab_priority3_protein_run_queue_current.md",
            "next3_queue_artifact": "runs/wetlab_next3_protein_run_queue_current.md",
            "final2_queue_artifact": "runs/wetlab_final2_protein_run_queue_current.md",
            "wave2_queue_artifact": "runs/wetlab_wave2_protein_run_queue_current.md",
            "execution_policy": "serialized_by_target_across_all_wetlab_chains",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the master serialized wet-lab execution queue across priority3, next3, and final2.")
    parser.add_argument("--priority3-queue-json", default=DEFAULT_PRIORITY3_QUEUE_JSON)
    parser.add_argument("--next3-queue-json", default=DEFAULT_NEXT3_QUEUE_JSON)
    parser.add_argument("--final2-queue-json", default=DEFAULT_FINAL2_QUEUE_JSON)
    parser.add_argument("--wave2-queue-json", default=DEFAULT_WAVE2_QUEUE_JSON)
    parser.add_argument("--priority3-final-review-json", default=DEFAULT_PRIORITY3_FINAL_REVIEW_JSON)
    parser.add_argument("--lbdhodh-review-json", default=DEFAULT_LBDHODH_REVIEW_JSON)
    parser.add_argument("--lbdhodh-launch-json", default=DEFAULT_LBDHODH_LAUNCH_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.priority3_queue_json),
        load_json(args.next3_queue_json),
        load_json(args.final2_queue_json),
        maybe_load_json(args.wave2_queue_json),
        load_json(args.priority3_final_review_json),
        maybe_load_json(args.lbdhodh_review_json),
        maybe_load_json(args.lbdhodh_launch_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Master Execution Queue", payload)


if __name__ == "__main__":
    main()
