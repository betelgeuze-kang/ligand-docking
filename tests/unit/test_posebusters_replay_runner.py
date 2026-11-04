"""Controller admission tests use synthetic bytes and reports, never molecules."""
from argparse import Namespace
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import run_posebusters_replay as replay


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def float_cell(value):
    return {"type": "builtins.float", "binary64_be": struct.pack(">d", value).hex(),
            "hex": value.hex(), "missing": "NaN" if math.isnan(value) else None}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(replay.canonical(value) + b"\n")
    return sha(path.read_bytes())


def file_descriptor(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"relative_path": relative, "path": str(root / relative),
            "sha256": sha(payload), "size_bytes": len(payload)}


def make_bundle(root):
    """Synthetic portable data exercises actual path/hash/order admission."""
    root.mkdir(parents=True)
    cases, reconstructions = [], []
    for case_id in replay.PILOT_CASES:
        records = [f"{case_id}_engine_v2_rank_{rank}\nsynthetic payload {rank}\n$$$$\n".encode("ascii")
                   for rank in range(1, 65)]
        outcomes = [{"rank": rank, "proposal_index": rank-1, "record_sha256": sha(record),
            "rmsd_angstrom": float(rank)/10, "rmsd_binary64_hex": (float(rank)/10).hex(),
            "geometric_valid": rank % 2 == 1, "chemical_valid": True,
            "failed_check_ids": [] if rank % 2 else ["minimum_distance_to_protein"]}
            for rank, record in enumerate(records, 1)]
        case = {"case_id": case_id,
            "native": file_descriptor(root, f"cases/{case_id}/native.sdf", b"native:" + case_id.encode()),
            "receptor": file_descriptor(root, f"cases/{case_id}/protein.pdb", b"protein:" + case_id.encode()),
            "top5": file_descriptor(root, f"cases/{case_id}/top5.sdf", b"".join(records[:5])),
            "legacy_top5_outcomes": outcomes[:5],
            "candidates_sorted": [{"legacy_outcome": row} for row in outcomes]}
        case["top5"].update(record_sha256s=[sha(record) for record in records[:5]], record_count=5)
        candidate_file = file_descriptor(root, f"cases/{case_id}/candidates64.sdf", b"".join(records))
        candidate_file.update(case_id=case_id, record_sha256s=[sha(record) for record in records], record_count=64)
        cases.append(case)
        reconstructions.append(candidate_file)
    manifest = {"schema_id": replay.inputs.SCHEMA_ID, "source_run_id": replay.inputs.SOURCE_RUN_ID,
                "output_root": str(root), "cases": cases}
    manifest_sha = write_json(root / "manifest.json", manifest)
    bundle = {"schema_id": replay.SCHEMA, "protocol": deepcopy(replay.PROTOCOL),
        "source": {"commit": "fixture-commit", "tree": "fixture-tree", "protocol_sha256": replay.digest(replay.PROTOCOL)},
        "manifest_sha256": manifest_sha, "reconstructions": reconstructions}
    bundle_sha = write_json(root / "bundle.json", bundle)
    return bundle, manifest, bundle_sha


def make_result(selected, mode="baseline"):
    expected, input_ids = selected["expected"], selected["input_ids"]
    count, case_id = len(expected), selected["case"]["case_id"]
    report = {"index_policy": "validated_original_mol_identity_replaced_by_record_sha256_and_ordinal",
        "index_names": ["file", "molecule"], "columns": ["rmsd", "valid_check", "integer", "optional"],
        "dtypes": [{"name": "float64", "type": "numpy.dtypes.Float64DType"},
                   {"name": "bool", "type": "numpy.dtypes.BoolDType"},
                   {"name": "int64", "type": "numpy.dtypes.Int64DType"},
                   {"name": "object", "type": "numpy.dtypes.ObjectDType"}],
        "rows": [{"record_ordinal": index+1, "record_sha256": outcome["record_sha256"],
            "molecule_name": f"{case_id}_engine_v2_rank_{index+1}",
            "cells": [float_cell(float.fromhex(outcome["rmsd_binary64_hex"])),
                      {"type": "builtins.bool", "value": outcome["geometric_valid"]},
                      {"type": "builtins.int", "decimal": str(index)},
                      {"type": "builtins.NoneType", "missing": "None"}]}
                 for index, outcome in enumerate(expected)]}
    legacy = deepcopy(replay.legacy_projection(expected))
    legacy["rmsds"] = [float.fromhex(row["rmsd_binary64_hex"]) for row in expected]
    fingerprint = {"predicted": [sha(f"mol-{i}".encode()) for i in range(count)],
                   "native": sha(b"native-mol"), "receptor": sha(b"receptor-mol")}
    return {"schema_id": "betelgeuze.posebusters_same_pose_replay/1.0.0", "status": "success",
        "mode": mode, "record_count": count, "case_id": case_id, "input_ids": deepcopy(input_ids),
        "legacy_outcomes": legacy, "fullReport": report,
        "evaluator_versions": {"posebusters": "0.3.1", "rdkit": "2022.9.5"},
        "python_version": "3.10.22", "upstream_source_sha256": {"posebusters.py": "a"*64},
        "input_immutability": {"verified": True, "before": deepcopy(fingerprint), "after": deepcopy(fingerprint),
                               "pickle_policy": "AllProps|CoordsAsDouble"},
        "energy_cache": {"cleared_at_entry": True, "cleared_at_exit": True},
        "timings": {"instrumented": mode != "baseline", "profile_timing_is_diagnostic": mode == "profile",
                    "end_to_end_ns": 1200, "posebusters_ns": 1000, "decode_ns": 100}}


