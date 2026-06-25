from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-service-contracts"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SERVICE_BOUNDARY_ARTIFACT = ROOT / "runs" / "product_service_boundary_contract_current.json"
PRODUCT_API_CONTRACT_ARTIFACT = ROOT / "runs" / "product_api_contract_current.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


@router.get("/service-boundary")
async def get_product_service_boundary() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SERVICE_BOUNDARY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_service_boundary_contract",
            "artifact_path": str(PRODUCT_SERVICE_BOUNDARY_ARTIFACT),
            "service_boundary_ready": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product service-boundary endpoint only; the local service-boundary contract is missing or invalid. "
                "It does not run docking, write licenses, assemble bundles, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_SERVICE_BOUNDARY_ARTIFACT),
        "service_boundary_ready": bool(summary.get("service_boundary_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "api_route_count": int(summary.get("api_route_count") or 0),
        "expected_api_route_count": int(summary.get("expected_api_route_count") or 0),
        "cli_command_count": int(summary.get("cli_command_count") or 0),
        "expected_cli_command_count": int(summary.get("expected_cli_command_count") or 0),
        "artifact_registry_mismatch_count": int(summary.get("artifact_registry_mismatch_count") or 0),
        "console_script_ready": bool(summary.get("console_script_ready") is True),
        "checks": rows,
        "blockers": blockers,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/api-contract")
async def get_product_api_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_API_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_api_contract",
            "artifact_path": str(PRODUCT_API_CONTRACT_ARTIFACT),
            "api_contract_ready": False,
            "check_count": 0,
            "blocker_count": 1,
            "server_started": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product API contract endpoint only; the local API contract artifact is missing or invalid. "
                "It does not start a server, run docking, write licenses, assemble bundles, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_API_CONTRACT_ARTIFACT),
        "api_contract_ready": bool(summary.get("api_contract_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "expected_route_count": int(summary.get("expected_route_count") or 0),
        "missing_route_count": int(summary.get("missing_route_count") or 0),
        "request_model_count": int(summary.get("request_model_count") or 0),
        "missing_request_model_field_count": int(summary.get("missing_request_model_field_count") or 0),
        "docking_response_missing_key_count": int(summary.get("docking_response_missing_key_count") or 0),
        "status_response_missing_key_count": int(summary.get("status_response_missing_key_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "server_started": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
