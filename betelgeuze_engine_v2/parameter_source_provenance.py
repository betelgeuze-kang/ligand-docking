"""Reviewed parameter-source provenance without parameter assignment.

This module freezes the identity, release, byte digest, license identity, and
bounded review scope for one public force-field artifact.  It deliberately does
not parse SMIRNOFF, assign atom types or charges, establish molecule coverage,
validate parameter values, or create an all-atom system.  The review state is a
source-provenance contract only and cannot promote scientific or product claims.

No runtime network access is performed.  Callers may independently supply the
two reviewed files to the verification helpers when an offline byte check is
required.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping


PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_parameter_source_provenance/1.0.0"
)
PARAMETER_SOURCE_PROVENANCE_PROFILE_ID = (
    "reviewed_openff_sage_2_2_1_identity_license_scope_only/1.0.0"
)
PARAMETER_SOURCE_PROVENANCE_REVIEW_VERSION = "1.0.0"
FROZEN_PARAMETER_SOURCE_PROVENANCE_SNAPSHOT_SHA256 = (
    "31cca3c605bf009579462435731290b8ff5cf5cf7c10fb7dcc0c24530998293d"
)

PARAMETER_SOURCE_ID = "openforcefield-sage-unconstrained"
PARAMETER_SOURCE_VERSION = "2.2.1"
PARAMETER_SOURCE_RELEASE_TAG = "2024.09.0"
PARAMETER_SOURCE_RELEASE_NAME = "Sage 2.2.1"
PARAMETER_SOURCE_REPOSITORY_URL = (
    "https://github.com/openforcefield/openff-forcefields"
)
PARAMETER_SOURCE_RELEASE_URL = (
    "https://github.com/openforcefield/openff-forcefields/releases/tag/2024.09.0"
)
PARAMETER_SOURCE_COMMIT_SHA = "3fabe581c3c0ca98ae662f1d3e265ff15cdcbca0"
PARAMETER_SOURCE_ARTIFACT_NAME = "openff_unconstrained-2.2.1.offxml"
PARAMETER_SOURCE_ARTIFACT_URL = (
    "https://raw.githubusercontent.com/openforcefield/openff-forcefields/"
    "3fabe581c3c0ca98ae662f1d3e265ff15cdcbca0/openforcefields/offxml/"
    "openff_unconstrained-2.2.1.offxml"
)
PARAMETER_SOURCE_ARTIFACT_SHA256 = (
    "124f46daf213453d33d773497c35b34f29e752a42b658223355072663ba05a47"
)
PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES = 80_580
PARAMETER_SOURCE_FORMAT = "SMIRNOFF OFFXML"

PARAMETER_SOURCE_LICENSE_SPDX_ID = "CC-BY-4.0"
PARAMETER_SOURCE_LICENSE_URL = (
    "https://raw.githubusercontent.com/openforcefield/openff-forcefields/"
    "3fabe581c3c0ca98ae662f1d3e265ff15cdcbca0/LICENSE"
)
PARAMETER_SOURCE_LICENSE_SHA256 = (
    "8e0281df4b7dd386c0b660f7476a74e486036d6d2f2372779e5561961a36e7b7"
)
PARAMETER_SOURCE_LICENSE_SIZE_BYTES = 18_693

PARAMETER_SOURCE_REVIEWED_AT_UTC = "2026-07-16T17:43:35Z"
PARAMETER_SOURCE_REVIEWER_ROLE = "repository_maintainer"
PARAMETER_SOURCE_REVIEWER_IDENTITY_SHA256 = (
    "ffaaea9cebb5975ed140fa0633ea4cb44e1f241f6bc73c916164c0ea5123b584"
)
PARAMETER_SOURCE_REVIEW_STATUS = "reviewed_identity_license_and_scope_only"
PARAMETER_SOURCE_REVIEW_SCOPE = (
    "release_and_commit_identity",
    "artifact_name_size_and_sha256",
    "repository_license_identity_and_text_sha256",
    "bounded_candidate_scope_declaration",
    "nonpromotion_claim_boundary",
)
PARAMETER_SOURCE_EXCLUDED_REVIEW_SCOPE = (
    "smirnoff_semantic_parsing",
    "parameter_assignment",
    "partial_charge_assignment",
    "molecule_parameter_coverage",
    "parameter_value_calibration",
    "force_or_energy_validation",
    "scientific_or_benchmark_validation",
    "legal_compliance_determination",
)
PARAMETER_SOURCE_CANDIDATE_SCOPE = "neutral_acyclic_coh_preparation_graph_only"
PARAMETER_SOURCE_CANDIDATE_ELEMENTS = ("C", "H", "O")
PARAMETER_SOURCE_CANDIDATE_BOND_ORDERS = ("single", "double")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class ParameterSourceProvenanceError(ValueError):
    """Stable fail-closed provenance error without artifact byte disclosure."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"parameter_source_provenance:{self.code}: {self.detail}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "release_provenance_reviewed": True,
        "immutable_source_reference_bound": True,
        "artifact_identity_reviewed": True,
        "artifact_sha256_recorded": True,
        "license_identity_reviewed": True,
        "license_text_sha256_recorded": True,
        "bounded_candidate_scope_declared": True,
        "nonpromotion_boundary_reviewed": True,
        "parameter_source_provenance_reviewed": True,
        "artifact_bundled": False,
        "runtime_network_fetch_enabled": False,
        "source_format_semantically_validated": False,
        "candidate_scope_parameter_coverage_validated": False,
        "parameter_assignment_implemented": False,
        "partial_charge_assigned": False,
        "parameter_values_calibrated": False,
        "force_or_energy_validated": False,
        "applicability_domain_validated": False,
        "legal_compliance_approved": False,
        "all_atom_system_created": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


