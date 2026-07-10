from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.docking_dispatch import dispatch_docking_job_if_eligible
from api.job_store import get_configured_job_store
from api.path_security import normalize_operator_input_value
from api.request_identity import (
    normalize_tenant_id,
    request_identity,
    require_admin,
    require_tenant_match,
)
from betelgeuze_product.docking_private_payload import configured_store, store_docking_request
from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record
from betelgeuze_product.docking_response import (
    build_docking_submission_response,
    docking_claim_summary,
    docking_diagnostics_envelope,
    docking_dispatch_summary,
    docking_links,
    docking_progress_summary,
    docking_structure_summary,
    docking_validation_summary,
)
from betelgeuze_product.job_orchestration import (
    cancel_job_record,
    job_history,
    list_job_records,
    retry_job_record,
    read_job_record,
)
from betelgeuze_product.structure_analysis import analyze_structure_source

router = APIRouter(prefix="/product", tags=["product-docking"])
ROOT = Path(__file__).resolve().parents[1]
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"
PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT = ROOT / "runs" / "product_scope_breadth_closure_checklist_current.json"
_PRODUCT_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class LigandInput(BaseModel):
    ligand_id: str | None = Field(default=None, max_length=160)
    smiles: str | None = Field(default=None, max_length=20000)
    sdf_path: str | None = Field(default=None, max_length=4096)
    mol2_path: str | None = Field(default=None, max_length=4096)
    pdbqt_path: str | None = Field(default=None, max_length=4096)
    inchi: str | None = Field(default=None, max_length=20000)
    compound_id: str | None = Field(default=None, max_length=160)


