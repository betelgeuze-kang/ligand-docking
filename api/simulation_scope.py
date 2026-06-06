from __future__ import annotations

from typing import Any

PRODUCT_SIMULATION_SCOPE = (
    "ligand HTVS and backmapping scoring via operator-approved validated runner profiles only"
)
GENERIC_MD_SCOPE_DENIED_REASON = (
    "Generic molecular-dynamics simulation is not a supported product surface. "
    "Submit jobs with runner_profile_id pointing to an operator-approved ligand HTVS or "
    "backmapping scoring profile."
)
RUNNER_PROFILE_REQUIRED_DETAIL = (
    "runner_profile_id is required. Supported product scope: ligand HTVS and backmapping "
    "scoring via validated runner profiles."
)


def request_has_runner_profile(request_data: dict[str, Any]) -> bool:
    return bool(str(request_data.get("runner_profile_id", "") or "").strip())


def validate_simulation_request_scope(request_data: dict[str, Any]) -> None:
    if request_has_runner_profile(request_data):
        return
    raise UnsupportedSimulationScopeError(
        RUNNER_PROFILE_REQUIRED_DETAIL,
        product_scope=PRODUCT_SIMULATION_SCOPE,
    )


class UnsupportedSimulationScopeError(ValueError):
    def __init__(self, message: str, *, product_scope: str) -> None:
        super().__init__(message)
        self.product_scope = product_scope
