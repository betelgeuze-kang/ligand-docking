#!/usr/bin/env python3
"""Independent observed-prefix allocation; not an engine or fixed64 adapter."""
import argparse
import hashlib
import json
import math
import sys

MAX_BYTES = 2 * 1024 * 1024
STRATEGIES = ('round_robin', 'low_energy', 'improvement_with_exploration')


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'invalid integer')
    return value


def finite(value):
    require(type(value) in (int, float), 'invalid number')
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise InputError('invalid number') from None
    require(math.isfinite(value) and abs(value) <= 1e100, 'number outside domain')
    return value


def fields(value, keys):
    require(isinstance(value, dict) and set(value) == set(keys), 'invalid fields')


def pairs(values):
    result = {}
    for key, value in values:
        require(key not in result, 'duplicate key')
        result[key] = value
    return result


def load_bytes(raw):
    require(len(raw) <= MAX_BYTES, 'byte budget')
    try:
        obj = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(InputError('nonfinite JSON')))
    except (ValueError, UnicodeError, RecursionError):
        raise InputError('invalid JSON') from None
    stack = [(obj, 0)]
    while stack:
        value, depth = stack.pop()
        require(depth <= 24, 'depth budget')
        if isinstance(value, dict):
            stack.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            stack.extend((v, depth + 1) for v in value)
    return obj


class BudgetController:
    """A serial, reserve-before-evaluate experimental allocation controller.

    Caller controls execution. Receipts bind claims, not producer authenticity.
    No optimizer state, reference labels or unobserved suffix is accepted.
    """
    def __init__(self, pose_ids, policy):
        require(isinstance(pose_ids, list) and 1 <= len(pose_ids) <= 128, 'pose count')
        require(all(isinstance(p, str) and 0 < len(p) <= 128 and
                    all(ord(c) >= 32 for c in p) for p in pose_ids), 'pose id')
        require(len(set(pose_ids)) == len(pose_ids), 'duplicate pose')
        fields(policy, ('strategy', 'total_budget', 'minimum_floor', 'window',
                        'exploration_interval', 'score_direction'))
        require(policy['strategy'] in STRATEGIES, 'strategy')
        require(policy['score_direction'] in ('minimize', 'maximize'), 'score direction')
        integer(policy['total_budget'], 1, 100000)
        integer(policy['minimum_floor'], 1, 32)
        integer(policy['window'], 2, 32)
        integer(policy['exploration_interval'], 2, 32)
        require(policy['total_budget'] >= len(pose_ids) * policy['minimum_floor'], 'floor infeasible')
        self.policy = dict(policy)
        self.ids = tuple(pose_ids)
        self.poses = {p: {'charged': 0, 'known_observation_units': 0, 'unknown_cost_upper_bound': 0,
                          'status': 'ready', 'successes': 0, 'last_energy': None,
                          'best_energy': None, 'history': []} for p in self.ids}
        self.spent = self.known = self.unknown = self.attempts = self.post_floor = 0
        self.pending = None
        self.decisions = []

    def _oriented(self, value):
        return value if self.policy['score_direction'] == 'minimize' else -value

    def _gain(self, pose):
        h = pose['history'][-self.policy['window']:]
        if len(h) < 2:
            return 0.0
        # Initial point is an observation, not improvement from an invented value.
        first = h[0]['best_after']
        last = h[-1]['best_after']
        cost = sum(row['cost'] for row in h[1:])
        if first is None or last is None or not cost:
            return 0.0
        return max(0.0, (self._oriented(first) - self._oriented(last)) / cost)

    def request(self):
        require(self.pending is None, 'pending request must settle')
        ready = [p for p in self.ids if self.poses[p]['status'] == 'ready']
        if self.spent >= self.policy['total_budget'] or not ready:
            return None
        require(self.attempts < self.policy['total_budget'] + len(self.ids), 'attempt limit')
        rank = {p: i for i, p in enumerate(self.ids)}
        least = lambda ids: min(ids, key=lambda p: (self.poses[p]['charged'], rank[p]))
        floor = [p for p in ready if self.poses[p]['charged'] < self.policy['minimum_floor']]
        if floor:
            selected, reason = least(floor), 'minimum_floor'
        else:
            self.post_floor += 1
            strategy = self.policy['strategy']
            if strategy == 'round_robin':
                selected, reason = least(ready), 'equal_allocation'
            elif strategy == 'low_energy':
                observed = [p for p in ready if self.poses[p]['last_energy'] is not None]
                if not observed:
                    selected, reason = least(ready), 'no_energy_exploration'
                else:
                    selected = min(observed, key=lambda p: (self._oriented(self.poses[p]['last_energy']), rank[p]))
                    reason = 'lowest_observed_energy'
            elif self.post_floor % self.policy['exploration_interval'] == 0:
                selected, reason = least(ready), 'reserved_exploration'
            else:
                gains = {p: self._gain(self.poses[p]) for p in ready}
                if max(gains.values()) <= 0:
                    selected, reason = least(ready), 'no_gain_exploration'
                else:
                    selected = min(ready, key=lambda p: (-gains[p], rank[p]))
                    reason = 'observed_improvement'
        self.attempts += 1
        self.pending = {'token': self.attempts, 'pose_id': selected, 'reserved_cost': 1, 'reason': reason}
        return dict(self.pending)

    def observe(self, token, status, energy=None, actual_cost=1):
        require(self.pending is not None and type(token) is int and token == self.pending['token'], 'stale request')
        require(status in ('ok', 'failed', 'exhausted', 'interrupted'), 'receipt status')
        if status == 'ok':
            require(type(actual_cost) is int and actual_cost == 1, 'success cost')
            energy = finite(energy)
        else:
            require(energy is None, 'failed observation cannot contain energy')
        if actual_cost is None:
            require(status == 'interrupted', 'unknown cost only for interrupted call')
            charged, known, unknown = 1, 0, 1
        else:
            integer(actual_cost, 0, 1)
            require(status != 'exhausted' or actual_cost == 0, 'exhaustion costs zero')
            charged, known, unknown = actual_cost, actual_cost, 0
        require(self.spent + charged <= self.policy['total_budget'], 'budget overrun')
        pending = self.pending
        p = self.poses[pending['pose_id']]
        p['charged'] += charged
        p['known_observation_units'] += known
        p['unknown_cost_upper_bound'] += unknown
        if status == 'ok':
            p['successes'] += 1
            p['last_energy'] = energy
            if p['best_energy'] is None or self._oriented(energy) < self._oriented(p['best_energy']):
                p['best_energy'] = energy
        else:
            p['status'] = status
        p['history'].append({'cost': charged, 'best_after': p['best_energy']})
        self.spent += charged
        self.known += known
        self.unknown += unknown
        self.decisions.append(dict(pending, status=status, charged_cost=charged,
                                   known_observation_units=known, unknown_cost_upper_bound=unknown, energy=energy))
        self.pending = None

    def snapshot(self):
        rows = [{key: value for key, value in self.poses[p].items() if key != 'history'} | {'pose_id': p}
                for p in self.ids]
        ready = sum(row['status'] == 'ready' for row in rows)
        reserved = 1 if self.pending is not None else 0
        reason = 'pending' if reserved else ('budget_exhausted' if self.spent == self.policy['total_budget']
                  else ('all_poses_terminal' if not ready else 'awaiting_request'))
        return {'schema': 'pose_budget_report/1', 'policy': dict(self.policy), 'expected_poses': len(self.ids),
                'poses': rows, 'pose_status_counts': {status: sum(p['status'] == status for p in rows)
                    for status in ('ready', 'failed', 'exhausted', 'interrupted')},
                'unattempted_pose_count': sum(p['successes'] == 0 and p['charged'] == 0 and p['status'] == 'ready' for p in rows),
                'charged_cost_upper_bound': self.spent, 'known_observation_units': self.known,
                'unknown_cost_upper_bound': self.unknown, 'reserved_cost': reserved,
                'available_budget': self.policy['total_budget'] - self.spent - reserved,
                'unspent_budget_before_reservation': self.policy['total_budget'] - self.spent,
                'attempts': self.attempts, 'termination_reason': reason,
                'charged_floor_complete_for_all_expected_poses': all(p['charged'] >= self.policy['minimum_floor'] for p in rows),
                'known_cost_floor_complete_for_all_expected_poses': all(p['known_observation_units'] >= self.policy['minimum_floor'] for p in rows),
                'successful_observation_floor_complete_for_all_expected_poses': all(p['successes'] >= self.policy['minimum_floor'] for p in rows),
                'all_costs_known': self.unknown == 0, 'pending_request': dict(self.pending) if self.pending else None,
                'decisions': [dict(d) for d in self.decisions], 'engine_evaluations_performed_by_tool': 0,
                'scientific_validation': False, 'producer_authenticity_verified': False,
                'fixed_mixed64_modified': False}


