#!/usr/bin/env python3
"""Verify a completed representative D1 CPU/HIP benchmark result.

The verifier checks the manifest identity, ordered cohort, denominator,
discrete scientific parity, bounded numerical parity, timing samples,
hardware/toolchain identity, and a fail-closed claim boundary. It never
executes a GPU or authorizes an acceleration claim.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Any

PROFILE_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_profile/1.0.0"
RESULT_SCHEMA = "betelgeuze.engine_v2_hip_d1_benchmark_result/1.0.0"
CASE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def _sha256(value: Any, name: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise HipBenchmarkError(f"{name} must be lowercase SHA-256")
    return value


def _case_id(value: Any, name: str) -> str:
    if type(value) is not str or CASE_ID_RE.fullmatch(value) is None:
        raise HipBenchmarkError(f"{name} is not a valid case ID")
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


def _compare_cases(
    reference_cases: list[dict[str, Any]],
    candidate_cases: list[dict[str, Any]],
    label: str,
    tolerance: float,
) -> None:
    for reference, candidate in zip(reference_cases, candidate_cases, strict=True):
        if reference["case_id"] != candidate["case_id"]:
            raise HipBenchmarkError(f"{label}: case ordering mismatch")
        for key in ("decision_sha256", "failure_sha256", "rank_sha256"):
            if reference[key] != candidate[key]:
                raise HipBenchmarkError(f"{label}: discrete parity")
        reference_values = _finite_values(
            reference["scientific_values"], f"{label}/reference"
        )
        candidate_values = _finite_values(
            candidate["scientific_values"], f"{label}/candidate"
        )
        if len(reference_values) != len(candidate_values):
            raise HipBenchmarkError(f"{label}: scientific value shape")
        if any(
            abs(reference_value - candidate_value) > tolerance
            for reference_value, candidate_value in zip(
                reference_values, candidate_values, strict=True
            )
        ):
            raise HipBenchmarkError(f"{label}: numerical parity")


def verify(profile_path: Path, result_path: Path) -> dict[str, Any]:
    profile, result = _load(profile_path), _load(result_path)
    if profile.get("schema_id") != PROFILE_SCHEMA:
        raise HipBenchmarkError("profile identity")
    profile_authority = profile.get("authority")
    if type(profile_authority) is not dict or any(
        value is not False for value in profile_authority.values()
    ):
        raise HipBenchmarkError("profile authority")
    if result.get("schema_id") != RESULT_SCHEMA:
        raise HipBenchmarkError("result identity")
    if result.get("profile_id") != profile.get("profile_id"):
        raise HipBenchmarkError("profile cross-wire")
    manifest_sha256 = _sha256(result.get("manifest_sha256"), "manifest_sha256")
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
    canonical_case_ids: list[str] | None = None
    canonical_cpu_cases: list[dict[str, Any]] | None = None

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
        for identity in ("gpu_model", "rocm_version", "driver_version"):
            value = architecture.get(identity)
            if type(value) is not str or not value:
                raise HipBenchmarkError(
                    f"{gpu_architecture}: missing identity {identity}"
                )
        _sha256(architecture.get("wheel_sha256"), f"{gpu_architecture}.wheel")
        _sha256(
            architecture.get("native_extension_sha256"),
            f"{gpu_architecture}.native_extension",
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
            observed_ids: list[str] = []
            for case_index, case in enumerate(cases):
                if type(case) is not dict:
                    raise HipBenchmarkError(
                        f"{gpu_architecture}/{backend_name}: case object"
                    )
                observed_ids.append(
                    _case_id(
                        case.get("case_id"),
                        f"{gpu_architecture}/{backend_name}/case[{case_index}]",
                    )
                )
                _positive_samples(
                    case.get("wall_time_seconds"),
                    f"{gpu_architecture}/{backend_name}/{observed_ids[-1]}",
                    minimum_samples,
                )
                for digest_name in (
                    "decision_sha256",
                    "failure_sha256",
                    "rank_sha256",
                ):
                    _sha256(
                        case.get(digest_name),
                        f"{gpu_architecture}/{backend_name}/{digest_name}",
                    )
                _finite_values(
                    case.get("scientific_values"),
                    f"{gpu_architecture}/{backend_name}/{observed_ids[-1]}",
                )
            if len(set(observed_ids)) != case_count:
                raise HipBenchmarkError(
                    f"{gpu_architecture}/{backend_name}: duplicate case ID"
                )
            if canonical_case_ids is None:
                canonical_case_ids = observed_ids
            elif observed_ids != canonical_case_ids:
                raise HipBenchmarkError(
                    f"{gpu_architecture}/{backend_name}: ordered cohort mismatch"
                )
        cpu_cases = backends["rust_cpu"]["cases"]
        if canonical_cpu_cases is None:
            canonical_cpu_cases = cpu_cases
        else:
            _compare_cases(
                canonical_cpu_cases,
                cpu_cases,
                f"{gpu_architecture}/rust_cpu_cross_architecture",
                tolerance,
            )
        for backend_name in ("hip_safe", "hip_fast"):
            _compare_cases(
                cpu_cases,
                backends[backend_name]["cases"],
                f"{gpu_architecture}/{backend_name}",
                tolerance,
            )
    result_authority = result.get("authority")
    if type(result_authority) is not dict or set(result_authority) != set(
        profile_authority
    ):
        raise HipBenchmarkError("result authority field set")
    if any(value is not False for value in result_authority.values()):
        raise HipBenchmarkError("result authority escalated")
    return {
        "verified": True,
        "architecture_count": len(seen),
        "case_count": case_count,
        "candidate_denominator": denominator,
        "manifest_sha256": manifest_sha256,
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
