"""Molecule-free admission tests with real journals, hashes and P1 caches.

Synthetic evidence exercises the controller's trust boundaries. These tests
make no claim about molecular equivalence; frozen runtime/cloud cases do that.
"""
from argparse import Namespace
from contextlib import redirect_stdout
from copy import deepcopy
from functools import lru_cache
import hashlib
import io
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import run_posebusters_integration as p
from tools.redocking_development_p1 import DevelopmentObservation
from tools.posebusters_subset import FROZEN_RDKIT_VERSION, IMPLEMENTATION_ID


def sha(value):
    return hashlib.sha256(value).hexdigest()


def raw_file(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return p.descriptor(root, relative)


def replace_document(root, relative, value):
    return raw_file(root, relative, p.canonical(value) + b"\n")


def resign(value, key):
    value.pop(key, None)
    value[key] = p.digest(value)
    return value


def make_environment():
    sources = [{"path": name, "size": 1, "sha256": sha(name.encode()), "mode": 0o644}
               for name in sorted(p.REQUIRED_SOURCE_FILES)]
    installed = {"path": "posebusters/module.py", "status": "present", "size": 1, "sha256": "c" * 64,
                 "mode": 0o644, "recorded": True, "content_included": True, "exclusion_reason": None}
    payload = p.digest([{key: installed[key] for key in ("path", "size", "sha256", "mode")}])
    raw = p.digest([p.evidence._file_projection(installed)])
    environment = {"schema_id": p.evidence.ENVIRONMENT_SCHEMA, "policy": p.evidence.POLICY,
        "support_module_sha256": "d" * 64, "versions": {"posebusters": "0.3.1"}, "source_files": sources,
        "wheel_manifest_sha256": p.common.WHEEL_MANIFEST, "wheel_set_sha256": p.common.WHEEL_SET,
        "runtime": {"implementation": "cpython", "version": "3.10.22 fixture", "cache_tag": "cpython-310",
            "platform": "linux", "machine": "x86_64", "byteorder": "little",
            "executable": {"size": 1, "sha256": "e" * 64, "mode": 0o755}, "libpython": [], "libpython_detection": "proc_self_maps"},
        "distributions": {"posebusters": {"files": [installed], "raw_payload_sha256": raw, "active_payload_sha256": payload}},
        "raw_payload_sha256": p.digest({"posebusters": raw})}
    environment["content_identity_sha256"] = p.evidence._digest(p.evidence._environment_projection(environment))
    return resign(environment, "report_sha256")


def make_inputs(root):
    root.mkdir(parents=True)
    environment = make_environment()
    cases, reconstructions, stage_details = [], [], {}
    versions = {"posebusters": "0.3.1", "rdkit-pypi": "2022.9.5", "PyYAML": "6.0.3", "numpy": "1.26.4", "pandas": "2.3.3"}
    for case_id, artifact, case_root, index, seed, receipt in p.inputs.CASE_SPECS:
        records = [f"{case_id}_engine_v2_rank_{rank}\nsynthetic {rank}\n$$$$\n".encode() for rank in range(1, 65)]
        hashes = [sha(record) for record in records]
        outcomes = [{"rank": rank, "proposal_index": rank - 1, "record_sha256": hashes[rank - 1],
            "rmsd_angstrom": rank / 10.0, "rmsd_binary64_hex": (rank / 10.0).hex(),
            "geometric_valid": True, "chemical_valid": True, "failed_check_ids": []} for rank in range(1, 65)]
        case = {"case_id": case_id, "source_global_index": index, "frozen_case_seed": seed,
            "receipt_file_sha256": receipt, "candidate_count": 64, "frozen_evaluator_versions": versions,
            "legacy_top5_outcomes": outcomes[:5], "candidates_sorted": []}
        for role in ("native", "seed", "reference", "receptor"):
            case[role] = raw_file(root, f"cases/{case_id}/{role}.dat", (case_id + role).encode())
        case["top5"] = {**raw_file(root, f"cases/{case_id}/top5.sdf", b"".join(records[:5])), "record_count": 5, "record_sha256s": hashes[:5]}
        reconstructions.append({**raw_file(root, f"cases/{case_id}/candidates64.sdf", b"".join(records)),
            "case_id": case_id, "record_count": 64, "record_sha256s": hashes,
            "template_role": "seed", "all_original_record_sha256s_match": True})
        candidates, details = [], []
        for proposal in range(64):
            states = {}
            for stage, offset in (("proposal_generated", 0), ("post_v6", 1), ("post_v7_optimization", 2)):
                coordinates = {"shape": [1, 3], "values_hex": [float(proposal + offset).hex(), (0.0).hex(), (-0.0).hex()]}
                state = {"schema_id": p.lineage.LINEAGE_SCHEMA, "proposal_index": proposal,
                    "candidate_id": f"candidate-{proposal}", "proposal_fingerprint_sha256": sha(f"original-{proposal}".encode()),
                    "coordinate_fingerprint_sha256": p.lineage.coordinate_payload_fingerprint(coordinates),
                    "coordinates_binary64": coordinates, "coordinate_unit": "angstrom"}
                states[stage] = state
                details.append((stage, state))
            chosen = deepcopy(states["post_v6"])
            chosen.update(proposal_fingerprint_sha256=sha(f"selected-{proposal}".encode()),
                parent_proposal_fingerprint_sha256=states["proposal_generated"]["proposal_fingerprint_sha256"],
                refinement_receipt_sha256=sha(f"refine-{proposal}".encode()), torsion_selected=False,
                final_penalty_binary64_hex=(5.0).hex())
            details.append(("refinement_selected", chosen))
            outcome = outcomes[proposal]
            candidate = {"proposal_index": proposal, "status": "success", "score": proposal + 0.5,
                "coordinate_fingerprint_sha256": chosen["coordinate_fingerprint_sha256"],
                "proposal_fingerprint_sha256": chosen["proposal_fingerprint_sha256"],
                "refinement_receipt_sha256": chosen["refinement_receipt_sha256"],
                "refinement_final_penalty_binary64_hex": chosen["final_penalty_binary64_hex"],
                "pose_artifact_sha256": hashes[proposal], "rmsd_angstrom": outcome["rmsd_angstrom"],
                "geometric_valid": True, "chemical_valid": True, "score_term_binary64_hex": {"total_score": (proposal + 0.5).hex()}}
            candidates.append(candidate)
            coordinate_file = replace_document(root, f"cases/{case_id}/coordinates/rank-{proposal+1:03d}.json", chosen["coordinates_binary64"])
            case["candidates_sorted"].append({"rank": proposal + 1, "proposal_index": proposal,
                "expected_sdf_record_sha256": hashes[proposal], "legacy_outcome": outcome,
                "coordinates_relative_path": coordinate_file["relative_path"], "coordinate_sha256": coordinate_file["sha256"],
                "coordinate_fingerprint_sha256": chosen["coordinate_fingerprint_sha256"], "coordinate_count": 1})
            if proposal < 5:
                final = deepcopy(chosen)
                final.update(rank_1based=proposal + 1, evaluated_pose_record_sha256=hashes[proposal])
                details.append(("final_ranked", final))
        row = {"case_id": case_id, "engine_id": "engine_v2", "status": "success", "failure_code": "",
            "runtime_seconds": 1.0, "execution_command": ["old-command"], "execution_policy": ["old-policy"],
            "engine_v2_diagnostics": {"candidates": candidates, "diagnostic_evaluation_seconds": 2.0,
                "diagnostic_evaluation_excluded_from_runtime": True, "ligand_atom_count": 1},
            "pose_artifact_sha256s": hashes[:5], "rmsd_angstroms": [outcome["rmsd_angstrom"] for outcome in outcomes[:5]],
            "geometric_valid": [True] * 5, "chemical_valid": [True] * 5,
            **{role + "_artifact_sha256": case[role]["sha256"] for role in ("native", "seed", "reference", "receptor")}}
        case["source_row"] = replace_document(root, f"cases/{case_id}/source-row.json", row)
        cases.append(case)
        stage_details[case_id] = details
    manifest = {"schema_id": p.inputs.SCHEMA_ID, "source_run_id": p.inputs.frozen.SOURCE_RUN_ID,
        "source_execution_commit": p.inputs.frozen.SOURCE_COMMIT, "source_execution_tree": p.inputs.frozen.SOURCE_TREE,
        "source_evaluation_pipeline_sha256": p.inputs.frozen.EVALUATION_PIPELINE_SHA256,
        "source_environment_content_identity_sha256": p.inputs.frozen.ENVIRONMENT_CONTENT_IDENTITY_SHA256,
        "fixed_case_denominator": 32, "fixed_case_order": p.inputs.FIXED_CASE_ORDER,
        "successful_case_count": 29, "not_prepared_case_count": 3, "molecular_evaluation_performed": False,
        "candidate_generation_performed": False, "exact_saved_top5_record_count": 145, "expected_candidate_record_count": 1856,
        "cases": cases, "not_prepared": [{"case_id": row[0], "source_global_index": row[3], "receipt_file_sha256": row[5],
            "status": "not_prepared", "candidate_count": 0, "preparation_failure_code": "unsupported_large_ring_system"} for row in p.inputs.NOT_PREPARED_SPECS]}
    manifest_file = replace_document(root, "manifest.json", manifest)
    bundle = {"schema_id": p.SCHEMA, "protocol": deepcopy(p.PROTOCOL),
        "source": {"commit": "a" * 40, "tree": "b" * 40, "protocol_sha256": p.digest(p.PROTOCOL)},
        "source_snapshot": p.source_projection(environment), "source_snapshot_sha256": p.digest(p.source_projection(environment)),
        "environment_content_identity_sha256": environment["content_identity_sha256"],
        "preparation_environment": replace_document(root, "environment-preparation.json", environment),
        "manifest_sha256": manifest_file["sha256"], "reconstructions": reconstructions,
        "evaluator_identities": {mode: sha(mode.encode()) for mode in p.MODES}, "evaluator_versions": versions,
        "upstream_source_sha256": deepcopy(p.adapter.UPSTREAM_SOURCE_SHA256)}
    bundle_file = replace_document(root, "bundle.json", bundle)
    return bundle, manifest, bundle_file["sha256"], environment, stage_details


def make_report(selected, bundle, mode):
    expected = selected["expected"]
    count = len(expected)
    full = {"index_policy": "validated_original_mol_identity_replaced_by_record_sha256_and_ordinal",
        "index_names": ["file", "molecule"], "columns": ["rmsd", *[f"check-{i}" for i in range(125)]],
        "dtypes": [{"name": "float64", "type": "numpy.dtypes.Float64DType"}] + [{"name": "bool", "type": "numpy.dtypes.BoolDType"}] * 125,
        "rows": []}
    for index, row in enumerate(expected):
        value = float.fromhex(row["rmsd_binary64_hex"])
        full["rows"].append({"record_ordinal": index + 1, "record_sha256": row["record_sha256"],
            "molecule_name": f"{selected['case']['case_id']}_engine_v2_rank_{index + 1}",
            "cells": [{"type": "builtins.float", "binary64_be": struct.pack(">d", value).hex(), "hex": value.hex(), "missing": None}]
                     + [{"type": "builtins.bool", "value": True} for _ in range(125)]})
    fingerprints = {"predicted": [sha(f"molecule-{i}".encode()) for i in range(count)], "native": "a" * 64, "receptor": "b" * 64}
    legacy = {**p.common.legacy_projection(expected), "rmsds": [float.fromhex(row["rmsd_binary64_hex"]) for row in expected]}
    return {"schema_id": "betelgeuze.posebusters_runner_report/1.0.0", "case_id": selected["case"]["case_id"],
        "mode": mode, "evaluator_identity": bundle["evaluator_identities"][mode], "evaluation_call": 1, "record_count": count,
        "input_ids": deepcopy(selected["input_ids"]), "fullReport": full, "legacy_outcomes": legacy,
        "input_immutability": {"verified": True, "before": deepcopy(fingerprints), "after": deepcopy(fingerprints), "pickle_policy": "AllProps|CoordsAsDouble"},
        "evaluator_versions": deepcopy(bundle["evaluator_versions"]), "upstream_source_sha256": deepcopy(bundle["upstream_source_sha256"])}


def contexts(selected, bundle, mode):
    count = len(selected["expected"])
    energy_before = {"hits": 0, "misses": 0, "maxsize": None, "current_size": 0}
    energy_after = {"hits": count - 1, "misses": 1, "maxsize": None, "current_size": 1}
    before = {"schema_id": "betelgeuze.posebusters_evaluator_context/1.0.0", "case_id": selected["case"]["case_id"],
        "mode": mode, "evaluator_identity": bundle["evaluator_identities"][mode], "healthy": True,
        "closed": False, "bust_calls": 0, "record_evaluations": 0, "full_reports_observed": 0,
        "input_immutability_verified_batches": 0, "input_ids": None, "receptor_preparation": None, "subset_filter": None}
    after = deepcopy(before)
    after.update(closed=True, bust_calls=1, record_evaluations=count, full_reports_observed=1, input_immutability_verified_batches=1,
        input_ids={key: selected["input_ids"][key] for key in ("native_sha256", "receptor_sha256")},
        energy_cache={"first_observed": energy_before, "last_observed": energy_after,
                      "hits_added": count - 1, "misses_added": 1, "cleared_by_context": False},
        timings={"collect_metrics": True, "posebusters_ns": 1000 - 100 * p.MODES.index(mode),
                 "input_identity_check_ns": 20, "report_observer_ns": 30, "volume_substages": []})
    if mode != "reference":
        after["receptor_preparation"] = {"hits": 4 * count - 4, "misses": 4, "entries": 4, "max_entries": 4}
    if mode == "prepared_subset":
        after["subset_filter"] = {"implementation_id": IMPLEMENTATION_ID, "rdkit_version": FROZEN_RDKIT_VERSION,
            "calls": count, "identity_calls": 0, "fast_path_calls": count, "fallback_calls": 0,
            "fast_path_errors": 0, "fallback_errors": 0, "source_atoms_fast_path": count * 10,
            "retained_atoms_fast_path": count * 4, "removed_atoms_fast_path": count * 6, "fallback_reasons": {}}
    return before, after, energy_before, energy_after


def make_worker(directory, *, selected, bundle, bundle_sha, environment, summary, slot, mode, stage_details):
    directory.mkdir(parents=True)
    command = p.worker_command(summary, slot=slot, mode=mode)
    identity = p.journal_identity(source=bundle["source"], bundle_sha256=bundle_sha, case_id=summary["case_id"],
        stage=summary["stage"], mode=mode, evaluator_identity=bundle["evaluator_identities"][mode],
        seed=selected["case"]["frozen_case_seed"], actual_argv=command)
    journal = p.isolation.AtomicJournal(directory / "journal", identity)
    observer = DevelopmentObservation(summary["case_id"], event_sink=journal.emit, evaluator_identity=bundle["evaluator_identities"][mode])
    report = make_report(selected, bundle, mode)
    files = {}
    for key, relative in (("environment_before", "environment-before.json"), ("environment_after", "environment-after.json")):
        files[key] = p.write_document(directory, relative, environment)
    if summary["stage"] == "pipeline":
        for stage, details in stage_details[summary["case_id"]]:
            observer.snapshot(stage, **details)

    def evaluate():
        observer.decode_inputs(native_payload=selected["native"], receptor_payload=selected["receptor"],
                               decode=lambda prepared: (None, "native", "receptor"), clone=lambda value: value)
        files["full_report"] = p.write_document(directory, "full-report.json", report)
        journal.emit({"stage": "raw_full_report", "phase": "snapshot", "details": {"file": files["full_report"]}})
        data = report["legacy_outcomes"]
        return tuple(tuple(data[key]) for key in ("rmsds", "geometric_valid", "chemical_valid", "failed_check_ids"))

    returned = []
    for records in (selected["records"], selected["records"][:5]):
        with journal.stage("runner_posebusters_outcomes"):
            returned.append(p._legacy_return(observer.evaluate(records, native_payload=selected["native"],
                receptor_payload=selected["receptor"], evaluate=evaluate)))
    before, after, energy_before, energy_after = contexts(selected, bundle, mode)
    files["context_before"] = p.write_document(directory, "evaluator-before.json", before)
    files["context_after"] = p.write_document(directory, "evaluator-after.json", after)
    files["observation_summary"] = p.write_document(directory, "observation-summary.json", observer.summary())
    if summary["stage"] == "pipeline":
        row = deepcopy(selected["source_row"])
        row.update(runtime_seconds=3.0, execution_command=["new-path"], execution_policy=["new-policy"])
        row["engine_v2_diagnostics"]["diagnostic_evaluation_seconds"] = 4.0
        files["scientific_row"] = p.write_document(directory, "scientific-row.json", row)
        files["top5"] = raw_file(directory, "poses/" + summary["case_id"] + ".sdf", b"".join(selected["records"][:5]))
        files["profile_observation"] = p.write_document(directory, "profile-observation.json",
            {"case_id": summary["case_id"], "ligand_artifact_sha256": selected["case"]["native"]["sha256"],
             "heavy_atom_count": 1, "rotor_count": 0, "ring_count": 0})
    journal.emit({"stage": "worker_complete", "phase": "snapshot", "details": {"status": "success"}})
    events, journal_receipt = p.verify_journal(directory / "journal", expected_identity=identity)
    result = {"schema_id": p.SCHEMA, "status": "success", "stage": summary["stage"], "case_id": summary["case_id"],
        "mode": mode, "source": deepcopy(bundle["source"]), "source_snapshot_sha256": bundle["source_snapshot_sha256"],
        "bundle_sha256": bundle_sha, "protocol_sha256": p.digest(p.PROTOCOL), "evaluator_identity": bundle["evaluator_identities"][mode],
        "actual_argv": command, "working_directory": summary["execution_context"]["working_directory"],
        "pid": 100 + slot, "parent_pid": summary["controller_pid"], "node": summary["node"],
        "runner_call_ns": 2000 - 100 * slot, "files": files, "energy_before": energy_before, "energy_after": energy_after,
        "journal": journal_receipt, "phase_durations": p.phase_durations(events), "final_context": after, "final_observation": observer.summary()}
    if summary["stage"] == "replay":
        result["returned_outcomes"] = returned
    result = p.signed(result, "result_sha256")
    p.write_document(directory, "result.json", result)
    streams = {}
    for name in ("stdout", "stderr"):
        payload = (name + " fixture\n").encode()
        raw_file(directory, name + ".log", payload)
        streams[name] = {"path": name + ".log", "bytes_seen": len(payload), "bytes_retained": len(payload),
                         "bytes_discarded": 0, "eof_observed": True, "truncated": False, "retained_sha256": sha(payload)}
    execution = p.signed({"schema_id": "betelgeuze.redocking_process_execution/1.0.0", "command": command,
        "returncode": 0, "termination": "exited", "cleanup_complete": True, "error": None,
        "wall_limit_seconds": p.PROTOCOL["wall_limit_seconds"][summary["stage"]],
        "rss_limit_bytes": p.PROTOCOL["rss_limit_bytes"], "rss_sampling_seconds": p.PROTOCOL["rss_sampling_seconds"],
        "wall_seconds": 1.0 + slot / 10, "child_cpu_seconds": 0.5, "sampled_peak_process_tree_rss_bytes": 4096, "streams": streams}, "control_sha256")
    p.write_document(directory, "process-execution.json", execution)
    return result, execution


def make_case(directory, *, input_root, bundle, manifest, bundle_sha, environment, stage_details, case_id, stage="replay"):
    directory.mkdir(parents=True)
    selected = p.selected_inputs(input_root, bundle, manifest, case_id, stage)
    summary = {"schema_id": p.SCHEMA, "status": "success", "case_id": case_id, "stage": stage,
        "source": deepcopy(bundle["source"]), "bundle_sha256": bundle_sha, "protocol_sha256": p.digest(p.PROTOCOL),
        "controller_pid": 42, "node": {"hostname": "fixture-node"}, "observations": [], "cleanup_complete": True,
        "execution_context": {"python_executable": "/original/venv/bin/python", "input_root": "/original/inputs",
            "runtime_root": "/original/runtime", "output_root": f"/original/results/{stage}/{case_id}", "working_directory": "/original/repo"}}
    for slot, mode in enumerate(p.mode_order(case_id, stage)):
        relative = f"worker-{slot}-{mode}"
        make_worker(directory / relative, selected=selected, bundle=bundle, bundle_sha=bundle_sha, environment=environment,
                    summary=summary, slot=slot, mode=mode, stage_details=stage_details)
        summary["observations"].append({"slot": slot, "mode": mode, "worker_directory": relative, "process_gate_passed": True,
            "execution": p.descriptor(directory, relative + "/process-execution.json"), "result": p.descriptor(directory, relative + "/result.json")})
    for key, relative in (("environment_before", "environment-before.json"), ("environment_after", "environment-after.json")):
        summary[key] = p.write_document(directory, relative, environment)
    summary["assessment"] = p.assess_case(directory, summary, selected=selected, bundle=bundle, bundle_sha256=bundle_sha)
    p.write_document(directory, "case-summary.json", p.signed(summary, "summary_sha256"))
    return summary, selected


class IntegrationAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_tmp = tempfile.TemporaryDirectory()
        cls.input_root = Path(cls.fixture_tmp.name) / "inputs"
        cls.bundle, cls.manifest, cls.bundle_sha, cls.environment, cls.stage_details = make_inputs(cls.input_root)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def case(self, case_id=p.PILOT_CASES[0], stage="replay", relative="case"):
        directory = self.root / relative
        summary, selected = make_case(directory, input_root=self.input_root, bundle=self.bundle, manifest=self.manifest,
            bundle_sha=self.bundle_sha, environment=self.environment, stage_details=self.stage_details, case_id=case_id, stage=stage)
        return directory, summary, selected

    def check(self, directory, summary, selected):
        return p.assess_case(directory, summary, selected=selected, bundle=self.bundle, bundle_sha256=self.bundle_sha)

    def aggregate(self, scope, results, output):
        args = Namespace(input_root=self.input_root, bundle_sha256=self.bundle_sha, runtime_root=self.root / "runtime",
                         scope=scope, results_root=results, output=output)
        with patch.object(p, "source_identity", return_value=self.bundle["source"]), \
             patch.object(p, "capture_environment", return_value=self.environment), redirect_stdout(io.StringIO()):
            return p.aggregate(args)

    def test_fixed_cohort_shards_order_and_distinct_resource_contracts(self):
        self.assertEqual([len(shard) for shard in p.SHARDS], [6, 6, 6, 6, 3])
        self.assertEqual(set(sum(p.SHARDS, ())) | set(p.PILOT_CASES), set(p.inputs.CASE_IDS))
        self.assertEqual(len(sum(p.SHARDS, ())), 27)
        self.assertEqual(len(p.expected_case_stages("all")), 31)
        self.assertEqual(len(p.expected_case_stages("pilot")), 2)
        for spec in p.inputs.CASE_SPECS:
            offset = spec[3] % 3
            self.assertEqual(p.mode_order(spec[0], "replay"), p.MODES[offset:] + p.MODES[:offset])
        self.assertEqual(p.mode_order("6T88_MWQ", "pipeline"), p.MODES)
        self.assertEqual(p.mode_order("6YSP_PAL", "pipeline"), tuple(reversed(p.MODES)))
        self.assertEqual(p.ORIGINAL_RESOURCE_CONTRACT["engine_v2_wall_limit_seconds"], 900)
        self.assertEqual(p.PROTOCOL["wall_limit_seconds"]["pipeline"], 1800)
        with self.assertRaises(ValueError):
            p.mode_order(p.inputs.NOT_PREPARED_SPECS[0][0], "replay")
        with self.assertRaises(ValueError):
            p.mode_order(p.inputs.CASE_IDS[0], "pipeline")

    def test_bundle_round_trip_has_fixed32_and_all_reconstruction_records(self):
        bundle, manifest = p.load_bundle(self.input_root, self.bundle_sha)
        self.assertEqual(len(bundle["reconstructions"]), 29)
        self.assertEqual(sum(row["record_count"] for row in bundle["reconstructions"]), 1856)
        self.assertEqual(manifest["fixed_case_denominator"], 32)
        self.assertEqual(len(manifest["not_prepared"]), 3)
        with self.assertRaises(ValueError):
            p.load_bundle(self.input_root, "0" * 64)

    def test_resigned_bundle_rejects_mode_source_protocol_and_cohort_tampering(self):
        mutations = {
            "duplicate_mode_identity": lambda b, m: b["evaluator_identities"].update(prepared_subset=b["evaluator_identities"]["reference"]),
            "upstream_source": lambda b, m: b["upstream_source_sha256"].update(**{"posebusters.py": "0" * 64}),
            "missing_source": lambda b, m: b["source_snapshot"].pop(),
            "source_hash": lambda b, m: b["source_snapshot"][0].update(sha256="0" * 64),
            "protocol_wall": lambda b, m: b["protocol"]["wall_limit_seconds"].update(pipeline=900),
            "bool_denominator": lambda b, m: m.update(fixed_case_denominator=True),
            "seed": lambda b, m: m["cases"][0].update(frozen_case_seed=2026072700),
            "duplicate_case": lambda b, m: m["cases"].__setitem__(1, deepcopy(m["cases"][0])),
            "removed_unprepared": lambda b, m: m["not_prepared"].pop(),
            "changed_receipt": lambda b, m: m["cases"][0].update(receipt_file_sha256="0" * 64),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                root = self.root / name
                root.mkdir()
                bundle, manifest = deepcopy(self.bundle), deepcopy(self.manifest)
                mutate(bundle, manifest)
                bundle["manifest_sha256"] = replace_document(root, "manifest.json", manifest)["sha256"]
                bundle["source_snapshot_sha256"] = p.digest(bundle["source_snapshot"])
                replace_document(root, "environment-preparation.json", self.environment)
                bundle_sha = replace_document(root, "bundle.json", bundle)["sha256"]
                with self.assertRaises((ValueError, p.evidence.EvidenceError)):
                    p.load_bundle(root, bundle_sha)

    def test_replay_three_modes_admit_real_journal_and_cache_receipts(self):
        directory, summary, selected = self.case()
        assessed = self.check(directory, summary, selected)
        self.assertTrue(assessed["exact_equivalence_passed"])
        self.assertEqual(len(assessed["pairs"]), 3)
        self.assertEqual(assessed["full_report_rows"], 5)
        self.assertEqual(assessed["full_report_columns"], 126)
        for mode in p.MODES:
            self.assertEqual(assessed["mode_observations"][mode]["observation"]["evaluation_cache"],
                             {"evaluation_calls": 1, "reused_records": 5, "cached_records": 5})
            self.assertFalse(assessed["mode_observations"][mode]["context"]["energy_cache"]["cleared_by_context"])

    def test_pipeline_three_modes_require_full64_lineage_and_original_scientific_row(self):
        directory, summary, selected = self.case(stage="pipeline")
        assessment = self.check(directory, summary, selected)
        self.assertEqual(assessment["full_report_rows"], 64)
        self.assertEqual(assessment["scientific_projection_sha256"], p.digest(p.scientific_projection(selected["source_row"])))
        for mode in p.MODES:
            self.assertEqual(assessment["mode_observations"][mode]["lineage"]["coordinate_snapshot_count"], 261)
            self.assertEqual(assessment["mode_observations"][mode]["observation"]["evaluation_cache"]["cached_records"], 64)

    def test_science_projection_excludes_only_four_observational_fields(self):
        selected = p.selected_inputs(self.input_root, self.bundle, self.manifest, p.PILOT_CASES[0], "pipeline")
        row = selected["source_row"]
        changed = deepcopy(row)
        changed.update(runtime_seconds=19.0, execution_command=["different"], execution_policy=["different"])
        changed["engine_v2_diagnostics"]["diagnostic_evaluation_seconds"] = 99.0
        p.equal(p.scientific_projection(row), p.scientific_projection(changed), "allowed observations")
        for key, value in (("score", 123.0), ("geometric_valid", 1), ("refinement_receipt_sha256", "f" * 64),
                           ("coordinate_fingerprint_sha256", "f" * 64), ("rmsd_angstrom", 0.0)):
            altered = deepcopy(row)
            altered["engine_v2_diagnostics"]["candidates"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.equal(p.scientific_projection(row), p.scientific_projection(altered), "science must remain exact")
        for left, right in ((False, 0), (True, 1), (1.0, 1), (-0.0, 0.0)):
            with self.assertRaises(ValueError):
                p.equal(left, right, "typed equality")

    def test_raw_report_types_bits_modes_and_denominators_are_not_coerced(self):
        selected = p.selected_inputs(self.input_root, self.bundle, self.manifest, p.PILOT_CASES[0], "replay")
        base = make_report(selected, self.bundle, "reference")
        changes = [lambda r: r.update(record_count=True), lambda r: r.update(mode="prepared_subset"),
            lambda r: r["fullReport"]["rows"].pop(), lambda r: r["fullReport"]["columns"].pop(),
            lambda r: r["fullReport"]["rows"][0]["cells"][1].update(value=1),
            lambda r: r["fullReport"]["rows"][0]["cells"][0].update(binary64_be="0" * 16),
            lambda r: r["legacy_outcomes"]["geometric_valid"].__setitem__(0, 1),
            lambda r: r["legacy_outcomes"]["rmsds"].__setitem__(0, 1),
            lambda r: r["input_immutability"]["after"].update(native="f" * 64)]
        for index, change in enumerate(changes):
            report = deepcopy(base)
            change(report)
            with self.subTest(index=index), self.assertRaises(ValueError):
                p.validate_report(report, selected=selected, bundle=self.bundle, mode="reference")

    def test_context_rejects_clear_warm_cache_open_lifetime_and_changed_reuse_counts(self):
        selected = p.selected_inputs(self.input_root, self.bundle, self.manifest, p.PILOT_CASES[0], "replay")
        original = contexts(selected, self.bundle, "prepared_receptor")
        mutations = [lambda b, a, e, x: a.update(closed=False), lambda b, a, e, x: a.update(bust_calls=2),
            lambda b, a, e, x: a["energy_cache"].update(cleared_by_context=True),
            lambda b, a, e, x: e.update(hits=1), lambda b, a, e, x: x.update(maxsize=256),
            lambda b, a, e, x: a["receptor_preparation"].update(entries=5),
            lambda b, a, e, x: a.update(input_immutability_verified_batches=True)]
        for index, change in enumerate(mutations):
            before, after, entry, exit_state = deepcopy(original)
            change(before, after, entry, exit_state)
            with self.subTest(index=index), self.assertRaises(ValueError):
                p.validate_context(before, after, selected=selected, bundle=self.bundle, mode="prepared_receptor",
                                   energy_before=entry, energy_after=exit_state)

    def test_supervisor_receipt_rejects_resigned_argv_limits_cleanup_returncode_and_logs(self):
        directory, summary, selected = self.case()
        item = summary["observations"][0]
        worker_root = directory / item["worker_directory"]
        original = p.read_document(directory, item["execution"])
        changes = [lambda r: r["command"].__setitem__(3, "other-worker"), lambda r: r.update(wall_limit_seconds=901),
            lambda r: r.update(rss_limit_bytes=True), lambda r: r.update(rss_sampling_seconds=1),
            lambda r: r.update(cleanup_complete=False), lambda r: r.update(returncode=False),
            lambda r: r.update(error={"message": "failed"}), lambda r: r["streams"]["stderr"].update(retained_sha256="f" * 64),
            lambda r: r["streams"]["stdout"].update(bytes_retained=p.PROTOCOL["log_limit_bytes"] + 1),
            lambda r: r["streams"]["stderr"].update(eof_observed=False)]
        for index, change in enumerate(changes):
            receipt = deepcopy(original)
            change(receipt)
            resign(receipt, "control_sha256")
            with self.subTest(index=index), self.assertRaises(ValueError):
                p.validate_execution(receipt, directory=worker_root, summary=summary, slot=0, mode=item["mode"])
        corrupted = deepcopy(original)
        corrupted["wall_seconds"] += 1
        with self.assertRaises(ValueError):
            p.validate_execution(corrupted, directory=worker_root, summary=summary, slot=0, mode=item["mode"])

    def test_original_execution_paths_are_relocatable_but_not_traversable(self):
        directory, summary, selected = self.case()
        relocated = self.root / "relocated"
        shutil.copytree(directory, relocated)
        self.check(relocated, summary, selected)
        for value in ("/original/../inputs", "relative", "/original//inputs", "/original/inputs\n", "/original/inputs\\other"):
            modified = deepcopy(summary)
            modified["execution_context"]["input_root"] = value
            with self.subTest(path=value), self.assertRaises(ValueError):
                p.worker_command(modified, slot=0, mode=modified["observations"][0]["mode"])

    def test_journal_verifies_every_event_not_only_last_checkpoint(self):
        directory, summary, selected = self.case()
        journal = directory / summary["observations"][0]["worker_directory"] / "journal"
        path = journal / "event-000001.json"
        first = p.read_json(path)
        original = path.read_bytes()
        first["event"]["details"]["complete_hit"] = True
        resign(first, "event_sha256")
        replace_document(journal, path.name, first)
        with self.assertRaises(ValueError):
            self.check(directory, summary, selected)
        path.write_bytes(original)
        (journal / "event-000002.json").unlink()
        with self.assertRaises(ValueError):
            self.check(directory, summary, selected)

    def test_worker_result_hash_and_resigned_source_mode_cache_tampering_fail(self):
        directory, summary, selected = self.case()
        item = summary["observations"][0]
        worker_root = directory / item["worker_directory"]
        result = p.read_document(directory, item["result"])
        mutations = [lambda r: r["source"].update(commit="c" * 40), lambda r: r.update(mode="prepared_subset"),
            lambda r: r.update(source_snapshot_sha256="f" * 64), lambda r: r.update(actual_argv=["forged"]),
            lambda r: r["final_observation"]["evaluation_cache"].update(reused_records=0), lambda r: r.update(pid=True)]
        for index, change in enumerate(mutations):
            altered = deepcopy(result)
            change(altered)
            resign(altered, "result_sha256")
            with self.subTest(index=index), self.assertRaises(ValueError):
                p.validate_worker(worker_root, altered, selected=selected, bundle=self.bundle, bundle_sha256=self.bundle_sha,
                    stage="replay", mode=item["mode"], actual_argv=p.worker_command(summary, slot=0, mode=item["mode"]))

    def test_environment_source_and_installed_bytes_remain_bound_after_resigning(self):
        for mutation in (lambda e: e["source_files"][0].update(sha256="f" * 64),
                         lambda e: e["distributions"]["posebusters"]["files"][0].update(sha256="f" * 64)):
            environment = deepcopy(self.environment)
            mutation(environment)
            environment["content_identity_sha256"] = p.evidence._digest(p.evidence._environment_projection(environment))
            resign(environment, "report_sha256")
            with self.assertRaises((ValueError, p.evidence.EvidenceError)):
                p.validate_environment(environment, bundle=self.bundle)

    def test_recursive_pilot_aggregate_rechecks_raw_artifacts_and_preserves_fixed32(self):
        for case_id in p.PILOT_CASES:
            self.case(case_id=case_id, relative="results/downloaded/pilot/replay/" + case_id)
        output = self.root / "pilot.json"
        self.assertEqual(self.aggregate("pilot", self.root / "results", output), 0)
        report = p.read_json(output)
        self.assertEqual(report["expected_worker_count"], 6)
        self.assertEqual(report["fixed_case_denominator"], 32)
        self.assertEqual(len(report["not_prepared"]), 3)
        p.verify_signed(report, "aggregate_sha256", "aggregate")
        self.assertEqual(self.aggregate("all", self.root / "results", self.root / "all-missing.json"), 1)
        all_report = p.read_json(self.root / "all-missing.json")
        self.assertEqual(all_report["expected_worker_count"], 93)
        self.assertEqual(len(all_report["missing"]), 29)

    def test_duplicate_missing_and_corrupted_raw_results_fail_aggregate(self):
        directory, summary, selected = self.case(relative="results/replay/" + p.PILOT_CASES[0])
        self.assertEqual(self.aggregate("pilot", self.root / "results", self.root / "missing.json"), 1)
        self.case(case_id=p.PILOT_CASES[1], relative="results/replay/" + p.PILOT_CASES[1])
        copied = self.root / "results" / "duplicate"
        shutil.copytree(directory, copied)
        self.assertEqual(self.aggregate("pilot", self.root / "results", self.root / "duplicate.json"), 1)
        self.assertIn("duplicate", p.read_json(self.root / "duplicate.json")["failures"][0]["error"])
        shutil.rmtree(copied)
        raw = directory / summary["observations"][0]["worker_directory"] / "full-report.json"
        raw.write_bytes(raw.read_bytes() + b" ")
        self.assertEqual(self.aggregate("pilot", self.root / "results", self.root / "corrupt.json"), 1)
        self.assertTrue(raw.exists())

    def test_stage_failure_is_preserved_without_a_success_or_missing_denominator(self):
        directory, summary, selected = self.case(relative="results/replay/" + p.PILOT_CASES[0])
        failed = p.read_json(directory / "case-summary.json")
        failed.update(status="failed", error="resource failure")
        replace_document(directory, "case-summary.json", resign(failed, "summary_sha256"))
        self.assertEqual(self.aggregate("pilot", self.root / "results", self.root / "failed.json"), 1)
        report = p.read_json(self.root / "failed.json")
        self.assertEqual(report["observed_case_stage_count"], 1)
        self.assertEqual(len(report["missing"]), 1)
        self.assertEqual(report["cases"][0]["status"], "failed")

    def test_controller_import_does_not_import_molecular_packages(self):
        subprocess.run([sys.executable, "-c", "import sys; import tools.run_posebusters_integration; "
                        "assert not {'torch','rdkit','posebusters','numpy'} & set(sys.modules)"], check=True)

    def test_failed_workers_keep_all_three_sequential_argv_and_fixed_limits(self):
        calls = []

        def failed(command, directory, limits, **kwargs):
            calls.append((command, limits, kwargs))
            directory.mkdir()
            receipt = p.signed({"schema_id": "betelgeuze.redocking_process_execution/1.0.0",
                "command": command, "returncode": 1, "termination": "exited", "cleanup_complete": True,
                "error": None, "streams": {}}, "control_sha256")
            p.write_document(directory, "process-execution.json", receipt)
            return receipt

        args = Namespace(input_root=self.input_root, bundle_sha256=self.bundle_sha, runtime_root=self.root / "runtime",
                         stage="replay", case_id=p.PILOT_CASES[1], output_root=self.root / "failed-case")
        with patch.object(p, "source_identity", return_value=self.bundle["source"]), \
             patch.object(p, "capture_environment", return_value=self.environment), \
             patch.object(p.isolation, "supervise", side_effect=failed), redirect_stdout(io.StringIO()):
            self.assertEqual(p.run_case(args), 1)
        self.assertEqual(len(calls), 3)
        self.assertEqual([command[command.index("--mode") + 1] for command, limits, kwargs in calls],
                         list(p.mode_order(args.case_id, args.stage)))
        for command, limits, kwargs in calls:
            self.assertEqual(limits.wall_seconds, 900)
            self.assertEqual(limits.rss_bytes, 6 * 1024**3)
            self.assertEqual(limits.poll_seconds, 0.25)
            self.assertEqual(limits.log_bytes, 8 * 1024**2)
            self.assertEqual(kwargs["cwd"], p.ROOT)
        summary = p.read_json(args.output_root / "case-summary.json")
        self.assertEqual(len(summary["observations"]), 3)
        self.assertEqual(summary["status"], "failed")
        self.assertTrue(summary["cleanup_complete"])
        for item in summary["observations"]:
            self.assertIsNone(item["result"])
            p.read_document(args.output_root, item["execution"])

    def test_cleanup_failure_stops_remaining_modes_and_all_later_shard_cases(self):
        def no_cleanup(command, directory, limits, **kwargs):
            directory.mkdir()
            receipt = p.signed({"schema_id": "betelgeuze.redocking_process_execution/1.0.0", "command": command,
                "returncode": -9, "termination": "cleanup_failed", "cleanup_complete": False,
                "error": {"message": "fixture cleanup failure"}, "streams": {}}, "control_sha256")
            p.write_document(directory, "process-execution.json", receipt)
            raise p.isolation.CleanupError("fixture cleanup failure", receipt)

        args = Namespace(input_root=self.input_root, bundle_sha256=self.bundle_sha, runtime_root=self.root / "runtime",
                         shard_id=0, output_root=self.root / "stopped-shard")
        with patch.object(p, "source_identity", return_value=self.bundle["source"]), \
             patch.object(p, "capture_environment", return_value=self.environment), \
             patch.object(p.isolation, "supervise", side_effect=no_cleanup) as supervisor, redirect_stdout(io.StringIO()):
            self.assertEqual(p.run_shard(args), 1)
            self.assertEqual(supervisor.call_count, 1)
        shard = p.read_json(args.output_root / "shard-summary.json")
        self.assertTrue(shard["stopped_after_cleanup_failure"])
        self.assertEqual(len(shard["cases"]), 1)
        case = p.read_document(args.output_root, shard["cases"][0]["summary"])
        self.assertFalse(case["cleanup_complete"])
        self.assertEqual(len(case["observations"]), 1)


class FrozenEnergyCacheAdmission(unittest.TestCase):
    @staticmethod
    def states():
        # PoseBusters 0.3.1 uses this exact unbounded-cache configuration.
        @lru_cache(maxsize=None)
        def energy(identity):
            return 1.0

        before = p.adapter._cache_info_document(energy.cache_info())
        for _ in range(5):
            energy("same-native")
        after = p.adapter._cache_info_document(energy.cache_info())
        context = {"first_observed": before, "last_observed": after,
                   "hits_added": 4, "misses_added": 1, "cleared_by_context": False}
        return before, after, context

    def test_actual_unbounded_lru_cache_info_is_admitted(self):
        before, after, context = self.states()
        self.assertIsNone(before["maxsize"])
        self.assertIsNone(after["maxsize"])
        p.validate_energy_cache(before, after, context, 5)

    def test_bounded_or_malformed_capacity_cannot_replace_frozen_policy(self):
        for capacity in (0, 128, True, "None"):
            with self.subTest(capacity=capacity):
                before, after, context = self.states()
                before["maxsize"] = after["maxsize"] = capacity
                with self.assertRaises(ValueError):
                    p.validate_energy_cache(before, after, context, 5)


if __name__ == "__main__":
    unittest.main()
