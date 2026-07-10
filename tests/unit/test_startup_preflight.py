# tests/unit/test_startup_preflight.py
"""Tests for api.startup_preflight -- stdlib-only, no external dependencies."""

from __future__ import annotations

import pytest

from api.startup_preflight import check_key_staleness, run_startup_preflight


class _FakeSettings:
    """Minimal stand-in for api.config.Settings."""

    def __init__(
        self,
        product_api_auth_required: bool = False,
        product_api_token: str = "",
        product_api_token_tenant_id: str = "local",
        product_api_admin_token: str = "",
        docking_private_payload_keys: str = "",
        product_api_secret_rotation_days: int = 30,
        product_api_hosted_exposure_approved: bool = False,
        product_api_tls_termination_operator_verified: bool = False,
        api_result_manifest_signing_key: str = "local-dev-result-manifest-signing-key-change-me",
        api_result_manifest_key_id: str = "local-dev",
    ) -> None:
        self.product_api_auth_required = product_api_auth_required
        self.product_api_token = product_api_token
        self.product_api_token_tenant_id = product_api_token_tenant_id
        self.product_api_admin_token = product_api_admin_token
        self.docking_private_payload_keys = docking_private_payload_keys
        self.product_api_secret_rotation_days = product_api_secret_rotation_days
        self.product_api_hosted_exposure_approved = product_api_hosted_exposure_approved
        self.product_api_tls_termination_operator_verified = product_api_tls_termination_operator_verified
        self.api_result_manifest_signing_key = api_result_manifest_signing_key
        self.api_result_manifest_key_id = api_result_manifest_key_id


# --- run_startup_preflight tests ---


def test_auth_required_empty_token_raises_system_exit() -> None:
    """auth_required=True + empty token must raise SystemExit."""
    settings = _FakeSettings(product_api_auth_required=True, product_api_token="")
    with pytest.raises(SystemExit) as exc_info:
        run_startup_preflight(settings)
    assert "PRODUCT_API_TOKEN" in str(exc_info.value)
    assert "empty" in str(exc_info.value).lower()


def test_auth_required_whitespace_token_raises_system_exit() -> None:
    """auth_required=True + whitespace-only token must also raise."""
    settings = _FakeSettings(product_api_auth_required=True, product_api_token="   ")
    with pytest.raises(SystemExit):
        run_startup_preflight(settings)


def test_auth_not_required_empty_token_does_not_raise() -> None:
    """auth_required=False + empty token should not raise for local/dev exposure."""
    settings = _FakeSettings(product_api_auth_required=False, product_api_token="")
    run_startup_preflight(settings)


def test_auth_required_valid_token_does_not_raise() -> None:
    """auth_required=True + non-empty token should not raise for local/dev exposure."""
    settings = _FakeSettings(
        product_api_auth_required=True, product_api_token="my-secret-token"
    )
    run_startup_preflight(settings)


def test_auth_required_rejects_invalid_server_bound_tenant() -> None:
    settings = _FakeSettings(
        product_api_auth_required=True,
        product_api_token="my-secret-token",
        product_api_token_tenant_id="../tenant",
    )
    with pytest.raises(SystemExit, match="PRODUCT_API_TOKEN_TENANT_ID"):
        run_startup_preflight(settings)


def test_admin_token_must_differ_from_tenant_token() -> None:
    settings = _FakeSettings(
        product_api_auth_required=True,
        product_api_token="same-token",
        product_api_admin_token="same-token",
    )
    with pytest.raises(SystemExit, match="PRODUCT_API_ADMIN_TOKEN"):
        run_startup_preflight(settings)


def _hosted_settings(**overrides: object) -> _FakeSettings:
    payload = {
        "product_api_hosted_exposure_approved": True,
        "product_api_auth_required": True,
        "product_api_token": "operator-token",
        "product_api_token_tenant_id": "hosted-tenant",
        "product_api_tls_termination_operator_verified": True,
        "api_result_manifest_signing_key": "operator-managed-signing-secret",
        "api_result_manifest_key_id": "product-key-v1",
        "docking_private_payload_keys": "k1:YWJjZGVmZ2hpamtsbW5vcA==",
    }
    payload.update(overrides)
    return _FakeSettings(**payload)


def test_hosted_exposure_requires_auth_required() -> None:
    with pytest.raises(SystemExit, match="PRODUCT_API_AUTH_REQUIRED"):
        run_startup_preflight(
            _hosted_settings(product_api_auth_required=False)
        )


def test_hosted_exposure_requires_tls_verified() -> None:
    with pytest.raises(SystemExit, match="TLS_TERMINATION"):
        run_startup_preflight(
            _hosted_settings(product_api_tls_termination_operator_verified=False)
        )


def test_hosted_exposure_blocks_dev_manifest_signing_key() -> None:
    with pytest.raises(SystemExit, match="API_RESULT_MANIFEST_SIGNING_KEY"):
        run_startup_preflight(
            _hosted_settings(
                api_result_manifest_signing_key="local-dev-result-manifest-signing-key-change-me"
            )
        )


def test_hosted_exposure_blocks_dev_manifest_key_id() -> None:
    with pytest.raises(SystemExit, match="API_RESULT_MANIFEST_KEY_ID"):
        run_startup_preflight(_hosted_settings(api_result_manifest_key_id="local-dev"))


def test_hosted_exposure_requires_private_payload_keys() -> None:
    with pytest.raises(SystemExit, match="DOCKING_PRIVATE_PAYLOAD_KEYS"):
        run_startup_preflight(_hosted_settings(docking_private_payload_keys=""))


def test_hosted_exposure_with_operator_security_controls_does_not_raise() -> None:
    run_startup_preflight(_hosted_settings())


# --- check_key_staleness tests ---


def test_key_staleness_no_keys_returns_none() -> None:
    """No keys configured means no warning."""
    settings = _FakeSettings(docking_private_payload_keys="")
    result = check_key_staleness(settings)
    assert result is None


def test_key_staleness_keys_with_positive_rotation_returns_warning() -> None:
    """Keys configured with positive rotation_days returns an unverifiable warning."""
    settings = _FakeSettings(
        docking_private_payload_keys="key1:abc123",
        product_api_secret_rotation_days=30,
    )
    result = check_key_staleness(settings)
    assert result is not None
    assert result["code"] == "key_staleness_unverifiable"
    assert result["severity"] == "warning"
    assert "30-day" in result["reason"]


def test_key_staleness_keys_with_zero_rotation_returns_disabled_warning() -> None:
    """Keys configured with rotation_days=0 returns a policy-disabled warning."""
    settings = _FakeSettings(
        docking_private_payload_keys="key1:abc123",
        product_api_secret_rotation_days=0,
    )
    result = check_key_staleness(settings)
    assert result is not None
    assert result["code"] == "key_staleness_unchecked"
    assert result["severity"] == "warning"
    assert "disabled" in result["reason"].lower()


def test_key_staleness_keys_with_negative_rotation_returns_disabled_warning() -> None:
    """Keys configured with negative rotation_days also triggers the disabled path."""
    settings = _FakeSettings(
        docking_private_payload_keys="key1:abc123",
        product_api_secret_rotation_days=-1,
    )
    result = check_key_staleness(settings)
    assert result is not None
    assert result["code"] == "key_staleness_unchecked"
