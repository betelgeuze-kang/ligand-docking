"""Synthetic admission/worker/transition tests; no molecular packages loaded."""
from argparse import Namespace
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import trace_redocking_stage_rmsd as trace
from tools.posebusters_replay_evaluator import UPSTREAM_SOURCE_SHA256


VERSIONS = {"numpy": "1.26.4", "pandas": "2.3.3", "PyYAML": "6.0.3", "rdkit-pypi": "2022.9.5", "posebusters": "0.3.1"}
ORIGINAL_SOURCE = {"commit": trace.frozen.SOURCE_COMMIT, "tree": trace.frozen.SOURCE_TREE,
    "workflow_run_id": trace.frozen.SOURCE_RUN_ID, "workflow_run_attempt": "1",
    "entrypoint_sha256s": {"tools/run_engine_v2_public_redocking_300.py": "ad32d38b48764c167496e9abd4b2e4e3e41d41a42014a78649ef4e2c31e88d2a"}}
FAKE_TORCH = SimpleNamespace(float64="float64", tensor=lambda values, **kwargs: values)


def coordinate(x, y):
    return {"shape": [1, 3], "values_hex": [float(x).hex(), float(y).hex(), 0.0.hex()]}


def serialize(case_id, points):
    # Deliberately synthetic, but models a four-decimal serialization round trip.
    return tuple(f"{case_id}_engine_v2_rank_{rank}\n{json.dumps([[round(v, 4) for v in row] for row in values])}\n$$$$\n".encode()
                 for rank, values in enumerate(points, 1))


def descriptor(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"relative_path": relative, "sha256": trace.sha256(payload), "size_bytes": len(payload)}


def fixture(root, case_id=trace.CASE_IDS[0], changes=None):
    spec = next(s for s in trace.cohort.CASE_SPECS if s[0] == case_id)
    case = {"case_id": case_id, "receipt_sha256": "b"*64, "receipt_file_sha256": spec[5],
            "frozen_evaluator_versions": VERSIONS, "candidates_sorted": []}
    inputs = {}
    for role, suffix in trace.frozen.ROLE_SUFFIXES.items():
        payload = ("synthetic-"+role).encode()
        case[role] = descriptor(root, f"cases/{case_id}/{suffix}", payload)
        inputs[role] = payload
    rows = []
    for index in range(64):
        stages = {}
        xs = {stage: 3.0 for stage in trace.STAGES}
        xs[trace.STAGES[0]] = 4.0
        if changes:
            xs.update(changes.get(index, {}))
        torsion_selected = xs[trace.STAGES[3]] != xs[trace.STAGES[1]]
        branch = trace.STAGES[2] if torsion_selected else trace.STAGES[1]
        proposal_sha = trace.sha256(f"proposal-{index}".encode())
        for stage in trace.STAGES:
            coords = coordinate(xs[stage], index+1)
            detail = {"candidate_id": f"candidate-{index}", "proposal_index": index,
                "coordinate_unit": "angstrom", "coordinates_binary64": coords,
                "coordinate_fingerprint_sha256": trace.coordinate_identity(coords), "proposal_fingerprint_sha256": proposal_sha}
            if stage == trace.STAGES[3]:
                detail.update(torsion_selected=torsion_selected, parent_proposal_fingerprint_sha256=proposal_sha)
            stages[stage] = {"details": detail}
        rows.append({"candidate_id": f"candidate-{index}", "proposal_index": index, "score_rank": index+1,
            "score_binary64_hex": float(index).hex(), "historical_selected_rmsd_binary64_hex": float(round(xs[trace.STAGES[3]], 4)).hex(),
            "torsion_selected": torsion_selected, "selected_branch": branch, "stages": stages})
    selected_points = [[[float.fromhex(v) for v in r["stages"][trace.STAGES[3]]["details"]["coordinates_binary64"]["values_hex"]]] for r in rows]
    records = serialize(case_id, selected_points)
    for row, record in zip(rows, records):
        row["historical_selected_record_sha256"] = trace.sha256(record)
        case["candidates_sorted"].append({"proposal_index": row["proposal_index"], "rank": row["score_rank"],
            "score_binary64_hex": row["score_binary64_hex"], "expected_sdf_record_sha256": trace.sha256(record),
            "legacy_outcome": {"rmsd_binary64_hex": row["historical_selected_rmsd_binary64_hex"]}})
    case["top5"] = descriptor(root, f"cases/{case_id}/top5.sdf", b"".join(records[:5]))
    document = {"schema_id": trace.TRACE_SCHEMA, "case_id": case_id, "source_run_id": trace.frozen.SOURCE_RUN_ID,
        "source_global_index": spec[3], "frozen_case_seed": spec[4], "source": ORIGINAL_SOURCE,
        "source_parameters": {"candidate_count": 64, "output_pose_count": 5, "rmsd_threshold_angstrom": 2.0,
                              "seed_base": 2026072700, "frozen_case_seed": spec[4]},
        "receipt_sha256": case["receipt_sha256"], "receipt_file_sha256": case["receipt_file_sha256"],
        "source_evaluation_pipeline_sha256": trace.frozen.EVALUATION_PIPELINE_SHA256,
        "input_sha256s": {role: case[role]["sha256"] for role in inputs}, "candidates": rows}
    return {"case": case, "trace": document, "inputs": inputs,
            "input_ids": {"case_id": case_id, "native_sha256": case["native"]["sha256"],
                          "receptor_sha256": case["receptor"]["sha256"], "seed_sha256": case["seed"]["sha256"]}}


