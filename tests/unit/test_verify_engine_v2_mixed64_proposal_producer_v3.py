from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_mixed64_proposal_producer_v3 import (
    DEFAULT_POLICY_PATH,
    Mixed64ProposalProducerPolicyVerificationError,
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


def test_current_policy_verifies_without_authority() -> None:
    result = verify_policy()
    assert result["verified"] is True
    assert result["verification_blockers"] == []
    assert result["activation_evidence_eligible"] is False
    assert result["producer_attested"] is False
    assert result["molecular_execution_authorized"] is False


def test_denominator_or_authority_tamper_fails_closed(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    document["candidate_denominator"] = 63
    path = tmp_path / "denominator.json"
    _write(path, document)
    with pytest.raises(Mixed64ProposalProducerPolicyVerificationError):
        verify_policy(path)

    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    document["authority"]["molecular_execution_authorized"] = True
    path = tmp_path / "authority.json"
    _write(path, document)
    with pytest.raises(Mixed64ProposalProducerPolicyVerificationError):
        verify_policy(path)


def test_noncanonical_policy_fails_closed(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    path = tmp_path / "pretty.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="ascii")
    with pytest.raises(
        Mixed64ProposalProducerPolicyVerificationError,
        match="not canonical",
    ):
        verify_policy(path)


def test_cli_runs_in_isolated_mode_outside_repository(tmp_path: Path) -> None:
    tool = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "verify_engine_v2_mixed64_proposal_producer_v3.py"
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
    assert result["producer_attested"] is False
