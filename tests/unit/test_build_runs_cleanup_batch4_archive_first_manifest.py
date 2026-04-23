from __future__ import annotations

import json
from pathlib import Path

from tools.build_runs_cleanup_batch4_archive_first_manifest import build_payload


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def test_build_runs_cleanup_batch4_archive_first_manifest(tmp_path: Path) -> None:
    runs_dir = tmp_path / 'runs'
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage1_queue.csv', 'queue_id,target\n1,ADRB2\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage1_ligands.json', json.dumps({'count': 1, 'rows': [{'ligand_id': 'L1'}]}))
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage2_active_learning_summary.json', json.dumps({'pass': True}))
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage2_active_learning_summary.md', '# Summary\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage2_active_learning_target_weights.csv', 'target,weight\nADRB2,1.0\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage2_traj_summary.json', json.dumps({'processed_rows': 1}))
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage2_traj_manifest.csv', 'queue_id,path\n1,traj.xtc\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage3_summary.json', json.dumps({'processed_jobs': 1}))
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage3_summary.md', '# Stage3\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage3_scores.csv', 'queue_id,target\n1,ADRB2\n')

    source_review = {
        'summary': {'status': 'runs_cleanup_batch4_stage_review_manifest_ready'},
        'stage_reviews': [
            {'family_id': 'ligand_blind_gpcr', 'stage_id': 'stage1', 'source_match_count': 2, 'source_size_mb': 0.01, 'sample_artifacts': 'a; b'},
            {'family_id': 'ligand_blind_gpcr', 'stage_id': 'stage2', 'source_match_count': 3, 'source_size_mb': 0.01, 'sample_artifacts': 'c; d'},
            {'family_id': 'ligand_blind_gpcr', 'stage_id': 'stage3', 'source_match_count': 3, 'source_size_mb': 0.01, 'sample_artifacts': 'e; f'},
        ],
    }
    source_path = tmp_path / 'review.json'
    source_path.write_text(json.dumps(source_review), encoding='utf-8')

    payload = build_payload(str(runs_dir), str(source_path))

    assert payload['summary']['status'] == 'runs_cleanup_batch4_archive_first_manifest_ready'
    assert payload['summary']['candidate_group_count'] == 3
    assert payload['summary']['candidate_match_count'] == 8

    rows = {row['group_id']: row for row in payload['rows']}
    assert rows['stage1_all']['match_count'] == 2
    assert rows['stage2_light_bundle']['match_count'] == 4
    assert rows['stage3_summary_only']['match_count'] == 2
    assert rows['stage2_light_bundle']['archive_rule'] == 'all stage2 files except *_traj_manifest.csv'
    assert rows['stage3_summary_only']['archive_rule'] == 'stage3 *_summary.json/_summary.md only'
