from __future__ import annotations

from tools import build_dengue_ns2b_ns3_protease_launch_packet as mod
from tools import build_dengue_ns2b_ns3_protease_render_suite as render_mod
from tools import build_wetlab_dengue_ns2b_ns3_protease_novelty_fill_map as novelty_mod
from tools import build_wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map as rep_mod


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


def test_build_dengue_ns2b_ns3_protease_launch_packet() -> None:
    rep_payload = rep_mod.build_payload()
    nov_payload = novelty_mod.build_payload(rep_payload)
    render_payload = render_mod.build_payload(PORTFOLIO, VALIDATION, rep_payload, nov_payload)
    payload = mod.build_payload(
        render_payload,
        render_payload["artifacts"]["condition_card"],
        rep_payload,
        nov_payload,
    )
    summary = payload["summary"]

    assert summary["status"] == "dengue_ns2b_ns3_protease_launch_packet_ready"
    assert summary["serialized_queue_rank"] == 2
    assert summary["serialized_run_order"] == "2_of_5_in_wave2"
    assert summary["partner_track_id"] == "IPK_dengue"
    assert summary["required_artifact_count"] == 5
    assert summary["primary_biochemical_arm"] == "recombinant dengue NS2B-NS3 protease arm with shallow-pocket-aware detergent sanity"
    assert summary["repurposing_filled_slot_count"] == 3
    assert summary["novelty_filled_slot_count"] == 3
    assert summary["launch_readiness"] == "ready_for_serialized_execution"
