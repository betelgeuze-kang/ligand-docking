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
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import sysconfig
import types


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
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_source_finder"
)
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_source_manifest_sha256"
)
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILES = 4_096
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILE_BYTES = 8 * 1_048_576
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_TOTAL_BYTES = 64 * 1_048_576
_SOURCE_PATH_PRIMITIVES_AVAILABLE = (
    os.name == "posix"
    and all(
        hasattr(os, name)
        for name in ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    )
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
    and os.listdir in os.supports_fd
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
    "betelgeuze.engine_v2_reference_minimization_validation_trust_store/2.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_review_attestation/1.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_NETWORK_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_network_isolation_attestation/1.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_FIELDS = frozenset(
    {
        "schema_id",
        "reviewer_keys",
        "operator_keys",
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
        "revoked_network_attestation_sha256s",
        "superseded_operator_key_ids",
        "superseded_reviewer_key_ids",
        "minimum_authorization_receipt_schema_id",
        "minimum_review_attestation_schema_id",
    }
)
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "ed25519"
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_authorization_receipt/1.0.0"
)
# Schema 1.0.0 is closed: extensions require a new schema identifier so that
# old verifiers cannot silently accept security-relevant signed fields.
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_FIELDS = {
    "schema_id",
    "contract_sha256",
    "artifact_binding_sha256",
    "review_contract_sha256",
    "review_attestation_sha256",
    "implementation_author_identity_sha256",
    "independent_reviewer_identity_sha256",
    "authorization_key_id",
    "authorization_operator_identity_sha256",
    "issued_at_utc",
    "expires_at_utc",
    "authorization_nonce_sha256",
    "code_commit_sha",
    "runner_source_sha256",
    "execution_environment_contract_sha256",
    "result_receipt_contract_sha256",
    "dependency_artifact_sha256_rows",
    "authorization_scope",
    "superseded",
    "revoked",
    "scientifically_validated",
    "claim_safe",
    "receipt_sha256",
    "signature",
}
_REFERENCE_MINIMIZATION_VALIDATION_IGNORED_IMPORT_SUFFIXES = (
    b".py",
    b".pyw",
    b".pyc",
    b".so",
    b".pyd",
    b".dll",
    b".dylib",
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


def _require_sorted_unique_digest_sequence(
    value: object, *, name: str
) -> tuple[str, ...]:
    rows = _require_string_sequence(value, name=name)
    normalized = tuple(
        _require_lower_hex(item, length=64, name=name) for item in rows
    )
    if normalized != tuple(sorted(set(normalized))):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be uniquely sorted"
        )
    return normalized


def _require_sorted_unique_key_id_sequence(
    value: object, *, name: str
) -> tuple[str, ...]:
    rows = _require_string_sequence(value, name=name)
    normalized = tuple(_require_key_id(item, name=name) for item in rows)
    if normalized != tuple(sorted(set(normalized))):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be uniquely sorted"
        )
    return normalized


def _require_embedded_receipt_sha256(
    value: object, *, field_name: str, name: str
) -> str:
    if not isinstance(value, dict):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is invalid")
    return _require_lower_hex(
        value.get(field_name), length=64, name=f"{name} {field_name}"
    )


