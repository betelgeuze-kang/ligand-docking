from __future__ import annotations

import copy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_profile_v7 import (
    BUILD_CONFIGURATION_SHA256,
    FALSE_AUTHORITY_KEYS,
    FALSE_RESTRICTION_KEYS,
    PROFILE_ID,
    PROFILE_SHA256,
)
from tools.verify_engine_v2_native_fixed64_cpu_v7_evidence import (
    ACTIVATION_DOMAIN,
    ARTIFACT_DOMAIN,
    ARTIFACT_SCHEMA_ID,
    ATTEMPT_DOMAIN,
    ATTEMPT_SCHEMA_ID,
    EXPECTED_FIXTURES,
    NativeFixed64CPUV7EvidenceError,
    TERMINAL_DOMAIN,
    TERMINAL_SCHEMA_ID,
    _exact_checkout_commit,
    require_artifact_bytes,
    require_attempt_bytes,
    require_persisted_evidence_bytes,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_RAW = (
    _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v7.json"
).read_bytes()
_VERIFIER = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_v7_evidence.py"
_OUTPUT_PATH_SHA256 = "a1" * 32
_SOURCE_COMMIT_OID = "f6" * 20


def _domain(domain: bytes, raw: bytes) -> str:
    return hashlib.sha256(domain + raw).hexdigest()


def _envelope(projection: dict[str, object], domain: bytes) -> bytes:
    raw = json.dumps(
        projection,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return (
        b'{"projection":'
        + raw
        + b',"receipt_sha256":"'
        + _domain(domain, raw).encode("ascii")
        + b'"}\n'
    )


def _false_authority() -> dict[str, bool]:
    return {key: False for key in sorted(FALSE_AUTHORITY_KEYS)}


def _false_restrictions() -> dict[str, bool]:
    return {key: False for key in sorted(FALSE_RESTRICTION_KEYS)}


def _attempt() -> dict[str, object]:
    return {
        "activation_sha256": _domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
        "attempt_ordinal": 1,
        "authority": _false_authority(),
        "build_configuration_sha256": BUILD_CONFIGURATION_SHA256,
        "measurement_started": False,
        "output_path_sha256": _OUTPUT_PATH_SHA256,
        "process_id": 1234,
        "process_start_ticks": 5678,
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "restrictions": _false_restrictions(),
        "run_nonce": "b2" * 32,
        "schema_id": ATTEMPT_SCHEMA_ID,
    }


@lru_cache(maxsize=1)
def _real_fixtures() -> dict[str, dict[str, object]]:
    completed = subprocess.run(
        [
            "cargo",
            "test",
            "--manifest-path",
            "rust/Cargo.toml",
            "-p",
            "betelgeuze-runtime",
            "--lib",
            "--locked",
            "qualification_v7::tests::fixture_artifact_persists_each_backend_failure_denominator",
            "--",
            "--exact",
            "--nocapture",
        ],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "BETELGEUZE_V7_EMIT_TEST_FIXTURE": "1",
            "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD": "1",
            "BETELGEUZE_V7_SOURCE_ROOT": str(_ROOT),
        },
    )
    prefix = "BETELGEUZE_V7_TEST_FIXTURE="
    fixtures = {
        value["fixture_id"]: value
        for value in (
            json.loads(line.removeprefix(prefix))
            for line in completed.stdout.splitlines()
            if line.startswith(prefix)
        )
    }
    assert set(fixtures) == set(EXPECTED_FIXTURES)
    for fixture in fixtures.values():
        fixture["cpp_sample_nanoseconds"] = list(range(100, 125))
        fixture["rust_sample_nanoseconds"] = list(range(100, 125))
        fixture["cpp_median_nanoseconds"] = 112
        fixture["rust_median_nanoseconds"] = 112
        fixture["rust_to_cpp_median_ratio"] = 1.0
        fixture["gate_passed"] = True
    return fixtures


def _fixture(fixture_id: str) -> dict[str, object]:
    return copy.deepcopy(_real_fixtures()[fixture_id])


def _artifact(
    attempt_raw: bytes,
    attempt_receipt: str,
    *,
    passed: bool,
) -> dict[str, object]:
    fixtures = [_fixture(value) for value in EXPECTED_FIXTURES] if passed else []
    blockers = [] if passed else ["source_checkout_not_exact_main"]
    return {
        "activation_sha256": _domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
        "attempt_ledger_raw_sha256": hashlib.sha256(attempt_raw).hexdigest(),
        "attempt_receipt_sha256": attempt_receipt,
        "authority": _false_authority(),
        "blockers": blockers,
        "build_configuration_sha256": BUILD_CONFIGURATION_SHA256,
        "execution": {
            "execution_attested": False,
            "measurement_started": passed,
            "offline_replay_only": True,
            "recorded_decision": "PASS" if passed else "BLOCKED",
            "recorded_gate_passed": True if passed else None,
            "recorded_numeric_gate_passed": True if passed else None,
        },
        "fixtures": fixtures,
        "host": {
            "boost_disabled": True,
            "cpu_model": "AMD Ryzen 9 5900X 12-Core Processor",
            "measurement_cpu_available": True,
            "measurement_cpu_ordinal": 2,
            "process_task_count": 1,
            "source_commit_oid": _SOURCE_COMMIT_OID if passed else None,
        },
        "output_path_sha256": _OUTPUT_PATH_SHA256,
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "qualification_authority": False,
        "restrictions": _false_restrictions(),
        "run_nonce": "b2" * 32,
        "schema_id": ARTIFACT_SCHEMA_ID,
        "status": "terminal_measurement_evidence",
    }


def _terminal(
    attempt_raw: bytes,
    attempt_receipt: str,
    artifact_raw: bytes,
    artifact_receipt: str,
    *,
    passed: bool,
) -> dict[str, object]:
    return {
        "activation_sha256": _domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
        "artifact_byte_count": len(artifact_raw),
        "artifact_persisted": True,
        "artifact_raw_sha256": hashlib.sha256(artifact_raw).hexdigest(),
        "artifact_receipt_sha256": artifact_receipt,
        "attempt_ledger_raw_sha256": hashlib.sha256(attempt_raw).hexdigest(),
        "attempt_receipt_sha256": attempt_receipt,
        "authority": _false_authority(),
        "blockers": [] if passed else ["source_checkout_not_exact_main"],
        "build_configuration_sha256": BUILD_CONFIGURATION_SHA256,
        "decision_returned_only_after_terminal_persistence": True,
        "execution_attested": False,
        "execution_consumed": True,
        "output_path_sha256": _OUTPUT_PATH_SHA256,
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "qualification_authority": False,
        "recorded_decision": "PASS" if passed else "BLOCKED",
        "recorded_gate_passed": True if passed else None,
        "restrictions": _false_restrictions(),
        "run_nonce": "b2" * 32,
        "schema_id": TERMINAL_SCHEMA_ID,
        "status": "terminal_recorded",
    }


def _evidence(*, passed: bool) -> tuple[bytes, bytes, bytes]:
    attempt_projection = _attempt()
    attempt_raw = _envelope(attempt_projection, ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        attempt_projection,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    attempt_receipt = _domain(ATTEMPT_DOMAIN, attempt_projection_raw)
    artifact_projection = _artifact(
        attempt_raw,
        attempt_receipt,
        passed=passed,
    )
    artifact_raw = _envelope(artifact_projection, ARTIFACT_DOMAIN)
    artifact_projection_raw = json.dumps(
        artifact_projection,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact_receipt = _domain(ARTIFACT_DOMAIN, artifact_projection_raw)
    terminal_raw = _envelope(
        _terminal(
            attempt_raw,
            attempt_receipt,
            artifact_raw,
            artifact_receipt,
            passed=passed,
        ),
        TERMINAL_DOMAIN,
    )
    return attempt_raw, artifact_raw, terminal_raw


@pytest.mark.parametrize("passed", [False, True])
def test_complete_blocked_and_pass_evidence_rederive(passed: bool) -> None:
    attempt_raw, artifact_raw, terminal_raw = _evidence(passed=passed)
    evidence = require_persisted_evidence_bytes(
        artifact_raw=artifact_raw,
        attempt_raw=attempt_raw,
        expected_source_commit_oid=_SOURCE_COMMIT_OID,
        terminal_raw=terminal_raw,
        output_path_sha256=_OUTPUT_PATH_SHA256,
        profile_raw=_PROFILE_RAW,
    )
    terminal = evidence["terminal"]
    assert isinstance(terminal, dict)
    assert terminal["recorded_decision"] == ("PASS" if passed else "BLOCKED")
    assert terminal["qualification_authority"] is False


def test_evidence_help_resolves_sibling_chain_without_site_packages() -> None:
    completed = subprocess.run(
        [sys.executable, "-S", str(_VERIFIER), "--help"],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    assert "--artifact" in completed.stdout
    assert "--attempt" in completed.stdout
    assert "--terminal" in completed.stdout


def test_exact_checkout_commit_is_derived_from_clean_git_head(tmp_path: Path) -> None:
    critical = (
        Path("config/engine_v2_native_fixed64_cpu_profile_v7.json"),
        Path("config/engine_v2_native_fixed64_cpu_profile_v7_sources.json"),
        Path("tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py"),
        Path("tools/verify_engine_v2_native_fixed64_cpu_v7_evidence.py"),
    )
    for relative in critical:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.as_posix().encode("ascii"))
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Engine V2 Test",
            "-c",
            "user.email=engine-v2-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "freeze evidence checkout",
        ],
        cwd=tmp_path,
        check=True,
    )
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert _exact_checkout_commit(tmp_path) == expected

    (tmp_path / critical[-1]).write_bytes(b"mutated")
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match="not clean"):
        _exact_checkout_commit(tmp_path)


