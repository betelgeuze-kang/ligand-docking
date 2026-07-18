"""Stdlib-only bootstrap for the bounded reference-validation process.

This file is executed directly, before importing the Engine v2 package.  The
frozen command uses isolated Python startup with automatic ``site`` loading
disabled, so ``PYTHONPATH``, user-site packages, ``sitecustomize``, and ``.pth``
files cannot run before the validation trust boundary is established.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import subprocess
import sys
import sysconfig


REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_minimization_validation_bootstrap.py"
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
_REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trust_store/1.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "hmac-sha256"
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


class _ReferenceMinimizationValidationBootstrapError(RuntimeError):
    """The interpreter did not establish the frozen import boundary."""


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


def _require_root_owned_read_only_directory(raw_path: str) -> str:
    if not raw_path or not os.path.isabs(raw_path) or os.pathsep in raw_path:
        raise _ReferenceMinimizationValidationBootstrapError("bootstrap path is invalid")
    resolved = os.path.realpath(raw_path)
    if resolved != os.path.abspath(raw_path):
        raise _ReferenceMinimizationValidationBootstrapError("bootstrap path is not canonical")
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
        raw = input_stream.read(REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES + 1)
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
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is unavailable") from exc
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
            if total > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES:
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
        or not 0 < initial_stat.st_size <= (
            REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES
        )
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
        or payload.get("schema_id") != _REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID
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
            or len(key_hex) < 64
            or len(key_hex) % 2
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
    expected_signature = hmac.new(
        verification_key,
        _canonical_bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature["value"], expected_signature):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization signature verification failed"
        )
    receipt_sha256 = payload.pop("receipt_sha256", None)
    if (
        receipt_sha256 != hashlib.sha256(_canonical_bytes(payload)).hexdigest()
        or payload.get("authorization_key_id") != key_id
        or payload.get("authorization_operator_identity_sha256")
        != operator_identity
        or payload.get("code_commit_sha") != expected_commit
        or payload.get("runner_source_sha256") != expected_source
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
    git_executable = "/usr/bin/git"
    try:
        git_stat = os.lstat(git_executable)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Git is unavailable"
        ) from exc
    if (
        os.path.islink(git_executable)
        or not stat.S_ISREG(git_stat.st_mode)
        or git_stat.st_uid != 0
        or stat.S_IMODE(git_stat.st_mode) & 0o022
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
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


def main() -> int:
    """Establish the import boundary and delegate canonical stdin handling."""

    try:
        state = _prepare_isolated_import_boundary()
        raw_request, request = _read_bootstrap_request()
        _require_signed_clean_checkout_before_import(state[1], request)
        setattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, state)
        from betelgeuze_engine_v2.physics import reference_minimization_validation_runner

        return reference_minimization_validation_runner._main_from_canonical_request(raw_request)
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
