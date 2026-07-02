from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-operator-cockpit"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_OPERATOR_COCKPIT_ARTIFACT = ROOT / "runs" / "product_operator_cockpit_current.json"

CLAIM_BOUNDARY = (
    "Product operator cockpit endpoint only; it reads the local cockpit artifact and renders operator-facing "
    "status, panel rows, and claim boundaries. It does not run docking, run MD, build bundles, approve claims, "
    "upload, email, delete, commit, push, deploy, or mutate external state."
)


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


def _list(packet: dict[str, Any], key: str) -> list[Any]:
    value = packet.get(key)
    return list(value) if isinstance(value, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _missing_response() -> dict[str, Any]:
    return {
        "status": "missing_product_operator_cockpit",
        "artifact_path": str(PRODUCT_OPERATOR_COCKPIT_ARTIFACT),
        "phase8_surface_ready": False,
        "required_phase8_panel_count": 9,
        "observed_phase8_panel_count": 0,
        "missing_required_phase8_panel_count": 9,
        "missing_required_phase8_panel_ids": [
            "product_capabilities_dashboard",
            "goal_readiness_dashboard",
            "hbond_backmap_candidate_table",
            "gpcr_hard_decoy_blocker_panel",
            "pocketmd_lite_report_panel",
            "public_benchmark_scorecard",
            "release_blockers_operator_actions",
            "evidence_bundle_export",
            "claim_boundary_matrix",
        ],
        "source_artifact_ready_panel_count": 0,
        "source_artifact_blocked_panel_count": 9,
        "source_artifact_blocked_panel_ids": [],
        "operator_action_required_panel_count": 9,
        "operator_action_required_panel_ids": [],
        "paid_pilot_wording_allowed": False,
        "general_platform_claim_allowed": False,
        "gpcr_hard_decoy_metric_ready": False,
        "gpcr_broad_claim_allowed": False,
        "pocketmd_lite_refinement_evidence_ready": False,
        "pocketmd_lite_claim_allowed": False,
        "public_benchmark_claim_allowed": False,
        "public_benchmark_receipt_attach_packet_ready": False,
        "public_benchmark_receipt_attach_packet_present": False,
        "public_benchmark_vina_gnina_pending_score_count": 0,
        "public_benchmark_metric_source_pending_field_count": 0,
        "public_benchmark_metric_source_pending_approval_token_count": 0,
        "evidence_bundle_export_ready": False,
        "customer_shadow_paid_pilot_evidence_ready": False,
        "release_allowed": False,
        "panels": [],
        "claim_matrix": [],
        "next_required_step": "Run python3 tools/product/build_product_operator_cockpit.py.",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


@router.get("/operator-cockpit")
async def get_product_operator_cockpit() -> dict[str, Any]:
    """Return the read-only Product Operator Cockpit surface.

    Exposes the local ``runs/product_operator_cockpit_current.json`` artifact so
    the GUI/operator API can inspect Phase 8 panels and allowed/disallowed claim
    text without running scientific workloads or promoting claims.
    """

    packet = _read_json_object(PRODUCT_OPERATOR_COCKPIT_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return _missing_response()

    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_OPERATOR_COCKPIT_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        "phase8_surface_ready": bool(summary.get("phase8_surface_ready") is True),
        "required_phase8_panel_count": _int(summary.get("required_phase8_panel_count")),
        "required_phase8_panel_ids": _string_list(summary.get("required_phase8_panel_ids")),
        "observed_phase8_panel_count": _int(summary.get("observed_phase8_panel_count")),
        "missing_required_phase8_panel_count": _int(summary.get("missing_required_phase8_panel_count")),
        "missing_required_phase8_panel_ids": _string_list(summary.get("missing_required_phase8_panel_ids")),
        "surface_ready_panel_count": _int(summary.get("surface_ready_panel_count")),
        "source_artifact_ready_panel_count": _int(summary.get("source_artifact_ready_panel_count")),
        "source_artifact_blocked_panel_count": _int(summary.get("source_artifact_blocked_panel_count")),
        "source_artifact_blocked_panel_ids": _string_list(summary.get("source_artifact_blocked_panel_ids")),
        "operator_action_required_panel_count": _int(summary.get("operator_action_required_panel_count")),
        "operator_action_required_panel_ids": _string_list(summary.get("operator_action_required_panel_ids")),
        "allowed_claim_count": _int(summary.get("allowed_claim_count")),
        "disallowed_claim_count": _int(summary.get("disallowed_claim_count")),
        "paid_pilot_wording_allowed": bool(summary.get("paid_pilot_wording_allowed") is True),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "gpcr_hard_decoy_metric_ready": bool(summary.get("gpcr_hard_decoy_metric_ready") is True),
        "gpcr_broad_claim_allowed": bool(summary.get("gpcr_broad_claim_allowed") is True),
        "pocketmd_lite_refinement_evidence_ready": bool(
            summary.get("pocketmd_lite_refinement_evidence_ready") is True
        ),
        "pocketmd_lite_claim_allowed": bool(summary.get("pocketmd_lite_claim_allowed") is True),
        "public_benchmark_claim_allowed": bool(summary.get("public_benchmark_claim_allowed") is True),
        "public_benchmark_receipt_attach_packet_ready": bool(
            summary.get("public_benchmark_receipt_attach_packet_ready") is True
        ),
        "public_benchmark_receipt_attach_packet_present": bool(
            summary.get("public_benchmark_receipt_attach_packet_present") is True
        ),
        "public_benchmark_vina_gnina_pending_score_count": _int(
            summary.get("public_benchmark_vina_gnina_pending_score_count")
        ),
        "public_benchmark_metric_source_pending_field_count": _int(
            summary.get("public_benchmark_metric_source_pending_field_count")
        ),
        "public_benchmark_metric_source_pending_approval_token_count": _int(
            summary.get("public_benchmark_metric_source_pending_approval_token_count")
        ),
        "evidence_bundle_export_ready": bool(summary.get("evidence_bundle_export_ready") is True),
        "customer_shadow_paid_pilot_evidence_ready": bool(
            summary.get("customer_shadow_paid_pilot_evidence_ready") is True
        ),
        "release_allowed": bool(summary.get("release_allowed") is True),
        "panels": _list(packet, "rows"),
        "claim_matrix": _list(packet, "claim_matrix"),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary") or CLAIM_BOUNDARY,
    }
