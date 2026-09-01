import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_evaluation_rollback_force_storage_binding_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 423
    assert result["delta_path_count"] == 10
    assert result["implementation_delta_path_count"] == 2
    assert result["trigger_path_count"] == 240
    assert result["predecessor_pull_request"] == 481
    assert result["predecessor_merge_tree"] == verifier.PREDECESSOR["merge_tree"]


def test_profile_scopes_evaluation_rollback_force_storage_binding() -> None:
    implementation = profile()["implementation"]
    for key in (
        "scope_is_only_native_evaluation_rollback_force_storage_binding",
        "evaluation_rollback_candidate_force_storage_type_alias_exact",
        "evaluation_rollback_candidate_force_storage_type_derived_from_evaluation_member",
        "evaluation_rollback_candidate_force_storage_nothrow_swap_assertion_exact",
        "evaluation_rollback_candidate_force_storage_is_non_null_reference",
        "evaluation_rollback_candidate_force_storage_reference_bound_once",
        "evaluation_rollback_whole_candidate_reference_parameter_removed",
        "evaluation_rollback_whole_candidate_reference_member_removed",
        "evaluation_rollback_candidate_force_storage_uses_direct_reference_access",
        "evaluation_rollback_callsite_passes_candidate_force_storage",
        "evaluation_rollback_candidate_declaration_precedes_guard",
        "evaluation_rollback_candidate_force_storage_lifetime_order_preserved",
        "evaluation_rollback_activation_predicate_localized_at_callsite",
        "evaluation_rollback_activation_uses_compute_forces_and_reuse_force_storage_only",
        "evaluation_rollback_output_pointer_is_sole_activation_and_commit_sentinel",
        "evaluation_rollback_initial_swap_and_destructor_restore_preserved",
        "evaluation_rollback_commit_disarms_via_output_only",
        "evaluation_rollback_copy_deletion_preserved",
        "five_semantic_route_rollback_activation_truth_table_preserved",
        "dispatch_status_normalization_binding_preserved",
    ):
        assert implementation[key] is True
    for stale_key in (
        "scope_is_only_native_evaluation_rollback_state_binding",
        "evaluation_rollback_candidate_is_non_null_reference",
        "evaluation_rollback_candidate_reference_bound_once",
        "evaluation_rollback_candidate_uses_reference_member_access",
    ):
        assert stale_key not in implementation


def test_exact_rollback_force_storage_binding_transform_evidence() -> None:
    validation = profile()["validation"]
    expected = {
        "exact_delta_path_count": 10,
        "implementation_delta_path_count": 2,
        "successor_evidence_path_count": 6,
        "predecessor_freeze_wiring_path_count": 2,
        "source_manifest_entry_count_exact": 423,
        "pull_request_trigger_path_count_exact": 240,
        "push_trigger_path_count_exact": 240,
        "rollback_class_count_exact": 1,
        "rollback_candidate_pointer_declaration_count_exact": 0,
        "rollback_candidate_pointer_member_access_count_exact": 0,
        "rollback_candidate_null_assignment_count_exact": 0,
        "rollback_candidate_conditional_initializer_count_exact": 0,
        "rollback_candidate_address_callsite_count_exact": 0,
        "rollback_force_storage_alias_count_exact": 1,
        "rollback_force_storage_alias_static_assert_count_exact": 1,
        "rollback_legacy_force_storage_type_expression_count_exact": 0,
        "rollback_whole_candidate_reference_declaration_count_exact": 0,
        "rollback_force_storage_reference_declaration_count_exact": 2,
        "rollback_force_storage_reference_initializer_count_exact": 1,
        "rollback_force_storage_reference_member_access_count_exact": 2,
        "rollback_whole_candidate_callsite_count_exact": 0,
        "rollback_force_storage_callsite_count_exact": 1,
        "rollback_enabled_parameter_count_exact": 0,
        "rollback_output_enabled_initializer_count_exact": 0,
        "rollback_output_direct_initializer_count_exact": 1,
        "rollback_callsite_activation_conditional_count_exact": 1,
        "rollback_output_null_assignment_count_exact": 1,
        "rollback_output_nonnull_guard_count_exact": 2,
        "rollback_copy_deletion_count_exact": 2,
        "rollback_force_swap_count_exact": 2,
        "rollback_guard_construction_count_exact": 1,
        "rollback_commit_call_count_exact": 1,
    }
    for key, value in expected.items():
        assert validation[key] == value
    for key in (
        "predecessor_adapter_exact_evaluation_rollback_force_storage_binding_transform",
        "evaluation_rollback_force_storage_binding_source_exact",
        "adapter_outside_evaluation_rollback_force_storage_regions_exact_predecessor_bytes",
        "rollback_force_storage_type_binding_region_exact",
        "dispatch_status_normalization_region_exact_predecessor_bytes",
        "rollback_candidate_declaration_precedes_guard",
        "rollback_guard_precedes_optional_scratch_declaration",
        "rollback_activation_predicate_exact",
        "post_dispatch_validation_and_commit_exact_predecessor_bytes",
        "canonical_vendor_adapter_byte_identical",
        "native_adapter_test_exact_predecessor_bytes",
    ):
        assert validation[key] is True
    for stale_key in (
        "predecessor_adapter_exact_evaluation_rollback_state_binding_transform",
        "evaluation_rollback_state_binding_source_exact",
        "adapter_outside_evaluation_rollback_state_regions_exact_predecessor_bytes",
        "rollback_candidate_reference_declaration_count_exact",
        "rollback_candidate_reference_member_access_count_exact",
        "rollback_candidate_reference_initializer_count_exact",
        "rollback_candidate_reference_callsite_count_exact",
    ):
        assert stale_key not in validation


