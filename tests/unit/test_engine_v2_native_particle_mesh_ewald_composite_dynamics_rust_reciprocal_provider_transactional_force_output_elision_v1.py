import json
from pathlib import Path

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_transactional_force_output_elision_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 333
    assert result["delta_path_count"] == 12
    assert result["trigger_path_count"] == 150


def test_profile_scopes_elision_and_preserves_raw_rust_semantics() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    for key in (
        "native_nonreuse_forceful_rust_adapter_uses_existing_direct_output_entry",
        "native_nonreuse_forceful_adapter_provider_internal_transactional_force_vec_allocation_elided",
        "elision_scope_is_only_nonreuse_forceful_native_cpp_adapter",
        "energy_only_uses_public_transactional_entry_with_forces_disabled",
        "reusable_forceful_workspace_route_preserved",
        "provider_force_source_triple_scratch_route_preserved",
        "cpp_lane_provider_independence_preserved",
        "call_local_cpp_force_soa_preserved",
        "late_direct_force_writes_are_disposable_before_adapter_commit",
        "evaluation_commit_occurs_after_status_error_and_finite_checks",
        "evaluation_pointer_capacity_size_and_bits_preserved_on_late_error",
        "raw_rust_transactional_entry_preserved",
        "raw_rust_transactional_force_vec_preserved",
        "raw_rust_transactional_success_only_commit_preserved",
    ):
        assert implementation[key] is True
    assert implementation["rust_kernel_source_changed"] is False
    assert implementation["rust_kernel_sha256"] == verifier.UNCHANGED_RUST_KERNEL_SHA256


def test_profile_forbids_broader_allocation_and_scientific_claims() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    for key in (
        "raw_direct_force_channels_transactional_claimed",
        "public_raw_transactional_vec_removed_claimed",
        "provider_wide_transactional_force_allocation_elided_claimed",
        "all_force_allocations_elided_claimed",
        "cpp_call_local_soa_allocations_elided_claimed",
        "final_candidate_aos_allocation_elided_claimed",
        "soa_to_aos_copy_elided_claimed",
        "allocation_free_claimed",
        "provider_allocation_free_claimed",
        "steady_state_allocation_free_claimed",
        "allocation_failure_timing_invariance_claimed",
        "allocation_error_detail_invariance_claimed",
        "performance_claimed",
        "peak_memory_reduction_claimed",
        "acceleration_claimed",
        "scientific_claimed",
        "scientific_equivalence_claimed",
        "cross_lane_bit_parity_claimed",
        "product_claimed",
        "operational_readiness_claimed",
    ):
        assert implementation[key] is False


def test_fake_provider_scope_is_explicitly_non_authoritative() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    assert implementation["fake_provider_is_dispatch_and_commit_separation_test_double"] is True
    assert (
        implementation[
            "changed_adapter_contract_asan_ubsan_evidence_limited_to_fake_provider"
        ]
        is True
    )
    for key in (
        "fake_provider_production_authority",
        "fake_provider_scientific_authority",
        "fake_provider_executes_real_rust_allocator",
        "fake_provider_executes_real_public_c_api",
        "fake_provider_executes_real_rust_panic_boundary",
        "fake_provider_proves_real_rust_scientific_transactionality",
        "real_rust_provider_sanitizer_execution_claimed",
        "macos_execution_claimed",
        "msvc_execution_claimed",
    ):
        assert implementation[key] is False


def test_exact_evidence_graph_and_manifest_derivation() -> None:
    assert len(verifier.EXPECTED_DELTA_PATHS) == 12
    assert set(verifier.IMPLEMENTATION_DELTA_PATHS) <= set(
        verifier.EXPECTED_DELTA_PATHS
    )
    assert len(verifier.EVIDENCE_PATHS) == 6
    manifest = json.loads(
        (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    )
    rows = manifest["files"]
    paths = [row["path"] for row in rows]
    assert len(rows) == 333
    assert paths == sorted(set(paths))
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in paths
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in paths
    assert verifier.PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix() in paths
    assert verifier.PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix() in paths
    assert verifier.NATIVE_TEST_RELATIVE_PATH.as_posix() in paths


def test_workflow_and_predecessor_freeze_wiring() -> None:
    verifier.require_workflow_contract(ROOT)
    verifier.require_predecessor_unit_freeze(ROOT)
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    pull_paths = verifier.workflow_trigger_paths(workflow, "pull_request", "push")
    push_paths = verifier.workflow_trigger_paths(workflow, "push", "workflow_dispatch")
    assert pull_paths == push_paths
    assert len(pull_paths) == len(set(pull_paths)) == 150


def test_adapter_rust_fake_abi_and_docs_contracts() -> None:
    verifier.require_exact_source_hashes(ROOT)
    verifier.require_adapter_contract(ROOT)
    verifier.require_unchanged_rust_contract(ROOT)
    verifier.require_native_test_and_cmake_contract(ROOT)
    verifier.require_abi_and_authority_contract(ROOT)
    verifier.require_docs_contract(ROOT)


def test_authority_and_operational_blockers_remain_closed() -> None:
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    assert profile["authority"] == verifier.AUTHORITY
    assert set(profile["authority"].values()) == {False}
    assert profile["operational_boundary"] == {
        "blockers": verifier.BLOCKERS,
        "unresolved_operational_decisions": 32,
    }
