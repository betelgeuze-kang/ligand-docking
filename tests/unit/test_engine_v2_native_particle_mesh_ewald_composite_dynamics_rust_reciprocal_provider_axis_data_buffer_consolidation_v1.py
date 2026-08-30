import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1
    as verifier,
)

ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 296
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    validation = profile["validation"]
    for key in (
        "reciprocal_axis_data_uses_one_call_local_backing_buffer",
        "reciprocal_axis_data_backing_length_is_sum_of_mesh_dimensions",
        "reciprocal_axis_data_x_y_z_slices_contiguous_and_non_overlapping",
        "reciprocal_axis_data_second_and_third_reserves_elided",
        "reciprocal_axis_data_arithmetic_and_axis_order_preserved",
        "reciprocal_axis_data_not_retained",
        "all_provider_modes_single_reciprocal_axis_data_reserve",
        "call_local_fft_line_scratch_shared_by_forward_and_inverse",
        "fft_line_scratch_length_is_max_mesh_axis",
        "force_modes_single_fft_line_scratch_reserve",
        "force_mode_second_fft_line_scratch_reserve_elided",
        "energy_only_single_fft_line_scratch_reserve_preserved",
        "fft_transform_arithmetic_and_axis_order_preserved",
        "fft_line_scratch_overwrites_poison_before_read",
        "fft_line_scratch_not_retained",
        "all_hidden_rust_reciprocal_provider_modes_borrow_input_soa",
        "energy_only_provider_input_borrowed",
        "transactional_force_provider_input_borrowed",
        "direct_force_provider_input_borrowed",
        "provider_input_channels_borrowed_call_local",
        "provider_channel_copy_allocations_elided",
        "provider_position_aos_rematerialization_elided",
        "provider_input_borrow_after_complete_alias_preflight",
        "zero_count_null_channels_use_empty_slices",
        "borrowed_input_not_retained",
        "shared_owned_and_borrowed_calculation_pipeline",
        "remaining_fallible_workspaces_preserved",
        "energy_only_force_storage_disabled_preserved",
        "transactional_force_internal_vec_preserved",
        "direct_force_caller_owned_scratch_preserved",
        "transactional_energy_and_force_commit_preserved",
        "direct_energy_success_only_commit_preserved",
        "stateless_hidden_rust_provider_uses_call_local_borrowed_input",
        "stateful_force_free_hidden_rust_provider_uses_call_local_borrowed_input",
        "stateful_forceful_hidden_rust_provider_uses_call_local_borrowed_input",
        "public_bg_system_owned_storage_preserved",
        "native_cpp_adapter_abi_preserved",
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
        "provider_allocation_free_claimed",
        "steady_state_allocation_free_claimed",
        "all_remaining_allocations_elided_claimed",
        "all_remaining_reciprocal_allocations_elided_claimed",
        "transactional_force_internal_vec_allocation_elided_claimed",
        "neutrality_sort_allocation_elided_claimed",
        "particle_assignment_allocation_elided_claimed",
        "spectrum_allocation_elided_claimed",
        "fft_scratch_allocation_elided_claimed",
        "all_fft_scratch_allocations_elided_claimed",
        "persistent_fft_scratch_reuse_claimed",
        "cross_call_fft_scratch_reuse_claimed",
        "owner_fft_scratch_reuse_claimed",
        "peak_memory_reduction_claimed",
        "reciprocal_axis_data_allocation_elided_claimed",
        "persistent_reciprocal_axis_data_reuse_claimed",
        "cross_call_reciprocal_axis_data_reuse_claimed",
        "owner_reciprocal_axis_data_reuse_claimed",
        "universal_input_allocation_elision_claimed",
        "public_api_zero_copy_input_claimed",
        "public_bg_system_borrowed_ownership_claimed",
        "persistent_input_view_claimed",
        "cross_call_input_borrowing_claimed",
        "universal_repository_input_borrowing_claimed",
        "universal_reciprocal_parent_allocation_elision_claimed",
        "scientific_claimed",
        "scientific_equivalence_claimed",
        "timing_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "cross_lane_bit_parity_claimed",
        "reciprocal_failure_storage_retention_claimed",
        "scientific_failure_force_storage_retention_claimed",
        "unconditional_failure_storage_retention_claimed",
        "fixed64_cpu_v7_qualification_invoked",
        "hip_device_execution_invoked",
        "molecular_execution_invoked",
    ):
        assert implementation[key] is False
    for key in (
        "single_reciprocal_axis_data_reserve_occurrence_exact",
        "reciprocal_axis_slice_lengths_offsets_and_non_overlap_exact",
        "reciprocal_axis_value_bits_and_x_y_z_order_preserved",
        "second_reciprocal_axis_data_occurrence_injection_succeeds_exact_bits",
        "first_reciprocal_axis_data_oom_transactional",
        "predecessor_fft_line_scratch_contract_inherited",
        "single_call_local_fft_scratch_allocation_exact",
        "same_fft_scratch_identity_and_capacity_across_transforms",
        "fft_scratch_poison_overwritten_before_read",
        "second_fft_line_scratch_reserve_absent",
        "second_occurrence_injection_succeeds_exact_bits",
        "first_occurrence_fft_scratch_oom_transactional",
        "direct_last_prewrite_axis_allocation_boundary_preserved",
        "energy_only_fft_scratch_allocation_unchanged",
        "predecessor_borrowed_input_contract_inherited",
        "four_canonical_vendor_pairs_byte_identical",
        "predecessor_eight_production_paths_exact_and_unchanged",
        "predecessor_native_regression_path_exact_and_unchanged",
        "single_rust_production_path_delta_exact",
        "removed_provider_copy_allocation_sites_absent",
        "borrowed_input_constructed_after_complete_preflight",
        "zero_count_raw_slice_formation_avoided",
        "borrowed_input_call_local_and_not_retained",
        "owned_and_borrowed_pipeline_shared_exact",
        "owned_and_three_borrowed_modes_bit_identical",
        "four_input_channel_aliases_fail_before_borrow",
        "provider_input_bits_retained_across_success_and_failure",
        "remaining_allocation_failure_boundaries_preserved",
        "exact_public_symbol_surfaces",
        "internal_force_source_symbols_absent_from_public_surfaces",
        "checkpoint_and_static_fingerprint_unchanged",
        "rust_only_stateful_forceful_dispatch_exact",
        "provider_soa_is_local_reciprocal_force_view",
        "reciprocal_parent_empty_and_stale_bits_preserved",
        "provider_force_source_finite_scan_exact",
        "composite_preflight_then_final_commit_order_exact",
        "cpp_stateless_and_force_free_routes_preserved",
        "late_scientific_failure_boundary_preserved",
        "predecessor_workflow_detaches_exact_merge_object",
    ):
        assert validation[key]
    assert not any(profile["authority"].values())


