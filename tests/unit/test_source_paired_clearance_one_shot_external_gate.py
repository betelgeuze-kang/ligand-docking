from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    OneShotABDecision,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_external_gate import (
    INVALID_EXTERNAL_POLICY_BLOCKER,
    combine_one_shot_and_external_decisions,
    external_historical_execution_decision,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_NAMES = (
    "engine_v2_source_paired_clearance_one_shot_ab.json",
    "engine_v2_phase25_cohort_admission.json",
    "engine_v2_source_paired_clearance_activation.json",
    "engine_v2_source_paired_clearance_external_reservation.json",
)
_EXPECTED_EXTERNAL_BLOCKERS = (
    "external_reservation_provider_not_operational",
    "external_reservation_endpoint_not_configured",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
)


def _external_policy() -> dict[str, object]:
    return json.loads(
        (
            _REPO_ROOT
            / "config/engine_v2_source_paired_clearance_external_reservation.json"
        ).read_text(encoding="utf-8")
    )


def _operator_root(tmp_path: Path) -> Path:
    config_root = tmp_path / "config"
    config_root.mkdir()
    for name in _CONFIG_NAMES:
        shutil.copy2(_REPO_ROOT / "config" / name, config_root / name)
    return tmp_path


def _run_operator(root: Path, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(
                _REPO_ROOT
                / "tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py"
            ),
            "--repo-root",
            str(root),
            *command,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_committed_external_policy_blocks_combined_execution_authority() -> None:
    local = OneShotABDecision(authorized=True, blockers=())

    decision = combine_one_shot_and_external_decisions(
        local,
        external_policy=_external_policy(),
    )

    assert decision.authorized is False
    assert decision.blockers == _EXPECTED_EXTERNAL_BLOCKERS


def test_invalid_external_policy_fails_closed_without_leaking_details() -> None:
    changed = copy.deepcopy(_external_policy())
    authority = changed["authority"]
    assert isinstance(authority, dict)
    authority["historical_execution_operational"] = True

    decision = external_historical_execution_decision(changed)

    assert decision == OneShotABDecision(
        authorized=False,
        blockers=(INVALID_EXTERNAL_POLICY_BLOCKER,),
    )


def test_operator_status_reports_combined_external_blockers(tmp_path: Path) -> None:
    result = _run_operator(_operator_root(tmp_path), "status")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["authorized_if_reserved_now"] is False
    assert payload["blockers"][-4:] == list(_EXPECTED_EXTERNAL_BLOCKERS)


@pytest.mark.parametrize(
    "command",
    (
        (
            "reserve",
            "--source-commit",
            "1" * 40,
            "--operator-id",
            "operator-alpha",
            "--execution-environment-sha256",
            "2" * 64,
        ),
        ("start",),
        ("write-result", "--full-evidence", "not-opened.json"),
    ),
)
def test_every_operator_mutation_fails_before_local_state(
    tmp_path: Path,
    command: tuple[str, ...],
) -> None:
    root = _operator_root(tmp_path)

    result = _run_operator(root, *command)

    assert result.returncode == 2
    assert _EXPECTED_EXTERNAL_BLOCKERS[0] in result.stderr
    assert not (root / ".betelgeuze").exists()
