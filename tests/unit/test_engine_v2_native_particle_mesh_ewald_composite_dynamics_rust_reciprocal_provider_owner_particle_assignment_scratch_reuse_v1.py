import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_v1
    as verifier,
)

ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_TRANSACTIONAL_FORCE_OUTPUT_ELISION_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_TRANSACTIONAL_FORCE_OUTPUT_ELISION_EVIDENCE_PRESENT,
    reason=(
        "PME Rust reciprocal-provider owner particle-assignment scratch evidence "
        "is verified from its exact frozen PR 466 object after transactional "
        "force-output elision evidence is present"
    ),
)


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 326
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    validation = profile["validation"]
    for key in (
        "owner_route_uses_one_persistent_complex_backing",
        "owner_reciprocal_workspace_reuse_claimed",
        "cross_call_reciprocal_workspace_reuse_claimed",
        "persistent_reciprocal_workspace_reuse_claimed",
        "stateful_forceful_owner_workspace_route_only",
        "private_provider_abi_extended",
        "private_workspace_descriptor_zero_initializable",
        "private_workspace_descriptor_not_exported",
        "private_workspace_descriptor_not_checkpointed",
        "provider_force_scratch_noncopyable_and_nonmovable",
        "cold_first_use_allocation_order_and_detail_preserved",
        "warm_same_shape_reciprocal_workspace_reserve_elided",
        "capacity_sufficient_shape_reuse_without_reserve",
        "growth_beyond_capacity_uses_one_workspace_reserve",
        "failed_workspace_growth_retains_prior_raw_parts_and_payload",
        "workspace_spectrum_cleared_before_additive_spread",
        "workspace_lease_restored_after_success_failure_and_panic",
        "workspace_complete_capacity_alias_preflight",
        "owner_dynamics_output_preflight_includes_complete_workspace_capacity",
        "integrate_output_alias_preflight_precedes_descriptor_reads",
        "particle_view_and_absolute_step_owner_overlap_precedes_access",
        "workspace_destroy_ready_exactly_once",
        "workspace_destroy_null_empty_double_and_detectably_malformed_fail_closed",
        "workspace_destroy_safety_contract_requires_private_rust_origin_canonical_ready",
        "independent_owners_use_independent_workspace_storage",
        "predecessor_owner_reciprocal_workspace_contract_inherited",
        "private_neutrality_sort_scratch_descriptor_zero_initializable",
        "private_neutrality_sort_scratch_descriptor_not_exported",
        "private_neutrality_sort_scratch_descriptor_not_checkpointed",
        "stateful_forceful_owner_neutrality_sort_scratch_route_only",
        "neutrality_sort_scratch_length_is_particle_count",
        "neutrality_sort_scratch_reserve_precedes_clear",
        "neutrality_sort_scratch_overwritten_before_read",
        "warm_same_shape_neutrality_sort_reserve_elided",
        "capacity_sufficient_neutrality_sort_shape_reuse_without_reserve",
        "growth_beyond_capacity_uses_one_neutrality_sort_reserve",
        "failed_neutrality_sort_growth_retains_prior_raw_parts_and_payload",
        "neutrality_sort_scratch_lease_restored_after_success_failure_and_panic",
        "neutrality_sort_complete_capacity_alias_preflight",
        "workspace_and_neutrality_complete_capacities_pairwise_disjoint",
        "owner_dynamics_output_preflight_includes_complete_neutrality_sort_capacity",
        "neutrality_sort_destroy_ready_exactly_once",
        "neutrality_sort_destroy_null_empty_double_and_detectably_malformed_fail_closed",
        "neutrality_sort_destroy_safety_contract_requires_private_rust_origin_canonical_ready",
        "independent_owners_use_independent_neutrality_sort_storage",
        "neutrality_sort_later_failure_retention_is_conditional",
        "persistent_neutrality_sort_scratch_reuse_claimed",
        "cross_call_neutrality_sort_scratch_reuse_claimed",
        "owner_neutrality_sort_scratch_reuse_claimed",
        "neutrality_sort_capacity_sufficient_reserve_elision_claimed",
        "predecessor_owner_neutrality_sort_scratch_contract_inherited",
        "private_particle_assignment_scratch_descriptor_zero_initializable",
        "private_particle_assignment_scratch_descriptor_not_exported",
        "private_particle_assignment_scratch_descriptor_not_checkpointed",
        "particle_assignment_scratch_descriptor_uses_opaque_byte_units",
        "particle_assignment_scratch_rust_origin_canonical_raw_parts_required",
        "stateful_forceful_owner_particle_assignment_scratch_route_only",
        "particle_assignment_scratch_reserve_precedes_clear",
        "particle_assignment_scratch_fully_recomputed_each_call",
        "changed_positions_recompute_particle_assignments",
        "warm_same_shape_particle_assignment_reserve_elided",
        "capacity_sufficient_particle_assignment_shape_reuse_without_reserve",
        "growth_beyond_capacity_uses_one_particle_assignment_reserve",
        "failed_particle_assignment_growth_retains_prior_raw_parts_and_payload",
        "particle_assignment_scratch_lease_restored_after_success_failure_and_panic",
        "particle_assignment_complete_capacity_alias_preflight",
        "workspace_neutrality_and_particle_assignment_complete_capacities_pairwise_disjoint",
        "owner_dynamics_output_preflight_includes_complete_particle_assignment_capacity",
        "particle_assignment_destroy_ready_exactly_once",
        "particle_assignment_destroy_null_empty_double_and_detectably_malformed_fail_closed",
        "particle_assignment_destroy_safety_contract_requires_private_rust_origin_canonical_ready",
        "independent_owners_use_independent_particle_assignment_storage",
        "particle_assignment_later_failure_retention_is_conditional",
        "three_owner_private_leases_restore_together",
        "owner_route_uses_three_distinct_private_reusable_descriptors",
        "persistent_particle_assignment_scratch_reuse_claimed",
        "cross_call_particle_assignment_scratch_reuse_claimed",
        "owner_particle_assignment_scratch_reuse_claimed",
        "particle_assignment_capacity_sufficient_reserve_elision_claimed",
        "stateful_force_free_path_preserved",
        "stateless_path_preserved",
        "existing_transactional_provider_entrypoint_preserved",
        "checkpoint_format_changed",
    ):
        expected = key != "checkpoint_format_changed"
        assert implementation[key] is expected
    for key in (
        "allocation_free_claimed",
        "provider_allocation_free_claimed",
        "steady_state_allocation_free_claimed",
        "all_remaining_allocations_elided_claimed",
        "all_remaining_reciprocal_allocations_elided_claimed",
        "neutrality_sort_allocation_elided_claimed",
        "particle_assignment_allocation_elided_claimed",
        "reciprocal_workspace_capacity_equality_claimed",
        "reciprocal_workspace_storage_allocation_free_claimed",
        "stateful_force_free_workspace_reuse_claimed",
        "stateless_workspace_reuse_claimed",
        "transactional_workspace_reuse_claimed",
        "concurrent_workspace_use_claimed",
        "provider_wide_neutrality_sort_scratch_reuse_claimed",
        "stateful_force_free_neutrality_sort_scratch_reuse_claimed",
        "stateless_neutrality_sort_scratch_reuse_claimed",
        "transactional_neutrality_sort_scratch_reuse_claimed",
        "concurrent_neutrality_sort_scratch_use_claimed",
        "unconditional_neutrality_sort_failure_storage_retention_claimed",
        "particle_assignment_c_layout_claimed",
        "particle_assignment_size_bytes_claimed",
        "particle_assignment_elements_need_drop",
        "stateful_force_free_particle_assignment_scratch_reuse_claimed",
        "stateless_particle_assignment_scratch_reuse_claimed",
        "transactional_particle_assignment_scratch_reuse_claimed",
        "concurrent_particle_assignment_scratch_use_claimed",
        "provider_wide_particle_assignment_scratch_reuse_claimed",
        "unconditional_particle_assignment_failure_storage_retention_claimed",
        "peak_memory_reduction_claimed",
        "timing_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "cross_lane_bit_parity_claimed",
        "scientific_claimed",
        "scientific_equivalence_claimed",
        "product_claimed",
        "operational_readiness_claimed",
        "fixed64_cpu_v7_qualification_invoked",
        "hip_device_execution_invoked",
        "molecular_execution_invoked",
        "public_benchmark_invoked",
        "reservation_invoked",
    ):
        assert implementation[key] is False
    assert implementation["private_workspace_descriptor_size_bytes"] == 72
    assert implementation["private_neutrality_sort_scratch_descriptor_size_bytes"] == 72
    assert implementation["private_particle_assignment_scratch_descriptor_size_bytes"] == 72
    for key in (
        "nine_production_path_delta_exact",
        "three_native_test_path_delta_exact",
        "four_modified_canonical_vendor_pairs_byte_identical",
        "workspace_descriptor_layout_and_states_exact",
        "workspace_descriptor_and_complete_capacity_disjointness_exact",
        "owner_dynamics_output_complete_workspace_capacity_overlap_exact",
        "integrate_alias_checks_before_output_descriptor_reads_exact",
        "particle_view_and_absolute_step_owner_overlap_before_access_exact",
        "cold_first_use_oom_order_detail_and_transactionality_exact",
        "warm_same_shape_occurrence_one_pending_and_bits_exact",
        "capacity_sufficient_and_growth_reserve_boundaries_exact",
        "failed_growth_prior_workspace_retention_exact",
        "poisoned_retained_workspace_overwritten_before_read",
        "panic_unwind_restores_ready_workspace",
        "destroy_null_empty_double_detectably_malformed_and_ready_contract_exact",
        "stateless_transactional_force_free_and_cpp_routes_preserved",
        "owner_checkpoint_cpp_interleave_and_independence_exact",
        "predecessor_owner_workspace_contract_inherited",
        "neutrality_sort_descriptor_layout_and_states_exact",
        "workspace_and_neutrality_descriptor_and_complete_capacity_disjointness_exact",
        "owner_dynamics_output_complete_neutrality_sort_capacity_overlap_exact",
        "neutrality_sort_length_particle_count_exact",
        "neutrality_sort_comparator_and_compensated_sum_exact",
        "cold_neutrality_sort_first_use_oom_order_detail_and_transactionality_exact",
        "warm_same_shape_neutrality_sort_occurrence_one_pending_and_bits_exact",
        "neutrality_sort_capacity_sufficient_and_growth_reserve_boundaries_exact",
        "failed_neutrality_sort_growth_prior_storage_retention_exact",
        "neutrality_sort_poison_overwritten_before_read",
        "neutrality_sort_late_failure_retention_conditional_exact",
        "panic_unwind_restores_ready_workspace_and_neutrality_sort_scratch",
        "neutrality_sort_destroy_null_empty_double_detectably_malformed_and_ready_contract_exact",
        "stateless_transactional_force_free_and_legacy_workspace_routes_preserved",
        "owner_checkpoint_private_scratch_exclusion_and_alias_semantics_unchanged",
        "particle_assignment_descriptor_layout_byte_units_and_states_exact",
        "particle_assignment_rust_origin_raw_parts_and_no_c_layout_claim_exact",
        "particle_assignment_needs_drop_false_exact",
        "workspace_neutrality_and_particle_assignment_descriptor_and_complete_capacity_disjointness_exact",
        "owner_dynamics_output_complete_particle_assignment_capacity_overlap_exact",
        "cold_particle_assignment_first_use_oom_order_detail_and_transactionality_exact",
        "warm_same_shape_particle_assignment_occurrence_one_pending_and_bits_exact",
        "particle_assignment_capacity_sufficient_and_growth_reserve_boundaries_exact",
        "particle_assignment_full_recompute_and_changed_positions_exact",
        "failed_particle_assignment_growth_prior_storage_retention_exact",
        "particle_assignment_late_failure_retention_conditional_exact",
        "panic_unwind_restores_ready_workspace_neutrality_and_particle_assignment_scratch",
        "particle_assignment_destroy_null_empty_double_detectably_malformed_and_ready_contract_exact",
        "stateless_transactional_force_free_and_legacy_workspace_neutrality_routes_preserved",
        "exact_public_symbol_surfaces",
        "checkpoint_and_static_fingerprint_unchanged",
        "predecessor_workflow_detaches_exact_merge_object",
        "predecessor_unit_skips_only_when_successor_profile_exists",
    ):
        assert validation[key]
    assert not any(profile["authority"].values())
    assert profile["operational_boundary"]["unresolved_operational_decisions"] == 32


