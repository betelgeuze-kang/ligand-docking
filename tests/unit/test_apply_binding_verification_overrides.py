import json
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location('apply_binding_verification_overrides', ROOT / 'tools' / 'apply_binding_verification_overrides.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_build_payload_marks_verified_rows():
    sheet_rows = [
        {
            'priority_rank': '1', 'packet_step': 'core_binder_01', 'replacement_ligand_id': 'acetazolamide',
            'replacement_is_binder': '1', 'verify_reference_binding_kcal_mol': '', 'verify_provenance_source': '',
            'verify_source_url': '', 'verification_status': 'pending_binding_provenance_review', 'notes': ''
        },
        {
            'priority_rank': '2', 'packet_step': 'core_non_binder_01', 'replacement_ligand_id': 'acetaminophen',
            'replacement_is_binder': '0', 'verify_reference_binding_kcal_mol': '', 'verify_provenance_source': '',
            'verify_source_url': '', 'verification_status': 'pending_binding_provenance_review', 'notes': ''
        },
    ]
    overrides = [{
        'packet_step': 'core_binder_01',
        'verify_reference_binding_kcal_mol': '-10.8',
        'verify_provenance_source': 'chembl_activity::example',
        'verify_source_url': 'https://example.com',
        'verification_status': 'verified_chembl_ki',
        'notes_append': 'verified',
    }]
    payload = mod.build_payload(sheet_rows, overrides, 'ca2')
    assert payload['summary']['verified_row_count'] == 1
    assert payload['summary']['verified_binder_row_count'] == 1
    row = payload['sheet_rows'][0]
    assert row['verify_reference_binding_kcal_mol'] == '-10.8'
    assert row['verification_status'] == 'verified_chembl_ki'
