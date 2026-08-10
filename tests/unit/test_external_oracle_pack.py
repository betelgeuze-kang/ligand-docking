from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import types

import pytest

import benchmarks.oracles.execution as execution
from benchmarks.oracles import (
    OracleContractError,
    OracleRequest,
    OracleResult,
    canonical_json_bytes,
)
from benchmarks.oracles.errors import OracleExecutionError
from benchmarks.oracles.execution import (
    pinned_oracle_workspace,
    run_argv,
    sha256_regular_file,
)


def test_openmm_is_lazy_and_reference_fixture_matches_analytic_result() -> None:
    openmm_was_loaded = "openmm" in sys.modules
    from benchmarks.oracles import openmm as boundary

    if not openmm_was_loaded:
        assert "openmm" not in sys.modules
    try:
        runtime_sha256 = boundary.openmm_reference_runtime_sha256()
    except Exception as exc:
        if os.environ.get("BETELGEUZE_REQUIRE_OPENMM_ORACLE") == "1":
            raise
        pytest.skip(f"OpenMM is not installed in this benchmark environment: {exc}")
    if not openmm_was_loaded:
        assert "openmm" not in sys.modules

    from benchmarks.oracles.openmm.adapter import (
        evaluate_harmonic_bond_reference,
        openmm_reference_runtime_sha256,
        openmm_runtime_dependency_distributions_sha256,
    )

    fixture = json.loads(
        (
            Path(boundary.__file__).parent / "fixtures" / "harmonic_bond_v1.json"
        ).read_text(encoding="utf-8")
    )
    request = OracleRequest(**fixture["request"])
    with pytest.raises(OracleExecutionError) as invalid_input:
        evaluate_harmonic_bond_reference(
            OracleRequest(
                **{
                    **fixture["request"],
                    "input_sha256": {"prepared_system": "0" * 64},
                }
            ),
            expected_runtime_sha256="0" * 64,
        )
    assert invalid_input.value.code == "input_hash_mismatch"

    assert runtime_sha256 == openmm_reference_runtime_sha256()
    assert runtime_sha256 == openmm_runtime_dependency_distributions_sha256()
    with pytest.raises(OracleExecutionError) as invalid_runtime:
        evaluate_harmonic_bond_reference(
            request,
            expected_runtime_sha256="0" * 64,
        )
    assert invalid_runtime.value.code == "runtime_hash_mismatch"
    run = evaluate_harmonic_bond_reference(
        request,
        expected_runtime_sha256=runtime_sha256,
    )
    result = run.result
    expected = fixture["expected"]
    assert result.platform == "Reference"
    assert run.identity.runtime_sha256 == runtime_sha256
    assert run.identity.openmm_artifact_count > 0
    assert run.identity.numpy_artifact_count > 0
    assert run.provenance.request_sha256 == request.sha256
    assert run.provenance.executable_sha256 == runtime_sha256
    assert (
        run.provenance.values["runtime_dependency_manifest_schema_id"]
        == "betelgeuze.openmm_runtime_dependency_distributions/3.0.0"
    )
    assert [
        row["distribution"]
        for row in run.provenance.values["runtime_dependency_distributions"]
    ] == ["OpenMM", "numpy"]
    assert (
        run.provenance.raw_output_sha256["state_record"]
        == hashlib.sha256(run.raw_state).hexdigest()
    )
    assert math.isclose(
        result.energy_kcal_per_mol,
        expected["energy_kcal_per_mol"],
        rel_tol=0.0,
        abs_tol=2.0e-12,
    )
    for actual, wanted in zip(
        result.force_x_kcal_per_mol_angstrom,
        expected["force_x_kcal_per_mol_angstrom"],
        strict=True,
    ):
        assert math.isclose(actual, wanted, rel_tol=0.0, abs_tol=2.0e-11)


