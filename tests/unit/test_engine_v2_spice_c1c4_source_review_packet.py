from __future__ import annotations

import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2 as package_root
import betelgeuze_engine_v2.forcefield as forcefield_api
from betelgeuze_engine_v2.forcefield import spice_c1c4_source_review_packet as module
from betelgeuze_engine_v2.forcefield.spice_c1c4_quantum_reference import (
    SpiceC1C4QuantumReferenceContractError,
)
from betelgeuze_engine_v2.forcefield.spice_c1c4_source_review_packet import (
    SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_BYTE_COUNT,
    SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_SHA256,
    SPICE_C1C4_SOURCE_REVIEW_PACKET_CLAIM_SCOPE,
    SPICE_C1C4_SOURCE_REVIEW_PACKET_CORE_SHA256,
    SPICE_C1C4_SOURCE_REVIEW_PACKET_REPORT_SCHEMA_ID,
    SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID,
    SpiceC1C4SourceReviewPacketContractError,
    SpiceC1C4SourceReviewPacketReport,
    analyze_spice_c1c4_source_review_packet,
    load_spice_c1c4_source_review_packet,
    serialize_spice_c1c4_source_review_packet_report,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_spice_c1c4_quantum_reference_evidence.json"
)
PACKET_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_spice_c1c4_source_review_packet.json"
)
MODULE_PATH = (
    REPOSITORY_ROOT
    / "betelgeuze_engine_v2"
    / "forcefield"
    / "spice_c1c4_source_review_packet.py"
)


def _evidence_bytes() -> bytes:
    return EVIDENCE_PATH.read_bytes()


def _packet_bytes() -> bytes:
    return PACKET_PATH.read_bytes()


def _document() -> dict[str, object]:
    value = json.loads(_packet_bytes())
    assert isinstance(value, dict)
    return value


def _canonical_bytes(document: dict[str, object]) -> bytes:
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


def _rehash(document: dict[str, object]) -> bytes:
    core = dict(document)
    core.pop("core_sha256", None)
    document["core_sha256"] = hashlib.sha256(_canonical_bytes(core)).hexdigest()
    return _canonical_bytes(document)


def test_frozen_packet_loads_after_exact_evidence_replay() -> None:
    data = _packet_bytes()
    packet = load_spice_c1c4_source_review_packet(_evidence_bytes(), data)

    assert len(data) == SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_BYTE_COUNT == 8933
    assert (
        hashlib.sha256(data).hexdigest()
        == SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_SHA256
        == "cf1c5179809331e8effb2c22e8dcd746169779b16c71b8629eb16c487c1099ad"
    )
    assert (
        packet.core_sha256
        == SPICE_C1C4_SOURCE_REVIEW_PACKET_CORE_SHA256
        == "a88fa4ead67c5a04ac372715b60e68573981f49cdac95785389e175a2efdee84"
    )
    assert packet.schema_id == SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID
    assert packet.claim_scope == SPICE_C1C4_SOURCE_REVIEW_PACKET_CLAIM_SCOPE
    assert packet.source_evidence_artifact_sha256 == (
        "ffa884e94f624b89ac8602cda8ff01f363f60838e4efc1c2a3c0a057bf94c0a3"
    )


