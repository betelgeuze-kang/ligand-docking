#!/usr/bin/env python3
"""Capture or verify one source-bound synthetic sampling-pool CPU observation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import tempfile
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
if hashlib.sha256(RUNNER_SOURCE_PATH.read_bytes()).hexdigest() != (
    EXPECTED_RUNNER_SOURCE_SHA256
):
    raise SamplingPoolCPUObservationEvidenceError(
        "imported observation runner differs from the pinned source"
    )

from tools import run_engine_v2_sampling_pool_cpu_observation_v1 as observer  # noqa: E402


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


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _verify_imported_observer_binding() -> None:
    if (
        Path(observer.__file__).resolve() != RUNNER_SOURCE_PATH
        or _file_sha256(RUNNER_SOURCE_PATH) != EXPECTED_RUNNER_SOURCE_SHA256
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "imported observation runner differs from the pinned source"
        )


def _receipt_sha256(projection: Mapping[str, object]) -> str:
    return _sha256(RECEIPT_DOMAIN + _canonical_projection(projection))


def _git(*arguments: str) -> str:
    try:
        completed = observer._run(("git", *arguments), cwd=REPOSITORY_ROOT, timeout=30)
    except observer.SamplingPoolCPUObservationError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            f"git source binding failed: {' '.join(arguments)}"
        ) from exc
    return completed.stdout.strip()


def _verify_source_baseline(
    *, require_matching_worktree: bool = True
) -> dict[str, object]:
    observed_tree = _git("rev-parse", f"{SOURCE_BASELINE_COMMIT}^{{tree}}")
    if observed_tree != SOURCE_BASELINE_TREE:
        raise SamplingPoolCPUObservationEvidenceError(
            "merged source baseline tree changed"
        )
    if require_matching_worktree:
        try:
            observer._run(
                (
                    "git",
                    "diff",
                    "--quiet",
                    SOURCE_BASELINE_COMMIT,
                    "--",
                    *SOURCE_CLOSURE_PATHS,
                ),
                cwd=REPOSITORY_ROOT,
                timeout=30,
            )
        except observer.SamplingPoolCPUObservationError as exc:
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
        completed = observer._run(
            ("git", "show", f"{SOURCE_BASELINE_COMMIT}:{path}"),
            cwd=REPOSITORY_ROOT,
            timeout=30,
        )
    except observer.SamplingPoolCPUObservationError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            f"baseline file is unavailable: {path}"
        ) from exc
    return _sha256(completed.stdout.encode("utf-8"))


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
    for section in re.split(r"\n\s*\n", cpuinfo):
        fields: dict[str, str] = {}
        for line in section.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
        processor = fields.get("processor", "")
        if not processor.isdigit():
            continue
        model = next(
            (fields[label] for label in labels if fields.get(label)),
            None,
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


def capture() -> dict[str, object]:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise SamplingPoolCPUObservationEvidenceError(
            "GitHub Actions cannot capture timing evidence"
        )
    _verify_imported_observer_binding()
    source = _verify_source_baseline()
    capture_tool_sha256 = _file_sha256(Path(__file__).resolve())
    rlib = observer._build_library()
    rlib_sha256 = _file_sha256(rlib)
    rlib_bytes = rlib.stat().st_size
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-sampling-pool-evidence-"
    ) as directory:
        executable = Path(directory) / "betelgeuze-sampling-pool-observe-v1"
        observer._compile_observer(rlib, executable)
        executable_sha256 = _file_sha256(executable)
        executable_bytes = executable.stat().st_size
        affinity_before = _cpu_affinity()
        completed = observer._run(
            (str(executable), "--observe", str(SAMPLE_COUNT)),
            cwd=REPOSITORY_ROOT,
            timeout=600,
        )
        if _file_sha256(executable) != executable_sha256:
            raise SamplingPoolCPUObservationEvidenceError(
                "observer binary changed during execution"
            )
    observation = _load_observer_output(completed.stdout)
    host = _host_identity(str(observation["cpu_model"]))
    _require_stable_affinity(affinity_before, host["affinity_cpu_ids"])
    if _verify_source_baseline() != source:
        raise SamplingPoolCPUObservationEvidenceError(
            "source closure changed during execution"
        )
    if (
        _file_sha256(Path(__file__).resolve()) != capture_tool_sha256
        or _file_sha256(rlib) != rlib_sha256
        or rlib.stat().st_size != rlib_bytes
    ):
        raise SamplingPoolCPUObservationEvidenceError(
            "capture tool or release rlib changed during execution"
        )
    toolchain = {
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
    projection: dict[str, object] = {
        "authority": dict(observation["authority"]),
        "build": {
            "build_environment": _environment_fingerprints(),
            "observer_binary_bytes": executable_bytes,
            "observer_binary_sha256": executable_sha256,
            "release_rlib_bytes": rlib_bytes,
            "release_rlib_sha256": rlib_sha256,
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
    if document["authority"] != validated_observation["authority"]:
        raise SamplingPoolCPUObservationEvidenceError(
            "evidence authority differs from observation"
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
        "observer_binary_bytes",
        "observer_binary_sha256",
        "release_rlib_bytes",
        "release_rlib_sha256",
        "toolchain",
    }:
        raise SamplingPoolCPUObservationEvidenceError("build binding is absent")
    for key in ("observer_binary_sha256", "release_rlib_sha256"):
        _require_digest(build.get(key), label=f"build.{key}")
    for key in ("observer_binary_bytes", "release_rlib_bytes"):
        if type(build.get(key)) is not int or build[key] <= 0:
            raise SamplingPoolCPUObservationEvidenceError(f"build.{key} is invalid")
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
    host = document["host"]
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
        or type(host.get("affinity_cpu_ids")) is not list
        or not host["affinity_cpu_ids"]
        or any(type(item) is not int or item < 0 for item in host["affinity_cpu_ids"])
        or host["affinity_cpu_ids"] != sorted(set(host["affinity_cpu_ids"]))
        or type(host.get("affinity_cpu_models")) is not dict
        or set(host["affinity_cpu_models"])
        != {str(item) for item in host["affinity_cpu_ids"]}
        or set(host["affinity_cpu_models"].values()) != {host.get("cpu_model")}
        or type(host.get("logical_cpu_count")) is not int
        or host["logical_cpu_count"] <= 0
        or any(
            type(host.get(key)) is not str or not host[key]
            for key in ("cpu_model", "kernel_release", "machine_architecture")
        )
        or host.get("system") != "Linux"
    ):
        raise SamplingPoolCPUObservationEvidenceError("host identity is invalid")
    _require_digest(host.get("boot_id_sha256"), label="host.boot_id_sha256")
    _require_digest(host.get("os_release_sha256"), label="host.os_release_sha256")
    try:
        captured = datetime.fromisoformat(str(document["captured_at_utc"]))
    except ValueError as exc:
        raise SamplingPoolCPUObservationEvidenceError(
            "capture timestamp is invalid"
        ) from exc
    if captured.tzinfo is None or captured.utcoffset() != timezone.utc.utcoffset(None):
        raise SamplingPoolCPUObservationEvidenceError("capture timestamp is not UTC")
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
    arguments = _parser().parse_args(argv)
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
