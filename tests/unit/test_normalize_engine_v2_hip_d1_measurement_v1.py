from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/normalize_engine_v2_hip_d1_measurement_v1.py"
VERIFIER_TOOL = ROOT / "tools/verify_engine_v2_hip_d1_benchmark_v1.py"
PROFILE_PATH = ROOT / "config/engine_v2_hip_d1_benchmark_profile_v1.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NORMALIZER = _load_module("normalize_engine_v2_hip_d1_measurement_v1", TOOL)
VERIFIER = _load_module("verify_engine_v2_hip_d1_benchmark_v1", VERIFIER_TOOL)


def _profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _journal() -> dict:
    profile = _profile()
    stages = profile["profiling"]["required_stage_sequence_per_sample"]
    kernels = profile["profiling"]["required_kernel_by_stage"]
    case_ids = [f"D1_CASE_{index:02d}" for index in range(32)]
    samples = []
    for case_id in case_ids:
        for sample_index in range(profile["sampling"]["minimum_case_samples"]):
            dispatches = []
            for event_index, stage_id in enumerate(stages):
                start = 10_000 + event_index * 20_000
                dispatches.append(
                    {
                        "stage_id": stage_id,
                        "kernel_name": kernels[stage_id],
                        "start_offset_nanoseconds": start,
                        "end_offset_nanoseconds": start + 10_000,
                    }
                )
            samples.append(
                {
                    "case_id": case_id,
                    "sample_index": sample_index,
                    "wall_time_nanoseconds": 1_000_000,
                    "dispatches": dispatches,
                    "transfers": [
                        {
                            "direction": "h2d",
                            "bytes": 4096,
                            "start_offset_nanoseconds": 200_000,
                            "end_offset_nanoseconds": 210_000,
                        },
                        {
                            "direction": "d2h",
                            "bytes": 2048,
                            "start_offset_nanoseconds": 220_000,
                            "end_offset_nanoseconds": 225_000,
                        },
                    ],
                }
            )
    return {
        "schema_id": NORMALIZER.JOURNAL_SCHEMA,
        "profile_sha256": profile["profile_sha256"],
        "execution_run_id_sha256": "a" * 64,
        "backend": "hip_safe",
        "ordered_case_ids": case_ids,
        "samples": samples,
        "authority": copy.deepcopy(NORMALIZER.AUTHORITY),
    }


def test_profile_only_preserves_blockers_and_grants_nothing() -> None:
    result = NORMALIZER.profile_only(_profile())
    assert result == {
        "ok": True,
        "profile_sha256": _profile()["profile_sha256"],
        "profile_status": "frozen_non_authoritative_manifest_not_bound",
        "blockers": [
            "d1_manifest_not_materialized",
            "hip_device_evidence_not_supplied",
            "hip_device_execution_not_authorized",
        ],
        "execution_performed": False,
        "normalization_performed": False,
        "authority_granted": False,
    }


def test_normalized_fragments_are_accepted_by_result_verifier() -> None:
    profile = _profile()
    journal = _journal()
    result = NORMALIZER.normalize(profile, journal)
    wall_times = result["wall_time_seconds_by_case"]
    stages = profile["profiling"]["required_stage_sequence_per_sample"]
    kernels = profile["profiling"]["required_kernel_by_stage"]

    dispatch_count, runtime, profiler_sha256 = VERIFIER._verify_profiler_trace(
        result["profiler_trace"],
        result["profiler_trace_sha256"],
        result["kernel_dispatches"],
        "normalized",
        wall_times,
        journal["execution_run_id_sha256"],
        stages,
        kernels,
    )
    h2d_bytes, d2h_bytes, h2d_seconds, d2h_seconds, transfer_sha256 = (
        VERIFIER._verify_transfer_trace(
            result["transfer_trace"],
            result["transfer_trace_sha256"],
            "normalized",
            profile["sampling"]["minimum_transfer_samples"],
            wall_times,
            journal["execution_run_id_sha256"],
        )
    )

    assert dispatch_count == result["kernel_dispatch_count"] == 32 * 5 * 8
    assert runtime == result["kernel_runtime_seconds"]
    assert profiler_sha256 == result["profiler_trace_sha256"]
    assert h2d_bytes == result["h2d_bytes"] == 32 * 5 * 4096
    assert d2h_bytes == result["d2h_bytes"] == 32 * 5 * 2048
    assert h2d_seconds == result["h2d_seconds"]
    assert d2h_seconds == result["d2h_seconds"]
    assert transfer_sha256 == result["transfer_trace_sha256"]
    assert result["execution_launched_by_normalizer"] is False
    assert result["authority"] == NORMALIZER.AUTHORITY
    assert result["normalization_sha256"] == NORMALIZER._hash(
        {key: value for key, value in result.items() if key != "normalization_sha256"}
    )


