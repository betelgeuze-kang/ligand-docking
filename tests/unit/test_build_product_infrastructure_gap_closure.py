from __future__ import annotations

from tools import build_product_infrastructure_gap_closure as mod


def test_product_infrastructure_gap_closure_complete() -> None:
    payload = mod.build_product_infrastructure_gap_closure()
    summary = payload["summary"]
    assert summary["status"] == "product_infrastructure_gap_closure_complete"
    assert summary["all_gaps_closed"] is True
    assert summary["closed_gap_count"] == 5
    assert summary["open_gap_ids"] == []
    gap_ids = {row["gap_id"] for row in payload["rows"]}
    assert gap_ids == {"HW-DEP-02", "HW-PROF-01", "HW-PROF-02", "HW-PROF-04", "CB-EXEC"}
