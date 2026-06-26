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
        docking_private_payload_keys: str = "",
        product_api_secret_rotation_days: int = 30,
    ) -> None:
        self.product_api_auth_required = product_api_auth_required
        self.product_api_token = product_api_token
        self.docking_private_payload_keys = docking_private_payload_keys
        self.product_api_secret_rotation_days = product_api_secret_rotation_days


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
    """auth_required=False + empty token should not raise."""
    settings = _FakeSettings(product_api_auth_required=False, product_api_token="")
    # Should complete without error
    run_startup_preflight(settings)


def test_auth_required_valid_token_does_not_raise() -> None:
    """auth_required=True + non-empty token should not raise."""
    settings = _FakeSettings(
        product_api_auth_required=True, product_api_token="my-secret-token"
    )
    # Should complete without error
    run_startup_preflight(settings)


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
