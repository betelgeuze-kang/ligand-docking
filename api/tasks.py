# api/tasks.py

import json
import os
import asyncio
from typing import Any
from pathlib import Path

from api.config import settings
from api.job_artifacts import (
    atomic_write_text_file,
    resolve_job_results_dir,
    sha256_current_attempt_file,
)
from api.simulation_scope import UnsupportedSimulationScopeError, validate_simulation_request_scope
from api.validated_runner import execute_validated_runner_profile
from betelgeuze_product.tier_beta_vertical_slice import (
    is_tier_beta_vertical_slice_request,
    run_tier_beta_vertical_slice_job,
)


def _write_pinned_tier_beta_artifact(path: Path, payload: str) -> None:
    atomic_write_text_file(path, payload)


def _hash_pinned_tier_beta_artifact(path: Path) -> str:
    digest = sha256_current_attempt_file(path)
    if digest is None:
        raise PermissionError("tier-beta API artifacts require a pinned worker attempt")
    return digest

async def run_simulation_async(job_id: str, request_data: dict[str, Any]):
    """
    Asynchronously run a simulation task.
    This function should be called by the API endpoint.
    """
    results_dir = str(resolve_job_results_dir(job_id, settings.results_storage_path))
    os.makedirs(results_dir, exist_ok=True)
    status_file_path = os.path.join(results_dir, "status.json")
    try:
        validate_simulation_request_scope(request_data)
        if is_tier_beta_vertical_slice_request(request_data):
            await asyncio.to_thread(
                run_tier_beta_vertical_slice_job,
                job_id=job_id,
                request_data=request_data,
                results_dir=results_dir,
                artifact_writer=_write_pinned_tier_beta_artifact,
                artifact_hasher=_hash_pinned_tier_beta_artifact,
            )
            return
        if request_data.get("runner_profile_id"):
            await execute_validated_runner_profile(job_id, request_data)
            return

        raise UnsupportedSimulationScopeError(
            "runner_profile_id is required for all /simulate jobs.",
        )

    except Exception as e:
        # Replace the directory entry atomically; never truncate a linked victim inode.
        atomic_write_text_file(
            status_file_path,
            json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}),
        )
        print(f"Simulation {job_id} failed: {e}")
        raise
