"""Synthetic accounting tests only; no molecular evaluator is invoked."""
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "betelgeuze_product" / "public_pose_benchmark.py"
SPEC = importlib.util.spec_from_file_location("_public_pose_benchmark_test", SOURCE)
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


def protocol(**kwargs):
    fields = dict(dataset_id="synthetic_fixture", release="test-v1", dataset_manifest_sha256="a" * 64,
                  case_ids=("case_a", "case_b"), purpose="development",
                  engines=(M.EngineSpec("own", "test-v1", "b" * 64, "cpu-test", 1),), seeds=(1, 2),
                  preparation_policy_sha256="c" * 64, pocket_policy_sha256="d" * 64,
                  evaluator_version="test-v1", evaluator_configuration_sha256="e" * 64,
                  required_pb_checks=("chemistry", "clashes"))
    fields.update(kwargs)
    return M.BenchmarkProtocol(**fields)


def successful(p, **kwargs):
    fields = dict(case_id="case_a", engine_id="own", seed=1, protocol_sha256=p.sha256,
                  stages=tuple(M.StageObservation(s, "success") for s in M.STAGES),
                  top1_pose_id="candidate_1", top1_pose_sha256="f" * 64,
                  evaluated_pose_sha256="f" * 64, rmsd_angstrom=1.0,
                  pb_checks=(("chemistry", True), ("clashes", True)))
    fields.update(kwargs)
    return M.OutcomeRecord(**fields)


def stopped(p, status, stage=0):
    stages = tuple(M.StageObservation(name, "success" if i < stage else status if i == stage else "not_run",
                                     "fixture_reason" if i == stage else None)
                   for i, name in enumerate(M.STAGES))
    r = successful(p, stages=stages, rmsd_angstrom=None, pb_checks=(), evaluated_pose_sha256=None)
    return r if stage == 4 else replace(r, top1_pose_id=None, top1_pose_sha256=None)


