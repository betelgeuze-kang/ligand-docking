from __future__ import annotations

from betelgeuze_product.residual_mode_policy import (
    residual_active_score_column,
    residual_ranking_apply_active,
    residual_runtime_status,
)


def test_backmapping_residual_posture_matches_production_guarded_unlocked() -> None:
    assist_mode = "production_guarded"
    shadow_only_active_locked = False
    base_mode = "shadow_only"

    assert residual_ranking_apply_active(
        assist_mode=assist_mode,
        shadow_only_active_locked=shadow_only_active_locked,
        base_mode=base_mode,
    )
    assert (
        residual_active_score_column(
            assist_mode=assist_mode,
            shadow_only_active_locked=shadow_only_active_locked,
        )
        == "binding_score_composite_v7_residual_active"
    )
    assert (
        residual_runtime_status(
            assist_mode=assist_mode,
            shadow_only_active_locked=shadow_only_active_locked,
            gpcr_effective_mode="apply_ranking",
        )
        == "residual_assist_ready"
    )


def test_backmapping_residual_posture_stays_locked_for_shadow_variant() -> None:
    assist_mode = "production_guarded"
    shadow_only_active_locked = True

    assert not residual_ranking_apply_active(
        assist_mode=assist_mode,
        shadow_only_active_locked=shadow_only_active_locked,
        base_mode="shadow_only",
    )
    assert (
        residual_active_score_column(
            assist_mode=assist_mode,
            shadow_only_active_locked=shadow_only_active_locked,
        )
        == "binding_score_composite_v7"
    )
    assert (
        residual_runtime_status(
            assist_mode=assist_mode,
            shadow_only_active_locked=shadow_only_active_locked,
            gpcr_effective_mode="shadow_only",
        )
        == "shadow_ready_claim_locked"
    )
