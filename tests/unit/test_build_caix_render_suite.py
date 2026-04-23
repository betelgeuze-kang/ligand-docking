from __future__ import annotations

from tools import build_caix_render_suite as mod
from tools.wetlab_target_render_utils import load_json


def test_build_caix_render_suite() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(mod.DEFAULT_CAIX_BRIEF_JSON),
        load_json(mod.DEFAULT_ONCOLOGY_PACKET_JSON),
        load_json(mod.DEFAULT_EXPORT_BUNDLE_JSON),
    )
    summary = payload["summary"]
    artifacts = payload["artifacts"]

    assert summary["status"] == "caix_render_suite_ready"
    assert summary["partner_track_id"] == "oncology_condition_aware"
    assert summary["artifact_count"] == 5
    assert artifacts["condition_card"]["structured"]["acidic_primary_arm"] == "MES-buffered acidic arm centered on pH 6.6"
    assert artifacts["selectivity_panel"]["structured"]["panel_label"] == "CA II plus CA XII counterscreen"
    assert artifacts["go_no_go_card"]["structured"]["primary_promote_rule"] == "acidic-arm CA IX activity plus visible CA II separation"
    assert artifacts["partner_export"]["summary"]["status"] == "caix_oncology_export_ready"
