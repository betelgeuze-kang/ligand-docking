#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch3_review_manifest import FAMILY_SPECS
from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve, _file_size, _summarize_artifact
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = 'runs'
DEFAULT_SOURCE_REVIEW_JSON = 'runs/runs_cleanup_batch4_stage_review_manifest_current.json'
DEFAULT_OUT_JSON = 'runs/runs_cleanup_batch4_archive_first_manifest_current.json'
DEFAULT_OUT_CSV = 'runs/runs_cleanup_batch4_archive_first_manifest_current.csv'
DEFAULT_OUT_MD = 'runs/runs_cleanup_batch4_archive_first_manifest_current.md'
ARCHIVE_FIRST = 'archive_first'

FAMILY_BY_ID = {str(f['family_id']): f for f in FAMILY_SPECS}

CANDIDATE_GROUP_SPECS: list[dict[str, str]] = [
    {
        'group_id': 'stage1_all',
        'stage_id': 'stage1',
        'group_label': 'stage1 queue/input bundle',
        'reason': 'Sampled queue and summary files confirm these are reproducible input artifacts; archive the whole stage1 bundle before touching heavier downstream stage files.',
    },
    {
        'group_id': 'stage2_light_bundle',
        'stage_id': 'stage2',
        'group_label': 'stage2 light bundle excluding trajectory manifests',
        'reason': 'Archive stage2 summaries, hard-score tables, weights, and lightweight trajectory status files now; keep only the bulky stage2 trajectory manifests for batch5.',
    },
    {
        'group_id': 'stage3_summary_only',
        'stage_id': 'stage3',
        'group_label': 'stage3 summary-only light bundle',
        'reason': 'Archive stage3 summaries now and leave the heavier score CSV bundles on review hold for batch5.',
    },
]


def _matches(name: str, group_id: str) -> bool:
    if group_id == 'stage1_all':
        return '_stage1_' in name
    if group_id == 'stage2_light_bundle':
        return '_stage2_' in name and not name.endswith('_traj_manifest.csv')
    if group_id == 'stage3_summary_only':
        return '_stage3_' in name and (name.endswith('_summary.json') or name.endswith('_summary.md'))
    return False


