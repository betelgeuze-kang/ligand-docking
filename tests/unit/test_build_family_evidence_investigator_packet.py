from __future__ import annotations

from tools import build_family_evidence_investigator_packet as mod


def test_build_family_evidence_investigator_packet_uses_top_queue_rows_and_routes() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "queue_rank": 1,
                    "family": "pxr",
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "priority_tier": "P2_supportive_manual_confirmation",
                    "phase_or_band": "second_pass",
                    "current_policy_bucket": "defer",
                    "claim_impact": "manual_confirmation_needed_before_count_improving",
                    "actionability_bucket": "supportive_manual_confirmation",
                    "state_change_potential": "medium",
                    "evidence_need_class": "target_specific_human_pxr_binder_evidence",
                    "blocking_reason": "activity_present_manual_confirmation_required",
                    "primary_source_title": "ChEMBL gap",
                    "primary_source_url": "https://example.org/chembl-gap",
                    "stop_condition": "keep deferred if no binder evidence",
                    "promotion_if_resolved": "yes",
                },
                {
                    "queue_rank": 2,
                    "family": "ca2",
                    "packet_step": "core_non_binder_02",
                    "ligand": "metformin",
                    "priority_tier": "P1_count_improving_negative_gap",
                    "phase_or_band": "today_focus",
                    "current_policy_bucket": "review_only",
                    "claim_impact": "potential_count_improving_if_direct_negative_found",
                    "actionability_bucket": "count_improving_gap",
                    "evidence_need_class": "direct_ca2_negative_evidence",
                    "blocking_reason": "no_direct_ca2_negative_evidence_located_after_research",
                    "primary_source_title": "Existing CA2 anchor",
                    "primary_source_url": "https://example.org/ca2-anchor",
                    "stop_condition": "keep review-only if non-specific",
                    "promotion_if_resolved": "yes",
                },
                {
                    "queue_rank": 3,
                    "family": "pxr",
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "priority_tier": "P2_conflict_resolution",
                    "phase_or_band": "same_day_followup",
                    "current_policy_bucket": "defer",
                    "claim_impact": "potential_count_improving_if_conflict_resolved",
                    "actionability_bucket": "actionable_conflict_resolution",
                    "state_change_potential": "medium",
                    "conflict_lane": "generic_human_proxy_conflict",
                    "evidence_need_class": "target_specific_human_pxr_negative_or_conflict_resolution",
                    "blocking_reason": "activity_proxy_conflicts_with_non_binder",
                    "primary_source_title": "Conflict anchor",
                    "primary_source_url": "https://example.org/pxr-conflict",
                    "stop_condition": "keep deferred if conflict remains",
                    "promotion_if_resolved": "yes",
                },
            ]
        },
        top_n=2,
    )

    summary = payload["summary"]
    assert summary["focus_row_count"] == 2
    assert summary["requested_top_n"] == 2
    assert summary["focus_mode"] == "actionable_non_confirmation_rows"
    assert summary["included_family_count"] == 2
    assert summary["count_improving_focus_count"] == 2
    assert summary["low_probability_conflict_focus_count"] == 0
    assert summary["primary_focus_ligand"] == "metformin"
    assert summary["queue_span"] == "2-3"

    first_row, second_row = payload["rows"]
    assert first_row["ligand"] == "metformin"
    assert first_row["primary_search_route_label"] == "PubMed exact target query"
    assert first_row["secondary_search_route_label"] == "Europe PMC exact target query"
    assert first_row["tertiary_search_route_label"] == "Current anchor review"
    assert "carbonic anhydrase II" in first_row["search_query"]
    assert "direct human CA2-specific assay evidence" in first_row["acceptance_criteria"]

    assert second_row["ligand"] == "acetaminophen"
    assert second_row["primary_search_route_label"] == "Current ChEMBL/PXR anchor"
    assert second_row["primary_search_route_url"] == "https://example.org/pxr-conflict"
    assert "pregnane X receptor" in second_row["search_query"]
    assert "dominate the current proxy conflict" in second_row["acceptance_criteria"]


