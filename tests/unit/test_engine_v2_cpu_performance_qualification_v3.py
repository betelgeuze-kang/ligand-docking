from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading

import pytest

from betelgeuze_engine_v2.docking import performance_qualification_v3 as v3
from betelgeuze_engine_v2.docking.performance_host_preflight_v3 import (
    HostPreflightEvidenceV3,
    SysfsBooleanEvidenceV3,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTIVATION = (
    _REPO_ROOT / "config/engine_v2_cpu_performance_v3_runner_activation.json"
)
_RUNNER = _REPO_ROOT / "tools/run_engine_v2_cpu_performance_qualification_v3.py"


def _use_isolated_state_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    monkeypatch.setattr(v3, "_account_home_directory", lambda: tmp_path)


def _reserve_test_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_name: str,
) -> v3._ReservedProfileAttemptV3:
    _use_isolated_state_home(tmp_path, monkeypatch)
    output = tmp_path / output_name
    activation = v3.verify_runner_activation_contract()
    _state_directory, descriptor = v3._open_state_directory()
    try:
        return v3._reserve_profile_attempt_v3(
            state_directory_fd=descriptor,
            activation_sha256=str(activation["activation_sha256"]),
            output_path_sha256=v3._output_path_sha256(output),
        )
    finally:
        os.close(descriptor)


def _blocked_host() -> HostPreflightEvidenceV3:
    return HostPreflightEvidenceV3(
        cpu_model="",
        boost_state=None,
        available_cpu_affinity=(),
        platform_system="Linux",
        platform_machine="x86_64",
        byteorder="little",
        parent_pid=os.getpid(),
        parent_os_task_count=1,
        qualified=False,
        blockers=("synthetic_host_blocker",),
    )


def _qualified_host() -> HostPreflightEvidenceV3:
    raw = b"0\n"
    return HostPreflightEvidenceV3(
        cpu_model=v3.v2.CPU_MODEL_EXACT,
        boost_state=SysfsBooleanEvidenceV3(
            path="/sys/devices/system/cpu/cpufreq/boost",
            reader_id="betelgeuze.linux_sysfs_boolean_reader/1.0.0",
            raw_byte_count=len(raw),
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            reported_size_before=4096,
            reported_size_descriptor_before=4096,
            reported_size_descriptor_after=4096,
            reported_size_after=4096,
            stable_read_count=2,
            boost_enabled=False,
        ),
        available_cpu_affinity=v3.v2.AUTHORITATIVE_CPU_AFFINITY,
        platform_system="Linux",
        platform_machine="x86_64",
        byteorder="little",
        parent_pid=os.getpid(),
        parent_os_task_count=1,
        qualified=True,
        blockers=(),
    )


def _blocked_projection() -> dict[str, object]:
    _profile, predecessor = v3._load_profiles()
    return v3._artifact_projection(
        predecessor=predecessor,
        run_nonce="0" * 64,
        host=_blocked_host(),
        source_bindings=v3._source_bindings(complete=False),
        transcript=(),
        fixture_results=(),
        status="blocked_preflight",
        recorded_decision="BLOCKED",
        recorded_numeric_gate_passed=None,
        blockers=("synthetic_host_blocker",),
    )


def _blocked_artifact() -> dict[str, object]:
    return v3._seal_artifact(_blocked_projection())


def test_current_runner_activation_is_exact_and_authority_false() -> None:
    result = v3.verify_runner_activation_contract()

    assert result == {
        "activation_sha256": (
            "3a309594b35cf0e14d4efd4f01146a6849218509c43f4f024b1d765e6d647bda"
        ),
        "authority": {
            "fresh_holdout_execution_authorized": False,
            "historical_ab_execution_authorized": False,
            "molecular_execution_authorized": False,
            "product_performance_claim_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "stage0_admission_authorized": False,
        },
        "github_actions_live_execution_allowed": False,
        "live_run_capability": True,
        "molecular_execution": False,
        "profile_id": "engine_v2_ryzen_5900x_geometric_kernel_synthetic_v3",
        "profile_sha256": (
            "21facfc62956b402d4a43e5b68389083bacaa3d3afd753eb6b1da3578c8bb6b3"
        ),
        "runner_activation_verified": True,
    }


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("authority", "molecular_execution_authorized"), True),
        (("runner", "github_actions_live_execution_allowed"), True),
        (("runner", "caller_supplied_probe_allowed"), True),
        (("runner", "exactly_once_profile_attempt"), False),
    ),
)
def test_runner_activation_tamper_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, str],
    value: object,
) -> None:
    document = json.loads(_ACTIVATION.read_text(encoding="ascii"))
    document[path[0]][path[1]] = value
    changed = tmp_path / "activation.json"
    changed.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    changed.chmod(0o600)
    monkeypatch.setattr(v3, "ACTIVATION_RELATIVE_PATH", changed)

    with pytest.raises(
        v3.CPUPerformanceQualificationV3Error,
        match="activation authority or identity changed",
    ):
        v3.verify_runner_activation_contract()


