"""Fail-closed synthetic CPU qualification for the real geometric kernel.

This module contains no receptor, ligand, case, benchmark, reservation, or
external-authority input surface.  It deterministically generates three
synthetic binary64 fixtures, runs the exact one-candidate Python geometric
admission kernel and its Rust counterpart, and records parity before timing is
considered.  A live result is process-local and deliberately non-serializable.
Persisted artifacts are replay evidence only: loading one can never recreate a
live execution capability or any product/scientific authority.
"""

from __future__ import annotations

import argparse
import base64
import csv
from dataclasses import dataclass, field
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import secrets
import signal
import stat
import struct
import subprocess
import sys
import sysconfig
import tempfile
import time
from types import MappingProxyType
from typing import Any, Final, Iterable, Mapping, Sequence
import weakref


CPU_PERFORMANCE_PROFILE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_cpu_performance_profile/2.0.0"
)
CPU_PERFORMANCE_ARTIFACT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_cpu_performance_artifact/2.0.0"
)
SYNTHETIC_GEOMETRIC_INPUT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_synthetic_geometric_input/2.0.0"
)
GEOMETRIC_KERNEL_OUTPUT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_kernel_output/2.0.0"
)
GEOMETRIC_KERNEL_TRANSCRIPT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_kernel_child_transcript/2.0.0"
)
SYNTHETIC_FIXTURE_GENERATOR_ID: Final = (
    "betelgeuze.synthetic_binary64_geometric_fixture/2.0.0"
)
PYTHON_GEOMETRIC_KERNEL_ID: Final = (
    "betelgeuze.engine_v2_python_fixed64_normalized_geometric_metrics/2.0.0"
)
NATIVE_GEOMETRIC_KERNEL_ID: Final = (
    "betelgeuze.engine_v2_native_geometric_admission_metrics_one/1.0.0"
)
PAIR_TRAVERSAL_ORDER: Final = (
    "full_cartesian_ligand_index_major_receptor_index_minor"
)
QUALIFICATION_BOOTSTRAP_RELATIVE_PATH: Final = Path(
    "tools/run_engine_v2_cpu_performance_qualification.py"
)
_QUALIFIED_ISOLATED_STDLIB_PATHS: Final = (
    "/usr/lib/python310.zip",
    "/usr/lib/python3.10",
    "/usr/lib/python3.10/lib-dynload",
)
_QUALIFIED_STDLIB_ZIP_PATH: Final = Path(_QUALIFIED_ISOLATED_STDLIB_PATHS[0])
_NUMPY_DIST_INFO_DIRECTORY: Final = "numpy-1.26.4.dist-info"
_NUMPY_RECORD_SELF_PATH: Final = f"{_NUMPY_DIST_INFO_DIRECTORY}/RECORD"
_NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY: Final = "../../bin/f2py"
_NUMPY_RECORD_TYPED_ABSENT_PATHS: Final = (
    "numpy/distutils/__pycache__/conv_template.cpython-310.pyc",
)
_QUALIFIED_CHILD_FLAGS: Final = MappingProxyType(
    {
        "isolated": 1,
        "ignore_environment": 1,
        "no_site": 1,
        "no_user_site": 1,
        "dont_write_bytecode": 1,
        "hash_randomization": 1,
        "safe_path_supported": False,
        "safe_path": False,
    }
)
_QUALIFIED_BOOTSTRAP_PATH_ROLES: Final = (
    "isolated_stdlib",
    "repository_source_root",
    "qualified_site_packages_root",
)
_QUALIFIED_SITE_PACKAGES_TOP_LEVEL: Final = (
    "betelgeuze_engine_v2_native",
    "betelgeuze_engine_v2_native-0.2.0rc6.dist-info",
    "numpy",
    "numpy-1.26.4.dist-info",
    "numpy.libs",
)

PROFILE_ID: Final = "engine_v2_ryzen_5900x_geometric_kernel_synthetic_v2"
CPU_MODEL_EXACT: Final = "AMD Ryzen 9 5900X 12-Core Processor"
AUTHORITATIVE_CPU_AFFINITY: Final = (2,)
EXPECTED_NATIVE_VERSION: Final = "0.2.0-rc.6"
EXPECTED_RUSTC_VERSION: Final = "rustc 1.93.0 (254b59607 2026-01-19)"
EXPECTED_BUILD_FLAGS: Final = (
    "codegen-units=1,lto=fat,opt-level=3,panic=abort,strip=symbols"
)
EXPECTED_RUSTC_VERBOSE_SHA256: Final = (
    "a8d93365194b081bd07ccb5c7db5c4dfc843a7f04b9b5895779a90bdb3880604"
)
EMPTY_SHA256: Final = hashlib.sha256(b"").hexdigest()

_NATIVE_BUILD_INFO_STATIC: Final = MappingProxyType(
    {
        "backend_id": "rust_cpu_required",
        "backend_version": EXPECTED_NATIVE_VERSION,
        "crate_name": "betelgeuze-engine-v2-native",
        "rustc_version": EXPECTED_RUSTC_VERSION,
        "rustc_verbose_sha256": EXPECTED_RUSTC_VERBOSE_SHA256,
        "target_triple": "x86_64-unknown-linux-gnu",
        "host_triple": "x86_64-unknown-linux-gnu",
        "target_arch": "x86_64",
        "target_env": "gnu",
        "target_features": "fxsr,sse,sse2",
        "target_os": "linux",
        "build_profile": "release",
        "build_opt_level": "3",
        "build_debug": "false",
        "build_panic": "abort",
        "build_script_cfg_panic": "unwind",
        "release_codegen_units": "1",
        "release_debug_assertions": "false",
        "release_incremental": "false",
        "release_lto": "fat",
        "release_overflow_checks": "false",
        "release_panic": "abort",
        "release_strip": "symbols",
        "rustflags_count": "0",
        "rustflags_sha256": EMPTY_SHA256,
        "build_wrapper_control": "verified_frozen_wrapper",
        "build_flags": EXPECTED_BUILD_FLAGS,
        "implicit_fallback_allowed": "false",
        "geometric_admission_metrics_kernel_id": NATIVE_GEOMETRIC_KERNEL_ID,
        "geometric_admission_pair_traversal_order": PAIR_TRAVERSAL_ORDER,
    }
)
_NATIVE_BUILD_INFO_DIGEST_KEYS: Final = frozenset(
    {
        "cargo_lock_sha256",
        "cargo_manifest_sha256",
        "native_pyproject_sha256",
        "rust_lib_sha256",
        "build_script_sha256",
        "native_build_wrapper_sha256",
        "rustc_executable_sha256",
    }
)
_NATIVE_BUILD_INFO_KEYS: Final = frozenset(_NATIVE_BUILD_INFO_STATIC) | (
    _NATIVE_BUILD_INFO_DIGEST_KEYS
)

