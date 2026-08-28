from __future__ import annotations
import json
from pathlib import Path
import pytest
from tools import verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1 as verifier

ROOT = Path(__file__).resolve().parents[2]
FORCE_SCRATCH_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    FORCE_SCRATCH_EVIDENCE_PRESENT,
    reason=(
        "legacy particle-mesh Ewald composite dynamics evidence is verified "
        "from its exact frozen object after force-scratch evidence is present"
    ),
)

def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    assert result["source_count"] == profile["implementation"]["source_manifest_entry_count"]
    assert profile["abi"]["public_symbol_count"] == 13
    assert profile["abi"]["checkpoint_magic"] == "BGPME001"
    assert profile["abi"]["checkpoint_header_size_bytes"] == 104
    assert profile["authority"] == verifier.AUTHORITY
    assert not any(profile["authority"].values())

def test_parent_objects_are_exact_and_review_heads_optional() -> None:
    verifier.require_parents()
    assert [p["source_manifest_entry_count"] for p in verifier.PARENTS] == [114, 120]

def test_parent_manifest_mutations_fail_closed() -> None:
    parent = verifier.PARENTS[0]
    raw = (ROOT / parent["source_manifest_path"]).read_bytes()
    manifest = json.loads(raw)
    manifest["files"][0]["sha256"] = "x" * 64
    with pytest.raises(ValueError):
        verifier.require_parent_manifest(verifier.canonical_bytes(manifest), 114)
    with pytest.raises(ValueError):
        verifier.require_parent_manifest(raw, 113)

