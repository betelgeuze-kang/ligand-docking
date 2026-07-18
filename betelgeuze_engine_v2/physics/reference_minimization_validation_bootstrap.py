"""Stdlib-only bootstrap for the bounded reference-validation process.

This file is executed directly, before importing the Engine v2 package.  An
isolated outer launcher verifies the executable and command, then re-executes
the same interpreter with a minimal environment so ``PYTHONHASHSEED`` is
applied during interpreter initialization.  Automatic ``site`` loading stays
disabled throughout the bootstrap.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import sysconfig


REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_minimization_validation_bootstrap.py"
)
REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH = "betelgeuze_engine_v2/physics/reference_minimization_validation_dependency_identity.py"
REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV = (
    "python",
    "-I",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_MINIMIZATION_VALIDATION_FIXED_RUNPY_LOADER = (
    'import runpy,sys;p=sys.argv.pop();runpy.run_path(p,run_name="__main__")'
)
REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV = (
    "python",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    "-c",
    REFERENCE_MINIMIZATION_VALIDATION_FIXED_RUNPY_LOADER,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE = "seeded-controlled-inner/1"
REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV = (
    "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STAGE"
)
REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV = (
    "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_SEED"
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_bootstrap_state"
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES = 1_048_576
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES = 65_536
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH = (
    "/etc/betelgeuze/engine-v2/reference-minimization-validation-trust-anchors.json"
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trust_store/1.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "ed25519"
_REFERENCE_MINIMIZATION_VALIDATION_OPENSSL_EXECUTABLE = "/usr/bin/openssl"
_ED25519_SUBJECT_PUBLIC_KEY_INFO_PREFIX = bytes.fromhex("302a300506032b6570032100")
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_request/1.1.0"
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


class _ReferenceMinimizationValidationBootstrapError(RuntimeError):
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


def reference_minimization_validation_bootstrap_path() -> str:
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request is not canonical JSON"
        ) from exc


def reference_minimization_validation_execution_source_sha256() -> str:
    """Bind the stdlib bootstrap and runner into one authorization identity."""

    physics_root = os.path.dirname(reference_minimization_validation_bootstrap_path())
    source_rows: list[dict[str, str]] = []
    for relative_path in (
        REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
        REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
        "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py",
    ):
        source = os.path.join(physics_root, os.path.basename(relative_path))
        try:
            file_stat = os.lstat(source)
            with open(source, "rb") as stream:
                payload = stream.read()
        except OSError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation execution source is unavailable"
            ) from exc
        if (
            os.path.islink(source)
            or not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_nlink != 1
            or len(payload) != file_stat.st_size
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation execution source is not a stable regular file"
            )
        source_rows.append(
            {
                "path": relative_path,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return hashlib.sha256(
        _canonical_bytes(
            {
                "schema_id": (
                    "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/"
                    "1.0.0"
                ),
                "sources": source_rows,
            }
        )
    ).hexdigest()


def _require_observed_dependency_artifact_rows_before_import(
    repository_root: str,
    dependency_roots: tuple[str, ...],
    request: dict[str, object],
) -> None:
    expected = request.get("expected_dependency_artifact_sha256_rows")
    if not isinstance(expected, dict) or any(
        not isinstance(key, str)
        or _require_lower_hex(value, length=64, name=f"dependency {key}") != value
        for key, value in expected.items()
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap dependency artifact rows are invalid"
        )
    helper_path = os.path.join(
        repository_root,
        REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "_betelgeuze_reference_minimization_validation_dependency_identity",
            helper_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("dependency identity loader is unavailable")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        observed = helper.observed_reference_minimization_validation_dependency_artifact_sha256_rows(
            dependency_roots
        )
    except Exception as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap dependency bytes cannot be measured"
        ) from exc
    if observed != expected:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap dependency bytes do not match the signed authorization"
        )


def _require_root_owned_read_only_directory(raw_path: str) -> str:
    if not raw_path or not os.path.isabs(raw_path) or os.pathsep in raw_path:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap path is invalid"
        )
    resolved = os.path.realpath(raw_path)
    if resolved != os.path.abspath(raw_path):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap path is not canonical"
        )
    current = resolved
    while current != os.path.dirname(current):
        try:
            file_stat = os.lstat(current)
        except OSError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap path is unavailable"
            ) from exc
        if (
            not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap path is not root-owned read-only storage"
            )
        current = os.path.dirname(current)
    return resolved


def _parse_canonical_seed(
    value: object,
    *,
    name: str,
    maximum: int,
) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} must be a canonical ASCII integer"
        )
    parsed = int(value)
    if not 0 <= parsed <= maximum or str(parsed) != value:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} is outside the frozen range"
        )
    return parsed


def reference_minimization_validation_controlled_inner_environment() -> dict[str, str]:
    """Return the exact secret-free environment for the seeded inner process."""

    python_hash_seed = _parse_canonical_seed(
        os.environ.get("PYTHONHASHSEED"),
        name="PYTHONHASHSEED",
        maximum=2**32 - 1,
    )
    application_seed = _parse_canonical_seed(
        os.environ.get(REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV),
        name=REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
        maximum=2**63 - 1,
    )
    return {
        **_CONTROLLED_INNER_FIXED_ENVIRONMENT,
        "PYTHONHASHSEED": str(python_hash_seed),
        REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV: str(application_seed),
        REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV: (
            REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE
        ),
    }


def _require_trusted_root_working_directory() -> str:
    try:
        root_stat = os.lstat("/")
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap trusted working directory is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or root_stat.st_uid != 0
        or stat.S_IMODE(root_stat.st_mode) & 0o022
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap trusted working directory is invalid"
        )
    return "/"


def _require_trusted_running_interpreter() -> str:
    raw_executable = sys.executable
    if not raw_executable or not os.path.isabs(raw_executable):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Python executable is invalid"
        )
    executable = os.path.realpath(raw_executable)
    if executable != os.path.abspath(executable):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Python executable is not canonical"
        )
    try:
        executable_stat = os.lstat(executable)
        running_stat = os.stat("/proc/self/exe")
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Python executable is not trusted"
        )
    _require_root_owned_read_only_directory(os.path.dirname(executable))
    _require_trusted_root_working_directory()
    return executable


def _read_process_argv() -> tuple[str, ...]:
    try:
        with open("/proc/self/cmdline", "rb") as stream:
            raw = stream.read(65_536)
        tokens = raw.rstrip(b"\0").split(b"\0")
        decoded = tuple(token.decode("utf-8") for token in tokens)
    except (OSError, UnicodeDecodeError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap process argv is unavailable"
        ) from exc
    if not raw.endswith(b"\0") or not decoded or any(not token for token in decoded):
        raise _ReferenceMinimizationValidationBootstrapError(
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
        raise _ReferenceMinimizationValidationBootstrapError(
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
        except _ReferenceMinimizationValidationBootstrapError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise _ReferenceMinimizationValidationBootstrapError(
            "trusted dependency roots are unavailable"
        )
    return tuple(roots)


def _read_bootstrap_request() -> tuple[bytes, dict[str, object]]:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    try:
        raw = input_stream.read(
            REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES + 1
        )
    except (AttributeError, OSError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request cannot be read"
        ) from exc
    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _ReferenceMinimizationValidationBootstrapError(
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request is not ASCII JSON"
        ) from exc
    if (
        not isinstance(request, dict)
        or _canonical_bytes(request) + b"\n" != raw
        or set(request) != _BOOTSTRAP_REQUEST_FIELDS
        or request.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request is not the exact canonical schema"
        )
    return raw, request


def _require_lower_hex(value: object, *, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is invalid")
    return value


def _require_external_private_root(
    value: object,
    *,
    repository_root: str,
    name: str,
) -> str:
    if not isinstance(value, str) or not value or not os.path.isabs(value):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is not absolute")
    candidate = os.path.abspath(value)
    resolved = os.path.realpath(value)
    try:
        file_stat = os.lstat(value)
        common = os.path.commonpath((resolved, repository_root))
    except (OSError, ValueError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} is unavailable"
        ) from exc
    if (
        candidate != resolved
        or not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != os.geteuid()
        or stat.S_IMODE(file_stat.st_mode) != 0o700
        or common in {resolved, repository_root}
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be private and outside the checkout"
        )
    return resolved


def _load_bootstrap_operator_keys() -> dict[str, tuple[str, bytes]]:
    trust_store = REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH
    _require_root_owned_read_only_directory(os.path.dirname(trust_store))
    flags = os.O_RDONLY | os.O_NONBLOCK
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise _ReferenceMinimizationValidationBootstrapError(
                "secure bootstrap trust-store access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(trust_store, flags)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store cannot be opened securely"
        ) from exc
    try:
        initial_stat = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if (
                total
                > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES
            ):
                raise _ReferenceMinimizationValidationBootstrapError(
                    "bootstrap trust store exceeds the size limit"
                )
        final_stat = os.fstat(descriptor)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if (
        not stat.S_ISREG(initial_stat.st_mode)
        or initial_stat.st_uid != 0
        or stat.S_IMODE(initial_stat.st_mode) != 0o600
        or initial_stat.st_nlink != 1
        or not 0
        < initial_stat.st_size
        <= (REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES)
        or (initial_stat.st_dev, initial_stat.st_ino, initial_stat.st_size)
        != (final_stat.st_dev, final_stat.st_ino, final_stat.st_size)
        or len(raw) != initial_stat.st_size
        or not raw.endswith(b"\n")
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store changed or violates the file policy"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _ReferenceMinimizationValidationBootstrapError(
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store is not ASCII JSON"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_id", "reviewer_keys", "operator_keys"}
        or payload.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID
        or _canonical_bytes(payload) + b"\n" != raw
        or not isinstance(payload.get("operator_keys"), list)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store is not the exact canonical schema"
        )
    result: dict[str, tuple[str, bytes]] = {}
    for row in payload["operator_keys"]:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "operator_identity_sha256",
            "verification_key_hex",
        }:
            raise _ReferenceMinimizationValidationBootstrapError(
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
            or len(key_hex) != 64
            or any(character not in "0123456789abcdef" for character in key_hex)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap operator key is invalid"
            )
        result[key_id] = (identity, bytes.fromhex(key_hex))
    if not result:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap operator keys are unavailable"
        )
    return result


def _require_trusted_root_executable(path: str, *, name: str) -> str:
    try:
        file_stat = os.lstat(path)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} is unavailable"
        ) from exc
    if (
        os.path.islink(path)
        or not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} is not trusted"
        )
    return path


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("secure bootstrap memory file write failed")
        remaining = remaining[written:]


def _verify_ed25519_with_trusted_openssl(
    message: bytes,
    signature_hex: object,
    public_key: bytes,
) -> bool:
    if (
        not isinstance(signature_hex, str)
        or len(signature_hex) != 128
        or any(character not in "0123456789abcdef" for character in signature_hex)
        or not isinstance(public_key, bytes)
        or len(public_key) != 32
        or not hasattr(os, "memfd_create")
    ):
        return False
    executable = _require_trusted_root_executable(
        _REFERENCE_MINIMIZATION_VALIDATION_OPENSSL_EXECUTABLE,
        name="OpenSSL",
    )
    message_descriptor = -1
    key_descriptor = -1
    signature_descriptor = -1
    try:
        message_descriptor = os.memfd_create("ed25519-message", flags=0)
        key_descriptor = os.memfd_create("ed25519-public-key", flags=0)
        signature_descriptor = os.memfd_create("ed25519-signature", flags=0)
        _write_all(message_descriptor, message)
        _write_all(
            key_descriptor,
            _ED25519_SUBJECT_PUBLIC_KEY_INFO_PREFIX + public_key,
        )
        _write_all(signature_descriptor, bytes.fromhex(signature_hex))
        os.lseek(message_descriptor, 0, os.SEEK_SET)
        os.lseek(key_descriptor, 0, os.SEEK_SET)
        os.lseek(signature_descriptor, 0, os.SEEK_SET)
        completed = subprocess.run(
            [
                executable,
                "pkeyutl",
                "-verify",
                "-pubin",
                "-keyform",
                "DER",
                "-inkey",
                f"/proc/self/fd/{key_descriptor}",
                "-rawin",
                "-in",
                f"/proc/self/fd/{message_descriptor}",
                "-sigfile",
                f"/proc/self/fd/{signature_descriptor}",
            ],
            env={
                "HOME": "/nonexistent",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(
                message_descriptor,
                key_descriptor,
                signature_descriptor,
            ),
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    finally:
        if signature_descriptor >= 0:
            os.close(signature_descriptor)
        if key_descriptor >= 0:
            os.close(key_descriptor)
        if message_descriptor >= 0:
            os.close(message_descriptor)
    return completed.returncode == 0


def _require_bootstrap_authorization_signature(
    request: dict[str, object],
    *,
    expected_commit: str,
    expected_source: str,
) -> None:
    raw_receipt = request.get("authorization_receipt")
    if not isinstance(raw_receipt, dict):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization receipt is invalid"
        )
    payload = dict(raw_receipt)
    signature = payload.pop("signature", None)
    if (
        not isinstance(signature, dict)
        or set(signature) != {"algorithm", "key_id", "value"}
        or signature.get("algorithm")
        != _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM
        or not isinstance(signature.get("key_id"), str)
        or not isinstance(signature.get("value"), str)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization signature is invalid"
        )
    key_id = signature["key_id"]
    operator_keys = _load_bootstrap_operator_keys()
    if key_id not in operator_keys:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization key is not trusted"
        )
    operator_identity, verification_key = operator_keys[key_id]
    if not _verify_ed25519_with_trusted_openssl(
        _canonical_bytes(payload), signature["value"], verification_key
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap dependency artifact rows are invalid"
        )
    expected_dependencies: list[dict[str, str]] = []
    for artifact_id, digest in sorted(raw_dependencies.items()):
        if not isinstance(artifact_id, str) or not artifact_id:
            raise _ReferenceMinimizationValidationBootstrapError(
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization source binding is invalid"
        )


def _require_signed_clean_checkout_before_import(
    repository_root: str,
    request: dict[str, object],
) -> None:
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
    git_executable = _require_trusted_root_executable("/usr/bin/git", name="Git")
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
            timeout=10,
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
            timeout=10,
        )
        observed_replacements = subprocess.run(
            [*common_command, "replace", "--list"],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap checkout cannot be verified"
        ) from exc
    if (
        observed_head.returncode != 0
        or observed_head.stdout != expected_commit.encode("ascii") + b"\n"
        or observed_status.returncode != 0
        or observed_status.stdout
        or observed_replacements.returncode != 0
        or observed_replacements.stdout
        or reference_minimization_validation_execution_source_sha256()
        != expected_source
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap checkout is not the signed clean source"
        )


def _require_canonical_bootstrap_source() -> str:
    expected_bootstrap = reference_minimization_validation_bootstrap_path()
    try:
        bootstrap_stat = os.lstat(__file__)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap source is unavailable"
        ) from exc
    if (
        os.path.abspath(__file__) != expected_bootstrap
        or not stat.S_ISREG(bootstrap_stat.st_mode)
        or bootstrap_stat.st_nlink != 1
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap source is not a canonical regular file"
        )
    return expected_bootstrap


def _prepare_isolated_outer_launcher() -> tuple[str, str]:
    expected_bootstrap = _require_canonical_bootstrap_source()
    expected_tail = (
        *REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    process_argv = _read_process_argv()
    interpreter = _require_trusted_running_interpreter()
    if (
        len(observed_argv)
        != len(REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV)
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap requires the frozen isolated Python command"
        )
    if hasattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap state exists before the controlled inner process"
        )
    return interpreter, expected_bootstrap


def _reexec_seeded_controlled_inner(
    interpreter: str,
    expected_bootstrap: str,
) -> None:
    environment = reference_minimization_validation_controlled_inner_environment()
    command = (
        interpreter,
        *REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    os.chdir(_require_trusted_root_working_directory())
    os.execve(interpreter, command, environment)
    raise _ReferenceMinimizationValidationBootstrapError(
        "validation bootstrap controlled inner exec unexpectedly returned"
    )


def _prepare_seeded_controlled_import_boundary() -> tuple[object, ...]:
    expected_bootstrap = _require_canonical_bootstrap_source()
    interpreter = _require_trusted_running_interpreter()
    expected_argv = (
        interpreter,
        *REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    process_argv = _read_process_argv()
    expected_environment = (
        reference_minimization_validation_controlled_inner_environment()
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
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap requires the frozen seeded inner command"
        )
    if hasattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap state exists before trust verification"
        )

    repository_root = os.path.dirname(
        os.path.dirname(os.path.dirname(expected_bootstrap))
    )
    package_root = os.path.join(repository_root, "betelgeuze_engine_v2")
    if not os.path.isdir(package_root):
        raise _ReferenceMinimizationValidationBootstrapError(
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
        REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
        expected_bootstrap,
        repository_root,
        dependency_roots,
        tuple(sys.path),
    )


def main() -> int:
    """Establish the import boundary and delegate canonical stdin handling."""

    try:
        stage = os.environ.get(
            REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV
        )
        if stage is None:
            interpreter, expected_bootstrap = _prepare_isolated_outer_launcher()
            _reexec_seeded_controlled_inner(interpreter, expected_bootstrap)
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation bootstrap controlled inner process did not start"
            )
        if stage != REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation bootstrap stage marker is invalid"
            )
        state = _prepare_seeded_controlled_import_boundary()
        raw_request, request = _read_bootstrap_request()
        _require_signed_clean_checkout_before_import(state[2], request)
        _require_observed_dependency_artifact_rows_before_import(
            state[2], state[3], request
        )
        setattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, state)
        from betelgeuze_engine_v2.physics import (
            reference_minimization_validation_runner,
        )

        return reference_minimization_validation_runner._main_from_canonical_request(
            raw_request
        )
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
