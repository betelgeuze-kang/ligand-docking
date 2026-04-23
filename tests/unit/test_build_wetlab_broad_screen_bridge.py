from __future__ import annotations

from tools import build_wetlab_broad_screen_bridge as mod
from tools import build_wetlab_broad_screen_library_spec as library_mod
from tools import build_wetlab_broad_screen_queue as queue_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod


def test_build_wetlab_broad_screen_bridge_describes_bulk_to_packet_reduction() -> None:
    portfolio = portfolio_mod.build_payload()
    library_spec = library_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, library_spec)

    payload = mod.build_payload(library_spec, queue)
    summary = payload["summary"]

    assert summary["status"] == "wetlab_broad_screen_bridge_ready"
    assert summary["library_lane"] == "broad_procurement_100k"
    assert summary["library_size"] == 100000
    assert summary["queue_row_count"] == 260
    assert summary["final_packet_shape"] == "top-3 repurposing + top-3 novelty"
    assert [row["bridge_stage"] for row in payload["rows"]] == [
        "bulk_screen",
        "anti_target_filter",
        "condition_rerank",
        "packet_binding",
    ]
