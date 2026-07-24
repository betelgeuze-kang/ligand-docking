from __future__ import annotations

from copy import deepcopy

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_trajectory_comparison import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_process_launch_identity import (
    FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
    FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_authenticated_head_receipt import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_later_head_consistency import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_witness_quorum_non_equivocation import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_epoch_transition_continuity import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_runtime_integrity_contract import (
    FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V16,
    FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V15,
    FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V14,
    FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V13,
    FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V12,
    FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V10,
    FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_MINIMIZATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION,
    ValidationRuntimeIntegrityContractError,
    require_validation_runtime_integrity_contract_document,
    validation_runtime_integrity_contract_document,
    validation_runtime_integrity_decision,
)


def test_runtime_integrity_companion_is_frozen_truthful_and_closed() -> None:
    first = validation_runtime_integrity_contract_document()
    second = validation_runtime_integrity_contract_document()
    decision = validation_runtime_integrity_decision()

    assert first == second
    assert first["contract_sha256"] == (
        FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256
    )
    assert (
        first["contract_version"]
        == VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION
        == "17.0.0"
    )
    assert first["superseded_contract_sha256"] == (
        FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V16
    )
    assert (
        FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V16
        == "3e955b12a5bcf6e4b090deab33fe4d71e6cf989fd63bd2cb7082ccc146494917"
    )
    assert (
        FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V15
        == "af20bc7b1036c7264c37ad7487e1d7832f52259415d07b8bc8963f04c8d83ebd"
    )
    assert (
        FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V14
        == "191560bd10344eddde753028033585821da1ca6cb259f30df1cf86c5feed35b2"
    )
    assert (
        FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V13
        == "1121a8a8a68fd8d2b41618404a8bff389307dc55de754a6400f00567f83c94d6"
    )
    assert (
        FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V12
        == "8e260d43a7cb6d6da93e519075a22f14f6a21bd06d069d428ad327b210065dba"
    )
    assert (
        FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V10
        == "6a260a1b4572c6331e19f8ed8bad8c942d04abe6b485b69738ebb69154ab2ef6"
    )
    assert (
        first["bound_contracts"]["minimization_trajectory_comparison_contract_sha256"]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_MINIMIZATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
        == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
    )
    assert (
        decision["bound_minimization_trajectory_comparison_contract_sha256"]
        == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
    )
    assert (
        first["implemented_enforcement"][
            "minimization_full_trajectory_comparison_contract_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "minimization_checkpoint_restart_digest_comparison_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "minimization_production_trajectory_comparison_receipt_present"
        ]
        is False
    )
    assert (
        first["bound_contracts"]["production_evidence_custody_contract_sha256"]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
    )
    assert (
        decision["bound_production_evidence_custody_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"][
            "production_review_authorization_custody_extension_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert (
        decision["bound_review_authorization_custody_extension_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"][
            "production_reservation_custody_extension_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert (
        decision["bound_reservation_custody_extension_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"][
            "production_reservation_registry_proof_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
    )
    assert (
        decision["bound_reservation_registry_proof_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"][
            "production_reservation_authenticated_head_receipt_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
    )
    assert (
        decision["bound_reservation_authenticated_head_receipt_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"][
            "production_reservation_later_head_consistency_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
    )
    assert (
        decision["bound_reservation_later_head_consistency_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"][
            "production_reservation_witness_quorum_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
    )
    assert (
        decision["bound_reservation_witness_quorum_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"][
            "production_reservation_epoch_transition_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
    )
    assert (
        decision["bound_reservation_epoch_transition_contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
    )
    assert (
        first["bound_contracts"]["process_launch_identity_contract_sha256"]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
        == FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
    )
    assert (
        decision["bound_process_launch_identity_contract_sha256"]
        == FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
    )
    assert (
        first["implemented_enforcement"][
            "canonical_per_file_dependency_manifest_generated"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "persisted_and_live_dependency_manifest_exact_equality_required"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "canonical_per_file_source_git_tree_manifest_generated"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "persisted_and_live_source_manifest_exact_equality_required"
        ]
        is True
    )
    assert (
        first["bounded_preflight"][
            "bounded_streaming_directory_enumeration_established"
        ]
        is True
    )
    assert (
        first["bounded_preflight"][
            "bounded_streaming_distribution_record_ingest_established"
        ]
        is True
    )
    assert (
        first["bounded_preflight"]["bounded_worker_stdout_streaming_established"]
        is True
    )
    assert (
        first["signed_carrier_compatibility"][
            "legacy_frozen_contract_projection_rewritten_without_version_bump"
        ]
        is False
    )
    assert (
        first["signed_carrier_compatibility"][
            "current_contracts_use_new_versioned_identities"
        ]
        is True
    )
    assert (
        first["signed_carrier_compatibility"][
            "legacy_contract_document_verification_preserved"
        ]
        is True
    )
    assert (
        first["signed_carrier_compatibility"][
            "legacy_signed_artifact_verification_preserved"
        ]
        is False
    )
    assert (
        first["implemented_enforcement"][
            "energy_force_ed25519_post_result_review_contract_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "energy_force_result_review_recomputes_metrics_from_retained_raw_evidence"
        ]
        is True
    )
    assert (
        first["signed_carrier_compatibility"][
            "energy_force_upstream_review_and_authorization_use_symmetric_hmac"
        ]
        is False
    )
    assert (
        first["signed_carrier_compatibility"][
            "energy_force_upstream_asymmetric_chain_established"
        ]
        is True
    )
    assert (
        first["signed_carrier_compatibility"][
            "energy_force_upstream_public_key_verification_only"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "production_reservation_custody_extension_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "reservation_intent_and_commit_attestation_primitives_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "external_same_epoch_registry_transaction_proof_verifier_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "sparse_merkle_three_slot_transition_verification_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"]["caller_expected_exact_registry_head_required"]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "authenticated_external_head_status_receipt_verifier_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "exact_registry_head_status_tail_and_challenge_binding_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "post_receipt_current_status_descendant_reverification_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "receipt_reverification_inputs_snapshotted_before_use"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "same_epoch_later_head_consistency_proof_verifier_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "adjacent_registry_checkpoint_lineage_verification_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "original_consumed_slot_retention_verification_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "post_consistency_current_status_descendant_reverification_implemented"
        ]
        is True
    )
    assert (
        first["implemented_enforcement"][
            "one_fork_consistency_does_not_prove_global_non_equivocation"
        ]
        is True
    )
    for field_name in (
        "fixed_policy_same_epoch_anchor_scoped_witness_quorum_verifier_implemented",
        "quorum_intersection_above_declared_fault_bound_verification_implemented",
        "exclusive_vote_statement_signature_verification_implemented",
        "fixed_policy_full_roster_validity_and_denial_verification_implemented",
        "anchor_scoped_quorum_certificate_does_not_prove_registry_non_equivocation",
        "adjacent_registry_epoch_transition_continuity_verifier_implemented",
        "previous_terminal_state_root_to_next_genesis_carry_forward_verification_implemented",
        "derived_next_genesis_checkpoint_verification_implemented",
        "joint_previous_and_next_epoch_transition_quorum_verification_implemented",
        "transition_successor_uniqueness_without_external_locking_not_claimed",
    ):
        assert first["implemented_enforcement"][field_name] is True
        assert decision[field_name] is True
    for field_name in (
        "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified",
        "declared_fault_bound_observed_in_operation",
        "cross_anchor_non_equivocation_verified",
        "exclusive_vote_enforcement_verified",
        "independent_witness_journal_consistency_verified",
        "witness_locking_enforced",
    ):
        assert first["implemented_enforcement"][field_name] is False
        assert decision[field_name] is False
    assert (
        first["implemented_enforcement"][
            "authenticated_out_of_band_registry_head_receipt_verified"
        ]
        is False
    )
    assert (
        first["implemented_enforcement"]["caller_challenge_freshness_verified"] is False
    )
    assert (
        first["implemented_enforcement"]["caller_challenge_one_use_verified"] is False
    )
    assert (
        first["implemented_enforcement"]["global_latest_registry_head_verified"]
        is False
    )
    assert (
        first["implemented_enforcement"]["global_latest_status_head_verified"] is False
    )
    assert first["implemented_enforcement"]["later_head_consistency_verified"] is False
    assert "legacy_frozen_contract_version_migration_missing" not in first["blockers"]
    assert "durable_source_per_file_manifest_missing" not in first["blockers"]
    assert "bounded_streaming_preflight_traversal_missing" not in first["blockers"]
    assert "mapped_native_dso_snapshot_missing" not in first["blockers"]
    assert "worker_pre_post_runtime_evidence_missing" not in first["blockers"]
    assert "energy_force_ed25519_chain_missing" not in first["blockers"]
    assert "energy_force_independent_result_review_missing" in first["blockers"]
    assert "energy_force_upstream_symmetric_hmac_chain" not in first["blockers"]
    assert "external_worker_launch_authenticity_or_custody_missing" in first["blockers"]
    assert "same_tick_pid_reuse_collision_not_excluded" in first["blockers"]
    assert "final_production_carrier_family_not_implemented" in first["blockers"]
    assert "production_permit_one_use_consumption_not_enforced" in first["blockers"]
    assert (
        "custody_stages_after_status_snapshot_not_implemented" not in first["blockers"]
    )
    assert (
        "reservation_and_later_custody_stages_not_implemented" not in first["blockers"]
    )
    assert "environment_and_later_custody_stages_not_implemented" in first["blockers"]
    assert (
        "external_serializable_reservation_registry_not_provisioned"
        in first["blockers"]
    )
    assert "external_registry_transaction_proof_not_provisioned" in first["blockers"]
    assert "external_registry_backend_key_not_provisioned" in first["blockers"]
    assert "external_registry_head_observer_key_not_provisioned" in first["blockers"]
    assert "out_of_band_current_registry_head_not_provisioned" in first["blockers"]
    assert (
        "authenticated_external_head_status_receipt_not_provisioned"
        in first["blockers"]
    )
    assert (
        "trusted_external_head_receipt_authority_key_not_provisioned"
        in first["blockers"]
    )
    assert "post_receipt_current_status_descendant_not_provisioned" in first["blockers"]
    assert (
        "caller_challenge_freshness_and_one_use_not_independently_verified"
        in first["blockers"]
    )
    assert "global_latest_registry_head_not_independently_verified" in first["blockers"]
    assert "global_latest_status_head_not_independently_verified" in first["blockers"]
    assert "later_head_consistency_proof_not_provisioned" in first["blockers"]
    assert (
        "post_consistency_current_status_descendant_not_provisioned"
        in first["blockers"]
    )
    for blocker in (
        "fixed_policy_witness_quorum_proof_not_provisioned",
        "fixed_policy_witness_keys_not_provisioned",
        "fixed_policy_witness_quorum_policy_not_provisioned",
        "post_quorum_current_status_descendant_not_provisioned",
        "independent_witness_journal_consistency_not_established",
        "witness_locking_enforcement_not_established",
        "realm_wide_external_registry_non_equivocation_not_established",
        "external_adjacent_epoch_transition_proof_not_provisioned",
    ):
        assert blocker in first["blockers"]
    assert "status_head_compare_and_set_not_independently_verified" in first["blockers"]
    assert "production_reservation_intent_not_provisioned" in first["blockers"]
    assert "production_atomic_reservation_commit_not_provisioned" in first["blockers"]
    assert (
        "production_review_authorization_carriers_not_provisioned" in first["blockers"]
    )
    assert (
        "production_review_authorization_custody_events_not_provisioned"
        in first["blockers"]
    )
    assert "external_custody_successor_uniqueness_not_provisioned" in first["blockers"]
    assert "external_runtime_integrity_manifest_store_missing" in first["blockers"]
    assert (
        "independent_result_review_dependency_manifest_reverification_missing"
        in first["blockers"]
    )
    assert "external_signed_native_dso_allowlist_missing" in first["blockers"]
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "resident_native_mapping_snapshot_implemented"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "fixed_proc_path_and_calling_pid_maps_view_bound"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"]["procfs_superblock_magic_verified"]
        is False
    )
    assert (
        first["native_runtime_and_worker_lifecycle"]["kernel_vdso_content_digest_bound"]
        is False
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "anonymous_deleted_memfd_or_writable_executable_mapping_gate"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"]["worker_pre_state_persisted"]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"]["worker_post_state_persisted"]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "worker_payload_aggregate_bound_to_post_state"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "worker_snapshot_process_id_bound_to_supervisor_child"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "worker_stdout_hard_byte_bound_before_buffering"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "worker_request_bound_to_persisted_observation_identity"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "successful_raw_stdout_equals_canonical_reconstruction"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "supervisor_child_process_starttime_and_boot_id_bound"
        ]
        is False
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "linux_process_pid_parent_starttime_boot_and_namespace_measurement_implemented"
        ]
        is True
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "same_tick_pid_reuse_collision_excluded"
        ]
        is False
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "pre_post_equality_is_native_lifetime_closure"
        ]
        is False
    )
    assert (
        first["native_runtime_and_worker_lifecycle"][
            "native_lifetime_closure_guard_implemented"
        ]
        is False
    )
    assert first["external_custody"]["independent_cpu_hosts_provisioned"] == 0
    assert (
        first["external_custody"][
            "exact_raw_byte_dual_signed_four_event_custody_primitive_implemented"
        ]
        is True
    )
    assert first["external_custody"]["verified_custody_stage_sequence"] == [
        "production_permit",
        "status_snapshot",
        "pre_execution_review",
        "authorization",
        "atomic_reservation_commit_attestation",
    ]
    assert first["external_custody"]["maximum_verified_custody_sequence"] == 5
    assert first["external_custody"]["production_permit_one_use_enforced"] is False
    assert (
        first["external_custody"][
            "external_same_epoch_registry_transaction_proof_verifier_implemented"
        ]
        is True
    )
    assert (
        first["external_custody"][
            "sparse_merkle_permit_nonce_predecessor_transition_verification_implemented"
        ]
        is True
    )
    assert (
        first["external_custody"][
            "caller_expected_exact_current_registry_head_required"
        ]
        is True
    )
    assert (
        first["external_custody"][
            "authenticated_external_head_status_receipt_verifier_implemented"
        ]
        is True
    )
    assert (
        first["external_custody"][
            "exact_registry_head_status_tail_and_challenge_binding_implemented"
        ]
        is True
    )
    assert (
        first["external_custody"][
            "post_receipt_current_status_descendant_reverification_implemented"
        ]
        is True
    )
    assert (
        first["external_custody"][
            "authenticated_out_of_band_current_registry_head_receipt_verified"
        ]
        is False
    )
    assert (
        first["external_custody"][
            "authenticated_external_head_status_receipt_provisioned"
        ]
        is False
    )
    assert (
        first["external_custody"]["post_receipt_current_status_descendant_provisioned"]
        is False
    )
    assert first["external_custody"]["caller_challenge_freshness_verified"] is False
    assert first["external_custody"]["caller_challenge_one_use_verified"] is False
    assert first["external_custody"]["global_latest_registry_head_verified"] is False
    assert first["external_custody"]["global_latest_status_head_verified"] is False
    assert first["external_custody"]["later_head_consistency_verified"] is False
    assert (
        first["external_custody"][
            "same_epoch_later_head_consistency_proof_verifier_implemented"
        ]
        is True
    )
    assert (
        first["external_custody"]["later_head_consistency_proof_provisioned"] is False
    )
    assert (
        first["external_custody"][
            "post_consistency_current_status_descendant_provisioned"
        ]
        is False
    )
    for field_name in (
        "fixed_policy_same_epoch_anchor_scoped_witness_quorum_verifier_implemented",
        "quorum_intersection_above_declared_fault_bound_verification_implemented",
        "exclusive_vote_statement_signature_verification_implemented",
        "fixed_policy_full_roster_validity_and_denial_verification_implemented",
        "adjacent_registry_epoch_transition_continuity_verifier_implemented",
        "previous_terminal_state_root_to_next_genesis_carry_forward_verification_implemented",
        "derived_next_genesis_checkpoint_verification_implemented",
        "joint_previous_and_next_epoch_transition_quorum_verification_implemented",
        "transition_successor_uniqueness_without_external_locking_not_claimed",
    ):
        assert first["external_custody"][field_name] is True
    for field_name in (
        "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified",
        "declared_fault_bound_observed_in_operation",
        "cross_anchor_non_equivocation_verified",
        "exclusive_vote_enforcement_verified",
        "independent_witness_journal_consistency_verified",
        "witness_locking_enforced",
        "fixed_policy_witness_quorum_proof_provisioned",
        "fixed_policy_witness_keys_provisioned",
        "fixed_policy_witness_quorum_policy_provisioned",
        "post_quorum_current_status_descendant_provisioned",
        "adjacent_epoch_transition_proof_provisioned",
        "previous_epoch_transition_votes_provisioned",
        "next_epoch_transition_votes_provisioned",
        "next_epoch_transition_policy_provisioned",
        "post_transition_current_status_descendant_provisioned",
    ):
        assert first["external_custody"][field_name] is False
    assert (
        first["external_custody"]["external_registry_transaction_proof_provisioned"]
        is False
    )
    assert (
        first["external_custody"]["out_of_band_current_registry_head_provisioned"]
        is False
    )
    assert (
        first["external_custody"]["custody_stages_after_status_snapshot_implemented"]
        is True
    )
    assert (
        first["external_custody"]["custody_stages_after_authorization_implemented"]
        is True
    )
    assert (
        first["external_custody"]["custody_stages_after_reservation_commit_implemented"]
        is False
    )
    for field in (
        "external_serializable_registry_commit_verified",
        "status_head_compare_and_set_committed",
        "permit_one_use_slot_consumed",
        "authorization_nonce_slot_consumed",
        "predecessor_successor_slot_consumed",
        "custody_successor_uniqueness_enforced",
        "external_registry_non_equivocation_verified",
        "registry_epoch_transition_continuity_verified",
    ):
        assert first["external_custody"][field] is False
    assert first["external_custody"]["custody_successor_uniqueness_enforced"] is False
    assert first["signed_carrier_compatibility"]["planned_only_custody_stages"] == [
        "environment",
        "runner_start",
        "worker_transcript",
        "observation",
        "result",
        "result_review",
        "response",
    ]
    assert first["external_custody"]["production_custody_chain_provisioned"] is False
    assert all(value is False for value in first["claim_policy"].values())
    assert decision["durable_dependency_per_file_manifest_implemented"] is True
    assert decision["durable_source_git_tree_manifest_implemented"] is True
    assert decision["bounded_streaming_preflight_traversal_implemented"] is True
    assert decision["resident_native_mapping_snapshot_implemented"] is True
    assert decision["worker_post_state_implemented"] is True
    assert decision["worker_payload_completion_binding_implemented"] is True
    assert decision["bounded_worker_stdout_streaming_implemented"] is True
    assert decision["worker_snapshot_process_id_binding_implemented"] is True
    assert decision["durable_worker_request_observation_binding_implemented"] is True
    assert decision["successful_worker_transcript_reconstruction_implemented"] is True
    assert (
        decision["energy_force_ed25519_post_result_review_contract_implemented"] is True
    )
    assert (
        decision[
            "energy_force_result_review_recomputes_metrics_from_retained_raw_evidence"
        ]
        is True
    )
    assert decision["energy_force_upstream_asymmetric_chain_established"] is True
    assert decision["linux_process_launch_identity_primitive_implemented"] is True
    assert decision["same_tick_pid_reuse_collision_excluded"] is False
    assert (
        decision[
            "claim_closed_production_evidence_four_event_custody_foundation_implemented"
        ]
        is True
    )
    assert decision["production_review_authorization_carriers_implemented"] is True
    assert (
        decision["production_review_authorization_custody_extension_implemented"]
        is True
    )
    assert (
        decision["frozen_ancestor_exact_json_scalar_type_preflight_implemented"] is True
    )
    assert decision["base_status_lineage_not_before_permit_enforced"] is True
    assert (
        decision[
            "process_launch_identity_digest_bound_by_review_authorization_carriers"
        ]
        is True
    )
    assert decision["process_launch_identity_authenticity_established"] is False
    assert decision["production_permit_one_use_enforced"] is False
    assert decision["production_reservation_custody_extension_implemented"] is True
    assert (
        decision["reservation_intent_and_commit_attestation_primitives_implemented"]
        is True
    )
    assert (
        decision["external_same_epoch_registry_transaction_proof_verifier_implemented"]
        is True
    )
    assert (
        decision["sparse_merkle_three_slot_transition_verification_implemented"] is True
    )
    assert decision["caller_expected_exact_registry_head_required"] is True
    assert (
        decision["authenticated_external_head_status_receipt_verifier_implemented"]
        is True
    )
    assert (
        decision["exact_registry_head_status_tail_and_challenge_binding_implemented"]
        is True
    )
    assert (
        decision["post_receipt_current_status_descendant_reverification_implemented"]
        is True
    )
    assert decision["receipt_reverification_inputs_snapshotted_before_use"] is True
    assert (
        decision["same_epoch_later_head_consistency_proof_verifier_implemented"] is True
    )
    assert (
        decision["adjacent_registry_checkpoint_lineage_verification_implemented"]
        is True
    )
    assert decision["original_consumed_slot_retention_verification_implemented"] is True
    assert (
        decision[
            "post_consistency_current_status_descendant_reverification_implemented"
        ]
        is True
    )
    assert (
        decision["one_fork_consistency_does_not_prove_global_non_equivocation"] is True
    )
    assert decision["authenticated_out_of_band_registry_head_receipt_verified"] is False
    assert decision["authenticated_external_head_status_receipt_provisioned"] is False
    assert decision["post_receipt_current_status_descendant_provisioned"] is False
    assert decision["later_head_consistency_proof_provisioned"] is False
    assert decision["post_consistency_current_status_descendant_provisioned"] is False
    assert decision["caller_challenge_freshness_verified"] is False
    assert decision["caller_challenge_one_use_verified"] is False
    assert decision["global_latest_registry_head_verified"] is False
    assert decision["global_latest_status_head_verified"] is False
    assert decision["later_head_consistency_verified"] is False
    assert decision["maximum_verified_custody_sequence"] == 5
    assert decision["custody_stages_after_status_snapshot_implemented"] is True
    assert decision["custody_stages_after_authorization_implemented"] is True
    assert decision["custody_stages_after_reservation_commit_implemented"] is False
    for field in (
        "external_serializable_registry_commit_verified",
        "status_head_compare_and_set_committed",
        "permit_one_use_slot_consumed",
        "authorization_nonce_slot_consumed",
        "predecessor_successor_slot_consumed",
        "custody_successor_uniqueness_enforced",
        "external_registry_non_equivocation_verified",
        "registry_epoch_transition_continuity_verified",
    ):
        assert decision[field] is False
    assert decision["final_production_carrier_family_implemented"] is False
    assert decision["production_custody_chain_provisioned"] is False
    assert decision["external_worker_launch_authenticity_implemented"] is False
    assert decision["native_lifetime_closure_implemented"] is False
    assert decision["production_validation_results_collected"] is False
    assert require_validation_runtime_integrity_contract_document(first) == first


def test_runtime_integrity_companion_rejects_self_consistent_claim_tamper() -> None:
    tampered = deepcopy(validation_runtime_integrity_contract_document())
    tampered["claim_policy"]["production_validation_results_collected"] = True

    with pytest.raises(
        ValidationRuntimeIntegrityContractError,
        match="does not match the frozen record",
    ):
        require_validation_runtime_integrity_contract_document(tampered)

    type_alias = deepcopy(validation_runtime_integrity_contract_document())
    type_alias["external_custody"][
        "review_authorization_custody_extension_implemented"
    ] = 1
    with pytest.raises(
        ValidationRuntimeIntegrityContractError,
        match="does not match the frozen record",
    ):
        require_validation_runtime_integrity_contract_document(type_alias)