def test_zenodo_snapshot_is_exact_but_not_publisher_authentication() -> None:
    snapshot = _document()["doi_record_metadata_snapshot"]
    identity = _document()["identity_boundary"]
    assert isinstance(snapshot, dict)
    assert isinstance(identity, dict)

    assert snapshot["captured_at_utc"] == "2026-07-15T03:01:58Z"
    assert snapshot["record_id"] == 10975225
    assert snapshot["concept_doi"] == "10.5281/zenodo.7258939"
    assert snapshot["revision"] == 10
    assert snapshot["http_etag"] == '"10"'
    assert snapshot["created_at_utc"] == "2024-04-15T20:08:22.850341Z"
    assert snapshot["updated_at_utc"] == "2025-01-23T18:26:59.658548Z"
    assert snapshot["license_id"] == "cc-zero"
    assert snapshot["file_id"] == "0680b54c-17a3-4d17-bdd0-6385b2733181"
    assert snapshot["file_version_id"] == ("4792aaf4-e39a-4f1f-bc2b-b96c10f82f56")
    assert snapshot["file_byte_count"] == 37479271148
    assert snapshot["file_checksum_algorithm"] == "md5"
    assert snapshot["file_checksum_hex"] == "bfba2224b6540e1390a579569b475510"
    assert snapshot["normalized_projection_integrity_bound"] is True
    assert snapshot["publisher_signature_present"] is False
    assert snapshot["publisher_identity_authenticated"] is False
    assert identity["doi_record_metadata_snapshot_bound"] is True
    assert identity["doi_is_publisher_signature"] is False
    assert identity["https_snapshot_is_publisher_signature"] is False
    assert identity["cryptographic_publisher_identity_authenticated"] is False


def test_github_release_snapshot_keeps_dataset_and_software_license_contexts_apart() -> (
    None
):
    document = _document()
    repository = document["repository_release_snapshot"]
    license_review = document["license_review"]
    assert isinstance(repository, dict)
    assert isinstance(license_review, dict)

    assert repository["release_id"] == 151245684
    assert repository["tag_kind"] == "lightweight"
    assert repository["tag_name"] == "2.0.1"
    assert repository["tag_target_commit"] == (
        "b99b3f4d85585df6bdfeca5a56420c57ec6385f1"
    )
    assert repository["tag_signature_present"] is False
    assert repository["dataset_artifact_digest_published_in_repository_release"] is (
        False
    )
    assert repository["readme_git_blob_sha1"] == (
        "c73d94582a4f18cb479f8cae16ddfead07b63297"
    )
    assert repository["readme_byte_count"] == 5603
    assert repository["readme_sha256"] == (
        "27218a14f9d4990366a1475395111aa0f0ac815b2dafd2f881a6437dfd20d602"
    )
    assert repository["license_git_blob_sha1"] == (
        "50f1780a253f5500b62f3567c6a3c96d66090b88"
    )
    assert repository["license_byte_count"] == 1063
    assert repository["license_sha256"] == (
        "901d147cf9eebbd366dbf2246ed408f156ad4e7349d22992d65b6cc7bf4ee8c8"
    )
    assert repository["license_text_heading_observed"] == "MIT License"
    assert repository["license_context"] == (
        "repository_software_not_assumed_to_cover_dataset"
    )

    declarations = license_review["observed_declarations"]
    assert isinstance(declarations, list)
    assert [(row["source"], row["declared_identifier"]) for row in declarations] == [
        ("zenodo_record_metadata", "cc-zero"),
        ("github_readme", "CC0_public_domain_equivalent"),
        ("github_license_file", "MIT"),
    ]
    assert license_review["scope_interpretation_status"] == "pending_human_review"


def test_upstream_checksum_declaration_is_not_a_local_whole_file_match() -> None:
    document = _document()
    whole = document["whole_file_expected_identity"]
    identity = document["identity_boundary"]
    assert isinstance(whole, dict)
    assert isinstance(identity, dict)

    assert whole["artifact_name"] == "SPICE-2.0.1.hdf5"
    assert whole["expected_byte_count"] == 37479271148
    assert whole["upstream_checksum_algorithm"] == "md5"
    assert whole["upstream_checksum_hex"] == "bfba2224b6540e1390a579569b475510"
    assert whole["local_full_stream_receipt_sha256"] is None
    assert whole["local_observed_byte_count"] is None
    assert whole["local_observed_md5"] is None
    assert whole["local_observed_sha256"] is None
    assert whole["local_full_stream_completed"] is False
    assert whole["upstream_byte_count_matched"] is False
    assert whole["upstream_checksum_matched"] is False
    assert whole["whole_file_byte_identity_established"] is False
    assert whole["source_whole_file_authenticated"] is False
    assert identity["upstream_checksum_declaration_bound"] is True
    assert identity["md5_is_collision_resistant"] is False
    assert identity["checksum_match_is_publisher_identity_authentication"] is False


