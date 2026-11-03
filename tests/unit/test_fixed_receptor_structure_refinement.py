"""Actual own-engine CPU E/F on explicitly synthetic fixtures, not real chemistry."""
# ruff: noqa: E402
from dataclasses import replace
import pytest

torch = pytest.importorskip("torch")
from betelgeuze_engine_v2.docking import build_authenticated_known_pocket_docking_problem
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_engine_v2.physics.reference_parameters import (
    HarmonicBondParameter, HarmonicAngleParameter, PeriodicTorsionParameter,
)
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEvaluator, FixedReceptorEnvironment
from betelgeuze_product.fixed_receptor_structure_refinement import FixedReceptorEnergyForceProvider
from betelgeuze_product.structure_preserving_refinement import StructureRefinementError
from tests.unit.test_engine_v2_docking_authority_search import _system, _authority
from tests.unit.test_cpu_fixed_receptor import base_parameters, environment


def fixture(*, charged=False, **kwargs):
    ligand, receptor = (_system(receptor=False), _system(receptor=True))
    ligand = replace(ligand, atoms=tuple(replace(a, partial_charge_e=(.15 if a.index % 2 == 0 else -.1) if charged else 0.) for a in ligand.atoms))
    receptor = replace(receptor, atoms=tuple(replace(a, partial_charge_e=(.2 if a.index % 2 == 0 else -.25) if charged else 0.) for a in receptor.atoms))
    authority = build_authenticated_known_pocket_docking_problem(receptor, ligand, _authority().pocket)
    base = replace(base_parameters(ligand),
        bonds=tuple(HarmonicBondParameter(b.atom_i, b.atom_j,
            float(torch.linalg.vector_norm(ligand.coordinates[0, b.atom_i] - ligand.coordinates[0, b.atom_j])),
            10.) for b in ligand.bonds),
        angles=(HarmonicAngleParameter(0, 1, 2, 2.5, 1.),
                HarmonicAngleParameter(1, 2, 3, 2.5, 1.)),
        torsions=(PeriodicTorsionParameter(0, 1, 2, 3, 1, 0., .1),))
    parameters = ReferenceForceFieldV2Parameters(base)
    cross = replace(environment(receptor, ligand, base).cross,
                    coordinate_frame_id=authority.pocket.coordinate_frame_id)
    provider = FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters, cross,
                 implementation_source_sha256="e"*64, **kwargs)
    return authority, ligand, receptor, parameters, cross, provider


def points(ligand):
    return tuple(tuple(float(v) for v in row) for row in ligand.coordinates[0].tolist())


@pytest.mark.parametrize("charged", [False, True])
def test_provider_matches_actual_total_raw_force_and_rebuilds_neighbors(monkeypatch, charged):
    _, ligand, receptor, parameters, cross, provider = fixture(charged=charged)
    import betelgeuze_product.fixed_receptor_structure_refinement as module
    calls = []
    original = module.build_compact_radius_graph
    def build(xyz, config):
        calls.append(xyz.clone())
        return original(xyz, config)
    monkeypatch.setattr(module, "build_compact_radius_graph", build)
    evaluator = FixedReceptorEvaluator(ExtendedEvaluator(parameters), FixedReceptorEnvironment(receptor, cross))
    for shift in (0., .05, 0.):
        xyz = ligand.coordinates + torch.tensor([shift, 0., 0.], dtype=torch.float64)
        actual = provider.evaluate(points(ligand.with_coordinates(xyz, operation="synthetic-test")))
        expected = evaluator.evaluate(ligand.with_coordinates(xyz, operation="synthetic-reference"),
            build_compact_radius_graph(xyz, RadiusGraphConfig(parameters.base_parameters.cutoff_angstrom, 256, 256)))
        assert actual.energy == float(expected.term.energy[0])
        assert actual.forces == tuple(tuple(float(v) for v in r) for r in expected.term.forces[0].tolist())
    assert len(calls) == provider.evaluation_attempts == 3
    assert not torch.equal(calls[0], calls[1])


