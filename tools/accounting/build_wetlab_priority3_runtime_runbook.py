#!/usr/bin/env python3
from __future__ import annotations

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_priority3_protein_run_queue_current.json"
DEFAULT_REFRESH_JSON = "runs/wetlab_priority3_gate_refresh_current.json"
DEFAULT_OUT_MD = "runs/wetlab_priority3_runtime_runbook_current.md"


def _next_required_step(queue_s: dict, refresh_s: dict) -> str:
    ready_now = int(queue_s.get("ready_now_target_count", 0) or 0)
    blocked = int(queue_s.get("blocked_on_previous_review_count", 0) or 0)
    resolved = int(queue_s.get("resolved_target_count", refresh_s.get("resolved_target_count", 0)) or 0)
    running = int(queue_s.get("running_target_count", refresh_s.get("running_target_count", 0)) or 0)
    if resolved >= 3 and ready_now == 0 and blocked == 0 and running == 0:
        return (
            "Priority3 serialized execution is resolved. Use the partner send-round artifact for dispatch review, "
            "and keep external outreach behind an explicit R4 confirmation."
        )
    return (
        "Use the Mpro start/complete events first. Once the refresh artifact shows the CA IX gate open, "
        "switch to the CA IX commands. Only then move to T. cruzi PDE."
    )


def build_payload(queue_payload: dict, refresh_payload: dict) -> dict:
    queue_s = dict(queue_payload.get("summary", {}) or {})
    refresh_s = dict(refresh_payload.get("summary", {}) or {})

    rows = [
        {
            "run_order": 1,
            "target_id": "SARS-CoV-2 Mpro",
            "event": "start",
            "precondition": "queue_status=ready_first",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target sarscov2_mpro --event start --active-stage-label fluorogenic_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/sarscov2_mpro_run_status_current.md",
            "expected_effect": "Mpro stays active_slot; CA IX remains blocked",
        },
        {
            "run_order": 2,
            "target_id": "SARS-CoV-2 Mpro",
            "event": "complete",
            "precondition": "Mpro live run finished and you need CA IX to open without freezing a favorable biology call yet",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target sarscov2_mpro --event complete --active-stage-label fluorogenic_primary_assay --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/caix_result_review_current.md",
            "expected_effect": "CA IX gate opens for serialized slot 2 while Mpro remains result_ready_pending_classification until a real decision is frozen",
        },
        {
            "run_order": 3,
            "target_id": "SARS-CoV-2 Mpro",
            "event": "hold",
            "precondition": "Mpro needs explicit manual hold instead of clean completion",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target sarscov2_mpro --event hold --active-stage-label fluorogenic_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/caix_result_review_current.md",
            "expected_effect": "CA IX gate still opens, but Mpro is carried forward as explicit_hold",
        },
        {
            "run_order": 4,
            "target_id": "CA IX",
            "event": "start",
            "precondition": "CA IX gate open after Mpro result-ready or explicit_hold",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target caix --event start --active-stage-label acidic_buffer_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/caix_result_review_current.md",
            "expected_effect": "CA IX stays active_slot; T. cruzi PDE remains blocked",
        },
        {
            "run_order": 5,
            "target_id": "CA IX",
            "event": "complete",
            "precondition": "CA IX acidic-buffer result is ready",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target caix --event complete --active-stage-label acidic_buffer_primary_assay --decision-case caix_condition_pass --action advance_to_successor_gate --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/tcruzi_pde_result_review_current.md",
            "expected_effect": "T. cruzi PDE gate opens for serialized slot 3",
        },
        {
            "run_order": 6,
            "target_id": "CA IX",
            "event": "hold",
            "precondition": "CA IX needs explicit manual hold instead of clean completion",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target caix --event hold --active-stage-label acidic_buffer_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/tcruzi_pde_result_review_current.md",
            "expected_effect": "T. cruzi PDE gate still opens, but CA IX is carried as explicit_hold",
        },
        {
            "run_order": 7,
            "target_id": "T. cruzi PDE",
            "event": "start",
            "precondition": "T. cruzi PDE gate open after CA IX result-ready or explicit_hold",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target tcruzi_pde --event start --active-stage-label parasite_vs_human_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/tcruzi_pde_result_review_current.md",
            "expected_effect": "T. cruzi PDE occupies final serialized slot while wave-2 stays blocked",
        },
        {
            "run_order": 8,
            "target_id": "T. cruzi PDE",
            "event": "complete",
            "precondition": "T. cruzi PDE result is ready",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target tcruzi_pde --event complete --active-stage-label parasite_vs_human_primary_assay --decision-case tcruzi_parasite_selective_pass --action advance_to_wave2_release_review --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/tcruzi_pde_result_review_current.md",
            "expected_effect": "wave-2 release gate opens after T. cruzi result_ready",
        },
        {
            "run_order": 9,
            "target_id": "T. cruzi PDE",
            "event": "hold",
            "precondition": "T. cruzi PDE needs explicit manual hold instead of clean completion",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target tcruzi_pde --event hold --active-stage-label parasite_vs_human_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/tcruzi_pde_result_review_current.md",
            "expected_effect": "wave-2 release gate opens after explicit_hold instead of clean completion",
        },
        {
            "run_order": 10,
            "target_id": "any",
            "event": "reset",
            "precondition": "use before a fresh dry-run or to clear stale writer state",
            "command": "python3 tools/build_wetlab_priority3_runtime_event.py --target <sarscov2_mpro|caix|tcruzi_pde> --event reset",
            "expected_gate_artifact": "runs/wetlab_priority3_gate_refresh_current.md",
            "expected_effect": "resets writer state for the chosen target and rebuilds the serialized gate chain",
        },
    ]

    return {
        "summary": {
            "status": "wetlab_priority3_runtime_runbook_ready",
            "target_count": 3,
            "command_row_count": len(rows),
            "queue_status": str(queue_s.get("status", "")).strip(),
            "ready_now_target_count": int(queue_s.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue_s.get("blocked_on_previous_review_count", 0) or 0),
            "refresh_status": str(refresh_s.get("status", "")).strip(),
            "mpro_execution_state": str(refresh_s.get("mpro_execution_state", "")).strip(),
            "caix_review_state": str(refresh_s.get("caix_review_state", "")).strip(),
            "tcruzi_execution_state": str(refresh_s.get("tcruzi_execution_state", "")).strip(),
            "next_required_step": _next_required_step(queue_s, refresh_s),
        },
        "structured": {
            "runtime_event_artifact": "runs/wetlab_priority3_runtime_event_current.md",
            "refresh_artifact": "runs/wetlab_priority3_gate_refresh_current.md",
            "queue_artifact": "runs/wetlab_priority3_protein_run_queue_current.md",
            "execution_policy": "serialized_by_target_with_parallel_prep_only",
        },
        "rows": rows,
    }


def main() -> None:
    payload = build_payload(
        load_json(DEFAULT_QUEUE_JSON),
        load_json(DEFAULT_REFRESH_JSON),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Priority3 Runtime Runbook", payload)


if __name__ == "__main__":
    main()
