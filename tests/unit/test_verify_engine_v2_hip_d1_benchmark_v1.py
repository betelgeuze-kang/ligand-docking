from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "hip_verify", ROOT / "tools/verify_engine_v2_hip_d1_benchmark_v1.py"
)
assert SPEC is not None and SPEC.loader is not None
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)
PROFILE = ROOT / "config/engine_v2_hip_d1_benchmark_profile_v1.json"


def result() -> dict:
    architectures = []
    for architecture in ("gfx1030", "gfx1100"):
        backends = {}
        for backend in ("rust_cpu", "hip_safe", "hip_fast"):
            backends[backend] = {
                "candidate_denominator": 64,
                "cases": [{
                    "case_id": f"D1_CASE_{i:03d}",
                    "decision_sha256": f"{i + 1:064x}",
                    "failure_sha256": f"{i + 100:064x}",
                    "rank_sha256": f"{i + 200:064x}",
                    "scientific_values": [1.0, 2.0],
                    "wall_time_seconds": [0.1, 0.11, 0.09, 0.1, 0.12],
                } for i in range(32)],
            }
        architectures.append({
            "gpu_architecture": architecture,
            "gpu_model": "AMD GPU", "rocm_version": "6.0.2",
            "backends": backends,
        })
    return {
        "schema_id": "betelgeuze.engine_v2_hip_d1_benchmark_result/1.0.0",
        "profile_id": "engine_v2_hip_d1_representative_v1",
        "architectures": architectures,
        "authority": {
            "gpu_acceleration_claim_authorized": False,
            "scientific_claim_authorized": False,
            "benchmark_claim_authorized": False,
            "product_authorized": False,
        },
    }


def save(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(value))
    return path


def test_valid_two_architecture_result(tmp_path: Path) -> None:
    assert H.verify(PROFILE, save(tmp_path, result()))["verified"] is True


def test_discrete_parity_tamper_is_rejected(tmp_path: Path) -> None:
    value = result()
    value["architectures"][0]["backends"]["hip_fast"]["cases"][0]["rank_sha256"] = "f" * 64
    with pytest.raises(H.HipBenchmarkError, match="discrete parity"):
        H.verify(PROFILE, save(tmp_path, value))


def test_claim_escalation_is_rejected(tmp_path: Path) -> None:
    value = result()
    value["authority"]["gpu_acceleration_claim_authorized"] = True
    with pytest.raises(H.HipBenchmarkError, match="authority"):
        H.verify(PROFILE, save(tmp_path, value))
