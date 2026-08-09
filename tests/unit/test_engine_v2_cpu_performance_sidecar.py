from __future__ import annotations

import base64
import copy
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, Mapping

import pytest

import betelgeuze_engine_v2.docking.performance_sidecar as performance_sidecar
from betelgeuze_engine_v2.docking.performance_sidecar import (
    CPUPerformanceError,
    FROZEN_SYNTHETIC_FIXTURES,
    LiveCPUPerformanceRunResult,
    VerifiedOfflineCPUPerformanceArtifact,
    compare_geometric_outputs,
    generate_synthetic_geometric_fixture,
    load_cpu_performance_artifact,
    load_cpu_performance_profile,
    normalize_python_geometric_output,
    require_cpu_performance_artifact_document,
    require_cpu_performance_artifact_bytes,
    run_sealed_local_performance_runner,
    write_cpu_performance_artifact,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_PATH = _REPO_ROOT / "config/engine_v2_cpu_performance_profile.json"
_INTEGER_METRICS = {
    "ligand_atom_count",
    "receptor_atom_count",
    "exact_pair_count",
    "penetration_pair_count",
    "unique_ligand_penetration_atom_count",
    "unique_ligand_heavy_atom_penetration_count",
}
_FLOAT_METRICS = {
    "raw_minimum_distance_angstrom",
    "minimum_vdw_surface_gap_angstrom",
    "minimum_vdw_ratio",
    "sphere_overlap_proxy_angstrom3",
    "pocket_escape_angstrom",
}


@pytest.fixture
def secure_artifact_dir() -> object:
    with tempfile.TemporaryDirectory(
        prefix="engine-v2-performance-test.", dir="/tmp"
    ) as value:
        path = Path(value)
        path.chmod(0o700)
        yield path


def _as_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    document = getattr(value, "document", None)
    if isinstance(document, Mapping):
        return dict(document)
    method = getattr(value, "to_dict", None)
    if callable(method):
        result = method()
        assert isinstance(result, Mapping)
        return dict(result)
    raise AssertionError(f"{type(value).__name__} has no mapping projection")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _fixture_id(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        result = value.get("fixture_id")
    else:
        result = getattr(value, "fixture_id", None)
    assert isinstance(result, str)
    return result


def _fixture_payload_without_identity(fixture: object) -> tuple[dict[str, Any], str]:
    payload = _as_dict(fixture)
    identity = getattr(fixture, "input_sha256", None)
    assert isinstance(identity, str) and len(identity) == 64
    return payload, identity


def _metrics(value: object) -> dict[str, Any]:
    if all(hasattr(value, key) for key in _INTEGER_METRICS | _FLOAT_METRICS):
        return {
            key: getattr(value, key) for key in _INTEGER_METRICS | _FLOAT_METRICS
        }
    payload = _as_dict(value)
    if isinstance(payload.get("metrics"), Mapping):
        payload = dict(payload["metrics"])
    return {key: payload[key] for key in _INTEGER_METRICS | _FLOAT_METRICS}


def _parity_passed(value: object) -> bool:
    if isinstance(value, bool):
        return value
    passed = getattr(value, "passed", None)
    if type(passed) is bool:
        return passed
    payload = _as_dict(value)
    for key in ("passed", "parity_passed", "exact_parity_passed"):
        if key in payload:
            assert isinstance(payload[key], bool)
            return payload[key]
    raise AssertionError("parity result has no pass/fail field")


def _artifact_document(value: object) -> dict[str, Any]:
    for name in ("artifact_document", "document", "to_dict"):
        member = getattr(value, name, None)
        result = member() if callable(member) else member
        if isinstance(result, Mapping):
            return copy.deepcopy(dict(result))
    raise AssertionError("live result has no artifact document")


def _canonical_document_bytes(document: Mapping[str, Any]) -> bytes:
    return _canonical_bytes(document) + b"\n"


def _reseal_artifact(document: dict[str, Any]) -> None:
    projection = {key: value for key, value in document.items() if key != "receipt_sha256"}
    document["receipt_sha256"] = _sha256(projection)


def _structural_complete_source_bindings() -> dict[str, object]:
    paths = {
        "performance_source_sha256": _REPO_ROOT
        / "betelgeuze_engine_v2/docking/performance_sidecar.py",
        "geometric_source_sha256": _REPO_ROOT
        / "betelgeuze_engine_v2/docking/geometric_admission_v2.py",
        "mixed64_source_sha256": _REPO_ROOT
        / "betelgeuze_engine_v2/docking/mixed64_allocation.py",
        "rust_source_sha256": _REPO_ROOT / "rust_engine_v2/src/lib.rs",
        "cargo_lock_sha256": _REPO_ROOT / "rust_engine_v2/Cargo.lock",
        "cargo_manifest_sha256": _REPO_ROOT / "rust_engine_v2/Cargo.toml",
        "native_pyproject_sha256": _REPO_ROOT / "rust_engine_v2/pyproject.toml",
        "rust_build_script_sha256": _REPO_ROOT / "rust_engine_v2/build.rs",
        "native_build_wrapper_sha256": _REPO_ROOT
        / "tools/build_engine_v2_native_wheel.py",
        "qualification_bootstrap_sha256": _REPO_ROOT
        / "tools/run_engine_v2_cpu_performance_qualification.py",
    }
    digests = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    }
    info = dict(performance_sidecar._NATIVE_BUILD_INFO_STATIC)
    info.update(
        {
            "cargo_lock_sha256": digests["cargo_lock_sha256"],
            "cargo_manifest_sha256": digests["cargo_manifest_sha256"],
            "native_pyproject_sha256": digests["native_pyproject_sha256"],
            "rust_lib_sha256": digests["rust_source_sha256"],
            "build_script_sha256": digests["rust_build_script_sha256"],
            "native_build_wrapper_sha256": digests[
                "native_build_wrapper_sha256"
            ],
            "rustc_executable_sha256": "a" * 64,
        }
    )
    native_sha = "b" * 64
    runtime_projection = {
        "performance_source_sha256": digests["performance_source_sha256"],
        "geometric_source_sha256": digests["geometric_source_sha256"],
        "mixed64_source_sha256": digests["mixed64_source_sha256"],
        "native_extension_sha256": native_sha,
        "native_build_info": info,
        "qualification_bootstrap_sha256": digests[
            "qualification_bootstrap_sha256"
        ],
        "python_runtime": copy.deepcopy(
            dict(performance_sidecar._QUALIFIED_PYTHON_RUNTIME)
        ),
    }
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "schema_id": "betelgeuze.engine_v2_geometric_kernel_source_bindings/2.0.0",
        "source_commit": commit,
        "source_tree_clean": True,
        "python_runtime": copy.deepcopy(
            dict(performance_sidecar._QUALIFIED_PYTHON_RUNTIME)
        ),
        **digests,
        "native_extension_sha256": native_sha,
        "native_extension_filename": (
            "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so"
        ),
        "native_build_info": info,
        "child_runtime_binding_sha256": _sha256(runtime_projection),
        "child_bootstrap_import_paths": [
            str(_REPO_ROOT),
            "/tmp/qualified-venv/lib/python3.10/site-packages",
        ],
        "child_bootstrap_import_paths_sha256": _sha256(
            [
                str(_REPO_ROOT),
                "/tmp/qualified-venv/lib/python3.10/site-packages",
            ]
        ),
        "fallback_allowed": False,
    }