def test_multiple_transfer_events_are_aggregated_without_deletion() -> None:
    journal = _journal()
    journal["samples"][0]["transfers"].insert(
        1,
        {
            "direction": "h2d",
            "bytes": 512,
            "start_offset_nanoseconds": 211_000,
            "end_offset_nanoseconds": 213_000,
        },
    )
    result = NORMALIZER.normalize(_profile(), journal)
    assert result["h2d_bytes"] == 32 * 5 * 4096 + 512
    assert result["h2d_seconds"][0] == pytest.approx(0.000012)
    first_rows = [
        row
        for row in result["transfer_trace"]["rows"]
        if row["case_id"] == "D1_CASE_00" and row["sample_index"] == 0
    ]
    assert [row["direction"] for row in first_rows] == ["h2d", "h2d", "d2h"]


def test_sample_order_and_coverage_are_exact() -> None:
    journal = _journal()
    journal["samples"][0], journal["samples"][1] = (
        journal["samples"][1],
        journal["samples"][0],
    )
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="sample"):
        NORMALIZER.normalize(_profile(), journal)


def test_samples_above_the_profile_minimum_are_retained() -> None:
    journal = _journal()
    extra = copy.deepcopy(journal["samples"][4])
    extra["sample_index"] = 5
    journal["samples"].insert(5, extra)
    result = NORMALIZER.normalize(_profile(), journal)
    assert len(result["wall_time_seconds_by_case"]["D1_CASE_00"]) == 6
    assert result["kernel_dispatch_count"] == (32 * 5 + 1) * 8


def test_required_stage_sequence_and_kernel_are_exact() -> None:
    journal = _journal()
    dispatches = journal["samples"][0]["dispatches"]
    first_identity = (dispatches[0]["stage_id"], dispatches[0]["kernel_name"])
    dispatches[0]["stage_id"], dispatches[0]["kernel_name"] = (
        dispatches[1]["stage_id"],
        dispatches[1]["kernel_name"],
    )
    dispatches[1]["stage_id"], dispatches[1]["kernel_name"] = first_identity
    with pytest.raises(
        NORMALIZER.MeasurementNormalizationError, match="stage sequence"
    ):
        NORMALIZER.normalize(_profile(), journal)

    journal = _journal()
    journal["samples"][0]["dispatches"][0]["kernel_name"] = "wrong_kernel"
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="stage/kernel"):
        NORMALIZER.normalize(_profile(), journal)


def test_each_sample_requires_both_transfer_directions() -> None:
    journal = _journal()
    journal["samples"][0]["transfers"] = [journal["samples"][0]["transfers"][0]]
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="both transfer"):
        NORMALIZER.normalize(_profile(), journal)


def test_aggregate_runtime_cannot_exceed_wall_time() -> None:
    journal = _journal()
    for dispatch in journal["samples"][0]["dispatches"]:
        dispatch["start_offset_nanoseconds"] = 0
        dispatch["end_offset_nanoseconds"] = 200_000
    with pytest.raises(
        NORMALIZER.MeasurementNormalizationError, match="dispatch runtime"
    ):
        NORMALIZER.normalize(_profile(), journal)


