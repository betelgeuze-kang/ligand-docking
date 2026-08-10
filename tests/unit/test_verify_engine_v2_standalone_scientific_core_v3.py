from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.verify_engine_v2_standalone_scientific_core_v3 as verifier
from tools.verify_engine_v2_standalone_scientific_core_v3 import (
    StandaloneScientificCorePolicyVerificationError,
    verify_policy,
)


def test_canonical_policy_and_executor_verify() -> None:
    result = verify_policy()

    assert result["verified"] is True
    assert result["verification_blockers"] == []
    assert result["candidate_denominator"] == 64
    assert result["complete_scoring_validity_rank_receipt"] is True
    assert result["canonical_pipeline_activation_authorized"] is False
    assert result["molecular_execution_authorized"] is False
    assert result["reservation_allowed"] is False


def test_noncanonical_and_authority_tampering_fail_closed(tmp_path: Path) -> None:
    document = json.loads(verifier.DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    document["authority"]["reservation_allowed"] = True
    tampered = tmp_path / "policy.json"
    tampered.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        StandaloneScientificCorePolicyVerificationError,
        match="disagrees",
    ):
        verify_policy(tampered)

    noncanonical = tmp_path / "pretty.json"
    noncanonical.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(
        StandaloneScientificCorePolicyVerificationError,
        match="not canonical",
    ):
        verify_policy(noncanonical)


def test_executor_api_and_call_count_tampering_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._EXECUTOR_PATH.read_text(encoding="utf-8")
    parameter_tamper = tmp_path / "parameter.py"
    parameter_tamper.write_text(
        source.replace(
            "request: DockingPipelineRequestV1,\n) -> StandaloneScientificCoreReceiptV1:",
            "request: DockingPipelineRequestV1,\n    *, allocation: object = None,\n) -> StandaloneScientificCoreReceiptV1:",
            1,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "_EXECUTOR_PATH", parameter_tamper)
    with pytest.raises(
        StandaloneScientificCorePolicyVerificationError,
        match="API changed",
    ):
        verify_policy()

    duplicate_call = tmp_path / "duplicate.py"
    duplicate_call.write_text(
        source.replace(
            "source = build_repository_synthetic_d0_mixed64_source(request)",
            "source = build_repository_synthetic_d0_mixed64_source(request)\n"
            "    build_repository_synthetic_d0_mixed64_source(request)",
            1,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "_EXECUTOR_PATH", duplicate_call)
    with pytest.raises(
        StandaloneScientificCorePolicyVerificationError,
        match="call order or call count",
    ):
        verify_policy()


def test_required_receipt_binding_removal_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._EXECUTOR_PATH.read_text(encoding="utf-8")
    tampered = tmp_path / "receipt.py"
    tampered.write_text(
        source.replace(
            '"complete_pose_validity_preserved": True,',
            '"complete_pose_validity_removed": True,',
            1,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "_EXECUTOR_PATH", tampered)
    with pytest.raises(
        StandaloneScientificCorePolicyVerificationError,
        match="lost required evidence",
    ):
        verify_policy()
