from __future__ import annotations

from tools import build_idp_page4_quantitative_anchor_replacement_packet as mod


def test_build_idp_page4_quantitative_anchor_replacement_packet() -> None:
    payload = mod.build_payload(
        {"summary": {"anchor_backed_candidate_ready_now": True}},
        {"summary": {"pending_manual_confirmation_count": 0}},
        {"summary": {"confirmed_anchor_citation": "PMC3077599 (2011)"}},
        {
            "targets": {
                "page4": {
                    "rg_mean_range": [24.0, 34.0],
                    "sasa_proxy_mean_range": [700.0, 1700.0],
                    "contact_persistence_range": [0.03, 0.14],
                    "transient_helicity_range": [0.08, 0.3],
                    "ensemble_diversity_range": [3.0, 11.0],
                    "source": "branch_family_provisional",
                    "provenance": {"kind": "branch_family_prior"},
                }
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_quantitative_anchor_replacement_packet_ready"
    assert s["candidate_ready_now"] is True
    assert s["replacement_completed"] is False
    assert s["quantitative_replacement_row_count"] == 5
    assert s["anchor_backed_target_count_after_replacement"] == 0
    assert payload["rows"][0]["replacement_requirement"] == "construct_matched_quantitative_range_required"


def test_build_idp_page4_quantitative_anchor_replacement_packet_completed() -> None:
    payload = mod.build_payload(
        {"summary": {"anchor_backed_candidate_ready_now": True}},
        {"summary": {"pending_manual_confirmation_count": 0}},
        {"summary": {"confirmed_anchor_citation": "PMC3077599 (2011)"}},
        {
            "targets": {
                "page4": {
                    "rg_mean_range": [34.9, 37.1],
                    "sasa_proxy_mean_range": [700.0, 1700.0],
                    "contact_persistence_range": [0.03, 0.14],
                    "transient_helicity_range": [0.08, 0.3],
                    "ensemble_diversity_range": [3.0, 11.0],
                    "source": "literature_curated_partial",
                    "provenance": {"kind": "paper_or_experiment"},
                }
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_quantitative_anchor_replacement_completed_partial_literature_anchor"
    assert s["replacement_completed"] is True
    assert s["direct_literature_field_count"] == 1
    assert s["proxy_assisted_field_count"] == 4
    assert s["anchor_backed_target_count_after_replacement"] == 1
    assert payload["rows"][0]["replacement_status"] == "direct_literature_range_applied"
    assert payload["rows"][1]["replacement_status"] == "proxy_assisted_range_carried_forward_under_literature_partial_anchor"
