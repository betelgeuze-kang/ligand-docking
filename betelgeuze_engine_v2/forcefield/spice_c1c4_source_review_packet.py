"""Strict offline admission of the SPICE C1--C4 source-review packet.

The packet freezes a machine-prefilled review surface around the existing
SPICE 2.0.1 C1--C4 evidence.  It records public metadata observations and the
receipts still required for whole-file and subset-extraction review.  It does
not authenticate publisher identity, replay the 37 GB HDF5 file, perform a
human license review, authorize use, fit parameters, or enable runtime work.
"""

from __future__ import annotations

from dataclasses import InitVar, asdict, dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from .spice_c1c4_quantum_reference import (
    SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID,
    load_spice_c1c4_quantum_reference_evidence,
)


SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID = (
    "betelgeuze.spice_c1_c4_source_authentication_license_review_packet/1.0.0"
)
SPICE_C1C4_SOURCE_REVIEW_PACKET_REPORT_SCHEMA_ID = (
    "betelgeuze.spice_c1_c4_source_review_packet_report/1.0.0"
)
SPICE_C1C4_SOURCE_REVIEW_PACKET_CLAIM_SCOPE = (
    "machine_prefilled_upstream_metadata_and_review_requirements_only"
)
SPICE_C1C4_SOURCE_REVIEW_PACKET_CORE_SHA256 = (
    "a88fa4ead67c5a04ac372715b60e68573981f49cdac95785389e175a2efdee84"
)
SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_SHA256 = (
    "cf1c5179809331e8effb2c22e8dcd746169779b16c71b8629eb16c487c1099ad"
)
SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_BYTE_COUNT = 8933

_FROZEN_SCHEMA_ID = SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID
_FROZEN_REPORT_SCHEMA_ID = SPICE_C1C4_SOURCE_REVIEW_PACKET_REPORT_SCHEMA_ID
_FROZEN_CLAIM_SCOPE = SPICE_C1C4_SOURCE_REVIEW_PACKET_CLAIM_SCOPE
_FROZEN_CORE_SHA256 = SPICE_C1C4_SOURCE_REVIEW_PACKET_CORE_SHA256
_FROZEN_ARTIFACT_SHA256 = SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_SHA256
_FROZEN_ARTIFACT_BYTE_COUNT = SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_BYTE_COUNT
_FROZEN_EVIDENCE_SCHEMA_ID = SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID
_FROZEN_EVIDENCE_CORE_SHA256 = (
    "265c9883c06755cb845dd682b3b16634ea1f0d8ffd76dc60094b2224ab072dae"
)
_FROZEN_EVIDENCE_ARTIFACT_SHA256 = (
    "ffa884e94f624b89ac8602cda8ff01f363f60838e4efc1c2a3c0a057bf94c0a3"
)
_FROZEN_EVIDENCE_ARTIFACT_BYTE_COUNT = 251253
_MAX_PACKET_BYTES = 64 * 1024
_LOWER_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REPORT_FACTORY_TOKEN = object()