def _require_trusted_revocation_state(
    request: dict[str, object], trust_payload: dict[str, object]
) -> dict[str, tuple[str, ...]]:
    state = {
        "revoked_authorization_receipt_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("revoked_authorization_receipt_sha256s"),
                name="trusted revoked authorization receipts",
            )
        ),
        "revoked_review_attestation_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("revoked_review_attestation_sha256s"),
                name="trusted revoked review attestations",
            )
        ),
        "externally_conflicting_nonce_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("externally_conflicting_nonce_sha256s"),
                name="trusted externally conflicting nonces",
            )
        ),
        "revoked_network_attestation_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("revoked_network_attestation_sha256s"),
                name="trusted revoked network attestations",
            )
        ),
        "superseded_operator_key_ids": _require_sorted_unique_key_id_sequence(
            trust_payload.get("superseded_operator_key_ids"),
            name="trusted superseded operator keys",
        ),
        "superseded_reviewer_key_ids": _require_sorted_unique_key_id_sequence(
            trust_payload.get("superseded_reviewer_key_ids"),
            name="trusted superseded reviewer keys",
        ),
    }
    for request_field in (
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
        "revoked_network_attestation_sha256s",
    ):
        request_rows = _require_sorted_unique_digest_sequence(
            request.get(request_field), name=f"bootstrap request {request_field}"
        )
        if request_rows != state[request_field]:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap request revocation state does not match the trusted store"
            )
    nonce = _require_lower_hex(
        request.get("authorization_nonce_sha256"),
        length=64,
        name="bootstrap request authorization nonce",
    )
    if nonce in state["externally_conflicting_nonce_sha256s"]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization nonce is externally conflicting"
        )
    review = request.get("review_attestation")
    review_sha256 = _require_embedded_receipt_sha256(
        review, field_name="attestation_sha256", name="bootstrap review attestation"
    )
    if not isinstance(review, dict) or review.get("schema_id") != trust_payload.get(
        "minimum_review_attestation_schema_id"
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap review attestation schema is below the trusted minimum"
        )
    if review_sha256 in state["revoked_review_attestation_sha256s"]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap review attestation is externally revoked"
        )
    network = request.get("network_isolation_attestation")
    network_sha256 = _require_embedded_receipt_sha256(
        network, field_name="attestation_sha256", name="bootstrap network attestation"
    )
    if not isinstance(network, dict) or network.get("schema_id") != (
        _REFERENCE_MINIMIZATION_VALIDATION_NETWORK_ATTESTATION_SCHEMA_ID
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap network attestation schema is unsupported"
        )
    if network_sha256 in state["revoked_network_attestation_sha256s"]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap network attestation is externally revoked"
        )
    return state


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


def _source_stat_signature(file_stat: os.stat_result) -> tuple[int, ...]:
    return (
        int(file_stat.st_dev),
        int(file_stat.st_ino),
        int(file_stat.st_uid),
        int(file_stat.st_gid),
        int(file_stat.st_mode),
        int(file_stat.st_nlink),
        int(file_stat.st_size),
        int(file_stat.st_mtime_ns),
        int(file_stat.st_ctime_ns),
    )


def _require_source_directory_stat(file_stat: os.stat_result) -> None:
    if not stat.S_ISDIR(file_stat.st_mode):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source ancestry contains a non-directory"
        )


def _require_source_regular_file_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_nlink != 1
        or not 0 <= file_stat.st_size
        <= REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILE_BYTES
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source is not a bounded single-link regular file"
        )


def _canonical_source_absolute_path(raw_path: object, *, name: str) -> str:
    try:
        raw = os.fspath(raw_path)
    except TypeError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} is invalid"
        ) from exc
    if (
        not isinstance(raw, str)
        or not raw
        or "\x00" in raw
        or not os.path.isabs(raw)
        or os.path.normpath(raw) != raw
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} is not a canonical absolute path"
        )
    return raw


def _source_lstat_at(directory_fd: int, component: str) -> os.stat_result:
    return os.stat(component, dir_fd=directory_fd, follow_symlinks=False)


def _open_source_child_directory(parent_fd: int, component: str) -> int:
    if (
        not isinstance(component, str)
        or not component
        or component in {".", ".."}
        or os.sep in component
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory component is invalid"
        )
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    path_before = _source_lstat_at(parent_fd, component)
    _require_source_directory_stat(path_before)
    next_fd = -1
    try:
        next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
        opened = os.fstat(next_fd)
        path_after = _source_lstat_at(parent_fd, component)
        _require_source_directory_stat(opened)
        _require_source_directory_stat(path_after)
        if not (
            _source_stat_signature(path_before)
            == _source_stat_signature(opened)
            == _source_stat_signature(path_after)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source directory changed while it was opened"
            )
        result = next_fd
        next_fd = -1
        return result
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be opened securely"
        ) from exc
    finally:
        if next_fd >= 0:
            os.close(next_fd)


