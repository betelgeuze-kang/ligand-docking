from __future__ import annotations

from tools import build_family_evidence_acquisition_queue as mod


def test_build_family_evidence_acquisition_queue_prioritizes_count_improving_rows() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "capture_rank": 1,
                    "capture_status": "captured_direct_conflict_review_only",
                    "manual_promotion_blocker": "direct_ca2_inhibitor_conflict_present",
                    "manual_next_required_action": "keep_review_only_conflict_documented",
                    "source_title": "CA2 conflict paper",
                    "source_url": "https://example.org/ca2-conflict",
                    "manual_decision_note": "conflict stays review-only",
                    "commit_status": "confirmed_review_only",
                    "review_phase": "today_focus",
                },
                {
                    "packet_step": "core_non_binder_02",
                    "ligand": "metformin",
                    "capture_rank": 2,
                    "capture_status": "captured_no_direct_negative_source_found",
                    "manual_promotion_blocker": "no_direct_ca2_negative_evidence_located_after_research",
                    "manual_next_required_action": "keep_review_only_no_direct_negative_source",
                    "source_title": "CA2 gap paper",
                    "source_url": "https://example.org/ca2-gap",
                    "manual_decision_note": "no direct CA2-negative evidence yet",
                    "commit_status": "confirmed_review_only",
                    "review_phase": "today_focus",
                },
            ]
        },
        {
            "rows": [
                {"packet_step": "core_non_binder_01", "review_phase": "today_focus"},
                {"packet_step": "core_non_binder_02", "review_phase": "today_focus"},
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "priority_rank": 10,
                    "capture_status": "captured_supportive",
                    "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                    "evidence_need_class": "target_specific_human_pxr_binder_evidence",
                    "manual_next_required_action": "curate_quantitative_binding_value",
                    "source_title": "PXR supportive binder source",
                    "source_url": "https://example.org/pxr-binder-gap",
                    "source_note": "literature-backed human PXR binder support is confirmed but still lacks quantitative provenance",
                    "commit_status": "defer",
                },
                {
                    "packet_step": "ood_eval_non_binder_02",
                    "replacement_ligand_id": "ibuprofen",
                    "priority_rank": 13,
                    "capture_status": "captured_review_only_conflict",
                    "manual_promotion_blocker": "manual_negative_evidence_review",
                    "evidence_need_class": "target_specific_human_pxr_negative_like_conflict_resolution",
                    "manual_next_required_action": "manual_negative_evidence_review",
                    "source_title": "PXR weak conflict",
                    "source_url": "https://example.org/pxr-weak-conflict",
                    "source_note": "weak upper-bound proxy only",
                    "commit_status": "review_only",
                },
            ]
        },
        {
            "rows": [
                {"packet_step": "ood_fit_binder_01", "plan_phase": "second_pass", "commit_status": "defer"},
                {"packet_step": "ood_eval_non_binder_02", "plan_phase": "first_hour", "commit_status": "review_only"},
            ]
        },
    )

    summary = payload["summary"]
    assert summary["queue_row_count"] == 4
    assert summary["high_priority_count"] == 2
    assert summary["count_improving_candidate_count"] == 2
    assert summary["supportive_manual_confirmation_count"] == 0
    assert summary["actionable_conflict_resolution_count"] == 0
    assert summary["low_probability_conflict_count"] == 0
    assert summary["review_only_documentation_count"] == 2

    first_row, second_row, third_row, fourth_row = payload["rows"]
    assert first_row["family"] == "pxr"
    assert first_row["ligand"] == "bexarotene"
    assert first_row["priority_tier"] == "P0_count_improving_binder_gap"
    assert first_row["claim_impact"] == "potential_count_improving_if_quantitative_binder_provenance_found"
    assert first_row["actionability_bucket"] == "count_improving_gap"
    assert first_row["state_change_potential"] == "high"
    assert "quantitative human NR1I2/PXR" in first_row["search_scope"]

    assert second_row["family"] == "ca2"
    assert second_row["ligand"] == "metformin"
    assert second_row["priority_tier"] == "P1_count_improving_negative_gap"
    assert second_row["claim_impact"] == "potential_count_improving_if_direct_negative_found"

    assert third_row["family"] == "ca2"
    assert third_row["priority_tier"] == "P3_review_only_documentation"
    assert third_row["promotion_if_resolved"] == "no"

    assert fourth_row["family"] == "pxr"
    assert fourth_row["priority_tier"] == "P3_review_only_documentation"
    assert "weak upper-bound signal" in fourth_row["stop_condition"]


def test_build_family_evidence_acquisition_queue_separates_low_probability_pxr_conflicts() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"rows": []},
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_01",
                    "replacement_ligand_id": "acetaminophen",
                    "priority_rank": 5,
                    "capture_status": "captured_conflict",
                    "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "evidence_need_class": "target_specific_human_pxr_negative_or_conflict_resolution",
                    "manual_next_required_action": "manual_curated_search_or_defer",
                    "source_title": "ChEMBL CHEMBL3401 activity query for acetaminophen returned 2 records.",
                    "source_url": "https://example.org/chembl-acetaminophen",
                    "source_note": "Antagonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method (AC50 =23999.9 nM); Agonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method (AC50 >30000.0 nM).",
                    "commit_status": "confirmed_defer",
                },
                {
                    "packet_step": "core_eval_non_binder_02",
                    "replacement_ligand_id": "caffeine",
                    "priority_rank": 6,
                    "capture_status": "captured_conflict",
                    "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "evidence_need_class": "target_specific_human_pxr_negative_or_conflict_resolution",
                    "manual_next_required_action": "manual_curated_search_or_defer",
                    "source_title": "PubChem CID 2519 human PXR qHTS summary for caffeine.",
                    "source_url": "https://example.org/pubchem-caffeine",
                    "source_note": "AID 1346982 gives Potency 5.5148 uM with outcome Active. Conflicting human PXR qHTS inactive rows also remain present.",
                    "commit_status": "confirmed_defer",
                },
            ]
        },
        {
            "rows": [
                {"packet_step": "core_eval_non_binder_01", "plan_phase": "same_day_followup", "commit_status": "confirmed_defer"},
                {"packet_step": "core_eval_non_binder_02", "plan_phase": "same_day_followup", "commit_status": "confirmed_defer"},
            ]
        },
    )

    summary = payload["summary"]
    assert summary["queue_row_count"] == 2
    assert summary["high_priority_count"] == 0
    assert summary["count_improving_candidate_count"] == 0
    assert summary["low_probability_conflict_count"] == 2
    assert "No strong CA2/PXR count-improving queue rows remain" in summary["next_required_step"]

    first_row, second_row = payload["rows"]
    assert first_row["ligand"] == "acetaminophen"
    assert first_row["priority_tier"] == "P2_low_probability_conflict_cleanup"
    assert first_row["actionability_bucket"] == "low_probability_conflict_cleanup"
    assert first_row["state_change_potential"] == "low"
    assert first_row["conflict_lane"] == "exact_human_dual_mode_activity_conflict"
    assert first_row["claim_impact"] == "low_probability_count_improving_only_if_orthogonal_human_source_found"

    assert second_row["ligand"] == "caffeine"
    assert second_row["priority_tier"] == "P2_low_probability_conflict_cleanup"
    assert second_row["actionability_bucket"] == "low_probability_conflict_cleanup"
    assert second_row["state_change_potential"] == "low"
    assert second_row["conflict_lane"] == "direct_human_qhts_active_inactive_conflict"
