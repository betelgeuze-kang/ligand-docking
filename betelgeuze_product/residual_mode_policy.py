from __future__ import annotations

from typing import Any

GUARDED_RESIDUAL_MODES = frozenset({"assist", "production", "production_guarded"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def production_ai_inference_subject_active(registry: dict[str, Any]) -> bool:
    default_mode = _text(registry.get("default_residual_mode"))
    trained_count = int(registry.get("trained_model_checkpoint_count") or 0)
    return bool(
        registry.get("production_promotion_allowed") is True
        and registry.get("customer_facing_auto_correction_allowed") is True
        and registry.get("customer_facing_score_mutation_allowed") is True
        and registry.get("customer_facing_ranking_mutation_allowed") is True
        and trained_count > 0
        and default_mode in GUARDED_RESIDUAL_MODES
    )


def customer_ranking_mutation_allowed_at_runtime(
    registry: dict[str, Any],
    *,
    shadow_only_active_locked: bool = True,
) -> bool:
    return production_ai_inference_subject_active(registry) and not shadow_only_active_locked


def residual_active_score_column(
    *,
    assist_mode: str,
    shadow_only_active_locked: bool,
) -> str:
    mode = _text(assist_mode).lower()
    if mode in GUARDED_RESIDUAL_MODES and not shadow_only_active_locked:
        return "binding_score_composite_v7_residual_active"
    return "binding_score_composite_v7"


def residual_ranking_apply_active(
    *,
    assist_mode: str,
    shadow_only_active_locked: bool,
    base_mode: str,
) -> bool:
    mode = _text(assist_mode).lower()
    effective_mode = _text(base_mode) or "shadow_only"
    if mode in GUARDED_RESIDUAL_MODES and not shadow_only_active_locked:
        effective_mode = "apply_ranking"
    return effective_mode in {"apply", "apply_ranking"} and not shadow_only_active_locked


def residual_runtime_status(
    *,
    assist_mode: str,
    shadow_only_active_locked: bool,
    gpcr_effective_mode: str = "shadow_only",
) -> str:
    mode = _text(assist_mode).lower()
    if shadow_only_active_locked:
        return "shadow_ready_claim_locked"
    if mode in GUARDED_RESIDUAL_MODES:
        return "residual_assist_ready"
    if _text(gpcr_effective_mode) == "shadow_only":
        return "shadow_ready"
    return "apply_ready"
