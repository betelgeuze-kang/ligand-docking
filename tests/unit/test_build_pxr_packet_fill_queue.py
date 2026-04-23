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


def test_build_pxr_packet_fill_queue(tmp_path: Path) -> None:
    config = tmp_path / 'config'
    runs = tmp_path / 'runs'
    _write_csv(
        config / 'ligand_binding_reference_blind_pxr_nr1i2_v1.csv',
        ['target', 'ligand_id', 'reference_binding_kcal_mol', 'is_binder', 'source'],
        [
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_binder_01', 'TODO_BINDING_KCAL', '1', 'pxr_blind_proxy_v1'],
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_nonbinder_01', 'TODO_BINDING_KCAL', '0', 'pxr_blind_proxy_v1'],
            ['PXR_NR1I2_BLIND', 'pxr_real_candidate_01', '-8.1', '1', 'manual_curated_note'],
        ],
    )
    _write_csv(
        config / 'ligand_eval_splits_blind_pxr_nr1i2_v1.csv',
        ['target', 'ligand_id', 'role'],
        [
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_binder_01', 'fit'],
            ['PXR_NR1I2_BLIND', 'pxr_placeholder_nonbinder_01', 'far_ood_eval'],
            ['PXR_NR1I2_BLIND', 'pxr_real_candidate_01', 'far_ood_eval'],
        ],
    )
    _write_csv(
        config / 'ligand_meta_blind_pxr_nr1i2_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['pxr_placeholder_binder_01', 'TODO_SMILES', '0.0', '0.0', '0', '0', '0', 'TODO_SCAFFOLD'],
            ['pxr_placeholder_nonbinder_01', 'TODO_SMILES', '0.0', '0.0', '0', '0', '0', 'TODO_SCAFFOLD'],
            ['pxr_real_candidate_01', 'CCO', '46.0', '0.1', '1', '1', '0', 'curated_scaffold'],
        ],
    )
    _write_csv(
        config / 'ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv',
        ['target', 'ligand_id', 'reference_binding_kcal_mol', 'is_binder', 'source'],
        [
            ['PXR_NR1I2_BLIND', 'pxr_ood_binder_01', 'TODO_BINDING_KCAL', '1', 'pxr_blind_proxy_v1'],
        ],
    )
    _write_csv(
        config / 'ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv',
        ['target', 'ligand_id', 'role'],
        [
            ['PXR_NR1I2_BLIND', 'pxr_ood_binder_01', 'far_ood_eval'],
        ],
    )
    _write_csv(
        config / 'ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['pxr_ood_binder_01', 'TODO_SMILES', '0.0', '0.0', '0', '0', '0', 'TODO_SCAFFOLD'],
        ],
    )

    out_json = runs / 'pxr_packet_fill_queue_current.json'
    out_csv = runs / 'pxr_packet_fill_queue_current.csv'
    out_md = runs / 'pxr_packet_fill_queue_current.md'
    subprocess.run(
        ['python3', str(ROOT / 'tools/build_pxr_packet_fill_queue.py'), '--out-json', str(out_json), '--out-csv', str(out_csv), '--out-md', str(out_md)],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['queue_count'] == 3
    assert payload['summary']['packets_with_queue'] == 2
    rows = list(csv.DictReader(out_csv.open('r', encoding='utf-8')))
    assert len(rows) == 3
    assert {'pxr_placeholder_binder_01', 'pxr_placeholder_nonbinder_01', 'pxr_ood_binder_01'} == {row['current_ligand_id'] for row in rows}
    assert all(row['curation_status'] == 'pending_replacement' for row in rows)
    md_text = out_md.read_text(encoding='utf-8')
    assert 'PXR Packet Fill Queue' in md_text
    assert 'core_fit_binder_01' in md_text
