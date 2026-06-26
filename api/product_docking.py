from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.docking_dispatch import dispatch_docking_job_if_eligible
from api.job_store import get_configured_job_store
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
)
from betelgeuze_product.structure_analysis import analyze_structure_source

router = APIRouter(prefix="/product", tags=["product-docking"])
ROOT = Path(__file__).resolve().parents[1]
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"
PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT = ROOT / "runs" / "product_scope_breadth_closure_checklist_current.json"


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
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructureAnalysisRequest(BaseModel):
    pdb_id: str | None = None
    pdb_path: str | None = None
    pdb_content: str | None = None
    mmcif_path: str | None = None
    mmcif_content: str | None = None


class JobActionRequest(BaseModel):
    reason: str | None = None
    actor: str | None = None


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _jobs_dir() -> Path:
    return Path(settings.results_storage_path) / "product_docking_jobs"


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
    record = build_docking_job_record(
        _model_to_dict(payload),
        source_host=request.client.host if request.client else "",
        residual_registry_packet=_read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
        scope_claim_guard_packet=_read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
    )
    persist_docking_job_record(record, _jobs_dir())
    # Persist the ORIGINAL request encrypted at rest, bound to job_id and the
    # ledger request_sha256. The public ledger keeps only the redacted form;
    # materialization recovers the raw inputs from this store. Fail-closed:
    # no-op when the store is not configured.
    store_docking_request(
        configured_store(),
        job_id=record["job_id"],
        request_sha256=record["request_sha256"],
        request=_model_to_dict(payload),
    )
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
        **(docking_diagnostics_envelope(record) if debug else {}),
    }


@router.post("/structure/analyze")
async def analyze_product_structure(payload: StructureAnalysisRequest) -> dict[str, Any]:
    analysis = analyze_structure_source(_model_to_dict(payload), root=ROOT)
    return {
        **analysis,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


@router.get("/docking/jobs/{job_id}")
async def get_docking_job(job_id: str, debug: bool = False) -> dict[str, Any]:
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return {
            "job_id": job_id,
            "status": "missing",
            "execution_enabled": False,
            "docking_results_emitted": False,
        }
    record = json.loads(path.read_text(encoding="utf-8"))
    return build_docking_submission_response(record, debug=debug)


@router.get("/docking/jobs")
async def list_docking_jobs(
    limit: int = 50,
    source_host: str = "",
    root_job_id: str = "",
    customer_id: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    return list_job_records(
        _jobs_dir(),
        limit=max(1, min(limit, 500)),
        source_host=source_host,
        root_job_id=root_job_id,
        customer_id=customer_id,
        user_id=user_id,
    )


@router.get("/docking/jobs/{job_id}/history")
async def get_docking_job_history(job_id: str) -> dict[str, Any]:
    return job_history(_jobs_dir(), job_id)


@router.post("/docking/jobs/{job_id}/cancel")
async def cancel_docking_job(job_id: str, payload: JobActionRequest | None = None) -> dict[str, Any]:
    action = payload or JobActionRequest()
    return cancel_job_record(_jobs_dir(), job_id, reason=action.reason or "", actor=action.actor or "")


@router.post("/docking/jobs/{job_id}/retry")
async def retry_docking_job(job_id: str, payload: JobActionRequest | None = None) -> dict[str, Any]:
    action = payload or JobActionRequest()
    return retry_job_record(_jobs_dir(), job_id, reason=action.reason or "", actor=action.actor or "")
