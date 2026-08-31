import json
from pathlib import Path

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_zero_step_particle_assignment_scratch_reuse_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_OWNER_REUSABLE_FORCEFUL_ALL_SCRATCH_REUSE_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_reusable_forceful_all_scratch_reuse_"
    "profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_OWNER_REUSABLE_FORCEFUL_ALL_SCRATCH_REUSE_EVIDENCE_PRESENT,
    reason=(
        "owner zero-step particle-assignment scratch reuse evidence is verified "
        "from its exact frozen PR 470 object after reusable forceful all-scratch "
        "reuse evidence is present"
    ),
)


def profile() -> dict:
    return json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 351
    assert result["delta_path_count"] == 15
    assert result["trigger_path_count"] == 168


def test_profile_scopes_owner_zero_step_particle_assignment_reuse() -> None:
    value = profile()
    implementation = value["implementation"]
    for key in (
        "stateful_rust_force_free_owner_reciprocal_workspace_reused",
        "stateful_rust_force_free_owner_neutrality_sort_scratch_reused",
        "stateful_rust_force_free_owner_particle_assignment_scratch_reused",
        "all_three_scratch_hidden_energy_entry_added",
        "predecessor_workspace_only_hidden_energy_entry_preserved",
        "predecessor_workspace_and_neutrality_hidden_energy_entry_preserved",
        "all_three_scratch_mode_uses_force_storage_disabled",
        "three_descriptors_and_full_capacities_alias_preflight_before_lease",
        "warm_capacity_sufficient_neutrality_reserve_elided",
        "warm_capacity_sufficient_particle_assignment_reserve_elided",
        "particle_assignment_growth_oom_preserves_ready_raw_parts_and_payload",
        "reusable_forceful_workspace_route_preserved",
        "nonreuse_forceful_direct_route_preserved",
        "stateless_force_free_transactional_route_preserved",
        "stateful_forceful_triple_scratch_route_preserved",
        "energy_output_committed_only_on_success",
        "owner_force_channels_untouched_by_force_free_entry",
    ):
        assert implementation[key] is True
    assert implementation["call_local_particle_assignment_allocation_preserved"] is False
    validation = value["validation"]
    assert validation["canonical_vendor_composite_exact_predecessor_bytes"] is True
    assert validation["canonical_vendor_adapter_byte_identical"] is True
    assert validation["canonical_vendor_provider_header_byte_identical"] is True
    assert value["abi"]["private_hidden_symbol_absent_from_public_surfaces"] is True
    assert value["abi"]["private_hidden_symbol_present_in_linux_linked_image"] is True
    assert value["abi"]["private_hidden_symbol_absent_from_linux_dynamic_exports"] is True
    assert value["abi"]["new_private_hidden_symbol"] == verifier.PRIVATE_SYMBOL


def test_profile_preserves_scientific_and_operational_boundaries() -> None:
    implementation = profile()["implementation"]
    for key in (
        "allocation_free_claimed",
        "provider_allocation_free_claimed",
        "steady_state_allocation_free_claimed",
        "local_particle_assignment_allocation_elided_claimed",
        "workspace_payload_transactionality_claimed",
        "neutrality_sort_payload_transactionality_claimed",
        "particle_assignment_payload_transactionality_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "scientific_claimed",
        "scientific_equivalence_claimed",
        "cross_lane_bit_parity_claimed",
        "product_claimed",
        "operational_readiness_claimed",
    ):
        assert implementation[key] is False


def test_fake_provider_is_only_dispatch_and_commit_evidence() -> None:
    implementation = profile()["implementation"]
    assert implementation["fake_provider_is_dispatch_and_commit_separation_test_double"] is True
    assert implementation["fake_provider_production_authority"] is False
    assert implementation["fake_provider_scientific_authority"] is False
    assert implementation["fake_provider_executes_real_rust_allocator"] is False


def test_predecessor_and_public_contracts_are_frozen() -> None:
    value = profile()
    assert value["target_predecessor"]["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert value["target_predecessor"]["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    assert value["abi"]["public_symbols"] == list(verifier.PUBLIC_SYMBOLS)
    assert value["validation"]["source_manifest_entry_count_exact"] == 351