class PublicPoseBenchmarkTests(unittest.TestCase):
    def test_missing_cases_and_seeds_retained(self):
        result = M.PublicPoseLedger(protocol()).export()
        self.assertEqual(len(result["observations"]), 4)
        self.assertTrue(all(not r["recorded"] for r in result["observations"]))
        self.assertTrue(all(s["case_denominator"] == 2 for s in result["per_seed_summary"]))

    def test_one_success_not_inflated_by_seed_or_missing_case(self):
        p = protocol(); ledger = M.PublicPoseLedger(p); ledger.add(successful(p))
        first, second = ledger.export()["per_seed_summary"]
        self.assertEqual(first["top1_joint_success_count"], 1)
        self.assertEqual(second["top1_joint_success_count"], 0)
        self.assertIsNone(first["top1_joint_success_fraction"])
        self.assertIsNone(second["top1_joint_success_fraction"])

    def test_terminal_failure_inclusive_fraction(self):
        p = protocol(); ledger = M.PublicPoseLedger(p); ledger.add(successful(p))
        ledger.add(replace(stopped(p, "unsupported"), case_id="case_b"))
        summary = ledger.export()["per_seed_summary"][0]
        self.assertEqual(summary["top1_joint_success_fraction"], 0.5)
        self.assertEqual(summary["terminal_outcomes"], 2)
        self.assertEqual(summary["evaluation_completed"], 1)

    def test_duplicate_cannot_overwrite(self):
        p = protocol(); ledger = M.PublicPoseLedger(p); ledger.add(successful(p))
        with self.assertRaises(M.PublicPoseBenchmarkError): ledger.add(successful(p, rmsd_angstrom=0.1))

    def test_foreign_protocol_rejected(self):
        p = protocol(); other = replace(p, rmsd_threshold_angstrom=3.0)
        with self.assertRaises(M.PublicPoseBenchmarkError): M.PublicPoseLedger(p).add(successful(other))

    def test_failed_stages_remain_in_denominator(self):
        p = protocol()
        for status in ("failure", "error", "unsupported", "timeout", "unassigned"):
            ledger = M.PublicPoseLedger(p); ledger.add(stopped(p, status))
            self.assertEqual(ledger.export()["per_seed_summary"][0]["case_denominator"], 2)
            self.assertFalse(ledger.export()["observations"][0]["top1_joint_success"])

    def test_unknown_case_engine_seed_rejected(self):
        p = protocol()
        for fields in ({"case_id": "outside"}, {"engine_id": "outside"}, {"seed": 3}, {"seed": True}):
            with self.assertRaises(M.PublicPoseBenchmarkError): successful(p, **fields).validate(p)

    def test_evaluation_complete_is_not_scientific_success(self):
        p = protocol(); ledger = M.PublicPoseLedger(p)
        ledger.add(successful(p, pb_checks=(("chemistry", True), ("clashes", False))))
        summary = ledger.export()["per_seed_summary"][0]
        self.assertEqual(summary["evaluation_completed"], 1)
        self.assertEqual(summary["top1_joint_success_count"], 0)
        self.assertEqual(summary["rmsd_success_count"], 1)
        self.assertEqual(summary["pb_valid_count"], 0)

    def test_bad_rmsd_fails_joint(self):
        p = protocol(); self.assertFalse(successful(p, rmsd_angstrom=2.1).joint_success(p))

    def test_rmsd_boundary_explicit(self):
        p = protocol(); self.assertTrue(successful(p, rmsd_angstrom=2.0).joint_success(p))
        q = replace(p, rmsd_comparison="lt")
        self.assertFalse(successful(q, rmsd_angstrom=2.0).joint_success(q))

    def test_none_check_never_success(self):
        p = protocol()
        with self.assertRaises(M.PublicPoseBenchmarkError):
            successful(p, pb_checks=(("chemistry", None), ("clashes", True))).joint_success(p)

    def test_missing_extra_duplicate_checks_rejected(self):
        p = protocol()
        for checks in ((), (("chemistry", True),), (("extra", True),),
                       (("chemistry", True), ("chemistry", True)), (("chemistry", 1), ("clashes", True))):
            with self.assertRaises(M.PublicPoseBenchmarkError): successful(p, pb_checks=checks).validate(p)

    def test_evaluation_is_bound_to_top1(self):
        p = protocol()
        with self.assertRaises(M.PublicPoseBenchmarkError): successful(p, evaluated_pose_sha256="a" * 64).validate(p)

    def test_selected_pose_hash_and_id_required(self):
        p = protocol()
        for fields in ({"top1_pose_id": None}, {"top1_pose_sha256": None}):
            with self.assertRaises(M.PublicPoseBenchmarkError): successful(p, **fields).validate(p)

    def test_partial_evaluator_failure_keeps_observations_not_success(self):
        p = protocol(); r = replace(stopped(p, "error", 4), rmsd_angstrom=0.2,
                                   evaluated_pose_sha256="f" * 64, pb_checks=(("chemistry", None),))
        self.assertFalse(r.joint_success(p))

    def test_not_run_cannot_have_evaluation(self):
        p = protocol(); r = replace(stopped(p, "error"), rmsd_angstrom=0.2)
        with self.assertRaises(M.PublicPoseBenchmarkError): r.validate(p)

    def test_pipeline_cannot_continue_after_failure(self):
        p = protocol(); r = successful(p)
        bad = (M.StageObservation("prepare", "error", "input_missing"), *r.stages[1:])
        with self.assertRaises(M.PublicPoseBenchmarkError): replace(r, stages=bad).validate(p)

    def test_incomplete_or_reordered_stages_rejected(self):
        p = protocol(); r = successful(p)
        for stages in (r.stages[:-1], tuple(reversed(r.stages))):
            with self.assertRaises(M.PublicPoseBenchmarkError): replace(r, stages=stages).validate(p)

    def test_invalid_metric_numbers_rejected(self):
        p = protocol()
        for value in (float("nan"), float("inf"), -1.0, True, "1.0", 10 ** 400):
            with self.assertRaises(M.PublicPoseBenchmarkError): successful(p, rmsd_angstrom=value).validate(p)

    def test_resource_missing_is_null_not_zero(self):
        p = protocol(); ledger = M.PublicPoseLedger(p); ledger.add(successful(p))
        data = json.loads(ledger.to_json())
        self.assertIsNone(data["observations"][0]["resources"]["total_seconds"])

    def test_resource_observation_metadata(self):
        M.ResourceObservation(1.0, 2.0, 3.0, 6.5, 1024, "proc_status_peak", "process").validate()
        for r in (M.ResourceObservation(peak_rss_bytes=1024),
                  M.ResourceObservation(peak_rss_bytes=-1, rss_method="proc", rss_scope="process"),
                  M.ResourceObservation(rss_method="proc"), M.ResourceObservation(total_seconds=True),
                  M.ResourceObservation(3.0, 3.0, 3.0, 5.0)):
            with self.assertRaises(M.PublicPoseBenchmarkError): r.validate()

    def test_protocol_duplicates_empty_mutable_rejected(self):
        for fields in ({"case_ids": ("a", "a")}, {"case_ids": ()}, {"case_ids": ["a"]},
                       {"seeds": (1, 1)}, {"seeds": (True,)}, {"required_pb_checks": ()},
                       {"required_pb_checks": ("a", "a")}, {"purpose": "blind_claim"}):
            with self.assertRaises(M.PublicPoseBenchmarkError): protocol(**fields)

    def test_protocol_and_engine_hash_validation(self):
        for fields in ({"dataset_manifest_sha256": "wrong"}, {"rmsd_threshold_angstrom": 0},
                       {"engines": (M.EngineSpec("own", "v1", "a" * 64, "cpu", True),)},
                       {"engines": (M.EngineSpec("own", "v1", "a" * 64, "cpu", 1),) * 2}):
            with self.assertRaises(M.PublicPoseBenchmarkError): protocol(**fields)

    def test_no_claim_promotion_and_deterministic_json(self):
        ledger = M.PublicPoseLedger(protocol()); first = ledger.to_json()
        self.assertEqual(first, ledger.to_json())
        data = json.loads(first)
        self.assertFalse(data["claim_promotion_allowed"])
        self.assertIn("no_confidence_intervals_computed", data["limitations"])

    def test_export_cannot_mutate_ledger(self):
        p = protocol(); ledger = M.PublicPoseLedger(p); ledger.add(successful(p))
        out = ledger.export(); out["observations"][0]["rmsd_angstrom"] = 100.0
        self.assertTrue(ledger.export()["observations"][0]["top1_joint_success"])

    def test_error_requires_reason(self):
        with self.assertRaises(M.PublicPoseBenchmarkError): M.StageObservation("prepare", "error").validate()

    def test_json_submission_roundtrip(self):
        p = protocol()
        submission = json.loads(json.dumps({"schema": M.SUBMISSION_SCHEMA_VERSION,
                                           "protocol": asdict(p), "records": [asdict(successful(p))]}))
        out = M.ledger_from_submission(submission).export()
        self.assertEqual(out["protocol_sha256"], p.sha256)
        self.assertEqual(out["per_seed_summary"][0]["top1_joint_success_count"], 1)

    def test_json_submission_unknown_fields_or_version_rejected(self):
        base = json.loads(json.dumps({"schema": M.SUBMISSION_SCHEMA_VERSION,
                                     "protocol": asdict(protocol()), "records": []}))
        for data in ({**base, "extra": 1}, {**base, "schema": "future"},
                     {**base, "records": [{}]}, {**base, "protocol": {}}):
            with self.assertRaises(M.PublicPoseBenchmarkError): M.ledger_from_submission(data)

    def test_json_duplicate_keys_rejected(self):
        with self.assertRaises(M.PublicPoseBenchmarkError): json.loads('{"a":1,"a":2}', object_pairs_hook=M._unique_object)

    def test_bounded_run_grid(self):
        with self.assertRaises(M.PublicPoseBenchmarkError): protocol(case_ids=tuple(f"case_{n}" for n in range(5001)))


if __name__ == "__main__":
    unittest.main()
