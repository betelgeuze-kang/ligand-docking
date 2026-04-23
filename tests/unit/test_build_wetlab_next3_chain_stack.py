from __future__ import annotations

from tools import build_wetlab_next3_chain_stack as mod


def test_build_wetlab_next3_chain_stack_reports_readiness() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "cruzain_render_suite_ready"}},
        {"summary": {"status": "sarscov2_plpro_render_suite_ready"}},
        {"summary": {"status": "alk2_render_suite_ready"}},
        {"summary": {"status": "cruzain_launch_packet_ready"}},
        {"summary": {"status": "sarscov2_plpro_launch_packet_ready"}},
        {"summary": {"status": "alk2_launch_packet_ready"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "Cruzain", "execution_state": "blocked_on_previous_review"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "SARS-CoV-2 PLpro", "execution_state": "blocked_on_previous_review"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "ALK2", "execution_state": "blocked_on_previous_review"}},
        {"summary": {"status": "cruzain_run_status_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "sarscov2_plpro_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "alk2_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "wetlab_next3_protein_run_queue_ready", "blocked_on_previous_review_count": 3}},
        {"summary": {"status": "tcruzi_pde_result_review_ready", "wave2_release_blocked": True}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_next3_chain_stack_ready"
    assert summary["priority3_final_review_ready"] is True
    assert summary["cruzain_run_record_ready"] is True
    assert summary["sarscov2_plpro_run_record_ready"] is True
    assert summary["alk2_run_record_ready"] is True
    assert summary["next3_queue_ready"] is True


def test_build_wetlab_next3_chain_stack_accepts_wave2_gate_status_fallback() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "cruzain_render_suite_ready"}},
        {"summary": {"status": "sarscov2_plpro_render_suite_ready"}},
        {"summary": {"status": "alk2_render_suite_ready"}},
        {"summary": {"status": "cruzain_launch_packet_ready"}},
        {"summary": {"status": "sarscov2_plpro_launch_packet_ready"}},
        {"summary": {"status": "alk2_launch_packet_ready"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "Cruzain", "execution_state": "blocked_on_previous_review"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "SARS-CoV-2 PLpro", "execution_state": "blocked_on_previous_review"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "ALK2", "execution_state": "blocked_on_previous_review"}},
        {"summary": {"status": "cruzain_run_status_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "sarscov2_plpro_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "alk2_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "wetlab_next3_protein_run_queue_ready", "blocked_on_previous_review_count": 3}},
        {
            "summary": {
                "status": "tcruzi_pde_result_review_ready",
                "wave2_release_gate_status": "open_after_tcruzi_result_ready",
            }
        },
    )
    summary = payload["summary"]

    assert summary["priority3_final_review_ready"] is True
    assert summary["priority3_final_gate_open"] is True