_QUALIFIED_PYTHON_RUNTIME: Final = MappingProxyType(
    {
        "python_implementation": "CPython",
        "python_version": "3.10.12",
        "python_cache_tag": "cpython-310",
        "python_soabi": "cpython-310-x86_64-linux-gnu",
        "python_byteorder": "little",
        "python_executable_filename": "python3.10",
        "python_executable_sha256": (
            "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86"
        ),
        "python_shared_library_filename": "libpython3.10.so.1.0",
        "python_shared_library_sha256": (
            "1ece943a1641101b1c678b553a7a0fbb6683ff0ad76f7ebce9f8844354e3f153"
        ),
        "virtual_environment_configuration_sha256": (
            "db6c8a96f25493eda9f74f23f0b5f248a8b50a5b469b15c5ee7313875b416364"
        ),
        "python_stdlib_zip_path": str(_QUALIFIED_STDLIB_ZIP_PATH),
        "python_stdlib_zip_state": "required_absent",
        "stdlib_runtime_manifest_schema_id": (
            "betelgeuze.python_stdlib_runtime_manifest/1.0.0"
        ),
        "stdlib_runtime_manifest_sha256": (
            "5938d3411a731e9b81cef6c1ea69914c0e9d1f8aa36d45a242e0118b39aa86e5"
        ),
        "stdlib_runtime_manifest_file_count": 1370,
        "stdlib_runtime_manifest_total_bytes": 47750395,
        "dynamic_library_manifest_schema_id": (
            "betelgeuze.loaded_dynamic_library_manifest/1.0.0"
        ),
        "dynamic_library_manifest_sha256": (
            "7206bca252a228e7f6c20c1f6427e24c04dc14b7e09e602c8eafe0835bae33ab"
        ),
        "dynamic_library_manifest_file_count": 37,
        "dynamic_library_manifest_total_bytes": 58651309,
        "native_distribution_name": "betelgeuze-engine-v2-native",
        "native_version": "0.2.0rc6",
        "native_extension_filename": (
            "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so"
        ),
        "native_extension_sha256": (
            "a07ca2276277cd610450d45d09f5b9789a69580747f61c6c9867640b07164a55"
        ),
        "native_distribution_metadata_sha256": (
            "e8a7e538cee43befb3a0b8b63b9b7b88db8d2969cf3da012af4694b902d5f64b"
        ),
        "native_wheel_metadata_sha256": (
            "e0b0b2962b6b3e1aca30116e39ad7ee772d32cf103803fd598f0f56370f0203b"
        ),
        "numpy_distribution_name": "numpy",
        "numpy_version": "1.26.4",
        "numpy_distribution_metadata_sha256": (
            "b09734a7fed44e84b4c8161934ce532dff1e779ec6822d415644d117f6381070"
        ),
        "numpy_wheel_metadata_sha256": (
            "b1933f35e50ccf61b87c37a731fd757a291c0b170b6905a26119a3c1005abd0b"
        ),
        "numpy_entry_points_sha256": (
            "cdd772609b94c3d52e77b2de2dfca75e4eb6febcb49468a10f008882e8017593"
        ),
        "numpy_record_sha256": (
            "23cbef5aec57da48ba6f4702fa941742a5afc66281162b6889b3745b2bbfaf73"
        ),
        "numpy_record_byte_count": 85607,
        "numpy_record_row_count": 918,
        "numpy_record_present_file_count": 917,
        "numpy_record_self_path": _NUMPY_RECORD_SELF_PATH,
        "numpy_record_console_script_entry": _NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY,
        "numpy_record_typed_absent_paths": list(_NUMPY_RECORD_TYPED_ABSENT_PATHS),
        "numpy_installed_files_manifest_schema_id": (
            "betelgeuze.numpy_installed_files_manifest/1.0.0"
        ),
        "numpy_installed_files_manifest_sha256": (
            "e834eba9cadcd903265ffe7bd1ec01af885b3dfc70a815501d7edc3ea88d218d"
        ),
        "numpy_installed_files_manifest_file_count": 917,
        "numpy_installed_files_manifest_total_bytes": 64658331,
        "numpy_console_script_relative_path": "bin/f2py",
        "numpy_console_script_sha256": (
            "53488d036810ad895b5efecb35bd6d5f4bb085d8068b48243ef7ee945a671d1a"
        ),
        "numpy_console_script_byte_count": 219,
        "numpy_runtime_manifest_schema_id": (
            "betelgeuze.numpy_runtime_payload_manifest/1.0.0"
        ),
        "numpy_runtime_manifest_sha256": (
            "d35d73448d1e6ec8a8d58b1ebca8cba5a1127b232ef539c814e9387656565408"
        ),
        "numpy_runtime_manifest_file_count": 909,
        "numpy_runtime_manifest_total_bytes": 64463458,
        "numpy_package_init_sha256": (
            "22cd1535fa14d74ef6f457cca149ffdc80875f460be313b8f895273f78bc402e"
        ),
        "numpy_core_extension_filename": (
            "_multiarray_umath.cpython-310-x86_64-linux-gnu.so"
        ),
        "numpy_core_extension_sha256": (
            "fe5efe31c55326b072c8fb239a225819211826cb45cd3c74ed0af0030e70f3a1"
        ),
        "qualified_site_packages_runtime_manifest_schema_id": (
            "betelgeuze.qualified_site_packages_runtime_manifest/1.0.0"
        ),
        "qualified_site_packages_runtime_manifest_sha256": (
            "d74142ee979516bcbaf80ca9b3d54a39a347da762dafbd92c68dbdd16d55694a"
        ),
        "qualified_site_packages_runtime_manifest_file_count": 911,
        "qualified_site_packages_runtime_manifest_total_bytes": 65061849,
        "site_packages_top_level_names": list(
            _QUALIFIED_SITE_PACKAGES_TOP_LEVEL
        ),
        "child_flags": dict(_QUALIFIED_CHILD_FLAGS),
        "bootstrap_path_roles": list(_QUALIFIED_BOOTSTRAP_PATH_ROLES),
        "isolated_stdlib_paths_sha256": hashlib.sha256(
            json.dumps(
                list(_QUALIFIED_ISOLATED_STDLIB_PATHS),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
        ).hexdigest(),
    }
)

CANONICAL_PROFILE_RELATIVE_PATH: Final = Path(
    "config/engine_v2_cpu_performance_profile.json"
)
MAX_PROFILE_BYTES: Final = 256 * 1024
MAX_ARTIFACT_BYTES: Final = 16 * 1024 * 1024
MAX_CHILD_OUTPUT_BYTES: Final = 256 * 1024
MAX_SOURCE_FILE_BYTES: Final = 256 * 1024 * 1024
MAX_JSON_DEPTH: Final = 40
MAX_JSON_NODES: Final = 2_000_000
MAX_SAFE_JSON_INTEGER: Final = (1 << 53) - 1
MAX_STRING_BYTES: Final = 2 * 1024 * 1024
MAX_MAPPING_KEY_BYTES: Final = 256
MAX_CHILD_DURATION_NS: Final = 30_000_000_000
MAX_RECORDED_RSS_KIB: Final = 1_073_741_824
CHILD_POLL_INTERVAL_SECONDS: Final = 0.001
MAX_CHILD_OPEN_FILES: Final = 64
MAX_RUNTIME_MANIFEST_FILES: Final = 10_000
MAX_RUNTIME_MANIFEST_BYTES: Final = 1024 * 1024 * 1024

EXACT_INTEGER_FIELDS: Final = (
    "ligand_atom_count",
    "receptor_atom_count",
    "exact_pair_count",
    "penetration_pair_count",
    "unique_ligand_penetration_atom_count",
    "unique_ligand_heavy_atom_penetration_count",
)
FLOAT_FIELDS: Final = (
    "raw_minimum_distance_angstrom",
    "minimum_vdw_surface_gap_angstrom",
    "minimum_vdw_ratio",
    "sphere_overlap_proxy_angstrom3",
    "pocket_escape_angstrom",
)
DEFAULT_FLOAT_TOLERANCES: Final = MappingProxyType(
    {
        "raw_minimum_distance_angstrom": (1.0e-12, 32),
        "minimum_vdw_surface_gap_angstrom": (1.0e-12, 32),
        "minimum_vdw_ratio": (1.0e-12, 32),
        "sphere_overlap_proxy_angstrom3": (1.0e-9, 4096),
        "pocket_escape_angstrom": (1.0e-12, 64),
    }
)
AUTHORITY_FALSE: Final = MappingProxyType(
    {
        "fresh_holdout_execution_authorized": False,
        "historical_ab_execution_authorized": False,
        "molecular_execution_authorized": False,
        "product_performance_claim_authorized": False,
        "public_benchmark_authorized": False,
        "scientific_claim_authorized": False,
        "stage0_admission_authorized": False,
    }
)
RESTRICTIONS: Final = MappingProxyType(
    {
        "actual_molecular_execution_allowed": False,
        "contains_molecular_cases": False,
        "fresh_or_historical_case_input_allowed": False,
        "github_actions_production_authority_allowed": False,
        "public_or_scientific_performance_claim_allowed": False,
        "reservation_allowed": False,
        "test_double_production_authority_allowed": False,
    }
)
THREAD_ENVIRONMENT: Final = MappingProxyType(
    {
        "BLIS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "RAYON_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FIXTURE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_RUN_NONCE_RE = re.compile(r"^[0-9a-f]{64}$")


class CPUPerformanceError(ValueError):
    """Raised when the synthetic CPU contract fails closed."""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CPUPerformanceError("value is not canonical JSON") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _require_digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise CPUPerformanceError(f"{name} must be a lowercase SHA-256")
    return value


def _require_exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int = MAX_SAFE_JSON_INTEGER,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CPUPerformanceError(f"{name} is outside its exact integer envelope")
    return value


def _require_exact_bool(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise CPUPerformanceError(f"{name} must be an exact boolean")
    return value


def _require_exact_mapping_keys(
    value: object,
    *,
    name: str,
    keys: Iterable[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CPUPerformanceError(f"{name} must be an object")
    expected = frozenset(keys)
    observed = frozenset(value)
    if observed != expected or any(type(key) is not str for key in value):
        raise CPUPerformanceError(f"{name} keys are not the frozen contract")
    return value


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CPUPerformanceError("JSON object contains a duplicate name")
        result[key] = value
    return result


def _parse_json_integer(value: str) -> int:
    parsed = int(value)
    if abs(parsed) > MAX_SAFE_JSON_INTEGER:
        raise CPUPerformanceError("JSON integer exceeds the exact envelope")
    return parsed


def _reject_json_float(_: str) -> float:
    raise CPUPerformanceError("binary64 values must use canonical hexadecimal strings")


def _reject_json_constant(_: str) -> object:
    raise CPUPerformanceError("JSON constants are forbidden")


def _validate_json_tree(value: object) -> None:
    remaining = MAX_JSON_NODES

    def visit(item: object, depth: int) -> None:
        nonlocal remaining
        remaining -= 1
        if remaining < 0:
            raise CPUPerformanceError("JSON document exceeds the node limit")
        if depth > MAX_JSON_DEPTH:
            raise CPUPerformanceError("JSON document exceeds the depth limit")
        if item is None or type(item) in (bool, int):
            return
        if type(item) is str:
            if len(item.encode("utf-8", "surrogatepass")) > MAX_STRING_BYTES:
                raise CPUPerformanceError("JSON string exceeds the byte limit")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in item):
                raise CPUPerformanceError("JSON strings cannot contain lone surrogates")
            return
        if type(item) is list:
            for child in item:
                visit(child, depth + 1)
            return
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise CPUPerformanceError("JSON object names must be strings")
                if len(key.encode("utf-8")) > MAX_MAPPING_KEY_BYTES:
                    raise CPUPerformanceError("JSON object name exceeds the byte limit")
                visit(child, depth + 1)
            return
        raise CPUPerformanceError("JSON document contains an unsupported value")

    visit(value, 0)


def require_canonical_json_object_bytes(
    raw: bytes,
    *,
    name: str,
    maximum_bytes: int,
    trailing_newline_required: bool = True,
) -> Mapping[str, Any]:
    """Decode bounded exact canonical JSON and reject duplicate names/floats."""

    if type(raw) is not bytes or not raw or len(raw) > maximum_bytes:
        raise CPUPerformanceError(f"{name} byte count is outside its envelope")
    if trailing_newline_required:
        if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
            raise CPUPerformanceError(f"{name} requires one canonical trailing newline")
        payload = raw[:-1]
    else:
        if raw.endswith(b"\n"):
            raise CPUPerformanceError(f"{name} cannot contain a trailing newline")
        payload = raw
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CPUPerformanceError(f"{name} must be ASCII canonical JSON") from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_strict_object_pairs,
            parse_int=_parse_json_integer,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_constant,
        )
    except CPUPerformanceError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise CPUPerformanceError(f"{name} is invalid JSON") from exc
    if type(decoded) is not dict:
        raise CPUPerformanceError(f"{name} must be a JSON object")
    _validate_json_tree(decoded)
    if _canonical_json_bytes(decoded) != payload:
        raise CPUPerformanceError(f"{name} is not exact canonical JSON")
    return decoded


def _read_bounded_regular_file(
    path: Path,
    *,
    name: str,
    maximum_bytes: int,
    require_single_link: bool = False,
    require_owner_only: bool = False,
    require_stable_size: bool = False,
) -> bytes:
    target = Path(path)
    if len(os.fsencode(target)) > 4096:
        raise CPUPerformanceError(f"{name} path is too long")
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as exc:
        raise CPUPerformanceError(f"{name} cannot be opened safely") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > maximum_bytes
            or (require_single_link and metadata.st_nlink != 1)
            or (
                require_owner_only
                and (
                    metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                )
            )
        ):
            raise CPUPerformanceError(f"{name} is not a bounded regular file")
        chunks: list[bytes] = []
        observed = 0
        while observed <= maximum_bytes:
            chunk = os.read(descriptor, min(1 << 20, maximum_bytes + 1 - observed))
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        if observed > maximum_bytes:
            raise CPUPerformanceError(f"{name} exceeds the byte limit")
        if require_stable_size and observed != metadata.st_size:
            raise CPUPerformanceError(f"{name} size changed during the bounded read")
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_mode,
            after.st_uid,
            after.st_gid,
            after.st_nlink,
        ) != (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
            metadata.st_mode,
            metadata.st_uid,
            metadata.st_gid,
            metadata.st_nlink,
        ):
            raise CPUPerformanceError(f"{name} changed during the bounded read")
        if require_single_link and after.st_nlink != 1:
            raise CPUPerformanceError(f"{name} link identity changed during read")
        if require_owner_only and (
            after.st_uid != os.geteuid() or stat.S_IMODE(after.st_mode) != 0o600
        ):
            raise CPUPerformanceError(f"{name} ownership changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _sha256_regular_file(path: Path, *, name: str) -> str:
    return _sha256_bytes(
        _read_bounded_regular_file(
            path,
            name=name,
            maximum_bytes=MAX_SOURCE_FILE_BYTES,
            require_stable_size=True,
        )
    )


def _sha256_owner_controlled_regular_file(path: Path, *, name: str) -> str:
    return _sha256_bytes(
        _read_owner_controlled_regular_file(
            path,
            name=name,
            maximum_bytes=MAX_SOURCE_FILE_BYTES,
        )
    )


def _read_owner_controlled_regular_file(
    path: Path,
    *,
    name: str,
    maximum_bytes: int,
) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise CPUPerformanceError(f"{name} is unavailable") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.geteuid()
        or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        or before.st_nlink != 1
    ):
        raise CPUPerformanceError(f"{name} is not owner-controlled")
    raw = _read_bounded_regular_file(
        path,
        name=name,
        maximum_bytes=maximum_bytes,
        require_single_link=True,
        require_stable_size=True,
    )
    try:
        after = path.lstat()
    except OSError as exc:
        raise CPUPerformanceError(f"{name} changed during hashing") from exc
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
    if any(getattr(before, field) != getattr(after, field) for field in identity_fields):
        raise CPUPerformanceError(f"{name} changed during hashing")
    return raw


def _float_hex(value: object, *, name: str) -> str:
    if type(value) is not float or not math.isfinite(value):
        raise CPUPerformanceError(f"{name} must be finite binary64")
    return value.hex()


def _require_float_hex(value: object, *, name: str) -> float:
    if type(value) is not str or len(value) > 64:
        raise CPUPerformanceError(f"{name} must be canonical binary64 hexadecimal")
    try:
        observed = float.fromhex(value)
    except ValueError as exc:
        raise CPUPerformanceError(f"{name} is not binary64 hexadecimal") from exc
    if not math.isfinite(observed) or observed.hex() != value:
        raise CPUPerformanceError(f"{name} is not canonical finite binary64")
    return observed


@dataclass(frozen=True, slots=True)
class SyntheticFixtureSpecV2:
    fixture_id: str
    ligand_atom_count: int
    receptor_atom_count: int
    seed: int

    @property
    def exact_pair_count(self) -> int:
        return self.ligand_atom_count * self.receptor_atom_count


FROZEN_SYNTHETIC_FIXTURES: Final = (
    SyntheticFixtureSpecV2("small", 16, 512, 11),
    SyntheticFixtureSpecV2("medium", 32, 2048, 23),
    SyntheticFixtureSpecV2("large", 48, 4096, 47),
)
_FROZEN_FIXTURE_BY_ID: Final = MappingProxyType(
    {fixture.fixture_id: fixture for fixture in FROZEN_SYNTHETIC_FIXTURES}
)


@dataclass(frozen=True, slots=True)
class SyntheticGeometricFixtureV2:
    fixture_id: str
    ligand_coordinates: tuple[tuple[float, float, float], ...]
    ligand_vdw_radii: tuple[float, ...]
    ligand_heavy_atom_mask: tuple[bool, ...]
    receptor_coordinates: tuple[tuple[float, float, float], ...]
    receptor_vdw_radii: tuple[float, ...]
    pocket_center: tuple[float, float, float]
    pocket_radius: float
    generator_seed: int

    def __post_init__(self) -> None:
        spec = _FROZEN_FIXTURE_BY_ID.get(self.fixture_id)
        if spec is None or self.generator_seed != spec.seed:
            raise CPUPerformanceError("synthetic fixture identity is not frozen")
        if (
            len(self.ligand_coordinates) != spec.ligand_atom_count
            or len(self.ligand_vdw_radii) != spec.ligand_atom_count
            or len(self.ligand_heavy_atom_mask) != spec.ligand_atom_count
            or len(self.receptor_coordinates) != spec.receptor_atom_count
            or len(self.receptor_vdw_radii) != spec.receptor_atom_count
        ):
            raise CPUPerformanceError("synthetic fixture denominator changed")
        for name, coordinates in (
            ("ligand_coordinates", self.ligand_coordinates),
            ("receptor_coordinates", self.receptor_coordinates),
        ):
            if type(coordinates) is not tuple:
                raise CPUPerformanceError(f"{name} must be an immutable tuple")
            for row in coordinates:
                if type(row) is not tuple or len(row) != 3:
                    raise CPUPerformanceError(f"{name} row shape changed")
                for component in row:
                    _float_hex(component, name=name)
        for name, radii in (
            ("ligand_vdw_radii", self.ligand_vdw_radii),
            ("receptor_vdw_radii", self.receptor_vdw_radii),
        ):
            if type(radii) is not tuple:
                raise CPUPerformanceError(f"{name} must be an immutable tuple")
            for radius in radii:
                observed = _require_float_hex(_float_hex(radius, name=name), name=name)
                if not 0.1 <= observed <= 10.0:
                    raise CPUPerformanceError(f"{name} radius is outside the safety envelope")
        if type(self.ligand_heavy_atom_mask) is not tuple or any(
            type(value) is not bool for value in self.ligand_heavy_atom_mask
        ):
            raise CPUPerformanceError("ligand_heavy_atom_mask must contain exact booleans")
        if type(self.pocket_center) is not tuple or len(self.pocket_center) != 3:
            raise CPUPerformanceError("pocket_center shape changed")
        for component in self.pocket_center:
            _float_hex(component, name="pocket_center")
        if not 0.0 < self.pocket_radius <= 1_000.0:
            raise CPUPerformanceError("pocket_radius is outside the safety envelope")

    @property
    def exact_pair_count(self) -> int:
        return len(self.ligand_coordinates) * len(self.receptor_coordinates)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": SYNTHETIC_GEOMETRIC_INPUT_SCHEMA_ID,
            "fixture_id": self.fixture_id,
            "generator_id": SYNTHETIC_FIXTURE_GENERATOR_ID,
            "generator_seed": self.generator_seed,
            "dtype": "binary64",
            "byte_order": "native_little_endian_required",
            "ligand_atom_count": len(self.ligand_coordinates),
            "receptor_atom_count": len(self.receptor_coordinates),
            "exact_pair_count": self.exact_pair_count,
            "ligand_coordinates_binary64_hex": [
                [component.hex() for component in row]
                for row in self.ligand_coordinates
            ],
            "ligand_vdw_radii_binary64_hex": [
                value.hex() for value in self.ligand_vdw_radii
            ],
            "ligand_heavy_atom_mask": list(self.ligand_heavy_atom_mask),
            "receptor_coordinates_binary64_hex": [
                [component.hex() for component in row]
                for row in self.receptor_coordinates
            ],
            "receptor_vdw_radii_binary64_hex": [
                value.hex() for value in self.receptor_vdw_radii
            ],
            "pocket_center_binary64_hex": [value.hex() for value in self.pocket_center],
            "pocket_radius_binary64_hex": self.pocket_radius.hex(),
            "contains_molecular_input": False,
            "contains_case_identity": False,
        }

    @property
    def input_sha256(self) -> str:
        return _sha256_json(self.to_dict())


def _binary_exact_coordinate(index: int, multiplier: int, modulus: int, offset: int) -> float:
    return float((index * multiplier) % modulus - offset) * 0.125


def generate_synthetic_geometric_fixture(fixture_id: str) -> SyntheticGeometricFixtureV2:
    """Generate one frozen, molecule-free binary64 fixture by identifier."""

    if type(fixture_id) is not str or _FIXTURE_ID_RE.fullmatch(fixture_id) is None:
        raise CPUPerformanceError("fixture_id is invalid")
    spec = _FROZEN_FIXTURE_BY_ID.get(fixture_id)
    if spec is None:
        raise CPUPerformanceError("fixture_id is not in the frozen synthetic profile")
    seed = spec.seed
    ligand = [
        (
            _binary_exact_coordinate(index + seed * 3, 17, 97, 48),
            _binary_exact_coordinate(index + seed * 5, 29, 89, 44),
            _binary_exact_coordinate(index + seed * 7, 43, 83, 41),
        )
        for index in range(spec.ligand_atom_count)
    ]
    ligand_radii = [
        float(10 + ((index + seed) % 5)) * 0.125
        for index in range(spec.ligand_atom_count)
    ]
    heavy = [((index + seed) % 4) != 0 for index in range(spec.ligand_atom_count)]
    receptor = [
        (
            _binary_exact_coordinate(index + seed * 11, 31, 257, 128),
            _binary_exact_coordinate(index + seed * 13, 47, 251, 125),
            _binary_exact_coordinate(index + seed * 17, 59, 241, 120),
        )
        for index in range(spec.receptor_atom_count)
    ]
    receptor_radii = [
        float(11 + ((index + 2 * seed) % 6)) * 0.125
        for index in range(spec.receptor_atom_count)
    ]

    # The three timed fixtures deliberately freeze different decision paths.
    # Small is accepted/nonpenetrating with positive pocket escape. Medium has
    # an exact threshold-ratio penetration, is accepted, and has zero escape.
    # Large exercises coincident/partial overlap, both heavy-mask branches,
    # rejection, and positive escape.  This prevents a zero/always-rejected
    # implementation from satisfying the profile parity rows.
    if fixture_id == "small":
        ligand[-1] = (12.0, 0.0, 0.0)
        ligand_radii[-1] = 1.0
        receptor = [
            (point[0] + 40.0, point[1] + 40.0, point[2] + 40.0)
            for point in receptor
        ]
    elif fixture_id == "medium":
        ligand = [
            (0.0, 0.0, 0.0)
            if index == 0
            else (
                -4.0 - float(index % 8) * 0.25,
                float(index // 8) * 0.5,
                0.0,
            )
            for index in range(spec.ligand_atom_count)
        ]
        ligand_radii[0] = 1.5
        heavy[0] = True
        receptor = [
            (point[0] + 40.0, point[1] + 40.0, point[2] + 40.0)
            for point in receptor
        ]
        receptor[0] = (1.375, 0.0, 0.0)
        receptor_radii[0] = 1.0
    else:
        ligand[0] = (0.0, 0.0, 0.0)
        ligand_radii[0] = 1.5
        heavy[0] = True
        ligand[1] = (4.0, 0.0, 0.0)
        ligand_radii[1] = 1.25
        heavy[1] = False
        ligand[-1] = (12.0, 0.0, 0.0)
        ligand_radii[-1] = 1.0
        receptor[0] = (0.0, 0.0, 0.0)
        receptor_radii[0] = 1.0
        receptor[1] = (2.5, 0.0, 0.0)
        receptor_radii[1] = 1.0
        receptor[2] = (4.75, 0.0, 0.0)
        receptor_radii[2] = 1.0
        receptor[3] = (20.0, 20.0, 20.0)
        receptor_radii[3] = 1.0

    return SyntheticGeometricFixtureV2(
        fixture_id=fixture_id,
        ligand_coordinates=tuple(ligand),
        ligand_vdw_radii=tuple(ligand_radii),
        ligand_heavy_atom_mask=tuple(heavy),
        receptor_coordinates=tuple(receptor),
        receptor_vdw_radii=tuple(receptor_radii),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=8.0,
        generator_seed=seed,
    )


@dataclass(frozen=True, slots=True)
class GeometricKernelOutputV2:
    ligand_atom_count: int
    receptor_atom_count: int
    exact_pair_count: int
    raw_minimum_distance_angstrom: float
    minimum_vdw_surface_gap_angstrom: float
    minimum_vdw_ratio: float
    penetration_pair_count: int
    unique_ligand_penetration_atom_count: int
    unique_ligand_heavy_atom_penetration_count: int
    sphere_overlap_proxy_angstrom3: float
    pocket_escape_angstrom: float
    decision: str

    def __post_init__(self) -> None:
        for name in EXACT_INTEGER_FIELDS:
            _require_exact_int(getattr(self, name), name=name)
        for name in FLOAT_FIELDS:
            _float_hex(getattr(self, name), name=name)
        if self.decision not in ("accepted", "rejected"):
            raise CPUPerformanceError("geometric decision is invalid")
        from .geometric_admission_v2 import HARD_REJECTION_MINIMUM_VDW_RATIO

        expected = (
            "accepted"
            if self.minimum_vdw_ratio >= HARD_REJECTION_MINIMUM_VDW_RATIO
            else "rejected"
        )
        if self.decision != expected:
            raise CPUPerformanceError("geometric decision does not rederive")

    def to_dict(self) -> dict[str, object]:
        from .geometric_admission_v2 import HARD_REJECTION_MINIMUM_VDW_RATIO

        return {
            "schema_id": GEOMETRIC_KERNEL_OUTPUT_SCHEMA_ID,
            **{name: getattr(self, name) for name in EXACT_INTEGER_FIELDS},
            **{
                f"{name}_binary64_hex": getattr(self, name).hex()
                for name in FLOAT_FIELDS
            },
            "hard_rejection_minimum_vdw_ratio_binary64_hex": (
                HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
            ),
            "decision": self.decision,
        }

    @property
    def output_sha256(self) -> str:
        return _sha256_json(self.to_dict())


def _output_from_metrics(metrics: object) -> GeometricKernelOutputV2:
    values: dict[str, object] = {}
    for name in EXACT_INTEGER_FIELDS:
        value = getattr(metrics, name, None)
        if type(value) is not int:
            raise CPUPerformanceError(f"kernel output {name} is not an exact integer")
        values[name] = value
    for name in FLOAT_FIELDS:
        value = getattr(metrics, name, None)
        if type(value) is not float or not math.isfinite(value):
            raise CPUPerformanceError(f"kernel output {name} is not finite binary64")
        values[name] = value
    from .geometric_admission_v2 import HARD_REJECTION_MINIMUM_VDW_RATIO

    values["decision"] = (
        "accepted"
        if values["minimum_vdw_ratio"] >= HARD_REJECTION_MINIMUM_VDW_RATIO
        else "rejected"
    )
    return GeometricKernelOutputV2(**values)  # type: ignore[arg-type]


def normalize_python_geometric_output(
    fixture: SyntheticGeometricFixtureV2,
) -> GeometricKernelOutputV2:
    """Run and normalize the exact Python one-candidate production kernel."""

    if not isinstance(fixture, SyntheticGeometricFixtureV2):
        raise CPUPerformanceError("fixture must be SyntheticGeometricFixtureV2")
    from .geometric_admission_v2 import (
        evaluate_geometric_admission_metrics_one_python,
    )

    metrics = evaluate_geometric_admission_metrics_one_python(
        fixture.ligand_coordinates,
        ligand_vdw_radii=fixture.ligand_vdw_radii,
        ligand_heavy_atom_mask=fixture.ligand_heavy_atom_mask,
        receptor_coordinates=fixture.receptor_coordinates,
        receptor_vdw_radii=fixture.receptor_vdw_radii,
        pocket_center=fixture.pocket_center,
        pocket_radius=fixture.pocket_radius,
    )
    return _output_from_metrics(metrics)


def _load_native_module() -> object:
    try:
        package = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError) as exc:
        raise CPUPerformanceError("native_geometric_kernel_unavailable") from exc
    extension = getattr(package, "betelgeuze_engine_v2_native", None)
    if extension is None or not str(getattr(extension, "__file__", "")).endswith(
        ".so"
    ):
        try:
            extension = importlib.import_module(
                "betelgeuze_engine_v2_native.betelgeuze_engine_v2_native"
            )
        except (ImportError, OSError) as exc:
            raise CPUPerformanceError("native_extension_provider_unavailable") from exc
    if not callable(getattr(extension, "geometric_admission_metrics_one", None)):
        raise CPUPerformanceError("native_geometric_kernel_entrypoint_missing")
    return extension


def _native_extension_path(module: object) -> Path:
    path = Path(str(getattr(module, "__file__", ""))).resolve()
    if not path.is_file() or path.suffix != ".so":
        raise CPUPerformanceError("native_extension_identity_unavailable")
    return path


def _require_native_build_info_document(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise CPUPerformanceError("native_build_info must be an object")
    raw = dict(value)
    if (
        frozenset(raw) != _NATIVE_BUILD_INFO_KEYS
        or any(type(key) is not str or type(value) is not str for key, value in raw.items())
    ):
        raise CPUPerformanceError("native_build_info_keys_mismatch")
    info = {str(key): str(value) for key, value in sorted(raw.items())}
    for name, expected in _NATIVE_BUILD_INFO_STATIC.items():
        if info[name] != expected:
            raise CPUPerformanceError(f"native_build_info_mismatch:{name}")
    for name in _NATIVE_BUILD_INFO_DIGEST_KEYS:
        _require_digest(info[name], name=f"native_build_info.{name}")
    return info


def _validated_native_build_info(module: object) -> dict[str, str]:
    try:
        value = module.build_info()
    except Exception as exc:
        raise CPUPerformanceError("native_build_info_unavailable") from exc
    return _require_native_build_info_document(value)


def _require_path_absent(path: Path, *, name: str) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise CPUPerformanceError(f"{name} state is ambiguous") from exc
    raise CPUPerformanceError(f"{name} must be absent")


def _require_owner_controlled_real_directory(path: Path, *, name: str) -> Path:
    unresolved = path.absolute()
    try:
        metadata = unresolved.lstat()
        resolved = unresolved.resolve(strict=True)
    except OSError as exc:
        raise CPUPerformanceError(f"{name} is unavailable") from exc
    if (
        unresolved != resolved
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise CPUPerformanceError(f"{name} is not an owner-controlled real directory")
    return resolved


def _decode_record_sha256(value: str, *, name: str) -> bytes:
    prefix = "sha256="
    encoded = value.removeprefix(prefix)
    if (
        not value.startswith(prefix)
        or re.fullmatch(r"[A-Za-z0-9_-]{43}", encoded) is None
    ):
        raise CPUPerformanceError(f"{name} is not canonical RECORD SHA-256")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=")
    except (ValueError, TypeError) as exc:
        raise CPUPerformanceError(f"{name} is not valid RECORD SHA-256") from exc
    if (
        len(decoded) != 32
        or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != encoded
    ):
        raise CPUPerformanceError(f"{name} is not canonical RECORD SHA-256")
    return decoded


def _record_site_path(path_text: str, *, site_packages: Path) -> Path:
    if (
        type(path_text) is not str
        or not path_text
        or "\\" in path_text
        or path_text.startswith("/")
    ):
        raise CPUPerformanceError("NumPy RECORD path is not canonical POSIX relative")
    pure = PurePosixPath(path_text)
    if (
        pure.as_posix() != path_text
        or any(part in ("", ".", "..") for part in pure.parts)
        or pure.parts[0] not in ("numpy", "numpy.libs", _NUMPY_DIST_INFO_DIRECTORY)
    ):
        raise CPUPerformanceError("NumPy RECORD path escaped its installed roots")
    return site_packages.joinpath(*pure.parts)


def _enumerate_owner_controlled_files(
    root: Path,
    *,
    top_level_names: Sequence[str],
    name: str,
) -> set[str]:
    observed: set[str] = set()
    pending: list[Path] = []
    for top_level_name in top_level_names:
        top = root / top_level_name
        _require_owner_controlled_real_directory(
            top,
            name=f"{name} root {top_level_name}",
        )
        pending.append(top)
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise CPUPerformanceError(f"{name} cannot be enumerated") from exc
        for entry in entries:
            path = Path(entry.path)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise CPUPerformanceError(f"{name} metadata is unavailable") from exc
            if stat.S_ISDIR(metadata.st_mode):
                if (
                    metadata.st_uid != os.geteuid()
                    or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                    or entry.is_symlink()
                ):
                    raise CPUPerformanceError(f"{name} directory is not owner-controlled")
                pending.append(path)
                continue
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                or metadata.st_nlink != 1
            ):
                raise CPUPerformanceError(f"{name} file is not owner-controlled")
            observed.add(path.relative_to(root).as_posix())
            if len(observed) > MAX_RUNTIME_MANIFEST_FILES:
                raise CPUPerformanceError(f"{name} exceeds its file-count envelope")
    return observed


def _numpy_installed_files_manifest(
    *,
    virtual_environment_root: Path,
    site_packages: Path,
) -> dict[str, object]:
    """Verify every NumPy RECORD row and every installed NumPy-owned file."""

    record_path = site_packages / _NUMPY_RECORD_SELF_PATH
    record_raw = _read_owner_controlled_regular_file(
        record_path,
        name="NumPy RECORD",
        maximum_bytes=MAX_PROFILE_BYTES,
    )
    if (
        not record_raw.endswith(b"\r\n")
        or b"\r" in record_raw.replace(b"\r\n", b"")
        or b"\n" in record_raw.replace(b"\r\n", b"")
    ):
        raise CPUPerformanceError("NumPy RECORD line endings are not canonical CRLF")
    try:
        record_text = record_raw.decode("ascii")
        parsed_rows = list(csv.reader(record_text.splitlines(), strict=True))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CPUPerformanceError("NumPy RECORD is not strict ASCII CSV") from exc
    if (
        not parsed_rows
        or len(parsed_rows) > MAX_RUNTIME_MANIFEST_FILES
        or any(len(row) != 3 for row in parsed_rows)
    ):
        raise CPUPerformanceError("NumPy RECORD row envelope changed")

    seen: set[str] = set()
    present_rows: dict[str, tuple[str, bytes]] = {}
    absent_rows: list[str] = []
    console_script_raw: bytes | None = None
    for index, row in enumerate(parsed_rows):
        path_text, encoded_digest, size_text = row
        if path_text in seen:
            raise CPUPerformanceError("NumPy RECORD contains a duplicate path")
        seen.add(path_text)
        row_name = f"NumPy RECORD row {index}"
        if path_text == _NUMPY_RECORD_SELF_PATH:
            if encoded_digest or size_text:
                raise CPUPerformanceError("NumPy RECORD self row must omit hash and size")
            file_raw = record_raw
            manifest_path = f"site-packages/{path_text}"
        else:
            expected_digest = _decode_record_sha256(encoded_digest, name=row_name)
            if (
                re.fullmatch(r"0|[1-9][0-9]*", size_text) is None
                or int(size_text) > MAX_RUNTIME_MANIFEST_BYTES
            ):
                raise CPUPerformanceError(f"{row_name} size is not canonical")
            if path_text in _NUMPY_RECORD_TYPED_ABSENT_PATHS:
                target = _record_site_path(path_text, site_packages=site_packages)
                _require_path_absent(target, name=f"typed-absent {path_text}")
                absent_rows.append(path_text)
                continue
            if path_text == _NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY:
                target = virtual_environment_root / "bin/f2py"
                manifest_path = "bin/f2py"
            else:
                target = _record_site_path(path_text, site_packages=site_packages)
                manifest_path = f"site-packages/{path_text}"
            file_raw = _read_owner_controlled_regular_file(
                target,
                name=f"installed NumPy file {path_text}",
                maximum_bytes=MAX_RUNTIME_MANIFEST_BYTES,
            )
            if len(file_raw) != int(size_text) or hashlib.sha256(file_raw).digest() != expected_digest:
                raise CPUPerformanceError(f"installed NumPy file changed: {path_text}")
            if path_text == _NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY:
                console_script_raw = file_raw
        present_rows[path_text] = (manifest_path, file_raw)

    if tuple(absent_rows) != _NUMPY_RECORD_TYPED_ABSENT_PATHS:
        raise CPUPerformanceError("NumPy RECORD typed-absent set changed")
    if console_script_raw is None:
        raise CPUPerformanceError("NumPy console script is unavailable")
    actual_site_files = _enumerate_owner_controlled_files(
        site_packages,
        top_level_names=("numpy", "numpy.libs", _NUMPY_DIST_INFO_DIRECTORY),
        name="installed NumPy distribution",
    )
    actual_record_paths = set(actual_site_files)
    actual_record_paths.add(_NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY)
    if actual_record_paths != set(present_rows):
        raise CPUPerformanceError("NumPy RECORD does not exactly enumerate installed files")

    manifest_rows = [
        {
            "path": manifest_path,
            "sha256": _sha256_bytes(file_raw),
            "size": len(file_raw),
        }
        for manifest_path, file_raw in sorted(
            present_rows.values(), key=lambda value: value[0]
        )
    ]
    total_bytes = sum(int(row["size"]) for row in manifest_rows)
    if total_bytes > MAX_RUNTIME_MANIFEST_BYTES:
        raise CPUPerformanceError("installed NumPy distribution exceeds its byte envelope")
    return {
        "schema_id": "betelgeuze.numpy_installed_files_manifest/1.0.0",
        "sha256": _sha256_json(manifest_rows),
        "file_count": len(manifest_rows),
        "total_bytes": total_bytes,
        "record_sha256": _sha256_bytes(record_raw),
        "record_byte_count": len(record_raw),
        "record_row_count": len(parsed_rows),
        "record_present_file_count": len(present_rows),
        "record_self_path": _NUMPY_RECORD_SELF_PATH,
        "record_console_script_entry": _NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY,
        "record_typed_absent_paths": list(_NUMPY_RECORD_TYPED_ABSENT_PATHS),
        "console_script_relative_path": "bin/f2py",
        "console_script_sha256": _sha256_bytes(console_script_raw),
        "console_script_byte_count": len(console_script_raw),
    }


def _runtime_directory_manifest(
    root: Path,
    *,
    top_level_names: Sequence[str],
    include_root: bool = False,
    schema_id: str,
    reject_bytecode: bool,
    allow_file_symlinks: bool,
    required_owner_uid: int | None = None,
    name: str,
) -> dict[str, object]:
    """Hash every reachable runtime file without following directory links."""

    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise CPUPerformanceError(f"{name} root is unavailable") from exc
    rows: list[dict[str, object]] = []
    total_bytes = 0
    pending: list[Path] = [root] if include_root else []
    if include_root and top_level_names:
        raise CPUPerformanceError(f"{name} manifest root selection is ambiguous")
    for top_level_name in top_level_names:
        if (
            type(top_level_name) is not str
            or not top_level_name
            or Path(top_level_name).name != top_level_name
        ):
            raise CPUPerformanceError(f"{name} top-level identity is invalid")
        top = root / top_level_name
        try:
            metadata = top.lstat()
        except OSError as exc:
            raise CPUPerformanceError(f"{name} payload is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise CPUPerformanceError(f"{name} payload root is not a real directory")
        pending.append(top)

    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise CPUPerformanceError(f"{name} payload cannot be enumerated") from exc
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise CPUPerformanceError(f"{name} payload metadata is unavailable") from exc
            if stat.S_ISDIR(metadata.st_mode):
                if (
                    required_owner_uid is not None
                    and metadata.st_uid != required_owner_uid
                ) or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                    raise CPUPerformanceError(
                        f"{name} payload directory is not owner-controlled"
                    )
                if reject_bytecode and entry.name == "__pycache__":
                    raise CPUPerformanceError(f"{name} bytecode cache is forbidden")
                pending.append(path)
                continue
            if reject_bytecode and path.suffix == ".pyc":
                raise CPUPerformanceError(f"{name} bytecode file is forbidden")
            row: dict[str, object] = {"path": relative}
            if stat.S_ISLNK(metadata.st_mode):
                if not allow_file_symlinks:
                    raise CPUPerformanceError(f"{name} payload symlink is forbidden")
                try:
                    target_text = os.readlink(path)
                    resolved = path.resolve(strict=True)
                    resolved_metadata = resolved.stat()
                except OSError as exc:
                    raise CPUPerformanceError(f"{name} payload symlink is invalid") from exc
                if not stat.S_ISREG(resolved_metadata.st_mode):
                    raise CPUPerformanceError(
                        f"{name} payload symlink target is not a regular file"
                    )
                if (
                    required_owner_uid is not None
                    and resolved_metadata.st_uid != required_owner_uid
                ) or resolved_metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                    raise CPUPerformanceError(
                        f"{name} payload symlink target is not owner-controlled"
                    )
                raw = _read_bounded_regular_file(
                    resolved,
                    name=f"{name} payload symlink target",
                    maximum_bytes=MAX_RUNTIME_MANIFEST_BYTES,
                    require_stable_size=True,
                )
                row.update({"kind": "symlink", "target": target_text})
            elif stat.S_ISREG(metadata.st_mode):
                if (
                    required_owner_uid is not None
                    and metadata.st_uid != required_owner_uid
                ) or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                    raise CPUPerformanceError(
                        f"{name} payload file is not owner-controlled"
                    )
                raw = _read_bounded_regular_file(
                    path,
                    name=f"{name} payload file",
                    maximum_bytes=MAX_RUNTIME_MANIFEST_BYTES,
                    require_stable_size=True,
                )
                row["kind"] = "regular"
            else:
                raise CPUPerformanceError(f"{name} payload file type is forbidden")
            row.update({"sha256": _sha256_bytes(raw), "size": len(raw)})
            rows.append(row)
            total_bytes += len(raw)
            if (
                len(rows) > MAX_RUNTIME_MANIFEST_FILES
                or total_bytes > MAX_RUNTIME_MANIFEST_BYTES
            ):
                raise CPUPerformanceError(f"{name} payload exceeds its envelope")

    rows.sort(key=lambda row: str(row["path"]))
    return {
        "schema_id": schema_id,
        "sha256": _sha256_json(rows),
        "file_count": len(rows),
        "total_bytes": total_bytes,
    }


def _loaded_dynamic_library_manifest(site_packages: Path) -> dict[str, object]:
    """Bind the actual shared-object closure mapped by the frozen runtime."""

    rows: list[dict[str, object]] = []
    observed: dict[Path, str] = {}
    try:
        map_lines = Path(f"/proc/{os.getpid()}/maps").read_text(
            encoding="ascii", errors="strict"
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        raise CPUPerformanceError("dynamic library mapping is unavailable") from exc
    stdlib_root = Path("/usr/lib/python3.10").resolve(strict=True)
    site_packages = site_packages.resolve(strict=True)
    for line in map_lines:
        fields = line.split()
        if len(fields) < 6:
            continue
        raw_path = fields[-1]
        if not raw_path.startswith("/") or ".so" not in Path(raw_path).name:
            continue
        try:
            path = Path(raw_path).resolve(strict=True)
        except OSError as exc:
            raise CPUPerformanceError("mapped dynamic library is unavailable") from exc
        try:
            relative = path.relative_to(site_packages).as_posix()
        except ValueError:
            try:
                relative = "stdlib/" + path.relative_to(stdlib_root).as_posix()
            except ValueError:
                relative = "system:" + str(path)
        else:
            relative = "qualified_site_packages/" + relative
        previous = observed.setdefault(path, relative)
        if previous != relative:
            raise CPUPerformanceError("dynamic library identity is ambiguous")
    total_bytes = 0
    for path, identity in sorted(observed.items(), key=lambda item: item[1]):
        raw = _read_bounded_regular_file(
            path,
            name="mapped dynamic library",
            maximum_bytes=MAX_RUNTIME_MANIFEST_BYTES,
            require_stable_size=True,
        )
        rows.append(
            {
                "path": identity,
                "sha256": _sha256_bytes(raw),
                "size": len(raw),
            }
        )
        total_bytes += len(raw)
        if total_bytes > MAX_RUNTIME_MANIFEST_BYTES:
            raise CPUPerformanceError("dynamic library closure exceeds its envelope")
    return {
        "schema_id": "betelgeuze.loaded_dynamic_library_manifest/1.0.0",
        "sha256": _sha256_json(rows),
        "file_count": len(rows),
        "total_bytes": total_bytes,
    }


def _verify_qualified_site_packages_inventory(expected_site: Path) -> None:
    try:
        site_entries = sorted(os.scandir(expected_site), key=lambda entry: entry.name)
    except OSError as exc:
        raise CPUPerformanceError("qualification site-packages is unavailable") from exc
    if tuple(entry.name for entry in site_entries) != (
        _QUALIFIED_SITE_PACKAGES_TOP_LEVEL
    ):
        raise CPUPerformanceError("qualification_site_packages_inventory_changed")
    for entry in site_entries:
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise CPUPerformanceError(
                "qualification site-packages metadata is unavailable"
            ) from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise CPUPerformanceError(
                "qualification site-packages inventory is not owner-controlled"
            )


def _qualification_runtime_roots() -> tuple[Path, Path, object, object]:
    launcher = Path(sys.executable).absolute()
    virtual_environment_root = launcher.parent.parent
    for path, name in (
        (virtual_environment_root, "qualification virtual environment"),
        (virtual_environment_root / "bin", "qualification virtual-environment bin"),
        (virtual_environment_root / "lib", "qualification virtual-environment lib"),
        (
            virtual_environment_root / "lib/python3.10",
            "qualification virtual-environment Python root",
        ),
        (
            virtual_environment_root / "lib/python3.10/site-packages",
            "qualification site-packages",
        ),
    ):
        _require_owner_controlled_real_directory(path, name=name)
    configuration = virtual_environment_root / "pyvenv.cfg"
    try:
        configuration_raw = _read_bounded_regular_file(
            configuration,
            name="qualification virtual-environment configuration",
            maximum_bytes=4096,
            require_single_link=True,
            require_stable_size=True,
        )
    except CPUPerformanceError as exc:
        raise CPUPerformanceError("clean_qualification_venv_unavailable") from exc
    if _sha256_bytes(configuration_raw) != _QUALIFIED_PYTHON_RUNTIME[
        "virtual_environment_configuration_sha256"
    ]:
        raise CPUPerformanceError("qualification_virtual_environment_not_clean")
    expected_site = virtual_environment_root / "lib/python3.10/site-packages"
    _verify_qualified_site_packages_inventory(expected_site)
    try:
        numpy = importlib.import_module("numpy")
        native = _load_native_module()
    except (ImportError, OSError) as exc:
        raise CPUPerformanceError("qualified_runtime_provider_unavailable") from exc
    numpy_path = Path(str(getattr(numpy, "__file__", ""))).resolve(strict=True)
    native_path = _native_extension_path(native)
    for path, name in ((numpy_path, "NumPy"), (native_path, "native extension")):
        try:
            path.relative_to(expected_site)
        except ValueError as exc:
            raise CPUPerformanceError(f"{name} is outside the clean qualification venv") from exc
    if numpy_path.parents[1] != expected_site or native_path.parents[1] != expected_site:
        raise CPUPerformanceError("qualification providers do not share one site-packages")
    root = _repository_root()
    for path, name in (
        (root, "repository root"),
        (root / "tools", "repository tools root"),
        (root / "betelgeuze_engine_v2", "Engine V2 package root"),
        (root / "betelgeuze_engine_v2/docking", "Engine V2 docking root"),
    ):
        _require_owner_controlled_real_directory(path, name=name)
    return virtual_environment_root, expected_site, numpy, native


def _qualified_python_runtime_projection() -> dict[str, object]:
    _require_path_absent(
        _QUALIFIED_STDLIB_ZIP_PATH,
        name="isolated standard-library zip",
    )
    executable = Path(sys.executable).resolve(strict=True)
    library_directory = sysconfig.get_config_var("LIBDIR")
    library_filename = sysconfig.get_config_var("LDLIBRARY")
    if type(library_directory) is not str or type(library_filename) is not str:
        raise CPUPerformanceError("python_shared_library_identity_unavailable")
    shared_library = (Path(library_directory) / library_filename).resolve(strict=True)
    virtual_environment_root, site_packages, numpy, native = (
        _qualification_runtime_roots()
    )
    try:
        numpy_core = importlib.import_module("numpy.core._multiarray_umath")
    except (ImportError, OSError) as exc:
        raise CPUPerformanceError("qualified_numpy_runtime_unavailable") from exc
    numpy_init = Path(str(getattr(numpy, "__file__", ""))).resolve(strict=True)
    numpy_core_path = Path(
        str(getattr(numpy_core, "__file__", ""))
    ).resolve(strict=True)
    native_extension_path = _native_extension_path(native)
    stdlib_manifest = _runtime_directory_manifest(
        Path("/usr/lib/python3.10"),
        top_level_names=(),
        include_root=True,
        schema_id="betelgeuze.python_stdlib_runtime_manifest/1.0.0",
        reject_bytecode=False,
        allow_file_symlinks=True,
        name="Python standard library",
    )
    numpy_manifest = _runtime_directory_manifest(
        site_packages,
        top_level_names=("numpy", "numpy.libs"),
        schema_id="betelgeuze.numpy_runtime_payload_manifest/1.0.0",
        reject_bytecode=True,
        allow_file_symlinks=False,
        required_owner_uid=os.geteuid(),
        name="NumPy runtime",
    )
    site_runtime_manifest = _runtime_directory_manifest(
        site_packages,
        top_level_names=("numpy", "numpy.libs", "betelgeuze_engine_v2_native"),
        schema_id="betelgeuze.qualified_site_packages_runtime_manifest/1.0.0",
        reject_bytecode=True,
        allow_file_symlinks=False,
        required_owner_uid=os.geteuid(),
        name="qualified site-packages runtime",
    )
    numpy_installed_manifest = _numpy_installed_files_manifest(
        virtual_environment_root=virtual_environment_root,
        site_packages=site_packages,
    )
    dynamic_manifest = _loaded_dynamic_library_manifest(site_packages)
    flags = {
        "isolated": sys.flags.isolated,
        "ignore_environment": sys.flags.ignore_environment,
        "no_site": sys.flags.no_site,
        "no_user_site": sys.flags.no_user_site,
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
        "hash_randomization": sys.flags.hash_randomization,
        "safe_path_supported": hasattr(sys.flags, "safe_path"),
        "safe_path": bool(getattr(sys.flags, "safe_path", False)),
    }
    expected_effective_paths = (
        *_QUALIFIED_ISOLATED_STDLIB_PATHS,
        str(_repository_root().resolve(strict=True)),
        str(site_packages),
    )
    if tuple(sys.path) != expected_effective_paths:
        raise CPUPerformanceError("qualified Python import path changed")
    if "" in sys.path or "sitecustomize" in sys.modules or "usercustomize" in sys.modules:
        raise CPUPerformanceError("qualified Python customization surface is active")
    projection: dict[str, object] = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": str(sys.implementation.cache_tag or ""),
        "python_soabi": str(sysconfig.get_config_var("SOABI") or ""),
        "python_byteorder": sys.byteorder,
        "python_executable_filename": executable.name,
        "python_executable_sha256": _sha256_regular_file(
            executable, name="Python executable"
        ),
        "python_shared_library_filename": shared_library.name,
        "python_shared_library_sha256": _sha256_regular_file(
            shared_library, name="Python shared library"
        ),
        "virtual_environment_configuration_sha256": _sha256_regular_file(
            virtual_environment_root / "pyvenv.cfg",
            name="qualification virtual-environment configuration",
        ),
        "python_stdlib_zip_path": str(_QUALIFIED_STDLIB_ZIP_PATH),
        "python_stdlib_zip_state": "required_absent",
        "stdlib_runtime_manifest_schema_id": stdlib_manifest["schema_id"],
        "stdlib_runtime_manifest_sha256": stdlib_manifest["sha256"],
        "stdlib_runtime_manifest_file_count": stdlib_manifest["file_count"],
        "stdlib_runtime_manifest_total_bytes": stdlib_manifest["total_bytes"],
        "dynamic_library_manifest_schema_id": dynamic_manifest["schema_id"],
        "dynamic_library_manifest_sha256": dynamic_manifest["sha256"],
        "dynamic_library_manifest_file_count": dynamic_manifest["file_count"],
        "dynamic_library_manifest_total_bytes": dynamic_manifest["total_bytes"],
        "native_distribution_name": "betelgeuze-engine-v2-native",
        "native_version": "0.2.0rc6",
        "native_extension_filename": native_extension_path.name,
        "native_extension_sha256": _sha256_regular_file(
            native_extension_path,
            name="qualified native extension",
        ),
        "native_distribution_metadata_sha256": _sha256_owner_controlled_regular_file(
            site_packages
            / "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/METADATA",
            name="native distribution metadata",
        ),
        "native_wheel_metadata_sha256": _sha256_owner_controlled_regular_file(
            site_packages
            / "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/WHEEL",
            name="native wheel metadata",
        ),
        "numpy_distribution_name": "numpy",
        "numpy_version": str(getattr(numpy, "__version__", "")),
        "numpy_distribution_metadata_sha256": _sha256_owner_controlled_regular_file(
            site_packages / "numpy-1.26.4.dist-info/METADATA",
            name="NumPy distribution metadata",
        ),
        "numpy_wheel_metadata_sha256": _sha256_owner_controlled_regular_file(
            site_packages / "numpy-1.26.4.dist-info/WHEEL",
            name="NumPy wheel metadata",
        ),
        "numpy_entry_points_sha256": _sha256_owner_controlled_regular_file(
            site_packages / "numpy-1.26.4.dist-info/entry_points.txt",
            name="NumPy entry-point metadata",
        ),
        "numpy_record_sha256": numpy_installed_manifest["record_sha256"],
        "numpy_record_byte_count": numpy_installed_manifest["record_byte_count"],
        "numpy_record_row_count": numpy_installed_manifest["record_row_count"],
        "numpy_record_present_file_count": numpy_installed_manifest[
            "record_present_file_count"
        ],
        "numpy_record_self_path": numpy_installed_manifest["record_self_path"],
        "numpy_record_console_script_entry": numpy_installed_manifest[
            "record_console_script_entry"
        ],
        "numpy_record_typed_absent_paths": numpy_installed_manifest[
            "record_typed_absent_paths"
        ],
        "numpy_installed_files_manifest_schema_id": numpy_installed_manifest[
            "schema_id"
        ],
        "numpy_installed_files_manifest_sha256": numpy_installed_manifest["sha256"],
        "numpy_installed_files_manifest_file_count": numpy_installed_manifest[
            "file_count"
        ],
        "numpy_installed_files_manifest_total_bytes": numpy_installed_manifest[
            "total_bytes"
        ],
        "numpy_console_script_relative_path": numpy_installed_manifest[
            "console_script_relative_path"
        ],
        "numpy_console_script_sha256": numpy_installed_manifest[
            "console_script_sha256"
        ],
        "numpy_console_script_byte_count": numpy_installed_manifest[
            "console_script_byte_count"
        ],
        "numpy_runtime_manifest_schema_id": numpy_manifest["schema_id"],
        "numpy_runtime_manifest_sha256": numpy_manifest["sha256"],
        "numpy_runtime_manifest_file_count": numpy_manifest["file_count"],
        "numpy_runtime_manifest_total_bytes": numpy_manifest["total_bytes"],
        "numpy_package_init_sha256": _sha256_regular_file(
            numpy_init, name="NumPy package initializer"
        ),
        "numpy_core_extension_filename": numpy_core_path.name,
        "numpy_core_extension_sha256": _sha256_regular_file(
            numpy_core_path, name="NumPy core extension"
        ),
        "qualified_site_packages_runtime_manifest_schema_id": (
            site_runtime_manifest["schema_id"]
        ),
        "qualified_site_packages_runtime_manifest_sha256": (
            site_runtime_manifest["sha256"]
        ),
        "qualified_site_packages_runtime_manifest_file_count": (
            site_runtime_manifest["file_count"]
        ),
        "qualified_site_packages_runtime_manifest_total_bytes": (
            site_runtime_manifest["total_bytes"]
        ),
        "site_packages_top_level_names": list(
            _QUALIFIED_SITE_PACKAGES_TOP_LEVEL
        ),
        "child_flags": flags,
        "bootstrap_path_roles": list(_QUALIFIED_BOOTSTRAP_PATH_ROLES),
        "isolated_stdlib_paths_sha256": _sha256_json(
            list(_QUALIFIED_ISOLATED_STDLIB_PATHS)
        ),
    }
    for name, expected in _QUALIFIED_PYTHON_RUNTIME.items():
        if projection[name] != expected:
            raise CPUPerformanceError(f"python_runtime_not_qualified:{name}")
    return projection


def _child_bootstrap_import_paths() -> tuple[str, ...]:
    _virtual_environment_root, site_packages, _numpy, _native = (
        _qualification_runtime_roots()
    )
    paths = (
        str(_repository_root().resolve(strict=True)),
        str(site_packages),
    )
    if len(set(paths)) != len(paths):
        raise CPUPerformanceError("child bootstrap import paths are ambiguous")
    return paths


def _native_child_binding_projection() -> dict[str, object]:
    root = _repository_root()
    module = _load_native_module()
    build_info = _validated_native_build_info(module)
    return {
        "performance_source_sha256": _sha256_owner_controlled_regular_file(
            Path(__file__).resolve(), name="performance source"
        ),
        "geometric_source_sha256": _sha256_owner_controlled_regular_file(
            root / "betelgeuze_engine_v2/docking/geometric_admission_v2.py",
            name="geometric source",
        ),
        "mixed64_source_sha256": _sha256_owner_controlled_regular_file(
            root / "betelgeuze_engine_v2/docking/mixed64_allocation.py",
            name="mixed64 allocation source",
        ),
        "native_extension_sha256": _sha256_owner_controlled_regular_file(
            _native_extension_path(module), name="native extension"
        ),
        "native_build_info": build_info,
    }


def _runtime_child_binding_projection() -> dict[str, object]:
    return {
        **_native_child_binding_projection(),
        "qualification_bootstrap_sha256": _sha256_owner_controlled_regular_file(
            _repository_root() / QUALIFICATION_BOOTSTRAP_RELATIVE_PATH,
            name="qualification bootstrap",
        ),
        "python_runtime": _qualified_python_runtime_projection(),
    }


def normalize_native_geometric_output(
    fixture: SyntheticGeometricFixtureV2,
) -> GeometricKernelOutputV2:
    """Run and normalize the exact Rust one-candidate geometric kernel."""

    if not isinstance(fixture, SyntheticGeometricFixtureV2):
        raise CPUPerformanceError("fixture must be SyntheticGeometricFixtureV2")
    module = _load_native_module()
    try:
        import numpy as np
    except ImportError as exc:
        raise CPUPerformanceError("numpy_required_for_native_kernel") from exc
    metrics = module.geometric_admission_metrics_one(
        np.asarray(fixture.ligand_coordinates, dtype=np.float64),
        ligand_vdw_radii=np.asarray(fixture.ligand_vdw_radii, dtype=np.float64),
        ligand_heavy_atom_mask=np.asarray(
            fixture.ligand_heavy_atom_mask, dtype=np.uint8
        ),
        receptor_coordinates=np.asarray(
            fixture.receptor_coordinates, dtype=np.float64
        ),
        receptor_vdw_radii=np.asarray(
            fixture.receptor_vdw_radii, dtype=np.float64
        ),
        pocket_center=np.asarray(fixture.pocket_center, dtype=np.float64),
        pocket_radius=fixture.pocket_radius,
    )
    return _output_from_metrics(metrics)


def _ordered_binary64_bits(value: float) -> int:
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    if bits & (1 << 63):
        return (~bits) & ((1 << 64) - 1)
    return bits | (1 << 63)


def _ulp_distance(left: float, right: float) -> int:
    return abs(_ordered_binary64_bits(left) - _ordered_binary64_bits(right))


@dataclass(frozen=True, slots=True)
class GeometricParityComparisonV2:
    passed: bool
    blockers: tuple[str, ...]
    max_ulp_by_field: Mapping[str, int]
    absolute_difference_binary64_hex_by_field: Mapping[str, str]


def compare_geometric_outputs(
    reference: GeometricKernelOutputV2,
    native: GeometricKernelOutputV2,
    profile: CPUPerformanceProfileV2 | None = None,
) -> GeometricParityComparisonV2:
    """Require exact integer/decision parity and frozen abs-or-ULP float parity."""

    if not isinstance(reference, GeometricKernelOutputV2) or not isinstance(
        native, GeometricKernelOutputV2
    ):
        raise CPUPerformanceError("parity inputs must be geometric kernel outputs")
    tolerances = (
        profile.float_tolerances if profile is not None else DEFAULT_FLOAT_TOLERANCES
    )
    if profile is not None:
        profile._assert_unchanged()
    blockers: list[str] = []
    for name in EXACT_INTEGER_FIELDS:
        if getattr(reference, name) != getattr(native, name):
            blockers.append(f"exact_integer_mismatch:{name}")
    if reference.decision != native.decision:
        blockers.append("geometric_decision_mismatch")
    ulps: dict[str, int] = {}
    differences: dict[str, str] = {}
    for name in FLOAT_FIELDS:
        left = getattr(reference, name)
        right = getattr(native, name)
        absolute = abs(left - right)
        distance = _ulp_distance(left, right)
        absolute_tolerance, maximum_ulp = tolerances[name]
        ulps[name] = distance
        differences[name] = absolute.hex()
        if absolute > absolute_tolerance and distance > maximum_ulp:
            blockers.append(f"binary64_parity_mismatch:{name}")
    return GeometricParityComparisonV2(
        passed=not blockers,
        blockers=tuple(blockers),
        max_ulp_by_field=MappingProxyType(ulps),
        absolute_difference_binary64_hex_by_field=MappingProxyType(differences),
    )


@dataclass(frozen=True, slots=True)
class CPUPerformanceProfileV2:
    _document_bytes: bytes = field(repr=False)
    profile_sha256: str
    source_path: Path | None = None
    fixtures: tuple[SyntheticFixtureSpecV2, ...] = field(init=False)
    float_tolerances: Mapping[str, tuple[float, int]] = field(init=False)

    def __post_init__(self) -> None:
        _require_digest(self.profile_sha256, name="profile_sha256")
        document = require_canonical_json_object_bytes(
            self._document_bytes,
            name="in-memory CPU performance profile",
            maximum_bytes=MAX_PROFILE_BYTES,
            trailing_newline_required=False,
        )
        fixture_specs = tuple(FROZEN_SYNTHETIC_FIXTURES)
        object.__setattr__(self, "fixtures", fixture_specs)
        parity = document["parity"]
        tolerances: dict[str, tuple[float, int]] = {}
        for name in FLOAT_FIELDS:
            row = parity["float_fields"][name]
            tolerances[name] = (
                _require_float_hex(
                    row["absolute_tolerance_binary64_hex"],
                    name=f"parity.float_fields.{name}.absolute_tolerance",
                ),
                _require_exact_int(
                    row["maximum_ulp_distance"],
                    name=f"parity.float_fields.{name}.maximum_ulp_distance",
                    maximum=1_000_000,
                ),
            )
        object.__setattr__(self, "float_tolerances", MappingProxyType(tolerances))

    @property
    def document(self) -> dict[str, Any]:
        return json.loads(self._document_bytes.decode("ascii"))

    def _assert_unchanged(self) -> None:
        observed = _sha256_bytes(self._document_bytes + b"\n")
        if observed != self.profile_sha256:
            raise CPUPerformanceError("CPU performance profile changed after validation")

    @property
    def warmup_count(self) -> int:
        self._assert_unchanged()
        return int(self.document["sampling"]["warmup_count"])

    @property
    def sample_count(self) -> int:
        self._assert_unchanged()
        return int(self.document["sampling"]["sample_count"])

    @property
    def child_timeout_seconds(self) -> int:
        self._assert_unchanged()
        return int(self.document["sampling"]["child_timeout_seconds"])

    @property
    def total_timeout_seconds(self) -> int:
        self._assert_unchanged()
        return int(self.document["sampling"]["total_timeout_seconds"])

    @property
    def expected_input_sha256s(self) -> Mapping[str, str]:
        self._assert_unchanged()
        return MappingProxyType(
            {
                row["fixture_id"]: row["expected_input_sha256"]
                for row in self.document["fixtures"]
            }
        )

    @property
    def expected_python_output_sha256s(self) -> Mapping[str, str]:
        self._assert_unchanged()
        return MappingProxyType(
            {
                row["fixture_id"]: row["expected_python_output_sha256"]
                for row in self.document["fixtures"]
            }
        )


def _verify_profile_fixture_rows(rows: object) -> None:
    if type(rows) is not list or len(rows) != len(FROZEN_SYNTHETIC_FIXTURES):
        raise CPUPerformanceError("profile fixtures are not the frozen set")
    for row, spec in zip(rows, FROZEN_SYNTHETIC_FIXTURES, strict=True):
        mapping = _require_exact_mapping_keys(
            row,
            name=f"fixtures.{spec.fixture_id}",
            keys=(
                "fixture_id",
                "generator_seed",
                "ligand_atom_count",
                "receptor_atom_count",
                "exact_pair_count",
                "expected_input_sha256",
                "expected_python_output_sha256",
                "synthetic_only",
            ),
        )
        if mapping["fixture_id"] != spec.fixture_id:
            raise CPUPerformanceError("profile fixture order or identity changed")
        for name, expected in (
            ("generator_seed", spec.seed),
            ("ligand_atom_count", spec.ligand_atom_count),
            ("receptor_atom_count", spec.receptor_atom_count),
            ("exact_pair_count", spec.exact_pair_count),
        ):
            if _require_exact_int(mapping[name], name=f"fixture.{name}") != expected:
                raise CPUPerformanceError(f"profile fixture {name} changed")
        if mapping["synthetic_only"] is not True:
            raise CPUPerformanceError("performance fixtures must remain synthetic-only")
        expected_input = _require_digest(
            mapping["expected_input_sha256"], name="expected_input_sha256"
        )
        expected_output = _require_digest(
            mapping["expected_python_output_sha256"],
            name="expected_python_output_sha256",
        )
        fixture = generate_synthetic_geometric_fixture(spec.fixture_id)
        if fixture.input_sha256 != expected_input:
            raise CPUPerformanceError("frozen synthetic input identity drifted")
        output = normalize_python_geometric_output(fixture)
        if output.output_sha256 != expected_output:
            raise CPUPerformanceError("frozen Python expected output identity drifted")


def verify_cpu_performance_profile_document(
    document: Mapping[str, Any],
    *,
    profile_sha256: str | None = None,
    source_path: Path | None = None,
) -> CPUPerformanceProfileV2:
    """Verify the complete v2 profile without granting execution authority."""

    profile = _require_exact_mapping_keys(
        document,
        name="CPU performance profile",
        keys=(
            "schema_id",
            "profile_id",
            "status",
            "authority",
            "restrictions",
            "runtime",
            "kernel",
            "fixtures",
            "parity",
            "sampling",
            "host",
            "gates",
        ),
    )
    if profile["schema_id"] != CPU_PERFORMANCE_PROFILE_SCHEMA_ID:
        raise CPUPerformanceError("CPU performance profile schema is unsupported")
    if profile["profile_id"] != PROFILE_ID:
        raise CPUPerformanceError("CPU performance profile identity changed")
    if profile["status"] != "synthetic_geometric_kernel_development_only":
        raise CPUPerformanceError("CPU performance profile status changed")
    if dict(profile["authority"]) != dict(AUTHORITY_FALSE):
        raise CPUPerformanceError("CPU performance profile authority must remain false")
    if dict(profile["restrictions"]) != dict(RESTRICTIONS):
        raise CPUPerformanceError("CPU performance restrictions changed")
    runtime = _require_exact_mapping_keys(
        profile["runtime"],
        name="runtime",
        keys=_QUALIFIED_PYTHON_RUNTIME,
    )
    if dict(runtime) != dict(_QUALIFIED_PYTHON_RUNTIME):
        raise CPUPerformanceError("CPU performance runtime lane changed")

    kernel = _require_exact_mapping_keys(
        profile["kernel"],
        name="kernel",
        keys=(
            "python_implementation_id",
            "native_implementation_id",
            "pair_traversal_order",
            "timed_boundary",
            "fixture_generator_id",
            "fixture_generator_source_sha256",
        ),
    )
    if kernel["python_implementation_id"] != PYTHON_GEOMETRIC_KERNEL_ID:
        raise CPUPerformanceError("Python geometric implementation identity changed")
    if kernel["native_implementation_id"] != NATIVE_GEOMETRIC_KERNEL_ID:
        raise CPUPerformanceError("native geometric implementation identity changed")
    if kernel["pair_traversal_order"] != PAIR_TRAVERSAL_ORDER:
        raise CPUPerformanceError("pair traversal order changed")
    if kernel["timed_boundary"] != (
        "fixed64_normalized_python_kernel_vs_pyo3_one_candidate_including_native_owned_copy"
    ):
        raise CPUPerformanceError("timed kernel boundary changed")
    if kernel["fixture_generator_id"] != SYNTHETIC_FIXTURE_GENERATOR_ID:
        raise CPUPerformanceError("synthetic generator identity changed")
    source_sha = _require_digest(
        kernel["fixture_generator_source_sha256"],
        name="fixture_generator_source_sha256",
    )
    if source_sha != _sha256_owner_controlled_regular_file(
        Path(__file__), name="performance source"
    ):
        raise CPUPerformanceError("synthetic generator source identity drifted")

    _verify_profile_fixture_rows(profile["fixtures"])
    parity = _require_exact_mapping_keys(
        profile["parity"],
        name="parity",
        keys=("exact_integer_fields", "exact_decision_required", "float_fields"),
    )
    if parity["exact_integer_fields"] != list(EXACT_INTEGER_FIELDS):
        raise CPUPerformanceError("exact integer parity fields changed")
    if parity["exact_decision_required"] is not True:
        raise CPUPerformanceError("decision parity must remain exact")
    float_rows = _require_exact_mapping_keys(
        parity["float_fields"],
        name="parity.float_fields",
        keys=FLOAT_FIELDS,
    )
    for name in FLOAT_FIELDS:
        row = _require_exact_mapping_keys(
            float_rows[name],
            name=f"parity.float_fields.{name}",
            keys=("absolute_tolerance_binary64_hex", "maximum_ulp_distance"),
        )
        absolute = _require_float_hex(
            row["absolute_tolerance_binary64_hex"], name=f"{name}.absolute_tolerance"
        )
        maximum_ulp = _require_exact_int(
            row["maximum_ulp_distance"], name=f"{name}.maximum_ulp", maximum=1_000_000
        )
        if (absolute, maximum_ulp) != DEFAULT_FLOAT_TOLERANCES[name]:
            raise CPUPerformanceError(f"float parity tolerance changed for {name}")

    sampling = _require_exact_mapping_keys(
        profile["sampling"],
        name="sampling",
        keys=(
            "warmup_count",
            "sample_count",
            "percentile_numerator",
            "percentile_denominator",
            "percentile_method",
            "launch_schedule_id",
            "process_isolation",
            "timer_methods",
            "child_timeout_seconds",
            "total_timeout_seconds",
            "child_output_max_bytes",
        ),
    )
    expected_sampling = {
        "warmup_count": 5,
        "sample_count": 30,
        "percentile_numerator": 95,
        "percentile_denominator": 100,
        "percentile_method": "nearest_rank_integer_v1",
        "launch_schedule_id": "paired_alternating_ab_ba_v2",
        "process_isolation": "separate_child_process_per_role_observation",
        "timer_methods": ["time.perf_counter_ns", "time.process_time_ns"],
        "child_timeout_seconds": 30,
        "total_timeout_seconds": 900,
        "child_output_max_bytes": MAX_CHILD_OUTPUT_BYTES,
    }
    if dict(sampling) != expected_sampling:
        raise CPUPerformanceError("CPU performance sampling contract changed")

    host = _require_exact_mapping_keys(
        profile["host"],
        name="host",
        keys=(
            "cpu_model_exact",
            "boost_disabled_required",
            "child_cpu_affinity",
            "os_task_count_exact",
            "thread_environment",
            "lane_role",
        ),
    )
    if dict(host) != {
        "cpu_model_exact": CPU_MODEL_EXACT,
        "boost_disabled_required": True,
        "child_cpu_affinity": list(AUTHORITATIVE_CPU_AFFINITY),
        "os_task_count_exact": 1,
        "thread_environment": dict(THREAD_ENVIRONMENT),
        "lane_role": "authoritative_local_thread1",
    }:
        raise CPUPerformanceError("authoritative host contract changed")

    gates = _require_exact_mapping_keys(
        profile["gates"],
        name="gates",
        keys=(
            "medium_large_minimum_p95_speedup_numerator",
            "medium_large_minimum_p95_speedup_denominator",
            "small_maximum_p95_regression_numerator",
            "small_maximum_p95_regression_denominator",
            "all_parity_rows_required",
            "memory_evidence_role",
            "fallback_allowed",
        ),
    )
    if dict(gates) != {
        "medium_large_minimum_p95_speedup_numerator": 3,
        "medium_large_minimum_p95_speedup_denominator": 2,
        "small_maximum_p95_regression_numerator": 1,
        "small_maximum_p95_regression_denominator": 20,
        "all_parity_rows_required": True,
        "memory_evidence_role": "descriptive_only_not_a_gate",
        "fallback_allowed": False,
    }:
        raise CPUPerformanceError("CPU performance numerical gates changed")

    profile_bytes = _canonical_json_bytes(profile) + b"\n"
    observed_sha = _sha256_bytes(profile_bytes)
    if profile_sha256 is not None and observed_sha != profile_sha256:
        raise CPUPerformanceError("CPU performance profile identity mismatch")
    return CPUPerformanceProfileV2(
        _document_bytes=_canonical_json_bytes(profile),
        profile_sha256=observed_sha,
        source_path=source_path,
    )


def load_cpu_performance_profile(path: Path) -> CPUPerformanceProfileV2:
    raw = _read_bounded_regular_file(
        Path(path),
        name="CPU performance profile",
        maximum_bytes=MAX_PROFILE_BYTES,
        require_single_link=True,
        require_stable_size=True,
    )
    document = require_canonical_json_object_bytes(
        raw,
        name="CPU performance profile",
        maximum_bytes=MAX_PROFILE_BYTES,
        trailing_newline_required=True,
    )
    return verify_cpu_performance_profile_document(
        document,
        profile_sha256=_sha256_bytes(raw),
        source_path=Path(path),
    )


def _read_proc_status(pid: int) -> dict[str, int]:
    try:
        raw = _read_bounded_regular_file(
            Path(f"/proc/{pid}/status"),
            name="process status",
            maximum_bytes=256 * 1024,
        )
    except CPUPerformanceError:
        return {}
    result: dict[str, int] = {}
    for line in raw.decode("ascii", "strict").splitlines():
        if line.startswith("Threads:"):
            fields = line.split()
            if len(fields) == 2 and fields[1].isdigit():
                result["threads"] = int(fields[1])
        elif line.startswith("VmRSS:") or line.startswith("VmHWM:"):
            fields = line.split()
            if len(fields) == 3 and fields[1].isdigit() and fields[2] == "kB":
                result[line[:5].lower()] = int(fields[1])
    return result


def _os_task_count(pid: int) -> int:
    try:
        with os.scandir(f"/proc/{pid}/task") as entries:
            return sum(1 for entry in entries if entry.name.isdigit())
    except OSError:
        return 0


def _process_start_ticks(pid: int) -> int:
    raw = _read_bounded_regular_file(
        Path(f"/proc/{pid}/stat"), name="process stat", maximum_bytes=64 * 1024
    )
    try:
        text = raw.decode("ascii")
        after_name = text.rsplit(")", 1)[1].strip().split()
        # Field 22 is starttime; after removing pid/comm, it is index 19.
        value = int(after_name[19])
    except (UnicodeDecodeError, IndexError, ValueError) as exc:
        raise CPUPerformanceError("process start identity is unavailable") from exc
    return _require_exact_int(
        value, name="process_start_ticks", minimum=1, maximum=MAX_SAFE_JSON_INTEGER
    )


def _cpu_model() -> str:
    raw = _read_bounded_regular_file(
        Path("/proc/cpuinfo"), name="CPU information", maximum_bytes=4 * 1024 * 1024
    )
    models = {
        line.split(":", 1)[1].strip()
        for line in raw.decode("ascii", "strict").splitlines()
        if line.startswith("model name") and ":" in line
    }
    if len(models) != 1:
        raise CPUPerformanceError("CPU model identity is ambiguous")
    return next(iter(models))


def _boost_disabled() -> bool:
    path = Path("/sys/devices/system/cpu/cpufreq/boost")
    raw = _read_bounded_regular_file(path, name="CPU boost state", maximum_bytes=32)
    if raw not in (b"0\n", b"1\n", b"0", b"1"):
        raise CPUPerformanceError("CPU boost state is invalid")
    return raw.strip() == b"0"


@dataclass(frozen=True, slots=True)
class HostExecutionContextV2:
    cpu_model: str
    boost_disabled: bool
    available_cpu_affinity: tuple[int, ...]
    platform_system: str
    platform_machine: str
    byteorder: str
    parent_pid: int
    parent_os_task_count: int
    qualified: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "cpu_model": self.cpu_model,
            "boost_disabled": self.boost_disabled,
            "available_cpu_affinity": list(self.available_cpu_affinity),
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "byteorder": self.byteorder,
            "parent_pid": self.parent_pid,
            "parent_os_task_count": self.parent_os_task_count,
            "qualified": self.qualified,
            "blockers": list(self.blockers),
        }


def derive_actual_host_execution_context() -> HostExecutionContextV2:
    """Read the current host.  Offline artifact verification never calls this."""

    blockers: list[str] = []
    try:
        model = _cpu_model()
    except CPUPerformanceError:
        model = ""
        blockers.append("cpu_model_unavailable")
    if model and model != CPU_MODEL_EXACT:
        blockers.append("cpu_model_not_qualified")
    try:
        boost_disabled = _boost_disabled()
    except CPUPerformanceError:
        boost_disabled = False
        blockers.append("boost_state_unavailable")
    if not boost_disabled and "boost_state_unavailable" not in blockers:
        blockers.append("cpu_boost_not_disabled")
    try:
        affinity = tuple(sorted(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        affinity = ()
        blockers.append("process_affinity_unavailable")
    if not set(AUTHORITATIVE_CPU_AFFINITY).issubset(affinity):
        blockers.append("authoritative_cpu_not_available")
    system = platform.system()
    machine = platform.machine()
    if system != "Linux":
        blockers.append("linux_host_required")
    if machine != "x86_64":
        blockers.append("x86_64_host_required")
    if sys.byteorder != "little":
        blockers.append("little_endian_host_required")
    parent_tasks = _os_task_count(os.getpid())
    if parent_tasks < 1:
        blockers.append("parent_os_task_count_unavailable")
    elif parent_tasks != 1:
        blockers.append("parent_os_task_count_not_one")
    return HostExecutionContextV2(
        cpu_model=model,
        boost_disabled=boost_disabled,
        available_cpu_affinity=affinity,
        platform_system=system,
        platform_machine=machine,
        byteorder=sys.byteorder,
        parent_pid=os.getpid(),
        parent_os_task_count=parent_tasks,
        qualified=not blockers,
        blockers=tuple(blockers),
    )


def _git_output(arguments: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            tuple(arguments),
            cwd=_repository_root(),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            },
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CPUPerformanceError("source_git_identity_unavailable") from exc
    return completed.stdout.strip()


def _derive_source_bindings() -> Mapping[str, object]:
    root = _repository_root()
    commit = _git_output(("git", "rev-parse", "HEAD"))
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise CPUPerformanceError("source commit identity is invalid")
    if _git_output(("git", "status", "--porcelain", "--untracked-files=all")):
        raise CPUPerformanceError("source_tree_not_clean")
    module = _load_native_module()
    info = _validated_native_build_info(module)
    cargo_lock = root / "rust_engine_v2/Cargo.lock"
    cargo_manifest = root / "rust_engine_v2/Cargo.toml"
    native_pyproject = root / "rust_engine_v2/pyproject.toml"
    rust_source = root / "rust_engine_v2/src/lib.rs"
    rust_build_script = root / "rust_engine_v2/build.rs"
    native_build_wrapper = root / "tools/build_engine_v2_native_wheel.py"
    qualification_bootstrap = root / QUALIFICATION_BOOTSTRAP_RELATIVE_PATH
    cargo_lock_sha = _sha256_owner_controlled_regular_file(cargo_lock, name="Cargo.lock")
    cargo_manifest_sha = _sha256_owner_controlled_regular_file(
        cargo_manifest, name="Cargo.toml"
    )
    native_pyproject_sha = _sha256_owner_controlled_regular_file(
        native_pyproject, name="native pyproject.toml"
    )
    rust_source_sha = _sha256_owner_controlled_regular_file(
        rust_source, name="Rust geometric source"
    )
    rust_build_script_sha = _sha256_owner_controlled_regular_file(
        rust_build_script, name="Rust build script"
    )
    native_build_wrapper_sha = _sha256_owner_controlled_regular_file(
        native_build_wrapper, name="native build wrapper"
    )
    qualification_bootstrap_sha = _sha256_owner_controlled_regular_file(
        qualification_bootstrap, name="qualification bootstrap"
    )
    if info.get("cargo_lock_sha256") != cargo_lock_sha:
        raise CPUPerformanceError("native_cargo_lock_binding_mismatch")
    if info.get("cargo_manifest_sha256") != cargo_manifest_sha:
        raise CPUPerformanceError("native_cargo_manifest_binding_mismatch")
    if info.get("native_pyproject_sha256") != native_pyproject_sha:
        raise CPUPerformanceError("native_pyproject_binding_mismatch")
    if info.get("rust_lib_sha256") != rust_source_sha:
        raise CPUPerformanceError("native_rust_source_binding_mismatch")
    if info.get("build_script_sha256") != rust_build_script_sha:
        raise CPUPerformanceError("native_build_script_binding_mismatch")
    if info.get("native_build_wrapper_sha256") != native_build_wrapper_sha:
        raise CPUPerformanceError("native_build_wrapper_binding_mismatch")
    module_path = _native_extension_path(module)
    geometric_source = root / "betelgeuze_engine_v2/docking/geometric_admission_v2.py"
    mixed64_source = root / "betelgeuze_engine_v2/docking/mixed64_allocation.py"
    performance_source = Path(__file__).resolve()
    bootstrap_import_paths = list(_child_bootstrap_import_paths())
    bindings: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_geometric_kernel_source_bindings/2.0.0",
        "source_commit": commit,
        "source_tree_clean": True,
        "python_runtime": _qualified_python_runtime_projection(),
        "performance_source_sha256": _sha256_owner_controlled_regular_file(
            performance_source, name="performance source"
        ),
        "geometric_source_sha256": _sha256_owner_controlled_regular_file(
            geometric_source, name="geometric source"
        ),
        "mixed64_source_sha256": _sha256_owner_controlled_regular_file(
            mixed64_source, name="mixed64 allocation source"
        ),
        "rust_source_sha256": rust_source_sha,
        "cargo_lock_sha256": cargo_lock_sha,
        "cargo_manifest_sha256": cargo_manifest_sha,
        "native_pyproject_sha256": native_pyproject_sha,
        "rust_build_script_sha256": rust_build_script_sha,
        "native_build_wrapper_sha256": native_build_wrapper_sha,
        "qualification_bootstrap_sha256": qualification_bootstrap_sha,
        "native_extension_sha256": _sha256_owner_controlled_regular_file(
            module_path, name="native extension"
        ),
        "native_extension_filename": module_path.name,
        "native_build_info": info,
        "child_runtime_binding_sha256": _sha256_json(
            _runtime_child_binding_projection()
        ),
        "child_bootstrap_import_paths": bootstrap_import_paths,
        "child_bootstrap_import_paths_sha256": _sha256_json(
            bootstrap_import_paths
        ),
        "fallback_allowed": False,
    }
    return MappingProxyType(bindings)


_CHILD_ENVIRONMENT: Final = MappingProxyType(
    {
        **dict(THREAD_ENVIRONMENT),
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
    }
)


def _sealed_child_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        **dict(_CHILD_ENVIRONMENT),
    }


def _prepare_child_kernel(
    role: str, fixture: SyntheticGeometricFixtureV2
) -> tuple[str, Any]:
    if role == "python_reference":
        # fixed64 validates and normalizes the entire batch once, then invokes
        # this exact kernel per generation-eligible candidate.  Timing the
        # public one-candidate validation wrapper would re-copy the full
        # receptor on every row and inflate the production baseline.
        from .geometric_admission_v2 import _evaluate_metrics

        def run_python() -> GeometricKernelOutputV2:
            metrics = _evaluate_metrics(
                fixture.ligand_coordinates,
                fixture.ligand_vdw_radii,
                fixture.ligand_heavy_atom_mask,
                fixture.receptor_coordinates,
                fixture.receptor_vdw_radii,
                fixture.pocket_center,
                fixture.pocket_radius,
            )
            return _output_from_metrics(metrics)

        return PYTHON_GEOMETRIC_KERNEL_ID, run_python
    if role != "rust_cpu":
        raise CPUPerformanceError("child implementation role is invalid")
    module = _load_native_module()
    try:
        import numpy as np
    except ImportError as exc:
        raise CPUPerformanceError("numpy_required_for_native_kernel") from exc
    ligand_coordinates = np.asarray(fixture.ligand_coordinates, dtype=np.float64)
    ligand_radii = np.asarray(fixture.ligand_vdw_radii, dtype=np.float64)
    heavy_mask = np.asarray(fixture.ligand_heavy_atom_mask, dtype=np.uint8)
    receptor_coordinates = np.asarray(fixture.receptor_coordinates, dtype=np.float64)
    receptor_radii = np.asarray(fixture.receptor_vdw_radii, dtype=np.float64)
    pocket_center = np.asarray(fixture.pocket_center, dtype=np.float64)

    def run_native() -> GeometricKernelOutputV2:
        metrics = module.geometric_admission_metrics_one(
            ligand_coordinates,
            ligand_vdw_radii=ligand_radii,
            ligand_heavy_atom_mask=heavy_mask,
            receptor_coordinates=receptor_coordinates,
            receptor_vdw_radii=receptor_radii,
            pocket_center=pocket_center,
            pocket_radius=fixture.pocket_radius,
        )
        return _output_from_metrics(metrics)

    return NATIVE_GEOMETRIC_KERNEL_ID, run_native


def _apply_child_resource_limits() -> None:
    # RLIMIT_AS is deliberately not lowered here: the qualified NumPy/native
    # runtime can reserve a large virtual address range without consuming
    # equivalent resident memory.  RSS/HWM remains descriptive and
    # never decides this gate.  CPU time, output size, descriptors, core dumps,
    # process groups, and wall-clock time are bounded independently.
    limits = (
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_FSIZE, MAX_CHILD_OUTPUT_BYTES),
        (resource.RLIMIT_NOFILE, MAX_CHILD_OPEN_FILES),
        (resource.RLIMIT_CPU, 35),
    )
    for limit, requested in limits:
        _soft, hard = resource.getrlimit(limit)
        bounded = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
        if requested > 0 and bounded <= 0:
            raise CPUPerformanceError("child resource limit cannot be enforced")
        try:
            resource.setrlimit(limit, (bounded, bounded))
        except (OSError, ValueError) as exc:
            raise CPUPerformanceError("child resource limit cannot be enforced") from exc
        if resource.getrlimit(limit) != (bounded, bounded):
            raise CPUPerformanceError("child resource limit did not bind exactly")


def _child_observation(
    *,
    run_nonce: str,
    global_launch_ordinal: int,
    fixture_id: str,
    phase: str,
    pair_index: int,
    role: str,
) -> dict[str, object]:
    _require_digest(run_nonce, name="run_nonce")
    _require_exact_int(global_launch_ordinal, name="global_launch_ordinal")
    _require_exact_int(pair_index, name="pair_index")
    if phase not in ("warmup", "sample"):
        raise CPUPerformanceError("child phase is invalid")
    entry_affinity = tuple(sorted(os.sched_getaffinity(0)))
    if not set(AUTHORITATIVE_CPU_AFFINITY).issubset(entry_affinity):
        raise CPUPerformanceError("authoritative child CPU is unavailable")
    os.sched_setaffinity(0, set(AUTHORITATIVE_CPU_AFFINITY))
    fixture = generate_synthetic_geometric_fixture(fixture_id)
    input_pre = fixture.input_sha256
    implementation_id, kernel = _prepare_child_kernel(role, fixture)
    runtime_binding_sha_pre = _sha256_json(_runtime_child_binding_projection())
    pre_affinity = tuple(sorted(os.sched_getaffinity(0)))
    pre_tasks = _os_task_count(os.getpid())
    pre_status = _read_proc_status(os.getpid())
    environment = {key: os.environ.get(key, "") for key in _CHILD_ENVIRONMENT}
    if environment != dict(_CHILD_ENVIRONMENT):
        raise CPUPerformanceError("child thread environment drifted")
    wall_start = time.perf_counter_ns()
    process_start = time.process_time_ns()
    output = kernel()
    process_end = time.process_time_ns()
    wall_end = time.perf_counter_ns()
    input_post = fixture.input_sha256
    runtime_binding_sha_post = _sha256_json(_runtime_child_binding_projection())
    post_affinity = tuple(sorted(os.sched_getaffinity(0)))
    post_tasks = _os_task_count(os.getpid())
    post_status = _read_proc_status(os.getpid())
    wall_duration = wall_end - wall_start
    process_duration = process_end - process_start
    if (
        wall_duration <= 0
        or process_duration <= 0
        or wall_duration > MAX_CHILD_DURATION_NS
        or process_duration > MAX_CHILD_DURATION_NS
    ):
        raise CPUPerformanceError("child timing is outside its envelope")
    if input_pre != input_post:
        raise CPUPerformanceError("synthetic input changed during kernel execution")
    if runtime_binding_sha_pre != runtime_binding_sha_post:
        raise CPUPerformanceError("child runtime source changed during kernel execution")
    output_document = output.to_dict()
    bootstrap_paths = list(_child_bootstrap_import_paths())
    bootstrap_paths_sha = _sha256_json(bootstrap_paths)
    return {
        "schema_id": GEOMETRIC_KERNEL_TRANSCRIPT_SCHEMA_ID,
        "run_nonce": run_nonce,
        "global_launch_ordinal": global_launch_ordinal,
        "fixture_id": fixture_id,
        "phase": phase,
        "pair_index": pair_index,
        "role": role,
        "implementation_id": implementation_id,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "process_start_ticks": _process_start_ticks(os.getpid()),
        "entry_affinity": list(entry_affinity),
        "pre_kernel_affinity": list(pre_affinity),
        "post_kernel_affinity": list(post_affinity),
        "pre_kernel_os_task_count": pre_tasks,
        "post_kernel_os_task_count": post_tasks,
        "pre_kernel_vmrss_kib": pre_status.get("vmrss", 0),
        "post_kernel_vmrss_kib": post_status.get("vmrss", 0),
        "pre_kernel_vmhwm_kib": pre_status.get("vmhwm", 0),
        "post_kernel_vmhwm_kib": post_status.get("vmhwm", 0),
        "thread_environment": environment,
        "thread_environment_sha256": _sha256_json(environment),
        "python_isolated_mode": sys.flags.isolated == 1,
        "python_no_site_mode": sys.flags.no_site == 1,
        "python_no_user_site_mode": sys.flags.no_user_site == 1,
        "python_ignore_environment_mode": sys.flags.ignore_environment == 1,
        "python_dont_write_bytecode_mode": sys.flags.dont_write_bytecode == 1,
        "python_hash_randomization_mode": sys.flags.hash_randomization == 1,
        "python_safe_path_supported": hasattr(sys.flags, "safe_path"),
        "python_safe_path_mode": bool(getattr(sys.flags, "safe_path", False)),
        "empty_import_path_present": "" in sys.path,
        "sitecustomize_loaded": "sitecustomize" in sys.modules,
        "usercustomize_loaded": "usercustomize" in sys.modules,
        "python_import_paths": list(sys.path),
        "bootstrap_import_paths": bootstrap_paths,
        "bootstrap_import_paths_sha256": bootstrap_paths_sha,
        "wall_start_ns": wall_start,
        "wall_end_ns": wall_end,
        "wall_duration_ns": wall_duration,
        "process_cpu_start_ns": process_start,
        "process_cpu_end_ns": process_end,
        "process_cpu_duration_ns": process_duration,
        "input_sha256_pre": input_pre,
        "input_sha256_post": input_post,
        "exact_pair_count": fixture.exact_pair_count,
        "output": output_document,
        "output_sha256": output.output_sha256,
        "runtime_source_binding_sha256_pre": runtime_binding_sha_pre,
        "runtime_source_binding_sha256_post": runtime_binding_sha_post,
        "fallback_used": False,
        "contains_molecular_input": False,
        "contains_case_identity": False,
    }


def _child_main(arguments: argparse.Namespace) -> int:
    try:
        _apply_child_resource_limits()
        document = _child_observation(
            run_nonce=arguments.run_nonce,
            global_launch_ordinal=arguments.global_launch_ordinal,
            fixture_id=arguments.fixture_id,
            phase=arguments.phase,
            pair_index=arguments.pair_index,
            role=arguments.role,
        )
        raw = _canonical_json_bytes(document)
        if len(raw) > MAX_CHILD_OUTPUT_BYTES:
            raise CPUPerformanceError("child transcript exceeds its byte limit")
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        return 0
    except Exception as exc:  # fail closed at the process boundary
        error = {
            "error": type(exc).__name__,
            "message": str(exc)[:512],
        }
        sys.stderr.buffer.write(_canonical_json_bytes(error))
        sys.stderr.buffer.flush()
        return 2


def _bounded_temp_output_bytes(file: Any, *, name: str) -> bytes:
    file.flush()
    size = os.fstat(file.fileno()).st_size
    if size > MAX_CHILD_OUTPUT_BYTES:
        raise CPUPerformanceError(f"{name} exceeds the child output limit")
    file.seek(0)
    raw = file.read(MAX_CHILD_OUTPUT_BYTES + 1)
    if len(raw) > MAX_CHILD_OUTPUT_BYTES:
        raise CPUPerformanceError(f"{name} exceeds the child output limit")
    return raw


def _launch_sealed_child(
    *,
    run_nonce: str,
    global_launch_ordinal: int,
    fixture_id: str,
    phase: str,
    pair_index: int,
    role: str,
    timeout_seconds: float,
    absolute_deadline_monotonic: float | None = None,
) -> Mapping[str, Any]:
    """Launch one repository-owned observation with bounded output and timeout."""

    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0.0
        or timeout_seconds > 60.0
    ):
        raise CPUPerformanceError("sealed child timeout is outside its envelope")

    launch_clock = time.monotonic()
    if absolute_deadline_monotonic is None:
        absolute_deadline_monotonic = launch_clock + timeout_seconds
    if (
        type(absolute_deadline_monotonic) not in (int, float)
        or not math.isfinite(absolute_deadline_monotonic)
        or absolute_deadline_monotonic <= launch_clock
    ):
        raise CPUPerformanceError("sealed child absolute deadline has expired")
    child_deadline = min(
        launch_clock + timeout_seconds, float(absolute_deadline_monotonic)
    )

    _child_bootstrap_import_paths()
    command = (
        sys.executable,
        "-I",
        "-S",
        "-B",
        str(_repository_root() / QUALIFICATION_BOOTSTRAP_RELATIVE_PATH),
        "--sealed-child",
        "--run-nonce",
        run_nonce,
        "--global-launch-ordinal",
        str(global_launch_ordinal),
        "--fixture-id",
        fixture_id,
        "--phase",
        phase,
        "--pair-index",
        str(pair_index),
        "--role",
        role,
    )
    process: subprocess.Popen[bytes] | None = None
    parent_launch_start_ns = time.perf_counter_ns()
    parent_launch_end_ns = 0
    observed_start_ticks = 0
    observed_process_group = 0
    observed_session = 0
    maximum_tasks = 0
    maximum_vmrss = 0
    maximum_vmhwm = 0
    with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
        mode="w+b"
    ) as stderr_file:
        try:
            if time.monotonic() >= child_deadline:
                raise CPUPerformanceError(
                    "sealed child timed out before process start"
                )
            try:
                process = subprocess.Popen(
                    command,
                    cwd=_repository_root(),
                    env=_sealed_child_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True,
                    close_fds=True,
                )
            except OSError as exc:
                raise CPUPerformanceError("sealed child could not start") from exc
            if time.monotonic() >= child_deadline:
                raise CPUPerformanceError("sealed child timed out during process start")
            while process.poll() is None:
                if observed_start_ticks == 0:
                    try:
                        observed_start_ticks = _process_start_ticks(process.pid)
                        observed_process_group = os.getpgid(process.pid)
                        observed_session = os.getsid(process.pid)
                    except (CPUPerformanceError, ProcessLookupError):
                        pass
                status = _read_proc_status(process.pid)
                maximum_tasks = max(maximum_tasks, _os_task_count(process.pid))
                maximum_vmrss = max(maximum_vmrss, status.get("vmrss", 0))
                maximum_vmhwm = max(maximum_vmhwm, status.get("vmhwm", 0))
                if (
                    os.fstat(stdout_file.fileno()).st_size > MAX_CHILD_OUTPUT_BYTES
                    or os.fstat(stderr_file.fileno()).st_size > MAX_CHILD_OUTPUT_BYTES
                ):
                    raise CPUPerformanceError("sealed child exceeded its output limit")
                if time.monotonic() >= child_deadline:
                    raise CPUPerformanceError("sealed child timed out")
                time.sleep(CHILD_POLL_INTERVAL_SECONDS)
            return_code = process.wait(timeout=5)
            parent_launch_end_ns = time.perf_counter_ns()
            group_survived = False
            try:
                os.killpg(process.pid, 0)
                group_survived = True
            except ProcessLookupError:
                pass
            if group_survived:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                raise CPUPerformanceError("sealed child left a surviving descendant")
            stdout = _bounded_temp_output_bytes(
                stdout_file, name="sealed child stdout"
            )
            stderr = _bounded_temp_output_bytes(
                stderr_file, name="sealed child stderr"
            )
        finally:
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    if return_code != 0 or stderr:
        detail = stderr.decode("ascii", "replace")[:512]
        raise CPUPerformanceError(f"sealed child failed closed: {detail}")
    child = dict(
        require_canonical_json_object_bytes(
            stdout,
            name="sealed child transcript",
            maximum_bytes=MAX_CHILD_OUTPUT_BYTES,
            trailing_newline_required=False,
        )
    )
    if child.get("pid") != process.pid or child.get("ppid") != os.getpid():
        raise CPUPerformanceError("sealed child process lineage is invalid")
    if (
        observed_start_ticks <= 0
        or observed_process_group != process.pid
        or observed_session != process.pid
    ):
        raise CPUPerformanceError("parent could not bind the child process identity")
    child.update(
        {
            "parent_launch_start_ns": parent_launch_start_ns,
            "parent_launch_end_ns": parent_launch_end_ns,
            "parent_observed_pid": process.pid,
            "parent_observed_process_start_ticks": observed_start_ticks,
            "parent_observed_process_group": observed_process_group,
            "parent_observed_session": observed_session,
            "parent_observed_max_os_task_count": maximum_tasks,
            "parent_observed_max_vmrss_kib": maximum_vmrss,
            "parent_observed_max_vmhwm_kib": maximum_vmhwm,
        }
    )
    return MappingProxyType(child)