def _timing_transcript(
    profile: performance_sidecar.CPUPerformanceProfileV2,
    *,
    wall_ns: Mapping[str, tuple[int, int]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in profile.fixtures:
        output = normalize_python_geometric_output(
            generate_synthetic_geometric_fixture(spec.fixture_id)
        ).to_dict()
        baseline_wall, native_wall = wall_ns[spec.fixture_id]
        for phase, count in (
            ("warmup", profile.warmup_count),
            ("sample", profile.sample_count),
        ):
            for _index in range(count):
                for role, duration in (
                    ("python_reference", baseline_wall),
                    ("rust_cpu", native_wall),
                ):
                    rows.append(
                        {
                            "fixture_id": spec.fixture_id,
                            "phase": phase,
                            "role": role,
                            "wall_duration_ns": duration,
                            "process_cpu_duration_ns": duration,
                            "parent_observed_max_vmhwm_kib": 1024,
                            "output": copy.deepcopy(output),
                        }
                    )
    return rows


def _blocked_live_result(monkeypatch: pytest.MonkeyPatch) -> LiveCPUPerformanceRunResult:
    """Obtain a real runtime-sealed, pre-measurement result without timing native work."""

    host_type = performance_sidecar.HostExecutionContextV2
    blocked_host = host_type(
        cpu_model="unit-test-unqualified-host",
        boost_disabled=False,
        available_cpu_affinity=(),
        platform_system="Linux",
        platform_machine="x86_64",
        byteorder="little",
        parent_pid=performance_sidecar.os.getpid(),
        parent_os_task_count=1,
        qualified=False,
        blockers=(
            "cpu_model_not_qualified",
            "cpu_boost_not_disabled",
            "authoritative_cpu_not_available",
        ),
    )
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        lambda: blocked_host,
    )
    monkeypatch.setattr(
        performance_sidecar,
        "_derive_source_bindings",
        lambda: (_ for _ in ()).throw(
            CPUPerformanceError("source_tree_not_clean")
        ),
    )
    monkeypatch.setattr(
        performance_sidecar,
        "_launch_sealed_child",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("preflight blocker must prevent child launch")
        ),
    )
    result = run_sealed_local_performance_runner()
    assert isinstance(result, LiveCPUPerformanceRunResult)
    return result


def _qualified_test_host() -> performance_sidecar.HostExecutionContextV2:
    return performance_sidecar.HostExecutionContextV2(
        cpu_model=performance_sidecar.CPU_MODEL_EXACT,
        boost_disabled=True,
        available_cpu_affinity=performance_sidecar.AUTHORITATIVE_CPU_AFFINITY,
        platform_system="Linux",
        platform_machine="x86_64",
        byteorder="little",
        parent_pid=os.getpid(),
        parent_os_task_count=1,
        qualified=True,
        blockers=(),
    )


def test_frozen_fixture_generation_is_deterministic_and_sha_bound() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    fixture_ids = tuple(_fixture_id(row) for row in FROZEN_SYNTHETIC_FIXTURES)

    assert len(fixture_ids) == len(set(fixture_ids))
    assert {"small", "medium", "large"}.issubset(fixture_ids)
    for fixture_id in fixture_ids:
        first = generate_synthetic_geometric_fixture(fixture_id)
        second = generate_synthetic_geometric_fixture(fixture_id)
        first_payload, first_sha256 = _fixture_payload_without_identity(first)
        second_payload, second_sha256 = _fixture_payload_without_identity(second)

        assert first_payload == second_payload
        assert first_sha256 == second_sha256 == _sha256(first_payload)
        assert first_sha256 == profile.expected_input_sha256s[fixture_id]
        assert first_payload["fixture_id"] == fixture_id


def test_count_preserving_fixture_mutation_changes_exact_input_sha() -> None:
    fixture = generate_synthetic_geometric_fixture("small")
    payload, input_sha256 = _fixture_payload_without_identity(fixture)
    changed = copy.deepcopy(payload)
    coordinates = changed["ligand_coordinates_binary64_hex"]
    assert isinstance(coordinates, list) and coordinates
    coordinates[0][0] = math.nextafter(
        float.fromhex(coordinates[0][0]), math.inf
    ).hex()

    assert len(changed["ligand_coordinates_binary64_hex"]) == len(
        payload["ligand_coordinates_binary64_hex"]
    )
    assert len(changed["receptor_coordinates_binary64_hex"]) == len(
        payload["receptor_coordinates_binary64_hex"]
    )
    assert _sha256(changed) != input_sha256


def test_unknown_fixture_id_is_rejected_before_work() -> None:
    with pytest.raises(CPUPerformanceError, match="fixture"):
        generate_synthetic_geometric_fixture("../molecular-case")


