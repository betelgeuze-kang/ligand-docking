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


def test_disabled_mode_skips_session_bootstrap(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "disabled")

    assert module._product_artifact_bootstrap_required(SimpleNamespace()) is False


def test_required_mode_is_the_only_session_bootstrap_opt_in(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "required")

    assert module._product_artifact_bootstrap_required(SimpleNamespace()) is True


def test_auto_mode_no_longer_classifies_tests_by_filename(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "auto")

    assert module._product_artifact_bootstrap_required(
        SimpleNamespace(args=[str(_REPO_ROOT / "tests/unit/new_contract.py")])
    ) is False
    assert not hasattr(module, "_LIGHTWEIGHT_CONTRACT_FILES")
    assert not hasattr(module, "_requested_tests_are_lightweight")


def test_invalid_mode_fails_closed(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "sometimes")

    with pytest.raises(pytest.UsageError, match="must be one of"):
        module._product_artifact_bootstrap_mode()


def test_whitespace_and_case_are_normalized(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "  REQUIRED  ")

    assert module._product_artifact_bootstrap_mode() == "required"


def test_explicit_materializer_creates_and_returns_artifact_root(tmp_path) -> None:
    module = _module()
    calls: list[str] = []

    def materialize() -> None:
        calls.append("called")
        runs = tmp_path / "runs"
        runs.mkdir()
        (runs / module._PRODUCT_CAPABILITY_FILENAME).write_text(
            "{}\n",
            encoding="utf-8",
        )

    observed = module._ensure_product_contract_artifacts(
        root=tmp_path,
        materializer=materialize,
    )

    assert observed == tmp_path / "runs"
    assert calls == ["called"]


def test_existing_artifact_skips_materializer(tmp_path) -> None:
    module = _module()
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / module._PRODUCT_CAPABILITY_FILENAME).write_text(
        "{}\n",
        encoding="utf-8",
    )

    observed = module._ensure_product_contract_artifacts(
        root=tmp_path,
        materializer=lambda: pytest.fail("materializer must not run"),
    )

    assert observed == runs


def test_missing_artifact_after_materialization_fails_closed(tmp_path) -> None:
    module = _module()

    with pytest.raises(pytest.UsageError, match="did not create"):
        module._ensure_product_contract_artifacts(
            root=tmp_path,
            materializer=lambda: None,
        )


def test_nonregular_artifact_fails_closed(tmp_path) -> None:
    module = _module()
    capability = tmp_path / "runs" / module._PRODUCT_CAPABILITY_FILENAME
    capability.mkdir(parents=True)

    with pytest.raises(pytest.UsageError, match="not a regular file"):
        module._ensure_product_contract_artifacts(
            root=tmp_path,
            materializer=lambda: None,
        )


def test_product_artifact_marker_is_explicit() -> None:
    module = _module()

    marked = SimpleNamespace(
        get_closest_marker=lambda name: object()
        if name == module._PRODUCT_ARTIFACT_MARKER
        else None
    )
    unmarked = SimpleNamespace(get_closest_marker=lambda _name: None)

    assert module._node_requests_product_artifacts(marked) is True
    assert module._node_requests_product_artifacts(unmarked) is False


def test_sessionstart_materializes_only_in_required_mode(monkeypatch) -> None:
    module = _module()
    calls: list[str] = []
    monkeypatch.setattr(
        module,
        "_ensure_product_contract_artifacts",
        lambda: calls.append("materialized"),
    )
    session = SimpleNamespace(config=SimpleNamespace())

    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "auto")
    module.pytest_sessionstart(session)
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "disabled")
    module.pytest_sessionstart(session)
    monkeypatch.setenv(module._PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "required")
    module.pytest_sessionstart(session)

    assert calls == ["materialized"]
