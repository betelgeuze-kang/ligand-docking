"""Read-only sidecar integration with fabricated retained analytic observations.

No molecular optimization runs: journals are assembled from explicit single-
point fixture observations and deterministic state-machine transitions.
"""
import json
import os

import pytest
import torch

from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as budget
from betelgeuze_product.cpu_refinement_diagnostics_v1 import workflow, evaluation
from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import DiagnosticConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest, decode_coordinates
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.kernel import CartesianMachine, make_observation
from betelgeuze_product.cpu_refinement_v1_3.journal import TrialJournal
from tests.unit.test_cpu_prepared_cartesian_budget_v3 import _prepared, _files


@pytest.fixture(autouse=True)
def one_thread():
    before = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(before)


def retained(tmp_path, *, count=3, failure=False, pending=False, stationary=False, restart=False):
    sealed, options = _prepared(tmp_path, restart_verifications=int(restart))
    _, loaded = budget._read(sealed['protocol_path'], sealed['protocol_sha256'], **options)
    ligand, _, config, _, _, identity = loaded
    machine = CartesianMachine(ligand.coordinates, config)
    directory = tmp_path / 'run'
    with TrialJournal(directory, identity, create=True) as journal:
        for _ in range(count):
            intent = machine.next_intent()
            if intent is None:
                break
            journal.append('objective_started', intent)
            if pending:
                break
            xyz = decode_coordinates(intent['coordinates'], ligand.atom_count)
            energy = float((xyz * xyz).sum())
            force = torch.zeros_like(xyz) if stationary else -2 * xyz
            components = {'ligand_internal': energy, 'cross_lennard_jones': 0.,
                          'cross_screened_coulomb': 0., 'total': energy}
            observation = None if failure else make_observation(intent['attempt'], xyz, energy, force, components)
            outcome = machine.commit(intent, observation, failure='fatal' if failure else None)
            receipt = {'observation': observation, 'failure': 'fatal' if failure else None,
                       'error_type': 'SyntheticFailure' if failure else None,
                       'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': int(failure)},
                       'timings_ns': {'graph': 1, 'force': 1, 'objective': 2},
                       'attempt': intent['attempt'], 'decision': outcome,
                       'state_sha256': digest(machine.snapshot())}
            journal.append('objective_finished', receipt)
            journal.save_checkpoint(machine.snapshot())
            if restart and intent['attempt'] == 1 and not failure:
                journal.append('restart_started', execution._restart_intent(machine, 1))
                verification = {k: v for k, v in receipt.items() if k not in ('attempt', 'decision')}
                verification.update(verification=1, matched=True)
                journal.append('restart_finished', verification)
                journal.save_checkpoint(machine.snapshot())
    return sealed, options, directory


def call(sealed, options, directory, output, **kwargs):
    return workflow.diagnose_budget_run(sealed['protocol_path'], sealed['protocol_sha256'],
                                       directory, output_dir=output, **options, **kwargs)


def forbidden(*args, **kwargs):
    pytest.fail('solver execution or original publication forbidden')


def fake_diagnostic(original, evaluator, config, observation, *, observation_ref,
                    diagnostic_config, shape_profile):
    record = {'schema_id': workflow.RECORD_SCHEMA, 'status': 'evaluated',
              'observation_ref': observation_ref, 'observation_sha256': digest(observation),
              'coordinates_sha256': digest(observation['coordinates']),
              'work': workflow.empty_work(), 'source_evidence_verified': False}
    return {**record, 'record_sha256': digest(record)}


def test_sidecar_preserves_every_source_byte_and_selects_checkpoint(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=5)
    before = _files(directory)
    source_hash = digest(budget.implementation_sources())
    monkeypatch.setattr(workflow, 'diagnose_observation', fake_diagnostic)
    monkeypatch.setattr(execution, '_minimize_profile', forbidden)
    monkeypatch.setattr(execution, '_invoke', forbidden)
    monkeypatch.setattr(TrialJournal, 'append', forbidden)
    monkeypatch.setattr(TrialJournal, 'publish_result', forbidden)
    report = call(sealed, options, directory, tmp_path / 'diagnostic',
                  diagnostic_config=DiagnosticConfig(accepted_stride=2))
    assert report['status'] == 'complete'
    assert [r['observation_ref']['accepted_step'] for r in report['records']] == [0, 2, 4]
    assert report['records'][0]['observation_ref']['phase_labels'] == ['initial']
    assert report['records'][-1]['observation_ref']['phase_labels'] == ['intermediate', 'current_checkpoint']
    assert report['source']['terminal_result_sha256'] is None
    assert report['original_solver_work']['optimizer_objective_attempts'] == 5
    assert report['diagnostic_work'] == workflow.empty_work()
    assert _files(directory) == before
    assert digest(budget.implementation_sources()) == source_hash
    assert all(not value for value in report['boundary'].values())


def test_only_initial_endpoint_is_evaluated_once(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=1)
    monkeypatch.setattr(workflow, 'diagnose_observation', fake_diagnostic)
    report = call(sealed, options, directory, tmp_path / 'diagnostic')
    assert len(report['records']) == 1
    assert report['records'][0]['observation_ref']['phase_labels'] == ['initial', 'current_checkpoint']