def make_case_evidence(directory, bundle, bundle_sha, selected, stage="pilot"):
    directory.mkdir(parents=True)
    case_id = selected["case"]["case_id"]
    summary = {"schema_id": replay.SCHEMA, "status": "success", "case_id": case_id, "stage": stage,
        "source": deepcopy(bundle["source"]), "bundle_sha256": bundle_sha,
        "protocol_sha256": replay.digest(replay.PROTOCOL), "observations": [],
        "execution_context": {"python_executable": "/original/venv/bin/python",
            "input_root": "/original/prepared", "output_root": f"/original/results/{stage}-{case_id}",
            "working_directory": "/original/repo"}}
    for slot, mode in enumerate(replay.PROTOCOL[f"{stage}_order"]):
        result_path = f"result-{slot}-{mode}.json"
        context = summary["execution_context"]
        execution = {"schema_id": "betelgeuze.redocking_process_execution/1.0.0",
            "command": [context["python_executable"], "-m", "tools.run_posebusters_replay", "worker",
                "--input-root", context["input_root"], "--bundle-sha256", bundle_sha,
                "--case-id", case_id, "--stage", stage, "--mode", mode,
                "--output", context["output_root"] + "/" + result_path],
            "returncode": 0, "termination": "exited", "cleanup_complete": True,
            "wall_limit_seconds": replay.PROTOCOL["wall_limit_seconds"][stage],
            "rss_limit_bytes": replay.PROTOCOL["rss_limit_bytes"],
            "rss_sampling_seconds": replay.PROTOCOL["rss_sampling_seconds"],
            "wall_seconds": 0.001, "child_cpu_seconds": 0.0005,
            "sampled_peak_process_tree_rss_bytes": 4096, "error": None}
        execution["control_sha256"] = replay.digest(execution)
        execution_path = f"worker-{slot}-{mode}/process-execution.json"
        execution_sha = write_json(directory / execution_path, execution)
        result = make_result(selected, mode)
        result.update(stage=stage, source=deepcopy(bundle["source"]), bundle_sha256=bundle_sha,
                      protocol_sha256=replay.digest(replay.PROTOCOL))
        result_sha = write_json(directory / result_path, result)
        summary["observations"].append({"slot": slot, "mode": mode, "execution_path": execution_path,
            "execution_sha256": execution_sha, "result_path": result_path, "result_sha256": result_sha,
            "process_gate_passed": True})
    for name in ("environment-before.json", "environment-after.json"):
        write_json(directory / name, {"content_identity_sha256": "c"*64, "fixture": True})
    with patch.object(replay.evidence, "require_matching_environment", side_effect=lambda left, right: replay.equal(left, right, "fixture environment")):
        summary["assessment"] = replay.assess_case(directory, summary, selected=selected,
            bundle=bundle, bundle_sha256=bundle_sha)
    write_json(directory / "case-summary.json", summary)
    return summary


class ControllerFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.bundle, self.manifest, self.bundle_sha = make_bundle(self.inputs)
        self.case_id = replay.PILOT_CASES[0]
        self.selected = replay.selected_inputs(self.inputs, self.bundle, self.manifest, self.case_id, "pilot")


