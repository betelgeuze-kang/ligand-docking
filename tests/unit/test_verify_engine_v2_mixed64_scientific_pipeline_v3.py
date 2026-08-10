from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import tools.verify_engine_v2_mixed64_scientific_pipeline_v3 as verifier
from tools.verify_engine_v2_mixed64_scientific_pipeline_v3 import (
    DEFAULT_POLICY_PATH,
    Mixed64ScientificPipelinePolicyVerificationError,
    verify_policy,
)


def _write(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n",
        encoding="ascii",
    )


def test_current_policy_and_exact_executor_verify_without_authority() -> None:
    result = verify_policy()
    assert result["verified"] is True
    assert result["verification_blockers"] == []
    assert result["canonical_scientific_core_receipt"] is True
    assert result["activation_evidence_eligible"] is False
    assert result["molecular_execution_authorized"] is False
    assert result["reservation_allowed"] is False
    assert result["hip_execution_authorized"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("candidate_denominator",), 63),
        (("execution_order",), ["scorer_v1_validity_stable_ranking"]),
        (("execution_semantics", "one_call_per_stage"), False),
        (("execution_semantics", "caller_allocation_allowed"), True),
        (("failure_semantics", "failed_or_rejected_slot_deleted"), True),
        (("consumer_contract", "api_consumer_activation_authorized"), True),
        (("authority", "molecular_cohort_execution_authorized"), True),
        (("authority", "hip_execution_authorized"), True),
    ),
)
def test_policy_tamper_fails_closed(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    candidate = tmp_path / "tampered.json"
    _write(candidate, document)
    with pytest.raises(Mixed64ScientificPipelinePolicyVerificationError):
        verify_policy(candidate)


def test_noncanonical_policy_fails_closed(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    path = tmp_path / "pretty.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="ascii")
    with pytest.raises(
        Mixed64ScientificPipelinePolicyVerificationError,
        match="not canonical",
    ):
        verify_policy(path)


def test_executor_with_caller_allocation_parameter_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._EXECUTOR_PATH.read_text(encoding="utf-8")
    changed = source.replace(
        "    source_bundle: Mixed64ProposalSourceBundleV1,\n    *,",
        "    source_bundle: Mixed64ProposalSourceBundleV1,\n"
        "    allocation: object = None,\n    *,",
        1,
    )
    assert changed != source
    path = tmp_path / "executor.py"
    path.write_text(changed, encoding="utf-8")
    monkeypatch.setattr(verifier, "_EXECUTOR_PATH", path)
    with pytest.raises(
        Mixed64ScientificPipelinePolicyVerificationError,
        match="gained result, tuning, or authority",
    ):
        verify_policy()


def test_executor_duplicate_stage_call_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._EXECUTOR_PATH.read_text(encoding="utf-8")
    needle = "    producer_batch = produce_fixed_mixed64_proposals(\n"
    changed = source.replace(
        needle,
        "    duplicate = produce_fixed_mixed64_proposals(\n"
        "        source_bundle.allocation, source_bundle=source_bundle\n"
        "    )\n"
        + needle,
        1,
    )
    assert changed != source
    path = tmp_path / "executor.py"
    path.write_text(changed, encoding="utf-8")
    monkeypatch.setattr(verifier, "_EXECUTOR_PATH", path)
    with pytest.raises(
        Mixed64ScientificPipelinePolicyVerificationError,
        match="stage order or call count",
    ):
        verify_policy()


def test_cli_runs_in_isolated_mode_outside_repository(tmp_path: Path) -> None:
    tool = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "verify_engine_v2_mixed64_scientific_pipeline_v3.py"
    )
    completed = subprocess.run(
        [sys.executable, "-I", str(tool)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["verified"] is True
    assert result["molecular_execution_authorized"] is False
