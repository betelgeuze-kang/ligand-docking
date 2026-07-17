"""Fail-closed run-start re-verification and environment-receipt persistence.

The primitive re-verifies raw signed review and authorization artifacts, reads
the durable one-time nonce record, observes the current CPU process, verifies a
short-lived operator-signed network-isolation attestation, and writes one
canonical execution-environment receipt before any evaluator is imported or
called.  It bundles no key, attestation, receipt, reservation root, artifact
root, runner, result writer, observed physics value, or scientific claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import re
import stat
from typing import Any, Mapping, Sequence

import torch

from .reference_validation_bootstrap import (
    REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
    reference_validation_bootstrap_path,
)
from .reference_validation_artifact_binding import (
    FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from .reference_validation_authorization import (
    FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
    AuthorizationOperatorTrustAnchor,
    ReferenceValidationAuthorizationError,
    ReferenceValidationAuthorizationVerification,
    verify_signed_reference_validation_authorization_receipt,
)
from .reference_validation_nonce_reservation import (
    FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
    ReferenceValidationNonceReservation,
    ReferenceValidationNonceReservationError,
    _open_secure_reservation_root,
    _validate_reservation_file_stat,
    read_reference_validation_nonce_reservation,
)
from .reference_validation_protocol import (
    FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
)
from .reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID,
)
from .reference_validation_review import ScientificReviewerTrustAnchor


REFERENCE_VALIDATION_RUN_START_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_run_start_contract/1.0.0"
)
REFERENCE_VALIDATION_NETWORK_ISOLATION_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_network_isolation_attestation/1.0.0"
)
REFERENCE_VALIDATION_RUN_START_CONTRACT_ID = (
    "cpu_reference_validation_run_start_environment/1.0.0"
)
REFERENCE_VALIDATION_RUN_START_CONTRACT_VERSION = "1.0.0"
REFERENCE_VALIDATION_RUN_START_CONTRACT_FROZEN_AT_UTC = "2026-07-17T13:20:00Z"
REFERENCE_VALIDATION_RUN_START_MAX_RECORD_BYTES = 131_072
REFERENCE_VALIDATION_NETWORK_ATTESTATION_MAX_VALIDITY = timedelta(minutes=5)
REFERENCE_VALIDATION_APPLICATION_SEED_ENV = "BETELGEUZE_REFERENCE_VALIDATION_SEED"
FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256 = (
    "946b939fcf6abd9b12958503bfe8d37e467760c70ae857aaab135c73f3a23658"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,200}$")
_PYTHON_VERSION_RE = re.compile(r"^3\.(?:10|11|12)\.\d+$")
_PYTHON_EXECUTABLE_RE = re.compile(r"^python(?:3(?:\.\d+)?)?$")

_REQUIRED_EMPTY_ENVIRONMENT_VARIABLES = (
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
)
_REQUIRED_ENVIRONMENT_VALUES = (
    ("LANG", "C.UTF-8"),
    ("LC_ALL", "C.UTF-8"),
    ("MKL_NUM_THREADS", "1"),
    ("OMP_NUM_THREADS", "1"),
    ("OPENBLAS_NUM_THREADS", "1"),
    ("PYTHONDONTWRITEBYTECODE", "1"),
    ("PYTHONPYCACHEPREFIX", "/dev/null"),
    ("TZ", "UTC"),
)
_POST_ENVIRONMENT_RECEIPT_BLOCKERS = (
    "validation_runner_not_implemented",
    "result_receipt_writer_not_implemented",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_CURRENT_BLOCKERS = (
    "independent_scientific_review_missing",
    "signed_independent_scientific_review_attestation_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "implementation_author_and_independent_reviewer_separation_not_attested",
    "signed_execution_authorization_receipt_missing",
    "trusted_authorization_operator_key_not_provided",
    "authorization_nonce_not_atomically_reserved",
    "execution_environment_receipt_missing",
    "validation_runner_not_implemented",
    "result_receipt_writer_not_implemented",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceValidationRunStartError(ValueError):
    """Run-start trust, runtime, persistence, or receipt verification failed."""


class ReferenceValidationEnvironmentReceiptAlreadyExistsError(
    ReferenceValidationRunStartError
):
    """The environment-receipt path for the one-time nonce already exists."""


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
        raise ReferenceValidationRunStartError(
            "run-start artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ReferenceValidationRunStartError(f"{name} must be a lowercase SHA-256")
    return value


def _require_git_commit(value: object) -> str:
    if not isinstance(value, str) or not _GIT_COMMIT_RE.fullmatch(value):
        raise ReferenceValidationRunStartError(
            "run-start code commit must be a lowercase 40-character Git SHA"
        )
    return value


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or not _KEY_ID_RE.fullmatch(value):
        raise ReferenceValidationRunStartError("network attestation key id is invalid")
    return value


def _require_key(value: bytes | str) -> bytes:
    key = value.encode("utf-8") if isinstance(value, str) else value
    if not isinstance(key, bytes) or len(key) < 32:
        raise ReferenceValidationRunStartError(
            "network attestation signing key must contain at least 32 bytes"
        )
    return key


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceValidationRunStartError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceValidationRunStartError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceValidationRunStartError(
            f"{name} must be second-resolution UTC"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceValidationRunStartError(
            f"{name} must be second-resolution UTC"
        ) from exc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_dependency_rows(
    rows: Mapping[str, str] | Sequence[Mapping[str, str]],
) -> tuple[tuple[str, str], ...]:
    if isinstance(rows, Mapping):
        candidates: Sequence[Mapping[str, str]] = tuple(
            {"artifact_id": artifact_id, "sha256": digest}
            for artifact_id, digest in rows.items()
        )
    elif isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
        candidates = rows
    else:
        raise ReferenceValidationRunStartError(
            "run-start dependency rows must be a mapping or sequence"
        )
    normalized: list[tuple[str, str]] = []
    for row in candidates:
        if not isinstance(row, Mapping) or set(row) != {"artifact_id", "sha256"}:
            raise ReferenceValidationRunStartError(
                "run-start dependency row fields are invalid"
            )
        artifact_id = row.get("artifact_id")
        if not isinstance(artifact_id, str) or not _ARTIFACT_ID_RE.fullmatch(
            artifact_id
        ):
            raise ReferenceValidationRunStartError(
                "run-start dependency artifact id is invalid"
            )
        normalized.append(
            (
                artifact_id,
                _require_sha256(
                    row.get("sha256"),
                    name=f"run-start dependency {artifact_id}",
                ),
            )
        )
    normalized.sort()
    if not normalized or len({row[0] for row in normalized}) != len(normalized):
        raise ReferenceValidationRunStartError(
            "run-start dependency rows must be non-empty and unique"
        )
    return tuple(normalized)


def reference_validation_artifact_output_root_identity_sha256(
    root: str | os.PathLike[str],
) -> str:
    """Hash an absolute POSIX root spelling without exposing it in a receipt."""

    try:
        candidate = Path(root)
    except (TypeError, ValueError) as exc:
        raise ReferenceValidationRunStartError("artifact output root is invalid") from exc
    if (
        os.name != "posix"
        or not candidate.is_absolute()
        or candidate.anchor != os.sep
        or ".." in candidate.parts
    ):
        raise ReferenceValidationRunStartError(
            "artifact output root must be an absolute POSIX path without '..'"
        )
    spelling = os.fspath(candidate)
    return hashlib.sha256(spelling.encode("utf-8")).hexdigest()


def _network_attestation_projection(
    *,
    authorization_receipt_sha256: str,
    authorization_nonce_sha256: str,
    authorization_operator_identity_sha256: str,
    authorization_key_id: str,
    code_commit_sha: str,
    runner_source_sha256: str,
    artifact_output_root_identity_sha256: str,
    network_namespace_identity_sha256: str,
    observed_at_utc: str,
    expires_at_utc: str,
) -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_VALIDATION_NETWORK_ISOLATION_ATTESTATION_SCHEMA_ID,
        "run_start_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
        ),
        "authorization_receipt_sha256": _require_sha256(
            authorization_receipt_sha256,
            name="network attestation authorization receipt",
        ),
        "authorization_nonce_sha256": _require_sha256(
            authorization_nonce_sha256,
            name="network attestation authorization nonce",
        ),
        "authorization_operator_identity_sha256": _require_sha256(
            authorization_operator_identity_sha256,
            name="network attestation operator identity",
        ),
        "authorization_key_id": _require_key_id(authorization_key_id),
        "code_commit_sha": _require_git_commit(code_commit_sha),
        "runner_source_sha256": _require_sha256(
            runner_source_sha256,
            name="network attestation runner source",
        ),
        "artifact_output_root_identity_sha256": _require_sha256(
            artifact_output_root_identity_sha256,
            name="network attestation artifact output root",
        ),
        "network_namespace_identity_sha256": _require_sha256(
            network_namespace_identity_sha256,
            name="network namespace identity",
        ),
        "observed_at_utc": observed_at_utc,
        "expires_at_utc": expires_at_utc,
        "verification_method": (
            "privileged_operator_linux_network_namespace_attestation"
        ),
        "non_loopback_interfaces_present": False,
        "ipv4_or_ipv6_routes_present": False,
        "dns_resolution_enabled": False,
        "network_access_disabled": True,
        "kernel_network_isolation_enforced_by_this_library": False,
    }


def build_signed_reference_validation_network_isolation_attestation(
    *,
    authorization_receipt_sha256: str,
    authorization_nonce_sha256: str,
    authorization_operator_identity_sha256: str,
    authorization_key_id: str,
    signing_key: bytes | str,
    code_commit_sha: str,
    runner_source_sha256: str,
    artifact_output_root_identity_sha256: str,
    network_namespace_identity_sha256: str,
    observed_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Build short-lived operator evidence; no key is retained or bundled."""

    observed_at_utc = _format_utc(observed_at, name="network observed_at")
    expires_at_utc = _format_utc(expires_at, name="network expires_at")
    observed = _parse_utc(observed_at_utc, name="network observed_at_utc")
    expiry = _parse_utc(expires_at_utc, name="network expires_at_utc")
    if not observed < expiry or expiry - observed > (
        REFERENCE_VALIDATION_NETWORK_ATTESTATION_MAX_VALIDITY
    ):
        raise ReferenceValidationRunStartError(
            "network attestation validity window is invalid"
        )
    projection = _network_attestation_projection(
        authorization_receipt_sha256=authorization_receipt_sha256,
        authorization_nonce_sha256=authorization_nonce_sha256,
        authorization_operator_identity_sha256=(
            authorization_operator_identity_sha256
        ),
        authorization_key_id=authorization_key_id,
        code_commit_sha=code_commit_sha,
        runner_source_sha256=runner_source_sha256,
        artifact_output_root_identity_sha256=(
            artifact_output_root_identity_sha256
        ),
        network_namespace_identity_sha256=network_namespace_identity_sha256,
        observed_at_utc=observed_at_utc,
        expires_at_utc=expires_at_utc,
    )
    payload = dict(projection)
    payload["attestation_sha256"] = _sha256(projection)
    payload["signature"] = {
        "algorithm": REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
        "key_id": authorization_key_id,
        "value": hmac.new(
            _require_key(signing_key),
            _canonical_bytes(payload),
            hashlib.sha256,
        ).hexdigest(),
    }
    return payload


