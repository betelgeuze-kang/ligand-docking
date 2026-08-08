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

_LIGHTWEIGHT_CONTRACT_FILES = {
    "test_release_claim_evidence_ladder_gate.py",
    "test_product_docking_response_snapshot.py",
    "test_benchmark_contract.py",
    "test_api_h4_security_hardening.py",
    "test_api_job_store.py",
    "test_api_security_middleware.py",
    "test_api_worker_deploy_artifacts.py",
}

_PRODUCT_ARTIFACT_BOOTSTRAP_ENV = "BETELGEUZE_PRODUCT_TEST_ARTIFACT_BOOTSTRAP"
_PRODUCT_ARTIFACT_BOOTSTRAP_MODES = frozenset({"auto", "required", "disabled"})


def _requested_tests_are_lightweight(config) -> bool:
    args = [str(arg).split("::", 1)[0] for arg in getattr(config, "args", []) or []]
    if not args:
        return False
    root = Path(__file__).resolve().parents[1]
    for text in args:
        candidate = Path(text)
        if candidate.name in _LIGHTWEIGHT_CONTRACT_FILES:
            continue
        try:
            relative = candidate.resolve().relative_to(root)
        except (OSError, ValueError):
            return False
        if relative.parts[:2] == ("tests", "mobile"):
            continue
        return False
    return True


def _product_artifact_bootstrap_mode() -> str:
    raw = os.getenv(_PRODUCT_ARTIFACT_BOOTSTRAP_ENV, "auto")
    mode = raw.strip().lower()
    if mode not in _PRODUCT_ARTIFACT_BOOTSTRAP_MODES:
        allowed = ", ".join(sorted(_PRODUCT_ARTIFACT_BOOTSTRAP_MODES))
        raise pytest.UsageError(
            f"{_PRODUCT_ARTIFACT_BOOTSTRAP_ENV} must be one of: {allowed}"
        )
    return mode


def _product_artifact_bootstrap_required(config) -> bool:
    mode = _product_artifact_bootstrap_mode()
    if mode == "disabled":
        return False
    if mode == "required":
        return True
    return not _requested_tests_are_lightweight(config)


def pytest_sessionstart(session) -> None:
    if not _product_artifact_bootstrap_required(session.config):
        return
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
