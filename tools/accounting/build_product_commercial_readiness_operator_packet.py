#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL_AUDIT_JSON = "runs/product_goal_completion_audit_current.json"
DEFAULT_DELTA_FORCE_CLOSURE_PACKET_JSON = "runs/residual_delta_force_closure_acceptance_packet_current.json"
DEFAULT_SCOPE_CLOSURE_PACKET_JSON = "runs/product_scope_closure_acceptance_packet_current.json"
DEFAULT_AQP1_DIRECT_BINDING_PROCUREMENT_JSON = "runs/aqp1_direct_binding_procurement_packet_current.json"
DEFAULT_AQP1_EXTERNAL_OPERATOR_FILL_GUIDE_JSON = (
    "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json"
)
DEFAULT_AQP1_EXTERNAL_OPERATOR_WORKSHEET_JSON = (
    "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json"
)
DEFAULT_AQP1_EXTERNAL_OPERATOR_STAGING_APPLY_JSON = (
    "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json"
)
DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_OPERATOR_RECEIPT_JSON = (
    "runs/production_ai_registry_promotion_operator_receipt_current.json"
)
DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_JSON = (
    "runs/production_ai_registry_promotion_priority_packet_current.json"
)
DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_FIELD_WORKSHEET_JSON = (
    "runs/production_ai_registry_promotion_operator_field_worksheet_current.json"
)
DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_FIELD_WORKSHEET_JSON = (
    "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json"
)
DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_FIELD_WORKSHEET_JSON = (
    "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json"
)
DEFAULT_OUT_JSON = "runs/product_commercial_readiness_operator_packet_current.json"
DEFAULT_OUT_CSV = "runs/product_commercial_readiness_operator_packet_current.csv"
DEFAULT_OUT_MD = "runs/product_commercial_readiness_operator_packet_current.md"

