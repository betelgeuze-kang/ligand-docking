from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    assert result["source_count"] == 238
    assert result["source_count"] == profile["implementation"][
        "source_manifest_entry_count"
    ]
    assert profile["abi"]["public_symbol_count"] == 13
    assert profile["abi"]["checkpoint_magic"] == "BGPME001"
    assert profile["abi"]["checkpoint_header_size_bytes"] == 104
    assert not profile["abi"]["abi_changed"]
    assert not profile["abi"]["checkpoint_format_changed"]


def test_predecessor_identity_and_optional_reviewed_heads_are_frozen() -> None:
    verifier.require_predecessor()
    assert verifier.PREDECESSOR == {
        "pull_request": 450,
        "reviewed_head": "b0e26a8b2eea995a6038a484894808387486ff9e",
        "merge_commit": "75d3a4e2b7ba5b0f1dcf99007358f6f2c47c7330",
        "merge_tree": "03ccd07339b71eafa435a9b2012d2ab6a863d4d9",
        "profile_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "short_parent_force_scratch_profile_v1.json"
        ),
        "profile_sha256": (
            "cc7c92719b832c847f213ea02b9a46e75bfd7e79b291c28af59b24f5b0478d3f"
        ),
        "source_manifest_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "short_parent_force_scratch_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "c19ec3eb610bc07978b7cb96b0368043f9084a91d344c8515fa75140bb27c7f6"
        ),
        "source_manifest_entry_count": 226,
    }
    assert verifier.ARCHITECTURE_PREDECESSOR == {
        "pull_request": 451,
        "reviewed_head": "b09f1dd125e1bb6aaf255cc2f3fb737ca4d9f475",
        "merge_commit": "0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a",
        "merge_tree": "124539c1d14f5cbc0f3d91d231d6a40736f58f5a",
        "profile_path": (
            "config/engine_v2_native_direct_ewald_composite_dynamics_"
            "combined_force_soa_profile_v1.json"
        ),
        "profile_sha256": (
            "50c50ba44f9d3ff32358454d0d9f81f2619265fdaa5a3e9fe9194f22848685b7"
        ),
        "source_manifest_path": (
            "config/engine_v2_native_direct_ewald_composite_dynamics_"
            "combined_force_soa_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "348ab691558af31b398c653d0c6399bc30c651bc7cc911edb35aedcda2ec9032"
        ),
        "source_manifest_entry_count": 232,
    }
    assert verifier.INHERITED_PREDECESSOR == {
        "pull_request": 445,
        "reviewed_head": "801a85d56846c464b3a618ecacca867cd12a8c9f",
        "merge_commit": "c53f7993ec06c4ac04a4907b40f179d12fbe309a",
        "merge_tree": "2bb25b756b802671bcfc5f3ac95b26df3b284956",
        "profile_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "force_scratch_profile_v1.json"
        ),
        "profile_sha256": (
            "32129a32d0b351ac265fda21906e707cc708c664241715b4d0d92fa3cc013b62"
        ),
        "source_manifest_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "force_scratch_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "d428b3f18d26382fbb7e5e8a48f3a114eb953b8708bec77c4f00ec6c0d1bcc3f"
        ),
        "source_manifest_entry_count": 194,
    }


