from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-pocketmd-lite"])

ROOT = Path(__file__).resolve().parents[1]
POCKETMD_LITE_REPORT_ARTIFACT = ROOT / "runs" / "pocketmd_lite_report_current.json"
POCKETMD_LITE_REMAINING_QUEUE_ARTIFACT = ROOT / "runs" / "pocketmd_lite_remaining_evidence_queue_current.json"
POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT = ROOT / "runs" / "pocketmd_lite_topk_refinement_audit_current.json"

_REPORT_CLAIM_BOUNDARY_MISSING = (
    "PocketMD Lite report endpoint only; the local report artifact is missing or invalid. "
    "It does not run local-min, micro-MD, docking, emit scientific results, or mutate external state. "
    "PocketMD Lite is top-k-only refinement evidence, not a binding-affinity claim."
)

_QUEUE_CLAIM_BOUNDARY_MISSING = (
    "PocketMD Lite remaining evidence queue endpoint only; the local queue artifact is missing or invalid. "
    "It does not run local-min, micro-MD, H-bond scoring, docking, emit scientific results, or mutate external state."
)

_TOPK_AUDIT_CLAIM_BOUNDARY_MISSING = (
    "PocketMD Lite top-k refinement audit endpoint only; the local audit artifact is missing or invalid. "
    "It does not run local-min, micro-MD, H-bond scoring, docking, emit scientific results, promote claims, "
    "or mutate external state. Proxy telemetry cannot satisfy claim-grade refinement evidence."
)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@router.get("/pocketmd-lite-report")
async def get_product_pocketmd_lite_report() -> dict[str, Any]:
    """Return the read-only PocketMD Lite top-k refinement report surface."""

    artifact = _read_json_object(POCKETMD_LITE_REPORT_ARTIFACT)
    summary = artifact.get("summary") if isinstance(artifact.get("summary"), dict) else {}
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_pocketmd_lite_report",
            "artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
            "candidate_count": 0,
            "selected_top_k_count": 0,
            "refinement_blocker_count": 0,
            "pocketmd_lite_claim_safe": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "candidates": [],
            "claim_boundary": _REPORT_CLAIM_BOUNDARY_MISSING,
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "selected_top_k_count": int(summary.get("selected_top_k_count") or 0),
        "refinement_blocker_count": int(summary.get("refinement_blocker_count") or 0),
        "pocketmd_lite_claim_safe": bool(summary.get("pocketmd_lite_claim_safe") is True),
        "band_counts": summary.get("band_counts", {}),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "candidates": rows,
        "claim_boundary": artifact.get("claim_boundary", ""),
    }


@router.get("/pocketmd-lite-remaining-evidence-queue")
async def get_product_pocketmd_lite_remaining_evidence_queue() -> dict[str, Any]:
    """Return the read-only PocketMD Lite remaining evidence queue surface."""

    artifact = _read_json_object(POCKETMD_LITE_REMAINING_QUEUE_ARTIFACT)
    summary = artifact.get("summary") if isinstance(artifact.get("summary"), dict) else {}
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_pocketmd_lite_remaining_evidence_queue",
            "artifact_path": str(POCKETMD_LITE_REMAINING_QUEUE_ARTIFACT),
            "candidate_count": 0,
            "selected_top_k_count": 0,
            "remaining_candidate_count": 0,
            "remaining_metric_count": 0,
            "missing_metric_names": [],
            "trajectory_npz_unavailable_count": 0,
            "protein_structure_source_path_unavailable_count": 0,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "rows": [],
            "claim_boundary": _QUEUE_CLAIM_BOUNDARY_MISSING,
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(POCKETMD_LITE_REMAINING_QUEUE_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "selected_top_k_count": int(summary.get("selected_top_k_count") or 0),
        "remaining_candidate_count": int(summary.get("remaining_candidate_count") or 0),
        "remaining_metric_count": int(summary.get("remaining_metric_count") or 0),
        "missing_metric_names": summary.get("missing_metric_names", []),
        "trajectory_npz_unavailable_count": int(summary.get("trajectory_npz_unavailable_count") or 0),
        "protein_structure_source_path_unavailable_count": int(
            summary.get("protein_structure_source_path_unavailable_count") or 0
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "rows": rows,
        "claim_boundary": artifact.get("claim_boundary", ""),
    }


@router.get("/pocketmd-lite-topk-refinement-audit")
async def get_product_pocketmd_lite_topk_refinement_audit() -> dict[str, Any]:
    """Return the read-only PocketMD Lite top-k refinement audit surface."""

    artifact = _read_json_object(POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT)
    summary = artifact.get("summary") if isinstance(artifact.get("summary"), dict) else {}
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_pocketmd_lite_topk_refinement_audit",
            "artifact_path": str(POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT),
            "candidate_count": 0,
            "selected_top_k_count": 0,
            "claim_grade_refinement_evidence_ready": False,
            "claim_grade_report_evidence_ready": False,
            "proxy_topk_telemetry_ready": False,
            "claim_grade_metric_ready_count": 0,
            "claim_grade_missing_candidate_count": 0,
            "missing_refinement_metric_names": [],
            "missing_refinement_metric_counts": {},
            "claim_promotion_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "rows": [],
            "claim_boundary": _TOPK_AUDIT_CLAIM_BOUNDARY_MISSING,
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "selected_top_k_count": int(summary.get("selected_top_k_count") or 0),
        "claim_grade_refinement_evidence_ready": bool(
            summary.get("claim_grade_refinement_evidence_ready") is True
        ),
        "claim_grade_report_evidence_ready": bool(summary.get("claim_grade_report_evidence_ready") is True),
        "proxy_topk_telemetry_ready": bool(summary.get("proxy_topk_telemetry_ready") is True),
        "claim_grade_metric_ready_count": int(summary.get("claim_grade_metric_ready_count") or 0),
        "claim_grade_missing_candidate_count": int(summary.get("claim_grade_missing_candidate_count") or 0),
        "missing_refinement_metric_names": summary.get("missing_refinement_metric_names", []),
        "missing_refinement_metric_counts": summary.get("missing_refinement_metric_counts", {}),
        "claim_promotion_allowed": bool(summary.get("claim_promotion_allowed") is True),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "rows": rows,
        "claim_boundary": artifact.get("claim_boundary", ""),
    }