def test_subset_hash_expectations_are_not_an_extraction_receipt() -> None:
    extraction = _document()["subset_extraction_review"]
    assert isinstance(extraction, dict)

    assert extraction["expected_group_ids"] == ["c", "cc", "ccc", "cccc"]
    assert extraction["expected_record_count"] == 200
    assert extraction["expected_dataset_names"] == [
        "conformations",
        "dft_total_energy",
        "dft_total_gradient",
    ]
    rows = extraction["expected_source_array_sha256"]
    assert isinstance(rows, list)
    assert len(rows) == 4
    assert [row["group_id"] for row in rows] == ["c", "cc", "ccc", "cccc"]
    assert rows[0]["conformations"] == (
        "5e51aa7b5a92bc55c5ed748354e2bf276e62ed38ff6b53e2146ad285d3e90bb1"
    )
    assert rows[-1]["dft_total_gradient"] == (
        "768fd1a07a9067d9bfc4ead711c0aaf7f5fbb2111c872d2464ba9ce010d7704e"
    )
    assert extraction["future_receipt_required_fields"] == [
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
    for key in (
        "extraction_receipt_sha256",
        "observed_shapes_and_dtypes",
        "selection_order_receipt",
        "selection_protocol_id",
        "source_hdf5_dataset_paths",
        "source_hdf5_group_paths",
        "whole_file_stream_receipt_sha256",
    ):
        assert extraction[key] is None
    assert extraction["receipt_status"] == "missing"
    assert extraction["extraction_replayed"] is False
    assert extraction["extracted_arrays_match_evidence"] is False
    assert extraction["admitted_subset_bound_to_whole_file"] is False


def test_human_review_and_every_science_or_runtime_promotion_remain_false() -> None:
    document = _document()
    license_review = document["license_review"]
    nonpromotion = document["nonpromotion"]
    assert isinstance(license_review, dict)
    assert isinstance(nonpromotion, dict)

    assert license_review["human_review_status"] == "pending"
    for key in (
        "human_attestation_sha256",
        "human_decision",
        "human_reviewed_at_utc",
        "human_reviewer_id",
    ):
        assert license_review[key] is None
    for key in (
        "commercial_use_authorized",
        "legal_advice_provided",
        "license_human_reviewed",
        "redistribution_authorized",
    ):
        assert license_review[key] is False

    assert nonpromotion["review_packet_integrity"] is True
    assert nonpromotion["upstream_metadata_projection_bound"] is True
    assert nonpromotion["repository_release_projection_bound"] is True
    for key in (
        "cryptographic_publisher_identity_authenticated",
        "license_human_reviewed",
        "license_use_authorized",
        "source_whole_file_authenticated",
        "subset_extraction_authenticated",
        "candidate_fitting_performed",
        "candidate_parameter_set_available",
        "parameter_family_sufficiency_assessed",
        "reference_validation_performed",
        "production_parameters_available",
        "parameterability_assessed",
        "parameterizable",
        "physics_ready",
        "runtime_eligible",
        "execution_authorized",
        "claim_safe",
    ):
        assert nonpromotion[key] is False


def test_factory_only_report_and_serialization_preserve_nonpromotion() -> None:
    evidence = _evidence_bytes()
    packet_data = _packet_bytes()
    report = analyze_spice_c1c4_source_review_packet(evidence, packet_data)

    assert report.schema_id == SPICE_C1C4_SOURCE_REVIEW_PACKET_REPORT_SCHEMA_ID
    assert report.packet_schema_id == SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID
    assert report.claim_scope == SPICE_C1C4_SOURCE_REVIEW_PACKET_CLAIM_SCOPE
    assert report.zenodo_record_id == 10975225
    assert report.zenodo_record_revision == 10
    assert report.zenodo_snapshot_etag == '"10"'
    assert report.github_release_id == 151245684
    assert report.source_group_count == 4
    assert report.source_record_count == 200
    assert report.source_array_hash_row_count == 4
    assert report.future_extraction_required_field_count == 11
    assert report.observed_license_declaration_count == 3
    assert report.human_review_status == "pending"
    assert report.review_packet_integrity is True
    assert report.upstream_metadata_projection_bound is True
    assert report.repository_release_projection_bound is True
    assert report.upstream_checksum_declaration_bound is True

    false_fields = (
        "local_whole_file_stream_completed",
        "upstream_byte_count_matched",
        "upstream_checksum_matched",
        "whole_file_byte_identity_established",
        "subset_extraction_receipt_available",
        "subset_extraction_replayed",
        "admitted_subset_bound_to_whole_file",
        "source_whole_file_authenticated",
        "license_human_reviewed",
        "commercial_use_authorized",
        "redistribution_authorized",
        "legal_advice_provided",
        "cryptographic_publisher_signature_present",
        "cryptographic_publisher_identity_authenticated",
        "candidate_fitting_performed",
        "candidate_parameter_set_available",
        "parameter_family_sufficiency_assessed",
        "reference_validation_performed",
        "production_parameters_available",
        "parameterability_assessed",
        "parameterizable",
        "physics_ready",
        "runtime_eligible",
        "execution_authorized",
        "claim_safe",
    )
    assert all(getattr(report, name) is False for name in false_fields)

    kwargs = asdict(report)
    with pytest.raises(TypeError, match="factory-only"):
        SpiceC1C4SourceReviewPacketReport(_factory_token=object(), **kwargs)

    serialized = serialize_spice_c1c4_source_review_packet_report(evidence, packet_data)
    assert serialized == _canonical_bytes(kwargs)
    assert json.loads(serialized) == kwargs


def test_evidence_is_replayed_before_packet_parsing() -> None:
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="must not be empty"
    ):
        load_spice_c1c4_source_review_packet(b"", b"")