def test_predecessor_manifest_mutations_fail_closed() -> None:
    raw = (ROOT / verifier.PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["sha256"] = "x" * 64
    with pytest.raises(ValueError, match="row value drift"):
        verifier.require_manifest_shape(verifier.canonical_bytes(manifest), 226)
    with pytest.raises(ValueError, match="count drift"):
        verifier.require_manifest_shape(raw, 225)


def test_architecture_manifest_mutations_fail_closed() -> None:
    raw = (ROOT / verifier.ARCHITECTURE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["sha256"] = "x" * 64
    with pytest.raises(ValueError, match="row value drift"):
        verifier.require_architecture_manifest_shape(
            verifier.canonical_bytes(manifest), 232
        )
    with pytest.raises(ValueError, match="count drift"):
        verifier.require_architecture_manifest_shape(raw, 231)


def test_inherited_manifest_mutations_fail_closed() -> None:
    raw = (ROOT / verifier.INHERITED_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["path"] = "../escape"
    with pytest.raises(ValueError, match="row value drift"):
        verifier.require_manifest_shape(verifier.canonical_bytes(manifest), 194)
    with pytest.raises(ValueError, match="count drift"):
        verifier.require_manifest_shape(raw, 193)


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
    assert verifier.ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix() in paths
    assert verifier.ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix() in paths


def test_delta_path_set_is_exact() -> None:
    assert len(verifier.EXPECTED_DELTA_PATHS) == 15
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS
    assert set(verifier.IMPLEMENTATION_DELTA_PATHS) <= set(
        verifier.EXPECTED_DELTA_PATHS
    )


def test_trigger_path_set_statically_closes_architecture_evidence() -> None:
    architecture_evidence = {
        verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix(),
        verifier.ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
        verifier.ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
        (
            "docs/engine_v2_native_direct_ewald_composite_dynamics_"
            "combined_force_soa_v1.md"
        ),
        (
            "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_"
            "combined_force_soa_v1.py"
        ),
        verifier.PREDECESSOR_UNIT_RELATIVE_PATH.as_posix(),
    }
    assert len(verifier.REQUIRED_TRIGGER_PATHS) == 54
    assert len(set(verifier.REQUIRED_TRIGGER_PATHS)) == 54
    assert architecture_evidence <= set(verifier.REQUIRED_TRIGGER_PATHS)


def test_profile_is_narrow_and_all_authority_is_false() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    for field in (
        "stateful_force_output_pointer_required_iff_stateful_forceful",
        "successful_stateful_forceful_direct_final_soa_recording",
        "successful_stateful_forceful_combined_aos_materialization_eliminated",
        "successful_stateful_forceful_combined_aos_to_soa_copy_eliminated",
        "stateless_combined_aos_path_preserved",
        "stateful_force_free_path_preserved",
        "final_soa_force_storage_reused",
        "short_system_scratch_contract_preserved",
        "short_parent_force_scratch_contract_preserved",
        "short_parent_output_alias_rejected",
        "parent_shape_and_component_finiteness_checked_before_final_soa_write",
        "final_soa_resize_after_all_parent_validation",
        "late_direct_local_failure_precedes_final_soa_write",
        "final_soa_scratch_is_derived_non_authoritative",
        "late_direct_local_failure_last_successful_final_soa_bits_preserved",
        "explicit_cpp_cpu_reference_lane",
        "explicit_rust_cpu_lane",
        "test_only_owner_introspection_not_exported",
    ):
        assert implementation[field]
    for field in (
        "final_soa_scratch_serialized_in_checkpoint",
        "final_soa_scratch_bound_into_static_fingerprint",
        "unconditional_failure_storage_retention_claimed",
        "upstream_failure_storage_retention_claimed",
        "universal_failure_storage_retention_claimed",
        "all_failure_path_storage_retention_claimed",
        "allocation_failure_storage_identity_claimed",
        "resize_failure_storage_retention_claimed",
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
    assert profile["target_predecessor"] == verifier.PREDECESSOR
    assert profile["architecture_predecessor"] == verifier.ARCHITECTURE_PREDECESSOR
    assert profile["inherited_final_soa_predecessor"] == verifier.INHERITED_PREDECESSOR
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


def test_production_delta_is_exact_and_vendor_identical() -> None:
    verifier.require_combined_force_soa_contract(ROOT)
    for name, digest in verifier.EXPECTED_PRODUCTION_SOURCE_SHA256.items():
        native = (ROOT / "native/src/composite" / name).read_bytes()
        vendor = (
            ROOT / "rust/betelgeuze-sys/vendor/native/src/composite" / name
        ).read_bytes()
        assert native == vendor
        assert verifier.sha(native) == digest


@pytest.mark.parametrize(
    "transform",
    [
        verifier.expected_particle_mesh_ewald_source,
        verifier.expected_dynamics_source,
        verifier.expected_evaluator_header,
    ],
)
def test_production_transforms_reject_missing_insertion_point(transform) -> None:
    with pytest.raises(ValueError, match="transformation point drift"):
        transform("bounded transformation anchor is absent")


@pytest.mark.parametrize(
    "relative_path,transform,sentinel",
    [
        (
            "native/src/composite/particle_mesh_ewald_composite.cpp",
            verifier.expected_particle_mesh_ewald_source,
            '#include "betelgeuze/particle_mesh_ewald_composite.h"\n',
        ),
        (
            "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp",
            verifier.expected_dynamics_source,
            '#include "particle_mesh_ewald_composite_dynamics.hpp"\n',
        ),
        (
            "native/src/composite/particle_mesh_ewald_composite_evaluator.hpp",
            verifier.expected_evaluator_header,
            "#include <vector>\n",
        ),
    ],
)
def test_production_transforms_are_derived_from_frozen_input(
    relative_path: str,
    transform,
    sentinel: str,
) -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:{relative_path}",
    ).stdout.decode()
    current = (ROOT / relative_path).read_text()
    assert transform(frozen) == current
    marker = "// bounded-frozen-input-sentinel\n"
    assert frozen.count(sentinel) == 1
    assert current.count(sentinel) == 1
    mutated = frozen.replace(sentinel, sentinel + marker, 1)
    assert transform(mutated) == current.replace(sentinel, sentinel + marker, 1)


def test_conditionally_disabled_final_soa_regression_fails_closed() -> None:
    test = (
        ROOT / "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_bytes()
    disabled = test.replace(
        b"    verify_force_output_scratch_reuse();\n",
        b"    if (false) { verify_force_output_scratch_reuse(); }\n",
        1,
    )
    assert disabled != test
    with pytest.raises(
        ValueError, match="exact particle-mesh Ewald dynamics regression source drift"
    ):
        verifier.require_exact_regression_source(disabled)


def test_stateful_provider_contains_no_combined_aos_copy() -> None:
    source = (
        ROOT / "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_text()
    provider = source.split("bg_status evaluate_composite_provider(", 1)[1].split(
        "bg_status validate_particle_view_descriptor(", 1
    )[0]
    for token in (
        "cpu::Evaluation candidate;",
        "candidate.force_x",
        "candidate.force_y",
        "candidate.force_z",
        "combined.forces",
        "*out_evaluation = std::move(candidate);",
    ):
        assert token not in provider


def test_predecessor_workflow_freeze_is_exact() -> None:
    verifier.require_predecessor_workflow_freeze(ROOT)
    frozen = verifier.git(
        "show",
        f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:"
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
        f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_UNIT_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    expected = verifier.expected_frozen_predecessor_unit(frozen)
    assert expected == (
        ROOT / verifier.PREDECESSOR_UNIT_RELATIVE_PATH
    ).read_text()


@pytest.mark.parametrize(
    "old,new",
    [
        (
            "    PARTICLE_MESH_EWALD_COMBINED_FORCE_SOA_EVIDENCE_PRESENT,\n",
            "    False,\n",
        ),
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


@pytest.mark.parametrize(
    "old,new",
    [
        ("        shell: bash\n", "        shell: sh\n"),
        (
            "          frozen=0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a\n",
            "          frozen=HEAD\n",
        ),
        (
            "          git checkout --detach --quiet \"$frozen\"\n",
            "          true # detached checkout removed\n",
        ),
    ],
)
def test_predecessor_workflow_freeze_mutation_fails_closed(
    tmp_path: Path,
    old: str,
    new: str,
) -> None:
    relative = verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    current = (ROOT / relative).read_text()
    assert old in current
    destination.write_text(current.replace(old, new, 1))
    with pytest.raises(ValueError, match="predecessor workflow freeze drift"):
        verifier.require_predecessor_workflow_freeze(tmp_path)


def test_workflow_is_pinned_cpu_only_and_fetches_predecessor() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count(verifier.PINNED_CHECKOUT_ACTION) == 4
    assert "permissions:\n  contents: read" in text
    assert text.count(verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL) == 1
    for pull_request in (451, 450, 445):
        assert text.count(f"refs/pull/{pull_request}/head") == 1
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


@pytest.mark.parametrize(
    "injected",
    [
        '"defaults":\n  run:\n    shell: "/bin/true {0}"\n',
        "'defaults':\n  run:\n    shell: \"/bin/true {0}\"\n",
        '"\\u0064efaults":\n  run:\n    shell: "/bin/true {0}"\n',
        '!!str defaults:\n  run:\n    shell: "/bin/true {0}"\n',
        '? defaults\n:\n  run:\n    shell: "/bin/true {0}"\n',
        (
            '"defaults": &root_defaults\n'
            '  run:\n    shell: "/bin/true {0}"\n'
        ),
        '"defaults": {run: {shell: "/bin/true {0}"}}\n',
        (
            "jobs:\n  'bypass':\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: true\n"
        ),
    ],
)
def test_quoted_root_and_job_key_bypasses_fail_closed(injected: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    if injected.startswith("jobs:\n"):
        mutated = text.replace("jobs:\n", injected, 1)
    else:
        mutated = text.replace("permissions:\n", injected + "permissions:\n", 1)
    with pytest.raises(ValueError, match="workflow exact document drift"):
        verifier.require_workflow_contract(mutated)


@pytest.mark.parametrize(
    "anchor,injected",
    [
        (
            "  immutable-evidence:\n    runs-on: ubuntu-latest\n",
            "  immutable-evidence:\n    'if': false\n"
            "    runs-on: ubuntu-latest\n",
        ),
        (
            "      - name: Synthetic release and sanitizer regressions\n"
            "        run: |\n",
            "      - name: Synthetic release and sanitizer regressions\n"
            "        'env': {BYPASS: '1'}\n"
            "        run: |\n",
        ),
        (
            "      - name: Synthetic release and sanitizer regressions\n"
            "        run: |\n",
            "      - name: Synthetic release and sanitizer regressions\n"
            "        'shell': '/bin/true {0}'\n"
            "        run: |\n",
        ),
    ],
)
def test_quoted_job_and_step_bypasses_fail_closed(
    anchor: str, injected: str
) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert anchor in text
    with pytest.raises(ValueError, match="workflow exact job body drift"):
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
        "          git merge-base --is-ancestor 0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a HEAD\n",
        "          git fetch --no-tags --depth=1 origin refs/pull/445/head\n",
        "          cmake --build build/particle-mesh-ewald-combined-force-soa-release --target betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2\n",
        "          ctest --test-dir build/particle-mesh-ewald-combined-force-soa-release -R '^betelgeuze_engine_(particle_mesh_ewald_composite_dynamics|export_allowlist)$' --output-on-failure\n",
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
            "python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.py",
            "python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.py --refresh",
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
        '      - "docs/engine_v2_native_direct_ewald_composite_'
        'dynamics_backend_preflight_v1.md"\n'
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
