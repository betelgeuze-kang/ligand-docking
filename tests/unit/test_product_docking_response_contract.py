from __future__ import annotations

import json

from betelgeuze_product.docking_response import (
    DOCKING_SUBMISSION_TOP_LEVEL_KEYS,
    build_docking_submission_response,
    docking_claim_summary,
    docking_dispatch_summary,
    docking_links,
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
        "warnings": ["low resolution"],
        "structure_analysis_status": "ok",
        "structure_source_available": True,
        "structure_atom_count": 1200,
        "structure_chain_count": 1,
        "structure_residue_count": 300,
        "structure_ligand_like_residue_count": 2,
        "progress_percent": 0.0,
        "progress_state": "ledger_intake_recorded",
        "current_step": "contract_validation",
        "queue_status": "queued_fail_closed",
        "queue_position": 0,
        "worker_state": "not_started_fail_closed",
        "engine_dispatch_ready": True,
        "scope_claim_status": "scoped_allow",
        "scope_claim_allowed_for_request": True,
        "general_platform_claim_allowed": False,
        "production_ai_promotion_allowed": False,
        "claim_boundary": "Docking intake only; no scientific results emitted.",
        "workflow_control_links": {
            "self": "/product/docking/jobs/job-123",
            "history": "/product/docking/jobs/job-123/history",
            "cancel": "/product/docking/jobs/job-123/cancel",
            "retry": "/product/docking/jobs/job-123/retry",
        },
        # Internal / sensitive-ish diagnostics that must not surface by default.
        "ledger_path": "/srv/results/product_docking_jobs/job-123.json",
        "ai_decision_graph_trace": [{"node": "intake"}],
        "customer_report_sections": [{"block": "summary"}],
        "production_ai_blocked_reason": "shadow_only",
    }


def test_default_response_is_slim_and_grouped() -> None:
    resp = build_docking_submission_response(_record(), dispatch_outcome={"dispatched": True, "reason": "eligible"})
    assert set(resp.keys()) == set(DOCKING_SUBMISSION_TOP_LEVEL_KEYS)
    assert resp["job_id"] == "job-123"
    assert resp["validation"]["warning_count"] == 1
    assert resp["structure"]["atom_count"] == 1200
    assert resp["progress"]["state"] == "ledger_intake_recorded"
    assert resp["dispatch"]["worker_dispatch_enqueued"] is True
    assert resp["dispatch"]["worker_dispatch_reason"] == "eligible"
    assert resp["claim"]["scope_claim_status"] == "scoped_allow"
    assert resp["links"]["self"] == "/product/docking/jobs/job-123"


def test_default_response_never_leaks_internal_ledger_path() -> None:
    resp = build_docking_submission_response(_record())
    assert "ledger_path" not in resp
    serialized = json.dumps(resp)
    assert "/srv/results" not in serialized
    assert "product_docking_jobs" not in serialized


def test_default_response_hides_internal_diagnostics() -> None:
    resp = build_docking_submission_response(_record())
    assert "diagnostics" not in resp
    assert "ai_decision_graph_trace" not in resp
    assert "customer_report_sections" not in resp
    assert "production_ai_blocked_reason" not in resp


def test_debug_response_exposes_diagnostics_but_not_ledger_path() -> None:
    resp = build_docking_submission_response(_record(), debug=True)
    assert "diagnostics" in resp
    diagnostics = resp["diagnostics"]
    assert diagnostics["ai_decision_graph_trace"] == [{"node": "intake"}]
    assert diagnostics["customer_report_sections"] == [{"block": "summary"}]
    assert diagnostics["production_ai_blocked_reason"] == "shadow_only"
    # Even in debug mode, the internal filesystem path is never exposed.
    assert "ledger_path" not in resp
    assert "ledger_path" not in diagnostics
    assert "/srv/results" not in json.dumps(resp)


def test_dispatch_summary_falls_back_to_record_when_no_outcome() -> None:
    record = _record()
    record["worker_dispatch_enqueued"] = True
    record["worker_dispatch_reason"] = "replayed"
    summary = docking_dispatch_summary(record, None)
    assert summary["worker_dispatch_enqueued"] is True
    assert summary["worker_dispatch_reason"] == "replayed"
    assert summary["engine_dispatch_ready"] is True


def test_claim_summary_maps_existing_fields_only() -> None:
    claim = docking_claim_summary(_record())
    assert claim["customer_pose_emission_allowed"] is False
    assert claim["production_promotion_allowed"] is False
    assert claim["general_platform_claim_allowed"] is False
    assert claim["claim_boundary"].startswith("Docking intake only")


def test_links_fallback_when_record_missing_control_links() -> None:
    record = _record()
    del record["workflow_control_links"]
    links = docking_links(record)
    assert links == {
        "self": "/product/docking/jobs/job-123",
        "history": "/product/docking/jobs/job-123/history",
        "cancel": "/product/docking/jobs/job-123/cancel",
        "retry": "/product/docking/jobs/job-123/retry",
    }


def test_top_level_keys_match_contract_source_of_truth() -> None:
    # The contract analyzer's required keys are derived from this same constant.
    resp = build_docking_submission_response(_record())
    assert set(resp.keys()) == set(DOCKING_SUBMISSION_TOP_LEVEL_KEYS)
