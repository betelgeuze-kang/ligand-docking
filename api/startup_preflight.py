# api/startup_preflight.py
"""Startup preflight checks -- stdlib-only, no FastAPI dependency.

run_startup_preflight(settings) raises SystemExit when the configuration is
fatally inconsistent (e.g. auth required but no token configured).

check_key_staleness(settings) returns a warning dict when
docking_private_payload_keys is configured but the rotation metadata suggests
the keys may be stale. It never blocks startup.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_startup_preflight(settings: Any) -> None:
    """Refuse to start if product_api_auth_required is True but product_api_token is empty.

    Raises SystemExit with a clear diagnostic message so the uvicorn process
    does not begin accepting requests in an unusable state.
    """
    auth_required: bool = getattr(settings, "product_api_auth_required", False)
    token: str = getattr(settings, "product_api_token", "") or ""

    if auth_required and not token.strip():
        raise SystemExit(
            "STARTUP PREFLIGHT FAILED: product_api_auth_required is True but "
            "PRODUCT_API_TOKEN is empty. The server cannot authenticate any "
            "request in this state. Set PRODUCT_API_TOKEN or disable "
            "PRODUCT_API_AUTH_REQUIRED before starting."
        )


def check_key_staleness(settings: Any) -> dict[str, Any] | None:
    """Check whether docking_private_payload_keys might be stale.

    Returns a warning dict if keys are configured but rotation_days suggests
    they may need rotation. Returns None when no warning is applicable.

    This function never blocks startup -- it only emits a log warning and
    returns a structured dict for metrics/observability.
    """
    keys: str = getattr(settings, "docking_private_payload_keys", "") or ""
    rotation_days: int = getattr(settings, "product_api_secret_rotation_days", 30)

    if not keys.strip():
        # No keys configured -- nothing to warn about.
        return None

    # When keys are present but there is no rotation metadata (no timestamp
    # embedded), we cannot verify freshness. Warn the operator.
    # In a production deployment this would cross-reference a key-creation
    # timestamp; here we flag the absence of verifiable rotation evidence.
    if rotation_days <= 0:
        warning = {
            "code": "key_staleness_unchecked",
            "severity": "warning",
            "reason": (
                "docking_private_payload_keys is configured but "
                "product_api_secret_rotation_days is <= 0; key rotation "
                "policy is effectively disabled."
            ),
        }
        logger.warning("Startup key-staleness check: %s", warning["reason"])
        return warning

    # Keys are configured and a positive rotation policy is set but no
    # verifiable creation timestamp exists in the runtime environment.
    warning = {
        "code": "key_staleness_unverifiable",
        "severity": "warning",
        "reason": (
            f"docking_private_payload_keys is configured with a "
            f"{rotation_days}-day rotation policy, but no key-creation "
            f"timestamp is available to verify freshness. Ensure keys are "
            f"rotated within the configured window."
        ),
    }
    logger.warning("Startup key-staleness check: %s", warning["reason"])
    return warning
