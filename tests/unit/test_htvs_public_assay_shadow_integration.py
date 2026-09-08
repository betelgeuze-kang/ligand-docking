"""Canonical HTVS entrypoint interception; no child molecular commands execute."""
from betelgeuze_engine.product.runners import htvs_pipeline as pipeline


def test_public_assay_shadow_cli_is_explicit_and_default_disabled():
    parser = pipeline.build_parser()
    assert parser.parse_args([]).public_assay_shadow_enabled is False
    args = parser.parse_args(['--public-assay-shadow-enabled',
                              '--public-assay-shadow-checkpoint', 'synthetic.json',
                              '--public-assay-shadow-checkpoint-sha256', 'a' * 64])
    assert args.public_assay_shadow_enabled is True
    assert args.public_assay_shadow_checkpoint == 'synthetic.json'
    assert args.public_assay_shadow_checkpoint_sha256 == 'a' * 64


def test_actual_entrypoint_writes_shadow_before_unchanged_mapping_command(tmp_path, monkeypatch):
    import csv
    import hashlib
    import json
    from rdkit import rdBase
    from betelgeuze_engine.product import public_assay_selector_shadow as shadow

    binding = dict(next(iter(shadow._APPROVED_V1.values())), rdkit_version=rdBase.rdkitVersion)
    payload = dict(binding, schema_version='public_assay_cheap_selector_ridge_v1',
                   features=shadow.FEATURES, coefficients=[0.] * 1024, intercept=2.5,
                   uncertainty_calibrated=False, product_ranking_enabled=False, customer_execution=False)
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(shadow._APPROVED_V1, digest, binding)
    checkpoint = tmp_path / 'synthetic.json'
    checkpoint.write_bytes(raw)
    requests = tmp_path / 'requests.csv'
    with requests.open('w') as stream:
        writer = csv.writer(stream)
        writer.writerow(['ligand_id', 'smiles', 'target_state_sha256', 'endpoint'])
        writer.writerows([['same', 'CCCCC', binding['target_state_sha256'], 'IC50'],
                         ['same', '', binding['target_state_sha256'], 'IC50'],
                         ['same', 'CCCCC', binding['target_state_sha256'], 'Ki']])
    request_bytes = requests.read_bytes()
    prefix = tmp_path / 'pipeline'
    sidecar = tmp_path / 'pipeline_public_assay_selector_shadow.json'
    commands = []
    expected_enabled = False

    def child(cmd):
        assert cmd[1] == 'tools/build_ligand_mapping_queue.py'
        assert sidecar.exists() == expected_enabled
        assert requests.read_bytes() == request_bytes
        assert cmd[cmd.index('--ligand-csv') + 1] == str(requests)
        commands.append(cmd)
        return {'ok': False, 'synthetic_stop_before_mapping': True}

    monkeypatch.setattr(pipeline, '_run_cmd', child)
    monkeypatch.setattr(pipeline, '_finalize_and_write', lambda _prefix, payload, _args: payload)
    base = ['--out-prefix', str(prefix), '--targets', 'caller_declared_target', '--no-single-instance',
            '--no-auto-heavy-artifacts-root', '--no-reuse-stage1-if-exists', '--ligand-csv', str(requests)]
    disabled = pipeline.run_pipeline(pipeline.build_parser().parse_args(base))
    assert 'public_assay_selector_shadow' not in disabled['stages']['stage1_ligand_mapping']
    expected_enabled = True
    enabled = pipeline.run_pipeline(pipeline.build_parser().parse_args(base + [
        '--public-assay-shadow-enabled', '--public-assay-shadow-checkpoint', str(checkpoint),
        '--public-assay-shadow-checkpoint-sha256', digest]))
    assert commands[0] == commands[1]
    assert enabled['failed_stage'] == 'stage1_ligand_mapping'
    meta = enabled['stages']['stage1_ligand_mapping']['public_assay_selector_shadow']
    assert (meta['requested_rows'], meta['evaluated_rows'], meta['unsupported_rows']) == (3, 1, 2)
    rows = json.loads(sidecar.read_text())['rows']
    assert [row['ligand_id'] for row in rows] == ['same'] * 3
    assert [row['predicted_negative_log10_molar_IC50'] for row in rows] == [2.5, None, None]
    assert checkpoint.read_bytes() == raw


def test_actual_entrypoint_retains_non_csv_unsupported_scope(tmp_path, monkeypatch):
    import json
    from betelgeuze_engine.product import public_assay_selector_shadow as shadow

    def forbidden(*args, **kwargs):
        raise AssertionError('non_csv_must_not_load_checkpoint')

    monkeypatch.setattr(shadow, 'load_public_assay_selector', forbidden)
    monkeypatch.setattr(pipeline, '_finalize_and_write', lambda _prefix, payload, _args: payload)
    prefix = tmp_path / 'sdf-only'
    sdf = tmp_path / 'unopened.sdf'
    sdf.write_text('synthetic unsupported input; do not parse')
    commands = []

    def child(command):
        assert command[1] == 'tools/build_ligand_mapping_queue.py'
        commands.append(command)
        return {'ok': False, 'synthetic_stop_before_mapping': True}

    monkeypatch.setattr(pipeline, '_run_cmd', child)
    base = ['--out-prefix', str(prefix), '--no-single-instance', '--no-auto-heavy-artifacts-root',
            '--no-reuse-stage1-if-exists', '--ligand-csv', '', '--ligand-sdf', str(sdf),
            '--public-assay-shadow-enabled']
    payload = pipeline.run_pipeline(pipeline.build_parser().parse_args(base))
    meta = payload['stages']['stage1_ligand_mapping']['public_assay_selector_shadow']
    assert meta['reason'] == 'unsupported_input_type:sdf_or_unspecified'
    assert meta['requested_rows'] is None and meta['unsupported_rows'] is None
    assert len(commands) == 1 and sdf.read_text() == 'synthetic unsupported input; do not parse'
    sidecar = json.loads((tmp_path / 'sdf-only_public_assay_selector_shadow.json').read_text())
    assert sidecar['rows'] == [] and sidecar['requested_rows'] is None
