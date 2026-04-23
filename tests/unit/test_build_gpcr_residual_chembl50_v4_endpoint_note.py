from __future__ import annotations

from tools import build_gpcr_residual_chembl50_v4_endpoint_note as mod


def test_build_gpcr_residual_chembl50_v4_endpoint_note() -> None:
    payload = mod.build_payload(
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"core_v4_apply_preserves_baseline": True, "chembl50_v4_apply_has_ef1_gain": True}},
        {"decision": "go_for_locked_decoy_apply_trial"},
        {"decision": "no_go_for_100k_router"},
    )
    assert payload["summary"]["router_status"] == "blocked"
    assert payload["summary"]["core_v4_apply_preserves_baseline"] is True
