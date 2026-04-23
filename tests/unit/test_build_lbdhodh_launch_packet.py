from __future__ import annotations

from tools import build_wetlab_lbdhodh_novelty_fill_map as novelty_mod
from tools import build_wetlab_lbdhodh_repurposing_fill_map as rep_mod
from tools import build_lbdhodh_launch_packet as mod
from tools.wetlab_target_render_utils import load_json


def test_build_lbdhodh_launch_packet_preserves_host_counterframe_and_content_ready_contract() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_RENDER_SUITE_JSON),
        load_json(mod.DEFAULT_EXPORT_JSON),
        load_json(mod.DEFAULT_CONDITION_CARD_JSON),
        rep_mod.build_payload(load_json(rep_mod.DEFAULT_BRIEF_FILL_QUEUE_JSON), load_json(rep_mod.DEFAULT_PACKET_QUEUE_JSON)),
        novelty_mod.build_payload(rep_mod.build_payload(load_json(rep_mod.DEFAULT_BRIEF_FILL_QUEUE_JSON), load_json(rep_mod.DEFAULT_PACKET_QUEUE_JSON))),
    )
    summary = payload["summary"]

    assert summary["status"] == "lbdhodh_launch_packet_ready"
    assert summary["host_counterframe"] == "host DHODH counterscreen"
    assert summary["launch_readiness"] == "ready_for_serialized_execution"
    assert summary["repurposing_filled_slot_count"] == 3
    assert summary["novelty_filled_slot_count"] == 3
