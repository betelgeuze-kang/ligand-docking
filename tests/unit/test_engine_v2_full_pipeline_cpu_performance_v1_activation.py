from __future__ import annotations

import errno
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import sys
import types

import pytest

from betelgeuze_engine_v2.docking import (
    full_pipeline_cpu_performance_v1_activation as activation,
)
from tools import (
    preflight_engine_v2_full_pipeline_cpu_performance_v1_activation as preflight,
)


def _module(name: str, *, origin: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name=name, loader=None)
    module.__spec__.origin = origin
    return module


def _executable_closure(rows: list[dict[str, object]]) -> dict[str, object]:
    ordered = sorted(rows, key=lambda row: str(row["path"]))
    return {
        "schema_id": activation.DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
        "executable_file_count": len(ordered),
        "total_bytes": sum(int(row["size_bytes"]) for row in ordered),
        "virtual_executable_mappings": ["[vdso]", "[vsyscall]"],
        "rows_sha256": activation.manifest_rows_sha256(ordered),
        "rows": ordered,
    }


def test_stdlib_import_closure_is_rederivable() -> None:
    modules = {
        "synthetic_builtin": _module("synthetic_builtin", origin="built-in"),
        "synthetic_frozen": _module("synthetic_frozen", origin="frozen"),
    }

    first = activation.derive_stdlib_import_closure(modules)
    second = activation.derive_stdlib_import_closure(modules)

    assert first == second
    assert first == {
        "schema_id": activation.STDLIB_CLOSURE_SCHEMA_ID,
        "module_count": 2,
        "file_backed_module_count": 0,
        "file_backed_total_bytes": 0,
        "cached_bytecode_file_count": 0,
        "cached_bytecode_total_bytes": 0,
        "rows_sha256": activation.manifest_rows_sha256(first["rows"]),
        "rows": [
            {"module": "synthetic_builtin", "origin": "built-in"},
            {"module": "synthetic_frozen", "origin": "frozen"},
        ],
    }


def test_stdlib_import_closure_binds_declared_bytecode_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "fixture.py"
    cache = tmp_path / "__pycache__/fixture.cpython-310.pyc"
    cache.parent.mkdir()
    source.write_bytes(b"SOURCE\n")
    cache.write_bytes(b"CACHE-V1\n")
    module = _module("fixture", origin=str(source))
    module.__file__ = str(source)
    module.__cached__ = str(cache)

    def read_fixture(
        path: Path,
        *,
        name: str,
        allowed_owner_uids: tuple[int, ...],
    ) -> bytes:
        del name, allowed_owner_uids
        return path.read_bytes()

    monkeypatch.setattr(activation, "PYTHON_STDLIB_ROOT", tmp_path)
    monkeypatch.setattr(activation, "_read_stable_regular_file", read_fixture)

    first = activation.derive_stdlib_import_closure({"fixture": module})
    cached = first["rows"][0]["cached_bytecode"]
    assert cached == {
        "path": "__pycache__/fixture.cpython-310.pyc",
        "present": True,
        "sha256": activation.sha256_bytes(b"CACHE-V1\n"),
        "size_bytes": len(b"CACHE-V1\n"),
    }
    assert first["cached_bytecode_file_count"] == 1
    assert first["cached_bytecode_total_bytes"] == len(b"CACHE-V1\n")

    cache.write_bytes(b"CACHE-V2\n")
    second = activation.derive_stdlib_import_closure({"fixture": module})
    assert second["rows_sha256"] != first["rows_sha256"]


