import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_two_symbol_dispatch_consolidation_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 381
    assert result["delta_path_count"] == 10
    assert result["trigger_path_count"] == 198


def test_profile_scopes_two_symbol_dispatch_consolidation() -> None:
    implementation = profile()["implementation"]
    for key in (
        "scope_is_only_native_provider_dispatch_branch_and_callsite_consolidation",
        "five_adapter_branches_collapsed_to_two_compute_forces_branches",
        "dispatch_uses_compute_forces_only",
        "dispatch_predicates_exclude_reuse_and_output_metadata",
        "provider_force_source_guard_precedes_dispatch",
        "reusable_owner_null_guard_precedes_dispatch",
        "force_descriptor_pointer_preparation_precedes_dispatch",
        "provider_validation_finiteness_rollback_and_commit_preserved",
        "native_adapter_test_exact_predecessor_bytes",
        "five_semantic_route_classes_preserved",
        "adapter_uses_two_unique_provider_symbols",
    ):
        assert implementation[key] is True
    assert implementation["five_adapter_branches_remain_distinct"] is False
    assert implementation["force_private_symbol_adapter_callsite_count_exact"] == 1
    assert implementation["energy_private_symbol_adapter_callsite_count_exact"] == 1


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
    assert validation["conditional_optional_selection_exact_predecessor_bytes"] is True
    assert validation["native_adapter_test_exact_predecessor_bytes"] is True
    assert validation["native_adapter_test_five_semantic_classes_frozen"] is True
    assert validation["reusable_zero_destroy_callback_assertion_count_exact"] == 6
    assert validation["external_owner_scope_destroy_assertion_count_exact"] == 3
    assert validation["stateless_lifecycle_assertion_count_exact"] == 6


def test_two_branch_dispatch_and_external_commit_boundaries_are_exact() -> None:
    validation = profile()["validation"]
    for key in (
        "predecessor_adapter_exact_two_symbol_dispatch_transform",
        "two_branch_two_symbol_adapter_dispatch_exact",
        "dispatch_predicates_compute_forces_only",
        "provider_force_source_and_reusable_null_guards_precede_dispatch",
        "force_descriptor_pointer_preparation_precedes_dispatch",
        "provider_validation_and_commit_exact_predecessor_bytes",
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
    assert value["target_predecessor"]["pull_request"] == 474
    assert value["target_predecessor"]["reviewed_head"] == verifier.PREDECESSOR["reviewed_head"]
    assert value["target_predecessor"]["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert value["target_predecessor"]["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    validation = value["validation"]
    assert validation["exact_delta_path_count"] == 10
    assert validation["implementation_delta_path_count"] == 2
    assert validation["source_manifest_entry_count_exact"] == 381
    assert validation["pull_request_trigger_path_count_exact"] == 198
    assert validation["push_trigger_path_count_exact"] == 198
