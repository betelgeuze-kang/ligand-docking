"""Synthetic native BindingDB controls; optional frozen-model metadata-only replay."""
from __future__ import annotations

from copy import deepcopy
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from rdkit import Chem, rdBase
from rdkit.Chem import rdFingerprintGenerator

from betelgeuze_engine.product import public_assay_selector_shadow as shadow

DIGEST = "de9b3e21c93b0f15c02df221d2f8ee9caa3d5e0590442c34efed3394b969ac85"
TARGET = "9359ee693bcd2a1342fbc39019a015888723cdaa006cf0e11a1b9d9fb9518a5f"
QUANTITY = "negative_log10_molar_Ki"


def _checkpoint(tmp_path, monkeypatch, change=None):
    binding = deepcopy(shadow._REGISTERED_BINDINGDB_V1[DIGEST])
    binding['rdkit_version'] = rdBase.rdkitVersion
    payload = dict(binding, schema_version=shadow.BINDINGDB_SCHEMA,
                   features=dict(shadow.BINDINGDB_FEATURES), coefficients=[.125] * 1024,
                   intercept=0., uncertainty_calibrated=False,
                   product_ranking_enabled=False, customer_execution=False)
    if change:
        change(payload)
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(shadow._REGISTERED_BINDINGDB_V1, digest, binding)
    path = tmp_path / 'synthetic-bindingdb.json'
    path.write_bytes(raw)
    return path, digest


def _row(**changes):
    return dict(dict(ligand_id='duplicate', smiles='CCCCC',
                     target_annotation_sha256=TARGET, endpoint='Ki'), **changes)


def _sidecar(tmp_path, path, digest, rows):
    csvpath = tmp_path / 'metadata.csv'
    with csvpath.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    raw = csvpath.read_bytes()
    output = tmp_path / 'sidecar.json'
    summary = shadow.run_pre_docking_shadow(ligand_csv=str(csvpath), ligand_sdf='',
        docking_request_json='', resume_stage3_only=False, checkpoint=str(path),
        checkpoint_sha256=digest, output_json=str(output))
    assert csvpath.read_bytes() == raw
    return summary, json.loads(output.read_text())


def _assert_generic(rows):
    assert all(row['prediction_quantity'] == QUANTITY for row in rows)
    assert not any('IC50' in key for row in rows for key in row)
    assert all(row['ood_status'] == 'not_assessed' and row['uncertainty'] is None for row in rows)


def test_bindingdb_generic_quantity_order_duplicate_and_exact_morgan_parity(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    model = shadow.load_public_assay_selector(path, expected_sha256=digest)
    rows = [_row(), _row(smiles='c1ccccc1'), _row(endpoint='IC50'), _row()]
    output = model.predict_rows(rows)
    _assert_generic(output)
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024, includeChirality=True)
    expected = [float(gen.GetFingerprintAsNumPy(Chem.MolFromSmiles(rows[i]['smiles'])).sum()) * .125
                for i in (0, 1, 3)]
    assert [output[i]['predicted_value'] for i in (0, 1, 3)] == expected
    assert output[2]['predicted_value'] is output[2]['mean_baseline_value'] is None
    assert [r['row_index'] for r in output] == list(range(4))
    assert [r['ligand_id'] for r in output] == ['duplicate'] * 4
    assert model.required_input_columns == {'smiles', 'target_annotation_sha256', 'endpoint'}
    assert model.metadata['chemical_scope'] == shadow.BINDINGDB_CHEMISTRY_SCOPE
    assert model.metadata['target_identity_basis'] == 'caller_declared_catalogue_target_annotation_not_physical_state'
    assert 'target_state_sha256' not in model.metadata
    assert all(model.metadata[k] is False for k in (
        'product_ranking_enabled', 'customer_execution', 'uncertainty_calibrated',
        'physical_energy_prediction', 'receptor_or_assay_construct_verified', 'scientific_validation'))


