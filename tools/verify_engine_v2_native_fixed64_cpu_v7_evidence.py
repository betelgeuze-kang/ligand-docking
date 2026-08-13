#!/usr/bin/env python3
"""Independently verify persisted native fixed64 CPU v7 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import pwd
import re
import stat
import struct
import subprocess
from typing import NoReturn

if __package__:
    from .verify_engine_v2_native_fixed64_cpu_profile_v7 import (
        FALSE_AUTHORITY_KEYS,
        FALSE_RESTRICTION_KEYS,
        BUILD_CONFIGURATION_SHA256,
        PROFILE_ID,
        PROFILE_RELATIVE_PATH,
        PROFILE_SHA256,
        SOURCE_MANIFEST_RELATIVE_PATH,
    )
else:
    from verify_engine_v2_native_fixed64_cpu_profile_v7 import (
        FALSE_AUTHORITY_KEYS,
        FALSE_RESTRICTION_KEYS,
        BUILD_CONFIGURATION_SHA256,
        PROFILE_ID,
        PROFILE_RELATIVE_PATH,
        PROFILE_SHA256,
        SOURCE_MANIFEST_RELATIVE_PATH,
    )


ATTEMPT_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_cpu_attempt/7.0.0"
ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_cpu_qualification_artifact/7.0.0"
)
TERMINAL_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_cpu_terminal/7.0.0"
ACTIVATION_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_activation_v7\0"
ATTEMPT_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_attempt_v7\0"
ARTIFACT_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_artifact_v7\0"
TERMINAL_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_terminal_v7\0"
MAX_STATE_BYTES = 64 * 1024
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
NUMERIC_PROJECTION_DOMAIN = (
    b"betelgeuze.engine_v2_native_fixed64_cpu_numeric_projection_v7\0"
)
NUMERIC_PROJECTION_F64_COUNT = 28_544
NUMERIC_ROW_F64_COUNT = 98
SCIENTIFIC_DECISION_DOMAIN = (
    "betelgeuze.engine_v2_native_fixed64_scientific_decision/2.0.0"
)
SCIENTIFIC_PROJECTION_DOMAIN = (
    "betelgeuze.engine_v2_native_fixed64_scientific_projection/2.0.0"
)
PROJECTION_DIGEST_STREAM_DOMAIN = (
    b"betelgeuze.engine_v2_native_fixed64_cpu_projection_digest_stream_v7\0"
)
PROJECTION_DIGEST_STREAM_BYTES = 64 * 6 * 32
LANE_METRICS_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_lane_metrics/1.0.0"
LANE_RANGES = (
    ("pocket_centered_controls", 0, 7),
    ("uniform_source_controls", 8, 23),
    ("deterministic_independent_so3", 24, 35),
    ("true_conformer_independent_so3", 36, 43),
    ("ligand_donor_to_receptor_acceptor", 44, 47),
    ("ligand_acceptor_to_receptor_donor", 48, 51),
    ("complementary_charge", 52, 55),
    ("aromatic_plane", 56, 57),
    ("principal_axis_shape", 58, 59),
    ("paired_retained_controls", 60, 63),
)
CONTROL_LANES = {
    "pocket_centered_controls",
    "uniform_source_controls",
    "paired_retained_controls",
}
CONFORMER_ORIENTATION_PAIRS = tuple((24 + index, 36 + index) for index in range(8))
MISSING_SLOT_INDEX = 2**32 - 1
LOG2_Q32 = (
    0,
    0,
    4294967296,
    6807362106,
    8589934592,
    9972605231,
    11102329402,
    12057497579,
    12884901888,
    13614724212,
    14267572527,
    14858145665,
    15397296698,
    15893267570,
    16352464875,
    16779967337,
    17179869184,
    17555519227,
    17909691508,
    18244709746,
    18562539823,
    18864859684,
    19153112961,
    19428550663,
    19692263994,
    19945210462,
    20188234866,
    20422086318,
    20647432171,
    20864869499,
    21074934633,
    21278111131,
    21474836480,
    21665507771,
    21850486523,
    22030102810,
    22204658804,
    22374431835,
    22539677042,
    22700629676,
    22857507119,
    23010510646,
    23159826980,
    23305629661,
    23448080257,
    23587329443,
    23723517959,
    23856777461,
    23987231290,
    24114995157,
    24240177758,
    24362881333,
    24483202162,
    24601231026,
    24717053614,
    24830750896,
    24942399467,
    25052071852,
    25159836795,
    25265759511,
    25369901929,
    25472322906,
    25573078427,
    25672221790,
    25769803776,
)
EXPECTED_FIXTURES = {
    "synthetic_complete_64": {
        "fixture_payload_sha256": "5e17b3a292a068115f223c5c433d5ec40557be50a05cc1dbaa07461d9aed7fb8",
        "generated_count": 64,
        "typed_failure_count": 0,
    },
    "synthetic_feature_sparse_48_plus_16": {
        "fixture_payload_sha256": "fca0d6dbdc0f188e332929b9ea220f1d3ecaa37e9939c49aa80bf0629c14f1fb",
        "generated_count": 48,
        "typed_failure_count": 16,
    },
}
KNOWN_BLOCKERS = {
    "affinity_unavailable",
    "boost_not_disabled",
    "boost_state_unavailable",
    "cpu_model_not_qualified",
    "measurement_affinity_pin_failed",
    "measurement_cpu_unavailable",
    "native_measurement_failed",
    "native_measurement_report_contract_failed",
    "native_qualification_gate_failed",
    "post_pin_boost_not_disabled",
    "post_pin_process_task_count_not_one",
    "post_measurement_host_invariant_failed",
    "process_task_count_not_one",
    "process_task_count_unavailable",
    "source_checkout_not_exact_main",
}
PREFLIGHT_BLOCKERS = {
    "affinity_unavailable",
    "boost_not_disabled",
    "boost_state_unavailable",
    "cpu_model_not_qualified",
    "measurement_cpu_unavailable",
    "process_task_count_not_one",
    "process_task_count_unavailable",
    "source_checkout_not_exact_main",
}
POST_PIN_BLOCKERS = {
    "measurement_affinity_pin_failed",
    "post_pin_boost_not_disabled",
    "post_pin_process_task_count_not_one",
}
MEASUREMENT_BLOCKERS = {
    "native_measurement_failed",
    "native_measurement_report_contract_failed",
    "post_measurement_host_invariant_failed",
}
ATTEMPT_KEYS = (
    "activation_sha256",
    "attempt_ordinal",
    "authority",
    "build_configuration_sha256",
    "measurement_started",
    "output_path_sha256",
    "process_id",
    "process_start_ticks",
    "profile_id",
    "profile_sha256",
    "restrictions",
    "run_nonce",
    "schema_id",
)
ARTIFACT_KEYS = (
    "activation_sha256",
    "attempt_ledger_raw_sha256",
    "attempt_receipt_sha256",
    "authority",
    "blockers",
    "build_configuration_sha256",
    "execution",
    "fixtures",
    "host",
    "output_path_sha256",
    "profile_id",
    "profile_sha256",
    "qualification_authority",
    "restrictions",
    "run_nonce",
    "schema_id",
    "status",
)
TERMINAL_KEYS = (
    "activation_sha256",
    "artifact_byte_count",
    "artifact_persisted",
    "artifact_raw_sha256",
    "artifact_receipt_sha256",
    "attempt_ledger_raw_sha256",
    "attempt_receipt_sha256",
    "authority",
    "blockers",
    "build_configuration_sha256",
    "decision_returned_only_after_terminal_persistence",
    "execution_attested",
    "execution_consumed",
    "output_path_sha256",
    "profile_id",
    "profile_sha256",
    "qualification_authority",
    "recorded_decision",
    "recorded_gate_passed",
    "restrictions",
    "run_nonce",
    "schema_id",
    "status",
)


class NativeFixed64CPUV7EvidenceError(ValueError):
    """Persisted native fixed64 CPU v7 evidence failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeFixed64CPUV7EvidenceError(message)


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _domain_sha256(domain: bytes, raw: bytes) -> str:
    return hashlib.sha256(domain + raw).hexdigest()


class _CanonicalHasher:
    def __init__(self, domain: str) -> None:
        self._hash = hashlib.sha256()
        self.string(domain)

    def byte(self, value: int) -> None:
        self._hash.update(bytes((value,)))

    def u32(self, value: int) -> None:
        self._hash.update(value.to_bytes(4, "big", signed=False))

    def i32(self, value: int) -> None:
        self._hash.update((value & 0xFFFFFFFF).to_bytes(4, "big"))

    def u64(self, value: int) -> None:
        self._hash.update(value.to_bytes(8, "big", signed=False))

    def f64(self, value: float) -> None:
        canonical = 0.0 if value == 0.0 else value
        self._hash.update(struct.pack(">d", canonical))

    def bytes(self, value: bytes) -> None:
        self.u64(len(value))
        self._hash.update(value)

    def string(self, value: str) -> None:
        self.bytes(value.encode("utf-8"))

    def digest(self, value: str) -> None:
        self._hash.update(bytes.fromhex(value))

    def finish(self) -> str:
        return self._hash.hexdigest()


def _require_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        _fail(f"{label} is not a boolean")
    return value


def _require_uint(value: object, *, maximum: int = 2**64 - 1, label: str) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        _fail(f"{label} is not an unsigned integer")
    return value


def _require_i32(value: object, *, label: str) -> int:
    if type(value) is not int or not -(2**31) <= value < 2**31:
        _fail(f"{label} is not an int32")
    return value