class TestExactScientificComparison(ControllerFixture):
    def test_equal_values_allow_dictionary_order_but_not_scalar_type_coercion(self):
        replay.equal({"a": 1, "b": 2}, {"b": 2, "a": 1}, "mapping")
        for left, right in ((True, 1), (False, 0), (1.0, 1), (-0.0, 0.0), ([1, 2], [2, 1])):
            with self.subTest(left=left, right=right), self.assertRaises(replay.ReplayProtocolError):
                replay.equal(left, right, "typed exactness")

    def test_identical_full_science_reports_pass_despite_different_timing_and_mode(self):
        baseline = make_result(self.selected)
        other = make_result(self.selected, "prepared_receptor")
        other["timings"]["posebusters_ns"] = 700
        result = replay.compare_results(baseline, other)
        self.assertTrue(result["all_full_report_cells_exact"])
        self.assertFalse(result["tolerance_used"])
        self.assertEqual(result["full_report_sha256"], replay.digest(baseline["fullReport"]))

    def test_float_bits_signed_zero_na_type_columns_dtype_and_order_changes_fail(self):
        baseline = make_result(self.selected)
        # Include an actual signed zero and typed missing value in the raw report.
        baseline["fullReport"]["rows"][0]["cells"][0] = float_cell(-0.0)
        mutations = {
            "signed_zero": lambda r: r["fullReport"]["rows"][0]["cells"].__setitem__(0, float_cell(0.0)),
            "float_ulp": lambda r: r["fullReport"]["rows"][1]["cells"].__setitem__(0, float_cell(math.nextafter(0.2, math.inf))),
            "float_type": lambda r: r["fullReport"]["rows"][0]["cells"][0].update(type="numpy.float64"),
            "bool_int": lambda r: r["fullReport"]["rows"][0]["cells"][1].update(value=1),
            "missing_category": lambda r: r["fullReport"]["rows"][0]["cells"][3].update(missing="pandas.NA"),
            "column_label": lambda r: r["fullReport"]["columns"].__setitem__(0, "different_rmsd"),
            "column_order": lambda r: r["fullReport"]["columns"].reverse(),
            "dtype": lambda r: r["fullReport"]["dtypes"][0].update(name="float32"),
            "row_order": lambda r: r["fullReport"]["rows"].reverse(),
            "cell_order": lambda r: r["fullReport"]["rows"][0]["cells"].reverse(),
            "input_identity": lambda r: r["input_ids"].update(native_sha256="b"*64),
            "evaluator_version": lambda r: r["evaluator_versions"].update(posebusters="0.3.2"),
            "python": lambda r: r.update(python_version="3.11.0"),
            "upstream_source": lambda r: r["upstream_source_sha256"].update(**{"posebusters.py": "b"*64}),
        }
        for name, change in mutations.items():
            with self.subTest(change=name):
                observed = deepcopy(baseline)
                change(observed)
                with self.assertRaises(replay.ReplayProtocolError):
                    replay.compare_results(baseline, observed)


