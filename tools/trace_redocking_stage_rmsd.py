"""Replay retained stage coordinates with the frozen original RMSD module.

Preparation and aggregation require no molecular dependencies. Fresh bounded
workers use the original SDF round trip. All selected record hashes and RMSD
bits must match history before intermediate observations can be interpreted.
No search, scoring, optimization or physical-validity checks are introduced.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from numbers import Real
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import time

from tools import posebusters_integration_inputs as cohort
from tools import posebusters_replay_inputs as frozen
from tools import redocking_evidence_support as evidence
from tools import redocking_isolation as isolation
from tools import run_posebusters_replay as replay

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "betelgeuze.redocking_stage_rmsd/1.0.0"
INPUT_SCHEMA = "betelgeuze.redocking_stage_rmsd_inputs/1.0.0"
TRACE_SCHEMA = "betelgeuze.redocking_stage_coordinates/1.0.0"
STAGES = ("proposal_generated", "post_v6", "post_v7_optimization", "refinement_selected")
MEASUREMENT_ORDER = (STAGES[3], *STAGES[:3])
CASE_IDS = cohort.CASE_IDS
SHARDS = tuple(tuple(CASE_IDS[start:start+6]) for start in range(0, len(CASE_IDS), 6))
RMSD_PARAMETERS = {"rmsd_threshold": 2.0, "heavy_only": True, "choose_by": "rmsd"}
PROTOCOL = {
    "schema_id": SCHEMA, "source_run_id": frozen.SOURCE_RUN_ID,
    "source_execution_commit": frozen.SOURCE_COMMIT, "source_execution_tree": frozen.SOURCE_TREE,
    "fixed_case_order": cohort.FIXED_CASE_ORDER, "fixed_case_denominator": 32,
    "prepared_case_ids": list(CASE_IDS), "not_prepared_case_ids": [s[0] for s in cohort.NOT_PREPARED_SPECS],
    "shards": [list(cases) for cases in SHARDS], "candidate_count_per_prepared_case": 64,
    "stages": list(STAGES), "measurement_order": list(MEASUREMENT_ORDER),
    "expected_stage_observations": 7424, "required_selected_history_matches": 1856,
    "expected_same_case_unique_raw_coordinates": 3561,
    "rmsd_module": "posebusters.modules.rmsd.check_rmsd", "rmsd_parameters": RMSD_PARAMETERS,
    "coordinate_policy": "original seed topology; original _serialize_pose_records and _posebusters_molecules; final-score rank order at every stage",
    "decode_policy": {"predicted": {"sanitize": False, "removeHs": True, "strictParsing": True},
        "native": {"sanitize": False, "removeHs": False, "strictParsing": False,
                   "conformers": "original runner skips None and appends valid conformers"},
        "receptor": {"sanitize": False, "removeHs": False, "proximityBonding": False,
                     "AssignStereochemistryFrom3D": True}},
    "reuse_policy": "fresh per-case cache; exact canonical raw coordinates with the same native/seed/receptor/parameters/runtime; never historical RMSD values",
    "historical_gate": "all selected SDF record SHA256s AND selected RMSD binary64 bits; no tolerance",
    "wall_limit_seconds": 600, "rss_limit_bytes": 6 * 1024**3, "rss_sampling_seconds": 0.25,
    "log_limit_bytes": 8 * 1024**2,
    "log_limit_scope": "retained bytes per stdout/stderr stream; discarded bytes remain explicit",
    "fresh_process_per_case": True, "intermediate_physical_validity_measured": False,
    "search_or_scoring_changed": False, "native_information_used_for_search": False,
    "interpretation": "stage associations on observed development cases; no causal or held-out accuracy claim",
    "frozen_wheel_manifest_sha256": replay.WHEEL_MANIFEST,
    "frozen_wheel_set_sha256": replay.WHEEL_SET,
    "frozen_reference_environment_file_sha256": replay.REFERENCE_ENVIRONMENT_FILE,
}


class StageTraceError(ValueError):
    """Evidence is missing, ambiguous, changed, or fails a required gate."""


def require(condition, message):
    if not condition:
        raise StageTraceError(message)


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


canonical = isolation.canonical
digest = isolation.digest_json
relative_file = replay.relative_file
bound_file = replay.bound_file


def equal(left, right, label):
    require(canonical(left) == canonical(right), f"exact mismatch: {label}")


def read_json(path):
    return frozen._json(Path(path).read_bytes(), str(path))


def binary64(value, label="binary64"):
    require(type(value) is str, f"{label}: hexadecimal string required")
    try:
        decoded = float.fromhex(value)
    except (ValueError, OverflowError) as exc:
        raise StageTraceError(f"{label}: invalid value") from exc
    require(math.isfinite(decoded) and decoded.hex() == value, f"{label}: nonfinite/noncanonical value")
    return decoded


def coordinate_identity(coordinates):
    frozen._coordinates(coordinates)
    return digest({"schema_id": "betelgeuze.engine_v2_pose_coordinates/1.1.0", "coordinates": coordinates})


def file_descriptor(root, relative):
    path = relative_file(root, relative)
    return {"relative_path": relative, "sha256": isolation.digest_file(path), "size_bytes": path.stat().st_size}


def source_files():
    files = replay.source_files()
    for name in ("tools/trace_redocking_stage_rmsd.py", "tools/posebusters_integration_inputs.py"):
        files[name] = ROOT / name
    return files


def source_identity():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=30).strip()
    require(not git("status", "--porcelain", "--untracked-files=no"), "tracked source checkout is dirty")
    commit = git("rev-parse", "HEAD")
    require(not os.environ.get("GITHUB_SHA") or commit == os.environ["GITHUB_SHA"], "checkout differs from GitHub SHA")
    files = source_files()
    git("ls-files", "--error-unmatch", *sorted(files))
    return {"commit": commit, "tree": git("rev-parse", "HEAD^{tree}"), "protocol_sha256": digest(PROTOCOL),
            "source_files": {name: {"sha256": isolation.digest_file(path), "size_bytes": path.stat().st_size}
                             for name, path in sorted(files.items())}}


def validate_trace(trace, case):
    cid = case["case_id"]
    require(trace.get("schema_id") == TRACE_SCHEMA and trace.get("case_id") == cid and
            trace.get("source_run_id") == frozen.SOURCE_RUN_ID and
            trace.get("receipt_sha256") == case["receipt_sha256"] and
            trace.get("receipt_file_sha256") == case["receipt_file_sha256"], "trace/receipt binding differs")
    spec = next(s for s in cohort.CASE_SPECS if s[0] == cid)
    require(trace.get("source_global_index") == spec[3] and trace.get("frozen_case_seed") == spec[4], "trace index/seed differs")
    require(case["receipt_file_sha256"] == spec[5], "historical receipt is not the pinned source case")
    equal(trace["source_parameters"], {"candidate_count": 64, "output_pose_count": 5, "rmsd_threshold_angstrom": 2.0,
          "seed_base": 2026072700, "frozen_case_seed": spec[4]}, "original observation parameters")
    frozen._validate_source(trace.get("source"))
    equal(trace["input_sha256s"], {role: case[role]["sha256"] for role in frozen.ROLE_SUFFIXES}, "trace input identities")
    require(trace.get("source_evaluation_pipeline_sha256") == frozen.EVALUATION_PIPELINE_SHA256, "trace evaluator differs")
    rows = trace.get("candidates")
    require(type(rows) is list and len(rows) == 64 and [r.get("proposal_index") for r in rows] == list(range(64)),
            "trace proposal order/denominator differs")
    require(len({r.get("candidate_id") for r in rows}) == 64 and sorted(r.get("score_rank") for r in rows) == list(range(1, 65)),
            "trace candidate identities or ranks are ambiguous")
    ranked = {c["proposal_index"]: c for c in case["candidates_sorted"]}
    for row in rows:
        index = row["proposal_index"]
        require(type(index) is int and type(row["score_rank"]) is int and row["score_rank"] == ranked[index]["rank"], "rank differs")
        equal(row["historical_selected_rmsd_binary64_hex"], ranked[index]["legacy_outcome"]["rmsd_binary64_hex"], "historical RMSD")
        require(binary64(row["historical_selected_rmsd_binary64_hex"]) >= 0 and
                row["historical_selected_record_sha256"] == ranked[index]["expected_sdf_record_sha256"], "historical record differs")
        require(set(row["stages"]) == set(STAGES), "stage set is incomplete")
        for stage in STAGES:
            details = row["stages"][stage]["details"]
            require(details.get("candidate_id") == row["candidate_id"] and details.get("proposal_index") == index and
                    type(details.get("proposal_index")) is int and details.get("coordinate_unit") == "angstrom" and
                    details.get("coordinate_fingerprint_sha256") == coordinate_identity(details["coordinates_binary64"]),
                    "stage candidate/coordinate differs")
        selected = row["stages"][STAGES[3]]["details"]
        require(type(row.get("torsion_selected")) is bool and selected.get("torsion_selected") is row["torsion_selected"] and
                row.get("selected_branch") == (STAGES[2] if row["torsion_selected"] else STAGES[1]), "selected branch is ambiguous")
        equal(selected["coordinates_binary64"], row["stages"][row["selected_branch"]]["details"]["coordinates_binary64"], "selected branch coordinates")
        require(selected["parent_proposal_fingerprint_sha256"] == row["stages"][STAGES[0]]["details"]["proposal_fingerprint_sha256"],
                "selected proposal parent differs")


def _trace_from_archive(archive, case, spec):
    cid, key, case_root, index, seed, receipt_file_sha = spec
    engine = case_root + "/engines/engine_v2/"
    receipt, request = archive.document(engine + "receipt.json"), archive.document(engine + "request.json")
    materialization = archive.document(case_root + "/materialization/materialization.json")
    require(archive.inventory[engine + "receipt.json"]["sha256"] == receipt_file_sha == case["receipt_file_sha256"], "frozen receipt changed")
    require(materialization.get("frozen_case_seed") == seed == 2026072700 + index, "case seed changed")
    manifest = archive.document("development/run-manifest.json")
    equal(request["source"], manifest["source"], "original request/manifest source")
    require(manifest["candidate_count"] == 64 and manifest["output_pose_count"] == 5 and
            manifest["rmsd_threshold_angstrom"] == 2 and index in manifest["active_indices"] and
            manifest["case_ids"][index] == cid, "original stage parameters differ")
    candidates = {c["proposal_index"]: c for c in receipt["result"]["engine_v2_diagnostics"]["candidates"]}
    ranked = {c["proposal_index"]: c for c in case["candidates_sorted"]}
    require(set(candidates) == set(range(64)), "original proposal set changed")
    events, proof = frozen._verify_journal(archive, engine + "journal/", request=request,
        request_sha256=case["request_file_sha256"], receipt_sha256=case["receipt_sha256"], case_id=cid)
    equal(proof, case["journal"], "independent journal admission")
    stages = {stage: {} for stage in STAGES}
    for seq, event in enumerate(events, 1):
        stage = event.get("stage")
        if stage not in stages:
            continue
        detail = event.get("details", {})
        proposal = detail.get("proposal_index")
        require(event.get("phase") == "snapshot" and type(proposal) is int and proposal in candidates and proposal not in stages[stage],
                "missing/duplicate/ambiguous stage proposal")
        path = engine + f"journal/event-{seq:06d}.json"
        envelope = archive.document(path)
        stages[stage][proposal] = {"details": detail, "source_member": path,
            "source_member_sha256": archive.inventory[path]["sha256"], "event_sha256": envelope["event_sha256"], "journal_sequence": seq}
    require(all(set(items) == set(range(64)) for items in stages.values()), "stage coverage is not 64 × 4")
    rows = []
    for proposal in range(64):
        snapshots = {stage: stages[stage][proposal] for stage in STAGES}
        generated, selected = snapshots[STAGES[0]]["details"], snapshots[STAGES[3]]["details"]
        require(selected["coordinate_fingerprint_sha256"] == candidates[proposal]["coordinate_fingerprint_sha256"], "selected result differs")
        rows.append({"candidate_id": generated["candidate_id"], "proposal_index": proposal,
            "score_rank": ranked[proposal]["rank"], "score_binary64_hex": ranked[proposal]["score_binary64_hex"],
            "historical_selected_rmsd_binary64_hex": ranked[proposal]["legacy_outcome"]["rmsd_binary64_hex"],
            "historical_selected_record_sha256": ranked[proposal]["expected_sdf_record_sha256"],
            "torsion_selected": selected["torsion_selected"], "selected_branch": STAGES[2] if selected["torsion_selected"] else STAGES[1],
            "stages": snapshots})
    trace = {"schema_id": TRACE_SCHEMA, "case_id": cid, "source_global_index": index, "frozen_case_seed": seed,
        "source_run_id": frozen.SOURCE_RUN_ID, "source": request["source"], "artifact_key": key, "source_case_root": case_root,
        "receipt_sha256": case["receipt_sha256"], "receipt_file_sha256": receipt_file_sha, "journal": proof,
        "source_evaluation_pipeline_sha256": frozen.EVALUATION_PIPELINE_SHA256,
        "source_parameters": {"candidate_count": 64, "output_pose_count": 5, "rmsd_threshold_angstrom": 2.0,
                              "seed_base": manifest["seed_base"], "frozen_case_seed": seed},
        "input_sha256s": {role: case[role]["sha256"] for role in frozen.ROLE_SUFFIXES}, "candidates": rows}
    validate_trace(trace, case)
    return trace


def _not_prepared(archive, spec):
    cid, key, case_root, index, seed, file_sha = spec
    path = case_root + "/engines/engine_v2/receipt.json"
    require(archive.inventory[path]["sha256"] == file_sha, "not-prepared receipt changed")
    receipt = archive.document(path)
    receipt_sha = frozen._self_hash(receipt, "receipt_sha256", path)
    row, materialization = receipt["result"], archive.document(case_root + "/materialization/materialization.json")
    diagnostic = row["engine_v2_diagnostics"]
    require(row["case_id"] == cid and row["engine_id"] == "engine_v2" and row["status"] == "failure" and
            row["failure_code"] == "engine_v2_case_failed" and diagnostic["preparation_status"] == "failure" and
            diagnostic["preparation_failure_code"] == "unsupported_large_ring_system" and
            diagnostic["candidates"] == [] and materialization["frozen_case_seed"] == seed, "not-prepared outcome/seed differs")
    request = archive.document(case_root + "/engines/engine_v2/request.json")
    frozen._validate_source(request["source"])
    require(request["case_id"] == cid and request["global_index"] == index, "not-prepared request differs")
    return {"case_id": cid, "source_global_index": index, "frozen_case_seed": seed, "artifact_key": key,
        "status": "not_prepared", "candidate_count": 0, "failure_code": row["failure_code"],
        "preparation_failure_code": diagnostic["preparation_failure_code"],
        "receipt_sha256": receipt_sha, "receipt_file_sha256": file_sha}


def prepare(artifact_root, output_root):
    cohort.validate_fixed_cohort()
    artifact_root, output_root = frozen._no_symlink_path(Path(artifact_root)), frozen._no_symlink_path(Path(output_root))
    require(artifact_root.is_dir() and output_root.parent.is_dir() and not output_root.exists(), "preparation paths missing/output not fresh")
    source = source_identity()
    staging = Path(tempfile.mkdtemp(prefix=f".{output_root.name}-preparing-", dir=output_root.parent))
    try:
        cases, not_prepared, artifacts, unique = {}, [], [], 0
        for spec in cohort.ARTIFACT_SPECS:
            archive, _ = frozen._load_artifact(artifact_root, spec)
            try:
                artifacts.append(archive.summary)
                for case_spec in cohort.CASE_SPECS:
                    cid, key, case_root, index, seed, _ = case_spec
                    if key != spec.key:
                        continue
                    case = frozen._prepare_case(archive, case_id=cid, artifact_key=key, case_root=case_root,
                        global_index=index, staging=staging, final_root=output_root)
                    case["frozen_case_seed"] = seed
                    trace = _trace_from_archive(archive, case, case_spec)
                    case["stage_trace"] = frozen._write_file(staging, output_root, f"cases/{cid}/stage-trace.json", canonical(trace)+b"\n")
                    case["source_receipt"] = frozen._write_file(staging, output_root, f"cases/{cid}/source-receipt.json",
                        archive.read(case_root + "/engines/engine_v2/receipt.json"))
                    unique += len({canonical(r["stages"][s]["details"]["coordinates_binary64"]) for r in trace["candidates"] for s in STAGES})
                    cases[cid] = case
                not_prepared.extend(_not_prepared(archive, s) for s in cohort.NOT_PREPARED_SPECS if s[1] == spec.key)
            finally:
                archive.close()
        require(set(cases) == set(CASE_IDS) and len(not_prepared) == 3 and unique == 3561, "fixed cohort/coordinate coverage differs")
        manifest = {"schema_id": INPUT_SCHEMA, "source_run_id": frozen.SOURCE_RUN_ID,
            "source_execution_commit": frozen.SOURCE_COMMIT, "source_execution_tree": frozen.SOURCE_TREE,
            "fixed_case_order": cohort.FIXED_CASE_ORDER, "fixed_case_denominator": 32,
            "successful_case_count": 29, "not_prepared_case_count": 3,
            "source_evaluation_pipeline_sha256": frozen.EVALUATION_PIPELINE_SHA256,
            "source_environment_content_identity_sha256": frozen.ENVIRONMENT_CONTENT_IDENTITY_SHA256,
            "expected_stage_observations": 7424, "same_case_unique_raw_coordinates": unique,
            "molecular_evaluation_performed": False, "cases": [cases[cid] for cid in CASE_IDS],
            "not_prepared": sorted(not_prepared, key=lambda r: r["source_global_index"]), "artifacts": artifacts}
        frozen._write_file(staging, output_root, "manifest.json", canonical(manifest)+b"\n")
        files = [file_descriptor(staging, p.relative_to(staging).as_posix()) for p in sorted(staging.rglob("*")) if p.is_file()]
        equal(source_identity(), source, "source stability during preparation")
        isolation.atomic_json(staging / "bundle.json", {"schema_id": SCHEMA, "protocol": PROTOCOL,
            "source": source, "manifest": file_descriptor(staging, "manifest.json"), "files": files}, replace=False)
        require(not output_root.exists() and not output_root.is_symlink(), "preparation output appeared concurrently")
        staging.rename(output_root)
        return {"status": "success", "bundle_sha256": isolation.digest_file(output_root / "bundle.json"),
            "prepared_cases": 29, "not_prepared_cases": 3, "stage_observations": 7424,
            "same_case_unique_raw_coordinates": unique, "shards": [list(s) for s in SHARDS]}
    except BaseException:
        shutil.rmtree(staging)
        raise


def load_bundle(root, bundle_sha256):
    root = frozen._no_symlink_path(Path(root))
    path = relative_file(root, "bundle.json")
    require(isolation.digest_file(path) == bundle_sha256, "input bundle SHA256 differs")
    bundle = read_json(path)
    require(bundle.get("schema_id") == SCHEMA, "unexpected bundle schema")
    equal(bundle["protocol"], PROTOCOL, "stage RMSD protocol")
    files = bundle.get("files")
    require(type(files) is list and len({f["relative_path"] for f in files}) == len(files), "bundle inventory is ambiguous")
    for descriptor in files:
        bound_file(root, descriptor)
    observed = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "input bundle contains a symlink")
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
    equal(sorted(observed), sorted({f["relative_path"] for f in files} | {"bundle.json"}), "exact input bundle membership")
    manifest = frozen._json(bound_file(root, bundle["manifest"]), "manifest.json")
    require(manifest.get("schema_id") == INPUT_SCHEMA and manifest.get("fixed_case_denominator") == 32 and
            manifest.get("source_run_id") == frozen.SOURCE_RUN_ID, "unexpected fixed cohort manifest")
    equal(manifest["fixed_case_order"], cohort.FIXED_CASE_ORDER, "fixed development order")
    equal([c["case_id"] for c in manifest["cases"]], list(CASE_IDS), "prepared case order")
    equal([c["case_id"] for c in manifest["not_prepared"]], [s[0] for s in cohort.NOT_PREPARED_SPECS], "not-prepared order")
    for item, spec in zip(manifest["not_prepared"], cohort.NOT_PREPARED_SPECS):
        require(item["status"] == "not_prepared" and item["candidate_count"] == 0 and
                item["receipt_file_sha256"] == spec[5], "not-prepared case mutated")
    return bundle, manifest


def case_inputs(root, manifest, case_id):
    require(case_id in CASE_IDS, "case outside fixed prepared cohort")
    case = next(c for c in manifest["cases"] if c["case_id"] == case_id)
    trace = frozen._json(bound_file(root, case["stage_trace"]), "stage trace")
    validate_trace(trace, case)
    receipt_bytes = bound_file(root, case["source_receipt"])
    require(sha256(receipt_bytes) == case["receipt_file_sha256"], "retained receipt file differs")
    receipt = frozen._json(receipt_bytes, "source receipt")
    require(frozen._self_hash(receipt, "receipt_sha256", "source receipt") == case["receipt_sha256"], "retained receipt differs")
    inputs = {role: bound_file(root, case[role]) for role in frozen.ROLE_SUFFIXES}
    equal(receipt["input_sha256s"], {role: sha256(payload) for role, payload in inputs.items()}, "raw receipt input identities")
    raw_candidates = receipt["result"]["engine_v2_diagnostics"]["candidates"]
    require([r["proposal_index"] for r in raw_candidates] == list(range(64)), "raw receipt candidate coverage differs")
    for raw, row in zip(raw_candidates, trace["candidates"]):
        require(raw["status"] == "success" and row["historical_selected_record_sha256"] == raw["pose_artifact_sha256"] and
                row["historical_selected_rmsd_binary64_hex"] == float(raw["rmsd_angstrom"]).hex() and
                row["score_binary64_hex"] == float(raw["score"]).hex() and
                row["stages"][STAGES[3]]["details"]["coordinate_fingerprint_sha256"] == raw["coordinate_fingerprint_sha256"],
                "trace historical fields differ from the pinned raw receipt")
    return {"case": case, "trace": trace, "inputs": inputs,
        "input_ids": {"case_id": case_id, "frozen_case_seed": trace["frozen_case_seed"],
            "stage_trace_sha256": case["stage_trace"]["sha256"], "source_receipt_sha256": case["receipt_sha256"],
            **{role+"_sha256": sha256(payload) for role, payload in inputs.items()}}}


def capture_environment(runtime_root):
    runtime_root = frozen._no_symlink_path(Path(runtime_root))
    wheel = read_json(relative_file(runtime_root, "evaluator/wheelhouse-manifest.json"))
    require(wheel["manifest_sha256"] == replay.WHEEL_MANIFEST and wheel["wheel_set_sha256"] == replay.WHEEL_SET,
            "runtime wheel manifest is not frozen")
    path = relative_file(runtime_root, "reference-environment.json")
    require(isolation.digest_file(path) == replay.REFERENCE_ENVIRONMENT_FILE, "frozen reference environment differs")
    reference = read_json(path)
    snapshot = evidence.snapshot_environment(wheel["distributions"], source_files=source_files(), wheelhouse_manifest=wheel)
    equal(snapshot["versions"], reference["versions"], "frozen evaluator versions")
    equal({n: r["active_payload_sha256"] for n, r in snapshot["distributions"].items()},
          {n: r["active_payload_sha256"] for n, r in reference["distributions"].items()}, "frozen evaluator payloads")
    equal(evidence._runtime_projection(snapshot["runtime"]), evidence._runtime_projection(reference["runtime"]), "frozen Python runtime")
    return snapshot


def _runtime_for_rmsd():
    from importlib import import_module
    from tools import posebusters_replay_evaluator as evaluator
    runtime = evaluator._load_runtime()
    module, core = import_module("posebusters.modules.rmsd"), import_module("posebusters.posebusters")
    require(core.module_dict["rmsd"] is module.check_rmsd, "upstream RMSD callable differs")
    config = runtime.PoseBusters(config="redock", top_n=64).config
    modules = [m for m in config["modules"] if m["function"] == "rmsd"]
    require(len(modules) == 1, "RMSD module selection is ambiguous")
    equal(modules[0]["parameters"], {"rmsd_threshold": 2.0}, "frozen RMSD configuration")
    runtime.check_rmsd = module.check_rmsd
    runtime.molecule_sha256 = lambda mol: evaluator._molecule_sha256(mol, runtime.Chem)
    return runtime


def rmsd_record(value):
    require(isinstance(value, Real) and type(value) is not bool, "RMSD must be an evaluated real number")
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise StageTraceError("RMSD module did not produce a number") from exc
    require(math.isfinite(value) and value >= 0, "RMSD is nonfinite/missing/negative")
    return {"value": value, "binary64_hex": value.hex(), "binary64_be": struct.pack(">d", value).hex(),
            "near_native": value <= 2.0}


def validate_rmsd_record(record):
    value = binary64(record.get("binary64_hex"), "observed RMSD")
    require(value >= 0 and type(record.get("value")) is float and record["value"].hex() == value.hex() and
            record.get("binary64_be") == struct.pack(">d", value).hex() and
            type(record.get("near_native")) is bool and record["near_native"] == (value <= 2.0), "RMSD bits/threshold disagree")
    return value


def coordinate_tensor(coordinates, torch):
    count, _ = frozen._coordinates(coordinates)
    flat = [float.fromhex(x) for x in coordinates["values_hex"]]
    return torch.tensor([flat[i:i+3] for i in range(0, count*3, 3)], dtype=torch.float64, device="cpu")


def measure_case(selected, input_root, runtime=None):
    """Fresh molecular values; the history is used only as an equality gate."""
    import torch
    runtime = _runtime_for_rmsd() if runtime is None else runtime
    case, trace = selected["case"], selected["trace"]
    ranked = sorted(trace["candidates"], key=lambda r: r["score_rank"])
    seed_path = relative_file(input_root, case["seed"]["relative_path"])
    cache, observations = {}, {row["proposal_index"]: {} for row in ranked}
    immutable_checks, fresh_calls = 0, 0
    started = time.perf_counter_ns()
    for stage in MEASUREMENT_ORDER:
        coords = [r["stages"][stage]["details"]["coordinates_binary64"] for r in ranked]
        records = runtime.runner._serialize_pose_records(seed_path, [coordinate_tensor(c, torch) for c in coords], case_id=case["case_id"])
        require(len(records) == 64, "stage serialization lost candidates")
        if stage == STAGES[3]:
            equal([sha256(p) for p in records], [r["historical_selected_record_sha256"] for r in ranked], "all selected SDF record bytes")
            require(tuple(frozen.split_sdf_records(bound_file(input_root, case["top5"]))) == records[:5], "selected Top5 SDF differs")
        predicted, native, receptor = runtime.runner._posebusters_molecules(
            output_payload=b"".join(records), native_payload=selected["inputs"]["native"],
            receptor_payload=selected["inputs"]["receptor"], expected_pose_count=64)
        native_before, receptor_before = runtime.molecule_sha256(native), runtime.molecule_sha256(receptor)
        for row, coordinates, record, molecule in zip(ranked, coords, records, predicted):
            index = row["proposal_index"]
            fingerprint = row["stages"][stage]["details"]["coordinate_fingerprint_sha256"]
            coordinate_bytes = canonical(coordinates)
            cache_key, reused = (case["case_id"], fingerprint), None
            if cache_key in cache:
                prior = cache[cache_key]
                require(prior["coordinates"] == coordinate_bytes, "coordinate hash collision or ambiguous reuse")
                measured = deepcopy(prior["rmsd"])
                reused = {"case_id": case["case_id"], "proposal_index": prior["proposal_index"], "stage": prior["stage"]}
            else:
                before = runtime.molecule_sha256(molecule)
                raw = runtime.check_rmsd(mol_pred=molecule, mol_true=native, **RMSD_PARAMETERS)
                require(type(raw) is dict and type(raw.get("results")) is dict and "rmsd" in raw["results"], "RMSD result missing")
                measured = rmsd_record(raw["results"]["rmsd"])
                require(before == runtime.molecule_sha256(molecule), "RMSD mutated predicted molecule")
                immutable_checks += 1
                fresh_calls += 1
                cache[cache_key] = {"coordinates": coordinate_bytes, "rmsd": deepcopy(measured), "stage": stage, "proposal_index": index}
            observations[index][stage] = {"coordinate_fingerprint_sha256": fingerprint,
                "raw_coordinates_sha256": sha256(coordinate_bytes), "serialized_record_sha256": sha256(record),
                "rmsd": measured, "reused_from": reused, "physical_validity_measured": False}
        require(runtime.molecule_sha256(native) == native_before and runtime.molecule_sha256(receptor) == receptor_before,
                "RMSD changed a reference molecule")
        immutable_checks += 2
        if stage == STAGES[3]:
            mismatches = [r["proposal_index"] for r in ranked if observations[r["proposal_index"]][stage]["rmsd"]["binary64_hex"]
                          != r["historical_selected_rmsd_binary64_hex"]]
            require(not mismatches, f"selected historical RMSD gate failed for proposals {mismatches}; intermediate stages not admitted")
    rows = [{"candidate_id": row["candidate_id"], "proposal_index": row["proposal_index"], "score_rank": row["score_rank"],
             "stages": observations[row["proposal_index"]]} for row in trace["candidates"]]
    return {"rows": rows, "historical_selected_gate": {"passed": True, "sdf_record_matches": 64, "rmsd_binary64_matches": 64, "tolerance": None},
        "measurement_counts": {"stage_observations": 256, "fresh_rmsd_module_calls": fresh_calls,
            "same_case_exact_coordinate_reuses": 256-fresh_calls, "molecule_immutability_checks": immutable_checks},
        "timing_ns": {"molecular_stage_measurement": time.perf_counter_ns()-started},
        "upstream_source_sha256": runtime.source_hashes, "evaluator_versions": runtime.versions,
        "intermediate_physical_validity_measured": False, "input_ids": selected["input_ids"]}


def validate_measurement(result, selected):
    from tools.posebusters_replay_evaluator import UPSTREAM_SOURCE_SHA256
    equal(result["input_ids"], selected["input_ids"], "result scientific inputs")
    equal(result["upstream_source_sha256"], UPSTREAM_SOURCE_SHA256, "frozen RMSD source/helper bytes")
    equal(result["evaluator_versions"], selected["case"]["frozen_evaluator_versions"], "source evaluator versions")
    require(result.get("intermediate_physical_validity_measured") is False, "unexpected physical-validity claim")
    equal(result["historical_selected_gate"], {"passed": True, "sdf_record_matches": 64, "rmsd_binary64_matches": 64, "tolerance": None}, "selected history gate")
    rows, expected = result.get("rows"), selected["trace"]["candidates"]
    require(type(rows) is list and len(rows) == 64 and [r.get("proposal_index") for r in rows] == list(range(64)), "result proposal coverage/order differs")
    observed = {}
    for row, source in zip(rows, expected):
        require(row.get("candidate_id") == source["candidate_id"] and type(row.get("proposal_index")) is int and
                type(row.get("score_rank")) is int and row["score_rank"] == source["score_rank"] and
                set(row["stages"]) == set(STAGES), "result candidate/rank/stage identity differs")
        for stage in STAGES:
            measurement, details = row["stages"][stage], source["stages"][stage]["details"]
            require(measurement["coordinate_fingerprint_sha256"] == details["coordinate_fingerprint_sha256"] and
                    measurement["raw_coordinates_sha256"] == sha256(canonical(details["coordinates_binary64"])) and
                    measurement.get("physical_validity_measured") is False, "result coordinate/validity binding differs")
            require(type(measurement.get("serialized_record_sha256")) is str and
                    frozen._SHA.fullmatch(measurement["serialized_record_sha256"]), "invalid serialized record digest")
            validate_rmsd_record(measurement["rmsd"])
            observed[(row["proposal_index"], stage)] = measurement
        final = row["stages"][STAGES[3]]
        require(final["serialized_record_sha256"] == source["historical_selected_record_sha256"] and
                final["rmsd"]["binary64_hex"] == source["historical_selected_rmsd_binary64_hex"], "selected historical SDF/RMSD mismatch")
    seen, fresh, reused = {}, 0, 0
    ranked = sorted(expected, key=lambda r: r["score_rank"])
    for stage in MEASUREMENT_ORDER:
        for source in ranked:
            index = source["proposal_index"]
            record = observed[(index, stage)]
            key = canonical(source["stages"][stage]["details"]["coordinates_binary64"])
            origin = record.get("reused_from")
            if key not in seen:
                require(origin is None, "RMSD reuse predates a fresh same-case exact-coordinate observation")
                seen[key] = (index, stage)
                fresh += 1
            else:
                prior_index, prior_stage = seen[key]
                equal(origin, {"case_id": selected["case"]["case_id"], "proposal_index": prior_index, "stage": prior_stage}, "exact-coordinate cache origin")
                equal(record["rmsd"], observed[(prior_index, prior_stage)]["rmsd"], "reused measured RMSD")
                reused += 1
    counts = result["measurement_counts"]
    equal(counts, {"stage_observations": 256, "fresh_rmsd_module_calls": fresh,
        "same_case_exact_coordinate_reuses": reused, "molecule_immutability_checks": fresh+8}, "fresh/reused measurement counts")
    require(type(result["timing_ns"]["molecular_stage_measurement"]) is int and result["timing_ns"]["molecular_stage_measurement"] > 0, "invalid molecular timing")


TRANSITIONS = ((STAGES[0], STAGES[1]), (STAGES[1], STAGES[2]), (STAGES[2], STAGES[3]), (STAGES[0], STAGES[3]))


def stage_summary(rows):
    """Descriptive stage associations, only called after evidence gates pass."""
    near = {stage: [r["proposal_index"] for r in rows if validate_rmsd_record(r["stages"][stage]["rmsd"]) <= 2.0] for stage in STAGES}
    transitions = {}
    for before, after in TRANSITIONS:
        a, b = set(near[before]), set(near[after])
        transitions[before+"->"+after] = {"near_appeared": sorted(b-a), "near_lost": sorted(a-b),
                                        "near_retained": sorted(a & b), "far_retained_count": len(rows)-len(a | b)}
    return {"near_native_count": {stage: len(indices) for stage, indices in near.items()},
            "near_native_proposal_indices": near,
            "case_has_near_native": {stage: bool(indices) for stage, indices in near.items()},
            "transitions": transitions,
            "selection_drop_proposal_indices": transitions[STAGES[2]+"->"+STAGES[3]]["near_lost"],
            "case_had_prior_near_but_no_selected_near": any(near[s] for s in STAGES[:3]) and not near[STAGES[3]],
            "intermediate_physical_validity_measured": False,
            "causal_failure_stage_assigned": False}


def _valid_original_path(value):
    return (type(value) is str and value.startswith("/") and not value.startswith("//") and
            "\\" not in value and not any(ord(c) < 32 or ord(c) == 127 for c in value) and
            PurePosixPath(value).as_posix() == value and ".." not in PurePosixPath(value).parts)


def worker_command(request, request_sha256):
    context = request["execution_context"]
    require(set(context) == {"python_executable", "input_root", "output_root", "working_directory", "runtime_root"} and
            all(_valid_original_path(v) for v in context.values()), "original execution paths invalid")
    directory = PurePosixPath(context["output_root"]) / "cases" / request["case_id"]
    return [context["python_executable"], "-m", "tools.trace_redocking_stage_rmsd", "worker",
        "--input-root", context["input_root"], "--bundle-sha256", request["bundle_sha256"],
        "--case-id", request["case_id"], "--request", str(directory / "case-request.json"),
        "--request-sha256", request_sha256, "--output", str(directory / "result.json")]


def validate_execution(record, request, request_sha256, directory):
    require(record.get("schema_id") == "betelgeuze.redocking_process_execution/1.0.0", "execution receipt schema differs")
    claimed = record.get("control_sha256")
    require(digest({k: v for k, v in record.items() if k != "control_sha256"}) == claimed, "execution self hash differs")
    require(replay.execution_ok(record) and record.get("error") is None, "worker exit/resource/cleanup gate failed")
    equal(record["command"], worker_command(request, request_sha256), "worker argv")
    for field in ("wall_limit_seconds", "rss_limit_bytes", "rss_sampling_seconds"):
        require(type(record.get(field)) is type(PROTOCOL[field]) and record[field] == PROTOCOL[field], "worker resource protocol differs")
    peak = record.get("sampled_peak_process_tree_rss_bytes")
    require(type(peak) is int and 0 <= peak <= PROTOCOL["rss_limit_bytes"], "sampled RSS exceeds protocol")
    require(type(record.get("wall_seconds")) in (int, float) and math.isfinite(record["wall_seconds"]) and record["wall_seconds"] > 0 and
            type(record.get("child_cpu_seconds")) in (int, float) and math.isfinite(record["child_cpu_seconds"]) and record["child_cpu_seconds"] >= 0,
            "execution times invalid")
    streams = record.get("streams")
    require(type(streams) is dict and set(streams) == {"stdout", "stderr"}, "missing worker streams")
    for name, stream in streams.items():
        require(stream.get("path") == name+".log" and stream.get("eof_observed") is True, "stream path/completion differs")
        data = relative_file(directory, stream["path"]).read_bytes()
        require(all(type(stream.get(k)) is int and stream[k] >= 0 for k in ("bytes_seen", "bytes_retained", "bytes_discarded")) and
                len(data) == stream["bytes_retained"] <= PROTOCOL["log_limit_bytes"] and
                stream["bytes_seen"] == stream["bytes_retained"] + stream["bytes_discarded"] and
                type(stream.get("truncated")) is bool and stream["truncated"] == (stream["bytes_discarded"] > 0) and
                sha256(data) == stream["retained_sha256"], "stream size/hash/log-limit binding differs")


def validate_request(request, *, selected, bundle, bundle_sha256):
    require(request.get("schema_id") == SCHEMA and request.get("kind") == "case_request" and
            request.get("case_id") == selected["case"]["case_id"] and
            request.get("bundle_sha256") == bundle_sha256 and request.get("protocol_sha256") == digest(PROTOCOL), "case request protocol differs")
    shard = request.get("shard_id")
    require(type(shard) is int and 0 <= shard < len(SHARDS) and request["case_id"] in SHARDS[shard], "case request shard differs")
    equal(request["source"], bundle["source"], "case request source")
    equal(request["input_ids"], selected["input_ids"], "case request input identity")
    require(request["runtime_identity_sha256"] == digest(request["runtime_identity"]), "request runtime digest differs")
    worker_command(request, "0"*64)


def validate_result(result, *, selected, request, request_sha256):
    require(result.get("schema_id") == SCHEMA and result.get("kind") == "case_result" and
            result.get("status") == "success" and result.get("case_id") == request["case_id"], "worker result did not pass")
    require(digest({k: v for k, v in result.items() if k != "receipt_sha256"}) == result.get("receipt_sha256"), "worker result self hash differs")
    require(result.get("request_sha256") == request_sha256 and result.get("bundle_sha256") == request["bundle_sha256"] and
            result.get("protocol_sha256") == request["protocol_sha256"] and
            result.get("environment_before_sha256") == request["environment_before"]["sha256"] and
            result.get("environment_content_identity_sha256") == request["environment_content_identity_sha256"], "worker request/environment binding differs")
    equal(result["source"], request["source"], "worker source")
    equal(result["runtime_identity"], request["runtime_identity"], "worker Python runtime")
    require(result.get("input_files_unchanged") is True, "worker input immutability not established")
    validate_measurement(result, selected)
    equal(result["stage_summary"], stage_summary(result["rows"]), "recomputed case stage summary")


def worker(args):
    result = {"schema_id": SCHEMA, "kind": "case_result", "status": "failed", "case_id": args.case_id,
              "request_sha256": args.request_sha256, "bundle_sha256": args.bundle_sha256,
              "protocol_sha256": digest(PROTOCOL), "intermediate_physical_validity_measured": False}
    try:
        bundle, manifest = load_bundle(args.input_root, args.bundle_sha256)
        equal(source_identity(), bundle["source"], "worker source checkout")
        require(isolation.digest_file(frozen._no_symlink_path(args.request)) == args.request_sha256, "worker request file SHA differs")
        request = read_json(args.request)
        selected = case_inputs(args.input_root, manifest, args.case_id)
        validate_request(request, selected=selected, bundle=bundle, bundle_sha256=args.bundle_sha256)
        context = request["execution_context"]
        require(str(args.input_root) == context["input_root"] and str(args.output) ==
                str(PurePosixPath(context["output_root"]) / "cases" / args.case_id / "result.json") and
                str(args.request) == str(PurePosixPath(context["output_root"]) / "cases" / args.case_id / "case-request.json") and
                str(ROOT) == context["working_directory"] and str(Path(sys.executable).absolute()) == context["python_executable"],
                "worker parsed paths differ from request")
        runtime_identity = evidence._runtime_projection(evidence._runtime())
        equal(runtime_identity, request["runtime_identity"], "worker runtime before molecular imports")
        before_path = relative_file(Path(context["output_root"]), request["environment_before"]["relative_path"])
        require(isolation.digest_file(before_path) == request["environment_before"]["sha256"], "worker environment report differs")
        measured = measure_case(selected, args.input_root)
        validate_measurement(measured, selected)
        equal(case_inputs(args.input_root, manifest, args.case_id)["input_ids"], selected["input_ids"], "inputs after measurement")
        equal(source_identity(), bundle["source"], "source after measurement")
        equal(evidence._runtime_projection(evidence._runtime()), runtime_identity, "worker runtime after measurement")
        result.update(measured, status="success", source=bundle["source"], runtime_identity=runtime_identity,
            environment_before_sha256=request["environment_before"]["sha256"],
            environment_content_identity_sha256=request["environment_content_identity_sha256"],
            input_files_unchanged=True, stage_summary=stage_summary(measured["rows"]))
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc), intermediate_inference_allowed=False)
    result["receipt_sha256"] = digest(result)
    isolation.atomic_json(args.output, result, replace=False)
    return 0 if result["status"] == "success" else 1


def assess_case(directory, observation, *, selected, bundle, bundle_sha256, before):
    cid = selected["case"]["case_id"]
    require(observation["case_id"] == cid and observation["request"]["relative_path"] == f"cases/{cid}/case-request.json" and
            observation["result"]["relative_path"] == f"cases/{cid}/result.json" and
            observation["execution"]["relative_path"] == f"cases/{cid}/worker/process-execution.json", "case evidence paths differ")
    request = frozen._json(bound_file(directory, observation["request"]), "case request")
    validate_request(request, selected=selected, bundle=bundle, bundle_sha256=bundle_sha256)
    equal(request["environment_before"], file_descriptor(directory, "environment-before.json"), "request environment report")
    require(request["environment_content_identity_sha256"] == before["content_identity_sha256"], "case environment content differs")
    equal(request["runtime_identity"], evidence._runtime_projection(before["runtime"]), "request runtime")
    execution = frozen._json(bound_file(directory, observation["execution"]), "execution receipt")
    validate_execution(execution, request, observation["request"]["sha256"], directory / f"cases/{cid}/worker")
    result = frozen._json(bound_file(directory, observation["result"]), "worker result")
    validate_result(result, selected=selected, request=request, request_sha256=observation["request"]["sha256"])
    return result


def run_shard(args):
    require(type(args.shard_id) is int and 0 <= args.shard_id < len(SHARDS), "invalid shard")
    directory = frozen._no_symlink_path(args.output_root)
    input_root = frozen._no_symlink_path(args.input_root)
    runtime_root = frozen._no_symlink_path(args.runtime_root)
    require(not directory.exists() and not directory.is_relative_to(input_root) and not directory.is_relative_to(runtime_root),
            "shard output must be fresh and outside immutable inputs/runtime")
    directory.mkdir(parents=True)
    summary = {"schema_id": SCHEMA, "kind": "shard_summary", "status": "failed", "shard_id": args.shard_id,
        "case_ids": list(SHARDS[args.shard_id]), "bundle_sha256": args.bundle_sha256,
        "protocol_sha256": digest(PROTOCOL), "observations": [],
        "execution_context": {"python_executable": str(Path(sys.executable).absolute()), "input_root": str(input_root),
            "output_root": str(directory), "runtime_root": str(runtime_root), "working_directory": str(ROOT)},
        "job": {k: os.environ.get(k) for k in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "RUNNER_OS", "RUNNER_ARCH")},
        "host": {"platform": platform.platform(), "cpu_count": os.cpu_count()}}
    try:
        bundle, manifest = load_bundle(input_root, args.bundle_sha256)
        equal(source_identity(), bundle["source"], "controller source checkout")
        summary["source"] = bundle["source"]
        reference_payload = relative_file(runtime_root, "reference-environment.json").read_bytes()
        require(sha256(reference_payload) == replay.REFERENCE_ENVIRONMENT_FILE, "frozen reference file differs")
        with (directory / "frozen-reference-environment.json").open("xb") as target:
            target.write(reference_payload)
        summary["frozen_reference_environment"] = file_descriptor(directory, "frozen-reference-environment.json")
        before = capture_environment(runtime_root)
        isolation.atomic_json(directory / "environment-before.json", before, replace=False)
        summary["environment_before"] = file_descriptor(directory, "environment-before.json")
        for cid in SHARDS[args.shard_id]:
            selected = case_inputs(input_root, manifest, cid)
            case_dir = directory / "cases" / cid
            case_dir.mkdir(parents=True)
            request = {"schema_id": SCHEMA, "kind": "case_request", "case_id": cid, "shard_id": args.shard_id,
                "bundle_sha256": args.bundle_sha256, "protocol_sha256": digest(PROTOCOL), "source": bundle["source"],
                "input_ids": selected["input_ids"], "execution_context": summary["execution_context"],
                "environment_before": summary["environment_before"], "environment_content_identity_sha256": before["content_identity_sha256"],
                "runtime_identity": evidence._runtime_projection(before["runtime"])}
            request["runtime_identity_sha256"] = digest(request["runtime_identity"])
            isolation.atomic_json(case_dir / "case-request.json", request, replace=False)
            request_descriptor = file_descriptor(directory, f"cases/{cid}/case-request.json")
            command = worker_command(request, request_descriptor["sha256"])
            execution = isolation.supervise(command, case_dir / "worker", isolation.Limits(
                wall_seconds=PROTOCOL["wall_limit_seconds"], rss_bytes=PROTOCOL["rss_limit_bytes"],
                poll_seconds=PROTOCOL["rss_sampling_seconds"], log_bytes=PROTOCOL["log_limit_bytes"]), cwd=ROOT, env=dict(os.environ))
            observation = {"case_id": cid, "request": request_descriptor,
                "execution": file_descriptor(directory, f"cases/{cid}/worker/process-execution.json"),
                "result": file_descriptor(directory, f"cases/{cid}/result.json") if (case_dir / "result.json").is_file() else None,
                "process_gate_passed": replay.execution_ok(execution)}
            summary["observations"].append(observation)
            isolation.atomic_json(directory / "progress.json", summary)
        after = capture_environment(runtime_root)
        isolation.atomic_json(directory / "environment-after.json", after, replace=False)
        summary["environment_after"] = file_descriptor(directory, "environment-after.json")
        equal(before["content_identity_sha256"], after["content_identity_sha256"], "same-node environment before/after")
        require(evidence.compare_environments(before, after)["matches"], "same-node runtime payload changed")
        for observation in summary["observations"]:
            assess_case(directory, observation, selected=case_inputs(input_root, manifest, observation["case_id"]),
                        bundle=bundle, bundle_sha256=args.bundle_sha256, before=before)
        equal(source_identity(), bundle["source"], "controller source after workers")
        summary["status"] = "success"
    except Exception as exc:
        summary.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    summary["receipt_sha256"] = digest(summary)
    isolation.atomic_json(directory / "shard-summary.json", summary, replace=False)
    print(json.dumps({"status": summary["status"], "shard_id": args.shard_id,
                      "observed_cases": len(summary["observations"]), "error": summary.get("error")}))
    return 0 if summary["status"] == "success" else 1


def validate_environment(snapshot, reference, bundle):
    evidence._validate_environment(snapshot)
    equal(snapshot["versions"], reference["versions"], "retained frozen versions")
    equal({n: r["active_payload_sha256"] for n, r in snapshot["distributions"].items()},
          {n: r["active_payload_sha256"] for n, r in reference["distributions"].items()}, "retained frozen installed payloads")
    equal(evidence._runtime_projection(snapshot["runtime"]), evidence._runtime_projection(reference["runtime"]), "retained frozen Python")
    equal({r["path"]: {"sha256": r["sha256"], "size_bytes": r["size"]} for r in snapshot["source_files"]},
          bundle["source"]["source_files"], "environment executed source files")
    require(snapshot["wheel_manifest_sha256"] == replay.WHEEL_MANIFEST and snapshot["wheel_set_sha256"] == replay.WHEEL_SET,
            "retained frozen wheel identities differ")


def combine_stage_summaries(results):
    require(set(results) == set(CASE_IDS), "all 29 case gates are required before stage aggregation")
    summaries = {cid: stage_summary(results[cid]["rows"]) for cid in CASE_IDS}
    per_stage = {stage: {"near_native_candidates": sum(s["near_native_count"][stage] for s in summaries.values()),
        "case_oracle_count": sum(s["case_has_near_native"][stage] for s in summaries.values()),
        "fixed_case_denominator": 32, "evaluated_candidate_denominator": 1856,
        "case_ids_with_near_native": [cid for cid in CASE_IDS if summaries[cid]["case_has_near_native"][stage]]} for stage in STAGES}
    transitions = {}
    for before, after in TRANSITIONS:
        key = before+"->"+after
        transitions[key] = {"candidate_near_appeared": sum(len(s["transitions"][key]["near_appeared"]) for s in summaries.values()),
            "candidate_near_lost": sum(len(s["transitions"][key]["near_lost"]) for s in summaries.values()),
            "candidate_near_retained": sum(len(s["transitions"][key]["near_retained"]) for s in summaries.values()),
            "candidate_far_retained": sum(s["transitions"][key]["far_retained_count"] for s in summaries.values()),
            "case_near_appeared": [cid for cid, s in summaries.items() if not s["case_has_near_native"][before] and s["case_has_near_native"][after]],
            "case_near_lost": [cid for cid, s in summaries.items() if s["case_has_near_native"][before] and not s["case_has_near_native"][after]]}
    return {"stages": per_stage, "transitions": transitions,
        "selection_drop_candidates": sum(len(s["selection_drop_proposal_indices"]) for s in summaries.values()),
        "cases_with_any_selection_drop": [cid for cid, s in summaries.items() if s["selection_drop_proposal_indices"]],
        "cases_with_prior_near_but_no_selected_near": [cid for cid, s in summaries.items() if s["case_had_prior_near_but_no_selected_near"]],
        "case_summaries": summaries, "intermediate_physical_validity_measured": False,
        "causal_failure_stage_assigned": False}


def aggregate(args):
    input_root = frozen._no_symlink_path(args.input_root)
    results_root = frozen._no_symlink_path(args.results_root)
    output = frozen._no_symlink_path(args.output)
    require(results_root.is_dir() and not output.exists() and not output.is_relative_to(input_root), "aggregate paths invalid")
    require(all(not path.is_symlink() for path in results_root.rglob("*")), "result artifacts contain a symlink")
    bundle, manifest = load_bundle(input_root, args.bundle_sha256)
    equal(source_identity(), bundle["source"], "aggregate source checkout")
    found, results, failures, shard_proofs = set(), {}, [], []
    for path in sorted(results_root.rglob("shard-summary.json")):
        try:
            path = frozen._no_symlink_path(path)
            summary = read_json(path)
            shard = summary.get("shard_id")
            require(type(shard) is int and 0 <= shard < len(SHARDS) and shard not in found, "duplicate/unexpected shard summary")
            found.add(shard)
            require(summary.get("schema_id") == SCHEMA and summary.get("kind") == "shard_summary" and
                    summary.get("bundle_sha256") == args.bundle_sha256 and summary.get("protocol_sha256") == digest(PROTOCOL), "shard protocol differs")
            require(digest({k: v for k, v in summary.items() if k != "receipt_sha256"}) == summary.get("receipt_sha256"), "shard self hash differs")
            equal(summary["source"], bundle["source"], "shard source")
            equal(summary["case_ids"], list(SHARDS[shard]), "shard assigned cases")
            equal([o["case_id"] for o in summary["observations"]], list(SHARDS[shard]), "shard observed case order")
            reference_bytes = bound_file(path.parent, summary["frozen_reference_environment"])
            require(sha256(reference_bytes) == replay.REFERENCE_ENVIRONMENT_FILE, "retained frozen environment reference differs")
            reference = frozen._json(reference_bytes, "frozen reference")
            before = frozen._json(bound_file(path.parent, summary["environment_before"]), "environment before")
            after = frozen._json(bound_file(path.parent, summary["environment_after"]), "environment after")
            validate_environment(before, reference, bundle)
            validate_environment(after, reference, bundle)
            require(evidence.compare_environments(before, after)["matches"], "shard environment changed")
            require(summary.get("status") == "success", "shard controller did not pass")
            for observation in summary["observations"]:
                cid = observation["case_id"]
                require(cid not in results and observation.get("process_gate_passed") is True, "duplicate case/failed process gate")
                selected = case_inputs(input_root, manifest, cid)
                result = assess_case(path.parent, observation, selected=selected, bundle=bundle,
                                     bundle_sha256=args.bundle_sha256, before=before)
                request = frozen._json(bound_file(path.parent, observation["request"]), "request")
                require(request["shard_id"] == shard, "case request assigned to another shard")
                equal(request["execution_context"], summary["execution_context"], "case/shard execution context")
                results[cid] = result
            shard_proofs.append({"shard_id": shard, "summary_path": str(path), "summary_sha256": isolation.digest_file(path),
                                 "environment_content_identity_sha256": before["content_identity_sha256"]})
        except Exception as exc:
            failures.append({"path": str(path), "error_type": type(exc).__name__, "error": str(exc)})
    missing_shards, missing_cases = sorted(set(range(5))-found), [cid for cid in CASE_IDS if cid not in results]
    success = not failures and not missing_shards and not missing_cases and len(results) == 29
    if success:
        totals = Counter()
        for result in results.values():
            totals.update(result["measurement_counts"])
        require(totals["stage_observations"] == 7424 and totals["fresh_rmsd_module_calls"] == 3561 and
                totals["same_case_exact_coordinate_reuses"] == 3863, "whole-cohort observation/reuse denominator differs")
    report = {"schema_id": SCHEMA, "kind": "aggregate", "status": "success" if success else "failed",
        "protocol": PROTOCOL, "source": bundle["source"], "bundle_sha256": args.bundle_sha256,
        "fixed_case_denominator": 32, "expected_prepared_cases": 29, "validated_prepared_cases": len(results),
        "not_prepared_cases": manifest["not_prepared"], "missing_shards": missing_shards,
        "cases_without_validated_measurement": missing_cases, "failures": failures, "shards": shard_proofs,
        "validated_selected_history_matches": 64*len(results), "required_selected_history_matches": 1856,
        "intermediate_inference_allowed": success, "measurement_counts": dict(totals) if success else None,
        "stage_summary": combine_stage_summaries(results) if success else None,
        "case_result_receipts": {cid: results[cid]["receipt_sha256"] for cid in CASE_IDS if cid in results},
        "intermediate_physical_validity_measured": False, "search_or_scoring_changed": False,
        "interpretation": PROTOCOL["interpretation"]}
    report["receipt_sha256"] = digest(report)
    isolation.atomic_json(output, report, replace=False)
    print(json.dumps({"status": report["status"], "validated_prepared_cases": len(results),
        "selected_history_matches": report["validated_selected_history_matches"], "intermediate_inference_allowed": success,
        "failures": failures, "missing_shards": missing_shards}, sort_keys=True))
    return 0 if success else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--artifact-root", type=Path, required=True)
    prep.add_argument("--output-root", type=Path, required=True)
    for name in ("worker", "run-shard", "aggregate"):
        item = commands.add_parser(name)
        item.add_argument("--input-root", type=Path, required=True)
        item.add_argument("--bundle-sha256", required=True)
        if name == "worker":
            item.add_argument("--case-id", choices=CASE_IDS, required=True)
            item.add_argument("--request", type=Path, required=True)
            item.add_argument("--request-sha256", required=True)
            item.add_argument("--output", type=Path, required=True)
        elif name == "run-shard":
            item.add_argument("--shard-id", type=int, choices=range(5), required=True)
            item.add_argument("--output-root", type=Path, required=True)
            item.add_argument("--runtime-root", type=Path, required=True)
        else:
            item.add_argument("--results-root", type=Path, required=True)
            item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        print(json.dumps(prepare(args.artifact_root, args.output_root), sort_keys=True))
        return 0
    if args.command == "worker":
        return worker(args)
    if args.command == "run-shard":
        return run_shard(args)
    return aggregate(args)


if __name__ == "__main__":
    raise SystemExit(main())
