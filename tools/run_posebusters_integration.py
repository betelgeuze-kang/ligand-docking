"""Exact opt-in evaluator experiments on the fixed development32 cohort.

29 saved Top5 replays and two fresh Engine V2 searches use three sequential
fresh processes per case. Original inputs, seeds and scientific rows stay fixed.
The experiment's resource limits do not change the original run's contract.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any

from tools import posebusters_integration_inputs as inputs
from tools import posebusters_replay_evaluator as adapter
from tools import redocking_evidence_support as evidence
from tools import redocking_isolation as isolation
from tools import redocking_lineage_validation as lineage
from tools import run_posebusters_replay as common

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "betelgeuze.posebusters_integration/1.0.0"
MODULE = "tools.run_posebusters_integration"
MODES = ("reference", "prepared_receptor", "prepared_subset")
PILOT_CASES = inputs.PILOT_CASES
REMAINING_CASES = tuple(case for case in inputs.CASE_IDS if case not in PILOT_CASES)
SHARDS = tuple(REMAINING_CASES[index:index + 6] for index in range(0, len(REMAINING_CASES), 6))
SCIENCE_EXCLUSIONS = ("/runtime_seconds", "/engine_v2_diagnostics/diagnostic_evaluation_seconds",
                      "/execution_command", "/execution_policy")
REQUIRED_SOURCE_FILES = (
    "tools/run_posebusters_integration.py", "tools/posebusters_integration_inputs.py",
    "tools/posebusters_evaluator_context.py", "tools/posebusters_subset.py",
    "tools/run_posebusters_replay.py", "tools/posebusters_replay_inputs.py",
    "tools/posebusters_replay_evaluator.py", "tools/redocking_development_p1.py",
    "tools/redocking_isolation.py", "tools/redocking_evidence_support.py",
    "tools/redocking_lineage_validation.py", "tools/run_engine_v2_public_redocking_300.py",
    "tools/run_redocking_isolated_development.py", "tools/analyze_redocking_failures.py",
    "tests/unit/test_posebusters_integration_runner.py", "tests/unit/test_posebusters_evaluator_context.py",
    "tests/unit/test_posebusters_integration_inputs.py", "tests/unit/test_posebusters_subset.py",
    "tests/unit/test_redocking_failure_diagnosis.py", ".github/workflows/posebusters_integration.yml",
)
ORIGINAL_RESOURCE_CONTRACT = {
    "source_run_id": inputs.frozen.SOURCE_RUN_ID, "source_commit": inputs.frozen.SOURCE_COMMIT,
    "source_tree": inputs.frozen.SOURCE_TREE, "manifest_path": "config/redocking_p0_p1_20261104.json",
    "manifest_sha256": "d1cade89b3e524e4e02a67ec07dc660c6ba5416919f11a1f33d7b4bb24910455",
    "engine_v2_wall_limit_seconds": 900, "rss_limit_bytes": 6 * 1024**3, "rss_sampling_seconds": 0.25,
    "receipt_file_sha256s": {row[0]: row[5] for row in (*inputs.CASE_SPECS, *inputs.NOT_PREPARED_SPECS)},
    "contract_unchanged": True,
}
PROTOCOL = {
    "schema_id": SCHEMA, "source_run_id": inputs.frozen.SOURCE_RUN_ID, "fixed_case_denominator": 32,
    "successful_replay_cases": list(inputs.CASE_IDS), "not_prepared_cases": [row[0] for row in inputs.NOT_PREPARED_SPECS],
    "pilot_replay_cases": list(PILOT_CASES), "pipeline_cases": list(PILOT_CASES),
    "replay_shards": [list(shard) for shard in SHARDS],
    "replay_order": "rotate [reference,prepared_receptor,prepared_subset] by source_global_index modulo 3",
    "pipeline_orders": {PILOT_CASES[0]: list(MODES), PILOT_CASES[1]: list(reversed(MODES))},
    "pilot_gate": "aggregate --scope pilot must pass before workflow schedules replay shards and fresh pipelines",
    "modes": list(MODES), "record_counts": {"replay": 5, "pipeline": 64},
    "expected_case_stage_count": 31, "expected_worker_count": 93, "full_report_column_count": 126,
    "same_case_modes_sequential_on_one_node": True, "fresh_process_per_mode": True,
    "energy_lru_cleared": False, "energy_lru_entry_must_be_empty": True,
    "outcome_cache_policy": "one evaluation batch followed by five unchanged P1 cached outcomes",
    "wall_limit_seconds": {"replay": 900, "pipeline": 1800}, "rss_limit_bytes": 6 * 1024**3,
    "rss_sampling_seconds": 0.25, "log_limit_bytes": 8 * 1024**2,
    "journal_limit_bytes": 64 * 1024**2, "journal_limit_events": 10000, "descendant_cleanup_required": True,
    "science_projection_exclusions": list(SCIENCE_EXCLUSIONS),
    "equivalence": "ordered fullReport cells, scalar types, binary64 bits, missing values, dtypes and columns; historical scientific row and exact pose bytes",
    "historical_raw_report_available": False, "numerical_tolerance": None,
    "performance_pairs": [[MODES[0], MODES[1]], [MODES[0], MODES[2]], [MODES[1], MODES[2]]],
    "performance_timers": ["posebusters_ns", "runner_call_ns", "supervised_worker_wall_seconds"],
    "profile_arm": False, "repetitions_per_case_mode": 1,
    "performance_inference": "one observation per mode; order/node/cache noise is not estimated; no confidence interval or general speedup claim is supported",
    "public_default_changed": False, "held_out_or_primary_claim_eligible": False,
    "original_resource_contract": ORIGINAL_RESOURCE_CONTRACT,
}
require, equal, canonical, digest = common.require, common.equal, common.canonical, common.digest
read_json, relative_file, bound_file = common.read_json, common.relative_file, common.bound_file
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _sha(value: Any, label: str) -> str:
    require(type(value) is str and _SHA256.fullmatch(value) is not None, "invalid SHA256: " + label)
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, "invalid integer: " + label)
    return value


def _finite(value: Any, label: str, *, positive: bool = False) -> float:
    require(type(value) in (int, float) and math.isfinite(value) and
            (value > 0 if positive else value >= 0), "invalid duration/value: " + label)
    return value


def descriptor(root: Path, relative: str) -> dict:
    path = relative_file(root, relative)
    return {"relative_path": relative, "size_bytes": path.stat().st_size, "sha256": isolation.digest_file(path)}


def write_document(root: Path, relative: str, value: Any) -> dict:
    isolation.atomic_json(root / relative, value, replace=False)
    return descriptor(root, relative)


def read_document(root: Path, item: dict) -> Any:
    return inputs.frozen._json(bound_file(root, item), item["relative_path"])


def signed(value: dict, key: str) -> dict:
    require(key not in value, "self hash already present")
    return {**value, key: digest(value)}


def verify_signed(value: dict, key: str, label: str) -> None:
    require(type(value) is dict, label + " is not an object")
    _sha(value.get(key), label)
    equal(value[key], digest({name: item for name, item in value.items() if name != key}), label + " self hash")


def source_files() -> dict[str, Path]:
    files = common.source_files()
    files.update({name: ROOT / name for name in REQUIRED_SOURCE_FILES})
    output = subprocess.check_output(["git", "ls-files", "-z", "--", "tools", "tests/unit", ".github/workflows"],
                                     cwd=ROOT, timeout=30)
    tracked = {name.decode("utf-8") for name in output.split(b"\0") if name}
    require(set(REQUIRED_SOURCE_FILES) <= tracked, "integration source is not fully tracked")
    files.update({name: ROOT / name for name in tracked if Path(name).suffix in {".py", ".yml", ".yaml"}})
    return files


def source_identity() -> dict:
    original = common.source_identity()
    return {"commit": original["commit"], "tree": original["tree"], "protocol_sha256": digest(PROTOCOL)}


def source_projection(environment: dict) -> list[dict]:
    return [{key: row[key] for key in ("path", "size", "sha256", "mode")} for row in environment["source_files"]]


def validate_source_snapshot(snapshot: list[dict]) -> None:
    require(type(snapshot) is list and snapshot, "missing observed source inventory")
    names = []
    for row in snapshot:
        require(type(row) is dict and set(row) == {"path", "size", "sha256", "mode"}, "source inventory fields differ")
        inputs.frozen._safe_member_name(row["path"])
        _sha(row["sha256"], "source payload")
        _integer(row["size"], "source file size")
        require(type(row["mode"]) is int and 0 <= row["mode"] <= 0o7777, "invalid source file mode")
        names.append(row["path"])
    equal(names, sorted(set(names)), "source inventory order/duplicates")
    require(set(REQUIRED_SOURCE_FILES) <= set(names), "source inventory omits integration code")


def capture_environment(runtime_root: Path) -> dict:
    wheels = read_json(relative_file(runtime_root, "evaluator/wheelhouse-manifest.json"))
    equal(wheels["manifest_sha256"], common.WHEEL_MANIFEST, "frozen wheel manifest")
    equal(wheels["wheel_set_sha256"], common.WHEEL_SET, "frozen wheel set")
    reference_path = relative_file(runtime_root, "reference-environment.json")
    equal(isolation.digest_file(reference_path), common.REFERENCE_ENVIRONMENT_FILE, "frozen environment file")
    reference = read_json(reference_path)
    evidence._validate_environment(reference)
    snapshot = evidence.snapshot_environment(wheels["distributions"], source_files=source_files(), wheelhouse_manifest=wheels)
    equal(snapshot["versions"], reference["versions"], "frozen installed versions")
    equal({name: row["active_payload_sha256"] for name, row in snapshot["distributions"].items()},
          {name: row["active_payload_sha256"] for name, row in reference["distributions"].items()}, "frozen installed active bytes")
    require(snapshot["runtime"]["version"].split()[0] == "3.10.22", "frozen Python 3.10.22 is required")
    return snapshot


def validate_environment(environment: dict, *, bundle: dict) -> None:
    evidence._validate_environment(environment)
    equal(source_projection(environment), bundle["source_snapshot"], "observed source bytes")
    equal(environment["wheel_manifest_sha256"], common.WHEEL_MANIFEST, "environment wheel manifest")
    equal(environment["wheel_set_sha256"], common.WHEEL_SET, "environment wheel set")
    require(environment["runtime"]["version"].split()[0] == "3.10.22", "worker Python version differs")
    equal(environment["content_identity_sha256"], bundle["environment_content_identity_sha256"], "prepared/worker environment identity")


def prepare(artifact_root: Path, output_root: Path, runtime_root: Path) -> dict:
    source, environment = source_identity(), capture_environment(runtime_root)
    manifest = inputs.prepare_cases(artifact_root, output_root)
    import torch
    from tools import run_engine_v2_public_redocking_300 as runner

    reconstructions = []
    for case in manifest["cases"]:
        coordinates = []
        for item in case["candidates_sorted"]:
            path = relative_file(output_root, item["coordinates_relative_path"])
            equal(isolation.digest_file(path), item["coordinate_sha256"], "saved coordinate bytes")
            document = read_json(path)
            equal(lineage.coordinate_payload_fingerprint(document), item["coordinate_fingerprint_sha256"], "saved coordinate fingerprint")
            equal(document["shape"], [item["coordinate_count"], 3], "saved coordinate shape")
            values = [float.fromhex(value) for value in document["values_hex"]]
            coordinates.append(torch.tensor(values, dtype=torch.float64, device="cpu").reshape(document["shape"]))
        bound_file(output_root, case["seed"])
        records = runner._serialize_pose_records(relative_file(output_root, case["seed"]["relative_path"]), coordinates, case_id=case["case_id"])
        expected = [item["expected_sdf_record_sha256"] for item in case["candidates_sorted"]]
        equal([hashlib.sha256(record).hexdigest() for record in records], expected, "all reconstructed candidate records: " + case["case_id"])
        require(len(records) == 64 and b"".join(records[:5]) == bound_file(output_root, case["top5"]), "original Top5 bytes changed during reconstruction")
        relative = f"cases/{case['case_id']}/candidates64.sdf"
        with (output_root / relative).open("xb") as target:
            target.write(b"".join(records))
        reconstructions.append({**descriptor(output_root, relative), "case_id": case["case_id"], "record_count": 64,
            "record_sha256s": expected, "template_role": "seed", "all_original_record_sha256s_match": True})
    runtime = adapter._load_runtime()
    snapshot = source_projection(environment)
    validate_source_snapshot(snapshot)
    bundle = {"schema_id": SCHEMA, "protocol": PROTOCOL, "source": source,
        "source_snapshot": snapshot, "source_snapshot_sha256": digest(snapshot),
        "environment_content_identity_sha256": environment["content_identity_sha256"],
        "preparation_environment": write_document(output_root, "environment-preparation.json", environment),
        "manifest_sha256": isolation.digest_file(output_root / "manifest.json"),
        "evaluator_identities": {mode: runner._evaluation_pipeline_sha256(ROOT, evaluator_mode=mode) for mode in MODES},
        "evaluator_versions": dict(runtime.versions), "upstream_source_sha256": dict(runtime.source_hashes),
        "reconstructions": reconstructions}
    equal(source_identity(), source, "source changed during preparation")
    evidence.require_matching_environment(environment, capture_environment(runtime_root))
    write_document(output_root, "bundle.json", bundle)
    bundle_sha = isolation.digest_file(output_root / "bundle.json")
    load_bundle(output_root, bundle_sha)
    return {"bundle_sha256": bundle_sha, "fixed_case_denominator": 32, "successful_case_count": 29,
        "not_prepared_case_count": 3, "saved_top5_record_count": 145, "reconstructed_record_count": 1856,
        "source": source, "protocol_sha256": digest(PROTOCOL)}


def load_bundle(root: Path, bundle_sha256: str) -> tuple[dict, dict]:
    _sha(bundle_sha256, "input bundle")
    bundle_path = relative_file(root, "bundle.json")
    equal(isolation.digest_file(bundle_path), bundle_sha256, "input bundle bytes")
    bundle = read_json(bundle_path)
    equal(bundle["schema_id"], SCHEMA, "bundle schema")
    equal(bundle["protocol"], PROTOCOL, "integration protocol")
    source = bundle["source"]
    require(type(source) is dict and set(source) == {"commit", "tree", "protocol_sha256"}, "invalid source identity")
    for name in ("commit", "tree"):
        require(type(source[name]) is str and re.fullmatch(r"[0-9a-f]{40}", source[name]) is not None, "invalid Git source " + name)
    equal(source["protocol_sha256"], digest(PROTOCOL), "source protocol identity")
    validate_source_snapshot(bundle["source_snapshot"])
    equal(bundle["source_snapshot_sha256"], digest(bundle["source_snapshot"]), "source inventory hash")
    ids = bundle["evaluator_identities"]
    require(type(ids) is dict and set(ids) == set(MODES), "evaluator mode identities missing")
    for mode in MODES:
        _sha(ids[mode], "evaluator identity " + mode)
    require(len(set(ids.values())) == 3, "mode identities must be distinct")
    equal(bundle["upstream_source_sha256"], adapter.UPSTREAM_SOURCE_SHA256, "frozen evaluator source hashes")
    validate_environment(read_document(root, bundle["preparation_environment"]), bundle=bundle)
    manifest_path = relative_file(root, "manifest.json")
    equal(isolation.digest_file(manifest_path), bundle["manifest_sha256"], "prepared manifest bytes")
    manifest = read_json(manifest_path)
    expected = {"schema_id": inputs.SCHEMA_ID, "source_run_id": inputs.frozen.SOURCE_RUN_ID,
        "source_execution_commit": inputs.frozen.SOURCE_COMMIT, "source_execution_tree": inputs.frozen.SOURCE_TREE,
        "source_evaluation_pipeline_sha256": inputs.frozen.EVALUATION_PIPELINE_SHA256,
        "source_environment_content_identity_sha256": inputs.frozen.ENVIRONMENT_CONTENT_IDENTITY_SHA256,
        "fixed_case_denominator": 32, "fixed_case_order": inputs.FIXED_CASE_ORDER,
        "successful_case_count": 29, "not_prepared_case_count": 3,
        "molecular_evaluation_performed": False, "candidate_generation_performed": False,
        "exact_saved_top5_record_count": 145, "expected_candidate_record_count": 1856}
    equal({name: manifest[name] for name in expected}, expected, "original fixed32 manifest contract")
    equal([case["case_id"] for case in manifest["cases"]], list(inputs.CASE_IDS), "successful cohort order")
    equal([row["case_id"] for row in bundle["reconstructions"]], list(inputs.CASE_IDS), "reconstruction cohort order")
    for case, spec, reconstruction in zip(manifest["cases"], inputs.CASE_SPECS, bundle["reconstructions"], strict=True):
        equal({name: case[name] for name in ("source_global_index", "frozen_case_seed", "receipt_file_sha256", "candidate_count")},
              {"source_global_index": spec[3], "frozen_case_seed": spec[4], "receipt_file_sha256": spec[5], "candidate_count": 64},
              "original case index/seed/receipt")
        equal(reconstruction["record_count"], 64, "candidate reconstruction denominator")
        require(reconstruction["template_role"] == "seed" and reconstruction["all_original_record_sha256s_match"] is True, "candidate reconstruction was not exact")
        equal(case["frozen_evaluator_versions"], bundle["evaluator_versions"], "original evaluator versions")
    equal([row["case_id"] for row in manifest["not_prepared"]], [row[0] for row in inputs.NOT_PREPARED_SPECS], "not-prepared cohort order")
    for case, spec in zip(manifest["not_prepared"], inputs.NOT_PREPARED_SPECS, strict=True):
        equal({name: case[name] for name in ("source_global_index", "receipt_file_sha256", "status", "candidate_count", "preparation_failure_code")},
              {"source_global_index": spec[3], "receipt_file_sha256": spec[5], "status": "not_prepared", "candidate_count": 0,
               "preparation_failure_code": "unsupported_large_ring_system"}, "not-prepared exclusion contract")
    return bundle, manifest


def mode_order(case_id: str, stage: str) -> tuple[str, ...]:
    require(stage in ("replay", "pipeline"), "unknown experiment stage")
    require(case_id in inputs.CASE_IDS, "case outside successful development cohort")
    if stage == "pipeline":
        require(case_id in PILOT_CASES, "pipeline case outside fixed expansion")
        return tuple(PROTOCOL["pipeline_orders"][case_id])
    index = next(row[3] for row in inputs.CASE_SPECS if row[0] == case_id) % 3
    return MODES[index:] + MODES[:index]


def selected_inputs(root: Path, bundle: dict, manifest: dict, case_id: str, stage: str) -> dict:
    mode_order(case_id, stage)
    case = next(row for row in manifest["cases"] if row["case_id"] == case_id)
    candidates = case["candidates_sorted"]
    require(type(candidates) is list and len(candidates) == 64, "saved candidate denominator differs")
    equal([row["rank"] for row in candidates], list(range(1, 65)), "saved candidate ranks")
    require(all(type(row["proposal_index"]) is int for row in candidates) and
            sorted(row["proposal_index"] for row in candidates) == list(range(64)), "saved candidate indices differ")
    item = case["top5"] if stage == "replay" else next(row for row in bundle["reconstructions"] if row["case_id"] == case_id)
    records = tuple(inputs.frozen.split_sdf_records(bound_file(root, item)))
    count = PROTOCOL["record_counts"][stage]
    equal(item["record_count"], count, "selected descriptor denominator")
    require(len(records) == count, "selected SDF denominator differs")
    expected = case["legacy_top5_outcomes"] if stage == "replay" else [row["legacy_outcome"] for row in candidates]
    hashes = [hashlib.sha256(record).hexdigest() for record in records]
    equal(hashes, item["record_sha256s"], "selected record bytes/order")
    equal(hashes, [row["record_sha256"] for row in expected], "historical legacy record binding")
    equal(hashes, [row["expected_sdf_record_sha256"] for row in candidates[:count]], "candidate record binding")
    require(b"".join(records[:5]) == bound_file(root, case["top5"]), "selected Top5 differs from original bytes")
    payloads = {role: bound_file(root, case[role]) for role in ("receptor", "reference", "native", "seed")}
    paths = {role: relative_file(root, case[role]["relative_path"]) for role in payloads}
    require(len({path.parent for path in paths.values()}) == 1, "pinned input directory differs by role")
    paths["directory"] = paths["native"].parent
    source_row = read_document(root, case["source_row"])
    require(source_row["case_id"] == case_id and source_row["engine_id"] == "engine_v2" and
            source_row["status"] == "success", "original scientific row differs")
    for role in payloads:
        equal(source_row[role + "_artifact_sha256"], case[role]["sha256"], "scientific row input " + role)
    return {"case": case, "records": records, "expected": expected, "source_row": source_row,
        "paths": paths, "root": root, "native": payloads["native"], "receptor": payloads["receptor"],
        "input_ids": {"record_sha256s": hashes, "native_sha256": case["native"]["sha256"], "receptor_sha256": case["receptor"]["sha256"]}}


def scientific_projection(row: dict) -> dict:
    """Omit four explicit observational paths, never nested scientific values."""
    require(type(row) is dict and type(row.get("engine_v2_diagnostics")) is dict, "scientific row/diagnostics missing")
    result = deepcopy(row)
    _finite(result.pop("runtime_seconds"), "row runtime")
    _finite(result["engine_v2_diagnostics"].pop("diagnostic_evaluation_seconds"), "diagnostic runtime")
    for name in ("execution_command", "execution_policy"):
        value = result.pop(name)
        require(type(value) is list and value and all(type(item) is str for item in value), "invalid observational row field: " + name)
    return result


def _legacy_return(outcomes: tuple) -> dict:
    rmsds, geometric, chemical, failures = outcomes
    return {"rmsds": list(rmsds), "rmsds_binary64_hex": [value.hex() for value in rmsds],
            "geometric_valid": list(geometric), "chemical_valid": list(chemical), "failed_check_ids": [list(row) for row in failures]}


def validate_report(report: dict, *, selected: dict, bundle: dict, mode: str) -> None:
    require(type(report) is dict and report.get("schema_id") == "betelgeuze.posebusters_runner_report/1.0.0", "raw runner report schema differs")
    count = len(selected["expected"])
    equal({name: report[name] for name in ("case_id", "mode", "evaluator_identity", "evaluation_call", "record_count")},
          {"case_id": selected["case"]["case_id"], "mode": mode, "evaluator_identity": bundle["evaluator_identities"][mode],
           "evaluation_call": 1, "record_count": count}, "raw report evaluation identity")
    equal(report["input_ids"], selected["input_ids"], "raw report input binding")
    equal(report["evaluator_versions"], bundle["evaluator_versions"], "raw report evaluator versions")
    equal(report["upstream_source_sha256"], bundle["upstream_source_sha256"], "raw report upstream source")
    legacy = report["legacy_outcomes"]
    require(type(legacy["rmsds"]) is list and len(legacy["rmsds"]) == count and
            all(type(value) is float and math.isfinite(value) and value >= 0 for value in legacy["rmsds"]), "invalid raw RMSD scalar/denominator")
    equal([value.hex() for value in legacy["rmsds"]], legacy["rmsds_binary64_hex"], "raw RMSD binary64 bits")
    historical = common.legacy_projection(selected["expected"])
    equal({name: legacy[name] for name in historical}, historical, "historical exact outcomes")
    common.validate_full_report(report["fullReport"], selected=selected)
    require(len(report["fullReport"]["columns"]) == PROTOCOL["full_report_column_count"], "raw report column denominator differs")
    immutable = report["input_immutability"]
    require(immutable["verified"] is True and immutable["pickle_policy"] == "AllProps|CoordsAsDouble", "molecular input immutability was not verified")
    equal(immutable["before"], immutable["after"], "molecular input mutation")
    before = immutable["before"]
    require(type(before) is dict and set(before) == {"predicted", "native", "receptor"} and
            type(before["predicted"]) is list and len(before["predicted"]) == count, "molecule fingerprint denominator differs")
    for value in [*before["predicted"], before["native"], before["receptor"]]:
        _sha(value, "molecular fingerprint")


def validate_energy_cache(before: dict, after: dict, context: dict, count: int) -> None:
    for state in (before, after):
        require(type(state) is dict and set(state) == {"hits", "misses", "maxsize", "current_size"}, "energy LRU state schema differs")
        # Source-pinned PoseBusters 0.3.1 decorates get_average_energy with
        # lru_cache(maxsize=None); None is the original unbounded policy.
        require(state["maxsize"] is None, "frozen energy LRU capacity must be unbounded")
        for key in ("hits", "misses", "current_size"):
            _integer(state[key], "energy LRU " + key)
        require(state["current_size"] <= state["misses"], "energy LRU entries exceed observed misses")
    equal({name: before[name] for name in ("hits", "misses", "current_size")},
          {"hits": 0, "misses": 0, "current_size": 0}, "fresh process energy LRU is not empty")
    equal(before["maxsize"], after["maxsize"], "energy LRU capacity changed")
    require(after["hits"] + after["misses"] == count and after["misses"] >= 1, "energy LRU evaluation count differs")
    equal(context["first_observed"], before, "context energy LRU entry")
    equal(context["last_observed"], after, "context energy LRU exit")
    equal(context["hits_added"], after["hits"], "energy LRU hits")
    equal(context["misses_added"], after["misses"], "energy LRU misses")
    require(context["cleared_by_context"] is False, "energy LRU must not be cleared")


def validate_context(before: dict, after: dict, *, selected: dict, bundle: dict, mode: str,
                     energy_before: dict, energy_after: dict) -> None:
    count = len(selected["expected"])
    for item in (before, after):
        equal({name: item[name] for name in ("schema_id", "case_id", "mode", "evaluator_identity", "healthy")},
              {"schema_id": "betelgeuze.posebusters_evaluator_context/1.0.0", "case_id": selected["case"]["case_id"],
               "mode": mode, "evaluator_identity": bundle["evaluator_identities"][mode], "healthy": True}, "evaluator context identity/health")
    fields = ("closed", "bust_calls", "record_evaluations", "full_reports_observed", "input_immutability_verified_batches")
    equal({name: before[name] for name in fields},
          {"closed": False, "bust_calls": 0, "record_evaluations": 0, "full_reports_observed": 0, "input_immutability_verified_batches": 0}, "evaluator context entry lifetime")
    equal({name: after[name] for name in fields},
          {"closed": True, "bust_calls": 1, "record_evaluations": count, "full_reports_observed": 1, "input_immutability_verified_batches": 1}, "evaluator context exit lifetime")
    equal(after["input_ids"], {key: selected["input_ids"][key] for key in ("native_sha256", "receptor_sha256")}, "evaluator receptor/input lifetime")
    require(before["input_ids"] is None and before["receptor_preparation"] is None and before["subset_filter"] is None, "context already bound/prepared at entry")
    if mode == "reference":
        require(after["receptor_preparation"] is None and after["subset_filter"] is None, "reference context used an optimization")
    else:
        equal(after["receptor_preparation"], {"hits": 4 * count - 4, "misses": 4, "entries": 4, "max_entries": 4}, "bounded receptor preparation cache")
        if mode == "prepared_receptor":
            require(after["subset_filter"] is None, "prepared receptor unexpectedly used subset strategy")
        else:
            from tools.posebusters_subset import FROZEN_RDKIT_VERSION, IMPLEMENTATION_ID
            stats = after["subset_filter"]
            require(type(stats) is dict and stats["implementation_id"] == IMPLEMENTATION_ID and
                    stats["rdkit_version"] == FROZEN_RDKIT_VERSION, "subset implementation identity differs")
            for key in ("calls", "identity_calls", "fast_path_calls", "fallback_calls", "fast_path_errors", "fallback_errors",
                        "source_atoms_fast_path", "retained_atoms_fast_path", "removed_atoms_fast_path",
                        "bonded_fast_path_calls", "bondless_fast_path_calls", "source_bonds_fast_path",
                        "retained_bonds_fast_path", "removed_bonds_fast_path"):
                _integer(stats.get(key), "subset " + key)
            require(stats["calls"] == stats["identity_calls"] + stats["fast_path_calls"] + stats["fallback_calls"] and
                    stats["fast_path_errors"] == stats["fallback_errors"] == 0, "subset call/error accounting differs")
            require(stats["bonded_fast_path_calls"] + stats["bondless_fast_path_calls"] == stats["fast_path_calls"],
                    "subset bonded/bondless call accounting differs")
            require(stats["source_atoms_fast_path"] == stats["retained_atoms_fast_path"] + stats["removed_atoms_fast_path"], "subset atom accounting differs")
            require(stats["source_bonds_fast_path"] == stats["retained_bonds_fast_path"] + stats["removed_bonds_fast_path"],
                    "subset bond accounting differs")
            if selected["case"]["case_id"] in PILOT_CASES:
                require(stats["bonded_fast_path_calls"] > 0 and
                        stats["source_bonds_fast_path"] >= stats["bonded_fast_path_calls"],
                        "pilot subset strategy did not apply the fast path to bonded source inputs")
            require(type(stats["fallback_reasons"]) is dict, "subset fallback reasons missing")
            for value in stats["fallback_reasons"].values():
                _integer(value, "subset fallback reason count", minimum=1)
            require(sum(stats["fallback_reasons"].values()) == stats["fallback_calls"], "subset fallback accounting differs")
    validate_energy_cache(energy_before, energy_after, after["energy_cache"], count)
    timing = after["timings"]
    require(timing["collect_metrics"] is True, "context metrics were not enabled")
    for key in ("posebusters_ns", "input_identity_check_ns", "report_observer_ns"):
        _integer(timing[key], "context timer " + key, minimum=1)
    for row in timing["volume_substages"]:
        require(type(row["module"]) is str and type(row["stage"]) is str, "invalid volume timer label")
        for key in ("calls", "total_ns", "min_ns", "max_ns"):
            _integer(row[key], "volume " + key, minimum=1)
        require(row["min_ns"] <= row["max_ns"] <= row["total_ns"], "volume timer bounds differ")


def journal_identity(*, source: dict, bundle_sha256: str, case_id: str, stage: str,
                     mode: str, evaluator_identity: str, seed: int, actual_argv: list[str]) -> dict:
    return {"schema_id": SCHEMA, "source": source, "bundle_sha256": bundle_sha256,
        "protocol_sha256": digest(PROTOCOL), "case_id": case_id, "stage": stage, "mode": mode,
        "evaluator_identity": evaluator_identity, "seed": seed, "actual_argv": actual_argv}


def verify_journal(directory: Path, *, expected_identity: dict) -> tuple[list[dict], dict]:
    identity_path = relative_file(directory, "identity.json")
    identity = read_json(identity_path)
    equal(identity, expected_identity, "durable journal identity")
    identity_sha = digest(identity)
    events, previous, total = [], None, 0
    paths = sorted(directory.glob("event-*.json"))
    require(1 <= len(paths) <= PROTOCOL["journal_limit_events"], "journal event bound/denominator differs")
    for index, path in enumerate(paths, 1):
        require(path.name == f"event-{index:06d}.json", "journal missing/duplicate/out-of-order sequence")
        raw = relative_file(directory, path.name).read_bytes()
        total += len(raw)
        require(total <= PROTOCOL["journal_limit_bytes"], "journal byte limit exceeded")
        wrapper = inputs.frozen._json(raw, path.name)
        require(type(wrapper) is dict and set(wrapper) == {"schema_id", "journal_sequence", "identity_sha256",
                "previous_event_sha256", "event", "event_sha256"}, "journal wrapper fields differ")
        equal({name: wrapper[name] for name in ("schema_id", "journal_sequence", "identity_sha256", "previous_event_sha256")},
              {"schema_id": "betelgeuze.redocking_phase_journal_event/1.0.0", "journal_sequence": index,
               "identity_sha256": identity_sha, "previous_event_sha256": previous}, "journal hash-chain binding")
        verify_signed(wrapper, "event_sha256", "journal event")
        require(raw == canonical(wrapper) + b"\n" and type(wrapper["event"]) is dict, "journal event bytes/schema differ")
        events.append(wrapper["event"])
        previous = wrapper["event_sha256"]
    checkpoint_path = relative_file(directory, "checkpoint.json")
    checkpoint = read_json(checkpoint_path)
    equal(checkpoint, {"schema_id": "betelgeuze.redocking_phase_checkpoint/1.0.0", "identity_sha256": identity_sha,
        "last_sequence": len(events), "event_path": paths[-1].name, "event_sha256": previous,
        "event_bytes_total": total, "last_event": events[-1]}, "durable journal checkpoint")
    return events, {"identity_file_sha256": isolation.digest_file(identity_path),
        "checkpoint_file_sha256": isolation.digest_file(checkpoint_path), "identity_sha256": identity_sha,
        "event_count": len(events), "event_bytes_total": total, "last_event_sha256": previous}


def phase_durations(events: list[dict]) -> list[dict]:
    groups = {}
    for event in events:
        if event.get("phase") != "complete":
            continue
        seconds = _finite(event.get("elapsed_seconds"), "journal phase duration")
        stage = event.get("stage")
        require(type(stage) is str and stage, "journal phase has no stage")
        origin = "development_observation" if event.get("schema_id") == lineage.EVENT_SCHEMA else "worker"
        groups.setdefault((origin, stage), []).append(seconds)
    return [{"origin": origin, "stage": stage, "calls": len(values), "total_seconds": sum(values),
             "min_seconds": min(values), "max_seconds": max(values)}
            for (origin, stage), values in sorted(groups.items())]


def _node_identity() -> dict:
    return {"hostname": platform.node(), "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None}


@contextmanager
def _private_pipeline_inputs(selected: dict, *, runner: Any, output_root: Path):
    """Materialize verified bytes under the runner's unchanged private-input contract."""
    case = selected["case"]
    require(case["case_id"] in inputs.CASE_IDS, "private input case is outside the fixed cohort")
    roles = ("receptor", "reference", "native", "seed")
    hashes = {role: case[role]["sha256"] for role in roles}
    names = {role: Path(case[role]["relative_path"]).name for role in roles}
    require(len(set(names.values())) == len(roles), "private input filenames collide")
    parent = runner._owned_directory_descriptor(output_root, create=False)
    os.close(parent)
    # Downloaded artifacts do not retain the public runner's 0500/0400 modes.
    # Each worker gets distinct inodes; the shared, hash-bound bundle is untouched.
    with tempfile.TemporaryDirectory(prefix="pipeline-inputs-", dir=output_root) as temporary:
        directory = Path(temporary) / case["case_id"]
        descriptor_fd = runner._owned_directory_descriptor(directory, create=True, exact_mode=0o700)
        paths = {"directory": directory}
        try:
            for role in roles:
                target = directory / names[role]
                runner._atomic_bytes(target, bound_file(selected["root"], case[role]))
                target.chmod(0o400)
                paths[role] = target
            os.fchmod(descriptor_fd, 0o500)
            runner._require_case_input_identity(paths, hashes)
            yield paths
        finally:
            # Restore only the owned private directory, including on pin/profile
            # failure, before TemporaryDirectory removes it and any private aliases.
            try:
                os.fchmod(descriptor_fd, 0o700)
            finally:
                os.close(descriptor_fd)


