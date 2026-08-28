from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_force_scratch_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    assert result["source_count"] == 194
    assert result["source_count"] == profile["implementation"][
        "source_manifest_entry_count"
    ]
    assert profile["abi"]["public_symbol_count"] == 13
    assert profile["abi"]["checkpoint_magic"] == "BGPME001"
    assert profile["abi"]["checkpoint_header_size_bytes"] == 104
    assert not profile["abi"]["abi_changed"]
    assert not profile["abi"]["checkpoint_format_changed"]


def test_predecessor_identity_and_optional_reviewed_head_are_frozen() -> None:
    verifier.require_predecessor()
    assert verifier.PREDECESSOR == {
        "pull_request": 444,
        "reviewed_head": "84dcdf4759e1d182d52502f157a2d551bfad68a4",
        "merge_commit": "6499ef99ed5b7b3a374b9f4ab15bc43057f44cf3",
        "merge_tree": "531399ae05897624439f561402b7d51d76a21cad",
        "profile_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "profile_v1.json"
        ),
        "profile_sha256": (
            "acca244232d196701044fd9ecbf6a2abce91cd03be966ead875c61cf42f75bab"
        ),
        "source_manifest_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "030264269b2c438c11013c1e5a62e8c9745abcdf8567771ce990cf2f33e14f78"
        ),
        "source_manifest_entry_count": 186,
    }


