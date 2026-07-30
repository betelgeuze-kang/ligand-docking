from __future__ import annotations

import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
)
from tools.derive_engine_v2_stage0_threshold_evidence import derive


def _candidate(index: int) -> dict[str, object]:
    return {
        "proposal_index": index,
        "status": "success",
        "score": float(index),
        "rmsd_angstrom": 1.0 if index == 0 else 3.0,
        "geometric_valid": True,
        "chemical_valid": True,
    }


def _write_report(path: Path, case_ids: tuple[str, ...]) -> None:
    rows: list[dict[str, object]] = []
    for engine_id in ("engine_v2", "vina", "gnina"):
        for case_id in case_ids:
            row: dict[str, object] = {
                "case_id": case_id,
                "engine_id": engine_id,
                "status": "success",
                "rmsd_angstroms": [1.0, 2.5, 3.0, 3.5, 4.0],
            }
            if engine_id == "engine_v2":
                row["engine_v2_diagnostics"] = {
                    "preparation_status": "success",
                    "candidates": [_candidate(index) for index in range(64)],
                }
            rows.append(row)
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")


def test_threshold_evidence_is_derived_from_failure_complete_development_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "development.json"
    case_ids = FROZEN_PUBLIC_REDOCKING_CASE_IDS[2:10]
    _write_report(path, case_ids)

    evidence = derive((path,))

    assert evidence["case_count"] == 8
    assert evidence["contains_fresh_internal_blind_holdout"] is False
    assert evidence["metrics"]["candidate_generation_coverage"] == {
        "operator": "min",
        "observed_estimate": 1.0,
        "proposed_threshold": 0.9,
        "derivation_rule": "fixed_operational_floor_90pct_of_64_predeclared_slots",
    }
    assert evidence["baseline_noninferiority_margins"] == {
        "top1_2a_recovery_delta": -0.1,
        "top5_2a_recovery_delta": -0.1,
    }


def test_threshold_evidence_rejects_engineering_smoke(tmp_path: Path) -> None:
    path = tmp_path / "development.json"
    case_ids = (
        PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS[0],
        *FROZEN_PUBLIC_REDOCKING_CASE_IDS[2:9],
    )
    _write_report(path, case_ids)

    with pytest.raises(ValueError, match="engineering smoke"):
        derive((path,))


def test_post_preparation_metrics_use_conditional_denominator(tmp_path: Path) -> None:
    path = tmp_path / "development.json"
    case_ids = FROZEN_PUBLIC_REDOCKING_CASE_IDS[2:10]
    _write_report(path, case_ids)
    payload = json.loads(path.read_text(encoding="utf-8"))
    failed = next(
        row
        for row in payload["rows"]
        if row["engine_id"] == "engine_v2" and row["case_id"] == case_ids[0]
    )
    failed["status"] = "failure"
    failed["rmsd_angstroms"] = []
    failed["engine_v2_diagnostics"] = {
        "preparation_status": "failure",
        "candidates": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    evidence = derive((path,))

    assert evidence["preparation_success_case_count"] == 7
    assert evidence["metrics"]["preparation_input_unsupported_rate"][
        "observed_estimate"
    ] == 0.125
    assert evidence["metrics"]["candidate_generation_coverage"][
        "observed_estimate"
    ] == 1.0
