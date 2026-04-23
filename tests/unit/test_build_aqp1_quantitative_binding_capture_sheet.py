from tools import build_aqp1_quantitative_binding_capture_sheet as mod


def test_build_aqp1_quantitative_binding_capture_sheet_defaults_to_review_only_gap() -> None:
    external_seed_payload = {
        "rows": [
            {
                "priority_rank": 1,
                "candidate_name": "bacopaside II",
                "proposed_packet_step": "core_binder_01",
                "evidence_class": "functional_aqp1_water_channel_inhibitor",
                "evidence_strength": "moderate_functional",
                "source_anchor": "PMID 27474162",
                "source_title": "Bacopaside paper",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                "potency_or_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
            },
            {
                "priority_rank": 2,
                "candidate_name": "AqB013",
                "proposed_packet_step": "core_binder_02",
                "evidence_class": "functional_aqp1_antagonist_tool",
                "evidence_strength": "moderate_functional",
                "source_anchor": "PMID 22427546",
                "source_title": "AqB013 paper",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                "potency_or_signal": "20 uM AqB013 blocked cGMP-stimulated flux",
            },
        ]
    }
    workbook_payload = {
        "workbook_rows": [
            {
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "replacement_reference_binding_kcal_mol": "",
                "replacement_source": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
            },
            {
                "packet_step": "core_binder_02",
                "replacement_ligand_id": "AqB013",
                "replacement_reference_binding_kcal_mol": "",
                "replacement_source": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
            },
        ]
    }

    payload = mod.build_payload(external_seed_payload, workbook_payload)

    assert payload["summary"]["binder_row_count"] == 2
    assert payload["summary"]["supportive_direct_quantitative_binding_count"] == 0
    assert payload["summary"]["captured_review_only_gap_count"] == 2
    row = payload["rows"][0]
    assert row["supports_direct_quantitative_binding"] == "no"
    assert row["capture_status"] == "captured_review_only_gap"
    assert row["quantitative_measure_kind"] == "IC50"
    assert row["quantitative_measure_value"] == "18"
    assert row["quantitative_measure_units"] == "uM"


def test_build_aqp1_quantitative_binding_capture_sheet_preserves_existing_manual_fields() -> None:
    external_seed_payload = {
        "rows": [
            {
                "priority_rank": 1,
                "candidate_name": "bacopaside II",
                "proposed_packet_step": "core_binder_01",
                "source_anchor": "PMID 27474162",
                "source_title": "Bacopaside paper",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                "potency_or_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
            }
        ]
    }
    workbook_payload = {"workbook_rows": [{"packet_step": "core_binder_01", "replacement_ligand_id": "seed"}]}
    existing_sheet = {
        "core_binder_01": {
            "supports_direct_quantitative_binding": "yes",
            "capture_status": "captured_supportive",
            "replacement_reference_binding_kcal_mol": "-8.4",
        }
    }

    payload = mod.build_payload(external_seed_payload, workbook_payload, existing_sheet=existing_sheet)

    row = payload["rows"][0]
    assert row["supports_direct_quantitative_binding"] == "yes"
    assert row["capture_status"] == "captured_supportive"
    assert row["replacement_reference_binding_kcal_mol"] == "-8.4"
