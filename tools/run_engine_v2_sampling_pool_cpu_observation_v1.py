#!/usr/bin/env python3
"""Build and run non-authoritative synthetic sampling-pool CPU observations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUST_ROOT = REPOSITORY_ROOT / "rust"
RUST_SOURCE = REPOSITORY_ROOT / "tools/rust/betelgeuze_sampling_pool_observe_v1.rs"
SCHEMA_ID = "betelgeuze.engine_v2_sampling_pool_cpu_observation/1.0.0"
PROFILE_ID = "engine_v2_sampling_pool_synthetic_cpu_observation_v1"
EXPECTED_RECEIPTS = {
    "small": "2603c7b0b13dd2af26313d26ce63e73e8162de396a1fb5d7030a31a993c60831",
    "medium": "61a8bb8490359fa03f0fb8fc0a12514203d602dc6539faac447f0e65e8e8d3a5",
    "large": "ded4134a8cd2e0c6d42f096c0220c22931378a5cba96e2fc36dba54f77bdc0bb",
}
EXPECTED_FIXTURE_COUNTS = {
    "small": (8, 64, 262_144),
    "medium": (24, 256, 3_145_728),
    "large": (48, 512, 12_582_912),
}
EXPECTED_AUTHORITY_KEYS = {
    "customer_pose_authorized",
    "fresh_128_execution_authorized",
    "hip_device_execution_authorized",
    "molecular_execution_authorized",
    "performance_claim_authorized",
    "product_authorized",
    "public_benchmark_authorized",
    "rank_mutation_authorized",
    "reservation_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
}
EXPECTED_MEMORY_ROLE = "descriptive_process_peak_rss_only"
EXPECTED_TIMED_BOUNDARY = (
    "produce_native_sampling_pool_only_fixture_construction_excluded"
)
EXPECTED_WALL_TIME_ROLE = "descriptive_no_threshold_no_claim"


class SamplingPoolCPUObservationError(RuntimeError):
    """Raised when build, execution, or output validation fails closed."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise SamplingPoolCPUObservationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env={
                **os.environ,
                "RAYON_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
            },
        )
    except OSError as exc:
        raise SamplingPoolCPUObservationError(
            f"command failed to launch: {command[0]}"
        ) from exc
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise SamplingPoolCPUObservationError(
            f"command timed out: {command[0]}"
        ) from exc
    completed = subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout,
        stderr,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SamplingPoolCPUObservationError(
            f"command failed ({command[0]}): {detail[:4096]}"
        )
    return completed


def _build_library() -> Path:
    completed = _run(
        (
            "cargo",
            "build",
            "--release",
            "--locked",
            "-p",
            "betelgeuze-docking-search",
            "--lib",
            "--message-format=json",
        ),
        cwd=RUST_ROOT,
        timeout=180,
    )
    observed: list[Path] = []
    for line in completed.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        target = row.get("target")
        if row.get("reason") != "compiler-artifact" or type(target) is not dict:
            continue
        if target.get("name") != "betelgeuze_docking_search":
            continue
        for filename in row.get("filenames", []):
            path = Path(filename)
            if (
                path.name == "libbetelgeuze_docking_search.rlib"
                or path.name.startswith("libbetelgeuze_docking_search-")
            ) and path.suffix == ".rlib":
                observed.append(path.resolve())
    unique = sorted(set(observed))
    if len(unique) != 1 or not unique[0].is_file():
        raise SamplingPoolCPUObservationError(
            "cargo did not report one exact docking-search rlib"
        )
    return unique[0]


def _compile_observer(rlib: Path, output: Path, *, test_harness: bool = False) -> None:
    dependency_directory = (
        rlib.parent if rlib.parent.name == "deps" else rlib.parent / "deps"
    )
    arguments = [
        "rustc",
        "--edition=2021",
        "-C",
        "opt-level=3",
    ]
    if test_harness:
        arguments.append("--test")
    arguments.extend(
        (
            str(RUST_SOURCE),
            "--extern",
            f"betelgeuze_docking_search={rlib}",
            "-L",
            f"dependency={dependency_directory}",
            "-o",
            str(output),
        )
    )
    _run(
        tuple(arguments),
        cwd=REPOSITORY_ROOT,
        timeout=120,
    )