@dataclass(frozen=True, slots=True)
class ReferenceValidationNetworkIsolationVerification:
    attestation_sha256: str
    authorization_operator_identity_sha256: str
    authorization_key_id: str
    network_namespace_identity_sha256: str
    artifact_output_root_identity_sha256: str
    observed_at_utc: str
    expires_at_utc: str

    def __post_init__(self) -> None:
        _require_sha256(self.attestation_sha256, name="network attestation")
        _require_sha256(
            self.authorization_operator_identity_sha256,
            name="network attestation operator",
        )
        _require_key_id(self.authorization_key_id)
        _require_sha256(
            self.network_namespace_identity_sha256,
            name="verified network namespace",
        )
        _require_sha256(
            self.artifact_output_root_identity_sha256,
            name="verified artifact output root",
        )
        if _parse_utc(self.expires_at_utc, name="network expiry") <= _parse_utc(
            self.observed_at_utc,
            name="network observation",
        ):
            raise ReferenceValidationRunStartError(
                "verified network attestation validity is invalid"
            )


def _load_json_artifact(
    source: str | bytes | Mapping[str, Any],
    *,
    name: str,
) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise ReferenceValidationRunStartError(
            f"{name} must be a mapping, string, or bytes"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunStartError(
                    f"{name} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunStartError(f"{name} is not valid JSON") from exc
    if not isinstance(loaded, dict):
        raise ReferenceValidationRunStartError(f"{name} root must be an object")
    return loaded


def verify_signed_reference_validation_network_isolation_attestation(
    source: str | bytes | Mapping[str, Any],
    *,
    trusted_operator_keys: Mapping[str, AuthorizationOperatorTrustAnchor],
    checked_at: datetime,
    expected_authorization: ReferenceValidationAuthorizationVerification,
    expected_artifact_output_root_identity_sha256: str,
    expected_network_namespace_identity_sha256: str,
    revoked_attestation_sha256s: Sequence[str] = (),
) -> ReferenceValidationNetworkIsolationVerification:
    """Verify short-lived network evidence against the exact authorization."""

    payload = _load_json_artifact(source, name="network isolation attestation")
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping) or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ReferenceValidationRunStartError(
            "network isolation attestation signature fields are invalid"
        )
    key_id = _require_key_id(signature.get("key_id"))
    try:
        anchor = trusted_operator_keys[key_id]
    except KeyError as exc:
        raise ReferenceValidationRunStartError(
            "network isolation attestation operator key is not trusted"
        ) from exc
    if signature.get("algorithm") != (
        REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM
    ):
        raise ReferenceValidationRunStartError(
            "network isolation attestation signature algorithm is invalid"
        )
    signature_value = signature.get("value")
    expected_signature = hmac.new(
        anchor.verification_key,
        _canonical_bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    if not isinstance(signature_value, str) or not hmac.compare_digest(
        signature_value,
        expected_signature,
    ):
        raise ReferenceValidationRunStartError(
            "network isolation attestation signature verification failed"
        )
    attestation_sha256 = payload.pop("attestation_sha256", None)
    if attestation_sha256 != _sha256(payload):
        raise ReferenceValidationRunStartError(
            "network isolation attestation SHA-256 verification failed"
        )
    attestation_sha256 = _require_sha256(
        attestation_sha256,
        name="network isolation attestation",
    )
    revoked = {
        _require_sha256(value, name="revoked network isolation attestation")
        for value in revoked_attestation_sha256s
    }
    if attestation_sha256 in revoked:
        raise ReferenceValidationRunStartError(
            "network isolation attestation is externally revoked"
        )
    observed_at = _parse_utc(payload.get("observed_at_utc"), name="network observed_at")
    expires_at = _parse_utc(payload.get("expires_at_utc"), name="network expires_at")
    checked = _parse_utc(_format_utc(checked_at, name="network checked_at"), name="network checked_at")
    if not observed_at <= checked < expires_at:
        raise ReferenceValidationRunStartError(
            "network isolation attestation is not currently valid"
        )
    if expires_at - observed_at > REFERENCE_VALIDATION_NETWORK_ATTESTATION_MAX_VALIDITY:
        raise ReferenceValidationRunStartError(
            "network isolation attestation exceeds the maximum validity"
        )
    expected_projection = _network_attestation_projection(
        authorization_receipt_sha256=expected_authorization.receipt_sha256,
        authorization_nonce_sha256=(
            expected_authorization.authorization_nonce_sha256
        ),
        authorization_operator_identity_sha256=(
            expected_authorization.authorization_operator_identity_sha256
        ),
        authorization_key_id=expected_authorization.authorization_key_id,
        code_commit_sha=expected_authorization.code_commit_sha,
        runner_source_sha256=expected_authorization.runner_source_sha256,
        artifact_output_root_identity_sha256=(
            expected_artifact_output_root_identity_sha256
        ),
        network_namespace_identity_sha256=(
            expected_network_namespace_identity_sha256
        ),
        observed_at_utc=payload["observed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
    )
    if payload != expected_projection:
        raise ReferenceValidationRunStartError(
            "network isolation attestation fields are cross-wired"
        )
    if anchor.operator_identity_sha256 != (
        expected_authorization.authorization_operator_identity_sha256
    ):
        raise ReferenceValidationRunStartError(
            "network isolation attestation operator identity is cross-wired"
        )
    return ReferenceValidationNetworkIsolationVerification(
        attestation_sha256=attestation_sha256,
        authorization_operator_identity_sha256=anchor.operator_identity_sha256,
        authorization_key_id=key_id,
        network_namespace_identity_sha256=(
            expected_network_namespace_identity_sha256
        ),
        artifact_output_root_identity_sha256=(
            expected_artifact_output_root_identity_sha256
        ),
        observed_at_utc=payload["observed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
    )


@dataclass(frozen=True, slots=True)
class _RuntimeObservation:
    operating_system: str
    operating_system_release: str
    machine_architecture: str
    cpu_identity_sha256: str
    python_version: str
    torch_version: str
    numpy_version: str
    environment_variable_rows: tuple[tuple[str, str], ...]
    network_namespace_identity_sha256: str
    command_argv: tuple[str, ...]
    python_hash_seed: int
    application_seed: int
    thread_count_rows: tuple[tuple[str, int], ...]
    torch_deterministic_algorithms_enabled: bool

    def fingerprint_projection(
        self,
        *,
        artifact_output_root_identity_sha256: str,
    ) -> dict[str, Any]:
        return {
            "operating_system": self.operating_system,
            "operating_system_release": self.operating_system_release,
            "machine_architecture": (
                "x86_64"
                if self.machine_architecture in {"x86_64", "amd64"}
                else self.machine_architecture
            ),
            "cpu_identity": self.cpu_identity_sha256,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "numpy_version": self.numpy_version,
            "environment_variable_rows": [
                {"name": name, "value": value}
                for name, value in self.environment_variable_rows
            ],
            "network_namespace_identity_sha256": (
                self.network_namespace_identity_sha256
            ),
            "command_argv": list(self.command_argv),
            "python_hash_seed": self.python_hash_seed,
            "application_seed": self.application_seed,
            "thread_count_rows": [
                {"name": name, "value": value}
                for name, value in self.thread_count_rows
            ],
            "torch_deterministic_algorithms_enabled": (
                self.torch_deterministic_algorithms_enabled
            ),
            "artifact_output_root_identity_sha256": (
                artifact_output_root_identity_sha256
            ),
        }


def _parse_seed(value: object, *, name: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ReferenceValidationRunStartError(f"{name} must be an ASCII integer")
    parsed = int(value)
    if not 0 <= parsed <= 2**63 - 1 or str(parsed) != value:
        raise ReferenceValidationRunStartError(f"{name} is outside the frozen range")
    return parsed


def _read_logical_runner_argv() -> tuple[str, ...]:
    try:
        raw = Path("/proc/self/cmdline").read_bytes()
        tokens = raw.rstrip(b"\0").split(b"\0")
        decoded = tuple(token.decode("utf-8") for token in tokens)
    except (OSError, UnicodeDecodeError) as exc:
        raise ReferenceValidationRunStartError(
            "exact Linux process argv cannot be observed"
        ) from exc
    expected_bootstrap = Path(reference_validation_bootstrap_path())
    try:
        observed_bootstrap = Path(decoded[-1])
        bootstrap_stat = observed_bootstrap.lstat()
        bootstrap_matches = (
            observed_bootstrap.is_absolute()
            and not observed_bootstrap.is_symlink()
            and stat.S_ISREG(bootstrap_stat.st_mode)
            and bootstrap_stat.st_nlink == 1
            and observed_bootstrap.resolve(strict=True) == expected_bootstrap
        )
    except (IndexError, OSError):
        bootstrap_matches = False
    if (
        len(decoded) != len(REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV)
        or not _PYTHON_EXECUTABLE_RE.fullmatch(Path(decoded[0]).name)
        or decoded[1:-1] != REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1]
        or not bootstrap_matches
    ):
        raise ReferenceValidationRunStartError(
            "process argv is not the frozen secret-free validation runner command"
        )
    return REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV


def _observe_current_runtime() -> _RuntimeObservation:
    try:
        import numpy as np
    except ImportError as exc:
        raise ReferenceValidationRunStartError(
            "runtime NumPy dependency is unavailable"
        ) from exc

    environment_names = (
        *_REQUIRED_EMPTY_ENVIRONMENT_VARIABLES,
        *(name for name, _ in _REQUIRED_ENVIRONMENT_VALUES),
        "PYTHONHASHSEED",
        REFERENCE_VALIDATION_APPLICATION_SEED_ENV,
    )
    environment_rows = tuple(
        sorted((name, os.environ.get(name, "<unset>")) for name in environment_names)
    )
    cpu_identity = platform.processor() or platform.machine()
    if not cpu_identity:
        raise ReferenceValidationRunStartError("CPU identity cannot be observed")
    try:
        namespace = os.readlink("/proc/self/ns/net")
    except OSError as exc:
        raise ReferenceValidationRunStartError(
            "Linux network namespace identity cannot be observed"
        ) from exc
    return _RuntimeObservation(
        operating_system=platform.system().lower(),
        operating_system_release=platform.release(),
        machine_architecture=platform.machine().lower(),
        cpu_identity_sha256=hashlib.sha256(
            cpu_identity.encode("utf-8")
        ).hexdigest(),
        python_version=platform.python_version(),
        torch_version=str(torch.__version__).split("+", 1)[0],
        numpy_version=str(np.__version__),
        environment_variable_rows=environment_rows,
        network_namespace_identity_sha256=hashlib.sha256(
            namespace.encode("utf-8")
        ).hexdigest(),
        command_argv=_read_logical_runner_argv(),
        python_hash_seed=_parse_seed(
            os.environ.get("PYTHONHASHSEED"),
            name="PYTHONHASHSEED",
        ),
        application_seed=_parse_seed(
            os.environ.get(REFERENCE_VALIDATION_APPLICATION_SEED_ENV),
            name=REFERENCE_VALIDATION_APPLICATION_SEED_ENV,
        ),
        thread_count_rows=(
            (
                "mkl_num_threads",
                _parse_seed(
                    os.environ.get("MKL_NUM_THREADS"),
                    name="MKL_NUM_THREADS",
                ),
            ),
            (
                "omp_num_threads",
                _parse_seed(
                    os.environ.get("OMP_NUM_THREADS"),
                    name="OMP_NUM_THREADS",
                ),
            ),
            (
                "openblas_num_threads",
                _parse_seed(
                    os.environ.get("OPENBLAS_NUM_THREADS"),
                    name="OPENBLAS_NUM_THREADS",
                ),
            ),
            ("torch_num_interop_threads", int(torch.get_num_interop_threads())),
            ("torch_num_threads", int(torch.get_num_threads())),
        ),
        torch_deterministic_algorithms_enabled=bool(
            torch.are_deterministic_algorithms_enabled()
        ),
    )


def _require_runtime_observation(observation: _RuntimeObservation) -> None:
    if not isinstance(observation, _RuntimeObservation):
        raise ReferenceValidationRunStartError("runtime observation type is invalid")
    if observation.operating_system != "linux":
        raise ReferenceValidationRunStartError("validation runtime must be Linux")
    if observation.machine_architecture not in {"x86_64", "amd64"}:
        raise ReferenceValidationRunStartError(
            "validation runtime architecture must be x86_64"
        )
    if not observation.operating_system_release:
        raise ReferenceValidationRunStartError("Linux release must be observed")
    _require_sha256(observation.cpu_identity_sha256, name="runtime CPU identity")
    if not _PYTHON_VERSION_RE.fullmatch(observation.python_version):
        raise ReferenceValidationRunStartError(
            "runtime Python patch version is outside 3.10-3.12"
        )
    if observation.torch_version != "2.6.0":
        raise ReferenceValidationRunStartError("runtime Torch version must be 2.6.0")
    if observation.numpy_version != "1.26.4":
        raise ReferenceValidationRunStartError("runtime NumPy version must be 1.26.4")
    environment = dict(observation.environment_variable_rows)
    if len(environment) != len(observation.environment_variable_rows):
        raise ReferenceValidationRunStartError(
            "runtime environment variable rows must be unique"
        )
    for name in _REQUIRED_EMPTY_ENVIRONMENT_VARIABLES:
        if environment.get(name) != "":
            raise ReferenceValidationRunStartError(
                f"runtime environment variable {name} must be present and empty"
            )
    for name, expected in _REQUIRED_ENVIRONMENT_VALUES:
        if environment.get(name) != expected:
            raise ReferenceValidationRunStartError(
                f"runtime environment variable {name} is not frozen"
            )
    if environment.get("PYTHONHASHSEED") != str(observation.python_hash_seed):
        raise ReferenceValidationRunStartError("PYTHONHASHSEED is cross-wired")
    if environment.get(REFERENCE_VALIDATION_APPLICATION_SEED_ENV) != str(
        observation.application_seed
    ):
        raise ReferenceValidationRunStartError("application seed is cross-wired")
    if observation.command_argv != REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV:
        raise ReferenceValidationRunStartError("logical runner argv is cross-wired")
    if observation.thread_count_rows != (
        ("mkl_num_threads", 1),
        ("omp_num_threads", 1),
        ("openblas_num_threads", 1),
        ("torch_num_interop_threads", 1),
        ("torch_num_threads", 1),
    ):
        raise ReferenceValidationRunStartError(
            "runtime thread counts do not match the frozen single-thread lane"
        )
    if not observation.torch_deterministic_algorithms_enabled:
        raise ReferenceValidationRunStartError(
            "Torch deterministic algorithms must be enabled"
        )
    _require_sha256(
        observation.network_namespace_identity_sha256,
        name="runtime network namespace",
    )


def _closed_claim_policy() -> dict[str, bool]:
    return {
        "run_start_environment_primitive_implemented": True,
        "production_execution_environment_receipt_present": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "force_or_energy_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_VALIDATION_RUN_START_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_VALIDATION_RUN_START_CONTRACT_ID,
        "contract_version": REFERENCE_VALIDATION_RUN_START_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_VALIDATION_RUN_START_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "scope": "pre_evaluation_dependency_and_environment_reverification",
            "contract_and_primitive_only": True,
            "production_environment_receipt_present": False,
            "validation_execution_authorized": False,
            "result_collection_performed": False,
        },
        "dependencies": {
            "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
            "artifact_binding_sha256": (
                FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256
            ),
            "authorization_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
            ),
            "nonce_reservation_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
            ),
            "execution_environment_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            ),
            "result_receipt_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            "raw_signed_review_and_authorization_reverification_required": True,
            "durable_nonce_record_reverification_required": True,
            "exact_code_runner_and_dependency_rows_required": True,
        },
        "runtime_observation": {
            "linux_x86_64_only": True,
            "python_patch_version_observed": True,
            "supported_python_minors": ["3.10", "3.11", "3.12"],
            "torch_version": "2.6.0",
            "numpy_version": "1.26.4",
            "cpu_identity_stored_as_sha256_only": True,
            "gpu_visibility_variables_present_and_empty": True,
            "locale_timezone_and_thread_environment_exact": True,
            "source_only_python_import_environment_exact": True,
            "ignored_timestamp_bytecode_cache_execution_allowed": False,
            "isolated_python_startup_required": True,
            "automatic_site_initialization_allowed": False,
            "python_import_path_environment_ignored": True,
            "user_site_packages_allowed": False,
            "python_hash_and_application_seeds_exact": True,
            "torch_single_thread_and_deterministic_algorithms_required": True,
            "logical_runner_argv": list(REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV),
            "arbitrary_or_secret_bearing_argv_allowed": False,
        },
        "network_isolation": {
            "operator_signed_short_lived_attestation_required": True,
            "maximum_attestation_validity_seconds": int(
                REFERENCE_VALIDATION_NETWORK_ATTESTATION_MAX_VALIDITY.total_seconds()
            ),
            "exact_process_network_namespace_identity_required": True,
            "non_loopback_interfaces_routes_and_dns_must_be_absent": True,
            "kernel_network_isolation_enforced_by_this_library": False,
            "operator_attestation_is_not_customer_execution_qualification": True,
        },
        "persistence": {
            "caller_provisioned_private_posix_artifact_root_required": True,
            "artifact_root_path_stored_as_sha256_only": True,
            "receipt_filename": "<authorization_nonce_sha256>.environment.json",
            "exclusive_nofollow_create_and_file_directory_fsync_required": True,
            "receipt_mode": "0600",
            "duplicate_or_poisoned_path_fails_closed": True,
            "release_or_delete_api_provided": False,
            "same_uid_replacement_resistance_established": False,
        },
        "current_state": {
            "run_start_environment_primitive_implemented": True,
            "production_review_attestation_present": False,
            "production_authorization_receipt_present": False,
            "production_nonce_reserved": False,
            "production_environment_receipt_present": False,
            "validation_runner_implemented": False,
            "result_receipt_writer_implemented": False,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
        },
        "claim_policy": _closed_claim_policy(),
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_validation_run_start_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
    ):
        raise ReferenceValidationRunStartError(
            "frozen run-start environment contract SHA-256 drifted"
        )
    return document


def require_reference_validation_run_start_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationRunStartError(
            "run-start contract document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = reference_validation_run_start_contract_document()
    if observed != expected:
        raise ReferenceValidationRunStartError(
            "run-start contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceValidationExecutionEnvironmentReceipt:
    receipt_sha256: str
    nonce_reservation_record_sha256: str
    authorization_receipt_sha256: str
    review_attestation_sha256: str
    implementation_author_identity_sha256: str
    independent_reviewer_identity_sha256: str
    authorization_operator_identity_sha256: str
    authorization_nonce_sha256: str
    code_commit_sha: str
    runner_source_sha256: str
    dependency_artifact_sha256_rows: tuple[tuple[str, str], ...]
    operating_system_release: str
    machine_architecture: str
    cpu_identity_sha256: str
    python_version: str
    torch_version: str
    numpy_version: str
    environment_variable_rows: tuple[tuple[str, str], ...]
    network_isolation_attestation_sha256: str
    network_namespace_identity_sha256: str
    command_argv: tuple[str, ...]
    python_hash_seed: int
    application_seed: int
    thread_count_rows: tuple[tuple[str, int], ...]
    artifact_output_root_identity_sha256: str
    environment_fingerprint_sha256: str
    started_at_utc: str
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("environment receipt", self.receipt_sha256),
            ("nonce reservation record", self.nonce_reservation_record_sha256),
            ("authorization receipt", self.authorization_receipt_sha256),
            ("review attestation", self.review_attestation_sha256),
            ("implementation author", self.implementation_author_identity_sha256),
            ("independent reviewer", self.independent_reviewer_identity_sha256),
            ("authorization operator", self.authorization_operator_identity_sha256),
            ("authorization nonce", self.authorization_nonce_sha256),
            ("runner source", self.runner_source_sha256),
            ("CPU identity", self.cpu_identity_sha256),
            ("network attestation", self.network_isolation_attestation_sha256),
            ("network namespace", self.network_namespace_identity_sha256),
            ("artifact output root", self.artifact_output_root_identity_sha256),
            ("environment fingerprint", self.environment_fingerprint_sha256),
        ):
            _require_sha256(value, name=name)
        _require_git_commit(self.code_commit_sha)
        if len(
            {
                self.implementation_author_identity_sha256,
                self.independent_reviewer_identity_sha256,
                self.authorization_operator_identity_sha256,
            }
        ) != 3:
            raise ReferenceValidationRunStartError(
                "environment receipt identities must be pairwise distinct"
            )
        if _normalize_dependency_rows(
            [
                {"artifact_id": artifact_id, "sha256": digest}
                for artifact_id, digest in self.dependency_artifact_sha256_rows
            ]
        ) != self.dependency_artifact_sha256_rows:
            raise ReferenceValidationRunStartError(
                "environment receipt dependency rows are not canonical"
            )
        if not self.operating_system_release or self.machine_architecture != "x86_64":
            raise ReferenceValidationRunStartError(
                "environment receipt Linux runtime identity is invalid"
            )
        if not _PYTHON_VERSION_RE.fullmatch(self.python_version):
            raise ReferenceValidationRunStartError(
                "environment receipt Python version is invalid"
            )
        if self.torch_version != "2.6.0" or self.numpy_version != "1.26.4":
            raise ReferenceValidationRunStartError(
                "environment receipt dependency versions drifted"
            )
        environment = dict(self.environment_variable_rows)
        if (
            len(environment) != len(self.environment_variable_rows)
            or tuple(sorted(self.environment_variable_rows))
            != self.environment_variable_rows
        ):
            raise ReferenceValidationRunStartError(
                "environment receipt variable rows must be canonical and unique"
            )
        for name in _REQUIRED_EMPTY_ENVIRONMENT_VARIABLES:
            if environment.get(name) != "":
                raise ReferenceValidationRunStartError(
                    "environment receipt GPU visibility variables must be empty"
                )
        for name, expected in _REQUIRED_ENVIRONMENT_VALUES:
            if environment.get(name) != expected:
                raise ReferenceValidationRunStartError(
                    "environment receipt frozen variables drifted"
                )
        if (
            type(self.python_hash_seed) is not int
            or type(self.application_seed) is not int
            or not 0 <= self.python_hash_seed <= 2**63 - 1
            or not 0 <= self.application_seed <= 2**63 - 1
            or environment.get("PYTHONHASHSEED") != str(self.python_hash_seed)
            or environment.get(REFERENCE_VALIDATION_APPLICATION_SEED_ENV)
            != str(self.application_seed)
        ):
            raise ReferenceValidationRunStartError(
                "environment receipt seeds are invalid or cross-wired"
            )
        if self.command_argv != REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV:
            raise ReferenceValidationRunStartError(
                "environment receipt runner argv drifted"
            )
        if self.thread_count_rows != (
            ("mkl_num_threads", 1),
            ("omp_num_threads", 1),
            ("openblas_num_threads", 1),
            ("torch_num_interop_threads", 1),
            ("torch_num_threads", 1),
        ):
            raise ReferenceValidationRunStartError(
                "environment receipt thread counts drifted"
            )
        if self.blockers != _POST_ENVIRONMENT_RECEIPT_BLOCKERS:
            raise ReferenceValidationRunStartError(
                "environment receipt downstream blockers drifted"
            )
        _parse_utc(self.started_at_utc, name="environment receipt started_at")
        reconstructed = _RuntimeObservation(
            operating_system="linux",
            operating_system_release=self.operating_system_release,
            machine_architecture=self.machine_architecture,
            cpu_identity_sha256=self.cpu_identity_sha256,
            python_version=self.python_version,
            torch_version=self.torch_version,
            numpy_version=self.numpy_version,
            environment_variable_rows=self.environment_variable_rows,
            network_namespace_identity_sha256=(
                self.network_namespace_identity_sha256
            ),
            command_argv=self.command_argv,
            python_hash_seed=self.python_hash_seed,
            application_seed=self.application_seed,
            thread_count_rows=self.thread_count_rows,
            torch_deterministic_algorithms_enabled=True,
        )
        if self.environment_fingerprint_sha256 != _sha256(
            reconstructed.fingerprint_projection(
                artifact_output_root_identity_sha256=(
                    self.artifact_output_root_identity_sha256
                )
            )
        ):
            raise ReferenceValidationRunStartError(
                "environment receipt fingerprint is cross-wired"
            )

    @property
    def eligible_for_bounded_validation_runner(self) -> bool:
        return True

    def projection(self) -> dict[str, Any]:
        return {
            "schema_id": REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID,
            "run_start_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
            ),
            "environment_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            ),
            "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
            "artifact_binding_sha256": (
                FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256
            ),
            "authorization_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
            ),
            "nonce_reservation_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
            ),
            "nonce_reservation_record_sha256": self.nonce_reservation_record_sha256,
            "authorization_receipt_sha256": self.authorization_receipt_sha256,
            "review_attestation_sha256": self.review_attestation_sha256,
            "implementation_author_identity_sha256": (
                self.implementation_author_identity_sha256
            ),
            "independent_reviewer_identity_sha256": (
                self.independent_reviewer_identity_sha256
            ),
            "authorization_operator_identity_sha256": (
                self.authorization_operator_identity_sha256
            ),
            "authorization_nonce_sha256": self.authorization_nonce_sha256,
            "code_commit_sha": self.code_commit_sha,
            "runner_source_sha256": self.runner_source_sha256,
            "dependency_artifact_sha256_rows": [
                {"artifact_id": artifact_id, "sha256": digest}
                for artifact_id, digest in self.dependency_artifact_sha256_rows
            ],
            "operating_system_release": self.operating_system_release,
            "machine_architecture": self.machine_architecture,
            "cpu_identity": self.cpu_identity_sha256,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "numpy_version": self.numpy_version,
            "environment_variable_rows": [
                {"name": name, "value": value}
                for name, value in self.environment_variable_rows
            ],
            "network_disabled_verification": {
                "attestation_sha256": self.network_isolation_attestation_sha256,
                "network_namespace_identity_sha256": (
                    self.network_namespace_identity_sha256
                ),
                "operator_signed": True,
                "network_access_disabled": True,
                "kernel_enforced_by_this_library": False,
            },
            "command_argv": list(self.command_argv),
            "python_hash_seed": self.python_hash_seed,
            "application_seed": self.application_seed,
            "thread_count_rows": [
                {"name": name, "value": value}
                for name, value in self.thread_count_rows
            ],
            "artifact_output_root": {
                "absolute_path_sha256": self.artifact_output_root_identity_sha256,
                "mode": "0700",
                "owner": "effective_uid",
                "path_disclosed": False,
            },
            "artifact_path_confinement_verification": {
                "secure_dir_fd_traversal": True,
                "symlink_components_allowed": False,
                "same_uid_replacement_resistance_established": False,
            },
            "started_at_utc": self.started_at_utc,
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "environment_receipt_persisted": True,
            "run_start_dependencies_reverified": True,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload


