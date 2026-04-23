import json
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/betelgeuze/분자동역학')


def test_build_idp_feature_state_literature_anchor_summary(tmp_path: Path) -> None:
    anchor_json = tmp_path / 'anchors.json'
    anchor_json.write_text(json.dumps({
        'targets': {
            'tp53_tad': {'source': 'literature_curated_partial', 'provenance': {'kind': 'paper'}},
            'page4': {'source': 'branch_family_provisional', 'provenance': {'kind': 'generated'}},
        }
    }, ensure_ascii=False), encoding='utf-8')
    tp53_json = tmp_path / 'idp_tp53_feature_state_v1_shadow_slice_current.json'
    tp53_json.write_text(json.dumps({'summary': {
        'changed_row_count': 3,
        'target_count': 8,
        'provisional_anchor_row_count': 0,
        'would_change_state_count': 3,
        'would_change_gate_count': 0,
        'anchor_feature_count': 40,
        'smoothed_feature_count': 40,
        'kalman_status': 'feature_state_v1_shadow',
        'kalman_mode': 'feature_state_v1',
    }}, ensure_ascii=False), encoding='utf-8')
    page4_json = tmp_path / 'idp_page4_feature_state_v1_shadow_slice_current.json'
    page4_json.write_text(json.dumps({'summary': {
        'changed_row_count': 0,
        'target_count': 6,
        'provisional_anchor_row_count': 6,
        'would_change_state_count': 0,
        'would_change_gate_count': 0,
        'anchor_feature_count': 0,
        'smoothed_feature_count': 0,
        'kalman_status': 'feature_state_v1_shadow',
        'kalman_mode': 'feature_state_v1',
    }}, ensure_ascii=False), encoding='utf-8')
    out_json = tmp_path / 'summary.json'
    out_csv = tmp_path / 'summary.csv'
    out_md = tmp_path / 'summary.md'
    proc = subprocess.run([
        sys.executable,
        str(ROOT / 'tools' / 'build_idp_feature_state_literature_anchor_summary.py'),
        '--anchor-json', str(anchor_json),
        '--slice-json', str(tp53_json),
        '--slice-json', str(page4_json),
        '--out-json', str(out_json),
        '--out-csv', str(out_csv),
        '--out-md', str(out_md),
    ], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['literature_anchor_slice_count'] == 1
    assert payload['summary']['provisional_slice_count'] == 1
    assert payload['summary']['literature_anchor_would_change_state_count'] == 3
    assert payload['rows'][0]['target_name'] == 'tp53_tad'
