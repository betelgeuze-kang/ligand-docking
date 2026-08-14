#!/usr/bin/env python3
"""Run the exact-runtime, non-consuming full-pipeline CPU activation preflight."""

# ruff: noqa: E402 -- repository modules are loaded only after isolation checks.

from __future__ import annotations

import argparse
import grp
import hashlib
import importlib
import importlib.machinery
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
    b"home = /usr/bin\n"
    b"include-system-site-packages = false\n"
    b"version = 3.10.12\n"
)
_MAX_SOURCE_BYTES = 4 * 1024 * 1024
_ACTIVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_full_pipeline_cpu_performance_activation/1.0.0"
)
_ACTIVATION_ID = "engine_v2_full_pipeline_cpu_performance_v1_activation"
_ACTIVATION_STATUS = (
    "frozen_non_consuming_exact_main_preflight_execution_not_activated"
)
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
        "230cc88d60a9fd0f92318492ec533672930e72eaed11ef5410a45ce7edbb690b"
    ),
    "dynamic_library_closure_manifest_sha256": (
        "b9190033cf42ea75aa1131da38517b70101f05f8c55992419964014bc67030b1"
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
        "b3d216100df51cfa0886ce9119a1e7e72a15ba30e6046609022c0d062351566b",
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


def _require_isolated_bootstrap() -> None:
    if tuple(sys.path) != _EXPECTED_INITIAL_PATHS:
        _fail("isolated standard-library path set changed")
    try:
        _STDLIB_ZIP_PATH.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise RuntimeError("isolated standard-library zip state is ambiguous") from exc
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
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        _fail("GitHub Actions cannot run the exact-runtime activation preflight")
    _require_private_effective_group()


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
                "library_count": 20,
                "manifest_sha256": _EXPECTED_SOURCE_BINDINGS[
                    "dynamic_library_closure_manifest_sha256"
                ],
                "path": (
                    "config/engine_v2_full_pipeline_cpu_performance_v1_"
                    "dynamic_library_closure.json"
                ),
                "total_bytes": 13_962_048,
            },
            "stdlib_import_closure": {
                "cached_bytecode_file_count": 78,
                "cached_bytecode_total_bytes": 1_447_655,
                "file_backed_module_count": 84,
                "file_backed_total_bytes": 2_194_777,
                "manifest_sha256": _EXPECTED_SOURCE_BINDINGS[
                    "stdlib_import_closure_manifest_sha256"
                ],
                "module_count": 125,
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
            "exact_native_extension_import_required": True,
            "github_actions_preflight_allowed": False,
            "host_preflight_required": True,
            "molecular_input_allowed": False,
            "performance_measurement_allowed": False,
            "performance_sidecar_sha256": _BOUND_MODULE_ROWS[0][2],
            "preflight_tool_sha256": bootstrap_sha256,
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
            "artifact_workflow_head_sha": (
                "3330faa43c7fc8640d89babd84ac444c5959157c"
            ),
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
            "merged_main_tree_manifest_encoding": (
                "git_ls_tree_r_full_tree_z_v1"
            ),
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
    *, repository_root: Path, site_packages: Path, authenticated_sources: dict[str, bytes]
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


def _require_native_extension(site_packages: Path) -> types.ModuleType:
    try:
        native = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError):
        _fail("exact native extension cannot be initialized")
    raw_path = getattr(native, "__file__", None)
    if type(raw_path) is not str:
        _fail("native extension module path is absent")
    try:
        path = Path(raw_path).resolve(strict=True)
        path.relative_to(site_packages)
    except (OSError, ValueError):
        _fail("native extension escaped the exact runtime site-packages")
    for name in (
        "native_fixed64_prepare_repository_synthetic_d0_session_v1",
        "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
    ):
        if not callable(getattr(native, name, None)):
            _fail(f"exact native extension lacks required entrypoint {name}")
    return native


def derive_preflight(
    *,
    artifact_directory: Path,
    runtime_root: Path,
) -> dict[str, object]:
    """Inspect exact bytes and imports without creating an execution attempt."""

    _require_isolated_bootstrap()
    bootstrap = Path(__file__).absolute()
    repository_root = _require_owner_directory(
        bootstrap.parent.parent,
        name="repository root",
    )
    if bootstrap.parent != repository_root / "tools":
        _fail("activation preflight bootstrap escaped repository tools")
    bootstrap_raw = _read_owner_source(
        bootstrap, name="activation preflight bootstrap"
    )
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
    _require_native_extension(site_packages)
    host = modules["performance_host_preflight_v3"].derive_host_preflight_evidence_v3()
    host_document = host.to_dict()

    activation = modules["full_pipeline_cpu_performance_v1_activation"]
    observed_stdlib = activation.derive_stdlib_import_closure()
    observed_dynamic = activation.derive_dynamic_library_closure(
        site_packages=site_packages
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
        name="dynamic-library closure",
    )
    blockers = tuple(str(value) for value in host_document["blockers"])
    evidence = activation.ActivationPreflightEvidenceV1(
        activation_sha256=hashlib.sha256(contract_raw).hexdigest(),
        profile_sha256=str(contract["profile_sha256"]),
        stdlib_import_closure_manifest_sha256=stdlib_manifest_sha256,
        dynamic_library_closure_manifest_sha256=dynamic_manifest_sha256,
        host_preflight=host_document,
        blockers=blockers,
    ).to_dict()
    evidence["artifact_and_runtime_verified"] = bool(
        runtime_evidence["artifact_and_runtime_verified"]
    )
    evidence["native_extension_sha256"] = runtime_evidence[
        "native_extension_sha256"
    ]
    evidence["native_entrypoints_verified"] = True
    return evidence


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
