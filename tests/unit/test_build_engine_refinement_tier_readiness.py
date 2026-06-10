from __future__ import annotations

from tools.product import build_engine_refinement_tier_readiness as mod


def test_build_engine_refinement_tier_readiness_passes_on_repo_defaults() -> None:
    payload = mod.build_engine_refinement_tier_readiness()
    summary = payload["summary"]
    assert summary["engine_refinement_tier_ready"] is True
    assert summary["status"] == "engine_refinement_tier_ready"
    assert summary["refined_energy_col"] == "deltaG_mm_gbsa_kcal_mol"