def _validate(document: object, *, expected_sample_count: int | None) -> dict[str, Any]:
    observed = expected_sample_count is not None
    if type(document) is not dict:
        raise SamplingPoolCPUObservationError("observer output must be an object")
    value = document
    if value.get("schema_id") != SCHEMA_ID or value.get("profile_id") != PROFILE_ID:
        raise SamplingPoolCPUObservationError("observer schema or profile changed")
    fixtures = value.get("fixtures")
    if type(fixtures) is not list or len(fixtures) != 3:
        raise SamplingPoolCPUObservationError("observer fixture denominator changed")
    fixture_map = {row.get("fixture_id"): row for row in fixtures if type(row) is dict}
    if set(fixture_map) != set(EXPECTED_RECEIPTS):
        raise SamplingPoolCPUObservationError("observer fixture identities changed")
    for fixture_id, receipt in EXPECTED_RECEIPTS.items():
        row = fixture_map[fixture_id]
        if row.get("receipt_sha256") != receipt:
            raise SamplingPoolCPUObservationError(
                f"{fixture_id} producer receipt changed"
            )
        ligand_count, receptor_count, pair_count = EXPECTED_FIXTURE_COUNTS[fixture_id]
        if (
            row.get("ligand_atom_count") != ligand_count
            or row.get("receptor_atom_count") != receptor_count
            or row.get("exact_pair_evaluation_count") != pair_count
        ):
            raise SamplingPoolCPUObservationError(
                f"{fixture_id} work denominator changed"
            )
        if observed:
            samples = row.get("wall_time_ns_samples")
            if (
                type(samples) is not list
                or len(samples) != expected_sample_count
                or any(type(sample) is not int or sample <= 0 for sample in samples)
                or row.get("wall_time_ns_p50")
                != sorted(samples)[(50 * len(samples) + 99) // 100 - 1]
                or row.get("wall_time_ns_p95")
                != sorted(samples)[(95 * len(samples) + 99) // 100 - 1]
                or type(row.get("peak_rss_kib")) is not int
                or row["peak_rss_kib"] <= 0
                or type(row.get("peak_rss_delta_kib")) is not int
                or row["peak_rss_delta_kib"] < 0
            ):
                raise SamplingPoolCPUObservationError(
                    f"{fixture_id} timing or memory observation is invalid"
                )
    if observed:
        authority = value.get("authority")
        if (
            type(authority) is not dict
            or set(authority) != EXPECTED_AUTHORITY_KEYS
            or any(type(item) is not bool or item for item in authority.values())
        ):
            raise SamplingPoolCPUObservationError("observer authority is not all false")
        if value.get("sample_count") != expected_sample_count:
            raise SamplingPoolCPUObservationError("observer sample denominator changed")
        if value.get("status") != "local_synthetic_development_observation_only":
            raise SamplingPoolCPUObservationError("observer status changed")
        if type(value.get("cpu_model")) is not str or not value["cpu_model"].strip():
            raise SamplingPoolCPUObservationError("observer CPU identity is absent")
        if (
            value.get("memory_role") != EXPECTED_MEMORY_ROLE
            or value.get("timed_boundary") != EXPECTED_TIMED_BOUNDARY
            or value.get("wall_time_role") != EXPECTED_WALL_TIME_ROLE
        ):
            raise SamplingPoolCPUObservationError(
                "observer measurement role metadata changed"
            )
    elif value.get("all_authority_false") is not True:
        raise SamplingPoolCPUObservationError("fixture verification authority changed")
    return value


def execute(*, samples: int | None) -> dict[str, Any]:
    if samples is not None and os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise SamplingPoolCPUObservationError(
            "GitHub Actions cannot create timing observations"
        )
    rlib = _build_library()
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-sampling-pool-observer-"
    ) as directory:
        executable = Path(directory) / "betelgeuze-sampling-pool-observe-v1"
        _compile_observer(rlib, executable)
        arguments = [str(executable), "--verify-fixtures"]
        if samples is not None:
            arguments = [str(executable), "--observe", str(samples)]
        completed = _run(arguments, cwd=REPOSITORY_ROOT, timeout=600)
    try:
        document = json.loads(
            completed.stdout,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda token: (_ for _ in ()).throw(
                SamplingPoolCPUObservationError(f"non-finite JSON value: {token}")
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SamplingPoolCPUObservationError(
            "observer output is invalid JSON"
        ) from exc
    return _validate(document, expected_sample_count=samples)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_mutually_exclusive_group(required=True)
    operations.add_argument("--verify-fixtures", action="store_true")
    operations.add_argument("--observe", type=int, metavar="SAMPLES")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = execute(
        samples=arguments.observe if not arguments.verify_fixtures else None
    )
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
