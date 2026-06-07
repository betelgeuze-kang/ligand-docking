from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_job_orchestration_contract as mod


def test_product_job_orchestration_contract_ready() -> None:
    payload = mod.build_product_job_orchestration_contract()

    summary = payload["summary"]
    assert summary["status"] == "product_job_orchestration_contract_ready"
    assert summary["product_job_orchestration_contract_ready"] is True
    assert summary["ready_check_count"] == summary["check_count"]
    assert summary["retry_child_attempt_created"] is True
    assert summary["idempotency_preserved"] is True
    assert summary["progress_fields_present"] is True
    assert summary["listed_status_progress_contract_ready"] is True
    assert summary["queue_lifecycle_progress_ready"] is True
    assert summary["customer_run_history_lineage_ready"] is True
    assert summary["status_snapshot_persistence_ready"] is True
    assert summary["retention_policy_ready"] is True
    assert summary["rerun_manifest_ready"] is True
    assert summary["long_running_status_persistence_ready"] is True
    assert summary["worker_backend_contract_ready"] is True
    assert summary["worker_lease_heartbeat_ready"] is True
    assert summary["retryable_failure_resume_ready"] is True
    assert summary["running_cancel_ack_ready"] is True
    assert summary["stale_worker_lease_recovery_ready"] is True
    assert summary["stale_worker_lease_sweep_ready"] is True
    assert summary["stale_worker_lease_detected_count"] == 1
    assert summary["stale_worker_lease_updated_count"] == 1
    assert summary["retryable_after_stale_count"] == 1
    assert summary["stale_worker_lease_timeout_seconds"] == 1800
    assert summary["job_retention_days"] == 90
    assert summary["source_host_filter_job_count"] == 4
    assert summary["root_job_id_filter_job_count"] == 3
    assert summary["customer_id_filter_job_count"] == 4
    assert summary["user_id_filter_job_count"] == 4
    assert summary["lineage_customer_id"] == "customer_contract_probe"
    assert summary["lineage_user_id"] == "user_contract_probe"
    assert summary["root_attempt_count_after_retry"] == 3
    assert summary["history_event_count"] == 3
    assert summary["job_count_after_retry"] == 3
    assert summary["job_count_after_stale_probe"] == 4
    assert {row["check_id"] for row in payload["rows"]} == {
        "intake_ledger_created",
        "history_cancel_retry_routes_semantics",
        "retry_attempt_reproducibility",
        "job_listing_status_progress",
        "queue_lifecycle_progress_contract",
        "customer_run_history_lineage",
        "durable_status_retention_rerun_manifest",
        "worker_lease_heartbeat_contract",
        "retryable_failure_resume_contract",
        "running_cancel_ack_contract",
        "stale_worker_lease_recovery_contract",
        "fail_closed_no_execution",
    }
    lineage = next(row for row in payload["rows"] if row["check_id"] == "customer_run_history_lineage")
    assert "source_filtered_job_count=4" in lineage["observed"]
    assert "root_filtered_job_count=3" in lineage["observed"]
    assert "customer_filtered_job_count=4" in lineage["observed"]
    assert "user_filtered_job_count=4" in lineage["observed"]
    assert "root_history_customer_id=customer_contract_probe" in lineage["observed"]
    assert "root_history_user_id=user_contract_probe" in lineage["observed"]
    durable = next(row for row in payload["rows"] if row["check_id"] == "durable_status_retention_rerun_manifest")
    assert "status_snapshot_persistence_ready=True" in durable["observed"]
    assert "rerun_manifest_ready=True" in durable["observed"]
    lifecycle = next(row for row in payload["rows"] if row["check_id"] == "queue_lifecycle_progress_contract")
    assert "initial_queue_status=queued_fail_closed" in lifecycle["observed"]
    assert "listed_status_progress_contract_ready=True" in lifecycle["observed"]
    worker = next(row for row in payload["rows"] if row["check_id"] == "worker_lease_heartbeat_contract")
    assert "heartbeat_recorded=True" in worker["observed"]
    resume = next(row for row in payload["rows"] if row["check_id"] == "retryable_failure_resume_contract")
    assert "resumed_job_id=job_orchestration_probe_1-retry-2" in resume["observed"]
    cancel = next(row for row in payload["rows"] if row["check_id"] == "running_cancel_ack_contract")
    assert "worker_cancel_acknowledged=True" in cancel["observed"]
    stale = next(row for row in payload["rows"] if row["check_id"] == "stale_worker_lease_recovery_contract")
    assert "stale_detected_count=1" in stale["observed"]
    assert "retryable_after_stale_count=1" in stale["observed"]
    assert "stale_history_status=failed_fail_closed" in stale["observed"]


def test_product_job_orchestration_contract_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "job_orchestration.json"
    out_csv = tmp_path / "job_orchestration.csv"
    out_md = tmp_path / "job_orchestration.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["product_job_orchestration_contract_ready"] is True
    assert payload["summary"]["rerun_manifest_ready"] is True
    assert payload["summary"]["queue_lifecycle_progress_ready"] is True
    assert payload["summary"]["worker_backend_contract_ready"] is True
    assert payload["summary"]["stale_worker_lease_recovery_ready"] is True
    assert "retry_attempt_reproducibility" in out_csv.read_text(encoding="utf-8")
    md = out_md.read_text(encoding="utf-8")
    assert "Product Job Orchestration Contract" in md
    assert "status_snapshot_persistence_ready" in md
    assert "queue_lifecycle_progress_ready" in md
    assert "worker_backend_contract_ready" in md
    assert "stale_worker_lease_recovery_ready" in md
    assert "customer_id_filter_job_count" in md
