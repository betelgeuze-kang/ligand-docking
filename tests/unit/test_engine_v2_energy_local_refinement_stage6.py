from __future__ import annotations

from dataclasses import replace
import math

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    ChemistryPoseScorerV1,
    DockingBudget,
    DockingScope,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    generate_pocket_centered_docking_proposals,
    run_authenticated_pocket_placement_search,
)
from betelgeuze_engine_v2.docking.energy_refinement import (  # noqa: E402
    EnergyBasedLocalRefiner,
    EnergyLocalRefinementConfig,
    EnergyRefinedGuidedSearchResult,
    EnergyRefinementError,
    run_authenticated_energy_refined_scorer_v1_guided_search,
)
from betelgeuze_engine_v2.molecular import canonical_topology_sha256  # noqa: E402
from betelgeuze_engine_v2.physics.reference_minimization import (  # noqa: E402
    ReferenceMinimizationConfig,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    PeriodicTorsionParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="energy-refinement-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "H", "O", "H")
    charges = (0.0, -0.2, 0.2, -0.4, 0.4)
    coordinates = (
        [-2.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
        [-2.0, 0.0, 0.0],
        [-3.0, 0.0, 0.0],
    )
    return AllAtomSystem(
        system_id="energy-refinement-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1),
            Bond(index=1, atom_i=1, atom_j=2),
            Bond(index=2, atom_i=0, atom_j=3),
            Bond(index=3, atom_i=3, atom_j=4),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("energy-refinement-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    elements = ("O", "N", "H", "C", "H")
    charges = (-0.4, -0.2, 0.2, 0.0, 0.4)
    coordinates = (
        [2.0, 0.0, 0.0],
        [3.0, 3.0, 0.0],
        [2.5, 2.5, 0.0],
        [-2.0, 3.0, 0.0],
        [6.0, 6.0, 0.0],
    )
    return AllAtomSystem(
        system_id="energy-refinement-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(Bond(index=0, atom_i=1, atom_j=2),),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("energy-refinement-receptor-source", "b" * 64),
    )


def _authority():
    receptor = _receptor()
    ligand = _ligand()
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="energy-refinement-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=4.0,
    )
    return authority, receptor, ligand


def _parameters(ligand: AllAtomSystem) -> ReferenceForceFieldParameters:
    coordinates = ligand.coordinates[0]

    def angle(first: int, center: int, third: int) -> float:
        left = coordinates[first] - coordinates[center]
        right = coordinates[third] - coordinates[center]
        cosine = torch.dot(left, right) / (
            torch.linalg.vector_norm(left) * torch.linalg.vector_norm(right)
        )
        return float(torch.acos(cosine.clamp(-1.0, 1.0)).item())

    bonds = tuple(
        HarmonicBondParameter(
            bond.atom_i,
            bond.atom_j,
            float(
                torch.linalg.vector_norm(
                    coordinates[bond.atom_i] - coordinates[bond.atom_j]
                ).item()
            ),
            50.0,
        )
        for bond in ligand.bonds
    )
    angles = tuple(
        HarmonicAngleParameter(first, center, third, angle(first, center, third), 20.0)
        for first, center, third in (
            (1, 0, 3),
            (0, 1, 2),
            (0, 3, 4),
        )
    )
    torsions = tuple(
        PeriodicTorsionParameter(*atoms, 3, 0.0, 0.0)
        for atoms in (
            (2, 1, 0, 3),
            (1, 0, 3, 4),
        )
    )
    return ReferenceForceFieldParameters(
        parameter_set_id="energy-refinement-test-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(ligand),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 1.0, 0.0, 0.0)
            for index in range(ligand.atom_count)
        ),
        bonds=bonds,
        angles=angles,
        torsions=torsions,
        excluded_pairs=tuple(
            sorted(
                tuple(sorted((int(bond.atom_i), int(bond.atom_j))))
                for bond in ligand.bonds
            )
        ),
        cutoff_angstrom=6.0,
        switch_start_angstrom=5.0,
        applicability_domain=ReferenceApplicabilityDomain(
            max_atoms=16,
            max_bonds=16,
            max_angles=16,
            max_torsions=16,
            max_nonbonded_pairs=64,
        ),
    )


def _config() -> EnergyLocalRefinementConfig:
    return EnergyLocalRefinementConfig(
        minimization=ReferenceMinimizationConfig(
            max_iterations=20,
            max_backtracks=8,
            initial_step_size_angstrom2_mol_per_kcal=1.0e-3,
            maximum_atom_displacement_angstrom=0.05,
            force_tolerance_kcal_per_mol_angstrom=1.0e-5,
            max_neighbors=16,
            max_atoms_per_cell=16,
        ),
        max_attempts=8,
    )


def _proposal(authority):
    budget = DockingBudget(
        candidate_count=2,
        top_k=1,
        max_torsions=1,
        max_refinement_steps=0,
        translation_radius_angstrom=1.0,
        seed=1301,
    )
    return generate_pocket_centered_docking_proposals(authority, budget)[0][0]


def _refiner(authority, ligand, *, parameters=None):
    return EnergyBasedLocalRefiner(
        authority,
        ligand,
        _parameters(ligand) if parameters is None else parameters,
        implementation_source_sha256="e" * 64,
        config=_config(),
    )


def test_ligand_internal_reference_energy_refinement_is_bounded_and_auditable():
    authority, _, ligand = _authority()
    proposal = _proposal(authority)
    distorted_coordinates = proposal.coordinates.clone()
    distorted_coordinates[4] += torch.tensor(
        [-0.5, 0.25, 0.0],
        dtype=torch.float64,
    )
    distorted = proposal.with_refined_coordinates(
        distorted_coordinates,
        refiner_id="energy-refinement-distortion-fixture",
        refiner_version="1.0.0",
    )
    refiner = _refiner(authority, ligand)

    refined = refiner.refine(distorted, max_steps=12)
    attempt = refiner.attempt_for(distorted.fingerprint_sha256)

    assert refined.refinement_receipt_sha256 == attempt.receipt_sha256
    assert refined.parent_proposal_fingerprint_sha256 == distorted.fingerprint_sha256
    assert attempt.status == "success"
    assert attempt.final_energy_kcal_per_mol <= attempt.initial_energy_kcal_per_mol
    assert attempt.energy_delta_kcal_per_mol <= 0.0
    assert attempt.maximum_displacement_angstrom <= 0.6 + 1.0e-12
    assert attempt.accepted_iterations <= 12
    assert attempt.evaluation_count >= 1
    assert len(attempt.pre_coordinates_binary64_hex) == ligand.atom_count
    assert len(attempt.post_coordinates_binary64_hex) == ligand.atom_count
    assert attempt.to_dict()["receptor_ligand_interaction_energy_included"] is False
    assert attempt.to_dict()["scientifically_validated"] is False


def test_refinement_is_deterministic_and_binds_effective_step_budget():
    authority, _, ligand = _authority()
    proposal = _proposal(authority)
    coordinates = proposal.coordinates.clone()
    coordinates[4, 0] -= 0.4
    source = proposal.with_refined_coordinates(
        coordinates,
        refiner_id="energy-refinement-determinism-fixture",
        refiner_version="1.0.0",
    )
    first = _refiner(authority, ligand)
    second = _refiner(authority, ligand)

    first_result = first.refine(source, max_steps=7)
    second_result = second.refine(source, max_steps=7)
    first_attempt = first.attempt_for(source.fingerprint_sha256)
    second_attempt = second.attempt_for(source.fingerprint_sha256)

    assert torch.equal(first_result.coordinates, second_result.coordinates)
    assert first_attempt.receipt_sha256 == second_attempt.receipt_sha256
    assert first_attempt.max_steps == 7
    assert first_attempt.effective_minimization_config_fingerprint_sha256 != (
        first.config.minimization.fingerprint_sha256
    )


def test_parameter_topology_and_step_budget_fail_closed():
    authority, _, ligand = _authority()
    parameters = _parameters(ligand)
    with pytest.raises(EnergyRefinementError, match="topology is cross-wired"):
        _refiner(
            authority,
            ligand,
            parameters=replace(parameters, topology_sha256="0" * 64),
        )

    refiner = _refiner(authority, ligand)
    proposal = _proposal(authority)
    with pytest.raises(EnergyRefinementError, match="max_steps"):
        refiner.refine(proposal, max_steps=21)


def test_runtime_failure_is_retained_without_fabricated_post_state():
    authority, _, ligand = _authority()
    proposal = _proposal(authority)
    invalid_coordinates = proposal.coordinates.clone()
    invalid_coordinates[4] = invalid_coordinates[2]
    invalid = proposal.with_refined_coordinates(
        invalid_coordinates,
        refiner_id="energy-refinement-failure-fixture",
        refiner_version="1.0.0",
    )
    refiner = _refiner(authority, ligand)

    with pytest.raises(EnergyRefinementError, match="failed"):
        refiner.refine(invalid, max_steps=4)
    attempt = refiner.attempt_for(invalid.fingerprint_sha256)
    assert attempt.status == "failure"
    assert attempt.public_error_code
    assert len(attempt.private_error_sha256) == 64
    assert attempt.post_coordinates_sha256 == ""
    assert attempt.initial_energy_kcal_per_mol is None
    assert attempt.final_energy_kcal_per_mol is None
    assert attempt.maximum_displacement_angstrom is None
    assert not attempt.converged


def test_attempt_receipt_detects_mutation_and_duplicate_execution():
    authority, _, ligand = _authority()
    proposal = _proposal(authority)
    refiner = _refiner(authority, ligand)
    refiner.refine(proposal, max_steps=2)
    attempt = refiner.attempt_for(proposal.fingerprint_sha256)
    object.__setattr__(
        attempt,
        "maximum_displacement_angstrom",
        float(attempt.maximum_displacement_angstrom) + math.ulp(1.0),
    )
    with pytest.raises(EnergyRefinementError, match="attempt changed"):
        _ = attempt.receipt_sha256
    with pytest.raises(EnergyRefinementError, match="already attempted"):
        refiner.refine(proposal, max_steps=2)


def test_attempt_constructor_rejects_coordinate_and_counter_forgery():
    authority, _, ligand = _authority()
    proposal = _proposal(authority)
    refiner = _refiner(authority, ligand)
    refiner.refine(proposal, max_steps=2)
    attempt = refiner.attempt_for(proposal.fingerprint_sha256)

    forged_pre = list(attempt.pre_coordinates_binary64_hex)
    forged_pre[0] = (
        (float.fromhex(forged_pre[0][0]) + 0.25).hex(),
        forged_pre[0][1],
        forged_pre[0][2],
    )
    with pytest.raises(EnergyRefinementError, match="coordinate hash"):
        replace(attempt, pre_coordinates_binary64_hex=tuple(forged_pre))
    with pytest.raises(EnergyRefinementError, match="displacement is inconsistent"):
        replace(
            attempt,
            maximum_displacement_angstrom=(
                float(attempt.maximum_displacement_angstrom) + 0.25
            ),
        )
    with pytest.raises(EnergyRefinementError, match="step bound"):
        replace(attempt, accepted_iterations=attempt.max_steps + 1)
    with pytest.raises(EnergyRefinementError, match="must be an integer"):
        replace(attempt, evaluation_count=0.0)


def test_source_mutation_and_attempt_capacity_fail_closed():
    authority, _, ligand = _authority()
    refiner = EnergyBasedLocalRefiner(
        authority,
        ligand,
        _parameters(ligand),
        implementation_source_sha256="e" * 64,
        config=replace(_config(), max_attempts=1),
    )
    proposals = generate_pocket_centered_docking_proposals(
        authority,
        DockingBudget(candidate_count=2, top_k=1, max_torsions=1, seed=1307),
    )[0]
    refiner.refine(proposals[0], max_steps=1)
    with pytest.raises(EnergyRefinementError, match="capacity exceeded"):
        refiner.refine(proposals[1], max_steps=1)
    with pytest.raises(AttributeError):
        refiner.problem_fingerprint_sha256 = "0" * 64

    mutated = _refiner(authority, ligand)
    object.__setattr__(
        ligand,
        "coordinates",
        ligand.coordinates + torch.tensor([[[0.1, 0.0, 0.0]]]),
    )
    with pytest.raises(EnergyRefinementError, match="source state changed"):
        mutated.refine(_proposal(authority), max_steps=1)


def test_refiner_integrates_with_failure_complete_docking_search():
    authority, receptor, ligand = _authority()
    refiner = _refiner(authority, ligand)
    scorer = ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="f" * 64,
    )
    budget = DockingBudget(
        candidate_count=3,
        top_k=2,
        max_torsions=1,
        max_refinement_steps=2,
        translation_radius_angstrom=1.0,
        seed=1319,
    )
    result = run_authenticated_pocket_placement_search(
        authority,
        budget,
        scorer,
        refiner=refiner,
        diversity_rmsd_angstrom=0.0,
    )
    rows = result.authenticated_search_result.search_result.rows
    assert len(rows) == budget.candidate_count
    assert len(refiner.attempts) == budget.candidate_count
    assert all(row.status in {"success", "failure"} for row in rows)
    for row in rows:
        attempt = refiner.attempt_for(row.proposal_fingerprint_sha256)
        if row.succeeded:
            assert row.proposal is not None
            assert row.proposal.refinement_receipt_sha256 == attempt.receipt_sha256
        else:
            assert attempt.status == "failure"


def _guided_budget(*, seed: int) -> DockingBudget:
    return DockingBudget(
        candidate_count=4,
        top_k=2,
        max_torsions=1,
        max_refinement_steps=4,
        translation_radius_angstrom=1.0,
        seed=seed,
    )


def test_guided_search_binds_every_row_to_exact_refinement_evidence():
    authority, receptor, ligand = _authority()
    refiner = _refiner(authority, ligand)
    budget = _guided_budget(seed=1321)
    result = run_authenticated_energy_refined_scorer_v1_guided_search(
        authority,
        budget,
        ChemistryPoseScorerV1(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="f" * 64,
        ),
        build_guided_placement_context(authority, receptor, ligand),
        refiner,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )

    assert len(result.rows) == budget.candidate_count
    assert result.refinement_success_count == len(result.rows)
    assert result.refinement_failure_count == 0
    assert result.success_count + result.failure_count == len(result.rows)
    assert result.to_dict()["pre_post_coordinates_retained"] is True
    assert result.to_dict()["exact_parameter_identity_retained"] is True
    for row in result.rows:
        assert row.attempt.status == "success"
        assert row.attempt.receipt_sha256 == (
            refiner.attempt_for(row.source_proposal_fingerprint_sha256).receipt_sha256
        )
        assert row.result_proposal_fingerprint_sha256


def test_guided_search_retains_refinement_failures_without_post_state():
    authority, receptor, ligand = _authority()
    incomplete = replace(_parameters(ligand), angles=(), torsions=())
    refiner = _refiner(authority, ligand, parameters=incomplete)
    budget = _guided_budget(seed=1327)
    result = run_authenticated_energy_refined_scorer_v1_guided_search(
        authority,
        budget,
        ChemistryPoseScorerV1(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="f" * 64,
        ),
        build_guided_placement_context(authority, receptor, ligand),
        refiner,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )

    assert result.failure_count == len(result.rows)
    assert result.refinement_failure_count == len(result.rows)
    for row in result.rows:
        assert row.search_status == "failure"
        assert row.result_proposal_fingerprint_sha256 == ""
        assert row.attempt.status == "failure"
        assert row.attempt.post_coordinates_sha256 == ""
        assert row.attempt.final_energy_kcal_per_mol is None


def test_energy_refined_result_rejects_cross_wired_attempt_row():
    authority, receptor, ligand = _authority()
    refiner = _refiner(authority, ligand)
    result = run_authenticated_energy_refined_scorer_v1_guided_search(
        authority,
        _guided_budget(seed=1329),
        ChemistryPoseScorerV1(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="f" * 64,
        ),
        build_guided_placement_context(authority, receptor, ligand),
        refiner,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )
    rows = list(result.rows)
    with pytest.raises(EnergyRefinementError, match="cross-wired"):
        rows[0] = replace(rows[0], attempt=rows[1].attempt)

    assert isinstance(result, EnergyRefinedGuidedSearchResult)


def test_energy_refined_search_preflights_attempt_state_and_capacity():
    authority, receptor, ligand = _authority()
    scorer = ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="f" * 64,
    )
    context = build_guided_placement_context(authority, receptor, ligand)
    used = _refiner(authority, ligand)
    used.refine(_proposal(authority), max_steps=1)
    with pytest.raises(EnergyRefinementError, match="fresh refiner"):
        run_authenticated_energy_refined_scorer_v1_guided_search(
            authority,
            _guided_budget(seed=1331),
            scorer,
            context,
            used,
            receptor_system=receptor,
            ligand_system=ligand,
        )

    bounded = EnergyBasedLocalRefiner(
        authority,
        ligand,
        _parameters(ligand),
        implementation_source_sha256="e" * 64,
        config=replace(_config(), max_attempts=2),
    )
    with pytest.raises(EnergyRefinementError, match="attempt capacity"):
        run_authenticated_energy_refined_scorer_v1_guided_search(
            authority,
            _guided_budget(seed=1333),
            scorer,
            context,
            bounded,
            receptor_system=receptor,
            ligand_system=ligand,
        )
