"""Synthetic compatibility/admission controls; no training or docking."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from rdkit import Chem, rdBase
from rdkit.Chem import rdFingerprintGenerator

from betelgeuze_engine.product import public_assay_selector_shadow as shadow


def _checkpoint(tmp_path, monkeypatch, change=None):
    binding = dict(next(iter(shadow._APPROVED_V1.values())))
    binding['rdkit_version'] = rdBase.rdkitVersion
    payload = dict(binding, schema_version='public_assay_cheap_selector_ridge_v1',
                   features=shadow.FEATURES, coefficients=[.25] * 1024, intercept=1.5,
                   uncertainty_calibrated=False, product_ranking_enabled=False, customer_execution=False)
    if change:
        change(payload)
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(shadow._APPROVED_V1, digest, binding)
    path = tmp_path / 'synthetic.json'
    path.write_bytes(raw)
    return path, digest


def _row(**change):
    row = dict(ligand_id='duplicate', smiles='CCCCC', endpoint='IC50',
               target_state_sha256=next(iter(shadow._APPROVED_V1.values()))['target_state_sha256'])
    row.update(change)
    return row


def _sidecar(tmp_path, checkpoint, digest, rows, **options):
    path = tmp_path / 'requests.csv'
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    output = tmp_path / 'shadow.json'
    args = dict(ligand_csv=str(path), ligand_sdf='', docking_request_json='', resume_stage3_only=False,
                checkpoint=str(checkpoint), checkpoint_sha256=digest, output_json=str(output))
    args.update(options)
    return shadow.run_pre_docking_shadow(**args), output, path


def test_exact_float64_morgan_parity_order_duplicates_and_unsupported(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    model = shadow.load_public_assay_selector(path, expected_sha256=digest)
    rows = [_row(), _row(smiles='c1ccccc1'), _row(endpoint='Kd'), _row()]
    result = model.predict_rows(rows)
    fp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024, includeChirality=True)
    expected = [float(fp.GetFingerprintAsNumPy(Chem.MolFromSmiles(row['smiles'])).sum()) * .25 + 1.5
                for row in (rows[0], rows[1], rows[3])]
    assert [result[i]['predicted_negative_log10_molar_IC50'] for i in (0, 1, 3)] == expected
    assert [row['row_index'] for row in result] == list(range(4))
    assert [row['ligand_id'] for row in result] == ['duplicate'] * 4
    assert result[2]['predicted_negative_log10_molar_IC50'] is None
    assert all(row['ood_status'] == 'not_assessed' and row['uncertainty'] is None for row in result)
    assert model.metadata['source_sha256'] != model.metadata['runtime_adapter_sha256']
    assert model.metadata['receptor_or_assay_construct_verified'] is False


@pytest.mark.parametrize('changes,reason', [
    ({'smiles': None}, 'missing_smiles'), ({'smiles': ''}, 'missing_smiles'),
    ({'smiles': float('nan')}, 'missing_smiles'), ({'smiles': '  '}, 'missing_smiles'),
    ({'smiles': 'CCCCC ligand-name'}, 'invalid_smiles_whitespace'),
    ({'smiles': 'C1'}, 'invalid_smiles'),
    ({'smiles': 'CCCC'}, 'outside_pilot_molecule_size_or_multifragment'),
    ({'smiles': 'C' * 71}, 'outside_pilot_molecule_size_or_multifragment'),
    ({'smiles': 'CCCCC.[Na+]'}, 'outside_pilot_molecule_size_or_multifragment'),
    ({'smiles': '[13CH3]CCCC'}, 'outside_pilot_element_radical_or_isotope_scope'),
    ({'smiles': '[CH2]CCCC'}, 'outside_pilot_element_radical_or_isotope_scope'),
    ({'smiles': 'CCCC[SiH3]'}, 'outside_pilot_element_radical_or_isotope_scope'),
    ({'smiles': 'C[N+](C)(C)CC[N+](C)(C)CC[N+](C)(C)C'}, 'outside_pilot_formal_charge_scope'),
    ({'target_state_sha256': ''}, 'missing_or_mismatched_target_state'),
    ({'target_state_sha256': 'BACE1'}, 'missing_or_mismatched_target_state'),
    ({'endpoint': None}, 'missing_or_mismatched_endpoint'),
    ({'endpoint': 'Ki'}, 'missing_or_mismatched_endpoint'),
    ({'is_ood': True}, 'declared_ood'), ({'is_ood': 'true'}, 'declared_ood'),
    ({'is_ood': 'uncertain'}, 'invalid_ood_declaration'),
])
def test_admission_never_replaces_unsupported_with_zero_or_intercept(tmp_path, monkeypatch, changes, reason):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    result = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([_row(**changes)])[0]
    assert result['status'] == 'unsupported'
    assert result['reason'] == reason
    assert result['predicted_negative_log10_molar_IC50'] is None


@pytest.mark.parametrize('change,reason', [
    (lambda p: p.update(source_sha256='0' * 64), 'binding_mismatch:source_sha256'),
    (lambda p: p.update(target_state_sha256='0' * 64), 'binding_mismatch:target_state_sha256'),
    (lambda p: p.update(endpoint='Kd'), 'binding_mismatch:endpoint'),
    (lambda p: p.update(training_protocol_sha256='0' * 64), 'binding_mismatch:training_protocol_sha256'),
    (lambda p: p.update(prediction_quantity='energy'), 'binding_mismatch:prediction_quantity'),
    (lambda p: p.update(features={}), 'feature_contract'),
    (lambda p: p.update(coefficients=[0.] * 1023), 'invalid_checkpoint_coefficients'),
    (lambda p: p.update(coefficients=[True] * 1024), 'invalid_checkpoint_coefficients'),
    (lambda p: p.update(intercept=float('inf')), 'invalid_checkpoint_coefficients'),
    (lambda p: p.update(product_ranking_enabled=True), 'unsupported_checkpoint_capability'),
    (lambda p: p.update(uncertainty_calibrated=True), 'unsupported_checkpoint_capability'),
    (lambda p: p.update(customer_execution=True), 'unsupported_checkpoint_capability'),
    (lambda p: p.update(extra_field=1), 'schema_keys_mismatch'),
])
def test_loader_rejects_contract_mismatch(tmp_path, monkeypatch, change, reason):
    path, digest = _checkpoint(tmp_path, monkeypatch, change)
    with pytest.raises(shadow.SelectorContractError, match=reason):
        shadow.load_public_assay_selector(path, expected_sha256=digest)


def test_unregistered_changed_bytes_and_rdkit_mismatch(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    with pytest.raises(shadow.SelectorContractError, match='unregistered'):
        shadow.load_public_assay_selector(path, expected_sha256='x' * 64)
    monkeypatch.setattr(rdBase, 'rdkitVersion', 'unsupported-version')
    with pytest.raises(shadow.SelectorContractError, match='rdkit_version_mismatch'):
        shadow.load_public_assay_selector(path, expected_sha256=digest)
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(shadow.SelectorContractError, match='checkpoint_sha256_mismatch'):
        shadow.load_public_assay_selector(path, expected_sha256=digest)


def test_nonfinite_math_keeps_row_and_null_prediction(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch, lambda p: p.update(coefficients=[1e308] * 1024))
    result = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([_row()])
    assert result[0]['reason'] == 'nonfinite_prediction'
    assert result[0]['predicted_negative_log10_molar_IC50'] is None


def test_sidecar_preserves_request_denominator_and_exact_input_cells(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    rows = [_row(), _row(smiles=''), _row(), _row(endpoint='Kd')]
    summary, output, csv_path = _sidecar(tmp_path, path, digest, rows)
    assert summary['requested_rows'] == 4
    assert summary['evaluated_rows'] == summary['unsupported_rows'] == 2
    result = json.loads(output.read_text())
    assert [row['row_index'] for row in result['rows']] == [0, 1, 2, 3]
    assert result['rows'][0]['input_cells'] == list(rows[0].values())
    assert result['input_sha256'] == hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert result['product_ranking_enabled'] is False


@pytest.mark.parametrize('contents,count', [
    ('smiles,smiles,endpoint,target_state_sha256\nCCCCC,CCCCC,IC50,abc\n', 1),
    ('smiles,endpoint,target_state_sha256\n\nCCCCC,IC50\n', 2),
    ('name\nfirst\nsecond\n', 2),
])
def test_invalid_csv_schema_and_empty_or_short_rows_retained(tmp_path, monkeypatch, contents, count):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    csv_path = tmp_path / 'invalid.csv'
    csv_path.write_text(contents)
    summary, output, _ = _sidecar(tmp_path, path, digest, [_row()], ligand_csv=str(csv_path))
    assert summary['requested_rows'] == summary['unsupported_rows'] == count
    assert summary['evaluated_rows'] == 0
    assert len(json.loads(output.read_text())['rows']) == count


def test_bad_checkpoint_keeps_every_row_and_csv_unmodified(tmp_path, monkeypatch):
    path, _ = _checkpoint(tmp_path, monkeypatch)
    summary, output, csv_path = _sidecar(tmp_path, path, 'bad', [_row(), _row()])
    assert summary['requested_rows'] == summary['unsupported_rows'] == 2
    assert summary['evaluated_rows'] == 0
    assert all(row['predicted_negative_log10_molar_IC50'] is None for row in json.loads(output.read_text())['rows'])
    assert summary['input_sha256'] == hashlib.sha256(csv_path.read_bytes()).hexdigest()


@pytest.mark.parametrize('kind', ['json', 'sdf', 'resume'])
def test_unsupported_input_not_claimed_zero_requests(tmp_path, monkeypatch, kind):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    request = tmp_path / 'request.json'
    request.write_text('{"untouched":true}')
    options = {'docking_request_json': str(request)} if kind == 'json' else (
        {'ligand_csv': '', 'ligand_sdf': 'unopened.sdf'} if kind == 'sdf' else {'resume_stage3_only': True})
    summary, _, _ = _sidecar(tmp_path, path, digest, [_row()], **options)
    assert summary['requested_rows'] is None and summary['unsupported_rows'] is None
    assert summary['evaluated_rows'] == 0
    assert request.read_text() == '{"untouched":true}'


@pytest.mark.parametrize('alias', ['input', 'checkpoint', 'symlink', 'hardlink'])
def test_sidecar_cannot_overwrite_source_or_checkpoint(tmp_path, monkeypatch, alias):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    csv_path = tmp_path / 'requests.csv'
    target = csv_path if alias == 'input' else path
    if alias in {'symlink', 'hardlink'}:
        target = tmp_path / 'alias.json'
        if alias == 'symlink':
            target.symlink_to(path)
        else:
            target.hardlink_to(path)
    before = path.read_bytes()
    summary, _, _ = _sidecar(tmp_path, path, digest, [_row()], output_json=str(target))
    assert summary['sidecar_status'] == 'failed'
    assert 'sidecar_aliases' in summary['sidecar_error']
    assert path.read_bytes() == before
    assert csv_path.read_text().startswith('ligand_id,smiles,')


def test_runtime_import_does_not_depend_on_tools_sklearn_or_eager_rdkit():
    code = '''
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'tools', 'sklearn', 'rdkit'}:
            raise AssertionError('forbidden runtime import: ' + fullname)
sys.meta_path.insert(0, Block())
from betelgeuze_engine.product import public_assay_selector_shadow
assert public_assay_selector_shadow.ADAPTER_SCHEMA == 'public_assay_selector_shadow_v1'
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_constructor_cannot_claim_registered_identity_for_forged_weights(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    forged = json.loads(path.read_text())
    forged['intercept'] = 999.0
    with pytest.raises((TypeError, ValueError)):
        shadow.PublicAssaySelectorShadow(forged, digest)
