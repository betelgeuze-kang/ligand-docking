"""Synthetic profile seam contracts; no molecular evaluation is permitted.

Frozen default hashes were captured before the optional seam was added. Fixed
synthetic timing values make the entire historical journal byte reproducible.
"""
from copy import deepcopy
from dataclasses import dataclass
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from betelgeuze_product.cpu_refinement_v1_2 import evaluation, fixed_receptor
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, decode_coordinates, digest, exact_fields, integer,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig, STATE_SCHEMA
from betelgeuze_product.cpu_refinement_v1_3.journal import TrialJournal
from betelgeuze_product.cpu_refinement_v1_3.kernel import (
    CartesianMachine, make_observation, validate_observation,
)


class ForbiddenMolecularEvaluation(BaseException):
    """Never swallowed as a retryable synthetic objective error."""


def _forbidden(*args, **kwargs):
    raise ForbiddenMolecularEvaluation('molecular evaluator/graph is forbidden')


@pytest.fixture(autouse=True)
def _synthetic_only(monkeypatch):
    monkeypatch.setattr(execution, 'build_compact_radius_graph', _forbidden)
    monkeypatch.setattr(evaluation.ExtendedEvaluator, 'evaluate', _forbidden)
    monkeypatch.setattr(fixed_receptor.FixedReceptorEvaluator, 'evaluate', _forbidden)
    # The admission/identity layer is outside this narrowly synthetic seam test.
    monkeypatch.setattr(execution, '_intact', lambda *args, **kwargs: None)


def _system():
    return SimpleNamespace(coordinates=torch.tensor([[[1., .25, -.125]]], dtype=torch.float64))


def _config(algorithm='lbfgs', **updates):
    return SolverConfig(**{'algorithm': algorithm, 'max_objective_attempts': 8,
                           'max_accepted_steps': 2, 'initial_step_size': .2,
                           'maximum_atom_displacement': .8, 'force_tolerance': 1.e-12,
                           **updates})


def _receipt(system, evaluator, config, intent):
    xyz = decode_coordinates(intent['coordinates'], 1)
    gradient = xyz * torch.tensor([2., 4., 8.], dtype=torch.float64)
    energy = float(.5 * (xyz * gradient).sum())
    observation = make_observation(intent['attempt'], xyz, energy, -gradient,
        {'total': energy, 'ligand_internal': energy,
         'cross_lennard_jones': 0., 'cross_screened_coulomb': 0.})
    return {'observation': observation, 'failure': None, 'error_type': None,
            'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0},
            'timings_ns': {'graph': 2, 'force': 3, 'objective': 7}}


@dataclass(frozen=True)
class _Profile:
    state_schema: str = 'synthetic_shape_state/1'
    journal_schema: str = 'synthetic_shape_journal/1'
    checkpoint_schema: str = 'synthetic_shape_checkpoint/1'

    def validate_observation(self, value, atom_count):
        base = {key: item for key, item in value.items() if key != 'synthetic_shape'}
        exact_fields(value, set(base) | {'synthetic_shape'})
        if value['synthetic_shape'] != 'validated':
            raise ResearchError('synthetic shape observation changed')
        return {**validate_observation(base, atom_count), 'synthetic_shape': 'validated'}

    def invoke(self, system, evaluator, config, intent):
        receipt = _receipt(system, evaluator, config, intent)
        receipt['observation']['synthetic_shape'] = 'validated'
        receipt['shape_work'] = {'calls': 1}
        return receipt

    def work(self, config):
        return {'optimizer_shape_calls': 0, 'restart_shape_calls': 0}

    def completed_work(self, payload, work, prefix):
        exact_fields(payload['shape_work'], {'calls'})
        work[prefix + '_shape_calls'] += integer(payload['shape_work']['calls'], 0, 1)

    def result_fields(self, state, config):
        fields = {'converged': False,
                  'augmented_force_converged': state['status'] == 'force_converged',
                  'raw_force_converged': False}
        if state['status'] == 'force_converged':
            fields['status'] = 'augmented_force_converged'
        return fields


def _arguments(path, config=None):
    return {'system': _system(), 'config': _config() if config is None else config,
            'evaluator': None, 'identity': {'synthetic': 'profile-seam'},
            'run_dir': path, 'implementation_sources': lambda: {},
            'result_schema': 'synthetic_result/1'}