def _open_source_absolute_directory(raw_path: object) -> int:
    if not _SOURCE_PATH_PRIMITIVES_AVAILABLE:
        raise _ReferenceMinimizationValidationBootstrapError(
            "secure validation source traversal is unavailable"
        )
    path = _canonical_source_absolute_path(
        raw_path, name="validation source directory"
    )
    components = tuple(part for part in path.split(os.sep) if part)
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    current_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        _require_source_directory_stat(os.fstat(current_fd))
        for component in components:
            next_fd = _open_source_child_directory(current_fd, component)
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be opened securely"
        ) from exc
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _read_source_file_at(directory_fd: int, name: str) -> bytes:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or os.sep in name
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source file name is invalid"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    path_before = _source_lstat_at(directory_fd, name)
    _require_source_regular_file_stat(path_before)
    descriptor = -1
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
        before = os.fstat(descriptor)
        path_opened = _source_lstat_at(directory_fd, name)
        _require_source_regular_file_stat(before)
        _require_source_regular_file_stat(path_opened)
        if not (
            _source_stat_signature(path_before)
            == _source_stat_signature(before)
            == _source_stat_signature(path_opened)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source changed before it was read"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 1_048_576)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILE_BYTES:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source file exceeds its byte bound"
                )
        after = os.fstat(descriptor)
        path_after = _source_lstat_at(directory_fd, name)
        _require_source_regular_file_stat(after)
        _require_source_regular_file_stat(path_after)
        if (
            total != before.st_size
            or _source_stat_signature(before) != _source_stat_signature(after)
            or _source_stat_signature(after) != _source_stat_signature(path_after)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source changed while it was read"
            )
        return b"".join(chunks)
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source cannot be read securely"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _snapshot_source_directory(
    directory_fd: int,
    relative_parts: tuple[str, ...],
    source_by_relative_path: dict[str, bytes],
    counters: list[int],
) -> None:
    before = os.fstat(directory_fd)
    _require_source_directory_stat(before)
    try:
        names_before = tuple(sorted(os.listdir(directory_fd)))
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be enumerated"
        ) from exc
    for name in names_before:
        if not isinstance(name, str) or name in {"", ".", ".."} or os.sep in name:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source directory entry is invalid"
            )
        entry_stat = _source_lstat_at(directory_fd, name)
        if stat.S_ISDIR(entry_stat.st_mode):
            if name == "__pycache__":
                continue
            child_fd = _open_source_child_directory(directory_fd, name)
            try:
                _snapshot_source_directory(
                    child_fd,
                    (*relative_parts, name),
                    source_by_relative_path,
                    counters,
                )
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(entry_stat.st_mode):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source tree contains a symlink or special file"
            )
        if not name.endswith(".py"):
            continue
        payload = _read_source_file_at(directory_fd, name)
        relative_path = "/".join((*relative_parts, name))
        if relative_path in source_by_relative_path:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source path is duplicated"
            )
        source_by_relative_path[relative_path] = payload
        counters[0] += 1
        counters[1] += len(payload)
        if (
            counters[0] > REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILES
            or counters[1] > REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_TOTAL_BYTES
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source snapshot exceeds its bounds"
            )
    try:
        names_after = tuple(sorted(os.listdir(directory_fd)))
        after = os.fstat(directory_fd)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be rechecked"
        ) from exc
    _require_source_directory_stat(after)
    if names_before != names_after or _source_stat_signature(before) != _source_stat_signature(after):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory changed during snapshot"
        )


