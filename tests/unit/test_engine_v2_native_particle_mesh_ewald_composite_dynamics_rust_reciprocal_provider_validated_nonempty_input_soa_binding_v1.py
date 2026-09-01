import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_validated_nonempty_input_soa_binding_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 441
    assert result["delta_path_count"] == 10
    assert result["implementation_delta_path_count"] == 2
    assert result["trigger_path_count"] == 258
    assert result["predecessor_pull_request"] == 484
    assert result["predecessor_merge_tree"] == verifier.PREDECESSOR["merge_tree"]


def test_profile_scopes_validated_nonempty_input_soa_binding() -> None:
    implementation = profile()["implementation"]
    for key in (
        "scope_is_only_native_validated_nonempty_input_soa_binding",
        "input_soa_empty_system_validation_precedes_provider_descriptor",
        "input_soa_count_validation_precedes_provider_descriptor",
        "input_soa_four_channels_nonempty_at_descriptor_binding",
        "input_soa_four_channels_equal_length_at_descriptor_binding",
        "input_soa_position_x_direct_data_binding",
        "input_soa_position_y_direct_data_binding",
        "input_soa_position_z_direct_data_binding",
        "input_soa_charge_direct_data_binding",
        "input_soa_legacy_nullable_helper_removed",
        "input_soa_vector_include_removed",
        "input_soa_provider_descriptor_field_order_preserved",
        "input_soa_caller_owned_addresses_preserved",
        "input_soa_caller_owned_lifetime_spans_provider_dispatch",
        "provider_system_input_pointers_non_null_by_validation",
        "raw_provider_zero_count_abi_semantics_preserved",
        "public_and_private_provider_abi_preserved",
        "error_output_reference_binding_preserved",
        "five_semantic_route_dispatch_preserved",
        "rollback_scratch_validation_and_commit_preserved",
    ):
        assert implementation[key] is True
    assert (
        "scope_is_only_native_error_output_reference_binding"
        not in implementation
    )


def test_exact_validated_nonempty_input_soa_transform_evidence() -> None:
    validation = profile()["validation"]
    expected = {
        "exact_delta_path_count": 10,
        "implementation_delta_path_count": 2,
        "successor_evidence_path_count": 6,
        "predecessor_freeze_wiring_path_count": 2,
        "source_manifest_entry_count_exact": 441,
        "pull_request_trigger_path_count_exact": 258,
        "push_trigger_path_count_exact": 258,
        "legacy_vector_include_count_exact": 0,
        "legacy_data_or_null_helper_count_exact": 0,
        "legacy_data_or_null_call_count_exact": 0,
        "direct_provider_input_data_binding_count_exact": 4,
        "position_x_direct_data_binding_count_exact": 1,
        "position_y_direct_data_binding_count_exact": 1,
        "position_z_direct_data_binding_count_exact": 1,
        "charge_direct_data_binding_count_exact": 1,
        "empty_system_validation_count_exact": 1,
        "input_count_validation_channel_count_exact": 4,
    }
    for key, value in expected.items():
        assert validation[key] == value
    for key in (
        "predecessor_adapter_exact_error_output_reference_binding_bytes",
        "adapter_exact_validated_nonempty_input_soa_transform",
        "adapter_outside_input_soa_binding_exact_predecessor_bytes",
        "empty_system_validation_precedes_provider_descriptor",
        "input_count_validation_precedes_provider_descriptor",
        "direct_input_bindings_follow_provider_descriptor_metadata",
        "direct_input_bindings_precede_provider_dispatch",
        "public_wrappers_exact_predecessor_bytes",
        "dispatch_rollback_scratch_validation_commit_exact_predecessor_bytes",
        "canonical_vendor_adapter_byte_identical",
        "native_adapter_test_exact_predecessor_bytes",
        "predecessor_workflow_detaches_exact_merge_object",
        "predecessor_unit_skips_only_when_successor_profile_exists",
    ):
        assert validation[key] is True


def test_inherited_routes_rollback_and_transactionality_remain_frozen() -> None:
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
        "validated_nonempty_input_soa_binding_performance_improvement_claimed",
        "validated_nonempty_input_soa_runtime_lifetime_enforcement_claimed",
        "validated_nonempty_input_soa_raw_provider_nullability_changed_claimed",
        "validated_nonempty_input_soa_object_layout_equivalence_claimed",
        "error_output_reference_binding_performance_improvement_claimed",
        "error_output_reference_runtime_lifetime_enforcement_claimed",
        "error_output_nullability_elision_claimed",
        "error_output_object_layout_equivalence_claimed",
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


def test_exact_pr484_predecessor_and_evidence_graph() -> None:
    data = profile()
    assert data["target_predecessor"] == verifier.PREDECESSOR
    assert verifier.PREDECESSOR["pull_request"] == 484
    assert verifier.PREDECESSOR["source_manifest_entry_count"] == 435
    manifest = json.loads((ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes())
    assert len(manifest["files"]) == 441
    assert manifest["evidence_paths"] == sorted(
        path.as_posix() for path in verifier.EVIDENCE_PATHS
    )
    assert [row["path"] for row in manifest["files"]] == sorted(
        {row["path"] for row in manifest["files"]}
    )
