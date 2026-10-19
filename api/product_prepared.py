"""Authenticated HTTP adapter for the optional prepared-job lifecycle service."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from api.request_identity import ProductRequestIdentity
from betelgeuze_product import prepared_lifecycle as lifecycle

router = APIRouter(prefix="/prepared/jobs", tags=["prepared-research-jobs"])


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreparedSubmitRequest(_StrictRequest):
    admission_id: StrictStr = Field(min_length=1, max_length=64)
    idempotency_key: StrictStr = Field(min_length=1, max_length=128)
    budget_policy: StrictStr = Field(default="local_cpu_research_v1", min_length=1, max_length=64)


class PreparedCancelRequest(_StrictRequest):
    reason: StrictStr = Field(default="", max_length=512)


class PreparedPlanRequest(_StrictRequest):
    admission_id: StrictStr = Field(min_length=1, max_length=64)
    budget_policy: StrictStr = Field(default="local_cpu_research_v1", min_length=1, max_length=64)


class PreparedExecuteRequest(_StrictRequest):
    plan_id: StrictStr = Field(min_length=32, max_length=32)
    plan_sha256: StrictStr = Field(min_length=64, max_length=64)
    idempotency_key: StrictStr = Field(min_length=1, max_length=128)


class PreparedCompareRequest(_StrictRequest):
    execution_ids: list[StrictStr] = Field(min_length=1, max_length=32)


def _service(request: Request):
    # ProductSecurityMiddleware owns this principal. In particular, the legacy
    # unauthenticated local X-Tenant-ID fallback is not an authority here.
    identity = getattr(request.state, "product_identity", None)
    if not isinstance(identity, ProductRequestIdentity) or not identity.authenticated:
        raise lifecycle.LifecycleError(
            "AUTHENTICATION_REQUIRED", "Authenticated product identity required", http_status=401,
        )
    return lifecycle.configured_service(tenant_id=identity.tenant_id)


def _call(request: Request, operation, *, accepted: bool = False):
    try:
        result = operation(_service(request))
        if isinstance(result, FileResponse):
            return result
        return JSONResponse(status_code=202 if accepted else 200, content=result)
    except lifecycle.LifecycleError as exc:
        return JSONResponse(status_code=exc.http_status, content=exc.document())
    except Exception:
        error = lifecycle.LifecycleError(
            "INTERNAL_ERROR", "Prepared lifecycle request failed", http_status=500,
        )
        return JSONResponse(status_code=error.http_status, content=error.document())


@router.post("", status_code=202)
def submit_prepared_job(body: PreparedSubmitRequest, request: Request):
    return _call(request, lambda service: service.submit(
        body.admission_id, body.idempotency_key, budget_policy=body.budget_policy,
    ), accepted=True)


@router.post("/plans")
def plan_prepared_job(body: PreparedPlanRequest, request: Request):
    return _call(request, lambda service: service.plan(body.admission_id, budget_policy=body.budget_policy))


@router.get("/plans/{plan_id}")
def prepared_job_plan(plan_id: str, request: Request):
    return _call(request, lambda service: service.get_plan(plan_id))


@router.post("/execute", status_code=202)
def execute_prepared_plan(body: PreparedExecuteRequest, request: Request):
    return _call(request, lambda service: service.execute(body.plan_id, body.plan_sha256, body.idempotency_key), accepted=True)


@router.post("/compare")
def compare_prepared_jobs(body: PreparedCompareRequest, request: Request):
    return _call(request, lambda service: service.compare(body.execution_ids))


@router.get("/{execution_id}")
def prepared_job_status(execution_id: str, request: Request):
    return _call(request, lambda service: service.status(execution_id))


@router.get("/{execution_id}/verify")
def verify_prepared_job(execution_id: str, request: Request):
    return _call(request, lambda service: service.verify(execution_id))


@router.get("/{execution_id}/report")
def report_prepared_job(execution_id: str, request: Request):
    return _call(request, lambda service: service.report(execution_id))


@router.post("/{execution_id}/cancel", status_code=202)
def cancel_prepared_job(execution_id: str, request: Request, body: PreparedCancelRequest | None = None):
    # 202 acknowledges a request. Active-process cancellation is confirmed only
    # after the process owner has waited for the actual child process to exit.
    reason = body.reason if body is not None else ""
    return _call(request, lambda service: service.cancel(execution_id, reason=reason), accepted=True)


@router.post("/{execution_id}/resume", status_code=202)
def resume_prepared_job(execution_id: str, request: Request):
    return _call(request, lambda service: service.resume(execution_id), accepted=True)


@router.get("/{execution_id}/artifacts")
def prepared_job_artifacts(execution_id: str, request: Request):
    return _call(request, lambda service: service.artifacts(execution_id))


@router.get("/{execution_id}/artifacts/{artifact_id}")
def prepared_job_artifact(execution_id: str, artifact_id: str, request: Request):
    def download(service):
        path, metadata = service.artifact(execution_id, artifact_id)
        return FileResponse(
            path=path,
            media_type=metadata["media_type"],
            filename=metadata["artifact_id"],
            headers={"ETag": '"' + metadata["sha256"] + '"'},
        )

    return _call(request, download)
