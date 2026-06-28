from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-capabilities"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CAPABILITY_ARTIFACT = ROOT / "runs" / "product_capability_surface_contract_current.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@router.get("/capabilities")
async def get_product_capabilities() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_CAPABILITY_ARTIFACT)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    evidence_surfaces = packet.get("evidence_surfaces") if isinstance(packet.get("evidence_surfaces"), list) else []
    if not summary:
        return {
            "status": "missing_product_capability_surface_contract",
            "artifact_path": str(PRODUCT_CAPABILITY_ARTIFACT),
            "capability_count": 0,
            "ready_capability_count": 0,
            "blocked_capability_count": 1,
            "allowed_scope_families": [],
            "restricted_scope_claim_guard_ready": False,
            "blocked_claim_scopes": ["capability_surface_contract_missing"],
            "general_platform_claim_allowed": False,
            "scope_claim_boundary_detail": "missing_product_capability_surface_contract",
            "evidence_surfaces": [],
            "evidence_surface_count": 0,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product capability endpoint only; the local capability surface artifact is missing or invalid. "
                "It does not run docking, emit scientific results, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_CAPABILITY_ARTIFACT),
        "target_id": summary.get("target_id", ""),
        "family": summary.get("family", ""),
        "ligand_count": int(summary.get("ligand_count") or 0),
        "capability_count": int(summary.get("capability_count") or 0),
        "ready_capability_count": int(summary.get("ready_capability_count") or 0),
        "blocked_capability_count": int(summary.get("blocked_capability_count") or 0),
        "structure_analysis_capability_ready": bool(summary.get("structure_analysis_capability_ready") is True),
        "ligand_docking_capability_ready": bool(summary.get("ligand_docking_capability_ready") is True),
        "local_delivery_bundle_capability_ready": bool(summary.get("local_delivery_bundle_capability_ready") is True),
        "api_surface_ready": bool(summary.get("api_surface_ready") is True),
        "product_service_boundary_endpoint_present": bool(
            summary.get("product_service_boundary_endpoint_present") is True
        ),
        "product_api_contract_endpoint_present": bool(summary.get("product_api_contract_endpoint_present") is True),
        "guarded_claims_ready": bool(summary.get("guarded_claims_ready") is True),
        "allowed_scope_families": summary.get("allowed_scope_families", []),
        "restricted_scope_claim_guard_ready": bool(summary.get("restricted_scope_claim_guard_ready") is True),
        "blocked_claim_scopes": summary.get("blocked_claim_scopes", []),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "restricted_unattended_execution_ready": bool(summary.get("restricted_unattended_execution_ready") is True),
        "restricted_unattended_execution_runtime_ready": bool(
            summary.get("restricted_unattended_execution_runtime_ready") is True
        ),
        "scope_claim_boundary_detail": summary.get("scope_claim_boundary_detail", ""),
        "evidence_surfaces": evidence_surfaces,
        "evidence_surface_count": int(summary.get("evidence_surface_count") or len(evidence_surfaces)),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "capabilities": rows,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
