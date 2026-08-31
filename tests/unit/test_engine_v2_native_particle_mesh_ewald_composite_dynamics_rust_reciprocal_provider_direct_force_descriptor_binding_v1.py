import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_direct_force_descriptor_binding_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 393
    assert result["delta_path_count"] == 10
    assert result["trigger_path_count"] == 210


def test_profile_scopes_direct_force_descriptor_binding() -> None:
    implementation = profile()["implementation"]
    for key in (
        "scope_is_only_native_force_symbol_direct_descriptor_binding",
        "force_descriptor_pointer_temporary_removed",
        "force_descriptor_pointer_declaration_removed",
        "force_descriptor_pointer_assignment_removed",
        "force_symbol_binds_provider_forces_by_address_directly",
        "force_descriptor_direct_binding_only_in_compute_forces_branch",
        "energy_branch_has_zero_force_descriptor_arguments",
        "two_symbol_dispatch_and_five_semantic_routes_preserved",
        "provider_validation_finiteness_rollback_and_commit_preserved",
    ):
        assert implementation[key] is True


def test_exact_three_point_transform_and_inherited_owner_contracts() -> None:
    validation = profile()["validation"]
    assert validation["predecessor_adapter_exact_three_point_force_descriptor_transform"] is True
    assert validation["provider_force_descriptor_declaration_count_exact"] == 1
    assert validation["provider_force_descriptor_population_branch_count_exact"] == 1
    assert validation["force_descriptor_preparation_exact_after_pointer_assignment_removal"] is True
    assert validation["force_descriptor_pointer_declaration_count_exact"] == 0
    assert validation["force_descriptor_pointer_assignment_count_exact"] == 0
    assert validation["force_descriptor_pointer_use_count_exact"] == 0
    assert validation["force_symbol_direct_provider_forces_argument_count_exact"] == 1
    assert validation["energy_symbol_force_descriptor_argument_count_exact"] == 0
    assert validation["active_scratch_reference_declaration_count_exact"] == 1
    assert validation["active_scratch_reference_member_access_count_exact"] == 18
    assert validation["active_scratch_pointer_declaration_count_exact"] == 0
    assert validation["active_scratch_pointer_member_access_count_exact"] == 0
    assert validation["active_scratch_reseating_branch_count_exact"] == 0
    assert validation["optional_emplacement_count_exact"] == 1


def test_dispatch_validation_rollback_and_lifecycle_are_frozen() -> None:
    validation = profile()["validation"]
    for key in (
        "two_branch_two_symbol_adapter_dispatch_exact_after_force_argument_normalization",
        "dispatch_predicates_compute_forces_only",
        "provider_force_source_and_reusable_null_guards_precede_dispatch",
        "force_descriptor_preparation_precedes_dispatch",
        "provider_validation_and_commit_exact_predecessor_bytes",
        "reusable_owner_pointer_parameter_and_null_guard_preserved",
        "reusable_evaluation_force_storage_rollback_guard_exact_predecessor_bytes",
        "provider_force_scratch_destructor_exact_predecessor_bytes",
        "native_adapter_test_exact_predecessor_bytes",
        "native_adapter_test_five_semantic_classes_frozen",
        "raw_public_transactional_peer_exact_predecessor_bytes",
        "rust_provider_and_private_header_exact_predecessor_bytes",
        "production_composite_and_composite_test_exact_predecessor_bytes",
    ):
        assert validation[key] is True
    assert validation["force_private_symbol_adapter_callsite_count_exact"] == 1
    assert validation["energy_private_symbol_adapter_callsite_count_exact"] == 1
    assert validation["reusable_zero_destroy_callback_assertion_count_exact"] == 6
    assert validation["external_owner_scope_destroy_assertion_count_exact"] == 3
    assert validation["stateless_lifecycle_assertion_count_exact"] == 6


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
        "pointer_temporary_removal_performance_improvement_claimed",
        "direct_descriptor_binding_performance_improvement_claimed",
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
    assert value["target_predecessor"]["pull_request"] == 476
    assert value["target_predecessor"]["reviewed_head"] == verifier.PREDECESSOR["reviewed_head"]
    assert value["target_predecessor"]["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert value["target_predecessor"]["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    validation = value["validation"]
    assert validation["exact_delta_path_count"] == 10
    assert validation["implementation_delta_path_count"] == 2
    assert validation["source_manifest_entry_count_exact"] == 393
    assert validation["pull_request_trigger_path_count_exact"] == 210
    assert validation["push_trigger_path_count_exact"] == 210