def test_runner_activation_source_cross_wiring_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = json.loads(_ACTIVATION.read_text(encoding="ascii"))
    document["source_bindings"]["runner_tool_sha256"] = "0" * 64
    changed = tmp_path / "activation.json"
    changed.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    changed.chmod(0o600)
    monkeypatch.setattr(v3, "ACTIVATION_RELATIVE_PATH", changed)

    with pytest.raises(
        v3.CPUPerformanceQualificationV3Error,
        match="source bindings changed",
    ):
        v3.verify_runner_activation_contract()


def test_blocked_artifact_round_trip_is_offline_only() -> None:
    artifact = _blocked_artifact()
    raw = v3._canonical_json_bytes(artifact) + b"\n"

    verified = v3.require_cpu_performance_artifact_v3_bytes(raw)

    assert verified.recorded_decision == "BLOCKED"
    assert verified.recorded_numeric_gate_passed is None
    assert verified.live_run_capability is False
    assert verified.local_numeric_gate_eligible is False
    assert verified.offline_replay_only is True
    assert verified.qualification_authority is False
    assert verified.verification_blockers == (
        "offline_artifact_cannot_attest_execution",
    )


def test_artifact_authority_escalation_fails_even_when_resealed() -> None:
    artifact = _blocked_artifact()
    projection = {
        key: copy.deepcopy(value)
        for key, value in artifact.items()
        if key != "receipt_sha256"
    }
    projection["authority"]["molecular_execution_authorized"] = True
    changed = v3._seal_artifact(projection)

    with pytest.raises(
        v3.CPUPerformanceQualificationV3Error,
        match="artifact v3 authority changed",
    ):
        v3.require_cpu_performance_artifact_v3_document(changed)


def test_artifact_receipt_tamper_fails_closed() -> None:
    artifact = _blocked_artifact()
    artifact["blockers"] = ["changed"]

    with pytest.raises(
        v3.CPUPerformanceQualificationV3Error,
        match="receipt changed",
    ):
        v3.require_cpu_performance_artifact_v3_document(artifact)


def test_live_result_is_unforgeable_and_blocked_runner_never_launches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(v3.CPUPerformanceQualificationV3Error, match="caller"):
        v3.LiveCPUPerformanceRunResultV3()

    monkeypatch.setattr(v3, "derive_host_preflight_evidence_v3", _blocked_host)

    def forbidden_launch(**_kwargs: object) -> object:
        raise AssertionError("host blocker must prevent child launch")

    monkeypatch.setattr(v3.v2, "_launch_sealed_child", forbidden_launch)
    attempt = _reserve_test_attempt(
        tmp_path, monkeypatch, output_name="blocked.json"
    )
    result = v3._execute_reserved_performance_runner_v3(attempt)

    assert result.live_run_capability is True
    assert result.recorded_decision == "BLOCKED"
    assert result.recorded_numeric_gate_passed is None
    assert result.blockers == ("synthetic_host_blocker",)


def test_total_budget_starts_before_activation_and_profile_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt = _reserve_test_attempt(
        tmp_path, monkeypatch, output_name="timeout.json"
    )
    clock = iter((100.0, 101.0))
    monkeypatch.setattr(v3.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        v3.v2.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )
    monkeypatch.setattr(
        v3,
        "derive_host_preflight_evidence_v3",
        lambda: (_ for _ in ()).throw(
            AssertionError("host preflight must not start after total timeout")
        ),
    )

    result = v3._execute_reserved_performance_runner_v3(attempt)

    assert result.recorded_decision == "BLOCKED"
    assert result.blockers == ("sealed_runner_total_timeout",)
    assert result.artifact_document()["host"]["blockers"] == [
        "host_not_evaluated_due_total_timeout"
    ]