@pytest.mark.parametrize("value", [bytearray(b"{}"), memoryview(b"{}"), "{}"])
def test_packet_requires_exact_bytes(value: object) -> None:
    with pytest.raises(TypeError, match="exact bytes"):
        load_spice_c1c4_source_review_packet(
            _evidence_bytes(),
            value,  # type: ignore[arg-type]
        )


def test_packet_rejects_empty_oversized_and_non_ascii_payloads() -> None:
    evidence = _evidence_bytes()
    with pytest.raises(SpiceC1C4SourceReviewPacketContractError, match="empty"):
        load_spice_c1c4_source_review_packet(evidence, b"")
    with pytest.raises(
        SpiceC1C4SourceReviewPacketContractError, match="fixed byte limit"
    ):
        load_spice_c1c4_source_review_packet(evidence, b" " * (64 * 1024 + 1))
    with pytest.raises(SpiceC1C4SourceReviewPacketContractError, match="ASCII"):
        load_spice_c1c4_source_review_packet(evidence, _packet_bytes() + b"\xc3\xa9")


def test_packet_rejects_duplicate_nonstandard_and_noncanonical_json() -> None:
    evidence = _evidence_bytes()
    duplicate = _packet_bytes().replace(
        b'{"artifact_purpose":',
        b'{"schema_id":"duplicate","artifact_purpose":',
        1,
    )
    with pytest.raises(SpiceC1C4SourceReviewPacketContractError, match="duplicate"):
        load_spice_c1c4_source_review_packet(evidence, duplicate)

    nonstandard = _packet_bytes().replace(b"37479271148", b"NaN", 1)
    with pytest.raises(
        SpiceC1C4SourceReviewPacketContractError, match="non-standard JSON constant"
    ):
        load_spice_c1c4_source_review_packet(evidence, nonstandard)

    pretty = json.dumps(_document(), indent=2, ensure_ascii=True).encode("ascii")
    with pytest.raises(SpiceC1C4SourceReviewPacketContractError, match="canonical"):
        load_spice_c1c4_source_review_packet(evidence, pretty)