@pytest.mark.parametrize("charged", [False, True])
def test_actual_force_agrees_with_coordinate_finite_difference(charged):
    _, ligand, _, _, _, provider = fixture(charged=charged)
    xyz = points(ligand)
    force = provider.evaluate(xyz).forces
    if charged:
        assert abs(provider.observations[-1].components_document()["cross_screened_coulomb"]) > 1.e-5
    for h in (1.e-4, 1.e-5, 1.e-6):
        for i in range(len(xyz)):
            for k in range(3):
                plus, minus = [list(r) for r in xyz], [list(r) for r in xyz]
                plus[i][k] += h
                minus[i][k] -= h
                ep = provider.evaluate(tuple(tuple(r) for r in plus)).energy
                em = provider.evaluate(tuple(tuple(r) for r in minus)).energy
                assert force[i][k] == pytest.approx(-(ep-em)/(2*h), rel=2e-5, abs=1e-8)
    assert provider.evaluation_attempts == 73


def test_receptor_mutation_is_hard_and_preflight_charges_no_evaluation():
    _, ligand, receptor, _, _, provider = fixture()
    receptor.coordinates[0, 0, 0] += .01
    with pytest.raises(StructureRefinementError, match="construction-bound"):
        provider.evaluate(points(ligand))
    assert provider.evaluation_attempts == 0


def test_frame_cross_wiring_and_budget_are_rejected():
    authority, ligand, receptor, parameters, cross, provider = fixture(max_evaluations=1)
    with pytest.raises(StructureRefinementError, match="cross-wired"):
        FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters,
            replace(cross, coordinate_frame_id="wrong-frame"), implementation_source_sha256="e"*64)
    provider.evaluate(points(ligand))
    with pytest.raises(StructureRefinementError, match="capacity"):
        provider.evaluate(points(ligand))
    assert provider.evaluation_attempts == 1


def test_physical_observation_preserves_components_and_scientific_limits():
    _, ligand, _, _, cross, provider = fixture()
    result = provider.evaluate(points(ligand))
    obs = provider.observations[-1]
    components = obs.components_document()
    assert set(components) == {"ligand_internal", "cross_lennard_jones", "cross_screened_coulomb", "total"}
    assert components["total"] == result.energy
    assert sum(components[k] for k in components if k != "total") == pytest.approx(result.energy)
    assert obs.calibrated is False and obs.validated_for_composition is False
    assert "fixed_receptor_model_not_scientifically_validated" in obs.scientific_blockers
    assert provider.max_internal_increase_kcal_per_mol == cross.max_internal_increase_kcal_per_mol


def test_actual_coordinator_retains_endpoints_and_final_strain_policy():
    from betelgeuze_engine_v2.docking import DockingBudget
    from betelgeuze_engine_v2.docking.proposals import generate_bounded_docking_proposals
    from betelgeuze_product.fixed_receptor_structure_refinement import FixedReceptorStructureCoordinator
    from betelgeuze_product.structure_preserving import SearchConfig
    from betelgeuze_product.cpu_refinement_v1_2.selection import refinement_admissible
    authority, ligand, _, _, cross, provider = fixture()
    proposal = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)[0]
    coordinator = FixedReceptorStructureCoordinator(authority, ligand, provider,
        implementation_source_sha256="d"*64, config=SearchConfig(max_steps=3, max_evaluations=16))
    outcome = coordinator.run(proposal, max_steps=3)
    assert outcome.admissible
    assert outcome.evaluation_attempts == outcome.optimizer_attempt.result.evaluation_attempts
    assert outcome.final_observation.components_document()["total"] <= outcome.initial_observation.components_document()["total"]
    document = outcome.admission_document()
    assert document["max_internal_increase_kcal_per_mol"] == cross.max_internal_increase_kcal_per_mol
    assert document["converged"] is False
    row = {"succeeded": True, "selection_eligible": True}
    assert refinement_admissible(row, document, require_convergence=False)
    assert not refinement_admissible(row, document, require_convergence=True)


def test_unsatisfied_distance_constraint_is_observed_not_waived():
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import DistanceConstraintParameter
    authority, ligand, receptor, parameters, cross, _ = fixture()
    parameters = replace(parameters, constraints=(DistanceConstraintParameter(0, 3, 2.),))
    provider = FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters, cross,
        implementation_source_sha256="e"*64)
    provider.evaluate(points(ligand))
    obs = provider.observations[-1]
    assert len(obs.constraint_observations) == 1
    assert obs.constraints_satisfied is False
    assert obs.constraint_observations[0].residual_angstrom != 0.