def _require_mutated_artifact_fails(
    artifact: dict[str, object],
    *,
    match: str,
) -> None:
    attempt_projection = _attempt()
    attempt_raw = _envelope(attempt_projection, ATTEMPT_DOMAIN)
    attempt, attempt_receipt = require_attempt_bytes(
        attempt_raw,
        activation_sha256=_domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
        output_path_sha256=_OUTPUT_PATH_SHA256,
    )
    artifact["attempt_ledger_raw_sha256"] = hashlib.sha256(attempt_raw).hexdigest()
    artifact["attempt_receipt_sha256"] = attempt_receipt
    artifact_raw = _envelope(artifact, ARTIFACT_DOMAIN)
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match=match):
        require_artifact_bytes(
            artifact_raw,
            attempt_raw=attempt_raw,
            attempt=attempt,
            attempt_receipt=attempt_receipt,
            activation_sha256=_domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            output_path_sha256=_OUTPUT_PATH_SHA256,
        )


def _require_mutated_artifact_passes(artifact: dict[str, object]) -> None:
    attempt_projection = _attempt()
    attempt_raw = _envelope(attempt_projection, ATTEMPT_DOMAIN)
    attempt, attempt_receipt = require_attempt_bytes(
        attempt_raw,
        activation_sha256=_domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
        output_path_sha256=_OUTPUT_PATH_SHA256,
    )
    artifact["attempt_ledger_raw_sha256"] = hashlib.sha256(attempt_raw).hexdigest()
    artifact["attempt_receipt_sha256"] = attempt_receipt
    artifact_raw = _envelope(artifact, ARTIFACT_DOMAIN)
    require_artifact_bytes(
        artifact_raw,
        attempt_raw=attempt_raw,
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        activation_sha256=_domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
        expected_source_commit_oid=_SOURCE_COMMIT_OID,
        output_path_sha256=_OUTPUT_PATH_SHA256,
    )


