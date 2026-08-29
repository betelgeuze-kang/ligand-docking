from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    assert result["source_count"] == 220
    assert result["source_count"] == profile["implementation"][
        "source_manifest_entry_count"
    ]
    assert profile["abi"]["public_symbol_count"] == 13
    assert profile["abi"]["checkpoint_magic"] == "BGDEC001"
    assert profile["abi"]["checkpoint_header_size_bytes"] == 104
    assert not profile["abi"]["abi_changed"]
    assert not profile["abi"]["checkpoint_format_changed"]


def test_predecessor_identity_and_optional_reviewed_head_are_frozen() -> None:
    verifier.require_predecessor()
    assert verifier.PREDECESSOR == {
        "pull_request": 447,
        "reviewed_head": "5d4d238a2eea2765b6ac5d5d3f596487bd5b8cd6",
        "merge_commit": "3f68361985e57f4c5ee547ba690f4a6859bd8b34",
        "merge_tree": "1fc25fdc53ae1d2303a6fe6abe279e520fc13f12",
        "profile_path": (
            "config/engine_v2_native_direct_ewald_composite_dynamics_"
            "short_system_scratch_profile_v1.json"
        ),
        "profile_sha256": (
            "8be1f7d28f936f78486bfabaf9fdfc2e1e334285864138639c796d36a454d3cb"
        ),
        "source_manifest_path": (
            "config/engine_v2_native_direct_ewald_composite_dynamics_"
            "short_system_scratch_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "85c17310e995b8eb22028083694f710414e523884a0ae9834b5258dfcb6c48fd"
        ),
        "source_manifest_entry_count": 208,
    }
    assert verifier.ARCHITECTURE_PREDECESSOR == {
        "pull_request": 448,
        "reviewed_head": "4ace5d02dd90618140baecfeba28fdf93f3b342f",
        "merge_commit": "5d4a55c85a80b62d38e79ea608e4850a6966ceeb",
        "merge_tree": "1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73",
        "profile_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "short_system_scratch_profile_v1.json"
        ),
        "profile_sha256": (
            "72982489ea675272607013d9495f36ea5f649eb94f57d35e6a37a9e8ebfef476"
        ),
        "source_manifest_path": (
            "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "short_system_scratch_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "691792ba1f59fb314bd7c4dc8b6ae746f25629a840b9e64da6b3f54eba561028"
        ),
        "source_manifest_entry_count": 214,
    }
    assert verifier.INHERITED_PREDECESSOR == {
        "pull_request": 446,
        "reviewed_head": "5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7",
        "merge_commit": "29edcd1ea18e9fb64b9d416a0d05d87e0485be4b",
        "merge_tree": "77f5298c291130f7ea86b96bd13b6bd9596f6850",
        "profile_path": (
            "config/engine_v2_native_direct_ewald_composite_dynamics_"
            "force_scratch_profile_v1.json"
        ),
        "profile_sha256": (
            "2c1a5c015cd4db903e359e6d18fb52ee70c583e1c2744409754b44352d201985"
        ),
        "source_manifest_path": (
            "config/engine_v2_native_direct_ewald_composite_dynamics_"
            "force_scratch_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "f1c41ad4ad774bd2d7ab1672df61792ad539f0c2c199b37511ed0f5783412467"
        ),
        "source_manifest_entry_count": 202,
    }


