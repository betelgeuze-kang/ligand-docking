from __future__ import annotations

from tools.product import build_engine_refinement_tier_readiness as mod


def test_build_engine_refinement_tier_readiness_passes_on_repo_defaults() -> None:
    payload = mod.build_engine_refinement_tier_readiness()
    summary = payload["summary"]
    assert summary["engine_refinement_tier_ready"] is True
    assert summary["status"] == "engine_refinement_tier_ready"
    assert summary["refined_energy_col"] == "deltaG_mm_gbsa_kcal_mol"
    assert summary["atom_typing_coverage_surface_ready"] is True
    assert summary["unsupported_metal_fail_closed_surface_ready"] is True
    assert summary["metal_cofactor_coordination_claim_guard_ready"] is True
    assert summary["charged_residue_atom_typing_surface_ready"] is True
    assert summary["formal_charge_proxy_claim_guard_ready"] is True
    assert summary["solvent_fep_calibration_claim_guard_ready"] is True
    assert summary["structure_quality_interface_claim_guard_ready"] is True
    assert summary["parameter_calibration_claim_guard_ready"] is True
    assert summary["benchmark_metric_surface_ready"] is True
    assert summary["free_energy_calibration_claim_guard_ready"] is True
    assert summary["claim_grade_public_benchmark_ready"] is False
    assert summary["public_benchmark_gate_status"] == "blocked_refine_tier_public_benchmark_readiness"
    assert summary["public_benchmark_operator_work_order_ready"] is True
    assert summary["public_benchmark_work_order_row_count"] == 8
    assert "insufficient_total_rows" in summary["public_benchmark_blockers"]
    assert "free_energy_spearman_or_pair_gate_not_ready" in summary["public_benchmark_blockers"]
    assert summary["claim_promotion_allowed"] is False
    assert summary["claim_promotion_blocker_count"] == 6
    assert summary["claim_promotion_blockers"] == [
        "public_benchmark_gate_not_ready",
        "parameter_calibration_claim_not_ready",
        "metal_cofactor_parameterization_not_ready",
        "charged_residue_protonation_and_charge_calibration_not_ready",
        "solvent_fep_public_pair_calibration_not_ready",
        "external_structure_quality_parity_not_ready",
    ]
    assert "curated public benchmark work-order rows" in summary["claim_promotion_next_required_step"]
    assert summary["pass_count"] == summary["check_count"]
    checks = {row["check_id"]: row for row in payload["checks"]}
    assert checks["fast_tier_ca_sc_residue_block_layout"]["status"] == "pass"
    assert checks["fast_tier_residue_class_nonbonded_params"]["status"] == "pass"
    assert checks["fast_tier_residue_class_screened_charges"]["status"] == "pass"
    assert checks["fast_tier_coarse_backbone_bonded_term"]["status"] == "pass"
    assert checks["fast_tier_coarse_backbone_angle_term"]["status"] == "pass"
    assert checks["fast_tier_runtime_profile_forcefield_params"]["status"] == "pass"
    assert checks["trajectory_engine_coarse_forcefield_param_surface"]["status"] == "pass"
    assert checks["module_core.explicit_solvent"]["status"] == "pass"
    assert checks["module_core.fep"]["status"] == "pass"
    assert checks["refine_tier_allatom_bonded_energy_active"]["status"] == "pass"
    assert checks["refine_tier_atom_typing_charge_exclusion_active"]["status"] == "pass"
    assert checks["refine_tier_atom_typing_coverage_surface"]["status"] == "pass"
    assert checks["refine_tier_unsupported_metal_fail_closed_surface"]["status"] == "pass"
    assert checks["refine_tier_metal_cofactor_coordination_claim_guard"]["status"] == "pass"
    assert checks["refine_tier_charged_residue_atom_typing_surface"]["status"] == "pass"
    assert checks["refine_tier_formal_charge_proxy_claim_guard"]["status"] == "pass"
    assert checks["refine_tier_solvent_fep_calibration_claim_guard"]["status"] == "pass"
    assert checks["refine_tier_structure_quality_interface_claim_guard"]["status"] == "pass"
    assert checks["refine_tier_parameter_calibration_claim_guard"]["status"] == "pass"
    assert checks["refine_tier_dihedral_improper_terms_active"]["status"] == "pass"
    assert checks["refine_tier_full_stack_internal_smoke"]["status"] == "pass"
    assert checks["refine_tier_allatom_energy_finite"]["status"] == "pass"
    assert checks["refine_tier_pose_metric_surface_ready"]["status"] == "pass"
    assert checks["refine_tier_free_energy_calibration_claim_guard"]["status"] == "pass"
    assert checks["refine_tier_public_benchmark_blocker_linkage"]["status"] == "pass"
