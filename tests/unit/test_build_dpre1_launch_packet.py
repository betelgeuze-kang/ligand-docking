from __future__ import annotations

from tools import build_dpre1_launch_packet as mod
from tools import build_dpre1_render_suite as render_mod
from tools import build_wetlab_dpre1_novelty_fill_map as novelty_mod
from tools import build_wetlab_dpre1_repurposing_fill_map as rep_mod


PORTFOLIO = {
    "rows": [
        {
            "target_id": "DprE1",
            "partner_rail": "TB Alliance / academic TB rail",
            "source_anchor": "OPC-167832 antituberculosis activity paper",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/32229496/",
            "main_risk": "Whole-cell signal can outrun target-specific evidence if the first packet is not kept biochemical-first.",
            "primary_strength": "Clinical-stage DprE1 anchors exist, so the first packet can stay bounded and still be decision-grade.",
        }
    ]
}
VALIDATION = {
    "rows": [
        {
            "target_id": "DprE1",
            "primary_companion_panel": "host-enzyme and whole-cell orthogonal validation panel",
            "companion_why": "DprE1 rows need host-enzyme cleanup before whole-cell interpretation.",
            "outbound_rule": "Ship this companion panel alongside the first validation packet, not later.",
        }
    ]
}


def test_build_dpre1_launch_packet() -> None:
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

    assert summary["status"] == "dpre1_launch_packet_ready"
    assert summary["serialized_queue_rank"] == 3
    assert summary["serialized_run_order"] == "3_of_5_in_wave2"
    assert summary["partner_track_id"] == "TB_Alliance"
    assert summary["primary_biochemical_arm"] == "recombinant DprE1 enzymatic inhibition arm with simple target-engagement framing"
    assert summary["repurposing_filled_slot_count"] == 3
    assert summary["novelty_filled_slot_count"] == 3
    assert summary["launch_readiness"] == "ready_for_serialized_execution"
