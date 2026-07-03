from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-operator-cockpit"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_OPERATOR_COCKPIT_ARTIFACT = ROOT / "runs" / "product_operator_cockpit_current.json"
PR38_SPLIT_ACCEPTANCE_PACKET_ARTIFACT = (
    ROOT / ".betelgeuze" / "pr38_split_acceptance_packet_current.json"
)
PR38_CHILD_PR_VERIFICATION_MATRIX_ARTIFACT = (
    ROOT / ".betelgeuze" / "pr38_child_pr_verification_matrix_current.json"
)

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


def _dict_rows(packet: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    value = packet.get(key)
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _claim_boundary_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    claim_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        allowed = bool(row.get("allowed") is True)
        claim_rows.append(
            {
                "claim_id": str(row.get("claim_id") or ""),
                "claim_status": "allowed" if allowed else "disallowed",
                "allowed": allowed,
                "claim_text": str(row.get("claim_text") or ""),
                "boundary": str(row.get("boundary") or row.get("claim_boundary") or ""),
                "reason": str(row.get("reason") or row.get("blocker") or ""),
                "source_artifact": str(row.get("source_artifact") or ""),
                "operator_action": str(
                    row.get("operator_action") or row.get("next_required_step") or ""
                ),
                "paid_pilot_wording_allowed": False,
                "general_platform_claim_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return claim_rows


def _pr38_verification_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sequence": _int(row.get("sequence")),
            "slice_id": str(row.get("slice_id") or ""),
            "changed_file_count": _int(row.get("changed_file_count")),
            "integration_touchpoint_count": _int(row.get("integration_touchpoint_count")),
            "hunk_split_review_required": bool(row.get("hunk_split_review_required") is True),
            "focused_test_required": bool(row.get("focused_test_required") is True),
            "focused_test_command": str(row.get("focused_test_command") or ""),
            "ai_verify_required": bool(row.get("ai_verify_required") is True),
            "ai_verify_command": str(row.get("ai_verify_command") or ""),
            "product_mode_required": bool(row.get("product_mode_required") is True),
            "product_mode_command": str(row.get("product_mode_command") or ""),
            "product_mode_expected_result": str(row.get("product_mode_expected_result") or ""),
            "claim_boundary_review_required": bool(
                row.get("claim_boundary_review_required") is True
            ),
            "child_pr_verification_matrix_ready": bool(
                row.get("child_pr_verification_matrix_ready") is True
            ),
            "verification_blockers": _string_list(row.get("verification_blockers")),
            "paid_pilot_wording_allowed": bool(row.get("paid_pilot_wording_allowed") is True),
            "branch_commit_work_allowed_by_this_matrix": bool(
                row.get("branch_commit_work_allowed_by_this_matrix") is True
            ),
            "execution_enabled": bool(row.get("execution_enabled") is True),
            "external_state_mutated": bool(row.get("external_state_mutated") is True),
        }
        for row in rows
    ]


def _customer_shadow_work_order_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        work_rows.append(
            {
                "work_order_id": str(row.get("work_order_id") or ""),
                "case_slot_id": str(row.get("case_slot_id") or ""),
                "status": str(row.get("status") or ""),
                "required_row_kind": str(row.get("required_row_kind") or ""),
                "operator_csv": str(row.get("operator_csv") or ""),
                "required_action": str(row.get("required_action") or ""),
                "required_raw_data_custody": str(row.get("required_raw_data_custody") or ""),
                "required_customer_retained_raw_data": bool(
                    row.get("required_customer_retained_raw_data") is True
                ),
                "required_redistribution_allowed": bool(
                    row.get("required_redistribution_allowed") is True
                ),
                "required_raw_data_stored_in_repo": bool(
                    row.get("required_raw_data_stored_in_repo") is True
                ),
                "required_derived_metadata_fields": _string_list(
                    row.get("required_derived_metadata_fields")
                ),
                "required_anonymized_result_summary": str(
                    row.get("required_anonymized_result_summary") or ""
                ),
                "required_reviewer_signoff_status": str(
                    row.get("required_reviewer_signoff_status") or ""
                ),
                "required_reviewer_id": str(row.get("required_reviewer_id") or ""),
                "required_reviewed_at_utc": str(row.get("required_reviewed_at_utc") or ""),
                "required_source_artifact_fingerprint": str(
                    row.get("required_source_artifact_fingerprint") or ""
                ),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return work_rows


def _customer_shadow_evidence_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    evidence_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_kind = str(row.get("row_kind") or "")
        raw_data_custody = str(row.get("raw_data_custody") or "")
        anonymized_summary_present = bool(
            row.get("anonymized_result_summary_present") is True
            or str(row.get("anonymized_result_summary") or "").strip()
        )
        reviewer_id_present = bool(
            row.get("reviewer_id_present") is True
            or str(row.get("reviewer_id") or "").strip()
        )
        reviewer_signoff_status = str(row.get("reviewer_signoff_status") or "")
        source_artifact_fingerprint = str(row.get("source_artifact_fingerprint") or "")
        artifact_fingerprint = str(row.get("artifact_fingerprint") or "")
        reviewed_customer_shadow_row_ready = bool(
            row_kind == "customer_shadow"
            and raw_data_custody == "customer_retained"
            and row.get("customer_retained_raw_data") is True
            and row.get("raw_data_stored_in_repo") is False
            and row.get("redistribution_allowed") is False
            and anonymized_summary_present
            and reviewer_id_present
            and reviewer_signoff_status == "approved"
            and bool(source_artifact_fingerprint)
            and bool(artifact_fingerprint)
        )
        case_id = str(row.get("case_id") or row.get("case_slot_id") or "")
        case_slot_id = str(row.get("case_slot_id") or row.get("case_id") or "")
        evidence_rows.append(
            {
                "case_id": case_id,
                "case_slot_id": case_slot_id,
                "row_kind": row_kind,
                "case_domain": str(row.get("case_domain") or ""),
                "raw_data_custody": raw_data_custody,
                "customer_retained_raw_data": bool(row.get("customer_retained_raw_data") is True),
                "raw_data_stored_in_repo": bool(row.get("raw_data_stored_in_repo") is True),
                "redistribution_allowed": bool(row.get("redistribution_allowed") is True),
                "anonymized_result_summary_present": anonymized_summary_present,
                "reviewer_id_present": reviewer_id_present,
                "reviewer_signoff_status": reviewer_signoff_status,
                "reviewed_at_utc": str(row.get("reviewed_at_utc") or ""),
                "source_artifact_fingerprint": source_artifact_fingerprint,
                "artifact_fingerprint": artifact_fingerprint,
                "derived_metadata_fields": _string_list(row.get("derived_metadata_fields")),
                "reviewed_customer_shadow_row_ready": reviewed_customer_shadow_row_ready,
                "claim_boundary": str(row.get("claim_boundary") or CLAIM_BOUNDARY),
                "raw_data_ingested": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return evidence_rows


def _customer_shadow_paid_pilot_requirement_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    requirement_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ready = bool(row.get("ready") is True)
        requirement_rows.append(
            {
                "requirement_id": str(row.get("requirement_id") or ""),
                "requirement_type": str(row.get("requirement_type") or ""),
                "ready": ready,
                "observed_count": _int(row.get("observed_count")),
                "required_count": _int(row.get("required_count")),
                "required_value": str(row.get("required_value") or ""),
                "observed_value": str(row.get("observed_value") or ""),
                "blocker": "" if ready else str(row.get("blocker") or ""),
                "operator_action": "" if ready else str(row.get("operator_action") or ""),
                "paid_pilot_wording_allowed": False,
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return requirement_rows


def _product_capability_rows(value: Any) -> list[dict[str, Any]]:
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
                "required": bool(row.get("required") is True),
                "release_blocker": bool(row.get("release_blocker") is True),
                "artifact_path": str(row.get("artifact_path") or ""),
                "observed": str(row.get("observed") or ""),
                "reason": str(row.get("reason") or ""),
                "bundle_assembled": bool(row.get("bundle_assembled") is True),
                "docking_results_emitted": False,
                "claim_boundary": str(row.get("claim_boundary") or CLAIM_BOUNDARY),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return capability_rows


def _goal_readiness_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    readiness_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        readiness_rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "lane_status": str(row.get("lane_status") or ""),
                "artifact_path": str(row.get("artifact_path") or ""),
                "artifact_present": bool(row.get("artifact_present") is True),
                "approval_token_required": str(row.get("approval_token_required") or ""),
                "blocker_count": _int(row.get("blocker_count")),
                "observed_status": str(row.get("observed_status") or ""),
                "next_required_step": str(row.get("next_required_step") or ""),
                "reclaim_size_gb": _float(row.get("reclaim_size_gb")),
                "claim_boundary": str(row.get("claim_boundary") or CLAIM_BOUNDARY),
                "action_executed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return readiness_rows


def _api_customer_flow_release_evidence_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    evidence_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        evidence_rows.append(
            {
                "check_id": str(row.get("check_id") or ""),
                "status": str(row.get("status") or ""),
                "release_blocker": bool(row.get("release_blocker") is True),
                "artifact_path": str(row.get("artifact_path") or ""),
                "required": str(row.get("required") or ""),
                "observed": str(row.get("observed") or ""),
                "reason": str(row.get("reason") or ""),
                "claim_boundary": str(row.get("claim_boundary") or CLAIM_BOUNDARY),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return evidence_rows


def _evidence_bundle_export_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    bundle_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        bundle_rows.append(
            {
                "artifact_id": str(row.get("artifact_id") or ""),
                "role": str(row.get("role") or ""),
                "artifact_path": str(row.get("artifact_path") or ""),
                "bundle_arcname": str(row.get("bundle_arcname") or ""),
                "required": bool(row.get("required") is True),
                "exists": bool(row.get("exists") is True),
                "missing": bool(row.get("missing") is True),
                "included_in_bundle": bool(row.get("included_in_bundle") is True),
                "release_blocker": bool(row.get("release_blocker") is True),
                "sha256": str(row.get("sha256") or ""),
                "size_bytes": _int(row.get("size_bytes")),
                "claim_boundary": str(row.get("claim_boundary") or CLAIM_BOUNDARY),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return bundle_rows


def _hbond_backmap_candidate_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    candidate_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate_rows.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "evidence_tier": str(row.get("evidence_tier") or ""),
                "claim_safe": bool(row.get("claim_safe") is True),
                "backmap_status": str(row.get("backmap_status") or ""),
                "mapping_source": str(row.get("mapping_source") or ""),
                "site_count": _int(row.get("site_count")),
                "mapped_site_count": _int(row.get("mapped_site_count")),
                "donor_count": _int(row.get("donor_count")),
                "acceptor_count": _int(row.get("acceptor_count")),
                "max_onsps_sites": _int(row.get("max_onsps_sites")),
                "polar_site_elements": _string_list(row.get("polar_site_elements")),
                "hbond_angle_score": _optional_float(row.get("hbond_angle_score")),
                "two_bead_vs_four_bead_delta": _optional_float(
                    row.get("two_bead_vs_four_bead_delta")
                ),
                "reason_code": str(row.get("reason_code") or ""),
                "reason_detail": str(row.get("reason_detail") or ""),
                "report_version": str(row.get("report_version") or ""),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return candidate_rows


def _public_benchmark_field_work_order_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        work_rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "field_name": str(row.get("field_name") or ""),
                "pending_row_count": _int(row.get("pending_row_count")),
                "required_value": str(row.get("required_value") or ""),
                "required_action": str(row.get("required_action") or ""),
                "approval_token_required": str(row.get("approval_token_required") or ""),
                "operator_csv": str(row.get("operator_csv") or ""),
                "source_artifact": str(row.get("source_artifact") or ""),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return work_rows


def _public_benchmark_score_evidence_row_work_order_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        missing_fields = _string_list(row.get("missing_fields"))
        work_rows.append(
            {
                "work_order_id": str(row.get("work_order_id") or ""),
                "status": str(row.get("status") or ""),
                "pose_id": str(row.get("pose_id") or ""),
                "complex_id": str(row.get("complex_id") or ""),
                "operator_csv": str(row.get("operator_csv") or ""),
                "source_artifact": str(row.get("source_artifact") or ""),
                "missing_field_count": _int(row.get("missing_field_count"))
                or len(missing_fields),
                "missing_fields": missing_fields,
                "primary_missing_field": str(row.get("primary_missing_field") or ""),
                "primary_required_action": str(row.get("primary_required_action") or ""),
                "required_action": str(row.get("required_action") or ""),
                "blocker_count": _int(row.get("blocker_count")),
                "blockers": _string_list(row.get("blockers")),
                "operator_action_required": bool(
                    row.get("operator_action_required") is not False
                ),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return work_rows


def _pocketmd_lite_claim_grade_metric_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    metric_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric_rows.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "band": str(row.get("band") or ""),
                "uncertainty_posture": str(row.get("uncertainty_posture") or ""),
                "uncertainty_score": _float(row.get("uncertainty_score")),
                "claim_grade_metric_ready": bool(row.get("claim_grade_metric_ready") is True),
                "claim_safe": bool(row.get("claim_safe") is True),
                "selected_for_refine": bool(row.get("selected_for_refine") is True),
                "local_min_ligand_rmsd_a": _float(row.get("local_min_ligand_rmsd_a")),
                "local_min_survived": bool(row.get("local_min_survived") is True),
                "hbond_persistence": _float(row.get("hbond_persistence")),
                "contact_persistence": _float(row.get("contact_persistence")),
                "initial_clash_count": _int(row.get("initial_clash_count")),
                "final_clash_count": _int(row.get("final_clash_count")),
                "clash_relief_count": _int(row.get("clash_relief_count")),
                "claim_grade_missing_metrics": _string_list(
                    row.get("claim_grade_missing_metrics")
                ),
                "blockers": _string_list(row.get("blockers")),
                "trajectory_probe_status": str(row.get("trajectory_probe_status") or ""),
                "candidate_metric_fill_status": str(
                    row.get("candidate_metric_fill_status") or ""
                ),
                "recommended_next_local_action": str(
                    row.get("recommended_next_local_action") or ""
                ),
                "candidate_csv_update_allowed": False,
                "refinement_execution_enabled": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return metric_rows


def _pocketmd_lite_metric_source_audit_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    metric_source_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        selected_missing = _string_list(row.get("selected_missing_exact_metric_fields"))
        selected_exact_ready = bool(row.get("selected_exact_metric_ready") is True)
        metric_source_rows.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "target": str(row.get("target") or ""),
                "ligand_id": str(row.get("ligand_id") or ""),
                "required_metrics": _string_list(row.get("required_metrics")),
                "selected_npz_status": str(row.get("selected_npz_status") or ""),
                "selected_npz_schema": str(row.get("selected_npz_schema") or ""),
                "selected_exact_metric_ready": selected_exact_ready,
                "selected_missing_exact_metric_fields": selected_missing,
                "searched_npz_candidate_count": _int(
                    row.get("searched_npz_candidate_count")
                ),
                "exact_metric_source_candidate_count": _int(
                    row.get("exact_metric_source_candidate_count")
                ),
                "atomized_protein_candidate_count": _int(
                    row.get("atomized_protein_candidate_count")
                ),
                "ligand_atom_candidate_count": _int(
                    row.get("ligand_atom_candidate_count")
                ),
                "claim_grade_collection_input_candidate_count": _int(
                    row.get("claim_grade_collection_input_candidate_count")
                ),
                "best_candidate_npz": str(row.get("best_candidate_npz") or ""),
                "best_candidate_status": str(row.get("best_candidate_status") or ""),
                "best_candidate_blockers": _string_list(row.get("best_candidate_blockers")),
                "recommended_next_local_action": str(
                    row.get("recommended_next_local_action") or ""
                ),
                "operator_action_required": bool(
                    selected_missing or not selected_exact_ready
                ),
                "candidate_csv_update_allowed": False,
                "refinement_execution_enabled": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return metric_source_rows


def _public_benchmark_external_receipt_step_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    step_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        step_rows.append(
            {
                "step_id": str(row.get("step_id") or ""),
                "status": str(row.get("status") or ""),
                "ready": bool(row.get("ready") is True),
                "evidence_artifact": str(row.get("evidence_artifact") or ""),
                "primary_metric": str(row.get("primary_metric") or ""),
                "secondary_metric": str(row.get("secondary_metric") or ""),
                "blocker": str(row.get("blocker") or ""),
                "next_required_step": str(row.get("next_required_step") or ""),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return step_rows


def _public_benchmark_external_beta_requirement_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    requirement_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ready = bool(row.get("ready") is True and str(row.get("status") or "") == "ready")
        requirement_rows.append(
            {
                "requirement_id": str(row.get("requirement_id") or ""),
                "status": str(row.get("status") or ""),
                "ready": ready,
                "required_value": str(row.get("required_value") or ""),
                "observed_value": str(row.get("observed_value") or ""),
                "blocker": str(row.get("blocker") or ""),
                "evidence_artifact": str(row.get("evidence_artifact") or ""),
                "operator_action": str(row.get("operator_action") or ""),
                "operator_action_required": not ready,
                "external_beta_wording_allowed": False,
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_boundary": str(row.get("claim_boundary") or ""),
            }
        )
    return requirement_rows


def _gpcr_promotion_work_order_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        work_rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "blocker": str(row.get("blocker") or ""),
                "required_action": str(row.get("required_action") or ""),
                "source_artifact": str(row.get("source_artifact") or ""),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return work_rows


def _gpcr_actual_closure_target_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    target_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_rows.append(
            {
                "target_id": str(row.get("target_id") or ""),
                "status": str(row.get("status") or ""),
                "actual_values_populated": bool(row.get("actual_values_populated") is True),
                "closure_ready": bool(row.get("closure_ready") is True),
                "gate_status": str(row.get("gate_status") or ""),
                "ranking_pr_auc": _optional_float(row.get("ranking_pr_auc")),
                "ranking_pr_auc_ci_low": _optional_float(row.get("ranking_pr_auc_ci_low")),
                "top20_hit_rate": _optional_float(row.get("top20_hit_rate")),
                "decoys_above_positive_count": _int(row.get("decoys_above_positive_count")),
                "positive_target_rank": _int(row.get("positive_target_rank")),
                "anchor_margin_a": _optional_float(row.get("anchor_margin_a")),
                "positive_not_out_anchored_by_top_decoy": bool(
                    row.get("positive_not_out_anchored_by_top_decoy") is True
                ),
                "positive_ligand_id": str(row.get("positive_ligand_id") or ""),
                "top_decoy_ligand_id": str(row.get("top_decoy_ligand_id") or ""),
                "over_anchored_decoy_count": _int(row.get("over_anchored_decoy_count")),
                "same_signature_decoy_count": _int(row.get("same_signature_decoy_count")),
                "multipolar_decoy_count": _int(row.get("multipolar_decoy_count")),
                "root_cause_tags": _string_list(row.get("root_cause_tags")),
                "blockers": _string_list(row.get("blockers")),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return target_rows


def _gpcr_actual_closure_requirement_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    requirement_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ready = str(row.get("status") or "") == "ready"
        requirement_rows.append(
            {
                "requirement_id": str(row.get("requirement_id") or ""),
                "status": str(row.get("status") or ""),
                "ready": ready,
                "observed": row.get("observed"),
                "threshold": row.get("threshold"),
                "blocker": str(row.get("blocker") or ""),
                "operator_action_required": not ready,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return requirement_rows


def _developer_preview_gate_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    gate_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        gate_rows.append(
            {
                "gate_id": str(row.get("gate_id") or ""),
                "priority": str(row.get("priority") or ""),
                "status": str(row.get("status") or ""),
                "ready": bool(row.get("ready") is True),
                "receipt_artifacts": str(row.get("receipt_artifacts") or ""),
                "required_receipt_count": _int(row.get("required_receipt_count")),
                "present_receipt_count": _int(row.get("present_receipt_count")),
                "present_blocked_receipt_count": _int(
                    row.get("present_blocked_receipt_count")
                ),
                "receipt_blocker_count": _int(row.get("receipt_blocker_count")),
                "primary_metric": str(row.get("primary_metric") or ""),
                "secondary_metric": str(row.get("secondary_metric") or ""),
                "blocker": str(row.get("blocker") or ""),
                "blockers": _string_list(row.get("blockers")),
                "receipt_blockers": _string_list(row.get("receipt_blockers")),
                "next_required_step": str(row.get("next_required_step") or ""),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return gate_rows


def _developer_preview_receipt_work_order_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        work_rows.append(
            {
                "gate_id": str(row.get("gate_id") or ""),
                "priority": str(row.get("priority") or ""),
                "receipt_artifact": str(row.get("receipt_artifact") or ""),
                "receipt_kind": str(row.get("receipt_kind") or ""),
                "blocker_scope": str(row.get("blocker_scope") or ""),
                "blocker": str(row.get("blocker") or ""),
                "blocker_detail": str(row.get("blocker_detail") or ""),
                "required_action": str(row.get("required_action") or ""),
                "next_required_step": str(row.get("next_required_step") or ""),
                "required_receipt_status": str(row.get("required_receipt_status") or ""),
                "required_true_field_count": _int(row.get("required_true_field_count")),
                "required_true_fields": _string_list(row.get("required_true_fields")),
                "required_zero_field_count": _int(row.get("required_zero_field_count")),
                "required_zero_fields": _string_list(row.get("required_zero_fields")),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return work_rows


def _developer_preview_stage5_recovery_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    recovery_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        recovery_rows.append(
            {
                "priority": str(row.get("priority") or ""),
                "gate_id": str(row.get("gate_id") or ""),
                "receipt_artifact": str(row.get("receipt_artifact") or ""),
                "receipt_kind": str(row.get("receipt_kind") or ""),
                "blocker_detail": str(row.get("blocker_detail") or ""),
                "source_label": str(row.get("source_label") or ""),
                "blocker_id": str(row.get("blocker_id") or ""),
                "source_argument": str(row.get("source_argument") or ""),
                "source_artifact_path": str(row.get("source_artifact_path") or ""),
                "source_artifact_present": bool(row.get("source_artifact_present") is True),
                "task_key": str(row.get("task_key") or ""),
                "required_stage5_arguments": _string_list(
                    row.get("required_stage5_arguments")
                ),
                "required_stage5_argument_count": _int(
                    row.get("required_stage5_argument_count")
                ),
                "required_action": str(row.get("required_action") or ""),
                "operator_action_required": bool(row.get("operator_action_required") is True),
                "claim_boundary": str(row.get("claim_boundary") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return recovery_rows


def _enterprise_on_prem_control_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    control_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        control_rows.append(
            {
                "control_id": str(row.get("control_id") or ""),
                "title": str(row.get("title") or ""),
                "status": str(row.get("status") or ""),
                "ready": bool(row.get("ready") is True),
                "blocker": str(row.get("blocker") or ""),
                "next_action": str(row.get("next_action") or ""),
                "evidence": str(row.get("evidence") or ""),
                "evidence_artifacts": _string_list(row.get("evidence_artifacts")),
                "claim_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return control_rows


def _f2g_f2h_recovery_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    recovery_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        recovery_rows.append(
            {
                "recovery_item_id": str(row.get("recovery_item_id") or ""),
                "preflight_check_id": str(row.get("preflight_check_id") or ""),
                "status": str(row.get("status") or ""),
                "required_surface": str(row.get("required_surface") or ""),
                "observed": str(row.get("observed") or ""),
                "blocker": str(row.get("blocker") or ""),
                "operator_action": str(row.get("operator_action") or ""),
                "acceptance_rule": str(row.get("acceptance_rule") or ""),
                "authoritative_source_hint": str(row.get("authoritative_source_hint") or ""),
                "prohibited_actions": str(row.get("prohibited_actions") or ""),
                "audit_executed": False,
                "continuation_executed": False,
                "surface_restore_executed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return recovery_rows


def _release_operator_action_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    action_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        action_rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "action_type": str(row.get("action_type") or ""),
                "status": str(row.get("status") or ""),
                "priority": _int(row.get("priority")),
                "approval_token": str(row.get("approval_token") or ""),
                "required_input": str(row.get("required_input") or ""),
                "artifact_path": str(row.get("artifact_path") or ""),
                "command": str(row.get("command") or ""),
                "reason": str(row.get("reason") or ""),
                "recommended_action": str(row.get("recommended_action") or ""),
                "operator_completion_artifact_id": str(
                    row.get("operator_completion_artifact_id") or ""
                ),
                "operator_completion_completion_rule": str(
                    row.get("operator_completion_completion_rule") or ""
                ),
                "operator_completion_next_action": str(
                    row.get("operator_completion_next_action") or ""
                ),
                "operator_completion_required_fields_or_columns": str(
                    row.get("operator_completion_required_fields_or_columns") or ""
                ),
                "parallelizable_with_primary_action": bool(
                    row.get("parallelizable_with_primary_action") is True
                ),
                "parallel_lane_precondition": str(
                    row.get("parallel_lane_precondition") or ""
                ),
                "action_executed": False,
                "delete_executed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": str(row.get("claim_boundary") or CLAIM_BOUNDARY),
            }
        )
    return action_rows


def _release_decision_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    decision_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision_rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "check": str(row.get("check") or ""),
                "status": str(row.get("status") or ""),
                "release_blocker": bool(row.get("release_blocker") is True),
                "artifact_path": str(row.get("artifact_path") or ""),
                "required": str(row.get("required") or ""),
                "observed": str(row.get("observed") or ""),
                "reason": str(row.get("reason") or ""),
                "action_executed": False,
                "delete_executed": False,
                "outbound_email_enabled": False,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return decision_rows


def _pr38_split_surface() -> dict[str, Any]:
    acceptance_packet = _read_json_object(PR38_SPLIT_ACCEPTANCE_PACKET_ARTIFACT)
    matrix_packet = _read_json_object(PR38_CHILD_PR_VERIFICATION_MATRIX_ARTIFACT)
    acceptance = _summary(acceptance_packet)
    matrix = _summary(matrix_packet)
    verification_rows = _pr38_verification_rows(_dict_rows(matrix_packet))
    matrix_ready = bool(matrix.get("verification_matrix_ready") is True)
    acceptance_ready = bool(acceptance.get("split_acceptance_ready") is True)
    return {
        "pr38_split_acceptance_artifact_path": str(PR38_SPLIT_ACCEPTANCE_PACKET_ARTIFACT),
        "pr38_split_acceptance_present": bool(acceptance),
        "pr38_split_acceptance_status": str(acceptance.get("status") or ""),
        "pr38_split_acceptance_ready": acceptance_ready,
        "pr38_child_pr_verification_matrix_artifact_path": str(
            PR38_CHILD_PR_VERIFICATION_MATRIX_ARTIFACT
        ),
        "pr38_child_pr_verification_matrix_present": bool(matrix),
        "pr38_child_pr_verification_matrix_status": str(matrix.get("status") or ""),
        "pr38_child_pr_verification_matrix_ready": matrix_ready,
        "pr38_split_ready_for_human_branch_approval": bool(
            acceptance_ready and matrix_ready and verification_rows
        ),
        "pr38_operator_branch_approval_required": bool(
            acceptance_ready and matrix_ready and verification_rows
        ),
        "pr38_child_pr_count": _int(
            matrix.get("child_pr_count") or acceptance.get("child_pr_count")
        ),
        "pr38_ready_child_pr_count": _int(
            matrix.get("ready_child_pr_count") or acceptance.get("ready_child_pr_count")
        ),
        "pr38_blocked_child_pr_count": _int(
            matrix.get("blocked_child_pr_count") or acceptance.get("blocked_child_pr_count")
        ),
        "pr38_blocked_slice_ids": _string_list(
            matrix.get("blocked_slice_ids") or acceptance.get("blocked_slice_ids")
        ),
        "pr38_focused_test_required_count": _int(matrix.get("focused_test_required_count")),
        "pr38_ai_verify_required_count": _int(matrix.get("ai_verify_required_count")),
        "pr38_product_mode_required_count": _int(matrix.get("product_mode_required_count")),
        "pr38_hunk_split_review_required_count": _int(
            matrix.get("hunk_split_review_required_count")
            or acceptance.get("hunk_split_review_required_count")
        ),
        "pr38_claim_boundary_review_required_count": _int(
            matrix.get("claim_boundary_review_required_count")
        ),
        "pr38_product_mode_expected_result": str(
            matrix.get("product_mode_expected_result")
            or acceptance.get("product_mode_expected_result")
            or ""
        ),
        "pr38_product_mode_expected_fail_closed_blockers": _string_list(
            matrix.get("product_mode_expected_fail_closed_blockers")
            or acceptance.get("product_mode_expected_fail_closed_blockers")
        ),
        "pr38_product_mode_claim_boundary_expected_locks": _string_list(
            matrix.get("product_mode_claim_boundary_expected_locks")
            or acceptance.get("product_mode_claim_boundary_expected_locks")
        ),
        "pr38_paid_pilot_wording_allowed": bool(
            matrix.get("paid_pilot_wording_allowed") is True
            or acceptance.get("paid_pilot_wording_allowed") is True
        ),
        "pr38_branch_commit_work_allowed": bool(
            matrix.get("branch_commit_work_allowed_by_this_matrix") is True
            or acceptance.get("branch_commit_work_allowed_by_this_packet") is True
        ),
        "pr38_patches_applied": bool(
            matrix.get("patches_applied") is True or acceptance.get("patches_applied") is True
        ),
        "pr38_branches_created": bool(
            matrix.get("branches_created") is True or acceptance.get("branches_created") is True
        ),
        "pr38_next_slice_id": str(verification_rows[0]["slice_id"] if verification_rows else ""),
        "pr38_next_focused_test_command": str(
            verification_rows[0]["focused_test_command"] if verification_rows else ""
        ),
        "pr38_next_ai_verify_command": str(
            verification_rows[0]["ai_verify_command"] if verification_rows else ""
        ),
        "pr38_next_required_step": str(
            matrix.get("next_required_step") or acceptance.get("next_required_step") or ""
        ),
        "pr38_verification_rows": verification_rows,
    }


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
        "allowed_claim_count": 0,
        "disallowed_claim_count": 0,
        "allowed_claim_ids": [],
        "disallowed_claim_ids": [],
        "allowed_claim_text": "",
        "disallowed_claim_text": "",
        "claim_boundary_row_count": 0,
        "allowed_claim_row_count": 0,
        "disallowed_claim_row_count": 0,
        "claim_boundary_rows": [],
        "allowed_claim_rows": [],
        "disallowed_claim_rows": [],
        "product_capability_row_count": 0,
        "product_capability_blocker_row_count": 0,
        "product_capability_rows": [],
        "goal_readiness_row_count": 0,
        "goal_readiness_action_required_row_count": 0,
        "goal_readiness_rows": [],
        "hbond_backmap_candidate_rows": [],
        "gpcr_hard_decoy_metric_ready": False,
        "gpcr_broad_claim_allowed": False,
        "gpcr_hard_decoy_actual_closure_ready": False,
        "gpcr_hard_decoy_actual_closure_metrics_ready": False,
        "gpcr_actual_closure_target_row_count": 0,
        "gpcr_actual_closure_ready_target_ids": [],
        "gpcr_actual_closure_requirement_ready_count": 0,
        "gpcr_actual_closure_requirement_blocked_count": 0,
        "gpcr_actual_closure_blocker_count": 0,
        "gpcr_actual_closure_blockers": [],
        "gpcr_actual_closure_min_anchor_margin_a": 0.0,
        "gpcr_actual_closure_max_decoys_above_positive": 0.0,
        "gpcr_actual_closure_target_rows": [],
        "gpcr_actual_closure_requirement_rows": [],
        "gpcr_phase3_closure_present": False,
        "gpcr_phase3_closure_evidence_ready": False,
        "gpcr_phase3_exit_metric_conditions_ready": False,
        "gpcr_phase3_broad_promotion_locked": False,
        "gpcr_phase3_effective_ranking_pr_auc_ci_low": 0.0,
        "gpcr_phase3_effective_top20_hit_rate": 0.0,
        "gpcr_phase3_effective_decoys_above_positive_total": 0,
        "gpcr_phase3_effective_metric_source": "",
        "gpcr_phase3_promotion_blocker_count": 0,
        "gpcr_promotion_work_order_row_count": 0,
        "gpcr_promotion_work_order_lane_count": 0,
        "gpcr_promotion_work_order_primary_blocker": "",
        "gpcr_promotion_work_order_rows": [],
        "pocketmd_lite_refinement_evidence_ready": False,
        "pocketmd_lite_report_evidence_ready": False,
        "pocketmd_lite_fill_preview_evidence_ready": False,
        "pocketmd_lite_preview_requires_canonical_review": False,
        "pocketmd_lite_canonical_review_present": False,
        "pocketmd_lite_canonical_review_required": False,
        "pocketmd_lite_canonical_review_status": "",
        "pocketmd_lite_canonical_report_ready": False,
        "pocketmd_lite_canonical_preview_report_ready": False,
        "pocketmd_lite_canonical_review_row_count": 0,
        "pocketmd_lite_canonical_ready_review_row_count": 0,
        "pocketmd_lite_canonical_approval_token_required": "",
        "pocketmd_lite_claim_grade_metric_ready_row_count": 0,
        "pocketmd_lite_local_min_ligand_rmsd_a_max": 0.0,
        "pocketmd_lite_hbond_persistence_min": 0.0,
        "pocketmd_lite_contact_persistence_min": 0.0,
        "pocketmd_lite_initial_clash_count_total": 0.0,
        "pocketmd_lite_final_clash_count_total": 0.0,
        "pocketmd_lite_clash_relief_count_total": 0.0,
        "pocketmd_lite_green_band_condition_text": "",
        "pocketmd_lite_claim_allowed": False,
        "pocketmd_lite_claim_grade_metric_rows": [],
        "pocketmd_lite_metric_source_audit_present": False,
        "pocketmd_lite_metric_source_audit_ready": False,
        "pocketmd_lite_metric_source_extraction_ready": False,
        "pocketmd_lite_metric_source_candidate_count": 0,
        "pocketmd_lite_metric_source_exact_ready_count": 0,
        "pocketmd_lite_metric_source_missing_count": 0,
        "pocketmd_lite_metric_source_collection_input_ready_count": 0,
        "pocketmd_lite_metric_source_selected_proxy_only_count": 0,
        "pocketmd_lite_metric_source_operator_action_row_count": 0,
        "pocketmd_lite_metric_source_canonical_review_required": False,
        "pocketmd_lite_metric_source_rows": [],
        "public_benchmark_claim_allowed": False,
        "public_benchmark_external_beta_candidate_ready": False,
        "public_benchmark_external_beta_wording_allowed": False,
        "public_benchmark_external_beta_operator_action_required": True,
        "public_benchmark_external_beta_requirement_row_count": 0,
        "public_benchmark_external_beta_requirement_ready_row_count": 0,
        "public_benchmark_external_beta_requirement_blocked_row_count": 0,
        "public_benchmark_external_beta_requirement_ids": [],
        "public_benchmark_external_beta_primary_requirement_id": "",
        "public_benchmark_external_beta_primary_blocker": "",
        "public_benchmark_external_beta_primary_operator_action": "",
        "public_benchmark_external_beta_requirement_rows": [],
        "public_benchmark_external_beta_blocked_requirement_rows": [],
        "public_benchmark_external_beta_claim_promotion_allowed": False,
        "public_benchmark_external_beta_execution_enabled": False,
        "public_benchmark_external_beta_external_state_mutated": False,
        "public_benchmark_receipt_attach_packet_ready": False,
        "public_benchmark_receipt_attach_packet_present": False,
        "public_benchmark_vina_gnina_pending_score_count": 0,
        "public_benchmark_vina_gnina_pending_field_count": 0,
        "public_benchmark_metric_source_pending_field_count": 0,
        "public_benchmark_metric_source_pending_approval_token_count": 0,
        "public_benchmark_field_work_order_row_count": 0,
        "public_benchmark_field_work_order_pending_field_count": 0,
        "public_benchmark_field_work_order_primary_field_name": "",
        "public_benchmark_field_work_order_primary_lane_id": "",
        "public_benchmark_field_work_order_primary_pending_row_count": 0,
        "public_benchmark_field_work_order_primary_required_value": "",
        "public_benchmark_field_work_order_primary_required_action": "",
        "public_benchmark_field_work_order_primary_approval_token_required": "",
        "public_benchmark_field_work_order_primary_operator_csv": "",
        "public_benchmark_field_work_order_primary_source_artifact": "",
        "public_benchmark_field_work_order_rows": [],
        "public_benchmark_score_evidence_row_work_order_ready": False,
        "public_benchmark_score_evidence_row_work_order_row_count": 0,
        "public_benchmark_score_evidence_row_work_order_pending_field_count": 0,
        "public_benchmark_score_evidence_row_work_order_primary_pose_id": "",
        "public_benchmark_score_evidence_row_work_order_primary_complex_id": "",
        "public_benchmark_score_evidence_row_work_order_primary_missing_field_count": 0,
        "public_benchmark_score_evidence_row_work_order_primary_missing_fields": [],
        "public_benchmark_score_evidence_row_work_order_primary_missing_field": "",
        "public_benchmark_score_evidence_row_work_order_primary_required_action": "",
        "public_benchmark_score_evidence_row_work_order_primary_operator_csv": "",
        "public_benchmark_score_evidence_row_work_order_primary_source_artifact": "",
        "public_benchmark_score_evidence_row_work_order_rows": [],
        "public_benchmark_external_receipt_step_rows": [],
        "public_benchmark_primary_blocker_id": "",
        "public_benchmark_primary_blocker": "",
        "public_benchmark_primary_next_required_step": "",
        "public_benchmark_vina_gnina_score_template_csv": "",
        "public_benchmark_vina_gnina_score_template_receipt_json": "",
        "public_benchmark_metric_source_receipt_csv": "",
        "public_benchmark_vina_gnina_adapter_command_after_fill": "",
        "evidence_bundle_export_ready": False,
        "evidence_bundle_export_row_count": 0,
        "evidence_bundle_export_blocker_row_count": 0,
        "evidence_bundle_export_required_missing_row_count": 0,
        "evidence_bundle_export_rows": [],
        "api_customer_flow_release_evidence_present": False,
        "api_customer_flow_release_evidence_ready": False,
        "api_customer_flow_release_evidence_status": "",
        "api_customer_flow_release_evidence_pass_count": 0,
        "api_customer_flow_release_evidence_blocker_count": 0,
        "api_customer_flow_tier_alpha_smoke_status": "",
        "api_customer_flow_tier_alpha_runner_execution_ok": False,
        "api_customer_flow_result_manifest_signature_verified": False,
        "api_customer_flow_restricted_runtime_ready": False,
        "api_customer_flow_bundle_validation_ready": False,
        "api_customer_flow_release_evidence_row_count": 0,
        "api_customer_flow_release_evidence_blocker_row_count": 0,
        "api_customer_flow_release_evidence_rows": [],
        "customer_shadow_paid_pilot_evidence_ready": False,
        "customer_shadow_real_row_count": 0,
        "customer_shadow_completed_case_count": 0,
        "customer_shadow_required_case_count": 0,
        "customer_shadow_missing_case_count": 0,
        "customer_shadow_customer_retained_raw_data_count": 0,
        "customer_shadow_redistribution_allowed_false_count": 0,
        "customer_shadow_anonymized_result_summary_count": 0,
        "customer_shadow_reviewer_signoff_count": 0,
        "customer_shadow_evidence_blocker_count": 0,
        "customer_shadow_work_order_ready": False,
        "customer_shadow_work_order_row_count": 0,
        "customer_shadow_work_order_primary_case_slot_id": "",
        "customer_shadow_work_order_primary_required_action": "",
        "customer_shadow_work_order_primary_operator_csv": "",
        "customer_shadow_work_order_primary_required_row_kind": "",
        "customer_shadow_work_order_primary_required_raw_data_custody": "",
        "customer_shadow_work_order_primary_required_customer_retained_raw_data": False,
        "customer_shadow_work_order_primary_required_redistribution_allowed": False,
        "customer_shadow_work_order_primary_required_raw_data_stored_in_repo": False,
        "customer_shadow_work_order_primary_required_derived_metadata_fields": [],
        "customer_shadow_work_order_primary_required_anonymized_result_summary": "",
        "customer_shadow_work_order_primary_required_reviewer_signoff_status": "",
        "customer_shadow_work_order_primary_required_reviewer_id": "",
        "customer_shadow_work_order_primary_required_reviewed_at_utc": "",
        "customer_shadow_work_order_primary_required_source_artifact_fingerprint": "",
        "customer_shadow_work_order_rows": [],
        "customer_shadow_evidence_row_count": 0,
        "customer_shadow_reviewed_evidence_row_count": 0,
        "customer_shadow_evidence_rows": [],
        "customer_shadow_paid_pilot_requirement_row_count": 0,
        "customer_shadow_paid_pilot_requirement_blocked_count": 0,
        "customer_shadow_paid_pilot_requirement_primary_row": {},
        "customer_shadow_paid_pilot_requirement_primary_id": "",
        "customer_shadow_paid_pilot_requirement_primary_blocker": "",
        "customer_shadow_paid_pilot_requirement_primary_action": "",
        "customer_shadow_paid_pilot_requirement_rows": [],
        "customer_shadow_intake_schema_ready": False,
        "customer_shadow_minimum_met": False,
        "customer_shadow_raw_data_stored_in_repo": False,
        "customer_shadow_invalid_row_count": 0,
        "customer_shadow_mock_fixture_row_count": 0,
        "customer_shadow_required_column_count": 0,
        "customer_shadow_redistribution_allowed_required_value": False,
        "developer_preview_clean_baseline_ready": False,
        "developer_preview_final_gate_evidence_present": False,
        "developer_preview_demo_allowed": False,
        "developer_preview_demo_blocked": True,
        "developer_preview_operator_action_required": True,
        "developer_preview_primary_blocker": "",
        "developer_preview_primary_next_required_step": "",
        "developer_preview_paid_pilot_wording_allowed": False,
        "developer_preview_claim_promotion_allowed": False,
        "developer_preview_execution_enabled": False,
        "developer_preview_external_state_mutated": False,
        "developer_preview_gate_count": 0,
        "developer_preview_ready_gate_count": 0,
        "developer_preview_blocked_gate_count": 0,
        "developer_preview_gate_row_count": 0,
        "developer_preview_gate_rows": [],
        "developer_preview_receipt_work_order_row_count": 0,
        "developer_preview_receipt_blocker_count": 0,
        "developer_preview_primary_blocker_id": "",
        "developer_preview_receipt_work_order_primary_gate_id": "",
        "developer_preview_receipt_work_order_primary_receipt_artifact": "",
        "developer_preview_receipt_work_order_primary_required_receipt_status": "",
        "developer_preview_receipt_work_order_primary_required_true_fields": [],
        "developer_preview_receipt_work_order_primary_required_zero_fields": [],
        "developer_preview_receipt_work_order_source_blocker_count": 0,
        "developer_preview_receipt_work_order_primary_source_blocker_gate_id": "",
        "developer_preview_receipt_work_order_primary_source_blocker_receipt_artifact": "",
        "developer_preview_receipt_work_order_primary_source_blocker": "",
        "developer_preview_receipt_work_order_primary_source_blocker_required_action": "",
        "developer_preview_receipt_work_order_rows": [],
        "developer_preview_stage5_recovery_row_count": 0,
        "developer_preview_stage5_missing_source_artifact_count": 0,
        "developer_preview_stage5_required_argument_count": 0,
        "developer_preview_stage5_primary_task_key": "",
        "developer_preview_stage5_primary_source_argument": "",
        "developer_preview_stage5_primary_source_artifact_path": "",
        "developer_preview_stage5_recovery_rows": [],
        "enterprise_on_prem_readiness_present": False,
        "enterprise_on_prem_ready": False,
        "enterprise_on_prem_claim_allowed": False,
        "enterprise_on_prem_control_count": 0,
        "enterprise_on_prem_ready_control_count": 0,
        "enterprise_on_prem_blocked_control_count": 0,
        "enterprise_on_prem_primary_blocker_id": "",
        "enterprise_on_prem_primary_blocker": "",
        "enterprise_on_prem_next_required_step": "",
        "enterprise_on_prem_oidc_rbac_ready": False,
        "enterprise_on_prem_object_storage_ready": False,
        "enterprise_on_prem_gpu_scheduler_ready": False,
        "enterprise_on_prem_audit_provenance_metrics_tracing_ready": False,
        "enterprise_on_prem_license_control_ready": False,
        "enterprise_on_prem_support_bundle_recovery_drill_ready": False,
        "enterprise_on_prem_rollback_retry_idempotency_ready": False,
        "enterprise_on_prem_control_rows": [],
        "f2g_f2h_preflight_present": False,
        "f2g_f2h_recovery_packet_present": False,
        "f2g_f2h_preflight_status": "",
        "f2g_f2h_recovery_status": "",
        "f2g_f2h_recovery_required": False,
        "f2g_f2h_preflight_blocker_count": 0,
        "f2g_f2h_blocked_recovery_item_count": 0,
        "f2g_f2h_recovery_item_count": 0,
        "f2g_f2h_primary_recovery_item_id": "",
        "f2g_f2h_primary_required_surface": "",
        "f2g_f2h_primary_blocker": "",
        "f2g_f2h_primary_operator_action": "",
        "f2g_f2h_audit_ready": False,
        "f2h_continuation_allowed": False,
        "f2g_f2h_placeholder_surface_creation_allowed": False,
        "f2g_f2h_surface_restore_executed": False,
        "f2g_f2h_recovery_rows": [],
        "pm_priority_queue_present": False,
        "pm_priority_queue_status": "",
        "pm_priority_queue_ready_item_count": 0,
        "pm_priority_queue_blocked_item_count": 0,
        "pm_priority_queue_first_blocked_item_id": "",
        "pm_priority_queue_first_blocker": "",
        "pm_priority_queue_next_required_step": "",
        "release_operator_action_row_count": 0,
        "release_operator_action_primary_lane_id": "",
        "release_operator_action_primary_action_type": "",
        "release_operator_action_primary_status": "",
        "release_operator_action_primary_approval_token": "",
        "release_operator_action_primary_required_input": "",
        "release_operator_action_primary_command": "",
        "release_operator_action_rows": [],
        "release_decision_present": False,
        "release_decision_status": "",
        "release_decision_release_allowed": False,
        "release_decision_restricted_release_allowed": False,
        "release_decision_blocker_count": 0,
        "release_decision_primary_blocker_check": "",
        "release_decision_primary_blocker_reason": "",
        "release_decision_primary_blocker_required": "",
        "release_decision_primary_blocker_artifact": "",
        "release_decision_rows": [],
        "pr38_split_acceptance_artifact_path": str(PR38_SPLIT_ACCEPTANCE_PACKET_ARTIFACT),
        "pr38_split_acceptance_present": False,
        "pr38_split_acceptance_status": "",
        "pr38_split_acceptance_ready": False,
        "pr38_child_pr_verification_matrix_artifact_path": str(
            PR38_CHILD_PR_VERIFICATION_MATRIX_ARTIFACT
        ),
        "pr38_child_pr_verification_matrix_present": False,
        "pr38_child_pr_verification_matrix_status": "",
        "pr38_child_pr_verification_matrix_ready": False,
        "pr38_split_ready_for_human_branch_approval": False,
        "pr38_operator_branch_approval_required": False,
        "pr38_child_pr_count": 0,
        "pr38_ready_child_pr_count": 0,
        "pr38_blocked_child_pr_count": 0,
        "pr38_blocked_slice_ids": [],
        "pr38_focused_test_required_count": 0,
        "pr38_ai_verify_required_count": 0,
        "pr38_product_mode_required_count": 0,
        "pr38_hunk_split_review_required_count": 0,
        "pr38_claim_boundary_review_required_count": 0,
        "pr38_product_mode_expected_result": "",
        "pr38_product_mode_expected_fail_closed_blockers": [],
        "pr38_product_mode_claim_boundary_expected_locks": [],
        "pr38_paid_pilot_wording_allowed": False,
        "pr38_branch_commit_work_allowed": False,
        "pr38_patches_applied": False,
        "pr38_branches_created": False,
        "pr38_next_slice_id": "",
        "pr38_next_focused_test_command": "",
        "pr38_next_ai_verify_command": "",
        "pr38_next_required_step": "",
        "pr38_verification_rows": [],
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
    claim_boundary_rows = _claim_boundary_rows(_list(packet, "claim_matrix"))
    allowed_claim_rows = [row for row in claim_boundary_rows if row["allowed"]]
    disallowed_claim_rows = [row for row in claim_boundary_rows if not row["allowed"]]
    developer_preview_gate_rows = _developer_preview_gate_rows(
        summary.get("developer_preview_gate_rows")
    )
    developer_preview_blocked_gate_rows = [
        row for row in developer_preview_gate_rows if not row["ready"]
    ]
    developer_preview_clean_baseline_ready = bool(
        summary.get("developer_preview_clean_baseline_ready") is True
    )
    developer_preview_gate_count = _int(summary.get("developer_preview_gate_count"))
    developer_preview_ready_gate_count = _int(
        summary.get("developer_preview_ready_gate_count")
    )
    developer_preview_blocked_gate_count = _int(
        summary.get("developer_preview_blocked_gate_count")
    )
    developer_preview_demo_allowed = bool(
        developer_preview_clean_baseline_ready
        and developer_preview_gate_count >= 6
        and developer_preview_blocked_gate_count == 0
        and developer_preview_ready_gate_count >= developer_preview_gate_count
    )
    developer_preview_primary_blocker = str(
        summary.get("developer_preview_receipt_work_order_primary_source_blocker") or ""
    )
    if not developer_preview_primary_blocker and developer_preview_blocked_gate_rows:
        first_blocked_gate = developer_preview_blocked_gate_rows[0]
        developer_preview_primary_blocker = str(
            first_blocked_gate.get("blocker")
            or (first_blocked_gate.get("blockers") or [""])[0]
            or ""
        )
    developer_preview_primary_next_required_step = str(
        summary.get("developer_preview_receipt_work_order_primary_source_blocker_required_action")
        or ""
    )
    if not developer_preview_primary_next_required_step and developer_preview_blocked_gate_rows:
        developer_preview_primary_next_required_step = str(
            developer_preview_blocked_gate_rows[0].get("next_required_step") or ""
        )
    public_external_beta_requirement_rows = (
        _public_benchmark_external_beta_requirement_rows(
            summary.get("public_benchmark_external_beta_requirement_rows")
        )
    )
    public_external_beta_blocked_requirement_rows = [
        row for row in public_external_beta_requirement_rows if row["operator_action_required"]
    ]
    public_external_beta_ready_requirement_rows = [
        row for row in public_external_beta_requirement_rows if row["ready"]
    ]

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
        "allowed_claim_ids": _string_list(summary.get("allowed_claim_ids")),
        "disallowed_claim_ids": _string_list(summary.get("disallowed_claim_ids")),
        "allowed_claim_text": str(summary.get("allowed_claim_text") or ""),
        "disallowed_claim_text": str(summary.get("disallowed_claim_text") or ""),
        "claim_boundary_row_count": len(claim_boundary_rows),
        "allowed_claim_row_count": len(allowed_claim_rows),
        "disallowed_claim_row_count": len(disallowed_claim_rows),
        "claim_boundary_rows": claim_boundary_rows,
        "allowed_claim_rows": allowed_claim_rows,
        "disallowed_claim_rows": disallowed_claim_rows,
        "paid_pilot_wording_allowed": bool(summary.get("paid_pilot_wording_allowed") is True),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "product_capability_row_count": _int(summary.get("product_capability_row_count")),
        "product_capability_blocker_row_count": _int(
            summary.get("product_capability_blocker_row_count")
        ),
        "product_capability_rows": _product_capability_rows(
            summary.get("product_capability_rows")
        ),
        "goal_readiness_row_count": _int(summary.get("goal_readiness_row_count")),
        "goal_readiness_action_required_row_count": _int(
            summary.get("goal_readiness_action_required_row_count")
        ),
        "goal_readiness_rows": _goal_readiness_rows(
            summary.get("goal_readiness_rows")
        ),
        "hbond_backmap_candidate_rows": _hbond_backmap_candidate_rows(
            summary.get("hbond_backmap_candidate_rows")
        ),
        "gpcr_hard_decoy_metric_ready": bool(summary.get("gpcr_hard_decoy_metric_ready") is True),
        "gpcr_broad_claim_allowed": bool(summary.get("gpcr_broad_claim_allowed") is True),
        "gpcr_hard_decoy_actual_closure_ready": bool(
            summary.get("gpcr_hard_decoy_actual_closure_ready") is True
        ),
        "gpcr_hard_decoy_actual_closure_metrics_ready": bool(
            summary.get("gpcr_hard_decoy_actual_closure_metrics_ready") is True
        ),
        "gpcr_actual_closure_target_row_count": _int(
            summary.get("gpcr_actual_closure_target_row_count")
        ),
        "gpcr_actual_closure_ready_target_ids": _string_list(
            summary.get("gpcr_actual_closure_ready_target_ids")
        ),
        "gpcr_actual_closure_requirement_ready_count": _int(
            summary.get("gpcr_actual_closure_requirement_ready_count")
        ),
        "gpcr_actual_closure_requirement_blocked_count": _int(
            summary.get("gpcr_actual_closure_requirement_blocked_count")
        ),
        "gpcr_actual_closure_blocker_count": _int(
            summary.get("gpcr_actual_closure_blocker_count")
        ),
        "gpcr_actual_closure_blockers": _string_list(
            summary.get("gpcr_actual_closure_blockers")
        ),
        "gpcr_actual_closure_min_anchor_margin_a": _float(
            summary.get("gpcr_actual_closure_min_anchor_margin_a")
        ),
        "gpcr_actual_closure_max_decoys_above_positive": _float(
            summary.get("gpcr_actual_closure_max_decoys_above_positive")
        ),
        "gpcr_actual_closure_target_rows": _gpcr_actual_closure_target_rows(
            summary.get("gpcr_actual_closure_target_rows")
        ),
        "gpcr_actual_closure_requirement_rows": _gpcr_actual_closure_requirement_rows(
            summary.get("gpcr_actual_closure_requirement_rows")
        ),
        "gpcr_phase3_closure_present": bool(summary.get("gpcr_phase3_closure_present") is True),
        "gpcr_phase3_closure_evidence_ready": bool(
            summary.get("gpcr_phase3_closure_evidence_ready") is True
        ),
        "gpcr_phase3_exit_metric_conditions_ready": bool(
            summary.get("gpcr_phase3_exit_metric_conditions_ready") is True
        ),
        "gpcr_phase3_broad_promotion_locked": bool(
            summary.get("gpcr_phase3_broad_promotion_locked") is True
        ),
        "gpcr_phase3_effective_ranking_pr_auc_ci_low": float(
            summary.get("gpcr_phase3_effective_ranking_pr_auc_ci_low") or 0.0
        ),
        "gpcr_phase3_effective_top20_hit_rate": float(
            summary.get("gpcr_phase3_effective_top20_hit_rate") or 0.0
        ),
        "gpcr_phase3_effective_decoys_above_positive_total": _int(
            summary.get("gpcr_phase3_effective_decoys_above_positive_total")
        ),
        "gpcr_phase3_effective_metric_source": str(
            summary.get("gpcr_phase3_effective_metric_source") or ""
        ),
        "gpcr_phase3_promotion_blocker_count": _int(
            summary.get("gpcr_phase3_promotion_blocker_count")
        ),
        "gpcr_promotion_work_order_row_count": _int(
            summary.get("gpcr_promotion_work_order_row_count")
        ),
        "gpcr_promotion_work_order_lane_count": _int(
            summary.get("gpcr_promotion_work_order_lane_count")
        ),
        "gpcr_promotion_work_order_primary_blocker": str(
            summary.get("gpcr_promotion_work_order_primary_blocker") or ""
        ),
        "gpcr_promotion_work_order_rows": _gpcr_promotion_work_order_rows(
            summary.get("gpcr_promotion_work_order_rows")
        ),
        "pocketmd_lite_refinement_evidence_ready": bool(
            summary.get("pocketmd_lite_refinement_evidence_ready") is True
        ),
        "pocketmd_lite_report_evidence_ready": bool(
            summary.get("pocketmd_lite_report_evidence_ready") is True
        ),
        "pocketmd_lite_fill_preview_evidence_ready": bool(
            summary.get("pocketmd_lite_fill_preview_evidence_ready") is True
        ),
        "pocketmd_lite_preview_requires_canonical_review": bool(
            summary.get("pocketmd_lite_preview_requires_canonical_review") is True
        ),
        "pocketmd_lite_canonical_review_present": bool(
            summary.get("pocketmd_lite_canonical_review_present") is True
        ),
        "pocketmd_lite_canonical_review_required": bool(
            summary.get("pocketmd_lite_canonical_review_required") is True
        ),
        "pocketmd_lite_canonical_review_status": str(
            summary.get("pocketmd_lite_canonical_review_status") or ""
        ),
        "pocketmd_lite_canonical_report_ready": bool(
            summary.get("pocketmd_lite_canonical_report_ready") is True
        ),
        "pocketmd_lite_canonical_preview_report_ready": bool(
            summary.get("pocketmd_lite_canonical_preview_report_ready") is True
        ),
        "pocketmd_lite_canonical_review_row_count": _int(
            summary.get("pocketmd_lite_canonical_review_row_count")
        ),
        "pocketmd_lite_canonical_ready_review_row_count": _int(
            summary.get("pocketmd_lite_canonical_ready_review_row_count")
        ),
        "pocketmd_lite_canonical_approval_token_required": str(
            summary.get("pocketmd_lite_canonical_approval_token_required") or ""
        ),
        "pocketmd_lite_claim_grade_metric_ready_row_count": _int(
            summary.get("pocketmd_lite_claim_grade_metric_ready_row_count")
        ),
        "pocketmd_lite_local_min_ligand_rmsd_a_max": _float(
            summary.get("pocketmd_lite_local_min_ligand_rmsd_a_max")
        ),
        "pocketmd_lite_hbond_persistence_min": _float(
            summary.get("pocketmd_lite_hbond_persistence_min")
        ),
        "pocketmd_lite_contact_persistence_min": _float(
            summary.get("pocketmd_lite_contact_persistence_min")
        ),
        "pocketmd_lite_initial_clash_count_total": _float(
            summary.get("pocketmd_lite_initial_clash_count_total")
        ),
        "pocketmd_lite_final_clash_count_total": _float(
            summary.get("pocketmd_lite_final_clash_count_total")
        ),
        "pocketmd_lite_clash_relief_count_total": _float(
            summary.get("pocketmd_lite_clash_relief_count_total")
        ),
        "pocketmd_lite_green_band_condition_text": str(
            summary.get("pocketmd_lite_green_band_condition_text") or ""
        ),
        "pocketmd_lite_claim_allowed": bool(summary.get("pocketmd_lite_claim_allowed") is True),
        "pocketmd_lite_claim_grade_metric_rows": _pocketmd_lite_claim_grade_metric_rows(
            summary.get("pocketmd_lite_claim_grade_metric_rows")
        ),
        "pocketmd_lite_metric_source_audit_present": bool(
            summary.get("pocketmd_lite_metric_source_audit_present") is True
        ),
        "pocketmd_lite_metric_source_audit_ready": bool(
            summary.get("pocketmd_lite_metric_source_audit_ready") is True
        ),
        "pocketmd_lite_metric_source_extraction_ready": bool(
            summary.get("pocketmd_lite_metric_source_extraction_ready") is True
        ),
        "pocketmd_lite_metric_source_candidate_count": _int(
            summary.get("pocketmd_lite_metric_source_candidate_count")
        ),
        "pocketmd_lite_metric_source_exact_ready_count": _int(
            summary.get("pocketmd_lite_metric_source_exact_ready_count")
        ),
        "pocketmd_lite_metric_source_missing_count": _int(
            summary.get("pocketmd_lite_metric_source_missing_count")
        ),
        "pocketmd_lite_metric_source_collection_input_ready_count": _int(
            summary.get("pocketmd_lite_metric_source_collection_input_ready_count")
        ),
        "pocketmd_lite_metric_source_selected_proxy_only_count": _int(
            summary.get("pocketmd_lite_metric_source_selected_proxy_only_count")
        ),
        "pocketmd_lite_metric_source_operator_action_row_count": _int(
            summary.get("pocketmd_lite_metric_source_operator_action_row_count")
        ),
        "pocketmd_lite_metric_source_canonical_review_required": bool(
            summary.get("pocketmd_lite_metric_source_canonical_review_required") is True
        ),
        "pocketmd_lite_metric_source_rows": _pocketmd_lite_metric_source_audit_rows(
            summary.get("pocketmd_lite_metric_source_rows")
        ),
        "public_benchmark_claim_allowed": bool(summary.get("public_benchmark_claim_allowed") is True),
        "public_benchmark_external_beta_candidate_ready": bool(
            summary.get("public_benchmark_external_beta_candidate_ready") is True
        ),
        "public_benchmark_external_beta_wording_allowed": bool(
            summary.get("public_benchmark_external_beta_wording_allowed") is True
        ),
        "public_benchmark_external_beta_operator_action_required": bool(
            summary.get("public_benchmark_external_beta_operator_action_required") is not False
        ),
        "public_benchmark_external_beta_requirement_row_count": _int(
            summary.get("public_benchmark_external_beta_requirement_row_count")
        )
        or len(public_external_beta_requirement_rows),
        "public_benchmark_external_beta_requirement_ready_row_count": _int(
            summary.get("public_benchmark_external_beta_requirement_ready_row_count")
        )
        or len(public_external_beta_ready_requirement_rows),
        "public_benchmark_external_beta_requirement_blocked_row_count": _int(
            summary.get("public_benchmark_external_beta_requirement_blocked_row_count")
        )
        or len(public_external_beta_blocked_requirement_rows),
        "public_benchmark_external_beta_requirement_ids": _string_list(
            summary.get("public_benchmark_external_beta_requirement_ids")
        ),
        "public_benchmark_external_beta_primary_requirement_id": str(
            summary.get("public_benchmark_external_beta_primary_requirement_id") or ""
        ),
        "public_benchmark_external_beta_primary_blocker": str(
            summary.get("public_benchmark_external_beta_primary_blocker") or ""
        ),
        "public_benchmark_external_beta_primary_operator_action": str(
            summary.get("public_benchmark_external_beta_primary_operator_action") or ""
        ),
        "public_benchmark_external_beta_requirement_rows": (
            public_external_beta_requirement_rows
        ),
        "public_benchmark_external_beta_blocked_requirement_rows": (
            public_external_beta_blocked_requirement_rows
        ),
        "public_benchmark_external_beta_claim_promotion_allowed": False,
        "public_benchmark_external_beta_execution_enabled": False,
        "public_benchmark_external_beta_external_state_mutated": False,
        "public_benchmark_receipt_attach_packet_ready": bool(
            summary.get("public_benchmark_receipt_attach_packet_ready") is True
        ),
        "public_benchmark_receipt_attach_packet_present": bool(
            summary.get("public_benchmark_receipt_attach_packet_present") is True
        ),
        "public_benchmark_vina_gnina_pending_score_count": _int(
            summary.get("public_benchmark_vina_gnina_pending_score_count")
        ),
        "public_benchmark_vina_gnina_pending_field_count": _int(
            summary.get("public_benchmark_vina_gnina_pending_field_count")
        ),
        "public_benchmark_metric_source_pending_field_count": _int(
            summary.get("public_benchmark_metric_source_pending_field_count")
        ),
        "public_benchmark_metric_source_pending_approval_token_count": _int(
            summary.get("public_benchmark_metric_source_pending_approval_token_count")
        ),
        "public_benchmark_field_work_order_row_count": _int(
            summary.get("public_benchmark_field_work_order_row_count")
        ),
        "public_benchmark_field_work_order_pending_field_count": _int(
            summary.get("public_benchmark_field_work_order_pending_field_count")
        ),
        "public_benchmark_field_work_order_primary_field_name": str(
            summary.get("public_benchmark_field_work_order_primary_field_name") or ""
        ),
        "public_benchmark_field_work_order_primary_lane_id": str(
            summary.get("public_benchmark_field_work_order_primary_lane_id") or ""
        ),
        "public_benchmark_field_work_order_primary_pending_row_count": _int(
            summary.get("public_benchmark_field_work_order_primary_pending_row_count")
        ),
        "public_benchmark_field_work_order_primary_required_value": str(
            summary.get("public_benchmark_field_work_order_primary_required_value") or ""
        ),
        "public_benchmark_field_work_order_primary_required_action": str(
            summary.get("public_benchmark_field_work_order_primary_required_action") or ""
        ),
        "public_benchmark_field_work_order_primary_approval_token_required": str(
            summary.get("public_benchmark_field_work_order_primary_approval_token_required") or ""
        ),
        "public_benchmark_field_work_order_primary_operator_csv": str(
            summary.get("public_benchmark_field_work_order_primary_operator_csv") or ""
        ),
        "public_benchmark_field_work_order_primary_source_artifact": str(
            summary.get("public_benchmark_field_work_order_primary_source_artifact") or ""
        ),
        "public_benchmark_field_work_order_rows": _public_benchmark_field_work_order_rows(
            summary.get("public_benchmark_field_work_order_rows")
        ),
        "public_benchmark_score_evidence_row_work_order_ready": bool(
            summary.get("public_benchmark_score_evidence_row_work_order_ready") is True
        ),
        "public_benchmark_score_evidence_row_work_order_row_count": _int(
            summary.get("public_benchmark_score_evidence_row_work_order_row_count")
        ),
        "public_benchmark_score_evidence_row_work_order_pending_field_count": _int(
            summary.get("public_benchmark_score_evidence_row_work_order_pending_field_count")
        ),
        "public_benchmark_score_evidence_row_work_order_primary_pose_id": str(
            summary.get("public_benchmark_score_evidence_row_work_order_primary_pose_id") or ""
        ),
        "public_benchmark_score_evidence_row_work_order_primary_complex_id": str(
            summary.get("public_benchmark_score_evidence_row_work_order_primary_complex_id")
            or ""
        ),
        "public_benchmark_score_evidence_row_work_order_primary_missing_field_count": _int(
            summary.get(
                "public_benchmark_score_evidence_row_work_order_primary_missing_field_count"
            )
        ),
        "public_benchmark_score_evidence_row_work_order_primary_missing_fields": _string_list(
            summary.get(
                "public_benchmark_score_evidence_row_work_order_primary_missing_fields"
            )
        ),
        "public_benchmark_score_evidence_row_work_order_primary_missing_field": str(
            summary.get("public_benchmark_score_evidence_row_work_order_primary_missing_field")
            or ""
        ),
        "public_benchmark_score_evidence_row_work_order_primary_required_action": str(
            summary.get(
                "public_benchmark_score_evidence_row_work_order_primary_required_action"
            )
            or ""
        ),
        "public_benchmark_score_evidence_row_work_order_primary_operator_csv": str(
            summary.get("public_benchmark_score_evidence_row_work_order_primary_operator_csv")
            or ""
        ),
        "public_benchmark_score_evidence_row_work_order_primary_source_artifact": str(
            summary.get(
                "public_benchmark_score_evidence_row_work_order_primary_source_artifact"
            )
            or ""
        ),
        "public_benchmark_score_evidence_row_work_order_rows": (
            _public_benchmark_score_evidence_row_work_order_rows(
                summary.get("public_benchmark_score_evidence_row_work_order_rows")
            )
        ),
        "public_benchmark_external_receipt_step_rows": (
            _public_benchmark_external_receipt_step_rows(
                summary.get("public_benchmark_external_receipt_step_rows")
            )
        ),
        "public_benchmark_primary_blocker_id": str(
            summary.get("public_benchmark_primary_blocker_id") or ""
        ),
        "public_benchmark_primary_blocker": str(
            summary.get("public_benchmark_primary_blocker") or ""
        ),
        "public_benchmark_primary_next_required_step": str(
            summary.get("public_benchmark_primary_next_required_step") or ""
        ),
        "public_benchmark_vina_gnina_score_template_csv": str(
            summary.get("public_benchmark_vina_gnina_score_template_csv") or ""
        ),
        "public_benchmark_vina_gnina_score_template_receipt_json": str(
            summary.get("public_benchmark_vina_gnina_score_template_receipt_json") or ""
        ),
        "public_benchmark_metric_source_receipt_csv": str(
            summary.get("public_benchmark_metric_source_receipt_csv") or ""
        ),
        "public_benchmark_vina_gnina_adapter_command_after_fill": str(
            summary.get("public_benchmark_vina_gnina_adapter_command_after_fill") or ""
        ),
        "evidence_bundle_export_ready": bool(summary.get("evidence_bundle_export_ready") is True),
        "evidence_bundle_export_row_count": _int(
            summary.get("evidence_bundle_export_row_count")
        ),
        "evidence_bundle_export_blocker_row_count": _int(
            summary.get("evidence_bundle_export_blocker_row_count")
        ),
        "evidence_bundle_export_required_missing_row_count": _int(
            summary.get("evidence_bundle_export_required_missing_row_count")
        ),
        "evidence_bundle_export_rows": _evidence_bundle_export_rows(
            summary.get("evidence_bundle_export_rows")
        ),
        "api_customer_flow_release_evidence_present": bool(
            summary.get("api_customer_flow_release_evidence_present") is True
        ),
        "api_customer_flow_release_evidence_ready": bool(
            summary.get("api_customer_flow_release_evidence_ready") is True
        ),
        "api_customer_flow_release_evidence_status": str(
            summary.get("api_customer_flow_release_evidence_status") or ""
        ),
        "api_customer_flow_release_evidence_pass_count": _int(
            summary.get("api_customer_flow_release_evidence_pass_count")
        ),
        "api_customer_flow_release_evidence_blocker_count": _int(
            summary.get("api_customer_flow_release_evidence_blocker_count")
        ),
        "api_customer_flow_tier_alpha_smoke_status": str(
            summary.get("api_customer_flow_tier_alpha_smoke_status") or ""
        ),
        "api_customer_flow_tier_alpha_runner_execution_ok": bool(
            summary.get("api_customer_flow_tier_alpha_runner_execution_ok") is True
        ),
        "api_customer_flow_result_manifest_signature_verified": bool(
            summary.get("api_customer_flow_result_manifest_signature_verified") is True
        ),
        "api_customer_flow_restricted_runtime_ready": bool(
            summary.get("api_customer_flow_restricted_runtime_ready") is True
        ),
        "api_customer_flow_bundle_validation_ready": bool(
            summary.get("api_customer_flow_bundle_validation_ready") is True
        ),
        "api_customer_flow_release_evidence_row_count": _int(
            summary.get("api_customer_flow_release_evidence_row_count")
        ),
        "api_customer_flow_release_evidence_blocker_row_count": _int(
            summary.get("api_customer_flow_release_evidence_blocker_row_count")
        ),
        "api_customer_flow_release_evidence_rows": (
            _api_customer_flow_release_evidence_rows(
                summary.get("api_customer_flow_release_evidence_rows")
            )
        ),
        "customer_shadow_paid_pilot_evidence_ready": bool(
            summary.get("customer_shadow_paid_pilot_evidence_ready") is True
        ),
        "customer_shadow_real_row_count": _int(summary.get("customer_shadow_real_row_count")),
        "customer_shadow_completed_case_count": _int(summary.get("customer_shadow_completed_case_count")),
        "customer_shadow_required_case_count": _int(summary.get("customer_shadow_required_case_count")),
        "customer_shadow_missing_case_count": _int(summary.get("customer_shadow_missing_case_count")),
        "customer_shadow_customer_retained_raw_data_count": _int(
            summary.get("customer_shadow_customer_retained_raw_data_count")
        ),
        "customer_shadow_redistribution_allowed_false_count": _int(
            summary.get("customer_shadow_redistribution_allowed_false_count")
        ),
        "customer_shadow_anonymized_result_summary_count": _int(
            summary.get("customer_shadow_anonymized_result_summary_count")
        ),
        "customer_shadow_reviewer_signoff_count": _int(
            summary.get("customer_shadow_reviewer_signoff_count")
        ),
        "customer_shadow_evidence_blocker_count": _int(
            summary.get("customer_shadow_evidence_blocker_count")
        ),
        "customer_shadow_work_order_ready": bool(
            summary.get("customer_shadow_work_order_ready") is True
        ),
        "customer_shadow_work_order_row_count": _int(
            summary.get("customer_shadow_work_order_row_count")
        ),
        "customer_shadow_work_order_primary_case_slot_id": str(
            summary.get("customer_shadow_work_order_primary_case_slot_id") or ""
        ),
        "customer_shadow_work_order_primary_required_action": str(
            summary.get("customer_shadow_work_order_primary_required_action") or ""
        ),
        "customer_shadow_work_order_primary_operator_csv": str(
            summary.get("customer_shadow_work_order_primary_operator_csv") or ""
        ),
        "customer_shadow_work_order_primary_required_row_kind": str(
            summary.get("customer_shadow_work_order_primary_required_row_kind") or ""
        ),
        "customer_shadow_work_order_primary_required_raw_data_custody": str(
            summary.get("customer_shadow_work_order_primary_required_raw_data_custody") or ""
        ),
        "customer_shadow_work_order_primary_required_customer_retained_raw_data": bool(
            summary.get("customer_shadow_work_order_primary_required_customer_retained_raw_data") is True
        ),
        "customer_shadow_work_order_primary_required_redistribution_allowed": bool(
            summary.get("customer_shadow_work_order_primary_required_redistribution_allowed") is True
        ),
        "customer_shadow_work_order_primary_required_raw_data_stored_in_repo": bool(
            summary.get("customer_shadow_work_order_primary_required_raw_data_stored_in_repo") is True
        ),
        "customer_shadow_work_order_primary_required_derived_metadata_fields": _string_list(
            summary.get("customer_shadow_work_order_primary_required_derived_metadata_fields")
        ),
        "customer_shadow_work_order_primary_required_anonymized_result_summary": str(
            summary.get("customer_shadow_work_order_primary_required_anonymized_result_summary") or ""
        ),
        "customer_shadow_work_order_primary_required_reviewer_signoff_status": str(
            summary.get("customer_shadow_work_order_primary_required_reviewer_signoff_status") or ""
        ),
        "customer_shadow_work_order_primary_required_reviewer_id": str(
            summary.get("customer_shadow_work_order_primary_required_reviewer_id") or ""
        ),
        "customer_shadow_work_order_primary_required_reviewed_at_utc": str(
            summary.get("customer_shadow_work_order_primary_required_reviewed_at_utc") or ""
        ),
        "customer_shadow_work_order_primary_required_source_artifact_fingerprint": str(
            summary.get("customer_shadow_work_order_primary_required_source_artifact_fingerprint") or ""
        ),
        "customer_shadow_work_order_rows": _customer_shadow_work_order_rows(
            summary.get("customer_shadow_work_order_rows")
        ),
        "customer_shadow_evidence_row_count": _int(
            summary.get("customer_shadow_evidence_row_count")
        ),
        "customer_shadow_reviewed_evidence_row_count": _int(
            summary.get("customer_shadow_reviewed_evidence_row_count")
        ),
        "customer_shadow_evidence_rows": _customer_shadow_evidence_rows(
            summary.get("customer_shadow_evidence_rows")
        ),
        "customer_shadow_paid_pilot_requirement_row_count": _int(
            summary.get("customer_shadow_paid_pilot_requirement_row_count")
        ),
        "customer_shadow_paid_pilot_requirement_blocked_count": _int(
            summary.get("customer_shadow_paid_pilot_requirement_blocked_count")
        ),
        "customer_shadow_paid_pilot_requirement_primary_row": (
            _customer_shadow_paid_pilot_requirement_rows(
                [summary.get("customer_shadow_paid_pilot_requirement_primary_row")]
            )[0]
            if isinstance(
                summary.get("customer_shadow_paid_pilot_requirement_primary_row"), dict
            )
            else {}
        ),
        "customer_shadow_paid_pilot_requirement_primary_id": str(
            summary.get("customer_shadow_paid_pilot_requirement_primary_id") or ""
        ),
        "customer_shadow_paid_pilot_requirement_primary_blocker": str(
            summary.get("customer_shadow_paid_pilot_requirement_primary_blocker") or ""
        ),
        "customer_shadow_paid_pilot_requirement_primary_action": str(
            summary.get("customer_shadow_paid_pilot_requirement_primary_action") or ""
        ),
        "customer_shadow_paid_pilot_requirement_rows": (
            _customer_shadow_paid_pilot_requirement_rows(
                summary.get("customer_shadow_paid_pilot_requirement_rows")
            )
        ),
        "customer_shadow_intake_schema_ready": bool(
            summary.get("customer_shadow_intake_schema_ready") is True
        ),
        "customer_shadow_minimum_met": bool(summary.get("customer_shadow_minimum_met") is True),
        "customer_shadow_raw_data_stored_in_repo": bool(
            summary.get("customer_shadow_raw_data_stored_in_repo") is True
        ),
        "customer_shadow_invalid_row_count": _int(summary.get("customer_shadow_invalid_row_count")),
        "customer_shadow_mock_fixture_row_count": _int(
            summary.get("customer_shadow_mock_fixture_row_count")
        ),
        "customer_shadow_required_column_count": _int(
            summary.get("customer_shadow_required_column_count")
        ),
        "customer_shadow_redistribution_allowed_required_value": bool(
            summary.get("customer_shadow_redistribution_allowed_required_value") is True
        ),
        "developer_preview_clean_baseline_ready": developer_preview_clean_baseline_ready,
        "developer_preview_final_gate_evidence_present": bool(
            developer_preview_gate_count > 0
            or len(developer_preview_gate_rows) > 0
            or str(summary.get("developer_preview_primary_blocker_id") or "")
        ),
        "developer_preview_demo_allowed": developer_preview_demo_allowed,
        "developer_preview_demo_blocked": not developer_preview_demo_allowed,
        "developer_preview_operator_action_required": not developer_preview_demo_allowed,
        "developer_preview_primary_blocker": developer_preview_primary_blocker,
        "developer_preview_primary_next_required_step": (
            developer_preview_primary_next_required_step
        ),
        "developer_preview_paid_pilot_wording_allowed": False,
        "developer_preview_claim_promotion_allowed": False,
        "developer_preview_execution_enabled": False,
        "developer_preview_external_state_mutated": False,
        "developer_preview_gate_count": developer_preview_gate_count,
        "developer_preview_ready_gate_count": developer_preview_ready_gate_count,
        "developer_preview_blocked_gate_count": developer_preview_blocked_gate_count,
        "developer_preview_gate_row_count": _int(
            summary.get("developer_preview_gate_row_count")
        ),
        "developer_preview_gate_rows": developer_preview_gate_rows,
        "developer_preview_receipt_work_order_row_count": _int(
            summary.get("developer_preview_receipt_work_order_row_count")
        ),
        "developer_preview_receipt_blocker_count": _int(
            summary.get("developer_preview_receipt_blocker_count")
        ),
        "developer_preview_primary_blocker_id": str(
            summary.get("developer_preview_primary_blocker_id") or ""
        ),
        "developer_preview_receipt_work_order_primary_gate_id": str(
            summary.get("developer_preview_receipt_work_order_primary_gate_id") or ""
        ),
        "developer_preview_receipt_work_order_primary_receipt_artifact": str(
            summary.get("developer_preview_receipt_work_order_primary_receipt_artifact") or ""
        ),
        "developer_preview_receipt_work_order_primary_required_receipt_status": str(
            summary.get("developer_preview_receipt_work_order_primary_required_receipt_status") or ""
        ),
        "developer_preview_receipt_work_order_primary_required_true_fields": _string_list(
            summary.get("developer_preview_receipt_work_order_primary_required_true_fields")
        ),
        "developer_preview_receipt_work_order_primary_required_zero_fields": _string_list(
            summary.get("developer_preview_receipt_work_order_primary_required_zero_fields")
        ),
        "developer_preview_receipt_work_order_source_blocker_count": _int(
            summary.get("developer_preview_receipt_work_order_source_blocker_count")
        ),
        "developer_preview_receipt_work_order_primary_source_blocker_gate_id": str(
            summary.get("developer_preview_receipt_work_order_primary_source_blocker_gate_id") or ""
        ),
        "developer_preview_receipt_work_order_primary_source_blocker_receipt_artifact": str(
            summary.get(
                "developer_preview_receipt_work_order_primary_source_blocker_receipt_artifact"
            )
            or ""
        ),
        "developer_preview_receipt_work_order_primary_source_blocker": str(
            summary.get("developer_preview_receipt_work_order_primary_source_blocker") or ""
        ),
        "developer_preview_receipt_work_order_primary_source_blocker_required_action": str(
            summary.get(
                "developer_preview_receipt_work_order_primary_source_blocker_required_action"
            )
            or ""
        ),
        "developer_preview_receipt_work_order_rows": _developer_preview_receipt_work_order_rows(
            summary.get("developer_preview_receipt_work_order_rows")
        ),
        "developer_preview_stage5_recovery_row_count": _int(
            summary.get("developer_preview_stage5_recovery_row_count")
        ),
        "developer_preview_stage5_missing_source_artifact_count": _int(
            summary.get("developer_preview_stage5_missing_source_artifact_count")
        ),
        "developer_preview_stage5_required_argument_count": _int(
            summary.get("developer_preview_stage5_required_argument_count")
        ),
        "developer_preview_stage5_primary_task_key": str(
            summary.get("developer_preview_stage5_primary_task_key") or ""
        ),
        "developer_preview_stage5_primary_source_argument": str(
            summary.get("developer_preview_stage5_primary_source_argument") or ""
        ),
        "developer_preview_stage5_primary_source_artifact_path": str(
            summary.get("developer_preview_stage5_primary_source_artifact_path") or ""
        ),
        "developer_preview_stage5_recovery_rows": _developer_preview_stage5_recovery_rows(
            summary.get("developer_preview_stage5_recovery_rows")
        ),
        "enterprise_on_prem_readiness_present": bool(
            summary.get("enterprise_on_prem_readiness_present") is True
        ),
        "enterprise_on_prem_ready": bool(summary.get("enterprise_on_prem_ready") is True),
        "enterprise_on_prem_claim_allowed": bool(
            summary.get("enterprise_on_prem_claim_allowed") is True
        ),
        "enterprise_on_prem_control_count": _int(summary.get("enterprise_on_prem_control_count")),
        "enterprise_on_prem_ready_control_count": _int(
            summary.get("enterprise_on_prem_ready_control_count")
        ),
        "enterprise_on_prem_blocked_control_count": _int(
            summary.get("enterprise_on_prem_blocked_control_count")
        ),
        "enterprise_on_prem_primary_blocker_id": str(
            summary.get("enterprise_on_prem_primary_blocker_id") or ""
        ),
        "enterprise_on_prem_primary_blocker": str(
            summary.get("enterprise_on_prem_primary_blocker") or ""
        ),
        "enterprise_on_prem_next_required_step": str(
            summary.get("enterprise_on_prem_next_required_step") or ""
        ),
        "enterprise_on_prem_oidc_rbac_ready": bool(
            summary.get("enterprise_on_prem_oidc_rbac_ready") is True
        ),
        "enterprise_on_prem_object_storage_ready": bool(
            summary.get("enterprise_on_prem_object_storage_ready") is True
        ),
        "enterprise_on_prem_gpu_scheduler_ready": bool(
            summary.get("enterprise_on_prem_gpu_scheduler_ready") is True
        ),
        "enterprise_on_prem_audit_provenance_metrics_tracing_ready": bool(
            summary.get("enterprise_on_prem_audit_provenance_metrics_tracing_ready") is True
        ),
        "enterprise_on_prem_license_control_ready": bool(
            summary.get("enterprise_on_prem_license_control_ready") is True
        ),
        "enterprise_on_prem_support_bundle_recovery_drill_ready": bool(
            summary.get("enterprise_on_prem_support_bundle_recovery_drill_ready") is True
        ),
        "enterprise_on_prem_rollback_retry_idempotency_ready": bool(
            summary.get("enterprise_on_prem_rollback_retry_idempotency_ready") is True
        ),
        "enterprise_on_prem_control_rows": _enterprise_on_prem_control_rows(
            summary.get("enterprise_on_prem_control_rows")
        ),
        "f2g_f2h_preflight_present": bool(summary.get("f2g_f2h_preflight_present") is True),
        "f2g_f2h_recovery_packet_present": bool(
            summary.get("f2g_f2h_recovery_packet_present") is True
        ),
        "f2g_f2h_preflight_status": str(summary.get("f2g_f2h_preflight_status") or ""),
        "f2g_f2h_recovery_status": str(summary.get("f2g_f2h_recovery_status") or ""),
        "f2g_f2h_recovery_required": bool(summary.get("f2g_f2h_recovery_required") is True),
        "f2g_f2h_preflight_blocker_count": _int(
            summary.get("f2g_f2h_preflight_blocker_count")
        ),
        "f2g_f2h_blocked_recovery_item_count": _int(
            summary.get("f2g_f2h_blocked_recovery_item_count")
        ),
        "f2g_f2h_recovery_item_count": _int(summary.get("f2g_f2h_recovery_item_count")),
        "f2g_f2h_primary_recovery_item_id": str(
            summary.get("f2g_f2h_primary_recovery_item_id") or ""
        ),
        "f2g_f2h_primary_required_surface": str(
            summary.get("f2g_f2h_primary_required_surface") or ""
        ),
        "f2g_f2h_primary_blocker": str(summary.get("f2g_f2h_primary_blocker") or ""),
        "f2g_f2h_primary_operator_action": str(
            summary.get("f2g_f2h_primary_operator_action") or ""
        ),
        "f2g_f2h_audit_ready": bool(summary.get("f2g_f2h_audit_ready") is True),
        "f2h_continuation_allowed": bool(summary.get("f2h_continuation_allowed") is True),
        "f2g_f2h_placeholder_surface_creation_allowed": bool(
            summary.get("f2g_f2h_placeholder_surface_creation_allowed") is True
        ),
        "f2g_f2h_surface_restore_executed": bool(
            summary.get("f2g_f2h_surface_restore_executed") is True
        ),
        "f2g_f2h_recovery_rows": _f2g_f2h_recovery_rows(
            summary.get("f2g_f2h_recovery_rows")
        ),
        "pm_priority_queue_present": bool(summary.get("pm_priority_queue_present") is True),
        "pm_priority_queue_status": str(summary.get("pm_priority_queue_status") or ""),
        "pm_priority_queue_ready_item_count": _int(summary.get("pm_priority_queue_ready_item_count")),
        "pm_priority_queue_blocked_item_count": _int(summary.get("pm_priority_queue_blocked_item_count")),
        "pm_priority_queue_first_blocked_item_id": str(
            summary.get("pm_priority_queue_first_blocked_item_id") or ""
        ),
        "pm_priority_queue_first_blocker": str(summary.get("pm_priority_queue_first_blocker") or ""),
        "pm_priority_queue_next_required_step": str(
            summary.get("pm_priority_queue_next_required_step") or ""
        ),
        "release_operator_action_row_count": _int(
            summary.get("release_operator_action_row_count")
        ),
        "release_operator_action_primary_lane_id": str(
            summary.get("release_operator_action_primary_lane_id") or ""
        ),
        "release_operator_action_primary_action_type": str(
            summary.get("release_operator_action_primary_action_type") or ""
        ),
        "release_operator_action_primary_status": str(
            summary.get("release_operator_action_primary_status") or ""
        ),
        "release_operator_action_primary_approval_token": str(
            summary.get("release_operator_action_primary_approval_token") or ""
        ),
        "release_operator_action_primary_required_input": str(
            summary.get("release_operator_action_primary_required_input") or ""
        ),
        "release_operator_action_primary_command": str(
            summary.get("release_operator_action_primary_command") or ""
        ),
        "release_operator_action_rows": _release_operator_action_rows(
            summary.get("release_operator_action_rows")
        ),
        "release_decision_present": bool(summary.get("release_decision_present") is True),
        "release_decision_status": str(summary.get("release_decision_status") or ""),
        "release_decision_release_allowed": bool(
            summary.get("release_decision_release_allowed") is True
        ),
        "release_decision_restricted_release_allowed": bool(
            summary.get("release_decision_restricted_release_allowed") is True
        ),
        "release_decision_blocker_count": _int(
            summary.get("release_decision_blocker_count")
        ),
        "release_decision_primary_blocker_check": str(
            summary.get("release_decision_primary_blocker_check") or ""
        ),
        "release_decision_primary_blocker_reason": str(
            summary.get("release_decision_primary_blocker_reason") or ""
        ),
        "release_decision_primary_blocker_required": str(
            summary.get("release_decision_primary_blocker_required") or ""
        ),
        "release_decision_primary_blocker_artifact": str(
            summary.get("release_decision_primary_blocker_artifact") or ""
        ),
        "release_decision_rows": _release_decision_rows(
            summary.get("release_decision_rows")
        ),
        **_pr38_split_surface(),
        "release_allowed": bool(summary.get("release_allowed") is True),
        "panels": _list(packet, "rows"),
        "claim_matrix": _list(packet, "claim_matrix"),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary") or CLAIM_BOUNDARY,
    }
