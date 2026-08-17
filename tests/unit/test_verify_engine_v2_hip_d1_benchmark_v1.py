from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "verify_engine_v2_hip_d1_benchmark_v1",
    ROOT / "tools/verify_engine_v2_hip_d1_benchmark_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)
PROFILE = ROOT / "config/engine_v2_hip_d1_benchmark_profile_v1.json"


def _case_ids() -> list[str]:
    return [f"PDB_{index:02d}:LIG_{index:02d}" for index in range(32)]


def _result() -> dict:
    identifiers = _case_ids()
    architectures = []
    for architecture_name in ("gfx1030", "gfx1100"):
        backends = {}
        for backend_name in ("rust_cpu", "hip_safe", "hip_fast"):
            backends[backend_name] = {
                "candidate_denominator": 64,
                "peak_memory_bytes": 1024,
                "cases": [
                    {
                        "case_id": case_id,
                        "decision_sha256": f"{index + 1:064x}",
                        "failure_sha256": f"{index + 100:064x}",
                        "rank_sha256": f"{index + 200:064x}",
                        "scientific_values": [1.0, 2.0],
                        "wall_time_seconds": [0.1, 0.11, 0.09, 0.1, 0.12],
                    }
                    for index, case_id in enumerate(identifiers)
                ],
            }
        architectures.append(
            {
                "gpu_architecture": architecture_name,
                "gpu_model": "AMD GPU",
                "rocm_version": "6.0.2",
                "driver_version": "example-driver",
                "wheel_sha256": "a" * 64,
                "native_extension_sha256": "b" * 64,
                "backends": backends,
            }
        )
    return {
        "schema_id": VERIFIER.RESULT_SCHEMA,
        "profile_id": "engine_v2_hip_d1_representative_v1",
        "manifest_sha256": "c" * 64,
        "architectures": architectures,
        "authority": {
            "gpu_acceleration_claim_authorized": False,
            "scientific_claim_authorized": False,
            "benchmark_claim_authorized": False,
            "product_authorized": False,
        },
    }


def _save(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_two_architecture_result_with_realistic_case_ids(tmp_path: Path) -> None:
    result = VERIFIER.verify(PROFILE, _save(tmp_path, _result()))
    assert result["verified"] is True
    assert result["architecture_count"] == 2
    assert result["manifest_sha256"] == "c" * 64
    assert result["claim_authority_granted"] is False


def test_discrete_parity_tamper_is_rejected(tmp_path: Path) -> None:
    value = _result()
    value["architectures"][0]["backends"]["hip_fast"]["cases"][0][
        "rank_sha256"
    ] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="discrete parity"):
        VERIFIER.verify(PROFILE, _save(tmp_path, value))


def test_numerical_parity_tamper_is_rejected(tmp_path: Path) -> None:
    value = _result()
    value["architectures"][0]["backends"]["hip_safe"]["cases"][0][
        "scientific_values"
    ][0] += 1.0e-5
    with pytest.raises(VERIFIER.HipBenchmarkError, match="numerical parity"):
        VERIFIER.verify(PROFILE, _save(tmp_path, value))


def test_cross_architecture_cpu_drift_is_rejected(tmp_path: Path) -> None:
    value = _result()
    value["architectures"][1]["backends"]["rust_cpu"]["cases"][0][
        "scientific_values"
    ][0] += 1.0e-5
    with pytest.raises(VERIFIER.HipBenchmarkError, match="numerical parity"):
        VERIFIER.verify(PROFILE, _save(tmp_path, value))


def test_ordered_cohort_mismatch_is_rejected(tmp_path: Path) -> None:
    value = _result()
    cases = value["architectures"][0]["backends"]["hip_safe"]["cases"]
    cases[0], cases[1] = cases[1], cases[0]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="ordered cohort mismatch"):
        VERIFIER.verify(PROFILE, _save(tmp_path, value))


def test_claim_escalation_is_rejected(tmp_path: Path) -> None:
    value = _result()
    value["authority"]["gpu_acceleration_claim_authorized"] = True
    with pytest.raises(VERIFIER.HipBenchmarkError, match="authority"):
        VERIFIER.verify(PROFILE, _save(tmp_path, value))


def test_single_architecture_is_rejected(tmp_path: Path) -> None:
    value = _result()
    value["architectures"].pop()
    with pytest.raises(VERIFIER.HipBenchmarkError, match="architectures"):
        VERIFIER.verify(PROFILE, _save(tmp_path, value))
