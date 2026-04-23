from __future__ import annotations

from tools import build_cathepsin_k_launch_packet as mod
from tools import build_cathepsin_k_render_suite as render_mod
from tools import build_wetlab_cathepsin_k_novelty_fill_map as novelty_mod
from tools import build_wetlab_cathepsin_k_repurposing_fill_map as rep_mod


PORTFOLIO = {
    "rows": [
        {
            "target_id": "Cathepsin K",
            "partner_rail": "acidic protease condition-aware rail",
            "source_anchor": "Cathepsin K acidic condition activity literature",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/24958728/",
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


def test_build_cathepsin_k_launch_packet() -> None:
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

    assert summary["status"] == "cathepsin_k_launch_packet_ready"
    assert summary["serialized_queue_rank"] == 1
    assert summary["serialized_run_order"] == "1_of_5_after_final2"
    assert summary["partner_track_id"] == "acidic_protease_wave2"
    assert summary["required_artifact_count"] == 5
    assert summary["acidic_primary_arm"] == "sodium-acetate or MES-like acidic arm centered on pH 4.5 to 5.0"
    assert summary["repurposing_filled_slot_count"] == 3
    assert summary["novelty_filled_slot_count"] == 3
    assert summary["launch_readiness"] == "ready_for_serialized_execution"