@dataclass(frozen=True, slots=True, repr=False)
class ParameterSourceProvenanceSnapshot:
    """Immutable result of the bounded source-provenance review."""

    source_id: str
    source_version: str
    release_tag: str
    release_name: str
    repository_url: str
    release_url: str
    source_commit_sha: str
    artifact_name: str
    artifact_url: str
    artifact_sha256: str
    artifact_size_bytes: int
    source_format: str
    license_spdx_id: str
    license_url: str
    license_sha256: str
    license_size_bytes: int
    reviewed_at_utc: str
    reviewer_role: str
    reviewer_identity_sha256: str
    review_status: str
    review_scope: tuple[str, ...]
    excluded_review_scope: tuple[str, ...]
    candidate_scope: str
    candidate_elements: tuple[str, ...]
    candidate_bond_orders: tuple[str, ...]

    def __post_init__(self) -> None:
        required_text = (
            self.source_id,
            self.source_version,
            self.release_tag,
            self.release_name,
            self.repository_url,
            self.release_url,
            self.artifact_name,
            self.artifact_url,
            self.source_format,
            self.license_spdx_id,
            self.license_url,
            self.reviewer_role,
            self.review_status,
            self.candidate_scope,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required_text):
            raise ParameterSourceProvenanceError(
                "invalid_text_field", "provenance text fields must be non-empty"
            )
        if not _COMMIT_RE.fullmatch(self.source_commit_sha):
            raise ParameterSourceProvenanceError(
                "invalid_commit_sha", "source commit must be a lowercase Git SHA-1"
            )
        for name, value in (
            ("artifact_sha256", self.artifact_sha256),
            ("license_sha256", self.license_sha256),
            ("reviewer_identity_sha256", self.reviewer_identity_sha256),
        ):
            if not _SHA256_RE.fullmatch(value):
                raise ParameterSourceProvenanceError(
                    "invalid_sha256", f"{name} must be a lowercase SHA-256 digest"
                )
        if type(self.artifact_size_bytes) is not int or self.artifact_size_bytes <= 0:
            raise ParameterSourceProvenanceError(
                "invalid_artifact_size", "artifact size must be a positive integer"
            )
        if type(self.license_size_bytes) is not int or self.license_size_bytes <= 0:
            raise ParameterSourceProvenanceError(
                "invalid_license_size", "license size must be a positive integer"
            )
        if not _UTC_RE.fullmatch(self.reviewed_at_utc):
            raise ParameterSourceProvenanceError(
                "invalid_review_timestamp", "review timestamp must be second-resolution UTC"
            )
        if (
            not self.review_scope
            or not self.excluded_review_scope
            or not self.candidate_elements
            or not self.candidate_bond_orders
        ):
            raise ParameterSourceProvenanceError(
                "incomplete_review_boundary", "review and candidate scopes must be explicit"
            )
        for values in (
            self.review_scope,
            self.excluded_review_scope,
            self.candidate_elements,
            self.candidate_bond_orders,
        ):
            if len(values) != len(set(values)) or any(
                not isinstance(value, str) or not value for value in values
            ):
                raise ParameterSourceProvenanceError(
                    "invalid_review_boundary", "review scope values must be unique text"
                )

    def __repr__(self) -> str:
        return (
            "ParameterSourceProvenanceSnapshot("
            f"source_id={self.source_id!r}, source_version={self.source_version!r}, "
            f"review_status={self.review_status!r})"
        )

    @property
    def provenance_projection_sha256(self) -> str:
        return _sha256(parameter_source_provenance_projection(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID,
                "provenance_projection_sha256": self.provenance_projection_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID,
            "profile_id": PARAMETER_SOURCE_PROVENANCE_PROFILE_ID,
            "review_version": PARAMETER_SOURCE_PROVENANCE_REVIEW_VERSION,
            "review_status": self.review_status,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "release_tag": self.release_tag,
            "source_commit_sha": self.source_commit_sha,
            "artifact_sha256": self.artifact_sha256,
            "license_spdx_id": self.license_spdx_id,
            "reviewed_at_utc": self.reviewed_at_utc,
            "reviewer_role": self.reviewer_role,
            "reviewer_identity_sha256": self.reviewer_identity_sha256,
            "candidate_scope": self.candidate_scope,
            "provenance_projection_sha256": self.provenance_projection_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def reviewed_parameter_source_provenance() -> ParameterSourceProvenanceSnapshot:
    """Return the frozen, identity-and-license-only provenance review."""

    snapshot = ParameterSourceProvenanceSnapshot(
        source_id=PARAMETER_SOURCE_ID,
        source_version=PARAMETER_SOURCE_VERSION,
        release_tag=PARAMETER_SOURCE_RELEASE_TAG,
        release_name=PARAMETER_SOURCE_RELEASE_NAME,
        repository_url=PARAMETER_SOURCE_REPOSITORY_URL,
        release_url=PARAMETER_SOURCE_RELEASE_URL,
        source_commit_sha=PARAMETER_SOURCE_COMMIT_SHA,
        artifact_name=PARAMETER_SOURCE_ARTIFACT_NAME,
        artifact_url=PARAMETER_SOURCE_ARTIFACT_URL,
        artifact_sha256=PARAMETER_SOURCE_ARTIFACT_SHA256,
        artifact_size_bytes=PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES,
        source_format=PARAMETER_SOURCE_FORMAT,
        license_spdx_id=PARAMETER_SOURCE_LICENSE_SPDX_ID,
        license_url=PARAMETER_SOURCE_LICENSE_URL,
        license_sha256=PARAMETER_SOURCE_LICENSE_SHA256,
        license_size_bytes=PARAMETER_SOURCE_LICENSE_SIZE_BYTES,
        reviewed_at_utc=PARAMETER_SOURCE_REVIEWED_AT_UTC,
        reviewer_role=PARAMETER_SOURCE_REVIEWER_ROLE,
        reviewer_identity_sha256=PARAMETER_SOURCE_REVIEWER_IDENTITY_SHA256,
        review_status=PARAMETER_SOURCE_REVIEW_STATUS,
        review_scope=PARAMETER_SOURCE_REVIEW_SCOPE,
        excluded_review_scope=PARAMETER_SOURCE_EXCLUDED_REVIEW_SCOPE,
        candidate_scope=PARAMETER_SOURCE_CANDIDATE_SCOPE,
        candidate_elements=PARAMETER_SOURCE_CANDIDATE_ELEMENTS,
        candidate_bond_orders=PARAMETER_SOURCE_CANDIDATE_BOND_ORDERS,
    )
    if snapshot.snapshot_sha256 != FROZEN_PARAMETER_SOURCE_PROVENANCE_SNAPSHOT_SHA256:
        raise ParameterSourceProvenanceError(
            "review_snapshot_drift",
            "parameter source provenance drifted from the frozen review boundary",
        )
    return snapshot


def parameter_source_provenance_projection(
    snapshot: ParameterSourceProvenanceSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID,
        "profile_id": PARAMETER_SOURCE_PROVENANCE_PROFILE_ID,
        "review_version": PARAMETER_SOURCE_PROVENANCE_REVIEW_VERSION,
        "source": {
            "source_id": snapshot.source_id,
            "source_version": snapshot.source_version,
            "release_tag": snapshot.release_tag,
            "release_name": snapshot.release_name,
            "repository_url": snapshot.repository_url,
            "release_url": snapshot.release_url,
            "source_commit_sha": snapshot.source_commit_sha,
            "source_format": snapshot.source_format,
        },
        "artifact": {
            "name": snapshot.artifact_name,
            "immutable_url": snapshot.artifact_url,
            "size_bytes": snapshot.artifact_size_bytes,
            "sha256": snapshot.artifact_sha256,
            "bundled": False,
        },
        "license": {
            "spdx_id": snapshot.license_spdx_id,
            "immutable_url": snapshot.license_url,
            "size_bytes": snapshot.license_size_bytes,
            "sha256": snapshot.license_sha256,
            "legal_compliance_determination": False,
        },
        "review": {
            "status": snapshot.review_status,
            "reviewed_at_utc": snapshot.reviewed_at_utc,
            "reviewer_role": snapshot.reviewer_role,
            "reviewer_identity_sha256": snapshot.reviewer_identity_sha256,
            "included_scope": list(snapshot.review_scope),
            "excluded_scope": list(snapshot.excluded_review_scope),
        },
        "candidate_applicability": {
            "scope": snapshot.candidate_scope,
            "elements": list(snapshot.candidate_elements),
            "bond_orders": list(snapshot.candidate_bond_orders),
            "formal_charge": "zero_only",
            "parameter_coverage_validated": False,
            "applicability_domain_validated": False,
        },
        **_claim_policy(),
    }


def parameter_source_provenance_document(
    snapshot: ParameterSourceProvenanceSnapshot | None = None,
) -> dict[str, Any]:
    selected = snapshot or reviewed_parameter_source_provenance()
    projection = parameter_source_provenance_projection(selected)
    return {
        "schema_id": PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID,
        "profile_id": PARAMETER_SOURCE_PROVENANCE_PROFILE_ID,
        "review_version": PARAMETER_SOURCE_PROVENANCE_REVIEW_VERSION,
        "provenance_projection": projection,
        "provenance_projection_sha256": _sha256(projection),
        **selected.to_dict(),
    }


def require_parameter_source_provenance_document(
    payload: object,
) -> Mapping[str, object]:
    """Require exact agreement with the frozen reviewed provenance record."""

    if not isinstance(payload, Mapping):
        raise ValueError("parameter source provenance document must be a mapping")
    document = dict(payload)
    if document != parameter_source_provenance_document():
        raise ValueError("parameter source provenance document drifted from review")
    return payload


def _verify_file(
    path: str | os.PathLike[str],
    *,
    expected_size: int,
    expected_sha256: str,
    kind: str,
) -> str:
    candidate = Path(path)
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise ParameterSourceProvenanceError(
            f"{kind}_unreadable", f"reviewed {kind} file is unavailable"
        ) from exc
    if size != expected_size:
        raise ParameterSourceProvenanceError(
            f"{kind}_size_mismatch", f"reviewed {kind} byte size does not match"
        )
    digest = hashlib.sha256()
    try:
        with candidate.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                digest.update(chunk)
    except OSError as exc:
        raise ParameterSourceProvenanceError(
            f"{kind}_unreadable", f"reviewed {kind} file is unavailable"
        ) from exc
    observed = digest.hexdigest()
    if observed != expected_sha256:
        raise ParameterSourceProvenanceError(
            f"{kind}_digest_mismatch", f"reviewed {kind} SHA-256 does not match"
        )
    return observed


def verify_parameter_source_review_files(
    artifact_path: str | os.PathLike[str],
    license_path: str | os.PathLike[str],
) -> dict[str, str | bool]:
    """Verify caller-supplied reviewed files without fetching or parsing them."""

    artifact_sha256 = _verify_file(
        artifact_path,
        expected_size=PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES,
        expected_sha256=PARAMETER_SOURCE_ARTIFACT_SHA256,
        kind="artifact",
    )
    license_sha256 = _verify_file(
        license_path,
        expected_size=PARAMETER_SOURCE_LICENSE_SIZE_BYTES,
        expected_sha256=PARAMETER_SOURCE_LICENSE_SHA256,
        kind="license",
    )
    return {
        "artifact_sha256": artifact_sha256,
        "license_sha256": license_sha256,
        "source_format_semantically_validated": False,
        "parameter_assignment_implemented": False,
    }


def parameter_source_provenance_json_bytes(
    snapshot: ParameterSourceProvenanceSnapshot | None = None,
) -> bytes:
    return _canonical_bytes(parameter_source_provenance_document(snapshot)) + b"\n"


def write_parameter_source_provenance_json(
    path: str | os.PathLike[str],
    snapshot: ParameterSourceProvenanceSnapshot | None = None,
) -> Path:
    """Atomically write the canonical reviewed provenance document."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=str(output.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(parameter_source_provenance_json_bytes(snapshot))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return output


__all__ = [
    "FROZEN_PARAMETER_SOURCE_PROVENANCE_SNAPSHOT_SHA256",
    "PARAMETER_SOURCE_ARTIFACT_NAME",
    "PARAMETER_SOURCE_ARTIFACT_SHA256",
    "PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES",
    "PARAMETER_SOURCE_ARTIFACT_URL",
    "PARAMETER_SOURCE_CANDIDATE_SCOPE",
    "PARAMETER_SOURCE_COMMIT_SHA",
    "PARAMETER_SOURCE_LICENSE_SHA256",
    "PARAMETER_SOURCE_LICENSE_SPDX_ID",
    "PARAMETER_SOURCE_LICENSE_URL",
    "PARAMETER_SOURCE_PROVENANCE_PROFILE_ID",
    "PARAMETER_SOURCE_PROVENANCE_REVIEW_VERSION",
    "PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID",
    "PARAMETER_SOURCE_RELEASE_URL",
    "PARAMETER_SOURCE_REVIEW_STATUS",
    "ParameterSourceProvenanceError",
    "ParameterSourceProvenanceSnapshot",
    "parameter_source_provenance_document",
    "parameter_source_provenance_json_bytes",
    "parameter_source_provenance_projection",
    "require_parameter_source_provenance_document",
    "reviewed_parameter_source_provenance",
    "verify_parameter_source_review_files",
    "write_parameter_source_provenance_json",
]