class DockingJobRequest(BaseModel):
    request_type: str = "structure_analysis_ligand_docking"
    family: str = Field(..., min_length=1, max_length=80)
    customer_id: str | None = Field(default=None, max_length=80)
    user_id: str | None = Field(default=None, max_length=160)
    target_id: str | None = Field(default=None, max_length=160)
    target_name: str | None = Field(default=None, max_length=240)
    pdb_id: str | None = Field(default=None, max_length=32)
    pdb_path: str | None = Field(default=None, max_length=4096)
    pdb_content: str | None = Field(default=None, max_length=10_000_000)
    mmcif_path: str | None = Field(default=None, max_length=4096)
    mmcif_content: str | None = Field(default=None, max_length=10_000_000)
    ligands: list[LigandInput] = Field(default_factory=list, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructureAnalysisRequest(BaseModel):
    pdb_id: str | None = Field(default=None, max_length=32)
    pdb_path: str | None = Field(default=None, max_length=4096)
    pdb_content: str | None = Field(default=None, max_length=10_000_000)
    mmcif_path: str | None = Field(default=None, max_length=4096)
    mmcif_content: str | None = Field(default=None, max_length=10_000_000)


class JobActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    actor: str | None = Field(default=None, max_length=160)


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _jobs_dir() -> Path:
    return Path(settings.results_storage_path) / "product_docking_jobs"


def _normalize_local_paths(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    structure_suffixes = (".pdb", ".cif", ".mmcif")
    ligand_suffixes = (".sdf", ".mol", ".mol2", ".pdbqt")
    for key in ("pdb_path", "mmcif_path"):
        if normalized.get(key):
            normalized[key] = normalize_operator_input_value(
                normalized[key],
                suffixes=structure_suffixes,
                local_paths_enabled=settings.product_api_local_path_inputs_enabled,
                input_root=settings.product_api_local_input_root,
                label=key,
            )
    rows = []
    for raw in normalized.get("ligands", []) or []:
        row = dict(raw) if isinstance(raw, dict) else raw
        if isinstance(row, dict):
            for key in ("sdf_path", "mol2_path", "pdbqt_path"):
                if row.get(key):
                    row[key] = normalize_operator_input_value(
                        row[key],
                        suffixes=ligand_suffixes,
                        local_paths_enabled=settings.product_api_local_path_inputs_enabled,
                        input_root=settings.product_api_local_input_root,
                        label=key,
                    )
        rows.append(row)
    if rows:
        normalized["ligands"] = rows
    return normalized


def _authorize_product_record(request: Request, job_id: str) -> dict[str, Any]:
    if not _PRODUCT_JOB_ID_RE.fullmatch(str(job_id or "")):
        raise HTTPException(status_code=404, detail="job not found")
    record = read_job_record(_jobs_dir(), job_id)
    if not record:
        raise HTTPException(status_code=404, detail="job not found")
    require_tenant_match(
        request_identity(request),
        record.get("customer_id") or "local",
        resource="job",
    )
    return record


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@router.post("/docking/jobs")
async def submit_docking_job(
    payload: DockingJobRequest, request: Request, debug: bool = False
) -> dict[str, Any]:
    identity = request_identity(request)
    if debug:
        require_admin(identity)
    raw_payload = _model_to_dict(payload)
    supplied_customer = str(raw_payload.get("customer_id") or "").strip()
    if supplied_customer:
        try:
            supplied_customer = normalize_tenant_id(supplied_customer)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raw_payload["customer_id"] = supplied_customer
    if supplied_customer and not identity.is_admin and supplied_customer != identity.tenant_id:
        raise HTTPException(status_code=403, detail="customer_id must match authenticated tenant")
    if not identity.is_admin or not supplied_customer:
        raw_payload["customer_id"] = identity.tenant_id
    try:
        raw_payload = _normalize_local_paths(raw_payload)
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = build_docking_job_record(
        raw_payload,
        source_host=request.client.host if request.client else "",
        residual_registry_packet=_read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
        scope_claim_guard_packet=_read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
    )
    # Persist the ORIGINAL request encrypted at rest, bound to job_id and the
    # ledger request_sha256. The public ledger keeps only the redacted form;
    # materialization recovers the raw inputs from this store. Fail-closed:
    # no-op when the store is not configured.
    private_store = configured_store()
    private_store_required = bool(
        str(settings.docking_private_payload_keys or "").strip()
        or settings.product_api_hosted_exposure_approved
    )
    if private_store_required and private_store is None:
        raise HTTPException(status_code=503, detail="private docking payload store is unavailable")
    private_ref = store_docking_request(
        private_store,
        job_id=record["job_id"],
        request_sha256=record["request_sha256"],
        request=raw_payload,
    )
    if private_store_required and private_ref is None:
        raise HTTPException(status_code=503, detail="private docking payload persistence failed")
    persist_docking_job_record(record, _jobs_dir())
    dispatch_outcome = dispatch_docking_job_if_eligible(
        record,
        jobs_dir=_jobs_dir(),
        store=get_configured_job_store(),
    )
    # Stable, grouped customer/GUI response. The internal ledger_path is never
    # exposed; verbose internals are returned only under debug=True. Keep the
    # top-level keys in sync with DOCKING_SUBMISSION_TOP_LEVEL_KEYS (enforced by
    # the product API contract check).
    return {
        "job_id": record["job_id"],
        "status": record["status"],
        "request_type": record["request_type"],
        "family": record["family"],
        "target_id": record["target_id"],
        "customer_id": record["customer_id"],
        "user_id": record["user_id"],
        "validation_status": record["validation_status"],
        "execution_enabled": record["execution_enabled"],
        "docking_results_emitted": record["docking_results_emitted"],
        "validation": docking_validation_summary(record),
        "structure": docking_structure_summary(record),
        "progress": docking_progress_summary(record),
        "dispatch": docking_dispatch_summary(record, dispatch_outcome),
        "claim": docking_claim_summary(record),
        "links": docking_links(record),
        "claim_boundary": record["claim_boundary"],
        **(
            docking_diagnostics_envelope(record)
            if debug and identity.is_admin
            else {}
        ),
    }


@router.post("/structure/analyze")
async def analyze_product_structure(
    payload: StructureAnalysisRequest,
    request: Request = None,
) -> dict[str, Any]:
    request_identity(request)
    try:
        normalized = _normalize_local_paths(_model_to_dict(payload))
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    analysis = analyze_structure_source(normalized, root=settings.product_api_local_input_root)
    return {
        **analysis,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


@router.get("/docking/jobs/{job_id}")
async def get_docking_job(job_id: str, request: Request, debug: bool = False) -> dict[str, Any]:
    identity = request_identity(request)
    record = _authorize_product_record(request, job_id)
    if debug:
        require_admin(identity)
    return build_docking_submission_response(record, debug=debug)


@router.get("/docking/jobs")
async def list_docking_jobs(
    request: Request = None,
    limit: int = 50,
    source_host: str = "",
    root_job_id: str = "",
    customer_id: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    identity = request_identity(request)
    if not identity.is_admin:
        source_host = ""
        customer_id = identity.tenant_id
        user_id = ""
    return list_job_records(
        _jobs_dir(),
        limit=max(1, min(limit, 500)),
        source_host=source_host,
        root_job_id=root_job_id,
        customer_id=customer_id,
        user_id=user_id,
    )


@router.get("/docking/jobs/{job_id}/history")
async def get_docking_job_history(job_id: str, request: Request) -> dict[str, Any]:
    _authorize_product_record(request, job_id)
    return job_history(_jobs_dir(), job_id)


@router.post("/docking/jobs/{job_id}/cancel")
async def cancel_docking_job(
    job_id: str,
    request: Request,
    payload: JobActionRequest | None = None,
) -> dict[str, Any]:
    identity = request_identity(request)
    _authorize_product_record(request, job_id)
    action = payload or JobActionRequest()
    return cancel_job_record(
        _jobs_dir(),
        job_id,
        reason=action.reason or "",
        actor=identity.principal,
    )


@router.post("/docking/jobs/{job_id}/retry")
async def retry_docking_job(
    job_id: str,
    request: Request,
    payload: JobActionRequest | None = None,
) -> dict[str, Any]:
    identity = request_identity(request)
    _authorize_product_record(request, job_id)
    action = payload or JobActionRequest()
    return retry_job_record(
        _jobs_dir(),
        job_id,
        reason=action.reason or "",
        actor=identity.principal,
    )