def _pipeline(selected: dict, *, runner: Any, observer: Any, context: Any, journal: Any, output_root: Path) -> dict:
    case = selected["case"]
    hashes = {role: case[role]["sha256"] for role in ("receptor", "reference", "native", "seed")}
    profiles = {profile.case_id: profile for profile in runner.frozen_public_redocking_profiles()}
    output = output_root / "poses" / (case["case_id"] + ".sdf")
    with _private_pipeline_inputs(selected, runner=runner, output_root=output_root) as paths, \
            runner.PinnedCaseInputs(paths, hashes) as pinned:
        with journal.stage("profile_validation"), pinned.verified_window():
            profile = runner._profile(case["case_id"], pinned.execution_paths, profiles[case["case_id"]], development_observation=observer)
            write_document(output_root, "profile-observation.json", {"case_id": profile.case_id,
                "heavy_atom_count": profile.heavy_atom_count, "rotor_count": profile.rotor_count,
                "ring_count": profile.ring_count, "ligand_artifact_sha256": profile.ligand_artifact_sha256})
        started = time.perf_counter_ns()
        with journal.stage("engine_v2_result"), pinned.verified_window():
            row = runner._engine_v2_result(case["case_id"], pinned.execution_paths, logical_paths=paths,
                input_sha256s=hashes, output=output, seed=case["frozen_case_seed"],
                scorer_backend=runner.ScorerBackend.PYTHON_REFERENCE,
                development_observation=observer, evaluation_context=context)
        elapsed = time.perf_counter_ns() - started
        pinned.verify()
    document = row.to_dict()
    require(document["status"] == "success", "fresh pipeline did not produce a successful scientific row")
    row_descriptor = write_document(output_root, "scientific-row.json", document)
    output_descriptor = descriptor(output_root, "poses/" + case["case_id"] + ".sdf")
    require(bound_file(output_root, output_descriptor) == bound_file(selected["root"], case["top5"]), "fresh pipeline Top5 output bytes differ from original")
    equal(scientific_projection(document), scientific_projection(selected["source_row"]), "fresh pipeline historical scientific row")
    return {"runner_call_ns": elapsed, "scientific_row": row_descriptor, "top5": output_descriptor,
            "profile_observation": descriptor(output_root, "profile-observation.json")}


