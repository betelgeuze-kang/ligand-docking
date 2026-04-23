from __future__ import annotations

from tools import build_wetlab_broad_screen_bridge as bridge_mod
from tools import build_wetlab_broad_screen_library_spec as library_mod
from tools import build_wetlab_broad_screen_queue as queue_mod
from tools import build_wetlab_broad_screen_repurposing_autofill as mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod


def test_build_wetlab_broad_screen_repurposing_autofill_promotes_top3_rows() -> None:
    portfolio = portfolio_mod.build_payload()
    library = library_mod.build_payload()
    broad_queue = queue_mod.build_payload(portfolio, library)
    bridge = bridge_mod.build_payload(library, broad_queue)
    bulk_results = {
        "rows": [
            {"target_id": "CA IX", "compound_name": "BulkCAIXA", "bulk_rank": 1, "bulk_score": 9.5},
            {"target_id": "CA IX", "compound_name": "BulkCAIXB", "bulk_rank": 2, "bulk_score": 8.0},
            {"target_id": "CA IX", "compound_name": "BulkCAIXC", "bulk_rank": 3, "bulk_score": 7.5},
        ]
    }

    payload = mod.build_payload(portfolio, bridge, bulk_results)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_broad_screen_repurposing_autofill_ready"
    assert summary["bulk_result_source_present"] is True
    assert summary["override_target_count"] == 1
    assert summary["override_row_count"] == 3
    assert [row["compound_name"] for row in rows] == ["BulkCAIXA", "BulkCAIXB", "BulkCAIXC"]
    assert all(row["row_status"] == "bulk_override_ready" for row in rows)
