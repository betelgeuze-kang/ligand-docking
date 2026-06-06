from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def test_build_ca2_packet_replacement_readiness(tmp_path: Path) -> None:
    runs = tmp_path / 'runs'
    workbook_csv = runs / 'ca2_packet_replacement_workbook_current.csv'
    _write_csv(
        workbook_csv,
        [
            'packet','packet_step','target','current_ligand_id','replacement_ligand_id',
            'replacement_reference_binding_kcal_mol','replacement_is_binder','replacement_source',
            'replacement_role','replacement_smiles','replacement_molecular_weight','replacement_logp',
            'replacement_h_donors','replacement_h_acceptors','replacement_rot_bonds','replacement_scaffold',
            'apply_reference_row','apply_split_row','apply_meta_row','row_ready_for_apply','required_missing_fields','notes'
        ],
        [
            ['core','core_binder_01','CARBONIC_ANHYDRASE_2_ZN_BLIND','ca2_placeholder_binder_01','','','1','','far_ood_eval','','','','','','','','yes','yes','yes','no','',''],
            ['ood','ood_non_binder_01','CARBONIC_ANHYDRASE_2_ZN_BLIND','ca2_ood_nonbinder_01','ca2_real_ood_01','-1.0','0','manual_note','far_ood_eval','CCO','','','','','','aryl','yes','yes','yes','no','',''],
        ],
    )

    out_json = runs / 'ca2_packet_replacement_readiness_current.json'
    out_csv = runs / 'ca2_packet_replacement_readiness_current.csv'
    out_md = runs / 'ca2_packet_replacement_readiness_current.md'
    subprocess.run(
        [
            'python3',
            str(ROOT / 'tools/product/build_ca2_packet_replacement_readiness.py'),
            '--workbook-csv',
            str(workbook_csv),
            '--out-json',
            str(out_json),
            '--out-csv',
            str(out_csv),
            '--out-md',
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['workbook_row_count'] == 2
    assert payload['summary']['ready_row_count'] == 1
    assert payload['summary']['blocked_row_count'] == 1
    assert payload['summary']['most_common_missing_field']
    rows = list(csv.DictReader(out_csv.open('r', encoding='utf-8')))
    assert len(rows) == 2
    blocked = next(row for row in rows if row['packet'] == 'core')
    assert blocked['row_ready_for_apply'] == 'no'
    ready = next(row for row in rows if row['packet'] == 'ood')
    assert ready['row_ready_for_apply'] == 'yes'
    md_text = out_md.read_text(encoding='utf-8')
    assert 'CA2 Packet Replacement Readiness' in md_text
    assert 'Missing Field Counts' in md_text