def test_dynamic_library_closure_is_rederivable(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    package = site_packages / "native"
    package.mkdir(parents=True)
    library = package / "native executable fixture"
    library.write_bytes(b"exact-native-fixture")
    library.chmod(0o600)
    metadata = library.stat()
    device = f"{os.major(metadata.st_dev):x}:{os.minor(metadata.st_dev):x}"
    process_maps = tmp_path / "maps"
    process_maps.write_text(
        f"1000-2000 r-xp 00000000 {device} {metadata.st_ino} {library}\n"
        "2000-3000 r-xp 00000000 00:00 0 [vdso]\n",
        encoding="ascii",
    )
    process_maps.chmod(0o600)

    observed = activation.derive_dynamic_library_closure(
        site_packages=site_packages,
        process_maps_path=process_maps,
        required_executable_file_identity=(
            os.major(metadata.st_dev),
            os.minor(metadata.st_dev),
            metadata.st_ino,
        ),
    )

    expected_row = {
        "path": "qualified_site_packages/native/native executable fixture",
        "sha256": hashlib.sha256(b"exact-native-fixture").hexdigest(),
        "size_bytes": len(b"exact-native-fixture"),
    }
    assert observed == {
        "schema_id": activation.DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
        "executable_file_count": 1,
        "total_bytes": len(b"exact-native-fixture"),
        "virtual_executable_mappings": ["[vdso]"],
        "rows_sha256": activation.manifest_rows_sha256([expected_row]),
        "rows": [expected_row],
    }


def test_dynamic_library_closure_rejects_unavailable_mapping(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    process_maps = tmp_path / "maps"
    process_maps.write_text(
        "1000-2000 r-xp 00000000 00:00 1 /absent/native_fixture.so\n",
        encoding="ascii",
    )

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="mapped executable file is unavailable",
    ):
        activation.derive_dynamic_library_closure(
            site_packages=site_packages,
            process_maps_path=process_maps,
        )


def test_dynamic_library_closure_rejects_deleted_mapping(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    executable = tmp_path / "deleted executable"
    executable.write_bytes(b"mapped")
    metadata = executable.stat()
    device = f"{os.major(metadata.st_dev):x}:{os.minor(metadata.st_dev):x}"
    process_maps = tmp_path / "maps"
    process_maps.write_text(
        f"1000-2000 r-xp 00000000 {device} {metadata.st_ino} {executable} (deleted)\n",
        encoding="ascii",
    )

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="deleted executable file mapping is forbidden",
    ):
        activation.derive_dynamic_library_closure(
            site_packages=site_packages,
            process_maps_path=process_maps,
        )


def test_dynamic_library_closure_rejects_anonymous_executable_mapping(
    tmp_path: Path,
) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    process_maps = tmp_path / "maps"
    process_maps.write_text(
        "1000-2000 rwxp 00000000 00:00 0 [jit-cache]\n",
        encoding="ascii",
    )

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="unexpected anonymous executable mapping",
    ):
        activation.derive_dynamic_library_closure(
            site_packages=site_packages,
            process_maps_path=process_maps,
        )


def test_dynamic_library_closure_rejects_mapping_device_inode_drift(
    tmp_path: Path,
) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    executable = tmp_path / "mapped-executable"
    executable.write_bytes(b"mapped")
    executable.chmod(0o600)
    process_maps = tmp_path / "maps"
    process_maps.write_text(
        f"1000-2000 r-xp 00000000 01:02 3 {executable}\n",
        encoding="ascii",
    )

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="device/inode differs from the executable mapping",
    ):
        activation.derive_dynamic_library_closure(
            site_packages=site_packages,
            process_maps_path=process_maps,
        )


def test_native_initialization_delta_accepts_only_the_sealed_extension() -> None:
    dependency = {
        "path": "system:/usr/lib/exact-dependency.so",
        "sha256": "a" * 64,
        "size_bytes": 17,
    }
    native = {
        "path": activation.SEALED_NATIVE_EXTENSION_IDENTITY,
        "sha256": "b" * 64,
        "size_bytes": 23,
    }

    activation.require_exact_native_initialization_delta(
        _executable_closure([dependency]),
        _executable_closure([native, dependency]),
        native_extension_sha256="b" * 64,
        native_extension_size_bytes=23,
    )


