from __future__ import annotations

from betelgeuze_product.operational_quality import build_product_operational_quality_contract


def test_product_operational_quality_contract_passes_current_fail_closed_surface() -> None:
    payload = build_product_operational_quality_contract()
    summary = payload["summary"]

    assert summary["status"] == "product_operational_quality_contract_ready"
    assert summary["operational_quality_ready"] is True
    assert summary["check_count"] == 6
    assert summary["fail_closed_docking_intake_ready"] is True
    assert summary["production_ai_correction_fail_closed_ready"] is True
    assert summary["production_ai_intake_correction_not_applied_ready"] is True
    assert summary["production_ai_shadow_abstention_ready"] is True
    assert summary["production_ai_guarded_active_ready"] is False
    assert summary["sample_production_ai_inference_subject_active"] is False
    assert summary["sample_production_ai_correction_applied"] is False
    assert summary["sample_production_ai_abstention_enforced"] is True
    assert summary["sample_production_ai_default_residual_mode"] == "shadow"
    assert summary["sample_production_ai_promotion_allowed"] is False
    assert summary["sample_production_ai_customer_facing_auto_correction_allowed"] is False
    assert summary["sample_production_ai_customer_facing_score_mutation_allowed"] is False
    assert summary["sample_production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert summary["sample_production_ai_trained_checkpoint_count"] == 0
    assert summary["sample_production_ai_selected_sidecar_ready"] is False
    assert summary["sample_production_ai_selected_sidecar_missing_output_fields"] == ["delta_force"]
    assert summary["ledger_payload_privacy_ready"] is True
    assert summary["ledger_materialization_hash_only_ready"] is True
    assert summary["ledger_sensitive_key_paths"] == []
    assert summary["request_traceability_ready"] is True
    assert summary["scope_limit_enforcement_ready"] is True
    assert summary["heavy_artifact_policy_ready"] is True
    assert summary["input_payload_persisted"] is False
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False
    assert len(summary["sample_request_sha256"]) == 64
    assert payload["blockers"] == []


def test_product_operational_quality_contract_blocks_if_sample_request_is_invalid() -> None:
    payload = build_product_operational_quality_contract(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "transporter",
            "target_id": "AQP1",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        }
    )

    assert payload["summary"]["status"] == "blocked_product_operational_quality_contract"
    assert payload["summary"]["fail_closed_docking_intake_ready"] is False
    assert payload["summary"]["production_ai_correction_fail_closed_ready"] is True
    assert any(blocker["code"] == "fail_closed_docking_intake_not_ready" for blocker in payload["blockers"])
