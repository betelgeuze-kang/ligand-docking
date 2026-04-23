from __future__ import annotations

from tools import build_idp_broader_shadow_launch_packet as mod


def test_build_idp_broader_shadow_launch_packet_true_broader_ready() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "broader_shadow_review_resolved_true_broader_roster_available",
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "reviewed_target_count": 20,
                "validated_current_target_count": 7,
                "additional_anchor_backed_target_count": 1,
                "provisional_expansion_target_count": 12,
                "true_broader_rerun_ready": True,
                "same_scope_process_check_ready": False,
                "config_json": "/tmp/idp_3bead_benchmark_v7_anchor_plus_page4.json",
                "same_scope_config_json": "/tmp/idp_subset.json",
            },
            "rows": [
                {"tier": "validated_current_core"},
                {"tier": "validated_current_watchlist"},
                {"tier": "anchor_backed_expansion"},
                {"tier": "provisional_only_expansion"},
            ],
        },
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "default_feature_mask": "rg_sasa_only",
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "launch_ready_shadow_stress_not_promotion"
    assert s["true_broader_rerun_ready"] is True
    assert s["same_scope_process_check_ready"] is True
    assert s["config_json"] == "/tmp/idp_3bead_benchmark_v7_anchor_plus_page4.json"
    assert "/tmp/idp_3bead_benchmark_v7_anchor_plus_page4.json" in s["command"]
    assert "plus PAGE4" in s["next_required_step"]
    rows = {row["launch_step"]: row for row in payload["rows"]}
    assert rows["scope"]["status"] == "frozen_true_broader_shadow_only"
    assert rows["additional_anchor_backed_targets"]["status"] == "included_first_true_broader_launch"
    assert rows["provisional_targets"]["status"] == "excluded_from_first_true_broader_launch"