@pytest.mark.parametrize('change,reason', [
    ({'endpoint': 'IC50'}, 'endpoint'), ({'endpoint': 'Kd'}, 'endpoint'),
    ({'endpoint': None}, 'endpoint'), ({'target_annotation_sha256': 'P00742'}, 'target_annotation'),
    ({'target_annotation_sha256': None, 'target_state_sha256': TARGET}, 'target_annotation'),
    ({'smiles': 'CCCC'}, 'size'), ({'smiles': 'C' * 71}, 'size'),
    ({'smiles': 'CCCCC.C'}, 'multifragment'), ({'smiles': 'CCCC[SiH3]'}, 'element'),
    ({'smiles': '[13CH3]CCCC'}, 'isotope'), ({'smiles': '[CH2]CCCC'}, 'radical'),
    ({'smiles': 'C[N+](C)(C)CC[N+](C)(C)CC[N+](C)(C)C'}, 'formal_charge'),
    ({'smiles': '[O-]C([O-])C([O-])CCC'}, 'formal_charge'),
    ({'is_ood': True}, 'declared_ood'), ({'is_ood': 'unknown'}, 'invalid_ood'),
])
def test_bindingdb_runtime_scope_fail_closed(tmp_path, monkeypatch, change, reason):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    output = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([_row(**change)])
    _assert_generic(output)
    assert output[0]['status'] == 'unsupported' and reason in output[0]['reason']
    assert output[0]['predicted_value'] is output[0]['mean_baseline_value'] is None


@pytest.mark.parametrize('smiles', ['CCCCC', 'C' * 70, 'C[N+](C)(C)CC[N+](C)(C)C'])
def test_bindingdb_scope_inclusive_boundaries(tmp_path, monkeypatch, smiles):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    output = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([_row(smiles=smiles)])
    assert output[0]['status'] == 'evaluated'


@pytest.mark.parametrize('key', list(shadow._REGISTERED_BINDINGDB_V1[DIGEST]))
@pytest.mark.parametrize('mutation', ['missing', 'changed'])
def test_bindingdb_exact_frozen_binding_required(tmp_path, monkeypatch, key, mutation):
    def change(payload):
        if mutation == 'missing':
            payload.pop(key)
        else:
            payload[key] = 'incompatible'
    path, digest = _checkpoint(tmp_path, monkeypatch, change)
    with pytest.raises(shadow.SelectorContractError, match='schema_keys|binding_mismatch'):
        shadow.load_public_assay_selector(path, expected_sha256=digest)


@pytest.mark.parametrize('change,reason', [
    (lambda p: p.update(schema_version=shadow.CHEMBL_SCHEMA), 'feature_contract'),
    (lambda p: p.update(features=shadow.FEATURES), 'feature_contract'),
    (lambda p: p['features'].update(radius=3), 'feature_contract'),
    (lambda p: p.update(coefficients=[True] * 1024), 'coefficients'),
    (lambda p: p.update(intercept=float('inf')), 'coefficients'),
    (lambda p: p.update(uncertainty_calibrated=True), 'capability'),
    (lambda p: p.update(product_ranking_enabled=True), 'capability'),
    (lambda p: p.update(customer_execution=True), 'capability'),
    (lambda p: p.update(chemistry_scope={}), 'schema_keys'),
])
def test_bindingdb_no_relabelled_features_or_capability_promotion(tmp_path, monkeypatch, change, reason):
    path, digest = _checkpoint(tmp_path, monkeypatch, change)
    with pytest.raises(shadow.SelectorContractError, match=reason):
        shadow.PublicAssaySelectorShadow(path, digest)


