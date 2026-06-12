from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_aqp1_direct_binding_procurement_packet as mod


def _triage() -> dict:
    return {
        "summary": {
            "target_id": "AQP1",
            "target_uniprot": "P29972",
            "candidate_name": "bacopaside II",
            "bacopaside_ii_chembl_id": "CHEMBL390758",
            "direct_experimental_binding_row_count": 0,
            "claim_safe_binding_kcal_ready_count": 0,
            "public_direct_binding_recheck_ready": True,
            "public_direct_binding_recheck_result": (
                "no_public_direct_experimental_or_claim_safe_binding_kcal_for_aqp1_bacopaside_ii"
            ),
        }
    }


def _operator_candidate() -> dict:
    return {
        "summary": {
            "packet_ready": True,
            "first_candidate_id": "aqp1_chembl20_direct_like_kd_operator_validation",
            "first_candidate_ligand_external_identifier": "CHEMBL20",
                "first_candidate_ligand_name": "acetazolamide",
                "first_candidate_reference_binding_kcal_mol": "-5.13",
                "first_candidate_blocker": "data_validity_outside_typical_range_and_assay_origin_unknown",
                "first_candidate_raw_activity_verified": True,
                "external_recheck_receipt_ready": True,
                "automated_target_match_confirmed": True,
                "automated_endpoint_binding_like_confirmed": True,
                "automated_bacopaside_absence_confirmed": True,
                "automated_bindingdb_cutoff100_empty_confirmed": True,
                "external_recheck_source_count": 3,
                "external_recheck_present_source_count": 3,
                "automated_data_validity_blocker_present": True,
                "automated_assay_origin_unknown_blocker_present": True,
            },
            "rows": [
                {
                    "candidate_id": "aqp1_chembl20_direct_like_kd_operator_validation",
                    "candidate_ligand_external_identifier": "CHEMBL20",
                "candidate_ligand_name": "acetazolamide",
                "candidate_reference_binding_kcal_mol": "-5.13",
                "candidate_source_locator": (
                    "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
                    "target_chembl_id=CHEMBL4523210&molecule_chembl_id=CHEMBL20"
                    ),
                    "candidate_blocker": "data_validity_outside_typical_range_and_assay_origin_unknown",
                    "candidate_claim_safe_ready": False,
                    "candidate_raw_activity_verified": True,
                    "external_recheck_receipt_ready": True,
                    "automated_target_match_confirmed": True,
                    "automated_endpoint_binding_like_confirmed": True,
                    "automated_bacopaside_absence_confirmed": True,
                    "automated_bindingdb_cutoff100_empty_confirmed": True,
                    "external_recheck_source_count": 3,
                    "external_recheck_present_source_count": 3,
                    "automated_data_validity_blocker_present": True,
                    "automated_assay_origin_unknown_blocker_present": True,
                }
            ],
        }


