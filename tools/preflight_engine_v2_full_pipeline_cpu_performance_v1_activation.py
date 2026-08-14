#!/usr/bin/env python3
"""Run the exact-runtime, non-consuming full-pipeline CPU activation preflight."""

# ruff: noqa: E402 -- repository modules are loaded only after isolation checks.

from __future__ import annotations

import argparse
import fcntl
import grp
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import types
from typing import NoReturn, Sequence


_EXPECTED_INITIAL_PATHS = (
    "/usr/lib/python310.zip",
    "/usr/lib/python3.10",
    "/usr/lib/python3.10/lib-dynload",
)
_STDLIB_ZIP_PATH = Path(_EXPECTED_INITIAL_PATHS[0])
_EXPECTED_VENV_CONFIGURATION = (
    b"home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.10.12\n"
)
_MAX_SOURCE_BYTES = 4 * 1024 * 1024
_MAX_NATIVE_EXTENSION_BYTES = 16 * 1024 * 1024
_NATIVE_EXTENSION_RELATIVE_PATH = Path(
    "betelgeuze_engine_v2_native/"
    "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so"
)
_NATIVE_PACKAGE_NAME = "betelgeuze_engine_v2_native"
_NATIVE_QUALIFIED_NAME = "betelgeuze_engine_v2_native.betelgeuze_engine_v2_native"
_SEALED_NATIVE_EXTENSION_NAME = "engine-v2-native-extension-v1"
_REQUIRED_NATIVE_SNAPSHOT_SEALS = (
    fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
)
_EXACT_DYNAMIC_LOADER = Path("/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2")
_EXACT_DYNAMIC_LOADER_LIBRARY_PATH = "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
_EXACT_NATIVE_DEPENDENCY_PRELOAD_PATHS = (
    "/usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.30",
    "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1",
    "/usr/lib/x86_64-linux-gnu/libpthread.so.0",
    "/usr/lib/x86_64-linux-gnu/libm.so.6",
    "/usr/lib/x86_64-linux-gnu/libdl.so.2",
    "/usr/lib/x86_64-linux-gnu/libc.so.6",
)
_EXACT_LOADER_BOOTSTRAP_SNAPSHOT_NAME = "engine-v2-preflight-bootstrap-v1"
_EXACT_LOADER_MAX_CMDLINE_BYTES = 64 * 1024
_EXACT_LOADER_STAGE0_PREFLIGHT_SHA256_TOKEN = "__ENGINE_V2_PREFLIGHT_SHA256__"
_EXACT_LOADER_BOOTSTRAP_ENVIRONMENT = {
    "CUDA_VISIBLE_DEVICES": "",
    "HIP_VISIBLE_DEVICES": "",
    "LC_ALL": "C",
    "PATH": "/usr/bin:/bin",
    "ROCR_VISIBLE_DEVICES": "",
}
_EXACT_LOADER_STAGE0_TEMPLATE = """\
import fcntl
import hashlib
import os
import stat
import sys

if len(sys.argv) < 2:
    raise RuntimeError("exact-loader stage0 arguments are incomplete")
source_path = sys.argv[1]
expected_sha256 = "__ENGINE_V2_PREFLIGHT_SHA256__"
forwarded_arguments = sys.argv[2:]
if (
    not os.path.isabs(source_path)
    or os.path.basename(source_path)
    != "preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
    or len(expected_sha256) != 64
    or any(character not in "0123456789abcdef" for character in expected_sha256)
):
    raise RuntimeError("exact-loader stage0 source identity is invalid")
source_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
if getattr(os, "O_NOFOLLOW", 0) == 0:
    raise RuntimeError("exact-loader stage0 no-follow reads are unavailable")
source_descriptor = os.open(source_path, source_flags)
try:
    before = os.fstat(source_descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.geteuid()
        or before.st_gid != os.getegid()
        or before.st_mode & stat.S_IWOTH
        or before.st_nlink != 1
        or not 1 <= before.st_size <= 4 * 1024 * 1024
    ):
        raise RuntimeError("exact-loader stage0 source is uncontrolled")
    chunks = []
    observed = 0
    while observed <= 4 * 1024 * 1024:
        chunk = os.read(source_descriptor, min(1 << 20, 4 * 1024 * 1024 + 1 - observed))
        if not chunk:
            break
        chunks.append(chunk)
        observed += len(chunk)
    after = os.fstat(source_descriptor)
    identity_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_uid",
        "st_gid",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if observed != before.st_size or any(
        getattr(before, field) != getattr(after, field) for field in identity_fields
    ):
        raise RuntimeError("exact-loader stage0 source changed while read")
    raw = b"".join(chunks)
finally:
    os.close(source_descriptor)
if hashlib.sha256(raw).hexdigest() != expected_sha256:
    raise RuntimeError("exact-loader stage0 source digest changed")
snapshot_descriptor = os.memfd_create(
    "engine-v2-preflight-bootstrap-v1",
    flags=os.MFD_ALLOW_SEALING,
)
try:
    written = 0
    while written < len(raw):
        count = os.write(snapshot_descriptor, raw[written:])
        if count <= 0:
            raise RuntimeError("exact-loader stage0 snapshot write did not progress")
        written += count
    os.fchmod(snapshot_descriptor, 0o400)
    required_seals = (
        fcntl.F_SEAL_SEAL
        | fcntl.F_SEAL_SHRINK
        | fcntl.F_SEAL_GROW
        | fcntl.F_SEAL_WRITE
    )
    fcntl.fcntl(snapshot_descriptor, fcntl.F_ADD_SEALS, required_seals)
    if fcntl.fcntl(snapshot_descriptor, fcntl.F_GET_SEALS) != required_seals:
        raise RuntimeError("exact-loader stage0 snapshot seals changed")
except BaseException:
    os.close(snapshot_descriptor)
    raise
snapshot_path = f"/proc/self/fd/{snapshot_descriptor}"
namespace = {
    "__name__": "__main__",
    "__file__": snapshot_path,
    "__package__": None,
    "__cached__": None,
    "__engine_v2_bootstrap_source_path__": source_path,
    "__engine_v2_bootstrap_expected_sha256__": expected_sha256,
    "__engine_v2_bootstrap_snapshot_fd__": snapshot_descriptor,
}
sys.argv = [snapshot_path, *forwarded_arguments]
exec(
    compile(raw, snapshot_path, "exec", dont_inherit=True, optimize=0),
    namespace,
    namespace,
)
"""
_ACTIVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_full_pipeline_cpu_performance_activation/1.0.0"
)
_ACTIVATION_ID = "engine_v2_full_pipeline_cpu_performance_v1_activation"
_ACTIVATION_STATUS = "frozen_non_consuming_exact_main_preflight_execution_not_activated"
_PROFILE_ID = "engine_v2_full_pipeline_cpu_performance_v1"
_PROFILE_SHA256 = "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000"
_EXPECTED_SOURCE_BINDINGS = {
    "profile_sha256": _PROFILE_SHA256,
    "profile_verifier_sha256": (
        "b05d9e9710cc9594eba4a0630420dfbc1204dba9e89c63332a0f10bbc541e880"
    ),
    "measurement_core_sha256": (
        "c27657f104248973f11f6da498fc08da460cb6d4823719139762ce76b0cd18d7"
    ),
    "runner_tool_sha256": (
        "bfaf4bc25b2161a43e1e01418394c716d4b762fd39ec6708a01791159916e6e8"
    ),
    "native_consumer_sha256": (
        "ea4fb7953d2bb2c1e4e16380dd3ad362d4fa8265bf0c11d26d69dfed3cc8df25"
    ),
    "native_cpu_parity_sha256": (
        "cbff9243caea510e070067663e7c36c216afc84e226b9ade3e37b03e6ac30f75"
    ),
    "host_preflight_sha256": (
        "236496cb7342040191db51f6c801948ab1c6b859d09a85b35e3c8a9c00a38adf"
    ),
    "merged_main_commit_sha256": (
        "1b478ee3b9737e9d50fc854fb4bde93cbd1efd48015a27df52199a698d17e82e"
    ),
    "merged_main_tree_sha256": (
        "69998e9df4740c927568b41e21eb8b94185d4fa3b9dd5fa37d71bcbbd5060579"
    ),
    "stdlib_import_closure_manifest_sha256": (
        "d892595cc2bb59aae3fbf7100da9e6b52809082dd5cbc2edb2646811d0b58e35"
    ),
    "preinit_executable_closure_manifest_sha256": (
        "282e17c72a82f0dc3e968e74fc2072371d7673dacf84b18985b2c2253c305558"
    ),
    "dynamic_library_closure_manifest_sha256": (
        "a5c56fd7ac0c26224e2282f88e54ff3a4e19c6a1d52263407f03d156199e7352"
    ),
}
_BOUND_MODULE_ROWS = (
    (
        "performance_sidecar",
        "performance_sidecar.py",
        "04253e3897bb5746e1c1082dbf8e27922835ffb075aeb3268c18a0895662173f",
    ),
    (
        "full_pipeline_cpu_performance_v1_activation",
        "full_pipeline_cpu_performance_v1_activation.py",
        "b53633b1219bd1f6ca283219e2879ae9b14ee8f0450a14251e689b5433c2cee0",
    ),
    (
        "full_pipeline_cpu_performance_v1",
        "full_pipeline_cpu_performance_v1.py",
        _EXPECTED_SOURCE_BINDINGS["measurement_core_sha256"],
    ),
    (
        "native_fixed64_consumers",
        "native_fixed64_consumers.py",
        _EXPECTED_SOURCE_BINDINGS["native_consumer_sha256"],
    ),
    (
        "native_cpu_parity",
        "native_cpu_parity.py",
        _EXPECTED_SOURCE_BINDINGS["native_cpu_parity_sha256"],
    ),
    (
        "performance_host_preflight_v3",
        "performance_host_preflight_v3.py",
        _EXPECTED_SOURCE_BINDINGS["host_preflight_sha256"],
    ),
)


