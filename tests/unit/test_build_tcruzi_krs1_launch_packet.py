from __future__ import annotations

from tools.wetlab import build_tcruzi_krs1_launch_packet as mod
from tools.wetlab import build_tcruzi_krs1_render_suite as render_mod
from tools import build_wetlab_tcruzi_krs1_novelty_fill_map as novelty_mod
from tools import build_wetlab_tcruzi_krs1_repurposing_fill_map as rep_mod


PORTFOLIO = {
    "rows": [
        {
            "target_id": "T. cruzi KRS1",
            "partner_rail": "DNDi Chagas backup rail",
            "source_anchor": "Sci Transl Med TcKRS1 efficacy paper",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/40632837/",
            "main_risk": "Whole-parasite context can outrun direct target evidence if the packet is not kept biochemical-first.",
            "primary_strength": "A bounded biochemical-to-parasite bridge already exists for TcKRS1, so the first packet can stay decision-grade.",
        }
    ]
}
VALIDATION = {
    "rows": [
        {
            "target_id": "T. cruzi KRS1",
            "primary_companion_panel": "host aaRS selectivity panel",
            "companion_why": "aaRS programs need explicit host cleanup before parasite-context signal is taken seriously.",
            "outbound_rule": "Ship the host-aaRS panel with the first packet, not later.",
        }
    ]
}


def test_build_tcruzi_krs1_launch_packet() -> None:
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

    assert summary["status"] == "tcruzi_krs1_launch_packet_ready"
    assert summary["serialized_queue_rank"] == 4
    assert summary["serialized_run_order"] == "4_of_5_in_wave2"
    assert summary["partner_track_id"] == "DNDi_Chagas_backup"
    assert summary["primary_biochemical_arm"] == "recombinant T. cruzi KRS1 enzymatic inhibition arm with simple target-engagement framing"
    assert summary["repurposing_filled_slot_count"] == 3
    assert summary["novelty_filled_slot_count"] == 3
    assert summary["launch_readiness"] == "ready_for_serialized_execution"
    assert summary["next_target_on_success"] == "LRRK2"
