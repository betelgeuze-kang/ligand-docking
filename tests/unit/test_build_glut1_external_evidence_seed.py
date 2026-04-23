from __future__ import annotations

from tools import build_glut1_external_evidence_seed as mod


def test_build_glut1_external_evidence_seed_payload() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["candidate_count"] == 5
    assert summary["draft_second_wave_candidate_count"] == 3
    assert summary["direct_quantitative_binding_candidate_count"] == 1
    assert summary["recommended_second_wave_candidates"] == ["cytochalasin B", "WZB117", "STF-31"]
    assert rows[0]["candidate_name"] == "cytochalasin B"
    assert rows[1]["candidate_name"] == "WZB117"
