# api/tasks.py

import json
import os
from typing import Any

from api.config import settings
from api.job_artifacts import (
    atomic_write_text_file,
    resolve_job_results_dir,
)
from api.simulation_scope import UnsupportedSimulationScopeError, validate_simulation_request_scope
from api.validated_runner import execute_validated_runner_profile

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
        if request_data.get("runner_profile_id"):
            await execute_validated_runner_profile(
                job_id,
                request_data,
                require_customer_submission_allowed=True,
            )
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
