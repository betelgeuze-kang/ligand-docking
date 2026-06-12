#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.production_ai_checkpoint_readiness import (
    build_product_production_ai_checkpoint_readiness,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_CHECKPOINT_WORK_ORDER_JSON = "runs/residual_production_checkpoint_work_order_current.json"
DEFAULT_TRAINING_DATA_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_FORCE_GPU_RECEIPT_JSON = "runs/residual_force_gpu_worker_return_receipt_current.json"
DEFAULT_FORCE_DERIVATION_VALIDATION_JSON = "runs/residual_force_derivation_validation_current.json"
DEFAULT_FORCE_GPU_HANDOFF_JSON = "runs/residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_GPU_RETURN_INTAKE_JSON = "runs/product_production_ai_gpu_return_intake_current.json"
DEFAULT_ROCM_ENVIRONMENT_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_OUTPUT_HEAD_GAP_CONTRACT_JSON = "runs/residual_production_output_head_gap_contract_current.json"
DEFAULT_OUT_JSON = "runs/product_production_ai_checkpoint_readiness_current.json"
DEFAULT_OUT_CSV = "runs/product_production_ai_checkpoint_readiness_current.csv"
DEFAULT_OUT_MD = "runs/product_production_ai_checkpoint_readiness_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
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


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# Product Production AI Checkpoint Readiness",
        "",
        f"- status: `{summary['status']}`",
        f"- production_ai_checkpoint_ready: `{summary['production_ai_checkpoint_ready']}`",
        f"- production_ai_inference_subject_active: `{summary['production_ai_inference_subject_active']}`",
        f"- default_residual_mode: `{summary['default_residual_mode']}`",
        f"- production_promotion_allowed: `{summary['production_promotion_allowed']}`",
        f"- trained_model_checkpoint_count: `{summary['trained_model_checkpoint_count']}`",
        f"- ready_checkpoint_count: `{summary['ready_checkpoint_count']}`",
        f"- production_output_head_gap_contract_ready: `{summary['production_output_head_gap_contract_ready']}`",
        f"- production_output_heads_complete: `{summary['production_output_heads_complete']}`",
        f"- production_output_head_ready_field_count: `{summary['production_output_head_ready_field_count']}` / `{summary['production_output_head_required_field_count']}`",
        f"- production_output_head_blocked_fields: `{','.join(str(item) for item in summary['production_output_head_blocked_fields'])}`",
        f"- production_output_head_first_blocked_field: `{summary['production_output_head_first_blocked_field']}`",
        f"- force_gpu_worker_return_receipt_ready: `{summary['force_gpu_worker_return_receipt_ready']}`",
        f"- delta_force_derivation_validation_ready: `{summary['delta_force_derivation_validation_ready']}`",
        f"- force_derivation_validation_status: `{summary['force_derivation_validation_status']}`",
        f"- force_gpu_worker_handoff_ready: `{summary['force_gpu_worker_handoff_ready']}`",
        f"- production_gpu_execution_environment_ready: `{summary['production_gpu_execution_environment_ready']}`",
        f"- production_gpu_execution_environment_status: `{summary['production_gpu_execution_environment_status']}`",
        f"- production_gpu_rocm_visible_device_count: `{summary['production_gpu_rocm_visible_device_count']}`",
        f"- production_gpu_rocm_torch_ready: `{summary['production_gpu_rocm_torch_ready']}`",
        f"- production_gpu_rocm_visibility_diagnostic_packet_ready: `{summary['production_gpu_rocm_visibility_diagnostic_packet_ready']}`",
        f"- production_gpu_rocm_visibility_diagnostic_command_count: `{summary['production_gpu_rocm_visibility_diagnostic_command_count']}`",
        f"- production_gpu_rocm_visibility_diagnostic_completion_rule: `{summary['production_gpu_rocm_visibility_diagnostic_completion_rule']}`",
        f"- production_gpu_rocm_next_required_step: `{summary['production_gpu_rocm_next_required_step']}`",
        f"- force_gpu_worker_operator_action_required: `{summary['force_gpu_worker_operator_action_required']}`",
        f"- force_gpu_worker_operator_transfer_manifest_ready: `{summary['force_gpu_worker_operator_transfer_manifest_ready']}`",
        f"- force_gpu_worker_operator_transfer_outbound_artifact_count: `{summary['force_gpu_worker_operator_transfer_outbound_artifact_count']}`",
        f"- force_gpu_worker_operator_transfer_inbound_artifact_count: `{summary['force_gpu_worker_operator_transfer_inbound_artifact_count']}`",
        f"- force_gpu_worker_operator_transfer_first_return_artifact: `{summary['force_gpu_worker_operator_transfer_first_return_artifact']}`",
        f"- force_gpu_worker_operator_transfer_acceptance_artifact: `{summary['force_gpu_worker_operator_transfer_acceptance_artifact']}`",
        f"- force_gpu_worker_return_summary_template_payload_json: `{summary['force_gpu_worker_return_summary_template_payload_json']}`",
        f"- gpu_receipt_expected_queue_rows: `{summary['gpu_receipt_expected_queue_rows']}`",
        f"- gpu_receipt_summary_manifest_bound: `{summary['gpu_receipt_summary_manifest_bound']}`",
        f"- gpu_receipt_summary_out_manifest_csv_bound: `{summary['gpu_receipt_summary_out_manifest_csv_bound']}`",
        f"- gpu_receipt_summary_out_summary_json_bound: `{summary['gpu_receipt_summary_out_summary_json_bound']}`",
        f"- gpu_receipt_summary_manifest_row_counts_consistent: `{summary['gpu_receipt_summary_manifest_row_counts_consistent']}`",
        f"- gpu_receipt_production_gpu_backend_provenance_ready: `{summary['gpu_receipt_production_gpu_backend_provenance_ready']}`",
        f"- gpu_receipt_production_gpu_backend_rows: `{summary['gpu_receipt_production_gpu_backend_rows']}`",
        f"- gpu_receipt_production_gpu_backend_non_production_rows: `{summary['gpu_receipt_production_gpu_backend_non_production_rows']}`",
        f"- gpu_receipt_manifest_ok_row_count: `{summary['gpu_receipt_manifest_ok_row_count']}`",
        f"- gpu_receipt_manifest_operator_verified: `{summary['gpu_receipt_manifest_operator_verified']}`",
        f"- force_gpu_worker_post_return_unlock_output_fields: `{','.join(str(item) for item in summary['force_gpu_worker_post_return_unlock_output_fields'])}`",
        f"- force_gpu_worker_post_return_min_expected_label_rows: `{summary['force_gpu_worker_post_return_min_expected_label_rows']}`",
        f"- force_gpu_worker_post_return_promotion_ladder_contract_ready: `{summary['force_gpu_worker_post_return_promotion_ladder_contract_ready']}`",
        f"- force_gpu_worker_post_return_promotion_ladder_currently_satisfied: `{summary['force_gpu_worker_post_return_promotion_ladder_currently_satisfied']}`",
        f"- force_gpu_worker_post_return_promotion_ladder_current_next_stage_id: `{summary['force_gpu_worker_post_return_promotion_ladder_current_next_stage_id']}`",
        f"- force_gpu_worker_post_return_promotion_ladder_stage_ids: `{','.join(str(item) for item in summary['force_gpu_worker_post_return_promotion_ladder_stage_ids'])}`",
        f"- force_gpu_worker_post_run_validation_command_count: `{summary['force_gpu_worker_post_run_validation_command_count']}`",
        f"- production_inference_acceptance_matrix_ready: `{summary['production_inference_acceptance_matrix_ready']}`",
        f"- production_inference_acceptance_ready_stage_count: `{summary['production_inference_acceptance_ready_stage_count']}`",
        f"- production_inference_acceptance_blocked_stage_count: `{summary['production_inference_acceptance_blocked_stage_count']}`",
        f"- production_inference_acceptance_next_stage_id: `{summary['production_inference_acceptance_next_stage_id']}`",
        f"- production_inference_acceptance_next_stage_artifact: `{summary['production_inference_acceptance_next_stage_artifact']}`",
        f"- production_inference_acceptance_next_stage_validation_command: `{summary['production_inference_acceptance_next_stage_validation_command']}`",
        f"- production_inference_actionable_blocker_stage_id: `{summary['production_inference_actionable_blocker_stage_id']}`",
        f"- production_inference_actionable_blocker_check_id: `{summary['production_inference_actionable_blocker_check_id']}`",
        f"- production_inference_actionable_blocker_artifact: `{summary['production_inference_actionable_blocker_artifact']}`",
        f"- production_inference_actionable_blocker_downstream_blocked_stage_count: `{summary['production_inference_actionable_blocker_downstream_blocked_stage_count']}`",
        f"- production_inference_next_after_actionable_blocker_stage_id: `{summary['production_inference_next_after_actionable_blocker_stage_id']}`",
        f"- production_inference_next_after_actionable_blocker_artifact: `{summary['production_inference_next_after_actionable_blocker_artifact']}`",
        f"- production_inference_next_after_actionable_blocker_validation_command: `{summary['production_inference_next_after_actionable_blocker_validation_command']}`",
        f"- production_inference_actionable_blocker_blocks_registry_promotion: `{summary['production_inference_actionable_blocker_blocks_registry_promotion']}`",
        f"- production_inference_actionable_operator_completion_packet_ready: `{summary['production_inference_actionable_operator_completion_packet_ready']}`",
        f"- production_inference_actionable_operator_completion_artifact_id: `{summary['production_inference_actionable_operator_completion_artifact_id']}`",
        f"- production_inference_actionable_operator_completion_artifact_path: `{summary['production_inference_actionable_operator_completion_artifact_path']}`",
        f"- production_inference_actionable_operator_completion_expected_queue_rows: `{summary['production_inference_actionable_operator_completion_expected_queue_rows']}`",
        f"- production_inference_actionable_operator_completion_diagnostic_command_count: `{summary['production_inference_actionable_operator_completion_diagnostic_command_count']}`",
        f"- production_inference_actionable_operator_completion_diagnostic_completion_rule: `{summary['production_inference_actionable_operator_completion_diagnostic_completion_rule']}`",
        f"- production_inference_actionable_operator_completion_validation_command: `{summary['production_inference_actionable_operator_completion_validation_command']}`",
        f"- production_inference_actionable_operator_completion_next_action: `{summary['production_inference_actionable_operator_completion_next_action']}`",
        f"- production_inference_worker_runtime_receipt_contract_ready: `{summary['production_inference_worker_runtime_receipt_contract_ready']}`",
        f"- production_inference_worker_runtime_receipt_required_field_count: `{summary['production_inference_worker_runtime_receipt_required_field_count']}`",
        f"- production_inference_worker_runtime_receipt_completion_rule: `{summary['production_inference_worker_runtime_receipt_completion_rule']}`",
        f"- production_inference_worker_runtime_receipt_post_environment_next_stage_id: `{summary['production_inference_worker_runtime_receipt_post_environment_next_stage_id']}`",
        f"- production_inference_worker_runtime_receipt_post_environment_next_artifact: `{summary['production_inference_worker_runtime_receipt_post_environment_next_artifact']}`",
        f"- checkpoint_closure_blockers: `{','.join(str(item) for item in summary['checkpoint_closure_blockers'])}`",
        f"- force_gpu_worker_full_regeneration_command: `{summary['force_gpu_worker_full_regeneration_command']}`",
        f"- force_gpu_worker_post_return_validation_command: `{summary['force_gpu_worker_post_return_validation_command']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | "
            f"{row['required']} | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Production Inference Acceptance Matrix",
            "",
            "| stage | status | artifact | validation_command | release_effect | next_action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["production_inference_acceptance_matrix"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['status']}` | `{row['artifact']}` | "
            f"`{row['validation_command']}` | {row['release_effect']} | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product production AI checkpoint readiness contract.")
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--checkpoint-work-order-json", default=DEFAULT_CHECKPOINT_WORK_ORDER_JSON)
    parser.add_argument("--training-data-json", default=DEFAULT_TRAINING_DATA_JSON)
    parser.add_argument("--force-gpu-receipt-json", default=DEFAULT_FORCE_GPU_RECEIPT_JSON)
    parser.add_argument("--force-derivation-validation-json", default=DEFAULT_FORCE_DERIVATION_VALIDATION_JSON)
    parser.add_argument("--force-gpu-handoff-json", default=DEFAULT_FORCE_GPU_HANDOFF_JSON)
    parser.add_argument("--gpu-return-intake-json", default=DEFAULT_GPU_RETURN_INTAKE_JSON)
    parser.add_argument("--rocm-environment-json", default=DEFAULT_ROCM_ENVIRONMENT_JSON)
    parser.add_argument("--output-head-gap-contract-json", default=DEFAULT_OUTPUT_HEAD_GAP_CONTRACT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_production_ai_checkpoint_readiness(
        registry_packet=_read_json(args.registry_json),
        checkpoint_work_order_packet=_read_json(args.checkpoint_work_order_json),
        training_data_packet=_read_json(args.training_data_json),
        force_gpu_worker_return_receipt_packet=_read_json(args.force_gpu_receipt_json),
        force_derivation_validation_packet=_read_json(args.force_derivation_validation_json),
        force_gpu_worker_handoff_packet=_read_json(args.force_gpu_handoff_json),
        gpu_return_intake_packet=_read_json(args.gpu_return_intake_json),
        rocm_environment_packet=_read_json(args.rocm_environment_json),
        output_head_gap_contract_packet=_read_json(args.output_head_gap_contract_json),
        registry_artifact_path=args.registry_json,
        checkpoint_work_order_artifact_path=args.checkpoint_work_order_json,
        training_data_artifact_path=args.training_data_json,
        force_gpu_worker_return_receipt_artifact_path=args.force_gpu_receipt_json,
        force_derivation_validation_artifact_path=args.force_derivation_validation_json,
        force_gpu_worker_handoff_artifact_path=args.force_gpu_handoff_json,
        gpu_return_intake_artifact_path=args.gpu_return_intake_json,
        rocm_environment_artifact_path=args.rocm_environment_json,
        output_head_gap_contract_artifact_path=args.output_head_gap_contract_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
