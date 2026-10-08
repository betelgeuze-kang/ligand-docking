from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/generate_engine_v2_state_bundle_v1.py"
SPEC = importlib.util.spec_from_file_location("engine_v2_state_bundle_v1", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COMMIT = "1" * 40
TREE = "2" * 40


def _copy_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    required = set(MODULE.verified_required_paths(ROOT))
    for relative in sorted(required, key=lambda value: value.as_posix()):
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return root


def _tool(root: Path) -> Path:
    return root / MODULE.GENERATOR_PATH


def _build(root: Path) -> tuple[dict, dict, dict]:
    return MODULE.build_bundle(
        root,
        source_commit=COMMIT,
        source_tree=TREE,
        source_binding="unverified_fixture",
    )


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="ascii"))


def _commit_fixture(root: Path) -> tuple[str, str]:
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "-q"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "add", "--all"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=state-bundle-test",
            "-c",
            "user.email=state-bundle-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


def test_repository_bundle_inventories_current_source_without_authority() -> None:
    implementation, authority, release = MODULE.build_bundle(
        ROOT,
        source_commit=COMMIT,
        source_tree=TREE,
        source_binding="unverified_fixture",
    )
    assert implementation["source_identity"] == {
        "binding": "unverified_fixture",
        "commit_sha": COMMIT,
        "tree_sha": TREE,
    }
    assert implementation["packages"]["python_distribution"]["version"] == "0.2.0rc5"
    assert implementation["packages"]["native_distribution"]["version"] == "0.2.0rc6"
    assert (
        implementation["packages"]["python_distribution"]
        ["required_native_distribution_version"]
        == "0.2.0rc6"
    )
    assert implementation["public_abis"]["core"]["version"] == "1.21"
    assert len(implementation["public_abis"]) == 8
    assert implementation["backends"]["hip_fast"]["source_path"] == (
        "native/src/hip/backend.hip"
    )
    assert implementation["backends"]["hip_safe"]["source_paths"] == [
        "native/src/hip/evaluator.cpp",
        "native/src/hip/provider.hip",
    ]
    expected_rust_cpu_paths = {
        path.as_posix()
        for path in (
            *MODULE.rust_cpu_bridge_source_paths(ROOT),
            *MODULE.rust_cpu_provider_source_paths(ROOT),
        )
    }
    rust_cpu = implementation["backends"]["rust_cpu"]
    assert (
        rust_cpu["implementation_state"]
        == "repository_source_and_build_surface_declared"
    )
    assert rust_cpu["binary_provenance_evaluated"] is False
    assert (
        rust_cpu["source_inventory_scope"]
        == "declared_rust_provider_and_native_bridge_inputs"
    )
    assert rust_cpu["build_path"] == "native/CMakeLists.txt"
    assert rust_cpu["source_paths"] == sorted(rust_cpu["source_paths"])
    assert len(rust_cpu["source_paths"]) == len(set(rust_cpu["source_paths"]))
    assert set(rust_cpu["source_paths"]) == expected_rust_cpu_paths
    assert {
        "native/src/rust/evaluator.hpp",
        "native/src/rust/provider.h",
        "native/src/internal.hpp",
        "native/src/cpu/evaluator.hpp",
        "native/src/cpu/neighbor_pair.hpp",
        "native/src/docking/fixed64_indexed_so3_provider.h",
        "native/src/docking/fixed64_single_anchor_provider.h",
        "rust/Cargo.lock",
        "rust/cpu-kernel/src/kernel.rs",
        "rust/betelgeuze-docking-search/src/geometry.rs",
    } <= expected_rust_cpu_paths
    source_input_paths = {row["path"] for row in implementation["source_inputs"]}
    assert {
        "native/src/hip/evaluator.cpp",
        "native/src/hip/provider.hip",
        "native/src/hip/backend.hip",
    } <= source_input_paths
    assert expected_rust_cpu_paths <= source_input_paths
    assert implementation["docking"]["sampling"]["input_denominator"] == 512
    assert implementation["docking"]["sampling"]["output_denominator"] == 64
    assert implementation["docking"]["scorer"]["term_count"] == 8
    assert (
        implementation["docking"]["pipeline_profile_id"]
        == "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0"
    )
    assert implementation["d1_development"]["all_repository_output_paths_present"] is False
    assert (
        implementation["d1_development"]["repository_output_semantic_validation"]
        == "not_evaluated_by_state_generator"
    )
    assert implementation["d1_development"]["repository_output_present_count"] == 0
    assert all(
        row["present"] is False
        for row in implementation["d1_development"]["repository_outputs"]
    )
    assert authority["unresolved_operational_decisions"] == 32
    assert release["release_status"] == "unreleased_unverified_fixture"
    assert release["artifacts"] == []
    assert release["release_authorized"] is False
    assert release["claim_authority_granted"] is False


