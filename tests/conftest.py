from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pytest

_CI_INTEGRATION_FILES = {
    "test_api_goal_import.py",
    "test_api_casp17_import.py",
    "test_api_cleanup_import.py",
    "test_api_product_import.py",
}

_PRODUCT_ARTIFACT_BOOTSTRAP_ENV = "BETELGEUZE_PRODUCT_TEST_ARTIFACT_BOOTSTRAP"
_PRODUCT_ARTIFACT_BOOTSTRAP_MODES = frozenset({"auto", "required", "disabled"})
_PRODUCT_ARTIFACT_MARKER = "product_artifacts"
_PRODUCT_CAPABILITY_FILENAME = "product_capability_surface_contract_current.json"


def _product_artifact_bootstrap_mode() -> str:
    raw = os.getenv(_PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "auto")
    mode = raw.strip().lower()
    if mode not in _PRODUCT_ARTIFACT_BOOTSTRAP_MODES:
        allowed = ", ".join(sorted(_PRODUCT_ARTIFACT_BOOTSTRAP_MODES))
        raise pytest.UsageError(
            f"{_PRODUCT_ARTIFACT_BOOTSTRAP_ENV} must be one of: {allowed}"
        )
    return mode


def _product_artifact_bootstrap_required(config=None) -> bool:
    """Return true only for an explicit dedicated product-test configuration.

    `auto` intentionally means no session-wide bootstrap. Product tests opt in
    through the marker/fixture below, while dedicated integration workflows may
    set the environment mode to `required`.
    """

    del config
    return _product_artifact_bootstrap_mode() == "required"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_product_contract_artifacts(
    *,
    root: Path | None = None,
    materializer: Callable[[], None] | None = None,
) -> Path:
    """Materialize product contract artifacts once and return their directory."""

    repository_root = (root or _repository_root()).resolve()
    runs_dir = repository_root / "runs"
    capability = runs_dir / _PRODUCT_CAPABILITY_FILENAME
    if capability.exists():
        if not capability.is_file():
            raise pytest.UsageError(
                "product capability artifact exists but is not a regular file"
            )
        return runs_dir

    if materializer is None:
        from tools.product.bootstrap_api_worker_contract_artifacts import (
            materialize,
        )

        materializer = materialize
    materializer()
    if not capability.is_file():
        raise pytest.UsageError(
            "explicit product artifact bootstrap did not create the "
            "capability contract"
        )
    return runs_dir


def _node_requests_product_artifacts(node) -> bool:
    return node.get_closest_marker(_PRODUCT_ARTIFACT_MARKER) is not None


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "product_artifacts: explicitly materialize product contract packets "
        "for this test",
    )


def pytest_sessionstart(session) -> None:
    if _product_artifact_bootstrap_required(session.config):
        _ensure_product_contract_artifacts()


@pytest.fixture(scope="session")
def product_contract_artifacts() -> Path:
    """Explicit session fixture for tests that consume generated product packets."""

    return _ensure_product_contract_artifacts()


@pytest.fixture(autouse=True)
def _materialize_product_artifacts_for_marked_test(request) -> None:
    if _node_requests_product_artifacts(request.node):
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
