"""Offline, failure-inclusive materialization of the frozen public input suite.

This module closes the gap between a frozen protocol document and verified,
locally supplied input bytes.  It verifies the receptor as well as both ligand
artifacts, retains one row for every protocol case, and embeds the existing
reference-pose materialization receipt when possible.  It never fetches data,
runs docking, evaluates pose validity, or emits benchmark performance results.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from numbers import Integral
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Callable, Mapping, Sequence

from .public_materialization import (
    MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES,
    PublicBenchmarkCaseMaterialization,
    PublicReferenceMaterializationError,
    PublicReferenceMaterializationLimits,
    materialize_public_benchmark_case,
)
from .public_protocol import (
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    PUBLIC_BENCHMARK_PROTOCOL_ID,
    PUBLIC_BENCHMARK_PROTOCOL_VERSION,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
    frozen_public_benchmark_protocol,
)


PUBLIC_BENCHMARK_ARTIFACT_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_artifact_observation/1.0.0"
)
PUBLIC_BENCHMARK_SUITE_CASE_MATERIALIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_suite_case_materialization/1.0.0"
)
PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_suite_materialization/1.0.0"
)
MAX_PUBLIC_BENCHMARK_SUITE_RECEIPT_BYTES = 64 * 1024 * 1024

PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCIENTIFIC_BLOCKERS = (
    "four_case_contract_cohort_not_statistically_representative",
    "posebusters_benchmark_equivalence_not_established",
    "docking_predictions_missing",
    "pose_validity_not_evaluated",
    "public_benchmark_not_executed",
    "public_holdout_results_missing",
    "same_input_vina_gnina_smina_receipts_missing",
    "independent_external_rerun_missing",
    "legal_compliance_determination_not_made",
    "scientific_review_missing",
    "product_integration_not_qualified",
)

_ARTIFACT_ROLES = (
    "ligand_identity_seed",
    "receptor",
    "reference_ligands",
)
_OBSERVATION_STATUSES = frozenset(
    {
        "verified",
        "missing",
        "invalid_type",
        "unsafe_path",
        "not_regular_file",
        "read_error",
        "oversized",
        "size_mismatch",
        "sha256_mismatch",
    }
)
_NO_BYTE_STATUSES = frozenset(
    {"missing", "invalid_type", "unsafe_path", "not_regular_file", "read_error"}
)
_CASE_STATUSES = frozenset(
    {
        "materialized_ready",
        "materialized_not_ready",
        "failure_input_verification",
        "failure_reference_materialization",
    }
)


class PublicBenchmarkSuiteMaterializationError(ValueError):
    """The public-suite input, receipt, or filesystem contract is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicBenchmarkSuiteMaterializationError(
            "public-suite value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PublicBenchmarkSuiteMaterializationError(f"{name} must be a SHA-256")
    result = value.strip().lower()
    if allow_empty and not result:
        return ""
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise PublicBenchmarkSuiteMaterializationError(
            f"{name} must be a lowercase SHA-256"
        )
    return result


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise PublicBenchmarkSuiteMaterializationError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise PublicBenchmarkSuiteMaterializationError(
            f"{name} must be at least {minimum}"
        )
    return result


def _require_text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicBenchmarkSuiteMaterializationError(f"{name} must be non-empty")
    return value.strip()


@dataclass(frozen=True, slots=True)
class PublicBenchmarkArtifactObservation:
    """Expected and observed identity for one locally supplied protocol file."""

    role: str
    relative_path: str
    expected_sha256: str
    expected_size_bytes: int
    status: str
    observed_sha256: str = ""
    observed_size_bytes: int = 0
    schema_id: str = PUBLIC_BENCHMARK_ARTIFACT_OBSERVATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_BENCHMARK_ARTIFACT_OBSERVATION_SCHEMA_ID:
            raise PublicBenchmarkSuiteMaterializationError(
                "unsupported public artifact observation schema"
            )
        if self.role not in _ARTIFACT_ROLES:
            raise PublicBenchmarkSuiteMaterializationError(
                "public artifact observation role is invalid"
            )
        path = Path(_require_text(self.relative_path, name="relative_path"))
        if path.is_absolute() or ".." in path.parts:
            raise PublicBenchmarkSuiteMaterializationError(
                "public artifact relative path is unsafe"
            )
        expected_digest = _require_digest(
            self.expected_sha256,
            name="expected_sha256",
        )
        expected_size = _exact_int(
            self.expected_size_bytes,
            name="expected_size_bytes",
            minimum=1,
        )
        observed_size = _exact_int(
            self.observed_size_bytes,
            name="observed_size_bytes",
        )
        if self.status not in _OBSERVATION_STATUSES:
            raise PublicBenchmarkSuiteMaterializationError(
                "public artifact observation status is invalid"
            )
        observed_digest = _require_digest(
            self.observed_sha256,
            name="observed_sha256",
            allow_empty=True,
        )
        if self.status in _NO_BYTE_STATUSES:
            if observed_digest or observed_size != 0:
                raise PublicBenchmarkSuiteMaterializationError(
                    "unread public artifact cannot carry observed byte identity"
                )
        elif self.status == "oversized":
            if observed_digest or observed_size <= MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES:
                raise PublicBenchmarkSuiteMaterializationError(
                    "oversized public artifact observation is inconsistent"
                )
        else:
            if not observed_digest or observed_size > MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES:
                raise PublicBenchmarkSuiteMaterializationError(
                    "read public artifact observation is inconsistent"
                )
            if self.status == "verified" and (
                observed_size != expected_size or observed_digest != expected_digest
            ):
                raise PublicBenchmarkSuiteMaterializationError(
                    "verified public artifact identity disagrees with the protocol"
                )
            if self.status == "size_mismatch" and observed_size == expected_size:
                raise PublicBenchmarkSuiteMaterializationError(
                    "size-mismatch public artifact has the expected size"
                )
            if self.status == "sha256_mismatch" and (
                observed_size != expected_size or observed_digest == expected_digest
            ):
                raise PublicBenchmarkSuiteMaterializationError(
                    "SHA-mismatch public artifact observation is inconsistent"
                )
        object.__setattr__(self, "expected_sha256", expected_digest)
        object.__setattr__(self, "expected_size_bytes", expected_size)
        object.__setattr__(self, "observed_sha256", observed_digest)
        object.__setattr__(self, "observed_size_bytes", observed_size)

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "relative_path": self.relative_path,
            "expected_sha256": self.expected_sha256,
            "expected_size_bytes": self.expected_size_bytes,
            "status": self.status,
            "observed_sha256": self.observed_sha256,
            "observed_size_bytes": self.observed_size_bytes,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, value: object) -> "PublicBenchmarkArtifactObservation":
        expected = {
            "schema_id",
            "role",
            "relative_path",
            "expected_sha256",
            "expected_size_bytes",
            "status",
            "observed_sha256",
            "observed_size_bytes",
            "verified",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise PublicBenchmarkSuiteMaterializationError(
                "public artifact observation payload is invalid"
            )
        result = cls(
            role=value["role"],
            relative_path=value["relative_path"],
            expected_sha256=value["expected_sha256"],
            expected_size_bytes=value["expected_size_bytes"],
            status=value["status"],
            observed_sha256=value["observed_sha256"],
            observed_size_bytes=value["observed_size_bytes"],
            schema_id=value["schema_id"],
        )
        if result.to_dict() != dict(value):
            raise PublicBenchmarkSuiteMaterializationError(
                "public artifact observation payload is inconsistent"
            )
        return result


@dataclass(frozen=True, slots=True)
class PublicBenchmarkSuiteCaseMaterialization:
    """One failure-inclusive suite row, optionally embedding a case receipt."""

    case_id: str
    pdb_id: str
    case_input_sha256: str
    artifact_observations: tuple[PublicBenchmarkArtifactObservation, ...]
    status: str
    error_code: str
    materialization: PublicBenchmarkCaseMaterialization | None = None
    schema_id: str = PUBLIC_BENCHMARK_SUITE_CASE_MATERIALIZATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_BENCHMARK_SUITE_CASE_MATERIALIZATION_SCHEMA_ID:
            raise PublicBenchmarkSuiteMaterializationError(
                "unsupported public suite case schema"
            )
        case_id = _require_text(self.case_id, name="case_id")
        pdb_id = _require_text(self.pdb_id, name="pdb_id").lower()
        case_digest = _require_digest(
            self.case_input_sha256,
            name="case_input_sha256",
        )
        observations = tuple(self.artifact_observations)
        if tuple(item.role for item in observations) != _ARTIFACT_ROLES:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite artifact rows must use the exact sorted role set"
            )
        if self.status not in _CASE_STATUSES:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite case status is invalid"
            )
        error_code = self.error_code
        if not isinstance(error_code, str):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite case error_code must be text"
            )
        inputs_verified = all(item.verified for item in observations)
        materialization = self.materialization
        if materialization is not None and (
            materialization.case_id != case_id
            or materialization.case_input_sha256 != case_digest
        ):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite case materialization is cross-wired"
            )
        if self.status == "failure_input_verification":
            valid = (
                not inputs_verified
                and materialization is None
                and error_code == "artifact_input_verification_failed"
            )
        elif self.status == "failure_reference_materialization":
            valid = (
                inputs_verified
                and materialization is None
                and error_code == "PublicReferenceMaterializationError"
            )
        elif self.status == "materialized_ready":
            valid = (
                inputs_verified
                and materialization is not None
                and materialization.ready_for_rmsd
                and not error_code
            )
        else:
            valid = (
                inputs_verified
                and materialization is not None
                and not materialization.ready_for_rmsd
                and error_code == "reference_materialization_not_ready"
            )
        if not valid:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite case status, inputs, and materialization disagree"
            )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "pdb_id", pdb_id)
        object.__setattr__(self, "case_input_sha256", case_digest)
        object.__setattr__(self, "artifact_observations", observations)

    @property
    def inputs_verified(self) -> bool:
        return all(item.verified for item in self.artifact_observations)

    @property
    def ready_for_rmsd(self) -> bool:
        return self.status == "materialized_ready"

    @property
    def materialization_sha256(self) -> str:
        if self.materialization is None:
            return ""
        return self.materialization.fingerprint_sha256

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "pdb_id": self.pdb_id,
            "case_input_sha256": self.case_input_sha256,
            "artifact_observations": [
                observation.to_dict() for observation in self.artifact_observations
            ],
            "inputs_verified": self.inputs_verified,
            "status": self.status,
            "error_code": self.error_code,
            "ready_for_rmsd": self.ready_for_rmsd,
            "materialization_sha256": self.materialization_sha256,
            "materialization": (
                None if self.materialization is None else self.materialization.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "PublicBenchmarkSuiteCaseMaterialization":
        expected = {
            "schema_id",
            "case_id",
            "pdb_id",
            "case_input_sha256",
            "artifact_observations",
            "inputs_verified",
            "status",
            "error_code",
            "ready_for_rmsd",
            "materialization_sha256",
            "materialization",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite case payload is invalid"
            )
        raw_observations = value["artifact_observations"]
        if not isinstance(raw_observations, list):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite artifact observations must be a list"
            )
        raw_materialization = value["materialization"]
        if raw_materialization is None:
            materialization = None
        elif isinstance(raw_materialization, Mapping):
            materialization = PublicBenchmarkCaseMaterialization.from_json_bytes(
                _canonical_bytes(dict(raw_materialization)) + b"\n"
            )
        else:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite embedded materialization is invalid"
            )
        result = cls(
            case_id=value["case_id"],
            pdb_id=value["pdb_id"],
            case_input_sha256=value["case_input_sha256"],
            artifact_observations=tuple(
                PublicBenchmarkArtifactObservation.from_dict(item)
                for item in raw_observations
            ),
            status=value["status"],
            error_code=value["error_code"],
            materialization=materialization,
            schema_id=value["schema_id"],
        )
        if result.to_dict() != dict(value):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite case payload is inconsistent"
            )
        return result

    def require_case(
        self,
        case: PublicBenchmarkCaseDefinition,
        *,
        protocol_sha256: str,
    ) -> "PublicBenchmarkSuiteCaseMaterialization":
        if not isinstance(case, PublicBenchmarkCaseDefinition):
            raise PublicBenchmarkSuiteMaterializationError(
                "suite case definition has the wrong type"
            )
        if (
            self.case_id != case.case_id
            or self.pdb_id != case.pdb_id
            or self.case_input_sha256 != case.input_sha256
        ):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite row disagrees with its protocol case"
            )
        expected_artifacts = {
            artifact.role: artifact
            for artifact in (
                case.ligand_identity_seed,
                case.receptor,
                case.reference_ligands,
            )
        }
        for observation in self.artifact_observations:
            artifact = expected_artifacts[observation.role]
            if (
                observation.relative_path != artifact.relative_path
                or observation.expected_sha256 != artifact.sha256
                or observation.expected_size_bytes != artifact.size_bytes
            ):
                raise PublicBenchmarkSuiteMaterializationError(
                    "public artifact observation disagrees with the protocol"
                )
        if self.materialization is not None and (
            self.materialization.protocol_sha256 != protocol_sha256
            or self.materialization.ligand_identity_seed_sha256
            != case.ligand_identity_seed.sha256
            or self.materialization.reference_ligands_sha256
            != case.reference_ligands.sha256
        ):
            raise PublicBenchmarkSuiteMaterializationError(
                "embedded reference materialization disagrees with the protocol"
            )
        return self


