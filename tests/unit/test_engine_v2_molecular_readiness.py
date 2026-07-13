from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2 import IndependentEngineV2
from betelgeuze_engine_v2.features import build_deterministic_atom_features
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Chain,
    MolecularPreparationError,
    Residue,
    StructureProvenance,
    molecular_preparation_blockers,
    parse_pdb,
    parse_sdf_v2000,
    validate_all_atom_system,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tier_beta"


def _single_atom_system(*, formal_charge_known: bool = True) -> AllAtomSystem:
    return AllAtomSystem(
        system_id="single",
        atoms=(
            Atom(
                index=0,
                name="He",
                element="He",
                atomic_number=2,
                residue_index=0,
                formal_charge_known=formal_charge_known,
            ),
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="ION",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0,),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.zeros((1, 1, 3), dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="unit",
            preparation_ready=True,
        ),
    )


def test_typed_unknown_formal_charge_blocks_feature_construction() -> None:
    system = _single_atom_system(formal_charge_known=False)
    assert molecular_preparation_blockers(system) == ("formal_charge_unknown_for_some_atoms",)
    with pytest.raises(MolecularPreparationError) as exc_info:
        build_deterministic_atom_features(system)
    assert "formal_charge_unknown_for_some_atoms" in exc_info.value.blockers


def test_preparation_attestation_defaults_fail_closed() -> None:
    source = _single_atom_system()
    unattested = replace(
        source,
        provenance=StructureProvenance(source_format="unit"),
    )
    assert unattested.provenance.preparation_ready is False
    assert molecular_preparation_blockers(unattested) == (
        "preparation_not_complete",
    )
    with pytest.raises(MolecularPreparationError):
        build_deterministic_atom_features(unattested)


@pytest.mark.parametrize("fixture_name", ["mini_protein.pdb", "ethanol.sdf"])
def test_ingest_coverage_blockers_are_enforced_at_feature_and_engine_boundary(
    fixture_name: str,
) -> None:
    source = (FIXTURES / fixture_name).read_bytes()
    system = (
        parse_pdb(source).system
        if fixture_name.endswith(".pdb")
        else parse_sdf_v2000(source).system
    )
    blockers = molecular_preparation_blockers(system)
    assert blockers
    with pytest.raises(MolecularPreparationError):
        build_deterministic_atom_features(system)
    with pytest.raises(MolecularPreparationError):
        IndependentEngineV2().run(system)


def test_typed_preparation_attestation_cannot_fail_open_when_metadata_is_removed() -> None:
    system = parse_sdf_v2000((FIXTURES / "ethanol.sdf").read_bytes()).system
    with pytest.raises(AttributeError):
        system.provenance.metadata.clear()  # type: ignore[attr-defined]
    system = replace(
        system,
        provenance=replace(system.provenance, metadata={}),
    )

    assert system.provenance.preparation_ready is False
    assert molecular_preparation_blockers(system) == ("preparation_not_complete",)
    with pytest.raises(MolecularPreparationError) as exc_info:
        build_deterministic_atom_features(system)
    assert exc_info.value.blockers == ("preparation_not_complete",)


def test_explicitly_constructed_complete_contract_without_ingest_blockers_remains_usable() -> None:
    system = _single_atom_system()
    assert molecular_preparation_blockers(system) == ()
    features = build_deterministic_atom_features(system)
    assert features.values.shape == (1, 1, len(features.names))


def test_topology_only_contract_is_valid_but_coordinates_fail_closed_at_execution_boundaries() -> None:
    system = _single_atom_system().with_coordinates(
        torch.empty((0, 1, 3), dtype=torch.float64)
    )
    report = validate_all_atom_system(system)
    assert report.valid
    assert {issue.code for issue in report.warnings} == {"coordinates_missing"}
    assert system.has_coordinates is False
    assert molecular_preparation_blockers(system) == ("coordinates_missing",)

    with pytest.raises(MolecularPreparationError) as feature_error:
        build_deterministic_atom_features(system)
    assert feature_error.value.blockers == ("coordinates_missing",)

    with pytest.raises(MolecularPreparationError) as engine_error:
        IndependentEngineV2().run(system)
    assert engine_error.value.blockers == ("coordinates_missing",)
