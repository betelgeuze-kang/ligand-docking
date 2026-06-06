#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESIDUAL_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_ASSIST_GATE_JSON = "runs/residual_assist_promotion_gate_current.json"
DEFAULT_PUBLIC_ASSIST_GATE_JSON = "runs/public_benchmark_residual_assist_comparison_gate_current.json"
DEFAULT_CHECKPOINT_WORK_ORDER_JSON = "runs/residual_production_checkpoint_work_order_current.json"
DEFAULT_SUPERVISED_DATASET_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_SCORE_MODEL_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_ENERGY_FORCE_LABEL_WORK_ORDER_JSON = "runs/residual_energy_force_label_evidence_work_order_current.json"
DEFAULT_UNCERTAINTY_POLICY_EVIDENCE_JSON = "runs/residual_uncertainty_policy_evidence_contract_current.json"
DEFAULT_AUX_SUMMARY_GLOB = "runs/*trajectory_aux*summary.json"
DEFAULT_OUT_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_OUT_CSV = "runs/residual_production_training_data_contract_current.csv"
DEFAULT_OUT_MD = "runs/residual_production_training_data_contract_current.md"

REQUIRED_OUTPUT_FIELDS = (
    "delta_score",
    "corrected_score",
    "delta_energy",
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
)
ENERGY_FORCE_LABEL_FIELDS = ("delta_energy", "delta_force")
UNCERTAINTY_POLICY_FIELDS = ("uncertainty", "abstention_reason", "stage2_route_decision")