def test_generation_is_byte_deterministic_and_release_hashes_exact(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    implementation, authority, release = _build(root)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_hashes = MODULE.write_bundle(first, implementation, authority, release)
    second_hashes = MODULE.write_bundle(second, implementation, authority, release)
    assert first_hashes == second_hashes
    for name in first_hashes:
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == first_hashes[name]
    assert release["state_documents"]["implementation"]["sha256"] == hashlib.sha256(
        (first / "engine_v2_implementation_state_v1.json").read_bytes()
    ).hexdigest()
    assert release["state_documents"]["authority"]["sha256"] == hashlib.sha256(
        (first / "engine_v2_authority_state_v1.json").read_bytes()
    ).hexdigest()
    with pytest.raises(MODULE.StateBundleError, match="must be absent"):
        MODULE.write_bundle(first, implementation, authority, release)


def test_python_version_is_derived_instead_of_frozen(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.PYTHON_PACKAGE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'version = "0.2.0rc5"', 'version = "0.2.0rc7"', 1
        ),
        encoding="utf-8",
    )
    implementation, _authority, _release = _build(root)
    assert implementation["packages"]["python_distribution"]["version"] == "0.2.0rc7"


def test_native_dependency_must_equal_native_distribution(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_PACKAGE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace("0.2.0rc6", "0.2.0rc7", 1),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="native dependency"):
        _build(root)


def test_canonical_vendor_abi_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / "rust/betelgeuze-sys/vendor/include/betelgeuze/engine.h"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(MODULE.StateBundleError, match="canonical/vendor ABI"):
        _build(root)


def test_c_and_rust_abi_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.RUST_SYS_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "pub const BG_ABI_VERSION_MINOR: u32 = 21;",
            "pub const BG_ABI_VERSION_MINOR: u32 = 22;",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="C/Rust ABI"):
        _build(root)


def test_rust_compatibility_abi_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.RUST_SYS_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "pub const BG_ABI_VERSION: u32 = 1;",
            "pub const BG_ABI_VERSION: u32 = 2;",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="C/Rust ABI"):
        _build(root)


def test_sampler_source_profile_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.SAMPLING_PROFILE_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    value["output_denominator"] = 63
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="sampling denominator"):
        _build(root)


def test_sampler_rust_profile_hash_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.SAMPLING_FUNNEL_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace("0x5f,", "0x00,", 1),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="profile hash"):
        _build(root)


def test_sampler_rust_lane_quota_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.SAMPLING_FUNNEL_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace("Self::UniformSo3 => 24", "Self::UniformSo3 => 23", 1),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="lane policy"):
        _build(root)


def test_sampler_profile_lane_quota_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.SAMPLING_PROFILE_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    value["lane_quotas"]["uniform_so3"] = 23
    value["lane_quotas"]["pocket_surface"] = 17
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="lane order or quota"):
        _build(root)


def test_scorer_term_count_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.SCORER_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace("[f64; 8]", "[f64; 9]"),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="weight count"):
        _build(root)


@pytest.mark.parametrize(
    ("section", "key"),
    [
        ("execution_authority", "fresh_128_execution_authorized"),
        ("execution_authority", "hip_device_execution_authorized"),
        ("execution_authority", "customer_execution_enabled"),
        ("claim_authority", "scientific_validity_green"),
        ("claim_authority", "docking_accuracy_claim_allowed"),
    ],
)
def test_authority_escalation_fails_closed(
    tmp_path: Path, section: str, key: str
) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.AUTHORITY_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    value[section][key] = True
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="must remain exactly false"):
        _build(root)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("native_fixed64_cpu_v7_authoritative", True),
        ("native_fixed64_cpu_v7_consumed", False),
        ("native_fixed64_cpu_v7_rerun_authorized", True),
    ],
)
def test_consumed_qualification_guard_drift_fails_closed(
    tmp_path: Path, field: str, value: bool
) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.AUTHORITY_PATH
    document = json.loads(path.read_text(encoding="utf-8"))
    document["qualification_guard"][field] = value
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="qualification guard"):
        _build(root)


def test_blocker_or_unresolved_count_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.AUTHORITY_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    value["operational_blockers"].pop()
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="blocker"):
        _build(root)

    root = _copy_root(tmp_path / "count")
    path = root / MODULE.AUTHORITY_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    value["unresolved_operational_decisions"] = 31
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="decision count"):
        _build(root)


