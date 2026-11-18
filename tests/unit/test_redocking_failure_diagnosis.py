"""Failure classification and evidence admission need no molecular dependencies."""
from copy import deepcopy
from io import BytesIO
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
import warnings
import zipfile

from tools import analyze_redocking_failures as diagnosis


def candidate(index, *, rmsd=3.0, score=None, chemical=True, geometric=True, eligible=True):
    failed = []
    if not chemical:
        failed.append("internal_energy")
    if not geometric:
        failed.append("minimum_distance_to_protein")
    return {"proposal_index": index, "status": "success", "error_code": "",
            "score": float(index) if score is None else score, "rmsd_angstrom": rmsd,
            "chemical_valid": chemical, "geometric_valid": geometric,
            "posebusters_failed_check_ids": failed, "selection_eligible": eligible}


def classify(pool, *, budget=None, top_k=1, status="success"):
    return diagnosis.classify_pool(pool, preparation_status=status,
                                   candidate_budget=len(pool) if budget is None else budget,
                                   top_k=top_k)


def zip_bytes(entries):
    output = BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in entries:
                archive.writestr(name, payload)
    return output.getvalue()


def inventory_zip(*, change=None, extra=()):
    files = {"case/receipt.json": b'{"status":"failure"}', "case/pose.sdf": b"pose\n$$$$\n"}
    inventory = {"schema_id": "betelgeuze.redocking_artifact_inventory/1.0.0",
                 "files": [{"path": name, "sha256": diagnosis.sha256(payload), "size": len(payload)}
                           for name, payload in files.items()], "payload_file_count": 2,
                 "archive_member_count": 3, "bytes": sum(map(len, files.values())), "excluded_paths": []}
    if change is not None:
        change(inventory, files)
    return zip_bytes([*files.items(), ("artifact-inventory.json", diagnosis.canonical(inventory)), *extra])


def journal_fixture():
    request = {"source": {"commit": "fixture"}}
    request_sha = "a" * 64
    receipt = {"receipt_sha256": "b" * 64}
    row = {"case_id": "fixture", "engine_id": "engine_v2", "status": "success"}
    identity = {"case_id": "fixture", "task": "engine_v2", "source": request["source"],
                "request_sha256": request_sha}
    ident_sha = diagnosis.digest(identity)
    files = {"journal/identity.json": diagnosis.canonical(identity)}
    events = [{"stage": "worker", "phase": "start"},
              {"stage": "worker", "phase": "complete", "details": {
                  "receipt_sha256": receipt["receipt_sha256"], "scientific_status": "success", "status": "completed"}}]
    previous, total = None, 0
    for seq, event in enumerate(events, 1):
        envelope = {"schema_id": "betelgeuze.redocking_phase_journal_event/1.0.0",
                    "journal_sequence": seq, "identity_sha256": ident_sha,
                    "previous_event_sha256": previous, "event": event}
        envelope["event_sha256"] = diagnosis.digest(envelope)
        payload = diagnosis.canonical(envelope)
        files[f"journal/event-{seq:06d}.json"] = payload
        previous = envelope["event_sha256"]
        total += len(payload)
    files["journal/checkpoint.json"] = diagnosis.canonical({
        "schema_id": "betelgeuze.redocking_phase_checkpoint/1.0.0", "identity_sha256": ident_sha,
        "last_sequence": 2, "event_path": "event-000002.json", "event_sha256": previous,
        "event_bytes_total": total, "last_event": events[-1]})
    return files, dict(request=request, request_sha=request_sha, receipt=receipt, row=row)


def verify_journal(files, args):
    with diagnosis.opened_zip(zip_bytes(files.items()), "fixture") as archive:
        return diagnosis.verify_journal(archive, "journal/", **args)