def test_native_initialization_delta_rejects_a_late_dependency() -> None:
    dependency = {
        "path": "system:/usr/lib/exact-dependency.so",
        "sha256": "a" * 64,
        "size_bytes": 17,
    }
    native = {
        "path": activation.SEALED_NATIVE_EXTENSION_IDENTITY,
        "sha256": "b" * 64,
        "size_bytes": 23,
    }
    late = {
        "path": "system:/usr/lib/late-constructor.so",
        "sha256": "c" * 64,
        "size_bytes": 29,
    }

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="executable mapping delta changed",
    ):
        activation.require_exact_native_initialization_delta(
            _executable_closure([dependency]),
            _executable_closure([native, dependency, late]),
            native_extension_sha256="b" * 64,
            native_extension_size_bytes=23,
        )


def test_native_initialization_delta_rejects_dependency_identity_drift() -> None:
    preinit_dependency = {
        "path": "system:/usr/lib/exact-dependency.so",
        "sha256": "a" * 64,
        "size_bytes": 17,
    }
    postinit_dependency = dict(preinit_dependency)
    postinit_dependency["sha256"] = "c" * 64
    native = {
        "path": activation.SEALED_NATIVE_EXTENSION_IDENTITY,
        "sha256": "b" * 64,
        "size_bytes": 23,
    }

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="changed an authenticated dependency mapping",
    ):
        activation.require_exact_native_initialization_delta(
            _executable_closure([preinit_dependency]),
            _executable_closure([native, postinit_dependency]),
            native_extension_sha256="b" * 64,
            native_extension_size_bytes=23,
        )


def test_loader_bootstrap_execs_the_exact_loader_with_a_clean_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class BootstrapExecCalled(RuntimeError):
        pass

    def fake_execve(
        path: Path, arguments: list[str], environment: dict[str, str]
    ) -> None:
        marker = environment[preflight._EXACT_LOADER_HANDSHAKE_ENVIRONMENT_KEY]
        version, raw_descriptor, expected_sha256 = marker.split(":")
        assert version == preflight._EXACT_LOADER_HANDSHAKE_VERSION
        preflight._validate_exact_loader_handshake_descriptor(
            int(raw_descriptor),
            expected_sha256=expected_sha256,
        )
        captured.update(path=path, arguments=arguments, environment=environment)
        raise BootstrapExecCalled

    monkeypatch.setattr(preflight.os, "execve", fake_execve)
    monkeypatch.setattr(preflight.sys, "executable", "/exact/runtime/bin/python3")
    monkeypatch.setattr(preflight.sys, "argv", ["preflight.py", "--fixture"])
    monkeypatch.setattr(preflight.os, "environ", {"LD_LIBRARY_PATH": "/attacker"})

    with pytest.raises(BootstrapExecCalled):
        preflight._require_exact_loader_bootstrap()

    assert captured["path"] == preflight._EXACT_DYNAMIC_LOADER
    arguments = captured["arguments"]
    assert isinstance(arguments, list)
    assert "--inhibit-cache" in arguments
    assert "--glibc-hwcaps-mask" in arguments
    assert "--preload" in arguments
    environment = captured["environment"]
    assert isinstance(environment, dict)
    marker = environment.pop(preflight._EXACT_LOADER_HANDSHAKE_ENVIRONMENT_KEY)
    expected_environment = dict(preflight._EXACT_LOADER_BOOTSTRAP_ENVIRONMENT)
    expected_environment.pop(preflight._EXACT_LOADER_HANDSHAKE_ENVIRONMENT_KEY)
    assert environment == expected_environment
    assert marker.startswith(preflight._EXACT_LOADER_HANDSHAKE_VERSION + ":")
    assert "LD_LIBRARY_PATH" not in captured["environment"]


def test_loader_bootstrap_consumes_sealed_one_time_handshake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor, marker = preflight._create_exact_loader_handshake()
    environment = dict(preflight._EXACT_LOADER_BOOTSTRAP_ENVIRONMENT)
    environment[preflight._EXACT_LOADER_HANDSHAKE_ENVIRONMENT_KEY] = marker
    monkeypatch.setattr(preflight.os, "environ", environment)

    preflight._require_exact_loader_bootstrap()

    assert environment == preflight._EXACT_LOADER_BOOTSTRAP_ENVIRONMENT
    with pytest.raises(OSError):
        os.fstat(descriptor)


