from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    ALL_ATOM_SCHEMA_ID,
    CHECKPOINT_SCHEMA_VERSION,
    DISTRIBUTION_VERSION,
    ENGINE_API_VERSION,
    ENGINE_RESULT_SCHEMA_VERSION,
    RUNTIME_INPUT_SCHEMA_VERSION,
    VERSION_TAXONOMY,
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    ClaimStage,
    Residue,
    StructureProvenance,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
    validate_all_atom_system,
)
from betelgeuze_engine_v2.molecular import CanonicalSerializationError  # noqa: E402


def _system(*, verified: bool = False, stereo: bool = False) -> AllAtomSystem:
    provenance = StructureProvenance(
        source_format="sdf",
        source_id="unit-fixture",
        source_sha256="a" * 64,
        parser_name="unit",
        parser_version="1.0",
        source_digest_verified=verified,
        transformation_chain_verified=verified,
        chemistry_validated=verified,
        scientifically_validated=verified,
        product_qualified=False,
        metadata={"z": 2, "a": 1},
    )
    return AllAtomSystem(
        system_id="ligand",
        atoms=(
            Atom(
                index=0,
                name="C1",
                element="C",
                atomic_number=6,
                residue_index=0,
                stereo="R" if stereo else "unspecified",
            ),
            Atom(
                index=1,
                name="O1",
                element="O",
                atomic_number=8,
                residue_index=0,
            ),
        ),
        bonds=(Bond(index=0, atom_i=0, atom_j=1, order=1.0),),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [1.25, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        provenance=provenance,
        metadata={"beta": {"y": 2, "x": 1}, "alpha": True},
    )


def test_version_taxonomy_keeps_independent_surfaces_explicit() -> None:
    assert ALL_ATOM_SCHEMA_ID == "betelgeuze.all_atom_system/2.0.0"
    assert VERSION_TAXONOMY.distribution_version == DISTRIBUTION_VERSION
    assert VERSION_TAXONOMY.engine_api_version == ENGINE_API_VERSION
    assert VERSION_TAXONOMY.result_schema_version == ENGINE_RESULT_SCHEMA_VERSION
    assert VERSION_TAXONOMY.checkpoint_schema_version == CHECKPOINT_SCHEMA_VERSION
    assert VERSION_TAXONOMY.runtime_input_schema_version == RUNTIME_INPUT_SCHEMA_VERSION
    assert set(VERSION_TAXONOMY.to_dict()) == {
        "distribution_name",
        "distribution_version",
        "engine_api_version",
        "molecular_schema_version",
        "result_schema_version",
        "checkpoint_schema_version",
        "runtime_input_schema_version",
    }


def test_canonical_hashes_are_order_stable_and_coordinate_sensitive() -> None:
    system = _system()
    reordered = replace(
        system,
        metadata={"alpha": True, "beta": {"x": 1, "y": 2}},
        provenance=replace(system.provenance, metadata={"a": 1, "z": 2}),
    )
    assert canonical_topology_sha256(system) == canonical_topology_sha256(reordered)
    assert canonical_coordinates_sha256(system) == canonical_coordinates_sha256(reordered)
    assert canonical_system_sha256(system) == canonical_system_sha256(reordered)

    moved = replace(system, coordinates=system.coordinates + 0.25)
    assert canonical_topology_sha256(system) == canonical_topology_sha256(moved)
    assert canonical_coordinates_sha256(system) != canonical_coordinates_sha256(moved)
    assert canonical_system_sha256(system) != canonical_system_sha256(moved)


def test_coordinate_change_requires_operation_and_invalidates_transformation_claims() -> None:
    system = _system(verified=True)
    original_hash = canonical_system_sha256(system)
    with pytest.raises(ValueError, match="declare an operation"):
        system.with_coordinates(system.coordinates + 1.0, operation="")

    moved = system.with_coordinates(
        system.coordinates + 1.0,
        operation="rigid_translation_test",
        operation_evidence_sha256="b" * 64,
    )
    assert moved.provenance.source_digest_verified is True
    assert moved.provenance.transformation_chain_verified is False
    assert moved.provenance.chemistry_validated is False
    assert moved.provenance.scientifically_validated is False
    assert moved.provenance.product_qualified is False
    assert moved.provenance.parent_sha256[-1] == original_hash
    assert moved.provenance.operations[-1] == "rigid_translation_test"
    assert moved.provenance.claim_stage is ClaimStage.CONTRACT_VALID
    assert moved.provenance.claim_safe is False


def test_validation_reports_contract_provenance_and_scientific_stages_separately() -> None:
    unverified = validate_all_atom_system(_system())
    assert unverified.valid
    assert unverified.claim_stage is ClaimStage.CONTRACT_VALID
    assert unverified.claim_safe is False
    assert unverified.provenance_digest_present is True
    assert unverified.provenance_verified is False

    verified = validate_all_atom_system(_system(verified=True))
    assert verified.valid
    assert verified.provenance_verified is True
    assert verified.chemistry_validated is True
    assert verified.scientific_claim_ready is True
    assert verified.claim_stage is ClaimStage.SCIENTIFICALLY_VALIDATED
    assert verified.claim_safe is True
    assert verified.system_sha256 == canonical_system_sha256(_system(verified=True))


def test_declared_stereo_without_geometry_evidence_blocks_scientific_claim() -> None:
    report = validate_all_atom_system(_system(verified=True, stereo=True))
    assert report.valid
    assert report.stereochemistry_declared is True
    assert report.stereochemistry_geometry_verified is False
    assert report.scientific_claim_ready is False
    assert report.claim_stage is ClaimStage.CHEMISTRY_VALIDATED
    assert "atom_stereo_geometry_unverified" in {issue.code for issue in report.warnings}


def test_invalid_topology_and_noncanonical_metadata_fail_closed() -> None:
    invalid = replace(
        _system(),
        atoms=(replace(_system().atoms[0], index=3), _system().atoms[1]),
    )
    report = validate_all_atom_system(invalid)
    assert not report.valid
    assert report.claim_stage is ClaimStage.INVALID
    assert "noncanonical_atom_indices" in {issue.code for issue in report.errors}

    bad_metadata = replace(_system(), metadata={"bad": float("nan")})
    bad_report = validate_all_atom_system(bad_metadata)
    assert not bad_report.valid
    assert "canonical_serialization_failed" in {issue.code for issue in bad_report.errors}

    from betelgeuze_engine_v2.molecular import canonical_system_sha256 as digest

    with pytest.raises(CanonicalSerializationError):
        digest(bad_metadata)