def worker(args: argparse.Namespace) -> int:
    output_root = inputs.frozen._no_symlink_path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)  # supervisor owns log/receipt siblings
    require(not (output_root / "result.json").exists(), "worker result is not fresh")
    result = {"schema_id": SCHEMA, "status": "failed", "stage": args.stage, "case_id": args.case_id,
        "mode": args.mode, "bundle_sha256": args.bundle_sha256, "protocol_sha256": digest(PROTOCOL),
        "actual_argv": list(sys.orig_argv), "working_directory": str(Path.cwd()),
        "pid": os.getpid(), "parent_pid": os.getppid(), "node": _node_identity(), "files": {}}
    context = observer = journal = None
    try:
        bundle, manifest = load_bundle(args.input_root, args.bundle_sha256)
        equal(source_identity(), bundle["source"], "worker current source checkout")
        selected = selected_inputs(args.input_root, bundle, manifest, args.case_id, args.stage)
        result.update(source=bundle["source"], source_snapshot_sha256=bundle["source_snapshot_sha256"],
                      evaluator_identity=bundle["evaluator_identities"][args.mode])
        identity = journal_identity(source=bundle["source"], bundle_sha256=args.bundle_sha256,
            case_id=args.case_id, stage=args.stage, mode=args.mode, evaluator_identity=result["evaluator_identity"],
            seed=selected["case"]["frozen_case_seed"], actual_argv=result["actual_argv"])
        journal = isolation.AtomicJournal(output_root / "journal", identity,
            max_bytes=PROTOCOL["journal_limit_bytes"], max_events=PROTOCOL["journal_limit_events"])
        with journal.stage("environment_before"):
            before = capture_environment(args.runtime_root)
            validate_environment(before, bundle=bundle)
            result["files"]["environment_before"] = write_document(output_root, "environment-before.json", before)
        from tools import run_engine_v2_public_redocking_300 as runner
        from tools.posebusters_evaluator_context import PoseBustersEvaluatorContext
        from tools.redocking_development_p1 import DevelopmentObservation
        with journal.stage("evaluator_initialization"):
            runner._configure_engine_v2_cpu()
            runtime = adapter._load_runtime()
            energy_before = adapter._cache_info_document(runtime.energy.get_average_energy.cache_info())
            equal({key: energy_before[key] for key in ("hits", "misses", "current_size")},
                  {"hits": 0, "misses": 0, "current_size": 0}, "fresh worker energy cache entry")
        reports = []

        def observe_report(report):
            reports.append(report)
            require(len(reports) == 1, "runner emitted more than one fullReport")
            result["files"]["full_report"] = write_document(output_root, "full-report.json", report)
            journal.emit({"stage": "raw_full_report", "phase": "snapshot", "details": {"file": result["files"]["full_report"]}})

        context = PoseBustersEvaluatorContext(args.case_id, mode=args.mode, report_observer=observe_report, collect_metrics=True)
        equal(context.evaluator_identity, bundle["evaluator_identities"][args.mode], "current evaluator implementation identity")
        observer = DevelopmentObservation(args.case_id, event_sink=journal.emit,
            evaluator_identity=context.evaluator_identity, reuse_evaluations=True)
        result["files"]["context_before"] = write_document(output_root, "evaluator-before.json", context.summary())
        with context:
            if args.stage == "replay":
                outcomes, started = [], time.perf_counter_ns()
                for ordinal in (1, 2):
                    with journal.stage("runner_posebusters_outcomes", call_ordinal=ordinal):
                        value = runner._posebusters_outcomes(b"".join(selected["records"]),
                            native_payload=selected["native"], receptor_payload=selected["receptor"], expected_pose_count=5,
                            development_observation=observer, evaluation_context=context)
                        outcomes.append(_legacy_return(value))
                result.update(runner_call_ns=time.perf_counter_ns() - started, returned_outcomes=outcomes)
            else:
                pipeline = _pipeline(selected, runner=runner, observer=observer, context=context, journal=journal, output_root=output_root)
                result["runner_call_ns"] = pipeline.pop("runner_call_ns")
                result["files"].update(pipeline)
        observer.assert_healthy()
        require(len(reports) == 1, "runner did not retain exactly one fullReport")
        result["energy_before"] = energy_before
        result["energy_after"] = adapter._cache_info_document(runtime.energy.get_average_energy.cache_info())
        result["files"]["context_after"] = write_document(output_root, "evaluator-after.json", context.summary())
        result["files"]["observation_summary"] = write_document(output_root, "observation-summary.json", observer.summary())
        with journal.stage("environment_after"):
            after = capture_environment(args.runtime_root)
            validate_environment(after, bundle=bundle)
            evidence.require_matching_environment(before, after)
            equal(source_identity(), bundle["source"], "worker source changed during execution")
            result["files"]["environment_after"] = write_document(output_root, "environment-after.json", after)
        journal.emit({"stage": "worker_complete", "phase": "snapshot", "details": {"status": "success"}})
        events, result["journal"] = verify_journal(output_root / "journal", expected_identity=identity)
        result["phase_durations"], result["status"] = phase_durations(events), "success"
        validate_worker(output_root, result, selected=selected, bundle=bundle, bundle_sha256=args.bundle_sha256,
                        stage=args.stage, mode=args.mode, actual_argv=result["actual_argv"], require_result_hash=False)
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        if journal is not None:
            try:
                journal.emit({"stage": "worker_failure", "phase": "error", "details": {"exception_type": type(exc).__name__, "message": str(exc)}})
            except Exception as journal_exc:
                result["failure_journal_error"] = str(journal_exc)
    finally:
        if context is not None and not context.summary()["closed"]:
            try:
                context.close()
            except Exception as exc:
                result.update(status="failed", context_close_error=str(exc))
        if context is not None:
            result["final_context"] = context.summary()
        if observer is not None:
            result["final_observation"] = observer.summary()
    isolation.atomic_json(output_root / "result.json", signed(result, "result_sha256"), replace=False)
    return 0 if result["status"] == "success" else 1


