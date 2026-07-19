from __future__ import annotations

from copy import deepcopy

import pytest

from betelgeuze_engine_v2.physics.validation_runtime_integrity_contract import (
    FROZEN_VALIDATION_RUNTIME_INTEGRITY_CONTRACT_SHA256,
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
    assert "legacy_frozen_contract_version_migration_missing" not in first["blockers"]
    assert "durable_source_per_file_manifest_missing" not in first["blockers"]
    assert "bounded_streaming_preflight_traversal_missing" not in first["blockers"]
    assert "mapped_native_dso_snapshot_missing" not in first["blockers"]
    assert "worker_pre_post_runtime_evidence_missing" not in first["blockers"]
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
    assert all(value is False for value in first["claim_policy"].values())
    assert decision["durable_dependency_per_file_manifest_implemented"] is True
    assert decision["durable_source_git_tree_manifest_implemented"] is True
    assert decision["bounded_streaming_preflight_traversal_implemented"] is True
    assert decision["resident_native_mapping_snapshot_implemented"] is True
    assert decision["worker_post_state_implemented"] is True
    assert decision["worker_payload_completion_binding_implemented"] is True
    assert decision["bounded_worker_stdout_streaming_implemented"] is True
    assert decision["worker_snapshot_process_id_binding_implemented"] is True
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
