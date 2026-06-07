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


def test_aqp1_operator_validation_candidate_packet_keeps_candidate_fail_closed() -> None:
    payload = mod.build_payload(source_triage=_source_triage())
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
    assert row["operator_claim_safe_decision"] == "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED"
    assert row["operator_replacement_reference_binding_kcal_mol"] == ""
    assert row["claim_promotion_allowed"] is False


def test_aqp1_operator_validation_candidate_packet_cli_writes_outputs(tmp_path: Path) -> None:
    source_json = tmp_path / "source.json"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    source_json.write_text(json.dumps(_source_triage(), indent=2) + "\n", encoding="utf-8")

    mod.main(
        [
            "--source-triage-json",
            str(source_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert out_json.exists()
    assert out_csv.read_text(encoding="utf-8").startswith("candidate_id,")
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Operator Validation Candidate Packet")
