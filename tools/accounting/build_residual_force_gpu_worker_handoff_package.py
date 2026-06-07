#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGENERATION_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_EXECUTION_PROBE_JSON = "runs/residual_force_trajectory_regeneration_execution_probe_current.json"
DEFAULT_RETURN_MANIFEST_TEMPLATE_JSON = "runs/residual_force_gpu_worker_return_manifest_template_current.json"
DEFAULT_RETURN_SUMMARY_TEMPLATE_JSON = "runs/residual_force_gpu_worker_return_summary_template_current.json"
DEFAULT_WORKER_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_gpu_worker_handoff_package_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_gpu_worker_handoff_package_current.md"

POST_RUN_VALIDATION_COMMANDS = (
    "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
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
)
POST_RETURN_PROMOTION_LADDER = (
    {
        "stage_id": "gpu_return_receipt",
        "artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
        "ready_key": "gpu_worker_return_receipt_ready",
        "required_value": True,
        "release_effect": "returned GPU summary/manifest covers the 768-row queue and operator verification is complete",
    },
    {
        "stage_id": "force_derivation_validation",
        "artifact": "runs/residual_force_derivation_validation_current.json",
        "ready_key": "delta_force_derivation_validation_ready",
        "required_value": True,
        "release_effect": "regenerated NPZ bundles are accepted as delta_force derivation inputs",
    },
    {
        "stage_id": "energy_force_label_evidence",
        "artifact": "runs/residual_energy_force_label_evidence_work_order_current.json",
        "ready_key": "delta_force_label_evidence_ready",
        "required_value": True,
        "release_effect": "production supervised labels include delta_force evidence",
    },
    {
        "stage_id": "production_training_data_contract",
        "artifact": "runs/residual_production_training_data_contract_current.json",
        "ready_key": "production_training_data_ready",
        "required_value": True,
        "release_effect": "production training-data contract no longer blocks residual checkpoint training",
    },
    {
        "stage_id": "production_score_model",
        "artifact": "runs/residual_production_score_model_current.json",
        "ready_key": "score_model_production_checkpoint_ready",
        "required_value": True,
        "release_effect": "trained score model advertises all required production outputs",
    },
    {
        "stage_id": "production_checkpoint_sidecar",
        "artifact": "runs/residual_production_checkpoint_sidecar_current.json",
        "ready_key": "sidecar_ready",
        "required_value": True,
        "release_effect": "checkpoint sidecar binds training contract, force receipt, adapter policy, uncertainty, and physics guard evidence",
    },
    {
        "stage_id": "production_checkpoint_preflight",
        "artifact": "runs/residual_production_checkpoint_preflight_current.json",
        "ready_key": "checkpoint_preflight_ready",
        "required_value": True,
        "release_effect": "checkpoint is ready for guarded promotion",
    },
    {
        "stage_id": "residual_model_registry",
        "artifact": "runs/residual_model_registry_current.json",
        "ready_key": "production_promotion_allowed",
        "required_value": True,
        "release_effect": "AI model can become the guarded production inference subject",
    },
    {
        "stage_id": "product_ai_architecture_gap_closure",
        "artifact": "runs/product_ai_architecture_gap_closure_current.json",
        "ready_key": "all_gaps_closed",
        "required_value": True,
        "release_effect": "protein-structure plus ligand-docking AI architecture gap is closed",
    },
    {
        "stage_id": "product_goal_completion_audit",
        "artifact": "runs/product_goal_completion_audit_current.json",
        "ready_key": "goal_complete",
        "required_value": True,
        "release_effect": "commercial independent product goal can be marked complete",
    },
)
RETURN_MANIFEST_STATUS_COLUMN = "status"
RETURN_MANIFEST_QUEUE_ID_COLUMNS = ("queue_id", "source_queue_id", "regeneration_queue_id")
RETURN_MANIFEST_NPZ_COLUMNS = (
    "expected_regenerated_trajectory_npz",
    "trajectory_npz",
    "output_npz",
    "generated_npz",
)
RETURN_MANIFEST_FINGERPRINT_COLUMNS = ("queue_row_fingerprint", "source_queue_row_fingerprint")
REQUIRED_QUEUE_IDENTITY_COLUMNS = ("queue_id", "expected_regenerated_trajectory_npz")
REQUIRED_PRODUCTION_OUTPUT_FIELDS = (
    "delta_score",
    "corrected_score",
    "delta_energy",
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
)
GPU_RETURN_UNLOCK_OUTPUT_FIELDS = (
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
)
GPU_RETURN_UNLOCK_ARTIFACTS = (
    "runs/residual_force_gpu_worker_return_receipt_current.json",
    "runs/residual_force_derivation_validation_current.json",
    "runs/residual_energy_force_label_validation_current.json",
    "runs/residual_energy_force_label_evidence_work_order_current.json",
    "runs/residual_uncertainty_policy_evidence_contract_current.json",
    "runs/residual_production_training_data_contract_current.json",
    "runs/residual_production_checkpoint_sidecar_current.json",
    "runs/residual_production_checkpoint_preflight_current.json",
)
GPU_WORKER_TOOL_ARTIFACTS = (
    "tools/generate_ligand_trajectory_engine.py",
    "tools/build_residual_force_trajectory_regeneration_execution_probe.py",
    "tools/build_rocm_environment_manifest.py",
)
WORKER_ROCM_MANIFEST_COMPLETION_RULE = (
    "manifest_ready=true;rocm_stack_detected=true;torch_rocm_ready=true;amd_gpu_detected=true;visible_device_count>0"
)

