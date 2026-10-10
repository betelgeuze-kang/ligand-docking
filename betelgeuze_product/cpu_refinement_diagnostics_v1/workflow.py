"""Offline sidecars over verified retained trials; never start/resume a solver.

The original run remains locked during snapshot diagnostics. A new external
output directory reserves each diagnostic before evaluation. Interrupted work
is retained, never automatically resumed/retried. No solver evidence is written.
"""
import argparse
import json
import os
import stat
from pathlib import Path

from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as budget
from betelgeuze_product.cpu_refinement_shape_v1 import cartesian as shape
from betelgeuze_product.cpu_refinement_v1_2.provenance import canonical, digest
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.journal import TrialJournal
from .contracts import (BOUNDARY, RECORD_SCHEMA, SCHEMA, DiagnosticConfig, empty_work,
                        implementation_sources, require)
from .evaluation import diagnose_observation


def _selection(events, state, config):
    accepted = []
    accepted_index = 0
    counts = {'objective_finished': 0, 'rejected': 0, 'failed': 0, 'restart_finished': 0}
    for event in events:
        if event['kind'] == 'restart_finished':
            counts['restart_finished'] += 1
        if event['kind'] != 'objective_finished':
            continue
        counts['objective_finished'] += 1
        payload = event['payload']
        outcome = payload['decision']['outcome']
        if outcome not in ('initial', 'accepted'):
            counts['rejected'] += 1
            counts['failed'] += int(payload['observation'] is None)
            continue
        if outcome == 'accepted':
            accepted_index += 1
        observation = payload['observation']
        accepted.append({'observation': observation, 'observation_sha256': digest(observation),
                         'event_index': event['index'], 'event_sha256': event['event_sha256'],
                         'objective_attempt': payload['attempt'], 'accepted_step': accepted_index,
                         'phase_labels': []})
    endpoint = 'current_checkpoint' if state['status'] == 'running' else 'final'
    selected = []
    for index, row in enumerate(accepted):
        labels = row['phase_labels']
        if index == 0:
            labels.append('initial')
        if row['accepted_step'] and row['accepted_step'] % config.accepted_stride == 0:
            labels.append('intermediate')
        if index == len(accepted) - 1:
            require(row['observation_sha256'] == digest(state['current']), 'endpoint observation mismatch')
            labels.append(endpoint)
        if labels:
            selected.append(row)
    unavailable = []
    if not accepted:
        unavailable = [{'phase_labels': ['initial', endpoint], 'status': 'unavailable',
                        'reason': 'no_successful_retained_observation'}]
    require(len(selected) + len(unavailable) <= config.maximum_records,
            'diagnostic selection exceeds declared record capacity')
    return selected, unavailable, {**counts, 'accepted_observations': len(accepted),
                                  'selected_unique_observations': len(selected)}


class _OutputDirectory:
    """Confined exclusive sidecar publication through held no-follow dirfds."""
    def __init__(self, path):
        self.path = path
        self.fds = []
        self.chain = []
        self.fd = None

    def __enter__(self):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        parent = os.open('/', flags)
        self.fds.append(parent)
        try:
            for component in self.path.parts[1:-1]:
                child = os.open(component, flags, dir_fd=parent)
                self.fds.append(child)
                info = os.fstat(child)
                self.chain.append((parent, component, (info.st_dev, info.st_ino)))
                parent = child
            os.mkdir(self.path.name, mode=0o700, dir_fd=parent)
            os.fsync(parent)
            self.fd = os.open(self.path.name, flags, dir_fd=parent)
            self.fds.append(self.fd)
            info = os.fstat(self.fd)
            self.chain.append((parent, self.path.name, (info.st_dev, info.st_ino)))
            self.guard()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def guard(self):
        for parent, name, identity in self.chain:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == identity,
                    'diagnostic output directory changed')
        info = os.fstat(self.fd)
        require(info.st_uid == os.geteuid() and not info.st_mode & 0o077,
                'private owned diagnostic output directory required')

    def open_file(self, name):
        self.guard()
        require('/' not in name and name not in ('.', '..'), 'confined diagnostic filename required')
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        try:
            self.guard()
            os.fsync(self.fd)
        except BaseException:
            os.close(fd)
            raise
        return fd

    def write(self, name, value):
        raw = (canonical(value) + '\n').encode('ascii')
        require(len(raw) <= 256 * 1024 * 1024, 'diagnostic artifact capacity exceeded')
        fd = self.open_file(name)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        self.guard()
        os.fsync(self.fd)

    def __exit__(self, *args):
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds = []


def _append(stream, value):
    stream.write((canonical(value) + '\n').encode('ascii'))
    stream.flush()
    os.fsync(stream.fileno())