class FakeRuntime:
    def __init__(self, *, invalid=False, mutate=False):
        self.invalid, self.mutate = invalid, mutate
        self.calls, self.serializations, self.decodes = [], [], []
        self.runner = SimpleNamespace(_serialize_pose_records=self.serialize, _posebusters_molecules=self.decode)
        self.source_hashes, self.versions = UPSTREAM_SOURCE_SHA256, VERSIONS

    def serialize(self, seed, coordinates, *, case_id):
        self.serializations.append((str(seed), deepcopy(coordinates)))
        return serialize(case_id, coordinates)

    def decode(self, **kwargs):
        self.decodes.append(kwargs)
        records = trace.frozen.split_sdf_records(kwargs["output_payload"])
        molecules = tuple({"name": r.splitlines()[0].decode(), "coords": json.loads(r.splitlines()[1])} for r in records)
        return molecules, {"native": kwargs["native_payload"].decode()}, {"receptor": kwargs["receptor_payload"].decode()}

    def molecule_sha256(self, molecule):
        return trace.digest(molecule)

    def check_rmsd(self, *, mol_pred, mol_true, **parameters):
        assert parameters == trace.RMSD_PARAMETERS
        self.calls.append((deepcopy(mol_pred), deepcopy(mol_true), deepcopy(parameters)))
        value = float("nan") if self.invalid else abs(mol_pred["coords"][0][0])
        if self.mutate:
            mol_pred["mutated"] = True
        return {"results": {"rmsd": value}}


def measure(selected, root, runtime=None):
    runtime = FakeRuntime() if runtime is None else runtime
    with patch.dict(sys.modules, {"torch": FAKE_TORCH}):
        result = trace.measure_case(selected, root, runtime=runtime)
    return result, runtime


def process_fixture(directory):
    request = {"case_id": trace.CASE_IDS[0], "bundle_sha256": "a"*64,
        "execution_context": {"python_executable": "/original/python", "input_root": "/original/input",
            "output_root": "/original/output", "working_directory": "/original/repo", "runtime_root": "/original/runtime"}}
    request_sha = "b"*64
    streams = {}
    for name in ("stdout", "stderr"):
        data = (name+" synthetic log\n").encode()
        (directory / (name+".log")).write_bytes(data)
        streams[name] = {"path": name+".log", "bytes_seen": len(data), "bytes_retained": len(data),
            "bytes_discarded": 0, "truncated": False, "eof_observed": True, "retained_sha256": trace.sha256(data)}
    record = {"schema_id": "betelgeuze.redocking_process_execution/1.0.0", "command": trace.worker_command(request, request_sha),
        "returncode": 0, "termination": "exited", "cleanup_complete": True, "error": None, "wall_seconds": 1.0,
        "child_cpu_seconds": 0.5, "sampled_peak_process_tree_rss_bytes": 1024,
        **{k: trace.PROTOCOL[k] for k in ("wall_limit_seconds", "rss_limit_bytes", "rss_sampling_seconds")}, "streams": streams}
    record["control_sha256"] = trace.digest(record)
    return record, request, request_sha


def resign(record, key="control_sha256"):
    record[key] = trace.digest({k: v for k, v in record.items() if k != key})