class TestResultAdmission(ControllerFixture):
    def test_valid_results_for_all_modes_pass(self):
        for mode in ("baseline", "prepared_receptor", "profile"):
            with self.subTest(mode=mode):
                replay.validate_result(make_result(self.selected, mode), selected=self.selected, mode=mode)

    def test_malformed_denominators_rmsd_validity_and_timing_fail(self):
        mutations = {
            "failed_status": lambda r: r.update(status="failed"),
            "wrong_mode": lambda r: r.update(mode="profile"),
            "bool_count": lambda r: r.update(record_count=True),
            "wrong_count": lambda r: r.update(record_count=4),
            "wrong_input": lambda r: r["input_ids"].update(receptor_sha256="f"*64),
            "rmsd_int": lambda r: r["legacy_outcomes"]["rmsds"].__setitem__(0, 1),
            "rmsd_nan": lambda r: r["legacy_outcomes"]["rmsds"].__setitem__(0, float("nan")),
            "rmsd_negative": lambda r: r["legacy_outcomes"]["rmsds"].__setitem__(0, -1.0),
            "rmsd_bits": lambda r: r["legacy_outcomes"]["rmsds_binary64_hex"].__setitem__(0, (0.2).hex()),
            "bool_to_int": lambda r: r["legacy_outcomes"]["chemical_valid"].__setitem__(0, 1),
            "failed_checks": lambda r: r["legacy_outcomes"]["failed_check_ids"][0].append("invented"),
            "columns_missing": lambda r: r["fullReport"].update(columns=[]),
            "duplicate_columns": lambda r: r["fullReport"]["columns"].__setitem__(1, "rmsd"),
            "dtype_count": lambda r: r["fullReport"]["dtypes"].pop(),
            "row_count": lambda r: r["fullReport"]["rows"].pop(),
            "bool_ordinal": lambda r: r["fullReport"]["rows"][0].update(record_ordinal=True),
            "record_binding": lambda r: r["fullReport"]["rows"][0].update(record_sha256="e"*64),
            "molecule_title": lambda r: r["fullReport"]["rows"][0].update(molecule_name="native-template"),
            "cell_count": lambda r: r["fullReport"]["rows"][0]["cells"].pop(),
            "unverified_immutability": lambda r: r["input_immutability"].update(verified=False),
            "input_mutation": lambda r: r["input_immutability"]["after"].update(native="changed"),
            "uncleared_cache_entry": lambda r: r["energy_cache"].update(cleared_at_entry=False),
            "uncleared_cache_exit": lambda r: r["energy_cache"].update(cleared_at_exit=False),
            "wrong_instrumentation": lambda r: r["timings"].update(instrumented=True),
            "wrong_profile_flag": lambda r: r["timings"].update(profile_timing_is_diagnostic=True),
            "timer_zero": lambda r: r["timings"].update(posebusters_ns=0),
            "timer_bool": lambda r: r["timings"].update(decode_ns=True),
        }
        for name, change in mutations.items():
            with self.subTest(change=name):
                result = make_result(self.selected)
                change(result)
                with self.assertRaises((replay.ReplayProtocolError, KeyError, TypeError, ValueError)):
                    replay.validate_result(result, selected=self.selected, mode="baseline")

    def test_missing_required_result_sections_cannot_pass(self):
        for key in ("input_ids", "legacy_outcomes", "fullReport", "input_immutability", "energy_cache", "timings"):
            with self.subTest(key=key):
                result = make_result(self.selected)
                result.pop(key)
                with self.assertRaises((replay.ReplayProtocolError, KeyError, TypeError)):
                    replay.validate_result(result, selected=self.selected, mode="baseline")

    def test_self_consistent_new_measurement_still_must_match_historical_value(self):
        result = make_result(self.selected)
        replacement = math.nextafter(result["legacy_outcomes"]["rmsds"][0], math.inf)
        result["legacy_outcomes"]["rmsds"][0] = replacement
        result["legacy_outcomes"]["rmsds_binary64_hex"][0] = replacement.hex()
        result["fullReport"]["rows"][0]["cells"][0] = float_cell(replacement)
        with self.assertRaisesRegex(replay.ReplayProtocolError, "historical scientific outcomes"):
            replay.validate_result(result, selected=self.selected, mode="baseline")

    def test_malformed_typed_cells_and_index_schema_cannot_pass(self):
        mutations = {
            "empty_cell": lambda r: r["fullReport"]["rows"][0]["cells"].__setitem__(0, {}),
            "invalid_binary64": lambda r: r["fullReport"]["rows"][0]["cells"][0].update(binary64_be="not-hex"),
            "inconsistent_binary64": lambda r: r["fullReport"]["rows"][0]["cells"][0].update(binary64_be=struct.pack(">d", 1.0).hex()),
            "float_missing_lie": lambda r: r["fullReport"]["rows"][0]["cells"][0].update(missing="NaN"),
            "int_leading_zero": lambda r: r["fullReport"]["rows"][0]["cells"][2].update(decimal="00"),
            "bool_value_int": lambda r: r["fullReport"]["rows"][0]["cells"][1].update(value=1),
            "wrong_missing_kind": lambda r: r["fullReport"]["rows"][0]["cells"][3].update(missing="untracked"),
            "wrong_index_names": lambda r: r["fullReport"].update(index_names=["address", "unverified"]),
            "wrong_index_policy": lambda r: r["fullReport"].update(index_policy="accept-anything"),
            "malformed_dtype": lambda r: r["fullReport"]["dtypes"].__setitem__(0, {}),
        }
        for name, change in mutations.items():
            with self.subTest(change=name):
                result = make_result(self.selected)
                change(result)
                with self.assertRaises((replay.ReplayProtocolError, KeyError, TypeError, ValueError)):
                    replay.validate_result(result, selected=self.selected, mode="baseline")


