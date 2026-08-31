import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reusable_forceful_all_scratch_reuse_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 357
    assert result["delta_path_count"] == 11
    assert result["trigger_path_count"] == 174


def test_profile_scopes_reusable_forceful_all_scratch_route() -> None:
    value = profile()
    implementation = value["implementation"]
    for key in (
        "scope_is_only_native_reusable_forceful_adapter_owner_route",
        "reusable_forceful_all_three_scratch_route_enabled",
        "reusable_forceful_workspace_only_route_removed_from_adapter",
        "existing_all_three_scratch_force_entry_reused",
        "provider_force_source_all_three_scratch_route_preserved",
        "five_adapter_branches_remain_distinct",
        "adapter_uses_four_unique_provider_symbols",
        "reusable_forceful_owner_reciprocal_workspace_reused",
        "reusable_forceful_owner_neutrality_sort_scratch_reused",
        "reusable_forceful_owner_particle_assignment_scratch_reused",
        "reusable_forceful_owner_force_xyz_reused",
        "force_output_allocation_site_not_consumed_by_all_scratch_entry",
        "production_composite_forceful_route_unchanged",
    ):
        assert implementation[key] is True
    assert implementation["new_rust_or_header_entry_added"] is False
    abi = value["abi"]
    assert abi["private_provider_abi_changed"] is False
    assert abi["new_private_hidden_symbol_added"] is False
    assert abi["reused_private_hidden_symbol"] == verifier.PRIVATE_SYMBOL


def test_external_evaluation_success_only_boundary_is_exact() -> None:
    implementation = profile()["implementation"]
    for key in (
        "external_evaluation_is_success_only",
        "external_evaluation_force_storage_rollback_guard_added",
        "external_evaluation_failure_preserves_energy_bits",
        "external_evaluation_failure_preserves_force_address_capacity_size_and_bits",
        "provider_success_force_finiteness_preflight_precedes_external_copy",
        "late_typed_failure_exact_evaluation_rollback_tested",
        "nonfinite_force_on_success_exact_evaluation_rollback_tested",
        "derived_force_xyz_may_change_on_late_error_or_nonfinite_success",
    ):
        assert implementation[key] is True
    for key in (
        "workspace_payload_transactionality_claimed",
        "neutrality_sort_payload_transactionality_claimed",
        "particle_assignment_payload_transactionality_claimed",
        "owner_force_xyz_transactionality_claimed",
        "error_output_transactionality_claimed",
    ):
        assert implementation[key] is False


def test_profile_preserves_scientific_and_operational_boundaries() -> None:
    implementation = profile()["implementation"]
    for key in (
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
    assert implementation["changed_reusable_forceful_branch_has_no_production_caller_in_scope"] is True


def test_predecessor_and_public_contracts_are_frozen() -> None:
    value = profile()
    assert value["target_predecessor"]["pull_request"] == 470
    assert value["target_predecessor"]["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert value["target_predecessor"]["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    assert value["abi"]["public_symbols"] == list(verifier.PUBLIC_SYMBOLS)
    validation = value["validation"]
    assert validation["exact_delta_path_count"] == 11
    assert validation["source_manifest_entry_count_exact"] == 357
    assert validation["pull_request_trigger_path_count_exact"] == 174
    assert validation["push_trigger_path_count_exact"] == 174