@pytest.mark.parametrize(
    ("distribution_name", "swap_scope"),
    (("OpenMM", "artifact"), ("numpy", "artifact"), ("OpenMM", "ancestor")),
)
def test_openmm_runtime_rejects_artifact_rename_swap_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    distribution_name: str,
    swap_scope: str,
) -> None:
    from benchmarks.oracles.openmm import adapter

    install_root = tmp_path / "site-packages"
    openmm_package = install_root / "openmm"
    numpy_package = install_root / "numpy"
    openmm_package.mkdir(parents=True)
    numpy_package.mkdir()
    openmm_artifact = openmm_package / "version.py"
    numpy_artifact = numpy_package / "version.py"
    openmm_artifact.write_bytes(b"trusted-openmm-runtime")
    numpy_artifact.write_bytes(b"trusted-numpy-runtime")
    for name in ("openmm", "numpy"):
        metadata_dir = install_root / f"{name}-test.dist-info"
        metadata_dir.mkdir()
        (metadata_dir / "METADATA").write_text(
            f"Name: {name}\nVersion: test-{name}-runtime\n",
            encoding="utf-8",
        )

    class FakeDistribution:
        def __init__(self, name: str) -> None:
            self.version = f"test-{name.lower()}-runtime"
            self.files = (
                f"{name.lower()}/version.py",
                f"{name.lower()}-test.dist-info/METADATA",
            )

        @staticmethod
        def locate_file(entry: object) -> Path:
            return install_root / str(entry)

    monkeypatch.setattr(
        adapter.metadata,
        "distribution",
        lambda name: FakeDistribution(name),
    )
    runtime_sha256 = adapter.openmm_reference_runtime_sha256()
    package = openmm_package if distribution_name == "OpenMM" else numpy_package
    artifact = openmm_artifact if distribution_name == "OpenMM" else numpy_artifact
    trusted_bytes = artifact.read_bytes()
    consumed: list[bytes] = []

    with pytest.raises(OracleExecutionError) as raised:
        with adapter._pinned_runtime(runtime_sha256):
            if swap_scope == "artifact":
                trusted = artifact.with_name("version.py.trusted")
                artifact.rename(trusted)
                artifact.write_bytes(b"attacker-runtime")
                consumed.append(artifact.read_bytes())
                artifact.unlink()
                trusted.rename(artifact)
            else:
                trusted_package = package.with_name(f"{package.name}.trusted")
                package.rename(trusted_package)
                package.mkdir()
                artifact.write_bytes(b"attacker-runtime")
                consumed.append(artifact.read_bytes())
                artifact.unlink()
                package.rmdir()
                trusted_package.rename(package)

    assert raised.value.code == "runtime_hash_drift"
    assert consumed == [b"attacker-runtime"]
    assert artifact.read_bytes() == trusted_bytes