def _expected_launch_schedule(profile: CPUPerformanceProfileV2) -> list[dict[str, object]]:
    profile._assert_unchanged()
    schedule: list[dict[str, object]] = []
    ordinal = 0
    for fixture in profile.fixtures:
        for phase, count in (
            ("warmup", profile.warmup_count),
            ("sample", profile.sample_count),
        ):
            for pair_index in range(count):
                roles = (
                    ("python_reference", "rust_cpu")
                    if pair_index % 2 == 0
                    else ("rust_cpu", "python_reference")
                )
                for role in roles:
                    schedule.append(
                        {
                            "global_launch_ordinal": ordinal,
                            "fixture_id": fixture.fixture_id,
                            "phase": phase,
                            "pair_index": pair_index,
                            "role": role,
                        }
                    )
                    ordinal += 1
    return schedule


def _measurement_contract(
    profile: CPUPerformanceProfileV2,
    transcript: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    expected = _expected_launch_schedule(profile)
    actual = [
        {
            "global_launch_ordinal": row["global_launch_ordinal"],
            "fixture_id": row["fixture_id"],
            "phase": row["phase"],
            "pair_index": row["pair_index"],
            "role": row["role"],
        }
        for row in transcript
    ]
    return {
        "launch_schedule_id": "paired_alternating_ab_ba_v2",
        "expected_observation_count": len(expected),
        "expected_launch_schedule": expected,
        "expected_launch_schedule_sha256": _sha256_json(expected),
        "actual_observation_count": len(actual),
        "actual_launch_schedule_sha256": _sha256_json(actual),
        "warmup_count_per_role_fixture": profile.warmup_count,
        "sample_count_per_role_fixture": profile.sample_count,
        "percentile_method": "nearest_rank_integer_v1",
        "wall_timer": "time.perf_counter_ns",
        "process_cpu_timer": "time.process_time_ns",
        "memory_evidence_role": "descriptive_only_not_a_gate",
    }


def _geometric_output_from_document(document: object) -> GeometricKernelOutputV2:
    expected_keys = {
        "schema_id",
        *EXACT_INTEGER_FIELDS,
        *(f"{name}_binary64_hex" for name in FLOAT_FIELDS),
        "hard_rejection_minimum_vdw_ratio_binary64_hex",
        "decision",
    }
    output = _require_exact_mapping_keys(
        document, name="geometric kernel output", keys=expected_keys
    )
    if output["schema_id"] != GEOMETRIC_KERNEL_OUTPUT_SCHEMA_ID:
        raise CPUPerformanceError("geometric output schema changed")
    from .geometric_admission_v2 import HARD_REJECTION_MINIMUM_VDW_RATIO

    if _require_float_hex(
        output["hard_rejection_minimum_vdw_ratio_binary64_hex"],
        name="hard rejection threshold",
    ) != HARD_REJECTION_MINIMUM_VDW_RATIO:
        raise CPUPerformanceError("geometric output threshold changed")
    values: dict[str, object] = {
        name: _require_exact_int(output[name], name=f"output.{name}")
        for name in EXACT_INTEGER_FIELDS
    }
    values.update(
        {
            name: _require_float_hex(
                output[f"{name}_binary64_hex"], name=f"output.{name}"
            )
            for name in FLOAT_FIELDS
        }
    )
    values["decision"] = output["decision"]
    return GeometricKernelOutputV2(**values)  # type: ignore[arg-type]


_TRANSCRIPT_KEYS: Final = frozenset(
    {
        "schema_id",
        "run_nonce",
        "global_launch_ordinal",
        "fixture_id",
        "phase",
        "pair_index",
        "role",
        "implementation_id",
        "pid",
        "ppid",
        "process_start_ticks",
        "entry_affinity",
        "pre_kernel_affinity",
        "post_kernel_affinity",
        "pre_kernel_os_task_count",
        "post_kernel_os_task_count",
        "pre_kernel_vmrss_kib",
        "post_kernel_vmrss_kib",
        "pre_kernel_vmhwm_kib",
        "post_kernel_vmhwm_kib",
        "parent_observed_max_os_task_count",
        "parent_observed_max_vmrss_kib",
        "parent_observed_max_vmhwm_kib",
        "parent_launch_start_ns",
        "parent_launch_end_ns",
        "parent_observed_pid",
        "parent_observed_process_start_ticks",
        "parent_observed_process_group",
        "parent_observed_session",
        "thread_environment",
        "thread_environment_sha256",
        "python_isolated_mode",
        "python_no_site_mode",
        "python_no_user_site_mode",
        "python_ignore_environment_mode",
        "python_dont_write_bytecode_mode",
        "python_hash_randomization_mode",
        "python_safe_path_supported",
        "python_safe_path_mode",
        "empty_import_path_present",
        "sitecustomize_loaded",
        "usercustomize_loaded",
        "python_import_paths",
        "bootstrap_import_paths",
        "bootstrap_import_paths_sha256",
        "wall_start_ns",
        "wall_end_ns",
        "wall_duration_ns",
        "process_cpu_start_ns",
        "process_cpu_end_ns",
        "process_cpu_duration_ns",
        "input_sha256_pre",
        "input_sha256_post",
        "exact_pair_count",
        "output",
        "output_sha256",
        "runtime_source_binding_sha256_pre",
        "runtime_source_binding_sha256_post",
        "fallback_used",
        "contains_molecular_input",
        "contains_case_identity",
    }
)


def _validate_transcript_rows(
    rows: object,
    *,
    profile: CPUPerformanceProfileV2,
    run_nonce: str,
    parent_pid: int,
    source_bindings: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if type(rows) is not list:
        raise CPUPerformanceError("performance transcript must be a list")
    expected_schedule = _expected_launch_schedule(profile)
    if len(rows) != len(expected_schedule):
        raise CPUPerformanceError("performance transcript denominator changed")
    fixture_inputs = {
        fixture.fixture_id: generate_synthetic_geometric_fixture(fixture.fixture_id)
        for fixture in profile.fixtures
    }
    expected_outputs = {
        fixture_id: normalize_python_geometric_output(fixture)
        for fixture_id, fixture in fixture_inputs.items()
    }
    observed_processes: set[tuple[int, int]] = set()
    validated: list[Mapping[str, Any]] = []
    previous_parent_launch_end_ns = 0
    for index, (value, expected) in enumerate(
        zip(rows, expected_schedule, strict=True)
    ):
        row = _require_exact_mapping_keys(
            value, name=f"transcript[{index}]", keys=_TRANSCRIPT_KEYS
        )
        if row["schema_id"] != GEOMETRIC_KERNEL_TRANSCRIPT_SCHEMA_ID:
            raise CPUPerformanceError("child transcript schema changed")
        if row["run_nonce"] != run_nonce:
            raise CPUPerformanceError("child transcript run nonce cross-wired")
        for name, expected_value in expected.items():
            if row[name] != expected_value:
                raise CPUPerformanceError("child launch schedule changed or reordered")
        role = str(row["role"])
        implementation_id = str(row["implementation_id"])
        expected_implementation = (
            PYTHON_GEOMETRIC_KERNEL_ID
            if role == "python_reference"
            else NATIVE_GEOMETRIC_KERNEL_ID
        )
        if implementation_id != expected_implementation:
            raise CPUPerformanceError("child implementation identity cross-wired")
        pid = _require_exact_int(row["pid"], name="child pid", minimum=1)
        ppid = _require_exact_int(row["ppid"], name="child ppid", minimum=1)
        start_ticks = _require_exact_int(
            row["process_start_ticks"], name="process_start_ticks", minimum=1
        )
        if ppid != parent_pid:
            raise CPUPerformanceError("child parent process identity changed")
        for name, expected_value in (
            ("parent_observed_pid", pid),
            ("parent_observed_process_start_ticks", start_ticks),
            ("parent_observed_process_group", pid),
            ("parent_observed_session", pid),
        ):
            if _require_exact_int(row[name], name=name, minimum=1) != expected_value:
                raise CPUPerformanceError("parent-observed process identity changed")
        process_identity = (pid, start_ticks)
        if process_identity in observed_processes:
            raise CPUPerformanceError("child process identity was reused")
        observed_processes.add(process_identity)
        entry_affinity = row["entry_affinity"]
        if (
            type(entry_affinity) is not list
            or any(type(cpu) is not int or cpu < 0 for cpu in entry_affinity)
            or not set(AUTHORITATIVE_CPU_AFFINITY).issubset(entry_affinity)
        ):
            raise CPUPerformanceError("child entry affinity is invalid")
        for name in ("pre_kernel_affinity", "post_kernel_affinity"):
            if row[name] != list(AUTHORITATIVE_CPU_AFFINITY):
                raise CPUPerformanceError("child kernel affinity drifted")
        for name in (
            "pre_kernel_os_task_count",
            "post_kernel_os_task_count",
            "parent_observed_max_os_task_count",
        ):
            if _require_exact_int(row[name], name=name, minimum=1, maximum=1024) != 1:
                raise CPUPerformanceError("child OS task count exceeded one")
        for name in (
            "pre_kernel_vmrss_kib",
            "post_kernel_vmrss_kib",
            "pre_kernel_vmhwm_kib",
            "post_kernel_vmhwm_kib",
            "parent_observed_max_vmrss_kib",
            "parent_observed_max_vmhwm_kib",
        ):
            _require_exact_int(
                row[name], name=name, minimum=0, maximum=MAX_RECORDED_RSS_KIB
            )
        if dict(row["thread_environment"]) != dict(_CHILD_ENVIRONMENT):
            raise CPUPerformanceError("child thread environment changed")
        if row["thread_environment_sha256"] != _sha256_json(
            dict(_CHILD_ENVIRONMENT)
        ):
            raise CPUPerformanceError("child thread environment identity changed")
        for name in (
            "python_isolated_mode",
            "python_no_site_mode",
            "python_no_user_site_mode",
            "python_ignore_environment_mode",
            "python_dont_write_bytecode_mode",
            "python_hash_randomization_mode",
        ):
            if _require_exact_bool(row[name], name=name) is not True:
                raise CPUPerformanceError("child Python isolation changed")
        for name in (
            "python_safe_path_supported",
            "python_safe_path_mode",
            "empty_import_path_present",
            "sitecustomize_loaded",
            "usercustomize_loaded",
        ):
            if _require_exact_bool(row[name], name=name) is not False:
                raise CPUPerformanceError("child customization module was loaded")
        expected_bootstrap_paths = source_bindings.get(
            "child_bootstrap_import_paths"
        )
        if row["bootstrap_import_paths"] != expected_bootstrap_paths:
            raise CPUPerformanceError("child bootstrap import paths changed")
        if row["bootstrap_import_paths_sha256"] != source_bindings.get(
            "child_bootstrap_import_paths_sha256"
        ):
            raise CPUPerformanceError("child bootstrap import paths changed")
        expected_import_paths = [
            *_QUALIFIED_ISOLATED_STDLIB_PATHS,
            *list(expected_bootstrap_paths),
        ]
        if row["python_import_paths"] != expected_import_paths:
            raise CPUPerformanceError("child effective import path changed")
        wall_start = _require_exact_int(
            row["wall_start_ns"], name="wall_start_ns", minimum=1
        )
        wall_end = _require_exact_int(row["wall_end_ns"], name="wall_end_ns", minimum=1)
        wall_duration = _require_exact_int(
            row["wall_duration_ns"],
            name="wall_duration_ns",
            minimum=1,
            maximum=MAX_CHILD_DURATION_NS,
        )
        cpu_start = _require_exact_int(
            row["process_cpu_start_ns"], name="process_cpu_start_ns", minimum=1
        )
        cpu_end = _require_exact_int(
            row["process_cpu_end_ns"], name="process_cpu_end_ns", minimum=1
        )
        cpu_duration = _require_exact_int(
            row["process_cpu_duration_ns"],
            name="process_cpu_duration_ns",
            minimum=1,
            maximum=MAX_CHILD_DURATION_NS,
        )
        if wall_end - wall_start != wall_duration or cpu_end - cpu_start != cpu_duration:
            raise CPUPerformanceError("child timing arithmetic does not rederive")
        parent_start = _require_exact_int(
            row["parent_launch_start_ns"], name="parent_launch_start_ns", minimum=1
        )
        parent_end = _require_exact_int(
            row["parent_launch_end_ns"], name="parent_launch_end_ns", minimum=1
        )
        if not (
            previous_parent_launch_end_ns <= parent_start
            <= wall_start
            <= wall_end
            <= parent_end
        ):
            raise CPUPerformanceError("parent-observed launch chronology is invalid")
        if parent_end - parent_start > MAX_CHILD_DURATION_NS + 5_000_000_000:
            raise CPUPerformanceError("parent-observed launch duration is unbounded")
        previous_parent_launch_end_ns = parent_end
        fixture = fixture_inputs[str(row["fixture_id"])]
        if (
            row["input_sha256_pre"] != fixture.input_sha256
            or row["input_sha256_post"] != fixture.input_sha256
        ):
            raise CPUPerformanceError("child synthetic input identity changed")
        if row["exact_pair_count"] != fixture.exact_pair_count:
            raise CPUPerformanceError("child exact pair denominator changed")
        output = _geometric_output_from_document(row["output"])
        if row["output_sha256"] != output.output_sha256:
            raise CPUPerformanceError("child output identity changed")
        expected_runtime_binding = source_bindings.get(
            "child_runtime_binding_sha256"
        )
        if (
            row["runtime_source_binding_sha256_pre"] != expected_runtime_binding
            or row["runtime_source_binding_sha256_post"] != expected_runtime_binding
        ):
            raise CPUPerformanceError("child runtime source binding changed")
        if output.exact_pair_count != fixture.exact_pair_count:
            raise CPUPerformanceError("child output pair denominator changed")
        if role == "python_reference":
            if output.output_sha256 != expected_outputs[fixture.fixture_id].output_sha256:
                raise CPUPerformanceError("Python reference output drifted")
        else:
            parity = compare_geometric_outputs(
                expected_outputs[fixture.fixture_id], output, profile
            )
            if not parity.passed:
                raise CPUPerformanceError("native geometric output parity failed")
        if (
            _require_exact_bool(row["fallback_used"], name="fallback_used")
            or _require_exact_bool(
                row["contains_molecular_input"], name="contains_molecular_input"
            )
            or _require_exact_bool(
                row["contains_case_identity"], name="contains_case_identity"
            )
        ):
            raise CPUPerformanceError("forbidden child execution state was observed")
        validated.append(MappingProxyType(dict(row)))
    return tuple(validated)


def _nearest_rank(values: Sequence[int], *, numerator: int, denominator: int) -> int:
    if not values or numerator <= 0 or denominator <= 0 or numerator > denominator:
        raise CPUPerformanceError("nearest-rank percentile input is invalid")
    ordered = sorted(values)
    rank = (len(ordered) * numerator + denominator - 1) // denominator
    return ordered[rank - 1]


def _derive_fixture_results(
    transcript: Sequence[Mapping[str, Any]], profile: CPUPerformanceProfileV2
) -> tuple[tuple[dict[str, object], ...], bool, tuple[str, ...]]:
    results: list[dict[str, object]] = []
    all_blockers: list[str] = []
    for spec in profile.fixtures:
        sample_rows = [
            row
            for row in transcript
            if row["fixture_id"] == spec.fixture_id and row["phase"] == "sample"
        ]
        warmup_rows = [
            row
            for row in transcript
            if row["fixture_id"] == spec.fixture_id and row["phase"] == "warmup"
        ]
        baseline_rows = [row for row in sample_rows if row["role"] == "python_reference"]
        native_rows = [row for row in sample_rows if row["role"] == "rust_cpu"]
        if (
            len(baseline_rows) != profile.sample_count
            or len(native_rows) != profile.sample_count
            or len(warmup_rows) != profile.warmup_count * 2
        ):
            raise CPUPerformanceError("fixture observation denominator changed")
        baseline_wall = _nearest_rank(
            [int(row["wall_duration_ns"]) for row in baseline_rows],
            numerator=95,
            denominator=100,
        )
        native_wall = _nearest_rank(
            [int(row["wall_duration_ns"]) for row in native_rows],
            numerator=95,
            denominator=100,
        )
        baseline_cpu = _nearest_rank(
            [int(row["process_cpu_duration_ns"]) for row in baseline_rows],
            numerator=95,
            denominator=100,
        )
        native_cpu = _nearest_rank(
            [int(row["process_cpu_duration_ns"]) for row in native_rows],
            numerator=95,
            denominator=100,
        )
        fixture = generate_synthetic_geometric_fixture(spec.fixture_id)
        reference = normalize_python_geometric_output(fixture)
        max_ulps = {name: 0 for name in FLOAT_FIELDS}
        parity_blockers: list[str] = []
        for row in native_rows:
            native = _geometric_output_from_document(row["output"])
            comparison = compare_geometric_outputs(reference, native, profile)
            parity_blockers.extend(comparison.blockers)
            for name, distance in comparison.max_ulp_by_field.items():
                max_ulps[name] = max(max_ulps[name], distance)
        parity_passed = not parity_blockers
        if spec.fixture_id == "small":
            speed_passed = native_wall * 20 <= baseline_wall * 21
            speed_blocker = "small_p95_regression_exceeds_5_percent"
        else:
            speed_passed = baseline_wall * 2 >= native_wall * 3
            speed_blocker = f"{spec.fixture_id}_p95_speedup_below_1_5x"
        blockers: list[str] = []
        if not parity_passed:
            blockers.append(f"{spec.fixture_id}_native_parity_failed")
        if not speed_passed:
            blockers.append(speed_blocker)
        all_blockers.extend(f"{spec.fixture_id}:{blocker}" for blocker in blockers)
        all_rows = [row for row in transcript if row["fixture_id"] == spec.fixture_id]
        results.append(
            {
                "fixture_id": spec.fixture_id,
                "exact_pair_count": spec.exact_pair_count,
                "warmup_count_per_role": profile.warmup_count,
                "sample_count_per_role": profile.sample_count,
                "baseline_p95_wall_ns": baseline_wall,
                "native_p95_wall_ns": native_wall,
                "baseline_p95_process_cpu_ns": baseline_cpu,
                "native_p95_process_cpu_ns": native_cpu,
                "parity_passed": parity_passed,
                "maximum_ulp_distance_by_field": max_ulps,
                "speed_gate_passed": speed_passed,
                "baseline_parent_observed_max_vmhwm_kib": max(
                    int(row["parent_observed_max_vmhwm_kib"])
                    for row in all_rows
                    if row["role"] == "python_reference"
                ),
                "native_parent_observed_max_vmhwm_kib": max(
                    int(row["parent_observed_max_vmhwm_kib"])
                    for row in all_rows
                    if row["role"] == "rust_cpu"
                ),
                "memory_evidence_role": "descriptive_only_not_a_gate",
                "blockers": blockers,
            }
        )
    return tuple(results), not all_blockers, tuple(all_blockers)


def _fixture_input_rows(profile: CPUPerformanceProfileV2) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in profile.fixtures:
        fixture = generate_synthetic_geometric_fixture(spec.fixture_id)
        rows.append(
            {
                "fixture_id": spec.fixture_id,
                "input_sha256": fixture.input_sha256,
                "input": fixture.to_dict(),
            }
        )
    return rows


def _artifact_projection(
    *,
    profile: CPUPerformanceProfileV2,
    run_nonce: str,
    host: HostExecutionContextV2,
    bindings: Mapping[str, object],
    transcript: Sequence[Mapping[str, Any]],
    fixture_results: Sequence[Mapping[str, object]],
    status: str,
    recorded_decision: str,
    recorded_numeric_gate_passed: bool | None,
    blockers: Sequence[str],
) -> dict[str, object]:
    return {
        "schema_id": CPU_PERFORMANCE_ARTIFACT_SCHEMA_ID,
        "profile_id": PROFILE_ID,
        "profile_sha256": profile.profile_sha256,
        "status": status,
        "run_nonce": run_nonce,
        "host": host.to_dict(),
        "source_bindings": dict(bindings),
        "fixture_inputs": _fixture_input_rows(profile),
        "measurement_contract": _measurement_contract(profile, transcript),
        "transcript": [dict(row) for row in transcript],
        "fixture_results": [dict(row) for row in fixture_results],
        "recorded_decision": recorded_decision,
        "recorded_numeric_gate_passed": recorded_numeric_gate_passed,
        "blockers": list(blockers),
        "offline_replay_only": True,
        "offline_artifact_gate_eligible": False,
        "live_run_capability_serialized": False,
        "qualification_authority": False,
        "authority": dict(AUTHORITY_FALSE),
        "restrictions": dict(RESTRICTIONS),
    }


def _seal_artifact(projection: Mapping[str, object]) -> dict[str, object]:
    return {**projection, "receipt_sha256": _sha256_json(projection)}


class LiveCPUPerformanceRunResult:
    """Opaque process-local result issued only by the sealed runner registry."""

    __slots__ = (
        "_artifact_bytes",
        "_artifact_sha256",
        "_issued_pid",
        "_issued_start_ticks",
        "__weakref__",
    )

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CPUPerformanceError(
            "live run results cannot be constructed from caller-supplied mappings"
        )

    def __setattr__(self, _name: str, _value: object) -> None:
        raise CPUPerformanceError("live run results are immutable")

    def _document(self) -> dict[str, Any]:
        if not _live_result_is_registered(self):
            raise CPUPerformanceError("live run result is not runner-issued")
        return json.loads(self._artifact_bytes.decode("ascii"))

    @property
    def live_run_capability(self) -> bool:
        return _live_result_is_registered(self)

    @property
    def offline_replay_only(self) -> bool:
        return not self.live_run_capability

    @property
    def local_numeric_gate_eligible(self) -> bool:
        return (
            self.live_run_capability
            and self._document()["status"] == "complete"
            and type(self._document()["recorded_numeric_gate_passed"]) is bool
        )

    @property
    def recorded_numeric_gate_passed(self) -> bool | None:
        value = self._document()["recorded_numeric_gate_passed"]
        return value if type(value) is bool else None

    @property
    def recorded_decision(self) -> str:
        return str(self._document()["recorded_decision"])

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self._document()["blockers"])

    def artifact_document(self) -> dict[str, object]:
        return self._document()


@dataclass(frozen=True, slots=True)
class VerifiedOfflineCPUPerformanceArtifact:
    _document_bytes: bytes = field(repr=False)
    recorded_numeric_gate_passed: bool | None
    recorded_decision: str
    verification_blockers: tuple[str, ...]
    live_run_capability: bool = False
    local_numeric_gate_eligible: bool = False
    offline_replay_only: bool = True
    qualification_authority: bool = False
    structural_integrity_verified: bool = True
    execution_attested: bool = False

    @property
    def document(self) -> dict[str, Any]:
        return json.loads(self._document_bytes.decode("ascii"))


def _verify_fixture_input_rows(rows: object, profile: CPUPerformanceProfileV2) -> None:
    if type(rows) is not list or len(rows) != len(profile.fixtures):
        raise CPUPerformanceError("artifact fixture input denominator changed")
    for row, spec in zip(rows, profile.fixtures, strict=True):
        mapping = _require_exact_mapping_keys(
            row,
            name=f"fixture_inputs.{spec.fixture_id}",
            keys=("fixture_id", "input_sha256", "input"),
        )
        fixture = generate_synthetic_geometric_fixture(spec.fixture_id)
        if mapping["fixture_id"] != spec.fixture_id:
            raise CPUPerformanceError("artifact fixture identity changed")
        if mapping["input"] != fixture.to_dict():
            raise CPUPerformanceError("artifact full binary64 fixture input changed")
        if mapping["input_sha256"] != fixture.input_sha256:
            raise CPUPerformanceError("artifact fixture input SHA changed")


def _verify_measurement_contract(
    value: object,
    *,
    profile: CPUPerformanceProfileV2,
    transcript: Sequence[Mapping[str, Any]],
) -> None:
    expected = _measurement_contract(profile, transcript)
    if value != expected:
        raise CPUPerformanceError("artifact measurement contract changed")


def _verify_source_bindings(value: object, *, complete: bool) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CPUPerformanceError("artifact source bindings must be an object")
    if not complete:
        if value:
            raise CPUPerformanceError("blocked artifact cannot claim source bindings")
        return value
    keys = (
        "schema_id",
        "source_commit",
        "source_tree_clean",
        "python_runtime",
        "performance_source_sha256",
        "geometric_source_sha256",
        "mixed64_source_sha256",
        "rust_source_sha256",
        "cargo_lock_sha256",
        "cargo_manifest_sha256",
        "native_pyproject_sha256",
        "rust_build_script_sha256",
        "native_build_wrapper_sha256",
        "qualification_bootstrap_sha256",
        "native_extension_sha256",
        "native_extension_filename",
        "native_build_info",
        "child_runtime_binding_sha256",
        "child_bootstrap_import_paths",
        "child_bootstrap_import_paths_sha256",
        "fallback_allowed",
    )
    bindings = _require_exact_mapping_keys(value, name="source_bindings", keys=keys)
    if bindings["schema_id"] != (
        "betelgeuze.engine_v2_geometric_kernel_source_bindings/2.0.0"
    ):
        raise CPUPerformanceError("source binding schema changed")
    source_commit = str(bindings["source_commit"])
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise CPUPerformanceError("source commit identity is invalid")
    if bindings["source_tree_clean"] is not True or bindings["fallback_allowed"] is not False:
        raise CPUPerformanceError("source binding execution state is invalid")
    for name in (
        "performance_source_sha256",
        "geometric_source_sha256",
        "mixed64_source_sha256",
        "rust_source_sha256",
        "cargo_lock_sha256",
        "cargo_manifest_sha256",
        "native_pyproject_sha256",
        "rust_build_script_sha256",
        "native_build_wrapper_sha256",
        "qualification_bootstrap_sha256",
        "native_extension_sha256",
        "child_runtime_binding_sha256",
        "child_bootstrap_import_paths_sha256",
    ):
        _require_digest(bindings[name], name=f"source_bindings.{name}")
    python_runtime = _require_exact_mapping_keys(
        bindings["python_runtime"],
        name="source_bindings.python_runtime",
        keys=_QUALIFIED_PYTHON_RUNTIME,
    )
    if dict(python_runtime) != dict(_QUALIFIED_PYTHON_RUNTIME):
        raise CPUPerformanceError("artifact Python runtime is not the qualified lane")
    bootstrap_paths = bindings["child_bootstrap_import_paths"]
    if (
        type(bootstrap_paths) is not list
        or len(bootstrap_paths) != 2
        or any(
            type(path) is not str
            or not Path(path).is_absolute()
            or len(os.fsencode(path)) > 4096
            for path in bootstrap_paths
        )
        or len(set(bootstrap_paths)) != len(bootstrap_paths)
        or bindings["child_bootstrap_import_paths_sha256"]
        != _sha256_json(bootstrap_paths)
    ):
        raise CPUPerformanceError("artifact child bootstrap paths are invalid")
    extension_filename = bindings["native_extension_filename"]
    if (
        type(extension_filename) is not str
        or len(os.fsencode(extension_filename)) > 240
        or Path(extension_filename).name != extension_filename
        or not extension_filename.endswith(".so")
    ):
        raise CPUPerformanceError("artifact native extension filename is invalid")

    root = _repository_root()
    current_sources = {
        "performance_source_sha256": _sha256_owner_controlled_regular_file(
            Path(__file__).resolve(), name="performance source"
        ),
        "geometric_source_sha256": _sha256_owner_controlled_regular_file(
            root / "betelgeuze_engine_v2/docking/geometric_admission_v2.py",
            name="geometric source",
        ),
        "mixed64_source_sha256": _sha256_owner_controlled_regular_file(
            root / "betelgeuze_engine_v2/docking/mixed64_allocation.py",
            name="mixed64 allocation source",
        ),
        "rust_source_sha256": _sha256_owner_controlled_regular_file(
            root / "rust_engine_v2/src/lib.rs", name="Rust geometric source"
        ),
        "cargo_lock_sha256": _sha256_owner_controlled_regular_file(
            root / "rust_engine_v2/Cargo.lock", name="Cargo.lock"
        ),
        "cargo_manifest_sha256": _sha256_owner_controlled_regular_file(
            root / "rust_engine_v2/Cargo.toml", name="Cargo.toml"
        ),
        "native_pyproject_sha256": _sha256_owner_controlled_regular_file(
            root / "rust_engine_v2/pyproject.toml",
            name="native pyproject.toml",
        ),
        "rust_build_script_sha256": _sha256_owner_controlled_regular_file(
            root / "rust_engine_v2/build.rs", name="Rust build script"
        ),
        "native_build_wrapper_sha256": _sha256_owner_controlled_regular_file(
            root / "tools/build_engine_v2_native_wheel.py",
            name="native build wrapper",
        ),
        "qualification_bootstrap_sha256": _sha256_owner_controlled_regular_file(
            root / QUALIFICATION_BOOTSTRAP_RELATIVE_PATH,
            name="qualification bootstrap",
        ),
    }
    for name, expected in current_sources.items():
        if bindings[name] != expected:
            raise CPUPerformanceError(f"artifact source identity drifted: {name}")

    info = _require_native_build_info_document(bindings["native_build_info"])
    if info["cargo_lock_sha256"] != bindings["cargo_lock_sha256"]:
        raise CPUPerformanceError("artifact native Cargo lock binding changed")
    if info["cargo_manifest_sha256"] != bindings["cargo_manifest_sha256"]:
        raise CPUPerformanceError("artifact native Cargo manifest binding changed")
    if info["native_pyproject_sha256"] != bindings["native_pyproject_sha256"]:
        raise CPUPerformanceError("artifact native pyproject binding changed")
    if info["rust_lib_sha256"] != bindings["rust_source_sha256"]:
        raise CPUPerformanceError("artifact native Rust source binding changed")
    if info["build_script_sha256"] != bindings["rust_build_script_sha256"]:
        raise CPUPerformanceError("artifact native build script binding changed")
    if info["native_build_wrapper_sha256"] != bindings[
        "native_build_wrapper_sha256"
    ]:
        raise CPUPerformanceError("artifact native build wrapper binding changed")
    runtime_projection = {
        "performance_source_sha256": bindings["performance_source_sha256"],
        "geometric_source_sha256": bindings["geometric_source_sha256"],
        "mixed64_source_sha256": bindings["mixed64_source_sha256"],
        "native_extension_sha256": bindings["native_extension_sha256"],
        "native_build_info": info,
        "qualification_bootstrap_sha256": bindings[
            "qualification_bootstrap_sha256"
        ],
        "python_runtime": dict(python_runtime),
    }
    if bindings["child_runtime_binding_sha256"] != _sha256_json(
        runtime_projection
    ):
        raise CPUPerformanceError("artifact child runtime binding does not rederive")
    try:
        _git_output(("git", "cat-file", "-e", f"{source_commit}^{{commit}}"))
    except CPUPerformanceError as exc:
        raise CPUPerformanceError("artifact source commit is unavailable") from exc

    try:
        module = _load_native_module()
    except CPUPerformanceError:
        module = None
    if module is not None:
        current_info = _validated_native_build_info(module)
        module_path = _native_extension_path(module)
        if current_info != info:
            raise CPUPerformanceError("installed native build info changed")
        if module_path.name != extension_filename or _sha256_regular_file(
            module_path, name="native extension"
        ) != bindings["native_extension_sha256"]:
            raise CPUPerformanceError("installed native extension identity changed")
    return bindings


def _verify_fixture_results(
    value: object,
    *,
    transcript: Sequence[Mapping[str, Any]],
    profile: CPUPerformanceProfileV2,
) -> tuple[bool, tuple[str, ...]]:
    if type(value) is not list:
        raise CPUPerformanceError("fixture results must be a list")
    derived, passed, blockers = _derive_fixture_results(transcript, profile)
    if value != list(derived):
        raise CPUPerformanceError("fixture performance results do not rederive")
    return passed, blockers


def _verify_host_projection(value: object, *, complete: bool) -> Mapping[str, Any]:
    host = _require_exact_mapping_keys(
        value,
        name="artifact host",
        keys=(
            "cpu_model",
            "boost_disabled",
            "available_cpu_affinity",
            "platform_system",
            "platform_machine",
            "byteorder",
            "parent_pid",
            "parent_os_task_count",
            "qualified",
            "blockers",
        ),
    )
    if type(host["cpu_model"]) is not str or len(host["cpu_model"]) > 256:
        raise CPUPerformanceError("artifact CPU model is invalid")
    boost_disabled = _require_exact_bool(
        host["boost_disabled"], name="host.boost_disabled"
    )
    affinity = host["available_cpu_affinity"]
    if (
        type(affinity) is not list
        or any(type(cpu) is not int or not 0 <= cpu <= 1_048_575 for cpu in affinity)
        or affinity != sorted(set(affinity))
    ):
        raise CPUPerformanceError("artifact available CPU affinity is invalid")
    for name in ("platform_system", "platform_machine", "byteorder"):
        if type(host[name]) is not str or not host[name] or len(host[name]) > 64:
            raise CPUPerformanceError(f"artifact host {name} is invalid")
    _require_exact_int(host["parent_pid"], name="host.parent_pid", minimum=1)
    _require_exact_int(
        host["parent_os_task_count"],
        name="host.parent_os_task_count",
        minimum=1,
        maximum=1024,
    )
    blockers = host["blockers"]
    if (
        type(blockers) is not list
        or any(type(blocker) is not str or not blocker for blocker in blockers)
        or len(set(blockers)) != len(blockers)
    ):
        raise CPUPerformanceError("artifact host blockers are invalid")
    qualified = _require_exact_bool(host["qualified"], name="host.qualified")
    if qualified != (not blockers):
        raise CPUPerformanceError("artifact host qualification does not rederive")
    if complete and (
        host["cpu_model"] != CPU_MODEL_EXACT
        or not boost_disabled
        or not set(AUTHORITATIVE_CPU_AFFINITY).issubset(affinity)
        or host["platform_system"] != "Linux"
        or host["platform_machine"] != "x86_64"
        or host["byteorder"] != "little"
        or host["parent_os_task_count"] != 1
        or not qualified
        or blockers
    ):
        raise CPUPerformanceError("complete artifact host is not qualified")
    return host


_ARTIFACT_KEYS: Final = frozenset(
    {
        "schema_id",
        "profile_id",
        "profile_sha256",
        "status",
        "run_nonce",
        "host",
        "source_bindings",
        "fixture_inputs",
        "measurement_contract",
        "transcript",
        "fixture_results",
        "recorded_decision",
        "recorded_numeric_gate_passed",
        "blockers",
        "offline_replay_only",
        "offline_artifact_gate_eligible",
        "live_run_capability_serialized",
        "qualification_authority",
        "authority",
        "restrictions",
        "receipt_sha256",
    }
)


def require_cpu_performance_artifact_document(
    document: Mapping[str, Any],
    *,
    profile: CPUPerformanceProfileV2,
) -> VerifiedOfflineCPUPerformanceArtifact:
    """Verify replay integrity; never inspect the host or mint a live proof."""

    profile._assert_unchanged()
    artifact = _require_exact_mapping_keys(
        document, name="CPU performance artifact", keys=_ARTIFACT_KEYS
    )
    if artifact["schema_id"] != CPU_PERFORMANCE_ARTIFACT_SCHEMA_ID:
        raise CPUPerformanceError("CPU performance artifact schema is unsupported")
    if artifact["profile_id"] != PROFILE_ID or artifact["profile_sha256"] != (
        profile.profile_sha256
    ):
        raise CPUPerformanceError("CPU performance artifact profile cross-wired")
    run_nonce = _require_digest(artifact["run_nonce"], name="run_nonce")
    if dict(artifact["authority"]) != dict(AUTHORITY_FALSE):
        raise CPUPerformanceError("artifact authority must remain false")
    if dict(artifact["restrictions"]) != dict(RESTRICTIONS):
        raise CPUPerformanceError("artifact restrictions changed")
    if (
        artifact["offline_replay_only"] is not True
        or artifact["offline_artifact_gate_eligible"] is not False
        or artifact["live_run_capability_serialized"] is not False
        or artifact["qualification_authority"] is not False
    ):
        raise CPUPerformanceError("serialized artifacts cannot claim live authority")
    receipt = _require_digest(artifact["receipt_sha256"], name="receipt_sha256")
    projection = {key: value for key, value in artifact.items() if key != "receipt_sha256"}
    if _sha256_json(projection) != receipt:
        raise CPUPerformanceError("CPU performance artifact receipt changed")
    _verify_fixture_input_rows(artifact["fixture_inputs"], profile)
    status = artifact["status"]
    if status not in ("complete", "blocked_preflight"):
        raise CPUPerformanceError("artifact status is invalid")
    complete = status == "complete"
    host = _verify_host_projection(artifact["host"], complete=complete)
    parent_pid = int(host["parent_pid"])
    source_bindings = _verify_source_bindings(
        artifact["source_bindings"], complete=complete
    )
    transcript_value = artifact["transcript"]
    if complete:
        transcript = _validate_transcript_rows(
            transcript_value,
            profile=profile,
            run_nonce=run_nonce,
            parent_pid=parent_pid,
            source_bindings=source_bindings,
        )
        numeric_passed, derived_blockers = _verify_fixture_results(
            artifact["fixture_results"], transcript=transcript, profile=profile
        )
        recorded_numeric = _require_exact_bool(
            artifact["recorded_numeric_gate_passed"],
            name="recorded_numeric_gate_passed",
        )
        if recorded_numeric != numeric_passed:
            raise CPUPerformanceError("recorded numerical gate does not rederive")
        expected_decision = "GO" if numeric_passed else "NO_GO"
        if artifact["recorded_decision"] != expected_decision:
            raise CPUPerformanceError("recorded performance decision does not rederive")
        if artifact["blockers"] != list(derived_blockers):
            raise CPUPerformanceError("recorded performance blockers do not rederive")
    else:
        if artifact["transcript"] != [] or artifact["fixture_results"] != []:
            raise CPUPerformanceError("blocked artifact cannot contain measurement rows")
        transcript = ()
        if artifact["recorded_numeric_gate_passed"] is not None:
            raise CPUPerformanceError("blocked artifact cannot claim a numerical gate")
        if artifact["recorded_decision"] != "BLOCKED":
            raise CPUPerformanceError("blocked artifact decision changed")
        blockers_value = artifact["blockers"]
        if (
            type(blockers_value) is not list
            or not blockers_value
            or any(type(value) is not str or not value for value in blockers_value)
        ):
            raise CPUPerformanceError("blocked artifact requires explicit blockers")
        recorded_numeric = None
    _verify_measurement_contract(
        artifact["measurement_contract"], profile=profile, transcript=transcript
    )
    offline_blockers = ("offline_artifact_cannot_attest_execution",)
    return VerifiedOfflineCPUPerformanceArtifact(
        _document_bytes=_canonical_json_bytes(dict(artifact)),
        recorded_numeric_gate_passed=recorded_numeric,
        recorded_decision=str(artifact["recorded_decision"]),
        verification_blockers=offline_blockers,
    )


def require_cpu_performance_artifact_bytes(
    raw: bytes,
    *,
    profile: CPUPerformanceProfileV2,
) -> VerifiedOfflineCPUPerformanceArtifact:
    document = require_canonical_json_object_bytes(
        raw,
        name="CPU performance artifact",
        maximum_bytes=MAX_ARTIFACT_BYTES,
        trailing_newline_required=True,
    )
    return require_cpu_performance_artifact_document(document, profile=profile)


def load_cpu_performance_artifact(
    path: Path,
    *,
    profile: CPUPerformanceProfileV2,
) -> VerifiedOfflineCPUPerformanceArtifact:
    raw = _read_bounded_regular_file(
        Path(path),
        name="CPU performance artifact",
        maximum_bytes=MAX_ARTIFACT_BYTES,
        require_single_link=True,
        require_owner_only=True,
        require_stable_size=True,
    )
    return require_cpu_performance_artifact_bytes(raw, profile=profile)


def _build_live_result_registry() -> tuple[Any, Any]:
    issued: weakref.WeakKeyDictionary[
        LiveCPUPerformanceRunResult, tuple[str, int, int]
    ] = weakref.WeakKeyDictionary()

    def issue(
        projection: Mapping[str, object],
        *,
        profile: CPUPerformanceProfileV2,
    ) -> LiveCPUPerformanceRunResult:
        artifact = _seal_artifact(
            {key: value for key, value in projection.items() if key != "receipt_sha256"}
        )
        # Full structural validation happens before registry issuance.  The
        # registry is process/start-time bound and is never serialized.
        require_cpu_performance_artifact_document(artifact, profile=profile)
        artifact_bytes = _canonical_json_bytes(artifact)
        artifact_sha = _sha256_bytes(artifact_bytes)
        result = object.__new__(LiveCPUPerformanceRunResult)
        object.__setattr__(result, "_artifact_bytes", artifact_bytes)
        object.__setattr__(result, "_artifact_sha256", artifact_sha)
        object.__setattr__(result, "_issued_pid", os.getpid())
        object.__setattr__(result, "_issued_start_ticks", _process_start_ticks(os.getpid()))
        issued[result] = (artifact_sha, os.getpid(), _process_start_ticks(os.getpid()))
        return result

    def is_registered(result: object) -> bool:
        if not isinstance(result, LiveCPUPerformanceRunResult):
            return False
        try:
            expected = issued.get(result)
            if expected is None:
                return False
            artifact_sha, pid, start_ticks = expected
            return bool(
                result._artifact_sha256 == artifact_sha
                and _sha256_bytes(result._artifact_bytes) == artifact_sha
                and result._issued_pid == pid == os.getpid()
                and result._issued_start_ticks == start_ticks
                and _process_start_ticks(os.getpid()) == start_ticks
            )
        except (AttributeError, CPUPerformanceError, TypeError):
            return False

    return issue, is_registered


_issue_live_result, _live_result_is_registered = _build_live_result_registry()


def _blocked_live_result(
    *,
    profile: CPUPerformanceProfileV2,
    run_nonce: str,
    host: HostExecutionContextV2,
    blockers: Sequence[str],
) -> LiveCPUPerformanceRunResult:
    projection = _artifact_projection(
        profile=profile,
        run_nonce=run_nonce,
        host=host,
        bindings={},
        transcript=(),
        fixture_results=(),
        status="blocked_preflight",
        recorded_decision="BLOCKED",
        recorded_numeric_gate_passed=None,
        blockers=tuple(blockers),
    )
    return _issue_live_result(projection, profile=profile)


def _unevaluated_timeout_host() -> HostExecutionContextV2:
    """Create a truthful failure projection without starting host qualification."""

    return HostExecutionContextV2(
        cpu_model="",
        boost_disabled=False,
        available_cpu_affinity=(),
        platform_system=platform.system() or "unknown",
        platform_machine=platform.machine() or "unknown",
        byteorder=sys.byteorder,
        parent_pid=os.getpid(),
        parent_os_task_count=max(1, _os_task_count(os.getpid())),
        qualified=False,
        blockers=("host_not_evaluated_due_total_timeout",),
    )


def run_sealed_local_performance_runner() -> LiveCPUPerformanceRunResult:
    """Run the frozen synthetic local qualification, or return a typed blocker.

    The function accepts no path, payload, molecular object, callable, timer,
    output digest, RSS observation, host DTO, or authority override.
    """

    started = time.monotonic()
    profile_path = _repository_root() / CANONICAL_PROFILE_RELATIVE_PATH
    profile = load_cpu_performance_profile(profile_path)
    deadline = started + profile.total_timeout_seconds
    run_nonce = secrets.token_hex(32)
    if time.monotonic() >= deadline:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=_unevaluated_timeout_host(),
            blockers=("sealed_runner_total_timeout",),
        )
    host = derive_actual_host_execution_context()
    blockers = list(host.blockers)
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if blockers:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=tuple(dict.fromkeys(blockers)),
        )
    bindings: Mapping[str, object] = {}
    try:
        bindings = _derive_source_bindings()
    except CPUPerformanceError as exc:
        blockers.append(str(exc))
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if blockers:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    transcript: list[Mapping[str, Any]] = []
    launch_schedule = _expected_launch_schedule(profile)
    if time.monotonic() >= deadline:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=("sealed_runner_total_timeout",),
        )
    for expected in launch_schedule:
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            blockers.append("sealed_runner_total_timeout")
            break
        try:
            row = _launch_sealed_child(
                run_nonce=run_nonce,
                global_launch_ordinal=int(expected["global_launch_ordinal"]),
                fixture_id=str(expected["fixture_id"]),
                phase=str(expected["phase"]),
                pair_index=int(expected["pair_index"]),
                role=str(expected["role"]),
                timeout_seconds=min(
                    float(profile.child_timeout_seconds), remaining_seconds
                ),
                absolute_deadline_monotonic=deadline,
            )
        except CPUPerformanceError as exc:
            blockers.append(
                f"observation_{expected['global_launch_ordinal']}_failed:{exc}"
            )
            break
        if time.monotonic() >= deadline:
            blockers.append("sealed_runner_total_timeout")
            break
        transcript.append(row)
    if blockers or len(transcript) != len(launch_schedule):
        blockers.append("sealed_measurement_incomplete")
        # A partial run is deliberately not serializable as performance data.
        # Only the preflight blocker list is retained; no partial denominator
        # can be mistaken for a qualification attempt.
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if not blockers:
        try:
            final_bindings = _derive_source_bindings()
        except CPUPerformanceError as exc:
            blockers.append(f"source_binding_postflight_failed:{exc}")
        else:
            if dict(final_bindings) != dict(bindings):
                blockers.append("source_binding_changed_during_measurement")
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if not blockers:
        final_host = derive_actual_host_execution_context()
        if final_host != host:
            blockers.append("host_context_changed_during_measurement")
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if blockers:
        if "sealed_runner_total_timeout" in blockers:
            discard_reason = "sealed_measurement_discarded_after_total_timeout"
        elif "host_context_changed_during_measurement" in blockers:
            discard_reason = "sealed_measurement_discarded_after_host_drift"
        else:
            discard_reason = "sealed_measurement_discarded_after_source_drift"
        blockers.append(discard_reason)
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    if time.monotonic() >= deadline:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=(
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            ),
        )
    try:
        validated = _validate_transcript_rows(
            [dict(row) for row in transcript],
            profile=profile,
            run_nonce=run_nonce,
            parent_pid=host.parent_pid,
            source_bindings=bindings,
        )
        if time.monotonic() >= deadline:
            raise CPUPerformanceError("sealed_runner_total_timeout")
        fixture_results, numeric_passed, numeric_blockers = _derive_fixture_results(
            validated, profile
        )
    except CPUPerformanceError as exc:
        # Parity is a semantic prerequisite, not a tunable numerical outcome.
        # Invalid/incomplete observations therefore cannot become NO_GO rows.
        validation_blockers = (
            (
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            )
            if str(exc) == "sealed_runner_total_timeout"
            else (
                f"sealed_transcript_validation_failed:{exc}",
                "sealed_measurement_discarded_after_validation_failure",
            )
        )
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=validation_blockers,
        )
    if time.monotonic() >= deadline:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=(
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            ),
        )
    projection = _artifact_projection(
        profile=profile,
        run_nonce=run_nonce,
        host=host,
        bindings=bindings,
        transcript=validated,
        fixture_results=fixture_results,
        status="complete",
        recorded_decision="GO" if numeric_passed else "NO_GO",
        recorded_numeric_gate_passed=numeric_passed,
        blockers=numeric_blockers,
    )
    if time.monotonic() >= deadline:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=(
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            ),
        )
    result = _issue_live_result(projection, profile=profile)
    if time.monotonic() >= deadline:
        return _blocked_live_result(
            profile=profile,
            run_nonce=run_nonce,
            host=host,
            blockers=(
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            ),
        )
    return result


