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

from betelgeuze_engine_v2.physics.validation_process_launch_identity import (
    FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
    FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
)

VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_runtime_integrity_contract/5.0.0"
)
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_ID = (
    "engine_v2_synthetic_validation_runtime_integrity/5.0.0"
)
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION = "5.0.0"
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_FROZEN_AT_UTC = "2026-07-19T05:40:00Z"
VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256 = (
    FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
)
VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256 = FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256 = (
    FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
)
FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256 = (
    "a93386f2be7a68c65684d25a057c5291f9d0374e2fc3c984e53a98fc5e29e8c1"
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
    "reservation_and_later_custody_stages_not_implemented",
    "external_custody_successor_uniqueness_not_provisioned",
    "external_runtime_integrity_manifest_store_missing",
    "energy_force_independent_result_review_missing",
    "energy_force_upstream_symmetric_hmac_chain",
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
        "lanes": [
            "27-case-59-variant-energy-force",
            "14-case-minimization",
        ],
        "bound_contracts": {
            "production_evidence_custody_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
            ),
            "production_review_authorization_custody_extension_contract_sha256": (
                VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
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
            "result_finalization_reuses_environment_manifest_reverification": True,
            "energy_force_ed25519_post_result_review_contract_implemented": True,
            "energy_force_result_review_recomputes_metrics_from_retained_raw_evidence": True,
            "linux_process_launch_identity_primitive_implemented": True,
            "claim_closed_production_permit_status_four_event_custody_primitives_implemented": True,
            "production_pre_execution_review_and_authorization_carriers_implemented": True,
            "production_review_authorization_custody_extension_implemented": True,
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
            ],
            "maximum_verified_custody_sequence": 4,
            "custody_successor_uniqueness_enforced": False,
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
            "energy_force_upstream_review_and_authorization_use_symmetric_hmac": True,
            "energy_force_upstream_asymmetric_chain_established": False,
            "production_evidence_class_common_four_event_foundation_implemented": True,
            "production_review_authorization_carriers_implemented": True,
            "production_review_authorization_custody_extension_implemented": True,
            "production_permit_one_use_enforced": False,
            "verified_custody_stage_sequence": [
                "production_permit",
                "status_snapshot",
                "pre_execution_review",
                "authorization",
            ],
            "planned_only_custody_stages": [
                "reservation",
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
            "frozen_ancestor_exact_json_scalar_type_preflight_implemented": True,
            "base_status_lineage_not_before_permit_enforced": True,
            "verified_custody_stage_sequence": [
                "production_permit",
                "status_snapshot",
                "pre_execution_review",
                "authorization",
            ],
            "maximum_verified_custody_sequence": 4,
            "production_permit_one_use_enforced": False,
            "custody_stages_after_status_snapshot_implemented": True,
            "custody_stages_after_authorization_implemented": False,
            "custody_successor_uniqueness_enforced": False,
            "production_evidence_class_exact_value": "synthetic_validation_production",
            "actual_production_permit_provisioned": False,
            "external_status_log_provisioned": False,
            "production_custody_chain_provisioned": False,
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
        "bound_production_evidence_custody_contract_sha256": (
            contract["bound_contracts"]["production_evidence_custody_contract_sha256"]
        ),
        "bound_review_authorization_custody_extension_contract_sha256": (
            contract["bound_contracts"][
                "production_review_authorization_custody_extension_contract_sha256"
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
        "frozen_ancestor_exact_json_scalar_type_preflight_implemented": True,
        "base_status_lineage_not_before_permit_enforced": True,
        "process_launch_identity_digest_bound_by_review_authorization_carriers": True,
        "process_launch_identity_authenticity_established": False,
        "production_permit_one_use_enforced": False,
        "maximum_verified_custody_sequence": 4,
        "custody_stages_after_status_snapshot_implemented": True,
        "custody_stages_after_authorization_implemented": False,
        "custody_successor_uniqueness_enforced": False,
        "final_production_carrier_family_implemented": False,
        "production_custody_chain_provisioned": False,
        "energy_force_ed25519_post_result_review_contract_implemented": True,
        "energy_force_result_review_recomputes_metrics_from_retained_raw_evidence": True,
        "energy_force_upstream_asymmetric_chain_established": False,
        "external_worker_launch_authenticity_implemented": False,
        "external_production_runtime_provisioned": False,
        "production_validation_results_collected": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_CONTRACT_ID",
    "VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SCHEMA_ID",
    "VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256",
    "VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256",
    "ValidationRuntimeIntegrityContractError",
    "require_validation_runtime_integrity_contract_document",
    "validation_runtime_integrity_contract_document",
    "validation_runtime_integrity_decision",
]
