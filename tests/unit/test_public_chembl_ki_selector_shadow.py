"""New synthetic Ki endpoint and native HTVS consumer controls; no assay labels."""
from copy import deepcopy
import csv
import hashlib
import json
import pytest
from rdkit import rdBase
from betelgeuze_engine.product import public_assay_selector_shadow as shadow

DIGEST = "c6e508e390df9d295ec53c9cc26f16a27c7ff5e31bf8f479e777f6c2e758049b"
BINDING = {'endpoint': 'Ki',
 'endpoint_subtype': 'enzyme_inhibition_Ki',
 'identity_context_sha256': '0d3371c5da43a0f07f02eee43d5327f352f0028a3c82c07d92dbb55bbd030b04',
 'implementation_hashes': {'chemical_identity': 'a1a900368821beb8b617796dc4189a9cbc1c8cc9ead90681380977088b79d45b',
                           'components': 'b437c37769c7c6e1f9833af03a656b2faf3d8429e08d49404b4e1ff9f5023b01',
                           'measurement': '83987579c318e2ecf5b210003b591606b5a0c0a82bf10010a15dbab955d5426e',
                           'normalizer': '7685a2ccfa1d9b6fb23750a01d382f2b0244be026c42c5817e226eded793b62e',
                           'reused_featurizer_and_metrics': '3df5839854abf24284ebbb71bf82635d8ccbc8405b0de8990a01a07854e45a26',
                           'trainer': '9437b41d3de95df8f1ac7576ac9e6e107e92da6fcf2f8c5aeaf0f63a3d0a4ab3'},
 'intake_scope_sha256': 'd4fc3754801d263781576db8dd4f2176ce402d507b371b5ed78619b422e503dc',
 'mean_baseline': 6.49811679504411,
 'ood_status': 'not_assessed',
 'physical_energy': False,
 'prediction_quantity': 'negative_log10_molar_Ki',
 'rdkit_version': '2026.03.6',
 'split_plan_sha256': '0f508a826cd363bcb1c2b958c5c0125a307262e7ea32c7afbdb2fa24d0ec2300',
 'target_annotation_sha256': 'd2725bf2131adcf8594e3ab8f2a446f4116a17b50ab8c34d799180bebff79351',
 'training_protocol_sha256': '1ae8f4dc3bdac10816eccd46646ac5e080e4fb249704aadbe0575cb8e635860c',
 'uncertainty': None}
FEATURES = {'available_at_stage': 'pre_docking',
 'bits': 1024,
 'include_chirality': True,
 'kind': 'Morgan_bit_vector',
 'radius': 2,
 'requires_target_structure': False,
 'target_encoding': 'one_catalogue_target_annotation_per_model_not_physical_state'}

def checkpoint(tmp_path, monkeypatch, change=None):
    binding = deepcopy(BINDING)
    binding['rdkit_version'] = rdBase.rdkitVersion
    payload = dict(binding, schema_version='public_chembl_cheap_selector_ridge_v2',
                   features=FEATURES, coefficients=[0.] * 1024, intercept=0.,
                   uncertainty_calibrated=False, product_ranking_enabled=False, customer_execution=False)
    if change:
        change(payload)
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    registry = dict(getattr(shadow, '_REGISTERED_CHEMBL_V2', {}))
    registry[digest] = binding
    monkeypatch.setattr(shadow, '_REGISTERED_CHEMBL_V2', registry, raising=False)
    path = tmp_path / 'synthetic-ki.json'
    path.write_bytes(raw)
    return path, digest


def row(**changes):
    return dict(dict(ligand_id='duplicate', smiles='CCCCC', endpoint='Ki',
                     endpoint_subtype='enzyme_inhibition_Ki',
                     target_annotation_sha256=BINDING['target_annotation_sha256']), **changes)


def test_real_ki_checkpoint_has_exact_archived_producer_registration():
    schema, binding = shadow._registration(DIGEST)
    assert schema == 'public_chembl_cheap_selector_ridge_v2'
    assert binding == BINDING


def test_ki_measured_zero_prediction_is_not_ic50_or_mean_fallback(tmp_path, monkeypatch):
    path, digest = checkpoint(tmp_path, monkeypatch)
    model = shadow.load_public_assay_selector(path, expected_sha256=digest)
    out = model.predict_rows([row(), row()])
    assert [r['predicted_value'] for r in out] == [0., 0.]
    assert [r['mean_baseline_value'] for r in out] == [BINDING['mean_baseline']] * 2
    assert all(r['prediction_quantity'] == 'negative_log10_molar_Ki' for r in out)
    assert all('predicted_negative_log10_molar_IC50' not in r for r in out)
    assert model.metadata['chemical_scope']['formal_charge_abs_max'] is None
    assert model.metadata['checkpoint_schema_version'] == 'public_chembl_cheap_selector_ridge_v2'
    assert all(model.metadata[k] is False for k in ['product_ranking_enabled', 'customer_execution', 'scientific_validation', 'uncertainty_calibrated'])


