from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_profile_v6 import (
    BUILD_CONFIGURATION_SHA256,
    FALSE_AUTHORITY_KEYS,
    FALSE_RESTRICTION_KEYS,
    PROFILE_ID,
    PROFILE_SHA256,
)
from tools.verify_engine_v2_native_fixed64_cpu_v6_evidence import (
    ACTIVATION_DOMAIN,
    ARTIFACT_DOMAIN,
    ARTIFACT_SCHEMA_ID,
    ATTEMPT_DOMAIN,
    ATTEMPT_SCHEMA_ID,
    EXPECTED_FIXTURES,
    NativeFixed64CPUV6EvidenceError,
    TERMINAL_DOMAIN,
    TERMINAL_SCHEMA_ID,
    _exact_checkout_commit,
    require_artifact_bytes,
    require_attempt_bytes,
    require_persisted_evidence_bytes,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_RAW = (
    _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v6.json"
).read_bytes()
_VERIFIER = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_v6_evidence.py"
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


def _fixture(fixture_id: str) -> dict[str, object]:
    expected = EXPECTED_FIXTURES[fixture_id]
    cpp_samples = list(range(100, 125))
    rust_samples = list(range(100, 125))
    return {
        "authority_false": True,
        "candidate_denominator": 64,
        "cpp_decision_sha256": "c3" * 32,
        "cpp_generated_count": expected["generated_count"],
        "cpp_median_nanoseconds": 112,
        "cpp_projection_sha256": "d4" * 32,
        "cpp_repeat_stable": True,
        "cpp_sample_nanoseconds": cpp_samples,
        "cpp_typed_failure_count": expected["typed_failure_count"],
        "decision_parity": True,
        "fixture_id": fixture_id,
        "fixture_payload_sha256": expected["fixture_payload_sha256"],
        "gate_passed": True,
        "ligand_atom_count": 12,
        "numeric_parity": {
            "compared_f64_count": 28544,
            "first_violation_index": None,
            "maximum_absolute_difference": 0.0,
            "maximum_scaled_difference": 0.0,
            "tolerance_violation_count": 0,
        },
        "persistent_cpp_context_count": 1,
        "persistent_rust_context_count": 1,
        "receptor_atom_count": 12,
        "rust_decision_sha256": "c3" * 32,
        "rust_generated_count": expected["generated_count"],
        "rust_median_nanoseconds": 112,
        "rust_projection_sha256": "e5" * 32,
        "rust_repeat_stable": True,
        "rust_sample_nanoseconds": rust_samples,
        "rust_to_cpp_median_ratio": 1.0,
        "rust_typed_failure_count": expected["typed_failure_count"],
        "score_term_count": 8,
    }


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
        Path("config/engine_v2_native_fixed64_cpu_profile_v6.json"),
        Path("config/engine_v2_native_fixed64_cpu_profile_v6_sources.json"),
        Path("tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py"),
        Path("tools/verify_engine_v2_native_fixed64_cpu_v6_evidence.py"),
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
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="not clean"):
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
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match=match):
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
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="semantics changed"):
        require_attempt_bytes(
            _envelope(attempt, ATTEMPT_DOMAIN),
            activation_sha256=_domain(ACTIVATION_DOMAIN, _PROFILE_RAW),
            output_path_sha256=_OUTPUT_PATH_SHA256,
        )


def test_attempt_rejects_other_build_configuration() -> None:
    attempt = _attempt()
    attempt["build_configuration_sha256"] = "00" * 32
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="semantics changed"):
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
        NativeFixed64CPUV6EvidenceError,
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


def test_artifact_receipt_tamper_fails_closed() -> None:
    attempt_raw, artifact_raw, terminal_raw = _evidence(passed=False)
    artifact_raw = artifact_raw.replace(b'"source_checkout', b'"source_checkouu', 1)
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="receipt"):
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
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="identity"):
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
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="timing samples"):
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
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="authority"):
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
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="attempt ledger semantics"):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
            expected_source_commit_oid=_SOURCE_COMMIT_OID,
            terminal_raw=terminal_raw,
            output_path_sha256="ff" * 32,
            profile_raw=_PROFILE_RAW,
        )