def test_final_strain_boundary_is_independent_of_total_descent():
    from betelgeuze_product.fixed_receptor_structure_refinement import final_admission_reasons
    _, ligand, _, _, _, provider = fixture()
    provider.evaluate(points(ligand))
    initial = provider.observations[-1]
    a = initial.components_document()
    for increase, rejected in ((2., False), (2.00001, True)):
        b = dict(a)
        b["ligand_internal"] += increase
        b["cross_lennard_jones"] -= increase + 1.
        b["total"] = sum(b[k] for k in b if k != "total")
        final = replace(initial, components=tuple(sorted(b.items())))
        reasons = final_admission_reasons(initial, final, 2.)
        assert ("final_internal_strain_exceeded" in reasons) is rejected
        assert "total_energy_increased" not in reasons
    with pytest.raises(StructureRefinementError, match="strain limit"):
        final_admission_reasons(initial, initial, None)


def test_final_constraint_admission_rejects_observed_violation():
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import DistanceConstraintParameter
    from betelgeuze_product.fixed_receptor_structure_refinement import final_admission_reasons
    authority, ligand, receptor, parameters, cross, _ = fixture()
    parameters = replace(parameters, constraints=(DistanceConstraintParameter(0, 3, 2.),))
    provider = FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters, cross,
        implementation_source_sha256="e"*64)
    provider.evaluate(points(ligand))
    obs = provider.observations[-1]
    assert final_admission_reasons(obs, obs, 2.) == ("initial_constraints_unsatisfied", "final_constraints_unsatisfied")
    recovered = replace(obs, constraint_observations=())
    assert final_admission_reasons(obs, recovered, 2.) == ("initial_constraints_unsatisfied",)


def test_coordinator_rejects_invalid_initial_constraint_before_any_ef_call():
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import DistanceConstraintParameter
    from betelgeuze_engine_v2.docking import DockingBudget
    from betelgeuze_engine_v2.docking.proposals import generate_bounded_docking_proposals
    from betelgeuze_product.fixed_receptor_structure_refinement import FixedReceptorStructureCoordinator
    authority, ligand, receptor, parameters, cross, _ = fixture()
    parameters = replace(parameters, constraints=(DistanceConstraintParameter(0, 3, 2.),))
    provider = FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters, cross,
        implementation_source_sha256="e"*64)
    proposal = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)[0]
    coordinator = FixedReceptorStructureCoordinator(authority, ligand, provider,
        implementation_source_sha256="d"*64)
    with pytest.raises(StructureRefinementError):
        coordinator.run(proposal, max_steps=3)
    assert provider.evaluation_attempts == 0
    assert not coordinator.attempts
    assert not coordinator.initial_constraint_rejections[proposal.fingerprint_sha256][0].satisfied
    with pytest.raises(StructureRefinementError, match="duplicate"):
        coordinator.run(proposal, max_steps=3)
    assert provider.evaluation_attempts == 0
    assert len(coordinator.initial_constraint_rejections) == 1

    capped = FixedReceptorStructureCoordinator(authority, ligand, provider,
        implementation_source_sha256="d"*64, max_attempts=1)
    proposals = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=2, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)
    with pytest.raises(StructureRefinementError, match="max_steps"):
        capped.run(proposals[0], max_steps=0)
    assert not capped.initial_constraint_rejections
    with pytest.raises(StructureRefinementError, match="DockingProposal"):
        capped.run(object(), max_steps=3)
    with pytest.raises(StructureRefinementError, match="initial constraints"):
        capped.run(proposals[0], max_steps=3)
    with pytest.raises(StructureRefinementError, match="excessive"):
        capped.run(proposals[1], max_steps=3)
    assert len(capped.initial_constraint_rejections) == 1
    assert provider.evaluation_attempts == 0


def test_nonzero_receptor_model_authority_is_not_silently_model_zero():
    authority, ligand, receptor, parameters, cross, _ = fixture()
    with pytest.raises(StructureRefinementError, match="cross-wired"):
        FixedReceptorEnergyForceProvider(replace(authority, receptor_model_index=1),
            ligand, receptor, parameters, cross, implementation_source_sha256="e"*64)


@pytest.mark.parametrize("bad", ["model", "force_semantics", "energy_semantics", "force_shape",
                                "force_dtype", "nonfinite", "blocker", "force_unit"])