@pytest.mark.parametrize('kind', ['valid', 'bytes', 'header', 'width'])
def test_bindingdb_sidecar_has_generic_values_even_when_unavailable(tmp_path, monkeypatch, kind):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    rows = [_row(), _row(smiles=''), _row(endpoint='IC50'), _row()]
    if kind == 'bytes':
        path.write_bytes(path.read_bytes() + b' ')
    if kind == 'header':
        for row in rows:
            row['target_state_sha256'] = row.pop('target_annotation_sha256')
    summary, result = _sidecar(tmp_path, path, digest, rows)
    if kind == 'width':
        csvpath = tmp_path / 'metadata.csv'
        csvpath.write_text(csvpath.read_text() + 'extra,width\n')
        shadow.run_pre_docking_shadow(ligand_csv=str(csvpath), ligand_sdf='', docking_request_json='',
            resume_stage3_only=False, checkpoint=str(path), checkpoint_sha256=digest,
            output_json=str(tmp_path / 'sidecar.json'))
        result = json.loads((tmp_path / 'sidecar.json').read_text())
        assert result['rows'][-1]['reason'] == 'invalid_csv_schema_or_row_width'
    _assert_generic(result['rows'])
    assert summary['requested_rows'] == 4
    assert summary['evaluated_rows'] == (2 if kind in {'valid', 'width'} else 0)
    assert [r['input_cells'] for r in result['rows'][:4]] == [list(r.values()) for r in rows]


def test_bindingdb_actual_htvs_hook_reuses_identical_mapping_command(tmp_path, monkeypatch):
    from betelgeuze_engine.product.runners import htvs_pipeline as pipeline
    path, digest = _checkpoint(tmp_path, monkeypatch)
    _sidecar(tmp_path, path, digest, [_row(), _row(smiles=''), _row()])
    commands = []
    def child(command):
        commands.append(command)
        return {'ok': False, 'synthetic_stop_before_mapping': True}
    monkeypatch.setattr(pipeline, '_run_cmd', child)
    monkeypatch.setattr(pipeline, '_finalize_and_write', lambda _prefix, payload, _args: payload)
    prefix = tmp_path / 'htvs'
    base = ['--out-prefix', str(prefix), '--no-single-instance', '--no-auto-heavy-artifacts-root',
            '--no-reuse-stage1-if-exists', '--ligand-csv', str(tmp_path / 'metadata.csv')]
    pipeline.run_pipeline(pipeline.build_parser().parse_args(base))
    result = pipeline.run_pipeline(pipeline.build_parser().parse_args(base + ['--public-assay-shadow-enabled',
        '--public-assay-shadow-checkpoint', str(path), '--public-assay-shadow-checkpoint-sha256', digest]))
    assert commands[0] == commands[1]
    meta = result['stages']['stage1_ligand_mapping']['public_assay_selector_shadow']
    assert (meta['requested_rows'], meta['evaluated_rows'], meta['unsupported_rows']) == (3, 2, 1)
    assert meta['product_ranking_enabled'] is meta['customer_execution'] is False
    _assert_generic(json.loads((tmp_path / 'htvs_public_assay_selector_shadow.json').read_text())['rows'])


