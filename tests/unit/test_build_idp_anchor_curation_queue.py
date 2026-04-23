from __future__ import annotations

from tools import build_idp_anchor_curation_queue as mod


def test_build_idp_anchor_curation_queue_filters_to_provisional_noncontrolled_targets(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_artifact_reference_count", lambda name: 2 if name == "page4" else 0)
    payload = mod.build_payload(
        {
            "targets": {
                "alpha_synuclein_full": {"source": "literature_compilation_partial", "provenance": {"kind": "compiled_experimental_range"}},
                "page4": {"source": "branch_family_provisional", "provenance": {"kind": "branch_family_prior"}},
                "ddx4_n1": {"source": "branch_family_provisional", "provenance": {"kind": "branch_family_prior"}},
            }
        },
        {
            "rows": [
                {"target_name": "alpha_synuclein_full"},
            ]
        },
    )
    s = payload["summary"]
    assert s["candidate_count"] == 2
    assert s["today_open_now"] == "page4"
    rows = {row["target_name"]: row for row in payload["rows"]}
    assert rows["page4"]["priority_band"] == "first_wave_existing_repo_touchpoint"
    assert rows["ddx4_n1"]["priority_band"] == "third_wave_needs_new_curated_anchor"
