from __future__ import annotations

from typing import Any

from betelgeuze_engine.biodiscovery import TierBetaScreeningResult
from betelgeuze_engine.product.runners.tier_beta_service_adapter import (
    run_tier_beta_vertical_slice_from_payload,
)


def run_tier_beta_vertical_slice_compat(payload: dict[str, Any]) -> TierBetaScreeningResult:
    """Shared legacy-runner compatibility hook for restricted Tier-beta jobs."""
    return run_tier_beta_vertical_slice_from_payload(payload)
