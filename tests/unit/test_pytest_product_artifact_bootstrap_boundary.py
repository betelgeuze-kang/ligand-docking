from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFTEST_PATH = _REPO_ROOT / "tests/conftest.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "betelgeuze_test_bootstrap_conftest",
        _CONFTEST_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(*paths: Path) -> SimpleNamespace:
    return SimpleNamespace(args=[str(path) for path in paths])


def test_disabled_mode_skips_nonlightweight_product_bootstrap(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(
        module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV,
        "disabled",
    )

    assert module._product_artifact_bootstrap_required(
        _config(_REPO_ROOT / "tests/unit/nonlightweight_contract.py")
    ) is False


def test_required_mode_forces_bootstrap_even_for_mobile_contract(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(
        module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV,
        "required",
    )

    assert module._product_artifact_bootstrap_required(
        _config(_REPO_ROOT / "tests/mobile/lightweight_contract.py")
    ) is True


def test_auto_mode_preserves_existing_lightweight_boundary(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "auto")

    assert module._product_artifact_bootstrap_required(
        _config(_REPO_ROOT / "tests/mobile/lightweight_contract.py")
    ) is False
    assert module._product_artifact_bootstrap_required(
        _config(_REPO_ROOT / "tests/unit/nonlightweight_contract.py")
    ) is True


def test_invalid_mode_fails_closed(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "sometimes")

    with pytest.raises(pytest.UsageError, match="must be one of"):
        module._product_artifact_bootstrap_mode()


def test_whitespace_and_case_are_normalized(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "  DISABLED  ")

    assert module._product_artifact_bootstrap_mode() == "disabled"