def test_openmm_runtime_inventory_is_reproducible_across_venv_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from benchmarks.oracles.openmm import adapter

    def fake_install(environment: Path) -> dict[str, object]:
        search_root = environment / "lib" / "python3.11" / "site-packages"
        scripts = environment / "bin"
        search_root.mkdir(parents=True)
        scripts.mkdir()
        distributions: dict[str, object] = {}
        for distribution_name, package_name, version in (
            ("OpenMM", "openmm", "8.4.0"),
            ("numpy", "numpy", "1.26.4"),
        ):
            package = search_root / package_name
            cache = package / "__pycache__"
            metadata_dir = search_root / f"{package_name}-{version}.dist-info"
            cache.mkdir(parents=True)
            metadata_dir.mkdir()
            (package / "__init__.py").write_text(
                f"VERSION = {version!r}\n", encoding="utf-8"
            )
            (cache / "__init__.cpython-311.pyc").write_bytes(
                f"generated-for:{environment}".encode()
            )
            (metadata_dir / "METADATA").write_text(
                f"Name: {distribution_name}\nVersion: {version}\n",
                encoding="utf-8",
            )
            (metadata_dir / "RECORD").write_text(
                f"installed-at,{environment}\n", encoding="utf-8"
            )
            (metadata_dir / "INSTALLER").write_text("pip\n", encoding="utf-8")
            (metadata_dir / "REQUESTED").write_bytes(b"")
            (metadata_dir / "direct_url.json").write_text(
                json.dumps({"url": environment.as_uri()}), encoding="utf-8"
            )
            files = [
                f"{package_name}/__init__.py",
                f"{package_name}/__pycache__/__init__.cpython-311.pyc",
                f"{metadata_dir.name}/METADATA",
                f"{metadata_dir.name}/RECORD",
                f"{metadata_dir.name}/INSTALLER",
                f"{metadata_dir.name}/REQUESTED",
                f"{metadata_dir.name}/direct_url.json",
            ]
            if distribution_name == "numpy":
                f2py = scripts / "f2py"
                f2py.write_text(f"#!{environment}/bin/python\n", encoding="utf-8")
                files.append("../../../bin/f2py")

            class FakeDistribution:
                def __init__(self) -> None:
                    self.version = version
                    self.files = tuple(files)

                def locate_file(self, entry: object) -> Path:
                    return search_root / str(entry)

            distributions[distribution_name] = FakeDistribution()
        return distributions

    installs = {
        "a": fake_install(tmp_path / "venv-a"),
        "b": fake_install(tmp_path / "different" / "venv-b"),
    }
    active = "a"
    monkeypatch.setattr(
        adapter.metadata,
        "distribution",
        lambda name: installs[active][name],
    )

    def inventory_digest() -> tuple[str, set[str]]:
        inventory = adapter._distribution_inventory()
        included = {
            path
            for distribution in inventory.distributions
            for path, _absolute in distribution.entries
        }
        snapshot = adapter._capture_runtime_snapshot(inventory)
        try:
            return snapshot.sha256, included
        finally:
            snapshot.close()

    digest_a, included_a = inventory_digest()
    active = "b"
    digest_b, included_b = inventory_digest()

    assert digest_a == digest_b
    assert included_a == included_b
    assert any(path.endswith(".dist-info/METADATA") for path in included_a)
    assert not any("__pycache__" in path for path in included_a)
    assert not any(
        path.endswith(("/RECORD", "/INSTALLER", "/REQUESTED", "/direct_url.json"))
        for path in included_a
    )
    assert "../../../bin/f2py" not in included_a


def test_openmm_reference_ignores_preloaded_parent_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from benchmarks.oracles.openmm import adapter, openmm_reference_runtime_sha256

    fixture = json.loads(
        (
            Path(adapter.__file__).parent / "fixtures" / "harmonic_bond_v1.json"
        ).read_text(encoding="utf-8")
    )
    try:
        runtime_sha256 = openmm_reference_runtime_sha256()
    except Exception as exc:
        if os.environ.get("BETELGEUZE_REQUIRE_OPENMM_ORACLE") == "1":
            raise
        pytest.skip(f"OpenMM is not installed in this benchmark environment: {exc}")
    inventory = adapter._distribution_inventory()
    dependencies = {
        distribution.name: distribution for distribution in inventory.distributions
    }
    disk_origin = dict(dependencies["OpenMM"].entries)["openmm/__init__.py"]
    numpy_disk_origin = dict(dependencies["numpy"].entries)["numpy/__init__.py"]
    preloaded_a = types.ModuleType("openmm")
    preloaded_a.__file__ = str(disk_origin)
    preloaded_a.reference_marker = "preloaded-A"
    preloaded_numpy_a = types.ModuleType("numpy")
    preloaded_numpy_a.__file__ = str(numpy_disk_origin)
    preloaded_numpy_a.reference_marker = "preloaded-numpy-A"
    monkeypatch.setitem(sys.modules, "openmm", preloaded_a)
    monkeypatch.setitem(sys.modules, "numpy", preloaded_numpy_a)
    parent_loader_called = False

    def load_preloaded_a():
        nonlocal parent_loader_called
        parent_loader_called = True
        raise AssertionError("high-assurance path used parent OpenMM code")

    monkeypatch.setattr(adapter, "load_openmm", load_preloaded_a)
    run = adapter.evaluate_harmonic_bond_reference(
        OracleRequest(**fixture["request"]),
        expected_runtime_sha256=runtime_sha256,
    )

    assert parent_loader_called is False
    assert run.identity.runtime_sha256 == runtime_sha256
    assert run.provenance.values["isolated_child"] is True
    assert math.isclose(
        run.result.energy_kcal_per_mol,
        fixture["expected"]["energy_kcal_per_mol"],
        rel_tol=0.0,
        abs_tol=2.0e-12,
    )


