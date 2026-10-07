"""Owning synthetic contracts for source-preserving pi harmonic angles."""
from dataclasses import replace
import math

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance,
    canonical_system_sha256, canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    HarmonicAngleParameter, HarmonicBondParameter, ReferenceParameterError,
)
from betelgeuze_engine_v2.physics.reference_forcefield import ReferencePhysicsApplicabilityError
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import (
    FourierParameters, NonbondedParameter, OrderedPeriodicImproperParameter,
)
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierInternalEvaluator, FourierCrossParameters, FourierEnvironment,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest, coordinates_hex
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_linear_angle_v1.parameters import (
    LinearAngleParameters, LinearHarmonicAngleParameter,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import (
    LinearAngleInternalEvaluator, LinearAngleEnvironment, LinearAngleFixedEvaluator,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.geometry import harmonic_linear_angle_energy
from betelgeuze_product.cpu_refinement_linear_angle_v1 import cartesian


def system(xyz):
    count = len(xyz)
    return AllAtomSystem(
        system_id="synthetic-linear-angle",
        atoms=tuple(Atom(index=i, name=f"C{i}", element="C", atomic_number=6,
                         residue_index=0, partial_charge_e=0.) for i in range(count)),
        bonds=tuple(Bond(index=n, atom_i=1, atom_j=i)
                    for n, i in enumerate(j for j in range(count) if j != 1)),
        residues=(Residue(index=0, name="LIG", chain_index=0, sequence_number=1,
                          atom_indices=tuple(range(count)), entity_type="non_polymer", hetero=True),),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([xyz], dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit", source_id="synthetic-linear",
                                      source_sha256="a"*64, parser_name="unit", parser_version="1"),
    )


def inputs(theta=math.pi, *, star=False):
    third = [-2., 0., 0.] if theta == math.pi else [2*math.cos(theta), 2*math.sin(theta), 0.]
    xyz = [[1., 0., 0.], [0., 0., 0.], third]
    if star:
        xyz.append([0., 0., 1.])
    ligand = system(xyz)
    base = FourierParameters(
        "synthetic-linear", "1", canonical_topology_sha256(ligand),
        tuple(NonbondedParameter(i, 1., 0., 0.) for i in range(len(xyz))),
        bonds=tuple(HarmonicBondParameter(1, i, 2. if i == 2 else 1., 100.)
                    for i in range(len(xyz)) if i != 1),
        angles=(() if not star else (HarmonicAngleParameter(0, 1, 3, math.pi/2, 20.),
                                    HarmonicAngleParameter(2, 1, 3, math.pi/2, 20.))),
        excluded_pairs=tuple((i, j) for i in range(len(xyz)) for j in range(i+1, len(xyz))),
        cutoff_angstrom=4., switch_start_angstrom=3.,
    )
    return ligand, LinearAngleParameters(base, (LinearHarmonicAngleParameter(0, 1, 2, math.pi, 100.),))


def neighbors(ligand):
    return build_compact_radius_graph(ligand.coordinates, RadiusGraphConfig(
        cutoff_angstrom=4., max_neighbors=8, max_atoms_per_cell=8))


def evaluate(ligand, model):
    return LinearAngleInternalEvaluator(model).evaluate(ligand, neighbors(ligand))


def test_exact_source_parameter_roundtrip_and_legacy_separation():
    _, model = inputs()
    assert LinearAngleParameters.from_dict(model.to_dict()) == model
    with pytest.raises(ReferenceParameterError):
        HarmonicAngleParameter(0, 1, 2, math.pi, 100.)
    with pytest.raises(ResearchError):
        replace(model.base_parameters, angles=model.linear_angles)
    with pytest.raises(ResearchError):
        FourierParameters.from_dict(model.to_dict())
    with pytest.raises(ResearchError):
        LinearAngleParameters.from_dict(model.base_parameters.to_dict())
    changed = replace(model, linear_angles=(replace(model.linear_angles[0],
                      force_constant_kcal_per_mol_radian2=101.),))
    assert changed.fingerprint_sha256 != model.fingerprint_sha256
    assert changed.linear_angles[0].equilibrium_radians == math.pi


@pytest.mark.parametrize("theta", [0., math.pi-1.e-15, math.pi+1.e-15, float('nan'), True])
def test_endpoint_parameter_requires_exact_pi(theta):
    with pytest.raises(ResearchError):
        LinearHarmonicAngleParameter(0, 1, 2, theta, 100.)


def test_combined_coverage_not_partial_base_and_no_duplicates():
    ligand, model = inputs(star=True)
    evaluate(ligand, model)
    with pytest.raises(ReferencePhysicsApplicabilityError, match="angle_parameters"):
        FourierInternalEvaluator(model.base_parameters).evaluate(ligand, neighbors(ligand))
    incomplete = replace(model, base_parameters=replace(model.base_parameters, angles=()))
    with pytest.raises(ReferencePhysicsApplicabilityError, match="angle_parameters"):
        evaluate(ligand, incomplete)
    with pytest.raises(ResearchError, match="duplicate"):
        replace(model, linear_angles=model.linear_angles*2)
    with pytest.raises(ResearchError, match="overlapping"):
        replace(model, base_parameters=replace(model.base_parameters,
                angles=model.base_parameters.angles+(HarmonicAngleParameter(0, 1, 2, 2., 100.),)))
    with pytest.raises(ResearchError):
        replace(model, linear_angles=())


@pytest.mark.parametrize("delta", [0., 1.e-14, 1.e-10, 1.e-7, .009, .011, .2, 1., 2.])
def test_closed_form_energy_and_cartesian_forces(delta):
    theta = math.pi-delta
    ligand, model = inputs(theta)
    out = evaluate(ligand, model)
    slope = -100.*delta
    a = torch.tensor([0., slope, 0.], dtype=torch.float64)
    c = torch.tensor([slope*math.sin(theta), -slope*math.cos(theta), 0.], dtype=torch.float64)/2
    expected = torch.stack((a, -a-c, c)).unsqueeze(0)
    assert out.term.energy.item() == pytest.approx(50*delta**2, abs=3.e-13, rel=2.e-12)
    torch.testing.assert_close(out.term.forces, expected, atol=4.e-12, rtol=2.e-12)
    if delta == 0:
        assert torch.count_nonzero(out.term.forces) == 0
        assert out.term.energy.item() == 0
    assert out.term.validated_for_composition is False


def test_rigid_motion_and_mixed_batch_gradgrad():
    a = torch.tensor([[1., 0., 0.], [1., 0., 0.]], dtype=torch.float64, requires_grad=True)
    b = torch.tensor([[-2., 0., 0.], [-2., .1, .02]], dtype=torch.float64, requires_grad=True)
    assert torch.autograd.gradcheck(lambda x,y: harmonic_linear_angle_energy(x,y,100.), (a,b))
    assert torch.autograd.gradgradcheck(lambda x,y: harmonic_linear_angle_energy(x,y,100.), (a,b))
    hessian = torch.autograd.functional.hessian(lambda x: harmonic_linear_angle_energy(x,b,100.).sum(), a)
    assert bool(torch.isfinite(hessian).all())
    assert hessian[0,1,0,1].item() == pytest.approx(100.)
    ligand, model = inputs(math.pi-1.e-6)
    original = evaluate(ligand, model)
    rotation = torch.tensor([[.36,-.48,.8],[.8,.6,0.],[-.48,.64,.6]], dtype=torch.float64)
    moved = ligand.with_coordinates(ligand.coordinates@rotation.T+.25, operation="synthetic-rigid")
    result = evaluate(moved, model)
    torch.testing.assert_close(result.term.forces, original.term.forces@rotation.T, atol=1.e-12, rtol=1.e-8)
    torch.testing.assert_close(result.term.forces.sum(1), torch.zeros((1,3),dtype=torch.float64), atol=1.e-12, rtol=0.)
    torque = torch.linalg.cross(moved.coordinates,result.term.forces,dim=-1).sum(1)
    torch.testing.assert_close(torque,torch.zeros_like(torque),atol=1.e-12,rtol=0.)


@pytest.mark.parametrize("other", [[0.,0.,0.], [1.,0.,0.], [float('nan'),0.,0.], [float('inf'),0.,0.]])
def test_degeneracy_guard(other):
    with pytest.raises(ReferencePhysicsApplicabilityError):
        harmonic_linear_angle_energy(torch.tensor([[1.,0.,0.]],dtype=torch.float64),
                                     torch.tensor([other],dtype=torch.float64),100.)


def test_undefined_improper_still_rejected_at_linear_angle():
    ligand, model = inputs(star=True)
    improper = OrderedPeriodicImproperParameter(0,1,2,3,2,0.,1.,star_center=1)
    model = replace(model,base_parameters=replace(model.base_parameters,periodic_impropers=(improper,)))
    with pytest.raises(ReferencePhysicsApplicabilityError,match="collinear"):
        evaluate(ligand,model)


def fixed_inputs(algorithm="sd"):
    ligand, model = inputs(math.pi-.05)
    receptor = system([[4.,3.,2.],[4.,2.,2.],[4.,1.,2.]])
    cross = FourierCrossParameters("synthetic-linear-cross","b"*64,
        canonical_system_sha256(receptor), canonical_topology_sha256(ligand), model.fingerprint_sha256,
        "synthetic-frame",tuple(NonbondedParameter(i,1.,0.,0.) for i in range(3)),
        7.,6.,.2,1.,0.,3,10.)
    env = LinearAngleEnvironment(receptor,cross)
    config = SolverConfig(algorithm=algorithm,max_objective_attempts=5,max_accepted_steps=2,
                          max_backtracks=2,max_restart_verifications=1,max_neighbors=8,max_atoms_per_cell=8)
    binding={"schema_id":cartesian.INPUT_SCHEMA,"candidate_id":"synthetic-linear",
             "prepared_protocol_sha256":"c"*64,"initial_coordinates_sha256":digest(coordinates_hex(ligand.coordinates))}
    return ligand,model,config,env,binding


@pytest.mark.parametrize("algorithm",["sd","lbfgs"])
def test_fixed_cartesian_resume_and_readonly_verify(tmp_path,monkeypatch,algorithm):
    torch.set_num_threads(1)
    ligand,model,config,env,binding=fixed_inputs(algorithm)
    run=tmp_path/algorithm
    paused=cartesian.minimize_cartesian(ligand,model,config,fixed_environment=env,run_dir=run,
                                        binding=binding,pause_after_objective_attempts=1)
    assert paused["status"]=="checkpointed"
    done=cartesian.minimize_cartesian(ligand,model,config,fixed_environment=env,run_dir=run,binding=binding,resume=True)
    assert done["schema_id"]==cartesian.RESULT_SCHEMA
    assert done["scientifically_validated"] is False
    assert done["work"]["actual_force_calls"]<=6
    def forbid(*args,**kwargs):
        raise AssertionError("verification must not evaluate forces")
    monkeypatch.setattr(LinearAngleFixedEvaluator,"evaluate",forbid)
    assert cartesian.verify_cartesian(ligand,model,config,fixed_environment=env,run_dir=run,binding=binding)==done
    assert cartesian.minimize_cartesian(ligand,model,config,fixed_environment=env,run_dir=run,binding=binding,resume=True)==done
    drift=cartesian.implementation_sources()
    drift["synthetic-drift"]="d"*64
    monkeypatch.setattr(cartesian,"implementation_sources",lambda:drift)
    with pytest.raises(ResearchError):
        cartesian.verify_cartesian(ligand,model,config,fixed_environment=env,run_dir=run,binding=binding)


def test_cross_and_old_cartesian_identity_separation(tmp_path):
    ligand,model,config,env,binding=fixed_inputs()
    with pytest.raises(ResearchError):
        FourierEnvironment(env.receptor,env.cross).validate_ligand(ligand,model)
    wrong=replace(env,cross=replace(env.cross,ligand_base_parameters_sha256=model.base_parameters.fingerprint_sha256))
    with pytest.raises(ResearchError):
        wrong.validate_ligand(ligand,model)
    from betelgeuze_product.cpu_refinement_fourier_v1 import cartesian as old
    with pytest.raises(ResearchError):
        old.minimize_cartesian(ligand,model,config,fixed_environment=env,run_dir=tmp_path/'wrong',binding=binding)


def test_cross_profile_journal_resume_rejected_before_force(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_refinement_fourier_v1 import cartesian as old
    from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import FourierFixedEvaluator
    torch.set_num_threads(1)
    ligand, model, config, env, binding = fixed_inputs()
    old_model = replace(model.base_parameters, angles=(HarmonicAngleParameter(0,1,2,2.9,100.),))
    old_env = FourierEnvironment(env.receptor,replace(env.cross,
                                ligand_base_parameters_sha256=old_model.fingerprint_sha256))
    old_binding = {**binding,"schema_id":old.INPUT_SCHEMA}
    new_run, old_run = tmp_path/'new', tmp_path/'old'
    cartesian.minimize_cartesian(ligand,model,config,fixed_environment=env,run_dir=new_run,
                                binding=binding,pause_after_objective_attempts=1)
    old.minimize_cartesian(ligand,old_model,config,fixed_environment=old_env,run_dir=old_run,
                          binding=old_binding,pause_after_objective_attempts=1)
    def forbid(*args,**kwargs):
        raise AssertionError("cross-profile journals must fail before force work")
    monkeypatch.setattr(LinearAngleFixedEvaluator,"evaluate",forbid)
    monkeypatch.setattr(FourierFixedEvaluator,"evaluate",forbid)
    with pytest.raises(ResearchError):
        cartesian.minimize_cartesian(ligand,model,config,fixed_environment=env,run_dir=old_run,
                                    binding=binding,resume=True)
    with pytest.raises(ResearchError):
        old.minimize_cartesian(ligand,old_model,config,fixed_environment=old_env,run_dir=new_run,
                              binding=old_binding,resume=True)


def test_unknown_reservation_never_reissued(tmp_path,monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
    torch.set_num_threads(1)
    ligand,model,config,env,binding=fixed_inputs()
    run=tmp_path/'interrupted'
    class Interrupted(BaseException):
        pass
    calls=[]
    def interrupt(*args,**kwargs):
        calls.append(True)
        raise Interrupted()
    monkeypatch.setattr(LinearAngleFixedEvaluator,"evaluate",interrupt)
    with pytest.raises(Interrupted):
        cartesian.minimize_cartesian(ligand,model,config,fixed_environment=env,run_dir=run,binding=binding)
    for action in (
        lambda:cartesian.minimize_cartesian(ligand,model,config,fixed_environment=env,
                                            run_dir=run,binding=binding,resume=True),
        lambda:cartesian.verify_cartesian(ligand,model,config,fixed_environment=env,run_dir=run,binding=binding),
    ):
        with pytest.raises(execution.PendingWorkError):
            action()
    assert calls==[True]
