from __future__ import annotations

from tools import build_gpcr_handoff_bundle as mod


def test_build_gpcr_handoff_bundle() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "safe_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                "blocked_now": "100k_router_promotion",
                "next_safe_experiment": "run another locked-decoy GPCR variant",
            }
        },
        {
            "summary": {
                "endpoint_status": "locked_decoy_apply_safe_router_blocked",
            }
        },
        {
            "summary": {
                "router_status": "paused_blocked",
            }
        },
        {
            "summary": {
                "core_v4_apply_preserves_baseline": True,
                "chembl50_v4_apply_has_ef1_gain": True,
            }
        },
        {
            "summary": {
                "decision": "use chembl50_v4 as the current GPCR locked-decoy apply-safe endpoint; do not promote to the 100k router yet."
            }
        },
    )

    assert payload["summary"]["safe_now"] == "chembl50_v4_locked_decoy_apply_safe_endpoint"
    assert payload["summary"]["blocked_now"] == "100k_router_promotion"
    assert payload["summary"]["check_count"] == 5
    assert payload["summary"]["blocked_check_count"] == 1
    assert payload["summary"]["ready_check_count"] == 3
    assert payload["checklist_rows"][1]["status"] == "blocked"
    assert payload["checklist_rows"][2]["status"] == "ready"