def _require_finite(value: object, *, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail(f"{label} is not finite")
    return float(value)


def _require_finite_array(
    value: object,
    *,
    count: int,
    label: str,
) -> list[float]:
    if type(value) is not list or len(value) != count:
        _fail(f"{label} length changed")
    return [_require_finite(item, label=label) for item in value]


def _canonical_f64_bits(value: float) -> bytes:
    return struct.pack(">d", 0.0 if value == 0.0 else value)


def _require_numeric_projection(value: object, *, label: str) -> list[float]:
    evidence = _require_ordered_keys(
        value,
        ("f64_be_hex", "f64_count", "sha256"),
        label=f"{label} numeric projection",
    )
    count = _require_uint(
        evidence["f64_count"],
        maximum=NUMERIC_PROJECTION_F64_COUNT,
        label=f"{label} numeric projection count",
    )
    hexadecimal = evidence["f64_be_hex"]
    if (
        count != NUMERIC_PROJECTION_F64_COUNT
        or type(hexadecimal) is not str
        or re.fullmatch(rf"[0-9a-f]{{{count * 16}}}", hexadecimal) is None
    ):
        _fail(f"{label} numeric projection envelope changed")
    raw = bytes.fromhex(hexadecimal)
    digest = _require_digest(evidence["sha256"], label=f"{label} numeric projection")
    if _domain_sha256(NUMERIC_PROJECTION_DOMAIN, raw) != digest:
        _fail(f"{label} numeric projection digest does not rederive")
    values = [item[0] for item in struct.iter_unpack(">d", raw)]
    if any(
        not math.isfinite(item) or (item == 0.0 and _canonical_f64_bits(item) != chunk)
        for item, chunk in zip(values, (raw[i : i + 8] for i in range(0, len(raw), 8)))
    ):
        _fail(f"{label} numeric projection contains non-finite or noncanonical values")
    return values


def _require_canonical_bytes(
    value: object,
    *,
    domain: bytes,
    expected_count: int | None,
    maximum_count: int,
    label: str,
) -> bytes:
    evidence = _require_ordered_keys(
        value,
        ("byte_count", "hex", "sha256"),
        label=label,
    )
    count = _require_uint(
        evidence["byte_count"], maximum=maximum_count, label=f"{label} byte count"
    )
    hexadecimal = evidence["hex"]
    if (
        count == 0
        or (expected_count is not None and count != expected_count)
        or type(hexadecimal) is not str
        or re.fullmatch(rf"[0-9a-f]{{{count * 2}}}", hexadecimal) is None
    ):
        _fail(f"{label} byte envelope changed")
    raw = bytes.fromhex(hexadecimal)
    digest = _require_digest(evidence["sha256"], label=label)
    if _domain_sha256(domain, raw) != digest:
        _fail(f"{label} digest does not rederive")
    return raw


def _hash_numeric_channel(
    hasher: _CanonicalHasher,
    numeric: list[float],
    start: int,
    count: int,
) -> None:
    hasher.u64(count)
    for value in numeric[start : start + count]:
        hasher.f64(value)


def _hash_position_projection(
    hasher: _CanonicalHasher,
    numeric: list[float],
    start: int,
) -> None:
    for channel in range(3):
        _hash_numeric_channel(hasher, numeric, start + channel * 768, 768)


def _scientific_projection_sha256(
    *,
    projection_decision_sha256: str,
    digest_stream: bytes,
    numeric: list[float],
) -> str:
    if (
        len(digest_stream) != PROJECTION_DIGEST_STREAM_BYTES
        or len(numeric) != NUMERIC_PROJECTION_F64_COUNT
    ):
        _fail("scientific projection input denominator changed")

    digests = [
        digest_stream[index : index + 32] for index in range(0, len(digest_stream), 32)
    ]
    hasher = _CanonicalHasher(SCIENTIFIC_PROJECTION_DOMAIN)
    hasher.digest(projection_decision_sha256)
    for slot in range(64):
        digest_base = slot * 6
        row = slot * NUMERIC_ROW_F64_COUNT
        for digest in digests[digest_base : digest_base + 3]:
            hasher.digest(digest.hex())

        _hash_numeric_channel(hasher, numeric, row, 4)
        for index in range(row + 4, row + 14):
            hasher.f64(numeric[index])
        for profile in range(4):
            start = row + 14 + profile * 12
            hasher.f64(numeric[start])
            hasher.f64(numeric[start + 1])
            _hash_numeric_channel(hasher, numeric, start + 2, 3)
            _hash_numeric_channel(hasher, numeric, start + 5, 3)
            for index in range(start + 8, start + 12):
                hasher.f64(numeric[index])
        for index in range(row + 62, row + 76):
            hasher.f64(numeric[index])
        _hash_numeric_channel(hasher, numeric, row + 76, 8)
        for index in range(row + 84, row + 97):
            hasher.f64(numeric[index])
        hasher.digest(digests[digest_base + 3].hex())
        hasher.digest(digests[digest_base + 4].hex())
        hasher.f64(numeric[row + 97])
        hasher.digest(digests[digest_base + 5].hex())

    cursor = 64 * NUMERIC_ROW_F64_COUNT
    for value in numeric[cursor : cursor + 512 * 4]:
        hasher.f64(value)

    producer = cursor + 512 * 4
    rigid_selected = producer + 3 * 768
    rigid_comparison = rigid_selected + 3 * 768
    rigid_baseline = rigid_comparison + 3 * 768
    rigid_clearance = rigid_baseline + 3 * 768
    torsion_optimized = rigid_clearance + 3 * 768
    torsion_final = torsion_optimized + 3 * 768
    final_coordinates = torsion_final + 3 * 768
    optimized_angles = final_coordinates + 3 * 768
    final_angles = optimized_angles + 768
    final_quaternions = final_angles + 768
    if final_quaternions + 4 * 64 != len(numeric):
        _fail("scientific projection numeric channel layout changed")

    _hash_position_projection(hasher, numeric, producer)
    for start in (
        rigid_selected,
        rigid_comparison,
        rigid_baseline,
        rigid_clearance,
    ):
        _hash_position_projection(hasher, numeric, start)
    _hash_position_projection(hasher, numeric, torsion_optimized)
    _hash_numeric_channel(hasher, numeric, optimized_angles, 768)
    _hash_position_projection(hasher, numeric, torsion_final)
    _hash_numeric_channel(hasher, numeric, final_angles, 768)
    _hash_position_projection(hasher, numeric, final_coordinates)
    for channel in range(4):
        _hash_numeric_channel(hasher, numeric, final_quaternions + channel * 64, 64)
    return hasher.finish()


def _require_digest(value: object, *, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(f"{label} is not a lowercase SHA-256")
    return value


def _require_commit_oid(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or re.fullmatch(r"[0-9a-f]{40}", value) is None
        or value == "0" * 40
    ):
        _fail(f"{label} is not a bound Git commit identity")
    return value


def _require_false_map(
    value: object,
    expected_keys: set[str],
    *,
    label: str,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != expected_keys
        or any(item is not False for item in value.values())
    ):
        _fail(f"{label} is not entirely false")
    return value


def _split_envelope(
    raw: bytes,
    *,
    domain: bytes,
    maximum_bytes: int,
    label: str,
) -> tuple[dict[str, object], str]:
    if not 1 <= len(raw) <= maximum_bytes or not raw.endswith(b"\n"):
        _fail(f"{label} byte envelope changed")
    prefix = b'{"projection":'
    if not raw.startswith(prefix):
        _fail(f"{label} envelope prefix changed")
    match = re.search(rb',"receipt_sha256":"([0-9a-f]{64})"}\n$', raw)
    if match is None or match.start() <= len(prefix):
        _fail(f"{label} receipt envelope changed")
    projection_raw = raw[len(prefix) : match.start()]
    receipt = match.group(1).decode("ascii")
    if (
        raw
        != prefix + projection_raw + b',"receipt_sha256":"' + match.group(1) + b'"}\n'
    ):
        _fail(f"{label} envelope contains unbound bytes")
    if _domain_sha256(domain, projection_raw) != receipt:
        _fail(f"{label} receipt does not rederive")
    try:
        projection = json.loads(
            projection_raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUV7EvidenceError(
            f"{label} projection is not strict ASCII JSON"
        ) from exc
    if type(projection) is not dict:
        _fail(f"{label} projection is not an object")
    return projection, receipt


def _require_ordered_keys(
    value: object,
    keys: tuple[str, ...],
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or tuple(value) != keys:
        _fail(f"{label} ordered field set changed")
    return value


def _require_blockers(value: object) -> list[str]:
    if (
        type(value) is not list
        or any(type(item) is not str or item not in KNOWN_BLOCKERS for item in value)
        or value != sorted(set(value))
    ):
        _fail("evidence blockers are invalid, unknown, duplicate, or unsorted")
    return value


def require_attempt_bytes(
    raw: bytes,
    *,
    activation_sha256: str,
    output_path_sha256: str,
) -> tuple[dict[str, object], str]:
    attempt, receipt = _split_envelope(
        raw,
        domain=ATTEMPT_DOMAIN,
        maximum_bytes=MAX_STATE_BYTES,
        label="attempt ledger",
    )
    _require_ordered_keys(attempt, ATTEMPT_KEYS, label="attempt ledger")
    _require_false_map(
        attempt["authority"], FALSE_AUTHORITY_KEYS, label="attempt authority"
    )
    _require_false_map(
        attempt["restrictions"],
        FALSE_RESTRICTION_KEYS,
        label="attempt restrictions",
    )
    if (
        attempt["schema_id"] != ATTEMPT_SCHEMA_ID
        or attempt["profile_id"] != PROFILE_ID
        or attempt["profile_sha256"] != PROFILE_SHA256
        or attempt["activation_sha256"] != activation_sha256
        or attempt["build_configuration_sha256"] != BUILD_CONFIGURATION_SHA256
        or attempt["output_path_sha256"] != output_path_sha256
        or type(attempt["attempt_ordinal"]) is not int
        or attempt["attempt_ordinal"] != 1
        or attempt["measurement_started"] is not False
        or type(attempt["process_id"]) is not int
        or attempt["process_id"] < 1
        or type(attempt["process_start_ticks"]) is not int
        or attempt["process_start_ticks"] < 1
    ):
        _fail("attempt ledger semantics changed")
    _require_digest(attempt["run_nonce"], label="attempt run nonce")
    return attempt, receipt


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _require_scorer_validity_rows(
    value: object,
    numeric: list[float],
    *,
    label: str,
) -> list[dict[str, object]]:
    if type(value) is not list or len(value) != 64:
        _fail(f"{label} scorer/validity denominator changed")
    rows: list[dict[str, object]] = []
    for slot, item in enumerate(value):
        row = _require_ordered_keys(
            item,
            ("ranking", "scorer", "slot_index", "validity"),
            label=f"{label} scorer/validity row",
        )
        if _require_uint(row["slot_index"], maximum=63, label="slot index") != slot:
            _fail(f"{label} scorer/validity rows are not index aligned")
        ranking = _require_ordered_keys(
            row["ranking"],
            (
                "rank_eligible",
                "stable_rank",
                "stable_valid_rank",
                "total_score",
                "valid_rank_eligible",
            ),
            label=f"{label} ranking evidence",
        )
        scorer = _require_ordered_keys(
            row["scorer"],
            ("counts", "failure_code", "status", "total_score", "weighted_terms"),
            label=f"{label} scorer evidence",
        )
        validity = _require_ordered_keys(
            row["validity"],
            (
                "blocker_mask",
                "counts",
                "failure_code",
                "measurements",
                "passed_check_mask",
                "status",
                "upstream_scorer_failure_code",
            ),
            label=f"{label} validity evidence",
        )
        for key in ("rank_eligible", "valid_rank_eligible"):
            _require_bool(ranking[key], label=f"{label} ranking {key}")
        for key in ("stable_rank", "stable_valid_rank"):
            _require_uint(ranking[key], maximum=2**32 - 1, label=f"ranking {key}")
        for owner, keys in (
            (scorer, ("failure_code", "status")),
            (validity, ("failure_code", "status", "upstream_scorer_failure_code")),
        ):
            for key in keys:
                _require_i32(owner[key], label=f"{label} {key}")
        for key in ("blocker_mask", "passed_check_mask"):
            _require_uint(validity[key], maximum=2**32 - 1, label=f"validity {key}")
        scorer_counts = scorer["counts"]
        validity_counts = validity["counts"]
        if type(scorer_counts) is not list or len(scorer_counts) != 5:
            _fail(f"{label} scorer count vector changed")
        if type(validity_counts) is not list or len(validity_counts) != 12:
            _fail(f"{label} validity count vector changed")
        for count in scorer_counts + validity_counts:
            _require_uint(count, label=f"{label} scorer/validity count")
        terms = _require_finite_array(
            scorer["weighted_terms"], count=8, label=f"{label} ScorerV1 terms"
        )
        scorer_total = _require_finite(scorer["total_score"], label="scorer total")
        measurements = _require_finite_array(
            validity["measurements"], count=11, label=f"{label} validity measurements"
        )
        ranking_total = _require_finite(ranking["total_score"], label="ranking total")
        start = slot * NUMERIC_ROW_F64_COUNT
        expected = numeric[start + 76 : start + 97]
        recorded = terms + [scorer_total] + measurements + [ranking_total]
        if len(expected) != 21 or any(
            _canonical_f64_bits(left) != _canonical_f64_bits(right)
            for left, right in zip(recorded, expected)
        ):
            _fail(
                f"{label} labeled score/validity evidence is not bound to numeric projection"
            )
        if _canonical_f64_bits(scorer_total) != _canonical_f64_bits(ranking_total):
            _fail(f"{label} scorer and ranking totals diverged")
        rows.append(row)
    return rows


def _hash_rate(hasher: _CanonicalHasher, value: dict[str, object]) -> None:
    hasher.u64(_require_uint(value["numerator"], label="metric rate numerator"))
    hasher.u64(_require_uint(value["denominator"], label="metric rate denominator"))


def _hash_entropy(hasher: _CanonicalHasher, value: dict[str, object]) -> None:
    for key in (
        "coordinate_ready_count",
        "distinct_coordinate_count",
        "entropy_q32_numerator",
        "entropy_q32_denominator",
        "maximum_entropy_q32",
    ):
        hasher.u64(_require_uint(value[key], label=f"entropy {key}"))


def _hash_lane(hasher: _CanonicalHasher, lane: str) -> None:
    hasher.string(lane)


def _require_lane_authority(value: object, *, label: str) -> dict[str, object]:
    keys = (
        "benchmark_execution_authorized",
        "customer_pose_emission_authorized",
        "denominator_preserved",
        "existing_rank_auto_change_authorized",
        "fallback_allowed",
        "molecular_execution_authorized",
        "multi_anchor_consumed",
        "production_claim_authorized",
        "reservation_authorized",
        "result_dependent_input_consumed",
        "scientific_claim_authorized",
    )
    authority = _require_ordered_keys(value, keys, label=label)
    if authority["denominator_preserved"] is not True or any(
        authority[key] is not False for key in keys if key != "denominator_preserved"
    ):
        _fail(f"{label} is not denominator-preserving and authority-false")
    return authority


def _hash_lane_authority(
    hasher: _CanonicalHasher, authority: dict[str, object]
) -> None:
    for key in (
        "result_dependent_input_consumed",
        "fallback_allowed",
        "multi_anchor_consumed",
        "denominator_preserved",
        "molecular_execution_authorized",
        "reservation_authorized",
        "benchmark_execution_authorized",
        "existing_rank_auto_change_authorized",
        "customer_pose_emission_authorized",
        "production_claim_authorized",
        "scientific_claim_authorized",
    ):
        hasher.byte(int(bool(authority[key])))


def _require_rate(value: object, *, label: str) -> dict[str, object]:
    rate = _require_ordered_keys(value, ("denominator", "numerator"), label=label)
    _require_uint(rate["denominator"], label=f"{label} denominator")
    _require_uint(rate["numerator"], label=f"{label} numerator")
    return rate


def _require_entropy(value: object, *, label: str) -> dict[str, object]:
    entropy = _require_ordered_keys(
        value,
        (
            "coordinate_ready_count",
            "distinct_coordinate_count",
            "entropy_q32_denominator",
            "entropy_q32_numerator",
            "maximum_entropy_q32",
        ),
        label=label,
    )
    for key in entropy:
        _require_uint(entropy[key], label=f"{label} {key}")
    return entropy


def _coordinate_entropy(observations: list[dict[str, object]]) -> dict[str, int]:
    groups: dict[str, int] = {}
    for row in observations:
        if row["coordinate_ready"] is True:
            digest = str(row["final_coordinate_sha256"])
            groups[digest] = groups.get(digest, 0) + 1
    count = sum(groups.values())
    if count == 0:
        return {
            "coordinate_ready_count": 0,
            "distinct_coordinate_count": 0,
            "entropy_q32_denominator": 1,
            "entropy_q32_numerator": 0,
            "maximum_entropy_q32": 0,
        }
    return {
        "coordinate_ready_count": count,
        "distinct_coordinate_count": len(groups),
        "entropy_q32_denominator": count,
        "entropy_q32_numerator": count * LOG2_Q32[count]
        - sum(size * LOG2_Q32[size] for size in groups.values()),
        "maximum_entropy_q32": LOG2_Q32[count],
    }


def _require_positions(
    value: object, *, count: int, label: str
) -> tuple[list[float], ...]:
    positions = _require_ordered_keys(
        value,
        ("x_angstrom", "y_angstrom", "z_angstrom"),
        label=label,
    )
    return tuple(
        _require_finite_array(positions[key], count=count, label=f"{label} {key}")
        for key in ("x_angstrom", "y_angstrom", "z_angstrom")
    )


def _reference_sha256(reference: dict[str, object]) -> str:
    hasher = _CanonicalHasher(
        "betelgeuze.engine_v2_native_fixed64_lane_metrics_reference/1.0.0"
    )
    hasher.string(str(reference["case_id"]))
    hasher.digest(str(reference["reference_pose_source_receipt_sha256"]))
    hasher.digest(str(reference["prepared_ligand_topology_sha256"]))
    coordinates = reference["reference_coordinates"]
    assert isinstance(coordinates, tuple)
    hasher.u64(len(coordinates[0]))
    for atom in range(len(coordinates[0])):
        for channel in coordinates:
            hasher.f64(channel[atom])
    mask = reference["heavy_atom_mask"]
    assert isinstance(mask, list)
    hasher.bytes(bytes(mask))
    permutations = reference["symmetry_permutations"]
    assert isinstance(permutations, list)
    hasher.u64(len(permutations))
    for permutation in permutations:
        assert isinstance(permutation, list)
        hasher.u64(len(permutation))
        for atom in permutation:
            hasher.u32(atom)
    return hasher.finish()


def _require_lane_reference(value: object) -> dict[str, object]:
    reference = _require_ordered_keys(
        value,
        (
            "case_id",
            "heavy_atom_mask",
            "prepared_ligand_topology_sha256",
            "receipt_sha256",
            "reference_coordinates",
            "reference_pose_source_receipt_sha256",
            "symmetry_permutations",
        ),
        label="lane-metrics reference",
    )
    case_id = reference["case_id"]
    if (
        type(case_id) is not str
        or not 1 <= len(case_id) <= 128
        or re.fullmatch(r"[A-Za-z0-9._:/-]+", case_id) is None
    ):
        _fail("lane-metrics reference case identity changed")
    for key in (
        "prepared_ligand_topology_sha256",
        "receipt_sha256",
        "reference_pose_source_receipt_sha256",
    ):
        digest = _require_digest(reference[key], label=f"lane reference {key}")
        if digest == "0" * 64:
            _fail(f"lane reference {key} is absent")
    coordinates = _require_positions(
        reference["reference_coordinates"], count=12, label="reference coordinates"
    )
    mask = reference["heavy_atom_mask"]
    if (
        type(mask) is not list
        or len(mask) != 12
        or any(type(item) is not int or item not in (0, 1) for item in mask)
        or 1 not in mask
    ):
        _fail("lane-metrics heavy-atom mask changed")
    permutations = reference["symmetry_permutations"]
    if type(permutations) is not list or not 1 <= len(permutations) <= 1024:
        _fail("lane-metrics symmetry permutation count changed")
    expected = list(range(12))
    for permutation in permutations:
        if (
            type(permutation) is not list
            or len(permutation) != 12
            or any(type(item) is not int for item in permutation)
            or sorted(permutation) != expected
            or any(
                mask[index] != mask[candidate]
                for index, candidate in enumerate(permutation)
            )
        ):
            _fail("lane-metrics symmetry permutation is invalid")
    if permutations != sorted(permutations) or permutations[0] != expected:
        _fail("lane-metrics symmetry permutations are not canonical")
    reference = dict(reference)
    reference["reference_coordinates"] = coordinates
    if _reference_sha256(reference) != reference["receipt_sha256"]:
        _fail("lane-metrics reference receipt does not rederive")
    return reference


def _canonical_orientation_sha256(values: list[float]) -> str:
    canonical = [0.0 if value == 0.0 else value for value in values]
    first = next((value for value in canonical if value != 0.0), None)
    if first is not None and math.copysign(1.0, first) < 0:
        canonical = [-value for value in canonical]
    hasher = _CanonicalHasher(
        "betelgeuze.engine_v2_native_fixed64_canonical_orientation/1.0.0"
    )
    for value in canonical:
        hasher.f64(value)
    return hasher.finish()


def _observation_sha256(value: dict[str, object]) -> str:
    hasher = _CanonicalHasher(
        "betelgeuze.engine_v2_native_fixed64_lane_metric_observation/1.0.0"
    )
    hasher.u32(int(value["slot_index"]))
    _hash_lane(hasher, str(value["lane"]))
    hasher.byte(int(bool(value["coordinate_ready"])))
    hasher.digest(str(value["final_coordinate_sha256"]))
    hasher.byte(int(bool(value["orientation_available"])))
    hasher.digest(str(value["canonical_orientation_sha256"]))
    for key in (
        "initial_severe_penetration",
        "post_refinement_severe_penetration",
        "exact_valid",
        "rmsd_evaluated",
    ):
        hasher.byte(int(bool(value[key])))
    hasher.f64(float(value["symmetry_aware_direct_heavy_atom_rmsd_angstrom"]))
    hasher.u32(int(value["symmetry_permutation_index"]))
    hasher.byte(int(bool(value["oracle_2a"])))
    hasher.byte(int(bool(value["valid_oracle_2a"])))
    hasher.u32(int(value["stable_rank"]))
    hasher.u32(int(value["stable_valid_rank"]))
    return hasher.finish()


def _lane_for_slot(slot: int) -> tuple[int, str, int, int]:
    for raw, (name, first, last) in enumerate(LANE_RANGES):
        if first <= slot <= last:
            return raw, name, first, last
    raise AssertionError("fixed64 slot outside frozen lanes")


def _require_lane_source_rows(
    value: object,
    scorer_validity_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    keys = (
        "cluster_eligible",
        "cluster_id",
        "coordinates_available",
        "geometric_decision",
        "geometric_status",
        "lane",
        "placement_quaternion",
        "post_admission_decision",
        "post_admission_status",
        "refinement_coordinate_available",
        "refinement_coordinate_sha256",
        "refinement_status",
        "slot_index",
        "stable_rank",
        "stable_valid_rank",
        "valid_rank_eligible",
        "validity_blocker_mask",
        "validity_passed_check_mask",
        "validity_status",
    )
    if type(value) is not list or len(value) != 64:
        _fail("lane-metrics source-row denominator changed")
    rows: list[dict[str, object]] = []
    for slot, item in enumerate(value):
        row = _require_ordered_keys(item, keys, label="lane-metrics source row")
        raw_lane, _, _, _ = _lane_for_slot(slot)
        if (
            _require_uint(row["slot_index"], maximum=63, label="source slot") != slot
            or _require_i32(row["lane"], label="source lane") != raw_lane
        ):
            _fail("lane-metrics source rows are not aligned with the frozen allocation")
        for key in (
            "cluster_eligible",
            "coordinates_available",
            "refinement_coordinate_available",
            "valid_rank_eligible",
        ):
            _require_bool(row[key], label=f"lane source {key}")
        for key in (
            "geometric_decision",
            "geometric_status",
            "post_admission_decision",
            "post_admission_status",
            "refinement_status",
            "validity_status",
        ):
            _require_i32(row[key], label=f"lane source {key}")
        for key in (
            "cluster_id",
            "stable_rank",
            "stable_valid_rank",
            "validity_blocker_mask",
            "validity_passed_check_mask",
        ):
            _require_uint(row[key], maximum=2**32 - 1, label=f"lane source {key}")
        _require_finite_array(
            row["placement_quaternion"], count=4, label="placement quaternion"
        )
        _require_digest(
            row["refinement_coordinate_sha256"], label="refinement coordinate"
        )
        scorer_row = scorer_validity_rows[slot]
        validity = scorer_row["validity"]
        ranking = scorer_row["ranking"]
        assert isinstance(validity, dict)
        assert isinstance(ranking, dict)
        if (
            row["validity_status"] != validity["status"]
            or row["validity_passed_check_mask"] != validity["passed_check_mask"]
            or row["validity_blocker_mask"] != validity["blocker_mask"]
            or row["valid_rank_eligible"] != ranking["valid_rank_eligible"]
            or row["stable_rank"] != ranking["stable_rank"]
            or row["stable_valid_rank"] != ranking["stable_valid_rank"]
        ):
            _fail("lane-metrics source row is cross-wired from score/validity evidence")
        rows.append(row)
    return rows


def _require_lane_observations(
    value: object,
    *,
    source_rows: list[dict[str, object]],
    reference: dict[str, object],
    final_coordinates: tuple[list[float], ...],
) -> list[dict[str, object]]:
    keys = (
        "canonical_orientation_sha256",
        "coordinate_ready",
        "exact_valid",
        "final_coordinate_sha256",
        "initial_severe_penetration",
        "lane",
        "oracle_2a",
        "orientation_available",
        "post_refinement_severe_penetration",
        "receipt_sha256",
        "rmsd_evaluated",
        "slot_index",
        "stable_rank",
        "stable_valid_rank",
        "symmetry_aware_direct_heavy_atom_rmsd_angstrom",
        "symmetry_permutation_index",
        "valid_oracle_2a",
    )
    if type(value) is not list or len(value) != 64:
        _fail("lane-metrics observation denominator changed")
    reference_coordinates = reference["reference_coordinates"]
    heavy_mask = reference["heavy_atom_mask"]
    permutations = reference["symmetry_permutations"]
    assert isinstance(reference_coordinates, tuple)
    assert isinstance(heavy_mask, list)
    assert isinstance(permutations, list)
    heavy_count = sum(heavy_mask)
    observations: list[dict[str, object]] = []
    for slot, item in enumerate(value):
        row = _require_ordered_keys(item, keys, label="lane-metrics observation")
        source = source_rows[slot]
        _, lane, _, _ = _lane_for_slot(slot)
        if (
            _require_uint(row["slot_index"], maximum=63, label="observation slot")
            != slot
            or row["lane"] != lane
        ):
            _fail("lane-metrics observations are not aligned with frozen lanes")
        for key in (
            "coordinate_ready",
            "exact_valid",
            "initial_severe_penetration",
            "oracle_2a",
            "orientation_available",
            "post_refinement_severe_penetration",
            "rmsd_evaluated",
            "valid_oracle_2a",
        ):
            _require_bool(row[key], label=f"observation {key}")
        for key in (
            "canonical_orientation_sha256",
            "final_coordinate_sha256",
            "receipt_sha256",
        ):
            _require_digest(row[key], label=f"observation {key}")
        for key in (
            "stable_rank",
            "stable_valid_rank",
            "symmetry_permutation_index",
        ):
            _require_uint(row[key], maximum=2**32 - 1, label=f"observation {key}")
        recorded_rmsd = _require_finite(
            row["symmetry_aware_direct_heavy_atom_rmsd_angstrom"],
            label="observation RMSD",
        )
        coordinate_ready = (
            source["refinement_status"] == 1
            and source["refinement_coordinate_available"] is True
        )
        orientation_available = source["coordinates_available"] is True
        quaternion = source["placement_quaternion"]
        assert isinstance(quaternion, list)
        expected_orientation = (
            _canonical_orientation_sha256(quaternion)
            if orientation_available
            else "0" * 64
        )
        exact_valid = (
            source["validity_status"] == 1
            and source["validity_passed_check_mask"] == 0xFF
            and source["validity_blocker_mask"] == 0
            and source["valid_rank_eligible"] is True
        )
        permutation_index = MISSING_SLOT_INDEX
        rmsd = 0.0
        if coordinate_ready:
            best = math.inf
            offset = slot * 12
            for candidate_index, permutation in enumerate(permutations):
                squared_sum = 0.0
                for atom, candidate_atom in enumerate(permutation):
                    if heavy_mask[atom] == 0:
                        continue
                    squared_sum += sum(
                        (
                            reference_coordinates[channel][atom]
                            - final_coordinates[channel][offset + candidate_atom]
                        )
                        ** 2
                        for channel in range(3)
                    )
                candidate_rmsd = math.sqrt(squared_sum / heavy_count)
                if candidate_rmsd < best:
                    best = candidate_rmsd
                    permutation_index = candidate_index
            rmsd = best
        oracle = coordinate_ready and rmsd <= 2.0
        expected_scalars = {
            "coordinate_ready": coordinate_ready,
            "exact_valid": exact_valid,
            "final_coordinate_sha256": source["refinement_coordinate_sha256"]
            if coordinate_ready
            else "0" * 64,
            "initial_severe_penetration": source["geometric_status"] == 1
            and source["geometric_decision"] == 2,
            "oracle_2a": oracle,
            "orientation_available": orientation_available,
            "post_refinement_severe_penetration": source["post_admission_status"] == 1
            and source["post_admission_decision"] == 2,
            "rmsd_evaluated": coordinate_ready,
            "stable_rank": source["stable_rank"],
            "stable_valid_rank": source["stable_valid_rank"],
            "symmetry_permutation_index": permutation_index,
            "valid_oracle_2a": oracle and exact_valid,
        }
        if any(row[key] != expected for key, expected in expected_scalars.items()):
            _fail("lane-metrics observation does not rederive from recorded inputs")
        if row["canonical_orientation_sha256"] != expected_orientation:
            _fail("lane-metrics orientation identity does not rederive")
        if not math.isclose(recorded_rmsd, rmsd, rel_tol=0.0, abs_tol=1e-12):
            _fail("lane-metrics RMSD does not rederive")
        if _observation_sha256(row) != row["receipt_sha256"]:
            _fail("lane-metrics observation receipt does not rederive")
        observations.append(row)
    return observations


def _rate(numerator: int, denominator: int) -> dict[str, int]:
    return {"denominator": denominator, "numerator": numerator}


def _lane_summary_sha256(value: dict[str, object]) -> str:
    hasher = _CanonicalHasher(
        "betelgeuze.engine_v2_native_fixed64_lane_metric_summary/1.0.0"
    )
    _hash_lane(hasher, str(value["lane"]))
    for key in (
        "first_slot_index",
        "slot_count",
        "generated_count",
        "typed_failure_count",
        "coordinate_ready_count",
        "exact_coordinate_unique_count",
        "exact_coordinate_duplicate_count",
        "cluster_eligible_count",
        "unique_valid_pose_cluster_count",
        "orientation_available_count",
        "unique_orientation_count",
        "orientation_duplicate_count",
        "initial_geometric_evaluated_count",
        "initial_severe_penetration_count",
        "post_geometric_evaluated_count",
        "post_severe_penetration_count",
        "exact_valid_count",
        "oracle_2a_count",
        "valid_oracle_2a_count",
    ):
        hasher.u64(int(value[key]))
    for key in (
        "exact_coordinate_unique_rate",
        "unique_valid_pose_rate",
        "orientation_duplicate_rate",
        "initial_severe_penetration_rate",
        "post_severe_penetration_rate",
        "exact_valid_contribution",
        "oracle_contribution",
        "valid_oracle_contribution",
    ):
        rate = value[key]
        assert isinstance(rate, dict)
        _hash_rate(hasher, rate)
    hasher.byte(int(bool(value["incremental_oracle_case_recovery"])))
    hasher.byte(int(bool(value["incremental_valid_oracle_case_recovery"])))
    entropy = value["coordinate_entropy"]
    assert isinstance(entropy, dict)
    _hash_entropy(hasher, entropy)
    return hasher.finish()


def _require_lane_summaries(
    value: object,
    *,
    observations: list[dict[str, object]],
    source_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    keys = (
        "cluster_eligible_count",
        "coordinate_entropy",
        "coordinate_ready_count",
        "exact_coordinate_duplicate_count",
        "exact_coordinate_unique_count",
        "exact_coordinate_unique_rate",
        "exact_valid_contribution",
        "exact_valid_count",
        "first_slot_index",
        "generated_count",
        "incremental_oracle_case_recovery",
        "incremental_valid_oracle_case_recovery",
        "initial_geometric_evaluated_count",
        "initial_severe_penetration_count",
        "initial_severe_penetration_rate",
        "lane",
        "oracle_2a_count",
        "oracle_contribution",
        "orientation_available_count",
        "orientation_duplicate_count",
        "orientation_duplicate_rate",
        "post_geometric_evaluated_count",
        "post_severe_penetration_count",
        "post_severe_penetration_rate",
        "receipt_sha256",
        "slot_count",
        "typed_failure_count",
        "unique_orientation_count",
        "unique_valid_pose_cluster_count",
        "unique_valid_pose_rate",
        "valid_oracle_2a_count",
        "valid_oracle_contribution",
    )
    if type(value) is not list or len(value) != len(LANE_RANGES):
        _fail("lane summary count changed")
    global_exact_valid = sum(row["exact_valid"] is True for row in observations)
    global_oracle = sum(row["oracle_2a"] is True for row in observations)
    global_valid_oracle = sum(row["valid_oracle_2a"] is True for row in observations)
    control_oracle = any(
        row["lane"] in CONTROL_LANES and row["oracle_2a"] is True
        for row in observations
    )
    control_valid_oracle = any(
        row["lane"] in CONTROL_LANES and row["valid_oracle_2a"] is True
        for row in observations
    )
    summaries: list[dict[str, object]] = []
    for lane_index, (lane, first, last) in enumerate(LANE_RANGES):
        summary = _require_ordered_keys(value[lane_index], keys, label="lane summary")
        rows = observations[first : last + 1]
        sources = source_rows[first : last + 1]
        coordinate_ready = [row for row in rows if row["coordinate_ready"] is True]
        coordinate_ids = {
            str(row["final_coordinate_sha256"]) for row in coordinate_ready
        }
        orientation_rows = [row for row in rows if row["orientation_available"] is True]
        orientation_ids = {
            str(row["canonical_orientation_sha256"]) for row in orientation_rows
        }
        cluster_rows = [
            source for source in sources if source["cluster_eligible"] is True
        ]
        cluster_ids = {int(source["cluster_id"]) for source in cluster_rows}
        generated = sum(source["coordinates_available"] is True for source in sources)
        initial_evaluated = sum(source["geometric_status"] == 1 for source in sources)
        post_evaluated = sum(source["post_admission_status"] == 1 for source in sources)
        exact_valid = sum(row["exact_valid"] is True for row in rows)
        oracle = sum(row["oracle_2a"] is True for row in rows)
        valid_oracle = sum(row["valid_oracle_2a"] is True for row in rows)
        expected: dict[str, object] = {
            "cluster_eligible_count": len(cluster_rows),
            "coordinate_entropy": _coordinate_entropy(rows),
            "coordinate_ready_count": len(coordinate_ready),
            "exact_coordinate_duplicate_count": len(coordinate_ready)
            - len(coordinate_ids),
            "exact_coordinate_unique_count": len(coordinate_ids),
            "exact_coordinate_unique_rate": _rate(
                len(coordinate_ids), len(coordinate_ready)
            ),
            "exact_valid_contribution": _rate(exact_valid, global_exact_valid),
            "exact_valid_count": exact_valid,
            "first_slot_index": first,
            "generated_count": generated,
            "incremental_oracle_case_recovery": lane not in CONTROL_LANES
            and not control_oracle
            and oracle > 0,
            "incremental_valid_oracle_case_recovery": lane not in CONTROL_LANES
            and not control_valid_oracle
            and valid_oracle > 0,
            "initial_geometric_evaluated_count": initial_evaluated,
            "initial_severe_penetration_count": sum(
                row["initial_severe_penetration"] is True for row in rows
            ),
            "initial_severe_penetration_rate": _rate(
                sum(row["initial_severe_penetration"] is True for row in rows),
                initial_evaluated,
            ),
            "lane": lane,
            "oracle_2a_count": oracle,
            "oracle_contribution": _rate(oracle, global_oracle),
            "orientation_available_count": len(orientation_rows),
            "orientation_duplicate_count": len(orientation_rows) - len(orientation_ids),
            "orientation_duplicate_rate": _rate(
                len(orientation_rows) - len(orientation_ids), len(orientation_rows)
            ),
            "post_geometric_evaluated_count": post_evaluated,
            "post_severe_penetration_count": sum(
                row["post_refinement_severe_penetration"] is True for row in rows
            ),
            "post_severe_penetration_rate": _rate(
                sum(row["post_refinement_severe_penetration"] is True for row in rows),
                post_evaluated,
            ),
            "slot_count": last - first + 1,
            "typed_failure_count": last - first + 1 - generated,
            "unique_orientation_count": len(orientation_ids),
            "unique_valid_pose_cluster_count": len(cluster_ids),
            "unique_valid_pose_rate": _rate(len(cluster_ids), len(cluster_rows)),
            "valid_oracle_2a_count": valid_oracle,
            "valid_oracle_contribution": _rate(valid_oracle, global_valid_oracle),
        }
        _require_digest(summary["receipt_sha256"], label="lane summary receipt")
        for key, expected_value in expected.items():
            if summary[key] != expected_value:
                _fail(f"lane summary {lane} does not rederive: {key}")
        for rate_key in (
            "exact_coordinate_unique_rate",
            "exact_valid_contribution",
            "initial_severe_penetration_rate",
            "oracle_contribution",
            "orientation_duplicate_rate",
            "post_severe_penetration_rate",
            "unique_valid_pose_rate",
            "valid_oracle_contribution",
        ):
            _require_rate(summary[rate_key], label=f"lane summary {rate_key}")
        _require_entropy(summary["coordinate_entropy"], label="lane coordinate entropy")
        if _lane_summary_sha256(summary) != summary["receipt_sha256"]:
            _fail("lane summary receipt does not rederive")
        summaries.append(summary)
    return summaries


def _oracle_selection_sha256(value: dict[str, object]) -> str:
    hasher = _CanonicalHasher(
        "betelgeuze.engine_v2_native_fixed64_oracle_selection_summary/1.0.0"
    )
    hasher.u32(int(value["proposal_oracle_slot_index"]))
    hasher.f64(float(value["proposal_oracle_rmsd_angstrom"]))
    hasher.byte(int(bool(value["proposal_oracle_success"])))
    hasher.u32(int(value["valid_proposal_oracle_slot_index"]))
    hasher.f64(float(value["valid_proposal_oracle_rmsd_angstrom"]))
    hasher.byte(int(bool(value["valid_proposal_oracle_success"])))
    hasher.u32(int(value["selected_top1_slot_index"]))
    hasher.byte(int(bool(value["selected_top1_rmsd_evaluated"])))
    hasher.f64(float(value["selected_top1_rmsd_angstrom"]))
    hasher.byte(int(bool(value["selected_top1_exact_valid"])))
    hasher.byte(int(bool(value["selected_top1_oracle_success"])))
    hasher.byte(int(bool(value["selected_top5_oracle_present"])))
    hasher.byte(int(bool(value["selected_top5_valid_oracle_present"])))
    hasher.byte(
        {
            "success": 0,
            "proposal_failure": 1,
            "validity_failure": 2,
            "ranking_failure": 3,
        }[str(value["failure_class"])]
    )
    return hasher.finish()


def _require_oracle_selection(
    value: object,
    *,
    observations: list[dict[str, object]],
    primary_slots: list[int],
) -> dict[str, object]:
    keys = (
        "failure_class",
        "proposal_oracle_rmsd_angstrom",
        "proposal_oracle_slot_index",
        "proposal_oracle_success",
        "receipt_sha256",
        "selected_top1_exact_valid",
        "selected_top1_oracle_success",
        "selected_top1_rmsd_angstrom",
        "selected_top1_rmsd_evaluated",
        "selected_top1_slot_index",
        "selected_top5_oracle_present",
        "selected_top5_valid_oracle_present",
        "valid_proposal_oracle_rmsd_angstrom",
        "valid_proposal_oracle_slot_index",
        "valid_proposal_oracle_success",
    )
    oracle = _require_ordered_keys(value, keys, label="oracle selection")
    available = [row for row in observations if row["rmsd_evaluated"] is True]
    valid = [row for row in available if row["exact_valid"] is True]
    proposal = min(
        available,
        key=lambda row: (
            float(row["symmetry_aware_direct_heavy_atom_rmsd_angstrom"]),
            int(row["slot_index"]),
        ),
        default=None,
    )
    valid_proposal = min(
        valid,
        key=lambda row: (
            float(row["symmetry_aware_direct_heavy_atom_rmsd_angstrom"]),
            int(row["slot_index"]),
        ),
        default=None,
    )
    top1 = observations[primary_slots[0]] if primary_slots else None
    top5 = [observations[slot] for slot in primary_slots[:5]]
    proposal_success = bool(
        proposal is not None
        and float(proposal["symmetry_aware_direct_heavy_atom_rmsd_angstrom"]) <= 2.0
    )
    valid_success = bool(
        valid_proposal is not None
        and float(valid_proposal["symmetry_aware_direct_heavy_atom_rmsd_angstrom"])
        <= 2.0
    )
    top1_success = bool(top1 is not None and top1["valid_oracle_2a"] is True)
    failure_class = (
        "proposal_failure"
        if not proposal_success
        else "validity_failure"
        if not valid_success
        else "ranking_failure"
        if not top1_success
        else "success"
    )
    expected: dict[str, object] = {
        "failure_class": failure_class,
        "proposal_oracle_rmsd_angstrom": 0.0
        if proposal is None
        else proposal["symmetry_aware_direct_heavy_atom_rmsd_angstrom"],
        "proposal_oracle_slot_index": MISSING_SLOT_INDEX
        if proposal is None
        else proposal["slot_index"],
        "proposal_oracle_success": proposal_success,
        "selected_top1_exact_valid": bool(top1 and top1["exact_valid"] is True),
        "selected_top1_oracle_success": top1_success,
        "selected_top1_rmsd_angstrom": 0.0
        if top1 is None
        else top1["symmetry_aware_direct_heavy_atom_rmsd_angstrom"],
        "selected_top1_rmsd_evaluated": bool(top1 and top1["rmsd_evaluated"] is True),
        "selected_top1_slot_index": MISSING_SLOT_INDEX
        if top1 is None
        else top1["slot_index"],
        "selected_top5_oracle_present": any(row["oracle_2a"] is True for row in top5),
        "selected_top5_valid_oracle_present": any(
            row["valid_oracle_2a"] is True for row in top5
        ),
        "valid_proposal_oracle_rmsd_angstrom": 0.0
        if valid_proposal is None
        else valid_proposal["symmetry_aware_direct_heavy_atom_rmsd_angstrom"],
        "valid_proposal_oracle_slot_index": MISSING_SLOT_INDEX
        if valid_proposal is None
        else valid_proposal["slot_index"],
        "valid_proposal_oracle_success": valid_success,
    }
    for key, expected_value in expected.items():
        if oracle[key] != expected_value:
            _fail(f"oracle selection does not rederive: {key}")
    _require_digest(oracle["receipt_sha256"], label="oracle selection receipt")
    if _oracle_selection_sha256(oracle) != oracle["receipt_sha256"]:
        _fail("oracle selection receipt does not rederive")
    return oracle


def _conformer_sha256(value: dict[str, object]) -> str:
    hasher = _CanonicalHasher(
        "betelgeuze.engine_v2_native_fixed64_conformer_orientation_interaction/1.0.0"
    )
    for key in (
        "predeclared_pair_count",
        "both_coordinate_ready_count",
        "conformer_lower_rmsd_count",
        "source_lower_rmsd_count",
        "rmsd_tie_count",
        "conformer_oracle_gain_count",
        "conformer_oracle_loss_count",
        "both_oracle_count",
        "neither_oracle_count",
        "conformer_valid_oracle_gain_count",
        "conformer_valid_oracle_loss_count",
    ):
        hasher.u64(int(value[key]))
    return hasher.finish()


def _require_conformer_interaction(
    value: object,
    *,
    observations: list[dict[str, object]],
) -> dict[str, object]:
    keys = (
        "both_coordinate_ready_count",
        "both_oracle_count",
        "conformer_lower_rmsd_count",
        "conformer_oracle_gain_count",
        "conformer_oracle_loss_count",
        "conformer_valid_oracle_gain_count",
        "conformer_valid_oracle_loss_count",
        "neither_oracle_count",
        "predeclared_pair_count",
        "receipt_sha256",
        "rmsd_tie_count",
        "source_lower_rmsd_count",
    )
    interaction = _require_ordered_keys(value, keys, label="conformer interaction")
    expected = {key: 0 for key in keys if key != "receipt_sha256"}
    expected["predeclared_pair_count"] = 8
    for source_slot, conformer_slot in CONFORMER_ORIENTATION_PAIRS:
        source = observations[source_slot]
        conformer = observations[conformer_slot]
        if source["rmsd_evaluated"] is True and conformer["rmsd_evaluated"] is True:
            expected["both_coordinate_ready_count"] += 1
            source_rmsd = float(
                source["symmetry_aware_direct_heavy_atom_rmsd_angstrom"]
            )
            conformer_rmsd = float(
                conformer["symmetry_aware_direct_heavy_atom_rmsd_angstrom"]
            )
            if conformer_rmsd < source_rmsd:
                expected["conformer_lower_rmsd_count"] += 1
            elif conformer_rmsd > source_rmsd:
                expected["source_lower_rmsd_count"] += 1
            else:
                expected["rmsd_tie_count"] += 1
        pair = (source["oracle_2a"], conformer["oracle_2a"])
        if pair == (False, True):
            expected["conformer_oracle_gain_count"] += 1
        elif pair == (True, False):
            expected["conformer_oracle_loss_count"] += 1
        elif pair == (True, True):
            expected["both_oracle_count"] += 1
        else:
            expected["neither_oracle_count"] += 1
        valid_pair = (source["valid_oracle_2a"], conformer["valid_oracle_2a"])
        if valid_pair == (False, True):
            expected["conformer_valid_oracle_gain_count"] += 1
        elif valid_pair == (True, False):
            expected["conformer_valid_oracle_loss_count"] += 1
    for key, expected_value in expected.items():
        if interaction[key] != expected_value:
            _fail(f"conformer/orientation interaction does not rederive: {key}")
    _require_digest(interaction["receipt_sha256"], label="conformer receipt")
    if _conformer_sha256(interaction) != interaction["receipt_sha256"]:
        _fail("conformer/orientation receipt does not rederive")
    return interaction


def _lane_metrics_decision_sha256(
    value: dict[str, object],
    observations: list[dict[str, object]],
    summaries: list[dict[str, object]],
    oracle: dict[str, object],
    interaction: dict[str, object],
    authority: dict[str, object],
) -> str:
    hasher = _CanonicalHasher(
        "betelgeuze.engine_v2_native_fixed64_lane_metrics_decision/1.0.0"
    )
    hasher.u64(int(value["candidate_denominator"]))
    hasher.f64(float(value["rmsd_threshold_angstrom"]))
    hasher.u64(len(observations))
    for row in observations:
        hasher.u32(int(row["slot_index"]))
        _hash_lane(hasher, str(row["lane"]))
        for key in (
            "coordinate_ready",
            "orientation_available",
            "initial_severe_penetration",
            "post_refinement_severe_penetration",
            "exact_valid",
            "rmsd_evaluated",
            "oracle_2a",
            "valid_oracle_2a",
        ):
            hasher.byte(int(bool(row[key])))
        hasher.u32(int(row["stable_rank"]))
        hasher.u32(int(row["stable_valid_rank"]))
    hasher.u64(len(summaries))
    for summary in summaries:
        hasher.digest(str(summary["receipt_sha256"]))
    hasher.u32(int(oracle["proposal_oracle_slot_index"]))
    hasher.byte(int(bool(oracle["proposal_oracle_success"])))
    hasher.u32(int(oracle["valid_proposal_oracle_slot_index"]))
    hasher.byte(int(bool(oracle["valid_proposal_oracle_success"])))
    hasher.u32(int(oracle["selected_top1_slot_index"]))
    for key in (
        "selected_top1_rmsd_evaluated",
        "selected_top1_exact_valid",
        "selected_top1_oracle_success",
        "selected_top5_oracle_present",
        "selected_top5_valid_oracle_present",
    ):
        hasher.byte(int(bool(oracle[key])))
    hasher.byte(
        {
            "success": 0,
            "proposal_failure": 1,
            "validity_failure": 2,
            "ranking_failure": 3,
        }[str(oracle["failure_class"])]
    )
    hasher.digest(str(interaction["receipt_sha256"]))
    _hash_lane_authority(hasher, authority)
    for key in (
        "result_dependent_allocation_consumed",
        "metrics_used_to_change_rank",
        "product_execution_authorized",
        "public_or_scientific_claim_authorized",
    ):
        hasher.byte(int(bool(value[key])))
    return hasher.finish()


def _lane_metrics_receipt_sha256(
    value: dict[str, object],
    observations: list[dict[str, object]],
    summaries: list[dict[str, object]],
    oracle: dict[str, object],
    interaction: dict[str, object],
    authority: dict[str, object],
) -> str:
    reference = value["reference"]
    entropy = value["global_coordinate_entropy"]
    assert isinstance(reference, dict)
    assert isinstance(entropy, dict)
    hasher = _CanonicalHasher(LANE_METRICS_SCHEMA_ID)
    for key in (
        "receipt_sha256",
        "pipeline_source_bundle_receipt_sha256",
        "pipeline_cluster_batch_receipt_sha256",
        "scientific_projection_sha256",
        "decision_sha256",
    ):
        owner = reference if key == "receipt_sha256" else value
        hasher.digest(str(owner[key]))
    hasher.u64(int(value["candidate_denominator"]))
    hasher.f64(float(value["rmsd_threshold_angstrom"]))
    hasher.u64(len(observations))
    for row in observations:
        hasher.digest(str(row["receipt_sha256"]))
    hasher.u64(len(summaries))
    for summary in summaries:
        hasher.digest(str(summary["receipt_sha256"]))
    _hash_entropy(hasher, entropy)
    hasher.digest(str(oracle["receipt_sha256"]))
    hasher.digest(str(interaction["receipt_sha256"]))
    _hash_lane_authority(hasher, authority)
    for key in (
        "result_dependent_allocation_consumed",
        "metrics_used_to_change_rank",
        "product_execution_authorized",
        "public_or_scientific_claim_authorized",
    ):
        hasher.byte(int(bool(value[key])))
    return hasher.finish()


def _require_lane_metrics(
    value: object,
    *,
    projection_sha256: str,
    scorer_validity_rows: list[dict[str, object]],
) -> dict[str, object]:
    keys = (
        "authority",
        "candidate_denominator",
        "conformer_orientation_interaction",
        "decision_sha256",
        "final_coordinates",
        "global_coordinate_entropy",
        "lane_summaries",
        "metrics_used_to_change_rank",
        "observations",
        "oracle_selection",
        "pipeline_cluster_batch_receipt_sha256",
        "pipeline_source_bundle_receipt_sha256",
        "primary_slot_indices",
        "product_execution_authorized",
        "public_or_scientific_claim_authorized",
        "receipt_sha256",
        "reference",
        "result_dependent_allocation_consumed",
        "rmsd_threshold_angstrom",
        "scientific_projection_sha256",
        "schema_id",
        "source_rows",
    )
    metrics = _require_ordered_keys(value, keys, label="lane-metrics receipt")
    if (
        metrics["schema_id"] != LANE_METRICS_SCHEMA_ID
        or metrics["candidate_denominator"] != 64
        or metrics["rmsd_threshold_angstrom"] != 2.0
        or metrics["scientific_projection_sha256"] != projection_sha256
    ):
        _fail("lane-metrics profile identity changed")
    for key in (
        "metrics_used_to_change_rank",
        "product_execution_authorized",
        "public_or_scientific_claim_authorized",
        "result_dependent_allocation_consumed",
    ):
        if metrics[key] is not False:
            _fail("lane-metrics authority or mutation flag is not false")
    for key in (
        "decision_sha256",
        "pipeline_cluster_batch_receipt_sha256",
        "pipeline_source_bundle_receipt_sha256",
        "receipt_sha256",
        "scientific_projection_sha256",
    ):
        digest = _require_digest(metrics[key], label=f"lane metrics {key}")
        if digest == "0" * 64:
            _fail(f"lane metrics {key} is absent")
    authority = _require_lane_authority(metrics["authority"], label="lane authority")
    reference = _require_lane_reference(metrics["reference"])
    final_coordinates = _require_positions(
        metrics["final_coordinates"], count=64 * 12, label="final coordinates"
    )
    source_rows = _require_lane_source_rows(
        metrics["source_rows"], scorer_validity_rows
    )
    observations = _require_lane_observations(
        metrics["observations"],
        source_rows=source_rows,
        reference=reference,
        final_coordinates=final_coordinates,
    )
    summaries = _require_lane_summaries(
        metrics["lane_summaries"],
        observations=observations,
        source_rows=source_rows,
    )
    entropy = _require_entropy(
        metrics["global_coordinate_entropy"], label="global coordinate entropy"
    )
    if entropy != _coordinate_entropy(observations):
        _fail("global coordinate entropy does not rederive")
    primary = metrics["primary_slot_indices"]
    if (
        type(primary) is not list
        or any(type(slot) is not int or not 0 <= slot < 64 for slot in primary)
        or len(primary) != len(set(primary))
    ):
        _fail("lane primary rank indices are invalid")
    if primary != sorted(
        [slot for slot in range(64) if source_rows[slot]["stable_rank"] > 0],
        key=lambda slot: source_rows[slot]["stable_rank"],
    ):
        _fail("lane primary ranks do not rederive")
    oracle = _require_oracle_selection(
        metrics["oracle_selection"], observations=observations, primary_slots=primary
    )
    interaction = _require_conformer_interaction(
        metrics["conformer_orientation_interaction"], observations=observations
    )
    if (
        _lane_metrics_decision_sha256(
            metrics, observations, summaries, oracle, interaction, authority
        )
        != metrics["decision_sha256"]
    ):
        _fail("lane-metrics decision receipt does not rederive")
    if (
        _lane_metrics_receipt_sha256(
            metrics, observations, summaries, oracle, interaction, authority
        )
        != metrics["receipt_sha256"]
    ):
        _fail("full lane-metrics receipt does not rederive")
    return metrics


def _require_backend_rederivable_evidence(
    value: object,
    *,
    projection_sha256: str,
    projection_decision_sha256: str,
    label: str,
) -> dict[str, object]:
    evidence = _require_ordered_keys(
        value,
        (
            "decision_preimage",
            "lane_metrics",
            "numeric_projection",
            "projection_decision_sha256",
            "projection_digest_stream",
            "projection_sha256",
            "schema_id",
            "scorer_validity_rows",
        ),
        label=f"{label} rederivable evidence",
    )
    if (
        evidence["schema_id"]
        != "betelgeuze.engine_v2_native_fixed64_cpu_backend_evidence/7.0.0"
        or evidence["projection_sha256"] != projection_sha256
        or evidence["projection_decision_sha256"] != projection_decision_sha256
    ):
        _fail(f"{label} rederivable evidence identity changed")
    _require_digest(projection_sha256, label=f"{label} projection")
    _require_digest(projection_decision_sha256, label=f"{label} decision")
    decision_preimage = _require_canonical_bytes(
        evidence["decision_preimage"],
        domain=b"",
        expected_count=None,
        maximum_count=MAX_ARTIFACT_BYTES,
        label=f"{label} decision preimage",
    )
    decision_domain = SCIENTIFIC_DECISION_DOMAIN.encode("ascii")
    decision_prefix = len(decision_domain).to_bytes(8, "big") + decision_domain
    if (
        not decision_preimage.startswith(decision_prefix)
        or _sha256(decision_preimage) != projection_decision_sha256
    ):
        _fail(f"{label} decision preimage does not bind the scientific decision")
    digest_stream = _require_canonical_bytes(
        evidence["projection_digest_stream"],
        domain=PROJECTION_DIGEST_STREAM_DOMAIN,
        expected_count=PROJECTION_DIGEST_STREAM_BYTES,
        maximum_count=PROJECTION_DIGEST_STREAM_BYTES,
        label=f"{label} projection digest stream",
    )
    numeric = _require_numeric_projection(evidence["numeric_projection"], label=label)
    rows = _require_scorer_validity_rows(
        evidence["scorer_validity_rows"], numeric, label=label
    )
    if (
        _scientific_projection_sha256(
            projection_decision_sha256=projection_decision_sha256,
            digest_stream=digest_stream,
            numeric=numeric,
        )
        != projection_sha256
    ):
        _fail(f"{label} scientific projection digest does not rederive")
    metrics = _require_lane_metrics(
        evidence["lane_metrics"],
        projection_sha256=projection_sha256,
        scorer_validity_rows=rows,
    )
    evidence = dict(evidence)
    evidence["decision_preimage_bytes"] = decision_preimage
    evidence["projection_digest_stream_bytes"] = digest_stream
    evidence["numeric_values"] = numeric
    evidence["validated_lane_metrics"] = metrics
    return evidence


def _require_fixture(value: object, *, expected_id: str) -> dict[str, object]:
    fixture_keys = (
        "authority_false",
        "candidate_denominator",
        "cpp_decision_sha256",
        "cpp_generated_count",
        "cpp_lane_metrics_decision_sha256",
        "cpp_lane_metrics_receipt_sha256",
        "cpp_median_nanoseconds",
        "cpp_projection_sha256",
        "cpp_rederivable_evidence",
        "cpp_repeat_stable",
        "cpp_sample_nanoseconds",
        "cpp_typed_failure_count",
        "decision_parity",
        "fixture_id",
        "fixture_payload_sha256",
        "gate_passed",
        "lane_metrics_authority_false",
        "lane_metrics_decision_parity",
        "lane_metrics_rederivable",
        "lane_metrics_reference_sha256",
        "ligand_atom_count",
        "numeric_parity",
        "persistent_cpp_context_count",
        "persistent_rust_context_count",
        "receptor_atom_count",
        "rust_decision_sha256",
        "rust_generated_count",
        "rust_lane_metrics_decision_sha256",
        "rust_lane_metrics_receipt_sha256",
        "rust_median_nanoseconds",
        "rust_projection_sha256",
        "rust_rederivable_evidence",
        "rust_repeat_stable",
        "rust_sample_nanoseconds",
        "rust_to_cpp_median_ratio",
        "rust_typed_failure_count",
        "score_term_count",
    )
    fixture = _require_ordered_keys(value, fixture_keys, label="fixture evidence")
    expected = EXPECTED_FIXTURES[expected_id]
    for key in (
        "cpp_decision_sha256",
        "cpp_lane_metrics_decision_sha256",
        "cpp_lane_metrics_receipt_sha256",
        "cpp_projection_sha256",
        "lane_metrics_reference_sha256",
        "rust_decision_sha256",
        "rust_lane_metrics_decision_sha256",
        "rust_lane_metrics_receipt_sha256",
        "rust_projection_sha256",
    ):
        digest = _require_digest(fixture[key], label=f"fixture {key}")
        if digest == "0" * 64:
            _fail(f"fixture {key} is an unbound zero digest")
    for key in (
        "authority_false",
        "cpp_repeat_stable",
        "decision_parity",
        "gate_passed",
        "lane_metrics_authority_false",
        "lane_metrics_decision_parity",
        "lane_metrics_rederivable",
        "rust_repeat_stable",
    ):
        if type(fixture[key]) is not bool:
            _fail(f"fixture {key} is not a boolean")
    for key in (
        "candidate_denominator",
        "cpp_generated_count",
        "cpp_typed_failure_count",
        "ligand_atom_count",
        "persistent_cpp_context_count",
        "persistent_rust_context_count",
        "receptor_atom_count",
        "rust_generated_count",
        "rust_typed_failure_count",
        "score_term_count",
    ):
        scalar = fixture[key]
        if type(scalar) is not int or scalar < 0:
            _fail(f"fixture {key} is not an unsigned integer")
    if type(fixture["fixture_id"]) is not str:
        _fail("fixture fixture_id is not a string")
    cpp_evidence = _require_backend_rederivable_evidence(
        fixture["cpp_rederivable_evidence"],
        projection_sha256=str(fixture["cpp_projection_sha256"]),
        projection_decision_sha256=str(fixture["cpp_decision_sha256"]),
        label="C++",
    )
    rust_evidence = _require_backend_rederivable_evidence(
        fixture["rust_rederivable_evidence"],
        projection_sha256=str(fixture["rust_projection_sha256"]),
        projection_decision_sha256=str(fixture["rust_decision_sha256"]),
        label="Rust",
    )
    cpp_lane = cpp_evidence["validated_lane_metrics"]
    rust_lane = rust_evidence["validated_lane_metrics"]
    assert isinstance(cpp_lane, dict)
    assert isinstance(rust_lane, dict)
    if (
        cpp_lane["reference"]["receipt_sha256"]
        != fixture["lane_metrics_reference_sha256"]
        or rust_lane["reference"]["receipt_sha256"]
        != fixture["lane_metrics_reference_sha256"]
        or cpp_lane["decision_sha256"] != fixture["cpp_lane_metrics_decision_sha256"]
        or rust_lane["decision_sha256"] != fixture["rust_lane_metrics_decision_sha256"]
        or cpp_lane["receipt_sha256"] != fixture["cpp_lane_metrics_receipt_sha256"]
        or rust_lane["receipt_sha256"] != fixture["rust_lane_metrics_receipt_sha256"]
    ):
        _fail("fixture lane-metrics identities cross-wire the persisted full evidence")
    numeric = _require_ordered_keys(
        fixture["numeric_parity"],
        (
            "compared_f64_count",
            "first_violation_index",
            "maximum_absolute_difference",
            "maximum_scaled_difference",
            "tolerance_violation_count",
        ),
        label="numeric parity",
    )
    cpp_samples = fixture["cpp_sample_nanoseconds"]
    rust_samples = fixture["rust_sample_nanoseconds"]
    cpp_median = fixture["cpp_median_nanoseconds"]
    rust_median = fixture["rust_median_nanoseconds"]
    if (
        type(cpp_samples) is not list
        or type(rust_samples) is not list
        or len(cpp_samples) != 25
        or len(rust_samples) != 25
        or any(type(item) is not int or item < 1 for item in cpp_samples + rust_samples)
        or type(cpp_median) is not int
        or type(rust_median) is not int
        or cpp_median != _median(cpp_samples)
        or rust_median != _median(rust_samples)
    ):
        _fail("fixture timing samples or medians are invalid")
    assert isinstance(cpp_samples, list)
    assert isinstance(rust_samples, list)
    assert type(cpp_median) is int
    assert type(rust_median) is int
    ratio = fixture["rust_to_cpp_median_ratio"]
    maximum_absolute = numeric["maximum_absolute_difference"]
    maximum_scaled = numeric["maximum_scaled_difference"]
    if (
        type(ratio) not in (int, float)
        or type(maximum_absolute) not in (int, float)
        or type(maximum_scaled) not in (int, float)
    ):
        _fail("fixture numeric evidence is non-finite or not rederivable")
    assert isinstance(ratio, (int, float))
    assert isinstance(maximum_absolute, (int, float))
    assert isinstance(maximum_scaled, (int, float))
    if (
        not math.isfinite(ratio)
        or not math.isfinite(maximum_absolute)
        or not math.isfinite(maximum_scaled)
        or ratio <= 0
        or maximum_absolute < 0
        or maximum_scaled < 0
        or maximum_scaled > 2.0
        or ratio != rust_median / cpp_median
        or (maximum_absolute == 0.0) is not (maximum_scaled == 0.0)
    ):
        _fail("fixture numeric evidence is non-finite or not rederivable")
    violations = numeric["tolerance_violation_count"]
    first_violation = numeric["first_violation_index"]
    if (
        type(numeric["compared_f64_count"]) is not int
        or numeric["compared_f64_count"] != 28544
        or type(violations) is not int
        or violations < 0
        or (violations == 0 and first_violation is not None)
        or (
            violations > 0
            and (type(first_violation) is not int or not 0 <= first_violation < 28544)
        )
    ):
        _fail("fixture numeric parity counts are invalid")
    decision_parity = fixture["cpp_decision_sha256"] == fixture["rust_decision_sha256"]
    lane_metrics_decision_parity = (
        fixture["cpp_lane_metrics_decision_sha256"]
        == fixture["rust_lane_metrics_decision_sha256"]
    )
    expected_gate = bool(
        fixture["authority_false"] is True
        and fixture["candidate_denominator"] == 64
        and fixture["cpp_repeat_stable"] is True
        and fixture["rust_repeat_stable"] is True
        and fixture["decision_parity"] is decision_parity is True
        and fixture["lane_metrics_authority_false"] is True
        and fixture["lane_metrics_decision_parity"]
        is lane_metrics_decision_parity
        is True
        and fixture["lane_metrics_rederivable"] is True
        and fixture["fixture_id"] == expected_id
        and fixture["fixture_payload_sha256"] == expected["fixture_payload_sha256"]
        and fixture["cpp_generated_count"] == expected["generated_count"]
        and fixture["rust_generated_count"] == expected["generated_count"]
        and fixture["cpp_typed_failure_count"] == expected["typed_failure_count"]
        and fixture["rust_typed_failure_count"] == expected["typed_failure_count"]
        and fixture["cpp_generated_count"] + fixture["cpp_typed_failure_count"] == 64
        and fixture["rust_generated_count"] + fixture["rust_typed_failure_count"] == 64
        and fixture["ligand_atom_count"] == 12
        and fixture["receptor_atom_count"] == 12
        and fixture["score_term_count"] == 8
        and fixture["persistent_cpp_context_count"] == 1
        and fixture["persistent_rust_context_count"] == 1
        and violations == 0
        and ratio <= 1.25
    )
    cpp_values = cpp_evidence["numeric_values"]
    rust_values = rust_evidence["numeric_values"]
    assert isinstance(cpp_values, list)
    assert isinstance(rust_values, list)
    if len(cpp_values) != len(rust_values):
        _fail("fixture numeric projections have different denominators")
    recomputed_maximum_absolute = 0.0
    recomputed_maximum_scaled = 0.0
    recomputed_violations = 0
    recomputed_first: int | None = None
    for index, (left, right) in enumerate(zip(cpp_values, rust_values)):
        difference = abs(left - right)
        scale = max(abs(left), abs(right))
        allowed = 1.0e-11 + 4.0e-12 * scale
        scaled = difference if scale == 0.0 else difference / scale
        recomputed_maximum_absolute = max(recomputed_maximum_absolute, difference)
        recomputed_maximum_scaled = max(recomputed_maximum_scaled, scaled)
        if difference > allowed:
            recomputed_violations += 1
            if recomputed_first is None:
                recomputed_first = index
    if (
        numeric["compared_f64_count"] != len(cpp_values)
        or numeric["tolerance_violation_count"] != recomputed_violations
        or numeric["first_violation_index"] != recomputed_first
        or numeric["maximum_absolute_difference"] != recomputed_maximum_absolute
        or numeric["maximum_scaled_difference"] != recomputed_maximum_scaled
    ):
        _fail("fixture numeric parity does not rederive from complete projections")
    if fixture["gate_passed"] is not expected_gate:
        _fail("fixture gate does not rederive from complete evidence")
    return fixture


def _qualified_host(
    host: dict[str, object], *, expected_source_commit_oid: str
) -> bool:
    return bool(
        host["boost_disabled"] is True
        and host["cpu_model"] == "AMD Ryzen 9 5900X 12-Core Processor"
        and host["measurement_cpu_available"] is True
        and host["process_task_count"] == 1
        and host["source_commit_oid"] == expected_source_commit_oid
    )


def _expected_preflight_blockers(host: dict[str, object]) -> set[str]:
    expected: set[str] = set()
    if host["source_commit_oid"] is None:
        expected.add("source_checkout_not_exact_main")
    if host["cpu_model"] is None:
        expected.add("cpu_model_not_qualified")
    if host["boost_disabled"] is None:
        expected.add("boost_state_unavailable")
    elif host["boost_disabled"] is False:
        expected.add("boost_not_disabled")
    if host["measurement_cpu_available"] is False:
        expected.add("measurement_cpu_unavailable")
    if host["process_task_count"] is None:
        expected.add("process_task_count_unavailable")
    elif host["process_task_count"] != 1:
        expected.add("process_task_count_not_one")
    return expected


def _blocked_state_rederives(
    blockers: list[str],
    execution: dict[str, object],
    host: dict[str, object],
    *,
    expected_source_commit_oid: str,
) -> bool:
    observed = set(blockers)
    expected_preflight = _expected_preflight_blockers(host)
    measurement_started = execution["measurement_started"]
    if expected_preflight:
        if measurement_started is not False:
            return False
        allowed = [expected_preflight]
        if host["measurement_cpu_available"] is False:
            allowed.append(expected_preflight | {"affinity_unavailable"})
        return observed in allowed and observed <= PREFLIGHT_BLOCKERS
    if not _qualified_host(host, expected_source_commit_oid=expected_source_commit_oid):
        return False
    if measurement_started is False:
        return len(observed) == 1 and observed <= POST_PIN_BLOCKERS
    if measurement_started is True:
        mutually_exclusive = {
            "native_measurement_failed",
            "native_measurement_report_contract_failed",
        }
        return (
            bool(observed)
            and observed <= MEASUREMENT_BLOCKERS
            and not mutually_exclusive <= observed
        )
    return False


def require_artifact_bytes(
    raw: bytes,
    *,
    attempt_raw: bytes,
    attempt: dict[str, object],
    attempt_receipt: str,
    activation_sha256: str,
    expected_source_commit_oid: str,
    output_path_sha256: str,
) -> tuple[dict[str, object], str]:
    expected_source_commit_oid = _require_commit_oid(
        expected_source_commit_oid, label="expected v7 build commit"
    )
    artifact, receipt = _split_envelope(
        raw,
        domain=ARTIFACT_DOMAIN,
        maximum_bytes=MAX_ARTIFACT_BYTES,
        label="qualification artifact",
    )
    _require_ordered_keys(artifact, ARTIFACT_KEYS, label="qualification artifact")
    _require_false_map(
        artifact["authority"], FALSE_AUTHORITY_KEYS, label="artifact authority"
    )
    _require_false_map(
        artifact["restrictions"],
        FALSE_RESTRICTION_KEYS,
        label="artifact restrictions",
    )
    blockers = _require_blockers(artifact["blockers"])
    execution = _require_ordered_keys(
        artifact["execution"],
        (
            "execution_attested",
            "measurement_started",
            "offline_replay_only",
            "recorded_decision",
            "recorded_gate_passed",
            "recorded_numeric_gate_passed",
        ),
        label="artifact execution",
    )
    host = _require_ordered_keys(
        artifact["host"],
        (
            "boost_disabled",
            "cpu_model",
            "measurement_cpu_available",
            "measurement_cpu_ordinal",
            "process_task_count",
            "source_commit_oid",
        ),
        label="artifact host",
    )
    if (
        artifact["schema_id"] != ARTIFACT_SCHEMA_ID
        or artifact["status"] != "terminal_measurement_evidence"
        or artifact["profile_id"] != PROFILE_ID
        or artifact["profile_sha256"] != PROFILE_SHA256
        or artifact["activation_sha256"] != activation_sha256
        or artifact["attempt_ledger_raw_sha256"] != _sha256(attempt_raw)
        or artifact["attempt_receipt_sha256"] != attempt_receipt
        or artifact["build_configuration_sha256"] != BUILD_CONFIGURATION_SHA256
        or artifact["build_configuration_sha256"]
        != attempt["build_configuration_sha256"]
        or artifact["run_nonce"] != attempt["run_nonce"]
        or artifact["output_path_sha256"] != output_path_sha256
        or artifact["output_path_sha256"] != attempt["output_path_sha256"]
        or artifact["qualification_authority"] is not False
        or execution["execution_attested"] is not False
        or execution["offline_replay_only"] is not True
        or type(host["measurement_cpu_ordinal"]) is not int
        or host["measurement_cpu_ordinal"] != 2
        or type(host["measurement_cpu_available"]) is not bool
        or (
            host["boost_disabled"] is not None
            and type(host["boost_disabled"]) is not bool
        )
        or (
            host["cpu_model"] is not None
            and host["cpu_model"] != "AMD Ryzen 9 5900X 12-Core Processor"
        )
        or (
            host["process_task_count"] is not None
            and (
                type(host["process_task_count"]) is not int
                or host["process_task_count"] < 1
            )
        )
        or (
            host["source_commit_oid"] is not None
            and (
                type(host["source_commit_oid"]) is not str
                or re.fullmatch(r"[0-9a-f]{40}", host["source_commit_oid"]) is None
                or host["source_commit_oid"] != expected_source_commit_oid
            )
        )
    ):
        _fail("qualification artifact identity or authority changed")
    fixtures = artifact["fixtures"]
    if type(fixtures) is not list:
        _fail("qualification artifact fixtures are not a list")
    if fixtures:
        if not _qualified_host(
            host, expected_source_commit_oid=expected_source_commit_oid
        ):
            _fail("measured qualification artifact host is not exactly qualified")
        if len(fixtures) != 2:
            _fail("qualification artifact fixture denominator changed")
        verified = [
            _require_fixture(fixtures[index], expected_id=fixture_id)
            for index, fixture_id in enumerate(EXPECTED_FIXTURES)
        ]
        recorded_gate = all(row["gate_passed"] is True for row in verified)
        numeric_gate = True
        for row in verified:
            numeric_parity = row["numeric_parity"]
            assert isinstance(numeric_parity, dict)
            if numeric_parity["tolerance_violation_count"] != 0:
                numeric_gate = False
        expected_decision = "PASS" if recorded_gate else "NO_GO"
        expected_blockers = (
            [] if recorded_gate else ["native_qualification_gate_failed"]
        )
        if (
            execution["measurement_started"] is not True
            or execution["recorded_gate_passed"] is not recorded_gate
            or execution["recorded_numeric_gate_passed"] is not numeric_gate
            or execution["recorded_decision"] != expected_decision
            or blockers != expected_blockers
        ):
            _fail("qualification artifact decision does not rederive")
    elif (
        execution["recorded_decision"] != "BLOCKED"
        or execution["recorded_gate_passed"] is not None
        or execution["recorded_numeric_gate_passed"] is not None
        or not _blocked_state_rederives(
            blockers,
            execution,
            host,
            expected_source_commit_oid=expected_source_commit_oid,
        )
    ):
        _fail("blocked qualification artifact state does not rederive")
    return artifact, receipt


def require_terminal_bytes(
    raw: bytes,
    *,
    attempt_raw: bytes,
    attempt: dict[str, object],
    attempt_receipt: str,
    artifact_raw: bytes,
    artifact: dict[str, object],
    artifact_receipt: str,
    activation_sha256: str,
    output_path_sha256: str,
) -> dict[str, object]:
    terminal, _ = _split_envelope(
        raw,
        domain=TERMINAL_DOMAIN,
        maximum_bytes=MAX_STATE_BYTES,
        label="terminal state",
    )
    _require_ordered_keys(terminal, TERMINAL_KEYS, label="terminal state")
    _require_false_map(
        terminal["authority"], FALSE_AUTHORITY_KEYS, label="terminal authority"
    )
    _require_false_map(
        terminal["restrictions"],
        FALSE_RESTRICTION_KEYS,
        label="terminal restrictions",
    )
    blockers = _require_blockers(terminal["blockers"])
    execution = artifact["execution"]
    assert isinstance(execution, dict)
    if (
        terminal["schema_id"] != TERMINAL_SCHEMA_ID
        or terminal["status"] != "terminal_recorded"
        or terminal["profile_id"] != PROFILE_ID
        or terminal["profile_sha256"] != PROFILE_SHA256
        or terminal["activation_sha256"] != activation_sha256
        or terminal["attempt_ledger_raw_sha256"] != _sha256(attempt_raw)
        or terminal["attempt_receipt_sha256"] != attempt_receipt
        or terminal["build_configuration_sha256"] != BUILD_CONFIGURATION_SHA256
        or terminal["build_configuration_sha256"]
        != attempt["build_configuration_sha256"]
        or terminal["build_configuration_sha256"]
        != artifact["build_configuration_sha256"]
        or terminal["artifact_raw_sha256"] != _sha256(artifact_raw)
        or terminal["artifact_byte_count"] != len(artifact_raw)
        or terminal["artifact_receipt_sha256"] != artifact_receipt
        or terminal["artifact_persisted"] is not True
        or terminal["output_path_sha256"] != output_path_sha256
        or terminal["output_path_sha256"] != attempt["output_path_sha256"]
        or terminal["run_nonce"] != attempt["run_nonce"]
        or terminal["recorded_decision"] != execution["recorded_decision"]
        or terminal["recorded_gate_passed"] is not execution["recorded_gate_passed"]
        or blockers != artifact["blockers"]
        or terminal["decision_returned_only_after_terminal_persistence"] is not True
        or terminal["execution_attested"] is not False
        or terminal["execution_consumed"] is not True
        or terminal["qualification_authority"] is not False
    ):
        _fail("terminal state does not rederive from attempt and artifact")
    return terminal


def require_persisted_evidence_bytes(
    *,
    artifact_raw: bytes,
    attempt_raw: bytes,
    expected_source_commit_oid: str,
    terminal_raw: bytes,
    output_path_sha256: str,
    profile_raw: bytes,
) -> dict[str, object]:
    if _sha256(profile_raw) != PROFILE_SHA256:
        _fail("v7 profile identity changed before evidence verification")
    activation_sha256 = _domain_sha256(ACTIVATION_DOMAIN, profile_raw)
    attempt, attempt_receipt = require_attempt_bytes(
        attempt_raw,
        activation_sha256=activation_sha256,
        output_path_sha256=output_path_sha256,
    )
    artifact, artifact_receipt = require_artifact_bytes(
        artifact_raw,
        attempt_raw=attempt_raw,
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        activation_sha256=activation_sha256,
        expected_source_commit_oid=expected_source_commit_oid,
        output_path_sha256=output_path_sha256,
    )
    terminal = require_terminal_bytes(
        terminal_raw,
        attempt_raw=attempt_raw,
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        artifact_raw=artifact_raw,
        artifact=artifact,
        artifact_receipt=artifact_receipt,
        activation_sha256=activation_sha256,
        output_path_sha256=output_path_sha256,
    )
    return {
        "artifact": artifact,
        "attempt": attempt,
        "terminal": terminal,
        "artifact_sha256": _sha256(artifact_raw),
        "source_commit_oid": expected_source_commit_oid,
        "terminal_sha256": _sha256(terminal_raw),
    }


def _git_bytes(repo_root: Path, arguments: list[str], *, label: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", *arguments],
            cwd=repo_root,
            check=False,
            capture_output=True,
            env={
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": os.environ.get("PATH", ""),
            },
        )
    except OSError as exc:
        raise NativeFixed64CPUV7EvidenceError(
            f"{label} Git evidence is unavailable"
        ) from exc
    if completed.returncode != 0 or completed.stderr:
        _fail(f"{label} Git evidence failed closed")
    return completed.stdout


def _exact_checkout_commit(repo_root: Path) -> str:
    try:
        if not repo_root.is_absolute() or repo_root.resolve(strict=True) != repo_root:
            _fail("evidence repository root is not exact")
    except OSError as exc:
        raise NativeFixed64CPUV7EvidenceError(
            "evidence repository root is unavailable"
        ) from exc
    reported_root_raw = _git_bytes(
        repo_root,
        ["rev-parse", "--show-toplevel"],
        label="repository root",
    )
    try:
        reported_root = Path(reported_root_raw.decode("utf-8").removesuffix("\n"))
    except UnicodeError as exc:
        raise NativeFixed64CPUV7EvidenceError(
            "repository root Git evidence is not UTF-8"
        ) from exc
    if reported_root != repo_root:
        _fail("evidence repository root differs from Git")
    status = _git_bytes(
        repo_root,
        ["status", "--porcelain=v1", "--untracked-files=normal"],
        label="repository status",
    )
    if status:
        _fail("evidence repository checkout is not clean")
    oid_raw = _git_bytes(
        repo_root,
        ["rev-parse", "--verify", "HEAD"],
        label="repository commit",
    )
    try:
        oid = oid_raw.decode("ascii").removesuffix("\n")
    except UnicodeError as exc:
        raise NativeFixed64CPUV7EvidenceError(
            "repository commit Git evidence is not ASCII"
        ) from exc
    oid = _require_commit_oid(oid, label="evidence repository HEAD")
    critical_paths = (
        PROFILE_RELATIVE_PATH,
        SOURCE_MANIFEST_RELATIVE_PATH,
        Path("tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py"),
        Path("tools/verify_engine_v2_native_fixed64_cpu_v7_evidence.py"),
    )
    for relative in critical_paths:
        try:
            observed = (repo_root / relative).read_bytes()
        except OSError as exc:
            raise NativeFixed64CPUV7EvidenceError(
                f"critical evidence source is unavailable: {relative.as_posix()}"
            ) from exc
        committed = _git_bytes(
            repo_root,
            ["cat-file", "blob", f"{oid}:{relative.as_posix()}"],
            label=f"committed evidence source {relative.as_posix()}",
        )
        if observed != committed:
            _fail(f"critical evidence source differs from HEAD: {relative.as_posix()}")
    return oid


def _read_owner_file(path: Path, *, maximum: int, label: str) -> bytes:
    if not path.is_absolute():
        _fail(f"{label} path is not absolute")
    parent_descriptor: int | None = None
    descriptor: int | None = None
    try:
        unresolved = path.absolute()
        resolved_parent = path.parent.resolve(strict=True)
        if unresolved.parent != resolved_parent:
            _fail(f"{label} parent traverses a symlink")
        parent_metadata = resolved_parent.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(parent_metadata.st_mode)
            or parent_metadata.st_uid != os.geteuid()
            or parent_metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            _fail(f"{label} parent is not owner controlled")
        parent_descriptor = os.open(
            resolved_parent,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        bound_parent = os.fstat(parent_descriptor)
        if (bound_parent.st_dev, bound_parent.st_ino) != (
            parent_metadata.st_dev,
            parent_metadata.st_ino,
        ):
            _fail(f"{label} parent changed during descriptor binding")
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        if parent_descriptor is not None:
            os.close(parent_descriptor)
        raise NativeFixed64CPUV7EvidenceError(
            f"{label} cannot be opened safely"
        ) from exc
    try:
        assert descriptor is not None
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != os.geteuid()
            or before.st_nlink != 1
            or not 1 <= before.st_size <= maximum
        ):
            _fail(f"{label} is not an owner-only bounded file")
        chunks: list[bytes] = []
        observed = 0
        while observed <= maximum:
            chunk = os.read(descriptor, min(1 << 20, maximum + 1 - observed))
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        if (
            observed != before.st_size
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_mode != after.st_mode
            or before.st_uid != after.st_uid
            or before.st_nlink != after.st_nlink
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            _fail(f"{label} changed while read")
        return b"".join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def _require_state_paths(attempt_path: Path, terminal_path: Path) -> None:
    if attempt_path.name != "attempt.json" or terminal_path.name != "terminal.json":
        _fail("v7 state filenames changed")
    if attempt_path.parent != terminal_path.parent:
        _fail("attempt and terminal are not in one profile state directory")
    expected_home = Path(pwd.getpwuid(os.geteuid()).pw_dir)
    expected_parent = (
        expected_home
        / ".betelgeuze-engine-v2"
        / "native-fixed64-qualification"
        / PROFILE_SHA256
    )
    if attempt_path.parent != expected_parent:
        _fail("v7 state directory is not account/profile scoped")
    for path in (
        expected_home / ".betelgeuze-engine-v2",
        expected_home / ".betelgeuze-engine-v2" / "native-fixed64-qualification",
        expected_parent,
    ):
        try:
            metadata = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise NativeFixed64CPUV7EvidenceError(
                "v7 state directory chain is unavailable"
            ) from exc
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            _fail("v7 state directory chain is not owner-only and no-follow")


def verify_persisted_evidence(
    *,
    artifact_path: Path,
    attempt_path: Path,
    terminal_path: Path,
    repo_root: Path,
) -> dict[str, object]:
    artifact_path = artifact_path.absolute()
    attempt_path = attempt_path.absolute()
    terminal_path = terminal_path.absolute()
    expected_source_commit_oid = _exact_checkout_commit(repo_root)
    _require_state_paths(attempt_path, terminal_path)
    artifact_raw = _read_owner_file(
        artifact_path, maximum=MAX_ARTIFACT_BYTES, label="qualification artifact"
    )
    attempt_raw = _read_owner_file(
        attempt_path, maximum=MAX_STATE_BYTES, label="attempt ledger"
    )
    terminal_raw = _read_owner_file(
        terminal_path, maximum=MAX_STATE_BYTES, label="terminal state"
    )
    profile_raw = (repo_root / PROFILE_RELATIVE_PATH).read_bytes()
    output_path_sha256 = _sha256(os.fsencode(str(artifact_path)))
    return require_persisted_evidence_bytes(
        artifact_raw=artifact_raw,
        attempt_raw=attempt_raw,
        expected_source_commit_oid=expected_source_commit_oid,
        terminal_raw=terminal_raw,
        output_path_sha256=output_path_sha256,
        profile_raw=profile_raw,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--terminal", type=Path, required=True)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    evidence = verify_persisted_evidence(
        artifact_path=arguments.artifact,
        attempt_path=arguments.attempt,
        terminal_path=arguments.terminal,
        repo_root=arguments.repo_root.resolve(),
    )
    terminal = evidence["terminal"]
    assert isinstance(terminal, dict)
    print(
        json.dumps(
            {
                "artifact_sha256": evidence["artifact_sha256"],
                "execution_consumed": True,
                "profile_id": PROFILE_ID,
                "profile_sha256": PROFILE_SHA256,
                "qualification_authority": False,
                "recorded_decision": terminal["recorded_decision"],
                "source_commit_oid": evidence["source_commit_oid"],
                "structural_integrity_verified": True,
                "terminal_sha256": evidence["terminal_sha256"],
            },
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