def validate_worker(directory: Path, result: dict, *, selected: dict, bundle: dict,
                    bundle_sha256: str, stage: str, mode: str, actual_argv: list[str],
                    require_result_hash: bool = True) -> dict:
    if require_result_hash:
        verify_signed(result, "result_sha256", "worker result")
    equal({name: result[name] for name in ("schema_id", "status", "stage", "case_id", "mode", "bundle_sha256", "protocol_sha256")},
          {"schema_id": SCHEMA, "status": "success", "stage": stage, "case_id": selected["case"]["case_id"],
           "mode": mode, "bundle_sha256": bundle_sha256, "protocol_sha256": digest(PROTOCOL)}, "worker identity/status")
    equal(result["source"], bundle["source"], "worker source commit/tree")
    equal(result["source_snapshot_sha256"], bundle["source_snapshot_sha256"], "worker observed source inventory")
    equal(result["evaluator_identity"], bundle["evaluator_identities"][mode], "worker strategy identity")
    equal(result["actual_argv"], actual_argv, "worker observed argv")
    _integer(result["pid"], "worker PID", minimum=1)
    _integer(result["parent_pid"], "controller PID", minimum=1)
    _integer(result["runner_call_ns"], "runner call timer", minimum=1)
    files = result["files"]
    expected_files = {"environment_before": "environment-before.json", "environment_after": "environment-after.json",
        "full_report": "full-report.json", "context_before": "evaluator-before.json",
        "context_after": "evaluator-after.json", "observation_summary": "observation-summary.json"}
    if stage == "pipeline":
        expected_files.update(scientific_row="scientific-row.json", profile_observation="profile-observation.json",
                              top5="poses/" + selected["case"]["case_id"] + ".sdf")
    equal(sorted(files), sorted(expected_files), "worker evidence file roles")
    for role, relative in expected_files.items():
        equal(files[role]["relative_path"], relative, "worker evidence path " + role)
    report = read_document(directory, files["full_report"])
    validate_report(report, selected=selected, bundle=bundle, mode=mode)
    before = read_document(directory, files["context_before"])
    context = read_document(directory, files["context_after"])
    validate_context(before, context, selected=selected, bundle=bundle, mode=mode,
                     energy_before=result["energy_before"], energy_after=result["energy_after"])
    observation = read_document(directory, files["observation_summary"])
    count = len(selected["expected"])
    equal({name: observation[name] for name in ("profile", "case_id", "evaluator_identity", "healthy", "incomplete_stages",
                                                "evaluation_cache", "prepared_inputs")},
          {"profile": "development_observation_v1", "case_id": selected["case"]["case_id"],
           "evaluator_identity": result["evaluator_identity"], "healthy": True, "incomplete_stages": [],
           "evaluation_cache": {"evaluation_calls": 1, "reused_records": 5, "cached_records": count},
           "prepared_inputs": {"cache_hits": 0, "cache_misses": 1}}, "unchanged P1 caches and health")
    if require_result_hash:
        equal(result["final_context"], context, "closed final context state")
        equal(result["final_observation"], observation, "final observation state")
    identity = journal_identity(source=bundle["source"], bundle_sha256=bundle_sha256,
        case_id=selected["case"]["case_id"], stage=stage, mode=mode, evaluator_identity=result["evaluator_identity"],
        seed=selected["case"]["frozen_case_seed"], actual_argv=actual_argv)
    events, journal = verify_journal(directory / "journal", expected_identity=identity)
    equal(journal, result["journal"], "worker journal receipt")
    equal(phase_durations(events), result["phase_durations"], "journal phase durations")
    p1_events, evaluator = lineage._events(events, selected["case"]["case_id"])
    equal(evaluator, result["evaluator_identity"], "journal evaluator implementation")
    equal(len(p1_events), observation["emitted_events"], "P1 emitted event denominator")
    lookups = [event["details"] for event in p1_events if event["stage"] == "evaluation_cache_lookup"]
    expected_lookup = {"native_sha256": selected["input_ids"]["native_sha256"], "receptor_sha256": selected["input_ids"]["receptor_sha256"]}
    equal(lookups, [{**expected_lookup, "record_count": count, "complete_hit": False, "record_sha256s": selected["input_ids"]["record_sha256s"]},
                   {**expected_lookup, "record_count": 5, "complete_hit": True, "record_sha256s": selected["input_ids"]["record_sha256s"][:5]}],
          "one batch and Top5 cache-hit events")
    raw_events = [event for event in events if event.get("stage") == "raw_full_report"]
    equal(raw_events, [{"stage": "raw_full_report", "phase": "snapshot", "details": {"file": files["full_report"]}}], "durable raw report observation")
    equal(events[-1], {"stage": "worker_complete", "phase": "snapshot", "details": {"status": "success"}}, "durable worker completion")
    environment_before = read_document(directory, files["environment_before"])
    environment_after = read_document(directory, files["environment_after"])
    for environment in (environment_before, environment_after):
        validate_environment(environment, bundle=bundle)
    evidence.require_matching_environment(environment_before, environment_after)
    scientific_sha = lineage_report = None
    if stage == "replay":
        equal(result["returned_outcomes"], [report["legacy_outcomes"], report["legacy_outcomes"]], "actual runner return values and cached reuse")
    else:
        require("returned_outcomes" not in result, "pipeline claims a separate replay result")
        row = read_document(directory, files["scientific_row"])
        projection = scientific_projection(row)
        equal(projection, scientific_projection(selected["source_row"]), "all original scientific row fields")
        scientific_sha = digest(projection)
        require(bound_file(directory, files["top5"]) == bound_file(selected["root"], selected["case"]["top5"]), "fresh pipeline Top5 bytes differ")
        profile = read_document(directory, files["profile_observation"])
        require(profile["case_id"] == selected["case"]["case_id"] and
                profile["ligand_artifact_sha256"] == selected["case"]["native"]["sha256"], "profile validation binding differs")
        for name in ("heavy_atom_count", "rotor_count", "ring_count"):
            _integer(profile[name], "validated profile " + name, minimum=1 if name == "heavy_atom_count" else 0)
        lineage_report = lineage.validate_observation_events(events, case_id=selected["case"]["case_id"], canonical_row=row)
        equal(lineage_report["evaluator_identity"], result["evaluator_identity"], "pipeline lineage evaluator")
        snapshots = {event["details"]["proposal_index"]: event["details"] for event in p1_events if event["stage"] == "refinement_selected"}
        for candidate in selected["case"]["candidates_sorted"]:
            path = relative_file(selected["root"], candidate["coordinates_relative_path"])
            equal(isolation.digest_file(path), candidate["coordinate_sha256"], "historical candidate coordinates")
            equal(snapshots[candidate["proposal_index"]]["coordinates_binary64"], read_json(path), "fresh candidate coordinate binary64 payload")
    return {"report": report, "context": context, "observation": observation,
        "scientific_projection_sha256": scientific_sha, "lineage": lineage_report,
        "environment_content_identity_sha256": environment_before["content_identity_sha256"]}