def test_operations_decision_crosscheck_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.OPERATIONS_DECISION_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    value["operations_decision_ready"] = True
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="must remain unresolved"):
        _build(root)


@pytest.mark.parametrize(
    ("relative_path", "missing_key", "error_name"),
    [
        (
            MODULE.OPERATIONS_DECISION_PATH,
            "historical_execution_operational",
            "operations authority",
        ),
        (
            MODULE.D1_PROFILE_PATH,
            "fresh_128_execution_authorized",
            "D1 authority",
        ),
        (
            MODULE.SAMPLING_PROFILE_PATH,
            "product_authorized",
            "sampling authority",
        ),
    ],
)
def test_secondary_authority_missing_key_fails_closed(
    tmp_path: Path, relative_path: Path, missing_key: str, error_name: str
) -> None:
    root = _copy_root(tmp_path)
    path = root / relative_path
    value = json.loads(path.read_text(encoding="utf-8"))
    del value["authority"][missing_key]
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match=error_name):
        _build(root)


def test_d1_repository_output_presence_is_derived(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    expected = root / MODULE.D1_REPOSITORY_OUTPUTS[0]
    expected.parent.mkdir(parents=True, exist_ok=True)
    expected.write_text("{}\n", encoding="ascii")
    implementation, _authority, _release = _build(root)
    assert implementation["d1_development"]["all_repository_output_paths_present"] is False
    assert implementation["d1_development"]["repository_output_present_count"] == 1
    first = implementation["d1_development"]["repository_outputs"][0]
    assert first["present"] is True
    assert first["sha256"] == hashlib.sha256(b"{}\n").hexdigest()


def test_d1_all_paths_present_does_not_claim_semantic_validation(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    for relative in MODULE.D1_REPOSITORY_OUTPUTS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="ascii")
    implementation, _authority, _release = _build(root)
    d1 = implementation["d1_development"]
    assert d1["repository_output_present_count"] == len(MODULE.D1_REPOSITORY_OUTPUTS)
    assert d1["all_repository_output_paths_present"] is True
    assert d1["repository_output_semantic_validation"] == "not_evaluated_by_state_generator"
    assert "repository_materialized_result_complete" not in d1


def test_source_inputs_are_sorted_unique_and_hash_bound() -> None:
    implementation, _authority, _release = MODULE.build_bundle(
        ROOT,
        source_commit=COMMIT,
        source_tree=TREE,
        source_binding="unverified_fixture",
    )
    rows = implementation["source_inputs"]
    paths = [row["path"] for row in rows]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    for row in rows:
        assert row["sha256"] == hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()


def test_rust_cpu_provider_source_closure_matches_declared_cmake_inputs() -> None:
    manifests = MODULE.rust_cpu_provider_crate_manifest_paths(ROOT)
    assert manifests == (
        Path("rust/betelgeuze-docking-search/Cargo.toml"),
        Path("rust/cpu-kernel/Cargo.toml"),
    )
    directories = MODULE.rust_cpu_provider_source_directories(ROOT)
    assert directories == (
        Path("rust/betelgeuze-docking-search/src"),
        Path("rust/cpu-kernel/src"),
    )
    expected = set(MODULE.RUST_CPU_PROVIDER_CONTROL_PATHS) | set(manifests)
    for relative_directory in directories:
        expected.update(
            path.relative_to(ROOT)
            for path in (ROOT / relative_directory).rglob("*.rs")
            if path.is_file() and not path.is_symlink()
        )
    expected.add(
        Path(
            "rust/betelgeuze-docking-search/tests/fixtures/"
            "sampling_funnel_selected_indices_v1.txt"
        )
    )
    assert set(MODULE.rust_cpu_provider_source_paths(ROOT)) == expected


def test_rust_cpu_bridge_source_closure_includes_private_headers() -> None:
    assert set(MODULE.rust_cpu_bridge_source_paths(ROOT)) == {
        Path("include/betelgeuze/engine.h"),
        Path("native/src/cpu/evaluator.hpp"),
        Path("native/src/cpu/neighbor_pair.hpp"),
        Path("native/src/docking/fixed64_indexed_so3_provider.h"),
        Path("native/src/docking/fixed64_single_anchor_provider.h"),
        Path("native/src/internal.hpp"),
        Path("native/src/rust/evaluator.cpp"),
        Path("native/src/rust/evaluator.hpp"),
        Path("native/src/rust/provider.h"),
    }


def test_rust_cpu_cmake_extra_source_glob_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    marker = '    "${PROJECT_SOURCE_DIR}/rust/betelgeuze-docking-search/src/*.rs")'
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            marker,
            '    "${PROJECT_SOURCE_DIR}/rust/betelgeuze-docking-search/src/*.rs"\n'
            '    "${PROJECT_SOURCE_DIR}/rust/unbound-provider/src/*.rs")',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="source globs differ"):
        _build(root)


