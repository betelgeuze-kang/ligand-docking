from __future__ import annotations

from tools import build_lrrk2_launch_packet as mod
from tools import build_lrrk2_render_suite as render_mod
from tools import build_wetlab_lrrk2_novelty_fill_map as novelty_mod
from tools import build_wetlab_lrrk2_repurposing_fill_map as rep_mod

PORTFOLIO = {
    'rows': [
        {
            'target_id': 'LRRK2',
            'partner_rail': 'MJFF translational Parkinson\'s rail',
            'source_anchor': 'MJFF LRRK2 targets-to-therapies context',
            'source_url': 'https://www.michaeljfox.org/targets-therapies-initiative',
            'main_risk': 'Large flexible kinase with higher assay and biology friction than the first-wave kinase targets.',
            'primary_strength': 'Major translational disease interest and real target-validation community support.',
        }
    ]
}
VALIDATION = {
    'rows': [
        {
            'target_id': 'LRRK2',
            'primary_companion_panel': 'kinase selectivity and CNS-relevant liability panel',
            'companion_why': 'Large flexible kinase stories are weak without selectivity and translational sanity checks.',
            'outbound_rule': 'Ship this companion panel alongside the first validation packet, not later.',
        }
    ]
}


def test_build_lrrk2_launch_packet() -> None:
    rep_payload = rep_mod.build_payload()
    nov_payload = novelty_mod.build_payload()
    render_payload = render_mod.build_payload(PORTFOLIO, VALIDATION, rep_payload, nov_payload)
    payload = mod.build_payload(render_payload, render_payload['artifacts']['condition_card'], rep_payload, nov_payload)
    summary = payload['summary']

    assert summary['status'] == 'lrrk2_launch_packet_ready'
    assert summary['serialized_queue_rank'] == 5
    assert summary['serialized_run_order'] == '5_of_5_in_wave2'
    assert summary['partner_track_id'] == 'MJFF_LRRK2'
    assert summary['required_artifact_count'] == 5
    assert summary['primary_biochemical_arm'] == 'recombinant LRRK2 kinase enzymatic inhibition arm with simple target-engagement framing'
    assert summary['repurposing_filled_slot_count'] == 3
    assert summary['novelty_filled_slot_count'] == 3
    assert summary['launch_readiness'] == 'ready_for_serialized_execution'