def _execution_context(summary: dict) -> dict:
    context = summary.get("execution_context")
    require(type(context) is dict and set(context) == {"python_executable", "input_root", "runtime_root", "output_root", "working_directory"},
            "original execution context is missing")
    for name, value in context.items():
        require(type(value) is str and value.startswith("/") and not value.startswith("//") and "\\" not in value
                and not any(ord(char) < 32 or ord(char) == 127 for char in value)
                and PurePosixPath(value).as_posix() == value and ".." not in PurePosixPath(value).parts,
                "noncanonical recorded execution path: " + name)
    return context


def worker_command(summary: dict, *, slot: int, mode: str) -> list[str]:
    order = mode_order(summary["case_id"], summary["stage"])
    require(type(slot) is int and 0 <= slot < 3 and order[slot] == mode, "worker slot/mode differs")
    _sha(summary["bundle_sha256"], "worker command bundle")
    context = _execution_context(summary)
    output = str(PurePosixPath(context["output_root"]) / f"worker-{slot}-{mode}")
    return [context["python_executable"], "-m", MODULE, "worker", "--input-root", context["input_root"],
        "--bundle-sha256", summary["bundle_sha256"], "--runtime-root", context["runtime_root"],
        "--stage", summary["stage"], "--case-id", summary["case_id"], "--mode", mode, "--output-root", output]


