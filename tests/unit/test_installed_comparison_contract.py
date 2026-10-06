"""Stdlib-only portable integrity tests using hand-authored scalar receipts.

These fixtures do not execute molecular workers or establish physical validity.
The adjacent integration suite exercises actual current checkout run/export.
"""
import copy
import json
import shutil
from pathlib import Path
import tempfile
import unittest

from betelgeuze_product import comparison_receipts as receipts


def _report():
    def component(x):
        values = [{"$float_hex": float(v).hex()} for v in (x, 0, 0)]
        return {
            "nonbonded_parameters": [{"atom_index": 0, "charge_e": 0,
                                      "sigma_angstrom": 1, "epsilon_kcal_per_mol": 0}],
            "system": {"system": {"coordinates": {"coordinates": {"$tensor": {
                "dtype": "float64", "shape": [1, 1, 3], "values": values}}}}},
        }
    result = {
        "status": "evaluated",
        "model": {"id": "existing_v2_switched_cross_lj_screened_coulomb_v1",
                  "mixing": "Lorentz-Berthelot", "periodic": False,
                  "cross_pair_scaling": 1, "minimum_pair_distance_angstrom": 0.35,
                  "cutoff_angstrom": 10, "switch_start_angstrom": 8,
                  "dielectric": 1, "screening_kappa_per_angstrom": 0},
        "sources": {"receptor": component(0), "ligand": component(1)},
        "quantities": {"cross_lennard_jones_kcal_per_mol": 0,
                       "cross_screened_coulomb_kcal_per_mol": 0,
                       "cross_total_kcal_per_mol": 0,
                       "receptor_cross_forces_kcal_per_mol_angstrom": [[0, 0, 0]],
                       "ligand_cross_forces_kcal_per_mol_angstrom": [[0, 0, 0]]},
        "pair_accounting": {"cross_pair_indices": [[0, 0]], "requested_cross_pairs": 1,
                            "within_declared_cutoff": 1},
    }
    return {"schema_version": "prepared_rigid_pose_cross_report_v1",
            "denominator": {"requested": 1, "evaluated": 1, "failed": 0, "skipped": 0},
            "rows": [{"status": "evaluated", "result": result}]}


def _fixture():
    binding = "a" * 64
    result = {"schema_version": receipts.SCHEMA, "source_kind": "synthetic_constants",
              "legacy_protocol_version": "prepared_candidate_comparison_protocol_v1",
              "legacy_binding": binding, "pool": ["a", "b"],
              "arm_order": list(receipts.ARMS), "budget_seconds_per_arm": 10,
              "max_engine_calls_per_arm": 3,
              "execution_receipt_version": receipts.EXECUTION_VERSION,
              "request_present": {"a": True, "b": True}, "selection_seed": None,
              "scientifically_validated": False, "source_authenticated": False,
              "selector_recomputed": False, "evaluation_labels_read": 0,
              "same_prepared_assay_state_verified": False, "product_ranking_enabled": False,
              "arms": {}}
    report = _report()
    raw = receipts._canonical(report) + b"\n"
    reports = {}
    for arm in receipts.ARMS:
        preds = {} if arm == "engine" else {"a": 2.0, "b": 1.0}
        rows = []
        for index, rid in enumerate(result["pool"]):
            row = {"record_id": rid, "arm": arm, "binding": binding,
                   "status": "evaluated", "score": preds[rid] if arm == "similarity" else 0,
                   "reason": None, "prediction": preds.get(rid), "completed_monotonic": 101 + index}
            if arm != "similarity":
                name = f"reports/{arm}/{receipts._sha(rid)}.poses.json"
                reports[name] = raw
                row.update(pose_report=receipts._entry(name, raw),
                           pose_denominator=report["denominator"],
                           numeric_denominator=receipts.check_report(report)["denominator"])
            rows.append(row)
        common = {"receipt_version": receipts.EXECUTION_VERSION, "binding": binding, "arm": arm}
        result["arms"][arm] = {
            "attempt": {**common, "started_monotonic": 100, "deadline": 110},
            "completion": {**common, "status": "complete", "budget_seconds": 10,
                           "deadline": 110, "measured_process_wall_seconds": 4,
                           "termination_overhead_seconds": 0},
            "worker_complete": {**common, "stop_reason": "order_exhausted",
                                "engine_calls": 0 if arm == "similarity" else 2,
                                "committed_rows": 2, "stopped_monotonic": 103,
                                "process_cpu_seconds": 1, "process_peak_rss_kib": 1},
            "priority": {"binding": binding, "arm": arm, "evaluation_labels_read": 0,
                         "order": ["a", "b"], "predictions": preds},
            "rows": rows, "denominator": {"requested": 2, "evaluated": 2},
            "ranked_record_ids": ["a", "b"],
            "score_quantity": "predicted_negative_log10_molar_endpoint" if arm == "similarity"
            else "existing_cross_only_kcal_per_mol", "combined_assay_energy_score": None,
        }
    return result, reports


