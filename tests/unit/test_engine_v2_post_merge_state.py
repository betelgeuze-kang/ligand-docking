from __future__ import annotations

from pathlib import Path

import pytest


yaml = pytest.importorskip("yaml")

from betelgeuze_engine_v2.capabilities import (
    CAPABILITY_SCHEMA_VERSION,
    IMPLEMENTATION_STAGE,
    capability_snapshot,
    require_capability_snapshot,
)


def test_capability_yaml_matches_executable_v2_g_snapshot() -> None:
    path = Path("config/independent_engine_v2_capabilities.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded == capability_snapshot()
    assert loaded["schema_version"] == CAPABILITY_SCHEMA_VERSION == 3
    assert loaded["implementation_stage"] == IMPLEMENTATION_STAGE
    assert len(loaded["capabilities"]) == 7
    assert all(row["implemented"] is True for row in loaded["capabilities"].values())
    assert all(row["claim_safe"] is False for row in loaded["capabilities"].values())
    assert all(row["customer_execution_enabled"] is False for row in loaded["capabilities"].values())
    require_capability_snapshot(loaded)


def test_engine_v2_status_and_public_api_docs_state_non_promotion_boundary() -> None:
    status = Path("docs/engine_v2_status.md").read_text(encoding="utf-8")
    policy = Path("docs/engine_v2_public_api.md").read_text(encoding="utf-8")
    entrypoints = Path("docs/entrypoints.md").read_text(encoding="utf-8")

    assert IMPLEMENTATION_STAGE in status
    assert "implemented scaffold" in status
    assert "scientifically validated method" in status
    assert "Stable within an Engine API major version" in policy
    assert "Provisional submodule APIs" in policy
    assert "Independent Engine v2 reviewer" in entrypoints


def test_readmes_describe_conditional_complexity_and_v2_quick_start() -> None:
    english = Path("README.md").read_text(encoding="utf-8")
    korean = Path("README.ko.md").read_text(encoding="utf-8")

    assert "conditional bounded-degree" in english
    assert "betelgeuze-engine-v2" in english
    assert "docs/engine_v2_status.md" in english
    assert "조건부 제한 차수" in korean
    assert "betelgeuze-engine-v2" in korean
    assert "docs/engine_v2_status.md" in korean


def test_main_integration_workflow_targets_main_and_complete_v2_suite() -> None:
    source = Path(".github/workflows/ci-engine-v2-main.yml").read_text(encoding="utf-8")
    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    for test_file in (
        "test_engine_v2_contracts_molecular.py",
        "test_engine_v2_sparse_geometry_features.py",
        "test_engine_v2_ai_core.py",
        "test_engine_v2_periodic_energy.py",
        "test_engine_v2_orchestrator_contract.py",
        "test_engine_v2_runtime_checkpoint_contracts.py",
        "test_engine_v2_packaging_guards.py",
        "test_engine_v2_bounded_scaffolds.py",
        "test_engine_v2_post_merge_state.py",
        "test_engine_v2_docking_semantics.py",
    ):
        assert test_file in source
    assert "pip check" in source
    assert "check_engine_v2_architecture.py" in source
