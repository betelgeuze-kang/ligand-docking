from __future__ import annotations

import json
from pathlib import Path

from tools.build_runs_cleanup_batch5_stage_heavy_review_manifest import build_payload


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def test_build_runs_cleanup_batch5_stage_heavy_review_manifest(tmp_path: Path) -> None:
    runs_dir = tmp_path / 'runs'
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage2_traj_manifest.csv', 'queue_id,path\n1,traj.xtc\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage2_active_learning_target_weights.csv', 'target,weight\nADRB2,1.0\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage3_scores.csv', 'queue_id,target\n1,ADRB2\n')
    _write(runs_dir / 'ligand_blind_gpcr_demo_stage3_summary.json', json.dumps({'processed_jobs': 1}))

    batch4_apply = {'summary': {'status': 'runs_cleanup_batch4_archive_first_apply_report_ready'}}
    batch4_apply_path = tmp_path / 'batch4_apply.json'
    batch4_apply_path.write_text(json.dumps(batch4_apply), encoding='utf-8')

    payload = build_payload(str(runs_dir), str(batch4_apply_path))

    assert payload['summary']['status'] == 'runs_cleanup_batch5_stage_heavy_review_manifest_ready'
    assert payload['summary']['review_row_count'] == 2
    rows = {row['group_id']: row for row in payload['rows']}
    assert rows['stage2_traj_manifest_bundle']['match_count'] == 1
    assert rows['stage3_scores_bundle']['match_count'] == 1
