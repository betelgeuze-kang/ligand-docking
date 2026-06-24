"""Bridge validated docking ledger entries to HTVS worker dispatch manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROADMAP_ARTIFACT = ROOT / "runs" / "independent_engine_roadmap_status_current.json"
DEFAULT_RUNNER_PROFILE = "ligand_htvs_pipeline_default"
DEFAULT_EXECUTION_MODE = "smoke"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def engine_roadmap_ready() -> bool:
    payload = _read_json(ENGINE_ROADMAP_ARTIFACT)
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        return False
    return str(summary.get("status", "")).strip() == "independent_engine_roadmap_closed"


def build_dispatch_manifest(
    *,
    job_id: str,
    target_id: str,
    family: str,
    runner_profile_id: str = DEFAULT_RUNNER_PROFILE,
    ligand_model_hint: str = "auto",
    execution_mode: str = DEFAULT_EXECUTION_MODE,
    customer_submission_allowed: bool = False,
    synthetic_input_allowed: bool = True,
    production_claim_allowed: bool = False,
    customer_pose_emission_allowed: bool = False,
) -> dict[str, Any]:
    ready = engine_roadmap_ready()
    return {
        "job_id": str(job_id),
        "target_id": str(target_id),
        "family": str(family),
        "runner_profile_id": str(runner_profile_id),
        "ligand_model_hint": str(ligand_model_hint),
        "runner_execution_contract_explicit": True,
        "execution_mode": str(execution_mode),
        "customer_submission_allowed": bool(customer_submission_allowed),
        "synthetic_input_allowed": bool(synthetic_input_allowed),
        "production_claim_allowed": bool(production_claim_allowed),
        "customer_pose_emission_allowed": bool(customer_pose_emission_allowed),
        "engine_roadmap_ready": bool(ready),
        "dispatch_ready": bool(ready),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scoped_execution_contract": (
            "Operator-approved runner dispatch only. Smoke and restricted-production modes are explicit. "
            "Customer pose emission remains gated until delivery bundle validation is green."
        ),
        "pipeline_entrypoints": [
            "tools/run_ligand_htvs_pipeline.py",
            "tools/run_ligand_backmapping_scoring.py",
            "tools/run_ligand_topk_delivery.py",
        ],
    }


def write_dispatch_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
