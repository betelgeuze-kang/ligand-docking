#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE_GATE_JSON = "runs/goal_release_decision_gate_current.json"
DEFAULT_OPERATOR_ACTION_BOARD_JSON = "runs/goal_operator_action_board_current.json"
DEFAULT_PRODUCT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_PRODUCT_GATE_REPAIR_JSON = "runs/product_operational_gate_repair_work_order_current.json"
DEFAULT_PRODUCT_WORK_ORDER_JSON = "runs/product_execution_work_order_current.json"
DEFAULT_PRODUCT_PILOT_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON = "runs/product_public_benchmark_work_order_current.json"
DEFAULT_PRODUCT_LICENSE_DECISION_PACKET_JSON = "runs/product_license_decision_packet_current.json"
DEFAULT_PRODUCT_AI_ARCHITECTURE_BACKLOG_JSON = "runs/product_ai_architecture_execution_backlog_current.json"
DEFAULT_PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_JSON = "runs/product_production_ai_gpu_return_intake_current.json"
DEFAULT_CAMEO_VALIDATION_REPAIR_JSON = "runs/cameo_validation_repair_work_order_current.json"
DEFAULT_CAMEO_RUNTIME_REPAIR_JSON = "runs/cameo_runtime_repair_work_order_current.json"
DEFAULT_CAMEO_CAPABILITY_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON = "runs/transition_cleanup_work_order_current.json"
DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON = "runs/ligand_heavy_cleanup_work_order_current.json"
DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON = "runs/cleanup_postcheck_contract_current.json"
DEFAULT_OUT_JSON = "runs/goal_release_burndown_work_order_current.json"
DEFAULT_OUT_CSV = "runs/goal_release_burndown_work_order_current.csv"
DEFAULT_OUT_MD = "runs/goal_release_burndown_work_order_current.md"

CLAIM_BOUNDARY = (
    "Goal release burndown work order only; it maps release gate blockers to existing operator-reviewed artifacts, "
    "approval tokens, and local refresh commands. It does not run docking, rebuild CAMEO artifacts, install packages, "
    "register a CAMEO server, submit predictions, send email, delete, archive, externalize, upload, commit, push, or "
    "mutate external state."
)

PRODUCTION_AI_FORCE_RETURN_REFRESH_COMMAND = " && ".join(
    [
        "python3 tools/build_residual_force_trajectory_regeneration_queue.py",
        "python3 tools/build_residual_force_gpu_worker_return_manifest_template.py",
        "python3 tools/build_residual_force_gpu_worker_return_summary_template.py",
        "python3 tools/build_residual_force_gpu_worker_handoff_package.py",
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
        "python3 tools/build_product_production_ai_gpu_return_intake.py",
        "python3 tools/build_residual_force_derivation_validation.py",
        "python3 tools/build_residual_energy_force_label_validation.py",
        "python3 tools/build_residual_energy_force_label_evidence_work_order.py",
        "python3 tools/build_residual_uncertainty_policy_evidence_contract.py",
        "python3 tools/build_residual_production_training_data_contract.py",
        "python3 tools/train_residual_production_score_model.py",
        "python3 tools/build_residual_production_checkpoint_sidecar.py",
        "python3 tools/build_residual_production_checkpoint_preflight.py",
        "python3 tools/build_residual_production_checkpoint_work_order.py",
        "python3 tools/build_residual_model_registry.py",
        "python3 tools/build_product_ai_architecture_execution_backlog.py",
        "python3 tools/build_product_ai_architecture_gap_closure.py",
        "python3 tools/build_goal_readiness_rollup.py",
        "python3 tools/build_goal_release_decision_gate.py",
        "python3 tools/build_goal_release_burndown_work_order.py",
        "python3 tools/build_goal_bottleneck_briefing.py",
        "python3 tools/build_product_goal_completion_audit.py",
    ]
)

