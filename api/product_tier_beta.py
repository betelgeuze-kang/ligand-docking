from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from api.config import settings
from api.job_store import get_configured_job_store
from api.path_security import normalize_operator_input_value
from api.request_identity import request_identity
from api.tasks import run_simulation_async
from api.validated_runner import authorize_runner_profile_execution
from api.worker import job_results_dir, job_status_path, process_next_job_once, write_status_file
from betelgeuze_product.tier_beta_vertical_slice import (
    TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
    TIER_BETA_WORKFLOW_ID,
)

router = APIRouter(prefix="/product/tier-beta", tags=["product-tier-beta"])


class TierBetaScreeningRequest(BaseModel):
    protein_input: str = Field(
        ...,
        min_length=1,
        max_length=10_000_000,
        description="Inline PDB/mmCIF text or an operator-root-confined local path.",
    )
    ligand_input: str = Field(
        ...,
        min_length=1,
        max_length=5_000_000,
        description="SMILES/inline ligand text or an operator-root-confined local path.",
    )
    pocket_residue_indices: list[int] | None = Field(default=None, max_length=512)
    pose_count: int = Field(default=8, ge=1, le=64)
    top_k: int = Field(default=3, ge=1, le=20)
    stability_steps: int = Field(default=0, ge=0, le=10_000)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "TierBetaScreeningRequest":
        if self.top_k > self.pose_count:
            raise ValueError("top_k cannot exceed pose_count")
        if self.pocket_residue_indices is not None and any(
            int(index) < 0 for index in self.pocket_residue_indices
        ):
            raise ValueError("pocket_residue_indices must be non-negative")
        return self


def _request_to_simulation_payload(payload: TierBetaScreeningRequest) -> dict[str, Any]:
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        data["protein_input"] = normalize_operator_input_value(
            data["protein_input"],
            suffixes=(".pdb", ".cif", ".mmcif"),
            local_paths_enabled=settings.product_api_local_path_inputs_enabled,
            input_root=settings.product_api_local_input_root,
            label="protein_input",
        )
        data["ligand_input"] = normalize_operator_input_value(
            data["ligand_input"],
            suffixes=(".sdf", ".mol", ".mol2", ".pdbqt"),
            local_paths_enabled=settings.product_api_local_path_inputs_enabled,
            input_root=settings.product_api_local_input_root,
            label="ligand_input",
        )
    except (FileNotFoundError, PermissionError) as exc:
        raise ValueError(str(exc)) from exc
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
    request: Request,
) -> dict[str, Any]:
    identity = request_identity(request)
    job_id = str(uuid.uuid4())
    try:
        request_data = _request_to_simulation_payload(payload)
        authorize_runner_profile_execution(request_data)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    store = get_configured_job_store()
    store.create_job(
        job_id,
        request_data,
        status="submitted",
        tenant_id=identity.tenant_id,
    )
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
