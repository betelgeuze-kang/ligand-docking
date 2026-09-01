import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_dispatch_status_single_assignment_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 405
    assert result["delta_path_count"] == 10
    assert result["implementation_delta_path_count"] == 2
    assert result["trigger_path_count"] == 222
    assert result["predecessor_pull_request"] == 478
    assert result["predecessor_merge_tree"] == verifier.PREDECESSOR["merge_tree"]


def test_profile_scopes_dispatch_status_single_assignment() -> None:
    implementation = profile()["implementation"]
    for key in (
        "scope_is_only_native_dispatch_status_single_assignment",
        "dispatch_status_initialized_exactly_once",
        "dispatch_status_is_const",
        "dispatch_status_uses_explicit_return_type_iife",
        "dispatch_status_iife_immediately_invoked",
        "uninitialized_dispatch_status_removed",
        "dispatch_status_branch_assignments_removed",
        "force_branch_returns_force_provider_status",
        "energy_branch_returns_energy_provider_status",
        "force_descriptor_branch_localization_preserved",
        "provider_error_descriptor_remains_common_to_both_dispatch_branches",
        "post_dispatch_validation_and_commit_preserved",
    ):
        assert implementation[key] is True
    assert "scope_is_only_native_force_descriptor_branch_localization" not in implementation


def test_exact_single_assignment_transform_evidence() -> None:
    validation = profile()["validation"]
    expected = {
        "exact_delta_path_count": 10,
        "implementation_delta_path_count": 2,
        "successor_evidence_path_count": 6,
        "predecessor_freeze_wiring_path_count": 2,
        "source_manifest_entry_count_exact": 405,
        "pull_request_trigger_path_count_exact": 222,
        "push_trigger_path_count_exact": 222,
        "dispatch_status_const_declaration_count_exact": 1,
        "dispatch_status_uninitialized_declaration_count_exact": 0,
        "dispatch_status_branch_assignment_count_exact": 0,
        "dispatch_status_iife_count_exact": 1,
        "dispatch_status_iife_explicit_return_type_count_exact": 1,
        "dispatch_status_provider_return_count_exact": 2,
        "force_branch_provider_return_count_exact": 1,
        "energy_branch_provider_return_count_exact": 1,
    }
    for key, value in expected.items():
        assert validation[key] == value
    for key in (
        "predecessor_adapter_exact_dispatch_status_single_assignment_transform",
        "provider_error_common_scope_exact_predecessor_bytes",
        "force_descriptor_branch_localization_preserved_by_exact_dispatch_transform",
        "post_dispatch_validation_and_commit_exact_predecessor_bytes",
        "canonical_vendor_adapter_byte_identical",
        "native_adapter_test_exact_predecessor_bytes",
    ):
        assert validation[key] is True
    for stale_key in (
        "predecessor_adapter_exact_force_descriptor_branch_localization_transform",
        "relocated_force_descriptor_preparation_exact_predecessor_bytes",
        "adapter_dispatch_exact_after_branch_local_preparation_normalization",
        "energy_branch_exact_predecessor_bytes",
    ):
        assert stale_key not in validation


def test_inherited_dispatch_rollback_and_lifecycle_contracts_remain_frozen() -> None:
    implementation = profile()["implementation"]
    for key in (
        "force_descriptor_declaration_is_branch_local",
        "force_symbol_binds_provider_forces_by_address_directly",
        "energy_branch_has_zero_force_descriptor_arguments",
        "two_symbol_dispatch_and_five_semantic_routes_preserved",
        "provider_validation_finiteness_rollback_and_commit_preserved",
        "native_adapter_test_exact_predecessor_bytes",
        "reusable_evaluation_force_storage_rollback_guard_preserved",
        "stateless_failure_preserves_evaluation_energy_bits",
        "stateless_failure_preserves_evaluation_force_address_capacity_size_and_bits",
        "external_evaluation_is_success_only",
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
        "single_assignment_performance_improvement_claimed",
        "iife_performance_improvement_claimed",
        "const_status_performance_improvement_claimed",
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


def test_exact_pr478_predecessor_and_evidence_graph() -> None:
    data = profile()
    assert data["target_predecessor"] == verifier.PREDECESSOR
    assert verifier.PREDECESSOR["pull_request"] == 478
    assert verifier.PREDECESSOR["source_manifest_entry_count"] == 399
    validation = data["validation"]
    assert validation["predecessor_workflow_detaches_exact_merge_object"] is True
    assert validation["predecessor_unit_skips_only_when_successor_profile_exists"] is True
    manifest = json.loads((ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes())
    assert len(manifest["files"]) == 405
    assert manifest["evidence_paths"] == sorted(
        path.as_posix() for path in verifier.EVIDENCE_PATHS
    )
