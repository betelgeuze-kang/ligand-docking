"""Dependency-free control-flow and execution-receipt contract tests.

These tests execute the real worker and immutable temporary-file publication.
Scientific imports, priority generation, and evaluators are test doubles: this is
not molecular runtime, numerical accuracy, or scientific validation. The suite
uses only unittest and is also collectible by pytest in the full repository.

Run locally from the repository root with::

    python -m unittest discover -s tests/unit -p test_candidate_execution_receipts.py -v
"""

from contextlib import ExitStack, contextmanager
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


# Loading the one stdlib-only module by path makes this suite runnable in a
# proposal checkout without importing the full project's optional dependencies.
_MODULE = Path(__file__).resolve().parents[2] / "tools/product/compare_prepared_candidate_policies.py"
_SPEC = importlib.util.spec_from_file_location("_receipt_contract_comparison", _MODULE)
comparison = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(comparison)


def _json_read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _module(name, **attributes):
    result = types.ModuleType(name)
    result.__dict__.update(attributes)
    return result


class ExecutionReceiptContractTests(unittest.TestCase):
    """Control-flow and receipt contracts; all scientific calculations are fake."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.now = 101.0
        self.start = 100.0
        self.deadline = 110.0
        self.torch = _module("torch", set_num_threads=mock.Mock())
        self.evaluate = mock.Mock(return_value={
            "denominator": {"requested": 1, "evaluated": 1},
            "rows": [{"result": {"quantities": {"cross_total_kcal_per_mol": -2.5}}}],
        })
        self.check_report = mock.Mock(return_value={
            "status": "passed", "denominator": {"requested": 1, "passed": 1},
        })
        self.d3 = _module("betelgeuze_product.cpu_refinement_v1_2.policy_adapter",
                          evaluate=mock.Mock(return_value={"synthetic": "d3-report"}),
                          summarize=mock.Mock(return_value={
                              "status": "evaluated", "score": -3.0, "reason": None,
                          }))
        self.modules = {
            "torch": self.torch,
            "betelgeuze_engine": _module("betelgeuze_engine", __path__=[]),
            "betelgeuze_engine.product": _module("betelgeuze_engine.product", __path__=[]),
            "betelgeuze_engine.product.prepared_rigid_poses": _module(
                "betelgeuze_engine.product.prepared_rigid_poses",
                evaluate_rigid_pose_request=self.evaluate),
            "tools.product.verify_prepared_cross_numerics": _module(
                "tools.product.verify_prepared_cross_numerics", check_report=self.check_report),
            "betelgeuze_product": _module("betelgeuze_product", __path__=[]),
            "betelgeuze_product.cpu_refinement_v1_2": _module(
                "betelgeuze_product.cpu_refinement_v1_2", __path__=[], policy_adapter=self.d3),
            "betelgeuze_product.cpu_refinement_v1_2.policy_adapter": self.d3,
        }

    def prepare(self, *, arm="engine", order=("a", "b"), cap=10,
                missing=(), d3=False):
        self.arm = arm
        self.directory = self.root / arm
        self.directory.mkdir()
        self.order = list(order)
        # An empty selector order is valid when no candidates have usable SMILES.
        pool = self.order or ["unsupported"]
        self.frozen = {
            "execution_receipt_version": comparison.RECEIPT_VERSION,
            "protocol": {
                "schema_version": comparison.D3_SCHEMA if d3 else comparison.SCHEMA,
                "budget_seconds_per_arm": 10.0,
                "max_engine_calls_per_arm": cap,
            },
            "pool": pool,
            "rows": [{"record_id": rid, "smiles": "synthetic" if self.order else None}
                     for rid in pool],
            "requests": {rid: None if rid in missing else {"synthetic_id": rid}
                         for rid in pool},
        }
        self.binding = comparison.sha(self.frozen)
        comparison.publish(self.root / "frozen.json", {
            "payload": self.frozen, "sha256": self.binding,
        })
        comparison.publish(self.directory / "attempt.json", {
            "receipt_version": comparison.RECEIPT_VERSION,
            "arm": self.arm,
            "binding": self.binding,
            "started_monotonic": self.start,
            "deadline": self.deadline,
        })
        predictions = ({} if arm == "engine" else
                       {rid: float(len(self.order) - i) for i, rid in enumerate(self.order)})
        self.priority_result = (self.order, predictions, {})
        self.priority = mock.Mock(return_value=self.priority_result)

    @contextmanager
    def worker_dependencies(self):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(sys.modules, self.modules))
            stack.enter_context(mock.patch.object(comparison, "read", side_effect=_json_read))
            stack.enter_context(mock.patch.object(comparison, "_priority", self.priority))
            stack.enter_context(mock.patch.object(comparison.time, "monotonic", side_effect=lambda: self.now))
            yield

    def execute(self, *, deadline=None):
        with self.worker_dependencies():
            comparison.worker(self.root, self.arm, self.deadline if deadline is None else deadline)
        return self.terminal()

    def terminal(self):
        return _json_read(self.directory / "worker-complete.json")

    def rows(self):
        result = []
        for path in sorted(self.directory.glob("*.row.json")):
            envelope = _json_read(path)
            self.assertEqual(envelope["sha256"], comparison.sha(envelope["payload"]))
            result.append(envelope["payload"])
        return result

    def completion(self, *, status="complete", elapsed=2.0):
        return {
            "receipt_version": comparison.RECEIPT_VERSION,
            "arm": self.arm,
            "binding": self.binding,
            "status": status,
            "deadline": self.deadline,
            "budget_seconds": 10.0,
            "measured_process_wall_seconds": elapsed,
            "termination_overhead_seconds": None if elapsed is None else max(0.0, elapsed - 10.0),
        }

    def observations(self):
        return {name: _json_read(self.directory / name)
                for name in ("priority.json", "worker-complete.json")
                if (self.directory / name).exists()}

    def validate(self, *, completion=None, observations=None, rows=None):
        with mock.patch.object(comparison, "read", side_effect=_json_read):
            return comparison._validate_execution_receipts(
                self.directory, self.frozen, self.binding,
                self.completion() if completion is None else completion,
                self.observations() if observations is None else observations,
                self.rows() if rows is None else rows,
            )

    def reseal_row(self, row):
        path = self.directory / (comparison.sha(row["record_id"]) + ".row.json")
        path.write_text(comparison.canonical({"payload": row, "sha256": comparison.sha(row)}),
                        encoding="utf-8")

    def assert_terminal(self, reason, calls, committed):
        terminal = self.terminal()
        self.assertEqual(terminal["receipt_version"], comparison.RECEIPT_VERSION)
        self.assertEqual(terminal["binding"], self.binding)
        self.assertEqual(terminal["arm"], self.arm)
        self.assertEqual(terminal["stop_reason"], reason)
        self.assertEqual(terminal["engine_calls"], calls)
        self.assertEqual(terminal["committed_rows"], committed)
        self.assertEqual(len(self.rows()), committed)
        self.assertGreaterEqual(terminal["process_cpu_seconds"], 0)
        self.assertGreaterEqual(terminal["process_peak_rss_kib"], 0)
        self.assertEqual(list(self.directory.glob(".*")), [], "publication must clean temporary files")

    def test_engine_exhausts_order_and_real_row_report_publication(self):
        self.prepare()
        self.execute()
        self.assert_terminal("order_exhausted", 2, 2)
        self.assertEqual(self.evaluate.call_count, 2)
        for row in self.rows():
            self.assertEqual((row["status"], row["score"]), ("evaluated", -2.5))
            self.assertEqual(row["pose_report"], comparison.file_ref(row["pose_report"]["path"]))
        self.validate()

    def test_similarity_exhaustion_never_consumes_engine_calls(self):
        self.prepare(arm="similarity", cap=1)
        self.execute()
        self.assert_terminal("order_exhausted", 0, 2)
        self.evaluate.assert_not_called()
        self.torch.set_num_threads.assert_not_called()
        self.validate()

    def test_empty_selector_order_has_explicit_order_exhausted_terminal(self):
        self.prepare(arm="similarity", order=())
        self.execute()
        self.assert_terminal("order_exhausted", 0, 0)
        self.validate()

    def test_engine_call_cap_one_commits_one_and_leaves_remainder(self):
        self.prepare(cap=1)
        self.execute()
        self.assert_terminal("engine_call_cap", 1, 1)
        self.assertEqual([row["record_id"] for row in self.rows()], ["a"])
        self.evaluate.assert_called_once()
        self.validate()

    def test_cap_exactly_reached_on_final_candidate_is_order_exhausted(self):
        self.prepare(order=("a",), cap=1)
        self.execute()
        self.assert_terminal("order_exhausted", 1, 1)
        self.validate()

    def test_freeze_rejects_zero_call_cap_before_source_or_dependencies(self):
        protocol = {
            "schema_version": comparison.SCHEMA,
            "source": {"kind": "synthetic_constants", "rows": []},
            "requests": {}, "budget_seconds_per_arm": 10,
            "max_engine_calls_per_arm": 0, "top_k": 1,
        }
        with mock.patch.object(comparison, "load_rows") as load_rows:
            with mock.patch.dict(sys.modules, {"torch": None, "rdkit": None}):
                with self.assertRaisesRegex(ValueError, "invalid_comparison_count_budget"):
                    comparison.freeze(protocol)
            load_rows.assert_not_called()

    def test_missing_inputs_commit_unsupported_rows_without_calls(self):
        self.prepare(order=("a", "b", "c"), missing=("a", "c"))
        self.execute()
        self.assert_terminal("order_exhausted", 1, 3)
        by_id = {row["record_id"]: row for row in self.rows()}
        for rid in ("a", "c"):
            self.assertEqual(by_id[rid]["status"], "unsupported")
            self.assertEqual(by_id[rid]["reason"], "prepared_input_missing")
            self.assertIsNone(by_id[rid]["score"])
        self.evaluate.assert_called_once_with({"synthetic_id": "b"})
        self.validate()

    def test_deadline_before_setup_emits_terminal_without_priority(self):
        self.prepare()
        self.now = self.deadline
        self.execute()
        self.assert_terminal("deadline", 0, 0)
        self.priority.assert_not_called()
        self.torch.set_num_threads.assert_not_called()
        self.assertFalse((self.directory / "priority.json").exists())
        self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.0))

    def test_deadline_during_torch_setup_does_not_start_priority(self):
        self.prepare()
        self.torch.set_num_threads.side_effect = lambda _: setattr(self, "now", self.deadline)
        self.execute()
        self.assert_terminal("deadline", 0, 0)
        self.priority.assert_not_called()
        self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.0))

    def test_deadline_during_priority_setup_wins_even_with_empty_order(self):
        self.prepare(arm="similarity", order=())
        def slow_priority(*_):
            self.now = self.deadline
            return self.priority_result
        self.priority.side_effect = slow_priority
        self.execute()
        self.assert_terminal("deadline", 0, 0)
        self.assertTrue((self.directory / "priority.json").exists())
        self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.0))

    def test_deadline_during_calculation_accounts_call_without_published_row(self):
        self.prepare()
        report = self.evaluate.return_value
        def slow_evaluate(_):
            self.now = self.deadline + 0.25
            return report
        self.evaluate.side_effect = slow_evaluate
        self.execute()
        self.assert_terminal("deadline", 1, 0)
        self.evaluate.assert_called_once()
        self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.25))

    def test_deadline_during_real_fsync_prevents_row_commit(self):
        self.prepare(order=("a",))
        real_fsync = comparison.os.fsync
        count = 0
        def deadline_fsync(fd):
            nonlocal count
            real_fsync(fd)
            count += 1
            if count == 3:  # priority, pose report, then completed row temporary file
                self.now = self.deadline
        with mock.patch.object(comparison.os, "fsync", side_effect=deadline_fsync):
            self.execute()
        self.assertEqual(count, 4)  # terminal is durably published after the missed row
        self.assert_terminal("deadline", 1, 0)
        self.assertTrue((self.directory / (comparison.sha("a") + ".poses.json")).exists())
        self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.0))

    def test_evaluator_failure_consumes_call_and_is_committed_before_cap_stop(self):
        self.prepare(cap=1)
        self.evaluate.side_effect = RuntimeError("synthetic calculation failure")
        self.execute()
        self.assert_terminal("engine_call_cap", 1, 1)
        self.assertEqual(self.rows()[0]["reason"], "RuntimeError:synthetic calculation failure")
        self.assertEqual(self.rows()[0]["status"], "failed")
        self.validate()

    def test_d3_import_failure_consumes_started_call(self):
        self.prepare(cap=1, d3=True)
        self.modules["betelgeuze_product.cpu_refinement_v1_2"] = None
        self.modules["betelgeuze_product.cpu_refinement_v1_2.policy_adapter"] = None
        self.execute()
        self.assert_terminal("engine_call_cap", 1, 1)
        self.assertEqual(self.rows()[0]["status"], "failed")
        self.assertIn("ModuleNotFoundError", self.rows()[0]["reason"])
        self.evaluate.assert_not_called()
        self.validate()

    def test_d3_evaluation_and_summary_publish_report_with_one_call(self):
        self.prepare(order=("a",), d3=True)
        self.execute()
        self.assert_terminal("order_exhausted", 1, 1)
        row = self.rows()[0]
        self.assertEqual((row["status"], row["score"]), ("evaluated", -3.0))
        self.assertEqual(row["d3_report"], comparison.file_ref(row["d3_report"]["path"]))
        self.d3.evaluate.assert_called_once_with({"synthetic_id": "a"})
        self.d3.summarize.assert_called_once()
        self.evaluate.assert_not_called()
        self.validate()

    def test_attempt_deadline_argument_mismatch_fails_before_work(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "worker_deadline_reservation_mismatch"):
            self.execute(deadline=self.deadline + 1)
        self.priority.assert_not_called()
        self.torch.set_num_threads.assert_not_called()
        self.assertFalse((self.directory / "worker-complete.json").exists())

    def test_complete_without_worker_terminal_is_rejected(self):
        self.prepare()
        self.execute()
        observations = self.observations()
        observations.pop("worker-complete.json")
        with self.assertRaisesRegex(ValueError, "complete_without_worker_receipt"):
            self.validate(observations=observations)

    def test_killed_or_failed_worker_need_not_invent_terminal(self):
        self.prepare()
        for status, elapsed in (("budget_exhausted", 10.0), ("worker_failed", 2.0),
                                ("interrupted_budget_forfeited", None)):
            with self.subTest(status=status):
                self.validate(completion=self.completion(status=status, elapsed=elapsed),
                              observations={}, rows=[])

    def test_resealed_row_outside_budget_is_rejected(self):
        self.prepare(order=("a",))
        self.execute()
        row = self.rows()[0]
        for timestamp in (self.start - 0.1, self.deadline + 0.1):
            with self.subTest(timestamp=timestamp):
                changed = copy.deepcopy(row)
                changed["completed_monotonic"] = timestamp
                self.reseal_row(changed)
                with self.assertRaisesRegex(ValueError, "row_outside_reserved_budget"):
                    self.validate()

    def test_resealed_terminal_with_missing_ordered_row_is_rejected(self):
        self.prepare()
        self.execute()
        observations = self.observations()
        observations["worker-complete.json"].update(committed_rows=1, engine_calls=1)
        first = next(row for row in self.rows() if row["record_id"] == "a")
        with self.assertRaisesRegex(ValueError, "completed_worker_missing_ordered_row"):
            self.validate(observations=observations, rows=[first])

    def test_resealed_terminal_caps_and_accounting_are_rejected(self):
        self.prepare(cap=1)
        self.execute()
        baseline = self.observations()
        cases = (
            ({"engine_calls": 0}, "worker_engine_call_accounting_mismatch"),
            ({"engine_calls": 2}, "invalid_worker_completion_receipt"),
            ({"engine_calls": True}, "invalid_worker_completion_receipt"),
            ({"committed_rows": 0}, "invalid_worker_completion_receipt"),
            ({"committed_rows": True}, "invalid_worker_completion_receipt"),
            ({"stop_reason": "unknown"}, "invalid_worker_completion_receipt"),
            ({"process_cpu_seconds": -1}, "invalid_worker_completion_receipt"),
            ({"process_peak_rss_kib": -1}, "invalid_worker_completion_receipt"),
            ({"process_peak_rss_kib": True}, "invalid_worker_completion_receipt"),
            ({"receipt_version": "unknown"}, "invalid_worker_completion_receipt"),
            ({"arm": "similarity"}, "invalid_worker_completion_receipt"),
        )
        for change, error in cases:
            with self.subTest(change=change):
                observations = copy.deepcopy(baseline)
                observations["worker-complete.json"].update(change)
                # Terminal receipts are canonical JSON rather than hash envelopes.
                path = self.directory / "worker-complete.json"
                path.write_text(comparison.canonical(observations["worker-complete.json"]), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error):
                    self.validate()

    def test_cap_terminal_requires_cap_reached_and_remaining_order(self):
        self.prepare(order=("a",))
        self.execute()
        observations = self.observations()
        observations["worker-complete.json"]["stop_reason"] = "engine_call_cap"
        with self.assertRaisesRegex(ValueError, "invalid_engine_call_cap"):
            self.validate(observations=observations)

    def test_similarity_cannot_claim_engine_cap(self):
        self.prepare(arm="similarity", cap=1)
        self.execute()
        observations = self.observations()
        observations["worker-complete.json"]["stop_reason"] = "engine_call_cap"
        with self.assertRaisesRegex(ValueError, "invalid_engine_call_cap"):
            self.validate(observations=observations)

    def test_terminal_committed_rows_must_be_priority_prefix(self):
        self.prepare(cap=1)
        self.execute()
        row = copy.deepcopy(self.rows()[0])
        row["record_id"] = "b"
        with self.assertRaisesRegex(ValueError, "worker_committed_prefix_mismatch"):
            self.validate(rows=[row])

    def test_committed_rows_without_priority_are_rejected(self):
        self.prepare()
        self.execute()
        observations = self.observations()
        observations.pop("priority.json")
        with self.assertRaisesRegex(ValueError, "worker_committed_prefix_mismatch"):
            self.validate(observations=observations)

    def test_completion_binding_version_budget_and_deadline_mismatches(self):
        self.prepare()
        self.execute()
        for change in ({"binding": "different"}, {"receipt_version": "old"},
                       {"arm": "similarity"}, {"budget_seconds": 9.0}, {"deadline": 111.0}, {"status": "unknown"}):
            with self.subTest(change=change):
                completion = self.completion()
                completion.update(change)
                with self.assertRaisesRegex(ValueError, "invalid_completion_receipt"):
                    self.validate(completion=completion)

    def test_completion_timing_and_status_mismatches(self):
        self.prepare()
        self.execute()
        for change in ({"measured_process_wall_seconds": -1.0},
                       {"termination_overhead_seconds": 0.5},
                       {"status": "budget_exhausted"},
                       {"measured_process_wall_seconds": 10.0},
                       {"measured_process_wall_seconds": 11.0, "termination_overhead_seconds": 1.0}):
            with self.subTest(change=change):
                completion = self.completion()
                completion.update(change)
                with self.assertRaisesRegex(ValueError, "invalid_completion_timing"):
                    self.validate(completion=completion)

    def test_interrupted_receipt_cannot_claim_measured_timing(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "invalid_interrupted_completion_receipt"):
            self.validate(completion=self.completion(status="interrupted_budget_forfeited"),
                          observations={}, rows=[])

    def test_terminal_timing_must_cover_rows_and_fit_parent_measurement(self):
        self.prepare(order=("a",))
        self.execute()
        for timestamp in (self.start - 1, self.now - 0.5, self.start + 2.5):
            with self.subTest(timestamp=timestamp):
                observations = self.observations()
                observations["worker-complete.json"]["stopped_monotonic"] = timestamp
                with self.assertRaisesRegex(ValueError, "invalid_worker_completion_receipt"):
                    self.validate(observations=observations)

    def test_deadline_terminal_cannot_masquerade_as_complete(self):
        self.prepare()
        self.now = self.deadline
        self.execute()
        # Even a forged pre-deadline timestamp satisfying the parent measurement
        # cannot make a deadline terminal a successful complete run.
        observations = self.observations()
        observations["worker-complete.json"]["stopped_monotonic"] = 101.0
        with self.assertRaisesRegex(ValueError, "invalid_worker_deadline"):
            self.validate(observations=observations)

    def test_deadline_terminal_must_actually_reach_reserved_deadline(self):
        self.prepare()
        self.now = self.deadline
        self.execute()
        observations = self.observations()
        observations["worker-complete.json"]["stopped_monotonic"] = self.deadline - 0.1
        with self.assertRaisesRegex(ValueError, "invalid_worker_deadline"):
            self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.0),
                          observations=observations)

    def test_budget_exhausted_terminal_with_overhead_is_accepted(self):
        self.prepare()
        self.now = self.deadline + 0.5
        self.execute()
        self.assert_terminal("deadline", 0, 0)
        self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.5))

    def test_deadline_allows_only_one_started_uncommitted_call(self):
        self.prepare()
        self.now = self.deadline
        self.execute()
        observations = self.observations()
        observations["priority.json"] = {"order": self.order}
        observations["worker-complete.json"]["engine_calls"] = 1
        completion = self.completion(status="budget_exhausted", elapsed=10.0)
        self.validate(completion=completion, observations=observations)
        observations["worker-complete.json"]["engine_calls"] = 2
        with self.assertRaisesRegex(ValueError, "worker_engine_call_accounting_mismatch"):
            self.validate(completion=completion, observations=observations)

    def test_missing_input_cannot_explain_uncommitted_engine_call(self):
        self.prepare(missing=("a",))
        self.now = self.deadline
        self.execute()
        observations = self.observations()
        observations["priority.json"] = {"order": self.order}
        observations["worker-complete.json"]["engine_calls"] = 1
        with self.assertRaisesRegex(ValueError, "worker_engine_call_accounting_mismatch"):
            self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.0),
                          observations=observations)

    def test_attempt_binding_version_or_reserved_duration_mismatch(self):
        self.prepare()
        baseline = _json_read(self.directory / "attempt.json")
        for change in ({"binding": "different"}, {"receipt_version": "old"},
                       {"deadline": 111.0}, {"started_monotonic": 99.0}, {"arm": "similarity"}):
            with self.subTest(change=change):
                attempt = dict(baseline, **change)
                (self.directory / "attempt.json").write_text(comparison.canonical(attempt), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "invalid_attempt_receipt"):
                    self.execute()
        self.priority.assert_not_called()


    def test_worker_rejects_missing_or_unknown_frozen_receipt_version(self):
        self.prepare()
        for version in (None, "unknown"):
            with self.subTest(version=version):
                frozen = copy.deepcopy(self.frozen)
                if version is None:
                    frozen.pop("execution_receipt_version")
                else:
                    frozen["execution_receipt_version"] = version
                envelope = {"payload": frozen, "sha256": comparison.sha(frozen)}
                (self.root / "frozen.json").write_text(comparison.canonical(envelope), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "unsupported_execution_receipt_version"):
                    self.execute()
        self.priority.assert_not_called()
        self.torch.set_num_threads.assert_not_called()

    def test_summary_rejects_stripped_version_for_current_runtime(self):
        self.prepare()
        frozen = copy.deepcopy(self.frozen)
        frozen.pop("execution_receipt_version")
        frozen["runtime"] = {"comparison_tools": {
            "tools/product/compare_prepared_candidate_policies.py": comparison.file_ref(_MODULE)["sha256"],
        }}
        with self.assertRaisesRegex(ValueError, "missing_execution_receipt_version"):
            comparison._arm_summary(self.directory, frozen, self.binding, self.completion())

    def test_no_terminal_still_rejects_committed_calls_over_cap(self):
        self.prepare(cap=1)
        self.execute()
        first = self.rows()[0]
        forged = copy.deepcopy(first)
        forged["record_id"] = "b"
        self.reseal_row(forged)
        observations = self.observations()
        observations.pop("worker-complete.json")
        for status, elapsed in (("budget_exhausted", 10.0), ("worker_failed", 2.0),
                                ("interrupted_budget_forfeited", None)):
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, "worker_engine_call_accounting_mismatch"):
                    self.validate(completion=self.completion(status=status, elapsed=elapsed),
                                  observations=observations)

    def test_valid_partial_rows_without_terminal_remain_acceptable(self):
        self.prepare(cap=1)
        self.execute()
        observations = self.observations()
        observations.pop("worker-complete.json")
        for status, elapsed in (("budget_exhausted", 10.0), ("worker_failed", 2.0),
                                ("interrupted_budget_forfeited", None)):
            with self.subTest(status=status):
                self.validate(completion=self.completion(status=status, elapsed=elapsed),
                              observations=observations)

    def test_row_after_parent_process_end_rejected_without_terminal(self):
        self.prepare(cap=1)
        self.execute()
        observations = self.observations()
        observations.pop("worker-complete.json")
        with self.assertRaisesRegex(ValueError, "row_after_process_completion"):
            self.validate(completion=self.completion(status="worker_failed", elapsed=0.5),
                          observations=observations)

    def test_identical_row_timestamps_follow_priority_not_record_id(self):
        self.prepare(arm="similarity", order=("z", "a"))
        self.execute()
        self.assertEqual({row["completed_monotonic"] for row in self.rows()}, {101.0})
        with mock.patch.object(comparison, "read", side_effect=_json_read):
            with mock.patch.object(comparison, "_replayed_priority_predictions",
                                   return_value=self.priority_result[1]):
                summary = comparison._arm_summary(self.directory, self.frozen,
                                                  self.binding, self.completion())
        self.assertEqual(summary["denominator"], {"requested": 2, "evaluated": 2})
        self.assertEqual(summary["ranked_record_ids"], ["z", "a"])

    def test_summary_rejects_reversed_timestamps_in_priority_prefix(self):
        self.prepare(arm="similarity", order=("z", "a"))
        self.execute()
        row = next(row for row in self.rows() if row["record_id"] == "z")
        row["completed_monotonic"] = 101.5
        self.reseal_row(row)
        with mock.patch.object(comparison, "read", side_effect=_json_read):
            with mock.patch.object(comparison, "_replayed_priority_predictions",
                                   return_value=self.priority_result[1]):
                with self.assertRaisesRegex(ValueError, "committed_row_priority_sequence_mismatch"):
                    comparison._arm_summary(self.directory, self.frozen,
                                            self.binding, self.completion())

    def test_missing_inputs_before_call_cap_do_not_consume_calls(self):
        self.prepare(order=("a", "b", "c"), cap=1, missing=("a", "c"))
        self.execute()
        self.assert_terminal("engine_call_cap", 1, 2)
        self.assertEqual({row["record_id"] for row in self.rows()}, {"a", "b"})
        self.evaluate.assert_called_once_with({"synthetic_id": "b"})
        self.validate()


    def test_non_deadline_empty_terminal_without_priority_is_rejected(self):
        self.prepare(arm="similarity", order=())
        self.execute()
        observations = self.observations()
        observations.pop("priority.json")
        with self.assertRaisesRegex(ValueError, "worker_completion_without_priority"):
            self.validate(observations=observations)

    def test_full_committed_order_cannot_claim_deadline_terminal(self):
        self.prepare()
        self.execute()
        observations = self.observations()
        observations["worker-complete.json"].update(stop_reason="deadline", stopped_monotonic=self.deadline)
        with self.assertRaisesRegex(ValueError, "invalid_worker_deadline"):
            self.validate(completion=self.completion(status="budget_exhausted", elapsed=10.0),
                          observations=observations)

    def test_missing_input_row_after_call_cap_is_rejected_with_or_without_terminal(self):
        self.prepare(cap=1, missing=("b",))
        self.execute()
        forged = copy.deepcopy(self.rows()[0])
        forged.update(record_id="b", status="unsupported", score=None, reason="prepared_input_missing")
        forged.pop("pose_report")
        forged.pop("pose_denominator")
        forged.pop("numeric_denominator")
        self.reseal_row(forged)
        baseline = self.observations()
        baseline["worker-complete.json"].update(committed_rows=2, stop_reason="order_exhausted")
        for status, elapsed, keep_terminal in (
                ("complete", 2.0, True), ("budget_exhausted", 10.0, False),
                ("worker_failed", 2.0, False), ("interrupted_budget_forfeited", None, False)):
            with self.subTest(status=status, keep_terminal=keep_terminal):
                observations = copy.deepcopy(baseline)
                if not keep_terminal:
                    observations.pop("worker-complete.json")
                with self.assertRaisesRegex(ValueError, "committed_row_after_engine_call_cap"):
                    self.validate(completion=self.completion(status=status, elapsed=elapsed),
                                  observations=observations)

    def test_no_terminal_cannot_hide_nonprefix_committed_rows(self):
        self.prepare(cap=1)
        self.execute()
        observations = self.observations()
        observations.pop("worker-complete.json")
        row = copy.deepcopy(self.rows()[0])
        row["record_id"] = "b"
        with self.assertRaisesRegex(ValueError, "worker_committed_prefix_mismatch"):
            self.validate(completion=self.completion(status="worker_failed"),
                          observations=observations, rows=[row])


    def test_tiny_budget_rejects_backwards_or_enlarged_reservation(self):
        self.prepare()
        frozen = copy.deepcopy(self.frozen)
        frozen["protocol"]["budget_seconds_per_arm"] = 1e-7
        binding = comparison.sha(frozen)
        attempt = _json_read(self.directory / "attempt.json")
        attempt["binding"] = binding
        for deadline in (99.9999995, 100.0000005):
            with self.subTest(deadline=deadline):
                attempt["deadline"] = deadline
                with self.assertRaisesRegex(ValueError, "invalid_attempt_receipt"):
                    comparison._validate_attempt(attempt, frozen, binding, self.arm)
        attempt["deadline"] = attempt["started_monotonic"] + 1e-7
        comparison._validate_attempt(attempt, frozen, binding, self.arm)


    def test_legacy_summary_is_read_only_and_does_not_invent_stop_reason(self):
        self.prepare(arm="similarity", order=("a", "b"))
        self.execute()
        frozen = copy.deepcopy(self.frozen)
        frozen.pop("execution_receipt_version")
        frozen["runtime"] = {"comparison_tools": {
            "tools/product/compare_prepared_candidate_policies.py": "0" * 64,
        }}
        binding = comparison.sha(frozen)
        (self.root / "frozen.json").write_text(comparison.canonical({
            "payload": frozen, "sha256": binding,
        }), encoding="utf-8")
        priority = self.observations()["priority.json"]
        priority["binding"] = binding
        (self.directory / "priority.json").write_text(comparison.canonical(priority), encoding="utf-8")
        row = next(row for row in self.rows() if row["record_id"] == "a")
        row["binding"] = binding
        self.reseal_row(row)
        # Model a historical partial run, which had no recorded cause of stopping.
        (self.directory / (comparison.sha("b") + ".row.json")).unlink()
        terminal = {key: value for key, value in self.terminal().items()
                    if key in {"engine_calls", "process_cpu_seconds", "process_peak_rss_kib"}}
        terminal["binding"] = binding
        (self.directory / "worker-complete.json").write_text(comparison.canonical(terminal), encoding="utf-8")
        attempt = {"binding": binding, "started_monotonic": self.start, "deadline": self.deadline}
        (self.directory / "attempt.json").write_text(comparison.canonical(attempt), encoding="utf-8")
        completion = self.completion()
        completion.pop("receipt_version")
        completion.pop("arm")
        completion["binding"] = binding
        (self.directory / "completion.json").write_text(comparison.canonical(completion), encoding="utf-8")
        before = {str(path.relative_to(self.root)): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        with mock.patch.object(comparison, "read", side_effect=_json_read):
            with mock.patch.object(comparison, "_replayed_priority_predictions",
                                   return_value=self.priority_result[1]):
                summary = comparison._arm_summary(self.directory, frozen, binding, completion)
        self.assertEqual(summary["worker_observations"]["worker-complete.json"], terminal)
        self.assertNotIn("stop_reason", summary["worker_observations"]["worker-complete.json"])
        self.assertNotIn("receipt_version", summary["cost"])
        self.assertEqual(summary["denominator"], {"requested": 2, "evaluated": 1, "not_processed": 1})
        remaining = next(row for row in summary["rows"] if row["record_id"] == "b")
        self.assertEqual(remaining["reason"], "complete")
        after = {str(path.relative_to(self.root)): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(after, before)


    def test_legacy_executable_resume_rejects_changed_runtime_without_running(self):
        self.prepare(arm="similarity")
        current = copy.deepcopy(self.frozen)
        source_key = "tools/product/compare_prepared_candidate_policies.py"
        current["runtime"] = {"comparison_tools": {
            source_key: comparison.file_ref(_MODULE)["sha256"],
        }}
        legacy = copy.deepcopy(current)
        legacy.pop("execution_receipt_version")
        legacy["runtime"]["comparison_tools"][source_key] = "0" * 64
        legacy_binding = comparison.sha(legacy)
        (self.root / "frozen.json").write_text(comparison.canonical({
            "payload": legacy, "sha256": legacy_binding,
        }), encoding="utf-8")
        attempt = {"binding": legacy_binding, "started_monotonic": self.start,
                   "deadline": self.deadline}
        (self.directory / "attempt.json").write_text(comparison.canonical(attempt), encoding="utf-8")
        (self.root / "run.lock").touch()
        before = {str(path.relative_to(self.root)): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        with mock.patch.object(comparison, "read", side_effect=_json_read):
            with mock.patch.object(comparison, "freeze", return_value=(current, 0.0)) as freeze:
                with mock.patch.object(comparison.subprocess, "Popen") as spawn:
                    with self.assertRaisesRegex(ValueError, "resume_input_or_runtime_changed"):
                        comparison.run(current["protocol"], self.root, resume=True)
        freeze.assert_called_once_with(current["protocol"])
        spawn.assert_not_called()
        after = {str(path.relative_to(self.root)): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