def test_exact_anchors_and_delta() -> None:
    assert verifier.PREDECESSOR["pull_request"] == 465
    assert verifier.PREDECESSOR["reviewed_head"] == "0c6a50e85a4613baea889f6ded810a53955d6326"
    assert verifier.PREDECESSOR["merge_commit"] == "dacb1fb5cb466a7ecb43b32b2a1039734bcfdfdb"
    assert verifier.PREDECESSOR["merge_tree"] == "09ae686da88e9875bd0646aa9be6774063f1079a"
    assert verifier.ARCHITECTURE_PREDECESSOR["pull_request"] == 453
    assert verifier.INHERITED_PREDECESSOR["pull_request"] == 440
    assert verifier.DIRECT_FORCE_OUTPUT_PRECEDENT["pull_request"] == 380
    assert len(verifier.EVIDENCE_PATHS) == 6
    assert len(verifier.IMPLEMENTATION_DELTA_PATHS) == 9
    assert len(verifier.NATIVE_TEST_RELATIVE_PATHS) == 3
    assert len(verifier.EXPECTED_DELTA_PATHS) == 20
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS


def test_workflow_static_trigger_closure_and_bodies() -> None:
    assert len(verifier.REQUIRED_TRIGGER_PATHS) == 144
    assert len(set(verifier.REQUIRED_TRIGGER_PATHS)) == 144
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    verifier.require_workflow_contract(workflow)
    assert workflow == verifier.expected_workflow_document()
    assert workflow.count(verifier.PINNED_CHECKOUT_ACTION) == 4
    assert "refs/pull/465/head" in workflow
    assert verifier.PREDECESSOR["reviewed_head"] in workflow


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


