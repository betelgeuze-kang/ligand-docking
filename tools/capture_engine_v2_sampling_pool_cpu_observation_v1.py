#!/usr/bin/env python3
"""Capture or verify one source-bound synthetic sampling-pool CPU observation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import stat
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


class SamplingPoolCPUObservationEvidenceError(RuntimeError):
    """Raised when capture or verification fails closed."""


RUNNER_SOURCE_PATH = (
    REPOSITORY_ROOT / "tools/run_engine_v2_sampling_pool_cpu_observation_v1.py"
)
EXPECTED_RUNNER_SOURCE_SHA256 = (
    "051d7f6fc4ecc84c16a72c196abb23f8e619e5d245924310c7373147f8416479"
)


def _load_observer() -> ModuleType:
    try:
        source_sha256 = hashlib.sha256(RUNNER_SOURCE_PATH.read_bytes()).hexdigest()
    except OSError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "pinned observation runner is unreadable"
        ) from exc
    if source_sha256 != EXPECTED_RUNNER_SOURCE_SHA256:
        raise SamplingPoolCPUObservationEvidenceError(
            "imported observation runner differs from the pinned source"
        )
    module = importlib.import_module(
        "tools.run_engine_v2_sampling_pool_cpu_observation_v1"
    )
    if Path(module.__file__).resolve() != RUNNER_SOURCE_PATH:
        raise SamplingPoolCPUObservationEvidenceError(
            "imported observation runner differs from the pinned source"
        )
    return module


observer: ModuleType | None = None
if __name__ != "__main__":
    observer = _load_observer()


SOURCE_BASELINE_COMMIT = "cb987662477e6fc56409f382ac5757ce62a09228"
SOURCE_BASELINE_TREE = "ed4221a64d7740e4063bdaff777e150f7035c769"
SOURCE_CLOSURE_PATHS = (
    "LICENSE",
    "rust",
    "tools/run_engine_v2_sampling_pool_cpu_observation_v1.py",
    "tools/rust/betelgeuze_sampling_pool_observe_v1.rs",
)
SCHEMA_ID = "betelgeuze.engine_v2_sampling_pool_cpu_observation_evidence/1.0.0"
PROFILE_ID = "engine_v2_sampling_pool_synthetic_cpu_observation_evidence_v1"
STATUS = "local_synthetic_development_observation_only"
SAMPLE_COUNT = 7
RECEIPT_DOMAIN = b"betelgeuze.engine_v2_sampling_pool_cpu_observation_evidence/1\0"
MAXIMUM_EVIDENCE_BYTES = 128 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_OID = re.compile(r"[0-9a-f]{40}")
_MAXIMUM_JSON_INTEGER_DIGITS = 128
_BUILD_ENVIRONMENT_KEYS = (
    "CARGO_BUILD_JOBS",
    "CARGO_BUILD_RUSTC",
    "CARGO_BUILD_RUSTC_WRAPPER",
    "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
    "CARGO_BUILD_TARGET",
    "CARGO_ENCODED_RUSTFLAGS",
    "CARGO_HOME",
    "CARGO_INCREMENTAL",
    "CARGO_PROFILE_RELEASE_CODEGEN_UNITS",
    "CARGO_PROFILE_RELEASE_DEBUG",
    "CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS",
    "CARGO_PROFILE_RELEASE_INCREMENTAL",
    "CARGO_PROFILE_RELEASE_LTO",
    "CARGO_PROFILE_RELEASE_OPT_LEVEL",
    "CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS",
    "CARGO_PROFILE_RELEASE_PANIC",
    "CARGO_PROFILE_RELEASE_RPATH",
    "CARGO_PROFILE_RELEASE_STRIP",
    "CARGO_TARGET_DIR",
    "RUSTC",
    "RUSTC_WRAPPER",
    "RUSTC_WORKSPACE_WRAPPER",
    "RUSTDOC",
    "RUSTDOCFLAGS",
    "RUSTFLAGS",
)
_CARGO_CONFIGURATION_FILENAMES = ("config.toml", "config")
_TIMED_RUNTIME_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "RAYON_NUM_THREADS": "1",
    "TZ": "UTC",
}
_SOURCE_GIT_ENVIRONMENT = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": os.defpath,
}
_OBSERVATION_KEYS = {
    "authority",
    "cpu_model",
    "fixtures",
    "memory_role",
    "profile_id",
    "sample_count",
    "schema_id",
    "status",
    "timed_boundary",
    "wall_time_role",
}
_OBSERVED_FIXTURE_KEYS = {
    "exact_pair_evaluation_count",
    "fixture_id",
    "ligand_atom_count",
    "peak_rss_delta_kib",
    "peak_rss_kib",
    "receptor_atom_count",
    "receipt_sha256",
    "wall_time_ns_p50",
    "wall_time_ns_p95",
    "wall_time_ns_samples",
}
_OBSERVED_FIXTURE_INTEGER_KEYS = {
    "exact_pair_evaluation_count",
    "ligand_atom_count",
    "peak_rss_delta_kib",
    "peak_rss_kib",
    "receptor_atom_count",
    "wall_time_ns_p50",
    "wall_time_ns_p95",
}


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _canonical_projection(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise SamplingPoolCPUObservationEvidenceError(
            "non-finite JSON number is forbidden"
        )
    return value


def _parse_bounded_int(token: str) -> int:
    digits = token.removeprefix("-")
    if len(digits) > _MAXIMUM_JSON_INTEGER_DIGITS:
        raise SamplingPoolCPUObservationEvidenceError(
            "JSON integer exceeds the evidence digit limit"
        )
    return int(token)


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _verify_imported_observer_binding() -> None:
    if (
        observer is None
        or observer.__file__ is None
        or Path(observer.__file__).resolve() != RUNNER_SOURCE_PATH
        or _file_sha256(RUNNER_SOURCE_PATH) != EXPECTED_RUNNER_SOURCE_SHA256
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "imported observation runner differs from the pinned source"
        )


def _receipt_sha256(projection: Mapping[str, object]) -> str:
    return _sha256(RECEIPT_DOMAIN + _canonical_projection(projection))


def _git_bytes(*arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            (
                "git",
                "-C",
                str(REPOSITORY_ROOT),
                f"--work-tree={REPOSITORY_ROOT}",
                *arguments,
            ),
            cwd=REPOSITORY_ROOT,
            env=dict(_SOURCE_GIT_ENVIRONMENT),
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            f"git source binding failed: {' '.join(arguments)}"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr.strip() or completed.stdout.strip()).decode(
            "utf-8", errors="replace"
        )
        raise SamplingPoolCPUObservationEvidenceError(
            f"git source binding failed: {' '.join(arguments)}: {detail[:4096]}"
        )
    return completed.stdout


def _git(*arguments: str) -> str:
    try:
        return _git_bytes(*arguments).decode("utf-8").strip()
    except UnicodeError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            f"git source binding output is not UTF-8: {' '.join(arguments)}"
        ) from exc


def _git_blob_oid(raw: bytes, object_format: str) -> str:
    if object_format not in {"sha1", "sha256"}:
        raise SamplingPoolCPUObservationEvidenceError(
            "Git object format is unsupported"
        )
    digest = hashlib.new(object_format)
    digest.update(f"blob {len(raw)}\0".encode("ascii"))
    digest.update(raw)
    return digest.hexdigest()


def _verify_actual_source_bytes() -> None:
    object_format = _git("rev-parse", "--show-object-format")
    listing = _git_bytes(
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        SOURCE_BASELINE_COMMIT,
        "--",
        *SOURCE_CLOSURE_PATHS,
    )
    rows = [row for row in listing.split(b"\0") if row]
    if not rows:
        raise SamplingPoolCPUObservationEvidenceError(
            "baseline source closure is empty"
        )
    executable_bits = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    for row in rows:
        try:
            metadata, raw_path = row.split(b"\t", 1)
            mode, object_type, expected_oid = metadata.decode("ascii").split()
            relative_path = raw_path.decode("utf-8")
        except (UnicodeError, ValueError) as exc:
            raise SamplingPoolCPUObservationEvidenceError(
                "baseline source tree entry is invalid"
            ) from exc
        if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
            raise SamplingPoolCPUObservationEvidenceError(
                f"unsupported baseline source entry: {relative_path}"
            )
        actual_path = REPOSITORY_ROOT / relative_path
        try:
            metadata = actual_path.lstat()
            if mode == "120000":
                if not stat.S_ISLNK(metadata.st_mode):
                    raise SamplingPoolCPUObservationEvidenceError(
                        f"source symlink shape changed: {relative_path}"
                    )
                actual_bytes = os.fsencode(os.readlink(actual_path))
            else:
                if not stat.S_ISREG(metadata.st_mode):
                    raise SamplingPoolCPUObservationEvidenceError(
                        f"source file shape changed: {relative_path}"
                    )
                if bool(metadata.st_mode & executable_bits) != (mode == "100755"):
                    raise SamplingPoolCPUObservationEvidenceError(
                        f"source executable mode changed: {relative_path}"
                    )
                actual_bytes = actual_path.read_bytes()
        except OSError as exc:
            raise SamplingPoolCPUObservationEvidenceError(
                f"source file is unreadable: {relative_path}"
            ) from exc
        if _git_blob_oid(actual_bytes, object_format) != expected_oid:
            raise SamplingPoolCPUObservationEvidenceError(
                f"source bytes differ from merged baseline: {relative_path}"
            )


def _verify_source_baseline(
    *, require_matching_worktree: bool = True
) -> dict[str, object]:
    observed_tree = _git("rev-parse", f"{SOURCE_BASELINE_COMMIT}^{{tree}}")
    if observed_tree != SOURCE_BASELINE_TREE:
        raise SamplingPoolCPUObservationEvidenceError(
            "merged source baseline tree changed"
        )
    if require_matching_worktree:
        _verify_actual_source_bytes()
        try:
            _git(
                "diff",
                "--quiet",
                SOURCE_BASELINE_COMMIT,
                "--",
                *SOURCE_CLOSURE_PATHS,
            )
        except SamplingPoolCPUObservationEvidenceError as exc:
            raise SamplingPoolCPUObservationEvidenceError(
                "working source closure differs from merged baseline"
            ) from exc
        untracked = _git(
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            *SOURCE_CLOSURE_PATHS,
        )
        if untracked:
            raise SamplingPoolCPUObservationEvidenceError(
                "working source closure contains untracked files"
            )
    return {
        "closure_paths": list(SOURCE_CLOSURE_PATHS),
        "closure_verified_clean": True,
        "merged_main_commit": SOURCE_BASELINE_COMMIT,
        "merged_main_tree": SOURCE_BASELINE_TREE,
        "observer_source_git_blob": _git(
            "rev-parse",
            f"{SOURCE_BASELINE_COMMIT}:tools/rust/"
            "betelgeuze_sampling_pool_observe_v1.rs",
        ),
        "runner_source_git_blob": _git(
            "rev-parse",
            f"{SOURCE_BASELINE_COMMIT}:tools/"
            "run_engine_v2_sampling_pool_cpu_observation_v1.py",
        ),
        "rust_tree_git_oid": _git("rev-parse", f"{SOURCE_BASELINE_COMMIT}:rust"),
    }


def _baseline_file_sha256(path: str) -> str:
    try:
        raw = _git_bytes("show", f"{SOURCE_BASELINE_COMMIT}:{path}")
    except SamplingPoolCPUObservationEvidenceError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            f"baseline file is unavailable: {path}"
        ) from exc
    return _sha256(raw)


def _environment_fingerprints() -> dict[str, object]:
    return {
        key: {
            "set": key in os.environ,
            "value_sha256": _sha256(os.environ[key].encode())
            if key in os.environ
            else None,
        }
        for key in _BUILD_ENVIRONMENT_KEYS
    }


_CARGO_PATH_COMPONENT_DOMAIN = b"betelgeuze.cargo_path_components/1\0"


def _components_path_sha256(components: Sequence[str]) -> str:
    return _sha256(
        _CARGO_PATH_COMPONENT_DOMAIN + _canonical_projection(list(components))
    )


def _path_components_sha256(path: Path) -> list[str]:
    absolute = path.absolute()
    return [
        _sha256(os.fsencode(part)) for part in absolute.parts if part != absolute.anchor
    ]


def _path_sha256(path: Path) -> str:
    return _components_path_sha256(_path_components_sha256(path))


def _cargo_configuration_file(path: Path) -> dict[str, object]:
    candidate_components = _path_components_sha256(path)
    binding: dict[str, object] = {
        "candidate_path_sha256": _components_path_sha256(candidate_components),
        "content_sha256": None,
        "present": False,
        "resolved_path_components_sha256": None,
        "resolved_path_sha256": None,
    }
    try:
        path.lstat()
    except FileNotFoundError:
        return binding
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise SamplingPoolCPUObservationEvidenceError(
                "Cargo configuration candidate is not a regular file"
            )
        content = resolved.read_bytes()
    except OSError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "Cargo configuration candidate is unreadable"
        ) from exc
    return {
        **binding,
        "content_sha256": _sha256(content),
        "present": True,
        "resolved_path_components_sha256": _path_components_sha256(resolved),
        "resolved_path_sha256": _path_sha256(resolved),
    }


def _cargo_configuration_binding() -> dict[str, object]:
    raw_cargo_home = os.environ.get("CARGO_HOME")
    if raw_cargo_home is not None and not raw_cargo_home:
        raise SamplingPoolCPUObservationEvidenceError("CARGO_HOME is empty")
    if raw_cargo_home is None:
        cargo_home = Path.home() / ".cargo"
        cargo_home_origin = "default_user_home"
    else:
        candidate = Path(raw_cargo_home).expanduser()
        cargo_home = (
            candidate if candidate.is_absolute() else observer.RUST_ROOT / candidate
        )
        cargo_home_origin = "environment"

    roots: list[dict[str, object]] = []
    for index, directory in enumerate(
        (observer.RUST_ROOT, *observer.RUST_ROOT.parents)
    ):
        root = directory / ".cargo"
        roots.append(
            {
                "candidate_files": {
                    name: _cargo_configuration_file(root / name)
                    for name in _CARGO_CONFIGURATION_FILENAMES
                },
                "root_path_components_sha256": _path_components_sha256(root),
                "root_path_sha256": _path_sha256(root),
                "scope": f"working_directory_ancestor_{index}",
            }
        )
    roots.append(
        {
            "candidate_files": {
                name: _cargo_configuration_file(cargo_home / name)
                for name in _CARGO_CONFIGURATION_FILENAMES
            },
            "root_path_components_sha256": _path_components_sha256(cargo_home),
            "root_path_sha256": _path_sha256(cargo_home),
            "scope": "cargo_home",
        }
    )
    return {
        "cargo_home_origin": cargo_home_origin,
        "lookup_roots": roots,
    }


def _timed_runtime_environment() -> dict[str, str]:
    return dict(_TIMED_RUNTIME_ENVIRONMENT)


def _run_timed_observer(
    command: Sequence[str], *, cwd: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=_timed_runtime_environment(),
        )
    except OSError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "timed observer failed to launch"
        ) from exc
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise SamplingPoolCPUObservationEvidenceError(
            "timed observer exceeded its timeout"
        ) from exc
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SamplingPoolCPUObservationEvidenceError(
            f"timed observer failed: {detail[:4096]}"
        )
    return completed


def _cpu_affinity() -> list[int]:
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except (OSError, ValueError) as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "Linux CPU affinity is unavailable"
        ) from exc
    if not affinity:
        raise SamplingPoolCPUObservationEvidenceError("Linux CPU affinity is empty")
    return affinity


def _require_stable_affinity(before: list[int], after: object) -> None:
    if after != before:
        raise SamplingPoolCPUObservationEvidenceError(
            "CPU affinity changed during observation"
        )


def _affinity_cpu_models_from(cpuinfo: str, affinity: Sequence[int]) -> dict[str, str]:
    models: dict[int, str] = {}
    labels = (
        "model name",
        "model",
        "hardware",
        "machine",
        "system type",
        "platform",
        "uarch",
        "cpu",
    )
    sections: list[dict[str, str]] = []
    for section in re.split(r"\n\s*\n", cpuinfo):
        fields: dict[str, str] = {}
        for line in section.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
        sections.append(fields)

    machine_wide_model: str | None = None
    machine_sections = [
        fields for fields in sections if not fields.get("processor", "").isdigit()
    ]
    for label in (*labels, "processor"):
        candidates = {fields[label] for fields in machine_sections if fields.get(label)}
        if candidates:
            if len(candidates) != 1:
                raise SamplingPoolCPUObservationEvidenceError(
                    "machine-wide CPU model is ambiguous"
                )
            machine_wide_model = candidates.pop()
            break

    for fields in sections:
        processor = fields.get("processor", "")
        if not processor.isdigit():
            continue
        model = next(
            (fields[label] for label in labels if fields.get(label)),
            machine_wide_model,
        )
        if model is not None:
            models[int(processor)] = model
    missing = [cpu_id for cpu_id in affinity if cpu_id not in models]
    if missing:
        raise SamplingPoolCPUObservationEvidenceError(
            "CPU model is unavailable for effective affinity"
        )
    return {str(cpu_id): models[cpu_id] for cpu_id in affinity}


def _host_identity(cpu_model: str) -> dict[str, object]:
    try:
        os_release = Path("/etc/os-release").read_bytes()
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_bytes().strip()
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="ascii")
    except (OSError, ValueError) as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "Linux host identity is unavailable"
        ) from exc
    logical_cpu_count = os.cpu_count()
    if type(logical_cpu_count) is not int or logical_cpu_count <= 0:
        raise SamplingPoolCPUObservationEvidenceError(
            "Linux CPU affinity or logical count is invalid"
        )
    affinity = _cpu_affinity()
    affinity_cpu_models = _affinity_cpu_models_from(cpuinfo, affinity)
    if set(affinity_cpu_models.values()) != {cpu_model}:
        raise SamplingPoolCPUObservationEvidenceError(
            "effective affinity CPU models differ from observer identity"
        )
    return {
        "affinity_cpu_ids": affinity,
        "affinity_cpu_models": affinity_cpu_models,
        "boot_id_sha256": _sha256(boot_id),
        "cpu_model": cpu_model,
        "kernel_release": platform.release(),
        "logical_cpu_count": logical_cpu_count,
        "machine_architecture": platform.machine(),
        "os_release_sha256": _sha256(os_release),
        "system": platform.system(),
    }


def _load_observer_output(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=observer._reject_duplicate_keys,
            parse_float=_parse_finite_float,
            parse_int=_parse_bounded_int,
            parse_constant=lambda token: (_ for _ in ()).throw(
                SamplingPoolCPUObservationEvidenceError(
                    f"non-finite observer JSON value: {token}"
                )
            ),
        )
    except (
        json.JSONDecodeError,
        observer.SamplingPoolCPUObservationError,
        UnicodeError,
    ) as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "observer output is invalid JSON"
        ) from exc
    try:
        return observer._validate(value, expected_sample_count=SAMPLE_COUNT)
    except observer.SamplingPoolCPUObservationError as exc:
        raise SamplingPoolCPUObservationEvidenceError(str(exc)) from exc


def _toolchain_identity() -> dict[str, str]:
    return {
        "cargo_version": observer._run(
            ("cargo", "--version", "--verbose"),
            cwd=observer.RUST_ROOT,
            timeout=30,
        ).stdout.strip(),
        "rustc_version": observer._run(
            ("rustc", "--version", "--verbose"),
            cwd=observer.RUST_ROOT,
            timeout=30,
        ).stdout.strip(),
    }


def _build_release_library_fresh(target_directory: Path) -> Path:
    if target_directory.exists():
        raise SamplingPoolCPUObservationEvidenceError(
            "capture-owned Cargo target already exists"
        )
    completed = observer._run(
        (
            "cargo",
            "build",
            "--target-dir",
            str(target_directory),
            "--release",
            "--locked",
            "-p",
            "betelgeuze-docking-search",
            "--lib",
            "--message-format=json",
        ),
        cwd=observer.RUST_ROOT,
        timeout=180,
    )
    observed: list[Path] = []
    for line in completed.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        target = row.get("target")
        if row.get("reason") != "compiler-artifact" or type(target) is not dict:
            continue
        if target.get("name") != "betelgeuze_docking_search":
            continue
        for filename in row.get("filenames", []):
            path = Path(filename)
            if (
                path.name == "libbetelgeuze_docking_search.rlib"
                or path.name.startswith("libbetelgeuze_docking_search-")
            ) and path.suffix == ".rlib":
                observed.append(path.resolve())
    unique = sorted(set(observed))
    resolved_target = target_directory.resolve()
    if (
        len(unique) != 1
        or not unique[0].is_file()
        or not unique[0].is_relative_to(resolved_target)
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "fresh Cargo build did not report one exact in-target rlib"
        )
    return unique[0]


def _capture_fresh_observation() -> tuple[dict[str, Any], list[int], dict[str, object]]:
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-sampling-pool-evidence-"
    ) as directory:
        temporary_root = Path(directory)
        rlib = _build_release_library_fresh(temporary_root / "cargo-target")
        rlib_sha256 = _file_sha256(rlib)
        rlib_bytes = rlib.stat().st_size
        executable = temporary_root / "betelgeuze-sampling-pool-observe-v1"
        observer._compile_observer(rlib, executable)
        executable_sha256 = _file_sha256(executable)
        executable_bytes = executable.stat().st_size
        affinity_before = _cpu_affinity()
        completed = _run_timed_observer(
            (str(executable), "--observe", str(SAMPLE_COUNT)),
            cwd=REPOSITORY_ROOT,
            timeout=600,
        )
        if (
            _file_sha256(executable) != executable_sha256
            or executable.stat().st_size != executable_bytes
            or _file_sha256(rlib) != rlib_sha256
            or rlib.stat().st_size != rlib_bytes
        ):
            raise SamplingPoolCPUObservationEvidenceError(
                "fresh observer binary or release rlib changed during execution"
            )
        observation = _load_observer_output(completed.stdout)
        artifacts: dict[str, object] = {
            "observer_binary_bytes": executable_bytes,
            "observer_binary_sha256": executable_sha256,
            "release_rlib_bytes": rlib_bytes,
            "release_rlib_sha256": rlib_sha256,
            "target_directory_role": "fresh_capture_owned_temporary_directory",
        }
        return observation, affinity_before, artifacts


def capture() -> dict[str, object]:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise SamplingPoolCPUObservationEvidenceError(
            "GitHub Actions cannot capture timing evidence"
        )
    _verify_imported_observer_binding()
    source = _verify_source_baseline()
    capture_tool_sha256 = _file_sha256(Path(__file__).resolve())
    build_environment = _environment_fingerprints()
    cargo_configuration = _cargo_configuration_binding()
    toolchain = _toolchain_identity()
    observation, affinity_before, artifacts = _capture_fresh_observation()
    host = _host_identity(str(observation["cpu_model"]))
    _require_stable_affinity(affinity_before, host["affinity_cpu_ids"])
    if _verify_source_baseline() != source:
        raise SamplingPoolCPUObservationEvidenceError(
            "source closure changed during execution"
        )
    if _file_sha256(Path(__file__).resolve()) != capture_tool_sha256:
        raise SamplingPoolCPUObservationEvidenceError(
            "capture tool changed during execution"
        )
    if (
        _environment_fingerprints() != build_environment
        or _cargo_configuration_binding() != cargo_configuration
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "build environment or Cargo configuration changed during execution"
        )
    if _toolchain_identity() != toolchain:
        raise SamplingPoolCPUObservationEvidenceError(
            "Rust/Cargo toolchain changed during execution"
        )
    projection: dict[str, object] = {
        "authority": dict(observation["authority"]),
        "build": {
            "build_environment": build_environment,
            "cargo_configuration": cargo_configuration,
            **artifacts,
            "runtime_environment": _timed_runtime_environment(),
            "toolchain": toolchain,
        },
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": host,
        "observation": observation,
        "profile_id": PROFILE_ID,
        "schema_id": SCHEMA_ID,
        "source": {
            **source,
            "cargo_lock_sha256": _file_sha256(observer.RUST_ROOT / "Cargo.lock"),
            "capture_tool_sha256": capture_tool_sha256,
            "observer_source_sha256": _file_sha256(observer.RUST_SOURCE),
            "runner_source_sha256": _file_sha256(Path(observer.__file__).resolve()),
        },
        "status": STATUS,
    }
    return {**projection, "receipt_sha256": _receipt_sha256(projection)}


def _require_digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SamplingPoolCPUObservationEvidenceError(
            f"{label} is not a lowercase SHA-256"
        )
    return value


def _require_git_oid(value: object, *, label: str) -> str:
    if type(value) is not str or _GIT_OID.fullmatch(value) is None:
        raise SamplingPoolCPUObservationEvidenceError(
            f"{label} is not a lowercase Git OID"
        )
    return value


def _verify_cargo_configuration(value: object) -> None:
    if (
        type(value) is not dict
        or set(value) != {"cargo_home_origin", "lookup_roots"}
        or type(value.get("cargo_home_origin")) is not str
        or value.get("cargo_home_origin") not in {"default_user_home", "environment"}
        or type(value.get("lookup_roots")) is not list
        or len(value["lookup_roots"]) < 3
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "Cargo configuration binding is invalid"
        )
    roots = value["lookup_roots"]
    working_roots = roots[:-1]
    expected_scopes = [
        *(f"working_directory_ancestor_{index}" for index in range(len(working_roots))),
        "cargo_home",
    ]
    if [row.get("scope") if type(row) is dict else None for row in roots] != (
        expected_scopes
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "Cargo configuration lookup roots are invalid"
        )
    for root in roots:
        if (
            type(root) is not dict
            or set(root)
            != {
                "candidate_files",
                "root_path_components_sha256",
                "root_path_sha256",
                "scope",
            }
            or type(root.get("candidate_files")) is not dict
            or set(root["candidate_files"]) != set(_CARGO_CONFIGURATION_FILENAMES)
            or type(root.get("root_path_components_sha256")) is not list
            or any(
                type(component) is not str or _SHA256.fullmatch(component) is None
                for component in root["root_path_components_sha256"]
            )
        ):
            raise SamplingPoolCPUObservationEvidenceError(
                "Cargo configuration lookup root is invalid"
            )
        root_components = root["root_path_components_sha256"]
        if _require_digest(
            root.get("root_path_sha256"),
            label=f"Cargo configuration root {root.get('scope')}",
        ) != _components_path_sha256(root_components):
            raise SamplingPoolCPUObservationEvidenceError(
                "Cargo configuration root digest is not component-bound"
            )
        candidate_digests: set[str] = set()
        for name, candidate in root["candidate_files"].items():
            if (
                type(candidate) is not dict
                or set(candidate)
                != {
                    "candidate_path_sha256",
                    "content_sha256",
                    "present",
                    "resolved_path_components_sha256",
                    "resolved_path_sha256",
                }
                or type(candidate.get("present")) is not bool
            ):
                raise SamplingPoolCPUObservationEvidenceError(
                    f"Cargo configuration candidate is invalid: {name}"
                )
            candidate_digest = _require_digest(
                candidate.get("candidate_path_sha256"),
                label=f"Cargo configuration candidate {name}",
            )
            expected_candidate_components = [*root_components, _sha256(name.encode())]
            if candidate_digest != _components_path_sha256(
                expected_candidate_components
            ):
                raise SamplingPoolCPUObservationEvidenceError(
                    f"Cargo configuration candidate path is not root-bound: {name}"
                )
            candidate_digests.add(candidate_digest)
            if candidate["present"]:
                _require_digest(
                    candidate.get("content_sha256"),
                    label=f"Cargo configuration content {name}",
                )
                resolved_components = candidate.get("resolved_path_components_sha256")
                if (
                    type(resolved_components) is not list
                    or not resolved_components
                    or any(
                        type(component) is not str
                        or _SHA256.fullmatch(component) is None
                        for component in resolved_components
                    )
                ):
                    raise SamplingPoolCPUObservationEvidenceError(
                        f"Cargo configuration resolved components are invalid: {name}"
                    )
                if _require_digest(
                    candidate.get("resolved_path_sha256"),
                    label=f"Cargo configuration resolved path {name}",
                ) != _components_path_sha256(resolved_components):
                    raise SamplingPoolCPUObservationEvidenceError(
                        f"Cargo configuration resolved path is not component-bound: {name}"
                    )
            elif (
                candidate.get("content_sha256") is not None
                or candidate.get("resolved_path_components_sha256") is not None
                or candidate.get("resolved_path_sha256") is not None
            ):
                raise SamplingPoolCPUObservationEvidenceError(
                    f"absent Cargo configuration candidate has metadata: {name}"
                )
        if len(candidate_digests) != len(_CARGO_CONFIGURATION_FILENAMES):
            raise SamplingPoolCPUObservationEvidenceError(
                "Cargo configuration candidate paths are not distinct"
            )
    cargo_component = _sha256(b".cargo")
    rust_component = _sha256(b"rust")
    working_components = [root["root_path_components_sha256"] for root in working_roots]
    if (
        len(working_components[0]) < 2
        or working_components[0][-2:] != [rust_component, cargo_component]
        or working_components[-1] != [cargo_component]
        or any(
            following != current[:-2] + [cargo_component]
            for current, following in zip(working_components, working_components[1:])
        )
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "Cargo configuration ancestor chain is incomplete"
        )


def verify(document: object) -> dict[str, object]:
    _verify_imported_observer_binding()
    if type(document) is not dict:
        raise SamplingPoolCPUObservationEvidenceError("evidence must be an object")
    expected_keys = {
        "authority",
        "build",
        "captured_at_utc",
        "host",
        "observation",
        "profile_id",
        "receipt_sha256",
        "schema_id",
        "source",
        "status",
    }
    if set(document) != expected_keys:
        raise SamplingPoolCPUObservationEvidenceError("evidence keys changed")
    projection = dict(document)
    receipt_sha256 = projection.pop("receipt_sha256")
    if _require_digest(receipt_sha256, label="receipt_sha256") != _receipt_sha256(
        projection
    ):
        raise SamplingPoolCPUObservationEvidenceError("evidence receipt changed")
    if (
        document["schema_id"] != SCHEMA_ID
        or document["profile_id"] != PROFILE_ID
        or document["status"] != STATUS
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "evidence schema, profile, or status changed"
        )
    observation = document["observation"]
    if type(observation) is not dict or set(observation) != _OBSERVATION_KEYS:
        raise SamplingPoolCPUObservationEvidenceError("observation keys changed")
    fixtures = observation.get("fixtures")
    if type(fixtures) is not list or any(
        type(row) is not dict or set(row) != _OBSERVED_FIXTURE_KEYS for row in fixtures
    ):
        raise SamplingPoolCPUObservationEvidenceError("observed fixture keys changed")
    if any(
        type(row["fixture_id"]) is not str or not row["fixture_id"] for row in fixtures
    ):
        raise SamplingPoolCPUObservationEvidenceError("fixture ID is invalid")
    if type(observation.get("sample_count")) is not int or any(
        any(type(row[key]) is not int for key in _OBSERVED_FIXTURE_INTEGER_KEYS)
        or type(row["wall_time_ns_samples"]) is not list
        or any(type(sample) is not int for sample in row["wall_time_ns_samples"])
        for row in fixtures
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "observation denominators or statistics are not integers"
        )
    try:
        validated_observation = observer._validate(
            observation, expected_sample_count=SAMPLE_COUNT
        )
    except observer.SamplingPoolCPUObservationError as exc:
        raise SamplingPoolCPUObservationEvidenceError(str(exc)) from exc
    if any(row["peak_rss_delta_kib"] > row["peak_rss_kib"] for row in fixtures):
        raise SamplingPoolCPUObservationEvidenceError(
            "peak RSS delta exceeds absolute peak"
        )
    authority = document["authority"]
    if (
        type(authority) is not dict
        or set(authority) != observer.EXPECTED_AUTHORITY_KEYS
        or any(type(value) is not bool for value in authority.values())
        or authority != validated_observation["authority"]
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "evidence authority is invalid or differs from observation"
        )
    source = document["source"]
    if type(source) is not dict:
        raise SamplingPoolCPUObservationEvidenceError("source binding is absent")
    if set(source) != {
        "capture_tool_sha256",
        "cargo_lock_sha256",
        "closure_paths",
        "closure_verified_clean",
        "merged_main_commit",
        "merged_main_tree",
        "observer_source_git_blob",
        "observer_source_sha256",
        "runner_source_git_blob",
        "runner_source_sha256",
        "rust_tree_git_oid",
    }:
        raise SamplingPoolCPUObservationEvidenceError("source binding keys changed")
    if type(source.get("closure_verified_clean")) is not bool:
        raise SamplingPoolCPUObservationEvidenceError(
            "source clean-closure marker is not Boolean"
        )
    current_source = _verify_source_baseline(require_matching_worktree=False)
    for key, expected in current_source.items():
        if source.get(key) != expected:
            raise SamplingPoolCPUObservationEvidenceError(
                f"source binding changed: {key}"
            )
    exact_source_digests = {
        "cargo_lock_sha256": _baseline_file_sha256("rust/Cargo.lock"),
        "capture_tool_sha256": _file_sha256(Path(__file__).resolve()),
        "observer_source_sha256": _baseline_file_sha256(
            "tools/rust/betelgeuze_sampling_pool_observe_v1.rs"
        ),
        "runner_source_sha256": _baseline_file_sha256(
            "tools/run_engine_v2_sampling_pool_cpu_observation_v1.py"
        ),
    }
    for key, expected in exact_source_digests.items():
        if _require_digest(source.get(key), label=f"source.{key}") != expected:
            raise SamplingPoolCPUObservationEvidenceError(
                f"source digest changed: {key}"
            )
    for key in (
        "observer_source_git_blob",
        "runner_source_git_blob",
        "rust_tree_git_oid",
    ):
        _require_git_oid(source.get(key), label=f"source.{key}")
    build = document["build"]
    if type(build) is not dict or set(build) != {
        "build_environment",
        "cargo_configuration",
        "observer_binary_bytes",
        "observer_binary_sha256",
        "release_rlib_bytes",
        "release_rlib_sha256",
        "runtime_environment",
        "target_directory_role",
        "toolchain",
    }:
        raise SamplingPoolCPUObservationEvidenceError("build binding is absent")
    for key in ("observer_binary_sha256", "release_rlib_sha256"):
        _require_digest(build.get(key), label=f"build.{key}")
    for key in ("observer_binary_bytes", "release_rlib_bytes"):
        if type(build.get(key)) is not int or build[key] <= 0:
            raise SamplingPoolCPUObservationEvidenceError(f"build.{key} is invalid")
    if build.get("target_directory_role") != (
        "fresh_capture_owned_temporary_directory"
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "build target-directory role is invalid"
        )
    if (
        type(build.get("toolchain")) is not dict
        or set(build["toolchain"]) != {"cargo_version", "rustc_version"}
        or any(
            type(build["toolchain"].get(key)) is not str
            or not build["toolchain"][key].strip()
            for key in ("cargo_version", "rustc_version")
        )
        or type(build.get("build_environment")) is not dict
        or set(build["build_environment"]) != set(_BUILD_ENVIRONMENT_KEYS)
    ):
        raise SamplingPoolCPUObservationEvidenceError("build metadata is invalid")
    for key, row in build["build_environment"].items():
        if (
            type(row) is not dict
            or set(row) != {"set", "value_sha256"}
            or type(row["set"]) is not bool
            or (row["set"] is False and row["value_sha256"] is not None)
            or (
                row["set"] is True
                and (
                    type(row["value_sha256"]) is not str
                    or _SHA256.fullmatch(row["value_sha256"]) is None
                )
            )
        ):
            raise SamplingPoolCPUObservationEvidenceError(
                f"build environment metadata is invalid: {key}"
            )
    _verify_cargo_configuration(build["cargo_configuration"])
    if build.get("runtime_environment") != _TIMED_RUNTIME_ENVIRONMENT:
        raise SamplingPoolCPUObservationEvidenceError(
            "timed runtime environment is invalid"
        )
    host = document["host"]
    affinity_cpu_ids = host.get("affinity_cpu_ids") if type(host) is dict else None
    affinity_cpu_models = (
        host.get("affinity_cpu_models") if type(host) is dict else None
    )
    if (
        type(host) is not dict
        or set(host)
        != {
            "affinity_cpu_ids",
            "affinity_cpu_models",
            "boot_id_sha256",
            "cpu_model",
            "kernel_release",
            "logical_cpu_count",
            "machine_architecture",
            "os_release_sha256",
            "system",
        }
        or host.get("cpu_model") != validated_observation["cpu_model"]
        or type(affinity_cpu_ids) is not list
        or not affinity_cpu_ids
        or any(type(item) is not int or item < 0 for item in affinity_cpu_ids)
        or affinity_cpu_ids != sorted(set(affinity_cpu_ids))
        or type(affinity_cpu_models) is not dict
        or set(affinity_cpu_models) != {str(item) for item in affinity_cpu_ids}
        or any(
            type(model) is not str or not model.strip()
            for model in affinity_cpu_models.values()
        )
        or set(affinity_cpu_models.values()) != {host.get("cpu_model")}
        or type(host.get("logical_cpu_count")) is not int
        or host["logical_cpu_count"] <= 0
        or len(affinity_cpu_ids) > host["logical_cpu_count"]
        or any(
            type(host.get(key)) is not str or not host[key]
            for key in ("cpu_model", "kernel_release", "machine_architecture")
        )
        or host.get("system") != "Linux"
    ):
        raise SamplingPoolCPUObservationEvidenceError("host identity is invalid")
    _require_digest(host.get("boot_id_sha256"), label="host.boot_id_sha256")
    _require_digest(host.get("os_release_sha256"), label="host.os_release_sha256")
    timestamp = document["captured_at_utc"]
    if type(timestamp) is not str:
        raise SamplingPoolCPUObservationEvidenceError("capture timestamp is invalid")
    try:
        captured = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "capture timestamp is invalid"
        ) from exc
    if (
        captured.tzinfo is None
        or captured.utcoffset() != timezone.utc.utcoffset(None)
        or captured.isoformat(timespec="seconds") != timestamp
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "capture timestamp is not exact UTC calendar seconds"
        )
    return document


def load_and_verify(path: Path) -> dict[str, object]:
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > MAXIMUM_EVIDENCE_BYTES
        ):
            raise SamplingPoolCPUObservationEvidenceError(
                "evidence file shape is invalid"
            )
        raw = resolved.read_bytes()
    except OSError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "evidence file is unreadable"
        ) from exc
    if len(raw) != metadata.st_size or not raw.endswith(b"\n"):
        raise SamplingPoolCPUObservationEvidenceError("evidence file shape is invalid")
    try:
        document = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=observer._reject_duplicate_keys,
            parse_float=_parse_finite_float,
            parse_int=_parse_bounded_int,
            parse_constant=lambda token: (_ for _ in ()).throw(
                SamplingPoolCPUObservationEvidenceError(
                    f"non-finite evidence JSON value: {token}"
                )
            ),
        )
    except (
        json.JSONDecodeError,
        observer.SamplingPoolCPUObservationError,
        UnicodeError,
    ) as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "evidence is not strict JSON"
        ) from exc
    if raw != _canonical_bytes(document):
        raise SamplingPoolCPUObservationEvidenceError(
            "evidence is not canonical pretty ASCII JSON"
        )
    return verify(document)


def _write_exclusive(path: Path, payload: bytes) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        directory_descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--capture", type=Path, metavar="OUTPUT_JSON")
    operation.add_argument("--verify", type=Path, metavar="EVIDENCE_JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    global observer
    arguments = _parser().parse_args(argv)
    try:
        if observer is None:
            observer = _load_observer()
    except (OSError, SamplingPoolCPUObservationEvidenceError) as exc:
        print(f"sampling_pool_cpu_observation_evidence=blocked:{exc}")
        return 1
    try:
        if arguments.capture is not None:
            document = capture()
            verify(document)
            _write_exclusive(arguments.capture, _canonical_bytes(document))
        else:
            document = load_and_verify(arguments.verify)
    except (
        OSError,
        observer.SamplingPoolCPUObservationError,
        SamplingPoolCPUObservationEvidenceError,
    ) as exc:
        print(f"sampling_pool_cpu_observation_evidence=blocked:{exc}")
        return 1
    print(
        f"sampling_pool_cpu_observation_evidence=verified:{document['receipt_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