def test_attempt_ordinal_rejects_boolean_alias_for_one() -> None:
    attempt = _attempt()
    attempt["attempt_ordinal"] = True
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match="semantics changed"):
        require_attempt_bytes(
            _envelope(attempt, ATTEMPT_DOMAIN),
            activation_sha256=_domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
            output_path_sha256=_OUTPUT_PATH_SHA256,
        )


def test_attempt_rejects_other_build_configuration() -> None:
    attempt = _attempt()
    attempt["build_configuration_sha256"] = "00" * 32
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match="semantics changed"):
        require_attempt_bytes(
            _envelope(attempt, ATTEMPT_DOMAIN),
            activation_sha256=_domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
            output_path_sha256=_OUTPUT_PATH_SHA256,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("boost_disabled", False),
        ("cpu_model", None),
        ("measurement_cpu_available", False),
        ("process_task_count", 99),
        ("source_commit_oid", None),
    ),
)
def test_measured_evidence_requires_exact_qualified_host(
    field: str,
    value: object,
) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    host = artifact["host"]
    assert isinstance(host, dict)
    host[field] = value
    _require_mutated_artifact_fails(artifact, match="host is not exactly qualified")


def test_measured_evidence_rejects_other_build_commit() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    host = artifact["host"]
    assert isinstance(host, dict)
    host["source_commit_oid"] = "ab" * 20
    _require_mutated_artifact_fails(artifact, match="identity or authority")


