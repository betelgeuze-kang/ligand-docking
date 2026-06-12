#!/usr/bin/env python3
from __future__ import annotations

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_next3_protein_run_queue_current.json"
DEFAULT_REFRESH_JSON = "runs/wetlab_next3_gate_refresh_current.json"
DEFAULT_OUT_MD = "runs/wetlab_next3_runtime_runbook_current.md"


def build_payload(queue_payload: dict, refresh_payload: dict) -> dict:
    queue_s = dict(queue_payload.get("summary", {}) or {})
    refresh_s = dict(refresh_payload.get("summary", {}) or {})

    rows = [
        {
            "run_order": 1,
            "target_id": "Cruzain",
            "event": "start",
            "precondition": "queue_status=ready_after_previous_review",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target cruzain --event start --active-stage-label parasite_cysteine_protease_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/cruzain_run_status_current.md",
            "expected_effect": "Cruzain stays active_slot; PLpro remains blocked",
        },
        {
            "run_order": 2,
            "target_id": "Cruzain",
            "event": "complete",
            "precondition": "Cruzain live run finished cleanly",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target cruzain --event complete --active-stage-label parasite_cysteine_protease_primary_assay --decision-case promote_clean_cruzain_favored --action promote --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/sarscov2_plpro_result_review_current.md",
            "expected_effect": "PLpro gate opens for serialized slot 2",
        },
        {
            "run_order": 3,
            "target_id": "Cruzain",
            "event": "hold",
            "precondition": "Cruzain needs explicit hold instead of clean completion",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target cruzain --event hold --active-stage-label parasite_cysteine_protease_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/sarscov2_plpro_result_review_current.md",
            "expected_effect": "PLpro gate still opens, but Cruzain is carried as explicit_hold",
        },
        {
            "run_order": 4,
            "target_id": "SARS-CoV-2 PLpro",
            "event": "start",
            "precondition": "PLpro gate open after Cruzain result-ready or explicit_hold",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target sarscov2_plpro --event start --active-stage-label antiviral_dub_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/sarscov2_plpro_result_review_current.md",
            "expected_effect": "PLpro stays active_slot; ALK2 remains blocked",
        },
        {
            "run_order": 5,
            "target_id": "SARS-CoV-2 PLpro",
            "event": "complete",
            "precondition": "PLpro live result is ready",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target sarscov2_plpro --event complete --active-stage-label antiviral_dub_primary_assay --decision-case promote_clean_plpro_favored --action promote --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/alk2_result_review_current.md",
            "expected_effect": "ALK2 gate opens for serialized slot 3",
        },
        {
            "run_order": 6,
            "target_id": "SARS-CoV-2 PLpro",
            "event": "hold",
            "precondition": "PLpro needs explicit hold instead of clean completion",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target sarscov2_plpro --event hold --active-stage-label antiviral_dub_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/alk2_result_review_current.md",
            "expected_effect": "ALK2 gate still opens, but PLpro is carried as explicit_hold",
        },
        {
            "run_order": 7,
            "target_id": "ALK2",
            "event": "start",
            "precondition": "ALK2 gate open after PLpro result-ready or explicit_hold",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target alk2 --event start --active-stage-label mutant_selective_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/alk2_result_review_current.md",
            "expected_effect": "ALK2 occupies the final serialized next3 slot",
        },
        {
            "run_order": 8,
            "target_id": "ALK2",
            "event": "complete",
            "precondition": "ALK2 result is ready",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target alk2 --event complete --active-stage-label mutant_selective_primary_assay --decision-case alk2_mutant_selective_pass --action advance_to_later_release_review --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/alk2_result_review_current.md",
            "expected_effect": "later release gate opens after ALK2 result_ready",
        },
        {
            "run_order": 9,
            "target_id": "ALK2",
            "event": "hold",
            "precondition": "ALK2 needs explicit hold instead of clean completion",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target alk2 --event hold --active-stage-label mutant_selective_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/alk2_result_review_current.md",
            "expected_effect": "later release gate opens after ALK2 explicit_hold",
        },
        {
            "run_order": 10,
            "target_id": "any",
            "event": "reset",
            "precondition": "use before a fresh dry-run or to clear stale writer state",
            "command": "python3 tools/wetlab/build_wetlab_next3_runtime_event.py --target <cruzain|sarscov2_plpro|alk2> --event reset",
            "expected_gate_artifact": "runs/wetlab_next3_gate_refresh_current.md",
            "expected_effect": "resets writer state for the chosen target and rebuilds the serialized next3 gate chain",
        },
    ]

    return {
        "summary": {
            "status": "wetlab_next3_runtime_runbook_ready",
            "target_count": 3,
            "command_row_count": len(rows),
            "queue_status": str(queue_s.get("status", "")).strip(),
            "ready_now_target_count": int(queue_s.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue_s.get("blocked_on_previous_review_count", 0) or 0),
            "refresh_status": str(refresh_s.get("status", "")).strip(),
            "cruzain_execution_state": str(refresh_s.get("cruzain_execution_state", "")).strip(),
            "plpro_review_state": str(refresh_s.get("plpro_review_state", "")).strip(),
            "alk2_execution_state": str(refresh_s.get("alk2_execution_state", "")).strip(),
            "next_required_step": "Use the Cruzain start/complete events first. Once the refresh artifact shows the PLpro gate open, switch to the PLpro commands. Only then move to ALK2.",
        },
        "structured": {
            "runtime_event_artifact": "runs/wetlab_next3_runtime_event_current.md",
            "refresh_artifact": "runs/wetlab_next3_gate_refresh_current.md",
            "queue_artifact": "runs/wetlab_next3_protein_run_queue_current.md",
            "execution_policy": "serialized_by_target_with_parallel_prep_only",
        },
        "rows": rows,
    }


def main() -> None:
    payload = build_payload(load_json(DEFAULT_QUEUE_JSON), load_json(DEFAULT_REFRESH_JSON))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Next3 Runtime Runbook", payload)


if __name__ == "__main__":
    main()