def test_build_family_evidence_investigator_packet_surfaces_literature_overlay() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "queue_rank": 1,
                    "family": "pxr",
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "priority_tier": "P2_supportive_manual_confirmation",
                    "phase_or_band": "second_pass",
                    "current_policy_bucket": "defer",
                    "claim_impact": "manual_confirmation_needed_before_count_improving",
                    "actionability_bucket": "supportive_manual_confirmation",
                    "state_change_potential": "medium",
                    "evidence_need_class": "target_specific_human_pxr_binder_evidence",
                    "blocking_reason": "activity_present_manual_confirmation_required",
                    "primary_source_title": "PMID 18544536",
                    "primary_source_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                    "stop_condition": "keep deferred if no claim-safe binder evidence",
                    "promotion_if_resolved": "yes",
                }
            ]
        },
        top_n=1,
        pxr_literature_overlay_payload={
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "candidate_status": "high_signal_candidates_present",
                    "candidate_count": 2,
                    "high_signal_candidate_count": 1,
                    "best_candidate_pmid": "18544536",
                    "best_candidate_title": "Rexinoids modulate steroid and xenobiotic receptor activity by increasing its protein turnover in a calpain-dependent manner.",
                    "best_candidate_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                    "best_candidate_signal": "high_signal_human_candidate",
                }
            ]
        },
    )

    summary = payload["summary"]
    assert summary["focus_mode"] == "queue_fallback"
    assert summary["rows_with_literature_candidates"] == 1
    assert summary["rows_with_high_signal_literature_candidates"] == 1
    row = payload["rows"][0]
    assert row["literature_candidate_status"] == "high_signal_candidates_present"
    assert row["best_candidate_pmid"] == "18544536"
    assert row["best_candidate_signal"] == "high_signal_human_candidate"


def test_build_family_evidence_investigator_packet_marks_low_probability_conflict_cleanup_mode() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "queue_rank": 1,
                    "family": "pxr",
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "priority_tier": "P2_supportive_manual_confirmation",
                    "phase_or_band": "second_pass",
                    "current_policy_bucket": "defer",
                    "claim_impact": "manual_confirmation_needed_before_count_improving",
                    "actionability_bucket": "supportive_manual_confirmation",
                    "state_change_potential": "medium",
                    "evidence_need_class": "target_specific_human_pxr_binder_evidence",
                    "blocking_reason": "activity_present_manual_confirmation_required",
                    "primary_source_title": "PMID 18544536",
                    "primary_source_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                    "stop_condition": "keep deferred if no claim-safe binder evidence",
                    "promotion_if_resolved": "yes",
                },
                {
                    "queue_rank": 2,
                    "family": "pxr",
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "priority_tier": "P2_low_probability_conflict_cleanup",
                    "phase_or_band": "same_day_followup",
                    "current_policy_bucket": "confirmed_defer",
                    "claim_impact": "low_probability_count_improving_only_if_orthogonal_human_source_found",
                    "actionability_bucket": "low_probability_conflict_cleanup",
                    "state_change_potential": "low",
                    "conflict_lane": "exact_human_dual_mode_activity_conflict",
                    "evidence_need_class": "target_specific_human_pxr_negative_or_conflict_resolution",
                    "blocking_reason": "activity_proxy_conflicts_with_non_binder",
                    "primary_source_title": "ChEMBL CHEMBL3401 activity query for acetaminophen returned 2 records.",
                    "primary_source_url": "https://example.org/chembl-acetaminophen",
                    "stop_condition": "keep deferred if conflict remains",
                    "promotion_if_resolved": "yes",
                },
                {
                    "queue_rank": 3,
                    "family": "pxr",
                    "packet_step": "core_eval_non_binder_02",
                    "ligand": "caffeine",
                    "priority_tier": "P2_low_probability_conflict_cleanup",
                    "phase_or_band": "same_day_followup",
                    "current_policy_bucket": "confirmed_defer",
                    "claim_impact": "low_probability_count_improving_only_if_orthogonal_human_source_found",
                    "actionability_bucket": "low_probability_conflict_cleanup",
                    "state_change_potential": "low",
                    "conflict_lane": "direct_human_qhts_active_inactive_conflict",
                    "evidence_need_class": "target_specific_human_pxr_negative_or_conflict_resolution",
                    "blocking_reason": "activity_proxy_conflicts_with_non_binder",
                    "primary_source_title": "PubChem CID 2519 human PXR qHTS summary for caffeine.",
                    "primary_source_url": "https://example.org/pubchem-caffeine",
                    "stop_condition": "keep deferred if conflict remains",
                    "promotion_if_resolved": "yes",
                },
            ]
        },
        top_n=2,
    )

    summary = payload["summary"]
    assert summary["focus_mode"] == "low_probability_conflict_cleanup"
    assert summary["focus_row_count"] == 2
    assert summary["count_improving_focus_count"] == 0
    assert summary["low_probability_conflict_focus_count"] == 2
    assert summary["primary_focus_ligand"] == "acetaminophen"
    assert "No true count-improving investigator rows remain" in summary["next_required_step"]

    first_row, second_row = payload["rows"]
    assert first_row["ligand"] == "acetaminophen"
    assert first_row["conflict_lane"] == "exact_human_dual_mode_activity_conflict"
    assert first_row["state_change_potential"] == "low"
    assert "orthogonal exact human NR1I2/PXR evidence" in first_row["acceptance_criteria"]
    assert "human dual-mode antagonist/agonist anchor" in first_row["investigator_note_template"]

    assert second_row["ligand"] == "caffeine"
    assert second_row["conflict_lane"] == "direct_human_qhts_active_inactive_conflict"
    assert second_row["state_change_potential"] == "low"
    assert "exact non-qHTS human NR1I2/PXR evidence" in second_row["acceptance_criteria"]