def test_artifact_rejects_other_build_configuration() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    artifact["build_configuration_sha256"] = "00" * 32
    _require_mutated_artifact_fails(artifact, match="identity or authority")


def test_terminal_rejects_other_build_configuration() -> None:
    attempt_raw, artifact_raw, _ = _evidence(passed=True)
    attempt_projection = _attempt()
    attempt_projection_raw = json.dumps(
        attempt_projection,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact_projection = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    artifact_projection_raw = json.dumps(
        artifact_projection,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    terminal = _terminal(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        artifact_raw,
        _domain(ARTIFACT_DOMAIN, artifact_projection_raw),
        passed=True,
    )
    terminal["build_configuration_sha256"] = "00" * 32
    with pytest.raises(
        NativeFixed64CPUV7EvidenceError,
        match="terminal state does not rederive",
    ):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            terminal_raw=_envelope(terminal, TERMINAL_DOMAIN),
            output_path_sha256=_OUTPUT_PATH_SHA256,
            profile_raw=_PROFILE_RAW,
        )


def test_measured_evidence_rejects_float_measurement_cpu_ordinal() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    host = artifact["host"]
    assert isinstance(host, dict)
    host["measurement_cpu_ordinal"] = 2.0
    _require_mutated_artifact_fails(artifact, match="identity or authority")


@pytest.mark.parametrize(
    ("blocker", "measurement_started"),
    (
        ("native_qualification_gate_failed", False),
        ("native_measurement_failed", False),
        ("source_checkout_not_exact_main", True),
    ),
)
def test_blocked_evidence_rejects_impossible_blocker_and_measurement_state(
    blocker: str,
    measurement_started: bool,
) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=False,
    )
    artifact["blockers"] = [blocker]
    execution = artifact["execution"]
    assert isinstance(execution, dict)
    execution["measurement_started"] = measurement_started
    _require_mutated_artifact_fails(artifact, match="state does not rederive")


@pytest.mark.parametrize(
    ("blocker", "measurement_started"),
    (
        ("measurement_affinity_pin_failed", False),
        ("native_measurement_failed", True),
    ),
)
def test_blocked_evidence_accepts_rederivable_post_preflight_failures(
    blocker: str,
    measurement_started: bool,
) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    artifact["blockers"] = [blocker]
    artifact["fixtures"] = []
    execution = artifact["execution"]
    assert isinstance(execution, dict)
    execution["measurement_started"] = measurement_started
    execution["recorded_decision"] = "BLOCKED"
    execution["recorded_gate_passed"] = None
    execution["recorded_numeric_gate_passed"] = None
    _require_mutated_artifact_passes(artifact)


def test_blocked_evidence_accepts_post_measurement_host_drift() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    artifact["blockers"] = ["post_measurement_host_invariant_failed"]
    artifact["fixtures"] = []
    execution = artifact["execution"]
    assert isinstance(execution, dict)
    execution["measurement_started"] = True
    execution["recorded_decision"] = "BLOCKED"
    execution["recorded_gate_passed"] = None
    execution["recorded_numeric_gate_passed"] = None
    _require_mutated_artifact_passes(artifact)


def test_blocked_evidence_rejects_mutually_exclusive_measurement_failures() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    artifact["blockers"] = [
        "native_measurement_failed",
        "native_measurement_report_contract_failed",
    ]
    artifact["fixtures"] = []
    execution = artifact["execution"]
    assert isinstance(execution, dict)
    execution["measurement_started"] = True
    execution["recorded_decision"] = "BLOCKED"
    execution["recorded_gate_passed"] = None
    execution["recorded_numeric_gate_passed"] = None
    _require_mutated_artifact_fails(artifact, match="state does not rederive")