def test_inherited_dispatch_routes_and_transactionality_remain_frozen() -> None:
    implementation = profile()["implementation"]
    for key in (
        "two_symbol_dispatch_and_five_semantic_routes_preserved",
        "provider_validation_finiteness_rollback_and_commit_preserved",
        "native_adapter_test_exact_predecessor_bytes",
        "stateless_failure_preserves_evaluation_energy_bits",
        "stateless_failure_preserves_evaluation_force_address_capacity_size_and_bits",
        "external_evaluation_is_success_only",
        "force_descriptor_branch_localization_preserved",
        "provider_error_descriptor_remains_common_to_both_dispatch_branches",
    ):
        assert implementation[key] is True


def test_abi_and_operational_authority_remain_closed() -> None:
    data = profile()
    abi = data["abi"]
    assert abi["public_abi_changed"] is False
    assert abi["new_public_symbol_added"] is False
    assert abi["private_provider_abi_changed"] is False
    assert abi["status_abi_changed"] is False
    assert abi["checkpoint_format_changed"] is False
    assert all(value is False for value in data["authority"].values())
    boundary = data["operational_boundary"]
    assert boundary["blockers"] == sorted(boundary["blockers"])
    assert len(boundary["blockers"]) == 4
    assert boundary["unresolved_operational_decisions"] == 32


def test_forbidden_claims_remain_false() -> None:
    implementation = profile()["implementation"]
    for key in (
        "evaluation_rollback_force_storage_binding_performance_improvement_claimed",
        "evaluation_rollback_force_storage_reference_performance_improvement_claimed",
        "evaluation_rollback_force_storage_object_layout_equivalence_claimed",
        "evaluation_rollback_force_storage_runtime_lifetime_enforcement_claimed",
        "evaluation_rollback_guard_is_force_storage_only_claimed",
        "evaluation_rollback_candidate_reference_performance_improvement_claimed",
        "evaluation_rollback_enabled_parameter_removal_performance_improvement_claimed",
        "evaluation_rollback_object_layout_equivalence_claimed",
        "evaluation_rollback_reference_runtime_lifetime_enforcement_claimed",
        "reference_binding_performance_improvement_claimed",
        "nullability_elision_performance_improvement_claimed",
        "object_size_reduction_claimed",
        "stack_storage_reduction_claimed",
        "allocation_free_claimed",
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


def test_exact_pr481_predecessor_and_evidence_graph() -> None:
    data = profile()
    assert data["target_predecessor"] == verifier.PREDECESSOR
    assert verifier.PREDECESSOR["pull_request"] == 481
    assert verifier.PREDECESSOR["source_manifest_entry_count"] == 417
    validation = data["validation"]
    assert validation["predecessor_workflow_detaches_exact_merge_object"] is True
    assert validation["predecessor_unit_skips_only_when_successor_profile_exists"] is True
    manifest = json.loads((ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes())
    assert len(manifest["files"]) == 423
    assert manifest["evidence_paths"] == sorted(
        path.as_posix() for path in verifier.EVIDENCE_PATHS
    )
