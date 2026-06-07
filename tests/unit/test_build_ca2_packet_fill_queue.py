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


def test_build_ca2_packet_fill_queue(tmp_path: Path) -> None:
    config = tmp_path / 'config'
    runs = tmp_path / 'runs'
    _write_csv(
        config / 'ligand_binding_reference_blind_ca2_zn_v1.csv',
        ['target', 'ligand_id', 'reference_binding_kcal_mol', 'is_binder', 'source'],
        [
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_binder_01', '-8.0', '1', 'template_placeholder_needs_curation'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_nonbinder_01', '-1.2', '0', 'template_placeholder_needs_curation'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_real_candidate_01', '-7.2', '1', 'manual_curated_note'],
        ],
    )
    _write_csv(
        config / 'ligand_eval_splits_blind_ca2_zn_v1.csv',
        ['target', 'ligand_id', 'role'],
        [
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_binder_01', 'far_ood_eval'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_placeholder_nonbinder_01', 'far_ood_eval'],
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_real_candidate_01', 'far_ood_eval'],
        ],
    )
    _write_csv(
        config / 'ligand_meta_blind_ca2_zn_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['ca2_placeholder_binder_01', 'O=S(=O)(N)c1ccc(cc1)N', '172.2', '-0.7', '2', '3', '1', 'template_placeholder'],
            ['ca2_placeholder_nonbinder_01', 'c1ccccc1', '78.1', '2.1', '0', '0', '0', 'template_placeholder'],
            ['ca2_real_candidate_01', 'C1=CC=NC=C1', '79.1', '0.5', '0', '1', '0', 'pyridine'],
        ],
    )
    _write_csv(
        config / 'ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv',
        ['target', 'ligand_id', 'reference_binding_kcal_mol', 'is_binder', 'source'],
        [
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_ood_binder_01', '-8.4', '1', 'template_placeholder_needs_curation'],
        ],
    )
    _write_csv(
        config / 'ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv',
        ['target', 'ligand_id', 'role'],
        [
            ['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'ca2_ood_binder_01', 'far_ood_eval'],
        ],
    )
    _write_csv(
        config / 'ligand_meta_blind_ca2_zn_chembl50_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['ca2_ood_binder_01', 'O=S(=O)(N)c1ccc(cc1)N', '172.2', '-0.7', '2', '3', '1', 'template_placeholder'],
        ],
    )

    out_json = runs / 'ca2_packet_fill_queue_current.json'
    out_csv = runs / 'ca2_packet_fill_queue_current.csv'
    out_md = runs / 'ca2_packet_fill_queue_current.md'
    subprocess.run(
        ['python3', str(ROOT / 'tools/product/build_ca2_packet_fill_queue.py'), '--out-json', str(out_json), '--out-csv', str(out_csv), '--out-md', str(out_md)],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['queue_count'] == 3
    assert payload['summary']['packets_with_queue'] == 2
    core_summary = next(row for row in payload['packet_summaries'] if row['packet'] == 'core')
    assert core_summary['binder_slots'] == 1
    assert core_summary['non_binder_slots'] == 1
    rows = list(csv.DictReader(out_csv.open('r', encoding='utf-8')))
    assert len(rows) == 3
    assert {'ca2_placeholder_binder_01', 'ca2_placeholder_nonbinder_01', 'ca2_ood_binder_01'} == {row['current_ligand_id'] for row in rows}
    assert all(row['curation_status'] == 'pending_replacement' for row in rows)
    md_text = out_md.read_text(encoding='utf-8')
    assert 'CA2 Packet Fill Queue' in md_text
    assert 'core_binder_01' in md_text