def test_last_child_timeout_discards_all_measurements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt = _reserve_test_attempt(
        tmp_path, monkeypatch, output_name="last-child-timeout.json"
    )
    clock_calls = 0

    def clock() -> float:
        nonlocal clock_calls
        clock_calls += 1
        return 100.0 if clock_calls <= 6 else 101.0

    schedule = [
        {
            "global_launch_ordinal": 0,
            "fixture_id": "small",
            "phase": "warmup",
            "pair_index": 0,
            "role": "python_reference",
        }
    ]
    monkeypatch.setattr(v3.time, "monotonic", clock)
    monkeypatch.setattr(
        v3.v2.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )
    monkeypatch.setattr(v3, "derive_host_preflight_evidence_v3", _qualified_host)
    monkeypatch.setattr(
        v3,
        "_source_bindings",
        lambda *, complete: (
            {"measurement_core": {"binding": "fixed"}, "orchestration": {}}
            if complete
            else {"measurement_core": {}, "orchestration": {}}
        ),
    )
    monkeypatch.setattr(v3.v2, "_expected_launch_schedule", lambda _profile: schedule)
    monkeypatch.setattr(v3.v2, "_launch_sealed_child", lambda **_kwargs: {})

    result = v3._execute_reserved_performance_runner_v3(attempt)

    assert result.recorded_decision == "BLOCKED"
    assert result.artifact_document()["transcript"] == []
    assert "sealed_runner_total_timeout" in result.blockers
    assert "sealed_measurement_incomplete" in result.blockers


def test_source_postflight_drift_discards_all_measurements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt = _reserve_test_attempt(
        tmp_path, monkeypatch, output_name="source-drift.json"
    )
    bindings = iter(
        (
            {"measurement_core": {"binding": "first"}, "orchestration": {}},
            {"measurement_core": {"binding": "changed"}, "orchestration": {}},
        )
    )
    monkeypatch.setattr(v3, "derive_host_preflight_evidence_v3", _qualified_host)
    monkeypatch.setattr(
        v3, "_source_bindings", lambda *, complete: next(bindings) if complete else {
            "measurement_core": {},
            "orchestration": {},
        }
    )
    monkeypatch.setattr(v3.v2, "_expected_launch_schedule", lambda _profile: [])

    result = v3._execute_reserved_performance_runner_v3(attempt)

    assert result.recorded_decision == "BLOCKED"
    assert result.artifact_document()["transcript"] == []
    assert "source_binding_changed_during_measurement" in result.blockers
    assert "sealed_measurement_discarded_after_source_drift" in result.blockers


def test_host_postflight_drift_discards_all_measurements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt = _reserve_test_attempt(
        tmp_path, monkeypatch, output_name="host-drift.json"
    )
    hosts = iter((_qualified_host(), _blocked_host()))
    binding = {"measurement_core": {"binding": "fixed"}, "orchestration": {}}
    monkeypatch.setattr(
        v3, "derive_host_preflight_evidence_v3", lambda: next(hosts)
    )
    monkeypatch.setattr(
        v3,
        "_source_bindings",
        lambda *, complete: binding if complete else {
            "measurement_core": {},
            "orchestration": {},
        },
    )
    monkeypatch.setattr(v3.v2, "_expected_launch_schedule", lambda _profile: [])

    result = v3._execute_reserved_performance_runner_v3(attempt)

    assert result.recorded_decision == "BLOCKED"
    assert result.artifact_document()["transcript"] == []
    assert "host_context_changed_during_measurement" in result.blockers
    assert "sealed_measurement_discarded_after_host_drift" in result.blockers


def test_writer_is_owner_only_absent_only_and_replayable() -> None:
    _profile, predecessor = v3._load_profiles()
    result = v3._blocked_result(
        predecessor=predecessor,
        run_nonce="1" * 64,
        host=_blocked_host(),
        blockers=("synthetic_host_blocker",),
    )
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-v3-writer-", dir="/tmp"
    ) as raw_directory:
        output = Path(raw_directory) / "result.json"

        published = v3._write_cpu_performance_artifact_v3(result, output)

        assert published == output
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
        verified = v3.require_cpu_performance_artifact_v3_bytes(output.read_bytes())
        assert verified.recorded_decision == "BLOCKED"
        with pytest.raises(
            v3.CPUPerformanceQualificationV3Error,
            match="already exists",
        ):
            v3._write_cpu_performance_artifact_v3(result, output)