def _reject_symlink_parent(path: Path) -> tuple[Path, os.stat_result]:
    parent = path.parent if str(path.parent) else Path(".")
    try:
        absolute = parent.absolute()
        resolved = parent.resolve(strict=True)
    except OSError as exc:
        raise CPUPerformanceError("artifact parent directory is unavailable") from exc
    if absolute != resolved:
        raise CPUPerformanceError("artifact parent path cannot contain symlinks")
    try:
        metadata = os.stat(resolved, follow_symlinks=False)
    except OSError as exc:
        raise CPUPerformanceError("artifact parent directory is unavailable") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise CPUPerformanceError("artifact parent must be a directory")
    if metadata.st_uid != os.geteuid() or metadata.st_mode & (
        stat.S_IWGRP | stat.S_IWOTH
    ):
        raise CPUPerformanceError(
            "artifact parent must be owner-controlled and non-writable by others"
        )
    current = Path(resolved.anchor)
    for component in resolved.parts[1:]:
        current /= component
        try:
            component_stat = os.stat(current, follow_symlinks=False)
        except OSError as exc:
            raise CPUPerformanceError(
                "artifact parent component is unavailable"
            ) from exc
        if not stat.S_ISDIR(component_stat.st_mode):
            raise CPUPerformanceError("artifact parent component is not a directory")
        writable_by_others = component_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        if writable_by_others and not component_stat.st_mode & stat.S_ISVTX:
            raise CPUPerformanceError(
                "artifact parent chain contains an untrusted writable directory"
            )
    return resolved, metadata


