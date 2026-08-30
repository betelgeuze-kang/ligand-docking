import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_direct_force_soa_v1
    as verifier,
)

ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_FORCE_SOURCE_SOA_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_force_source_soa_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_FORCE_SOURCE_SOA_EVIDENCE_PRESENT,
    reason=(
        "PME Rust reciprocal provider direct force-SoA evidence is verified "
        "from its exact frozen PR 457 object after provider force-source SoA "
        "evidence is present"
    ),
)


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 272
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    validation = profile["validation"]
    for key in (
        "successful_stateful_forceful_rust_reciprocal_provider_direct_force_soa",
        "steady_state_rust_reciprocal_provider_direct_force_soa",
        "hidden_internal_provider_symbol_added",
        "existing_transactional_provider_entrypoint_preserved",
        "direct_route_selected_only_for_reuse_and_forces",
        "direct_force_output_uses_caller_owned_provider_scratch",
        "direct_force_output_vec_allocation_elided",
        "direct_force_output_reserve_elided",
        "direct_force_output_channel_copy_elided",
        "direct_force_output_energy_commit_success_only",
        "single_common_scientific_pipeline_preserved",
        "direct_force_output_preflight_precedes_force_write",
        "remaining_fallible_allocations_precede_direct_force_write",
        "remaining_allocation_failure_preserves_force_output",
        "late_scientific_failure_may_modify_direct_force_output",
        "provider_force_scratch_reuse_preserved",
    ):
        assert implementation[key]
    for key in (
        "allocation_free_claimed",
        "timing_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "cross_lane_bit_parity_claimed",
        "checkpoint_buffer_aliasing_claimed",
        "scientific_failure_force_storage_retention_claimed",
        "unconditional_failure_storage_retention_claimed",
        "universal_failure_storage_retention_claimed",
        "all_failure_path_storage_retention_claimed",
    ):
        assert implementation[key] is False
    assert validation["hidden_provider_symbol_absent_from_public_surfaces"]
    assert validation["remaining_allocation_failures_preserve_sentinels"]
    assert validation[
        "forward_and_inverse_fft_allocation_failures_preserve_sentinels"
    ]
    assert validation["force_output_allocation_failpoint_is_not_reached"]
    assert validation["late_scientific_failure_transaction_boundary_explicit"]
    assert validation["checkpoint_and_static_fingerprint_unchanged"]
    assert not any(profile["authority"].values())


def test_exact_anchors_and_delta() -> None:
    assert verifier.PREDECESSOR["pull_request"] == 456
    assert verifier.ARCHITECTURE_PREDECESSOR["pull_request"] == 453
    assert verifier.INHERITED_PREDECESSOR["pull_request"] == 440
    assert verifier.DIRECT_FORCE_OUTPUT_PRECEDENT["pull_request"] == 380
    assert len(verifier.IMPLEMENTATION_DELTA_PATHS) == 5
    assert len(verifier.EXPECTED_DELTA_PATHS) == 13
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS


def test_workflow_static_trigger_closure_and_bodies() -> None:
    assert len(verifier.REQUIRED_TRIGGER_PATHS) == 90
    assert len(set(verifier.REQUIRED_TRIGGER_PATHS)) == 90
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    verifier.require_workflow_contract(workflow)
    assert workflow == verifier.expected_workflow_document()
    assert (
        workflow.count(
            "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
        )
        == 4
    )
    assert (
        "cargo test --manifest-path rust/Cargo.toml --locked "
        "--package betelgeuze-cpu-kernel particle_mesh_reciprocal"
    ) in workflow
    assert (
        "cargo clippy --manifest-path rust/Cargo.toml --locked "
        "--package betelgeuze-cpu-kernel --all-targets -- -D warnings"
    ) in workflow


@pytest.mark.parametrize(
    "job",
    [
        "immutable-evidence",
        "native-linux",
        "rust-boundaries",
        "macos-export-boundary",
    ],
)
def test_workflow_job_body_mutation_fails_closed(job: str) -> None:
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    body = verifier.job_body(workflow, job)
    mutated = workflow.replace(body, body + "      # sentinel drift\n", 1)
    with pytest.raises(ValueError, match="workflow exact job body drift"):
        verifier.require_workflow_contract(mutated)


