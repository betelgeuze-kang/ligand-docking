import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_active_scratch_reference_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 387
    assert result["delta_path_count"] == 10
    assert result["trigger_path_count"] == 204


def test_profile_scopes_non_null_active_scratch_reference_binding() -> None:
    implementation = profile()["implementation"]
    for key in (
        "scope_is_only_native_provider_active_scratch_reference_binding_and_member_syntax",
        "active_provider_force_scratch_is_non_null_reference_after_guard",
        "active_provider_force_scratch_reference_bound_once",
        "active_provider_force_scratch_pointer_reseating_removed",
        "active_provider_force_scratch_pointer_member_access_removed",
        "reusable_owner_pointer_parameter_preserved",
        "reusable_owner_null_guard_precedes_reference_binding",
        "reference_selection_uses_reuse_force_storage_only",
        "stateless_reference_binds_emplaced_call_local_owner",
        "reusable_reference_binds_external_owner",
        "two_symbol_dispatch_and_five_semantic_routes_preserved",
    ):
        assert implementation[key] is True


def test_inherited_optional_owner_and_lifecycle_contracts_are_frozen() -> None:
    implementation = profile()["implementation"]
    for key in (
        "conditional_call_local_provider_force_scratch_enabled",
        "call_local_provider_force_scratch_emplaced_only_for_stateless_calls",
        "call_local_provider_force_scratch_disengaged_for_reusable_calls",
        "active_provider_force_scratch_uses_emplaced_owner_for_stateless_calls",
        "active_provider_force_scratch_uses_external_owner_for_reusable_calls",
        "call_local_optional_lifetime_spans_dispatch_validation_and_commit",
        "reusable_unused_call_local_destroy_callbacks_elided",
        "reusable_calls_have_zero_destroy_callbacks_before_external_owner_scope_exit",
        "external_reusable_owner_matching_destroy_callbacks_exactly_once_each_at_scope_exit",
        "stateless_call_local_destroy_lifecycle_preserved",
    ):
        assert implementation[key] is True
    validation = profile()["validation"]
    assert validation["predecessor_adapter_exact_active_scratch_reference_transform"] is True
    assert validation["active_scratch_reference_binding_source_exact"] is True
    assert validation["active_scratch_reference_declaration_count_exact"] == 1
    assert validation["active_scratch_reference_member_access_count_exact"] == 18
    assert validation["active_scratch_pointer_declaration_count_exact"] == 0
    assert validation["active_scratch_pointer_member_access_count_exact"] == 0
    assert validation["active_scratch_reseating_branch_count_exact"] == 0
    assert validation["optional_emplacement_count_exact"] == 1
    assert validation["native_adapter_test_exact_predecessor_bytes"] is True
    assert validation["native_adapter_test_five_semantic_classes_frozen"] is True
    assert validation["reusable_zero_destroy_callback_assertion_count_exact"] == 6
    assert validation["external_owner_scope_destroy_assertion_count_exact"] == 3
    assert validation["stateless_lifecycle_assertion_count_exact"] == 6


def test_two_branch_dispatch_and_external_commit_boundaries_are_exact() -> None:
    validation = profile()["validation"]
    for key in (
        "two_branch_two_symbol_adapter_dispatch_exact_after_member_syntax_normalization",
        "dispatch_predicates_compute_forces_only",
        "provider_force_source_and_reusable_null_guards_precede_dispatch",
        "force_descriptor_pointer_preparation_precedes_dispatch",
        "provider_validation_and_commit_exact_after_member_syntax_normalization",
        "reusable_owner_pointer_parameter_and_null_guard_preserved",
        "reusable_evaluation_force_storage_rollback_guard_exact_predecessor_bytes",
        "provider_force_scratch_destructor_exact_predecessor_bytes",
        "raw_public_transactional_peer_exact_predecessor_bytes",
        "rust_provider_and_private_header_exact_predecessor_bytes",
        "production_composite_and_composite_test_exact_predecessor_bytes",
    ):
        assert validation[key] is True
    assert validation["force_private_symbol_adapter_callsite_count_exact"] == 1
    assert validation["energy_private_symbol_adapter_callsite_count_exact"] == 1


def test_abi_and_operational_boundaries_are_unchanged() -> None:
    value = profile()
    abi = value["abi"]
    assert abi["public_abi_changed"] is False
    assert abi["private_provider_abi_changed"] is False
    assert abi["new_public_symbol_added"] is False
    assert abi["new_private_hidden_symbol_added"] is False
    assert abi["reused_private_hidden_symbol"] == verifier.PRIVATE_SYMBOL
    assert abi["public_symbols"] == list(verifier.PUBLIC_SYMBOLS)
    assert set(value["operational_boundary"]["blockers"]) == set(verifier.BLOCKERS)
    assert value["operational_boundary"]["unresolved_operational_decisions"] == 32
    assert all(flag is False for flag in value["authority"].values())


def test_claim_boundaries_remain_explicitly_false() -> None:
    implementation = profile()["implementation"]
    for key in (
        "allocation_free_claimed",
        "allocation_count_claimed",
        "allocation_behavior_changed_claimed",
        "provider_allocation_free_claimed",
        "steady_state_allocation_free_claimed",
        "production_allocation_elision_claimed",
        "heap_allocation_elision_claimed",
        "provider_allocation_elision_claimed",
        "stack_storage_reduction_claimed",
        "scratch_storage_footprint_reduction_claimed",
        "object_size_reduction_claimed",
        "peak_memory_reduction_claimed",
        "branch_reduction_performance_improvement_claimed",
        "callsite_reduction_performance_improvement_claimed",
        "nullability_elision_performance_improvement_claimed",
        "reference_binding_performance_improvement_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "scientific_claimed",
        "scientific_equivalence_claimed",
        "molecular_execution_claimed",
        "hip_execution_claimed",
        "product_claimed",
        "operational_readiness_claimed",
    ):
        assert implementation[key] is False


def test_predecessor_and_evidence_graph_are_exact() -> None:
    value = profile()
    assert value["target_predecessor"]["pull_request"] == 475
    assert value["target_predecessor"]["reviewed_head"] == verifier.PREDECESSOR["reviewed_head"]
    assert value["target_predecessor"]["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert value["target_predecessor"]["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    validation = value["validation"]
    assert validation["exact_delta_path_count"] == 10
    assert validation["implementation_delta_path_count"] == 2
    assert validation["source_manifest_entry_count_exact"] == 387
    assert validation["pull_request_trigger_path_count_exact"] == 204
    assert validation["push_trigger_path_count_exact"] == 204
