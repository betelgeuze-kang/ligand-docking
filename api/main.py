# api/main.py

from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
import hashlib
import json
import uuid
import os
from api.artifact_access import verify_completed_result_artifacts
from api.cameo import router as cameo_router
from api.casp17 import router as casp17_router
from api.cleanup import router as cleanup_router
from api.goal import router as goal_router
from api.product_ai_surface import router as product_ai_surface_router
from api.product_architecture import router as product_architecture_router
from api.product_scope import router as product_scope_router
from api.product import router as product_router
from api.product_benchmark import router as product_benchmark_router
from api.product_cameo_runner import router as product_cameo_runner_router
from api.product_capabilities import router as product_capabilities_router
from api.product_commercial_readiness import router as product_commercial_readiness_router
from api.product_evidence_goal import router as product_evidence_goal_router
from api.product_gpcr_hard_decoy import router as product_gpcr_hard_decoy_router
from api.product_hbond_backmap import router as product_hbond_backmap_router
from api.product_docking import router as product_docking_router
from api.product_license import router as product_license_router
from api.product_operational import router as product_operational_router
from api.product_production_ai import router as product_production_ai_router
from api.product_release_evidence import router as product_release_evidence_router
from api.product_release_ops import router as product_release_ops_router
from api.product_service_contracts import router as product_service_contracts_router
from api.product_tier_beta import router as product_tier_beta_router
from api.models import SimulationRequest, SimulationResponse, StatusResponse
from api.simulation_scope import (
    PRODUCT_SIMULATION_SCOPE,
    UnsupportedSimulationScopeError,
    validate_simulation_request_scope,
)
from api.tasks import run_simulation_async
from api.config import settings
from api.startup_preflight import run_startup_preflight, check_key_staleness
from api.job_store import SQLiteJobStore, get_configured_job_store
from api.request_identity import request_identity
from api.security import ProductSecurityMiddleware, security_metrics_text
from api.simulation_endpoint_access import (
    create_simulation_job_for_identity,
    get_simulation_job_for_identity,
)
from api.worker import (
    job_results_dir,
    job_status_path,
    process_next_job_once,
    read_status_file,
    run_job_once,
    write_status_file,
)
from betelgeuze_product.tier_beta_vertical_slice import is_tier_beta_vertical_slice_request

# --- Startup preflight: fail fast on fatal misconfigurations ---
run_startup_preflight(settings)
check_key_staleness(settings)

app = FastAPI(title=settings.app_name)
app.add_middleware(ProductSecurityMiddleware)
app.include_router(cameo_router)
app.include_router(casp17_router)
app.include_router(cleanup_router)
app.include_router(goal_router)
app.include_router(product_architecture_router)
app.include_router(product_capabilities_router)
app.include_router(product_docking_router)
app.include_router(product_service_contracts_router)
app.include_router(product_operational_router)
app.include_router(product_release_ops_router)
app.include_router(product_release_evidence_router)
app.include_router(product_license_router)
app.include_router(product_benchmark_router)
app.include_router(product_cameo_runner_router)
app.include_router(product_ai_surface_router)
app.include_router(product_production_ai_router)
app.include_router(product_scope_router)
app.include_router(product_commercial_readiness_router)
app.include_router(product_evidence_goal_router)
app.include_router(product_hbond_backmap_router)
app.include_router(product_gpcr_hard_decoy_router)
app.include_router(product_router)
app.include_router(product_tier_beta_router)

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


def _error_receipt(value: object) -> tuple[str | None, str | None]:
    text = str(value or "")
    if not text:
        return None, None
    raw = text.encode("utf-8", errors="replace")
    return "job_execution_failed", hashlib.sha256(raw).hexdigest()


@app.post("/simulate", response_model=SimulationResponse)
async def submit_simulation(
    payload: SimulationRequest,
    background_tasks: BackgroundTasks,
    request: Request = None,
):
    identity = request_identity(request)
    job_id = str(uuid.uuid4())
    request_data = _model_to_dict(payload)
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
    create_simulation_job_for_identity(
        store,
        identity,
        job_id,
        request_data,
        status="submitted",
    )

    # Create status file only after the durable owner binding and job row exist.
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
            retry_on_failure=not is_tier_beta_vertical_slice_request(request_data),
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
def get_simulation_status(job_id: str, request: Request = None):
    identity = request_identity(request)
    store = get_job_store()
    record = get_simulation_job_for_identity(
        store,
        identity,
        job_id,
        resource="Job",
    )

    # Read status from file only after object authorization succeeds.
    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        return StatusResponse(
            job_id=job_id,
            status=str(record.get("status", "unknown")),
            message="Status file unavailable",
        )

    status_data = read_status_file(status_file_path)
    status = str(status_data.get("status", record.get("status", "unknown")))
    error_code, error_reference = _error_receipt(
        status_data.get("error") or record.get("error")
    )

    manifest_available = False
    bundle_available = False
    evidence_sha: str | None = None
    if status == "completed":
        verified = verify_completed_result_artifacts(
            job_id=job_id,
            record=record,
            status_data=status_data,
            result_root=job_results_dir(job_id),
            signing_key=settings.api_result_manifest_signing_key,
            expected_key_id=settings.api_result_manifest_key_id,
        )
        manifest_available = True
        bundle_available = True
        evidence_sha = verified.evidence_bundle_sha256

    if error_code:
        message = "Job failed; use error_reference for operator lookup"
    elif status == "completed":
        message = "Completed"
    else:
        message = "Running..."

    return StatusResponse(
        job_id=job_id,
        status=status,
        message=message,
        error_code=error_code,
        error_reference=error_reference,
        result_manifest_available=manifest_available,
        evidence_bundle_available=bundle_available,
        evidence_bundle_sha256=evidence_sha,
        result_manifest=None,
        evidence_bundle=None,
    )


@app.get(
    "/results/{job_id}",
    responses={
        200: {
            "description": "Completed result artifact. JSON artifacts are returned inline; file artifacts are downloaded with their artifact media type.",
            "content": {
                "application/json": {},
                "chemical/x-pdb": {},
                "chemical/x-mdl-sdfile": {},
                "chemical/x-mdl-molfile": {},
                "application/zip": {},
                "application/octet-stream": {},
            },
        }
    },
)
def get_simulation_results(job_id: str, request: Request = None):
    identity = request_identity(request)
    store = get_job_store()
    record = get_simulation_job_for_identity(
        store,
        identity,
        job_id,
        resource="Job",
    )

    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        raise HTTPException(status_code=404, detail="Results not ready or job failed")

    status_data = read_status_file(status_file_path)
    verified = verify_completed_result_artifacts(
        job_id=job_id,
        record=record,
        status_data=status_data,
        result_root=job_results_dir(job_id),
        signing_key=settings.api_result_manifest_signing_key,
        expected_key_id=settings.api_result_manifest_key_id,
        snapshot_result=True,
    )
    if verified.artifact_type == "json" or verified.media_type == "application/json":
        try:
            assert verified.result_snapshot is not None
            result_payload = json.load(verified.result_snapshot)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="Result JSON artifact is invalid") from exc
        finally:
            verified.close()
        return JSONResponse(result_payload)
    disposition = f"attachment; filename*=UTF-8''{quote(verified.result_path.name)}"
    return StreamingResponse(
        verified.iter_result(),
        media_type=verified.media_type,
        headers={"Content-Disposition": disposition},
        background=BackgroundTask(verified.close),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
