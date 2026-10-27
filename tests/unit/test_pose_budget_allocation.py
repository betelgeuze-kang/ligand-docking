import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

core = load('budget_under_test', ROOT / 'tools/allocate_pose_budget.py')
runner = load('budget_comparison_under_test', ROOT / 'tools/compare_pose_budget_policies.py')
FIXTURE = ROOT / 'tests/fixtures/pose_budget_synthetic.json'

def policy(strategy='round_robin', **kwargs):
    result = dict(strategy=strategy, total_budget=64, minimum_floor=2, window=4,
                  exploration_interval=4, score_direction='minimize')
    result.update(kwargs)
    return result


def complete(controller):
    while (req := controller.request()) is not None:
        controller.observe(req['token'], 'ok', 10 - controller.poses[req['pose_id']]['charged'] * 0.1, 1)
    return controller.snapshot()


class BudgetTests(unittest.TestCase):
    def test_uniform_allocation_exact_budget(self):
        report = complete(core.BudgetController(['a', 'b', 'c', 'd'], policy()))
        self.assertEqual([p['charged'] for p in report['poses']], [16] * 4)
        self.assertEqual(report['known_observation_units'], 64)
        self.assertEqual(report['available_budget'], 0)
        self.assertTrue(report['charged_floor_complete_for_all_expected_poses'])

    def test_invalid_policy_and_ids(self):
        for ids, p in [([], policy()), (['a', 'a'], policy()), (['a'], policy(total_budget=True)),
                       (['a', 'b'], policy(total_budget=3)), (['a'], policy(window=1)),
                       (['a'], policy(strategy='future_best')), (['a'], policy(total_budget=-1))]:
            with self.subTest(ids=ids, p=p), self.assertRaises(core.InputError):
                core.BudgetController(ids, p)

    def test_reserve_before_settle_and_duplicate(self):
        c = core.BudgetController(['a'], policy())
        req = c.request()
        self.assertEqual(c.snapshot()['reserved_cost'], 1)
        with self.assertRaises(core.InputError):
            c.request()
        c.observe(req['token'], 'ok', 1, 1)
        with self.assertRaises(core.InputError):
            c.observe(req['token'], 'ok', 1, 1)

    def test_invalid_receipt_atomic(self):
        c = core.BudgetController(['a'], policy())
        r = c.request()
        before = c.snapshot()
        for token, status, energy, cost in [(r['token'] + 1, 'ok', 1, 1), (True, 'ok', 1, 1),
                                          (r['token'], 'ok', float('nan'), 1),
                                          (r['token'], 'ok', 1, 2), (r['token'], 'failed', 1, 1),
                                          (r['token'], 'failed', None, None)]:
            with self.assertRaises(core.InputError):
                c.observe(token, status, energy, cost)
            self.assertEqual(c.snapshot(), before)

    def test_unknown_interruption_cost_separate(self):
        c = core.BudgetController(['a', 'b'], policy())
        r = c.request()
        c.observe(r['token'], 'interrupted', None, None)
        s = c.snapshot()
        self.assertEqual((s['charged_cost_upper_bound'], s['known_observation_units'], s['unknown_cost_upper_bound']), (1, 0, 1))
        self.assertFalse(s['all_costs_known'])
        self.assertFalse(s['charged_floor_complete_for_all_expected_poses'])
        self.assertEqual(c.request()['pose_id'], 'b')

    def test_charged_floor_not_known_or_success_floor(self):
        c = core.BudgetController(['a'], policy())
        r = c.request(); c.observe(r['token'], 'ok', 1, 1)
        r = c.request(); c.observe(r['token'], 'interrupted', None, None)
        s = c.snapshot()
        self.assertTrue(s['charged_floor_complete_for_all_expected_poses'])
        self.assertFalse(s['known_cost_floor_complete_for_all_expected_poses'])
        self.assertFalse(s['successful_observation_floor_complete_for_all_expected_poses'])

    def test_failure_charged_and_terminal(self):
        c = core.BudgetController(['a'], policy())
        r = c.request()
        c.observe(r['token'], 'failed', None, 1)
        self.assertIsNone(c.request())
        self.assertEqual(c.snapshot()['known_observation_units'], 1)
        self.assertEqual(c.snapshot()['expected_poses'], 1)

    def test_zero_cost_exhaustion_keeps_budget(self):
        c = core.BudgetController(['a'], policy())
        r = c.request()
        c.observe(r['token'], 'exhausted', None, 0)
        self.assertIsNone(c.request())
        s = c.snapshot()
        self.assertEqual(s['unspent_budget_before_reservation'], 64)
        self.assertEqual(s['termination_reason'], 'all_poses_terminal')

    def test_floor_all_strategies(self):
        for strategy in core.STRATEGIES:
            c = core.BudgetController(['a', 'b', 'c', 'd'], policy(strategy))
            chosen = []
            for _ in range(8):
                req = c.request(); chosen.append(req['pose_id'])
                c.observe(req['token'], 'ok', -100 if req['pose_id'] == 'a' else 100, 1)
            self.assertEqual(chosen, ['a', 'b', 'c', 'd'] * 2)

    def test_low_energy_minimize_and_maximize(self):
        for direction, expected in [('minimize', 'a'), ('maximize', 'b')]:
            c = core.BudgetController(['a', 'b'], policy('low_energy', minimum_floor=1, score_direction=direction))
            for _ in range(2):
                r = c.request(); c.observe(r['token'], 'ok', 1 if r['pose_id'] == 'a' else 2, 1)
            self.assertEqual(c.request()['pose_id'], expected)

    def test_exploration_every_four_postfloor_decisions(self):
        c = core.BudgetController(['a', 'b'], policy('improvement_with_exploration'))
        for _ in range(4):
            r = c.request(); c.observe(r['token'], 'ok', 10 - c.poses[r['pose_id']]['charged'], 1)
        for index in range(1, 9):
            r = c.request()
            if index % 4 == 0:
                self.assertEqual(r['reason'], 'reserved_exploration')
            c.observe(r['token'], 'ok', 10 - c.poses[r['pose_id']]['charged'], 1)

    def test_flat_energy_falls_back_to_exploration(self):
        c = core.BudgetController(['a', 'b'], policy('improvement_with_exploration'))
        for _ in range(4):
            r = c.request(); c.observe(r['token'], 'ok', 3, 1)
        self.assertEqual(c.request()['reason'], 'no_gain_exploration')

    def test_bounded_large_energy_no_overflow(self):
        c = core.BudgetController(['a'], policy('improvement_with_exploration'))
        for i in range(5):
            r = c.request(); c.observe(r['token'], 'ok', 1e100 if i == 0 else -1e100, 1)
        json.dumps(c.snapshot(), allow_nan=False)

    def test_input_label_rejected(self):
        data = dict(schema='pose_budget_observations/1', context=dict(model='m', chemical_state='s', energy_unit='toy'),
                    pose_ids=['a'], policy=policy(), observations=[], target='a')
        with self.assertRaises(core.InputError):
            core.analyze(data)

    def test_cli_contract_receipt_replay_and_pose_binding(self):
        data = dict(schema='pose_budget_observations/1', context=dict(model='m', chemical_state='s', energy_unit='toy'),
                    pose_ids=['a'], policy=policy(), observations=[dict(token=1, pose_id='a', status='ok', energy=1, actual_cost=1)])
        r = core.analyze(data)
        self.assertEqual(r['known_observation_units'], 1)
        self.assertEqual(r['pending_request']['token'], 2)
        data['observations'][0]['pose_id'] = 'b'
        with self.assertRaises(core.InputError):
            core.analyze(data)

    def test_strict_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'[' * 30 + b'0' + b']' * 30,
                    b' ' * (core.MAX_BYTES + 1)):
            with self.assertRaises(core.InputError):
                core.load_bytes(raw)

    def test_request_copy_no_internal_mutation(self):
        c = core.BudgetController(['a'], policy())
        r = c.request(); r['pose_id'] = 'evil'
        self.assertEqual(c.snapshot()['pending_request']['pose_id'], 'a')

    def test_compare_frozen_protocol_all_cases(self):
        r = runner.compare(FIXTURE.read_bytes())
        self.assertEqual(r['expected_runs'], 24)
        self.assertEqual(len(r['results']), 24)
        for row in r['results']:
            self.assertLessEqual(row['charged_cost_upper_bound'], 64)
            self.assertEqual(row['charged_cost_upper_bound'], row['known_observation_units'] + row['unknown_cost_upper_bound'])
            if row['scenario'] == 'all_exhausted':
                self.assertEqual(row['charged_cost_upper_bound'], 8)
                self.assertFalse(row['evaluation']['synthetic_target_marker_observed'])
            else:
                self.assertEqual(row['charged_cost_upper_bound'], 64)

    def test_protocol_digest_prevents_retuning(self):
        with self.assertRaises(runner._core.InputError):
            runner.compare(FIXTURE.read_bytes() + b' ')

    def test_labels_do_not_change_decisions(self):
        p = json.loads(FIXTURE.read_text())
        scenario = copy.deepcopy(p['scenarios'][0])
        before = runner.run_case(scenario, 'low_energy', p)
        scenario['target'] = dict(pose='p0', step=4)
        after = runner.run_case(scenario, 'low_energy', p)
        self.assertEqual(before['decisions'], after['decisions'])

    def test_interrupted_target_not_success(self):
        p = json.loads(FIXTURE.read_text())
        scenario = copy.deepcopy(p['scenarios'][6])
        scenario['target'] = dict(pose='p2', step=3)
        r = runner.run_case(scenario, 'round_robin', p)
        self.assertFalse(r['evaluation']['synthetic_target_marker_observed'])
        self.assertEqual(r['unknown_cost_upper_bound'], 1)

    def test_comparison_deterministic(self):
        raw = FIXTURE.read_bytes()
        self.assertEqual(runner.compare(raw), runner.compare(raw))


if __name__ == '__main__':
    unittest.main()