def _fail(message: str) -> NoReturn:
    raise RuntimeError(
        "full-pipeline CPU activation preflight rejected runtime: " + message
    )


def _read_exact_proc_cmdline() -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    if getattr(os, "O_NOFOLLOW", 0) == 0:
        _fail("safe procfs cmdline reads are unavailable")
    try:
        descriptor = os.open("/proc/self/cmdline", flags)
    except OSError as exc:
        raise RuntimeError("kernel process command line is unavailable") from exc
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        observed = 0
        while observed <= _EXACT_LOADER_MAX_CMDLINE_BYTES:
            chunk = os.read(
                descriptor,
                min(4096, _EXACT_LOADER_MAX_CMDLINE_BYTES + 1 - observed),
            )
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_uid",
        "st_gid",
        "st_nlink",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    raw = b"".join(chunks)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.geteuid()
        or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        or any(
            getattr(before, field) != getattr(after, field) for field in identity_fields
        )
        or not raw
        or len(raw) > _EXACT_LOADER_MAX_CMDLINE_BYTES
        or not raw.endswith(b"\0")
    ):
        _fail("kernel process command line is invalid or changed")
    return raw


def _render_exact_loader_stage0(expected_sha256: str) -> str:
    if (
        type(expected_sha256) is not str
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
        or _EXACT_LOADER_STAGE0_TEMPLATE.count(
            _EXACT_LOADER_STAGE0_PREFLIGHT_SHA256_TOKEN
        )
        != 1
    ):
        _fail("exact-loader stage0 rendering identity is invalid")
    rendered = _EXACT_LOADER_STAGE0_TEMPLATE.replace(
        _EXACT_LOADER_STAGE0_PREFLIGHT_SHA256_TOKEN,
        expected_sha256,
    )
    if _EXACT_LOADER_STAGE0_PREFLIGHT_SHA256_TOKEN in rendered:
        _fail("exact-loader stage0 rendering retained its digest token")
    return rendered


