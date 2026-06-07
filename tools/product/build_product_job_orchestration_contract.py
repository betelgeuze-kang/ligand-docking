#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

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
    read_job_record,
    retry_job_record,
    write_job_record,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_job_orchestration_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_job_orchestration_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_job_orchestration_contract_current.md"

CLAIM_BOUNDARY = (
    "Product job orchestration contract only; probes local fail-closed job ledger semantics for intake, list, "
    "history, cancel, retry-child creation, idempotency, progress fields, worker lease, heartbeat, cancel "
    "acknowledgment, and retryable failure recovery. It does not run docking, execute scientific workers, emit "
    "scientific results, upload, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _request_payload() -> dict[str, Any]:
    return {
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "customer_id": "customer_contract_probe",
        "user_id": "user_contract_probe",
        "target_id": "ADRB2",
        "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
        "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
    }


def _check(check_id: str, status: str, observed: str, requirement: str, next_action: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "requirement": requirement,
        "next_action": next_action,
        "release_blocker": status != "ready",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def _all_events_fail_closed(records: list[dict[str, Any]]) -> bool:
    for record in records:
        if record.get("execution_enabled") is not False:
            return False
        if record.get("docking_results_emitted") is not False:
            return False
        if record.get("external_state_mutated") is not False:
            return False
        for event in record.get("event_history") or []:
            if not isinstance(event, dict):
                return False
            if event.get("execution_enabled") is not False:
                return False
            if event.get("docking_results_emitted") is not False:
                return False
            if event.get("external_state_mutated") is not False:
                return False
    return True


def build_product_job_orchestration_contract(*, jobs_dir: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="product_job_orchestration_") as tmp:
        probe_dir = jobs_dir or (Path(tmp) / "jobs")
        root_record = build_docking_job_record(_request_payload(), job_id="job_orchestration_probe_1", source_host="contract-probe")
        persist_docking_job_record(root_record, probe_dir)
        initial_listing = list_job_records(probe_dir)
        cancelled = cancel_job_record(probe_dir, root_record["job_id"], reason="contract probe cancel", actor="contract-probe")
        retry_child = retry_job_record(probe_dir, root_record["job_id"], reason="contract probe retry", actor="contract-probe")
        leased = lease_job_record(
            probe_dir,
            retry_child.get("job_id", ""),
            worker_id="worker_contract_probe_1",
            actor="contract-probe-worker",
        )
        heartbeat = heartbeat_job_record(
            probe_dir,
            retry_child.get("job_id", ""),
            worker_id="worker_contract_probe_1",
            progress_percent=37.5,
            current_step="pose_scoring_probe",
            actor="contract-probe-worker",
        )
        failed = fail_job_record(
            probe_dir,
            retry_child.get("job_id", ""),
            reason="contract probe retryable failure",
            actor="contract-probe-worker",
        )
        resumed_child = retry_job_record(
            probe_dir,
            retry_child.get("job_id", ""),
            reason="contract probe resume after failure",
            actor="contract-probe",
        )
        cancel_lease = lease_job_record(
            probe_dir,
            resumed_child.get("job_id", ""),
            worker_id="worker_contract_probe_2",
            actor="contract-probe-worker",
        )
        cancel_heartbeat = heartbeat_job_record(
            probe_dir,
            resumed_child.get("job_id", ""),
            worker_id="worker_contract_probe_2",
            progress_percent=12.5,
            current_step="structure_quality_probe",
            actor="contract-probe-worker",
        )
        cancel_requested = cancel_job_record(
            probe_dir,
            resumed_child.get("job_id", ""),
            reason="contract probe cancel running job",
            actor="contract-probe",
        )
        cancel_ack = acknowledge_cancel_job_record(
            probe_dir,
            resumed_child.get("job_id", ""),
            worker_id="worker_contract_probe_2",
            reason="contract probe cancel acknowledged",
            actor="contract-probe-worker",
        )
        stale_root = build_docking_job_record(
            _request_payload(),
            job_id="job_orchestration_probe_stale_1",
            source_host="contract-probe",
        )
        persist_docking_job_record(stale_root, probe_dir)
        stale_lease = lease_job_record(
            probe_dir,
            stale_root["job_id"],
            worker_id="worker_contract_probe_stale",
            actor="contract-probe-worker",
        )
        aged_stale = read_job_record(probe_dir, stale_root["job_id"])
        aged_stale["heartbeat_at_utc"] = "2000-01-01T00:00:00+00:00"
        aged_stale["updated_at_utc"] = "2000-01-01T00:00:00+00:00"
        write_job_record(probe_dir, aged_stale)
        stale_sweep = mark_stale_worker_leases(
            probe_dir,
            lease_timeout_seconds=1800,
            actor="contract-probe-watchdog",
        )
        stale_history = job_history(probe_dir, stale_root["job_id"])
        root_history = job_history(probe_dir, root_record["job_id"])
        retry_history = job_history(probe_dir, retry_child.get("job_id", ""))
        resumed_history = job_history(probe_dir, resumed_child.get("job_id", ""))
        final_listing = list_job_records(probe_dir)
        source_filtered_listing = list_job_records(probe_dir, source_host="contract-probe")
        root_filtered_listing = list_job_records(probe_dir, root_job_id=root_record["job_id"])
        customer_filtered_listing = list_job_records(probe_dir, customer_id="customer_contract_probe")
        user_filtered_listing = list_job_records(probe_dir, user_id="user_contract_probe")

    final_rows = final_listing.get("jobs") or []
    root_final_rows = [
        row for row in final_rows if isinstance(row, dict) and _text(row.get("root_job_id")) == root_record["job_id"]
    ]
    final_job_ids = {_text(row.get("job_id")) for row in final_rows if isinstance(row, dict)}
    root_final_job_ids = {_text(row.get("job_id")) for row in root_final_rows}
    listed_progress_fields_present = all(
        isinstance(row, dict)
        and _text(row.get("progress_state"))
        and _text(row.get("current_step"))
        and _text(row.get("worker_state"))
        and _text(row.get("queue_status"))
        and _text(row.get("retry_policy"))
        and "progress_percent" in row
        and "queue_position" in row
        and "max_retry_attempts" in row
        for row in final_rows
    )
    listed_status_progress_contract_ready = all(
        isinstance(row, dict)
        and row.get("progress_percent_range_valid") is True
        and row.get("status_progress_contract_ready") is True
        and 0.0 <= float(row.get("progress_percent") or 0.0) <= 100.0
        and int(row.get("max_retry_attempts") or 0) >= 3
        for row in final_rows
    )
    retry_child_attempt_created = (
        _text(retry_child.get("job_id")) == "job_orchestration_probe_1-retry-1"
        and _text(retry_child.get("retry_of_job_id")) == root_record["job_id"]
        and _text(retry_child.get("parent_job_id")) == root_record["job_id"]
        and int(retry_child.get("attempt_index") or 0) == 2
        and retry_history.get("event_count") >= 1
        and _text((retry_history.get("events") or [{}])[0].get("event_type")) == "retry_attempt_created"
    )
    idempotency_preserved = (
        _text(root_record.get("request_sha256"))
        and _text(retry_child.get("request_sha256")) == _text(root_record.get("request_sha256"))
        and _text(retry_child.get("idempotency_key")) == _text(root_record.get("idempotency_key"))
    )
    history_cancel_retry_semantics = (
        cancelled.get("cancel_recorded") is True
        and retry_child.get("retry_recorded") is True
        and root_history.get("event_count") == 3
        and [event.get("event_type") for event in root_history.get("events") or []] == [
            "created",
            "cancel_requested",
            "retry_requested",
        ]
    )
    listing_status_progress_ready = (
        initial_listing.get("job_count") == 1
        and final_listing.get("job_count") == 4
        and root_final_job_ids == {
            "job_orchestration_probe_1",
            "job_orchestration_probe_1-retry-1",
            "job_orchestration_probe_1-retry-2",
        }
        and "job_orchestration_probe_stale_1" in final_job_ids
        and listed_progress_fields_present
    )
    queue_lifecycle_progress_ready = (
        _text((initial_listing.get("jobs") or [{}])[0].get("queue_status")) == "queued_fail_closed"
        and _text(cancelled.get("queue_status")) == "cancel_requested_fail_closed"
        and cancelled.get("cancellable") is False
        and cancelled.get("retryable") is True
        and _text(root_history.get("queue_status")) == "retry_requested_fail_closed"
        and _text(retry_history.get("queue_status")) == "retry_requested_fail_closed"
        and _text(resumed_history.get("queue_status")) == "cancel_requested_fail_closed"
        and root_history.get("status_progress_contract_ready") is True
        and retry_history.get("status_progress_contract_ready") is True
        and resumed_history.get("status_progress_contract_ready") is True
        and listed_status_progress_contract_ready
        and root_history.get("progress_percent") == 0.0
        and retry_history.get("progress_percent") == 0.0
        and resumed_history.get("progress_percent") == 12.5
    )
    status_snapshot_persistence_ready = (
        all(isinstance(row, dict) and row.get("status_snapshot_persisted") is True for row in final_rows)
        and root_history.get("status_snapshot_persisted") is True
        and retry_history.get("status_snapshot_persisted") is True
        and _text((root_history.get("status_snapshot") or {}).get("status")) == "retry_requested_fail_closed"
        and retry_history.get("status_snapshot_persisted") is True
        and resumed_history.get("status_snapshot_persisted") is True
        and _text((retry_history.get("status_snapshot") or {}).get("status")) == "retry_requested_fail_closed"
        and _text((resumed_history.get("status_snapshot") or {}).get("status")) == "cancel_requested_fail_closed"
    )
    retention_policy_ready = (
        all(
            isinstance(row, dict)
            and _text(row.get("job_retention_policy")) == "local_job_ledger_retain_90_days_minimum"
            and int(row.get("job_retention_days") or 0) >= 90
            for row in final_rows
        )
        and int(root_history.get("job_retention_days") or 0) >= 90
        and int(retry_history.get("job_retention_days") or 0) >= 90
        and int(resumed_history.get("job_retention_days") or 0) >= 90
    )
    rerun_manifest_ready = (
        all(isinstance(row, dict) and row.get("rerun_manifest_ready") is True for row in final_rows)
        and root_history.get("rerun_manifest_ready") is True
        and retry_history.get("rerun_manifest_ready") is True
        and resumed_history.get("rerun_manifest_ready") is True
        and _text((root_history.get("rerun_manifest") or {}).get("request_sha256")) == _text(root_record.get("request_sha256"))
        and _text((retry_history.get("rerun_manifest") or {}).get("request_sha256")) == _text(root_record.get("request_sha256"))
        and "retry" in _text((root_history.get("rerun_manifest") or {}).get("rerun_command"))
    )
    long_running_status_persistence_ready = (
        all(
            isinstance(row, dict)
            and row.get("long_running_status_persistence_ready") is True
            and row.get("reproducible_rerun_ready") is True
            for row in final_rows
        )
        and root_history.get("long_running_status_persistence_ready") is True
        and retry_history.get("long_running_status_persistence_ready") is True
        and resumed_history.get("long_running_status_persistence_ready") is True
    )
    final_rows_have_customer_lineage = all(
        isinstance(row, dict)
        and _text(row.get("source_host")) == "contract-probe"
        and _text(row.get("customer_id")) == "customer_contract_probe"
        and _text(row.get("user_id")) == "user_contract_probe"
        and _text(row.get("root_job_id")) == root_record["job_id"]
        and int(row.get("root_attempt_count") or 0) == 3
        and isinstance(row.get("event_actors"), list)
        for row in root_final_rows
    )
    customer_run_history_ready = (
        final_rows_have_customer_lineage
        and len(root_final_rows) == 3
        and source_filtered_listing.get("job_count") == 4
        and root_filtered_listing.get("job_count") == 3
        and customer_filtered_listing.get("job_count") == 4
        and user_filtered_listing.get("job_count") == 4
        and _text(root_history.get("source_host")) == "contract-probe"
        and _text(root_history.get("customer_id")) == "customer_contract_probe"
        and _text(root_history.get("user_id")) == "user_contract_probe"
        and _text(root_history.get("root_job_id")) == root_record["job_id"]
        and _text(retry_history.get("customer_id")) == "customer_contract_probe"
        and _text(retry_history.get("user_id")) == "user_contract_probe"
        and _text(retry_history.get("root_job_id")) == root_record["job_id"]
        and _text((root_history.get("rerun_manifest") or {}).get("customer_id")) == "customer_contract_probe"
        and _text((root_history.get("rerun_manifest") or {}).get("user_id")) == "user_contract_probe"
        and "contract-probe" in (root_history.get("event_actors") or [])
        and "contract-probe" in (retry_history.get("event_actors") or [])
        and "contract-probe-worker" in (retry_history.get("event_actors") or [])
        and "contract-probe-worker" in (resumed_history.get("event_actors") or [])
    )
    worker_lease_heartbeat_ready = (
        leased.get("worker_lease_acquired") is True
        and _text(leased.get("worker_lease_id"))
        and heartbeat.get("heartbeat_recorded") is True
        and heartbeat.get("progress_percent") == 37.5
        and _text(heartbeat.get("worker_state")) == "active_fail_closed"
        and _text(heartbeat.get("queue_status")) == "worker_lease_active_fail_closed"
        and heartbeat.get("status_progress_contract_ready") is True
        and bool(_text(heartbeat.get("heartbeat_at_utc")))
    )
    retryable_failure_resume_ready = (
        failed.get("failure_recorded") is True
        and _text(failed.get("status")) == "failed_fail_closed"
        and failed.get("retryable") is True
        and _text(resumed_child.get("job_id")) == "job_orchestration_probe_1-retry-2"
        and _text(resumed_child.get("retry_of_job_id")) == root_record["job_id"]
        and _text(resumed_child.get("parent_job_id")) == retry_child.get("job_id")
        and int(resumed_child.get("attempt_index") or 0) == 3
        and _text(resumed_child.get("request_sha256")) == _text(root_record.get("request_sha256"))
    )
    running_cancel_ack_ready = (
        cancel_lease.get("worker_lease_acquired") is True
        and cancel_heartbeat.get("heartbeat_recorded") is True
        and cancel_requested.get("cancel_recorded") is True
        and cancel_ack.get("worker_cancel_acknowledged") is True
        and _text(cancel_ack.get("worker_state")) == "cancel_acknowledged_fail_closed"
        and cancel_ack.get("status_progress_contract_ready") is True
        and cancel_ack.get("retryable") is True
    )
    stale_worker_lease_recovery_ready = (
        stale_lease.get("worker_lease_acquired") is True
        and stale_sweep.get("stale_worker_lease_sweep_ready") is True
        and stale_sweep.get("stale_worker_lease_detected_count") == 1
        and stale_sweep.get("stale_worker_lease_updated_count") == 1
        and stale_sweep.get("retryable_after_stale_count") == 1
        and _text(stale_history.get("status")) == "failed_fail_closed"
        and stale_history.get("retryable") is True
        and stale_history.get("stale_worker_lease_detected") is True
        and stale_history.get("status_progress_contract_ready") is True
        and _text((stale_history.get("events") or [{}])[-1].get("event_type")) == "worker_lease_stale"
    )
    worker_backend_contract_ready = (
        worker_lease_heartbeat_ready
        and retryable_failure_resume_ready
        and running_cancel_ack_ready
        and stale_worker_lease_recovery_ready
    )
    records_fail_closed = _all_events_fail_closed(
        [
            root_record,
            cancelled,
            retry_child,
            leased,
            heartbeat,
            failed,
            resumed_child,
            cancel_lease,
            cancel_heartbeat,
            cancel_requested,
            cancel_ack,
            stale_root,
            stale_lease,
            stale_history,
        ]
    )

    checks = [
        _check(
            "intake_ledger_created",
            "ready" if root_record.get("status") == "accepted_fail_closed" and _text(root_record.get("idempotency_key")) else "blocked",
            f"status={root_record.get('status')};idempotency_key_present={bool(_text(root_record.get('idempotency_key')))}",
            "valid product request creates a fail-closed local ledger row with request hash and idempotency key",
            "Repair docking request ledger creation before claiming job intake readiness.",
        ),
        _check(
            "history_cancel_retry_routes_semantics",
            "ready" if history_cancel_retry_semantics else "blocked",
            f"root_event_count={root_history.get('event_count')};cancel_recorded={cancelled.get('cancel_recorded')};retry_recorded={retry_child.get('retry_recorded')}",
            "history records created, cancel_requested, and retry_requested events without execution",
            "Repair cancel/retry event history before exposing orchestration as a durable product surface.",
        ),
        _check(
            "retry_attempt_reproducibility",
            "ready" if retry_child_attempt_created and idempotency_preserved else "blocked",
            (
                f"retry_job_id={retry_child.get('job_id')};attempt_index={retry_child.get('attempt_index')};"
                f"idempotency_preserved={idempotency_preserved}"
            ),
            "retry creates a child attempt with parent/root ids, incremented attempt index, and preserved request hash",
            "Create durable retry-child records before claiming reproducible rerun support.",
        ),
        _check(
            "job_listing_status_progress",
            "ready" if listing_status_progress_ready else "blocked",
            f"initial_job_count={initial_listing.get('job_count')};final_job_count={final_listing.get('job_count')};progress_fields_present={listed_progress_fields_present}",
            "job listing exposes root and retry child with status, attempt, idempotency, progress, step, and worker state",
            "Expose progress and attempt metadata in job list/status before closing orchestration.",
        ),
        _check(
            "queue_lifecycle_progress_contract",
            "ready" if queue_lifecycle_progress_ready else "blocked",
            (
                f"initial_queue_status={(initial_listing.get('jobs') or [{}])[0].get('queue_status')};"
                f"cancel_queue_status={cancelled.get('queue_status')};"
                f"root_queue_status={root_history.get('queue_status')};"
                f"retry_queue_status={retry_history.get('queue_status')};"
                f"listed_status_progress_contract_ready={listed_status_progress_contract_ready}"
            ),
            "intake, cancel, root retry request, and retry child expose consistent queue status, progress range, and retry/cancel policy",
            "Repair queue lifecycle and status-progress invariants before claiming product-grade job orchestration.",
        ),
        _check(
            "customer_run_history_lineage",
            "ready" if customer_run_history_ready else "blocked",
            (
                f"source_filtered_job_count={source_filtered_listing.get('job_count')};"
                f"root_filtered_job_count={root_filtered_listing.get('job_count')};"
                f"customer_filtered_job_count={customer_filtered_listing.get('job_count')};"
                f"user_filtered_job_count={user_filtered_listing.get('job_count')};"
                f"final_rows_have_customer_lineage={final_rows_have_customer_lineage};"
                f"root_history_source_host={root_history.get('source_host')};"
                f"root_history_customer_id={root_history.get('customer_id')};"
                f"root_history_user_id={root_history.get('user_id')};"
                f"retry_history_root_job_id={retry_history.get('root_job_id')}"
            ),
            "job listing and history expose source_host/customer/user filters, root_job_id lineage, root attempt count, and event actors",
            "Expose customer/run-history lineage before claiming product-grade job orchestration.",
        ),
        _check(
            "durable_status_retention_rerun_manifest",
            (
                "ready"
                if status_snapshot_persistence_ready
                and retention_policy_ready
                and rerun_manifest_ready
                and long_running_status_persistence_ready
                else "blocked"
            ),
            (
                f"status_snapshot_persistence_ready={status_snapshot_persistence_ready};"
                f"retention_policy_ready={retention_policy_ready};"
                f"rerun_manifest_ready={rerun_manifest_ready};"
                f"long_running_status_persistence_ready={long_running_status_persistence_ready};"
                f"root_retention_days={root_history.get('job_retention_days')};"
                f"retry_retention_days={retry_history.get('job_retention_days')}"
            ),
            "job list/history expose persisted status snapshots, >=90 day local retention policy, rerun manifest, and long-running status persistence flags",
            "Persist status snapshots, retention policy, and rerun manifests before claiming durable long-running job orchestration.",
        ),
        _check(
            "worker_lease_heartbeat_contract",
            "ready" if worker_lease_heartbeat_ready else "blocked",
            (
                f"worker_lease_acquired={leased.get('worker_lease_acquired')};"
                f"worker_lease_id_present={bool(_text(leased.get('worker_lease_id')))};"
                f"heartbeat_recorded={heartbeat.get('heartbeat_recorded')};"
                f"heartbeat_progress={heartbeat.get('progress_percent')};"
                f"heartbeat_queue_status={heartbeat.get('queue_status')};"
                f"heartbeat_status_progress_contract_ready={heartbeat.get('status_progress_contract_ready')}"
            ),
            "worker lease and heartbeat update persisted status/progress without emitting docking results",
            "Add worker lease and heartbeat semantics before claiming product-grade long-running jobs.",
        ),
        _check(
            "retryable_failure_resume_contract",
            "ready" if retryable_failure_resume_ready else "blocked",
            (
                f"failure_recorded={failed.get('failure_recorded')};"
                f"failed_status={failed.get('status')};"
                f"failed_retryable={failed.get('retryable')};"
                f"resumed_job_id={resumed_child.get('job_id')};"
                f"resumed_attempt_index={resumed_child.get('attempt_index')};"
                f"resumed_parent_job_id={resumed_child.get('parent_job_id')}"
            ),
            "retryable worker failure can create a reproducible child attempt preserving request identity",
            "Add retryable failure and resume-child semantics before claiming durable recovery.",
        ),
        _check(
            "running_cancel_ack_contract",
            "ready" if running_cancel_ack_ready else "blocked",
            (
                f"running_lease_acquired={cancel_lease.get('worker_lease_acquired')};"
                f"running_heartbeat_recorded={cancel_heartbeat.get('heartbeat_recorded')};"
                f"cancel_recorded={cancel_requested.get('cancel_recorded')};"
                f"worker_cancel_acknowledged={cancel_ack.get('worker_cancel_acknowledged')};"
                f"cancel_ack_worker_state={cancel_ack.get('worker_state')};"
                f"cancel_ack_retryable={cancel_ack.get('retryable')}"
            ),
            "running job cancel request has a persisted worker acknowledgment and retryable terminal state",
            "Add cancel acknowledgment semantics before exposing cancellation as product-grade orchestration.",
        ),
        _check(
            "stale_worker_lease_recovery_contract",
            "ready" if stale_worker_lease_recovery_ready else "blocked",
            (
                f"stale_lease_acquired={stale_lease.get('worker_lease_acquired')};"
                f"sweep_ready={stale_sweep.get('stale_worker_lease_sweep_ready')};"
                f"stale_detected_count={stale_sweep.get('stale_worker_lease_detected_count')};"
                f"stale_updated_count={stale_sweep.get('stale_worker_lease_updated_count')};"
                f"retryable_after_stale_count={stale_sweep.get('retryable_after_stale_count')};"
                f"stale_history_status={stale_history.get('status')};"
                f"stale_history_retryable={stale_history.get('retryable')};"
                f"stale_status_progress_contract_ready={stale_history.get('status_progress_contract_ready')}"
            ),
            "stale worker leases are detected by timeout, marked failed fail-closed, and left retryable without execution",
            "Add stale lease timeout recovery before claiming robust worker orchestration.",
        ),
        _check(
            "fail_closed_no_execution",
            "ready" if records_fail_closed else "blocked",
            f"records_fail_closed={records_fail_closed};docking_results_emitted=False;external_state_mutated=False",
            "ledger probe never executes docking, emits scientific results, or mutates external state",
            "Keep orchestration contract separate from worker execution until an explicit worker gate exists.",
        ),
    ]
    ready_checks = [row for row in checks if row["status"] == "ready"]
    blocked_checks = [row for row in checks if row["status"] != "ready"]
    contract_ready = not blocked_checks
    summary = {
        "packet_type": "product_job_orchestration_contract",
        "status": "product_job_orchestration_contract_ready" if contract_ready else "blocked_product_job_orchestration_contract",
        "product_job_orchestration_contract_ready": contract_ready,
        "check_count": len(checks),
        "ready_check_count": len(ready_checks),
        "blocked_check_count": len(blocked_checks),
        "blocked_checks": [row["check_id"] for row in blocked_checks],
        "retry_child_attempt_created": retry_child_attempt_created,
        "idempotency_preserved": idempotency_preserved,
        "progress_fields_present": listed_progress_fields_present,
        "listed_status_progress_contract_ready": listed_status_progress_contract_ready,
        "queue_lifecycle_progress_ready": queue_lifecycle_progress_ready,
        "customer_run_history_lineage_ready": customer_run_history_ready,
        "status_snapshot_persistence_ready": status_snapshot_persistence_ready,
        "retention_policy_ready": retention_policy_ready,
        "rerun_manifest_ready": rerun_manifest_ready,
        "long_running_status_persistence_ready": long_running_status_persistence_ready,
        "worker_backend_contract_ready": worker_backend_contract_ready,
        "worker_lease_heartbeat_ready": worker_lease_heartbeat_ready,
        "retryable_failure_resume_ready": retryable_failure_resume_ready,
        "running_cancel_ack_ready": running_cancel_ack_ready,
        "stale_worker_lease_recovery_ready": stale_worker_lease_recovery_ready,
        "stale_worker_lease_sweep_ready": bool(stale_sweep.get("stale_worker_lease_sweep_ready") is True),
        "stale_worker_lease_detected_count": int(stale_sweep.get("stale_worker_lease_detected_count") or 0),
        "stale_worker_lease_updated_count": int(stale_sweep.get("stale_worker_lease_updated_count") or 0),
        "retryable_after_stale_count": int(stale_sweep.get("retryable_after_stale_count") or 0),
        "stale_worker_lease_timeout_seconds": int(stale_sweep.get("lease_timeout_seconds") or 0),
        "job_retention_days": 90,
        "source_host_filter_job_count": int(source_filtered_listing.get("job_count") or 0),
        "root_job_id_filter_job_count": int(root_filtered_listing.get("job_count") or 0),
        "customer_id_filter_job_count": int(customer_filtered_listing.get("job_count") or 0),
        "user_id_filter_job_count": int(user_filtered_listing.get("job_count") or 0),
        "lineage_customer_id": "customer_contract_probe" if customer_run_history_ready else "",
        "lineage_user_id": "user_contract_probe" if customer_run_history_ready else "",
        "root_attempt_count_after_retry": 3 if final_rows_have_customer_lineage else 0,
        "history_event_count": int(root_history.get("event_count") or 0),
        "job_count_after_retry": len(root_final_rows),
        "job_count_after_stale_probe": int(final_listing.get("job_count") or 0),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Attach this job orchestration contract to the AI architecture gap closure gate."
            if contract_ready
            else "Repair blocked job orchestration checks before closing durable job orchestration."
        ),
    }
    return {"summary": summary, "rows": checks}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Job Orchestration Contract",
        "",
        f"- status: `{s['status']}`",
        f"- product_job_orchestration_contract_ready: `{s['product_job_orchestration_contract_ready']}`",
        f"- ready_check_count: `{s['ready_check_count']}` / `{s['check_count']}`",
        f"- retry_child_attempt_created: `{s['retry_child_attempt_created']}`",
        f"- idempotency_preserved: `{s['idempotency_preserved']}`",
        f"- progress_fields_present: `{s['progress_fields_present']}`",
        f"- listed_status_progress_contract_ready: `{s['listed_status_progress_contract_ready']}`",
        f"- queue_lifecycle_progress_ready: `{s['queue_lifecycle_progress_ready']}`",
        f"- customer_run_history_lineage_ready: `{s['customer_run_history_lineage_ready']}`",
        f"- status_snapshot_persistence_ready: `{s['status_snapshot_persistence_ready']}`",
        f"- retention_policy_ready: `{s['retention_policy_ready']}`",
        f"- rerun_manifest_ready: `{s['rerun_manifest_ready']}`",
        f"- long_running_status_persistence_ready: `{s['long_running_status_persistence_ready']}`",
        f"- worker_backend_contract_ready: `{s['worker_backend_contract_ready']}`",
        f"- worker_lease_heartbeat_ready: `{s['worker_lease_heartbeat_ready']}`",
        f"- retryable_failure_resume_ready: `{s['retryable_failure_resume_ready']}`",
        f"- running_cancel_ack_ready: `{s['running_cancel_ack_ready']}`",
        f"- stale_worker_lease_recovery_ready: `{s['stale_worker_lease_recovery_ready']}`",
        f"- stale_worker_lease_detected_count: `{s['stale_worker_lease_detected_count']}`",
        f"- retryable_after_stale_count: `{s['retryable_after_stale_count']}`",
        f"- job_retention_days: `{s['job_retention_days']}`",
        f"- source_host_filter_job_count: `{s['source_host_filter_job_count']}`",
        f"- root_job_id_filter_job_count: `{s['root_job_id_filter_job_count']}`",
        f"- customer_id_filter_job_count: `{s['customer_id_filter_job_count']}`",
        f"- user_id_filter_job_count: `{s['user_id_filter_job_count']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | next action |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | {row['next_action']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Required Step", "", f"- {s['next_required_step']}", ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product job orchestration ledger contract evidence.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_job_orchestration_contract()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