def test_request_and_result_bytes_are_canonical_and_claim_locked() -> None:
    request = OracleRequest(
        engine_id="openmm",
        case_id="case-1",
        task="energy_force",
        input_sha256={"system": "a" * 64},
        parameters={"temperature_kelvin": 300.0, "rows": [2, 1]},
        seed=7,
        thread_count=1,
    )
    assert (
        request.sha256
        == hashlib.sha256(canonical_json_bytes(request.to_dict())).hexdigest()
    )
    assert request.to_dict()["claim_safe"] is False
    detached = request.to_dict()
    detached["parameters"]["rows"].append(3)
    assert request.to_dict()["parameters"]["rows"] == [2, 1]
    result = OracleResult(
        request_sha256=request.sha256,
        engine_id="openmm",
        engine_version="8.4",
        executable_sha256="b" * 64,
        status="success",
        values={"total_kcal_per_mol": -1.25},
        raw_output_sha256={"stdout": hashlib.sha256(b"ok").hexdigest()},
    )
    assert result.to_dict()["customer_execution_enabled"] is False
    assert result.to_dict()["scientifically_validated"] is False
    assert len(result.sha256) == 64
    with pytest.raises(OracleContractError, match="non-finite"):
        OracleRequest(
            engine_id="openmm",
            case_id="bad",
            task="energy",
            input_sha256={"system": "a" * 64},
            parameters={"bad": float("nan")},
        )
    for invalid in (
        {"seed": 1.5},
        {"thread_count": 1.0},
        {"input_sha256": None},
        {"parameters": None},
    ):
        arguments = {
            "engine_id": "openmm",
            "case_id": "bad-type",
            "task": "energy",
            "input_sha256": {"system": "a" * 64},
            "parameters": {},
        }
        arguments.update(invalid)
        with pytest.raises(OracleContractError):
            OracleRequest(**arguments)


def test_argv_executor_is_shell_free_hash_pinned_and_output_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_popen = subprocess.Popen
    bounded_pipe_drains: list[bool] = []

    def observed_popen(*args, **kwargs):
        bounded_pipe_drains.append(
            kwargs.get("stdout") is subprocess.PIPE
            and kwargs.get("stderr") is subprocess.PIPE
            and kwargs.get("start_new_session") is True
        )
        return original_popen(*args, **kwargs)

    monkeypatch.setattr("benchmarks.oracles.execution.subprocess.Popen", observed_popen)
    executable = tmp_path / "oracle"
    executable.write_text("#!/bin/sh\nprintf 'ok'\n", encoding="utf-8")
    executable.chmod(0o700)
    digest = sha256_regular_file(executable)
    output = run_argv(
        (str(executable),),
        timeout_seconds=2,
        max_output_bytes=8,
        expected_executable_sha256=digest,
    )
    assert output.stdout == b"ok"
    assert output.returncode == 0
    assert bounded_pipe_drains == [True]
    with pytest.raises(OracleExecutionError) as raised:
        run_argv(
            (
                sys.executable,
                "-c",
                "import os; os.write(1, b'x' * 10000000); os.write(2, b'y' * 10000000)",
            ),
            timeout_seconds=2,
            max_output_bytes=1024,
        )
    assert raised.value.code == "output_too_large"
    assert len(raised.value.stdout) + len(raised.value.stderr) == 1024
    assert raised.value.capture_complete is False
    assert bounded_pipe_drains == [True, True]

    def assert_no_shell(*args, **kwargs):
        assert kwargs["shell"] is False
        return subprocess.CompletedProcess(args[0], 0, b"ok", b"")

    run_argv((str(executable),), timeout_seconds=2, runner=assert_no_shell)