PRODUCT_AI_SCOPE_CLOSURE_REFRESH_COMMAND = " && ".join(
    [
        "python3 tools/build_transporter_local_crosscheck_triage_packet.py",
        "python3 tools/build_transporter_slot_assignment_candidate_workbook.py",
        "python3 tools/build_transporter_manual_review_intake_template.py",
        "python3 tools/build_pxr_blocked_row_promotion_gate.py",
        "python3 tools/build_pxr_authoritative_reconciliation_packet.py",
        "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
        "python3 tools/build_product_scope_breadth_evidence_intake_readiness.py",
        "python3 tools/build_product_scope_breadth_contract.py",
        "python3 tools/build_product_scope_breadth_closure_checklist.py",
        "python3 tools/build_product_ai_architecture_execution_backlog.py",
        "python3 tools/build_product_ai_architecture_gap_closure.py",
        "python3 tools/build_goal_readiness_rollup.py",
        "python3 tools/build_goal_release_decision_gate.py",
        "python3 tools/build_goal_release_burndown_work_order.py",
        "python3 tools/build_goal_bottleneck_briefing.py",
        "python3 tools/build_product_goal_completion_audit.py",
    ]
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


def _first_command(packet: dict[str, Any], step: str = "") -> str:
    for row in _rows(packet):
        if step and _text(row.get("step")) != step:
            continue
        command = _text(row.get("command"))
        if command:
            return command
    return ""


def _first_approval_token(*packets: dict[str, Any]) -> str:
    for packet in packets:
        summary = _summary(packet)
        token = _text(summary.get("approval_token_required") or summary.get("registration_approval_token_required"))
        if token:
            return token
        for row in _rows(packet):
            token = _text(row.get("approval_token_required") or row.get("approval_token"))
            if token:
                return token
    return ""


def _join_tokens(*tokens: str) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for token_group in tokens:
        for token in _split_tokens(token_group):
            if token not in seen:
                seen.add(token)
                ordered.append(token)
    return ";".join(ordered)


def _split_tokens(token_group: str) -> list[str]:
    return [token.strip() for token in _text(token_group).split(";") if token.strip()]


def _operator_action_token(packet: dict[str, Any], *, lane_id: str = "", action_type: str = "") -> str:
    for row in _rows(packet):
        if lane_id and _text(row.get("lane_id")) != lane_id:
            continue
        if action_type and _text(row.get("action_type")) != action_type:
            continue
        token = _text(row.get("approval_token_required") or row.get("approval_token"))
        if token:
            return token
    return ""


def _operator_action_artifact(packet: dict[str, Any], *, lane_id: str = "", action_type: str = "") -> str:
    for row in _rows(packet):
        if lane_id and _text(row.get("lane_id")) != lane_id:
            continue
        if action_type and _text(row.get("action_type")) != action_type:
            continue
        artifact = _text(row.get("artifact_path"))
        if artifact:
            return artifact
    return ""


def _operator_action_command(packet: dict[str, Any], *, lane_id: str = "", action_type: str = "") -> str:
    for row in _rows(packet):
        if lane_id and _text(row.get("lane_id")) != lane_id:
            continue
        if action_type and _text(row.get("action_type")) != action_type:
            continue
        command = _text(row.get("command"))
        if command:
            return command
    return ""


def _license_local_source_command_examples(packet: dict[str, Any]) -> list[str]:
    examples: list[str] = []
    seen: set[str] = set()
    for row in _rows(packet):
        command = _text(row.get("operator_intake_fill_command_local_source_example"))
        if command and command not in seen:
            seen.add(command)
            examples.append(command)
    return examples


def _license_text_source_from_fill_command(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        return "OPERATOR_APPROVED_LICENSE_TEXT_FILE"
    for index, part in enumerate(parts):
        if part == "--license-text-source" and index + 1 < len(parts):
            return parts[index + 1]
    return "OPERATOR_APPROVED_LICENSE_TEXT_FILE"


def _license_file_write_command(license_text_source: str) -> str:
    return (
        "APPROVE_PRODUCT_LICENSE_FILE_CREATION=1 python3 tools/write_product_license_file.py "
        "--work-order-json runs/product_license_file_creation_work_order_current.json "
        f"--license-template {shlex.quote(license_text_source)} "
        "--out LICENSE"
    )


def _license_approval_full_command(fill_command: str, refresh_before_write: str, refresh_after_write: str) -> str:
    license_text_source = _license_text_source_from_fill_command(fill_command)
    return " && ".join(
        [
            fill_command,
            refresh_before_write,
            _license_file_write_command(license_text_source),
            refresh_after_write,
        ]
    )


def _row(
    *,
    sequence: int,
    phase: str,
    lane_id: str,
    release_check: str,
    release_observed: str,
    release_required: str,
    burndown_status: str,
    source_artifact: str,
    approval_token_required: str = "",
    recommended_action: str = "",
    command: str = "",
    reason: str = "",
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "phase": phase,
        "lane_id": lane_id,
        "release_check": release_check,
        "release_check_count": 1,
        "release_observed": release_observed,
        "release_required": release_required,
        "burndown_status": burndown_status,
        "source_artifact": source_artifact,
        "approval_token_required": approval_token_required,
        "recommended_action": recommended_action,
        "command": command,
        "reason": reason,
        "requires_operator_action": True,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _merge_burndown_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            _text(row.get("phase")),
            _text(row.get("lane_id")),
            _text(row.get("burndown_status")),
            _text(row.get("approval_token_required")),
            _text(row.get("command")),
            _text(row.get("source_artifact")),
        )
        current = by_key.get(key)
        if current is None:
            clone = dict(row)
            clone["release_checks"] = _text(row.get("release_check"))
            check = _text(row.get("release_check"))
            clone["release_observed"] = f"{check}={_text(row.get('release_observed'))}" if check else _text(row.get("release_observed"))
            clone["release_required"] = f"{check}={_text(row.get('release_required'))}" if check else _text(row.get("release_required"))
            clone["reason"] = f"{check}: {_text(row.get('reason'))}" if check else _text(row.get("reason"))
            by_key[key] = clone
            merged.append(clone)
            continue
        check = _text(row.get("release_check"))
        current["release_check_count"] = _int(current.get("release_check_count")) + 1
        current["release_checks"] = ";".join(part for part in (_text(current.get("release_checks")), check) if part)
        current["release_check"] = current["release_checks"]
        current["release_observed"] = "; ".join(
            part
            for part in (
                _text(current.get("release_observed")),
                f"{check}={_text(row.get('release_observed'))}",
            )
            if part
        )
        current["release_required"] = "; ".join(
            part
            for part in (
                _text(current.get("release_required")),
                f"{check}={_text(row.get('release_required'))}",
            )
            if part
        )
        current["reason"] = "; ".join(
            part
            for part in (
                _text(current.get("reason")),
                f"{check}: {_text(row.get('reason'))}",
            )
            if part
        )
    for sequence, row in enumerate(merged, start=1):
        row["sequence"] = sequence
    return merged


def _phase_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    order = {
        "P0_product_ai_architecture_production_inference_closure": 0,
        "P0_product_ai_architecture_scope_closure": 1,
        "P1_product_execution_and_bundle_validation": 10,
        "P1_product_commercial_independence": 11,
        "P2_cameo_official_validation_and_registration": 20,
        "P3_cleanup_execution_or_policy_resolution": 30,
        "P4_refresh_release_evidence": 40,
    }
    return (order.get(_text(row.get("phase")), 99), _int(row.get("sequence")))


def _next_required_step(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Release burndown is clear; refresh the release decision gate before any completion claim."

    items: list[str] = []

    def add(item: str) -> None:
        if item not in items:
            items.append(item)

    for row in rows:
        phase = _text(row.get("phase"))
        status = _text(row.get("burndown_status"))
        token = _text(row.get("approval_token_required"))
        if phase == "P1_product_execution_and_bundle_validation":
            add("P1 product execution/bundle validation")
        elif phase == "P0_product_ai_architecture_production_inference_closure":
            add("P0 product AI production inference closure")
        elif phase == "P0_product_ai_architecture_scope_closure":
            add("P0 product AI architecture scope closure")
        elif phase == "P1_product_commercial_independence":
            add("P1 commercial license/independence")
        elif phase == "P2_cameo_official_validation_and_registration":
            if status == "official_results_required":
                add("P2 official CAMEO evidence")
            if "APPROVE_API_DEPENDENCY_INSTALL" in token:
                add("P2 CAMEO runtime repair")
            elif token:
                add("P2 CAMEO registration/email approval")
        elif phase == "P3_cleanup_execution_or_policy_resolution":
            add("P3 cleanup completion/policy/postcheck")
        elif phase == "P4_refresh_release_evidence":
            add("P4 release evidence refresh")

    if "P4 release evidence refresh" in items:
        return f"Burn down {', '.join(items)}."
    return f"Burn down {', '.join(items)}, then refresh release evidence."


def _product_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    product_preflight: dict[str, Any],
    product_gate_repair: dict[str, Any],
    product_work_order: dict[str, Any],
    product_pilot_packet: dict[str, Any],
    public_benchmark_work_order: dict[str, Any],
    product_preflight_path: str,
    product_gate_repair_path: str,
    product_work_order_path: str,
    product_pilot_path: str,
    public_benchmark_work_order_path: str,
) -> dict[str, Any]:
    preflight = _summary(product_preflight)
    pilot = _summary(product_pilot_packet)
    preflight_status = _text(preflight.get("status"))
    preflight_ready = (not preflight_status) or preflight_status == "product_execution_preflight_ready"
    pilot_delivery_ready = bool(pilot.get("pilot_delivery_ready") is True)
    token = _first_approval_token(product_work_order) if preflight_ready else ""
    preflight_gate_status = _text(preflight.get("operational_gate_feasibility_status"))
    preflight_blocker_count = _int(preflight.get("blocker_count"))
    gate_repair = _summary(product_gate_repair)
    gate_repair_required = bool(gate_repair.get("repair_required") is True)
    additional_eval_needed = _int(gate_repair.get("additional_eval_unique_keys_needed"))
    additional_negative_needed = _int(gate_repair.get("additional_negative_keys_needed"))
    required_negative_at_gate_min = _int(gate_repair.get("required_negative_keys_at_gate_min"))
    gate_min_eval = _int(gate_repair.get("gate_min_eval_unique_keys"))
    source_artifact = f"{product_work_order_path};{product_pilot_path}"
    burndown_status = "approval_required"
    recommended_action = "Review and approve product execution, then assemble and validate the product local-delivery bundle before refreshing pilot evidence."
    command = _first_command(product_work_order, "execution") or _first_command(product_work_order)
    reason = _text(release_row.get("reason"))
    public_benchmark = _summary(public_benchmark_work_order)
    public_benchmark_continuous_command = _text(public_benchmark.get("continuous_validation_command"))
    public_benchmark_result_generation_token = _text(public_benchmark.get("result_generation_approval_token_required"))
    public_benchmark_refresh_command = (
        "python3 tools/build_product_public_benchmark_work_order.py && "
        "python3 tools/build_product_public_benchmark_contract.py && "
        "python3 tools/build_product_commercial_independence_gate.py && "
        "python3 tools/build_product_architecture_contract.py && "
        "python3 tools/build_product_release_operations_dossier.py && "
        "python3 tools/build_goal_release_decision_gate.py && "
        "python3 tools/build_goal_release_burndown_work_order.py && "
        "python3 tools/build_goal_bottleneck_briefing.py && "
        "python3 tools/build_product_goal_completion_audit.py"
    )
    if (
        preflight_ready
        and pilot_delivery_ready
        and _text(release_row.get("check")) == "product_architecture_release_ready"
    ):
        token = ""
        burndown_status = "blocked_until_public_benchmark_validation"
        recommended_action = (
            "Product docking execution, bundle assembly, and pilot delivery evidence are ready; run the public "
            "benchmark continuous-validation chain, attach scorecard evidence, then refresh release gates."
        )
        command = public_benchmark_continuous_command or public_benchmark_refresh_command
        source_artifact = f"{source_artifact};{public_benchmark_work_order_path}"
        reason = (
            f"{reason}; product_pilot_delivery_ready=True, product_execution_no_longer_blocks_this_check=True, "
            f"public_benchmark_work_order_status={_text(public_benchmark.get('status')) or 'missing'}, "
            f"public_benchmark_continuous_validation_command_count={_int(public_benchmark.get('continuous_validation_command_count'))}, "
            f"public_benchmark_suite_run_command_count={_int(public_benchmark.get('suite_run_command_count'))}, "
            f"public_benchmark_suite_blocker_count={_int(public_benchmark.get('suite_blocker_count'))}, "
            f"public_benchmark_suite_threshold_count={_int(public_benchmark.get('suite_threshold_count'))}, "
            f"public_benchmark_suite_materialization_manifest_count={_int(public_benchmark.get('suite_materialization_manifest_count'))}, "
            f"public_benchmark_suite_materialization_run_command_count={_int(public_benchmark.get('suite_materialization_run_command_count'))}, "
            f"public_benchmark_suite_scorecard_command_count={_int(public_benchmark.get('suite_scorecard_command_count'))}, "
            f"public_benchmark_suite_scorecard_row_csv_count={_int(public_benchmark.get('suite_scorecard_row_csv_count'))}, "
            f"public_benchmark_suite_no_external_dependency_count={_int(public_benchmark.get('suite_no_external_dependency_count'))}, "
            f"public_benchmark_local_artifact_preflight_blocked_suite_count={_int(public_benchmark.get('local_artifact_preflight_blocked_suite_count'))}, "
            f"public_benchmark_missing_local_input_artifact_count={_int(public_benchmark.get('missing_local_input_artifact_count'))}, "
            f"public_benchmark_missing_local_output_artifact_count={_int(public_benchmark.get('missing_local_output_artifact_count'))}, "
            f"public_benchmark_result_generation_required_suite_count={_int(public_benchmark.get('result_generation_required_suite_count'))}, "
            f"public_benchmark_result_generation_approval_token_required={public_benchmark_result_generation_token or 'none'}"
        )
        if public_benchmark_result_generation_token:
            token = public_benchmark_result_generation_token
    if not preflight_ready:
        source_artifact = f"{product_preflight_path};{product_gate_repair_path};{source_artifact}" if gate_repair else f"{product_preflight_path};{source_artifact}"
        burndown_status = "operator_action_required"
        recommended_action = (
            (
                f"Repair the product operational eval panel to at least {gate_min_eval} unique eval keys with at least "
                f"{required_negative_at_gate_min} negative/decoy keys ({additional_eval_needed} total eval additions, "
                f"{additional_negative_needed} more negative/decoy keys), then rebuild preflight, approval gate, product "
                "release dossier, and goal burndown."
            )
            if gate_repair_required
            else (
                "Repair product execution preflight before approval: align operational gate thresholds with the eval split "
                "or switch to a validation dataset that can satisfy the configured gate; then rebuild preflight, approval gate, "
                "product release dossier, and goal burndown."
            )
        )
        command = (
            "python3 tools/build_product_execution_preflight.py && "
            "python3 tools/product/build_product_operational_gate_repair_work_order.py && "
            "python3 tools/build_product_execution_approval_gate.py && python3 tools/build_product_release_operations_dossier.py && "
            "python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py"
        )
        reason = (
            f"{reason}; product_execution_preflight_status={preflight_status or 'missing'}, "
            f"preflight_blocker_count={preflight_blocker_count}, "
            f"operational_gate_feasibility_status={preflight_gate_status or 'not_checked'}, "
            f"gate_repair_required={gate_repair_required}, additional_eval_unique_keys_needed={additional_eval_needed}, "
            f"additional_negative_keys_needed={additional_negative_needed}"
        )
    return _row(
        sequence=sequence,
        phase="P1_product_execution_and_bundle_validation",
        lane_id=_text(release_row.get("lane_id")),
        release_check=_text(release_row.get("check")),
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status=burndown_status,
        source_artifact=source_artifact,
        approval_token_required=token,
        recommended_action=recommended_action,
        command=command,
        reason=reason,
    )


def _product_independence_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    operator_action_board: dict[str, Any],
    product_license_decision_packet: dict[str, Any],
    operator_action_board_path: str,
    product_license_decision_packet_path: str,
) -> dict[str, Any]:
    artifact = _text(release_row.get("artifact_path")) or "runs/product_commercial_independence_gate_current.json"
    token = _operator_action_token(
        operator_action_board,
        lane_id="commercial_product_license",
        action_type="fill_product_license_decision",
    )
    fill_command = _operator_action_command(
        operator_action_board,
        lane_id="commercial_product_license",
        action_type="fill_product_license_decision",
    )
    refresh_command = (
        "python3 tools/build_product_license_decision_gate.py && "
        "python3 tools/build_product_license_file_creation_work_order.py"
    )
    refresh_after_write_command = (
        "python3 tools/build_product_commercial_independence_gate.py && "
        "python3 tools/build_product_release_operations_dossier.py && "
        "python3 tools/build_goal_release_decision_gate.py && "
        "python3 tools/build_goal_release_burndown_work_order.py && "
        "python3 tools/build_goal_bottleneck_briefing.py && "
        "python3 tools/build_product_goal_completion_audit.py"
    )
    license_packet_summary = _summary(product_license_decision_packet)
    local_source_examples = _license_local_source_command_examples(product_license_decision_packet)
    full_local_source_examples = [
        _license_approval_full_command(example, refresh_command, refresh_after_write_command)
        for example in local_source_examples
    ]
    generic_fill_command = fill_command or (
        "python3 tools/fill_product_license_decision_operator_intake.py "
        "--approval-token APPROVE_PRODUCT_LICENSE_FILE_CREATION "
        "--spdx-license-id OPERATOR_FILL_SPDX "
        "--license-text-source OPERATOR_APPROVED_LICENSE_TEXT_FILE "
        "--copyright-holder OPERATOR_FILL_HOLDER "
        "--effective-year OPERATOR_FILL_YEAR "
        "--out-csv runs/product_license_decision_operator_intake.csv"
    )
    row = _row(
        sequence=sequence,
        phase="P1_product_commercial_independence",
        lane_id=_text(release_row.get("lane_id")),
        release_check=_text(release_row.get("check")),
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status="approval_required" if token else "implementation_required",
        source_artifact=f"{artifact};{operator_action_board_path};{product_license_decision_packet_path}" if token else artifact,
        approval_token_required=token,
        recommended_action=(
            "Fill the product license decision operator intake with the exact approval token, SPDX/source, holder, "
            "and year before any LICENSE file creation review; then rebuild the license, commercial-independence, "
            "product release, and goal release gates."
            if token
            else "Resolve commercial-independence blockers: add license evidence, pin core runtime dependencies, "
            "move external API SDKs out of requirements.txt, then rebuild the commercial-independence and release gates."
        ),
        command=(
            _license_approval_full_command(generic_fill_command, refresh_command, refresh_after_write_command)
            if token
            else "python3 tools/build_product_commercial_independence_gate.py && python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py"
        ),
        reason=_text(release_row.get("reason")),
    )
    row["license_decision_packet_status"] = _text(license_packet_summary.get("status"))
    row["ready_local_license_text_source_candidate_count"] = _int(
        license_packet_summary.get("ready_local_license_text_source_candidate_count")
    )
    row["license_local_source_command_example_count"] = len(local_source_examples)
    row["license_local_source_command_examples"] = " || ".join(full_local_source_examples)
    return row


def _primary_architecture_backlog_row(backlog_packet: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(backlog_packet)
    primary_id = _text(summary.get("primary_work_item_id"))
    rows = _rows(backlog_packet)
    for row in rows:
        if primary_id and _text(row.get("work_item_id")) == primary_id:
            return row
    return rows[0] if rows else {}


def _architecture_backlog_detail(backlog_packet: dict[str, Any]) -> str:
    summary = _summary(backlog_packet)
    primary = _primary_architecture_backlog_row(backlog_packet)
    if not summary and not primary:
        return ""
    return (
        f"architecture_backlog_status={summary.get('status')};"
        f"architecture_backlog_work_item_count={summary.get('work_item_count')};"
        f"architecture_backlog_primary_work_item_id={summary.get('primary_work_item_id')};"
        f"architecture_backlog_primary_observed={_text(primary.get('observed'))};"
        f"architecture_backlog_primary_next_action={_text(primary.get('next_action'))}"
    )


def _product_ai_architecture_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    architecture_backlog_packet: dict[str, Any] | None = None,
    architecture_backlog_path: str = DEFAULT_PRODUCT_AI_ARCHITECTURE_BACKLOG_JSON,
    production_ai_gpu_return_intake_path: str = DEFAULT_PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_JSON,
) -> dict[str, Any]:
    observed = _text(release_row.get("observed"))
    backlog_detail = _architecture_backlog_detail(architecture_backlog_packet or {})
    observed_with_backlog = observed + (f";{backlog_detail}" if backlog_detail else "")
    production_inference_primary = (
        "current_primary_open_gap=production_ai_inference_checkpoint" in observed_with_backlog
        or "primary_work_item_id=training_data." in observed_with_backlog
        or "primary_work_item_id=checkpoint_work_order." in observed_with_backlog
        or "architecture_backlog_primary_work_item_id=training_data." in observed_with_backlog
        or "architecture_backlog_primary_work_item_id=checkpoint_work_order." in observed_with_backlog
    )
    if production_inference_primary:
        phase = "P0_product_ai_architecture_production_inference_closure"
        burndown_status = "production_ai_checkpoint_evidence_required"
        recommended_action = (
            "Run the full external GPU force-label regeneration, return the identity-preserving summary/manifest, "
            "then close receipt, force derivation, label validation, training-data, production model training, "
            "checkpoint sidecar, checkpoint preflight, registry, and architecture gap evidence before release."
        )
        command = PRODUCTION_AI_FORCE_RETURN_REFRESH_COMMAND
    else:
        phase = "P0_product_ai_architecture_scope_closure"
        burndown_status = "scientific_scope_evidence_required"
        recommended_action = (
            "Close the product AI architecture execution backlog before release, starting with scope breadth atomic "
            "blockers for transporter/PXR/general protein-ligand claims."
        )
        command = PRODUCT_AI_SCOPE_CLOSURE_REFRESH_COMMAND
    source_artifact = (
        _text(release_row.get("artifact_path"))
        or f"runs/product_ai_architecture_gap_closure_current.json;{architecture_backlog_path}"
    )
    if production_inference_primary and production_ai_gpu_return_intake_path not in source_artifact.split(";"):
        source_artifact = f"{source_artifact};{production_ai_gpu_return_intake_path}"
    return _row(
        sequence=sequence,
        phase=phase,
        lane_id=_text(release_row.get("lane_id")),
        release_check=_text(release_row.get("check")),
        release_observed=observed_with_backlog,
        release_required=_text(release_row.get("required")),
        burndown_status=burndown_status,
        source_artifact=source_artifact,
        recommended_action=recommended_action,
        command=command,
        reason=_text(release_row.get("reason")) + (f"; {backlog_detail}" if backlog_detail else ""),
    )


def _cameo_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    validation_repair: dict[str, Any],
    runtime_repair: dict[str, Any],
    capability: dict[str, Any],
    validation_repair_path: str,
    runtime_repair_path: str,
    capability_path: str,
    operator_action_board: dict[str, Any],
    operator_action_board_path: str,
) -> dict[str, Any]:
    check = _text(release_row.get("check"))
    if check == "cameo_public_registration_allowed":
        operator_actions = _summary(operator_action_board)
        receiver_status = _text(operator_actions.get("cameo_cli_receiver_smoke_status"))
        api_install_required = bool(operator_actions.get("cameo_cli_api_install_approval_required") is True)
        runtime_repair_required = api_install_required or bool(receiver_status and receiver_status != "cameo_receiver_smoke_ready")
        capability_summary = _summary(capability)
        if runtime_repair_required:
            token = _first_approval_token(runtime_repair)
            command = _first_command(runtime_repair, "install_or_activate_api_dependency_profile") or _first_command(runtime_repair)
            action = (
                "Repair API dependency and receiver smoke first; only after validation evidence is ready, review "
                "CAMEO registration and outbound-email approval tokens."
            )
        else:
            token = _join_tokens(
                _text(capability_summary.get("registration_approval_token_required")),
                _text(capability_summary.get("outbound_email_approval_token_required")),
            )
            command = ""
            action = "Review CAMEO registration and outbound-email approval only after official validation evidence is ready."
        status = "approval_required"
        source_artifact = f"{validation_repair_path};{runtime_repair_path};{capability_path}"
    elif check == "official_cameo_results_used":
        token = ""
        command = (
            "python3 tools/build_cameo_official_results_intake_gate.py && "
            "python3 tools/build_cameo_performance_scorecard.py --results-csv runs/cameo_official_results_operator_intake.csv && "
            "python3 tools/build_cameo_validation_readiness_gate.py"
        )
        action = (
            "Fill official CAMEO assessment rows, validate the official-results intake gate, rebuild the performance "
            "scorecard with official metrics, then refresh CAMEO validation readiness."
        )
        status = "official_results_required"
        source_artifact = (
            _operator_action_artifact(
                operator_action_board,
                lane_id="cameo_validation",
                action_type="fill_cameo_official_results_intake",
            )
            or f"{validation_repair_path};{operator_action_board_path}"
        )
    else:
        token = ""
        command = (
            "python3 tools/build_cameo_official_results_intake_gate.py && "
            "python3 tools/build_cameo_performance_scorecard.py --results-csv runs/cameo_official_results_operator_intake.csv && "
            "python3 tools/build_cameo_validation_readiness_gate.py"
        )
        action = (
            "Current local CAMEO selection/format/handoff stages are ready; attach official CAMEO result rows and "
            "refresh the performance/readiness artifacts before claiming architecture validation."
        )
        status = "official_results_required"
        source_artifact = (
            _operator_action_artifact(
                operator_action_board,
                lane_id="cameo_validation",
                action_type="fill_cameo_official_results_intake",
            )
            or f"{validation_repair_path};{operator_action_board_path}"
        )
    return _row(
        sequence=sequence,
        phase="P2_cameo_official_validation_and_registration",
        lane_id=_text(release_row.get("lane_id")),
        release_check=check,
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status=status,
        source_artifact=source_artifact,
        approval_token_required=token,
        recommended_action=action,
        command=command,
        reason=_text(release_row.get("reason")),
    )


