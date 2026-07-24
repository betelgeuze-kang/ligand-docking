"""Companion contract for production-class validation runtime integrity.

The active energy-force and minimization chains use new versioned contract
identities.  Superseded contract documents remain exactly verifiable by their
frozen hashes; superseded signed artifacts and receipts are not supported.
This companion records the stronger enforcement now implemented and keeps
production collection closed until native lifetime closure, externally
authenticated worker launch/custody, and production infrastructure exist.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

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

VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_runtime_integrity_contract/17.0.0"
)
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_ID = (
    "engine_v2_synthetic_validation_runtime_integrity/17.0.0"
)
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION = "17.0.0"
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_FROZEN_AT_UTC = "2026-07-24T19:15:00Z"
VALIDATION_RUNTIME_INTEGRITY_BOUND_MINIMIZATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256 = FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256 = (
    FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
)
VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256 = FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256 = (
    FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
)
VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256 = (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
)
VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256 = (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
)
VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256 = FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256 = FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256 = (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
)
VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256 = (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
)
FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256 = (
    "6b33d19a02c8e8d5a4b45095d259f96a0cfea00dca93d8445bc2ae64baf6ed33"
)
FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V16 = (
    "3e955b12a5bcf6e4b090deab33fe4d71e6cf989fd63bd2cb7082ccc146494917"
)
FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V15 = (
    "af20bc7b1036c7264c37ad7487e1d7832f52259415d07b8bc8963f04c8d83ebd"
)
FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V14 = (
    "191560bd10344eddde753028033585821da1ca6cb259f30df1cf86c5feed35b2"
)
FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V13 = (
    "1121a8a8a68fd8d2b41618404a8bff389307dc55de754a6400f00567f83c94d6"
)
FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V12 = (
    "8e260d43a7cb6d6da93e519075a22f14f6a21bd06d069d428ad327b210065dba"
)
FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V11 = (
    "24a95d5c42efcd63235614f491d7c2dc818cd3d4f3a6a40317ec8ee6f2d6018d"
)
FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V10 = (
    "6a260a1b4572c6331e19f8ed8bad8c942d04abe6b485b69738ebb69154ab2ef6"
)

_BLOCKERS = (
    "external_root_owned_source_snapshot_not_provisioned",
    "source_snapshot_kernel_immutability_not_established",
    "prebootstrap_loaded_stdlib_origin_closure_missing",
    "external_signed_native_dso_allowlist_missing",
    "kernel_vdso_content_identity_missing",
    "procfs_superblock_identity_missing",
    "native_lifetime_closure_guard_missing",
    "worker_process_starttime_and_boot_id_binding_missing",
    "same_tick_pid_reuse_collision_not_excluded",
    "external_worker_launch_authenticity_or_custody_missing",
    "final_production_carrier_family_not_implemented",
    "production_evidence_permit_status_and_custody_not_provisioned",
    "production_review_authorization_carriers_not_provisioned",
    "production_review_authorization_custody_events_not_provisioned",
    "production_permit_one_use_consumption_not_enforced",
    "environment_and_later_custody_stages_not_implemented",
    "external_serializable_reservation_registry_not_provisioned",
    "external_registry_transaction_proof_not_provisioned",
    "external_registry_backend_key_not_provisioned",
    "external_registry_head_observer_key_not_provisioned",
    "out_of_band_current_registry_head_not_provisioned",
    "authenticated_external_head_status_receipt_not_provisioned",
    "trusted_external_head_receipt_authority_key_not_provisioned",
    "caller_head_receipt_challenge_not_provisioned",
    "post_receipt_current_status_descendant_not_provisioned",
    "post_consistency_current_status_descendant_not_provisioned",
    "caller_challenge_freshness_and_one_use_not_independently_verified",
    "global_latest_registry_head_not_independently_verified",
    "global_latest_status_head_not_independently_verified",
    "later_head_consistency_proof_not_provisioned",
    "fixed_policy_witness_quorum_proof_not_provisioned",
    "fixed_policy_witness_keys_not_provisioned",
    "fixed_policy_witness_quorum_policy_not_provisioned",
    "post_quorum_current_status_descendant_not_provisioned",
    "independent_witness_journal_consistency_not_established",
    "witness_locking_enforcement_not_established",
    "realm_wide_external_registry_non_equivocation_not_established",
    "status_head_compare_and_set_not_independently_verified",
    "production_reservation_intent_not_provisioned",
    "production_atomic_reservation_commit_not_provisioned",
    "external_registry_non_equivocation_proof_not_provisioned",
    "external_adjacent_epoch_transition_proof_not_provisioned",
    "external_custody_successor_uniqueness_not_provisioned",
    "external_runtime_integrity_manifest_store_missing",
    "energy_force_independent_result_review_missing",
    "independent_result_review_dependency_manifest_reverification_missing",
    "two_production_cpu_hosts_missing",
)


class ValidationRuntimeIntegrityContractError(ValueError):
    """The runtime-integrity companion contract is not the frozen record."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ValidationRuntimeIntegrityContractError(
            "runtime-integrity contract is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SCHEMA_ID,
        "contract_id": VALIDATION_RUNTIME_INTEGRITY_CONTRACT_ID,
        "contract_version": VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION,
        "frozen_at_utc": VALIDATION_RUNTIME_INTEGRITY_CONTRACT_FROZEN_AT_UTC,
        "superseded_contract_sha256": (
            FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V16
        ),
        "legacy_contract_chain_sha256s": [
            FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V15,
            FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V14,
            FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V13,
            FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V12,
            FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V11,
            FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V10,
        ],
        "refreeze_reason": (
            "bind_refrozen_production_review_authorization_and_reservation_"
            "custody_contracts_without_runtime_gate_change"
        ),
        "lanes": [
            "27-case-59-variant-energy-force",
            "14-case-minimization",
        ],
        "bound_contracts": {
            "minimization_trajectory_comparison_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_MINIMIZATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
            ),
            "production_evidence_custody_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
            ),
            "production_review_authorization_custody_extension_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
            ),
            "production_reservation_custody_extension_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
            ),
            "production_reservation_registry_proof_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
            ),
            "production_reservation_authenticated_head_receipt_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
            ),
            "production_reservation_later_head_consistency_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
            ),
            "production_reservation_witness_quorum_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
            ),
            "production_reservation_epoch_transition_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
            ),
            "process_launch_identity_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
            ),
        },
        "implemented_enforcement": {
            "bootstrap_requires_root_owned_read_only_source_snapshot": True,
            "entire_engine_package_tree_checked_before_package_import": True,
            "source_symlink_hardlink_and_bytecode_cache_rejected": True,
            "bootstrap_root_execution_rejected": True,
            "same_uid_source_tree_rewrite_or_replacement_rejected": False,
            "active_import_origin_bound_to_distribution_record": True,
            "record_payload_confined_to_install_scheme_roots": True,
            "external_record_paths_normalized_to_install_scheme": True,
            "record_owned_package_namespace_payload_rejected": True,
            "measured_source_dependency_and_stdlib_bytecode_cache_rejected": True,
            "one_monotonic_dependency_scan_deadline": True,
            "aggregate_dependency_file_and_byte_bounds": True,
            "canonical_per_file_dependency_manifest_generated": True,
            "dependency_manifest_persisted_once_per_nonce": True,
            "dependency_manifest_mode_0600_single_link_required": True,
            "persisted_and_live_dependency_manifest_exact_equality_required": True,
            "signed_commit_git_objects_independently_rehashed": True,
            "canonical_per_file_source_git_tree_manifest_generated": True,
            "source_manifest_persisted_once_per_nonce": True,
            "source_manifest_mode_0600_single_link_required": True,
            "persisted_and_live_source_manifest_exact_equality_required": True,
            "source_manifest_digest_bound_through_result_finalization": True,
            "minimization_result_review_binds_source_manifest_digest": True,
            "minimization_full_trajectory_comparison_contract_implemented": True,
            "minimization_checkpoint_restart_digest_comparison_implemented": True,
            "minimization_production_trajectory_comparison_receipt_present": False,
            "result_finalization_reuses_environment_manifest_reverification": True,
            "energy_force_ed25519_post_result_review_contract_implemented": True,
            "energy_force_result_review_recomputes_metrics_from_retained_raw_evidence": True,
            "linux_process_launch_identity_primitive_implemented": True,
            "claim_closed_production_permit_status_four_event_custody_primitives_implemented": True,
            "production_pre_execution_review_and_authorization_carriers_implemented": True,
            "production_review_authorization_custody_extension_implemented": True,
            "production_reservation_custody_extension_implemented": True,
            "reservation_intent_and_commit_attestation_primitives_implemented": True,
            "reservation_registry_and_witness_signature_verification_implemented": True,
            "external_same_epoch_registry_transaction_proof_verifier_implemented": True,
            "sparse_merkle_three_slot_transition_verification_implemented": True,
            "caller_expected_exact_registry_head_required": True,
            "authenticated_external_head_status_receipt_verifier_implemented": True,
            "exact_registry_head_status_tail_and_challenge_binding_implemented": True,
            "post_receipt_current_status_descendant_reverification_implemented": True,
            "receipt_reverification_inputs_snapshotted_before_use": True,
            "same_epoch_later_head_consistency_proof_verifier_implemented": True,
            "adjacent_registry_checkpoint_lineage_verification_implemented": True,
            "original_consumed_slot_retention_verification_implemented": True,
            "post_consistency_current_status_descendant_reverification_implemented": True,
            "one_fork_consistency_does_not_prove_global_non_equivocation": True,
            "fixed_policy_same_epoch_anchor_scoped_witness_quorum_verifier_implemented": True,
            "quorum_intersection_above_declared_fault_bound_verification_implemented": True,
            "exclusive_vote_statement_signature_verification_implemented": True,
            "fixed_policy_full_roster_validity_and_denial_verification_implemented": True,
            "anchor_scoped_quorum_certificate_does_not_prove_registry_non_equivocation": True,
            "adjacent_registry_epoch_transition_continuity_verifier_implemented": True,
            "previous_terminal_state_root_to_next_genesis_carry_forward_verification_implemented": True,
            "derived_next_genesis_checkpoint_verification_implemented": True,
            "joint_previous_and_next_epoch_transition_quorum_verification_implemented": True,
            "transition_successor_uniqueness_without_external_locking_not_claimed": True,
            "authenticated_out_of_band_registry_head_receipt_verified": False,
            "caller_challenge_freshness_verified": False,
            "caller_challenge_one_use_verified": False,
            "supplied_status_lineage_tail_denials_enforced": True,
            "global_latest_registry_head_verified": False,
            "global_latest_status_head_verified": False,
            "later_head_consistency_verified": False,
            "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified": False,
            "declared_fault_bound_observed_in_operation": False,
            "cross_anchor_non_equivocation_verified": False,
            "exclusive_vote_enforcement_verified": False,
            "independent_witness_journal_consistency_verified": False,
            "witness_locking_enforced": False,
            "selected_external_signing_keys_valid_at_check_required": True,
            "raw_base_and_review_authorization_prefix_internally_reverified": True,
            "frozen_ancestor_exact_json_scalar_type_preflight_implemented": True,
            "base_status_lineage_not_before_permit_enforced": True,
            "process_launch_identity_digest_bound_by_review_authorization_carriers": True,
            "process_launch_identity_authenticity_established": False,
            "production_permit_one_use_consumption_enforced": False,
            "verified_custody_stage_sequence": [
                "production_permit",
                "status_snapshot",
                "pre_execution_review",
                "authorization",
                "atomic_reservation_commit_attestation",
            ],
            "maximum_verified_custody_sequence": 5,
            "external_serializable_registry_commit_verified": False,
            "status_head_compare_and_set_committed": False,
            "permit_one_use_slot_consumed": False,
            "authorization_nonce_slot_consumed": False,
            "predecessor_successor_slot_consumed": False,
            "custody_successor_uniqueness_enforced": False,
            "external_registry_non_equivocation_verified": False,
            "registry_epoch_transition_continuity_verified": False,
        },
        "bounded_preflight": {
            "bootstrap_source_and_dependency_cooperative_deadline_seconds": 180.0,
            "run_start_dependency_cooperative_deadline_seconds": 180.0,
            "runner_parent_preflight_cooperative_deadline_seconds": 180.0,
            "physics_evaluation_hard_wall_seconds": 120.0,
            "worker_process_hard_kill_includes_worker_preflight": True,
            "bounded_streaming_directory_enumeration_established": True,
            "bounded_streaming_distribution_record_ingest_established": True,
            "source_and_dependency_file_pre_read_caps_established": True,
            "bounded_stdin_polling_established": True,
            "bounded_worker_stdout_streaming_established": True,
            "blocking_kernel_filesystem_call_preemption_established": False,
        },
        "signed_carrier_compatibility": {
            "legacy_frozen_contract_projection_rewritten_without_version_bump": False,
            "current_contracts_use_new_versioned_identities": True,
            "legacy_contract_document_verification_preserved": True,
            "legacy_signed_artifact_verification_preserved": False,
            "code_commit_sha_retained": True,
            "runner_source_sha256_retained": True,
            "six_dependency_artifact_manifest_sha256_rows_retained": True,
            "per_file_rows_cryptographically_bound_by_existing_artifact_digests": True,
            "deterministic_nonce_manifest_filename": "<nonce>.dependencies.json",
            "deterministic_nonce_source_manifest_filename": (
                "<nonce>.source-tree.json"
            ),
            "overall_manifest_sha256_separately_signed": False,
            "energy_force_upstream_review_and_authorization_use_symmetric_hmac": False,
            "energy_force_upstream_asymmetric_chain_established": True,
            "energy_force_upstream_public_key_verification_only": True,
            "energy_force_upstream_private_or_symmetric_verification_material_accepted": False,
            "production_evidence_class_common_four_event_foundation_implemented": True,
            "production_review_authorization_carriers_implemented": True,
            "production_review_authorization_custody_extension_implemented": True,
            "production_reservation_custody_extension_implemented": True,
            "reservation_commit_artifact_is_attestation_only": True,
            "external_same_epoch_registry_transaction_proof_verifier_implemented": True,
            "authenticated_external_head_status_receipt_verifier_implemented": True,
            "same_epoch_later_head_consistency_proof_verifier_implemented": True,
            "fixed_policy_same_epoch_anchor_scoped_witness_quorum_verifier_implemented": True,
            "anchor_scoped_quorum_certificate_does_not_prove_registry_non_equivocation": True,
            "adjacent_registry_epoch_transition_continuity_verifier_implemented": True,
            "joint_previous_and_next_epoch_transition_quorum_verification_implemented": True,
            "transition_successor_uniqueness_without_external_locking_not_claimed": True,
            "production_permit_one_use_enforced": False,
            "verified_custody_stage_sequence": [
                "production_permit",
                "status_snapshot",
                "pre_execution_review",
                "authorization",
                "atomic_reservation_commit_attestation",
            ],
            "planned_only_custody_stages": [
                "environment",
                "runner_start",
                "worker_transcript",
                "observation",
                "result",
                "result_review",
                "response",
            ],
            "final_stage_discriminated_production_carrier_family_implemented": False,
        },
        "native_runtime_and_worker_lifecycle": {
            "resident_native_mapping_snapshot_implemented": True,
            "fixed_proc_path_and_calling_pid_maps_view_bound": True,
            "procfs_superblock_magic_verified": False,
            "kernel_vdso_content_digest_bound": False,
            "authorized_native_dso_allowlist_implemented": False,
            "native_lifetime_closure_guard_implemented": False,
            "anonymous_deleted_memfd_or_writable_executable_mapping_gate": True,
            "worker_pre_state_persisted": True,
            "worker_post_state_persisted": True,
            "worker_payload_aggregate_bound_to_post_state": True,
            "worker_snapshot_process_id_bound_to_supervisor_child": True,
            "worker_stdout_hard_byte_bound_before_buffering": True,
            "worker_bounded_failure_prefix_and_transport_outcome_retained": True,
            "worker_request_canonical_document_and_transport_identity_retained": True,
            "worker_request_bound_to_persisted_observation_identity": True,
            "worker_request_run_nonce_start_code_source_dependency_environment_seed_and_materialization_crosschecked": True,
            "successful_raw_stdout_equals_canonical_reconstruction": True,
            "successful_transcript_digest_length_frame_order_independently_reverified": True,
            "worker_incomplete_lifecycle_discards_partial_payload": True,
            "worker_incomplete_payload_eligible_for_acceptance": False,
            "incomplete_raw_partial_transcript_independently_replayable": False,
            "supervisor_child_process_starttime_and_boot_id_bound": False,
            "linux_process_pid_parent_starttime_boot_and_namespace_measurement_implemented": True,
            "pid_namespace_init_parent_pid_zero_supported": True,
            "same_tick_pid_reuse_collision_excluded": False,
            "durable_process_uniqueness_established": False,
            "external_worker_launch_authenticity_established": False,
            "pre_post_equality_is_native_lifetime_closure": False,
        },
        "external_custody": {
            "ed25519_production_permit_primitive_implemented": True,
            "monotonic_signed_status_snapshot_primitive_implemented": True,
            "exact_raw_byte_dual_signed_four_event_custody_primitive_implemented": True,
            "production_pre_execution_review_and_authorization_carriers_implemented": True,
            "review_authorization_custody_extension_implemented": True,
            "reservation_custody_extension_implemented": True,
            "reservation_intent_and_commit_attestation_primitives_implemented": True,
            "external_same_epoch_registry_transaction_proof_verifier_implemented": True,
            "authenticated_external_head_status_receipt_verifier_implemented": True,
            "same_epoch_later_head_consistency_proof_verifier_implemented": True,
            "fixed_policy_same_epoch_anchor_scoped_witness_quorum_verifier_implemented": True,
            "quorum_intersection_above_declared_fault_bound_verification_implemented": True,
            "exclusive_vote_statement_signature_verification_implemented": True,
            "fixed_policy_full_roster_validity_and_denial_verification_implemented": True,
            "adjacent_registry_epoch_transition_continuity_verifier_implemented": True,
            "previous_terminal_state_root_to_next_genesis_carry_forward_verification_implemented": True,
            "derived_next_genesis_checkpoint_verification_implemented": True,
            "joint_previous_and_next_epoch_transition_quorum_verification_implemented": True,
            "transition_successor_uniqueness_without_external_locking_not_claimed": True,
            "sparse_merkle_permit_nonce_predecessor_transition_verification_implemented": True,
            "caller_expected_exact_current_registry_head_required": True,
            "exact_registry_head_status_tail_and_challenge_binding_implemented": True,
            "post_receipt_current_status_descendant_reverification_implemented": True,
            "adjacent_registry_checkpoint_lineage_verification_implemented": True,
            "original_consumed_slot_retention_verification_implemented": True,
            "post_consistency_current_status_descendant_reverification_implemented": True,
            "one_fork_consistency_does_not_prove_global_non_equivocation": True,
            "authenticated_out_of_band_current_registry_head_receipt_verified": False,
            "caller_challenge_freshness_verified": False,
            "caller_challenge_one_use_verified": False,
            "supplied_status_lineage_tail_denials_enforced": True,
            "global_latest_registry_head_verified": False,
            "global_latest_status_head_verified": False,
            "later_head_consistency_verified": False,
            "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified": False,
            "declared_fault_bound_observed_in_operation": False,
            "cross_anchor_non_equivocation_verified": False,
            "exclusive_vote_enforcement_verified": False,
            "independent_witness_journal_consistency_verified": False,
            "witness_locking_enforced": False,
            "frozen_ancestor_exact_json_scalar_type_preflight_implemented": True,
            "base_status_lineage_not_before_permit_enforced": True,
            "verified_custody_stage_sequence": [
                "production_permit",
                "status_snapshot",
                "pre_execution_review",
                "authorization",
                "atomic_reservation_commit_attestation",
            ],
            "maximum_verified_custody_sequence": 5,
            "production_permit_one_use_enforced": False,
            "custody_stages_after_status_snapshot_implemented": True,
            "custody_stages_after_authorization_implemented": True,
            "custody_stages_after_reservation_commit_implemented": False,
            "external_serializable_registry_commit_verified": False,
            "status_head_compare_and_set_committed": False,
            "permit_one_use_slot_consumed": False,
            "authorization_nonce_slot_consumed": False,
            "predecessor_successor_slot_consumed": False,
            "custody_successor_uniqueness_enforced": False,
            "external_registry_non_equivocation_verified": False,
            "registry_epoch_transition_continuity_verified": False,
            "production_evidence_class_exact_value": "synthetic_validation_production",
            "actual_production_permit_provisioned": False,
            "external_status_log_provisioned": False,
            "production_custody_chain_provisioned": False,
            "external_reservation_registry_provisioned": False,
            "external_registry_transaction_proof_provisioned": False,
            "out_of_band_current_registry_head_provisioned": False,
            "authenticated_external_head_status_receipt_provisioned": False,
            "post_receipt_current_status_descendant_provisioned": False,
            "later_head_consistency_proof_provisioned": False,
            "post_consistency_current_status_descendant_provisioned": False,
            "fixed_policy_witness_quorum_proof_provisioned": False,
            "fixed_policy_witness_keys_provisioned": False,
            "fixed_policy_witness_quorum_policy_provisioned": False,
            "post_quorum_current_status_descendant_provisioned": False,
            "adjacent_epoch_transition_proof_provisioned": False,
            "previous_epoch_transition_votes_provisioned": False,
            "next_epoch_transition_votes_provisioned": False,
            "next_epoch_transition_policy_provisioned": False,
            "post_transition_current_status_descendant_provisioned": False,
            "actual_production_reservation_commit_present": False,
            "root_owned_source_snapshot_provisioned": False,
            "root_owned_dependency_runtime_provisioned": False,
            "external_runtime_integrity_manifest_store_provisioned": False,
            "trusted_production_keys_provisioned": False,
            "independent_cpu_hosts_provisioned": 0,
        },
        "claim_policy": {
            "production_validation_execution_authorized": False,
            "production_validation_results_collected": False,
            "scientifically_validated": False,
            "force_or_energy_validated": False,
            "minimization_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "parameter_fitting_authorized": False,
            "claim_safe": False,
        },
        "blockers": list(_BLOCKERS),
    }


