#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SET_DEFS = [
    {
        'set_id': 'set1_core_blind',
        'title': 'Core Blind Submission Set',
        'purpose': 'Primary external submission set for strongest currently frozen blind or release-grade evidence across the four domains.',
        'domains': [
            {
                'domain': 'kinase',
                'target': 'EGFR_KINASE',
                'evidence_type': 'definition_only_disjoint_external_style',
                'note': 'Uses disjoint kinase/protease external-style panel definition and control packet; no frozen large blind ranking summary currently archived for this axis.',
                'files': [
                    'config/ligand_htvs_commercial_validation_no_leak_v2_seq03.json',
                    'config/ligand_eval_splits_disjoint_v2.csv',
                    'config/ligand_binding_reference_disjoint_v2.csv',
                    'docs/wetlab_packets/egfr_kinase_pilot_controls.csv',
                    'docs/wetlab_packets/hiv1_protease_pilot_controls.csv',
                ],
            },
            {
                'domain': 'gpcr',
                'target': 'ADRB2_GPCR_BLIND',
                'evidence_type': 'blind_result',
                'files': [
                    'runs/ligand_blind_gpcr_full_v4_2026-03-11_r1_stage5_ranking_summary.json',
                    'runs/ligand_blind_gpcr_full_v4_2026-03-11_r1_stage5_ranking_summary.md',
                    'config/real_drug_targets_blind_gpcr_adrb2_v1.csv',
                    'config/ligand_eval_splits_blind_gpcr_adrb2_chembl50_v1.csv',
                    'config/ligand_binding_reference_blind_gpcr_adrb2_v1.csv',
                ],
            },
            {
                'domain': 'ion_channel',
                'target': 'TRPV1_ION_CHANNEL_BLIND',
                'evidence_type': 'blind_result',
                'files': [
                    'runs/ligand_blind_trpv1_chembl20_npz_v6_2026-03-11_r1_stage5_ranking_summary.json',
                    'runs/ligand_blind_trpv1_chembl20_npz_v6_2026-03-11_r1_stage5_ranking_summary.md',
                    'config/real_drug_targets_blind_trpv1_v1.csv',
                    'config/ligand_eval_splits_blind_trpv1_chembl20_v1.csv',
                    'config/ligand_binding_reference_blind_trpv1_chembl20_v1.csv',
                    'docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv',
                    'docs/wetlab_packets/trpv1_ion_channel_normalization_notes.md',
                    'docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv',
                ],
            },
            {
                'domain': 'idp',
                'target': 'IDP_3BEAD_RELEASE_CURRENT',
                'evidence_type': 'release_grade_holdout',
                'files': [
                    'runs/idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3_summary.json',
                    'runs/idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3_release_regression.json',
                    'runs/idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3_release_manifest.json',
                    'runs/idp_3bead_release_report_current.md',
                ],
            },
        ],
    },
    {
        'set_id': 'set2_expanded_ood',
        'title': 'Expanded OOD Submission Set',
        'purpose': 'Broader OOD stress set using larger public blind ligand expansions and the current full IDP release with calibrated diagnostics.',
        'domains': [
            {
                'domain': 'kinase',
                'target': 'EGFR_KINASE',
                'evidence_type': 'definition_only_disjoint_strict',
                'note': 'Strict external-style disjoint profile; suitable as protocol evidence, not yet a frozen large blind ranking result.',
                'files': [
                    'config/ligand_htvs_commercial_validation_disjoint_strict_v2.json',
                    'config/ligand_eval_splits_disjoint_v2.csv',
                    'config/ligand_binding_reference_disjoint_v2.csv',
                    'docs/wetlab_packets/egfr_kinase_pilot_controls.csv',
                    'docs/wetlab_packets/hiv1_protease_pilot_controls.csv',
                ],
            },
            {
                'domain': 'gpcr',
                'target': 'ADRB2_GPCR_BLIND',
                'evidence_type': 'blind_result',
                'files': [
                    'runs/ligand_blind_gpcr_chembl50_full_2026-03-11_r1_p0_n10000_r1_stage5_ranking_summary.json',
                    'runs/ligand_blind_gpcr_chembl50_full_2026-03-11_r1_p0_n10000_r1_stage5_ranking_summary.md',
                    'config/ligand_eval_splits_blind_gpcr_adrb2_chembl50_v1.csv',
                    'config/ligand_binding_reference_blind_gpcr_adrb2_chembl50_v1.csv',
                ],
            },
            {
                'domain': 'ion_channel',
                'target': 'TRPV1_ION_CHANNEL_BLIND',
                'evidence_type': 'blind_result',
                'files': [
                    'runs/ligand_blind_trpv1_chembl50_npz_v6_2026-03-11_r1_stage5_ranking_summary.json',
                    'runs/ligand_blind_trpv1_chembl50_npz_v6_2026-03-11_r1_stage5_ranking_summary.md',
                    'config/ligand_eval_splits_blind_trpv1_chembl50_v1.csv',
                    'config/ligand_binding_reference_blind_trpv1_chembl50_v1.csv',
                    'docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv',
                ],
            },
            {
                'domain': 'idp',
                'target': 'IDP_3BEAD_RELEASE_CURRENT',
                'evidence_type': 'release_grade_holdout_plus_diagnostics',
                'files': [
                    'runs/idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3_summary.json',
                    'runs/idp_3bead_release_report_current.md',
                    'runs/idp_3bead_global_aggregation_calibrator_current.json',
                    'runs/idp_3bead_global_aggregation_dashboard_current.html',
                    'runs/idp_3bead_global_aggregation_compare_current.html',
                ],
            },
        ],
    },
    {
        'set_id': 'set3_operational_smoke',
        'title': 'Operational Smoke Submission Set',
        'purpose': 'Fast reproducibility set for sharing a small but repeatable cross-domain check alongside the larger submission bundles.',
        'domains': [
            {
                'domain': 'kinase',
                'target': 'EGFR_KINASE',
                'evidence_type': 'definition_only_disjoint_smoke',
                'note': 'Small external-style smoke profile for the kinase/protease axis; this is an operational packet, not the primary performance claim.',
                'files': [
                    'config/ligand_htvs_commercial_validation_disjoint_strict_poscounter_smoke_v2.json',
                    'config/ligand_eval_splits_disjoint_v2.csv',
                    'config/ligand_binding_reference_disjoint_v2.csv',
                    'docs/wetlab_packets/egfr_kinase_pilot_controls.csv',
                    'docs/wetlab_packets/hiv1_protease_pilot_controls.csv',
                ],
            },
            {
                'domain': 'gpcr',
                'target': 'ADRB2_GPCR_BLIND',
                'evidence_type': 'blind_smoke_result',
                'files': [
                    'runs/ligand_blind_gpcr_smoke_r2_2026-03-10_p0_n64_r1_stage5_ranking_summary.json',
                    'runs/ligand_blind_gpcr_smoke_r2_2026-03-10_p0_n64_r1_stage5_ranking_summary.md',
                ],
            },
            {
                'domain': 'ion_channel',
                'target': 'TRPV1_ION_CHANNEL_BLIND',
                'evidence_type': 'blind_smoke_result',
                'files': [
                    'runs/ligand_blind_trpv1_chembl20_smoke_2026-03-11_r2_p0_n64_r1_stage5_ranking_summary.json',
                    'runs/ligand_blind_trpv1_chembl20_smoke_2026-03-11_r2_p0_n64_r1_stage5_ranking_summary.md',
                    'docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv',
                ],
            },
            {
                'domain': 'idp',
                'target': 'IDP_3BEAD_SMOKE_CURRENT',
                'evidence_type': 'release_smoke_result',
                'files': [
                    'runs/idp_3bead_release_smoke_summary_current.json',
                    'runs/idp_3bead_release_smoke_regression_current.json',
                    'runs/idp_3bead_release_smoke_global_aggregation_dashboard_current.html',
                ],
            },
        ],
    },
]