@pytest.mark.parametrize(
    "measurement_failure",
    ("native_measurement_failed", "native_measurement_report_contract_failed"),
)
def test_blocked_evidence_accepts_one_measurement_failure_plus_host_drift(
    measurement_failure: str,
) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    artifact["blockers"] = [
        measurement_failure,
        "post_measurement_host_invariant_failed",
    ]
    artifact["fixtures"] = []
    execution = artifact["execution"]
    assert isinstance(execution, dict)
    execution["measurement_started"] = True
    execution["recorded_decision"] = "BLOCKED"
    execution["recorded_gate_passed"] = None
    execution["recorded_numeric_gate_passed"] = None
    _require_mutated_artifact_passes(artifact)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("cpp_generated_count", None),
        ("rust_typed_failure_count", "0"),
        ("persistent_cpp_context_count", -1),
        ("candidate_denominator", True),
    ),
)
def test_measured_fixture_rejects_impossible_scalar_types_and_ranges(
    field: str,
    value: object,
) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    fixture[field] = value
    fixture["gate_passed"] = False
    artifact["blockers"] = ["native_qualification_gate_failed"]
    execution = artifact["execution"]
    assert isinstance(execution, dict)
    execution["recorded_decision"] = "NO_GO"
    execution["recorded_gate_passed"] = False
    _require_mutated_artifact_fails(artifact, match="unsigned integer")


def test_measured_fixture_rederives_each_backend_failure_denominator() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    fixture["rust_generated_count"] = 63
    fixture["rust_typed_failure_count"] = 1
    _require_mutated_artifact_fails(artifact, match="gate does not rederive")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lane_metrics_authority_false", False),
        ("lane_metrics_rederivable", False),
        ("rust_lane_metrics_decision_sha256", "b7" * 32),
    ],
)
def test_measured_fixture_lane_metrics_gate_rederives(
    field: str, value: object
) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    fixture[field] = value
    _require_mutated_artifact_fails(
        artifact,
        match="gate does not rederive|cross-wire the persisted full evidence",
    )


@pytest.mark.parametrize(
    "field",
    [
        "lane_metrics_reference_sha256",
        "cpp_lane_metrics_decision_sha256",
        "cpp_lane_metrics_receipt_sha256",
        "rust_lane_metrics_decision_sha256",
        "rust_lane_metrics_receipt_sha256",
    ],
)
def test_measured_fixture_rejects_unbound_lane_metrics_digest(field: str) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    fixture[field] = "0" * 64
    _require_mutated_artifact_fails(artifact, match="unbound zero digest")


def test_measured_fixture_rejects_float_numeric_parity_count() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    numeric = fixture["numeric_parity"]
    assert isinstance(numeric, dict)
    numeric["compared_f64_count"] = 28544.0
    _require_mutated_artifact_fails(artifact, match="numeric parity counts")


@pytest.mark.parametrize(
    ("maximum_absolute", "maximum_scaled"),
    ((0.0, 1.0), (1.0, 0.0)),
)
def test_measured_fixture_rejects_inconsistent_numeric_parity_maxima(
    maximum_absolute: float,
    maximum_scaled: float,
) -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    numeric = fixture["numeric_parity"]
    assert isinstance(numeric, dict)
    numeric["maximum_absolute_difference"] = maximum_absolute
    numeric["maximum_scaled_difference"] = maximum_scaled
    _require_mutated_artifact_fails(artifact, match="numeric evidence")