@pytest.mark.parametrize(
    ("section_name", "field_name", "value"),
    [
        ("doi_record_metadata_snapshot", "revision", 11),
        ("doi_record_metadata_snapshot", "publisher_identity_authenticated", True),
        ("repository_release_snapshot", "tag_signature_present", True),
        ("whole_file_expected_identity", "upstream_checksum_matched", True),
        ("whole_file_expected_identity", "local_observed_sha256", "0" * 64),
        ("subset_extraction_review", "extraction_replayed", True),
        ("license_review", "license_human_reviewed", True),
        ("license_review", "human_decision", "approved"),
        ("nonpromotion", "runtime_eligible", True),
    ],
)
def test_packet_rejects_metadata_receipt_review_and_promotion_tampering(
    section_name: str,
    field_name: str,
    value: object,
) -> None:
    document = _document()
    section = document[section_name]
    assert isinstance(section, dict)
    section[field_name] = value
    with pytest.raises(SpiceC1C4SourceReviewPacketContractError):
        load_spice_c1c4_source_review_packet(_evidence_bytes(), _rehash(document))


def test_packet_rejects_source_array_and_evidence_binding_tampering() -> None:
    document = _document()
    extraction = document["subset_extraction_review"]
    assert isinstance(extraction, dict)
    rows = extraction["expected_source_array_sha256"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    rows[0]["conformations"] = "0" * 64
    with pytest.raises(
        SpiceC1C4SourceReviewPacketContractError, match="source_array_sha256"
    ):
        load_spice_c1c4_source_review_packet(_evidence_bytes(), _rehash(document))

    document = _document()
    binding = document["source_evidence_binding"]
    assert isinstance(binding, dict)
    binding["evidence_artifact_sha256"] = "0" * 64
    with pytest.raises(
        SpiceC1C4SourceReviewPacketContractError,
        match="source_evidence_binding",
    ):
        load_spice_c1c4_source_review_packet(_evidence_bytes(), _rehash(document))


def test_public_digest_alias_mutation_cannot_redefine_frozen_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "SPICE_C1C4_SOURCE_REVIEW_PACKET_CORE_SHA256", "0" * 64)
    monkeypatch.setattr(
        module, "SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_SHA256", "1" * 64
    )
    monkeypatch.setattr(
        module, "SPICE_C1C4_SOURCE_REVIEW_PACKET_ARTIFACT_BYTE_COUNT", 1
    )
    monkeypatch.setattr(
        module,
        "SPICE_C1C4_SOURCE_REVIEW_PACKET_REPORT_SCHEMA_ID",
        "mutated.public.report.schema",
    )
    packet = load_spice_c1c4_source_review_packet(_evidence_bytes(), _packet_bytes())
    report = analyze_spice_c1c4_source_review_packet(_evidence_bytes(), _packet_bytes())
    assert packet.artifact_sha256 == (
        "cf1c5179809331e8effb2c22e8dcd746169779b16c71b8629eb16c487c1099ad"
    )
    assert report.schema_id == (
        "betelgeuze.spice_c1_c4_source_review_packet_report/1.0.0"
    )


def test_module_has_no_network_hdf5_qcarchive_or_array_dependency() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint(
        {"fsspec", "h5py", "numpy", "qcportal", "requests", "urllib"}
    )


def test_source_review_api_is_forcefield_only() -> None:
    exported_names = (
        "SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID",
        "SpiceC1C4SourceReviewPacketReport",
        "analyze_spice_c1c4_source_review_packet",
        "load_spice_c1c4_source_review_packet",
        "serialize_spice_c1c4_source_review_packet_report",
    )
    for name in exported_names:
        assert name in forcefield_api.__all__
        assert hasattr(forcefield_api, name)
        assert name not in package_root.__all__
        assert not hasattr(package_root, name)
