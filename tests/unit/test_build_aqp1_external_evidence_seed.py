from __future__ import annotations

from tools import build_aqp1_external_evidence_seed as mod


def test_build_aqp1_external_evidence_seed_payload() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["candidate_count"] == 5
    assert summary["draft_first_wave_candidate_count"] == 3
    assert summary["caution_only_candidate_count"] == 2
    assert summary["endpoint_status"] == "external_seed_ready_direct_binding_absent"
    assert summary["recommended_first_wave_candidates"] == ["bacopaside II", "AqB013", "AqB011"]
    assert rows[0]["candidate_name"] == "bacopaside II"
    assert rows[0]["recommended_verdict"] == "keep_review_only"
    assert rows[1]["candidate_name"] == "AqB013"
    assert rows[1]["recommended_verdict"] == "keep_review_only"
    assert rows[2]["candidate_name"] == "AqB011"
    assert rows[2]["recommended_verdict"] == "keep_review_only"
    assert rows[3]["recommended_verdict"] == "caution_only"
    assert rows[4]["recommended_verdict"] == "defer"
