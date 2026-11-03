#!/usr/bin/env python3
"""Frozen synthetic prefix comparison; never molecular docking evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

_spec = importlib.util.spec_from_file_location('_pose_budget_controller', Path(__file__).with_name('allocate_pose_budget.py'))
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
PROTOCOL_SHA256 = '074b43c3fb028bfd186a559841ad99836a012dc8efab3ebcf03692fc900cba82'


def observation(curve, step):
    """Curve: start,slope,delay,plateau,length,charged-failure-step."""
    start, slope, delay, plateau, length, failed_at = curve
    if failed_at == step:
        return 'failed', None, 1
    if step > length:
        return 'exhausted', None, 0
    return 'ok', start - slope * max(0, min(step, plateau) - delay), 1


def run_case(scenario, strategy, protocol):
    pose_ids = ['p' + str(i) for i in range(len(scenario['curves']))]
    policy = {'strategy': strategy, 'total_budget': protocol['budget'],
              'minimum_floor': protocol['minimum_floor'], 'window': protocol['window'],
              'exploration_interval': protocol['exploration_interval'], 'score_direction': 'minimize'}
    controller = _core.BudgetController(pose_ids, policy)
    prefix = {p: 0 for p in pose_ids}
    observed_successes = {p: [] for p in pose_ids}
    while True:
        request = controller.request()
        if request is None:
            break
        pid = request['pose_id']
        prefix[pid] += 1
        step = prefix[pid]
        if scenario.get('interrupt') == {'pose': pid, 'step': step}:
            status, energy, cost = 'interrupted', None, None
        else:
            status, energy, cost = observation(scenario['curves'][int(pid[1:])], step)
        controller.observe(request['token'], status, energy, cost)
        if status == 'ok':
            observed_successes[pid].append(step)
    report = controller.snapshot()
    # Evaluation-only labels never enter controller construction or observations.
    target = scenario['target']
    report['evaluation'] = {'synthetic_target_marker_observed': target['step'] in observed_successes[target['pose']],
                            'target_pose': target['pose'], 'target_step': target['step'],
                            'not_molecular_recovery': True, 'unobserved_marker_is_failure': False}
    report['scenario'] = scenario['id']
    report['prefix_steps_revealed'] = prefix
    return report


def compare(raw):
    _core.require(hashlib.sha256(raw).hexdigest() == PROTOCOL_SHA256, 'frozen protocol mismatch')
    protocol = _core.load_bytes(raw)
    results = [run_case(scenario, strategy, protocol) for scenario in protocol['scenarios']
               for strategy in protocol['strategies']]
    summaries = []
    for strategy in protocol['strategies']:
        selected = [r for r in results if r['policy']['strategy'] == strategy]
        summaries.append({'strategy': strategy, 'expected_scenarios': len(protocol['scenarios']),
                          'observed_scenarios': len(selected),
                          'synthetic_marker_observed_cases': sum(r['evaluation']['synthetic_target_marker_observed'] for r in selected),
                          'charged_cost_upper_bound': sum(r['charged_cost_upper_bound'] for r in selected),
                          'known_observation_units': sum(r['known_observation_units'] for r in selected),
                          'unknown_cost_upper_bound': sum(r['unknown_cost_upper_bound'] for r in selected),
                          'underused_budget_cases': sum(r['charged_cost_upper_bound'] < protocol['budget'] for r in selected)})
    return {'schema': 'pose_budget_synthetic_comparison/1', 'protocol_sha256': PROTOCOL_SHA256,
            'expected_runs': len(protocol['scenarios']) * len(protocol['strategies']), 'results': results,
            'summary': summaries, 'future_trace_available_to_controller': False,
            'molecular_evaluations': 0, 'scientific_validation': False,
            'replay_assumption': 'separable deterministic per-pose prefixes; no unrecorded suffix extrapolation',
            'cost_unit': 'one revealed synthetic observation unit with modeled E/F cost; unknown interrupted cost charged conservatively; no E/F engine executed',
            'claims': 'hand-constructed policy cases, not docking accuracy or throughput'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('protocol')
    args = parser.parse_args(argv)
    try:
        with open(args.protocol, 'rb') as stream:
            raw = stream.read(_core.MAX_BYTES + 1)
        result = compare(raw)
        output = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)
        _core.require(len(output.encode()) <= 8 * _core.MAX_BYTES, 'output budget')
        print(output)
        return 0
    except (_core.InputError, OSError, ValueError, OverflowError, RecursionError):
        print('synthetic pose budget protocol rejected', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