def _exact_loader_stage0_arguments(
    *, source_path: Path, expected_sha256: str
) -> list[str]:
    launcher = Path(sys.executable).absolute()
    stage0_source = _render_exact_loader_stage0(expected_sha256)
    return [
        str(_EXACT_DYNAMIC_LOADER),
        "--inhibit-cache",
        "--library-path",
        _EXACT_DYNAMIC_LOADER_LIBRARY_PATH,
        "--glibc-hwcaps-mask",
        "",
        "--preload",
        ":".join(_EXACT_NATIVE_DEPENDENCY_PRELOAD_PATHS),
        "--argv0",
        str(launcher),
        str(launcher),
        "-I",
        "-S",
        "-B",
        "-c",
        stage0_source,
        str(source_path),
        *sys.argv[1:],
    ]


def _validate_bootstrap_snapshot(descriptor: int, *, expected_sha256: str) -> bytes:
    if type(descriptor) is not int or descriptor < 3:
        _fail("bootstrap snapshot descriptor is invalid")
    try:
        metadata = os.fstat(descriptor)
        descriptor_flags = fcntl.fcntl(descriptor, fcntl.F_GETFD)
        seals = fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)
        target = os.readlink(f"/proc/self/fd/{descriptor}")
        raw = os.pread(descriptor, _MAX_SOURCE_BYTES + 1, 0)
    except OSError as exc:
        raise RuntimeError("bootstrap snapshot descriptor is unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or stat.S_IMODE(metadata.st_mode) != 0o400
        or metadata.st_nlink != 0
        or not 1 <= metadata.st_size <= _MAX_SOURCE_BYTES
        or descriptor_flags & fcntl.FD_CLOEXEC
        or seals != _REQUIRED_NATIVE_SNAPSHOT_SEALS
        or target != f"/memfd:{_EXACT_LOADER_BOOTSTRAP_SNAPSHOT_NAME} (deleted)"
        or len(raw) != metadata.st_size
        or hashlib.sha256(raw).hexdigest() != expected_sha256
    ):
        _fail("authenticated immutable bootstrap snapshot changed")
    return raw


def _require_exact_loader_bootstrap() -> tuple[Path, int, bytes]:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        _fail("GitHub Actions cannot run the exact-runtime activation preflight")
    source_path_value = globals().get("__engine_v2_bootstrap_source_path__")
    expected_sha256 = globals().get("__engine_v2_bootstrap_expected_sha256__")
    descriptor = globals().get("__engine_v2_bootstrap_snapshot_fd__")
    if (
        type(source_path_value) is not str
        or not source_path_value
        or type(expected_sha256) is not str
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
        or type(descriptor) is not int
    ):
        _fail("preflight must be launched through the authenticated stage0 snapshot")
    source_path = Path(source_path_value)
    snapshot_path = f"/proc/self/fd/{descriptor}"
    if (
        not source_path.is_absolute()
        or Path(__file__).absolute() != Path(snapshot_path)
        or sys.argv[0] != snapshot_path
        or dict(os.environ) != _EXACT_LOADER_BOOTSTRAP_ENVIRONMENT
    ):
        _fail("authenticated stage0 bootstrap process state changed")
    try:
        executable_target = os.readlink("/proc/self/exe")
    except OSError as exc:
        raise RuntimeError("kernel process executable identity is unavailable") from exc
    expected_arguments = _exact_loader_stage0_arguments(
        source_path=source_path,
        expected_sha256=expected_sha256,
    )
    expected_cmdline = (
        b"\0".join(os.fsencode(value) for value in expected_arguments) + b"\0"
    )
    if (
        executable_target != str(_EXACT_DYNAMIC_LOADER)
        or _read_exact_proc_cmdline() != expected_cmdline
    ):
        _fail("kernel process identity does not prove the exact loader invocation")
    raw = _validate_bootstrap_snapshot(
        descriptor,
        expected_sha256=expected_sha256,
    )
    return source_path, descriptor, raw


def _require_private_effective_group() -> None:
    try:
        account = pwd.getpwuid(os.geteuid())
        group = grp.getgrgid(os.getegid())
        primary_accounts = tuple(
            entry.pw_name for entry in pwd.getpwall() if entry.pw_gid == os.getegid()
        )
    except KeyError:
        _fail("effective account or group identity is unavailable")
    if (
        account.pw_gid != os.getegid()
        or primary_accounts != (account.pw_name,)
        or any(name != account.pw_name for name in group.gr_mem)
    ):
        _fail("effective account group is not private")


def _require_isolated_bootstrap() -> tuple[Path, bytes]:
    source_path, descriptor, raw = _require_exact_loader_bootstrap()
    try:
        if tuple(sys.path) != _EXPECTED_INITIAL_PATHS:
            _fail("isolated standard-library path set changed")
        try:
            _STDLIB_ZIP_PATH.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RuntimeError(
                "isolated standard-library zip state is ambiguous"
            ) from exc
        else:
            _fail("isolated standard-library zip must be absent")
        if not (
            sys.flags.isolated == 1
            and sys.flags.ignore_environment == 1
            and sys.flags.no_site == 1
            and sys.flags.no_user_site == 1
            and sys.flags.dont_write_bytecode == 1
            and sys.flags.hash_randomization == 1
            and sys.flags.optimize == 0
            and sys.pycache_prefix is None
        ):
            _fail("preflight requires exact CPython -I -S -B flags")
        if hasattr(sys.flags, "safe_path"):
            _fail("unexpected safe_path field appeared in the pinned CPython lane")
        _require_private_effective_group()
    finally:
        os.close(descriptor)
    return source_path, raw


