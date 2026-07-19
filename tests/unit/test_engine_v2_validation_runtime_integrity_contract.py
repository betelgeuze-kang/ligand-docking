from __future__ import annotations

from copy import deepcopy

import pytest

from betelgeuze_engine_v2.physics.validation_process_launch_identity import (
    FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
    FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_runtime_integrity_contract import (
    FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256,
    VALIDATION_RUNTIME_INTEGRITY_BOUND_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
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
        == "5.0.0"
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
        is True
    )
    assert (
        first["signed_carrier_compatibility"][
            "energy_force_upstream_asymmetric_chain_established"
        ]
        is False
    )
    assert "legacy_frozen_contract_version_migration_missing" not in first["blockers"]
    assert "durable_source_per_file_manifest_missing" not in first["blockers"]
    assert "bounded_streaming_preflight_traversal_missing" not in first["blockers"]
    assert "mapped_native_dso_snapshot_missing" not in first["blockers"]
    assert "worker_pre_post_runtime_evidence_missing" not in first["blockers"]
    assert "energy_force_ed25519_chain_missing" not in first["blockers"]
    assert "energy_force_independent_result_review_missing" in first["blockers"]
    assert "energy_force_upstream_symmetric_hmac_chain" in first["blockers"]
    assert "external_worker_launch_authenticity_or_custody_missing" in first["blockers"]
    assert "same_tick_pid_reuse_collision_not_excluded" in first["blockers"]
    assert "final_production_carrier_family_not_implemented" in first["blockers"]
    assert "production_permit_one_use_consumption_not_enforced" in first["blockers"]
    assert (
        "custody_stages_after_status_snapshot_not_implemented" not in first["blockers"]
    )
    assert "reservation_and_later_custody_stages_not_implemented" in first["blockers"]
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
    ]
    assert first["external_custody"]["maximum_verified_custody_sequence"] == 4
    assert first["external_custody"]["production_permit_one_use_enforced"] is False
    assert (
        first["external_custody"]["custody_stages_after_status_snapshot_implemented"]
        is True
    )
    assert (
        first["external_custody"]["custody_stages_after_authorization_implemented"]
        is False
    )
    assert first["external_custody"]["custody_successor_uniqueness_enforced"] is False
    assert first["signed_carrier_compatibility"]["planned_only_custody_stages"] == [
        "reservation",
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
    assert decision["energy_force_upstream_asymmetric_chain_established"] is False
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
    assert decision["maximum_verified_custody_sequence"] == 4
    assert decision["custody_stages_after_status_snapshot_implemented"] is True
    assert decision["custody_stages_after_authorization_implemented"] is False
    assert decision["custody_successor_uniqueness_enforced"] is False
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