def test_rust_cpu_new_local_path_dependency_fails_without_cmake_binding(
    tmp_path: Path,
) -> None:
    root = _copy_root(tmp_path)
    manifest = root / MODULE.RUST_CPU_CRATE_MANIFEST_PATH
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            '[dependencies]\n',
            '[dependencies]\nfixture-local = { path = "../fixture-local" }\n',
            1,
        ),
        encoding="utf-8",
    )
    fixture_manifest = root / "rust/fixture-local/Cargo.toml"
    fixture_manifest.parent.mkdir(parents=True, exist_ok=True)
    fixture_manifest.write_text(
        '[package]\nname = "fixture-local"\nversion = "0.0.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    fixture_source = root / "rust/fixture-local/src/lib.rs"
    fixture_source.parent.mkdir(parents=True, exist_ok=True)
    fixture_source.write_text("pub fn fixture() {}\n", encoding="utf-8")
    workspace = root / MODULE.RUST_WORKSPACE_MANIFEST_PATH
    workspace.write_text(
        workspace.read_text(encoding="utf-8").replace(
            '    "cpu-kernel",\n',
            '    "cpu-kernel",\n    "fixture-local",\n',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="source globs differ"):
        _build(root)


def test_rust_cpu_workspace_dependency_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    workspace = root / MODULE.RUST_WORKSPACE_MANIFEST_PATH
    workspace.write_text(
        workspace.read_text(encoding="utf-8")
        + '\n[workspace.dependencies]\nfixture-local = { path = "fixture-local" }\n',
        encoding="utf-8",
    )
    manifest = root / MODULE.RUST_CPU_CRATE_MANIFEST_PATH
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "[dependencies]\n",
            "[dependencies]\nfixture-local = { workspace = true }\n",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="workspace-inherited dependency"):
        _build(root)


def test_rust_cpu_workspace_patch_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    workspace = root / MODULE.RUST_WORKSPACE_MANIFEST_PATH
    workspace.write_text(
        workspace.read_text(encoding="utf-8")
        + '\n[patch.crates-io]\nlibm = { path = "fixture-libm" }\n',
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="patch overrides are unsupported"):
        _build(root)


def test_rust_cpu_custom_library_path_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    manifest = root / MODULE.RUST_CPU_CRATE_MANIFEST_PATH
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            '[lib]\ncrate-type = ["rlib", "staticlib"]',
            '[lib]\npath = "src/lib.rs"\ncrate-type = ["rlib", "staticlib"]',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="custom library paths"):
        _build(root)


def test_rust_cpu_custom_build_script_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    manifest = root / MODULE.RUST_CPU_CRATE_MANIFEST_PATH
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "publish = false\n",
            'publish = false\nbuild = "build_support/custom.rs"\n',
            1,
        ),
        encoding="utf-8",
    )
    build_script = manifest.parent / "build_support/custom.rs"
    build_script.parent.mkdir(parents=True, exist_ok=True)
    build_script.write_text("fn main() {}\n", encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="build scripts are unsupported"):
        _build(root)


def test_rust_cpu_repository_cargo_config_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    config = root / ".cargo/config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[build]\nrustflags = ["-C", "opt-level=0"]\n', encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="Cargo configuration"):
        _build(root)


def test_rust_cpu_out_of_tree_path_dependency_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    manifest = root / MODULE.RUST_CPU_CRATE_MANIFEST_PATH
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "[dependencies]\n",
            '[dependencies]\noutside = { path = "../../third-party/outside" }\n',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="must stay below rust"):
        _build(root)