_TOP_KEYS = frozenset(
    {
        "artifact_purpose",
        "claim_scope",
        "core_sha256",
        "doi_record_metadata_snapshot",
        "identity_boundary",
        "license_review",
        "nonpromotion",
        "repository_release_snapshot",
        "schema_id",
        "source_evidence_binding",
        "subset_extraction_review",
        "whole_file_expected_identity",
    }
)
_DOI_KEYS = frozenset(
    {
        "captured_at_utc",
        "concept_doi",
        "created_at_utc",
        "doi",
        "doi_url",
        "endpoint_url",
        "file_byte_count",
        "file_checksum_algorithm",
        "file_checksum_hex",
        "file_content_url",
        "file_id",
        "file_name",
        "file_version_id",
        "http_etag",
        "http_status",
        "license_id",
        "normalized_projection_integrity_bound",
        "provider",
        "publication_date",
        "publisher_identity_authenticated",
        "publisher_signature_present",
        "record_id",
        "record_url",
        "resource_type",
        "revision",
        "snapshot_kind",
        "title",
        "updated_at_utc",
        "version",
    }
)
_IDENTITY_KEYS = frozenset(
    {
        "checksum_match_is_publisher_identity_authentication",
        "cryptographic_publisher_identity_authenticated",
        "cryptographic_publisher_signature_present",
        "doi_is_publisher_signature",
        "doi_record_metadata_snapshot_bound",
        "git_tag_is_signed",
        "https_snapshot_is_publisher_signature",
        "md5_is_collision_resistant",
        "repository_release_snapshot_bound",
        "upstream_checksum_declaration_bound",
    }
)
_LICENSE_KEYS = frozenset(
    {
        "commercial_use_authorized",
        "human_attestation_sha256",
        "human_decision",
        "human_review_status",
        "human_reviewed_at_utc",
        "human_reviewer_id",
        "intended_use_scope_questions",
        "legal_advice_provided",
        "license_human_reviewed",
        "observed_declarations",
        "redistribution_authorized",
        "scope_interpretation_status",
    }
)
_DECLARATION_KEYS = frozenset(
    {"declared_context", "declared_identifier", "locator", "source"}
)
_NONPROMOTION_KEYS = frozenset(
    {
        "candidate_fitting_performed",
        "candidate_parameter_set_available",
        "claim_safe",
        "cryptographic_publisher_identity_authenticated",
        "execution_authorized",
        "license_human_reviewed",
        "license_use_authorized",
        "parameter_family_sufficiency_assessed",
        "parameterability_assessed",
        "parameterizable",
        "physics_ready",
        "production_parameters_available",
        "reference_validation_performed",
        "repository_release_projection_bound",
        "review_packet_integrity",
        "runtime_eligible",
        "source_whole_file_authenticated",
        "subset_extraction_authenticated",
        "upstream_metadata_projection_bound",
    }
)
_REPOSITORY_KEYS = frozenset(
    {
        "commit_verification_status",
        "cryptographic_publisher_identity_authenticated",
        "dataset_artifact_digest_published_in_repository_release",
        "license_byte_count",
        "license_context",
        "license_git_blob_sha1",
        "license_immutable_url",
        "license_path",
        "license_sha256",
        "license_text_heading_observed",
        "provider",
        "readme_byte_count",
        "readme_dataset_license_declaration_observed",
        "readme_git_blob_sha1",
        "readme_immutable_url",
        "readme_path",
        "readme_sha256",
        "release_api_url",
        "release_id",
        "repository_url",
        "snapshot_integrity_bound",
        "tag_kind",
        "tag_name",
        "tag_signature_present",
        "tag_target_commit",
    }
)
_EVIDENCE_KEYS = frozenset(
    {
        "evidence_artifact_byte_count",
        "evidence_artifact_sha256",
        "evidence_core_sha256",
        "evidence_group_count",
        "evidence_record_count",
        "evidence_schema_id",
        "qcarchive_dataset_id",
        "qcarchive_dataset_name",
        "qcarchive_dataset_type",
        "qcarchive_server_url",
        "qcarchive_specification_name",
        "source_doi",
        "source_release",
    }
)
_EXTRACTION_KEYS = frozenset(
    {
        "admitted_subset_bound_to_whole_file",
        "expected_dataset_names",
        "expected_group_count",
        "expected_group_ids",
        "expected_record_count",
        "expected_records_per_group",
        "expected_source_array_sha256",
        "extracted_arrays_match_evidence",
        "extraction_receipt_sha256",
        "extraction_replayed",
        "future_receipt_required_fields",
        "future_receipt_schema_id",
        "observed_shapes_and_dtypes",
        "receipt_status",
        "selection_order_receipt",
        "selection_protocol_id",
        "source_hdf5_dataset_paths",
        "source_hdf5_group_paths",
        "whole_file_stream_receipt_sha256",
    }
)
_ARRAY_HASH_KEYS = frozenset(
    {"conformations", "dft_total_energy", "dft_total_gradient", "group_id"}
)
_WHOLE_FILE_KEYS = frozenset(
    {
        "artifact_name",
        "expected_byte_count",
        "expected_download_url",
        "local_full_stream_completed",
        "local_full_stream_receipt_schema_id",
        "local_full_stream_receipt_sha256",
        "local_observed_byte_count",
        "local_observed_md5",
        "local_observed_sha256",
        "source_whole_file_authenticated",
        "upstream_byte_count_matched",
        "upstream_checksum_algorithm",
        "upstream_checksum_declaration_source",
        "upstream_checksum_hex",
        "upstream_checksum_matched",
        "whole_file_byte_identity_established",
    }
)