@dataclass(frozen=True, slots=True)
class PublicBenchmarkSuiteMaterializationReceipt:
    """Canonical receipt for verification/materialization of all four inputs."""

    protocol_sha256: str
    case_rows: tuple[PublicBenchmarkSuiteCaseMaterialization, ...]
    scientific_blockers: tuple[str, ...] = (
        PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCHEMA_ID:
            raise PublicBenchmarkSuiteMaterializationError(
                "unsupported public suite materialization schema"
            )
        protocol_digest = _require_digest(
            self.protocol_sha256,
            name="protocol_sha256",
        )
        rows = tuple(self.case_rows)
        case_ids = tuple(row.case_id for row in rows)
        if len(rows) != 4 or case_ids != tuple(sorted(set(case_ids))):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt must contain four uniquely sorted case rows"
            )
        if any(
            row.materialization is not None
            and row.materialization.protocol_sha256 != protocol_digest
            for row in rows
        ):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt contains a cross-protocol materialization"
            )
        if tuple(self.scientific_blockers) != (
            PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCIENTIFIC_BLOCKERS
        ):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite scientific blockers cannot be promoted"
            )
        object.__setattr__(self, "protocol_sha256", protocol_digest)
        object.__setattr__(self, "case_rows", rows)

    @property
    def input_verified_case_count(self) -> int:
        return sum(row.inputs_verified for row in self.case_rows)

    @property
    def ready_for_rmsd_case_count(self) -> int:
        return sum(row.ready_for_rmsd for row in self.case_rows)

    @property
    def failed_case_count(self) -> int:
        return len(self.case_rows) - self.ready_for_rmsd_case_count

    @property
    def verified_artifact_count(self) -> int:
        return sum(
            observation.verified
            for row in self.case_rows
            for observation in row.artifact_observations
        )

    @property
    def input_materialization_complete(self) -> bool:
        return self.ready_for_rmsd_case_count == len(self.case_rows)

    @property
    def claim_safe(self) -> bool:
        return False

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "protocol_id": PUBLIC_BENCHMARK_PROTOCOL_ID,
            "protocol_version": PUBLIC_BENCHMARK_PROTOCOL_VERSION,
            "protocol_sha256": self.protocol_sha256,
            "source_commit_sha": POSEBUSTERS_SOURCE_COMMIT_SHA,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "case_count": len(self.case_rows),
            "artifact_count": len(self.case_rows) * len(_ARTIFACT_ROLES),
            "verified_artifact_count": self.verified_artifact_count,
            "input_verified_case_count": self.input_verified_case_count,
            "ready_for_rmsd_case_count": self.ready_for_rmsd_case_count,
            "failed_case_count": self.failed_case_count,
            "failure_rows_retained": True,
            "denominator": "all_protocol_cases",
            "network_fetch_performed": False,
            "input_materialization_complete": self.input_materialization_complete,
            "docking_predictions_present": False,
            "pose_validity_evaluated": False,
            "benchmark_executed": False,
            "public_holdout_result_established": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "customer_execution_enabled": False,
            "scientific_blockers": list(self.scientific_blockers),
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "receipt_sha256": self.fingerprint_sha256,
        }

    def to_json_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    @classmethod
    def from_json_bytes(
        cls,
        source: bytes,
    ) -> "PublicBenchmarkSuiteMaterializationReceipt":
        if not isinstance(source, bytes):
            raise TypeError("public suite receipt source must be bytes")
        if len(source) < 1 or len(source) > MAX_PUBLIC_BENCHMARK_SUITE_RECEIPT_BYTES:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt size is outside the configured bound"
            )
        try:
            value = json.loads(source.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt is not canonical JSON"
            ) from exc
        expected = {
            "schema_id",
            "protocol_id",
            "protocol_version",
            "protocol_sha256",
            "source_commit_sha",
            "case_rows",
            "case_count",
            "artifact_count",
            "verified_artifact_count",
            "input_verified_case_count",
            "ready_for_rmsd_case_count",
            "failed_case_count",
            "failure_rows_retained",
            "denominator",
            "network_fetch_performed",
            "input_materialization_complete",
            "docking_predictions_present",
            "pose_validity_evaluated",
            "benchmark_executed",
            "public_holdout_result_established",
            "scientifically_validated",
            "benchmark_validated",
            "customer_execution_enabled",
            "scientific_blockers",
            "claim_safe",
            "receipt_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt payload is invalid"
            )
        raw_rows = value["case_rows"]
        raw_blockers = value["scientific_blockers"]
        if not isinstance(raw_rows, list) or not isinstance(raw_blockers, list):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt collections are invalid"
            )
        result = cls(
            protocol_sha256=value["protocol_sha256"],
            case_rows=tuple(
                PublicBenchmarkSuiteCaseMaterialization.from_dict(row)
                for row in raw_rows
            ),
            scientific_blockers=tuple(raw_blockers),
            schema_id=value["schema_id"],
        )
        if result.to_dict() != dict(value) or result.to_json_bytes() != source:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt is not canonical or is inconsistent"
            )
        return result

    def require_protocol(
        self,
        protocol: FrozenPublicBenchmarkProtocol,
    ) -> "PublicBenchmarkSuiteMaterializationReceipt":
        if not isinstance(protocol, FrozenPublicBenchmarkProtocol):
            raise PublicBenchmarkSuiteMaterializationError(
                "protocol must be FrozenPublicBenchmarkProtocol"
            )
        if self.protocol_sha256 != protocol.protocol_sha256:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt protocol SHA-256 mismatch"
            )
        if tuple(row.case_id for row in self.case_rows) != tuple(
            case.case_id for case in protocol.cases
        ):
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt case set disagrees with the protocol"
            )
        for row, case in zip(self.case_rows, protocol.cases, strict=True):
            row.require_case(case, protocol_sha256=protocol.protocol_sha256)
        return self


