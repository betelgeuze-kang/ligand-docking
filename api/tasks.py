# api/tasks.py

import json
import os
from typing import Any

from api.config import settings
from api.job_store import validate_job_id
from api.path_security import confined_path, normalize_tier_beta_request_paths
from api.simulation_scope import UnsupportedSimulationScopeError, validate_simulation_request_scope
from api.validated_runner import (
    EXECUTION_ORIGIN_CUSTOMER,
    authorize_runner_profile_execution,
    execute_validated_runner_profile,
)
from betelgeuze_product.tier_beta_vertical_slice import (
    is_tier_beta_vertical_slice_request,
    run_tier_beta_vertical_slice_job,
)

async def run_simulation_async(
    job_id: str,
    request_data: dict[str, Any],
    *,
    execution_origin: str = EXECUTION_ORIGIN_CUSTOMER,
):
    """
    Asynchronously run a simulation task.
    This function should be called by the API endpoint.
    """
    safe_job_id = validate_job_id(job_id)
    results_dir = str(
        confined_path(
            safe_job_id,
            settings.results_storage_path,
            label="job results directory",
        )
    )
    os.makedirs(results_dir, exist_ok=True)
    status_file_path = os.path.join(results_dir, "status.json")
    try:
        validate_simulation_request_scope(request_data)
        authorize_runner_profile_execution(
            request_data,
            execution_origin=execution_origin,
        )
        if is_tier_beta_vertical_slice_request(request_data):
            request_data = normalize_tier_beta_request_paths(
                request_data,
                local_paths_enabled=settings.product_api_local_path_inputs_enabled,
                input_root=settings.product_api_local_input_root,
            )
            run_tier_beta_vertical_slice_job(
                job_id=job_id,
                request_data=request_data,
                results_dir=results_dir,
                manifest_signing_key=settings.api_result_manifest_signing_key,
                manifest_signing_key_id=settings.api_result_manifest_key_id,
            )
            return
        if request_data.get("runner_profile_id"):
            await execute_validated_runner_profile(
                job_id,
                request_data,
                execution_origin=execution_origin,
            )
            return

        raise UnsupportedSimulationScopeError(
            "runner_profile_id is required for all /simulate jobs.",
            product_scope="validated ligand runner profiles",
        )

    except Exception as e:
        # Update status to failed
        with open(status_file_path, 'w') as sf:
            json.dump({"job_id": job_id, "status": "failed", "error": str(e)}, sf)
        print(f"Simulation {job_id} failed: {e}")
        raise e
