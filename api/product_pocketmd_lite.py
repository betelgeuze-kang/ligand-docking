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
POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_ARTIFACT = (
    ROOT / "runs" / "pocketmd_lite_claim_grade_metric_source_audit_current.json"
)
POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT = (
    ROOT / "runs" / "pocketmd_lite_candidate_metric_fill_preview_report_current.json"
)
POCKETMD_LITE_CANONICAL_REPORT_REVIEW_PACKET_ARTIFACT = (
    ROOT / "runs" / "pocketmd_lite_canonical_report_review_packet_current.json"
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

_METRIC_SOURCE_AUDIT_CLAIM_BOUNDARY_MISSING = (
    "PocketMD Lite claim-grade metric source audit endpoint only; the local audit artifact is missing or "
    "invalid. It does not run local-min, micro-MD, H-bond scoring, docking, copy metric payloads, update "
    "candidate CSVs, promote claims, or mutate external state."
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


def _float_or_none(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in ("", None):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


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


def _pocketmd_operator_action(row: dict[str, Any]) -> str:
    band = str(row.get("band") or "")
    missing = _string_list(row.get("missing_evidence_fields"))
    if missing:
        return "recover_exact_refinement_metric_fields"
    if band == "red":
        return "review_failed_local_refinement"
    if band == "yellow":
        return "review_medium_uncertainty_refinement"
    if band == "green":
        return "review_and_promote_to_canonical_report_if_approved"
    return "review_refinement_evidence"


def _report_rows(rows: list[Any]) -> list[dict[str, Any]]:
    report_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        missing = _string_list(row.get("missing_evidence_fields"))
        review_flags = _string_list(row.get("review_flags"))
        band = str(row.get("band") or "")
        claim_safe = bool(row.get("claim_safe") is True)
        operator_action_required = bool(band != "green" or missing or review_flags or not claim_safe)
        report_rows.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "family": str(row.get("family") or ""),
                "selected_for_refine": bool(row.get("selected_for_refine") is True),
                "band": band,
                "claim_safe": claim_safe,
                "local_min_ligand_rmsd_a": _float_or_none(
                    row.get("local_min_ligand_rmsd_a")
                ),
                "local_min_survived": _bool_or_none(row.get("local_min_survived")),
                "hbond_persistence": _float_or_none(row.get("hbond_persistence")),
                "contact_persistence": _float_or_none(row.get("contact_persistence")),
                "initial_clash_count": _int_or_none(row.get("initial_clash_count")),
                "final_clash_count": _int_or_none(row.get("clash_count")),
                "clash_relief_count": _int_or_none(row.get("clash_relief_count")),
                "evidence_completeness": _float_or_none(row.get("evidence_completeness")),
                "uncertainty_score": _float_or_none(row.get("uncertainty_score")),
                "uncertainty_posture": str(row.get("uncertainty_posture") or ""),
                "reason_code": str(row.get("reason_code") or ""),
                "missing_evidence_fields": missing,
                "review_flags": review_flags,
                "operator_action_required": operator_action_required,
                "recommended_next_action": _pocketmd_operator_action(row),
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        )
    return report_rows


def _metric_source_audit_rows(rows: list[Any]) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        selected_missing = _string_list(row.get("selected_missing_exact_metric_fields"))
        selected_exact_metric_ready = bool(row.get("selected_exact_metric_ready") is True)
        operator_action_required = bool(
            selected_missing or not selected_exact_metric_ready
        )
        audit_rows.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "target": str(row.get("target") or ""),
                "ligand_id": str(row.get("ligand_id") or ""),
                "required_metrics": _string_list(row.get("required_metrics")),
                "selected_npz_status": str(row.get("selected_npz_status") or ""),
                "selected_npz_schema": str(row.get("selected_npz_schema") or ""),
                "selected_exact_metric_ready": selected_exact_metric_ready,
                "selected_missing_exact_metric_fields": selected_missing,
                "selected_protein_atom_frame_count": _int(
                    row.get("selected_protein_atom_frame_count")
                ),
                "selected_ligand_atom_frame_count": _int(
                    row.get("selected_ligand_atom_frame_count")
                ),
                "searched_npz_candidate_count": _int(
                    row.get("searched_npz_candidate_count")
                ),
                "exact_metric_source_candidate_count": _int(
                    row.get("exact_metric_source_candidate_count")
                ),
                "atomized_protein_candidate_count": _int(
                    row.get("atomized_protein_candidate_count")
                ),
                "ligand_atom_candidate_count": _int(row.get("ligand_atom_candidate_count")),
                "claim_grade_collection_input_candidate_count": _int(
                    row.get("claim_grade_collection_input_candidate_count")
                ),
                "best_candidate_npz": str(row.get("best_candidate_npz") or ""),
                "best_candidate_status": str(row.get("best_candidate_status") or ""),
                "best_candidate_blockers": _string_list(row.get("best_candidate_blockers")),
                "recommended_next_local_action": str(
                    row.get("recommended_next_local_action") or ""
                ),
                "operator_action_required": operator_action_required,
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "refinement_execution_enabled": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        )
    return audit_rows


def _canonical_review_rows(rows: list[Any]) -> list[dict[str, Any]]:
    review_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        review_rows.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "review_ready": bool(row.get("review_ready") is True),
                "review_action": str(row.get("review_action") or ""),
                "metric_fill_status": str(row.get("metric_fill_status") or ""),
                "metric_source_npz": str(row.get("metric_source_npz") or ""),
                "canonical_band": str(row.get("canonical_band") or ""),
                "preview_band": str(row.get("preview_band") or ""),
                "canonical_claim_safe": bool(row.get("canonical_claim_safe") is True),
                "preview_claim_safe": bool(row.get("preview_claim_safe") is True),
                "canonical_missing_metric_names": _string_list(
                    row.get("canonical_missing_metric_names")
                ),
                "preview_missing_metric_names": _string_list(
                    row.get("preview_missing_metric_names")
                ),
                "canonical_update_candidate": bool(
                    row.get("canonical_update_candidate") is True
                ),
                "canonical_local_min_ligand_rmsd_a": _float_or_none(
                    row.get("canonical_local_min_ligand_rmsd_a")
                ),
                "preview_local_min_ligand_rmsd_a": _float_or_none(
                    row.get("preview_local_min_ligand_rmsd_a")
                ),
                "canonical_hbond_persistence": _float_or_none(
                    row.get("canonical_hbond_persistence")
                ),
                "preview_hbond_persistence": _float_or_none(
                    row.get("preview_hbond_persistence")
                ),
                "canonical_contact_persistence": _float_or_none(
                    row.get("canonical_contact_persistence")
                ),
                "preview_contact_persistence": _float_or_none(
                    row.get("preview_contact_persistence")
                ),
                "canonical_initial_clash_count": _int_or_none(
                    row.get("canonical_initial_clash_count")
                ),
                "preview_initial_clash_count": _int_or_none(
                    row.get("preview_initial_clash_count")
                ),
                "canonical_final_clash_count": _int_or_none(
                    row.get("canonical_clash_count")
                ),
                "preview_final_clash_count": _int_or_none(row.get("preview_clash_count")),
                "canonical_clash_relief_count": _int_or_none(
                    row.get("canonical_clash_relief_count")
                ),
                "preview_clash_relief_count": _int_or_none(
                    row.get("preview_clash_relief_count")
                ),
                "blockers": _string_list(row.get("blockers")),
                "operator_action_required": bool(row.get("review_ready") is not True),
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "refinement_execution_enabled": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        )
    return review_rows


