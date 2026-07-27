from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_cut_c",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cut_c_checker_accepts_the_authoritative_repository_stack() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    assert set(checker.TARGET_WORKFLOWS) == {
        "ci-engine-v2-public-benchmark-protocol.yml",
        "ci-engine-v2-package.yml",
        "ci-engine-v2-top-stack.yml",
    }
    assert all(
        not (ROOT / ".github" / "workflows" / filename).exists()
        for filename in checker.REDUNDANT_STACK_WORKFLOWS
    )


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


def test_top_stack_explicitly_runs_all_reconstructed_cut_c_contracts() -> None:
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
        "test_engine_v2_element_contact_round8.py",
        "test_engine_v2_interpretable_scorer_round10.py",
        "test_engine_v2_interpretable_result_round12.py",
        "test_engine_v2_release_integration_cut_c.py",
    ):
        assert filename in source


def test_package_lane_builds_two_identical_wheels_and_imports_term_evidence_api() -> None:
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
        "ElementAwarePoseValidityContext",
        "ElementAwareValidityError",
        "InterpretablePoseScoreConfig",
        "InterpretablePoseScoreTerms",
        "InterpretablePoseScorerError",
        "InterpretablePoseScorerV0",
        "InterpretableScoredSearchResult",
        "InterpretableSearchResultError",
        "InterpretableSearchTermRow",
        "PocketDefinition",
        "PocketPlacementPolicy",
        "PocketPlacementReceipt",
        "PocketPlacementSearchResult",
        "TorsionSearchSpaceDerivationReceipt",
        "VdwContactPolicy",
        "build_element_aware_authenticated_known_pocket_docking_problem",
        "run_authenticated_interpretable_pocket_search",
    ):
        assert api_name in source


def test_release_workflows_remain_read_only_and_disable_checkout_credentials() -> None:
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
