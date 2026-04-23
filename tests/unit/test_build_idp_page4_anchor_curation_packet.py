from __future__ import annotations

from tools import build_idp_page4_anchor_curation_packet as mod


def test_build_idp_page4_anchor_curation_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_name": "page4",
                    "priority_band": "first_wave_existing_repo_touchpoint",
                    "artifact_reference_count": 115,
                }
            ]
        },
        {
            "targets": {
                "page4": {
                    "source": "branch_family_provisional",
                    "rg_mean_range": [24.0, 34.0],
                    "sasa_proxy_mean_range": [700.0, 1700.0],
                    "provenance": {
                        "kind": "branch_family_prior",
                        "citation": "Generated provisional anchor.",
                    },
                }
            }
        },
        {
            "summary": {
                "likely_failure_mechanism": "Borderline page4 slice with weak aggregation discrimination.",
                "current_rg_anchor_error": 0.75,
                "regressed_conditions": ["salt_high"],
                "current_wrong_conditions": ["hydro_high", "salt_high"],
            }
        },
        {
            "target_count": 6,
            "kalman_shadow": {
                "provisional_anchor_row_count": 6,
                "smoothed_feature_count": 0,
                "would_change_state_count": 0,
            },
        },
        {
            "summary": {
                "first_open_source_anchor": "PMC3077599 (2011)",
                "first_open_source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3077599/",
            }
        },
        {
            "summary": {
                "confirmed_anchor_citation": "PMC3077599 (2011)",
                "construct_mapping": "synthetic page4 target likely maps to PAGE4 full-length 102-aa construct candidate",
                "followup_source_anchors": "PMID 26242913 ; PMID 28289210",
            }
        },
        {
            "summary": {
                "status": "page4_phosphorylation_followup_packet_ready",
                "focus_conditions": "ph_low ; ph_high",
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_curation_packet_ready"
    assert s["priority_band"] == "first_wave_existing_repo_touchpoint"
    assert s["source_class"] == "branch_family_provisional"
    assert s["shadow_abstain_expected"] is True
    assert s["provisional_condition_count"] == 6
    assert s["evidence_seed_ready"] is True
    assert s["evidence_seed_artifact"] == "runs/idp_page4_anchor_evidence_seed_current.md"
    assert s["provenance_fill_draft_artifact"] == "runs/idp_page4_anchor_provenance_fill_draft_current.md"
    assert s["citation_confirmed_packet_artifact"] == "runs/idp_page4_anchor_citation_confirmed_packet_current.md"
    assert s["phosphorylation_followup_packet_artifact"] == "runs/idp_page4_phosphorylation_followup_packet_current.md"
    assert s["first_open_source_anchor"] == "PMC3077599 (2011)"
    assert "construct-matched" in s["evidence_search_target"]
    assert "phosphorylation-state follow-up packet" in s["next_required_step"]
    assert "phosphorylation-state follow-up" in s["next_required_step"]
    assert "confirmed citation=PMC3077599 (2011)" in payload["rows"][0]["current_value"]
