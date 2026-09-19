"""D3 physics: independent scalar energy/force, switching, pair coverage, identity."""
from __future__ import annotations
from dataclasses import replace
import math
import pytest
import torch
from betelgeuze_engine_v2.molecular import AllAtomSystem, Atom, Chain, Residue, StructureProvenance, UnitCell, canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter, ReferenceForceFieldParameters, ReferenceApplicabilityDomain
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import ReferencePhysicsApplicabilityError
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, CrossPairScaling, FixedReceptorEnvironment, FIXED_EVALUATOR_ID
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig, minimize_extended, require_checkpoint
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig

def atom_system(name, xyz, charges):
    return AllAtomSystem(system_id=name, atoms=tuple((Atom(index=i, name=f'C{i}', element='C', atomic_number=6, residue_index=0, partial_charge_e=float(q)) for i, q in enumerate(charges))), bonds=(), residues=(Residue(index=0, name='SYN', chain_index=0, sequence_number=1, atom_indices=tuple(range(len(charges))), entity_type='non-polymer', hetero=True),), chains=(Chain(index=0, chain_id='A', residue_indices=(0,)),), coordinates=torch.tensor([xyz], dtype=torch.float64), provenance=StructureProvenance(source_format='unit', source_id=name, source_sha256='f' * 64, parser_name='synthetic-d3', parser_version='1'))

def pair_fixture(distance=3.0, charge=0.2, receptor_charge=-0.3):
    ligand = atom_system('ligand', [[distance, 0.0, 0.0]], [charge])
    receptor = atom_system('receptor', [[0.0, 0.0, 0.0]], [receptor_charge])
    base = ReferenceForceFieldParameters(parameter_set_id='synthetic-single', parameter_set_version='1', topology_sha256=canonical_topology_sha256(ligand), atom_parameters=(AtomNonbondedParameter(0, 2.0, 0.4, charge),), cutoff_angstrom=6.0, switch_start_angstrom=4.0, applicability_domain=ReferenceApplicabilityDomain(max_atoms=256))
    cross = CrossParameters('synthetic-cross', '1', 'e' * 64, canonical_system_sha256(receptor), canonical_topology_sha256(ligand), base.fingerprint_sha256, 'synthetic-receptor-frame', (AtomNonbondedParameter(0, 2.4, 0.9, receptor_charge),), (), 6.0, 4.0, 4.0, 0.1, 0.2)
    return (ligand, ReferenceForceFieldV2Parameters(base), FixedReceptorEnvironment(receptor, cross))

def scalar_pair(r, a, b, p, lj_scale=1.0, el_scale=1.0):
    if r >= p.cutoff_angstrom:
        return (0.0, 0.0)
    sigma = (a.sigma_angstrom + b.sigma_angstrom) / 2
    epsilon = math.sqrt(a.epsilon_kcal_per_mol * b.epsilon_kcal_per_mol)
    lj = 4 * epsilon * ((sigma / r) ** 12 - (sigma / r) ** 6) * lj_scale
    el = 332.063713299 * a.charge_e * b.charge_e * math.exp(-p.screening_kappa_per_angstrom * r) / (p.dielectric * r) * el_scale
    if r > p.switch_start_angstrom:
        t = (r - p.switch_start_angstrom) / (p.cutoff_angstrom - p.switch_start_angstrom)
        switch = 1 - 10 * t ** 3 + 15 * t ** 4 - 6 * t ** 5
        lj, el = (lj * switch, el * switch)
    return (lj, el)

@pytest.mark.parametrize('distance', [0.3, 1.0, 2.2, 2.6, 3.0, 3.999, 4.0, 4.5, 5.99, 6.0, 8.0])
@pytest.mark.parametrize('screening', [0.0, 0.1, 1.0])
def test_independent_pair_energy_and_radial_force(distance, screening):
    ligand, params, env = pair_fixture(distance)
    env = replace(env, parameters=replace(env.parameters, screening_kappa_per_angstrom=screening))
    lj, el, force, count = env.evaluate_cross(ligand, params.base_parameters)
    expected = scalar_pair(distance, params.base_parameters.atom_parameters[0], env.parameters.receptor_atom_parameters[0], env.parameters)
    assert lj.item() == pytest.approx(expected[0], rel=1e-11, abs=1e-11)
    assert el.item() == pytest.approx(expected[1], rel=1e-11, abs=1e-11)
    h = 1e-06 * min(distance, 1.0)
    a, b = (params.base_parameters.atom_parameters[0], env.parameters.receptor_atom_parameters[0])
    expected_force = -(sum(scalar_pair(distance + h, a, b, env.parameters)) - sum(scalar_pair(distance - h, a, b, env.parameters))) / (2 * h)
    assert force[0, 0, 0].item() == pytest.approx(expected_force, rel=2e-07, abs=2e-07)
    assert torch.equal(force[0, 0, 1:], torch.zeros(2, dtype=torch.float64))
    assert count == int(distance < env.parameters.cutoff_angstrom)