def test_aqp1_direct_binding_procurement_packet_defines_external_acceptance_contract() -> None:
    payload = mod.build_payload(triage_packet=_triage(), operator_candidate_packet=_operator_candidate())
    summary = payload["summary"]
    rows = {row["action_id"]: row for row in payload["rows"]}

    assert summary["status"] == "aqp1_direct_binding_procurement_packet_ready"
    assert summary["procurement_packet_ready"] is True
    assert summary["target_id"] == "AQP1"
    assert summary["target_uniprot"] == "P29972"
    assert summary["current_direct_experimental_binding_row_count"] == 0
    assert summary["current_claim_safe_binding_kcal_ready_count"] == 0
    assert summary["direct_binding_gap_open"] is True
    assert summary["external_primary_evidence_required"] is True
    assert summary["current_operator_candidate_ligand_external_identifier"] == "CHEMBL20"
    assert summary["current_operator_candidate_reference_binding_kcal_mol"] == "-5.13"
    assert summary["current_operator_candidate_claim_safe_ready"] is False
    assert summary["current_operator_candidate_public_recheck_receipt_ready"] is True
    assert summary["current_operator_candidate_raw_activity_verified"] is True
    assert summary["current_operator_candidate_target_match_confirmed"] is True
    assert summary["current_operator_candidate_endpoint_binding_like_confirmed"] is True
    assert summary["current_operator_candidate_bacopaside_absence_confirmed"] is True
    assert summary["current_operator_candidate_bindingdb_cutoff100_empty_confirmed"] is True
    assert summary["public_database_recheck_receipt_ready"] is True
    assert summary["public_database_recheck_required_source_count"] == 3
    assert summary["public_database_recheck_source_file_count"] == 3
    assert summary["public_absence_claim_supported"] is True
    assert summary["current_operator_candidate_data_validity_blocker_present"] is True
    assert summary["current_operator_candidate_assay_origin_unknown_blocker_present"] is True
    assert "raw_activity_verified=True" in summary["current_operator_candidate_public_recheck_observed"]
    assert "bacopaside_absence=True" in summary["current_operator_candidate_public_recheck_observed"]
    assert "bindingdb_cutoff100_empty=True" in summary["current_operator_candidate_public_recheck_observed"]
    assert "standard_value_nM" in summary["acceptance_fields"]
    assert "operator_claim_safe_decision" in summary["acceptance_fields"]
    assert "target_uniprot=P29972" in summary["minimum_acceptance_rule"]
    assert "standard_type in Kd,Ki" in summary["minimum_acceptance_rule"]
    assert summary["first_required_external_action_id"] == (
        "procure_aqp1_bacopaside_ii_direct_binding_measurement"
    )
    assert summary["claim_promotion_allowed"] is False
    assert summary["authoritative_apply_allowed"] is False
    assert {"code": "direct_binding_gap_open"} in payload["blockers"]

    assert rows["reject_current_chembl20_candidate_for_claim_safe_apply"]["evidence_verdict"] == (
        "keep_blocked"
    )
    assert rows["reject_current_chembl20_candidate_for_claim_safe_apply"][
        "public_recheck_raw_activity_verified"
    ] is True
    assert rows["reject_current_chembl20_candidate_for_claim_safe_apply"][
        "public_recheck_bacopaside_absence_confirmed"
    ] is True
    assert rows["reject_current_chembl20_candidate_for_claim_safe_apply"][
        "public_recheck_bindingdb_cutoff100_empty_confirmed"
    ] is True
    assert rows["reject_current_chembl20_candidate_for_claim_safe_apply"][
        "public_absence_claim_supported"
    ] is True
    assert rows["reject_current_chembl20_candidate_for_claim_safe_apply"][
        "public_recheck_data_validity_blocker_present"
    ] is True
    assert rows["reject_current_chembl20_candidate_for_claim_safe_apply"][
        "public_recheck_assay_origin_unknown_blocker_present"
    ] is True
    assert rows["procure_aqp1_bacopaside_ii_direct_binding_measurement"]["action_type"] == (
        "external_primary_evidence_request"
    )
    assert rows["or_curate_claim_safe_replacement_aqp1_blocker"]["action_type"] == (
        "replacement_reference_evidence_request"
    )


def test_aqp1_direct_binding_procurement_packet_blocks_without_operator_candidate() -> None:
    payload = mod.build_payload(triage_packet=_triage(), operator_candidate_packet={"summary": {}})

    assert payload["summary"]["status"] == "blocked_aqp1_direct_binding_procurement_packet"
    assert payload["summary"]["procurement_packet_ready"] is False
    assert {"code": "operator_candidate_packet_not_ready"} in payload["blockers"]


def test_aqp1_direct_binding_procurement_packet_cli_writes_outputs(tmp_path: Path) -> None:
    triage_json = tmp_path / "triage.json"
    candidate_json = tmp_path / "candidate.json"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    triage_json.write_text(json.dumps(_triage()) + "\n", encoding="utf-8")
    candidate_json.write_text(json.dumps(_operator_candidate()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--triage-json",
            str(triage_json),
            "--operator-candidate-json",
            str(candidate_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["procurement_packet_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("action_id,")
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Direct Binding Procurement Packet")
