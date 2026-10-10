"""Real subprocess/P3-journal integration with explicitly synthetic arithmetic."""
import json

import pytest
import torch

from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow as comparison
from betelgeuze_product.cpu_refinement_v1_2.provenance import canonical, ResearchError
from betelgeuze_product.cpu_shape_comparison_supervisor_v1 import supervisor, worker, synthetic
from betelgeuze_product.cpu_shape_comparison_supervisor_v1.limits import Limits
from tests.unit.test_cpu_prepared_shape_comparison_cartesian import values, budget, files, _forbidden


_SYNTHETIC_BASE_CALLS = 0
_SYNTHETIC_DIAGNOSTIC_RECORDS = 0


def prepared_plan(tmp_path):
    torch.set_num_threads(1)
    ligand, parameters, config, fixed, binding = values()
    raw = {'ligand': canonical_system_json_bytes(ligand),
           'receptor': canonical_system_json_bytes(fixed.receptor),
           'parameters': canonical(parameters.to_dict()).encode(),
           'cross': canonical(fixed.cross.to_dict()).encode(),
           'source_evidence': canonical({
               'schema_version': 'declared_prepared_source_evidence/1.0.0',
               'evidence_kind': 'synthetic_control', 'source_files': [],
               'source_authenticated': False,
               'original_simulation_hamiltonian_reproduced': False}).encode()}
    paths = {}
    for name, content in raw.items():
        paths[name] = tmp_path / (name + '.json')
        paths[name].write_bytes(content)
    prepared = budget.prepare(model='fourier', accepted_steps=40, restart_verifications=0,
        candidate_id=binding['candidate_id'], evidence_kind='synthetic_control',
        solver=config, output=tmp_path / 'prepared.json', **paths)
    return comparison.prepare(prepared['protocol_path'], prepared['protocol_sha256'],
                              tmp_path / 'plan', model='fourier')


@pytest.mark.parametrize('arm', ['B0', 'B1', 'B2'])
def test_subprocess_runs_real_p3_worker_with_synthetic_arithmetic(tmp_path, monkeypatch, arm):
    plan = prepared_plan(tmp_path)
    request = {'mode': 'synthetic_control', 'behavior': 'prepared_analytic',
               'plan_path': plan['plan_path'], 'plan_sha256': plan['plan_sha256'], 'arm': arm}
    limits = Limits(wall_seconds=30, cpu_seconds=30, write_reservations=120,
                    file_bytes=2 * 1024 * 1024, directory_reservations=16)
    receipt = supervisor.run_arm(request, tmp_path / 'supervised', limits=limits)
    assert receipt['status'] == 'finished', receipt
    global _SYNTHETIC_BASE_CALLS, _SYNTHETIC_DIAGNOSTIC_RECORDS
    row = receipt['worker_result']['row']
    _SYNTHETIC_BASE_CALLS += (row['work']['evaluation_work']['force_calls'] if arm == 'B0'
                              else row['work']['actual_force_calls'])
    _SYNTHETIC_DIAGNOSTIC_RECORDS += row['diagnostic_work']['internal_evaluator_calls']
    assert _SYNTHETIC_BASE_CALLS <= 512
    assert row['schema_id'] == worker.SCHEMA
    assert row['arm'] == arm and row['result_sha256'] is not None
    assert row['status'] != 'failed_or_unknown'
    assert row['plan_sha256'] == plan['plan_sha256']
    assert row['diagnostic_status'] == ('evaluated' if arm == 'B0' else 'complete')
    if arm == 'B0':
        assert row['work']['optimizer_force_calls'] == 0
        assert row['work']['evaluation_work']['force_calls'] == 1
    else:
        assert 0 < row['work']['actual_force_calls'] <= 161
        assert row['work']['restart_verification_attempts'] == 0
        assert row['work']['optimizer_shape_calls'] == (
            0 if arm == 'B1' else row['work']['actual_force_calls'])
    assert row['diagnostic_work']['internal_evaluator_calls'] > 0
    assert not any(row['boundary'].values())
    before = files(tmp_path / 'supervised')
    monkeypatch.setattr(synthetic.execution, '_invoke', _forbidden)
    monkeypatch.setattr(synthetic.diagnostic_evaluation, 'diagnose_observation', _forbidden)
    monkeypatch.setattr(synthetic.diagnostic_workflow, 'diagnose_observation', _forbidden)
    assert worker.verify_arm(plan['plan_path'], plan['plan_sha256'], arm,
                             tmp_path / 'supervised' / 'work', row) == row
    assert supervisor.verify_supervised_arm(tmp_path / 'supervised', receipt['receipt_sha256']) == receipt
    assert files(tmp_path / 'supervised') == before
    target = next((tmp_path / 'supervised' / 'work' / 'diagnostics').glob('*.json'))
    document = json.loads(target.read_text())
    document['synthetic_tamper'] = True
    target.write_text(json.dumps(document))
    with pytest.raises((ResearchError, ValueError)):
        supervisor.verify_supervised_arm(tmp_path / 'supervised', receipt['receipt_sha256'])