def test_actual_frozen_checkpoint_metadata_only_replay(tmp_path):
    checkpoint = os.getenv('BETELGEUZE_BINDINGDB_SHADOW_CHECKPOINT')
    manifest_path = os.getenv('BETELGEUZE_BINDINGDB_SHADOW_MANIFEST')
    if not checkpoint or not manifest_path:
        pytest.skip('explicit frozen checkpoint and metadata manifest paths required')
    model = shadow.load_public_assay_selector(checkpoint, expected_sha256=DIGEST)
    raw_manifest = Path(manifest_path).read_bytes()
    assert hashlib.sha256(raw_manifest).hexdigest() == model.metadata['manifest_sha256']
    manifest = json.loads(raw_manifest)
    assert model.metadata['chemical_scope'] == manifest['scope']['chemistry_scope']
    assert model.metadata['target_annotation_sha256'] == manifest['scope']['target_annotation_sha256']
    # Only metadata and preassigned roles are opened. No archive, assay ledger,
    # fit/evaluation records, labels, frozen predictions or outcome summaries.
    def bound_metadata(entry):
        raw = Path(entry['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        return raw
    metadata = [json.loads(line) for line in bound_metadata(manifest['normalized_metadata']).splitlines()]
    plan = json.loads(bound_metadata(manifest['split_plan']))
    ids = {r['record_id'] for r in plan['assignments']}
    rows = [_row(ligand_id=r['ligand_id'], smiles=r['chemical_identity']['canonical_isomeric_smiles'])
            for r in metadata if r['record_id'] in ids]
    assert len(rows) == len(ids) == 914
    summary, result = _sidecar(tmp_path, checkpoint, DIGEST, rows)
    assert summary['requested_rows'] == 914
    assert summary['sidecar_status'] == 'written'
    _assert_generic(result['rows'])
    admitted = [i for i, r in enumerate(result['rows']) if r['status'] == 'evaluated']
    assert admitted
    # Independently replay the frozen weights; this is numerical consumer parity,
    # not an assay-quality test or an OOD/physical-accuracy assessment.
    payload = json.loads(Path(checkpoint).read_text())
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024, includeChirality=True)
    matrix = np.asarray([gen.GetFingerprintAsNumPy(Chem.MolFromSmiles(rows[i]['smiles']))
                         for i in admitted], dtype=np.float64)
    expected = matrix @ np.asarray(payload['coefficients'], dtype=np.float64) + payload['intercept']
    np.testing.assert_array_equal([result['rows'][i]['predicted_value'] for i in admitted], expected)
    assert all(r['mean_baseline_value'] == payload['mean_baseline'] for r in result['rows'] if r['status'] == 'evaluated')
    assert all(result[k] is False for k in ('product_ranking_enabled', 'customer_execution', 'uncertainty_calibrated'))
    print(json.dumps({'metadata_rows': len(rows), 'evaluated_rows': summary['evaluated_rows'],
                      'unsupported_rows': summary['unsupported_rows'], 'sidecar_path': str(tmp_path / 'sidecar.json')}))


def test_unregistered_ki_request_has_no_ic50_keys_or_inferred_quantity(tmp_path, monkeypatch):
    path, _ = _checkpoint(tmp_path, monkeypatch)
    with pytest.raises(shadow.SelectorContractError, match='unregistered_checkpoint'):
        shadow.load_public_assay_selector(path, expected_sha256='0' * 64)
    summary, result = _sidecar(tmp_path, path, '0' * 64, [_row(), _row()])
    assert summary['evaluated_rows'] == 0 and summary['unsupported_rows'] == 2
    assert summary['prediction_scope'] is None
    assert all(row['prediction_quantity'] is row['predicted_value'] is row['mean_baseline_value'] is None
               for row in result['rows'])
    assert not any('IC50' in key for row in result['rows'] for key in row)


CATHEPSIN_L_DIGEST = "e8194e9a782ae503f1a61afa5e2a53031a99c01c117d04aa1b9617369a0de94d"


def test_cathepsin_l_frozen_binding_does_not_inherit_other_target_or_approval():
    binding = shadow._REGISTERED_BINDINGDB_V1[CATHEPSIN_L_DIGEST]
    assert binding["manifest_sha256"] == "0f22a9ae2b093a36ec5692efe5cd975f9da900fadc99208112cdbcb7134a450e"
    assert binding["target_annotation_sha256"] == "ed5586c054c184e9acfeba06749fcc27b73051fe20c9070a3d8fbfa7192f5058"
    assert binding["endpoint"] == "Ki"
    evidence = shadow._CHECKPOINT_EVIDENCE[CATHEPSIN_L_DIGEST]
    assert evidence["promotion_status"] == "NOT_PROMOTED"
    assert evidence["supported_development_positive_count"] == 0
    assert evidence["development_recall_and_average_precision"] is None
    assert evidence["primary_per_compound_measurements_verified"] is False
    assert evidence["checkpoint_rehashed_for_new_runtime"] is False


def test_cathepsin_l_sidecar_keeps_failed_rows_and_sparse_evidence(tmp_path, monkeypatch):
    # New synthetic weights, never public evaluation labels.
    binding = deepcopy(shadow._REGISTERED_BINDINGDB_V1[CATHEPSIN_L_DIGEST])
    binding["rdkit_version"] = rdBase.rdkitVersion
    payload = dict(binding, schema_version=shadow.BINDINGDB_SCHEMA,
                   features=dict(shadow.BINDINGDB_FEATURES), coefficients=[0.] * 1024,
                   intercept=0., uncertainty_calibrated=False,
                   product_ranking_enabled=False, customer_execution=False)
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(shadow._REGISTERED_BINDINGDB_V1, digest, binding)
    monkeypatch.setitem(shadow._CHECKPOINT_EVIDENCE, digest,
                        deepcopy(shadow._CHECKPOINT_EVIDENCE[CATHEPSIN_L_DIGEST]))
    path = tmp_path / "synthetic-cathepsin-l.json"
    path.write_bytes(raw)
    row = _row(target_annotation_sha256=binding["target_annotation_sha256"])
    rows = [row, dict(row, endpoint="IC50"), dict(row, is_ood="true"), row]
    rows = [dict(r, is_ood=r.get("is_ood", "")) for r in rows]
    summary, saved = _sidecar(tmp_path, path, digest, rows)
    assert (summary["requested_rows"], summary["evaluated_rows"], summary["unsupported_rows"]) == (4, 2, 2)
    assert [r["predicted_value"] for r in saved["rows"]] == [0., None, None, 0.]
    _assert_generic(saved["rows"])
    model = saved["model"]
    assert binding["target_annotation_sha256"] in model["prediction_scope"]
    assert saved["prediction_scope"] == model["prediction_scope"]
    assert model["checkpoint_evidence_observations"]["supported_development_rows"] == 4
    assert model["checkpoint_evidence_observations"]["requested_development_rows"] == 27
    assert all(model[k] is False for k in ("customer_execution", "product_ranking_enabled",
        "scientific_validation", "receptor_or_assay_construct_verified", "physical_energy_prediction"))
    assert path.read_bytes() == raw


def test_vegfr2_registered_contract_keeps_ic50_target_and_ood_boundaries(tmp_path, monkeypatch):
    digest = '1255488791dd517bf12c261bb376c1e778def7bab1cb30e242ad427b3c4cb066'
    binding = deepcopy(shadow._REGISTERED_BINDINGDB_V1[digest])
    binding['rdkit_version'] = rdBase.rdkitVersion
    # Fresh synthetic weights exercise the real registered contract without
    # embedding public observations or requiring a local checkpoint in CI.
    payload = dict(binding, schema_version=shadow.BINDINGDB_SCHEMA,
                   features=dict(shadow.BINDINGDB_FEATURES), coefficients=[0.] * 1024,
                   intercept=0., uncertainty_calibrated=False,
                   product_ranking_enabled=False, customer_execution=False)
    raw = json.dumps(payload).encode()
    synthetic_digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(shadow._REGISTERED_BINDINGDB_V1, synthetic_digest, binding)
    checkpoint = tmp_path / 'synthetic-vegfr2.json'
    checkpoint.write_bytes(raw)
    model = shadow.load_public_assay_selector(checkpoint, expected_sha256=synthetic_digest)
    valid = dict(ligand_id='same-id', smiles='CCCCC', endpoint='IC50',
                 target_annotation_sha256=binding['target_annotation_sha256'])
    output = model.predict_rows([valid, dict(valid, endpoint='Ki'),
                                 dict(valid, target_annotation_sha256=TARGET),
                                 dict(valid, is_ood=True)])
    assert output[0]['status'] == 'evaluated' and output[0]['predicted_value'] == 0.
    assert [row['status'] for row in output[1:]] == ['unsupported'] * 3
    assert all(row['predicted_value'] is None for row in output[1:])
    assert all(row['prediction_quantity'] == 'negative_log10_molar_IC50' for row in output)
    assert model.metadata['compatibility_registration_only'] is True
    assert all(model.metadata[key] is False for key in (
        'customer_execution', 'product_ranking_enabled', 'scientific_validation',
        'physical_energy_prediction', 'uncertainty_calibrated'))