def test_rust_cpu_entry_must_remain_workspace_member(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    workspace = root / MODULE.RUST_WORKSPACE_MANIFEST_PATH
    workspace.write_text(
        workspace.read_text(encoding="utf-8").replace('    "cpu-kernel",\n', "", 1),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="not a workspace member"):
        _build(root)


def test_rust_cpu_entry_must_produce_static_library(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    manifest = root / MODULE.RUST_CPU_CRATE_MANIFEST_PATH
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'crate-type = ["rlib", "staticlib"]',
            'crate-type = ["rlib"]',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="must produce the static provider"):
        _build(root)


@pytest.mark.parametrize(
    "attribute",
    [
        '#[cfg_attr(all(), path = "../outside.rs")]',
        '# /* gap */ [path = "../outside.rs"]',
        '#[cfg_attr(all(), doc = "]", path = "../outside.rs")]',
    ],
)
def test_rust_cpu_path_attribute_forms_fail_closed(
    tmp_path: Path, attribute: str
) -> None:
    root = _copy_root(tmp_path)
    source = root / "rust/cpu-kernel/src/kernel.rs"
    source.write_text(
        source.read_text(encoding="utf-8")
        + f'\n{attribute}\nmod outside;\n',
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match=r"unsupported #\[path\] input"):
        _build(root)


@pytest.mark.parametrize(
    "source_suffix",
    [
        'const _COMMENT_GAP: &str = include_str /* gap */ !("kernel.rs");',
        (
            "use std::include_str as embedded_file;\n"
            'const _ALIASED: &str = embedded_file!("kernel.rs");'
        ),
    ],
)
def test_rust_cpu_indirect_file_input_syntax_fails_closed(
    tmp_path: Path, source_suffix: str
) -> None:
    root = _copy_root(tmp_path)
    source = root / "rust/cpu-kernel/src/kernel.rs"
    source.write_text(
        source.read_text(encoding="utf-8") + f"\n{source_suffix}\n",
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="file-input syntax"):
        _build(root)


def test_rust_cpu_source_tree_symlink_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    target = root / "rust/cpu-kernel/unbound-module"
    target.mkdir(parents=True)
    (target / "mod.rs").write_text("pub fn outside() {}\n", encoding="utf-8")
    link = root / "rust/cpu-kernel/src/indirect"
    link.symlink_to(target, target_is_directory=True)
    source = root / "rust/cpu-kernel/src/lib.rs"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nmod indirect;\n",
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="source tree contains symlink"):
        _build(root)


def test_rust_cpu_literal_file_input_is_hash_bound(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    relative = Path(
        "rust/betelgeuze-docking-search/tests/fixtures/"
        "sampling_funnel_selected_indices_v1.txt"
    )
    before, _authority, _release = _build(root)
    before_hashes = {row["path"]: row["sha256"] for row in before["source_inputs"]}
    assert relative.as_posix() in before_hashes
    path = root / relative
    path.write_bytes(path.read_bytes() + b"\n")
    after, _authority, _release = _build(root)
    after_hashes = {row["path"]: row["sha256"] for row in after["source_inputs"]}
    assert after_hashes[relative.as_posix()] != before_hashes[relative.as_posix()]
    assert after_hashes[relative.as_posix()] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_rust_cpu_nonliteral_file_input_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / "rust/cpu-kernel/src/kernel.rs"
    path.write_text(
        path.read_text(encoding="utf-8")
        + '\nconst _UNBOUND: &str = include_str!(concat!("un", "bound"));\n',
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="non-literal file input"):
        _build(root)


def test_rust_cpu_path_attribute_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / "rust/cpu-kernel/src/kernel.rs"
    path.write_text(
        path.read_text(encoding="utf-8")
        + '\n#[path = "unbound.rs"]\nmod unbound;\n',
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match=r"unsupported #\[path\] input"):
        _build(root)


def test_rust_cpu_cargo_command_replacement_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "${CARGO_EXECUTABLE} build",
            "${CMAKE_COMMAND} -E echo",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="Rust CPU Cargo"):
        _build(root)


def test_rust_cpu_commented_locked_flag_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "        --locked\n",
            "        # --locked\n",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="Rust CPU Cargo"):
        _build(root)


def test_rust_cpu_source_variable_mutation_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    marker = '    "${PROJECT_SOURCE_DIR}/rust/betelgeuze-docking-search/src/*.rs")\n'
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            marker,
            marker + "list(REMOVE_ITEM BG_RUST_CPU_SOURCES unbound.rs)\n",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="source variable usage changed"):
        _build(root)


def test_rust_cpu_literal_dependency_removal_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '        "${PROJECT_SOURCE_DIR}/rust/betelgeuze-docking-search/tests/'
            'fixtures/sampling_funnel_selected_indices_v1.txt"\n',
            "",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="command or dependencies"):
        _build(root)


def test_rust_cpu_cargo_executable_rebinding_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "find_program(CARGO_EXECUTABLE cargo REQUIRED)\n",
            "find_program(CARGO_EXECUTABLE cargo REQUIRED)\n"
            'set(CARGO_EXECUTABLE "${CMAKE_COMMAND}")\n',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="reassignment"):
        _build(root)


@pytest.mark.parametrize(
    ("old", "error"),
    [
        ("    src/rust/evaluator.cpp\n", "bridge source binding"),
        (
            "target_link_libraries(betelgeuze_engine PRIVATE "
            "betelgeuze_rust_cpu_provider)\n",
            "provider control-flow boundary|provider link binding",
        ),
    ],
)
def test_rust_cpu_required_native_binding_removal_fails_closed(
    tmp_path: Path, old: str, error: str
) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(old, "", 1),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match=error):
        _build(root)