def test_missing_initial_and_final_explicit_no_numerical_calls(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=1, failure=True)
    monkeypatch.setattr(workflow, 'diagnose_observation', forbidden)
    report = call(sealed, options, directory, tmp_path / 'diagnostic')
    assert report['status'] == 'not_complete'
    assert report['denominator'] == dict(requested=1, evaluated=0, failed=0, parity_failed=0, unavailable=1)
    assert report['records'][0]['phase_labels'] == ['initial', 'final']
    assert report['coverage']['failed'] == 1
    assert report['diagnostic_work'] == workflow.empty_work()


def test_pending_source_never_retried(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=1, pending=True)
    before = _files(directory)
    monkeypatch.setattr(workflow, 'diagnose_observation', forbidden)
    with pytest.raises(execution.PendingWorkError):
        call(sealed, options, directory, tmp_path / 'diagnostic')
    assert not (tmp_path / 'diagnostic').exists()
    assert before == _files(directory)


def test_capacity_and_in_source_output_fail_before_diagnostic(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=4)
    monkeypatch.setattr(workflow, 'diagnose_observation', forbidden)
    with pytest.raises(ResearchError, match='capacity'):
        call(sealed, options, directory, tmp_path / 'diagnostic',
             diagnostic_config=DiagnosticConfig(1, 2))
    assert not (tmp_path / 'diagnostic').exists()
    with pytest.raises(ResearchError, match='outside'):
        call(sealed, options, directory, directory / 'diagnostic')
    assert not (directory / 'diagnostic').exists()


def test_interruption_retains_started_receipt_and_cannot_overwrite(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=1)
    before = _files(directory)
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(workflow, 'diagnose_observation', interrupt)
    output = tmp_path / 'diagnostic'
    with pytest.raises(KeyboardInterrupt):
        call(sealed, options, directory, output)
    events = [json.loads(line) for line in (output / 'events.jsonl').read_text().splitlines()]
    assert [event['kind'] for event in events] == ['diagnostic_started']
    assert not (output / 'report.json').exists()
    with pytest.raises(FileExistsError):
        call(sealed, options, directory, output)
    assert _files(directory) == before


def test_real_single_point_diagnostics_detect_fabricated_retained_objective(tmp_path):
    sealed, options, directory = retained(tmp_path, count=1)
    before = _files(directory)
    report = call(sealed, options, directory, tmp_path / 'diagnostic')
    assert report['status'] == 'not_complete'
    assert report['records'][0]['status'] == 'parity_failed'
    assert report['diagnostic_work']['internal_evaluator_calls'] == 1
    assert report['diagnostic_work']['cross_passes'] == 1
    assert report['original_solver_work']['optimizer_force_calls'] == 1
    assert _files(directory) == before


@pytest.mark.parametrize('stride,capacity', [(True, 10), (0, 10), (1, False), (1, 0), (1, 1025)])
def test_config_strict_types_and_bounds(stride, capacity):
    with pytest.raises(ResearchError):
        DiagnosticConfig(stride, capacity)


def test_sidecar_verification_is_force_free_and_rejects_tampering(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=2)
    monkeypatch.setattr(workflow, 'diagnose_observation', fake_diagnostic)
    output = tmp_path / 'diagnostic'
    report = call(sealed, options, directory, output)
    monkeypatch.setattr(workflow, 'diagnose_observation', forbidden)
    monkeypatch.setattr(evaluation, 'split_cross', forbidden)
    monkeypatch.setattr(evaluation, 'build_compact_radius_graph', forbidden)
    before = _files(output)
    result = workflow.verify_budget_sidecar(sealed['protocol_path'], sealed['protocol_sha256'], directory,
        **options, output_dir=output, expected_report_sha256=report['report_sha256'])
    assert result == report
    assert before == _files(output)
    with pytest.raises(ResearchError, match='digest'):
        workflow.verify_budget_sidecar(sealed['protocol_path'], sealed['protocol_sha256'], directory,
            **options, output_dir=output, expected_report_sha256='0'*64)
    (output / 'record-00000.json').write_text('{}\n')
    with pytest.raises(ResearchError, match='record'):
        workflow.verify_budget_sidecar(sealed['protocol_path'], sealed['protocol_sha256'], directory,
            **options, output_dir=output, expected_report_sha256=report['report_sha256'])



def test_journal_tamper_during_diagnostic_prevents_verified_publication(tmp_path, monkeypatch):
    sealed, options, directory = retained(tmp_path, count=1)
    def tamper(*args, **kwargs):
        result = fake_diagnostic(*args, **kwargs)
        with (directory / 'events.jsonl').open('ab') as stream:
            stream.write(b'\n')
        return result
    monkeypatch.setattr(workflow, 'diagnose_observation', tamper)
    output = tmp_path / 'diagnostic'
    with pytest.raises(ResearchError):
        call(sealed, options, directory, output)
    assert not (output / 'report.json').exists()
    assert not (output / 'record-00000.json').exists()
    events = [json.loads(line) for line in (output / 'events.jsonl').read_text().splitlines()]
    assert [e['kind'] for e in events] == ['diagnostic_started']


