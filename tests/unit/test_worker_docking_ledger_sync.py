from __future__ import annotations

import json
from pathlib import Path

from api import worker


def test_docking_ledger_sync_skips_non_docking_requests() -> None:
    outcome = worker._sync_docking_ledger_if_needed(
        job_id="job-1",
        request_data={"runner_profile_params": {}},
        status="completed",
    )

    assert outcome == {"sync_attempted": False, "reason": "docking_job_id_missing"}


def test_docking_ledger_sync_records_redacted_exception(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import api.docking_dispatch as docking_dispatch

    def _raise_sync_error(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("sync failure detail should not be copied into status")

    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path))
    monkeypatch.setattr(docking_dispatch, "sync_ledger_from_simulation_result", _raise_sync_error)

    outcome = worker._sync_docking_ledger_if_needed(
        job_id="job-1",
        request_data={"runner_profile_params": {"docking_job_id": "dock-1"}},
        status="failed",
        error="runner failed",
        worker_id="worker-1",
    )

    serialized = json.dumps(outcome, sort_keys=True)
    assert outcome["sync_attempted"] is True
    assert outcome["synced"] is False
    assert outcome["reason"] == "ledger_sync_exception"
    assert outcome["error"]["redacted"] is True
    assert outcome["error"]["exception_type"] == "RuntimeError"
    assert "sync failure detail" not in serialized