def test_rust_cpu_cmake_bracket_comment_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    text = path.read_text(encoding="utf-8").replace(
        "find_program(CARGO_EXECUTABLE cargo REQUIRED)\n",
        "#[[\nfind_program(CARGO_EXECUTABLE cargo REQUIRED)\n",
        1,
    )
    text = text.replace(
        "target_link_libraries(betelgeuze_engine PRIVATE "
        "betelgeuze_rust_cpu_provider)\n",
        "target_link_libraries(betelgeuze_engine PRIVATE "
        "betelgeuze_rust_cpu_provider)\n]]\n",
        1,
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="Cargo executable binding"):
        _build(root)


def test_rust_cpu_cmake_control_flow_wrapper_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    text = path.read_text(encoding="utf-8").replace(
        "find_program(CARGO_EXECUTABLE cargo REQUIRED)\n",
        "if(FALSE)\nfind_program(CARGO_EXECUTABLE cargo REQUIRED)\n",
        1,
    )
    text = text.replace(
        "target_link_libraries(betelgeuze_engine PRIVATE "
        "betelgeuze_rust_cpu_provider)\n",
        "target_link_libraries(betelgeuze_engine PRIVATE "
        "betelgeuze_rust_cpu_provider)\nendif()\n",
        1,
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(MODULE.StateBundleError, match="active at top level"):
        _build(root)


def test_rust_cpu_custom_command_suffix_mutation_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '    COMMENT "Building deterministic Rust CPU provider"\n    VERBATIM\n',
            '    COMMENT "Building deterministic Rust CPU provider"\n'
            '    WORKING_DIRECTORY "/tmp"\n    VERBATIM\n',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="command or dependencies"):
        _build(root)


def test_native_directory_include_mutation_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.NATIVE_CMAKE_PATH
    path.write_text(
        'include_directories(BEFORE "${PROJECT_SOURCE_DIR}/shadow")\n'
        + path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="include paths are unsupported"):
        _build(root)


def test_root_cmake_native_target_mutation_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    path = root / MODULE.ROOT_CMAKE_PATH
    path.write_text(
        path.read_text(encoding="utf-8")
        + '\ntarget_include_directories(betelgeuze_engine BEFORE PRIVATE "shadow")\n',
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="must not mutate"):
        _build(root)


