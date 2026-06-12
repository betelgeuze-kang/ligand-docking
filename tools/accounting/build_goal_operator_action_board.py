#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_goal_readiness_rollup import (
    DEFAULT_CAMEO_INPUT_KIT_JSON,
    DEFAULT_CAMEO_INPUT_VALIDATION_JSON,
    DEFAULT_CAMEO_REPAIR_PREFLIGHT_JSON,
    DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON,
    DEFAULT_OUT_JSON as DEFAULT_ROLLUP_JSON,
    DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON,
    DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON,
    DEFAULT_PRODUCT_PILOT_PACKET_JSON,
    DEFAULT_PRODUCT_PREFLIGHT_JSON,
    DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON,
)
from tools.build_goal_release_decision_gate import DEFAULT_OUT_JSON as DEFAULT_GOAL_RELEASE_DECISION_GATE_JSON
from tools.build_goal_release_burndown_work_order import DEFAULT_OUT_JSON as DEFAULT_GOAL_RELEASE_BURNDOWN_WORK_ORDER_JSON
from tools.build_cleanup_snapshot_preflight import DEFAULT_OUT_JSON as DEFAULT_CLEANUP_SNAPSHOT_PREFLIGHT_JSON
from tools.build_cleanup_execution_approval_dossier import DEFAULT_OUT_JSON as DEFAULT_CLEANUP_EXECUTION_APPROVAL_DOSSIER_JSON
from tools.build_cleanup_execution_approval_gate import DEFAULT_OUT_JSON as DEFAULT_CLEANUP_EXECUTION_APPROVAL_GATE_JSON
from tools.build_cleanup_payload_manifest_lock import DEFAULT_OUT_JSON as DEFAULT_CLEANUP_PAYLOAD_MANIFEST_LOCK_JSON
from tools.build_cleanup_postcheck_contract import DEFAULT_OUT_JSON as DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON
from tools.build_product_execution_approval_gate import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_EXECUTION_APPROVAL_GATE_JSON
from tools.build_product_license_decision_gate import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_LICENSE_DECISION_GATE_JSON
from tools.build_product_license_decision_packet import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_LICENSE_DECISION_PACKET_JSON
from tools.build_product_license_file_creation_work_order import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_LICENSE_FILE_CREATION_WORK_ORDER_JSON
from tools.build_cameo_validation_operations_dossier import DEFAULT_OUT_JSON as DEFAULT_CAMEO_VALIDATION_OPERATIONS_DOSSIER_JSON
from tools.build_cameo_official_results_intake_gate import DEFAULT_OUT_JSON as DEFAULT_CAMEO_OFFICIAL_RESULTS_INTAKE_GATE_JSON
from tools.build_cameo_public_registration_approval_gate import DEFAULT_OUT_JSON as DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON
from tools.build_product_release_operations_dossier import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_RELEASE_OPERATIONS_DOSSIER_JSON
from tools.build_protected_cleanup_policy_decision_gate import DEFAULT_OUT_JSON as DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON
from tools.build_protected_ligand_heavy_payload_deep_review import DEFAULT_OUT_JSON as DEFAULT_PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_JSON
from tools.build_cleanup_completion_gate import DEFAULT_OUT_JSON as DEFAULT_CLEANUP_COMPLETION_GATE_JSON
from betelgeuze_cameo.cli import build_all_status as build_cameo_cli_all_status
from betelgeuze_cleanup.cli import build_all_status as build_cleanup_cli_all_status
from betelgeuze_product.cli import build_all_status as build_product_cli_all_status
from tools.product.build_product_scope_breadth_evidence_receipt import (
    APPROVAL_TOKEN as PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_APPROVAL_TOKEN,
    DEFAULT_RECEIPT_CSV as DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_CSV,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/goal_operator_action_board_current.json"
DEFAULT_OUT_CSV = "runs/goal_operator_action_board_current.csv"
DEFAULT_OUT_MD = "runs/goal_operator_action_board_current.md"
DEFAULT_LARGE_CLEANUP_DRILLDOWN_JSON = "runs/large_cleanup_surface_drilldown_current.json"
DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_CAMEO_RUNTIME_REPAIR_WORK_ORDER_JSON = "runs/cameo_runtime_repair_work_order_current.json"
DEFAULT_GOAL_OPERATOR_INTAKE_KIT_JSON = "runs/goal_operator_intake_kit_current/manifest.json"
DEFAULT_PRODUCT_GOAL_COMPLETION_AUDIT_JSON = "runs/product_goal_completion_audit_current.json"
DEFAULT_ENGINE_REFINEMENT_CLAIM_ACTION_BOARD_CSV = (
    "runs/engine_refinement_claim_promotion_action_board_current.csv"
)

CLAIM_BOUNDARY = (
    "Goal operator action board only; it consolidates approval tokens, blocked CAMEO operator inputs, and cleanup review rows "
    "from existing local artifacts and summarizes the full-goal release gate. It does not run docking, rebuild CAMEO artifacts, "
    "submit predictions, send email, delete, archive, externalize, upload, commit, push, or mutate external state."
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


def _read_csv_if_present(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _action(
    *,
    priority: int,
    lane_id: str,
    action_type: str,
    status: str,
    required_input: str = "",
    approval_token: str = "",
    artifact_path: str = "",
    recommended_action: str = "",
    size_gb: float = 0.0,
    command: str = "",
    reason: str = "",
) -> dict[str, Any]:
    return {
        "priority": priority,
        "lane_id": lane_id,
        "action_type": action_type,
        "status": status,
        "required_input": required_input,
        "approval_token": approval_token,
        "artifact_path": artifact_path,
        "recommended_action": recommended_action,
        "size_gb": round(size_gb, 3),
        "command": command,
        "reason": reason,
        "action_executed": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def _next_required_step(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No operator actions are currently surfaced by the tracked readiness artifacts."
    first_lane = _text(rows[0].get("lane_id"))
    first_action = _text(rows[0].get("action_type"))
    if first_lane in {"commercial_product_execution", "commercial_product_license"}:
        return "Complete P1 product execution and license intake actions first; CAMEO official evidence and registration remain P2."
    if first_lane == "product_ai_production":
        return "Return the GPU force-regeneration summary and identity-locked manifest first, then run the post-return validation chain before any production AI promotion claim."
    if first_lane == "product_scope_expansion":
        return "Curate the top scope-priority evidence item first, keeping broader platform claims blocked until authoritative apply gates pass."
    if first_action == "fill_cameo_official_results_intake":
        return "Fill official CAMEO result intake rows when official assessment output is available; review approval tokens separately."
    if first_action == "fill_or_repair_cameo_operator_input":
        return "Complete priority-1 CAMEO operator input rows before CAMEO repair commands; review approval tokens separately."
    if first_action == "repair_cameo_receiver_runtime_smoke":
        return "Resolve the CAMEO receiver runtime smoke lane after explicit dependency approval; review product and cleanup approvals separately."
    return "Work through surfaced operator actions in priority order; approval-gated rows remain disabled until explicit tokens are provided."


def _primary_action(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return rows[0]


def _cameo_actions(
    *,
    input_kit: dict[str, Any],
    input_validation: dict[str, Any],
    repair_preflight: dict[str, Any],
    input_kit_path: str,
    input_validation_path: str,
    repair_preflight_path: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    validation_summary = _summary(input_validation)
    validation_blocked = validation_summary.get("status") == "blocked_cameo_operator_input_validation"
    if validation_blocked:
        for row in _rows(input_validation):
            actions.append(
                _action(
                    priority=1,
                    lane_id="cameo_validation",
                    action_type="fill_or_repair_cameo_operator_input",
                    status="required",
                    required_input=_text(row.get("input_name")),
                    artifact_path=input_validation_path,
                    reason=_text(row.get("blockers") or "operator input row is blocked"),
                )
            )
    if validation_blocked or not validation_summary:
        kit_rows = [row for row in _rows(input_kit) if row.get("required_now") is True]
        for row in kit_rows:
            actions.append(
                _action(
                    priority=2,
                    lane_id="cameo_validation",
                    action_type="use_cameo_input_template",
                    status="available",
                    required_input=_text(row.get("repair_command_arg")),
                    artifact_path=_text(row.get("path") or input_kit_path),
                    recommended_action="replace OPERATOR_FILL placeholders with internal local evidence rows",
                    reason=_text(row.get("purpose")),
                )
            )
    repair_summary = _summary(repair_preflight)
    if repair_summary.get("status") == "blocked_cameo_repair_execution_preflight":
        for row in _rows(repair_preflight):
            if _text(row.get("preflight_status")) != "fail":
                continue
            actions.append(
                _action(
                    priority=3,
                    lane_id="cameo_validation",
                    action_type="repair_cameo_rebuild_command",
                    status="blocked",
                    required_input=_text(row.get("input_required")),
                    artifact_path=repair_preflight_path,
                    command=_text(row.get("command")),
                    reason=_text(row.get("blockers") or "repair command row failed preflight"),
                )
            )
    return actions


def _cameo_receiver_smoke_actions(
    *,
    rollup_packet: dict[str, Any],
    rollup_path: str,
    runtime_repair_work_order: dict[str, Any],
    runtime_repair_work_order_path: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    runtime_summary = _summary(runtime_repair_work_order)
    for row in _rows(rollup_packet):
        if _text(row.get("lane_id")) != "cameo_validation":
            continue
        smoke_status = _text(row.get("receiver_smoke_status"))
        api_dependency_status = _text(row.get("api_dependency_status"))
        api_dependency_blockers = _int(row.get("api_dependency_blocker_count"))
        smoke_blockers = _int(row.get("receiver_smoke_blocker_count"))
        post_ok = row.get("receiver_smoke_post_200_ok") is True
        if smoke_status and (smoke_blockers > 0 or not post_ok):
            actions.append(
                _action(
                    priority=2,
                    lane_id="cameo_validation",
                    action_type="repair_cameo_receiver_runtime_smoke",
                    status="approval_required" if runtime_summary.get("install_approval_required") is True else "required",
                    required_input="requirements-api.txt runtime dependency set and receiver smoke rerun",
                    approval_token=_text(runtime_summary.get("approval_token_required")),
                    artifact_path=_text(runtime_repair_work_order_path if runtime_repair_work_order else row.get("artifact_path") or rollup_path),
                    recommended_action="install/activate the API dependency set, then rerun build_cameo_receiver_smoke_contract.py and build_cameo_capability_preflight.py",
                    reason=(
                        f"CAMEO receiver smoke status={smoke_status}, post_200_ok={post_ok}, blocker_count={smoke_blockers}; "
                        f"api_dependency_status={api_dependency_status or 'unknown'}, api_dependency_blocker_count={api_dependency_blockers}; "
                        f"runtime_repair_work_order_status={_text(runtime_summary.get('status')) or 'missing'}."
                    ),
                )
            )
    return actions


def _cameo_official_results_actions(
    *,
    official_results_intake_gate: dict[str, Any],
    official_results_intake_gate_path: str,
) -> list[dict[str, Any]]:
    summary = _summary(official_results_intake_gate)
    if not summary or summary.get("status") == "cameo_official_results_intake_ready":
        return []
    missing_columns = ";".join(_text(column) for column in summary.get("missing_required_columns", []) if _text(column))
    blocker_codes = ";".join(_text(code) for code in summary.get("blocker_codes", []) if _text(code))
    operator_intake_csv = _text(summary.get("operator_intake_csv")) or "runs/cameo_official_results_operator_intake.csv"
    action = _action(
        priority=2,
        lane_id="cameo_validation",
        action_type="fill_cameo_official_results_intake",
        status="required",
        required_input=f"official CAMEO results operator intake CSV;{operator_intake_csv}",
        artifact_path=official_results_intake_gate_path,
        recommended_action="Fill cameo_official_results_operator_intake.csv from official CAMEO assessment output, including CAMEO URL, record id, dates, model1 rank, and official metrics.",
        reason=(
            f"official_results_intake_status={_text(summary.get('status')) or 'missing'}, "
            f"result_row_count={_int(summary.get('result_row_count'))}, "
            f"accepted_official_result_count={_int(summary.get('accepted_official_result_count'))}, "
            f"rejected_official_result_count={_int(summary.get('rejected_official_result_count'))}, "
            f"model1_official_result_ready={bool(summary.get('model1_official_result_ready') is True)}, "
            f"blocker_count={_int(summary.get('blocker_count'))}, "
            f"blocker_codes={blocker_codes or 'none'}, "
            f"missing_required_columns={missing_columns or 'none'}."
        ),
    )
    action.update(
        {
            "official_results_operator_intake_csv": operator_intake_csv,
            "official_results_missing_required_columns": missing_columns,
            "official_results_blocker_codes": blocker_codes,
        }
    )
    return [action]


def _product_actions(
    *,
    product_preflight: dict[str, Any],
    bundle_contract: dict[str, Any],
    delivery_evidence: dict[str, Any],
    pilot_packet: dict[str, Any],
    product_preflight_path: str,
    bundle_contract_path: str,
    delivery_evidence_path: str,
    pilot_packet_path: str,
) -> list[dict[str, Any]]:
    preflight = _summary(product_preflight)
    bundle = _summary(bundle_contract)
    evidence = _summary(delivery_evidence)
    pilot = _summary(pilot_packet)
    if (
        preflight.get("status") != "product_execution_preflight_ready"
        or bundle.get("status") != "product_bundle_contract_ready"
        or (delivery_evidence and evidence.get("status") != "product_delivery_evidence_contract_ready")
        or (pilot_packet and pilot.get("status") not in {"product_pilot_packet_preflight_ready", "product_pilot_packet_ready"})
    ):
        return []
    artifact_path = f"{product_preflight_path};{bundle_contract_path}"
    reason = "Product command and bundle contract are parseable, but execution remains disabled until explicit approval."
    if delivery_evidence:
        artifact_path = f"{artifact_path};{delivery_evidence_path}"
        reason = (
            "Product command, bundle contract, and delivery evidence contract are ready, but customer delivery-ready wording "
            f"is allowed={bool(evidence.get('delivery_ready_claim_allowed') is True)} until bundle assembly/validation finishes."
        )
    if pilot_packet:
        artifact_path = f"{artifact_path};{pilot_packet_path}"
        reason = (
            f"{reason} Pilot packet status={_text(pilot.get('status'))}, "
            f"pilot_delivery_ready={bool(pilot.get('pilot_delivery_ready') is True)}."
        )
    return [
        _action(
            priority=1,
            lane_id="commercial_product_execution",
            action_type="review_product_execution_approval",
            status="approval_required",
            approval_token=_text(preflight.get("approval_token_required")),
            artifact_path=artifact_path,
            recommended_action="Review the product execution work order and fill the exact execution approval intake before running docking or bundle assembly.",
            command="operator-reviewed product execution command recorded in product work order",
            reason=reason,
        )
    ]


def _product_license_actions(
    *,
    product_license_decision_gate: dict[str, Any],
    product_license_decision_packet: dict[str, Any],
    product_license_file_creation_work_order: dict[str, Any] | None = None,
    product_license_decision_gate_path: str,
    product_license_decision_packet_path: str,
    product_license_file_creation_work_order_path: str = DEFAULT_PRODUCT_LICENSE_FILE_CREATION_WORK_ORDER_JSON,
) -> list[dict[str, Any]]:
    summary = _summary(product_license_decision_gate)
    packet = _summary(product_license_decision_packet)
    fill_command_template = _text(packet.get("operator_intake_fill_command_template"))
    actions: list[dict[str, Any]] = []
    if summary and summary.get("status") != "product_license_decision_gate_ready" and packet.get("status") == "product_license_decision_packet_ready":
        actions.append(
            _action(
                priority=1,
                lane_id="commercial_product_license",
                action_type="review_product_license_options",
                status="available",
                required_input="product license option packet",
                approval_token=_text(packet.get("approval_token_required")),
                artifact_path=product_license_decision_packet_path,
                recommended_action="Review the license option packet, choose an operator-approved license path, then fill the product license decision intake CSV.",
                command=fill_command_template,
                reason=(
                    f"license_decision_packet_status={_text(packet.get('status'))}, "
                    f"option_count={_int(packet.get('option_count'))}, "
                    f"commercial_gate_only_license_blocked={bool(packet.get('commercial_gate_only_license_blocked') is True)}, "
                    f"legal_advice_provided={bool(packet.get('legal_advice_provided') is True)}."
                ),
            )
        )
        actions.append(
            _action(
                priority=1,
                lane_id="commercial_product_license",
                action_type="fill_product_license_decision",
                status="required",
                required_input="product license decision operator intake CSV",
                approval_token=_text(summary.get("approval_token_required")),
                artifact_path=product_license_decision_gate_path,
                recommended_action="Fill product_license_decision_operator_intake.csv with the exact approval token, SPDX/source, holder, and year before any LICENSE file creation review.",
                command=fill_command_template,
                reason=(
                    f"license_decision_gate_status={_text(summary.get('status')) or 'missing'}, "
                    f"authorized_for_license_file_creation_review={bool(summary.get('authorized_for_license_file_creation_review') is True)}, "
                    f"operator_intake_csv_present={bool(summary.get('operator_intake_csv_present') is True)}, "
                    f"blocker_count={_int(summary.get('blocker_count'))}."
                ),
            )
        )
    work_order = _summary(product_license_file_creation_work_order or {})
    review_fingerprint = _text(work_order.get("license_review_manifest_fingerprint_sha256"))
    if (
        summary.get("status") == "product_license_decision_gate_ready"
        and work_order.get("status") == "product_license_file_creation_work_order_ready"
    ):
        action = _action(
            priority=1,
            lane_id="commercial_product_license",
            action_type="create_product_license_file_from_approved_metadata",
            status="required",
            required_input=_text(work_order.get("license_text_source")),
            approval_token=_text(work_order.get("approval_token_required")),
            artifact_path=product_license_file_creation_work_order_path,
            recommended_action="Create/review the LICENSE file from the approved license metadata, then rerun commercial-independence and release gates.",
            reason=(
                f"license_file_creation_work_order_status={_text(work_order.get('status'))}; "
                f"target_license_path={_text(work_order.get('target_license_path'))}; "
                f"spdx_license_id={_text(work_order.get('spdx_license_id'))}; "
                f"license_review_manifest_fingerprint_sha256={review_fingerprint}; "
                f"license_file_written={bool(work_order.get('license_file_written') is True)}."
            ),
        )
        action["license_review_manifest_fingerprint_sha256"] = review_fingerprint
        actions.append(action)
    return actions


def _product_goal_completion_actions(
    *,
    goal_completion_audit: dict[str, Any],
    goal_completion_audit_path: str,
) -> list[dict[str, Any]]:
    summary = _summary(goal_completion_audit)
    if not summary or summary.get("goal_complete") is True:
        return []
    actions: list[dict[str, Any]] = []
    if summary.get("production_ai_checkpoint_ready") is False and summary.get(
        "production_ai_force_gpu_worker_handoff_ready"
    ) is True:
        gpu_return_intake_path = _text(summary.get("production_ai_gpu_return_intake_artifact_path"))
        artifact_path = goal_completion_audit_path
        if gpu_return_intake_path:
            artifact_path = f"{artifact_path};{gpu_return_intake_path}"
        action = _action(
            priority=0,
            lane_id="product_ai_production",
            action_type="return_gpu_force_regeneration_receipt",
            status="required",
            required_input="GPU full-regeneration summary and manifest with operator verification",
            artifact_path=artifact_path,
            command=_text(summary.get("production_ai_force_gpu_full_regeneration_command")),
            recommended_action=(
                "Run the full regeneration command on a GPU worker, return the identity-locked manifest and summary, "
                "then run the post-return validation chain."
            ),
            reason=(
                f"checkpoint_ready={bool(summary.get('production_ai_checkpoint_ready') is True)}; "
                f"failed_checks={';'.join(str(item) for item in summary.get('production_ai_checkpoint_failed_check_ids') or [])}; "
                f"handoff_ready={bool(summary.get('production_ai_force_gpu_worker_handoff_ready') is True)}; "
                f"operator_action_required={bool(summary.get('production_ai_force_gpu_worker_operator_action_required') is True)}; "
                f"gpu_return_intake_status={_text(summary.get('production_ai_gpu_return_intake_status'))}; "
                f"gpu_return_intake_ready={bool(summary.get('production_ai_gpu_return_intake_ready') is True)}; "
                f"gpu_return_artifacts_ready={bool(summary.get('production_ai_gpu_return_artifacts_ready') is True)}; "
                f"gpu_return_failed_checks={';'.join(str(item) for item in summary.get('production_ai_gpu_return_failed_check_ids') or [])}; "
                f"expected_label_rows={_int(summary.get('production_ai_force_gpu_post_return_min_expected_label_rows'))}; "
                f"promotion_ladder_stages={';'.join(str(item) for item in summary.get('production_ai_force_gpu_post_return_promotion_ladder_stage_ids') or [])}; "
                f"receipt_manifest_identity_rows={_int(summary.get('production_ai_force_gpu_receipt_manifest_identity_row_count'))}; "
                f"receipt_matched_queue_ids={_int(summary.get('production_ai_force_gpu_receipt_matched_queue_id_count'))}; "
                f"receipt_matched_expected_npz={_int(summary.get('production_ai_force_gpu_receipt_matched_expected_npz_count'))}; "
                f"unlock_outputs={';'.join(str(item) for item in summary.get('production_ai_force_gpu_post_return_unlock_output_fields') or [])}."
            ),
        )
        action.update(
            {
                "parallelizable_with_primary_action": False,
                "parallel_primary_action_id": "",
                "parallel_lane_precondition": "",
                "post_return_validation_command": _text(
                    summary.get("production_ai_force_gpu_post_return_validation_command")
                ),
                "gpu_return_intake_artifact_path": gpu_return_intake_path,
                "gpu_return_intake_status": _text(summary.get("production_ai_gpu_return_intake_status")),
                "gpu_return_intake_ready": bool(summary.get("production_ai_gpu_return_intake_ready") is True),
                "gpu_return_artifacts_ready": bool(
                    summary.get("production_ai_gpu_return_artifacts_ready") is True
                ),
                "gpu_return_failed_check_ids": ";".join(
                    str(item) for item in summary.get("production_ai_gpu_return_failed_check_ids") or []
                ),
                "gpu_return_actual_summary_return_path": _text(
                    summary.get("production_ai_gpu_return_actual_summary_return_path")
                ),
                "gpu_return_actual_manifest_return_path": _text(
                    summary.get("production_ai_gpu_return_actual_manifest_return_path")
                ),
                "gpu_return_manifest_template_csv": _text(
                    summary.get("production_ai_gpu_return_manifest_template_csv")
                ),
                "gpu_return_summary_template_csv": _text(
                    summary.get("production_ai_gpu_return_summary_template_csv")
                ),
                "gpu_return_summary_template_payload_json": _text(
                    summary.get("production_ai_gpu_return_summary_template_payload_json")
                ),
                "gpu_return_manifest_operator_verification_placeholder_count": _int(
                    summary.get("production_ai_gpu_return_manifest_operator_verification_placeholder_count")
                ),
                "post_return_unlock_output_fields": ";".join(
                    str(item) for item in summary.get("production_ai_force_gpu_post_return_unlock_output_fields") or []
                ),
                "post_return_min_expected_label_rows": _int(
                    summary.get("production_ai_force_gpu_post_return_min_expected_label_rows")
                ),
                "post_return_promotion_ladder_stage_count": _int(
                    summary.get("production_ai_force_gpu_post_return_promotion_ladder_stage_count")
                ),
                "post_return_promotion_ladder_stage_ids": ";".join(
                    str(item)
                    for item in summary.get("production_ai_force_gpu_post_return_promotion_ladder_stage_ids") or []
                ),
                "post_return_required_production_output_fields": ";".join(
                    str(item)
                    for item in summary.get("production_ai_force_gpu_post_return_required_production_output_fields")
                    or []
                ),
                "post_run_validation_command_count": len(
                    summary.get("production_ai_force_gpu_post_run_validation_commands") or []
                ),
                "receipt_manifest_identity_row_count": _int(
                    summary.get("production_ai_force_gpu_receipt_manifest_identity_row_count")
                ),
                "receipt_matched_queue_id_count": _int(
                    summary.get("production_ai_force_gpu_receipt_matched_queue_id_count")
                ),
                "receipt_matched_expected_npz_count": _int(
                    summary.get("production_ai_force_gpu_receipt_matched_expected_npz_count")
                ),
                "receipt_matched_queue_fingerprint_count": _int(
                    summary.get("production_ai_force_gpu_receipt_matched_queue_fingerprint_count")
                ),
            }
        )
        actions.append(action)
    if summary.get("product_scope_evidence_priority_ready") is True and summary.get(
        "product_scope_general_platform_claim_allowed"
    ) is False:
        action = _action(
            priority=2,
            lane_id="product_scope_expansion",
            action_type="curate_scope_evidence_priority_item",
            status="review_required",
            required_input=_text(summary.get("product_scope_evidence_priority_top_item_id")),
            artifact_path=goal_completion_audit_path,
            recommended_action=_text(summary.get("product_scope_evidence_priority_top_next_step")),
            reason=(
                f"scope_priority_ready=True; "
                f"queue_item_count={_int(summary.get('product_scope_evidence_priority_queue_item_count'))}; "
                f"open_item_count={_int(summary.get('product_scope_evidence_priority_open_item_count'))}; "
                f"local_crosscheck_candidate_count={_int(summary.get('product_scope_evidence_priority_local_crosscheck_candidate_count'))}; "
                f"external_primary_exact_required_count={_int(summary.get('product_scope_evidence_priority_external_primary_exact_required_count'))}; "
                f"intake_ready={bool(summary.get('product_scope_evidence_intake_ready') is True)}; "
                f"local_crosscheck_intake_ready_count={_int(summary.get('product_scope_local_crosscheck_intake_ready_count'))}; "
                f"transporter_manual_review_direct_binding_required_count={_int(summary.get('product_scope_transporter_manual_review_direct_binding_evidence_required_count'))}; "
                f"transporter_manual_review_negative_quantitative_required_count={_int(summary.get('product_scope_transporter_manual_review_negative_quantitative_value_required_count'))}; "
                f"transporter_manual_review_decision_placeholder_count={_int(summary.get('product_scope_transporter_manual_review_decision_placeholder_count'))}; "
                f"transporter_candidate_ready_for_apply_count={_int(summary.get('product_scope_transporter_candidate_ready_for_apply_count'))}; "
                f"pxr_exact_review_intake_ready={bool(summary.get('product_scope_pxr_exact_review_intake_ready') is True)}; "
                f"pxr_exact_review_template_row_count={_int(summary.get('product_scope_pxr_exact_review_template_row_count'))}; "
                f"pxr_exact_review_kcal_placeholder_count={_int(summary.get('product_scope_pxr_exact_review_kcal_placeholder_count'))}; "
                f"pxr_exact_review_conflict_resolution_required_count={_int(summary.get('product_scope_pxr_exact_review_conflict_resolution_required_count'))}; "
                f"top_domain={_text(summary.get('product_scope_evidence_priority_top_domain'))}; "
                f"top_bucket={_text(summary.get('product_scope_evidence_priority_top_bucket'))}."
            ),
        )
        action.update(
            {
                "parallelizable_with_primary_action": bool(actions),
                "parallel_primary_action_id": (
                    f"{_text(actions[0].get('lane_id'))}:{_text(actions[0].get('action_type'))}"
                    if actions
                    else ""
                ),
                "parallel_lane_precondition": (
                    "Can be completed while production GPU environment and force-regeneration receipt "
                    "work proceed; does not require production GPU execution."
                ),
                "scope_priority_top_item_id": _text(summary.get("product_scope_evidence_priority_top_item_id")),
                "scope_priority_top_domain": _text(summary.get("product_scope_evidence_priority_top_domain")),
                "scope_priority_top_bucket": _text(summary.get("product_scope_evidence_priority_top_bucket")),
                "scope_evidence_intake_ready": bool(summary.get("product_scope_evidence_intake_ready") is True),
                "scope_local_crosscheck_intake_ready_count": _int(
                    summary.get("product_scope_local_crosscheck_intake_ready_count")
                ),
                "scope_transporter_manual_review_direct_binding_required_count": _int(
                    summary.get("product_scope_transporter_manual_review_direct_binding_evidence_required_count")
                ),
                "scope_transporter_manual_review_negative_quantitative_required_count": _int(
                    summary.get("product_scope_transporter_manual_review_negative_quantitative_value_required_count")
                ),
                "scope_transporter_manual_review_decision_placeholder_count": _int(
                    summary.get("product_scope_transporter_manual_review_decision_placeholder_count")
                ),
                "scope_transporter_candidate_ready_for_apply_count": _int(
                    summary.get("product_scope_transporter_candidate_ready_for_apply_count")
                ),
                "scope_pxr_exact_review_intake_ready": bool(
                    summary.get("product_scope_pxr_exact_review_intake_ready") is True
                ),
                "scope_pxr_exact_review_template_row_count": _int(
                    summary.get("product_scope_pxr_exact_review_template_row_count")
                ),
                "scope_pxr_exact_review_kcal_placeholder_count": _int(
                    summary.get("product_scope_pxr_exact_review_kcal_placeholder_count")
                ),
                "scope_pxr_exact_review_conflict_resolution_required_count": _int(
                    summary.get("product_scope_pxr_exact_review_conflict_resolution_required_count")
                ),
            }
        )
        actions.append(action)
    scope_receipt_status = _text(summary.get("product_scope_breadth_evidence_receipt_status"))
    raw_scope_receipt_artifact = _text(summary.get("product_scope_breadth_evidence_receipt_artifact"))
    raw_scope_receipt_csv = _text(summary.get("product_scope_breadth_evidence_receipt_csv"))
    scope_receipt_artifact = raw_scope_receipt_artifact or "runs/product_scope_breadth_evidence_receipt_current.json"
    scope_receipt_csv = raw_scope_receipt_csv or DEFAULT_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_CSV
    scope_receipt_present = bool(
        scope_receipt_status
        or raw_scope_receipt_artifact
        or raw_scope_receipt_csv
        or "product_scope_breadth_evidence_receipt_ready" in summary
    )
    if scope_receipt_present and summary.get("product_scope_breadth_evidence_receipt_ready") is not True:
        action = _action(
            priority=2,
            lane_id="product_scope_expansion",
            action_type="resolve_full_scope_breadth_evidence_receipt",
            status="required",
            required_input=scope_receipt_csv,
            approval_token=PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_APPROVAL_TOKEN,
            artifact_path=f"{goal_completion_audit_path};{scope_receipt_artifact};{scope_receipt_csv}",
            recommended_action=(
                "Fill the full-scope evidence receipt rows with local evidence artifacts, reviewer metadata, "
                "license/provenance flags, and the scope-breadth evidence receipt approval token."
            ),
            reason=(
                f"scope_evidence_receipt_status={scope_receipt_status or 'missing'}; "
                f"receipt_ready={bool(summary.get('product_scope_breadth_evidence_receipt_ready') is True)}; "
                f"blocked_row_count={_int(summary.get('product_scope_breadth_evidence_receipt_blocked_row_count'))}; "
                f"blocker_count={_int(summary.get('product_scope_breadth_evidence_receipt_blocker_count'))}; "
                f"required_scope_blocker_count={_int(summary.get('product_scope_breadth_evidence_receipt_required_scope_blocker_count'))}; "
                f"receipt_csv={scope_receipt_csv}."
            ),
        )
        action.update(
            {
                "parallelizable_with_primary_action": bool(actions),
                "parallel_primary_action_id": (
                    f"{_text(actions[0].get('lane_id'))}:{_text(actions[0].get('action_type'))}"
                    if actions
                    else ""
                ),
                "parallel_lane_precondition": (
                    "Can be completed while GPU or engine-refinement evidence work proceeds; it only validates "
                    "operator-provided local full-scope evidence packets."
                ),
                "scope_breadth_evidence_receipt_status": scope_receipt_status,
                "scope_breadth_evidence_receipt_ready": bool(
                    summary.get("product_scope_breadth_evidence_receipt_ready") is True
                ),
                "scope_breadth_evidence_receipt_blocked_row_count": _int(
                    summary.get("product_scope_breadth_evidence_receipt_blocked_row_count")
                ),
                "scope_breadth_evidence_receipt_blocker_count": _int(
                    summary.get("product_scope_breadth_evidence_receipt_blocker_count")
                ),
                "scope_breadth_evidence_receipt_required_scope_blocker_count": _int(
                    summary.get("product_scope_breadth_evidence_receipt_required_scope_blocker_count")
                ),
                "scope_breadth_evidence_receipt_csv": scope_receipt_csv,
                "scope_breadth_evidence_receipt_artifact": scope_receipt_artifact,
            }
        )
        actions.append(action)
    return actions


def _engine_refinement_claim_actions(
    *,
    action_board_rows: list[dict[str, Any]],
    action_board_path: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for row in action_board_rows:
        blocker_id = _text(row.get("blocker_id"))
        if not blocker_id:
            continue
        action = _action(
            priority=2,
            lane_id="product_engine_refinement",
            action_type="resolve_refine_tier_claim_promotion_blocker",
            status="required",
            required_input=blocker_id,
            artifact_path=action_board_path,
            recommended_action=_text(row.get("owner_action")),
            reason=(
                f"current_status={_text(row.get('current_status'))}; "
                f"required_evidence={_text(row.get('required_evidence'))}; "
                f"gate_or_artifact={_text(row.get('gate_or_artifact'))}; "
                f"blocking_signals={_text(row.get('blocking_signals'))}; "
                f"claim_boundary={_text(row.get('claim_boundary'))}."
            ),
        )
        action.update(
            {
                "claim_blocker_id": blocker_id,
                "claim_blocker_current_status": _text(row.get("current_status")),
                "claim_blocker_required_evidence": _text(row.get("required_evidence")),
                "claim_blocker_gate_or_artifact": _text(row.get("gate_or_artifact")),
                "claim_blocker_blocking_signals": _text(row.get("blocking_signals")),
                "claim_blocker_next_required_step": _text(row.get("next_required_step")),
                "claim_blocker_external_dependency": _text(row.get("external_dependency")),
            }
        )
        actions.append(action)
    return actions


def _drilldown_surface_paths(drilldown_packet: dict[str, Any]) -> set[str]:
    summary = _summary(drilldown_packet)
    if summary.get("status") != "large_cleanup_surface_drilldown_ready":
        return set()
    return {_text(row.get("surface_path")) for row in _rows(drilldown_packet) if _text(row.get("surface_path"))}


def _transition_cleanup_actions(
    *,
    preflight: dict[str, Any],
    preflight_path: str,
    large_cleanup_drilldown: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if _summary(preflight).get("status") != "transition_cleanup_execution_preflight_ready":
        return actions
    classified_surfaces = _drilldown_surface_paths(large_cleanup_drilldown or {})
    for row in _rows(preflight):
        work_order_status = _text(row.get("work_order_status"))
        if work_order_status == "approval_gated":
            actions.append(
                _action(
                    priority=5,
                    lane_id="transition_cleanup",
                    action_type="review_cleanup_approval_token",
                    status="approval_required",
                    approval_token=_text(row.get("approval_token")),
                    artifact_path=_text(row.get("path") or preflight_path),
                    recommended_action=_text(row.get("recommended_action")),
                    size_gb=_float(row.get("size_gb")),
                    reason=f"{_text(row.get('lane'))} cleanup row passed preflight and is approval-gated.",
                )
            )
        elif work_order_status == "review_only" and _float(row.get("size_gb")) >= 1.0:
            if _text(row.get("path")) in classified_surfaces:
                continue
            actions.append(
                _action(
                    priority=6,
                    lane_id="transition_cleanup",
                    action_type="review_large_cleanup_surface",
                    status="review_required",
                    artifact_path=_text(row.get("path") or preflight_path),
                    recommended_action=_text(row.get("recommended_action")),
                    size_gb=_float(row.get("size_gb")),
                    reason="Large review-only path needs a narrower cleanup classifier before approval-gated deletion.",
                )
            )
    return actions


def _large_cleanup_review_resolved_count(
    *,
    preflight: dict[str, Any],
    large_cleanup_drilldown: dict[str, Any] | None = None,
) -> int:
    if _summary(preflight).get("status") != "transition_cleanup_execution_preflight_ready":
        return 0
    classified_surfaces = _drilldown_surface_paths(large_cleanup_drilldown or {})
    return sum(
        1
        for row in _rows(preflight)
        if _text(row.get("work_order_status")) == "review_only"
        and _float(row.get("size_gb")) >= 1.0
        and _text(row.get("path")) in classified_surfaces
    )


def _ligand_cleanup_actions(*, preflight: dict[str, Any], preflight_path: str) -> list[dict[str, Any]]:
    summary = _summary(preflight)
    if summary.get("status") != "ligand_heavy_cleanup_execution_preflight_ready":
        return []
    return [
        _action(
            priority=5,
            lane_id="ligand_heavy_cleanup",
            action_type="review_ligand_heavy_cleanup_approval",
            status="approval_required",
            approval_token=_text(summary.get("approval_token_required")),
            artifact_path=preflight_path,
            recommended_action="delete stale stage2 trajectory payload directories after explicit approval",
            size_gb=_float(summary.get("candidate_size_gb")),
            command="execute_after_approval command recorded in ligand-heavy cleanup work order",
            reason=f"{_int(summary.get('existing_candidate_count'))} stale payload directories passed preflight.",
        )
    ]


def _protected_cleanup_policy_actions(
    *,
    protected_deep_review: dict[str, Any],
    protected_policy_gate: dict[str, Any],
    protected_deep_review_path: str,
    protected_policy_gate_path: str,
) -> list[dict[str, Any]]:
    deep = _summary(protected_deep_review)
    gate = _summary(protected_policy_gate)
    if not deep or gate.get("status") == "protected_cleanup_policy_decision_gate_ready":
        return []
    return [
        _action(
            priority=6,
            lane_id="ligand_heavy_cleanup",
            action_type="review_protected_ligand_heavy_policy",
            status="policy_decision_required",
            required_input="protected cleanup policy decision intake CSV",
            artifact_path=f"{protected_deep_review_path};{protected_policy_gate_path}",
            recommended_action="Use the protected ligand-heavy deep review to decide whether each known payload child stays protected or receives an explicit policy-change request.",
            size_gb=_float(deep.get("known_payload_child_size_gb")),
            reason=(
                f"deep_review_status={_text(deep.get('status'))}, "
                f"known_payload_child_count={_int(deep.get('known_payload_child_count'))}, "
                f"known_payload_child_size_gb={round(_float(deep.get('known_payload_child_size_gb')), 3)}, "
                f"preservation_sibling_count={_int(deep.get('preservation_sibling_count'))}, "
                f"policy_gate_status={_text(gate.get('status')) or 'missing'}, "
                f"awaiting_policy_decision_row_count={_int(gate.get('awaiting_policy_decision_row_count'))}."
            ),
        )
    ]


def build_action_board(
    *,
    rollup_packet: dict[str, Any],
    product_preflight_packet: dict[str, Any],
    product_bundle_contract_packet: dict[str, Any],
    product_delivery_evidence_packet: dict[str, Any],
    product_pilot_packet: dict[str, Any] | None = None,
    product_execution_approval_gate_packet: dict[str, Any] | None = None,
    product_license_decision_gate_packet: dict[str, Any] | None = None,
    product_license_decision_packet: dict[str, Any] | None = None,
    product_license_file_creation_work_order_packet: dict[str, Any] | None = None,
    product_release_operations_dossier_packet: dict[str, Any] | None = None,
    product_cli_status_packet: dict[str, Any] | None = None,
    product_goal_completion_audit_packet: dict[str, Any] | None = None,
    goal_release_decision_gate_packet: dict[str, Any] | None = None,
    goal_release_burndown_work_order_packet: dict[str, Any] | None = None,
    cameo_runtime_repair_work_order_packet: dict[str, Any] | None = None,
    cameo_validation_operations_dossier_packet: dict[str, Any] | None = None,
    cameo_cli_status_packet: dict[str, Any] | None = None,
    cameo_official_results_intake_gate_packet: dict[str, Any] | None = None,
    cameo_public_registration_approval_gate_packet: dict[str, Any] | None = None,
    cameo_input_kit_packet: dict[str, Any],
    cameo_input_validation_packet: dict[str, Any],
    cameo_repair_preflight_packet: dict[str, Any],
    transition_cleanup_preflight_packet: dict[str, Any],
    ligand_cleanup_preflight_packet: dict[str, Any],
    large_cleanup_drilldown_packet: dict[str, Any] | None = None,
    protected_cleanup_review_packet: dict[str, Any] | None = None,
    protected_ligand_heavy_deep_review_packet: dict[str, Any] | None = None,
    protected_cleanup_policy_decision_gate_packet: dict[str, Any] | None = None,
    cleanup_cli_status_packet: dict[str, Any] | None = None,
    cleanup_snapshot_preflight_packet: dict[str, Any] | None = None,
    cleanup_payload_manifest_lock_packet: dict[str, Any] | None = None,
    cleanup_postcheck_contract_packet: dict[str, Any] | None = None,
    cleanup_execution_approval_dossier_packet: dict[str, Any] | None = None,
    cleanup_execution_approval_gate_packet: dict[str, Any] | None = None,
    cleanup_completion_gate_packet: dict[str, Any] | None = None,
    goal_operator_intake_kit_packet: dict[str, Any] | None = None,
    engine_refinement_claim_action_board_rows: list[dict[str, Any]] | None = None,
    rollup_path: str = DEFAULT_ROLLUP_JSON,
    product_preflight_path: str = DEFAULT_PRODUCT_PREFLIGHT_JSON,
    product_bundle_contract_path: str = DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON,
    product_delivery_evidence_path: str = DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON,
    product_pilot_packet_path: str = DEFAULT_PRODUCT_PILOT_PACKET_JSON,
    product_execution_approval_gate_path: str = DEFAULT_PRODUCT_EXECUTION_APPROVAL_GATE_JSON,
    product_license_decision_gate_path: str = DEFAULT_PRODUCT_LICENSE_DECISION_GATE_JSON,
    product_license_decision_packet_path: str = DEFAULT_PRODUCT_LICENSE_DECISION_PACKET_JSON,
    product_license_file_creation_work_order_path: str = DEFAULT_PRODUCT_LICENSE_FILE_CREATION_WORK_ORDER_JSON,
    product_release_operations_dossier_path: str = DEFAULT_PRODUCT_RELEASE_OPERATIONS_DOSSIER_JSON,
    product_goal_completion_audit_path: str = DEFAULT_PRODUCT_GOAL_COMPLETION_AUDIT_JSON,
    goal_release_decision_gate_path: str = DEFAULT_GOAL_RELEASE_DECISION_GATE_JSON,
    goal_release_burndown_work_order_path: str = DEFAULT_GOAL_RELEASE_BURNDOWN_WORK_ORDER_JSON,
    cameo_runtime_repair_work_order_path: str = DEFAULT_CAMEO_RUNTIME_REPAIR_WORK_ORDER_JSON,
    cameo_validation_operations_dossier_path: str = DEFAULT_CAMEO_VALIDATION_OPERATIONS_DOSSIER_JSON,
    cameo_official_results_intake_gate_path: str = DEFAULT_CAMEO_OFFICIAL_RESULTS_INTAKE_GATE_JSON,
    cameo_public_registration_approval_gate_path: str = DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON,
    cameo_input_kit_path: str = DEFAULT_CAMEO_INPUT_KIT_JSON,
    cameo_input_validation_path: str = DEFAULT_CAMEO_INPUT_VALIDATION_JSON,
    cameo_repair_preflight_path: str = DEFAULT_CAMEO_REPAIR_PREFLIGHT_JSON,
    transition_cleanup_preflight_path: str = DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON,
    ligand_cleanup_preflight_path: str = DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON,
    large_cleanup_drilldown_path: str = DEFAULT_LARGE_CLEANUP_DRILLDOWN_JSON,
    protected_cleanup_review_path: str = DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON,
    protected_ligand_heavy_deep_review_path: str = DEFAULT_PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_JSON,
    protected_cleanup_policy_decision_gate_path: str = DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON,
    cleanup_snapshot_preflight_path: str = DEFAULT_CLEANUP_SNAPSHOT_PREFLIGHT_JSON,
    cleanup_payload_manifest_lock_path: str = DEFAULT_CLEANUP_PAYLOAD_MANIFEST_LOCK_JSON,
    cleanup_postcheck_contract_path: str = DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON,
    cleanup_execution_approval_dossier_path: str = DEFAULT_CLEANUP_EXECUTION_APPROVAL_DOSSIER_JSON,
    cleanup_execution_approval_gate_path: str = DEFAULT_CLEANUP_EXECUTION_APPROVAL_GATE_JSON,
    cleanup_completion_gate_path: str = DEFAULT_CLEANUP_COMPLETION_GATE_JSON,
    goal_operator_intake_kit_path: str = DEFAULT_GOAL_OPERATOR_INTAKE_KIT_JSON,
    engine_refinement_claim_action_board_path: str = DEFAULT_ENGINE_REFINEMENT_CLAIM_ACTION_BOARD_CSV,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    cleanup_completion_gate_packet = cleanup_completion_gate_packet or {}
    cleanup_completion = _summary(cleanup_completion_gate_packet)
    cleanup_complete = (
        _text(cleanup_completion.get("status")) == "cleanup_completion_gate_ready"
        and bool(cleanup_completion.get("cleanup_complete") is True)
        and _int(cleanup_completion.get("blocked_stage_count")) == 0
    )
    rows.extend(
        _product_goal_completion_actions(
            goal_completion_audit=product_goal_completion_audit_packet or {},
            goal_completion_audit_path=product_goal_completion_audit_path,
        )
    )
    rows.extend(
        _engine_refinement_claim_actions(
            action_board_rows=engine_refinement_claim_action_board_rows or [],
            action_board_path=engine_refinement_claim_action_board_path,
        )
    )
    rows.extend(
        _cameo_actions(
            input_kit=cameo_input_kit_packet,
            input_validation=cameo_input_validation_packet,
            repair_preflight=cameo_repair_preflight_packet,
            input_kit_path=cameo_input_kit_path,
            input_validation_path=cameo_input_validation_path,
            repair_preflight_path=cameo_repair_preflight_path,
        )
    )
    rows.extend(
        _cameo_receiver_smoke_actions(
            rollup_packet=rollup_packet,
            rollup_path=rollup_path,
            runtime_repair_work_order=cameo_runtime_repair_work_order_packet or {},
            runtime_repair_work_order_path=cameo_runtime_repair_work_order_path,
        )
    )
    rows.extend(
        _cameo_official_results_actions(
            official_results_intake_gate=cameo_official_results_intake_gate_packet or {},
            official_results_intake_gate_path=cameo_official_results_intake_gate_path,
        )
    )
    rows.extend(
        _product_actions(
            product_preflight=product_preflight_packet,
            bundle_contract=product_bundle_contract_packet,
            delivery_evidence=product_delivery_evidence_packet,
            pilot_packet=product_pilot_packet or {},
            product_preflight_path=product_preflight_path,
            bundle_contract_path=product_bundle_contract_path,
            delivery_evidence_path=product_delivery_evidence_path,
            pilot_packet_path=product_pilot_packet_path,
        )
    )
    rows.extend(
        _product_license_actions(
            product_license_decision_gate=product_license_decision_gate_packet or {},
            product_license_decision_packet=product_license_decision_packet or {},
            product_license_file_creation_work_order=product_license_file_creation_work_order_packet or {},
            product_license_decision_gate_path=product_license_decision_gate_path,
            product_license_decision_packet_path=product_license_decision_packet_path,
            product_license_file_creation_work_order_path=product_license_file_creation_work_order_path,
        )
    )
    if not cleanup_complete:
        rows.extend(
            _transition_cleanup_actions(
                preflight=transition_cleanup_preflight_packet,
                preflight_path=transition_cleanup_preflight_path,
                large_cleanup_drilldown=large_cleanup_drilldown_packet or {},
            )
        )
        rows.extend(_ligand_cleanup_actions(preflight=ligand_cleanup_preflight_packet, preflight_path=ligand_cleanup_preflight_path))
        rows.extend(
            _protected_cleanup_policy_actions(
                protected_deep_review=protected_ligand_heavy_deep_review_packet or {},
                protected_policy_gate=protected_cleanup_policy_decision_gate_packet or {},
                protected_deep_review_path=protected_ligand_heavy_deep_review_path,
                protected_policy_gate_path=protected_cleanup_policy_decision_gate_path,
            )
        )
    rows.sort(key=lambda row: (row["priority"], row["lane_id"], row["action_type"], row["artifact_path"]))

    primary_action = _primary_action(rows)
    approval_count = sum(1 for row in rows if row["status"] == "approval_required")
    blocked_count = sum(1 for row in rows if row["status"] in {"blocked", "required"})
    review_count = sum(1 for row in rows if row["status"] == "review_required")
    operator_input_required_count = blocked_count + review_count
    large_cleanup_drilldown_packet = large_cleanup_drilldown_packet or {}
    drilldown = _summary(large_cleanup_drilldown_packet)
    large_cleanup_review_resolved_by_drilldown_count = _large_cleanup_review_resolved_count(
        preflight=transition_cleanup_preflight_packet,
        large_cleanup_drilldown=large_cleanup_drilldown_packet,
    )
    protected_cleanup_review_packet = protected_cleanup_review_packet or {}
    protected_review = _summary(protected_cleanup_review_packet)
    protected_ligand_heavy_deep_review_packet = protected_ligand_heavy_deep_review_packet or {}
    protected_deep = _summary(protected_ligand_heavy_deep_review_packet)
    protected_cleanup_policy_decision_gate_packet = protected_cleanup_policy_decision_gate_packet or {}
    protected_policy_gate = _summary(protected_cleanup_policy_decision_gate_packet)
    cleanup_cli_status = cleanup_cli_status_packet or {}
    cleanup_snapshot_preflight_packet = cleanup_snapshot_preflight_packet or {}
    cleanup_snapshot = _summary(cleanup_snapshot_preflight_packet)
    cleanup_payload_manifest_lock_packet = cleanup_payload_manifest_lock_packet or {}
    cleanup_payload_lock = _summary(cleanup_payload_manifest_lock_packet)
    cleanup_postcheck_contract_packet = cleanup_postcheck_contract_packet or {}
    cleanup_postcheck = _summary(cleanup_postcheck_contract_packet)
    cleanup_execution_approval_dossier_packet = cleanup_execution_approval_dossier_packet or {}
    cleanup_approval_dossier = _summary(cleanup_execution_approval_dossier_packet)
    cleanup_execution_approval_gate_packet = cleanup_execution_approval_gate_packet or {}
    cleanup_approval_gate = _summary(cleanup_execution_approval_gate_packet)
    goal_operator_intake_kit_packet = goal_operator_intake_kit_packet or {}
    operator_intake_kit = _summary(goal_operator_intake_kit_packet)
    goal_release_decision_gate_packet = goal_release_decision_gate_packet or {}
    release_gate = _summary(goal_release_decision_gate_packet)
    goal_release_burndown_work_order_packet = goal_release_burndown_work_order_packet or {}
    release_burndown = _summary(goal_release_burndown_work_order_packet)
    runtime_repair = _summary(cameo_runtime_repair_work_order_packet or {})
    cameo_operations_dossier = _summary(cameo_validation_operations_dossier_packet or {})
    cameo_runtime_ready = (
        _text(cameo_operations_dossier.get("api_dependency_status")) == "cameo_api_dependency_ready"
        and _text(cameo_operations_dossier.get("receiver_smoke_status")) == "cameo_receiver_smoke_ready"
    )
    effective_runtime_install_approval_required = (
        False if cameo_runtime_ready else bool(runtime_repair.get("install_approval_required") is True)
    )
    effective_runtime_approval_token_required = "" if cameo_runtime_ready else _text(runtime_repair.get("approval_token_required"))
    effective_runtime_repair_command_count = 0 if cameo_runtime_ready else _int(runtime_repair.get("command_count"))
    cameo_cli_status = cameo_cli_status_packet or {}
    cameo_official_results_gate = _summary(cameo_official_results_intake_gate_packet or {})
    cameo_registration_gate = _summary(cameo_public_registration_approval_gate_packet or {})
    pilot = _summary(product_pilot_packet or {})
    product_approval_gate = _summary(product_execution_approval_gate_packet or {})
    product_license_gate = _summary(product_license_decision_gate_packet or {})
    product_license_packet = _summary(product_license_decision_packet or {})
    product_license_file_creation_work_order = _summary(product_license_file_creation_work_order_packet or {})
    product_release_dossier = _summary(product_release_operations_dossier_packet or {})
    product_cli_status = product_cli_status_packet or {}
    product_goal_completion_audit = _summary(product_goal_completion_audit_packet or {})
    parallel_product_actions = [
        row
        for row in rows
        if row.get("parallelizable_with_primary_action") is True
        and _text(row.get("lane_id")) in {"product_scope_expansion"}
    ]
    parallel_product_actions = sorted(
        parallel_product_actions,
        key=lambda row: (_int(row.get("priority")), _text(row.get("lane_id")), _text(row.get("action_type"))),
    )
    first_parallel_product_action = parallel_product_actions[0] if parallel_product_actions else {}
    summary = {
        "packet_type": "goal_operator_action_board",
        "status": "operator_actions_required" if rows else "goal_operator_actions_clear",
        "source_rollup_status": _text(_summary(rollup_packet).get("status")),
        "action_count": len(rows),
        "blocked_or_required_action_count": blocked_count,
        "approval_required_count": approval_count,
        "review_required_count": review_count,
        "operator_input_required_count": operator_input_required_count,
        "primary_action_priority": _int(primary_action.get("priority")),
        "primary_action_lane_id": _text(primary_action.get("lane_id")),
        "primary_action_type": _text(primary_action.get("action_type")),
        "primary_action_status": _text(primary_action.get("status")),
        "primary_action_required_input": _text(primary_action.get("required_input")),
        "primary_action_artifact_path": _text(primary_action.get("artifact_path")),
        "primary_action_command": _text(primary_action.get("command")),
        "primary_action_recommended_action": _text(primary_action.get("recommended_action")),
        "top_action_id": (
            f"{_text(primary_action.get('lane_id'))}:{_text(primary_action.get('action_type'))}"
            if primary_action
            else ""
        ),
        "primary_action_id": (
            f"{_text(primary_action.get('lane_id'))}:{_text(primary_action.get('action_type'))}"
            if primary_action
            else ""
        ),
        "product_ai_production_action_count": sum(1 for row in rows if row["lane_id"] == "product_ai_production"),
        "product_scope_expansion_action_count": sum(1 for row in rows if row["lane_id"] == "product_scope_expansion"),
        "product_engine_refinement_action_count": sum(
            1 for row in rows if row["lane_id"] == "product_engine_refinement"
        ),
        "product_engine_refinement_action_board_csv": (
            engine_refinement_claim_action_board_path
            if engine_refinement_claim_action_board_rows
            else ""
        ),
        "product_engine_refinement_claim_blocker_count": len(engine_refinement_claim_action_board_rows or []),
        "parallel_product_action_count": len(parallel_product_actions),
        "parallel_product_action_ids": [
            f"{_text(row.get('lane_id'))}:{_text(row.get('action_type'))}"
            for row in parallel_product_actions
        ],
        "first_parallel_product_action_id": (
            f"{_text(first_parallel_product_action.get('lane_id'))}:"
            f"{_text(first_parallel_product_action.get('action_type'))}"
            if first_parallel_product_action
            else ""
        ),
        "first_parallel_product_action_lane_id": _text(first_parallel_product_action.get("lane_id")),
        "first_parallel_product_action_type": _text(first_parallel_product_action.get("action_type")),
        "first_parallel_product_action_required_input": _text(
            first_parallel_product_action.get("required_input")
        ),
        "first_parallel_product_action_artifact_path": _text(
            first_parallel_product_action.get("artifact_path")
        ),
        "first_parallel_product_action_recommended_action": _text(
            first_parallel_product_action.get("recommended_action")
        ),
        "first_parallel_product_action_primary_action_id": _text(
            first_parallel_product_action.get("parallel_primary_action_id")
        ),
        "first_parallel_product_action_precondition": _text(
            first_parallel_product_action.get("parallel_lane_precondition")
        ),
        "product_goal_completion_audit_status": _text(product_goal_completion_audit.get("status")),
        "product_goal_complete": bool(product_goal_completion_audit.get("goal_complete") is True),
        "product_goal_primary_bottleneck_kind": _text(product_goal_completion_audit.get("primary_bottleneck_kind")),
        "product_goal_engine_refinement_claim_promotion_ready": bool(
            product_goal_completion_audit.get("engine_refinement_claim_promotion_ready") is True
        ),
        "product_goal_engine_refinement_claim_promotion_blocker_count": _int(
            product_goal_completion_audit.get("engine_refinement_claim_promotion_blocker_count")
        ),
        "product_goal_engine_refinement_claim_promotion_action_row_count": _int(
            product_goal_completion_audit.get("engine_refinement_claim_promotion_action_row_count")
        ),
        "product_goal_engine_refinement_claim_promotion_blockers": [
            str(item)
            for item in (
                product_goal_completion_audit.get("engine_refinement_claim_promotion_blockers")
                or []
            )
        ],
        "product_goal_engine_refinement_claim_promotion_action_board_csv": _text(
            product_goal_completion_audit.get("engine_refinement_claim_promotion_action_board_csv")
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_ready": bool(
            product_goal_completion_audit.get("engine_refinement_claim_evidence_receipt_ready") is True
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_blocked_row_count": _int(
            product_goal_completion_audit.get("engine_refinement_claim_evidence_receipt_blocked_row_count")
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_artifact": _text(
            product_goal_completion_audit.get("engine_refinement_claim_evidence_receipt_artifact")
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_csv": _text(
            product_goal_completion_audit.get("engine_refinement_claim_evidence_receipt_csv")
        ),
        "product_goal_engine_refinement_claim_promotion_next_required_step": _text(
            product_goal_completion_audit.get("engine_refinement_claim_promotion_next_required_step")
        ),
        "product_goal_production_ai_checkpoint_ready": bool(
            product_goal_completion_audit.get("production_ai_checkpoint_ready") is True
        ),
        "product_goal_production_ai_gpu_handoff_ready": bool(
            product_goal_completion_audit.get("production_ai_force_gpu_worker_handoff_ready") is True
        ),
        "product_goal_scope_priority_ready": bool(
            product_goal_completion_audit.get("product_scope_evidence_priority_ready") is True
        ),
        "product_goal_scope_breadth_evidence_receipt_status": _text(
            product_goal_completion_audit.get("product_scope_breadth_evidence_receipt_status")
        ),
        "product_goal_scope_breadth_evidence_receipt_ready": bool(
            product_goal_completion_audit.get("product_scope_breadth_evidence_receipt_ready") is True
        ),
        "product_goal_scope_breadth_evidence_receipt_blocked_row_count": _int(
            product_goal_completion_audit.get("product_scope_breadth_evidence_receipt_blocked_row_count")
        ),
        "product_goal_scope_breadth_evidence_receipt_artifact": _text(
            product_goal_completion_audit.get("product_scope_breadth_evidence_receipt_artifact")
        ),
        "product_goal_scope_breadth_evidence_receipt_csv": _text(
            product_goal_completion_audit.get("product_scope_breadth_evidence_receipt_csv")
        ),
        "product_goal_scope_priority_top_item_id": _text(
            product_goal_completion_audit.get("product_scope_evidence_priority_top_item_id")
        ),
        "approval_reclaim_size_gb": round(sum(_float(row.get("size_gb")) for row in rows if row["status"] == "approval_required"), 3),
        "large_review_size_gb": round(sum(_float(row.get("size_gb")) for row in rows if row["status"] == "review_required"), 3),
        "large_cleanup_review_resolved_by_drilldown_count": large_cleanup_review_resolved_by_drilldown_count,
        "large_cleanup_drilldown_status": _text(drilldown.get("status")),
        "large_cleanup_known_payload_size_gb": round(_float(drilldown.get("known_payload_total_size_gb")), 3),
        "large_cleanup_dry_run_delete_payload_size_gb": round(_float(drilldown.get("dry_run_delete_payload_size_gb")), 3),
        "large_cleanup_dry_run_protected_payload_size_gb": round(_float(drilldown.get("dry_run_protected_payload_size_gb")), 3),
        "large_cleanup_drilldown_json": large_cleanup_drilldown_path if large_cleanup_drilldown_packet else "",
        "protected_cleanup_review_status": _text(protected_review.get("status")),
        "protected_cleanup_payload_size_gb": round(_float(protected_review.get("protected_payload_size_gb")), 3),
        "protected_cleanup_policy_change_required_count": _int(protected_review.get("policy_change_required_count")),
        "protected_cleanup_approval_promoted_count": _int(protected_review.get("approval_promoted_count")),
        "protected_cleanup_review_json": protected_cleanup_review_path if protected_cleanup_review_packet else "",
        "protected_ligand_heavy_deep_review_status": _text(protected_deep.get("status")),
        "protected_ligand_heavy_known_payload_child_count": _int(protected_deep.get("known_payload_child_count")),
        "protected_ligand_heavy_known_payload_child_size_gb": round(_float(protected_deep.get("known_payload_child_size_gb")), 3),
        "protected_ligand_heavy_preservation_sibling_count": _int(protected_deep.get("preservation_sibling_count")),
        "protected_ligand_heavy_policy_change_required_for_deletion_count": _int(
            protected_deep.get("policy_change_required_for_deletion_count")
        ),
        "protected_ligand_heavy_deep_review_json": (
            protected_ligand_heavy_deep_review_path if protected_ligand_heavy_deep_review_packet else ""
        ),
        "protected_cleanup_policy_decision_gate_status": _text(protected_policy_gate.get("status")),
        "protected_cleanup_policy_resolved": bool(protected_policy_gate.get("policy_resolved") is True),
        "protected_cleanup_policy_awaiting_decision_row_count": _int(protected_policy_gate.get("awaiting_policy_decision_row_count")),
        "protected_cleanup_policy_change_requested_row_count": _int(protected_policy_gate.get("policy_change_requested_row_count")),
        "protected_cleanup_policy_decision_blocked_row_count": _int(protected_policy_gate.get("blocked_row_count")),
        "protected_cleanup_policy_decision_gate_json": protected_cleanup_policy_decision_gate_path if protected_cleanup_policy_decision_gate_packet else "",
        "cleanup_cli_status_set_status": _text(cleanup_cli_status.get("status")),
        "cleanup_cli_command_count": _int(cleanup_cli_status.get("command_count")),
        "cleanup_cli_blocked_or_missing_command_count": _int(cleanup_cli_status.get("blocked_or_missing_command_count")),
        "cleanup_cli_approval_required_command_count": _int(cleanup_cli_status.get("approval_required_command_count")),
        "cleanup_cli_approval_token_count": _int(cleanup_cli_status.get("approval_token_count")),
        "cleanup_cli_approval_tokens_required": list(cleanup_cli_status.get("approval_tokens_required") or []),
        "cleanup_cli_approval_reclaim_size_gb": round(_float(cleanup_cli_status.get("approval_reclaim_size_gb")), 3),
        "cleanup_cli_authorized_reclaim_size_gb": round(_float(cleanup_cli_status.get("authorized_reclaim_size_gb")), 3),
        "cleanup_cli_awaiting_operator_approval_row_count": _int(cleanup_cli_status.get("awaiting_operator_approval_row_count")),
        "cleanup_cli_postcheck_contract_ready": bool(cleanup_cli_status.get("postcheck_contract_ready") is True),
        "cleanup_cli_postcheck_row_count": _int(cleanup_cli_status.get("postcheck_row_count")),
        "cleanup_cli_postcheck_blocked_row_count": _int(cleanup_cli_status.get("postcheck_blocked_row_count")),
        "cleanup_cli_protected_payload_size_gb": round(_float(cleanup_cli_status.get("protected_payload_size_gb")), 3),
        "cleanup_cli_protected_policy_change_required_count": _int(
            cleanup_cli_status.get("protected_policy_change_required_count")
        ),
        "cleanup_cli_protected_policy_resolved": bool(cleanup_cli_status.get("protected_policy_resolved") is True),
        "cleanup_snapshot_preflight_status": _text(cleanup_snapshot.get("status")),
        "cleanup_snapshot_blocked_row_count": _int(cleanup_snapshot.get("blocked_row_count")),
        "cleanup_snapshot_missing_count": _int(cleanup_snapshot.get("snapshot_missing_count")),
        "cleanup_snapshot_required_count": _int(cleanup_snapshot.get("snapshot_required_count")),
        "cleanup_snapshot_approval_gated_size_gb": round(_float(cleanup_snapshot.get("approval_gated_size_gb")), 3),
        "cleanup_snapshot_preflight_json": cleanup_snapshot_preflight_path if cleanup_snapshot_preflight_packet else "",
        "cleanup_payload_manifest_lock_status": _text(cleanup_payload_lock.get("status")),
        "cleanup_payload_manifest_lock_row_count": _int(cleanup_payload_lock.get("row_count")),
        "cleanup_payload_manifest_lock_blocked_row_count": _int(cleanup_payload_lock.get("blocked_row_count")),
        "cleanup_payload_manifest_fingerprint_sha256": _text(cleanup_payload_lock.get("payload_manifest_fingerprint_sha256")),
        "cleanup_payload_manifest_lock_json": cleanup_payload_manifest_lock_path if cleanup_payload_manifest_lock_packet else "",
        "cleanup_postcheck_contract_status": _text(cleanup_postcheck.get("status")),
        "cleanup_postcheck_contract_ready": bool(cleanup_postcheck.get("postcheck_contract_ready") is True),
        "cleanup_postcheck_row_count": _int(cleanup_postcheck.get("row_count")),
        "cleanup_postcheck_approval_row_count": _int(cleanup_postcheck.get("approval_row_count")),
        "cleanup_postcheck_protected_policy_row_count": _int(cleanup_postcheck.get("protected_policy_row_count")),
        "cleanup_postcheck_blocked_row_count": _int(cleanup_postcheck.get("blocked_row_count")),
        "cleanup_postcheck_global_refresh_command_count": _int(cleanup_postcheck.get("global_refresh_command_count")),
        "cleanup_postcheck_contract_json": cleanup_postcheck_contract_path if cleanup_postcheck_contract_packet else "",
        "cleanup_execution_approval_dossier_status": _text(cleanup_approval_dossier.get("status")),
        "cleanup_execution_approval_dossier_approval_row_count": _int(cleanup_approval_dossier.get("approval_row_count")),
        "cleanup_execution_approval_dossier_snapshot_backed_approval_row_count": _int(
            cleanup_approval_dossier.get("snapshot_backed_approval_row_count")
        ),
        "cleanup_execution_approval_dossier_snapshot_artifact_count": _int(cleanup_approval_dossier.get("snapshot_artifact_count")),
        "cleanup_execution_approval_dossier_snapshot_ready_count": _int(cleanup_approval_dossier.get("snapshot_ready_count")),
        "cleanup_execution_approval_dossier_snapshot_listing_truncated_count": _int(
            cleanup_approval_dossier.get("snapshot_listing_truncated_count")
        ),
        "cleanup_execution_approval_dossier_snapshot_total_entry_count": _int(
            cleanup_approval_dossier.get("snapshot_total_entry_count")
        ),
        "cleanup_execution_approval_dossier_snapshot_set_fingerprint_sha256": _text(
            cleanup_approval_dossier.get("snapshot_set_fingerprint_sha256")
        ),
        "cleanup_execution_approval_dossier_json": (
            cleanup_execution_approval_dossier_path if cleanup_execution_approval_dossier_packet else ""
        ),
        "cleanup_execution_approval_gate_status": _text(cleanup_approval_gate.get("status")),
        "cleanup_execution_authorized_row_count": _int(cleanup_approval_gate.get("authorized_row_count")),
        "cleanup_execution_awaiting_operator_approval_row_count": _int(cleanup_approval_gate.get("awaiting_operator_approval_row_count")),
        "cleanup_execution_blocked_row_count": _int(cleanup_approval_gate.get("blocked_row_count")),
        "cleanup_execution_authorized_reclaim_size_gb": round(_float(cleanup_approval_gate.get("authorized_reclaim_size_gb")), 3),
        "cleanup_execution_total_reclaim_size_gb": round(_float(cleanup_approval_gate.get("total_reclaim_size_gb")), 3),
        "cleanup_execution_operator_approval_csv_present": bool(cleanup_approval_gate.get("operator_approval_csv_present") is True),
        "cleanup_execution_approval_gate_json": cleanup_execution_approval_gate_path if cleanup_execution_approval_gate_packet else "",
        "cleanup_completion_gate_status": _text(cleanup_completion.get("status")),
        "cleanup_completion_complete": bool(cleanup_completion.get("cleanup_complete") is True),
        "cleanup_completion_blocked_stage_count": _int(cleanup_completion.get("blocked_stage_count")),
        "cleanup_completion_approval_ready": bool(cleanup_completion.get("approval_ready") is True),
        "cleanup_completion_transition_cleanup_complete": bool(cleanup_completion.get("transition_cleanup_complete") is True),
        "cleanup_completion_ligand_heavy_cleanup_complete": bool(cleanup_completion.get("ligand_heavy_cleanup_complete") is True),
        "cleanup_completion_protected_policy_resolved": bool(cleanup_completion.get("protected_policy_resolved") is True),
        "cleanup_completion_gate_json": cleanup_completion_gate_path if cleanup_completion_gate_packet else "",
        "goal_release_decision_gate_status": _text(release_gate.get("status")),
        "goal_release_allowed": bool(release_gate.get("release_allowed") is True),
        "goal_release_blocker_count": _int(release_gate.get("blocker_count")),
        "goal_release_check_count": _int(release_gate.get("check_count")),
        "commercial_independent_product_ready": bool(release_gate.get("commercial_independent_product_ready") is True),
        "cameo_architecture_validation_ready": bool(release_gate.get("cameo_architecture_validation_ready") is True),
        "cleanup_objective_ready": bool(release_gate.get("cleanup_objective_ready") is True),
        "source_goal_api_surface_contract_status": _text(release_gate.get("source_goal_api_surface_contract_status")),
        "goal_api_surface_ready": bool(release_gate.get("goal_api_surface_ready") is True),
        "goal_api_surface_check_count": _int(release_gate.get("goal_api_surface_check_count")),
        "goal_api_surface_blocker_count": _int(release_gate.get("goal_api_surface_blocker_count")),
        "goal_api_surface_missing_endpoint_count": _int(release_gate.get("goal_api_surface_missing_endpoint_count")),
        "goal_api_surface_missing_status_key_count": _int(release_gate.get("goal_api_surface_missing_status_key_count")),
        "goal_release_decision_gate_json": goal_release_decision_gate_path if goal_release_decision_gate_packet else "",
        "goal_release_burndown_work_order_status": _text(release_burndown.get("status")),
        "goal_release_burndown_release_blocker_check_count": _int(release_burndown.get("release_blocker_check_count")),
        "goal_release_burndown_work_item_count": _int(release_burndown.get("work_item_count")),
        "goal_release_burndown_approval_required_item_count": _int(release_burndown.get("approval_required_item_count")),
        "goal_release_burndown_operator_input_required_item_count": _int(
            release_burndown.get("operator_input_required_item_count")
        ),
        "goal_release_burndown_operator_input_required_work_item_count": _int(
            release_burndown.get("burndown_operator_input_required_work_item_count")
        ),
        "goal_release_burndown_official_results_required_item_count": _int(
            release_burndown.get("official_results_required_item_count")
        ),
        "goal_release_burndown_policy_decision_required_item_count": _int(release_burndown.get("policy_decision_required_item_count")),
        "goal_release_burndown_postcheck_required_item_count": _int(release_burndown.get("postcheck_required_item_count")),
        "goal_release_burndown_approval_token_count": _int(release_burndown.get("approval_token_count")),
        "goal_release_burndown_work_order_json": goal_release_burndown_work_order_path if goal_release_burndown_work_order_packet else "",
        "goal_operator_intake_kit_status": _text(operator_intake_kit.get("status")),
        "goal_operator_intake_kit_entry_count": _int(operator_intake_kit.get("entry_count")),
        "goal_operator_intake_kit_release_burndown_linked_entry_count": _int(
            operator_intake_kit.get("release_burndown_linked_entry_count")
        ),
        "goal_operator_intake_kit_operator_input_required_count": _int(operator_intake_kit.get("operator_input_required_count")),
        "goal_operator_intake_kit_current_action_required_count": _int(
            operator_intake_kit.get("current_action_required_count")
        ),
        "goal_operator_intake_kit_deferred_operator_input_count": _int(
            operator_intake_kit.get("deferred_operator_input_count")
        ),
        "goal_operator_intake_kit_template_copied_count": _int(operator_intake_kit.get("template_copied_count")),
        "goal_operator_intake_kit_template_missing_count": _int(operator_intake_kit.get("template_missing_count")),
        "goal_operator_intake_kit_approval_token_count": _int(operator_intake_kit.get("approval_token_count")),
        "goal_operator_intake_kit_current_action_approval_token_count": _int(
            operator_intake_kit.get("current_action_approval_token_count")
        ),
        "goal_operator_intake_kit_current_action_approval_tokens": list(
            operator_intake_kit.get("current_action_approval_tokens") or []
        ),
        "goal_operator_intake_kit_product_commercial_independence_status": _text(
            operator_intake_kit.get("product_commercial_independence_status")
        ),
        "goal_operator_intake_kit_product_commercial_independent_claim_allowed": bool(
            operator_intake_kit.get("product_commercial_independent_claim_allowed") is True
        ),
        "goal_operator_intake_kit_product_commercial_independence_blocker_count": _int(
            operator_intake_kit.get("product_commercial_independence_blocker_count")
        ),
        "goal_operator_intake_kit_product_commercial_independence_license_present": bool(
            operator_intake_kit.get("product_commercial_independence_license_present") is True
        ),
        "goal_operator_intake_kit_goal_api_surface_contract_status": _text(
            operator_intake_kit.get("goal_api_surface_contract_status")
        ),
        "goal_operator_intake_kit_goal_api_surface_ready": bool(operator_intake_kit.get("goal_api_surface_ready") is True),
        "goal_operator_intake_kit_goal_api_surface_check_count": _int(operator_intake_kit.get("goal_api_surface_check_count")),
        "goal_operator_intake_kit_goal_api_surface_blocker_count": _int(
            operator_intake_kit.get("goal_api_surface_blocker_count")
        ),
        "goal_operator_intake_kit_goal_api_status_endpoint": _text(operator_intake_kit.get("goal_api_status_endpoint")),
        "goal_operator_intake_kit_goal_api_contract_endpoint": _text(operator_intake_kit.get("goal_api_contract_endpoint")),
        "goal_operator_intake_kit_json": goal_operator_intake_kit_path if goal_operator_intake_kit_packet else "",
        "cameo_runtime_repair_work_order_status": _text(runtime_repair.get("status")),
        "cameo_runtime_install_approval_required": effective_runtime_install_approval_required,
        "cameo_runtime_approval_token_required": effective_runtime_approval_token_required,
        "cameo_runtime_repair_command_count": effective_runtime_repair_command_count,
        "cameo_runtime_repair_work_order_json": cameo_runtime_repair_work_order_path if cameo_runtime_repair_work_order_packet else "",
        "cameo_validation_operations_dossier_status": _text(cameo_operations_dossier.get("status")),
        "cameo_validation_operations_blocked_stage_count": _int(cameo_operations_dossier.get("blocked_stage_count")),
        "cameo_validation_operations_approval_required_stage_count": _int(cameo_operations_dossier.get("approval_required_stage_count")),
        "cameo_validation_operations_operator_input_required_count": _int(cameo_operations_dossier.get("operator_input_required_count")),
        "cameo_validation_operations_approval_token_count": _int(cameo_operations_dossier.get("approval_token_count")),
        "cameo_validation_operations_official_result_required": bool(cameo_operations_dossier.get("official_result_required") is True),
        "cameo_validation_operations_evidence_integrity_status": _text(cameo_operations_dossier.get("evidence_integrity_status")),
        "cameo_validation_operations_evidence_integrity_ready": bool(
            cameo_operations_dossier.get("evidence_integrity_ready") is True
        ),
        "cameo_validation_operations_evidence_integrity_blocker_count": _int(
            cameo_operations_dossier.get("evidence_integrity_blocker_count")
        ),
        "cameo_validation_operations_official_results_pending_honest": bool(
            cameo_operations_dossier.get("official_results_pending_honest") is True
        ),
        "cameo_validation_operations_no_local_native_accuracy_substitution": bool(
            cameo_operations_dossier.get("no_local_native_accuracy_substitution") is True
        ),
        "cameo_validation_operations_evidence_integrity_artifact": "runs/cameo_evidence_integrity_contract_current.json"
        if cameo_validation_operations_dossier_packet
        else "",
        "cameo_validation_operations_official_results_intake_status": _text(cameo_operations_dossier.get("official_results_intake_status")),
        "cameo_validation_operations_official_results_intake_ready": bool(cameo_operations_dossier.get("official_results_intake_ready") is True),
        "cameo_validation_operations_official_results_intake_blocker_count": _int(cameo_operations_dossier.get("official_results_intake_blocker_count")),
        "cameo_validation_operations_public_registration_allowed": bool(cameo_operations_dossier.get("public_registration_allowed") is True),
        "cameo_validation_operations_dossier_json": cameo_validation_operations_dossier_path if cameo_validation_operations_dossier_packet else "",
        "cameo_cli_status_set_status": _text(cameo_cli_status.get("status")),
        "cameo_cli_command_count": _int(cameo_cli_status.get("command_count")),
        "cameo_cli_blocked_or_missing_command_count": _int(cameo_cli_status.get("blocked_or_missing_command_count")),
        "cameo_cli_approval_required_command_count": _int(cameo_cli_status.get("approval_required_command_count")),
        "cameo_cli_approval_token_count": _int(cameo_cli_status.get("approval_token_count")),
        "cameo_cli_approval_tokens_required": list(cameo_cli_status.get("approval_tokens_required") or []),
        "cameo_cli_official_result_required": bool(cameo_cli_status.get("official_result_required") is True),
        "cameo_cli_official_results_result_row_count": _int(cameo_cli_status.get("official_results_result_row_count")),
        "cameo_cli_official_results_accepted_count": _int(cameo_cli_status.get("official_results_accepted_count")),
        "cameo_cli_official_model1_result_ready": bool(cameo_cli_status.get("official_model1_result_ready") is True),
        "cameo_cli_evidence_integrity_ready": bool(cameo_cli_status.get("evidence_integrity_ready") is True),
        "cameo_cli_official_results_pending_honest": bool(cameo_cli_status.get("official_results_pending_honest") is True),
        "cameo_cli_no_local_native_accuracy_substitution": bool(
            cameo_cli_status.get("no_local_native_accuracy_substitution") is True
        ),
        "cameo_cli_api_install_approval_required": bool(cameo_cli_status.get("api_install_approval_required") is True),
        "cameo_cli_api_dependency_status": _text(cameo_cli_status.get("api_dependency_status")),
        "cameo_cli_receiver_smoke_status": _text(cameo_cli_status.get("receiver_smoke_status")),
        "cameo_cli_public_registration_authorized": bool(cameo_cli_status.get("public_registration_authorized") is True),
        "cameo_cli_registration_awaiting_operator_approval_row_count": _int(
            cameo_cli_status.get("registration_awaiting_operator_approval_row_count")
        ),
        "cameo_official_results_intake_gate_status": _text(cameo_official_results_gate.get("status")),
        "cameo_official_results_intake_result_row_count": _int(cameo_official_results_gate.get("result_row_count")),
        "cameo_official_results_intake_accepted_count": _int(cameo_official_results_gate.get("accepted_official_result_count")),
        "cameo_official_results_intake_rejected_count": _int(cameo_official_results_gate.get("rejected_official_result_count")),
        "cameo_official_results_intake_model1_ready": bool(cameo_official_results_gate.get("model1_official_result_ready") is True),
        "cameo_official_results_intake_blocker_count": _int(cameo_official_results_gate.get("blocker_count")),
        "cameo_official_results_intake_blocker_codes": list(cameo_official_results_gate.get("blocker_codes") or []),
        "cameo_official_results_intake_missing_required_columns": list(cameo_official_results_gate.get("missing_required_columns") or []),
        "cameo_official_results_operator_intake_csv": _text(cameo_official_results_gate.get("operator_intake_csv")),
        "cameo_official_results_intake_gate_json": cameo_official_results_intake_gate_path if cameo_official_results_intake_gate_packet else "",
        "cameo_public_registration_approval_gate_status": _text(cameo_registration_gate.get("status")),
        "cameo_public_registration_authorized_for_registration_review": bool(cameo_registration_gate.get("authorized_for_registration_review") is True),
        "cameo_public_registration_operator_approval_csv_present": bool(cameo_registration_gate.get("operator_approval_csv_present") is True),
        "cameo_public_registration_blocked_row_count": _int(cameo_registration_gate.get("blocked_row_count")),
        "cameo_public_registration_approval_gate_json": cameo_public_registration_approval_gate_path if cameo_public_registration_approval_gate_packet else "",
        "product_pilot_packet_status": _text(pilot.get("status")),
        "product_pilot_delivery_ready": bool(pilot.get("pilot_delivery_ready") is True),
        "product_pilot_packet_json": product_pilot_packet_path if product_pilot_packet else "",
        "product_execution_approval_gate_status": _text(product_approval_gate.get("status")),
        "product_execution_authorized_for_execution": bool(product_approval_gate.get("authorized_for_execution") is True),
        "product_execution_authorized_row_count": _int(product_approval_gate.get("authorized_row_count")),
        "product_execution_awaiting_operator_approval_row_count": _int(product_approval_gate.get("awaiting_operator_approval_row_count")),
        "product_execution_blocked_row_count": _int(product_approval_gate.get("blocked_row_count")),
        "product_execution_operator_approval_csv_present": bool(product_approval_gate.get("operator_approval_csv_present") is True),
        "product_execution_approval_gate_json": product_execution_approval_gate_path if product_execution_approval_gate_packet else "",
        "product_license_decision_gate_status": _text(product_license_gate.get("status")),
        "product_license_decision_packet_status": _text(product_license_packet.get("status")),
        "product_license_decision_option_count": _int(product_license_packet.get("option_count")),
        "product_license_decision_packet_ready": bool(product_license_packet.get("status") == "product_license_decision_packet_ready"),
        "product_license_authorized_for_file_creation_review": bool(product_license_gate.get("authorized_for_license_file_creation_review") is True),
        "product_license_operator_intake_csv_present": bool(product_license_gate.get("operator_intake_csv_present") is True),
        "product_license_blocker_count": _int(product_license_gate.get("blocker_count")),
        "product_license_decision_gate_json": product_license_decision_gate_path if product_license_decision_gate_packet else "",
        "product_license_decision_packet_json": product_license_decision_packet_path if product_license_decision_packet else "",
        "product_license_file_creation_work_order_status": _text(product_license_file_creation_work_order.get("status")),
        "product_license_file_creation_review_ready": bool(
            product_license_file_creation_work_order.get("license_file_creation_review_ready") is True
        ),
        "product_license_review_manifest_ready": bool(
            product_license_file_creation_work_order.get("license_review_manifest_ready") is True
        ),
        "product_license_review_manifest_fingerprint_sha256": _text(
            product_license_file_creation_work_order.get("license_review_manifest_fingerprint_sha256")
        ),
        "product_license_file_creation_work_order_json": (
            product_license_file_creation_work_order_path if product_license_file_creation_work_order_packet else ""
        ),
        "product_cli_status_set_status": _text(product_cli_status.get("status")),
        "product_cli_command_count": _int(product_cli_status.get("command_count")),
        "product_cli_blocked_or_missing_command_count": _int(product_cli_status.get("blocked_or_missing_command_count")),
        "product_cli_approval_token_count": _int(product_cli_status.get("approval_token_count")),
        "product_cli_approval_tokens_required": list(product_cli_status.get("approval_tokens_required") or []),
        "product_cli_operations_stage_count": _int(product_cli_status.get("operations_stage_count")),
        "product_cli_operations_blocked_stage_count": _int(product_cli_status.get("operations_blocked_stage_count")),
        "product_cli_operations_approval_required_stage_count": _int(
            product_cli_status.get("operations_approval_required_stage_count")
        ),
        "product_cli_capability_surface_ready": bool(product_cli_status.get("capability_surface_ready") is True),
        "product_cli_operational_quality_ready": bool(product_cli_status.get("operational_quality_ready") is True),
        "product_cli_structure_analysis_capability_ready": bool(
            product_cli_status.get("structure_analysis_capability_ready") is True
        ),
        "product_cli_ligand_docking_capability_ready": bool(product_cli_status.get("ligand_docking_capability_ready") is True),
        "product_cli_product_api_surface_ready": bool(product_cli_status.get("product_api_surface_ready") is True),
        "product_cli_architecture_release_ready": bool(product_cli_status.get("architecture_release_ready") is True),
        "product_cli_commercial_independence_ready": bool(product_cli_status.get("commercial_independence_ready") is True),
        "product_cli_license_present": bool(product_cli_status.get("license_present") is True),
        "product_cli_license_authorized_for_file_creation_review": bool(
            product_cli_status.get("license_authorized_for_file_creation_review") is True
        ),
        "product_cli_authorized_for_execution": bool(product_cli_status.get("authorized_for_execution") is True),
        "product_cli_bundle_assembled": bool(product_cli_status.get("bundle_assembled") is True),
        "product_cli_bundle_validation_passed": bool(product_cli_status.get("bundle_validation_passed") is True),
        "product_cli_delivery_ready_claim_allowed": bool(product_cli_status.get("delivery_ready_claim_allowed") is True),
        "product_cli_pilot_delivery_ready": bool(product_cli_status.get("pilot_delivery_ready") is True),
        "product_release_operations_dossier_status": _text(product_release_dossier.get("status")),
        "product_release_operations_blocked_stage_count": _int(product_release_dossier.get("blocked_stage_count")),
        "product_release_operations_approval_required_stage_count": _int(product_release_dossier.get("approval_required_stage_count")),
        "product_release_operations_capability_surface_ready": bool(product_release_dossier.get("capability_surface_ready") is True),
        "product_release_operations_operational_quality_ready": bool(
            product_release_dossier.get("operational_quality_ready") is True
        ),
        "product_release_operations_operational_quality_blocker_count": _int(
            product_release_dossier.get("operational_quality_blocker_count")
        ),
        "product_release_operations_source_operational_quality_status": _text(
            product_release_dossier.get("source_operational_quality_status")
        ),
        "product_release_operations_operational_quality_artifact": "runs/product_operational_quality_contract_current.json"
        if product_release_operations_dossier_packet
        else "",
        "product_release_operations_architecture_contract_ready": bool(
            product_release_dossier.get("architecture_contract_ready") is True
        ),
        "product_release_operations_architecture_release_ready": bool(
            product_release_dossier.get("architecture_release_ready") is True
        ),
        "product_release_operations_architecture_blocked_lane_count": _int(
            product_release_dossier.get("architecture_blocked_lane_count")
        ),
        "product_release_operations_architecture_approval_required_lane_count": _int(
            product_release_dossier.get("architecture_approval_required_lane_count")
        ),
        "product_release_operations_cameo_architecture_validation_ready": bool(
            product_release_dossier.get("cameo_architecture_validation_ready") is True
        ),
        "product_release_operations_cameo_official_validation_evidence_ready": bool(
            product_release_dossier.get("cameo_official_validation_evidence_ready") is True
        ),
        "product_release_operations_cameo_receiver_smoke_ready": bool(
            product_release_dossier.get("cameo_receiver_smoke_ready") is True
        ),
        "product_release_operations_cameo_receiver_smoke_status": _text(
            product_release_dossier.get("cameo_receiver_smoke_status")
        ),
        "product_release_operations_cameo_api_dependency_ready": bool(
            product_release_dossier.get("cameo_api_dependency_ready") is True
        ),
        "product_release_operations_cameo_api_dependency_status": _text(
            product_release_dossier.get("cameo_api_dependency_status")
        ),
        "product_release_operations_cameo_public_registration_allowed": bool(
            product_release_dossier.get("cameo_public_registration_allowed") is True
        ),
        "product_release_operations_cameo_public_registration_blocker_count": _int(
            product_release_dossier.get("cameo_public_registration_blocker_count")
        ),
        "product_release_operations_cameo_registration_approval_token_count": _int(
            product_release_dossier.get("cameo_registration_approval_token_count")
        ),
        "product_release_operations_cameo_registration_approval_tokens_required": list(
            product_release_dossier.get("cameo_registration_approval_tokens_required") or []
        ),
        "product_release_operations_cleanup_postcheck_contract_ready": bool(
            product_release_dossier.get("cleanup_postcheck_contract_ready") is True
        ),
        "product_release_operations_structure_analysis_capability_ready": bool(
            product_release_dossier.get("structure_analysis_capability_ready") is True
        ),
        "product_release_operations_ligand_docking_capability_ready": bool(
            product_release_dossier.get("ligand_docking_capability_ready") is True
        ),
        "product_release_operations_api_surface_ready": bool(product_release_dossier.get("product_api_surface_ready") is True),
        "product_release_operations_commercial_independence_ready": bool(
            product_release_dossier.get("commercial_independence_ready") is True
        ),
        "product_release_operations_license_present": bool(product_release_dossier.get("license_present") is True),
        "product_release_operations_license_decision_packet_ready": bool(
            product_release_dossier.get("license_decision_packet_ready") is True
        ),
        "product_release_operations_license_decision_option_count": _int(product_release_dossier.get("license_decision_option_count")),
        "product_release_operations_license_authorized_for_file_creation_review": bool(
            product_release_dossier.get("license_authorized_for_file_creation_review") is True
        ),
        "product_release_operations_authorized_for_execution": bool(product_release_dossier.get("authorized_for_execution") is True),
        "product_release_operations_bundle_assembled": bool(product_release_dossier.get("bundle_assembled") is True),
        "product_release_operations_bundle_validation_passed": bool(product_release_dossier.get("bundle_validation_passed") is True),
        "product_release_operations_delivery_ready_claim_allowed": bool(product_release_dossier.get("delivery_ready_claim_allowed") is True),
        "product_release_operations_pilot_delivery_ready": bool(product_release_dossier.get("pilot_delivery_ready") is True),
        "product_release_operations_dossier_json": product_release_operations_dossier_path if product_release_operations_dossier_packet else "",
        "source_rollup_json": rollup_path,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": _next_required_step(rows),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Operator Action Board",
        "",
        f"- status: `{s['status']}`",
        f"- source_rollup_status: `{s['source_rollup_status']}`",
        f"- action_count: `{s['action_count']}`",
        f"- blocked_or_required_action_count: `{s['blocked_or_required_action_count']}`",
        f"- approval_required_count: `{s['approval_required_count']}`",
        f"- review_required_count: `{s['review_required_count']}`",
        f"- operator_input_required_count: `{s['operator_input_required_count']}`",
        f"- primary_action_id: `{s['primary_action_id']}`",
        f"- primary_action_priority: `{s['primary_action_priority']}`",
        f"- primary_action_status: `{s['primary_action_status']}`",
        f"- primary_action_required_input: `{s['primary_action_required_input']}`",
        f"- primary_action_recommended_action: `{s['primary_action_recommended_action']}`",
        f"- product_ai_production_action_count: `{s['product_ai_production_action_count']}`",
        f"- product_scope_expansion_action_count: `{s['product_scope_expansion_action_count']}`",
        f"- product_engine_refinement_action_count: `{s['product_engine_refinement_action_count']}`",
        f"- product_engine_refinement_action_board_csv: `{s['product_engine_refinement_action_board_csv']}`",
        f"- product_engine_refinement_claim_blocker_count: `{s['product_engine_refinement_claim_blocker_count']}`",
        f"- product_goal_completion_audit_status: `{s['product_goal_completion_audit_status']}`",
        f"- product_goal_complete: `{s['product_goal_complete']}`",
        f"- product_goal_primary_bottleneck_kind: `{s['product_goal_primary_bottleneck_kind']}`",
        f"- product_goal_engine_refinement_claim_promotion_ready: `{s['product_goal_engine_refinement_claim_promotion_ready']}`",
        f"- product_goal_engine_refinement_claim_promotion_blocker_count: `{s['product_goal_engine_refinement_claim_promotion_blocker_count']}`",
        f"- product_goal_engine_refinement_claim_promotion_action_board_csv: `{s['product_goal_engine_refinement_claim_promotion_action_board_csv']}`",
        f"- product_goal_engine_refinement_claim_evidence_receipt_ready: `{s['product_goal_engine_refinement_claim_evidence_receipt_ready']}`",
        f"- product_goal_engine_refinement_claim_evidence_receipt_artifact: `{s['product_goal_engine_refinement_claim_evidence_receipt_artifact']}`",
        f"- product_goal_production_ai_checkpoint_ready: `{s['product_goal_production_ai_checkpoint_ready']}`",
        f"- product_goal_production_ai_gpu_handoff_ready: `{s['product_goal_production_ai_gpu_handoff_ready']}`",
        f"- product_goal_scope_priority_ready: `{s['product_goal_scope_priority_ready']}`",
        f"- product_goal_scope_breadth_evidence_receipt_ready: `{s['product_goal_scope_breadth_evidence_receipt_ready']}`",
        f"- product_goal_scope_breadth_evidence_receipt_status: `{s['product_goal_scope_breadth_evidence_receipt_status']}`",
        f"- product_goal_scope_breadth_evidence_receipt_artifact: `{s['product_goal_scope_breadth_evidence_receipt_artifact']}`",
        f"- product_goal_scope_priority_top_item_id: `{s['product_goal_scope_priority_top_item_id']}`",
        f"- approval_reclaim_size_gb: `{s['approval_reclaim_size_gb']}`",
        f"- large_review_size_gb: `{s['large_review_size_gb']}`",
        f"- large_cleanup_drilldown_status: `{s['large_cleanup_drilldown_status']}`",
        f"- large_cleanup_known_payload_size_gb: `{s['large_cleanup_known_payload_size_gb']}`",
        f"- large_cleanup_dry_run_delete_payload_size_gb: `{s['large_cleanup_dry_run_delete_payload_size_gb']}`",
        f"- large_cleanup_dry_run_protected_payload_size_gb: `{s['large_cleanup_dry_run_protected_payload_size_gb']}`",
        f"- protected_cleanup_review_status: `{s['protected_cleanup_review_status']}`",
        f"- protected_cleanup_payload_size_gb: `{s['protected_cleanup_payload_size_gb']}`",
        f"- protected_cleanup_policy_change_required_count: `{s['protected_cleanup_policy_change_required_count']}`",
        f"- protected_cleanup_approval_promoted_count: `{s['protected_cleanup_approval_promoted_count']}`",
        f"- protected_ligand_heavy_deep_review_status: `{s['protected_ligand_heavy_deep_review_status']}`",
        f"- protected_ligand_heavy_known_payload_child_count: `{s['protected_ligand_heavy_known_payload_child_count']}`",
        f"- protected_ligand_heavy_known_payload_child_size_gb: `{s['protected_ligand_heavy_known_payload_child_size_gb']}`",
        f"- protected_ligand_heavy_preservation_sibling_count: `{s['protected_ligand_heavy_preservation_sibling_count']}`",
        f"- protected_ligand_heavy_policy_change_required_for_deletion_count: `{s['protected_ligand_heavy_policy_change_required_for_deletion_count']}`",
        f"- protected_cleanup_policy_decision_gate_status: `{s['protected_cleanup_policy_decision_gate_status']}`",
        f"- protected_cleanup_policy_resolved: `{s['protected_cleanup_policy_resolved']}`",
        f"- protected_cleanup_policy_awaiting_decision_row_count: `{s['protected_cleanup_policy_awaiting_decision_row_count']}`",
        f"- protected_cleanup_policy_change_requested_row_count: `{s['protected_cleanup_policy_change_requested_row_count']}`",
        f"- protected_cleanup_policy_decision_blocked_row_count: `{s['protected_cleanup_policy_decision_blocked_row_count']}`",
        f"- cleanup_cli_status_set_status: `{s['cleanup_cli_status_set_status']}`",
        f"- cleanup_cli_command_count: `{s['cleanup_cli_command_count']}`",
        f"- cleanup_cli_blocked_or_missing_command_count: `{s['cleanup_cli_blocked_or_missing_command_count']}`",
        f"- cleanup_cli_approval_required_command_count: `{s['cleanup_cli_approval_required_command_count']}`",
        f"- cleanup_cli_approval_token_count: `{s['cleanup_cli_approval_token_count']}`",
        f"- cleanup_cli_approval_tokens_required: `{';'.join(s['cleanup_cli_approval_tokens_required'])}`",
        f"- cleanup_cli_approval_reclaim_size_gb: `{s['cleanup_cli_approval_reclaim_size_gb']}`",
        f"- cleanup_cli_authorized_reclaim_size_gb: `{s['cleanup_cli_authorized_reclaim_size_gb']}`",
        f"- cleanup_cli_awaiting_operator_approval_row_count: `{s['cleanup_cli_awaiting_operator_approval_row_count']}`",
        f"- cleanup_cli_postcheck_contract_ready: `{s['cleanup_cli_postcheck_contract_ready']}`",
        f"- cleanup_cli_postcheck_row_count: `{s['cleanup_cli_postcheck_row_count']}`",
        f"- cleanup_cli_postcheck_blocked_row_count: `{s['cleanup_cli_postcheck_blocked_row_count']}`",
        f"- cleanup_cli_protected_payload_size_gb: `{s['cleanup_cli_protected_payload_size_gb']}`",
        f"- cleanup_cli_protected_policy_change_required_count: `{s['cleanup_cli_protected_policy_change_required_count']}`",
        f"- cleanup_cli_protected_policy_resolved: `{s['cleanup_cli_protected_policy_resolved']}`",
        f"- cleanup_snapshot_preflight_status: `{s['cleanup_snapshot_preflight_status']}`",
        f"- cleanup_snapshot_blocked_row_count: `{s['cleanup_snapshot_blocked_row_count']}`",
        f"- cleanup_snapshot_missing_count: `{s['cleanup_snapshot_missing_count']}`",
        f"- cleanup_snapshot_required_count: `{s['cleanup_snapshot_required_count']}`",
        f"- cleanup_snapshot_approval_gated_size_gb: `{s['cleanup_snapshot_approval_gated_size_gb']}`",
        f"- cleanup_payload_manifest_lock_status: `{s['cleanup_payload_manifest_lock_status']}`",
        f"- cleanup_payload_manifest_lock_row_count: `{s['cleanup_payload_manifest_lock_row_count']}`",
        f"- cleanup_payload_manifest_lock_blocked_row_count: `{s['cleanup_payload_manifest_lock_blocked_row_count']}`",
        f"- cleanup_payload_manifest_fingerprint_sha256: `{s['cleanup_payload_manifest_fingerprint_sha256']}`",
        f"- cleanup_postcheck_contract_status: `{s['cleanup_postcheck_contract_status']}`",
        f"- cleanup_postcheck_contract_ready: `{s['cleanup_postcheck_contract_ready']}`",
        f"- cleanup_postcheck_row_count: `{s['cleanup_postcheck_row_count']}`",
        f"- cleanup_postcheck_approval_row_count: `{s['cleanup_postcheck_approval_row_count']}`",
        f"- cleanup_postcheck_protected_policy_row_count: `{s['cleanup_postcheck_protected_policy_row_count']}`",
        f"- cleanup_postcheck_blocked_row_count: `{s['cleanup_postcheck_blocked_row_count']}`",
        f"- cleanup_postcheck_global_refresh_command_count: `{s['cleanup_postcheck_global_refresh_command_count']}`",
        f"- cleanup_execution_approval_dossier_status: `{s['cleanup_execution_approval_dossier_status']}`",
        f"- cleanup_execution_approval_dossier_approval_row_count: `{s['cleanup_execution_approval_dossier_approval_row_count']}`",
        f"- cleanup_execution_approval_dossier_snapshot_backed_approval_row_count: `{s['cleanup_execution_approval_dossier_snapshot_backed_approval_row_count']}`",
        f"- cleanup_execution_approval_dossier_snapshot_artifact_count: `{s['cleanup_execution_approval_dossier_snapshot_artifact_count']}`",
        f"- cleanup_execution_approval_dossier_snapshot_ready_count: `{s['cleanup_execution_approval_dossier_snapshot_ready_count']}`",
        f"- cleanup_execution_approval_dossier_snapshot_listing_truncated_count: `{s['cleanup_execution_approval_dossier_snapshot_listing_truncated_count']}`",
        f"- cleanup_execution_approval_dossier_snapshot_total_entry_count: `{s['cleanup_execution_approval_dossier_snapshot_total_entry_count']}`",
        f"- cleanup_execution_approval_dossier_snapshot_set_fingerprint_sha256: `{s['cleanup_execution_approval_dossier_snapshot_set_fingerprint_sha256']}`",
        f"- cleanup_execution_approval_gate_status: `{s['cleanup_execution_approval_gate_status']}`",
        f"- cleanup_execution_authorized_row_count: `{s['cleanup_execution_authorized_row_count']}`",
        f"- cleanup_execution_awaiting_operator_approval_row_count: `{s['cleanup_execution_awaiting_operator_approval_row_count']}`",
        f"- cleanup_execution_blocked_row_count: `{s['cleanup_execution_blocked_row_count']}`",
        f"- cleanup_execution_authorized_reclaim_size_gb: `{s['cleanup_execution_authorized_reclaim_size_gb']}`",
        f"- cleanup_execution_total_reclaim_size_gb: `{s['cleanup_execution_total_reclaim_size_gb']}`",
        f"- cleanup_execution_operator_approval_csv_present: `{s['cleanup_execution_operator_approval_csv_present']}`",
        f"- cleanup_completion_gate_status: `{s['cleanup_completion_gate_status']}`",
        f"- cleanup_completion_complete: `{s['cleanup_completion_complete']}`",
        f"- cleanup_completion_blocked_stage_count: `{s['cleanup_completion_blocked_stage_count']}`",
        f"- cleanup_completion_approval_ready: `{s['cleanup_completion_approval_ready']}`",
        f"- cleanup_completion_transition_cleanup_complete: `{s['cleanup_completion_transition_cleanup_complete']}`",
        f"- cleanup_completion_ligand_heavy_cleanup_complete: `{s['cleanup_completion_ligand_heavy_cleanup_complete']}`",
        f"- cleanup_completion_protected_policy_resolved: `{s['cleanup_completion_protected_policy_resolved']}`",
        f"- goal_release_decision_gate_status: `{s['goal_release_decision_gate_status']}`",
        f"- goal_release_allowed: `{s['goal_release_allowed']}`",
        f"- goal_release_blocker_count: `{s['goal_release_blocker_count']}`",
        f"- goal_release_check_count: `{s['goal_release_check_count']}`",
        f"- commercial_independent_product_ready: `{s['commercial_independent_product_ready']}`",
        f"- cameo_architecture_validation_ready: `{s['cameo_architecture_validation_ready']}`",
        f"- cleanup_objective_ready: `{s['cleanup_objective_ready']}`",
        f"- source_goal_api_surface_contract_status: `{s['source_goal_api_surface_contract_status']}`",
        f"- goal_api_surface_ready: `{s['goal_api_surface_ready']}`",
        f"- goal_api_surface_check_count: `{s['goal_api_surface_check_count']}`",
        f"- goal_api_surface_blocker_count: `{s['goal_api_surface_blocker_count']}`",
        f"- goal_release_burndown_work_order_status: `{s['goal_release_burndown_work_order_status']}`",
        f"- goal_release_burndown_release_blocker_check_count: `{s['goal_release_burndown_release_blocker_check_count']}`",
        f"- goal_release_burndown_work_item_count: `{s['goal_release_burndown_work_item_count']}`",
        f"- goal_release_burndown_approval_required_item_count: `{s['goal_release_burndown_approval_required_item_count']}`",
        f"- goal_release_burndown_operator_input_required_item_count: `{s['goal_release_burndown_operator_input_required_item_count']}`",
        f"- goal_release_burndown_operator_input_required_work_item_count: `{s['goal_release_burndown_operator_input_required_work_item_count']}`",
        f"- goal_release_burndown_official_results_required_item_count: `{s['goal_release_burndown_official_results_required_item_count']}`",
        f"- goal_release_burndown_policy_decision_required_item_count: `{s['goal_release_burndown_policy_decision_required_item_count']}`",
        f"- goal_release_burndown_postcheck_required_item_count: `{s['goal_release_burndown_postcheck_required_item_count']}`",
        f"- goal_release_burndown_approval_token_count: `{s['goal_release_burndown_approval_token_count']}`",
        f"- goal_operator_intake_kit_status: `{s['goal_operator_intake_kit_status']}`",
        f"- goal_operator_intake_kit_entry_count: `{s['goal_operator_intake_kit_entry_count']}`",
        f"- goal_operator_intake_kit_release_burndown_linked_entry_count: `{s['goal_operator_intake_kit_release_burndown_linked_entry_count']}`",
        f"- goal_operator_intake_kit_operator_input_required_count: `{s['goal_operator_intake_kit_operator_input_required_count']}`",
        f"- goal_operator_intake_kit_current_action_required_count: `{s['goal_operator_intake_kit_current_action_required_count']}`",
        f"- goal_operator_intake_kit_deferred_operator_input_count: `{s['goal_operator_intake_kit_deferred_operator_input_count']}`",
        f"- goal_operator_intake_kit_template_copied_count: `{s['goal_operator_intake_kit_template_copied_count']}`",
        f"- goal_operator_intake_kit_template_missing_count: `{s['goal_operator_intake_kit_template_missing_count']}`",
        f"- goal_operator_intake_kit_approval_token_count: `{s['goal_operator_intake_kit_approval_token_count']}`",
        f"- goal_operator_intake_kit_current_action_approval_token_count: `{s['goal_operator_intake_kit_current_action_approval_token_count']}`",
        f"- goal_operator_intake_kit_current_action_approval_tokens: `{';'.join(s['goal_operator_intake_kit_current_action_approval_tokens'])}`",
        f"- goal_operator_intake_kit_product_commercial_independence_status: `{s['goal_operator_intake_kit_product_commercial_independence_status']}`",
        f"- goal_operator_intake_kit_product_commercial_independence_blocker_count: `{s['goal_operator_intake_kit_product_commercial_independence_blocker_count']}`",
        f"- goal_operator_intake_kit_product_commercial_independence_license_present: `{s['goal_operator_intake_kit_product_commercial_independence_license_present']}`",
        f"- goal_operator_intake_kit_goal_api_surface_contract_status: `{s['goal_operator_intake_kit_goal_api_surface_contract_status']}`",
        f"- goal_operator_intake_kit_goal_api_surface_ready: `{s['goal_operator_intake_kit_goal_api_surface_ready']}`",
        f"- goal_operator_intake_kit_goal_api_status_endpoint: `{s['goal_operator_intake_kit_goal_api_status_endpoint']}`",
        f"- goal_operator_intake_kit_goal_api_contract_endpoint: `{s['goal_operator_intake_kit_goal_api_contract_endpoint']}`",
        f"- cameo_runtime_repair_work_order_status: `{s['cameo_runtime_repair_work_order_status']}`",
        f"- cameo_runtime_install_approval_required: `{s['cameo_runtime_install_approval_required']}`",
        f"- cameo_runtime_approval_token_required: `{s['cameo_runtime_approval_token_required']}`",
        f"- cameo_runtime_repair_command_count: `{s['cameo_runtime_repair_command_count']}`",
        f"- cameo_validation_operations_dossier_status: `{s['cameo_validation_operations_dossier_status']}`",
        f"- cameo_validation_operations_blocked_stage_count: `{s['cameo_validation_operations_blocked_stage_count']}`",
        f"- cameo_validation_operations_approval_required_stage_count: `{s['cameo_validation_operations_approval_required_stage_count']}`",
        f"- cameo_validation_operations_operator_input_required_count: `{s['cameo_validation_operations_operator_input_required_count']}`",
        f"- cameo_validation_operations_approval_token_count: `{s['cameo_validation_operations_approval_token_count']}`",
        f"- cameo_validation_operations_official_result_required: `{s['cameo_validation_operations_official_result_required']}`",
        f"- cameo_validation_operations_evidence_integrity_status: `{s['cameo_validation_operations_evidence_integrity_status']}`",
        f"- cameo_validation_operations_evidence_integrity_ready: `{s['cameo_validation_operations_evidence_integrity_ready']}`",
        f"- cameo_validation_operations_evidence_integrity_blocker_count: `{s['cameo_validation_operations_evidence_integrity_blocker_count']}`",
        f"- cameo_validation_operations_official_results_pending_honest: `{s['cameo_validation_operations_official_results_pending_honest']}`",
        f"- cameo_validation_operations_no_local_native_accuracy_substitution: `{s['cameo_validation_operations_no_local_native_accuracy_substitution']}`",
        f"- cameo_validation_operations_official_results_intake_status: `{s['cameo_validation_operations_official_results_intake_status']}`",
        f"- cameo_validation_operations_official_results_intake_ready: `{s['cameo_validation_operations_official_results_intake_ready']}`",
        f"- cameo_validation_operations_official_results_intake_blocker_count: `{s['cameo_validation_operations_official_results_intake_blocker_count']}`",
        f"- cameo_validation_operations_public_registration_allowed: `{s['cameo_validation_operations_public_registration_allowed']}`",
        f"- cameo_cli_status_set_status: `{s['cameo_cli_status_set_status']}`",
        f"- cameo_cli_command_count: `{s['cameo_cli_command_count']}`",
        f"- cameo_cli_blocked_or_missing_command_count: `{s['cameo_cli_blocked_or_missing_command_count']}`",
        f"- cameo_cli_approval_required_command_count: `{s['cameo_cli_approval_required_command_count']}`",
        f"- cameo_cli_approval_token_count: `{s['cameo_cli_approval_token_count']}`",
        f"- cameo_cli_approval_tokens_required: `{';'.join(s['cameo_cli_approval_tokens_required'])}`",
        f"- cameo_cli_official_result_required: `{s['cameo_cli_official_result_required']}`",
        f"- cameo_cli_official_results_result_row_count: `{s['cameo_cli_official_results_result_row_count']}`",
        f"- cameo_cli_official_results_accepted_count: `{s['cameo_cli_official_results_accepted_count']}`",
        f"- cameo_cli_official_model1_result_ready: `{s['cameo_cli_official_model1_result_ready']}`",
        f"- cameo_cli_evidence_integrity_ready: `{s['cameo_cli_evidence_integrity_ready']}`",
        f"- cameo_cli_official_results_pending_honest: `{s['cameo_cli_official_results_pending_honest']}`",
        f"- cameo_cli_no_local_native_accuracy_substitution: `{s['cameo_cli_no_local_native_accuracy_substitution']}`",
        f"- cameo_cli_api_install_approval_required: `{s['cameo_cli_api_install_approval_required']}`",
        f"- cameo_cli_api_dependency_status: `{s['cameo_cli_api_dependency_status']}`",
        f"- cameo_cli_receiver_smoke_status: `{s['cameo_cli_receiver_smoke_status']}`",
        f"- cameo_cli_public_registration_authorized: `{s['cameo_cli_public_registration_authorized']}`",
        f"- cameo_cli_registration_awaiting_operator_approval_row_count: `{s['cameo_cli_registration_awaiting_operator_approval_row_count']}`",
        f"- cameo_official_results_intake_gate_status: `{s['cameo_official_results_intake_gate_status']}`",
        f"- cameo_official_results_intake_result_row_count: `{s['cameo_official_results_intake_result_row_count']}`",
        f"- cameo_official_results_intake_accepted_count: `{s['cameo_official_results_intake_accepted_count']}`",
        f"- cameo_official_results_intake_rejected_count: `{s['cameo_official_results_intake_rejected_count']}`",
        f"- cameo_official_results_intake_model1_ready: `{s['cameo_official_results_intake_model1_ready']}`",
        f"- cameo_official_results_intake_blocker_count: `{s['cameo_official_results_intake_blocker_count']}`",
        f"- cameo_official_results_intake_blocker_codes: `{';'.join(s['cameo_official_results_intake_blocker_codes'])}`",
        f"- cameo_official_results_intake_missing_required_columns: `{';'.join(s['cameo_official_results_intake_missing_required_columns'])}`",
        f"- cameo_official_results_operator_intake_csv: `{s['cameo_official_results_operator_intake_csv']}`",
        f"- cameo_public_registration_approval_gate_status: `{s['cameo_public_registration_approval_gate_status']}`",
        f"- cameo_public_registration_authorized_for_registration_review: `{s['cameo_public_registration_authorized_for_registration_review']}`",
        f"- cameo_public_registration_operator_approval_csv_present: `{s['cameo_public_registration_operator_approval_csv_present']}`",
        f"- cameo_public_registration_blocked_row_count: `{s['cameo_public_registration_blocked_row_count']}`",
        f"- product_pilot_packet_status: `{s['product_pilot_packet_status']}`",
        f"- product_pilot_delivery_ready: `{s['product_pilot_delivery_ready']}`",
        f"- product_execution_approval_gate_status: `{s['product_execution_approval_gate_status']}`",
        f"- product_execution_authorized_for_execution: `{s['product_execution_authorized_for_execution']}`",
        f"- product_execution_authorized_row_count: `{s['product_execution_authorized_row_count']}`",
        f"- product_execution_awaiting_operator_approval_row_count: `{s['product_execution_awaiting_operator_approval_row_count']}`",
        f"- product_execution_blocked_row_count: `{s['product_execution_blocked_row_count']}`",
        f"- product_execution_operator_approval_csv_present: `{s['product_execution_operator_approval_csv_present']}`",
        f"- product_license_decision_gate_status: `{s['product_license_decision_gate_status']}`",
        f"- product_license_decision_packet_status: `{s['product_license_decision_packet_status']}`",
        f"- product_license_decision_option_count: `{s['product_license_decision_option_count']}`",
        f"- product_license_decision_packet_ready: `{s['product_license_decision_packet_ready']}`",
        f"- product_license_authorized_for_file_creation_review: `{s['product_license_authorized_for_file_creation_review']}`",
        f"- product_license_operator_intake_csv_present: `{s['product_license_operator_intake_csv_present']}`",
        f"- product_license_blocker_count: `{s['product_license_blocker_count']}`",
        f"- product_license_file_creation_work_order_status: `{s['product_license_file_creation_work_order_status']}`",
        f"- product_license_file_creation_review_ready: `{s['product_license_file_creation_review_ready']}`",
        f"- product_license_review_manifest_ready: `{s['product_license_review_manifest_ready']}`",
        f"- product_license_review_manifest_fingerprint_sha256: `{s['product_license_review_manifest_fingerprint_sha256']}`",
        f"- product_cli_status_set_status: `{s['product_cli_status_set_status']}`",
        f"- product_cli_command_count: `{s['product_cli_command_count']}`",
        f"- product_cli_blocked_or_missing_command_count: `{s['product_cli_blocked_or_missing_command_count']}`",
        f"- product_cli_approval_token_count: `{s['product_cli_approval_token_count']}`",
        f"- product_cli_approval_tokens_required: `{';'.join(s['product_cli_approval_tokens_required'])}`",
        f"- product_cli_operations_stage_count: `{s['product_cli_operations_stage_count']}`",
        f"- product_cli_operations_blocked_stage_count: `{s['product_cli_operations_blocked_stage_count']}`",
        f"- product_cli_operations_approval_required_stage_count: `{s['product_cli_operations_approval_required_stage_count']}`",
        f"- product_cli_capability_surface_ready: `{s['product_cli_capability_surface_ready']}`",
        f"- product_cli_operational_quality_ready: `{s['product_cli_operational_quality_ready']}`",
        f"- product_cli_structure_analysis_capability_ready: `{s['product_cli_structure_analysis_capability_ready']}`",
        f"- product_cli_ligand_docking_capability_ready: `{s['product_cli_ligand_docking_capability_ready']}`",
        f"- product_cli_product_api_surface_ready: `{s['product_cli_product_api_surface_ready']}`",
        f"- product_cli_architecture_release_ready: `{s['product_cli_architecture_release_ready']}`",
        f"- product_cli_commercial_independence_ready: `{s['product_cli_commercial_independence_ready']}`",
        f"- product_cli_license_present: `{s['product_cli_license_present']}`",
        f"- product_cli_license_authorized_for_file_creation_review: `{s['product_cli_license_authorized_for_file_creation_review']}`",
        f"- product_cli_authorized_for_execution: `{s['product_cli_authorized_for_execution']}`",
        f"- product_cli_bundle_assembled: `{s['product_cli_bundle_assembled']}`",
        f"- product_cli_bundle_validation_passed: `{s['product_cli_bundle_validation_passed']}`",
        f"- product_cli_delivery_ready_claim_allowed: `{s['product_cli_delivery_ready_claim_allowed']}`",
        f"- product_cli_pilot_delivery_ready: `{s['product_cli_pilot_delivery_ready']}`",
        f"- product_release_operations_dossier_status: `{s['product_release_operations_dossier_status']}`",
        f"- product_release_operations_blocked_stage_count: `{s['product_release_operations_blocked_stage_count']}`",
        f"- product_release_operations_approval_required_stage_count: `{s['product_release_operations_approval_required_stage_count']}`",
        f"- product_release_operations_capability_surface_ready: `{s['product_release_operations_capability_surface_ready']}`",
        f"- product_release_operations_operational_quality_ready: `{s['product_release_operations_operational_quality_ready']}`",
        f"- product_release_operations_operational_quality_blocker_count: `{s['product_release_operations_operational_quality_blocker_count']}`",
        f"- product_release_operations_source_operational_quality_status: `{s['product_release_operations_source_operational_quality_status']}`",
        f"- product_release_operations_architecture_contract_ready: `{s['product_release_operations_architecture_contract_ready']}`",
        f"- product_release_operations_architecture_release_ready: `{s['product_release_operations_architecture_release_ready']}`",
        f"- product_release_operations_architecture_blocked_lane_count: `{s['product_release_operations_architecture_blocked_lane_count']}`",
        f"- product_release_operations_architecture_approval_required_lane_count: `{s['product_release_operations_architecture_approval_required_lane_count']}`",
        f"- product_release_operations_cameo_architecture_validation_ready: `{s['product_release_operations_cameo_architecture_validation_ready']}`",
        f"- product_release_operations_cameo_official_validation_evidence_ready: `{s['product_release_operations_cameo_official_validation_evidence_ready']}`",
        f"- product_release_operations_cameo_receiver_smoke_ready: `{s['product_release_operations_cameo_receiver_smoke_ready']}`",
        f"- product_release_operations_cameo_receiver_smoke_status: `{s['product_release_operations_cameo_receiver_smoke_status']}`",
        f"- product_release_operations_cameo_api_dependency_ready: `{s['product_release_operations_cameo_api_dependency_ready']}`",
        f"- product_release_operations_cameo_api_dependency_status: `{s['product_release_operations_cameo_api_dependency_status']}`",
        f"- product_release_operations_cameo_public_registration_allowed: `{s['product_release_operations_cameo_public_registration_allowed']}`",
        f"- product_release_operations_cameo_public_registration_blocker_count: `{s['product_release_operations_cameo_public_registration_blocker_count']}`",
        f"- product_release_operations_cameo_registration_approval_token_count: `{s['product_release_operations_cameo_registration_approval_token_count']}`",
        f"- product_release_operations_cameo_registration_approval_tokens_required: `{';'.join(s['product_release_operations_cameo_registration_approval_tokens_required'])}`",
        f"- product_release_operations_cleanup_postcheck_contract_ready: `{s['product_release_operations_cleanup_postcheck_contract_ready']}`",
        f"- product_release_operations_structure_analysis_capability_ready: `{s['product_release_operations_structure_analysis_capability_ready']}`",
        f"- product_release_operations_ligand_docking_capability_ready: `{s['product_release_operations_ligand_docking_capability_ready']}`",
        f"- product_release_operations_api_surface_ready: `{s['product_release_operations_api_surface_ready']}`",
        f"- product_release_operations_commercial_independence_ready: `{s['product_release_operations_commercial_independence_ready']}`",
        f"- product_release_operations_license_present: `{s['product_release_operations_license_present']}`",
        f"- product_release_operations_license_decision_packet_ready: `{s['product_release_operations_license_decision_packet_ready']}`",
        f"- product_release_operations_license_decision_option_count: `{s['product_release_operations_license_decision_option_count']}`",
        f"- product_release_operations_license_authorized_for_file_creation_review: `{s['product_release_operations_license_authorized_for_file_creation_review']}`",
        f"- product_release_operations_authorized_for_execution: `{s['product_release_operations_authorized_for_execution']}`",
        f"- product_release_operations_bundle_assembled: `{s['product_release_operations_bundle_assembled']}`",
        f"- product_release_operations_bundle_validation_passed: `{s['product_release_operations_bundle_validation_passed']}`",
        f"- product_release_operations_delivery_ready_claim_allowed: `{s['product_release_operations_delivery_ready_claim_allowed']}`",
        f"- product_release_operations_pilot_delivery_ready: `{s['product_release_operations_pilot_delivery_ready']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Actions",
        "",
        "| priority | lane | type | status | input/token | size_gb | artifact | reason |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        input_or_token = row["required_input"] or row["approval_token"]
        lines.append(
            f"| `{row['priority']}` | `{row['lane_id']}` | `{row['action_type']}` | `{row['status']}` | "
            f"`{input_or_token}` | `{row['size_gb']}` | `{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a consolidated operator action board from current goal readiness artifacts.")
    parser.add_argument("--rollup-json", default=DEFAULT_ROLLUP_JSON)
    parser.add_argument("--product-preflight-json", default=DEFAULT_PRODUCT_PREFLIGHT_JSON)
    parser.add_argument("--product-bundle-contract-json", default=DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON)
    parser.add_argument("--product-delivery-evidence-json", default=DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON)
    parser.add_argument("--product-pilot-packet-json", default=DEFAULT_PRODUCT_PILOT_PACKET_JSON)
    parser.add_argument("--product-execution-approval-gate-json", default=DEFAULT_PRODUCT_EXECUTION_APPROVAL_GATE_JSON)
    parser.add_argument("--product-license-decision-gate-json", default=DEFAULT_PRODUCT_LICENSE_DECISION_GATE_JSON)
    parser.add_argument("--product-license-decision-packet-json", default=DEFAULT_PRODUCT_LICENSE_DECISION_PACKET_JSON)
    parser.add_argument("--product-license-file-creation-work-order-json", default=DEFAULT_PRODUCT_LICENSE_FILE_CREATION_WORK_ORDER_JSON)
    parser.add_argument("--product-release-operations-dossier-json", default=DEFAULT_PRODUCT_RELEASE_OPERATIONS_DOSSIER_JSON)
    parser.add_argument("--product-goal-completion-audit-json", default=DEFAULT_PRODUCT_GOAL_COMPLETION_AUDIT_JSON)
    parser.add_argument("--goal-release-decision-gate-json", default=DEFAULT_GOAL_RELEASE_DECISION_GATE_JSON)
    parser.add_argument("--goal-release-burndown-work-order-json", default=DEFAULT_GOAL_RELEASE_BURNDOWN_WORK_ORDER_JSON)
    parser.add_argument("--cameo-runtime-repair-work-order-json", default=DEFAULT_CAMEO_RUNTIME_REPAIR_WORK_ORDER_JSON)
    parser.add_argument("--cameo-validation-operations-dossier-json", default=DEFAULT_CAMEO_VALIDATION_OPERATIONS_DOSSIER_JSON)
    parser.add_argument("--cameo-official-results-intake-gate-json", default=DEFAULT_CAMEO_OFFICIAL_RESULTS_INTAKE_GATE_JSON)
    parser.add_argument("--cameo-public-registration-approval-gate-json", default=DEFAULT_CAMEO_PUBLIC_REGISTRATION_APPROVAL_GATE_JSON)
    parser.add_argument("--cameo-input-kit-json", default=DEFAULT_CAMEO_INPUT_KIT_JSON)
    parser.add_argument("--cameo-input-validation-json", default=DEFAULT_CAMEO_INPUT_VALIDATION_JSON)
    parser.add_argument("--cameo-repair-preflight-json", default=DEFAULT_CAMEO_REPAIR_PREFLIGHT_JSON)
    parser.add_argument("--transition-cleanup-preflight-json", default=DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--ligand-cleanup-preflight-json", default=DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--large-cleanup-drilldown-json", default=DEFAULT_LARGE_CLEANUP_DRILLDOWN_JSON)
    parser.add_argument("--protected-cleanup-review-json", default=DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON)
    parser.add_argument("--protected-ligand-heavy-deep-review-json", default=DEFAULT_PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_JSON)
    parser.add_argument("--protected-cleanup-policy-decision-gate-json", default=DEFAULT_PROTECTED_CLEANUP_POLICY_DECISION_GATE_JSON)
    parser.add_argument("--cleanup-snapshot-preflight-json", default=DEFAULT_CLEANUP_SNAPSHOT_PREFLIGHT_JSON)
    parser.add_argument("--cleanup-payload-manifest-lock-json", default=DEFAULT_CLEANUP_PAYLOAD_MANIFEST_LOCK_JSON)
    parser.add_argument("--cleanup-postcheck-contract-json", default=DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON)
    parser.add_argument("--cleanup-execution-approval-dossier-json", default=DEFAULT_CLEANUP_EXECUTION_APPROVAL_DOSSIER_JSON)
    parser.add_argument("--cleanup-execution-approval-gate-json", default=DEFAULT_CLEANUP_EXECUTION_APPROVAL_GATE_JSON)
    parser.add_argument("--cleanup-completion-gate-json", default=DEFAULT_CLEANUP_COMPLETION_GATE_JSON)
    parser.add_argument("--goal-operator-intake-kit-json", default=DEFAULT_GOAL_OPERATOR_INTAKE_KIT_JSON)
    parser.add_argument(
        "--engine-refinement-claim-action-board-csv",
        default=DEFAULT_ENGINE_REFINEMENT_CLAIM_ACTION_BOARD_CSV,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_action_board(
        rollup_packet=_read_json_if_present(args.rollup_json),
        product_preflight_packet=_read_json_if_present(args.product_preflight_json),
        product_bundle_contract_packet=_read_json_if_present(args.product_bundle_contract_json),
        product_delivery_evidence_packet=_read_json_if_present(args.product_delivery_evidence_json),
        product_pilot_packet=_read_json_if_present(args.product_pilot_packet_json),
        product_execution_approval_gate_packet=_read_json_if_present(args.product_execution_approval_gate_json),
        product_license_decision_gate_packet=_read_json_if_present(args.product_license_decision_gate_json),
        product_license_decision_packet=_read_json_if_present(args.product_license_decision_packet_json),
        product_license_file_creation_work_order_packet=_read_json_if_present(args.product_license_file_creation_work_order_json),
        product_release_operations_dossier_packet=_read_json_if_present(args.product_release_operations_dossier_json),
        product_cli_status_packet=build_product_cli_all_status(),
        product_goal_completion_audit_packet=_read_json_if_present(args.product_goal_completion_audit_json),
        goal_release_decision_gate_packet=_read_json_if_present(args.goal_release_decision_gate_json),
        goal_release_burndown_work_order_packet=_read_json_if_present(args.goal_release_burndown_work_order_json),
        cameo_runtime_repair_work_order_packet=_read_json_if_present(args.cameo_runtime_repair_work_order_json),
        cameo_validation_operations_dossier_packet=_read_json_if_present(args.cameo_validation_operations_dossier_json),
        cameo_cli_status_packet=build_cameo_cli_all_status(),
        cameo_official_results_intake_gate_packet=_read_json_if_present(args.cameo_official_results_intake_gate_json),
        cameo_public_registration_approval_gate_packet=_read_json_if_present(args.cameo_public_registration_approval_gate_json),
        cameo_input_kit_packet=_read_json_if_present(args.cameo_input_kit_json),
        cameo_input_validation_packet=_read_json_if_present(args.cameo_input_validation_json),
        cameo_repair_preflight_packet=_read_json_if_present(args.cameo_repair_preflight_json),
        transition_cleanup_preflight_packet=_read_json_if_present(args.transition_cleanup_preflight_json),
        ligand_cleanup_preflight_packet=_read_json_if_present(args.ligand_cleanup_preflight_json),
        large_cleanup_drilldown_packet=_read_json_if_present(args.large_cleanup_drilldown_json),
        protected_cleanup_review_packet=_read_json_if_present(args.protected_cleanup_review_json),
        protected_ligand_heavy_deep_review_packet=_read_json_if_present(args.protected_ligand_heavy_deep_review_json),
        protected_cleanup_policy_decision_gate_packet=_read_json_if_present(args.protected_cleanup_policy_decision_gate_json),
        cleanup_cli_status_packet=build_cleanup_cli_all_status(),
        cleanup_snapshot_preflight_packet=_read_json_if_present(args.cleanup_snapshot_preflight_json),
        cleanup_payload_manifest_lock_packet=_read_json_if_present(args.cleanup_payload_manifest_lock_json),
        cleanup_postcheck_contract_packet=_read_json_if_present(args.cleanup_postcheck_contract_json),
        cleanup_execution_approval_dossier_packet=_read_json_if_present(args.cleanup_execution_approval_dossier_json),
        cleanup_execution_approval_gate_packet=_read_json_if_present(args.cleanup_execution_approval_gate_json),
        cleanup_completion_gate_packet=_read_json_if_present(args.cleanup_completion_gate_json),
        goal_operator_intake_kit_packet=_read_json_if_present(args.goal_operator_intake_kit_json),
        engine_refinement_claim_action_board_rows=_read_csv_if_present(
            args.engine_refinement_claim_action_board_csv
        ),
        rollup_path=args.rollup_json,
        product_preflight_path=args.product_preflight_json,
        product_bundle_contract_path=args.product_bundle_contract_json,
        product_delivery_evidence_path=args.product_delivery_evidence_json,
        product_pilot_packet_path=args.product_pilot_packet_json,
        product_execution_approval_gate_path=args.product_execution_approval_gate_json,
        product_license_decision_gate_path=args.product_license_decision_gate_json,
        product_license_decision_packet_path=args.product_license_decision_packet_json,
        product_license_file_creation_work_order_path=args.product_license_file_creation_work_order_json,
        product_release_operations_dossier_path=args.product_release_operations_dossier_json,
        product_goal_completion_audit_path=args.product_goal_completion_audit_json,
        goal_release_decision_gate_path=args.goal_release_decision_gate_json,
        goal_release_burndown_work_order_path=args.goal_release_burndown_work_order_json,
        cameo_runtime_repair_work_order_path=args.cameo_runtime_repair_work_order_json,
        cameo_validation_operations_dossier_path=args.cameo_validation_operations_dossier_json,
        cameo_official_results_intake_gate_path=args.cameo_official_results_intake_gate_json,
        cameo_public_registration_approval_gate_path=args.cameo_public_registration_approval_gate_json,
        cameo_input_kit_path=args.cameo_input_kit_json,
        cameo_input_validation_path=args.cameo_input_validation_json,
        cameo_repair_preflight_path=args.cameo_repair_preflight_json,
        transition_cleanup_preflight_path=args.transition_cleanup_preflight_json,
        ligand_cleanup_preflight_path=args.ligand_cleanup_preflight_json,
        large_cleanup_drilldown_path=args.large_cleanup_drilldown_json,
        protected_cleanup_review_path=args.protected_cleanup_review_json,
        protected_ligand_heavy_deep_review_path=args.protected_ligand_heavy_deep_review_json,
        protected_cleanup_policy_decision_gate_path=args.protected_cleanup_policy_decision_gate_json,
        cleanup_snapshot_preflight_path=args.cleanup_snapshot_preflight_json,
        cleanup_payload_manifest_lock_path=args.cleanup_payload_manifest_lock_json,
        cleanup_postcheck_contract_path=args.cleanup_postcheck_contract_json,
        cleanup_execution_approval_dossier_path=args.cleanup_execution_approval_dossier_json,
        cleanup_execution_approval_gate_path=args.cleanup_execution_approval_gate_json,
        cleanup_completion_gate_path=args.cleanup_completion_gate_json,
        goal_operator_intake_kit_path=args.goal_operator_intake_kit_json,
        engine_refinement_claim_action_board_path=args.engine_refinement_claim_action_board_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