def test_pinned_workspace_consumes_descriptor_snapshot_during_swap_restore(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "oracle"
    executable.write_text('#!/bin/sh\ncat "$1"\n', encoding="utf-8")
    executable.chmod(0o700)
    executable_digest = sha256_regular_file(executable)
    prepared = tmp_path / "prepared.dat"
    prepared.write_bytes(b"trusted-input")
    prepared_digest = hashlib.sha256(prepared.read_bytes()).hexdigest()
    request = OracleRequest(
        engine_id="vina",
        case_id="snapshot-race",
        task="docking",
        input_sha256={"system": prepared_digest},
        parameters={},
    )

    with pinned_oracle_workspace(
        executable,
        executable_digest,
        request,
        {"system": prepared},
        engine_id="vina",
        task="docking",
    ) as workspace:
        trusted_executable = tmp_path / "trusted-executable"
        trusted_input = tmp_path / "trusted-input"
        executable.replace(trusted_executable)
        prepared.replace(trusted_input)
        executable.write_text(
            "#!/bin/sh\nprintf 'malicious-binary'\n", encoding="utf-8"
        )
        executable.chmod(0o700)
        prepared.write_bytes(b"malicious-input")
        try:
            output = run_argv(
                (workspace.executable, workspace.inputs["system"]),
                timeout_seconds=2,
                expected_executable_sha256=workspace.executable_sha256,
                pass_fds=workspace.pass_fds,
            )
        finally:
            executable.unlink()
            prepared.unlink()
            trusted_executable.replace(executable)
            trusted_input.replace(prepared)

    assert output.stdout == b"trusted-input"
    assert sha256_regular_file(executable) == executable_digest
    assert hashlib.sha256(prepared.read_bytes()).hexdigest() == prepared_digest


def test_pinned_workspace_rejects_snapshot_write_and_restore(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "oracle"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    executable_digest = sha256_regular_file(executable)
    prepared = tmp_path / "prepared.dat"
    prepared.write_bytes(b"trusted-input")
    request = OracleRequest(
        engine_id="vina",
        case_id="snapshot-mutation",
        task="docking",
        input_sha256={"system": hashlib.sha256(prepared.read_bytes()).hexdigest()},
        parameters={},
    )
    consumed: list[bytes] = []

    def mutating_runner(command, **_kwargs):
        snapshot = Path(command[1])
        original = snapshot.read_bytes()
        snapshot.chmod(0o600)
        snapshot.write_bytes(b"attacker-snapshot")
        consumed.append(snapshot.read_bytes())
        snapshot.write_bytes(original)
        snapshot.chmod(0o400)
        return subprocess.CompletedProcess(command, 0, b"ok", b"")

    with pytest.raises(OracleExecutionError) as raised:
        with pinned_oracle_workspace(
            executable,
            executable_digest,
            request,
            {"system": prepared},
            engine_id="vina",
            task="docking",
        ) as workspace:
            run_argv(
                (workspace.executable, workspace.inputs["system"]),
                timeout_seconds=2,
                expected_executable_sha256=workspace.executable_sha256,
                pass_fds=workspace.pass_fds,
                runner=mutating_runner,
                integrity_check=workspace.verify_unchanged,
            )
    assert raised.value.code == "input_hash_drift"
    assert consumed == [b"attacker-snapshot"]


def test_pinned_workspace_rejects_private_path_rename_swap_restore(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "oracle"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    prepared = tmp_path / "prepared.dat"
    prepared.write_bytes(b"trusted-input")
    request = OracleRequest(
        engine_id="vina",
        case_id="snapshot-path-swap",
        task="docking",
        input_sha256={"system": hashlib.sha256(prepared.read_bytes()).hexdigest()},
        parameters={},
    )

    def swapping_runner(command, **_kwargs):
        snapshot = Path(command[1])
        snapshot.parent.chmod(0o700)
        backup = snapshot.with_name("attacker-backup")
        snapshot.rename(backup)
        snapshot.write_bytes(b"attacker-snapshot")
        snapshot.unlink()
        backup.rename(snapshot)
        snapshot.parent.chmod(0o500)
        return subprocess.CompletedProcess(command, 0, b"ok", b"")

    with pytest.raises(OracleExecutionError) as raised:
        with pinned_oracle_workspace(
            executable,
            sha256_regular_file(executable),
            request,
            {"system": prepared},
            engine_id="vina",
            task="docking",
        ) as workspace:
            run_argv(
                (workspace.executable, workspace.inputs["system"]),
                timeout_seconds=2,
                expected_executable_sha256=workspace.executable_sha256,
                pass_fds=workspace.pass_fds,
                runner=swapping_runner,
                integrity_check=workspace.verify_unchanged,
            )
    assert raised.value.code == "input_hash_drift"


def test_pinned_workspace_rejects_swap_during_final_descriptor_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "oracle"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    prepared = tmp_path / "prepared.dat"
    prepared.write_bytes(b"trusted-input")
    request = OracleRequest(
        engine_id="vina",
        case_id="final-verification-race",
        task="docking",
        input_sha256={"system": hashlib.sha256(prepared.read_bytes()).hexdigest()},
        parameters={},
    )
    original_hash = execution._sha256_descriptor
    armed = False
    triggered = False
    snapshot: Path | None = None

    def racing_hash(descriptor: int) -> str:
        nonlocal triggered
        digest = original_hash(descriptor)
        if armed and not triggered:
            assert snapshot is not None
            triggered = True
            snapshot.parent.chmod(0o700)
            trusted = snapshot.with_name("trusted-final-snapshot")
            snapshot.rename(trusted)
            snapshot.write_bytes(b"attacker-snapshot")
            assert snapshot.read_bytes() == b"attacker-snapshot"
            snapshot.unlink()
            trusted.rename(snapshot)
            snapshot.parent.chmod(0o500)
        return digest

    monkeypatch.setattr(execution, "_sha256_descriptor", racing_hash)
    with pytest.raises(OracleExecutionError) as raised:
        with pinned_oracle_workspace(
            executable,
            sha256_regular_file(executable),
            request,
            {"system": prepared},
            engine_id="vina",
            task="docking",
        ) as workspace:
            snapshot = Path(workspace.inputs["system"])
            armed = True
    assert triggered is True
    assert raised.value.code == "input_hash_drift"


def test_timeout_kills_solver_process_group_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "escaped"
    descendant = (
        "from pathlib import Path; import time; "
        f"time.sleep(0.8); Path({str(marker)!r}).write_text('escaped')"
    )
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}], "
        "start_new_session=True); "
        "time.sleep(30)"
    )
    with pytest.raises(OracleExecutionError) as raised:
        run_argv(
            (sys.executable, "-c", parent),
            timeout_seconds=0.3,
            max_output_bytes=1024,
        )
    assert raised.value.code == "timeout"
    time.sleep(1.0)
    assert not marker.exists()