def test_native_line_spliced_quoted_include_is_hash_bound(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    header = Path("native/src/rust/line_spliced_fixture.hpp")
    (root / header).write_text("// line-spliced fixture\n", encoding="utf-8")
    provider = root / MODULE.RUST_CPU_PROVIDER_HEADER_PATH
    provider.write_text(
        provider.read_text(encoding="utf-8")
        + '#include \\\n    "line_spliced_fixture.hpp"\n',
        encoding="utf-8",
    )
    implementation, _authority, _release = _build(root)
    hashes = {row["path"]: row["sha256"] for row in implementation["source_inputs"]}
    assert hashes[header.as_posix()] == hashlib.sha256(
        (root / header).read_bytes()
    ).hexdigest()


def test_native_macro_include_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    provider = root / MODULE.RUST_CPU_PROVIDER_HEADER_PATH
    provider.write_text(
        provider.read_text(encoding="utf-8")
        + '#define BG_UNBOUND_HEADER "unbound.hpp"\n#include BG_UNBOUND_HEADER\n',
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="unsupported include operand"):
        _build(root)


def test_native_angle_include_uses_cmake_search_order(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    selected = Path("include/source_order_fixture.hpp")
    shadowed = Path("native/src/source_order_fixture.hpp")
    (root / selected).write_text("// selected include\n", encoding="utf-8")
    (root / shadowed).write_text("// shadowed include\n", encoding="utf-8")
    provider = root / MODULE.RUST_CPU_PROVIDER_HEADER_PATH
    provider.write_text(
        provider.read_text(encoding="utf-8")
        + "#include <source_order_fixture.hpp>\n",
        encoding="utf-8",
    )
    paths = set(MODULE.rust_cpu_bridge_source_paths(root))
    assert selected in paths
    assert shadowed not in paths


def test_native_commented_include_is_hash_bound(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    header = Path("native/src/rust/commented_include_fixture.hpp")
    (root / header).write_text("// commented include fixture\n", encoding="utf-8")
    provider = root / MODULE.RUST_CPU_PROVIDER_HEADER_PATH
    provider.write_text(
        provider.read_text(encoding="utf-8")
        + '#/**/include "commented_include_fixture.hpp"\n',
        encoding="utf-8",
    )
    assert header in set(MODULE.rust_cpu_bridge_source_paths(root))


@pytest.mark.parametrize(
    ("directive", "error"),
    [
        ("#include_next <cstddef>", "unsupported include directive"),
        ("#import <cstddef>", "unsupported include directive"),
        ("%:include <cstddef>", "digraph directive"),
    ],
)
def test_native_alternate_include_directives_fail_closed(
    tmp_path: Path, directive: str, error: str
) -> None:
    root = _copy_root(tmp_path)
    provider = root / MODULE.RUST_CPU_PROVIDER_HEADER_PATH
    provider.write_text(
        provider.read_text(encoding="utf-8") + f"{directive}\n",
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match=error):
        MODULE.rust_cpu_bridge_source_paths(root)


def test_native_raw_string_include_ambiguity_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    provider = root / MODULE.RUST_CPU_PROVIDER_HEADER_PATH
    provider.write_text(
        provider.read_text(encoding="utf-8")
        + 'const char *raw_fixture = R"tag(/*)tag";\n',
        encoding="utf-8",
    )
    with pytest.raises(MODULE.StateBundleError, match="raw strings are unsupported"):
        MODULE.rust_cpu_bridge_source_paths(root)


def test_rust_cpu_provider_source_hash_is_derived(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    relative = Path("rust/cpu-kernel/src/kernel.rs")
    before, _authority, _release = _build(root)
    before_hashes = {row["path"]: row["sha256"] for row in before["source_inputs"]}
    path = root / relative
    path.write_bytes(path.read_bytes() + b"\n// source-hash regression fixture\n")
    after, _authority, _release = _build(root)
    after_hashes = {row["path"]: row["sha256"] for row in after["source_inputs"]}
    assert after_hashes[relative.as_posix()] != before_hashes[relative.as_posix()]
    assert after_hashes[relative.as_posix()] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_rust_cpu_bridge_private_header_hash_is_derived(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    relative = Path("native/src/cpu/neighbor_pair.hpp")
    before, _authority, _release = _build(root)
    before_hashes = {row["path"]: row["sha256"] for row in before["source_inputs"]}
    path = root / relative
    path.write_bytes(path.read_bytes() + b"\n// bridge-hash regression fixture\n")
    after, _authority, _release = _build(root)
    after_hashes = {row["path"]: row["sha256"] for row in after["source_inputs"]}
    assert after_hashes[relative.as_posix()] != before_hashes[relative.as_posix()]
    assert after_hashes[relative.as_posix()] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_invalid_or_partial_source_identity_is_rejected(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    with pytest.raises(MODULE.StateBundleError, match="source commit"):
        MODULE.build_bundle(
            root,
            source_commit="bad",
            source_tree=TREE,
            source_binding="unverified_fixture",
        )
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "out"),
            "--source-commit",
            COMMIT,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "must be supplied together" in result.stdout


def test_cli_writes_only_the_three_versioned_documents(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    commit, tree = _commit_fixture(root)
    output = tmp_path / "bundle"
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["claim_authority_granted"] is False
    assert summary["release_authorized"] is False
    assert sorted(path.name for path in output.iterdir()) == [
        "engine_v2_authority_state_v1.json",
        "engine_v2_implementation_state_v1.json",
        "engine_v2_release_manifest_v1.json",
    ]
    implementation = _load(output / "engine_v2_implementation_state_v1.json")
    release = _load(output / "engine_v2_release_manifest_v1.json")
    assert implementation["source_identity"]["binding"] == "verified_git_checkout"
    assert release["source_identity"]["binding"] == "verified_git_checkout"
    assert release["release_status"] == "unreleased_source_snapshot"
    assert release["artifacts"] == []

    repeat = tmp_path / "bundle-repeat"
    repeated = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(repeat),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    for path in output.iterdir():
        assert path.read_bytes() == (repeat / path.name).read_bytes()


def test_cli_rejects_external_generator_copy_for_verified_root(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    commit, tree = _commit_fixture(root)
    external_generator = tmp_path / "external-state-generator.py"
    shutil.copyfile(_tool(root), external_generator)
    result = subprocess.run(
        [
            sys.executable,
            str(external_generator),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "external-bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "must resolve to the verified repository generator" in result.stdout


def test_cli_accepts_symlink_to_verified_repository_generator(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    commit, tree = _commit_fixture(root)
    linked_generator = tmp_path / "linked-state-generator.py"
    linked_generator.symlink_to(_tool(root))
    result = subprocess.run(
        [
            sys.executable,
            str(linked_generator),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "linked-bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_rejects_symlinked_repository_generator_ancestor(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    commit, tree = _commit_fixture(root)
    external_tools = tmp_path / "external-tools"
    shutil.copytree(root / "tools", external_tools)
    tracked_tools = [
        path.relative_to(root)
        for path in (root / "tools").rglob("*")
        if path.is_file()
    ]
    for relative in tracked_tools:
        subprocess.run(
            ["git", "update-index", "--skip-worktree", relative.as_posix()],
            cwd=root,
            check=True,
        )
    (root / ".git/info/exclude").write_text("/tools\n", encoding="utf-8")
    shutil.rmtree(root / "tools")
    (root / "tools").symlink_to(external_tools, target_is_directory=True)
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "symlink-ancestor-bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "generator path contains a symlink component" in result.stdout


def test_cli_rejects_source_identity_not_bound_to_checkout(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    _commit, tree = _commit_fixture(root)
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--source-commit",
            COMMIT,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "does not match checkout HEAD" in result.stdout


def test_cli_rejects_untracked_source_input(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    commit, tree = _commit_fixture(root)
    untracked = root / MODULE.D1_REPOSITORY_OUTPUTS[0]
    untracked.parent.mkdir(parents=True, exist_ok=True)
    untracked.write_text("{}\n", encoding="ascii")
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "requires a clean checkout" in result.stdout


def test_cli_rejects_ignored_untracked_optional_input(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    ignored_relative = MODULE.D1_REPOSITORY_OUTPUTS[0]
    (root / ".gitignore").write_text(
        f"/{ignored_relative.as_posix()}\n", encoding="utf-8"
    )
    commit, tree = _commit_fixture(root)
    ignored = root / ignored_relative
    ignored.parent.mkdir(parents=True, exist_ok=True)
    ignored.write_text("{}\n", encoding="ascii")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "optional D1 inputs are not tracked by HEAD" in result.stdout


def test_cli_rejects_tracked_optional_input_missing_from_checkout(
    tmp_path: Path,
) -> None:
    root = _copy_root(tmp_path)
    relative = MODULE.D1_REPOSITORY_OUTPUTS[0]
    tracked = root / relative
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("{}\n", encoding="ascii")
    commit, tree = _commit_fixture(root)
    subprocess.run(
        ["git", "update-index", "--skip-worktree", relative.as_posix()],
        cwd=root,
        check=True,
    )
    tracked.unlink()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "tracked optional D1 inputs are unavailable" in result.stdout


def test_cli_rejects_skip_worktree_modified_required_input(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    commit, tree = _commit_fixture(root)
    relative = MODULE.PYTHON_PACKAGE_PATH
    subprocess.run(
        ["git", "update-index", "--skip-worktree", relative.as_posix()],
        cwd=root,
        check=True,
    )
    path = root / relative
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'version = "0.2.0rc5"', 'version = "0.2.0rc7"', 1
        ),
        encoding="utf-8",
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "consumed worktree files differ from HEAD blobs" in result.stdout


def test_cli_rejects_missing_tracked_rust_provider_source(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    commit, tree = _commit_fixture(root)
    relative = Path("rust/cpu-kernel/src/kernel.rs")
    subprocess.run(
        ["git", "update-index", "--skip-worktree", relative.as_posix()],
        cwd=root,
        check=True,
    )
    (root / relative).unlink()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    result = subprocess.run(
        [
            sys.executable,
            str(_tool(root)),
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--source-commit",
            commit,
            "--source-tree",
            tree,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Rust CPU provider source closure differs from HEAD" in result.stdout


def test_workflow_generates_every_main_push_and_uses_pinned_upload() -> None:
    workflow = (ROOT / ".github/workflows/ci-engine-v2-current-state.yml").read_text(
        encoding="utf-8"
    )
    push_block = workflow.split("  push:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert "branches:\n      - main" in push_block
    assert "paths:" not in push_block
    assert "tools/generate_engine_v2_state_bundle_v1.py" in workflow
    assert "config/engine_v2_authority_state_v1.json" in workflow
    assert '      - "rust/**"' in workflow
    assert '      - "native/src/**"' in workflow
    assert '      - "include/**"' in workflow
    assert '      - ".cargo/**"' in workflow
    assert "Set up Python 3.10" in workflow
    assert 'python-version: "3.10"' in workflow
    assert "pytest==8.3.5" in workflow
    assert "tomli==2.2.1; python_version < '3.11'" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "persist-credentials: false" in workflow
    assert "cancel-in-progress: false" in workflow
    assert (
        "group: ci-engine-v2-current-state-"
        "${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    )
    assert '--output-dir "${RUNNER_TEMP}/engine-v2-state-bundle"' in workflow
    assert "path: ${{ runner.temp }}/engine-v2-state-bundle" in workflow
