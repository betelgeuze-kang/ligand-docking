"""Synthetic contract controls
    real V2 arithmetic, explicit fake selector only."""
import copy
import json
from types import SimpleNamespace

import pytest

from tools.product import score_prepared_cross_interactions as consumer
from tests.unit.test_score_prepared_cross_interactions import _case, _prepared, _assert_scalar_pair

SCHEMA = 'prepared_cross_interaction_with_assay_shadow_request_v1'


def request(tmp_path):
    case = _case(_prepared(tmp_path / 'sources'))
    case['assay_metadata'] = {'smiles': 'c1ccccc1', 'endpoint': 'Ki',
        'role': 'fit', 'source_provenance': {'split': 'calibration', 'evaluation_only': True},
        'target_annotation_sha256': 'catalogue-only', 'source_zero': 0}
    return {'schema_version': SCHEMA, 'cases': [case],
            'assay_selector': {'checkpoint': 'synthetic', 'checkpoint_sha256': '0' * 64}}


def fake_selector(monkeypatch, *, fail=False):
    from betelgeuze_engine.product import public_assay_selector_shadow as selector
    seen = []
    def load(*args, **kwargs):
        if fail:
            raise ValueError('explicit unavailable checkpoint')
        def predict(rows):
            seen.extend(copy.deepcopy(rows))
            return [{'row_index': i, 'status': 'evaluated', 'reason': None,
                     'prediction_quantity': 'negative_log10_molar_Ki',
                     'predicted_value': 0.0, 'mean_baseline_value': 0.0,
                     'uncertainty': None, 'ood_status': 'not_assessed'} for i, row in enumerate(rows)]
        return SimpleNamespace(predict_rows=predict, metadata={'synthetic_test_only': True})
    monkeypatch.setattr(selector, 'load_public_assay_selector', load)
    return seen


def test_optional_shadow_executes_existing_physics_preserves_zero_and_original_roles(tmp_path, monkeypatch):
    seen = fake_selector(monkeypatch)
    req = request(tmp_path)
    before = copy.deepcopy(req)
    result = consumer.evaluate_request(req)
    assert req == before and seen == [req['cases'][0]['assay_metadata']]
    row = result['rows'][0]
    _assert_scalar_pair(row['result'])
    shadow = row['assay_selector_shadow']
    assert shadow['prediction']['predicted_value'] == 0.0
    assert shadow['input_metadata'] == req['cases'][0]['assay_metadata']
    assert shadow['same_prepared_or_assay_state_verified'] is False
    assert shadow['combined_score'] is None and shadow['residual_training_eligible'] is False
    assert result['assay_selector_shadow']['denominator'] == {
        'requested_cases': 1, 'evaluated': 1, 'unsupported': 0, 'not_requested': 0}


@pytest.mark.parametrize('mode', ['missing', 'invalid', 'model_failed', 'case_invalid', 'preparation_failed'])
def test_independent_failure_denominators_and_no_id_join(tmp_path, monkeypatch, mode):
    fake_selector(monkeypatch, fail=mode == 'model_failed')
    req = request(tmp_path)
    req['cases'].append(copy.deepcopy(req['cases'][0]))
    if mode == 'missing':
        req['cases'][1].pop('assay_metadata')
    elif mode == 'invalid':
        req['cases'][1]['assay_metadata'] = None
    elif mode == 'case_invalid':
        req['cases'][1]['unexpected'] = True
    elif mode == 'preparation_failed':
        req['cases'][1]['prepared_input']['ligand_gro']['sha256'] = 'f' * 64
    out = consumer.evaluate_request(req)
    assert [r['request_index'] for r in out['rows']] == [0, 1]
    assert len({r['case_id'] for r in out['rows']}) == 1
    for row in out['rows']:
        if row['status'] == 'evaluated':
            _assert_scalar_pair(row['result'])
    assert out['denominator']['failed'] == int(mode in {'case_invalid', 'preparation_failed'})
    sd = out['assay_selector_shadow']['denominator']
    assert sd['requested_cases'] == sum(sd[k] for k in ['evaluated', 'unsupported', 'not_requested']) == 2
    assert sd['evaluated'] == (0 if mode == 'model_failed' else 1 if mode in {'missing','invalid'} else 2)


