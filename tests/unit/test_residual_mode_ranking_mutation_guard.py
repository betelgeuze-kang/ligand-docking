from __future__ import annotations

from betelgeuze_product.docking_request import _production_ai_posture_from_registry
from betelgeuze_product.residual_mode_policy import (
    customer_ranking_mutation_allowed_at_runtime,
    production_ai_inference_subject_active,
    residual_active_score_column,
)
from tools.product.build_residual_mode_inference_wiring_smoke import run_smoke


def test_shadow_mode_keeps_ranking_mutation_guard_locked() -> None:
    registry = {
        "default_residual_mode": "shadow",
        "production_promotion_allowed": False,
        "customer_facing_auto_correction_allowed": False,
        "customer_facing_score_mutation_allowed": False,
        "customer_facing_ranking_mutation_allowed": False,
        "trained_model_checkpoint_count": 1,
    }
    posture = _production_ai_posture_from_registry(registry)
    assert posture["production_ai_inference_subject_active"] is False
    assert customer_ranking_mutation_allowed_at_runtime(registry, shadow_only_active_locked=False) is False
    assert residual_active_score_column(assist_mode="shadow", shadow_only_active_locked=False) == "binding_score_composite_v7"


def test_docking_posture_honors_shadow_lock_for_ranking_mutation() -> None:
    registry = {
        "default_residual_mode": "production_guarded",
        "production_promotion_allowed": True,
        "customer_facing_auto_correction_allowed": True,
        "customer_facing_score_mutation_allowed": True,
        "customer_facing_ranking_mutation_allowed": True,
        "trained_model_checkpoint_count": 1,
    }
    locked = _production_ai_posture_from_registry(registry, shadow_only_active_locked=True)
    unlocked = _production_ai_posture_from_registry(registry, shadow_only_active_locked=False)
    assert locked["production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert unlocked["production_ai_customer_facing_ranking_mutation_allowed"] is True


def test_production_guarded_mode_allows_ranking_mutation_when_unlocked() -> None:
    registry = {
        "default_residual_mode": "production_guarded",
        "production_promotion_allowed": True,
        "customer_facing_auto_correction_allowed": True,
        "customer_facing_score_mutation_allowed": True,
        "customer_facing_ranking_mutation_allowed": True,
        "trained_model_checkpoint_count": 1,
    }
    assert production_ai_inference_subject_active(registry) is True
    assert customer_ranking_mutation_allowed_at_runtime(registry, shadow_only_active_locked=False) is True
    assert (
        residual_active_score_column(assist_mode="production_guarded", shadow_only_active_locked=False)
        == "binding_score_composite_v7_residual_active"
    )


def test_residual_mode_inference_wiring_smoke_passes_all_fixtures() -> None:
    payload = run_smoke()
    assert payload["summary"]["status"] == "residual_mode_inference_wiring_smoke_ready"
    assert payload["summary"]["pass_mode_count"] == 3