def test_bad_actual_evaluator_output_is_not_relabelled_or_recorded(monkeypatch, bad):
    _, ligand, _, _, _, provider = fixture(charged=True)
    original = FixedReceptorEvaluator.evaluate
    def malformed(self, state, neighbors):
        result = original(self, state, neighbors)
        if bad == "model":
            return replace(result, evaluator_fingerprint_sha256="f"*64)
        if bad == "blocker":
            return replace(result, scientific_blockers=())
        term = result.term
        if bad == "force_semantics":
            term = replace(term, force_descriptor=replace(term.force_descriptor, semantics="positive_gradient"))
        elif bad == "energy_semantics":
            term = replace(term, energy_descriptor=replace(term.energy_descriptor, semantics="different_model"))
        elif bad == "force_unit":
            term = replace(term, force_descriptor=replace(term.force_descriptor, unit="kJ/mol/nm"))
        elif bad == "force_shape":
            term = replace(term, forces=term.forces[:, :-1])
        elif bad == "force_dtype":
            term = replace(term, forces=term.forces.float(), energy=term.energy.float())
        elif bad == "nonfinite":
            term.forces[0, 0, 0] = float("nan")
        return replace(result, term=term)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", malformed)
    with pytest.raises(StructureRefinementError, match="output contract"):
        provider.evaluate(points(ligand))
    assert provider.evaluation_attempts == 1
    assert provider.observations == ()


def test_duplicate_endpoint_component_keys_are_not_silently_dropped():
    from betelgeuze_product.fixed_receptor_structure_refinement import final_admission_reasons
    _, ligand, _, _, _, provider = fixture()
    provider.evaluate(points(ligand))
    obs = provider.observations[-1]
    malformed = replace(obs, components=obs.components + (obs.components[0],))
    with pytest.raises(StructureRefinementError, match="duplicate component"):
        final_admission_reasons(obs, malformed, 2.)


def test_actual_lj_collision_backtracks_and_halved_trial_is_accepted():
    from tests.unit.test_cpu_fixed_receptor import system
    from betelgeuze_product.structure_preserving import Evaluation, SearchConfig, StructureTopology, refine_structure
    ligand, receptor = system([[1.8, 0., 0.]], name="synthetic-lj-ligand"), system([[0., 0., 0.]], name="synthetic-lj-receptor")
    authority = build_authenticated_known_pocket_docking_problem(receptor, ligand, _authority().pocket)
    base = base_parameters(ligand)
    cross = replace(environment(receptor, ligand, base).cross,
        coordinate_frame_id=authority.pocket.coordinate_frame_id, minimum_distance_angstrom=.9)
    provider = FixedReceptorEnergyForceProvider(authority, ligand, receptor,
        ReferenceForceFieldV2Parameters(base), cross, implementation_source_sha256="e"*64)
    def evaluate(xyz):
        result = provider.evaluate(xyz)
        return Evaluation(result.energy, result.forces)
    result = refine_structure(points(ligand), StructureTopology(1, (), ()), evaluate,
        SearchConfig(max_steps=1, max_evaluations=3, max_backtracks=2, translation_step_angstrom=1.))
    assert result.coordinates[0][0] == pytest.approx(1.3)
    assert result.energy < result.initial_energy
    assert result.accepted_steps == 1
    assert result.recoverable_rejections == provider.recoverable_rejections == 1
    assert result.evaluation_attempts == provider.evaluation_attempts == 3
    assert result.failed_evaluations == 1
    assert result.successful_evaluations == provider.physical_evaluation_attempts == 2
    assert provider.graph_build_attempts == 3
    assert len(provider.observations) == 2


def test_incomplete_parameters_plus_collision_is_hard_not_recoverable():
    from betelgeuze_engine_v2.molecular import canonical_system_sha256
    authority, ligand, receptor, parameters, cross, _ = fixture()
    # Missing an explicitly required bond term, with consistent declared hashes.
    base = replace(parameters.base_parameters, bonds=parameters.base_parameters.bonds[:-1])
    parameters = replace(parameters, base_parameters=base)
    cross = replace(cross, ligand_base_parameters_sha256=base.fingerprint_sha256,
                    receptor_system_sha256=canonical_system_sha256(receptor))
    provider = FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters, cross,
        implementation_source_sha256="e"*64)
    xyz = [list(r) for r in points(ligand)]
    xyz[0] = receptor.coordinates[0, 0].tolist()
    with pytest.raises(StructureRefinementError, match="model applicability"):
        provider.evaluate(tuple(tuple(float(v) for v in r) for r in xyz))
    assert provider.evaluation_attempts == provider.graph_build_attempts == 1
    assert provider.physical_evaluation_attempts == provider.recoverable_rejections == 0
    assert not provider.observations


