from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics import (
    FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256,
    REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID,
    REFERENCE_PARAMETER_APPLICABILITY_SCHEMA_ID,
    ReferenceApplicabilityDomain,
    ReferenceParameterApplicabilityError,
    ReferencePhysicsSourceIdentity,
    frozen_reference_parameter_applicability_record,
    reference_parameter_applicability_document,
    reference_parameter_applicability_json_bytes,
    require_reference_parameter_applicability_document,
    verify_reference_parameter_applicability_sources,
    write_reference_parameter_applicability_json,
)
from betelgeuze_engine_v2.physics.reference_parameter_applicability import (
    FROZEN_LEGACY_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256_V1,
    FROZEN_LEGACY_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256_V1_1,
)


def test_frozen_h5_record_binds_parameter_origin_runtime_envelope_and_digest() -> None:
    record = frozen_reference_parameter_applicability_record()
    document = reference_parameter_applicability_document(record)

    assert document["schema_id"] == REFERENCE_PARAMETER_APPLICABILITY_SCHEMA_ID
    assert document["profile_id"] == REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID
    assert document["record_sha256"] == (
        FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256
    )
    assert FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256 == (
        "cfc9d2a5f9ff4ee2539c3e15a8c0519788e26c447a71de4e994c53d4f78760a6"
    )
    assert document["record_version"] == "1.2.0"
    assert (
        document["superseded_record_sha256"]
        == FROZEN_LEGACY_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256_V1_1
        == "0c41a2a2e4471f2d632eca92964bb8f8c5d09abd249dd3cc5f414525c4daebeb"
    )
    assert document["legacy_record_chain_sha256s"] == [
        FROZEN_LEGACY_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256_V1
    ]
    assert (
        FROZEN_LEGACY_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256_V1
        == "63c3ae48ed755a360afd4c9ed77a8553f75da4ab793e287d89a8a68b76ea7ac8"
    )
    assert record.record_sha256 == document["record_sha256"]

    origin = document["parameter_origin"]
    assert origin["runtime_values_origin"] == (
        "caller_supplied_explicit_ReferenceForceFieldParameters"
    )
    assert origin["packaged_production_parameter_set"] is False
    assert origin["packaged_reference_parameter_values"] is False
    assert origin["offxml_parser_implemented"] is False
    assert origin["source_values_extracted"] is False
    assert origin["reviewed_source_to_runtime_values_binding_established"] is False
    candidate = origin["reviewed_candidate_source"]
    assert candidate["source_version"] == "2.2.1"
    assert candidate["selection_role"] == (
        "preexisting_reviewed_candidate_identity_only"
    )
    assert candidate["latest_release_selection_claimed"] is False
    assert candidate["parameter_coverage_validated"] is False
    assert candidate["runtime_value_binding_established"] is False

    envelope = document["runtime_execution_envelope"]
    assert envelope["status"] == "code_enforced_admission_and_capacity_guard_only"
    assert envelope["scientific_applicability_domain"] is False
    assert envelope["default_values_are_caller_configurable"] is True
    assert (
        envelope["default_capacity_guard"] == ReferenceApplicabilityDomain().to_dict()
    )
    assert (
        "canonical_topology_sha256_matches_parameter_record"
        in (envelope["admission_requirements"])
    )
    assert (
        "coordinate_tensor_is_finite_via_neighbor_graph_construction"
        in (envelope["admission_requirements"])
    )
    assert (
        "parameter_values_are_correct" in (envelope["admission_success_does_not_mean"])
    )


def test_runtime_equations_and_missing_semantics_are_explicit() -> None:
    document = reference_parameter_applicability_document()
    semantics = document["implemented_runtime_semantics"]
    terms = {row["term"]: row for row in semantics["terms"]}

    assert set(terms) == {
        "harmonic_bond",
        "harmonic_angle",
        "periodic_torsion",
        "lennard_jones_12_6",
        "screened_coulomb",
    }
    assert terms["lennard_jones_12_6"]["sigma_combination_rule"] == ("arithmetic_mean")
    assert terms["lennard_jones_12_6"]["epsilon_combination_rule"] == ("geometric_mean")
    assert terms["periodic_torsion"]["improper_torsion_semantics_implemented"] is False
    assert semantics["pair_policy"]["automatic_one_four_inference"] is False
    assert semantics["calibrated"] is False
    assert semantics["validated_for_composition"] is False

    unsupported = set(document["unsupported_or_unimplemented"])
    assert "atom_typing_and_parameter_assignment" in unsupported
    assert "partial_charge_generation" in unsupported
    assert "improper_torsion_semantics" in unsupported
    assert "pme_ewald_or_other_long_range_electrostatics" in unsupported
    assert "implicit_or_explicit_solvation_model" in unsupported
    assert "parameter_fitting_or_calibration" in unsupported


