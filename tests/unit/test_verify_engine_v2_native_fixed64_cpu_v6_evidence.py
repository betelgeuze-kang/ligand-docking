from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_profile_v6 import (
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
    require_persisted_evidence_bytes,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_RAW = (
    _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v6.json"
).read_bytes()
_VERIFIER = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_v6_evidence.py"
_OUTPUT_PATH_SHA256 = "a1" * 32


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
        "cpp_median_nanoseconds": 112,
        "cpp_projection_sha256": "d4" * 32,
        "cpp_repeat_stable": True,
        "cpp_sample_nanoseconds": cpp_samples,
        "decision_parity": True,
        "fixture_id": fixture_id,
        "fixture_payload_sha256": expected["fixture_payload_sha256"],
        "gate_passed": True,
        "generated_count": expected["generated_count"],
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
        "rust_median_nanoseconds": 112,
        "rust_projection_sha256": "e5" * 32,
        "rust_repeat_stable": True,
        "rust_sample_nanoseconds": rust_samples,
        "rust_to_cpp_median_ratio": 1.0,
        "score_term_count": 8,
        "typed_failure_count": expected["typed_failure_count"],
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
            "source_commit_oid": "f6" * 20 if passed else None,
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
        terminal_raw=terminal_raw,
        output_path_sha256=_OUTPUT_PATH_SHA256,
        profile_raw=_PROFILE_RAW,
    )
    terminal = evidence["terminal"]
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


def test_artifact_receipt_tamper_fails_closed() -> None:
    attempt_raw, artifact_raw, terminal_raw = _evidence(passed=False)
    artifact_raw = artifact_raw.replace(b'"source_checkout', b'"source_checkouu', 1)
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="receipt"):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
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
    artifact["fixtures"][0]["cpp_sample_nanoseconds"].pop()
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
    terminal["authority"]["qualification_authority"] = True
    terminal_raw = _envelope(terminal, TERMINAL_DOMAIN)
    with pytest.raises(NativeFixed64CPUV6EvidenceError, match="authority"):
        require_persisted_evidence_bytes(
            artifact_raw=artifact_raw,
            attempt_raw=attempt_raw,
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
            terminal_raw=terminal_raw,
            output_path_sha256="ff" * 32,
            profile_raw=_PROFILE_RAW,
        )
