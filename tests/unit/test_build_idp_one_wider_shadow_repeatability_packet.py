from __future__ import annotations

from tools import build_idp_one_wider_shadow_repeatability_packet as mod


def test_build_idp_one_wider_shadow_repeatability_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "one_wider_shadow_safe_lane_only",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "wider_shadow_safe_lane_admitted": True,
                "frozen_validated_current_target_count": 7,
                "frozen_additional_anchor_backed_target_count": 1,
                "frozen_total_target_count": 8,
            }
        },
        {
            "summary": {
                "status": "first_true_broader_shadow_completed_pass",
                "corrected_pass_folds": 8,
                "fold_count": 8,
                "page4_fold_pass": True,
                "tau_k18_fold_pass": True,
                "config_json": "/tmp/idp_anchor_plus_page4.json",
            },
            "rows": [
                {"target_name": "tau_k18", "pass": True},
                {"target_name": "page4", "pass": True},
            ],
        },
        out_prefix="runs/idp_3bead_holdout_v7_onewider_repeatability_r1",
    )
    summary = payload["summary"]
    assert summary["status"] == "one_wider_shadow_repeatability_packet_ready"
    assert summary["operator_scope_now"] == "one_wider_shadow_safe_lane_only"
    assert summary["wider_shadow_safe_lane_admitted"] is True
    assert summary["row_count"] == 2
    assert "run_idp_3bead_holdout_pipeline.py" in summary["exact_command"]
    assert "one_wider_shadow_safe_lane_only" in summary["next_required_step"]
    rows = {row["target_name"]: row for row in payload["rows"]}
    assert rows["tau_k18"]["focus_class"] == "tau_k18_watch_target"
    assert rows["page4"]["focus_class"] == "page4_anchor_target"
