"""Companion contract for production-class validation runtime integrity.

The active energy-force and minimization chains use new versioned contract
identities.  Superseded contract documents remain exactly verifiable by their
frozen hashes; superseded signed artifacts and receipts are not supported.
This companion records the stronger enforcement now implemented and keeps
production collection closed until native lifetime closure, worker post-state,
external custody, and production infrastructure exist.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_runtime_integrity_contract/2.0.0"
)
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_ID = (
    "engine_v2_synthetic_validation_runtime_integrity/2.0.0"
)
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_VERSION = "2.0.0"
VALIDATION_RUNTIME_INTEGRITY_CONTRACT_FROZEN_AT_UTC = "2026-07-18T23:33:55Z"
FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256 = (
    "b0c3b1cf2f4182ad6c1f508be7126a3ca01c6c6aa3ff03d8c754d25bafee4e22"
)

_BLOCKERS = (
    "external_root_owned_source_snapshot_not_provisioned",
    "source_snapshot_kernel_immutability_not_established",
    "prebootstrap_loaded_stdlib_origin_closure_missing",
    "external_signed_native_dso_allowlist_missing",
    "kernel_vdso_content_identity_missing",
    "procfs_superblock_identity_missing",
    "native_lifetime_closure_guard_missing",
    "worker_request_observation_identity_binding_missing",
    "external_runtime_integrity_manifest_store_missing",
    "energy_force_ed25519_chain_missing",
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
        "lanes": [
            "27-case-59-variant-energy-force",
            "14-case-minimization",
        ],
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
            "worker_request_bound_to_persisted_observation_identity": False,
            "worker_incomplete_lifecycle_discards_partial_payload": True,
            "pre_post_equality_is_native_lifetime_closure": False,
        },
        "external_custody": {
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
    if dict(value) != expected:
        raise ValidationRuntimeIntegrityContractError(
            "runtime-integrity contract does not match the frozen record"
        )
    return expected


def validation_runtime_integrity_decision() -> dict[str, Any]:
    contract = validation_runtime_integrity_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
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
    "ValidationRuntimeIntegrityContractError",
    "require_validation_runtime_integrity_contract_document",
    "validation_runtime_integrity_contract_document",
    "validation_runtime_integrity_decision",
]
