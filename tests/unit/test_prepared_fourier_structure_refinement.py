"""Synthetic bridge regressions only: no chemistry or runtime qualification."""
from dataclasses import replace
import pytest
import torch
from betelgeuze_engine_v2.geometry import build_compact_radius_graph, RadiusGraphConfig
from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_engine_v2.docking.proposals import generate_bounded_docking_proposals
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import (
    FourierParameters, NonbondedParameter, SignedPeriodicTorsionParameter, ListedPairParameter,
)
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierCrossParameters, FourierEnvironment, FourierFixedEvaluator, ENERGY_BASIS,
)
from betelgeuze_product.fixed_receptor_structure_refinement import (
    FixedReceptorEnergyForceProvider, FixedReceptorStructureCoordinator,
)
from betelgeuze_product.structure_preserving import SearchConfig, RecoverableTrialRejection
from betelgeuze_product.structure_preserving_refinement import StructureRefinementError
from tests.unit.test_fixed_receptor_structure_refinement import fixture as legacy_fixture, points


def fixture(**kwargs):
    a, lig, rec, legacy, cross, _ = legacy_fixture(charged=True)
    base = legacy.base_parameters
    p = FourierParameters(parameter_set_id='synthetic-fourier-not-chemistry',
        parameter_set_version='1', topology_sha256=base.topology_sha256,
        atom_parameters=tuple(NonbondedParameter(r.atom_index, r.sigma_angstrom,
            r.epsilon_kcal_per_mol, r.charge_e) for r in base.atom_parameters),
        bonds=base.bonds, angles=base.angles,
        torsions=(SignedPeriodicTorsionParameter(0, 1, 2, 3, 2, .3, -.2),),
        excluded_pairs=base.excluded_pairs,
        listed_pairs=(ListedPairParameter(0, 3, 1.2, .1, .5),))
    d = cross.to_dict()
    d['schema_id'] = 'cpu_prepared_fourier_cross/1.0.0'
    d['ligand_base_parameters_sha256'] = p.fingerprint_sha256
    c = FourierCrossParameters.from_dict(d)
    provider = FixedReceptorEnergyForceProvider(a, lig, rec, p, c,
        implementation_source_sha256='e'*64, **kwargs)
    return a, lig, rec, p, c, provider


def test_existing_combined_evaluator_is_reused_with_exact_raw_forces():
    _, lig, rec, p, c, provider = fixture()
    expected_evaluator = FourierFixedEvaluator(p, FourierEnvironment(rec, c))
    for shift in (0., .03, -.02):
        state = lig.with_coordinates(lig.coordinates + shift, operation='synthetic')
        actual = provider.evaluate(points(state))
        expected = expected_evaluator.evaluate(state, build_compact_radius_graph(
            state.coordinates, RadiusGraphConfig(p.cutoff_angstrom, 256, 256)))
        assert actual.energy == float(expected.term.energy[0])
        assert actual.forces == tuple(tuple(float(x) for x in row) for row in expected.term.forces[0])
    assert provider.evaluation_attempts == provider.physical_evaluation_attempts == 3
    assert sum(r.admitted_attempts for r in provider.callbacks) == 3
    assert all(r.status == 'success' for r in provider.callbacks)
    row = provider.observations[-1]
    assert row.energy_semantics == ENERGY_BASIS
    assert row.force_semantics == 'negative_coordinate_gradient_of_reference_force_field_energy'
    assert not row.calibrated and not row.force_calibrated and not row.validated_for_composition
    assert row.constraint_observations == ()
    assert 'prepared_fourier_model_not_scientifically_validated' in row.scientific_blockers
    assert set(row.components_document()) == {'ligand_internal', 'cross_lennard_jones', 'cross_screened_coulomb', 'total'}


def test_finite_difference_of_total_matches_raw_force():
    _, lig, _, _, _, provider = fixture()
    xyz = lig.coordinates.clone()
    actual = provider.evaluate(points(lig))
    h = 1e-5
    for i in range(lig.atom_count):
        for j in range(3):
            plus, minus = xyz.clone(), xyz.clone()
            plus[0, i, j] += h
            minus[0, i, j] -= h
            ep = provider.evaluate(points(lig.with_coordinates(plus, operation='synthetic-fd'))).energy
            em = provider.evaluate(points(lig.with_coordinates(minus, operation='synthetic-fd'))).energy
            assert actual.forces[i][j] == pytest.approx(-(ep-em)/(2*h), abs=1e-6, rel=1e-6)


def test_mixed_profile_frame_and_parameter_bindings_fail_closed():
    a, lig, rec, p, c, _ = fixture()
    _, _, _, legacy, legacy_cross, _ = legacy_fixture()
    for params, cross in ((p, legacy_cross), (legacy, c)):
        with pytest.raises(StructureRefinementError):
            FixedReceptorEnergyForceProvider(a, lig, rec, params, cross, implementation_source_sha256='e'*64)
    with pytest.raises(StructureRefinementError):
        FixedReceptorEnergyForceProvider(a, lig, rec, p, replace(c, coordinate_frame_id='wrong'), implementation_source_sha256='e'*64)
    with pytest.raises(Exception):
        FixedReceptorEnergyForceProvider(a, lig, rec, p, replace(c, ligand_base_parameters_sha256='0'*64), implementation_source_sha256='e'*64)


def test_every_callback_including_preflight_and_collision_is_accounted():
    _, lig, rec, _, _, provider = fixture(max_evaluations=2)
    xyz = lig.coordinates.clone()
    xyz[0, 0] = rec.coordinates[0, 0]
    with pytest.raises(RecoverableTrialRejection):
        provider.evaluate(points(lig.with_coordinates(xyz, operation='synthetic-collision')))
    provider.evaluate(points(lig))
    with pytest.raises(StructureRefinementError):
        provider.evaluate(points(lig))
    assert [r.status for r in provider.callbacks] == ['recoverable_rejection', 'success']
    assert [r.admitted_attempts for r in provider.callbacks] == [1, 1]
    assert [r.physical_evaluation_attempts for r in provider.callbacks] == [0, 1]
    assert [r.recoverable_rejections for r in provider.callbacks] == [1, 0]
    for _ in range(1000):
        with pytest.raises(StructureRefinementError):
            provider.evaluate(points(lig))
    assert len(provider.callbacks) == 2
    assert provider.preflight_denials == 1001
    assert provider.callback_attempts == provider.evaluation_attempts + provider.preflight_denials == 1003


def test_existing_coordinator_and_final_strain_policy_remain_bound():
    a, lig, _, _, c, provider = fixture()
    proposal = generate_bounded_docking_proposals(a.search_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=a.problem)[0]
    coordinator = FixedReceptorStructureCoordinator(a, lig, provider,
        implementation_source_sha256='d'*64, config=SearchConfig(max_steps=3, max_evaluations=16))
    outcome = coordinator.run(proposal, max_steps=3)
    assert outcome.evaluation_attempts == len(provider.callbacks)
    assert outcome.physical_evaluation_attempts == sum(r.physical_evaluation_attempts for r in provider.callbacks)
    assert outcome.max_internal_increase_kcal_per_mol == c.max_internal_increase_kcal_per_mol
    assert outcome.admission_document()['converged'] is False
    assert not outcome.scientifically_validated
