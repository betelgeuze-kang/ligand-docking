from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from tools.run_engine_v2_sampling_pool_cpu_observation_v1 import (
    EXPECTED_AUTHORITY_KEYS,
    EXPECTED_FIXTURE_COUNTS,
    EXPECTED_MEMORY_ROLE,
    EXPECTED_RECEIPTS,
    EXPECTED_TIMED_BOUNDARY,
    EXPECTED_WALL_TIME_ROLE,
    PROFILE_ID,
    SCHEMA_ID,
    SamplingPoolCPUObservationError,
    _build_library,
    _compile_observer,
    _reject_duplicate_keys,
    _run,
    _validate,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/run_engine_v2_sampling_pool_cpu_observation_v1.py"


def fixture_document() -> dict[str, object]:
    return {
        "all_authority_false": True,
        "fixtures": [
            {
                "fixture_id": fixture_id,
                "receipt_sha256": receipt,
                "ligand_atom_count": EXPECTED_FIXTURE_COUNTS[fixture_id][0],
                "receptor_atom_count": EXPECTED_FIXTURE_COUNTS[fixture_id][1],
                "exact_pair_evaluation_count": EXPECTED_FIXTURE_COUNTS[fixture_id][2],
            }
            for fixture_id, receipt in EXPECTED_RECEIPTS.items()
        ],
        "profile_id": PROFILE_ID,
        "schema_id": SCHEMA_ID,
        "status": "synthetic_fixture_verification_only",
    }


def test_static_fixture_runner_compiles_and_reproduces_exact_receipts() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--verify-fixtures"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    observed = json.loads(completed.stdout)
    assert observed["all_authority_false"] is True
    assert {
        row["fixture_id"]: row["receipt_sha256"] for row in observed["fixtures"]
    } == EXPECTED_RECEIPTS


def test_duplicate_crosswired_and_malformed_outputs_fail_closed() -> None:
    with pytest.raises(SamplingPoolCPUObservationError, match="duplicate JSON key"):
        json.loads('{"a":1,"a":2}', object_pairs_hook=_reject_duplicate_keys)

    value = fixture_document()
    value["fixtures"][0]["receipt_sha256"] = "00" * 32
    with pytest.raises(SamplingPoolCPUObservationError, match="receipt changed"):
        _validate(value, expected_sample_count=None)

    value = fixture_document()
    value["fixtures"] = value["fixtures"][:2]
    with pytest.raises(SamplingPoolCPUObservationError, match="denominator changed"):
        _validate(value, expected_sample_count=None)


def observed_document(samples: int = 3) -> dict[str, object]:
    value = fixture_document()
    value.pop("all_authority_false")
    value["authority"] = {key: False for key in EXPECTED_AUTHORITY_KEYS}
    value["cpu_model"] = "synthetic-test-cpu"
    value["memory_role"] = EXPECTED_MEMORY_ROLE
    value["sample_count"] = samples
    value["status"] = "local_synthetic_development_observation_only"
    value["timed_boundary"] = EXPECTED_TIMED_BOUNDARY
    value["wall_time_role"] = EXPECTED_WALL_TIME_ROLE
    for row in value["fixtures"]:
        row["wall_time_ns_samples"] = list(range(1, samples + 1))
        row["wall_time_ns_p50"] = 2
        row["wall_time_ns_p95"] = samples
        row["peak_rss_kib"] = 1
        row["peak_rss_delta_kib"] = 0
    return value


def test_observation_sample_and_authority_denominators_fail_closed() -> None:
    value = observed_document()
    value["fixtures"][0]["wall_time_ns_samples"] = [1]
    with pytest.raises(SamplingPoolCPUObservationError, match="timing or memory"):
        _validate(value, expected_sample_count=3)

    value = observed_document()
    value["sample_count"] = 2
    with pytest.raises(SamplingPoolCPUObservationError, match="sample denominator"):
        _validate(value, expected_sample_count=3)

    value = observed_document()
    del value["authority"]["reservation_authorized"]
    with pytest.raises(SamplingPoolCPUObservationError, match="authority"):
        _validate(value, expected_sample_count=3)

    value = observed_document()
    value["cpu_model"] = ""
    with pytest.raises(SamplingPoolCPUObservationError, match="CPU identity"):
        _validate(value, expected_sample_count=3)

    value = observed_document()
    value["timed_boundary"] = "whole_process"
    with pytest.raises(SamplingPoolCPUObservationError, match="role metadata"):
        _validate(value, expected_sample_count=3)


def test_compile_uses_cargo_reported_rlib_dependency_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[tuple[tuple[str, ...], Path, int]] = []

    def fake_run(
        command: tuple[str, ...], *, cwd: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        observed.append((command, cwd, timeout))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "tools.run_engine_v2_sampling_pool_cpu_observation_v1._run", fake_run
    )
    dependency_dir = tmp_path / "custom-target/release/deps"
    _compile_observer(
        dependency_dir / "libbetelgeuze_docking_search-abcd.rlib",
        tmp_path / "observer",
    )
    assert f"dependency={dependency_dir}" in observed[0][0]

    _compile_observer(
        dependency_dir.parent / "libbetelgeuze_docking_search.rlib",
        tmp_path / "observer-from-release-root",
    )
    assert f"dependency={dependency_dir}" in observed[1][0]


def test_standalone_rust_test_module_is_compiled_and_executed(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "sampling-pool-observer-tests"
    _compile_observer(_build_library(), executable, test_harness=True)
    completed = _run((str(executable),), cwd=ROOT, timeout=120)
    assert "4 passed" in completed.stdout


def test_timeout_kills_the_entire_command_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        pid = 4321
        returncode = -signal.SIGKILL
        calls = 0

        def communicate(self, timeout: int | None = None) -> tuple[str, str]:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(("observer",), timeout)
            return "", ""

    process = FakeProcess()
    popen_arguments: dict[str, object] = {}

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        popen_arguments.update(kwargs)
        return process

    killed: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    with pytest.raises(SamplingPoolCPUObservationError, match="timed out"):
        _run(("observer",), cwd=ROOT, timeout=1)
    assert popen_arguments["start_new_session"] is True
    assert killed == [(process.pid, signal.SIGKILL)]
    assert process.calls == 2


def test_github_actions_timing_fails_before_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    from tools.run_engine_v2_sampling_pool_cpu_observation_v1 import execute

    with pytest.raises(SamplingPoolCPUObservationError, match="cannot create timing"):
        execute(samples=3)
