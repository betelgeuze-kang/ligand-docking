#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHITECTURE_JSON = "runs/product_ai_architecture_gap_closure_current.json"
DEFAULT_TRAINING_DATA_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_CHECKPOINT_WORK_ORDER_JSON = "runs/residual_production_checkpoint_work_order_current.json"
DEFAULT_SCOPE_WORK_ORDER_JSON = "runs/product_scope_breadth_work_order_current.json"
DEFAULT_SCOPE_CLOSURE_CHECKLIST_JSON = "runs/product_scope_breadth_closure_checklist_current.json"
DEFAULT_FORCE_RECEIPT_JSON = "runs/residual_force_gpu_worker_return_receipt_current.json"
DEFAULT_OUT_JSON = "runs/product_ai_architecture_execution_backlog_current.json"
DEFAULT_OUT_CSV = "runs/product_ai_architecture_execution_backlog_current.csv"
DEFAULT_OUT_MD = "runs/product_ai_architecture_execution_backlog_current.md"

CLAIM_BOUNDARY = (
    "Product AI architecture execution backlog only; consolidates existing local gap, training-data, checkpoint, "
    "and scope work-order evidence into prioritized next actions. It does not train models, create checkpoints, "
    "run docking, widen scope, promote production mode, upload, submit, email, delete, or mutate external state."
)

FORCE_LABEL_EVIDENCE_VERIFICATION_COMMAND = " && ".join(
    [
        "python3 tools/build_residual_force_trajectory_regeneration_queue.py",
        "python3 tools/build_residual_force_gpu_worker_return_manifest_template.py",
        "python3 tools/build_residual_force_gpu_worker_return_summary_template.py",
        "python3 tools/build_residual_force_gpu_worker_handoff_package.py",
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
        "python3 tools/build_residual_force_derivation_validation.py",
        "python3 tools/build_residual_energy_force_label_validation.py",
        "python3 tools/build_residual_energy_force_label_evidence_work_order.py",
        "python3 tools/build_residual_uncertainty_policy_evidence_contract.py",
        "python3 tools/build_residual_production_training_data_contract.py",
        "python3 tools/build_product_ai_architecture_execution_backlog.py",
        "python3 tools/build_product_ai_architecture_gap_closure.py",
    ]
)

PRODUCTION_CHECKPOINT_VERIFICATION_COMMAND = " && ".join(
    [
        "python3 tools/build_residual_uncertainty_policy_evidence_contract.py",
        "python3 tools/build_residual_production_training_data_contract.py",
        "python3 tools/train_residual_production_score_model.py",
        "python3 tools/build_residual_production_checkpoint_sidecar.py",
        "python3 tools/build_residual_production_checkpoint_preflight.py",
        "python3 tools/build_residual_production_checkpoint_work_order.py",
        "python3 tools/build_residual_model_registry.py",
        "python3 tools/build_product_ai_architecture_execution_backlog.py",
        "python3 tools/build_product_ai_architecture_gap_closure.py",
    ]
)