def test_lj_minimum_and_coulomb_closed_forms_without_switch():
    ligand, params, env = pair_fixture(2.2 * 2 ** (1 / 6), charge=0.0, receptor_charge=0.0)
    lj, el, force, _ = env.evaluate_cross(ligand, params.base_parameters)
    assert lj.item() == pytest.approx(-0.6, abs=1e-14)
    assert el.item() == 0.0
    assert force.abs().max().item() < 1e-13

@pytest.mark.parametrize('exception', [(0.0, 0.0), (0.25, 0.5), (1.0, 0.0)])
def test_scaling_and_excluded_zero_distance(exception):
    ligand, params, env = pair_fixture(0.0 if exception == (0.0, 0.0) else 3.0)
    env = replace(env, parameters=replace(env.parameters, pair_scalings=(CrossPairScaling(0, 0, *exception),)))
    lj, el, force, count = env.evaluate_cross(ligand, params.base_parameters)
    if exception == (0.0, 0.0):
        assert lj.item() == el.item() == force.abs().sum().item() == count == 0
    else:
        expected = scalar_pair(3.0, params.base_parameters.atom_parameters[0], env.parameters.receptor_atom_parameters[0], env.parameters, *exception)
        assert (lj.item(), el.item()) == pytest.approx(expected)

def test_block_boundaries_match_independent_all_pairs_and_moved_coordinates():
    gen = torch.Generator().manual_seed(724)
    lx = torch.rand((33, 3), generator=gen, dtype=torch.float64) * 2 + 4
    rx = torch.rand((129, 3), generator=gen, dtype=torch.float64) * 2
    ligand = atom_system('many-ligand', lx.tolist(), [0.1] * 33)
    r = atom_system('many-receptor', rx.tolist(), [-0.1] * 129)
    base = ReferenceForceFieldParameters(parameter_set_id='many', parameter_set_version='1', topology_sha256=canonical_topology_sha256(ligand), atom_parameters=tuple((AtomNonbondedParameter(i, 1.0, 0.2, 0.1) for i in range(33))))
    p = CrossParameters('many-cross', '1', 'a' * 64, canonical_system_sha256(r), canonical_topology_sha256(ligand), base.fingerprint_sha256, 'frame', tuple((AtomNonbondedParameter(i, 1.5, 0.3, -0.1) for i in range(129))), (CrossPairScaling(0, 0, 0.0, 0.0), CrossPairScaling(32, 128, 0.5, 0.25)), 8.0, 6.0, 10.0, 0.2, 0.1)
    env = FixedReceptorEnvironment(r, p)
    for offset in (0.0, 0.2):
        state = ligand.with_coordinates(ligand.coordinates + offset, operation='moved')
        lj, el, _, count = env.evaluate_cross(state, base)
        expected_lj = expected_el = 0.0
        expected_count = 0
        ex = {(x.ligand_index, x.receptor_index): (x.lj_scale, x.electrostatic_scale) for x in p.pair_scalings}
        for i, x in enumerate(state.coordinates[0].tolist()):
            for j, y in enumerate(r.coordinates[0].tolist()):
                radius = math.dist(x, y)
                scales = ex.get((i, j), (1.0, 1.0))
                a, b = scalar_pair(radius, base.atom_parameters[i], p.receptor_atom_parameters[j], p, *scales)
                expected_lj += a
                expected_el += b
                expected_count += int(radius < p.cutoff_angstrom and any(scales))
        assert lj.item() == pytest.approx(expected_lj, rel=1e-12, abs=1e-12)
        assert el.item() == pytest.approx(expected_el, rel=1e-12, abs=1e-12)
        assert count == expected_count

