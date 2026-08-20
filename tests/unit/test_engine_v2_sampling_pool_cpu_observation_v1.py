from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.run_engine_v2_sampling_pool_cpu_observation_v1 import (
    EXPECTED_RECEIPTS,
    PROFILE_ID,
    SCHEMA_ID,
    SamplingPoolCPUObservationError,
    _reject_duplicate_keys,
    _validate,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/run_engine_v2_sampling_pool_cpu_observation_v1.py"


def fixture_document() -> dict[str, object]:
    return {
        "all_authority_false": True,
        "fixtures": [
            {"fixture_id": fixture_id, "receipt_sha256": receipt}
            for fixture_id, receipt in EXPECTED_RECEIPTS.items()
        ],
        "profile_id": PROFILE_ID,
        "schema_id": SCHEMA_ID,
        "status": "synthetic_fixture_verification_only",
    }


def test_static_fixture_runner_compiles_and_reproduces_exact_receipts() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--verify-fixtures"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    observed = json.loads(completed.stdout)
    assert observed["all_authority_false"] is True
    assert {
        row["fixture_id"]: row["receipt_sha256"] for row in observed["fixtures"]
    } == EXPECTED_RECEIPTS


def test_duplicate_crosswired_and_malformed_outputs_fail_closed() -> None:
    with pytest.raises(SamplingPoolCPUObservationError, match="duplicate JSON key"):
        json.loads('{"a":1,"a":2}', object_pairs_hook=_reject_duplicate_keys)

    value = fixture_document()
    value["fixtures"][0]["receipt_sha256"] = "00" * 32
    with pytest.raises(SamplingPoolCPUObservationError, match="receipt changed"):
        _validate(value, observed=False)

    value = fixture_document()
    value["fixtures"] = value["fixtures"][:2]
    with pytest.raises(SamplingPoolCPUObservationError, match="denominator changed"):
        _validate(value, observed=False)


def test_github_actions_timing_fails_before_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    from tools.run_engine_v2_sampling_pool_cpu_observation_v1 import execute

    with pytest.raises(SamplingPoolCPUObservationError, match="cannot create timing"):
        execute(samples=3)