def _require_owner_directory(path: Path, *, name: str) -> Path:
    try:
        unresolved = path.absolute()
        resolved = path.resolve(strict=True)
        metadata = unresolved.lstat()
    except OSError as exc:
        raise RuntimeError(f"{name} is unavailable") from exc
    if unresolved != resolved or not stat.S_ISDIR(metadata.st_mode):
        _fail(f"{name} must be a real directory without symlinks")
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or metadata.st_mode & stat.S_IWOTH
    ):
        _fail(f"{name} is not account-controlled")
    return resolved


def _read_owner_source(path: Path, *, name: str) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    if getattr(os, "O_NOFOLLOW", 0) == 0:
        _fail("safe no-follow source reads are unavailable")
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError(f"{name} cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_gid != os.getegid()
            or before.st_mode & stat.S_IWOTH
            or before.st_nlink != 1
            or not 1 <= before.st_size <= _MAX_SOURCE_BYTES
        ):
            _fail(f"{name} is not an owner-controlled bounded source file")
        chunks: list[bytes] = []
        observed = 0
        while observed <= _MAX_SOURCE_BYTES:
            chunk = os.read(
                descriptor,
                min(1 << 20, _MAX_SOURCE_BYTES + 1 - observed),
            )
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        identity = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if observed != before.st_size or any(
            getattr(before, field) != getattr(after, field) for field in identity
        ):
            _fail(f"{name} changed while read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _install_package_stub(name: str, path: Path) -> None:
    module = types.ModuleType(name)
    module.__file__ = str(path / "__init__.py")
    module.__package__ = name
    module.__path__ = [str(path)]
    module.__spec__ = importlib.machinery.ModuleSpec(
        name=name,
        loader=None,
        is_package=True,
    )
    sys.modules[name] = module


def _load_source_module(name: str, path: Path, raw: bytes) -> types.ModuleType:
    if name in sys.modules:
        _fail(f"bound source module was already loaded: {name}")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition(".")[0]
    module.__loader__ = None
    module.__spec__ = importlib.machinery.ModuleSpec(name=name, loader=None)
    sys.modules[name] = module
    try:
        code = compile(raw, str(path), "exec", dont_inherit=True, optimize=0)
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            _fail(f"activation contract has duplicate key: {key}")
        document[key] = value
    return document


def _reject_json_float(value: str) -> NoReturn:
    _fail(f"activation contract contains a non-integer number: {value}")


def _exact_json_equal(observed: object, expected: object) -> bool:
    if type(observed) is not type(expected):
        return False
    if type(expected) is dict:
        observed_mapping = observed
        expected_mapping = expected
        return bool(
            observed_mapping.keys() == expected_mapping.keys()
            and all(
                _exact_json_equal(observed_mapping[key], expected_mapping[key])
                for key in expected_mapping
            )
        )
    if type(expected) is list:
        observed_rows = observed
        expected_rows = expected
        return bool(
            len(observed_rows) == len(expected_rows)
            and all(
                _exact_json_equal(observed_value, expected_value)
                for observed_value, expected_value in zip(
                    observed_rows, expected_rows, strict=True
                )
            )
        )
    return bool(observed == expected)


def _expected_activation_contract(*, bootstrap_sha256: str) -> dict[str, object]:
    false_authority = {
        key: False
        for key in (
            "fresh_holdout_execution_authorized",
            "hip_device_execution_authorized",
            "historical_ab_execution_authorized",
            "molecular_execution_authorized",
            "product_execution_authorized",
            "product_performance_claim_authorized",
            "public_benchmark_authorized",
            "reservation_authorized",
            "scientific_claim_authorized",
            "stage0_admission_authorized",
            "synthetic_cpu_performance_qualification_authorized",
        )
    }
    false_restrictions = {
        key: False
        for key in (
            "actual_molecular_execution_allowed",
            "caller_science_input_allowed",
            "fresh_or_historical_case_input_allowed",
            "github_actions_production_authority_allowed",
            "hip_device_execution_allowed",
            "performance_measurement_allowed",
            "product_or_public_performance_claim_allowed",
            "qualification_consumption_allowed",
            "reservation_allowed",
            "result_dependent_configuration_allowed",
            "test_double_production_authority_allowed",
        )
    }
    return {
        "activation_id": _ACTIVATION_ID,
        "authority": false_authority,
        "closure_manifests": {
            "dynamic_library_closure": {
                "executable_file_count": 21,
                "manifest_sha256": _EXPECTED_SOURCE_BINDINGS[
                    "dynamic_library_closure_manifest_sha256"
                ],
                "path": (
                    "config/engine_v2_full_pipeline_cpu_performance_v1_"
                    "dynamic_library_closure.json"
                ),
                "total_bytes": 19_879_272,
                "virtual_executable_mappings": ["[vdso]", "[vsyscall]"],
            },
            "preinit_executable_closure": {
                "executable_file_count": 20,
                "manifest_sha256": _EXPECTED_SOURCE_BINDINGS[
                    "preinit_executable_closure_manifest_sha256"
                ],
                "path": (
                    "config/engine_v2_full_pipeline_cpu_performance_v1_"
                    "preinit_executable_closure.json"
                ),
                "total_bytes": 17_279_568,
                "virtual_executable_mappings": ["[vdso]", "[vsyscall]"],
            },
            "stdlib_import_closure": {
                "cached_bytecode_file_count": 79,
                "cached_bytecode_total_bytes": 1_449_467,
                "file_backed_module_count": 85,
                "file_backed_total_bytes": 2_196_025,
                "manifest_sha256": _EXPECTED_SOURCE_BINDINGS[
                    "stdlib_import_closure_manifest_sha256"
                ],
                "module_count": 126,
                "path": (
                    "config/engine_v2_full_pipeline_cpu_performance_v1_"
                    "stdlib_closure.json"
                ),
            },
        },
        "preflight": {
            "activation_module_sha256": _BOUND_MODULE_ROWS[1][2],
            "bootstrap_flags": ["-I", "-S", "-B"],
            "caller_science_input_allowed": False,
            "exact_dynamic_loader_path": str(_EXACT_DYNAMIC_LOADER),
            "exact_loader_environment": dict(_EXACT_LOADER_BOOTSTRAP_ENVIRONMENT),
            "exact_loader_kernel_process_identity": {
                "proc_cmdline_exact": True,
                "proc_exe_exact": True,
                "stage0_argument_vector_bound": True,
                "stage0_source_sha256": hashlib.sha256(
                    _render_exact_loader_stage0(bootstrap_sha256).encode("ascii")
                ).hexdigest(),
            },
            "immutable_bootstrap_snapshot": {
                "descriptor_cloexec": False,
                "descriptor_mode": "0400",
                "descriptor_name": _EXACT_LOADER_BOOTSTRAP_SNAPSHOT_NAME,
                "descriptor_seals": [
                    "F_SEAL_SEAL",
                    "F_SEAL_SHRINK",
                    "F_SEAL_GROW",
                    "F_SEAL_WRITE",
                ],
                "exact_source_sha256_required": True,
                "launched_from_snapshot_required": True,
                "zero_link_count_required": True,
            },
            "exact_loader_inhibit_cache": True,
            "exact_loader_library_path": _EXACT_DYNAMIC_LOADER_LIBRARY_PATH,
            "exact_loader_preload_paths": list(_EXACT_NATIVE_DEPENDENCY_PRELOAD_PATHS),
            "exact_native_extension_import_required": True,
            "exact_preinit_closure_required": True,
            "github_actions_preflight_allowed": False,
            "host_preflight_required": True,
            "molecular_input_allowed": False,
            "performance_measurement_allowed": False,
            "performance_sidecar_sha256": _BOUND_MODULE_ROWS[0][2],
            "preflight_tool_sha256": bootstrap_sha256,
            "native_initialization_delta_exact": True,
            "qualification_state_write_allowed": False,
            "reservation_allowed": False,
        },
        "profile_id": _PROFILE_ID,
        "profile_sha256": _PROFILE_SHA256,
        "restrictions": false_restrictions,
        "runner": {
            "activation_contract_allows_live_execution": False,
            "activation_contract_present": True,
            "exactly_once_local_synthetic_attempt_required": True,
            "github_actions_live_execution_allowed": False,
            "live_synthetic_local_execution_implemented": False,
            "profile_change_after_activation_allowed": False,
            "qualification_attempt_consumed": False,
            "reservation_created": False,
            "runner_remains_fail_closed": True,
        },
        "runtime_binding": {
            "abi": "cp310-cp310",
            "artifact_contract_sha256": (
                "195abc14487ccec4d0f8065fa0e642337ce42691cebee4f47106b94bd2d0ebe8"
            ),
            "artifact_id": 9_213_296_947,
            "artifact_run_attempt": 1,
            "artifact_run_id": 31_785_070_195,
            "artifact_workflow_head_sha": ("3330faa43c7fc8640d89babd84ac444c5959157c"),
            "native_extension_sha256": (
                "ff7b5e6ba7c0e250cf739292d34c562d0bd142d5f7f6c842c5c191d42b2504e1"
            ),
            "python_executable_sha256": (
                "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86"
            ),
            "python_shared_library_sha256": (
                "1ece943a1641101b1c678b553a7a0fbb6683ff0ad76f7ebce9f8844354e3f153"
            ),
            "runtime_scope_manifest_sha256": (
                "72b90f500af43c921ce0b8f7d6774c5e99a7e4f3fe366478b3fc33b524b4b404"
            ),
        },
        "schema_id": _ACTIVATION_SCHEMA_ID,
        "source_bindings": dict(_EXPECTED_SOURCE_BINDINGS),
        "source_foundation": {
            "merged_main_commit_object_encoding": "git_cat_file_commit_raw_v1",
            "merged_main_commit_oid": "38c16136a1e2cc126517ff9b50a05f06c5795adb",
            "merged_main_commit_sha256": _EXPECTED_SOURCE_BINDINGS[
                "merged_main_commit_sha256"
            ],
            "merged_main_tree_manifest_encoding": ("git_ls_tree_r_full_tree_z_v1"),
            "merged_main_tree_oid": "e36d1cf0915350556ac4202e11d6176fabf5e797",
            "merged_main_tree_sha256": _EXPECTED_SOURCE_BINDINGS[
                "merged_main_tree_sha256"
            ],
        },
        "status": _ACTIVATION_STATUS,
    }


def _load_activation_contract(
    *, repository_root: Path, bootstrap_raw: bytes
) -> tuple[dict[str, object], bytes]:
    raw = _read_owner_source(
        repository_root
        / "config/engine_v2_full_pipeline_cpu_performance_v1_activation.json",
        name="full-pipeline CPU activation contract",
    )
    try:
        document = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_float,
        )
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("activation contract cannot be decoded safely") from exc
    if type(document) is not dict:
        _fail("activation contract must be an exact object")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if raw != canonical:
        _fail("activation contract is not canonical indented JSON")
    expected = _expected_activation_contract(
        bootstrap_sha256=hashlib.sha256(bootstrap_raw).hexdigest()
    )
    if not _exact_json_equal(document, expected):
        _fail("activation contract exact projection changed")
    return document, raw


