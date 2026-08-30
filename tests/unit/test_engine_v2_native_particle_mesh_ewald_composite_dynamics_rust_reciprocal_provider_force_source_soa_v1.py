import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_source_soa_v1
    as verifier,
)

ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 278
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    validation = profile["validation"]
    for key in (
        "successful_stateful_forceful_rust_reciprocal_provider_force_source_soa",
        "steady_state_rust_reciprocal_provider_force_source_soa",
        "rust_only_forceful_stateful_dispatch",
        "provider_force_source_result_is_private_internal_cpp_type",
        "provider_force_scratch_is_composite_local_force_source",
        "reciprocal_parent_aos_storage_untouched_on_rust_lane",
        "reciprocal_parent_empty_storage_preserved",
        "reciprocal_parent_stale_storage_and_bits_preserved",
        "fresh_rust_reciprocal_parent_aos_allocation_elided",
        "provider_soa_to_parent_aos_rematerialization_elided",
        "provider_force_source_finite_scan_precedes_composite_use",
        "composite_force_validation_two_pass_transactional",
        "final_force_soa_commit_after_full_preflight",
        "cpp_lane_reciprocal_parent_reuse_preserved",
        "stateless_path_preserved",
        "stateful_force_free_path_preserved",
        "existing_transactional_provider_entrypoint_preserved",
        "direct_provider_force_output_preserved",
    ):
        assert implementation[key]
    for key in (
        "allocation_free_claimed",
        "universal_reciprocal_parent_allocation_elision_claimed",
        "timing_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "cross_lane_bit_parity_claimed",
        "scientific_failure_force_storage_retention_claimed",
        "unconditional_failure_storage_retention_claimed",
        "fixed64_cpu_v7_qualification_invoked",
        "hip_device_execution_invoked",
        "molecular_execution_invoked",
    ):
        assert implementation[key] is False
    for key in (
        "four_canonical_vendor_pairs_byte_identical",
        "eight_production_paths_exact_hashes",
        "native_regression_path_exact_hash",
        "exact_public_symbol_surfaces",
        "internal_force_source_symbols_absent_from_public_surfaces",
        "checkpoint_and_static_fingerprint_unchanged",
        "rust_only_stateful_forceful_dispatch_exact",
        "provider_soa_is_local_reciprocal_force_view",
        "reciprocal_parent_empty_and_stale_bits_preserved",
        "provider_force_source_finite_scan_exact",
        "composite_preflight_then_final_commit_order_exact",
        "cpp_stateless_and_force_free_routes_preserved",
        "inverse_fft_second_occurrence_failure_boundary_preserved",
        "late_scientific_failure_boundary_preserved",
        "predecessor_workflow_detaches_exact_merge_object",
    ):
        assert validation[key]
    assert not any(profile["authority"].values())


def test_exact_anchors_and_delta() -> None:
    assert verifier.PREDECESSOR["pull_request"] == 457
    assert verifier.ARCHITECTURE_PREDECESSOR["pull_request"] == 453
    assert verifier.INHERITED_PREDECESSOR["pull_request"] == 440
    assert verifier.DIRECT_FORCE_OUTPUT_PRECEDENT["pull_request"] == 380
    assert len(verifier.EVIDENCE_PATHS) == 6
    assert len(verifier.IMPLEMENTATION_DELTA_PATHS) == 8
    assert len(verifier.EXPECTED_DELTA_PATHS) == 17
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS


def test_workflow_static_trigger_closure_and_bodies() -> None:
    assert len(verifier.REQUIRED_TRIGGER_PATHS) == 96
    assert len(set(verifier.REQUIRED_TRIGGER_PATHS)) == 96
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    verifier.require_workflow_contract(workflow)
    assert workflow == verifier.expected_workflow_document()
    assert workflow.count(verifier.PINNED_CHECKOUT_ACTION) == 4
    assert "refs/pull/457/head" in workflow
    assert verifier.PREDECESSOR["reviewed_head"] in workflow
    assert verifier.PREDECESSOR["merge_commit"] in workflow
    assert verifier.PREDECESSOR["merge_tree"] in workflow


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


def test_force_source_contract_hashes_and_mirrors() -> None:
    verifier.require_rust_reciprocal_provider_force_source_soa_contract(ROOT)
    assert len(verifier.EXPECTED_PRODUCTION_SHA256) == 8
    assert len(verifier.CANONICAL_VENDOR_MIRROR_PAIRS) == 4
    for relative in verifier.CANONICAL_VENDOR_MIRROR_PAIRS:
        assert (
            ROOT / "native/src" / relative
        ).read_bytes() == (
            ROOT / "rust/betelgeuze-sys/vendor/native/src" / relative
        ).read_bytes()


def test_hidden_symbols_public_surface_and_checkpoint_freezes() -> None:
    verifier.require_hidden_provider_symbols(ROOT)
    for relative in verifier.HIDDEN_SYMBOL_PUBLIC_SURFACES:
        source = (ROOT / relative).read_text()
        assert verifier.HIDDEN_PROVIDER_SYMBOL not in source
        for symbol in verifier.INTERNAL_FORCE_SOURCE_SYMBOLS:
            assert symbol not in source
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


def test_predecessor_workflow_executes_exact_frozen_merge() -> None:
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
        "Materialize exact PR 457 evidence and reviewed head",
        "Verify exact frozen PR 457 evidence",
        'git checkout --detach --quiet "$frozen"',
        "trap restore EXIT",
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
            frozen.replace(
                "      - name: Verify bounded successor evidence\n",
                "      - name: drifted predecessor step\n",
                1,
            )
        )


def test_predecessor_unit_skip_is_exact_and_frozen() -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_UNIT_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_frozen_predecessor_unit(frozen)
    assert transformed == (ROOT / verifier.PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    assert "PME_RUST_RECIPROCAL_PROVIDER_FORCE_SOURCE_SOA_EVIDENCE_PRESENT" in transformed
    assert "exact frozen PR 457 object" in transformed


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
    assert 'build_pipeline_status=("${PIPESTATUS[@]}")' in transformed
    assert "cargo metadata --manifest-path rust/Cargo.toml --locked" in transformed


def test_manifest_and_profile_mutations_are_noncanonical() -> None:
    manifest_raw = (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    assert len(manifest["files"]) == 278
    manifest["files"][0]["sha256"] = "0" * 64
    assert verifier.canonical_bytes(manifest) != manifest_raw
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["authority"]["product_authority"] = True
    assert profile != verifier.build_profile(manifest_raw)
