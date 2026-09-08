"""Fresh synthetic native-ChEMBL migration controls, without assay training."""
from __future__ import annotations
import csv
import hashlib
import json
from copy import deepcopy
import pytest
from rdkit import rdBase
from betelgeuze_engine.product import public_assay_selector_shadow as shadow

SCHEMA = "public_chembl_cheap_selector_ridge_v1"
FEATURES = {'available_at_stage': 'pre_docking', 'bits': 1024, 'include_chirality': True, 'kind': 'Morgan_bit_vector', 'radius': 2, 'requires_target_structure': False, 'target_encoding': 'one_catalogue_target_annotation_per_model_not_physical_state'}
BINDING = {'endpoint': 'IC50',
 'endpoint_subtype': 'enzyme_inhibition_IC50',
 'identity_context_sha256': '3accdbd3a19313fcee3366514d5165a29fb30d184c1a79cf691cdefaf2e59dbd',
 'implementation_hashes': {'chemical_identity': 'a1a900368821beb8b617796dc4189a9cbc1c8cc9ead90681380977088b79d45b',
                           'components': 'b437c37769c7c6e1f9833af03a656b2faf3d8429e08d49404b4e1ff9f5023b01',
                           'measurement': '83987579c318e2ecf5b210003b591606b5a0c0a82bf10010a15dbab955d5426e',
                           'normalizer': 'd69204740b5cd296343b3beff8f0959f1e0e6c9cc1ad32512421471259508765',
                           'reused_featurizer_and_metrics': '3df5839854abf24284ebbb71bf82635d8ccbc8405b0de8990a01a07854e45a26',
                           'trainer': '9ed664bb08ce681f9cd1919bdb513a9b90a896e4fee753cd97e35562cd836996'},
 'intake_scope_sha256': '39db885ef26fee8f4b360309e6ae35e9b97deb8cff6e5d5674357d3ea6883491',
 'mean_baseline': 5.5153571070070635,
 'ood_status': 'not_assessed',
 'physical_energy': False,
 'prediction_quantity': 'negative_log10_molar_IC50',
 'rdkit_version': '2026.03.6',
 'split_plan_sha256': 'ec80249b46e825f24029c8a097ab67497985b414f51fcd94e5495cd7efb11744',
 'target_annotation_sha256': '0ab0f219820e5b0e7b27c07731f35db19b1130863660c46b9e099435b958294f',
 'training_protocol_sha256': '995eb9935d7759642e1a5260879913969aaa51222a5e1237170dda259e294069',
 'uncertainty': None}


def _checkpoint(tmp_path, monkeypatch, change=None):
    binding = deepcopy(BINDING)
    binding['rdkit_version'] = rdBase.rdkitVersion
    payload = dict(binding, schema_version=SCHEMA, features=FEATURES,
                   coefficients=[0.] * 1024, intercept=0., uncertainty_calibrated=False,
                   product_ranking_enabled=False, customer_execution=False)
    if change:
        change(payload)
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    registry = dict(getattr(shadow, '_REGISTERED_CHEMBL_V1', {}))
    registry[digest] = binding
    monkeypatch.setattr(shadow, '_REGISTERED_CHEMBL_V1', registry, raising=False)
    path = tmp_path / 'synthetic-native.json'
    path.write_bytes(raw)
    return path, digest


def _row(**changes):
    row = dict(ligand_id='same', smiles='CCCCC', target_annotation_sha256=BINDING['target_annotation_sha256'],
               endpoint='IC50', endpoint_subtype='enzyme_inhibition_IC50')
    row.update(changes)
    return row