_HISTORICAL = {
    'sd': {
        'result': 'eaa6868352a9f4fc2502af33dc93d69bb43a0749c1442babe8e1aa50f0b0e10b',
        'state': '2c50ba590d1f0bc323ade3c5ff530027b2a9f398b939960736802d8e80f40601',
        'files': {
            'checkpoints/checkpoint-00002.json': 'b2e6e4a80d95865edd059e1d7a3d0cd5618a1667fbb14e5065c9cbda63fe3919',
            'checkpoints/checkpoint-00004.json': 'dcbb51243981ab9cfcd62f1147b82c86e3e121a2dcd503b9bf18e53ad0ec099b',
            'checkpoints/checkpoint-00006.json': '88246e519f354871ae2681d190a38807a214794fd21a90b002c1425c7250a316',
            'events.jsonl': '2e6f3fda202197f2040dd092d93b0d0984b9aa35cc4ea1e035c37c9cdd0cc9c1',
            'meta.json': 'df99d291e642dbe6f48fb41511b97404fa5abf6257ce0bf9c4d58c4bbc66a107',
            'result.json': '60bb4fcc9222b9c9b53cec791ed4e037741dbe12e8b9c1072dbfa4c90da3ec3f',
        },
    },
    'lbfgs': {
        'result': '8b0b7bf45c09ed6f6c8efe63598c68eff51564d39c4733c7328bb23f4959d37c',
        'state': 'cc51b491ae0573881771fde35c367947b37bcb7074ae62c46b4e61a8b406521e',
        'files': {
            'checkpoints/checkpoint-00002.json': '6aba7bc553f02217bee28ffbdbafb1834e3b0eab6cf17ff9223d6759fde1ad79',
            'checkpoints/checkpoint-00004.json': 'fa0d0db1d937b89a18cde078e7d5bd6f07daed5c6c8b96616f884859dc9f4a79',
            'checkpoints/checkpoint-00006.json': '5f8da320269e63081a9233a8559e731c5028a2c657cfad717f2be7e67157c87b',
            'events.jsonl': 'a00cd482d4f32c5ffa42c53700a5924e7c7bd37cb60859927c1f97d42f8747f1',
            'meta.json': 'df99d291e642dbe6f48fb41511b97404fa5abf6257ce0bf9c4d58c4bbc66a107',
            'result.json': 'd9ba5322d6eca75348659fbf978ae6b83c01d7a510aa3bf4191d8630a3e0401c',
        },
    },
}


@pytest.mark.parametrize('algorithm', ['sd', 'lbfgs'])
@pytest.mark.parametrize('explicit_none', [False, True])
def test_default_profile_preserves_historical_numerics_and_journal_bytes(
        tmp_path, monkeypatch, algorithm, explicit_none):
    monkeypatch.setattr(execution, '_invoke', _receipt)
    path = tmp_path / 'default'
    arguments = _arguments(path, _config(algorithm))
    if explicit_none:
        arguments['profile'] = None
    result = execution._minimize_profile(**arguments)
    assert digest(result) == _HISTORICAL[algorithm]['result']
    assert digest(result['checkpoint']['state']) == _HISTORICAL[algorithm]['state']
    assert result['checkpoint']['state']['schema_id'] == STATE_SCHEMA
    assert 'schema_id' not in result['checkpoint']
    for name, expected in _HISTORICAL[algorithm]['files'].items():
        assert hashlib.sha256((path / name).read_bytes()).hexdigest() == expected
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    assert execution._verify_profile(**arguments) == result


def test_historical_invoke_implementation_is_unchanged():
    source = Path(execution.__file__).read_text()
    node = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == '_invoke')
    assert hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest() == (
        '8e6287c3daf47c986bdb1d30bd2e762388a166267c55d307eea61f2f56856ea7')


def test_profile_codec_is_opt_in_and_invalid_observation_is_atomic():
    system, config, profile = _system(), _config(), _Profile()
    profiled = CartesianMachine(system.coordinates, config, profile=profile)
    default = CartesianMachine(system.coordinates, config)
    intent = profiled.next_intent()
    observation = profile.invoke(system, None, config, intent)['observation']
    with pytest.raises(ResearchError):
        default.commit(intent, observation)
    assert default.snapshot()['attempts'] == 0
    before = profiled.snapshot()
    corrupted = deepcopy(observation)
    corrupted['synthetic_shape'] = 'altered'
    with pytest.raises(ResearchError, match='shape observation'):
        profiled.commit(intent, corrupted)
    assert profiled.snapshot() == before
    profiled.commit(intent, observation)
    assert profiled.snapshot()['schema_id'] == profile.state_schema
    assert profiled.snapshot()['current'] == observation


@pytest.mark.parametrize('algorithm', ['sd', 'lbfgs'])
def test_profile_uses_shared_pause_resume_and_read_only_replay(tmp_path, monkeypatch, algorithm):
    profile = _Profile()
    arguments = {**_arguments(tmp_path / 'profile', _config(algorithm)), 'profile': profile}
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    paused = execution._minimize_profile(**arguments, pause_after_objective_attempts=1)
    assert paused['status'] == 'checkpointed'
    assert paused['work']['optimizer_shape_calls'] == 1
    assert paused['work']['restart_shape_calls'] == 0
    result = execution._minimize_profile(**arguments, resume=True)
    assert result['work']['optimizer_shape_calls'] == 3
    assert result['work']['restart_shape_calls'] == 1
    assert result['work']['actual_force_calls'] == 4
    assert result['checkpoint']['schema_id'] == profile.checkpoint_schema
    assert result['checkpoint']['state']['schema_id'] == profile.state_schema
    metadata = json.loads((arguments['run_dir'] / 'meta.json').read_text())
    assert metadata['schema_id'] == profile.journal_schema
    validations = []
    validate = _Profile.validate_observation

    def observed(self, value, atom_count):
        validations.append(value['attempt'])
        return validate(self, value, atom_count)

    monkeypatch.setattr(_Profile, 'validate_observation', observed)
    monkeypatch.setattr(_Profile, 'invoke', _forbidden)
    assert execution._verify_profile(**arguments) == result
    assert validations == [1, 1, 2, 3]  # Includes the restart receipt.
    assert execution._minimize_profile(**arguments, resume=True) == result


