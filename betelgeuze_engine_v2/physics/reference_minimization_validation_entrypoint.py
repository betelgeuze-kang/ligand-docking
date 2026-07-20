"""Canonical process entrypoint for one bounded minimization-validation run.

The stdlib-only bootstrap verifies the signed source and dependency boundary
before importing this module.  This module then loads the external reviewer and
operator public keys, re-verifies the run-start chain, evaluates the frozen
fourteen-case matrix, and atomically writes the failure-inclusive result
receipt.  It never opens parameter fitting, scientific validation, benchmark,
product, or customer-execution claims.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Mapping, Sequence

import torch

from .reference_minimization_validation_authorization import (
    MinimizationAuthorizationOperatorTrustAnchor,
)
from .reference_minimization_validation_bootstrap import (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH,
)
from .reference_minimization_validation_dependency_identity import (
    REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
)
from .reference_minimization_validation_result_writer import (
    write_reference_minimization_validation_result_receipt,
)
from .reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
)
from .reference_minimization_validation_run_start import (
    REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
    create_reference_minimization_validation_execution_environment_receipt,
)
from .reference_minimization_validation_runner import (
    run_bounded_cpu_reference_minimization_validation,
)


REFERENCE_MINIMIZATION_VALIDATION_ENTRYPOINT_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_request/1.1.0"
)
REFERENCE_MINIMIZATION_VALIDATION_ENTRYPOINT_RESPONSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_response/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trust_store/1.0.0"
)

_REQUEST_FIELDS = {
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


class ReferenceMinimizationValidationEntrypointError(RuntimeError):
    """The canonical request, external trust, or execution chain is invalid."""


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
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization entrypoint artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_lower_hex(value: object, *, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceMinimizationValidationEntrypointError(f"{name} is invalid")
    return value


def _require_key_id(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or any(character not in _SAFE_KEY_ID_CHARACTERS for character in value)
    ):
        raise ReferenceMinimizationValidationEntrypointError(f"{name} is invalid")
    return value


def _require_string_sequence(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ReferenceMinimizationValidationEntrypointError(
            f"{name} must be a JSON string array"
        )
    return tuple(value)


def _require_dependency_rows(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ReferenceMinimizationValidationEntrypointError(
            "entrypoint dependency rows must be a JSON object"
        )
    rows: dict[str, str] = {}
    for artifact_id, digest in value.items():
        if not isinstance(artifact_id, str) or artifact_id in rows:
            raise ReferenceMinimizationValidationEntrypointError(
                "entrypoint dependency rows are invalid"
            )
        rows[artifact_id] = _require_lower_hex(
            digest,
            length=64,
            name=f"entrypoint dependency {artifact_id}",
        )
    if tuple(sorted(rows)) != (
        REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "entrypoint dependency row schema is invalid"
        )
    return rows


def _validate_trust_directory(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust-store directory policy failed"
        )


def _validate_trust_file(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) != 0o600
        or file_stat.st_nlink != 1
        or not 0
        < file_stat.st_size
        <= REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust-store file policy failed"
        )


def _open_trust_store() -> int:
    required_flags = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY", "O_NONBLOCK")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required_flags)
        or os.open not in os.supports_dir_fd
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "secure minimization trust-store access is unavailable"
        )
    path = Path(REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH)
    if not path.is_absolute() or ".." in path.parts or path.anchor != os.sep:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust-store path is invalid"
        )
    components = tuple(part for part in path.parts[1:] if part not in {"", "."})
    if len(components) < 2:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust-store path is invalid"
        )

    directory_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    current_fd = -1
    file_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        for component in components[:-1]:
            _validate_trust_directory(os.fstat(current_fd))
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        _validate_trust_directory(os.fstat(current_fd))
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=current_fd,
        )
        _validate_trust_file(os.fstat(file_fd))
        result = file_fd
        file_fd = -1
        return result
    except ReferenceMinimizationValidationEntrypointError:
        raise
    except (OSError, ValueError) as exc:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust store cannot be opened securely"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if current_fd >= 0:
            os.close(current_fd)


def _load_trust_store_payload() -> dict[str, Any]:
    descriptor = _open_trust_store()
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
                raise ReferenceMinimizationValidationEntrypointError(
                    "minimization trust store exceeds the size limit"
                )
        after = os.fstat(descriptor)
        _validate_trust_file(after)
    except ReferenceMinimizationValidationEntrypointError:
        raise
    except OSError as exc:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust store cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        or len(raw) != before.st_size
        or not raw.endswith(b"\n")
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust store changed or is not canonically framed"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationEntrypointError(
                    "minimization trust store contains a duplicate field"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust store is not ASCII JSON"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_id", "reviewer_keys", "operator_keys"}
        or payload.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID
        or _canonical_bytes(payload) + b"\n" != raw
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization trust store is not the exact canonical schema"
        )
    return payload


def _verification_key(value: object, *, name: str) -> bytes:
    key_hex = _require_lower_hex(value, length=64, name=name)
    return bytes.fromhex(key_hex)


def _load_trust_anchors() -> tuple[
    dict[str, MinimizationScientificReviewerTrustAnchor],
    dict[str, MinimizationAuthorizationOperatorTrustAnchor],
]:
    payload = _load_trust_store_payload()
    reviewer_rows = payload.get("reviewer_keys")
    operator_rows = payload.get("operator_keys")
    if not isinstance(reviewer_rows, list) or not reviewer_rows:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization reviewer trust anchors are unavailable"
        )
    if not isinstance(operator_rows, list) or not operator_rows:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization operator trust anchors are unavailable"
        )

    reviewers: dict[str, MinimizationScientificReviewerTrustAnchor] = {}
    for row in reviewer_rows:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "reviewer_identity_sha256",
            "verification_key_hex",
        }:
            raise ReferenceMinimizationValidationEntrypointError(
                "minimization reviewer trust-anchor fields are invalid"
            )
        key_id = _require_key_id(row.get("key_id"), name="reviewer key id")
        if key_id in reviewers:
            raise ReferenceMinimizationValidationEntrypointError(
                "minimization reviewer key ids are duplicated"
            )
        reviewers[key_id] = MinimizationScientificReviewerTrustAnchor(
            _require_lower_hex(
                row.get("reviewer_identity_sha256"),
                length=64,
                name="reviewer identity",
            ),
            _verification_key(
                row.get("verification_key_hex"),
                name="reviewer verification key",
            ),
        )

    operators: dict[str, MinimizationAuthorizationOperatorTrustAnchor] = {}
    for row in operator_rows:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "operator_identity_sha256",
            "verification_key_hex",
        }:
            raise ReferenceMinimizationValidationEntrypointError(
                "minimization operator trust-anchor fields are invalid"
            )
        key_id = _require_key_id(row.get("key_id"), name="operator key id")
        if key_id in operators:
            raise ReferenceMinimizationValidationEntrypointError(
                "minimization operator key ids are duplicated"
            )
        operators[key_id] = MinimizationAuthorizationOperatorTrustAnchor(
            _require_lower_hex(
                row.get("operator_identity_sha256"),
                length=64,
                name="operator identity",
            ),
            _verification_key(
                row.get("verification_key_hex"),
                name="operator verification key",
            ),
        )
    return reviewers, operators


def _load_request(raw: bytes) -> dict[str, Any]:
    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization entrypoint request size or framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationEntrypointError(
                    "minimization entrypoint request contains a duplicate field"
                )
            result[key] = value
        return result

    try:
        request = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization entrypoint request is not ASCII JSON"
        ) from exc
    if (
        not isinstance(request, dict)
        or set(request) != _REQUEST_FIELDS
        or request.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_ENTRYPOINT_REQUEST_SCHEMA_ID
        or _canonical_bytes(request) + b"\n" != raw
    ):
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization entrypoint request is not the exact canonical schema"
        )
    for name in ("reservation_root", "artifact_output_root"):
        if not isinstance(request.get(name), str) or not request[name]:
            raise ReferenceMinimizationValidationEntrypointError(
                f"minimization entrypoint {name} must be non-empty text"
            )
    for name in (
        "authorization_receipt",
        "review_attestation",
        "network_isolation_attestation",
    ):
        if not isinstance(request.get(name), dict):
            raise ReferenceMinimizationValidationEntrypointError(
                f"minimization entrypoint {name} must be a JSON object"
            )
    _require_lower_hex(
        request.get("authorization_nonce_sha256"),
        length=64,
        name="authorization nonce",
    )
    _require_lower_hex(
        request.get("expected_implementation_author_identity_sha256"),
        length=64,
        name="implementation author identity",
    )
    _require_lower_hex(
        request.get("expected_code_commit_sha"),
        length=40,
        name="expected code commit",
    )
    _require_lower_hex(
        request.get("expected_runner_source_sha256"),
        length=64,
        name="expected runner source",
    )
    request["expected_dependency_artifact_sha256_rows"] = _require_dependency_rows(
        request.get("expected_dependency_artifact_sha256_rows")
    )
    for name in (
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
        "revoked_network_attestation_sha256s",
    ):
        _require_string_sequence(request.get(name), name=name)
    return request


def _configure_deterministic_runtime() -> None:
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError as exc:
            if torch.get_num_interop_threads() != 1:
                raise ReferenceMinimizationValidationEntrypointError(
                    "Torch interop thread count cannot be frozen"
                ) from exc
    torch.use_deterministic_algorithms(True)
    seed_text = os.environ.get(
        REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV
    )
    if not isinstance(seed_text, str) or not seed_text.isascii() or not seed_text.isdigit():
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization application seed is unavailable"
        )
    seed = int(seed_text)
    if not 0 <= seed <= 2**63 - 1 or str(seed) != seed_text:
        raise ReferenceMinimizationValidationEntrypointError(
            "minimization application seed is outside the frozen range"
        )
    torch.manual_seed(seed)


def _execute_request(request: Mapping[str, Any]) -> dict[str, Any]:
    reviewers, operators = _load_trust_anchors()
    _configure_deterministic_runtime()

    revoked_authorizations = _require_string_sequence(
        request["revoked_authorization_receipt_sha256s"],
        name="revoked authorization receipts",
    )
    revoked_reviews = _require_string_sequence(
        request["revoked_review_attestation_sha256s"],
        name="revoked review attestations",
    )
    conflicting_nonces = _require_string_sequence(
        request["externally_conflicting_nonce_sha256s"],
        name="externally conflicting nonces",
    )
    revoked_network = _require_string_sequence(
        request["revoked_network_attestation_sha256s"],
        name="revoked network attestations",
    )
    dependency_rows = _require_dependency_rows(
        request["expected_dependency_artifact_sha256_rows"]
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
    observation_sha256 = _sha256(observation.to_dict())
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_ENTRYPOINT_RESPONSE_SCHEMA_ID,
        "environment_receipt_sha256": environment.receipt_sha256,
        "observation_sha256": observation_sha256,
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


def _main_from_canonical_request(raw: bytes) -> int:
    """Execute one request already admitted by the stdlib-only bootstrap."""

    output_stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        response = _execute_request(_load_request(raw))
        output_stream.write(_canonical_bytes(response) + b"\n")
        output_stream.flush()
    except Exception:
        return 2
    return 0


def main() -> int:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    try:
        raw = input_stream.read(
            REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES + 1
        )
    except (AttributeError, OSError):
        return 2
    if not isinstance(raw, bytes):
        return 2
    return _main_from_canonical_request(raw)


__all__ = [
    "REFERENCE_MINIMIZATION_VALIDATION_ENTRYPOINT_REQUEST_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_ENTRYPOINT_RESPONSE_SCHEMA_ID",
    "ReferenceMinimizationValidationEntrypointError",
]


if __name__ == "__main__":
    raise SystemExit(main())
