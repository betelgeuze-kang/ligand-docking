from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_script(path: str) -> dict:
    proc = subprocess.run(
        [sys.executable, path],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout)


def test_check_independent_product_readiness_script_reports_restricted_ready_with_claim_boundary() -> None:
    payload = _run_script("scripts/check_independent_product_readiness.py")
    summary = payload["summary"]

    assert summary["status"] == "independent_product_readiness_verified"
    assert summary["independent_restricted_product_ready"] is True
    assert summary["full_commercial_claim_promotion_ready"] is False
    assert summary["full_commercial_science_claim_blocked"] is True
    assert summary["full_commercial_open_gap_ids"] == ["SCI-GPCR", "SCI-OPENMM"]
    assert summary["blocker_count"] == 0
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert {
        "release_source_of_truth_ready",
        "release_refresh_final_gates_verified",
        "full_commercial_science_claim_blockers_explicit",
    }.issubset({row["check"] for row in payload["rows"]})


def test_verify_quality_gate_script_rebuilds_operational_quality_fail_closed() -> None:
    payload = _run_script("scripts/verify_quality_gate.py")
    summary = payload["summary"]

    assert summary["status"] == "product_quality_gate_verified"
    assert summary["quality_gate_ready"] is True
    assert summary["blocker_count"] == 0
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    rows = {row["check"]: row for row in payload["rows"]}
    assert rows["fail_closed_execution_posture"]["status"] == "pass"
    assert rows["production_ai_correction_guarded"]["status"] == "pass"
