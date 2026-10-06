"""Dependency-free tests of real receipt, deadline and recovery controls.

No molecular execution or selector quality is claimed by these tests.
"""
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from betelgeuze_product import installed_synthetic_comparison as installed


def fixture():
    frozen = {"protocol": {"budget_seconds_per_arm": 10,
                            "max_engine_calls_per_arm": 1},
              "pool": ["a", "b"], "requests": {"a": {}, "b": {}}}
    attempt = {"receipt_version": installed.EXECUTION_VERSION, "arm": "engine",
               "binding": "binding", "started_monotonic": 10, "deadline": 20}
    completion = {"receipt_version": installed.EXECUTION_VERSION, "arm": "engine",
                  "binding": "binding", "status": "complete", "budget_seconds": 10,
                  "deadline": 20, "measured_process_wall_seconds": 2,
                  "termination_overhead_seconds": 0}
    priority = {"binding": "binding", "arm": "engine", "order": ["a", "b"],
                "predictions": {}, "selector_kind": "source_order",
                "evaluation_labels_read": 0, "setup_wall_seconds": 0}
    worker = {"receipt_version": installed.EXECUTION_VERSION, "arm": "engine",
              "binding": "binding", "engine_calls": 1, "committed_rows": 1,
              "stop_reason": "engine_call_cap", "stopped_monotonic": 11,
              "process_cpu_seconds": 0, "process_peak_rss_kib": 1}
    rows = [{"record_id": "a", "completed_monotonic": 10.5}]
    return attempt, completion, priority, worker, rows, frozen, "binding", "engine"