def _assert_reservation_matches_authorization(
    reservation: ReferenceValidationNonceReservation,
    verification: ReferenceValidationAuthorizationVerification,
) -> None:
    expected = {
        "authorization_receipt_sha256": verification.receipt_sha256,
        "review_attestation_sha256": verification.review_attestation_sha256,
        "authorization_operator_identity_sha256": (
            verification.authorization_operator_identity_sha256
        ),
        "authorization_nonce_sha256": verification.authorization_nonce_sha256,
        "code_commit_sha": verification.code_commit_sha,
        "runner_source_sha256": verification.runner_source_sha256,
        "execution_environment_contract_sha256": (
            verification.execution_environment_contract_sha256
        ),
        "result_receipt_contract_sha256": (
            verification.result_receipt_contract_sha256
        ),
        "dependency_artifact_sha256_rows": (
            verification.dependency_artifact_sha256_rows
        ),
    }
    observed = {name: getattr(reservation, name) for name in expected}
    if observed != expected:
        raise ReferenceValidationRunStartError(
            "nonce reservation and run-start authorization are cross-wired"
        )


def _build_environment_receipt(
    *,
    reservation: ReferenceValidationNonceReservation,
    verification: ReferenceValidationAuthorizationVerification,
    observation: _RuntimeObservation,
    network: ReferenceValidationNetworkIsolationVerification,
    artifact_output_root_identity_sha256: str,
    started_at_utc: str,
) -> ReferenceValidationExecutionEnvironmentReceipt:
    fingerprint = _sha256(
        observation.fingerprint_projection(
            artifact_output_root_identity_sha256=(
                artifact_output_root_identity_sha256
            )
        )
    )
    values = {
        "nonce_reservation_record_sha256": reservation.reservation_record_sha256,
        "authorization_receipt_sha256": verification.receipt_sha256,
        "review_attestation_sha256": verification.review_attestation_sha256,
        "implementation_author_identity_sha256": (
            verification.implementation_author_identity_sha256
        ),
        "independent_reviewer_identity_sha256": (
            verification.independent_reviewer_identity_sha256
        ),
        "authorization_operator_identity_sha256": (
            verification.authorization_operator_identity_sha256
        ),
        "authorization_nonce_sha256": verification.authorization_nonce_sha256,
        "code_commit_sha": verification.code_commit_sha,
        "runner_source_sha256": verification.runner_source_sha256,
        "dependency_artifact_sha256_rows": (
            verification.dependency_artifact_sha256_rows
        ),
        "operating_system_release": observation.operating_system_release,
        "machine_architecture": "x86_64",
        "cpu_identity_sha256": observation.cpu_identity_sha256,
        "python_version": observation.python_version,
        "torch_version": observation.torch_version,
        "numpy_version": observation.numpy_version,
        "environment_variable_rows": observation.environment_variable_rows,
        "network_isolation_attestation_sha256": network.attestation_sha256,
        "network_namespace_identity_sha256": (
            network.network_namespace_identity_sha256
        ),
        "command_argv": observation.command_argv,
        "python_hash_seed": observation.python_hash_seed,
        "application_seed": observation.application_seed,
        "thread_count_rows": observation.thread_count_rows,
        "artifact_output_root_identity_sha256": (
            artifact_output_root_identity_sha256
        ),
        "environment_fingerprint_sha256": fingerprint,
        "started_at_utc": started_at_utc,
        "blockers": _POST_ENVIRONMENT_RECEIPT_BLOCKERS,
    }
    provisional = ReferenceValidationExecutionEnvironmentReceipt(
        receipt_sha256="0" * 64,
        **values,
    )
    return ReferenceValidationExecutionEnvironmentReceipt(
        receipt_sha256=_sha256(provisional.projection()),
        **values,
    )


