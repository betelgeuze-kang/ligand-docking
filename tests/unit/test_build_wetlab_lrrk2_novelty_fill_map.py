from __future__ import annotations

from tools import build_wetlab_lrrk2_novelty_fill_map as mod


def test_build_wetlab_lrrk2_novelty_fill_map() -> None:
    payload = mod.build_payload()
    summary = payload['summary']

    assert summary['status'] == 'wetlab_lrrk2_novelty_fill_map_ready'
    assert summary['target_id'] == 'LRRK2'
    assert summary['filled_slot_count'] == 3
    assert [row['novelty_compound_name'] for row in payload['rows']] == ['MLi-2', 'PFE-360', 'BIIB122 (DNL151)']