class TestFrozenStageInputs(unittest.TestCase):
    def test_five_shards_preserve_29_prepared_and_three_unprepared_cases(self):
        self.assertEqual([len(s) for s in trace.SHARDS], [6, 6, 6, 6, 5])
        self.assertEqual(tuple(cid for shard in trace.SHARDS for cid in shard), trace.CASE_IDS)
        self.assertEqual(len(set(trace.CASE_IDS)), 29)
        self.assertEqual(trace.PROTOCOL["fixed_case_denominator"], 32)
        self.assertEqual(trace.PROTOCOL["expected_stage_observations"], 29*64*4)
        self.assertEqual(trace.PROTOCOL["required_selected_history_matches"], 29*64)
        self.assertEqual(len(trace.PROTOCOL["not_prepared_case_ids"]), 3)

    def test_stage_trace_binds_candidate_rank_seed_and_selected_branch(self):
        with TemporaryDirectory() as d:
            selected = fixture(Path(d))
            trace.validate_trace(selected["trace"], selected["case"])
            for change in ("seed", "parameters", "candidate", "rank", "missing_stage", "branch", "historical_receipt"):
                bad = deepcopy(selected)
                row = bad["trace"]["candidates"][0]
                if change == "seed": bad["trace"]["frozen_case_seed"] += 1
                elif change == "parameters": bad["trace"]["source_parameters"]["candidate_count"] = 128
                elif change == "candidate": row["candidate_id"] = bad["trace"]["candidates"][1]["candidate_id"]
                elif change == "rank": row["score_rank"] = 2
                elif change == "missing_stage": row["stages"].pop(trace.STAGES[1])
                elif change == "branch": row["selected_branch"] = trace.STAGES[0]
                else:
                    bad["case"]["receipt_file_sha256"] = "c"*64
                    bad["trace"]["receipt_file_sha256"] = "c"*64
                with self.subTest(change=change), self.assertRaises((trace.StageTraceError, trace.frozen.ReplayInputError)):
                    trace.validate_trace(bad["trace"], bad["case"])

    def test_coordinate_one_bit_change_invalidates_stage_fingerprint(self):
        with TemporaryDirectory() as d:
            selected = fixture(Path(d))
            coord = selected["trace"]["candidates"][0]["stages"][trace.STAGES[0]]["details"]["coordinates_binary64"]
            coord["values_hex"][0] = math.nextafter(4.0, math.inf).hex()
            with self.assertRaisesRegex(trace.StageTraceError, "coordinate"):
                trace.validate_trace(selected["trace"], selected["case"])

    def test_result_input_paths_do_not_allow_traversal(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "file").write_bytes(b"content")
            for relative in ("../file", "/file", "a/../file", "a\\file"):
                with self.subTest(relative=relative), self.assertRaises((trace.replay.ReplayProtocolError, trace.frozen.ReplayInputError)):
                    trace.relative_file(root, relative)

    def test_source_snapshot_includes_new_scientific_and_input_modules(self):
        files = trace.source_files()
        self.assertIn("tools/trace_redocking_stage_rmsd.py", files)
        self.assertIn("tools/posebusters_integration_inputs.py", files)
        self.assertIn("tools/run_engine_v2_public_redocking_300.py", files)
        self.assertIn("tools/redocking_isolation.py", files)

    def test_import_and_cli_help_do_not_import_molecular_packages(self):
        code = "import sys; from tools import trace_redocking_stage_rmsd; assert not any(n in sys.modules for n in ('torch','rdkit','posebusters','numpy'))"
        result = subprocess.run([sys.executable, "-c", code], cwd=trace.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestMolecularWorkerContract(unittest.TestCase):
    def test_selected_64_are_freshly_measured_before_other_stages(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected = fixture(root)
            result, runtime = measure(selected, root)
            trace.validate_measurement(result, selected)
            self.assertEqual(result["historical_selected_gate"]["rmsd_binary64_matches"], 64)
            self.assertEqual(result["measurement_counts"]["stage_observations"], 256)
            self.assertEqual(result["measurement_counts"]["fresh_rmsd_module_calls"], 128)
            self.assertEqual(result["measurement_counts"]["same_case_exact_coordinate_reuses"], 128)
            self.assertEqual([call[0]["coords"][0][0] for call in runtime.calls[:64]], [3.0]*64)
            self.assertEqual(len(runtime.decodes), 4)
            self.assertTrue(all(call["native_payload"] == selected["inputs"]["native"] and
                                call["receptor_payload"] == selected["inputs"]["receptor"] for call in runtime.decodes))

    def test_one_ulp_selected_rmsd_mismatch_stops_before_intermediate_stages(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected, runtime = fixture(root), FakeRuntime()
            selected["trace"]["candidates"][0]["historical_selected_rmsd_binary64_hex"] = math.nextafter(3., math.inf).hex()
            with self.assertRaisesRegex(trace.StageTraceError, "historical RMSD gate"):
                measure(selected, root, runtime)
            self.assertEqual(len(runtime.serializations), 1)
            self.assertEqual(len(runtime.calls), 64)

    def test_selected_record_hash_mismatch_stops_before_rmsd_calls(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected, runtime = fixture(root), FakeRuntime()
            selected["trace"]["candidates"][0]["historical_selected_record_sha256"] = "0"*64
            with self.assertRaisesRegex(trace.StageTraceError, "SDF record"):
                measure(selected, root, runtime)
            self.assertEqual(runtime.calls, [])

    def test_sdf_round_trip_not_raw_binary64_coordinates_is_measured(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            changes = {0: {trace.STAGES[0]: 1.9999999, trace.STAGES[1]: 2.0000001,
                           trace.STAGES[2]: 2.0000001, trace.STAGES[3]: 2.0000001}}
            selected = fixture(root, changes=changes)
            result, _ = measure(selected, root)
            trace.validate_measurement(result, selected)
            row = result["rows"][0]
            self.assertEqual(row["stages"][trace.STAGES[3]]["rmsd"]["binary64_hex"], 2.0.hex())
            # Equal rounded records are not enough to share a raw-coordinate cache entry.
            self.assertIsNone(row["stages"][trace.STAGES[0]]["reused_from"])
            self.assertTrue(row["stages"][trace.STAGES[3]]["rmsd"]["near_native"])

    def test_coordinate_cache_is_private_to_each_case_invocation(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            runtime = FakeRuntime()
            first = fixture(root, trace.CASE_IDS[0])
            a, _ = measure(first, root, runtime)
            before = len(runtime.calls)
            second = fixture(root, trace.CASE_IDS[1])
            b, _ = measure(second, root, runtime)
            self.assertEqual(len(runtime.calls)-before, 128)
            self.assertEqual(a["measurement_counts"], b["measurement_counts"])
            self.assertTrue(all(s["reused_from"] is None or s["reused_from"]["case_id"] == second["case"]["case_id"]
                                for row in b["rows"] for s in row["stages"].values()))

    def test_nan_and_mutated_molecules_fail_without_inventing_rmsd(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected = fixture(root)
            for runtime in (FakeRuntime(invalid=True), FakeRuntime(mutate=True)):
                with self.subTest(runtime=runtime), self.assertRaises(trace.StageTraceError):
                    measure(selected, root, runtime)

    def test_output_reuse_must_reference_prior_same_case_exact_coordinates(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected = fixture(root)
            result, _ = measure(selected, root)
            for change in ("case", "coordinate", "rmsd", "counts"):
                bad = deepcopy(result)
                value = bad["rows"][0]["stages"][trace.STAGES[1]]
                if change == "case": value["reused_from"]["case_id"] = trace.CASE_IDS[1]
                elif change == "coordinate": value["raw_coordinates_sha256"] = "0"*64
                elif change == "rmsd": value["rmsd"] = trace.rmsd_record(1.0)
                else: bad["measurement_counts"]["fresh_rmsd_module_calls"] -= 1
                with self.subTest(change=change), self.assertRaises(trace.StageTraceError):
                    trace.validate_measurement(bad, selected)


class TestStageInterpretation(unittest.TestCase):
    def test_optimized_near_discarded_for_v6_is_separate_from_generation_loss(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected = fixture(root, changes={
                0: {trace.STAGES[2]: 1.0},
                1: {trace.STAGES[0]: 1.0},
                2: {stage: 1.0 for stage in trace.STAGES},
            })
            result, _ = measure(selected, root)
            summary = trace.stage_summary(result["rows"])
            self.assertEqual(summary["selection_drop_proposal_indices"], [0])
            self.assertEqual(summary["transitions"][trace.STAGES[0]+"->"+trace.STAGES[3]]["near_lost"], [1])
            self.assertEqual(summary["transitions"][trace.STAGES[1]+"->"+trace.STAGES[2]]["near_appeared"], [0])
            self.assertEqual(summary["near_native_count"][trace.STAGES[3]], 1)
            self.assertFalse(summary["case_had_prior_near_but_no_selected_near"])
            self.assertFalse(summary["causal_failure_stage_assigned"])
            self.assertFalse(summary["intermediate_physical_validity_measured"])

    def test_case_has_prior_near_and_no_selected_near_is_explicit(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected = fixture(root, changes={0: {trace.STAGES[2]: 1.0}})
            result, _ = measure(selected, root)
            summary = trace.stage_summary(result["rows"])
            self.assertTrue(summary["case_had_prior_near_but_no_selected_near"])
            self.assertEqual(summary["near_native_count"][trace.STAGES[0]], 0)
            self.assertEqual(summary["near_native_count"][trace.STAGES[2]], 1)
            self.assertEqual(summary["near_native_count"][trace.STAGES[3]], 0)

    def test_rmsd_threshold_and_bits_are_independently_validated(self):
        self.assertTrue(trace.rmsd_record(2.0)["near_native"])
        self.assertFalse(trace.rmsd_record(math.nextafter(2.0, math.inf))["near_native"])
        for change in ("bits", "threshold", "scalar_type"):
            record = trace.rmsd_record(2.0)
            if change == "bits": record["binary64_be"] = struct.pack(">d", math.nextafter(2.0, math.inf)).hex()
            elif change == "threshold": record["near_native"] = False
            else: record["value"] = 2
            with self.subTest(change=change), self.assertRaises(trace.StageTraceError):
                trace.validate_rmsd_record(record)
        for value in (None, float("nan"), float("inf"), -1., True, "1.0"):
            with self.subTest(value=value), self.assertRaises(trace.StageTraceError):
                trace.rmsd_record(value)

    def test_missing_case_cannot_shrink_the_scientific_denominator(self):
        with self.assertRaisesRegex(trace.StageTraceError, "all 29"):
            trace.combine_stage_summaries({})
        with TemporaryDirectory() as d:
            root = Path(d)
            result, _ = measure(fixture(root), root)
            cases = {cid: deepcopy(result) for cid in trace.CASE_IDS}
            combined = trace.combine_stage_summaries(cases)
            self.assertTrue(all(s["fixed_case_denominator"] == 32 and s["evaluated_candidate_denominator"] == 1856
                                for s in combined["stages"].values()))
            cases.pop(trace.CASE_IDS[-1])
            with self.assertRaisesRegex(trace.StageTraceError, "all 29"):
                trace.combine_stage_summaries(cases)


class TestExecutionEvidence(unittest.TestCase):
    def test_case_result_binds_science_to_request_source_runtime_and_environment(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            selected = fixture(root)
            measured, _ = measure(selected, root)
            request = {"case_id": selected["case"]["case_id"], "bundle_sha256": "a"*64,
                "protocol_sha256": trace.digest(trace.PROTOCOL), "source": {"commit": "fixture"},
                "environment_before": {"sha256": "b"*64}, "environment_content_identity_sha256": "c"*64,
                "runtime_identity": {"version": "fixture"}}
            request_sha = "d"*64
            result = {**measured, "schema_id": trace.SCHEMA, "kind": "case_result", "status": "success",
                "case_id": request["case_id"], "bundle_sha256": request["bundle_sha256"],
                "protocol_sha256": request["protocol_sha256"], "source": request["source"],
                "environment_before_sha256": "b"*64, "environment_content_identity_sha256": "c"*64,
                "runtime_identity": request["runtime_identity"], "request_sha256": request_sha,
                "input_files_unchanged": True, "stage_summary": trace.stage_summary(measured["rows"])}
            resign(result, "receipt_sha256")
            trace.validate_result(result, selected=selected, request=request, request_sha256=request_sha)
            changes = {"request_sha256": "e"*64, "source": {"commit": "changed"},
                "runtime_identity": {"version": "changed"}, "environment_before_sha256": "e"*64,
                "input_files_unchanged": False, "intermediate_physical_validity_measured": True}
            for field, value in changes.items():
                bad = deepcopy(result)
                bad[field] = value
                resign(bad, "receipt_sha256")
                with self.subTest(field=field), self.assertRaises(trace.StageTraceError):
                    trace.validate_result(bad, selected=selected, request=request, request_sha256=request_sha)
            bad = deepcopy(result)
            bad["stage_summary"]["near_native_count"][trace.STAGES[0]] += 1
            resign(bad, "receipt_sha256")
            with self.assertRaisesRegex(trace.StageTraceError, "stage summary"):
                trace.validate_result(bad, selected=selected, request=request, request_sha256=request_sha)

    def test_valid_process_receipt_and_log_bytes_are_bound(self):
        with TemporaryDirectory() as d:
            directory = Path(d)
            record, request, request_sha = process_fixture(directory)
            trace.validate_execution(record, request, request_sha, directory)
            self.assertIn("tools.trace_redocking_stage_rmsd", record["command"])
            self.assertIn("--request-sha256", record["command"])

    def test_rehashed_timeout_cleanup_rss_argv_and_limit_tampering_still_fail(self):
        with TemporaryDirectory() as d:
            directory = Path(d)
            original, request, request_sha = process_fixture(directory)
            changes = {"returncode": 1, "termination": "wall_timeout", "cleanup_complete": False,
                "sampled_peak_process_tree_rss_bytes": trace.PROTOCOL["rss_limit_bytes"]+1,
                "wall_limit_seconds": 601, "rss_sampling_seconds": 1.0,
                "command": original["command"]+["--unexpected"], "wall_seconds": float("nan")}
            for field, value in changes.items():
                record = deepcopy(original)
                record[field] = value
                with self.subTest(field=field), self.assertRaises((trace.StageTraceError, ValueError)):
                    resign(record)
                    trace.validate_execution(record, request, request_sha, directory)

    def test_changed_log_bytes_fail_even_when_process_receipt_is_unchanged(self):
        with TemporaryDirectory() as d:
            directory = Path(d)
            record, request, request_sha = process_fixture(directory)
            (directory / "stderr.log").write_bytes(b"changed")
            with self.assertRaisesRegex(trace.StageTraceError, "stream"):
                trace.validate_execution(record, request, request_sha, directory)

    def test_original_worker_paths_are_validated_without_opening_remote_paths(self):
        with TemporaryDirectory() as d:
            record, request, request_sha = process_fixture(Path(d))
            self.assertEqual(trace.worker_command(request, request_sha), record["command"])
            for path in ("relative", "/original/../outside", "//server/path", "/original/\npath"):
                bad = deepcopy(request)
                bad["execution_context"]["input_root"] = path
                with self.subTest(path=path), self.assertRaises(trace.StageTraceError):
                    trace.worker_command(bad, request_sha)

    def test_empty_results_make_explicit_failed_aggregate_without_inference(self):
        with TemporaryDirectory() as d:
            directory = Path(d)
            inputs, results = directory / "inputs", directory / "results"
            inputs.mkdir(); results.mkdir()
            source = {"commit": "fixture", "protocol_sha256": trace.digest(trace.PROTOCOL)}
            bundle = {"source": source}
            manifest = {"not_prepared": [{"case_id": s[0], "status": "not_prepared", "candidate_count": 0}
                                         for s in trace.cohort.NOT_PREPARED_SPECS]}
            output = directory / "report.json"
            args = Namespace(input_root=inputs, bundle_sha256="a"*64, results_root=results, output=output)
            with patch.object(trace, "load_bundle", return_value=(bundle, manifest)), \
                 patch.object(trace, "source_identity", return_value=source), redirect_stdout(StringIO()):
                status = trace.aggregate(args)
            self.assertEqual(status, 1)
            report = trace.read_json(output)
            self.assertEqual(report["fixed_case_denominator"], 32)
            self.assertEqual(report["missing_shards"], [0, 1, 2, 3, 4])
            self.assertEqual(report["cases_without_validated_measurement"], list(trace.CASE_IDS))
            self.assertEqual(len(report["not_prepared_cases"]), 3)
            self.assertEqual(report["validated_selected_history_matches"], 0)
            self.assertFalse(report["intermediate_inference_allowed"])
            self.assertIsNone(report["stage_summary"])

    def test_duplicate_recursive_shard_is_failed_and_never_interpreted(self):
        with TemporaryDirectory() as d:
            directory = Path(d)
            inputs, results = directory / "inputs", directory / "results"
            inputs.mkdir(); results.mkdir()
            source = {"commit": "fixture", "protocol_sha256": trace.digest(trace.PROTOCOL)}
            for child in ("artifact-a", "nested/artifact-b"):
                path = results / child / "shard-summary.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"shard_id": 0}))
            args = Namespace(input_root=inputs, bundle_sha256="a"*64, results_root=results, output=directory / "report.json")
            with patch.object(trace, "load_bundle", return_value=({"source": source}, {"not_prepared": []})), \
                 patch.object(trace, "source_identity", return_value=source), redirect_stdout(StringIO()):
                self.assertEqual(trace.aggregate(args), 1)
            report = trace.read_json(args.output)
            self.assertTrue(any("duplicate" in row["error"] for row in report["failures"]))
            self.assertFalse(report["intermediate_inference_allowed"])


if __name__ == "__main__":
    unittest.main()
