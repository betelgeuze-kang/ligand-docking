from __future__ import annotations

from tools import build_lbdhodh_render_suite as mod
from tools.wetlab_target_render_utils import load_json


def test_build_lbdhodh_render_suite_uses_target_specific_export_copy() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(mod.DEFAULT_NEGLECTED_ROWS_JSON),
        load_json(mod.DEFAULT_NEGLECTED_PACKET_JSON),
        load_json(mod.DEFAULT_OUTREACH_JSON),
        load_json(mod.DEFAULT_EXPORT_BUNDLE_JSON),
        {},
        {},
    )
    export_payload = payload["artifacts"]["partner_export"]
    structured = export_payload["structured"]

    assert structured["email_subject"] == "Leishmania DHODH micro-validation packet: host-DHODH separation from the first assay"
    assert structured["proposal_title"] == "DNDi/IPK neglected-disease micro-validation: Leishmania braziliensis DHODH"
    assert structured["content_fill_status"] == "slot_criteria_only"