def _load_metrics(path: Path) -> dict[str, Any]:
    if not path.exists() or path.suffix != '.json':
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    metrics = data.get('metrics', {}) if isinstance(data, dict) else {}
    out = {}
    for k in ['pass', 'all_fold_pass', 'combined_gate_pass', 'corrected_pass_folds', 'baseline_pass_folds']:
        if k in data:
            out[k] = data[k]
    for k in ['roc_auc', 'pr_auc', 'ef1', 'bedroc_alpha20']:
        if k in metrics:
            out[k] = metrics[k]
    return out


def _copy(src: Path, dst_dir: Path) -> dict[str, Any]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return {'src': str(src.resolve()), 'dst': str(dst.resolve()), 'size_bytes': dst.stat().st_size}


def build(out_dir: Path, tag: str) -> dict[str, Any]:
    root = ROOT
    bundle_root = out_dir / f'external_validation_submission_sets_{tag}'
    bundle_root.mkdir(parents=True, exist_ok=True)
    overview_sets = []

    for set_def in SET_DEFS:
        set_dir = bundle_root / set_def['set_id']
        files_dir = set_dir / 'files'
        files_dir.mkdir(parents=True, exist_ok=True)
        domain_rows = []
        copied = []
        for domain in set_def['domains']:
            domain_dst = files_dir / domain['domain']
            file_rows = []
            metrics = {}
            for rel in domain['files']:
                src = root / rel
                if not src.exists():
                    raise FileNotFoundError(src)
                rec = _copy(src, domain_dst)
                copied.append(rec)
                file_rows.append(rec)
                if not metrics and src.suffix == '.json':
                    metrics = _load_metrics(src)
            row = {
                'domain': domain['domain'],
                'target': domain['target'],
                'evidence_type': domain['evidence_type'],
                'note': domain.get('note', ''),
                'files': file_rows,
                'metrics': metrics,
            }
            domain_rows.append(row)

        manifest = {
            'set_id': set_def['set_id'],
            'title': set_def['title'],
            'purpose': set_def['purpose'],
            'bundle_dir': str(set_dir.resolve()),
            'domains': domain_rows,
            'file_count': len(copied),
        }
        (set_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
        lines = [
            f"# {set_def['title']}",
            '',
            f"- set_id: `{set_def['set_id']}`",
            f"- purpose: {set_def['purpose']}",
            f"- file_count: `{len(copied)}`",
            '',
            '## Domains',
        ]
        for row in domain_rows:
            lines.extend([
                f"### `{row['domain']}` / `{row['target']}`",
                f"- evidence_type: `{row['evidence_type']}`",
            ])
            if row['note']:
                lines.append(f"- note: {row['note']}")
            if row['metrics']:
                for k, v in row['metrics'].items():
                    lines.append(f"- {k}: `{v}`")
            lines.append('- files:')
            lines.extend([f"  - `{file['dst']}`" for file in row['files']])
            lines.append('')
        (set_dir / 'manifest.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        zip_path = shutil.make_archive(str(set_dir), 'zip', root_dir=set_dir)
        overview_sets.append({
            'set_id': set_def['set_id'],
            'title': set_def['title'],
            'purpose': set_def['purpose'],
            'manifest_json': str((set_dir / 'manifest.json').resolve()),
            'manifest_md': str((set_dir / 'manifest.md').resolve()),
            'archive_zip': str(Path(zip_path).resolve()),
        })

    overview = {
        'tag': tag,
        'bundle_root': str(bundle_root.resolve()),
        'sets': overview_sets,
        'note': 'Kinase axis currently uses external-style disjoint control definitions rather than a frozen large blind ranking summary. This is explicitly surfaced in each set manifest.',
    }
    (bundle_root / 'overview.json').write_text(json.dumps(overview, indent=2, ensure_ascii=False), encoding='utf-8')
    md_lines = [
        '# External Validation Submission Sets',
        '',
        f'- tag: `{tag}`',
        f'- bundle_root: `{bundle_root.resolve()}`',
        '',
        '## Sets',
    ]
    for s in overview_sets:
        md_lines.extend([
            f"### `{s['set_id']}`",
            f"- title: {s['title']}",
            f"- purpose: {s['purpose']}",
            f"- manifest_json: `{s['manifest_json']}`",
            f"- manifest_md: `{s['manifest_md']}`",
            f"- archive_zip: `{s['archive_zip']}`",
            '',
        ])
    md_lines.extend([
        '## Caveat',
        '',
        '- kinase axis is currently represented by external-style disjoint panel definitions and control packets, not by a frozen large blind ranking result.',
        '- GPCR, ion-channel, and IDP axes do include frozen result artifacts in these bundles.',
        '',
    ])
    (bundle_root / 'overview.md').write_text('\n'.join(md_lines), encoding='utf-8')
    return overview


def main() -> int:
    ap = argparse.ArgumentParser(description='Build 3 cross-domain external validation submission sets.')
    ap.add_argument('--out-dir', default='runs/external_validation_submission', type=str)
    ap.add_argument('--tag', default='2026-03-21_r1', type=str)
    args = ap.parse_args()
    overview = build(Path(args.out_dir), str(args.tag).strip() or '2026-03-21_r1')
    print(json.dumps(overview, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
