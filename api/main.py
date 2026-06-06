# api/main.py

from typing import Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
import uuid
import os
from api.cameo import router as cameo_router
from api.casp17 import router as casp17_router
from api.cleanup import router as cleanup_router
from api.goal import router as goal_router
from api.product import router as product_router
from api.models import SimulationRequest, SimulationResponse, StatusResponse, ResultsResponse
from api.simulation_scope import (
    PRODUCT_SIMULATION_SCOPE,
    UnsupportedSimulationScopeError,
    validate_simulation_request_scope,
)
from api.tasks import run_simulation_async
from api.config import settings
from api.job_store import SQLiteJobStore
from api.security import ProductSecurityMiddleware, security_metrics_text
from api.worker import (
    job_results_dir,
    job_status_path,
    process_next_job_once,
    read_status_file,
    run_job_once,
    write_status_file,
)

app = FastAPI(title=settings.app_name)
app.add_middleware(ProductSecurityMiddleware)
app.include_router(cameo_router)
app.include_router(casp17_router)
app.include_router(cleanup_router)
app.include_router(goal_router)
app.include_router(product_router)

job_store = SQLiteJobStore(settings.api_job_store_path)


@app.get("/metrics", response_class=PlainTextResponse)
def get_metrics() -> str:
    return security_metrics_text()


def _model_to_dict(model: SimulationRequest) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.post("/simulate", response_model=SimulationResponse)
async def submit_simulation(request: SimulationRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    request_data = _model_to_dict(request)
    try:
        validate_simulation_request_scope(request_data)
    except UnsupportedSimulationScopeError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_simulation_scope",
                "message": str(exc),
                "product_scope": exc.product_scope or PRODUCT_SIMULATION_SCOPE,
            },
        ) from exc

    job_store.create_job(job_id, request_data, status="submitted")

    # Create status file
    results_dir = job_results_dir(job_id)
    os.makedirs(results_dir, exist_ok=True)
    status_file_path = job_status_path(job_id)
    write_status_file(status_file_path, {"job_id": job_id, "status": "submitted"})

    if settings.api_inline_worker_enabled:
        background_tasks.add_task(
            process_next_job_once,
            job_store,
            worker_id=f"api-inline-{job_id}",
            runner=run_simulation_async,
            lease_seconds=settings.api_worker_lease_seconds,
        )

    return SimulationResponse(
        job_id=job_id,
        status="submitted",
        message=(
            "Validated ligand runner job submitted. Product scope: "
            f"{PRODUCT_SIMULATION_SCOPE}."
        ),
    )

async def run_simulation_async_wrapper(job_id: str, request_data: dict[str, Any]):
    """Wrapper to handle the async task and update job status."""
    return await run_job_once(
        job_store,
        job_id=job_id,
        request_data=request_data,
        runner=run_simulation_async,
        lease_seconds=settings.api_worker_lease_seconds,
    )

@app.get("/status/{job_id}", response_model=StatusResponse)
def get_simulation_status(job_id: str):
    if not job_store.job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    # Read status from file
    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        return StatusResponse(job_id=job_id, status="unknown", message="Status file missing")

    status_data = read_status_file(status_file_path)

    return StatusResponse(
        job_id=job_id,
        status=status_data.get("status", "unknown"),
        message=status_data.get("error", "Running...")
    )

@app.get("/results/{job_id}", response_model=ResultsResponse)
def get_simulation_results(job_id: str):
    if not job_store.job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        raise HTTPException(status_code=404, detail="Results not ready or job failed")

    status_data = read_status_file(status_file_path)

    if status_data["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed. Status: {status_data['status']}")

    result_file = status_data.get("result_file")
    if not result_file or not os.path.exists(result_file):
        raise HTTPException(status_code=404, detail="Result file not found")

    # Return the result file
    return FileResponse(result_file, media_type='chemical/x-pdb', filename=os.path.basename(result_file))
    # Or return a ResultsResponse object with a download link if serving via URL is preferred
    # return ResultsResponse(job_id=job_id, status="completed", result_url=f"/download/{job_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
