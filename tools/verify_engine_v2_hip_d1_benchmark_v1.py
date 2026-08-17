#!/usr/bin/env python3
"""Verify a completed representative D1 CPU/HIP benchmark result.

The verifier checks denominator, discrete scientific parity, bounded numerical
parity, timing samples, hardware/toolchain identity, and a fail-closed claim
boundary. It never executes a GPU or authorizes an acceleration claim.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_profile/1.0.0"
RESULT_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_result/1.0.0"


class HipBenchmarkError(ValueError):
    """The HIP D1 benchmark profile or result is inconsistent."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HipBenchmarkError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise HipBenchmarkError("JSON root must be object")
    return value


def _positive_samples(value: Any, name: str, minimum_count: int) -> list[float]:
    if type(value) is not list or len(value) < minimum_count:
        raise HipBenchmarkError(f"{name}: insufficient samples")
    output: list[float] = []
    for raw in value:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise HipBenchmarkError(f"{name}: invalid timing")
        number = float(raw)
        if not math.isfinite(number) or number <= 0.0:
            raise HipBenchmarkError(f"{name}: invalid timing")
        output.append(number)
    return output


def _finite_values(value: Any, name: str) -> list[float]:
    if type(value) is not list:
        raise HipBenchmarkError(f"{name}: scientific_values must be a list")
    output: list[float] = []
    for raw in value:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise HipBenchmarkError(f"{name}: invalid scientific value")
        number = float(raw)
        if not math.isfinite(number):
            raise HipBenchmarkError(f"{name}: nonfinite scientific value")
        output.append(number)
    return output


def verify(profile_path: Path, result_path: Path) -> dict[str, Any]:
    profile, result = _load(profile_path), _load(result_path)
    if profile.get("schema_id") != PROFILE_SCHEMA:
        raise HipBenchmarkError("profile identity")
    authority = profile.get("authority")
    if type(authority) is not dict or any(
        value is not False for value in authority.values()
    ):
        raise HipBenchmarkError("profile authority")
    if result.get("schema_id") != RESULT_SCHEMA:
        raise HipBenchmarkError("result identity")
    if result.get("profile_id") != profile.get("profile_id"):
        raise HipBenchmarkError("profile cross-wire")
    required_backends = profile.get("required_backends")
    if type(required_backends) is not list or required_backends != [
        "rust_cpu",
        "hip_safe",
        "hip_fast",
    ]:
        raise HipBenchmarkError("required backend policy changed")
    architectures = result.get("architectures")
    if (
        type(architectures) is not list
        or len(architectures) < profile.get("required_architecture_count", 0)
    ):
        raise HipBenchmarkError("insufficient GPU architectures")
    seen: set[str] = set()
    tolerance = float(profile["numeric_absolute_tolerance"])
    minimum_samples = int(profile["minimum_samples_per_case"])
    case_count = int(profile["case_count"])
    denominator = int(profile["candidate_denominator"])
    for architecture in architectures:
        if type(architecture) is not dict:
            raise HipBenchmarkError("architecture row must be an object")
        gpu_architecture = architecture.get("gpu_architecture")
        if (
            type(gpu_architecture) is not str
            or not gpu_architecture
            or gpu_architecture in seen
        ):
            raise HipBenchmarkError("duplicate/invalid architecture")
        seen.add(gpu_architecture)
        for identity in (
            "gpu_model",
            "rocm_version",
            "driver_version",
            "wheel_sha256",
            "native_extension_sha256",
        ):
            value = architecture.get(identity)
            if type(value) is not str or not value:
                raise HipBenchmarkError(
                    f"{gpu_architecture}: missing identity {identity}"
                )
        backends = architecture.get("backends")
        if type(backends) is not dict or set(backends) != set(required_backends):
            raise HipBenchmarkError("backend set mismatch")
        for backend_name, backend in backends.items():
            if type(backend) is not dict:
                raise HipBenchmarkError(f"{gpu_architecture}/{backend_name}: object")
            cases = backend.get("cases")
            if type(cases) is not list or len(cases) != case_count:
                raise HipBenchmarkError(
                    f"{gpu_architecture}/{backend_name}: {case_count} cases required"
                )
            if backend.get("candidate_denominator") != denominator:
                raise HipBenchmarkError(
                    f"{gpu_architecture}/{backend_name}: denominator"
                )
            if type(backend.get("peak_memory_bytes")) is not int or backend[
                "peak_memory_bytes"
            ] < 0:
                raise HipBenchmarkError(
                    f"{gpu_architecture}/{backend_name}: peak memory"
                )
            for case_index, case in enumerate(cases):
                if type(case) is not dict:
                    raise HipBenchmarkError(
                        f"{gpu_architecture}/{backend_name}: case object"
                    )
                expected_case = f"D1_CASE_{case_index:03d}"
                if case.get("case_id") != expected_case:
                    raise HipBenchmarkError(
                        f"{gpu_architecture}/{backend_name}: case ordering mismatch"
                    )
                _positive_samples(
                    case.get("wall_time_seconds"),
                    f"{gpu_architecture}/{backend_name}/{expected_case}",
                    minimum_samples,
                )
                for digest_name in (
                    "decision_sha256",
                    "failure_sha256",
                    "rank_sha256",
                ):
                    digest = case.get(digest_name)
                    if (
                        type(digest) is not str
                        or len(digest) != 64
                        or any(
                            character not in "0123456789abcdef"
                            for character in digest
                        )
                    ):
                        raise HipBenchmarkError(
                            f"{gpu_architecture}/{backend_name}: {digest_name}"
                        )
                _finite_values(
                    case.get("scientific_values"),
                    f"{gpu_architecture}/{backend_name}/{expected_case}",
                )
        cpu_cases = backends["rust_cpu"]["cases"]
        for backend_name in ("hip_safe", "hip_fast"):
            hip_cases = backends[backend_name]["cases"]
            for cpu_case, hip_case in zip(cpu_cases, hip_cases, strict=True):
                if cpu_case["case_id"] != hip_case["case_id"]:
                    raise HipBenchmarkError("case ordering mismatch")
                for key in ("decision_sha256", "failure_sha256", "rank_sha256"):
                    if cpu_case[key] != hip_case[key]:
                        raise HipBenchmarkError(
                            f"{gpu_architecture}/{backend_name}: discrete parity"
                        )
                cpu_values = _finite_values(
                    cpu_case["scientific_values"], "rust_cpu scientific values"
                )
                hip_values = _finite_values(
                    hip_case["scientific_values"],
                    f"{backend_name} scientific values",
                )
                if len(cpu_values) != len(hip_values):
                    raise HipBenchmarkError("scientific value shape")
                if any(
                    abs(cpu_value - hip_value) > tolerance
                    for cpu_value, hip_value in zip(
                        cpu_values, hip_values, strict=True
                    )
                ):
                    raise HipBenchmarkError(
                        f"{gpu_architecture}/{backend_name}: numerical parity"
                    )
    result_authority = result.get("authority")
    if type(result_authority) is not dict or any(
        value is not False for value in result_authority.values()
    ):
        raise HipBenchmarkError("result authority escalated")
    return {
        "verified": True,
        "architecture_count": len(seen),
        "case_count": case_count,
        "candidate_denominator": denominator,
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