def _persist_environment_receipt(
    root_fd: int,
    receipt: ReferenceValidationExecutionEnvironmentReceipt,
) -> None:
    filename = f"{receipt.authorization_nonce_sha256}.environment.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(filename, flags, 0o600, dir_fd=root_fd)
    except FileExistsError as exc:
        raise ReferenceValidationEnvironmentReceiptAlreadyExistsError(
            "execution environment receipt already exists for the nonce"
        ) from exc
    except (OSError, ValueError) as exc:
        raise ReferenceValidationRunStartError(
            "execution environment receipt cannot be created securely"
        ) from exc
    try:
        try:
            _validate_reservation_file_stat(os.fstat(descriptor))
            payload = _canonical_bytes(receipt.to_dict()) + b"\n"
            remaining = memoryview(payload)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("environment receipt write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        except Exception as exc:
            raise ReferenceValidationRunStartError(
                "environment receipt persistence failed; the path remains consumed"
            ) from exc
    finally:
        os.close(descriptor)
    try:
        os.fsync(root_fd)
    except OSError as exc:
        raise ReferenceValidationRunStartError(
            "environment receipt directory fsync failed; the path remains consumed"
        ) from exc


def create_reference_validation_execution_environment_receipt(
    reservation_root: str | os.PathLike[str],
    artifact_output_root: str | os.PathLike[str],
    *,
    authorization_nonce_sha256: str,
    authorization_receipt: str | bytes | Mapping[str, Any],
    review_attestation: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    trusted_operator_keys: Mapping[str, AuthorizationOperatorTrustAnchor],
    network_isolation_attestation: str | bytes | Mapping[str, Any],
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    revoked_receipt_sha256s: Sequence[str] = (),
    revoked_review_attestation_sha256s: Sequence[str] = (),
    externally_conflicting_nonce_sha256s: Sequence[str] = (),
    revoked_network_attestation_sha256s: Sequence[str] = (),
) -> ReferenceValidationExecutionEnvironmentReceipt:
    """Reverify the full chain and persist one pre-evaluation receipt."""

    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="requested run-start authorization nonce",
    )
    checked_at = _utc_now()
    try:
        verification = verify_signed_reference_validation_authorization_receipt(
            authorization_receipt,
            review_attestation=review_attestation,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(
                expected_implementation_author_identity_sha256
            ),
            trusted_operator_keys=trusted_operator_keys,
            checked_at=checked_at,
            expected_code_commit_sha=expected_code_commit_sha,
            expected_runner_source_sha256=expected_runner_source_sha256,
            expected_execution_environment_contract_sha256=(
                FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            ),
            expected_result_receipt_contract_sha256=(
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            expected_dependency_artifact_sha256_rows=(
                expected_dependency_artifact_sha256_rows
            ),
            revoked_receipt_sha256s=revoked_receipt_sha256s,
            revoked_review_attestation_sha256s=(
                revoked_review_attestation_sha256s
            ),
            consumed_nonce_sha256s=externally_conflicting_nonce_sha256s,
        )
    except ReferenceValidationAuthorizationError as exc:
        raise ReferenceValidationRunStartError(
            "run-start authorization re-verification failed"
        ) from exc
    if verification.authorization_nonce_sha256 != nonce:
        raise ReferenceValidationRunStartError(
            "requested nonce and signed authorization are cross-wired"
        )
    try:
        reservation = read_reference_validation_nonce_reservation(
            reservation_root,
            nonce,
        )
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunStartError(
            "run-start durable nonce reservation verification failed"
        ) from exc
    _assert_reservation_matches_authorization(reservation, verification)
    observation = _observe_current_runtime()
    _require_runtime_observation(observation)
    output_root_identity = reference_validation_artifact_output_root_identity_sha256(
        artifact_output_root
    )
    network = verify_signed_reference_validation_network_isolation_attestation(
        network_isolation_attestation,
        trusted_operator_keys=trusted_operator_keys,
        checked_at=checked_at,
        expected_authorization=verification,
        expected_artifact_output_root_identity_sha256=output_root_identity,
        expected_network_namespace_identity_sha256=(
            observation.network_namespace_identity_sha256
        ),
        revoked_attestation_sha256s=revoked_network_attestation_sha256s,
    )
    receipt = _build_environment_receipt(
        reservation=reservation,
        verification=verification,
        observation=observation,
        network=network,
        artifact_output_root_identity_sha256=output_root_identity,
        started_at_utc=_format_utc(checked_at, name="run-start checked_at"),
    )
    try:
        root_fd = _open_secure_reservation_root(artifact_output_root)
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunStartError(
            "artifact output root does not satisfy the private POSIX policy"
        ) from exc
    try:
        _persist_environment_receipt(root_fd, receipt)
    finally:
        os.close(root_fd)
    return receipt


def _load_persisted_receipt(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > REFERENCE_VALIDATION_RUN_START_MAX_RECORD_BYTES:
        raise ReferenceValidationRunStartError("environment receipt size is invalid")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunStartError(
                    "environment receipt contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunStartError(
            "environment receipt must be canonical ASCII JSON"
        ) from exc
    if not isinstance(loaded, dict) or raw != _canonical_bytes(loaded) + b"\n":
        raise ReferenceValidationRunStartError(
            "environment receipt bytes are not canonical"
        )
    return loaded


def _receipt_from_payload(
    payload: Mapping[str, Any],
    *,
    expected_nonce_sha256: str,
) -> ReferenceValidationExecutionEnvironmentReceipt:
    projection = dict(payload)
    receipt_sha256 = projection.pop("receipt_sha256", None)
    if receipt_sha256 != _sha256(projection):
        raise ReferenceValidationRunStartError(
            "environment receipt SHA-256 verification failed"
        )
    fixed = {
        "schema_id": REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID,
        "run_start_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
        ),
        "environment_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
        "artifact_binding_sha256": (
            FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256
        ),
        "authorization_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
        ),
        "nonce_reservation_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
        ),
        "environment_receipt_persisted": True,
        "run_start_dependencies_reverified": True,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "blockers": list(_POST_ENVIRONMENT_RECEIPT_BLOCKERS),
    }
    if any(projection.get(key) != value for key, value in fixed.items()):
        raise ReferenceValidationRunStartError(
            "environment receipt fixed fields drifted"
        )
    nonce = _require_sha256(
        projection.get("authorization_nonce_sha256"),
        name="environment receipt authorization nonce",
    )
    if nonce != expected_nonce_sha256:
        raise ReferenceValidationRunStartError(
            "environment receipt filename and nonce are cross-wired"
        )
    network = projection.get("network_disabled_verification")
    artifact_root = projection.get("artifact_output_root")
    confinement = projection.get("artifact_path_confinement_verification")
    if not isinstance(network, Mapping) or set(network) != {
        "attestation_sha256",
        "network_namespace_identity_sha256",
        "operator_signed",
        "network_access_disabled",
        "kernel_enforced_by_this_library",
    }:
        raise ReferenceValidationRunStartError(
            "environment receipt network verification fields are invalid"
        )
    if network.get("operator_signed") is not True or network.get(
        "network_access_disabled"
    ) is not True or network.get("kernel_enforced_by_this_library") is not False:
        raise ReferenceValidationRunStartError(
            "environment receipt network verification state drifted"
        )
    if not isinstance(artifact_root, Mapping) or artifact_root.get("mode") != "0700":
        raise ReferenceValidationRunStartError(
            "environment receipt artifact root fields are invalid"
        )
    if not isinstance(confinement, Mapping) or confinement.get(
        "secure_dir_fd_traversal"
    ) is not True:
        raise ReferenceValidationRunStartError(
            "environment receipt confinement fields are invalid"
        )
    environment_rows = projection.get("environment_variable_rows")
    thread_rows = projection.get("thread_count_rows")
    if not isinstance(environment_rows, list) or not isinstance(thread_rows, list):
        raise ReferenceValidationRunStartError(
            "environment receipt runtime rows are invalid"
        )
    try:
        receipt = ReferenceValidationExecutionEnvironmentReceipt(
            receipt_sha256=_require_sha256(
                receipt_sha256,
                name="environment receipt",
            ),
            nonce_reservation_record_sha256=_require_sha256(
                projection.get("nonce_reservation_record_sha256"),
                name="environment receipt nonce reservation record",
            ),
            authorization_receipt_sha256=_require_sha256(
                projection.get("authorization_receipt_sha256"),
                name="environment receipt authorization",
            ),
            review_attestation_sha256=_require_sha256(
                projection.get("review_attestation_sha256"),
                name="environment receipt review",
            ),
            implementation_author_identity_sha256=_require_sha256(
                projection.get("implementation_author_identity_sha256"),
                name="environment receipt author",
            ),
            independent_reviewer_identity_sha256=_require_sha256(
                projection.get("independent_reviewer_identity_sha256"),
                name="environment receipt reviewer",
            ),
            authorization_operator_identity_sha256=_require_sha256(
                projection.get("authorization_operator_identity_sha256"),
                name="environment receipt operator",
            ),
            authorization_nonce_sha256=nonce,
            code_commit_sha=_require_git_commit(projection.get("code_commit_sha")),
            runner_source_sha256=_require_sha256(
                projection.get("runner_source_sha256"),
                name="environment receipt runner",
            ),
            dependency_artifact_sha256_rows=_normalize_dependency_rows(
                projection.get("dependency_artifact_sha256_rows")
            ),
            operating_system_release=projection["operating_system_release"],
            machine_architecture=projection["machine_architecture"],
            cpu_identity_sha256=projection["cpu_identity"],
            python_version=projection["python_version"],
            torch_version=projection["torch_version"],
            numpy_version=projection["numpy_version"],
            environment_variable_rows=tuple(
                (row["name"], row["value"]) for row in environment_rows
            ),
            network_isolation_attestation_sha256=_require_sha256(
                network.get("attestation_sha256"),
                name="environment receipt network attestation",
            ),
            network_namespace_identity_sha256=_require_sha256(
                network.get("network_namespace_identity_sha256"),
                name="environment receipt network namespace",
            ),
            command_argv=tuple(projection["command_argv"]),
            python_hash_seed=projection["python_hash_seed"],
            application_seed=projection["application_seed"],
            thread_count_rows=tuple(
                (row["name"], row["value"]) for row in thread_rows
            ),
            artifact_output_root_identity_sha256=_require_sha256(
                artifact_root.get("absolute_path_sha256"),
                name="environment receipt artifact root",
            ),
            environment_fingerprint_sha256=_require_sha256(
                projection.get("environment_fingerprint_sha256"),
                name="environment receipt fingerprint",
            ),
            started_at_utc=projection["started_at_utc"],
            blockers=_POST_ENVIRONMENT_RECEIPT_BLOCKERS,
        )
    except (KeyError, TypeError) as exc:
        raise ReferenceValidationRunStartError(
            "environment receipt fields are invalid"
        ) from exc
    if receipt.to_dict() != dict(payload):
        raise ReferenceValidationRunStartError(
            "environment receipt fields are not exact"
        )
    return receipt


