import json
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/betelgeuze/분자동역학')


def test_build_idp_feature_state_subset_decision(tmp_path: Path) -> None:
    holdout = tmp_path / 'holdout.json'
    disagreement = tmp_path / 'dis.json'
    failure = tmp_path / 'fail.json'
    comparison = tmp_path / 'cmp.json'
    holdout.write_text(json.dumps({'fold_count': 7, 'corrected_pass_folds': 6}, ensure_ascii=False), encoding='utf-8')
    disagreement.write_text(json.dumps({'overall': {'would_have_changed_state_count': 11, 'would_have_changed_gate_count': 0}}, ensure_ascii=False), encoding='utf-8')
    failure.write_text(json.dumps({'summary': {'fold_name': 'tau_k18', 'failure_interpretation': 'corrected path fragility'}} , ensure_ascii=False), encoding='utf-8')
    comparison.write_text(json.dumps({'decision': 'keep_all_mask_baseline'}, ensure_ascii=False), encoding='utf-8')
    out_json = tmp_path / 'out.json'
    out_md = tmp_path / 'out.md'
    proc = subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_idp_feature_state_subset_decision.py'), '--holdout-summary-json', str(holdout), '--disagreement-json', str(disagreement), '--failure-json', str(failure), '--feature-mask-comparison-json', str(comparison), '--out-json', str(out_json), '--out-md', str(out_md)], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['decision'] == 'no_go_broader_promotion'
    assert payload['summary']['blocking_fold'] == 'tau_k18'
    assert payload['summary']['would_have_changed_state_count'] == 11


def test_build_idp_feature_state_subset_decision_promotes_rg_sasa_default_when_clean(tmp_path: Path) -> None:
    holdout = tmp_path / 'holdout.json'
    disagreement = tmp_path / 'dis.json'
    failure = tmp_path / 'fail.json'
    comparison = tmp_path / 'cmp.json'
    holdout.write_text(json.dumps({'fold_count': 7, 'corrected_pass_folds': 7}, ensure_ascii=False), encoding='utf-8')
    disagreement.write_text(json.dumps({'overall': {'would_have_changed_state_count': 0, 'would_have_changed_gate_count': 0}}, ensure_ascii=False), encoding='utf-8')
    failure.write_text(json.dumps({'summary': {'fold_name': 'tau_k18', 'failure_interpretation': 'legacy blocker resolved for subset'}} , ensure_ascii=False), encoding='utf-8')
    comparison.write_text(json.dumps({'decision': 'prefer_rg_sasa_only'}, ensure_ascii=False), encoding='utf-8')
    out_json = tmp_path / 'out.json'
    out_md = tmp_path / 'out.md'
    proc = subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_idp_feature_state_subset_decision.py'), '--holdout-summary-json', str(holdout), '--disagreement-json', str(disagreement), '--failure-json', str(failure), '--feature-mask-comparison-json', str(comparison), '--out-json', str(out_json), '--out-md', str(out_md)], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['decision'] == 'go_literature_anchor_default_mask_promotion'
    assert payload['summary']['default_feature_mask'] == 'rg_sasa_only'
    assert payload['summary']['literature_anchor_default_promotion'] is True