CLAIM_BOUNDARY = (
    "Residual production training-data contract only; audits local dataset, auxiliary model, shadow schema, "
    "benchmark, and checkpoint work-order evidence for a guarded protein-ligand residual production checkpoint. "
    "It does not train models, create checkpoints, create sidecars, run inference, run docking, promote production "
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
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    return value is True


def _row(
    check_id: str,
    status: str,
    observed: str,
    required: str,
    source_artifact: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "source_artifact": source_artifact,
        "next_action": next_action,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _scan_aux_summaries(pattern: str) -> list[tuple[str, dict[str, Any]]]:
    paths = sorted(glob.glob(str(_resolve(pattern))))
    packets: list[tuple[str, dict[str, Any]]] = []
    for path in paths:
        packet = _read_json_if_present(path)
        if packet:
            packets.append((str(Path(path).relative_to(ROOT)) if str(path).startswith(str(ROOT)) else path, packet))
    return packets


def _dataset_candidates(aux_summary_packets: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for path, packet in aux_summary_packets:
        s = _summary(packet)
        if "rows_emitted" not in s:
            continue
        emitted = _int(s.get("rows_emitted"))
        binder = _int(s.get("binder_rows"))
        unknown = _int(s.get("unknown_label_rows"))
        negative = _int(s.get("negative_rows")) if "negative_rows" in s else max(0, emitted - binder - unknown)
        rows.append(
            {
                "path": path,
                "rows_emitted": emitted,
                "binder_rows": binder,
                "negative_rows": negative,
                "unknown_label_rows": unknown,
                "targets": _int(s.get("targets")),
                "feature_dim": _int(s.get("feature_dim")),
                "dataset_ready_flag": bool(s.get("production_supervised_dataset_ready") is True),
            }
        )
    return sorted(rows, key=lambda row: (row["rows_emitted"], row["targets"], -row["unknown_label_rows"]), reverse=True)


def _training_candidates(aux_summary_packets: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for path, packet in aux_summary_packets:
        s = _summary(packet)
        if "train_rows" not in s and "checkpoint" not in s:
            continue
        best = s.get("best") if isinstance(s.get("best"), dict) else {}
        checkpoint = str(s.get("checkpoint") or "")
        rows.append(
            {
                "path": path,
                "checkpoint": checkpoint,
                "checkpoint_exists": bool(checkpoint and _resolve(checkpoint).exists()),
                "train_rows": _int(s.get("train_rows")),
                "val_rows": _int(s.get("val_rows")),
                "feature_dim": _int(s.get("feature_dim")),
                "auc": _float(best.get("auc")),
                "pr_auc": _float(best.get("pr_auc")),
                "score": _float(best.get("score")),
                "model_role": str(s.get("model_role") or "trajectory_aux_classifier"),
            }
        )
    return sorted(rows, key=lambda row: (row["train_rows"] + row["val_rows"], row["pr_auc"]), reverse=True)


def build_residual_production_training_data_contract(
    *,
    residual_shadow_packet: dict[str, Any],
    assist_gate_packet: dict[str, Any],
    public_assist_gate_packet: dict[str, Any],
    checkpoint_work_order_packet: dict[str, Any],
    supervised_dataset_packet: dict[str, Any] | None = None,
    score_model_packet: dict[str, Any] | None = None,
    energy_force_label_work_order_packet: dict[str, Any] | None = None,
    uncertainty_policy_evidence_packet: dict[str, Any] | None = None,
    aux_summary_packets: list[tuple[str, dict[str, Any]]] | None = None,
    residual_shadow_path: str = DEFAULT_RESIDUAL_SHADOW_JSON,
    assist_gate_path: str = DEFAULT_ASSIST_GATE_JSON,
    public_assist_gate_path: str = DEFAULT_PUBLIC_ASSIST_GATE_JSON,
    checkpoint_work_order_path: str = DEFAULT_CHECKPOINT_WORK_ORDER_JSON,
    supervised_dataset_path: str = DEFAULT_SUPERVISED_DATASET_JSON,
    score_model_path: str = DEFAULT_SCORE_MODEL_JSON,
    energy_force_label_work_order_path: str = DEFAULT_ENERGY_FORCE_LABEL_WORK_ORDER_JSON,
    uncertainty_policy_evidence_path: str = DEFAULT_UNCERTAINTY_POLICY_EVIDENCE_JSON,
    min_dataset_rows: int = 1000,
    min_targets: int = 3,
    min_train_rows: int = 1000,
    min_val_rows: int = 100,
    min_pr_auc: float = 0.50,
) -> dict[str, Any]:
    residual = _summary(residual_shadow_packet)
    assist = _summary(assist_gate_packet)
    public_assist = _summary(public_assist_gate_packet)
    checkpoint = _summary(checkpoint_work_order_packet)
    supervised_dataset = _summary(supervised_dataset_packet or {})
    score_model = _summary(score_model_packet or {})
    energy_force_label_work_order = _summary(energy_force_label_work_order_packet or {})
    uncertainty_policy_evidence = _summary(uncertainty_policy_evidence_packet or {})
    checkpoint_rows = [dict(row) for row in checkpoint_work_order_packet.get("rows", []) or [] if isinstance(row, dict)]
    top_checkpoint = checkpoint_rows[0] if checkpoint_rows else {}
    aux_summary_packets = list(aux_summary_packets or [])
    if supervised_dataset_packet:
        aux_summary_packets.append((supervised_dataset_path, supervised_dataset_packet))
    if score_model_packet:
        aux_summary_packets.append((score_model_path, score_model_packet))

    residual_fields = {str(item) for item in residual.get("residual_output_fields") or []}
    missing_output_fields = [field for field in REQUIRED_OUTPUT_FIELDS if field not in residual_fields]
    schema_ready = _bool(residual.get("residual_shadow_ab_ready")) and not missing_output_fields

    datasets = _dataset_candidates(aux_summary_packets)
    best_dataset = datasets[0] if datasets else {}
    dataset_ready = bool(
        best_dataset
        and best_dataset["rows_emitted"] >= min_dataset_rows
        and best_dataset["targets"] >= min_targets
        and best_dataset["binder_rows"] > 0
        and best_dataset["negative_rows"] > 0
        and best_dataset["unknown_label_rows"] == 0
    )

    training_runs = _training_candidates(aux_summary_packets)
    best_training = training_runs[0] if training_runs else {}
    auxiliary_training_ready = bool(
        best_training
        and best_training["checkpoint_exists"]
        and best_training["train_rows"] >= min_train_rows
        and best_training["val_rows"] >= min_val_rows
        and best_training["pr_auc"] >= min_pr_auc
    )

    checkpoint_preflight_ready = _bool(checkpoint.get("checkpoint_preflight_ready"))
    ready_checkpoint_count = _int(checkpoint.get("ready_checkpoint_count"))
    production_output_head_ready = checkpoint_preflight_ready and ready_checkpoint_count > 0
    score_model_production_checkpoint_ready = _bool(score_model.get("production_checkpoint_ready"))
    missing_production_output_fields = [
        str(field) for field in score_model.get("missing_production_output_fields") or []
    ]
    dataset_label_fields = [str(field) for field in supervised_dataset.get("label_fields") or []]
    dataset_missing_output_labels = [
        str(field) for field in supervised_dataset.get("missing_production_output_labels") or []
    ]
    missing_energy_force_label_fields = [
        field for field in ENERGY_FORCE_LABEL_FIELDS if field in dataset_missing_output_labels
    ]
    missing_uncertainty_policy_label_fields = [
        field for field in UNCERTAINTY_POLICY_FIELDS if field in dataset_missing_output_labels
    ]
    delta_energy_label_evidence_ready = "delta_energy" not in missing_energy_force_label_fields or _bool(
        energy_force_label_work_order.get("delta_energy_label_evidence_ready")
    )
    delta_force_label_evidence_ready = "delta_force" not in missing_energy_force_label_fields or _bool(
        energy_force_label_work_order.get("delta_force_label_evidence_ready")
    )
    learned_output_fields = [str(field) for field in score_model.get("learned_output_fields") or []]
    policy_output_fields = [str(field) for field in score_model.get("policy_output_fields") or []]
    uncertainty_learned_output_ready = "uncertainty" in learned_output_fields or production_output_head_ready
    policy_output_adapter_ready = _bool(score_model.get("policy_output_adapter_ready")) or production_output_head_ready
    policy_output_fields_ready = all(field in policy_output_fields for field in ("abstention_reason", "stage2_route_decision")) or production_output_head_ready
    abstention_schema_ready = _bool(residual.get("abstention_fields_present")) or all(
        field in residual_fields for field in UNCERTAINTY_POLICY_FIELDS
    )
    policy_contract_ready = _bool(uncertainty_policy_evidence.get("uncertainty_policy_evidence_ready")) and str(
        uncertainty_policy_evidence.get("status") or ""
    ).endswith("_ready")
    uncertainty_policy_label_or_sidecar_ready = (
        not missing_uncertainty_policy_label_fields or policy_contract_ready or production_output_head_ready
    )
    uncertainty_policy_evidence_ready = bool(
        uncertainty_learned_output_ready
        and policy_output_adapter_ready
        and policy_output_fields_ready
        and abstention_schema_ready
        and uncertainty_policy_label_or_sidecar_ready
    )
    assist_benchmark_ready = _bool(assist.get("assist_promotion_allowed")) and _bool(public_assist.get("assist_comparison_gate_ready"))
    uncertainty_physics_guard_ready = production_output_head_ready

    rows = [
        _row(
            "residual_output_schema_contract",
            "pass" if schema_ready else "fail",
            f"shadow_ready={residual.get('residual_shadow_ab_ready')};missing_output_fields={','.join(missing_output_fields)}",
            "shadow residual schema exposes all production output fields before any learned model is promoted",
            residual_shadow_path,
            "Keep shadow schema green and reject checkpoint sidecars that omit required output fields.",
        ),
        _row(
            "supervised_ligand_dataset_breadth",
            "pass" if dataset_ready else "fail",
            (
                f"best_rows={best_dataset.get('rows_emitted', 0)};targets={best_dataset.get('targets', 0)};"
                f"binders={best_dataset.get('binder_rows', 0)};negatives={best_dataset.get('negative_rows', 0)};"
                f"unknown_labels={best_dataset.get('unknown_label_rows', 0)}"
            ),
            f">={min_dataset_rows} labeled rows, >={min_targets} targets, positive and negative labels, and zero unknown labels",
            str(best_dataset.get("path") or DEFAULT_AUX_SUMMARY_GLOB),
            "Materialize a broader labeled protein-ligand residual training/eval dataset, not only smoke trajectory-aux rows.",
        ),
        _row(
            "auxiliary_training_quality_floor",
            "pass" if auxiliary_training_ready else "fail",
            (
                f"train_rows={best_training.get('train_rows', 0)};val_rows={best_training.get('val_rows', 0)};"
                f"checkpoint_exists={best_training.get('checkpoint_exists', False)};pr_auc={best_training.get('pr_auc', 0.0)};"
                f"model_role={best_training.get('model_role', 'none')}"
            ),
            f"local training summary has checkpoint, >={min_train_rows} train rows, >={min_val_rows} validation rows, and PR-AUC>={min_pr_auc}",
            str(best_training.get("path") or DEFAULT_AUX_SUMMARY_GLOB),
            "Train/evaluate a production-scale ligand residual or calibrated auxiliary model on the broader labeled dataset.",
        ),
        _row(
            "production_delta_energy_label_evidence",
            "pass" if delta_energy_label_evidence_ready else "fail",
            (
                f"label_fields={','.join(dataset_label_fields)};"
                f"missing_production_output_labels={','.join(dataset_missing_output_labels)};"
                f"energy_proxy_rows={energy_force_label_work_order.get('energy_proxy_rows', 0)};"
                f"unique_energy_proxy_keys={energy_force_label_work_order.get('unique_energy_proxy_keys', 0)};"
                f"delta_energy_proxy_validation_ready={energy_force_label_work_order.get('delta_energy_proxy_validation_ready')}"
            ),
            "delta_energy training/evaluation labels or a validated energy proxy are available before training the production energy head",
            energy_force_label_work_order_path,
            str(
                energy_force_label_work_order.get("next_required_step")
                or "Materialize delta_energy labels or validated energy proxy/evaluation evidence before training the production energy head."
            ),
        ),
        _row(
            "production_delta_force_label_evidence",
            "pass" if delta_force_label_evidence_ready else "fail",
            (
                f"label_fields={','.join(dataset_label_fields)};"
                f"missing_production_output_labels={','.join(dataset_missing_output_labels)};"
                f"force_label_rows={energy_force_label_work_order.get('force_label_rows', 0)};"
                f"unique_force_label_keys={energy_force_label_work_order.get('unique_force_label_keys', 0)};"
                f"valid_trajectory_path_rows={energy_force_label_work_order.get('force_derivation_valid_trajectory_path_rows', 0)};"
                f"existing_trajectory_npz_rows={energy_force_label_work_order.get('force_derivation_existing_trajectory_npz_rows', 0)};"
                f"derivation_input_sample_count={energy_force_label_work_order.get('force_derivation_input_sample_count', 0)};"
                f"effective_min_existing_npz_rows={energy_force_label_work_order.get('force_derivation_effective_min_existing_npz_rows', 0)};"
                f"existing_npz_floor_capped_by_available_paths={energy_force_label_work_order.get('force_derivation_existing_npz_floor_capped_by_available_paths')};"
                f"artifact_recovery_required={energy_force_label_work_order.get('force_artifact_recovery_required')};"
                f"missing_trajectory_npz_rows={energy_force_label_work_order.get('force_artifact_missing_trajectory_npz_rows', 0)};"
                f"top_missing_prefix={energy_force_label_work_order.get('force_artifact_top_missing_prefix', '')};"
                f"trajectory_regeneration_queue_execution_ready={energy_force_label_work_order.get('force_trajectory_regeneration_queue_execution_ready')};"
                f"trajectory_regeneration_queue_rows={energy_force_label_work_order.get('force_trajectory_regeneration_queue_rows', 0)};"
                f"trajectory_regeneration_engine_runtime_ready={energy_force_label_work_order.get('force_trajectory_regeneration_engine_runtime_ready')};"
                f"trajectory_regeneration_gpu_backend_unavailable={energy_force_label_work_order.get('force_trajectory_regeneration_gpu_backend_unavailable')};"
                f"gpu_worker_handoff_ready={energy_force_label_work_order.get('force_gpu_worker_handoff_ready')};"
                f"gpu_worker_handoff_required={energy_force_label_work_order.get('force_gpu_worker_handoff_required')};"
                f"gpu_worker_return_receipt_ready={energy_force_label_work_order.get('force_gpu_worker_return_receipt_ready')};"
                f"gpu_worker_return_receipt_blockers={','.join(str(item) for item in energy_force_label_work_order.get('force_gpu_worker_return_receipt_blockers') or [])};"
                f"gpu_worker_return_summary_manifest_bound={energy_force_label_work_order.get('force_gpu_worker_return_summary_manifest_bound')};"
                f"gpu_worker_return_summary_manifest_csv={energy_force_label_work_order.get('force_gpu_worker_return_summary_manifest_csv', '')};"
                f"gpu_worker_return_summary_out_manifest_csv_present={energy_force_label_work_order.get('force_gpu_worker_return_summary_out_manifest_csv_present')};"
                f"gpu_worker_return_summary_out_manifest_csv={energy_force_label_work_order.get('force_gpu_worker_return_summary_out_manifest_csv', '')};"
                f"gpu_worker_return_summary_out_manifest_csv_bound={energy_force_label_work_order.get('force_gpu_worker_return_summary_out_manifest_csv_bound')};"
                f"gpu_worker_return_summary_out_summary_json_bound={energy_force_label_work_order.get('force_gpu_worker_return_summary_out_summary_json_bound')};"
                f"gpu_worker_return_summary_out_summary_json={energy_force_label_work_order.get('force_gpu_worker_return_summary_out_summary_json', '')};"
                f"gpu_worker_return_summary_manifest_row_counts_consistent={energy_force_label_work_order.get('force_gpu_worker_return_summary_manifest_row_counts_consistent')};"
                f"gpu_worker_return_summary_ok_rows={energy_force_label_work_order.get('force_gpu_worker_return_summary_ok_rows', 0)};"
                f"gpu_worker_return_manifest_ok_row_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_ok_row_count', 0)};"
                f"gpu_worker_return_manifest_status_placeholder_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_status_placeholder_count', 0)};"
                f"gpu_worker_return_manifest_status_invalid_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_status_invalid_count', 0)};"
                f"gpu_worker_return_manifest_allowed_ok_status_values={','.join(str(item) for item in energy_force_label_work_order.get('force_gpu_worker_return_manifest_allowed_ok_status_values') or [])};"
                f"gpu_worker_return_manifest_npz_paths_complete={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_paths_complete')};"
                f"gpu_worker_return_manifest_npz_path_present_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_path_present_count', 0)};"
                f"gpu_worker_return_manifest_npz_path_missing_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_path_missing_count', 0)};"
                f"gpu_worker_return_manifest_ok_row_missing_npz_path_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_ok_row_missing_npz_path_count', 0)};"
                f"gpu_worker_return_manifest_operator_verified_missing_npz_path_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_operator_verified_missing_npz_path_count', 0)};"
                f"gpu_worker_return_manifest_npz_files_exist={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_files_exist')};"
                f"gpu_worker_return_manifest_npz_file_existing_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_file_existing_count', 0)};"
                f"gpu_worker_return_manifest_npz_file_missing_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_file_missing_count', 0)};"
                f"gpu_worker_return_manifest_ok_row_missing_npz_file_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_ok_row_missing_npz_file_count', 0)};"
                f"gpu_worker_return_manifest_operator_verified_missing_npz_file_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_operator_verified_missing_npz_file_count', 0)};"
                f"gpu_worker_return_manifest_npz_files_valid={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_files_valid')};"
                f"gpu_worker_return_manifest_npz_file_valid_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_file_valid_count', 0)};"
                f"gpu_worker_return_manifest_npz_file_invalid_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_file_invalid_count', 0)};"
                f"gpu_worker_return_manifest_ok_row_invalid_npz_file_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_ok_row_invalid_npz_file_count', 0)};"
                f"gpu_worker_return_manifest_operator_verified_invalid_npz_file_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_operator_verified_invalid_npz_file_count', 0)};"
                f"gpu_worker_return_manifest_npz_schema_valid={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_schema_valid')};"
                f"gpu_worker_return_manifest_npz_schema_valid_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_schema_valid_count', 0)};"
                f"gpu_worker_return_manifest_npz_schema_invalid_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_schema_invalid_count', 0)};"
                f"gpu_worker_return_manifest_ok_row_invalid_npz_schema_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_ok_row_invalid_npz_schema_count', 0)};"
                f"gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count', 0)};"
                f"gpu_worker_return_manifest_npz_identity_valid={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_identity_valid')};"
                f"gpu_worker_return_manifest_npz_identity_valid_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_identity_valid_count', 0)};"
                f"gpu_worker_return_manifest_npz_identity_invalid_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_npz_identity_invalid_count', 0)};"
                f"gpu_worker_return_manifest_ok_row_invalid_npz_identity_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_ok_row_invalid_npz_identity_count', 0)};"
                f"gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count={energy_force_label_work_order.get('force_gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count', 0)};"
                f"gpu_worker_return_identity_coverage_ready={energy_force_label_work_order.get('force_gpu_worker_return_identity_coverage_ready')};"
                f"gpu_worker_return_matched_queue_id_count={energy_force_label_work_order.get('force_gpu_worker_return_matched_queue_id_count', 0)};"
                f"gpu_worker_return_matched_expected_npz_count={energy_force_label_work_order.get('force_gpu_worker_return_matched_expected_npz_count', 0)};"
                f"gpu_worker_return_missing_queue_id_count={energy_force_label_work_order.get('force_gpu_worker_return_missing_queue_id_count', 0)};"
                f"gpu_worker_return_missing_expected_npz_count={energy_force_label_work_order.get('force_gpu_worker_return_missing_expected_npz_count', 0)};"
                f"force_derivation_input_ready={energy_force_label_work_order.get('force_derivation_input_ready')};"
                f"delta_force_derivation_validation_ready={energy_force_label_work_order.get('delta_force_derivation_validation_ready')}"
            ),
            "delta_force training/evaluation labels or a validated -grad(delta_energy) derivation set are available before training the production force head",
            energy_force_label_work_order_path,
            str(
                energy_force_label_work_order.get("next_required_step")
                or "Materialize delta_force labels or validated force-derivation evidence before training the production force head."
            ),
        ),
        _row(
            "production_uncertainty_abstention_route_policy",
            "pass" if uncertainty_policy_evidence_ready else "fail",
            (
                f"label_fields={','.join(dataset_label_fields)};"
                f"missing_uncertainty_policy_labels={','.join(missing_uncertainty_policy_label_fields)};"
                f"learned_output_fields={','.join(learned_output_fields)};"
                f"policy_output_fields={','.join(policy_output_fields)};"
                f"uncertainty_learned_output_ready={uncertainty_learned_output_ready};"
                f"policy_output_adapter_ready={policy_output_adapter_ready};"
                f"policy_output_fields_ready={policy_output_fields_ready};"
                f"abstention_schema_ready={abstention_schema_ready};"
                f"policy_contract_ready={policy_contract_ready};"
                f"checkpoint_preflight_ready={checkpoint_preflight_ready}"
            ),
            "uncertainty, abstention_reason, and stage2_route_decision have label evidence or calibrated sidecar/policy evidence before production promotion",
            f"{score_model_path};{residual_shadow_path};{uncertainty_policy_evidence_path};{checkpoint_work_order_path}",
            (
                "Build the uncertainty/policy evidence contract, attach checkpoint sidecar evidence, or materialize policy labels before treating the residual model as a production inference subject."
            ),
        ),
        dict(
            _row(
                "production_residual_output_head",
                "pass" if production_output_head_ready else "fail",
                (
                    f"checkpoint_preflight_ready={checkpoint_preflight_ready};ready_checkpoint_count={ready_checkpoint_count};"
                    f"top_checkpoint={top_checkpoint.get('checkpoint_path', '')};"
                    f"top_compatibility={top_checkpoint.get('compatibility_status', '')};"
                    f"score_model_production_checkpoint_ready={score_model_production_checkpoint_ready};"
                    f"missing_production_output_fields={','.join(missing_production_output_fields)}"
                ),
                "at least one preflight-ready protein-ligand residual checkpoint with required sidecar and output contract",
                checkpoint_work_order_path,
                str(top_checkpoint.get("required_action") or "Create or select a protein-ligand residual checkpoint, attach sidecar metadata, then rerun preflight."),
            ),
            missing_production_output_fields=missing_production_output_fields,
            score_model_production_checkpoint_ready=score_model_production_checkpoint_ready,
            score_model_artifact=score_model_path,
        ),
        _row(
            "assist_benchmark_evidence",
            "pass" if assist_benchmark_ready else "fail",
            (
                f"assist_promotion_allowed={assist.get('assist_promotion_allowed')};"
                f"public_assist_gate_ready={public_assist.get('assist_comparison_gate_ready')}"
            ),
            "assist/shadow benchmark evidence is green before production checkpoint work starts",
            f"{assist_gate_path};{public_assist_gate_path}",
            "Keep assist benchmark gate green while adding production checkpoint evidence.",
        ),
        _row(
            "uncertainty_physics_guard_binding",
            "pass" if uncertainty_physics_guard_ready else "fail",
            (
                f"checkpoint_preflight_ready={checkpoint_preflight_ready};ready_checkpoint_count={ready_checkpoint_count};"
                f"top_checkpoint={top_checkpoint.get('checkpoint_path', '')};"
                f"top_blockers={top_checkpoint.get('current_blockers', '')}"
            ),
            "production checkpoint preflight proves uncertainty calibration and physics guard binding",
            checkpoint_work_order_path,
            "Bind uncertainty calibration and physics guard evidence into the checkpoint sidecar metadata.",
        ),
    ]

    fail_rows = [row for row in rows if row["status"] != "pass"]
    ready = not fail_rows
    summary = {
        "packet_type": "residual_production_training_data_contract",
        "status": "residual_production_training_data_contract_ready" if ready else "blocked_residual_production_training_data_contract",
        "production_training_data_ready": ready,
        "dataset_candidate_count": len(datasets),
        "training_candidate_count": len(training_runs),
        "best_dataset_artifact": best_dataset.get("path", ""),
        "best_training_artifact": best_training.get("path", ""),
        "best_training_checkpoint": best_training.get("checkpoint", ""),
        "check_count": len(rows),
        "pass_check_count": len(rows) - len(fail_rows),
        "fail_check_count": len(fail_rows),
        "failed_check_ids": [row["check_id"] for row in fail_rows],
        "primary_blocker": fail_rows[0]["check_id"] if fail_rows else "none",
        "required_output_fields": list(REQUIRED_OUTPUT_FIELDS),
        "production_missing_output_fields": missing_production_output_fields,
        "dataset_label_fields": dataset_label_fields,
        "dataset_missing_output_labels": dataset_missing_output_labels,
        "missing_energy_force_label_fields": missing_energy_force_label_fields,
        "missing_uncertainty_policy_label_fields": missing_uncertainty_policy_label_fields,
        "delta_energy_label_evidence_ready": delta_energy_label_evidence_ready,
        "delta_force_label_evidence_ready": delta_force_label_evidence_ready,
        "uncertainty_policy_evidence_ready": uncertainty_policy_evidence_ready,
        "uncertainty_policy_contract_ready": policy_contract_ready,
        "uncertainty_policy_evidence_artifact": uncertainty_policy_evidence_path,
        "uncertainty_learned_output_ready": uncertainty_learned_output_ready,
        "policy_output_adapter_ready": policy_output_adapter_ready,
        "policy_output_fields_ready": policy_output_fields_ready,
        "abstention_schema_ready": abstention_schema_ready,
        "energy_force_label_work_order_artifact": energy_force_label_work_order_path,
        "score_model_production_checkpoint_ready": score_model_production_checkpoint_ready,
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Training-data and checkpoint contract is ready; rerun checkpoint preflight and registry."
            if ready
            else fail_rows[0]["next_action"]
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
        "# Residual Production Training Data Contract",
        "",
        f"- status: `{s['status']}`",
        f"- production_training_data_ready: `{s['production_training_data_ready']}`",
        f"- pass_check_count: `{s['pass_check_count']}` / `{s['check_count']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        f"- dataset_candidate_count: `{s['dataset_candidate_count']}`",
        f"- training_candidate_count: `{s['training_candidate_count']}`",
        f"- best_dataset_artifact: `{s['best_dataset_artifact']}`",
        f"- best_training_artifact: `{s['best_training_artifact']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual production training-data readiness contract.")
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_JSON)
    parser.add_argument("--assist-gate-json", default=DEFAULT_ASSIST_GATE_JSON)
    parser.add_argument("--public-assist-gate-json", default=DEFAULT_PUBLIC_ASSIST_GATE_JSON)
    parser.add_argument("--checkpoint-work-order-json", default=DEFAULT_CHECKPOINT_WORK_ORDER_JSON)
    parser.add_argument("--supervised-dataset-json", default=DEFAULT_SUPERVISED_DATASET_JSON)
    parser.add_argument("--score-model-json", default=DEFAULT_SCORE_MODEL_JSON)
    parser.add_argument("--energy-force-label-work-order-json", default=DEFAULT_ENERGY_FORCE_LABEL_WORK_ORDER_JSON)
    parser.add_argument("--uncertainty-policy-evidence-json", default=DEFAULT_UNCERTAINTY_POLICY_EVIDENCE_JSON)
    parser.add_argument("--aux-summary-glob", default=DEFAULT_AUX_SUMMARY_GLOB)
    parser.add_argument("--min-dataset-rows", type=int, default=1000)
    parser.add_argument("--min-targets", type=int, default=3)
    parser.add_argument("--min-train-rows", type=int, default=1000)
    parser.add_argument("--min-val-rows", type=int, default=100)
    parser.add_argument("--min-pr-auc", type=float, default=0.50)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_production_training_data_contract(
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        assist_gate_packet=_read_json_if_present(args.assist_gate_json),
        public_assist_gate_packet=_read_json_if_present(args.public_assist_gate_json),
        checkpoint_work_order_packet=_read_json_if_present(args.checkpoint_work_order_json),
        supervised_dataset_packet=_read_json_if_present(args.supervised_dataset_json),
        score_model_packet=_read_json_if_present(args.score_model_json),
        energy_force_label_work_order_packet=_read_json_if_present(args.energy_force_label_work_order_json),
        uncertainty_policy_evidence_packet=_read_json_if_present(args.uncertainty_policy_evidence_json),
        aux_summary_packets=_scan_aux_summaries(args.aux_summary_glob),
        residual_shadow_path=args.residual_shadow_json,
        assist_gate_path=args.assist_gate_json,
        public_assist_gate_path=args.public_assist_gate_json,
        checkpoint_work_order_path=args.checkpoint_work_order_json,
        supervised_dataset_path=args.supervised_dataset_json,
        score_model_path=args.score_model_json,
        energy_force_label_work_order_path=args.energy_force_label_work_order_json,
        uncertainty_policy_evidence_path=args.uncertainty_policy_evidence_json,
        min_dataset_rows=args.min_dataset_rows,
        min_targets=args.min_targets,
        min_train_rows=args.min_train_rows,
        min_val_rows=args.min_val_rows,
        min_pr_auc=args.min_pr_auc,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