def test_integer_nanosecond_sum_equal_to_wall_is_accepted() -> None:
    journal = _journal()
    sample = journal["samples"][0]
    sample["wall_time_nanoseconds"] = 3_725
    cursor = 0
    for event_index, dispatch in enumerate(sample["dispatches"]):
        duration = 466 if event_index < 7 else 463
        dispatch["start_offset_nanoseconds"] = cursor
        cursor += duration
        dispatch["end_offset_nanoseconds"] = cursor
    sample["transfers"] = [
        {
            "direction": "h2d",
            "bytes": 1,
            "start_offset_nanoseconds": 0,
            "end_offset_nanoseconds": 1,
        },
        {
            "direction": "d2h",
            "bytes": 1,
            "start_offset_nanoseconds": 1,
            "end_offset_nanoseconds": 2,
        },
    ]
    result = NORMALIZER.normalize(_profile(), journal)
    assert result["wall_time_seconds_by_case"]["D1_CASE_00"][0] == 3.725e-6


def test_whitespace_kernel_names_and_reversed_timestamps_fail_closed() -> None:
    journal = _journal()
    journal["samples"][0]["dispatches"].append(
        {
            "stage_id": "auxiliary",
            "kernel_name": "   ",
            "start_offset_nanoseconds": 170_000,
            "end_offset_nanoseconds": 180_000,
        }
    )
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="non-empty"):
        NORMALIZER.normalize(_profile(), journal)

    journal = _journal()
    dispatches = journal["samples"][0]["dispatches"]
    dispatches[0]["start_offset_nanoseconds"] = 40_000
    dispatches[0]["end_offset_nanoseconds"] = 45_000
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="chronological"):
        NORMALIZER.normalize(_profile(), journal)


def test_frozen_sampling_policy_cannot_be_rehashed_and_relaxed() -> None:
    profile = _profile()
    profile["sampling"]["minimum_case_samples"] = 4
    projection = dict(profile)
    projection.pop("profile_sha256")
    profile["profile_sha256"] = NORMALIZER._hash(projection)
    with pytest.raises(
        NORMALIZER.MeasurementNormalizationError, match="sampling policy"
    ):
        NORMALIZER.normalize(profile, _journal())

    profile = _profile()
    profile["profiling"]["failure_probe_codes"] = ["backend_unavailable"]
    projection = dict(profile)
    projection.pop("profile_sha256")
    profile["profile_sha256"] = NORMALIZER._hash(projection)
    with pytest.raises(
        NORMALIZER.MeasurementNormalizationError, match="profiler policy"
    ):
        NORMALIZER.normalize(profile, _journal())


def test_boolean_and_out_of_range_timestamps_fail_closed() -> None:
    journal = _journal()
    journal["samples"][0]["dispatches"][0]["start_offset_nanoseconds"] = False
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="integer"):
        NORMALIZER.normalize(_profile(), journal)

    journal = _journal()
    journal["samples"][0]["transfers"][0]["end_offset_nanoseconds"] = 1_000_001
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="outside"):
        NORMALIZER.normalize(_profile(), journal)


def test_profile_run_identity_and_authority_cross_wires_fail() -> None:
    journal = _journal()
    journal["profile_sha256"] = "b" * 64
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="cross-wire"):
        NORMALIZER.normalize(_profile(), journal)

    journal = _journal()
    journal["authority"]["device_execution_authorized"] = True
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="authority"):
        NORMALIZER.normalize(_profile(), journal)


def test_cli_writes_once_and_never_executes(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.json"
    output_path = tmp_path / "normalized.json"
    journal_path.write_text(json.dumps(_journal()), encoding="utf-8")
    command = [
        sys.executable,
        str(TOOL),
        "--profile",
        str(PROFILE_PATH),
        "--journal",
        str(journal_path),
        "--output",
        str(output_path),
    ]
    first = subprocess.run(command, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    written = json.loads(output_path.read_text(encoding="ascii"))
    assert written["execution_launched_by_normalizer"] is False
    assert written["authority"] == NORMALIZER.AUTHORITY

    second = subprocess.run(command, check=False, capture_output=True, text=True)
    assert second.returncode == 1
    assert "output path must be absent" in second.stdout


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_id":"one","schema_id":"two"}', encoding="utf-8")
    with pytest.raises(NORMALIZER.MeasurementNormalizationError, match="duplicate"):
        NORMALIZER._load(duplicate)
