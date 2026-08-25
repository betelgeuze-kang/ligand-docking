#!/usr/bin/env python3
"""Verify the frozen, non-authoritative representative D1 CPU/HIP evidence.

The committed profile is intentionally manifest-unbound. A result can be
checked only after an owner-controlled successor binds the exact private D1
manifest. Verification never executes a GPU and never grants claim authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any

PROFILE_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_profile/1.1.0"
RESULT_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_result/1.1.0"
CASE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GPU_ARCHITECTURE_RE = re.compile(r"^gfx([0-9]{3,5})$")
PCI_DEVICE_ID_RE = re.compile(r"^[0-9a-f]{4}:[0-9a-f]{4}$")
REQUIRED_BACKENDS = ("rust_cpu", "hip_safe", "hip_fast")
PARITY_DIGEST_FIELDS = (
    "decision_sha256",
    "typed_failure_sha256",
    "score_order_sha256",
    "validity_sha256",
    "rank_sha256",
    "cluster_sha256",
)
SCIENTIFIC_FIELDS = (
    "score",
    "proposal_rmsd_angstrom",
    "final_rmsd_angstrom",
)
FAILURE_PROBE_CODES = (
    "backend_unavailable",
    "device_oom",
    "execution_timeout",
    "numeric_overflow",
)
AUTHORITY_KEYS = (
    "device_execution_authorized",
    "gpu_acceleration_claim_authorized",
    "scientific_claim_authorized",
    "benchmark_claim_authorized",
    "product_authorized",
    "production_authorized",
    "reservation_authorized",
    "molecular_ab_authorized",
    "fresh128_authorized",
    "stage0_authorized",
)
UNBOUND_STATUS = "frozen_non_authoritative_manifest_not_bound"
BOUND_STATUS = "frozen_non_authoritative_manifest_bound"
UNBOUND_BLOCKERS = (
    "d1_manifest_not_materialized",
    "hip_device_evidence_not_supplied",
    "hip_device_execution_not_authorized",
)
BOUND_BLOCKERS = (
    "hip_device_evidence_not_supplied",
    "hip_device_execution_not_authorized",
)


class HipBenchmarkError(ValueError):
    """The HIP D1 benchmark profile or result is inconsistent."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise HipBenchmarkError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except HipBenchmarkError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HipBenchmarkError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise HipBenchmarkError("JSON root must be object")
    return value


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _exact_keys(value: Any, expected: set[str], name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise HipBenchmarkError(f"{name} must be object")
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise HipBenchmarkError(f"{name} field set: missing={missing} extra={extra}")
    return value


def _exact_list(value: Any, expected: tuple[str, ...], name: str) -> None:
    if type(value) is not list or value != list(expected):
        raise HipBenchmarkError(f"{name} policy changed")


def _sha256(value: Any, name: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise HipBenchmarkError(f"{name} must be lowercase SHA-256")
    return value


def _nonempty_string(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise HipBenchmarkError(f"{name} must be nonempty string")
    return value


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise HipBenchmarkError(f"{name} must be integer >= {minimum}")
    return value


def _finite(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HipBenchmarkError(f"{name} must be finite number")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0.0):
        qualifier = "positive " if positive else ""
        raise HipBenchmarkError(f"{name} must be {qualifier}finite number")
    return number


def _samples(
    value: Any,
    name: str,
    minimum_count: int,
    *,
    allow_empty: bool = False,
) -> list[float]:
    if type(value) is not list:
        raise HipBenchmarkError(f"{name} must be list")
    if allow_empty and not value:
        return []
    if len(value) < minimum_count:
        raise HipBenchmarkError(f"{name}: insufficient samples")
    return [
        _finite(item, f"{name}[{index}]", positive=True)
        for index, item in enumerate(value)
    ]


def _case_id(value: Any, name: str) -> str:
    if type(value) is not str or CASE_ID_RE.fullmatch(value) is None:
        raise HipBenchmarkError(f"{name} is not a valid case ID")
    return value


def _authority(value: Any, name: str) -> None:
    document = _exact_keys(value, set(AUTHORITY_KEYS), name)
    if any(document[key] is not False for key in AUTHORITY_KEYS):
        raise HipBenchmarkError(f"{name} escalated")


def _profile_projection(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in profile.items() if key != "profile_sha256"}


def _verify_profile_document(profile: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(
        profile,
        {
            "schema_id",
            "profile_id",
            "status",
            "expected_manifest_sha256",
            "case_count",
            "candidate_denominator",
            "required_backends",
            "required_architecture_count",
            "baseline_gpu_architecture",
            "newer_gpu_architecture_required",
            "parity",
            "sampling",
            "profiling",
            "performance_gate",
            "blockers",
            "authority",
            "profile_sha256",
        },
        "profile",
    )
    if profile["schema_id"] != PROFILE_SCHEMA:
        raise HipBenchmarkError("profile identity")
    if profile["profile_id"] != "engine_v2_hip_d1_representative_v1":
        raise HipBenchmarkError("profile ID")
    _integer(profile["case_count"], "profile.case_count", minimum=1)
    _integer(
        profile["candidate_denominator"],
        "profile.candidate_denominator",
        minimum=1,
    )
    if profile["case_count"] != 32 or profile["candidate_denominator"] != 64:
        raise HipBenchmarkError("frozen cohort/denominator policy changed")
    _exact_list(profile["required_backends"], REQUIRED_BACKENDS, "required backend")
    if profile["required_architecture_count"] != 2:
        raise HipBenchmarkError("required architecture count changed")
    if profile["baseline_gpu_architecture"] != "gfx1030":
        raise HipBenchmarkError("baseline GPU architecture changed")
    if profile["newer_gpu_architecture_required"] is not True:
        raise HipBenchmarkError("newer GPU architecture policy changed")

    parity = _exact_keys(
        profile["parity"],
        {
            "digest_fields",
            "scientific_fields",
            "scientific_vector_order",
            "absolute_tolerance",
            "relative_tolerance",
            "nonfinite_values_allowed",
            "typed_failure_scientific_value_encoding",
            "no_denominator_deletion",
            "repeat_stability_required",
            "cpu_cross_architecture_parity_required",
        },
        "profile.parity",
    )
    _exact_list(parity["digest_fields"], PARITY_DIGEST_FIELDS, "parity digest")
    _exact_list(parity["scientific_fields"], SCIENTIFIC_FIELDS, "scientific field")
    if parity["scientific_vector_order"] != "slot_major_field_order":
        raise HipBenchmarkError("scientific vector ordering changed")
    if (
        parity["typed_failure_scientific_value_encoding"]
        != "json_null_for_complete_slot_triple"
    ):
        raise HipBenchmarkError("typed-failure scientific encoding changed")
    if (
        _finite(parity["absolute_tolerance"], "absolute tolerance", positive=True)
        != 1e-10
    ):
        raise HipBenchmarkError("absolute tolerance changed")
    if (
        _finite(parity["relative_tolerance"], "relative tolerance", positive=True)
        != 4e-12
    ):
        raise HipBenchmarkError("relative tolerance changed")
    for key in (
        "nonfinite_values_allowed",
        "no_denominator_deletion",
        "repeat_stability_required",
        "cpu_cross_architecture_parity_required",
    ):
        expected = key != "nonfinite_values_allowed"
        if parity[key] is not expected:
            raise HipBenchmarkError(f"parity policy changed: {key}")

    sampling = _exact_keys(
        profile["sampling"],
        {
            "minimum_case_samples",
            "minimum_context_samples",
            "minimum_transfer_samples",
            "p50_method",
            "p95_method",
        },
        "profile.sampling",
    )
    for key in (
        "minimum_case_samples",
        "minimum_context_samples",
        "minimum_transfer_samples",
    ):
        if sampling[key] != 5:
            raise HipBenchmarkError(f"sampling policy changed: {key}")
    if (
        sampling["p50_method"] != "median"
        or sampling["p95_method"] != "nearest_rank_95"
    ):
        raise HipBenchmarkError("sampling statistic policy changed")

    profiling = _exact_keys(
        profile["profiling"],
        {
            "profiler",
            "kernel_dispatch_trace_required",
            "transfer_accounting_required",
            "failure_probes_required",
            "failure_probe_codes",
            "cpu_fallback_forbidden",
        },
        "profile.profiling",
    )
    if profiling["profiler"] != "rocprofiler-sdk":
        raise HipBenchmarkError("profiler policy changed")
    for key in (
        "kernel_dispatch_trace_required",
        "transfer_accounting_required",
        "failure_probes_required",
        "cpu_fallback_forbidden",
    ):
        if profiling[key] is not True:
            raise HipBenchmarkError(f"profiling policy changed: {key}")
    _exact_list(profiling["failure_probe_codes"], FAILURE_PROBE_CODES, "failure probe")

    gate = _exact_keys(
        profile["performance_gate"],
        {
            "reference_backend",
            "candidate_backend",
            "statistic",
            "maximum_ratio_numerator",
            "maximum_ratio_denominator",
            "strictly_less_than_ratio",
            "minimum_passing_case_count",
        },
        "profile.performance_gate",
    )
    for key in (
        "maximum_ratio_numerator",
        "maximum_ratio_denominator",
        "minimum_passing_case_count",
    ):
        _integer(gate[key], f"profile.performance_gate.{key}", minimum=1)
    if (
        gate["reference_backend"] != "rust_cpu"
        or gate["candidate_backend"] != "hip_fast"
        or gate["statistic"] != "per_case_median_wall_time_seconds"
        or gate["maximum_ratio_numerator"] != 1
        or gate["maximum_ratio_denominator"] != 1
        or gate["strictly_less_than_ratio"] is not True
        or gate["minimum_passing_case_count"] != 1
    ):
        raise HipBenchmarkError("performance gate policy changed")

    expected_manifest = profile["expected_manifest_sha256"]
    if expected_manifest is None:
        if profile["status"] != UNBOUND_STATUS or profile["blockers"] != list(
            UNBOUND_BLOCKERS
        ):
            raise HipBenchmarkError("unbound profile state")
    else:
        _sha256(expected_manifest, "profile.expected_manifest_sha256")
        if profile["status"] != BOUND_STATUS or profile["blockers"] != list(
            BOUND_BLOCKERS
        ):
            raise HipBenchmarkError("bound profile state")
    _authority(profile["authority"], "profile.authority")
    profile_sha256 = _sha256(profile["profile_sha256"], "profile.profile_sha256")
    if profile_sha256 != _canonical_sha256(_profile_projection(profile)):
        raise HipBenchmarkError("profile SHA-256 mismatch")
    return {
        "verified": True,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha256,
        "manifest_bound": expected_manifest is not None,
        "result_verification_authorized": expected_manifest is not None,
        "device_execution_authorized": False,
        "claim_authority_granted": False,
    }


def verify_profile(profile_path: Path) -> dict[str, Any]:
    """Verify a profile without accepting or executing benchmark evidence."""

    return _verify_profile_document(_load(profile_path))


def _scientific_values(
    value: Any, name: str, expected_length: int
) -> list[float | None]:
    if type(value) is not list or len(value) != expected_length:
        raise HipBenchmarkError(f"{name}: scientific vector shape")
    output: list[float | None] = []
    for slot in range(expected_length // len(SCIENTIFIC_FIELDS)):
        start = slot * len(SCIENTIFIC_FIELDS)
        triple = value[start : start + len(SCIENTIFIC_FIELDS)]
        if all(item is None for item in triple):
            output.extend([None] * len(SCIENTIFIC_FIELDS))
            continue
        if any(item is None for item in triple):
            raise HipBenchmarkError(
                f"{name}: partial typed-failure scientific slot {slot}"
            )
        output.extend(
            _finite(item, f"{name}[{index}]")
            for index, item in enumerate(triple, start=start)
        )
    return output


def _compare_case(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    label: str,
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> None:
    if reference["case_id"] != candidate["case_id"]:
        raise HipBenchmarkError(f"{label}: case ordering mismatch")
    for key in PARITY_DIGEST_FIELDS:
        if reference[key] != candidate[key]:
            raise HipBenchmarkError(f"{label}: discrete parity: {key}")
    for index, (reference_value, candidate_value) in enumerate(
        zip(
            reference["scientific_values"],
            candidate["scientific_values"],
            strict=True,
        )
    ):
        if reference_value is None or candidate_value is None:
            if reference_value is not None or candidate_value is not None:
                raise HipBenchmarkError(
                    f"{label}: scientific availability parity at index {index}"
                )
            continue
        if not math.isclose(
            reference_value,
            candidate_value,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        ):
            raise HipBenchmarkError(f"{label}: numerical parity at index {index}")


def _nearest_rank_95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _verify_failure_probes(value: Any, architecture: str) -> None:
    if type(value) is not list or len(value) != len(FAILURE_PROBE_CODES) * 2:
        raise HipBenchmarkError(f"{architecture}: failure probe coverage")
    observed: set[tuple[str, str]] = set()
    for index, raw in enumerate(value):
        probe = _exact_keys(
            raw,
            {
                "backend",
                "error_code",
                "observed_error_sha256",
                "cpu_fallback_observed",
                "claim_authority_granted",
            },
            f"{architecture}.failure_probes[{index}]",
        )
        pair = (probe["backend"], probe["error_code"])
        if pair in observed:
            raise HipBenchmarkError(f"{architecture}: duplicate failure probe")
        observed.add(pair)
        _sha256(probe["observed_error_sha256"], f"{architecture}.failure_probe SHA")
        if probe["cpu_fallback_observed"] is not False:
            raise HipBenchmarkError(f"{architecture}: CPU fallback observed")
        if probe["claim_authority_granted"] is not False:
            raise HipBenchmarkError(
                f"{architecture}: failure probe authority escalated"
            )
    expected = {
        (backend, code)
        for backend in REQUIRED_BACKENDS[1:]
        for code in FAILURE_PROBE_CODES
    }
    if observed != expected:
        raise HipBenchmarkError(f"{architecture}: failure probe set")


def _verify_case(
    raw: Any,
    label: str,
    case_id: str,
    denominator: int,
    minimum_samples: int,
    scientific_length: int,
) -> dict[str, Any]:
    expected_keys = {
        "case_id",
        "candidate_count",
        "scientific_values",
        "repeat_scientific_values",
        "wall_time_seconds",
        *PARITY_DIGEST_FIELDS,
        *(f"repeat_{field}" for field in PARITY_DIGEST_FIELDS),
    }
    case = _exact_keys(raw, expected_keys, label)
    if _case_id(case["case_id"], f"{label}.case_id") != case_id:
        raise HipBenchmarkError(f"{label}: ordered cohort mismatch")
    if (
        type(case["candidate_count"]) is not int
        or case["candidate_count"] != denominator
    ):
        raise HipBenchmarkError(f"{label}: candidate denominator deletion")
    for field in PARITY_DIGEST_FIELDS:
        digest = _sha256(case[field], f"{label}.{field}")
        repeat = _sha256(case[f"repeat_{field}"], f"{label}.repeat_{field}")
        if digest != repeat:
            raise HipBenchmarkError(f"{label}: repeat stability: {field}")
    scientific = _scientific_values(case["scientific_values"], label, scientific_length)
    repeat_scientific = _scientific_values(
        case["repeat_scientific_values"],
        f"{label}.repeat",
        scientific_length,
    )
    if scientific != repeat_scientific:
        raise HipBenchmarkError(f"{label}: repeat scientific stability")
    wall_times = _samples(
        case["wall_time_seconds"],
        f"{label}.wall_time_seconds",
        minimum_samples,
    )
    return {**case, "scientific_values": scientific, "wall_time_seconds": wall_times}


def _verify_backend(
    raw: Any,
    *,
    architecture: str,
    backend_name: str,
    ordered_case_ids: list[str],
    denominator: int,
    sampling: dict[str, Any],
    scientific_length: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    label = f"{architecture}/{backend_name}"
    backend = _exact_keys(
        raw,
        {
            "backend_name",
            "candidate_denominator",
            "context_construction_seconds",
            "peak_rss_bytes",
            "peak_vram_bytes",
            "h2d_bytes",
            "d2h_bytes",
            "h2d_seconds",
            "d2h_seconds",
            "runtime_failure_counts",
            "profiler_trace_sha256",
            "kernel_dispatches",
            "cases",
        },
        label,
    )
    if backend["backend_name"] != backend_name:
        raise HipBenchmarkError(f"{label}: backend identity")
    if (
        type(backend["candidate_denominator"]) is not int
        or backend["candidate_denominator"] != denominator
    ):
        raise HipBenchmarkError(f"{label}: candidate denominator")
    context_samples = _samples(
        backend["context_construction_seconds"],
        f"{label}.context_construction_seconds",
        sampling["minimum_context_samples"],
    )
    peak_rss = _integer(backend["peak_rss_bytes"], f"{label}.peak_rss_bytes", minimum=1)
    peak_vram = _integer(backend["peak_vram_bytes"], f"{label}.peak_vram_bytes")
    h2d_bytes = _integer(backend["h2d_bytes"], f"{label}.h2d_bytes")
    d2h_bytes = _integer(backend["d2h_bytes"], f"{label}.d2h_bytes")
    failure_counts = _exact_keys(
        backend["runtime_failure_counts"],
        {"success", *FAILURE_PROBE_CODES},
        f"{label}.runtime_failure_counts",
    )
    for code, count in failure_counts.items():
        _integer(count, f"{label}.runtime_failure_counts.{code}")
    if failure_counts["success"] != len(ordered_case_ids):
        raise HipBenchmarkError(f"{label}: runtime success denominator")
    if any(failure_counts[code] != 0 for code in FAILURE_PROBE_CODES):
        raise HipBenchmarkError(f"{label}: representative runtime failure")

    if backend_name == "rust_cpu":
        if peak_vram != 0 or h2d_bytes != 0 or d2h_bytes != 0:
            raise HipBenchmarkError(f"{label}: CPU transfer/VRAM accounting")
        h2d_samples = _samples(
            backend["h2d_seconds"],
            f"{label}.h2d_seconds",
            0,
            allow_empty=True,
        )
        d2h_samples = _samples(
            backend["d2h_seconds"],
            f"{label}.d2h_seconds",
            0,
            allow_empty=True,
        )
        if h2d_samples or d2h_samples or backend["profiler_trace_sha256"] is not None:
            raise HipBenchmarkError(f"{label}: CPU profiler/transfer evidence")
        if backend["kernel_dispatches"] != []:
            raise HipBenchmarkError(f"{label}: CPU kernel trace")
        kernel_total = 0.0
        kernel_dispatch_total = 0
    else:
        if peak_vram <= 0 or h2d_bytes <= 0 or d2h_bytes <= 0:
            raise HipBenchmarkError(f"{label}: missing GPU transfer/VRAM accounting")
        h2d_samples = _samples(
            backend["h2d_seconds"],
            f"{label}.h2d_seconds",
            sampling["minimum_transfer_samples"],
        )
        d2h_samples = _samples(
            backend["d2h_seconds"],
            f"{label}.d2h_seconds",
            sampling["minimum_transfer_samples"],
        )
        _sha256(
            backend["profiler_trace_sha256"],
            f"{label}.profiler_trace_sha256",
        )
        dispatches = backend["kernel_dispatches"]
        if type(dispatches) is not list or not dispatches:
            raise HipBenchmarkError(f"{label}: kernel dispatch trace required")
        names: set[str] = set()
        kernel_total = 0.0
        kernel_dispatch_total = 0
        for index, raw_dispatch in enumerate(dispatches):
            dispatch = _exact_keys(
                raw_dispatch,
                {"kernel_name", "dispatch_count", "total_runtime_seconds"},
                f"{label}.kernel_dispatches[{index}]",
            )
            name = _nonempty_string(dispatch["kernel_name"], f"{label}.kernel_name")
            if name in names:
                raise HipBenchmarkError(f"{label}: duplicate kernel name")
            names.add(name)
            kernel_dispatch_total += _integer(
                dispatch["dispatch_count"],
                f"{label}.{name}.dispatch_count",
                minimum=1,
            )
            kernel_total += _finite(
                dispatch["total_runtime_seconds"],
                f"{label}.{name}.runtime",
                positive=True,
            )

    cases_raw = backend["cases"]
    if type(cases_raw) is not list or len(cases_raw) != len(ordered_case_ids):
        raise HipBenchmarkError(f"{label}: exact case denominator required")
    cases = [
        _verify_case(
            raw_case,
            f"{label}/case[{index}]",
            case_id,
            denominator,
            sampling["minimum_case_samples"],
            scientific_length,
        )
        for index, (raw_case, case_id) in enumerate(
            zip(cases_raw, ordered_case_ids, strict=True)
        )
    ]
    all_wall_times = [sample for case in cases for sample in case["wall_time_seconds"]]
    case_medians = [statistics.median(case["wall_time_seconds"]) for case in cases]
    total_candidates = denominator * sum(
        len(case["wall_time_seconds"]) for case in cases
    )
    return cases, {
        "context_construction_seconds_p50": statistics.median(context_samples),
        "case_wall_time_seconds_p50": statistics.median(case_medians),
        "case_wall_time_seconds_p95": _nearest_rank_95(case_medians),
        "candidate_throughput_per_second": total_candidates / sum(all_wall_times),
        "peak_rss_bytes": peak_rss,
        "peak_vram_bytes": peak_vram,
        "h2d_bytes": h2d_bytes,
        "d2h_bytes": d2h_bytes,
        "h2d_seconds_p50": statistics.median(h2d_samples) if h2d_samples else 0.0,
        "d2h_seconds_p50": statistics.median(d2h_samples) if d2h_samples else 0.0,
        "kernel_dispatch_count_total": kernel_dispatch_total,
        "kernel_runtime_seconds_total": kernel_total,
    }


def verify(profile_path: Path, result_path: Path) -> dict[str, Any]:
    """Verify a completed result against an exact manifest-bound profile."""

    profile = _load(profile_path)
    profile_summary = _verify_profile_document(profile)
    if not profile_summary["manifest_bound"]:
        raise HipBenchmarkError(
            "profile manifest is not bound; result verification refused"
        )
    result = _load(result_path)
    _exact_keys(
        result,
        {
            "schema_id",
            "profile_id",
            "profile_sha256",
            "manifest_sha256",
            "ordered_case_ids",
            "ordered_case_ids_sha256",
            "architectures",
            "authority",
            "output_claim_authorized",
        },
        "result",
    )
    if result["schema_id"] != RESULT_SCHEMA:
        raise HipBenchmarkError("result identity")
    if result["profile_id"] != profile["profile_id"]:
        raise HipBenchmarkError("profile cross-wire")
    if result["profile_sha256"] != profile["profile_sha256"]:
        raise HipBenchmarkError("profile SHA cross-wire")
    manifest_sha256 = _sha256(result["manifest_sha256"], "result.manifest_sha256")
    if manifest_sha256 != profile["expected_manifest_sha256"]:
        raise HipBenchmarkError("manifest/profile cross-wire")
    ordered_case_ids_raw = result["ordered_case_ids"]
    if (
        type(ordered_case_ids_raw) is not list
        or len(ordered_case_ids_raw) != profile["case_count"]
    ):
        raise HipBenchmarkError("ordered case denominator")
    ordered_case_ids = [
        _case_id(value, f"result.ordered_case_ids[{index}]")
        for index, value in enumerate(ordered_case_ids_raw)
    ]
    if len(set(ordered_case_ids)) != len(ordered_case_ids):
        raise HipBenchmarkError("duplicate ordered case ID")
    if _sha256(
        result["ordered_case_ids_sha256"], "ordered_case_ids_sha256"
    ) != _canonical_sha256(ordered_case_ids):
        raise HipBenchmarkError("ordered case identity SHA-256 mismatch")
    _authority(result["authority"], "result.authority")
    if result["output_claim_authorized"] is not False:
        raise HipBenchmarkError("output claim authority escalated")

    architectures = result["architectures"]
    if (
        type(architectures) is not list
        or len(architectures) < profile["required_architecture_count"]
    ):
        raise HipBenchmarkError("insufficient GPU architectures")
    seen_architectures: set[str] = set()
    architecture_ranks: dict[str, int] = {}
    canonical_cpu_cases: list[dict[str, Any]] | None = None
    derived_metrics: dict[str, Any] = {}
    scientific_length = profile["candidate_denominator"] * len(SCIENTIFIC_FIELDS)
    absolute_tolerance = profile["parity"]["absolute_tolerance"]
    relative_tolerance = profile["parity"]["relative_tolerance"]

    for architecture_index, raw_architecture in enumerate(architectures):
        architecture = _exact_keys(
            raw_architecture,
            {
                "gpu_architecture",
                "architecture_generation_rank",
                "gpu_model",
                "pci_device_id",
                "device_serial_sha256",
                "total_vram_bytes",
                "rocm_version",
                "driver_version",
                "rust_version",
                "hip_compiler_version",
                "wheel_sha256",
                "native_extension_sha256",
                "native_binary_sha256",
                "profiler_version",
                "failure_probes",
                "backends",
            },
            f"architectures[{architecture_index}]",
        )
        architecture_name = _nonempty_string(
            architecture["gpu_architecture"], "gpu_architecture"
        )
        architecture_match = GPU_ARCHITECTURE_RE.fullmatch(architecture_name)
        if architecture_match is None:
            raise HipBenchmarkError("invalid GPU architecture identity")
        if architecture_name in seen_architectures:
            raise HipBenchmarkError("duplicate GPU architecture")
        seen_architectures.add(architecture_name)
        architecture_ranks[architecture_name] = _integer(
            architecture["architecture_generation_rank"],
            f"{architecture_name}.architecture_generation_rank",
            minimum=1,
        )
        if architecture_ranks[architecture_name] != int(architecture_match.group(1)):
            raise HipBenchmarkError(
                f"{architecture_name}: architecture generation rank mismatch"
            )
        for identity in (
            "gpu_model",
            "rocm_version",
            "driver_version",
            "rust_version",
            "hip_compiler_version",
            "profiler_version",
        ):
            _nonempty_string(architecture[identity], f"{architecture_name}.{identity}")
        pci_device_id = _nonempty_string(
            architecture["pci_device_id"], f"{architecture_name}.pci_device_id"
        )
        if PCI_DEVICE_ID_RE.fullmatch(pci_device_id) is None:
            raise HipBenchmarkError(f"{architecture_name}: invalid PCI device ID")
        if not architecture["profiler_version"].startswith("rocprofiler-sdk "):
            raise HipBenchmarkError(f"{architecture_name}: profiler identity")
        for digest in (
            "device_serial_sha256",
            "wheel_sha256",
            "native_extension_sha256",
            "native_binary_sha256",
        ):
            _sha256(architecture[digest], f"{architecture_name}.{digest}")
        _integer(
            architecture["total_vram_bytes"],
            f"{architecture_name}.total_vram_bytes",
            minimum=1,
        )
        _verify_failure_probes(architecture["failure_probes"], architecture_name)
        backends = _exact_keys(
            architecture["backends"],
            set(REQUIRED_BACKENDS),
            f"{architecture_name}.backends",
        )
        verified_backends: dict[str, list[dict[str, Any]]] = {}
        architecture_metrics: dict[str, Any] = {}
        for backend_name in REQUIRED_BACKENDS:
            cases, metrics = _verify_backend(
                backends[backend_name],
                architecture=architecture_name,
                backend_name=backend_name,
                ordered_case_ids=ordered_case_ids,
                denominator=profile["candidate_denominator"],
                sampling=profile["sampling"],
                scientific_length=scientific_length,
            )
            verified_backends[backend_name] = cases
            architecture_metrics[backend_name] = metrics
            if metrics["peak_vram_bytes"] > architecture["total_vram_bytes"]:
                raise HipBenchmarkError(
                    f"{architecture_name}/{backend_name}: peak VRAM exceeds device"
                )
        cpu_cases = verified_backends["rust_cpu"]
        if canonical_cpu_cases is None:
            canonical_cpu_cases = cpu_cases
        else:
            for index, (reference, candidate) in enumerate(
                zip(canonical_cpu_cases, cpu_cases, strict=True)
            ):
                _compare_case(
                    reference,
                    candidate,
                    f"{architecture_name}/rust_cpu_cross_architecture/case[{index}]",
                    absolute_tolerance=absolute_tolerance,
                    relative_tolerance=relative_tolerance,
                )
        for backend_name in REQUIRED_BACKENDS[1:]:
            for index, (reference, candidate) in enumerate(
                zip(cpu_cases, verified_backends[backend_name], strict=True)
            ):
                _compare_case(
                    reference,
                    candidate,
                    f"{architecture_name}/{backend_name}/case[{index}]",
                    absolute_tolerance=absolute_tolerance,
                    relative_tolerance=relative_tolerance,
                )
        passing_cases = sum(
            statistics.median(fast["wall_time_seconds"])
            < statistics.median(cpu["wall_time_seconds"])
            for cpu, fast in zip(cpu_cases, verified_backends["hip_fast"], strict=True)
        )
        if passing_cases < profile["performance_gate"]["minimum_passing_case_count"]:
            raise HipBenchmarkError(
                f"{architecture_name}: predeclared hip_fast speed gate"
            )
        architecture_metrics["hip_fast_speed_gate_passing_case_count"] = passing_cases
        derived_metrics[architecture_name] = architecture_metrics

    baseline = profile["baseline_gpu_architecture"]
    if baseline not in architecture_ranks:
        raise HipBenchmarkError("baseline gfx1030 architecture missing")
    if architecture_ranks[baseline] != 1030:
        raise HipBenchmarkError("baseline architecture rank mismatch")
    if not any(
        rank > architecture_ranks[baseline] for rank in architecture_ranks.values()
    ):
        raise HipBenchmarkError("newer GPU architecture missing")
    return {
        "verified": True,
        "profile_sha256": profile["profile_sha256"],
        "manifest_sha256": manifest_sha256,
        "architecture_count": len(seen_architectures),
        "case_count": profile["case_count"],
        "candidate_denominator": profile["candidate_denominator"],
        "derived_metrics": derived_metrics,
        "device_execution_authorized": False,
        "claim_authority_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        output = (
            verify_profile(args.profile)
            if args.result is None
            else verify(args.profile, args.result)
        )
    except HipBenchmarkError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
