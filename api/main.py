# api/main.py

from pathlib import Path
from typing import Any

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
import json
import hmac
import hashlib
import uuid
import os
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
from api.result_manifest import infer_result_artifact_metadata, verify_result_manifest
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
from api.security import ProductSecurityMiddleware, security_metrics_text
from api.path_security import confined_path, normalize_tier_beta_request_paths
from api.request_identity import request_identity, require_tenant_match
from api.validated_runner import authorize_runner_profile_execution
from api.worker import (
    job_results_dir,
    job_status_path,
    process_next_job_once,
    read_status_file,
    run_job_once,
    write_status_file,
)
from betelgeuze_product.tier_beta_vertical_slice import is_tier_beta_vertical_slice_request
from betelgeuze_ai_md.contracts import EvidenceBundle
from betelgeuze_ai_md.contracts.errors import ContractValidationError

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_payload(payload: Any) -> str:
    normalized = payload if isinstance(payload, dict) else {"value": payload}
    canonical = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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
async def submit_simulation(
    payload: SimulationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    job_id = str(uuid.uuid4())
    request_data = _model_to_dict(payload)
    identity = request_identity(request)
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

    if is_tier_beta_vertical_slice_request(request_data):
        try:
            request_data = normalize_tier_beta_request_paths(
                request_data,
                local_paths_enabled=settings.product_api_local_path_inputs_enabled,
                input_root=settings.product_api_local_input_root,
            )
        except (FileNotFoundError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        authorize_runner_profile_execution(request_data)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403, detail=f"runner profile authorization failed: {exc}") from exc

    store = get_job_store()
    store.create_job(
        job_id,
        request_data,
        status="submitted",
        tenant_id=identity.tenant_id,
    )

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
def get_simulation_status(job_id: str, request: Request):
    store = get_job_store()
    record = store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    require_tenant_match(request_identity(request), record.get("tenant_id"), resource="job")

    # Read status from file
    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        return StatusResponse(job_id=job_id, status="unknown", message="Status file missing")

    status_data = read_status_file(status_file_path)

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
def get_simulation_results(job_id: str, request: Request):
    store = get_job_store()
    record = store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    require_tenant_match(request_identity(request), record.get("tenant_id"), resource="job")

    status_file_path = job_status_path(job_id)
    if not os.path.exists(status_file_path):
        raise HTTPException(status_code=404, detail="Results not ready or job failed")

    status_data = read_status_file(status_file_path)

    if status_data["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed. Status: {status_data['status']}")

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
    job_root = Path(job_results_dir(job_id))
    try:
        manifest_file = confined_path(
            manifest_path,
            job_root,
            label="result manifest",
            must_exist=True,
        )
        evidence_bundle_file = confined_path(
            evidence_bundle_path,
            job_root,
            label="evidence bundle",
            must_exist=True,
        )
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Completed job has invalid artifact provenance: {exc}",
        ) from exc
    if len(evidence_bundle_sha256) != 64:
        raise HTTPException(
            status_code=403,
            detail="Completed job missing evidence bundle fingerprint",
        )
    try:
        raw_bundle = json.loads(evidence_bundle_file.read_text(encoding="utf-8"))
        observed_bundle_sha256 = EvidenceBundle(**raw_bundle).fingerprint()
    except (OSError, json.JSONDecodeError, ContractValidationError, TypeError) as exc:
        raise HTTPException(status_code=403, detail="Evidence bundle contract validation failed") from exc
    if not hmac.compare_digest(observed_bundle_sha256, evidence_bundle_sha256):
        raise HTTPException(status_code=403, detail="Evidence bundle fingerprint mismatch")

    result_file = status_data.get("result_file")
    try:
        result_path = confined_path(
            str(result_file or ""),
            job_root,
            label="result artifact",
            must_exist=True,
        )
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail="Result file not found") from exc

    manifest_payload: dict[str, Any] = {}
    try:
        loaded_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest_payload = loaded_manifest if isinstance(loaded_manifest, dict) else {}
    except (OSError, json.JSONDecodeError):
        manifest_payload = {}
    if not verify_result_manifest(
        manifest_payload,
        signing_key=settings.api_result_manifest_signing_key,
    ):
        raise HTTPException(status_code=403, detail="Result manifest signature verification failed")
    if (
        str(manifest_payload.get("job_id") or "") != job_id
        or str(manifest_payload.get("status") or "") != "completed"
    ):
        raise HTTPException(status_code=403, detail="Result manifest job binding is invalid")
    expected_request_digest = _sha256_payload(record.get("request") or {})
    manifest_request_digest = str(manifest_payload.get("request_sha256") or "")
    if not hmac.compare_digest(expected_request_digest, manifest_request_digest):
        raise HTTPException(status_code=403, detail="Result manifest request binding is invalid")
    try:
        manifest_result_path = confined_path(
            str(manifest_payload.get("result_file") or ""),
            job_root,
            label="manifest result artifact",
            must_exist=True,
        )
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail="Result manifest artifact binding is invalid") from exc
    if manifest_result_path != result_path:
        raise HTTPException(status_code=403, detail="Result manifest artifact path mismatch")
    result_digest = _sha256_file(result_path)
    manifest_digest = str(manifest_payload.get("result_file_sha256") or "")
    if len(manifest_digest) != 64 or not hmac.compare_digest(result_digest, manifest_digest):
        raise HTTPException(status_code=403, detail="Result artifact fingerprint mismatch")
    artifact_metadata = infer_result_artifact_metadata(result_path)
    media_type = str(
        manifest_payload.get("result_file_media_type")
        or artifact_metadata["result_file_media_type"]
    )
    artifact_type = str(
        manifest_payload.get("result_artifact_type")
        or artifact_metadata["result_artifact_type"]
    )
    if artifact_type == "json" or media_type == "application/json":
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Result JSON artifact is invalid") from exc
        return JSONResponse(payload)
    return FileResponse(str(result_path), media_type=media_type, filename=result_path.name)
    # Or return a ResultsResponse object with a download link if serving via URL is preferred
    # return ResultsResponse(job_id=job_id, status="completed", result_url=f"/download/{job_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