def test_loader_bootstrap_rejects_forged_validated_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        preflight.os,
        "execve",
        lambda *_arguments, **_keywords: pytest.fail("execve must not be called"),
    )
    monkeypatch.setattr(
        preflight.os,
        "environ",
        dict(preflight._EXACT_LOADER_BOOTSTRAP_ENVIRONMENT),
    )

    with pytest.raises(RuntimeError, match="handshake marker is invalid"):
        preflight._require_exact_loader_bootstrap()


def test_loader_bootstrap_rejects_github_actions_before_exec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        preflight.os,
        "execve",
        lambda *_arguments, **_keywords: pytest.fail("execve must not be called"),
    )
    monkeypatch.setattr(preflight.os, "environ", {"GITHUB_ACTIONS": "true"})

    with pytest.raises(
        RuntimeError,
        match="GitHub Actions cannot run the exact-runtime activation preflight",
    ):
        preflight._require_exact_loader_bootstrap()


def test_native_extension_descriptor_detects_post_authentication_change(
    tmp_path: Path,
) -> None:
    extension = tmp_path / preflight._NATIVE_EXTENSION_RELATIVE_PATH
    extension.parent.mkdir(parents=True)
    original = b"A" * 64
    extension.write_bytes(original)
    extension.chmod(0o600)
    expected_sha256 = hashlib.sha256(original).hexdigest()
    descriptor, metadata = preflight._open_authenticated_native_extension(
        tmp_path,
        expected_sha256=expected_sha256,
    )
    try:
        extension.write_bytes(b"B" * 64)
        with pytest.raises(
            RuntimeError,
            match="authenticated native extension descriptor changed",
        ):
            preflight._require_native_descriptor_stable(
                descriptor,
                expected_metadata=metadata,
                expected_sha256=expected_sha256,
            )
    finally:
        os.close(descriptor)


def test_native_extension_snapshot_is_sealed_before_load(tmp_path: Path) -> None:
    extension = tmp_path / preflight._NATIVE_EXTENSION_RELATIVE_PATH
    extension.parent.mkdir(parents=True)
    original = b"immutable-native-snapshot" * 8
    extension.write_bytes(original)
    extension.chmod(0o600)
    expected_sha256 = hashlib.sha256(original).hexdigest()
    source_descriptor, _source_metadata = (
        preflight._open_authenticated_native_extension(
            tmp_path,
            expected_sha256=expected_sha256,
        )
    )
    try:
        snapshot_descriptor, snapshot_metadata = (
            preflight._create_sealed_native_extension_snapshot(
                source_descriptor,
                expected_sha256=expected_sha256,
            )
        )
    finally:
        os.close(source_descriptor)
    try:
        extension.write_bytes(b"mutable-source-drift-after-snapshot")
        preflight._require_native_snapshot_sealed(
            snapshot_descriptor,
            expected_metadata=snapshot_metadata,
            expected_sha256=expected_sha256,
        )
        with pytest.raises(OSError) as caught:
            os.pwrite(snapshot_descriptor, b"X", 0)
        assert caught.value.errno == errno.EPERM
    finally:
        os.close(snapshot_descriptor)


def test_native_extension_public_package_reexports_entrypoints() -> None:
    package = types.ModuleType("betelgeuze_engine_v2_native")
    native = types.ModuleType("betelgeuze_engine_v2_native.betelgeuze_engine_v2_native")

    def prepare() -> None:
        return None

    def parity() -> None:
        return None

    native.native_fixed64_prepare_repository_synthetic_d0_session_v1 = prepare
    native.native_fixed64_repository_synthetic_d0_cpu_parity_v1 = parity
    native.__all__ = [
        "native_fixed64_prepare_repository_synthetic_d0_session_v1",
        "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
    ]

    preflight._populate_native_package(package, native)

    assert package.native_fixed64_prepare_repository_synthetic_d0_session_v1 is prepare
    assert package.native_fixed64_repository_synthetic_d0_cpu_parity_v1 is parity
    assert package.betelgeuze_engine_v2_native is native
    assert package.__all__ == native.__all__