@dataclass(frozen=True, slots=True)
class _ArtifactReadFailure:
    status: str
    observed_size_bytes: int = 0


_ArtifactSource = bytes | _ArtifactReadFailure
_ArtifactLoader = Callable[[PublicBenchmarkArtifact], _ArtifactSource]


def _artifact_observation(
    artifact: PublicBenchmarkArtifact,
    source: _ArtifactSource,
) -> tuple[PublicBenchmarkArtifactObservation, bytes | None]:
    if isinstance(source, _ArtifactReadFailure):
        return (
            PublicBenchmarkArtifactObservation(
                role=artifact.role,
                relative_path=artifact.relative_path,
                expected_sha256=artifact.sha256,
                expected_size_bytes=artifact.size_bytes,
                status=source.status,
                observed_size_bytes=source.observed_size_bytes,
            ),
            None,
        )
    if not isinstance(source, bytes):
        source = _ArtifactReadFailure("invalid_type")
        return _artifact_observation(artifact, source)
    observed_size = len(source)
    if observed_size > MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES:
        return _artifact_observation(
            artifact,
            _ArtifactReadFailure("oversized", observed_size),
        )
    observed_sha256 = hashlib.sha256(source).hexdigest()
    if observed_size != artifact.size_bytes:
        status = "size_mismatch"
    elif observed_sha256 != artifact.sha256:
        status = "sha256_mismatch"
    else:
        status = "verified"
    return (
        PublicBenchmarkArtifactObservation(
            role=artifact.role,
            relative_path=artifact.relative_path,
            expected_sha256=artifact.sha256,
            expected_size_bytes=artifact.size_bytes,
            status=status,
            observed_sha256=observed_sha256,
            observed_size_bytes=observed_size,
        ),
        source if status == "verified" else None,
    )


