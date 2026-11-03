import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from stagnation_search_controller import Controller, ContractError
import experiment_stagnation_search as runner

FIXTURE = ROOT / "tests/fixtures/stagnation_search_protocol.json"


def consume(c, energy=1, accepted=True):
    action = c.issue()
    c.observe(action["action_id"], status="ok", evaluations=1, energy=energy, accepted=accepted)
    return action


class ControllerTests(unittest.TestCase):
    def test_initialization_charged(self):
        c = Controller("continuation", 1)
        self.assertEqual(consume(c)["kind"], "initialize")
        self.assertIsNone(c.issue())
        self.assertEqual(c.snapshot()["known_evaluations"], 1)

    def test_pending_reservation(self):
        c = Controller("continuation", 2)
        action = c.issue()
        action["kind"] = "forged"
        self.assertEqual(c.snapshot()["available_unreserved_evaluations"], 1)
        with self.assertRaises(ContractError):
            c.issue()
        c.observe(1, status="ok", evaluations=1, energy=2, accepted=True)
        self.assertEqual(c.snapshot()["action_counts"]["initialize"], 1)

    def test_stale_receipt_atomic(self):
        c = Controller("continuation", 2)
        c.issue()
        before = c.snapshot()
        with self.assertRaises(ContractError):
            c.observe(2, status="ok", evaluations=1, energy=0, accepted=True)
        self.assertEqual(c.snapshot(), before)

    def test_invalid_receipts_atomic(self):
        for kwargs in ({"status": []}, {"evaluations": 2}, {"evaluations": True}, {"energy": float("nan")}, {"accepted": 1}, {"status": "failed", "energy": 3}):
            c = Controller("continuation", 2)
            c.issue()
            receipt = dict(status="ok", evaluations=1, energy=2, accepted=True)
            receipt.update(kwargs)
            before = c.snapshot()
            with self.assertRaises(ContractError):
                c.observe(1, **receipt)
            self.assertEqual(c.snapshot(), before)

    def test_interruption_charged_conservatively(self):
        c = Controller("continuation", 1)
        c.issue()
        c.observe(1, status="interrupted", evaluations=None)
        s = c.snapshot()
        self.assertEqual((s["charged_evaluations"], s["known_evaluations"], s["unknown_evaluation_allowance"]), (1, 0, 1))
        self.assertIsNone(c.issue())

    def test_unavailable_bounded_by_actions(self):
        c = Controller("continuation", 10, maximum_actions=2)
        for i in (1, 2):
            c.issue()
            c.observe(i, status="unavailable", evaluations=0)
        self.assertIsNone(c.issue())
        self.assertEqual(c.snapshot()["stop_reason"], "action_limit")
        self.assertEqual(c.snapshot()["remaining_evaluations"], 10)

    def test_failure_charged(self):
        c = Controller("continuation", 1)
        c.issue()
        c.observe(1, status="failed", evaluations=1)
        self.assertEqual(c.snapshot()["outcome_counts"]["failed"], 1)
        self.assertIsNone(c.issue())

    def test_rejection_charged_preserves_state(self):
        c = Controller("continuation", 2)
        consume(c, 1)
        consume(c, 5, False)
        s = c.snapshot()
        self.assertEqual((s["current_energy"], s["best_observed_energy"], s["rejected"], s["known_evaluations"]), (1, 1, 1, 2))

    def test_stagnation_escape_and_reset(self):
        c = Controller("stagnation_escape", 8, patience=2)
        consume(c, 1)
        self.assertEqual(consume(c, 1)["kind"], "refine")
        consume(c, 1)
        self.assertEqual(consume(c, 4)["kind"], "escape")
        self.assertEqual(c.snapshot()["stale_observations"], 0)
        self.assertEqual(consume(c, 3)["kind"], "refine")
        self.assertEqual(c.snapshot()["best_observed_energy"], 1)

    def test_improvement_resets_stagnation(self):
        c = Controller("stagnation_escape", 5, patience=2)
        for energy in (3, 3, 2, 2):
            self.assertNotEqual(consume(c, energy)["kind"], "escape")
        self.assertEqual(c.snapshot()["stale_observations"], 1)

    def test_uniform_fixed_interval(self):
        c = Controller("uniform_restart", 5, restart_interval=2)
        self.assertEqual([consume(c, v)["kind"] for v in (4, 3, 2, 5, 4)],
                         ["initialize", "refine", "refine", "restart", "refine"])

    def test_invalid_parameters(self):
        for kwargs in ({"budget": True}, {"budget": 0}, {"budget": 2, "patience": 0}, {"budget": 2, "improvement_epsilon": float("inf")}, {"budget": 2, "maximum_actions": -1}):
            with self.assertRaises(ContractError):
                Controller("continuation", **kwargs)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.p = runner.load_protocol(FIXTURE.read_bytes())
        self.p["seeds"] = self.p["seeds"][:2]

    def test_known_analytic_minima(self):
        for name, x in (("convex", .75), ("planted_double_well", -1), ("periodic_wells", 0)):
            self.assertEqual(runner.objective(name, x), (0, 0))

    def test_derivatives_independent_fd(self):
        for name in runner.OBJECTIVES:
            for x in (-2.4, -.2, .9, 2.1):
                e, g = runner.objective(name, x)
                h = 1e-5
                fd = (runner.objective(name, x+h)[0]-runner.objective(name, x-h)[0])/(2*h)
                self.assertAlmostEqual(g, fd, delta=2e-7)

    def test_exact_oracle_call_cost(self):
        original = runner.objective
        observed = []
        def wrapped(name, x):
            observed.append((name, x))
            return original(name, x)
        with patch.object(runner, "objective", wrapped):
            r = runner.experiment(self.p)
        self.assertEqual(len(observed), 3 * 2 * 3 * 120)
        for case in r["cases"]:
            self.assertEqual(case["actual_joint_ef_calls"], 120)
            self.assertTrue(case["complete_budget"])
            self.assertEqual(case["controller"]["charged_evaluations"], 120)
            self.assertIsNone(case["controller"]["pending_action_id"])

    def test_determinism_pairing_order_independence(self):
        a = runner.experiment(self.p)
        self.assertEqual(a, runner.experiment(self.p))
        q = copy.deepcopy(self.p)
        q["policies"].reverse()
        b = runner.experiment(q)
        key = lambda row: (row["objective"], row["seed"], row["policy"])
        self.assertEqual(sorted(a["cases"], key=key), sorted(b["cases"], key=key))
        for name in runner.OBJECTIVES:
            for seed in self.p["seeds"]:
                initial = {r["initial_x"] for r in a["cases"] if r["objective"] == name and r["seed"] == seed}
                self.assertEqual(len(initial), 1)

    def test_goal_threshold_does_not_change_trajectory(self):
        a = runner.experiment(self.p)
        self.p["success_threshold"] = 1
        b = runner.experiment(self.p)
        for x, y in zip(a["cases"], b["cases"]):
            x.pop("success"); y.pop("success")
            self.assertEqual(x, y)

    def test_archive_matches_analytic_energy(self):
        for case in runner.experiment(self.p)["cases"]:
            self.assertEqual(case["best_energy"], runner.objective(case["objective"], case["best_x"])[0])
            self.assertLessEqual(case["best_energy"], case["final_energy"])

    def test_protocol_parser_rejects_malformed(self):
        for raw in (b'{"schema":1,"schema":2}', b'{"x":NaN}', b'[]', b'x'*65537):
            with self.assertRaises(ContractError):
                runner.load_protocol(raw)
        for key, value in (("seeds", [True]), ("budget", 1001), ("domain", [-3, float("inf")]), ("objectives", ["arbitrary_code"]), ("success_threshold", True)):
            q = copy.deepcopy(self.p); q[key] = value
            with self.assertRaises(ContractError):
                runner.validate_protocol(q)

    def test_action_limit_preserved(self):
        self.p["maximum_actions"] = 3
        for case in runner.experiment(self.p)["cases"]:
            self.assertEqual(case["actual_joint_ef_calls"], 3)
            self.assertFalse(case["complete_budget"])
            self.assertEqual(case["controller"]["stop_reason"], "action_limit")

    def test_cli_digest_and_no_site(self):
        digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        command = [sys.executable, "-S", str(ROOT / "tools/experiment_stagnation_search.py"), str(FIXTURE), "--expected-sha256"]
        good = subprocess.run(command+[digest], capture_output=True, text=True, timeout=30)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["expected_cases"], 180)
        bad = subprocess.run(command+["0"*64], capture_output=True, text=True, timeout=30)
        self.assertEqual(bad.returncode, 2)
        self.assertNotIn(str(FIXTURE), bad.stderr)


if __name__ == "__main__":
    unittest.main()
