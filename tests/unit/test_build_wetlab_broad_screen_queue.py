from __future__ import annotations

from tools import build_wetlab_broad_screen_library_spec as library_mod
from tools import build_wetlab_broad_screen_queue as mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod


def test_build_wetlab_broad_screen_queue_creates_target_by_shard_rows() -> None:
    portfolio = portfolio_mod.build_payload()
    library_spec = library_mod.build_payload()

    payload = mod.build_payload(portfolio, library_spec)
    summary = payload["summary"]

    assert summary["status"] == "wetlab_broad_screen_queue_ready"
    assert summary["target_count"] == 13
    assert summary["library_lane"] == "broad_procurement_100k"
    assert summary["library_size"] == 100000
    assert summary["shard_size"] == 5000
    assert summary["shard_count_per_target"] == 20
    assert summary["total_queue_rows"] == 260

    first = payload["rows"][0]
    assert first["target_id"] == "CA IX"
    assert first["shard_id"] == "01_of_20"
    assert first["compound_index_start"] == 1
    assert first["compound_index_end"] == 5000

    last = payload["rows"][-1]
    assert last["target_id"] == "LRRK2"
    assert last["shard_id"] == "20_of_20"
    assert last["compound_index_start"] == 95001
    assert last["compound_index_end"] == 100000
