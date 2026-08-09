from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import betelgeuze_engine_v2.docking.performance_sidecar as performance_sidecar
from betelgeuze_engine_v2.docking.performance_sidecar import (
    FROZEN_SYNTHETIC_FIXTURES,
    compare_geometric_outputs,
    generate_synthetic_geometric_fixture,
    load_cpu_performance_profile,
    normalize_native_geometric_output,
    normalize_python_geometric_output,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _REPO_ROOT / "config/engine_v2_cpu_performance_profile.json"


@pytest.fixture(scope="module", autouse=True)
def _native_extension_is_installed() -> None:
    pytest.importorskip("betelgeuze_engine_v2_native")


@pytest.mark.parametrize(
    "fixture_id", [fixture.fixture_id for fixture in FROZEN_SYNTHETIC_FIXTURES]
)
def test_native_geometric_kernel_matches_full_python_metrics(fixture_id: str) -> None:
    profile = load_cpu_performance_profile(_PROFILE)
    fixture = generate_synthetic_geometric_fixture(fixture_id)
    reference = normalize_python_geometric_output(fixture)
    first = normalize_native_geometric_output(fixture)
    second = normalize_native_geometric_output(fixture)

    comparison = compare_geometric_outputs(reference, first, profile)
    assert comparison.passed, comparison.blockers
    assert first.to_dict() == second.to_dict()
    assert first.output_sha256 == second.output_sha256
    assert first.exact_pair_count == fixture.exact_pair_count
    expected_paths = {
        "small": ("accepted", 0, 5.0),
        "medium": ("accepted", 1, 0.0),
        "large": ("rejected", 874, 5.0),
    }
    assert (
        first.decision,
        first.penetration_pair_count,
        first.pocket_escape_angstrom,
    ) == expected_paths[fixture_id]
    if fixture_id == "medium":
        assert first.minimum_vdw_ratio == 0.55


def test_native_geometric_build_receipt_binds_current_rust_source_and_lock() -> None:
    native = pytest.importorskip("betelgeuze_engine_v2_native")
    info = dict(native.build_info())
    rust_source = _REPO_ROOT / "rust_engine_v2/src/lib.rs"
    cargo_lock = _REPO_ROOT / "rust_engine_v2/Cargo.lock"
    cargo_manifest = _REPO_ROOT / "rust_engine_v2/Cargo.toml"
    native_pyproject = _REPO_ROOT / "rust_engine_v2/pyproject.toml"
    build_script = _REPO_ROOT / "rust_engine_v2/build.rs"
    build_wrapper = _REPO_ROOT / "tools/build_engine_v2_native_wheel.py"

    assert info["backend_version"] == "0.2.0-rc.6"
    assert info["rust_lib_sha256"] == hashlib.sha256(rust_source.read_bytes()).hexdigest()
    assert info["cargo_lock_sha256"] == hashlib.sha256(cargo_lock.read_bytes()).hexdigest()
    assert info["cargo_manifest_sha256"] == hashlib.sha256(
        cargo_manifest.read_bytes()
    ).hexdigest()
    assert info["native_pyproject_sha256"] == hashlib.sha256(
        native_pyproject.read_bytes()
    ).hexdigest()
    assert info["build_script_sha256"] == hashlib.sha256(
        build_script.read_bytes()
    ).hexdigest()
    assert info["native_build_wrapper_sha256"] == hashlib.sha256(
        build_wrapper.read_bytes()
    ).hexdigest()
    assert info["build_wrapper_control"] == "verified_frozen_wrapper"
    assert info["geometric_admission_metrics_kernel_id"] == (
        "betelgeuze.engine_v2_native_geometric_admission_metrics_one/1.0.0"
    )
    assert info["geometric_admission_pair_traversal_order"] == (
        "full_cartesian_ligand_index_major_receptor_index_minor"
    )
    assert info["implicit_fallback_allowed"] == "false"


def test_native_loader_binds_the_actual_installed_extension_file() -> None:
    module = performance_sidecar._load_native_module()
    extension = performance_sidecar._native_extension_path(module)
    projection = performance_sidecar._native_child_binding_projection()

    assert extension.is_file()
    assert extension.suffix == ".so"
    assert projection["native_extension_sha256"] == hashlib.sha256(
        extension.read_bytes()
    ).hexdigest()
    assert projection["native_build_info"] == dict(module.build_info())