def test_live_result_cannot_publish_to_a_second_absent_path() -> None:
    _profile, predecessor = v3._load_profiles()
    result = v3._blocked_result(
        predecessor=predecessor,
        run_nonce="3" * 64,
        host=_blocked_host(),
        blockers=("synthetic_host_blocker",),
    )

    with tempfile.TemporaryDirectory(
        prefix="engine-v2-v3-single-publish-", dir="/tmp"
    ) as raw_directory:
        directory = Path(raw_directory)
        first = v3._write_cpu_performance_artifact_v3(
            result, directory / "first.json"
        )

        assert first.is_file()
        assert result.live_run_capability is False
        with pytest.raises(v3.CPUPerformanceQualificationV3Error, match="claimed"):
            v3._write_cpu_performance_artifact_v3(
                result, directory / "second.json"
            )
        assert not (directory / "second.json").exists()


def test_writer_rejects_symlink_parent() -> None:
    _profile, predecessor = v3._load_profiles()
    result = v3._blocked_result(
        predecessor=predecessor,
        run_nonce="2" * 64,
        host=_blocked_host(),
        blockers=("synthetic_host_blocker",),
    )
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-v3-symlink-", dir="/tmp"
    ) as raw_directory:
        secure = Path(raw_directory)
        real = secure / "real"
        real.mkdir(mode=0o700)
        linked = secure / "linked"
        linked.symlink_to(real, target_is_directory=True)

        with pytest.raises(
            v3.CPUPerformanceQualificationV3Error,
            match="symlink",
        ):
            v3._write_cpu_performance_artifact_v3(result, linked / "result.json")


def test_artifact_reader_rejects_symlink_and_oversized_input() -> None:
    _profile, predecessor = v3._load_profiles()
    result = v3._blocked_result(
        predecessor=predecessor,
        run_nonce="4" * 64,
        host=_blocked_host(),
        blockers=("synthetic_host_blocker",),
    )
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-v3-reader-", dir="/tmp"
    ) as raw_directory:
        directory = Path(raw_directory)
        artifact = v3._write_cpu_performance_artifact_v3(
            result, directory / "artifact.json"
        )
        linked = directory / "linked.json"
        linked.symlink_to(artifact)

        with pytest.raises(v3.CPUPerformanceQualificationV3Error):
            v3.read_cpu_performance_artifact_v3(linked)

        oversized = directory / "oversized.json"
        descriptor = os.open(
            oversized,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.ftruncate(descriptor, v3.MAX_ARTIFACT_BYTES + 1)
        finally:
            os.close(descriptor)
        with pytest.raises(
            v3.CPUPerformanceQualificationV3Error,
            match="bounded|byte limit|outside",
        ):
            v3.read_cpu_performance_artifact_v3(oversized)


def test_exactly_once_transaction_persists_before_returning_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-v3-transaction-", dir="/tmp"
    ) as raw_directory:
        directory = Path(raw_directory)
        _use_isolated_state_home(directory, monkeypatch)
        monkeypatch.setattr(v3, "derive_host_preflight_evidence_v3", _blocked_host)
        monkeypatch.setattr(
            v3.v2,
            "_launch_sealed_child",
            lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("blocked preflight must not launch a child")
            ),
        )
        output = directory / "transaction.json"

        persisted = v3.run_sealed_local_performance_runner_v3(output)

        assert persisted.recorded_decision == "BLOCKED"
        assert persisted.live_run_capability is False
        assert persisted.qualification_authority is False
        assert persisted.execution_attested is False
        assert persisted.artifact_path == output
        assert persisted.attempt_ledger_path.is_file()
        assert persisted.terminal_state_path.is_file()
        artifact_raw = output.read_bytes()
        attempt_raw = persisted.attempt_ledger_path.read_bytes()
        terminal_raw = persisted.terminal_state_path.read_bytes()
        terminal = v3._require_terminal_state_bytes(
            terminal_raw,
            attempt_raw=attempt_raw,
            artifact_raw=artifact_raw,
            output_path_sha256=v3._output_path_sha256(output),
        )
        assert terminal["decision_returned_only_after_terminal_persistence"] is True
        assert terminal["recorded_decision"] == "BLOCKED"

        with pytest.raises(
            v3.CPUPerformanceQualificationV3Error,
            match="already consumed",
        ):
            v3.run_sealed_local_performance_runner_v3(directory / "rerun.json")