def test_terminal_final_and_restart_verification_not_duplicate_samples(tmp_path, monkeypatch):
    terminal = tmp_path / 'terminal'
    terminal.mkdir()
    sealed, options, directory = retained(terminal, count=1, stationary=True)
    monkeypatch.setattr(workflow, 'diagnose_observation', fake_diagnostic)
    report = call(sealed, options, directory, terminal / 'diagnostic')
    assert report['records'][0]['observation_ref']['phase_labels'] == ['initial', 'final']
    assert report['source']['source_status'] == 'force_converged'
    resumed = tmp_path / 'resumed'
    resumed.mkdir()
    sealed, options, directory = retained(resumed, count=3, restart=True)
    report = call(sealed, options, directory, resumed / 'diagnostic')
    assert report['coverage']['restart_finished'] == 1
    assert report['coverage']['accepted_observations'] == 3
    assert report['coverage']['selected_unique_observations'] == 2
    assert report['original_solver_work']['restart_verification_attempts'] == 1



@pytest.mark.parametrize('when', ['after_mkdir', 'after_diagnostic'])
def test_output_swap_cannot_redirect_writes_into_source(tmp_path, monkeypatch, when):
    sealed, options, directory = retained(tmp_path, count=1)
    before = _files(directory)
    output = tmp_path / 'diagnostic'
    moved = tmp_path / 'moved-diagnostic'
    def swap():
        output.rename(moved)
        output.symlink_to(directory, target_is_directory=True)
    if when == 'after_mkdir':
        original_mkdir = os.mkdir
        def swapped_mkdir(path, *args, **kwargs):
            result = original_mkdir(path, *args, **kwargs)
            if path == output.name:
                swap()
            return result
        monkeypatch.setattr(os, 'mkdir', swapped_mkdir)
        monkeypatch.setattr(workflow, 'diagnose_observation', fake_diagnostic)
    else:
        def diagnostic(*args, **kwargs):
            result = fake_diagnostic(*args, **kwargs)
            swap()
            return result
        monkeypatch.setattr(workflow, 'diagnose_observation', diagnostic)
    with pytest.raises((OSError, ResearchError)):
        call(sealed, options, directory, output)
    assert _files(directory) == before
    assert not (directory / 'binding.json').exists()
    assert not (moved / 'report.json').exists()



@pytest.mark.parametrize('profile', ['fourier', 'linear_angle'])
def test_retained_shape_workflow_reuses_restraint_and_verifies_without_calls(tmp_path, monkeypatch, profile):
    from betelgeuze_product.cpu_refinement_shape_v1 import cartesian as shape
    from betelgeuze_product.cpu_refinement_shape_v1.profile import make_shape_observation
    from tests.unit.test_cpu_refinement_diagnostic_components import _admitted, _owning_point
    ligand, evaluator, config, binding = _admitted(profile)
    reference = shape.prepare_reference(ligand, binding)
    _, identity, owner, _, _ = shape._context(ligand, evaluator.parameters, config, evaluator.fixed,
        binding, base_profile=profile, reference=reference, strength=100.)
    base, _ = _owning_point(ligand, evaluator, config)
    observed = make_shape_observation(base, 0., torch.zeros_like(ligand.coordinates), 100.)
    machine = CartesianMachine(ligand.coordinates, config, profile=owner)
    intent = machine.next_intent()
    decision = machine.commit(intent, observed)
    directory = tmp_path / 'run'
    with TrialJournal(directory, identity, create=True, profile=owner) as journal:
        journal.append('objective_started', intent)
        journal.append('objective_finished', {
            'observation': observed, 'failure': None, 'error_type': None,
            'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0},
            'timings_ns': {'graph': 1, 'force': 1, 'objective': 2},
            'shape_work': {'base_force_calls': 1, 'failed_base_force_calls': 0,
                           'shape_calls': 1, 'failed_shape_calls': 0, 'augmented_observation_failures': 0},
            'attempt': 1, 'decision': decision, 'state_sha256': digest(machine.snapshot())})
        journal.save_checkpoint(machine.snapshot())
    before = _files(directory)
    monkeypatch.setattr(shape, '_calculate', forbidden)
    monkeypatch.setattr(execution, '_minimize_profile', forbidden)
    monkeypatch.setattr(execution, '_invoke', forbidden)
    options = dict(fixed_environment=evaluator.fixed, run_dir=directory, binding=binding,
                   base_profile=profile, reference=reference, strength=100., output_dir=tmp_path / 'diagnostic')
    report = workflow.diagnose_shape_run(ligand, evaluator.parameters, config, **options)
    assert report['status'] == 'complete'
    assert report['diagnostic_work']['retained_shape_reuses'] == 1
    assert report['source']['shape_reference_sha256'] == reference.digest
    monkeypatch.setattr(workflow, 'diagnose_observation', forbidden)
    assert workflow.verify_shape_sidecar(ligand, evaluator.parameters, config,
        expected_report_sha256=report['report_sha256'], **options) == report
    assert _files(directory) == before