_EXPECTED_DOI_VALUES: Mapping[str, Any] = {
    "captured_at_utc": "2026-07-15T03:01:58Z",
    "concept_doi": "10.5281/zenodo.7258939",
    "created_at_utc": "2024-04-15T20:08:22.850341Z",
    "doi": "10.5281/zenodo.10975225",
    "doi_url": "https://doi.org/10.5281/zenodo.10975225",
    "endpoint_url": "https://zenodo.org/api/records/10975225",
    "file_byte_count": 37479271148,
    "file_checksum_algorithm": "md5",
    "file_checksum_hex": "bfba2224b6540e1390a579569b475510",
    "file_content_url": (
        "https://zenodo.org/api/records/10975225/files/SPICE-2.0.1.hdf5/content"
    ),
    "file_id": "0680b54c-17a3-4d17-bdd0-6385b2733181",
    "file_name": "SPICE-2.0.1.hdf5",
    "file_version_id": "4792aaf4-e39a-4f1f-bc2b-b96c10f82f56",
    "http_etag": '"10"',
    "http_status": 200,
    "license_id": "cc-zero",
    "normalized_projection_integrity_bound": True,
    "provider": "zenodo",
    "publication_date": "2024-04-15",
    "publisher_identity_authenticated": False,
    "publisher_signature_present": False,
    "record_id": 10975225,
    "record_url": "https://zenodo.org/api/records/10975225",
    "resource_type": "dataset",
    "revision": 10,
    "snapshot_kind": "normalized_selected_public_https_metadata_projection",
    "title": "SPICE 2.0.1",
    "updated_at_utc": "2025-01-23T18:26:59.658548Z",
    "version": "2.0.1",
}
_EXPECTED_REPOSITORY_VALUES: Mapping[str, Any] = {
    "commit_verification_status": "verified",
    "cryptographic_publisher_identity_authenticated": False,
    "dataset_artifact_digest_published_in_repository_release": False,
    "license_byte_count": 1063,
    "license_context": "repository_software_not_assumed_to_cover_dataset",
    "license_git_blob_sha1": "50f1780a253f5500b62f3567c6a3c96d66090b88",
    "license_immutable_url": (
        "https://raw.githubusercontent.com/openmm/spice-dataset/"
        "b99b3f4d85585df6bdfeca5a56420c57ec6385f1/LICENSE"
    ),
    "license_path": "LICENSE",
    "license_sha256": (
        "901d147cf9eebbd366dbf2246ed408f156ad4e7349d22992d65b6cc7bf4ee8c8"
    ),
    "license_text_heading_observed": "MIT License",
    "provider": "github",
    "readme_byte_count": 5603,
    "readme_dataset_license_declaration_observed": "CC0_public_domain_equivalent",
    "readme_git_blob_sha1": "c73d94582a4f18cb479f8cae16ddfead07b63297",
    "readme_immutable_url": (
        "https://raw.githubusercontent.com/openmm/spice-dataset/"
        "b99b3f4d85585df6bdfeca5a56420c57ec6385f1/README.md"
    ),
    "readme_path": "README.md",
    "readme_sha256": (
        "27218a14f9d4990366a1475395111aa0f0ac815b2dafd2f881a6437dfd20d602"
    ),
    "release_api_url": (
        "https://api.github.com/repos/openmm/spice-dataset/releases/151245684"
    ),
    "release_id": 151245684,
    "repository_url": "https://github.com/openmm/spice-dataset",
    "snapshot_integrity_bound": True,
    "tag_kind": "lightweight",
    "tag_name": "2.0.1",
    "tag_signature_present": False,
    "tag_target_commit": "b99b3f4d85585df6bdfeca5a56420c57ec6385f1",
}
_EXPECTED_GROUP_HASHES = (
    (
        "c",
        "5e51aa7b5a92bc55c5ed748354e2bf276e62ed38ff6b53e2146ad285d3e90bb1",
        "fdfb9a790a01d89163c78acfead0b2ed321852b02aa5839c899b232934864a93",
        "235fb701e31f64467539ad57feeedac71235761432dd1451057fb4ed866d756f",
    ),
    (
        "cc",
        "25934750eb828dc436b96bcb3a7ac3ced2474ad0b9a76f99ab265b02575a7b11",
        "670e02f3617347843d0c4e913e84403776bc4531d51661491056e7dd1b0dc0e7",
        "5bb929b00b333ed00e096f0e1b4b71f65cfed3cb016fae76042b7567b9a22420",
    ),
    (
        "ccc",
        "4802ecb632be7f2245be9c6ba6248d9244c8c46b1f7d24f92b9c897021999665",
        "f589866974752c41f7d4005838273703f16e143e7a362376fb96b72604ef8978",
        "80145f7ca4297bf7dc7df12529567bb4e91a0dfa8a64c3ea3b74809a074616a2",
    ),
    (
        "cccc",
        "2fe76411ce91fd3c57ffc592d4712c46496c4f3fc0dde95cdc3e61cedc0b95a9",
        "1181069e78c8190aaa21095f07fa4beac400c3c18751a615779a87001a9206aa",
        "768fd1a07a9067d9bfc4ead711c0aaf7f5fbb2111c872d2464ba9ce010d7704e",
    ),
)


class SpiceC1C4SourceReviewPacketContractError(ValueError):
    """Raised when the frozen source-review packet violates its contract."""