CLAIM_BOUNDARY = (
    "Product commercial-readiness operator packet only; it flattens the current goal-completion next-action matrix "
    "into human handoff rows. It does not run docking, run GPU jobs, fill scientific evidence, promote checkpoints, "
    "widen product claims, upload, submit, email, delete, or mutate external state."
)
TRANSPORTER_NEXT_SLOT_ACTION_ID = "transporter_next_slot_exact_evidence"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file_if_present(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _goal_audit_source_sha256(goal_audit_packet: dict[str, Any]) -> str:
    if not goal_audit_packet:
        return ""
    payload = json.loads(json.dumps(goal_audit_packet))
    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in list(summary):
            if str(key).startswith("commercial_readiness_handoff_bundle_"):
                summary.pop(key, None)
    return _sha256_json(payload)


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = _text(value)
    return [part.strip() for part in text.split(";") if part.strip()] if text else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _receipt_diagnostics(
    goal_summary: dict[str, Any],
    *,
    prefix: str,
    first_blocked_id_key: str,
) -> dict[str, Any]:
    artifact_path = _text(goal_summary.get(f"{prefix}_artifact"))
    receipt_summary = _summary(_read_json_if_present(artifact_path)) if artifact_path else {}

    def pick(source_key: str) -> Any:
        value = receipt_summary.get(source_key)
        if value in (None, ""):
            value = goal_summary.get(f"{prefix}_{source_key}")
        return value

    return {
        "status": _text(pick("status")),
        "first_blocked_id": _text(pick(first_blocked_id_key)),
        "first_blocked_evidence_artifact": _text(pick("first_blocked_evidence_artifact")),
        "first_blocked_expected_evidence_status": _text(
            pick("first_blocked_expected_evidence_status")
        ),
        "first_blocked_observed_evidence_status": _text(
            pick("first_blocked_observed_evidence_status")
        ),
        "first_blocked_missing_true_fields": _list(pick("first_blocked_missing_true_fields")),
        "first_blocked_row_blockers": _list(pick("first_blocked_row_blockers")),
        "most_common_row_blocker": _text(pick("most_common_row_blocker")),
    }


def _overlay_aqp1_procurement(row: dict[str, Any], procurement_packet: dict[str, Any], procurement_path: str) -> dict[str, Any]:
    summary = _summary(procurement_packet)
    if _text(row.get("action_id")) != "transporter_next_slot_exact_evidence" or not summary:
        return row
    out = dict(row)
    packet = dict(_dict(out.get("operator_completion_packet")))
    methods = _list(summary.get("accepted_direct_binding_methods"))
    fields = _list(summary.get("acceptance_fields"))
    overlay = {
        "direct_binding_procurement_packet_ready": bool(summary.get("procurement_packet_ready") is True),
        "direct_binding_procurement_packet_status": _text(summary.get("status")),
        "direct_binding_procurement_packet_artifact": procurement_path,
        "direct_binding_procurement_direct_binding_gap_open": bool(summary.get("direct_binding_gap_open") is True),
        "direct_binding_procurement_external_primary_evidence_required": bool(
            summary.get("external_primary_evidence_required") is True
        ),
        "direct_binding_procurement_first_required_external_action_id": _text(
            summary.get("first_required_external_action_id")
        ),
        "direct_binding_procurement_current_operator_candidate_blocker": _text(
            summary.get("current_operator_candidate_blocker")
        ),
        "direct_binding_procurement_minimum_acceptance_rule": _text(
            summary.get("minimum_acceptance_rule")
        ),
        "direct_binding_procurement_accepted_direct_binding_methods": methods,
        "direct_binding_procurement_acceptance_fields": fields,
    }
    out.update(overlay)
    packet.update(overlay)
    packet["direct_binding_procurement_packet"] = {
        "artifact": procurement_path,
        "status": overlay["direct_binding_procurement_packet_status"],
        "procurement_packet_ready": overlay["direct_binding_procurement_packet_ready"],
        "direct_binding_gap_open": overlay["direct_binding_procurement_direct_binding_gap_open"],
        "external_primary_evidence_required": overlay[
            "direct_binding_procurement_external_primary_evidence_required"
        ],
        "first_required_external_action_id": overlay[
            "direct_binding_procurement_first_required_external_action_id"
        ],
        "minimum_acceptance_rule": overlay["direct_binding_procurement_minimum_acceptance_rule"],
        "accepted_direct_binding_methods": methods,
        "acceptance_fields": fields,
    }
    out["operator_completion_packet"] = packet
    return out


def _csv_row(row: dict[str, Any]) -> dict[str, Any]:
    packet = _dict(row.get("operator_completion_packet"))
    packet_keys = sorted(str(key) for key in packet.keys())
    worker_contract = _dict(packet.get("worker_runtime_receipt_contract"))
    dependency_matrix = [
        item
        for item in (
            row.get("blocked_stage_dependency_matrix")
            or packet.get("blocked_stage_dependency_matrix")
            or []
        )
        if isinstance(item, dict)
    ]
    return {
        "action_id": _text(row.get("action_id")),
        "status": _text(row.get("status")),
        "gap_id": _text(row.get("gap_id")),
        "release_blocker": bool(row.get("release_blocker") is True),
        "artifact": _text(row.get("artifact")),
        "required_operator_inputs": ";".join(_list(row.get("required_operator_inputs"))),
        "required_exact_evidence_fields": ";".join(_list(row.get("required_exact_evidence_fields"))),
        "required_claim_guardrails": ";".join(_list(row.get("required_claim_guardrails"))),
        "expected_evidence_type": _text(row.get("expected_evidence_type") or packet.get("expected_evidence_type")),
        "required_missing_fields": ";".join(_list(row.get("required_missing_fields") or packet.get("required_missing_fields"))),
        "required_evidence": _text(row.get("required_evidence") or packet.get("completion_rule")),
        "operator_review_artifact": _text(row.get("operator_review_artifact") or packet.get("operator_review_artifact")),
        "post_intake_synchronization_targets": ";".join(
            _list(row.get("post_intake_synchronization_targets") or packet.get("post_intake_synchronization_targets"))
        ),
        "acceptance_gate_commands": ";".join(
            _list(row.get("acceptance_gate_commands") or packet.get("acceptance_gate_commands") or packet.get("validation_commands"))
        ),
        "source_signal": _text(row.get("source_signal") or packet.get("source_signal")),
        "claim_safe_completion_rule": _text(row.get("claim_safe_completion_rule")),
        "next_slot_source_modality_guard_ready": bool(
            row.get("next_slot_source_modality_guard_ready") is True
            or packet.get("next_slot_source_modality_guard_ready") is True
        ),
        "next_slot_source_modality": _text(
            row.get("next_slot_source_modality") or packet.get("next_slot_source_modality")
        ),
        "next_slot_source_modality_claim_safe": bool(
            row.get("next_slot_source_modality_claim_safe") is True
            or packet.get("next_slot_source_modality_claim_safe") is True
        ),
        "next_slot_source_modality_direct_binding_claim_allowed": bool(
            row.get("next_slot_source_modality_direct_binding_claim_allowed") is True
            or packet.get("next_slot_source_modality_direct_binding_claim_allowed") is True
        ),
        "next_slot_source_modality_decision": _text(
            row.get("next_slot_source_modality_decision")
            or packet.get("next_slot_source_modality_decision")
        ),
        "next_slot_source_modality_guardrails": ";".join(
            _list(
                row.get("next_slot_source_modality_guardrails")
                or packet.get("next_slot_source_modality_guardrails")
            )
        ),
        "next_slot_source_modality_observed_signal": _text(
            row.get("next_slot_source_modality_observed_signal")
            or packet.get("next_slot_source_modality_observed_signal")
        ),
        "next_slot_source_modality_required_upgrade": _text(
            row.get("next_slot_source_modality_required_upgrade")
            or packet.get("next_slot_source_modality_required_upgrade")
        ),
        "next_slot_source_modality_triage_artifact": _text(
            row.get("next_slot_source_modality_triage_artifact")
            or packet.get("next_slot_source_modality_triage_artifact")
        ),
        "next_slot_source_modality_triage_decision": _text(
            row.get("next_slot_source_modality_triage_decision")
            or packet.get("next_slot_source_modality_triage_decision")
        ),
        "next_slot_source_modality_direct_experimental_binding_row_count": _int(
            row.get("next_slot_source_modality_direct_experimental_binding_row_count")
            or packet.get("next_slot_source_modality_direct_experimental_binding_row_count")
        ),
        "next_slot_source_modality_claim_safe_binding_kcal_ready_count": _int(
            row.get("next_slot_source_modality_claim_safe_binding_kcal_ready_count")
            or packet.get("next_slot_source_modality_claim_safe_binding_kcal_ready_count")
        ),
        "next_slot_source_modality_computational_binding_energy_row_count": _int(
            row.get("next_slot_source_modality_computational_binding_energy_row_count")
            or packet.get("next_slot_source_modality_computational_binding_energy_row_count")
        ),
        "next_slot_source_modality_best_computational_binding_energy_kcal_mol": _text(
            row.get("next_slot_source_modality_best_computational_binding_energy_kcal_mol")
            or packet.get("next_slot_source_modality_best_computational_binding_energy_kcal_mol")
        ),
        "operator_validation_candidate_ready": bool(
            row.get("operator_validation_candidate_ready") is True
            or packet.get("operator_validation_candidate_ready") is True
        ),
        "operator_validation_candidate_status": _text(
            row.get("operator_validation_candidate_status")
            or packet.get("operator_validation_candidate_status")
        ),
        "operator_validation_candidate_ligand_external_identifier": _text(
            row.get("operator_validation_candidate_ligand_external_identifier")
            or packet.get("operator_validation_candidate_ligand_external_identifier")
        ),
        "operator_validation_candidate_reference_binding_kcal_mol": _text(
            row.get("operator_validation_candidate_reference_binding_kcal_mol")
            or packet.get("operator_validation_candidate_reference_binding_kcal_mol")
        ),
        "operator_validation_candidate_blocker": _text(
            row.get("operator_validation_candidate_blocker")
            or packet.get("operator_validation_candidate_blocker")
        ),
        "operator_validation_candidate_claim_safe_ready": bool(
            row.get("operator_validation_candidate_claim_safe_ready") is True
            or packet.get("operator_validation_candidate_claim_safe_ready") is True
        ),
        "direct_binding_procurement_packet_ready": bool(
            row.get("direct_binding_procurement_packet_ready") is True
            or packet.get("direct_binding_procurement_packet_ready") is True
        ),
        "direct_binding_procurement_packet_status": _text(
            row.get("direct_binding_procurement_packet_status")
            or packet.get("direct_binding_procurement_packet_status")
        ),
        "direct_binding_procurement_packet_artifact": _text(
            row.get("direct_binding_procurement_packet_artifact")
            or packet.get("direct_binding_procurement_packet_artifact")
        ),
        "direct_binding_procurement_direct_binding_gap_open": bool(
            row.get("direct_binding_procurement_direct_binding_gap_open") is True
            or packet.get("direct_binding_procurement_direct_binding_gap_open") is True
        ),
        "direct_binding_procurement_external_primary_evidence_required": bool(
            row.get("direct_binding_procurement_external_primary_evidence_required") is True
            or packet.get("direct_binding_procurement_external_primary_evidence_required") is True
        ),
        "direct_binding_procurement_first_required_external_action_id": _text(
            row.get("direct_binding_procurement_first_required_external_action_id")
            or packet.get("direct_binding_procurement_first_required_external_action_id")
        ),
        "direct_binding_procurement_current_operator_candidate_blocker": _text(
            row.get("direct_binding_procurement_current_operator_candidate_blocker")
            or packet.get("direct_binding_procurement_current_operator_candidate_blocker")
        ),
        "direct_binding_procurement_minimum_acceptance_rule": _text(
            row.get("direct_binding_procurement_minimum_acceptance_rule")
            or packet.get("direct_binding_procurement_minimum_acceptance_rule")
        ),
        "direct_binding_procurement_accepted_direct_binding_methods": ";".join(
            _list(
                row.get("direct_binding_procurement_accepted_direct_binding_methods")
                or packet.get("direct_binding_procurement_accepted_direct_binding_methods")
            )
        ),
        "direct_binding_procurement_acceptance_fields": ";".join(
            _list(
                row.get("direct_binding_procurement_acceptance_fields")
                or packet.get("direct_binding_procurement_acceptance_fields")
            )
        ),
        "operator_completion_packet_ready": bool(row.get("operator_completion_packet_ready") is True),
        "operator_completion_packet_keys": ";".join(packet_keys),
        "operator_completion_worker_runtime_receipt_contract_ready": bool(worker_contract),
        "operator_completion_worker_runtime_receipt_required_fields_or_columns": ";".join(
            _list(packet.get("worker_runtime_receipt_required_fields_or_columns"))
        ),
        "operator_completion_worker_runtime_receipt_required_field_count": _int(
            packet.get("worker_runtime_receipt_required_field_count")
        ),
        "operator_completion_worker_runtime_receipt_completion_rule": _text(
            packet.get("worker_runtime_receipt_completion_rule")
        ),
        "operator_completion_worker_runtime_receipt_post_environment_next_stage_id": _text(
            packet.get("post_environment_next_stage_id")
        ),
        "operator_completion_worker_runtime_receipt_post_environment_next_artifact": _text(
            packet.get("post_environment_next_artifact")
        ),
        "operator_completion_worker_runtime_receipt_post_environment_validation_command": _text(
            packet.get("post_environment_validation_command")
        ),
        "operator_completion_worker_runtime_receipt_full_regeneration_command": _text(
            packet.get("full_regeneration_command")
        ),
        "operator_completion_worker_runtime_receipt_guardrails": ";".join(
            _list(packet.get("worker_runtime_receipt_guardrails"))
        ),
        "operator_completion_diagnostic_commands": ";".join(
            _list(packet.get("diagnostic_commands"))
        ),
        "operator_completion_diagnostic_command_count": _int(
            packet.get("diagnostic_command_count")
        ),
        "operator_completion_diagnostic_required_fields": ";".join(
            _list(packet.get("diagnostic_required_fields"))
        ),
        "operator_completion_diagnostic_required_field_count": _int(
            packet.get("diagnostic_required_field_count")
        ),
        "operator_completion_diagnostic_completion_rule": _text(
            packet.get("diagnostic_completion_rule")
        ),
        "operator_completion_diagnostic_return_artifacts": ";".join(
            _list(packet.get("diagnostic_return_artifacts"))
        ),
        "operator_completion_torch_visibility_probe_command": _text(
            packet.get("torch_visibility_probe_command")
        ),
        "next_action": _text(row.get("next_action")),
        "execution_command": _text(row.get("execution_command")),
        "validation_command": _text(row.get("validation_command")),
        "unlock_claim": _text(row.get("unlock_claim")),
        "next_slot_id": _text(row.get("next_slot_id")),
        "next_review_row_id": _text(row.get("next_review_row_id")),
        "candidate_ligand_id": _text(row.get("candidate_ligand_id")),
        "candidate_name": _text(row.get("candidate_name")),
        "target_ready_for_promotion_ids": ";".join(_list(row.get("target_ready_for_promotion_ids"))),
        "target_blocked_for_promotion_ids": ";".join(_list(row.get("target_blocked_for_promotion_ids"))),
        "primary_blocker_target_id": _text(row.get("primary_blocker_target_id")),
        "primary_blocker_packet_step": _text(row.get("primary_blocker_packet_step")),
        "primary_blocker_candidate_name": _text(row.get("primary_blocker_candidate_name")),
        "target_scope_guardrail": _text(row.get("target_scope_guardrail")),
        "blocked_stage_dependency_count": _int(row.get("blocked_stage_dependency_count")),
        "blocked_stage_evidence_count": _int(
            row.get("blocked_stage_evidence_count") or packet.get("blocked_stage_evidence_count")
        ),
        "blocked_stage_dependency_matrix_count": len(dependency_matrix),
        "blocked_stage_dependency_stage_ids": ";".join(
            _text(item.get("stage_id")) for item in dependency_matrix if _text(item.get("stage_id"))
        ),
        "blocked_stage_dependency_unlock_claim_scopes": ";".join(
            sorted(
                {
                    str(scope)
                    for item in dependency_matrix
                    for scope in _list(item.get("unlock_claim_scopes"))
                }
            )
        ),
        "blocked_stage_dependency_first_blocked_evidence_row_ids": ";".join(
            _text(item.get("first_blocked_evidence_row_id"))
            for item in dependency_matrix
            if _text(item.get("first_blocked_evidence_row_id"))
        ),
        "workstream_lane_id": _text(row.get("workstream_lane_id")),
        "parallelizable_with_primary_blocker": bool(
            row.get("parallelizable_with_primary_blocker") is True
        ),
        "parallel_lane_precondition": _text(row.get("parallel_lane_precondition")),
        "parallel_lane_priority": _int(row.get("parallel_lane_priority")),
        "parallel_primary_blocker_action_id": _text(row.get("parallel_primary_blocker_action_id")),
        "blocked_by_action_id": _text(row.get("blocked_by_action_id")),
        "first_blocked_stage_id": _text(row.get("first_blocked_stage_id")),
        "first_blocked_evidence_row_id": _text(row.get("first_blocked_evidence_row_id")),
        "first_blocked_target_id": _text(row.get("first_blocked_target_id")),
        "first_blocked_candidate": _text(row.get("first_blocked_candidate")),
        "first_blocked_required_missing_fields": _text(row.get("first_blocked_required_missing_fields")),
        "next_after_actionable_blocker_stage_id": _text(
            row.get("next_after_actionable_blocker_stage_id")
        ),
        "next_after_actionable_blocker_artifact": _text(
            row.get("next_after_actionable_blocker_artifact")
        ),
        "next_after_actionable_blocker_validation_command": _text(
            row.get("next_after_actionable_blocker_validation_command")
        ),
        "next_after_actionable_blocker_required_checks": ";".join(
            _list(row.get("next_after_actionable_blocker_required_checks"))
        ),
        "next_after_actionable_blocker_unlock_fields": ";".join(
            _list(row.get("next_after_actionable_blocker_unlock_fields"))
        ),
        "return_bundle_required_artifact_count": _int(row.get("return_bundle_required_artifact_count")),
        "return_bundle_required_artifacts": ";".join(_list(row.get("return_bundle_required_artifacts"))),
        "return_bundle_artifact_completion_matrix_count": _int(
            row.get("return_bundle_artifact_completion_matrix_count")
        ),
        "return_bundle_next_artifact_id": _text(row.get("return_bundle_next_artifact_id")),
        "return_bundle_next_artifact_path": _text(row.get("return_bundle_next_artifact_path")),
        "return_bundle_next_artifact_failed_check_ids": ";".join(
            _list(row.get("return_bundle_next_artifact_failed_check_ids"))
        ),
        "return_bundle_manifest_required_columns": ";".join(
            _list(row.get("return_bundle_manifest_required_columns"))
        ),
        "return_bundle_post_return_validation_command": _text(
            row.get("return_bundle_post_return_validation_command")
        ),
        "return_bundle_guardrail": _text(row.get("return_bundle_guardrail")),
    }


def build_product_commercial_readiness_operator_packet(
    *,
    goal_audit_packet: dict[str, Any],
    delta_force_closure_packet: dict[str, Any] | None = None,
    scope_closure_packet: dict[str, Any] | None = None,
    aqp1_direct_binding_procurement_packet: dict[str, Any] | None = None,
    aqp1_external_operator_fill_guide_packet: dict[str, Any] | None = None,
    aqp1_external_operator_worksheet_packet: dict[str, Any] | None = None,
    aqp1_external_operator_staging_apply_packet: dict[str, Any] | None = None,
    production_ai_registry_promotion_operator_receipt_packet: dict[str, Any] | None = None,
    production_ai_registry_promotion_priority_packet: dict[str, Any] | None = None,
    production_ai_registry_promotion_field_worksheet_packet: dict[str, Any] | None = None,
    product_scope_breadth_evidence_field_worksheet_packet: dict[str, Any] | None = None,
    engine_refinement_claim_evidence_field_worksheet_packet: dict[str, Any] | None = None,
    goal_audit_path: str = DEFAULT_GOAL_AUDIT_JSON,
    delta_force_closure_packet_path: str = DEFAULT_DELTA_FORCE_CLOSURE_PACKET_JSON,
    scope_closure_packet_path: str = DEFAULT_SCOPE_CLOSURE_PACKET_JSON,
    aqp1_direct_binding_procurement_path: str = DEFAULT_AQP1_DIRECT_BINDING_PROCUREMENT_JSON,
    aqp1_external_operator_fill_guide_path: str = DEFAULT_AQP1_EXTERNAL_OPERATOR_FILL_GUIDE_JSON,
    aqp1_external_operator_worksheet_path: str = DEFAULT_AQP1_EXTERNAL_OPERATOR_WORKSHEET_JSON,
    aqp1_external_operator_staging_apply_path: str = DEFAULT_AQP1_EXTERNAL_OPERATOR_STAGING_APPLY_JSON,
    production_ai_registry_promotion_operator_receipt_path: str = (
        DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_OPERATOR_RECEIPT_JSON
    ),
    production_ai_registry_promotion_priority_path: str = (
        DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_JSON
    ),
    production_ai_registry_promotion_field_worksheet_path: str = (
        DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_FIELD_WORKSHEET_JSON
    ),
    product_scope_breadth_evidence_field_worksheet_path: str = (
        DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_FIELD_WORKSHEET_JSON
    ),
    engine_refinement_claim_evidence_field_worksheet_path: str = (
        DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_FIELD_WORKSHEET_JSON
    ),
) -> dict[str, Any]:
    summary = _summary(goal_audit_packet)
    delta_force_closure = _summary(delta_force_closure_packet or {})
    scope_closure = _summary(scope_closure_packet or {})
    production_ai_registry_receipt = _summary(
        production_ai_registry_promotion_operator_receipt_packet or {}
    )
    production_ai_registry_priority = _summary(
        production_ai_registry_promotion_priority_packet or {}
    )
    production_ai_registry_field_worksheet = _summary(
        production_ai_registry_promotion_field_worksheet_packet or {}
    )
    product_scope_breadth_evidence_field_worksheet = _summary(
        product_scope_breadth_evidence_field_worksheet_packet or {}
    )
    engine_refinement_claim_evidence_field_worksheet = _summary(
        engine_refinement_claim_evidence_field_worksheet_packet or {}
    )
    aqp1_external_fill_guide = _summary(aqp1_external_operator_fill_guide_packet or {})
    aqp1_external_worksheet = _summary(aqp1_external_operator_worksheet_packet or {})
    aqp1_external_staging_apply = _summary(aqp1_external_operator_staging_apply_packet or {})
    raw_rows = summary.get("commercial_readiness_next_action_matrix")
    source_rows = [dict(row) for row in (raw_rows or []) if isinstance(row, dict)]
    rows = [
        _overlay_aqp1_procurement(
            dict(row),
            aqp1_direct_binding_procurement_packet or {},
            aqp1_direct_binding_procurement_path,
        )
        for row in source_rows
    ]
    csv_rows = [_csv_row(row) for row in rows]
    blocker_rows = [row for row in csv_rows if row["status"] != "ready"]
    raw_blocker_rows = [row for row in rows if _text(row.get("status")) != "ready"]
    parallel_rows = [
        row
        for row in rows
        if row.get("parallelizable_with_primary_blocker") is True and _text(row.get("status")) != "ready"
    ]
    parallel_rows = sorted(parallel_rows, key=lambda row: (_int(row.get("parallel_lane_priority")), _text(row.get("action_id"))))
    parallel_csv_rows = [
        row
        for row in csv_rows
        if row.get("parallelizable_with_primary_blocker") is True and _text(row.get("status")) != "ready"
    ]
    parallel_csv_rows = sorted(
        parallel_csv_rows,
        key=lambda row: (_int(row.get("parallel_lane_priority")), _text(row.get("action_id"))),
    )
    first = blocker_rows[0] if blocker_rows else {}
    first_raw = raw_blocker_rows[0] if raw_blocker_rows else {}
    first_parallel = parallel_csv_rows[0] if parallel_csv_rows else {}
    first_parallel_raw = parallel_rows[0] if parallel_rows else {}
    first_packet = _dict(first_raw.get("operator_completion_packet"))
    first_packet_keys = sorted(str(key) for key in first_packet)
    first_required_fields = _list(first_packet.get("required_fields_or_columns"))
    first_required_exact_evidence_fields = _list(first_packet.get("required_exact_evidence_fields"))
    first_worker_contract = _dict(first_packet.get("worker_runtime_receipt_contract"))
    production_ai_return_raw = next(
        (
            row
            for row in rows
            if _text(row.get("action_id")) == "production_ai_return_summary"
        ),
        {},
    )
    production_ai_return = next(
        (
            row
            for row in csv_rows
            if _text(row.get("action_id")) == "production_ai_return_summary"
        ),
        {},
    )
    production_ai_return_packet = _dict(production_ai_return_raw.get("operator_completion_packet"))
    production_ai_registry_raw = next(
        (
            row
            for row in rows
            if _text(row.get("action_id")) == "production_ai_registry_guarded_promotion"
        ),
        {},
    )
    production_ai_registry = next(
        (
            row
            for row in csv_rows
            if _text(row.get("action_id")) == "production_ai_registry_guarded_promotion"
        ),
        {},
    )
    production_ai_registry_packet = _dict(production_ai_registry_raw.get("operator_completion_packet"))
    transporter_scope_raw = next(
        (
            row
            for row in rows
            if _text(row.get("action_id")) == TRANSPORTER_NEXT_SLOT_ACTION_ID
        ),
        {},
    )
    transporter_scope = next(
        (
            row
            for row in csv_rows
            if _text(row.get("action_id")) == TRANSPORTER_NEXT_SLOT_ACTION_ID
        ),
        {},
    )
    engine_receipt_diagnostics = _receipt_diagnostics(
        summary,
        prefix="engine_refinement_claim_evidence_receipt",
        first_blocked_id_key="first_blocked_blocker_id",
    )
    scope_receipt_diagnostics = _receipt_diagnostics(
        summary,
        prefix="product_scope_breadth_evidence_receipt",
        first_blocked_id_key="first_blocked_scope_blocker_id",
    )
    source_sha256 = _goal_audit_source_sha256(goal_audit_packet)
    matrix_sha256 = _sha256_json(source_rows)
    packet_ready = bool(rows)
    out_summary = {
        "packet_type": "product_commercial_readiness_operator_packet",
        "status": "product_commercial_readiness_operator_packet_ready" if packet_ready else "missing_product_commercial_readiness_actions",
        "packet_ready": packet_ready,
        "goal_audit_artifact": goal_audit_path,
        "goal_audit_sha256": source_sha256,
        "commercial_readiness_matrix_sha256": matrix_sha256,
        "source_fingerprint_ready": bool(source_sha256 and matrix_sha256),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "engine_refinement_claim_promotion_ready": bool(
            summary.get("engine_refinement_claim_promotion_ready") is True
        ),
        "engine_refinement_claim_promotion_blocker_count": _int(
            summary.get("engine_refinement_claim_promotion_blocker_count")
        ),
        "engine_refinement_claim_promotion_action_row_count": _int(
            summary.get("engine_refinement_claim_promotion_action_row_count")
        ),
        "engine_refinement_claim_promotion_blockers": [
            str(item)
            for item in (summary.get("engine_refinement_claim_promotion_blockers") or [])
        ],
        "engine_refinement_claim_promotion_action_board_csv": _text(
            summary.get("engine_refinement_claim_promotion_action_board_csv")
        ),
        "engine_refinement_claim_evidence_receipt_ready": bool(
            summary.get("engine_refinement_claim_evidence_receipt_ready") is True
        ),
        "engine_refinement_claim_evidence_receipt_status": (
            engine_receipt_diagnostics["status"]
            or _text(summary.get("engine_refinement_claim_evidence_receipt_status"))
        ),
        "engine_refinement_claim_evidence_receipt_blocked_row_count": _int(
            summary.get("engine_refinement_claim_evidence_receipt_blocked_row_count")
        ),
        "engine_refinement_claim_evidence_receipt_artifact": _text(
            summary.get("engine_refinement_claim_evidence_receipt_artifact")
        ),
        "engine_refinement_claim_evidence_receipt_csv": _text(
            summary.get("engine_refinement_claim_evidence_receipt_csv")
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": (
            engine_receipt_diagnostics["first_blocked_id"]
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": (
            engine_receipt_diagnostics["first_blocked_evidence_artifact"]
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": (
            engine_receipt_diagnostics["first_blocked_expected_evidence_status"]
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": (
            engine_receipt_diagnostics["first_blocked_observed_evidence_status"]
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields": (
            engine_receipt_diagnostics["first_blocked_missing_true_fields"]
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": (
            engine_receipt_diagnostics["first_blocked_row_blockers"]
        ),
        "engine_refinement_claim_evidence_receipt_most_common_row_blocker": (
            engine_receipt_diagnostics["most_common_row_blocker"]
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_artifact": (
            engine_refinement_claim_evidence_field_worksheet_path
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_status": _text(
            engine_refinement_claim_evidence_field_worksheet.get("status")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_ready": bool(
            engine_refinement_claim_evidence_field_worksheet.get("field_worksheet_ready") is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete": bool(
            engine_refinement_claim_evidence_field_worksheet.get("operator_fill_complete") is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_field_row_count": _int(
            engine_refinement_claim_evidence_field_worksheet.get("worksheet_field_row_count")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_required_receipt_field_count": _int(
            engine_refinement_claim_evidence_field_worksheet.get("required_receipt_field_count")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count": _int(
            engine_refinement_claim_evidence_field_worksheet.get("operator_fill_pending_field_count")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count": _int(
            engine_refinement_claim_evidence_field_worksheet.get(
                "receipt_operator_fill_pending_field_count"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count": _int(
            engine_refinement_claim_evidence_field_worksheet.get(
                "public_benchmark_work_order_pending_field_count"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id": _text(
            engine_refinement_claim_evidence_field_worksheet.get("top_blocker_id")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket": _text(
            engine_refinement_claim_evidence_field_worksheet.get("top_priority_bucket")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_pending_field_count": _int(
            engine_refinement_claim_evidence_field_worksheet.get("top_blocker_pending_field_count")
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count": _int(
            engine_refinement_claim_evidence_field_worksheet.get(
                "public_benchmark_work_order_apply_blocked_row_count"
            )
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_claim_promoted": bool(
            engine_refinement_claim_evidence_field_worksheet.get("claim_promoted") is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_external_engine_calls_executed": bool(
            engine_refinement_claim_evidence_field_worksheet.get(
                "external_engine_calls_executed"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated": bool(
            engine_refinement_claim_evidence_field_worksheet.get("external_state_mutated")
            is True
        ),
        "engine_refinement_claim_promotion_next_required_step": _text(
            summary.get("engine_refinement_claim_promotion_next_required_step")
        ),
        "product_scope_breadth_evidence_receipt_status": _text(
            summary.get("product_scope_breadth_evidence_receipt_status")
        ),
        "product_scope_breadth_evidence_receipt_ready": bool(
            summary.get("product_scope_breadth_evidence_receipt_ready") is True
        ),
        "product_scope_breadth_evidence_receipt_blocker_count": _int(
            summary.get("product_scope_breadth_evidence_receipt_blocker_count")
        ),
        "product_scope_breadth_evidence_receipt_blocked_row_count": _int(
            summary.get("product_scope_breadth_evidence_receipt_blocked_row_count")
        ),
        "product_scope_breadth_evidence_receipt_required_scope_blocker_count": _int(
            summary.get("product_scope_breadth_evidence_receipt_required_scope_blocker_count")
        ),
        "product_scope_breadth_evidence_receipt_artifact": _text(
            summary.get("product_scope_breadth_evidence_receipt_artifact")
        ),
        "product_scope_breadth_evidence_receipt_csv": _text(
            summary.get("product_scope_breadth_evidence_receipt_csv")
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": (
            scope_receipt_diagnostics["first_blocked_id"]
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": (
            scope_receipt_diagnostics["first_blocked_evidence_artifact"]
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": (
            scope_receipt_diagnostics["first_blocked_expected_evidence_status"]
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": (
            scope_receipt_diagnostics["first_blocked_observed_evidence_status"]
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields": (
            scope_receipt_diagnostics["first_blocked_missing_true_fields"]
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_row_blockers": (
            scope_receipt_diagnostics["first_blocked_row_blockers"]
        ),
        "product_scope_breadth_evidence_receipt_most_common_row_blocker": (
            scope_receipt_diagnostics["most_common_row_blocker"]
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_artifact": (
            product_scope_breadth_evidence_field_worksheet_path
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_status": _text(
            product_scope_breadth_evidence_field_worksheet.get("status")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_ready": bool(
            product_scope_breadth_evidence_field_worksheet.get("field_worksheet_ready") is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_operator_fill_complete": bool(
            product_scope_breadth_evidence_field_worksheet.get("operator_fill_complete") is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_field_row_count": _int(
            product_scope_breadth_evidence_field_worksheet.get("receipt_field_row_count")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_required_receipt_field_count": _int(
            product_scope_breadth_evidence_field_worksheet.get("required_receipt_field_count")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_pending_field_count": _int(
            product_scope_breadth_evidence_field_worksheet.get("operator_fill_pending_field_count")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id": _text(
            product_scope_breadth_evidence_field_worksheet.get("top_blocker_id")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_pending_field_count": _int(
            product_scope_breadth_evidence_field_worksheet.get("top_blocker_pending_field_count")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_item_id": _text(
            product_scope_breadth_evidence_field_worksheet.get("top_item_id")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_bucket": _text(
            product_scope_breadth_evidence_field_worksheet.get("top_bucket")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_required_evidence_type": _text(
            product_scope_breadth_evidence_field_worksheet.get("top_required_evidence_type")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_priority_open_item_count": _int(
            product_scope_breadth_evidence_field_worksheet.get("priority_open_item_count")
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_priority_local_crosscheck_candidate_count": _int(
            product_scope_breadth_evidence_field_worksheet.get(
                "priority_local_crosscheck_candidate_count"
            )
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_scope_checklist_manual_review_subcheck_count": _int(
            product_scope_breadth_evidence_field_worksheet.get(
                "scope_checklist_manual_review_subcheck_count"
            )
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_claim_promoted": bool(
            product_scope_breadth_evidence_field_worksheet.get("claim_promoted") is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_external_state_mutated": bool(
            product_scope_breadth_evidence_field_worksheet.get("external_state_mutated") is True
        ),
        "open_gap_ids": [str(item) for item in (summary.get("product_ai_architecture_open_gap_ids") or [])],
        "action_count": len(rows),
        "blocked_action_count": len(blocker_rows),
        "ready_action_count": len(rows) - len(blocker_rows),
        "parallelizable_action_count": len(parallel_rows),
        "parallelizable_action_ids": [_text(row.get("action_id")) for row in parallel_rows],
        "first_parallelizable_action_id": _text(first_parallel.get("action_id")),
        "first_parallelizable_action_artifact": _text(first_parallel.get("artifact")),
        "first_parallelizable_action_next_action": _text(first_parallel.get("next_action")),
        "first_parallelizable_action_validation_command": _text(
            first_parallel.get("validation_command")
        ),
        "first_parallelizable_action_required_operator_inputs": _text(
            first_parallel.get("required_operator_inputs")
        ),
        "first_parallelizable_action_required_exact_evidence_fields": _text(
            first_parallel.get("required_exact_evidence_fields")
        ),
        "first_parallelizable_action_required_claim_guardrails": _text(
            first_parallel.get("required_claim_guardrails")
        ),
        "first_parallelizable_action_expected_evidence_type": _text(
            first_parallel.get("expected_evidence_type")
        ),
        "first_parallelizable_action_required_missing_fields": _text(
            first_parallel.get("required_missing_fields")
        ),
        "first_parallelizable_action_operator_review_artifact": _text(
            first_parallel.get("operator_review_artifact")
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": _text(
            first_parallel.get("post_intake_synchronization_targets")
        ),
        "first_parallelizable_action_acceptance_gate_commands": _text(
            first_parallel.get("acceptance_gate_commands")
        ),
        "first_parallelizable_action_next_slot_source_modality_guard_ready": bool(
            first_parallel.get("next_slot_source_modality_guard_ready") is True
        ),
        "first_parallelizable_action_next_slot_source_modality": _text(
            first_parallel.get("next_slot_source_modality")
        ),
        "first_parallelizable_action_next_slot_source_modality_claim_safe": bool(
            first_parallel.get("next_slot_source_modality_claim_safe") is True
        ),
        "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed": bool(
            first_parallel.get("next_slot_source_modality_direct_binding_claim_allowed") is True
        ),
        "first_parallelizable_action_next_slot_source_modality_decision": _text(
            first_parallel.get("next_slot_source_modality_decision")
        ),
        "first_parallelizable_action_next_slot_source_modality_guardrails": _list(
            first_parallel.get("next_slot_source_modality_guardrails")
        ),
        "first_parallelizable_action_next_slot_source_modality_observed_signal": _text(
            first_parallel.get("next_slot_source_modality_observed_signal")
        ),
        "first_parallelizable_action_next_slot_source_modality_required_upgrade": _text(
            first_parallel.get("next_slot_source_modality_required_upgrade")
        ),
        "first_parallelizable_action_next_slot_source_modality_triage_artifact": _text(
            first_parallel.get("next_slot_source_modality_triage_artifact")
        ),
        "first_parallelizable_action_next_slot_source_modality_triage_decision": _text(
            first_parallel.get("next_slot_source_modality_triage_decision")
        ),
        "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count": _int(
            first_parallel.get("next_slot_source_modality_direct_experimental_binding_row_count")
        ),
        "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count": _int(
            first_parallel.get("next_slot_source_modality_claim_safe_binding_kcal_ready_count")
        ),
        "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count": _int(
            first_parallel.get("next_slot_source_modality_computational_binding_energy_row_count")
        ),
        "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol": _text(
            first_parallel.get("next_slot_source_modality_best_computational_binding_energy_kcal_mol")
        ),
        "first_parallelizable_action_operator_validation_candidate_ready": bool(
            first_parallel.get("operator_validation_candidate_ready") is True
        ),
        "first_parallelizable_action_operator_validation_candidate_status": _text(
            first_parallel.get("operator_validation_candidate_status")
        ),
        "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier": _text(
            first_parallel.get("operator_validation_candidate_ligand_external_identifier")
        ),
        "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol": _text(
            first_parallel.get("operator_validation_candidate_reference_binding_kcal_mol")
        ),
        "first_parallelizable_action_operator_validation_candidate_blocker": _text(
            first_parallel.get("operator_validation_candidate_blocker")
        ),
        "first_parallelizable_action_operator_validation_candidate_claim_safe_ready": bool(
            first_parallel.get("operator_validation_candidate_claim_safe_ready") is True
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_ready": bool(
            first_parallel.get("direct_binding_procurement_packet_ready") is True
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_status": _text(
            first_parallel.get("direct_binding_procurement_packet_status")
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_artifact": _text(
            first_parallel.get("direct_binding_procurement_packet_artifact")
        ),
        "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open": bool(
            first_parallel.get("direct_binding_procurement_direct_binding_gap_open") is True
        ),
        "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required": bool(
            first_parallel.get("direct_binding_procurement_external_primary_evidence_required") is True
        ),
        "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id": _text(
            first_parallel.get("direct_binding_procurement_first_required_external_action_id")
        ),
        "first_parallelizable_action_direct_binding_procurement_current_operator_candidate_blocker": _text(
            first_parallel.get("direct_binding_procurement_current_operator_candidate_blocker")
        ),
        "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule": _text(
            first_parallel.get("direct_binding_procurement_minimum_acceptance_rule")
        ),
        "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods": _list(
            first_parallel.get("direct_binding_procurement_accepted_direct_binding_methods")
        ),
        "first_parallelizable_action_direct_binding_procurement_acceptance_fields": _list(
            first_parallel.get("direct_binding_procurement_acceptance_fields")
        ),
        "first_parallelizable_action_lane_id": _text(first_parallel.get("workstream_lane_id")),
        "first_parallelizable_action_precondition": _text(
            first_parallel.get("parallel_lane_precondition")
        ),
        "first_parallelizable_action_packet": first_parallel_raw,
        "first_action_id": _text(first.get("action_id")),
        "first_artifact": _text(first.get("artifact")),
        "first_execution_command": _text(first.get("execution_command")),
        "first_validation_command": _text(first.get("validation_command")),
        "first_operator_completion_packet_ready": bool(first_raw.get("operator_completion_packet_ready") is True),
        "first_operator_completion_packet_keys": first_packet_keys,
        "first_operator_completion_artifact_id": _text(first_packet.get("artifact_id")),
        "first_operator_completion_artifact_path": _text(first_packet.get("artifact_path")),
        "first_operator_completion_required_fields_or_columns": first_required_fields,
        "first_operator_completion_required_exact_evidence_fields": first_required_exact_evidence_fields,
        "first_operator_completion_validation_command": _text(first_packet.get("validation_command")),
        "first_operator_completion_next_action": _text(first_packet.get("next_action")),
        "first_operator_completion_packet": first_packet,
        "first_operator_completion_worker_runtime_receipt_contract_ready": bool(first_worker_contract),
        "first_operator_completion_worker_runtime_receipt_contract": first_worker_contract,
        "first_operator_completion_worker_runtime_receipt_required_fields_or_columns": _list(
            first_packet.get("worker_runtime_receipt_required_fields_or_columns")
        ),
        "first_operator_completion_worker_runtime_receipt_required_field_count": _int(
            first_packet.get("worker_runtime_receipt_required_field_count")
        ),
        "first_operator_completion_worker_runtime_receipt_completion_rule": _text(
            first_packet.get("worker_runtime_receipt_completion_rule")
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id": _text(
            first_packet.get("post_environment_next_stage_id")
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact": _text(
            first_packet.get("post_environment_next_artifact")
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_validation_command": _text(
            first_packet.get("post_environment_validation_command")
        ),
        "first_operator_completion_worker_runtime_receipt_full_regeneration_command": _text(
            first_packet.get("full_regeneration_command")
        ),
        "first_operator_completion_worker_runtime_receipt_guardrails": _list(
            first_packet.get("worker_runtime_receipt_guardrails")
        ),
        "first_operator_completion_diagnostic_commands": _list(
            first_packet.get("diagnostic_commands")
        ),
        "first_operator_completion_diagnostic_command_count": _int(
            first_packet.get("diagnostic_command_count")
        ),
        "first_operator_completion_diagnostic_required_fields": _list(
            first_packet.get("diagnostic_required_fields")
        ),
        "first_operator_completion_diagnostic_required_field_count": _int(
            first_packet.get("diagnostic_required_field_count")
        ),
        "first_operator_completion_diagnostic_completion_rule": _text(
            first_packet.get("diagnostic_completion_rule")
        ),
        "first_operator_completion_diagnostic_return_artifacts": _list(
            first_packet.get("diagnostic_return_artifacts")
        ),
        "first_operator_completion_torch_visibility_probe_command": _text(
            first_packet.get("torch_visibility_probe_command")
        ),
        "production_ai_return_action_id": _text(production_ai_return.get("action_id")),
        "production_ai_return_action_artifact": _text(production_ai_return.get("artifact")),
        "production_ai_return_action_next_action": _text(production_ai_return.get("next_action")),
        "production_ai_return_action_execution_command": _text(
            production_ai_return.get("execution_command")
        ),
        "production_ai_return_action_validation_command": _text(
            production_ai_return.get("validation_command")
        ),
        "production_ai_return_action_blocked_by_action_id": _text(
            production_ai_return.get("blocked_by_action_id")
        ),
        "production_ai_return_action_required_operator_inputs": _text(
            production_ai_return.get("required_operator_inputs")
        ),
        "production_ai_return_action_required_evidence": _text(
            production_ai_return.get("required_evidence")
        ),
        "production_ai_return_operator_completion_packet_ready": bool(
            production_ai_return_raw.get("operator_completion_packet_ready") is True
        ),
        "production_ai_return_operator_completion_packet_keys": sorted(
            str(key) for key in production_ai_return_packet
        ),
        "production_ai_return_operator_completion_artifact_id": _text(
            production_ai_return_packet.get("artifact_id")
        ),
        "production_ai_return_operator_completion_artifact_path": _text(
            production_ai_return_packet.get("artifact_path")
        ),
        "production_ai_return_operator_completion_required_fields_or_columns": _list(
            production_ai_return_packet.get("required_fields_or_columns")
        ),
        "production_ai_return_operator_completion_template_payload_json": _text(
            production_ai_return_packet.get("template_payload_json")
        ),
        "production_ai_return_operator_completion_expected_queue_rows": _int(
            production_ai_return_packet.get("expected_queue_rows")
        ),
        "production_ai_return_operator_completion_completion_rule": _text(
            production_ai_return_packet.get("completion_rule")
        ),
        "production_ai_return_operator_completion_backend_provenance_completion_rule": _text(
            production_ai_return_packet.get("backend_provenance_completion_rule")
        ),
        "production_ai_return_operator_completion_failed_check_ids": [
            str(item) for item in _list(production_ai_return_packet.get("failed_check_ids"))
        ],
        "production_ai_return_operator_completion_packet": production_ai_return_packet,
        "production_ai_registry_promotion_action_id": _text(production_ai_registry.get("action_id")),
        "production_ai_registry_promotion_action_artifact": _text(production_ai_registry.get("artifact")),
        "production_ai_registry_promotion_action_next_action": _text(production_ai_registry.get("next_action")),
        "production_ai_registry_promotion_action_validation_command": _text(
            production_ai_registry.get("validation_command")
        ),
        "production_ai_registry_promotion_action_blocked_by_action_id": _text(
            production_ai_registry.get("blocked_by_action_id")
        ),
        "production_ai_registry_promotion_action_required_operator_inputs": _text(
            production_ai_registry.get("required_operator_inputs")
        ),
        "production_ai_registry_promotion_action_required_evidence": _text(
            production_ai_registry.get("required_evidence")
        ),
        "production_ai_registry_promotion_operator_completion_packet_ready": bool(
            production_ai_registry_raw.get("operator_completion_packet_ready") is True
        ),
        "production_ai_registry_promotion_operator_completion_packet_keys": sorted(
            str(key) for key in production_ai_registry_packet
        ),
        "production_ai_registry_promotion_operator_completion_artifact_id": _text(
            production_ai_registry_packet.get("artifact_id")
        ),
        "production_ai_registry_promotion_operator_completion_artifact_path": _text(
            production_ai_registry_packet.get("artifact_path")
        ),
        "production_ai_registry_promotion_operator_completion_required_fields_or_columns": _list(
            production_ai_registry_packet.get("required_fields_or_columns")
        ),
        "production_ai_registry_promotion_operator_completion_diagnostic_commands": _list(
            production_ai_registry_packet.get("diagnostic_commands")
        ),
        "production_ai_registry_promotion_operator_completion_diagnostic_command_count": _int(
            production_ai_registry_packet.get("diagnostic_command_count")
        ),
        "production_ai_registry_promotion_operator_completion_completion_rule": _text(
            production_ai_registry_packet.get("completion_rule")
        ),
        "production_ai_registry_promotion_operator_completion_failed_check_ids": [
            str(item) for item in _list(production_ai_registry_packet.get("failed_check_ids"))
        ],
        "production_ai_registry_promotion_operator_completion_packet": production_ai_registry_packet,
        "production_ai_registry_promotion_operator_receipt_artifact": (
            production_ai_registry_promotion_operator_receipt_path
        ),
        "production_ai_registry_promotion_operator_receipt_status": _text(
            production_ai_registry_receipt.get("status")
        ),
        "production_ai_registry_promotion_operator_receipt_ready": bool(
            production_ai_registry_receipt.get("operator_receipt_ready") is True
        ),
        "production_ai_registry_promotion_operator_receipt_present": bool(
            production_ai_registry_receipt.get("receipt_present") is True
        ),
        "production_ai_registry_promotion_operator_receipt_csv": _text(
            production_ai_registry_receipt.get("receipt_csv")
        ),
        "production_ai_registry_promotion_operator_receipt_row_count": _int(
            production_ai_registry_receipt.get("receipt_row_count")
        ),
        "production_ai_registry_promotion_operator_receipt_blocker_count": _int(
            production_ai_registry_receipt.get("blocker_count")
        ),
        "production_ai_registry_promotion_operator_receipt_blocked_row_count": _int(
            production_ai_registry_receipt.get("blocked_row_count")
        ),
        "production_ai_registry_promotion_operator_receipt_blockers": [
            str(item) for item in _list(production_ai_registry_receipt.get("blockers"))
        ],
        "production_ai_registry_promotion_operator_receipt_first_blocked_artifact_id": _text(
            production_ai_registry_receipt.get("first_blocked_artifact_id")
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker": _text(
            production_ai_registry_receipt.get("first_blocked_row_blocker")
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blockers": [
            str(item)
            for item in _list(production_ai_registry_receipt.get("first_blocked_row_blockers"))
        ],
        "production_ai_registry_promotion_operator_receipt_most_common_row_blocker": _text(
            production_ai_registry_receipt.get("most_common_row_blocker")
        ),
        "production_ai_registry_promotion_operator_receipt_approval_token_required": _text(
            production_ai_registry_receipt.get("approval_token_required")
        ),
        "production_ai_registry_promotion_operator_receipt_next_required_step": _text(
            production_ai_registry_receipt.get("next_required_step")
        ),
        "production_ai_registry_promotion_operator_receipt_registry_artifact": _text(
            production_ai_registry_receipt.get("registry_artifact")
        ),
        "production_ai_registry_promotion_operator_receipt_checkpoint_readiness_artifact": _text(
            production_ai_registry_receipt.get("checkpoint_readiness_artifact")
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode": _text(
            production_ai_registry_receipt.get("observed_registry_default_residual_mode")
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count": _int(
            production_ai_registry_receipt.get("observed_registry_trained_model_checkpoint_count")
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied": bool(
            production_ai_registry_receipt.get(
                "observed_checkpoint_registry_promotion_currently_satisfied"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids": [
            str(item)
            for item in _list(
                production_ai_registry_receipt.get(
                    "observed_checkpoint_registry_promotion_missing_gate_ids"
                )
            )
        ],
        "production_ai_registry_promotion_operator_receipt_registry_edited_by_this_tool": bool(
            production_ai_registry_receipt.get("registry_edited_by_this_tool") is True
        ),
        "production_ai_registry_promotion_operator_receipt_checkpoint_created_by_this_tool": bool(
            production_ai_registry_receipt.get("checkpoint_created_by_this_tool") is True
        ),
        "production_ai_registry_promotion_priority_artifact": (
            production_ai_registry_promotion_priority_path
        ),
        "production_ai_registry_promotion_priority_status": _text(
            production_ai_registry_priority.get("status")
        ),
        "production_ai_registry_promotion_priority_packet_ready": bool(
            production_ai_registry_priority.get("priority_packet_ready") is True
        ),
        "production_ai_registry_promotion_priority_registry_promotion_ready": bool(
            production_ai_registry_priority.get("registry_promotion_ready") is True
        ),
        "production_ai_registry_promotion_priority_operator_input_required_count": _int(
            production_ai_registry_priority.get("operator_input_required_count")
        ),
        "production_ai_registry_promotion_priority_blocked_priority_item_count": _int(
            production_ai_registry_priority.get("blocked_priority_item_count")
        ),
        "production_ai_registry_promotion_priority_missing_gate_count": _int(
            production_ai_registry_priority.get("registry_promotion_missing_gate_count")
        ),
        "production_ai_registry_promotion_priority_missing_gate_ids": [
            str(item)
            for item in _list(
                production_ai_registry_priority.get("registry_promotion_missing_gate_ids")
            )
        ],
        "production_ai_registry_promotion_priority_operator_receipt_csv": _text(
            production_ai_registry_priority.get("operator_receipt_csv")
        ),
        "production_ai_registry_promotion_priority_approval_token_required": _text(
            production_ai_registry_priority.get("approval_token_required")
        ),
        "production_ai_registry_promotion_priority_observed_registry_default_residual_mode": _text(
            production_ai_registry_priority.get("observed_registry_default_residual_mode")
        ),
        "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed": bool(
            production_ai_registry_priority.get("observed_registry_production_promotion_allowed")
            is True
        ),
        "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready": bool(
            production_ai_registry_priority.get(
                "observed_registry_customer_facing_mutation_flags_ready"
            )
            is True
        ),
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": _int(
            production_ai_registry_priority.get("observed_registry_trained_model_checkpoint_count")
        ),
        "production_ai_registry_promotion_priority_top_gate_id": _text(
            production_ai_registry_priority.get("top_gate_id")
        ),
        "production_ai_registry_promotion_priority_top_priority_bucket": _text(
            production_ai_registry_priority.get("top_priority_bucket")
        ),
        "production_ai_registry_promotion_priority_top_required_input": _text(
            production_ai_registry_priority.get("top_required_input")
        ),
        "production_ai_registry_promotion_priority_top_acceptance_artifact": _text(
            production_ai_registry_priority.get("top_acceptance_artifact")
        ),
        "production_ai_registry_promotion_priority_top_verification_command": _text(
            production_ai_registry_priority.get("top_verification_command")
        ),
        "production_ai_registry_promotion_priority_top_next_operator_step": _text(
            production_ai_registry_priority.get("top_next_operator_step")
        ),
        "production_ai_registry_promotion_priority_model_promoted": bool(
            production_ai_registry_priority.get("model_promoted") is True
        ),
        "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": bool(
            production_ai_registry_priority.get("customer_facing_mutation_enabled") is True
        ),
        "production_ai_registry_promotion_priority_external_state_mutated": bool(
            production_ai_registry_priority.get("external_state_mutated") is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_artifact": (
            production_ai_registry_promotion_field_worksheet_path
        ),
        "production_ai_registry_promotion_operator_field_worksheet_status": _text(
            production_ai_registry_field_worksheet.get("status")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_ready": bool(
            production_ai_registry_field_worksheet.get("field_worksheet_ready") is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_operator_fill_complete": bool(
            production_ai_registry_field_worksheet.get("operator_fill_complete") is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_field_row_count": _int(
            production_ai_registry_field_worksheet.get("worksheet_field_row_count")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_required_field_count": _int(
            production_ai_registry_field_worksheet.get("required_receipt_field_count")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_count": _int(
            production_ai_registry_field_worksheet.get("operator_fill_pending_field_count")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_diagnostic_required_field_count": _int(
            production_ai_registry_field_worksheet.get("diagnostic_required_field_count")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count": _int(
            production_ai_registry_field_worksheet.get("diagnostic_required_pending_field_count")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_names": [
            str(item)
            for item in _list(production_ai_registry_field_worksheet.get("pending_field_names"))
        ],
        "production_ai_registry_promotion_operator_field_worksheet_top_gate_id": _text(
            production_ai_registry_field_worksheet.get("top_gate_id")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_top_required_input": _text(
            production_ai_registry_field_worksheet.get("top_required_input")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_approval_token_required": _text(
            production_ai_registry_field_worksheet.get("approval_token_required")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_observed_registry_default_residual_mode": _text(
            production_ai_registry_field_worksheet.get("observed_registry_default_residual_mode")
        ),
        "production_ai_registry_promotion_operator_field_worksheet_observed_registry_trained_model_checkpoint_count": _int(
            production_ai_registry_field_worksheet.get(
                "observed_registry_trained_model_checkpoint_count"
            )
        ),
        "production_ai_registry_promotion_operator_field_worksheet_model_promoted": bool(
            production_ai_registry_field_worksheet.get("model_promoted") is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_customer_facing_mutation_enabled": bool(
            production_ai_registry_field_worksheet.get("customer_facing_mutation_enabled")
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated": bool(
            production_ai_registry_field_worksheet.get("external_state_mutated") is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_next_required_step": _text(
            production_ai_registry_field_worksheet.get("next_required_step")
        ),
        "production_ai_return_bundle_required_artifact_count": _int(
            production_ai_return.get("return_bundle_required_artifact_count")
        ),
        "production_ai_return_bundle_required_artifacts": _list(
            production_ai_return.get("return_bundle_required_artifacts")
        ),
        "production_ai_return_bundle_artifact_completion_matrix_count": _int(
            production_ai_return.get("return_bundle_artifact_completion_matrix_count")
        ),
        "production_ai_return_bundle_next_artifact_id": _text(
            production_ai_return.get("return_bundle_next_artifact_id")
        ),
        "production_ai_return_bundle_next_artifact_path": _text(
            production_ai_return.get("return_bundle_next_artifact_path")
        ),
        "production_ai_return_bundle_next_artifact_failed_check_ids": _list(
            production_ai_return.get("return_bundle_next_artifact_failed_check_ids")
        ),
        "production_ai_return_bundle_manifest_required_columns": _list(
            production_ai_return.get("return_bundle_manifest_required_columns")
        ),
        "production_ai_return_bundle_post_return_validation_command": _text(
            production_ai_return.get("return_bundle_post_return_validation_command")
        ),
        "production_ai_return_bundle_guardrail": _text(
            production_ai_return.get("return_bundle_guardrail")
        ),
        "delta_force_closure_acceptance_packet_artifact": delta_force_closure_packet_path,
        "delta_force_closure_acceptance_packet_ready": bool(
            delta_force_closure.get("packet_ready") is True
        ),
        "delta_force_closure_ready": bool(
            delta_force_closure.get("delta_force_closure_ready") is True
        ),
        "delta_force_closure_first_blocked_output_field": _text(
            delta_force_closure.get("first_blocked_output_field")
        ),
        "delta_force_closure_ready_output_field_count": _int(
            delta_force_closure.get("ready_output_field_count")
        ),
        "delta_force_closure_blocked_output_field_count": _int(
            delta_force_closure.get("blocked_output_field_count")
        ),
        "delta_force_closure_failed_stage_count": _int(
            delta_force_closure.get("closure_failed_stage_count")
        ),
        "delta_force_closure_failed_stage_ids": _list(
            delta_force_closure.get("closure_failed_stage_ids")
        ),
        "delta_force_closure_next_stage_id": _text(
            delta_force_closure.get("next_stage_id")
        ),
        "delta_force_closure_next_stage_artifact": _text(
            delta_force_closure.get("next_stage_artifact")
        ),
        "delta_force_closure_next_stage_validation_command": _text(
            delta_force_closure.get("next_stage_validation_command")
        ),
        "delta_force_closure_next_required_step": _text(
            delta_force_closure.get("next_required_step")
        ),
        "delta_force_closure_operator_return_required_artifact_count": _int(
            delta_force_closure.get("operator_return_required_artifact_count")
        ),
        "delta_force_closure_operator_return_required_artifacts": _list(
            delta_force_closure.get("operator_return_required_artifacts")
        ),
        "delta_force_closure_return_summary_required_fields": _list(
            delta_force_closure.get("return_summary_required_fields")
        ),
        "delta_force_closure_post_return_validation_command": _text(
            delta_force_closure.get("post_return_validation_command")
        ),
        "scope_closure_acceptance_packet_artifact": scope_closure_packet_path,
        "scope_closure_acceptance_packet_ready": bool(
            scope_closure.get("packet_ready") is True
        ),
        "scope_closure_ready": bool(scope_closure.get("scope_closure_ready") is True),
        "scope_closure_stage_count": _int(
            scope_closure.get("scope_acceptance_stage_count")
        ),
        "scope_closure_blocked_stage_count": _int(
            scope_closure.get("scope_acceptance_blocked_stage_count")
        ),
        "scope_closure_blocked_stage_ids": _list(
            scope_closure.get("scope_acceptance_blocked_stage_ids")
        ),
        "scope_closure_next_stage_id": _text(
            scope_closure.get("scope_acceptance_next_stage_id")
        ),
        "scope_closure_next_stage_artifact": _text(
            scope_closure.get("scope_acceptance_next_stage_artifact")
        ),
        "scope_closure_next_stage_validation_command": _text(
            scope_closure.get("scope_acceptance_next_stage_validation_command")
        ),
        "scope_closure_first_blocked_evidence_row_id": _text(
            scope_closure.get("first_blocked_evidence_row_id")
        ),
        "scope_closure_first_blocked_target_id": _text(
            scope_closure.get("first_blocked_target_id")
        ),
        "scope_closure_first_blocked_candidate": _text(
            scope_closure.get("first_blocked_candidate")
        ),
        "scope_closure_first_blocked_required_missing_fields": _text(
            scope_closure.get("first_blocked_required_missing_fields")
        ),
        "scope_closure_transporter_unresolved_slot_count": _int(
            scope_closure.get("transporter_unresolved_slot_count")
        ),
        "scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count": _int(
            scope_closure.get("pxr_direct_or_claim_safe_quantitative_ready_count")
        ),
        "scope_closure_general_platform_claim_allowed": bool(
            scope_closure.get("general_platform_claim_allowed") is True
        ),
        "scope_closure_next_required_step": _text(
            scope_closure.get("next_required_step")
        ),
        "operator_input_total_count": sum(len(_list(row.get("required_operator_inputs"))) for row in rows),
        "operator_completion_packet_ready_count": sum(
            1 for row in rows if row.get("operator_completion_packet_ready") is True
        ),
        "release_blocker_action_ids": [
            row["action_id"] for row in blocker_rows if row.get("release_blocker") is True
        ],
        "next_required_step": (
            _text(first.get("next_action"))
            if first
            else "No blocked commercial readiness action remains in the current goal-completion audit."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
    }
    primary_requirement_id = _text(summary.get("primary_release_blocker_requirement_id"))
    scope_receipt_csv = _text(summary.get("product_scope_breadth_evidence_receipt_csv"))
    scope_next_item_id = _text(summary.get("product_scope_next_operator_completion_item_id"))
    scope_next_required_evidence = _text(
        summary.get("product_scope_next_operator_completion_required_evidence_type")
    )
    transporter_return_required_artifacts = (
        _list(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts"
            )
        )
        or _list(transporter_scope.get("return_bundle_required_artifacts"))
        or _list(transporter_scope_raw.get("return_bundle_required_artifacts"))
    )
    transporter_return_failed_checks = (
        _list(transporter_scope.get("return_bundle_next_artifact_failed_check_ids"))
        or _list(transporter_scope_raw.get("return_bundle_next_artifact_failed_check_ids"))
    )
    transporter_completion_packet = _dict(
        summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet")
    )
    out_summary.update(
        {
            "primary_full_commercial_release_blocker_id": primary_requirement_id,
            "primary_full_commercial_release_blocker_requirement_id": primary_requirement_id,
            "primary_full_commercial_release_blocker_tier": _text(
                summary.get("primary_release_blocker_tier")
            ),
            "primary_full_commercial_release_blocker": _text(
                summary.get("primary_release_blocker")
            ),
            "primary_full_commercial_release_blocker_blocked_row_count": _int(
                summary.get("product_scope_breadth_evidence_receipt_blocked_row_count")
            ),
            "primary_full_commercial_release_blocker_first_blocked_evidence_row_id": (
                scope_receipt_diagnostics["first_blocked_id"]
            ),
            "primary_full_commercial_release_blocker_receipt_csv": scope_receipt_csv,
            "primary_full_commercial_release_blocker_approval_token_required": _text(
                summary.get("product_scope_breadth_evidence_receipt_approval_token_required")
            )
            or "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
            "primary_full_commercial_release_blocker_next_required_step": _text(
                summary.get("product_scope_breadth_evidence_receipt_next_required_step")
            )
            or _text(summary.get("product_scope_evidence_priority_next_required_step"))
            or _text(summary.get("primary_release_blocker_next_command")),
            "product_scope_next_operator_completion_item_id": scope_next_item_id,
            "product_scope_next_operator_completion_intake_mode": _text(
                summary.get("product_scope_next_operator_completion_intake_mode")
            ),
            "product_scope_next_operator_completion_required_evidence_type": (
                scope_next_required_evidence
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_activity_type": _text(
                summary.get(
                    "product_scope_next_operator_completion_transporter_best_evidence_activity_type"
                )
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_value": _text(
                summary.get(
                    "product_scope_next_operator_completion_transporter_best_evidence_value"
                )
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_units": _text(
                summary.get(
                    "product_scope_next_operator_completion_transporter_best_evidence_units"
                )
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_document_id": _text(
                summary.get(
                    "product_scope_next_operator_completion_transporter_best_evidence_document_id"
                )
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_source_file": _text(
                summary.get(
                    "product_scope_next_operator_completion_transporter_best_evidence_source_file"
                )
            ),
            "product_scope_next_operator_completion_transporter_claim_safe_blocker": _text(
                summary.get(
                    "product_scope_next_operator_completion_transporter_claim_safe_blocker"
                )
            ),
            "product_scope_next_operator_completion_transporter_operator_next_verdict": _text(
                summary.get(
                    "product_scope_next_operator_completion_transporter_operator_next_verdict"
                )
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_id": (
                _text(
                    summary.get(
                        "product_scope_transporter_p0_evidence_acquisition_next_slot_id"
                    )
                )
                or scope_next_item_id
                or _text(transporter_scope_raw.get("next_slot_id"))
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
                summary.get(
                    "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"
                )
                is True
                or bool(transporter_completion_packet)
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": _text(
                summary.get(
                    "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact"
                )
            )
            or _text(transporter_scope.get("operator_review_artifact")),
            "product_scope_transporter_p0_return_bundle_required_artifact_count": _int(
                summary.get(
                    "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
                )
            )
            or _int(transporter_scope.get("return_bundle_required_artifact_count")),
            "product_scope_transporter_p0_return_bundle_required_artifacts": (
                transporter_return_required_artifacts
            ),
            "product_scope_transporter_p0_return_bundle_blocker_count": _int(
                summary.get(
                    "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count"
                )
            ),
            "product_scope_transporter_p0_return_bundle_next_artifact_id": _text(
                summary.get(
                    "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id"
                )
            )
            or _text(transporter_scope.get("return_bundle_next_artifact_id")),
            "product_scope_transporter_p0_return_bundle_next_artifact_path": _text(
                summary.get(
                    "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path"
                )
            )
            or _text(transporter_scope.get("return_bundle_next_artifact_path")),
            "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids": (
                transporter_return_failed_checks
            ),
            "product_scope_transporter_p0_operator_validation_candidate_ready": bool(
                summary.get("product_scope_transporter_p0_operator_validation_candidate_ready")
                is True
                or transporter_scope.get("operator_validation_candidate_ready") is True
            ),
            "product_scope_transporter_p0_operator_validation_candidate_status": _text(
                summary.get("product_scope_transporter_p0_operator_validation_candidate_status")
            )
            or _text(transporter_scope.get("operator_validation_candidate_status")),
            "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier": _text(
                summary.get(
                    "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier"
                )
            )
            or _text(
                transporter_scope.get("operator_validation_candidate_ligand_external_identifier")
            ),
            "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol": _text(
                summary.get(
                    "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol"
                )
            )
            or _text(
                transporter_scope.get("operator_validation_candidate_reference_binding_kcal_mol")
            ),
            "product_scope_transporter_p0_operator_validation_candidate_blocker": _text(
                summary.get("product_scope_transporter_p0_operator_validation_candidate_blocker")
            )
            or _text(transporter_scope.get("operator_validation_candidate_blocker")),
            "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready": bool(
                summary.get(
                    "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready"
                )
                is True
                or transporter_scope.get("operator_validation_candidate_claim_safe_ready")
                is True
            ),
            "product_scope_transporter_p0_operator_validation_candidate_placeholder_count": _int(
                summary.get(
                    "product_scope_transporter_p0_operator_validation_candidate_placeholder_count"
                )
            ),
            "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count": _int(
                summary.get(
                    "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count"
                )
            ),
            "product_scope_transporter_p0_external_operator_artifacts": [
                aqp1_external_operator_fill_guide_path,
                aqp1_external_operator_worksheet_path,
                aqp1_external_operator_staging_apply_path,
            ],
            "product_scope_transporter_p0_external_operator_fill_guide_artifact": (
                aqp1_external_operator_fill_guide_path
            ),
            "product_scope_transporter_p0_external_operator_fill_guide_status": _text(
                aqp1_external_fill_guide.get("status")
            ),
            "product_scope_transporter_p0_external_operator_fill_guide_ready": bool(
                aqp1_external_fill_guide.get("status")
                == "aqp1_direct_binding_external_evidence_operator_fill_guide_ready"
            ),
            "product_scope_transporter_p0_external_operator_fill_guide_row_count": _int(
                aqp1_external_fill_guide.get("operator_fill_row_count")
            ),
            "product_scope_transporter_p0_external_operator_fill_guide_next_required_step": _text(
                aqp1_external_fill_guide.get("next_required_step")
            ),
            "product_scope_transporter_p0_external_operator_worksheet_artifact": (
                aqp1_external_operator_worksheet_path
            ),
            "product_scope_transporter_p0_external_operator_worksheet_status": _text(
                aqp1_external_worksheet.get("status")
            ),
            "product_scope_transporter_p0_external_operator_worksheet_ready": bool(
                aqp1_external_worksheet.get("status")
                == "aqp1_direct_binding_external_evidence_operator_worksheet_ready"
            ),
            "product_scope_transporter_p0_external_operator_worksheet_field_row_count": _int(
                aqp1_external_worksheet.get("worksheet_field_row_count")
            ),
            "product_scope_transporter_p0_external_operator_worksheet_pending_field_count": _int(
                aqp1_external_worksheet.get("operator_fill_pending_field_count")
            ),
            "product_scope_transporter_p0_external_operator_worksheet_validation_error_count": _int(
                aqp1_external_worksheet.get("validation_error_count")
            ),
            "product_scope_transporter_p0_external_operator_worksheet_supplement_csv": _text(
                aqp1_external_worksheet.get("supplement_csv")
            ),
            "product_scope_transporter_p0_external_operator_worksheet_next_required_step": _text(
                aqp1_external_worksheet.get("next_required_step")
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_artifact": (
                aqp1_external_operator_staging_apply_path
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_status": _text(
                aqp1_external_staging_apply.get("status")
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_mode": _text(
                aqp1_external_staging_apply.get("mode")
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_live_apply_allowed": bool(
                aqp1_external_staging_apply.get("live_apply_allowed") is True
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_validation_error_count": _int(
                aqp1_external_staging_apply.get("validation_error_count")
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_claim_safe_approved_count": _int(
                aqp1_external_staging_apply.get("staging_claim_safe_approved_count")
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_next_required_step": _text(
                aqp1_external_staging_apply.get("next_required_step")
            ),
        }
    )
    goal_scope_aliases = {
        key.replace("product_scope_", "product_goal_scope_", 1): value
        for key, value in out_summary.items()
        if key.startswith("product_scope_next_operator_completion_")
        or key.startswith("product_scope_transporter_p0_")
    }
    out_summary.update(goal_scope_aliases)
    return {"summary": out_summary, "rows": csv_rows, "operator_completion_packets": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Commercial Readiness Operator Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_ready: `{s['packet_ready']}`",
        f"- goal_complete: `{s['goal_complete']}`",
        f"- engine_refinement_claim_promotion_ready: `{s['engine_refinement_claim_promotion_ready']}`",
        f"- engine_refinement_claim_promotion_blocker_count: `{s['engine_refinement_claim_promotion_blocker_count']}`",
        f"- engine_refinement_claim_promotion_action_board_csv: `{s['engine_refinement_claim_promotion_action_board_csv']}`",
        f"- engine_refinement_claim_evidence_receipt_ready: `{s['engine_refinement_claim_evidence_receipt_ready']}`",
        f"- engine_refinement_claim_evidence_receipt_status: `{s['engine_refinement_claim_evidence_receipt_status']}`",
        f"- engine_refinement_claim_evidence_receipt_first_blocked_blocker_id: `{s['engine_refinement_claim_evidence_receipt_first_blocked_blocker_id']}`",
        f"- engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact: `{s['engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact']}`",
        f"- engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields: `{';'.join(s['engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields'])}`",
        f"- engine_refinement_claim_evidence_receipt_most_common_row_blocker: `{s['engine_refinement_claim_evidence_receipt_most_common_row_blocker']}`",
        f"- engine_refinement_claim_evidence_receipt_artifact: `{s['engine_refinement_claim_evidence_receipt_artifact']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_status: `{s['engine_refinement_claim_evidence_operator_field_worksheet_status']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count: `{s['engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count: `{s['engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count']}`",
        f"- engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id: `{s['engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id']}`",
        f"- product_scope_breadth_evidence_receipt_ready: `{s['product_scope_breadth_evidence_receipt_ready']}`",
        f"- product_scope_breadth_evidence_receipt_status: `{s['product_scope_breadth_evidence_receipt_status']}`",
        f"- product_scope_breadth_evidence_receipt_blocked_row_count: `{s['product_scope_breadth_evidence_receipt_blocked_row_count']}`",
        f"- product_scope_breadth_evidence_receipt_required_scope_blocker_count: `{s['product_scope_breadth_evidence_receipt_required_scope_blocker_count']}`",
        f"- product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id: `{s['product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id']}`",
        f"- product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact: `{s['product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact']}`",
        f"- product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields: `{';'.join(s['product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields'])}`",
        f"- product_scope_breadth_evidence_receipt_most_common_row_blocker: `{s['product_scope_breadth_evidence_receipt_most_common_row_blocker']}`",
        f"- product_scope_breadth_evidence_receipt_artifact: `{s['product_scope_breadth_evidence_receipt_artifact']}`",
        f"- product_scope_breadth_evidence_receipt_csv: `{s['product_scope_breadth_evidence_receipt_csv']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_status: `{s['product_scope_breadth_evidence_operator_field_worksheet_status']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_pending_field_count: `{s['product_scope_breadth_evidence_operator_field_worksheet_pending_field_count']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id: `{s['product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id']}`",
        f"- product_scope_breadth_evidence_operator_field_worksheet_top_item_id: `{s['product_scope_breadth_evidence_operator_field_worksheet_top_item_id']}`",
        f"- primary_full_commercial_release_blocker_id: `{s['primary_full_commercial_release_blocker_id']}`",
        f"- primary_full_commercial_release_blocker_receipt_csv: `{s['primary_full_commercial_release_blocker_receipt_csv']}`",
        f"- primary_full_commercial_release_blocker_approval_token_required: `{s['primary_full_commercial_release_blocker_approval_token_required']}`",
        f"- product_scope_next_operator_completion_item_id: `{s['product_scope_next_operator_completion_item_id']}`",
        f"- product_scope_next_operator_completion_required_evidence_type: `{s['product_scope_next_operator_completion_required_evidence_type']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_status: `{s['product_scope_transporter_p0_operator_validation_candidate_status']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier: `{s['product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol: `{s['product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol']}`",
        f"- product_scope_transporter_p0_operator_validation_candidate_blocker: `{s['product_scope_transporter_p0_operator_validation_candidate_blocker']}`",
        f"- product_scope_transporter_p0_return_bundle_next_artifact_id: `{s['product_scope_transporter_p0_return_bundle_next_artifact_id']}`",
        f"- product_scope_transporter_p0_return_bundle_next_artifact_path: `{s['product_scope_transporter_p0_return_bundle_next_artifact_path']}`",
        f"- product_scope_transporter_p0_return_bundle_required_artifacts: `{';'.join(s['product_scope_transporter_p0_return_bundle_required_artifacts'])}`",
        f"- goal_audit_sha256: `{s['goal_audit_sha256']}`",
        f"- commercial_readiness_matrix_sha256: `{s['commercial_readiness_matrix_sha256']}`",
        f"- source_fingerprint_ready: `{s['source_fingerprint_ready']}`",
        f"- open_gap_ids: `{';'.join(s['open_gap_ids'])}`",
        f"- action_count: `{s['action_count']}`",
        f"- blocked_action_count: `{s['blocked_action_count']}`",
        f"- first_parallelizable_action_id: `{s['first_parallelizable_action_id']}`",
        f"- first_parallelizable_action_next_slot_source_modality: `{s['first_parallelizable_action_next_slot_source_modality']}`",
        f"- first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed: `{s['first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed']}`",
        f"- first_parallelizable_action_next_slot_source_modality_decision: `{s['first_parallelizable_action_next_slot_source_modality_decision']}`",
        f"- first_action_id: `{s['first_action_id']}`",
        f"- first_artifact: `{s['first_artifact']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## First Operator Completion Packet",
        "",
        f"- packet_ready: `{s['first_operator_completion_packet_ready']}`",
        f"- artifact_id: `{s['first_operator_completion_artifact_id']}`",
        f"- artifact_path: `{s['first_operator_completion_artifact_path']}`",
        f"- validation_command: `{s['first_operator_completion_validation_command']}`",
        f"- required_fields_or_columns: `{';'.join(s['first_operator_completion_required_fields_or_columns'])}`",
        f"- required_exact_evidence_fields: `{';'.join(s['first_operator_completion_required_exact_evidence_fields'])}`",
        f"- packet_keys: `{';'.join(s['first_operator_completion_packet_keys'])}`",
        f"- next_action: `{s['first_operator_completion_next_action']}`",
        f"- worker_runtime_receipt_contract_ready: `{s['first_operator_completion_worker_runtime_receipt_contract_ready']}`",
        f"- worker_runtime_receipt_required_fields_or_columns: `{';'.join(s['first_operator_completion_worker_runtime_receipt_required_fields_or_columns'])}`",
        f"- worker_runtime_receipt_completion_rule: `{s['first_operator_completion_worker_runtime_receipt_completion_rule']}`",
        f"- worker_runtime_receipt_post_environment_next_stage_id: `{s['first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id']}`",
        f"- worker_runtime_receipt_post_environment_next_artifact: `{s['first_operator_completion_worker_runtime_receipt_post_environment_next_artifact']}`",
        f"- worker_runtime_receipt_post_environment_validation_command: `{s['first_operator_completion_worker_runtime_receipt_post_environment_validation_command']}`",
        f"- diagnostic_command_count: `{s['first_operator_completion_diagnostic_command_count']}`",
        f"- diagnostic_completion_rule: `{s['first_operator_completion_diagnostic_completion_rule'] or '-'}`",
        "",
        "## Production AI Registry Promotion Packet",
        "",
        f"- action_id: `{s['production_ai_registry_promotion_action_id']}`",
        f"- priority_status: `{s['production_ai_registry_promotion_priority_status']}`",
        f"- priority_top_gate_id: `{s['production_ai_registry_promotion_priority_top_gate_id']}`",
        f"- priority_operator_receipt_csv: `{s['production_ai_registry_promotion_priority_operator_receipt_csv']}`",
        f"- priority_approval_token_required: `{s['production_ai_registry_promotion_priority_approval_token_required']}`",
        f"- priority_observed_registry_default_residual_mode: `{s['production_ai_registry_promotion_priority_observed_registry_default_residual_mode']}`",
        f"- priority_observed_registry_production_promotion_allowed: `{s['production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed']}`",
        f"- priority_observed_registry_customer_facing_mutation_flags_ready: `{s['production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready']}`",
        f"- artifact: `{s['production_ai_registry_promotion_action_artifact']}`",
        f"- blocked_by_action_id: `{s['production_ai_registry_promotion_action_blocked_by_action_id']}`",
        f"- packet_ready: `{s['production_ai_registry_promotion_operator_completion_packet_ready']}`",
        f"- artifact_id: `{s['production_ai_registry_promotion_operator_completion_artifact_id']}`",
        f"- artifact_path: `{s['production_ai_registry_promotion_operator_completion_artifact_path']}`",
        f"- required_fields_or_columns: `{';'.join(s['production_ai_registry_promotion_operator_completion_required_fields_or_columns'])}`",
        f"- diagnostic_command_count: `{s['production_ai_registry_promotion_operator_completion_diagnostic_command_count']}`",
        f"- completion_rule: `{s['production_ai_registry_promotion_operator_completion_completion_rule']}`",
        f"- failed_check_ids: `{';'.join(s['production_ai_registry_promotion_operator_completion_failed_check_ids'])}`",
        f"- receipt_status: `{s['production_ai_registry_promotion_operator_receipt_status']}`",
        f"- receipt_ready: `{s['production_ai_registry_promotion_operator_receipt_ready']}`",
        f"- receipt_artifact: `{s['production_ai_registry_promotion_operator_receipt_artifact']}`",
        f"- receipt_csv: `{s['production_ai_registry_promotion_operator_receipt_csv']}`",
        f"- receipt_approval_token_required: `{s['production_ai_registry_promotion_operator_receipt_approval_token_required']}`",
        f"- receipt_first_blocked_row_blocker: `{s['production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker']}`",
        f"- receipt_observed_registry_default_residual_mode: `{s['production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode']}`",
        f"- receipt_observed_registry_trained_model_checkpoint_count: `{s['production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count']}`",
        f"- field_worksheet_status: `{s['production_ai_registry_promotion_operator_field_worksheet_status']}`",
        f"- field_worksheet_pending_field_count: `{s['production_ai_registry_promotion_operator_field_worksheet_pending_field_count']}`",
        f"- field_worksheet_diagnostic_pending_field_count: `{s['production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count']}`",
        f"- field_worksheet_top_gate_id: `{s['production_ai_registry_promotion_operator_field_worksheet_top_gate_id']}`",
        "",
        "## Production AI Return Completion Packet",
        "",
        f"- action_id: `{s['production_ai_return_action_id']}`",
        f"- artifact: `{s['production_ai_return_action_artifact']}`",
        f"- blocked_by_action_id: `{s['production_ai_return_action_blocked_by_action_id']}`",
        f"- packet_ready: `{s['production_ai_return_operator_completion_packet_ready']}`",
        f"- artifact_id: `{s['production_ai_return_operator_completion_artifact_id']}`",
        f"- artifact_path: `{s['production_ai_return_operator_completion_artifact_path']}`",
        f"- expected_queue_rows: `{s['production_ai_return_operator_completion_expected_queue_rows']}`",
        f"- required_fields_or_columns: `{';'.join(s['production_ai_return_operator_completion_required_fields_or_columns'])}`",
        f"- completion_rule: `{s['production_ai_return_operator_completion_completion_rule']}`",
        f"- backend_provenance_completion_rule: `{s['production_ai_return_operator_completion_backend_provenance_completion_rule']}`",
        f"- return_bundle_required_artifacts: `{';'.join(s['production_ai_return_bundle_required_artifacts'])}`",
        f"- return_bundle_next_artifact_id: `{s['production_ai_return_bundle_next_artifact_id']}`",
        f"- return_bundle_failed_check_ids: `{';'.join(s['production_ai_return_bundle_next_artifact_failed_check_ids'])}`",
        f"- post_return_validation_command: `{s['production_ai_return_bundle_post_return_validation_command']}`",
        f"- guardrail: `{s['production_ai_return_bundle_guardrail']}`",
        "",
        "## Delta Force Closure Acceptance",
        "",
        f"- packet_ready: `{s['delta_force_closure_acceptance_packet_ready']}`",
        f"- delta_force_closure_ready: `{s['delta_force_closure_ready']}`",
        f"- first_blocked_output_field: `{s['delta_force_closure_first_blocked_output_field']}`",
        f"- failed_stage_ids: `{';'.join(s['delta_force_closure_failed_stage_ids'])}`",
        f"- next_stage_id: `{s['delta_force_closure_next_stage_id']}`",
        f"- next_stage_artifact: `{s['delta_force_closure_next_stage_artifact']}`",
        f"- next_stage_validation_command: `{s['delta_force_closure_next_stage_validation_command']}`",
        "",
        "## Scope Closure Acceptance",
        "",
        f"- packet_ready: `{s['scope_closure_acceptance_packet_ready']}`",
        f"- scope_closure_ready: `{s['scope_closure_ready']}`",
        f"- blocked_stage_ids: `{';'.join(s['scope_closure_blocked_stage_ids'])}`",
        f"- next_stage_id: `{s['scope_closure_next_stage_id']}`",
        f"- first_blocked_evidence_row_id: `{s['scope_closure_first_blocked_evidence_row_id']}`",
        f"- first_blocked_target_id: `{s['scope_closure_first_blocked_target_id']}`",
        f"- first_blocked_required_missing_fields: `{s['scope_closure_first_blocked_required_missing_fields']}`",
        "",
        "## Actions",
        "",
        "| action | status | artifact | inputs | execution | validation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['status']}` | `{row['artifact']}` | "
            f"`{row['required_operator_inputs']}` | `{row['execution_command']}` | "
            f"`{row['validation_command']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a commercial-readiness operator handoff packet.")
    parser.add_argument("--goal-audit-json", default=DEFAULT_GOAL_AUDIT_JSON)
    parser.add_argument("--delta-force-closure-packet-json", default=DEFAULT_DELTA_FORCE_CLOSURE_PACKET_JSON)
    parser.add_argument("--scope-closure-packet-json", default=DEFAULT_SCOPE_CLOSURE_PACKET_JSON)
    parser.add_argument("--aqp1-direct-binding-procurement-json", default=DEFAULT_AQP1_DIRECT_BINDING_PROCUREMENT_JSON)
    parser.add_argument(
        "--aqp1-external-operator-fill-guide-json",
        default=DEFAULT_AQP1_EXTERNAL_OPERATOR_FILL_GUIDE_JSON,
    )
    parser.add_argument(
        "--aqp1-external-operator-worksheet-json",
        default=DEFAULT_AQP1_EXTERNAL_OPERATOR_WORKSHEET_JSON,
    )
    parser.add_argument(
        "--aqp1-external-operator-staging-apply-json",
        default=DEFAULT_AQP1_EXTERNAL_OPERATOR_STAGING_APPLY_JSON,
    )
    parser.add_argument(
        "--production-ai-registry-promotion-operator-receipt-json",
        default=DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_OPERATOR_RECEIPT_JSON,
    )
    parser.add_argument(
        "--production-ai-registry-promotion-priority-json",
        default=DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_JSON,
    )
    parser.add_argument(
        "--production-ai-registry-promotion-field-worksheet-json",
        default=DEFAULT_PRODUCTION_AI_REGISTRY_PROMOTION_FIELD_WORKSHEET_JSON,
    )
    parser.add_argument(
        "--product-scope-breadth-evidence-field-worksheet-json",
        default=DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_FIELD_WORKSHEET_JSON,
    )
    parser.add_argument(
        "--engine-refinement-claim-evidence-field-worksheet-json",
        default=DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_FIELD_WORKSHEET_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_commercial_readiness_operator_packet(
        goal_audit_packet=_read_json_if_present(args.goal_audit_json),
        delta_force_closure_packet=_read_json_if_present(args.delta_force_closure_packet_json),
        scope_closure_packet=_read_json_if_present(args.scope_closure_packet_json),
        aqp1_direct_binding_procurement_packet=_read_json_if_present(
            args.aqp1_direct_binding_procurement_json
        ),
        aqp1_external_operator_fill_guide_packet=_read_json_if_present(
            args.aqp1_external_operator_fill_guide_json
        ),
        aqp1_external_operator_worksheet_packet=_read_json_if_present(
            args.aqp1_external_operator_worksheet_json
        ),
        aqp1_external_operator_staging_apply_packet=_read_json_if_present(
            args.aqp1_external_operator_staging_apply_json
        ),
        production_ai_registry_promotion_operator_receipt_packet=_read_json_if_present(
            args.production_ai_registry_promotion_operator_receipt_json
        ),
        production_ai_registry_promotion_priority_packet=_read_json_if_present(
            args.production_ai_registry_promotion_priority_json
        ),
        production_ai_registry_promotion_field_worksheet_packet=_read_json_if_present(
            args.production_ai_registry_promotion_field_worksheet_json
        ),
        product_scope_breadth_evidence_field_worksheet_packet=_read_json_if_present(
            args.product_scope_breadth_evidence_field_worksheet_json
        ),
        engine_refinement_claim_evidence_field_worksheet_packet=_read_json_if_present(
            args.engine_refinement_claim_evidence_field_worksheet_json
        ),
        goal_audit_path=args.goal_audit_json,
        delta_force_closure_packet_path=args.delta_force_closure_packet_json,
        scope_closure_packet_path=args.scope_closure_packet_json,
        aqp1_direct_binding_procurement_path=args.aqp1_direct_binding_procurement_json,
        aqp1_external_operator_fill_guide_path=args.aqp1_external_operator_fill_guide_json,
        aqp1_external_operator_worksheet_path=args.aqp1_external_operator_worksheet_json,
        aqp1_external_operator_staging_apply_path=args.aqp1_external_operator_staging_apply_json,
        production_ai_registry_promotion_operator_receipt_path=(
            args.production_ai_registry_promotion_operator_receipt_json
        ),
        production_ai_registry_promotion_priority_path=(
            args.production_ai_registry_promotion_priority_json
        ),
        production_ai_registry_promotion_field_worksheet_path=(
            args.production_ai_registry_promotion_field_worksheet_json
        ),
        product_scope_breadth_evidence_field_worksheet_path=(
            args.product_scope_breadth_evidence_field_worksheet_json
        ),
        engine_refinement_claim_evidence_field_worksheet_path=(
            args.engine_refinement_claim_evidence_field_worksheet_json
        ),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
