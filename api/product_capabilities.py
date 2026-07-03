from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-capabilities"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CAPABILITY_ARTIFACT = ROOT / "runs" / "product_capability_surface_contract_current.json"


CLAIM_BOUNDARY = (
    "Product capability endpoint only; reads the local capability surface artifact and renders "
    "dashboard-safe capability and evidence surface rows. It does not run docking, emit scientific "
    "results, approve claims, or mutate external state."
)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _capability_rows(value: Any, *, claim_boundary: str) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    capability_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        capability_rows.append(
            {
                "capability_id": str(row.get("capability_id") or ""),
                "domain": str(row.get("domain") or ""),
                "status": str(row.get("status") or ""),
                "required": str(row.get("required") or ""),
                "release_blocker": _bool_true(row.get("release_blocker")),
                "artifact_path": str(row.get("artifact_path") or ""),
                "observed": str(row.get("observed") or ""),
                "reason": str(row.get("reason") or ""),
                "bundle_assembled": _bool_true(row.get("bundle_assembled")),
                "docking_results_emitted": False,
                "claim_boundary": str(row.get("claim_boundary") or claim_boundary),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return capability_rows


def _evidence_surface_rows(value: Any, *, claim_boundary: str) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    surface_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        surface_rows.append(
            {
                "capability_id": str(row.get("capability_id") or ""),
                "surface": str(row.get("surface") or ""),
                "route": str(row.get("route") or ""),
                "artifact": str(row.get("artifact") or ""),
                "artifact_present": _bool_true(row.get("artifact_present")),
                "surface_available": _bool_true(row.get("surface_available")),
                "claim_type": str(row.get("claim_type") or ""),
                "claim_status": str(row.get("claim_status") or ""),
                "claim_safe": _bool_true(row.get("claim_safe")),
                "bundle_surfaces": _string_list(row.get("bundle_surfaces")),
                "claim_boundary": str(row.get("claim_boundary") or claim_boundary),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return surface_rows


@router.get("/capabilities")
async def get_product_capabilities() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_CAPABILITY_ARTIFACT)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    if not summary:
        return {
            "status": "missing_product_capability_surface_contract",
            "artifact_path": str(PRODUCT_CAPABILITY_ARTIFACT),
            "capability_count": 0,
            "ready_capability_count": 0,
            "blocked_capability_count": 1,
            "capability_row_count": 0,
            "capability_blocker_row_count": 0,
            "capability_rows": [],
            "capabilities": [],
            "allowed_scope_families": [],
            "restricted_scope_claim_guard_ready": False,
            "blocked_claim_scopes": ["capability_surface_contract_missing"],
            "general_platform_claim_allowed": False,
            "scope_claim_boundary_detail": "missing_product_capability_surface_contract",
            "evidence_surfaces": [],
            "evidence_surface_count": 0,
            "evidence_surface_row_count": 0,
            "evidence_surface_claim_locked_row_count": 0,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    claim_boundary = str(summary.get("claim_boundary") or CLAIM_BOUNDARY)
    capability_rows = _capability_rows(packet.get("rows"), claim_boundary=claim_boundary)
    evidence_surfaces = _evidence_surface_rows(
        packet.get("evidence_surfaces"),
        claim_boundary=claim_boundary,
    )
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_CAPABILITY_ARTIFACT),
        "target_id": summary.get("target_id", ""),
        "family": summary.get("family", ""),
        "ligand_count": _int(summary.get("ligand_count")),
        "capability_count": _int(summary.get("capability_count")),
        "ready_capability_count": _int(summary.get("ready_capability_count")),
        "blocked_capability_count": _int(summary.get("blocked_capability_count")),
        "capability_row_count": len(capability_rows),
        "capability_blocker_row_count": sum(
            1 for row in capability_rows if row["release_blocker"] is True
        ),
        "capability_rows": capability_rows,
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
        "evidence_surface_count": _int(summary.get("evidence_surface_count")) or len(evidence_surfaces),
        "evidence_surface_row_count": len(evidence_surfaces),
        "evidence_surface_claim_locked_row_count": sum(
            1 for row in evidence_surfaces if row["claim_safe"] is not True
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "capabilities": capability_rows,
        "claim_boundary": claim_boundary,
    }