class ExecutionContract(unittest.TestCase):
    def test_valid_call_cap_receipt(self):
        args = fixture()
        installed._validate_attempt(args[0], args[5], "binding", "engine")
        installed._validate_execution(*args)

    def test_unversioned_attempt_rejected(self):
        args = fixture()
        del args[0]["receipt_version"]
        with self.assertRaisesRegex(ValueError, "invalid_installed_attempt"):
            installed._validate_attempt(args[0], args[5], "binding", "engine")

    def test_unversioned_terminal_rejected(self):
        args = fixture()
        del args[3]["receipt_version"]
        with self.assertRaisesRegex(ValueError, "invalid_installed_worker_terminal"):
            installed._validate_execution(*args)

    def test_terminal_tampering_rejected(self):
        for field, value in [("arm", "similarity"), ("committed_rows", 0),
                             ("stopped_monotonic", 9), ("stopped_monotonic", 13),
                             ("binding", "other")]:
            with self.subTest(field=field, value=value):
                args = fixture()
                args[3][field] = value
                with self.assertRaisesRegex(ValueError, "invalid_installed_worker_terminal"):
                    installed._validate_execution(*args)

    def test_engine_calls_under_and_over_count_rejected(self):
        for value in (0, 2):
            args = fixture()
            args[3]["engine_calls"] = value
            with self.assertRaisesRegex(ValueError, "installed_engine_call_count_mismatch"):
                installed._validate_execution(*args)

    def test_incomplete_order_exhaustion_rejected(self):
        args = fixture()
        args[3]["stop_reason"] = "order_exhausted"
        with self.assertRaisesRegex(ValueError, "installed_worker_missing_ordered_row"):
            installed._validate_execution(*args)

    def test_cap_cannot_describe_exhausted_order(self):
        args = fixture()
        args[2]["order"] = ["a"]
        with self.assertRaisesRegex(ValueError, "invalid_installed_engine_call_cap"):
            installed._validate_execution(*args)

    def test_deadline_cannot_be_early_or_complete(self):
        args = fixture()
        args[3]["stop_reason"] = "deadline"
        with self.assertRaisesRegex(ValueError, "invalid_installed_worker_deadline"):
            installed._validate_execution(*args)

    def test_partial_deadline_allows_one_started_next_call(self):
        args = fixture()
        args[5]["protocol"]["max_engine_calls_per_arm"] = 2
        args[1].update(status="budget_exhausted", measured_process_wall_seconds=11,
                       termination_overhead_seconds=1)
        args[3].update(stop_reason="deadline", stopped_monotonic=20, engine_calls=2)
        installed._validate_execution(*args)
        args[5]["requests"]["b"] = None
        with self.assertRaisesRegex(ValueError, "installed_engine_call_count_mismatch"):
            installed._validate_execution(*args)

    def test_rows_before_attempt_at_deadline_or_after_exit_rejected(self):
        for value, reason in [(9, "installed_row_outside_budget"),
                              (20, "installed_row_outside_budget"),
                              (13, "installed_row_after_process_completion")]:
            args = fixture()
            args[4][0]["completed_monotonic"] = value
            with self.assertRaisesRegex(ValueError, reason):
                installed._validate_execution(*args)

    def test_cap_enforced_without_terminal_observation(self):
        args = list(fixture())
        args[1]["status"] = "worker_failed"
        args[3] = None
        args[4].append({"record_id": "b", "completed_monotonic": 10.6})
        with self.assertRaisesRegex(ValueError, "installed_engine_call_count_mismatch"):
            installed._validate_execution(*args)

    def test_equal_clock_ticks_follow_priority_not_pool_order(self):
        args = fixture()
        args[5]["protocol"]["max_engine_calls_per_arm"] = 2
        args[2]["order"] = ["b", "a"]
        args[4].append({"record_id": "b", "completed_monotonic": 10.5})
        args[3].update(stop_reason="order_exhausted", engine_calls=2, committed_rows=2)
        installed._validate_execution(*args)
        args[4][1]["completed_monotonic"] = 10.6
        with self.assertRaisesRegex(ValueError, "installed_committed_priority_sequence_mismatch"):
            installed._validate_execution(*args)

    def test_empty_order_observes_deadline_after_priority_publication(self):
        frozen = {"schema_version": installed.FROZEN,
                  "execution_receipt_version": installed.EXECUTION_VERSION,
                  "runtime": {}, "pool": [],
                  "protocol": {"budget_seconds_per_arm": 10, "selection_seed": 0}}
        binding = installed._sha(frozen)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "similarity"
            directory.mkdir(mode=0o700)
            installed._publish(root / "frozen.json", {"payload": frozen, "sha256": binding})
            installed._publish(directory / "attempt.json", {
                "receipt_version": installed.EXECUTION_VERSION, "binding": binding,
                "arm": "similarity", "started_monotonic": 10, "deadline": 20})
            clock = [11]
            publish = installed._publish

            def advance_after_priority(path, value, **kwargs):
                result = publish(path, value, **kwargs)
                if path.name == "priority.json":
                    clock[0] = 21
                return result

            with patch.object(installed, "_comparison_runtime", return_value={}), \
                    patch.object(installed, "_predictions", return_value={}), \
                    patch.object(installed.time, "monotonic", side_effect=lambda: clock[0]), \
                    patch.object(installed, "_publish", side_effect=advance_after_priority):
                installed.worker(root, "similarity", 20)
            terminal = installed._committed(directory / "worker-complete.json")
            self.assertEqual(terminal["stop_reason"], "deadline")
            self.assertEqual(terminal["committed_rows"], 0)

    def test_real_orphan_forfeiture_is_immutable_without_launch(self):
        args = fixture()
        frozen, binding = args[5], "binding"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arm = root / "engine"
            arm.mkdir(mode=0o700)
            installed._publish(arm / "attempt.json", args[0])
            lease = installed._lock(arm / "worker.lock", create=True)
            os.close(lease)
            with patch.object(installed.subprocess, "Popen", side_effect=AssertionError("replayed")):
                result = installed._one_arm(root, "engine", frozen, binding, resume=True)
                before = (arm / "completion.json").read_bytes()
                self.assertEqual(installed._one_arm(root, "engine", frozen, binding, resume=True), result)
            self.assertEqual((arm / "completion.json").read_bytes(), before)
            self.assertEqual(result["completion"]["status"], "interrupted_budget_forfeited")
            self.assertIsNone(result["completion"]["measured_process_wall_seconds"])
            self.assertEqual(result["denominator"], {"requested": 2, "not_processed": 2})

    def test_live_worker_lease_blocks_resume(self):
        args = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arm = root / "engine"
            arm.mkdir(mode=0o700)
            installed._publish(arm / "attempt.json", args[0])
            lease = installed._lock(arm / "worker.lock", create=True)
            try:
                with self.assertRaises(BlockingIOError):
                    installed._one_arm(root, "engine", args[5], "binding", resume=True)
                self.assertFalse((arm / "completion.json").exists())
            finally:
                os.close(lease)

    def test_unversioned_orphan_not_migrated(self):
        args = fixture()
        del args[0]["receipt_version"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arm = root / "engine"
            arm.mkdir(mode=0o700)
            installed._publish(arm / "attempt.json", args[0])
            lease = installed._lock(arm / "worker.lock", create=True)
            os.close(lease)
            with self.assertRaisesRegex(ValueError, "invalid_installed_attempt"):
                installed._one_arm(root, "engine", args[5], "binding", resume=True)
            self.assertFalse((arm / "completion.json").exists())

    def test_real_process_group_termination_is_reaped(self):
        child = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"],
                                 start_new_session=True)
        try:
            installed._stop_child(child)
            self.assertEqual(child.returncode, -installed.signal.SIGKILL)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()

    def test_private_canonical_exclusive_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            installed._publish(path, {"value": 1})
            self.assertEqual(installed._committed(path), {"value": 1})
            with self.assertRaises(FileExistsError):
                installed._publish(path, {"value": 2})
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "noncanonical_installed_receipt"):
                installed._committed(path)


if __name__ == "__main__":
    unittest.main()
