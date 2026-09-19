"""Independent cross-interaction math and actual shared-solver integration."""
from dataclasses import replace
import math

import pytest
import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, Atom, Chain, Residue, StructureProvenance, canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter, ReferenceForceFieldParameters, ReferenceApplicabilityDomain
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_product.cpu_refinement_v1_2.cross_interaction import CrossParameters, FixedReceptorEvaluator
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig, minimize_objective, minimize_extended
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError


def atom_system(name, coordinates, charges):
    n = len(coordinates)
    return AllAtomSystem(system_id=name,
        atoms=tuple(Atom(index=i, name=f'C{i}', element='C', atomic_number=6, residue_index=0,
                         partial_charge_e=float(q)) for i, q in enumerate(charges)), bonds=(),
        residues=(Residue(index=0, name='LIG', chain_index=0, sequence_number=1, atom_indices=tuple(range(n))),),
        chains=(Chain(index=0, chain_id='A', residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=StructureProvenance(source_format='unit', source_id=name, source_sha256='a'*64,
                                      parser_name='synthetic', parser_version='1'))


def fixture(r=3.0, charge=0.2, count=1):
    ligand = atom_system('ligand', [[r,0.,0.]], [charge])
    receptor = atom_system('receptor', [[0.,float(i)*3,0.] for i in range(count)], [-charge]*count)
    base = ReferenceForceFieldParameters(parameter_set_id='synthetic', parameter_set_version='1',
        topology_sha256=canonical_topology_sha256(ligand),
        atom_parameters=(AtomNonbondedParameter(0, 2., .3, charge),),
        cutoff_angstrom=8., switch_start_angstrom=6., applicability_domain=ReferenceApplicabilityDomain(max_atoms=256))
    parameters = ReferenceForceFieldV2Parameters(base)
    cross = CrossParameters(canonical_topology_sha256(receptor), base.fingerprint_sha256, 'b'*64, 'frame',
        tuple(AtomNonbondedParameter(i,2.,.3,-charge) for i in range(count)),8.,6.,.1,4.,.15,2,())
    return ligand, receptor, parameters, cross


def independent_energy(r, charge=.2):
    switch=1.
    if r>=8:
        return 0.
    if r>6:
        t=(r-6)/2
        switch=1-10*t**3+15*t**4-6*t**5
    return (4*.3*((2/r)**12-(2/r)**6) -332.063713299*charge**2*math.exp(-.15*r)/(4*r))*switch


@pytest.mark.parametrize('r',[1.7,2.,2.3,3.,5.,6.,6.2,7.,7.9,8.,9.])
def test_independent_energy_and_finite_difference_force(r):
    ligand,receptor,p,c = fixture(r)
    e=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame')
    terms, force, pairs=e.cross_terms(ligand)
    assert sum(v.item() for v in terms.values())==pytest.approx(independent_energy(r),abs=1e-12,rel=1e-12)
    h=1e-5
    expected=-(independent_energy(r+h)-independent_energy(r-h))/(2*h)
    assert force[0,0,0].item()==pytest.approx(expected,abs=1e-6,rel=1e-7)
    assert pairs==int(r<8)
    assert force[0,0,1:].tolist()==[0.,0.]


@pytest.mark.parametrize('block',[1,2,3,8])
def test_blocks_do_not_omit_or_double_count_pairs(block):
    ligand,receptor,p,c=fixture(count=5)
    c=replace(c,receptor_block_size=block)
    terms,force,pairs=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame').cross_terms(ligand)
    expected=sum(independent_energy(math.hypot(3,i*3)) for i in range(5))
    assert sum(v.item() for v in terms.values())==pytest.approx(expected,abs=1e-12)
    assert pairs==3
    assert torch.isfinite(force).all()


def test_excluded_overlap_is_not_divided_by_zero_and_active_overlap_rejected():
    ligand,receptor,p,c=fixture(r=0.)
    from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import ReferencePhysicsApplicabilityError
    with pytest.raises(ReferencePhysicsApplicabilityError):
        FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame').cross_terms(ligand)
    terms,f,n=FixedReceptorEvaluator(receptor,p,replace(c,excluded_pairs=((0,0),)),coordinate_frame_id='frame').cross_terms(ligand)
    assert sum(v.item() for v in terms.values())==0 and n==0
    assert torch.equal(f,torch.zeros_like(f))


@pytest.mark.parametrize('change',['frame','topology','parameter','charges','mutated_receptor','bad_exclusion','float32'])
def test_invalid_cross_binding_rejected(change):
    ligand,receptor,p,c=fixture()
    frame='wrong' if change=='frame' else 'frame'
    if change=='topology':
        c=replace(c,receptor_topology_sha256='c'*64)
    if change=='parameter':
        c=replace(c,ligand_parameters_sha256='c'*64)
    if change=='charges':
        c=replace(c,receptor_atoms=(replace(c.receptor_atoms[0],charge_e=.99),))
    if change=='bad_exclusion':
        c=replace(c,excluded_pairs=((1,0),))
    if change=='float32':
        ligand=ligand.with_coordinates(ligand.coordinates.float(),operation='changed')
    with pytest.raises((ResearchError,ValueError)):
        e=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id=frame)
        if change=='mutated_receptor':
            receptor.coordinates[0,0,0]=1.
        e.cross_terms(ligand)


def test_joint_translation_preserves_energy_ligand_only_translation_does_not():
    ligand,receptor,p,c=fixture()
    terms,f,_=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame').cross_terms(ligand)
    moved=ligand.with_coordinates(ligand.coordinates+2.,operation='translate')
    fixed=receptor.with_coordinates(receptor.coordinates+2.,operation='translate')
    t,g,_=FixedReceptorEvaluator(fixed,p,c,coordinate_frame_id='frame').cross_terms(moved)
    torch.testing.assert_close(f,g,rtol=0,atol=0)
    assert sum(v.item() for v in terms.values())==sum(v.item() for v in t.values())
    t,_,_=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame').cross_terms(moved)
    assert sum(v.item() for v in terms.values())!=sum(v.item() for v in t.values())


def test_shared_solver_moves_toward_fixed_receptor_and_restart_is_exact():
    ligand,receptor,p,c=fixture()
    original=receptor.coordinates.clone()
    evaluator=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame')
    cfg=SolverConfig(ReferenceMinimizationConfig(max_iterations=4))
    full=minimize_objective(ligand,evaluator,cfg)
    paused=minimize_objective(ligand,evaluator,cfg,pause_after_accepted_iterations=1)
    resumed=minimize_objective(ligand,evaluator,cfg,checkpoint=paused.checkpoint)
    assert full.checkpoint.to_dict()==resumed.checkpoint.to_dict()
    assert full.system.coordinates[0,0,0]<ligand.coordinates[0,0,0]
    assert torch.equal(receptor.coordinates,original)
    assert full.checkpoint.to_dict()['current_energy']<full.checkpoint.to_dict()['initial_energy']
    old=minimize_extended(ligand,p,cfg)
    with pytest.raises(ResearchError,match='evaluator'):
        minimize_objective(ligand,evaluator,cfg,checkpoint=old.checkpoint)
    moved=receptor.with_coordinates(receptor.coordinates+.1,operation='changed')
    with pytest.raises(ResearchError,match='evaluator'):
        minimize_objective(ligand,FixedReceptorEvaluator(moved,p,c,coordinate_frame_id='frame'),cfg,checkpoint=paused.checkpoint)


def test_internal_plus_cross_components_sum_exactly():
    ligand,receptor,p,c=fixture()
    e=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame')
    graph=build_compact_radius_graph(ligand.coordinates,RadiusGraphConfig(cutoff_angstrom=8.,max_neighbors=8,max_atoms_per_cell=8))
    value=e.evaluate(ligand,graph)
    torch.testing.assert_close(sum(value.component_energies.values()),value.term.energy,rtol=0,atol=0)
    assert not value.term.validated_for_composition


def test_complete_parameter_roundtrip_and_noncanonical_input():
    _,_,_,c=fixture()
    assert CrossParameters.from_dict(c.to_dict())==c
    doc=c.to_dict()
    doc['receptor_atoms'][0]['atom_index']=False
    with pytest.raises(ResearchError):
        CrossParameters.from_dict(doc)


def test_receptor_larger_than_ligand_solver_limit_is_not_cropped():
    ligand,receptor,p,c=fixture(count=300)
    c=replace(c,receptor_block_size=64)
    e=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame')
    assert e.receptor.atom_count==300
    terms,force,pairs=e.cross_terms(ligand)
    assert pairs==3
    assert sum(v.item() for v in terms.values())==pytest.approx(sum(independent_energy(math.hypot(3,i*3)) for i in range(300)))
    assert torch.isfinite(force).all()


def test_rigid_rotation_covariance():
    ligand,receptor,p,c=fixture(count=3)
    e=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame')
    terms,f,_=e.cross_terms(ligand)
    rotation=torch.tensor([[.36,-.48,.8],[.8,.6,0.],[-.48,.64,.6]],dtype=torch.float64)
    fixed=receptor.with_coordinates(receptor.coordinates@rotation.T,operation='rotate')
    moving=ligand.with_coordinates(ligand.coordinates@rotation.T,operation='rotate')
    t,g,_=FixedReceptorEvaluator(fixed,p,c,coordinate_frame_id='frame').cross_terms(moving)
    assert sum(v.item() for v in t.values())==pytest.approx(sum(v.item() for v in terms.values()),abs=1e-12)
    torch.testing.assert_close(g,f@rotation.T,atol=1e-12,rtol=1e-12)


@pytest.mark.parametrize('change',['cutoff','switch','distance','dielectric','block','duplicates','exclusion_type'])
def test_cross_configuration_rejects_ambiguous_or_unbounded_inputs(change):
    _,_,_,c=fixture()
    kwargs={'cutoff':{'cutoff_angstrom':6.},'switch':{'switch_start_angstrom':0.},
            'distance':{'minimum_distance_angstrom':0.},'dielectric':{'dielectric':0.},
            'block':{'receptor_block_size':True},'duplicates':{'excluded_pairs':((0,0),(0,0))},
            'exclusion_type':{'excluded_pairs':((False,0),)}}[change]
    with pytest.raises(ResearchError):
        replace(c,**kwargs)


def test_same_objective_rejects_changed_cross_parameters_on_restart():
    ligand,receptor,p,c=fixture()
    cfg=SolverConfig(ReferenceMinimizationConfig(max_iterations=3))
    original=FixedReceptorEvaluator(receptor,p,c,coordinate_frame_id='frame')
    paused=minimize_objective(ligand,original,cfg,pause_after_accepted_iterations=1)
    changed=FixedReceptorEvaluator(receptor,p,replace(c,dielectric=5.),coordinate_frame_id='frame')
    with pytest.raises(ResearchError,match='evaluator'):
        minimize_objective(ligand,changed,cfg,checkpoint=paused.checkpoint)