def test_owner_particle_assignment_source_hashes_mirrors_and_contract() -> None:
    verifier.require_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_contract(ROOT)
    assert len(verifier.EXPECTED_PREDECESSOR_DELTA_SHA256) == 12
    assert len(verifier.EXPECTED_SUCCESSOR_DELTA_SHA256) == 12
    assert len(verifier.CANONICAL_VENDOR_MIRROR_PAIRS) == 4
    for relative in verifier.CANONICAL_VENDOR_MIRROR_PAIRS:
        assert (ROOT / "native/src" / relative).read_bytes() == (
            ROOT / "rust/betelgeuze-sys/vendor/native/src" / relative
        ).read_bytes()


def test_hidden_symbols_public_surface_and_checkpoint_freezes() -> None:
    verifier.require_hidden_provider_symbols(ROOT)
    for relative in verifier.HIDDEN_SYMBOL_PUBLIC_SURFACES:
        source = (ROOT / relative).read_text()
        assert verifier.OWNER_WORKSPACE_PROVIDER_SYMBOL not in source
        assert verifier.OWNER_WORKSPACE_DESTROY_SYMBOL not in source
        assert verifier.OWNER_NEUTRALITY_SORT_PROVIDER_SYMBOL not in source
        assert verifier.OWNER_NEUTRALITY_SORT_DESTROY_SYMBOL not in source
        assert verifier.OWNER_PARTICLE_ASSIGNMENT_PROVIDER_SYMBOL not in source
        assert verifier.OWNER_PARTICLE_ASSIGNMENT_DESTROY_SYMBOL not in source
    for relative in verifier.FROZEN_CHECKPOINT_FINGERPRINT_PATHS:
        assert (ROOT / relative).read_bytes() == verifier.git(
            "show", f"{verifier.PREDECESSOR['merge_commit']}:{relative.as_posix()}"
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
    assert transformed == (ROOT / verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    for token in (
        "Materialize exact PR 465 evidence and reviewed head",
        "Verify exact frozen PR 465 evidence",
        'git checkout --detach --quiet "$frozen"',
        "trap restore EXIT",
        verifier.PREDECESSOR["reviewed_head"],
        verifier.PREDECESSOR["merge_commit"],
        verifier.PREDECESSOR["merge_tree"],
    ):
        assert token in transformed


def test_predecessor_unit_skip_is_exact_and_frozen() -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_UNIT_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_frozen_predecessor_unit(frozen)
    assert transformed == (ROOT / verifier.PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    assert "OWNER_PARTICLE_ASSIGNMENT_SCRATCH_REUSE_EVIDENCE_PRESENT" in transformed
    assert "exact frozen PR 465 object" in transformed


def test_macos_locked_cargo_transient_retry_remains_exact() -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:"
        f"{verifier.MACOS_RETRY_WORKFLOW_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_macos_lock_transient_retry_workflow(frozen)
    assert transformed == (ROOT / verifier.MACOS_RETRY_WORKFLOW_RELATIVE_PATH).read_text()


def test_manifest_and_profile_mutations_are_noncanonical() -> None:
    manifest_raw = (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    assert len(manifest["files"]) == 326
    manifest["files"][0]["sha256"] = "0" * 64
    assert verifier.canonical_bytes(manifest) != manifest_raw
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["authority"]["product_authority"] = True
    assert profile != verifier.build_profile(manifest_raw)
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["implementation"]["allocation_free_claimed"] = True
    assert profile != verifier.build_profile(manifest_raw)