def _collect(original, config, evaluator, identity, run_dir, *, output_dir,
             diagnostic_config, source_result, source_manifest, result_schema,
             model_guard, profile=None):
    require(type(diagnostic_config) is DiagnosticConfig, 'explicit diagnostic config required')
    run_dir = Path(run_dir).absolute()
    output = Path(output_dir).absolute()
    require('..' not in output.parts, 'diagnostic output traversal forbidden')
    # Output is new and external to source evidence. Parent must already exist.
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    source_path = run_dir.resolve(strict=True)
    require(output != source_path and source_path not in output.parents,
            'diagnostic output must be outside original run evidence')
    diagnostic_sources = implementation_sources()
    with TrialJournal(run_dir, identity, create=False, profile=profile) as journal:
        machine, original_work, original_timings = execution._replay(journal, original, config, profile)
        verified = execution._result(journal, machine, original_work, original_timings,
                                     identity, result_schema, profile)
        require(canonical(verified) == canonical(source_result), 'source run changed since verification')
        saved = journal.result()
        if saved is not None:
            require(canonical(saved) == canonical(verified), 'source terminal result differs from replay')
        execution._intact(original, evaluator, identity, source_manifest, model_guard)
        selected, unavailable, coverage = _selection(journal.events, machine.snapshot(), diagnostic_config)
        source = {'binding_sha256': digest(identity), 'journal_sha256': journal.head_sha256,
                  'journal_count': journal.event_count,
                  'checkpoint_sha256': verified['checkpoint']['checkpoint_sha256'],
                  'snapshot_result_sha256': verified['result_sha256'],
                  'terminal_result_sha256': None if saved is None else saved['result_sha256'],
                  'source_system_sha256': canonical_system_sha256(original),
                  'solver_implementation_sha256': identity['implementation_sha256'],
                  'evaluator': evaluator.identity(), 'external_binding': identity['external_binding'],
                  'source_status': verified['status']}
        if profile is not None:
            source.update(shape_reference_sha256=identity['shape_reference_sha256'],
                          shape_contract_sha256=identity['shape_contract_sha256'])
        binding = {'schema_id': SCHEMA, 'source': source, 'config': diagnostic_config.to_dict(),
                   'diagnostic_sources': diagnostic_sources,
                   'diagnostic_implementation_sha256': digest(diagnostic_sources),
                   'runtime': identity['environment'], 'boundary': dict(BOUNDARY),
                   'units': {'coordinates': 'angstrom', 'energy': 'kcal/mol',
                             'force': 'kcal/mol/angstrom', 'angle': 'radian'}}
        with _OutputDirectory(output) as destination:
            destination.write('binding.json', binding)
            records = []
            work = empty_work()
            with os.fdopen(destination.open_file('events.jsonl'), 'wb') as stream:
                for index, row in enumerate(selected):
                    observation = row['observation']
                    ref = {name: value for name, value in row.items() if name != 'observation'}
                    _append(stream, {'kind': 'diagnostic_started', 'index': index,
                                     'observation_ref': ref, 'binding_sha256': digest(binding)})
                    record = diagnose_observation(original, evaluator, config, observation,
                        observation_ref=ref, diagnostic_config=diagnostic_config, shape_profile=profile)
                    journal.result()  # Recheck source storage after diagnostic arithmetic.
                    # Only this verified workflow can assert association with source evidence.
                    record.pop('record_sha256')
                    record['source_evidence_verified'] = True
                    record['record_sha256'] = digest(record)
                    destination.write(f'record-{index:05d}.json', record)
                    _append(stream, {'kind': 'diagnostic_finished', 'index': index,
                                     'record_sha256': record['record_sha256'], 'work': record['work']})
                    records.append(record)
                    for name in work:
                        work[name] += record['work'][name]
            for row in unavailable:
                record = {'schema_id': RECORD_SCHEMA, **row, 'work': empty_work()}
                records.append({**record, 'record_sha256': digest(record)})
            execution._intact(original, evaluator, identity, source_manifest, model_guard)
            journal.result()  # Guard all retained source storage before publication.
            require(implementation_sources() == diagnostic_sources, 'diagnostic implementation changed')
            evaluated = sum(row['status'] == 'evaluated' for row in records)
            report = {**binding, 'binding_sha256': digest(binding), 'coverage': coverage,
                      'records': records, 'status': 'complete' if evaluated == len(records) else 'not_complete',
                      'denominator': {'requested': len(records), 'evaluated': evaluated,
                                      'failed': sum(row['status'] == 'failed' for row in records),
                                      'parity_failed': sum(row['status'] == 'parity_failed' for row in records),
                                      'unavailable': len(unavailable)},
                      'diagnostic_work': work, 'original_solver_work': original_work,
                      'cost_semantics': 'diagnostic_only_excluded_from_solver_and_restart_budgets',
                      'internal_evaluator_gradient_count': 'not_instrumented; internal evaluator calls counted',
                      'unknown_pending_diagnostics': 0,
                      'rigid_projection': {'status': 'unavailable', 'reason': 'not_in_this_narrow_version'},
                      'stationarity': 'retained_original_criterion_unchanged'}
            report['report_sha256'] = digest(report)
            journal.result()
            destination.write('report.json', report)
            return report


