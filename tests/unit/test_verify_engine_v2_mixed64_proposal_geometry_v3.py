from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_mixed64_proposal_geometry_v3 import (
    DEFAULT_POLICY_PATH,
    Mixed64ProposalGeometryPolicyVerificationError,
    verify_policy,
)


def _write_policy(path: Path, document: object) -> None:
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


def test_canonical_policy_verifies_with_zero_authority() -> None:
    result = verify_policy()
    assert result["verified"] is True
    assert result["verification_blockers"] == []
    assert result["activation_evidence_eligible"] is False
    assert result["molecular_execution_authorized"] is False
    assert result["reservation_allowed"] is False


def test_policy_tamper_fails_closed(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    document["single_anchor"]["profiles"][0][
        "target_distance_angstrom_binary64_hex"
    ] = (3.1).hex()
    path = tmp_path / "tampered.json"
    _write_policy(path, document)

    with pytest.raises(
        Mixed64ProposalGeometryPolicyVerificationError,
        match="disagrees",
    ):
        verify_policy(path)


def test_authority_cannot_be_enabled(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    document["authority"]["molecular_execution_authorized"] = True
    path = tmp_path / "authority.json"
    _write_policy(path, document)

    with pytest.raises(Mixed64ProposalGeometryPolicyVerificationError):
        verify_policy(path)


def test_noncanonical_json_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "pretty.json"
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="ascii")

    with pytest.raises(
        Mixed64ProposalGeometryPolicyVerificationError,
        match="not canonical",
    ):
        verify_policy(path)


def test_cli_runs_from_outside_repository(tmp_path: Path) -> None:
    tool = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "verify_engine_v2_mixed64_proposal_geometry_v3.py"
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
    assert result["activation_evidence_eligible"] is False
