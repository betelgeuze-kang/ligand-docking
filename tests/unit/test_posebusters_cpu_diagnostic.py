"""Pure guards for the isolated CPU diagnostic; no Torch/probe/docking execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tools import run_posebusters_cpu_diagnostic as diagnostic


FULL_FLAGS = {"avx2", "fma", "avx512f", "avx512dq", "avx512bw", "avx512vl"}
NAMES = ["native", "default", "avx2", "avx512", "native_repeat"]
REQUESTS = [None, "default", "avx2", "avx512", None]
HISTORICAL_GATE = "exact mismatch: fresh pipeline historical scientific row"
TOP5_GATE = "fresh pipeline Top5 output bytes differ from original"


def process(returncode=0, **changes):
    value = {
        "returncode": returncode, "termination": "exited",
        "cleanup_complete": True, "error": None,
    }
    value.update(changes)
    return value


def gate_failure(message=HISTORICAL_GATE, **changes):
    value = {"status": "failed", "error_type": "ReplayProtocolError", "error": message}
    value.update(changes)
    return value


class CpuDiagnosticPureTests(unittest.TestCase):
    def conditions(self, native, flags):
        rows = diagnostic.supported_conditions(native, flags)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 5)
        self.assertEqual([row["name"] for row in rows], NAMES)
        self.assertEqual([row["request"] for row in rows], REQUESTS)
        for row in rows:
            self.assertIs(type(row["eligible"]), bool)
            if not row["eligible"]:
                self.assertIsInstance(row["reason"], str)
                self.assertTrue(row["reason"])
        return rows

    def test_worker_and_total_deadlines_leave_job_time_for_evidence(self):
        self.assertEqual(diagnostic.WORKER_WALL_SECONDS, 600)
        self.assertEqual(diagnostic.TOTAL_WALL_SECONDS, 2100)
        self.assertLess(diagnostic.TOTAL_WALL_SECONDS, 45 * 60)

    def test_native_avx512_with_all_flags_enables_ordered_conditions(self):
        self.assertEqual(
            [row["eligible"] for row in self.conditions("AVX512", FULL_FLAGS)], [True] * 5
        )

    def test_native_avx2_never_enables_avx512_despite_all_cpu_flags(self):
        self.assertEqual(
            [row["eligible"] for row in self.conditions("AVX2", FULL_FLAGS)],
            [True, True, True, False, True],
        )

    def test_cpu_flags_cannot_replace_a_supported_native_capability(self):
        for native in ("", "UNKNOWN", "NO AVX", "DEFAULT"):
            with self.subTest(native=native):
                rows = self.conditions(native, FULL_FLAGS)
                self.assertIs(rows[2]["eligible"], False)
                self.assertIs(rows[3]["eligible"], False)

    def test_native_capability_without_flags_cannot_enable_forced_isa(self):
        rows = self.conditions("AVX512", set())
        self.assertIs(rows[2]["eligible"], False)
        self.assertIs(rows[3]["eligible"], False)

    def test_every_required_avx2_flag_is_needed(self):
        for missing in ("avx2", "fma"):
            with self.subTest(missing=missing):
                rows = self.conditions("AVX2", FULL_FLAGS - {missing})
                self.assertIs(rows[2]["eligible"], False)

    def test_every_required_avx512_flag_is_needed(self):
        for missing in sorted(FULL_FLAGS):
            with self.subTest(missing=missing):
                rows = self.conditions("AVX512", FULL_FLAGS - {missing})
                self.assertIs(rows[3]["eligible"], False)

    def test_supported_conditions_does_not_mutate_flags(self):
        flags = set(FULL_FLAGS)
        before = set(flags)
        diagnostic.supported_conditions("AVX512", flags)
        self.assertEqual(flags, before)

    def test_environment_is_private_and_bound_to_frozen_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            execution_root = Path(temporary) / "frozen-execution"
            for capability in (None, "default", "avx2", "avx512"):
                with self.subTest(capability=capability):
                    parent = {
                        "KEEP_UNRELATED": "preserved", "ATEN_CPU_CAPABILITY": "avx512",
                        "PYTHONPATH": "/diagnostic-controller:/other/checkout",
                        "OMP_NUM_THREADS": "1",
                        "GITHUB_SHA": "a" * 40,
                    }
                    before = deepcopy(parent)
                    actual = diagnostic.condition_environment(parent, execution_root, capability)
                    self.assertIsNot(actual, parent)
                    self.assertEqual(parent, before)
                    self.assertEqual(actual["PYTHONPATH"], str(execution_root))
                    self.assertEqual(actual["KEEP_UNRELATED"], "preserved")
                    self.assertEqual(actual["OMP_NUM_THREADS"], "1")
                    self.assertEqual(actual["GITHUB_SHA"], diagnostic.EXECUTION_COMMIT)
                    self.assertEqual(parent["GITHUB_SHA"], "a" * 40)
                    if capability is None:
                        self.assertNotIn("ATEN_CPU_CAPABILITY", actual)
                    else:
                        self.assertEqual(actual["ATEN_CPU_CAPABILITY"], capability)

    def test_native_repeat_does_not_inherit_prior_forced_condition(self):
        parent = {"ATEN_CPU_CAPABILITY": "avx2", "OMP_NUM_THREADS": "1"}
        before = deepcopy(parent)
        with tempfile.TemporaryDirectory() as temporary:
            execution_root = Path(temporary)
            native = diagnostic.condition_environment(parent, execution_root, None)
            forced = diagnostic.condition_environment(parent, execution_root, "avx512")
            repeated = diagnostic.condition_environment(parent, execution_root, None)
        self.assertEqual(forced["ATEN_CPU_CAPABILITY"], "avx512")
        self.assertNotIn("ATEN_CPU_CAPABILITY", native)
        self.assertEqual(native, repeated)
        self.assertEqual(parent, before)

    def test_disallowed_capabilities_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            for capability in ("native", "AVX2", "", "sse4", "avx512\n", 0, False):
                with self.subTest(capability=capability):
                    with self.assertRaises((ValueError, RuntimeError)):
                        diagnostic.condition_environment({}, Path(temporary), capability)

    def test_numerical_environment_retains_controls_without_unlisted_values(self):
        expected = {
            "ATEN_CPU_CAPABILITY": "avx2", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1", "MKL_CBWR": "COMPATIBLE", "MKL_DEBUG_CPU_TYPE": "5",
            "OPENBLAS_CORETYPE": "Haswell", "NPY_DISABLE_CPU_FEATURES": "AVX512F",
            "ONEDNN_MAX_CPU_ISA": "AVX2", "DNNL_MAX_CPU_ISA": "AVX2",
            "CUDA_VISIBLE_DEVICES": "", "PYTHONHASHSEED": "0",
        }
        forbidden = {
            "GITHUB_TOKEN": "not-for-evidence", "PATH": "/private/path",
            "GITHUB_SHA": "a" * 40,
            "PYTHONPATH": "/controller", "MKL_UNLISTED_SETTING": "must-not-leak",
            "ATEN_CPU_CAPABILITY_EXTRA": "must-not-leak", "UNRELATED": "must-not-leak",
        }
        parent = {**expected, **forbidden}
        before = deepcopy(parent)
        actual = diagnostic.numerical_environment(parent)
        self.assertEqual(actual, expected)
        self.assertEqual(parent, before)
        self.assertEqual(diagnostic.numerical_environment({}), {})

    def test_normal_success_requires_process_and_worker_agreement(self):
        self.assertEqual(
            diagnostic.classify_worker_exit(process(), {"status": "success"}), "success"
        )

    def test_exact_historical_gates_remain_strict_failures(self):
        for message in (HISTORICAL_GATE, TOP5_GATE):
            with self.subTest(message=message):
                self.assertEqual(
                    diagnostic.classify_worker_exit(process(1), gate_failure(message)),
                    "strict_gate_failure",
                )

    def test_abnormal_or_incomplete_execution_is_not_accepted(self):
        cases = [
            (process(1), {"status": "success"}),
            (process(), gate_failure()),
            (process(-9), gate_failure()),
            (process(-15), gate_failure()),
            (process(2), gate_failure()),
            (process(1, termination="wall_timeout"), gate_failure()),
            (process(1, termination="sampled_rss_limit"), gate_failure()),
            (process(1, termination="remaining_descendants_terminated"), gate_failure()),
            (process(1, termination="supervision_error"), gate_failure()),
            (process(1, cleanup_complete=False), gate_failure()),
            (process(1, cleanup_complete=1), gate_failure()),
            (process(1, error={"exception_type": "OSError"}), gate_failure()),
            (process(1, error={}), gate_failure()),
            (process(), None),
            (process(1), None),
            ({}, {"status": "success"}),
            (process(), {}),
            (None, None),
        ]
        missing_error = process()
        missing_error.pop("error")
        cases.append((missing_error, {"status": "success"}))
        for index, (receipt, result) in enumerate(cases):
            with self.subTest(index=index):
                self.assertEqual(
                    diagnostic.classify_worker_exit(receipt, result), "incomplete"
                )

    def test_gate_matching_is_exact_not_a_substring(self):
        messages = [
            "exact mismatch: case mode order/process gate",
            "exact mismatch: unrelated scientific value",
            HISTORICAL_GATE + " (additional context)",
            "prefix " + HISTORICAL_GATE,
            HISTORICAL_GATE + "\n",
            "",
        ]
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(
                    diagnostic.classify_worker_exit(process(1), gate_failure(message)),
                    "incomplete",
                )

    def test_non_protocol_errors_are_not_scientific_gate_results(self):
        for exception_type in ("ValueError", "RuntimeError", "AssertionError", None):
            with self.subTest(exception_type=exception_type):
                self.assertEqual(
                    diagnostic.classify_worker_exit(
                        process(1), gate_failure(error_type=exception_type)
                    ),
                    "incomplete",
                )

    def test_bool_or_float_exit_codes_are_not_process_return_codes(self):
        cases = [
            (False, {"status": "success"}), (True, gate_failure()),
            (0.0, {"status": "success"}), (1.0, gate_failure()),
        ]
        for returncode, result in cases:
            with self.subTest(returncode=returncode, kind=type(returncode).__name__):
                self.assertEqual(
                    diagnostic.classify_worker_exit(process(returncode), result),
                    "incomplete",
                )

    def assert_cleanup_failure_preserved(self, secondary):
        class CleanupFailure(RuntimeError):
            def __init__(self):
                super().__init__("descendant cleanup uncertain")
                self.record = {"cleanup_complete": False, "termination": "cleanup_failed"}

        primary = CleanupFailure()
        calls = []

        def supervise():
            calls.append("supervise")
            raise primary

        def finalize():
            calls.append("finalize")
            raise secondary

        with self.assertRaises(CleanupFailure) as captured:
            diagnostic.supervise_and_finalize(supervise, finalize)
        self.assertIs(captured.exception, primary)
        self.assertIs(captured.exception.__cause__, secondary)
        self.assertEqual(captured.exception.record["cleanup_complete"], False)
        self.assertEqual(calls, ["supervise", "finalize"])

    def test_monitor_failure_does_not_replace_cleanup_failure(self):
        self.assert_cleanup_failure_preserved(
            diagnostic.DiagnosticError("worker monitor did not stop")
        )

    def test_observation_write_failure_does_not_replace_cleanup_failure(self):
        self.assert_cleanup_failure_preserved(OSError("observation write failed"))

    def test_successful_supervision_and_finalization_return_both_receipts(self):
        process_receipt, observation = {"cleanup_complete": True}, {"samples": 3}
        calls = []

        def supervise():
            calls.append("supervise")
            return process_receipt

        def finalize():
            calls.append("finalize")
            return observation

        result = diagnostic.supervise_and_finalize(supervise, finalize)
        self.assertIs(result[0], process_receipt)
        self.assertIs(result[1], observation)
        self.assertEqual(calls, ["supervise", "finalize"])

    def test_finalization_failure_after_success_still_propagates(self):
        failure = OSError("cannot persist observation")
        calls = []

        def supervise():
            calls.append("supervise")
            return {"cleanup_complete": True}

        def finalize():
            calls.append("finalize")
            raise failure

        with self.assertRaises(OSError) as captured:
            diagnostic.supervise_and_finalize(supervise, finalize)
        self.assertIs(captured.exception, failure)
        self.assertEqual(calls, ["supervise", "finalize"])

    def test_primary_base_exception_survives_successful_finalization(self):
        primary = KeyboardInterrupt("stop")
        calls = []

        def supervise():
            calls.append("supervise")
            raise primary

        def finalize():
            calls.append("finalize")
            return {"samples": 1}

        with self.assertRaises(KeyboardInterrupt) as captured:
            diagnostic.supervise_and_finalize(supervise, finalize)
        self.assertIs(captured.exception, primary)
        self.assertEqual(calls, ["supervise", "finalize"])


if __name__ == "__main__":
    unittest.main()

