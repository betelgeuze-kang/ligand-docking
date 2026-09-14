"""Prespecified v2 tie/arm ordering; real similarity worker without physics."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tools.product import compare_prepared_candidate_policies as comparison
from tests.unit.test_prepared_candidate_comparison import _protocol

def ordered(tmp_path):
    protocol = _protocol(tmp_path, calls=1)
    protocol.update(schema_version=comparison.ORDERED_SCHEMA, selection_seed=42, tie_policy='seeded_pool_order', arm_order=list(reversed(comparison.ARMS)))
    return protocol

def test_v1_order_is_retained():
    frozen = {'protocol': {'schema_version': comparison.SCHEMA}, 'pool': ['z', 'a']}
    assert comparison._prediction_order(frozen, {'z': 7.0, 'a': 7.0}) == ['a', 'z']
    assert comparison._execution_order(frozen['protocol']) == comparison.ARMS

@pytest.mark.parametrize('seed', [0, 1, 42, 4294967295])
def test_v2_ties_ignore_id_names_not_scores(seed):
    protocol = {'schema_version': comparison.ORDERED_SCHEMA, 'selection_seed': seed}
    one = {'protocol': protocol, 'pool': ['a', 'z', 'best']}
    two = {'protocol': protocol, 'pool': ['z', 'a', 'best']}
    first = comparison._prediction_order(one, {'a': 7.0, 'z': 7.0, 'best': 8.0})
    second = comparison._prediction_order(two, {'a': 7.0, 'z': 7.0, 'best': 8.0})
    assert first[0] == second[0] == 'best'
    assert [one['pool'].index(r) for r in first] == [two['pool'].index(r) for r in second]
    assert first == comparison._prediction_order(one, {'best': 8.0, 'z': 7.0, 'a': 7.0})

@pytest.mark.parametrize('change', ['seed_bool', 'seed_negative', 'seed_huge', 'missing_seed', 'duplicate_arm', 'missing_arm', 'unknown_arm', 'tie', 'v1_extra'])
def test_order_contract_is_rejected_before_execution(tmp_path, change):
    p = ordered(tmp_path / 'input')
    if change == 'seed_bool':
        p['selection_seed'] = True
    elif change == 'seed_negative':
        p['selection_seed'] = -1
    elif change == 'seed_huge':
        p['selection_seed'] = 2 ** 32
    elif change == 'missing_seed':
        p.pop('selection_seed')
    elif change == 'duplicate_arm':
        p['arm_order'] = ['engine'] * 4
    elif change == 'missing_arm':
        p['arm_order'].pop()
    elif change == 'unknown_arm':
        p['arm_order'][0] = 'cuda'
    elif change == 'tie':
        p['tie_policy'] = 'best_observed_labels'
    else:
        p['schema_version'] = comparison.SCHEMA
    with pytest.raises(ValueError):
        comparison.run(p, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()

def test_order_configuration_changes_frozen_binding(tmp_path):
    p = ordered(tmp_path / 'input')
    first, _ = comparison.freeze(p)
    assert comparison.freeze(p)[0] == first
    second = copy.deepcopy(p)
    second['selection_seed'] += 1
    assert comparison.freeze(second)[0] != first
    second = copy.deepcopy(p)
    second['arm_order'].reverse()
    assert comparison.freeze(second)[0] != first
    assert first['protocol']['arm_order'] == p['arm_order']

def test_actual_similarity_worker_never_imports_torch_or_physics(tmp_path):
    p = ordered(tmp_path / 'input')
    frozen, _ = comparison.freeze(p)
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'similarity').mkdir()
    comparison.publish(run / 'frozen.json', {'payload': frozen, 'sha256': comparison.sha(frozen)})
    code = "import json,sys,time,importlib.abc\nclass Block(importlib.abc.MetaPathFinder):\n    def find_spec(self,fullname,path=None,target=None):\n        if fullname=='torch' or fullname.startswith(('torch.','betelgeuze_engine.','betelgeuze_engine_v2.')):\n            raise AssertionError('pure similarity loaded '+fullname)\nsys.meta_path.insert(0,Block())\nfrom pathlib import Path\nfrom tools.product.compare_prepared_candidate_policies import worker\nworker(Path(sys.argv[1]),'similarity',time.monotonic()+20)\nprint(json.dumps({'torch_loaded':'torch' in sys.modules,'engine_loaded':any(k.startswith('betelgeuze_engine.') for k in sys.modules)}))\n"
    root = Path(comparison.__file__).resolve().parents[2]
    env = {**os.environ, 'PYTHONPATH': str(root), 'OPENBLAS_NUM_THREADS': '1'}
    child = subprocess.run([sys.executable, '-c', code, str(run)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout) == {'torch_loaded': False, 'engine_loaded': False}
    result = json.loads((run / 'similarity/worker-complete.json').read_text())
    assert result['engine_calls'] == 0
    assert len(list((run / 'similarity').glob('*.row.json'))) == 3

def test_actual_v2_four_arms_order_resume_and_changed_seed(tmp_path):
    p = ordered(tmp_path / 'input')
    result = comparison.run(p, tmp_path / 'run')
    times = [json.loads((tmp_path / 'run' / arm / 'attempt.json').read_text())['started_monotonic'] for arm in p['arm_order']]
    assert times == sorted(times) and len(set(times)) == 4
    assert all((a['denominator']['requested'] == 4 for a in result['arms'].values()))
    assert all((a['cost']['status'] == 'complete' for a in result['arms'].values()))
    assert comparison.run(p, tmp_path / 'run', resume=True) == result
    changed = copy.deepcopy(p)
    changed['selection_seed'] += 1
    with pytest.raises(ValueError, match='resume_'):
        comparison.run(changed, tmp_path / 'run', resume=True)
    assert not result['scientifically_validated'] and (not result['product_ranking_enabled'])