def _snapshot_reference_minimization_validation_sources(
    repository_root: str,
) -> tuple[str, types.MappingProxyType, tuple[int, ...]]:
    repository = _canonical_source_absolute_path(
        repository_root, name="validation repository root"
    )
    repository_fd = _open_source_absolute_directory(repository)
    package_fd = -1
    try:
        repository_identity = _source_stat_signature(os.fstat(repository_fd))
        package_fd = _open_source_child_directory(
            repository_fd, "betelgeuze_engine_v2"
        )
        sources: dict[str, bytes] = {}
        counters = [0, 0]
        _snapshot_source_directory(
            package_fd,
            ("betelgeuze_engine_v2",),
            sources,
            counters,
        )
    finally:
        if package_fd >= 0:
            os.close(package_fd)
        os.close(repository_fd)
    required_paths = {
        REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
        REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
        "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py",
    }
    if not required_paths.issubset(sources):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source snapshot is missing required execution sources"
        )
    rows = [
        {
            "path": relative_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }
        for relative_path, payload in sorted(sources.items())
    ]
    manifest_sha256 = _sha256(
        {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_SCHEMA_ID,
            "source_count": len(rows),
            "total_source_bytes": sum(int(row["size"]) for row in rows),
            "sources": rows,
        }
    )
    verification_fd = _open_source_absolute_directory(repository)
    try:
        if _source_stat_signature(os.fstat(verification_fd)) != repository_identity:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation repository root changed during source snapshot"
            )
    finally:
        os.close(verification_fd)
    return manifest_sha256, types.MappingProxyType(sources), repository_identity


def _module_record_from_relative_path(
    repository_root: str,
    relative_path: str,
    payload: bytes,
) -> tuple[str, str, bytes, bool]:
    parts = relative_path.split("/")
    if not parts or parts[0] != "betelgeuze_engine_v2" or not parts[-1].endswith(".py"):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source module path is invalid"
        )
    is_package = parts[-1] == "__init__.py"
    module_parts = parts[:-1] if is_package else (*parts[:-1], parts[-1][:-3])
    module_name = ".".join(module_parts)
    if not module_name:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source module name is invalid"
        )
    filename = os.path.join(repository_root, *parts)
    return module_name, filename, payload, is_package


class _VerifiedSourceLoader(importlib.abc.Loader):
    __slots__ = ("_filename", "_fullname", "_is_package", "_payload")

    def __init__(
        self,
        fullname: str,
        filename: str,
        payload: bytes,
        is_package: bool,
    ) -> None:
        self._fullname = fullname
        self._filename = filename
        self._payload = payload
        self._is_package = is_package

    def create_module(self, spec: object) -> None:
        del spec
        return None

    def exec_module(self, module: object) -> None:
        module.__file__ = self._filename
        module.__cached__ = None
        code = compile(
            self._payload,
            self._filename,
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
        exec(code, module.__dict__)

    def get_filename(self, fullname: str) -> str:
        if fullname != self._fullname:
            raise ImportError("verified source loader name mismatch")
        return self._filename

    def get_source(self, fullname: str) -> str:
        if fullname != self._fullname:
            raise ImportError("verified source loader name mismatch")
        return self._payload.decode("utf-8")

    def is_package(self, fullname: str) -> bool:
        if fullname != self._fullname:
            raise ImportError("verified source loader name mismatch")
        return self._is_package


class _VerifiedSourceFinder(importlib.abc.MetaPathFinder):
    __slots__ = (
        "_records",
        "_repository_identity",
        "_repository_root",
        "_sources",
        "finder_identity_sha256",
        "source_manifest_sha256",
    )

    def __init__(
        self,
        repository_root: str,
        source_manifest_sha256: str,
        sources: types.MappingProxyType,
        repository_identity: tuple[int, ...],
    ) -> None:
        records: dict[str, tuple[str, bytes, bool]] = {}
        for relative_path, payload in sources.items():
            module_name, filename, source, is_package = _module_record_from_relative_path(
                repository_root,
                relative_path,
                payload,
            )
            if module_name in records:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source module name is duplicated"
                )
            records[module_name] = (filename, source, is_package)
        self._repository_root = repository_root
        self._repository_identity = repository_identity
        self._sources = sources
        self._records = types.MappingProxyType(records)
        self.source_manifest_sha256 = source_manifest_sha256
        self.finder_identity_sha256 = _sha256(
            {
                "schema_id": (
                    "betelgeuze.engine_v2_reference_minimization_validation_source_finder/"
                    "1.0.0"
                ),
                "source_manifest_sha256": source_manifest_sha256,
                "module_count": len(records),
            }
        )

    @property
    def repository_root(self) -> str:
        return self._repository_root

    def source_bytes_for_relative_path(self, relative_path: str) -> bytes:
        try:
            return self._sources[relative_path]
        except KeyError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "verified source path is unavailable"
            ) from exc

    def verify_repository_binding(self) -> None:
        descriptor = _open_source_absolute_directory(self._repository_root)
        try:
            observed = _source_stat_signature(os.fstat(descriptor))
        finally:
            os.close(descriptor)
        if observed != self._repository_identity:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation repository root changed after source snapshot"
            )

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> object:
        del path, target
        record = self._records.get(fullname)
        if record is None:
            if fullname == "betelgeuze_engine_v2" or fullname.startswith(
                "betelgeuze_engine_v2."
            ):
                raise ModuleNotFoundError(
                    f"{fullname} is absent from the verified source snapshot"
                )
            return None
        filename, payload, is_package = record
        loader = _VerifiedSourceLoader(fullname, filename, payload, is_package)
        spec = importlib.machinery.ModuleSpec(
            fullname,
            loader,
            origin=filename,
            is_package=is_package,
        )
        if is_package:
            spec.submodule_search_locations = [
                f"<verified-source:{self.source_manifest_sha256}>/{fullname.replace('.', '/')}"
            ]
        return spec