def test_predecessor_manifest_mutations_fail_closed() -> None:
    raw = (ROOT / verifier.PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["sha256"] = "x" * 64
    with pytest.raises(ValueError, match="row value drift"):
        verifier.require_manifest_shape(verifier.canonical_bytes(manifest), 208)
    with pytest.raises(ValueError, match="count drift"):
        verifier.require_manifest_shape(raw, 207)


def test_architecture_manifest_mutations_fail_closed() -> None:
    raw = (ROOT / verifier.ARCHITECTURE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["sha256"] = "x" * 64
    with pytest.raises(ValueError, match="row value drift"):
        verifier.require_architecture_manifest_shape(
            verifier.canonical_bytes(manifest), 214
        )
    with pytest.raises(ValueError, match="count drift"):
        verifier.require_architecture_manifest_shape(raw, 213)


def test_inherited_manifest_mutations_fail_closed() -> None:
    raw = (ROOT / verifier.INHERITED_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["path"] = "../escape"
    with pytest.raises(ValueError, match="row value drift"):
        verifier.require_manifest_shape(verifier.canonical_bytes(manifest), 202)
    with pytest.raises(ValueError, match="count drift"):
        verifier.require_manifest_shape(raw, 201)


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
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS
    assert set(verifier.IMPLEMENTATION_DELTA_PATHS) <= set(
        verifier.EXPECTED_DELTA_PATHS
    )


def test_profile_is_narrow_and_all_authority_is_false() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    assert implementation["owner_persistent_short_parent_evaluation_scratch"]
    assert implementation["stateful_scratch_and_cache_pointers_all_or_none"]
    assert implementation[
        "steady_state_successful_forceful_short_parent_three_vector_storage_reuse"
    ]
    assert implementation["force_free_stateful_local_evaluation_path"]
    assert implementation["force_free_short_parent_scratch_and_cache_unchanged"]
    assert implementation["stateless_local_evaluation_path_preserved"]
    assert implementation[
        "dynamics_output_alias_guard_includes_short_parent_scratch"
    ]
    assert implementation[
        "short_parent_scratch_and_cache_are_derived_non_authoritative"
    ]
    assert not implementation["short_parent_scratch_serialized_in_checkpoint"]
    assert not implementation["rust_validation_cache_serialized_in_checkpoint"]
    assert not implementation["short_parent_scratch_bound_into_static_fingerprint"]
    assert not implementation[
        "rust_validation_cache_bound_into_static_fingerprint"
    ]
    assert implementation["late_downstream_failure_storage_identity_checked"]
    assert not implementation["unconditional_failure_storage_retention_claimed"]
    assert not implementation["upstream_failure_storage_retention_claimed"]
    assert not implementation["all_failure_path_storage_retention_claimed"]
    assert implementation["existing_short_system_scratch_contract_preserved"]
    assert implementation["existing_final_soa_force_output_storage_preserved"]
    assert implementation["explicit_cpp_cpu_reference_lane"]
    assert implementation["explicit_rust_cpu_lane"]
    assert implementation["test_only_owner_introspection_not_exported"]
    assert profile["target_predecessor"] == verifier.PREDECESSOR
    assert profile["architecture_predecessor"] == verifier.ARCHITECTURE_PREDECESSOR
    assert (
        profile["inherited_force_scratch_predecessor"]
        == verifier.INHERITED_PREDECESSOR
    )
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
        ROOT / "include/betelgeuze/direct_ewald_composite_dynamics.h"
    ).read_text()
    symbols = tuple(
        symbol
        for symbol in __import__("re").findall(
            r"\b(bg_[a-z0-9_]+)\s*\(",
            header + "\nbg_direct_ewald_composite_dynamics_extra(",
        )
        if verifier.is_dynamics_symbol(symbol)
    )
    assert symbols != verifier.PUBLIC_SYMBOLS


def test_production_delta_is_exact_and_vendor_identical() -> None:
    verifier.require_short_parent_force_scratch_contract(ROOT)
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
        verifier.expected_direct_ewald_source,
        verifier.expected_dynamics_source,
        verifier.expected_dynamics_header,
        verifier.expected_evaluator_header,
    ],
)
def test_production_transforms_reject_missing_insertion_point(transform) -> None:
    with pytest.raises(ValueError, match="transformation point drift"):
        transform("bounded transformation anchor is absent")


def test_conditionally_disabled_short_parent_regression_fails_closed() -> None:
    test = (
        ROOT / "native/tests/direct_ewald_composite_dynamics.cpp"
    ).read_text()
    helper = (
        ROOT / "native/tests/direct_ewald_composite_dynamics_scratch.cpp"
    ).read_text()
    header = (
        ROOT / "native/tests/direct_ewald_composite_dynamics_scratch.hpp"
    ).read_text()
    disabled = test.replace(
        "    verify_short_parent_force_scratch_reuse();\n",
        "    if (false) { verify_short_parent_force_scratch_reuse(); }\n",
        1,
    )
    assert disabled.count("verify_short_parent_force_scratch_reuse();") == 1
    with pytest.raises(ValueError, match="exact direct-Ewald dynamics regression source drift"):
        verifier.require_exact_regression_sources(disabled, helper, header)


@pytest.mark.parametrize("kind", ["helper", "header"])
def test_test_only_scratch_introspection_drift_fails_closed(kind: str) -> None:
    test = (
        ROOT / "native/tests/direct_ewald_composite_dynamics.cpp"
    ).read_text()
    helper = (
        ROOT / "native/tests/direct_ewald_composite_dynamics_scratch.cpp"
    ).read_text()
    header = (
        ROOT / "native/tests/direct_ewald_composite_dynamics_scratch.hpp"
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
            "    DIRECT_EWALD_SHORT_PARENT_FORCE_SCRATCH_EVIDENCE_PRESENT,\n",
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
            "          frozen=5d4a55c85a80b62d38e79ea608e4850a6966ceeb\n",
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
    for pull_request in (448, 447, 446):
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
        "          git merge-base --is-ancestor 5d4a55c85a80b62d38e79ea608e4850a6966ceeb HEAD\n",
        "          git fetch --no-tags --depth=1 origin refs/pull/446/head\n",
        "          cmake --build build/direct-ewald-short-parent-force-scratch-release --target betelgeuze_engine_direct_ewald_composite_dynamics --parallel 2\n",
        "          ctest --test-dir build/direct-ewald-short-parent-force-scratch-release -R '^betelgeuze_engine_(direct_ewald_composite_dynamics|export_allowlist)$' --output-on-failure\n",
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
            "python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py",
            "python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py --refresh",
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
