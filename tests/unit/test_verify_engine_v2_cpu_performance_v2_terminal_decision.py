from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_cpu_performance_v2_terminal_decision import (
    CPUPerformanceTerminalDecisionError,
    verify_terminal_decision,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DECISION_PATH = (
    _REPO_ROOT / "config/engine_v2_cpu_performance_v2_terminal_decision.json"
)
_TOOL_PATH = (
    _REPO_ROOT
    / "tools/verify_engine_v2_cpu_performance_v2_terminal_decision.py"
)


def _document() -> dict[str, object]:
    return json.loads(_DECISION_PATH.read_text(encoding="ascii"))


def _write_canonical(path: Path, document: object) -> None:
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


def test_current_v2_terminal_decision_is_consumed_and_fail_closed() -> None:
    result = verify_terminal_decision()
    raw = _DECISION_PATH.read_bytes()

    assert result == {
        "artifact_structurally_replayed": False,
        "authority": {
            "fresh_holdout_execution_authorized": False,
            "historical_ab_execution_authorized": False,
            "molecular_execution_authorized": False,
            "product_performance_claim_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "stage0_admission_authorized": False,
        },
        "decision_record_sha256": hashlib.sha256(raw).hexdigest(),
        "execution_attested": False,
        "implementation_commit_oid": (
            "33bb355ef2d6e7fea7f4f6b796806e12e5acb70a"
        ),
        "profile_id": "engine_v2_ryzen_5900x_geometric_kernel_synthetic_v2",
        "profile_sha256": (
            "1d6d3da4dc1d3d0a2734cd2a19ee45409e105fe67c3bc6518b3df566d86b7560"
        ),
        "qualification_consumed": True,
        "rerun_allowed": False,
        "terminal_decision": "BLOCKED",
        "terminal_record_verified": True,
        "verification_blockers": ["owner_local_artifact_not_supplied"],
    }

    completed = subprocess.run(
        [sys.executable, str(_TOOL_PATH)],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == result


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("disposition", "qualification_consumed"), False),
        (("disposition", "rerun_allowed"), True),
        (("disposition", "terminal_decision"), "NO_GO"),
        (("execution", "blockers"), []),
        (("execution", "transcript_row_count"), 1),
        (("artifact", "sha256"), "0" * 64),
        (("authority", "molecular_execution_authorized"), True),
    ),
)
def test_terminal_decision_tamper_fails_closed(
    tmp_path: Path,
    path: tuple[str, str],
    replacement: object,
) -> None:
    changed = copy.deepcopy(_document())
    changed[path[0]][path[1]] = replacement  # type: ignore[index]
    decision_path = tmp_path / "decision.json"
    _write_canonical(decision_path, changed)

    with pytest.raises(
        CPUPerformanceTerminalDecisionError,
        match="terminal decision changed",
    ):
        verify_terminal_decision(decision_path=decision_path)


def test_noncanonical_or_duplicate_terminal_decision_fails_closed(
    tmp_path: Path,
) -> None:
    pretty = tmp_path / "pretty.json"
    pretty.write_text(json.dumps(_document(), indent=2) + "\n", encoding="ascii")
    with pytest.raises(CPUPerformanceTerminalDecisionError, match="canonical"):
        verify_terminal_decision(decision_path=pretty)

    duplicate = tmp_path / "duplicate.json"
    raw = _DECISION_PATH.read_text(encoding="ascii")
    duplicate.write_text(
        raw.replace("{", '{"schema_id":"duplicate",', 1),
        encoding="ascii",
    )
    with pytest.raises(CPUPerformanceTerminalDecisionError, match="duplicate"):
        verify_terminal_decision(decision_path=duplicate)


def test_wrong_retained_artifact_fails_before_replay(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}\n", encoding="ascii")
    artifact.chmod(0o600)

    with pytest.raises(
        CPUPerformanceTerminalDecisionError,
        match="byte count changed",
    ):
        verify_terminal_decision(artifact_path=artifact)