def test_successful_solver_cannot_leave_daemonized_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "escaped-after-success"
    descendant = (
        "from pathlib import Path; import os, time; "
        "os.close(1); os.close(2); time.sleep(0.8); "
        f"Path({str(marker)!r}).write_text('escaped')"
    )
    parent = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}], "
        "start_new_session=True); "
        "print('ok')"
    )
    output = run_argv(
        (sys.executable, "-c", parent),
        timeout_seconds=2,
        max_output_bytes=1024,
    )
    assert output.stdout == b"ok\n"
    time.sleep(1.0)
    assert not marker.exists()


def test_solver_cannot_kill_namespace_cleanup_authority(tmp_path: Path) -> None:
    marker = tmp_path / "escaped-after-supervisor-kill"
    descendant = (
        "from pathlib import Path; import os, time; "
        "os.close(1); os.close(2); time.sleep(0.8); "
        f"Path({str(marker)!r}).write_text('escaped')"
    )
    parent = (
        "import os, signal, subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}], "
        "start_new_session=True); "
        "os.kill(os.getppid(), signal.SIGKILL)"
    )
    output = run_argv(
        (sys.executable, "-c", parent),
        timeout_seconds=2,
        max_output_bytes=1024,
    )
    assert output.returncode == 0
    time.sleep(1.0)
    assert not marker.exists()


