# api/models.py

from pydantic import BaseModel
from typing import Optional

class SimulationRequest(BaseModel):
    pdb_id: Optional[str] = None  # PDB ID
    pdb_content: Optional[str] = None  # PDB 파일 내용 (Base64 encoded string or plain text)
    target_name: str  # e.g., "Chignolin"
    steps: int = 1000
    ai_model_path: Optional[str] = None # Path to specific AI model to use
    output_format: str = "pdb" # "pdb", "traj", etc.

class SimulationResponse(BaseModel):
    job_id: str
    status: str # "submitted", "running", "completed", "failed"
    message: str

class StatusResponse(BaseModel):
    job_id: str
    status: str # "running", "completed", "failed"
    progress: Optional[float] = None # 0.0 to 1.0
    message: Optional[str] = None

class ResultsResponse(BaseModel):
    job_id: str
    status: str # "completed", "failed"
    result_url: Optional[str] = None # URL to download results
    message: Optional[str] = None
