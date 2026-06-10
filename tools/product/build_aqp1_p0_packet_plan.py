#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / 'runs'
CONFIG = ROOT / 'config'


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open('r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    gap_rows = [r for r in read_csv(CONFIG / 'transporter_membrane_expansion_gap_checklist_v1.csv') if r.get('target_id') == 'Aquaporin_1']
    ref_rows = [r for r in read_csv(CONFIG / 'ligand_binding_reference_blind_aqp1_v1.csv') if r.get('target') == 'AQP1_TRANSPORT_BLIND']
    split_rows = [r for r in read_csv(CONFIG / 'ligand_eval_splits_blind_aqp1_v1.csv') if r.get('target') == 'AQP1_TRANSPORT_BLIND']
    target_rows = [r for r in read_csv(CONFIG / 'real_drug_targets_blind_aqp1_v1.csv') if r.get('target') == 'AQP1_TRANSPORT_BLIND']
    target_meta_rows = [r for r in read_csv(CONFIG / 'ligand_target_metadata_blind_aqp1_v1.csv') if r.get('target') == 'AQP1_TRANSPORT_BLIND']
    packet_rows: List[Dict[str, str]] = []

    def add(step, artifact, status, blocker, next_action, repo_path, detail):
        packet_rows.append({
            'step_id': step,
            'artifact': artifact,
            'status': status,
            'blocker': blocker,
            'next_action': next_action,
            'repo_path': repo_path,
            'detail': detail,
        })

    target_row = target_rows[0] if target_rows else {}
    pocket_zero = all(str(target_row.get(k,'')).strip() in {'0','0.0'} for k in ('pocket_x','pocket_y','pocket_z')) if target_row else True
    seq_placeholder = 'TEMPLATE_SEQ' in str(target_meta_rows[0].get('sequence','')) if target_meta_rows else True
    add('aqp1_target_native', 'target_native_csv', 'todo' if pocket_zero else 'ready', 'pocket_centroid_placeholder' if pocket_zero else '', 'freeze AQP1 pocket centroid and update native target row', 'config/real_drug_targets_blind_aqp1_v1.csv', f"pdb_id={target_row.get('pdb_id','')} native={target_row.get('native_pdb_path','')}")
    add('aqp1_target_meta', 'target_meta_csv', 'todo' if seq_placeholder else 'ready', 'sequence_placeholder' if seq_placeholder else '', 'replace template sequence and finalize pocket fingerprint note', 'config/ligand_target_metadata_blind_aqp1_v1.csv', f"target_family={target_meta_rows[0].get('target_family','') if target_meta_rows else ''}")

    binder_ids = {
        str(r.get("ligand_id", "")).strip()
        for r in ref_rows
        if str(r.get("is_binder", "")).strip() == "1"
    }
    binder_ref_rows = [r for r in ref_rows if str(r.get("is_binder", "")).strip() == "1"]
    binder_meta_rows = [
        r for r in read_csv(CONFIG / "ligand_meta_blind_aqp1_v1.csv") if str(r.get("ligand_id", "")).strip() in binder_ids
    ]

    def _reference_needs_curation(row: Dict[str, str]) -> bool:
        source = str(row.get("source", "")).lower()
        return (
            "placeholder" in str(row.get("ligand_id", "")).lower()
            or "placeholder" in source
            or not str(row.get("reference_binding_kcal_mol", "")).strip()
            or "functional_ic50_derived_surrogate" in source
            or "not_direct_binding" in source
        )

    placeholder_ref = sum(1 for r in binder_ref_rows if _reference_needs_curation(r))
    ref_blocker = "claim_safe_direct_binding_kcal_missing" if placeholder_ref else ""
    add(
        "aqp1_ligand_reference",
        "ligand_reference_csv",
        "todo" if placeholder_ref else "ready",
        ref_blocker if placeholder_ref else "",
        "replace placeholder binders/non-binders with curated AQP1 packet",
        "config/ligand_binding_reference_blind_aqp1_v1.csv",
        f"row_count={len(ref_rows)} binder_rows={len(binder_ref_rows)} claim_safe_blocker_rows={placeholder_ref}",
    )

    placeholder_split = sum(1 for r in split_rows if "placeholder" in r.get("ligand_id", ""))
    add(
        "aqp1_eval_split",
        "eval_split_csv",
        "todo" if placeholder_split else "ready",
        "placeholder_split_roles" if placeholder_split else "",
        "freeze fit/far_ood_eval roles after curated ligand packet is ready",
        "config/ligand_eval_splits_blind_aqp1_v1.csv",
        f"row_count={len(split_rows)} placeholder_rows={placeholder_split}",
    )

    placeholder_meta = sum(
        1
        for r in binder_meta_rows
        if "template_placeholder" in r.get("scaffold", "") or "placeholder" in r.get("ligand_id", "")
    )
    add(
        "aqp1_ligand_meta",
        "ligand_meta_csv",
        "todo" if placeholder_meta else "ready",
        "placeholder_meta_rows" if placeholder_meta else "",
        "replace placeholder smiles/physchem rows with curated AQP1 ligand metadata",
        "config/ligand_meta_blind_aqp1_v1.csv",
        f"row_count={len(binder_meta_rows)} placeholder_rows={placeholder_meta}",
    )

    add('aqp1_profile_json', 'profile_json', 'ready', '', 'keep dry_run until packet blockers are closed, then freeze donor policy', 'config/ligand_htvs_blind_aqp1_v1.json', 'profile scaffold exists with dry_run=true')
    add('aqp1_smoke_binding', 'smoke_task_binding', 'todo', 'core_packet_not_frozen', 'reuse core profile for smoke only after core packet is frozen', 'config/external_validation_transporter_membrane_sets_v1_template.json', 'set3 smoke remains dependent on set1 core packet')
    add('transporter_fit_donor_policy', 'fit_donor_policy', 'todo', 'family_level_policy_unfrozen', 'decide whether EGFR_KINASE remains temporary donor or membrane-family donor replaces it', 'docs/transporter_membrane_expansion_scaffold_plan.md', 'current scaffold reuses EGFR_KINASE donor rows')

    summary = {
        'target_id': 'Aquaporin_1',
        'task_id': 'aqp1_core_full',
        'step_count': len(packet_rows),
        'ready_count': sum(1 for r in packet_rows if r['status'] == 'ready'),
        'todo_count': sum(1 for r in packet_rows if r['status'] == 'todo'),
        'p0_count': sum(1 for r in packet_rows if r['artifact'] in {'target_native_csv','ligand_reference_csv','eval_split_csv','ligand_meta_csv','target_meta_csv','profile_json','fit_donor_policy'}),
        'next_priority_steps': [r['step_id'] for r in packet_rows if r['status'] == 'todo'][:5],
    }

    out_json = RUNS / 'aqp1_p0_packet_plan_current.json'
    out_csv = RUNS / 'aqp1_p0_packet_plan_current.csv'
    out_md = RUNS / 'aqp1_p0_packet_plan_current.md'
    write_json(out_json, {'summary': summary, 'rows': packet_rows})
    write_csv(out_csv, packet_rows, ['step_id','artifact','status','blocker','next_action','repo_path','detail'])
    md = [
        '# AQP1 P0 Packet Plan',
        '',
        f"- target: `{summary['target_id']}`",
        f"- task: `{summary['task_id']}`",
        f"- ready: `{summary['ready_count']}`",
        f"- todo: `{summary['todo_count']}`",
        f"- next_priority_steps: `{', '.join(summary['next_priority_steps'])}`",
        '',
        '| step | artifact | status | blocker | next_action |',
        '| --- | --- | --- | --- | --- |',
    ]
    for r in packet_rows:
        md.append(f"| `{r['step_id']}` | `{r['artifact']}` | `{r['status']}` | `{r['blocker'] or '-'}` | {r['next_action']} |")
    out_md.write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
