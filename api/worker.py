from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import asyncio
import json
import os

from api.config import settings
from api.job_store import SQLiteJobStore
from api.result_manifest import write_result_manifest
from api.tasks import run_simulation_async

SimulationRunner = Callable[[str, dict[str, Any]], Awaitable[None]]


def _sync_docking_ledger_if_needed(
    *,
    job_id: str,
    request_data: dict[str, Any],
    status: str,
    result_file: str = "",
    error: str = "",
    worker_id: str = "",
) -> None:
    params = request_data.get("runner_profile_params", {})
    if not isinstance(params, dict):
        return
    docking_job_id = str(params.get("docking_job_id", "") or "").strip()
    if not docking_job_id:
        return
    try:
        from pathlib import Path

        from api.docking_dispatch import sync_ledger_from_simulation_result

        jobs_dir = Path(settings.results_storage_path) / "product_docking_jobs"
        sync_ledger_from_simulation_result(
            jobs_dir,
            docking_job_id,
            status=status,
            result_file=result_file,
            error=error,
            worker_id=worker_id,
        )
    except Exception:
        return


def job_results_dir(job_id: str) -> str:
    return os.path.join(settings.results_storage_path, job_id)


def job_status_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "status.json")


def job_manifest_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "result_manifest.json")


def read_status_file(status_file_path: str) -> dict[str, Any]:
    if not os.path.exists(status_file_path):
        return {}
    with open(status_file_path, "r", encoding="utf-8") as sf:
        return json.load(sf)


def write_status_file(status_file_path: str, status_data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(status_file_path), exist_ok=True)
    with open(status_file_path, "w", encoding="utf-8") as sf:
        json.dump(status_data, sf)


def write_job_result_manifest(
    *,
    job_id: str,
    request_data: dict[str, Any],
    status: str,
    result_file: str = "",
    error: str = "",
) -> str:
    manifest_path = job_manifest_path(job_id)
    write_result_manifest(
        manifest_path,
        job_id=job_id,
        request=request_data,
        status=status,
        result_file=result_file,
        error=error,
        signing_key=settings.api_result_manifest_signing_key,
        key_id=settings.api_result_manifest_key_id,
    )
    return manifest_path


async def run_job_once(
    store: SQLiteJobStore,
    *,
    job_id: str,
    request_data: dict[str, Any],
    runner: SimulationRunner = run_simulation_async,
    worker_id: str = "",
    lease_seconds: int = 300,
    heartbeat_interval_seconds: float | None = None,
    retry_on_failure: bool = False,
) -> dict[str, Any]:
    """Run one job and persist status, manifest, and retry state."""
    if worker_id:
        store.heartbeat_job(job_id, worker_id, lease_seconds=lease_seconds)
    else:
        store.update_job(job_id, status="running")

    status_file_path = job_status_path(job_id)
    status_data = read_status_file(status_file_path)
    status_data.update({"job_id": job_id, "status": "running"})
    write_status_file(status_file_path, status_data)

    try:
        if worker_id:
            await _run_with_periodic_heartbeat(
                store,
                job_id=job_id,
                worker_id=worker_id,
                runner=runner,
                request_data=request_data,
                lease_seconds=lease_seconds,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
            )
        else:
            await runner(job_id, request_data)
        status_data = read_status_file(status_file_path)
        result_file = str(status_data.get("result_file", "") or "")
        manifest_path = write_job_result_manifest(
            job_id=job_id,
            request_data=request_data,
            status="completed",
            result_file=result_file,
        )
        status_data.update({"job_id": job_id, "status": "completed", "result_manifest": manifest_path})
        write_status_file(status_file_path, status_data)
        _sync_docking_ledger_if_needed(
            job_id=job_id,
            request_data=request_data,
            status="completed",
            result_file=result_file,
            worker_id=worker_id,
        )
        return store.update_job(
            job_id,
            status="completed",
            result_file=result_file,
            result_manifest_path=manifest_path,
        )
    except Exception as exc:
        error = str(exc)
        _sync_docking_ledger_if_needed(
            job_id=job_id,
            request_data=request_data,
            status="failed",
            error=error,
            worker_id=worker_id,
        )
        if retry_on_failure and worker_id:
            released = store.release_job_for_retry(job_id, worker_id, error=error)
            if released is not None and released.get("status") == "retry_ready":
                status_data = read_status_file(status_file_path)
                status_data.update({"job_id": job_id, "status": "retry_ready", "error": error})
                write_status_file(status_file_path, status_data)
                return released

        manifest_path = write_job_result_manifest(
            job_id=job_id,
            request_data=request_data,
            status="failed",
            error=error,
        )
        status_data = read_status_file(status_file_path)
        status_data.update({"job_id": job_id, "status": "failed", "error": error, "result_manifest": manifest_path})
        write_status_file(status_file_path, status_data)
        return store.update_job(job_id, status="failed", error=error, result_manifest_path=manifest_path)


async def process_next_job_once(
    store: SQLiteJobStore,
    *,
    worker_id: str,
    runner: SimulationRunner = run_simulation_async,
    lease_seconds: int = 300,
    heartbeat_interval_seconds: float | None = None,
) -> dict[str, Any] | None:
    acquired = store.acquire_next_job(worker_id, lease_seconds=lease_seconds)
    if acquired is None:
        return None
    return await run_job_once(
        store,
        job_id=str(acquired["job_id"]),
        request_data=dict(acquired.get("request") or {}),
        runner=runner,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        retry_on_failure=True,
    )


async def _run_with_periodic_heartbeat(
    store: SQLiteJobStore,
    *,
    job_id: str,
    worker_id: str,
    runner: SimulationRunner,
    request_data: dict[str, Any],
    lease_seconds: int,
    heartbeat_interval_seconds: float | None,
) -> None:
    interval = heartbeat_interval_seconds
    if interval is None:
        interval = max(1.0, min(float(lease_seconds) / 3.0, float(settings.api_worker_heartbeat_interval_seconds)))

    runner_task = asyncio.create_task(runner(job_id, request_data))
    try:
        while True:
            try:
                await asyncio.wait_for(asyncio.shield(runner_task), timeout=max(0.05, float(interval)))
                return
            except (TimeoutError, asyncio.TimeoutError):
                store.heartbeat_job(job_id, worker_id, lease_seconds=lease_seconds)
    finally:
        if not runner_task.done():
            runner_task.cancel()