def test_rigid_transform_and_fixed_receptor_integrity():
    ligand, params, env = pair_fixture()
    _, _, old, _ = env.evaluate_cross(ligand, params.base_parameters)
    rotation = torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=torch.float64)
    transformed_l = ligand.with_coordinates(ligand.coordinates @ rotation.T + 5, operation='rigid')
    receptor = env.receptor.with_coordinates(env.receptor.coordinates @ rotation.T + 5, operation='rigid')
    newenv = FixedReceptorEnvironment(receptor, replace(env.parameters, receptor_system_sha256=canonical_system_sha256(receptor)))
    _, _, force, _ = newenv.evaluate_cross(transformed_l, params.base_parameters)
    torch.testing.assert_close(force, old @ rotation.T, atol=1e-12, rtol=1e-12)
    env.receptor.coordinates[0, 0, 0] += 0.1
    with pytest.raises(ResearchError, match='identity'):
        env.evaluate_cross(ligand, params.base_parameters)

@pytest.mark.parametrize('change', ['missing_atom', 'duplicate', 'bounds', 'switch', 'charge', 'sigma', 'nonfinite', 'unknown'])
def test_malformed_parameter_documents_rejected(change):
    _, _, env = pair_fixture()
    d = env.parameters.to_dict()
    if change == 'missing_atom':
        d['receptor_atom_parameters'] = []
    elif change == 'duplicate':
        d['pair_scalings'] = [CrossPairScaling(0, 0, 0.0, 0.0).to_dict()] * 2
    elif change == 'bounds':
        d['pair_scalings'] = [{'ligand_index': True, 'receptor_index': 0, 'lj_scale': 1.0, 'electrostatic_scale': 1.0}]
    elif change == 'switch':
        d['switch_start_angstrom'] = d['cutoff_angstrom']
    elif change == 'charge':
        d['receptor_atom_parameters'][0]['charge_e'] = 1e+100
    elif change == 'sigma':
        d['receptor_atom_parameters'][0]['sigma_angstrom'] = 0.0
    elif change == 'nonfinite':
        d['dielectric'] = float('nan')
    else:
        d['unknown'] = True
    with pytest.raises(ValueError):
        CrossParameters.from_dict(d)

def test_parameter_roundtrip_and_explicit_crosswiring_rejection():
    ligand, params, env = pair_fixture()
    assert CrossParameters.from_dict(env.parameters.to_dict()) == env.parameters
    bad = replace(env, parameters=replace(env.parameters, ligand_parameter_fingerprint_sha256='0' * 64))
    with pytest.raises(ResearchError, match='identity'):
        bad.evaluate_cross(ligand, params.base_parameters)
    with pytest.raises(ResearchError, match='charge'):
        FixedReceptorEnvironment(env.receptor, replace(env.parameters, receptor_atom_parameters=(AtomNonbondedParameter(0, 2.4, 0.9, 0.8),)))

@pytest.mark.parametrize('distance', [0.0, 0.199])
def test_overlap_raises_applicability_not_clamped_energy(distance):
    ligand, p, e = pair_fixture(distance)
    with pytest.raises(ReferencePhysicsApplicabilityError):
        e.evaluate_cross(ligand, p.base_parameters)

def test_nonperiodic_single_model_contract():
    ligand, p, e = pair_fixture()
    ligand = replace(ligand, cell=UnitCell(vectors=torch.eye(3, dtype=torch.float64) * 10))
    with pytest.raises(ResearchError):
        e.evaluate_cross(ligand, p.base_parameters)

def test_total_energy_moves_ligand_toward_fixed_receptor_and_restart():
    ligand, p, e = pair_fixture(3.0, charge=0.0, receptor_charge=0.0)
    config = SolverConfig(ReferenceMinimizationConfig(max_iterations=20, initial_step_size_angstrom2_mol_per_kcal=0.05))
    before = e.receptor.coordinates.clone()
    full = minimize_extended(ligand, p, config, fixed_environment=e)
    paused = minimize_extended(ligand, p, config, fixed_environment=e, pause_after_accepted_iterations=2)
    resumed = minimize_extended(ligand, p, config, fixed_environment=e, checkpoint=paused.checkpoint)
    assert full.checkpoint.to_dict() == resumed.checkpoint.to_dict()
    d = full.checkpoint.to_dict()
    assert d['evaluator']['evaluator_id'] == FIXED_EVALUATOR_ID
    assert d['current_energy'] < d['initial_energy']
    assert full.system.coordinates[0, 0, 0] < ligand.coordinates[0, 0, 0]
    assert torch.equal(e.receptor.coordinates, before)
    assert d['current_objective_components']['ligand_reference'] == 0.0
    dry = minimize_extended(ligand, p, config)
    assert torch.equal(dry.system.coordinates, ligand.coordinates)
    with pytest.raises(ResearchError, match='identity'):
        minimize_extended(ligand, p, config, checkpoint=paused.checkpoint)

