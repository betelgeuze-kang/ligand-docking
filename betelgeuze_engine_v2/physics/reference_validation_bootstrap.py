"""Stdlib-only bootstrap for the bounded reference-validation process.

This file is executed directly, before importing the Engine v2 package.  An
isolated outer launcher verifies the executable and command, then re-executes
the same interpreter with a minimal environment so ``PYTHONHASHSEED`` is
applied during interpreter initialization.  Automatic ``site`` loading stays
disabled throughout the bootstrap.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import select
import stat
import subprocess
import sys
import sysconfig
import time


REFERENCE_VALIDATION_BOOTSTRAP_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_validation_bootstrap.py"
)
REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_validation_dependency_identity.py"
)
REFERENCE_VALIDATION_SOURCE_IDENTITY_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/validation_source_identity.py"
)
REFERENCE_VALIDATION_NATIVE_RUNTIME_IDENTITY_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/validation_native_runtime_identity.py"
)
REFERENCE_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV = (
    "python",
    "-I",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    REFERENCE_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_VALIDATION_FIXED_RUNPY_LOADER = (
    'import runpy,sys;p=sys.argv.pop();runpy.run_path(p,run_name="__main__")'
)
REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV = (
    "python",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    "-c",
    REFERENCE_VALIDATION_FIXED_RUNPY_LOADER,
    REFERENCE_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_VALIDATION_CONTROLLED_INNER_STATE = "seeded-controlled-inner/3"
REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV = (
    "BETELGEUZE_REFERENCE_VALIDATION_BOOTSTRAP_STAGE"
)
REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV = (
    "BETELGEUZE_REFERENCE_VALIDATION_PREFLIGHT_DEADLINE"
)
REFERENCE_VALIDATION_APPLICATION_SEED_ENV = "BETELGEUZE_REFERENCE_VALIDATION_SEED"
REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE = (
    "_betelgeuze_reference_validation_bootstrap_state"
)
REFERENCE_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES = 1_048_576
REFERENCE_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES = 65_536
REFERENCE_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS = 180.0
REFERENCE_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_ENTRIES = 50_000
REFERENCE_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_PATH_BYTES = 4_096
REFERENCE_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_BYTES = 16 * 1024**2
REFERENCE_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_WALL_SECONDS = 10.0
REFERENCE_VALIDATION_BOOTSTRAP_PROCESS_ARGV_MAX_BYTES = 65_536
REFERENCE_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH = (
    "/etc/betelgeuze/engine-v2/reference-validation-trust-anchors.json"
)
_REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_trust_store/1.0.0"
)
_REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "hmac-sha256"
_REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_runner_request/2.0.0"
)
_BOOTSTRAP_REQUEST_FIELDS = {
    "schema_id",
    "reservation_root",
    "artifact_output_root",
    "authorization_nonce_sha256",
    "authorization_receipt",
    "review_attestation",
    "expected_implementation_author_identity_sha256",
    "network_isolation_attestation",
    "expected_code_commit_sha",
    "expected_runner_source_sha256",
    "expected_dependency_artifact_sha256_rows",
    "revoked_authorization_receipt_sha256s",
    "revoked_review_attestation_sha256s",
    "externally_conflicting_nonce_sha256s",
    "revoked_network_attestation_sha256s",
}


class _ReferenceValidationBootstrapError(RuntimeError):
    """The interpreter did not establish the frozen import boundary."""


_CONTROLLED_INNER_FIXED_ENVIRONMENT = {
    "CUDA_VISIBLE_DEVICES": "",
    "HIP_VISIBLE_DEVICES": "",
    "HOME": "/nonexistent",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "MKL_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "PATH": "/usr/bin:/bin",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONPYCACHEPREFIX": "/dev/null",
    "ROCR_VISIBLE_DEVICES": "",
    "TZ": "UTC",
}


def reference_validation_bootstrap_path() -> str:
    """Return the canonical checked-out bootstrap path."""

    return os.path.realpath(__file__)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap request is not canonical JSON"
        ) from exc


def _bounded_execution_source_sha256(source: str, *, deadline: float) -> str:
    """Hash one execution source after enforcing its cap before any read."""

    try:
        path_stat = os.lstat(source)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation execution source is unavailable"
        ) from exc
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise _ReferenceValidationBootstrapError(
                "secure validation execution source access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation execution source cannot be opened securely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if (
            os.path.islink(source)
            or not stat.S_ISREG(path_stat.st_mode)
            or path_stat.st_nlink != 1
            or (path_stat.st_dev, path_stat.st_ino, path_stat.st_size)
            != (before.st_dev, before.st_ino, before.st_size)
            or before.st_size < 0
            or before.st_size
            > REFERENCE_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_BYTES
        ):
            raise _ReferenceValidationBootstrapError(
                "validation execution source violates its pre-read file policy"
            )
        digest = hashlib.sha256()
        observed = 0
        while True:
            if time.monotonic() >= deadline:
                raise _ReferenceValidationBootstrapError(
                    "validation execution source deadline expired"
                )
            chunk = os.read(
                descriptor,
                min(
                    1024 * 1024,
                    before.st_size + 1 - observed,
                ),
            )
            if not chunk:
                break
            observed += len(chunk)
            if observed > before.st_size:
                raise _ReferenceValidationBootstrapError(
                    "validation execution source grew while being measured"
                )
            digest.update(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation execution source cannot be measured"
        ) from exc
    finally:
        os.close(descriptor)
    if observed != before.st_size or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise _ReferenceValidationBootstrapError(
            "validation execution source changed while being measured"
        )
    return digest.hexdigest()


def reference_validation_execution_source_sha256() -> str:
    """Bind the bootstrap, dependency helper, and runner source identity."""

    physics_root = os.path.dirname(reference_validation_bootstrap_path())
    source_rows: list[dict[str, str]] = []
    deadline = (
        time.monotonic()
        + REFERENCE_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_WALL_SECONDS
    )
    for relative_path in (
        REFERENCE_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
        REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
        REFERENCE_VALIDATION_SOURCE_IDENTITY_RELATIVE_PATH,
        REFERENCE_VALIDATION_NATIVE_RUNTIME_IDENTITY_RELATIVE_PATH,
        "betelgeuze_engine_v2/physics/reference_validation_runner.py",
    ):
        source = os.path.join(physics_root, os.path.basename(relative_path))
        source_rows.append(
            {
                "path": relative_path,
                "sha256": _bounded_execution_source_sha256(
                    source,
                    deadline=deadline,
                ),
            }
        )
    return hashlib.sha256(
        _canonical_bytes(
            {
                "schema_id": (
                    "betelgeuze.engine_v2_reference_validation_execution_sources/4.0.0"
                ),
                "sources": source_rows,
            }
        )
    ).hexdigest()


def _require_observed_dependency_artifact_rows_before_import(
    repository_root: str,
    dependency_roots: tuple[str, ...],
    request: dict[str, object],
    *,
    deadline: float,
) -> None:
    _require_preflight_time(deadline)
    expected = request.get("expected_dependency_artifact_sha256_rows")
    if not isinstance(expected, dict) or any(
        not isinstance(key, str)
        or not key
        or _require_lower_hex(value, length=64, name=f"dependency {key}") != value
        for key, value in expected.items()
    ):
        raise _ReferenceValidationBootstrapError(
            "bootstrap dependency artifact rows are invalid"
        )
    helper_path = os.path.join(
        repository_root,
        REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "_betelgeuze_reference_validation_dependency_identity",
            helper_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("dependency identity loader is unavailable")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        observed = helper.observed_reference_validation_dependency_artifact_sha256_rows(
            dependency_roots,
            deadline=deadline,
        )
    except Exception as exc:
        raise _ReferenceValidationBootstrapError(
            "bootstrap dependency bytes cannot be measured"
        ) from exc
    if observed != expected:
        raise _ReferenceValidationBootstrapError(
            "bootstrap dependency bytes do not match the signed authorization"
        )


def _require_source_manifest_before_import(
    repository_root: str,
    expected_code_commit_sha: str,
    *,
    deadline: float,
) -> dict[str, object]:
    """Bind every package file to the self-verified signed Git tree."""

    _require_preflight_time(deadline)
    helper_path = os.path.join(
        repository_root,
        REFERENCE_VALIDATION_SOURCE_IDENTITY_RELATIVE_PATH,
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "_betelgeuze_validation_source_identity",
            helper_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("source identity loader is unavailable")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        document = helper.observed_validation_source_manifest_document(
            repository_root,
            expected_code_commit_sha,
            deadline=deadline,
        )
        return helper.require_validation_source_manifest_document(document)
    except Exception as exc:
        raise _ReferenceValidationBootstrapError(
            "bootstrap source bytes do not match the signed Git tree"
        ) from exc


def _require_root_owned_read_only_directory(raw_path: str) -> str:
    if not raw_path or not os.path.isabs(raw_path) or os.pathsep in raw_path:
        raise _ReferenceValidationBootstrapError("bootstrap path is invalid")
    resolved = os.path.realpath(raw_path)
    if resolved != os.path.abspath(raw_path):
        raise _ReferenceValidationBootstrapError("bootstrap path is not canonical")
    current = resolved
    while current != os.path.dirname(current):
        try:
            file_stat = os.lstat(current)
        except OSError as exc:
            raise _ReferenceValidationBootstrapError(
                "bootstrap path is unavailable"
            ) from exc
        if (
            not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise _ReferenceValidationBootstrapError(
                "bootstrap path is not root-owned read-only storage"
            )
        current = os.path.dirname(current)
    return resolved


def _require_preflight_time(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap preflight deadline expired"
        )
    return remaining


def _require_canonical_preflight_deadline(value: object) -> float:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap preflight deadline is invalid"
        )
    try:
        deadline = float.fromhex(value)
    except ValueError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap preflight deadline is invalid"
        ) from exc
    if (
        deadline != deadline
        or deadline in {float("inf"), float("-inf")}
        or deadline.hex() != value
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap preflight deadline is not canonical"
        )
    remaining = _require_preflight_time(deadline)
    if remaining > REFERENCE_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap preflight deadline exceeds its frozen bound"
        )
    return deadline


def _require_immutable_source_snapshot(
    repository_root: str,
    *,
    deadline: float,
) -> str:
    """Reject any package tree the executing uid could replace or rewrite."""

    _require_preflight_time(deadline)
    if os.geteuid() == 0:
        raise _ReferenceValidationBootstrapError(
            "validation source snapshot must execute under a non-root uid"
        )
    resolved_root = _require_root_owned_read_only_directory(repository_root)
    package_root = os.path.join(resolved_root, "betelgeuze_engine_v2")
    _require_root_owned_read_only_directory(package_root)
    entry_count = 0
    pending = [package_root]
    while pending:
        _require_preflight_time(deadline)
        directory = pending.pop()
        try:
            with os.scandir(directory) as stream:
                names: list[str] = []
                for entry in stream:
                    _require_preflight_time(deadline)
                    entry_count += 1
                    if (
                        entry_count
                        > REFERENCE_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_ENTRIES
                    ):
                        raise _ReferenceValidationBootstrapError(
                            "validation source snapshot exceeds its entry bound"
                        )
                    name = entry.name
                    path = os.path.join(directory, name)
                    try:
                        relative = os.path.relpath(path, package_root).encode("utf-8")
                    except UnicodeError as exc:
                        raise _ReferenceValidationBootstrapError(
                            "validation source snapshot path is not canonical UTF-8"
                        ) from exc
                    if (
                        len(relative)
                        > REFERENCE_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_PATH_BYTES
                    ):
                        raise _ReferenceValidationBootstrapError(
                            "validation source snapshot path exceeds its bound"
                        )
                    names.append(name)
        except OSError as exc:
            raise _ReferenceValidationBootstrapError(
                "validation source snapshot cannot be enumerated"
            ) from exc
        child_directories: list[str] = []
        for name in sorted(names):
            path = os.path.join(directory, name)
            try:
                file_stat = os.lstat(path)
            except OSError as exc:
                raise _ReferenceValidationBootstrapError(
                    "validation source snapshot entry is unavailable"
                ) from exc
            if (
                os.path.islink(path)
                or file_stat.st_uid != 0
                or stat.S_IMODE(file_stat.st_mode) & 0o022
            ):
                raise _ReferenceValidationBootstrapError(
                    "validation source snapshot is not root-owned read-only storage"
                )
            if name == "__pycache__" or name.endswith(".pyc"):
                raise _ReferenceValidationBootstrapError(
                    "validation source snapshot contains bytecode cache payload"
                )
            if stat.S_ISDIR(file_stat.st_mode):
                child_directories.append(path)
                continue
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
                raise _ReferenceValidationBootstrapError(
                    "validation source snapshot contains an unsafe entry"
                )
        pending.extend(reversed(child_directories))
    if entry_count == 0:
        raise _ReferenceValidationBootstrapError("validation source snapshot is empty")
    return resolved_root


def _parse_canonical_seed(
    value: object,
    *,
    name: str,
    maximum: int,
) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise _ReferenceValidationBootstrapError(
            f"validation bootstrap {name} must be a canonical ASCII integer"
        )
    parsed = int(value)
    if not 0 <= parsed <= maximum or str(parsed) != value:
        raise _ReferenceValidationBootstrapError(
            f"validation bootstrap {name} is outside the frozen range"
        )
    return parsed


def reference_validation_controlled_inner_environment(
    *,
    preflight_deadline: float | None = None,
) -> dict[str, str]:
    """Return the exact secret-free environment for the seeded inner process."""

    python_hash_seed = _parse_canonical_seed(
        os.environ.get("PYTHONHASHSEED"),
        name="PYTHONHASHSEED",
        maximum=2**32 - 1,
    )
    application_seed = _parse_canonical_seed(
        os.environ.get(REFERENCE_VALIDATION_APPLICATION_SEED_ENV),
        name=REFERENCE_VALIDATION_APPLICATION_SEED_ENV,
        maximum=2**63 - 1,
    )
    if preflight_deadline is None:
        raw_deadline = os.environ.get(
            REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV
        )
        preflight_deadline = (
            _require_canonical_preflight_deadline(raw_deadline)
            if raw_deadline is not None
            else time.monotonic()
            + REFERENCE_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS
        )
    _require_preflight_time(preflight_deadline)
    return {
        **_CONTROLLED_INNER_FIXED_ENVIRONMENT,
        "PYTHONHASHSEED": str(python_hash_seed),
        REFERENCE_VALIDATION_APPLICATION_SEED_ENV: str(application_seed),
        REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV: (
            REFERENCE_VALIDATION_CONTROLLED_INNER_STATE
        ),
        REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV: (
            preflight_deadline.hex()
        ),
    }


def _require_trusted_root_working_directory() -> str:
    try:
        root_stat = os.lstat("/")
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap trusted working directory is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or root_stat.st_uid != 0
        or stat.S_IMODE(root_stat.st_mode) & 0o022
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap trusted working directory is invalid"
        )
    return "/"


def _require_trusted_running_interpreter() -> str:
    raw_executable = sys.executable
    if not raw_executable or not os.path.isabs(raw_executable):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap Python executable is invalid"
        )
    executable = os.path.realpath(raw_executable)
    if executable != os.path.abspath(executable):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap Python executable is not canonical"
        )
    try:
        executable_stat = os.lstat(executable)
        running_stat = os.stat("/proc/self/exe")
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap Python executable is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_uid != 0
        or stat.S_IMODE(executable_stat.st_mode) & 0o022
        or executable_stat.st_nlink != 1
        or (executable_stat.st_dev, executable_stat.st_ino)
        != (running_stat.st_dev, running_stat.st_ino)
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap Python executable is not trusted"
        )
    _require_root_owned_read_only_directory(os.path.dirname(executable))
    _require_trusted_root_working_directory()
    return executable


def _read_process_argv() -> tuple[str, ...]:
    try:
        with open("/proc/self/cmdline", "rb") as stream:
            raw = stream.read(REFERENCE_VALIDATION_BOOTSTRAP_PROCESS_ARGV_MAX_BYTES + 1)
        tokens = raw.rstrip(b"\0").split(b"\0")
        decoded = tuple(token.decode("utf-8") for token in tokens)
    except (OSError, UnicodeDecodeError) as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap process argv is unavailable"
        ) from exc
    if (
        len(raw) > REFERENCE_VALIDATION_BOOTSTRAP_PROCESS_ARGV_MAX_BYTES
        or not raw.endswith(b"\0")
        or not decoded
        or any(not token for token in decoded)
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap process argv is invalid"
        )
    return decoded


def _trusted_standard_library_roots() -> tuple[str, ...]:
    roots: list[str] = []
    for raw_path in sys.path:
        if not raw_path or not os.path.isdir(raw_path):
            continue
        resolved = _require_root_owned_read_only_directory(raw_path)
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise _ReferenceValidationBootstrapError(
            "trusted standard-library roots are unavailable"
        )
    return tuple(roots)


def _trusted_dependency_roots() -> tuple[str, ...]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    configured = sysconfig.get_paths()
    candidates = (
        configured.get("purelib"),
        configured.get("platlib"),
        f"/usr/local/lib/{version}/site-packages",
        f"/usr/local/lib/{version}/dist-packages",
        f"/usr/lib/{version}/site-packages",
        f"/usr/lib/{version}/dist-packages",
        "/usr/lib/python3/dist-packages",
    )
    roots: list[str] = []
    for raw_path in candidates:
        if not isinstance(raw_path, str) or not os.path.isdir(raw_path):
            continue
        try:
            resolved = _require_root_owned_read_only_directory(raw_path)
        except _ReferenceValidationBootstrapError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise _ReferenceValidationBootstrapError(
            "trusted dependency roots are unavailable"
        )
    return tuple(roots)


def _read_bootstrap_request() -> tuple[bytes, dict[str, object]]:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    deadline = _require_canonical_preflight_deadline(
        os.environ.get(REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV)
    )
    try:
        descriptor = input_stream.fileno()
        poller = select.poll()
        poller.register(
            descriptor,
            select.POLLIN | select.POLLHUP | select.POLLERR | select.POLLNVAL,
        )
    except (AttributeError, OSError, ValueError) as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap request cannot be read"
        ) from exc
    raw_buffer = bytearray()
    while len(raw_buffer) <= REFERENCE_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES:
        remaining = _require_preflight_time(deadline)
        timeout_ms = max(1, int(remaining * 1000.0))
        try:
            events = poller.poll(timeout_ms)
        except OSError as exc:
            raise _ReferenceValidationBootstrapError(
                "validation bootstrap request cannot be polled"
            ) from exc
        if not events:
            continue
        if any(mask & select.POLLNVAL for _, mask in events):
            raise _ReferenceValidationBootstrapError(
                "validation bootstrap request descriptor is invalid"
            )
        try:
            chunk = os.read(
                descriptor,
                min(
                    65_536,
                    REFERENCE_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
                    + 1
                    - len(raw_buffer),
                ),
            )
        except OSError as exc:
            raise _ReferenceValidationBootstrapError(
                "validation bootstrap request cannot be read"
            ) from exc
        if not chunk:
            break
        raw_buffer.extend(chunk)
        newline = raw_buffer.find(b"\n")
        if newline >= 0:
            if newline != len(raw_buffer) - 1:
                raise _ReferenceValidationBootstrapError(
                    "validation bootstrap request framing is invalid"
                )
            break
    raw = bytes(raw_buffer)
    if (
        not raw
        or len(raw) > REFERENCE_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap request framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _ReferenceValidationBootstrapError(
                    "validation bootstrap request contains duplicate fields"
                )
            result[key] = value
        return result

    try:
        request = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap request is not ASCII JSON"
        ) from exc
    if (
        not isinstance(request, dict)
        or _canonical_bytes(request) + b"\n" != raw
        or set(request) != _BOOTSTRAP_REQUEST_FIELDS
        or request.get("schema_id") != _REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap request is not the exact canonical schema"
        )
    return raw, request


def _require_lower_hex(value: object, *, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _ReferenceValidationBootstrapError(f"{name} is invalid")
    return value


def _require_external_private_root(
    value: object,
    *,
    repository_root: str,
    name: str,
) -> str:
    if not isinstance(value, str) or not value or not os.path.isabs(value):
        raise _ReferenceValidationBootstrapError(f"{name} is not absolute")
    candidate = os.path.abspath(value)
    resolved = os.path.realpath(value)
    try:
        file_stat = os.lstat(value)
        common = os.path.commonpath((resolved, repository_root))
    except (OSError, ValueError) as exc:
        raise _ReferenceValidationBootstrapError(f"{name} is unavailable") from exc
    if (
        candidate != resolved
        or not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != os.geteuid()
        or stat.S_IMODE(file_stat.st_mode) != 0o700
        or common in {resolved, repository_root}
    ):
        raise _ReferenceValidationBootstrapError(
            f"{name} must be private and outside the checkout"
        )
    return resolved


def _load_bootstrap_operator_keys() -> dict[str, tuple[str, bytes]]:
    trust_store = REFERENCE_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH
    _require_root_owned_read_only_directory(os.path.dirname(trust_store))
    flags = os.O_RDONLY | os.O_NONBLOCK
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise _ReferenceValidationBootstrapError(
                "secure bootstrap trust-store access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(trust_store, flags)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "bootstrap trust store cannot be opened securely"
        ) from exc
    try:
        initial_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(initial_stat.st_mode)
            or initial_stat.st_uid != 0
            or stat.S_IMODE(initial_stat.st_mode) != 0o600
            or initial_stat.st_nlink != 1
            or not 0
            < initial_stat.st_size
            <= REFERENCE_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES
        ):
            raise _ReferenceValidationBootstrapError(
                "bootstrap trust store violates the pre-read file policy"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                descriptor,
                min(
                    8192,
                    initial_stat.st_size + 1 - total,
                ),
            )
            if not chunk:
                break
            total += len(chunk)
            if total > initial_stat.st_size:
                raise _ReferenceValidationBootstrapError(
                    "bootstrap trust store grew while being read"
                )
            chunks.append(chunk)
        final_stat = os.fstat(descriptor)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "bootstrap trust store cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if (
        (initial_stat.st_dev, initial_stat.st_ino, initial_stat.st_size)
        != (final_stat.st_dev, final_stat.st_ino, final_stat.st_size)
        or len(raw) != initial_stat.st_size
        or not raw.endswith(b"\n")
    ):
        raise _ReferenceValidationBootstrapError(
            "bootstrap trust store changed or violates the file policy"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _ReferenceValidationBootstrapError(
                    "bootstrap trust store contains duplicate fields"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _ReferenceValidationBootstrapError(
            "bootstrap trust store is not ASCII JSON"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_id", "reviewer_keys", "operator_keys"}
        or payload.get("schema_id") != _REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID
        or _canonical_bytes(payload) + b"\n" != raw
        or not isinstance(payload.get("operator_keys"), list)
    ):
        raise _ReferenceValidationBootstrapError(
            "bootstrap trust store is not the exact canonical schema"
        )
    result: dict[str, tuple[str, bytes]] = {}
    for row in payload["operator_keys"]:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "operator_identity_sha256",
            "verification_key_hex",
        }:
            raise _ReferenceValidationBootstrapError(
                "bootstrap operator key fields are invalid"
            )
        key_id = row.get("key_id")
        identity = row.get("operator_identity_sha256")
        key_hex = row.get("verification_key_hex")
        if (
            not isinstance(key_id, str)
            or not 1 <= len(key_id) <= 128
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                for character in key_id
            )
            or key_id in result
            or _require_lower_hex(
                identity,
                length=64,
                name="bootstrap operator identity",
            )
            != identity
            or not isinstance(key_hex, str)
            or len(key_hex) < 64
            or len(key_hex) % 2
            or any(character not in "0123456789abcdef" for character in key_hex)
        ):
            raise _ReferenceValidationBootstrapError(
                "bootstrap operator key is invalid"
            )
        result[key_id] = (identity, bytes.fromhex(key_hex))
    if not result:
        raise _ReferenceValidationBootstrapError(
            "bootstrap operator keys are unavailable"
        )
    return result


def _require_bootstrap_authorization_signature(
    request: dict[str, object],
    *,
    expected_commit: str,
    expected_source: str,
) -> None:
    raw_receipt = request.get("authorization_receipt")
    if not isinstance(raw_receipt, dict):
        raise _ReferenceValidationBootstrapError(
            "bootstrap authorization receipt is invalid"
        )
    payload = dict(raw_receipt)
    signature = payload.pop("signature", None)
    if (
        not isinstance(signature, dict)
        or set(signature) != {"algorithm", "key_id", "value"}
        or signature.get("algorithm")
        != _REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM
        or not isinstance(signature.get("key_id"), str)
        or not isinstance(signature.get("value"), str)
    ):
        raise _ReferenceValidationBootstrapError(
            "bootstrap authorization signature is invalid"
        )
    key_id = signature["key_id"]
    operator_keys = _load_bootstrap_operator_keys()
    if key_id not in operator_keys:
        raise _ReferenceValidationBootstrapError(
            "bootstrap authorization key is not trusted"
        )
    operator_identity, verification_key = operator_keys[key_id]
    expected_signature = hmac.new(
        verification_key,
        _canonical_bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature["value"], expected_signature):
        raise _ReferenceValidationBootstrapError(
            "bootstrap authorization signature verification failed"
        )
    receipt_sha256 = payload.pop("receipt_sha256", None)
    expected_nonce = _require_lower_hex(
        request.get("authorization_nonce_sha256"),
        length=64,
        name="bootstrap authorization nonce",
    )
    expected_author = _require_lower_hex(
        request.get("expected_implementation_author_identity_sha256"),
        length=64,
        name="bootstrap implementation author",
    )
    raw_dependencies = request.get("expected_dependency_artifact_sha256_rows")
    if not isinstance(raw_dependencies, dict) or not raw_dependencies:
        raise _ReferenceValidationBootstrapError(
            "bootstrap dependency artifact rows are invalid"
        )
    expected_dependencies: list[dict[str, str]] = []
    for artifact_id, digest in sorted(raw_dependencies.items()):
        if not isinstance(artifact_id, str) or not artifact_id:
            raise _ReferenceValidationBootstrapError(
                "bootstrap dependency artifact rows are invalid"
            )
        expected_dependencies.append(
            {
                "artifact_id": artifact_id,
                "sha256": _require_lower_hex(
                    digest,
                    length=64,
                    name=f"bootstrap dependency {artifact_id}",
                ),
            }
        )
    if (
        receipt_sha256 != hashlib.sha256(_canonical_bytes(payload)).hexdigest()
        or payload.get("authorization_key_id") != key_id
        or payload.get("authorization_operator_identity_sha256") != operator_identity
        or payload.get("authorization_nonce_sha256") != expected_nonce
        or payload.get("implementation_author_identity_sha256") != expected_author
        or payload.get("code_commit_sha") != expected_commit
        or payload.get("runner_source_sha256") != expected_source
        or payload.get("dependency_artifact_sha256_rows") != expected_dependencies
    ):
        raise _ReferenceValidationBootstrapError(
            "bootstrap authorization source binding is invalid"
        )


def _require_signed_clean_checkout_before_import(
    repository_root: str,
    request: dict[str, object],
    *,
    deadline: float,
) -> dict[str, object]:
    _require_preflight_time(deadline)
    _require_root_owned_read_only_directory(repository_root)
    _require_external_private_root(
        request.get("reservation_root"),
        repository_root=repository_root,
        name="reservation root",
    )
    _require_external_private_root(
        request.get("artifact_output_root"),
        repository_root=repository_root,
        name="artifact output root",
    )
    expected_commit = _require_lower_hex(
        request.get("expected_code_commit_sha"),
        length=40,
        name="expected checkout commit",
    )
    expected_source = _require_lower_hex(
        request.get("expected_runner_source_sha256"),
        length=64,
        name="expected validation source",
    )
    _require_bootstrap_authorization_signature(
        request,
        expected_commit=expected_commit,
        expected_source=expected_source,
    )
    git_executable = "/usr/bin/git"
    try:
        git_stat = os.lstat(git_executable)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap Git is unavailable"
        ) from exc
    if (
        os.path.islink(git_executable)
        or not stat.S_ISREG(git_stat.st_mode)
        or git_stat.st_uid != 0
        or stat.S_IMODE(git_stat.st_mode) & 0o022
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap Git is not trusted"
        )
    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }
    common_command = [
        git_executable,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
    ]
    try:
        observed_head = subprocess.run(
            [*common_command, "rev-parse", "--verify", "HEAD"],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=min(10.0, _require_preflight_time(deadline)),
        )
        observed_status = subprocess.run(
            [
                *common_command,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=min(10.0, _require_preflight_time(deadline)),
        )
        observed_replacements = subprocess.run(
            [*common_command, "replace", "--list"],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=min(10.0, _require_preflight_time(deadline)),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap checkout cannot be verified"
        ) from exc
    if (
        observed_head.returncode != 0
        or observed_head.stdout != expected_commit.encode("ascii") + b"\n"
        or observed_status.returncode != 0
        or observed_status.stdout
        or observed_replacements.returncode != 0
        or observed_replacements.stdout
        or reference_validation_execution_source_sha256() != expected_source
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap checkout is not the signed clean source"
        )
    return _require_source_manifest_before_import(
        repository_root,
        expected_commit,
        deadline=deadline,
    )


def _require_canonical_bootstrap_source() -> str:
    expected_bootstrap = reference_validation_bootstrap_path()
    try:
        bootstrap_stat = os.lstat(__file__)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap source is unavailable"
        ) from exc
    if (
        os.path.abspath(__file__) != expected_bootstrap
        or not stat.S_ISREG(bootstrap_stat.st_mode)
        or bootstrap_stat.st_nlink != 1
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap source is not a canonical regular file"
        )
    return expected_bootstrap


def _prepare_isolated_outer_launcher(*, deadline: float) -> tuple[str, str]:
    expected_bootstrap = _require_canonical_bootstrap_source()
    repository_root = os.path.dirname(
        os.path.dirname(os.path.dirname(expected_bootstrap))
    )
    _require_immutable_source_snapshot(repository_root, deadline=deadline)
    expected_tail = (
        *REFERENCE_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    process_argv = _read_process_argv()
    interpreter = _require_trusted_running_interpreter()
    if (
        len(observed_argv) != len(REFERENCE_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV)
        or observed_argv[1:] != expected_tail
        or process_argv != observed_argv
        or not os.path.isabs(observed_argv[0])
        or os.path.realpath(observed_argv[0]) != interpreter
        or sys.argv != [expected_bootstrap]
        or sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap requires the frozen isolated Python command"
        )
    if hasattr(sys, REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap state exists before the controlled inner process"
        )
    return interpreter, expected_bootstrap


def _reexec_seeded_controlled_inner(
    interpreter: str,
    expected_bootstrap: str,
    *,
    deadline: float,
) -> None:
    environment = reference_validation_controlled_inner_environment(
        preflight_deadline=deadline
    )
    command = (
        interpreter,
        *REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    os.chdir(_require_trusted_root_working_directory())
    os.execve(interpreter, command, environment)
    raise _ReferenceValidationBootstrapError(
        "validation bootstrap controlled inner exec unexpectedly returned"
    )


def _prepare_seeded_controlled_import_boundary(
    *,
    deadline: float,
) -> tuple[object, ...]:
    expected_bootstrap = _require_canonical_bootstrap_source()
    interpreter = _require_trusted_running_interpreter()
    expected_argv = (
        interpreter,
        *REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    process_argv = _read_process_argv()
    expected_environment = reference_validation_controlled_inner_environment(
        preflight_deadline=deadline
    )
    python_hash_seed = int(expected_environment["PYTHONHASHSEED"])
    if (
        observed_argv != expected_argv
        or process_argv != expected_argv
        or sys.argv != [expected_bootstrap]
        or os.getcwd() != "/"
        or dict(os.environ) != expected_environment
        or sys.flags.isolated != 0
        or sys.flags.ignore_environment != 0
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.hash_randomization != (0 if python_hash_seed == 0 else 1)
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap requires the frozen seeded inner command"
        )
    if hasattr(sys, REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap state exists before trust verification"
        )

    repository_root = os.path.dirname(
        os.path.dirname(os.path.dirname(expected_bootstrap))
    )
    _require_immutable_source_snapshot(repository_root, deadline=deadline)
    package_root = os.path.join(repository_root, "betelgeuze_engine_v2")
    if not os.path.isdir(package_root):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap checkout is unavailable"
        )
    standard_library_roots = _trusted_standard_library_roots()
    dependency_roots = _trusted_dependency_roots()
    sanitized_path = (
        repository_root,
        *standard_library_roots,
        *dependency_roots,
    )
    sys.path[:] = list(dict.fromkeys(sanitized_path))
    return (
        REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
        expected_bootstrap,
        repository_root,
        dependency_roots,
        tuple(sys.path),
    )


def main() -> int:
    """Establish the import boundary and delegate canonical stdin handling."""

    try:
        stage = os.environ.get(REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV)
        if stage is None:
            preflight_deadline = (
                time.monotonic()
                + REFERENCE_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS
            )
            interpreter, expected_bootstrap = _prepare_isolated_outer_launcher(
                deadline=preflight_deadline
            )
            _reexec_seeded_controlled_inner(
                interpreter,
                expected_bootstrap,
                deadline=preflight_deadline,
            )
            raise _ReferenceValidationBootstrapError(
                "validation bootstrap controlled inner process did not start"
            )
        if stage != REFERENCE_VALIDATION_CONTROLLED_INNER_STATE:
            raise _ReferenceValidationBootstrapError(
                "validation bootstrap stage marker is invalid"
            )
        preflight_deadline = _require_canonical_preflight_deadline(
            os.environ.get(REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV)
        )
        state = _prepare_seeded_controlled_import_boundary(deadline=preflight_deadline)
        raw_request, request = _read_bootstrap_request()
        source_manifest = _require_signed_clean_checkout_before_import(
            state[2],
            request,
            deadline=preflight_deadline,
        )
        _require_observed_dependency_artifact_rows_before_import(
            state[2],
            state[3],
            request,
            deadline=preflight_deadline,
        )
        setattr(
            sys,
            REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE,
            (*state, _canonical_bytes(source_manifest)),
        )
        from betelgeuze_engine_v2.physics import reference_validation_runner

        return reference_validation_runner._main_from_canonical_request(raw_request)
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
