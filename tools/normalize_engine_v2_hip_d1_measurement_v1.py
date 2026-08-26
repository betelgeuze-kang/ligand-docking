#!/usr/bin/env python3
"""Normalize owner-recorded HIP D1 timing journals without executing a GPU.

The tool converts sample-relative nanosecond dispatch and memory-copy events
into the normalized profiler and transfer fragments consumed by the Engine V2
HIP D1 result verifier.  It never launches a molecular workload, invokes a HIP
device, grants execution authority, or authorizes a performance claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any


PROFILE_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_profile/1.5.0"
JOURNAL_SCHEMA = "betelgeuze.engine_v2_hip_d1_measurement_journal/1.0.0"
OUTPUT_SCHEMA = "betelgeuze.engine_v2_hip_d1_measurement_normalization/1.0.0"
PROFILER_TRACE_SCHEMA = (
    "betelgeuze.engine_v2_rocprofiler_normalized_dispatch_trace/1.3.0"
)
TRANSFER_TRACE_SCHEMA = "betelgeuze.engine_v2_hip_normalized_transfer_trace/1.2.0"
PROFILE_ID = "engine_v2_hip_d1_representative_v1"
GPU_BACKENDS = {"hip_safe", "hip_fast"}
FAILURE_PROBE_CODES = [
    "backend_unavailable",
    "device_oom",
    "execution_timeout",
    "numeric_overflow",
]
REQUIRED_STAGE_SEQUENCE = [
    "initial_geometric_admission",
    "rigid_refinement",
    "torsion_refinement",
    "post_geometric_admission",
    "scoring",
    "pose_validity",
    "stable_ranking",
    "rmsd_clustering",
]
REQUIRED_KERNEL_BY_STAGE = {
    "initial_geometric_admission": "geometric_fixed64_kernel",
    "rigid_refinement": "rigid_refinement_kernel",
    "torsion_refinement": "torsion_fixed64_kernel",
    "post_geometric_admission": "geometric_fixed64_kernel",
    "scoring": "scorer_fixed64_kernel",
    "pose_validity": "validity_fixed64_kernel",
    "stable_ranking": "stable_top_k_fixed64_kernel",
    "rmsd_clustering": "direct_rmsd_cluster_fixed64_kernel",
}
CASE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
STAGE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
MAX_NANOSECONDS = (1 << 63) - 1
MAX_EVENT_BYTES = (1 << 63) - 1

AUTHORITY = {
    "device_execution_authorized": False,
    "gpu_acceleration_claim_authorized": False,
    "scientific_claim_authorized": False,
    "benchmark_claim_authorized": False,
    "product_authorized": False,
    "production_authorized": False,
    "reservation_authorized": False,
    "molecular_ab_authorized": False,
    "fresh128_authorized": False,
    "stage0_authorized": False,
}


class MeasurementNormalizationError(ValueError):
    """A profile or measurement journal is malformed or incomplete."""


def _object_no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in items:
        if key in output:
            raise MeasurementNormalizationError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise MeasurementNormalizationError(
            f"{path} must be a regular non-symlink file"
        )
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                MeasurementNormalizationError(f"non-finite JSON number: {token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MeasurementNormalizationError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise MeasurementNormalizationError(f"{path} must contain one JSON object")
    return value


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise MeasurementNormalizationError("value is not canonical JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise MeasurementNormalizationError(f"{label} field set changed")
    return value


def _integer(
    value: Any,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_NANOSECONDS,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise MeasurementNormalizationError(f"{label} must be an integer in range")
    return value


def _string(value: Any, label: str, pattern: re.Pattern[str] | None = None) -> str:
    if type(value) is not str or not value.strip() or len(value) > 256:
        raise MeasurementNormalizationError(f"{label} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise MeasurementNormalizationError(f"{label} has an invalid identity")
    return value


def _sha256(value: Any, label: str) -> str:
    return _string(value, label, SHA256_RE)


def _seconds(nanoseconds: int) -> float:
    result = nanoseconds / 1_000_000_000.0
    if not math.isfinite(result) or result <= 0.0:
        raise MeasurementNormalizationError(
            "nanosecond duration is not positive finite"
        )
    return result


def _finite_sum(values: list[float], label: str) -> float:
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise MeasurementNormalizationError(f"{label} is not summable") from exc
    if not math.isfinite(result) or result <= 0.0:
        raise MeasurementNormalizationError(f"{label} is not positive finite")
    return result


def _profile(document: dict[str, Any]) -> dict[str, Any]:
    _exact(
        document,
        {
            "schema_id",
            "profile_id",
            "status",
            "expected_manifest_sha256",
            "expected_ordered_case_ids_sha256",
            "expected_ordered_candidate_ids_sha256_by_case",
            "case_count",
            "candidate_denominator",
            "required_backends",
            "required_architecture_count",
            "baseline_gpu_architecture",
            "newer_gpu_architecture_required",
            "allowed_newer_gpu_architectures",
            "parity",
            "sampling",
            "profiling",
            "performance_gate",
            "blockers",
            "authority",
            "profile_sha256",
        },
        "HIP D1 profile",
    )
    if document.get("schema_id") != PROFILE_SCHEMA:
        raise MeasurementNormalizationError("HIP D1 profile schema changed")
    if document.get("profile_id") != PROFILE_ID:
        raise MeasurementNormalizationError("HIP D1 profile identity changed")
    profile_sha256 = _sha256(document.get("profile_sha256"), "profile_sha256")
    projection = dict(document)
    projection.pop("profile_sha256")
    if profile_sha256 != _hash(projection):
        raise MeasurementNormalizationError("HIP D1 profile self-hash mismatch")
    if document.get("case_count") != 32 or document.get("candidate_denominator") != 64:
        raise MeasurementNormalizationError("HIP D1 denominator changed")
    if document.get("required_backends") != ["rust_cpu", "hip_safe", "hip_fast"]:
        raise MeasurementNormalizationError("HIP D1 backend order changed")
    if document.get("authority") != AUTHORITY:
        raise MeasurementNormalizationError("HIP D1 profile authority changed")
    sampling = document.get("sampling")
    profiling = document.get("profiling")
    if type(sampling) is not dict or type(profiling) is not dict:
        raise MeasurementNormalizationError("HIP D1 measurement policy is missing")
    expected_sampling = {
        "minimum_case_samples": 5,
        "minimum_context_samples": 5,
        "minimum_transfer_samples": 5,
        "p50_method": "median",
        "p95_method": "nearest_rank_95",
    }
    if sampling != expected_sampling:
        raise MeasurementNormalizationError("HIP D1 sampling policy changed")
    blockers = document.get("blockers")
    if (
        type(blockers) is not list
        or not blockers
        or any(type(blocker) is not str or not blocker for blocker in blockers)
        or len(set(blockers)) != len(blockers)
    ):
        raise MeasurementNormalizationError("HIP D1 blocker set is invalid")
    expected_profiling = {
        "profiler": "rocprofiler-sdk",
        "kernel_dispatch_trace_required": True,
        "transfer_accounting_required": True,
        "failure_probes_required": True,
        "failure_probe_codes": FAILURE_PROBE_CODES,
        "cpu_fallback_forbidden": True,
        "normalized_trace_schema": PROFILER_TRACE_SCHEMA,
        "normalized_transfer_trace_schema": TRANSFER_TRACE_SCHEMA,
        "required_stage_sequence_per_sample": REQUIRED_STAGE_SEQUENCE,
        "required_kernel_by_stage": REQUIRED_KERNEL_BY_STAGE,
        "cpu_reference_identity_required": True,
    }
    if profiling != expected_profiling:
        raise MeasurementNormalizationError("HIP D1 profiler policy changed")
    return {
        "profile_sha256": profile_sha256,
        "minimum_case_samples": 5,
        "minimum_transfer_samples": 5,
        "required_stages": list(REQUIRED_STAGE_SEQUENCE),
        "required_kernels": dict(REQUIRED_KERNEL_BY_STAGE),
        "blockers": list(blockers),
        "status": document.get("status"),
    }


def _duration(row: dict[str, Any], wall_ns: int, label: str) -> int:
    start = _integer(row["start_offset_nanoseconds"], f"{label}.start")
    end = _integer(row["end_offset_nanoseconds"], f"{label}.end", minimum=1)
    if start >= end or end > wall_ns:
        raise MeasurementNormalizationError(f"{label} is outside the wall-time sample")
    return end - start


def normalize(profile: dict[str, Any], journal: dict[str, Any]) -> dict[str, Any]:
    policy = _profile(profile)
    journal = _exact(
        journal,
        {
            "schema_id",
            "profile_sha256",
            "execution_run_id_sha256",
            "backend",
            "ordered_case_ids",
            "samples",
            "authority",
        },
        "measurement journal",
    )
    if journal["schema_id"] != JOURNAL_SCHEMA:
        raise MeasurementNormalizationError("measurement journal schema changed")
    if (
        _sha256(journal["profile_sha256"], "journal.profile_sha256")
        != policy["profile_sha256"]
    ):
        raise MeasurementNormalizationError("measurement journal/profile cross-wire")
    execution_run_id = _sha256(
        journal["execution_run_id_sha256"], "execution_run_id_sha256"
    )
    backend = _string(journal["backend"], "backend")
    if backend not in GPU_BACKENDS:
        raise MeasurementNormalizationError(
            "measurement journal requires a HIP backend"
        )
    if journal["authority"] != AUTHORITY:
        raise MeasurementNormalizationError("measurement journal authority changed")

    ordered_case_ids = journal["ordered_case_ids"]
    if type(ordered_case_ids) is not list or len(ordered_case_ids) != 32:
        raise MeasurementNormalizationError(
            "measurement journal needs 32 ordered cases"
        )
    case_ids = [
        _string(value, f"ordered_case_ids[{index}]", CASE_RE)
        for index, value in enumerate(ordered_case_ids)
    ]
    if len(set(case_ids)) != 32:
        raise MeasurementNormalizationError(
            "measurement journal case IDs are duplicated"
        )

    samples = journal["samples"]
    if type(samples) is not list:
        raise MeasurementNormalizationError(
            "measurement journal samples must be a list"
        )
    parsed_samples: list[tuple[dict[str, Any], str, int]] = []
    for sample_offset, raw_sample in enumerate(samples):
        sample = _exact(
            raw_sample,
            {
                "case_id",
                "sample_index",
                "wall_time_nanoseconds",
                "dispatches",
                "transfers",
            },
            f"samples[{sample_offset}]",
        )
        parsed_samples.append(
            (
                sample,
                _string(sample["case_id"], "sample.case_id", CASE_RE),
                _integer(sample["sample_index"], "sample.sample_index", maximum=1023),
            )
        )
    cursor = 0
    for expected_case_id in case_ids:
        case_sample_index = 0
        while (
            cursor < len(parsed_samples)
            and parsed_samples[cursor][1] == expected_case_id
        ):
            if parsed_samples[cursor][2] != case_sample_index:
                raise MeasurementNormalizationError(
                    "measurement sample indices must be contiguous from zero"
                )
            cursor += 1
            case_sample_index += 1
        if case_sample_index < policy["minimum_case_samples"]:
            raise MeasurementNormalizationError(
                f"insufficient samples for case {expected_case_id}"
            )
    if cursor != len(parsed_samples):
        raise MeasurementNormalizationError("measurement sample ordering changed")

    profiler_rows: list[dict[str, Any]] = []
    transfer_rows: list[dict[str, Any]] = []
    wall_times_by_case: dict[str, list[float]] = {case_id: [] for case_id in case_ids}
    kernel_runtimes: dict[str, list[float]] = {}
    kernel_order: list[str] = []
    transfer_seconds: dict[str, list[float]] = {"h2d": [], "d2h": []}
    transfer_bytes: dict[str, int] = {"h2d": 0, "d2h": 0}

    for sample_offset, (sample, case_id, sample_index) in enumerate(parsed_samples):
        wall_ns = _integer(
            sample["wall_time_nanoseconds"],
            "sample.wall_time_nanoseconds",
            minimum=1,
        )
        wall_seconds = _seconds(wall_ns)
        wall_times_by_case[case_id].append(wall_seconds)

        dispatches = sample["dispatches"]
        if type(dispatches) is not list or not dispatches:
            raise MeasurementNormalizationError("each sample needs dispatch events")
        observed_required_stages: list[str] = []
        sample_dispatch_seconds: list[float] = []
        sample_dispatch_nanoseconds: list[int] = []
        previous_dispatch_start = -1
        for event_offset, raw_dispatch in enumerate(dispatches):
            dispatch = _exact(
                raw_dispatch,
                {
                    "stage_id",
                    "kernel_name",
                    "start_offset_nanoseconds",
                    "end_offset_nanoseconds",
                },
                f"samples[{sample_offset}].dispatches[{event_offset}]",
            )
            stage_id = _string(dispatch["stage_id"], "dispatch.stage_id", STAGE_RE)
            kernel_name = _string(dispatch["kernel_name"], "dispatch.kernel_name")
            dispatch_start = _integer(
                dispatch["start_offset_nanoseconds"], "dispatch.start"
            )
            if dispatch_start < previous_dispatch_start:
                raise MeasurementNormalizationError(
                    "dispatch events are not in chronological order"
                )
            previous_dispatch_start = dispatch_start
            if stage_id in policy["required_kernels"]:
                observed_required_stages.append(stage_id)
                if kernel_name != policy["required_kernels"][stage_id]:
                    raise MeasurementNormalizationError(
                        f"required stage/kernel mismatch: {stage_id}"
                    )
            runtime_nanoseconds = _duration(
                dispatch, wall_ns, f"dispatch[{event_offset}]"
            )
            runtime = _seconds(runtime_nanoseconds)
            sample_dispatch_seconds.append(runtime)
            sample_dispatch_nanoseconds.append(runtime_nanoseconds)
            if kernel_name not in kernel_runtimes:
                kernel_runtimes[kernel_name] = []
                kernel_order.append(kernel_name)
            kernel_runtimes[kernel_name].append(runtime)
            profiler_rows.append(
                {
                    "dispatch_index": len(profiler_rows),
                    "case_id": case_id,
                    "sample_index": sample_index,
                    "stage_id": stage_id,
                    "kernel_name": kernel_name,
                    "runtime_seconds": runtime,
                }
            )
        if observed_required_stages != policy["required_stages"]:
            raise MeasurementNormalizationError(
                f"required stage sequence changed at {case_id}/sample[{sample_index}]"
            )
        _finite_sum(sample_dispatch_seconds, "sample dispatch runtime")
        if sum(sample_dispatch_nanoseconds) > wall_ns:
            raise MeasurementNormalizationError("dispatch runtime exceeds wall time")

        transfers = sample["transfers"]
        if type(transfers) is not list or not transfers:
            raise MeasurementNormalizationError("each sample needs transfer events")
        sample_transfer_seconds: list[float] = []
        sample_transfer_nanoseconds: list[int] = []
        by_direction: dict[str, list[float]] = {"h2d": [], "d2h": []}
        previous_transfer_start = -1
        for event_offset, raw_transfer in enumerate(transfers):
            transfer = _exact(
                raw_transfer,
                {
                    "direction",
                    "bytes",
                    "start_offset_nanoseconds",
                    "end_offset_nanoseconds",
                },
                f"samples[{sample_offset}].transfers[{event_offset}]",
            )
            direction = _string(transfer["direction"], "transfer.direction")
            if direction not in transfer_bytes:
                raise MeasurementNormalizationError("transfer direction changed")
            transfer_start = _integer(
                transfer["start_offset_nanoseconds"], "transfer.start"
            )
            if transfer_start < previous_transfer_start:
                raise MeasurementNormalizationError(
                    "transfer events are not in chronological order"
                )
            previous_transfer_start = transfer_start
            byte_count = _integer(
                transfer["bytes"],
                "transfer.bytes",
                minimum=1,
                maximum=MAX_EVENT_BYTES,
            )
            runtime_nanoseconds = _duration(
                transfer, wall_ns, f"transfer[{event_offset}]"
            )
            runtime = _seconds(runtime_nanoseconds)
            transfer_bytes[direction] += byte_count
            if transfer_bytes[direction] > MAX_EVENT_BYTES:
                raise MeasurementNormalizationError("transfer byte total overflow")
            by_direction[direction].append(runtime)
            sample_transfer_seconds.append(runtime)
            sample_transfer_nanoseconds.append(runtime_nanoseconds)
            transfer_rows.append(
                {
                    "event_index": len(transfer_rows),
                    "case_id": case_id,
                    "sample_index": sample_index,
                    "direction": direction,
                    "bytes": byte_count,
                    "runtime_seconds": runtime,
                }
            )
        if any(not by_direction[direction] for direction in ("h2d", "d2h")):
            raise MeasurementNormalizationError(
                f"both transfer directions are required at {case_id}/sample[{sample_index}]"
            )
        _finite_sum(sample_transfer_seconds, "sample transfer runtime")
        if sum(sample_transfer_nanoseconds) > wall_ns:
            raise MeasurementNormalizationError("transfer runtime exceeds wall time")
        for direction in ("h2d", "d2h"):
            transfer_seconds[direction].append(
                _finite_sum(by_direction[direction], f"sample {direction} runtime")
            )

    profiler_trace = {
        "schema_id": PROFILER_TRACE_SCHEMA,
        "execution_run_id_sha256": execution_run_id,
        "rows": profiler_rows,
    }
    transfer_trace = {
        "schema_id": TRANSFER_TRACE_SCHEMA,
        "execution_run_id_sha256": execution_run_id,
        "rows": transfer_rows,
    }
    kernel_dispatches = [
        {
            "kernel_name": kernel_name,
            "dispatch_count": len(kernel_runtimes[kernel_name]),
            "total_runtime_seconds": _finite_sum(
                kernel_runtimes[kernel_name], f"{kernel_name} runtime"
            ),
        }
        for kernel_name in kernel_order
    ]
    if len(parsed_samples) < policy["minimum_transfer_samples"]:
        raise MeasurementNormalizationError("insufficient transfer samples")
    output: dict[str, Any] = {
        "schema_id": OUTPUT_SCHEMA,
        "profile_sha256": policy["profile_sha256"],
        "source_journal_sha256": _hash(journal),
        "execution_run_id_sha256": execution_run_id,
        "backend": backend,
        "ordered_case_ids": case_ids,
        "wall_time_seconds_by_case": wall_times_by_case,
        "profiler_trace": profiler_trace,
        "profiler_trace_sha256": _hash(profiler_trace),
        "kernel_dispatches": kernel_dispatches,
        "kernel_dispatch_count": len(profiler_rows),
        "kernel_runtime_seconds": _finite_sum(
            [row["runtime_seconds"] for row in profiler_rows],
            "all kernel runtime",
        ),
        "transfer_trace": transfer_trace,
        "transfer_trace_sha256": _hash(transfer_trace),
        "h2d_bytes": transfer_bytes["h2d"],
        "d2h_bytes": transfer_bytes["d2h"],
        "h2d_seconds": transfer_seconds["h2d"],
        "d2h_seconds": transfer_seconds["d2h"],
        "execution_launched_by_normalizer": False,
        "authority": dict(AUTHORITY),
    }
    output["normalization_sha256"] = _hash(output)
    return output


def profile_only(profile: dict[str, Any]) -> dict[str, Any]:
    policy = _profile(profile)
    return {
        "ok": True,
        "profile_sha256": policy["profile_sha256"],
        "profile_status": policy["status"],
        "blockers": policy["blockers"],
        "execution_performed": False,
        "normalization_performed": False,
        "authority_granted": False,
    }


def _write_absent(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise MeasurementNormalizationError("output path must be absent")
    parent = path.parent.resolve()
    if not parent.is_dir():
        raise MeasurementNormalizationError("output parent must exist")
    target = parent / path.name
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        payload = (
            json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
        ).encode("ascii")
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise MeasurementNormalizationError("output path must be absent") from exc
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        profile = _load(args.profile)
        if args.journal is None:
            if args.output is not None:
                raise MeasurementNormalizationError(
                    "--output requires an explicit --journal"
                )
            result = profile_only(profile)
        else:
            if args.output is None:
                raise MeasurementNormalizationError(
                    "journal normalization requires an absent --output path"
                )
            result = normalize(profile, _load(args.journal))
            _write_absent(args.output, result)
        print(json.dumps(result, allow_nan=False, sort_keys=True))
        return 0
    except MeasurementNormalizationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