def test_direct_provider_contract_and_hashes() -> None:
    verifier.require_rust_reciprocal_provider_direct_force_soa_contract(ROOT)


def test_hidden_symbol_and_public_surfaces() -> None:
    verifier.require_hidden_provider_symbol(ROOT)
    for relative in verifier.HIDDEN_SYMBOL_PUBLIC_SURFACES:
        assert verifier.HIDDEN_PROVIDER_SYMBOL not in (ROOT / relative).read_text()


def test_mirror_checkpoint_and_fingerprint_freezes() -> None:
    assert len(verifier.INHERITED_CANONICAL_VENDOR_MIRROR_PAIRS) == 6
    for relative in verifier.INHERITED_CANONICAL_VENDOR_MIRROR_PAIRS:
        assert (
            ROOT / "native/src" / relative
        ).read_bytes() == (
            ROOT / "rust/betelgeuze-sys/vendor/native/src" / relative
        ).read_bytes()
    for relative in verifier.FROZEN_CHECKPOINT_FINGERPRINT_PATHS:
        assert (ROOT / relative).read_bytes() == verifier.git(
            "show",
            f"{verifier.PREDECESSOR['merge_commit']}:{relative.as_posix()}",
        ).stdout


def test_predecessor_and_precedent_freezes() -> None:
    verifier.require_predecessor()
    verifier.require_direct_force_output_precedent()
    verifier.require_predecessor_workflow_freeze(ROOT)
    verifier.require_predecessor_unit_freeze(ROOT)


def test_macos_locked_cargo_transient_retry_remains_exact() -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:"
        f"{verifier.MACOS_RETRY_WORKFLOW_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_macos_lock_transient_retry_workflow(frozen)
    assert transformed == (
        ROOT / verifier.MACOS_RETRY_WORKFLOW_RELATIVE_PATH
    ).read_text()
    for token in (
        "        shell: bash",
        'build_pipeline_status=("${PIPESTATUS[@]}")',
        'tee_status="${build_pipeline_status[1]}"',
        'grep -Fq "xcrun_db-"',
        'grep -Fq "errno=Invalid argument"',
        'grep -Fq "cannot update the lock file"',
        'grep -Fq "because --locked was passed"',
        "cargo metadata --manifest-path rust/Cargo.toml --locked",
    ):
        assert token in transformed


@pytest.mark.parametrize(
    "anchor",
    [
        (
            "      - name: Materialize exact PR 455 target, PR 453 "
            "architecture, and PR 440 inherited reciprocal evaluator\n"
        ),
        "      - name: Verify bounded successor evidence\n",
    ],
)
def test_predecessor_workflow_executes_exact_frozen_merge(anchor: str) -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_frozen_predecessor_workflow(frozen)
    assert transformed == (
        ROOT / verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH
    ).read_text()
    for token in (
        "Materialize exact PR 456 evidence and reviewed head",
        'git checkout --detach --quiet "$frozen"',
        "trap 'git checkout --detach --quiet \"$current_sha\"' EXIT",
        verifier.PREDECESSOR["reviewed_head"],
        verifier.PREDECESSOR["merge_commit"],
        verifier.PREDECESSOR["merge_tree"],
    ):
        assert token in transformed
    sentinel = "\n# unrelated-frozen-workflow-sentinel\n"
    assert verifier.expected_frozen_predecessor_workflow(
        frozen + sentinel
    ).endswith(sentinel)
    with pytest.raises(ValueError, match="transformation point drift"):
        verifier.expected_frozen_predecessor_workflow(
            frozen.replace(anchor, "      - name: drifted predecessor step\n", 1)
        )


def test_manifest_and_profile_mutations_are_noncanonical() -> None:
    manifest_raw = (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    manifest["files"][0]["sha256"] = "0" * 64
    assert verifier.canonical_bytes(manifest) != manifest_raw
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["authority"]["product_authority"] = True
    assert profile != verifier.build_profile(manifest_raw)
