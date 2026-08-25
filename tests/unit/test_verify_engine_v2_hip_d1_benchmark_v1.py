from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/verify_engine_v2_hip_d1_benchmark_v1.py"
PROFILE = ROOT / "config/engine_v2_hip_d1_benchmark_profile_v1.json"
SPEC = importlib.util.spec_from_file_location(
    "verify_engine_v2_hip_d1_benchmark_v1", TOOL
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def _save(tmp_path: Path, name: str, value: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _case_ids() -> list[str]:
    return [f"PDB_{index:02d}:LIG_{index:02d}" for index in range(32)]


def _candidate_ids(case_id: str) -> list[str]:
    return [f"{case_id}:fixed64:{slot:02d}" for slot in range(64)]


def _bound_profile(tmp_path: Path) -> tuple[Path, dict]:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["status"] = VERIFIER.BOUND_STATUS
    profile["expected_manifest_sha256"] = "c" * 64
    profile["expected_ordered_case_ids_sha256"] = VERIFIER._canonical_sha256(
        _case_ids()
    )
    profile["expected_ordered_candidate_ids_sha256_by_case"] = {
        case_id: VERIFIER._canonical_sha256(_candidate_ids(case_id))
        for case_id in _case_ids()
    }
    profile["blockers"] = list(VERIFIER.BOUND_BLOCKERS)
    profile["profile_sha256"] = VERIFIER._canonical_sha256(
        VERIFIER._profile_projection(profile)
    )
    VERIFIER.AUTHORIZED_BOUND_PROFILE_SHA256S = frozenset({profile["profile_sha256"]})
    return _save(tmp_path, "bound-profile.json", profile), profile


def _case(case_id: str, index: int, backend_name: str) -> dict:
    statuses = [
        {
            "slot_index": slot,
            "status": "typed_failure" if slot == 63 else "scored",
            "failure_code": "candidate_rejected" if slot == 63 else None,
        }
        for slot in range(64)
    ]
    scored_slots = list(range(63))
    discrete_outputs = {
        "decision": ["scored_valid"] * 63 + ["typed_failure"],
        "score_order": scored_slots,
        "validity": [True] * 63 + [None],
        "rank": [slot + 1 for slot in scored_slots] + [None],
        "cluster": [(slot % 4) + 1 for slot in scored_slots] + [None],
    }
    digests = {
        "typed_failure_sha256": VERIFIER._canonical_sha256(statuses),
        **{
            f"{field}_sha256": VERIFIER._canonical_sha256(discrete_outputs[field])
            for field in VERIFIER.DERIVED_DISCRETE_FIELDS
        },
    }
    scientific = [
        component
        for slot in range(64)
        for component in (
            (None, None, None)
            if slot == 63
            else (float(slot), float(slot) / 10.0, float(slot) / 20.0)
        )
    ]
    wall_time = {
        "rust_cpu": [0.100, 0.110, 0.090, 0.105, 0.095],
        "hip_safe": [0.080, 0.085, 0.075, 0.082, 0.078],
        "hip_fast": [0.050, 0.055, 0.045, 0.052, 0.048],
    }[backend_name]
    return {
        "case_id": case_id,
        "candidate_count": 64,
        "ordered_candidate_ids": _candidate_ids(case_id),
        "ordered_candidate_ids_sha256": VERIFIER._canonical_sha256(
            _candidate_ids(case_id)
        ),
        "candidate_statuses": statuses,
        "repeat_candidate_statuses": [dict(status) for status in statuses],
        "discrete_outputs": discrete_outputs,
        "repeat_discrete_outputs": copy.deepcopy(discrete_outputs),
        **digests,
        **{f"repeat_{field}": value for field, value in digests.items()},
        "scientific_values": scientific,
        "repeat_scientific_values": list(scientific),
        "wall_time_seconds": wall_time,
        "repeat_wall_time_seconds": [value * 1.01 for value in wall_time],
    }


def _backend(case_ids: list[str], backend_name: str, architecture: str) -> dict:
    gpu = backend_name != "rust_cpu"
    execution_run_id = VERIFIER._canonical_sha256(
        [architecture, backend_name, "primary"]
    )
    repeat_execution_run_id = VERIFIER._canonical_sha256(
        [architecture, backend_name, "repeat"]
    )
    case_rows = [
        _case(case_id, index, backend_name) for index, case_id in enumerate(case_ids)
    ]
    profiler_rows = (
        [
            {
                "dispatch_index": dispatch_index,
                "case_id": case_id,
                "sample_index": sample_index,
                "kernel_name": "score_candidates",
                "runtime_seconds": 0.001953125,
            }
            for dispatch_index, (case_id, sample_index) in enumerate(
                (case_id, sample_index)
                for case_id in case_ids
                for sample_index in range(5)
            )
        ]
        if gpu
        else []
    )
    profiler_trace = (
        {
            "schema_id": VERIFIER.NORMALIZED_PROFILER_TRACE_SCHEMA,
            "execution_run_id_sha256": execution_run_id,
            "rows": profiler_rows,
        }
        if gpu
        else None
    )
    profiler_trace_sha256 = VERIFIER._canonical_sha256(profiler_trace) if gpu else None
    repeat_profiler_rows = (
        [
            {
                **row,
                "runtime_seconds": 0.0018,
            }
            for row in profiler_rows
        ]
        if gpu
        else []
    )
    repeat_profiler_trace = (
        {
            "schema_id": VERIFIER.NORMALIZED_PROFILER_TRACE_SCHEMA,
            "execution_run_id_sha256": repeat_execution_run_id,
            "rows": repeat_profiler_rows,
        }
        if gpu
        else None
    )
    repeat_profiler_trace_sha256 = (
        VERIFIER._canonical_sha256(repeat_profiler_trace) if gpu else None
    )
    transfer_rows = (
        [
            {
                "event_index": event_index,
                "case_id": case_id,
                "sample_index": sample_index,
                "direction": direction,
                "bytes": byte_count,
                "runtime_seconds": runtime,
            }
            for event_index, (
                case_id,
                sample_index,
                direction,
                byte_count,
                runtime,
            ) in enumerate(
                (case_id, sample_index, direction, byte_count, runtime)
                for case_id in case_ids
                for sample_index in range(5)
                for direction, byte_count, runtime in (
                    ("h2d", 4096, 0.001),
                    ("d2h", 2048, 0.0005),
                )
            )
        ]
        if gpu
        else []
    )
    transfer_trace = (
        {
            "schema_id": VERIFIER.NORMALIZED_TRANSFER_TRACE_SCHEMA,
            "execution_run_id_sha256": execution_run_id,
            "rows": transfer_rows,
        }
        if gpu
        else None
    )
    transfer_trace_sha256 = VERIFIER._canonical_sha256(transfer_trace) if gpu else None
    repeat_transfer_rows = (
        [
            {
                **row,
                "runtime_seconds": (0.0011 if row["direction"] == "h2d" else 0.00055),
            }
            for row in transfer_rows
        ]
        if gpu
        else []
    )
    repeat_transfer_trace = (
        {
            "schema_id": VERIFIER.NORMALIZED_TRANSFER_TRACE_SCHEMA,
            "execution_run_id_sha256": repeat_execution_run_id,
            "rows": repeat_transfer_rows,
        }
        if gpu
        else None
    )
    repeat_transfer_trace_sha256 = (
        VERIFIER._canonical_sha256(repeat_transfer_trace) if gpu else None
    )
    backend = {
        "backend_name": backend_name,
        "observed_backend": backend_name,
        "cpu_fallback_observed": False,
        "repeat_observed_backend": backend_name,
        "repeat_cpu_fallback_observed": False,
        "execution_run_id_sha256": execution_run_id,
        "repeat_execution_run_id_sha256": repeat_execution_run_id,
        "execution_backend_receipt_sha256": "0" * 64,
        "repeat_execution_backend_receipt_sha256": "0" * 64,
        "candidate_denominator": 64,
        "context_construction_seconds": [0.02, 0.021, 0.019, 0.022, 0.018],
        "repeat_context_construction_seconds": [
            0.0202,
            0.02121,
            0.01919,
            0.02222,
            0.01818,
        ],
        "peak_rss_bytes": 1048576,
        "peak_vram_bytes": 2097152 if gpu else 0,
        "repeat_peak_rss_bytes": 1064960,
        "repeat_peak_vram_bytes": 2162688 if gpu else 0,
        "h2d_bytes": 4096 * len(case_ids) * 5 if gpu else 0,
        "d2h_bytes": 2048 * len(case_ids) * 5 if gpu else 0,
        "h2d_seconds": [0.001] * (len(case_ids) * 5) if gpu else [],
        "d2h_seconds": [0.0005] * (len(case_ids) * 5) if gpu else [],
        "runtime_failure_counts": {
            "success": 32,
            **{code: 0 for code in VERIFIER.FAILURE_PROBE_CODES},
        },
        "profiler_trace": profiler_trace,
        "profiler_trace_sha256": profiler_trace_sha256,
        "kernel_dispatches": (
            [
                {
                    "kernel_name": "score_candidates",
                    "dispatch_count": len(profiler_rows),
                    "total_runtime_seconds": sum(
                        row["runtime_seconds"] for row in profiler_rows
                    ),
                }
            ]
            if gpu
            else []
        ),
        "transfer_trace": transfer_trace,
        "transfer_trace_sha256": transfer_trace_sha256,
        "repeat_profiler_trace": repeat_profiler_trace,
        "repeat_profiler_trace_sha256": repeat_profiler_trace_sha256,
        "repeat_kernel_dispatches": (
            [
                {
                    "kernel_name": "score_candidates",
                    "dispatch_count": len(repeat_profiler_rows),
                    "total_runtime_seconds": sum(
                        row["runtime_seconds"] for row in repeat_profiler_rows
                    ),
                }
            ]
            if gpu
            else []
        ),
        "repeat_transfer_trace": repeat_transfer_trace,
        "repeat_transfer_trace_sha256": repeat_transfer_trace_sha256,
        "cases": case_rows,
    }
    _reseal_backend_receipt(backend, architecture, case_ids)
    return backend


def _architecture(case_ids: list[str], name: str) -> dict:
    failure_probes = []
    for backend in VERIFIER.REQUIRED_BACKENDS[1:]:
        for code in VERIFIER.FAILURE_PROBE_CODES:
            execution_run_id = VERIFIER._canonical_sha256(
                [name, backend, code, "failure-probe"]
            )
            stimulus = {
                "schema_id": VERIFIER.FAILURE_STIMULUS_SCHEMA,
                "gpu_architecture": name,
                "requested_backend": backend,
                "requested_error_code": code,
                "stimulus_type": VERIFIER.FAILURE_STIMULUS_TYPES[code],
                "stimulus_parameter_sha256": VERIFIER._canonical_sha256(
                    [name, backend, code, "stimulus-parameter"]
                ),
            }
            stimulus_sha256 = VERIFIER._canonical_sha256(stimulus)
            observation = {
                "schema_id": VERIFIER.FAILURE_OBSERVATION_SCHEMA,
                "gpu_architecture": name,
                "requested_backend": backend,
                "error_code": code,
                "execution_run_id_sha256": execution_run_id,
                "failure_stimulus_sha256": stimulus_sha256,
                "message_sha256": "9" * 64,
            }
            observed_error_sha256 = VERIFIER._canonical_sha256(observation)
            receipt = {
                "schema_id": VERIFIER.FAILURE_PROBE_RECEIPT_SCHEMA,
                "gpu_architecture": name,
                "requested_backend": backend,
                "requested_error_code": code,
                "execution_run_id_sha256": execution_run_id,
                "failure_stimulus_sha256": stimulus_sha256,
                "observed_error_sha256": observed_error_sha256,
                "cpu_fallback_observed": False,
            }
            failure_probes.append(
                {
                    "backend": backend,
                    "error_code": code,
                    "execution_run_id_sha256": execution_run_id,
                    "failure_stimulus": stimulus,
                    "failure_stimulus_sha256": stimulus_sha256,
                    "observed_error": observation,
                    "observed_error_sha256": observed_error_sha256,
                    "cpu_fallback_observed": False,
                    "probe_execution_receipt_sha256": VERIFIER._canonical_sha256(
                        receipt
                    ),
                    "claim_authority_granted": False,
                }
            )
    return {
        "gpu_architecture": name,
        "gpu_model": f"AMD {name}",
        "pci_device_id": "1002:744c",
        "device_serial_sha256": VERIFIER._canonical_sha256(name),
        "total_vram_bytes": 16 * 1024**3,
        "cpu_model": "AMD Ryzen 9 7950X",
        "cpu_physical_core_count": 16,
        "cpu_logical_thread_count": 32,
        "cpu_execution_settings": {
            "benchmark_thread_count": 16,
            "affinity": "0-15",
            "frequency_governor": "performance",
            "turbo_enabled": False,
            "numa_policy": "local",
            "environment_sha256": "7" * 64,
        },
        "rocm_version": "6.4.1",
        "driver_version": "amdgpu-6.14",
        "rust_version": "rustc 1.93.0",
        "hip_compiler_version": "HIP clang 19.0.0",
        "wheel_sha256": "a" * 64,
        "native_extension_sha256": "b" * 64,
        "native_binary_sha256": "e" * 64,
        "profiler_version": "rocprofiler-sdk 0.6.0",
        "failure_probes": failure_probes,
        "backends": {
            backend: _backend(case_ids, backend, name)
            for backend in VERIFIER.REQUIRED_BACKENDS
        },
    }


def _result(profile: dict) -> dict:
    case_ids = _case_ids()
    result = {
        "schema_id": VERIFIER.RESULT_SCHEMA,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile["profile_sha256"],
        "manifest_sha256": profile["expected_manifest_sha256"],
        "ordered_case_ids": case_ids,
        "ordered_case_ids_sha256": VERIFIER._canonical_sha256(case_ids),
        "architectures": [
            _architecture(case_ids, "gfx1030"),
            _architecture(case_ids, "gfx1100"),
        ],
        "authority": {key: False for key in VERIFIER.AUTHORITY_KEYS},
        "output_claim_authorized": False,
    }
    return _seal_and_authorize_result(result)


def _seal_and_authorize_result(result: dict) -> dict:
    result["result_sha256"] = VERIFIER._canonical_sha256(
        VERIFIER._result_projection(result)
    )
    VERIFIER.AUTHORIZED_RESULT_SHA256S = frozenset({result["result_sha256"]})
    return result


def _reseal_backend_receipt(
    backend: dict, architecture: str, case_ids: list[str]
) -> None:
    for repeat in (False, True):
        prefix = "repeat_" if repeat else ""
        receipt = VERIFIER._execution_backend_receipt(
            architecture=architecture,
            backend_name=backend["backend_name"],
            observed_backend=(
                backend["repeat_observed_backend"]
                if repeat
                else backend["observed_backend"]
            ),
            cpu_fallback_observed=(
                backend["repeat_cpu_fallback_observed"]
                if repeat
                else backend["cpu_fallback_observed"]
            ),
            ordered_case_ids=case_ids,
            run_role="repeat" if repeat else "primary",
            execution_run_id_sha256=backend[f"{prefix}execution_run_id_sha256"],
            profiler_trace_sha256=backend[f"{prefix}profiler_trace_sha256"],
            transfer_trace_sha256=backend[f"{prefix}transfer_trace_sha256"],
            context_construction_samples=backend[
                f"{prefix}context_construction_seconds"
            ],
            peak_rss_bytes=backend[f"{prefix}peak_rss_bytes"],
            peak_vram_bytes=backend[f"{prefix}peak_vram_bytes"],
            cases=backend["cases"],
        )
        backend[f"{prefix}execution_backend_receipt_sha256"] = (
            VERIFIER._canonical_sha256(receipt)
        )


def _verify(tmp_path: Path, value: dict | None = None) -> dict:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile) if value is None else value
    return VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_committed_profile_is_valid_unbound_and_non_authoritative() -> None:
    result = VERIFIER.verify_profile(PROFILE)
    assert result == {
        "verified": True,
        "profile_id": "engine_v2_hip_d1_representative_v1",
        "profile_sha256": (
            "14bbcf914e5b6ad56f9969770d192b1916aac820a1a16a69eb60409bffd51606"
        ),
        "manifest_bound": False,
        "result_verification_authorized": False,
        "device_execution_authorized": False,
        "claim_authority_granted": False,
    }


def test_committed_unbound_profile_refuses_result_verification(tmp_path: Path) -> None:
    with pytest.raises(VERIFIER.HipBenchmarkError, match="manifest is not bound"):
        VERIFIER.verify(PROFILE, _save(tmp_path, "result.json", {}))


def test_arbitrarily_resealed_bound_profile_is_not_authorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    monkeypatch.setattr(VERIFIER, "AUTHORIZED_BOUND_PROFILE_SHA256S", frozenset())
    with pytest.raises(VERIFIER.HipBenchmarkError, match="not repository-authorized"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_arbitrarily_resealed_result_is_not_authorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    monkeypatch.setattr(VERIFIER, "AUTHORIZED_RESULT_SHA256S", frozenset())
    with pytest.raises(VERIFIER.HipBenchmarkError, match="result is not repository"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_valid_bound_result_derives_metrics_without_authority(tmp_path: Path) -> None:
    output = _verify(tmp_path)
    assert output["verified"] is True
    assert output["architecture_count"] == 2
    assert output["case_count"] == 32
    assert output["candidate_denominator"] == 64
    metrics = output["derived_metrics"]["gfx1030"]
    assert metrics["hip_fast_speed_gate_passing_case_count"] == 32
    assert metrics["hip_fast_primary_speed_gate_passing_case_count"] == 32
    assert metrics["hip_fast_repeat_speed_gate_passing_case_count"] == 32
    assert metrics["rust_cpu"]["context_construction_seconds_p50"] == 0.02
    assert metrics["rust_cpu"]["repeat_context_construction_seconds_p50"] == 0.0202
    assert metrics["rust_cpu"]["case_wall_time_seconds_p50"] == 0.1
    assert metrics["rust_cpu"]["case_wall_time_seconds_p95"] == 0.1
    assert metrics["rust_cpu"]["candidate_throughput_per_second"] == 640.0
    assert metrics["hip_safe"]["repeat_peak_rss_bytes"] == 1064960
    assert metrics["hip_safe"]["repeat_peak_vram_bytes"] == 2162688
    assert metrics["hip_safe"]["h2d_seconds_p50"] == 0.001
    assert metrics["hip_safe"]["d2h_seconds_p50"] == 0.0005
    assert metrics["hip_safe"]["kernel_dispatch_count_total"] == 160
    assert metrics["hip_safe"]["kernel_runtime_seconds_total"] == 0.3125
    assert output["device_execution_authorized"] is False
    assert output["claim_authority_granted"] is False


def test_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    raw = PROFILE.read_text(encoding="utf-8").replace(
        "{", '{"schema_id":"duplicate",', 1
    )
    path = tmp_path / "duplicate.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(VERIFIER.HipBenchmarkError, match="duplicate JSON key"):
        VERIFIER.verify_profile(path)


def test_json_parser_value_error_is_translated_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _save(tmp_path, "profile.json", {})

    def _raise_integer_limit(*_args: object, **_kwargs: object) -> object:
        raise ValueError("integer string conversion limit exceeded")

    monkeypatch.setattr(VERIFIER.json, "loads", _raise_integer_limit)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="cannot load.*integer string"):
        VERIFIER.verify_profile(path)


def test_profile_self_hash_tamper_is_rejected(tmp_path: Path) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["profile_sha256"] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="profile SHA-256 mismatch"):
        VERIFIER.verify_profile(_save(tmp_path, "profile.json", profile))


def test_result_exact_field_set_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["unexpected"] = False
    with pytest.raises(VERIFIER.HipBenchmarkError, match="result field set"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_manifest_profile_cross_wire_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["manifest_sha256"] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="manifest/profile cross-wire"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_ordered_case_identity_hash_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["ordered_case_ids_sha256"] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="case identity"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_ordered_cohort_is_bound_to_profile_manifest_selection(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["ordered_case_ids"][0] = "OTHER:CASE"
    result["ordered_case_ids_sha256"] = VERIFIER._canonical_sha256(
        result["ordered_case_ids"]
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="cohort/profile cross-wire"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_candidate_denominator_deletion_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["cases"][0][
        "candidate_count"
    ] = 63
    with pytest.raises(VERIFIER.HipBenchmarkError, match="denominator deletion"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_ordered_candidate_identity_is_bound_to_profile(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    case["ordered_candidate_ids"][0] = "SUBSTITUTED:CANDIDATE:00"
    case["ordered_candidate_ids_sha256"] = VERIFIER._canonical_sha256(
        case["ordered_candidate_ids"]
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="candidate cohort/profile"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


@pytest.mark.parametrize("field", VERIFIER.PARITY_DIGEST_FIELDS)
def test_each_discrete_parity_field_is_enforced(tmp_path: Path, field: str) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    case[field] = "f" * 64
    case[f"repeat_{field}"] = "f" * 64
    expected = (
        "status SHA-256 mismatch"
        if field == "typed_failure_sha256"
        else f"{field.removesuffix('_sha256')} output SHA-256 mismatch"
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match=expected):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_digest_drift_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["cases"][0][
        "repeat_rank_sha256"
    ] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="repeat stability"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_discrete_digest_is_recomputed_from_structured_output(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    case["discrete_outputs"]["decision"][0] = "scored_alternate"
    case["repeat_discrete_outputs"]["decision"][0] = "scored_alternate"
    with pytest.raises(VERIFIER.HipBenchmarkError, match="decision output SHA-256"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_zero_based_stable_rank_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    case["discrete_outputs"]["rank"][0] = 0
    case["repeat_discrete_outputs"]["rank"][0] = 0
    with pytest.raises(VERIFIER.HipBenchmarkError, match="rank: scored-slot"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


@pytest.mark.parametrize(
    ("validity", "cluster_id", "message"),
    [(True, 0, "valid candidate cluster"), (False, 2, "invalid candidate cluster")],
)
def test_cluster_membership_matches_candidate_validity(
    tmp_path: Path, validity: bool, cluster_id: int, message: str
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    for prefix in ("", "repeat_"):
        case[f"{prefix}discrete_outputs"]["validity"][0] = validity
        case[f"{prefix}discrete_outputs"]["cluster"][0] = cluster_id
    with pytest.raises(VERIFIER.HipBenchmarkError, match=message):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_untrusted_cluster_id_is_bounded_before_range_expansion(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    for prefix in ("", "repeat_"):
        case[f"{prefix}discrete_outputs"]["cluster"][0] = 10**30
    with pytest.raises(VERIFIER.HipBenchmarkError, match="cluster ID exceeds"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_scientific_vector_shape_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"].pop()
    case["repeat_scientific_values"].pop()
    with pytest.raises(VERIFIER.HipBenchmarkError, match="scientific vector shape"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_scientific_drift_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"]["cases"][0][
        "repeat_scientific_values"
    ][0] = 1.0e-5
    with pytest.raises(VERIFIER.HipBenchmarkError, match="repeat scientific"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_partial_typed_failure_scientific_slot_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][0] = None
    case["repeat_scientific_values"][0] = None
    with pytest.raises(VERIFIER.HipBenchmarkError, match="partial typed-failure"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_typed_failure_scientific_availability_parity_is_enforced(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][:3] = [None, None, None]
    case["repeat_scientific_values"][:3] = [None, None, None]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="scientific/status mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_null_scientific_triple_requires_structured_typed_failure(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    for architecture in result["architectures"]:
        for backend in architecture["backends"].values():
            case = backend["cases"][0]
            case["scientific_values"][:3] = [None, None, None]
            case["repeat_scientific_values"][:3] = [None, None, None]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="scientific/status mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_structured_candidate_status_digest_is_recomputed(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["rust_cpu"]["cases"][0]
    for field in ("candidate_statuses", "repeat_candidate_statuses"):
        case[field][0] = {
            "slot_index": 0,
            "status": "typed_failure",
            "failure_code": "candidate_rejected",
        }
    case["scientific_values"][:3] = [None, None, None]
    case["repeat_scientific_values"][:3] = [None, None, None]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="status SHA-256 mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_boolean_candidate_slot_index_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["rust_cpu"]["cases"][0]
    case["candidate_statuses"][0]["slot_index"] = False
    case["repeat_candidate_statuses"][0]["slot_index"] = False
    with pytest.raises(VERIFIER.HipBenchmarkError, match="candidate status ordering"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_nonfinite_scientific_value_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][0] = float("nan")
    case["repeat_scientific_values"][0] = float("nan")
    with pytest.raises(VERIFIER.HipBenchmarkError, match="finite number"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


@pytest.mark.parametrize("component_index", [1, 2])
def test_negative_rmsd_is_rejected(tmp_path: Path, component_index: int) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][component_index] = -1.0e-6
    case["repeat_scientific_values"][component_index] = -1.0e-6
    with pytest.raises(VERIFIER.HipBenchmarkError, match="RMSD must be nonnegative"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_integer_to_float_overflow_fails_closed_in_cli(tmp_path: Path) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["parity"]["absolute_tolerance"] = 10**400
    profile["profile_sha256"] = VERIFIER._canonical_sha256(
        VERIFIER._profile_projection(profile)
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--profile",
            str(_save(tmp_path, "overflow-profile.json", profile)),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "verified": False,
        "error": "absolute tolerance must be finite number",
    }


def test_numerical_parity_tolerance_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][0] = 1.0e-5
    case["repeat_scientific_values"][0] = 1.0e-5
    _reseal_backend_receipt(
        result["architectures"][0]["backends"]["hip_safe"],
        "gfx1030",
        result["ordered_case_ids"],
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="numerical parity"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_score_order_is_derived_from_scientific_scores(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][0] = 100.0
    case["scientific_values"][3] = -100.0
    case["repeat_scientific_values"][0] = 100.0
    case["repeat_scientific_values"][3] = -100.0
    with pytest.raises(VERIFIER.HipBenchmarkError, match="score order/scientific"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_cross_architecture_cpu_parity_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][1]["backends"]["rust_cpu"]["cases"][0]
    case["scientific_values"][0] = 1.0e-5
    case["repeat_scientific_values"][0] = 1.0e-5
    _reseal_backend_receipt(
        result["architectures"][1]["backends"]["rust_cpu"],
        "gfx1100",
        result["ordered_case_ids"],
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="numerical parity"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_backend_ordered_cohort_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    cases = result["architectures"][0]["backends"]["hip_safe"]["cases"]
    cases[0], cases[1] = cases[1], cases[0]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="ordered cohort"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_baseline_architecture_is_required(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case_ids = result["ordered_case_ids"]
    result["architectures"] = [
        _architecture(case_ids, "gfx1100"),
        _architecture(case_ids, "gfx942"),
    ]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="gfx1030"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_architecture_must_be_in_owner_sealed_policy(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][1] = _architecture(result["ordered_case_ids"], "gfx1010")
    with pytest.raises(VERIFIER.HipBenchmarkError, match="not allowed by profile"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_alphanumeric_newer_architecture_is_accepted(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][1] = _architecture(result["ordered_case_ids"], "gfx90a")
    _seal_and_authorize_result(result)
    assert VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))[
        "verified"
    ]


def test_distinct_architectures_require_distinct_device_identities(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][1]["device_serial_sha256"] = result["architectures"][0][
        "device_serial_sha256"
    ]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="duplicate GPU device"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_device_and_toolchain_identity_are_required(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["hip_compiler_version"] = ""
    with pytest.raises(VERIFIER.HipBenchmarkError, match="nonempty string"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_profiler_identity_requires_version_suffix(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["profiler_version"] = "rocprofiler-sdk "
    with pytest.raises(VERIFIER.HipBenchmarkError, match="profiler identity"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_cpu_reference_execution_identity_is_required(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["cpu_execution_settings"]["affinity"] = ""
    with pytest.raises(VERIFIER.HipBenchmarkError, match="nonempty string"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


@pytest.mark.parametrize("field", ["peak_vram_bytes", "h2d_bytes", "d2h_bytes"])
def test_gpu_resource_accounting_is_required(tmp_path: Path, field: str) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"][field] = 0
    with pytest.raises(VERIFIER.HipBenchmarkError, match="transfer/VRAM"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_transfer_summary_is_derived_from_normalized_trace(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"]["h2d_bytes"] += 1
    with pytest.raises(VERIFIER.HipBenchmarkError, match="transfer summary/trace"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_transfer_trace_is_bound_to_execution_receipt(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_safe"]
    backend["transfer_trace"]["rows"][0]["bytes"] += 1
    backend["transfer_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["transfer_trace"]
    )
    backend["h2d_bytes"] += 1
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="backend receipt mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_transfer_trace_aggregates_multiple_events_per_timed_sample(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_safe"]
    original = backend["transfer_trace"]["rows"][0]
    first = {**original, "bytes": 1024, "runtime_seconds": 0.00025}
    second = {**original, "bytes": 3072, "runtime_seconds": 0.00075}
    backend["transfer_trace"]["rows"][0:1] = [first, second]
    for event_index, row in enumerate(backend["transfer_trace"]["rows"]):
        row["event_index"] = event_index
    backend["transfer_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["transfer_trace"]
    )
    _reseal_backend_receipt(backend, "gfx1030", result["ordered_case_ids"])
    _seal_and_authorize_result(result)
    output = VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))
    assert output["derived_metrics"]["gfx1030"]["hip_safe"][
        "h2d_seconds_p50"
    ] == pytest.approx(0.001)


def test_transfer_trace_must_cover_every_case_sample_and_direction(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_safe"]
    removed = backend["transfer_trace"]["rows"].pop(0)
    for event_index, row in enumerate(backend["transfer_trace"]["rows"]):
        row["event_index"] = event_index
    backend["transfer_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["transfer_trace"]
    )
    backend["h2d_bytes"] -= removed["bytes"]
    backend["h2d_seconds"].pop(0)
    _reseal_backend_receipt(backend, "gfx1030", result["ordered_case_ids"])
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="transfer case/sample"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_kernel_trace_is_required(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["kernel_dispatches"] = []
    with pytest.raises(VERIFIER.HipBenchmarkError, match="kernel dispatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_kernel_summary_must_be_derived_from_profiler_trace(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["kernel_dispatches"][0][
        "dispatch_count"
    ] = 6
    with pytest.raises(VERIFIER.HipBenchmarkError, match="summary/trace mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_tiny_profiler_runtime_cannot_use_dominating_absolute_tolerance(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    architecture = result["architectures"][0]
    backend = architecture["backends"]["hip_fast"]
    for row in backend["profiler_trace"]["rows"]:
        row["runtime_seconds"] = 1.0e-20
    backend["profiler_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["profiler_trace"]
    )
    backend["kernel_dispatches"][0]["total_runtime_seconds"] = 1.0e-15
    _reseal_backend_receipt(
        backend, architecture["gpu_architecture"], result["ordered_case_ids"]
    )
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="summary/trace mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_reported_kernel_runtime_is_derived_from_profiler_trace(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    architecture = result["architectures"][0]
    backend = architecture["backends"]["hip_fast"]
    for row in backend["profiler_trace"]["rows"]:
        row["runtime_seconds"] = 1.0e-6
    expected_runtime = VERIFIER._finite_sum(
        tuple(row["runtime_seconds"] for row in backend["profiler_trace"]["rows"]),
        "test profiler runtime",
    )
    submitted_runtime = expected_runtime * (1.0 + 5.0e-13)
    backend["profiler_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["profiler_trace"]
    )
    backend["kernel_dispatches"][0]["total_runtime_seconds"] = submitted_runtime
    _reseal_backend_receipt(
        backend, architecture["gpu_architecture"], result["ordered_case_ids"]
    )
    _seal_and_authorize_result(result)
    output = VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))
    observed = output["derived_metrics"]["gfx1030"]["hip_fast"][
        "kernel_runtime_seconds_total"
    ]
    assert observed == expected_runtime
    assert observed != submitted_runtime


def test_profiler_trace_digest_is_recomputed(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["profiler_trace_sha256"] = (
        "f" * 64
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="trace SHA-256 mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_boolean_profiler_dispatch_index_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_fast"]
    backend["profiler_trace"]["rows"][0]["dispatch_index"] = False
    backend["profiler_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["profiler_trace"]
    )
    _reseal_backend_receipt(backend, "gfx1030", result["ordered_case_ids"])
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="profiler dispatch ordering"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_profiler_trace_must_cover_every_case_sample(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    architecture = result["architectures"][0]
    backend = architecture["backends"]["hip_fast"]
    backend["profiler_trace"]["rows"].pop()
    backend["profiler_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["profiler_trace"]
    )
    backend["kernel_dispatches"][0]["dispatch_count"] = len(
        backend["profiler_trace"]["rows"]
    )
    backend["kernel_dispatches"][0]["total_runtime_seconds"] = sum(
        row["runtime_seconds"] for row in backend["profiler_trace"]["rows"]
    )
    execution_receipt = {
        "schema_id": VERIFIER.EXECUTION_BACKEND_RECEIPT_SCHEMA,
        "gpu_architecture": architecture["gpu_architecture"],
        "requested_backend": "hip_fast",
        "observed_backend": "hip_fast",
        "cpu_fallback_observed": False,
        "ordered_case_ids_sha256": result["ordered_case_ids_sha256"],
        "profiler_trace_sha256": backend["profiler_trace_sha256"],
    }
    backend["execution_backend_receipt_sha256"] = VERIFIER._canonical_sha256(
        execution_receipt
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="case/sample coverage"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_profiler_dispatch_runtime_cannot_exceed_wall_sample(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_fast"]
    backend["cases"][0]["wall_time_seconds"] = [1.0e-6] * 5
    _reseal_backend_receipt(backend, "gfx1030", result["ordered_case_ids"])
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="exceeds wall time"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_execution_backend_receipt_is_recomputed(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"][
        "execution_backend_receipt_sha256"
    ] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="backend receipt mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


@pytest.mark.parametrize(
    "field",
    ["context_construction_seconds", "repeat_context_construction_seconds"],
)
def test_context_timing_samples_are_bound_to_execution_receipts(
    tmp_path: Path, field: str
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_fast"]
    backend[field][0] *= 0.5
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="backend receipt mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


@pytest.mark.parametrize(
    "field",
    [
        "peak_rss_bytes",
        "peak_vram_bytes",
        "repeat_peak_rss_bytes",
        "repeat_peak_vram_bytes",
    ],
)
def test_peak_memory_metrics_are_bound_to_execution_receipts(
    tmp_path: Path, field: str
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_fast"]
    backend[field] += 4096
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="backend receipt mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_execution_identity_must_be_distinct(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_fast"]
    backend["repeat_execution_run_id_sha256"] = backend["execution_run_id_sha256"]
    with pytest.raises(VERIFIER.HipBenchmarkError, match="repeat execution identity"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_profiler_trace_cannot_reuse_primary_execution_evidence(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_fast"]
    backend["repeat_profiler_trace"] = copy.deepcopy(backend["profiler_trace"])
    backend["repeat_profiler_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["repeat_profiler_trace"]
    )
    backend["repeat_kernel_dispatches"] = copy.deepcopy(backend["kernel_dispatches"])
    _reseal_backend_receipt(backend, "gfx1030", result["ordered_case_ids"])
    _seal_and_authorize_result(result)
    with pytest.raises(
        VERIFIER.HipBenchmarkError, match="profiler trace execution identity"
    ):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_transfer_trace_cannot_reuse_primary_execution_evidence(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    backend = result["architectures"][0]["backends"]["hip_fast"]
    backend["repeat_transfer_trace"] = copy.deepcopy(backend["transfer_trace"])
    backend["repeat_transfer_trace_sha256"] = VERIFIER._canonical_sha256(
        backend["repeat_transfer_trace"]
    )
    _reseal_backend_receipt(backend, "gfx1030", result["ordered_case_ids"])
    _seal_and_authorize_result(result)
    with pytest.raises(
        VERIFIER.HipBenchmarkError, match="transfer trace execution identity"
    ):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_outputs_are_bound_to_repeat_execution_receipt(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"][
        "repeat_execution_backend_receipt_sha256"
    ] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="repeat execution backend"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_transfer_sample_floor_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"]["h2d_seconds"] = [0.001] * 4
    with pytest.raises(VERIFIER.HipBenchmarkError, match="insufficient samples"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_complete_failure_probe_set_is_required(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"].pop()
    with pytest.raises(VERIFIER.HipBenchmarkError, match="failure probe coverage"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_failure_probe_execution_identities_are_distinct(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    probes = result["architectures"][0]["failure_probes"]
    probes[1]["execution_run_id_sha256"] = probes[0]["execution_run_id_sha256"]
    _seal_and_authorize_result(result)
    with pytest.raises(
        VERIFIER.HipBenchmarkError, match="duplicate execution identity"
    ):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_failure_probe_stimulus_type_is_predeclared(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"][0]["failure_stimulus"][
        "stimulus_type"
    ] = "operator_selected"
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="failure stimulus type"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_failure_probe_receipt_binds_observation_to_execution(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    probe = result["architectures"][0]["failure_probes"][0]
    probe["observed_error"]["message_sha256"] = "8" * 64
    probe["observed_error_sha256"] = VERIFIER._canonical_sha256(probe["observed_error"])
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="probe receipt mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_failure_probe_cpu_fallback_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"][0]["cpu_fallback_observed"] = True
    with pytest.raises(VERIFIER.HipBenchmarkError, match="CPU fallback"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


@pytest.mark.parametrize(
    "field,value",
    [("backend", []), ("error_code", {})],
)
def test_failure_probe_labels_fail_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"][0][field] = value
    with pytest.raises(VERIFIER.HipBenchmarkError, match="nonempty string"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_failure_probe_structured_error_code_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"][0]["observed_error"]["error_code"] = (
        "device_oom"
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="observation error code"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_failure_observation_digest_is_recomputed(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"][0]["observed_error"][
        "message_sha256"
    ] = "8" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="observation SHA-256"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_representative_cpu_fallback_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"]["cpu_fallback_observed"] = True
    with pytest.raises(VERIFIER.HipBenchmarkError, match="representative CPU fallback"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_representative_cpu_fallback_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"][
        "repeat_cpu_fallback_observed"
    ] = True
    with pytest.raises(VERIFIER.HipBenchmarkError, match="repeat representative CPU"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_representative_runtime_failure_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    counts = result["architectures"][0]["backends"]["hip_safe"][
        "runtime_failure_counts"
    ]
    counts["success"] = 31
    counts["device_oom"] = 1
    with pytest.raises(VERIFIER.HipBenchmarkError, match="runtime success denominator"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_each_representative_case_requires_a_scored_candidate(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    for architecture in result["architectures"]:
        for backend in architecture["backends"].values():
            case = backend["cases"][0]
            statuses = [
                {
                    "slot_index": slot,
                    "status": "typed_failure",
                    "failure_code": "candidate_rejected",
                }
                for slot in range(64)
            ]
            case["candidate_statuses"] = statuses
            case["repeat_candidate_statuses"] = [dict(status) for status in statuses]
            status_sha256 = VERIFIER._canonical_sha256(statuses)
            case["typed_failure_sha256"] = status_sha256
            case["repeat_typed_failure_sha256"] = status_sha256
            case["scientific_values"] = [None] * (64 * 3)
            case["repeat_scientific_values"] = [None] * (64 * 3)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="insufficient scored"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_predeclared_speed_gate_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    for architecture in result["architectures"]:
        backend = architecture["backends"]["hip_fast"]
        for case in backend["cases"]:
            case["wall_time_seconds"] = [0.2] * 5
        _reseal_backend_receipt(
            backend, architecture["gpu_architecture"], result["ordered_case_ids"]
        )
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="speed gate"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_speed_gate_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    for architecture in result["architectures"]:
        backend = architecture["backends"]["hip_fast"]
        for case in backend["cases"]:
            case["repeat_wall_time_seconds"] = [10.0] * 5
        _reseal_backend_receipt(
            backend, architecture["gpu_architecture"], result["ordered_case_ids"]
        )
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="replicated.*speed gate"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_speed_gate_timing_samples_are_bound_to_execution_receipt(
    tmp_path: Path,
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["cases"][0][
        "wall_time_seconds"
    ] = [0.01] * 5
    with pytest.raises(VERIFIER.HipBenchmarkError, match="backend receipt mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_overflowing_derived_timing_sum_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    for architecture in result["architectures"]:
        for backend_name, backend in architecture["backends"].items():
            timing = 5.0e307 if backend_name == "hip_fast" else 1.0e308
            for case in backend["cases"]:
                case["wall_time_seconds"] = [timing] * 5
            _reseal_backend_receipt(
                backend, architecture["gpu_architecture"], result["ordered_case_ids"]
            )
    _seal_and_authorize_result(result)
    with pytest.raises(VERIFIER.HipBenchmarkError, match="derived sum overflow"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_even_median_preserves_positive_subnormal_values() -> None:
    smallest_subnormal = 5e-324
    assert (
        VERIFIER._median([smallest_subnormal, smallest_subnormal], "subnormal")
        == smallest_subnormal
    )


@pytest.mark.parametrize(
    "location,key",
    [
        ("authority", "gpu_acceleration_claim_authorized"),
        ("top", "output_claim_authorized"),
    ],
)
def test_authority_escalation_is_rejected(
    tmp_path: Path, location: str, key: str
) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    if location == "authority":
        result["authority"][key] = True
    else:
        result[key] = True
    with pytest.raises(VERIFIER.HipBenchmarkError, match="authority"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_profile_only_cli_succeeds_without_result() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--profile", str(PROFILE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["manifest_bound"] is False