def test_v1_does_not_load_selector_or_accept_shadow_fields(tmp_path, monkeypatch):
    fake_selector(monkeypatch, fail=True)
    req = request(tmp_path)
    req.pop('assay_selector')
    req['schema_version'] = consumer.SCHEMA
    out = consumer.evaluate_request(req)
    assert out['denominator']['failed'] == 1
    req['cases'][0].pop('assay_metadata')
    out = consumer.evaluate_request(req)
    assert out['denominator']['evaluated'] == 1
    assert 'assay_selector_shadow' not in out


def test_real_module_cli_preserves_physics_when_registered_model_unavailable(tmp_path):
    req = request(tmp_path)
    source, output = tmp_path/'request.json', tmp_path/'report.json'
    source.write_text(json.dumps(req))
    code = consumer.main(['--request',str(source),'--output',str(output),'--output-format','compact'])
    out=json.loads(output.read_text())
    assert code == 2  # incomplete explicitly requested model, even when physics succeeds
    assert out['denominator']['evaluated'] == 1
    assert out['assay_selector_shadow']['denominator']['unsupported'] == 1
    _assert_scalar_pair(out['rows'][0]['result'])


@pytest.mark.parametrize('changes, supported', [({}, True), ({'is_ood': 'true'}, False),
    ({'smiles': 'not-a-molecule'}, False), ({'endpoint': 'IC50'}, False),
    ({'target_annotation_sha256': 'different'}, False), ({'endpoint_subtype': 'Kd'}, False)])
def test_registered_ki_predictor_and_v2_run_together_without_training(tmp_path, monkeypatch, changes, supported):
    import hashlib
    from rdkit import rdBase
    from betelgeuze_engine.product import public_assay_selector_shadow as selector
    # Synthetic registered bytes, never a real experimental checkpoint or label.
    binding = copy.deepcopy(next(iter(selector._REGISTERED_CHEMBL_V2.values())))
    binding['rdkit_version'] = rdBase.rdkitVersion
    payload = {**binding, 'schema_version': selector.CHEMBL_KI_SCHEMA,
        'features': selector.CHEMBL_FEATURES, 'coefficients': [0.0] * 1024, 'intercept': -1.25,
        'uncertainty_calibrated': False, 'product_ranking_enabled': False, 'customer_execution': False}
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    checkpoint = tmp_path / 'synthetic-selector.json'
    checkpoint.write_bytes(raw)
    monkeypatch.setattr(selector, '_REGISTERED_CHEMBL_V2', {digest: binding})
    req = request(tmp_path)
    req['assay_selector'] = {'checkpoint': str(checkpoint), 'checkpoint_sha256': digest}
    req['cases'][0]['assay_metadata'].update(target_annotation_sha256=binding['target_annotation_sha256'],
                                           endpoint_subtype='enzyme_inhibition_Ki')
    req['cases'][0]['assay_metadata'].update(changes)
    result = consumer.evaluate_request(req)
    _assert_scalar_pair(result['rows'][0]['result'])
    shadow = result['rows'][0]['assay_selector_shadow']
    assert shadow['status'] == ('evaluated' if supported else 'unsupported')
    assert shadow['prediction']['prediction_quantity'] == 'negative_log10_molar_Ki'
    assert shadow['prediction']['predicted_value'] == (-1.25 if supported else None)
    assert 'predicted_negative_log10_molar_IC50' not in shadow['prediction']
    assert checkpoint.read_bytes() == raw
    assert shadow['input_metadata']['source_provenance']['evaluation_only'] is True
    assert shadow['combined_score'] is None and shadow['residual_training_eligible'] is False
