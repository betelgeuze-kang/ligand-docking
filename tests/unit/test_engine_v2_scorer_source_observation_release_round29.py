from __future__ import annotations

import importlib.util
from pathlib import Path

from betelgeuze_engine_v2 import (
    SCORER_SOURCE_OBSERVATION_MODE,
    SCORER_SOURCE_OBSERVATION_SCHEMA_ID,
    SCORER_SOURCE_OBSERVATION_SHA256,
    ScorerSourceObservationReceipt,
    SourceObservedInputBoundVerificationReceipt,
)
from betelgeuze_engine_v2.scorer_source_observation import (
    SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID,
)


ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "tools" / "check_engine_v2_top_stack.py"
    spec = importlib.util.spec_from_file_location(
        "engine_v2_top_stack_checker_round29",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_requires_source_observation_source_and_release_lanes() -> None:
    checker = _load_checker()
    assert checker.main() == 0
    required = set(checker.TARGET_WORKFLOWS)
    assert {
        "ci-engine-v2-scorer-source-observation-round28.yml",
        "ci-engine-v2-scorer-source-observation-release-round29.yml",
        "ci-engine-v2-input-bound-verifier-release-round25.yml",
        "ci-engine-v2-top-stack.yml",
    }.issubset(required)


def test_source_observation_api_is_public_and_explicitly_postimport() -> None:
    assert SCORER_SOURCE_OBSERVATION_SCHEMA_ID.endswith("/1.0.0")
    assert SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID.endswith("/1.0.0")
    assert SCORER_SOURCE_OBSERVATION_MODE.endswith("after_import")
    assert len(SCORER_SOURCE_OBSERVATION_SHA256) == 64
    assert ScorerSourceObservationReceipt.__module__.startswith(
        "betelgeuze_engine_v2."
    )
    assert SourceObservedInputBoundVerificationReceipt.__module__.startswith(
        "betelgeuze_engine_v2."
    )


def test_top_stack_runs_source_observation_and_release_contracts() -> None:
    source = (
        ROOT / ".github" / "workflows" / "ci-engine-v2-top-stack.yml"
    ).read_text(encoding="utf-8")
    trigger = source.split("permissions:", 1)[0]
    assert "  pull_request:\n" in trigger
    assert '  push:\n    branches: ["main"]\n' in trigger
    assert "paths:" not in trigger
    assert "paths-ignore:" not in trigger
    assert "test_engine_v2_scorer_source_observation_round28.py" in source
    assert "test_engine_v2_scorer_source_observation_release_round29.py" in source


def test_installed_bundle_lane_requires_observation_without_attestation_claim() -> None:
    source = (
        ROOT
        / ".github"
        / "workflows"
        / "ci-engine-v2-input-bound-verifier-release-round25.yml"
    ).read_text(encoding="utf-8")
    assert "Build two byte-identical wheels" in source
    assert 'cmp "$wheel_a" "$wheel_b"' in source
    assert "pip check" in source
    assert 'bundle["scorer_source_bytes_locally_observed"] is True' in source
    assert (
        'bundle["scorer_source_bytes_sha256_matched_result"] is True'
        in source
    )
    assert (
        'bundle["scorer_source_bytes_observed_after_import"] is True'
        in source
    )
    assert 'bundle["scorer_source_bytes_locally_attested"] is False' in source
    assert (
        'bundle["scorer_source_execution_preimport_attested"] is False'
        in source
    )
    assert 'bundle["scorer_source_signature_verified"] is False' in source
    assert "scorer_source_observation_receipt_sha256" in source
    assert 'document["scientifically_validated"] is False' in source
    assert 'document["benchmark_validated"] is False' in source
    assert 'document["product_qualified"] is False' in source
    assert 'document["customer_execution_enabled"] is False' in source
    assert 'document["claim_safe"] is False' in source


def test_source_observation_release_workflows_remain_read_only() -> None:
    for filename in (
        "ci-engine-v2-scorer-source-observation-round28.yml",
        "ci-engine-v2-scorer-source-observation-release-round29.yml",
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