def diagnose_budget_run(protocol_path, expected_sha256, run_dir, *, model, accepted_steps,
                        restart_verifications, output_dir, diagnostic_config=DiagnosticConfig()):
    """Verify a supported P1 run, then diagnose retained states without execution."""
    options = dict(model=model, accepted_steps=accepted_steps, restart_verifications=restart_verifications)
    source_result = budget.verify(protocol_path, expected_sha256, run_dir, **options)
    _, loaded = budget._read(protocol_path, expected_sha256, model, accepted_steps, restart_verifications)
    original, _, config, fixed, evaluator, identity = loaded
    return _collect(original, config, evaluator, identity, run_dir, output_dir=output_dir,
                    diagnostic_config=diagnostic_config, source_result=source_result,
                    source_manifest=budget.implementation_sources, result_schema=budget.RESULT_SCHEMA,
                    model_guard=fixed.assert_intact)


def diagnose_shape_run(system, parameters, config, *, fixed_environment, run_dir, binding,
                       base_profile, reference, strength, output_dir,
                       diagnostic_config=DiagnosticConfig()):
    """Explicit development API for a retained, admitted shape-profile run."""
    options = dict(fixed_environment=fixed_environment, run_dir=run_dir, binding=binding,
                   base_profile=base_profile, reference=reference, strength=strength)
    source_result = shape.verify_shape(system, parameters, config, **options)
    evaluator, identity, profile, sources, guard = shape._context(
        system, parameters, config, fixed_environment, binding,
        base_profile=base_profile, reference=reference, strength=strength)
    return _collect(system, config, evaluator, identity, run_dir, output_dir=output_dir,
                    diagnostic_config=diagnostic_config, source_result=source_result,
                    source_manifest=sources, result_schema=shape.RESULT_SCHEMA,
                    model_guard=guard, profile=profile)



def _read_document(path):
    from betelgeuze_product.comparison_receipts import _json, _regular_file
    raw = _regular_file(Path(path), 256 * 1024 * 1024)
    value = _json(raw)
    require(raw == (canonical(value) + '\n').encode('ascii'), 'noncanonical diagnostic artifact')
    return value


