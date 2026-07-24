from __future__ import annotations

import importlib.util
from pathlib import Path

from betelgeuze_engine_v2 import (
    DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID,
    DOCKING_SEARCH_RESULT_SCHEMA_ID,
    SEARCH_FINGERPRINT_MATERIAL_SHA256,
    recompute_search_fingerprint_sha256,
)


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_round21",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_requires_recomputable_search_identity_workflow() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    assert "ci-engine-v2-search-fingerprint-material-round20.yml" in set(
        checker.TARGET_WORKFLOWS
    )


def test_public_search_identity_api_is_packaged_and_versioned() -> None:
    assert DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID.endswith("/6.0.0")
    assert DOCKING_SEARCH_RESULT_SCHEMA_ID.endswith("/2.0.0")
    assert len(SEARCH_FINGERPRINT_MATERIAL_SHA256) == 64
    assert recompute_search_fingerprint_sha256.__module__.startswith(
        "betelgeuze_engine_v2."
    )


def test_top_stack_runs_search_material_and_release_contracts() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    trigger = source.split("permissions:", 1)[0]
    assert "  pull_request:\n" in trigger
    assert '  push:\n    branches: ["main"]\n' in trigger
    assert "paths:" not in trigger
    assert "paths-ignore:" not in trigger
    assert "test_engine_v2_search_fingerprint_material_round20.py" in source
    assert "test_engine_v2_search_fingerprint_release_round21.py" in source


def test_installed_verifier_requires_full_search_fingerprint_recomputation() -> None:
    source = (
        ROOT
        / ".github"
        / "workflows"
        / "ci-engine-v2-cli-result-verifier-package-round19.yml"
    ).read_text(encoding="utf-8")
    assert (
        'verification["generic_search_fingerprint_fully_recomputed"] is True'
        in source
    )
    assert (
        'verification["generic_search_fingerprint_crosslinked"] is True'
        in source
    )
    assert "Build two byte-identical wheels" in source
    assert "dock-canonical" in source
    assert "verify-result" in source


def test_search_identity_release_workflows_remain_read_only() -> None:
    for filename in (
        "ci-engine-v2-search-fingerprint-material-round20.yml",
        "ci-engine-v2-cli-result-verifier-package-round19.yml",
        "ci-engine-v2-top-stack.yml",
    ):
        source = (ROOT / ".github" / "workflows" / filename).read_text(
            encoding="utf-8"
        )
        assert "permissions:\n  contents: read" in source
        assert "persist-credentials: false" in source
        assert "contents: write" not in source
        assert "actions: write" not in source