class TestPortableBoundInputs(ControllerFixture):
    def test_bundle_remains_valid_after_root_migration_without_rewriting_absolute_paths(self):
        moved = self.root / "moved-inputs"
        shutil.copytree(self.inputs, moved)
        shutil.rmtree(self.inputs)
        bundle, manifest = replay.load_bundle(moved, self.bundle_sha)
        self.assertFalse(Path(manifest["cases"][0]["native"]["path"]).exists())
        selected = replay.selected_inputs(moved, bundle, manifest, self.case_id, "pilot")
        self.assertEqual(selected["records"], self.selected["records"])
        self.assertEqual(selected["input_ids"], self.selected["input_ids"])
        expanded = replay.selected_inputs(moved, bundle, manifest, replay.EXPANDED_CASES[0], "expanded")
        self.assertEqual(len(expanded["records"]), 64)

    def test_path_traversal_absolute_symlink_and_symlink_ancestor_fail(self):
        outside = self.root / "outside.txt"
        outside.write_bytes(b"untrusted")
        (self.inputs / "link").symlink_to(outside)
        (self.inputs / "linked-parent").symlink_to(self.inputs / "cases", target_is_directory=True)
        for relative in ("../outside.txt", str(outside), "cases/../bundle.json", "link",
                         f"linked-parent/{self.case_id}/native.sdf"):
            with self.subTest(relative=relative), self.assertRaises((ValueError, replay.ReplayProtocolError)):
                replay.relative_file(self.inputs, relative)

    def test_input_hash_size_and_record_order_bindings_reject_tampering(self):
        for change in ("hash", "size", "bool_size", "record_order", "historical_order", "wrong_denominator"):
            with self.subTest(change=change):
                case = deepcopy(self.manifest["cases"][0])
                manifest = deepcopy(self.manifest)
                manifest["cases"][0] = case
                if change == "hash": case["native"]["sha256"] = "0" * 64
                elif change == "size": case["receptor"]["size_bytes"] += 1
                elif change == "bool_size": case["receptor"]["size_bytes"] = True
                elif change == "record_order": case["top5"]["record_sha256s"].reverse()
                elif change == "historical_order": case["legacy_top5_outcomes"].reverse()
                else: case["top5"] = deepcopy(self.bundle["reconstructions"][0])
                with self.assertRaises(replay.ReplayProtocolError):
                    replay.selected_inputs(self.inputs, self.bundle, manifest, self.case_id, "pilot")

    def test_bundle_and_manifest_hashes_are_independent_gates(self):
        with self.assertRaisesRegex(replay.ReplayProtocolError, "bundle SHA256"):
            replay.load_bundle(self.inputs, "0" * 64)
        path = self.inputs / "manifest.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(replay.ReplayProtocolError, "manifest SHA256"):
            replay.load_bundle(self.inputs, self.bundle_sha)

    def test_fixed_case_order_and_protocol_are_checked_even_after_json_rehashed(self):
        for change in ("case_order", "reconstruction_order", "protocol"):
            with self.subTest(change=change):
                bundle, manifest = deepcopy(self.bundle), deepcopy(self.manifest)
                if change == "case_order":
                    manifest["cases"].reverse()
                    bundle["manifest_sha256"] = write_json(self.inputs / "manifest.json", manifest)
                elif change == "reconstruction_order": bundle["reconstructions"].reverse()
                else: bundle["protocol"]["numerical_tolerance"] = 1e-3
                bundle_sha = write_json(self.inputs / "bundle.json", bundle)
                with self.assertRaises(replay.ReplayProtocolError):
                    replay.load_bundle(self.inputs, bundle_sha)
                write_json(self.inputs / "manifest.json", self.manifest)
                write_json(self.inputs / "bundle.json", self.bundle)

    def test_stage_membership_is_enforced(self):
        for case_id, stage in ((self.case_id, "expanded"), ("unknown", "pilot"), (self.case_id, "other")):
            with self.subTest(case_id=case_id, stage=stage), self.assertRaises(replay.ReplayProtocolError):
                replay.selected_inputs(self.inputs, self.bundle, self.manifest, case_id, stage)


