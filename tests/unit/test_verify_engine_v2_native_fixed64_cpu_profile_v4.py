from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import tools.verify_engine_v2_native_fixed64_cpu_profile_v4 as verifier

from tools.verify_engine_v2_native_fixed64_cpu_profile_v4 import (
    NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS,
    NATIVE_VENDOR_COPY_SOURCE_RELATIVE_PATHS,
    REPOSITORY_CARGO_CONFIG_RELATIVE_PATHS,
    REPOSITORY_RUST_TOOLCHAIN_OVERRIDE_RELATIVE_PATHS,
    RUST_BOUND_EMBEDDED_INPUT_BINDINGS,
    RUST_BOUND_CARGO_TARGET_SOURCE_RELATIVE_PATHS,
    RUST_BOUND_BUILD_SCRIPT_RELATIVE_PATHS,
    RUST_BOUND_LOCAL_DEPENDENCY_BINDINGS,
    RUST_COMPILED_SOURCE_TREE_ROOT_RELATIVE_PATHS,
    RUST_PACKAGE_ROOT_RELATIVE_PATHS,
    NativeFixed64CPUProfileV4Error,
    _transitive_source_manifest_sha256,
    discover_native_vendor_tree_paths,
    discover_rust_cargo_target_source_paths,
    discover_rust_compiled_source_tree_paths,
    discover_rust_embedded_input_bindings,
    discover_rust_package_build_script_paths,
    read_bound_source_bytes,
    require_compiled_profile_binding,
    require_native_vendor_tree_paths,
    require_repository_cargo_configuration_absent,
    require_repository_rust_toolchain_override_absent,
    require_rust_cargo_target_source_paths,
    require_rust_embedded_input_bindings,
    require_rust_local_dependency_bindings,
    require_rust_package_build_script_paths,
    require_rust_compiled_source_tree_paths,
    require_profile_document,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
_VERIFIER = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_profile_v4.py"
_NATIVE_WORKFLOW = _ROOT / ".github/workflows/ci-native-compute-abi.yml"
_FOCUSED_WORKFLOW = _ROOT / ".github/workflows/ci-engine-v2-main.yml"
_QUALIFICATION_SOURCE = _ROOT / "rust/betelgeuze-runtime/src/qualification.rs"
_DOCKING_SOURCE = _ROOT / "rust/betelgeuze-runtime/src/docking.rs"
_NATIVE_PIPELINE_SOURCE = _ROOT / "native/src/docking/fixed64_pipeline.cpp"
_PROBE_SOURCE = (
    _ROOT / "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs"
)
_TRANSITIVE_SOURCES = {
    path.as_posix(): (_ROOT / path).read_bytes()
    for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
}
_VENDOR_TREE_PATHS = tuple(
    path.as_posix() for path in NATIVE_VENDOR_COPY_SOURCE_RELATIVE_PATHS
)
_RUST_SOURCE_TREE_PATHS = tuple(
    path.as_posix()
    for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
    if path.suffix == ".rs"
    and any(
        path.is_relative_to(root)
        for root in RUST_COMPILED_SOURCE_TREE_ROOT_RELATIVE_PATHS
    )
)
_RUST_BUILD_SCRIPT_PATHS = tuple(
    path.as_posix() for path in RUST_BOUND_BUILD_SCRIPT_RELATIVE_PATHS
)
_RUST_CARGO_TARGET_SOURCE_PATHS = tuple(
    sorted(path.as_posix() for path in RUST_BOUND_CARGO_TARGET_SOURCE_RELATIVE_PATHS)
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def test_canonical_native_fixed64_cpu_profile_v4_is_frozen() -> None:
    raw = _PROFILE.read_bytes()
    profile = require_profile_document(raw)

    assert hashlib.sha256(raw).hexdigest() == (
        "09a7d27446c7b6283798c6f1c6ba6a3c36ac63582c65b4897657e409ed4536c8"
    )
    assert profile["profile_id"] == "engine_v2_native_fixed64_cpu_synthetic_v4"
    assert all(value is False for value in profile["authority"].values())
    assert [fixture["expected_generated_count"] for fixture in profile["fixtures"]] == [
        64,
        48,
    ]
    assert [
        fixture["expected_typed_failure_count"] for fixture in profile["fixtures"]
    ] == [0, 16]
    assert [fixture["receptor_atom_count"] for fixture in profile["fixtures"]] == [
        12,
        12,
    ]
    assert [fixture["ligand_atom_count"] for fixture in profile["fixtures"]] == [
        12,
        12,
    ]
    require_compiled_profile_binding(
        profile,
        _QUALIFICATION_SOURCE.read_bytes(),
        _DOCKING_SOURCE.read_bytes(),
        _NATIVE_PIPELINE_SOURCE.read_bytes(),
        _PROBE_SOURCE.read_bytes(),
        dict(_TRANSITIVE_SOURCES),
        _VENDOR_TREE_PATHS,
        _RUST_SOURCE_TREE_PATHS,
        _RUST_BUILD_SCRIPT_PATHS,
    )


@pytest.mark.parametrize(
    ("source_name", "old", "new"),
    (
        ("qualification", b"sample_rounds: 25", b"sample_rounds: 2"),
        (
            "qualification",
            b"maximum_rust_to_cpp_median_ratio: 1.25",
            b"maximum_rust_to_cpp_median_ratio: 2.0",
        ),
        (
            "qualification",
            b"const SLOT_COUNT: usize = 64",
            b"const SLOT_COUNT: usize = 63",
        ),
        (
            "qualification",
            b"Self::FeatureSparse => (48, 16)",
            b"Self::FeatureSparse => (49, 15)",
        ),
        (
            "qualification",
            b'Self::Complete => "synthetic_complete_64"',
            b'Self::Complete => "synthetic_complete_drift"',
        ),
        (
            "qualification",
            b"const FROZEN_SCORER_V1_TERM_COUNT: usize = 8",
            b"const FROZEN_SCORER_V1_TERM_COUNT: usize = 7",
        ),
        (
            "qualification",
            b"ligand_radii: [1.2; LIGAND_ATOM_COUNT]",
            b"ligand_radii: [1.3; LIGAND_ATOM_COUNT]",
        ),
        (
            "docking",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.1",
        ),
        (
            "native_pipeline",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.1",
        ),
        (
            "docking",
            b"hash_bool(hash, value.denominator_preserved);",
            b"hash_bool(hash, false);",
        ),
        (
            "native_pipeline",
            b"committed.denominator_preserved = UINT8_C(1);",
            b"committed.denominator_preserved = UINT8_C(0);",
        ),
        (
            "probe",
            b"Fixed64CpuProbeConfigV4::qualification_profile()",
            b"Fixed64CpuProbeConfigV4::unit_test()",
        ),
        (
            "qualification",
            b"pub const FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED: bool = false;",
            b"pub const FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED: bool = true;",
        ),
        (
            "qualification",
            b"pub const fn fixed64_cpu_v4_live_activation_admitted() -> bool {\n"
            b"    FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED\n"
            b"}",
            b"pub const fn fixed64_cpu_v4_live_activation_admitted() -> bool {\n"
            b"    true\n}",
        ),
    ),
)
def test_profile_v4_rejects_compiled_gate_drift(
    source_name: str, old: bytes, new: bytes
) -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    qualification = _QUALIFICATION_SOURCE.read_bytes()
    docking = _DOCKING_SOURCE.read_bytes()
    native_pipeline = _NATIVE_PIPELINE_SOURCE.read_bytes()
    probe = _PROBE_SOURCE.read_bytes()
    if source_name == "qualification":
        assert qualification.count(old) == 1
        qualification = qualification.replace(old, new, 1)
    elif source_name == "docking":
        assert docking.count(old) == 1
        docking = docking.replace(old, new, 1)
    elif source_name == "native_pipeline":
        assert native_pipeline.count(old) == 1
        native_pipeline = native_pipeline.replace(old, new, 1)
    else:
        assert probe.count(old) == 1
        probe = probe.replace(old, new, 1)

    with pytest.raises(NativeFixed64CPUProfileV4Error, match="compiled|entry point"):
        require_compiled_profile_binding(
            profile,
            qualification,
            docking,
            native_pipeline,
            probe,
            dict(_TRANSITIVE_SOURCES),
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_measurement_moved_before_activation_guard() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    probe = _PROBE_SOURCE.read_bytes()
    measurement_call = b"run_native_fixed64_cpu_probe_v4(config)"
    activation_guard = b"if !fixed64_cpu_v4_live_activation_admitted()"
    assert probe.count(measurement_call) == 1
    assert probe.count(activation_guard) == 1
    probe = probe.replace(measurement_call, b"measurement_call_moved", 1)
    probe = probe.replace(
        activation_guard,
        measurement_call + b";\n    " + activation_guard,
        1,
    )
    core = profile["measurement_core"]
    assert type(core) is dict
    core["native_probe_source_sha256"] = hashlib.sha256(probe).hexdigest()
    changed = dict(_TRANSITIVE_SOURCES)
    changed["rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs"] = (
        probe
    )
    core["native_transitive_source_manifest_sha256"] = (
        _transitive_source_manifest_sha256(changed)
    )

    with pytest.raises(NativeFixed64CPUProfileV4Error, match="entry point|precede"):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            probe,
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_requires_runtime_observation_of_release_activation_constant() -> (
    None
):
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    path = "rust/betelgeuze-runtime/tests/fixed64_cpu_probe_activation.rs"
    old = b"std::hint::black_box(FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED)"
    new = b"std::convert::identity(FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED)"
    assert changed[path].count(old) == 1
    changed[path] = changed[path].replace(old, new, 1)
    core = profile["measurement_core"]
    assert type(core) is dict
    core["native_transitive_source_manifest_sha256"] = (
        _transitive_source_manifest_sha256(changed)
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="release non-test activation artifact check",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


@pytest.mark.parametrize(
    "target",
    (
        "native/src/cpu/evaluator.hpp",
        "native/src/docking/scorer_v1.cpp",
    ),
)
def test_profile_v4_rejects_transitive_kernel_source_drift(target: str) -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    drift = b"\n// semantic drift\n"
    changed[target] += drift
    changed[(Path("rust/betelgeuze-sys/vendor") / target).as_posix()] += drift

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="transitive source manifest",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_transitive_source_path_omission() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    changed.pop("rust/betelgeuze-docking-search/src/fixed64_ranking.rs")

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="path set",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_cross_wired_qualification_source() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    qualification = _QUALIFICATION_SOURCE.read_bytes() + b"\n// direct-only drift\n"
    core = profile["measurement_core"]
    assert type(core) is dict
    core["native_qualification_source_sha256"] = hashlib.sha256(
        qualification
    ).hexdigest()

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="cross-wired",
    ):
        require_compiled_profile_binding(
            profile,
            qualification,
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            dict(_TRANSITIVE_SOURCES),
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_abi_probe_source_drift() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    changed["rust/betelgeuze-sys/abi/header_c11.c"] += b"\n/* ABI drift */\n"

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="transitive source manifest",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_vendor_source_drift() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    changed["rust/betelgeuze-sys/vendor/native/src/cpu/evaluator.hpp"] += (
        b"\n// vendored-only semantic drift\n"
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="vendor source differs from canonical",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_vendor_equality_manifest_drift() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    build_path = "rust/betelgeuze-sys/build.rs"
    old = b'    "native/src/cpu/evaluator.hpp",\n'
    assert changed[build_path].count(old) == 1
    changed[build_path] = changed[build_path].replace(old, b"", 1)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="vendor equality manifest changed",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_cfg_shadowed_vendor_declaration() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    build_path = "rust/betelgeuze-sys/build.rs"
    declaration = b"const VENDORED_FILES: &[&str] = &[\n"
    assert changed[build_path].count(declaration) == 1
    changed[build_path] = changed[build_path].replace(
        declaration,
        b"#[cfg(any())]\n" + declaration,
        1,
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="vendor equality manifest changed",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_vendor_shadow_header() -> None:
    expected = tuple(
        path.as_posix() for path in NATIVE_VENDOR_COPY_SOURCE_RELATIVE_PATHS
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="vendor tree contains an unbound",
    ):
        require_native_vendor_tree_paths(
            expected
            + ("rust/betelgeuze-sys/vendor/native/src/cpu/betelgeuze/engine.h",)
        )


def test_profile_v4_rejects_symlinked_vendor_root(tmp_path: Path) -> None:
    vendor = tmp_path / "rust/betelgeuze-sys/vendor"
    vendor.mkdir(parents=True)
    target = tmp_path / "canonical-include"
    target.mkdir()
    (vendor / "include").symlink_to(target, target_is_directory=True)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="vendor root is missing, invalid, or symlinked",
    ):
        discover_native_vendor_tree_paths(tmp_path)


def test_profile_v4_rejects_symlinked_vendor_parent(tmp_path: Path) -> None:
    external = tmp_path / "external-vendor"
    (external / "include").mkdir(parents=True)
    (external / "native").mkdir()
    parent = tmp_path / "rust/betelgeuze-sys"
    parent.mkdir(parents=True)
    (parent / "vendor").symlink_to(external, target_is_directory=True)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="vendor root is missing, invalid, or symlinked",
    ):
        discover_native_vendor_tree_paths(tmp_path)


@pytest.mark.parametrize(
    "target",
    (
        "rust/betelgeuze-runtime/src/dynamics.rs",
        "rust/betelgeuze-runtime/src/forcefield.rs",
    ),
)
def test_profile_v4_rejects_runtime_module_drift(target: str) -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    changed[target] += b"\n// compiled runtime semantic drift\n"

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="transitive source manifest",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


@pytest.mark.parametrize(
    "target",
    (
        "rust/reference-dynamics/fixtures/dynamics_v1.tsv",
        "rust/reference-physics/fixtures/exact_energy_v1.tsv",
    ),
)
def test_profile_v4_rejects_embedded_fixture_drift(target: str) -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    changed[target] += b"\n# embedded fixture semantic drift\n"

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="transitive source manifest",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
            _VENDOR_TREE_PATHS,
            _RUST_SOURCE_TREE_PATHS,
            _RUST_BUILD_SCRIPT_PATHS,
        )


def test_profile_v4_rejects_unbound_rust_source() -> None:
    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Rust compiled source tree contains an unbound",
    ):
        require_rust_compiled_source_tree_paths(
            _RUST_SOURCE_TREE_PATHS + ("rust/betelgeuze-runtime/src/unbound_module.rs",)
        )


def test_profile_v4_discovers_exact_rust_source_tree() -> None:
    assert discover_rust_compiled_source_tree_paths(_ROOT) == tuple(
        sorted(_RUST_SOURCE_TREE_PATHS)
    )


def test_profile_v4_discovers_exact_rust_embedded_inputs() -> None:
    observed = discover_rust_embedded_input_bindings(
        _ROOT,
        _RUST_SOURCE_TREE_PATHS + _RUST_BUILD_SCRIPT_PATHS,
    )
    assert tuple(sorted(observed)) == tuple(sorted(RUST_BOUND_EMBEDDED_INPUT_BINDINGS))


def test_profile_v4_scans_only_present_nonempty_rust_source_roots() -> None:
    for relative in RUST_COMPILED_SOURCE_TREE_ROOT_RELATIVE_PATHS:
        source_root = _ROOT / relative
        assert source_root.is_dir()
        assert any(path.suffix == ".rs" for path in source_root.rglob("*.rs"))


def test_profile_v4_discovers_exact_cargo_target_sources() -> None:
    assert (
        discover_rust_cargo_target_source_paths(_ROOT)
        == _RUST_CARGO_TARGET_SOURCE_PATHS
    )


def test_profile_v4_rejects_package_root_probe_target() -> None:
    changed = tuple(
        "rust/betelgeuze-runtime/probe.rs"
        if path == "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs"
        else path
        for path in _RUST_CARGO_TARGET_SOURCE_PATHS
    )
    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Cargo target source set contains an unbound",
    ):
        require_rust_cargo_target_source_paths(changed)


def test_profile_v4_rejects_unbound_local_dependency_root() -> None:
    changed = tuple(
        (
            *binding[:4],
            "external/betelgeuze-docking-search",
            *binding[5:],
        )
        if binding[:2] == ("betelgeuze-runtime", "betelgeuze-docking-search")
        else binding
        for binding in RUST_BOUND_LOCAL_DEPENDENCY_BINDINGS
    )
    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="local dependency graph contains an unbound",
    ):
        require_rust_local_dependency_bindings(changed)