def test_source_manifest_is_canonical_sorted_and_acyclic() -> None:
    raw = (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(raw)
    assert raw == verifier.canonical_bytes(manifest)
    paths = [row["path"] for row in manifest["files"]]
    assert paths == sorted(set(paths))
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in paths
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in paths

def test_abi_ownership_checkpoint_and_lane_contracts() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    assert implementation["deep_owned_model"]
    assert implementation["shared_integrator_and_transactional_rollback"]
    assert implementation["ignored_direct_reciprocal_bounds_normalized_in_fingerprint"]
    assert implementation["same_lane_checkpoint_exact_only"]
    assert not implementation["cross_lane_bit_parity_claimed"]
    assert not implementation["hip_to_cpu_fallback"]

def test_all_public_symbol_surfaces_are_exactly_thirteen() -> None:
    surfaces = verifier.extract_public_symbol_surfaces(ROOT)
    assert set(surfaces) == {"header", "native", "linux_map", "darwin_exports", "check_exports", "rust_sys"}
    assert all(symbols == verifier.PUBLIC_SYMBOLS for symbols in surfaces.values())

def test_fourteenth_namespace_symbol_is_detected() -> None:
    header = (ROOT / "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h").read_text()
    symbols = tuple(
        symbol
        for symbol in __import__("re").findall(r"\b(bg_[a-z0-9_]+)\s*\(", header + "\nbg_particle_mesh_ewald_composite_dynamics_extra(")
        if verifier.is_dynamics_symbol(symbol)
    )
    assert symbols != verifier.PUBLIC_SYMBOLS

@pytest.mark.parametrize("field", sorted(verifier.AUTHORITY))
def test_authority_drift_fails_closed(tmp_path: Path, field: str) -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["authority"][field] = True
    assert profile != verifier.build_profile((ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes())

def test_workflow_is_pinned_cpu_only_and_fetches_parents() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count("actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0") == 4
    assert "permissions:\n  contents: read" in text
    assert text.count(verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL) == 1
    verifier.require_contracts(ROOT)

@pytest.mark.parametrize("component", [" --component rustfmt", " --component clippy"])
def test_rust_boundary_toolchain_component_removal_fails_closed(component: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL in text
    with pytest.raises(ValueError, match="toolchain/component installation drift"):
        verifier.require_workflow_contract(text.replace(component, "", 1))

@pytest.mark.parametrize("next_job_header", [
    "macos-export-boundary:",
    "macos_export_boundary:",
    "MacosExportBoundary:",
    '"macos-export-boundary":',
    "macos-export-boundary: # next job",
])
def test_rust_boundary_toolchain_component_relocation_fails_closed(next_job_header: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    text = text.replace("  macos-export-boundary:\n", f"  {next_job_header}\n", 1)
    full_step = (
        "      - name: Select frozen hosted Rust toolchain\n"
        "        run: |\n"
        f"          {verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    minimal_step = (
        "      - name: Select frozen hosted Rust toolchain\n"
        "        run: |\n"
        f"          {verifier.MINIMAL_RUST_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    relocated = text.replace(full_step, "", 1)
    before_macos_step, found_macos_step, after_macos_step = relocated.rpartition(minimal_step)
    assert found_macos_step == minimal_step
    relocated = f"{before_macos_step}{full_step}{after_macos_step}"
    following_run = "      - name: Verify exact shared-library exports\n        run: |\n"
    relocated = relocated.replace(
        following_run,
        f"{following_run}          {verifier.MINIMAL_RUST_TOOLCHAIN_INSTALL}\n",
        1,
    )
    with pytest.raises(ValueError, match="rust-boundaries job must own"):
        verifier.require_workflow_contract(relocated)

def test_rust_boundary_toolchain_install_after_tests_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    full_step = (
        "      - name: Select frozen hosted Rust toolchain\n"
        "        run: |\n"
        f"          {verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    moved_late = text.replace(full_step, "", 1)
    moved_late = moved_late.replace(
        "  macos-export-boundary:\n",
        f"{full_step}  macos-export-boundary:\n",
        1,
    )
    with pytest.raises(ValueError, match="must immediately precede the exact rust-boundaries command step"):
        verifier.require_workflow_contract(moved_late)

def test_rust_boundary_toolchain_duplicate_noop_step_name_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    full_step = (
        "      - name: Select frozen hosted Rust toolchain\n"
        "        run: |\n"
        f"          {verifier.RUST_BOUNDARY_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    duplicate_noop = (
        "      - name: Test raw and safe boundaries, docs, format, and clippy\n"
        "        run: echo duplicate-name sentinel\n"
    )
    moved_late = text.replace(full_step, "", 1)
    moved_late = moved_late.replace(
        "  macos-export-boundary:\n",
        f"{full_step}{duplicate_noop}  macos-export-boundary:\n",
        1,
    )
    with pytest.raises(ValueError, match="exactly one named Rust command step"):
        verifier.require_workflow_contract(moved_late)

@pytest.mark.parametrize("command", [
    "          cargo fmt --manifest-path rust/Cargo.toml --all -- --check\n",
    "          cargo clippy --manifest-path rust/Cargo.toml --locked --package betelgeuze-sys --package betelgeuze-runtime --all-targets -- -D warnings\n",
])
def test_rust_boundary_exact_command_step_removal_fails_closed(command: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count(command) == 1
    with pytest.raises(ValueError, match="exact rust-boundaries command step"):
        verifier.require_workflow_contract(text.replace(command, "", 1))

@pytest.mark.parametrize("old,new", [
    ("DBG_ENABLE_HIP=OFF", "DBG_ENABLE_HIP=ON"),
    ("contents: read", "contents: write"),
    ("runs-on: ubuntu-latest", "runs-on: self-hosted"),
    ("workflow_dispatch:", "pull_request_target:"),
    ("python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py", "python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py --refresh"),
])
def test_workflow_mutations_fail_closed(old: str, new: str) -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    with pytest.raises(ValueError):
        verifier.require_workflow_contract(text.replace(old, new, 1))

def test_predecessor_trigger_path_removal_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    predecessor = '      - "docs/engine_v2_native_particle_mesh_ewald_composite_cpu_v1.md"\n'
    assert text.count(predecessor) == 2
    with pytest.raises(ValueError, match="path trigger set drift"):
        verifier.require_workflow_contract(text.replace(predecessor, "", 1))

def test_paths_ignore_trigger_bypass_fails_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    assert text.count("    paths:\n") == 2
    with pytest.raises(ValueError, match="exactly one paths key"):
        verifier.require_workflow_contract(text.replace("    paths:\n", "    paths-ignore:\n"))

def test_workflow_nested_permission_and_accelerator_overrides_fail_closed() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    with pytest.raises(ValueError, match="exactly one global"):
        verifier.require_workflow_contract(text.replace("jobs:\n", "jobs:\n  permissions: write-all\n", 1))
    with pytest.raises(ValueError, match="global empty HIP_VISIBLE_DEVICES"):
        verifier.require_workflow_contract(text.replace("jobs:\n", 'jobs:\n  HIP_VISIBLE_DEVICES: ""\n', 1))
    with pytest.raises(ValueError, match="exactly one global"):
        verifier.require_workflow_contract(
            text.replace("  contents: read\n", "  contents: read\n  pages: write\n", 1)
        )

def test_cpu_environment_relocation_to_job_fails_closed() -> None:
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

def test_each_cmake_configuration_must_disable_hip_independently() -> None:
    text = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    mutated = text.replace("DBG_ENABLE_HIP=OFF", "HIP_OFF_REMOVED", 1)
    mutated = mutated.replace(
        "DBG_ENABLE_HIP=OFF",
        "DBG_ENABLE_HIP=OFF DBG_ENABLE_HIP=OFF",
        1,
    )
    with pytest.raises(ValueError, match="independently disable"):
        verifier.require_workflow_contract(mutated)
