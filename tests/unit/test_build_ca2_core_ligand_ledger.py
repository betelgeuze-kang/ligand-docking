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


def test_ca2_core_ligand_ledger_scopes_to_ca2_reference_and_split(tmp_path: Path) -> None:
    config = tmp_path / 'config'
    runs = tmp_path / 'runs'
    _write_csv(
        config / 'ligand_binding_reference_blind_ca2_zn_v1.csv',
        ['target', 'ligand_id', 'reference_binding_kcal_mol', 'is_binder', 'source'],
        [
            ['EGFR_KINASE', 'erlotinib', '-9.2', '1', 'literature_proxy_v2'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_binder_01', '-8.0', '1', 'template_placeholder_needs_curation'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_nonbinder_01', '-1.2', '0', 'template_placeholder_needs_curation'],
        ],
    )
    _write_csv(
        config / 'ligand_eval_splits_blind_ca2_zn_v1.csv',
        ['target', 'ligand_id', 'role'],
        [
            ['EGFR_KINASE', 'erlotinib', 'fit'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_binder_01', 'far_ood_eval'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_nonbinder_01', 'far_ood_eval'],
        ],
    )
    _write_csv(
        config / 'ligand_meta_blind_ca2_zn_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['erlotinib', 'COCC', '393.4', '2.7', '1', '6', '8', 'quinazoline'],
            ['ca2_placeholder_binder_01', 'O=S(=O)(N)c1ccc(cc1)N', '172.2', '-0.7', '2', '3', '1', 'template_placeholder'],
            ['ca2_placeholder_nonbinder_01', 'c1ccccc1', '78.1', '2.1', '0', '0', '0', 'template_placeholder'],
        ],
    )

    out_json = runs / 'ca2_core_ligand_ledger_current.json'
    subprocess.run(
        [
            'python3',
            str(ROOT / 'tools/build_ca2_core_ligand_ledger.py'),
            '--reference-csv',
            'config/ligand_binding_reference_blind_ca2_zn_v1.csv',
            '--eval-split-csv',
            'config/ligand_eval_splits_blind_ca2_zn_v1.csv',
            '--ligand-meta-csv',
            'config/ligand_meta_blind_ca2_zn_v1.csv',
            '--out-json',
            str(out_json),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['ligand_count'] == 2
    assert payload['summary']['placeholder_ligand_id_count'] == 2
    ligand_ids = [row['ligand_id'] for row in payload['ledger_rows']]
    assert ligand_ids == ['ca2_placeholder_binder_01', 'ca2_placeholder_nonbinder_01']
