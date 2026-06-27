from __future__ import annotations

from betelgeuze_product.docking_response import (
    DOCKING_SUBMISSION_TOP_LEVEL_KEYS,
    build_docking_submission_response,
)


def _record() -> dict:
    return {
        "job_id": "job-123",
        "status": "accepted_fail_closed",
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "target_id": "ADRB2",
        "customer_id": "cust-1",
        "user_id": "user-1",
        "validation_status": "pass",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "blockers": [],
        "warnings": [],
        "structure_analysis_status": "structure_analysis_ready",
        "structure_source_available": True,
        "structure_atom_count": 12,
        "structure_chain_count": 1,
        "structure_residue_count": 2,
        "structure_ligand_like_residue_count": 0,
        "progress_percent": 0.0,
        "progress_state": "ledger_intake_recorded",
        "current_step": "contract_validation",
        "queue_status": "queued_fail_closed",
        "queue_position": 1,
        "worker_state": "not_started_fail_closed",
        "engine_dispatch_ready": True,
        "worker_dispatch_enqueued": False,
        "worker_dispatch_reason": "runner_input_materialization_not_ready",
        "scope_claim_status": "restricted_local_allowed",
        "scope_claim_allowed_for_request": True,
        "general_platform_claim_allowed": False,
        "production_ai_promotion_allowed": False,
        "workflow_control_links": {
            "self": "/product/docking/jobs/job-123",
            "history": "/product/docking/jobs/job-123/history",
            "cancel": "/product/docking/jobs/job-123/cancel",
            "retry": "/product/docking/jobs/job-123/retry",
        },
        "claim_boundary": "restricted local delivery only",
        "ledger_path": "/internal/job-123.json",
        "private_payload_ref": "redacted-ref",
        "ligand_smiles": "CCO",
    }


def test_submission_response_top_level_keys_are_stable_snapshot() -> None:
    response = build_docking_submission_response(_record())

    assert set(response) == set(DOCKING_SUBMISSION_TOP_LEVEL_KEYS)
    assert list(response.keys()) == [
        "job_id",
        "status",
        "request_type",
        "family",
        "target_id",
        "customer_id",
        "user_id",
        "validation_status",
        "execution_enabled",
        "docking_results_emitted",
        "validation",
        "structure",
        "progress",
        "dispatch",
        "claim",
        "links",
        "claim_boundary",
    ]


def test_submission_response_groups_contract_for_gui() -> None:
    response = build_docking_submission_response(
        _record(), dispatch_outcome={"dispatched": True, "reason": "eligible"}
    )

    assert response["validation"] == {
        "status": "pass",
        "blocker_count": 0,
        "warning_count": 0,
        "blockers": [],
        "warnings": [],
    }
    assert response["structure"]["atom_count"] == 12
    assert response["progress"]["queue_status"] == "queued_fail_closed"
    assert response["dispatch"] == {
        "engine_dispatch_ready": True,
        "worker_dispatch_enqueued": True,
        "worker_dispatch_reason": "eligible",
    }
    assert response["claim"]["customer_pose_emission_allowed"] is False
    assert response["links"]["self"] == "/product/docking/jobs/job-123"


def test_submission_response_never_exposes_sensitive_or_internal_fields() -> None:
    response = build_docking_submission_response(_record())

    text = repr(response)
    assert "ledger_path" not in response
    assert "private_payload_ref" not in text
    assert "/internal/" not in text
    assert "ligand_smiles" not in text
    assert "CCO" not in text


def test_debug_response_only_adds_diagnostics_envelope_without_ledger_path() -> None:
    response = build_docking_submission_response(_record(), debug=True)

    assert set(response) == set(DOCKING_SUBMISSION_TOP_LEVEL_KEYS) | {"diagnostics"}
    assert "ledger_path" not in repr(response)
    assert isinstance(response["diagnostics"], dict)