def test_scientific_and_product_promotion_remain_fail_closed() -> None:
    document = reference_parameter_applicability_document()

    applicability = document["scientific_applicability"]
    assert applicability["status"] == "not_established"
    assert applicability["validated_molecule_classes"] == []
    assert applicability["validated_elements"] == []
    assert applicability["validated_energy_force_reference_sets"] == []
    assert applicability["parameter_fit_dataset"] is None
    assert applicability["independent_holdout_dataset"] is None

    claims = document["claim_policy"]
    for name in (
        "production_parameter_set_shipped",
        "reviewed_source_values_bound_to_runtime",
        "parameter_assignment_implemented",
        "partial_charge_generation_implemented",
        "parameter_values_calibrated",
        "runtime_envelope_is_scientific_applicability_domain",
        "molecule_or_element_coverage_validated",
        "force_or_energy_validated",
        "parameter_fitting_authorized",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert claims[name] is False
    assert (
        "runtime_capacity_envelope_is_not_scientific_applicability_evidence"
        in (document["blockers"])
    )
    assert "parameter_fitting_not_authorized" in document["blockers"]


def test_document_verifier_rejects_digest_and_policy_drift() -> None:
    document = reference_parameter_applicability_document()
    assert require_reference_parameter_applicability_document(document) == document

    tampered = deepcopy(document)
    tampered["runtime_execution_envelope"]["scientific_applicability_domain"] = True
    with pytest.raises(
        ReferenceParameterApplicabilityError,
        match="digest mismatch",
    ):
        require_reference_parameter_applicability_document(tampered)

    rehashed = deepcopy(tampered)
    projection = {
        key: value for key, value in rehashed.items() if key != "record_sha256"
    }
    rehashed["record_sha256"] = hashlib.sha256(
        json.dumps(
            projection,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    with pytest.raises(
        ReferenceParameterApplicabilityError,
        match="does not match the frozen record",
    ):
        require_reference_parameter_applicability_document(rehashed)


def test_bound_runtime_sources_match_current_repository_bytes(tmp_path: Path) -> None:
    root = Path.cwd()
    observed = verify_reference_parameter_applicability_sources(root)
    record = frozen_reference_parameter_applicability_record()

    assert observed == {row.role: row.sha256 for row in record.runtime_sources}
    assert len(observed) == 7

    for row in record.runtime_sources:
        destination = tmp_path / row.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / row.relative_path).read_bytes())
    verify_reference_parameter_applicability_sources(tmp_path)

    drifted = tmp_path / record.runtime_sources[0].relative_path
    drifted.write_bytes(drifted.read_bytes() + b"\n")
    with pytest.raises(ReferenceParameterApplicabilityError, match="SHA-256 mismatch"):
        verify_reference_parameter_applicability_sources(tmp_path)


def test_record_and_source_identity_validation_fail_closed() -> None:
    record = frozen_reference_parameter_applicability_record()
    with pytest.raises(ReferenceParameterApplicabilityError, match="superseded"):
        replace(record, superseded=True)
    with pytest.raises(ReferenceParameterApplicabilityError, match="repository"):
        ReferencePhysicsSourceIdentity(
            role="escape",
            relative_path="../outside.py",
            sha256="a" * 64,
        )


def test_private_atomic_json_writer_round_trips(tmp_path: Path) -> None:
    output = tmp_path / "records" / "h5-parameter-applicability.json"
    assert write_reference_parameter_applicability_json(output) == (
        FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256
    )
    assert output.read_bytes() == reference_parameter_applicability_json_bytes()
    assert (
        require_reference_parameter_applicability_document(
            json.loads(output.read_text(encoding="ascii"))
        )
        == reference_parameter_applicability_document()
    )
    assert os.stat(output).st_mode & 0o777 == 0o600

    symlink = tmp_path / "record-link.json"
    symlink.symlink_to(output)
    with pytest.raises(ReferenceParameterApplicabilityError, match="symlink"):
        write_reference_parameter_applicability_json(symlink)
