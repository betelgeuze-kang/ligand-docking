from __future__ import annotations

from tools import build_wetlab_priority3_protein_run_queue as mod
from tools import build_sarscov2_mpro_launch_packet as mpro_launch_mod
from tools import build_caix_launch_packet as caix_launch_mod
from tools import build_tcruzi_pde_launch_packet as tcruzi_launch_mod
from tools import build_sarscov2_mpro_render_suite as mpro_render_mod
from tools import build_caix_render_suite as caix_render_mod
from tools import build_tcruzi_pde_render_suite as tcruzi_render_mod
from tools import build_wetlab_prep_artifact_lane as prep_lane_mod
from tools import build_sarscov2_mpro_run_status as mpro_status_mod
from tools import build_sarscov2_mpro_run_record as mpro_record_mod
from tools import build_caix_result_review as caix_review_mod
from tools import build_caix_run_record as caix_record_mod
from tools import build_tcruzi_pde_result_review as tcruzi_review_mod
from tools.wetlab_target_render_utils import load_json


def test_build_wetlab_priority3_protein_run_queue() -> None:
    mpro_render = mpro_render_mod.build_payload(
        load_json(mpro_render_mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(mpro_render_mod.DEFAULT_ANTIVIRAL_RAIL_JSON),
        load_json(mpro_render_mod.DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON),
        load_json(mpro_render_mod.DEFAULT_EXPORT_BUNDLE_JSON),
        load_json(mpro_render_mod.DEFAULT_VENDOR_COST_JSON),
    )
    caix_render = caix_render_mod.build_payload(
        load_json(caix_render_mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(caix_render_mod.DEFAULT_CAIX_BRIEF_JSON),
        load_json(caix_render_mod.DEFAULT_ONCOLOGY_PACKET_JSON),
        load_json(caix_render_mod.DEFAULT_EXPORT_BUNDLE_JSON),
    )
    tcruzi_render = tcruzi_render_mod.build_payload(
        load_json(tcruzi_render_mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(tcruzi_render_mod.DEFAULT_NEGLECTED_PACKET_JSON),
        load_json(tcruzi_render_mod.DEFAULT_EXPORT_BUNDLE_JSON),
    )
    mpro_launch = mpro_launch_mod.build_payload(
        mpro_render,
        mpro_render["artifacts"]["partner_export"],
        load_json(mpro_launch_mod.DEFAULT_VENDOR_COST_JSON),
    )
    caix_launch = caix_launch_mod.build_payload(
        load_json(caix_launch_mod.DEFAULT_BRIEF_INDEX_JSON),
        caix_render,
        caix_render["artifacts"]["partner_export"],
        caix_render["artifacts"]["condition_card"],
    )
    tcruzi_launch = tcruzi_launch_mod.build_payload(
        load_json(tcruzi_launch_mod.DEFAULT_BRIEF_INDEX_JSON),
        tcruzi_render,
        tcruzi_render["artifacts"]["partner_export"],
        tcruzi_render["artifacts"]["condition_card"],
    )
    prep_lane = prep_lane_mod.build_payload(
        mpro_render,
        caix_render,
        tcruzi_render,
    )
    mpro_run_record = mpro_record_mod.build_payload(mpro_launch, {}, {})
    mpro_run_status = mpro_status_mod.build_payload(mpro_launch, mpro_run_record)
    caix_run_record = caix_record_mod.build_payload(caix_launch, {}, {})
    caix_result_review = caix_review_mod.build_payload(mpro_run_status, caix_launch, tcruzi_launch, caix_run_record)
    tcruzi_result_review = tcruzi_review_mod.build_payload(caix_result_review, tcruzi_launch)
    payload = mod.build_payload(
        mpro_launch,
        caix_launch,
        tcruzi_launch,
        prep_lane,
        mpro_run_status,
        caix_result_review,
        tcruzi_result_review,
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_priority3_protein_run_queue_ready"
    assert summary["queue_target_count"] == 3
    assert summary["serialized_execution_slot_count"] == 1
    assert summary["mpro_run_status"] == "sarscov2_mpro_run_status_ready"
    assert summary["caix_result_review_status"] == "caix_result_review_ready"
    assert summary["tcruzi_pde_result_review_status"] == "tcruzi_pde_result_review_ready"
    assert summary["ready_now_target_count"] == 1
    assert summary["running_target_count"] == 0
    assert summary["resolved_target_count"] == 0
    assert summary["mpro_queue_status"] == "ready_first"
    assert summary["caix_queue_status"] == "blocked_on_previous_review"
    assert summary["tcruzi_queue_status"] == "blocked_on_previous_review"
    assert payload["rows"][0]["target_id"] == "SARS-CoV-2 Mpro"
    assert payload["rows"][1]["queue_status"] == "blocked_on_previous_review"
    assert payload["rows"][2]["launch_packet_artifact"] == "runs/tcruzi_pde_launch_packet_current.md"
    assert payload["rows"][0]["transition_artifact"] == "runs/sarscov2_mpro_run_status_current.md"


def test_build_wetlab_priority3_protein_run_queue_propagates_downstream_gate_opening() -> None:
    payload = mod.build_payload(
        {"summary": {"partner_track_id": "READDI_Korea"}},
        {"summary": {"partner_track_id": "oncology_condition_aware"}},
        {"summary": {"partner_track_id": "DNDi_IPK"}},
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "sarscov2_mpro_run_status_ready", "queue_status_now": "result_ready_for_review"}},
        {"summary": {"status": "caix_result_review_ready", "queue_status_now": "result_ready_for_successor"}},
        {"summary": {"status": "tcruzi_pde_result_review_ready", "queue_status_now": "ready_after_previous_review"}},
    )
    summary = payload["summary"]

    assert summary["ready_now_target_count"] == 1
    assert summary["running_target_count"] == 0
    assert summary["resolved_target_count"] == 2
    assert summary["mpro_queue_status"] == "result_ready_for_review"
    assert summary["caix_queue_status"] == "result_ready_for_successor"
    assert summary["tcruzi_queue_status"] == "ready_after_previous_review"
    assert payload["rows"][2]["queue_status"] == "ready_after_previous_review"