def _install_verified_source_finder(
    repository_root: str,
    source_manifest_sha256: str,
    sources: types.MappingProxyType,
    repository_identity: tuple[int, ...],
) -> _VerifiedSourceFinder:
    if any(
        name == "betelgeuze_engine_v2" or name.startswith("betelgeuze_engine_v2.")
        for name in sys.modules
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "Engine v2 was imported before source verification"
        )
    if hasattr(sys, REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE):
        raise _ReferenceMinimizationValidationBootstrapError(
            "verified source finder is already installed"
        )
    finder = _VerifiedSourceFinder(
        repository_root,
        source_manifest_sha256,
        sources,
        repository_identity,
    )
    sys.meta_path.insert(0, finder)
    setattr(sys, REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE, finder)
    setattr(
        sys,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_ATTRIBUTE,
        source_manifest_sha256,
    )
    return finder


def _require_verified_source_finder() -> _VerifiedSourceFinder:
    finder = getattr(
        sys, REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE, None
    )
    manifest = getattr(
        sys, REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_ATTRIBUTE, None
    )
    if (
        not isinstance(finder, _VerifiedSourceFinder)
        or finder not in sys.meta_path
        or manifest != finder.source_manifest_sha256
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "verified source finder is unavailable"
        )
    return finder


