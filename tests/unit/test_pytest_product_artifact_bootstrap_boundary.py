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


class _Config:
    def __init__(self, *, requested: bool = False) -> None:
        self.requested = requested
        self.markers: list[tuple[str, str]] = []

    def getoption(self, name: str) -> bool:
        assert name == "product_contract_artifacts"
        return self.requested

    def addinivalue_line(self, name: str, value: str) -> None:
        self.markers.append((name, value))


def test_default_mode_skips_a_new_unclassified_unit_test(monkeypatch) -> None:
    module = _module()
    monkeypatch.delenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, raising=False)

    assert module._product_artifact_bootstrap_mode() == "disabled"
    assert module._product_artifact_bootstrap_required(_Config()) is False
    assert not hasattr(module, "_LIGHTWEIGHT_CONTRACT_FILES")


def test_required_mode_explicitly_bootstraps_product_integration(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "required")

    assert module._product_artifact_bootstrap_required(_Config()) is True


def test_disabled_mode_overrides_the_cli_option(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "disabled")

    assert module._product_artifact_bootstrap_required(
        _Config(requested=True)
    ) is False


def test_auto_mode_requires_the_explicit_cli_option(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "auto")

    assert module._product_artifact_bootstrap_required(_Config()) is False
    assert module._product_artifact_bootstrap_required(
        _Config(requested=True)
    ) is True


def test_sessionstart_does_not_materialize_by_default(monkeypatch) -> None:
    module = _module()
    monkeypatch.delenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, raising=False)
    called = []
    monkeypatch.setattr(
        module,
        "_materialize_product_contract_artifacts",
        lambda: called.append(True),
    )

    module.pytest_sessionstart(SimpleNamespace(config=_Config()))

    assert called == []


def test_sessionstart_materializes_once_when_required(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "required")
    called = []
    monkeypatch.setattr(
        module,
        "_materialize_product_contract_artifacts",
        lambda: called.append(True),
    )

    module.pytest_sessionstart(SimpleNamespace(config=_Config()))

    assert called == [True]


def test_product_marker_is_registered() -> None:
    module = _module()
    config = _Config()

    module.pytest_configure(config)

    assert config.markers == [
        (
            "markers",
            "product_contract_artifacts: request the session-scoped product "
            "contract artifact fixture for this test",
        )
    ]


def test_invalid_mode_fails_closed(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "sometimes")

    with pytest.raises(pytest.UsageError, match="must be one of"):
        module._product_artifact_bootstrap_mode()


def test_whitespace_and_case_are_normalized(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "  REQUIRED  ")

    assert module._product_artifact_bootstrap_mode() == "required"