def validate_execution(record: dict, *, directory: Path, summary: dict, slot: int, mode: str) -> None:
    require(type(record) is dict and record.get("schema_id") == "betelgeuze.redocking_process_execution/1.0.0", "invalid process receipt schema")
    verify_signed(record, "control_sha256", "process execution")
    require(common.execution_ok(record) and record.get("error") is None, "worker resource/exit/cleanup gate failed")
    equal(record["command"], worker_command(summary, slot=slot, mode=mode), "supervised worker argv")
    limits = {"wall_limit_seconds": PROTOCOL["wall_limit_seconds"][summary["stage"]],
              "rss_limit_bytes": PROTOCOL["rss_limit_bytes"], "rss_sampling_seconds": PROTOCOL["rss_sampling_seconds"]}
    equal({name: record[name] for name in limits}, limits, "supervised experiment resource limits")
    _finite(record["wall_seconds"], "supervised wall time", positive=True)
    _finite(record["child_cpu_seconds"], "supervised CPU time")
    require(_integer(record["sampled_peak_process_tree_rss_bytes"], "sampled RSS") <= PROTOCOL["rss_limit_bytes"], "worker exceeded RSS protocol")
    require(type(record["streams"]) is dict and set(record["streams"]) == {"stdout", "stderr"}, "supervised log streams missing")
    for name, stream in record["streams"].items():
        require(stream["path"] == name + ".log" and stream["eof_observed"] is True, "log stream path/EOF differs")
        for key in ("bytes_seen", "bytes_retained", "bytes_discarded"):
            _integer(stream[key], "log " + key)
        require(stream["bytes_retained"] == min(stream["bytes_seen"], PROTOCOL["log_limit_bytes"]) and
                stream["bytes_discarded"] == stream["bytes_seen"] - stream["bytes_retained"] and
                stream["truncated"] is (stream["bytes_discarded"] > 0), "bounded log accounting differs")
        payload = relative_file(directory, stream["path"]).read_bytes()
        require(len(payload) == stream["bytes_retained"] and hashlib.sha256(payload).hexdigest() == stream["retained_sha256"], "supervised log bytes differ")


