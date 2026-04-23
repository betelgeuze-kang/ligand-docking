from __future__ import annotations

from tools import build_pxr_conflict_resolver_packet as mod


def test_build_pxr_conflict_resolver_packet_focuses_active_conflict_rows() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "priority_rank": 5,
                    "packet_step": "core_eval_non_binder_01",
                    "replacement_ligand_id": "acetaminophen",
                    "policy_bucket": "defer",
                    "capture_status": "captured_conflict",
                    "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "source_title": "ChEMBL CHEMBL3401 activity query for acetaminophen returned 2 records.",
                    "source_url": "https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL112&target_chembl_id=CHEMBL3401&limit=20",
                    "source_note": "Antagonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method (AC50 =23999.9 nM; CHEMBL5291845 / CHEMBL5291721); Agonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method (AC50 >30000.0 nM; CHEMBL5291844 / CHEMBL5291721).",
                },
                {
                    "priority_rank": 6,
                    "packet_step": "core_eval_non_binder_02",
                    "replacement_ligand_id": "caffeine",
                    "policy_bucket": "defer",
                    "capture_status": "captured_conflict",
                    "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "source_title": "PubChem CID 2519 human PXR qHTS summary for caffeine.",
                    "source_url": "https://pubchem.ncbi.nlm.nih.gov/bioassay/1346982",
                    "source_note": "Active plus inactive PubChem rows remain present.",
                },
                {
                    "priority_rank": 8,
                    "packet_step": "ood_eval_non_binder_01",
                    "replacement_ligand_id": "nicotinamide",
                    "policy_bucket": "review_only",
                    "capture_status": "captured_review_only",
                    "manual_promotion_blocker": "inactive_only_human_pxr_qhts_review_only",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_01",
                    "search_query": '"acetaminophen" AND ("pregnane X receptor" OR PXR)',
                    "primary_search_route_label": "Current ChEMBL/PXR anchor",
                    "primary_search_route_url": "https://example.org/acetaminophen-anchor",
                    "secondary_search_route_label": "PubMed exact target query",
                    "secondary_search_route_url": "https://pubmed.ncbi.nlm.nih.gov/?term=acetaminophen+PXR",
                    "acceptance_criteria": "Accept only exact human NR1I2/PXR evidence.",
                    "rejection_criteria": "Reject non-human proxy-only evidence.",
                    "stop_condition": "Keep deferred if the blocker remains.",
                },
                {
                    "packet_step": "core_eval_non_binder_02",
                    "search_query": '"caffeine" AND ("pregnane X receptor" OR PXR)',
                    "primary_search_route_label": "Current ChEMBL/PXR anchor",
                    "primary_search_route_url": "https://example.org/caffeine-anchor",
                    "secondary_search_route_label": "PubMed exact target query",
                    "secondary_search_route_url": "https://pubmed.ncbi.nlm.nih.gov/?term=caffeine+PXR",
                    "acceptance_criteria": "Accept only exact human NR1I2/PXR evidence.",
                    "rejection_criteria": "Reject proxy-only evidence.",
                    "stop_condition": "Keep deferred if the blocker remains.",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_01",
                    "candidate_status": "title_direct_nonhuman_candidates_present",
                    "best_candidate_pmid": "41034397",
                    "best_candidate_title": "Acetaminophen activates PXR in mice.",
                    "best_candidate_url": "https://pubmed.ncbi.nlm.nih.gov/41034397/",
                    "best_candidate_signal": "title_direct_nonhuman_candidate",
                }
            ]
        },
    )

    summary = payload["summary"]
    assert summary["row_count"] == 2
    assert summary["primary_focus_ligand"] == "acetaminophen"
    assert summary["pubchem_conflict_count"] == 1
    assert summary["title_direct_nonhuman_conflict_count"] == 1
    assert summary["exact_human_dual_mode_conflict_count"] == 1
    assert summary["direct_human_qhts_conflict_count"] == 1
    assert summary["weak_human_nonhuman_boundary_conflict_count"] == 0
    assert summary["nonhuman_boundary_context_count"] == 1
    assert summary["medium_state_change_potential_count"] == 0
    assert summary["low_state_change_potential_count"] == 2
    assert summary["search_ready_count"] == 2

    first_row, second_row = payload["rows"]
    assert first_row["ligand"] == "acetaminophen"
    assert first_row["conflict_lane"] == "exact_human_dual_mode_activity_conflict"
    assert first_row["state_change_potential"] == "low"
    assert first_row["nonhuman_boundary_context"] == "yes"
    assert first_row["recommended_resolution"] == "keep_deferred_exact_human_dual_mode_conflict"
    assert second_row["ligand"] == "caffeine"
    assert second_row["conflict_lane"] == "direct_human_qhts_active_inactive_conflict"
    assert second_row["state_change_potential"] == "low"
    assert second_row["nonhuman_boundary_context"] == "no"
    assert second_row["recommended_resolution"] == "keep_deferred_direct_human_qhts_conflict"
