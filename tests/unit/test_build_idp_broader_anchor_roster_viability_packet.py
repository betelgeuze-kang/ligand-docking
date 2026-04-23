from __future__ import annotations

from tools import build_idp_broader_anchor_roster_viability_packet as mod


def test_build_idp_broader_anchor_roster_viability_packet() -> None:
    payload = mod.build_payload(
        {
            "targets": {
                "alpha_synuclein_full": {"source": "literature_compilation_partial", "provenance": {"kind": "compiled_experimental_range"}},
                "fus_lcd": {"source": "literature_inferred_partial", "provenance": {"kind": "paper_or_experiment"}},
                "tau_k18": {"source": "literature_curated_partial", "provenance": {"kind": "paper_or_experiment"}},
                "amyloid_beta_40": {"source": "branch_family_provisional", "provenance": {"kind": "branch_family_prior"}},
                "page4": {"source": "branch_family_provisional", "provenance": {"kind": "branch_family_prior"}},
            }
        },
        {
            "summary": {"controlled_target_count": 3},
            "rows": [
                {"target_name": "alpha_synuclein_full"},
                {"target_name": "fus_lcd"},
                {"target_name": "tau_k18"},
            ],
        },
        {"summary": {"status": "broader_shadow_review_packet_ready"}},
    )
    s = payload["summary"]
    assert s["controlled_target_count"] == 3
    assert s["anchor_backed_target_count"] == 3
    assert s["additional_anchor_backed_target_count"] == 0
    assert s["provisional_only_target_count"] == 2
    assert s["broader_anchor_config_ready"] is False
    rows = {row["target_name"]: row for row in payload["rows"]}
    assert rows["alpha_synuclein_full"]["anchor_class"] == "anchor_backed"
    assert rows["amyloid_beta_40"]["anchor_class"] == "provisional_only"


def test_build_idp_broader_anchor_roster_viability_packet_counts_page4_as_additional_anchor() -> None:
    payload = mod.build_payload(
        {
            "targets": {
                "alpha_synuclein_full": {"source": "literature_compilation_partial", "provenance": {"kind": "compiled_experimental_range"}},
                "fus_lcd": {"source": "literature_inferred_partial", "provenance": {"kind": "paper_or_experiment"}},
                "tau_k18": {"source": "literature_curated_partial", "provenance": {"kind": "paper_or_experiment"}},
                "page4": {"source": "literature_curated_partial", "provenance": {"kind": "paper_or_experiment"}},
            }
        },
        {
            "summary": {"controlled_target_count": 3},
            "rows": [
                {"target_name": "alpha_synuclein_full"},
                {"target_name": "fus_lcd"},
                {"target_name": "tau_k18"},
            ],
        },
        {"summary": {"status": "broader_shadow_review_packet_ready"}},
    )
    s = payload["summary"]
    assert s["additional_anchor_backed_target_count"] == 1
    assert s["first_additional_anchor_backed_target"] == "page4"
    assert s["broader_anchor_config_ready"] is True
    assert "page4 now provides the first additional anchor-backed target" in s["next_required_step"]
