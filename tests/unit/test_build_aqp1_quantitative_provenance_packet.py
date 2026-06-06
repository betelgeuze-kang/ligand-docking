from __future__ import annotations

from tools.product import build_aqp1_quantitative_provenance_packet as mod


def test_build_aqp1_quantitative_provenance_packet_surfaces_exact_human_activity() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "priority_rank": 1,
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "source_title": "Bacopaside paper",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "current_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
                    "capture_status": "captured_review_only_gap",
                    "assay_type_honesty": "functional_not_direct_binding",
                },
                {
                    "priority_rank": 2,
                    "packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "source_anchor": "PMID 22427546",
                    "source_title": "AqB013 paper",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                    "current_signal": "20 uM AqB013 blocked cGMP-stimulated AQP1-dependent fluid flux",
                    "capture_status": "captured_review_only_gap",
                    "assay_type_honesty": "functional_not_direct_binding",
                },
                {
                    "priority_rank": 3,
                    "packet_step": "core_binder_03",
                    "candidate_name": "AqB011",
                    "source_anchor": "PMID 26467039",
                    "source_title": "AqB011 paper",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/26467039/",
                    "current_signal": "AqB011 blocked AQP1 ion conductance with IC50 14 uM",
                    "capture_status": "captured_review_only_gap",
                    "assay_type_honesty": "functional_not_direct_binding",
                },
            ]
        },
        pubchem_lookup=lambda query_name: {
            "bacopaside II": {
                "query_name": query_name,
                "resolved": True,
                "pubchem_cid": "9876264",
                "canonical_smiles": "BACO",
                "resolution_url": "https://pubchem/bacopaside",
            },
            "AqB013": {
                "query_name": query_name,
                "resolved": True,
                "pubchem_cid": "25026841",
                "canonical_smiles": "AQB013",
                "resolution_url": "https://pubchem/aqb013",
            },
            "AqB011": {
                "query_name": query_name,
                "resolved": True,
                "pubchem_cid": "25026839",
                "canonical_smiles": "AQB011",
                "resolution_url": "https://pubchem/aqb011",
            },
        }[query_name],
        chembl_molecule_lookup=lambda query_name, preferred_id: {
            "bacopaside II": {
                "query_name": query_name,
                "search_result_count": 5,
                "exact_match_count": 1,
                "molecule_chembl_id": "CHEMBL390758",
                "canonical_smiles": "BACO",
                "match_url": "https://chembl/baco",
            },
            "AqB013": {
                "query_name": query_name,
                "search_result_count": 1,
                "exact_match_count": 1,
                "molecule_chembl_id": "CHEMBL5280895",
                "canonical_smiles": "AQB013",
                "match_url": "https://chembl/aqb013",
            },
            "3-(Butylamino)-4-phenoxy-N-(pyridin-3-ylmethyl)-5-sulfamoylbenzamide": {
                "query_name": query_name,
                "search_result_count": 5,
                "exact_match_count": 0,
                "molecule_chembl_id": "",
                "canonical_smiles": "",
                "match_url": "https://chembl/aqb011",
            },
        }[query_name],
        chembl_activity_lookup=lambda molecule_chembl_id, target_chembl_id: (
            {
                "activity_url": "https://chembl/activity/aqb013",
                "activity_count": 1,
                "activities": [
                    {
                        "standard_type": "IC50",
                        "standard_relation": "=",
                        "standard_value": "20000.0",
                        "standard_units": "nM",
                        "assay_type": "B",
                        "assay_description": "Inhibition of human AQP1 water channel expressed in Xenopus laevis oocytes",
                    }
                ],
            }
            if molecule_chembl_id == "CHEMBL5280895"
            else {"activity_url": "https://chembl/activity/none", "activity_count": 0, "activities": []}
        ),
        as_of_date="2026-04-19",
        throttle_sec=0.0,
    )

    summary = payload["summary"]
    assert summary["row_count"] == 3
    assert summary["pubchem_resolved_count"] == 3
    assert summary["chembl_exact_match_count"] == 2
    assert summary["exact_human_aqp1_activity_count"] == 1
    assert summary["primary_focus_ligand"] == "AqB013"
    assert summary["signal"] == "exact_human_activity_present_leave_kcal_blank"

    rows = {row["candidate_name"]: row for row in payload["rows"]}
    assert rows["bacopaside II"]["public_provenance_status"] == "compound_publicly_resolved_target_activity_absent"
    assert rows["bacopaside II"]["chembl_activity_record_count"] == 0
    assert rows["AqB013"]["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
    assert rows["AqB013"]["chembl_best_activity_type"] == "IC50"
    assert rows["AqB013"]["chembl_best_activity_value"] == "20000.0"
    assert rows["AqB011"]["public_provenance_status"] == "pubchem_resolved_chembl_target_pair_absent"
    assert rows["AqB011"]["chembl_exact_match_count"] == 0