def _cleanup_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    operator_action_board: dict[str, Any],
    transition_cleanup: dict[str, Any],
    ligand_cleanup: dict[str, Any],
    protected_cleanup: dict[str, Any],
    cleanup_postcheck: dict[str, Any],
    operator_action_board_path: str,
    transition_cleanup_path: str,
    ligand_cleanup_path: str,
    protected_cleanup_path: str,
    cleanup_postcheck_path: str,
) -> dict[str, Any]:
    check = _text(release_row.get("check"))
    if check == "transition_cleanup_complete":
        token = _first_approval_token(transition_cleanup)
        source = transition_cleanup_path
        command = ""
        action = "Review row-specific transition cleanup approvals, snapshot payloads, then execute only the approved archive/externalize/delete rows."
        status = "approval_required"
    elif check == "ligand_heavy_cleanup_complete":
        token = _first_approval_token(ligand_cleanup)
        source = ligand_cleanup_path
        command = _first_command(ligand_cleanup, "execute_after_approval")
        action = "Review stale ligand-heavy trajectory payload candidates, then execute the cleanup command only after explicit approval."
        status = "approval_required"
    elif check == "protected_cleanup_policy_resolved":
        token = ""
        source = protected_cleanup_path
        command = ""
        action = "Keep protected payload rows out of deletion or record an explicit cleanup-policy change before promoting them."
        status = "policy_decision_required"
    elif check == "cleanup_postcheck_contract_ready":
        token = ""
        source = cleanup_postcheck_path
        command = (
            "python3 tools/build_cleanup_postcheck_contract.py && "
            "python3 tools/cleanup/build_cleanup_operations_surface_contract.py && "
            "python3 tools/build_goal_readiness_rollup.py && "
            "python3 tools/build_goal_operator_action_board.py && "
            "python3 tools/build_goal_release_decision_gate.py && "
            "python3 tools/build_goal_release_burndown_work_order.py"
        )
        action = "Refresh the cleanup postcheck contract and goal-level release evidence before any cleanup completion claim."
        status = "postcheck_required"
    else:
        token = ""
        source = operator_action_board_path
        command = ""
        action = "Clear all priority operator action board rows before release; product, CAMEO, and cleanup actions remain open."
        status = "operator_action_required"
    return _row(
        sequence=sequence,
        phase="P3_cleanup_execution_or_policy_resolution",
        lane_id=_text(release_row.get("lane_id")),
        release_check=check,
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status=status,
        source_artifact=source,
        approval_token_required=token,
        recommended_action=action,
        command=command,
        reason=_text(release_row.get("reason")),
    )