def _authenticate_bound_sources(
    *, repository_root: Path
) -> tuple[Path, dict[str, bytes]]:
    package_root = _require_owner_directory(
        repository_root / "betelgeuze_engine_v2",
        name="Engine V2 package root",
    )
    docking_root = _require_owner_directory(
        package_root / "docking",
        name="Engine V2 docking root",
    )
    sources: dict[str, bytes] = {}
    for short_name, file_name, expected_sha256 in _BOUND_MODULE_ROWS:
        raw = _read_owner_source(
            docking_root / file_name,
            name=f"bound source {short_name}",
        )
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            _fail(f"bound source changed before import: {short_name}")
        sources[short_name] = raw
    return docking_root, sources


def _load_closure_manifest(
    *, repository_root: Path, relative_path: str, binding_name: str, schema_id: str
) -> tuple[dict[str, object], str]:
    raw = _read_owner_source(
        repository_root / relative_path,
        name=f"runtime closure manifest {binding_name}",
    )
    digest = hashlib.sha256(raw).hexdigest()
    if digest != _EXPECTED_SOURCE_BINDINGS[binding_name]:
        _fail(f"runtime closure manifest changed: {binding_name}")
    try:
        document = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_float,
        )
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("runtime closure manifest cannot be decoded safely") from exc
    if type(document) is not dict or document.get("schema_id") != schema_id:
        _fail(f"runtime closure manifest schema changed: {binding_name}")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if raw != canonical:
        _fail(f"runtime closure manifest is not canonical: {binding_name}")
    return document, digest