def test_declared_constraint_observation_cannot_be_silently_dropped(monkeypatch):
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import DistanceConstraintParameter
    authority, ligand, receptor, parameters, cross, _ = fixture()
    parameters = replace(parameters, constraints=(DistanceConstraintParameter(0, 3, 2.),))
    provider = FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters, cross,
        implementation_source_sha256="e"*64)
    original = FixedReceptorEvaluator.evaluate
    def dropped(self, state, neighbors):
        return replace(original(self, state, neighbors), constraint_observations=())
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", dropped)
    with pytest.raises(StructureRefinementError, match="constraint observation coverage"):
        provider.evaluate(points(ligand))
    assert provider.evaluation_attempts == provider.physical_evaluation_attempts == 1
    assert provider.observations == ()


def test_coordinator_failed_callback_keeps_per_source_work(monkeypatch):
    from betelgeuze_engine_v2.docking import DockingBudget
    from betelgeuze_engine_v2.docking.proposals import generate_bounded_docking_proposals
    from betelgeuze_product.fixed_receptor_structure_refinement import FixedReceptorStructureCoordinator
    authority, ligand, _, _, _, provider = fixture()
    proposal = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)[0]
    original = FixedReceptorEvaluator.evaluate
    def wrong_model(self, state, neighbors):
        return replace(original(self, state, neighbors), evaluator_fingerprint_sha256="f"*64)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", wrong_model)
    coordinator = FixedReceptorStructureCoordinator(authority, ligand, provider,
        implementation_source_sha256="d"*64)
    with pytest.raises(StructureRefinementError):
        coordinator.run(proposal, max_steps=1)
    work = coordinator.failed_work[proposal.fingerprint_sha256]
    assert work.evaluation_attempts == work.physical_evaluation_attempts == work.graph_build_attempts == 1
    assert work.recoverable_rejections == 0
    assert coordinator.attempts[proposal.fingerprint_sha256].result.failed_evaluations == 1


def test_provider_capacity_denial_is_still_charged_to_core_failed_work():
    from betelgeuze_engine_v2.docking import DockingBudget
    from betelgeuze_engine_v2.docking.proposals import generate_bounded_docking_proposals
    from betelgeuze_product.fixed_receptor_structure_refinement import FixedReceptorStructureCoordinator
    authority, ligand, _, _, _, provider = fixture(max_evaluations=1)
    proposal = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)[0]
    coordinator = FixedReceptorStructureCoordinator(authority, ligand, provider,
        implementation_source_sha256="d"*64)
    with pytest.raises(StructureRefinementError):
        coordinator.run(proposal, max_steps=1)
    work = coordinator.failed_work[proposal.fingerprint_sha256]
    assert work.evaluation_attempts == 2
    assert work.provider_admitted_attempts == provider.evaluation_attempts == 1
    assert work.physical_evaluation_attempts == work.graph_build_attempts == 1
    assert work.recoverable_rejections == 0
    attempt = coordinator.attempts[proposal.fingerprint_sha256].result
    assert attempt.evaluation_attempts == 2
    assert attempt.successful_evaluations == attempt.failed_evaluations == 1


def test_zero_callback_anchor_failure_does_not_grow_failed_work_registry():
    from betelgeuze_engine_v2.docking import DockingBudget
    from betelgeuze_engine_v2.docking.proposals import generate_bounded_docking_proposals
    from betelgeuze_product.fixed_receptor_structure_refinement import FixedReceptorStructureCoordinator
    authority, ligand, _, _, _, provider = fixture()
    proposals = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=2, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)
    coordinator = FixedReceptorStructureCoordinator(authority, ligand, provider,
        implementation_source_sha256="d"*64, max_attempts=1)
    line = torch.tensor([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.], [3., 0., 0.]], dtype=torch.float64)
    for proposal in (*proposals, proposals[0]):
        degenerate = proposal.with_refined_coordinates(line, refiner_id="synthetic-test",
            refiner_version="1", refinement_receipt_sha256="a"*64)
        with pytest.raises(StructureRefinementError, match="degenerate torsion anchor"):
            coordinator.run(degenerate, max_steps=1)
    assert provider.evaluation_attempts == provider.graph_build_attempts == provider.physical_evaluation_attempts == 0
    assert not coordinator.attempts
    assert not coordinator.failed_work
    assert not coordinator.initial_constraint_rejections
