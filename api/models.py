# api/models.py

from pydantic import BaseModel, Field, model_validator
from typing import Any, Optional

from api.simulation_scope import RUNNER_PROFILE_REQUIRED_DETAIL


class SimulationRequest(BaseModel):
    """Ligand validated-runner job request. Generic MD simulation is not supported."""

    runner_profile_id: str = Field(
        ...,
        description=(
            "Required operator-approved validated runner profile id "
            "(ligand HTVS or backmapping scoring)."
        ),
    )
    target_name: str  # e.g., "Chignolin"
    runner_profile_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata only; profile controls runner arguments.",
    )
    pdb_id: Optional[str] = None  # Deprecated for generic MD; retained for profile metadata only
    pdb_content: Optional[str] = None
    steps: int = 1000
    ai_model_path: Optional[str] = None
    output_format: str = "pdb"

    @model_validator(mode="after")
    def _runner_profile_required(self) -> "SimulationRequest":
        if not str(self.runner_profile_id or "").strip():
            raise ValueError(RUNNER_PROFILE_REQUIRED_DETAIL)
        return self

class SimulationResponse(BaseModel):
    job_id: str
    status: str # "submitted", "running", "completed", "failed"
    message: str

class StatusResponse(BaseModel):
    job_id: str
    status: str # "running", "completed", "failed"
    progress: Optional[float] = None # 0.0 to 1.0
    message: Optional[str] = None
    result_manifest: Optional[str] = None
    evidence_bundle: Optional[str] = None
    evidence_bundle_sha256: Optional[str] = None

class ResultsResponse(BaseModel):
    job_id: str
    status: str # "completed", "failed"
    result_url: Optional[str] = None # URL to download results
    message: Optional[str] = None
