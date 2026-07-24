from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_round7",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_checker_accepts_the_exact_repository_stack() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    required = set(checker.TARGET_WORKFLOWS)
    assert {
        "ci-engine-v2-correctness-round1.yml",
        "ci-engine-v2-evaluator-round2.yml",
        "ci-engine-v2-molecular-round3.yml",
        "ci-engine-v2-docking-authority-round4.yml",
        "ci-engine-v2-package.yml",
        "ci-engine-v2-release-integration-round5.yml",
        "ci-engine-v2-pocket-placement-round6.yml",
        "ci-engine-v2-top-stack.yml",
    }.issubset(required)


def test_top_stack_runs_on_pull_requests_and_exact_main_without_path_filters() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    trigger = source.split("permissions:", 1)[0]
    assert "  pull_request:\n" in trigger
    assert '  push:\n    branches: ["main"]\n' in trigger
    assert "  workflow_dispatch:\n" in trigger
    assert "paths:" not in trigger
    assert "paths-ignore:" not in trigger


def test_top_stack_explicitly_runs_round_one_through_round_six_contracts() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    for filename in (
        "test_engine_v2_stack_round1_hardening.py",
        "test_engine_v2_stack_round2_evaluator.py",
        "test_engine_v2_stack_round3_molecular.py",
        "test_engine_v2_stack_round3_compatibility.py",
        "test_engine_v2_docking_authority_contract.py",
        "test_engine_v2_docking_authority_search.py",
        "test_engine_v2_pocket_placement_round6.py",
        "test_engine_v2_release_integration_round5.py",
    ):
        assert filename in source


def test_package_lane_builds_two_identical_wheels_and_imports_authority_api() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-package.yml"
    ).read_text(encoding="utf-8")
    assert 'push:\n    branches: ["main"]' in source
    assert "Build two byte-identical Engine v2 wheels" in source
    assert "cmp \"$wheel_a\" \"$wheel_b\"" in source
    assert "sha256sum dist-engine-v2/*.whl" in source
    assert "pip check" in source
    assert "Import wheel outside checkout" in source
    for api_name in (
        "AuthenticatedDockingProblem",
        "PocketDefinition",
        "PocketPlacementPolicy",
        "PocketPlacementReceipt",
        "PocketPlacementSearchResult",
        "TorsionSearchSpaceDerivationReceipt",
    ):
        assert api_name in source


def test_release_workflows_remain_read_only_and_disable_checkout_credentials() -> None:
    for filename in (
        "ci-engine-v2-package.yml",
        "ci-engine-v2-release-integration-round5.yml",
        "ci-engine-v2-pocket-placement-round6.yml",
        "ci-engine-v2-top-stack.yml",
    ):
        source = (ROOT / ".github" / "workflows" / filename).read_text(
            encoding="utf-8"
        )
        assert "permissions:\n  contents: read" in source
        assert "persist-credentials: false" in source
        assert "contents: write" not in source
        assert "actions: write" not in source
