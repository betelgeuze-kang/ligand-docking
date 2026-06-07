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


def test_pxr_core_ligand_ledger_scopes_to_pxr_reference_and_split(tmp_path: Path) -> None:
    config = tmp_path / 'config'
    runs = tmp_path / 'runs'
    _write_csv(
        config / 'ligand_binding_reference_blind_pxr_nr1i2_v1.csv',
        ['target', 'ligand_id', 'reference_binding_kcal_mol', 'is_binder', 'source'],
        [
            ['EGFR_KINASE', 'erlotinib', '-9.2', '1', 'literature_proxy_v2'],
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_binder_01', '-8.0', '1', 'template_placeholder_needs_curation'],
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_nonbinder_01', '-1.2', '0', 'template_placeholder_needs_curation'],
        ],
    )
    _write_csv(
        config / 'ligand_eval_splits_blind_pxr_nr1i2_v1.csv',
        ['target', 'ligand_id', 'role'],
        [
            ['EGFR_KINASE', 'erlotinib', 'fit'],
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_binder_01', 'far_ood_eval'],
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_nonbinder_01', 'far_ood_eval'],
        ],
    )
    _write_csv(
        config / 'ligand_meta_blind_pxr_nr1i2_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['erlotinib', 'COCC', '393.4', '2.7', '1', '6', '8', 'quinazoline'],
            ['pxr_placeholder_binder_01', 'O=S(=O)(N)c1ccc(cc1)N', '172.2', '-0.7', '2', '3', '1', 'template_placeholder'],
            ['pxr_placeholder_nonbinder_01', 'c1ccccc1', '78.1', '2.1', '0', '0', '0', 'template_placeholder'],
        ],
    )

    out_json = runs / 'pxr_core_ligand_ledger_current.json'
    subprocess.run(
        [
            'python3',
            str(ROOT / 'tools/product/build_pxr_core_ligand_ledger.py'),
            '--reference-csv',
            'config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv',
            '--eval-split-csv',
            'config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv',
            '--ligand-meta-csv',
            'config/ligand_meta_blind_pxr_nr1i2_v1.csv',
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
    assert ligand_ids == ['pxr_placeholder_binder_01', 'pxr_placeholder_nonbinder_01']
