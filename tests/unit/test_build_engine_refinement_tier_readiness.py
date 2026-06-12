from __future__ import annotations

from tools.product import build_engine_refinement_tier_readiness as mod


def test_build_engine_refinement_tier_readiness_passes_on_repo_defaults() -> None:
    payload = mod.build_engine_refinement_tier_readiness()
    summary = payload["summary"]
    assert summary["engine_refinement_tier_ready"] is True
    assert summary["status"] == "engine_refinement_tier_ready"
    assert summary["refined_energy_col"] == "deltaG_mm_gbsa_kcal_mol"
    assert summary["pass_count"] == summary["check_count"]
    checks = {row["check_id"]: row for row in payload["checks"]}
    assert checks["fast_tier_ca_sc_residue_block_layout"]["status"] == "pass"
    assert checks["fast_tier_residue_class_nonbonded_params"]["status"] == "pass"
    assert checks["fast_tier_residue_class_screened_charges"]["status"] == "pass"
    assert checks["fast_tier_coarse_backbone_bonded_term"]["status"] == "pass"
    assert checks["fast_tier_coarse_backbone_angle_term"]["status"] == "pass"
    assert checks["fast_tier_runtime_profile_forcefield_params"]["status"] == "pass"
    assert checks["trajectory_engine_coarse_forcefield_param_surface"]["status"] == "pass"