def test_measured_fixture_rejects_impossible_scaled_difference_bound() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(
        _attempt(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    numeric = fixture["numeric_parity"]
    assert isinstance(numeric, dict)
    numeric["maximum_absolute_difference"] = 1.0
    numeric["maximum_scaled_difference"] = 3.0
    _require_mutated_artifact_fails(artifact, match="numeric evidence")


def _first_cpp_backend_evidence(artifact: dict[str, object]) -> dict[str, object]:
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    evidence = fixture["cpp_rederivable_evidence"]
    assert isinstance(evidence, dict)
    return evidence


def test_full_evidence_rejects_scorer_term_drift_with_recomputed_artifact() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    evidence = _first_cpp_backend_evidence(artifact)
    rows = evidence["scorer_validity_rows"]
    assert isinstance(rows, list)
    scorer = rows[0]["scorer"]
    assert isinstance(scorer, dict)
    terms = scorer["weighted_terms"]
    assert isinstance(terms, list)
    terms[0] += 0.25
    _require_mutated_artifact_fails(artifact, match="not bound to numeric projection")


def test_full_evidence_rejects_validity_measurement_drift() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    evidence = _first_cpp_backend_evidence(artifact)
    rows = evidence["scorer_validity_rows"]
    assert isinstance(rows, list)
    validity = rows[0]["validity"]
    assert isinstance(validity, dict)
    measurements = validity["measurements"]
    assert isinstance(measurements, list)
    measurements[0] += 0.125
    _require_mutated_artifact_fails(artifact, match="not bound to numeric projection")


def test_full_evidence_rejects_rehashed_numeric_projection_cross_wiring() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    evidence = _first_cpp_backend_evidence(artifact)
    numeric = evidence["numeric_projection"]
    assert isinstance(numeric, dict)
    raw = bytearray.fromhex(str(numeric["f64_be_hex"]))
    term_offset = 76 * 8
    raw[term_offset + 7] ^= 1
    numeric["f64_be_hex"] = raw.hex()
    numeric["sha256"] = _domain(
        b"betelgeuze.engine_v2_native_fixed64_cpu_numeric_projection_v7\0",
        bytes(raw),
    )
    _require_mutated_artifact_fails(artifact, match="not bound to numeric projection")


def test_full_evidence_rejects_rehashed_decision_preimage_drift() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    evidence = _first_cpp_backend_evidence(artifact)
    preimage = evidence["decision_preimage"]
    assert isinstance(preimage, dict)
    raw = bytearray.fromhex(str(preimage["hex"]))
    raw[-1] ^= 1
    preimage["hex"] = raw.hex()
    preimage["sha256"] = hashlib.sha256(raw).hexdigest()
    _require_mutated_artifact_fails(
        artifact, match="decision preimage does not bind the scientific decision"
    )


def test_full_evidence_rejects_rehashed_projection_digest_stream_drift() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    evidence = _first_cpp_backend_evidence(artifact)
    stream = evidence["projection_digest_stream"]
    assert isinstance(stream, dict)
    raw = bytearray.fromhex(str(stream["hex"]))
    raw[0] ^= 1
    stream["hex"] = raw.hex()
    stream["sha256"] = _domain(
        b"betelgeuze.engine_v2_native_fixed64_cpu_projection_digest_stream_v7\0",
        bytes(raw),
    )
    _require_mutated_artifact_fails(
        artifact, match="scientific projection digest does not rederive"
    )


def test_full_evidence_rejects_projection_identity_drift() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    artifact = _artifact(
        attempt_raw,
        _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
        passed=True,
    )
    evidence = _first_cpp_backend_evidence(artifact)
    evidence["projection_sha256"] = "f1" * 32
    _require_mutated_artifact_fails(artifact, match="evidence identity changed")


def test_full_evidence_rejects_lane_rmsd_and_summary_drift() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    for mutation, match in (
        ("rmsd", "RMSD does not rederive"),
        ("summary", "lane summary"),
    ):
        artifact = _artifact(
            attempt_raw,
            _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
            passed=True,
        )
        evidence = _first_cpp_backend_evidence(artifact)
        metrics = evidence["lane_metrics"]
        assert isinstance(metrics, dict)
        if mutation == "rmsd":
            observations = metrics["observations"]
            assert isinstance(observations, list)
            observations[24]["symmetry_aware_direct_heavy_atom_rmsd_angstrom"] += 0.5
        else:
            summaries = metrics["lane_summaries"]
            assert isinstance(summaries, list)
            summaries[2]["generated_count"] -= 1
        _require_mutated_artifact_fails(artifact, match=match)


def test_full_evidence_rejects_observation_receipt_and_authority_escalation() -> None:
    attempt_raw = _envelope(_attempt(), ATTEMPT_DOMAIN)
    attempt_projection_raw = json.dumps(_attempt(), separators=(",", ":")).encode(
        "ascii"
    )
    for mutation, match in (
        ("receipt", "observation receipt"),
        ("authority", "lane authority"),
    ):
        artifact = _artifact(
            attempt_raw,
            _domain(ATTEMPT_DOMAIN, attempt_projection_raw),
            passed=True,
        )
        evidence = _first_cpp_backend_evidence(artifact)
        metrics = evidence["lane_metrics"]
        assert isinstance(metrics, dict)
        if mutation == "receipt":
            observations = metrics["observations"]
            assert isinstance(observations, list)
            observations[0]["receipt_sha256"] = "f0" * 32
        else:
            authority = metrics["authority"]
            assert isinstance(authority, dict)
            authority["scientific_claim_authorized"] = True
        _require_mutated_artifact_fails(artifact, match=match)


def test_artifact_receipt_tamper_fails_closed() -> None:
    attempt_raw, artifact_raw, terminal_raw = _evidence(passed=False)
    artifact_raw = artifact_raw.replace(b'"source_checkout', b'"source_checkouu', 1)
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match="receipt"):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            terminal_raw=terminal_raw,
            output_path_sha256=_OUTPUT_PATH_SHA256,
            profile_raw=_PROFILE_RAW,
        )


