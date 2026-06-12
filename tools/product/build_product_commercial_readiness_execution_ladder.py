#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATOR_PACKET_JSON = "runs/product_commercial_readiness_operator_packet_current.json"
DEFAULT_FRESHNESS_JSON = "runs/product_commercial_readiness_operator_packet_freshness_current.json"
DEFAULT_OUT_JSON = "runs/product_commercial_readiness_execution_ladder_current.json"
DEFAULT_OUT_CSV = "runs/product_commercial_readiness_execution_ladder_current.csv"
DEFAULT_OUT_MD = "runs/product_commercial_readiness_execution_ladder_current.md"

CLAIM_BOUNDARY = (
    "Product commercial-readiness execution ladder only; orders existing operator handoff actions into input, "
    "execution, and validation steps. It does not run commands, run docking, run GPU jobs, fill evidence, promote "
    "checkpoints, widen product claims, upload, submit, email, delete, or mutate external state."
)


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [dict(row) for row in (rows or []) if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _input_artifact_for_action(action_id: str, artifact: str) -> str:
    if action_id == "production_ai_return_summary":
        return "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    return artifact


def _post_validation_command(action_id: str, validation_command: str) -> str:
    if action_id == "production_ai_return_summary":
        return (
            validation_command
            + " && python3 tools/build_residual_force_derivation_validation.py"
            + " && python3 tools/build_product_goal_completion_audit.py"
        )
    if action_id in {"transporter_next_slot_exact_evidence", "pxr_next_exact_review", "broad_platform_claim_floor"}:
        return validation_command + " && python3 tools/build_product_goal_completion_audit.py"
    return validation_command


def build_product_commercial_readiness_execution_ladder(
    *,
    operator_packet: dict[str, Any],
    freshness_packet: dict[str, Any],
    operator_packet_path: str = DEFAULT_OPERATOR_PACKET_JSON,
    freshness_path: str = DEFAULT_FRESHNESS_JSON,
) -> dict[str, Any]:
    operator_summary = _summary(operator_packet)
    freshness_summary = _summary(freshness_packet)
    actions = _rows(operator_packet)
    freshness_ready = _bool(freshness_summary.get("freshness_ready"))
    packet_ready = _bool(operator_summary.get("packet_ready"))
    ladder_ready = packet_ready and freshness_ready and bool(actions)
    ladder_rows: list[dict[str, Any]] = []
    for index, row in enumerate(actions, start=1):
        action_id = _text(row.get("action_id"))
        artifact = _text(row.get("artifact"))
        validation_command = _text(row.get("validation_command"))
        required_inputs = _text(row.get("required_operator_inputs"))
        ladder_rows.append(
            {
                "execution_order": index,
                "action_id": action_id,
                "gap_id": _text(row.get("gap_id")),
                "status": _text(row.get("status")),
                "release_blocker": bool(row.get("release_blocker") is True),
                "precondition": "commercial_readiness_operator_packet_freshness_ready",
                "precondition_satisfied": freshness_ready,
                "operator_input_artifact": _input_artifact_for_action(action_id, artifact),
                "required_operator_inputs": required_inputs,
                "required_exact_evidence_fields": _text(row.get("required_exact_evidence_fields")),
                "required_claim_guardrails": _text(row.get("required_claim_guardrails")),
                "expected_evidence_type": _text(row.get("expected_evidence_type")),
                "required_missing_fields": _text(row.get("required_missing_fields")),
                "required_evidence": _text(row.get("required_evidence")),
                "operator_review_artifact": _text(row.get("operator_review_artifact")),
                "post_intake_synchronization_targets": _text(
                    row.get("post_intake_synchronization_targets")
                ),
                "acceptance_gate_commands": _text(row.get("acceptance_gate_commands")),
                "source_signal": _text(row.get("source_signal")),
                "next_slot_source_modality_guard_ready": bool(
                    row.get("next_slot_source_modality_guard_ready") is True
                ),
                "next_slot_source_modality": _text(row.get("next_slot_source_modality")),
                "next_slot_source_modality_claim_safe": bool(
                    row.get("next_slot_source_modality_claim_safe") is True
                ),
                "next_slot_source_modality_direct_binding_claim_allowed": bool(
                    row.get("next_slot_source_modality_direct_binding_claim_allowed") is True
                ),
                "next_slot_source_modality_decision": _text(
                    row.get("next_slot_source_modality_decision")
                ),
                "next_slot_source_modality_guardrails": _text(
                    row.get("next_slot_source_modality_guardrails")
                ),
                "next_slot_source_modality_observed_signal": _text(
                    row.get("next_slot_source_modality_observed_signal")
                ),
                "next_slot_source_modality_required_upgrade": _text(
                    row.get("next_slot_source_modality_required_upgrade")
                ),
                "next_slot_source_modality_triage_artifact": _text(
                    row.get("next_slot_source_modality_triage_artifact")
                ),
                "next_slot_source_modality_triage_decision": _text(
                    row.get("next_slot_source_modality_triage_decision")
                ),
                "next_slot_source_modality_direct_experimental_binding_row_count": int(
                    row.get("next_slot_source_modality_direct_experimental_binding_row_count") or 0
                ),
                "next_slot_source_modality_claim_safe_binding_kcal_ready_count": int(
                    row.get("next_slot_source_modality_claim_safe_binding_kcal_ready_count") or 0
                ),
                "next_slot_source_modality_computational_binding_energy_row_count": int(
                    row.get("next_slot_source_modality_computational_binding_energy_row_count") or 0
                ),
                "next_slot_source_modality_best_computational_binding_energy_kcal_mol": _text(
                    row.get("next_slot_source_modality_best_computational_binding_energy_kcal_mol")
                ),
                "operator_validation_candidate_ready": bool(
                    row.get("operator_validation_candidate_ready") is True
                ),
                "operator_validation_candidate_status": _text(
                    row.get("operator_validation_candidate_status")
                ),
                "operator_validation_candidate_ligand_external_identifier": _text(
                    row.get("operator_validation_candidate_ligand_external_identifier")
                ),
                "operator_validation_candidate_reference_binding_kcal_mol": _text(
                    row.get("operator_validation_candidate_reference_binding_kcal_mol")
                ),
                "operator_validation_candidate_blocker": _text(
                    row.get("operator_validation_candidate_blocker")
                ),
                "operator_validation_candidate_claim_safe_ready": bool(
                    row.get("operator_validation_candidate_claim_safe_ready") is True
                ),
                "direct_binding_procurement_packet_ready": bool(
                    row.get("direct_binding_procurement_packet_ready") is True
                ),
                "direct_binding_procurement_packet_status": _text(
                    row.get("direct_binding_procurement_packet_status")
                ),
                "direct_binding_procurement_packet_artifact": _text(
                    row.get("direct_binding_procurement_packet_artifact")
                ),
                "direct_binding_procurement_direct_binding_gap_open": bool(
                    row.get("direct_binding_procurement_direct_binding_gap_open") is True
                ),
                "direct_binding_procurement_external_primary_evidence_required": bool(
                    row.get("direct_binding_procurement_external_primary_evidence_required") is True
                ),
                "direct_binding_procurement_first_required_external_action_id": _text(
                    row.get("direct_binding_procurement_first_required_external_action_id")
                ),
                "direct_binding_procurement_current_operator_candidate_blocker": _text(
                    row.get("direct_binding_procurement_current_operator_candidate_blocker")
                ),
                "direct_binding_procurement_minimum_acceptance_rule": _text(
                    row.get("direct_binding_procurement_minimum_acceptance_rule")
                ),
                "direct_binding_procurement_accepted_direct_binding_methods": _text(
                    row.get("direct_binding_procurement_accepted_direct_binding_methods")
                ),
                "direct_binding_procurement_acceptance_fields": _text(
                    row.get("direct_binding_procurement_acceptance_fields")
                ),
                "execution_command": _text(row.get("execution_command")),
                "validation_command": validation_command,
                "post_validation_rebuild_command": _post_validation_command(action_id, validation_command),
                "unlock_claim": _text(row.get("unlock_claim")),
                "next_action": _text(row.get("next_action")),
                "workstream_lane_id": _text(row.get("workstream_lane_id")),
                "blocked_stage_dependency_count": int(
                    row.get("blocked_stage_dependency_count") or 0
                ),
                "blocked_stage_evidence_count": int(
                    row.get("blocked_stage_evidence_count") or 0
                ),
                "blocked_stage_dependency_matrix_count": int(
                    row.get("blocked_stage_dependency_matrix_count") or 0
                ),
                "blocked_stage_dependency_stage_ids": _text(
                    row.get("blocked_stage_dependency_stage_ids")
                ),
                "blocked_stage_dependency_unlock_claim_scopes": _text(
                    row.get("blocked_stage_dependency_unlock_claim_scopes")
                ),
                "blocked_stage_dependency_first_blocked_evidence_row_ids": _text(
                    row.get("blocked_stage_dependency_first_blocked_evidence_row_ids")
                ),
                "operator_completion_worker_runtime_receipt_contract_ready": bool(
                    row.get("operator_completion_worker_runtime_receipt_contract_ready") is True
                ),
                "operator_completion_worker_runtime_receipt_required_fields_or_columns": _text(
                    row.get("operator_completion_worker_runtime_receipt_required_fields_or_columns")
                ),
                "operator_completion_worker_runtime_receipt_required_field_count": int(
                    row.get("operator_completion_worker_runtime_receipt_required_field_count") or 0
                ),
                "operator_completion_worker_runtime_receipt_completion_rule": _text(
                    row.get("operator_completion_worker_runtime_receipt_completion_rule")
                ),
                "operator_completion_worker_runtime_receipt_post_environment_next_stage_id": _text(
                    row.get("operator_completion_worker_runtime_receipt_post_environment_next_stage_id")
                ),
                "operator_completion_worker_runtime_receipt_post_environment_next_artifact": _text(
                    row.get("operator_completion_worker_runtime_receipt_post_environment_next_artifact")
                ),
                "operator_completion_worker_runtime_receipt_post_environment_validation_command": _text(
                    row.get("operator_completion_worker_runtime_receipt_post_environment_validation_command")
                ),
                "operator_completion_worker_runtime_receipt_full_regeneration_command": _text(
                    row.get("operator_completion_worker_runtime_receipt_full_regeneration_command")
                ),
                "operator_completion_worker_runtime_receipt_guardrails": _text(
                    row.get("operator_completion_worker_runtime_receipt_guardrails")
                ),
                "operator_completion_diagnostic_commands": _text(
                    row.get("operator_completion_diagnostic_commands")
                ),
                "operator_completion_diagnostic_command_count": int(
                    row.get("operator_completion_diagnostic_command_count") or 0
                ),
                "operator_completion_diagnostic_required_fields": _text(
                    row.get("operator_completion_diagnostic_required_fields")
                ),
                "operator_completion_diagnostic_required_field_count": int(
                    row.get("operator_completion_diagnostic_required_field_count") or 0
                ),
                "operator_completion_diagnostic_completion_rule": _text(
                    row.get("operator_completion_diagnostic_completion_rule")
                ),
                "operator_completion_diagnostic_return_artifacts": _text(
                    row.get("operator_completion_diagnostic_return_artifacts")
                ),
                "operator_completion_torch_visibility_probe_command": _text(
                    row.get("operator_completion_torch_visibility_probe_command")
                ),
                "parallelizable_with_primary_blocker": bool(
                    row.get("parallelizable_with_primary_blocker") is True
                ),
                "parallel_lane_precondition": _text(row.get("parallel_lane_precondition")),
                "parallel_lane_priority": int(row.get("parallel_lane_priority") or 0),
                "parallel_primary_blocker_action_id": _text(
                    row.get("parallel_primary_blocker_action_id")
                ),
                "blocked_by_action_id": _text(row.get("blocked_by_action_id")),
                "return_bundle_required_artifact_count": int(
                    row.get("return_bundle_required_artifact_count") or 0
                ),
                "return_bundle_required_artifacts": _text(row.get("return_bundle_required_artifacts")),
                "return_bundle_next_artifact_id": _text(row.get("return_bundle_next_artifact_id")),
                "return_bundle_next_artifact_path": _text(row.get("return_bundle_next_artifact_path")),
                "return_bundle_next_artifact_failed_check_ids": _text(
                    row.get("return_bundle_next_artifact_failed_check_ids")
                ),
                "return_bundle_manifest_required_columns": _text(
                    row.get("return_bundle_manifest_required_columns")
                ),
                "return_bundle_post_return_validation_command": _text(
                    row.get("return_bundle_post_return_validation_command")
                ),
                "return_bundle_guardrail": _text(row.get("return_bundle_guardrail")),
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    blocked_rows = [row for row in ladder_rows if row["status"] != "ready"]
    parallel_rows = [
        row
        for row in ladder_rows
        if row.get("parallelizable_with_primary_blocker") is True and row["status"] != "ready"
    ]
    parallel_rows = sorted(
        parallel_rows,
        key=lambda row: (int(row.get("parallel_lane_priority") or 0), _text(row.get("action_id"))),
    )
    first = blocked_rows[0] if blocked_rows else (ladder_rows[0] if ladder_rows else {})
    first_parallel = parallel_rows[0] if parallel_rows else {}
    summary = {
        "packet_type": "product_commercial_readiness_execution_ladder",
        "status": (
            "product_commercial_readiness_execution_ladder_ready"
            if ladder_ready
            else "blocked_product_commercial_readiness_execution_ladder"
        ),
        "ladder_ready": ladder_ready,
        "operator_packet_artifact": operator_packet_path,
        "freshness_artifact": freshness_path,
        "operator_packet_ready": packet_ready,
        "freshness_ready": freshness_ready,
        "goal_complete": bool(operator_summary.get("goal_complete") is True),
        "action_count": len(ladder_rows),
        "blocked_action_count": len(blocked_rows),
        "parallelizable_action_count": len(parallel_rows),
        "parallelizable_action_ids": [_text(row.get("action_id")) for row in parallel_rows],
        "first_parallelizable_action_id": _text(first_parallel.get("action_id")),
        "first_parallelizable_action_order": int(first_parallel.get("execution_order") or 0),
        "first_parallelizable_action_artifact": _text(first_parallel.get("operator_input_artifact")),
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
            first_parallel.get("next_slot_source_modality_direct_binding_claim_allowed")
            is True
        ),
        "first_parallelizable_action_next_slot_source_modality_decision": _text(
            first_parallel.get("next_slot_source_modality_decision")
        ),
        "first_parallelizable_action_next_slot_source_modality_guardrails": [
            item
            for item in _text(first_parallel.get("next_slot_source_modality_guardrails")).split(";")
            if item
        ],
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
        "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count": int(
            first_parallel.get("next_slot_source_modality_direct_experimental_binding_row_count") or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count": int(
            first_parallel.get("next_slot_source_modality_claim_safe_binding_kcal_ready_count") or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count": int(
            first_parallel.get("next_slot_source_modality_computational_binding_energy_row_count") or 0
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
        "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods": _text(
            first_parallel.get("direct_binding_procurement_accepted_direct_binding_methods")
        ),
        "first_parallelizable_action_direct_binding_procurement_acceptance_fields": _text(
            first_parallel.get("direct_binding_procurement_acceptance_fields")
        ),
        "first_parallelizable_action_lane_id": _text(first_parallel.get("workstream_lane_id")),
        "first_parallelizable_action_precondition": _text(
            first_parallel.get("parallel_lane_precondition")
        ),
        "first_execution_order": int(first.get("execution_order") or 0),
        "first_action_id": _text(first.get("action_id")),
        "first_operator_input_artifact": _text(first.get("operator_input_artifact")),
        "first_execution_command": _text(first.get("execution_command")),
        "first_validation_command": _text(first.get("validation_command")),
        "first_operator_completion_worker_runtime_receipt_contract_ready": bool(
            operator_summary.get("first_operator_completion_worker_runtime_receipt_contract_ready")
            is True
        ),
        "first_operator_completion_worker_runtime_receipt_contract": dict(
            operator_summary.get("first_operator_completion_worker_runtime_receipt_contract")
            or {}
        ),
        "first_operator_completion_worker_runtime_receipt_required_fields_or_columns": [
            str(item)
            for item in (
                operator_summary.get(
                    "first_operator_completion_worker_runtime_receipt_required_fields_or_columns"
                )
                or []
            )
        ],
        "first_operator_completion_worker_runtime_receipt_required_field_count": int(
            operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_required_field_count"
            )
            or 0
        ),
        "first_operator_completion_worker_runtime_receipt_completion_rule": _text(
            operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_completion_rule"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id": _text(
            operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact": _text(
            operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_validation_command": _text(
            operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_post_environment_validation_command"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_full_regeneration_command": _text(
            operator_summary.get(
                "first_operator_completion_worker_runtime_receipt_full_regeneration_command"
            )
        ),
        "first_operator_completion_worker_runtime_receipt_guardrails": [
            str(item)
            for item in (
                operator_summary.get(
                    "first_operator_completion_worker_runtime_receipt_guardrails"
                )
                or []
            )
        ],
        "first_operator_completion_diagnostic_commands": [
            str(item)
            for item in (
                operator_summary.get("first_operator_completion_diagnostic_commands") or []
            )
        ],
        "first_operator_completion_diagnostic_command_count": int(
            operator_summary.get("first_operator_completion_diagnostic_command_count") or 0
        ),
        "first_operator_completion_diagnostic_required_fields": [
            str(item)
            for item in (
                operator_summary.get("first_operator_completion_diagnostic_required_fields") or []
            )
        ],
        "first_operator_completion_diagnostic_required_field_count": int(
            operator_summary.get("first_operator_completion_diagnostic_required_field_count") or 0
        ),
        "first_operator_completion_diagnostic_completion_rule": _text(
            operator_summary.get("first_operator_completion_diagnostic_completion_rule")
        ),
        "first_operator_completion_diagnostic_return_artifacts": [
            str(item)
            for item in (
                operator_summary.get("first_operator_completion_diagnostic_return_artifacts") or []
            )
        ],
        "first_operator_completion_torch_visibility_probe_command": _text(
            operator_summary.get("first_operator_completion_torch_visibility_probe_command")
        ),
        "production_ai_return_action_id": _text(
            operator_summary.get("production_ai_return_action_id")
        ),
        "production_ai_return_action_artifact": _text(
            operator_summary.get("production_ai_return_action_artifact")
        ),
        "production_ai_return_action_next_action": _text(
            operator_summary.get("production_ai_return_action_next_action")
        ),
        "production_ai_return_action_execution_command": _text(
            operator_summary.get("production_ai_return_action_execution_command")
        ),
        "production_ai_return_action_validation_command": _text(
            operator_summary.get("production_ai_return_action_validation_command")
        ),
        "production_ai_return_action_blocked_by_action_id": _text(
            operator_summary.get("production_ai_return_action_blocked_by_action_id")
        ),
        "production_ai_return_action_required_operator_inputs": _text(
            operator_summary.get("production_ai_return_action_required_operator_inputs")
        ),
        "production_ai_return_action_required_evidence": _text(
            operator_summary.get("production_ai_return_action_required_evidence")
        ),
        "production_ai_return_operator_completion_packet_ready": bool(
            operator_summary.get("production_ai_return_operator_completion_packet_ready") is True
        ),
        "production_ai_return_operator_completion_artifact_id": _text(
            operator_summary.get("production_ai_return_operator_completion_artifact_id")
        ),
        "production_ai_return_operator_completion_artifact_path": _text(
            operator_summary.get("production_ai_return_operator_completion_artifact_path")
        ),
        "production_ai_return_operator_completion_required_fields_or_columns": [
            str(item)
            for item in (
                operator_summary.get(
                    "production_ai_return_operator_completion_required_fields_or_columns"
                )
                or []
            )
        ],
        "production_ai_return_operator_completion_expected_queue_rows": int(
            operator_summary.get("production_ai_return_operator_completion_expected_queue_rows") or 0
        ),
        "production_ai_return_operator_completion_completion_rule": _text(
            operator_summary.get("production_ai_return_operator_completion_completion_rule")
        ),
        "production_ai_return_operator_completion_backend_provenance_completion_rule": _text(
            operator_summary.get(
                "production_ai_return_operator_completion_backend_provenance_completion_rule"
            )
        ),
        "production_ai_return_bundle_required_artifact_count": int(
            operator_summary.get("production_ai_return_bundle_required_artifact_count") or 0
        ),
        "production_ai_return_bundle_required_artifacts": [
            str(item)
            for item in (operator_summary.get("production_ai_return_bundle_required_artifacts") or [])
        ],
        "production_ai_return_bundle_next_artifact_id": _text(
            operator_summary.get("production_ai_return_bundle_next_artifact_id")
        ),
        "production_ai_return_bundle_next_artifact_path": _text(
            operator_summary.get("production_ai_return_bundle_next_artifact_path")
        ),
        "production_ai_return_bundle_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                operator_summary.get(
                    "production_ai_return_bundle_next_artifact_failed_check_ids"
                )
                or []
            )
        ],
        "production_ai_return_bundle_manifest_required_columns": [
            str(item)
            for item in (
                operator_summary.get("production_ai_return_bundle_manifest_required_columns")
                or []
            )
        ],
        "production_ai_return_bundle_post_return_validation_command": _text(
            operator_summary.get("production_ai_return_bundle_post_return_validation_command")
        ),
        "production_ai_return_bundle_guardrail": _text(
            operator_summary.get("production_ai_return_bundle_guardrail")
        ),
        "production_ai_registry_promotion_action_id": _text(
            operator_summary.get("production_ai_registry_promotion_action_id")
        ),
        "production_ai_registry_promotion_action_artifact": _text(
            operator_summary.get("production_ai_registry_promotion_action_artifact")
        ),
        "production_ai_registry_promotion_action_next_action": _text(
            operator_summary.get("production_ai_registry_promotion_action_next_action")
        ),
        "production_ai_registry_promotion_action_validation_command": _text(
            operator_summary.get("production_ai_registry_promotion_action_validation_command")
        ),
        "production_ai_registry_promotion_action_blocked_by_action_id": _text(
            operator_summary.get("production_ai_registry_promotion_action_blocked_by_action_id")
        ),
        "production_ai_registry_promotion_action_required_operator_inputs": _text(
            operator_summary.get(
                "production_ai_registry_promotion_action_required_operator_inputs"
            )
        ),
        "production_ai_registry_promotion_action_required_evidence": _text(
            operator_summary.get("production_ai_registry_promotion_action_required_evidence")
        ),
        "production_ai_registry_promotion_operator_completion_packet_ready": bool(
            operator_summary.get(
                "production_ai_registry_promotion_operator_completion_packet_ready"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_completion_packet_keys": [
            str(item)
            for item in (
                operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_packet_keys"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_artifact_id": _text(
            operator_summary.get(
                "production_ai_registry_promotion_operator_completion_artifact_id"
            )
        ),
        "production_ai_registry_promotion_operator_completion_artifact_path": _text(
            operator_summary.get(
                "production_ai_registry_promotion_operator_completion_artifact_path"
            )
        ),
        "production_ai_registry_promotion_operator_completion_required_fields_or_columns": [
            str(item)
            for item in (
                operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_required_fields_or_columns"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_diagnostic_commands": [
            str(item)
            for item in (
                operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_diagnostic_commands"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_diagnostic_command_count": int(
            operator_summary.get(
                "production_ai_registry_promotion_operator_completion_diagnostic_command_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_completion_completion_rule": _text(
            operator_summary.get(
                "production_ai_registry_promotion_operator_completion_completion_rule"
            )
        ),
        "production_ai_registry_promotion_operator_completion_failed_check_ids": [
            str(item)
            for item in (
                operator_summary.get(
                    "production_ai_registry_promotion_operator_completion_failed_check_ids"
                )
                or []
            )
        ],
        "production_ai_registry_promotion_operator_completion_packet": dict(
            operator_summary.get("production_ai_registry_promotion_operator_completion_packet")
            or {}
        ),
        "all_preconditions_satisfied": all(row["precondition_satisfied"] for row in ladder_rows) if ladder_rows else False,
        "next_required_step": (
            _text(first.get("next_action"))
            if ladder_ready and first
            else "Rebuild the commercial-readiness operator packet and freshness artifacts before using this ladder."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
    }
    return {"summary": summary, "rows": ladder_rows, "blockers": blocked_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Commercial Readiness Execution Ladder",
        "",
        f"- status: `{s['status']}`",
        f"- ladder_ready: `{s['ladder_ready']}`",
        f"- operator_packet_ready: `{s['operator_packet_ready']}`",
        f"- freshness_ready: `{s['freshness_ready']}`",
        f"- action_count: `{s['action_count']}`",
        f"- blocked_action_count: `{s['blocked_action_count']}`",
        f"- parallelizable_action_count: `{s['parallelizable_action_count']}`",
        f"- first_parallelizable_action_id: `{s['first_parallelizable_action_id']}`",
        f"- first_parallelizable_action_required_exact_evidence_fields: `{s['first_parallelizable_action_required_exact_evidence_fields']}`",
        f"- first_parallelizable_action_operator_review_artifact: `{s['first_parallelizable_action_operator_review_artifact']}`",
        f"- first_parallelizable_action_acceptance_gate_commands: `{s['first_parallelizable_action_acceptance_gate_commands']}`",
        f"- first_parallelizable_action_next_slot_source_modality: `{s['first_parallelizable_action_next_slot_source_modality']}`",
        f"- first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed: `{s['first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed']}`",
        f"- first_parallelizable_action_next_slot_source_modality_decision: `{s['first_parallelizable_action_next_slot_source_modality_decision']}`",
        f"- production_ai_return_action_id: `{s['production_ai_return_action_id']}`",
        f"- production_ai_return_operator_completion_artifact_path: `{s['production_ai_return_operator_completion_artifact_path']}`",
        f"- production_ai_return_bundle_next_artifact_id: `{s['production_ai_return_bundle_next_artifact_id']}`",
        f"- production_ai_return_bundle_failed_check_ids: `{';'.join(s['production_ai_return_bundle_next_artifact_failed_check_ids'])}`",
        f"- production_ai_return_bundle_post_return_validation_command: `{s['production_ai_return_bundle_post_return_validation_command']}`",
        f"- production_ai_registry_promotion_action_id: `{s['production_ai_registry_promotion_action_id']}`",
        f"- production_ai_registry_promotion_operator_completion_artifact_path: `{s['production_ai_registry_promotion_operator_completion_artifact_path']}`",
        f"- production_ai_registry_promotion_operator_completion_completion_rule: `{s['production_ai_registry_promotion_operator_completion_completion_rule']}`",
        f"- first_operator_completion_worker_runtime_receipt_contract_ready: `{s['first_operator_completion_worker_runtime_receipt_contract_ready']}`",
        f"- first_operator_completion_worker_runtime_receipt_required_fields_or_columns: `{';'.join(s['first_operator_completion_worker_runtime_receipt_required_fields_or_columns'])}`",
        f"- first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id: `{s['first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id']}`",
        f"- first_operator_completion_worker_runtime_receipt_post_environment_validation_command: `{s['first_operator_completion_worker_runtime_receipt_post_environment_validation_command']}`",
        f"- first_operator_completion_diagnostic_command_count: `{s['first_operator_completion_diagnostic_command_count']}`",
        f"- first_operator_completion_diagnostic_completion_rule: `{s['first_operator_completion_diagnostic_completion_rule'] or '-'}`",
        f"- first_action_id: `{s['first_action_id']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## Ladder",
        "",
        "| order | action | lane | parallel | input artifact | inputs | exact fields | review artifact | execution | validation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['execution_order']}` | `{row['action_id']}` | `{row['workstream_lane_id']}` | "
            f"`{row['parallelizable_with_primary_blocker']}` | `{row['operator_input_artifact']}` | "
            f"`{row['required_operator_inputs']}` | `{row['required_exact_evidence_fields']}` | "
            f"`{row['operator_review_artifact']}` | `{row['execution_command']}` | "
            f"`{row['validation_command']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build commercial-readiness execution ladder from handoff artifacts.")
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--freshness-json", default=DEFAULT_FRESHNESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_commercial_readiness_execution_ladder(
        operator_packet=_read_json_if_present(args.operator_packet_json),
        freshness_packet=_read_json_if_present(args.freshness_json),
        operator_packet_path=args.operator_packet_json,
        freshness_path=args.freshness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
