from __future__ import annotations

import pytest
from fastapi import HTTPException

from api import product_docking


def test_debug_diagnostics_allowed_for_local_unexposed_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRODUCT_API_DEBUG_DIAGNOSTICS_ALLOWED", raising=False)
    monkeypatch.setattr(product_docking.settings, "product_api_auth_required", False)
    monkeypatch.setattr(product_docking.settings, "product_api_hosted_exposure_approved", False)

    assert product_docking._guard_debug_diagnostics(True) is True


def test_debug_diagnostics_blocked_when_auth_required_without_operator_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PRODUCT_API_DEBUG_DIAGNOSTICS_ALLOWED", raising=False)
    monkeypatch.setattr(product_docking.settings, "product_api_auth_required", True)
    monkeypatch.setattr(product_docking.settings, "product_api_hosted_exposure_approved", False)

    with pytest.raises(HTTPException) as exc:
        product_docking._guard_debug_diagnostics(True)

    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "debug_diagnostics_not_allowed"
    assert exc.value.detail["execution_enabled"] is False
    assert exc.value.detail["docking_results_emitted"] is False


def test_debug_diagnostics_operator_opt_in_overrides_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCT_API_DEBUG_DIAGNOSTICS_ALLOWED", "1")
    monkeypatch.setattr(product_docking.settings, "product_api_auth_required", True)
    monkeypatch.setattr(product_docking.settings, "product_api_hosted_exposure_approved", True)

    assert product_docking._guard_debug_diagnostics(True) is True
