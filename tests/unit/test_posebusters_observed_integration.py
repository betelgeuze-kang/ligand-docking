"""Control-plane regressions; no molecular execution or source-identity substitutes."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools import run_posebusters_observed_integration as observed

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "config/posebusters_observed_protocol_20261104.json"


def arguments(base):
    return SimpleNamespace(launcher_root=base / "launcher", execution_root=base / "execution",
        python=base / "runtime/bin/python", protocol=base / "launcher/config/protocol.json",
        input_root=base / "inputs", runtime_root=base / "runtime", output_root=base / "output/host-1",
        protocol_sha256=observed.PROTOCOL_SHA256, bundle_sha256=observed.BUNDLE_SHA256,
        launcher_workflow_sha="a" * 40, host_slot=1)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.protocol = observed.load_protocol(PROTOCOL_PATH, observed.PROTOCOL_SHA256)

    def test_real_protocol_and_helpers_are_hash_bound(self):
        self.assertEqual(self.protocol["host_slots"], [1, 2])
        self.assertEqual(self.protocol["required_modes"], list(observed.MODES))
        self.assertEqual(self.protocol["execution_source"]["commit"],
                         "8f5fc53ab68b7e6d9801c6a5830e94dbdd914bb4")
        for filename, expected in (("run_posebusters_qualified_integration.py", observed.MONITOR_HELPER_SHA256),
                                   ("run_posebusters_cpu_diagnostic.py", observed.core.HELPER_SHA256)):
            self.assertEqual(hashlib.sha256((ROOT / "tools" / filename).read_bytes()).hexdigest(), expected)
        self.assertEqual(observed.core.__name__, "_posebusters_observed_shared")

    def test_tampered_bytes_cannot_be_authorized_by_replacing_requested_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "protocol.json"
            path.write_bytes(PROTOCOL_PATH.read_bytes() + b"\n")
            for requested in (observed.PROTOCOL_SHA256, observed.core.digest_file(path)):
                with self.subTest(requested=requested), self.assertRaises(observed.core.IntegrityError):
                    observed.load_protocol(path, requested)

    def test_only_native_capability_and_known_environment_are_allowed(self):
        for field in ("capability_request", "ATEN_CPU_CAPABILITY", "UNKNOWN_NUMERIC_SETTING"):
            value = deepcopy(self.protocol)
            if field == "capability_request":
                value[field] = "avx2"
            else:
                value["numerical_environment"][field] = "avx2"
            with self.subTest(field=field), self.assertRaises(observed.core.IntegrityError):
                observed.validate_protocol(value)

    def test_two_hosts_cannot_be_filtered_selected_or_retried(self):
        for field, changed in (("host_slots", [1]), ("batches", 2), ("slots_per_batch", 3),
                ("cpu_model_eligibility_filter", True), ("outcome_dependent_selection", True),
                ("retry_on_scientific_failure", True)):
            value = deepcopy(self.protocol)
            (value if field == "host_slots" else value["host_selection"])[field] = changed
            with self.subTest(field=field), self.assertRaises(observed.core.IntegrityError):
                observed.validate_protocol(value)

    def test_no_claim_can_promote_results_or_change_gates(self):
        for field, initial in self.protocol["claim_scope"].items():
            value = deepcopy(self.protocol)
            value["claim_scope"][field] = not initial
            with self.subTest(field=field), self.assertRaises(observed.core.IntegrityError):
                observed.validate_protocol(value)


class StatusTests(unittest.TestCase):
    def test_complete_collection_preserves_strict_failure(self):
        for code, status, passed in ((0, "success", True), (1, "failed", False)):
            with self.subTest(code=code):
                self.assertEqual(observed.decide_status(original_returncode=code, original_status=status,
                    assessment_passed=passed, collection_complete=True), status)

    def test_missing_collection_is_always_incomplete(self):
        for code, status, passed in ((0, "success", True), (1, "failed", False)):
            with self.subTest(code=code):
                self.assertEqual(observed.decide_status(original_returncode=code, original_status=status,
                    assessment_passed=passed, collection_complete=False), "incomplete")

    def test_invalid_exits_contradictions_and_false_admission_are_rejected(self):
        valid = dict(original_returncode=0, original_status="success", assessment_passed=True,
                     collection_complete=True)
        for change in ({"original_returncode": True}, {"original_returncode": None},
                {"original_returncode": 2}, {"original_status": "failed"}, {"assessment_passed": False},
                {"assessment_passed": 1}, {"collection_complete": 1},
                {"original_returncode": 1, "original_status": "failed"}):
            with self.subTest(change=change), self.assertRaises(observed.core.IntegrityError):
                observed.decide_status(**(valid | change))


class AssessmentTests(unittest.TestCase):
    def test_failed_summary_still_calls_strict_assessor_and_keeps_exact_error(self):
        class ReplayProtocolError(RuntimeError):
            pass
        calls, summary = [], {"status": "failed"}
        bundle, selected, directory = {"bundle": "sentinel"}, {"case": "sentinel"}, Path("/retained-case")
        def assess_case(*args, **kwargs):
            calls.append((args, kwargs))
            raise ReplayProtocolError("exact mismatch: case mode order/process gate")
        result = observed.record_original_assessment(SimpleNamespace(assess_case=assess_case), directory,
                                                     summary, bundle=bundle, selected=selected)
        self.assertEqual(result, {"passed": False, "error_type": "ReplayProtocolError",
                                  "error": "exact mismatch: case mode order/process gate"})
        self.assertEqual(calls, [((directory, summary), {"bundle": bundle, "selected": selected,
                                                       "bundle_sha256": observed.BUNDLE_SHA256})])
        self.assertEqual(summary, {"status": "failed"})

    def test_success_requires_identical_recorded_raw_assessment(self):
        assessment = {"count": 64, "nested": {"b": 2, "a": 1}}
        controller = SimpleNamespace(assess_case=lambda *args, **kwargs: deepcopy(assessment))
        summary = {"assessment": {"nested": {"a": 1, "b": 2}, "count": 64}}
        self.assertEqual(observed.record_original_assessment(controller, Path("/case"), summary,
            bundle={}, selected={}), {"passed": True, "assessment": assessment})
        for changed in ({}, {"assessment": {"count": 64.0, "nested": {"a": 1, "b": 2}}}):
            with self.subTest(summary=changed), self.assertRaises(observed.core.IntegrityError):
                observed.record_original_assessment(controller, Path("/case"), changed, bundle={}, selected={})


class BoundaryTests(unittest.TestCase):
    def test_only_declared_disjoint_roots_are_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            observed.normalize_arguments(arguments(base))
            for field, value in (("host_slot", True), ("host_slot", 3), ("bundle_sha256", "0" * 64),
                    ("execution_root", base / "launcher/child"), ("output_root", base / "inputs/output"),
                    ("output_root", base)):
                invalid = arguments(base)
                setattr(invalid, field, value)
                with self.subTest(field=field, value=value), self.assertRaises(observed.core.IntegrityError):
                    observed.normalize_arguments(invalid)

    def test_output_symlink_cannot_redirect_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            (base / "destination").mkdir()
            (base / "redirect").symlink_to(base / "destination", target_is_directory=True)
            args = arguments(base)
            args.output_root = base / "redirect/host-1"
            with self.assertRaises(observed.core.IntegrityError):
                observed.normalize_arguments(args)

    def test_missing_receipt_or_unconfirmed_cleanup_is_incomplete(self):
        result = {"status": "failed", "error_type": "ReplayProtocolError",
                  "error": next(iter(observed.helper.STRICT_FAILURES))}
        receipt = {"termination": "exited", "returncode": 1, "cleanup_complete": True, "error": None}
        self.assertEqual(observed.helper.classify_worker_exit(receipt, result), "strict_gate_failure")
        for changed in (None, {}, receipt | {"cleanup_complete": False},
                        receipt | {"termination": "timeout"}, receipt | {"returncode": True}):
            with self.subTest(receipt=changed):
                self.assertEqual(observed.helper.classify_worker_exit(changed, result), "incomplete")
        self.assertEqual(observed.helper.classify_worker_exit(receipt, result | {"error": "other failure"}),
                         "incomplete")

    def test_fatal_supervisor_error_survives_failed_finalization(self):
        class FatalCleanup(BaseException):
            pass
        primary, secondary, calls = FatalCleanup("descendants may be alive"), RuntimeError("write failed"), []
        def supervise():
            calls.append("supervise")
            raise primary
        def finalize():
            calls.append("finalize")
            raise secondary
        with self.assertRaises(FatalCleanup) as raised:
            observed.helper.supervise_and_finalize(supervise, finalize)
        self.assertIs(raised.exception, primary)
        self.assertIs(raised.exception.__cause__, secondary)
        self.assertEqual(calls, ["supervise", "finalize"])

    def test_launcher_does_not_call_old_profile_gates_or_replace_source_identity(self):
        tree = ast.parse(Path(observed.__file__).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        attributes = {node.func.attr for node in calls if isinstance(node.func, ast.Attribute)}
        self.assertTrue({"assess_case", "supervise_and_finalize", "validate_report",
                         "validate_observation_events"}.issubset(attributes))
        self.assertFalse({"validate_cpu", "validate_probe", "validate_observation", "execute",
                          "run_original_case"} & attributes)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                self.assertNotEqual(node.attr, "source_identity")
                if isinstance(node.value, ast.Name):
                    self.assertNotEqual(node.value.id, "controller", "frozen controller mutation")
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                if name in {"setattr", "patch", "object"}:
                    self.assertFalse(any(isinstance(arg, ast.Constant) and arg.value == "source_identity"
                                         for arg in node.args), "source identity substitution")


if __name__ == "__main__":
    unittest.main()
