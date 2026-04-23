from __future__ import annotations

from tools import build_tcruzi_pde_render_suite as mod
from tools.wetlab_target_render_utils import load_json


def test_build_tcruzi_pde_render_suite() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(mod.DEFAULT_NEGLECTED_PACKET_JSON),
        load_json(mod.DEFAULT_EXPORT_BUNDLE_JSON),
    )
    summary = payload["summary"]
    artifacts = payload["artifacts"]

    assert summary["status"] == "tcruzi_pde_render_suite_ready"
    assert summary["partner_track_id"] == "DNDi_IPK"
    assert summary["artifact_count"] == 5
    assert artifacts["condition_card"]["structured"]["partner_track"] == "DNDi_IPK"
    assert artifacts["selectivity_panel"]["structured"]["panel_label"] == "human PDE family mini-panel"
    assert artifacts["go_no_go_card"]["structured"]["promote_rule"] == "parasite PDE signal plus human PDE separation"
    assert artifacts["partner_export"]["summary"]["status"] == "tcruzi_pde_dndi_ipk_export_ready"
