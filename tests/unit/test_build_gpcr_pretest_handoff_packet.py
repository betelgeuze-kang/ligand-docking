from __future__ import annotations

from tools import build_gpcr_pretest_handoff_packet as mod


def test_build_gpcr_pretest_handoff_packet() -> None:
    payload = mod.build_payload(
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"router_status": "paused_blocked"}},
    )
    assert payload["summary"]["safe_now"] == "chembl50_v4_locked_decoy_apply_safe_endpoint"
    assert payload["summary"]["blocked_now"] == "100k_router_promotion"
    assert payload["summary"]["router_status"] == "paused_blocked"

