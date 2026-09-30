"""Tiny declared water fixtures; Cartesian installation/orchestration, not accuracy."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.chemical_features import ExplicitGraphScorer
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_v1_3 import workflow
from tests.unit.test_cpu_registered_pose_workflow import request_fixture


def request(directory, *, strained=False, attempts=3, accepted=2):
    old, _ = request_fixture(directory, strained=strained)
    config = SolverConfig(max_objective_attempts=attempts, max_accepted_steps=accepted)
    return workflow.prepare_cartesian_request(old, config)


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def reseal(value, field='receipt_sha256'):
    value[field] = digest({k: v for k, v in value.items() if k != field})


def forbidden(*args, **kwargs):
    pytest.fail('completed verification/resume attempted numerical work or scoring')


def observe_numerical_and_score_calls(monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_3 import minimization
    calls = {'numerical_graph': 0, 'force': 0, 'score': 0}

    def counted(original, name):
        def wrapped(*args, **kwargs):
            calls[name] += 1
            return original(*args, **kwargs)
        return wrapped

    for target, method, name in (
            (minimization, 'build_compact_radius_graph', 'numerical_graph'),
            (workflow.FixedReceptorEvaluator, 'evaluate', 'force'),
            (ExplicitGraphScorer, 'score_terms', 'score')):
        monkeypatch.setattr(target, method, counted(getattr(target, method), name))
    return calls


def test_conversion_is_explicit_and_does_not_mutate_old_input(tmp_path):
    old, _ = request_fixture(tmp_path)
    before = deepcopy(old)
    config = SolverConfig(max_objective_attempts=3)
    new = workflow.prepare_cartesian_request(old, config)
    assert old == before
    assert new['schema_id'] == workflow.REQUEST_SCHEMA
    assert new['solver'] == config.to_dict()
    assert set(new['budget']) == workflow.POSE_FIELDS
    assert 'max_refinement_steps' not in new['budget']
    for name in workflow.FILE_FIELDS:
        assert new[name] == old[name]
    from betelgeuze_product.cpu_refinement_v1_2.registered_policy_adapter import input_binding
    with pytest.raises(ResearchError, match='requires_registered'):
        input_binding(new)


@pytest.mark.parametrize('change', ['old_schema', 'weaker_force', 'unconverged', 'perturb',
                                   'pose_iteration_budget', 'bool_candidate', 'unknown_field'])
def test_new_request_rejects_schema_and_selection_budget_relaxations(tmp_path, change):
    req = request(tmp_path)
    if change == 'old_schema':
        req['schema_id'] = workflow.REGISTERED_REQUEST_SCHEMA
    elif change == 'weaker_force':
        req['solver'] = replace(SolverConfig(), force_tolerance=.01).to_dict()
    elif change == 'unconverged':
        req['comparison']['require_convergence_for_selection'] = False
    elif change == 'perturb':
        req['budget']['translation_radius_angstrom'] = .01
    elif change == 'pose_iteration_budget':
        req['budget']['max_refinement_steps'] = 1
    elif change == 'bool_candidate':
        req['budget']['candidate_count'] = True
    else:
        req['undeclared'] = 1
    with pytest.raises(ResearchError):
        workflow._request(req)


def test_binding_preserves_registered_coordinates_and_rejects_weaker_strain(tmp_path):
    req = request(tmp_path)
    binding = workflow.input_binding(req)
    assert binding['score_quantity'] == workflow.SCORE_QUANTITY
    assert binding['proposal_policy']['candidate_count'] == 1
    assert binding['proposal_policy']['translation_radius_angstrom'] == 0
    assert binding['candidate_source_admission_verified'] is False
    cross = read(req['cross_parameters']['path'])
    cross['max_internal_increase_kcal_per_mol'] = 5.001
    write(req['cross_parameters']['path'], cross)
    import hashlib
    req['cross_parameters']['sha256'] = hashlib.sha256(Path(req['cross_parameters']['path']).read_bytes()).hexdigest()
    with pytest.raises(ResearchError, match='strain cap'):
        workflow.input_binding(req)


@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    path = tmp_path_factory.mktemp('cartesian-workflow-completed')
    req = request(path, strained=True, attempts=2, accepted=1)
    envelope = workflow.evaluate(req, path / 'run')
    return path, req, envelope


def test_completed_refinement_retains_baseline_when_not_converged(completed):
    path, req, envelope = completed
    result = envelope['result']
    assert result['execution_complete']
    assert result['attempt']['converged'] is False
    assert result['paired_decision']['variant'] == 'baseline'
    assert result['paired_decision']['reason'] == 'refinement_not_converged'
    assert result['score_calls'] == 2
    assert envelope['invocation']['score_work']['new_score_calls'] == 2
    assert result['per_arm_selection']['refined']['selected_candidates'] == []
    selected, = result['final_selection']['selected_candidates']
    assert selected['coordinates_binary64_hex'] == result['binding']['proposal_policy']['initial_coordinates_binary64_hex']
    assert selected['variant'] == 'baseline'
    assert read(path / 'run/request.json') == req
    assert workflow.verify_output(req, path / 'run')['structural_verification_passed']


def test_completed_resume_and_cli_verify_never_rescore_or_recompute(completed, monkeypatch, capsys):
    path, req, envelope = completed
    from betelgeuze_product.cpu_refinement_v1_3 import minimization
    monkeypatch.setattr(minimization, 'minimize', forbidden)
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    monkeypatch.setattr(workflow.ExtendedEvaluator, 'evaluate', forbidden)
    monkeypatch.setattr(workflow.FixedReceptorEvaluator, 'evaluate', forbidden)
    monkeypatch.setattr(workflow.FixedReceptorEnvironment, 'evaluate_cross', forbidden)
    result = workflow.evaluate(req, path / 'run', resume=True)
    assert result['result'] == envelope['result']
    assert result['invocation']['score_work']['new_score_calls'] == 0
    assert result['invocation']['score_work']['reused_score_receipts'] == 2
    assert result['invocation']['new_force_calls'] == 0
    from betelgeuze_product.cpu_refinement_v1_3.__main__ import main
    assert main(['verify', '--request', str(path / 'run/request.json'), '--run-dir', str(path / 'run')]) == 0
    assert json.loads(capsys.readouterr().out)['scoring_reexecuted'] is False


def test_pause_preserves_baseline_and_resume_only_scores_terminal_once(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_3 import minimization
    original, seen = minimization.minimize, []

    def observe_path(*args, **kwargs):
        seen.append(kwargs['run_dir'])
        assert not str(kwargs['run_dir']).startswith('/proc/')
        assert kwargs['run_dir'] == tmp_path / 'run/numerical'
        return original(*args, **kwargs)

    monkeypatch.setattr(minimization, 'minimize', observe_path)
    req = request(tmp_path, strained=True, attempts=4, accepted=3)
    first = workflow.evaluate(req, tmp_path / 'run', pause_after_objective_attempts=1)
    assert first['result']['status'] == 'checkpointed'
    assert first['result']['final_selection'] is None
    assert first['invocation']['score_work']['new_score_calls'] == 1
    assert first['invocation']['new_force_calls'] == 1
    assert not (tmp_path / 'run/refined-score-intent.json').exists()
    before = (tmp_path / 'run/baseline-score.json').read_bytes()
    second = workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert second['result']['execution_complete']
    assert second['invocation']['score_work']['new_score_calls'] == 1
    assert (tmp_path / 'run/baseline-score.json').read_bytes() == before
    assert len(seen) == 2
    assert (first['invocation']['new_force_calls'] + second['invocation']['new_force_calls']
            == second['result']['force_work']['actual_force_calls'])
    assert workflow.verify_output(req, tmp_path / 'run')['structural_verification_passed']


@pytest.mark.parametrize('damage', ['numerical', 'intent', 'changed_intent', 'both', 'both_unfinished'])
def test_missing_numerical_history_cannot_reset_force_budget(tmp_path, monkeypatch, damage):
    import shutil
    from betelgeuze_product.cpu_refinement_v1_3 import minimization
    req = request(tmp_path, strained=True, attempts=4, accepted=3)
    first = workflow.evaluate(req, tmp_path / 'run', pause_after_objective_attempts=1)
    assert first['invocation']['new_force_calls'] == 1
    intent = tmp_path / 'run/numerical-start-intent.json'
    if damage in {'numerical', 'both', 'both_unfinished'}:
        shutil.rmtree(tmp_path / 'run/numerical')  # Tiny test output only.
    if damage in {'intent', 'both', 'both_unfinished'}:
        intent.unlink()
    if damage == 'both_unfinished':
        (tmp_path / 'run/invocation-000000.end.json').unlink()
    if damage == 'changed_intent':
        value = read(intent)
        value['binding_sha256'] = '0' * 64
        write(intent, value)
    monkeypatch.setattr(minimization, 'minimize', forbidden)
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    with pytest.raises(ResearchError):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    last = read(tmp_path / 'run/invocation-000001.end.json')
    assert last['new_force_calls'] == 0
    assert last['numerical_entrypoint_invoked'] is False
    assert last['score_work']['new_score_calls'] == 0


def test_completed_baseline_before_reservation_can_resume_without_rescoring(tmp_path, monkeypatch):
    req = request(tmp_path, attempts=2, accepted=1)
    original = workflow._numerical_reservation

    def interrupt_before_reservation(*args, **kwargs):
        raise KeyboardInterrupt('synthetic interruption before numerical reservation')

    monkeypatch.setattr(workflow, '_numerical_reservation', interrupt_before_reservation)
    with pytest.raises(KeyboardInterrupt):
        workflow.evaluate(req, tmp_path / 'run')
    assert not (tmp_path / 'run/numerical-start-intent.json').exists()
    baseline = (tmp_path / 'run/baseline-score.json').read_bytes()
    end = read(tmp_path / 'run/invocation-000000.end.json')
    assert end['numerical_entrypoint_invoked'] is False and end['new_force_calls'] == 0
    monkeypatch.setattr(workflow, '_numerical_reservation', original)
    result = workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert result['result']['execution_complete']
    assert result['invocation']['score_work']['new_score_calls'] == 1
    assert (tmp_path / 'run/baseline-score.json').read_bytes() == baseline


def test_completed_verification_requires_numerical_reservation(completed, tmp_path, monkeypatch):
    import shutil
    path, req, _ = completed
    shutil.copytree(path / 'run', tmp_path / 'run')
    (tmp_path / 'run/numerical-start-intent.json').unlink()
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    with pytest.raises(ResearchError, match='numerical start intent is missing'):
        workflow.verify_output(req, tmp_path / 'run')


@pytest.mark.parametrize('arm', ['baseline', 'refined'])
@pytest.mark.parametrize('unfinished', [False, True])
def test_deleted_score_reservation_and_receipt_cannot_reset_score_budget(tmp_path, monkeypatch, arm, unfinished):
    req = request(tmp_path, strained=True, attempts=2, accepted=1)
    kwargs = {'pause_after_objective_attempts': 1} if arm == 'baseline' else {}
    first = workflow.evaluate(req, tmp_path / 'run', **kwargs)
    assert first['invocation']['score_work']['new_score_calls_by_arm'][arm] == 1
    for name in (f'{arm}-score-intent.json', f'{arm}-score.json', 'result.json'):
        path = tmp_path / 'run' / name
        if path.exists():
            path.unlink()  # Tiny test artifacts only.
    if unfinished:
        (tmp_path / 'run/invocation-000000.end.json').unlink()
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    monkeypatch.setattr(workflow.FixedReceptorEvaluator, 'evaluate', forbidden)
    with pytest.raises(ResearchError, match='automatic rescore is forbidden'):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    last = read(tmp_path / 'run/invocation-000001.end.json')
    assert last['new_force_calls'] == 0
    assert last['score_work']['new_score_calls'] == 0
    assert last['score_work']['unknown_pending_score_attempts'] == 1


@pytest.mark.parametrize('arm', ['baseline', 'refined'])
def test_deleted_interrupted_score_intent_keeps_unknown_denominator(tmp_path, monkeypatch, arm):
    req = request(tmp_path, attempts=2, accepted=1)
    original, calls = ExplicitGraphScorer.score_terms, []

    def interrupt(self, proposal):
        calls.append('refined' if proposal.refined else 'baseline')
        if calls[-1] == arm:
            raise KeyboardInterrupt('synthetic score interruption')
        return original(self, proposal)

    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', interrupt)
    with pytest.raises(KeyboardInterrupt):
        workflow.evaluate(req, tmp_path / 'run')
    (tmp_path / 'run' / f'{arm}-score-intent.json').unlink()
    before = list(calls)
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    monkeypatch.setattr(workflow.FixedReceptorEvaluator, 'evaluate', forbidden)
    with pytest.raises(ResearchError, match='automatic rescore is forbidden'):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert calls == before
    first = read(tmp_path / 'run/invocation-000000.end.json')
    last = read(tmp_path / 'run/invocation-000001.end.json')
    assert first['score_work']['unknown_pending_score_attempts'] == 1
    assert first['score_work']['new_score_calls_by_arm'][arm] == 1
    assert last['score_work']['unknown_pending_score_attempts'] == 1
    assert last['score_work']['new_score_calls'] == 0 and last['new_force_calls'] == 0


def test_proven_zero_score_interruption_can_resume_before_baseline(tmp_path, monkeypatch):
    req = request(tmp_path, attempts=2, accepted=1)
    original = workflow._score

    def before_score(*args, **kwargs):
        raise KeyboardInterrupt('synthetic interruption before score entry')

    monkeypatch.setattr(workflow, '_score', before_score)
    with pytest.raises(KeyboardInterrupt):
        workflow.evaluate(req, tmp_path / 'run')
    first = read(tmp_path / 'run/invocation-000000.end.json')
    assert first['score_work']['new_score_calls_by_arm'] == {'baseline': 0, 'refined': 0}
    assert first['score_work']['new_score_calls'] == 0
    monkeypatch.setattr(workflow, '_score', original)
    resumed = workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert resumed['result']['execution_complete']
    assert resumed['invocation']['score_work']['new_score_calls'] == 2


@pytest.mark.parametrize('damage', ['end_only', 'index_gap', 'end_index', 'filename', 'score_denominator'])
def test_surviving_invocation_records_are_checked_before_any_new_work(completed, tmp_path, monkeypatch, damage):
    import shutil
    path, req, _ = completed
    shutil.copytree(path / 'run', tmp_path / 'run')
    # Model a terminal nested run whose outer final score/summary was lost.
    for name in ('result.json', 'refined-score-intent.json', 'refined-score.json'):
        (tmp_path / 'run' / name).unlink()
    end_path = tmp_path / 'run/invocation-000000.end.json'
    # The module fixture may already contain a completed zero-work reuse.
    if damage == 'end_only':
        (tmp_path / 'run/invocation-000000.start.json').unlink()
    elif damage == 'index_gap':
        for item in sorted((tmp_path / 'run').glob('invocation-*.*.json'), reverse=True):
            index = int(item.name.split('-')[1].split('.')[0])
            renamed = item.with_name(item.name.replace(f'{index:06d}', f'{index + 1:06d}', 1))
            item.rename(renamed)
            if renamed.name.endswith('.end.json'):
                value = read(renamed)
                value['index'] = index + 1
                write(renamed, value)
    elif damage == 'end_index':
        value = read(end_path)
        value['index'] += 10
        write(end_path, value)
    elif damage == 'filename':
        end_path.rename(tmp_path / 'run/invocation-unindexed.end.json')
    else:
        value = read(end_path)
        value['score_work']['new_score_calls_by_arm']['refined'] = 0
        write(end_path, value)
    from betelgeuze_product.cpu_refinement_v1_3 import minimization
    monkeypatch.setattr(minimization, 'minimize', forbidden)
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    with pytest.raises(ResearchError, match='invocation'):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    last = read(sorted((tmp_path / 'run').glob('invocation-*.end.json'))[-1])
    # For the unindexed corrupt filename, use the highest numeric end explicitly.
    if damage == 'filename':
        last = read(sorted((tmp_path / 'run').glob('invocation-0*.end.json'))[-1])
    assert last['new_force_calls'] == 0
    assert last['score_work']['new_score_calls'] == 0
    assert last['numerical_entrypoint_invoked'] is False


def test_start_only_invocation_preserves_completed_zero_work_reuse(completed, tmp_path, monkeypatch):
    import shutil
    from betelgeuze_product.cpu_refinement_v1_3 import minimization
    path, req, original = completed
    shutil.copytree(path / 'run', tmp_path / 'run')
    (tmp_path / 'run/invocation-000000.end.json').unlink()
    monkeypatch.setattr(minimization, 'minimize', forbidden)
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    reused = workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert reused['result'] == original['result']
    assert reused['invocation']['prior_unfinished_invocations'] == 1
    assert reused['invocation']['new_force_calls'] == 0
    assert reused['invocation']['score_work']['new_score_calls'] == 0
    assert not (tmp_path / 'run/invocation-000000.end.json').exists()


def test_older_valid_numerical_prefix_cannot_erase_retained_outer_work(tmp_path, monkeypatch):
    import shutil
    from betelgeuze_product.cpu_refinement_v1_3 import minimization
    req = request(tmp_path, strained=True, attempts=5, accepted=4)
    workflow.evaluate(req, tmp_path / 'run', pause_after_objective_attempts=1)
    shutil.copytree(tmp_path / 'run/numerical', tmp_path / 'older-numerical-prefix')
    newer = workflow.evaluate(req, tmp_path / 'run', resume=True, pause_after_objective_attempts=2)
    assert newer['result']['numerical_result']['work']['actual_force_calls'] == 3
    # Keep both outer invocation ends but substitute an older internally valid tiny journal.
    shutil.rmtree(tmp_path / 'run/numerical')
    shutil.copytree(tmp_path / 'older-numerical-prefix', tmp_path / 'run/numerical')
    monkeypatch.setattr(minimization, 'minimize', forbidden)
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    with pytest.raises(ResearchError, match='behind retained invocation work'):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    retained = read(tmp_path / 'run/invocation-000001.end.json')
    assert retained['numerical_work_after']['actual_force_calls'] == 3
    last = read(tmp_path / 'run/invocation-000002.end.json')
    assert last['new_force_calls'] == 0
    assert last['score_work']['new_score_calls'] == 0
    assert last['numerical_entrypoint_invoked'] is False


@pytest.mark.parametrize('missing_end', [False, True])
def test_unknown_invocation_cannot_resume_from_older_complete_prefix(tmp_path, monkeypatch, missing_end):
    import shutil
    req = request(tmp_path, strained=True, attempts=5, accepted=4)
    calls = observe_numerical_and_score_calls(monkeypatch)
    workflow.evaluate(req, tmp_path / 'run', pause_after_objective_attempts=1)
    assert calls == {'numerical_graph': 1, 'force': 1, 'score': 1}
    shutil.copytree(tmp_path / 'run/numerical', tmp_path / 'older-numerical-prefix')
    tracked_evaluate = workflow.FixedReceptorEvaluator.evaluate
    force_entries = []

    def interrupt_objective(*args, **kwargs):
        value = tracked_evaluate(*args, **kwargs)
        force_entries.append(1)
        # The restart check returns, then a real tiny objective evaluates without a durable finish.
        if len(force_entries) == 2:
            raise KeyboardInterrupt('synthetic objective interruption after force evaluation')
        return value

    monkeypatch.setattr(workflow.FixedReceptorEvaluator, 'evaluate', interrupt_objective)
    with pytest.raises(KeyboardInterrupt):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    interrupted_path = tmp_path / 'run/invocation-000001.end.json'
    interrupted = read(interrupted_path)
    assert interrupted['numerical_entrypoint_invoked'] is True
    assert interrupted['numerical_work_before']['actual_force_calls'] == 1
    assert interrupted['numerical_work_after'] is None and interrupted['new_force_calls'] is None
    assert calls == {'numerical_graph': 3, 'force': 3, 'score': 1}
    if missing_end:
        interrupted_path.unlink()
    shutil.rmtree(tmp_path / 'run/numerical')
    shutil.copytree(tmp_path / 'older-numerical-prefix', tmp_path / 'run/numerical')
    monkeypatch.setattr(workflow.FixedReceptorEvaluator, 'evaluate', tracked_evaluate)
    before = dict(calls)
    with pytest.raises(ResearchError, match='work is unresolved; automatic continuation is forbidden'):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert calls == before  # Real graph, force and scorer entrypoints all remained uncalled.
    last = read(tmp_path / 'run/invocation-000002.end.json')
    assert last['new_force_calls'] == 0 and last['score_work']['new_score_calls'] == 0
    assert last['numerical_entrypoint_invoked'] is False
    assert last['prior_unresolved_numerical_invocations'] == [{'index': 1, 'reason':
        'invocation_end_missing' if missing_end else 'numerical_return_work_unknown'}]
    if not missing_end:
        assert read(interrupted_path) == interrupted  # Unknown historical cost was not rewritten as zero.


@pytest.mark.parametrize('missing_end', [False, True])
def test_terminal_nested_result_can_rebuild_outer_result_without_new_work(completed, tmp_path, monkeypatch, missing_end):
    import shutil
    path, req, original = completed
    shutil.copytree(path / 'run', tmp_path / 'run')
    (tmp_path / 'run/result.json').unlink()
    end_path = tmp_path / 'run/invocation-000000.end.json'
    if missing_end:
        end_path.unlink()
    else:
        end = read(end_path)
        end.update(numerical_work_after=None, new_force_calls=None, new_numerical_call_counts=None)
        write(end_path, end)
    calls = observe_numerical_and_score_calls(monkeypatch)
    reused = workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert reused['result'] == original['result']
    assert calls == {'numerical_graph': 0, 'force': 0, 'score': 0}
    assert reused['invocation']['new_force_calls'] == 0
    assert reused['invocation']['score_work']['new_score_calls'] == 0
    assert reused['invocation']['prior_unresolved_numerical_invocations'] == [{'index': 0, 'reason':
        'invocation_end_missing' if missing_end else 'numerical_return_work_unknown'}]


def test_terminal_finish_before_checkpoint_recovers_without_new_numerical_work(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_3.journal import TrialJournal
    req = request(tmp_path, strained=True, attempts=2, accepted=1)
    calls = observe_numerical_and_score_calls(monkeypatch)
    save = TrialJournal.save_checkpoint

    def interrupt_terminal_checkpoint(self, state):
        if state['status'] != 'running':
            raise KeyboardInterrupt('synthetic terminal finish before checkpoint')
        return save(self, state)

    monkeypatch.setattr(TrialJournal, 'save_checkpoint', interrupt_terminal_checkpoint)
    with pytest.raises(KeyboardInterrupt):
        workflow.evaluate(req, tmp_path / 'run')
    end = read(tmp_path / 'run/invocation-000000.end.json')
    assert end['numerical_work_after'] is None and end['new_force_calls'] is None
    assert calls == {'numerical_graph': 2, 'force': 2, 'score': 1}
    monkeypatch.setattr(TrialJournal, 'save_checkpoint', save)
    resumed = workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert resumed['result']['execution_complete']
    assert calls == {'numerical_graph': 2, 'force': 2, 'score': 2}
    assert resumed['invocation']['new_force_calls'] == 0
    assert resumed['invocation']['score_work']['new_score_calls_by_arm'] == {'baseline': 0, 'refined': 1}
    assert resumed['invocation']['prior_unresolved_numerical_invocations'] == [
        {'index': 0, 'reason': 'numerical_return_work_unknown'}]
    assert read(tmp_path / 'run/invocation-000000.end.json') == end


def test_uncommitted_score_intent_is_never_automatically_retried(tmp_path, monkeypatch):
    req = request(tmp_path)
    calls = []

    def interrupt(*args, **kwargs):
        calls.append(1)
        raise KeyboardInterrupt('synthetic interrupted score')

    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', interrupt)
    with pytest.raises(KeyboardInterrupt):
        workflow.evaluate(req, tmp_path / 'run')
    assert calls == [1]
    assert not (tmp_path / 'run/baseline-score.json').exists()
    first = read(tmp_path / 'run/invocation-000000.end.json')
    assert first['score_work']['new_score_calls'] == 1
    assert first['score_work']['unknown_pending_score_attempts'] == 1
    assert first['new_force_calls'] == 0
    with pytest.raises(ResearchError, match='automatic rescore is forbidden'):
        workflow.evaluate(req, tmp_path / 'run', resume=True)
    assert calls == [1]
    last = read(tmp_path / 'run/invocation-000001.end.json')
    assert last['score_work']['new_score_calls'] == 0
    assert last['score_work']['unknown_pending_score_attempts'] == 1


def test_failed_score_receipt_remains_in_denominator(tmp_path, monkeypatch):
    req = request(tmp_path, attempts=2, accepted=1)
    original = ExplicitGraphScorer.score_terms
    calls = []

    def fail_first(self, proposal):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError('synthetic baseline score failure')
        return original(self, proposal)

    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', fail_first)
    result = workflow.evaluate(req, tmp_path / 'run')['result']
    assert result['rows']['baseline']['status'] == 'failure'
    assert result['score_calls'] == 2 and len(calls) == 2
    assert result['score_receipts']['baseline']['work']['stages']['score.evaluate']['failed'] == 1
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    assert workflow.verify_output(req, tmp_path / 'run')['structural_verification_passed']


def test_initial_objective_failure_keeps_baseline_and_does_not_score_a_fabricated_final_pose(tmp_path, monkeypatch):
    req = request(tmp_path)

    def fail_force(*args, **kwargs):
        raise ValueError('synthetic initial objective failure')

    monkeypatch.setattr(workflow.FixedReceptorEvaluator, 'evaluate', fail_force)
    result = workflow.evaluate(req, tmp_path / 'run')['result']
    assert result['numerical_result']['status'] == 'evaluation_failed'
    assert result['attempt']['status'] == 'failure'
    assert result['score_calls'] == 1
    assert result['score_receipts']['refined'] is None
    assert result['force_work']['actual_force_calls'] == 1
    assert result['force_work']['failed_optimizer_force_calls'] == 1
    assert result['paired_decision']['variant'] == 'baseline'
    assert result['paired_decision']['reason'] == 'refinement_or_rescoring_failed'
    monkeypatch.setattr(ExplicitGraphScorer, 'score_terms', forbidden)
    assert workflow.verify_output(req, tmp_path / 'run')['structural_verification_passed']


@pytest.mark.parametrize('field', ['paired_decision', 'final_selection', 'force_work', 'binding'])
def test_resealed_summary_tampering_is_rejected(completed, tmp_path, field):
    path, req, _ = completed
    # Only tiny test output artifacts are copied, never installed dependencies.
    import shutil
    shutil.copytree(path / 'run', tmp_path / 'run')
    result = read(tmp_path / 'run/result.json')
    if field == 'paired_decision':
        result[field]['reason'] = 'invented'
    elif field == 'final_selection':
        result[field]['selected_candidates'] = []
    elif field == 'force_work':
        result[field]['actual_force_calls'] += 1
    else:
        result[field]['candidate_source_admission_verified'] = True
        reseal(result[field])
    reseal(result, 'result_sha256')
    write(tmp_path / 'run/result.json', result)
    with pytest.raises(ResearchError):
        workflow.verify_output(req, tmp_path / 'run')


def test_resealed_score_receipt_cannot_change_scored_coordinates(completed, tmp_path):
    path, req, _ = completed
    import shutil
    shutil.copytree(path / 'run', tmp_path / 'run')
    target = tmp_path / 'run/refined-score.json'
    score = read(target)
    score['row']['coordinates_binary64_hex'][0][0] = 123.0.hex()
    reseal(score)
    write(target, score)
    with pytest.raises(ResearchError):
        workflow.verify_output(req, tmp_path / 'run')
