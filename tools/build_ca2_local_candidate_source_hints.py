#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_TARGET = 'CARBONIC_ANHYDRASE_2_ZN_BLIND'
CURRENT_CA2_META = {
    'core': 'config/ligand_meta_blind_ca2_zn_v1.csv',
    'ood': 'config/ligand_meta_blind_ca2_zn_chembl50_v1.csv',
}
CURRENT_QUEUE_JSON = 'runs/ca2_packet_fill_queue_current.json'
TARGET_PACKET_CSV = 'config/real_drug_targets_blind_ca2_zn_v1.csv'
TARGET_META_CSV = 'config/ligand_target_metadata_blind_ca2_zn_v1.csv'
STRUCTURE_SOURCE_CSV = 'config/structure_sources_ood_measured20_v1.csv'
WEAK_SULFONAMIDE_HINT = ('config/ligand_meta_disjoint_v2.csv', 'hiv_darunavir', 'hiv_sulfonamide_like')


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _build_smiles_index(exclude_paths: set[Path]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    for path_like in glob.glob(str(ROOT / 'config/ligand_meta*.csv')):
        path = Path(path_like).resolve()
        if path in exclude_paths:
            continue
        try:
            rows = _read_csv(path)
        except Exception:
            continue
        for row in rows:
            smiles = row.get('smiles', '').strip()
            if not smiles:
                continue
            key = (
                row.get('ligand_id', ''),
                row.get('scaffold', ''),
                smiles,
            )
            entry = grouped[smiles].setdefault(
                key,
                {
                    'candidate_ligand_id': row.get('ligand_id', ''),
                    'candidate_scaffold': row.get('scaffold', ''),
                    'candidate_smiles': smiles,
                    'repo_source_paths': [],
                },
            )
            entry['repo_source_paths'].append(str(path.relative_to(ROOT)))
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for smiles, entries in grouped.items():
        for entry in entries.values():
            entry['repo_source_paths'] = sorted(set(entry['repo_source_paths']))
            entry['repo_source_path'] = entry['repo_source_paths'][0]
            entry['repo_source_count'] = len(entry['repo_source_paths'])
            index[smiles].append(entry)
    return index


def _load_ca2_meta_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for packet, path_like in CURRENT_CA2_META.items():
        for row in _read_csv(_resolve(path_like)):
            copied = dict(row)
            copied['packet'] = packet
            rows.append(copied)
    return rows


def _load_target_anchor() -> dict[str, str]:
    target_rows = _read_csv(_resolve(TARGET_PACKET_CSV))
    target_row = next(row for row in target_rows if row.get('target') == PRIMARY_TARGET)
    meta_rows = _read_csv(_resolve(TARGET_META_CSV))
    meta_row = next(row for row in meta_rows if row.get('target') == PRIMARY_TARGET)
    structure_rows = _read_csv(_resolve(STRUCTURE_SOURCE_CSV))
    structure_row = next(row for row in structure_rows if row.get('target') == 'Carbonic_Anhydrase_2_Zn')
    return {
        'native_pdb_path': target_row.get('native_pdb_path', ''),
        'pdb_id': target_row.get('pdb_id', ''),
        'pocket_center': ','.join([target_row.get('pocket_x', ''), target_row.get('pocket_y', ''), target_row.get('pocket_z', '')]),
        'target_notes': target_row.get('notes', ''),
        'sequence_length': str(len(meta_row.get('sequence', '').strip())),
        'pocket_fingerprint': meta_row.get('pocket_fingerprint', ''),
        'structure_notes': structure_row.get('notes', ''),
        'structure_source_path': STRUCTURE_SOURCE_CSV,
    }


def _hint_rows_for_slot(
    queue_row: dict[str, Any],
    meta_row: dict[str, str],
    smiles_index: dict[str, list[dict[str, str]]],
    target_anchor: dict[str, str],
) -> list[dict[str, Any]]:
    packet = queue_row['packet']
    packet_step = queue_row['packet_step']
    current_ligand_id = queue_row['current_ligand_id']
    current_smiles = meta_row.get('smiles', '')
    hints: list[dict[str, Any]] = []

    hints.append(
        {
            'packet': packet,
            'packet_step': packet_step,
            'current_ligand_id': current_ligand_id,
            'current_smiles': current_smiles,
            'hint_rank': 1,
            'hint_type': 'target_anchor',
            'candidate_ligand_id': '',
            'candidate_scaffold': '',
            'repo_source_path': TARGET_PACKET_CSV,
            'provenance_hint': f"Use 1CA2 Zn-site anchor {target_anchor['pocket_center']} with {target_anchor['pocket_fingerprint']}.",
            'evidence_strength': 'target_structure_only',
            'safe_usage': 'target_packet_context_only',
            'notes': target_anchor['target_notes'],
        }
    )

    exact_matches: list[dict[str, Any]] = [
        row for row in smiles_index.get(current_smiles, [])
        if row['candidate_scaffold'] != 'template_placeholder'
    ]
    for rank, match in enumerate(exact_matches, start=2):
        hints.append(
            {
                'packet': packet,
                'packet_step': packet_step,
                'current_ligand_id': current_ligand_id,
                'current_smiles': current_smiles,
                'hint_rank': rank,
                'hint_type': 'exact_smiles_local_curated',
                'candidate_ligand_id': match['candidate_ligand_id'],
                'candidate_scaffold': match['candidate_scaffold'],
                'repo_source_path': match['repo_source_path'],
                'provenance_hint': (
                    f"Exact SMILES match already exists in {match['repo_source_count']} local ligand_meta source(s); "
                    f"first source: {match['repo_source_path']}."
                ),
                'evidence_strength': 'exact_smiles_local_curated',
                'safe_usage': 'replacement_candidate_hint',
                'notes': (
                    'Local exact-match candidate; still requires CA2-specific provenance before packet apply. '
                    f"All local sources: {', '.join(match['repo_source_paths'])}"
                ),
            }
        )

    if 'S(=O)(=O)N' in current_smiles and not exact_matches:
        weak_path, weak_ligand, weak_scaffold = WEAK_SULFONAMIDE_HINT
        hints.append(
            {
                'packet': packet,
                'packet_step': packet_step,
                'current_ligand_id': current_ligand_id,
                'current_smiles': current_smiles,
                'hint_rank': 2,
                'hint_type': 'weak_scaffold_analogy',
                'candidate_ligand_id': weak_ligand,
                'candidate_scaffold': weak_scaffold,
                'repo_source_path': weak_path,
                'provenance_hint': 'Local sulfonamide-like motif exists, but it is not CA2 evidence.',
                'evidence_strength': 'weak_scaffold_analogy',
                'safe_usage': 'motif_inspiration_only',
                'notes': 'Use only as scaffold inspiration; do not copy provenance or binding label.',
            }
        )
    return hints


def build_payload() -> dict[str, Any]:
    queue_payload = _load_json(_resolve(CURRENT_QUEUE_JSON))
    queue_rows = list(queue_payload.get('queue_rows', []))
    ca2_meta_rows = _load_ca2_meta_rows()
    meta_by_ligand = {row['ligand_id']: row for row in ca2_meta_rows}
    exclude_paths = {_resolve(path) for path in CURRENT_CA2_META.values()}
    smiles_index = _build_smiles_index(exclude_paths)
    target_anchor = _load_target_anchor()

    hint_rows: list[dict[str, Any]] = []
    slot_summary: list[dict[str, Any]] = []
    evidence_counter = Counter()
    exact_match_slots = 0
    weak_only_slots = 0
    for queue_row in queue_rows:
        meta_row = meta_by_ligand.get(queue_row['current_ligand_id'])
        if not meta_row:
            continue
        rows = _hint_rows_for_slot(queue_row, meta_row, smiles_index, target_anchor)
        hint_rows.extend(rows)
        strengths = {row['evidence_strength'] for row in rows}
        has_exact = 'exact_smiles_local_curated' in strengths
        has_weak = 'weak_scaffold_analogy' in strengths
        if has_exact:
            exact_match_slots += 1
        elif has_weak:
            weak_only_slots += 1
        slot_summary.append(
            {
                'packet': queue_row['packet'],
                'packet_step': queue_row['packet_step'],
                'current_ligand_id': queue_row['current_ligand_id'],
                'hint_count': len(rows),
                'has_exact_local_curated_match': 'yes' if has_exact else 'no',
                'has_only_target_anchor_or_weak_hint': 'yes' if (not has_exact) else 'no',
                'recommended_next_move': (
                    'Prefer exact local curated candidate review'
                    if has_exact else
                    'Use target anchor plus manual CA2 curation'
                ),
            }
        )
        for row in rows:
            evidence_counter[row['evidence_strength']] += 1

    summary = {
        'slot_count': len(slot_summary),
        'hint_row_count': len(hint_rows),
        'slots_with_exact_local_curated_match': exact_match_slots,
        'slots_with_only_target_anchor_or_weak_hint': len(slot_summary) - exact_match_slots,
        'slots_with_weak_only_hint': weak_only_slots,
        'evidence_strength_counts': dict(evidence_counter),
        'next_required_step': 'Review exact local matches first, then use target-anchor-only rows as manual curation guide for the remaining CA2 packet slots.',
    }
    return {
        'summary': summary,
        'slot_summary': slot_summary,
        'hint_rows': hint_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '# CA2 Local Candidate Source Hints',
        '',
        f"- slot_count: `{payload['summary']['slot_count']}`",
        f"- hint_row_count: `{payload['summary']['hint_row_count']}`",
        f"- slots_with_exact_local_curated_match: `{payload['summary']['slots_with_exact_local_curated_match']}`",
        f"- slots_with_only_target_anchor_or_weak_hint: `{payload['summary']['slots_with_only_target_anchor_or_weak_hint']}`",
        f"- slots_with_weak_only_hint: `{payload['summary']['slots_with_weak_only_hint']}`",
        '',
        '## Next Step',
        '',
        f"- {payload['summary']['next_required_step']}",
        '',
        '## Slot Summary',
        '',
        '| packet_step | current_ligand_id | hint_count | exact_local_match | next_move |',
        '| --- | --- | ---: | --- | --- |',
    ]
    for row in payload['slot_summary']:
        lines.append(
            f"| {row['packet_step']} | `{row['current_ligand_id']}` | {row['hint_count']} | {row['has_exact_local_curated_match']} | {row['recommended_next_move']} |"
        )
    lines.extend([
        '',
        '## Hint Rows',
        '',
        '| packet_step | hint_rank | hint_type | candidate_ligand_id | evidence_strength | repo_source_path | safe_usage |',
        '| --- | ---: | --- | --- | --- | --- | --- |',
    ])
    for row in payload['hint_rows']:
        candidate = f"`{row['candidate_ligand_id']}`" if row['candidate_ligand_id'] else ''
        lines.append(
            f"| {row['packet_step']} | {row['hint_rank']} | {row['hint_type']} | {candidate} | {row['evidence_strength']} | `{row['repo_source_path']}` | {row['safe_usage']} |"
        )
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build repo-local CA2 candidate/source/provenance hints for packet replacement.')
    parser.add_argument('--out-json', default='runs/ca2_local_candidate_source_hints_current.json')
    parser.add_argument('--out-csv', default='runs/ca2_local_candidate_source_hints_current.csv')
    parser.add_argument('--out-md', default='runs/ca2_local_candidate_source_hints_current.md')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    _write_csv(out_csv, payload['hint_rows'])
    _write_markdown(out_md, payload)


if __name__ == '__main__':
    main()