def test_exact_closure_rejects_semantic_drift() -> None:
    expected = {
        "schema_id": activation.STDLIB_CLOSURE_SCHEMA_ID,
        "rows": [{"module": "sys", "origin": "built-in"}],
    }
    changed = json.loads(json.dumps(expected))
    changed["rows"][0]["origin"] = "frozen"

    with pytest.raises(
        activation.FullPipelineCPUActivationError,
        match="standard-library import closure changed",
    ):
        activation.require_exact_closure(
            changed,
            expected,
            name="standard-library import closure",
        )


def test_bound_source_drift_is_rejected_before_module_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docking_root = tmp_path / "betelgeuze_engine_v2/docking"
    docking_root.mkdir(parents=True)
    source = docking_root / "fixture.py"
    source.write_text("BOUND = True\n", encoding="ascii")
    monkeypatch.setattr(
        preflight,
        "_BOUND_MODULE_ROWS",
        (("fixture", "fixture.py", "0" * 64),),
    )

    with pytest.raises(RuntimeError, match="bound source changed before import"):
        preflight._authenticate_bound_sources(repository_root=tmp_path)


def test_bound_module_executes_only_the_authenticated_bytes(tmp_path: Path) -> None:
    source = tmp_path / "authenticated_fixture.py"
    authenticated = b"VALUE = 'authenticated'\n"
    source.write_bytes(authenticated)
    source.write_bytes(b"raise AssertionError('path was reread')\n")
    qualified = "betelgeuze_engine_v2.docking.authenticated_fixture"
    sys.modules.pop(qualified, None)
    try:
        module = preflight._load_source_module(qualified, source, authenticated)
        assert getattr(module, "VALUE") == "authenticated"
        with pytest.raises(RuntimeError, match="already loaded"):
            preflight._load_source_module(qualified, source, authenticated)
    finally:
        sys.modules.pop(qualified, None)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda document: document.__setitem__("unknown_runtime_authority", False),
        lambda document: document["authority"].__setitem__(
            "molecular_execution_authorized", 0
        ),
        lambda document: document["runtime_binding"].__setitem__(
            "artifact_run_attempt", True
        ),
    ),
)
def test_runtime_activation_contract_rejects_unknown_and_type_drift(
    tmp_path: Path,
    mutate: object,
) -> None:
    repository_root = tmp_path / "repository"
    config_root = repository_root / "config"
    config_root.mkdir(parents=True)
    source = (
        Path(preflight.__file__).resolve().parents[1]
        / "config/engine_v2_full_pipeline_cpu_performance_v1_activation.json"
    )
    document = json.loads(source.read_text(encoding="ascii"))
    assert callable(mutate)
    mutate(document)
    changed = config_root / source.name
    changed.write_text(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    bootstrap_raw = Path(preflight.__file__).read_bytes()

    with pytest.raises(RuntimeError, match="exact projection changed"):
        preflight._load_activation_contract(
            repository_root=repository_root,
            bootstrap_raw=bootstrap_raw,
        )


def test_preflight_evidence_remains_non_consuming() -> None:
    evidence = activation.ActivationPreflightEvidenceV1(
        activation_sha256="a" * 64,
        profile_sha256="b" * 64,
        preinit_executable_closure_manifest_sha256="c" * 64,
        stdlib_import_closure_manifest_sha256="d" * 64,
        dynamic_library_closure_manifest_sha256="e" * 64,
        host_preflight={"qualified": True, "blockers": []},
        blockers=(),
    ).to_dict()

    assert evidence["ready"] is True
    assert evidence["imports_performed"] is True
    assert evidence["native_extension_initialized"] is True
    for key in (
        "performance_measurement_performed",
        "qualification_attempt_created",
        "qualification_consumed",
        "reservation_created",
        "molecular_execution_performed",
        "public_benchmark_performed",
        "hip_device_execution_performed",
        "product_action_performed",
    ):
        assert evidence[key] is False
    assert evidence["all_authority_false"] is True
