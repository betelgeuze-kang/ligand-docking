#!/usr/bin/env python3
"""Assemble a non-authoritative HIP D1 candidate result without execution.

The input is a completed owner-recorded result-shaped draft.  This tool
recomputes every redundant digest, trace summary, transfer aggregate, backend
receipt, and the result self-hash, then runs the canonical pre-pin candidate
validator before writing an absent output.  It never launches a workload or
grants repository, device, performance, scientific, or product authority.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from typing import Any


VERIFIER_PATH = Path(__file__).with_name("verify_engine_v2_hip_d1_benchmark_v1.py")


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "assemble_engine_v2_hip_d1_candidate_verifier_v1", VERIFIER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the HIP D1 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = _load_verifier()
AUTHORITY = {key: False for key in VERIFIER.AUTHORITY_KEYS}
ASSEMBLY_RECEIPT_SCHEMA = (
    "betelgeuze.engine_v2_hip_d1_candidate_result_assembly_receipt/1.0.0"
)


class CandidateAssemblyError(ValueError):
    """The bound profile or completed result-shaped draft is invalid."""


def _object_no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in items:
        if key in output:
            raise CandidateAssemblyError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CandidateAssemblyError(f"{path} must be a regular non-symlink file")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CandidateAssemblyError(f"non-finite JSON number: {token}")
            ),
        )
    except CandidateAssemblyError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidateAssemblyError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise CandidateAssemblyError(f"{path} must contain one JSON object")
    return value


def _hash(value: Any) -> str:
    try:
        return VERIFIER._canonical_sha256(value)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise CandidateAssemblyError("value is not canonical JSON") from exc


def _dict(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CandidateAssemblyError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise CandidateAssemblyError(f"{label} must be a list")
    return value


def _positive_float(value: Any, label: str) -> float:
    try:
        return VERIFIER._finite(value, label, positive=True)
    except VERIFIER.HipBenchmarkError as exc:
        raise CandidateAssemblyError(str(exc)) from exc


def _profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    try:
        summary = VERIFIER._verify_profile_document(profile)
    except VERIFIER.HipBenchmarkError as exc:
        raise CandidateAssemblyError(f"invalid HIP D1 profile: {exc}") from exc
    if not summary["manifest_bound"]:
        raise CandidateAssemblyError(
            "candidate assembly requires a manifest-bound HIP D1 profile"
        )
    return summary


def _kernel_summaries(trace: Any, label: str) -> list[dict[str, Any]]:
    rows = _list(_dict(trace, label).get("rows"), f"{label}.rows")
    order: list[str] = []
    runtimes: dict[str, list[float]] = {}
    for index, raw_row in enumerate(rows):
        row = _dict(raw_row, f"{label}.rows[{index}]")
        name = row.get("kernel_name")
        runtime = row.get("runtime_seconds")
        if type(name) is not str or not name:
            raise CandidateAssemblyError(f"{label}.rows[{index}].kernel_name")
        if name not in runtimes:
            order.append(name)
            runtimes[name] = []
        runtimes[name].append(
            _positive_float(runtime, f"{label}.rows[{index}].runtime_seconds")
        )
    try:
        return [
            {
                "kernel_name": name,
                "dispatch_count": len(runtimes[name]),
                "total_runtime_seconds": VERIFIER._finite_sum(
                    runtimes[name], f"{label}.{name}.runtime"
                ),
            }
            for name in order
        ]
    except VERIFIER.HipBenchmarkError as exc:
        raise CandidateAssemblyError(str(exc)) from exc


def _transfer_aggregates(
    trace: Any,
    ordered_case_ids: list[Any],
    cases: list[Any],
    label: str,
) -> tuple[int, int, list[float], list[float]]:
    rows = _list(_dict(trace, label).get("rows"), f"{label}.rows")
    case_map: dict[Any, dict[str, Any]] = {}
    for raw_case in cases:
        case = _dict(raw_case, f"{label}.case")
        case_id = case.get("case_id")
        if type(case_id) is not str:
            raise CandidateAssemblyError(f"{label}.case.case_id")
        case_map[case_id] = case
    sample_order: list[tuple[Any, int]] = []
    for case_id in ordered_case_ids:
        if type(case_id) is not str:
            raise CandidateAssemblyError(f"{label}: ordered case identity")
        case = case_map.get(case_id)
        if case is None:
            raise CandidateAssemblyError(f"{label}: missing case {case_id}")
        samples = _list(case.get("wall_time_seconds"), f"{label}.{case_id}.samples")
        sample_order.extend((case_id, index) for index in range(len(samples)))
    timing: dict[str, dict[tuple[Any, int], list[float]]] = {
        "h2d": {},
        "d2h": {},
    }
    byte_totals = {"h2d": 0, "d2h": 0}
    for index, raw_row in enumerate(rows):
        row = _dict(raw_row, f"{label}.rows[{index}]")
        direction = row.get("direction")
        if type(direction) is not str or direction not in timing:
            raise CandidateAssemblyError(f"{label}.rows[{index}].direction")
        byte_count = row.get("bytes")
        runtime = row.get("runtime_seconds")
        if type(byte_count) is not int or byte_count < 0:
            raise CandidateAssemblyError(f"{label}.rows[{index}].bytes")
        row_case_id = row.get("case_id")
        sample_index = row.get("sample_index")
        if type(row_case_id) is not str or type(sample_index) is not int:
            raise CandidateAssemblyError(f"{label}.rows[{index}].sample identity")
        key = (row_case_id, sample_index)
        byte_totals[direction] += byte_count
        timing[direction].setdefault(key, []).append(
            _positive_float(runtime, f"{label}.rows[{index}].runtime_seconds")
        )
    try:
        derived = {
            direction: [
                VERIFIER._finite_sum(
                    timing[direction].get(key, []),
                    f"{label}.{key[0]}.sample[{key[1]}].{direction}",
                )
                for key in sample_order
            ]
            for direction in ("h2d", "d2h")
        }
    except VERIFIER.HipBenchmarkError as exc:
        raise CandidateAssemblyError(str(exc)) from exc
    return (
        byte_totals["h2d"],
        byte_totals["d2h"],
        derived["h2d"],
        derived["d2h"],
    )


def _assemble_case(raw_case: Any, label: str) -> dict[str, Any]:
    case = _dict(raw_case, label)
    case["ordered_candidate_ids_sha256"] = _hash(
        _list(case.get("ordered_candidate_ids"), f"{label}.ordered_candidate_ids")
    )
    for repeat in (False, True):
        prefix = "repeat_" if repeat else ""
        statuses = _list(
            case.get(f"{prefix}candidate_statuses"),
            f"{label}.{prefix}candidate_statuses",
        )
        discrete = _dict(
            case.get(f"{prefix}discrete_outputs"),
            f"{label}.{prefix}discrete_outputs",
        )
        case[f"{prefix}typed_failure_sha256"] = _hash(statuses)
        for field in VERIFIER.DERIVED_DISCRETE_FIELDS:
            case[f"{prefix}{field}_sha256"] = _hash(discrete.get(field))
    return case


def _assemble_failure_probe(
    raw_probe: Any, architecture: str, label: str
) -> dict[str, Any]:
    probe = _dict(raw_probe, label)
    stimulus = _dict(probe.get("failure_stimulus"), f"{label}.failure_stimulus")
    stimulus_sha256 = _hash(stimulus)
    observation = _dict(probe.get("observed_error"), f"{label}.observed_error")
    if observation.get("failure_stimulus_sha256") != stimulus_sha256:
        raise CandidateAssemblyError(f"{label}: observation/stimulus cross-wire")
    observed_error_sha256 = _hash(observation)
    probe["failure_stimulus_sha256"] = stimulus_sha256
    probe["observed_error_sha256"] = observed_error_sha256
    receipt = {
        "schema_id": VERIFIER.FAILURE_PROBE_RECEIPT_SCHEMA,
        "gpu_architecture": architecture,
        "requested_backend": probe.get("backend"),
        "requested_error_code": probe.get("error_code"),
        "execution_run_id_sha256": probe.get("execution_run_id_sha256"),
        "failure_stimulus_sha256": stimulus_sha256,
        "observed_error_sha256": observed_error_sha256,
        "cpu_fallback_observed": probe.get("cpu_fallback_observed"),
    }
    probe["probe_execution_receipt_sha256"] = _hash(receipt)
    return probe


def _assemble_backend(
    raw_backend: Any,
    architecture: str,
    ordered_case_ids: list[Any],
    executable_bundle_sha256: str,
    label: str,
) -> dict[str, Any]:
    backend = _dict(raw_backend, label)
    cases = [
        _assemble_case(raw_case, f"{label}.cases[{index}]")
        for index, raw_case in enumerate(_list(backend.get("cases"), f"{label}.cases"))
    ]
    backend["cases"] = cases
    is_gpu = backend.get("backend_name") != "rust_cpu"
    for repeat in (False, True):
        prefix = "repeat_" if repeat else ""
        if is_gpu:
            profiler_trace = backend.get(f"{prefix}profiler_trace")
            transfer_trace = backend.get(f"{prefix}transfer_trace")
            backend[f"{prefix}profiler_trace_sha256"] = _hash(profiler_trace)
            backend[f"{prefix}kernel_dispatches"] = _kernel_summaries(
                profiler_trace, f"{label}.{prefix}profiler_trace"
            )
            backend[f"{prefix}transfer_trace_sha256"] = _hash(transfer_trace)
            if not repeat:
                h2d_bytes, d2h_bytes, h2d_seconds, d2h_seconds = _transfer_aggregates(
                    transfer_trace, ordered_case_ids, cases, f"{label}.transfer_trace"
                )
                backend["h2d_bytes"] = h2d_bytes
                backend["d2h_bytes"] = d2h_bytes
                backend["h2d_seconds"] = h2d_seconds
                backend["d2h_seconds"] = d2h_seconds
        else:
            backend[f"{prefix}profiler_trace_sha256"] = None
            backend[f"{prefix}kernel_dispatches"] = []
            backend[f"{prefix}transfer_trace_sha256"] = None
            if not repeat:
                backend["h2d_bytes"] = 0
                backend["d2h_bytes"] = 0
                backend["h2d_seconds"] = []
                backend["d2h_seconds"] = []
        try:
            receipt = VERIFIER._execution_backend_receipt(
                architecture=architecture,
                backend_name=backend.get("backend_name"),
                observed_backend=backend.get(
                    "repeat_observed_backend" if repeat else "observed_backend"
                ),
                cpu_fallback_observed=backend.get(
                    "repeat_cpu_fallback_observed"
                    if repeat
                    else "cpu_fallback_observed"
                ),
                ordered_case_ids=ordered_case_ids,
                run_role="repeat" if repeat else "primary",
                execution_run_id_sha256=backend.get(f"{prefix}execution_run_id_sha256"),
                profiler_trace_sha256=backend.get(f"{prefix}profiler_trace_sha256"),
                transfer_trace_sha256=backend.get(f"{prefix}transfer_trace_sha256"),
                context_construction_samples=backend.get(
                    f"{prefix}context_construction_seconds"
                ),
                peak_rss_bytes=backend.get(f"{prefix}peak_rss_bytes"),
                peak_vram_bytes=backend.get(f"{prefix}peak_vram_bytes"),
                executable_bundle_sha256=executable_bundle_sha256,
                cases=cases,
            )
        except (KeyError, TypeError, VERIFIER.HipBenchmarkError) as exc:
            raise CandidateAssemblyError(
                f"{label}: cannot derive backend receipt"
            ) from exc
        backend[f"{prefix}execution_backend_receipt_sha256"] = _hash(receipt)
    return backend


def assemble_candidate_result(
    profile: dict[str, Any], draft: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = _profile_summary(profile)
    result = copy.deepcopy(draft)
    ordered_case_ids = _list(result.get("ordered_case_ids"), "ordered_case_ids")
    result["ordered_case_ids_sha256"] = _hash(ordered_case_ids)
    architectures = _list(result.get("architectures"), "architectures")
    for architecture_index, raw_architecture in enumerate(architectures):
        label = f"architectures[{architecture_index}]"
        architecture = _dict(raw_architecture, label)
        architecture_name = architecture.get("gpu_architecture")
        probes = _list(architecture.get("failure_probes"), f"{label}.failure_probes")
        architecture["failure_probes"] = [
            _assemble_failure_probe(
                probe, architecture_name, f"{label}.failure_probes[{i}]"
            )
            for i, probe in enumerate(probes)
        ]
        try:
            executable_bundle_sha256 = VERIFIER._executable_bundle_sha256(
                architecture.get("wheel_sha256"),
                architecture.get("native_extension_sha256"),
                architecture.get("native_binary_sha256"),
            )
        except (TypeError, VERIFIER.HipBenchmarkError) as exc:
            raise CandidateAssemblyError(f"{label}: executable bundle") from exc
        backends = _dict(architecture.get("backends"), f"{label}.backends")
        for backend_name in list(backends):
            backends[backend_name] = _assemble_backend(
                backends[backend_name],
                architecture_name,
                ordered_case_ids,
                executable_bundle_sha256,
                f"{label}.backends.{backend_name}",
            )
    result["result_sha256"] = _hash(VERIFIER._result_projection(result))
    receipt = {
        "schema_id": ASSEMBLY_RECEIPT_SCHEMA,
        "profile_sha256": summary["profile_sha256"],
        "source_draft_sha256": _hash(draft),
        "candidate_result_sha256": result["result_sha256"],
        "architecture_count": len(architectures),
        "case_count": len(ordered_case_ids),
        "candidate_denominator": profile["candidate_denominator"],
        "candidate_validation_performed": False,
        "result_verification_authorized": False,
        "device_execution_performed": False,
        "molecular_execution_performed": False,
        "authority_granted": False,
        "authority": dict(AUTHORITY),
    }
    receipt["receipt_sha256"] = _hash(receipt)
    return result, receipt


def _mark_candidate_validated(receipt: dict[str, Any]) -> dict[str, Any]:
    validated = copy.deepcopy(receipt)
    validated["candidate_validation_performed"] = True
    validated.pop("receipt_sha256", None)
    validated["receipt_sha256"] = _hash(validated)
    return validated


def profile_only(profile: dict[str, Any]) -> dict[str, Any]:
    summary = _profile_summary(profile)
    return {
        "ok": True,
        "profile_sha256": summary["profile_sha256"],
        "manifest_bound": True,
        "candidate_assembly_ready": True,
        "result_verification_authorized": False,
        "device_execution_performed": False,
        "molecular_execution_performed": False,
        "authority_granted": False,
    }


def _payload(value: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise CandidateAssemblyError("candidate result is not canonical JSON") from exc


def _validate_and_write_absent(
    profile_path: Path, output_path: Path, result: dict[str, Any]
) -> dict[str, Any]:
    if output_path.exists() or output_path.is_symlink():
        raise CandidateAssemblyError("output path must be absent")
    parent = output_path.parent.resolve()
    if not parent.is_dir():
        raise CandidateAssemblyError("output parent must exist")
    target = parent / output_path.name
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.tmp-", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_payload(result))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            validation = VERIFIER.validate_candidate_result(profile_path, temporary)
        except VERIFIER.HipBenchmarkError as exc:
            raise CandidateAssemblyError(f"candidate validation failed: {exc}") from exc
        if validation["result_sha256"] != result.get("result_sha256"):
            raise CandidateAssemblyError("candidate validator result digest drift")
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise CandidateAssemblyError("output path must be absent") from exc
        return validation
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        profile = _load(args.profile)
        if args.draft is None:
            if args.output is not None:
                raise CandidateAssemblyError("--output requires an explicit --draft")
            output = profile_only(profile)
        else:
            if args.output is None:
                raise CandidateAssemblyError(
                    "candidate assembly requires an absent --output path"
                )
            result, receipt = assemble_candidate_result(profile, _load(args.draft))
            _validate_and_write_absent(args.profile, args.output, result)
            output = {"ok": True, **_mark_candidate_validated(receipt)}
        print(json.dumps(output, allow_nan=False, sort_keys=True))
        return 0
    except CandidateAssemblyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
