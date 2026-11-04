"""Bounded, exact-equivalence replay of saved development poses (no docking).

Profile timing is diagnostic only. Performance pairs use fresh processes on
one node. Historical raw energy scalars were not retained: compare those with
a newly captured baseline, not an invented historical report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import statistics
import struct
import subprocess
import sys
from typing import Any

from tools import redocking_evidence_support as evidence
from tools import redocking_isolation as isolation
from tools import posebusters_replay_inputs as inputs

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "betelgeuze.posebusters_replay/1.0.0"
PILOT_CASES = tuple(row[0] for row in inputs.CASE_SPECS)
EXPANDED_CASES = ("6YSP_PAL", "6T88_MWQ")
WHEEL_MANIFEST = "6688cb744017878f035a3a70c369d8e30031861560a786a639f4732bde7e28b6"
WHEEL_SET = "47f139ad43d54f34e1163562d50d1ff7f54a5a0604880c9cca9c3565a294fb5c"
REFERENCE_ENVIRONMENT_FILE = "860066f496592ebd68897e6d0480749c3f049d5ea364945c3c49ec57a974191d"
PROTOCOL = {
    "schema_id": SCHEMA, "source_run_id": inputs.SOURCE_RUN_ID,
    "pilot_cases": list(PILOT_CASES), "expanded_cases": list(EXPANDED_CASES),
    "pilot_record_count": 5, "expanded_record_count": 64,
    "pilot_order": ["baseline", "prepared_receptor", "prepared_receptor", "baseline", "profile"],
    "expanded_order": ["baseline", "prepared_receptor"],
    "pilot_pairs": [[0, 1], [3, 2]], "expanded_pairs": [[0, 1]],
    "performance_pair_metrics": ["posebusters_ns", "end_to_end_ns", "supervisor_wall_seconds"],
    "profile_is_diagnostic_only": True,
    "fresh_process_per_evaluation": True, "energy_cache_cleared_in_each_worker": True,
    "wall_limit_seconds": {"pilot": 900, "expanded": 1200},
    "rss_limit_bytes": 6 * 1024**3, "rss_sampling_seconds": 0.25,
    "log_limit_bytes": 8 * 1024**2,
    "equivalence": "all ordered full-report cells, scalar types, binary64 bits, NA semantics, dtypes and columns; historical RMSD/validity/failed IDs",
    "historical_raw_report_available": False, "numerical_tolerance": None,
    "selection": "fixed development cases including three joint-valid Top5 poses in 6T88_MWQ",
    "claim_scope": "saved-pose development replay; no docking accuracy or held-out generalization claim",
    "default_runner_changed": False, "new_docking_performed": False,
}


class ReplayProtocolError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayProtocolError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path) -> Any:
    return inputs._json(Path(path).read_bytes(), str(path))


def equal(left: Any, right: Any, label: str) -> None:
    # Python container equality considers True == 1. Canonical JSON does not.
    require(canonical(left) == canonical(right), f"exact mismatch: {label}")


def relative_file(root: Path, relative: str) -> Path:
    inputs._safe_member_name(relative)
    root = inputs._no_symlink_path(root)
    path = inputs._no_symlink_path(root / relative)
    require(path.is_file() and path.is_relative_to(root), f"missing/unsafe input: {relative}")
    return path


def bound_file(root: Path, descriptor: dict) -> bytes:
    payload = relative_file(root, descriptor["relative_path"]).read_bytes()
    require(type(descriptor["size_bytes"]) is int and len(payload) == descriptor["size_bytes"], "input size mismatch")
    require(hashlib.sha256(payload).hexdigest() == descriptor["sha256"], "input SHA256 mismatch")
    return payload


def source_identity() -> dict:
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=30).strip()
    require(not git("status", "--porcelain", "--untracked-files=no"), "tracked source files are dirty")
    commit = git("rev-parse", "HEAD")
    if os.environ.get("GITHUB_SHA"):
        require(commit == os.environ["GITHUB_SHA"], "checkout is not the requested GitHub SHA")
    return {"commit": commit, "tree": git("rev-parse", "HEAD^{tree}"), "protocol_sha256": digest(PROTOCOL)}


def source_files() -> dict[str, Path]:
    names = ["tools/run_posebusters_replay.py", "tools/posebusters_replay_inputs.py",
             "tools/posebusters_replay_evaluator.py", "tools/redocking_isolation.py",
             "tools/redocking_evidence_support.py", "tools/redocking_lineage_validation.py",
             "tools/run_engine_v2_public_redocking_300.py", "tools/redocking_development_p1.py"]
    files = {name: ROOT / name for name in names}
    for path in sorted((ROOT / "betelgeuze_engine_v2").rglob("*.py")):
        files[path.relative_to(ROOT).as_posix()] = path
    return files


def prepare(artifact_root: Path, output_root: Path) -> dict:
    manifest = inputs.prepare_cases(artifact_root, output_root)
    # Exact bytes are mandatory, even if reconstructed poses look equivalent.
    import torch
    from tools.run_engine_v2_public_redocking_300 import _serialize_pose_records
    reconstructions = []
    for case in manifest["cases"]:
        coordinates = []
        for item in case["candidates_sorted"]:
            path = relative_file(output_root, item["coordinates_relative_path"])
            require(isolation.digest_file(path) == item["coordinate_sha256"], "coordinate SHA256 mismatch")
            document = read_json(path)
            require(document["shape"] == [item["coordinate_count"], 3], "coordinate shape mismatch")
            flat_values = [float.fromhex(value) for value in document["values_hex"]]
            require(len(flat_values) == item["coordinate_count"] * 3, "coordinate denominator mismatch")
            values = [flat_values[index:index + 3] for index in range(0, len(flat_values), 3)]
            require(all(math.isfinite(value) for row in values for value in row), "nonfinite coordinate")
            coordinates.append(torch.tensor(values, dtype=torch.float64, device="cpu"))
        bound_file(output_root, case["seed"])
        records = _serialize_pose_records(relative_file(output_root, case["seed"]["relative_path"]),
                                          coordinates, case_id=case["case_id"])
        expected = [item["expected_sdf_record_sha256"] for item in case["candidates_sorted"]]
        equal([hashlib.sha256(record).hexdigest() for record in records], expected,
              f"all reconstructed record bytes: {case['case_id']}")
        require(records[:5] == tuple(inputs.split_sdf_records(bound_file(output_root, case["top5"]))),
                "reconstructed Top5 differs from retained records")
        relative = f"cases/{case['case_id']}/candidates64.sdf"
        path = output_root / relative
        with path.open("xb") as target:
            target.write(b"".join(records))
        reconstructions.append({"case_id": case["case_id"], "relative_path": relative,
            "sha256": isolation.digest_file(path), "size_bytes": path.stat().st_size,
            "record_count": 64, "record_sha256s": expected, "template_role": "seed",
            "all_original_record_sha256s_match": True})
    bundle = {"schema_id": SCHEMA, "protocol": PROTOCOL, "source": source_identity(),
              "manifest_sha256": isolation.digest_file(output_root / "manifest.json"),
              "reconstructions": reconstructions}
    isolation.atomic_json(output_root / "bundle.json", bundle, replace=False)
    return {"bundle_sha256": isolation.digest_file(output_root / "bundle.json"),
            "case_count": len(reconstructions), "reconstructed_record_count": 384}


def load_bundle(root: Path, bundle_sha256: str) -> tuple[dict, dict]:
    path = relative_file(root, "bundle.json")
    require(isolation.digest_file(path) == bundle_sha256, "prepared bundle SHA256 mismatch")
    bundle = read_json(path)
    equal(bundle["protocol"], PROTOCOL, "frozen replay protocol")
    manifest_path = relative_file(root, "manifest.json")
    require(isolation.digest_file(manifest_path) == bundle["manifest_sha256"], "input manifest SHA256 mismatch")
    manifest = read_json(manifest_path)
    require(manifest["schema_id"] == inputs.SCHEMA_ID and manifest["source_run_id"] == inputs.SOURCE_RUN_ID,
            "unexpected source input manifest")
    equal([case["case_id"] for case in manifest["cases"]], list(PILOT_CASES), "fixed replay cohort")
    equal([case["case_id"] for case in bundle["reconstructions"]], list(PILOT_CASES), "reconstruction cohort")
    return bundle, manifest


def selected_inputs(root: Path, bundle: dict, manifest: dict, case_id: str, stage: str) -> dict:
    require(stage in ("pilot", "expanded"), "unsupported stage")
    require(case_id in (PILOT_CASES if stage == "pilot" else EXPANDED_CASES), "case outside fixed stage")
    case = next(row for row in manifest["cases"] if row["case_id"] == case_id)
    descriptor = case["top5"] if stage == "pilot" else next(row for row in bundle["reconstructions"] if row["case_id"] == case_id)
    records = tuple(inputs.split_sdf_records(bound_file(root, descriptor)))
    require(len(records) == PROTOCOL[f"{stage}_record_count"], "selected record denominator mismatch")
    expected = case["legacy_top5_outcomes"] if stage == "pilot" else [row["legacy_outcome"] for row in case["candidates_sorted"]]
    hashes = [hashlib.sha256(record).hexdigest() for record in records]
    equal(hashes, descriptor["record_sha256s"], "record ordering")
    equal(hashes, [row["record_sha256"] for row in expected], "historical outcome record binding")
    return {"case": case, "records": records, "expected": expected,
            "native": bound_file(root, case["native"]), "receptor": bound_file(root, case["receptor"]),
            "input_ids": {"record_sha256s": hashes, "native_sha256": case["native"]["sha256"], "receptor_sha256": case["receptor"]["sha256"]}}


def legacy_projection(expected: list[dict]) -> dict:
    return {"rmsds_binary64_hex": [row["rmsd_binary64_hex"] for row in expected],
            "geometric_valid": [row["geometric_valid"] for row in expected],
            "chemical_valid": [row["chemical_valid"] for row in expected],
            "failed_check_ids": [row["failed_check_ids"] for row in expected]}


_FLOAT_TYPES = frozenset({"builtins.float", "numpy.float16", "numpy.float32", "numpy.float64"})
_BOOL_TYPES = frozenset({"builtins.bool", "numpy.bool_", "numpy.bool"})
_STRING_TYPES = frozenset({"builtins.str", "numpy.str_"})
_INTEGER_BOUNDS = {
    **{f"numpy.int{bits}": (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1) for bits in (8, 16, 32, 64)},
    **{f"numpy.uint{bits}": (0, 2 ** bits - 1) for bits in (8, 16, 32, 64)},
    "numpy.longlong": (-(2 ** 63), 2 ** 63 - 1),
    "numpy.ulonglong": (0, 2 ** 64 - 1),
}
_MISSING_TYPES = {
    "builtins.NoneType": "None",
    "pandas._libs.missing.NAType": "pandas.NA",
    "pandas._libs.tslibs.nattype.NaTType": "pandas.NaT",
}
_DTYPE_CLASSES = {
    "bool": "numpy.dtypes.BoolDType", "object": "numpy.dtypes.ObjectDType",
    **{f"float{bits}": f"numpy.dtypes.Float{bits}DType" for bits in (16, 32, 64)},
    **{f"int{bits}": f"numpy.dtypes.Int{bits}DType" for bits in (8, 16, 32, 64)},
    **{f"uint{bits}": f"numpy.dtypes.UInt{bits}DType" for bits in (8, 16, 32, 64)},
}
_HEX64 = re.compile(r"[0-9a-f]{16}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DECIMAL = re.compile(r"(?:0|-?[1-9][0-9]*)")


def validate_scalar(cell: dict) -> None:
    """Admit only the exact typed scalar encoding emitted by the evaluator.

    NaN payload/sign bits remain in binary64_be even though float.hex() writes
    every NaN as 'nan'. Infinity is a numeric value with missing=None, never a
    missing boolean or a fabricated successful check.
    """
    require(type(cell) is dict and type(cell.get("type")) is str, "invalid typed full-report scalar")
    kind = cell["type"]
    if kind in _MISSING_TYPES:
        require(set(cell) == {"type", "missing"} and cell["missing"] == _MISSING_TYPES[kind],
                "typed missing scalar differs")
    elif kind in _BOOL_TYPES:
        require(set(cell) == {"type", "value"} and type(cell["value"]) is bool,
                "typed boolean scalar is not a boolean")
    elif kind in _STRING_TYPES:
        require(set(cell) == {"type", "value"} and type(cell["value"]) is str,
                "typed string scalar is not a string")
    elif kind == "builtins.int" or kind in _INTEGER_BOUNDS:
        require(set(cell) == {"type", "decimal"} and type(cell["decimal"]) is str and
                _DECIMAL.fullmatch(cell["decimal"]) is not None, "invalid canonical integer scalar")
        try:
            value = int(cell["decimal"])
        except ValueError as exc:
            raise ReplayProtocolError("integer scalar cannot be decoded") from exc
        if kind in _INTEGER_BOUNDS:
            lower, upper = _INTEGER_BOUNDS[kind]
            require(lower <= value <= upper, "integer scalar exceeds its declared type")
    elif kind in _FLOAT_TYPES:
        require(set(cell) == {"type", "binary64_be", "hex", "missing"} and
                type(cell["binary64_be"]) is str and _HEX64.fullmatch(cell["binary64_be"]) is not None and
                type(cell["hex"]) is str, "invalid binary64 scalar encoding")
        value = struct.unpack(">d", bytes.fromhex(cell["binary64_be"]))[0]
        require(cell["hex"] == value.hex(), "binary64 bits and hex scalar differ")
        require(cell["missing"] == ("NaN" if math.isnan(value) else None),
                "floating scalar missing category differs")
        if kind in {"numpy.float16", "numpy.float32"} and not math.isnan(value):
            try:
                code = ">e" if kind == "numpy.float16" else ">f"
                restored = struct.unpack(code, struct.pack(code, value))[0]
            except (OverflowError, struct.error) as exc:
                raise ReplayProtocolError("floating scalar exceeds its declared precision") from exc
            require(struct.pack(">d", restored).hex() == cell["binary64_be"],
                    "floating scalar is not representable in its declared precision")
    else:
        raise ReplayProtocolError(f"unsupported typed full-report scalar: {kind}")


def _validate_dtype_cell(dtype: dict, cell: dict) -> None:
    name, kind = dtype["name"], cell["type"]
    if name == "object":
        return
    if name == "bool":
        require(kind in _BOOL_TYPES, "full-report boolean dtype/cell mismatch")
    elif name.startswith("float"):
        require(kind in _FLOAT_TYPES, "full-report floating dtype/cell mismatch")
    else:
        require(kind == "builtins.int" or kind in _INTEGER_BOUNDS, "full-report integer dtype/cell mismatch")
        lower, upper = _INTEGER_BOUNDS["numpy." + name]
        require(lower <= int(cell["decimal"]) <= upper, "full-report integer exceeds its dtype")


def validate_full_report(report: dict, *, selected: dict) -> None:
    require(type(report) is dict and set(report) == {"index_policy", "index_names", "columns", "dtypes", "rows"},
            "invalid full-report schema")
    require(report["index_policy"] == "validated_original_mol_identity_replaced_by_record_sha256_and_ordinal",
            "unverified full-report index policy")
    equal(report["index_names"], ["file", "molecule"], "full-report index names")
    columns, dtypes, rows = report["columns"], report["dtypes"], report["rows"]
    require(type(columns) is list and columns and all(type(name) is str and name for name in columns) and
            len(columns) == len(set(columns)) and "rmsd" in columns, "invalid full-report column schema")
    require(type(dtypes) is list and len(dtypes) == len(columns), "full-report dtype denominator mismatch")
    for dtype in dtypes:
        require(type(dtype) is dict and set(dtype) == {"name", "type"} and type(dtype["name"]) is str and
                dtype["name"] in _DTYPE_CLASSES and dtype["type"] == _DTYPE_CLASSES[dtype["name"]],
                "invalid frozen full-report dtype")
    count = len(selected["expected"])
    require(type(rows) is list and len(rows) == count, "full-report row denominator mismatch")
    rmsd_column = columns.index("rmsd")
    for index, row in enumerate(rows):
        require(type(row) is dict and set(row) == {"record_ordinal", "record_sha256", "molecule_name", "cells"},
                "invalid full-report row schema")
        require(type(row["record_ordinal"]) is int and row["record_ordinal"] == index + 1 and
                row["record_sha256"] == selected["input_ids"]["record_sha256s"][index],
                "full-report record order/binding mismatch")
        require(row["molecule_name"] == f"{selected['case']['case_id']}_engine_v2_rank_{index + 1}",
                "full-report molecule name mismatch")
        require(type(row["cells"]) is list and len(row["cells"]) == len(columns), "full-report cell denominator mismatch")
        for dtype, cell in zip(dtypes, row["cells"]):
            validate_scalar(cell)
            _validate_dtype_cell(dtype, cell)
        rmsd = row["cells"][rmsd_column]
        require(rmsd["type"] in _FLOAT_TYPES and rmsd["hex"] == selected["expected"][index]["rmsd_binary64_hex"],
                "full-report RMSD differs from historical scientific outcomes")


def validate_result(result: dict, *, selected: dict, mode: str) -> None:
    count = len(selected["expected"])
    require(result.get("status") == "success" and result.get("mode") == mode, "worker failed or mode differs")
    require(type(result.get("record_count")) is int and result["record_count"] == count, "worker denominator mismatch")
    equal(result["input_ids"], selected["input_ids"], "worker input identities")
    legacy = result["legacy_outcomes"]
    require(len(legacy["rmsds"]) == count and all(type(v) is float and math.isfinite(v) and v >= 0 for v in legacy["rmsds"]), "invalid RMSD values")
    equal([v.hex() for v in legacy["rmsds"]], legacy["rmsds_binary64_hex"], "RMSD binary64 encoding")
    equal({key: legacy[key] for key in legacy_projection(selected["expected"])}, legacy_projection(selected["expected"]), "historical scientific outcomes")
    validate_full_report(result["fullReport"], selected=selected)
    immutable = result["input_immutability"]
    require(immutable.get("verified") is True, "input immutability was not verified")
    equal(immutable["before"], immutable["after"], "input mutation")
    require(result["energy_cache"]["cleared_at_entry"] is True and result["energy_cache"]["cleared_at_exit"] is True, "energy cache not cleared")
    timing = result["timings"]
    require(timing["instrumented"] is (mode != "baseline") and timing["profile_timing_is_diagnostic"] is (mode == "profile"), "timing mode mismatch")
    for key in ("end_to_end_ns", "posebusters_ns", "decode_ns"):
        require(type(timing[key]) is int and timing[key] > 0, f"invalid timer: {key}")


def compare_results(baseline: dict, observed: dict) -> dict:
    for key in ("fullReport", "legacy_outcomes", "input_ids", "evaluator_versions", "python_version", "upstream_source_sha256", "input_immutability"):
        equal(baseline[key], observed[key], key)
    return {"full_report_sha256": digest(baseline["fullReport"]), "legacy_outcomes_sha256": digest(baseline["legacy_outcomes"]), "all_full_report_cells_exact": True, "tolerance_used": False}


def worker(args: argparse.Namespace) -> int:
    from tools.posebusters_replay_evaluator import run_evaluation
    result = {"schema_id": SCHEMA, "status": "failed", "mode": args.mode, "case_id": args.case_id, "stage": args.stage}
    try:
        bundle, manifest = load_bundle(args.input_root, args.bundle_sha256)
        equal(source_identity(), bundle["source"], "worker source checkout")
        selected = selected_inputs(args.input_root, bundle, manifest, args.case_id, args.stage)
        evaluated = run_evaluation(records=selected["records"], native_payload=selected["native"], receptor_payload=selected["receptor"], mode=args.mode)
        result.update(evaluated, status="success", bundle_sha256=args.bundle_sha256, protocol_sha256=digest(PROTOCOL), source=bundle["source"])
        validate_result(result, selected=selected, mode=args.mode)
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    isolation.atomic_json(args.output, result, replace=False)
    return 0 if result["status"] == "success" else 1


def capture_environment(bundle_root: Path) -> dict:
    manifest = read_json(bundle_root / "evaluator/wheelhouse-manifest.json")
    require(manifest["manifest_sha256"] == WHEEL_MANIFEST and manifest["wheel_set_sha256"] == WHEEL_SET, "runtime wheel set is not the frozen source run")
    reference_path = bundle_root / "reference-environment.json"
    require(isolation.digest_file(reference_path) == REFERENCE_ENVIRONMENT_FILE, "frozen reference environment SHA256 mismatch")
    reference = read_json(reference_path)
    snapshot = evidence.snapshot_environment(manifest["distributions"], source_files=source_files(), wheelhouse_manifest=manifest)
    equal(snapshot["versions"], reference["versions"], "frozen evaluator versions")
    equal({name: row["active_payload_sha256"] for name, row in snapshot["distributions"].items()}, {name: row["active_payload_sha256"] for name, row in reference["distributions"].items()}, "frozen installed active payloads")
    return snapshot


def execution_ok(record: dict) -> bool:
    return (type(record.get("returncode")) is int and record["returncode"] == 0 and record.get("termination") == "exited" and record.get("cleanup_complete") is True)


def _execution_context(summary: dict) -> dict:
    context = summary.get("execution_context")
    require(type(context) is dict and set(context) == {"python_executable", "input_root", "output_root", "working_directory"},
            "missing original worker execution context")
    # These are the original node's paths, not paths to open on this node.
    # Evidence can be relocated without rewriting its recorded argv.
    for name, value in context.items():
        require(type(value) is str and value.startswith("/") and not value.startswith("//") and
                "\\" not in value and not any(ord(char) < 32 or ord(char) == 127 for char in value) and
                PurePosixPath(value).as_posix() == value and ".." not in PurePosixPath(value).parts,
                f"noncanonical original execution path: {name}")
    return context


def worker_command(summary: dict, *, slot: int, mode: str) -> list[str]:
    stage = summary.get("stage")
    require(stage in ("pilot", "expanded"), "invalid execution stage")
    order = PROTOCOL[f"{stage}_order"]
    require(type(slot) is int and 0 <= slot < len(order) and mode == order[slot], "worker slot/mode differs")
    require(summary.get("case_id") in (PILOT_CASES if stage == "pilot" else EXPANDED_CASES),
            "worker case outside fixed stage")
    context = _execution_context(summary)
    output = str(PurePosixPath(context["output_root"]) / f"result-{slot}-{mode}.json")
    return [context["python_executable"], "-m", "tools.run_posebusters_replay", "worker",
            "--input-root", context["input_root"], "--bundle-sha256", summary["bundle_sha256"],
            "--case-id", summary["case_id"], "--stage", stage, "--mode", mode, "--output", output]


def validate_execution(record: dict, *, summary: dict, slot: int, mode: str,
                       result_relative_path: str) -> None:
    require(type(record) is dict and record.get("schema_id") == "betelgeuze.redocking_process_execution/1.0.0",
            "invalid execution receipt schema")
    claimed = record.get("control_sha256")
    require(type(claimed) is str and _SHA256.fullmatch(claimed) is not None, "invalid execution self hash")
    projection = {key: value for key, value in record.items() if key != "control_sha256"}
    require(isolation.digest_json(projection) == claimed, "execution receipt self hash differs")
    require(execution_ok(record), f"worker {slot} failed resource/exit/cleanup gate")
    require("error" in record and record["error"] is None, "execution receipt reports a supervision error")
    expected_command = worker_command(summary, slot=slot, mode=mode)
    require(result_relative_path == f"result-{slot}-{mode}.json", "worker result path differs")
    command = record.get("command")
    require(type(command) is list and all(type(value) is str for value in command), "invalid worker argv")
    equal(command, expected_command, "worker command binding")
    limits = {"wall_limit_seconds": PROTOCOL["wall_limit_seconds"][summary["stage"]],
              "rss_limit_bytes": PROTOCOL["rss_limit_bytes"],
              "rss_sampling_seconds": PROTOCOL["rss_sampling_seconds"]}
    for name, expected in limits.items():
        require(type(record.get(name)) is type(expected) and record[name] == expected,
                f"execution protocol limit differs: {name}")
    require(type(record.get("wall_seconds")) in (int, float) and math.isfinite(record["wall_seconds"]) and
            record["wall_seconds"] > 0, "invalid execution wall time")
    require(type(record.get("child_cpu_seconds")) in (int, float) and math.isfinite(record["child_cpu_seconds"]) and
            record["child_cpu_seconds"] >= 0, "invalid execution CPU time")
    peak = record.get("sampled_peak_process_tree_rss_bytes")
    require(type(peak) is int and 0 <= peak <= PROTOCOL["rss_limit_bytes"], "invalid execution sampled RSS")


def assess_case(directory: Path, summary: dict, *, selected: dict, bundle: dict, bundle_sha256: str) -> dict:
    stage = summary["stage"]
    require(stage in ("pilot", "expanded"), "invalid summary stage")
    equal(summary["source"], bundle["source"], "case source")
    require(summary["bundle_sha256"] == bundle_sha256 and summary["protocol_sha256"] == digest(PROTOCOL), "case protocol/bundle binding differs")
    order = PROTOCOL[f"{stage}_order"]
    require(len(summary["observations"]) == len(order), "missing worker observation")
    reports, executions = [], []
    for index, (observation, mode) in enumerate(zip(summary["observations"], order)):
        require(type(observation["slot"]) is int and observation["slot"] == index and observation["mode"] == mode,
                "worker order differs")
        require(observation.get("process_gate_passed") is True, "worker process gate was not passed")
        require(observation["execution_path"] == f"worker-{index}-{mode}/process-execution.json",
                "worker execution receipt path differs")
        execution_path = relative_file(directory, observation["execution_path"])
        require(isolation.digest_file(execution_path) == observation["execution_sha256"], "execution receipt hash differs")
        execution = read_json(execution_path)
        validate_execution(execution, summary=summary, slot=index, mode=mode,
                           result_relative_path=observation["result_path"])
        result_path = relative_file(directory, observation["result_path"])
        require(isolation.digest_file(result_path) == observation["result_sha256"], "worker result hash differs")
        result = read_json(result_path)
        require(result["bundle_sha256"] == bundle_sha256 and result["case_id"] == summary["case_id"] and result["stage"] == stage and result["protocol_sha256"] == digest(PROTOCOL), "worker identity differs")
        equal(result["source"], bundle["source"], "worker source")
        validate_result(result, selected=selected, mode=mode)
        reports.append(result)
        executions.append(execution)
    comparisons = [compare_results(reports[0], report) for report in reports[1:]]
    before = read_json(relative_file(directory, "environment-before.json"))
    after = read_json(relative_file(directory, "environment-after.json"))
    evidence.require_matching_environment(before, after)
    pairs = []
    for baseline_index, prepared_index in PROTOCOL[f"{stage}_pairs"]:
        baseline_ns = reports[baseline_index]["timings"]["posebusters_ns"]
        prepared_ns = reports[prepared_index]["timings"]["posebusters_ns"]
        baseline_total = reports[baseline_index]["timings"]["end_to_end_ns"]
        prepared_total = reports[prepared_index]["timings"]["end_to_end_ns"]
        baseline_wall = executions[baseline_index]["wall_seconds"]
        prepared_wall = executions[prepared_index]["wall_seconds"]
        pairs.append({"baseline_slot": baseline_index, "prepared_slot": prepared_index,
            "baseline_ns": baseline_ns, "prepared_ns": prepared_ns,
            "saved_fraction": (baseline_ns - prepared_ns) / baseline_ns, "timer": "posebusters_ns",
            "baseline_end_to_end_ns": baseline_total, "prepared_end_to_end_ns": prepared_total,
            "end_to_end_saved_fraction": (baseline_total - prepared_total) / baseline_total,
            "baseline_worker_wall_seconds": baseline_wall, "prepared_worker_wall_seconds": prepared_wall,
            "worker_wall_saved_fraction": (baseline_wall - prepared_wall) / baseline_wall,
            "baseline_is_unprofiled": True, "prepared_includes_lightweight_timers": True})
    return {"exact_equivalence_passed": True, "comparisons": comparisons, "pairs": pairs,
            "median_saved_fraction": statistics.median(row["saved_fraction"] for row in pairs),
            "median_end_to_end_saved_fraction": statistics.median(row["end_to_end_saved_fraction"] for row in pairs),
            "median_worker_wall_saved_fraction": statistics.median(row["worker_wall_saved_fraction"] for row in pairs),
            "same_node_environment_stable": True, "environment_content_identity_sha256": before["content_identity_sha256"],
            "joint_valid_records": sum(row["geometric_valid"] and row["chemical_valid"] for row in selected["expected"]),
            "full_report_columns": len(reports[0]["fullReport"]["columns"]), "full_report_rows": len(reports[0]["fullReport"]["rows"])}


def run_case(args: argparse.Namespace) -> int:
    directory = args.output_root
    require(not directory.exists(), "case output directory must be fresh")
    directory.mkdir(parents=True)
    summary = {"schema_id": SCHEMA, "status": "failed", "case_id": args.case_id, "stage": args.stage,
               "bundle_sha256": args.bundle_sha256, "protocol_sha256": digest(PROTOCOL), "observations": [],
               "execution_context": {"python_executable": str(Path(sys.executable).absolute()),
                                     "input_root": str(args.input_root), "output_root": str(directory),
                                     "working_directory": str(ROOT)},
               "host": {"platform": platform.platform(), "cpu_count": os.cpu_count(), "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None},
               "job": {key: os.environ.get(key) for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion")}}
    isolation.atomic_json(directory / "case-request.json", summary, replace=False)
    try:
        bundle, manifest = load_bundle(args.input_root, args.bundle_sha256)
        equal(source_identity(), bundle["source"], "controller source checkout")
        summary["source"] = bundle["source"]
        selected = selected_inputs(args.input_root, bundle, manifest, args.case_id, args.stage)
        isolation.atomic_json(directory / "environment-before.json", capture_environment(args.runtime_root), replace=False)
        for slot, mode in enumerate(PROTOCOL[f"{args.stage}_order"]):
            worker_dir = directory / f"worker-{slot}-{mode}"
            result_path = directory / f"result-{slot}-{mode}.json"
            command = worker_command(summary, slot=slot, mode=mode)
            execution = isolation.supervise(command, worker_dir, isolation.Limits(wall_seconds=PROTOCOL["wall_limit_seconds"][args.stage], rss_bytes=PROTOCOL["rss_limit_bytes"], poll_seconds=PROTOCOL["rss_sampling_seconds"], log_bytes=PROTOCOL["log_limit_bytes"]), cwd=ROOT, env=dict(os.environ))
            execution_path = worker_dir / "process-execution.json"
            require(execution_path.is_file(), "supervisor did not retain its execution receipt")
            summary["observations"].append({"slot": slot, "mode": mode,
                "execution_path": execution_path.relative_to(directory).as_posix(), "execution_sha256": isolation.digest_file(execution_path),
                "result_path": result_path.relative_to(directory).as_posix(), "result_sha256": isolation.digest_file(result_path) if result_path.is_file() else None,
                "process_gate_passed": execution_ok(execution)})
            isolation.atomic_json(directory / "progress.json", summary)
        isolation.atomic_json(directory / "environment-after.json", capture_environment(args.runtime_root), replace=False)
        summary["assessment"] = assess_case(directory, summary, selected=selected, bundle=bundle, bundle_sha256=args.bundle_sha256)
        summary["status"] = "success"
    except Exception as exc:
        summary.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    isolation.atomic_json(directory / "case-summary.json", summary, replace=False)
    print(json.dumps({key: summary.get(key) for key in ("case_id", "stage", "status", "error", "assessment")}, sort_keys=True))
    return 0 if summary["status"] == "success" else 1


def aggregate(args: argparse.Namespace) -> int:
    bundle, manifest = load_bundle(args.input_root, args.bundle_sha256)
    stages = ("pilot", "expanded") if args.stage == "all" else (args.stage,)
    expected = {(stage, case) for stage in stages for case in (PILOT_CASES if stage == "pilot" else EXPANDED_CASES)}
    observed, failures = {}, []
    for path in sorted(args.results_root.rglob("case-summary.json")):
        try:
            summary = read_json(path)
            key = (summary["stage"], summary["case_id"])
            require(key in expected and key not in observed, "duplicate or unexpected case summary")
            observed[key] = {"case_id": key[1], "stage": key[0], "status": "failed", "summary_sha256": isolation.digest_file(path)}
            selected = selected_inputs(args.input_root, bundle, manifest, key[1], key[0])
            require(summary.get("status") == "success", "case summary did not pass")
            assessment = assess_case(path.parent, summary, selected=selected, bundle=bundle, bundle_sha256=args.bundle_sha256)
            equal(assessment, summary["assessment"], "recomputed case assessment")
            observed[key].update(status="success", assessment=assessment)
        except Exception as exc:
            failures.append({"path": str(path), "error_type": type(exc).__name__, "error": str(exc)})
    missing = sorted(expected - set(observed))
    success = not failures and not missing and len(observed) == len(expected)
    report = {"schema_id": SCHEMA, "status": "success" if success else "failed", "stage": args.stage,
              "protocol": PROTOCOL, "source": bundle["source"], "bundle_sha256": args.bundle_sha256,
              "expected_case_stage_count": len(expected), "observed_case_stage_count": len(observed),
              "missing": [{"stage": stage, "case_id": case} for stage, case in missing], "failures": failures,
              "cases": [observed[key] for key in sorted(observed)]}
    isolation.atomic_json(args.output, report, replace=False)
    print(json.dumps(report, sort_keys=True))
    return 0 if success else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--artifact-root", required=True, type=Path)
    prep.add_argument("--output-root", required=True, type=Path)
    for name in ("worker", "run-case", "aggregate"):
        item = commands.add_parser(name)
        item.add_argument("--input-root", required=True, type=Path)
        item.add_argument("--bundle-sha256", required=True)
        item.add_argument("--stage", required=True, choices=("pilot", "expanded", "all") if name == "aggregate" else ("pilot", "expanded"))
        if name == "aggregate":
            item.add_argument("--results-root", required=True, type=Path)
            item.add_argument("--output", required=True, type=Path)
        else:
            item.add_argument("--case-id", required=True, choices=PILOT_CASES)
            if name == "worker":
                item.add_argument("--mode", required=True, choices=("baseline", "profile", "prepared_receptor"))
                item.add_argument("--output", required=True, type=Path)
            else:
                item.add_argument("--runtime-root", required=True, type=Path)
                item.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    for key in ("input_root", "artifact_root", "runtime_root", "output_root", "results_root", "output"):
        if hasattr(args, key):
            setattr(args, key, getattr(args, key).absolute())
    if args.command == "prepare":
        print(json.dumps(prepare(args.artifact_root, args.output_root), sort_keys=True))
        return 0
    return {"worker": worker, "run-case": run_case, "aggregate": aggregate}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
