from __future__ import annotations

from tools import build_dengue_ns2b_ns3_protease_render_suite as mod


PORTFOLIO = {
    "rows": [
        {
            "target_id": "Dengue NS2B-NS3 protease",
            "partner_rail": "IPK / dengue antiviral rail",
            "source_anchor": "IPK anti-dengue screening service context",
            "source_url": "https://www.ip-korea.org/impact/service.php",
            "main_risk": "Flat water-exposed pocket lowers first-pass hit probability versus PLpro/Mpro.",
            "primary_strength": "Strong fit for shallow wet pocket and SASA-driven discrimination; partner context exists in anti-dengue screening lanes.",
        }
    ]
}
VALIDATION = {
    "rows": [
        {
            "target_id": "Dengue NS2B-NS3 protease",
            "primary_companion_panel": "flaviviral protease orthogonal panel plus shallow-pocket negative controls",
            "companion_why": "Flat wet pockets need stronger discrimination against sticky false positives.",
            "outbound_rule": "Ship this companion panel alongside the first validation packet, not later.",
        }
    ]
}
REPURPOSING = {
    "rows": [
        {"target_id": "Dengue NS2B-NS3 protease", "compound_name": "Eltrombopag"},
        {"target_id": "Dengue NS2B-NS3 protease", "compound_name": "Policresulen"},
        {"target_id": "Dengue NS2B-NS3 protease", "compound_name": "Boceprevir"},
    ]
}
NOVELTY = {
    "rows": [
        {"target_id": "Dengue NS2B-NS3 protease", "novelty_compound_name": "BP2109"},
        {"target_id": "Dengue NS2B-NS3 protease", "novelty_compound_name": "Curcumin"},
        {"target_id": "Dengue NS2B-NS3 protease", "novelty_compound_name": "Punicalagin"},
    ]
}


def test_build_dengue_ns2b_ns3_protease_render_suite() -> None:
    payload = mod.build_payload(PORTFOLIO, VALIDATION, REPURPOSING, NOVELTY)
    summary = payload["summary"]
    artifacts = payload["artifacts"]

    assert summary["status"] == "dengue_ns2b_ns3_protease_render_suite_ready"
    assert summary["partner_track_id"] == "IPK_dengue"
    assert summary["artifact_count"] == 5
    assert artifacts["condition_card"]["structured"]["primary_biochemical_arm"] == "fluorogenic or AlphaScreen NS2B-NS3 protease arm under neutral-to-mildly basic assay conditions"
    assert artifacts["selectivity_panel"]["structured"]["panel_label"] == "flaviviral protease orthogonal panel plus shallow-pocket negative controls"
    assert artifacts["go_no_go_card"]["structured"]["primary_promote_rule"] == "dengue NS2B-NS3 signal survives the orthogonal flaviviral replay and shallow-pocket cleanup"
