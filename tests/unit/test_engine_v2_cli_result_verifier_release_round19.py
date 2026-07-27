from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_round19",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_requires_consolidated_verifier_and_package_lanes() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    assert {"ci-engine-v2-package.yml", "ci-engine-v2-top-stack.yml"}.issubset(
        set(checker.TARGET_WORKFLOWS)
    )
    for filename in (
        "ci-engine-v2-cli-result-verifier-round18.yml",
        "ci-engine-v2-cli-result-verifier-package-round19.yml",
    ):
        assert filename in checker.REDUNDANT_STACK_WORKFLOWS
        assert not (ROOT / ".github" / "workflows" / filename).exists()


def test_top_stack_runs_verifier_and_release_contracts() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    trigger = source.split("permissions:", 1)[0]
    assert "  pull_request:\n" in trigger
    assert '  push:\n    branches: ["main"]\n' in trigger
    assert "paths:" not in trigger
    assert "paths-ignore:" not in trigger
    assert "test_engine_v2_cli_result_verifier_round18.py" in source
    assert "test_engine_v2_cli_result_verifier_release_round19.py" in source


def test_package_verifier_lane_builds_and_executes_both_commands() -> None:
    source = (
        ROOT
        / ".github"
        / "workflows"
        / "ci-engine-v2-package.yml"
    ).read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in source
    assert "persist-credentials: false" in source
    assert "Build two byte-identical Engine v2 wheels" in source
    assert "cmp \"$wheel_a\" \"$wheel_b\"" in source
    assert "pip check" in source
    assert "dock-canonical" in source
    assert "verify-result" in source
    for field in (
        "canonical_bytes_verified",
        "nested_receipts_verified",
        "failure_denominator_verified",
        "generic_search_fingerprint_fully_recomputed",
        "generic_search_fingerprint_crosslinked",
        "calibrated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert field in source


def test_verifier_release_workflows_remain_read_only() -> None:
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
