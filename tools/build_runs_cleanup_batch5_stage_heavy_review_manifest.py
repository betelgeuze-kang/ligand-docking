#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch3_review_manifest import FAMILY_SPECS
from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve, _file_size, _summarize_artifact
from tools.builder_table_utils import write_csv_rows

DEFAULT_RUNS_DIR = 'runs'
DEFAULT_BATCH4_APPLY_JSON = 'runs/runs_cleanup_batch4_archive_first_apply_report_current.json'
DEFAULT_OUT_JSON = 'runs/runs_cleanup_batch5_stage_heavy_review_manifest_current.json'
DEFAULT_OUT_CSV = 'runs/runs_cleanup_batch5_stage_heavy_review_manifest_current.csv'
DEFAULT_OUT_MD = 'runs/runs_cleanup_batch5_stage_heavy_review_manifest_current.md'

HEAVY_GROUP_SPECS: list[dict[str, str]] = [
    {
        'group_id': 'stage2_traj_manifest_bundle',
        'stage_id': 'stage2',
        'group_label': 'stage2 trajectory manifest bundle',
        'reason': 'Keep only the bulky stage2 trajectory manifest CSVs on review hold after batch4, because they dominate the remaining stage2 footprint.',
    },
    {
        'group_id': 'stage3_scores_bundle',
        'stage_id': 'stage3',
        'group_label': 'stage3 score CSV bundle',
        'reason': 'Largest remaining score bundle after batch4; review separately before archival because it preserves the final per-ligand score surface.',
    },
]


def _matches(name: str, group_id: str) -> bool:
    if group_id == 'stage2_traj_manifest_bundle':
        return '_stage2_' in name and name.endswith('_traj_manifest.csv')
    if group_id == 'stage3_scores_bundle':
        return '_stage3_' in name and not (name.endswith('_summary.json') or name.endswith('_summary.md'))
    return False


def build_payload(runs_dir: str, batch4_apply_json: str) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    batch4_apply = json.loads(_resolve(batch4_apply_json).read_text(encoding='utf-8'))
    family_rows: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    total_bytes = 0

    for family in FAMILY_SPECS:
        family_id = str(family['family_id'])
        files = sorted(path for path in runs_root.glob(str(family['family_glob'])) if path.is_file())
        family_heavy_bytes = 0
        family_heavy_count = 0
        for spec in HEAVY_GROUP_SPECS:
            matched = [path for path in files if _matches(path.name, spec['group_id'])]
            if not matched:
                continue
            sample_files = matched[:3]
            group_bytes = sum(_file_size(path) for path in matched)
            total_bytes += group_bytes
            family_heavy_bytes += group_bytes
            family_heavy_count += len(matched)
            rows.append(
                {
                    'family_id': family_id,
                    'family_label': family['family_label'],
                    'group_id': spec['group_id'],
                    'group_label': spec['group_label'],
                    'stage_id': spec['stage_id'],
                    'match_count': len(matched),
                    'size_mb': round(group_bytes / (1024 * 1024), 2),
                    'recommended_disposition': 'review_for_archive_after_sampling',
                    'sample_artifacts': '; '.join(path.name for path in sample_files),
                    'sample_highlights': ' | '.join(f"{path.name}: {_summarize_artifact(path)}" for path in sample_files),
                    'reason': spec['reason'],
                }
            )
        family_rows.append(
            {
                'family_id': family_id,
                'family_label': family['family_label'],
                'remaining_heavy_group_count': sum(1 for row in rows if row['family_id'] == family_id),
                'remaining_heavy_match_count': family_heavy_count,
                'remaining_heavy_size_mb': round(family_heavy_bytes / (1024 * 1024), 2),
            }
        )

    summary = {
        'status': 'runs_cleanup_batch5_stage_heavy_review_manifest_ready',
        'source_batch4_apply_json': str(_resolve(batch4_apply_json)),
        'source_batch4_apply_status': str(batch4_apply.get('summary', {}).get('status', 'unknown')),
        'runs_dir': str(runs_root),
        'family_count': len(family_rows),
        'review_row_count': len(rows),
        'remaining_heavy_file_count': sum(int(row['match_count']) for row in rows),
        'remaining_heavy_size_gb': round(total_bytes / (1024 * 1024 * 1024), 2),
        'next_required_step': 'Review the remaining stage2 trajectory-manifest CSVs and stage3 score CSV bundles, then archive them only after family-level signoff.',
    }
    return {'summary': summary, 'families': family_rows, 'rows': rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload['summary']
    lines = [
        '# Runs Cleanup Batch5 Stage-Heavy Review Manifest',
        '',
        f"- status: `{s['status']}`",
        f"- source_batch4_apply_json: `{s['source_batch4_apply_json']}`",
        f"- source_batch4_apply_status: `{s['source_batch4_apply_status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- family_count: `{s['family_count']}`",
        f"- review_row_count: `{s['review_row_count']}`",
        f"- remaining_heavy_file_count: `{s['remaining_heavy_file_count']}`",
        f"- remaining_heavy_size_gb: `{s['remaining_heavy_size_gb']}`",
        '',
        '## Family Totals',
        '',
        '| family_id | remaining_heavy_group_count | remaining_heavy_match_count | remaining_heavy_size_mb |',
        '| --- | ---: | ---: | ---: |',
    ]
    for row in payload['families']:
        lines.append(f"| `{row['family_id']}` | `{row['remaining_heavy_group_count']}` | `{row['remaining_heavy_match_count']}` | `{row['remaining_heavy_size_mb']}` |")
    lines.extend(['', '## Review Rows', '', '| family_id | group_id | stage_id | match_count | size_mb | recommended_disposition |', '| --- | --- | --- | ---: | ---: | --- |'])
    for row in payload['rows']:
        lines.append(f"| `{row['family_id']}` | `{row['group_id']}` | `{row['stage_id']}` | `{row['match_count']}` | `{row['size_mb']}` | `{row['recommended_disposition']}` |")
    lines.extend(['', '## Detail', ''])
    for row in payload['rows']:
        lines.extend([
            f"### {row['family_id']} / {row['group_id']}",
            '',
            f"- group_label: `{row['group_label']}`",
            f"- stage_id: `{row['stage_id']}`",
            f"- match_count: `{row['match_count']}`",
            f"- size_mb: `{row['size_mb']}`",
            f"- sample_artifacts: `{row['sample_artifacts']}`",
            f"- sample_highlights: {row['sample_highlights']}",
            f"- reason: {row['reason']}",
            '',
        ])
    lines.extend(['## Next Step', '', f"- {s['next_required_step']}", ''])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build a batch5 review manifest for remaining stage2/stage3 heavy artifacts.')
    parser.add_argument('--runs-dir', default=DEFAULT_RUNS_DIR)
    parser.add_argument('--batch4-apply-json', default=DEFAULT_BATCH4_APPLY_JSON)
    parser.add_argument('--out-json', default=DEFAULT_OUT_JSON)
    parser.add_argument('--out-csv', default=DEFAULT_OUT_CSV)
    parser.add_argument('--out-md', default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.runs_dir, args.batch4_apply_json)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_csv_rows(out_csv, payload['rows'])
    _write_markdown(out_md, payload)


if __name__ == '__main__':
    main()
