#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOAL_AUDIT_JSON = "runs/product_goal_completion_audit_current.json"
DEFAULT_DELTA_FORCE_CLOSURE_PACKET_JSON = "runs/residual_delta_force_closure_acceptance_packet_current.json"
DEFAULT_SCOPE_CLOSURE_PACKET_JSON = "runs/product_scope_closure_acceptance_packet_current.json"
DEFAULT_AQP1_DIRECT_BINDING_PROCUREMENT_JSON = "runs/aqp1_direct_binding_procurement_packet_current.json"
DEFAULT_OUT_JSON = "runs/product_commercial_readiness_operator_packet_current.json"
DEFAULT_OUT_CSV = "runs/product_commercial_readiness_operator_packet_current.csv"
DEFAULT_OUT_MD = "runs/product_commercial_readiness_operator_packet_current.md"

CLAIM_BOUNDARY = (
    "Product commercial-readiness operator packet only; it flattens the current goal-completion next-action matrix "
    "into human handoff rows. It does not run docking, run GPU jobs, fill scientific evidence, promote checkpoints, "
    "widen product claims, upload, submit, email, delete, or mutate external state."
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
    goal_audit_path: str = DEFAULT_GOAL_AUDIT_JSON,
    delta_force_closure_packet_path: str = DEFAULT_DELTA_FORCE_CLOSURE_PACKET_JSON,
    scope_closure_packet_path: str = DEFAULT_SCOPE_CLOSURE_PACKET_JSON,
    aqp1_direct_binding_procurement_path: str = DEFAULT_AQP1_DIRECT_BINDING_PROCUREMENT_JSON,
) -> dict[str, Any]:
    summary = _summary(goal_audit_packet)
    delta_force_closure = _summary(delta_force_closure_packet or {})
    scope_closure = _summary(scope_closure_packet or {})
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
        goal_audit_path=args.goal_audit_json,
        delta_force_closure_packet_path=args.delta_force_closure_packet_json,
        scope_closure_packet_path=args.scope_closure_packet_json,
        aqp1_direct_binding_procurement_path=args.aqp1_direct_binding_procurement_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
