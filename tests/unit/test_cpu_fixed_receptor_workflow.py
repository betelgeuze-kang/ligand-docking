"""Actual candidate pipeline, crash boundaries and durable resume contracts."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.molecular import canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter
from betelgeuze_product.cpu_refinement_v1_2.cross_interaction import CrossParameters
from betelgeuze_product.cpu_refinement_v1_2 import fixed_receptor_workflow as workflow
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tests.unit.test_cpu_refinement_v1_2_workflow import request_fixture as internal_request
from tests.unit.test_engine_v2_energy_local_refinement_stage6 import _authority, _parameters


def request_fixture(path):
    prepared = internal_request(path)
    prepared['comparison']['require_convergence_for_selection'] = False
    _, receptor, ligand = _authority()
    # Unlike the old internal-only fixture, explicitly make physical charges
    # agree with the molecular state used by scoring and cross interactions.
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
    base = _parameters(ligand)
    base = replace(base, atom_parameters=tuple(replace(row, charge_e=float(ligand.atoms[i].partial_charge_e),
                  epsilon_kcal_per_mol=.02) for i,row in enumerate(base.atom_parameters)))
    for key,document in (("parameters",base.to_dict()),("extensions",ReferenceForceFieldV2Parameters(base).to_dict())):
        data=json.dumps(document).encode()
        dest=path/(key+"-physical.json")
        dest.write_bytes(data)
        prepared[key]={"path":str(dest.absolute()),"sha256":hashlib.sha256(data).hexdigest()}
    prepared["budget"]["seed"]=1301
    cross = CrossParameters(canonical_topology_sha256(receptor), base.fingerprint_sha256,
        'c'*64, prepared['pocket']['coordinate_frame_id'],
        tuple(AtomNonbondedParameter(i,1.5,.1,float(a.partial_charge_e)) for i,a in enumerate(receptor.atoms)),
        8.,6.,.1,4.,.1,2,())
    raw=json.dumps(cross.to_dict()).encode()
    dest=path/'cross.json'
    dest.write_bytes(raw)
    return {'schema_id':workflow.SCHEMA, 'prepared':prepared,
            'cross_parameters':{'path':str(dest.absolute()), 'sha256':hashlib.sha256(raw).hexdigest()},
            'maximum_internal_increase_kcal_per_mol':.5}


def test_real_fixed_receptor_pipeline_and_readonly_verify(tmp_path):
    request=request_fixture(tmp_path)
    report=workflow.run_request(request,tmp_path/'run')
    assert report['candidate_count']==2
    assert report['refinement_failure_count']==0
    assert report['committed_force_calls_observed']>0
    assert len(report['numerical_result']['final_selection']['selected_candidates'])<=1
    before={p.name:p.read_bytes() for p in (tmp_path/'run').iterdir() if p.is_file()}
    assert workflow.verify_output(tmp_path/'run')==report
    assert {p.name:p.read_bytes() for p in (tmp_path/'run').iterdir() if p.is_file()}==before
    for path in (tmp_path/'run').glob('candidate-*.json'):
        candidate=workflow._verified(path.absolute())['record']['numerical']
        attempt=candidate['attempt']
        assert attempt['energy_changes']['total_objective']<=0
        assert set(attempt['initial_components'])=={'ligand_internal','cross_lennard_jones','cross_screened_coulomb'}
        assert candidate['refined']['coordinates_sha256']!=candidate['baseline']['coordinates_sha256']


def test_pause_resume_reuses_committed_work_and_matches_uninterrupted(tmp_path,monkeypatch):
    request=request_fixture(tmp_path)
    full=workflow.run_request(request,tmp_path/'full')
    paused=workflow.run_request(request,tmp_path/'resume',stop_after=1)
    assert paused['completed_candidates']==1 and not paused['execution_complete']
    original=workflow.evaluate_candidate
    calls=[]
    def measured(*args,**kwargs):
        calls.append(args[2].proposal_index)
        return original(*args,**kwargs)
    monkeypatch.setattr(workflow,'evaluate_candidate',measured)
    resumed=workflow.run_request(request,tmp_path/'resume',resume=True)
    assert calls==[1]
    assert resumed['numerical_sha256']==full['numerical_sha256']
    assert resumed['committed_force_calls_observed']==full['committed_force_calls_observed']
    assert resumed['interrupted_attempts_unknown_cost']==0
    calls.clear()
    assert workflow.run_request(request,tmp_path/'resume',resume=True)==resumed
    assert calls==[]


@pytest.mark.parametrize('after_commit',[False,True])
def test_killed_process_recovery_preserves_commit_boundary(tmp_path,after_commit):
    request=request_fixture(tmp_path)
    full=workflow.run_request(request,tmp_path/'full')
    source=Path(__file__).resolve().parents[2]
    script='''import json,os,sys
from pathlib import Path
from betelgeuze_product.cpu_refinement_v1_2 import fixed_receptor_workflow as w
request=json.loads(Path(sys.argv[1]).read_text())
original=w._commit_candidate
def stop(*args,**kwargs):
    if sys.argv[3]=='True': original(*args,**kwargs)
    os._exit(42)
w._commit_candidate=stop
w.run_request(request,sys.argv[2])
'''
    path=tmp_path/'request.json'
    path.write_text(json.dumps(request))
    run=subprocess.run([sys.executable,'-c',script,str(path),str(tmp_path/'crash'),str(after_commit)],
                       env={**os.environ,'PYTHONPATH':str(source)},capture_output=True,text=True,timeout=90)
    assert run.returncode==42,run.stderr
    assert (tmp_path/'crash'/'candidate-00000.json').exists()==after_commit
    result=workflow.run_request(request,tmp_path/'crash',resume=True)
    assert result['numerical_sha256']==full['numerical_sha256']
    assert result['interrupted_attempts_unknown_cost']==(0 if after_commit else 1)
    assert workflow.verify_output(tmp_path/'crash')==result


@pytest.mark.parametrize('field',['seed','cross','strain','source','environment'])
def test_resume_drift_rejected(tmp_path,monkeypatch,field):
    request=request_fixture(tmp_path)
    workflow.run_request(request,tmp_path/'out',stop_after=1)
    if field=='seed':
        request['prepared']['budget']['seed']+=1
    elif field=='strain':
        request['maximum_internal_increase_kcal_per_mol']+=1
    elif field=='cross':
        Path(request['cross_parameters']['path']).write_text('{}')
    elif field=='environment':
        real=workflow.environment
        monkeypatch.setattr(workflow,'environment',lambda:{**real(),'python':'different'})
    else:
        real=workflow.source_manifest
        monkeypatch.setattr(workflow,'source_manifest',lambda:{**real(),'extra.py':'a'*64})
    with pytest.raises(ValueError):
        workflow.run_request(request,tmp_path/'out',resume=True)
    assert not (tmp_path/'out'/'complete.json').exists()


def test_corrupt_completed_candidate_is_rejected_not_recomputed(tmp_path):
    request=request_fixture(tmp_path)
    workflow.run_request(request,tmp_path/'out',stop_after=1)
    path=tmp_path/'out'/'candidate-00000.json'
    doc=json.loads(path.read_bytes())
    doc['payload']['record']['numerical']['selected_variant']='wrong'
    path.write_text(json.dumps(doc))
    with pytest.raises(ResearchError):
        workflow.run_request(request,tmp_path/'out',resume=True)


def test_partial_candidate_is_archived_not_treated_as_complete(tmp_path):
    request=request_fixture(tmp_path)
    workflow.run_request(request,tmp_path/'out',stop_after=0)
    (tmp_path/'out'/'candidate-00000.json.partial').write_bytes(b'{incomplete')
    result=workflow.run_request(request,tmp_path/'out',resume=True)
    assert result['candidate_count']==2
    assert (tmp_path/'out'/'abandoned-00000.bin').read_bytes()==b'{incomplete'


def test_invalid_total_report_or_completion_cannot_verify(tmp_path):
    request=request_fixture(tmp_path)
    workflow.run_request(request,tmp_path/'out')
    path=tmp_path/'out'/'report.json'
    doc=json.loads(path.read_bytes())
    doc['committed_force_calls_observed']=-1
    raw=json.dumps(doc).encode()
    path.write_bytes(raw)
    complete=tmp_path/'out'/'complete.json'
    d=json.loads(complete.read_bytes())
    d['report_sha256']=hashlib.sha256(raw).hexdigest()
    complete.write_text(json.dumps(d))
    with pytest.raises(ResearchError):
        workflow.verify_output(tmp_path/'out')


def test_internal_strain_and_total_objective_are_separate():
    from betelgeuze_product.cpu_refinement_v1_2.receptor_candidates import decision
    before={'succeeded':True,'selection_eligible':True,'score':5.}
    after={'succeeded':True,'selection_eligible':True,'score':4.}
    attempt={'status':'success','checkpoint':{'status':'converged'},
             'energy_changes':{'total_objective':-2.,'ligand_internal':1.}}
    assert decision(before,after,attempt,{'require_convergence':True,'maximum_internal_increase_kcal_per_mol':2.})[0]=='refined'
    assert decision(before,after,attempt,{'require_convergence':True,'maximum_internal_increase_kcal_per_mol':.5})[0]=='baseline'


def test_refinement_failure_retains_baselines(tmp_path,monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2 import receptor_candidates
    request=request_fixture(tmp_path)
    def fail(*args,**kwargs):
        raise RuntimeError('private failure')
    monkeypatch.setattr(receptor_candidates,'minimize_objective',fail)
    result=workflow.run_request(request,tmp_path/'out')
    assert result['refinement_failure_count']==2
    assert all(row['variant']=='baseline' for row in result['numerical_result']['final_selection']['selected_candidates'])
    assert workflow.verify_output(tmp_path/'out')==result
    assert 'private failure' not in str(result)


def test_preflight_no_output_and_existing_output_not_overwritten(tmp_path):
    request=request_fixture(tmp_path)
    plan,*_=workflow.prepare(request)
    assert len(plan['proposals'])==2
    (tmp_path/'out').mkdir()
    (tmp_path/'out'/'keep').write_text('keep')
    with pytest.raises(FileExistsError):
        workflow.run_request(request,tmp_path/'out')
    assert (tmp_path/'out'/'keep').read_text()=='keep'


def test_mismatched_ligand_charges_rejected_at_preflight(tmp_path):
    request=request_fixture(tmp_path)
    # Retain a complete table and its hashes but deliberately change a charge.
    from betelgeuze_product.reference_minimization_workflow import _parameters
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
    base=_parameters(json.loads(Path(request['prepared']['parameters']['path']).read_bytes()))
    base=replace(base,atom_parameters=tuple(replace(row,charge_e=0.) for row in base.atom_parameters))
    cross=CrossParameters.from_dict(json.loads(Path(request['cross_parameters']['path']).read_bytes()))
    cross=replace(cross,ligand_parameters_sha256=base.fingerprint_sha256)
    for ref,doc in ((request['prepared']['parameters'],base.to_dict()),
                    (request['prepared']['extensions'],ReferenceForceFieldV2Parameters(base).to_dict()),
                    (request['cross_parameters'],cross.to_dict())):
        data=json.dumps(doc).encode()
        Path(ref['path']).write_bytes(data)
        ref['sha256']=hashlib.sha256(data).hexdigest()
    with pytest.raises(ResearchError,match='charges'):
        workflow.run_request(request,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_lock_conflict_and_symlink_candidate_rejected(tmp_path):
    from betelgeuze_product.reference_minimization_workflow import _directory
    request=request_fixture(tmp_path)
    workflow.run_request(request,tmp_path/'out',stop_after=1)
    with _directory(tmp_path/'out',resume=True):
        with pytest.raises(BlockingIOError):
            workflow.run_request(request,tmp_path/'out',resume=True)
    candidate=tmp_path/'out'/'candidate-00000.json'
    data=candidate.read_bytes()
    candidate.unlink()
    target=tmp_path/'external'
    target.write_bytes(data)
    candidate.symlink_to(target)
    with pytest.raises(OSError):
        workflow.run_request(request,tmp_path/'out',resume=True)


def test_unexpected_intent_and_rehashed_component_mismatch_rejected(tmp_path):
    request=request_fixture(tmp_path)
    workflow.run_request(request,tmp_path/'out',stop_after=1)
    extra=tmp_path/'out'/'intent-99999-00000.json'
    extra.write_text('{}')
    with pytest.raises(ResearchError):
        workflow.run_request(request,tmp_path/'out',resume=True)
    extra.unlink()
    path=tmp_path/'out'/'candidate-00000.json'
    doc=json.loads(path.read_bytes())
    record=doc['payload']['record']
    record['numerical']['attempt']['energy_changes']['total_objective']-=1.
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
    record['numerical_sha256']=digest(record['numerical'])
    doc['sha256']=digest(doc['payload'])
    path.write_text(json.dumps(doc))
    with pytest.raises(ResearchError):
        workflow.run_request(request,tmp_path/'out',resume=True)


def test_input_change_during_candidate_does_not_commit(tmp_path,monkeypatch):
    request=request_fixture(tmp_path)
    original=workflow.evaluate_candidate
    def run_then_change(*args,**kwargs):
        record=original(*args,**kwargs)
        path=Path(request['cross_parameters']['path'])
        path.write_bytes(path.read_bytes()+b'\n')
        return record
    monkeypatch.setattr(workflow,'evaluate_candidate',run_then_change)
    with pytest.raises(ResearchError):
        workflow.run_request(request,tmp_path/'out')
    assert not (tmp_path/'out'/'candidate-00000.json').exists()
    assert not (tmp_path/'out'/'complete.json').exists()


def test_cli_real_subprocess_preflight_run_resume_and_verify(tmp_path):
    request=request_fixture(tmp_path)
    p=tmp_path/'request.json'
    p.write_text(json.dumps(request))
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2])}
    module='betelgeuze_product.cpu_refinement_v1_2.fixed_receptor_workflow'
    commands=[['preflight',str(p)],['run',str(p),'--output',str(tmp_path/'out'),'--stop-after','1'],
              ['run',str(p),'--output',str(tmp_path/'out'),'--resume'],['verify',str(tmp_path/'out')]]
    for args in commands:
        run=subprocess.run([sys.executable,'-m',module,*args],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=90)
        assert run.returncode==0,run.stderr
    assert workflow.verify_output(tmp_path/'out')['candidate_count']==2


@pytest.mark.parametrize('solvated', [False, True])
def test_cross_objective_with_distance_constraints_and_optional_charged_solvation(tmp_path, solvated):
    from betelgeuze_product.reference_minimization_workflow import _parameters
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
        ReferenceForceFieldV2Parameters, DistanceConstraintParameter,
    )
    from betelgeuze_engine_v2.physics.reference_solvation import FixedBornAtomParameter, FixedBornPolarSolvationParameters
    request = request_fixture(tmp_path)
    base = _parameters(json.loads(Path(request['prepared']['parameters']['path']).read_bytes()))
    parameters = ReferenceForceFieldV2Parameters(base, constraints=(
        DistanceConstraintParameter(1, 2, 1., tolerance_angstrom=1.e-10),))
    documents = {'extensions': parameters.to_dict()}
    if solvated:
        solvent = FixedBornPolarSolvationParameters(
            parameter_set_id='synthetic-cross-gb', parameter_set_version='1', parameter_source_sha256='d' * 64,
            topology_sha256=parameters.topology_sha256,
            charge_parameter_fingerprint_sha256=parameters.fingerprint_sha256,
            atom_parameters=tuple(FixedBornAtomParameter(i, 1.5 + .1 * i) for i in range(5)))
        documents['solvation'] = solvent.to_dict()
    for name, document in documents.items():
        path = tmp_path / f'{name}-composed.json'
        data = json.dumps(document).encode()
        path.write_bytes(data)
        request['prepared'][name] = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}
    full = workflow.run_request(request, tmp_path / 'full')
    assert full['refinement_failure_count'] == 0
    workflow.run_request(request, tmp_path / 'resumed', stop_after=1)
    resumed = workflow.run_request(request, tmp_path / 'resumed', resume=True)
    assert resumed['numerical_sha256'] == full['numerical_sha256']
    assert workflow.verify_output(tmp_path / 'resumed') == resumed
    for path in (tmp_path / 'full').glob('candidate-*.json'):
        attempt = workflow._verified(path.absolute())['record']['numerical']['attempt']
        assert attempt['checkpoint']['current_constraint_residual'] <= 1.e-10
        assert attempt['energy_changes']['total_objective'] <= 0
        assert (attempt['checkpoint']['evaluator']['internal']['solvation_fingerprint_sha256'] is not None) == solvated


@pytest.mark.parametrize('after_report', [False, True])
def test_killed_final_publication_reuses_all_committed_candidates(tmp_path, monkeypatch, after_report):
    request = request_fixture(tmp_path)
    full = workflow.run_request(request, tmp_path / 'full')
    script = '''import json,os,sys
from pathlib import Path
from betelgeuze_product.cpu_refinement_v1_2 import fixed_receptor_workflow as w
request=json.loads(Path(sys.argv[1]).read_text())
original=w._publish
def stop(path,value):
    if path.name == 'report.json':
        if sys.argv[3]=='True': original(path,value)
        os._exit(43)
    return original(path,value)
w._publish=stop
w.run_request(request,sys.argv[2])
'''
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    run = subprocess.run([sys.executable, '-c', script, str(path), str(tmp_path / 'crash'), str(after_report)],
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])},
        capture_output=True, text=True, timeout=90)
    assert run.returncode == 43, run.stderr
    assert len(list((tmp_path / 'crash').glob('candidate-*.json'))) == 2
    assert (tmp_path / 'crash' / 'report.json').exists() == after_report
    assert not (tmp_path / 'crash' / 'complete.json').exists()
    def forbidden(*args, **kwargs):
        pytest.fail('committed candidates must not be recomputed during final publication recovery')
    monkeypatch.setattr(workflow, 'evaluate_candidate', forbidden)
    resumed = workflow.run_request(request, tmp_path / 'crash', resume=True)
    assert resumed['numerical_sha256'] == full['numerical_sha256']
    assert resumed['interrupted_attempts_unknown_cost'] == 0
    assert workflow.verify_output(tmp_path / 'crash') == resumed