def _save(root, result, reports):
    root.mkdir(mode=0o700)
    (root / "reports").mkdir(mode=0o700)
    for arm in receipts.ARMS:
        (root / "reports" / arm).mkdir(mode=0o700)
    for name, raw in reports.items():
        (root / name).write_bytes(raw)
    _reseal(root, result, reports)


def _reseal(root, result, reports):
    raw = receipts._canonical(result) + b"\n"
    (root / "result.json").write_bytes(raw)
    manifest = {"schema_version": receipts.MANIFEST_SCHEMA,
                "result": receipts._entry("result.json", raw),
                "pose_reports": [receipts._entry(name, value) for name, value in sorted(reports.items())]}
    (root / "manifest.json").write_bytes(receipts._canonical(manifest) + b"\n")


class PortableReceiptContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "portable"
        self.result, self.reports = _fixture()
        _save(self.root, self.result, self.reports)

    def test_actual_read_only_verification_and_scalar_arithmetic(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        outcome = receipts.verify_run(self.root)
        self.assertEqual(outcome["status"], "verified", outcome)
        self.assertEqual(outcome["pose_reports_checked"], 6)
        self.assertFalse(outcome["selector_recomputed"])
        self.assertFalse(outcome["source_authenticated"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_resealed_terminal_and_evidence_tampering(self):
        cases = [
            ("version", lambda r: r.update(execution_receipt_version="old")),
            ("denominator", lambda r: r["arms"]["engine"]["denominator"].update(requested=9)),
            ("v1_arm_order", lambda r: r.update(arm_order=list(reversed(receipts.ARMS)))),
            ("ranking", lambda r: r["arms"]["engine"].update(ranked_record_ids=["b", "a"])),
            ("calls", lambda r: r["arms"]["engine"]["worker_complete"].update(engine_calls=3)),
            ("deadline", lambda r: r["arms"]["engine"]["worker_complete"].update(stop_reason="deadline")),
            ("exhausted_cap", lambda r: r["arms"]["engine"]["worker_complete"].update(stop_reason="engine_call_cap")),
            ("committed", lambda r: r["arms"]["engine"]["worker_complete"].update(committed_rows=1)),
            ("stop_time", lambda r: r["arms"]["engine"]["worker_complete"].update(stopped_monotonic=101)),
            ("attempt", lambda r: r["arms"]["engine"]["attempt"].update(started_monotonic=99)),
            ("row_binding", lambda r: r["arms"]["engine"]["rows"][0].update(binding="b"*64)),
            ("row_reverse_time", lambda r: r["arms"]["engine"]["rows"][0].update(completed_monotonic=102.5)),
            ("row_before_start", lambda r: r["arms"]["engine"]["rows"][0].update(completed_monotonic=99)),
            ("prediction", lambda r: r["arms"]["similarity"]["rows"][0].update(prediction=9)),
            ("priority", lambda r: r["arms"]["similarity"]["priority"].update(order=["b", "a"])),
            ("budget", lambda r: r["arms"]["engine"]["completion"].update(measured_process_wall_seconds=10)),
            ("boolean_request", lambda r: r["request_present"].update(a=1)),
            ("authority", lambda r: r.update(selector_recomputed=True)),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                value = copy.deepcopy(self.result)
                mutate(value)
                _reseal(self.root, value, self.reports)
                self.assertEqual(receipts.verify_run(self.root)["status"], "invalid")

    def test_raw_hash_tamper(self):
        with (self.root / "result.json").open("ab") as stream:
            stream.write(b" ")
        self.assertEqual(receipts.verify_run(self.root)["reason"], "receipt_result_hash_mismatch")

    def test_resealed_numeric_tamper(self):
        name = next(iter(self.reports))
        report = json.loads(self.reports[name])
        report["rows"][0]["result"]["quantities"]["cross_total_kcal_per_mol"] = 1
        raw = receipts._canonical(report)
        self.reports[name] = raw
        (self.root / name).write_bytes(raw)
        self.result["arms"]["engine"]["rows"][0]["pose_report"] = receipts._entry(name, raw)
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["reason"], "pose_report_denominator_mismatch")

    def test_export_then_remove_all_source_inputs(self):
        source = Path(self.temp.name) / "legacy"
        source.mkdir()
        protocol = {"schema_version": self.result["legacy_protocol_version"],
                    "source": {"kind": "synthetic_constants"},
                    "budget_seconds_per_arm": 10, "max_engine_calls_per_arm": 3}
        frozen = {"protocol": protocol, "pool": self.result["pool"],
                  "execution_receipt_version": receipts.EXECUTION_VERSION,
                  "requests": {"a": {"synthetic": True}, "b": {"synthetic": True}}}
        binding = receipts._sha(frozen)
        legacy = {"schema_version": "prepared_candidate_comparison_result_v1",
                  "execution_receipt_version": receipts.EXECUTION_VERSION,
                  "binding": binding, "pool": self.result["pool"], "arms": {},
                  "evaluation_labels_read": 0, "scientifically_validated": False,
                  "product_ranking_enabled": False}

        def write(path, value):
            path.write_bytes(receipts._canonical(value) + b"\n")

        write(source / "frozen.json", {"payload": frozen, "sha256": binding})
        for arm, original in self.result["arms"].items():
            directory = source / arm
            directory.mkdir()
            data = copy.deepcopy(original)
            for key in ("attempt", "completion", "priority", "worker_complete"):
                data[key]["binding"] = binding
                name = "worker-complete" if key == "worker_complete" else key
                write(directory / (name + ".json"), data[key])
            for row in data["rows"]:
                row["binding"] = binding
                if "pose_report" in row:
                    ref = row["pose_report"]
                    raw = self.reports[ref["path"]]
                    dest = directory / Path(ref["path"]).name
                    dest.write_bytes(raw)
                    row["pose_report"] = {"path": str(dest), "sha256": receipts._digest(raw)}
                write(directory / (receipts._sha(row["record_id"]) + ".row.json"),
                      {"payload": row, "sha256": receipts._sha(row)})
            legacy["arms"][arm] = {
                "cost": data["completion"],
                "worker_observations": {"priority.json": data["priority"],
                                        "worker-complete.json": data["worker_complete"]},
                **{key: data[key] for key in ("rows", "denominator", "ranked_record_ids",
                                             "score_quantity", "combined_assay_energy_score")},
            }
        write(source / "comparison.json", legacy)
        before = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
        output = Path(self.temp.name) / "exported"
        row_path = source / "engine" / (receipts._sha("a") + ".row.json")
        wrapped = json.loads(row_path.read_bytes())
        wrapped["payload"]["completed_monotonic"] = 111
        wrapped["sha256"] = receipts._sha(wrapped["payload"])
        write(row_path, wrapped)
        with self.assertRaisesRegex(ValueError, "row_outside_reserved_budget"):
            receipts.export_legacy_synthetic(source, output)
        self.assertFalse(output.exists())
        row_path.write_bytes(before[row_path])
        self.assertEqual(receipts.export_legacy_synthetic(source, output)["status"], "verified")
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        shutil.rmtree(source)
        self.assertEqual(receipts.verify_run(output)["status"], "verified")
        self.assertFalse((output / "frozen.json").exists())

    def test_symlink_report_is_rejected(self):
        path = self.root / next(iter(self.reports))
        saved = Path(self.temp.name) / "outside.json"
        path.rename(saved)
        path.symlink_to(saved)
        self.assertEqual(receipts.verify_run(self.root)["status"], "invalid")

    def test_extra_report_is_rejected(self):
        (self.root / "reports" / "engine" / "extra.poses.json").write_text("{}")
        self.assertEqual(receipts.verify_run(self.root)["reason"], "unexpected_pose_report_file")

    def test_missing_prepared_request_does_not_count_as_engine_call(self):
        self.result["request_present"]["b"] = False
        for arm in receipts.ARMS[1:]:
            data = self.result["arms"][arm]
            row = data["rows"][1]
            removed = row.pop("pose_report")["path"]
            del self.reports[removed]
            (self.root / removed).unlink()
            row.pop("pose_denominator")
            row.pop("numeric_denominator")
            row.update(status="unsupported", score=None, reason="prepared_input_missing")
            data["worker_complete"]["engine_calls"] = 1
            data.update(denominator={"requested": 2, "evaluated": 1, "unsupported": 1},
                        ranked_record_ids=["a"])
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["status"], "verified")

    def test_cap_on_final_row_is_order_exhausted(self):
        self.result["max_engine_calls_per_arm"] = 2
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["status"], "verified")
        self.result["arms"]["engine"]["worker_complete"]["stop_reason"] = "engine_call_cap"
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["reason"], "invalid_engine_call_cap")

    def test_entirely_abstaining_selector(self):
        data = self.result["arms"]["similarity"]
        data["priority"].update(order=[], predictions={})
        data["rows"] = [{"record_id": rid, "status": "unsupported", "score": None,
                         "reason": "predictor_abstained"} for rid in self.result["pool"]]
        data["worker_complete"].update(committed_rows=0)
        data.update(denominator={"requested": 2, "unsupported": 2}, ranked_record_ids=[])
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["status"], "verified")

    def test_v2_seed_bounds_and_arm_order(self):
        self.result.update(legacy_protocol_version="prepared_candidate_comparison_protocol_v2",
                           selection_seed=17, arm_order=list(reversed(receipts.ARMS)))
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["status"], "verified")
        for seed in (-1, 2**32, True):
            self.result["selection_seed"] = seed
            _reseal(self.root, self.result, self.reports)
            self.assertEqual(receipts.verify_run(self.root)["reason"], "invalid_selection_seed")

    def test_valid_cap_preserves_unprocessed_candidate(self):
        self.result["max_engine_calls_per_arm"] = 1
        for arm in receipts.ARMS[1:]:
            data = self.result["arms"][arm]
            removed = data["rows"][1]["pose_report"]["path"]
            del self.reports[removed]
            (self.root / removed).unlink()
            data["rows"][1] = {"record_id": "b", "status": "not_processed", "score": None,
                               "reason": "engine_call_cap"}
            data["worker_complete"].update(engine_calls=1, committed_rows=1, stop_reason="engine_call_cap")
            data.update(denominator={"requested": 2, "evaluated": 1, "not_processed": 1}, ranked_record_ids=["a"])
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["status"], "verified")

    def test_abstention_remains_in_denominator(self):
        for arm in ("similarity", "ai_engine", "similarity_engine"):
            data = self.result["arms"][arm]
            if arm != "similarity":
                removed = data["rows"][1]["pose_report"]["path"]
                del self.reports[removed]
                (self.root / removed).unlink()
            data["priority"].update(order=["a"], predictions={"a": 2.0})
            data["rows"][1] = {"record_id": "b", "status": "unsupported", "score": None,
                               "reason": "predictor_abstained"}
            data["worker_complete"].update(engine_calls=0 if arm == "similarity" else 1, committed_rows=1)
            data.update(denominator={"requested": 2, "evaluated": 1, "unsupported": 1}, ranked_record_ids=["a"])
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["status"], "verified")
        data = self.result["arms"]["similarity"]
        data["rows"][1].update(status="not_processed", reason="order_exhausted")
        data["denominator"] = {"requested": 2, "evaluated": 1, "not_processed": 1}
        _reseal(self.root, self.result, self.reports)
        self.assertEqual(receipts.verify_run(self.root)["reason"], "invalid_row_terminal_observation")


if __name__ == "__main__":
    unittest.main()
