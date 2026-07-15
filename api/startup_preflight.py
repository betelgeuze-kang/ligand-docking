# api/startup_preflight.py
"""Startup preflight checks -- stdlib-only, no FastAPI dependency.

run_startup_preflight(settings) raises SystemExit when the configuration is
fatally inconsistent. The checks are deliberately fail-start for hosted/product
exposure so the API does not accept traffic with missing auth, development
signing keys, missing encrypted private-payload keys, or unverified TLS.

check_key_staleness(settings) returns a warning dict when
docking_private_payload_keys is configured but the rotation metadata suggests
the keys may be stale. It never blocks startup.
"""

from __future__ import annotations

import logging
from typing import Any

from api.deployment_secret_policy import (
    docking_private_payload_keys_are_operator_managed,
    product_api_token_is_operator_managed,
    result_manifest_key_id_is_operator_managed,
    result_manifest_signing_key_is_operator_managed,
)

logger = logging.getLogger(__name__)


def _flag(settings: Any, name: str, default: bool = False) -> bool:
    return bool(getattr(settings, name, default))


def _text(settings: Any, name: str, default: str = "") -> str:
    return str(getattr(settings, name, default) or "").strip()


def _fatal(message: str) -> None:
    raise SystemExit(f"STARTUP PREFLIGHT FAILED: {message}")


def run_startup_preflight(settings: Any) -> None:
    """Refuse to start when product exposure configuration is unsafe."""

    auth_required = _flag(settings, "product_api_auth_required")
    token = _text(settings, "product_api_token")
    admin_token = _text(settings, "product_api_admin_token")
    hosted_exposure = _flag(settings, "product_api_hosted_exposure_approved")
    tls_verified = _flag(settings, "product_api_tls_termination_operator_verified")
    signing_key = _text(settings, "api_result_manifest_signing_key")
    signing_key_id = _text(settings, "api_result_manifest_key_id")
    private_payload_keys = _text(settings, "docking_private_payload_keys")

    if auth_required and not token:
        _fatal(
            "product_api_auth_required is True but PRODUCT_API_TOKEN is empty. "
            "The server cannot authenticate any request in this state. Set "
            "PRODUCT_API_TOKEN or disable PRODUCT_API_AUTH_REQUIRED before starting."
        )
    if auth_required and not product_api_token_is_operator_managed(token):
        _fatal(
            "PRODUCT_API_AUTH_REQUIRED=1 requires PRODUCT_API_TOKEN to be an "
            "operator-managed non-placeholder secret."
        )
    if (
        auth_required
        and admin_token
        and not product_api_token_is_operator_managed(admin_token)
    ):
        _fatal(
            "PRODUCT_API_AUTH_REQUIRED=1 requires a configured "
            "PRODUCT_API_ADMIN_TOKEN to be an operator-managed non-placeholder "
            "secret."
        )

    if auth_required and not result_manifest_signing_key_is_operator_managed(
        signing_key
    ):
        _fatal(
            "PRODUCT_API_AUTH_REQUIRED=1 requires "
            "API_RESULT_MANIFEST_SIGNING_KEY to be an operator-managed "
            "non-development secret."
        )
    if auth_required and not result_manifest_key_id_is_operator_managed(signing_key_id):
        _fatal(
            "PRODUCT_API_AUTH_REQUIRED=1 requires API_RESULT_MANIFEST_KEY_ID "
            "to be a non-development key identifier."
        )
    if auth_required and not docking_private_payload_keys_are_operator_managed(
        private_payload_keys
    ):
        _fatal(
            "PRODUCT_API_AUTH_REQUIRED=1 requires DOCKING_PRIVATE_PAYLOAD_KEYS "
            "to contain an operator-managed keyring in "
            "key_id:base64secret format with at least 32 decoded secret bytes "
            "per key."
        )

    if not hosted_exposure:
        return

    if not auth_required:
        _fatal(
            "PRODUCT_API_HOSTED_EXPOSURE_APPROVED=1 requires "
            "PRODUCT_API_AUTH_REQUIRED=1."
        )
    if not tls_verified:
        _fatal(
            "PRODUCT_API_HOSTED_EXPOSURE_APPROVED=1 requires "
            "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1."
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
