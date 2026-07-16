from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2.parameter_source_provenance as module
from betelgeuze_engine_v2.parameter_source_provenance import (
    FROZEN_PARAMETER_SOURCE_PROVENANCE_SNAPSHOT_SHA256,
    PARAMETER_SOURCE_ARTIFACT_NAME,
    PARAMETER_SOURCE_ARTIFACT_SHA256,
    PARAMETER_SOURCE_ARTIFACT_URL,
    PARAMETER_SOURCE_COMMIT_SHA,
    PARAMETER_SOURCE_LICENSE_SHA256,
    PARAMETER_SOURCE_LICENSE_SPDX_ID,
    PARAMETER_SOURCE_LICENSE_URL,
    PARAMETER_SOURCE_PROVENANCE_PROFILE_ID,
    PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID,
    PARAMETER_SOURCE_RELEASE_URL,
    PARAMETER_SOURCE_REVIEW_STATUS,
    ParameterSourceProvenanceError,
    parameter_source_provenance_document,
    parameter_source_provenance_json_bytes,
    parameter_source_provenance_projection,
    require_parameter_source_provenance_document,
    reviewed_parameter_source_provenance,
    verify_parameter_source_review_files,
    write_parameter_source_provenance_json,
)


def test_reviewed_source_freezes_release_artifact_license_and_scope() -> None:
    snapshot = reviewed_parameter_source_provenance()
    projection = parameter_source_provenance_projection(snapshot)
    payload = snapshot.to_dict()

    assert snapshot.source_id == "openforcefield-sage-unconstrained"
    assert snapshot.source_version == "2.2.1"
    assert snapshot.release_tag == "2024.09.0"
    assert snapshot.source_commit_sha == PARAMETER_SOURCE_COMMIT_SHA
    assert snapshot.artifact_name == PARAMETER_SOURCE_ARTIFACT_NAME
    assert snapshot.artifact_sha256 == PARAMETER_SOURCE_ARTIFACT_SHA256
    assert snapshot.license_spdx_id == PARAMETER_SOURCE_LICENSE_SPDX_ID
    assert snapshot.license_sha256 == PARAMETER_SOURCE_LICENSE_SHA256
    assert snapshot.review_status == PARAMETER_SOURCE_REVIEW_STATUS
    assert snapshot.snapshot_sha256 == (
        FROZEN_PARAMETER_SOURCE_PROVENANCE_SNAPSHOT_SHA256
    )
    assert snapshot.candidate_elements == ("C", "H", "O")
    assert snapshot.candidate_bond_orders == ("single", "double")

    assert projection["schema_id"] == PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID
    assert projection["profile_id"] == PARAMETER_SOURCE_PROVENANCE_PROFILE_ID
    assert projection["source"]["release_url"] == PARAMETER_SOURCE_RELEASE_URL
    assert projection["artifact"]["immutable_url"] == PARAMETER_SOURCE_ARTIFACT_URL
    assert projection["artifact"]["bundled"] is False
    assert projection["license"]["immutable_url"] == PARAMETER_SOURCE_LICENSE_URL
    assert projection["license"]["legal_compliance_determination"] is False
    assert projection["candidate_applicability"]["formal_charge"] == "zero_only"
    assert (
        projection["candidate_applicability"]["parameter_coverage_validated"]
        is False
    )

    for flag in (
        "release_provenance_reviewed",
        "immutable_source_reference_bound",
        "artifact_identity_reviewed",
        "artifact_sha256_recorded",
        "license_identity_reviewed",
        "license_text_sha256_recorded",
        "bounded_candidate_scope_declared",
        "nonpromotion_boundary_reviewed",
        "parameter_source_provenance_reviewed",
    ):
        assert payload[flag] is True
    for flag in (
        "artifact_bundled",
        "runtime_network_fetch_enabled",
        "source_format_semantically_validated",
        "candidate_scope_parameter_coverage_validated",
        "parameter_assignment_implemented",
        "partial_charge_assigned",
        "parameter_values_calibrated",
        "force_or_energy_validated",
        "applicability_domain_validated",
        "legal_compliance_approved",
        "all_atom_system_created",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_document_is_canonical_and_rejects_review_or_claim_tampering() -> None:
    first = parameter_source_provenance_document()
    second = parameter_source_provenance_document()
    assert first == second
    assert json.loads(parameter_source_provenance_json_bytes()) == first
    assert require_parameter_source_provenance_document(first) is first

    changed = deepcopy(first)
    changed["provenance_projection"]["review"]["status"] = "scientifically_reviewed"
    with pytest.raises(ValueError, match="drifted from review"):
        require_parameter_source_provenance_document(changed)

    promoted = deepcopy(first)
    promoted["scientifically_validated"] = True
    with pytest.raises(ValueError, match="drifted from review"):
        require_parameter_source_provenance_document(promoted)


def test_offline_file_verifier_checks_size_and_sha_without_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "source.offxml"
    license_file = tmp_path / "LICENSE"
    artifact_bytes = b"bounded-offxml-fixture\n"
    license_bytes = b"bounded-license-fixture\n"
    artifact.write_bytes(artifact_bytes)
    license_file.write_bytes(license_bytes)

    monkeypatch.setattr(module, "PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES", len(artifact_bytes))
    monkeypatch.setattr(
        module,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        hashlib.sha256(artifact_bytes).hexdigest(),
    )
    monkeypatch.setattr(module, "PARAMETER_SOURCE_LICENSE_SIZE_BYTES", len(license_bytes))
    monkeypatch.setattr(
        module,
        "PARAMETER_SOURCE_LICENSE_SHA256",
        hashlib.sha256(license_bytes).hexdigest(),
    )

    verified = verify_parameter_source_review_files(artifact, license_file)
    assert verified["artifact_sha256"] == hashlib.sha256(artifact_bytes).hexdigest()
    assert verified["license_sha256"] == hashlib.sha256(license_bytes).hexdigest()
    assert verified["source_format_semantically_validated"] is False
    assert verified["parameter_assignment_implemented"] is False

    artifact.write_bytes(b"wrong-size")
    with pytest.raises(ParameterSourceProvenanceError) as caught:
        verify_parameter_source_review_files(artifact, license_file)
    assert caught.value.code == "artifact_size_mismatch"


def test_offline_file_verifier_fails_closed_on_same_size_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "source.offxml"
    license_file = tmp_path / "LICENSE"
    artifact.write_bytes(b"aaaa")
    license_file.write_bytes(b"bbbb")
    monkeypatch.setattr(module, "PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES", 4)
    monkeypatch.setattr(module, "PARAMETER_SOURCE_ARTIFACT_SHA256", "0" * 64)
    monkeypatch.setattr(module, "PARAMETER_SOURCE_LICENSE_SIZE_BYTES", 4)
    monkeypatch.setattr(
        module, "PARAMETER_SOURCE_LICENSE_SHA256", hashlib.sha256(b"bbbb").hexdigest()
    )

    with pytest.raises(ParameterSourceProvenanceError) as caught:
        verify_parameter_source_review_files(artifact, license_file)
    assert caught.value.code == "artifact_digest_mismatch"
    assert "aaaa" not in str(caught.value)


def test_atomic_writer_round_trips_and_module_has_no_network_client(tmp_path: Path) -> None:
    output = write_parameter_source_provenance_json(tmp_path / "nested" / "record.json")
    assert output.read_bytes() == parameter_source_provenance_json_bytes()
    assert require_parameter_source_provenance_document(
        json.loads(output.read_text(encoding="ascii"))
    )

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "urllib.request" not in source
    assert "urlopen(" not in source


def test_public_physics_namespace_exposes_provenance_contract() -> None:
    from betelgeuze_engine_v2.physics import (
        ParameterSourceProvenanceSnapshot,
        reviewed_parameter_source_provenance as public_factory,
    )

    assert isinstance(public_factory(), ParameterSourceProvenanceSnapshot)


def test_dedicated_workflow_is_sparse_offline_and_cross_version() -> None:
    path = Path(".github/workflows/ci-engine-v2-parameter-source-provenance.yml")
    source = path.read_text(encoding="utf-8")

    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "permissions:\n  contents: read" in source
    assert "persist-credentials: false" in source
    assert "betelgeuze_engine_v2/parameter_source_provenance.py" in source
    assert "test_engine_v2_parameter_source_provenance.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "curl " not in source
    assert "wget " not in source

    for workflow_name in (
        "ci-engine-v2-main.yml",
        "ci-engine-v2-mmcif-nonpoly-preparation.yml",
        "ci-engine-v2-mmcif-nonpoly-hydrogen-coordinates.yml",
        "ci-engine-v2-mmcif-nonpoly-preparation-corpus.yml",
    ):
        integration = Path(".github/workflows", workflow_name).read_text(
            encoding="utf-8"
        )
        assert "test_engine_v2_parameter_source_provenance.py" in integration
        assert "ci-engine-v2-parameter-source-provenance.yml" in integration