def _goal_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    release_gate_path: str,
    operator_action_board_path: str,
) -> dict[str, Any]:
    if _text(release_row.get("check")) == "goal_api_surface_contract_ready":
        return _row(
            sequence=sequence,
            phase="P4_refresh_release_evidence",
            lane_id=_text(release_row.get("lane_id")),
            release_check=_text(release_row.get("check")),
            release_observed=_text(release_row.get("observed")),
            release_required=_text(release_row.get("required")),
            burndown_status="api_contract_refresh_required",
            source_artifact=f"{release_gate_path};runs/goal_api_surface_contract_current.json",
            recommended_action="Refresh the static goal API surface contract, then rebuild the release gate and burndown work order.",
            command="python3 tools/build_goal_api_surface_contract.py && python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py",
            reason=_text(release_row.get("reason")),
        )
    return _row(
        sequence=sequence,
        phase="P4_refresh_release_evidence",
        lane_id=_text(release_row.get("lane_id")),
        release_check=_text(release_row.get("check")),
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status="blocked_until_prior_phases_clear",
        source_artifact=f"{release_gate_path};{operator_action_board_path}",
        recommended_action="After prior blocking phases are cleared, refresh goal rollup, action board, release gate, and this burndown work order.",
        command="python3 tools/build_goal_readiness_rollup.py && python3 tools/build_goal_operator_action_board.py && python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py",
        reason=_text(release_row.get("reason")),
    )


