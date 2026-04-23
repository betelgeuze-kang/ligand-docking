from __future__ import annotations

from tools import build_wetlab_prep_artifact_lane as mod


def test_build_wetlab_prep_artifact_lane() -> None:
    payload = mod.build_payload(
        mod._load_json(mod.DEFAULT_MPRO_RENDER_SUITE_JSON),
        mod._load_json(mod.DEFAULT_CAIX_RENDER_SUITE_JSON),
        mod._load_json(mod.DEFAULT_TCRUZI_RENDER_SUITE_JSON),
    )
    summary = payload["summary"]
    rows = {row["execution_target"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_prep_artifact_lane_ready"
    assert summary["target_count"] == 3
    assert summary["ready_render_suite_count"] == 3
    assert rows["SARS-CoV-2 Mpro"]["parallel_prep_targets"] == "CA IX; T. cruzi PDE"
    assert rows["CA IX"]["serialized_execution_slot"] == "active_slot_2"
    assert rows["T. cruzi PDE"]["parallel_prep_targets"] == ""
