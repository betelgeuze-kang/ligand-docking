from __future__ import annotations

from tools.product import build_pxr_quantitative_provenance_packet as mod


def test_build_pxr_quantitative_provenance_packet_tracks_bexarotene_gap() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "capture_status": "captured_supportive",
                    "policy_bucket": "confirmed_defer",
                    "manual_assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                    "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                    "manual_next_required_action": "curate_quantitative_binding_value",
                    "source_note": "Manual review accepted PMID 18544536 but quantitative provenance is still missing.",
                    "source_title": "PMID 18544536",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "search_query": '"bexarotene" AND ("pregnane X receptor" OR PXR OR NR1I2 OR SXR) AND (EC50 OR IC50 OR Ki OR Kd OR potency OR affinity)',
                    "stop_condition": "keep deferred and leave binder fields blank",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "commit_note": "Keep deferred until target-specific human PXR quantitative provenance closes the binder-gap row cleanly.",
                }
            ]
        },
        pubmed_search_ids=lambda query: ["18544536", "14996618"],
        chembl_activity_count=lambda molecule_id, target_id: 0,
        bindingdb_exact_match_count=lambda uniprot, smiles: 0,
        as_of_date="2026-04-19",
        throttle_sec=0.0,
    )

    summary = payload["summary"]
    assert summary["row_count"] == 1
    assert summary["primary_focus_ligand"] == "bexarotene"
    assert summary["quantitative_value_found_count"] == 0
    assert summary["chembl_zero_activity_count"] == 1
    assert summary["bindingdb_exact_gap_count"] == 1
    assert summary["pubmed_trace_ready_count"] == 1

    row = payload["rows"][0]
    assert row["ligand"] == "bexarotene"
    assert row["qualitative_support_pmid"] == "18544536"
    assert row["primary_trace_pmid"] == "10628745"
    assert row["review_trace_pmid"] == "14996618"
    assert row["pubmed_exact_target_hit_count"] == 2
    assert row["pubmed_exact_target_pmids"] == "18544536,14996618"
    assert row["chembl_target_activity_record_count"] == 0
    assert row["bindingdb_exact_smiles_match_count"] == 0
    assert row["quantitative_value_found"] == "no"
    assert "Keep the row deferred" in row["next_required_step"]


def test_build_pxr_quantitative_provenance_packet_marks_value_found_when_database_hit_exists() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "capture_status": "captured_supportive",
                    "policy_bucket": "confirmed_defer",
                    "manual_assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                    "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                }
            ]
        },
        {"rows": [{"packet_step": "ood_fit_binder_01"}]},
        {"rows": [{"packet_step": "ood_fit_binder_01"}]},
        pubmed_search_ids=lambda query: ["18544536"],
        chembl_activity_count=lambda molecule_id, target_id: 1,
        bindingdb_exact_match_count=lambda uniprot, smiles: 0,
        as_of_date="2026-04-19",
        throttle_sec=0.0,
    )

    summary = payload["summary"]
    assert summary["quantitative_value_found_count"] == 1
    row = payload["rows"][0]
    assert row["quantitative_value_found"] == "yes"
    assert "Attach the exact quantitative human PXR source" in row["next_required_step"]


def test_build_pxr_quantitative_provenance_packet_includes_supportive_manual_confirmation_rows() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "capture_status": "captured_supportive",
                    "policy_bucket": "confirmed_defer",
                    "manual_assay_type_honesty": "activity_present_manual_confirmation_required",
                    "manual_promotion_blocker": "activity_present_manual_confirmation_required",
                    "evidence_need_class": "target_specific_human_pxr_binder_evidence",
                    "manual_next_required_action": "manual_curated_search_or_defer",
                    "source_note": "PubChem human PXR qHTS activity proxy exists for bexarotene.",
                }
            ]
        },
        {"rows": [{"packet_step": "ood_fit_binder_01", "search_query": '"bexarotene" AND PXR', "stop_condition": "keep deferred"}]},
        {"rows": [{"packet_step": "ood_fit_binder_01", "commit_note": "keep deferred pending manual confirmation"}]},
        pubmed_search_ids=lambda query: ["18544536", "10628745"],
        chembl_activity_count=lambda molecule_id, target_id: 0,
        bindingdb_exact_match_count=lambda uniprot, smiles: 0,
        as_of_date="2026-04-19",
        throttle_sec=0.0,
    )

    summary = payload["summary"]
    assert summary["row_count"] == 1
    assert summary["supportive_manual_confirmation_gap_count"] == 1
    row = payload["rows"][0]
    assert row["provenance_scope"] == "supportive_manual_confirmation_quantitative_gap"
    assert row["qualitative_support_strength"] == "primary_abstract_human_target_support_nonquantitative"
    assert "weak activators of human SXR/PXR" in row["qualitative_support_note"]
    assert row["quantitative_value_found"] == "no"