def read_reference_validation_execution_environment_receipt(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
) -> ReferenceValidationExecutionEnvironmentReceipt:
    """Read one durable receipt without trusting it as a run authorization."""

    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="requested environment receipt nonce",
    )
    try:
        root_fd = _open_secure_reservation_root(artifact_output_root)
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunStartError(
            "artifact output root does not satisfy the private POSIX policy"
        ) from exc
    try:
        try:
            descriptor = os.open(
                f"{nonce}.environment.json",
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC
                | getattr(os, "O_NONBLOCK", 0),
                dir_fd=root_fd,
            )
        except (OSError, ValueError) as exc:
            raise ReferenceValidationRunStartError(
                "environment receipt is missing, inaccessible, or unsafe"
            ) from exc
        try:
            file_stat = os.fstat(descriptor)
            _validate_reservation_file_stat(file_stat)
            if not 0 < file_stat.st_size <= REFERENCE_VALIDATION_RUN_START_MAX_RECORD_BYTES:
                raise ReferenceValidationRunStartError(
                    "environment receipt size is invalid"
                )
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 8192)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > REFERENCE_VALIDATION_RUN_START_MAX_RECORD_BYTES:
                    raise ReferenceValidationRunStartError(
                        "environment receipt exceeds the size limit"
                    )
        finally:
            os.close(descriptor)
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunStartError(
            "environment receipt file policy verification failed"
        ) from exc
    finally:
        os.close(root_fd)
    return _receipt_from_payload(
        _load_persisted_receipt(b"".join(chunks)),
        expected_nonce_sha256=nonce,
    )