@dataclass(frozen=True, slots=True)
class SpiceC1C4SourceReviewPacket:
    schema_id: str
    claim_scope: str
    core_sha256: str
    artifact_sha256: str
    artifact_byte_count: int
    source_evidence_artifact_sha256: str
    zenodo_record_id: int
    zenodo_record_revision: int
    zenodo_snapshot_etag: str
    github_release_id: int
    github_tag_target_commit: str
    expected_whole_file_byte_count: int
    upstream_checksum_algorithm: str
    upstream_checksum_hex: str
    expected_group_ids: tuple[str, ...]
    future_extraction_required_fields: tuple[str, ...]
    observed_license_declaration_count: int


@dataclass(frozen=True, slots=True)
class SpiceC1C4SourceReviewPacketReport:
    _factory_token: InitVar[object]
    schema_id: str
    packet_schema_id: str
    claim_scope: str
    source_evidence_artifact_sha256: str
    packet_core_sha256: str
    packet_artifact_sha256: str
    packet_artifact_byte_count: int
    zenodo_record_id: int
    zenodo_record_revision: int
    zenodo_snapshot_etag: str
    github_release_id: int
    github_tag_target_commit: str
    expected_whole_file_byte_count: int
    upstream_checksum_algorithm: str
    upstream_checksum_hex: str
    source_group_count: int
    source_record_count: int
    source_array_hash_row_count: int
    future_extraction_required_field_count: int
    observed_license_declaration_count: int
    human_review_status: str
    review_packet_integrity: bool = True
    upstream_metadata_projection_bound: bool = True
    repository_release_projection_bound: bool = True
    upstream_checksum_declaration_bound: bool = True
    local_whole_file_stream_completed: bool = False
    upstream_byte_count_matched: bool = False
    upstream_checksum_matched: bool = False
    whole_file_byte_identity_established: bool = False
    subset_extraction_receipt_available: bool = False
    subset_extraction_replayed: bool = False
    admitted_subset_bound_to_whole_file: bool = False
    source_whole_file_authenticated: bool = False
    license_human_reviewed: bool = False
    commercial_use_authorized: bool = False
    redistribution_authorized: bool = False
    legal_advice_provided: bool = False
    cryptographic_publisher_signature_present: bool = False
    cryptographic_publisher_identity_authenticated: bool = False
    candidate_fitting_performed: bool = False
    candidate_parameter_set_available: bool = False
    parameter_family_sufficiency_assessed: bool = False
    reference_validation_performed: bool = False
    production_parameters_available: bool = False
    parameterability_assessed: bool = False
    parameterizable: bool = False
    physics_ready: bool = False
    runtime_eligible: bool = False
    execution_authorized: bool = False
    claim_safe: bool = False

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _REPORT_FACTORY_TOKEN:
            raise TypeError(
                "source-review reports are factory-only; replay evidence and packet bytes"
            )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SpiceC1C4SourceReviewPacketContractError(
                f"duplicate JSON key {key!r}"
            )
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise SpiceC1C4SourceReviewPacketContractError(
        f"non-standard JSON constant {value!r} is prohibited"
    )


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise SpiceC1C4SourceReviewPacketContractError(
            f"canonical JSON encoding failed: {exc}"
        ) from exc


def _core_sha256(document: Mapping[str, Any]) -> str:
    core = dict(document)
    core.pop("core_sha256", None)
    return hashlib.sha256(_canonical_json_bytes(core)).hexdigest()


def _exact_object(
    value: Any,
    expected_keys: frozenset[str],
    location: str,
) -> dict[str, Any]:
    if type(value) is not dict:
        raise SpiceC1C4SourceReviewPacketContractError(
            f"{location} must be an exact JSON object"
        )
    observed = set(value)
    if observed != expected_keys:
        raise SpiceC1C4SourceReviewPacketContractError(
            f"{location} keys mismatch: "
            f"missing={sorted(expected_keys - observed)}, "
            f"unexpected={sorted(observed - expected_keys)}"
        )
    return value