TRAINING_DATA_CONTRACT_VERIFICATION_COMMAND = (
    "python3 tools/build_residual_uncertainty_policy_evidence_contract.py && "
    "python3 tools/build_residual_production_training_data_contract.py && "
    "python3 tools/build_product_ai_architecture_execution_backlog.py && "
    "python3 tools/build_product_ai_architecture_gap_closure.py"
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _receipt_observed_suffix(force_receipt: dict[str, Any]) -> str:
    if not force_receipt:
        return ""
    return (
        f"gpu_worker_return_receipt_ready={force_receipt.get('gpu_worker_return_receipt_ready')};"
        f"gpu_worker_return_receipt_blockers={','.join(str(item) for item in force_receipt.get('blockers') or [])};"
        f"gpu_worker_return_summary_manifest_bound={force_receipt.get('full_regeneration_summary_manifest_bound')};"
        f"gpu_worker_return_summary_manifest_csv={force_receipt.get('summary_manifest_csv')};"
        f"gpu_worker_return_summary_out_manifest_csv_present={force_receipt.get('full_regeneration_summary_out_manifest_csv_present')};"
        f"gpu_worker_return_summary_out_manifest_csv={force_receipt.get('summary_out_manifest_csv')};"
        f"gpu_worker_return_summary_out_manifest_csv_bound={force_receipt.get('full_regeneration_summary_out_manifest_csv_bound')};"
        f"gpu_worker_return_summary_out_summary_json_bound={force_receipt.get('full_regeneration_summary_out_summary_json_bound')};"
        f"gpu_worker_return_summary_out_summary_json={force_receipt.get('summary_out_summary_json')};"
        f"gpu_worker_return_summary_manifest_row_counts_consistent={force_receipt.get('full_regeneration_summary_manifest_row_counts_consistent')};"
        f"gpu_worker_return_expected_queue_rows={force_receipt.get('expected_queue_rows')};"
        f"gpu_worker_return_manifest_ok_row_count={force_receipt.get('manifest_ok_row_count')};"
        f"gpu_worker_return_manifest_status_placeholder_count={force_receipt.get('manifest_status_placeholder_count')};"
        f"gpu_worker_return_manifest_status_invalid_count={force_receipt.get('manifest_status_invalid_count')};"
        f"gpu_worker_return_manifest_allowed_ok_status_values={','.join(str(item) for item in force_receipt.get('manifest_allowed_ok_status_values') or [])};"
        f"gpu_worker_return_manifest_npz_paths_complete={force_receipt.get('full_regeneration_manifest_npz_paths_complete')};"
        f"gpu_worker_return_manifest_npz_path_present_count={force_receipt.get('manifest_npz_path_present_count')};"
        f"gpu_worker_return_manifest_npz_path_missing_count={force_receipt.get('manifest_npz_path_missing_count')};"
        f"gpu_worker_return_manifest_ok_row_missing_npz_path_count={force_receipt.get('manifest_ok_row_missing_npz_path_count')};"
        f"gpu_worker_return_manifest_operator_verified_missing_npz_path_count={force_receipt.get('manifest_operator_verified_missing_npz_path_count')};"
        f"gpu_worker_return_manifest_npz_files_exist={force_receipt.get('full_regeneration_manifest_npz_files_exist')};"
        f"gpu_worker_return_manifest_npz_file_existing_count={force_receipt.get('manifest_npz_file_existing_count')};"
        f"gpu_worker_return_manifest_npz_file_missing_count={force_receipt.get('manifest_npz_file_missing_count')};"
        f"gpu_worker_return_manifest_ok_row_missing_npz_file_count={force_receipt.get('manifest_ok_row_missing_npz_file_count')};"
        f"gpu_worker_return_manifest_operator_verified_missing_npz_file_count={force_receipt.get('manifest_operator_verified_missing_npz_file_count')};"
        f"gpu_worker_return_manifest_npz_files_valid={force_receipt.get('full_regeneration_manifest_npz_files_valid')};"
        f"gpu_worker_return_manifest_npz_file_valid_count={force_receipt.get('manifest_npz_file_valid_count')};"
        f"gpu_worker_return_manifest_npz_file_invalid_count={force_receipt.get('manifest_npz_file_invalid_count')};"
        f"gpu_worker_return_manifest_ok_row_invalid_npz_file_count={force_receipt.get('manifest_ok_row_invalid_npz_file_count')};"
        f"gpu_worker_return_manifest_operator_verified_invalid_npz_file_count={force_receipt.get('manifest_operator_verified_invalid_npz_file_count')};"
        f"gpu_worker_return_manifest_npz_schema_valid={force_receipt.get('full_regeneration_manifest_npz_schema_valid')};"
        f"gpu_worker_return_manifest_npz_schema_valid_count={force_receipt.get('manifest_npz_schema_valid_count')};"
        f"gpu_worker_return_manifest_npz_schema_invalid_count={force_receipt.get('manifest_npz_schema_invalid_count')};"
        f"gpu_worker_return_manifest_ok_row_invalid_npz_schema_count={force_receipt.get('manifest_ok_row_invalid_npz_schema_count')};"
        f"gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count={force_receipt.get('manifest_operator_verified_invalid_npz_schema_count')};"
        f"gpu_worker_return_manifest_npz_identity_valid={force_receipt.get('full_regeneration_manifest_npz_identity_valid')};"
        f"gpu_worker_return_manifest_npz_identity_valid_count={force_receipt.get('manifest_npz_identity_valid_count')};"
        f"gpu_worker_return_manifest_npz_identity_invalid_count={force_receipt.get('manifest_npz_identity_invalid_count')};"
        f"gpu_worker_return_manifest_ok_row_invalid_npz_identity_count={force_receipt.get('manifest_ok_row_invalid_npz_identity_count')};"
        f"gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count={force_receipt.get('manifest_operator_verified_invalid_npz_identity_count')};"
        f"gpu_worker_return_manifest_operator_verified={force_receipt.get('full_regeneration_manifest_operator_verified')};"
        f"gpu_worker_return_operator_verified_true_count={force_receipt.get('manifest_operator_verified_true_count')};"
        f"gpu_worker_return_operator_verification_column_present={force_receipt.get('manifest_operator_verification_column_present')};"
        f"gpu_worker_return_identity_coverage_ready={force_receipt.get('queue_manifest_identity_coverage_ready')};"
        f"gpu_worker_return_matched_queue_fingerprints={force_receipt.get('manifest_matched_queue_fingerprint_count')};"
        f"gpu_worker_return_queue_fingerprints={force_receipt.get('queue_fingerprint_count')}"
    )


def _without_gpu_return_pairs(observed: str) -> str:
    parts = []
    for part in observed.split(";"):
        text = part.strip()
        if not text:
            continue
        key = text.split("=", 1)[0].strip()
        if key.startswith("gpu_worker_return_"):
            continue
        parts.append(text)
    return ";".join(parts)


def _count_map_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return ",".join(f"{key}={value[key]}" for key in sorted(value))


def _scope_closure_detail(closure: dict[str, Any]) -> str:
    if not closure:
        return ""
    return (
        f"scope_closure_blocker_classes={_count_map_text(closure.get('blocker_class_counts'))};"
        f"scope_closure_first_scientific_blocker={_text(closure.get('first_scientific_blocker'))};"
        f"scope_closure_manual_review_subcheck_count={closure.get('manual_review_subcheck_count')};"
        f"scope_closure_transporter_manual_review_subcheck_count={closure.get('transporter_manual_review_subcheck_count')};"
        f"scope_closure_transporter_identity_scaffold_confirmation_required_count={closure.get('transporter_identity_scaffold_confirmation_required_count')};"
        f"scope_closure_transporter_direct_binding_or_kcal_confirmation_required_count={closure.get('transporter_direct_binding_or_kcal_confirmation_required_count')};"
        f"scope_closure_transporter_negative_quantitative_confirmation_required_count={closure.get('transporter_negative_quantitative_confirmation_required_count')};"
        f"scope_closure_transporter_direct_binding_missing_count={closure.get('transporter_direct_binding_missing_count')};"
        f"scope_closure_transporter_negative_quantitative_missing_count={closure.get('transporter_negative_quantitative_missing_count')};"
        f"scope_closure_pxr_reconciled_blocked_row_count={closure.get('pxr_reconciled_blocked_row_count')};"
        f"scope_closure_pxr_conflict_resolution_count={closure.get('pxr_conflict_resolution_count')};"
        f"scope_closure_pxr_quantitative_missing_count={closure.get('pxr_quantitative_missing_count')};"
        f"scope_closure_general_claim_blocker_count={closure.get('general_claim_blocker_count')};"
        f"scope_closure_ready_for_apply_count={closure.get('ready_for_apply_count')};"
        f"scope_closure_authoritative_apply_allowed={closure.get('authoritative_apply_allowed')};"
        f"scope_claim_boundary={_text(closure.get('claim_boundary_detail'))}"
    )


def _scope_closure_row(
    priority: int,
    item: dict[str, Any],
    source_artifact: str,
) -> dict[str, Any]:
    domain = _text(item.get("domain")) or "unknown"
    item_id = _text(item.get("item_id")) or f"priority_{item.get('priority')}"
    missing = _text(item.get("missing_fields")) or "none"
    blockers = _text(item.get("manual_review_blockers")) or "none"
    manual_subchecks = _text(item.get("manual_review_subchecks")) or "none"
    candidate_ligand_id = _text(item.get("candidate_ligand_id")) or "none"
    candidate_source = _text(item.get("candidate_source")) or "none"
    candidate_kcal = _text(item.get("candidate_reference_binding_kcal_mol")) or "none"
    lane = _text(item.get("closure_lane")) or "scope_closure"
    blocker_class = _text(item.get("blocker_class")) or "unclassified_scope_blocker"
    claim_impact = _text(item.get("customer_claim_impact")) or "broad product-scope wording remains blocked"
    return _row(
        priority,
        "scope_breadth_expansion",
        f"scope_breadth.{domain}.{item_id}",
        _text(item.get("source_artifact")) or source_artifact,
        (
            f"lane={lane};blocker_class={blocker_class};claim_impact={claim_impact};"
            f"state={_text(item.get('current_state'))};missing={missing};blockers={blockers};"
            f"manual_review_subchecks={manual_subchecks};candidate_ligand_id={candidate_ligand_id};"
            f"candidate_reference_binding_kcal_mol={candidate_kcal};candidate_source={candidate_source}"
        ),
        _text(item.get("acceptance_criteria")),
        _text(item.get("close_action")),
        _text(item.get("verification_command")) or "python3 tools/build_product_scope_breadth_closure_checklist.py && python3 tools/build_product_ai_architecture_gap_closure.py",
        "broad product-scope wording would be overclaimed until this atomic closure item is resolved",
        release_blocker=False,
    )


def _row(
    priority: int,
    gap_id: str,
    work_item_id: str,
    source_artifact: str,
    observed: str,
    acceptance_criteria: str,
    next_action: str,
    verification_command: str,
    risk: str,
    *,
    release_blocker: bool = True,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "gap_id": gap_id,
        "work_item_id": work_item_id,
        "source_artifact": source_artifact,
        "observed": observed,
        "acceptance_criteria": acceptance_criteria,
        "next_action": next_action,
        "verification_command": verification_command,
        "risk": risk,
        "release_blocker": release_blocker,
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "scope_widened": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _production_output_field_action(field: str) -> tuple[str, str]:
    actions = {
        "delta_energy": (
            "Learn or explicitly validate a production delta_energy head with labels/evaluation, not a guarded-zero placeholder.",
            "trained/evaluated delta_energy output head is present in the production checkpoint artifact",
        ),
        "delta_force": (
            "Learn or derive a production delta_force head from validated delta_energy gradients with force-shape and physics checks.",
            "trained/evaluated delta_force output head or validated -grad(delta_energy) derivation is present",
        ),
        "uncertainty": (
            "Calibrate uncertainty for the production checkpoint and attach calibration evidence to the sidecar.",
            "production uncertainty calibration artifact is linked and ready",
        ),
        "abstention_reason": (
            "Bind an abstention policy that emits customer-facing reasons for OOD, high uncertainty, or physics-guard violations.",
            "production checkpoint emits abstention_reason under the guarded abstention policy",
        ),
        "stage2_route_decision": (
            "Bind a stage-2 route policy that sends uncertain/high-value cases to the frozen expensive path.",
            "production checkpoint emits stage2_route_decision with validated routing policy evidence",
        ),
        "corrected_score": (
            "Validate corrected_score as raw_score plus learned delta_score under guardrails.",
            "production checkpoint emits corrected_score with no pass-to-fail benchmark regression",
        ),
        "delta_score": (
            "Validate learned delta_score as the customer-facing residual correction head.",
            "production checkpoint emits learned delta_score with benchmark-bound regression evidence",
        ),
    }
    return actions.get(
        field,
        (
            f"Add production output-head evidence for {field}.",
            f"production checkpoint emits {field} with validation evidence",
        ),
    )


def _production_output_head_rows(priority: int, item: dict[str, Any], training_data_path: str) -> tuple[list[dict[str, Any]], int]:
    missing_fields = [str(field) for field in item.get("missing_production_output_fields") or []]
    if not missing_fields:
        return [], priority
    rows = []
    for field in missing_fields:
        next_action, acceptance = _production_output_field_action(field)
        rows.append(
            _row(
                priority,
                "production_ai_inference_checkpoint",
                f"training_data.production_residual_output_head.{field}",
                _text(item.get("score_model_artifact")) or _text(item.get("source_artifact")) or training_data_path,
                f"missing_production_output_field={field};{_text(item.get('observed'))}",
                acceptance,
                next_action,
                PRODUCTION_CHECKPOINT_VERIFICATION_COMMAND,
                "production checkpoint would be overclaimed while a required output head is missing",
            )
        )
        priority += 1
    return rows, priority


def build_product_ai_architecture_execution_backlog(
    *,
    architecture_packet: dict[str, Any],
    training_data_packet: dict[str, Any],
    checkpoint_work_order_packet: dict[str, Any],
    scope_work_order_packet: dict[str, Any],
    scope_closure_checklist_packet: dict[str, Any] | None = None,
    force_receipt_packet: dict[str, Any] | None = None,
    architecture_path: str = DEFAULT_ARCHITECTURE_JSON,
    training_data_path: str = DEFAULT_TRAINING_DATA_JSON,
    checkpoint_work_order_path: str = DEFAULT_CHECKPOINT_WORK_ORDER_JSON,
    scope_work_order_path: str = DEFAULT_SCOPE_WORK_ORDER_JSON,
    scope_closure_checklist_path: str = DEFAULT_SCOPE_CLOSURE_CHECKLIST_JSON,
    force_receipt_path: str = DEFAULT_FORCE_RECEIPT_JSON,
) -> dict[str, Any]:
    architecture = _summary(architecture_packet)
    training = _summary(training_data_packet)
    checkpoint = _summary(checkpoint_work_order_packet)
    scope = _summary(scope_work_order_packet)
    closure_packet = scope_closure_checklist_packet or {}
    closure = _summary(closure_packet)
    closure_rows = _rows(closure_packet)
    scope_closure_detail = _scope_closure_detail(closure)
    force_receipt = _summary(force_receipt_packet or {})

    rows: list[dict[str, Any]] = []
    priority = 1

    if not _bool(training.get("production_training_data_ready")):
        for item in _rows(training_data_packet):
            if _text(item.get("status")) == "pass":
                continue
            if _text(item.get("check_id")) == "production_residual_output_head":
                atomic_rows, priority = _production_output_head_rows(priority, item, training_data_path)
                rows.extend(atomic_rows)
                if atomic_rows:
                    continue
            check_id = _text(item.get("check_id"))
            if check_id == "production_delta_force_label_evidence":
                verification_command = FORCE_LABEL_EVIDENCE_VERIFICATION_COMMAND
                receipt_suffix = _receipt_observed_suffix(force_receipt)
            elif check_id in {"production_uncertainty_abstention_route_policy", "uncertainty_physics_guard_binding"}:
                verification_command = PRODUCTION_CHECKPOINT_VERIFICATION_COMMAND
                receipt_suffix = ""
            else:
                verification_command = TRAINING_DATA_CONTRACT_VERIFICATION_COMMAND
                receipt_suffix = ""
            rows.append(
                _row(
                    priority,
                    "production_ai_inference_checkpoint",
                    f"training_data.{check_id}",
                    _text(item.get("source_artifact")) or training_data_path,
                    (
                        (
                            _without_gpu_return_pairs(_text(item.get("observed")))
                            if check_id == "production_delta_force_label_evidence"
                            else _text(item.get("observed"))
                        )
                        + (f";{receipt_suffix}" if receipt_suffix else "")
                    ),
                    _text(item.get("required")),
                    _text(item.get("next_action")),
                    verification_command,
                    "production checkpoint would be overclaimed without this evidence",
                )
            )
            priority += 1

    if not _bool(checkpoint.get("checkpoint_preflight_ready")):
        rows.append(
            _row(
                priority,
                "production_ai_inference_checkpoint",
                "checkpoint_work_order.ready_checkpoint",
                checkpoint_work_order_path,
                (
                    f"candidate_checkpoint_count={checkpoint.get('candidate_checkpoint_count')};"
                    f"ready_checkpoint_count={checkpoint.get('ready_checkpoint_count')};"
                    f"compatible_candidate_count={checkpoint.get('compatible_candidate_count')};"
                    f"sidecar_builder_ready={checkpoint.get('sidecar_builder_ready')};"
                    f"sidecar_builder_status={checkpoint.get('sidecar_builder_status')};"
                    f"sidecar_training_data_ready={checkpoint.get('sidecar_builder_training_data_contract_ready')};"
                    f"sidecar_force_receipt_ready={checkpoint.get('sidecar_builder_force_gpu_return_receipt_ready')};"
                    f"sidecar_force_receipt_operator_verified={checkpoint.get('sidecar_builder_force_gpu_return_receipt_operator_verified')};"
                    f"sidecar_force_receipt_operator_verified_true_count={checkpoint.get('sidecar_builder_force_gpu_return_receipt_operator_verified_true_count')};"
                    f"sidecar_force_receipt_expected_queue_rows={checkpoint.get('sidecar_builder_force_gpu_return_receipt_expected_queue_rows')};"
                    f"sidecar_builder_blockers={','.join(str(item) for item in checkpoint.get('sidecar_builder_blockers') or [])};"
                    f"sidecar_missing_production_output_fields={','.join(str(item) for item in checkpoint.get('sidecar_builder_missing_production_output_fields') or [])};"
                    f"sidecar_training_contract_missing_label_fields={','.join(str(item) for item in checkpoint.get('sidecar_builder_training_contract_missing_label_fields') or [])};"
                    f"checkpoint_closure_blockers={','.join(str(item) for item in checkpoint.get('checkpoint_closure_blockers') or [])};"
                    f"registry_checkpoint_missing_output_fields={','.join(str(item) for item in checkpoint.get('registry_checkpoint_missing_output_fields') or [])};"
                    f"registry_checkpoint_missing_adapter_output_policy_fields={','.join(str(item) for item in checkpoint.get('registry_checkpoint_missing_adapter_output_policy_fields') or [])}"
                ),
                "ready_for_guarded_promotion=true in residual_production_checkpoint_preflight and production_promotion_allowed=true in residual_model_registry",
                _text(checkpoint.get("next_required_step")) or "Choose or train a protein-ligand residual checkpoint and rerun preflight.",
                PRODUCTION_CHECKPOINT_VERIFICATION_COMMAND,
                "local checkpoint candidates exist, but none are preflight-ready production protein-ligand residual checkpoints",
            )
        )
        priority += 1

    scope_closure_checklist_used = False
    if not _bool(scope.get("scope_breadth_ready")) and _bool(closure.get("closure_checklist_ready")) and closure_rows:
        scope_closure_checklist_used = True
        for item in closure_rows:
            if item.get("ready_for_apply") is True and item.get("scope_promotion_allowed") is True:
                continue
            rows.append(_scope_closure_row(priority, item, scope_closure_checklist_path))
            priority += 1
    elif not _bool(scope.get("scope_breadth_ready")):
        for item in _rows(scope_work_order_packet):
            rows.append(
                _row(
                    priority,
                    "scope_breadth_expansion",
                    f"scope_breadth.{item.get('domain')}",
                    _text(item.get("source_artifact")) or scope_work_order_path,
                    _text(item.get("observed")),
                    _text(item.get("acceptance_criteria")),
                    _text(item.get("next_action")),
                    _text(item.get("verification_command"))
                    or _text(item.get("verification"))
                    or "python3 tools/build_product_scope_breadth_contract.py && python3 tools/build_product_ai_architecture_gap_closure.py",
                    _text(item.get("risk_if_skipped")) or _text(item.get("risk")) or "broad product-scope wording would be overclaimed",
                    release_blocker=False,
                )
            )
            priority += 1

    if not rows:
        for item in _rows(architecture_packet):
            if _text(item.get("status")) == "closed":
                continue
            rows.append(
                _row(
                    priority,
                    _text(item.get("gap_id")),
                    f"architecture.{item.get('gap_id')}",
                    _text(item.get("evidence")) or architecture_path,
                    _text(item.get("observed")),
                    _text(item.get("close_requirement")),
                    _text(item.get("next_action")),
                    "python3 tools/build_product_ai_architecture_gap_closure.py",
                    "architecture gap remains open without a more specific work-order artifact",
                )
            )
            priority += 1

    release_blocking_rows = [row for row in rows if _bool(row.get("release_blocker", True))]
    ready = not release_blocking_rows and _bool(architecture.get("all_gaps_closed"))
    summary = {
        "packet_type": "product_ai_architecture_execution_backlog",
        "status": "product_ai_architecture_execution_backlog_clear" if ready else "product_ai_architecture_execution_backlog_ready",
        "backlog_clear": ready,
        "all_gaps_closed": _bool(architecture.get("all_gaps_closed")),
        "open_gap_count": int(architecture.get("open_gap_count") or 0),
        "work_item_count": len(rows),
        "release_blocking_work_item_count": len(release_blocking_rows),
        "scope_deferred_work_item_count": len(rows) - len(release_blocking_rows),
        "primary_work_item_id": rows[0]["work_item_id"] if rows else "none",
        "scope_closure_checklist_used": scope_closure_checklist_used,
        "scope_closure_checklist_item_count": len(closure_rows) if scope_closure_checklist_used else 0,
        "scope_closure_blocker_class_counts": closure.get("blocker_class_counts") if isinstance(closure.get("blocker_class_counts"), dict) else {},
        "scope_closure_first_scientific_blocker": _text(closure.get("first_scientific_blocker")),
        "scope_closure_manual_review_subcheck_count": closure.get("manual_review_subcheck_count"),
        "scope_closure_transporter_manual_review_subcheck_count": closure.get("transporter_manual_review_subcheck_count"),
        "scope_closure_transporter_identity_scaffold_confirmation_required_count": closure.get(
            "transporter_identity_scaffold_confirmation_required_count"
        ),
        "scope_closure_transporter_direct_binding_or_kcal_confirmation_required_count": closure.get(
            "transporter_direct_binding_or_kcal_confirmation_required_count"
        ),
        "scope_closure_transporter_negative_quantitative_confirmation_required_count": closure.get(
            "transporter_negative_quantitative_confirmation_required_count"
        ),
        "scope_closure_detail": scope_closure_detail,
        "source_artifacts": [
            architecture_path,
            training_data_path,
            checkpoint_work_order_path,
            scope_work_order_path,
            scope_closure_checklist_path,
            force_receipt_path,
        ],
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "scope_widened": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": rows[0]["next_action"] if rows else "No execution backlog remains.",
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product AI Architecture Execution Backlog",
        "",
        f"- status: `{s['status']}`",
        f"- backlog_clear: `{s['backlog_clear']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- open_gap_count: `{s['open_gap_count']}`",
        f"- work_item_count: `{s['work_item_count']}`",
        f"- primary_work_item_id: `{s['primary_work_item_id']}`",
        f"- scope_closure_detail: `{s['scope_closure_detail']}`",
        "",
        "## Work Items",
        "",
        "| priority | gap | work item | observed | acceptance criteria | verification |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['gap_id']}` | `{row['work_item_id']}` | `{row['observed']}` | "
            f"`{row['acceptance_criteria']}` | `{row['verification_command']}` |"
        )
    if not payload["rows"]:
        lines.append("| 0 | `none` | `none` | `none` | `none` | `none` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a consolidated execution backlog for open product AI architecture gaps.")
    parser.add_argument("--architecture-json", default=DEFAULT_ARCHITECTURE_JSON)
    parser.add_argument("--training-data-json", default=DEFAULT_TRAINING_DATA_JSON)
    parser.add_argument("--checkpoint-work-order-json", default=DEFAULT_CHECKPOINT_WORK_ORDER_JSON)
    parser.add_argument("--scope-work-order-json", default=DEFAULT_SCOPE_WORK_ORDER_JSON)
    parser.add_argument("--scope-closure-checklist-json", default=DEFAULT_SCOPE_CLOSURE_CHECKLIST_JSON)
    parser.add_argument("--force-receipt-json", default=DEFAULT_FORCE_RECEIPT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_ai_architecture_execution_backlog(
        architecture_packet=_read_json_if_present(args.architecture_json),
        training_data_packet=_read_json_if_present(args.training_data_json),
        checkpoint_work_order_packet=_read_json_if_present(args.checkpoint_work_order_json),
        scope_work_order_packet=_read_json_if_present(args.scope_work_order_json),
        scope_closure_checklist_packet=_read_json_if_present(args.scope_closure_checklist_json),
        force_receipt_packet=_read_json_if_present(args.force_receipt_json),
        architecture_path=args.architecture_json,
        training_data_path=args.training_data_json,
        checkpoint_work_order_path=args.checkpoint_work_order_json,
        scope_work_order_path=args.scope_work_order_json,
        scope_closure_checklist_path=args.scope_closure_checklist_json,
        force_receipt_path=args.force_receipt_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
