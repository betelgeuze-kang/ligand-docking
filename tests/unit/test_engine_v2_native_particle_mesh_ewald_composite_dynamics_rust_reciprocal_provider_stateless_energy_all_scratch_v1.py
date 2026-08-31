import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_stateless_energy_all_scratch_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 369
    assert result["delta_path_count"] == 11
    assert result["trigger_path_count"] == 186


def test_profile_scopes_stateless_energy_all_scratch_route() -> None:
    value = profile()
    implementation = value["implementation"]
    for key in (
        "scope_is_only_native_stateless_energy_adapter_route",
        "stateless_energy_all_three_scratch_route_enabled",
        "stateless_energy_public_transactional_route_removed_from_adapter",
        "existing_all_three_scratch_energy_entry_reused",
        "provider_force_source_all_three_scratch_route_preserved",
        "reusable_forceful_all_three_scratch_route_preserved",
        "reusable_force_free_all_three_scratch_energy_route_preserved",
        "stateless_forceful_all_three_scratch_route_preserved",
        "five_adapter_branches_remain_distinct",
        "adapter_uses_two_unique_provider_symbols",
        "call_local_provider_force_scratch_selected_for_stateless_calls",
        "force_output_allocation_site_not_consumed_by_stateless_energy_route",
        "production_composite_caller_exact_predecessor_bytes",
        "production_stateless_energy_caller_reaches_changed_adapter_route",
        "production_stateless_energy_caller_tests_enabled",
    ):
        assert implementation[key] is True
    assert implementation["new_rust_or_header_entry_added"] is False
    assert value["validation"][
        "release_and_sanitizer_cover_stateless_energy_reciprocal_pme_and_composite_callers"
    ] is True
    abi = value["abi"]
    assert abi["private_provider_abi_changed"] is False
    assert abi["new_private_hidden_symbol_added"] is False
    assert abi["reused_private_hidden_symbol"] == verifier.PRIVATE_SYMBOL


def test_call_local_empty_descriptor_lifecycle_is_exact() -> None:
    implementation = profile()["implementation"]
    for key in (
        "stateless_energy_call_local_reciprocal_workspace_initially_empty",
        "stateless_energy_call_local_neutrality_sort_scratch_initially_empty",
        "stateless_energy_call_local_particle_assignment_scratch_initially_empty",
        "stateless_energy_three_descriptors_initially_exact_all_zero",
        "stateless_energy_three_descriptors_pairwise_distinct",
        "stateless_energy_call_local_force_xyz_remain_empty",
        "stateless_energy_three_descriptors_destroyed_before_return",
        "stateless_energy_matching_destroy_callbacks_exactly_once_each",
        "stateless_energy_lifecycle_tested_on_success_typed_failure_and_nonfinite_success",
        "stateless_scratch_lifetime_is_single_call",
    ):
        assert implementation[key] is True


def test_stateless_energy_evaluation_success_only_boundary_is_exact() -> None:
    implementation = profile()["implementation"]
    for key in (
        "external_evaluation_is_success_only",
        "reusable_evaluation_force_storage_rollback_guard_preserved",
        "stateless_failure_preserves_evaluation_energy_bits",
        "stateless_failure_preserves_evaluation_force_address_capacity_size_and_bits",
        "provider_success_energy_finiteness_preflight_precedes_external_commit",
        "stateless_energy_late_typed_failure_exact_evaluation_rollback_tested",
        "stateless_nonfinite_energy_success_exact_evaluation_rollback_tested",
        "raw_public_transactional_peer_frozen",
    ):
        assert implementation[key] is True
    for key in (
        "workspace_payload_transactionality_claimed",
        "neutrality_sort_payload_transactionality_claimed",
        "particle_assignment_payload_transactionality_claimed",
        "call_local_scratch_transactionality_claimed",
        "error_output_transactionality_claimed",
    ):
        assert implementation[key] is False


def test_profile_preserves_claim_and_operational_boundaries() -> None:
    implementation = profile()["implementation"]
    for key in (
        "persistent_scratch_reuse_claimed",
        "cross_call_scratch_reuse_claimed",
        "allocation_free_claimed",
        "allocation_count_claimed",
        "provider_allocation_free_claimed",
        "steady_state_allocation_free_claimed",
        "production_allocation_elision_claimed",
        "performance_claimed",
        "peak_memory_reduction_claimed",
        "acceleration_claimed",
        "scientific_claimed",
        "scientific_equivalence_claimed",
        "cross_lane_bit_parity_claimed",
        "molecular_execution_claimed",
        "hip_execution_claimed",
        "product_claimed",
        "operational_readiness_claimed",
    ):
        assert implementation[key] is False
    value = profile()
    assert set(value["operational_boundary"]["blockers"]) == set(verifier.BLOCKERS)
    assert value["operational_boundary"]["unresolved_operational_decisions"] == 32
    assert all(flag is False for flag in value["authority"].values())


def test_fake_provider_and_production_scope_are_bounded() -> None:
    implementation = profile()["implementation"]
    assert implementation["fake_provider_is_dispatch_and_commit_separation_test_double"] is True
    assert implementation["fake_provider_production_authority"] is False
    assert implementation["fake_provider_scientific_authority"] is False
    assert implementation["fake_provider_executes_real_rust_allocator"] is False
    assert implementation["fake_provider_executes_real_rust_panic_boundary"] is False
    assert implementation["real_rust_provider_sanitizer_execution_claimed"] is False


def test_predecessor_and_public_contracts_are_frozen() -> None:
    value = profile()
    assert value["target_predecessor"]["pull_request"] == 472
    assert value["target_predecessor"]["reviewed_head"] == verifier.PREDECESSOR["reviewed_head"]
    assert value["target_predecessor"]["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert value["target_predecessor"]["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    assert value["abi"]["public_symbols"] == list(verifier.PUBLIC_SYMBOLS)
    validation = value["validation"]
    assert validation["exact_delta_path_count"] == 11
    assert validation["source_manifest_entry_count_exact"] == 369
    assert validation["pull_request_trigger_path_count_exact"] == 186
    assert validation["push_trigger_path_count_exact"] == 186
    assert validation["five_branch_two_symbol_adapter_dispatch_exact"] is True
    assert validation["raw_public_transactional_peer_exact_predecessor_bytes"] is True
    assert validation["public_transactional_provider_symbol_zero_adapter_call_sites"] is True