def _case_artifacts(
    case: PublicBenchmarkCaseDefinition,
) -> tuple[PublicBenchmarkArtifact, ...]:
    return tuple(
        sorted(
            (case.ligand_identity_seed, case.receptor, case.reference_ligands),
            key=lambda artifact: artifact.role,
        )
    )


def _materialize_suite_with_loader(
    protocol: FrozenPublicBenchmarkProtocol,
    loader: _ArtifactLoader,
    *,
    limits: PublicReferenceMaterializationLimits | None,
) -> PublicBenchmarkSuiteMaterializationReceipt:
    if not isinstance(protocol, FrozenPublicBenchmarkProtocol):
        raise PublicBenchmarkSuiteMaterializationError(
            "protocol must be FrozenPublicBenchmarkProtocol"
        )
    active = PublicReferenceMaterializationLimits() if limits is None else limits
    if not isinstance(active, PublicReferenceMaterializationLimits):
        raise PublicBenchmarkSuiteMaterializationError(
            "limits must be PublicReferenceMaterializationLimits"
        )
    rows: list[PublicBenchmarkSuiteCaseMaterialization] = []
    for case in protocol.cases:
        observations: list[PublicBenchmarkArtifactObservation] = []
        verified_sources: dict[str, bytes] = {}
        for artifact in _case_artifacts(case):
            observation, verified_source = _artifact_observation(
                artifact,
                loader(artifact),
            )
            observations.append(observation)
            if verified_source is not None:
                verified_sources[artifact.role] = verified_source
        if len(verified_sources) != len(_ARTIFACT_ROLES):
            row = PublicBenchmarkSuiteCaseMaterialization(
                case_id=case.case_id,
                pdb_id=case.pdb_id,
                case_input_sha256=case.input_sha256,
                artifact_observations=tuple(observations),
                status="failure_input_verification",
                error_code="artifact_input_verification_failed",
            )
        else:
            try:
                materialization = materialize_public_benchmark_case(
                    case,
                    verified_sources["ligand_identity_seed"],
                    verified_sources["reference_ligands"],
                    protocol_sha256=protocol.protocol_sha256,
                    limits=active,
                )
            except PublicReferenceMaterializationError:
                row = PublicBenchmarkSuiteCaseMaterialization(
                    case_id=case.case_id,
                    pdb_id=case.pdb_id,
                    case_input_sha256=case.input_sha256,
                    artifact_observations=tuple(observations),
                    status="failure_reference_materialization",
                    error_code="PublicReferenceMaterializationError",
                )
            else:
                ready = materialization.ready_for_rmsd
                row = PublicBenchmarkSuiteCaseMaterialization(
                    case_id=case.case_id,
                    pdb_id=case.pdb_id,
                    case_input_sha256=case.input_sha256,
                    artifact_observations=tuple(observations),
                    status=("materialized_ready" if ready else "materialized_not_ready"),
                    error_code=("" if ready else "reference_materialization_not_ready"),
                    materialization=materialization,
                )
        rows.append(row)
    receipt = PublicBenchmarkSuiteMaterializationReceipt(
        protocol_sha256=protocol.protocol_sha256,
        case_rows=tuple(rows),
    )
    return receipt.require_protocol(protocol)