def test_terminal_failure_burns_attempt_without_returning_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-v3-terminal-failure-", dir="/tmp"
    ) as raw_directory:
        directory = Path(raw_directory)
        _use_isolated_state_home(directory, monkeypatch)
        monkeypatch.setattr(v3, "derive_host_preflight_evidence_v3", _blocked_host)

        def fail_terminal(_descriptor: int, _raw: bytes) -> None:
            raise v3.CPUPerformanceQualificationV3Error(
                "synthetic terminal failure"
            )

        monkeypatch.setattr(v3, "_publish_terminal_state", fail_terminal)
        output = directory / "artifact-before-terminal-failure.json"

        with pytest.raises(
            v3.CPUPerformanceQualificationV3Error,
            match="synthetic terminal failure",
        ):
            v3.run_sealed_local_performance_runner_v3(output)

        state_directory = directory / v3.STATE_DIRECTORY_RELATIVE_PATH
        assert output.is_file()
        assert (state_directory / v3.ATTEMPT_LEDGER_FILENAME).is_file()
        assert not (state_directory / v3.TERMINAL_STATE_FILENAME).exists()
        with pytest.raises(
            v3.CPUPerformanceQualificationV3Error,
            match="already consumed",
        ):
            v3.run_sealed_local_performance_runner_v3(
                directory / "forbidden-rerun.json"
            )


def test_attempt_reservation_is_atomic_across_concurrent_callers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_isolated_state_home(tmp_path, monkeypatch)
    activation = v3.verify_runner_activation_contract()
    state_directory, first_descriptor = v3._open_state_directory()
    second_state_directory, second_descriptor = v3._open_state_directory()
    assert second_state_directory == state_directory
    barrier = threading.Barrier(2)
    outcomes: list[object] = []
    outcome_lock = threading.Lock()

    def reserve(descriptor: int, suffix: str) -> None:
        barrier.wait()
        try:
            outcome: object = v3._reserve_profile_attempt_v3(
                state_directory_fd=descriptor,
                activation_sha256=str(activation["activation_sha256"]),
                output_path_sha256=v3._output_path_sha256(
                    tmp_path / f"{suffix}.json"
                ),
            )
        except v3.CPUPerformanceQualificationV3Error as exc:
            outcome = exc
        with outcome_lock:
            outcomes.append(outcome)

    threads = (
        threading.Thread(target=reserve, args=(first_descriptor, "first")),
        threading.Thread(target=reserve, args=(second_descriptor, "second")),
    )
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
    finally:
        os.close(first_descriptor)
        os.close(second_descriptor)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(isinstance(value, v3._ReservedProfileAttemptV3) for value in outcomes) == 1
    errors = [value for value in outcomes if isinstance(value, Exception)]
    assert len(errors) == 1
    assert "consumed" in str(errors[0])


def test_underlying_runner_refuses_github_actions_before_state_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_isolated_state_home(tmp_path, monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    with pytest.raises(
        v3.CPUPerformanceQualificationV3Error,
        match="GitHub Actions cannot execute",
    ):
        v3.run_sealed_local_performance_runner_v3(tmp_path / "must-not-exist.json")

    assert not (tmp_path / v3.STATE_DIRECTORY_RELATIVE_PATH).exists()


def test_cli_refuses_live_execution_inside_github_actions(tmp_path: Path) -> None:
    output = tmp_path / "must-not-exist.json"
    environment = dict(os.environ)
    environment["GITHUB_ACTIONS"] = "true"

    completed = subprocess.run(
        [sys.executable, str(_RUNNER), "--run-output", str(output)],
        cwd=_REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "GitHub Actions cannot execute" in completed.stderr
    assert not output.exists()


def test_isolated_cli_enters_bootstrap_instead_of_importing_checkout_package() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(_RUNNER), "--verify-activation"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # The development interpreter is not the frozen CPython 3.10.12 lane, but
    # it must reach the stdlib-only bootstrap and fail there, not on package import.
    assert completed.returncode != 0
    assert "bootstrap rejected runtime" in completed.stderr
    assert "ModuleNotFoundError" not in completed.stderr
