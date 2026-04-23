from __future__ import annotations

from tools.transporter_phase_helpers import aqp1_follow_on_seed_steps, infer_transporter_phase


def test_infer_transporter_phase_switches_to_seed_row_blocker_closure_when_manual_backlog_is_zero() -> None:
    assert infer_transporter_phase({"binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 6}) == "seed_row_blocker_closure"
    assert infer_transporter_phase({"binder_pending_manual_verdict_count": 2, "binder_seed_row_count": 6}) == "manual_review_only"
    assert infer_transporter_phase({"binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 0}) == "manual_review_only"


def test_aqp1_follow_on_seed_steps_collects_only_post_row01_binders() -> None:
    board = {
        "rows": [
            {"target_id": "AQP1", "packet_step": "core_binder_01"},
            {"target_id": "AQP1", "packet_step": "core_binder_02"},
            {"target_id": "AQP1", "packet_step": "core_binder_03"},
            {"target_id": "AQP1", "packet_step": "core_non_binder_01"},
            {"target_id": "GLUT1", "packet_step": "core_binder_02"},
        ]
    }
    assert aqp1_follow_on_seed_steps(board) == ["core_binder_02", "core_binder_03"]
