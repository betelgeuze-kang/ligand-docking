# api/main.py

from pathlib import Path
from typing import Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
import json
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
from api.job_store import SQLiteJobStore, get_configured_job_store
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

job_store: SQLiteJobStore | None = None
_job_store_path: str | None = None


def _normalized_path(path_like: object) -> str:
    return str(Path(str(path_like)).expanduser())


def get_job_store() -> SQLiteJobStore:
    """Return a config-aware job store without pinning settings at import time."""
    global job_store, _job_store_path

    configured_path = _normalized_path(settings.api_job_store_path)
    if job_store is None:
        job_store = get_configured_job_store(configured_path)
        _job_store_path = configured_path
        return job_store

    current_store_path = _normalized_path(getattr(job_store, "path", configured_path))
    if _job_store_path is not None and current_store_path != _job_store_path:
        # Preserve legacy tests and callers that monkeypatch main.job_store directly.
        return job_store
    if _job_store_path is not None and _job_store_path != configured_path:
        job_store = get_configured_job_store(configured_path)
        _job_store_path = configured_path
    elif _job_store_path is None:
        _job_store_path = current_store_path
    return job_store


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

    store = get_job_store()
    store.create_job(job_id, request_data, status="submitted")

    # Create status file
    results_dir = job_results_dir(job_id)
    os.makedirs(results_dir, exist_ok=True)
    status_file_path = job_status_path(job_id)
    write_status_file(status_file_path, {"job_id": job_id, "status": "submitted"})

    if settings.api_inline_worker_enabled:
        background_tasks.add_task(
            process_next_job_once,
            store,
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
        get_job_store(),
        job_id=job_id,
        request_data=request_data,
        runner=run_simulation_async,
        lease_seconds=settings.api_worker_lease_seconds,
    )

@app.get("/status/{job_id}", response_model=StatusResponse)
def get_simulation_status(job_id: str):
    store = get_job_store()
    if not store.job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    # Read status from file
    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        return StatusResponse(job_id=job_id, status="unknown", message="Status file missing")

    status_data = read_status_file(status_file_path)
    record = store.get_job(job_id) or {}

    def _artifact_path(*values: object) -> str | None:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None

    return StatusResponse(
        job_id=job_id,
        status=status_data.get("status", "unknown"),
        message=status_data.get("error", "Running..."),
        result_manifest=_artifact_path(status_data.get("result_manifest"), record.get("result_manifest_path")),
        evidence_bundle=_artifact_path(status_data.get("evidence_bundle"), record.get("evidence_bundle_path")),
        evidence_bundle_sha256=_artifact_path(
            status_data.get("evidence_bundle_sha256"),
            record.get("evidence_bundle_sha256"),
        ),
    )

@app.get("/results/{job_id}", response_model=ResultsResponse)
def get_simulation_results(job_id: str):
    store = get_job_store()
    if not store.job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        raise HTTPException(status_code=404, detail="Results not ready or job failed")

    status_data = read_status_file(status_file_path)

    if status_data["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed. Status: {status_data['status']}")

    record = store.get_job(job_id) or {}

    def _artifact_path(*values: object) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    manifest_path = _artifact_path(status_data.get("result_manifest"), record.get("result_manifest_path"))
    evidence_bundle_path = _artifact_path(status_data.get("evidence_bundle"), record.get("evidence_bundle_path"))
    evidence_bundle_sha256 = _artifact_path(
        status_data.get("evidence_bundle_sha256"),
        record.get("evidence_bundle_sha256"),
    )
    if not manifest_path or not os.path.exists(manifest_path):
        raise HTTPException(
            status_code=403,
            detail="Completed job missing result manifest provenance",
        )
    if not evidence_bundle_path or not os.path.exists(evidence_bundle_path):
        raise HTTPException(
            status_code=403,
            detail="Completed job missing evidence bundle provenance",
        )
    if len(evidence_bundle_sha256) != 64:
        raise HTTPException(
            status_code=403,
            detail="Completed job missing evidence bundle fingerprint",
        )

    result_file = status_data.get("result_file")
    if not result_file or not os.path.exists(result_file):
        raise HTTPException(status_code=404, detail="Result file not found")

    result_path = Path(result_file)
    suffix = result_path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Result JSON artifact is invalid") from exc
        return JSONResponse(payload)
    media_type = {
        ".pdb": "chemical/x-pdb",
        ".sdf": "chemical/x-mdl-sdfile",
        ".mol": "chemical/x-mdl-molfile",
        ".zip": "application/zip",
    }.get(suffix, "application/octet-stream")
    return FileResponse(result_file, media_type=media_type, filename=os.path.basename(result_file))
    # Or return a ResultsResponse object with a download link if serving via URL is preferred
    # return ResultsResponse(job_id=job_id, status="completed", result_url=f"/download/{job_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