def _require_runtime_root(runtime_root: Path) -> tuple[Path, Path]:
    runtime_root = _require_owner_directory(runtime_root, name="native runtime root")
    launcher = Path(sys.executable).absolute()
    if launcher.parent.parent != runtime_root:
        _fail("running interpreter is outside the supplied native runtime root")
    configuration = _read_owner_source(
        runtime_root / "pyvenv.cfg",
        name="native runtime virtual-environment configuration",
    )
    if configuration != _EXPECTED_VENV_CONFIGURATION:
        _fail("native runtime virtual-environment configuration changed")
    site_packages = _require_owner_directory(
        runtime_root / "lib/python3.10/site-packages",
        name="native runtime site-packages",
    )
    if launcher.parent != runtime_root / "bin":
        _fail("native runtime launcher escaped the runtime bin directory")
    if launcher.resolve(strict=True) != Path("/usr/bin/python3.10"):
        _fail("native runtime launcher target changed")
    return runtime_root, site_packages


def _load_bound_modules(
    *,
    repository_root: Path,
    site_packages: Path,
    authenticated_sources: dict[str, bytes],
) -> dict[str, types.ModuleType]:
    package_root = _require_owner_directory(
        repository_root / "betelgeuze_engine_v2",
        name="Engine V2 package root",
    )
    docking_root = _require_owner_directory(
        package_root / "docking", name="Engine V2 docking root"
    )
    sys.path.extend((str(repository_root), str(site_packages)))
    _install_package_stub("betelgeuze_engine_v2", package_root)
    _install_package_stub("betelgeuze_engine_v2.docking", docking_root)
    modules: dict[str, types.ModuleType] = {}
    for short_name, file_name, _expected_sha256 in _BOUND_MODULE_ROWS:
        qualified = f"betelgeuze_engine_v2.docking.{short_name}"
        modules[short_name] = _load_source_module(
            qualified,
            docking_root / file_name,
            authenticated_sources[short_name],
        )
    return modules


def _descriptor_sha256(descriptor: int, *, maximum_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    observed = 0
    while observed <= maximum_bytes:
        chunk = os.pread(
            descriptor,
            min(1 << 20, maximum_bytes + 1 - observed),
            observed,
        )
        if not chunk:
            break
        digest.update(chunk)
        observed += len(chunk)
    if observed > maximum_bytes:
        _fail("native extension exceeds its byte envelope")
    return digest.hexdigest(), observed


def _native_descriptor_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _require_native_descriptor_stable(
    descriptor: int,
    *,
    expected_metadata: os.stat_result,
    expected_sha256: str,
) -> None:
    before = os.fstat(descriptor)
    digest, size = _descriptor_sha256(
        descriptor, maximum_bytes=_MAX_NATIVE_EXTENSION_BYTES
    )
    after = os.fstat(descriptor)
    expected_identity = _native_descriptor_identity(expected_metadata)
    if (
        _native_descriptor_identity(before) != expected_identity
        or _native_descriptor_identity(after) != expected_identity
        or size != expected_metadata.st_size
        or digest != expected_sha256
    ):
        _fail("authenticated native extension descriptor changed")


def _open_authenticated_native_extension(
    site_packages: Path, *, expected_sha256: str
) -> tuple[int, os.stat_result]:
    path = site_packages / _NATIVE_EXTENSION_RELATIVE_PATH
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    if getattr(os, "O_NOFOLLOW", 0) == 0:
        _fail("safe no-follow native extension reads are unavailable")
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError("exact native extension cannot be opened safely") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_gid != os.getegid()
            or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            or metadata.st_nlink != 1
            or not 1 <= metadata.st_size <= _MAX_NATIVE_EXTENSION_BYTES
        ):
            _fail("exact native extension is not a controlled regular file")
        _require_native_descriptor_stable(
            descriptor,
            expected_metadata=metadata,
            expected_sha256=expected_sha256,
        )
        return descriptor, metadata
    except BaseException:
        os.close(descriptor)
        raise


