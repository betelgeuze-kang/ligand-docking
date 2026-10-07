"""Public adapter tests with real admission objects and a synthetic objective."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
import torch

from betelgeuze_engine_v2.molecular import (AllAtomSystem, Atom, Bond, Chain, Residue,
    StructureProvenance, canonical_system_sha256, canonical_topology_sha256)
from betelgeuze_product.cpu_refinement_fourier_v1 import cartesian as base
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierCrossParameters, FourierEnvironment, FourierFixedEvaluator, FourierInternalEvaluator)
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import FourierParameters, NonbondedParameter
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex, digest
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_shape_v1 import cartesian
from betelgeuze_product.cpu_refinement_shape_v1.reference import ShapeContractError


def molecule(xyz, name):
    n = len(xyz)
    return AllAtomSystem(name,
        tuple(Atom(index=i, name='C'+str(i), element='C', atomic_number=6,
                   residue_index=0, partial_charge_e=0.) for i in range(n)),
        tuple(Bond(index=i, atom_i=i, atom_j=i+1) for i in range(n-1)),
        (Residue(index=0, name='LIG', chain_index=0, sequence_number=1,
                 atom_indices=tuple(range(n)), entity_type='non_polymer', hetero=True),),
        (Chain(index=0, chain_id='L', residue_indices=(0,)),),
        torch.tensor([xyz], dtype=torch.float64),
        StructureProvenance(source_format='unit', source_id=name, source_sha256='a'*64,
                            parser_name='synthetic', parser_version='1'))


def inputs():
    ligand = molecule([[-1., .1, 0.], [1., 0., .2]], 'ligand')
    receptor = molecule([[5., 0., 0.]], 'receptor')
    params = FourierParameters('synthetic-only', '1', canonical_topology_sha256(ligand),
        tuple(NonbondedParameter(i, 1., .5, 0.) for i in range(2)))
    cross = FourierCrossParameters('synthetic-only', 'b'*64, canonical_system_sha256(receptor),
        canonical_topology_sha256(ligand), params.fingerprint_sha256, 'mock-frame',
        (NonbondedParameter(0, 1., .5, 0.),), 6., 4., .2, 4., .15, 2, 0.)
    fixed = FourierEnvironment(receptor, cross)
    config = SolverConfig(max_objective_attempts=17, max_accepted_steps=4,
        max_restart_verifications=2, max_backtracks=3)
    binding = dict(schema_id=base.INPUT_SCHEMA, candidate_id='synthetic',
        prepared_protocol_sha256='c'*64,
        initial_coordinates_sha256=digest(coordinates_hex(ligand.coordinates)))
    return ligand, params, config, fixed, binding


@pytest.fixture(autouse=True)
def mock_only(monkeypatch):
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    def forbidden(*args):
        raise AssertionError('molecular evaluator forbidden')
    monkeypatch.setattr(FourierInternalEvaluator, 'evaluate', forbidden)
    monkeypatch.setattr(FourierEnvironment, 'evaluate_cross', forbidden)
    monkeypatch.setattr(execution, 'build_compact_radius_graph', lambda *args: object())
    def synthetic(self, system, neighbors):
        x = system.coordinates
        return SimpleNamespace(constraint_observations=(), term=SimpleNamespace(
            energy=(x*x).sum().reshape(1), forces=-2*x))
    monkeypatch.setattr(FourierFixedEvaluator, 'evaluate', synthetic)
    def parts(evaluated):
        e = float(evaluated.term.energy[0])
        return {'ligand_internal': e, 'cross_lennard_jones': 0., 'cross_screened_coulomb': 0., 'total': e}
    monkeypatch.setattr(execution, 'components_document', parts)
    yield
    torch.set_num_threads(old_threads)


def run(values, directory, strength, reference=None, **kwargs):
    lig, params, cfg, fixed, binding = values
    reference = cartesian.prepare_reference(lig, binding) if reference is None else reference
    return cartesian.minimize_shape(lig, params, cfg, fixed_environment=fixed, binding=binding,
        run_dir=directory, base_profile='fourier', reference=reference, strength=strength, **kwargs)


@pytest.mark.parametrize('strength', [0., 100., 1000.])
def test_public_admission_run_and_replay(tmp_path, strength, monkeypatch):
    values = inputs()
    result = run(values, tmp_path/'run', strength)
    lig, params, cfg, fixed, binding = values
    ref = cartesian.prepare_reference(lig, binding)
    monkeypatch.setattr(FourierFixedEvaluator, 'evaluate', lambda *args: pytest.fail('replay invoked'))
    checked = cartesian.verify_shape(lig, params, cfg, fixed_environment=fixed, binding=binding,
        run_dir=tmp_path/'run', base_profile='fourier', reference=ref, strength=strength)
    assert checked == result
    assert result['checkpoint']['schema_id'] == 'cpu_parent_shape_checkpoint/1.0.0'
    assert result['work']['optimizer_base_force_calls'] == result['work']['optimizer_force_calls']
    assert result['pose_selection_admitted'] is False
    assert result['internal_energy_gate_basis'] == 'unpenalized_ligand_internal_only'


def test_reference_source_and_coordinate_drift(tmp_path):
    values = inputs()
    lig, _, _, _, binding = values
    reference = cartesian.prepare_reference(lig, binding)
    for changed in [replace(reference, source_digest='d'*64),
                    replace(reference, parent_provenance='forged'),
                    replace(reference, coordinates=((-1., 0., 0.), (1., 0., .2)))]:
        with pytest.raises((ResearchError, ShapeContractError)):
            run(values, tmp_path/'never-created', 100., reference=changed)
        assert not (tmp_path/'never-created').exists()


def test_reference_retained_across_resume(tmp_path):
    values = inputs()
    reference = cartesian.prepare_reference(values[0], values[4])
    original = reference.to_json()
    run(values, tmp_path/'run', 100., reference=reference, pause_after_objective_attempts=2)
    resumed = run(values, tmp_path/'run', 100., reference=reference, resume=True)
    assert resumed['work']['restart_shape_calls'] == 1
    assert reference.to_json() == original


def test_disconnected_identity_rejected_before_work(tmp_path):
    values = list(inputs())
    ligand = values[0]
    # Standalone canonical system is permitted to represent fragments; this
    # shape experiment explicitly is not.
    disconnected = AllAtomSystem(ligand.system_id, ligand.atoms, (), ligand.residues,
        ligand.chains, ligand.coordinates, ligand.provenance)
    binding = dict(values[4], initial_coordinates_sha256=digest(coordinates_hex(disconnected.coordinates)))
    with pytest.raises(ShapeContractError):
        cartesian.prepare_reference(disconnected, binding)