def _require_exact(value: Any, expected: Any, location: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise SpiceC1C4SourceReviewPacketContractError(
            f"{location} does not match the frozen source-review contract"
        )


def _require_sha256(value: Any, location: str) -> str:
    if type(value) is not str or _LOWER_SHA256.fullmatch(value) is None:
        raise SpiceC1C4SourceReviewPacketContractError(
            f"{location} must be a lowercase SHA-256 digest"
        )
    return value


def _parse_packet(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TypeError("SPICE source-review packet must be exact bytes")
    if not data:
        raise SpiceC1C4SourceReviewPacketContractError(
            "SPICE source-review packet must not be empty"
        )
    if len(data) > _MAX_PACKET_BYTES:
        raise SpiceC1C4SourceReviewPacketContractError(
            "SPICE source-review packet exceeds the fixed byte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise SpiceC1C4SourceReviewPacketContractError(
            "SPICE source-review packet must be strict ASCII"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except SpiceC1C4SourceReviewPacketContractError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise SpiceC1C4SourceReviewPacketContractError(
            f"invalid SPICE source-review JSON: {exc}"
        ) from exc
    document = _exact_object(value, _TOP_KEYS, "packet")
    if _canonical_json_bytes(document) != data:
        raise SpiceC1C4SourceReviewPacketContractError(
            "SPICE source-review packet is not canonical ASCII JSON"
        )
    return document


def _validate_exact_mapping(
    value: Any,
    *,
    keys: frozenset[str],
    expected: Mapping[str, Any],
    location: str,
) -> dict[str, Any]:
    document = _exact_object(value, keys, location)
    _require_exact(document, dict(expected), location)
    return document


def _validate_metadata_and_boundaries(document: Mapping[str, Any]) -> None:
    _require_exact(document["schema_id"], _FROZEN_SCHEMA_ID, "schema_id")
    _require_exact(
        document["artifact_purpose"],
        "machine_prefilled_source_authentication_and_license_review_packet_only",
        "artifact_purpose",
    )
    _require_exact(document["claim_scope"], _FROZEN_CLAIM_SCOPE, "claim_scope")
    _validate_exact_mapping(
        document["doi_record_metadata_snapshot"],
        keys=_DOI_KEYS,
        expected=_EXPECTED_DOI_VALUES,
        location="doi_record_metadata_snapshot",
    )
    _validate_exact_mapping(
        document["repository_release_snapshot"],
        keys=_REPOSITORY_KEYS,
        expected=_EXPECTED_REPOSITORY_VALUES,
        location="repository_release_snapshot",
    )
    _validate_exact_mapping(
        document["identity_boundary"],
        keys=_IDENTITY_KEYS,
        expected={
            "checksum_match_is_publisher_identity_authentication": False,
            "cryptographic_publisher_identity_authenticated": False,
            "cryptographic_publisher_signature_present": False,
            "doi_is_publisher_signature": False,
            "doi_record_metadata_snapshot_bound": True,
            "git_tag_is_signed": False,
            "https_snapshot_is_publisher_signature": False,
            "md5_is_collision_resistant": False,
            "repository_release_snapshot_bound": True,
            "upstream_checksum_declaration_bound": True,
        },
        location="identity_boundary",
    )


def _validate_evidence_binding(
    document: Mapping[str, Any],
    *,
    evidence_artifact_sha256: str,
    evidence_artifact_byte_count: int,
    evidence_core_sha256: str,
    evidence_group_count: int,
    evidence_record_count: int,
) -> None:
    expected = {
        "evidence_artifact_byte_count": _FROZEN_EVIDENCE_ARTIFACT_BYTE_COUNT,
        "evidence_artifact_sha256": _FROZEN_EVIDENCE_ARTIFACT_SHA256,
        "evidence_core_sha256": _FROZEN_EVIDENCE_CORE_SHA256,
        "evidence_group_count": 4,
        "evidence_record_count": 200,
        "evidence_schema_id": _FROZEN_EVIDENCE_SCHEMA_ID,
        "qcarchive_dataset_id": 340,
        "qcarchive_dataset_name": "SPICE DES Monomers Single Points Dataset v1.1",
        "qcarchive_dataset_type": "singlepoint",
        "qcarchive_server_url": "https://ml.qcarchive.molssi.org",
        "qcarchive_specification_name": "spec_4",
        "source_doi": "10.5281/zenodo.10975225",
        "source_release": "SPICE 2.0.1",
    }
    _validate_exact_mapping(
        document["source_evidence_binding"],
        keys=_EVIDENCE_KEYS,
        expected=expected,
        location="source_evidence_binding",
    )
    observed = (
        evidence_artifact_sha256,
        evidence_artifact_byte_count,
        evidence_core_sha256,
        evidence_group_count,
        evidence_record_count,
    )
    required = (
        _FROZEN_EVIDENCE_ARTIFACT_SHA256,
        _FROZEN_EVIDENCE_ARTIFACT_BYTE_COUNT,
        _FROZEN_EVIDENCE_CORE_SHA256,
        4,
        200,
    )
    _require_exact(observed, required, "source_evidence_binding.replayed_evidence")


def _validate_extraction_review(
    value: Any,
    *,
    replayed_group_hashes: tuple[tuple[str, str, str, str], ...],
) -> dict[str, Any]:
    document = _exact_object(value, _EXTRACTION_KEYS, "subset_extraction_review")
    _require_exact(
        document["expected_dataset_names"],
        ["conformations", "dft_total_energy", "dft_total_gradient"],
        "subset_extraction_review.expected_dataset_names",
    )
    _require_exact(
        document["expected_group_ids"],
        ["c", "cc", "ccc", "cccc"],
        "subset_extraction_review.expected_group_ids",
    )
    for key, expected in (
        ("expected_group_count", 4),
        ("expected_record_count", 200),
        ("expected_records_per_group", 50),
        (
            "future_receipt_schema_id",
            "betelgeuze.spice_c1_c4_subset_extraction_receipt/1.0.0",
        ),
        ("receipt_status", "missing"),
    ):
        _require_exact(document[key], expected, f"subset_extraction_review.{key}")
    required_fields = [
        "whole_file_stream_receipt_sha256",
        "extractor_implementation_id",
        "source_hdf5_group_paths",
        "source_hdf5_dataset_paths",
        "selection_protocol_id",
        "selection_order",
        "dataset_shapes",
        "dataset_dtypes",
        "per_group_source_array_sha256",
        "evidence_core_sha256",
        "evidence_artifact_sha256",
    ]
    _require_exact(
        document["future_receipt_required_fields"],
        required_fields,
        "subset_extraction_review.future_receipt_required_fields",
    )
    for key in (
        "extraction_receipt_sha256",
        "observed_shapes_and_dtypes",
        "selection_order_receipt",
        "selection_protocol_id",
        "source_hdf5_dataset_paths",
        "source_hdf5_group_paths",
        "whole_file_stream_receipt_sha256",
    ):
        _require_exact(document[key], None, f"subset_extraction_review.{key}")
    for key in (
        "admitted_subset_bound_to_whole_file",
        "extracted_arrays_match_evidence",
        "extraction_replayed",
    ):
        _require_exact(document[key], False, f"subset_extraction_review.{key}")
    rows = document["expected_source_array_sha256"]
    if type(rows) is not list or len(rows) != 4:
        raise SpiceC1C4SourceReviewPacketContractError(
            "subset_extraction_review.expected_source_array_sha256 must have four rows"
        )
    observed_hashes: list[tuple[str, str, str, str]] = []
    for index, row_value in enumerate(rows):
        row = _exact_object(
            row_value,
            _ARRAY_HASH_KEYS,
            f"subset_extraction_review.expected_source_array_sha256[{index}]",
        )
        for field in ("conformations", "dft_total_energy", "dft_total_gradient"):
            _require_sha256(row[field], f"source_array[{index}].{field}")
        observed_hashes.append(
            (
                row["group_id"],
                row["conformations"],
                row["dft_total_energy"],
                row["dft_total_gradient"],
            )
        )
    _require_exact(
        tuple(observed_hashes),
        _EXPECTED_GROUP_HASHES,
        "subset_extraction_review.expected_source_array_sha256",
    )
    _require_exact(
        replayed_group_hashes,
        _EXPECTED_GROUP_HASHES,
        "subset_extraction_review.replayed_group_hashes",
    )
    return document


def _validate_whole_file(value: Any) -> dict[str, Any]:
    expected = {
        "artifact_name": "SPICE-2.0.1.hdf5",
        "expected_byte_count": 37479271148,
        "expected_download_url": (
            "https://zenodo.org/api/records/10975225/files/SPICE-2.0.1.hdf5/content"
        ),
        "local_full_stream_completed": False,
        "local_full_stream_receipt_schema_id": (
            "betelgeuze.spice_c1_c4_whole_file_stream_receipt/1.0.0"
        ),
        "local_full_stream_receipt_sha256": None,
        "local_observed_byte_count": None,
        "local_observed_md5": None,
        "local_observed_sha256": None,
        "source_whole_file_authenticated": False,
        "upstream_byte_count_matched": False,
        "upstream_checksum_algorithm": "md5",
        "upstream_checksum_declaration_source": "zenodo_record_metadata_snapshot",
        "upstream_checksum_hex": "bfba2224b6540e1390a579569b475510",
        "upstream_checksum_matched": False,
        "whole_file_byte_identity_established": False,
    }
    return _validate_exact_mapping(
        value,
        keys=_WHOLE_FILE_KEYS,
        expected=expected,
        location="whole_file_expected_identity",
    )


def _validate_license_review(value: Any) -> dict[str, Any]:
    document = _exact_object(value, _LICENSE_KEYS, "license_review")
    _require_exact(document["human_review_status"], "pending", "human_review_status")
    _require_exact(
        document["scope_interpretation_status"],
        "pending_human_review",
        "scope_interpretation_status",
    )
    for key in (
        "human_attestation_sha256",
        "human_decision",
        "human_reviewed_at_utc",
        "human_reviewer_id",
    ):
        _require_exact(document[key], None, f"license_review.{key}")
    for key in (
        "commercial_use_authorized",
        "legal_advice_provided",
        "license_human_reviewed",
        "redistribution_authorized",
    ):
        _require_exact(document[key], False, f"license_review.{key}")
    _require_exact(
        document["intended_use_scope_questions"],
        [
            "commercial_use_of_dataset_derived_force_field_parameters",
            "redistribution_of_admitted_subset_or_derived_artifacts",
            "attribution_notice_and_provenance_requirements",
            "scope_relationship_between_dataset_cc0_and_repository_mit",
        ],
        "license_review.intended_use_scope_questions",
    )
    declarations = document["observed_declarations"]
    if type(declarations) is not list or len(declarations) != 3:
        raise SpiceC1C4SourceReviewPacketContractError(
            "license_review.observed_declarations must have three rows"
        )
    for index, declaration in enumerate(declarations):
        _exact_object(
            declaration,
            _DECLARATION_KEYS,
            f"license_review.observed_declarations[{index}]",
        )
    expected = [
        {
            "declared_context": "dataset_record_metadata",
            "declared_identifier": "cc-zero",
            "locator": "https://zenodo.org/api/records/10975225",
            "source": "zenodo_record_metadata",
        },
        {
            "declared_context": "dataset_statement",
            "declared_identifier": "CC0_public_domain_equivalent",
            "locator": (
                "https://raw.githubusercontent.com/openmm/spice-dataset/"
                "b99b3f4d85585df6bdfeca5a56420c57ec6385f1/README.md"
            ),
            "source": "github_readme",
        },
        {
            "declared_context": "repository_software_not_assumed_to_cover_dataset",
            "declared_identifier": "MIT",
            "locator": (
                "https://raw.githubusercontent.com/openmm/spice-dataset/"
                "b99b3f4d85585df6bdfeca5a56420c57ec6385f1/LICENSE"
            ),
            "source": "github_license_file",
        },
    ]
    _require_exact(declarations, expected, "license_review.observed_declarations")
    return document


def _validate_nonpromotion(value: Any) -> dict[str, Any]:
    expected: dict[str, Any] = {
        "candidate_fitting_performed": False,
        "candidate_parameter_set_available": False,
        "claim_safe": False,
        "cryptographic_publisher_identity_authenticated": False,
        "execution_authorized": False,
        "license_human_reviewed": False,
        "license_use_authorized": False,
        "parameter_family_sufficiency_assessed": False,
        "parameterability_assessed": False,
        "parameterizable": False,
        "physics_ready": False,
        "production_parameters_available": False,
        "reference_validation_performed": False,
        "repository_release_projection_bound": True,
        "review_packet_integrity": True,
        "runtime_eligible": False,
        "source_whole_file_authenticated": False,
        "subset_extraction_authenticated": False,
        "upstream_metadata_projection_bound": True,
    }
    return _validate_exact_mapping(
        value,
        keys=_NONPROMOTION_KEYS,
        expected=expected,
        location="nonpromotion",
    )


def load_spice_c1c4_source_review_packet(
    evidence_data: bytes,
    packet_data: bytes,
) -> SpiceC1C4SourceReviewPacket:
    """Replay source evidence, then admit the one frozen offline review packet."""

    corpus = load_spice_c1c4_quantum_reference_evidence(evidence_data)
    document = _parse_packet(packet_data)
    _validate_metadata_and_boundaries(document)
    _validate_evidence_binding(
        document,
        evidence_artifact_sha256=corpus.artifact_sha256,
        evidence_artifact_byte_count=corpus.artifact_byte_count,
        evidence_core_sha256=corpus.core_sha256,
        evidence_group_count=len(corpus.groups),
        evidence_record_count=len(corpus.records),
    )
    replayed_group_hashes = tuple(
        (
            group.group_id,
            group.conformations_sha256,
            group.energies_sha256,
            group.gradients_sha256,
        )
        for group in corpus.groups
    )
    extraction = _validate_extraction_review(
        document["subset_extraction_review"],
        replayed_group_hashes=replayed_group_hashes,
    )
    whole_file = _validate_whole_file(document["whole_file_expected_identity"])
    license_review = _validate_license_review(document["license_review"])
    _validate_nonpromotion(document["nonpromotion"])

    supplied_core_sha256 = _require_sha256(document["core_sha256"], "core_sha256")
    computed_core_sha256 = _core_sha256(document)
    if computed_core_sha256 != supplied_core_sha256:
        raise SpiceC1C4SourceReviewPacketContractError(
            "SPICE source-review packet core self-hash mismatch"
        )
    artifact_sha256 = hashlib.sha256(packet_data).hexdigest()
    if supplied_core_sha256 != _FROZEN_CORE_SHA256:
        raise SpiceC1C4SourceReviewPacketContractError(
            "SPICE source-review packet is not the frozen reviewed core"
        )
    if (
        artifact_sha256 != _FROZEN_ARTIFACT_SHA256
        or len(packet_data) != _FROZEN_ARTIFACT_BYTE_COUNT
    ):
        raise SpiceC1C4SourceReviewPacketContractError(
            "SPICE source-review bytes are not the frozen reviewed artifact"
        )

    doi_snapshot = document["doi_record_metadata_snapshot"]
    repository_snapshot = document["repository_release_snapshot"]
    declarations = license_review["observed_declarations"]
    assert type(doi_snapshot) is dict
    assert type(repository_snapshot) is dict
    assert type(declarations) is list
    return SpiceC1C4SourceReviewPacket(
        schema_id=_FROZEN_SCHEMA_ID,
        claim_scope=_FROZEN_CLAIM_SCOPE,
        core_sha256=supplied_core_sha256,
        artifact_sha256=artifact_sha256,
        artifact_byte_count=len(packet_data),
        source_evidence_artifact_sha256=corpus.artifact_sha256,
        zenodo_record_id=doi_snapshot["record_id"],
        zenodo_record_revision=doi_snapshot["revision"],
        zenodo_snapshot_etag=doi_snapshot["http_etag"],
        github_release_id=repository_snapshot["release_id"],
        github_tag_target_commit=repository_snapshot["tag_target_commit"],
        expected_whole_file_byte_count=whole_file["expected_byte_count"],
        upstream_checksum_algorithm=whole_file["upstream_checksum_algorithm"],
        upstream_checksum_hex=whole_file["upstream_checksum_hex"],
        expected_group_ids=tuple(extraction["expected_group_ids"]),
        future_extraction_required_fields=tuple(
            extraction["future_receipt_required_fields"]
        ),
        observed_license_declaration_count=len(declarations),
    )


def analyze_spice_c1c4_source_review_packet(
    evidence_data: bytes,
    packet_data: bytes,
) -> SpiceC1C4SourceReviewPacketReport:
    """Report packet readiness without closing authentication or legal gates."""

    packet = load_spice_c1c4_source_review_packet(evidence_data, packet_data)
    return SpiceC1C4SourceReviewPacketReport(
        _factory_token=_REPORT_FACTORY_TOKEN,
        schema_id=_FROZEN_REPORT_SCHEMA_ID,
        packet_schema_id=packet.schema_id,
        claim_scope=packet.claim_scope,
        source_evidence_artifact_sha256=packet.source_evidence_artifact_sha256,
        packet_core_sha256=packet.core_sha256,
        packet_artifact_sha256=packet.artifact_sha256,
        packet_artifact_byte_count=packet.artifact_byte_count,
        zenodo_record_id=packet.zenodo_record_id,
        zenodo_record_revision=packet.zenodo_record_revision,
        zenodo_snapshot_etag=packet.zenodo_snapshot_etag,
        github_release_id=packet.github_release_id,
        github_tag_target_commit=packet.github_tag_target_commit,
        expected_whole_file_byte_count=packet.expected_whole_file_byte_count,
        upstream_checksum_algorithm=packet.upstream_checksum_algorithm,
        upstream_checksum_hex=packet.upstream_checksum_hex,
        source_group_count=len(packet.expected_group_ids),
        source_record_count=200,
        source_array_hash_row_count=len(packet.expected_group_ids),
        future_extraction_required_field_count=len(
            packet.future_extraction_required_fields
        ),
        observed_license_declaration_count=packet.observed_license_declaration_count,
        human_review_status="pending",
    )


def serialize_spice_c1c4_source_review_packet_report(
    evidence_data: bytes,
    packet_data: bytes,
) -> bytes:
    """Serialize the factory-only nonpromoting source-review report."""

    return _canonical_json_bytes(
        asdict(analyze_spice_c1c4_source_review_packet(evidence_data, packet_data))
    )


__all__ = [
    "SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_BYTE_COUNT",
    "SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_SHA256",
    "SPICE_C1C4_SOURCE_REVIEW_PACKET_CLAIM_SCOPE",
    "SPICE_C1C4_SOURCE_REVIEW_PACKET_CORE_SHA256",
    "SPICE_C1C4_SOURCE_REVIEW_PACKET_REPORT_SCHEMA_ID",
    "SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID",
    "SpiceC1C4SourceReviewPacket",
    "SpiceC1C4SourceReviewPacketContractError",
    "SpiceC1C4SourceReviewPacketReport",
    "analyze_spice_c1c4_source_review_packet",
    "load_spice_c1c4_source_review_packet",
    "serialize_spice_c1c4_source_review_packet_report",
]
