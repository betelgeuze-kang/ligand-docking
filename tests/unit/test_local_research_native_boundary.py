"""New synthetic protocol tests; no public/holdout data or native qualification.

Stub native entrypoints exercise the *real* existing receipt owner, not a GPU.
The only actual child-native observation in CPU CI is extension unavailability.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest
from betelgeuze_product import native_backend_diagnostic as native
from betelgeuze_product import local_research_workflow as workflow
from betelgeuze_product import local_research_verify as verify
from tests.unit.test_engine_v2_native_fixed64_complete_pipeline import _input
from tests.unit.test_local_research_workflow import request

def _source(tmp_path, backend='hip_safe'):
    value = _input(consumer='cli')
    value['backend'] = backend
    value['device_ordinal'] = 0
    raw = json.dumps(value, sort_keys=True).encode()
    path = tmp_path / 'native-request.json'
    path.write_bytes(raw)
    return (path, raw, hashlib.sha256(raw).hexdigest())

def _evidence(backend):
    from betelgeuze_engine_v2.docking import native_fixed64_consumers as owner
    graph = {key: hashlib.sha256(key.encode()).hexdigest() for key in owner._RECEIPT_GRAPH_FIELDS}
    projection = hashlib.sha256(b'synthetic-projection').hexdigest()
    document = {'schema_id': owner._COMPLETE_EVIDENCE_SCHEMA_ID, 'consumer': 'cli', 'backend': backend, 'candidate_denominator': 64, 'denominator_preserved': True, 'evidence_display_authorized': True, 'operator_second_opinion_authorized': False, 'prepared_input_bounded': True, 'prepared_input_projection_sha256': projection, 'ligand_atom_count': 1, 'receptor_atom_count': 4, 'exact_cartesian_pair_count': 4, 'prepared_input_scalar_count': 100, 'prepared_input_scalar_limit': 8 * 1024 * 1024, 'receipt_graph': graph, 'consumer_view_receipt_sha256': hashlib.sha256(b'synthetic-cli').hexdigest(), 'scientific_projection_sha256': hashlib.sha256(b'synthetic-science').hexdigest()}
    document.update({key: graph[value] for key, value in owner._RECEIPT_GRAPH_ALIASES.items()})
    document['prepared_input_receipt_sha256'] = hashlib.sha256(owner._PREPARED_INPUT_RECEIPT_DOMAIN + bytes.fromhex(projection) + bytes.fromhex(document['pipeline_receipt_sha256'])).hexdigest()
    document.update({key: False for key in ('reservation_authorized', 'molecular_execution_authorized', 'existing_rank_auto_change_authorized', 'customer_pose_emission_authorized', 'production_claim_authorized', 'result_dependent_input_consumed', 'fallback_allowed', 'multi_anchor_consumed', 'benchmark_execution_authorized', 'scientific_claim_authorized')})
    document.update({key: 64 for key in native.COUNTS})
    document.update(typed_failure_count=0, post_rejected_count=0)
    document['candidates'] = [{'slot_index': i, 'post_refinement_geometric_admission': {'rank_eligible': True, 'receipt_sha256': 'a' * 64}, 'ranking': {'rank_eligible': True, 'valid_rank_eligible': True}, 'lineage': {'post_admission_row_receipt_sha256': 'a' * 64}} for i in range(64)]
    return document

@pytest.mark.parametrize('backend', native.BACKENDS)
def test_owned_native_receipt_and_requested_backend_are_preserved(tmp_path, monkeypatch, backend):
    from betelgeuze_engine_v2.docking import native_fixed64_consumers as owner
    _, raw, digest = _source(tmp_path, backend)
    original = json.loads(raw)
    marker = tmp_path / 'stub-extension'
    marker.write_bytes(b'synthetic-extension-stub-not-native')
    extension_digest = native._file_digest(marker)
    monkeypatch.setattr(native, '_load_native', lambda: (marker, extension_digest))
    calls = []

    def entrypoint(payload):
        calls.append(copy.deepcopy(payload))
        return _evidence(backend)
    monkeypatch.setattr(owner, '_native_entrypoint', lambda: entrypoint)
    result = native._execute(raw, backend, 0)
    assert result['status'] == 'native_pipeline_completed', result
    assert result['backend_observed'] == backend
    assert result['candidate_denominator'] == 64
    assert result['counts']['scored_count'] == 64
    assert calls == [original] and json.loads(raw) == original
    assert native._packet(json.dumps(result).encode(), backend, 0, digest) == result
    assert all((result[key] is False for key in native.FLAGS))

@pytest.mark.parametrize('change', ['backend', 'authority', 'rows', 'counts', 'receipt'])
def test_existing_native_owner_rejects_bad_evidence(tmp_path, monkeypatch, change):
    from betelgeuze_engine_v2.docking import native_fixed64_consumers as owner
    _, raw, _ = _source(tmp_path)
    marker = tmp_path / 'stub'
    marker.write_bytes(b'not-native')
    monkeypatch.setattr(native, '_load_native', lambda: (marker, native._file_digest(marker)))
    result = _evidence('hip_safe')
    if change == 'backend':
        result['backend'] = 'rust_cpu'
    elif change == 'authority':
        result['molecular_execution_authorized'] = True
    elif change == 'rows':
        result['candidates'].pop()
    elif change == 'counts':
        result['generated_count'] = 2
    else:
        result['pipeline_receipt_sha256'] = 'f' * 64
    monkeypatch.setattr(owner, '_native_entrypoint', lambda: lambda request: result)
    observed = native._execute(raw, 'hip_safe', 0)
    assert observed['status'] == 'native_request_rejected'
    assert observed['backend_observed'] is None and observed['native_pipeline_completed'] is False

@pytest.mark.parametrize('change', ['schema', 'test_only', 'device', 'boolean_device', 'backend', 'consumer', 'extra_key'])
def test_unadmitted_request_never_loads_native(tmp_path, monkeypatch, change):
    _, raw, _ = _source(tmp_path)
    value = json.loads(raw)
    if change == 'schema':
        value['schema_id'] = 'legacy'
    elif change == 'test_only':
        value['test_only'] = False
    elif change == 'device':
        value['device_ordinal'] = 1
    elif change == 'boolean_device':
        value['device_ordinal'] = False
    elif change == 'backend':
        value['backend'] = 'rust_cpu'
    elif change == 'consumer':
        value['consumer'] = 'api'
    else:
        value['extra'] = 1
    monkeypatch.setattr(native, '_load_native', lambda: pytest.fail('unadmitted input loaded native'))
    result = native._execute(json.dumps(value).encode(), 'hip_safe', 0)
    assert result['status'] == 'request_rejected'

@pytest.mark.parametrize('kind', ['digest', 'duplicate', 'nonfinite', 'oversized', 'fifo', 'symlink'])
def test_input_errors_do_not_spawn_or_disclose_private_data(tmp_path, monkeypatch, kind):
    path, raw, digest = _source(tmp_path)
    if kind == 'digest':
        digest = '0' * 64
    elif kind == 'duplicate':
        raw = raw[:-1] + b',"backend":"hip_safe"}'
        path.write_bytes(raw)
    elif kind == 'nonfinite':
        raw = raw.replace(b'0.2', b'NaN')
        path.write_bytes(raw)
    elif kind == 'oversized':
        path.write_bytes(b' ' * (native.MAX_REQUEST_BYTES + 1))
    elif kind == 'fifo':
        path.unlink()
        os.mkfifo(path)
    else:
        original = path.with_name('original.json')
        path.rename(original)
        path.symlink_to(original)
    if kind not in {'digest', 'fifo', 'symlink'}:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *a, **k: pytest.fail('invalid input spawned'))
    result = native.observe_native_request(path, expected_sha256=digest, backend='hip_safe')
    assert result['status'] == 'request_rejected'
    assert str(tmp_path) not in json.dumps(result)

def _stub(monkeypatch, code):
    monkeypatch.setattr(native, '_command', lambda inp, out, backend, device: [sys.executable, '-S', '-c', code, str(inp), str(out)])

@pytest.mark.parametrize('kind', ['timeout', 'abort', 'malformed', 'overlong', 'bad_backend'])
def test_isolated_worker_failure_keeps_no_fallback(tmp_path, monkeypatch, kind):
    path, _, digest = _source(tmp_path)
    if kind == 'timeout':
        code = 'import time;time.sleep(20)'
    elif kind == 'abort':
        code = 'import os,resource;resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.abort()'
    elif kind == 'malformed':
        code = "import os,sys;os.write(int(sys.argv[2]),b'not-json')"
    elif kind == 'overlong':
        code = f"import os,sys;os.write(int(sys.argv[2]),b'x'*{native.MAX_RECEIPT_BYTES + 1})"
    else:
        data = native._empty('rust_cpu', 0, digest)
        data['status'] = 'native_request_rejected'
        code = f'import os,sys;os.write(int(sys.argv[2]),{json.dumps(data).encode()!r})'
    _stub(monkeypatch, code)
    result = native.observe_native_request(path, expected_sha256=digest, backend='hip_safe', timeout_seconds=0.3)
    assert result['exit_code'] == 2 and result['backend_observed'] is None
    assert result['native_pipeline_completed'] is False
    assert result['cleanup'] == 'child_reaped'
    if kind == 'timeout':
        assert result['status'] == 'native_probe_timeout'
    elif kind == 'abort':
        assert result['status'] == 'native_probe_process_failed'
    else:
        assert result['status'] == 'native_probe_failed'

def test_actual_subprocess_checks_compiled_extension_without_parent_engine_import(tmp_path):
    path, _, digest = _source(tmp_path)
    code = 'import json,sys\nbefore=set(sys.modules)\nfrom betelgeuze_product.native_backend_diagnostic import observe_native_request\nresult=observe_native_request(sys.argv[1],expected_sha256=sys.argv[2],backend="hip_safe",timeout_seconds=10)\nassert result["status"]=="native_extension_unavailable",result\nadded=set(sys.modules)-before\nassert not any(n.split(\'.\')[0] in {"torch","numpy","rdkit","betelgeuze_engine_v2","betelgeuze_engine_v2_native"} for n in added)\nprint(json.dumps(result))\n'
    result = subprocess.run([sys.executable, '-c', code, str(path), digest], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['backend_observed'] is None and receipt['native_backend_qualified'] is False

@pytest.mark.parametrize('option,value', [('device_ordinal', True), ('device_ordinal', -1), ('device_ordinal', 64), ('timeout_seconds', 0), ('timeout_seconds', float('nan')), ('timeout_seconds', 121), ('timeout_seconds', True), ('backend', 'cuda'), ('expected_sha256', 'g' * 64)])
def test_bad_native_diagnostic_options_are_rejected(option, value):
    kwargs = dict(backend='hip_safe', expected_sha256='0' * 64)
    kwargs[option] = value
    with pytest.raises(ValueError):
        native.observe_native_request(Path('missing'), **kwargs)

def test_unified_cli_native_mode_is_separate_from_research(tmp_path, capsys):
    path, _, digest = _source(tmp_path)
    code = workflow.main(['--diagnose-native', '--native-request', str(path), '--native-sha256', digest, '--native-backend', 'hip_safe'])
    assert code == 2
    observed = json.loads(capsys.readouterr().out)
    assert observed['status'] == 'native_extension_unavailable'
    assert observed['prepared_physics_backend_changed'] is False
    with pytest.raises(SystemExit):
        workflow.main(['--diagnose-native', '--native-request', str(path), '--native-sha256', digest, '--native-backend', 'hip_safe', '--run-dir', str(tmp_path / 'run')])
    assert not (tmp_path / 'run').exists()
    with pytest.raises(SystemExit):
        workflow.main(['--native-timeout', '1', '--diagnose-only'])

@pytest.mark.parametrize('field', ['energy', 'pose_id', 'cost', 'source_binding', 'remove_policy'])
def test_completion_marker_detects_summary_only_corruption(tmp_path, field):
    run = tmp_path / 'run'
    workflow.run_workflow(request(tmp_path), run_dir=run)
    assert verify.verify_run(run)['summary_receipt_verified'] is True
    report_file = run / 'attempt-000001/report.json'
    data = json.loads(report_file.read_text())
    if field == 'energy':
        data['physics']['poses'][0]['cross_energy_kcal_per_mol'] += 123.0
    elif field == 'pose_id':
        data['physics']['poses'][0]['pose_id'] = 'different-pose'
    elif field == 'cost':
        data['cost']['wall_seconds'] += 10.0
    elif field == 'remove_policy':
        del data['publication_policy']
    else:
        report_file = run / 'request.json'
        data = json.loads(report_file.read_text())
        data['workflow_source_sha256'] = 'f' * 64
    report_file.write_text(json.dumps(data))
    result = verify.verify_run(run)
    assert result['status'] == 'invalid', result
    assert str(tmp_path) not in json.dumps(result)

def test_final_report_without_completion_marker_is_incomplete(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    real = workflow._atomic

    def interrupted(path, text):
        if path.name == 'complete.json':
            raise KeyboardInterrupt('publication interrupted')
        return real(path, text)
    with monkeypatch.context() as patch:
        patch.setattr(workflow, '_atomic', interrupted)
        with pytest.raises(KeyboardInterrupt):
            workflow.run_workflow(request(tmp_path), run_dir=run)
    result = verify.verify_run(run)
    assert result['status'] == 'incomplete'
    assert result['reason'] == 'missing_final_completion_receipt'
    from betelgeuze_engine.product import prepared_rigid_poses as poses
    monkeypatch.setattr(poses, 'evaluate_prepared_cross_interaction', lambda *a, **k: pytest.fail('recomputed'))
    result = workflow.run_workflow(json.loads((run / 'request.json').read_text())['request'], run_dir=run, resume=True)
    assert result['attempt'] == 2 and result['backend_executed'] is None
    assert verify.verify_run(run)['status'] == 'intact'
    assert verify.verify_run(run, attempt=1)['status'] == 'incomplete'

@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo', 'duplicate', 'oversized', 'wrong_attempt'])
def test_bad_completion_marker_is_read_only_and_rejected(tmp_path, kind):
    run = tmp_path / 'run'
    workflow.run_workflow(request(tmp_path), run_dir=run)
    path = run / 'attempt-000001/complete.json'
    original = path.read_bytes()
    if kind in {'symlink', 'hardlink', 'fifo'}:
        path.unlink()
        outside = tmp_path / 'outside'
        outside.write_bytes(original)
        if kind == 'symlink':
            path.symlink_to(outside)
        elif kind == 'hardlink':
            os.link(outside, path)
        else:
            os.mkfifo(path)
    elif kind == 'duplicate':
        path.write_bytes(original.rstrip()[:-1] + b',"attempt":1}')
    elif kind == 'oversized':
        path.write_bytes(b' ' * 4097)
    else:
        data = json.loads(original)
        data['attempt'] = True
        path.write_text(json.dumps(data))
    before = os.lstat(path)
    result = verify.verify_run(run)
    assert result['status'] == 'invalid', result
    after = os.lstat(path)
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)

def test_native_subprocess_timeout_kills_descendants(tmp_path, monkeypatch):
    path, _, digest = _source(tmp_path)
    pidfile = tmp_path / 'pid'
    code = f"import subprocess,sys,time;child=subprocess.Popen([sys.executable,'-S','-c','import time;time.sleep(30)']);open({str(pidfile)!r},'w').write(str(child.pid));time.sleep(30)"
    _stub(monkeypatch, code)
    result = native.observe_native_request(path, expected_sha256=digest, backend='hip_safe', timeout_seconds=0.5)
    assert result['status'] == 'native_probe_timeout'
    pid = int(pidfile.read_text())
    for _ in range(100):
        try:
            state = Path(f'/proc/{pid}/stat').read_text().split(')', 1)[1].split()[0]
        except FileNotFoundError:
            break
        if state == 'Z':
            break
        time.sleep(0.01)
    else:
        os.kill(pid, signal.SIGKILL)
        pytest.fail('diagnostic descendant remained alive')
