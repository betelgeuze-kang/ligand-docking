from __future__ import annotations

import importlib.util
from typing import Any, Mapping, cast

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    InterpretablePoseScorerV0,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)
from betelgeuze_engine_v2.docking.chemistry_validity_v2 import (  # noqa: E402
    CHEMISTRY_AWARE_POSE_VALIDITY_V2_BLOCKERS,
    CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID,
    ChemistryAwarePoseValidityV2Context,
    ChemistryAwarePoseValidityV2Error,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Chain,
    OpenFFAdmission,
    Residue,
    StructureProvenance,
    canonical_system_sha256,
    prepare_ligand_with_rdkit_openff,
)


RDKIT_AVAILABLE = importlib.util.find_spec("rdkit") is not None
pytestmark = pytest.mark.skipif(
    not RDKIT_AVAILABLE,
    reason="RDKit is an optional chemistry capability",
)


class _UnavailableOpenFF:
    def admit(
        self,
        molecule: object,
        *,
        allow_undefined_stereo: bool,
        rdkit_modules: Mapping[str, Any],
    ) -> OpenFFAdmission:
        del molecule, allow_undefined_stereo, rdkit_modules
        return OpenFFAdmission(
            status="unavailable",
            adapter_id="validity_v2_test_unavailable/1.0.0",
            error_code="openff_toolkit_unavailable",
        )


def _receptor() -> AllAtomSystem:
    coordinates = ((10.0, 0.0, 0.0), (0.0, 10.0, 0.0))
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id="validity-v2-receptor",
        atoms=atoms,
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="polymer",
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _proposal(
    ligand: AllAtomSystem,
    problem: DockingProblemIdentity,
):
    coordinates = ligand.coordinates[0]
    atom_count = ligand.atom_count
    space = TorsionSearchSpace(
        local_offsets=torch.zeros_like(coordinates),
        parent=torch.full((atom_count,), -1, dtype=torch.long),
        local_axes=torch.tensor(
            [[0.0, 0.0, 1.0]] * atom_count,
            dtype=torch.float64,
        ),
        rotatable_mask=torch.zeros(atom_count, dtype=torch.bool),
        root_positions=coordinates,
    )
    proposal = generate_bounded_docking_proposals(
        space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=0.0,
        ),
        problem=problem,
    )[0]
    return space, proposal


def _fixture(smiles: str):
    source = prepare_ligand_with_rdkit_openff(
        smiles,
        source_format="smiles",
        openff_adapter=_UnavailableOpenFF(),
    )
    ligand = source.with_coordinates(
        source.coordinates,
        operation="validity_v2_test_coordinate_frame",
        operation_evidence_sha256="a" * 64,
    )
    receptor = _receptor()
    problem = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(receptor),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="b" * 64,
        coordinate_frame_id="validity_v2_test_frame",
    )
    context = ChemistryAwarePoseValidityV2Context.from_prepared_systems(
        receptor,
        ligand,
        source,
        problem,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius_angstrom=12.0,
    )
    space, proposal = _proposal(ligand, problem)
    return receptor, source, ligand, problem, context, space, proposal


def _refined(proposal, coordinates, marker: str):
    return proposal.with_refined_coordinates(
        coordinates,
        refiner_id="validity-v2-test-refiner",
        refiner_version="1.0.0",
        refinement_receipt_sha256=marker * 64,
    )


def test_v2_context_binds_preparation_topology_and_complete_result() -> None:
    _receptor_system, _source, _ligand, problem, context, _space, proposal = _fixture(
        "F[C@](Cl)(Br)I"
    )

    result = context.evaluate(proposal)
    document = cast(dict[str, Any], result.to_dict())

    assert result.complete
    assert result.valid
    assert document["schema_id"] == (CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID)
    assert document["problem_fingerprint_sha256"] == problem.fingerprint_sha256
    assert document["validity_context_fingerprint_sha256"] == (
        context.fingerprint_sha256
    )
    assert document["claim_safe"] is False
    assert document["scientifically_validated"] is False
    assert set(CHEMISTRY_AWARE_POSE_VALIDITY_V2_BLOCKERS) <= set(document["blockers"])
    assert document["checks"]["verified_ligand_preparation_bound"] is True
    assert document["checks"]["declared_chirality_preserved"] is True
    assert document["measurements"]["declared_atom_stereo_count"] == 1
    assert len(document["ligand_preparation_receipt_sha256"]) == 64