class TestProcessAndCaseAssessment(ControllerFixture):
    def setUp(self):
        super().setUp()
        self.directory = self.root / "case-evidence"
        self.summary = make_case_evidence(self.directory, self.bundle, self.bundle_sha, self.selected)
        environment_patch = patch.object(replay.evidence, "require_matching_environment",
            side_effect=lambda left, right: replay.equal(left, right, "fixture environment"))
        environment_patch.start()
        self.addCleanup(environment_patch.stop)

    def assess(self, summary=None):
        return replay.assess_case(self.directory, self.summary if summary is None else summary,
            selected=self.selected, bundle=self.bundle, bundle_sha256=self.bundle_sha)

    def test_execution_gate_requires_typed_zero_exit_natural_completion_and_cleanup(self):
        self.assertTrue(replay.execution_ok({"returncode": 0, "termination": "exited", "cleanup_complete": True}))
        for record in ({}, {"returncode": False, "termination": "exited", "cleanup_complete": True},
            {"returncode": 1, "termination": "exited", "cleanup_complete": True},
            {"returncode": 0, "termination": "wall_timeout", "cleanup_complete": True},
            {"returncode": 0, "termination": "remaining_descendants_terminated", "cleanup_complete": True},
            {"returncode": 0, "termination": "sampled_rss_limit", "cleanup_complete": True},
            {"returncode": 0, "termination": "exited", "cleanup_complete": False},
            {"returncode": 0, "termination": "exited", "cleanup_complete": 1}):
            with self.subTest(record=record):
                self.assertFalse(replay.execution_ok(record))

    def test_case_recomputes_science_and_excludes_profile_from_performance_pairs(self):
        assessment = self.assess()
        self.assertTrue(assessment["exact_equivalence_passed"])
        self.assertEqual(len(assessment["comparisons"]), 4)
        self.assertEqual([(p["baseline_slot"], p["prepared_slot"]) for p in assessment["pairs"]], [(0, 1), (3, 2)])
        self.assertEqual(assessment["median_saved_fraction"], 0.0)
        self.assertNotIn(4, [p["prepared_slot"] for p in assessment["pairs"]])

    def test_case_rejects_missing_duplicate_bool_slot_and_wrong_worker_order(self):
        for change in ("missing", "duplicate", "bool_slot", "wrong_mode"):
            with self.subTest(change=change):
                summary = deepcopy(self.summary)
                if change == "missing": summary["observations"].pop()
                elif change == "duplicate": summary["observations"][1] = deepcopy(summary["observations"][0])
                elif change == "bool_slot": summary["observations"][0]["slot"] = False
                else: summary["observations"][0]["mode"] = "profile"
                with self.assertRaises(replay.ReplayProtocolError):
                    self.assess(summary)

    def test_forged_process_pass_flag_cannot_override_bad_execution_receipt(self):
        observation = self.summary["observations"][0]
        execution_path = self.directory / observation["execution_path"]
        original = json.loads(execution_path.read_bytes())
        for change in ({"returncode": 2}, {"termination": "wall_timeout"}, {"cleanup_complete": False}):
            with self.subTest(change=change):
                record = deepcopy(original)
                record.update(change)
                record.pop("control_sha256")
                record["control_sha256"] = replay.digest(record)
                observation["execution_sha256"] = write_json(execution_path, record)
                observation["process_gate_passed"] = True
                with self.assertRaises(replay.ReplayProtocolError):
                    self.assess()

    def test_missing_result_corrupt_receipt_hash_and_rebound_scientific_difference_fail(self):
        first = self.summary["observations"][1]
        path = self.directory / first["result_path"]
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises((ValueError, replay.ReplayProtocolError)):
            self.assess()
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(replay.ReplayProtocolError, "result hash"):
            self.assess()
        changed = json.loads(original)
        changed["fullReport"]["rows"][0]["cells"][0] = float_cell(0.3)
        first["result_sha256"] = write_json(path, changed)
        with self.assertRaisesRegex(replay.ReplayProtocolError, "full-report RMSD differs from historical scientific outcomes"):
            self.assess()

    def test_changed_environment_fails_before_performance_acceptance(self):
        write_json(self.directory / "environment-after.json", {"content_identity_sha256": "changed"})
        with self.assertRaisesRegex(replay.ReplayProtocolError, "fixture environment"):
            self.assess()

    def test_execution_receipt_is_bound_to_selfhash_protocol_and_original_argv(self):
        observation = self.summary["observations"][0]
        original = json.loads((self.directory / observation["execution_path"]).read_bytes())
        arguments = {"summary": self.summary, "slot": 0, "mode": "baseline",
                     "result_relative_path": observation["result_path"]}
        # Original execution paths deliberately do not exist after relocation.
        replay.validate_execution(original, **arguments)
        stale_hash = deepcopy(original)
        stale_hash["wall_seconds"] = 0.5
        with self.assertRaises(replay.ReplayProtocolError):
            replay.validate_execution(stale_hash, **arguments)
        mutations = {
            "schema": lambda r: r.update(schema_id="unrecognized"),
            "wrong_python": lambda r: r["command"].__setitem__(0, "/other/python"),
            "wrong_native_input_root": lambda r: r["command"].__setitem__(5, "/other/prepared"),
            "wrong_bundle": lambda r: r["command"].__setitem__(7, "0"*64),
            "wrong_case": lambda r: r["command"].__setitem__(9, "6YSP_PAL"),
            "wrong_stage": lambda r: r["command"].__setitem__(11, "expanded"),
            "wrong_mode": lambda r: r["command"].__setitem__(13, "profile"),
            "wrong_output": lambda r: r["command"].__setitem__(15, "/tmp/unbound.json"),
            "extra_argv": lambda r: r["command"].append("--unreviewed-option"),
            "wall_policy": lambda r: r.update(wall_limit_seconds=1),
            "float_wall_policy": lambda r: r.update(wall_limit_seconds=float(replay.PROTOCOL["wall_limit_seconds"]["pilot"])),
            "rss_policy": lambda r: r.update(rss_limit_bytes=1024),
            "sampling_policy": lambda r: r.update(rss_sampling_seconds=0.5),
            "zero_wall": lambda r: r.update(wall_seconds=0),
            "negative_cpu": lambda r: r.update(child_cpu_seconds=-1),
            "bool_peak_rss": lambda r: r.update(sampled_peak_process_tree_rss_bytes=True),
            "supervisor_error": lambda r: r.update(error={"exception_type": "hidden"}),
        }
        for name, change in mutations.items():
            with self.subTest(change=name):
                record = deepcopy(original)
                change(record)
                record.pop("control_sha256")
                record["control_sha256"] = replay.digest(record)
                with self.assertRaises((replay.ReplayProtocolError, KeyError, TypeError, ValueError)):
                    replay.validate_execution(record, **arguments)

    def test_execution_context_and_result_paths_are_canonical_and_portable(self):
        observation = self.summary["observations"][0]
        record = json.loads((self.directory / observation["execution_path"]).read_bytes())
        for key in self.summary["execution_context"]:
            for invalid in ("relative/path", "/original/../different", "/original//different"):
                with self.subTest(key=key, invalid=invalid):
                    summary = deepcopy(self.summary)
                    summary["execution_context"][key] = invalid
                    with self.assertRaises((replay.ReplayProtocolError, ValueError)):
                        replay.validate_execution(record, summary=summary, slot=0, mode="baseline",
                            result_relative_path=observation["result_path"])
        for relative in ("../outside.json", "wrong-result.json", "/absolute/result.json"):
            with self.subTest(relative=relative), self.assertRaises((replay.ReplayProtocolError, ValueError)):
                replay.validate_execution(record, summary=self.summary, slot=0, mode="baseline",
                    result_relative_path=relative)

    @unittest.skipUnless(sys.platform.startswith("linux") and Path("/proc").is_dir(), "supervisor requires Linux procfs")
    def test_real_tiny_workers_exit_and_timeout_are_distinguished_with_receipts(self):
        for label, script, wall, expected in (
            ("exit-zero", "pass", 3.0, True),
            ("exit-nonzero", "raise SystemExit(7)", 3.0, False),
            ("timeout", "import time; time.sleep(30)", 0.2, False),
        ):
            with self.subTest(label=label):
                directory = self.root / label
                record = replay.isolation.supervise([sys.executable, "-c", script], directory,
                    replay.isolation.Limits(wall_seconds=wall, poll_seconds=0.05,
                        terminate_grace_seconds=0.1, cleanup_seconds=1.0))
                self.assertEqual(replay.execution_ok(record), expected)
                self.assertIs(record["cleanup_complete"], True)
                self.assertTrue((directory / "process-execution.json").is_file())
                if label == "timeout": self.assertEqual(record["termination"], "wall_timeout")


