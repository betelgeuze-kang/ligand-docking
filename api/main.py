# api/main.py

from typing import Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
import uuid
import os
import json
from api.cameo import router as cameo_router
from api.casp17 import router as casp17_router
from api.cleanup import router as cleanup_router
from api.goal import router as goal_router
from api.product import router as product_router
from api.models import SimulationRequest, SimulationResponse, StatusResponse, ResultsResponse
from api.tasks import run_simulation_async
from api.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(cameo_router)
app.include_router(casp17_router)
app.include_router(cleanup_router)
app.include_router(goal_router)
app.include_router(product_router)

# In-memory job store (use Redis or DB for production)
jobs = {}


def _model_to_dict(model: SimulationRequest) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()

@app.post("/simulate", response_model=SimulationResponse)
async def submit_simulation(request: SimulationRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    request_data = _model_to_dict(request)
    jobs[job_id] = {"status": "submitted", "request": request_data}

    # Create status file
    results_dir = os.path.join(settings.results_storage_path, job_id)
    os.makedirs(results_dir, exist_ok=True)
    status_file_path = os.path.join(results_dir, "status.json")
    with open(status_file_path, 'w') as sf:
        json.dump({"job_id": job_id, "status": "submitted"}, sf)

    # Add background task to run simulation
    background_tasks.add_task(run_simulation_async_wrapper, job_id, request_data)

    return SimulationResponse(job_id=job_id, status="submitted", message="Simulation submitted successfully.")

async def run_simulation_async_wrapper(job_id: str, request_data: dict[str, Any]):
    """Wrapper to handle the async task and update job status."""
    jobs[job_id]["status"] = "running"
    try:
        await run_simulation_async(job_id, request_data)
        # Status is updated within run_simulation_async
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        # Status is also updated in run_simulation_async on failure

@app.get("/status/{job_id}", response_model=StatusResponse)
def get_simulation_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    # Read status from file
    results_dir = os.path.join(settings.results_storage_path, job_id)
    status_file_path = os.path.join(results_dir, "status.json")
    if not os.path.exists(status_file_path):
        return StatusResponse(job_id=job_id, status="unknown", message="Status file missing")

    with open(status_file_path, 'r') as sf:
        status_data = json.load(sf)

    return StatusResponse(
        job_id=job_id,
        status=status_data.get("status", "unknown"),
        message=status_data.get("error", "Running...")
    )

@app.get("/results/{job_id}", response_model=ResultsResponse)
def get_simulation_results(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    results_dir = os.path.join(settings.results_storage_path, job_id)
    status_file_path = os.path.join(results_dir, "status.json")
    if not os.path.exists(status_file_path):
        raise HTTPException(status_code=404, detail="Results not ready or job failed")

    with open(status_file_path, 'r') as sf:
        status_data = json.load(sf)

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