CLAIM_BOUNDARY = (
    "Residual force GPU worker handoff package only; consolidates the prepared trajectory regeneration queue, runtime "
    "probe evidence, exact GPU-worker commands, and post-run validation commands for operator execution. It does not "
    "run docking, regenerate trajectories, derive force labels, train models, create checkpoints, promote production "
    "mode, upload, submit, email, delete, or mutate external state."
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
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sha256_if_present(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_header(path_like: str | Path) -> list[str]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return list(reader.fieldnames or [])
    except OSError:
        return []


def _row(step_id: str, status: str, command: str, required: str, acceptance: str) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "status": status,
        "command": command,
        "required": required,
        "acceptance": acceptance,
        "operator_action_required": status != "pass",
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _tiny_pilot_command(full_command: str) -> str:
    replacements = {
        "--out-root runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames": "--out-root runs/residual_force_trajectory_regeneration_pilot/stage2_trajectory_frames",
        "--out-manifest-csv runs/residual_force_trajectory_regeneration_current_manifest.csv": "--out-manifest-csv runs/residual_force_trajectory_regeneration_pilot_manifest.csv",
        "--out-summary-json runs/residual_force_trajectory_regeneration_current_summary.json": "--out-summary-json runs/residual_force_trajectory_regeneration_pilot_summary.json",
        "--out-summary-md runs/residual_force_trajectory_regeneration_current_summary.md": "--out-summary-md runs/residual_force_trajectory_regeneration_pilot_summary.md",
        "--out-progress-json runs/residual_force_trajectory_regeneration_current_progress.json": "--out-progress-json runs/residual_force_trajectory_regeneration_pilot_progress.json",
        "--frames 120": "--frames 4",
    }
    command = full_command
    for old, new in replacements.items():
        command = command.replace(old, new)
    if "--max-jobs" not in command:
        command = f"{command} --max-jobs 2"
    return command


def _promotion_ladder_command_coverage() -> tuple[bool, list[str]]:
    command_text = "\n".join(POST_RUN_VALIDATION_COMMANDS)
    missing = [
        stage["stage_id"]
        for stage in POST_RETURN_PROMOTION_LADDER
        if Path(str(stage["artifact"])).stem.replace("_current", "") not in command_text
        and str(stage["stage_id"]) not in command_text
    ]
    return (not missing, missing)


def build_residual_force_gpu_worker_handoff_package(
    *,
    regeneration_queue_packet: dict[str, Any],
    execution_probe_packet: dict[str, Any],
    return_manifest_template_packet: dict[str, Any] | None = None,
    return_summary_template_packet: dict[str, Any] | None = None,
    regeneration_queue_path: str = DEFAULT_REGENERATION_QUEUE_JSON,
    execution_probe_path: str = DEFAULT_EXECUTION_PROBE_JSON,
    return_manifest_template_path: str = DEFAULT_RETURN_MANIFEST_TEMPLATE_JSON,
    return_summary_template_path: str = DEFAULT_RETURN_SUMMARY_TEMPLATE_JSON,
) -> dict[str, Any]:
    queue = _summary(regeneration_queue_packet)
    probe = _summary(execution_probe_packet)
    template = _summary(return_manifest_template_packet or {})
    summary_template = _summary(return_summary_template_packet or {})
    queue_ready = queue.get("regeneration_queue_execution_ready") is True
    queue_rows = _int(queue.get("queue_rows"))
    queue_csv = _text(queue.get("regeneration_queue_csv"))
    queue_csv_header = _csv_header(queue_csv) if queue_csv else []
    queue_csv_present = bool(queue_csv and _resolve(queue_csv).exists())
    queue_csv_sha256 = _sha256_if_present(queue_csv) if queue_csv else ""
    queue_identity_columns_present = all(column in queue_csv_header for column in REQUIRED_QUEUE_IDENTITY_COLUMNS)
    return_manifest_schema_contract_ready = bool(queue_csv_present and queue_identity_columns_present)
    return_manifest_template_ready = template.get("return_manifest_template_ready") is True
    return_manifest_template_csv = _text(template.get("template_csv"))
    return_manifest_template_row_count = _int(template.get("template_row_count"))
    return_manifest_template_row_count_matches_queue = bool(queue_rows > 0 and return_manifest_template_row_count == queue_rows)
    return_summary_template_ready = summary_template.get("return_summary_template_ready") is True
    return_summary_template_expected_queue_rows = _int(summary_template.get("expected_queue_rows"))
    return_summary_template_row_count_matches_queue = bool(
        queue_rows > 0 and return_summary_template_expected_queue_rows == queue_rows
    )
    return_summary_actual_path = _text(summary_template.get("actual_summary_return_path"))
    return_summary_required_fields = [
        _text(field) for field in summary_template.get("required_summary_fields", []) if _text(field)
    ]
    return_summary_completion_rule = _text(summary_template.get("required_completion_rule"))
    return_summary_template_payload_json = _text(summary_template.get("template_payload_json"))
    return_summary_template_payload_source = return_summary_template_payload_json or return_summary_template_path
    actual_manifest_return_path = "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    outbound_artifacts = [
        regeneration_queue_path,
        queue_csv,
        return_manifest_template_path,
        return_manifest_template_csv,
        return_summary_template_path,
        return_summary_template_payload_source,
        *GPU_WORKER_TOOL_ARTIFACTS,
        "native PDB files referenced by regeneration_queue_csv.native_pdb_path",
    ]
    outbound_artifacts = [artifact for artifact in outbound_artifacts if _text(artifact)]
    inbound_artifacts = [
        DEFAULT_WORKER_ROCM_MANIFEST_JSON,
        return_summary_actual_path or "runs/residual_force_trajectory_regeneration_current_summary.json",
        actual_manifest_return_path,
        "regenerated NPZ bundles referenced by returned manifest NPZ path columns",
        "runs/residual_force_trajectory_regeneration_execution_probe_current.json after rerun on the returned pilot/full run evidence",
    ]
    full_command = _text(queue.get("engine_command"))
    pilot_command = _tiny_pilot_command(full_command) if full_command else ""
    engine_runtime_ready = probe.get("engine_runtime_ready") is True
    gpu_backend_unavailable = probe.get("gpu_backend_unavailable") is True
    handoff_required = queue_ready and not engine_runtime_ready
    handoff_ready = bool(
        queue_ready
        and bool(full_command)
        and bool(pilot_command)
        and return_manifest_schema_contract_ready
        and return_manifest_template_ready
        and return_manifest_template_row_count_matches_queue
        and return_summary_template_ready
        and return_summary_template_row_count_matches_queue
    )
    promotion_ladder_command_covered, promotion_ladder_missing_stages = _promotion_ladder_command_coverage()
    operator_transfer_manifest_ready = bool(
        handoff_ready
        and len(outbound_artifacts) >= 8
        and len(inbound_artifacts) == 5
        and bool(POST_RUN_VALIDATION_COMMANDS)
    )

    rows = [
        _row(
            "copy_or_mount_workspace",
            "pending" if handoff_ready else "blocked",
            "rsync or mount this repository on a GPU-equipped worker with the same relative paths under the repo root",
            "worker can read queue CSV, return manifest template CSV, native PDB files, and tools/",
            "python3 -m py_compile tools/generate_ligand_trajectory_engine.py succeeds on the worker",
        ),
        _row(
            "use_prefilled_return_manifest_template",
            "pending" if handoff_ready else "blocked",
            f"copy {return_manifest_template_csv} to the GPU worker and fill status/operator verification columns after the full run",
            f"template contains one identity-locked row for each of the {queue_rows} prepared queue rows",
            "completed return manifest preserves queue_id and expected_regenerated_trajectory_npz for every template row",
        ),
        _row(
            "use_prefilled_return_summary_template",
            "pending" if handoff_ready else "blocked",
            (
                f"copy {return_summary_template_payload_source} to the GPU worker as the fillable summary JSON skeleton, "
                f"keep {return_summary_template_path} as the summary contract packet, and write "
                f"{return_summary_actual_path or 'runs/residual_force_trajectory_regeneration_current_summary.json'} after the full run"
            ),
            f"summary template expected_queue_rows equals the {queue_rows} prepared queue rows",
            "returned summary has processed_rows>=queue_rows, ok_rows>=queue_rows, failed_rows=0, and aborted_early=false",
        ),
        _row(
            "run_tiny_npz_pilot",
            "pending" if handoff_ready else "blocked",
            pilot_command,
            "GPU worker can produce at least one NPZ bundle in production-mode engine settings",
            "runs/residual_force_trajectory_regeneration_pilot_summary.json has ok_rows>=1 and aborted_early=false",
        ),
        _row(
            "return_worker_rocm_environment_manifest",
            "pending" if handoff_ready else "blocked",
            "python3 tools/build_rocm_environment_manifest.py",
            "GPU worker returns a ROCm/PyTorch manifest generated on the same worker that ran the pilot/full regeneration",
            WORKER_ROCM_MANIFEST_COMPLETION_RULE,
        ),
        _row(
            "rerun_execution_probe",
            "pending" if handoff_ready else "blocked",
            "python3 tools/build_residual_force_trajectory_regeneration_execution_probe.py",
            "pilot summary is summarized into current execution probe",
            "runs/residual_force_trajectory_regeneration_execution_probe_current.json has engine_runtime_ready=true",
        ),
        _row(
            "run_full_regeneration_queue",
            "pending" if handoff_ready else "blocked",
            full_command,
            f"all {queue_rows} prepared trajectory jobs are regenerated as NPZ bundles",
            f"runs/residual_force_trajectory_regeneration_current_summary.json has ok_rows={queue_rows} and aborted_early=false",
        ),
        _row(
            "return_summary_manifest_with_identity_columns",
            "pending" if handoff_ready else "blocked",
            (
                "return runs/residual_force_trajectory_regeneration_current_summary.json and the completed "
                "identity-locked manifest CSV derived from the handoff template"
            ),
            "returned manifest includes status plus queue_id or generated NPZ path identity for every prepared queue row",
            "residual_force_gpu_worker_return_receipt_current.json has queue_manifest_identity_coverage_ready=true",
        ),
        _row(
            "run_post_regeneration_validation_chain",
            "pending" if handoff_ready else "blocked",
            " && ".join(POST_RUN_VALIDATION_COMMANDS),
            "return receipt, force derivation, energy/force label, training-data, checkpoint, registry, backlog, and release-gate artifacts are rebuilt",
            "return receipt is ready, force derivation accepts regenerated NPZ bundles, and product AI architecture gap closure is rerun",
        ),
        _row(
            "verify_post_return_production_promotion_ladder",
            "pending" if handoff_ready and promotion_ladder_command_covered else "blocked",
            "inspect the post_return_promotion_ladder stages in this handoff package after running the validation chain",
            "every promotion ladder stage has its required ready_key at the required value before production inference or release claims",
            "goal_complete=true only after production_promotion_allowed=true and all AI architecture/release gates are green",
        ),
        _row(
            "verify_post_return_production_output_contract",
            "pending" if handoff_ready and promotion_ladder_command_covered else "blocked",
            "inspect post_return_required_production_output_fields and post_return_gpu_unlock_output_fields after running the validation chain",
            "GPU return evidence unlocks delta_force, uncertainty, abstention_reason, and stage2_route_decision before checkpoint sidecar/preflight can pass",
            "residual_production_checkpoint_preflight_current.json has every required_output_field present and force receipt/training contract ready",
        ),
    ]
    blockers: list[str] = []
    if not queue_ready:
        blockers.append("regeneration_queue_execution_ready")
    if not queue_csv:
        blockers.append("regeneration_queue_csv")
    elif not queue_csv_present:
        blockers.append("regeneration_queue_csv_present")
    elif not queue_identity_columns_present:
        blockers.append("queue_identity_columns")
    if not return_manifest_template_ready:
        blockers.append("return_manifest_template_ready")
    elif not return_manifest_template_row_count_matches_queue:
        blockers.append("return_manifest_template_row_count_matches_queue")
    if not return_summary_template_ready:
        blockers.append("return_summary_template_ready")
    elif not return_summary_template_row_count_matches_queue:
        blockers.append("return_summary_template_row_count_matches_queue")
    if not full_command:
        blockers.append("engine_command")
    if gpu_backend_unavailable:
        blockers.append("gpu_backend_available")
    if not promotion_ladder_command_covered:
        blockers.append("post_return_promotion_ladder_command_coverage")
    status = (
        "residual_force_gpu_worker_handoff_package_ready"
        if handoff_ready
        else "blocked_residual_force_gpu_worker_handoff_package"
    )
    summary = {
        "packet_type": "residual_force_gpu_worker_handoff_package",
        "status": status,
        "gpu_worker_handoff_ready": handoff_ready,
        "gpu_worker_handoff_required": handoff_required,
        "operator_action_required": handoff_required,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "regeneration_queue_artifact": regeneration_queue_path,
        "execution_probe_artifact": execution_probe_path,
        "return_manifest_template_artifact": return_manifest_template_path,
        "return_summary_template_artifact": return_summary_template_path,
        "return_summary_template_payload_json": return_summary_template_payload_json,
        "operator_transfer_manifest_ready": operator_transfer_manifest_ready,
        "operator_transfer_outbound_artifact_count": len(outbound_artifacts),
        "operator_transfer_outbound_artifacts": outbound_artifacts,
        "operator_transfer_inbound_artifact_count": len(inbound_artifacts),
        "operator_transfer_inbound_artifacts": inbound_artifacts,
        "operator_transfer_first_return_artifact": inbound_artifacts[0],
        "operator_transfer_return_manifest_artifact": actual_manifest_return_path,
        "worker_rocm_manifest_return_required": True,
        "worker_rocm_manifest_return_artifact": DEFAULT_WORKER_ROCM_MANIFEST_JSON,
        "worker_rocm_manifest_validation_command": "python3 tools/build_rocm_environment_manifest.py",
        "worker_rocm_manifest_completion_rule": WORKER_ROCM_MANIFEST_COMPLETION_RULE,
        "operator_transfer_post_return_validation_command": " && ".join(POST_RUN_VALIDATION_COMMANDS),
        "operator_transfer_acceptance_ready_key": "gpu_worker_return_receipt_ready",
        "operator_transfer_acceptance_artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
        "queue_rows": queue_rows,
        "queue_csv": queue_csv,
        "queue_csv_present": queue_csv_present,
        "queue_csv_sha256": queue_csv_sha256,
        "queue_csv_header_columns": queue_csv_header,
        "required_queue_identity_columns": list(REQUIRED_QUEUE_IDENTITY_COLUMNS),
        "queue_identity_columns_present": queue_identity_columns_present,
        "return_manifest_schema_contract_ready": return_manifest_schema_contract_ready,
        "return_manifest_template_ready": return_manifest_template_ready,
        "return_manifest_template_csv": return_manifest_template_csv,
        "return_manifest_template_row_count": return_manifest_template_row_count,
        "return_manifest_template_row_count_matches_queue": return_manifest_template_row_count_matches_queue,
        "return_summary_template_ready": return_summary_template_ready,
        "return_summary_template_expected_queue_rows": return_summary_template_expected_queue_rows,
        "return_summary_template_row_count_matches_queue": return_summary_template_row_count_matches_queue,
        "return_summary_actual_path": return_summary_actual_path,
        "return_summary_required_fields": return_summary_required_fields,
        "return_summary_completion_rule": return_summary_completion_rule,
        "return_manifest_status_column": RETURN_MANIFEST_STATUS_COLUMN,
        "return_manifest_queue_id_columns": list(RETURN_MANIFEST_QUEUE_ID_COLUMNS),
        "return_manifest_npz_columns": list(RETURN_MANIFEST_NPZ_COLUMNS),
        "return_manifest_fingerprint_columns": list(RETURN_MANIFEST_FINGERPRINT_COLUMNS),
        "return_manifest_required_identity_rule": (
            "Every returned manifest row must include status and either a prepared queue_id/source_queue_id/regeneration_queue_id "
            "or an expected/generated NPZ path or queue_row_fingerprint matching the handoff queue."
        ),
        "engine_runtime_ready": engine_runtime_ready,
        "gpu_backend_unavailable": gpu_backend_unavailable,
        "pilot_abort_reason": _text(probe.get("pilot_abort_reason")),
        "tiny_pilot_command": pilot_command,
        "full_regeneration_command": full_command,
        "post_run_validation_command_count": len(POST_RUN_VALIDATION_COMMANDS),
        "post_run_validation_commands": list(POST_RUN_VALIDATION_COMMANDS),
        "post_return_promotion_ladder_ready": promotion_ladder_command_covered,
        "post_return_promotion_ladder_stage_count": len(POST_RETURN_PROMOTION_LADDER),
        "post_return_promotion_ladder_missing_stages": promotion_ladder_missing_stages,
        "post_return_promotion_ladder": list(POST_RETURN_PROMOTION_LADDER),
        "post_return_promotion_ladder_ready_keys": [
            f"{stage['artifact']}::{stage['ready_key']}={stage['required_value']}"
            for stage in POST_RETURN_PROMOTION_LADDER
        ],
        "post_return_output_contract_ready": promotion_ladder_command_covered,
        "post_return_required_production_output_fields": list(REQUIRED_PRODUCTION_OUTPUT_FIELDS),
        "post_return_gpu_unlock_output_fields": list(GPU_RETURN_UNLOCK_OUTPUT_FIELDS),
        "post_return_gpu_unlock_artifacts": list(GPU_RETURN_UNLOCK_ARTIFACTS),
        "post_return_min_expected_label_rows": queue_rows,
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run this handoff package on a GPU-equipped worker, rerun the execution probe, then rerun the post-regeneration validation chain."
            if handoff_ready
            else "Repair the trajectory regeneration queue or command before GPU worker handoff."
        ),
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
        "# Residual Force GPU Worker Handoff Package",
        "",
        f"- status: `{s['status']}`",
        f"- gpu_worker_handoff_ready: `{s['gpu_worker_handoff_ready']}`",
        f"- gpu_worker_handoff_required: `{s['gpu_worker_handoff_required']}`",
        f"- queue_rows: `{s['queue_rows']}`",
        f"- queue_csv_present: `{s['queue_csv_present']}`",
        f"- queue_csv_sha256: `{s['queue_csv_sha256']}`",
        f"- queue_identity_columns_present: `{s['queue_identity_columns_present']}`",
        f"- return_manifest_schema_contract_ready: `{s['return_manifest_schema_contract_ready']}`",
        f"- return_manifest_template_ready: `{s['return_manifest_template_ready']}`",
        f"- return_manifest_template_csv: `{s['return_manifest_template_csv']}`",
        f"- return_manifest_template_row_count: `{s['return_manifest_template_row_count']}`",
        f"- return_summary_template_ready: `{s['return_summary_template_ready']}`",
        f"- return_summary_template_expected_queue_rows: `{s['return_summary_template_expected_queue_rows']}`",
        f"- return_summary_template_payload_json: `{s['return_summary_template_payload_json']}`",
        f"- return_summary_actual_path: `{s['return_summary_actual_path']}`",
        f"- operator_transfer_manifest_ready: `{s['operator_transfer_manifest_ready']}`",
        f"- operator_transfer_outbound_artifact_count: `{s['operator_transfer_outbound_artifact_count']}`",
        f"- operator_transfer_inbound_artifact_count: `{s['operator_transfer_inbound_artifact_count']}`",
        f"- operator_transfer_first_return_artifact: `{s['operator_transfer_first_return_artifact']}`",
        f"- worker_rocm_manifest_return_required: `{s['worker_rocm_manifest_return_required']}`",
        f"- worker_rocm_manifest_return_artifact: `{s['worker_rocm_manifest_return_artifact']}`",
        f"- worker_rocm_manifest_validation_command: `{s['worker_rocm_manifest_validation_command']}`",
        f"- worker_rocm_manifest_completion_rule: `{s['worker_rocm_manifest_completion_rule']}`",
        f"- engine_runtime_ready: `{s['engine_runtime_ready']}`",
        f"- gpu_backend_unavailable: `{s['gpu_backend_unavailable']}`",
        f"- pilot_abort_reason: `{s['pilot_abort_reason']}`",
        f"- post_return_promotion_ladder_ready: `{s['post_return_promotion_ladder_ready']}`",
        f"- post_return_promotion_ladder_stage_count: `{s['post_return_promotion_ladder_stage_count']}`",
        f"- post_return_output_contract_ready: `{s['post_return_output_contract_ready']}`",
        f"- post_return_gpu_unlock_output_fields: `{','.join(s['post_return_gpu_unlock_output_fields'])}`",
        f"- post_return_min_expected_label_rows: `{s['post_return_min_expected_label_rows']}`",
        "",
        "## Commands",
        "",
        "### Tiny Pilot",
        "",
        "```bash",
        s["tiny_pilot_command"],
        "```",
        "",
        "### Full Regeneration",
        "",
        "```bash",
        s["full_regeneration_command"],
        "```",
        "",
        "### Post-Run Validation",
        "",
        "```bash",
        " && ".join(s["post_run_validation_commands"]),
        "```",
        "",
        "## Return Manifest Schema",
        "",
        f"- status column: `{s['return_manifest_status_column']}`",
        f"- accepted queue-id columns: `{','.join(s['return_manifest_queue_id_columns'])}`",
        f"- accepted NPZ path columns: `{','.join(s['return_manifest_npz_columns'])}`",
        f"- accepted fingerprint columns: `{','.join(s['return_manifest_fingerprint_columns'])}`",
        f"- identity rule: {s['return_manifest_required_identity_rule']}",
        f"- prefilled template: `{s['return_manifest_template_csv']}`",
        "",
        "## Return Summary Schema",
        "",
        f"- actual summary path: `{s['return_summary_actual_path']}`",
        f"- required fields: `{','.join(s['return_summary_required_fields'])}`",
        f"- completion rule: {s['return_summary_completion_rule']}",
        f"- fillable JSON skeleton: `{s['return_summary_template_payload_json']}`",
        f"- summary contract packet: `{s['return_summary_template_artifact']}`",
        "",
        "## Operator Transfer Manifest",
        "",
        "### Copy To GPU Worker",
        "",
    ]
    for artifact in s["operator_transfer_outbound_artifacts"]:
        lines.append(f"- `{artifact}`")
    lines.extend(
        [
            "",
            "### Return From GPU Worker",
            "",
        ]
    )
    for artifact in s["operator_transfer_inbound_artifacts"]:
        lines.append(f"- `{artifact}`")
    lines.extend(
        [
            "",
            f"- acceptance artifact: `{s['operator_transfer_acceptance_artifact']}`",
            f"- acceptance ready key: `{s['operator_transfer_acceptance_ready_key']}`",
            "",
            "### Post-Return Validation Command",
            "",
            "```bash",
            s["operator_transfer_post_return_validation_command"],
            "```",
            "",
            "## Post-Return Output Contract",
            "",
            f"- required production output fields: `{','.join(s['post_return_required_production_output_fields'])}`",
            f"- GPU-return unlock output fields: `{','.join(s['post_return_gpu_unlock_output_fields'])}`",
            f"- minimum expected label rows: `{s['post_return_min_expected_label_rows']}`",
            "",
        ]
    )
    lines.extend(
        [
            "## Post-Return Promotion Ladder",
            "",
            "| stage | artifact | ready key | required | release effect |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for stage in s["post_return_promotion_ladder"]:
        lines.append(
            f"| `{stage['stage_id']}` | `{stage['artifact']}` | `{stage['ready_key']}` | "
            f"`{stage['required_value']}` | {stage['release_effect']} |"
        )
    lines.extend(
        [
        "",
        "## Handoff Steps",
        "",
        "| step | status | command | required | acceptance |",
        "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['step_id']}` | `{row['status']}` | `{row['command']}` | `{row['required']}` | `{row['acceptance']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual force GPU worker handoff package.")
    parser.add_argument("--regeneration-queue-json", default=DEFAULT_REGENERATION_QUEUE_JSON)
    parser.add_argument("--execution-probe-json", default=DEFAULT_EXECUTION_PROBE_JSON)
    parser.add_argument("--return-manifest-template-json", default=DEFAULT_RETURN_MANIFEST_TEMPLATE_JSON)
    parser.add_argument("--return-summary-template-json", default=DEFAULT_RETURN_SUMMARY_TEMPLATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_gpu_worker_handoff_package(
        regeneration_queue_packet=_read_json_if_present(args.regeneration_queue_json),
        execution_probe_packet=_read_json_if_present(args.execution_probe_json),
        return_manifest_template_packet=_read_json_if_present(args.return_manifest_template_json),
        return_summary_template_packet=_read_json_if_present(args.return_summary_template_json),
        regeneration_queue_path=args.regeneration_queue_json,
        execution_probe_path=args.execution_probe_json,
        return_manifest_template_path=args.return_manifest_template_json,
        return_summary_template_path=args.return_summary_template_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
