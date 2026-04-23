from __future__ import annotations

from tools import build_dengue_ns2b_ns3_protease_result_summary as mod


def test_build_dengue_ns2b_ns3_protease_result_summary_defaults_to_not_ready() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "dengue_ns2b_ns3_protease_launch_packet_ready", "partner_track_id": "IPK_dengue"}},
        {"summary": {"status": "dengue_ns2b_ns3_protease_go_no_go_card_ready"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "not_ready"
    assert summary["artifact_kind"] == "result_summary"
    assert summary["result_review_ready"] is False
    assert summary["explicit_hold"] is False


def test_build_dengue_ns2b_ns3_protease_result_summary_marks_completed() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "dengue_ns2b_ns3_protease_launch_packet_ready", "partner_track_id": "IPK_dengue"}},
        {"summary": {"status": "dengue_ns2b_ns3_protease_go_no_go_card_ready"}},
        status="completed",
        decision_case="promote_clean_dengue_shallow_pocket_bias",
        action="promote",
        started_at="2026-03-30T02:00:00",
        completed_at="2026-03-30T03:15:00",
    )
    summary = payload["summary"]

    assert summary["status"] == "completed"
    assert summary["result_review_ready"] is True
    assert summary["decision_case"] == "promote_clean_dengue_shallow_pocket_bias"
    assert summary["action"] == "promote"
    assert summary["completed_at"] == "2026-03-30T03:15:00"