class TestAggregateCannotHideFailures(ControllerFixture):
    def setUp(self):
        super().setUp()
        self.results = self.root / "results"
        self.results.mkdir()
        self.environment_patch = patch.object(replay.evidence, "require_matching_environment",
            side_effect=lambda left, right: replay.equal(left, right, "fixture environment"))
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)

    def add_case(self, case_id, *, stage="pilot", directory_name=None):
        directory = self.results / (directory_name or f"{stage}-{case_id}")
        selected = replay.selected_inputs(self.inputs, self.bundle, self.manifest, case_id, stage)
        summary = make_case_evidence(directory, self.bundle, self.bundle_sha, selected, stage=stage)
        return directory, summary

    def aggregate(self, name, stage="pilot"):
        output = self.root / (name + ".json")
        args = Namespace(input_root=self.inputs, bundle_sha256=self.bundle_sha, stage=stage,
                         results_root=self.results, output=output)
        with redirect_stdout(io.StringIO()):
            code = replay.aggregate(args)
        return code, json.loads(output.read_bytes())

    def test_all_complete_cases_pass_and_empty_or_partial_sets_fail(self):
        code, report = self.aggregate("empty")
        self.assertEqual(code, 1)
        self.assertEqual(len(report["missing"]), 6)
        self.add_case(replay.PILOT_CASES[0])
        code, report = self.aggregate("partial")
        self.assertEqual(code, 1)
        self.assertEqual(len(report["missing"]), 5)
        for case_id in replay.PILOT_CASES[1:]: self.add_case(case_id)
        code, report = self.aggregate("complete")
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["expected_case_stage_count"], 6)
        self.assertEqual(report["observed_case_stage_count"], 6)
        self.assertEqual(report["failures"], [])

    def test_duplicate_or_unexpected_case_never_passes_complete_denominator(self):
        for case_id in replay.PILOT_CASES: self.add_case(case_id)
        first = replay.PILOT_CASES[0]
        self.add_case(first, directory_name="duplicate")
        code, report = self.aggregate("duplicate")
        self.assertEqual(code, 1)
        self.assertEqual(report["observed_case_stage_count"], 6)
        self.assertTrue(any("duplicate" in row["error"] for row in report["failures"]))
        shutil.rmtree(self.results / "duplicate")
        write_json(self.results / "unexpected/case-summary.json", {"stage": "pilot", "case_id": "unknown", "status": "success"})
        code, report = self.aggregate("unexpected")
        self.assertEqual(code, 1)
        self.assertTrue(report["failures"])

    def test_failed_or_malformed_summary_cannot_disappear_from_failure_report(self):
        directories = [self.add_case(case_id)[0] for case_id in replay.PILOT_CASES]
        first = directories[0] / "case-summary.json"
        summary = json.loads(first.read_bytes())
        summary["status"] = "failed"
        write_json(first, summary)
        code, report = self.aggregate("failed")
        self.assertEqual(code, 1)
        self.assertEqual(report["observed_case_stage_count"], 6)
        self.assertEqual(sum(case["status"] == "failed" for case in report["cases"]), 1)
        self.assertTrue(report["failures"])
        first.write_bytes(b'{"status": "success", "status": "success"}')
        code, report = self.aggregate("malformed")
        self.assertEqual(code, 1)
        self.assertTrue(report["failures"])
        self.assertEqual(len(report["missing"]), 1)

    def test_claimed_assessment_is_recomputed_from_worker_evidence(self):
        for case_id in replay.PILOT_CASES: self.add_case(case_id)
        first = self.results / f"pilot-{replay.PILOT_CASES[0]}" / "case-summary.json"
        summary = json.loads(first.read_bytes())
        summary["assessment"]["median_saved_fraction"] = 0.99
        write_json(first, summary)
        code, report = self.aggregate("forged-performance")
        self.assertEqual(code, 1)
        self.assertTrue(any("recomputed case assessment" in row["error"] for row in report["failures"]))

    def test_all_stage_gate_requires_the_expanded_cases_too(self):
        for case_id in replay.PILOT_CASES: self.add_case(case_id)
        code, report = self.aggregate("missing-expanded", stage="all")
        self.assertEqual(code, 1)
        self.assertEqual(report["expected_case_stage_count"], 8)
        self.assertEqual({row["case_id"] for row in report["missing"]}, set(replay.EXPANDED_CASES))
        for case_id in replay.EXPANDED_CASES: self.add_case(case_id, stage="expanded")
        code, report = self.aggregate("all-complete", stage="all")
        self.assertEqual(code, 0)
        self.assertEqual(report["observed_case_stage_count"], 8)