def analyze(obj):
    fields(obj, ('schema', 'context', 'pose_ids', 'policy', 'observations'))
    require(obj['schema'] == 'pose_budget_observations/1', 'schema')
    fields(obj['context'], ('model', 'chemical_state', 'energy_unit'))
    require(all(isinstance(x, str) and 0 < len(x) <= 256 for x in obj['context'].values()), 'context')
    observations = obj['observations']
    require(isinstance(observations, list) and len(observations) <= 100128, 'observation budget')
    controller = BudgetController(obj['pose_ids'], obj['policy'])
    for record in observations:
        fields(record, ('token', 'pose_id', 'status', 'energy', 'actual_cost'))
        req = controller.request()
        require(req is not None and record['pose_id'] == req['pose_id'], 'unexpected pose observation')
        controller.observe(record['token'], record['status'], record['energy'], record['actual_cost'])
    controller.request()
    report = controller.snapshot()
    report['context_sha256'] = hashlib.sha256(json.dumps(obj['context'], sort_keys=True,
                                                        separators=(',', ':')).encode()).hexdigest()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='observed receipts JSON, no future traces or labels')
    args = parser.parse_args(argv)
    try:
        with open(args.input, 'rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        report = analyze(load_bytes(raw))
        report['input_sha256'] = hashlib.sha256(raw).hexdigest()
        output = json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False)
        require(len(output.encode()) <= 8 * MAX_BYTES, 'output budget')
        print(output)
        return 0
    except (InputError, OSError, ValueError, OverflowError, RecursionError):
        print('pose budget input rejected: invalid, inaccessible, or over budget', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
