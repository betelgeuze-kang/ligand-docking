from __future__ import annotations

from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_candidate_slot_workbook as mod


def test_build_wetlab_wave1_candidate_slot_workbook() -> None:
    payload = mod.build_payload(blueprint_mod.build_payload({"rows": [
        {"target_id": "T. cruzi PDE", "wave": "Wave 1", "partner_rail": "DNDi/IPK neglected-disease rail"},
        {"target_id": "CA IX", "wave": "Wave 1", "partner_rail": "oncology condition-aware rail"},
    ]}))
    summary = payload["summary"]
    assert summary["target_count"] == 2
    assert summary["row_count"] == 12
    rows = payload["rows"]
    assert rows[0]["status"] == "ready_for_manual_fill"
    assert any("human PDE" in row["slot_criteria"] for row in rows if row["target_id"] == "T. cruzi PDE" and row["lane"] == "repurposing")