def test_exact_anchors_and_delta() -> None:
    assert verifier.PREDECESSOR["pull_request"] == 460
    assert verifier.ARCHITECTURE_PREDECESSOR["pull_request"] == 453
    assert verifier.INHERITED_PREDECESSOR["pull_request"] == 440
    assert verifier.DIRECT_FORCE_OUTPUT_PRECEDENT["pull_request"] == 380
    assert len(verifier.EVIDENCE_PATHS) == 6
    assert len(verifier.IMPLEMENTATION_DELTA_PATHS) == 1
    assert len(verifier.EXPECTED_DELTA_PATHS) == 9
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS


def test_workflow_static_trigger_closure_and_bodies() -> None:
    assert len(verifier.REQUIRED_TRIGGER_PATHS) == 114
    assert len(set(verifier.REQUIRED_TRIGGER_PATHS)) == 114
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    verifier.require_workflow_contract(workflow)
    assert workflow == verifier.expected_workflow_document()
    assert workflow.count(verifier.PINNED_CHECKOUT_ACTION) == 4
    assert "refs/pull/460/head" in workflow
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


def test_axis_data_buffer_contract_hashes_and_frozen_predecessor_mirrors() -> None:
    verifier.require_rust_reciprocal_provider_axis_data_buffer_consolidation_contract(ROOT)
    assert len(verifier.EXPECTED_PREDECESSOR_PRODUCTION_SHA256) == 8
    assert verifier.IMPLEMENTATION_DELTA_PATHS == (
        verifier.RUST_RECIPROCAL_RELATIVE_PATH,
    )
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
        "Materialize exact PR 460 evidence and reviewed head",
        "Verify exact frozen PR 460 evidence",
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
    with pytest.raises(ValueError, match="drift"):
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
    assert (
        "PME_RUST_RECIPROCAL_PROVIDER_AXIS_DATA_BUFFER_CONSOLIDATION_EVIDENCE_PRESENT"
        in transformed
    )
    assert "exact frozen PR 460 object" in transformed


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
    assert len(manifest["files"]) == 296
    manifest["files"][0]["sha256"] = "0" * 64
    assert verifier.canonical_bytes(manifest) != manifest_raw
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["authority"]["product_authority"] = True
    assert profile != verifier.build_profile(manifest_raw)
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["implementation"]["allocation_free_claimed"] = True
    assert profile != verifier.build_profile(manifest_raw)