def test_analytic_helper_rejects_nonsynthetic_preparation_before_mock_dispatch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(worker, '_load', lambda *args:
                        ({'preflight': {'evidence_kind': 'prepared_real_development'}}, None, None, None))
    monkeypatch.setattr(worker, 'execute_arm', lambda *args: calls.append(args))
    original = synthetic.execution._invoke
    with pytest.raises(ResearchError, match='synthetic-only'):
        synthetic.execute_analytic('unused', 'a' * 64, 'B1', tmp_path)
    assert calls == []
    assert synthetic.execution._invoke is original


def test_analytic_helper_restores_patches_on_interruption(tmp_path, monkeypatch):
    plan = prepared_plan(tmp_path)
    original = synthetic.execution._invoke
    evaluator = synthetic.FourierFixedEvaluator.evaluate

    def interrupted(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(worker, 'execute_arm', interrupted)
    with pytest.raises(KeyboardInterrupt):
        synthetic.execute_analytic(plan['plan_path'], plan['plan_sha256'], 'B1', tmp_path)
    assert synthetic.execution._invoke is original
    assert synthetic.FourierFixedEvaluator.evaluate is evaluator


def test_complete_four_arm_synthetic_comparison_is_supervised_and_source_bound(tmp_path, monkeypatch):
    global _SYNTHETIC_BASE_CALLS, _SYNTHETIC_DIAGNOSTIC_RECORDS
    plan = prepared_plan(tmp_path)
    limits = Limits(wall_seconds=30, cpu_seconds=30, write_reservations=120,
                    file_bytes=2 * 1024 * 1024, directory_reservations=16)
    output = tmp_path / 'complete-comparison'
    report = supervisor.run_synthetic_comparison(plan['plan_path'], plan['plan_sha256'], output,
                                                 limits=limits, total_wall_seconds=120)
    assert [r['arm'] for r in report['rows']] == ['B0', 'B1', 'B2', 'B3']
    assert report['denominator'] == {'planned': 4, 'finished': 4,
                                     'failed_or_unknown': 0, 'not_started': 0}, report
    assert report['plan_sha256'] == plan['plan_sha256']
    assert report['supervisor_sources'] == supervisor.sources()
    assert report['evidence_kind'] == 'synthetic_control'
    assert report['scientifically_validated'] is False
    assert report['report_sha256'] == supervisor.digest({
        k: v for k, v in report.items() if k != 'report_sha256'})
    assert json.loads((output / 'report.json').read_text()) == report
    before = files(output)
    monkeypatch.setattr(synthetic.execution, '_invoke', _forbidden)
    monkeypatch.setattr(synthetic.diagnostic_evaluation, 'diagnose_observation', _forbidden)
    monkeypatch.setattr(synthetic.diagnostic_workflow, 'diagnose_observation', _forbidden)
    for receipt in report['rows']:
        arm = receipt['arm']
        assert receipt['limits']['write_reservations'] == (16 if arm == 'B0' else 120)
        assert receipt['limits']['cpu_seconds'] == 30
        assert receipt['automatic_retry_performed'] is False
        assert receipt['unknown_work_is_not_zero'] is False
        result = receipt['worker_result']['row']
        assert result['arm'] == arm and result['plan_sha256'] == plan['plan_sha256']
        assert result['result_sha256'] is not None
        assert result['diagnostic_status'] == ('evaluated' if arm == 'B0' else 'complete')
        assert not any(result['boundary'].values())
        _SYNTHETIC_BASE_CALLS += (result['work']['evaluation_work']['force_calls'] if arm == 'B0'
                                  else result['work']['actual_force_calls'])
        _SYNTHETIC_DIAGNOSTIC_RECORDS += result['diagnostic_work']['internal_evaluator_calls']
        assert _SYNTHETIC_BASE_CALLS <= 512
        assert worker.verify_arm(plan['plan_path'], plan['plan_sha256'], arm,
                                 output / arm / 'work', result) == result
        assert supervisor.verify_supervised_arm(output / arm, receipt['receipt_sha256']) == receipt
    assert files(output) == before
