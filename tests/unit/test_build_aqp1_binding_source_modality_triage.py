from pathlib import Path

from tools.product import build_aqp1_binding_source_modality_triage as mod


def test_aqp1_binding_source_modality_triage_blocks_computational_only_kcal() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["evidence_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_aqp1_binding_source_modality_triage"
    assert summary["target_id"] == "AQP1"
    assert summary["candidate_name"] == "bacopaside II"
    assert summary["direct_experimental_binding_row_count"] == 0
    assert summary["claim_safe_binding_kcal_ready_count"] == 0
    assert summary["public_direct_binding_recheck_ready"] is True
    assert summary["public_direct_binding_recheck_source_count"] == 8
    assert "chembl_aqp1_bacopaside_ii_rows=0" in summary["public_direct_binding_recheck_result"]
    assert "bindingdb_p29972_cutoff100_affinities=0" in summary["public_direct_binding_recheck_result"]
    assert "CHEMBL195380_not_CHEMBL390758" in summary["public_direct_binding_recheck_result"]
    assert "chembl20_kd_candidate_delta_g=-5.13_requires_operator_validation" in summary[
        "public_direct_binding_recheck_result"
    ]
    assert summary["public_database_recheck_row_count"] == 3
    assert summary["ligand_identity_mismatch_row_count"] == 1
    assert summary["direct_like_binding_candidate_row_count"] == 1
    assert summary["direct_like_binding_candidate_claim_safe_ready_count"] == 0
    assert summary["chembl_aqp1_direct_like_binding_candidate_chembl_id"] == "CHEMBL20"
    assert summary["chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol"] == "-5.13"
    assert summary["chembl_aqp1_direct_like_binding_candidate_blocker"] == (
        "data_validity_outside_typical_range_and_assay_origin_unknown"
    )
    assert summary["bindingdb_aqp1_expanded_cutoff_affinity_row_count"] == 17
    assert summary["bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count"] == 0
    assert summary["bacopaside_ii_pubchem_cid"] == "9876264"
    assert summary["bacopaside_ii_chembl_id"] == "CHEMBL390758"
    assert summary["aqp1_chembl_target_id"] == "CHEMBL4523210"
    assert summary["aqp1_bindingdb_uniprot_affinity_row_count"] == 0
    assert summary["bacopaside_ii_chembl_aqp1_activity_row_count"] == 0
    assert "CHEMBL195380" in summary["functional_ic50_identity_mismatch_detail"]
    assert summary["replacement_reference_binding_kcal_mol_action"] == (
        "keep_blank_until_direct_binding_or_operator_verified_claim_safe_kcal"
    )
    assert summary["computational_binding_energy_row_count"] == 1
    assert summary["best_computational_binding_energy_kcal_mol"] == "-34.48"
    assert summary["triage_decision"] == (
        "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
    )
    assert rows["aqp1_bacopaside_ii_functional_ic50_pm27474162"][
        "rejection_reason"
    ] == "functional_ic50_surrogate_not_direct_or_claim_safe_binding_kcal"
    assert rows["aqp1_bacopaside_ii_computational_mmgbsa_jmgm_2026"][
        "accepted_for_scope_promotion"
    ] is False
    assert rows["aqp1_bacopaside_ii_chembl_aqp1_absence_current"][
        "rejection_reason"
    ] == "no_chembl_aqp1_activity_or_binding_rows_for_bacopaside_ii"
    assert rows["aqp1_bacopaside_ii_bindingdb_p29972_empty_current"][
        "rejection_reason"
    ] == "bindingdb_has_no_p29972_affinity_rows"
    assert rows["aqp1_functional_ic50_chembl195380_identity_mismatch"][
        "rejection_reason"
    ] == "functional_ic50_row_is_not_bacopaside_ii_identity_mismatch"
    assert rows["aqp1_chembl20_kd_direct_like_operator_validation_candidate"][
        "reference_binding_kcal_mol"
    ] == "-5.13"
    assert rows["aqp1_chembl20_kd_direct_like_operator_validation_candidate"][
        "claim_safe_binding_kcal_ready"
    ] is False


def test_aqp1_binding_source_modality_triage_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "triage.json"
    out_csv = tmp_path / "triage.csv"
    out_md = tmp_path / "triage.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert out_json.exists()
    assert out_csv.read_text(encoding="utf-8").startswith("evidence_id,")
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Binding Source-Modality Triage")
