from __future__ import annotations

from tools import build_wetlab_cathepsin_k_tuned_branch_summary as cat_branch_mod
from tools import build_wetlab_cathepsin_k_tuned_operator_packet as cat_packet_mod
from tools import build_wetlab_dengue_ns2b_ns3_protease_operator_packet as dengue_packet_mod
from tools import build_wetlab_dengue_ns2b_ns3_protease_review_branch_summary as dengue_branch_mod


def _cathepsin_result_summary() -> dict:
    return {"summary": {"status": "completed", "target_id": "Cathepsin K", "decision_case": "promote_clean_cathepsin_k_favored", "action": "promote"}}


def _cathepsin_result_review() -> dict:
    return {"summary": {"status": "cathepsin_k_result_review_ready", "target_id": "Cathepsin K", "queue_status_now": "result_ready_for_successor", "cathepsin_k_explicit_hold": False}}


def _cathepsin_run_record() -> dict:
    return {"summary": {"status": "cathepsin_k_run_record_ready", "target_id": "Cathepsin K", "queue_status_now": "result_ready_for_review"}}


def _cathepsin_tuning() -> dict:
    return {"summary": {"status": "wetlab_cathepsin_k_stage6_tuning_surface_ready", "target_id": "Cathepsin K", "campaign_start_shard_id": "01_of_20", "recommended_observed_threshold_A": 4.45, "immediately_runnable_command_kind": "throughput_preflight_tuned_gate45", "immediately_runnable_threshold_A": 4.5}}


def _cathepsin_lane() -> dict:
    return {"summary": {"status": "wetlab_cathepsin_k_exploratory_retry_lane_ready", "target_id": "Cathepsin K", "shard_id": "01_of_20", "selected_command_kind": "throughput_preflight_tuned_gate45", "selected_threshold_A": 4.5, "prior_tuned_success_count": 5, "prior_tuned_hold_count": 15}}


def _dengue_result_summary() -> dict:
    return {"summary": {"status": "completed", "target_id": "Dengue NS2B-NS3 protease", "decision_case": "dengue_shallow_pocket_pass", "action": "advance_to_successor_gate"}}


def _dengue_result_review() -> dict:
    return {"summary": {"status": "dengue_ns2b_ns3_protease_result_review_ready", "target_id": "Dengue NS2B-NS3 protease", "queue_status_now": "result_ready_for_successor", "dengue_ns2b_ns3_explicit_hold": False}}


def _dengue_run_record() -> dict:
    return {"summary": {"status": "dengue_ns2b_ns3_protease_run_record_ready", "target_id": "Dengue NS2B-NS3 protease", "queue_status_now": "result_ready_for_review"}}


def _dengue_tuning() -> dict:
    return {"summary": {"status": "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready", "target_id": "Dengue NS2B-NS3 protease", "campaign_start_shard_id": "01_of_20", "recommended_observed_threshold_A": 4.5, "immediately_runnable_command_kind": "throughput_preflight_tuned_gate45", "immediately_runnable_threshold_A": 4.5}}


def _dengue_lane() -> dict:
    return {"summary": {"status": "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready", "target_id": "Dengue NS2B-NS3 protease", "shard_id": "01_of_20", "selected_command_kind": "throughput_preflight_tuned_gate45", "selected_threshold_A": 4.5, "prior_tuned_success_count": 4, "prior_tuned_hold_count": 16}}


def test_build_cathepsin_k_tuned_operator_packet() -> None:
    payload = cat_packet_mod.build_payload(
        _cathepsin_result_summary(),
        _cathepsin_result_review(),
        _cathepsin_run_record(),
        _cathepsin_tuning(),
        _cathepsin_lane(),
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_cathepsin_k_tuned_operator_packet_ready"
    assert summary["packet_scope"] == "partner_operator_tuned_branch_review"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_threshold_A"] == 4.5
    assert summary["decision_case"] == "promote_clean_cathepsin_k_favored"
    assert summary["action"] == "promote"
    assert summary["success_shard_count"] == 5
    assert summary["hold_shard_count"] == 15


def test_build_cathepsin_k_tuned_branch_summary() -> None:
    operator_packet = cat_packet_mod.build_payload(
        _cathepsin_result_summary(),
        _cathepsin_result_review(),
        _cathepsin_run_record(),
        _cathepsin_tuning(),
        _cathepsin_lane(),
    )
    payload = cat_branch_mod.build_payload(
        operator_packet,
        _cathepsin_result_summary(),
        _cathepsin_result_review(),
        _cathepsin_run_record(),
        _cathepsin_tuning(),
        _cathepsin_lane(),
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_cathepsin_k_tuned_branch_summary_ready"
    assert summary["branch_label"] == "cathepsin_k_tuned_branch"
    assert summary["branch_state"] == "promotion_ready_default_lane_closed"
    assert summary["branch_to_rescue_only"] is False
    assert summary["branch_to_tuned_only"] is True
    assert summary["operator_packet_ready"] is True


def test_build_dengue_operator_packet() -> None:
    payload = dengue_packet_mod.build_payload(
        _dengue_result_summary(),
        _dengue_result_review(),
        _dengue_run_record(),
        _dengue_tuning(),
        _dengue_lane(),
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_dengue_ns2b_ns3_protease_operator_packet_ready"
    assert summary["packet_scope"] == "partner_operator_guarded_stage6_review"
    assert summary["selected_threshold_A"] == 4.5
    assert summary["action"] == "advance_to_successor_gate"
    assert summary["success_shard_count"] == 4
    assert summary["hold_shard_count"] == 16


def test_build_dengue_review_branch_summary() -> None:
    operator_packet = dengue_packet_mod.build_payload(
        _dengue_result_summary(),
        _dengue_result_review(),
        _dengue_run_record(),
        _dengue_tuning(),
        _dengue_lane(),
    )
    payload = dengue_branch_mod.build_payload(
        operator_packet,
        _dengue_result_summary(),
        _dengue_result_review(),
        _dengue_run_record(),
        _dengue_tuning(),
        _dengue_lane(),
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_dengue_ns2b_ns3_protease_review_branch_summary_ready"
    assert summary["branch_label"] == "dengue_ns2b_ns3_protease_review_branch"
    assert summary["branch_state"] == "operator_review_ready_default_lane_closed"
    assert summary["branch_to_rescue_only"] is False
    assert summary["operator_packet_scope"] == "partner_operator_guarded_stage6_review"
