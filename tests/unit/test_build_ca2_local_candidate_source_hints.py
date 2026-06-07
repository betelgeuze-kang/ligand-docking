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


def test_build_ca2_local_candidate_source_hints(tmp_path: Path) -> None:
    config = tmp_path / 'config'
    runs = tmp_path / 'runs'
    runs.mkdir(parents=True, exist_ok=True)

    _write_csv(
        config / 'ligand_meta_blind_ca2_zn_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['ca2_placeholder_nonbinder_03', 'CN1C=NC2=C1N(C)C(=O)N(C)C(=O)N2C', '194.19', '-0.1', '0', '6', '0', 'template_placeholder'],
            ['ca2_placeholder_binder_03', 'CN1CCN(CC1)S(=O)(=O)N', '180.23', '-1.0', '1', '3', '2', 'template_placeholder'],
        ],
    )
    _write_csv(
        config / 'ligand_meta_blind_ca2_zn_chembl50_v1.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [],
    )
    _write_csv(
        config / 'real_drug_targets_blind_ca2_zn_v1.csv',
        ['target', 'native_pdb_path', 'pdb_id', 'pocket_x', 'pocket_y', 'pocket_z', 'notes'],
        [['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'data/public_structures/1CA2.pdb', '1CA2', '-6.788', '-1.621', '15.381', 'CA2 anchor']],
    )
    _write_csv(
        config / 'ligand_target_metadata_blind_ca2_zn_v1.csv',
        ['target', 'target_family', 'sequence', 'pocket_fingerprint'],
        [['CARBONIC_ANHYDRASE_2_ZN_BLIND', 'METALLOENZYME', 'AAAA', 'zn_active_site|metal']],
    )
    _write_csv(
        config / 'structure_sources_ood_measured20_v1.csv',
        ['target', 'pdb_id', 'uniprot_id', 'notes'],
        [['Carbonic_Anhydrase_2_Zn', '1CA2', 'P00918', 'ood_measured20_metal']],
    )
    _write_csv(
        config / 'ligand_meta_disjoint_v2.csv',
        ['ligand_id', 'smiles', 'molecular_weight', 'logp', 'h_donors', 'h_acceptors', 'rot_bonds', 'scaffold'],
        [
            ['egfr_decoy_caffeine', 'CN1C=NC2=C1N(C)C(=O)N(C)C(=O)N2C', '194.19', '-0.1', '0', '6', '0', 'egfr_xanthine'],
            ['hiv_darunavir', 'CC(C)(C)NC(=O)N[C@@H](CC1=CC=CC=C1)C(O)C[C@@H](O)[C@@H](CC1=CC=CC=C1)NC(=O)N[C@@H](C(C)C)C(O)C(C)(C)C', '547.66', '2.9', '6', '11', '14', 'hiv_sulfonamide_like'],
        ],
    )
    queue_payload = {
        'queue_rows': [
            {'packet': 'core', 'packet_step': 'core_non_binder_03', 'current_ligand_id': 'ca2_placeholder_nonbinder_03'},
            {'packet': 'core', 'packet_step': 'core_binder_03', 'current_ligand_id': 'ca2_placeholder_binder_03'},
        ]
    }
    (runs / 'ca2_packet_fill_queue_current.json').write_text(json.dumps(queue_payload), encoding='utf-8')

    out_json = runs / 'ca2_local_candidate_source_hints_current.json'
    out_csv = runs / 'ca2_local_candidate_source_hints_current.csv'
    out_md = runs / 'ca2_local_candidate_source_hints_current.md'
    subprocess.run(
        [
            'python3',
            str(ROOT / 'tools/product/build_ca2_local_candidate_source_hints.py'),
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
    assert payload['summary']['slot_count'] == 2
    assert payload['summary']['slots_with_exact_local_curated_match'] == 1
    rows = list(csv.DictReader(out_csv.open('r', encoding='utf-8')))
    assert any(row['hint_type'] == 'exact_smiles_local_curated' and row['candidate_ligand_id'] == 'egfr_decoy_caffeine' for row in rows)
    assert any(row['hint_type'] == 'weak_scaffold_analogy' and row['candidate_ligand_id'] == 'hiv_darunavir' for row in rows)
    md_text = out_md.read_text(encoding='utf-8')
    assert 'CA2 Local Candidate Source Hints' in md_text
    assert 'core_non_binder_03' in md_text
