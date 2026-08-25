from __future__ import annotations

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


def _bound_profile(tmp_path: Path) -> tuple[Path, dict]:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["status"] = VERIFIER.BOUND_STATUS
    profile["expected_manifest_sha256"] = "c" * 64
    profile["expected_ordered_case_ids_sha256"] = VERIFIER._canonical_sha256(
        _case_ids()
    )
    profile["blockers"] = list(VERIFIER.BOUND_BLOCKERS)
    profile["profile_sha256"] = VERIFIER._canonical_sha256(
        VERIFIER._profile_projection(profile)
    )
    return _save(tmp_path, "bound-profile.json", profile), profile


def _case(case_id: str, index: int, backend_name: str) -> dict:
    digests = {
        field: f"{index * len(VERIFIER.PARITY_DIGEST_FIELDS) + offset + 1:064x}"
        for offset, field in enumerate(VERIFIER.PARITY_DIGEST_FIELDS)
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
        **digests,
        **{f"repeat_{field}": value for field, value in digests.items()},
        "scientific_values": scientific,
        "repeat_scientific_values": list(scientific),
        "wall_time_seconds": wall_time,
    }


def _backend(case_ids: list[str], backend_name: str, architecture: str) -> dict:
    gpu = backend_name != "rust_cpu"
    profiler_trace = (
        {
            "schema_id": VERIFIER.NORMALIZED_PROFILER_TRACE_SCHEMA,
            "rows": [
                {
                    "dispatch_index": index,
                    "kernel_name": "score_candidates",
                    "runtime_seconds": 0.05,
                }
                for index in range(5)
            ],
        }
        if gpu
        else None
    )
    profiler_trace_sha256 = VERIFIER._canonical_sha256(profiler_trace) if gpu else None
    execution_receipt = {
        "schema_id": VERIFIER.EXECUTION_BACKEND_RECEIPT_SCHEMA,
        "gpu_architecture": architecture,
        "requested_backend": backend_name,
        "observed_backend": backend_name,
        "cpu_fallback_observed": False,
        "ordered_case_ids_sha256": VERIFIER._canonical_sha256(case_ids),
        "profiler_trace_sha256": profiler_trace_sha256,
    }
    return {
        "backend_name": backend_name,
        "observed_backend": backend_name,
        "cpu_fallback_observed": False,
        "execution_backend_receipt_sha256": VERIFIER._canonical_sha256(
            execution_receipt
        ),
        "candidate_denominator": 64,
        "context_construction_seconds": [0.02, 0.021, 0.019, 0.022, 0.018],
        "peak_rss_bytes": 1048576,
        "peak_vram_bytes": 2097152 if gpu else 0,
        "h2d_bytes": 4096 if gpu else 0,
        "d2h_bytes": 2048 if gpu else 0,
        "h2d_seconds": [0.001] * 5 if gpu else [],
        "d2h_seconds": [0.0005] * 5 if gpu else [],
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
                    "dispatch_count": 5,
                    "total_runtime_seconds": 0.25,
                }
            ]
            if gpu
            else []
        ),
        "cases": [
            _case(case_id, index, backend_name)
            for index, case_id in enumerate(case_ids)
        ],
    }


def _architecture(case_ids: list[str], name: str) -> dict:
    failure_probes = []
    for backend in VERIFIER.REQUIRED_BACKENDS[1:]:
        for code in VERIFIER.FAILURE_PROBE_CODES:
            observation = {
                "schema_id": VERIFIER.FAILURE_OBSERVATION_SCHEMA,
                "gpu_architecture": name,
                "requested_backend": backend,
                "error_code": code,
                "message_sha256": "9" * 64,
            }
            failure_probes.append(
                {
                    "backend": backend,
                    "error_code": code,
                    "observed_error": observation,
                    "observed_error_sha256": VERIFIER._canonical_sha256(observation),
                    "cpu_fallback_observed": False,
                    "claim_authority_granted": False,
                }
            )
    return {
        "gpu_architecture": name,
        "gpu_model": f"AMD {name}",
        "pci_device_id": "1002:744c",
        "device_serial_sha256": VERIFIER._canonical_sha256(name),
        "total_vram_bytes": 16 * 1024**3,
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
    return {
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
            "19d9fe580ef22c3600a6e79f0b8bc41d70c95b4d1fefbe86f7513ae3908f0855"
        ),
        "manifest_bound": False,
        "result_verification_authorized": False,
        "device_execution_authorized": False,
        "claim_authority_granted": False,
    }


