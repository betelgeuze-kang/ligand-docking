"""Stdlib-only bootstrap for the bounded minimization-validation process.

This file is executed directly before importing Engine v2 or any third-party
runtime package.  It verifies the signed source, dependency bytes, clean Git
checkout, and external trust-store boundary, then runs one bounded validation
request through the environment receipt, fourteen-case runner, and atomic
failure-inclusive result writer.  Every scientific and product claim remains
closed.
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
REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_minimization_validation_dependency_identity.py"
)
REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV = (
    "python",
    "-I",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_bootstrap_state"
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES = 1_048_576
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES = 65_536
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH = (
    "/etc/betelgeuze/engine-v2/reference-minimization-validation-trust-anchors.json"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_response/1.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trust_store/1.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "ed25519"
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_authorization_receipt/1.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS = (
    "cryptography-distribution",
    "numpy-distribution",
    "openssl-executable",
    "python-runtime-executable",
    "python-standard-library",
    "torch-distribution",
)
_REFERENCE_MINIMIZATION_VALIDATION_OPENSSL_EXECUTABLE = "/usr/bin/openssl"
_ED25519_SUBJECT_PUBLIC_KEY_INFO_PREFIX = bytes.fromhex(
    "302a300506032b6570032100"
)
_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID = (
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
_SAFE_KEY_ID_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


class _ReferenceMinimizationValidationBootstrapError(RuntimeError):
    """The interpreter did not establish the frozen execution boundary."""


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
            "validation bootstrap artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_lower_hex(value: object, *, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is invalid")
    return value


def _require_key_id(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or any(character not in _SAFE_KEY_ID_CHARACTERS for character in value)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is invalid")
    return value


def _require_string_sequence(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be a JSON string array"
        )
    return tuple(value)


def _require_dependency_artifact_row_mapping(
    value: object,
    *,
    name: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} dependency artifact rows are invalid"
        )
    rows: dict[str, str] = {}
    for artifact_id, digest in value.items():
        if not isinstance(artifact_id, str) or artifact_id in rows:
            raise _ReferenceMinimizationValidationBootstrapError(
                f"{name} dependency artifact rows are invalid"
            )
        rows[artifact_id] = _require_lower_hex(
            digest,
            length=64,
            name=f"{name} dependency {artifact_id}",
        )
    if tuple(sorted(rows)) != (
        _REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} dependency artifact row schema is invalid"
        )
    return rows


def _require_signed_dependency_artifact_rows(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise _ReferenceMinimizationValidationBootstrapError(
            "signed authorization dependency artifact rows are invalid"
        )
    rows: dict[str, str] = {}
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"artifact_id", "sha256"}
            or not isinstance(row.get("artifact_id"), str)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "signed authorization dependency artifact rows are invalid"
            )
        artifact_id = row["artifact_id"]
        if artifact_id in rows:
            raise _ReferenceMinimizationValidationBootstrapError(
                "signed authorization dependency artifact rows are duplicated"
            )
        rows[artifact_id] = _require_lower_hex(
            row.get("sha256"),
            length=64,
            name=f"signed authorization dependency {artifact_id}",
        )
    return _require_dependency_artifact_row_mapping(
        rows,
        name="signed authorization",
    )


def reference_minimization_validation_execution_source_sha256() -> str:
    """Bind the stdlib bootstrap, dependency helper, and bounded runner."""

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
    return _sha256(
        {
            "schema_id": (
                "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/"
                "1.0.0"
            ),
            "sources": source_rows,
        }
    )


def _require_root_owned_read_only_directory(raw_path: str) -> str:
    if not raw_path or not os.path.isabs(raw_path) or os.pathsep in raw_path:
        raise _ReferenceMinimizationValidationBootstrapError("bootstrap path is invalid")
    resolved = os.path.realpath(raw_path)
    if resolved != os.path.abspath(raw_path):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap path is not canonical"
        )
    current = resolved
    while True:
        try:
            file_stat = os.lstat(current)
        except OSError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap path is unavailable"
            ) from exc
        if (
            os.path.islink(current)
            or not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap path is not root-owned read-only storage"
            )
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return resolved


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
        != _REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request is not the exact canonical schema"
        )
    return raw, request


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
        or os.path.islink(value)
        or not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != os.geteuid()
        or stat.S_IMODE(file_stat.st_mode) != 0o700
        or common in {resolved, repository_root}
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be private and outside the checkout"
        )
    return resolved


def _open_bootstrap_trust_store() -> int:
    required_flags = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY", "O_NONBLOCK")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required_flags)
        or os.open not in os.supports_dir_fd
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "secure bootstrap trust-store access is unavailable"
        )
    path = REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH
    if not os.path.isabs(path) or os.path.normpath(path) != path:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust-store path is invalid"
        )
    components = tuple(part for part in path.split(os.sep) if part)
    if len(components) < 2:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust-store path is invalid"
        )
    directory_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    current_fd = -1
    file_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        for component in components[:-1]:
            directory_stat = os.fstat(current_fd)
            if (
                not stat.S_ISDIR(directory_stat.st_mode)
                or directory_stat.st_uid != 0
                or stat.S_IMODE(directory_stat.st_mode) & 0o022
            ):
                raise _ReferenceMinimizationValidationBootstrapError(
                    "bootstrap trust-store directory policy failed"
                )
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        directory_stat = os.fstat(current_fd)
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != 0
            or stat.S_IMODE(directory_stat.st_mode) & 0o022
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap trust-store directory policy failed"
            )
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=current_fd,
        )
        file_stat = os.fstat(file_fd)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) != 0o600
            or file_stat.st_nlink != 1
            or not (
                0
                < file_stat.st_size
                <= REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES
            )
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap trust-store file policy failed"
            )
        result = file_fd
        file_fd = -1
        return result
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except (OSError, ValueError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store cannot be opened securely"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if current_fd >= 0:
            os.close(current_fd)


def _load_bootstrap_trust_store_payload() -> dict[str, object]:
    descriptor = _open_bootstrap_trust_store()
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "bootstrap trust store exceeds the size limit"
                )
        after = os.fstat(descriptor)
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != 0
        or stat.S_IMODE(before.st_mode) != 0o600
        or before.st_nlink != 1
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        or len(raw) != before.st_size
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
        or payload.get("schema_id") != _REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID
        or not isinstance(payload.get("reviewer_keys"), list)
        or not isinstance(payload.get("operator_keys"), list)
        or _canonical_bytes(payload) + b"\n" != raw
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store is not the exact canonical schema"
        )
    return payload


def _load_bootstrap_operator_keys() -> dict[str, tuple[str, bytes]]:
    payload = _load_bootstrap_trust_store_payload()
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
        key_id = _require_key_id(row.get("key_id"), name="bootstrap operator key id")
        identity = _require_lower_hex(
            row.get("operator_identity_sha256"),
            length=64,
            name="bootstrap operator identity",
        )
        key_hex = _require_lower_hex(
            row.get("verification_key_hex"),
            length=64,
            name="bootstrap operator verification key",
        )
        if key_id in result:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap operator key ids are duplicated"
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
        or file_stat.st_nlink != 1
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
    descriptors = [-1, -1, -1]
    try:
        descriptors[0] = os.memfd_create("ed25519-message", flags=0)
        descriptors[1] = os.memfd_create("ed25519-public-key", flags=0)
        descriptors[2] = os.memfd_create("ed25519-signature", flags=0)
        _write_all(descriptors[0], message)
        _write_all(
            descriptors[1],
            _ED25519_SUBJECT_PUBLIC_KEY_INFO_PREFIX + public_key,
        )
        _write_all(descriptors[2], bytes.fromhex(signature_hex))
        for descriptor in descriptors:
            os.lseek(descriptor, 0, os.SEEK_SET)
        completed = subprocess.run(
            [
                executable,
                "pkeyutl",
                "-verify",
                "-pubin",
                "-keyform",
                "DER",
                "-inkey",
                f"/proc/self/fd/{descriptors[1]}",
                "-rawin",
                "-in",
                f"/proc/self/fd/{descriptors[0]}",
                "-sigfile",
                f"/proc/self/fd/{descriptors[2]}",
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
            pass_fds=tuple(descriptors),
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    finally:
        for descriptor in reversed(descriptors):
            if descriptor >= 0:
                os.close(descriptor)
    return completed.returncode == 0


def _require_bootstrap_authorization_signature(
    request: dict[str, object],
    *,
    expected_commit: str,
    expected_source: str,
) -> dict[str, str]:
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
        or not isinstance(signature.get("value"), str)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization signature is invalid"
        )
    key_id = _require_key_id(
        signature.get("key_id"),
        name="bootstrap authorization key id",
    )
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
    request_nonce = _require_lower_hex(
        request.get("authorization_nonce_sha256"),
        length=64,
        name="bootstrap request authorization nonce",
    )
    if (
        receipt_sha256 != _sha256(payload)
        or payload.get("schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
        or payload.get("authorization_key_id") != key_id
        or payload.get("authorization_operator_identity_sha256") != operator_identity
        or payload.get("authorization_nonce_sha256") != request_nonce
        or payload.get("code_commit_sha") != expected_commit
        or payload.get("runner_source_sha256") != expected_source
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization source binding is invalid"
        )
    return _require_signed_dependency_artifact_rows(
        payload.get("dependency_artifact_sha256_rows")
    )


def _require_signed_clean_checkout_before_import(
    repository_root: str,
    request: dict[str, object],
) -> dict[str, str]:
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
    signed_dependency_rows = _require_bootstrap_authorization_signature(
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
        or reference_minimization_validation_execution_source_sha256() != expected_source
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap checkout is not the signed clean source"
        )
    return signed_dependency_rows


def _require_observed_dependency_artifact_rows_before_import(
    repository_root: str,
    dependency_roots: tuple[str, ...],
    request: dict[str, object],
    *,
    signed_expected: dict[str, str],
) -> None:
    request_expected = _require_dependency_artifact_row_mapping(
        request.get("expected_dependency_artifact_sha256_rows"),
        name="bootstrap request",
    )
    if request_expected != signed_expected:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap request dependency rows do not match the signed authorization"
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
    if observed != signed_expected:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap dependency bytes do not match the signed authorization"
        )


def _prepare_isolated_import_boundary() -> tuple[object, ...]:
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
    expected_tail = (
        *REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    if (
        len(observed_argv) != len(REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV)
        or observed_argv[1:] != expected_tail
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
        expected_bootstrap,
        repository_root,
        dependency_roots,
        tuple(sys.path),
    )


def _runtime_trust_anchors(
    payload: dict[str, object],
    reviewer_class: object,
    operator_class: object,
) -> tuple[dict[str, object], dict[str, object]]:
    reviewer_rows = payload.get("reviewer_keys")
    operator_rows = payload.get("operator_keys")
    if not isinstance(reviewer_rows, list) or not reviewer_rows:
        raise _ReferenceMinimizationValidationBootstrapError(
            "runtime reviewer trust anchors are unavailable"
        )
    if not isinstance(operator_rows, list) or not operator_rows:
        raise _ReferenceMinimizationValidationBootstrapError(
            "runtime operator trust anchors are unavailable"
        )
    reviewers: dict[str, object] = {}
    for row in reviewer_rows:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "reviewer_identity_sha256",
            "verification_key_hex",
        }:
            raise _ReferenceMinimizationValidationBootstrapError(
                "runtime reviewer trust-anchor fields are invalid"
            )
        key_id = _require_key_id(row.get("key_id"), name="runtime reviewer key id")
        if key_id in reviewers:
            raise _ReferenceMinimizationValidationBootstrapError(
                "runtime reviewer key ids are duplicated"
            )
        reviewers[key_id] = reviewer_class(
            _require_lower_hex(
                row.get("reviewer_identity_sha256"),
                length=64,
                name="runtime reviewer identity",
            ),
            bytes.fromhex(
                _require_lower_hex(
                    row.get("verification_key_hex"),
                    length=64,
                    name="runtime reviewer verification key",
                )
            ),
        )
    operators: dict[str, object] = {}
    for row in operator_rows:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "operator_identity_sha256",
            "verification_key_hex",
        }:
            raise _ReferenceMinimizationValidationBootstrapError(
                "runtime operator trust-anchor fields are invalid"
            )
        key_id = _require_key_id(row.get("key_id"), name="runtime operator key id")
        if key_id in operators:
            raise _ReferenceMinimizationValidationBootstrapError(
                "runtime operator key ids are duplicated"
            )
        operators[key_id] = operator_class(
            _require_lower_hex(
                row.get("operator_identity_sha256"),
                length=64,
                name="runtime operator identity",
            ),
            bytes.fromhex(
                _require_lower_hex(
                    row.get("verification_key_hex"),
                    length=64,
                    name="runtime operator verification key",
                )
            ),
        )
    return reviewers, operators


def _configure_deterministic_torch_runtime(torch_module: object) -> None:
    torch_module.set_num_threads(1)
    if torch_module.get_num_interop_threads() != 1:
        try:
            torch_module.set_num_interop_threads(1)
        except RuntimeError as exc:
            if torch_module.get_num_interop_threads() != 1:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "Torch interop thread count cannot be frozen"
                ) from exc
    torch_module.use_deterministic_algorithms(True)
    seed_text = os.environ.get("BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_SEED")
    if not isinstance(seed_text, str) or not seed_text.isascii() or not seed_text.isdigit():
        raise _ReferenceMinimizationValidationBootstrapError(
            "minimization application seed is unavailable"
        )
    seed = int(seed_text)
    if not 0 <= seed <= 2**63 - 1 or str(seed) != seed_text:
        raise _ReferenceMinimizationValidationBootstrapError(
            "minimization application seed is outside the frozen range"
        )
    torch_module.manual_seed(seed)


def _execute_verified_request(raw_request: bytes, request: dict[str, object]) -> dict[str, object]:
    from betelgeuze_engine_v2.physics import (
        MinimizationAuthorizationOperatorTrustAnchor,
        MinimizationScientificReviewerTrustAnchor,
        create_reference_minimization_validation_execution_environment_receipt,
        run_bounded_cpu_reference_minimization_validation,
        write_reference_minimization_validation_result_receipt,
    )

    del raw_request
    torch_module = sys.modules.get("torch")
    if torch_module is None:
        raise _ReferenceMinimizationValidationBootstrapError(
            "Torch was not imported through the verified Engine v2 package"
        )
    _configure_deterministic_torch_runtime(torch_module)
    trust_payload = _load_bootstrap_trust_store_payload()
    reviewers, operators = _runtime_trust_anchors(
        trust_payload,
        MinimizationScientificReviewerTrustAnchor,
        MinimizationAuthorizationOperatorTrustAnchor,
    )
    dependency_rows = _require_dependency_artifact_row_mapping(
        request.get("expected_dependency_artifact_sha256_rows"),
        name="runtime request",
    )
    revoked_authorizations = _require_string_sequence(
        request.get("revoked_authorization_receipt_sha256s"),
        name="revoked authorization receipts",
    )
    revoked_reviews = _require_string_sequence(
        request.get("revoked_review_attestation_sha256s"),
        name="revoked review attestations",
    )
    conflicting_nonces = _require_string_sequence(
        request.get("externally_conflicting_nonce_sha256s"),
        name="externally conflicting nonces",
    )
    revoked_network = _require_string_sequence(
        request.get("revoked_network_attestation_sha256s"),
        name="revoked network attestations",
    )
    environment = create_reference_minimization_validation_execution_environment_receipt(
        request["reservation_root"],
        request["artifact_output_root"],
        authorization_nonce_sha256=request["authorization_nonce_sha256"],
        authorization_receipt=request["authorization_receipt"],
        review_attestation=request["review_attestation"],
        trusted_reviewer_keys=reviewers,
        expected_implementation_author_identity_sha256=(
            request["expected_implementation_author_identity_sha256"]
        ),
        trusted_operator_keys=operators,
        network_isolation_attestation=request["network_isolation_attestation"],
        expected_code_commit_sha=request["expected_code_commit_sha"],
        expected_runner_source_sha256=request["expected_runner_source_sha256"],
        expected_dependency_artifact_sha256_rows=dependency_rows,
        revoked_receipt_sha256s=revoked_authorizations,
        revoked_review_attestation_sha256s=revoked_reviews,
        externally_conflicting_nonce_sha256s=conflicting_nonces,
        revoked_network_attestation_sha256s=revoked_network,
    )
    observation = run_bounded_cpu_reference_minimization_validation(
        request["artifact_output_root"],
        request["authorization_nonce_sha256"],
        expected_environment_receipt_sha256=environment.receipt_sha256,
        expected_code_commit_sha=request["expected_code_commit_sha"],
        expected_dependency_artifact_sha256_rows=dependency_rows,
    )
    result = write_reference_minimization_validation_result_receipt(
        request["artifact_output_root"],
        request["authorization_nonce_sha256"],
        observation,
        review_attestation=request["review_attestation"],
        authorization_receipt=request["authorization_receipt"],
        trusted_reviewer_keys=reviewers,
        expected_implementation_author_identity_sha256=(
            request["expected_implementation_author_identity_sha256"]
        ),
        trusted_operator_keys=operators,
        revoked_authorization_receipt_sha256s=revoked_authorizations,
        revoked_review_attestation_sha256s=revoked_reviews,
        externally_conflicting_nonce_sha256s=conflicting_nonces,
    )
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "environment_receipt_sha256": environment.receipt_sha256,
        "observation_sha256": _sha256(observation.to_dict()),
        "result_receipt_sha256": result.receipt_sha256,
        "bounded_validation_observation_collected": True,
        "failure_inclusive_result_receipt_written": True,
        "production_validation_results_collected": False,
        "minimization_scientifically_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def main() -> int:
    """Establish the boundary, execute one request, and emit canonical output."""

    output_stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        state = _prepare_isolated_import_boundary()
        raw_request, request = _read_bootstrap_request()
        signed_dependency_rows = _require_signed_clean_checkout_before_import(
            state[1], request
        )
        _require_observed_dependency_artifact_rows_before_import(
            state[1],
            state[2],
            request,
            signed_expected=signed_dependency_rows,
        )
        setattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, state)
        response = _execute_verified_request(raw_request, request)
        output_stream.write(_canonical_bytes(response) + b"\n")
        output_stream.flush()
    except Exception:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
