from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_mixed64_v7_post_admission_v3 import (
    DEFAULT_POLICY_PATH,
    Mixed64V7PostAdmissionPolicyVerificationError,
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


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("candidate_denominator",), 63),
        (("receipt_integrity", "maximum_canonical_bytes"), 64 * 1024 * 1024),
        (("operational_input_integrity", "recursive_preflight_required"), False),
        (("output_live_integrity", "recursive_finalization_required"), False),
        (("refinement", "max_steps"), 25),
        (("refinement", "result_dependent_retry_allowed"), True),
        (
            (
                "post_refinement_geometric_admission",
                "hard_rejection_threshold_binary64_hex",
            ),
            (0.50).hex(),
        ),
        (
            (
                "post_refinement_geometric_admission",
                "geometric_admission_v3_policy_sha256",
            ),
            "0" * 64,
        ),
        (("failure_semantics", "typed_refinement_failure_reason_preserved"), False),
        (("failure_semantics", "slot_reallocation_allowed"), True),
        (("failure_semantics", "unexpected_runtime_failure_typed"), True),
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

    with pytest.raises(Mixed64V7PostAdmissionPolicyVerificationError):
        verify_policy(candidate)


def test_noncanonical_policy_fails_closed(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="ascii"))
    path = tmp_path / "pretty.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="ascii")
    with pytest.raises(
        Mixed64V7PostAdmissionPolicyVerificationError,
        match="not canonical",
    ):
        verify_policy(path)


def test_cli_runs_in_isolated_mode_outside_repository(tmp_path: Path) -> None:
    tool = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "verify_engine_v2_mixed64_v7_post_admission_v3.py"
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


def test_verifier_import_does_not_poison_canonical_package(tmp_path: Path) -> None:
    tool = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "verify_engine_v2_mixed64_v7_post_admission_v3.py"
    )
    script = """
import importlib.util
import pathlib
import sys

tool = pathlib.Path(sys.argv[1])
assert "betelgeuze_engine_v2" not in sys.modules
spec = importlib.util.spec_from_file_location("isolated_v7_verifier", tool)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
assert "betelgeuze_engine_v2" not in sys.modules
assert "betelgeuze_engine_v2.docking" not in sys.modules
assert module.verify_policy()["verified"] is True
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script, str(tool)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
