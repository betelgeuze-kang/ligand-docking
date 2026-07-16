from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.request_identity import (
    normalize_tenant_id,
    request_identity,
    require_admin,
    require_tenant_match,
)
from betelgeuze_product.job_orchestration import (
    cancel_job_record,
    job_history,
    list_job_records,
    read_job_record,
    retry_job_record,
)

router = APIRouter(prefix="/product", tags=["product-docking"])
ROOT = Path(__file__).resolve().parents[1]
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"
PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT = ROOT / "runs" / "product_scope_breadth_closure_checklist_current.json"
_PRODUCT_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class LigandInput(BaseModel):
    ligand_id: str | None = None
    smiles: str | None = None
    sdf_path: str | None = None
    mol2_path: str | None = None
    pdbqt_path: str | None = None
    inchi: str | None = None
    compound_id: str | None = None


class DockingJobRequest(BaseModel):
    request_type: str = "structure_analysis_ligand_docking"
    family: str
    customer_id: str | None = None
    user_id: str | None = None
    target_id: str | None = None
    target_name: str | None = None
    pdb_id: str | None = None
    pdb_path: str | None = None
    pdb_content: str | None = None
    mmcif_path: str | None = None
    mmcif_content: str | None = None
    ligands: list[LigandInput] = Field(default_factory=list)
    pocket_residue_indices: list[int] = Field(default_factory=list)
    pocket_center: list[float] | None = None
    pocket_box_size: list[float] | None = None
    pocket_radius_a: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructureAnalysisRequest(BaseModel):
    pdb_id: str | None = None
    pdb_path: str | None = None
    pdb_content: str | None = None
    mmcif_path: str | None = None
    mmcif_content: str | None = None


class JobActionRequest(BaseModel):
    reason: str | None = None
    # Retained for input compatibility only. The authenticated principal is the
    # authoritative event actor and this caller-supplied field is ignored.
    actor: str | None = None


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _jobs_dir() -> Path:
    return Path(settings.results_storage_path) / "product_docking_jobs"


def _authorize_product_record(request: Request, job_id: str) -> dict[str, Any]:
    """Load a product job without permitting traversal or cross-tenant discovery."""

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


def _scientific_input_summary(record: dict[str, Any]) -> dict[str, Any]:
    receipt = record.get("scientific_input_provenance")
    if not isinstance(receipt, dict):
        receipt = {}
    pocket = receipt.get("pocket") if isinstance(receipt.get("pocket"), dict) else {}
    return {
        "schema_version": str(receipt.get("schema_version") or ""),
        "receipt_sha256": str(receipt.get("receipt_sha256") or ""),
        "content_identity_ready": receipt.get("content_identity_ready") is True,
        "execution_input_ready": receipt.get("execution_input_ready") is True,
        "explicit_pocket": pocket.get("explicit") is True,
        "pocket_definition_kind": str(pocket.get("definition_kind") or ""),
        "ligand_count": int(receipt.get("ligand_count") or 0),
        "private_payload_stored": record.get("private_payload_stored") is True,
        "blockers": list(receipt.get("blockers") or []),
        "claim_safe": False,
    }


@router.post("/docking/jobs")
async def submit_docking_job(
    payload: DockingJobRequest,
    request: Request,
    debug: bool = False,
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

    if (
        supplied_customer
        and not identity.is_admin
        and supplied_customer != identity.tenant_id
    ):
        raise HTTPException(
            status_code=403,
            detail="customer_id must match authenticated tenant",
        )
    if not identity.is_admin or not supplied_customer:
        raw_payload["customer_id"] = identity.tenant_id

    # Keep scientific/runner imports behind the approved submission path so
    # read/list/cancel/retry authorization remains dependency-light.
    from api.docking_dispatch import dispatch_docking_job_if_eligible
    from api.job_store import get_configured_job_store
    from betelgeuze_product.docking_private_payload import (
        configured_store,
        store_docking_request,
    )
    from betelgeuze_product.docking_request import (
        build_docking_job_record,
        persist_docking_job_record,
    )
    from betelgeuze_product.docking_response import (
        docking_claim_summary,
        docking_diagnostics_envelope,
        docking_dispatch_summary,
        docking_links,
        docking_progress_summary,
        docking_structure_summary,
        docking_validation_summary,
    )
    from betelgeuze_product.scientific_input_provenance import (
        build_scientific_input_provenance,
    )

    record = build_docking_job_record(
        raw_payload,
        source_host=request.client.host if request.client else "",
        residual_registry_packet=_read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
        scope_claim_guard_packet=_read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
    )
    receipt = build_scientific_input_provenance(
        raw_payload,
        request_sha256=str(record.get("request_sha256") or ""),
        dispatch_manifest=record.get("engine_dispatch_manifest", {}),
        root=ROOT,
    )
    record["scientific_input_provenance"] = receipt
    record["scientific_input_provenance_sha256"] = receipt["receipt_sha256"]
    record["scientific_input_provenance_ready"] = receipt["execution_input_ready"] is True
    record["scientific_input_explicit_pocket"] = receipt["pocket"]["explicit"] is True
    record["scientific_input_blockers"] = list(receipt["blockers"])

    private_payload_ref = store_docking_request(
        configured_store(),
        job_id=record["job_id"],
        request_sha256=record["request_sha256"],
        request=raw_payload,
    )
    record["private_payload_stored"] = bool(private_payload_ref)
    record["private_payload_ref_sha256"] = (
        hashlib.sha256(private_payload_ref.encode("utf-8")).hexdigest()
        if private_payload_ref
        else ""
    )
    persist_docking_job_record(record, _jobs_dir())

    dispatch_outcome = dispatch_docking_job_if_eligible(
        record,
        jobs_dir=_jobs_dir(),
        store=get_configured_job_store(),
    )
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
        "scientific_input": _scientific_input_summary(record),
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
    request: Request,
) -> dict[str, Any]:
    request_identity(request)
    from betelgeuze_product.structure_analysis import analyze_structure_source

    analysis = analyze_structure_source(_model_to_dict(payload), root=ROOT)
    return {
        **analysis,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


@router.get("/docking/jobs/{job_id}")
async def get_docking_job(
    job_id: str,
    request: Request,
    debug: bool = False,
) -> dict[str, Any]:
    identity = request_identity(request)
    record = _authorize_product_record(request, job_id)
    if debug:
        require_admin(identity)
    from betelgeuze_product.docking_response import build_docking_submission_response

    return build_docking_submission_response(record, debug=debug)


@router.get("/docking/jobs")
async def list_docking_jobs(
    request: Request,
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