def test_solver_filesystem_writes_are_confined_to_private_directories(
    tmp_path: Path,
) -> None:
    forbidden = tmp_path / "caller-side-effect"
    metadata_target = tmp_path / "caller-metadata"
    metadata_target.write_bytes(b"trusted")
    metadata_target.chmod(0o600)
    frozen_time_ns = 1_700_000_000_000_000_000
    os.utime(metadata_target, ns=(frozen_time_ns, frozen_time_ns))
    probe = (
        "import os, pathlib, socket; "
        "target = pathlib.Path(" + repr(str(forbidden)) + "); "
        "metadata = pathlib.Path(" + repr(str(metadata_target)) + "); "
        "blocked = []\n"
        "\ntry: target.write_text('owned')\n"
        "except PermissionError: blocked.append('write')\n"
        "try: os.chmod(metadata, 0o644)\n"
        "except PermissionError: blocked.append('chmod')\n"
        "try: os.utime(metadata, None)\n"
        "except PermissionError: blocked.append('utime')\n"
        "try: os.setxattr(metadata, b'user.betelgeuze', b'owned')\n"
        "except PermissionError: blocked.append('xattr')\n"
        "try: socket.socket()\n"
        "except PermissionError: blocked.append('socket')\n"
        "print(','.join(blocked), "
        "os.getcwd() == os.environ['HOME'] == os.environ['TMPDIR'])"
    )
    output = run_argv(
        (sys.executable, "-c", probe),
        timeout_seconds=2,
        max_output_bytes=1024,
    )
    assert output.stdout == b"write,chmod,utime,xattr,socket True\n"
    assert not forbidden.exists()
    assert metadata_target.read_bytes() == b"trusted"
    assert metadata_target.stat().st_mode & 0o777 == 0o600
    assert metadata_target.stat().st_mtime_ns == frozen_time_ns
    with pytest.raises(OSError):
        os.getxattr(metadata_target, b"user.betelgeuze")

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    descriptor = os.open(allowed, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        destination = f"/proc/self/fd/{descriptor}/result.txt"
        output = run_argv(
            (
                sys.executable,
                "-c",
                f"from pathlib import Path; Path({destination!r}).write_text('ok')",
            ),
            timeout_seconds=2,
            max_output_bytes=1024,
            pass_fds=(descriptor,),
            writable_directory_fds=(descriptor,),
        )
    finally:
        os.close(descriptor)
    assert output.returncode == 0
    assert (allowed / "result.txt").read_bytes() == b"ok"


def test_isolated_executor_does_not_leak_descriptors() -> None:
    before = frozenset(os.listdir("/proc/self/fd"))
    for _ in range(3):
        output = run_argv(
            (sys.executable, "-c", "print('ok')"),
            timeout_seconds=2,
            max_output_bytes=1024,
        )
        assert output.stdout == b"ok\n"
    assert frozenset(os.listdir("/proc/self/fd")) == before


def test_executor_rejects_inherited_writable_file_descriptor(tmp_path: Path) -> None:
    target = tmp_path / "caller-data"
    target.write_bytes(b"ORIGINAL-CALLER-DATA")
    descriptor = os.open(target, os.O_RDWR)
    try:
        with pytest.raises(OracleContractError):
            run_argv(
                (
                    sys.executable,
                    "-c",
                    f"import os; os.pwrite({descriptor}, b'PWNED!!!', 0)",
                ),
                timeout_seconds=2,
                pass_fds=(descriptor,),
            )
    finally:
        os.close(descriptor)
    assert target.read_bytes() == b"ORIGINAL-CALLER-DATA"


@pytest.mark.skipif(not hasattr(os, "memfd_create"), reason="Linux memfd is required")
def test_executor_rejects_read_only_memfd_reopen_upgrade() -> None:
    owner = os.memfd_create("betelgeuze-caller-data", flags=0)
    os.write(owner, b"ORIGINAL-CALLER-DATA")
    readonly = os.open(f"/proc/self/fd/{owner}", os.O_RDONLY)
    try:
        with pytest.raises(OracleContractError):
            run_argv(
                (
                    sys.executable,
                    "-c",
                    (
                        "import os; "
                        f"upgraded=os.open('/proc/self/fd/{readonly}', os.O_RDWR); "
                        "os.pwrite(upgraded, b'PWNED!!!', 0)"
                    ),
                ),
                timeout_seconds=2,
                pass_fds=(readonly,),
            )
        assert (
            os.pread(owner, len(b"ORIGINAL-CALLER-DATA"), 0) == b"ORIGINAL-CALLER-DATA"
        )
    finally:
        os.close(readonly)
        os.close(owner)


def test_executor_denies_keyring_and_io_uring_syscalls() -> None:
    probe = r"""
import ctypes
import errno

seccomp = ctypes.CDLL("libseccomp.so.2")
seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long

def denied(name, *arguments):
    number = seccomp.seccomp_syscall_resolve_name(name.encode("ascii"))
    if number < 0:
        raise RuntimeError(name)
    ctypes.set_errno(0)
    result = libc.syscall(number, *arguments)
    return result == -1 and ctypes.get_errno() == errno.EPERM

params = ctypes.create_string_buffer(256)
blocked = []
if denied("keyctl", 0, -3, 0, 0, 0):
    blocked.append("keyctl")
if denied("io_uring_setup", 1, ctypes.byref(params)):
    blocked.append("io_uring_setup")
print(",".join(blocked))
"""
    output = run_argv(
        (sys.executable, "-c", probe),
        timeout_seconds=2,
        max_output_bytes=1024,
    )
    assert output.stdout == b"keyctl,io_uring_setup\n"


def test_caller_death_kills_complete_oracle_process_tree(tmp_path: Path) -> None:
    output_directory = tmp_path / "caller-death-output"
    output_directory.mkdir()
    ready = output_directory / "ready"
    survived = output_directory / "survived"
    outer_source = f"""
import os
import sys
from benchmarks.oracles.execution import run_argv

directory_fd = os.open({str(output_directory)!r}, os.O_RDONLY | os.O_DIRECTORY)
try:
    ready = f"/proc/self/fd/{{directory_fd}}/ready"
    survived = f"/proc/self/fd/{{directory_fd}}/survived"
    solver = (
        "from pathlib import Path; import time; "
        f"Path({{ready!r}}).write_text('ready'); time.sleep(1.2); "
        f"Path({{survived!r}}).write_text('escaped')"
    )
    run_argv(
        (sys.executable, "-c", solver),
        timeout_seconds=10,
        pass_fds=(directory_fd,),
        writable_directory_fds=(directory_fd,),
    )
finally:
    os.close(directory_fd)
"""
    outer = subprocess.Popen(
        (sys.executable, "-c", outer_source),
        cwd=Path(__file__).resolve().parents[2],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5.0
        while not ready.exists() and outer.poll() is None:
            if time.monotonic() >= deadline:
                break
            time.sleep(0.02)
        assert ready.read_bytes() == b"ready"
        os.kill(outer.pid, signal.SIGKILL)
        outer.wait(timeout=2)
        time.sleep(1.5)
        assert not survived.exists()
    finally:
        if outer.poll() is None:
            outer.kill()
            outer.wait(timeout=2)


def test_solver_resource_limits_are_bounded() -> None:
    probe = (
        "import json, resource; "
        "names=('RLIMIT_AS','RLIMIT_CORE','RLIMIT_CPU','RLIMIT_FSIZE',"
        "'RLIMIT_NOFILE','RLIMIT_NPROC'); "
        "print(json.dumps({name: resource.getrlimit(getattr(resource,name)) "
        "for name in names}, sort_keys=True))"
    )
    output = run_argv(
        (sys.executable, "-c", probe),
        timeout_seconds=2,
        max_output_bytes=4096,
    )
    limits = json.loads(output.stdout)
    assert limits["RLIMIT_AS"][0] <= 32 * 1024**3
    assert limits["RLIMIT_CORE"] == [0, 0]
    assert 1 <= limits["RLIMIT_CPU"][0] <= 129
    assert limits["RLIMIT_FSIZE"][0] <= 2 * 1024**3
    assert limits["RLIMIT_NOFILE"][0] <= 4096
    assert limits["RLIMIT_NPROC"][0] <= 512
