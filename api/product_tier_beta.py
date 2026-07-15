from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
) -> dict[str, Any]:
    del payload
    raise HTTPException(
        status_code=503,
        detail={
            "error": "tier_beta_customer_execution_disabled",
            "workflow_id": TIER_BETA_WORKFLOW_ID,
            "runner_profile_id": TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
            "execution_enabled": False,
            "customer_execution_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Tier-beta remains an operator-only restricted profile; customer "
                "submission and pose emission are disabled."
            ),
        },
    )
