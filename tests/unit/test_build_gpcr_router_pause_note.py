from __future__ import annotations

from tools import build_gpcr_router_pause_note as mod


def test_build_gpcr_router_pause_note() -> None:
    payload = mod.build_payload(
        {"summary": {"endpoint_label": "GPCR chembl50_v4 locked-decoy apply-safe endpoint"}},
        {"decision": "no_go_for_100k_router", "rationale": "tiny PR regression remains"},
    )
    assert payload["summary"]["router_status"] == "paused_blocked"
    assert payload["summary"]["decision"] == "no_go_for_100k_router"
