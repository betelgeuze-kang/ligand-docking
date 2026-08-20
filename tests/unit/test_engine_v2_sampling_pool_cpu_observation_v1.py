from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.run_engine_v2_sampling_pool_cpu_observation_v1 import (
    EXPECTED_AUTHORITY_KEYS,
    EXPECTED_FIXTURE_COUNTS,
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
            {
                "fixture_id": fixture_id,
                "receipt_sha256": receipt,
                "ligand_atom_count": EXPECTED_FIXTURE_COUNTS[fixture_id][0],
                "receptor_atom_count": EXPECTED_FIXTURE_COUNTS[fixture_id][1],
                "exact_pair_evaluation_count": EXPECTED_FIXTURE_COUNTS[fixture_id][2],
            }
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
        _validate(value, expected_sample_count=None)

    value = fixture_document()
    value["fixtures"] = value["fixtures"][:2]
    with pytest.raises(SamplingPoolCPUObservationError, match="denominator changed"):
        _validate(value, expected_sample_count=None)


def observed_document(samples: int = 3) -> dict[str, object]:
    value = fixture_document()
    value.pop("all_authority_false")
    value["authority"] = {key: False for key in EXPECTED_AUTHORITY_KEYS}
    value["sample_count"] = samples
    value["status"] = "local_synthetic_development_observation_only"
    for row in value["fixtures"]:
        row["wall_time_ns_samples"] = list(range(1, samples + 1))
        row["wall_time_ns_p50"] = 2
        row["wall_time_ns_p95"] = samples
        row["peak_rss_kib"] = 1
        row["peak_rss_delta_kib"] = 0
    return value


def test_observation_sample_and_authority_denominators_fail_closed() -> None:
    value = observed_document()
    value["fixtures"][0]["wall_time_ns_samples"] = [1]
    with pytest.raises(SamplingPoolCPUObservationError, match="timing or memory"):
        _validate(value, expected_sample_count=3)

    value = observed_document()
    value["sample_count"] = 2
    with pytest.raises(SamplingPoolCPUObservationError, match="sample denominator"):
        _validate(value, expected_sample_count=3)

    value = observed_document()
    del value["authority"]["reservation_authorized"]
    with pytest.raises(SamplingPoolCPUObservationError, match="authority"):
        _validate(value, expected_sample_count=3)


def test_github_actions_timing_fails_before_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    from tools.run_engine_v2_sampling_pool_cpu_observation_v1 import execute

    with pytest.raises(SamplingPoolCPUObservationError, match="cannot create timing"):
        execute(samples=3)
