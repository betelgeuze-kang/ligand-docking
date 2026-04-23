from __future__ import annotations

from tools import build_wetlab_wave1_target_brief_matrix as mod


def test_build_wetlab_wave1_target_brief_matrix() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_target_brief_matrix_ready"
    assert summary["row_count"] == 8
    assert "human PDE" in rows["T. cruzi PDE"]["anti_target_panel"]
    assert rows["CA IX"]["main_external_lab_objection"].startswith("This will just rediscover")
