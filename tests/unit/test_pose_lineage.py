"""Standard-library tests; intentionally do not import the engine package."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/analyze_pose_lineage.py"
FIXTURE = ROOT / "tests/fixtures/pose_lineage_synthetic.json"
SPEC = importlib.util.spec_from_file_location("pose_lineage", SCRIPT)
lineage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lineage)


class PoseLineageTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_bytes())

    def analyze(self):
        return lineage.analyze_export(self.data)

    def metric(self):
        return self.data["cases"][0]["candidates"][0]["initial"]["metric"]

    def test_fixture_transitions_and_denominators(self):
        report = self.analyze()
        self.assertEqual(report["case_denominator"], 4)
        self.assertEqual(report["candidate_denominator"], 7)
        first, loss, not_attempted, missing = report["cases"]
        self.assertEqual(first["candidates"][0]["transition"], "recovery")
        self.assertTrue(first["selection_loss"])
        self.assertFalse(first["top_k_success"]["1"])
        self.assertTrue(first["top_k_success"]["5"])
        self.assertEqual(first["refinement_transition"], "UNKNOWN")
        self.assertEqual(first["status_counts"]["initial"]["missing"], 1)
        self.assertEqual(loss["refinement_transition"], "loss")
        self.assertEqual(not_attempted["refinement_transition"], "no_success")
        self.assertFalse(not_attempted["top_k_success"]["1"])
        self.assertIsNone(missing["top_k_success"]["1"])
        self.assertFalse(missing["case_observed"])

    def test_complete_case_recovery(self):
        self.data["manifest"][0]["candidate_ids"].remove("unobserved-D")
        self.assertEqual(self.analyze()["cases"][0]["refinement_transition"], "recovery")

    def test_missing_reference_is_unknown_even_with_failed_slots(self):
        self.data["manifest"][2]["reference_id"] = None
        case = self.analyze()["cases"][2]
        self.assertIsNone(case["initial_coverage_success"])
        self.assertIsNone(case["top_k_success"]["1"])

    def test_missing_reference_rejects_claimed_metric(self):
        self.data["manifest"][0]["reference_id"] = None
        with self.assertRaises(lineage.LineageError):
            self.analyze()

    def test_status_is_not_convergence_or_validity(self):
        first = self.analyze()["cases"][0]["candidates"][0]
        self.assertTrue(first["refined_success"])
        self.assertEqual(first["refined"]["convergence"], "not_converged")
        self.data["cases"][0]["candidates"][0]["refined"]["validity"] = "unknown"
        self.assertIsNone(self.analyze()["cases"][0]["candidates"][0]["refined_success"])

    def test_invalid_pose_never_succeeds(self):
        self.data["cases"][0]["candidates"][0]["refined"]["validity"] = "invalid"
        self.assertFalse(self.analyze()["cases"][0]["candidates"][0]["refined_success"])

    def test_threshold_boundary_is_inclusive(self):
        self.metric()["rmsd_angstrom"] = 2.0
        self.assertTrue(self.analyze()["cases"][0]["candidates"][0]["initial_success"])

    def test_duplicate_and_unexpected_id_rejections(self):
        original = copy.deepcopy(self.data)
        mutations = [
            lambda d: d["manifest"].append(copy.deepcopy(d["manifest"][0])),
            lambda d: d["manifest"][0]["candidate_ids"].append("seed-A"),
            lambda d: d["cases"].append(copy.deepcopy(d["cases"][0])),
            lambda d: d["cases"][0]["candidates"].append(copy.deepcopy(d["cases"][0]["candidates"][0])),
            lambda d: d["cases"][0].update(case_id="unexpected"),
            lambda d: d["cases"][0]["candidates"][0].update(candidate_id="unexpected"),
            lambda d: d["cases"][0].update(selected_ids=["seed-A", "seed-A"]),
            lambda d: d["cases"][0].update(selected_ids=["unobserved-D"]),
            lambda d: d["cases"][0].update(selected_ids=["failed-C"]),
        ]
        for mutation in mutations:
            self.data = copy.deepcopy(original)
            mutation(self.data)
            with self.subTest(mutation=mutation), self.assertRaises(lineage.LineageError):
                self.analyze()

    def test_incomparable_metric_rejections(self):
        for key in ("reference_id", "frame_id", "mapping_id", "method_id"):
            old = self.metric()[key]
            self.metric()[key] = "other"
            with self.subTest(key=key), self.assertRaises(lineage.LineageError):
                self.analyze()
            self.metric()[key] = old

    def test_numeric_rejections(self):
        for value in (True, False, float("nan"), float("inf"), -1, "1", 10**1000):
            self.metric()["rmsd_angstrom"] = value
            with self.subTest(value=repr(value)[:30]), self.assertRaises(lineage.LineageError):
                self.analyze()

    def test_policy_and_schema_rejections(self):
        original = copy.deepcopy(self.data)
        for field, value in (("threshold_angstrom", True), ("threshold_angstrom", 0),
                             ("threshold_angstrom", float("inf")), ("unit", "nm"),
                             ("top_k", [True, 5]), ("top_k", [1, 10]),
                             ("schema_id", "other"), ("manifest", [])):
            self.data = copy.deepcopy(original)
            self.data[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(lineage.LineageError):
                self.analyze()

    def test_unknown_fields_empty_ids_and_failed_evidence_rejected(self):
        original = copy.deepcopy(self.data)
        mutations = [lambda d: d.update(extra=1),
                     lambda d: d["manifest"][0].update(candidate_ids=[]),
                     lambda d: d["manifest"][0].update(frame_id=""),
                     lambda d: d["cases"][0]["candidates"][0]["initial"].update(status="failed"),
                     lambda d: d["cases"][0]["candidates"][0]["initial"].update(validity=True),
                     lambda d: d["cases"][0]["candidates"][0]["initial"].update(convergence=True)]
        for mutation in mutations:
            self.data = copy.deepcopy(original)
            mutation(self.data)
            with self.assertRaises(lineage.LineageError):
                self.analyze()

    def test_missing_selection_differs_from_empty(self):
        self.data["cases"][0]["selected_ids"] = None
        self.assertIsNone(self.analyze()["cases"][0]["selection_loss"])
        self.data["cases"][0]["selected_ids"] = []
        self.assertTrue(self.analyze()["cases"][0]["selection_loss"])

    def test_missing_metric_stays_unknown(self):
        self.data["cases"][0]["candidates"][0]["initial"]["metric"] = None
        self.assertIsNone(self.analyze()["cases"][0]["candidates"][0]["initial_success"])

    def test_missing_cases_and_candidates_preserve_denominator(self):
        self.data["cases"] = []
        report = self.analyze()
        self.assertEqual(report["candidate_denominator"], 7)
        self.assertTrue(all(case["refinement_transition"] == "UNKNOWN" for case in report["cases"]))

    def test_json_parser_rejects_duplicates_nonfinite_and_depth(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'\xff',
                    b'[' * 2000 + b']' * 2000, b'{}' + b' ' * lineage.MAX_BYTES):
            with self.subTest(raw=raw[:20]), self.assertRaises(lineage.LineageError):
                lineage.parse_export(raw)

    def test_bounds(self):
        self.data["manifest"] *= lineage.MAX_CASES + 1
        with self.assertRaises(lineage.LineageError):
            self.analyze()
        self.setUp()
        self.data["manifest"][0]["candidate_ids"] = [f"p{i}" for i in range(lineage.MAX_CANDIDATES + 1)]
        with self.assertRaises(lineage.LineageError):
            self.analyze()

    def test_actual_input_digest_and_no_authority(self):
        raw = FIXTURE.read_bytes()
        report = lineage.analyze_bytes(raw)
        self.assertEqual(report["input_file_sha256"], hashlib.sha256(raw).hexdigest())
        for key in ("source_authentication_performed", "scientifically_validated", "benchmark_gate_authority", "causal_inference"):
            self.assertIs(report[key], False)
        self.assertEqual(report, lineage.analyze_bytes(raw))

    def test_cli_both_formats_and_failure(self):
        for format_ in ("json", "text"):
            result = subprocess.run([sys.executable, "-S", str(SCRIPT), str(FIXTURE), "--format", format_], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            if format_ == "json":
                self.assertEqual(json.loads(result.stdout)["candidate_denominator"], 7)
            else:
                self.assertIn("UNKNOWN", result.stdout)
                self.assertIn("refined convergence=not_converged", result.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"duplicate":1,"duplicate":2}')
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertNotIn(str(path), result.stderr)


if __name__ == "__main__":
    unittest.main()
