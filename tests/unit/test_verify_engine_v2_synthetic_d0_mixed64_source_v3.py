from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import tools.verify_engine_v2_synthetic_d0_mixed64_source_v3 as verifier
from tools.verify_engine_v2_synthetic_d0_mixed64_source_v3 import (
    DEFAULT_POLICY_PATH,
    SyntheticD0Mixed64SourcePolicyVerificationError,
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


def test_current_policy_and_adapter_verify_without_authority() -> None:
    result = verify_policy()
    assert result["verified"] is True
    assert result["verification_blockers"] == []
    assert result["standalone_binding_ready"] is True
    assert result["standalone_activation_authorized"] is False
    assert result["molecular_execution_authorized"] is False
    assert result["reservation_allowed"] is False
    assert result["hip_execution_authorized"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("fixture", "candidate_denominator"), 63),
        (("fixture", "seed"), 4302),
        (("source_generation", "one_call"), False),
        (("source_generation", "result_dependent_retry_allowed"), True),
        (("source_generation", "retained_source_indices"), [36]),
        (("feature_extraction", "result_fields_consumed"), True),
        (("consumer_contract", "standalone_activation_authorized"), True),
        (("authority", "molecular_cohort_execution_authorized"), True),
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
    with pytest.raises(SyntheticD0Mixed64SourcePolicyVerificationError):
        verify_policy(candidate)


def test_noncanonical_policy_fails_closed(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    path = tmp_path / "pretty.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="ascii")
    with pytest.raises(
        SyntheticD0Mixed64SourcePolicyVerificationError,
        match="not canonical",
    ):
        verify_policy(path)


def test_adapter_with_authority_parameter_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._ADAPTER_PATH.read_text(encoding="utf-8")
    changed = source.replace(
        "    request: DockingPipelineRequestV1,\n)",
        "    request: DockingPipelineRequestV1,\n    authority: object = None,\n)",
        1,
    )
    assert changed != source
    path = tmp_path / "adapter.py"
    path.write_text(changed, encoding="utf-8")
    monkeypatch.setattr(verifier, "_ADAPTER_PATH", path)
    with pytest.raises(
        SyntheticD0Mixed64SourcePolicyVerificationError,
        match="gained allocation, result, or authority",
    ):
        verify_policy()


def test_adapter_duplicate_generator_call_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = verifier._ADAPTER_PATH.read_text(encoding="utf-8")
    needle = "    proposals, guided_receipt = generate_guided_docking_proposals(\n"
    changed = source.replace(
        needle,
        "    duplicate = generate_guided_docking_proposals(\n"
        "        authority, budget, context, receptor_system=prepared.receptor_system,\n"
        "        ligand_system=prepared.ligand_system, policy=guided_policy,\n"
        "    )\n"
        + needle,
        1,
    )
    assert changed != source
    path = tmp_path / "adapter.py"
    path.write_text(changed, encoding="utf-8")
    monkeypatch.setattr(verifier, "_ADAPTER_PATH", path)
    with pytest.raises(
        SyntheticD0Mixed64SourcePolicyVerificationError,
        match="call count",
    ):
        verify_policy()


def test_cli_runs_in_isolated_mode_outside_repository(tmp_path: Path) -> None:
    tool = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "verify_engine_v2_synthetic_d0_mixed64_source_v3.py"
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
    assert result["standalone_activation_authorized"] is False