def build_payload(runs_dir: str, source_review_json: str) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    source_review = json.loads(_resolve(source_review_json).read_text(encoding='utf-8'))
    stage_review_map = {
        (str(row['family_id']), str(row['stage_id'])): row
        for row in source_review.get('stage_reviews', [])
    }

    family_rows: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    total_bytes = 0

    for family in FAMILY_SPECS:
        family_id = str(family['family_id'])
        files = sorted(path for path in runs_root.glob(str(family['family_glob'])) if path.is_file())
        family_candidate_bytes = 0
        family_candidate_count = 0
        for spec in CANDIDATE_GROUP_SPECS:
            matched = [path for path in files if _matches(path.name, spec['group_id'])]
            if not matched:
                continue
            sample_files = matched[:3]
            size_mb = round(sum(_file_size(path) for path in matched) / (1024 * 1024), 2)
            total_bytes += sum(_file_size(path) for path in matched)
            family_candidate_bytes += sum(_file_size(path) for path in matched)
            family_candidate_count += len(matched)
            stage_review = stage_review_map.get((family_id, spec['stage_id']), {})
            rows.append(
                {
                    'family_id': family_id,
                    'family_label': family['family_label'],
                    'group_id': spec['group_id'],
                    'group_label': spec['group_label'],
                    'stage_id': spec['stage_id'],
                    'recommended_disposition': ARCHIVE_FIRST,
                    'match_count': len(matched),
                    'size_mb': size_mb,
                    'sample_artifacts': '; '.join(path.name for path in sample_files),
                    'sample_highlights': ' | '.join(f"{path.name}: {_summarize_artifact(path)}" for path in sample_files),
                    'source_stage_match_count': int(stage_review.get('source_match_count', 0) or 0),
                    'source_stage_size_mb': float(stage_review.get('source_size_mb', 0.0) or 0.0),
                    'source_stage_sample_artifacts': str(stage_review.get('sample_artifacts', '')),
                    'archive_rule': (
                        'all stage1 files' if spec['group_id'] == 'stage1_all' else
                        'all stage2 files except *_traj_manifest.csv' if spec['group_id'] == 'stage2_light_bundle' else
                        'stage3 *_summary.json/_summary.md only'
                    ),
                    'reason': spec['reason'],
                }
            )
        family_rows.append(
            {
                'family_id': family_id,
                'family_label': family['family_label'],
                'candidate_group_count': sum(1 for row in rows if row['family_id'] == family_id),
                'candidate_match_count': family_candidate_count,
                'candidate_size_mb': round(family_candidate_bytes / (1024 * 1024), 2),
            }
        )

    summary = {
        'status': 'runs_cleanup_batch4_archive_first_manifest_ready',
        'source_review_json': str(_resolve(source_review_json)),
        'source_review_status': str(source_review.get('summary', {}).get('status', 'unknown')),
        'runs_dir': str(runs_root),
        'family_count': len(family_rows),
        'candidate_group_count': len(rows),
        'candidate_match_count': sum(int(row['match_count']) for row in rows),
        'candidate_size_gb': round(total_bytes / (1024 * 1024 * 1024), 2),
        'next_required_step': 'Apply this manifest to archive stage1 bundles plus the stage2 light bundle and stage3 summaries, then generate a batch5 review manifest for the remaining stage2 trajectory manifests and stage3 score CSVs.',
    }
    return {'summary': summary, 'families': family_rows, 'rows': rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload['summary']
    lines = [
        '# Runs Cleanup Batch4 Archive-First Manifest',
        '',
        f"- status: `{s['status']}`",
        f"- source_review_json: `{s['source_review_json']}`",
        f"- source_review_status: `{s['source_review_status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- family_count: `{s['family_count']}`",
        f"- candidate_group_count: `{s['candidate_group_count']}`",
        f"- candidate_match_count: `{s['candidate_match_count']}`",
        f"- candidate_size_gb: `{s['candidate_size_gb']}`",
        '',
        '## Family Totals',
        '',
        '| family_id | candidate_group_count | candidate_match_count | candidate_size_mb |',
        '| --- | ---: | ---: | ---: |',
    ]
    for row in payload['families']:
        lines.append(f"| `{row['family_id']}` | `{row['candidate_group_count']}` | `{row['candidate_match_count']}` | `{row['candidate_size_mb']}` |")
    lines.extend(['', '## Archive-First Candidates', '', '| family_id | group_id | stage_id | match_count | size_mb | archive_rule |', '| --- | --- | --- | ---: | ---: | --- |'])
    for row in payload['rows']:
        lines.append(f"| `{row['family_id']}` | `{row['group_id']}` | `{row['stage_id']}` | `{row['match_count']}` | `{row['size_mb']}` | `{row['archive_rule']}` |")
    lines.extend(['', '## Detail', ''])
    for row in payload['rows']:
        lines.extend([
            f"### {row['family_id']} / {row['group_id']}",
            '',
            f"- group_label: `{row['group_label']}`",
            f"- stage_id: `{row['stage_id']}`",
            f"- match_count: `{row['match_count']}`",
            f"- size_mb: `{row['size_mb']}`",
            f"- recommended_disposition: `{row['recommended_disposition']}`",
            f"- archive_rule: `{row['archive_rule']}`",
            f"- source_stage_match_count: `{row['source_stage_match_count']}`",
            f"- source_stage_size_mb: `{row['source_stage_size_mb']}`",
            f"- sample_artifacts: `{row['sample_artifacts']}`",
            f"- source_stage_sample_artifacts: `{row['source_stage_sample_artifacts']}`",
            f"- sample_highlights: {row['sample_highlights']}",
            f"- reason: {row['reason']}",
            '',
        ])
    lines.extend(['## Next Step', '', f"- {s['next_required_step']}", ''])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build a batch4 archive-first manifest from sampled stage review artifacts.')
    parser.add_argument('--runs-dir', default=DEFAULT_RUNS_DIR)
    parser.add_argument('--source-review-json', default=DEFAULT_SOURCE_REVIEW_JSON)
    parser.add_argument('--out-json', default=DEFAULT_OUT_JSON)
    parser.add_argument('--out-csv', default=DEFAULT_OUT_CSV)
    parser.add_argument('--out-md', default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.runs_dir, args.source_review_json)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_csv_rows(out_csv, payload['rows'])
    _write_markdown(out_md, payload)


if __name__ == '__main__':
    main()
