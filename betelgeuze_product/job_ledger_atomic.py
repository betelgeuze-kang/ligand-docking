from __future__ import annotations

from pathlib import Path
from typing import Any

from betelgeuze_product.atomic_io import atomic_write_json
from betelgeuze_product.payload_privacy import sanitize_request_for_ledger


def atomic_write_job_record(jobs_dir: Path, record: dict[str, Any]) -> Path:
    job_id = str(record.get("job_id") or "").strip()
    if not job_id:
        raise ValueError("job ledger record requires job_id")
    path = Path(jobs_dir) / f"{job_id}.json"
    return atomic_write_json(
        path,
        sanitize_request_for_ledger(record),
        mode=0o600,
    )


def install_atomic_job_ledger_writes() -> None:
    """Install atomic persistence for all orchestration functions in-process.

    The orchestration functions resolve ``write_job_record`` from their module
    globals at call time, so replacing that single global upgrades cancel,
    retry, lease, heartbeat, failure, and stale-lease writes together.
    """

    from betelgeuze_product import job_orchestration

    job_orchestration.write_job_record = atomic_write_job_record