def require_reference_validation_execution_environment_receipt_for_runner(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_receipt_sha256: str,
) -> ReferenceValidationExecutionEnvironmentReceipt:
    """Re-read a receipt and require the live process to match it exactly."""

    expected_receipt = _require_sha256(
        expected_receipt_sha256,
        name="expected execution environment receipt",
    )
    receipt = read_reference_validation_execution_environment_receipt(
        artifact_output_root,
        authorization_nonce_sha256,
    )
    if not hmac.compare_digest(receipt.receipt_sha256, expected_receipt):
        raise ReferenceValidationRunStartError(
            "runner environment receipt identity is cross-wired"
        )
    root_identity = reference_validation_artifact_output_root_identity_sha256(
        artifact_output_root
    )
    if not hmac.compare_digest(
        receipt.artifact_output_root_identity_sha256,
        root_identity,
    ):
        raise ReferenceValidationRunStartError(
            "runner artifact output root identity is cross-wired"
        )
    observation = _observe_current_runtime()
    _require_runtime_observation(observation)
    observed_architecture = (
        "x86_64"
        if observation.machine_architecture in {"x86_64", "amd64"}
        else observation.machine_architecture
    )
    observed_fields = {
        "operating_system_release": observation.operating_system_release,
        "machine_architecture": observed_architecture,
        "cpu_identity_sha256": observation.cpu_identity_sha256,
        "python_version": observation.python_version,
        "torch_version": observation.torch_version,
        "numpy_version": observation.numpy_version,
        "environment_variable_rows": observation.environment_variable_rows,
        "network_namespace_identity_sha256": (
            observation.network_namespace_identity_sha256
        ),
        "command_argv": observation.command_argv,
        "python_hash_seed": observation.python_hash_seed,
        "application_seed": observation.application_seed,
        "thread_count_rows": observation.thread_count_rows,
    }
    if any(getattr(receipt, name) != value for name, value in observed_fields.items()):
        raise ReferenceValidationRunStartError(
            "live runner process does not match the execution environment receipt"
        )
    fingerprint = _sha256(
        observation.fingerprint_projection(
            artifact_output_root_identity_sha256=root_identity
        )
    )
    if not hmac.compare_digest(
        receipt.environment_fingerprint_sha256,
        fingerprint,
    ):
        raise ReferenceValidationRunStartError(
            "live runner environment fingerprint is cross-wired"
        )
    return receipt


