from __future__ import annotations

from tools import build_wetlab_wave2_chain_stack as mod


def test_build_wetlab_wave2_chain_stack_reflects_final2_gate() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "wetlab_partner_target_portfolio_ready"}},
        {"summary": {"status": "wetlab_validation_companion_panels_ready"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": True}},
        {"summary": {"status": "wetlab_wave2_protein_run_queue_ready", "queue_target_count": 5, "ready_now_target_count": 0, "blocked_on_previous_review_count": 5, "blocked_on_target_content_count": 0, "running_target_count": 0, "resolved_target_count": 0, "next_required_step": "Keep Wave 2 behind the LbDHODH final-release gate. Once that gate opens, Cathepsin K becomes the first live Wave 2 slot."}, "rows": []},
        {},
        {},
        {},
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_wave2_chain_stack_ready"
    assert summary["final2_final_review_ready"] is True
    assert summary["final2_final_gate_open"] is False
    assert summary["wave2_queue_ready"] is True
    assert summary["stack_gate_states"]["cathepsin_k"]["placeholder_state"] == "missing_launch_packet+missing_transition_surface"
    assert "Cathepsin K becomes the first live Wave 2 slot" in summary["next_required_step"]
    assert payload["rows"][1]["chain_item"] == "cathepsin_k_placeholder_gate"


def test_build_wetlab_wave2_chain_stack_recognizes_real_cathepsin_k_packet() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "wetlab_partner_target_portfolio_ready"}},
        {"summary": {"status": "wetlab_validation_companion_panels_ready"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": False, "final_release_gate_status": "open_after_lbdhodh_result_ready"}},
        {
            "summary": {
                "status": "wetlab_wave2_protein_run_queue_ready",
                "queue_target_count": 1,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 0,
                "blocked_on_target_content_count": 1,
                "running_target_count": 0,
                "resolved_target_count": 0,
                "placeholder_target_count": 0,
                "missing_target_specific_packet_count": 0,
                "next_required_step": "The final2 gate is open, but Cathepsin K still needs its compound-fill-backed launch readiness before the serialized Wave 2 chain can advance.",
            },
            "rows": [
                {
                    "target_id": "Cathepsin K",
                    "queue_status": "blocked_on_target_content",
                    "placeholder_state": "live_target_specific_packet_present",
                }
            ],
        },
        {"cathepsin_k": {"summary": {"status": "cathepsin_k_launch_packet_ready"}}},
        {"cathepsin_k": {"summary": {"status": "cathepsin_k_run_record_ready"}}},
        {"cathepsin_k": {"summary": {"status": "cathepsin_k_result_review_ready"}}},
    )
    summary = payload["summary"]

    assert summary["final2_final_gate_open"] is True
    assert summary["stack_gate_states"]["cathepsin_k"]["launch_packet_ready"] is True
    assert summary["stack_gate_states"]["cathepsin_k"]["transition_ready"] is True
    assert summary["stack_gate_states"]["cathepsin_k"]["run_record_ready"] is True
    assert summary["stack_gate_states"]["cathepsin_k"]["placeholder_state"] == "live_target_specific_packet_present"
    assert "compound-fill-backed launch readiness" in summary["next_required_step"]


def test_build_wetlab_wave2_chain_stack_recognizes_real_tcruzi_krs1_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {"status": "wetlab_partner_target_portfolio_ready"},
            "rows": [{"target_id": "T. cruzi KRS1", "wave": "Wave 2"}],
        },
        {"summary": {"status": "wetlab_validation_companion_panels_ready"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": False, "final_release_gate_status": "open_after_lbdhodh_result_ready"}},
        {
            "summary": {
                "status": "wetlab_wave2_protein_run_queue_ready",
                "queue_target_count": 1,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 1,
                "blocked_on_target_content_count": 0,
                "running_target_count": 0,
                "resolved_target_count": 0,
                "placeholder_target_count": 0,
                "missing_target_specific_packet_count": 0,
                "next_required_step": "Keep T. cruzi KRS1 blocked until its predecessor review resolves.",
            },
            "rows": [
                {
                    "target_id": "T. cruzi KRS1",
                    "queue_status": "blocked_on_previous_review",
                    "placeholder_state": "live_target_specific_packet_present",
                }
            ],
        },
        {"tcruzi_krs1": {"summary": {"status": "tcruzi_krs1_launch_packet_ready"}}},
        {"tcruzi_krs1": {"summary": {"status": "tcruzi_krs1_run_record_ready"}}},
        {"tcruzi_krs1": {"summary": {"status": "tcruzi_krs1_result_review_ready"}}},
    )
    summary = payload["summary"]

    assert summary["final2_final_gate_open"] is True
    assert summary["stack_gate_states"]["tcruzi_krs1"]["launch_packet_ready"] is True
    assert summary["stack_gate_states"]["tcruzi_krs1"]["transition_ready"] is True
    assert summary["stack_gate_states"]["tcruzi_krs1"]["run_record_ready"] is True
    assert summary["stack_gate_states"]["tcruzi_krs1"]["placeholder_state"] == "live_target_specific_packet_present"
    assert payload["rows"][1]["chain_item"] == "tcruzi_krs1_runtime_gate"
