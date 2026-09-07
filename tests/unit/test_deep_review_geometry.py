"""Synthetic geometry and chemistry-wiring tests, not docking accuracy evidence."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
import torch

from betelgeuze_engine.biodiscovery import pose, scoring, screening
from betelgeuze_engine.biodiscovery.coarse_receptor import prepare_receptor_proxy, PROXY_SCHEMA
from tests.unit.test_biodiscovery_screening import MINI_PDB


def receptor():
    return np.array([[0.,0.,0.],[3.,0.,0.],[1.,3.,0.],[1.,1.,4.],[4.,4.,1.]])


@pytest.mark.parametrize('seed', range(16))
@pytest.mark.parametrize('kind', ['noncollinear','collinear'])
def test_proxy_and_coarse_score_preserve_rigid_transform(seed,kind):
    rng=np.random.default_rng(seed)
    q,_=np.linalg.qr(rng.normal(size=(3,3)))
    if np.linalg.det(q)<0.: q[:,0]*=-1.
    shift=rng.uniform(-20,20,3)
    ca=receptor() if kind=='noncollinear' else np.array([[i*3.8,0.,0.] for i in range(6)])
    ligand=np.array([[2.,5.,6.],[4.,6.,7.]])
    beads=pose.virtual_protein_coords(ca)
    actual=pose.virtual_protein_coords(ca@q+shift)
    np.testing.assert_allclose(actual,beads@q+shift,rtol=0.,atol=3e-6)
    a=pose.coarse_pose_score(beads,ligand)['score']
    b=pose.coarse_pose_score(actual,ligand@q+shift)['score']
    assert a==pytest.approx(b,rel=3e-6,abs=3e-6)


@pytest.mark.parametrize('coords',[np.zeros((1,3)),np.zeros((4,3)),np.zeros((0,3)),
                                  np.full((4,3),np.nan),np.full((4,3),1j)])
def test_proxy_rejects_undefined_or_invalid_frames(coords):
    with pytest.raises(ValueError): pose.virtual_protein_coords(coords)


def large_receptor():
    return np.array([[3.8*i,0.3*(i%3),0.2*(i%2)] for i in range(127)])


def pdb(ca):
    return ''.join(f'ATOM  {i:5d}  CA  ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n'
                   for i,(x,y,z) in enumerate(ca,1))


def test_fixed_pocket_buffer_limits_work_without_truncating_to_cap():
    ca=large_receptor()
    beads,center,meta=prepare_receptor_proxy(ca,list(range(10)),ligand_atom_count=6,buffer_a=8.,explicit_pocket=True)
    assert meta['scoring_residue_indices']==list(range(12))
    assert meta['scoring_residue_count']==12 and meta['input_residue_count']==127
    assert len(beads)==48 and meta['dense_diagnostic_cap']==512
    np.testing.assert_allclose(center,ca[:10].mean(axis=0),atol=1e-6)
    assert meta['physical_subsystem_validated'] is False
    with pytest.raises(ValueError,match='dense_diagnostic_blocked'):
        prepare_receptor_proxy(ca,list(range(127)),ligand_atom_count=6,buffer_a=8.,explicit_pocket=True)


def test_large_structure_small_explicit_pocket_runs_actual_screening():
    result=screening.TierBetaScreening(device='cpu',pose_count=1,top_k=1,stability_steps=0).screen(
        protein_input=pdb(large_receptor()),ligand_input='c1ccccc1',pocket_residue_indices=list(range(10)))
    assert result.ok is True, result.blocked_reason
    assert result.protein_residue_count==127
    assert result.pocket_residue_count==10
    meta=result.diagnostics['receptor_proxy']
    assert meta['scoring_residue_count']==12
    assert meta['schema_version']==PROXY_SCHEMA
    assert result.pose_scores[0]['ranking_metric']['receptor_representation']==PROXY_SCHEMA
    assert result.claim_metadata['claim_safe'] is False
    pocket_stage=next(s for s in result.stage_records if s['stage_id']=='pocket_resolution')
    assert pocket_stage['diagnostics']['receptor_proxy']==meta


def test_cap_is_enforced_before_expensive_candidate_scoring(monkeypatch):
    def forbidden(*args,**kwargs): pytest.fail('oversized domain entered search')
    monkeypatch.setattr(screening,'_pose_search_candidates',forbidden)
    result=screening.TierBetaScreening(device='cpu',pose_count=1,top_k=1,stability_steps=0).screen(
        protein_input=pdb(large_receptor()),ligand_input='c1ccccc1')
    assert result.ok is False and 'dense_diagnostic_blocked' in result.blocked_reason


@pytest.mark.parametrize('indices',[[],[True],[1.5],['1'],[0,0],[-1],[500]])
def test_invalid_explicit_pocket_is_not_silently_replaced(indices):
    result=screening.TierBetaScreening(device='cpu',pose_count=1,top_k=1,stability_steps=0).screen(
        protein_input=MINI_PDB,ligand_input='c1ccccc1',pocket_residue_indices=indices)
    assert not result.ok
    assert 'pocket' in result.blocked_reason


def test_wrapper_forwards_elements_and_partial_charges_to_real_calculation():
    p=np.array([[0.,0.,0.],[4.,0.,0.]])
    l=np.array([[2.,2.,0.],[3.,3.,0.]])
    kwargs=dict(protein_elements=['C','N'],ligand_elements=['O','C'],
                protein_charges=np.array([.2,-.2]),ligand_charges=np.array([-.3,.3]))
    direct=scoring.mm_gbsa_binding_energy(p,l,**kwargs)
    actual=scoring.mm_gbsa_binding_score(p,l,**kwargs)
    assert actual['ligand_element_fallback_used'] is False
    assert actual['protein_element_fallback_used'] is False
    assert actual['partial_charges_supplied'] is True
    assert actual['e_gb']==pytest.approx(direct['e_gb'])
    assert actual['e_vdw']==pytest.approx(direct['e_vdw'])
    assert actual['claim_safe'] is False


@pytest.mark.parametrize('kwargs', [
    dict(ligand_elements=['O']),dict(ligand_elements=['O','']),
    dict(ligand_charges=np.array([.1,-.1])),
    dict(protein_charges=np.array([0.,0.]),ligand_charges=np.array([np.nan,0.])),
    dict(protein_charges=np.array([0.,0.]),ligand_charges=np.array([True,False])),
])
def test_bad_chemistry_is_blocked_not_silently_fallback(kwargs):
    out=scoring.mm_gbsa_binding_score(np.zeros((2,3)),np.ones((2,3)),**kwargs)
    assert out['status']=='blocked_chemistry_input_or_proxy_evaluation'
    assert out['claim_safe'] is False and out['binding_energy_kcal_mol']==float('inf')


def test_actual_screening_passes_prepared_ligand_elements_but_not_formal_as_partial_charges(monkeypatch):
    seen=[]; original=screening._mm_gbsa_binding_score
    def capture(*args,**kwargs):
        out=original(*args,**kwargs); seen.append((kwargs,out)); return out
    monkeypatch.setattr(screening,'_mm_gbsa_binding_score',capture)
    result=screening.TierBetaScreening(device='cpu',pose_count=1,top_k=1,stability_steps=0).screen(
        protein_input=MINI_PDB,ligand_input='CCO')
    assert result.ok, result.blocked_reason
    assert seen
    for inputs,out in seen:
        assert inputs['ligand_elements']==['C','C','O']
        assert out['ligand_element_fallback_used'] is False
        assert out['protein_element_fallback_used'] is True
        assert out['partial_charges_supplied'] is False
        assert out['charge_source']=='unavailable_no_formal_charge_substitution'


@pytest.mark.parametrize('shift', [[50.,0.,0.],[-50.,70.,-60.]])
def test_uniform_translation_no_longer_causes_fixed_box_failure(monkeypatch,shift):
    def zero(state,pairs,**kwargs):
        return SimpleNamespace(energy=torch.zeros(1),forces=torch.zeros_like(state.coords))
    monkeypatch.setattr(scoring.ProductForceField,'from_registry',lambda *a,**k:SimpleNamespace(energy_forces=zero))
    p=receptor(); l=np.array([[1.,1.,1.],[2.,1.,1.]])
    a,da=scoring.run_stability_simulation(p,l,steps=2,temp_k=0.)
    b,db=scoring.run_stability_simulation(p+shift,l+shift,steps=2,temp_k=0.)
    assert da['status']==db['status']=='observed'
    assert a==pytest.approx(b,abs=1e-6)
    assert db['coordinate_clamped_component_count']==0
    assert db['coordinate_frame']=='receptor_centroid_local_translation_only'
    assert db['scientific_claim_validated'] is False