def materialize_public_benchmark_input_suite(
    protocol: FrozenPublicBenchmarkProtocol,
    artifacts_by_relative_path: Mapping[str, bytes],
    *,
    limits: PublicReferenceMaterializationLimits | None = None,
) -> PublicBenchmarkSuiteMaterializationReceipt:
    """Materialize a four-case protocol from an in-memory, offline byte map."""

    if not isinstance(artifacts_by_relative_path, Mapping):
        raise PublicBenchmarkSuiteMaterializationError(
            "artifacts_by_relative_path must be a mapping"
        )

    def load(artifact: PublicBenchmarkArtifact) -> _ArtifactSource:
        if artifact.relative_path not in artifacts_by_relative_path:
            return _ArtifactReadFailure("missing")
        source = artifacts_by_relative_path[artifact.relative_path]
        if not isinstance(source, bytes):
            return _ArtifactReadFailure("invalid_type")
        return source

    return _materialize_suite_with_loader(protocol, load, limits=limits)


def _directory_loader(root: Path) -> _ArtifactLoader:
    def load(artifact: PublicBenchmarkArtifact) -> _ArtifactSource:
        candidate = root.joinpath(*Path(artifact.relative_path).parts)
        current = root
        try:
            for part in Path(artifact.relative_path).parts:
                current = current / part
                metadata = os.lstat(current)
                if stat.S_ISLNK(metadata.st_mode):
                    return _ArtifactReadFailure("unsafe_path")
        except FileNotFoundError:
            return _ArtifactReadFailure("missing")
        except OSError:
            return _ArtifactReadFailure("read_error")
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            return _ArtifactReadFailure("unsafe_path")
        try:
            before = os.stat(resolved, follow_symlinks=False)
        except OSError:
            return _ArtifactReadFailure("read_error")
        if not stat.S_ISREG(before.st_mode):
            return _ArtifactReadFailure("not_regular_file")
        if before.st_size > MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES:
            return _ArtifactReadFailure("oversized", before.st_size)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(resolved, flags)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                source = handle.read(MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES + 1)
                after = os.fstat(handle.fileno())
        except OSError:
            return _ArtifactReadFailure("read_error")
        if (
            opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or after.st_size != opened.st_size
        ):
            return _ArtifactReadFailure("read_error")
        if len(source) > MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES:
            return _ArtifactReadFailure("oversized", len(source))
        return source

    return load


