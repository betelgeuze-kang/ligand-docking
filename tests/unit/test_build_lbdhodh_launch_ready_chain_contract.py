from __future__ import annotations

from tools import build_lbdhodh_launch_packet as launch_mod
from tools import build_lbdhodh_render_suite as render_mod
from tools import build_lbdhodh_result_review as review_mod
from tools import build_lbdhodh_run_record as record_mod
from tools import build_wetlab_final2_chain_stack as final2_stack_mod
from tools import build_wetlab_final2_protein_run_queue as final2_queue_mod
from tools import build_wetlab_master_execution_queue as master_mod
from tools.wetlab_target_render_utils import load_json


def _build_launch_ready_payloads() -> tuple[dict, dict]:
    repurposing_fill_map = {
        "rows": [
            {"target_id": "Leishmania braziliensis DHODH", "compound_name": "R1"},
            {"target_id": "Leishmania braziliensis DHODH", "compound_name": "R2"},
            {"target_id": "Leishmania braziliensis DHODH", "compound_name": "R3"},
        ]
    }
    novelty_fill_map = {
        "rows": [
            {"target_id": "Leishmania braziliensis DHODH", "novelty_compound_name": "N1"},
            {"target_id": "Leishmania braziliensis DHODH", "novelty_compound_name": "N2"},
            {"target_id": "Leishmania braziliensis DHODH", "novelty_compound_name": "N3"},
        ]
    }

    render_payload = render_mod.build_payload(
        load_json(render_mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(render_mod.DEFAULT_NEGLECTED_ROWS_JSON),
        load_json(render_mod.DEFAULT_NEGLECTED_PACKET_JSON),
        load_json(render_mod.DEFAULT_OUTREACH_JSON),
        load_json(render_mod.DEFAULT_EXPORT_BUNDLE_JSON),
        repurposing_fill_map,
        novelty_fill_map,
    )
    launch_payload = launch_mod.build_payload(
        render_payload,
        render_payload["artifacts"]["condition_card"],
        repurposing_fill_map,
        novelty_fill_map,
    )
    return render_payload, launch_payload


def test_lbdhodh_fully_filled_review_and_run_record_open_launch_slot() -> None:
    _, launch_payload = _build_launch_ready_payloads()

    review_payload = review_mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        launch_payload,
    )
    record_payload = record_mod.build_payload(launch_payload, review_payload)

    assert launch_payload["summary"]["launch_readiness"] == "ready_for_serialized_execution"
    assert review_payload["summary"]["upstream_gate_open"] is True
    assert review_payload["summary"]["content_ready"] is True
    assert review_payload["summary"]["lbdhodh_gate_open"] is True
    assert review_payload["summary"]["lbdhodh_review_state"] == "ready_to_capture_lbdhodh_result_review"
    assert review_payload["summary"]["queue_status_now"] == "ready_after_previous_review"
    assert record_payload["summary"]["execution_state"] == "ready_to_launch"
    assert record_payload["summary"]["queue_status_now"] == "ready_after_previous_review"
    assert record_payload["summary"]["content_ready"] is True
    assert record_payload["summary"]["upstream_gate_open"] is True


def test_lbdhodh_fully_filled_state_clears_final2_blockers() -> None:
    render_payload, launch_payload = _build_launch_ready_payloads()
    review_payload = review_mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        launch_payload,
    )
    record_payload = record_mod.build_payload(launch_payload, review_payload)

    final2_queue_payload = final2_queue_mod.build_payload(
        {"summary": {"status": "stk17b_launch_packet_ready", "partner_track_id": "SGC_dark_kinase"}},
        launch_payload,
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "result_ready_for_review"}},
        review_payload,
    )
    chain_payload = final2_stack_mod.build_payload(
        {"summary": {"status": "stk17b_render_suite_ready"}},
        render_payload,
        {"summary": {"status": "stk17b_launch_packet_ready"}},
        launch_payload,
        {"summary": {"artifact_kind": "run_record", "target_id": "STK17B (DRAK2)", "execution_state": "result_ready"}},
        record_payload,
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "result_ready_for_review", "execution_state": "result_ready"}},
        review_payload,
        final2_queue_payload,
        {"summary": {"status": "alk2_result_review_ready", "next_queue_release_blocked": False, "next_queue_release_gate_status": "open_after_alk2_result_ready"}},
    )

    assert final2_queue_payload["summary"]["ready_now_target_count"] == 1
    assert final2_queue_payload["summary"]["blocked_on_target_content_count"] == 0
    assert final2_queue_payload["summary"]["lbdhodh_queue_status"] == "ready_after_previous_review"
    assert chain_payload["summary"]["lbdhodh_content_ready"] is True
    assert chain_payload["summary"]["lbdhodh_queue_status"] == "ready_after_previous_review"
    assert chain_payload["summary"]["lbdhodh_execution_state"] == "ready_to_launch"
    assert chain_payload["summary"]["lbdhodh_blockers"] == {
        "upstream_stk17b_result_review": "clear",
        "compound_fill": "clear",
    }


def test_lbdhodh_fully_filled_state_becomes_master_actionable_after_stk17b_resolution() -> None:
    _, launch_payload = _build_launch_ready_payloads()
    review_payload = review_mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        launch_payload,
    )

    final2_queue_payload = final2_queue_mod.build_payload(
        {"summary": {"status": "stk17b_launch_packet_ready", "partner_track_id": "SGC_dark_kinase"}},
        launch_payload,
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "result_ready_for_review"}},
        review_payload,
    )
    master_payload = master_mod.build_payload(
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0}, "rows": []},
        {"summary": {"ready_now_target_count": 0, "blocked_on_previous_review_count": 0}, "rows": []},
        final2_queue_payload,
        {
            "summary": {
                "status": "wetlab_wave2_protein_run_queue_ready",
                "upstream_final2_gate_status": "wave2_release_blocked",
                "upstream_final2_gate_open": False,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 1,
                "blocked_on_target_content_count": 0,
                "running_target_count": 0,
                "resolved_target_count": 0,
            },
            "rows": [
                {
                    "target_id": "Cathepsin K",
                    "queue_status": "blocked_on_previous_review",
                    "transition_status": "cathepsin_k_result_review_ready",
                }
            ],
        },
        {"summary": {"wave2_release_gate_status": "wave2_release_blocked", "wave2_release_blocked": True}},
    )

    assert master_payload["summary"]["active_stack_level"] == "final2"
    assert master_payload["summary"]["active_target_id"] == "Leishmania braziliensis DHODH"
    assert master_payload["summary"]["active_target_queue_status"] == "ready_after_previous_review"
    assert master_payload["summary"]["active_target_execution_state"] == "ready_to_launch"
    assert master_payload["summary"]["first_actionable_target"] == "Leishmania braziliensis DHODH"
    assert master_payload["summary"]["first_actionable_chain"] == "final2"
    assert master_payload["summary"]["lbdhodh_blockers"] == {
        "upstream_stk17b_result_review": "clear",
        "compound_fill": "clear",
    }
