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
POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT = (
    ROOT / "runs" / "pocketmd_lite_candidate_metric_fill_preview_report_current.json"
)

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

_PREVIEW_REPORT_CLAIM_BOUNDARY_MISSING = (
    "PocketMD Lite candidate metric fill-preview report endpoint only; the local preview report artifact is "
    "missing or invalid. It does not mutate the canonical candidate CSV, approve customer-facing PocketMD Lite "
    "wording, run local-min, micro-MD, docking, emit scientific results, or mutate external state."
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
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    return []


def _row_values(rows: list[Any], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get(field)
        if value in ("", None):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _row_sum(rows: list[Any], field: str) -> float:
    return sum(_row_values(rows, field))


def _row_max(rows: list[Any], field: str) -> float:
    values = _row_values(rows, field)
    return max(values) if values else 0.0


def _row_min(rows: list[Any], field: str) -> float:
    values = _row_values(rows, field)
    return min(values) if values else 0.0


@router.get("/pocketmd-lite-report")
async def get_product_pocketmd_lite_report() -> dict[str, Any]:
    """Return the read-only PocketMD Lite top-k refinement report surface."""

    artifact = _read_json_object(POCKETMD_LITE_REPORT_ARTIFACT)
    summary = _summary(artifact)
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_pocketmd_lite_report",
            "artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
            "candidate_count": 0,
            "selected_top_k_count": 0,
            "refinement_blocker_count": 0,
            "pocketmd_lite_claim_safe": False,
            "top_k_refinement_evidence_ready": False,
            "claim_grade_metric_ready_row_count": 0,
            "green_row_count": 0,
            "yellow_row_count": 0,
            "red_row_count": 0,
            "abstain_row_count": 0,
            "missing_refinement_metric_names": [],
            "missing_refinement_metric_counts": {},
            "next_required_step": "",
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
        "top_k_refinement_evidence_ready": bool(
            summary.get("top_k_refinement_evidence_ready") is True
        ),
        "claim_grade_metric_ready_row_count": _int(
            summary.get("claim_grade_metric_ready_row_count")
        ),
        "band_counts": summary.get("band_counts", {}),
        "green_row_count": _int(summary.get("green_row_count")),
        "yellow_row_count": _int(summary.get("yellow_row_count")),
        "red_row_count": _int(summary.get("red_row_count")),
        "abstain_row_count": _int(summary.get("abstain_row_count")),
        "missing_refinement_metric_names": _string_list(
            summary.get("missing_refinement_metric_names")
        ),
        "missing_refinement_metric_counts": (
            summary.get("missing_refinement_metric_counts")
            if isinstance(summary.get("missing_refinement_metric_counts"), dict)
            else {}
        ),
        "green_band_condition_text": str(summary.get("green_band_condition_text") or ""),
        "next_required_step": str(summary.get("next_required_step") or ""),
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


@router.get("/pocketmd-lite-candidate-metric-fill-preview-report")
async def get_product_pocketmd_lite_candidate_metric_fill_preview_report() -> dict[str, Any]:
    """Return the read-only PocketMD Lite candidate metric fill-preview report surface."""

    artifact = _read_json_object(POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT)
    summary = _summary(artifact)
    canonical_artifact = _read_json_object(POCKETMD_LITE_REPORT_ARTIFACT)
    canonical = _summary(canonical_artifact)
    audit = _summary(_read_json_object(POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT))
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_pocketmd_lite_candidate_metric_fill_preview_report",
            "artifact_path": str(POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT),
            "canonical_report_artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
            "canonical_report_status": "",
            "canonical_report_ready": False,
            "canonical_pocketmd_lite_claim_safe": False,
            "canonical_abstain_row_count": 0,
            "canonical_missing_refinement_metric_names": [],
            "canonical_missing_refinement_metric_counts": {},
            "canonical_review_required": False,
            "canonical_candidate_csv_mutated": False,
            "preview_report_ready": False,
            "preview_requires_canonical_review": False,
            "candidate_count": 0,
            "selected_top_k_count": 0,
            "preview_pocketmd_lite_claim_safe": False,
            "pocketmd_lite_claim_safe": False,
            "claim_grade_metric_ready_row_count": 0,
            "band_counts": {},
            "green_row_count": 0,
            "yellow_row_count": 0,
            "red_row_count": 0,
            "abstain_row_count": 0,
            "local_min_ligand_rmsd_a_max": 0.0,
            "hbond_persistence_min": 0.0,
            "contact_persistence_min": 0.0,
            "initial_clash_count_total": 0.0,
            "final_clash_count_total": 0.0,
            "clash_relief_count_total": 0.0,
            "green_band_condition_text": "",
            "claim_promotion_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "candidates": [],
            "claim_boundary": _PREVIEW_REPORT_CLAIM_BOUNDARY_MISSING,
        }
    preview_ready = bool(
        summary.get("status") == "pocketmd_lite_report_ready"
        and summary.get("top_k_refinement_evidence_ready") is True
    )
    canonical_ready = bool(
        canonical.get("status") == "pocketmd_lite_report_ready"
        and canonical.get("top_k_refinement_evidence_ready") is True
        and canonical.get("pocketmd_lite_claim_safe") is True
    )
    return {
        "status": summary.get("status"),
        "artifact_path": str(POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT),
        "canonical_report_artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
        "canonical_report_status": str(canonical.get("status") or ""),
        "canonical_report_ready": canonical_ready,
        "canonical_pocketmd_lite_claim_safe": bool(
            canonical.get("pocketmd_lite_claim_safe") is True
        ),
        "canonical_abstain_row_count": _int(canonical.get("abstain_row_count")),
        "canonical_missing_refinement_metric_names": _string_list(
            canonical.get("missing_refinement_metric_names")
        ),
        "canonical_missing_refinement_metric_counts": (
            canonical.get("missing_refinement_metric_counts")
            if isinstance(canonical.get("missing_refinement_metric_counts"), dict)
            else {}
        ),
        "canonical_review_required": bool(preview_ready and not canonical_ready),
        "canonical_candidate_csv_mutated": bool(
            audit.get("candidate_metric_fill_preview_canonical_candidate_csv_mutated") is True
        ),
        "schema_version": summary.get("schema_version", ""),
        "preview_report_ready": preview_ready,
        "preview_requires_canonical_review": True,
        "candidate_count": int(summary.get("candidate_count") or 0),
        "selected_top_k_count": int(summary.get("selected_top_k_count") or 0),
        "preview_pocketmd_lite_claim_safe": bool(summary.get("pocketmd_lite_claim_safe") is True),
        "pocketmd_lite_claim_safe": False,
        "claim_grade_metric_ready_row_count": _int(
            summary.get("claim_grade_metric_ready_row_count")
        ),
        "band_counts": summary.get("band_counts", {}),
        "green_row_count": _int(summary.get("green_row_count")),
        "yellow_row_count": _int(summary.get("yellow_row_count")),
        "red_row_count": _int(summary.get("red_row_count")),
        "abstain_row_count": _int(summary.get("abstain_row_count")),
        "local_min_ligand_rmsd_a_max": _row_max(rows, "local_min_ligand_rmsd_a"),
        "hbond_persistence_min": _row_min(rows, "hbond_persistence"),
        "contact_persistence_min": _row_min(rows, "contact_persistence"),
        "initial_clash_count_total": _row_sum(rows, "initial_clash_count"),
        "final_clash_count_total": _row_sum(rows, "clash_count"),
        "clash_relief_count_total": _row_sum(rows, "clash_relief_count"),
        "green_band_condition_text": str(summary.get("green_band_condition_text") or ""),
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "candidates": rows,
        "claim_boundary": summary.get("claim_boundary") or artifact.get("claim_boundary", ""),
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
            "claim_grade_band_counts": {},
            "green_row_count": 0,
            "yellow_row_count": 0,
            "red_row_count": 0,
            "abstain_row_count": 0,
            "claim_grade_fill_preview_evidence_ready": False,
            "claim_grade_local_min_reported_count": 0,
            "claim_grade_local_min_survival_count": 0,
            "claim_grade_hbond_reported_count": 0,
            "claim_grade_contact_reported_count": 0,
            "claim_grade_initial_clash_reported_count": 0,
            "claim_grade_final_clash_reported_count": 0,
            "claim_grade_clash_relief_reported_count": 0,
            "local_min_ligand_rmsd_a_max": 0.0,
            "hbond_persistence_min": 0.0,
            "contact_persistence_min": 0.0,
            "initial_clash_count_total": 0.0,
            "final_clash_count_total": 0.0,
            "clash_relief_count_total": 0.0,
            "missing_refinement_metric_names": [],
            "missing_refinement_metric_counts": {},
            "green_band_condition_text": "",
            "top_k_only_policy_enforced": False,
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
        "claim_grade_metric_ready_count": _int(summary.get("claim_grade_metric_ready_count")),
        "claim_grade_missing_candidate_count": _int(summary.get("claim_grade_missing_candidate_count")),
        "claim_grade_band_counts": summary.get("claim_grade_band_counts", {}),
        "green_row_count": _int(summary.get("green_row_count")),
        "yellow_row_count": _int(summary.get("yellow_row_count")),
        "red_row_count": _int(summary.get("red_row_count")),
        "abstain_row_count": _int(summary.get("abstain_row_count")),
        "claim_grade_fill_preview_evidence_ready": bool(
            summary.get("claim_grade_fill_preview_evidence_ready") is True
        ),
        "claim_grade_local_min_reported_count": _int(
            summary.get("claim_grade_local_min_reported_count")
        ),
        "claim_grade_local_min_survival_count": _int(
            summary.get("claim_grade_local_min_survival_count")
        ),
        "claim_grade_hbond_reported_count": _int(summary.get("claim_grade_hbond_reported_count")),
        "claim_grade_contact_reported_count": _int(summary.get("claim_grade_contact_reported_count")),
        "claim_grade_initial_clash_reported_count": _int(
            summary.get("claim_grade_initial_clash_reported_count")
        ),
        "claim_grade_final_clash_reported_count": _int(
            summary.get("claim_grade_final_clash_reported_count")
        ),
        "claim_grade_clash_relief_reported_count": _int(
            summary.get("claim_grade_clash_relief_reported_count")
        ),
        "local_min_ligand_rmsd_a_max": _row_max(rows, "local_min_ligand_rmsd_a"),
        "hbond_persistence_min": _row_min(rows, "hbond_persistence"),
        "contact_persistence_min": _row_min(rows, "contact_persistence"),
        "initial_clash_count_total": _row_sum(rows, "initial_clash_count"),
        "final_clash_count_total": _row_sum(rows, "clash_count"),
        "clash_relief_count_total": _row_sum(rows, "clash_relief_count"),
        "missing_refinement_metric_names": summary.get("missing_refinement_metric_names", []),
        "missing_refinement_metric_counts": summary.get("missing_refinement_metric_counts", {}),
        "green_band_condition_text": str(summary.get("green_band_condition_text") or ""),
        "top_k_only_policy_enforced": bool(summary.get("top_k_only_policy_enforced") is True),
        "claim_promotion_allowed": bool(summary.get("claim_promotion_allowed") is True),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "rows": rows,
        "claim_boundary": artifact.get("claim_boundary", ""),
    }