class TestTypedScalarAdmission(unittest.TestCase):
    def test_finite_nan_infinity_signed_zero_and_missing_categories_are_explicit(self):
        cells = [float_cell(value) for value in (0.0, -0.0, 1.25, math.inf, -math.inf, math.nan)]
        cells += [
            {"type": "numpy.bool_", "value": True},
            {"type": "builtins.int", "decimal": "0"},
            {"type": "numpy.int64", "decimal": "-42"},
            {"type": "builtins.str", "value": "typed text"},
            {"type": "builtins.NoneType", "missing": "None"},
            {"type": "pandas._libs.missing.NAType", "missing": "pandas.NA"},
            {"type": "pandas._libs.tslibs.nattype.NaTType", "missing": "pandas.NaT"},
        ]
        for cell in cells:
            with self.subTest(cell=cell):
                replay.validate_scalar(cell)

    def test_malformed_or_self_inconsistent_typed_scalars_fail(self):
        malformed = [None, {}, {"type": "builtins.bool", "value": 1},
            {"type": "builtins.int", "decimal": "01"},
            {"type": "builtins.int", "decimal": "-0"},
            {"type": "builtins.int", "decimal": 12},
            {"type": "builtins.str", "value": False},
            {"type": "builtins.NoneType", "missing": "pandas.NA"},
            {"type": "pandas._libs.missing.NAType", "missing": "None"},
            {"type": "builtins.complex", "value": "1j"},
            {**float_cell(1.0), "hex": "0x1p+0"},
            {**float_cell(1.0), "binary64_be": "0" * 16},
            {**float_cell(1.0), "binary64_be": "1" * 15},
            {**float_cell(math.nan), "missing": None},
            {**float_cell(math.inf), "missing": "NaN"},
            {**float_cell(-0.0), "hex": (0.0).hex()},
            {**float_cell(1.0), "unexpected": "ignored"}]
        for cell in malformed:
            with self.subTest(cell=cell), self.assertRaises((replay.ReplayProtocolError, KeyError, TypeError, ValueError)):
                replay.validate_scalar(cell)


class TestNoMolecularImport(unittest.TestCase):
    def test_controller_imports_without_scientific_dependencies(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, "-c", "import sys; from tools import run_posebusters_replay; "
            "assert not any(name in sys.modules for name in ('torch','rdkit','posebusters','numpy','pandas'))"],
            cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
