import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_stateless_forceful_all_scratch_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 363
    assert result["delta_path_count"] == 11
    assert result["trigger_path_count"] == 180


def test_profile_scopes_stateless_forceful_all_scratch_route() -> None:
    value = profile()
    implementation = value["implementation"]
    for key in (
        "scope_is_only_native_stateless_forceful_adapter_route",
        "stateless_forceful_all_three_scratch_route_enabled",
        "stateless_forceful_direct_route_removed_from_adapter",
        "existing_all_three_scratch_force_entry_reused",
        "provider_force_source_all_three_scratch_route_preserved",
        "reusable_forceful_all_three_scratch_route_preserved",
        "five_adapter_branches_remain_distinct",
        "adapter_uses_three_unique_provider_symbols",
        "call_local_provider_force_scratch_selected_for_stateless_calls",
        "stateless_forceful_call_local_force_xyz_used",
        "stateless_scratch_lifetime_is_single_call",
        "force_output_allocation_site_not_consumed_by_all_scratch_entry",
        "production_composite_caller_exact_predecessor_bytes",
        "production_stateless_forceful_caller_reaches_changed_adapter_route",
        "production_stateless_forceful_caller_tests_enabled",
    ):
        assert implementation[key] is True
    assert implementation["new_rust_or_header_entry_added"] is False
    assert value["validation"][
        "release_and_sanitizer_cover_stateless_reciprocal_pme_and_composite_callers"
    ] is True
    abi = value["abi"]
    assert abi["private_provider_abi_changed"] is False
    assert abi["new_private_hidden_symbol_added"] is False
    assert abi["reused_private_hidden_symbol"] == verifier.PRIVATE_SYMBOL


def test_call_local_empty_descriptor_lifecycle_is_exact() -> None:
    implementation = profile()["implementation"]
    for key in (
        "stateless_forceful_call_local_reciprocal_workspace_initially_empty",
        "stateless_forceful_call_local_neutrality_sort_scratch_initially_empty",
        "stateless_forceful_call_local_particle_assignment_scratch_initially_empty",
        "stateless_forceful_three_descriptors_initially_exact_all_zero",
        "stateless_forceful_three_descriptors_pairwise_distinct",
        "stateless_forceful_three_descriptors_destroyed_before_return",
        "stateless_forceful_matching_destroy_callbacks_exactly_once_each",
        "stateless_forceful_lifecycle_tested_on_success_typed_failure_and_nonfinite_success",
    ):
        assert implementation[key] is True


def test_stateless_evaluation_success_only_boundary_is_exact() -> None:
    implementation = profile()["implementation"]
    for key in (
        "external_evaluation_is_success_only",
        "reusable_evaluation_force_storage_rollback_guard_preserved",
        "stateless_failure_preserves_evaluation_energy_bits",
        "stateless_failure_preserves_evaluation_force_address_capacity_size_and_bits",
        "provider_success_force_finiteness_preflight_precedes_external_copy",
        "stateless_late_typed_failure_exact_evaluation_rollback_tested",
        "stateless_nonfinite_force_success_exact_evaluation_rollback_tested",
        "call_local_force_xyz_may_change_on_late_error_or_nonfinite_success",
    ):
        assert implementation[key] is True
    for key in (
        "workspace_payload_transactionality_claimed",
        "neutrality_sort_payload_transactionality_claimed",
        "particle_assignment_payload_transactionality_claimed",
        "call_local_scratch_transactionality_claimed",
        "call_local_force_xyz_transactionality_claimed",
        "error_output_transactionality_claimed",
    ):
        assert implementation[key] is False


def test_profile_preserves_scientific_and_operational_boundaries() -> None:
    implementation = profile()["implementation"]
    for key in (
        "persistent_scratch_reuse_claimed",
        "cross_call_scratch_reuse_claimed",
        "allocation_free_claimed",
        "provider_allocation_free_claimed",
        "steady_state_allocation_free_claimed",
        "production_allocation_elision_claimed",
        "performance_claimed",
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


def test_fake_provider_and_production_scope_are_bounded() -> None:
    implementation = profile()["implementation"]
    assert implementation["fake_provider_is_dispatch_and_commit_separation_test_double"] is True
    assert implementation["fake_provider_production_authority"] is False
    assert implementation["fake_provider_scientific_authority"] is False
    assert implementation["fake_provider_executes_real_rust_allocator"] is False
    assert implementation["real_rust_provider_sanitizer_execution_claimed"] is False


def test_predecessor_and_public_contracts_are_frozen() -> None:
    value = profile()
    assert value["target_predecessor"]["pull_request"] == 471
    assert value["target_predecessor"]["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert value["target_predecessor"]["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    assert value["abi"]["public_symbols"] == list(verifier.PUBLIC_SYMBOLS)
    validation = value["validation"]
    assert validation["exact_delta_path_count"] == 11
    assert validation["source_manifest_entry_count_exact"] == 363
    assert validation["pull_request_trigger_path_count_exact"] == 180
    assert validation["push_trigger_path_count_exact"] == 180