def build_goal_release_burndown_work_order(
    *,
    release_gate_packet: dict[str, Any],
    operator_action_board_packet: dict[str, Any],
    product_work_order_packet: dict[str, Any],
    product_pilot_packet: dict[str, Any],
    cameo_validation_repair_packet: dict[str, Any],
    cameo_runtime_repair_packet: dict[str, Any],
    cameo_capability_packet: dict[str, Any],
    transition_cleanup_work_order_packet: dict[str, Any],
    ligand_cleanup_work_order_packet: dict[str, Any],
    protected_cleanup_review_packet: dict[str, Any],
    cleanup_postcheck_contract_packet: dict[str, Any] | None = None,
    product_preflight_packet: dict[str, Any] | None = None,
    product_gate_repair_packet: dict[str, Any] | None = None,
    public_benchmark_work_order_packet: dict[str, Any] | None = None,
    product_license_decision_packet: dict[str, Any] | None = None,
    product_ai_architecture_backlog_packet: dict[str, Any] | None = None,
    release_gate_path: str = DEFAULT_RELEASE_GATE_JSON,
    operator_action_board_path: str = DEFAULT_OPERATOR_ACTION_BOARD_JSON,
    product_preflight_path: str = DEFAULT_PRODUCT_PREFLIGHT_JSON,
    product_gate_repair_path: str = DEFAULT_PRODUCT_GATE_REPAIR_JSON,
    product_work_order_path: str = DEFAULT_PRODUCT_WORK_ORDER_JSON,
    product_pilot_path: str = DEFAULT_PRODUCT_PILOT_JSON,
    public_benchmark_work_order_path: str = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON,
    product_license_decision_packet_path: str = DEFAULT_PRODUCT_LICENSE_DECISION_PACKET_JSON,
    product_ai_architecture_backlog_path: str = DEFAULT_PRODUCT_AI_ARCHITECTURE_BACKLOG_JSON,
    cameo_validation_repair_path: str = DEFAULT_CAMEO_VALIDATION_REPAIR_JSON,
    cameo_runtime_repair_path: str = DEFAULT_CAMEO_RUNTIME_REPAIR_JSON,
    cameo_capability_path: str = DEFAULT_CAMEO_CAPABILITY_JSON,
    transition_cleanup_work_order_path: str = DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON,
    ligand_cleanup_work_order_path: str = DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON,
    protected_cleanup_review_path: str = DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON,
    cleanup_postcheck_contract_path: str = DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON,
) -> dict[str, Any]:
    release_summary = _summary(release_gate_packet)
    rows: list[dict[str, Any]] = []
    blockers = [row for row in _rows(release_gate_packet) if row.get("release_blocker") is True]

    for sequence, release_row in enumerate(blockers, start=1):
        lane = _text(release_row.get("lane_id"))
        if lane == "commercial_product_release":
            check = _text(release_row.get("check"))
            if check == "product_ai_architecture_gap_closure_ready":
                rows.append(
                    _product_ai_architecture_burndown_row(
                        sequence=sequence,
                        release_row=release_row,
                        architecture_backlog_packet=product_ai_architecture_backlog_packet or {},
                        architecture_backlog_path=product_ai_architecture_backlog_path,
                    )
                )
            elif check == "commercial_independence_gate_ready":
                rows.append(
                    _product_independence_burndown_row(
                        sequence=sequence,
                        release_row=release_row,
                        operator_action_board=operator_action_board_packet,
                        product_license_decision_packet=product_license_decision_packet or {},
                        operator_action_board_path=operator_action_board_path,
                        product_license_decision_packet_path=product_license_decision_packet_path,
                    )
                )
            else:
                rows.append(
                    _product_burndown_row(
                        sequence=sequence,
                        release_row=release_row,
                        product_preflight=product_preflight_packet or {},
                        product_gate_repair=product_gate_repair_packet or {},
                        product_work_order=product_work_order_packet,
                        product_pilot_packet=product_pilot_packet,
                        public_benchmark_work_order=public_benchmark_work_order_packet or {},
                        product_preflight_path=product_preflight_path,
                        product_gate_repair_path=product_gate_repair_path,
                        product_work_order_path=product_work_order_path,
                        product_pilot_path=product_pilot_path,
                        public_benchmark_work_order_path=public_benchmark_work_order_path,
                    )
                )
        elif lane == "cameo_architecture_validation":
            rows.append(
                _cameo_burndown_row(
                    sequence=sequence,
                    release_row=release_row,
                    validation_repair=cameo_validation_repair_packet,
                    runtime_repair=cameo_runtime_repair_packet,
                    capability=cameo_capability_packet,
                    validation_repair_path=cameo_validation_repair_path,
                    runtime_repair_path=cameo_runtime_repair_path,
                    capability_path=cameo_capability_path,
                    operator_action_board=operator_action_board_packet,
                    operator_action_board_path=operator_action_board_path,
                )
            )
        elif lane == "cleanup_release":
            rows.append(
                _cleanup_burndown_row(
                    sequence=sequence,
                    release_row=release_row,
                    operator_action_board=operator_action_board_packet,
                    transition_cleanup=transition_cleanup_work_order_packet,
                    ligand_cleanup=ligand_cleanup_work_order_packet,
                    protected_cleanup=protected_cleanup_review_packet,
                    cleanup_postcheck=cleanup_postcheck_contract_packet or {},
                    operator_action_board_path=operator_action_board_path,
                    transition_cleanup_path=transition_cleanup_work_order_path,
                    ligand_cleanup_path=ligand_cleanup_work_order_path,
                    protected_cleanup_path=protected_cleanup_review_path,
                    cleanup_postcheck_path=cleanup_postcheck_contract_path,
                )
            )
        else:
            rows.append(
                _goal_burndown_row(
                    sequence=sequence,
                    release_row=release_row,
                    release_gate_path=release_gate_path,
                    operator_action_board_path=operator_action_board_path,
                )
            )

    raw_row_count = len(rows)
    rows = sorted(rows, key=_phase_sort_key)
    rows = _merge_burndown_rows(rows)
    approval_tokens = sorted(
        {
            token
            for row in rows
            for token in _split_tokens(_text(row.get("approval_token_required")))
        }
    )
    operator_actions = _summary(operator_action_board_packet)
    primary_action_id = _text(operator_actions.get("primary_action_id"))
    public_benchmark_summary = _summary(public_benchmark_work_order_packet or {})
    product_license_summary = _summary(product_license_decision_packet or {})
    burndown_operator_input_required_work_item_count = sum(
        1 for row in rows if row.get("burndown_status") == "operator_input_required"
    )
    intake_current_action_required_count = _int(operator_actions.get("goal_operator_intake_kit_current_action_required_count"))
    summary = {
        "packet_type": "goal_release_burndown_work_order",
        "status": "goal_release_burndown_clear" if not rows else "goal_release_burndown_work_order_ready",
        "source_release_gate_status": _text(release_summary.get("status")),
        "source_release_allowed": bool(release_summary.get("release_allowed") is True),
        "source_release_blocker_count": _int(release_summary.get("blocker_count")),
        "release_blocker_check_count": raw_row_count,
        "work_item_count": len(rows),
        "approval_required_item_count": sum(1 for row in rows if _text(row.get("approval_token_required"))),
        "operator_input_required_item_count": intake_current_action_required_count
        or burndown_operator_input_required_work_item_count,
        "burndown_operator_input_required_work_item_count": burndown_operator_input_required_work_item_count,
        "official_results_required_item_count": sum(1 for row in rows if row.get("burndown_status") == "official_results_required"),
        "policy_decision_required_item_count": sum(1 for row in rows if row.get("burndown_status") == "policy_decision_required"),
        "postcheck_required_item_count": sum(1 for row in rows if row.get("burndown_status") == "postcheck_required"),
        "approval_tokens_required": approval_tokens,
        "approval_token_count": len(approval_tokens),
        "operator_action_count": _int(operator_actions.get("action_count")),
        "primary_action_id": primary_action_id,
        "top_action_id": _text(operator_actions.get("top_action_id")) or primary_action_id,
        "primary_action_priority": _int(operator_actions.get("primary_action_priority")),
        "primary_action_lane_id": _text(operator_actions.get("primary_action_lane_id")),
        "primary_action_type": _text(operator_actions.get("primary_action_type")),
        "primary_action_status": _text(operator_actions.get("primary_action_status")),
        "primary_action_required_input": _text(operator_actions.get("primary_action_required_input")),
        "primary_action_artifact_path": _text(operator_actions.get("primary_action_artifact_path")),
        "primary_action_command": _text(operator_actions.get("primary_action_command")),
        "primary_action_recommended_action": _text(operator_actions.get("primary_action_recommended_action")),
        "parallel_product_action_count": _int(operator_actions.get("parallel_product_action_count")),
        "parallel_product_action_ids": operator_actions.get("parallel_product_action_ids") or [],
        "first_parallel_product_action_id": _text(operator_actions.get("first_parallel_product_action_id")),
        "first_parallel_product_action_lane_id": _text(operator_actions.get("first_parallel_product_action_lane_id")),
        "first_parallel_product_action_type": _text(operator_actions.get("first_parallel_product_action_type")),
        "first_parallel_product_action_required_input": _text(
            operator_actions.get("first_parallel_product_action_required_input")
        ),
        "first_parallel_product_action_artifact_path": _text(
            operator_actions.get("first_parallel_product_action_artifact_path")
        ),
        "first_parallel_product_action_recommended_action": _text(
            operator_actions.get("first_parallel_product_action_recommended_action")
        ),
        "first_parallel_product_action_primary_action_id": _text(
            operator_actions.get("first_parallel_product_action_primary_action_id")
        ),
        "first_parallel_product_action_precondition": _text(
            operator_actions.get("first_parallel_product_action_precondition")
        ),
        "goal_operator_intake_kit_status": _text(operator_actions.get("goal_operator_intake_kit_status")),
        "goal_operator_intake_kit_json": _text(operator_actions.get("goal_operator_intake_kit_json")),
        "goal_operator_intake_kit_operator_input_required_count": _int(
            operator_actions.get("goal_operator_intake_kit_operator_input_required_count")
        ),
        "goal_operator_intake_kit_release_burndown_linked_entry_count": _int(
            operator_actions.get("goal_operator_intake_kit_release_burndown_linked_entry_count")
        ),
        "goal_operator_intake_kit_current_action_required_count": intake_current_action_required_count,
        "goal_operator_intake_kit_deferred_operator_input_count": _int(
            operator_actions.get("goal_operator_intake_kit_deferred_operator_input_count")
        ),
        "goal_operator_intake_kit_approval_token_count": _int(
            operator_actions.get("goal_operator_intake_kit_approval_token_count")
        ),
        "goal_operator_intake_kit_current_action_approval_token_count": _int(
            operator_actions.get("goal_operator_intake_kit_current_action_approval_token_count")
        ),
        "goal_operator_intake_kit_current_action_approval_tokens": operator_actions.get(
            "goal_operator_intake_kit_current_action_approval_tokens"
        )
        or [],
        "approval_reclaim_size_gb": round(_float(operator_actions.get("approval_reclaim_size_gb")), 3),
        "product_cli_status_set_status": _text(operator_actions.get("product_cli_status_set_status")),
        "product_cli_approval_token_count": _int(operator_actions.get("product_cli_approval_token_count")),
        "product_cli_operations_blocked_stage_count": _int(operator_actions.get("product_cli_operations_blocked_stage_count")),
        "product_cli_operational_quality_ready": bool(operator_actions.get("product_cli_operational_quality_ready") is True),
        "product_operational_quality_ready": bool(
            operator_actions.get("product_cli_operational_quality_ready") is True
            or operator_actions.get("product_release_operations_operational_quality_ready") is True
        ),
        "product_operational_quality_status": _text(
            operator_actions.get("product_release_operations_source_operational_quality_status")
        ),
        "product_operational_quality_blocker_count": _int(
            operator_actions.get("product_release_operations_operational_quality_blocker_count")
        ),
        "product_cli_authorized_for_execution": bool(operator_actions.get("product_cli_authorized_for_execution") is True),
        "product_cli_bundle_validation_passed": bool(operator_actions.get("product_cli_bundle_validation_passed") is True),
        "product_cli_delivery_ready_claim_allowed": bool(operator_actions.get("product_cli_delivery_ready_claim_allowed") is True),
        "product_gate_repair_status": _text(_summary(product_gate_repair_packet or {}).get("status")),
        "product_gate_repair_required": bool(_summary(product_gate_repair_packet or {}).get("repair_required") is True),
        "product_gate_repair_additional_eval_unique_keys_needed": _int(
            _summary(product_gate_repair_packet or {}).get("additional_eval_unique_keys_needed")
        ),
        "product_gate_repair_additional_negative_keys_needed": _int(
            _summary(product_gate_repair_packet or {}).get("additional_negative_keys_needed")
        ),
        "public_benchmark_work_order_status": _text(public_benchmark_summary.get("status")),
        "public_benchmark_continuous_validation_command_count": _int(
            public_benchmark_summary.get("continuous_validation_command_count")
        ),
        "public_benchmark_suite_run_command_count": _int(public_benchmark_summary.get("suite_run_command_count")),
        "public_benchmark_suite_blocker_count": _int(public_benchmark_summary.get("suite_blocker_count")),
        "public_benchmark_suite_threshold_count": _int(public_benchmark_summary.get("suite_threshold_count")),
        "public_benchmark_suite_materialization_manifest_count": _int(
            public_benchmark_summary.get("suite_materialization_manifest_count")
        ),
        "public_benchmark_suite_materialization_run_command_count": _int(
            public_benchmark_summary.get("suite_materialization_run_command_count")
        ),
        "public_benchmark_suite_scorecard_command_count": _int(
            public_benchmark_summary.get("suite_scorecard_command_count")
        ),
        "public_benchmark_suite_scorecard_row_csv_count": _int(
            public_benchmark_summary.get("suite_scorecard_row_csv_count")
        ),
        "public_benchmark_suite_no_external_dependency_count": _int(
            public_benchmark_summary.get("suite_no_external_dependency_count")
        ),
        "public_benchmark_local_artifact_preflight_ready_suite_count": _int(
            public_benchmark_summary.get("local_artifact_preflight_ready_suite_count")
        ),
        "public_benchmark_local_artifact_preflight_blocked_suite_count": _int(
            public_benchmark_summary.get("local_artifact_preflight_blocked_suite_count")
        ),
        "public_benchmark_missing_local_input_artifact_count": _int(
            public_benchmark_summary.get("missing_local_input_artifact_count")
        ),
        "public_benchmark_missing_local_output_artifact_count": _int(
            public_benchmark_summary.get("missing_local_output_artifact_count")
        ),
        "product_license_decision_packet_status": _text(product_license_summary.get("status")),
        "product_license_ready_local_source_candidate_count": _int(
            product_license_summary.get("ready_local_license_text_source_candidate_count")
        ),
        "product_license_local_source_command_example_count": len(
            _license_local_source_command_examples(product_license_decision_packet or {})
        ),
        "cameo_cli_status_set_status": _text(operator_actions.get("cameo_cli_status_set_status")),
        "cameo_cli_approval_token_count": _int(operator_actions.get("cameo_cli_approval_token_count")),
        "cameo_cli_official_result_required": bool(operator_actions.get("cameo_cli_official_result_required") is True),
        "cameo_cli_evidence_integrity_ready": bool(operator_actions.get("cameo_cli_evidence_integrity_ready") is True),
        "cameo_evidence_integrity_ready": bool(
            operator_actions.get("cameo_cli_evidence_integrity_ready") is True
            or operator_actions.get("cameo_validation_operations_evidence_integrity_ready") is True
        ),
        "cameo_evidence_integrity_status": _text(
            operator_actions.get("cameo_validation_operations_evidence_integrity_status")
        ),
        "cameo_evidence_integrity_blocker_count": _int(
            operator_actions.get("cameo_validation_operations_evidence_integrity_blocker_count")
        ),
        "cameo_official_results_pending_honest": bool(
            operator_actions.get("cameo_cli_official_results_pending_honest") is True
            or operator_actions.get("cameo_validation_operations_official_results_pending_honest") is True
        ),
        "cameo_no_local_native_accuracy_substitution": bool(
            operator_actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or operator_actions.get("cameo_validation_operations_no_local_native_accuracy_substitution") is True
        ),
        "cameo_cli_api_install_approval_required": bool(operator_actions.get("cameo_cli_api_install_approval_required") is True),
        "cameo_cli_receiver_smoke_status": _text(operator_actions.get("cameo_cli_receiver_smoke_status")),
        "cleanup_cli_status_set_status": _text(operator_actions.get("cleanup_cli_status_set_status")),
        "cleanup_cli_approval_token_count": _int(operator_actions.get("cleanup_cli_approval_token_count")),
        "cleanup_cli_approval_reclaim_size_gb": round(_float(operator_actions.get("cleanup_cli_approval_reclaim_size_gb")), 3),
        "cleanup_cli_postcheck_contract_ready": bool(operator_actions.get("cleanup_cli_postcheck_contract_ready") is True),
        "cleanup_cli_protected_payload_size_gb": round(_float(operator_actions.get("cleanup_cli_protected_payload_size_gb")), 3),
        "cleanup_cli_protected_policy_change_required_count": _int(
            operator_actions.get("cleanup_cli_protected_policy_change_required_count")
        ),
        "protected_cleanup_payload_size_gb": round(_float(_summary(protected_cleanup_review_packet).get("protected_payload_size_gb")), 3),
        "cleanup_postcheck_contract_status": _text(_summary(cleanup_postcheck_contract_packet or {}).get("status")),
        "cleanup_postcheck_contract_ready": bool(_summary(cleanup_postcheck_contract_packet or {}).get("postcheck_contract_ready") is True),
        "cleanup_postcheck_row_count": _int(_summary(cleanup_postcheck_contract_packet or {}).get("row_count")),
        "cleanup_postcheck_blocked_row_count": _int(_summary(cleanup_postcheck_contract_packet or {}).get("blocked_row_count")),
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": _next_required_step(rows),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Release Burndown Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- source_release_gate_status: `{s['source_release_gate_status']}`",
        f"- source_release_allowed: `{s['source_release_allowed']}`",
        f"- source_release_blocker_count: `{s['source_release_blocker_count']}`",
        f"- work_item_count: `{s['work_item_count']}`",
        f"- approval_required_item_count: `{s['approval_required_item_count']}`",
        f"- operator_input_required_item_count: `{s['operator_input_required_item_count']}`",
        f"- burndown_operator_input_required_work_item_count: `{s['burndown_operator_input_required_work_item_count']}`",
        f"- primary_action_id: `{s['primary_action_id']}`",
        f"- primary_action_status: `{s['primary_action_status']}`",
        f"- primary_action_required_input: `{s['primary_action_required_input']}`",
        f"- primary_action_recommended_action: `{s['primary_action_recommended_action']}`",
        f"- parallel_product_action_count: `{s['parallel_product_action_count']}`",
        f"- first_parallel_product_action_id: `{s['first_parallel_product_action_id']}`",
        f"- first_parallel_product_action_required_input: `{s['first_parallel_product_action_required_input']}`",
        f"- first_parallel_product_action_precondition: `{s['first_parallel_product_action_precondition']}`",
        f"- goal_operator_intake_kit_status: `{s['goal_operator_intake_kit_status']}`",
        f"- goal_operator_intake_kit_release_burndown_linked_entry_count: `{s['goal_operator_intake_kit_release_burndown_linked_entry_count']}`",
        f"- goal_operator_intake_kit_current_action_required_count: `{s['goal_operator_intake_kit_current_action_required_count']}`",
        f"- goal_operator_intake_kit_deferred_operator_input_count: `{s['goal_operator_intake_kit_deferred_operator_input_count']}`",
        f"- goal_operator_intake_kit_current_action_approval_token_count: `{s['goal_operator_intake_kit_current_action_approval_token_count']}`",
        f"- official_results_required_item_count: `{s['official_results_required_item_count']}`",
        f"- policy_decision_required_item_count: `{s['policy_decision_required_item_count']}`",
        f"- postcheck_required_item_count: `{s['postcheck_required_item_count']}`",
        f"- approval_tokens_required: `{','.join(s['approval_tokens_required'])}`",
        f"- product_cli_status_set_status: `{s['product_cli_status_set_status']}`",
        f"- product_cli_approval_token_count: `{s['product_cli_approval_token_count']}`",
        f"- product_cli_operations_blocked_stage_count: `{s['product_cli_operations_blocked_stage_count']}`",
        f"- product_operational_quality_status: `{s['product_operational_quality_status']}`",
        f"- product_operational_quality_ready: `{s['product_operational_quality_ready']}`",
        f"- product_operational_quality_blocker_count: `{s['product_operational_quality_blocker_count']}`",
        f"- public_benchmark_work_order_status: `{s['public_benchmark_work_order_status']}`",
        f"- public_benchmark_continuous_validation_command_count: `{s['public_benchmark_continuous_validation_command_count']}`",
        f"- public_benchmark_suite_run_command_count: `{s['public_benchmark_suite_run_command_count']}`",
        f"- public_benchmark_suite_blocker_count: `{s['public_benchmark_suite_blocker_count']}`",
        f"- public_benchmark_suite_threshold_count: `{s['public_benchmark_suite_threshold_count']}`",
        f"- public_benchmark_suite_materialization_manifest_count: `{s['public_benchmark_suite_materialization_manifest_count']}`",
        f"- public_benchmark_suite_materialization_run_command_count: `{s['public_benchmark_suite_materialization_run_command_count']}`",
        f"- public_benchmark_suite_scorecard_command_count: `{s['public_benchmark_suite_scorecard_command_count']}`",
        f"- public_benchmark_suite_scorecard_row_csv_count: `{s['public_benchmark_suite_scorecard_row_csv_count']}`",
        f"- public_benchmark_suite_no_external_dependency_count: `{s['public_benchmark_suite_no_external_dependency_count']}`",
        f"- public_benchmark_local_artifact_preflight_ready_suite_count: `{s['public_benchmark_local_artifact_preflight_ready_suite_count']}`",
        f"- public_benchmark_local_artifact_preflight_blocked_suite_count: `{s['public_benchmark_local_artifact_preflight_blocked_suite_count']}`",
        f"- public_benchmark_missing_local_input_artifact_count: `{s['public_benchmark_missing_local_input_artifact_count']}`",
        f"- public_benchmark_missing_local_output_artifact_count: `{s['public_benchmark_missing_local_output_artifact_count']}`",
        f"- product_license_decision_packet_status: `{s['product_license_decision_packet_status']}`",
        f"- product_license_ready_local_source_candidate_count: `{s['product_license_ready_local_source_candidate_count']}`",
        f"- product_license_local_source_command_example_count: `{s['product_license_local_source_command_example_count']}`",
        f"- cameo_cli_status_set_status: `{s['cameo_cli_status_set_status']}`",
        f"- cameo_cli_approval_token_count: `{s['cameo_cli_approval_token_count']}`",
        f"- cameo_cli_official_result_required: `{s['cameo_cli_official_result_required']}`",
        f"- cameo_evidence_integrity_status: `{s['cameo_evidence_integrity_status']}`",
        f"- cameo_evidence_integrity_ready: `{s['cameo_evidence_integrity_ready']}`",
        f"- cameo_evidence_integrity_blocker_count: `{s['cameo_evidence_integrity_blocker_count']}`",
        f"- cameo_official_results_pending_honest: `{s['cameo_official_results_pending_honest']}`",
        f"- cameo_no_local_native_accuracy_substitution: `{s['cameo_no_local_native_accuracy_substitution']}`",
        f"- cleanup_cli_status_set_status: `{s['cleanup_cli_status_set_status']}`",
        f"- cleanup_cli_approval_token_count: `{s['cleanup_cli_approval_token_count']}`",
        f"- cleanup_cli_approval_reclaim_size_gb: `{s['cleanup_cli_approval_reclaim_size_gb']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Work Items",
        "",
        "| seq | phase | lane | check | status | approval | artifact | action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['phase']}` | `{row['lane_id']}` | `{row['release_check']}` | "
            f"`{row['burndown_status']}` | `{row['approval_token_required']}` | `{row['source_artifact']}` | {row['recommended_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a release blocker burndown work order from current local artifacts.")
    parser.add_argument("--release-gate-json", default=DEFAULT_RELEASE_GATE_JSON)
    parser.add_argument("--operator-action-board-json", default=DEFAULT_OPERATOR_ACTION_BOARD_JSON)
    parser.add_argument("--product-preflight-json", default=DEFAULT_PRODUCT_PREFLIGHT_JSON)
    parser.add_argument("--product-gate-repair-json", default=DEFAULT_PRODUCT_GATE_REPAIR_JSON)
    parser.add_argument("--product-work-order-json", default=DEFAULT_PRODUCT_WORK_ORDER_JSON)
    parser.add_argument("--product-pilot-json", default=DEFAULT_PRODUCT_PILOT_JSON)
    parser.add_argument("--public-benchmark-work-order-json", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON)
    parser.add_argument("--product-license-decision-packet-json", default=DEFAULT_PRODUCT_LICENSE_DECISION_PACKET_JSON)
    parser.add_argument("--product-ai-architecture-backlog-json", default=DEFAULT_PRODUCT_AI_ARCHITECTURE_BACKLOG_JSON)
    parser.add_argument("--cameo-validation-repair-json", default=DEFAULT_CAMEO_VALIDATION_REPAIR_JSON)
    parser.add_argument("--cameo-runtime-repair-json", default=DEFAULT_CAMEO_RUNTIME_REPAIR_JSON)
    parser.add_argument("--cameo-capability-json", default=DEFAULT_CAMEO_CAPABILITY_JSON)
    parser.add_argument("--transition-cleanup-work-order-json", default=DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON)
    parser.add_argument("--ligand-cleanup-work-order-json", default=DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON)
    parser.add_argument("--protected-cleanup-review-json", default=DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON)
    parser.add_argument("--cleanup-postcheck-contract-json", default=DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_goal_release_burndown_work_order(
        release_gate_packet=_read_json_if_present(args.release_gate_json),
        operator_action_board_packet=_read_json_if_present(args.operator_action_board_json),
        product_work_order_packet=_read_json_if_present(args.product_work_order_json),
        product_pilot_packet=_read_json_if_present(args.product_pilot_json),
        cameo_validation_repair_packet=_read_json_if_present(args.cameo_validation_repair_json),
        cameo_runtime_repair_packet=_read_json_if_present(args.cameo_runtime_repair_json),
        cameo_capability_packet=_read_json_if_present(args.cameo_capability_json),
        transition_cleanup_work_order_packet=_read_json_if_present(args.transition_cleanup_work_order_json),
        ligand_cleanup_work_order_packet=_read_json_if_present(args.ligand_cleanup_work_order_json),
        protected_cleanup_review_packet=_read_json_if_present(args.protected_cleanup_review_json),
        cleanup_postcheck_contract_packet=_read_json_if_present(args.cleanup_postcheck_contract_json),
        product_preflight_packet=_read_json_if_present(args.product_preflight_json),
        product_gate_repair_packet=_read_json_if_present(args.product_gate_repair_json),
        public_benchmark_work_order_packet=_read_json_if_present(args.public_benchmark_work_order_json),
        product_license_decision_packet=_read_json_if_present(args.product_license_decision_packet_json),
        product_ai_architecture_backlog_packet=_read_json_if_present(args.product_ai_architecture_backlog_json),
        release_gate_path=args.release_gate_json,
        operator_action_board_path=args.operator_action_board_json,
        product_preflight_path=args.product_preflight_json,
        product_gate_repair_path=args.product_gate_repair_json,
        product_work_order_path=args.product_work_order_json,
        product_pilot_path=args.product_pilot_json,
        public_benchmark_work_order_path=args.public_benchmark_work_order_json,
        product_license_decision_packet_path=args.product_license_decision_packet_json,
        product_ai_architecture_backlog_path=args.product_ai_architecture_backlog_json,
        cameo_validation_repair_path=args.cameo_validation_repair_json,
        cameo_runtime_repair_path=args.cameo_runtime_repair_json,
        cameo_capability_path=args.cameo_capability_json,
        transition_cleanup_work_order_path=args.transition_cleanup_work_order_json,
        ligand_cleanup_work_order_path=args.ligand_cleanup_work_order_json,
        protected_cleanup_review_path=args.protected_cleanup_review_json,
        cleanup_postcheck_contract_path=args.cleanup_postcheck_contract_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
