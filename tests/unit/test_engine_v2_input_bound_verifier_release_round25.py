from __future__ import annotations

import importlib.util
from pathlib import Path

from betelgeuze_engine_v2.input_bound_verifier import (
    INPUT_BOUND_VERIFICATION_SCHEMA_ID,
    InputBoundVerificationReceipt,
    verify_input_bound_cli_bundle_bytes,
)


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_round25",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_consolidates_input_bound_release_workflows() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    assert {"ci-engine-v2-package.yml", "ci-engine-v2-top-stack.yml"}.issubset(
        set(checker.TARGET_WORKFLOWS)
    )
    for filename in (
        "ci-engine-v2-input-bound-verifier-round24.yml",
        "ci-engine-v2-input-bound-verifier-release-round25.yml",
    ):
        assert filename in checker.REDUNDANT_STACK_WORKFLOWS
        assert not (ROOT / ".github" / "workflows" / filename).exists()


def test_input_bound_verifier_api_is_publicly_packaged() -> None:
    assert INPUT_BOUND_VERIFICATION_SCHEMA_ID.endswith("/1.0.0")
    assert InputBoundVerificationReceipt.__module__.startswith(
        "betelgeuze_engine_v2."
    )
    assert verify_input_bound_cli_bundle_bytes.__module__.startswith(
        "betelgeuze_engine_v2."
    )


def test_top_stack_runs_input_bound_source_and_release_contracts() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    trigger = source.split("permissions:", 1)[0]
    assert "  pull_request:\n" in trigger
    assert '  push:\n    branches: ["main"]\n' in trigger
    assert "paths:" not in trigger
    assert "paths-ignore:" not in trigger
    assert "test_engine_v2_input_bound_verifier_round24.py" in source
    assert "test_engine_v2_input_bound_verifier_release_round25.py" in source


def test_installed_bundle_lane_runs_full_artifact_replay_chain() -> None:
    source = (
        ROOT
        / ".github"
        / "workflows"
        / "ci-engine-v2-package.yml"
    ).read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in source
    assert "persist-credentials: false" in source
    assert "Build two byte-identical Engine v2 wheels" in source
    assert 'cmp "$wheel_a" "$wheel_b"' in source
    assert "pip check" in source
    assert "pocket-from-reference" in source
    assert "dock-canonical" in source
    assert "verify-result" in source
    assert "verify-bundle" in source
    assert "--require-reference-pocket-derivation" in source
    for field in (
        "input_artifact_sha256s_verified",
        "pocket_definition_fully_recomputed",
        "reference_pocket_derivation_fully_recomputed",
        "authority_state_fully_recomputed",
        "scorer_contract_recomputed_from_declared_source_sha",
        "scorer_source_bytes_locally_attested",
        "search_fingerprint_fully_recomputed",
        "receptor_margin_uniquely_attested",
        "model_indices_uniquely_attested",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert field in source


def test_input_bound_release_workflows_remain_read_only() -> None:
    for filename in (
        "ci-engine-v2-package.yml",
        "ci-engine-v2-top-stack.yml",
    ):
        source = (ROOT / ".github" / "workflows" / filename).read_text(
            encoding="utf-8"
        )
        assert "permissions:\n  contents: read" in source
        assert "persist-credentials: false" in source
        assert "contents: write" not in source
        assert "actions: write" not in source
