"""A complete declared chemical graph survives scoring, publication and replay."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import math

import pytest
import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, Atom, Bond, Residue, Chain, StructureProvenance, canonical_topology_sha256
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_engine_v2.physics.reference_parameters import ReferenceForceFieldParameters, AtomNonbondedParameter, HarmonicBondParameter, HarmonicAngleParameter
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import OpenMMPeriodicParameters
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import EXPLICIT_REQUEST_SCHEMA, EXPLICIT_REPORT_SCHEMA, EXPLICIT_MODEL, LEGACY_MODEL, descriptor
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.workflow import run_request, verify_output
from betelgeuze_product.cpu_refinement_v1_2.resumable_workflow import run_resumable_request, verify_resumable_output
from betelgeuze_product.cpu_refinement_v1_2.resume_verification import verify_resume_summary
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from tests.unit.test_cpu_fixed_receptor import environment
from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture as old_request


def water(name, shift):
    theta = math.radians(104.5)
    return AllAtomSystem(name,
        tuple(Atom(i, f'{e}{i}', e, 8 if e == 'O' else 1, 0, partial_charge_e=q)
              for i, (e, q) in enumerate(zip(('O','H','H'),(-.8,.4,.4)))),
        (Bond(0,0,1), Bond(1,0,2)),
        (Residue(0,'HOH',0,1,(0,1,2)),), (Chain(0,'A',(0,)),),
        torch.tensor([[[0.,0.,0.],[1.,0.,0.],[math.cos(theta),math.sin(theta),0.]]],dtype=torch.float64)+shift,
        StructureProvenance(source_format='synthetic',source_id=name,source_sha256='a'*64,parser_name='explicit-test',parser_version='1'))


def request_fixture(tmp_path):
    request = old_request(tmp_path)
    receptor, ligand = water('receptor',4.), water('ligand',0.)
    base = ReferenceForceFieldParameters('synthetic-water','1',canonical_topology_sha256(ligand),
        tuple(AtomNonbondedParameter(i,1.,.01,float(a.partial_charge_e)) for i,a in enumerate(ligand.atoms)),
        bonds=(HarmonicBondParameter(0,1,1.,50.),HarmonicBondParameter(0,2,1.,50.)),
        angles=(HarmonicAngleParameter(1,0,2,math.radians(104.5),20.),),
        excluded_pairs=((0,1),(0,2),(1,2)),cutoff_angstrom=6.,switch_start_angstrom=5.)
    params = OpenMMPeriodicParameters(base)
    from dataclasses import replace
    cross = replace(environment(receptor,ligand,base).cross, coordinate_frame_id=request['pocket']['coordinate_frame_id'])
    for name, raw in {'receptor':canonical_system_json_bytes(receptor),'ligand':canonical_system_json_bytes(ligand),
        'parameters':json.dumps(base.to_dict()).encode(),'extensions':json.dumps(params.to_dict()).encode(),
        'cross_parameters':json.dumps(cross.to_dict()).encode()}.items():
        path=tmp_path/(name+'-explicit.json');path.write_bytes(raw)
        request[name]={'path':str(path),'sha256':hashlib.sha256(raw).hexdigest()}
    request['schema_id']=EXPLICIT_REQUEST_SCHEMA
    request['budget'].update(candidate_count=2,top_k=1,max_torsions=0)
    request['selection']['top_k']=1
    return request


def test_explicit_profile_actual_workflow_and_interrupted_replay(tmp_path):
    request=request_fixture(tmp_path)
    report=run_request(request,tmp_path/'full')['result']
    assert report['schema_id']==EXPLICIT_REPORT_SCHEMA
    assert verify_output(tmp_path/'full')['structural_verification_passed']
    assert report['arms']['baseline']['success_count']==2
    assert report['arms']['refined']['success_count']==2
    assert report['per_arm_selection']['baseline']['score_descriptor']==descriptor(EXPLICIT_MODEL).to_dict()
    paused=run_resumable_request(request,tmp_path/'split',stop_after=1)
    assert not paused['execution_complete'] and paused['committed_candidates']==1
    run_resumable_request(request,tmp_path/'split',resume=True)
    assert verify_resumable_output(tmp_path/'split')['structural_verification_passed']
    summary=json.loads((tmp_path/'split/report.json').read_bytes())['summary']
    assert summary['plan']['scorer']['feature_model_id']==EXPLICIT_MODEL
    assert report['scorer']==summary['plan']['scorer']
    assert summary['costs']['baseline']['reused_candidates']==1
    assert summary['costs']['baseline']['new_candidates']==1
    assert summary['paired_decisions']==report['paired_decisions']
    # Every retained numeric term is the same across the continuous and resumed paths.
    for arm in ('baseline','refined'):
        assert summary['rows'][arm]==report['arms'][arm]['rows']
    forged=deepcopy(report)
    forged['per_arm_selection']['baseline']['score_descriptor']=descriptor(LEGACY_MODEL).to_dict()
    forged['report_sha256']=digest({k:v for k,v in forged.items() if k!='report_sha256'})
    with pytest.raises(ResearchError,match='descriptor'):
        verify_report(forged)
    summary['plan']['scorer']['feature_model_id']=LEGACY_MODEL
    summary['plan_sha256']=digest(summary['plan'])
    summary['summary_sha256']=digest({k:v for k,v in summary.items() if k!='summary_sha256'})
    with pytest.raises(ResearchError,match='binding'):
        verify_resume_summary(summary)


def test_request_cannot_relabel_new_scoring_as_legacy_after_rehash(tmp_path):
    request=request_fixture(tmp_path)
    run_resumable_request(request,tmp_path/'run')
    request['schema_id']='cpu_fixed_receptor_request/1.0.0'
    # A different request cannot reuse the journal even if every coordinate is the same.
    with pytest.raises(ResearchError,match='resume request'):
        run_resumable_request(request,tmp_path/'run',resume=True)


@pytest.mark.parametrize('arm', ['baseline', 'refined'])
@pytest.mark.parametrize('identity', [
    'context_fingerprint_sha256', 'config_fingerprint_sha256', 'backend_receipt_sha256',
])
def test_explicit_success_terms_must_match_report_scorer_binding(tmp_path, arm, identity):
    report = run_request(request_fixture(tmp_path), tmp_path / 'run')['result']
    forged = deepcopy(report)
    terms = forged['arms'][arm]['rows'][1]['terms']
    terms[identity] = '0' * 64
    terms['receipt_sha256'] = digest({k: v for k, v in terms.items() if k != 'receipt_sha256'})
    forged['report_sha256'] = digest({k: v for k, v in forged.items() if k != 'report_sha256'})
    with pytest.raises(ResearchError, match='scorer identity'):
        verify_report(forged)
