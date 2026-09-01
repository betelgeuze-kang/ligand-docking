import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_error_output_reference_binding_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 435
    assert result["delta_path_count"] == 10
    assert result["implementation_delta_path_count"] == 2
    assert result["trigger_path_count"] == 252
    assert result["predecessor_pull_request"] == 483
    assert result["predecessor_merge_tree"] == verifier.PREDECESSOR["merge_tree"]


def test_profile_scopes_error_output_reference_binding() -> None:
    implementation = profile()["implementation"]
    for key in (
        "scope_is_only_native_error_output_reference_binding",
        "error_output_public_pointer_signatures_preserved",
        "error_output_null_validation_precedes_reference_binding",
        "error_output_reference_is_non_null_by_construction",
        "error_output_reference_bound_once",
        "error_output_initialization_uses_bound_reference",
        "error_output_member_writes_use_bound_reference",
        "error_output_empty_system_mapping_preserved",
        "error_output_capacity_mapping_preserved",
        "error_output_count_mismatch_mapping_preserved",
        "error_output_provider_typed_mapping_preserved",
        "error_output_unknown_provider_mapping_preserved",
        "error_output_wrappers_preserved",
        "five_semantic_route_dispatch_preserved",
        "rollback_scratch_validation_and_commit_preserved",
    ):
        assert implementation[key] is True
    assert (
        "scope_is_only_native_evaluation_rollback_output_force_storage_binding"
        not in implementation
    )


def test_exact_error_output_reference_transform_evidence() -> None:
    validation = profile()["validation"]
    expected = {
        "exact_delta_path_count": 10,
        "implementation_delta_path_count": 2,
        "successor_evidence_path_count": 6,
        "predecessor_freeze_wiring_path_count": 2,
        "source_manifest_entry_count_exact": 435,
        "pull_request_trigger_path_count_exact": 252,
        "push_trigger_path_count_exact": 252,
        "evaluate_impl_out_error_pointer_parameter_count_exact": 1,
        "public_error_output_pointer_signature_count_exact": 4,
        "error_output_null_check_count_exact": 1,
        "error_output_reference_binding_count_exact": 1,
        "error_output_reference_initialization_count_exact": 1,
        "legacy_error_output_initialization_count_exact": 0,
        "legacy_error_output_member_access_count_exact": 0,
        "bound_error_output_member_access_count_exact": 8,
        "bound_error_output_code_write_count_exact": 4,
        "bound_error_output_detail_write_count_exact": 4,
    }
    for key, value in expected.items():
        assert validation[key] == value
    for key in (
        "predecessor_adapter_exact_error_output_reference_binding_transform",
        "adapter_outside_error_output_binding_exact_predecessor_bytes",
        "error_output_null_check_precedes_reference_binding",
        "error_output_reference_binding_precedes_initialization",
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


def test_exact_pr483_predecessor_and_evidence_graph() -> None:
    data = profile()
    assert data["target_predecessor"] == verifier.PREDECESSOR
    assert verifier.PREDECESSOR["pull_request"] == 483
    assert verifier.PREDECESSOR["source_manifest_entry_count"] == 429
    manifest = json.loads((ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes())
    assert len(manifest["files"]) == 435
    assert manifest["evidence_paths"] == sorted(
        path.as_posix() for path in verifier.EVIDENCE_PATHS
    )
    assert [row["path"] for row in manifest["files"]] == sorted(
        {row["path"] for row in manifest["files"]}
    )