def validation_runtime_integrity_contract_document() -> dict[str, Any]:
    projection = _contract_projection()
    observed = _sha256(projection)
    if observed != FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256:
        raise ValidationRuntimeIntegrityContractError(
            "runtime-integrity contract projection drifted"
        )
    return {**projection, "contract_sha256": observed}


def require_validation_runtime_integrity_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationRuntimeIntegrityContractError(
            "runtime-integrity contract must be a mapping"
        )
    expected = validation_runtime_integrity_contract_document()
    if _canonical_bytes(dict(value)) != _canonical_bytes(expected):
        raise ValidationRuntimeIntegrityContractError(
            "runtime-integrity contract does not match the frozen record"
        )
    return expected


def validation_runtime_integrity_decision() -> dict[str, Any]:
    contract = validation_runtime_integrity_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "bound_minimization_trajectory_comparison_contract_sha256": (
            contract["bound_contracts"][
                "minimization_trajectory_comparison_contract_sha256"
            ]
        ),
        "bound_production_evidence_custody_contract_sha256": (
            contract["bound_contracts"]["production_evidence_custody_contract_sha256"]
        ),
        "bound_review_authorization_custody_extension_contract_sha256": (
            contract["bound_contracts"][
                "production_review_authorization_custody_extension_contract_sha256"
            ]
        ),
        "bound_reservation_custody_extension_contract_sha256": (
            contract["bound_contracts"][
                "production_reservation_custody_extension_contract_sha256"
            ]
        ),
        "bound_reservation_registry_proof_contract_sha256": (
            contract["bound_contracts"][
                "production_reservation_registry_proof_contract_sha256"
            ]
        ),
        "bound_reservation_authenticated_head_receipt_contract_sha256": (
            contract["bound_contracts"][
                "production_reservation_authenticated_head_receipt_contract_sha256"
            ]
        ),
        "bound_reservation_later_head_consistency_contract_sha256": (
            contract["bound_contracts"][
                "production_reservation_later_head_consistency_contract_sha256"
            ]
        ),
        "bound_reservation_witness_quorum_contract_sha256": (
            contract["bound_contracts"][
                "production_reservation_witness_quorum_contract_sha256"
            ]
        ),
        "bound_reservation_epoch_transition_contract_sha256": (
            contract["bound_contracts"][
                "production_reservation_epoch_transition_contract_sha256"
            ]
        ),
        "bound_process_launch_identity_contract_sha256": contract["bound_contracts"][
            "process_launch_identity_contract_sha256"
        ],
        "versioned_contract_identity_migration_implemented": True,
        "legacy_contract_document_verification_preserved": True,
        "legacy_signed_artifact_verification_preserved": False,
        "immutable_source_snapshot_enforcement_implemented": True,
        "durable_dependency_per_file_manifest_implemented": True,
        "durable_source_git_tree_manifest_implemented": True,
        "bounded_streaming_preflight_traversal_implemented": True,
        "resident_native_mapping_snapshot_implemented": True,
        "native_lifetime_closure_implemented": False,
        "worker_post_state_implemented": True,
        "worker_payload_completion_binding_implemented": True,
        "bounded_worker_stdout_streaming_implemented": True,
        "worker_snapshot_process_id_binding_implemented": True,
        "durable_worker_request_observation_binding_implemented": True,
        "successful_worker_transcript_reconstruction_implemented": True,
        "bounded_incomplete_worker_transport_disposition_implemented": True,
        "linux_process_launch_identity_primitive_implemented": True,
        "same_tick_pid_reuse_collision_excluded": False,
        "durable_process_uniqueness_established": False,
        "claim_closed_production_evidence_four_event_custody_foundation_implemented": True,
        "production_review_authorization_carriers_implemented": True,
        "production_review_authorization_custody_extension_implemented": True,
        "production_reservation_custody_extension_implemented": True,
        "reservation_intent_and_commit_attestation_primitives_implemented": True,
        "external_same_epoch_registry_transaction_proof_verifier_implemented": True,
        "sparse_merkle_three_slot_transition_verification_implemented": True,
        "caller_expected_exact_registry_head_required": True,
        "authenticated_external_head_status_receipt_verifier_implemented": True,
        "exact_registry_head_status_tail_and_challenge_binding_implemented": True,
        "post_receipt_current_status_descendant_reverification_implemented": True,
        "receipt_reverification_inputs_snapshotted_before_use": True,
        "same_epoch_later_head_consistency_proof_verifier_implemented": True,
        "adjacent_registry_checkpoint_lineage_verification_implemented": True,
        "original_consumed_slot_retention_verification_implemented": True,
        "post_consistency_current_status_descendant_reverification_implemented": True,
        "one_fork_consistency_does_not_prove_global_non_equivocation": True,
        "fixed_policy_same_epoch_anchor_scoped_witness_quorum_verifier_implemented": True,
        "quorum_intersection_above_declared_fault_bound_verification_implemented": True,
        "exclusive_vote_statement_signature_verification_implemented": True,
        "fixed_policy_full_roster_validity_and_denial_verification_implemented": True,
        "anchor_scoped_quorum_certificate_does_not_prove_registry_non_equivocation": True,
        "adjacent_registry_epoch_transition_continuity_verifier_implemented": True,
        "previous_terminal_state_root_to_next_genesis_carry_forward_verification_implemented": True,
        "derived_next_genesis_checkpoint_verification_implemented": True,
        "joint_previous_and_next_epoch_transition_quorum_verification_implemented": True,
        "transition_successor_uniqueness_without_external_locking_not_claimed": True,
        "authenticated_out_of_band_registry_head_receipt_verified": False,
        "authenticated_external_head_status_receipt_provisioned": False,
        "post_receipt_current_status_descendant_provisioned": False,
        "later_head_consistency_proof_provisioned": False,
        "post_consistency_current_status_descendant_provisioned": False,
        "fixed_policy_witness_quorum_proof_provisioned": False,
        "fixed_policy_witness_keys_provisioned": False,
        "fixed_policy_witness_quorum_policy_provisioned": False,
        "post_quorum_current_status_descendant_provisioned": False,
        "adjacent_epoch_transition_proof_provisioned": False,
        "previous_epoch_transition_votes_provisioned": False,
        "next_epoch_transition_votes_provisioned": False,
        "next_epoch_transition_policy_provisioned": False,
        "post_transition_current_status_descendant_provisioned": False,
        "caller_challenge_freshness_verified": False,
        "caller_challenge_one_use_verified": False,
        "supplied_status_lineage_tail_denials_enforced": True,
        "global_latest_registry_head_verified": False,
        "global_latest_status_head_verified": False,
        "later_head_consistency_verified": False,
        "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified": False,
        "declared_fault_bound_observed_in_operation": False,
        "cross_anchor_non_equivocation_verified": False,
        "exclusive_vote_enforcement_verified": False,
        "independent_witness_journal_consistency_verified": False,
        "witness_locking_enforced": False,
        "frozen_ancestor_exact_json_scalar_type_preflight_implemented": True,
        "base_status_lineage_not_before_permit_enforced": True,
        "process_launch_identity_digest_bound_by_review_authorization_carriers": True,
        "process_launch_identity_authenticity_established": False,
        "production_permit_one_use_enforced": False,
        "maximum_verified_custody_sequence": 5,
        "custody_stages_after_status_snapshot_implemented": True,
        "custody_stages_after_authorization_implemented": True,
        "custody_stages_after_reservation_commit_implemented": False,
        "external_serializable_registry_commit_verified": False,
        "status_head_compare_and_set_committed": False,
        "permit_one_use_slot_consumed": False,
        "authorization_nonce_slot_consumed": False,
        "predecessor_successor_slot_consumed": False,
        "custody_successor_uniqueness_enforced": False,
        "external_registry_non_equivocation_verified": False,
        "registry_epoch_transition_continuity_verified": False,
        "final_production_carrier_family_implemented": False,
        "production_custody_chain_provisioned": False,
        "energy_force_ed25519_post_result_review_contract_implemented": True,
        "energy_force_result_review_recomputes_metrics_from_retained_raw_evidence": True,
        "minimization_full_trajectory_comparison_contract_implemented": True,
        "minimization_checkpoint_restart_digest_comparison_implemented": True,
        "minimization_production_trajectory_comparison_receipt_present": False,
        "energy_force_upstream_asymmetric_chain_established": True,
        "external_worker_launch_authenticity_implemented": False,
        "external_production_runtime_provisioned": False,
        "production_validation_results_collected": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V16",
    "FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V15",
    "FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V14",
    "FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V13",
    "FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V12",
    "FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V11",
    "FROZEN_LEGACY_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256_V10",
    "FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_CONTRACT_ID",
    "VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SCHEMA_ID",
    "VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_MINIMIZATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256",
    "ValidationRuntimeIntegrityContractError",
    "require_validation_runtime_integrity_contract_document",
    "validation_runtime_integrity_contract_document",
    "validation_runtime_integrity_decision",
]