def test_changed_environment_checkpoint_and_component_forgery_rejected():
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
    ligand, p, e = pair_fixture()
    config = SolverConfig(ReferenceMinimizationConfig(max_iterations=3))
    pause = minimize_extended(ligand, p, config, fixed_environment=e, pause_after_accepted_iterations=1)
    e2 = replace(e, parameters=replace(e.parameters, dielectric=5.0))
    with pytest.raises(ResearchError, match='identity'):
        minimize_extended(ligand, p, config, fixed_environment=e2, checkpoint=pause.checkpoint)
    d = pause.checkpoint.to_dict()
    d['current_objective_components']['cross_lennard_jones'] += 1.0
    d['checkpoint_sha256'] = digest({k: v for k, v in d.items() if k != 'checkpoint_sha256'})
    with pytest.raises(ResearchError, match='sum'):
        require_checkpoint(d)

def test_receptor_larger_than_ligand_limit_is_not_truncated():
    ligand, params, original = pair_fixture(3.0)
    xyz = [[100.0 + i, 0.0, 0.0] for i in range(299)] + [[0.0, 0.0, 0.0]]
    receptor = atom_system('large-fixed-receptor', xyz, [0.0] * 299 + [-0.3])
    cross = replace(original.parameters, receptor_system_sha256=canonical_system_sha256(receptor), receptor_atom_parameters=tuple([AtomNonbondedParameter(i, 2.4, 0.0, 0.0) for i in range(299)] + [AtomNonbondedParameter(299, 2.4, 0.9, -0.3)]))
    large = FixedReceptorEnvironment(receptor, cross)
    expected = original.evaluate_cross(ligand, params.base_parameters)
    observed = large.evaluate_cross(ligand, params.base_parameters)
    for x, y in zip(expected[:3], observed[:3], strict=True):
        torch.testing.assert_close(x, y, rtol=1e-13, atol=1e-13)
    assert observed[3] == 1

def test_combined_energy_gradient_in_general_coordinates():
    ligand, params, env = pair_fixture()
    ligand = ligand.with_coordinates(torch.tensor([[[2.3, 1.7, -0.9]]], dtype=torch.float64), operation='off-axis')
    _, _, force, _ = env.evaluate_cross(ligand, params.base_parameters)
    for axis in range(3):
        energies = []
        for shift in (-1e-06, 1e-06):
            xyz = ligand.coordinates.clone()
            xyz[0, 0, axis] += shift
            state = ligand.with_coordinates(xyz, operation='fd')
            lj, el, _, _ = env.evaluate_cross(state, params.base_parameters)
            energies.append((lj + el).item())
        assert force[0, 0, axis].item() == pytest.approx(-(energies[1] - energies[0]) / 2e-06, abs=1e-08)

def test_checkpoint_replay_rejects_selfconsistent_but_wrong_component_partition():
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
    ligand, params, env = pair_fixture()
    config = SolverConfig(ReferenceMinimizationConfig(max_iterations=4))
    run = minimize_extended(ligand, params, config, fixed_environment=env, pause_after_accepted_iterations=1)
    doc = run.checkpoint.to_dict()
    c = doc['current_objective_components']
    c['cross_lennard_jones'], c['cross_screened_coulomb'] = (c['cross_screened_coulomb'], c['cross_lennard_jones'])
    doc['checkpoint_sha256'] = digest({k: v for k, v in doc.items() if k != 'checkpoint_sha256'})
    with pytest.raises(ResearchError, match='components'):
        minimize_extended(ligand, params, config, fixed_environment=env, checkpoint=doc)

def test_single_pair_converges_to_analytic_lj_minimum():
    ligand, params, env = pair_fixture(3.0, charge=0.0, receptor_charge=0.0)
    config = SolverConfig(ReferenceMinimizationConfig(max_iterations=100, initial_step_size_angstrom2_mol_per_kcal=0.05, force_tolerance_kcal_per_mol_angstrom=1e-8))
    run = minimize_extended(ligand, params, config, fixed_environment=env)
    assert run.converged
    assert run.system.coordinates[0, 0, 0].item() == pytest.approx(2.2 * 2 ** (1 / 6), abs=2e-06)
    assert run.checkpoint.to_dict()['current_energy'] == pytest.approx(-0.6, abs=1e-10)
