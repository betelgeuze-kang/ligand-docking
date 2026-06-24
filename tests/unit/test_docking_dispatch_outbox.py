from __future__ import annotations

from pathlib import Path

from api.docking_dispatch import reconcile_pending_dispatch_outbox
from api.docking_outbox import (
    OUTBOX_EVENT_TYPE,
    enqueue_job_with_outbox,
    get_outbox_event,
    pending_outbox_events,
)
from api.job_store import SQLiteJobStore
from betelgeuze_product.job_orchestration import read_job_record, write_job_record


def _request() -> dict:
    return {
        "runner_profile_id": "ligand_htvs.restricted-production",
        "target_name": "ADRB2",
        "runner_profile_params": {
            "docking_job_id": "job-outbox-1",
            "private_payload_ref": "opaque-private-payload-reference",
        },
    }


def _ledger(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "status": "accepted_fail_closed",
        "validation_status": "pass",
        "queue_status": "queued_fail_closed",
        "progress_percent": 0.0,
        "progress_state": "ledger_intake_recorded",
        "current_step": "contract_validation",
        "worker_state": "not_started_fail_closed",
        "worker_dispatch_enqueued": False,
        "event_history": [],
        "execution_enabled": False,
        "docking_results_emitted": False,
    }


def test_job_and_dispatch_event_are_created_idempotently(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    first = enqueue_job_with_outbox(
        store,
        job_id="job-outbox-1",
        request=_request(),
        event_payload={"job_id": "job-outbox-1"},
    )
    second = enqueue_job_with_outbox(
        store,
        job_id="job-outbox-1",
        request=_request(),
        event_payload={"job_id": "job-outbox-1"},
    )

    assert first["job_created"] is True
    assert first["outbox_created"] is True
    assert second["job_created"] is False
    assert second["outbox_created"] is False
    assert len(pending_outbox_events(store)) == 1
    event = get_outbox_event(store, first["event_id"])
    assert event is not None
    assert event["event_type"] == OUTBOX_EVENT_TYPE
    assert event["status"] == "pending"


def test_pending_dispatch_event_recovers_after_ledger_write_becomes_available(
    tmp_path: Path,
) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    jobs_dir = tmp_path / "ledgers"
    enqueued = enqueue_job_with_outbox(
        store,
        job_id="job-outbox-1",
        request=_request(),
        event_payload={"job_id": "job-outbox-1"},
    )

    first = reconcile_pending_dispatch_outbox(jobs_dir, store=store)
    failed_event = get_outbox_event(store, enqueued["event_id"])
    assert first == [
        {
            "event_id": enqueued["event_id"],
            "job_id": "job-outbox-1",
            "delivered": False,
            "error": "docking ledger record not found: job-outbox-1",
        }
    ]
    assert failed_event is not None
    assert failed_event["status"] == "retry_ready"
    assert failed_event["attempt_count"] == 1

    write_job_record(jobs_dir, _ledger("job-outbox-1"))
    second = reconcile_pending_dispatch_outbox(jobs_dir, store=store)
    delivered_event = get_outbox_event(store, enqueued["event_id"])
    ledger = read_job_record(jobs_dir, "job-outbox-1")

    assert second == [
        {
            "event_id": enqueued["event_id"],
            "job_id": "job-outbox-1",
            "delivered": True,
        }
    ]
    assert delivered_event is not None
    assert delivered_event["status"] == "delivered"
    assert delivered_event["delivered_at_utc"]
    assert ledger["worker_dispatch_enqueued"] is True
    assert ledger["progress_state"] == "worker_dispatch_enqueued"
    assert ledger["event_history"][-1]["event_type"] == "worker_dispatch_enqueued"