def test_python_reference_runs_actual_geometric_metrics_deterministically() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    saw_penetration = False
    saw_escape = False
    for row in FROZEN_SYNTHETIC_FIXTURES:
        fixture = generate_synthetic_geometric_fixture(_fixture_id(row))
        fixture_payload, _ = _fixture_payload_without_identity(fixture)
        first_output = normalize_python_geometric_output(fixture)
        second_output = normalize_python_geometric_output(fixture)
        first = _metrics(first_output)
        second = _metrics(second_output)

        assert first == second
        assert (
            first_output.output_sha256
            == second_output.output_sha256
            == profile.expected_python_output_sha256s[fixture.fixture_id]
        )
        ligand_count = fixture_payload["ligand_atom_count"]
        receptor_count = fixture_payload["receptor_atom_count"]
        assert first["ligand_atom_count"] == ligand_count
        assert first["receptor_atom_count"] == receptor_count
        assert first["exact_pair_count"] == ligand_count * receptor_count
        assert 0 <= first["penetration_pair_count"] <= first["exact_pair_count"]
        assert (
            0
            <= first["unique_ligand_heavy_atom_penetration_count"]
            <= first["unique_ligand_penetration_atom_count"]
            <= ligand_count
        )
        assert all(math.isfinite(first[key]) for key in _FLOAT_METRICS)
        assert first["sphere_overlap_proxy_angstrom3"] >= 0.0
        assert first["pocket_escape_angstrom"] >= 0.0
        saw_penetration |= first["penetration_pair_count"] > 0
        saw_escape |= first["pocket_escape_angstrom"] > 0.0

    assert saw_penetration
    assert saw_escape

    small = normalize_python_geometric_output(
        generate_synthetic_geometric_fixture("small")
    )
    medium = normalize_python_geometric_output(
        generate_synthetic_geometric_fixture("medium")
    )
    large = normalize_python_geometric_output(
        generate_synthetic_geometric_fixture("large")
    )
    assert (small.decision, small.penetration_pair_count, small.pocket_escape_angstrom) == (
        "accepted",
        0,
        5.0,
    )
    assert medium.decision == "accepted"
    assert medium.minimum_vdw_ratio == 0.55
    assert medium.penetration_pair_count == 1
    assert medium.pocket_escape_angstrom == 0.0
    assert large.decision == "rejected"
    assert large.penetration_pair_count > 1
    assert large.pocket_escape_angstrom == 5.0


def test_geometric_parity_requires_exact_integer_metrics() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    reference = normalize_python_geometric_output(
        generate_synthetic_geometric_fixture("small")
    )
    assert _parity_passed(compare_geometric_outputs(reference, reference, profile))

    for field in _INTEGER_METRICS:
        changed = replace(reference, **{field: getattr(reference, field) + 1})
        result = compare_geometric_outputs(reference, changed, profile)
        assert not _parity_passed(result), field


def test_geometric_parity_requires_exact_decision() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    output = normalize_python_geometric_output(
        generate_synthetic_geometric_fixture("small")
    )
    changed = replace(
        output,
        minimum_vdw_ratio=(1.0 if output.decision == "rejected" else 0.0),
        decision=("accepted" if output.decision == "rejected" else "rejected"),
    )

    comparison = compare_geometric_outputs(output, changed, profile)
    assert not comparison.passed
    assert "geometric_decision_mismatch" in comparison.blockers


def test_geometric_parity_uses_abs_and_ulp_tolerances() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    reference = normalize_python_geometric_output(
        generate_synthetic_geometric_fixture("small")
    )

    for field in _FLOAT_METRICS:
        adjacent = replace(
            reference,
            **{field: math.nextafter(getattr(reference, field), math.inf)},
        )
        assert _parity_passed(
            compare_geometric_outputs(reference, adjacent, profile)
        ), field

        scale = max(1.0, abs(getattr(reference, field)))
        outside = replace(
            reference,
            **{field: getattr(reference, field) + scale * 1.0e-4},
        )
        assert not _parity_passed(
            compare_geometric_outputs(reference, outside, profile)
        ), field


@pytest.mark.parametrize("bad", (math.nan, math.inf, -math.inf, True, "0.0"))
def test_geometric_parity_rejects_nonfinite_or_wrong_type_values(bad: object) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    reference = normalize_python_geometric_output(
        generate_synthetic_geometric_fixture("small")
    )

    with pytest.raises(CPUPerformanceError):
        changed = replace(reference, raw_minimum_distance_angstrom=bad)
        compare_geometric_outputs(reference, changed, profile)


def test_profile_is_canonical_frozen_and_all_authority_false() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    payload = _as_dict(profile)

    assert payload["schema_id"].endswith("/2.0.0")
    assert payload["restrictions"]["contains_molecular_cases"] is False
    assert payload["restrictions"]["actual_molecular_execution_allowed"] is False
    assert payload["restrictions"]["reservation_allowed"] is False
    assert payload["authority"]
    assert all(value is False for value in payload["authority"].values())


def test_offline_verification_never_mints_current_live_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    live = _blocked_live_result(monkeypatch)
    document = _artifact_document(live)
    offline = require_cpu_performance_artifact_document(document, profile=profile)

    assert isinstance(offline, VerifiedOfflineCPUPerformanceArtifact)
    assert live.live_run_capability is True
    assert live.offline_replay_only is False
    assert offline.live_run_capability is False
    assert offline.local_numeric_gate_eligible is False
    assert offline.offline_replay_only is True
    assert offline.recorded_numeric_gate_passed is live.recorded_numeric_gate_passed


def test_live_result_cannot_be_forged_from_an_offline_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    document = _artifact_document(_blocked_live_result(monkeypatch))
    offline = require_cpu_performance_artifact_document(document, profile=profile)

    assert not isinstance(offline, LiveCPUPerformanceRunResult)
    with pytest.raises(CPUPerformanceError, match="cannot be constructed"):
        LiveCPUPerformanceRunResult(document, _seal=object())


def test_profile_live_and_offline_documents_are_defensive_copies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    original_profile_id = profile.document["profile_id"]
    exposed_profile = profile.document
    exposed_profile["profile_id"] = "mutated"
    exposed_profile["authority"]["molecular_execution_authorized"] = True
    assert profile.document["profile_id"] == original_profile_id
    assert all(value is False for value in profile.document["authority"].values())

    live = _blocked_live_result(monkeypatch)
    original_live = live.artifact_document()
    exposed_live = live.artifact_document()
    exposed_live["authority"]["molecular_execution_authorized"] = True
    exposed_live["blockers"].clear()
    assert live.artifact_document() == original_live
    with pytest.raises(CPUPerformanceError, match="immutable"):
        live._artifact_bytes = b"{}"  # type: ignore[misc]

    offline = require_cpu_performance_artifact_document(original_live, profile=profile)
    original_offline = offline.document
    exposed_offline = offline.document
    exposed_offline["authority"]["molecular_execution_authorized"] = True
    exposed_offline["blockers"].clear()
    assert offline.document == original_offline
    assert offline.qualification_authority is False


