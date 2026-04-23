from tools import build_aqp1_quantitative_binding_capture_intake as mod


def test_build_aqp1_quantitative_binding_capture_intake_without_supportive_rows() -> None:
    rows = [
        {
            "packet_step": "core_binder_01",
            "candidate_name": "bacopaside II",
            "source_title": "Bacopaside paper",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
            "supports_direct_quantitative_binding": "no",
            "capture_status": "captured_review_only_gap",
            "quantitative_measure_value": "18",
            "replacement_reference_binding_kcal_mol": "",
        }
    ]

    updates_payload = mod._build_updates_payload(rows)
    payload = mod.build_payload(rows, updates_payload)

    assert updates_payload["summary"]["update_row_count"] == 0
    assert payload["summary"]["captured_review_only_gap_count"] == 1
    assert payload["summary"]["supportive_direct_quantitative_binding_count"] == 0
    assert payload["summary"]["intake_applied"] is True


def test_build_aqp1_quantitative_binding_capture_intake_collects_supportive_rows() -> None:
    rows = [
        {
            "packet_step": "core_binder_01",
            "candidate_name": "bacopaside II",
            "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
            "source_anchor": "PMID 27474162",
            "source_title": "Bacopaside paper",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
            "assay_type_honesty": "direct_binding_human_target",
            "supports_direct_quantitative_binding": "yes",
            "capture_status": "captured_supportive",
            "quantitative_measure_kind": "Kd",
            "quantitative_measure_value": "120",
            "quantitative_measure_units": "nM",
            "replacement_reference_binding_kcal_mol": "-9.4",
        }
    ]

    updates_payload = mod._build_updates_payload(rows)
    payload = mod.build_payload(rows, updates_payload)

    assert updates_payload["summary"]["update_row_count"] == 1
    assert updates_payload["rows"][0]["replacement_reference_binding_kcal_mol"] == "-9.4"
    assert payload["summary"]["supportive_direct_quantitative_binding_count"] == 1
    assert payload["summary"]["kcal_overlay_ready_count"] == 1