def test_committed_unbound_profile_refuses_result_verification(tmp_path: Path) -> None:
    with pytest.raises(VERIFIER.HipBenchmarkError, match="manifest is not bound"):
        VERIFIER.verify(PROFILE, _save(tmp_path, "result.json", {}))


def test_valid_bound_result_derives_metrics_without_authority(tmp_path: Path) -> None:
    output = _verify(tmp_path)
    assert output["verified"] is True
    assert output["architecture_count"] == 2
    assert output["case_count"] == 32
    assert output["candidate_denominator"] == 64
    metrics = output["derived_metrics"]["gfx1030"]
    assert metrics["hip_fast_speed_gate_passing_case_count"] == 32
    assert metrics["rust_cpu"]["context_construction_seconds_p50"] == 0.02
    assert metrics["rust_cpu"]["case_wall_time_seconds_p50"] == 0.1
    assert metrics["rust_cpu"]["case_wall_time_seconds_p95"] == 0.1
    assert metrics["rust_cpu"]["candidate_throughput_per_second"] == 640.0
    assert metrics["hip_safe"]["h2d_seconds_p50"] == 0.001
    assert metrics["hip_safe"]["d2h_seconds_p50"] == 0.0005
    assert metrics["hip_safe"]["kernel_dispatch_count_total"] == 5
    assert metrics["hip_safe"]["kernel_runtime_seconds_total"] == 0.25
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


@pytest.mark.parametrize("field", VERIFIER.PARITY_DIGEST_FIELDS)
def test_each_discrete_parity_field_is_enforced(tmp_path: Path, field: str) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    case[field] = "f" * 64
    case[f"repeat_{field}"] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match=f"discrete parity: {field}"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_repeat_digest_drift_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["cases"][0][
        "repeat_rank_sha256"
    ] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="repeat stability"):
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
    with pytest.raises(VERIFIER.HipBenchmarkError, match="availability parity"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_nonfinite_scientific_value_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][0] = float("nan")
    case["repeat_scientific_values"][0] = float("nan")
    with pytest.raises(VERIFIER.HipBenchmarkError, match="finite number"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_numerical_parity_tolerance_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][0]["backends"]["hip_safe"]["cases"][0]
    case["scientific_values"][0] = 1.0e-5
    case["repeat_scientific_values"][0] = 1.0e-5
    with pytest.raises(VERIFIER.HipBenchmarkError, match="numerical parity"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_cross_architecture_cpu_parity_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    case = result["architectures"][1]["backends"]["rust_cpu"]["cases"][0]
    case["scientific_values"][0] = 1.0e-5
    case["repeat_scientific_values"][0] = 1.0e-5
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


@pytest.mark.parametrize("field", ["peak_vram_bytes", "h2d_bytes", "d2h_bytes"])
def test_gpu_resource_accounting_is_required(tmp_path: Path, field: str) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"][field] = 0
    with pytest.raises(VERIFIER.HipBenchmarkError, match="transfer/VRAM"):
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


def test_profiler_trace_digest_is_recomputed(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"]["profiler_trace_sha256"] = (
        "f" * 64
    )
    with pytest.raises(VERIFIER.HipBenchmarkError, match="trace SHA-256 mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_execution_backend_receipt_is_recomputed(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_fast"][
        "execution_backend_receipt_sha256"
    ] = "f" * 64
    with pytest.raises(VERIFIER.HipBenchmarkError, match="backend receipt mismatch"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_transfer_sample_floor_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["backends"]["hip_safe"]["h2d_seconds"].pop()
    with pytest.raises(VERIFIER.HipBenchmarkError, match="insufficient samples"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_complete_failure_probe_set_is_required(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"].pop()
    with pytest.raises(VERIFIER.HipBenchmarkError, match="failure probe coverage"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


def test_failure_probe_cpu_fallback_is_rejected(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    result["architectures"][0]["failure_probes"][0]["cpu_fallback_observed"] = True
    with pytest.raises(VERIFIER.HipBenchmarkError, match="CPU fallback"):
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


def test_predeclared_speed_gate_is_enforced(tmp_path: Path) -> None:
    profile_path, profile = _bound_profile(tmp_path)
    result = _result(profile)
    for architecture in result["architectures"]:
        for case in architecture["backends"]["hip_fast"]["cases"]:
            case["wall_time_seconds"] = [0.2] * 5
    with pytest.raises(VERIFIER.HipBenchmarkError, match="speed gate"):
        VERIFIER.verify(profile_path, _save(tmp_path, "result.json", result))


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