def _require_native_snapshot_sealed(
    descriptor: int,
    *,
    expected_metadata: os.stat_result,
    expected_sha256: str,
) -> None:
    metadata = os.fstat(descriptor)
    try:
        seals = fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)
    except OSError as exc:
        raise RuntimeError("native extension snapshot seals are unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or stat.S_IMODE(metadata.st_mode) != 0o500
        or metadata.st_nlink != 0
        or seals != _REQUIRED_NATIVE_SNAPSHOT_SEALS
    ):
        _fail("native extension snapshot is not immutable")
    _require_native_descriptor_stable(
        descriptor,
        expected_metadata=expected_metadata,
        expected_sha256=expected_sha256,
    )


def _create_sealed_native_extension_snapshot(
    source_descriptor: int, *, expected_sha256: str
) -> tuple[int, os.stat_result]:
    if not hasattr(os, "memfd_create") or not hasattr(os, "MFD_ALLOW_SEALING"):
        _fail("sealed native extension snapshots are unavailable")
    try:
        descriptor = os.memfd_create(
            _SEALED_NATIVE_EXTENSION_NAME,
            flags=os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
        )
    except OSError as exc:
        raise RuntimeError("native extension snapshot cannot be created") from exc
    try:
        offset = 0
        while offset <= _MAX_NATIVE_EXTENSION_BYTES:
            chunk = os.pread(
                source_descriptor,
                min(1 << 20, _MAX_NATIVE_EXTENSION_BYTES + 1 - offset),
                offset,
            )
            if not chunk:
                break
            written = 0
            while written < len(chunk):
                count = os.pwrite(
                    descriptor,
                    chunk[written:],
                    offset + written,
                )
                if count <= 0:
                    _fail("native extension snapshot write did not progress")
                written += count
            offset += len(chunk)
        if offset > _MAX_NATIVE_EXTENSION_BYTES:
            _fail("native extension snapshot exceeds its byte envelope")
        digest, observed_size = _descriptor_sha256(
            descriptor,
            maximum_bytes=_MAX_NATIVE_EXTENSION_BYTES,
        )
        if digest != expected_sha256 or observed_size != offset:
            _fail("native extension snapshot differs from authenticated bytes")
        os.fchmod(descriptor, 0o500)
        fcntl.fcntl(
            descriptor,
            fcntl.F_ADD_SEALS,
            _REQUIRED_NATIVE_SNAPSHOT_SEALS,
        )
        metadata = os.fstat(descriptor)
        _require_native_snapshot_sealed(
            descriptor,
            expected_metadata=metadata,
            expected_sha256=expected_sha256,
        )
        return descriptor, metadata
    except BaseException:
        os.close(descriptor)
        raise


def _populate_native_package(
    package: types.ModuleType, native: types.ModuleType
) -> None:
    declared = getattr(native, "__all__", None)
    if declared is None:
        exported_names = tuple(
            sorted(name for name in vars(native) if not name.startswith("_"))
        )
    else:
        if (
            type(declared) not in {list, tuple}
            or any(type(name) is not str or not name for name in declared)
            or len(set(declared)) != len(declared)
        ):
            _fail("native extension export surface is invalid")
        exported_names = tuple(declared)
        package.__all__ = declared
    for name in exported_names:
        if not hasattr(native, name):
            _fail("native extension declared an absent export")
        setattr(package, name, getattr(native, name))
    package.betelgeuze_engine_v2_native = native
    package.__doc__ = native.__doc__


def _remove_loaded_native_extension() -> None:
    sys.modules.pop(_NATIVE_QUALIFIED_NAME, None)
    sys.modules.pop(_NATIVE_PACKAGE_NAME, None)


def _require_native_extension(
    site_packages: Path, *, expected_sha256: str
) -> tuple[types.ModuleType, int, os.stat_result]:
    package_name = _NATIVE_PACKAGE_NAME
    qualified_name = _NATIVE_QUALIFIED_NAME
    if package_name in sys.modules or qualified_name in sys.modules:
        _fail("exact native extension was already loaded")
    package_root = _require_owner_directory(
        site_packages / package_name,
        name="native extension package root",
    )
    source_descriptor, _source_metadata = _open_authenticated_native_extension(
        site_packages, expected_sha256=expected_sha256
    )
    try:
        descriptor, metadata = _create_sealed_native_extension_snapshot(
            source_descriptor,
            expected_sha256=expected_sha256,
        )
    finally:
        os.close(source_descriptor)
    descriptor_path = f"/proc/self/fd/{descriptor}"
    _install_package_stub(package_name, package_root)
    package = sys.modules[package_name]
    try:
        loader = importlib.machinery.ExtensionFileLoader(
            qualified_name, descriptor_path
        )
        specification = importlib.util.spec_from_file_location(
            qualified_name,
            descriptor_path,
            loader=loader,
        )
        if specification is None:
            _fail("exact native extension descriptor has no import specification")
        native = importlib.util.module_from_spec(specification)
        sys.modules[qualified_name] = native
        loader.exec_module(native)
        _require_native_snapshot_sealed(
            descriptor,
            expected_metadata=metadata,
            expected_sha256=expected_sha256,
        )
        _populate_native_package(package, native)
        public_package = importlib.import_module(package_name)
        if public_package is not package:
            _fail("native extension public package identity changed")
        for name in (
            "native_fixed64_prepare_repository_synthetic_d0_session_v1",
            "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
        ):
            if not callable(getattr(native, name, None)) or not callable(
                getattr(public_package, name, None)
            ):
                _fail(f"exact native extension lacks required entrypoint {name}")
    except BaseException:
        _remove_loaded_native_extension()
        os.close(descriptor)
        raise
    return native, descriptor, metadata


