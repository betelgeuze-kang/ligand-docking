from __future__ import annotations

from typing import Any

EXECUTION_MODE_SMOKE = "smoke"
EXECUTION_MODE_RESTRICTED_PRODUCTION = "restricted-production"
ALLOWED_EXECUTION_MODES = {
    EXECUTION_MODE_SMOKE,
    EXECUTION_MODE_RESTRICTED_PRODUCTION,
}


def _required_bool(profile: dict[str, Any], key: str) -> bool:
    value = profile.get(key)
    if not isinstance(value, bool):
        raise PermissionError(f"runner profile {key} must be an explicit boolean")
    return value


def validate_runner_profile_execution_contract(
    profile: dict[str, Any],
    *,
    require_explicit: bool = True,
) -> dict[str, Any]:
    """Validate the product-facing execution boundary declared by a runner profile.

    Older ad-hoc test profiles may omit the contract when ``require_explicit`` is
    false. Such profiles are returned as fail-closed ``unspecified`` contracts
    and are never eligible for customer docking dispatch.
    """

    mode = str(profile.get("execution_mode", "") or "").strip().lower()
    if not mode:
        if require_explicit:
            raise PermissionError("runner profile execution_mode is required")
        return {
            "execution_contract_explicit": False,
            "execution_mode": "unspecified",
            "customer_submission_allowed": False,
            "synthetic_input_allowed": False,
            "production_claim_allowed": False,
            "customer_pose_emission_allowed": False,
        }
    if mode not in ALLOWED_EXECUTION_MODES:
        raise PermissionError(
            f"runner profile execution_mode must be one of {sorted(ALLOWED_EXECUTION_MODES)}"
        )

    customer_submission_allowed = _required_bool(profile, "customer_submission_allowed")
    synthetic_input_allowed = _required_bool(profile, "synthetic_input_allowed")
    production_claim_allowed = _required_bool(profile, "production_claim_allowed")
    customer_pose_emission_allowed = _required_bool(profile, "customer_pose_emission_allowed")

    if mode == EXECUTION_MODE_SMOKE:
        if customer_submission_allowed:
            raise PermissionError("smoke runner profiles cannot allow customer submissions")
        if production_claim_allowed:
            raise PermissionError("smoke runner profiles cannot allow production claims")
        if customer_pose_emission_allowed:
            raise PermissionError("smoke runner profiles cannot emit customer poses")
    elif synthetic_input_allowed:
        raise PermissionError("restricted-production runner profiles cannot allow synthetic input")

    return {
        "execution_contract_explicit": True,
        "execution_mode": mode,
        "customer_submission_allowed": customer_submission_allowed,
        "synthetic_input_allowed": synthetic_input_allowed,
        "production_claim_allowed": production_claim_allowed,
        "customer_pose_emission_allowed": customer_pose_emission_allowed,
    }