def _canonical_report_review_surface(packet: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(packet)
    rows = _canonical_review_rows(
        packet.get("rows") if isinstance(packet.get("rows"), list) else []
    )
    return {
        "canonical_review_packet_artifact_path": str(
            POCKETMD_LITE_CANONICAL_REPORT_REVIEW_PACKET_ARTIFACT
        ),
        "canonical_review_packet_present": bool(summary),
        "canonical_review_packet_status": str(summary.get("status") or ""),
        "canonical_review_packet_ready": bool(
            summary.get("status") == "pocketmd_lite_canonical_report_review_packet_ready"
        ),
        "canonical_review_operator_approval_required": bool(
            summary.get("operator_approval_required") is True
        ),
        "canonical_review_approval_token_required": str(
            summary.get("approval_token_required") or ""
        ),
        "canonical_review_candidate_csv_update_allowed": False,
        "canonical_review_canonical_candidate_csv_mutated": bool(
            summary.get("canonical_candidate_csv_mutated") is True
        ),
        "canonical_review_canonical_candidate_csv": str(
            summary.get("canonical_candidate_csv") or ""
        ),
        "canonical_review_preview_candidate_csv": str(
            summary.get("preview_candidate_csv") or ""
        ),
        "canonical_review_review_row_count": _int(summary.get("review_row_count")),
        "canonical_review_ready_review_row_count": _int(
            summary.get("ready_review_row_count")
        ),
        "canonical_review_blocked_review_row_count": _int(
            summary.get("blocked_review_row_count")
        ),
        "canonical_review_selected_top_k_count": _int(
            summary.get("selected_top_k_count")
        ),
        "canonical_review_preview_report_ready": bool(
            summary.get("preview_report_ready") is True
        ),
        "canonical_review_preview_claim_safe": bool(
            summary.get("preview_claim_safe") is True
        ),
        "canonical_review_preview_green_row_count": _int(
            summary.get("preview_green_row_count")
        ),
        "canonical_review_preview_abstain_row_count": _int(
            summary.get("preview_abstain_row_count")
        ),
        "canonical_review_canonical_report_ready": bool(
            summary.get("canonical_report_ready") is True
        ),
        "canonical_review_canonical_claim_safe": bool(
            summary.get("canonical_claim_safe") is True
        ),
        "canonical_review_canonical_green_row_count": _int(
            summary.get("canonical_green_row_count")
        ),
        "canonical_review_canonical_abstain_row_count": _int(
            summary.get("canonical_abstain_row_count")
        ),
        "canonical_review_canonical_missing_refinement_metric_names": _string_list(
            summary.get("canonical_missing_refinement_metric_names")
        ),
        "canonical_review_metric_source_audit_ready": bool(
            summary.get("metric_source_audit_ready") is True
        ),
        "canonical_review_candidate_fill_preview_ready": bool(
            summary.get("candidate_fill_preview_ready") is True
        ),
        "canonical_review_next_required_step": str(
            summary.get("next_required_step") or ""
        ),
        "canonical_review_rows": rows,
        "canonical_review_claim_promotion_allowed": False,
        "canonical_review_refinement_execution_enabled": False,
        "canonical_review_execution_enabled": False,
        "canonical_review_external_state_mutated": False,
    }


def _report_blocker_rows(
    summary: dict[str, Any],
    report_rows: list[dict[str, Any]],
    preview_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    blocker_rows: list[dict[str, Any]] = []
    preview_ready = bool(
        preview_summary.get("status") == "pocketmd_lite_report_ready"
        and preview_summary.get("top_k_refinement_evidence_ready") is True
    )
    canonical_ready = bool(
        summary.get("status") == "pocketmd_lite_report_ready"
        and summary.get("top_k_refinement_evidence_ready") is True
        and summary.get("pocketmd_lite_claim_safe") is True
    )
    if not bool(summary.get("top_k_refinement_evidence_ready") is True):
        blocker_rows.append(
            {
                "blocker_id": "pocketmd_lite_top_k_refinement_evidence_not_ready",
                "blocker_type": "canonical_report_gate",
                "severity": "blocker",
                "operator_action": "recover_missing_claim_grade_refinement_metrics",
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    if not bool(summary.get("pocketmd_lite_claim_safe") is True):
        blocker_rows.append(
            {
                "blocker_id": "pocketmd_lite_claim_safe_false",
                "blocker_type": "canonical_report_gate",
                "severity": "blocker",
                "operator_action": "review_bands_and_missing_refinement_evidence",
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    for metric_name in _string_list(summary.get("missing_refinement_metric_names")):
        blocker_rows.append(
            {
                "blocker_id": f"missing_refinement_metric:{metric_name}",
                "blocker_type": "missing_metric",
                "severity": "blocker",
                "metric_name": metric_name,
                "missing_count": _int(
                    (summary.get("missing_refinement_metric_counts") or {}).get(metric_name)
                    if isinstance(summary.get("missing_refinement_metric_counts"), dict)
                    else 0
                ),
                "operator_action": "recover_exact_refinement_metric_fields",
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    for row in report_rows:
        if not row["operator_action_required"]:
            continue
        blocker_rows.append(
            {
                "blocker_id": f"candidate_refinement_evidence:{row['entry_id']}",
                "blocker_type": "candidate_metric_row",
                "severity": "blocker",
                "entry_id": row["entry_id"],
                "band": row["band"],
                "missing_evidence_fields": row["missing_evidence_fields"],
                "operator_action": row["recommended_next_action"],
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    if preview_ready and not canonical_ready:
        blocker_rows.append(
            {
                "blocker_id": "preview_metrics_require_canonical_review",
                "blocker_type": "canonical_review",
                "severity": "operator_review",
                "preview_green_row_count": _int(preview_summary.get("green_row_count")),
                "preview_claim_grade_metric_ready_row_count": _int(
                    preview_summary.get("claim_grade_metric_ready_row_count")
                ),
                "operator_action": "review_preview_report_and_update_canonical_candidate_csv",
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return blocker_rows


def _metric_source_audit_blocker_rows(
    summary: dict[str, Any],
    audit_rows: list[dict[str, Any]],
    canonical_summary: dict[str, Any],
    preview_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    blocker_rows: list[dict[str, Any]] = []
    audit_ready = bool(
        summary.get("status") == "pocketmd_lite_claim_grade_metric_source_audit_ready"
        and _int(summary.get("missing_exact_metric_source_count")) == 0
    )
    canonical_ready = bool(
        canonical_summary.get("status") == "pocketmd_lite_report_ready"
        and canonical_summary.get("top_k_refinement_evidence_ready") is True
        and canonical_summary.get("pocketmd_lite_claim_safe") is True
    )
    preview_ready = bool(
        preview_summary.get("status") == "pocketmd_lite_report_ready"
        and preview_summary.get("top_k_refinement_evidence_ready") is True
    )
    operator_row_count = sum(1 for row in audit_rows if row["operator_action_required"])
    if not audit_ready:
        blocker_rows.append(
            {
                "blocker_id": "pocketmd_lite_claim_grade_metric_source_audit_not_ready",
                "blocker_type": "metric_source_audit",
                "severity": "blocker",
                "operator_action": "recover_claim_grade_metric_sources_or_collection_inputs",
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    if operator_row_count:
        blocker_rows.append(
            {
                "blocker_id": "metric_source_extraction_required",
                "blocker_type": "operator_work_order",
                "severity": "operator_review",
                "affected_row_count": operator_row_count,
                "operator_action": "extract_exact_metric_fields_into_candidate_fill_preview",
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    if preview_ready and not canonical_ready:
        blocker_rows.append(
            {
                "blocker_id": "canonical_report_review_required",
                "blocker_type": "canonical_review",
                "severity": "operator_review",
                "operator_action": "review_preview_metrics_and_update_canonical_report_if_approved",
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    if not preview_ready:
        blocker_rows.append(
            {
                "blocker_id": "claim_grade_preview_report_not_ready",
                "blocker_type": "preview_report",
                "severity": "blocker",
                "operator_action": "run_candidate_metric_fill_preview_and_preview_report",
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return blocker_rows


def _claim_grade_readiness_rows(
    summary: dict[str, Any],
    preview_summary: dict[str, Any],
    preview_rows: list[Any],
) -> list[dict[str, Any]]:
    preview_ready = bool(
        preview_summary.get("status") == "pocketmd_lite_report_ready"
        and preview_summary.get("top_k_refinement_evidence_ready") is True
    )
    canonical_ready = bool(
        summary.get("status") == "pocketmd_lite_report_ready"
        and summary.get("top_k_refinement_evidence_ready") is True
        and summary.get("pocketmd_lite_claim_safe") is True
    )
    preview_candidate_count = _int(preview_summary.get("candidate_count")) or len(
        [row for row in preview_rows if isinstance(row, dict)]
    )
    required_metric_count = preview_candidate_count or 1
    local_min_values = _row_values(preview_rows, "local_min_ligand_rmsd_a")
    hbond_values = _row_values(preview_rows, "hbond_persistence")
    contact_values = _row_values(preview_rows, "contact_persistence")
    initial_clash_values = _row_values(preview_rows, "initial_clash_count")
    final_clash_values = _row_values(preview_rows, "clash_count")
    clash_relief_values = _row_values(preview_rows, "clash_relief_count")
    adrb2_green_count = sum(
        1
        for row in preview_rows
        if isinstance(row, dict)
        and "ADRB2" in str(row.get("entry_id") or "")
        and row.get("band") == "green"
        and row.get("claim_safe") is True
    )
    recovered_targets = {
        target_id
        for target_id in ("DRD3", "OPRD1")
        for row in preview_rows
        if isinstance(row, dict)
        and target_id in str(row.get("entry_id") or "")
        and row.get("band") == "green"
        and row.get("claim_safe") is True
    }
    rows: list[dict[str, Any]] = []

    def add_row(
        requirement_id: str,
        ready: bool,
        observed_value: str,
        required_value: str,
        blocker: str,
        operator_action: str,
    ) -> None:
        rows.append(
            {
                "requirement_id": requirement_id,
                "ready": ready,
                "observed_value": observed_value,
                "required_value": required_value,
                "blocker": "" if ready else blocker,
                "operator_action": "" if ready else operator_action,
                "claim_promotion_allowed": False,
                "candidate_csv_update_allowed": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        )

    add_row(
        "preview_claim_grade_metric_report_ready",
        preview_ready,
        str(preview_summary.get("status") or ""),
        "pocketmd_lite_report_ready",
        "preview_claim_grade_metric_report_not_ready",
        "Run the bounded metric collector, candidate fill preview, and preview report.",
    )
    add_row(
        "adrb2_three_collection_ready_rows",
        preview_ready and adrb2_green_count >= 3,
        str(adrb2_green_count),
        ">=3",
        f"adrb2_collection_ready_rows_below_required:{adrb2_green_count}/3",
        "Recover or rerun bounded metrics for three ADRB2 collection-ready rows.",
    )
    add_row(
        "drd3_oprd1_atom_frame_recovery",
        preview_ready and recovered_targets == {"DRD3", "OPRD1"},
        ",".join(sorted(recovered_targets)),
        "DRD3,OPRD1",
        "drd3_oprd1_atom_frame_recovery_incomplete",
        "Recover DRD3 and OPRD1 atomized protein/ligand frames and rerun metrics.",
    )
    add_row(
        "local_min_ligand_rmsd_ready",
        preview_ready
        and len(local_min_values) >= required_metric_count
        and bool(local_min_values)
        and max(local_min_values) <= 2.0,
        f"reported={len(local_min_values)}; max={max(local_min_values) if local_min_values else ''}",
        "all rows reported and max<=2.0A",
        "local_min_ligand_rmsd_not_claim_grade",
        "Recover exact local-min RMSD metrics for every selected top-k row.",
    )
    add_row(
        "hbond_persistence_ready",
        preview_ready
        and len(hbond_values) >= required_metric_count
        and bool(hbond_values)
        and min(hbond_values) >= 0.5,
        f"reported={len(hbond_values)}; min={min(hbond_values) if hbond_values else ''}",
        "all rows reported and min>=0.5",
        "hbond_persistence_not_claim_grade",
        "Recover H-bond persistence metrics for every selected top-k row.",
    )
    add_row(
        "contact_persistence_ready",
        preview_ready
        and len(contact_values) >= required_metric_count
        and bool(contact_values)
        and min(contact_values) >= 0.5,
        f"reported={len(contact_values)}; min={min(contact_values) if contact_values else ''}",
        "all rows reported and min>=0.5",
        "contact_persistence_not_claim_grade",
        "Recover contact persistence metrics for every selected top-k row.",
    )
    add_row(
        "clash_relief_ready",
        preview_ready
        and len(initial_clash_values) >= required_metric_count
        and len(final_clash_values) >= required_metric_count
        and len(clash_relief_values) >= required_metric_count
        and bool(final_clash_values)
        and max(final_clash_values) <= 0,
        (
            f"initial={len(initial_clash_values)}; final={len(final_clash_values)}; "
            f"relief={len(clash_relief_values)}; final_max="
            f"{max(final_clash_values) if final_clash_values else ''}"
        ),
        "initial/final/relief reported for all rows and final_clash_count<=0",
        "clash_relief_not_claim_grade",
        "Recover initial/final clash counts and clash-relief metrics for every row.",
    )
    add_row(
        "green_yellow_red_abstain_banding_ready",
        preview_ready
        and _int(preview_summary.get("green_row_count")) >= required_metric_count
        and _int(preview_summary.get("yellow_row_count")) == 0
        and _int(preview_summary.get("red_row_count")) == 0
        and _int(preview_summary.get("abstain_row_count")) == 0,
        (
            f"green={_int(preview_summary.get('green_row_count'))}; "
            f"yellow={_int(preview_summary.get('yellow_row_count'))}; "
            f"red={_int(preview_summary.get('red_row_count'))}; "
            f"abstain={_int(preview_summary.get('abstain_row_count'))}"
        ),
        "all selected rows green; yellow/red/abstain=0",
        "claim_grade_banding_not_green",
        "Review banding and recover any missing or failed claim-grade metrics.",
    )
    add_row(
        "canonical_report_review_closed",
        canonical_ready,
        str(summary.get("status") or ""),
        "canonical pocketmd_lite_report_ready and claim_safe=true",
        "preview_metrics_require_canonical_review",
        "Review preview metrics and update canonical candidate CSV/report if approved.",
    )
    return rows


@router.get("/pocketmd-lite-report")
async def get_product_pocketmd_lite_report() -> dict[str, Any]:
    """Return the read-only PocketMD Lite top-k refinement report surface."""

    artifact = _read_json_object(POCKETMD_LITE_REPORT_ARTIFACT)
    summary = _summary(artifact)
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    preview_artifact = _read_json_object(
        POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT
    )
    preview_summary = _summary(preview_artifact)
    preview_rows = (
        preview_artifact.get("rows")
        if isinstance(preview_artifact.get("rows"), list)
        else []
    )
    canonical_review_surface = _canonical_report_review_surface(
        _read_json_object(POCKETMD_LITE_CANONICAL_REPORT_REVIEW_PACKET_ARTIFACT)
    )
    if not artifact or not summary:
        readiness_rows = _claim_grade_readiness_rows({}, preview_summary, preview_rows)
        blocked_readiness_rows = [row for row in readiness_rows if not row["ready"]]
        return {
            "status": "missing_pocketmd_lite_report",
            "artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
            "report_panel_ready": False,
            "preview_report_ready": False,
            "preview_report_status": "",
            "preview_pocketmd_lite_claim_safe": False,
            "preview_claim_grade_metric_ready_row_count": 0,
            "preview_green_row_count": 0,
            "canonical_review_required": False,
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
            "local_min_ligand_rmsd_a_max": 0.0,
            "hbond_persistence_min": 0.0,
            "contact_persistence_min": 0.0,
            "initial_clash_count_total": 0.0,
            "final_clash_count_total": 0.0,
            "clash_relief_count_total": 0.0,
            "missing_refinement_metric_names": [],
            "missing_refinement_metric_counts": {},
            "claim_grade_readiness_row_count": len(readiness_rows),
            "claim_grade_readiness_ready_row_count": len(readiness_rows)
            - len(blocked_readiness_rows),
            "claim_grade_readiness_blocked_row_count": len(blocked_readiness_rows),
            "claim_grade_readiness_rows": readiness_rows,
            "claim_grade_readiness_blocked_rows": blocked_readiness_rows,
            "next_required_step": "",
            "report_row_count": 0,
            "report_rows": [],
            "blocker_row_count": 1,
            "blocker_rows": [
                {
                    "blocker_id": "pocketmd_lite_report_missing",
                    "blocker_type": "missing_artifact",
                    "severity": "blocker",
                    "operator_action": "build_pocketmd_lite_report",
                    "claim_promotion_allowed": False,
                    "candidate_csv_update_allowed": False,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                }
            ],
            "claim_promotion_allowed": False,
            "candidate_csv_update_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "candidates": [],
            **canonical_review_surface,
            "claim_boundary": _REPORT_CLAIM_BOUNDARY_MISSING,
        }
    report_rows = _report_rows(rows)
    blocker_rows = _report_blocker_rows(summary, report_rows, preview_summary)
    readiness_rows = _claim_grade_readiness_rows(summary, preview_summary, preview_rows)
    blocked_readiness_rows = [row for row in readiness_rows if not row["ready"]]
    preview_ready = bool(
        preview_summary.get("status") == "pocketmd_lite_report_ready"
        and preview_summary.get("top_k_refinement_evidence_ready") is True
    )
    canonical_ready = bool(
        summary.get("status") == "pocketmd_lite_report_ready"
        and summary.get("top_k_refinement_evidence_ready") is True
        and summary.get("pocketmd_lite_claim_safe") is True
    )
    return {
        "status": summary.get("status"),
        "artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        "report_panel_ready": True,
        "preview_report_ready": preview_ready,
        "preview_report_status": str(preview_summary.get("status") or ""),
        "preview_pocketmd_lite_claim_safe": bool(
            preview_summary.get("pocketmd_lite_claim_safe") is True
        ),
        "preview_claim_grade_metric_ready_row_count": _int(
            preview_summary.get("claim_grade_metric_ready_row_count")
        ),
        "preview_green_row_count": _int(preview_summary.get("green_row_count")),
        "canonical_review_required": bool(preview_ready and not canonical_ready),
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
        "local_min_ligand_rmsd_a_max": _row_max(rows, "local_min_ligand_rmsd_a"),
        "hbond_persistence_min": _row_min(rows, "hbond_persistence"),
        "contact_persistence_min": _row_min(rows, "contact_persistence"),
        "initial_clash_count_total": _row_sum(rows, "initial_clash_count"),
        "final_clash_count_total": _row_sum(rows, "clash_count"),
        "clash_relief_count_total": _row_sum(rows, "clash_relief_count"),
        "missing_refinement_metric_names": _string_list(
            summary.get("missing_refinement_metric_names")
        ),
        "missing_refinement_metric_counts": (
            summary.get("missing_refinement_metric_counts")
            if isinstance(summary.get("missing_refinement_metric_counts"), dict)
            else {}
        ),
        "green_band_condition_text": str(summary.get("green_band_condition_text") or ""),
        "claim_grade_readiness_row_count": len(readiness_rows),
        "claim_grade_readiness_ready_row_count": len(readiness_rows)
        - len(blocked_readiness_rows),
        "claim_grade_readiness_blocked_row_count": len(blocked_readiness_rows),
        "claim_grade_readiness_rows": readiness_rows,
        "claim_grade_readiness_blocked_rows": blocked_readiness_rows,
        "next_required_step": str(summary.get("next_required_step") or ""),
        "report_row_count": len(report_rows),
        "report_rows": report_rows,
        "blocker_row_count": len(blocker_rows),
        "blocker_rows": blocker_rows,
        "claim_promotion_allowed": False,
        "candidate_csv_update_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "candidates": rows,
        **canonical_review_surface,
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


@router.get("/pocketmd-lite-claim-grade-metric-source-audit")
async def get_product_pocketmd_lite_claim_grade_metric_source_audit() -> dict[str, Any]:
    """Return the read-only PocketMD Lite claim-grade metric source audit surface."""

    artifact = _read_json_object(POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_ARTIFACT)
    summary = _summary(artifact)
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    canonical_artifact = _read_json_object(POCKETMD_LITE_REPORT_ARTIFACT)
    canonical_summary = _summary(canonical_artifact)
    preview_artifact = _read_json_object(
        POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT
    )
    preview_summary = _summary(preview_artifact)
    if not artifact or not summary:
        return {
            "status": "missing_pocketmd_lite_claim_grade_metric_source_audit",
            "artifact_path": str(POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_ARTIFACT),
            "audit_panel_ready": False,
            "claim_grade_metric_source_audit_ready": False,
            "metric_source_extraction_ready": False,
            "canonical_report_artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
            "canonical_report_status": "",
            "canonical_report_ready": False,
            "preview_report_artifact_path": str(
                POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT
            ),
            "preview_report_status": "",
            "preview_report_ready": False,
            "canonical_review_required": False,
            "candidate_count": 0,
            "searched_npz_candidate_count": 0,
            "exact_metric_source_ready_count": 0,
            "missing_exact_metric_source_count": 0,
            "claim_grade_collection_input_ready_count": 0,
            "selected_proxy_only_count": 0,
            "atomized_protein_source_candidate_count": 0,
            "ligand_atom_source_candidate_count": 0,
            "partial_atomized_protein_only_candidate_count": 0,
            "probe_status": "",
            "metric_source_row_count": 0,
            "metric_source_operator_action_row_count": 0,
            "metric_source_rows": [],
            "blocker_row_count": 1,
            "blocker_rows": [
                {
                    "blocker_id": "pocketmd_lite_claim_grade_metric_source_audit_missing",
                    "blocker_type": "missing_artifact",
                    "severity": "blocker",
                    "operator_action": "build_pocketmd_lite_claim_grade_metric_source_audit",
                    "claim_promotion_allowed": False,
                    "candidate_csv_update_allowed": False,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                }
            ],
            "next_required_step": "",
            "claim_promotion_allowed": False,
            "candidate_csv_update_allowed": False,
            "refinement_execution_enabled": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": _METRIC_SOURCE_AUDIT_CLAIM_BOUNDARY_MISSING,
        }

    audit_rows = _metric_source_audit_rows(rows)
    blocker_rows = _metric_source_audit_blocker_rows(
        summary,
        audit_rows,
        canonical_summary,
        preview_summary,
    )
    canonical_ready = bool(
        canonical_summary.get("status") == "pocketmd_lite_report_ready"
        and canonical_summary.get("top_k_refinement_evidence_ready") is True
        and canonical_summary.get("pocketmd_lite_claim_safe") is True
    )
    preview_ready = bool(
        preview_summary.get("status") == "pocketmd_lite_report_ready"
        and preview_summary.get("top_k_refinement_evidence_ready") is True
    )
    audit_ready = bool(
        summary.get("status") == "pocketmd_lite_claim_grade_metric_source_audit_ready"
        and _int(summary.get("missing_exact_metric_source_count")) == 0
    )
    operator_action_row_count = sum(
        1 for row in audit_rows if row["operator_action_required"]
    )
    return {
        "status": summary.get("status"),
        "artifact_path": str(POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_ARTIFACT),
        "schema_version": str(summary.get("schema_version") or ""),
        "audit_panel_ready": True,
        "claim_grade_metric_source_audit_ready": audit_ready,
        "metric_source_extraction_ready": bool(
            audit_ready
            and _int(summary.get("exact_metric_source_ready_count")) >= len(audit_rows)
            and len(audit_rows) > 0
        ),
        "canonical_report_artifact_path": str(POCKETMD_LITE_REPORT_ARTIFACT),
        "canonical_report_status": str(canonical_summary.get("status") or ""),
        "canonical_report_ready": canonical_ready,
        "preview_report_artifact_path": str(
            POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_ARTIFACT
        ),
        "preview_report_status": str(preview_summary.get("status") or ""),
        "preview_report_ready": preview_ready,
        "canonical_review_required": bool(preview_ready and not canonical_ready),
        "candidate_count": _int(summary.get("candidate_count")),
        "searched_npz_candidate_count": _int(summary.get("searched_npz_candidate_count")),
        "exact_metric_source_ready_count": _int(
            summary.get("exact_metric_source_ready_count")
        ),
        "missing_exact_metric_source_count": _int(
            summary.get("missing_exact_metric_source_count")
        ),
        "claim_grade_collection_input_ready_count": _int(
            summary.get("claim_grade_collection_input_ready_count")
        ),
        "selected_proxy_only_count": _int(summary.get("selected_proxy_only_count")),
        "atomized_protein_source_candidate_count": _int(
            summary.get("atomized_protein_source_candidate_count")
        ),
        "ligand_atom_source_candidate_count": _int(
            summary.get("ligand_atom_source_candidate_count")
        ),
        "partial_atomized_protein_only_candidate_count": _int(
            summary.get("partial_atomized_protein_only_candidate_count")
        ),
        "probe_status": str(summary.get("probe_status") or ""),
        "metric_source_row_count": len(audit_rows),
        "metric_source_operator_action_row_count": operator_action_row_count,
        "metric_source_rows": audit_rows,
        "blocker_row_count": len(blocker_rows),
        "blocker_rows": blocker_rows,
        "next_required_step": str(summary.get("next_required_step") or ""),
        "claim_promotion_allowed": False,
        "candidate_csv_update_allowed": False,
        "refinement_execution_enabled": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
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
