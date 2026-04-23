from __future__ import annotations

from tools import build_wetlab_lrrk2_repurposing_fill_map as mod


def test_build_wetlab_lrrk2_repurposing_fill_map() -> None:
    payload = mod.build_payload()
    summary = payload['summary']

    assert summary['status'] == 'wetlab_lrrk2_repurposing_fill_map_ready'
    assert summary['target_id'] == 'LRRK2'
    assert summary['filled_slot_count'] == 3
    assert [row['compound_name'] for row in payload['rows']] == ['Crizotinib', 'Sunitinib', 'Nilotinib']
