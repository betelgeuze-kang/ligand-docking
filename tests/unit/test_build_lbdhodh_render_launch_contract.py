from __future__ import annotations

from tools import build_wetlab_lbdhodh_novelty_fill_map as novelty_mod
from tools import build_wetlab_lbdhodh_repurposing_fill_map as rep_mod
from tools import build_lbdhodh_launch_packet as launch_mod
from tools import build_lbdhodh_render_suite as render_mod
from tools.wetlab_target_render_utils import load_json


def test_lbdhodh_render_and_launch_contract_default_blocked_state() -> None:
    render_payload = render_mod.build_payload(
        load_json(render_mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(render_mod.DEFAULT_NEGLECTED_ROWS_JSON),
        load_json(render_mod.DEFAULT_NEGLECTED_PACKET_JSON),
        load_json(render_mod.DEFAULT_OUTREACH_JSON),
        load_json(render_mod.DEFAULT_EXPORT_BUNDLE_JSON),
        None,
        None,
    )
    condition_card = render_payload["artifacts"]["condition_card"]
    export_payload = render_payload["artifacts"]["partner_export"]
    launch_payload = launch_mod.build_payload(
        render_payload,
        export_payload,
        condition_card,
        {"rows": []},
        {"rows": []},
    )

    assert condition_card["structured"]["host_counterframe"] == "host DHODH counterscreen"
    assert launch_payload["summary"]["host_counterframe"] == "host DHODH counterscreen"
    assert export_payload["summary"]["status"] == "lbdhodh_dndi_ipk_export_pending_compound_fill"
    assert export_payload["structured"]["email_subject"] == "Leishmania DHODH micro-validation packet: host-DHODH separation from the first assay"
    body_row = next(row for row in export_payload["rows"] if row["export_item"] == "email_body")
    assert "host DHODH counterscreen built in from day one" in body_row["value"]
    assert "the current compound-fill status in a single attachment set." in body_row["value"]
    assert launch_payload["summary"]["launch_readiness"] == "blocked_on_compound_fill"
    assert launch_payload["summary"]["repurposing_filled_slot_count"] == 0
    assert launch_payload["summary"]["novelty_filled_slot_count"] == 0
    assert all(row["queue_blocking"] == "content_block" for row in launch_payload["rows"])
    assert launch_payload["summary"]["next_required_step"] == "Keep LbDHODH in the second final2 slot, but do not launch until STK17B resolves and the missing compound lanes are filled."


def test_lbdhodh_launch_contract_ready_when_both_compound_lanes_are_filled() -> None:
    repurposing_fill_map = rep_mod.build_payload(
        load_json(rep_mod.DEFAULT_BRIEF_FILL_QUEUE_JSON),
        load_json(rep_mod.DEFAULT_PACKET_QUEUE_JSON),
    )
    novelty_fill_map = novelty_mod.build_payload(repurposing_fill_map)

    render_payload = render_mod.build_payload(
        load_json(render_mod.DEFAULT_BRIEF_INDEX_JSON),
        load_json(render_mod.DEFAULT_NEGLECTED_ROWS_JSON),
        load_json(render_mod.DEFAULT_NEGLECTED_PACKET_JSON),
        load_json(render_mod.DEFAULT_OUTREACH_JSON),
        load_json(render_mod.DEFAULT_EXPORT_BUNDLE_JSON),
        repurposing_fill_map,
        novelty_fill_map,
    )
    launch_payload = launch_mod.build_payload(
        render_payload,
        render_payload["artifacts"]["partner_export"],
        render_payload["artifacts"]["condition_card"],
        repurposing_fill_map,
        novelty_fill_map,
    )

    assert render_payload["artifacts"]["partner_export"]["summary"]["status"] == "lbdhodh_dndi_ipk_export_ready"
    assert launch_payload["summary"]["launch_readiness"] == "ready_for_serialized_execution"
    assert launch_payload["summary"]["export_status"] == "lbdhodh_dndi_ipk_export_ready"
    assert launch_payload["summary"]["repurposing_filled_slot_count"] == 3
    assert launch_payload["summary"]["novelty_filled_slot_count"] == 3
    assert all(row["queue_blocking"] == "hard_block" for row in launch_payload["rows"])
    assert launch_payload["summary"]["next_required_step"] == "LbDHODH content is fully filled; keep it in the second final2 slot and wait only for STK17B result resolution before launch."
