"""Single-point diagnostic checks against owning evaluators, never optimizers.

These tiny synthetic fixtures establish arithmetic/accounting behavior only;
no docking, force-field calibration, or scientific-validation claim is made.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import math

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    MolecularIntegrityError, canonical_system_sha256, canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_forcefield import ReferencePhysicsApplicabilityError
from betelgeuze_engine_v2.physics.reference_parameters import HarmonicBondParameter
from betelgeuze_product.cpu_refinement_diagnostics_v1 import evaluation as diagnostic
from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import COMPONENTS, empty_work
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierCrossParameters, FourierEnvironment, FourierFixedEvaluator, FourierInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import FourierParameters, NonbondedParameter
from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import (
    LinearAngleFixedEvaluator, LinearAngleInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_shape_v1 import cartesian as shape
from betelgeuze_product.cpu_refinement_shape_v1.profile import ShapeProfile, make_shape_observation
from betelgeuze_product.cpu_refinement_shape_v1.reference import ShapeContract
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, coordinates_hex, decode_coordinates, digest,
)
from betelgeuze_product.cpu_refinement_v1_3.kernel import make_observation
from tests.unit.test_cpu_parent_shape_cartesian import inputs, molecule
from tests.unit.test_cpu_parent_shape_linear_base import _inputs


@pytest.fixture(autouse=True)
def one_cpu_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _cross_fixture(distances, *, block=2, epsilon=.5, charge=.4, screening=.15):
    ligand = molecule([[0., 0., 0.]], 'diagnostic-ligand')
    ligand = replace(ligand, atoms=(replace(ligand.atoms[0], partial_charge_e=charge),))
    receptor = molecule([[r, 0., 0.] for r in distances], 'diagnostic-receptor')
    receptor = replace(receptor, atoms=tuple(
        replace(atom, partial_charge_e=(-1.)**i * charge) for i, atom in enumerate(receptor.atoms)))
    params = FourierParameters('synthetic-diagnostics', '1', canonical_topology_sha256(ligand),
                               (NonbondedParameter(0, 1.1, epsilon, charge),))
    cross = FourierCrossParameters('synthetic-cross', 'b'*64, canonical_system_sha256(receptor),
        canonical_topology_sha256(ligand), params.fingerprint_sha256, 'synthetic-frame',
        tuple(NonbondedParameter(i, .9 + i*.1, epsilon, atom.partial_charge_e)
              for i, atom in enumerate(receptor.atoms)),
        6., 4., .2, 4., screening, block, 0.)
    return ligand, params, FourierEnvironment(receptor, cross)


@pytest.mark.parametrize('epsilon,charge', [(.5, 0.), (0., .4), (.5, .4), (0., 0.)])
@pytest.mark.parametrize('block', [1, 2, 5])
@pytest.mark.parametrize('screening', [0., .15])
def test_split_cross_matches_owning_evaluator_and_counts_blocks(epsilon, charge, block, screening):
    distances = [.2, 1.3, 4., 4.8, 5.999, 6., 8.]
    ligand, params, fixed = _cross_fixture(distances, block=block, epsilon=epsilon,
                                          charge=charge, screening=screening)
    expected_energy, expected_force, pair_count = fixed.evaluate_cross(ligand, params)
    work = empty_work()
    energies, forces = diagnostic.split_cross(fixed, ligand, params, work)
    for name in COMPONENTS[1:]:
        torch.testing.assert_close(energies[name], expected_energy[name][0], rtol=1.e-12, atol=1.e-12)
    torch.testing.assert_close(sum(forces.values()), expected_force, rtol=1.e-12, atol=1.e-9)
    assert pair_count == 5
    active = sum(any(r < 6. for r in distances[start:start+block])
                 for start in range(0, len(distances), block))
    assert work == dict(empty_work(), cross_passes=1, cross_blocks_visited=math.ceil(7/block),
                        cross_blocks_active=active, cross_component_gradient_calls=2*active)
    assert not any(value.requires_grad for value in (*energies.values(), *forces.values()))


@pytest.mark.parametrize('distance', [6., 6.01, 20.])
def test_cutoff_inactive_blocks_return_exact_zeros_without_gradients(distance):
    ligand, params, fixed = _cross_fixture([distance])
    work = empty_work()
    energies, forces = diagnostic.split_cross(fixed, ligand, params, work)
    assert all(float(e) == 0. for e in energies.values())
    assert all(torch.count_nonzero(f) == 0 for f in forces.values())
    assert work == dict(empty_work(), cross_passes=1, cross_blocks_visited=1)


def test_minimum_distance_rejected_by_both_owning_and_diagnostic_routes():
    ligand, params, fixed = _cross_fixture([.199])
    with pytest.raises(ReferencePhysicsApplicabilityError, match='minimum distance'):
        fixed.evaluate_cross(ligand, params)
    work = empty_work()
    with pytest.raises(ResearchError, match='outside admitted domain'):
        diagnostic.split_cross(fixed, ligand, params, work)
    assert work == dict(empty_work(), cross_passes=1, cross_blocks_visited=1)


@pytest.mark.parametrize('distance', [1.3, 4., 4.8, 5.9])
def test_each_cross_force_matches_independent_owning_energy_finite_difference(distance):
    ligand, params, fixed = _cross_fixture([distance], screening=.3)
    _, forces = diagnostic.split_cross(fixed, ligand, params, empty_work())
    step = 1.e-5
    for axis in range(3):
        plus, minus = ligand.coordinates.clone(), ligand.coordinates.clone()
        plus[0, 0, axis] += step
        minus[0, 0, axis] -= step
        eplus, _, _ = fixed.evaluate_cross(ligand.with_coordinates(plus, operation='single_point_test'), params)
        eminus, _, _ = fixed.evaluate_cross(ligand.with_coordinates(minus, operation='single_point_test'), params)
        for name in COMPONENTS[1:]:
            expected = -(eplus[name][0] - eminus[name][0]) / (2*step)
            torch.testing.assert_close(forces[name][0, 0, axis], expected, rtol=2.e-7, atol=2.e-8)


def _admitted(profile):
    if profile == 'fourier':
        ligand, params, config, fixed, binding = inputs()
        params = replace(params, bonds=(HarmonicBondParameter(0, 1, 1.8, 40.),),
                         excluded_pairs=((0, 1),))
        fixed = FourierEnvironment(fixed.receptor, replace(fixed.cross,
            ligand_base_parameters_sha256=params.fingerprint_sha256))
        evaluator = FourierFixedEvaluator(params, fixed)
    else:
        ligand, params, config, fixed, binding = _inputs()
        evaluator = LinearAngleFixedEvaluator(params, fixed)
    return ligand, evaluator, config, binding


def _owning_point(ligand, evaluator, config):
    neighbors = build_compact_radius_graph(ligand.coordinates, RadiusGraphConfig(
        cutoff_angstrom=evaluator.parameters.base_parameters.cutoff_angstrom,
        max_neighbors=config.max_neighbors, max_atoms_per_cell=config.max_atoms_per_cell))
    result = evaluator.evaluate(ligand, neighbors)
    parts = {name: float(value[0]) for name, value in result.component_energies.items()}
    parts['total'] = float(result.term.energy[0])
    observation = make_observation(1, ligand.coordinates, parts['total'], result.term.forces, parts)
    internal_type = FourierInternalEvaluator if type(evaluator) is FourierFixedEvaluator else LinearAngleInternalEvaluator
    return observation, internal_type(evaluator.parameters).evaluate(ligand, neighbors)


@pytest.mark.parametrize('profile', ['fourier', 'linear_angle'])
def test_diagnose_real_admitted_single_points_internal_leaves_and_identity(profile):
    original, evaluator, config, _ = _admitted(profile)
    xyz = original.coordinates.clone()
    xyz[0, 0] += torch.tensor([.1, .2, -.1], dtype=torch.float64)
    trial = original.with_coordinates(xyz, operation='single_point_test')
    observation, internal = _owning_point(trial, evaluator, config)
    before = deepcopy(observation)
    record = diagnostic.diagnose_observation(original, evaluator, config, observation,
                                             observation_ref={'attempt': 1})
    assert record['status'] == 'evaluated', record
    assert all(row['passed'] for row in record['parity'].values())
    assert record['failure_code'] is None
    assert record['source_evidence_verified'] is False
    assert record['internal_component_forces_available'] is False
    assert record['internal_component_energy_semantics'] == 'subdivision_of_ligand_internal_not_additional_terms'
    assert record['internal_component_energies'] == {
        name: float(value[0]).hex() for name, value in internal.component_energies.items()}
    torch.testing.assert_close(decode_coordinates(record['components']['ligand_internal']['forces'], original.atom_count),
                               internal.term.forces, rtol=0., atol=0.)
    assert sum(map(float.fromhex, record['internal_component_energies'].values())) == pytest.approx(
        float.fromhex(record['components']['ligand_internal']['energy']), abs=1.e-12)
    assert set(record['components']) == set(COMPONENTS)
    assert record['atoms'] == [{'source_index': atom.index, 'element': atom.element,
                               'atom_metadata_sha256': digest(asdict(atom))} for atom in original.atoms]
    assert record['work'] == dict(empty_work(), graph_calls=1, internal_evaluator_calls=1,
        cross_passes=1, cross_blocks_visited=1, cross_blocks_active=1, cross_component_gradient_calls=2)
    assert observation == before
    assert record['record_sha256'] == digest({k: v for k, v in record.items() if k != 'record_sha256'})
    assert record['wall_ns'] >= 0


@pytest.mark.parametrize('profile', ['fourier', 'linear_angle'])
@pytest.mark.parametrize('strength', [0., 100., 1000.])
def test_shape_retains_component_without_recomputing_restraint(profile, strength, monkeypatch):
    original, evaluator, config, binding = _admitted(profile)
    contract = ShapeContract(shape.prepare_reference(original, binding), strength)
    shape_profile = ShapeProfile(contract, strength, shape.system_identity, shape._calculate)
    xyz = original.coordinates.clone()
    xyz[0, 0, 0] += .15
    trial = original.with_coordinates(xyz, operation='single_point_test')
    base, _ = _owning_point(trial, evaluator, config)
    penalty, rows = shape._calculate(contract, xyz[0].tolist(), strength, **shape.system_identity(trial))
    shape_forces = torch.tensor([rows], dtype=torch.float64)
    observed = make_shape_observation(base, penalty, shape_forces, strength)
    def forbidden(*args, **kwargs):
        pytest.fail('diagnostics must reuse retained shape forces, not evaluate them')
    monkeypatch.setattr(ShapeContract, 'evaluate', forbidden)
    record = diagnostic.diagnose_observation(original, evaluator, config, observed,
        observation_ref={'attempt': 1}, shape_profile=shape_profile)
    assert record['status'] == 'evaluated', record
    assert record['components']['parent_shape_restraint']['forces'] == observed['restraint_forces']
    assert record['components']['parent_shape_restraint']['energy'] == observed['components']['parent_shape_restraint']
    assert record['work']['retained_shape_reuses'] == 1
    assert record['augmented_total']['energy'] == observed['energy']
    torch.testing.assert_close(decode_coordinates(record['augmented_total']['forces'], original.atom_count),
                               decode_coordinates(observed['forces'], original.atom_count), rtol=1.e-10, atol=1.e-9)
    assert all(row['passed'] for row in record['parity'].values())
    if strength == 0.:
        assert record['augmented_total'] == record['unpenalized_total']


@pytest.mark.parametrize('change', ['energy', 'forces'])
def test_self_consistent_but_wrong_observation_is_visible_parity_failure(change):
    ligand, evaluator, config, _ = _admitted('fourier')
    observed, _ = _owning_point(ligand, evaluator, config)
    parts = {k: float.fromhex(v) for k, v in observed['components'].items()}
    force = decode_coordinates(observed['forces'], ligand.atom_count)
    if change == 'energy':
        parts['cross_lennard_jones'] += 1.
        parts['total'] += 1.
    else:
        force[0, 0, 0] += 1.
    wrong = make_observation(1, ligand.coordinates, parts['total'], force, parts)
    record = diagnostic.diagnose_observation(ligand, evaluator, config, wrong, observation_ref='wrong')
    assert record['status'] == 'parity_failed'
    assert record['failure_code'] is None
    assert record['work']['failed_evaluations'] == 0
    assert not record['parity']['unpenalized_' + ('energy' if change == 'energy' else 'forces')]['passed']
    assert record['geometry'] is not None


def test_atom_force_ties_use_first_source_identity_and_retain_array_digest():
    atoms = [{'source_index': 7}, {'source_index': 2}, {'source_index': 9}]
    forces = torch.tensor([[[3., 4., 0.], [-3., -4., 0.], [0., 0., 1.]]], dtype=torch.float64)
    row = diagnostic._component(torch.tensor(2.), forces, atoms)
    assert row['highest_force_atom'] == atoms[0]
    assert row['maximum_atom_force'] == 5..hex()
    assert row['force_l2_norm'] == math.sqrt(51.).hex()
    assert row['net_force'] == [0..hex(), 0..hex(), 1..hex()]
    assert row['forces_sha256'] == digest(coordinates_hex(forces))
    zeros = diagnostic._component(0., torch.zeros_like(forces), atoms)
    assert zeros['highest_force_atom'] == atoms[0]


def test_evaluation_failure_retains_failure_type_and_attempted_work(monkeypatch):
    ligand, evaluator, config, _ = _admitted('fourier')
    observed, _ = _owning_point(ligand, evaluator, config)
    def fail(*args):
        raise FloatingPointError('private detail must not become a record')
    monkeypatch.setattr(FourierInternalEvaluator, 'evaluate', fail)
    record = diagnostic.diagnose_observation(ligand, evaluator, config, observed, observation_ref='failed')
    assert record['status'] == 'failed'
    assert record['failure_code'] == 'FloatingPointError'
    assert record['work'] == dict(empty_work(), graph_calls=1, internal_evaluator_calls=1, failed_evaluations=1)
    assert 'private detail' not in repr(record)


def test_cross_noncollinear_multi_atom_blocks_match_each_owning_energy_derivative():
    ligand, params, fixed = _cross_fixture([1.3, 4.8, 9.], block=1)
    # Distinct atom identities, charges and sigma/epsilon expose index and
    # broadcasting mistakes; the final receptor block remains inactive.
    ligand = molecule([[.1, .2, -.3], [-.4, .1, .5]], 'diagnostic-two-atom')
    ligand = replace(ligand, atoms=tuple(replace(atom, partial_charge_e=q)
        for atom, q in zip(ligand.atoms, [.4, -.2])))
    params = replace(params, topology_sha256=canonical_topology_sha256(ligand),
        atom_parameters=(NonbondedParameter(0, 1.1, .5, .4), NonbondedParameter(1, 1.4, .3, -.2)))
    fixed = FourierEnvironment(fixed.receptor, replace(fixed.cross,
        ligand_topology_sha256=canonical_topology_sha256(ligand),
        ligand_base_parameters_sha256=params.fingerprint_sha256))
    expected_energy, expected_force, _ = fixed.evaluate_cross(ligand, params)
    work = empty_work()
    energies, forces = diagnostic.split_cross(fixed, ligand, params, work)
    torch.testing.assert_close(sum(forces.values()), expected_force, rtol=1.e-12, atol=1.e-12)
    for name in COMPONENTS[1:]:
        torch.testing.assert_close(energies[name], expected_energy[name][0], rtol=0., atol=0.)
    step = 1.e-5
    for atom in range(2):
        for axis in range(3):
            plus, minus = ligand.coordinates.clone(), ligand.coordinates.clone()
            plus[0, atom, axis] += step
            minus[0, atom, axis] -= step
            ep, _, _ = fixed.evaluate_cross(ligand.with_coordinates(plus, operation='finite_difference'), params)
            em, _, _ = fixed.evaluate_cross(ligand.with_coordinates(minus, operation='finite_difference'), params)
            for name in COMPONENTS[1:]:
                torch.testing.assert_close(forces[name][0, atom, axis], -(ep[name][0]-em[name][0])/(2*step),
                                           rtol=3.e-7, atol=2.e-8)
    assert work == dict(empty_work(), cross_passes=1, cross_blocks_visited=3,
                        cross_blocks_active=2, cross_component_gradient_calls=4)


@pytest.mark.parametrize('mismatch', ['parameter_fingerprint', 'ligand_charge', 'receptor_coordinates'])
def test_split_cross_rejects_identity_drift_before_counting_work(mismatch):
    ligand, params, fixed = _cross_fixture([2.])
    if mismatch == 'parameter_fingerprint':
        params = replace(params, parameter_set_id='changed-identity')
    elif mismatch == 'ligand_charge':
        ligand = replace(ligand, atoms=(replace(ligand.atoms[0], partial_charge_e=.8),))
    else:
        fixed.receptor.coordinates[0, 0, 0] += .1
    work = empty_work()
    error = MolecularIntegrityError if mismatch == 'receptor_coordinates' else ResearchError
    with pytest.raises(error):
        diagnostic.split_cross(fixed, ligand, params, work)
    assert work == empty_work()


@pytest.mark.parametrize('kind,leaf', [('proper', 'periodic_torsion'),
                                       ('improper', 'ordered_periodic_improper')])
def test_nonzero_signed_fourier_and_listed_pair_leaves_are_retained_once(kind, leaf):
    from betelgeuze_product.cpu_refinement_fourier_v1.parameters import ListedPairParameter
    from betelgeuze_engine_v2.physics.reference_parameters import COULOMB_KCAL_ANGSTROM_PER_MOL_E2

    from betelgeuze_engine_v2.molecular import Bond
    from betelgeuze_engine_v2.physics.reference_parameters import HarmonicAngleParameter
    from betelgeuze_product.cpu_refinement_fourier_v1.parameters import (
        SignedPeriodicTorsionParameter, OrderedPeriodicImproperParameter,
    )
    xyz = [[0., 1., 0.], [0., 0., 0.], [1., 0., 0.],
           [1., math.cos(.6), math.sin(.6)]]
    bonds = [(0, 1), (1, 2), (2, 3)] if kind == 'proper' else [(0, 1), (1, 2), (1, 3)]
    angles = [(0, 1, 2), (1, 2, 3)] if kind == 'proper' else [(0, 1, 2), (0, 1, 3), (2, 1, 3)]
    ligand = molecule(xyz, 'nonzero-fourier-ligand')
    ligand = replace(ligand, bonds=tuple(Bond(i, *pair) for i, pair in enumerate(bonds)))
    positions = ligand.coordinates[0]
    bond_params = tuple(HarmonicBondParameter(i, j, float(torch.linalg.vector_norm(positions[i]-positions[j])), 2.)
                        for i, j in bonds)
    angle_params = []
    for i, j, k in angles:
        a, b = positions[i]-positions[j], positions[k]-positions[j]
        angle = math.acos(float(torch.dot(a, b)/(torch.linalg.vector_norm(a)*torch.linalg.vector_norm(b))))
        angle_params.append(HarmonicAngleParameter(i, j, k, angle, 1.8))
    terms = ({'torsions': (SignedPeriodicTorsionParameter(0, 1, 2, 3, 3, .4, -1.7),)}
             if kind == 'proper' else {'periodic_impropers': (
                 OrderedPeriodicImproperParameter(0, 1, 2, 3, 3, .4, -1.7, star_center=1),)})
    params = FourierParameters('nonzero-leaves', '1', canonical_topology_sha256(ligand),
        tuple(NonbondedParameter(i, 1., 0., 0.) for i in range(4)),
        bonds=bond_params, angles=tuple(angle_params),
        excluded_pairs=tuple((i, j) for i in range(4) for j in range(i+1, 4)), **terms)
    charges = [.3, 0., 0., -.2]
    ligand = replace(ligand, atoms=tuple(replace(atom, partial_charge_e=q)
        for atom, q in zip(ligand.atoms, charges)))
    params = replace(params, topology_sha256=canonical_topology_sha256(ligand),
        atom_parameters=tuple(NonbondedParameter(i, 1., 0., q) for i, q in enumerate(charges)),
        listed_pairs=(ListedPairParameter(0, 3, 1.5, .2, .83333),))
    receptor = molecule([[20., 0., 0.]], 'inactive-fixed-receptor')
    cross = FourierCrossParameters('nonzero-fourier-leaves', 'b'*64,
        canonical_system_sha256(receptor), canonical_topology_sha256(ligand),
        params.fingerprint_sha256, 'synthetic-frame', (NonbondedParameter(0, 1., 0., 0.),),
        10., 8., .2, 1., 0., 1, 0.)
    evaluator = FourierFixedEvaluator(params, FourierEnvironment(receptor, cross))
    _, _, config, _, _ = inputs()
    observed, internal = _owning_point(ligand, evaluator, config)
    record = diagnostic.diagnose_observation(ligand, evaluator, config, observed,
                                             observation_ref={'synthetic_kind': kind})
    assert record['status'] == 'evaluated', record
    expected = {leaf: -1.7*(1.+math.cos(3.*.6-.4))}
    distance = float(torch.linalg.vector_norm(ligand.coordinates[0, 0] - ligand.coordinates[0, 3]))
    ratio6 = (1.5 / distance)**6
    expected['listed_pair_lennard_jones'] = 4*.2*(ratio6**2-ratio6)
    expected['listed_pair_coulomb'] = COULOMB_KCAL_ANGSTROM_PER_MOL_E2*.3*(-.2)*.83333/distance
    leaves = {name: float.fromhex(value) for name, value in record['internal_component_energies'].items()}
    assert leaves[leaf] < 0.  # Preserve the signed Fourier offset, not abs/clipped energy.
    for name in (leaf, 'listed_pair_lennard_jones', 'listed_pair_coulomb'):
        assert abs(expected[name]) > 1.e-3
        assert leaves[name] == pytest.approx(expected[name], rel=1.e-10, abs=1.e-9)
        assert leaves[name] == float(internal.component_energies[name][0])
    # All nonzero explanatory leaves belong to internal energy exactly once.
    expected_total = math.fsum(expected.values())
    assert math.fsum(leaves.values()) == pytest.approx(expected_total, abs=1.e-9)
    assert float.fromhex(record['components']['ligand_internal']['energy']) == pytest.approx(expected_total, abs=1.e-9)
    assert float.fromhex(record['unpenalized_total']['energy']) == pytest.approx(expected_total, abs=1.e-9)
    assert record['internal_component_forces_available'] is False
    assert all(row['passed'] for row in record['parity'].values())