def materialize_public_benchmark_input_suite_from_directory(
    protocol: FrozenPublicBenchmarkProtocol,
    input_root: str | os.PathLike[str],
    *,
    limits: PublicReferenceMaterializationLimits | None = None,
) -> PublicBenchmarkSuiteMaterializationReceipt:
    """Read one four-case protocol from a non-symlink local directory."""

    unresolved = Path(input_root)
    if unresolved.is_symlink():
        raise PublicBenchmarkSuiteMaterializationError(
            "public benchmark input root must not be a symlink"
        )
    try:
        root = unresolved.resolve(strict=True)
    except OSError as exc:
        raise PublicBenchmarkSuiteMaterializationError(
            "public benchmark input root does not exist"
        ) from exc
    if not root.is_dir():
        raise PublicBenchmarkSuiteMaterializationError(
            "public benchmark input root must be a directory"
        )
    return _materialize_suite_with_loader(
        protocol,
        _directory_loader(root),
        limits=limits,
    )


def materialize_frozen_public_benchmark_input_suite_from_directory(
    input_root: str | os.PathLike[str],
    *,
    limits: PublicReferenceMaterializationLimits | None = None,
) -> PublicBenchmarkSuiteMaterializationReceipt:
    """Read exact frozen relative paths from a non-symlink local directory."""

    return materialize_public_benchmark_input_suite_from_directory(
        frozen_public_benchmark_protocol(),
        input_root,
        limits=limits,
    )


