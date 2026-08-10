from __future__ import annotations

import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2  # noqa: F401
import tools.verify_engine_v2_standalone_scientific_consumer_activation_v3 as verifier
from tools.verify_engine_v2_standalone_scientific_consumer_activation_v3 import (
    StandaloneScientificConsumerActivationVerificationError,
    verify_policy,
)


def test_exact_consumer_activation_routes_verify() -> None:
    result = verify_policy()

    assert result["verified"] is True
    assert result["verification_blockers"] == []
    assert result["same_core_receipt_route_verified"] is True
    assert result["candidate_denominator"] == 64
    assert result["verified_surfaces"] == [
        "canonical_pipeline",
        "cli",
        "python_api",
        "diagnostic_benchmark",
        "product_shadow",
    ]
    assert result["rank_or_selection_rewrite_authorized"] is False
    assert result["product_or_molecular_execution_authorized"] is False
    assert result["reservation_allowed"] is False
    assert result["hip_execution_authorized"] is False


def test_policy_authority_and_canonical_tampering_fail_closed(
    tmp_path: Path,
) -> None:
    document = json.loads(verifier.DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    document["authority"]["product_execution_authorized"] = True
    tampered = tmp_path / "policy.json"
    tampered.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    with pytest.raises(
        StandaloneScientificConsumerActivationVerificationError,
        match="disagrees",
    ):
        verify_policy(tampered)

    noncanonical = tmp_path / "pretty.json"
    noncanonical.write_text(json.dumps(document, indent=2) + "\n", encoding="ascii")
    with pytest.raises(
        StandaloneScientificConsumerActivationVerificationError,
        match="not canonical",
    ):
        verify_policy(noncanonical)


def test_pipeline_duplicate_scientific_executor_call_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._PIPELINE_PATH.read_text(encoding="utf-8")
    needle = (
        "            recorded = "
        "execute_repository_synthetic_d0_standalone_scientific_core(\n"
        "                request\n"
        "            )"
    )
    replacement = (
        "            execute_repository_synthetic_d0_standalone_scientific_core(\n"
        "                request\n"
        "            )\n"
        + needle
    )
    assert source.count(needle) == 1
    tampered = tmp_path / "pipeline.py"
    tampered.write_text(source.replace(needle, replacement, 1), encoding="utf-8")
    monkeypatch.setattr(verifier, "_PIPELINE_PATH", tampered)

    with pytest.raises(
        StandaloneScientificConsumerActivationVerificationError,
        match="scientific route",
    ):
        verify_policy()


def test_consumer_pipeline_bypass_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._CONSUMERS_PATH.read_text(encoding="utf-8")
    needle = "    result = DockingPipeline().run(request)"
    assert source.count(needle) == 2
    tampered = tmp_path / "consumers.py"
    tampered.write_text(
        source.replace(
            needle,
            "    DockingPipeline().run(request)\n" + needle,
            1,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "_CONSUMERS_PATH", tampered)

    with pytest.raises(
        StandaloneScientificConsumerActivationVerificationError,
        match="call count changed",
    ):
        verify_policy()


def test_cli_duplicate_pipeline_call_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._CLI_PATH.read_text(encoding="utf-8")
    needle = "        return DockingPipeline().run(request).to_dict()"
    assert source.count(needle) == 1
    tampered = tmp_path / "standalone_cli.py"
    tampered.write_text(
        source.replace(
            needle,
            "        DockingPipeline().run(request)\n" + needle,
            1,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "_CLI_PATH", tampered)

    with pytest.raises(
        StandaloneScientificConsumerActivationVerificationError,
        match="CLI dock",
    ):
        verify_policy()
