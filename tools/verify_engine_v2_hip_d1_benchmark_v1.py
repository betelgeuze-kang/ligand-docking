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
from typing import Any

PROFILE_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_profile/1.2.0"
RESULT_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_result/1.2.0"
CASE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GPU_ARCHITECTURE_RE = re.compile(r"^gfx[0-9a-z]{2,8}$")
PCI_DEVICE_ID_RE = re.compile(r"^[0-9a-f]{4}:[0-9a-f]{4}$")
ROCPROFILER_VERSION_RE = re.compile(
    r"^rocprofiler-sdk [0-9]+(?:\.[0-9]+){1,3}(?:[-+][A-Za-z0-9.-]+)?$"
)
REQUIRED_BACKENDS = ("rust_cpu", "hip_safe", "hip_fast")
PARITY_DIGEST_FIELDS = (
    "decision_sha256",
    "typed_failure_sha256",
    "score_order_sha256",
    "validity_sha256",
    "rank_sha256",
    "cluster_sha256",
)
DERIVED_DISCRETE_FIELDS = (
    "decision",
    "score_order",
    "validity",
    "rank",
    "cluster",
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
ALLOWED_NEWER_GPU_ARCHITECTURES = (
    "gfx90a",
    "gfx940",
    "gfx941",
    "gfx942",
    "gfx950",
    "gfx1100",
    "gfx1101",
    "gfx1102",
    "gfx1150",
    "gfx1151",
    "gfx1200",
    "gfx1201",
)
FAILURE_OBSERVATION_SCHEMA = "betelgeuze.engine_v2_hip_failure_observation/1.0.0"
EXECUTION_BACKEND_RECEIPT_SCHEMA = (
    "betelgeuze.engine_v2_hip_execution_backend_receipt/1.1.0"
)
NORMALIZED_PROFILER_TRACE_SCHEMA = (
    "betelgeuze.engine_v2_rocprofiler_normalized_dispatch_trace/1.0.0"
)
NORMALIZED_TRANSFER_TRACE_SCHEMA = (
    "betelgeuze.engine_v2_hip_normalized_transfer_trace/1.0.0"
)
# Intentionally empty until an owner-reviewed successor pins exact artifacts.
AUTHORIZED_BOUND_PROFILE_SHA256S: frozenset[str] = frozenset()
AUTHORIZED_RESULT_SHA256S: frozenset[str] = frozenset()


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
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise HipBenchmarkError(f"{name} must be finite number") from exc
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


def _result_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "result_sha256"}