def test_child_resource_limits_accept_zero_core_in_disposable_process() -> None:
    script = """
import resource
from betelgeuze_engine_v2.docking.performance_sidecar import _apply_child_resource_limits
_apply_child_resource_limits()
assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
print("bounded")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "bounded\n"


def test_runner_discards_all_rows_when_source_binding_changes_postflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = {"binding": "first"}
    second = {"binding": "second"}
    calls = iter((first, second))
    schedule = [
        {
            "global_launch_ordinal": 0,
            "fixture_id": "small",
            "phase": "warmup",
            "pair_index": 0,
            "role": "python_reference",
        }
    ]
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        _qualified_test_host,
    )
    monkeypatch.setattr(
        performance_sidecar, "_derive_source_bindings", lambda: next(calls)
    )
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: schedule
    )
    monkeypatch.setattr(performance_sidecar, "_launch_sealed_child", lambda **_kwargs: {})

    result = run_sealed_local_performance_runner()
    document = result.artifact_document()
    assert result.recorded_decision == "BLOCKED"
    assert document["transcript"] == []
    assert document["source_bindings"] == {}
    assert "source_binding_changed_during_measurement" in result.blockers
    assert "sealed_measurement_discarded_after_source_drift" in result.blockers


def test_runner_discards_all_rows_when_host_context_changes_postflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_host = _qualified_test_host()
    changed_host = replace(
        initial_host,
        boost_disabled=False,
        qualified=False,
        blockers=("cpu_boost_not_disabled",),
    )
    hosts = iter((initial_host, changed_host))
    binding = {"binding": "fixed"}
    schedule = [
        {
            "global_launch_ordinal": 0,
            "fixture_id": "small",
            "phase": "warmup",
            "pair_index": 0,
            "role": "python_reference",
        }
    ]
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        lambda: next(hosts),
    )
    monkeypatch.setattr(
        performance_sidecar, "_derive_source_bindings", lambda: binding
    )
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: schedule
    )
    monkeypatch.setattr(performance_sidecar, "_launch_sealed_child", lambda **_kwargs: {})
    monkeypatch.setattr(
        performance_sidecar,
        "_validate_transcript_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("validation must not start after host drift")
        ),
    )

    result = run_sealed_local_performance_runner()
    document = result.artifact_document()
    assert result.recorded_decision == "BLOCKED"
    assert document["transcript"] == []
    assert document["source_bindings"] == {}
    assert "host_context_changed_during_measurement" in result.blockers
    assert "sealed_measurement_discarded_after_host_drift" in result.blockers


def test_runner_caps_each_child_by_the_remaining_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_timeouts: list[float] = []
    schedule = [
        {
            "global_launch_ordinal": 0,
            "fixture_id": "small",
            "phase": "warmup",
            "pair_index": 0,
            "role": "python_reference",
        }
    ]
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        _qualified_test_host,
    )
    monkeypatch.setattr(
        performance_sidecar, "_derive_source_bindings", lambda: {"binding": "fixed"}
    )
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: schedule
    )
    monkeypatch.setattr(
        performance_sidecar.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )
    monkeypatch.setattr(
        performance_sidecar.CPUPerformanceProfileV2,
        "child_timeout_seconds",
        property(lambda _self: 30),
    )

    def fail_after_recording(**kwargs: object) -> Mapping[str, Any]:
        observed_timeouts.append(float(kwargs["timeout_seconds"]))
        raise CPUPerformanceError("synthetic timeout sentinel")

    monkeypatch.setattr(
        performance_sidecar, "_launch_sealed_child", fail_after_recording
    )
    result = run_sealed_local_performance_runner()
    assert result.recorded_decision == "BLOCKED"
    assert len(observed_timeouts) == 1
    assert 0.0 < observed_timeouts[0] <= 1.0


def test_runner_blocks_and_discards_semantically_invalid_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = {"binding": "fixed"}
    schedule = [
        {
            "global_launch_ordinal": 0,
            "fixture_id": "small",
            "phase": "warmup",
            "pair_index": 0,
            "role": "python_reference",
        }
    ]
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        _qualified_test_host,
    )
    monkeypatch.setattr(
        performance_sidecar, "_derive_source_bindings", lambda: binding
    )
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: schedule
    )
    monkeypatch.setattr(performance_sidecar, "_launch_sealed_child", lambda **_kwargs: {})
    monkeypatch.setattr(
        performance_sidecar,
        "_validate_transcript_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CPUPerformanceError("native geometric output parity failed")
        ),
    )

    result = run_sealed_local_performance_runner()
    assert result.recorded_decision == "BLOCKED"
    assert result.artifact_document()["transcript"] == []
    assert any("parity failed" in blocker for blocker in result.blockers)
    assert "sealed_measurement_discarded_after_validation_failure" in result.blockers


def test_slow_launch_cannot_extend_the_absolute_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = {"binding": "fixed"}
    schedule = [
        {
            "global_launch_ordinal": 0,
            "fixture_id": "small",
            "phase": "warmup",
            "pair_index": 0,
            "role": "python_reference",
        }
    ]
    clock = iter((100.0, 100.1, 100.2, 100.3, 100.4, 100.5, 101.1))
    observed_deadlines: list[float] = []
    monkeypatch.setattr(performance_sidecar.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        _qualified_test_host,
    )
    monkeypatch.setattr(
        performance_sidecar, "_derive_source_bindings", lambda: binding
    )
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: schedule
    )
    monkeypatch.setattr(
        performance_sidecar.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )

    def slow_launch(**kwargs: object) -> Mapping[str, Any]:
        observed_deadlines.append(float(kwargs["absolute_deadline_monotonic"]))
        return {}

    monkeypatch.setattr(performance_sidecar, "_launch_sealed_child", slow_launch)
    result = run_sealed_local_performance_runner()
    assert observed_deadlines == [101.0]
    assert result.recorded_decision == "BLOCKED"
    assert "sealed_runner_total_timeout" in result.blockers
    assert result.artifact_document()["transcript"] == []


def test_deadline_clock_is_sampled_before_profile_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    events: list[str] = []
    blocked_host = replace(
        _qualified_test_host(),
        qualified=False,
        blockers=("synthetic_preflight_blocker",),
    )

    def clock() -> float:
        events.append("clock")
        return 100.0

    def load(_path: Path) -> performance_sidecar.CPUPerformanceProfileV2:
        events.append("load")
        return profile

    monkeypatch.setattr(performance_sidecar.time, "monotonic", clock)
    monkeypatch.setattr(performance_sidecar, "load_cpu_performance_profile", load)
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        lambda: blocked_host,
    )
    result = run_sealed_local_performance_runner()

    assert events[:2] == ["clock", "load"]
    assert result.recorded_decision == "BLOCKED"


def test_profile_load_time_consumes_total_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    clock = iter((100.0, 101.0))
    monkeypatch.setattr(performance_sidecar.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        performance_sidecar,
        "load_cpu_performance_profile",
        lambda _path: profile,
    )
    monkeypatch.setattr(
        performance_sidecar.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        lambda: (_ for _ in ()).throw(AssertionError("host phase must not start")),
    )
    monkeypatch.setattr(
        performance_sidecar,
        "_derive_source_bindings",
        lambda: (_ for _ in ()).throw(AssertionError("source phase must not start")),
    )

    result = run_sealed_local_performance_runner()
    assert result.recorded_decision == "BLOCKED"
    assert "sealed_runner_total_timeout" in result.blockers


def test_expired_before_postflight_skips_second_source_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding_calls = 0
    clock_calls = 0

    def clock() -> float:
        nonlocal clock_calls
        clock_calls += 1
        return 100.0 if clock_calls <= 5 else 101.0

    def binding() -> Mapping[str, object]:
        nonlocal binding_calls
        binding_calls += 1
        return {"binding": "fixed"}

    monkeypatch.setattr(performance_sidecar.time, "monotonic", clock)
    monkeypatch.setattr(
        performance_sidecar.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        _qualified_test_host,
    )
    monkeypatch.setattr(performance_sidecar, "_derive_source_bindings", binding)
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: []
    )
    monkeypatch.setattr(
        performance_sidecar,
        "_validate_transcript_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("validation must not start after timeout")
        ),
    )

    result = run_sealed_local_performance_runner()
    assert binding_calls == 1
    assert result.recorded_decision == "BLOCKED"
    assert "sealed_runner_total_timeout" in result.blockers


def test_validation_overrun_discards_complete_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    schedule = [
        {
            "global_launch_ordinal": 0,
            "fixture_id": "small",
            "phase": "warmup",
            "pair_index": 0,
            "role": "python_reference",
        }
    ]
    monkeypatch.setattr(performance_sidecar.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        performance_sidecar.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        _qualified_test_host,
    )
    monkeypatch.setattr(
        performance_sidecar, "_derive_source_bindings", lambda: {"binding": "fixed"}
    )
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: schedule
    )
    monkeypatch.setattr(performance_sidecar, "_launch_sealed_child", lambda **_kw: {})

    def validate(*_args: object, **_kwargs: object) -> tuple[Mapping[str, Any], ...]:
        now[0] = 101.0
        return ({},)

    monkeypatch.setattr(performance_sidecar, "_validate_transcript_rows", validate)
    monkeypatch.setattr(
        performance_sidecar,
        "_derive_fixture_results",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("result derivation must not start after timeout")
        ),
    )

    result = run_sealed_local_performance_runner()
    assert result.recorded_decision == "BLOCKED"
    assert result.artifact_document()["transcript"] == []
    assert "sealed_runner_total_timeout" in result.blockers


def test_projection_overrun_prevents_complete_result_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    complete_issue_calls = 0
    real_projection = performance_sidecar._artifact_projection
    real_issue = performance_sidecar._issue_live_result
    monkeypatch.setattr(performance_sidecar.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        performance_sidecar.CPUPerformanceProfileV2,
        "total_timeout_seconds",
        property(lambda _self: 1),
    )
    monkeypatch.setattr(
        performance_sidecar,
        "derive_actual_host_execution_context",
        _qualified_test_host,
    )
    monkeypatch.setattr(
        performance_sidecar, "_derive_source_bindings", lambda: {"binding": "fixed"}
    )
    monkeypatch.setattr(
        performance_sidecar, "_expected_launch_schedule", lambda _profile: []
    )
    monkeypatch.setattr(
        performance_sidecar, "_validate_transcript_rows", lambda *_a, **_kw: ()
    )
    monkeypatch.setattr(
        performance_sidecar,
        "_derive_fixture_results",
        lambda *_a, **_kw: ((), True, ()),
    )

    def projection(**kwargs: object) -> dict[str, object]:
        result = real_projection(**kwargs)  # type: ignore[arg-type]
        if kwargs["status"] == "complete":
            now[0] = 101.0
        return result

    def issue(
        projection_value: Mapping[str, object],
        *,
        profile: performance_sidecar.CPUPerformanceProfileV2,
    ) -> LiveCPUPerformanceRunResult:
        nonlocal complete_issue_calls
        if projection_value["status"] == "complete":
            complete_issue_calls += 1
        return real_issue(projection_value, profile=profile)

    monkeypatch.setattr(performance_sidecar, "_artifact_projection", projection)
    monkeypatch.setattr(performance_sidecar, "_issue_live_result", issue)

    result = run_sealed_local_performance_runner()
    assert complete_issue_calls == 0
    assert result.recorded_decision == "BLOCKED"
    assert "sealed_runner_total_timeout" in result.blockers


def test_launch_does_not_spawn_when_bootstrap_consumes_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]

    def bootstrap() -> tuple[str, ...]:
        now[0] = 101.0
        return (str(_REPO_ROOT), "/tmp/qualified-site-packages")

    monkeypatch.setattr(performance_sidecar.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(performance_sidecar, "_child_bootstrap_import_paths", bootstrap)
    monkeypatch.setattr(
        performance_sidecar.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Popen must not run at the exact deadline")
        ),
    )

    with pytest.raises(CPUPerformanceError, match="before process start"):
        performance_sidecar._launch_sealed_child(
            run_nonce="a" * 64,
            global_launch_ordinal=0,
            fixture_id="small",
            phase="warmup",
            pair_index=0,
            role="python_reference",
            timeout_seconds=1.0,
            absolute_deadline_monotonic=101.0,
        )


def test_nearest_rank_and_exact_speed_gate_boundaries() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    assert performance_sidecar._nearest_rank(
        tuple(range(1, 31)), numerator=95, denominator=100
    ) == 29
    exact_boundary = {
        "small": (100_000, 105_000),
        "medium": (150_000, 100_000),
        "large": (150_000, 100_000),
    }
    results, passed, blockers = performance_sidecar._derive_fixture_results(
        _timing_transcript(profile, wall_ns=exact_boundary), profile
    )
    assert passed is True
    assert blockers == ()
    assert all(row["speed_gate_passed"] is True for row in results)


def test_warmup_timings_are_excluded_from_all_numeric_speed_gates() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    walls = {
        "small": (100_000, 105_000),
        "medium": (150_000, 100_000),
        "large": (150_000, 100_000),
    }
    transcript = _timing_transcript(profile, wall_ns=walls)
    baseline = performance_sidecar._derive_fixture_results(transcript, profile)
    for row in transcript:
        if row["phase"] == "warmup":
            row["wall_duration_ns"] = 30_000_000_000
            row["process_cpu_duration_ns"] = 30_000_000_000
    changed = performance_sidecar._derive_fixture_results(transcript, profile)

    assert changed == baseline


def test_parent_task_count_above_one_is_a_terminal_host_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(performance_sidecar, "_cpu_model", lambda: performance_sidecar.CPU_MODEL_EXACT)
    monkeypatch.setattr(performance_sidecar, "_boost_disabled", lambda: True)
    monkeypatch.setattr(
        performance_sidecar.os,
        "sched_getaffinity",
        lambda _pid: set(performance_sidecar.AUTHORITATIVE_CPU_AFFINITY),
    )
    monkeypatch.setattr(performance_sidecar, "_os_task_count", lambda _pid: 2)

    host = performance_sidecar.derive_actual_host_execution_context()
    assert host.parent_os_task_count == 2
    assert host.qualified is False
    assert "parent_os_task_count_not_one" in host.blockers


def test_runtime_payload_manifest_detects_added_files_and_forbidden_bytecode(
    tmp_path: Path,
) -> None:
    numpy_root = tmp_path / "numpy"
    libraries_root = tmp_path / "numpy.libs"
    numpy_root.mkdir()
    libraries_root.mkdir()
    (numpy_root / "__init__.py").write_bytes(b"version = 'frozen'\n")
    (libraries_root / "libfrozen.so").write_bytes(b"synthetic-library")
    (numpy_root / "__init__.py").chmod(0o644)
    (libraries_root / "libfrozen.so").chmod(0o644)

    first = performance_sidecar._runtime_directory_manifest(
        tmp_path,
        top_level_names=("numpy", "numpy.libs"),
        schema_id="synthetic.manifest/1",
        reject_bytecode=True,
        allow_file_symlinks=False,
        name="synthetic runtime",
    )
    second = performance_sidecar._runtime_directory_manifest(
        tmp_path,
        top_level_names=("numpy", "numpy.libs"),
        schema_id="synthetic.manifest/1",
        reject_bytecode=True,
        allow_file_symlinks=False,
        name="synthetic runtime",
    )
    assert first == second
    assert first["file_count"] == 2

    (numpy_root / "shadow.py").write_bytes(b"raise RuntimeError\n")
    (numpy_root / "shadow.py").chmod(0o644)
    added = performance_sidecar._runtime_directory_manifest(
        tmp_path,
        top_level_names=("numpy", "numpy.libs"),
        schema_id="synthetic.manifest/1",
        reject_bytecode=True,
        allow_file_symlinks=False,
        name="synthetic runtime",
    )
    assert added["sha256"] != first["sha256"]
    cache = numpy_root / "__pycache__"
    cache.mkdir()
    cache.chmod(0o755)
    (cache / "shadow.cpython-310.pyc").write_bytes(b"not-bytecode")
    (cache / "shadow.cpython-310.pyc").chmod(0o644)
    with pytest.raises(CPUPerformanceError, match="bytecode cache"):
        performance_sidecar._runtime_directory_manifest(
            tmp_path,
            top_level_names=("numpy", "numpy.libs"),
            schema_id="synthetic.manifest/1",
            reject_bytecode=True,
            allow_file_symlinks=False,
            name="synthetic runtime",
        )


def test_stdlib_zip_must_be_absent_even_for_a_symlink(tmp_path: Path) -> None:
    candidate = tmp_path / "python310.zip"
    performance_sidecar._require_path_absent(candidate, name="stdlib zip")
    candidate.symlink_to(tmp_path / "missing-target")
    with pytest.raises(CPUPerformanceError, match="must be absent"):
        performance_sidecar._require_path_absent(candidate, name="stdlib zip")


def test_numpy_record_manifest_covers_every_present_and_typed_absent_file(
    tmp_path: Path,
) -> None:
    venv = tmp_path / "venv"
    site = venv / "lib/python3.10/site-packages"
    numpy_root = site / "numpy"
    libraries_root = site / "numpy.libs"
    dist_info = site / performance_sidecar._NUMPY_DIST_INFO_DIRECTORY
    bin_root = venv / "bin"
    for directory in (
        venv,
        venv / "lib",
        venv / "lib/python3.10",
        site,
        numpy_root,
        libraries_root,
        dist_info,
        bin_root,
    ):
        directory.mkdir(exist_ok=True)
        directory.chmod(0o755)

    payloads = {
        "numpy/__init__.py": b"version = 'frozen'\n",
        "numpy.libs/libfrozen.so": b"synthetic-library",
        performance_sidecar._NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY: b"#!/usr/bin/python3.10\n",
    }
    targets = {
        "numpy/__init__.py": numpy_root / "__init__.py",
        "numpy.libs/libfrozen.so": libraries_root / "libfrozen.so",
        performance_sidecar._NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY: bin_root / "f2py",
    }
    for path_text, raw in payloads.items():
        targets[path_text].write_bytes(raw)
        targets[path_text].chmod(
            0o755
            if path_text == performance_sidecar._NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY
            else 0o644
        )

    def record_hash(raw: bytes) -> str:
        encoded = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        return "sha256=" + encoded.rstrip(b"=").decode("ascii")

    rows = [
        f"{path_text},{record_hash(raw)},{len(raw)}"
        for path_text, raw in payloads.items()
    ]
    rows.extend(
        (
            f"{performance_sidecar._NUMPY_RECORD_TYPED_ABSENT_PATHS[0]},{record_hash(b'absent')},6",
            f"{performance_sidecar._NUMPY_RECORD_SELF_PATH},,",
        )
    )
    record = dist_info / "RECORD"
    record.write_bytes(("\r\n".join(rows) + "\r\n").encode("ascii"))
    record.chmod(0o644)

    manifest = performance_sidecar._numpy_installed_files_manifest(
        virtual_environment_root=venv,
        site_packages=site,
    )
    assert manifest["record_row_count"] == 5
    assert manifest["record_present_file_count"] == 4
    assert manifest["file_count"] == 4
    assert manifest["record_typed_absent_paths"] == list(
        performance_sidecar._NUMPY_RECORD_TYPED_ABSENT_PATHS
    )
    assert manifest["console_script_sha256"] == hashlib.sha256(
        payloads[performance_sidecar._NUMPY_RECORD_CONSOLE_SCRIPT_ENTRY]
    ).hexdigest()

    extra = dist_info / "unrecorded"
    extra.write_bytes(b"not-recorded")
    extra.chmod(0o644)
    with pytest.raises(CPUPerformanceError, match="exactly enumerate"):
        performance_sidecar._numpy_installed_files_manifest(
            virtual_environment_root=venv,
            site_packages=site,
        )


def test_qualified_site_packages_inventory_is_exact_and_owner_controlled(
    tmp_path: Path,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir(mode=0o755)
    site.chmod(0o755)
    for name in performance_sidecar._QUALIFIED_SITE_PACKAGES_TOP_LEVEL:
        path = site / name
        path.mkdir(mode=0o755)
        path.chmod(0o755)

    performance_sidecar._verify_qualified_site_packages_inventory(site)
    extra = site / "unqualified_dependency"
    extra.mkdir(mode=0o755)
    extra.chmod(0o755)
    with pytest.raises(CPUPerformanceError, match="inventory_changed"):
        performance_sidecar._verify_qualified_site_packages_inventory(site)


@pytest.mark.parametrize(
    ("fixture_id", "durations", "expected_blocker"),
    (
        (
            "small",
            (100_000, 105_001),
            "small_p95_regression_exceeds_5_percent",
        ),
        ("medium", (149_999, 100_000), "medium_p95_speedup_below_1_5x"),
        ("large", (149_999, 100_000), "large_p95_speedup_below_1_5x"),
    ),
)
def test_one_unit_beyond_a_speed_boundary_is_no_go(
    fixture_id: str,
    durations: tuple[int, int],
    expected_blocker: str,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    walls = {
        "small": (100_000, 105_000),
        "medium": (150_000, 100_000),
        "large": (150_000, 100_000),
    }
    walls[fixture_id] = durations
    results, passed, blockers = performance_sidecar._derive_fixture_results(
        _timing_transcript(profile, wall_ns=walls), profile
    )
    assert passed is False
    assert blockers == (f"{fixture_id}:{expected_blocker}",)
    result = next(row for row in results if row["fixture_id"] == fixture_id)
    assert result["parity_passed"] is True
    assert result["speed_gate_passed"] is False


def test_artifact_tamper_and_launch_order_drift_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    document = _artifact_document(_blocked_live_result(monkeypatch))

    authority = copy.deepcopy(document)
    authority["authority"][next(iter(authority["authority"]))] = True
    _reseal_artifact(authority)
    with pytest.raises(CPUPerformanceError, match="authority"):
        require_cpu_performance_artifact_document(authority, profile=profile)

    launch_order = copy.deepcopy(document)
    order = launch_order["measurement_contract"]["expected_launch_schedule"]
    assert len(order) > 1
    order[0], order[1] = order[1], order[0]
    _reseal_artifact(launch_order)
    with pytest.raises(CPUPerformanceError, match="measurement contract"):
        require_cpu_performance_artifact_document(launch_order, profile=profile)

    host = copy.deepcopy(document)
    host["host"]["qualified"] = True
    _reseal_artifact(host)
    with pytest.raises(CPUPerformanceError, match="qualification"):
        require_cpu_performance_artifact_document(host, profile=profile)


def test_complete_source_binding_rederives_every_source_and_runtime_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bindings = _structural_complete_source_bindings()
    monkeypatch.setattr(
        performance_sidecar,
        "_load_native_module",
        lambda: (_ for _ in ()).throw(
            CPUPerformanceError("native_geometric_kernel_unavailable")
        ),
    )
    verified = performance_sidecar._verify_source_bindings(bindings, complete=True)
    assert dict(verified) == bindings

    changed_source = copy.deepcopy(bindings)
    changed_source["geometric_source_sha256"] = "0" * 64
    with pytest.raises(CPUPerformanceError, match="source identity"):
        performance_sidecar._verify_source_bindings(changed_source, complete=True)

    changed_mixed64 = copy.deepcopy(bindings)
    changed_mixed64["mixed64_source_sha256"] = "0" * 64
    with pytest.raises(CPUPerformanceError, match="source identity"):
        performance_sidecar._verify_source_bindings(changed_mixed64, complete=True)

    changed_pyproject = copy.deepcopy(bindings)
    changed_pyproject["native_pyproject_sha256"] = "0" * 64
    with pytest.raises(CPUPerformanceError, match="source identity|pyproject"):
        performance_sidecar._verify_source_bindings(changed_pyproject, complete=True)

    changed_runtime = copy.deepcopy(bindings)
    changed_runtime["child_runtime_binding_sha256"] = "0" * 64
    with pytest.raises(CPUPerformanceError, match="runtime binding"):
        performance_sidecar._verify_source_bindings(changed_runtime, complete=True)

    changed_wrapper = copy.deepcopy(bindings)
    changed_wrapper["native_build_info"]["build_wrapper_control"] = (
        "direct_cargo_unattested"
    )
    with pytest.raises(CPUPerformanceError, match="build_info"):
        performance_sidecar._verify_source_bindings(changed_wrapper, complete=True)


def test_artifact_bytes_reject_duplicate_noncanonical_and_oversize_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    document = _artifact_document(_blocked_live_result(monkeypatch))
    canonical = _canonical_document_bytes(document)
    duplicate = canonical.replace(
        b"{",
        b'{"schema_id":"duplicate-forbidden",',
        1,
    )

    verified = require_cpu_performance_artifact_bytes(canonical, profile=profile)
    assert isinstance(verified, VerifiedOfflineCPUPerformanceArtifact)
    assert verified.offline_replay_only is True
    with pytest.raises(CPUPerformanceError, match="duplicate"):
        require_cpu_performance_artifact_bytes(duplicate, profile=profile)
    with pytest.raises(CPUPerformanceError, match="canonical"):
        require_cpu_performance_artifact_bytes(b" " + canonical, profile=profile)
    with pytest.raises(CPUPerformanceError, match="byte count|envelope|size"):
        require_cpu_performance_artifact_bytes(
            canonical + b" " * (16 * 1024 * 1024),
            profile=profile,
        )


def test_artifact_writer_is_no_clobber_and_rejects_symlinks(
    secure_artifact_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _blocked_live_result(monkeypatch)
    target = secure_artifact_dir / "qualification.json"

    write_cpu_performance_artifact(live, target)
    first = target.read_bytes()
    assert first.endswith(b"\n")
    offline = load_cpu_performance_artifact(
        target, profile=load_cpu_performance_profile(_PROFILE_PATH)
    )
    assert offline.offline_replay_only is True
    with pytest.raises(CPUPerformanceError, match="exist|replace|clobber"):
        write_cpu_performance_artifact(live, target)
    assert target.read_bytes() == first

    real = secure_artifact_dir / "real.json"
    real.write_bytes(b"sentinel")
    link = secure_artifact_dir / "link.json"
    link.symlink_to(real)
    with pytest.raises(CPUPerformanceError, match="symlink|regular|exist"):
        write_cpu_performance_artifact(live, link)
    assert real.read_bytes() == b"sentinel"


def test_artifact_writer_refuses_non_json_and_parent_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _blocked_live_result(monkeypatch)

    with pytest.raises(CPUPerformanceError, match="filename|json|path"):
        write_cpu_performance_artifact(live, tmp_path / "receipt.txt")
    with pytest.raises(CPUPerformanceError, match="path|parent|traversal"):
        write_cpu_performance_artifact(live, tmp_path / "nested" / "../escape.json")


def test_artifact_reader_rejects_hardlinks_and_writer_rejects_untrusted_parent(
    secure_artifact_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _blocked_live_result(monkeypatch)
    target = secure_artifact_dir / "qualification.json"
    write_cpu_performance_artifact(live, target)
    hardlink = secure_artifact_dir / "qualification-hardlink.json"
    os.link(target, hardlink)

    with pytest.raises(CPUPerformanceError, match="bounded regular file"):
        load_cpu_performance_artifact(
            target, profile=load_cpu_performance_profile(_PROFILE_PATH)
        )

    unsafe = secure_artifact_dir / "unsafe"
    unsafe.mkdir(mode=0o700)
    unsafe.chmod(stat.S_IRWXU | stat.S_IWGRP)
    try:
        with pytest.raises(CPUPerformanceError, match="owner-controlled"):
            write_cpu_performance_artifact(live, unsafe / "qualification.json")
    finally:
        unsafe.chmod(0o700)


def test_artifact_writer_binds_the_prevalidated_parent_inode(
    secure_artifact_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _blocked_live_result(monkeypatch)
    parent = secure_artifact_dir / "bound-parent"
    parent.mkdir(mode=0o700)
    displaced = secure_artifact_dir / "displaced-parent"
    original_open = performance_sidecar.os.open
    swapped = False

    def swapping_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if not swapped and dir_fd is None and Path(path) == parent:
            parent.rename(displaced)
            parent.mkdir(mode=0o700)
            swapped = True
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(performance_sidecar.os, "open", swapping_open)
    with pytest.raises(CPUPerformanceError, match="parent changed"):
        write_cpu_performance_artifact(live, parent / "qualification.json")
    assert swapped
    assert not (parent / "qualification.json").exists()
    assert not (displaced / "qualification.json").exists()


def test_artifact_writer_cleans_an_ambiguous_committed_link(
    secure_artifact_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _blocked_live_result(monkeypatch)
    target = secure_artifact_dir / "qualification.json"
    original_link = performance_sidecar.os.link

    def ambiguous_link(*args: object, **kwargs: object) -> None:
        original_link(*args, **kwargs)
        raise OSError("simulated ambiguous link commit")

    monkeypatch.setattr(performance_sidecar.os, "link", ambiguous_link)
    with pytest.raises(CPUPerformanceError, match="atomically"):
        write_cpu_performance_artifact(live, target)
    assert not target.exists()
    assert not tuple(secure_artifact_dir.glob(".qualification.json.tmp.*"))


def test_artifact_writer_does_not_delete_a_replacement_staging_name(
    secure_artifact_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _blocked_live_result(monkeypatch)
    target = secure_artifact_dir / "qualification.json"
    original_fsync = performance_sidecar.os.fsync
    replacement: Path | None = None

    def failing_fsync(descriptor: int) -> None:
        nonlocal replacement
        metadata = os.fstat(descriptor)
        if stat.S_ISREG(metadata.st_mode) and replacement is None:
            (staging,) = tuple(secure_artifact_dir.glob(".qualification.json.tmp.*"))
            staging.unlink()
            staging.write_bytes(b"replacement")
            staging.chmod(0o600)
            replacement = staging
            raise OSError("simulated staging fsync failure")
        original_fsync(descriptor)

    monkeypatch.setattr(performance_sidecar.os, "fsync", failing_fsync)
    with pytest.raises(OSError, match="fsync failure"):
        write_cpu_performance_artifact(live, target)
    assert replacement is not None
    assert replacement.read_bytes() == b"replacement"
    assert not target.exists()


def test_bounded_reader_rechecks_links_and_rejects_fifo_and_non_owner_mode(
    tmp_path: Path,
    secure_artifact_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b"{}\n")
    linked = tmp_path / "linked.json"
    original_read = performance_sidecar.os.read
    linked_during_read = False

    def linking_read(descriptor: int, count: int) -> bytes:
        nonlocal linked_during_read
        if not linked_during_read:
            os.link(source, linked)
            linked_during_read = True
        return original_read(descriptor, count)

    monkeypatch.setattr(performance_sidecar.os, "read", linking_read)
    with pytest.raises(CPUPerformanceError, match="changed during|link identity"):
        performance_sidecar._read_bounded_regular_file(
            source,
            name="test source",
            maximum_bytes=1024,
            require_single_link=True,
            require_stable_size=True,
        )
    monkeypatch.setattr(performance_sidecar.os, "read", original_read)

    fifo = tmp_path / "profile.fifo"
    os.mkfifo(fifo)
    with pytest.raises(CPUPerformanceError, match="bounded regular file"):
        load_cpu_performance_profile(fifo)

    live = _blocked_live_result(monkeypatch)
    artifact = secure_artifact_dir / "owner-only.json"
    write_cpu_performance_artifact(live, artifact)
    artifact.chmod(0o644)
    with pytest.raises(CPUPerformanceError, match="bounded regular file"):
        load_cpu_performance_artifact(
            artifact, profile=load_cpu_performance_profile(_PROFILE_PATH)
        )


def test_artifact_writer_rejects_a_writable_nonsticky_ancestor(
    secure_artifact_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _blocked_live_result(monkeypatch)
    unsafe_ancestor = secure_artifact_dir / "unsafe-ancestor"
    unsafe_ancestor.mkdir(mode=0o700)
    safe_leaf = unsafe_ancestor / "safe-leaf"
    safe_leaf.mkdir(mode=0o700)
    unsafe_ancestor.chmod(0o720)
    try:
        with pytest.raises(CPUPerformanceError, match="parent chain"):
            write_cpu_performance_artifact(live, safe_leaf / "qualification.json")
    finally:
        unsafe_ancestor.chmod(0o700)