def require_frozen_public_benchmark_input_suite_receipt(
    receipt: PublicBenchmarkSuiteMaterializationReceipt,
) -> PublicBenchmarkSuiteMaterializationReceipt:
    """Require exact agreement with the repository's frozen four-case protocol."""

    if not isinstance(receipt, PublicBenchmarkSuiteMaterializationReceipt):
        raise PublicBenchmarkSuiteMaterializationError(
            "receipt must be PublicBenchmarkSuiteMaterializationReceipt"
        )
    return receipt.require_protocol(frozen_public_benchmark_protocol())


def write_public_benchmark_input_suite_receipt(
    receipt: PublicBenchmarkSuiteMaterializationReceipt,
    output_path: str | os.PathLike[str],
) -> Path:
    """Write a receipt with mode 0600 and refuse to replace an existing path."""

    if not isinstance(receipt, PublicBenchmarkSuiteMaterializationReceipt):
        raise PublicBenchmarkSuiteMaterializationError(
            "receipt must be PublicBenchmarkSuiteMaterializationReceipt"
        )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(receipt.to_json_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PublicBenchmarkSuiteMaterializationError(
                "public suite receipt output already exists"
            ) from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-public-materialize",
        description=(
            "Verify and materialize the frozen four-case public input suite "
            "offline. This does not run docking or create benchmark results."
        ),
    )
    parser.add_argument(
        "--input-root",
        required=True,
        help="directory containing the exact frozen upstream relative paths",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="new receipt path, or '-' for stdout (default: '-')",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli_parser().parse_args(argv)
    try:
        receipt = materialize_frozen_public_benchmark_input_suite_from_directory(
            args.input_root
        )
        if args.output == "-":
            sys.stdout.buffer.write(receipt.to_json_bytes())
        else:
            write_public_benchmark_input_suite_receipt(receipt, args.output)
    except (OSError, PublicBenchmarkSuiteMaterializationError) as exc:
        print(f"public input materialization failed: {exc}", file=sys.stderr)
        return 2
    return 0 if receipt.input_materialization_complete else 3


__all__ = [
    "MAX_PUBLIC_BENCHMARK_SUITE_RECEIPT_BYTES",
    "PUBLIC_BENCHMARK_ARTIFACT_OBSERVATION_SCHEMA_ID",
    "PUBLIC_BENCHMARK_SUITE_CASE_MATERIALIZATION_SCHEMA_ID",
    "PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCHEMA_ID",
    "PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCIENTIFIC_BLOCKERS",
    "PublicBenchmarkArtifactObservation",
    "PublicBenchmarkSuiteCaseMaterialization",
    "PublicBenchmarkSuiteMaterializationError",
    "PublicBenchmarkSuiteMaterializationReceipt",
    "main",
    "materialize_frozen_public_benchmark_input_suite_from_directory",
    "materialize_public_benchmark_input_suite",
    "materialize_public_benchmark_input_suite_from_directory",
    "require_frozen_public_benchmark_input_suite_receipt",
    "write_public_benchmark_input_suite_receipt",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