def _verify_profile_document(profile: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(
        profile,
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
    _exact_list(
        profile["allowed_newer_gpu_architectures"],
        ALLOWED_NEWER_GPU_ARCHITECTURES,
        "allowed newer GPU architecture",
    )

    parity = _exact_keys(
        profile["parity"],
        {
            "digest_fields",
            "derived_discrete_fields",
            "scientific_fields",
            "scientific_vector_order",
            "score_order_policy",
            "absolute_tolerance",
            "relative_tolerance",
            "nonfinite_values_allowed",
            "typed_failure_scientific_value_encoding",
            "minimum_scored_candidates_per_case",
            "no_denominator_deletion",
            "repeat_stability_required",
            "cpu_cross_architecture_parity_required",
        },
        "profile.parity",
    )
    _exact_list(parity["digest_fields"], PARITY_DIGEST_FIELDS, "parity digest")
    _exact_list(
        parity["derived_discrete_fields"],
        DERIVED_DISCRETE_FIELDS,
        "derived discrete field",
    )
    _exact_list(parity["scientific_fields"], SCIENTIFIC_FIELDS, "scientific field")
    if parity["scientific_vector_order"] != "slot_major_field_order":
        raise HipBenchmarkError("scientific vector ordering changed")
    if parity["score_order_policy"] != "ascending_score_then_slot_index":
        raise HipBenchmarkError("score order policy changed")
    if (
        parity["typed_failure_scientific_value_encoding"]
        != "json_null_for_complete_slot_triple"
    ):
        raise HipBenchmarkError("typed-failure scientific encoding changed")
    minimum_scored = _integer(
        parity["minimum_scored_candidates_per_case"],
        "minimum scored candidates per case",
        minimum=1,
    )
    if minimum_scored != 1 or minimum_scored > profile["candidate_denominator"]:
        raise HipBenchmarkError("minimum scored candidate policy changed")
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
            "normalized_trace_schema",
            "normalized_transfer_trace_schema",
            "cpu_reference_identity_required",
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
        "cpu_reference_identity_required",
    ):
        if profiling[key] is not True:
            raise HipBenchmarkError(f"profiling policy changed: {key}")
    _exact_list(profiling["failure_probe_codes"], FAILURE_PROBE_CODES, "failure probe")
    if profiling["normalized_trace_schema"] != NORMALIZED_PROFILER_TRACE_SCHEMA:
        raise HipBenchmarkError("normalized profiler trace schema changed")
    if (
        profiling["normalized_transfer_trace_schema"]
        != NORMALIZED_TRANSFER_TRACE_SCHEMA
    ):
        raise HipBenchmarkError("normalized transfer trace schema changed")

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
    expected_case_ids = profile["expected_ordered_case_ids_sha256"]
    expected_candidate_ids = profile["expected_ordered_candidate_ids_sha256_by_case"]
    if expected_manifest is None:
        if (
            profile["status"] != UNBOUND_STATUS
            or profile["blockers"] != list(UNBOUND_BLOCKERS)
            or expected_case_ids is not None
            or expected_candidate_ids is not None
        ):
            raise HipBenchmarkError("unbound profile state")
    else:
        _sha256(expected_manifest, "profile.expected_manifest_sha256")
        _sha256(expected_case_ids, "profile.expected_ordered_case_ids_sha256")
        if (
            type(expected_candidate_ids) is not dict
            or len(expected_candidate_ids) != profile["case_count"]
        ):
            raise HipBenchmarkError("profile candidate identity map")
        for case_id, digest in expected_candidate_ids.items():
            _case_id(case_id, "profile candidate identity case")
            _sha256(digest, f"profile candidate identity {case_id}")
        if profile["status"] != BOUND_STATUS or profile["blockers"] != list(
            BOUND_BLOCKERS
        ):
            raise HipBenchmarkError("bound profile state")
    _authority(profile["authority"], "profile.authority")
    profile_sha256 = _sha256(profile["profile_sha256"], "profile.profile_sha256")
    if profile_sha256 != _canonical_sha256(_profile_projection(profile)):
        raise HipBenchmarkError("profile SHA-256 mismatch")
    repository_authorized = profile_sha256 in AUTHORIZED_BOUND_PROFILE_SHA256S
    return {
        "verified": True,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha256,
        "manifest_bound": expected_manifest is not None,
        "result_verification_authorized": (
            expected_manifest is not None and repository_authorized
        ),
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
        finite_triple = [
            _finite(item, f"{name}[{index}]")
            for index, item in enumerate(triple, start=start)
        ]
        if finite_triple[1] < 0.0 or finite_triple[2] < 0.0:
            raise HipBenchmarkError(f"{name}: RMSD must be nonnegative at slot {slot}")
        output.extend(finite_triple)
    return output


def _candidate_statuses(
    value: Any, name: str, denominator: int
) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) != denominator:
        raise HipBenchmarkError(f"{name}: candidate status denominator")
    output: list[dict[str, Any]] = []
    for slot_index, raw_status in enumerate(value):
        status = _exact_keys(
            raw_status,
            {"slot_index", "status", "failure_code"},
            f"{name}[{slot_index}]",
        )
        if type(status["slot_index"]) is not int or status["slot_index"] != slot_index:
            raise HipBenchmarkError(f"{name}: candidate status ordering")
        if status["status"] == "scored":
            if status["failure_code"] is not None:
                raise HipBenchmarkError(f"{name}: scored slot failure code")
        elif status["status"] == "typed_failure":
            _nonempty_string(
                status["failure_code"], f"{name}[{slot_index}].failure_code"
            )
        else:
            raise HipBenchmarkError(f"{name}: candidate status value")
        output.append(status)
    return output


def _discrete_outputs(
    value: Any,
    name: str,
    statuses: list[dict[str, Any]],
    denominator: int,
) -> dict[str, Any]:
    outputs = _exact_keys(value, set(DERIVED_DISCRETE_FIELDS), name)
    scored_slots = [
        index for index, status in enumerate(statuses) if status["status"] == "scored"
    ]

    decisions = outputs["decision"]
    validities = outputs["validity"]
    ranks = outputs["rank"]
    clusters = outputs["cluster"]
    for field_name, rows in (
        ("decision", decisions),
        ("validity", validities),
        ("rank", ranks),
        ("cluster", clusters),
    ):
        if type(rows) is not list or len(rows) != denominator:
            raise HipBenchmarkError(f"{name}.{field_name}: candidate denominator")

    for slot_index, status in enumerate(statuses):
        decision = _nonempty_string(
            decisions[slot_index], f"{name}.decision[{slot_index}]"
        )
        if status["status"] == "typed_failure":
            if (
                decision != "typed_failure"
                or validities[slot_index] is not None
                or ranks[slot_index] is not None
                or clusters[slot_index] is not None
            ):
                raise HipBenchmarkError(
                    f"{name}: typed-failure discrete output at slot {slot_index}"
                )
            continue
        if decision == "typed_failure":
            raise HipBenchmarkError(f"{name}: scored decision at slot {slot_index}")
        if type(validities[slot_index]) is not bool:
            raise HipBenchmarkError(f"{name}: validity at slot {slot_index}")
        _integer(ranks[slot_index], f"{name}.rank[{slot_index}]")
        _integer(clusters[slot_index], f"{name}.cluster[{slot_index}]")

    score_order = outputs["score_order"]
    if (
        type(score_order) is not list
        or any(type(slot) is not int for slot in score_order)
        or len(score_order) != len(scored_slots)
        or set(score_order) != set(scored_slots)
    ):
        raise HipBenchmarkError(f"{name}.score_order: scored-slot permutation")
    expected_ranks = list(range(len(scored_slots)))
    observed_ranks = [ranks[slot] for slot in scored_slots]
    if sorted(observed_ranks) != expected_ranks:
        raise HipBenchmarkError(f"{name}.rank: scored-slot permutation")
    if any(ranks[slot] != rank for rank, slot in enumerate(score_order)):
        raise HipBenchmarkError(f"{name}: score order/rank mismatch")
    return outputs


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


def _finite_sum(values: list[float] | tuple[float, ...], name: str) -> float:
    try:
        total = math.fsum(values)
    except OverflowError as exc:
        raise HipBenchmarkError(f"{name}: derived sum overflow") from exc
    if not math.isfinite(total):
        raise HipBenchmarkError(f"{name}: nonfinite derived sum")
    return total


def _median(values: list[float], name: str) -> float:
    if not values:
        raise HipBenchmarkError(f"{name}: empty median")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        result = ordered[middle]
    else:
        result = _finite_sum((ordered[middle - 1] / 2.0, ordered[middle] / 2.0), name)
    if not math.isfinite(result):
        raise HipBenchmarkError(f"{name}: nonfinite derived median")
    return result


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
                "observed_error",
                "observed_error_sha256",
                "cpu_fallback_observed",
                "claim_authority_granted",
            },
            f"{architecture}.failure_probes[{index}]",
        )
        backend = _nonempty_string(
            probe["backend"], f"{architecture}.failure_probes[{index}].backend"
        )
        error_code = _nonempty_string(
            probe["error_code"],
            f"{architecture}.failure_probes[{index}].error_code",
        )
        if backend not in REQUIRED_BACKENDS[1:]:
            raise HipBenchmarkError(f"{architecture}: failure probe backend")
        if error_code not in FAILURE_PROBE_CODES:
            raise HipBenchmarkError(f"{architecture}: failure probe error code")
        pair = (backend, error_code)
        if pair in observed:
            raise HipBenchmarkError(f"{architecture}: duplicate failure probe")
        observed.add(pair)
        observation = _exact_keys(
            probe["observed_error"],
            {
                "schema_id",
                "gpu_architecture",
                "requested_backend",
                "error_code",
                "message_sha256",
            },
            f"{architecture}.failure_probes[{index}].observed_error",
        )
        if observation["schema_id"] != FAILURE_OBSERVATION_SCHEMA:
            raise HipBenchmarkError(f"{architecture}: failure observation schema")
        if observation["gpu_architecture"] != architecture:
            raise HipBenchmarkError(f"{architecture}: failure observation architecture")
        if observation["requested_backend"] != backend:
            raise HipBenchmarkError(f"{architecture}: failure observation backend")
        if observation["error_code"] != error_code:
            raise HipBenchmarkError(f"{architecture}: failure observation error code")
        _sha256(observation["message_sha256"], f"{architecture}.failure message")
        observed_error_sha256 = _sha256(
            probe["observed_error_sha256"], f"{architecture}.failure_probe SHA"
        )
        if observed_error_sha256 != _canonical_sha256(observation):
            raise HipBenchmarkError(f"{architecture}: failure observation SHA-256")
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
    expected_candidate_ids_sha256: str,
    minimum_samples: int,
    minimum_scored_candidates: int,
    scientific_length: int,
) -> dict[str, Any]:
    expected_keys = {
        "case_id",
        "candidate_count",
        "ordered_candidate_ids",
        "ordered_candidate_ids_sha256",
        "candidate_statuses",
        "repeat_candidate_statuses",
        "discrete_outputs",
        "repeat_discrete_outputs",
        "scientific_values",
        "repeat_scientific_values",
        "wall_time_seconds",
        "repeat_wall_time_seconds",
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
    candidate_ids_raw = case["ordered_candidate_ids"]
    if type(candidate_ids_raw) is not list or len(candidate_ids_raw) != denominator:
        raise HipBenchmarkError(f"{label}: ordered candidate identity denominator")
    candidate_ids = [
        _nonempty_string(value, f"{label}.ordered_candidate_ids[{index}]")
        for index, value in enumerate(candidate_ids_raw)
    ]
    if any(len(value) > 256 for value in candidate_ids):
        raise HipBenchmarkError(f"{label}: ordered candidate identity length")
    if len(set(candidate_ids)) != denominator:
        raise HipBenchmarkError(f"{label}: duplicate ordered candidate identity")
    candidate_ids_sha256 = _sha256(
        case["ordered_candidate_ids_sha256"],
        f"{label}.ordered_candidate_ids_sha256",
    )
    if candidate_ids_sha256 != _canonical_sha256(candidate_ids):
        raise HipBenchmarkError(f"{label}: ordered candidate identity SHA-256")
    if candidate_ids_sha256 != expected_candidate_ids_sha256:
        raise HipBenchmarkError(f"{label}: candidate cohort/profile cross-wire")
    for field in PARITY_DIGEST_FIELDS:
        digest = _sha256(case[field], f"{label}.{field}")
        repeat = _sha256(case[f"repeat_{field}"], f"{label}.repeat_{field}")
        if digest != repeat:
            raise HipBenchmarkError(f"{label}: repeat stability: {field}")
    statuses = _candidate_statuses(
        case["candidate_statuses"], f"{label}.candidate_statuses", denominator
    )
    repeat_statuses = _candidate_statuses(
        case["repeat_candidate_statuses"],
        f"{label}.repeat_candidate_statuses",
        denominator,
    )
    if statuses != repeat_statuses:
        raise HipBenchmarkError(f"{label}: repeat candidate status stability")
    if (
        sum(status["status"] == "scored" for status in statuses)
        < minimum_scored_candidates
    ):
        raise HipBenchmarkError(f"{label}: insufficient scored candidates")
    if case["typed_failure_sha256"] != _canonical_sha256(statuses):
        raise HipBenchmarkError(f"{label}: typed-failure status SHA-256 mismatch")
    if case["repeat_typed_failure_sha256"] != _canonical_sha256(repeat_statuses):
        raise HipBenchmarkError(
            f"{label}: repeat typed-failure status SHA-256 mismatch"
        )
    discrete_outputs = _discrete_outputs(
        case["discrete_outputs"], f"{label}.discrete_outputs", statuses, denominator
    )
    repeat_discrete_outputs = _discrete_outputs(
        case["repeat_discrete_outputs"],
        f"{label}.repeat_discrete_outputs",
        repeat_statuses,
        denominator,
    )
    if discrete_outputs != repeat_discrete_outputs:
        raise HipBenchmarkError(f"{label}: repeat discrete output stability")
    for field in DERIVED_DISCRETE_FIELDS:
        digest_field = f"{field}_sha256"
        if case[digest_field] != _canonical_sha256(discrete_outputs[field]):
            raise HipBenchmarkError(f"{label}: {field} output SHA-256 mismatch")
        if case[f"repeat_{digest_field}"] != _canonical_sha256(
            repeat_discrete_outputs[field]
        ):
            raise HipBenchmarkError(f"{label}: repeat {field} output SHA-256 mismatch")
    scientific = _scientific_values(case["scientific_values"], label, scientific_length)
    repeat_scientific = _scientific_values(
        case["repeat_scientific_values"],
        f"{label}.repeat",
        scientific_length,
    )
    for slot_index, status in enumerate(statuses):
        start = slot_index * len(SCIENTIFIC_FIELDS)
        primary_null = all(
            value is None
            for value in scientific[start : start + len(SCIENTIFIC_FIELDS)]
        )
        repeat_null = all(
            value is None
            for value in repeat_scientific[start : start + len(SCIENTIFIC_FIELDS)]
        )
        typed_failure = status["status"] == "typed_failure"
        if primary_null != typed_failure or repeat_null != typed_failure:
            raise HipBenchmarkError(
                f"{label}: scientific/status mismatch at slot {slot_index}"
            )
    scored_slots = [
        slot_index
        for slot_index, status in enumerate(statuses)
        if status["status"] == "scored"
    ]
    expected_score_order = sorted(
        scored_slots,
        key=lambda slot_index: (
            scientific[slot_index * len(SCIENTIFIC_FIELDS)],
            slot_index,
        ),
    )
    repeat_expected_score_order = sorted(
        scored_slots,
        key=lambda slot_index: (
            repeat_scientific[slot_index * len(SCIENTIFIC_FIELDS)],
            slot_index,
        ),
    )
    if discrete_outputs["score_order"] != expected_score_order:
        raise HipBenchmarkError(f"{label}: score order/scientific score mismatch")
    if repeat_discrete_outputs["score_order"] != repeat_expected_score_order:
        raise HipBenchmarkError(
            f"{label}: repeat score order/scientific score mismatch"
        )
    if scientific != repeat_scientific:
        raise HipBenchmarkError(f"{label}: repeat scientific stability")
    wall_times = _samples(
        case["wall_time_seconds"],
        f"{label}.wall_time_seconds",
        minimum_samples,
    )
    repeat_wall_times = _samples(
        case["repeat_wall_time_seconds"],
        f"{label}.repeat_wall_time_seconds",
        minimum_samples,
    )
    return {
        **case,
        "ordered_candidate_ids": candidate_ids,
        "discrete_outputs": discrete_outputs,
        "repeat_discrete_outputs": repeat_discrete_outputs,
        "scientific_values": scientific,
        "repeat_scientific_values": repeat_scientific,
        "wall_time_seconds": wall_times,
        "repeat_wall_time_seconds": repeat_wall_times,
    }


def _verify_profiler_trace(
    trace_value: Any,
    trace_sha256_value: Any,
    dispatches_value: Any,
    label: str,
    case_wall_times: dict[str, list[float]],
) -> tuple[int, float, str]:
    trace = _exact_keys(trace_value, {"schema_id", "rows"}, f"{label}.profiler_trace")
    if trace["schema_id"] != NORMALIZED_PROFILER_TRACE_SCHEMA:
        raise HipBenchmarkError(f"{label}: profiler trace schema")
    rows = trace["rows"]
    if type(rows) is not list or not rows:
        raise HipBenchmarkError(f"{label}: complete profiler trace required")
    aggregates: dict[str, list[float]] = {}
    coverage: set[tuple[str, int]] = set()
    runtime_by_sample: dict[tuple[str, int], list[float]] = {}
    allowed_case_ids = set(case_wall_times)
    for index, raw_row in enumerate(rows):
        row = _exact_keys(
            raw_row,
            {
                "dispatch_index",
                "case_id",
                "sample_index",
                "kernel_name",
                "runtime_seconds",
            },
            f"{label}.profiler_trace.rows[{index}]",
        )
        if type(row["dispatch_index"]) is not int or row["dispatch_index"] != index:
            raise HipBenchmarkError(f"{label}: profiler dispatch ordering")
        case_id = _case_id(
            row["case_id"], f"{label}.profiler_trace.rows[{index}].case_id"
        )
        if case_id not in allowed_case_ids:
            raise HipBenchmarkError(f"{label}: profiler trace case identity")
        sample_index = _integer(
            row["sample_index"],
            f"{label}.profiler_trace.rows[{index}].sample_index",
        )
        if sample_index >= len(case_wall_times[case_id]):
            raise HipBenchmarkError(f"{label}: profiler trace sample identity")
        sample_key = (case_id, sample_index)
        coverage.add(sample_key)
        kernel_name = _nonempty_string(
            row["kernel_name"], f"{label}.profiler_trace.kernel_name"
        )
        runtime = _finite(
            row["runtime_seconds"],
            f"{label}.profiler_trace.runtime_seconds",
            positive=True,
        )
        aggregates.setdefault(kernel_name, []).append(runtime)
        runtime_by_sample.setdefault(sample_key, []).append(runtime)
    expected_coverage = {
        (case_id, sample_index)
        for case_id, wall_times in case_wall_times.items()
        for sample_index in range(len(wall_times))
    }
    if coverage != expected_coverage:
        raise HipBenchmarkError(f"{label}: incomplete profiler case/sample coverage")
    for case_id, sample_index in expected_coverage:
        dispatch_runtime = _finite_sum(
            tuple(runtime_by_sample[(case_id, sample_index)]),
            f"{label}.{case_id}.sample[{sample_index}].dispatch_runtime",
        )
        wall_time = case_wall_times[case_id][sample_index]
        if dispatch_runtime > wall_time and not math.isclose(
            dispatch_runtime, wall_time, rel_tol=1e-12, abs_tol=0.0
        ):
            raise HipBenchmarkError(
                f"{label}: profiler dispatch runtime exceeds wall time"
            )
    trace_sha256 = _sha256(trace_sha256_value, f"{label}.profiler_trace_sha256")
    if trace_sha256 != _canonical_sha256(trace):
        raise HipBenchmarkError(f"{label}: profiler trace SHA-256 mismatch")

    dispatches = dispatches_value
    if type(dispatches) is not list or not dispatches:
        raise HipBenchmarkError(f"{label}: kernel dispatch summary required")
    observed_names: set[str] = set()
    dispatch_total = 0
    derived_runtime_totals: list[float] = []
    for index, raw_dispatch in enumerate(dispatches):
        dispatch = _exact_keys(
            raw_dispatch,
            {"kernel_name", "dispatch_count", "total_runtime_seconds"},
            f"{label}.kernel_dispatches[{index}]",
        )
        name = _nonempty_string(dispatch["kernel_name"], f"{label}.kernel_name")
        if name in observed_names:
            raise HipBenchmarkError(f"{label}: duplicate kernel summary")
        observed_names.add(name)
        if name not in aggregates:
            raise HipBenchmarkError(f"{label}: kernel summary not present in trace")
        dispatch_count = _integer(
            dispatch["dispatch_count"], f"{label}.{name}.dispatch_count", minimum=1
        )
        runtime = _finite(
            dispatch["total_runtime_seconds"],
            f"{label}.{name}.runtime",
            positive=True,
        )
        expected_count = len(aggregates[name])
        expected_runtime = _finite_sum(
            tuple(aggregates[name]), f"{label}.{name}.kernel_runtime"
        )
        if dispatch_count != expected_count or not math.isclose(
            runtime, expected_runtime, rel_tol=1e-12, abs_tol=0.0
        ):
            raise HipBenchmarkError(f"{label}: kernel summary/trace mismatch")
        dispatch_total += dispatch_count
        derived_runtime_totals.append(expected_runtime)
    if observed_names != set(aggregates):
        raise HipBenchmarkError(f"{label}: incomplete kernel summary")
    runtime_total = _finite_sum(
        tuple(derived_runtime_totals), f"{label}.kernel_runtime_total"
    )
    return dispatch_total, runtime_total, trace_sha256


def _verify_transfer_trace(
    trace_value: Any,
    trace_sha256_value: Any,
    label: str,
    minimum_samples: int,
) -> tuple[int, int, list[float], list[float], str]:
    trace = _exact_keys(trace_value, {"schema_id", "rows"}, f"{label}.transfer_trace")
    if trace["schema_id"] != NORMALIZED_TRANSFER_TRACE_SCHEMA:
        raise HipBenchmarkError(f"{label}: transfer trace schema")
    rows = trace["rows"]
    if type(rows) is not list or not rows:
        raise HipBenchmarkError(f"{label}: complete transfer trace required")
    bytes_by_direction: dict[str, list[int]] = {"h2d": [], "d2h": []}
    timings_by_direction: dict[str, list[float]] = {"h2d": [], "d2h": []}
    for index, raw_row in enumerate(rows):
        row = _exact_keys(
            raw_row,
            {"event_index", "direction", "bytes", "runtime_seconds"},
            f"{label}.transfer_trace.rows[{index}]",
        )
        if type(row["event_index"]) is not int or row["event_index"] != index:
            raise HipBenchmarkError(f"{label}: transfer event ordering")
        direction = _nonempty_string(
            row["direction"], f"{label}.transfer_trace.direction"
        )
        if direction not in bytes_by_direction:
            raise HipBenchmarkError(f"{label}: transfer direction")
        bytes_by_direction[direction].append(
            _integer(
                row["bytes"],
                f"{label}.transfer_trace.rows[{index}].bytes",
                minimum=1,
            )
        )
        timings_by_direction[direction].append(
            _finite(
                row["runtime_seconds"],
                f"{label}.transfer_trace.rows[{index}].runtime_seconds",
                positive=True,
            )
        )
    if any(
        len(timings_by_direction[direction]) < minimum_samples
        for direction in ("h2d", "d2h")
    ):
        raise HipBenchmarkError(f"{label}: insufficient transfer trace samples")
    trace_sha256 = _sha256(trace_sha256_value, f"{label}.transfer_trace_sha256")
    if trace_sha256 != _canonical_sha256(trace):
        raise HipBenchmarkError(f"{label}: transfer trace SHA-256 mismatch")
    return (
        sum(bytes_by_direction["h2d"]),
        sum(bytes_by_direction["d2h"]),
        timings_by_direction["h2d"],
        timings_by_direction["d2h"],
        trace_sha256,
    )


def _case_run_outputs_sha256(cases: list[dict[str, Any]], *, repeat: bool) -> str:
    prefix = "repeat_" if repeat else ""
    return _canonical_sha256(
        [
            {
                "case_id": case["case_id"],
                "candidate_count": case["candidate_count"],
                "ordered_candidate_ids_sha256": case["ordered_candidate_ids_sha256"],
                "candidate_statuses": case[f"{prefix}candidate_statuses"],
                "discrete_outputs": case[f"{prefix}discrete_outputs"],
                "scientific_values": case[f"{prefix}scientific_values"],
                "parity_digests": {
                    field: case[f"{prefix}{field}"] for field in PARITY_DIGEST_FIELDS
                },
            }
            for case in cases
        ]
    )


def _case_run_timings_sha256(cases: list[dict[str, Any]], *, repeat: bool) -> str:
    timing_field = "repeat_wall_time_seconds" if repeat else "wall_time_seconds"
    return _canonical_sha256(
        [
            {
                "case_id": case["case_id"],
                "wall_time_seconds": case[timing_field],
            }
            for case in cases
        ]
    )


def _execution_backend_receipt(
    *,
    architecture: str,
    backend_name: str,
    observed_backend: str,
    cpu_fallback_observed: bool,
    ordered_case_ids: list[str],
    run_role: str,
    execution_run_id_sha256: str,
    profiler_trace_sha256: str | None,
    transfer_trace_sha256: str | None,
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    repeat = run_role == "repeat"
    return {
        "schema_id": EXECUTION_BACKEND_RECEIPT_SCHEMA,
        "gpu_architecture": architecture,
        "requested_backend": backend_name,
        "observed_backend": observed_backend,
        "cpu_fallback_observed": cpu_fallback_observed,
        "ordered_case_ids_sha256": _canonical_sha256(ordered_case_ids),
        "run_role": run_role,
        "execution_run_id_sha256": execution_run_id_sha256,
        "profiler_trace_sha256": profiler_trace_sha256,
        "transfer_trace_sha256": transfer_trace_sha256,
        "case_timing_samples_sha256": _case_run_timings_sha256(cases, repeat=repeat),
        "case_outputs_sha256": _case_run_outputs_sha256(cases, repeat=repeat),
    }


def _verify_backend(
    raw: Any,
    *,
    architecture: str,
    backend_name: str,
    ordered_case_ids: list[str],
    expected_candidate_ids_sha256_by_case: dict[str, str],
    denominator: int,
    sampling: dict[str, Any],
    minimum_scored_candidates: int,
    scientific_length: int,
    seen_execution_run_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    label = f"{architecture}/{backend_name}"
    backend = _exact_keys(
        raw,
        {
            "backend_name",
            "observed_backend",
            "cpu_fallback_observed",
            "execution_run_id_sha256",
            "repeat_execution_run_id_sha256",
            "execution_backend_receipt_sha256",
            "repeat_execution_backend_receipt_sha256",
            "candidate_denominator",
            "context_construction_seconds",
            "peak_rss_bytes",
            "peak_vram_bytes",
            "h2d_bytes",
            "d2h_bytes",
            "h2d_seconds",
            "d2h_seconds",
            "runtime_failure_counts",
            "profiler_trace",
            "profiler_trace_sha256",
            "kernel_dispatches",
            "transfer_trace",
            "transfer_trace_sha256",
            "repeat_profiler_trace",
            "repeat_profiler_trace_sha256",
            "repeat_kernel_dispatches",
            "repeat_transfer_trace",
            "repeat_transfer_trace_sha256",
            "cases",
        },
        label,
    )
    if backend["backend_name"] != backend_name:
        raise HipBenchmarkError(f"{label}: backend identity")
    if backend["observed_backend"] != backend_name:
        raise HipBenchmarkError(f"{label}: representative observed backend mismatch")
    if backend["cpu_fallback_observed"] is not False:
        raise HipBenchmarkError(f"{label}: representative CPU fallback observed")
    execution_run_id = _sha256(
        backend["execution_run_id_sha256"], f"{label}.execution_run_id_sha256"
    )
    repeat_execution_run_id = _sha256(
        backend["repeat_execution_run_id_sha256"],
        f"{label}.repeat_execution_run_id_sha256",
    )
    if execution_run_id == repeat_execution_run_id:
        raise HipBenchmarkError(f"{label}: repeat execution identity reused")
    for run_id in (execution_run_id, repeat_execution_run_id):
        if run_id in seen_execution_run_ids:
            raise HipBenchmarkError(f"{label}: duplicate execution identity")
        seen_execution_run_ids.add(run_id)
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
        if (
            h2d_samples
            or d2h_samples
            or backend["profiler_trace"] is not None
            or backend["profiler_trace_sha256"] is not None
            or backend["repeat_profiler_trace"] is not None
            or backend["repeat_profiler_trace_sha256"] is not None
            or backend["transfer_trace"] is not None
            or backend["transfer_trace_sha256"] is not None
            or backend["repeat_transfer_trace"] is not None
            or backend["repeat_transfer_trace_sha256"] is not None
        ):
            raise HipBenchmarkError(f"{label}: CPU profiler/transfer evidence")
        if (
            backend["kernel_dispatches"] != []
            or backend["repeat_kernel_dispatches"] != []
        ):
            raise HipBenchmarkError(f"{label}: CPU kernel trace")
        kernel_total = 0.0
        kernel_dispatch_total = 0
        profiler_trace_sha256 = None
        repeat_profiler_trace_sha256 = None
        transfer_trace_sha256 = None
        repeat_transfer_trace_sha256 = None
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
        profiler_trace_sha256 = None
        repeat_profiler_trace_sha256 = None
        (
            trace_h2d_bytes,
            trace_d2h_bytes,
            trace_h2d_samples,
            trace_d2h_samples,
            transfer_trace_sha256,
        ) = _verify_transfer_trace(
            backend["transfer_trace"],
            backend["transfer_trace_sha256"],
            label,
            sampling["minimum_transfer_samples"],
        )
        if (
            h2d_bytes != trace_h2d_bytes
            or d2h_bytes != trace_d2h_bytes
            or h2d_samples != trace_h2d_samples
            or d2h_samples != trace_d2h_samples
        ):
            raise HipBenchmarkError(f"{label}: transfer summary/trace mismatch")
        *_, repeat_transfer_trace_sha256 = _verify_transfer_trace(
            backend["repeat_transfer_trace"],
            backend["repeat_transfer_trace_sha256"],
            f"{label}/repeat",
            sampling["minimum_transfer_samples"],
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
            expected_candidate_ids_sha256_by_case[case_id],
            sampling["minimum_case_samples"],
            minimum_scored_candidates,
            scientific_length,
        )
        for index, (raw_case, case_id) in enumerate(
            zip(cases_raw, ordered_case_ids, strict=True)
        )
    ]
    if backend_name != "rust_cpu":
        case_wall_times = {case["case_id"]: case["wall_time_seconds"] for case in cases}
        repeat_case_wall_times = {
            case["case_id"]: case["repeat_wall_time_seconds"] for case in cases
        }
        kernel_dispatch_total, kernel_total, profiler_trace_sha256 = (
            _verify_profiler_trace(
                backend["profiler_trace"],
                backend["profiler_trace_sha256"],
                backend["kernel_dispatches"],
                label,
                case_wall_times,
            )
        )
        _, _, repeat_profiler_trace_sha256 = _verify_profiler_trace(
            backend["repeat_profiler_trace"],
            backend["repeat_profiler_trace_sha256"],
            backend["repeat_kernel_dispatches"],
            f"{label}/repeat",
            repeat_case_wall_times,
        )

    execution_receipt = _execution_backend_receipt(
        architecture=architecture,
        backend_name=backend_name,
        observed_backend=backend["observed_backend"],
        cpu_fallback_observed=backend["cpu_fallback_observed"],
        ordered_case_ids=ordered_case_ids,
        run_role="primary",
        execution_run_id_sha256=execution_run_id,
        profiler_trace_sha256=profiler_trace_sha256,
        transfer_trace_sha256=transfer_trace_sha256,
        cases=cases,
    )
    if _sha256(
        backend["execution_backend_receipt_sha256"],
        f"{label}.execution_backend_receipt_sha256",
    ) != _canonical_sha256(execution_receipt):
        raise HipBenchmarkError(f"{label}: execution backend receipt mismatch")
    repeat_execution_receipt = _execution_backend_receipt(
        architecture=architecture,
        backend_name=backend_name,
        observed_backend=backend["observed_backend"],
        cpu_fallback_observed=backend["cpu_fallback_observed"],
        ordered_case_ids=ordered_case_ids,
        run_role="repeat",
        execution_run_id_sha256=repeat_execution_run_id,
        profiler_trace_sha256=repeat_profiler_trace_sha256,
        transfer_trace_sha256=repeat_transfer_trace_sha256,
        cases=cases,
    )
    if _sha256(
        backend["repeat_execution_backend_receipt_sha256"],
        f"{label}.repeat_execution_backend_receipt_sha256",
    ) != _canonical_sha256(repeat_execution_receipt):
        raise HipBenchmarkError(f"{label}: repeat execution backend receipt mismatch")
    all_wall_times = [sample for case in cases for sample in case["wall_time_seconds"]]
    case_medians = [
        _median(case["wall_time_seconds"], f"{label}/{case['case_id']}.median")
        for case in cases
    ]
    total_candidates = denominator * sum(
        len(case["wall_time_seconds"]) for case in cases
    )
    wall_time_total = _finite_sum(all_wall_times, f"{label}.wall_time_total")
    metrics = {
        "context_construction_seconds_p50": _median(
            context_samples, f"{label}.context_median"
        ),
        "case_wall_time_seconds_p50": _median(case_medians, f"{label}.case_median"),
        "case_wall_time_seconds_p95": _nearest_rank_95(case_medians),
        "candidate_throughput_per_second": total_candidates / wall_time_total,
        "peak_rss_bytes": peak_rss,
        "peak_vram_bytes": peak_vram,
        "h2d_bytes": h2d_bytes,
        "d2h_bytes": d2h_bytes,
        "h2d_seconds_p50": (
            _median(h2d_samples, f"{label}.h2d_median") if h2d_samples else 0.0
        ),
        "d2h_seconds_p50": (
            _median(d2h_samples, f"{label}.d2h_median") if d2h_samples else 0.0
        ),
        "kernel_dispatch_count_total": kernel_dispatch_total,
        "kernel_runtime_seconds_total": kernel_total,
    }
    for metric_name, metric_value in metrics.items():
        if isinstance(metric_value, float) and not math.isfinite(metric_value):
            raise HipBenchmarkError(f"{label}.{metric_name}: nonfinite derived metric")
    return cases, metrics


def verify(profile_path: Path, result_path: Path) -> dict[str, Any]:
    """Verify a completed result against an exact manifest-bound profile."""

    profile = _load(profile_path)
    profile_summary = _verify_profile_document(profile)
    if not profile_summary["manifest_bound"]:
        raise HipBenchmarkError(
            "profile manifest is not bound; result verification refused"
        )
    if not profile_summary["result_verification_authorized"]:
        raise HipBenchmarkError("bound profile is not repository-authorized")
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
            "result_sha256",
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
    ordered_case_ids_sha256 = _sha256(
        result["ordered_case_ids_sha256"], "ordered_case_ids_sha256"
    )
    if ordered_case_ids_sha256 != _canonical_sha256(ordered_case_ids):
        raise HipBenchmarkError("ordered case identity SHA-256 mismatch")
    if ordered_case_ids_sha256 != profile["expected_ordered_case_ids_sha256"]:
        raise HipBenchmarkError("ordered cohort/profile cross-wire")
    expected_candidate_ids_sha256_by_case = profile[
        "expected_ordered_candidate_ids_sha256_by_case"
    ]
    if set(expected_candidate_ids_sha256_by_case) != set(ordered_case_ids):
        raise HipBenchmarkError("candidate identity map/profile cross-wire")
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
    seen_device_serials: set[str] = set()
    seen_execution_run_ids: set[str] = set()
    allowed_newer_architectures = set(profile["allowed_newer_gpu_architectures"])
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
                "gpu_model",
                "pci_device_id",
                "device_serial_sha256",
                "total_vram_bytes",
                "cpu_model",
                "cpu_physical_core_count",
                "cpu_logical_thread_count",
                "cpu_execution_settings",
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
        if GPU_ARCHITECTURE_RE.fullmatch(architecture_name) is None:
            raise HipBenchmarkError("invalid GPU architecture identity")
        if (
            architecture_name != profile["baseline_gpu_architecture"]
            and architecture_name not in allowed_newer_architectures
        ):
            raise HipBenchmarkError("GPU architecture not allowed by profile")
        if architecture_name in seen_architectures:
            raise HipBenchmarkError("duplicate GPU architecture")
        seen_architectures.add(architecture_name)
        for identity in (
            "gpu_model",
            "cpu_model",
            "rocm_version",
            "driver_version",
            "rust_version",
            "hip_compiler_version",
            "profiler_version",
        ):
            _nonempty_string(architecture[identity], f"{architecture_name}.{identity}")
        physical_cores = _integer(
            architecture["cpu_physical_core_count"],
            f"{architecture_name}.cpu_physical_core_count",
            minimum=1,
        )
        logical_threads = _integer(
            architecture["cpu_logical_thread_count"],
            f"{architecture_name}.cpu_logical_thread_count",
            minimum=1,
        )
        if logical_threads < physical_cores:
            raise HipBenchmarkError(f"{architecture_name}: CPU topology")
        cpu_settings = _exact_keys(
            architecture["cpu_execution_settings"],
            {
                "benchmark_thread_count",
                "affinity",
                "frequency_governor",
                "turbo_enabled",
                "numa_policy",
                "environment_sha256",
            },
            f"{architecture_name}.cpu_execution_settings",
        )
        benchmark_threads = _integer(
            cpu_settings["benchmark_thread_count"],
            f"{architecture_name}.benchmark_thread_count",
            minimum=1,
        )
        if benchmark_threads > logical_threads:
            raise HipBenchmarkError(f"{architecture_name}: CPU benchmark thread count")
        for key in ("affinity", "frequency_governor", "numa_policy"):
            _nonempty_string(cpu_settings[key], f"{architecture_name}.{key}")
        if type(cpu_settings["turbo_enabled"]) is not bool:
            raise HipBenchmarkError(f"{architecture_name}: CPU turbo setting")
        _sha256(
            cpu_settings["environment_sha256"],
            f"{architecture_name}.cpu_environment_sha256",
        )
        pci_device_id = _nonempty_string(
            architecture["pci_device_id"], f"{architecture_name}.pci_device_id"
        )
        if PCI_DEVICE_ID_RE.fullmatch(pci_device_id) is None:
            raise HipBenchmarkError(f"{architecture_name}: invalid PCI device ID")
        if ROCPROFILER_VERSION_RE.fullmatch(architecture["profiler_version"]) is None:
            raise HipBenchmarkError(f"{architecture_name}: profiler identity")
        device_serial_sha256 = _sha256(
            architecture["device_serial_sha256"],
            f"{architecture_name}.device_serial_sha256",
        )
        if device_serial_sha256 in seen_device_serials:
            raise HipBenchmarkError("duplicate GPU device identity")
        seen_device_serials.add(device_serial_sha256)
        for digest in (
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
                expected_candidate_ids_sha256_by_case=(
                    expected_candidate_ids_sha256_by_case
                ),
                denominator=profile["candidate_denominator"],
                sampling=profile["sampling"],
                minimum_scored_candidates=profile["parity"][
                    "minimum_scored_candidates_per_case"
                ],
                scientific_length=scientific_length,
                seen_execution_run_ids=seen_execution_run_ids,
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
        primary_gate_results = [
            _median(fast["wall_time_seconds"], "hip_fast.speed_gate.primary")
            < _median(cpu["wall_time_seconds"], "rust_cpu.speed_gate.primary")
            for cpu, fast in zip(cpu_cases, verified_backends["hip_fast"], strict=True)
        ]
        repeat_gate_results = [
            _median(fast["repeat_wall_time_seconds"], "hip_fast.speed_gate.repeat")
            < _median(cpu["repeat_wall_time_seconds"], "rust_cpu.speed_gate.repeat")
            for cpu, fast in zip(cpu_cases, verified_backends["hip_fast"], strict=True)
        ]
        passing_cases = sum(
            primary and repeat
            for primary, repeat in zip(
                primary_gate_results, repeat_gate_results, strict=True
            )
        )
        if passing_cases < profile["performance_gate"]["minimum_passing_case_count"]:
            raise HipBenchmarkError(
                f"{architecture_name}: replicated predeclared hip_fast speed gate"
            )
        architecture_metrics["hip_fast_primary_speed_gate_passing_case_count"] = sum(
            primary_gate_results
        )
        architecture_metrics["hip_fast_repeat_speed_gate_passing_case_count"] = sum(
            repeat_gate_results
        )
        architecture_metrics["hip_fast_speed_gate_passing_case_count"] = passing_cases
        derived_metrics[architecture_name] = architecture_metrics

    baseline = profile["baseline_gpu_architecture"]
    if baseline not in seen_architectures:
        raise HipBenchmarkError("baseline gfx1030 architecture missing")
    if not any(name in allowed_newer_architectures for name in seen_architectures):
        raise HipBenchmarkError("newer GPU architecture missing")
    result_sha256 = _sha256(result["result_sha256"], "result.result_sha256")
    if result_sha256 != _canonical_sha256(_result_projection(result)):
        raise HipBenchmarkError("result SHA-256 mismatch")
    if result_sha256 not in AUTHORIZED_RESULT_SHA256S:
        raise HipBenchmarkError("result is not repository-authorized")
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