class TestScientificClassification(unittest.TestCase):
    def test_exclusive_categories_partition_a_fixed_denominator(self):
        examples = [
            ([], "failure", 2, 1, "preparation_failure"),
            (None, "unobserved", 2, 1, "incomplete_observation"),
            ([candidate(0), candidate(1)], "success", 2, 1, "no_near_native"),
            ([candidate(0, rmsd=1, geometric=False), candidate(1)], "success", 2, 1, "near_native_only_invalid"),
            ([candidate(0), candidate(1, rmsd=1)], "success", 2, 1, "valid_near_native_ranked_out"),
            ([candidate(0, rmsd=1), candidate(1)], "success", 2, 1, "valid_near_native_recovered"),
        ]
        observed = []
        for pool, status, budget, k, expected in examples:
            with self.subTest(expected=expected):
                value = diagnosis.classify_pool(pool, preparation_status=status, candidate_budget=budget, top_k=k)
                self.assertEqual(value["category"], expected)
                observed.append(value["category"])
        self.assertCountEqual(observed, diagnosis.CATEGORIES)
        self.assertEqual(len(observed), 6)

    def test_invalid_near_candidate_can_coexist_with_valid_recovery(self):
        result = classify([candidate(0, rmsd=1, geometric=False), candidate(1, rmsd=1.5)], top_k=3)
        self.assertEqual(result["category"], "valid_near_native_recovered")
        self.assertEqual(result["known_invalid_near_native_count"], 1)
        self.assertTrue(result["has_any_invalid_near_native"])
        self.assertTrue(result["has_any_valid_near_native"])

    def test_two_validity_flags_must_belong_to_the_same_candidate(self):
        pool = [candidate(0, rmsd=1, geometric=False), candidate(1, rmsd=1, chemical=False)]
        result = classify(pool, top_k=5)
        self.assertEqual(result["known_near_native_count"], 2)
        self.assertEqual(result["known_valid_near_native_count"], 0)
        self.assertEqual(result["category"], "near_native_only_invalid")

    def test_exact_rmsd_boundary_is_inclusive(self):
        self.assertEqual(classify([candidate(0, rmsd=2.0)])["category"], "valid_near_native_recovered")
        self.assertEqual(classify([candidate(0, rmsd=math.nextafter(2.0, math.inf))])["category"], "no_near_native")

    def test_rank_ties_use_proposal_index_not_input_order(self):
        pool = [candidate(1, rmsd=1, score=-5), candidate(0, score=-5)]
        self.assertEqual(classify(pool)["best_valid_near_native_rank"], 2)
        self.assertEqual(classify(pool)["category"], "valid_near_native_ranked_out")

    def test_selection_eligible_does_not_silently_change_benchmark_ranking(self):
        pool = [candidate(0, rmsd=1, eligible=False), candidate(1, eligible=True)]
        self.assertEqual(classify(pool)["category"], "valid_near_native_recovered")

    def test_missing_candidate_evaluation_is_not_a_search_failure(self):
        result = classify([candidate(0)], budget=2)
        self.assertFalse(result["pool_complete"])
        self.assertEqual(result["category"], "incomplete_observation")
        failed = {"proposal_index": 1, "status": "failure", "error_code": "evaluation_error"}
        self.assertEqual(classify([candidate(0), failed])["category"], "incomplete_observation")

    def test_preparation_failure_has_no_fabricated_candidate_pool(self):
        result = classify([], status="failure", budget=64)
        self.assertEqual(result["known_near_native_count"], 0)
        with self.assertRaisesRegex(diagnosis.DiagnosisError, "fabricated"):
            classify([candidate(0)], status="failure", budget=64)
        with self.assertRaises(diagnosis.DiagnosisError):
            classify(None, status="failure", budget=64)

    def test_unknown_is_not_a_false_recovery(self):
        result = classify(None, status="unobserved", budget=64)
        self.assertIsNone(result["known_topk_recovered"])
        self.assertIsNone(result["known_near_native_count"])
        self.assertTrue(all(value is None for value in diagnosis.topk_metrics(None).values()))

    def test_duplicate_and_out_of_budget_proposals_are_rejected(self):
        for pool in ([candidate(0), candidate(0)], [candidate(0), candidate(2)]):
            with self.subTest(pool=pool), self.assertRaises(diagnosis.DiagnosisError):
                classify(pool, budget=2)

    def test_nonnumeric_and_nonfinite_outcomes_cannot_become_failures(self):
        for field, value in (("score", float("nan")), ("score", float("inf")),
                             ("rmsd_angstrom", -1), ("rmsd_angstrom", None),
                             ("chemical_valid", 1), ("geometric_valid", "false")):
            c = candidate(0)
            c[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(diagnosis.DiagnosisError):
                classify([c])

    def test_check_ids_and_validity_cannot_disagree(self):
        for checks in (["internal_energy"], ["unknown_check"], ["internal_energy", "internal_energy"]):
            c = candidate(0)
            c["posebusters_failed_check_ids"] = checks
            with self.subTest(checks=checks), self.assertRaises(diagnosis.DiagnosisError):
                classify([c])

    def test_failure_rows_count_zero_without_losing_the_case(self):
        row = {"status": "failure", "failure_code": "unsupported_large_ring_system",
               "rmsd_angstroms": [], "chemical_valid": [], "geometric_valid": [], "pose_artifact_sha256s": []}
        self.assertEqual(set(diagnosis.topk_metrics(row).values()), {0})
        row["failure_code"] = ""
        with self.assertRaises(diagnosis.DiagnosisError):
            diagnosis.topk_metrics(row)

    def test_topk_metrics_require_complete_paired_pose_values(self):
        row = {"status": "success", "rmsd_angstroms": [1., 1., 3., 3., 3.],
               "chemical_valid": [True, False, True, True, True],
               "geometric_valid": [False, True, True, True, True], "pose_artifact_sha256s": ["x"]*5}
        observed = diagnosis.topk_metrics(row)
        self.assertEqual(observed["top1"], 1)
        self.assertEqual(observed["valid_top5"], 0)
        row["rmsd_angstroms"].pop()
        with self.assertRaises(diagnosis.DiagnosisError):
            diagnosis.topk_metrics(row)

    def test_missing_rows_cannot_be_silently_aggregated_as_zero(self):
        case = {"case_id": "missing", "candidates": [], "lineage": {}, "classifications": {
            f"top{k}": classify(None, status="unobserved", budget=64) for k in diagnosis.TOP_K}}
        engine = {"engine_v2": [{"status": "unobserved", "failure_code": "", "recoveries": diagnosis.topk_metrics(None)}]}
        with self.assertRaisesRegex(diagnosis.DiagnosisError, "unobserved engine"):
            diagnosis.summarize([case], engine)


class TestNumericalEvidence(unittest.TestCase):
    def test_score_sum_matches_historical_ordered_binary64_not_fsum(self):
        values = (1e16, 1., -1e16, 0., 0., 0., 0., 0.)
        terms = {name: value.hex() for name, value in zip(diagnosis.SCORE_COMPONENTS, values)}
        terms["total_score"] = 0.0.hex()
        self.assertEqual(diagnosis.historical_score_sum(terms), 0.0)
        self.assertEqual(math.fsum(values), 1.0)
        terms["total_score"] = 1.0.hex()
        with self.assertRaisesRegex(diagnosis.DiagnosisError, "component sum"):
            diagnosis.historical_score_sum(terms)

    def test_score_projection_requires_all_and_only_the_expected_terms(self):
        terms = {name: 0.0.hex() for name in (*diagnosis.SCORE_COMPONENTS, "total_score")}
        for change in (lambda d: d.pop("typed_vdw"), lambda d: d.update({"new_term": 0.0.hex()})):
            modified = deepcopy(terms)
            change(modified)
            with self.assertRaises(diagnosis.DiagnosisError):
                diagnosis.historical_score_sum(modified)

    def test_typed_float_binds_bits_hex_and_missingness(self):
        for value in (1.25, -0.0, float("nan")):
            cell = {"type": "numpy.float64", "binary64_be": struct.pack(">d", value).hex(),
                    "hex": value.hex(), "missing": "NaN" if math.isnan(value) else None}
            recovered = diagnosis.typed_value(cell)
            self.assertEqual(struct.pack(">d", recovered), struct.pack(">d", value))
            cell["hex"] = "0x1.0000000000000p+0"
            with self.assertRaises(diagnosis.DiagnosisError):
                diagnosis.typed_value(cell)

    def test_typed_boolean_and_integer_do_not_accept_coercion(self):
        self.assertIs(diagnosis.typed_value({"type": "numpy.bool_", "value": False}), False)
        self.assertEqual(diagnosis.typed_value({"type": "numpy.int64", "decimal": "15"}), 15)
        for cell in ({"type": "numpy.bool_", "value": 0}, {"type": "numpy.int64", "decimal": "015"},
                     {"type": "numpy.str_", "value": False}, {"type": "arbitrary", "value": 1}):
            with self.subTest(cell=cell), self.assertRaises(diagnosis.DiagnosisError):
                diagnosis.typed_value(cell)

    def test_spearman_uses_average_ties_and_handles_constant_values(self):
        self.assertEqual(diagnosis.rank_values([4., 1., 1., 3.]), [4., 1.5, 1.5, 3.])
        self.assertAlmostEqual(diagnosis.spearman([1., 2., 3.], [3., 2., 1.]), -1.)
        self.assertIsNone(diagnosis.spearman([1., 1.], [1., 2.]))

    def test_coordinate_fingerprint_binds_canonical_shape_and_bits(self):
        payload = {"shape": [1, 3], "values_hex": [1.0.hex(), 0.0.hex(), (-0.0).hex()]}
        original = diagnosis.canonical_coordinate_fingerprint(payload)
        payload["values_hex"][2] = 0.0.hex()
        self.assertNotEqual(diagnosis.canonical_coordinate_fingerprint(payload), original)
        payload["shape"] = [3, 3]
        with self.assertRaises(diagnosis.DiagnosisError):
            diagnosis.canonical_coordinate_fingerprint(payload)


class TestEvidenceIntegrity(unittest.TestCase):
    def test_json_rejects_duplicate_keys_and_nonfinite_numbers(self):
        for payload in (b'{"status":"success","status":"failure"}', b'{"rmsd":NaN}', b'{"score":Infinity}'):
            with self.subTest(payload=payload), self.assertRaises(diagnosis.DiagnosisError):
                diagnosis.parse_json(payload)

    def test_self_hash_detects_changed_scientific_result(self):
        receipt = {"case_id": "fixture", "status": "success"}
        receipt["receipt_sha256"] = diagnosis.digest(receipt)
        self.assertEqual(diagnosis.self_hash(receipt, "receipt_sha256", "receipt"), receipt["receipt_sha256"])
        receipt["status"] = "failure"
        with self.assertRaises(diagnosis.DiagnosisError):
            diagnosis.self_hash(receipt, "receipt_sha256", "receipt")

    def test_inventory_checks_content_size_and_exact_membership(self):
        with diagnosis.opened_zip(inventory_zip(), "fixture") as archive:
            inventory, members = diagnosis.verify_inventory(archive, name="artifact-inventory.json", key="files", size_key="size")
            self.assertEqual(len(members), inventory["payload_file_count"])
        for payload in (
            inventory_zip(change=lambda inv, files: files.update({"case/pose.sdf": b"tampered"})),
            inventory_zip(change=lambda inv, files: inv["files"][0].update({"sha256": "0"*64})),
            inventory_zip(extra=[("extra.json", b"{}")]),
            inventory_zip(change=lambda inv, files: inv.update({"payload_file_count": 3})),
        ):
            with self.subTest(size=len(payload)), diagnosis.opened_zip(payload, "fixture") as archive:
                with self.assertRaises(diagnosis.DiagnosisError):
                    diagnosis.verify_inventory(archive, name="artifact-inventory.json", key="files", size_key="size")

    def test_zip_rejects_duplicate_and_unsafe_members(self):
        for entries in ([('a', b'1'), ('a', b'2')], [('../outside', b'x')], [('/absolute', b'x')], [('a/./b', b'x')]):
            with self.subTest(entries=entries), self.assertRaises(diagnosis.DiagnosisError):
                with diagnosis.opened_zip(zip_bytes(entries), "fixture"):
                    pass

    def test_journal_binds_chain_checkpoint_and_scientific_receipt(self):
        files, args = journal_fixture()
        events, proof = verify_journal(files, args)
        self.assertEqual(len(events), proof["event_count"])
        self.assertEqual(events[-1]["details"]["receipt_sha256"], args["receipt"]["receipt_sha256"])
        args["receipt"]["receipt_sha256"] = "c"*64
        with self.assertRaisesRegex(diagnosis.DiagnosisError, "scientific completion"):
            verify_journal(files, args)

    def test_journal_detects_tampered_event_even_with_unchanged_inventory_context(self):
        files, args = journal_fixture()
        event = json.loads(files["journal/event-000001.json"])
        event["event"]["stage"] = "tampered"
        files["journal/event-000001.json"] = diagnosis.canonical(event)
        with self.assertRaisesRegex(diagnosis.DiagnosisError, "self hash mismatch"):
            verify_journal(files, args)

    def test_journal_detects_gap_extra_event_and_checkpoint_mismatch(self):
        for mutation in ("gap", "extra", "checkpoint"):
            files, args = journal_fixture()
            if mutation == "gap":
                files.pop("journal/event-000001.json")
            elif mutation == "extra":
                files["journal/event-000003.json"] = files["journal/event-000002.json"]
            else:
                checkpoint = json.loads(files["journal/checkpoint.json"])
                checkpoint["event_bytes_total"] += 1
                files["journal/checkpoint.json"] = diagnosis.canonical(checkpoint)
            with self.subTest(mutation=mutation), self.assertRaises(diagnosis.DiagnosisError):
                verify_journal(files, args)

    def test_cli_does_not_overwrite_inputs_or_existing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "evidence.zip"
            artifact.write_bytes(b"retained input")
            with self.assertRaisesRegex(diagnosis.DiagnosisError, "output already exists"):
                diagnosis.main(["--delivery", str(artifact), "--output", str(artifact)])
            self.assertEqual(artifact.read_bytes(), b"retained input")


if __name__ == "__main__":
    unittest.main()
