from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt import (
    EXPECTED_RECEIPT_SHA256,
    NativeFixed64CPUV7ExecutionReceiptError,
    RECEIPT_DOMAIN,
    require_execution_receipt_bytes,
    verify_execution_receipt,
)


_ROOT = Path(__file__).resolve().parents[2]
_RECEIPT = (
    _ROOT
    / "config/engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.json"
)
_VERIFIER = (
    _ROOT
    / "tools/verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.py"
)


def _canonical_projection(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _envelope(projection: dict[str, object]) -> bytes:
    receipt = hashlib.sha256(
        RECEIPT_DOMAIN + _canonical_projection(projection)
    ).hexdigest()
    return json.dumps(
        {"projection": projection, "receipt_sha256": receipt},
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")


def _projection() -> dict[str, object]:
    value = json.loads(_RECEIPT.read_text(encoding="ascii"))
    projection = value["projection"]
    assert isinstance(projection, dict)
    return projection


def test_frozen_execution_receipt_verifies() -> None:
    projection = require_execution_receipt_bytes(_RECEIPT.read_bytes())
    assert projection["status"] == "recorded_pass_non_authoritative"
    assert projection["execution"]["execution_consumed"] is True
    assert projection["authority"]["qualification_authority"] is False


def test_frozen_receipt_sha_is_canonical() -> None:
    envelope = json.loads(_RECEIPT.read_text(encoding="ascii"))
    projection = envelope["projection"]
    assert isinstance(projection, dict)
    observed = hashlib.sha256(
        RECEIPT_DOMAIN + _canonical_projection(projection)
    ).hexdigest()
    assert observed == EXPECTED_RECEIPT_SHA256 == envelope["receipt_sha256"]


def test_static_cli_resolves_without_site_packages() -> None:
    completed = subprocess.run(
        [sys.executable, "-S", str(_VERIFIER)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert completed.stderr == ""
    assert result["recorded_decision"] == "PASS"
    assert result["raw_evidence_reverified"] is False
    assert result["historical_source_reverified"] is True
    assert result["all_authority_false"] is True


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("authority", "qualification_authority"), True),
        (("claims", "cpu_product_performance_claimed"), True),
        (("execution", "execution_consumed"), False),
        (("profile", "source_commit_oid"), "0" * 40),
        (("raw_evidence", "artifact", "raw_sha256"), "0" * 64),
        (("fixtures", 0, "candidate_denominator"), 63),
        (("fixtures", 0, "numeric_parity", "tolerance_violation_count"), 1),
        (("fixtures", 1, "rust_to_cpp_median_ratio"), 1.1),
        (("external_authority_snapshot", "operations_decision_ready"), True),
    ],
)
def test_semantic_or_identity_mutation_fails_closed(
    path: tuple[str | int, ...], value: object
) -> None:
    projection = copy.deepcopy(_projection())
    cursor: object = projection
    for component in path[:-1]:
        if isinstance(component, int):
            assert isinstance(cursor, list)
            cursor = cursor[component]
        else:
            assert isinstance(cursor, dict)
            cursor = cursor[component]
    terminal = path[-1]
    if isinstance(terminal, int):
        assert isinstance(cursor, list)
        cursor[terminal] = value
    else:
        assert isinstance(cursor, dict)
        cursor[terminal] = value
    with pytest.raises(
        NativeFixed64CPUV7ExecutionReceiptError,
        match="execution receipt identity changed",
    ):
        require_execution_receipt_bytes(_envelope(projection))


def test_duplicate_json_key_fails_closed() -> None:
    raw = b'{"projection":{},"projection":{},"receipt_sha256":"' + b"0" * 64 + b'"}'
    with pytest.raises(
        NativeFixed64CPUV7ExecutionReceiptError, match="duplicate JSON key"
    ):
        require_execution_receipt_bytes(raw)


def test_partial_raw_reverification_arguments_fail_closed() -> None:
    with pytest.raises(
        NativeFixed64CPUV7ExecutionReceiptError,
        match="must be supplied together",
    ):
        verify_execution_receipt(
            receipt_path=_RECEIPT,
            artifact_path=Path("/tmp/not-opened.json"),
            attempt_path=None,
            repo_root=_ROOT,
            terminal_path=None,
        )