def test_v2_detects_atom_stereo_inversion_and_element_penetration() -> None:
    receptor, _source, _ligand, _problem, context, _space, proposal = _fixture(
        "F[C@](Cl)(Br)I"
    )
    stereo_row = context.declared_atom_stereo_rows[0]
    first = stereo_row[1]
    second = stereo_row[2]
    inverted = proposal.coordinates.clone()
    first_coordinates = inverted[first].clone()
    inverted[first] = inverted[second]
    inverted[second] = first_coordinates

    inverted_result = context.evaluate(_refined(proposal, inverted, "c"))

    assert inverted_result.checks["declared_chirality_preserved"] is False
    assert "declared_atom_stereo_geometry_failed" in inverted_result.blockers

    penetrated = proposal.coordinates.clone()
    penetrated += receptor.coordinates[0, 0] - penetrated[0]
    penetration_result = context.evaluate(_refined(proposal, penetrated, "d"))

    assert (
        penetration_result.checks["receptor_ligand_element_scaled_penetration_free"]
        is False
    )
    assert (
        penetration_result.measurements[
            "receptor_ligand_element_scaled_penetration_count"
        ]
        >= 1
    )
    assert "receptor_ligand_element_scaled_penetration_detected" in (
        penetration_result.blockers
    )


def test_v2_detects_reference_relative_bond_and_double_bond_stereo_damage() -> None:
    _receptor_system, _source, _ligand, _problem, context, _space, proposal = _fixture(
        "F/C=C/F"
    )
    assert len(context.declared_bond_stereo_rows) == 1

    distorted = proposal.coordinates.clone()
    first_bond = context.ligand_bond_rows[0]
    distorted[first_bond[0]] += torch.tensor(
        [0.5, 0.0, 0.0],
        dtype=torch.float64,
    )
    distorted_result = context.evaluate(_refined(proposal, distorted, "e"))
    assert (
        distorted_result.checks["reference_relative_bond_geometry_within_limit"]
        is False
    )

    row = context.declared_bond_stereo_rows[0]
    substituent, center_i, center_j, _other_substituent, _label = row
    flipped = proposal.coordinates.clone()
    axis = flipped[center_j] - flipped[center_i]
    axis = axis / torch.linalg.vector_norm(axis)
    offset = flipped[substituent] - flipped[center_i]
    parallel = torch.dot(offset, axis) * axis
    perpendicular = offset - parallel
    flipped[substituent] = flipped[center_i] + parallel - perpendicular
    flipped_result = context.evaluate(_refined(proposal, flipped, "f"))

    assert flipped_result.checks["declared_double_bond_stereo_preserved"] is False
    assert "declared_double_bond_stereo_geometry_failed" in (flipped_result.blockers)


def test_v2_context_fails_closed_on_topology_or_problem_mismatch() -> None:
    receptor, source, ligand, problem, _context, _space, _proposal_row = _fixture("CC")
    wrong_source = prepare_ligand_with_rdkit_openff(
        "CCC",
        source_format="smiles",
        openff_adapter=_UnavailableOpenFF(),
    )
    with pytest.raises(ChemistryAwarePoseValidityV2Error, match="topology"):
        ChemistryAwarePoseValidityV2Context.from_prepared_systems(
            receptor,
            ligand,
            wrong_source,
            problem,
            pocket_center=(0.0, 0.0, 0.0),
            pocket_radius_angstrom=12.0,
        )

    other_problem = DockingProblemIdentity(
        receptor_system_sha256="1" * 64,
        ligand_system_sha256="2" * 64,
    )
    with pytest.raises(ChemistryAwarePoseValidityV2Error, match="do not match"):
        ChemistryAwarePoseValidityV2Context.from_prepared_systems(
            receptor,
            ligand,
            source,
            other_problem,
            pocket_center=(0.0, 0.0, 0.0),
            pocket_radius_angstrom=12.0,
        )


def test_v2_context_is_accepted_by_failure_inclusive_search() -> None:
    receptor, _source, ligand, problem, context, space, _proposal_row = _fixture("CC")
    scorer = InterpretablePoseScorerV0(
        receptor,
        ligand,
        problem,
    )

    search = run_bounded_docking_search(
        space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=0.0,
        ),
        scorer,
        validity_context=context,
        problem=problem,
        diversity_rmsd_angstrom=0.0,
    )

    assert search.failure_count == 0
    assert search.rows[0].pose_validity is not None
    assert search.rows[0].pose_validity.to_dict()["schema_id"] == (
        CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID
    )


def test_v2_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.chemistry_validity_v2 import (
        __all__ as validity_v2_exports,
    )

    assert set(validity_v2_exports) <= set(docking.__all__)
