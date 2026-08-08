"""Fail-closed bridge from the frozen one-shot policy to external authority.

The historical A/B policy and the external immutable-reservation contract are
reviewed independently.  This module is the only repository-side composition
point: local eligibility cannot become execution authority while the external
provider remains unconfigured or historical execution remains non-operational.
"""

from __future__ import annotations

from typing import Any, Mapping

from .source_paired_clearance_external_reservation import (
    ExternalReservationContractError,
    external_reservation_operational_blockers,
    verify_external_reservation_policy,
)
from .source_paired_clearance_one_shot_ab import (
    OneShotABAuthorityError,
    OneShotABDecision,
)


INVALID_EXTERNAL_POLICY_BLOCKER = "external_reservation_policy_invalid"


def external_historical_execution_decision(
    external_policy: Mapping[str, Any],
) -> OneShotABDecision:
    """Return external operational authority without performing a network call."""

    try:
        verify_external_reservation_policy(external_policy)
        blockers = external_reservation_operational_blockers(external_policy)
    except ExternalReservationContractError:
        blockers = (INVALID_EXTERNAL_POLICY_BLOCKER,)
    return OneShotABDecision(authorized=not blockers, blockers=tuple(blockers))


def combine_one_shot_and_external_decisions(
    local_decision: OneShotABDecision,
    *,
    external_policy: Mapping[str, Any],
) -> OneShotABDecision:
    """Compose local eligibility with the mandatory external authority gate."""

    external = external_historical_execution_decision(external_policy)
    blockers = tuple(dict.fromkeys((*local_decision.blockers, *external.blockers)))
    return OneShotABDecision(authorized=not blockers, blockers=blockers)


def require_external_historical_execution_authority(
    external_policy: Mapping[str, Any],
) -> None:
    """Reject reserve/start/result mutation while external authority is closed."""

    decision = external_historical_execution_decision(external_policy)
    if not decision.authorized:
        raise OneShotABAuthorityError(";".join(decision.blockers))


__all__ = [
    "INVALID_EXTERNAL_POLICY_BLOCKER",
    "combine_one_shot_and_external_decisions",
    "external_historical_execution_decision",
    "require_external_historical_execution_authority",
]
