from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record
from betelgeuze_product.job_orchestration import (
    acknowledge_cancel_job_record,
    cancel_job_record,
    fail_job_record,
    heartbeat_job_record,
    job_history,
    lease_job_record,
    list_job_records,
    mark_stale_worker_leases,
    retry_job_record,
    read_job_record,
    write_job_record,
)


def _request() -> dict[str, object]:
    return {
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "customer_id": "customer_unit",
        "user_id": "user_unit",
        "target_id": "ADRB2",
        "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
        "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
    }


def test_write_job_record_redacts_legacy_sensitive_payload(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    record = {
        "job_id": "legacy_raw",
        "materialization_ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
    }

    path = write_job_record(jobs_dir, record)
    raw_payload = path.read_text(encoding="utf-8")
    payload = json.loads(raw_payload)

    assert payload["materialization_ligands"][0]["smiles"]["redacted"] is True
    assert payload["pdb_content"]["redacted"] is True
    assert "CCO" not in raw_payload
    assert "ATOM      1" not in raw_payload


def test_job_orchestration_lists_history_cancel_and_retry_without_execution(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    record = build_docking_job_record(_request(), job_id="job_1", source_host="unit-test")
    persist_docking_job_record(record, jobs_dir)

    listing = list_job_records(jobs_dir)
    assert listing["status"] == "product_job_history_ready"
    assert listing["job_count"] == 1
    assert listing["jobs"][0]["job_id"] == "job_1"
    assert listing["jobs"][0]["root_job_id"] == "job_1"
    assert listing["jobs"][0]["source_host"] == "unit-test"
    assert listing["jobs"][0]["customer_id"] == "customer_unit"
    assert listing["jobs"][0]["user_id"] == "user_unit"
    assert listing["jobs"][0]["last_event_type"] == "created"
    assert listing["jobs"][0]["attempt_index"] == 1
    assert listing["jobs"][0]["root_attempt_count"] == 1
    assert listing["jobs"][0]["progress_percent"] == 0.0
    assert listing["jobs"][0]["progress_state"] == "ledger_intake_recorded"
    assert listing["jobs"][0]["current_step"] == "contract_validation"
    assert listing["jobs"][0]["worker_state"] == "not_started_fail_closed"
    assert listing["jobs"][0]["queue_status"] == "queued_fail_closed"
    assert listing["jobs"][0]["queue_position"] == 0
    assert listing["jobs"][0]["max_retry_attempts"] == 3
    assert listing["jobs"][0]["retry_policy"] == "operator_requested_retry_child_preserves_request_sha256_max_3"
    assert listing["jobs"][0]["retry_limit_reached"] is False
    assert listing["jobs"][0]["progress_percent_range_valid"] is True
    assert listing["jobs"][0]["status_progress_contract_ready"] is True
    assert listing["jobs"][0]["workflow_controls_ready"] is True
    assert listing["jobs"][0]["workflow_control_links"]["self"] == "/product/docking/jobs/job_1"
    assert listing["jobs"][0]["workflow_allowed_actions"] == [
        "view_status",
        "view_history",
        "cancel",
        "retry",
    ]
    assert listing["jobs"][0]["workflow_disabled_actions"] == []
    assert listing["jobs"][0]["status_transition_contract"]["current_status"] == "accepted_fail_closed"
    assert listing["jobs"][0]["status_transition_contract"]["fail_closed"] is True
    assert listing["jobs"][0]["idempotency_key"] == record["request_sha256"]
    assert listing["jobs"][0]["status_snapshot_persisted"] is True
    assert listing["jobs"][0]["job_retention_policy"] == "local_job_ledger_retain_90_days_minimum"
    assert listing["jobs"][0]["job_retention_days"] == 90
    assert listing["jobs"][0]["rerun_manifest_ready"] is True
    assert listing["jobs"][0]["status_snapshot"]["customer_id"] == "customer_unit"
    assert listing["jobs"][0]["rerun_manifest"]["customer_id"] == "customer_unit"
    assert listing["jobs"][0]["rerun_manifest"]["user_id"] == "user_unit"
    assert listing["jobs"][0]["reproducible_rerun_ready"] is True
    assert listing["jobs"][0]["long_running_status_persistence_ready"] is True
    assert listing["jobs"][0]["production_ai_inference_subject_active"] is False
    assert listing["jobs"][0]["production_ai_correction_applied"] is False
    assert listing["jobs"][0]["production_ai_abstention_enforced"] is True
    assert listing["jobs"][0]["production_ai_default_residual_mode"] == "shadow"
    assert listing["jobs"][0]["production_ai_promotion_allowed"] is False
    assert listing["jobs"][0]["production_ai_customer_facing_auto_correction_allowed"] is False
    assert listing["jobs"][0]["production_ai_customer_facing_score_mutation_allowed"] is False
    assert listing["jobs"][0]["production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert listing["jobs"][0]["production_ai_trained_checkpoint_count"] == 0
    assert "production checkpoint preflight is blocked" in listing["jobs"][0]["production_ai_abstention_reason"]
    assert "promote the residual model registry out of shadow mode" in listing["jobs"][0][
        "production_ai_what_would_change_decision"
    ]
    assert listing["jobs"][0]["scope_claim_guard_ready"] is True
    assert listing["jobs"][0]["scope_claim_allowed_for_request"] is True
    assert listing["jobs"][0]["scope_claim_status"] == "allowed_restricted_delivery_scope"
    assert listing["jobs"][0]["general_platform_claim_allowed"] is False
    assert listing["jobs"][0]["ai_decision_graph_trace_ready"] is True
    assert listing["jobs"][0]["ai_decision_graph_node_count"] == 7
    assert listing["jobs"][0]["ai_decision_graph_edge_count"] == 6
    assert listing["jobs"][0]["ai_decision_graph_abstention_node_id"] == "uncertainty_abstention_guard"
    assert listing["jobs"][0]["ai_decision_graph_current_node_id"] == "customer_report_ux"
    assert listing["jobs"][0]["customer_report_explanation_ready"] is True
    assert listing["jobs"][0]["customer_report_card_ready"] is True
    assert listing["jobs"][0]["customer_report_delivery_contract_ready"] is True
    assert listing["jobs"][0]["customer_report_evidence_binding_ready"] is True
    assert listing["jobs"][0]["customer_report_selection_rationale_ready"] is True
    assert listing["jobs"][0]["customer_report_uncertainty_posture_ready"] is True
    assert listing["jobs"][0]["customer_report_prohibited_claims_ready"] is True
    assert listing["jobs"][0]["customer_report_uncertainty_posture"] == "production_ai_abstained"
    assert "fresh_docking_pose_claim" in listing["jobs"][0]["customer_report_prohibited_claims"]
    assert listing["jobs"][0]["customer_report_ready_block_count"] == 7
    assert listing["jobs"][0]["customer_report_required_block_count"] == 7
    assert listing["jobs"][0]["customer_report_blocked_block_count"] == 0
    assert listing["jobs"][0]["customer_report_section_count"] == 7
    assert listing["jobs"][0]["customer_report_card"]["target_id"] == "ADRB2"
    assert listing["jobs"][0]["customer_report_card"]["ranking_mutation_policy"] == (
        "customer_ranking_mutation_locked_by_shadow_guard"
    )
    assert listing["jobs"][0]["customer_report_primary_abstention_reason"] == listing["jobs"][0][
        "production_ai_abstention_reason"
    ]

    cancelled = cancel_job_record(jobs_dir, "job_1", reason="operator requested", actor="qa")
    assert cancelled["status"] == "cancel_requested_fail_closed"
    assert cancelled["cancel_recorded"] is True
    assert cancelled["status_snapshot"]["status"] == "cancel_requested_fail_closed"
    assert cancelled["queue_status"] == "cancel_requested_fail_closed"
    assert cancelled["cancellable"] is False
    assert cancelled["retryable"] is True
    assert cancelled["status_progress_contract_ready"] is True
    assert cancelled["workflow_controls_ready"] is True
    assert cancelled["workflow_allowed_actions"] == ["view_status", "view_history", "retry"]
    assert cancelled["workflow_disabled_actions"] == ["cancel"]
    assert cancelled["status_transition_contract"]["current_status"] == "cancel_requested_fail_closed"
    assert cancelled["execution_enabled"] is False
    assert cancelled["docking_results_emitted"] is False

    retried = retry_job_record(jobs_dir, "job_1", reason="rerun with same manifest", actor="qa")
    assert retried["status"] == "retry_requested_fail_closed"
    assert retried["retry_recorded"] is True
    assert retried["retry_request_count"] == 1
    assert retried["retry_of_job_id"] == "job_1"
    assert retried["root_job_id"] == "job_1"
    assert retried["parent_job_id"] == "job_1"
    assert retried["customer_id"] == "customer_unit"
    assert retried["user_id"] == "user_unit"
    assert retried["job_id"] == "job_1-retry-1"
    assert retried["attempt_index"] == 2
    assert retried["request_sha256"] == record["request_sha256"]
    assert retried["idempotency_key"] == record["request_sha256"]
    assert retried["progress_state"] == "retry_attempt_recorded"
    assert retried["status_snapshot"]["status"] == "retry_requested_fail_closed"
    assert retried["queue_status"] == "retry_attempt_recorded_fail_closed"
    assert retried["progress_percent_range_valid"] is True
    assert retried["status_progress_contract_ready"] is True
    assert retried["workflow_controls_ready"] is True
    assert retried["workflow_allowed_actions"] == ["view_status", "view_history", "cancel", "retry"]
    assert retried["workflow_control_links"]["history"] == "/product/docking/jobs/job_1-retry-1/history"
    assert retried["rerun_manifest"]["request_sha256"] == record["request_sha256"]
    assert retried["rerun_manifest"]["customer_id"] == "customer_unit"
    assert retried["rerun_manifest"]["user_id"] == "user_unit"
    assert retried["job_retention_days"] == 90
    assert retried["execution_enabled"] is False
    assert retried["docking_results_emitted"] is False

    history = job_history(jobs_dir, "job_1")
    assert history["source_host"] == "unit-test"
    assert history["customer_id"] == "customer_unit"
    assert history["user_id"] == "user_unit"
    assert history["root_job_id"] == "job_1"
    assert history["event_actors"] == ["qa", "unit-test"]
    assert history["event_count"] == 3
    assert history["production_ai_inference_subject_active"] is False
    assert history["production_ai_correction_applied"] is False
    assert history["production_ai_abstention_enforced"] is True
    assert history["production_ai_customer_facing_auto_correction_allowed"] is False
    assert history["production_ai_customer_facing_score_mutation_allowed"] is False
    assert history["production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert history["production_ai_default_residual_mode"] == "shadow"
    assert history["production_ai_trained_checkpoint_count"] == 0
    assert history["production_ai_selected_sidecar_missing_output_fields"] == ["delta_force"]
    assert "production checkpoint preflight is blocked" in history["production_ai_abstention_reason"]
    assert "promote the residual model registry out of shadow mode" in history[
        "production_ai_what_would_change_decision"
    ]
    assert history["scope_claim_guard_ready"] is True
    assert history["scope_claim_allowed_for_request"] is True
    assert history["scope_claim_status"] == "allowed_restricted_delivery_scope"
    assert history["general_platform_claim_allowed"] is False
    assert history["ai_decision_graph_trace_ready"] is True
    assert history["ai_decision_graph_node_count"] == 7
    assert history["ai_decision_graph_edge_count"] == 6
    assert history["ai_decision_graph_abstention_node_id"] == "uncertainty_abstention_guard"
    assert history["ai_decision_graph_current_node_id"] == "customer_report_ux"
    assert history["ai_decision_graph_trace"][0]["node_id"] == "structure_quality"
    assert history["ai_decision_graph_edges"][0]["from_node"] == "structure_quality"
    assert history["customer_report_explanation_ready"] is True
    assert history["customer_report_card_ready"] is True
    assert history["customer_report_delivery_contract_ready"] is True
    assert history["customer_report_evidence_binding_ready"] is True
    assert history["customer_report_selection_rationale_ready"] is True
    assert history["customer_report_uncertainty_posture_ready"] is True
    assert history["customer_report_prohibited_claims_ready"] is True
    assert history["customer_report_uncertainty_posture"] == "production_ai_abstained"
    assert "customer_facing_ranking_mutation_claim" in history["customer_report_prohibited_claims"]
    assert history["customer_report_ready_block_count"] == 7
    assert history["customer_report_required_block_count"] == 7
    assert history["customer_report_blocked_block_count"] == 0
    assert history["customer_report_section_count"] == 7
    assert history["customer_report_card"]["target_id"] == "ADRB2"
    assert history["customer_report_sections"][0]["section_id"] == "binding_site_explanation"
    assert history["customer_report_primary_abstention_reason"] == history["production_ai_abstention_reason"]
    assert history["status_snapshot_persisted"] is True
    assert history["status_snapshot"]["status"] == "retry_requested_fail_closed"
    assert history["status_snapshot"]["customer_id"] == "customer_unit"
    assert history["rerun_manifest"]["customer_id"] == "customer_unit"
    assert history["rerun_manifest"]["user_id"] == "user_unit"
    assert history["queue_status"] == "retry_requested_fail_closed"
    assert history["progress_percent"] == 0.0
    assert history["status_progress_contract_ready"] is True
    assert history["workflow_controls_ready"] is True
    assert history["workflow_allowed_actions"] == ["view_status", "view_history", "retry"]
    assert history["workflow_disabled_actions"] == ["cancel"]
    assert history["status_transition_contract"]["current_status"] == "retry_requested_fail_closed"
    assert history["status_transition_contract"]["queue_status"] == "retry_requested_fail_closed"
    assert history["job_retention_policy"] == "local_job_ledger_retain_90_days_minimum"
    assert history["job_retention_days"] == 90
    assert history["rerun_manifest_ready"] is True
    assert history["rerun_manifest"]["request_sha256"] == record["request_sha256"]
    assert history["reproducible_rerun_ready"] is True
    assert history["long_running_status_persistence_ready"] is True
    assert [event["event_type"] for event in history["events"]] == [
        "created",
        "cancel_requested",
        "retry_requested",
    ]
    assert history["events"][-1]["retry_job_id"] == "job_1-retry-1"
    assert history["external_state_mutated"] is False

    retry_history = job_history(jobs_dir, "job_1-retry-1")
    assert retry_history["root_job_id"] == "job_1"
    assert retry_history["customer_id"] == "customer_unit"
    assert retry_history["user_id"] == "user_unit"
    assert retry_history["event_actors"] == ["qa"]
    assert retry_history["event_count"] == 1
    assert retry_history["status_snapshot_persisted"] is True
    assert retry_history["queue_status"] == "retry_attempt_recorded_fail_closed"
    assert retry_history["status_progress_contract_ready"] is True
    assert retry_history["rerun_manifest_ready"] is True
    assert retry_history["job_retention_days"] == 90
    assert retry_history["events"][0]["event_type"] == "retry_attempt_created"

    listing = list_job_records(jobs_dir)
    assert listing["job_count"] == 2
    assert {row["job_id"] for row in listing["jobs"]} == {"job_1", "job_1-retry-1"}
    assert {row["root_job_id"] for row in listing["jobs"]} == {"job_1"}
    assert {row["root_attempt_count"] for row in listing["jobs"]} == {2}
    assert {row["status_progress_contract_ready"] for row in listing["jobs"]} == {True}
    assert {row["queue_status"] for row in listing["jobs"]} == {
        "retry_requested_fail_closed",
        "retry_attempt_recorded_fail_closed",
    }
    source_filtered = list_job_records(jobs_dir, source_host="unit-test")
    assert source_filtered["job_count"] == 2
    root_filtered = list_job_records(jobs_dir, root_job_id="job_1")
    assert root_filtered["job_count"] == 2
    customer_filtered = list_job_records(jobs_dir, customer_id="customer_unit")
    assert customer_filtered["customer_id_filter"] == "customer_unit"
    assert customer_filtered["job_count"] == 2
    user_filtered = list_job_records(jobs_dir, user_id="user_unit")
    assert user_filtered["user_id_filter"] == "user_unit"
    assert user_filtered["job_count"] == 2


def test_job_orchestration_missing_job_fails_closed(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"

    assert cancel_job_record(jobs_dir, "missing")["status"] == "missing"
    assert retry_job_record(jobs_dir, "missing")["retry_recorded"] is False
    assert job_history(jobs_dir, "missing")["event_count"] == 0


def test_job_orchestration_worker_lifecycle_and_resume_are_persisted(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    record = build_docking_job_record(_request(), job_id="job_worker", source_host="unit-test")
    persist_docking_job_record(record, jobs_dir)

    leased = lease_job_record(jobs_dir, "job_worker", worker_id="worker_1", actor="worker")
    assert leased["status"] == "running_fail_closed"
    assert leased["worker_lease_acquired"] is True
    assert leased["worker_lease_id"] == "job_worker:lease:1"
    assert leased["queue_status"] == "worker_lease_active_fail_closed"
    assert leased["status_progress_contract_ready"] is True
    assert leased["execution_enabled"] is False
    assert leased["docking_results_emitted"] is False

    heartbeat = heartbeat_job_record(
        jobs_dir,
        "job_worker",
        worker_id="worker_1",
        progress_percent=42.0,
        current_step="pose_scoring_probe",
        actor="worker",
    )
    assert heartbeat["heartbeat_recorded"] is True
    assert heartbeat["progress_percent"] == 42.0
    assert heartbeat["worker_state"] == "active_fail_closed"
    assert heartbeat["status_snapshot"]["worker_lease_id"] == "job_worker:lease:1"
    assert heartbeat["status_progress_contract_ready"] is True

    failed = fail_job_record(jobs_dir, "job_worker", reason="unit retryable failure", actor="worker")
    assert failed["status"] == "failed_fail_closed"
    assert failed["failure_recorded"] is True
    assert failed["retryable"] is True
    assert failed["queue_status"] == "failed_retryable_fail_closed"
    assert failed["status_progress_contract_ready"] is True

    retried = retry_job_record(jobs_dir, "job_worker", reason="resume failed worker", actor="qa")
    assert retried["job_id"] == "job_worker-retry-1"
    assert retried["root_job_id"] == "job_worker"
    assert retried["parent_job_id"] == "job_worker"
    assert retried["attempt_index"] == 2
    assert retried["request_sha256"] == record["request_sha256"]

    lease_retry = lease_job_record(jobs_dir, "job_worker-retry-1", worker_id="worker_2", actor="worker")
    assert lease_retry["worker_lease_acquired"] is True
    cancel_requested = cancel_job_record(jobs_dir, "job_worker-retry-1", reason="stop retry", actor="qa")
    assert cancel_requested["cancel_recorded"] is True
    cancel_ack = acknowledge_cancel_job_record(
        jobs_dir,
        "job_worker-retry-1",
        worker_id="worker_2",
        reason="ack stop",
        actor="worker",
    )
    assert cancel_ack["worker_cancel_acknowledged"] is True
    assert cancel_ack["worker_state"] == "cancel_acknowledged_fail_closed"
    assert cancel_ack["retryable"] is True
    assert cancel_ack["status_progress_contract_ready"] is True

    history = job_history(jobs_dir, "job_worker-retry-1")
    assert history["worker_cancel_acknowledged"] is True
    assert history["worker_lease_id"] == "job_worker-retry-1:lease:1"
    assert history["event_count"] == 4
    assert [event["event_type"] for event in history["events"]] == [
        "retry_attempt_created",
        "worker_lease_acquired",
        "cancel_requested",
        "worker_cancel_acknowledged",
    ]


def test_job_orchestration_marks_stale_worker_lease_retryable(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    stale_record = build_docking_job_record(_request(), job_id="job_stale", source_host="unit-test")
    fresh_record = build_docking_job_record(_request(), job_id="job_fresh", source_host="unit-test")
    persist_docking_job_record(stale_record, jobs_dir)
    persist_docking_job_record(fresh_record, jobs_dir)

    lease_job_record(jobs_dir, "job_stale", worker_id="worker_stale", actor="worker")
    lease_job_record(jobs_dir, "job_fresh", worker_id="worker_fresh", actor="worker")
    aged = read_job_record(jobs_dir, "job_stale")
    aged["heartbeat_at_utc"] = "2000-01-01T00:00:00+00:00"
    write_job_record(jobs_dir, aged)

    sweep = mark_stale_worker_leases(jobs_dir, lease_timeout_seconds=1800, actor="watchdog")

    assert sweep["status"] == "stale_worker_lease_sweep_ready"
    assert sweep["stale_worker_lease_detected_count"] == 1
    assert sweep["stale_worker_lease_updated_count"] == 1
    assert sweep["retryable_after_stale_count"] == 1
    assert sweep["updated_job_ids"] == ["job_stale"]

    stale_history = job_history(jobs_dir, "job_stale")
    assert stale_history["status"] == "failed_fail_closed"
    assert stale_history["retryable"] is True
    assert stale_history["cancellable"] is False
    assert stale_history["stale_worker_lease_detected"] is True
    assert stale_history["stale_worker_lease_timeout_seconds"] == 1800
    assert stale_history["stale_worker_lease_previous_heartbeat_at_utc"] == "2000-01-01T00:00:00+00:00"
    assert stale_history["status_progress_contract_ready"] is True
    assert stale_history["events"][-1]["event_type"] == "worker_lease_stale"
    assert stale_history["events"][-1]["lease_timeout_seconds"] == 1800

    fresh_history = job_history(jobs_dir, "job_fresh")
    assert fresh_history["status"] == "running_fail_closed"
    assert fresh_history["retryable"] is False
    assert fresh_history["stale_worker_lease_detected"] is False

    retry = retry_job_record(jobs_dir, "job_stale", reason="resume stale worker", actor="qa")
    assert retry["job_id"] == "job_stale-retry-1"
    assert retry["request_sha256"] == stale_record["request_sha256"]
