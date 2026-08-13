#!/usr/bin/env python3
"""Independently verify persisted native fixed64 CPU v6 evidence."""

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
import subprocess
from typing import NoReturn

if __package__:
    from .verify_engine_v2_native_fixed64_cpu_profile_v6 import (
        FALSE_AUTHORITY_KEYS,
        FALSE_RESTRICTION_KEYS,
        PROFILE_ID,
        PROFILE_RELATIVE_PATH,
        PROFILE_SHA256,
        SOURCE_MANIFEST_RELATIVE_PATH,
    )
else:
    from verify_engine_v2_native_fixed64_cpu_profile_v6 import (
        FALSE_AUTHORITY_KEYS,
        FALSE_RESTRICTION_KEYS,
        PROFILE_ID,
        PROFILE_RELATIVE_PATH,
        PROFILE_SHA256,
        SOURCE_MANIFEST_RELATIVE_PATH,
    )


ATTEMPT_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_cpu_attempt/6.0.0"
ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_cpu_qualification_artifact/6.0.0"
)
TERMINAL_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_cpu_terminal/6.0.0"
ACTIVATION_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_activation_v6\0"
ATTEMPT_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_attempt_v6\0"
ARTIFACT_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_artifact_v6\0"
TERMINAL_DOMAIN = b"betelgeuze.engine_v2_native_fixed64_cpu_terminal_v6\0"
MAX_STATE_BYTES = 64 * 1024
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
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


class NativeFixed64CPUV6EvidenceError(ValueError):
    """Persisted native fixed64 CPU v6 evidence failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeFixed64CPUV6EvidenceError(message)


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
    if raw != prefix + projection_raw + b',"receipt_sha256":"' + match.group(1) + b'"}\n':
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
        raise NativeFixed64CPUV6EvidenceError(
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


def _require_fixture(value: object, *, expected_id: str) -> dict[str, object]:
    fixture_keys = (
        "authority_false",
        "candidate_denominator",
        "cpp_decision_sha256",
        "cpp_generated_count",
        "cpp_median_nanoseconds",
        "cpp_projection_sha256",
        "cpp_repeat_stable",
        "cpp_sample_nanoseconds",
        "cpp_typed_failure_count",
        "decision_parity",
        "fixture_id",
        "fixture_payload_sha256",
        "gate_passed",
        "ligand_atom_count",
        "numeric_parity",
        "persistent_cpp_context_count",
        "persistent_rust_context_count",
        "receptor_atom_count",
        "rust_decision_sha256",
        "rust_generated_count",
        "rust_median_nanoseconds",
        "rust_projection_sha256",
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
        "cpp_projection_sha256",
        "rust_decision_sha256",
        "rust_projection_sha256",
    ):
        _require_digest(fixture[key], label=f"fixture {key}")
    for key in (
        "authority_false",
        "cpp_repeat_stable",
        "decision_parity",
        "gate_passed",
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
            and (
                type(first_violation) is not int
                or not 0 <= first_violation < 28544
            )
        )
    ):
        _fail("fixture numeric parity counts are invalid")
    decision_parity = fixture["cpp_decision_sha256"] == fixture["rust_decision_sha256"]
    expected_gate = bool(
        fixture["authority_false"] is True
        and fixture["candidate_denominator"] == 64
        and fixture["cpp_repeat_stable"] is True
        and fixture["rust_repeat_stable"] is True
        and fixture["decision_parity"] is decision_parity is True
        and fixture["fixture_id"] == expected_id
        and fixture["fixture_payload_sha256"]
        == expected["fixture_payload_sha256"]
        and fixture["cpp_generated_count"] == expected["generated_count"]
        and fixture["rust_generated_count"] == expected["generated_count"]
        and fixture["cpp_typed_failure_count"] == expected["typed_failure_count"]
        and fixture["rust_typed_failure_count"] == expected["typed_failure_count"]
        and fixture["cpp_generated_count"]
        + fixture["cpp_typed_failure_count"]
        == 64
        and fixture["rust_generated_count"]
        + fixture["rust_typed_failure_count"]
        == 64
        and fixture["ligand_atom_count"] == 12
        and fixture["receptor_atom_count"] == 12
        and fixture["score_term_count"] == 8
        and fixture["persistent_cpp_context_count"] == 1
        and fixture["persistent_rust_context_count"] == 1
        and violations == 0
        and ratio <= 1.25
    )
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
    if not _qualified_host(
        host, expected_source_commit_oid=expected_source_commit_oid
    ):
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
        expected_source_commit_oid, label="expected v6 build commit"
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
        or artifact["run_nonce"] != attempt["run_nonce"]
        or artifact["output_path_sha256"] != output_path_sha256
        or artifact["output_path_sha256"] != attempt["output_path_sha256"]
        or artifact["qualification_authority"] is not False
        or execution["execution_attested"] is not False
        or execution["offline_replay_only"] is not True
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
                or re.fullmatch(r"[0-9a-f]{40}", host["source_commit_oid"])
                is None
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
        expected_blockers = [] if recorded_gate else ["native_qualification_gate_failed"]
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
        or terminal["artifact_raw_sha256"] != _sha256(artifact_raw)
        or terminal["artifact_byte_count"] != len(artifact_raw)
        or terminal["artifact_receipt_sha256"] != artifact_receipt
        or terminal["artifact_persisted"] is not True
        or terminal["output_path_sha256"] != output_path_sha256
        or terminal["output_path_sha256"] != attempt["output_path_sha256"]
        or terminal["run_nonce"] != attempt["run_nonce"]
        or terminal["recorded_decision"] != execution["recorded_decision"]
        or terminal["recorded_gate_passed"]
        is not execution["recorded_gate_passed"]
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
        _fail("v6 profile identity changed before evidence verification")
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
        raise NativeFixed64CPUV6EvidenceError(
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
        raise NativeFixed64CPUV6EvidenceError(
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
        raise NativeFixed64CPUV6EvidenceError(
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
        raise NativeFixed64CPUV6EvidenceError(
            "repository commit Git evidence is not ASCII"
        ) from exc
    oid = _require_commit_oid(oid, label="evidence repository HEAD")
    critical_paths = (
        PROFILE_RELATIVE_PATH,
        SOURCE_MANIFEST_RELATIVE_PATH,
        Path("tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py"),
        Path("tools/verify_engine_v2_native_fixed64_cpu_v6_evidence.py"),
    )
    for relative in critical_paths:
        try:
            observed = (repo_root / relative).read_bytes()
        except OSError as exc:
            raise NativeFixed64CPUV6EvidenceError(
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
        raise NativeFixed64CPUV6EvidenceError(
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
        _fail("v6 state filenames changed")
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
        _fail("v6 state directory is not account/profile scoped")
    for path in (
        expected_home / ".betelgeuze-engine-v2",
        expected_home / ".betelgeuze-engine-v2" / "native-fixed64-qualification",
        expected_parent,
    ):
        try:
            metadata = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise NativeFixed64CPUV6EvidenceError(
                "v6 state directory chain is unavailable"
            ) from exc
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            _fail("v6 state directory chain is not owner-only and no-follow")


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
