from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_round23",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_requires_reference_pocket_source_and_release_lanes() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    required = set(checker.TARGET_WORKFLOWS)
    assert {
        "ci-engine-v2-reference-pocket-round22.yml",
        "ci-engine-v2-reference-pocket-release-round23.yml",
        "ci-engine-v2-top-stack.yml",
    }.issubset(required)


def test_top_stack_runs_reference_pocket_and_release_contracts() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    trigger = source.split("permissions:", 1)[0]
    assert "  pull_request:\n" in trigger
    assert '  push:\n    branches: ["main"]\n' in trigger
    assert "paths:" not in trigger
    assert "paths-ignore:" not in trigger
    assert "test_engine_v2_reference_pocket_round22.py" in source
    assert "test_engine_v2_reference_pocket_release_round23.py" in source


def test_installed_reference_pocket_lane_runs_the_full_command_chain() -> None:
    source = (
        ROOT
        / ".github"
        / "workflows"
        / "ci-engine-v2-reference-pocket-release-round23.yml"
    ).read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in source
    assert "persist-credentials: false" in source
    assert "Build two byte-identical wheels" in source
    assert 'cmp "$wheel_a" "$wheel_b"' in source
    assert "pip check" in source
    assert "pocket-from-reference" in source
    assert "dock-canonical" in source
    assert "verify-result" in source
    for field in (
        "derivation_receipt_sha256",
        "ligand_artifact_sha256",
        "pocket_artifact_sha256",
        "canonical_bytes_verified",
        "nested_receipts_verified",
        "generic_search_fingerprint_fully_recomputed",
        "generic_search_fingerprint_crosslinked",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert field in source


def test_reference_pocket_release_workflows_remain_read_only() -> None:
    for filename in (
        "ci-engine-v2-reference-pocket-round22.yml",
        "ci-engine-v2-reference-pocket-release-round23.yml",
        "ci-engine-v2-top-stack.yml",
    ):
        source = (ROOT / ".github" / "workflows" / filename).read_text(
            encoding="utf-8"
        )
        assert "permissions:\n  contents: read" in source
        assert "persist-credentials: false" in source
        assert "contents: write" not in source
        assert "actions: write" not in source
