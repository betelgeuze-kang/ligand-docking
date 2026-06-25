from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from api.config import settings
from api.job_store import get_configured_job_store
from api.tasks import run_simulation_async
from api.worker import job_results_dir, job_status_path, process_next_job_once, write_status_file
from betelgeuze_product.tier_beta_vertical_slice import (
    TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
    TIER_BETA_WORKFLOW_ID,
)

router = APIRouter(prefix="/product/tier-beta", tags=["product-tier-beta"])


class TierBetaScreeningRequest(BaseModel):
    protein_input: str = Field(..., description="Local PDB/mmCIF path or PDB text.")
    ligand_input: str = Field(..., description="SMILES/SDF path or ligand text.")
    pocket_residue_indices: list[int] | None = None
    pose_count: int = 8
    top_k: int = 3
    stability_steps: int = 0
    seed: int = 42


def _request_to_simulation_payload(payload: TierBetaScreeningRequest) -> dict[str, Any]:
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return {
        "runner_profile_id": TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
        "target_name": "tier_beta_local_fixture",
        "runner_profile_params": {
            "workflow_id": TIER_BETA_WORKFLOW_ID,
            **data,
        },
        "steps": int(data.get("stability_steps") or 0),
        "output_format": "json",
    }


@router.post("/docking/jobs")
async def submit_tier_beta_docking_job(
    payload: TierBetaScreeningRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    request_data = _request_to_simulation_payload(payload)
    store = get_configured_job_store()
    store.create_job(job_id, request_data, status="submitted")
    results_dir = job_results_dir(job_id)
    os.makedirs(results_dir, exist_ok=True)
    write_status_file(job_status_path(job_id), {"job_id": job_id, "status": "submitted"})

    if settings.api_inline_worker_enabled:
        background_tasks.add_task(
            process_next_job_once,
            store,
            worker_id=f"api-tier-beta-inline-{job_id}",
            runner=run_simulation_async,
            lease_seconds=settings.api_worker_lease_seconds,
            retry_on_failure=False,
        )

    return {
        "job_id": job_id,
        "status": "submitted",
        "workflow_id": TIER_BETA_WORKFLOW_ID,
        "runner_profile_id": TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
        "execution_enabled": True,
        "external_state_mutated": False,
        "claim_boundary": (
            "Restricted local Tier-beta screening job. Results remain claim-limited and signed "
            "only for local provenance."
        ),
    }