def test_predecessor_manifest_mutations_fail_closed() -> None:
    raw = (ROOT / verifier.PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["sha256"] = "x" * 64
    with pytest.raises(ValueError, match="row value drift"):
        verifier.require_manifest_shape(verifier.canonical_bytes(manifest), 186)
    with pytest.raises(ValueError, match="count drift"):
        verifier.require_manifest_shape(raw, 185)


def test_source_manifest_is_canonical_sorted_and_acyclic() -> None:
    raw = (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    assert raw == verifier.canonical_bytes(manifest)
    paths = [row["path"] for row in manifest["files"]]
    assert paths == sorted(set(paths))
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in paths
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in paths
    assert verifier.PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix() in paths
    assert verifier.PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix() in paths


def test_delta_path_set_is_exact() -> None:
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS
    assert set(verifier.IMPLEMENTATION_DELTA_PATHS) <= set(
        verifier.EXPECTED_DELTA_PATHS
    )


def test_profile_is_narrow_and_all_authority_is_false() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    assert implementation["persistent_final_soa_force_output_storage"]
    assert implementation["storage_transfer_after_upstream_success_only"]
    assert implementation["explicit_cpp_cpu_reference_lane"]
    assert implementation["explicit_rust_cpu_lane"]
    assert implementation["test_only_owner_introspection_not_exported"]
    for field in (
        "allocation_free_claimed",
        "timing_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "cross_lane_bit_parity_claimed",
        "fixed64_cpu_v7_qualification_invoked",
        "hip_device_execution_invoked",
        "molecular_execution_invoked",
    ):
        assert not implementation[field]
    assert profile["authority"] == verifier.AUTHORITY
    assert not any(profile["authority"].values())
    assert profile["operational_boundary"] == {
        "blockers": verifier.BLOCKERS,
        "unresolved_operational_decisions": 32,
    }


@pytest.mark.parametrize("field", sorted(verifier.AUTHORITY))
def test_authority_mutations_differ_from_canonical_profile(field: str) -> None:
    manifest_raw = (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    profile = verifier.build_profile(manifest_raw)
    profile["authority"][field] = True
    assert profile != verifier.build_profile(manifest_raw)


def test_all_public_symbol_surfaces_are_exactly_thirteen() -> None:
    surfaces = verifier.extract_public_symbol_surfaces(ROOT)
    assert set(surfaces) == {
        "header",
        "native",
        "linux_map",
        "darwin_exports",
        "check_exports",
        "rust_sys",
    }
    assert all(symbols == verifier.PUBLIC_SYMBOLS for symbols in surfaces.values())


def test_fourteenth_namespace_symbol_is_detected() -> None:
    header = (
        ROOT / "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h"
    ).read_text()
    symbols = tuple(
        symbol
        for symbol in __import__("re").findall(
            r"\b(bg_[a-z0-9_]+)\s*\(",
            header + "\nbg_particle_mesh_ewald_composite_dynamics_extra(",
        )
        if verifier.is_dynamics_symbol(symbol)
    )
    assert symbols != verifier.PUBLIC_SYMBOLS


def test_provider_delta_is_exact_and_vendor_identical() -> None:
    verifier.require_force_scratch_contract(ROOT)
    native = (
        ROOT / "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_bytes()
    vendor = (
        ROOT
        / "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.cpp"
    ).read_bytes()
    assert native == vendor
    assert native.count(b"std::move(out_evaluation->force_") == 3


def test_provider_transform_rejects_missing_insertion_point() -> None:
    with pytest.raises(ValueError, match="provider insertion point drift"):
        verifier.expected_force_scratch_source("cpu::Evaluation candidate;")


def test_conditionally_disabled_force_scratch_regression_fails_closed() -> None:
    test = (
        ROOT / "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_text()
    helper = (
        ROOT / "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp"
    ).read_text()
    header = (
        ROOT / "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp"
    ).read_text()
    disabled = test.replace(
        "    verify_force_output_scratch_reuse();\n",
        "    if (false) { verify_force_output_scratch_reuse(); }\n",
        1,
    )
    assert disabled.count("verify_force_output_scratch_reuse();") == 1
    with pytest.raises(ValueError, match="exact PME dynamics regression source drift"):
        verifier.require_exact_regression_sources(disabled, helper, header)


@pytest.mark.parametrize("kind", ["helper", "header"])
def test_test_only_scratch_introspection_drift_fails_closed(kind: str) -> None:
    test = (
        ROOT / "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_text()
    helper = (
        ROOT / "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp"
    ).read_text()
    header = (
        ROOT / "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp"
    ).read_text()
    if kind == "helper":
        helper += "// drift\n"
        expected = "exact scratch helper source drift"
    else:
        header += "// drift\n"
        expected = "exact scratch helper header source drift"
    with pytest.raises(ValueError, match=expected):
        verifier.require_exact_regression_sources(test, helper, header)


def test_predecessor_workflow_freeze_is_exact() -> None:
    verifier.require_predecessor_workflow_freeze(ROOT)
    frozen = verifier.git(
        "show",
        f"{verifier.PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    expected = verifier.expected_frozen_predecessor_workflow(frozen)
    assert expected == (
        ROOT / verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH
    ).read_text()


def test_predecessor_unit_freeze_is_exact() -> None:
    verifier.require_predecessor_unit_freeze(ROOT)
    frozen = verifier.git(
        "show",
        f"{verifier.PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_UNIT_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    expected = verifier.expected_frozen_predecessor_unit(frozen)
    assert expected == (
        ROOT / verifier.PREDECESSOR_UNIT_RELATIVE_PATH
    ).read_text()


@pytest.mark.parametrize(
    "old,new",
    [
        ("    FORCE_SCRATCH_EVIDENCE_PRESENT,\n", "    False,\n"),
        (").is_file()\n", ").is_dir()\n"),
        ("pytestmark = pytest.mark.skipif(\n", "pytestmark = pytest.mark.xfail(\n"),
    ],
)
def test_predecessor_unit_freeze_mutation_fails_closed(
    tmp_path: Path,
    old: str,
    new: str,
) -> None:
    relative = verifier.PREDECESSOR_UNIT_RELATIVE_PATH
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    current = (ROOT / relative).read_text()
    assert current.count(old) == 1
    destination.write_text(current.replace(old, new, 1))
    with pytest.raises(ValueError, match="predecessor unit freeze drift"):
        verifier.require_predecessor_unit_freeze(tmp_path)


def test_workflow_is_pinned_cpu_only_and_fetches_predecessor() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count(verifier.PINNED_CHECKOUT_ACTION) == 4
    assert "permissions:\n  contents: read" in text
    assert text.count(verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL) == 1
    verifier.require_workflow_contract(text)


@pytest.mark.parametrize(
    "anchor,injected",
    [
        ("  immutable-evidence:\n", "  immutable-evidence:\n    if: false\n"),
        (
            "  native-linux:\n",
            "  native-linux:\n    continue-on-error: true\n",
        ),
        (
            "      - name: Synthetic release and sanitizer regressions\n",
            "      - name: Synthetic release and sanitizer regressions\n"
            "        if: false\n",
        ),
        ("jobs:\n", "jobs:\n  defaults:\n    run:\n      shell: true\n"),
    ],
)
def test_conditional_and_error_bypasses_fail_closed(
    anchor: str, injected: str
) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert anchor in text
    with pytest.raises(ValueError, match="bypasses are forbidden"):
        verifier.require_workflow_contract(text.replace(anchor, injected, 1))


def test_checkout_credentials_mutation_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count("persist-credentials: false") == 4
    with pytest.raises(ValueError, match="exact job body drift"):
        verifier.require_workflow_contract(
            text.replace("persist-credentials: false", "persist-credentials: true", 1)
        )


@pytest.mark.parametrize(
    "command",
    [
        "          git merge-base --is-ancestor 6499ef99ed5b7b3a374b9f4ab15bc43057f44cf3 HEAD\n",
        "          git fetch --no-tags --depth=1 origin refs/pull/444/head\n",
        "          cmake --build build/pme-force-scratch-release --target betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2\n",
        "          ctest --test-dir build/pme-force-scratch-release -R '^betelgeuze_engine_(particle_mesh_ewald_composite_dynamics|export_allowlist)$' --output-on-failure\n",
    ],
)
def test_commented_token_command_bypasses_fail_closed(command: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count(command) == 1
    bypassed = text.replace(command, f"          true # {command.strip()}\n", 1)
    with pytest.raises(ValueError):
        verifier.require_workflow_contract(bypassed)


def test_extra_job_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    extra = (
        "  ignored-regression:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: true\n\n"
    )
    mutated = text.replace("  native-linux:\n", f"{extra}  native-linux:\n", 1)
    with pytest.raises(ValueError, match="job set or ordering drift"):
        verifier.require_workflow_contract(mutated)


@pytest.mark.parametrize(
    "component", [" --component rustfmt", " --component clippy"]
)
def test_rust_component_removal_fails_closed(component: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    with pytest.raises(ValueError, match="toolchain/component installation drift"):
        verifier.require_workflow_contract(text.replace(component, "", 1))


@pytest.mark.parametrize(
    "next_job_header",
    [
        "macos-export-boundary:",
        "macos_export_boundary:",
        "MacosExportBoundary:",
        '"macos-export-boundary":',
        "macos-export-boundary: # next job",
    ],
)
def test_rust_component_relocation_fails_closed(next_job_header: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    text = text.replace(
        "  macos-export-boundary:\n", f"  {next_job_header}\n", 1
    )
    full_step = (
        "      - name: Select frozen Rust components\n"
        "        run: |\n"
        f"          {verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    minimal_step = (
        "      - name: Select frozen Rust toolchain\n"
        "        run: |\n"
        f"          {verifier.MINIMAL_RUST_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    relocated = text.replace(full_step, "", 1)
    before, found, after = relocated.rpartition(minimal_step)
    assert found == minimal_step
    relocated = f"{before}{full_step}{after}"
    with pytest.raises(ValueError):
        verifier.require_workflow_contract(relocated)


def test_rust_component_install_after_commands_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    full_step = (
        "      - name: Select frozen Rust components\n"
        "        run: |\n"
        f"          {verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    moved = text.replace(full_step, "", 1).replace(
        verifier.RUST_BOUNDARY_COMMAND_STEP,
        verifier.RUST_BOUNDARY_COMMAND_STEP + full_step,
        1,
    )
    with pytest.raises(ValueError, match="immediately precede"):
        verifier.require_workflow_contract(moved)


def test_duplicate_noop_rust_command_step_name_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    duplicate = (
        "      - name: Existing Rust regression, docs, and clean packages\n"
        "        run: echo duplicate-name sentinel\n"
    )
    mutated = text.replace(
        "  macos-export-boundary:\n",
        f"{duplicate}  macos-export-boundary:\n",
        1,
    )
    with pytest.raises(ValueError, match="exactly one named command step"):
        verifier.require_workflow_contract(mutated)


@pytest.mark.parametrize(
    "command",
    [
        "          cargo fmt --manifest-path rust/Cargo.toml --all -- --check\n",
        "          cargo clippy --manifest-path rust/Cargo.toml --locked --package betelgeuze-sys --package betelgeuze-runtime --all-targets -- -D warnings\n",
    ],
)
def test_exact_rust_command_removal_fails_closed(command: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count(command) == 1
    with pytest.raises(ValueError, match="exact command step"):
        verifier.require_workflow_contract(text.replace(command, "", 1))


@pytest.mark.parametrize(
    "old,new",
    [
        ("DBG_ENABLE_HIP=OFF", "DBG_ENABLE_HIP=ON"),
        ("contents: read", "contents: write"),
        ("runs-on: ubuntu-latest", "runs-on: self-hosted"),
        ("workflow_dispatch:", "pull_request_target:"),
        (
            "python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_force_scratch_v1.py",
            "python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_force_scratch_v1.py --refresh",
        ),
    ],
)
def test_workflow_security_mutations_fail_closed(old: str, new: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    with pytest.raises(ValueError):
        verifier.require_workflow_contract(text.replace(old, new, 1))


def test_trigger_path_removal_and_paths_ignore_fail_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    predecessor = (
        '      - "docs/engine_v2_native_particle_mesh_ewald_composite_'
        'dynamics_v1.md"\n'
    )
    assert text.count(predecessor) == 2
    with pytest.raises(ValueError, match="path trigger set drift"):
        verifier.require_workflow_contract(text.replace(predecessor, "", 1))
    with pytest.raises(ValueError, match="exactly one paths key"):
        verifier.require_workflow_contract(
            text.replace("    paths:\n", "    paths-ignore:\n")
        )


def test_nested_permissions_and_accelerator_env_fail_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    with pytest.raises(ValueError, match="exactly one global"):
        verifier.require_workflow_contract(
            text.replace("jobs:\n", "jobs:\n  permissions: write-all\n", 1)
        )
    with pytest.raises(ValueError, match="global empty HIP_VISIBLE_DEVICES"):
        verifier.require_workflow_contract(
            text.replace("jobs:\n", 'jobs:\n  HIP_VISIBLE_DEVICES: ""\n', 1)
        )


def test_cpu_environment_relocation_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    global_block = (
        'env:\n  CUDA_VISIBLE_DEVICES: ""\n  HIP_VISIBLE_DEVICES: ""\n'
        '  ROCR_VISIBLE_DEVICES: ""\n\njobs:'
    )
    job_block = (
        'jobs:\n  env:\n    CUDA_VISIBLE_DEVICES: ""\n'
        '    HIP_VISIBLE_DEVICES: ""\n    ROCR_VISIBLE_DEVICES: ""'
    )
    assert global_block in text
    with pytest.raises(ValueError, match="global CPU-only environment"):
        verifier.require_workflow_contract(text.replace(global_block, job_block, 1))


def test_each_cmake_configuration_disables_hip_independently() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    mutated = text.replace("DBG_ENABLE_HIP=OFF", "HIP_OFF_REMOVED", 1)
    mutated = mutated.replace(
        "DBG_ENABLE_HIP=OFF", "DBG_ENABLE_HIP=OFF DBG_ENABLE_HIP=OFF", 1
    )
    with pytest.raises(ValueError, match="independently disable"):
        verifier.require_workflow_contract(mutated)