@pytest.mark.parametrize('changes,reason', [
    ({'endpoint': 'IC50'}, 'endpoint'), ({'endpoint': 'Kd'}, 'endpoint'),
    ({'endpoint_subtype': None}, 'endpoint_subtype'),
    ({'endpoint_subtype': 'enzyme_inhibition_IC50'}, 'endpoint_subtype'),
    ({'target_annotation_sha256': None}, 'target_annotation'),
    ({'target_annotation_sha256': 'P00742'}, 'target_annotation'),
    ({'is_ood': True}, 'declared_ood'), ({'is_ood': float('nan')}, 'invalid_ood'),
    ({'smiles': ''}, 'missing_smiles'), ({'smiles': 'CCCCC.[Na+]'}, 'multifragment'),
    ({'smiles': '[13CH3]CCCC'}, 'isotope'), ({'smiles': 'C1'}, 'invalid_smiles'),
])
def test_ki_unsupported_stays_null_and_preserves_duplicate_rows(tmp_path, monkeypatch, changes, reason):
    path, digest = checkpoint(tmp_path, monkeypatch)
    model = shadow.load_public_assay_selector(path, expected_sha256=digest)
    output = model.predict_rows([row(), row(**changes), row()])
    assert [r['row_index'] for r in output] == [0, 1, 2]
    assert [r['status'] for r in output] == ['evaluated', 'unsupported', 'evaluated']
    assert reason in output[1]['reason']
    assert output[1]['predicted_value'] is output[1]['mean_baseline_value'] is None
    assert all('predicted_negative_log10_molar_IC50' not in r for r in output)


@pytest.mark.parametrize('key', list(BINDING))
@pytest.mark.parametrize('mutation', ['missing', 'changed'])
def test_ki_archived_binding_cannot_be_dropped_or_relabelled(tmp_path, monkeypatch, key, mutation):
    def change(payload):
        if mutation == 'missing':
            payload.pop(key)
        else:
            payload[key] = 'incompatible'
    path, digest = checkpoint(tmp_path, monkeypatch, change)
    with pytest.raises(shadow.SelectorContractError, match='schema_keys_mismatch|binding_mismatch'):
        shadow.load_public_assay_selector(path, expected_sha256=digest)


def test_ki_preserves_original_unbounded_formal_charge_scope(tmp_path, monkeypatch):
    path, digest = checkpoint(tmp_path, monkeypatch)
    result = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([
        row(smiles='C[N+](C)(C)CC[N+](C)(C)CC[N+](C)(C)C')])[0]
    assert result['status'] == 'evaluated'


def test_ki_actual_htvs_hook_keeps_mapping_command_and_all_cells(tmp_path, monkeypatch):
    from betelgeuze_engine.product.runners import htvs_pipeline as pipeline
    path, digest = checkpoint(tmp_path, monkeypatch)
    csvpath = tmp_path / 'original.csv'
    rows = [row(), row(smiles=''), row()]
    with csvpath.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row()))
        writer.writeheader()
        writer.writerows(rows)
    original = csvpath.read_bytes()
    commands = []
    def child(command):
        commands.append(command)
        return {'ok': False, 'synthetic_stop_before_mapping': True}
    monkeypatch.setattr(pipeline, '_run_cmd', child)
    monkeypatch.setattr(pipeline, '_finalize_and_write', lambda _prefix, payload, _args: payload)
    prefix = tmp_path / 'htvs'
    base = ['--out-prefix', str(prefix), '--no-single-instance', '--no-auto-heavy-artifacts-root',
            '--no-reuse-stage1-if-exists', '--ligand-csv', str(csvpath)]
    pipeline.run_pipeline(pipeline.build_parser().parse_args(base))
    enabled = pipeline.run_pipeline(pipeline.build_parser().parse_args(base + [
        '--public-assay-shadow-enabled', '--public-assay-shadow-checkpoint', str(path),
        '--public-assay-shadow-checkpoint-sha256', digest]))
    assert commands[0] == commands[1]
    meta = enabled['stages']['stage1_ligand_mapping']['public_assay_selector_shadow']
    assert (meta['requested_rows'], meta['evaluated_rows'], meta['unsupported_rows']) == (3, 2, 1)
    saved = json.loads((tmp_path / 'htvs_public_assay_selector_shadow.json').read_text())
    assert [r['input_cells'] for r in saved['rows']] == [list(r.values()) for r in rows]
    assert all('predicted_negative_log10_molar_IC50' not in r for r in saved['rows'])
    assert csvpath.read_bytes() == original


@pytest.mark.parametrize('change,reason', [
    (lambda p: p.update(schema_version='public_chembl_cheap_selector_ridge_v1'), 'feature_contract'),
    (lambda p: p.update(features=shadow.FEATURES), 'feature_contract'),
    (lambda p: p.update(coefficients=[False] * 1024), 'coefficients'),
    (lambda p: p.update(intercept=float('inf')), 'coefficients'),
    (lambda p: p.update(customer_execution=True), 'capability'),
    (lambda p: p.update(product_ranking_enabled=True), 'capability'),
    (lambda p: p.update(uncertainty_calibrated=True), 'capability'),
])
def test_ki_no_schema_downgrade_nonfinite_or_capability_promotion(tmp_path, monkeypatch, change, reason):
    path, digest = checkpoint(tmp_path, monkeypatch, change)
    with pytest.raises(shadow.SelectorContractError, match=reason):
        shadow.load_public_assay_selector(path, expected_sha256=digest)
