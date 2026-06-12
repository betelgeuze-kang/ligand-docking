import json
from pathlib import Path

from tools.product import build_aqp1_operator_validation_candidate_packet as mod


def _source_triage() -> dict:
    return {
        "summary": {
            "aqp1_chembl_target_id": "CHEMBL4523210",
            "direct_like_binding_candidate_claim_safe_ready_count": 0,
            "chembl_aqp1_direct_like_binding_candidate_chembl_id": "CHEMBL20",
            "chembl_aqp1_direct_like_binding_candidate_name": "acetazolamide",
            "chembl_aqp1_direct_like_binding_candidate_activity_id": "29308926",
            "chembl_aqp1_direct_like_binding_candidate_standard_type": "Kd",
            "chembl_aqp1_direct_like_binding_candidate_standard_value_nM": "174000.0",
            "chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": "-5.13",
            "chembl_aqp1_direct_like_binding_candidate_blocker": (
                "data_validity_outside_typical_range_and_assay_origin_unknown"
            ),
        }
    }


def _write_recheck_sources(base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / "chembl_aqp1_chembl20_activity.json").write_text(
        json.dumps(
            {
                "activities": [
                    {
                        "activity_id": 29308926,
                        "assay_chembl_id": "CHEMBL6183208",
                        "assay_description": (
                            "Binding affinity to AQP1 (unknown origin) expressed in HEK cells "
                            "assessed as dissociation constant"
                        ),
                        "assay_type": "B",
                        "bao_endpoint": "BAO_0000034",
                        "bao_label": "cell-based format",
                        "canonical_smiles": "SHOULD_NOT_APPEAR_IN_PACKET",
                        "data_validity_comment": "Outside typical range",
                        "data_validity_description": (
                            "Values for this activity type are unusually large/small, so may not be accurate"
                        ),
                        "document_chembl_id": "CHEMBL6182835",
                        "document_journal": "RSC Med Chem",
                        "document_year": 2025,
                        "molecule_chembl_id": "CHEMBL20",
                        "molecule_pref_name": "ACETAZOLAMIDE",
                        "standard_type": "Kd",
                        "standard_units": "nM",
                        "standard_value": "174000.0",
                        "target_chembl_id": "CHEMBL4523210",
                        "target_organism": "Homo sapiens",
                        "target_pref_name": "Aquaporin-1",
                    }
                ],
                "page_meta": {"total_count": 1},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (base / "chembl_aqp1_bacopaside_ii_activity.json").write_text(
        json.dumps({"activities": [], "page_meta": {"total_count": 0}}, indent=2) + "\n",
        encoding="utf-8",
    )
    (base / "bindingdb_p29972_cutoff100.json").write_text(
        json.dumps({"getLindsByUniprotsResponse": {"affinities": []}}, indent=2) + "\n",
        encoding="utf-8",
    )


def test_aqp1_operator_validation_candidate_packet_keeps_candidate_fail_closed(tmp_path: Path) -> None:
    payload = mod.build_payload(source_triage=_source_triage(), recheck_sources_dir=tmp_path / "missing")
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "aqp1_operator_validation_candidate_packet_ready"
    assert summary["packet_ready"] is True
    assert summary["candidate_ready"] is True
    assert summary["candidate_count"] == 1
    assert summary["candidate_claim_safe_ready_count"] == 0
    assert summary["operator_validation_required_count"] == 1
    assert summary["operator_placeholder_count"] == 6
    assert summary["first_candidate_ligand_external_identifier"] == "CHEMBL20"
    assert summary["first_candidate_ligand_name"] == "acetazolamide"
    assert summary["first_candidate_reference_binding_kcal_mol"] == "-5.13"
    assert summary["first_candidate_claim_safe_ready"] is False
    assert summary["external_recheck_receipt_ready"] is False
    assert summary["first_candidate_raw_activity_verified"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["authoritative_apply_allowed"] is False
    assert "operator_assay_origin_confirmed" in summary["required_operator_decision_fields"]
    assert "data_validity_outside_typical_range" in summary["validation_blockers"]
    assert any(
        "build_product_scope_breadth_contract.py" in command
        for command in summary["post_return_validation_commands"]
    )

    assert row["candidate_activity_id"] == "29308926"
    assert row["candidate_standard_type"] == "Kd"
    assert row["candidate_standard_value_nM"] == "174000.0"
    assert row["candidate_claim_safe_ready"] is False
    assert row["candidate_raw_activity_verified"] is False
    assert row["operator_claim_safe_decision"] == "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED"
    assert row["operator_replacement_reference_binding_kcal_mol"] == ""
    assert row["claim_promotion_allowed"] is False


def test_aqp1_operator_validation_candidate_packet_records_public_recheck_fail_closed(tmp_path: Path) -> None:
    recheck_dir = tmp_path / "recheck"
    _write_recheck_sources(recheck_dir)

    payload = mod.build_payload(source_triage=_source_triage(), recheck_sources_dir=recheck_dir)
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["external_recheck_receipt_ready"] is True
    assert summary["external_recheck_source_count"] == 3
    assert summary["external_recheck_present_source_count"] == 3
    assert summary["first_candidate_raw_activity_verified"] is True
    assert summary["automated_target_match_confirmed"] is True
    assert summary["automated_endpoint_binding_like_confirmed"] is True
    assert summary["automated_bacopaside_absence_confirmed"] is True
    assert summary["automated_bindingdb_cutoff100_empty_confirmed"] is True
    assert summary["automated_data_validity_blocker_present"] is True
    assert summary["automated_assay_origin_unknown_blocker_present"] is True
    assert summary["candidate_claim_safe_ready_count"] == 0
    assert summary["claim_promotion_allowed"] is False
    assert summary["authoritative_apply_allowed"] is False

    assert row["candidate_raw_activity_id"] == "29308926"
    assert row["candidate_raw_activity_verified"] is True
    assert row["candidate_raw_assay_chembl_id"] == "CHEMBL6183208"
    assert row["candidate_raw_data_validity_auto_blocker"] is True
    assert row["candidate_raw_assay_origin_unknown_auto_blocker"] is True
    assert row["bacopaside_ii_raw_activity_count"] == 0
    assert row["bindingdb_p29972_cutoff100_affinity_count"] == 0
    assert "canonical_smiles" not in row
    assert "SHOULD_NOT_APPEAR_IN_PACKET" not in json.dumps(payload)


def test_aqp1_operator_validation_candidate_packet_cli_writes_outputs(tmp_path: Path) -> None:
    source_json = tmp_path / "source.json"
    recheck_dir = tmp_path / "recheck"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    source_json.write_text(json.dumps(_source_triage(), indent=2) + "\n", encoding="utf-8")
    _write_recheck_sources(recheck_dir)

    mod.main(
        [
            "--source-triage-json",
            str(source_json),
            "--recheck-sources-dir",
            str(recheck_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert out_json.exists()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["external_recheck_receipt_ready"] is True
    assert payload["summary"]["first_candidate_raw_activity_verified"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("candidate_id,")
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Operator Validation Candidate Packet")
    assert "SHOULD_NOT_APPEAR_IN_PACKET" not in out_csv.read_text(encoding="utf-8")
    assert "SHOULD_NOT_APPEAR_IN_PACKET" not in out_md.read_text(encoding="utf-8")