def _require_same_trusted_parent(
    parent: Path, directory_fd: int, initial: os.stat_result
) -> None:
    try:
        descriptor_stat = os.fstat(directory_fd)
        path_stat = os.stat(parent, follow_symlinks=False)
    except OSError as exc:
        raise CPUPerformanceError("artifact parent identity is unavailable") from exc
    identity = (initial.st_dev, initial.st_ino)
    if (
        (descriptor_stat.st_dev, descriptor_stat.st_ino) != identity
        or (path_stat.st_dev, path_stat.st_ino) != identity
        or not stat.S_ISDIR(descriptor_stat.st_mode)
        or descriptor_stat.st_uid != os.geteuid()
        or descriptor_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise CPUPerformanceError("artifact parent identity changed")


def write_cpu_performance_artifact(
    result: LiveCPUPerformanceRunResult,
    path: Path,
) -> Path:
    """Publish one owner-only, absent-only canonical replay artifact."""

    if not isinstance(result, LiveCPUPerformanceRunResult) or not (
        result.live_run_capability
    ):
        raise CPUPerformanceError("only a current live result can be persisted")
    target = Path(path)
    if (
        not target.name
        or target.name in (".", "..")
        or target.suffix != ".json"
        or len(os.fsencode(target.name)) > 240
    ):
        raise CPUPerformanceError("artifact output filename is invalid")
    parent, validated_parent_stat = _reject_symlink_parent(target)
    profile = load_cpu_performance_profile(
        _repository_root() / CANONICAL_PROFILE_RELATIVE_PATH
    )
    document = result.artifact_document()
    require_cpu_performance_artifact_document(document, profile=profile)
    raw = _canonical_json_bytes(document) + b"\n"
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise CPUPerformanceError("artifact exceeds the byte limit")
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(parent, directory_flags)
    except OSError as exc:
        raise CPUPerformanceError("artifact parent cannot be opened safely") from exc
    temporary_name = f".{target.name}.tmp.{secrets.token_hex(16)}"
    target_name = target.name
    temporary_created = False
    target_published = False
    descriptor: int | None = None
    staging_identity: tuple[int, int] | None = None
    try:
        parent_stat = os.fstat(directory_fd)
        if (parent_stat.st_dev, parent_stat.st_ino) != (
            validated_parent_stat.st_dev,
            validated_parent_stat.st_ino,
        ):
            raise CPUPerformanceError("artifact parent changed before descriptor binding")
        _require_same_trusted_parent(parent, directory_fd, validated_parent_stat)
        try:
            os.stat(target_name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise CPUPerformanceError("artifact output already exists")
        file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(
                temporary_name,
                file_flags,
                0o600,
                dir_fd=directory_fd,
            )
        except OSError as exc:
            raise CPUPerformanceError("artifact staging file cannot be created") from exc
        temporary_created = True
        os.fchmod(descriptor, 0o600)
        initial_staging = os.fstat(descriptor)
        staging_identity = (initial_staging.st_dev, initial_staging.st_ino)
        if (
            not stat.S_ISREG(initial_staging.st_mode)
            or stat.S_IMODE(initial_staging.st_mode) != 0o600
            or initial_staging.st_nlink != 1
            or initial_staging.st_size != 0
        ):
            raise CPUPerformanceError("artifact staging identity is invalid")
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise CPUPerformanceError("artifact write made no progress")
            offset += written
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size != len(raw)
            or (metadata.st_dev, metadata.st_ino) != staging_identity
        ):
            raise CPUPerformanceError("artifact staging identity is invalid")
        _require_same_trusted_parent(parent, directory_fd, validated_parent_stat)
        try:
            os.link(
                temporary_name,
                target_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except (FileExistsError, OSError) as exc:
            try:
                ambiguous_target = os.stat(
                    target_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except OSError:
                pass
            else:
                if (ambiguous_target.st_dev, ambiguous_target.st_ino) == staging_identity:
                    try:
                        os.unlink(target_name, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    except OSError:
                        pass
            if isinstance(exc, FileExistsError):
                raise CPUPerformanceError(
                    "artifact output was created concurrently"
                ) from exc
            raise CPUPerformanceError("artifact cannot be published atomically") from exc
        target_published = True
        linked = os.stat(target_name, dir_fd=directory_fd, follow_symlinks=False)
        staged_after_link = os.fstat(descriptor)
        if (
            (linked.st_dev, linked.st_ino) != staging_identity
            or (staged_after_link.st_dev, staged_after_link.st_ino) != staging_identity
            or linked.st_nlink != 2
            or staged_after_link.st_nlink != 2
        ):
            raise CPUPerformanceError("published artifact link identity is invalid")
        os.unlink(temporary_name, dir_fd=directory_fd)
        temporary_created = False
        if os.fstat(descriptor).st_nlink != 1:
            raise CPUPerformanceError("published artifact link count is invalid")
        os.fsync(directory_fd)
        verification_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        verification_fd = os.open(target_name, verification_flags, dir_fd=directory_fd)
        try:
            metadata = os.fstat(verification_fd)
            observed = b""
            while len(observed) <= len(raw):
                chunk = os.read(verification_fd, min(1 << 20, len(raw) + 1 - len(observed)))
                if not chunk:
                    break
                observed += chunk
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_nlink != 1
                or (metadata.st_dev, metadata.st_ino) != staging_identity
                or observed != raw
            ):
                raise CPUPerformanceError("published artifact identity is invalid")
        finally:
            os.close(verification_fd)
        _require_same_trusted_parent(parent, directory_fd, validated_parent_stat)
    except Exception:
        if target_published and staging_identity is not None:
            try:
                target_stat = os.stat(
                    target_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except OSError:
                pass
            else:
                if (target_stat.st_dev, target_stat.st_ino) == staging_identity:
                    try:
                        os.unlink(target_name, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    except OSError:
                        pass
        raise
    finally:
        if temporary_created:
            try:
                temporary_stat = os.stat(
                    temporary_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except OSError:
                pass
            else:
                if staging_identity is None or (
                    temporary_stat.st_dev,
                    temporary_stat.st_ino,
                ) == staging_identity:
                    try:
                        os.unlink(temporary_name, dir_fd=directory_fd)
                    except OSError:
                        pass
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)
    return parent / target_name


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify or run the synthetic geometric CPU qualification"
    )
    parser.add_argument("--sealed-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-nonce", help=argparse.SUPPRESS)
    parser.add_argument("--global-launch-ordinal", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--fixture-id", choices=tuple(_FROZEN_FIXTURE_BY_ID), help=argparse.SUPPRESS)
    parser.add_argument("--phase", choices=("warmup", "sample"), help=argparse.SUPPRESS)
    parser.add_argument("--pair-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--role", choices=("python_reference", "rust_cpu"), help=argparse.SUPPRESS)
    parser.add_argument("--verify-profile", action="store_true")
    parser.add_argument("--verify-artifact", type=Path)
    parser.add_argument("--run-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _argument_parser().parse_args(argv)
    if arguments.sealed_child:
        required = (
            arguments.run_nonce,
            arguments.global_launch_ordinal,
            arguments.fixture_id,
            arguments.phase,
            arguments.pair_index,
            arguments.role,
        )
        if any(value is None for value in required):
            return 2
        return _child_main(arguments)
    selected = sum(
        (
            bool(arguments.verify_profile),
            arguments.verify_artifact is not None,
            arguments.run_output is not None,
        )
    )
    if selected != 1:
        raise CPUPerformanceError("select exactly one public operation")
    profile = load_cpu_performance_profile(
        _repository_root() / CANONICAL_PROFILE_RELATIVE_PATH
    )
    if arguments.verify_profile:
        output = {
            "profile_id": PROFILE_ID,
            "profile_sha256": profile.profile_sha256,
            "authority": dict(AUTHORITY_FALSE),
            "structural_integrity_verified": True,
            "execution_attested": False,
            "verification_blockers": [
                "profile_contract_only_cannot_attest_execution"
            ],
        }
    elif arguments.verify_artifact is not None:
        verified = load_cpu_performance_artifact(
            arguments.verify_artifact, profile=profile
        )
        output = {
            "structural_integrity_verified": True,
            "execution_attested": False,
            "recorded_decision": verified.recorded_decision,
            "recorded_numeric_gate_passed": verified.recorded_numeric_gate_passed,
            "live_run_capability": verified.live_run_capability,
            "local_numeric_gate_eligible": verified.local_numeric_gate_eligible,
            "offline_replay_only": verified.offline_replay_only,
            "qualification_authority": verified.qualification_authority,
            "verification_blockers": list(verified.verification_blockers),
            "authority": dict(AUTHORITY_FALSE),
        }
    else:
        result = run_sealed_local_performance_runner()
        published = write_cpu_performance_artifact(result, arguments.run_output)
        output = {
            "artifact": str(published),
            "execution_attested": False,
            "recorded_decision": result.recorded_decision,
            "recorded_numeric_gate_passed": result.recorded_numeric_gate_passed,
            "live_run_capability": result.live_run_capability,
            "local_numeric_gate_eligible": result.local_numeric_gate_eligible,
            "offline_replay_only": result.offline_replay_only,
            "blockers": list(result.blockers),
            "authority": dict(AUTHORITY_FALSE),
        }
    sys.stdout.buffer.write(_canonical_json_bytes(output) + b"\n")
    return 0


__all__ = [
    "AUTHORITY_FALSE",
    "CANONICAL_PROFILE_RELATIVE_PATH",
    "CPUPerformanceError",
    "CPUPerformanceProfileV2",
    "CPU_PERFORMANCE_ARTIFACT_SCHEMA_ID",
    "CPU_PERFORMANCE_PROFILE_SCHEMA_ID",
    "EXACT_INTEGER_FIELDS",
    "FLOAT_FIELDS",
    "FROZEN_SYNTHETIC_FIXTURES",
    "GeometricKernelOutputV2",
    "GeometricParityComparisonV2",
    "HostExecutionContextV2",
    "LiveCPUPerformanceRunResult",
    "MAX_ARTIFACT_BYTES",
    "PROFILE_ID",
    "RESTRICTIONS",
    "SyntheticGeometricFixtureV2",
    "VerifiedOfflineCPUPerformanceArtifact",
    "compare_geometric_outputs",
    "derive_actual_host_execution_context",
    "generate_synthetic_geometric_fixture",
    "load_cpu_performance_artifact",
    "load_cpu_performance_profile",
    "normalize_native_geometric_output",
    "normalize_python_geometric_output",
    "require_canonical_json_object_bytes",
    "require_cpu_performance_artifact_bytes",
    "require_cpu_performance_artifact_document",
    "run_sealed_local_performance_runner",
    "verify_cpu_performance_profile_document",
    "write_cpu_performance_artifact",
]


if __name__ == "__main__":
    raise SystemExit(main())
