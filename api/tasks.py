# api/tasks.py

import json
import os
from typing import Any

from api.config import settings
from api.simulation_scope import (
    PRODUCT_SIMULATION_SCOPE,
    UnsupportedSimulationScopeError,
    validate_simulation_request_scope,
)
from api.validated_runner import execute_validated_runner_profile
from betelgeuze_product.tier_beta_vertical_slice import (
    is_tier_beta_vertical_slice_request,
    run_tier_beta_vertical_slice_job,
)

async def run_simulation_async(job_id: str, request_data: dict[str, Any]):
    """
    Asynchronously run a simulation task.
    This function should be called by the API endpoint.
    """
    results_dir = os.path.join(settings.results_storage_path, job_id)
    os.makedirs(results_dir, exist_ok=True)
    status_file_path = os.path.join(results_dir, "status.json")
    try:
        validate_simulation_request_scope(request_data)
        if is_tier_beta_vertical_slice_request(request_data):
            run_tier_beta_vertical_slice_job(
                job_id=job_id,
                request_data=request_data,
                results_dir=results_dir,
            )
            return
        if request_data.get("runner_profile_id"):
            await execute_validated_runner_profile(job_id, request_data)
            return

        raise UnsupportedSimulationScopeError(
            "runner_profile_id is required for all /simulate jobs.",
            product_scope=PRODUCT_SIMULATION_SCOPE,
        )

    except Exception as e:
        # Update status to failed without leaking raw request data.
        with open(status_file_path, "w", encoding="utf-8") as sf:
            json.dump({"job_id": job_id, "status": "failed", "error": str(e)}, sf)
        print(f"Simulation {job_id} failed: {e}")
        raise
