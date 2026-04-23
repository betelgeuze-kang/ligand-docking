from __future__ import annotations

from tools import build_aqp1_first_wave_source_confirmation_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_aqp1_first_wave_source_confirmation_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "candidate_name": "bacopaside II",
                "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
            }
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "source_title": "Differential Inhibition of Water and Ion Channel Activities of Mammalian Aquaporin-1",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "evidence_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
                    "review_bucket": "review_only_first_wave",
                },
                {
                    "packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "source_anchor": "PMID 22427546",
                    "source_title": "Stimulation of aquaporin-mediated fluid transport by cyclic GMP",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                    "evidence_signal": "20 uM AqB013 blocked cGMP-stimulated AQP1-dependent fluid flux in human RPE culture",
                    "review_bucket": "review_only_first_wave",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "review_bucket": "defer_pending_target_specific_evidence",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                },
                {
                    "packet_step": "core_binder_02",
                    "review_bucket": "defer_exact_human_activity_nonbinding",
                    "promotion_blocker": "no_claim_safe_aqp1_binding_kcal_curated",
                    "next_required_action": "carry_exact_human_activity_provenance_keep_kcal_blank",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                },
            ]
        },
        {
            "summary": {
                "pubchem_resolved_count": 3,
                "claim_safe_kcal_ready_count": 0,
            },
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "source_title": "Differential Inhibition of Water and Ion Channel Activities of Mammalian Aquaporin-1",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "current_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
                    "assay_type_honesty": "functional_not_direct_binding",
                    "public_provenance_status": "compound_publicly_resolved_target_activity_absent",
                    "public_provenance_signal": "compound_resolved_target_activity_absent",
                    "pubchem_resolved": "yes",
                    "pubchem_cid": "9876264",
                    "chembl_molecule_chembl_id": "CHEMBL390758",
                    "chembl_activity_record_count": 0,
                    "chembl_activity_url": "https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL390758&target_chembl_id=CHEMBL4523210&limit=10",
                    "claim_safe_binding_kcal_ready": "no",
                },
                {
                    "packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "source_anchor": "PMID 22427546",
                    "source_title": "Stimulation of aquaporin-mediated fluid transport by cyclic GMP",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                    "current_signal": "20 uM AqB013 blocked cGMP-stimulated AQP1-dependent fluid flux in human RPE culture",
                    "assay_type_honesty": "functional_not_direct_binding",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                    "pubchem_resolved": "yes",
                    "pubchem_cid": "25026841",
                    "chembl_molecule_chembl_id": "CHEMBL5280895",
                    "chembl_activity_record_count": 1,
                    "chembl_activity_url": "https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL5280895&target_chembl_id=CHEMBL4523210&limit=10",
                    "claim_safe_binding_kcal_ready": "no",
                },
                {
                    "packet_step": "core_binder_03",
                    "candidate_name": "AqB011",
                    "public_provenance_status": "pubchem_resolved_chembl_target_pair_absent",
                    "public_provenance_signal": "pubchem_resolved_target_pair_absent",
                    "chembl_activity_record_count": 0,
                    "claim_safe_binding_kcal_ready": "no",
                },
            ],
        },
    )

    summary = payload["summary"]
    assert summary["row_count"] == 3
    assert summary["primary_focus_ligand"] == "bacopaside II"
    assert summary["exact_human_reference_ligand"] == "AqB013"
    assert summary["exact_pair_absent_count"] == 2
    assert summary["exact_human_activity_reference_count"] == 1
    _contains_tokens(summary["next_required_step"], "bacopaside ii", "aqb013", "replacement_reference_binding_kcal_mol", "blank")

    rows = payload["rows"]
    assert rows[0]["focus_scope"] == "first_wave_primary_exact_source_scope"
    assert rows[0]["review_action"] == "confirm_exact_source_scope_and_keep_review_only"
    _contains_tokens(rows[0]["rejection_gate"], "xenopus", "exact human target activity", "claim-safe kcal")

    assert rows[1]["focus_scope"] == "exact_human_activity_reference_guardrail"
    assert rows[1]["review_action"] == "confirm_exact_human_activity_reference_keep_kcal_blank"
    _contains_tokens(rows[1]["acceptance_gate"], "replacement_reference_binding_kcal_mol", "blank")
