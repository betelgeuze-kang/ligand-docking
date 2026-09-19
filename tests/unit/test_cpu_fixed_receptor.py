"""D3 independent pair derivatives, block equivalence, integrity and real descent."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import math
import pytest
import torch
from betelgeuze_engine_v2.molecular import AllAtomSystem, Atom, Chain, Residue, StructureProvenance, canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter, ReferenceForceFieldParameters
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, FixedReceptorEnvironment, ReferencePhysicsApplicabilityError
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig, minimize_extended
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError

def system(xyz, charges=None, name='synthetic'):
    charges = [0.0] * len(xyz) if charges is None else charges
    return AllAtomSystem(name, tuple((Atom(index=i, name=f'C{i}', element='C', atomic_number=6, residue_index=0, partial_charge_e=float(charges[i])) for i in range(len(xyz)))), (), (Residue(index=0, name='LIG', chain_index=0, sequence_number=1, atom_indices=tuple(range(len(xyz))), entity_type='non_polymer', hetero=True),), (Chain(index=0, chain_id='L', residue_indices=(0,)),), torch.tensor([xyz], dtype=torch.float64), StructureProvenance(source_format='unit', source_id=name, source_sha256='a' * 64, parser_name='synthetic', parser_version='1'))

def base_parameters(ligand, sigma=1.0, epsilon=0.5):
    return ReferenceForceFieldParameters('synthetic-explicit', '1', canonical_topology_sha256(ligand), tuple((AtomNonbondedParameter(i, sigma, epsilon, float(a.partial_charge_e)) for i, a in enumerate(ligand.atoms))), excluded_pairs=tuple(((i, j) for i in range(ligand.atom_count) for j in range(i + 1, ligand.atom_count))))

def environment(receptor, ligand, base, *, block=2, sigma=1.0, epsilon=0.5, **kwargs):
    return FixedReceptorEnvironment(receptor, CrossParameters(parameter_set_id='synthetic-cross', parameter_source_sha256='b' * 64, receptor_system_sha256=canonical_system_sha256(receptor), ligand_topology_sha256=canonical_topology_sha256(ligand), ligand_base_parameters_sha256=base.fingerprint_sha256, coordinate_frame_id='test-frame', receptor_atoms=tuple((AtomNonbondedParameter(i, sigma, epsilon, float(a.partial_charge_e)) for i, a in enumerate(receptor.atoms))), cutoff_angstrom=6.0, switch_start_angstrom=4.0, minimum_distance_angstrom=0.2, dielectric=4.0, screening_kappa_per_angstrom=0.15, receptor_block_size=block, max_internal_increase_kcal_per_mol=2.0, **kwargs))

def scalar_pair(r, sigma, epsilon, qprod, cross):
    if r >= cross.cutoff_angstrom:
        return (0.0, 0.0)
    s6 = (sigma / r) ** 6
    lj = 4 * epsilon * (s6 * s6 - s6)
    dlj = 24 * epsilon * (s6 - 2 * s6 * s6) / r
    q = 332.063713299 * qprod * math.exp(-cross.screening_kappa_per_angstrom * r) / (cross.dielectric * r)
    dq = -q * (cross.screening_kappa_per_angstrom + 1 / r)
    sw, dsw = (1.0, 0.0)
    if r > cross.switch_start_angstrom:
        width = cross.cutoff_angstrom - cross.switch_start_angstrom
        x = (r - cross.switch_start_angstrom) / width
        sw = 1 - 10 * x ** 3 + 15 * x ** 4 - 6 * x ** 5
        dsw = (-30 * x * x + 60 * x ** 3 - 30 * x ** 4) / width
    return ((lj + q) * sw, (dlj + dq) * sw + (lj + q) * dsw)

@pytest.mark.parametrize('r', [0.5, 0.9, 1.0, 2 ** (1 / 6), 2.0, 3.9, 4.0, 4.000001, 4.8, 5.99999, 6.0, 7.0])
@pytest.mark.parametrize('charges', [(0.0, 0.0), (0.3, -0.2), (0.3, 0.2)])
def test_independent_analytic_pair_energy_force(r, charges):
    ligand = system([[r, 0, 0]], [charges[0]], 'lig')
    receptor = system([[0, 0, 0]], [charges[1]], 'rec')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base)
    terms, forces, count = env.evaluate_cross(ligand, base)
    expected, derivative = scalar_pair(r, 1.0, 0.5, charges[0] * charges[1], env.cross)
    assert sum((float(v[0]) for v in terms.values())) == pytest.approx(expected, rel=2e-10, abs=1e-11)
    assert float(forces[0, 0, 0]) == pytest.approx(-derivative, rel=1e-09, abs=1e-10)
    assert torch.equal(forces[0, 0, 1:], torch.zeros(2, dtype=torch.float64))
    assert count == int(r < 6)

@pytest.mark.parametrize('block', [1, 2, 3, 7, 128])
def test_all_pairs_once_and_blocked_force_matches_independent_math(block):
    receptor = system([[0, 0, 0], [2, 0, 0], [0, 4, 0], [8, 0, 0]], [0.2, -0.2, 0.1, 0.3], 'rec')
    ligand = system([[1, 2, 1], [-2, 3, -1]], [0.3, -0.4], 'lig')
    base = base_parameters(ligand, sigma=1.2, epsilon=0.4)
    env = environment(receptor, ligand, base, block=block, sigma=1.6, epsilon=0.9)
    terms, force, count = env.evaluate_cross(ligand, base)
    e = 0.0
    f = torch.zeros_like(force)
    pairs = 0
    for i, x in enumerate(ligand.coordinates[0]):
        for j, y in enumerate(receptor.coordinates[0]):
            d = (x - y).tolist()
            r = math.sqrt(sum((v * v for v in d)))
            ee, derivative = scalar_pair(r, 1.4, 0.6, float(ligand.atoms[i].partial_charge_e * receptor.atoms[j].partial_charge_e), env.cross)
            e += ee
            f[0, i] -= derivative * torch.tensor(d, dtype=torch.float64) / r
            pairs += r < 6
    assert sum((float(v[0]) for v in terms.values())) == pytest.approx(e, abs=1e-12)
    torch.testing.assert_close(force, f, rtol=1e-12, atol=1e-12)
    assert count == pairs

def test_receptor_above_ligand_capacity_not_silently_truncated():
    receptor = system([[100 + 2 * i, 0, 0] for i in range(299)] + [[0, 0, 0]], name='rec')
    ligand = system([[2, 0, 0]], name='lig')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base, block=17)
    terms, force, count = env.evaluate_cross(ligand, base)
    e, d = scalar_pair(2, 1.0, 0.5, 0.0, env.cross)
    assert count == 1 and float(force[0, 0, 0]) == pytest.approx(-d)
    assert float(terms['cross_lennard_jones'][0]) == pytest.approx(e)

def test_joint_rigid_transform_and_fixed_receptor_integrity():
    receptor = system([[0, 0, 0], [0, 3, 0]], [0.1, -0.1], 'rec')
    ligand = system([[2, 1, 1]], [0.2], 'lig')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base)
    e, f, _ = env.evaluate_cross(ligand, base)
    old = receptor.coordinates.clone()
    rotation = torch.tensor([[0.36, -0.48, 0.8], [0.8, 0.6, 0], [-0.48, 0.64, 0.6]], dtype=torch.float64)
    rr = receptor.with_coordinates(receptor.coordinates @ rotation.T + 0.25, operation='transform')
    ll = ligand.with_coordinates(ligand.coordinates @ rotation.T + 0.25, operation='transform')
    ee, ff, _ = environment(rr, ll, base).evaluate_cross(ll, base)
    assert sum((v.item() for v in e.values())) == pytest.approx(sum((v.item() for v in ee.values())), abs=1e-12)
    torch.testing.assert_close(ff, f @ rotation.T, rtol=1e-11, atol=1e-12)
    assert torch.equal(receptor.coordinates, old)
    receptor.coordinates[0, 0, 0] += 0.01
    with pytest.raises(ResearchError, match='changed'):
        env.evaluate_cross(ligand, base)

def test_minimum_distance_rejected_not_softened():
    receptor = system([[0, 0, 0]], name='rec')
    ligand = system([[0.1, 0, 0]], name='lig')
    base = base_parameters(ligand)
    with pytest.raises(ReferencePhysicsApplicabilityError, match='minimum distance'):
        environment(receptor, ligand, base).evaluate_cross(ligand, base)

@pytest.mark.parametrize('kind', ['block', 'cutoff', 'switch', 'minimum', 'dielectric', 'kappa', 'strain', 'policy', 'coverage', 'charge', 'frame'])
def test_malformed_cross_contract(kind):
    receptor = system([[0, 0, 0]], name='rec')
    ligand = system([[2, 0, 0]], name='lig')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base)
    doc = env.cross.to_dict()
    if kind == 'block':
        doc['receptor_block_size'] = True
    elif kind == 'cutoff':
        doc['cutoff_angstrom'] = float('nan')
    elif kind == 'switch':
        doc['switch_start_angstrom'] = 6.0
    elif kind == 'minimum':
        doc['minimum_distance_angstrom'] = 0.0
    elif kind == 'dielectric':
        doc['dielectric'] = 0.0
    elif kind == 'kappa':
        doc['screening_kappa_per_angstrom'] = -1.0
    elif kind == 'strain':
        doc['max_internal_increase_kcal_per_mol'] = True
    elif kind == 'policy':
        doc['pair_policy'] = 'covalent'
    elif kind == 'coverage':
        doc['receptor_atoms'][0]['atom_index'] = 1
    elif kind == 'charge':
        doc['receptor_atoms'][0]['charge_e'] = 999.0
    else:
        doc['coordinate_frame_id'] = ''
    with pytest.raises(ValueError):
        CrossParameters.from_dict(doc)

def test_cross_charge_mismatch_and_parameter_mismatch_fail():
    receptor = system([[0, 0, 0]], name='rec')
    ligand = system([[2, 0, 0]], [0.2], 'lig')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base)
    wrong = replace(base, atom_parameters=(AtomNonbondedParameter(0, 1, 0.5, 0.1),))
    with pytest.raises(ResearchError, match='parameters'):
        env.evaluate_cross(ligand, wrong)
    with pytest.raises(ResearchError, match='charges'):
        environment(receptor, ligand, wrong).evaluate_cross(ligand, wrong)

def test_real_minimization_moves_toward_target_and_restarts_exactly():
    receptor = system([[0, 0, 0]], name='rec')
    ligand = system([[2.0, 0, 0]], name='lig')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base)
    params = ReferenceForceFieldV2Parameters(base)
    config = SolverConfig(ReferenceMinimizationConfig(max_iterations=8, initial_step_size_angstrom2_mol_per_kcal=0.03))
    full = minimize_extended(ligand, params, config, fixed_environment=env)
    paused = minimize_extended(ligand, params, config, fixed_environment=env, pause_after_accepted_iterations=2)
    resumed = minimize_extended(ligand, params, config, fixed_environment=env, checkpoint=paused.checkpoint)
    doc = full.checkpoint.to_dict()
    assert doc['accepted_iterations'] > 0 and doc['current_energy'] < doc['initial_energy']
    assert float(full.system.coordinates[0, 0, 0]) < 2.0
    assert torch.equal(receptor.coordinates, torch.zeros((1, 1, 3), dtype=torch.float64))
    assert doc == resumed.checkpoint.to_dict()
    assert doc['current_components']['ligand_internal'] == 0.0
    assert paused.execution['force_evaluation_calls'] + resumed.execution['force_evaluation_calls'] == full.execution['force_evaluation_calls'] + 1
    rr = receptor.with_coordinates(receptor.coordinates + 0.1, operation='changed')
    with pytest.raises(ResearchError, match='identity mismatch'):
        minimize_extended(ligand, params, config, fixed_environment=environment(rr, ligand, base), checkpoint=paused.checkpoint)
    with pytest.raises(ResearchError, match='identity mismatch'):
        minimize_extended(ligand, params, config, checkpoint=paused.checkpoint)

def test_current_component_corruption_rejected_after_rehash():
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
    receptor = system([[0, 0, 0]], name='rec')
    ligand = system([[2.0, 0, 0]], name='lig')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base)
    params = ReferenceForceFieldV2Parameters(base)
    cfg = SolverConfig(ReferenceMinimizationConfig(max_iterations=3))
    run = minimize_extended(ligand, params, cfg, fixed_environment=env, pause_after_accepted_iterations=1)
    doc = deepcopy(run.checkpoint.to_dict())
    doc['current_components']['ligand_internal'] += 1
    doc['checkpoint_sha256'] = digest({k: v for k, v in doc.items() if k != 'checkpoint_sha256'})
    with pytest.raises(ResearchError, match='component'):
        minimize_extended(ligand, params, cfg, fixed_environment=env, checkpoint=doc)

def test_pair_relaxation_reaches_analytic_lj_minimum():
    receptor = system([[0, 0, 0]], name='rec')
    ligand = system([[1.25, 0, 0]], name='lig')
    base = base_parameters(ligand)
    env = environment(receptor, ligand, base)
    params = ReferenceForceFieldV2Parameters(base)
    config = SolverConfig(ReferenceMinimizationConfig(max_iterations=100, initial_step_size_angstrom2_mol_per_kcal=0.02, force_tolerance_kcal_per_mol_angstrom=1e-05))
    result = minimize_extended(ligand, params, config, fixed_environment=env)
    assert result.converged
    assert float(result.system.coordinates[0, 0, 0]) == pytest.approx(2 ** (1 / 6), abs=1e-06)
    assert result.checkpoint.to_dict()['current_energy'] == pytest.approx(-0.5, abs=1e-10)

@pytest.mark.parametrize('kind', ['dtype', 'unit', 'nan', 'periodic', 'indices'])
def test_invalid_receptor_admission(kind):
    from betelgeuze_engine_v2.molecular import UnitCell
    receptor = system([[0, 0, 0]], name='rec')
    ligand = system([[2, 0, 0]], name='lig')
    base = base_parameters(ligand)
    if kind == 'dtype':
        receptor = replace(receptor, coordinates=receptor.coordinates.float())
    elif kind == 'unit':
        receptor = replace(receptor, coordinate_unit='nm')
    elif kind == 'nan':
        receptor = replace(receptor, coordinates=torch.full_like(receptor.coordinates, float('nan')))
    elif kind == 'periodic':
        receptor = replace(receptor, cell=UnitCell(vectors=torch.eye(3, dtype=torch.float64) * 10))
    else:
        receptor = replace(receptor, atoms=(replace(receptor.atoms[0], index=1),))
    with pytest.raises((ResearchError, ValueError, RuntimeError)):
        environment(receptor, ligand, base)

def test_fixed_model_rejects_ligand_only_solvation_composition():
    from tests.unit.test_cpu_refinement_v1_2_physics import near_linear
    from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEvaluator
    ligand, params, solvent, _ = near_linear()
    receptor = system([[4, 0, 0]], name='rec')
    env = environment(receptor, ligand, params.base_parameters)
    with pytest.raises(ResearchError, match='solvent'):
        FixedReceptorEvaluator(ExtendedEvaluator(params, solvent), env)
