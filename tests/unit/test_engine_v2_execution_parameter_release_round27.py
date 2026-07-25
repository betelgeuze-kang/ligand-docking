from __future__ import annotations

import importlib.util
from pathlib import Path

from betelgeuze_engine_v2 import (
    ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID,
    CLI_EXECUTION_PARAMETERS_SCHEMA_ID,
    EXECUTION_PARAMETER_ATTESTATION_SHA256,
    AttestedInputBoundVerificationReceipt,
)


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_round27",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_requires_execution_attestation_source_and_release_lanes() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    required = set(checker.TARGET_WORKFLOWS)
    assert {
        "ci-engine-v2-execution-parameter-attestation-round26.yml",
        "ci-engine-v2-execution-parameter-release-round27.yml",
        "ci-engine-v2-input-bound-verifier-release-round25.yml",
        "ci-engine-v2-top-stack.yml",
    }.issubset(required)


def test_execution_attestation_api_is_public_and_versioned() -> None:
    assert CLI_EXECUTION_PARAMETERS_SCHEMA_ID.endswith("/1.0.0")
    assert ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID.endswith("/2.0.0")
    assert len(EXECUTION_PARAMETER_ATTESTATION_SHA256) == 64
    assert AttestedInputBoundVerificationReceipt.__module__.startswith(
        "betelgeuze_engine_v2."
    )


def test_top_stack_runs_execution_attestation_and_release_contracts() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    trigger = source.split("permissions:", 1)[0]
    assert "  pull_request:\n" in trigger
    assert '  push:\n    branches: ["main"]\n' in trigger
    assert "paths:" not in trigger
    assert "paths-ignore:" not in trigger
    assert "test_engine_v2_execution_parameter_attestation_round26.py" in source
    assert "test_engine_v2_execution_parameter_release_round27.py" in source


def test_installed_input_bound_lane_requires_unique_parameter_attestation() -> None:
    source = (
        ROOT
        / ".github"
        / "workflows"
        / "ci-engine-v2-input-bound-verifier-release-round25.yml"
    ).read_text(encoding="utf-8")
    assert "Build two byte-identical wheels" in source
    assert 'cmp "$wheel_a" "$wheel_b"' in source
    assert "pip check" in source
    assert "execution_parameters" in source
    assert "execution_parameters_receipt_sha256" in source
    assert 'bundle["execution_parameters_fully_verified"] is True' in source
    assert 'bundle["receptor_margin_uniquely_attested"] is True' in source
    assert 'bundle["model_indices_uniquely_attested"] is True' in source
    assert 'bundle["scorer_source_bytes_locally_attested"] is False' in source
    assert 'document["scientifically_validated"] is False' in source
    assert 'document["benchmark_validated"] is False' in source
    assert 'document["product_qualified"] is False' in source
    assert 'document["customer_execution_enabled"] is False' in source
    assert 'document["claim_safe"] is False' in source


def test_execution_parameter_release_workflows_remain_read_only() -> None:
    for filename in (
        "ci-engine-v2-execution-parameter-attestation-round26.yml",
        "ci-engine-v2-execution-parameter-release-round27.yml",
        "ci-engine-v2-input-bound-verifier-release-round25.yml",
        "ci-engine-v2-top-stack.yml",
    ):
        source = (ROOT / ".github" / "workflows" / filename).read_text(
            encoding="utf-8"
        )
        assert "permissions:\n  contents: read" in source
        assert "persist-credentials: false" in source
        assert "contents: write" not in source
        assert "actions: write" not in source