def reference_minimization_validation_execution_source_sha256() -> str:
    """Return the package-wide verified source manifest identity."""

    existing = getattr(
        sys, REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_ATTRIBUTE, None
    )
    if (
        isinstance(existing, str)
        and len(existing) == 64
        and all(character in "0123456789abcdef" for character in existing)
    ):
        return existing
    repository_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(reference_minimization_validation_bootstrap_path())
        )
    )
    manifest_sha256, _, _ = _snapshot_reference_minimization_validation_sources(
        repository_root
    )
    return manifest_sha256

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
        or set(payload) != _REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_FIELDS
        or payload.get("schema_id") != _REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID
        or not isinstance(payload.get("reviewer_keys"), list)
        or not isinstance(payload.get("operator_keys"), list)
        or payload.get("minimum_authorization_receipt_schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
        or payload.get("minimum_review_attestation_schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID
        or _canonical_bytes(payload) + b"\n" != raw
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store is not the exact canonical schema"
        )
    reviewer_ids = tuple(
        row.get("key_id") for row in payload["reviewer_keys"] if isinstance(row, dict)
    )
    operator_ids = tuple(
        row.get("key_id") for row in payload["operator_keys"] if isinstance(row, dict)
    )
    if reviewer_ids != tuple(sorted(set(reviewer_ids))) or operator_ids != tuple(
        sorted(set(operator_ids))
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust-store active key ids must be uniquely sorted"
        )
    superseded_reviewers = _require_sorted_unique_key_id_sequence(
        payload.get("superseded_reviewer_key_ids"),
        name="trusted superseded reviewer keys",
    )
    superseded_operators = _require_sorted_unique_key_id_sequence(
        payload.get("superseded_operator_key_ids"),
        name="trusted superseded operator keys",
    )
    if set(reviewer_ids).intersection(superseded_reviewers) or set(
        operator_ids
    ).intersection(superseded_operators):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store contains active superseded keys"
        )
    return payload


