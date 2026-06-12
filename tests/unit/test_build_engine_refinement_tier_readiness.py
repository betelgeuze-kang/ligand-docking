from __future__ import annotations

import csv

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
    assert summary["claim_promotion_evidence_receipt_status"] == (
        "blocked_engine_refinement_claim_evidence_receipt"
    )
    assert summary["claim_promotion_evidence_receipt_ready"] is False
    assert summary["claim_promotion_evidence_receipt_blocked_row_count"] == 6
    assert summary["claim_promotion_evidence_receipt_csv"] == (
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
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
    assert summary["claim_promotion_action_row_count"] == 6
    assert "curated public benchmark work-order rows" in summary["claim_promotion_next_required_step"]
    action_rows = payload["claim_promotion_action_rows"]
    assert len(action_rows) == 6
    assert [row["blocker_id"] for row in action_rows] == summary["claim_promotion_blockers"]
    rows_by_id = {row["blocker_id"]: row for row in action_rows}
    public_row = rows_by_id["public_benchmark_gate_not_ready"]
    assert public_row["current_status"] == "blocked_refine_tier_public_benchmark_readiness"
    assert "runs/refine_tier_public_benchmark_work_order_current.csv" in public_row["owner_action"]
    assert "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE" in public_row["owner_action"]
    assert public_row["gate_or_artifact"] == "runs/refine_tier_public_benchmark_readiness_current.json"
    assert "insufficient_total_rows" in public_row["blocking_signals"]
    assert "OpenMM/Schrödinger-grade claims stay blocked" in public_row["claim_boundary"]
    assert rows_by_id["metal_cofactor_parameterization_not_ready"]["gate_or_artifact"] == (
        "refine_tier_metal_cofactor_coordination_claim_guard"
    )
    assert "MolProbity/OpenStructure" in rows_by_id[
        "external_structure_quality_parity_not_ready"
    ]["required_evidence"]
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
    assert checks["refine_tier_claim_evidence_receipt_linkage"]["status"] == "pass"


def test_engine_refinement_tier_readiness_writes_claim_promotion_action_board(tmp_path) -> None:
    out_json = tmp_path / "engine_refinement_tier_readiness.json"
    out_csv = tmp_path / "engine_refinement_claim_promotion_action_board.csv"

    mod.main(["--out-json", str(out_json), "--out-action-board-csv", str(out_csv)])

    assert out_json.is_file()
    assert out_csv.is_file()
    with out_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert rows[0]["blocker_id"] == "public_benchmark_gate_not_ready"
    assert rows[0]["gate_or_artifact"] == "runs/refine_tier_public_benchmark_readiness_current.json"
    assert "insufficient_total_rows" in rows[0]["blocking_signals"]
    assert rows[-1]["blocker_id"] == "external_structure_quality_parity_not_ready"
    assert rows[-1]["gate_or_artifact"] == "refine_tier_structure_quality_interface_claim_guard"
