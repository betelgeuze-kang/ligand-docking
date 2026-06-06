from __future__ import annotations

from tools.product import build_transporter_binder_slot_ledger as mod


def test_build_transporter_binder_slot_ledger() -> None:
    payload = mod.build_payload(
        {"rows": [{"target_id": "AQP1", "wave_label": "first_wave_low_risk"}, {"target_id": "GLUT1", "wave_label": "second_wave_higher_upside"}]},
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "aqp1_placeholder_binder_01",
                    "replacement_is_binder": "1",
                    "suggested_external_candidate": "bacopaside II",
                    "suggested_external_review_bucket": "review_only_first_wave",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "notes": "note",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "anchor": "PMID 27474162",
                    "mechanism_bucket": "functional_aqp1_water_channel_inhibitor",
                    "confidence": "medium",
                }
            ]
        },
        {"rows": [{"candidate_name": "bacopaside II", "review_bucket": "review_only_first_wave", "recommended_verdict": "keep_review_only"}]},
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "glut1_placeholder_binder_01",
                    "replacement_is_binder": "1",
                    "suggested_external_candidate": "cytochalasin B",
                    "suggested_external_review_bucket": "review_only_second_wave",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "notes": "note",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "cytochalasin B",
                    "source_anchor": "PMID 27078104",
                    "evidence_class": "direct_glut1_inhibitor_binding_site_anchor",
                    "evidence_strength": "strong_structural",
                }
            ]
        },
        {"rows": [{"candidate_name": "cytochalasin B", "review_bucket": "review_only_second_wave", "recommended_verdict": "keep_review_only"}]},
    )

    assert payload["summary"]["binder_slot_count"] == 2
    assert payload["summary"]["keep_review_only_count"] == 2
    assert "blocker-closure surface" in payload["summary"]["next_required_step"]
    assert payload["rows"][0]["wave_label"] == "first_wave_low_risk"
    assert payload["rows"][0]["candidate_name"] == "bacopaside II"
    assert payload["rows"][1]["wave_label"] == "second_wave_higher_upside"
    assert payload["rows"][1]["evidence_anchor"] == "PMID 27078104"