@pytest.mark.parametrize(
    ("binding_index", "replacement"),
    (
        (5, ("hip",)),
        (6, False),
        (7, True),
        (8, 'cfg(target_arch = "x86_64")'),
    ),
)
def test_profile_v4_rejects_local_dependency_compile_option_drift(
    binding_index: int,
    replacement: object,
) -> None:
    changed = []
    for binding in RUST_BOUND_LOCAL_DEPENDENCY_BINDINGS:
        if binding[:2] != ("betelgeuze-runtime", "betelgeuze-sys"):
            changed.append(binding)
            continue
        mutable = list(binding)
        mutable[binding_index] = replacement
        changed.append(tuple(mutable))

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="local dependency graph contains an unbound",
    ):
        require_rust_local_dependency_bindings(tuple(changed))


def test_profile_v4_rejects_external_local_dependency_from_cargo_metadata(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    external_workspace = tmp_path / "external-workspace"
    shutil.copytree(
        _ROOT / "rust",
        external_workspace / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    external_dependency = external_workspace / "rust/betelgeuze-docking-search"
    runtime_manifest = copied_root / "rust/betelgeuze-runtime/Cargo.toml"
    raw = runtime_manifest.read_text(encoding="utf-8")
    original = 'path = "../betelgeuze-docking-search"'
    assert raw.count(original) == 1
    runtime_manifest.write_text(
        raw.replace(original, f'path = "{external_dependency}"', 1),
        encoding="utf-8",
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="local dependency escapes the repository",
    ):
        discover_rust_cargo_target_source_paths(copied_root)


def test_profile_v4_rejects_local_dependency_feature_from_cargo_metadata(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    runtime_manifest = copied_root / "rust/betelgeuze-runtime/Cargo.toml"
    raw = runtime_manifest.read_text(encoding="utf-8")
    original = 'betelgeuze-sys = { version = "0.1.0", path = "../betelgeuze-sys" }'
    replacement = (
        'betelgeuze-sys = { version = "0.1.0", '
        'path = "../betelgeuze-sys", features = ["hip"] }'
    )
    assert raw.count(original) == 1
    runtime_manifest.write_text(
        raw.replace(original, replacement, 1),
        encoding="utf-8",
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="local dependency graph contains an unbound",
    ):
        discover_rust_cargo_target_source_paths(copied_root)


def test_profile_v4_rejects_cargo_patch_table_before_metadata(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    workspace_manifest = copied_root / "rust/Cargo.toml"
    workspace_manifest.write_text(
        workspace_manifest.read_text(encoding="utf-8")
        + '\n[patch.crates-io]\nsha2 = { path = "/external/sha2" }\n',
        encoding="utf-8",
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Cargo manifest table set contains an unbound",
    ):
        discover_rust_cargo_target_source_paths(copied_root)


@pytest.mark.parametrize(
    "root_assignment",
    (
        'patch.crates-io.sha2 = { path = "/external/sha2" }',
        'patch = { crates-io = { sha2 = { path = "/external/sha2" } } }',
        'replace = { "sha2:0.10.9" = { path = "/external/sha2" } }',
    ),
)
def test_profile_v4_rejects_cargo_root_assignment_before_metadata(
    tmp_path: Path,
    root_assignment: str,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    workspace_manifest = copied_root / "rust/Cargo.toml"
    workspace_manifest.write_text(
        root_assignment
        + "\n"
        + workspace_manifest.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Cargo manifest contains an unbound root assignment",
    ):
        discover_rust_cargo_target_source_paths(copied_root)


def test_profile_v4_rejects_rust_path_attribute_outside_inventory(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    runtime_root = copied_root / "rust/betelgeuze-runtime"
    (runtime_root / "unbound.rs").write_text("pub const VALUE: u8 = 1;\n")
    crate_root = runtime_root / "src/lib.rs"
    crate_root.write_text(
        '#[path = "../unbound.rs"]\nmod unbound;\n'
        + crate_root.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Rust path attribute source expansion is forbidden",
    ):
        discover_rust_compiled_source_tree_paths(copied_root)


@pytest.mark.parametrize(
    ("macro", "expected_error"),
    (
        ("include_str", "embedded compiler input binding set changed"),
        ("include_bytes", "embedded compiler input binding set changed"),
        ("include", "include! source expansion is forbidden"),
    ),
)
def test_profile_v4_rejects_unbound_rust_include_input(
    tmp_path: Path,
    macro: str,
    expected_error: str,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    runtime_root = copied_root / "rust/betelgeuze-runtime"
    (runtime_root / "unbound.rs").write_text("pub const VALUE: u8 = 1;\n")
    crate_root = runtime_root / "src/lib.rs"
    crate_root.write_text(
        f'const _: &[u8] = {macro}!("../unbound.rs");\n'
        + crate_root.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(NativeFixed64CPUProfileV4Error, match=expected_error):
        discover_rust_compiled_source_tree_paths(copied_root)


@pytest.mark.parametrize(
    "macro_source",
    (
        'const _: &str = include_str /* gap */ ! ("../unbound.rs");\n',
        (
            'const _: &str = include_str /* outer /* nested */ gap */ '
            '!("../unbound.rs");\n'
        ),
        'const _: &str = include_str // gap\n!("../unbound.rs");\n',
    ),
)
def test_profile_v4_rejects_comment_separated_rust_include_input(
    tmp_path: Path,
    macro_source: str,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    runtime_root = copied_root / "rust/betelgeuze-runtime"
    (runtime_root / "unbound.rs").write_text("pub const VALUE: u8 = 1;\n")
    crate_root = runtime_root / "src/lib.rs"
    crate_root.write_text(
        macro_source + crate_root.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="embedded compiler input binding set changed",
    ):
        discover_rust_compiled_source_tree_paths(copied_root)


@pytest.mark.parametrize(
    ("character_type", "character_literal"),
    (("char", "'\"'"), ("u8", "b'\"'")),
)
def test_profile_v4_rejects_include_between_rust_character_literals(
    tmp_path: Path,
    character_type: str,
    character_literal: str,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    runtime_root = copied_root / "rust/betelgeuze-runtime"
    (runtime_root / "unbound.rs").write_text("pub const VALUE: u8 = 1;\n")
    crate_root = runtime_root / "src/lib.rs"
    crate_root.write_text(
        f"const Q1: {character_type} = {character_literal};\n"
        'const _: &str = include_str!("../unbound.rs");\n'
        f"const Q2: {character_type} = {character_literal};\n"
        + crate_root.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="embedded compiler input binding set changed",
    ):
        discover_rust_compiled_source_tree_paths(copied_root)


def test_profile_v4_ignores_include_tokens_inside_comments_and_raw_strings(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "copied-repository"
    shutil.copytree(
        _ROOT / "rust",
        copied_root / "rust",
        ignore=shutil.ignore_patterns("target"),
    )
    crate_root = copied_root / "rust/betelgeuze-runtime/src/lib.rs"
    crate_root.write_text(
        '// include_str!("../unbound-comment.txt")\n'
        'const _: &str = r#"include_bytes!("../unbound-raw.txt")"#;\n'
        + crate_root.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    assert discover_rust_compiled_source_tree_paths(copied_root) == tuple(
        sorted(_RUST_SOURCE_TREE_PATHS)
    )


def test_profile_v4_requires_embedded_target_in_transitive_manifest(monkeypatch) -> None:
    changed = RUST_BOUND_EMBEDDED_INPUT_BINDINGS + (
        (
            "rust/betelgeuze-runtime/src/lib.rs",
            "include_str",
            "rust/betelgeuze-runtime/unbound.txt",
        ),
    )
    monkeypatch.setattr(verifier, "RUST_BOUND_EMBEDDED_INPUT_BINDINGS", changed)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="embedded compiler input is absent from the transitive manifest",
    ):
        require_rust_embedded_input_bindings(changed)


def test_profile_v4_rejects_symlinked_rust_source_subdirectory(
    tmp_path: Path,
) -> None:
    for relative in RUST_COMPILED_SOURCE_TREE_ROOT_RELATIVE_PATHS:
        (tmp_path / relative).mkdir(parents=True)
    external = tmp_path / "external-rust-source"
    external.mkdir()
    runtime_root = tmp_path / "rust/betelgeuze-runtime/src"
    (runtime_root / "linked").symlink_to(external, target_is_directory=True)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Rust compiled source tree contains a symlink",
    ):
        discover_rust_compiled_source_tree_paths(tmp_path)


def test_profile_v4_discovers_exact_rust_package_build_scripts() -> None:
    assert discover_rust_package_build_script_paths(_ROOT) == (
        "rust/betelgeuze-sys/build.rs",
    )


def test_profile_v4_rejects_unbound_default_rust_build_script(
    tmp_path: Path,
) -> None:
    for relative in RUST_PACKAGE_ROOT_RELATIVE_PATHS:
        (tmp_path / relative).mkdir(parents=True)
    (tmp_path / "rust/betelgeuze-sys/build.rs").write_bytes(b"fn main() {}\n")
    (tmp_path / "rust/betelgeuze-runtime/build.rs").write_bytes(b"fn main() {}\n")

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="build-script set contains an unbound",
    ):
        discover_rust_package_build_script_paths(tmp_path)


def test_profile_v4_rejects_symlinked_compiler_input(tmp_path: Path) -> None:
    rust_root = tmp_path / "rust"
    rust_root.mkdir()
    external = tmp_path / "external-Cargo.toml"
    external.write_bytes(b"[workspace]\n")
    (rust_root / "Cargo.toml").symlink_to(external)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="compiler source or parent.*symlinked",
    ):
        read_bound_source_bytes(tmp_path, Path("rust/Cargo.toml"))


def test_profile_v4_rejects_symlinked_compiler_input_parent(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external-rust"
    external.mkdir()
    (external / "Cargo.lock").write_bytes(b"")
    (tmp_path / "rust").symlink_to(external, target_is_directory=True)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="compiler source or parent.*symlinked",
    ):
        read_bound_source_bytes(tmp_path, Path("rust/Cargo.lock"))


def test_profile_v4_rejects_build_script_inventory_drift() -> None:
    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="build-script set contains an unbound",
    ):
        require_rust_package_build_script_paths(
            _RUST_BUILD_SCRIPT_PATHS + ("rust/betelgeuze-runtime/build.rs",)
        )


def test_profile_v4_canonical_repository_has_no_cargo_configuration() -> None:
    require_repository_cargo_configuration_absent(_ROOT)


def test_profile_v4_release_non_test_activation_check_is_in_native_ci() -> None:
    source = _NATIVE_WORKFLOW.read_text(encoding="utf-8")
    assert source.count("Verify release non-test activation artifact is blocked") == 1
    assert source.count("cargo test --release --manifest-path rust/Cargo.toml") == 1
    assert source.count("--test fixed64_cpu_probe_activation") == 1
    assert (
        source.count("--exact native_fixed64_cpu_probe_is_blocked_before_measurement")
        == 1
    )


def test_profile_v4_native_workflow_change_triggers_focused_suite() -> None:
    source = _FOCUSED_WORKFLOW.read_text(encoding="utf-8")
    assert source.count('- ".github/workflows/ci-native-compute-abi.yml"') == 1


@pytest.mark.parametrize(
    "relative",
    (
        Path(".cargo"),
        Path(".cargo/config"),
        Path(".cargo/config.toml"),
        Path("rust-toolchain"),
        Path("rust-toolchain.toml"),
    ),
)
def test_profile_v4_root_compiler_overrides_trigger_and_reach_ci_checkout(
    relative: Path,
) -> None:
    quoted_trigger = f'      - "{relative.as_posix()}"'
    sparse_entry = f"            {relative.as_posix()}\n"
    focused = _FOCUSED_WORKFLOW.read_text(encoding="utf-8")
    native = _NATIVE_WORKFLOW.read_text(encoding="utf-8")
    assert focused.count(quoted_trigger) == 1
    assert focused.count(sparse_entry) == 1
    assert native.count(quoted_trigger) == 2
    assert native.count(sparse_entry) == 1


@pytest.mark.parametrize("relative", REPOSITORY_CARGO_CONFIG_RELATIVE_PATHS)
def test_profile_v4_rejects_repository_cargo_configuration(
    tmp_path: Path,
    relative: Path,
) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"[build]\nrustflags = ['--cfg', 'activation_open']\n")

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Cargo configuration is forbidden",
    ):
        require_repository_cargo_configuration_absent(tmp_path)


def test_profile_v4_rejects_symlinked_cargo_configuration_parent(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external-cargo"
    external.mkdir()
    (tmp_path / ".cargo").symlink_to(external, target_is_directory=True)

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Cargo configuration path is symlinked",
    ):
        require_repository_cargo_configuration_absent(tmp_path)


def test_profile_v4_canonical_repository_has_no_rust_toolchain_override() -> None:
    require_repository_rust_toolchain_override_absent(_ROOT)


@pytest.mark.parametrize(
    "relative",
    REPOSITORY_RUST_TOOLCHAIN_OVERRIDE_RELATIVE_PATHS,
)
def test_profile_v4_rejects_repository_rust_toolchain_override(
    tmp_path: Path,
    relative: Path,
) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"[toolchain]\nchannel = 'nightly'\n")

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="Rust toolchain override is forbidden",
    ):
        require_repository_rust_toolchain_override_absent(tmp_path)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda profile: profile["authority"].update(qualification_authority=True),
        lambda profile: profile["restrictions"].update(
            hip_device_execution_allowed=True
        ),
        lambda profile: profile["fixtures"][0].update(candidate_denominator=63),
        lambda profile: profile["gates"].update(score_term_count_exact=7),
        lambda profile: profile["numeric_parity"].update(relative_tolerance=1e-3),
        lambda profile: profile["performance"].update(maximum_ratio=2.0),
        lambda profile: profile["sampling"].update(schedule="rust_first"),
    ),
)
def test_profile_v4_rejects_authority_or_numeric_drift(mutate) -> None:
    profile = json.loads(_PROFILE.read_text(encoding="ascii"))
    changed = deepcopy(profile)
    mutate(changed)

    with pytest.raises(NativeFixed64CPUProfileV4Error):
        require_profile_document(_canonical(changed))


def test_profile_v4_rejects_noncanonical_or_duplicate_json() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="ascii"))
    compact = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode("ascii")
    with pytest.raises(NativeFixed64CPUProfileV4Error, match="serialization"):
        require_profile_document(compact)

    duplicate = _PROFILE.read_bytes().replace(
        b'{\n  "authority": {',
        b'{\n  "status": "duplicate",\n  "authority": {',
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV4Error, match="duplicate"):
        require_profile_document(duplicate)


def test_profile_v4_cli_reports_non_consuming_authority_false() -> None:
    completed = subprocess.run(
        [sys.executable, str(_VERIFIER)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "all_authority_false": True,
        "candidate_denominator": 64,
        "compiled_profile_binding_verified": True,
        "execution_consumed": False,
        "fixture_count": 2,
        "profile_id": "engine_v2_native_fixed64_cpu_synthetic_v4",
        "profile_sha256": (
            "09a7d27446c7b6283798c6f1c6ba6a3c36ac63582c65b4897657e409ed4536c8"
        ),
        "reservation_created": False,
        "status": "verified",
    }
