from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_artifact_binding import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256,
    FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SOURCE_SHA256,
    FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256,
    FROZEN_INDEPENDENT_MINIMIZATION_ORACLE_SOURCE_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
    SUPERSEDED_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
    ReferenceMinimizationValidationArtifactBindingError,
    independent_analytic_oracle_source_sha256,
    independent_minimization_oracle_source_sha256,
    reference_minimization_validation_artifact_binding_document,
    reference_minimization_validation_artifact_binding_json_bytes,
    require_reference_minimization_validation_artifact_binding_document,
    write_reference_minimization_validation_artifact_binding_json,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    cpu_minimization_validation_materialization_manifest_document,
    cpu_minimization_validation_materializer_source_sha256,
)


def test_binding_freezes_exact_protocol_materializer_and_oracles() -> None:
    document = reference_minimization_validation_artifact_binding_document()
    dependencies = document["dependencies"]
    assert document["artifact_binding_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
    )
    assert document["superseded_artifact_binding_sha256"] == (
        SUPERSEDED_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
    )
    assert dependencies["materializer_source_sha256"] == (
        FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SOURCE_SHA256
    )
    assert dependencies["materializer_source_sha256"] == (
        cpu_minimization_validation_materializer_source_sha256()
    )
    assert dependencies["analytic_oracle_source_sha256"] == (
        FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256
    )
    assert dependencies["analytic_oracle_source_sha256"] == (
        independent_analytic_oracle_source_sha256()
    )
    assert dependencies["minimization_oracle_source_sha256"] == (
        FROZEN_INDEPENDENT_MINIMIZATION_ORACLE_SOURCE_SHA256
    )
    assert dependencies["minimization_oracle_source_sha256"] == (
        independent_minimization_oracle_source_sha256()
    )
    assert dependencies["materialization_manifest_sha256"] == (
        FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256
    )
    assert (
        dependencies["materialization_manifest_sha256"]
        == (
            cpu_minimization_validation_materialization_manifest_document()[
                "materialization_manifest_sha256"
            ]
        )
    )


def test_binding_import_audit_enforces_independence_boundary() -> None:
    audit = reference_minimization_validation_artifact_binding_document()[
        "import_audit"
    ]
    assert audit["audit_passed"] is True
    assert audit["analytic_oracle_is_only_relative_dependency"] is True
    assert audit["operational_evaluator_imported"] is False
    assert audit["operational_minimizer_imported"] is False
    assert audit["constraint_or_solvation_implementation_imported"] is False
    assert audit["protocol_or_materializer_imported"] is False
    assert audit["third_party_dependency_imported"] is False
    assert audit["dynamic_import_tokens_present"] is False


def test_binding_keeps_review_execution_result_and_claim_gates_closed() -> None:
    document = reference_minimization_validation_artifact_binding_document()
    policy = document["claim_policy"]
    assert policy["independent_minimization_reference_implemented"] is True
    assert policy["independent_minimization_reference_source_identity_bound"] is True
    assert policy["independent_minimization_reference_import_boundary_verified"] is True
    for key in (
        "independent_scientific_review_completed",
        "validation_execution_authorized",
        "validation_results_collected",
        "runtime_parameter_values_independently_reviewed",
        "scientific_applicability_established",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "minimization_validated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert policy[key] is False
    assert document["authorization_gate"]["decision"] == "closed"
    assert (
        "independent_minimization_reference_is_not_validation_result_evidence"
        in document["authorization_gate"]["current_blockers"]
    )


def test_binding_rejects_tampering_and_writes_canonical_json(
    tmp_path: Path,
) -> None:
    document = reference_minimization_validation_artifact_binding_document()
    assert (
        require_reference_minimization_validation_artifact_binding_document(document)
        == document
    )
    tampered = deepcopy(document)
    tampered["claim_policy"]["scientifically_validated"] = True
    with pytest.raises(
        ReferenceMinimizationValidationArtifactBindingError,
        match="does not match",
    ):
        require_reference_minimization_validation_artifact_binding_document(tampered)
    encoded = reference_minimization_validation_artifact_binding_json_bytes()
    assert encoded.endswith(b"\n")
    assert json.loads(encoded) == document
    destination = write_reference_minimization_validation_artifact_binding_json(
        tmp_path / "nested" / "binding.json"
    )
    assert destination.read_bytes() == encoded
    assert os.stat(destination).st_mode & 0o777 == 0o644
    symlink = tmp_path / "binding-link.json"
    symlink.symlink_to(destination)
    with pytest.raises(
        ReferenceMinimizationValidationArtifactBindingError,
        match="symlink",
    ):
        write_reference_minimization_validation_artifact_binding_json(symlink)
