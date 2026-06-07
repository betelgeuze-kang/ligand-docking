from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_p0_evidence_acquisition_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _row(step: str, binder: str, ready: bool = False) -> dict[str, str]:
    return {
        "packet_step": step,
        "current_ligand_id": f"placeholder_{step}",
        "replacement_ligand_id": f"replacement_{step}" if binder == "1" else "",
        "replacement_is_binder": binder,
        "replacement_role": "far_ood_eval",
        "replacement_source": "source" if binder == "1" else "",
        "row_ready_for_apply": "yes" if ready else "no",
        "required_missing_fields": "" if ready else "replacement_reference_binding_kcal_mol",
    }


def _workbook(rows: list[dict[str, str]]) -> dict[str, object]:
    return {"workbook_rows": rows}


def test_transporter_p0_evidence_acquisition_packet_splits_unresolved_slots() -> None:
    aqp1_rows = [
        _row("core_binder_01", "1"),
        _row("core_binder_02", "1"),
        _row("core_binder_03", "1"),
        _row("core_non_binder_01", "0"),
        _row("core_non_binder_02", "0"),
        _row("core_non_binder_03", "0"),
    ]
    glut1_rows = [
        _row("core_binder_01", "1", ready=True),
        _row("core_binder_02", "1"),
        _row("core_binder_03", "1"),
        _row("core_non_binder_01", "0"),
        _row("core_non_binder_02", "0"),
        _row("core_non_binder_03", "0"),
    ]

    payload = mod.build_payload(
        closure_payload={"summary": {"closure_row_count": 6, "current_membrane_p0_open_count": 6}},
        aqp1_workbook_payload=_workbook(aqp1_rows),
        aqp1_negative_payload={"summary": {"negative_slot_cover_ready_count": 3}},
        aqp1_negative_intake_payload={
            "summary": {
                "review_ready_row_count": 3,
                "authoritative_negative_apply_allowed_count": 0,
                "negative_evidence_closure_allowed": False,
            }
        },
        aqp1_negative_slot_closure_payload={"summary": {"authoritative_negative_apply_allowed": False}},
        aqp1_binding_source_modality_triage_payload={
            "summary": {
                "status": "blocked_aqp1_binding_source_modality_triage",
                "source_modality_guard_ready": True,
                "triage_artifact": "runs/aqp1_binding_source_modality_triage_current.json",
                "triage_decision": (
                    "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                ),
                "direct_experimental_binding_row_count": 0,
                "claim_safe_binding_kcal_ready_count": 0,
                "public_direct_binding_recheck_ready": True,
                "public_direct_binding_recheck_source_count": 6,
                "public_direct_binding_recheck_result": (
                    "no_public_direct_experimental_or_claim_safe_binding_kcal_for_aqp1_bacopaside_ii;"
                    "chembl_aqp1_bacopaside_ii_rows=0;bindingdb_p29972_affinities=0;"
                    "functional_ic50_identity_mismatch=CHEMBL195380_not_CHEMBL390758"
                ),
                "public_database_recheck_row_count": 2,
                "ligand_identity_mismatch_row_count": 1,
                "bacopaside_ii_pubchem_cid": "9876264",
                "bacopaside_ii_chembl_id": "CHEMBL390758",
                "aqp1_chembl_target_id": "CHEMBL4523210",
                "aqp1_bindingdb_uniprot_affinity_row_count": 0,
                "bacopaside_ii_chembl_aqp1_activity_row_count": 0,
                "functional_ic50_identity_mismatch_detail": (
                    "AQP1 functional IC50 2700 nM row is CHEMBL195380, while bacopaside II is CHEMBL390758."
                ),
                "replacement_reference_binding_kcal_mol_action": (
                    "keep_blank_until_direct_binding_or_operator_verified_claim_safe_kcal"
                ),
                "computational_binding_energy_row_count": 1,
                "best_computational_binding_energy_kcal_mol": "-34.48",
                "best_functional_delta_g_surrogate_kcal_mol": "-6.47",
                "next_required_step": "Keep AQP1.core_binder_01 blocked.",
            }
        },
        glut1_workbook_payload=_workbook(glut1_rows),
        glut1_second_wave_payload={
            "rows": [
                {"packet_step": "core_binder_02", "public_provenance_signal": "apparent_functional_affinity_present_leave_direct_binding_kcal_blank"}
            ]
        },
        glut1_claim_safe_payload={"rows": [{"packet_step": "core_binder_01", "ready": "yes"}]},
    )

    summary = payload["summary"]
    assert summary["unresolved_slot_count"] == 11
    assert summary["binder_unresolved_slot_count"] == 5
    assert summary["negative_unresolved_slot_count"] == 6
    assert summary["negative_sync_slot_count"] == 0
    assert summary["exact_evidence_request_slot_count"] == 11
    assert summary["aqp1_negative_review_ready"] is True
    assert summary["aqp1_negative_authoritative_ready"] is False
    assert summary["scope_promotion_allowed"] is False
    assert summary["next_slot_completion_packet_ready"] is True
    assert summary["next_evidence_slot_id"] == "AQP1.core_binder_01"
    assert summary["next_evidence_slot_target_id"] == "AQP1"
    assert summary["next_evidence_slot_packet_step"] == "core_binder_01"
    assert summary["next_evidence_slot_candidate_ligand_id"] == "replacement_core_binder_01"
    assert summary["next_evidence_slot_request_mode"] == "exact_target_pair_quantitative_binder_kcal_required"
    assert summary["next_evidence_slot_source_signal"] == "source"
    assert summary["next_evidence_slot_required_missing_fields"] == "replacement_reference_binding_kcal_mol"
    assert summary["next_slot_source_modality_guard_ready"] is True
    assert summary["next_slot_source_modality"] == "functional_quantitative_surrogate"
    assert summary["next_slot_source_modality_claim_safe"] is False
    assert summary["next_slot_source_modality_direct_binding_claim_allowed"] is False
    assert summary["next_slot_source_modality_decision"] == (
        "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
    )
    assert "scope_promotion_allowed_false_until_source_modality_upgrade" in summary[
        "next_slot_source_modality_guardrails"
    ]
    assert "missing_fields=replacement_reference_binding_kcal_mol" in summary[
        "next_slot_source_modality_observed_signal"
    ]
    assert "exact target-pair direct/claim-safe binding kcal/mol" in summary[
        "next_slot_source_modality_required_upgrade"
    ]
    assert summary["aqp1_binding_source_modality_triage_ready"] is True
    assert summary["aqp1_binding_source_modality_triage_artifact"] == (
        "runs/aqp1_binding_source_modality_triage_current.json"
    )
    assert summary["aqp1_binding_source_modality_triage_decision"] == (
        "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
    )
    assert summary["aqp1_binding_source_modality_direct_experimental_binding_row_count"] == 0
    assert summary["aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count"] == 0
    assert summary["aqp1_binding_source_modality_public_direct_binding_recheck_ready"] is True
    assert summary["aqp1_binding_source_modality_public_direct_binding_recheck_source_count"] == 6
    assert "chembl_aqp1_bacopaside_ii_rows=0" in summary[
        "aqp1_binding_source_modality_public_direct_binding_recheck_result"
    ]
    assert summary["aqp1_binding_source_modality_public_database_recheck_row_count"] == 2
    assert summary["aqp1_binding_source_modality_ligand_identity_mismatch_row_count"] == 1
    assert summary["aqp1_binding_source_modality_bacopaside_ii_pubchem_cid"] == "9876264"
    assert summary["aqp1_binding_source_modality_bacopaside_ii_chembl_id"] == "CHEMBL390758"
    assert summary["aqp1_binding_source_modality_aqp1_chembl_target_id"] == "CHEMBL4523210"
    assert summary["aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"] == 0
    assert summary["aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"] == 0
    assert "CHEMBL195380" in summary[
        "aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail"
    ]
    assert summary["aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action"] == (
        "keep_blank_until_direct_binding_or_operator_verified_claim_safe_kcal"
    )
    assert summary["aqp1_binding_source_modality_computational_binding_energy_row_count"] == 1
    assert summary["aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol"] == "-34.48"
    assert summary["next_slot_return_bundle_required_artifact_count"] == 5
    assert summary["next_slot_return_bundle_blocker_count"] == 5
    assert summary["next_slot_return_bundle_next_artifact_id"] == "operator_review_row"
    assert summary["next_slot_return_bundle_next_artifact_path"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert summary["next_slot_return_bundle_next_artifact_failed_check_ids"] == [
        "next_slot_required_missing_fields",
        "operator_review_row_not_operator_verified",
    ]
    next_packet = payload["next_slot_completion_packet"]
    assert next_packet["slot_id"] == "AQP1.core_binder_01"
    assert next_packet["completion_contract_version"] == "transporter_next_slot_exact_evidence_v2"
    assert next_packet["expected_evidence_type"] == "direct_or_claim_safe_binding_kcal"
    assert next_packet["next_slot_source_modality_guard_ready"] is True
    assert next_packet["next_slot_source_modality"] == "functional_quantitative_surrogate"
    assert next_packet["next_slot_source_modality_direct_binding_claim_allowed"] is False
    assert next_packet["required_exact_evidence_field_count"] == 19
    assert "target_uniprot_accession" in next_packet["required_exact_evidence_fields"]
    assert "evidence_sentence_or_table_locator" in next_packet["required_exact_evidence_fields"]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in next_packet["required_claim_guardrails"]
    assert "config/ligand_binding_reference_blind_aqp1_v1.csv" in next_packet["post_intake_synchronization_targets"]
    assert next_packet["return_bundle_required_artifact_count"] == 5
    assert "runs/transporter_binder_promotion_gate_current.json" in next_packet["return_bundle_required_artifacts"]
    assert next_packet["required_operator_intake_columns"] == [
        "target_id",
        "candidate_ligand_id",
        "reference_binding_kcal_mol",
        "source_url_or_doi",
        "smiles",
        "scaffold",
        "evidence_type",
    ]
    assert any(
        "build_product_scope_breadth_contract.py" in command
        for command in next_packet["validation_commands"]
    )
    assert next_packet["acceptance_gate_commands"] == next_packet["validation_commands"]
    matrix = payload["next_slot_return_bundle_completion_matrix"]
    assert len(matrix) == 5
    assert matrix[0]["artifact_id"] == "operator_review_row"
    assert matrix[0]["status"] == "blocked"
    assert matrix[0]["slot_id"] == "AQP1.core_binder_01"
    assert "reference_binding_kcal_mol" in matrix[0]["required_fields_or_columns"]
    assert "next_slot_required_missing_fields" in matrix[0]["failed_check_ids"]
    assert matrix[-1]["artifact_id"] == "transporter_promotion_gate"
    modes = {row["packet_step"]: row["request_mode"] for row in payload["rows"] if row["target_id"] == "GLUT1_4PYP"}
    assert modes["core_binder_02"] == "direct_binding_kcal_or_keep_functional_review_only_required"


def test_transporter_p0_evidence_acquisition_packet_allows_negative_sync_only_after_authoritative_gate() -> None:
    payload = mod.build_payload(
        closure_payload={"summary": {"closure_row_count": 3, "current_membrane_p0_open_count": 3}},
        aqp1_workbook_payload=_workbook(
            [
                _row("core_non_binder_01", "0"),
                _row("core_non_binder_02", "0"),
                _row("core_non_binder_03", "0"),
            ]
        ),
        aqp1_negative_payload={"summary": {"negative_slot_cover_ready_count": 3}},
        aqp1_negative_intake_payload={
            "summary": {
                "review_ready_row_count": 3,
                "authoritative_negative_apply_allowed_count": 3,
                "negative_evidence_closure_allowed": True,
            }
        },
        aqp1_negative_slot_closure_payload={"summary": {"authoritative_negative_apply_allowed": True}},
        glut1_workbook_payload=_workbook([]),
        glut1_second_wave_payload={"rows": []},
        glut1_claim_safe_payload={"rows": []},
    )

    assert payload["summary"]["aqp1_negative_authoritative_ready"] is True
    assert payload["summary"]["negative_sync_slot_count"] == 3
    assert {row["request_mode"] for row in payload["rows"]} == {"sync_exact_negative_evidence_into_workbook_required"}


def test_transporter_p0_evidence_acquisition_packet_cli_writes_outputs(tmp_path: Path) -> None:
    closure = tmp_path / "closure.json"
    aqp1 = tmp_path / "aqp1.json"
    aqp1_negative = tmp_path / "aqp1_negative.json"
    aqp1_negative_intake = tmp_path / "aqp1_negative_intake.json"
    aqp1_negative_slot_closure = tmp_path / "aqp1_negative_slot_closure.json"
    glut1 = tmp_path / "glut1.json"
    second_wave = tmp_path / "second_wave.json"
    claim_safe = tmp_path / "claim_safe.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    closure.write_text(json.dumps({"summary": {"closure_row_count": 1}}), encoding="utf-8")
    aqp1.write_text(json.dumps(_workbook([_row("core_binder_01", "1")])), encoding="utf-8")
    aqp1_negative.write_text(json.dumps({"summary": {"negative_slot_cover_ready_count": 0}}), encoding="utf-8")
    aqp1_negative_intake.write_text(json.dumps({"summary": {}}), encoding="utf-8")
    aqp1_negative_slot_closure.write_text(json.dumps({"summary": {}}), encoding="utf-8")
    glut1.write_text(json.dumps(_workbook([_row("core_binder_01", "1", ready=True), _row("core_binder_02", "1")])), encoding="utf-8")
    second_wave.write_text(json.dumps({"rows": []}), encoding="utf-8")
    claim_safe.write_text(json.dumps({"rows": [{"packet_step": "core_binder_01", "ready": "yes"}]}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_p0_evidence_acquisition_packet.py",
            "--closure-json",
            str(closure),
            "--aqp1-workbook-json",
            str(aqp1),
            "--aqp1-negative-json",
            str(aqp1_negative),
            "--aqp1-negative-intake-json",
            str(aqp1_negative_intake),
            "--aqp1-negative-slot-closure-json",
            str(aqp1_negative_slot_closure),
            "--glut1-workbook-json",
            str(glut1),
            "--glut1-second-wave-json",
            str(second_wave),
            "--glut1-claim-safe-json",
            str(claim_safe),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["unresolved_slot_count"] == 2
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["next_slot_return_bundle_required_artifact_count"] == 5
    assert "Transporter P0 Evidence Acquisition Packet" in out_md.read_text(encoding="utf-8")
    assert "Next Slot Return Bundle" in out_md.read_text(encoding="utf-8")
    assert "target_id" in out_csv.read_text(encoding="utf-8")
