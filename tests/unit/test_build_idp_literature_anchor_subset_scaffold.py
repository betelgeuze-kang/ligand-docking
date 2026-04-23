import json
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/betelgeuze/분자동역학')


def test_build_idp_literature_anchor_subset_scaffold(tmp_path: Path) -> None:
    base_cfg = tmp_path / 'cfg.json'
    base_cfg.write_text(json.dumps({
        'version': 'idp_v7',
        'targets': [
            {'name': 'tp53_tad', 'condition_group': 'base'},
            {'name': 'tp53_tad', 'condition_group': 'salt_high'},
            {'name': 'page4', 'condition_group': 'base'},
        ],
    }, ensure_ascii=False), encoding='utf-8')
    anchors = tmp_path / 'anchors.json'
    anchors.write_text(json.dumps({
        'targets': {
            'tp53_tad': {'source': 'literature_curated_partial'},
            'page4': {'source': 'branch_family_provisional'},
        }
    }, ensure_ascii=False), encoding='utf-8')
    out_cfg = tmp_path / 'subset.json'
    out_json = tmp_path / 'subset_summary.json'
    out_md = tmp_path / 'subset_summary.md'
    proc = subprocess.run([
        sys.executable,
        str(ROOT / 'tools' / 'build_idp_literature_anchor_subset_scaffold.py'),
        '--base-config-json', str(base_cfg),
        '--anchor-json', str(anchors),
        '--out-config-json', str(out_cfg),
        '--out-json', str(out_json),
        '--out-md', str(out_md),
    ], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    cfg = json.loads(out_cfg.read_text(encoding='utf-8'))
    assert cfg['version'] == 'idp_v7_literature_anchor_subset'
    assert len(cfg['targets']) == 2
    assert {row['name'] for row in cfg['targets']} == {'tp53_tad'}
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['literature_anchor_target_count'] == 1
    assert payload['summary']['subset_target_rows'] == 2