def test_native_zero_is_prediction_with_bound_mean_and_no_physical_state(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    model = shadow.load_public_assay_selector(path, expected_sha256=digest)
    out = model.predict_rows([_row(), _row()])
    assert len(out) == 2
    assert [x['predicted_negative_log10_molar_IC50'] for x in out] == [0., 0.]
    assert [x['mean_baseline_negative_log10_molar_IC50'] for x in out] == [BINDING['mean_baseline']] * 2
    assert all(x['declared_target_state_sha256'] is None for x in out)
    assert model.metadata['target_identity_basis'] == 'caller_declared_catalogue_target_annotation_not_physical_state'
    assert model.metadata['chemical_scope']['formal_charge_abs_max'] is None
    assert 'target_state_sha256' not in model.metadata
    assert model.metadata['features'] == FEATURES
    assert model.metadata['implementation_hashes'] == BINDING['implementation_hashes']
    assert model.metadata['product_ranking_enabled'] is False


@pytest.mark.parametrize('changes,reason', [
    ({'target_annotation_sha256': None}, 'target_annotation'),
    ({'target_annotation_sha256': '', 'target_state_sha256': BINDING['target_annotation_sha256']}, 'target_annotation'),
    ({'target_annotation_sha256': 'CHEMBL3038469'}, 'target_annotation'),
    ({'endpoint_subtype': None}, 'endpoint_subtype'),
    ({'endpoint_subtype': 'fluorescence_polarization_displacement'}, 'endpoint_subtype'),
    ({'endpoint': 'Ki'}, 'endpoint'), ({'endpoint': 'potential_energy'}, 'endpoint'),
    ({'is_ood': True}, 'declared_ood'), ({'is_ood': float('nan')}, 'invalid_ood'),
    ({'smiles': None}, 'missing_smiles'), ({'smiles': 'C1'}, 'invalid_smiles'),
    ({'smiles': 'CCCCC.[Na+]'}, 'multifragment'),
])
def test_native_unsupported_keeps_row_without_mean_fallback(tmp_path, monkeypatch, changes, reason):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    rows = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([_row(), _row(**changes), _row()])
    assert [r['status'] for r in rows] == ['evaluated', 'unsupported', 'evaluated']
    assert reason in rows[1]['reason']
    assert rows[1]['predicted_negative_log10_molar_IC50'] is None
    assert rows[1]['mean_baseline_negative_log10_molar_IC50'] is None


def test_native_preserves_predeclared_charge_scope(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    row = _row(smiles='C[N+](C)(C)CC[N+](C)(C)CC[N+](C)(C)C')
    result = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([row])[0]
    assert result['status'] == 'evaluated'
    assert result['smiles'] == row['smiles']


@pytest.mark.parametrize('key', list(BINDING))
@pytest.mark.parametrize('mutation', ['missing', 'changed'])
def test_native_exact_binding_cannot_be_dropped_or_relabelled(tmp_path, monkeypatch, key, mutation):
    def change(payload):
        if mutation == 'missing':
            payload.pop(key)
        else:
            payload[key] = 'incompatible'
    path, digest = _checkpoint(tmp_path, monkeypatch, change)
    with pytest.raises(shadow.SelectorContractError, match='schema_keys_mismatch|binding_mismatch'):
        shadow.PublicAssaySelectorShadow(path, digest)


@pytest.mark.parametrize('change,reason', [
    (lambda p: p.update(features=shadow.FEATURES), 'feature_contract'),
    (lambda p: p.update(schema_version='public_assay_cheap_selector_ridge_v2'), 'feature_contract'),
    (lambda p: p.update(coefficients=[False] * 1024), 'coefficients'),
    (lambda p: p.update(intercept=float('nan')), 'coefficients'),
    (lambda p: p.update(customer_execution=True), 'capability'),
    (lambda p: p.update(product_ranking_enabled=True), 'capability'),
    (lambda p: p.update(uncertainty_calibrated=True), 'capability'),
    (lambda p: p.update(target_state_sha256=BINDING['target_annotation_sha256']), 'schema_keys'),
])
def test_native_no_schema_downgrade_or_capability_promotion(tmp_path, monkeypatch, change, reason):
    path, digest = _checkpoint(tmp_path, monkeypatch, change)
    with pytest.raises(shadow.SelectorContractError, match=reason):
        shadow.load_public_assay_selector(path, expected_sha256=digest)


@pytest.mark.parametrize('old_header', [False, True])
def test_native_csv_contract_preserves_all_cells(tmp_path, monkeypatch, old_header):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    rows = [_row(), _row(smiles=''), _row()]
    if old_header:
        for row in rows:
            row['target_state_sha256'] = row.pop('target_annotation_sha256')
    csvpath = tmp_path / 'original.csv'
    with csvpath.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    original = csvpath.read_bytes()
    dest = tmp_path / 'sidecar.json'
    result = shadow.run_pre_docking_shadow(ligand_csv=str(csvpath), ligand_sdf='', docking_request_json='',
        resume_stage3_only=False, checkpoint=str(path), checkpoint_sha256=digest, output_json=str(dest))
    assert result['requested_rows'] == 3
    assert result['evaluated_rows'] == (0 if old_header else 2)
    assert result['unsupported_rows'] == (3 if old_header else 1)
    saved = json.loads(dest.read_text())
    assert [r['input_cells'] for r in saved['rows']] == [list(r.values()) for r in rows]
    assert csvpath.read_bytes() == original
    assert saved['prediction_scope'] == saved['model']['prediction_scope']


def test_native_actual_htvs_hook_keeps_mapping_command(tmp_path, monkeypatch):
    from betelgeuze_engine.product.runners import htvs_pipeline as pipeline
    path, digest = _checkpoint(tmp_path, monkeypatch)
    csvpath = tmp_path / 'original.csv'
    with csvpath.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(_row()))
        writer.writeheader()
        writer.writerows([_row(), _row(smiles=''), _row()])
    prefix = tmp_path / 'htvs'
    commands = []
    def child(command):
        commands.append(command)
        return {'ok': False, 'synthetic_stop_before_mapping': True}
    monkeypatch.setattr(pipeline, '_run_cmd', child)
    monkeypatch.setattr(pipeline, '_finalize_and_write', lambda _prefix, payload, _args: payload)
    base = ['--out-prefix', str(prefix), '--no-single-instance', '--no-auto-heavy-artifacts-root',
            '--no-reuse-stage1-if-exists', '--ligand-csv', str(csvpath)]
    pipeline.run_pipeline(pipeline.build_parser().parse_args(base))
    enabled = pipeline.run_pipeline(pipeline.build_parser().parse_args(base + ['--public-assay-shadow-enabled',
        '--public-assay-shadow-checkpoint', str(path), '--public-assay-shadow-checkpoint-sha256', digest]))
    assert commands[0] == commands[1]
    meta = enabled['stages']['stage1_ligand_mapping']['public_assay_selector_shadow']
    assert (meta['requested_rows'], meta['evaluated_rows'], meta['unsupported_rows']) == (3, 2, 1)
    assert meta['product_ranking_enabled'] is False


def test_unavailable_model_has_no_inferred_chemical_or_target_scope():
    contract = shadow._contract()
    assert contract['chemical_scope'] is None
    assert contract['target_identity_basis'] is None
    assert contract['mean_baseline_evidence_kind'] is None