def test_attempt_cross_wiring_fails_with_recomputed_artifact_receipt() -> None:
    attempt_raw, _, _ = _evidence(passed=False)
    attempt_projection_raw = json.dumps(
        _attempt(), allow_nan=False, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    attempt_receipt = _domain(ATTEMPT_DOMAIN, attempt_projection_raw)
    artifact = _artifact(attempt_raw, attempt_receipt, passed=False)
    artifact["attempt_ledger_raw_sha256"] = "00" * 32
    artifact_raw = _envelope(artifact, ARTIFACT_DOMAIN)
    artifact_projection_raw = json.dumps(
        artifact, allow_nan=False, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    terminal_raw = _envelope(
        _terminal(
            attempt_raw,
            attempt_receipt,
            artifact_raw,
            _domain(ARTIFACT_DOMAIN, artifact_projection_raw),
            passed=False,
        ),
        TERMINAL_DOMAIN,
    )
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match="identity"):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            terminal_raw=terminal_raw,
            output_path_sha256=_OUTPUT_PATH_SHA256,
            profile_raw=_PROFILE_RAW,
        )


def test_truncated_timing_denominator_fails_closed() -> None:
    attempt_raw, _, _ = _evidence(passed=True)
    attempt_projection_raw = json.dumps(
        _attempt(), allow_nan=False, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    attempt_receipt = _domain(ATTEMPT_DOMAIN, attempt_projection_raw)
    artifact = _artifact(attempt_raw, attempt_receipt, passed=True)
    fixtures = artifact["fixtures"]
    assert isinstance(fixtures, list)
    fixture = fixtures[0]
    assert isinstance(fixture, dict)
    cpp_samples = fixture["cpp_sample_nanoseconds"]
    assert isinstance(cpp_samples, list)
    cpp_samples.pop()
    artifact_raw = _envelope(artifact, ARTIFACT_DOMAIN)
    artifact_projection_raw = json.dumps(
        artifact, allow_nan=False, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    terminal_raw = _envelope(
        _terminal(
            attempt_raw,
            attempt_receipt,
            artifact_raw,
            _domain(ARTIFACT_DOMAIN, artifact_projection_raw),
            passed=True,
        ),
        TERMINAL_DOMAIN,
    )
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match="timing samples"):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            terminal_raw=terminal_raw,
            output_path_sha256=_OUTPUT_PATH_SHA256,
            profile_raw=_PROFILE_RAW,
        )


def test_terminal_authority_escalation_fails_even_with_recomputed_receipt() -> None:
    attempt_raw, artifact_raw, _ = _evidence(passed=False)
    attempt_projection_raw = json.dumps(
        _attempt(), allow_nan=False, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    attempt_receipt = _domain(ATTEMPT_DOMAIN, attempt_projection_raw)
    artifact_projection = _artifact(attempt_raw, attempt_receipt, passed=False)
    artifact_projection_raw = json.dumps(
        artifact_projection,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    terminal = _terminal(
        attempt_raw,
        attempt_receipt,
        artifact_raw,
        _domain(ARTIFACT_DOMAIN, artifact_projection_raw),
        passed=False,
    )
    authority = terminal["authority"]
    assert isinstance(authority, dict)
    authority["qualification_authority"] = True
    terminal_raw = _envelope(terminal, TERMINAL_DOMAIN)
    with pytest.raises(NativeFixed64CPUV7EvidenceError, match="authority"):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            terminal_raw=terminal_raw,
            output_path_sha256=_OUTPUT_PATH_SHA256,
            profile_raw=_PROFILE_RAW,
        )


def test_output_path_cross_wiring_fails_closed() -> None:
    attempt_raw, artifact_raw, terminal_raw = _evidence(passed=False)
    with pytest.raises(
        NativeFixed64CPUV7EvidenceError, match="attempt ledger semantics"
    ):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            terminal_raw=terminal_raw,
            output_path_sha256="ff" * 32,
            profile_raw=_PROFILE_RAW,
        )
