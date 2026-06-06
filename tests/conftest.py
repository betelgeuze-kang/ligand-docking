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


def pytest_sessionstart(session) -> None:
    root = Path(__file__).resolve().parents[1]
    capability = root / "runs" / "product_capability_surface_contract_current.json"
    if capability.exists():
        return
    from tools.product.bootstrap_api_worker_contract_artifacts import materialize

    materialize()


def pytest_collection_modifyitems(config, items) -> None:
    if not os.getenv("GITHUB_ACTIONS"):
        return
    skip = pytest.mark.skip(
        reason="Integration test requires the full local runs/ artifact tree; CI bootstraps contract packets only."
    )
    for item in items:
        if any(name in str(item.fspath) for name in _CI_INTEGRATION_FILES):
            item.add_marker(skip)
