from __future__ import annotations

from tools import build_sarscov2_mpro_render_suite as mod
from tools.wetlab_target_render_utils import load_json


def test_build_sarscov2_mpro_render_suite() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(mod.DEFAULT_ANTIVIRAL_RAIL_JSON),
        load_json(mod.DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON),
        load_json(mod.DEFAULT_EXPORT_BUNDLE_JSON),
        load_json(mod.DEFAULT_VENDOR_COST_JSON),
    )
    summary = payload["summary"]
    artifacts = payload["artifacts"]

    assert summary["status"] == "sarscov2_mpro_render_suite_ready"
    assert summary["partner_track_id"] == "READDI_Korea"
    assert summary["artifact_count"] == 5
    assert artifacts["condition_card"]["structured"]["partner_track"] == "READDI_Korea"
    assert artifacts["host_protease_panel"]["structured"]["packet_role"] == "first-pass deselection panel"
    assert artifacts["assay_packet"]["structured"]["repurposing_compounds"] == "Nirmatrelvir; Boceprevir; Telaprevir"
    assert artifacts["go_no_go_card"]["summary"]["status"] == "sarscov2_mpro_go_no_go_card_ready"
    assert artifacts["partner_export"]["rows"][-1]["artifact"] == "runs/wetlab_mpro_vendor_cost_check_current.md"