def _verify_sidecar(output_dir, expected_report_sha256, source_result, identity):
    """Authenticate against caller-retained digest and reverified source snapshot.

    This is serialization/provenance validation, not numerical reevaluation.
    A digest is integrity evidence, not independent scientific authentication.
    """
    from betelgeuze_product.cpu_refinement_v1_2.provenance import require_digest
    from betelgeuze_product.comparison_receipts import _regular_file, _json
    require_digest(expected_report_sha256)
    output = Path(output_dir)
    require(output.is_dir() and not output.is_symlink(), 'regular diagnostic directory required')
    report = _read_document(output / 'report.json')
    require(report.get('schema_id') == SCHEMA, 'diagnostic report schema mismatch')
    body = {key: value for key, value in report.items() if key != 'report_sha256'}
    require(report.get('report_sha256') == expected_report_sha256 == digest(body),
            'diagnostic report digest mismatch')
    require(report['boundary'] == BOUNDARY, 'diagnostic authority promotion forbidden')
    require(report['diagnostic_sources'] == implementation_sources(), 'diagnostic implementation changed')
    require(report['diagnostic_implementation_sha256'] == digest(implementation_sources()),
            'diagnostic implementation digest mismatch')
    require(report['source']['snapshot_result_sha256'] == source_result['result_sha256']
            and report['source']['binding_sha256'] == digest(identity), 'stale diagnostic source snapshot')
    binding = _read_document(output / 'binding.json')
    require(all(report.get(key) == value for key, value in binding.items())
            and report['binding_sha256'] == digest(binding), 'diagnostic binding mismatch')
    raw = _regular_file(output / 'events.jsonl', 256 * 1024 * 1024)
    events = []
    for line in raw.splitlines(keepends=True):
        row = _json(line)
        require(line == (canonical(row) + '\n').encode('ascii'), 'noncanonical diagnostic journal')
        events.append(row)
    records = report['records']
    selected = [row for row in records if row['status'] != 'unavailable']
    require(len(events) == 2 * len(selected), 'unfinished diagnostic work')
    names = {'binding.json', 'report.json', 'events.jsonl'}
    work = empty_work()
    for index, row in enumerate(selected):
        name = f'record-{index:05d}.json'
        names.add(name)
        require(_read_document(output / name) == row, 'diagnostic record differs from report')
        require(row['record_sha256'] == digest({k: v for k, v in row.items() if k != 'record_sha256'}),
                'diagnostic record digest mismatch')
        require(events[2 * index] == {'kind': 'diagnostic_started', 'index': index,
                    'observation_ref': row['observation_ref'], 'binding_sha256': digest(binding)}
                and events[2 * index + 1] == {'kind': 'diagnostic_finished', 'index': index,
                    'record_sha256': row['record_sha256'], 'work': row['work']},
                'diagnostic reservation/receipt mismatch')
        for key in work:
            require(type(row['work'][key]) is int and row['work'][key] >= 0, 'invalid diagnostic work')
            work[key] += row['work'][key]
    require({path.name for path in output.iterdir()} == names, 'unexpected diagnostic artifacts')
    require(work == report['diagnostic_work'] and report['unknown_pending_diagnostics'] == 0,
            'diagnostic work accounting mismatch')
    denominator = {'requested': len(records), **{name: sum(r['status'] == name for r in records)
                  for name in ('evaluated', 'failed', 'parity_failed', 'unavailable')}}
    require(report['denominator'] == denominator, 'diagnostic denominator mismatch')
    require(report['status'] == ('complete' if denominator['evaluated'] == len(records) else 'not_complete'),
            'diagnostic completion mismatch')
    return report


def verify_budget_sidecar(protocol_path, expected_sha256, run_dir, *, model, accepted_steps,
                          restart_verifications, output_dir, expected_report_sha256):
    """Force-free verification; requires the independently retained report digest."""
    options = dict(model=model, accepted_steps=accepted_steps, restart_verifications=restart_verifications)
    result = budget.verify(protocol_path, expected_sha256, run_dir, **options)
    _, loaded = budget._read(protocol_path, expected_sha256, model, accepted_steps, restart_verifications)
    report = _verify_sidecar(output_dir, expected_report_sha256, result, loaded[-1])
    require(budget.verify(protocol_path, expected_sha256, run_dir, **options) == result,
            'source run changed during sidecar verification')
    return report



def verify_shape_sidecar(system, parameters, config, *, fixed_environment, run_dir, binding,
                         base_profile, reference, strength, output_dir, expected_report_sha256):
    """Force-free verifier for explicitly admitted retained shape-profile evidence."""
    options = dict(fixed_environment=fixed_environment, run_dir=run_dir, binding=binding,
                   base_profile=base_profile, reference=reference, strength=strength)
    result = shape.verify_shape(system, parameters, config, **options)
    _, identity, _, _, _ = shape._context(system, parameters, config, fixed_environment, binding,
        base_profile=base_profile, reference=reference, strength=strength)
    report = _verify_sidecar(output_dir, expected_report_sha256, result, identity)
    require(shape.verify_shape(system, parameters, config, **options) == result,
            'source run changed during sidecar verification')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--model', choices=budget.MODELS, required=True)
    parser.add_argument('--accepted-steps', choices=budget.ACCEPTED_STEP_BUDGETS, type=int, required=True)
    parser.add_argument('--restart-verifications', choices=(0, 1), type=int, required=True)
    parser.add_argument('--accepted-stride', type=int, default=10)
    parser.add_argument('--maximum-records', type=int, default=256)
    parser.add_argument('--verify-report-sha256')
    args = parser.parse_args(argv)
    options = dict(model=args.model, accepted_steps=args.accepted_steps,
                   restart_verifications=args.restart_verifications, output_dir=args.output_dir)
    if args.verify_report_sha256 is not None:
        report = verify_budget_sidecar(args.protocol, args.protocol_sha256, args.run_dir,
            expected_report_sha256=args.verify_report_sha256, **options)
    else:
        report = diagnose_budget_run(args.protocol, args.protocol_sha256, args.run_dir,
            diagnostic_config=DiagnosticConfig(args.accepted_stride, args.maximum_records), **options)
    print(json.dumps({'schema_id': SCHEMA, 'status': report['status'],
                      'report_sha256': report['report_sha256'], 'denominator': report['denominator']},
                     sort_keys=True, allow_nan=False))
    return 0 if report['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