def assess_case(directory: Path, summary: dict, *, selected: dict, bundle: dict, bundle_sha256: str) -> dict:
    equal(summary["schema_id"], SCHEMA, "case summary schema")
    equal(summary["source"], bundle["source"], "case source")
    equal(summary["bundle_sha256"], bundle_sha256, "case bundle")
    equal(summary["protocol_sha256"], digest(PROTOCOL), "case protocol")
    order = mode_order(summary["case_id"], summary["stage"])
    equal(summary["case_id"], selected["case"]["case_id"], "case selected inputs")
    require(type(summary["observations"]) is list and len(summary["observations"]) == 3, "missing/duplicate mode observation")
    observed, pids = {}, []
    for slot, (item, mode) in enumerate(zip(summary["observations"], order, strict=True)):
        equal({name: item[name] for name in ("slot", "mode", "worker_directory", "process_gate_passed")},
              {"slot": slot, "mode": mode, "worker_directory": f"worker-{slot}-{mode}", "process_gate_passed": True}, "case mode order/process gate")
        worker_root = directory / item["worker_directory"]
        equal(item["execution"]["relative_path"], f"worker-{slot}-{mode}/process-execution.json", "process receipt path")
        require(type(item["result"]) is dict, "worker result was not retained")
        equal(item["result"]["relative_path"], f"worker-{slot}-{mode}/result.json", "worker result path")
        execution = read_document(directory, item["execution"])
        validate_execution(execution, directory=worker_root, summary=summary, slot=slot, mode=mode)
        result = read_document(directory, item["result"])
        equal(result["node"], summary["node"], "same-node worker binding")
        equal(result["parent_pid"], summary["controller_pid"], "sequential controller parent binding")
        equal(result["working_directory"], _execution_context(summary)["working_directory"], "observed worker working directory")
        pids.append(result["pid"])
        admitted = validate_worker(worker_root, result, selected=selected, bundle=bundle, bundle_sha256=bundle_sha256,
            stage=summary["stage"], mode=mode, actual_argv=worker_command(summary, slot=slot, mode=mode))
        observed[mode] = {**admitted, "result": result, "execution": execution, "slot": slot}
    require(len(set(pids)) == 3, "mode workers did not use fresh processes")
    reference = observed["reference"]
    for mode in MODES[1:]:
        other = observed[mode]
        for name in ("fullReport", "legacy_outcomes", "input_ids", "evaluator_versions", "upstream_source_sha256", "input_immutability"):
            equal(reference["report"][name], other["report"][name], "mode exact equivalence: " + name)
        for name in ("energy_before", "energy_after"):
            equal(reference["result"][name], other["result"][name], "unchanged energy LRU policy: " + name)
        equal(reference["scientific_projection_sha256"], other["scientific_projection_sha256"], "mode scientific projection")
    before = read_document(directory, summary["environment_before"])
    after = read_document(directory, summary["environment_after"])
    for environment in (before, after):
        validate_environment(environment, bundle=bundle)
    evidence.require_matching_environment(before, after)
    pairs = []
    for left, right in PROTOCOL["performance_pairs"]:
        a, b = observed[left], observed[right]
        metrics = {}
        for timer, first, second in (
            ("posebusters_ns", a["context"]["timings"]["posebusters_ns"], b["context"]["timings"]["posebusters_ns"]),
            ("runner_call_ns", a["result"]["runner_call_ns"], b["result"]["runner_call_ns"]),
            ("supervised_worker_wall_seconds", a["execution"]["wall_seconds"], b["execution"]["wall_seconds"]),
        ):
            metrics[timer] = {"first": first, "second": second, "saved_fraction": (first - second) / first}
        pairs.append({"first_mode": left, "second_mode": right, "first_slot": a["slot"], "second_slot": b["slot"], "observation_pairs": 1, "metrics": metrics})
    return {"exact_equivalence_passed": True, "numerical_tolerance": None,
        "full_report_sha256": digest(reference["report"]["fullReport"]), "legacy_outcomes_sha256": digest(reference["report"]["legacy_outcomes"]),
        "scientific_projection_sha256": reference["scientific_projection_sha256"],
        "full_report_rows": len(selected["expected"]), "full_report_columns": PROTOCOL["full_report_column_count"],
        "same_node_environment_stable": True, "environment_content_identity_sha256": before["content_identity_sha256"],
        "evaluator_identities": bundle["evaluator_identities"], "pairs": pairs,
        "mode_observations": {mode: {"slot": observed[mode]["slot"], "context": observed[mode]["context"],
            "observation": observed[mode]["observation"], "lineage": observed[mode]["lineage"],
            "phase_durations": observed[mode]["result"]["phase_durations"]} for mode in MODES},
        "performance_inference": PROTOCOL["performance_inference"]}


