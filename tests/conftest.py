from __future__ import annotations

import os
from pathlib import Path

import pytest

_CI_INTEGRATION_FILES = {
    "test_api_goal_import.py",
    "test_api_casp17_import.py",
    "test_api_cleanup_import.py",
    "test_api_product_import.py",
}

_PRODUCT_ARTIFACT_BOOTSTRAP_ENV = "BETELGEUZE_PRODUCT_TEST_ARTIFACT_BOOTSTRAP"
_PRODUCT_ARTIFACT_BOOTSTRAP_MODES = frozenset({"auto", "required", "disabled"})
_PRODUCT_ARTIFACT_BOOTSTRAP_OPTION = "product_contract_artifacts"
_PRODUCT_ARTIFACT_MARKER = "product_contract_artifacts"


def pytest_addoption(parser) -> None:
    group = parser.getgroup("betelgeuze-product")
    group.addoption(
        "--product-contract-artifacts",
        action="store_true",
        dest=_PRODUCT_ARTIFACT_BOOTSTRAP_OPTION,
        default=False,
        help=(
            "Materialize product contract packets before test collection. "
            "Focused unit and scientific suites remain disabled by default."
        ),
    )


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        (
            f"{_PRODUCT_ARTIFACT_MARKER}: request the session-scoped product "
            "contract artifact fixture for this test"
        ),
    )


def _product_artifact_bootstrap_mode() -> str:
    raw = os.getenv(_PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "disabled")
    mode = raw.strip().lower()
    if mode not in _PRODUCT_ARTIFACT_BOOTSTRAP_MODES:
        allowed = ", ".join(sorted(_PRODUCT_ARTIFACT_BOOTSTRAP_MODES))
        raise pytest.UsageError(
            f"{_PRODUCT_ARTIFACT_BOOTSTRAP_ENV} must be one of: {allowed}"
        )
    return mode


def _product_artifact_option_requested(config) -> bool:
    getter = getattr(config, "getoption", None)
    if getter is None:
        return False
    try:
        return bool(getter(_PRODUCT_ARTIFACT_BOOTSTRAP_OPTION))
    except (LookupError, ValueError):
        return False


def _product_artifact_bootstrap_required(config) -> bool:
    mode = _product_artifact_bootstrap_mode()
    if mode == "required":
        return True
    if mode == "disabled":
        return False
    return _product_artifact_option_requested(config)


def _materialize_product_contract_artifacts() -> Path:
    root = Path(__file__).resolve().parents[1]
    capability = root / "runs" / "product_capability_surface_contract_current.json"
    if capability.exists():
        return capability
    from tools.product.bootstrap_api_worker_contract_artifacts import materialize

    materialize()
    if not capability.is_file():
        raise pytest.UsageError(
            "product contract artifact bootstrap completed without the "
            "capability surface packet"
        )
    return capability


def pytest_sessionstart(session) -> None:
    if _product_artifact_bootstrap_required(session.config):
        _materialize_product_contract_artifacts()


@pytest.fixture(scope="session")
def product_contract_artifacts() -> Path:
    """Explicit fixture for tests that consume bootstrapped product packets."""

    return _materialize_product_contract_artifacts()


@pytest.fixture(autouse=True)
def _bootstrap_marked_product_contract_artifacts(request):
    marker = request.node.get_closest_marker(_PRODUCT_ARTIFACT_MARKER)
    if marker is not None:
        request.getfixturevalue("product_contract_artifacts")


def pytest_collection_modifyitems(config, items) -> None:
    if not os.getenv("GITHUB_ACTIONS"):
        return
    skip = pytest.mark.skip(
        reason=(
            "Integration test requires the full local runs/ artifact tree; "
            "CI bootstraps contract packets only."
        )
    )
    for item in items:
        if any(name in str(item.fspath) for name in _CI_INTEGRATION_FILES):
            item.add_marker(skip)