def test_profile_convergence_is_explicitly_qualified(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    result = execution._minimize_profile(**_arguments(tmp_path / 'profile',
        _config(force_tolerance=100.)), profile=_Profile())
    assert result['checkpoint']['state']['status'] == 'force_converged'
    assert result['status'] == 'augmented_force_converged'
    assert result['augmented_force_converged'] is True
    assert result['converged'] is result['raw_force_converged'] is False
    assert result['scientifically_validated'] is result['claim_safe'] is False
    assert result['customer_execution_allowed'] is False


def test_profile_must_supply_convergence_field(tmp_path, monkeypatch):
    monkeypatch.setattr(_Profile, 'result_fields', lambda *args: {})
    with pytest.raises(ResearchError, match='explicitly qualify'):
        execution._minimize_profile(**_arguments(tmp_path / 'profile'), profile=_Profile())


def test_profile_cannot_replace_baseline_work_or_bypass_validation(monkeypatch):
    profile, config = _Profile(), _config()
    with monkeypatch.context() as patch:
        patch.setattr(_Profile, 'work', lambda *args: {'actual_force_calls': 99})
        with pytest.raises(ResearchError, match='separate counters'):
            execution._work(config, profile)
    machine = CartesianMachine(_system().coordinates, config)
    receipt = profile.invoke(_system(), None, config, machine.next_intent())
    receipt['work']['force_calls'] = 0
    monkeypatch.setattr(_Profile, 'completed_work', _forbidden)
    with pytest.raises(ResearchError, match='denominator'):
        execution._completed_work(receipt, execution._work(config, profile),
                                  execution._timings(), 'optimizer', profile)


@pytest.mark.parametrize('created_profile', [None, _Profile()])
def test_journal_schema_prevents_cross_profile_admission(tmp_path, created_profile):
    path, binding = tmp_path / 'journal', {'synthetic': True}
    with TrialJournal(path, binding, True, profile=created_profile):
        pass
    other = _Profile() if created_profile is None else None
    with pytest.raises(ResearchError, match='binding changed'):
        with TrialJournal(path, binding, False, profile=other):
            pytest.fail('mismatched profile admitted')


def test_profile_checkpoint_schema_is_validated_even_after_reseal(tmp_path):
    profile, path, binding = _Profile(), tmp_path / 'journal', {'synthetic': True}
    machine = CartesianMachine(_system().coordinates, _config(), profile)
    with TrialJournal(path, binding, True, profile=profile) as journal:
        checkpoint = journal.save_checkpoint(machine.snapshot())
        assert checkpoint == execution._checkpoint(machine, 0, digest(binding), profile)
    checkpoint['schema_id'] = 'substituted_checkpoint/1'
    checkpoint['checkpoint_sha256'] = digest({key: value for key, value in checkpoint.items()
                                               if key != 'checkpoint_sha256'})
    (path / 'checkpoints' / 'checkpoint-00000.json').write_text(canonical(checkpoint) + '\n')
    with pytest.raises(ResearchError, match='checkpoint schema'):
        with TrialJournal(path, binding, False, profile=profile):
            pytest.fail('substituted checkpoint admitted')


@pytest.mark.parametrize('profile', [None, _Profile()])
def test_shape_work_field_is_exactly_profile_scoped(tmp_path, profile):
    system, config, binding = _system(), _config(), {'synthetic': True}
    machine = CartesianMachine(system.coordinates, config, profile)
    intent = machine.next_intent()
    receipt = (_receipt if profile is None else profile.invoke)(system, None, config, intent)
    decision = machine.commit(intent, receipt['observation'])
    receipt.update(attempt=intent['attempt'], decision=decision, state_sha256=digest(machine.snapshot()))
    if profile is None:
        receipt['shape_work'] = {'calls': 1}
    else:
        del receipt['shape_work']
    with TrialJournal(tmp_path / 'journal', binding, True, profile=profile) as journal:
        journal.append('objective_started', intent)
        journal.append('objective_finished', receipt)
        with pytest.raises(ResearchError):
            execution._replay(journal, system, config, profile)


def test_profile_unknown_pending_preserves_additive_work(tmp_path):
    profile, system, config = _Profile(), _system(), _config()
    machine = CartesianMachine(system.coordinates, config, profile)
    with TrialJournal(tmp_path / 'journal', {'synthetic': True}, True, profile) as journal:
        journal.append('objective_started', machine.next_intent())
        with pytest.raises(execution.PendingWorkError) as failure:
            execution._replay(journal, system, config, profile)
    assert failure.value.work['unknown_pending_attempts'] == 1
    assert failure.value.work['actual_force_calls'] is None
    assert failure.value.work['optimizer_shape_calls'] == 0