def reference_validation_run_start_contract_decision() -> dict[str, Any]:
    contract = reference_validation_run_start_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "run_start_environment_primitive_implemented": True,
        "production_review_attestation_present": False,
        "production_authorization_receipt_present": False,
        "production_nonce_reserved": False,
        "production_environment_receipt_present": False,
        "validation_runner_implemented": False,
        "result_receipt_writer_implemented": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


__all__ = [
    "FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256",
    "REFERENCE_VALIDATION_APPLICATION_SEED_ENV",
    "REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV",
    "REFERENCE_VALIDATION_NETWORK_ATTESTATION_MAX_VALIDITY",
    "REFERENCE_VALIDATION_NETWORK_ISOLATION_ATTESTATION_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUN_START_CONTRACT_ID",
    "REFERENCE_VALIDATION_RUN_START_CONTRACT_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUN_START_CONTRACT_VERSION",
    "REFERENCE_VALIDATION_RUN_START_MAX_RECORD_BYTES",
    "ReferenceValidationEnvironmentReceiptAlreadyExistsError",
    "ReferenceValidationExecutionEnvironmentReceipt",
    "ReferenceValidationNetworkIsolationVerification",
    "ReferenceValidationRunStartError",
    "build_signed_reference_validation_network_isolation_attestation",
    "create_reference_validation_execution_environment_receipt",
    "read_reference_validation_execution_environment_receipt",
    "require_reference_validation_execution_environment_receipt_for_runner",
    "reference_validation_artifact_output_root_identity_sha256",
    "reference_validation_run_start_contract_decision",
    "reference_validation_run_start_contract_document",
    "require_reference_validation_run_start_contract_document",
    "verify_signed_reference_validation_network_isolation_attestation",
]
