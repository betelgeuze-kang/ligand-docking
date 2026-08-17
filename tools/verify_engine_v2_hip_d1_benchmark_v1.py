#!/usr/bin/env python3
"""Verify a completed representative D1 CPU/HIP benchmark result."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


class HipBenchmarkError(ValueError):
    pass


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise HipBenchmarkError("JSON root must be object")
    return value


def verify(profile_path: Path, result_path: Path) -> dict[str, Any]:
    profile, result = load(profile_path), load(result_path)
    if profile.get("schema_id") != "betelgeuze.engine_v2_hip_d1_benchmark_profile/1.0.0":
        raise HipBenchmarkError("profile identity")
    if any(value is not False for value in profile["authority"].values()):
        raise HipBenchmarkError("profile authority")
    if result.get("schema_id") != "betelgeuze.engine_v2_hip_d1_benchmark_result/1.0.0":
        raise HipBenchmarkError("result identity")
    if result.get("profile_id") != profile["profile_id"]:
        raise HipBenchmarkError("profile cross-wire")
    architectures = result.get("architectures")
    if type(architectures) is not list or len(architectures) < profile["required_architecture_count"]:
        raise HipBenchmarkError("insufficient GPU architectures")
    seen = set()
    tolerance = float(profile["numeric_absolute_tolerance"])
    for architecture in architectures:
        arch = architecture.get("gpu_architecture")
        if type(arch) is not str or not arch or arch in seen:
            raise HipBenchmarkError("duplicate/invalid architecture")
        seen.add(arch)
        if not architecture.get("gpu_model") or not architecture.get("rocm_version"):
            raise HipBenchmarkError("missing GPU/ROCm identity")
        backends = architecture.get("backends")
        if type(backends) is not dict or set(backends) != set(profile["required_backends"]):
            raise HipBenchmarkError("backend set mismatch")
        cpu = backends["rust_cpu"]
        for name, backend in backends.items():
            cases = backend.get("cases")
            if type(cases) is not list or len(cases) != 32:
                raise HipBenchmarkError(f"{arch}/{name}: 32 cases required")
            if backend.get("candidate_denominator") != 64:
                raise HipBenchmarkError(f"{arch}/{name}: denominator")
            for case in cases:
                samples = case.get("wall_time_seconds")
                if type(samples) is not list or len(samples) < profile["minimum_samples_per_case"]:
                    raise HipBenchmarkError(f"{arch}/{name}: samples")
                if any(
                    isinstance(v, bool) or not isinstance(v, (int, float))
                    or not math.isfinite(float(v)) or float(v) <= 0
                    for v in samples
                ):
                    raise HipBenchmarkError(f"{arch}/{name}: invalid timing")
        cpu_cases = cpu["cases"]
        for name in ("hip_safe", "hip_fast"):
            for cpu_case, hip_case in zip(cpu_cases, backends[name]["cases"], strict=True):
                if cpu_case["case_id"] != hip_case["case_id"]:
                    raise HipBenchmarkError("case ordering mismatch")
                for key in ("decision_sha256", "failure_sha256", "rank_sha256"):
                    if cpu_case[key] != hip_case[key]:
                        raise HipBenchmarkError(f"{arch}/{name}: discrete parity")
                cpu_values = cpu_case.get("scientific_values")
                hip_values = hip_case.get("scientific_values")
                if type(cpu_values) is not list or type(hip_values) is not list or len(cpu_values) != len(hip_values):
                    raise HipBenchmarkError("scientific value shape")
                if any(abs(float(a) - float(b)) > tolerance for a, b in zip(cpu_values, hip_values, strict=True)):
                    raise HipBenchmarkError(f"{arch}/{name}: numerical parity")
    authority = result.get("authority")
    if type(authority) is not dict or any(value is not False for value in authority.values()):
        raise HipBenchmarkError("result authority escalated")
    return {
        "verified": True, "architecture_count": len(seen),
        "claim_authority_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = verify(args.profile, args.result)
    except HipBenchmarkError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