def derive_preflight(
    *,
    artifact_directory: Path,
    runtime_root: Path,
) -> dict[str, object]:
    """Inspect exact bytes and imports without creating an execution attempt."""

    bootstrap, bootstrap_raw = _require_isolated_bootstrap()
    repository_root = _require_owner_directory(
        bootstrap.parent.parent,
        name="repository root",
    )
    if bootstrap.parent != repository_root / "tools":
        _fail("activation preflight bootstrap escaped repository tools")
    runtime_root, site_packages = _require_runtime_root(runtime_root)
    contract, contract_raw = _load_activation_contract(
        repository_root=repository_root,
        bootstrap_raw=bootstrap_raw,
    )
    _docking_root, authenticated_sources = _authenticate_bound_sources(
        repository_root=repository_root
    )
    modules = _load_bound_modules(
        repository_root=repository_root,
        site_packages=site_packages,
        authenticated_sources=authenticated_sources,
    )
    measurement = modules["full_pipeline_cpu_performance_v1"]
    runtime_evidence = measurement.verify_local_runtime_binding(
        artifact_directory=artifact_directory,
        runtime_root=runtime_root,
    ).to_dict()
    native_extension_sha256 = str(runtime_evidence["native_extension_sha256"])
    host = modules["performance_host_preflight_v3"].derive_host_preflight_evidence_v3()
    host_document = host.to_dict()
    activation = modules["full_pipeline_cpu_performance_v1_activation"]
    observed_preinit = activation.derive_dynamic_library_closure(
        site_packages=site_packages
    )
    expected_preinit, preinit_manifest_sha256 = _load_closure_manifest(
        repository_root=repository_root,
        relative_path=(
            "config/engine_v2_full_pipeline_cpu_performance_v1_"
            "preinit_executable_closure.json"
        ),
        binding_name="preinit_executable_closure_manifest_sha256",
        schema_id=activation.DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
    )
    activation.require_exact_closure(
        observed_preinit,
        expected_preinit,
        name="pre-initialization executable-file mapping closure",
    )
    if dict(os.environ) != _EXACT_LOADER_BOOTSTRAP_ENVIRONMENT:
        _fail("exact dynamic-loader environment changed before native initialization")
    _native, native_descriptor, native_metadata = _require_native_extension(
        site_packages, expected_sha256=native_extension_sha256
    )
    try:
        observed_stdlib = activation.derive_stdlib_import_closure()
        observed_dynamic = activation.derive_dynamic_library_closure(
            site_packages=site_packages,
            required_executable_file_identity=(
                os.major(native_metadata.st_dev),
                os.minor(native_metadata.st_dev),
                native_metadata.st_ino,
            ),
            sealed_executable_descriptor=native_descriptor,
        )
        expected_stdlib, stdlib_manifest_sha256 = _load_closure_manifest(
            repository_root=repository_root,
            relative_path=(
                "config/engine_v2_full_pipeline_cpu_performance_v1_stdlib_closure.json"
            ),
            binding_name="stdlib_import_closure_manifest_sha256",
            schema_id=activation.STDLIB_CLOSURE_SCHEMA_ID,
        )
        expected_dynamic, dynamic_manifest_sha256 = _load_closure_manifest(
            repository_root=repository_root,
            relative_path=(
                "config/engine_v2_full_pipeline_cpu_performance_v1_dynamic_library_closure.json"
            ),
            binding_name="dynamic_library_closure_manifest_sha256",
            schema_id=activation.DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
        )
        activation.require_exact_closure(
            observed_stdlib,
            expected_stdlib,
            name="standard-library import closure",
        )
        activation.require_exact_closure(
            observed_dynamic,
            expected_dynamic,
            name="executable-file mapping closure",
        )
        activation.require_exact_native_initialization_delta(
            observed_preinit,
            observed_dynamic,
            native_extension_sha256=native_extension_sha256,
            native_extension_size_bytes=native_metadata.st_size,
        )
        _require_native_snapshot_sealed(
            native_descriptor,
            expected_metadata=native_metadata,
            expected_sha256=native_extension_sha256,
        )
        blockers = tuple(str(value) for value in host_document["blockers"])
        evidence = activation.ActivationPreflightEvidenceV1(
            activation_sha256=hashlib.sha256(contract_raw).hexdigest(),
            profile_sha256=str(contract["profile_sha256"]),
            preinit_executable_closure_manifest_sha256=(preinit_manifest_sha256),
            stdlib_import_closure_manifest_sha256=stdlib_manifest_sha256,
            dynamic_library_closure_manifest_sha256=dynamic_manifest_sha256,
            host_preflight=host_document,
            blockers=blockers,
        ).to_dict()
        evidence["artifact_and_runtime_verified"] = bool(
            runtime_evidence["artifact_and_runtime_verified"]
        )
        evidence["exact_loader_process_identity_validated"] = True
        evidence["immutable_bootstrap_snapshot_validated"] = True
        evidence["native_extension_sha256"] = native_extension_sha256
        evidence["native_entrypoints_verified"] = True
        evidence["native_extension_descriptor_bound"] = True
        evidence["native_extension_immutable_snapshot_bound"] = True
        evidence["native_dependencies_preinitialized_and_authenticated"] = True
        evidence["native_initialization_mapping_delta_exact"] = True
        evidence["native_public_package_verified"] = True
        return evidence
    except BaseException:
        _remove_loaded_native_extension()
        raise
    finally:
        os.close(native_descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = derive_preflight(
        artifact_directory=arguments.artifact_directory,
        runtime_root=arguments.runtime_root,
    )
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