def _load_bootstrap_operator_keys(
    payload: dict[str, object] | None = None,
) -> dict[str, tuple[str, bytes]]:
    if payload is None:
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
    trust_payload: dict[str, object],
    trusted_revocation_state: dict[str, tuple[str, ...]],
) -> dict[str, str]:
    raw_receipt = request.get("authorization_receipt")
    if not isinstance(raw_receipt, dict):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization receipt is invalid"
        )
    if (
        set(raw_receipt)
        != _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_FIELDS
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization receipt is not the exact schema"
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
    if key_id in trusted_revocation_state["superseded_operator_key_ids"]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization key is superseded"
        )
    operator_keys = _load_bootstrap_operator_keys(trust_payload)
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
    if receipt_sha256 in trusted_revocation_state[
        "revoked_authorization_receipt_sha256s"
    ]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization receipt is externally revoked"
        )
    if (
        receipt_sha256 != _sha256(payload)
        or payload.get("schema_id")
        != trust_payload.get("minimum_authorization_receipt_schema_id")
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
) -> tuple[dict[str, str], str]:
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
    finder = _require_verified_source_finder()
    if finder.repository_root != repository_root:
        raise _ReferenceMinimizationValidationBootstrapError(
            "verified source finder repository is cross-wired"
        )
    finder.verify_repository_binding()
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
    trust_payload = _load_bootstrap_trust_store_payload()
    trusted_revocation_state = _require_trusted_revocation_state(
        request, trust_payload
    )
    signed_dependency_rows = _require_bootstrap_authorization_signature(
        request,
        expected_commit=expected_commit,
        expected_source=expected_source,
        trust_payload=trust_payload,
        trusted_revocation_state=trusted_revocation_state,
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
        observed_ignored = subprocess.run(
            [
                *common_command,
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                "-z",
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
    finder.verify_repository_binding()
    if (
        observed_head.returncode != 0
        or observed_head.stdout != expected_commit.encode("ascii") + b"\n"
        or observed_status.returncode != 0
        or observed_status.stdout
        or observed_ignored.returncode != 0
        or _ignored_importable_checkout_paths(observed_ignored.stdout)
        or observed_replacements.returncode != 0
        or observed_replacements.stdout
        or reference_minimization_validation_execution_source_sha256() != expected_source
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap checkout is not the signed clean source"
        )
    return signed_dependency_rows, _sha256(trust_payload)


def _ignored_importable_checkout_paths(raw: object) -> tuple[bytes, ...]:
    """Return ignored checkout paths that Python could import or execute."""

    if not isinstance(raw, bytes):
        raise _ReferenceMinimizationValidationBootstrapError(
            "ignored checkout path inventory is invalid"
        )
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise _ReferenceMinimizationValidationBootstrapError(
            "ignored checkout path inventory is invalid"
        )
    paths = tuple(raw[:-1].split(b"\0"))
    if any(not path for path in paths):
        raise _ReferenceMinimizationValidationBootstrapError(
            "ignored checkout path inventory is invalid"
        )
    return tuple(
        path
        for path in paths
        if path.lower().endswith(
            _REFERENCE_MINIMIZATION_VALIDATION_IGNORED_IMPORT_SUFFIXES
        )
    )


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
    finder = _require_verified_source_finder()
    if finder.repository_root != repository_root:
        raise _ReferenceMinimizationValidationBootstrapError(
            "verified dependency helper repository is cross-wired"
        )
    helper_path = os.path.join(
        repository_root,
        REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
    )
    try:
        helper_source = finder.source_bytes_for_relative_path(
            REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH
        )
        helper_name = (
            "_betelgeuze_reference_minimization_validation_dependency_identity"
        )
        loader = _VerifiedSourceLoader(
            helper_name,
            helper_path,
            helper_source,
            False,
        )
        spec = importlib.util.spec_from_loader(
            helper_name,
            loader,
            origin=helper_path,
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
    source_manifest_sha256, sources, repository_identity = (
        _snapshot_reference_minimization_validation_sources(repository_root)
    )
    finder = _install_verified_source_finder(
        repository_root,
        source_manifest_sha256,
        sources,
        repository_identity,
    )
    standard_library_roots = _trusted_standard_library_roots()
    dependency_roots = _trusted_dependency_roots()
    sanitized_path = (
        *standard_library_roots,
        *dependency_roots,
    )
    sys.path[:] = list(dict.fromkeys(sanitized_path))
    if repository_root in sys.path:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation repository remained importable from the live checkout"
        )
    return (
        expected_bootstrap,
        repository_root,
        dependency_roots,
        tuple(sys.path),
        source_manifest_sha256,
        finder.finder_identity_sha256,
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


def _execute_verified_request(
    raw_request: bytes,
    request: dict[str, object],
    *,
    expected_trust_store_sha256: str,
) -> dict[str, object]:
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
    if _sha256(trust_payload) != expected_trust_store_sha256:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store changed after pre-import verification"
        )
    trusted_revocation_state = _require_trusted_revocation_state(
        request, trust_payload
    )
    reviewers, operators = _runtime_trust_anchors(
        trust_payload,
        MinimizationScientificReviewerTrustAnchor,
        MinimizationAuthorizationOperatorTrustAnchor,
    )
    dependency_rows = _require_dependency_artifact_row_mapping(
        request.get("expected_dependency_artifact_sha256_rows"),
        name="runtime request",
    )
    revoked_authorizations = trusted_revocation_state[
        "revoked_authorization_receipt_sha256s"
    ]
    revoked_reviews = trusted_revocation_state[
        "revoked_review_attestation_sha256s"
    ]
    conflicting_nonces = trusted_revocation_state[
        "externally_conflicting_nonce_sha256s"
    ]
    revoked_network = trusted_revocation_state[
        "revoked_network_attestation_sha256s"
    ]
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
    result_receipt_sha256 = _require_lower_hex(
        getattr(result, "receipt_sha256", None),
        length=64,
        name="failure-inclusive result receipt",
    )
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "environment_receipt_sha256": environment.receipt_sha256,
        "observation_sha256": _sha256(observation.to_dict()),
        "result_receipt_sha256": result_receipt_sha256,
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
        signed_dependency_rows, trust_store_sha256 = (
            _require_signed_clean_checkout_before_import(state[1], request)
        )
        _require_observed_dependency_artifact_rows_before_import(
            state[1],
            state[2],
            request,
            signed_expected=signed_dependency_rows,
        )
        _require_verified_source_finder().verify_repository_binding()
        setattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, state)
        response = _execute_verified_request(
            raw_request,
            request,
            expected_trust_store_sha256=trust_store_sha256,
        )
        output_stream.write(_canonical_bytes(response) + b"\n")
        output_stream.flush()
    except Exception:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
