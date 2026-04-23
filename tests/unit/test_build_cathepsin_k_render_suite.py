from __future__ import annotations

from tools import build_cathepsin_k_render_suite as mod


PORTFOLIO = {
    "rows": [
        {
            "target_id": "Cathepsin K",
            "partner_rail": "acidic protease condition-aware rail",
            "source_anchor": "Cathepsin K acidic condition activity literature",
            "main_risk": "External partner pull is weaker than CA IX and prior target history is more mixed.",
            "primary_strength": "Good acidic-pH mechanistic demo with tractable protease biochemistry.",
        }
    ]
}
VALIDATION = {
    "rows": [
        {
            "target_id": "Cathepsin K",
            "primary_companion_panel": "related cathepsin / pH-context specificity panel",
            "companion_why": "Acidic protease stories need class selectivity and condition specificity together.",
            "outbound_rule": "Ship this companion panel alongside the first validation packet, not later.",
        }
    ]
}


def test_build_cathepsin_k_render_suite() -> None:
    payload = mod.build_payload(PORTFOLIO, VALIDATION)
    summary = payload["summary"]
    artifacts = payload["artifacts"]

    assert summary["status"] == "cathepsin_k_render_suite_ready"
    assert summary["partner_track_id"] == "acidic_protease_wave2"
    assert summary["artifact_count"] == 4
    assert artifacts["condition_card"]["structured"]["acidic_primary_arm"] == "acidic recombinant Cathepsin K fluorogenic arm"
    assert artifacts["selectivity_panel"]["structured"]["panel_label"] == "related cathepsin / pH-context specificity panel"
    assert artifacts["go_no_go_card"]["structured"]["primary_promote_rule"] == "acidic-arm Cathepsin K activity plus related-cathepsin separation and weaker neutral replay"
