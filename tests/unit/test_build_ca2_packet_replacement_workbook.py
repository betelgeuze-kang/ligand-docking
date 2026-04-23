from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_ca2_packet_replacement_workbook(tmp_path: Path) -> None:
    runs = tmp_path / 'runs'
    runs.mkdir(parents=True, exist_ok=True)
    queue_json = runs / 'ca2_packet_fill_queue_current.json'
    queue_json.write_text(json.dumps({
        'queue_rows': [
            {
                'packet': 'core',
                'packet_step': 'core_binder_01',
                'current_ligand_id': 'ca2_placeholder_binder_01',
                'binder_label': 'binder',
                'current_role': 'far_ood_eval',
                'replacement_role': 'far_ood_eval',
                'notes': 'Replace core binder slot 01.',
            },
            {
                'packet': 'ood',
                'packet_step': 'ood_non_binder_01',
                'current_ligand_id': 'ca2_ood_nonbinder_01',
                'binder_label': 'non_binder',
                'current_role': 'far_ood_eval',
                'replacement_role': 'far_ood_eval',
                'notes': 'Replace ood non-binder slot 01.',
            },
        ]
    }, indent=2), encoding='utf-8')

    out_json = runs / 'ca2_packet_replacement_workbook_current.json'
    out_csv = runs / 'ca2_packet_replacement_workbook_current.csv'
    out_md = runs / 'ca2_packet_replacement_workbook_current.md'
    subprocess.run(
        [
            'python3',
            str(ROOT / 'tools/build_ca2_packet_replacement_workbook.py'),
            '--queue-json',
            str(queue_json),
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
    assert payload['summary']['ready_seed_row_count'] == 0
    assert payload['summary']['packets_with_workbook_rows'] == 2
    rows = list(csv.DictReader(out_csv.open('r', encoding='utf-8')))
    assert len(rows) == 2
    assert rows[0]['replacement_ligand_id'] == ''
    assert rows[0]['apply_reference_row'] == 'yes'
    assert rows[0]['replacement_is_binder'] == '1'
    assert rows[1]['replacement_is_binder'] == '0'
    md_text = out_md.read_text(encoding='utf-8')
    assert 'CA2 Packet Replacement Workbook' in md_text
    assert 'core_binder_01' in md_text