def run_case(args: argparse.Namespace) -> int:
    directory = inputs.frozen._no_symlink_path(args.output_root)
    require(not directory.exists(), "case output directory must be fresh")
    directory.mkdir(parents=True)
    summary = {"schema_id": SCHEMA, "status": "failed", "case_id": args.case_id, "stage": args.stage,
        "bundle_sha256": args.bundle_sha256, "protocol_sha256": digest(PROTOCOL), "observations": [],
        "controller_pid": os.getpid(), "node": _node_identity(),
        "execution_context": {"python_executable": str(Path(sys.executable).absolute()), "input_root": str(args.input_root),
            "runtime_root": str(args.runtime_root), "output_root": str(directory), "working_directory": str(ROOT)},
        "job": {name: os.environ.get(name) for name in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion")}}
    write_document(directory, "case-request.json", summary)
    cleanup_ok = True
    try:
        bundle, manifest = load_bundle(args.input_root, args.bundle_sha256)
        equal(source_identity(), bundle["source"], "controller source checkout")
        summary["source"] = bundle["source"]
        selected = selected_inputs(args.input_root, bundle, manifest, args.case_id, args.stage)
        before = capture_environment(args.runtime_root)
        validate_environment(before, bundle=bundle)
        summary["environment_before"] = write_document(directory, "environment-before.json", before)
        for slot, mode in enumerate(mode_order(args.case_id, args.stage)):
            worker_relative = f"worker-{slot}-{mode}"
            worker_root = directory / worker_relative
            command = worker_command(summary, slot=slot, mode=mode)
            limits = isolation.Limits(wall_seconds=PROTOCOL["wall_limit_seconds"][args.stage], rss_bytes=PROTOCOL["rss_limit_bytes"],
                                      poll_seconds=PROTOCOL["rss_sampling_seconds"], log_bytes=PROTOCOL["log_limit_bytes"])
            try:
                execution = isolation.supervise(command, worker_root, limits, cwd=ROOT, env=dict(os.environ))
            except isolation.CleanupError:
                cleanup_ok = False
                execution = read_json(relative_file(worker_root, "process-execution.json"))
            summary["observations"].append({"slot": slot, "mode": mode, "worker_directory": worker_relative,
                "execution": descriptor(directory, worker_relative + "/process-execution.json"),
                "result": descriptor(directory, worker_relative + "/result.json") if (worker_root / "result.json").is_file() else None,
                "process_gate_passed": common.execution_ok(execution)})
            isolation.atomic_json(directory / "progress.json", summary)
            require(cleanup_ok, "descendant cleanup could not be confirmed; later workers were not launched")
        after = capture_environment(args.runtime_root)
        validate_environment(after, bundle=bundle)
        summary["environment_after"] = write_document(directory, "environment-after.json", after)
        equal(source_identity(), bundle["source"], "controller source changed")
        summary["assessment"] = assess_case(directory, summary, selected=selected, bundle=bundle, bundle_sha256=args.bundle_sha256)
        summary["status"] = "success"
    except Exception as exc:
        summary.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    summary["cleanup_complete"] = cleanup_ok
    write_document(directory, "case-summary.json", signed(summary, "summary_sha256"))
    print(json.dumps({name: summary.get(name) for name in ("stage", "case_id", "status", "error")}, sort_keys=True))
    return 0 if summary["status"] == "success" else 1


def run_shard(args: argparse.Namespace) -> int:
    require(type(args.shard_id) is int and 0 <= args.shard_id < len(SHARDS), "unknown replay shard")
    require(not args.output_root.exists(), "shard output directory must be fresh")
    args.output_root.mkdir(parents=True)
    rows, stopped = [], False
    for case_id in SHARDS[args.shard_id]:
        call = argparse.Namespace(input_root=args.input_root, bundle_sha256=args.bundle_sha256, runtime_root=args.runtime_root,
            stage="replay", case_id=case_id, output_root=args.output_root / ("replay-" + case_id))
        code = run_case(call)
        summary = read_json(call.output_root / "case-summary.json")
        rows.append({"case_id": case_id, "exit_code": code, "summary": descriptor(args.output_root, "replay-" + case_id + "/case-summary.json")})
        if summary.get("cleanup_complete") is not True:
            stopped = True
            break
    report = {"schema_id": SCHEMA, "shard_id": args.shard_id, "case_ids": list(SHARDS[args.shard_id]),
        "bundle_sha256": args.bundle_sha256, "protocol_sha256": digest(PROTOCOL), "cases": rows, "stopped_after_cleanup_failure": stopped,
        "status": "success" if not stopped and len(rows) == len(SHARDS[args.shard_id]) and all(row["exit_code"] == 0 for row in rows) else "failed"}
    write_document(args.output_root, "shard-summary.json", signed(report, "shard_sha256"))
    return 0 if report["status"] == "success" else 1


def expected_case_stages(scope: str) -> set[tuple[str, str]]:
    require(scope in ("pilot", "all"), "unknown aggregate scope")
    if scope == "pilot":
        return {("replay", case) for case in PILOT_CASES}
    return {("replay", case) for case in inputs.CASE_IDS} | {("pipeline", case) for case in PILOT_CASES}


def aggregate(args: argparse.Namespace) -> int:
    bundle, manifest = load_bundle(args.input_root, args.bundle_sha256)
    equal(source_identity(), bundle["source"], "aggregator source checkout")
    environment = capture_environment(args.runtime_root)
    validate_environment(environment, bundle=bundle)
    expected, observed, failures = expected_case_stages(args.scope), {}, []
    for path in sorted(args.results_root.rglob("case-summary.json")):
        try:
            path = relative_file(args.results_root, path.relative_to(args.results_root).as_posix())
            summary = read_json(path)
            verify_signed(summary, "summary_sha256", "case summary")
            key = (summary["stage"], summary["case_id"])
            require(key in expected and key not in observed, "duplicate or unexpected case-stage summary")
            observed[key] = {"case_id": key[1], "stage": key[0], "status": "failed", "summary": descriptor(args.results_root, path.relative_to(args.results_root).as_posix())}
            require(summary["status"] == "success" and summary["cleanup_complete"] is True, "case summary did not pass resource/scientific gates")
            selected = selected_inputs(args.input_root, bundle, manifest, key[1], key[0])
            assessment = assess_case(path.parent, summary, selected=selected, bundle=bundle, bundle_sha256=args.bundle_sha256)
            equal(assessment, summary["assessment"], "recomputed exact case assessment")
            observed[key].update(status="success", assessment=assessment)
        except Exception as exc:
            failures.append({"path": path.relative_to(args.results_root).as_posix(), "error_type": type(exc).__name__, "error": str(exc)})
    missing = sorted(expected - set(observed))
    passed = not failures and not missing and len(observed) == len(expected)
    timing_groups = {}
    for row in observed.values():
        if row["status"] != "success":
            continue
        for pair in row["assessment"]["pairs"]:
            for timer, metrics in pair["metrics"].items():
                group = (row["stage"], pair["first_mode"], pair["second_mode"], timer)
                timing_groups.setdefault(group, []).append(metrics["saved_fraction"])
    timing = [{"stage": stage, "first_mode": first, "second_mode": second, "timer": timer, "case_count": len(values),
               "median_saved_fraction": statistics.median(values), "min_saved_fraction": min(values), "max_saved_fraction": max(values)}
              for (stage, first, second, timer), values in sorted(timing_groups.items())]
    report = {"schema_id": SCHEMA, "status": "success" if passed else "failed", "scope": args.scope,
        "protocol": PROTOCOL, "protocol_sha256": digest(PROTOCOL), "source": bundle["source"],
        "source_snapshot_sha256": bundle["source_snapshot_sha256"], "bundle_sha256": args.bundle_sha256,
        "environment_content_identity_sha256": environment["content_identity_sha256"],
        "fixed_case_denominator": 32, "successful_source_case_count": 29,
        "not_prepared": [{**row, "molecular_regression_exclusion_reason": "Original preparation failed with unsupported_large_ring_system; no original candidate/Top5 molecules exist. Case remains in the fixed32 denominator."} for row in manifest["not_prepared"]],
        "expected_case_stage_count": len(expected), "expected_worker_count": 3 * len(expected), "observed_case_stage_count": len(observed),
        "missing": [{"stage": stage, "case_id": case} for stage, case in missing], "failures": failures,
        "cases": [observed[key] for key in sorted(observed)], "timing_observations": timing,
        "performance_inference": PROTOCOL["performance_inference"],
        "claim_scope": "Exact behavior and timing observations on contaminated fixed development data; no improved docking accuracy, held-out generalization or primary claim."}
    isolation.atomic_json(args.output, signed(report, "aggregate_sha256"), replace=False)
    print(json.dumps({name: report[name] for name in ("status", "scope", "expected_case_stage_count", "observed_case_stage_count", "missing", "failures")}, sort_keys=True))
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    for name in ("artifact-root", "output-root", "runtime-root"):
        prep.add_argument("--" + name, required=True, type=Path)
    for name in ("worker", "run-case", "run-shard", "aggregate"):
        item = commands.add_parser(name)
        item.add_argument("--input-root", required=True, type=Path)
        item.add_argument("--bundle-sha256", required=True)
        item.add_argument("--runtime-root", required=True, type=Path)
        if name == "aggregate":
            item.add_argument("--scope", required=True, choices=("pilot", "all"))
            item.add_argument("--results-root", required=True, type=Path)
            item.add_argument("--output", required=True, type=Path)
        else:
            item.add_argument("--output-root", required=True, type=Path)
            if name == "run-shard":
                item.add_argument("--shard-id", required=True, type=int, choices=range(len(SHARDS)))
            else:
                item.add_argument("--stage", required=True, choices=("replay", "pipeline"))
                item.add_argument("--case-id", required=True, choices=inputs.CASE_IDS)
                if name == "worker":
                    item.add_argument("--mode", required=True, choices=MODES)
    args = parser.parse_args(argv)
    for name in ("artifact_root", "input_root", "runtime_root", "output_root", "results_root", "output"):
        if hasattr(args, name):
            setattr(args, name, getattr(args, name).absolute())
    if args.command == "prepare":
        print(json.dumps(prepare(args.artifact_root, args.output_root, args.runtime_root), sort_keys=True))
        return 0
    return {"worker": worker, "run-case": run_case, "run-shard": run_shard, "aggregate": aggregate}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
