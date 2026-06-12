from __future__ import annotations

from typing import Any

CLAIM_BOUNDARY = (
    "Production AI checkpoint-readiness contract only; it audits local registry, checkpoint work-order, training-data, "
    "and GPU receipt artifacts for customer-facing guarded production inference. It does not run inference, train "
    "models, create sidecars, create checkpoints, promote production mode, run docking, upload, submit, email, delete, "
    "or mutate external state."
)

ROCM_ENVIRONMENT_UNLOCK_FIELDS = [
    "manifest_ready",
    "rocm_stack_detected",
    "torch_rocm_ready",
    "amd_gpu_detected",
    "visible_device_count",
]
ROCM_WORKER_RUNTIME_RECEIPT_FIELDS = [
    "manifest_ready",
    "rocm_stack_detected",
    "torch_rocm_ready",
    "amd_gpu_detected",
    "visible_device_count",
    "device_names",
    "torch_version",
    "torch_hip_version",
    "prod_mode",
    "require_rust_hip",
    "backend_counts",
]
REGISTRY_PROMOTION_REQUIRED_GATE_IDS = [
    "production_promotion_allowed",
    "customer_facing_mutation_flags",
    "default_residual_mode_guarded",
    "trained_model_checkpoint_count_positive",
]
REGISTRY_PROMOTION_OPERATOR_COMPLETION_FIELDS = [
    "production_promotion_allowed",
    "customer_facing_auto_correction_allowed",
    "customer_facing_score_mutation_allowed",
    "customer_facing_ranking_mutation_allowed",
    "default_residual_mode",
    "trained_model_checkpoint_count",
]


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _list(value: Any) -> list[Any]:
    return list(value or []) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "")


def _first_row_command(packet: dict[str, Any], step_id: str) -> str:
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return ""
    for row in rows:
        if isinstance(row, dict) and row.get("step_id") == step_id:
            return _text(row.get("command"))
    return ""


def _row(check_id: str, ready: bool, observed: str, required: str, next_action: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if ready else "fail",
        "observed": observed,
        "required": required,
        "next_action": "" if ready else next_action,
        "release_blocker": not ready,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _registry_promotion_missing_gate_ids(
    *,
    production_promotion_allowed: bool,
    customer_flags_ready: bool,
    mode_ready: bool,
    trained_checkpoint_count: int,
) -> list[str]:
    missing_registry_gates: list[str] = []
    if not production_promotion_allowed:
        missing_registry_gates.append("production_promotion_allowed")
    if not customer_flags_ready:
        missing_registry_gates.append("customer_facing_mutation_flags")
    if not mode_ready:
        missing_registry_gates.append("default_residual_mode_guarded")
    if trained_checkpoint_count <= 0:
        missing_registry_gates.append("trained_model_checkpoint_count_positive")
    return missing_registry_gates


def _registry_promotion_upstream_acceptance_ready(
    *,
    production_gpu_execution_environment_ready: bool,
    gpu_receipt_ready: bool,
    delta_force_derivation_validation_ready: bool,
    training_data_ready: bool,
    score_model_ready: bool,
    selected_sidecar_ready: bool,
    selected_sidecar_training_ready: bool,
    selected_sidecar_force_receipt_ready: bool,
    checkpoint_preflight_ready: bool,
    ready_checkpoint_count: int,
) -> bool:
    return all(
        (
            production_gpu_execution_environment_ready,
            gpu_receipt_ready,
            delta_force_derivation_validation_ready,
            training_data_ready,
            score_model_ready,
            selected_sidecar_ready,
            selected_sidecar_training_ready,
            selected_sidecar_force_receipt_ready,
            checkpoint_preflight_ready,
            ready_checkpoint_count > 0,
        )
    )


def _registry_promotion_next_action(
    *,
    production_promotion_allowed: bool,
    customer_flags_ready: bool,
    mode_ready: bool,
    trained_checkpoint_count: int,
    production_gpu_execution_environment_ready: bool,
    gpu_receipt_ready: bool,
    delta_force_derivation_validation_ready: bool,
    training_data_ready: bool,
    score_model_ready: bool,
    selected_sidecar_ready: bool,
    selected_sidecar_training_ready: bool,
    selected_sidecar_force_receipt_ready: bool,
    checkpoint_preflight_ready: bool,
    ready_checkpoint_count: int,
) -> str:
    missing_registry_gates = _registry_promotion_missing_gate_ids(
        production_promotion_allowed=production_promotion_allowed,
        customer_flags_ready=customer_flags_ready,
        mode_ready=mode_ready,
        trained_checkpoint_count=trained_checkpoint_count,
    )
    upstream_ready = _registry_promotion_upstream_acceptance_ready(
        production_gpu_execution_environment_ready=production_gpu_execution_environment_ready,
        gpu_receipt_ready=gpu_receipt_ready,
        delta_force_derivation_validation_ready=delta_force_derivation_validation_ready,
        training_data_ready=training_data_ready,
        score_model_ready=score_model_ready,
        selected_sidecar_ready=selected_sidecar_ready,
        selected_sidecar_training_ready=selected_sidecar_training_ready,
        selected_sidecar_force_receipt_ready=selected_sidecar_force_receipt_ready,
        checkpoint_preflight_ready=checkpoint_preflight_ready,
        ready_checkpoint_count=ready_checkpoint_count,
    )
    gate_list = ",".join(missing_registry_gates) or "none"
    if upstream_ready:
        return (
            "Register or promote a trained preflight-ready production checkpoint in residual_model_registry, "
            "then rerun the registry and checkpoint-readiness gates; keep customer-facing mutation disabled "
            f"until registry_customer_facing_promotion_allowed passes. Missing registry gates: {gate_list}."
        )
    return (
        "Keep customer-facing mutation disabled while closing the upstream production-inference acceptance gates, "
        "then rebuild residual_model_registry for guarded promotion. Missing registry gates: "
        f"{gate_list}."
    )


def _acceptance_stage(
    *,
    stage_id: str,
    ready: bool,
    required_checks: list[str],
    artifact: str,
    validation_command: str,
    release_effect: str,
    unlock_fields: list[str] | None = None,
    next_action: str = "",
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "status": "ready" if ready else "blocked",
        "required_checks": required_checks,
        "artifact": artifact,
        "validation_command": validation_command,
        "release_effect": release_effect,
        "unlock_fields": list(unlock_fields or []),
        "next_action": "" if ready else next_action,
        "release_blocker": not ready,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def build_product_production_ai_checkpoint_readiness(
    *,
    registry_packet: dict[str, Any],
    checkpoint_work_order_packet: dict[str, Any],
    training_data_packet: dict[str, Any],
    force_gpu_worker_return_receipt_packet: dict[str, Any],
    force_derivation_validation_packet: dict[str, Any] | None = None,
    force_gpu_worker_handoff_packet: dict[str, Any] | None = None,
    gpu_return_intake_packet: dict[str, Any] | None = None,
    rocm_environment_packet: dict[str, Any] | None = None,
    output_head_gap_contract_packet: dict[str, Any] | None = None,
    registry_artifact_path: str = "runs/residual_model_registry_current.json",
    checkpoint_work_order_artifact_path: str = "runs/residual_production_checkpoint_work_order_current.json",
    training_data_artifact_path: str = "runs/residual_production_training_data_contract_current.json",
    force_gpu_worker_return_receipt_artifact_path: str = "runs/residual_force_gpu_worker_return_receipt_current.json",
    force_derivation_validation_artifact_path: str = "runs/residual_force_derivation_validation_current.json",
    force_gpu_worker_handoff_artifact_path: str = "runs/residual_force_gpu_worker_handoff_package_current.json",
    gpu_return_intake_artifact_path: str = "runs/product_production_ai_gpu_return_intake_current.json",
    rocm_environment_artifact_path: str = "runs/rocm_environment_manifest_current.json",
    output_head_gap_contract_artifact_path: str = "runs/residual_production_output_head_gap_contract_current.json",
) -> dict[str, Any]:
    registry = _summary(registry_packet)
    work_order = _summary(checkpoint_work_order_packet)
    training = _summary(training_data_packet)
    receipt = _summary(force_gpu_worker_return_receipt_packet)
    force_derivation = _summary(force_derivation_validation_packet or {})
    handoff_packet = force_gpu_worker_handoff_packet or {}
    handoff = _summary(handoff_packet)
    gpu_return_intake = _summary(gpu_return_intake_packet or {})
    rocm_environment = _summary(rocm_environment_packet or {})
    output_head_gap = _summary(output_head_gap_contract_packet or {})
    gpu_return_operator_completion_packet = gpu_return_intake.get(
        "operator_return_next_artifact_completion_packet"
    )
    gpu_return_operator_completion_packet = (
        dict(gpu_return_operator_completion_packet)
        if isinstance(gpu_return_operator_completion_packet, dict)
        else {}
    )

    customer_flags_ready = all(
        registry.get(key) is True
        for key in (
            "customer_facing_auto_correction_allowed",
            "customer_facing_score_mutation_allowed",
            "customer_facing_ranking_mutation_allowed",
        )
    )
    mode_ready = str(registry.get("default_residual_mode") or "") in {"assist", "production", "production_guarded"}
    product_model_layer_ready = _bool(registry.get("product_model_layer_ready"))
    production_promotion_allowed = _bool(registry.get("production_promotion_allowed"))
    trained_checkpoint_count = _int(registry.get("trained_model_checkpoint_count"))
    checkpoint_preflight_ready = _bool(work_order.get("checkpoint_preflight_ready"))
    ready_checkpoint_count = _int(work_order.get("ready_checkpoint_count"))
    training_data_ready = _bool(training.get("production_training_data_ready"))
    gpu_receipt_ready = _bool(receipt.get("gpu_worker_return_receipt_ready"))
    delta_force_derivation_validation_ready = _bool(
        force_derivation.get("delta_force_derivation_validation_ready")
    ) or _bool(training.get("delta_force_label_evidence_ready"))
    gpu_handoff_ready = _bool(handoff.get("gpu_worker_handoff_ready"))
    rocm_manifest_ready = _bool(rocm_environment.get("manifest_ready"))
    rocm_stack_detected = _bool(rocm_environment.get("rocm_stack_detected"))
    rocm_torch_ready = _bool(rocm_environment.get("torch_rocm_ready"))
    rocm_amd_gpu_detected = _bool(rocm_environment.get("amd_gpu_detected"))
    rocm_visible_device_count = _int(rocm_environment.get("visible_device_count"))
    rocm_visibility_diagnostic_commands = [
        str(item) for item in _list(rocm_environment.get("gpu_visibility_diagnostic_commands"))
    ]
    rocm_visibility_diagnostic_required_fields = [
        str(item) for item in _list(rocm_environment.get("gpu_visibility_diagnostic_required_fields"))
    ]
    rocm_visibility_diagnostic_return_artifacts = [
        str(item) for item in _list(rocm_environment.get("gpu_visibility_diagnostic_return_artifacts"))
    ]
    production_gpu_execution_environment_ready = bool(
        rocm_manifest_ready
        and rocm_stack_detected
        and rocm_torch_ready
        and rocm_amd_gpu_detected
        and rocm_visible_device_count > 0
    )
    selected_sidecar_ready = _bool(registry.get("selected_sidecar_ready"))
    selected_sidecar_training_ready = _bool(registry.get("selected_sidecar_training_contract_ready"))
    selected_sidecar_force_receipt_ready = _bool(registry.get("selected_sidecar_force_receipt_ready"))
    output_head_gap_contract_ready = _bool(output_head_gap.get("output_head_gap_contract_ready"))
    production_output_heads_complete = _bool(output_head_gap.get("production_output_heads_complete"))
    score_model_ready = bool(
        ready_checkpoint_count > 0
        and not _list(registry.get("checkpoint_missing_output_fields"))
        and not _list(registry.get("checkpoint_missing_adapter_output_policy_fields"))
    )
    registry_promotion_missing_gate_ids = _registry_promotion_missing_gate_ids(
        production_promotion_allowed=production_promotion_allowed,
        customer_flags_ready=customer_flags_ready,
        mode_ready=mode_ready,
        trained_checkpoint_count=trained_checkpoint_count,
    )
    registry_promotion_upstream_acceptance_ready = _registry_promotion_upstream_acceptance_ready(
        production_gpu_execution_environment_ready=production_gpu_execution_environment_ready,
        gpu_receipt_ready=gpu_receipt_ready,
        delta_force_derivation_validation_ready=delta_force_derivation_validation_ready,
        training_data_ready=training_data_ready,
        score_model_ready=score_model_ready,
        selected_sidecar_ready=selected_sidecar_ready,
        selected_sidecar_training_ready=selected_sidecar_training_ready,
        selected_sidecar_force_receipt_ready=selected_sidecar_force_receipt_ready,
        checkpoint_preflight_ready=checkpoint_preflight_ready,
        ready_checkpoint_count=ready_checkpoint_count,
    )
    registry_promotion_next_action = _registry_promotion_next_action(
        production_promotion_allowed=production_promotion_allowed,
        customer_flags_ready=customer_flags_ready,
        mode_ready=mode_ready,
        trained_checkpoint_count=trained_checkpoint_count,
        production_gpu_execution_environment_ready=production_gpu_execution_environment_ready,
        gpu_receipt_ready=gpu_receipt_ready,
        delta_force_derivation_validation_ready=delta_force_derivation_validation_ready,
        training_data_ready=training_data_ready,
        score_model_ready=score_model_ready,
        selected_sidecar_ready=selected_sidecar_ready,
        selected_sidecar_training_ready=selected_sidecar_training_ready,
        selected_sidecar_force_receipt_ready=selected_sidecar_force_receipt_ready,
        checkpoint_preflight_ready=checkpoint_preflight_ready,
        ready_checkpoint_count=ready_checkpoint_count,
    )
    post_return_promotion_ladder = _list(handoff.get("post_return_promotion_ladder"))
    post_return_promotion_ladder_stage_ids = [
        _text(row.get("stage_id")) for row in post_return_promotion_ladder if isinstance(row, dict) and row.get("stage_id")
    ]
    post_run_validation_commands = _list(handoff.get("post_run_validation_commands"))
    return_summary_template_payload_json = _text(handoff.get("return_summary_template_payload_json"))

    rows = [
        _row(
            "registry_product_layer_ready",
            product_model_layer_ready,
            f"product_model_layer_ready={registry.get('product_model_layer_ready')}",
            "residual model product layer is registered",
            "Rebuild residual_model_registry with all required product-layer components present.",
        ),
        _row(
            "registry_customer_facing_promotion_allowed",
            production_promotion_allowed and customer_flags_ready and mode_ready and trained_checkpoint_count > 0,
            (
                f"default_residual_mode={registry.get('default_residual_mode')};"
                f"production_promotion_allowed={registry.get('production_promotion_allowed')};"
                f"customer_facing_auto_correction_allowed={registry.get('customer_facing_auto_correction_allowed')};"
                f"customer_facing_score_mutation_allowed={registry.get('customer_facing_score_mutation_allowed')};"
                f"customer_facing_ranking_mutation_allowed={registry.get('customer_facing_ranking_mutation_allowed')};"
                f"trained_model_checkpoint_count={trained_checkpoint_count}"
            ),
            "production promotion, customer-facing mutation flags, guarded mode, and trained checkpoint count are ready",
            registry_promotion_next_action,
        ),
        _row(
            "production_gpu_execution_environment_ready",
            production_gpu_execution_environment_ready,
            (
                f"rocm_status={rocm_environment.get('status')};"
                f"manifest_ready={rocm_manifest_ready};"
                f"rocm_stack_detected={rocm_stack_detected};"
                f"torch_rocm_ready={rocm_torch_ready};"
                f"amd_gpu_detected={rocm_amd_gpu_detected};"
                f"visible_device_count={rocm_visible_device_count};"
                f"device_names={','.join(str(item) for item in _list(rocm_environment.get('device_names')))}"
            ),
            "ROCm/HIP runtime is ready with at least one visible AMD GPU device for the full production regeneration run",
            (
                "Expose a supported AMD ROCm/HIP device on this node, or move the full regeneration command to a "
                "GPU worker with a ready rocm_environment_manifest."
            ),
        ),
        _row(
            "production_output_heads_complete",
            output_head_gap_contract_ready and production_output_heads_complete,
            (
                f"output_head_gap_contract_ready={output_head_gap_contract_ready};"
                f"production_output_heads_complete={production_output_heads_complete};"
                f"ready_output_field_count={_int(output_head_gap.get('ready_output_field_count'))};"
                f"blocked_output_field_count={_int(output_head_gap.get('blocked_output_field_count'))};"
                f"blocked_output_fields={','.join(str(item) for item in _list(output_head_gap.get('blocked_output_fields')))};"
                f"first_blocked_output_field={output_head_gap.get('first_blocked_output_field')}"
            ),
            "all required production output heads are present across training data, score model, sidecar, preflight, and registry",
            _text(output_head_gap.get("next_required_step"))
            or "Close blocked production output heads before checkpoint promotion.",
        ),
        _row(
            "checkpoint_preflight_ready",
            checkpoint_preflight_ready and ready_checkpoint_count > 0,
            f"checkpoint_preflight_ready={checkpoint_preflight_ready};ready_checkpoint_count={ready_checkpoint_count}",
            "at least one checkpoint is preflight-ready for guarded promotion",
            "Create sidecar metadata, attach training-data/force-receipt/benchmark gates, and rerun checkpoint preflight.",
        ),
        _row(
            "production_training_data_ready",
            training_data_ready,
            (
                f"production_training_data_ready={training_data_ready};"
                f"failed_check_ids={','.join(str(item) for item in _list(training.get('failed_check_ids')))};"
                f"dataset_missing_output_labels={','.join(str(item) for item in _list(training.get('dataset_missing_output_labels')))}"
            ),
            "production training-data contract is ready with required output labels",
            str(training.get("next_required_step") or "Close failed training-data checks before checkpoint promotion."),
        ),
        _row(
            "force_gpu_worker_return_receipt_ready",
            gpu_receipt_ready,
            (
                f"gpu_worker_return_receipt_ready={gpu_receipt_ready};"
                f"blockers={','.join(str(item) for item in _list(receipt.get('blockers')))};"
                f"summary_manifest_bound={receipt.get('full_regeneration_summary_manifest_bound')};"
                f"summary_out_manifest_csv_bound={receipt.get('full_regeneration_summary_out_manifest_csv_bound')};"
                f"summary_out_summary_json_bound={receipt.get('full_regeneration_summary_out_summary_json_bound')};"
                f"summary_manifest_row_counts_consistent={receipt.get('full_regeneration_summary_manifest_row_counts_consistent')};"
                f"production_gpu_backend_provenance_ready={receipt.get('production_gpu_backend_provenance_ready')};"
                f"production_gpu_backend_rows={receipt.get('production_gpu_backend_rows')};"
                f"non_production_backend_rows={receipt.get('production_gpu_backend_non_production_rows')};"
                f"expected_queue_rows={_int(receipt.get('expected_queue_rows'))};"
                f"manifest_ok_row_count={_int(receipt.get('manifest_ok_row_count'))};"
                f"manifest_operator_verified={receipt.get('full_regeneration_manifest_operator_verified')};"
                f"operator_verified_true_count={_int(receipt.get('manifest_operator_verified_true_count'))};"
                f"identity_coverage_ready={receipt.get('queue_manifest_identity_coverage_ready')}"
            ),
            "GPU return receipt covers queue, manifest, operator verification, and post-run force derivation",
            "Return full regeneration summary/manifest, operator verification, identity coverage, and force derivation validation.",
        ),
        _row(
            "selected_sidecar_ready",
            selected_sidecar_ready and selected_sidecar_training_ready and selected_sidecar_force_receipt_ready,
            (
                f"selected_sidecar_status={registry.get('selected_sidecar_status')};"
                f"selected_sidecar_ready={selected_sidecar_ready};"
                f"selected_sidecar_training_contract_ready={selected_sidecar_training_ready};"
                f"selected_sidecar_force_receipt_ready={selected_sidecar_force_receipt_ready};"
                f"selected_sidecar_missing_output_fields={','.join(str(item) for item in _list(registry.get('selected_sidecar_missing_output_fields')))}"
            ),
            "selected checkpoint sidecar is ready and binds training-data plus force receipt provenance",
            "Build a sidecar with full output contract, training-data contract, force receipt provenance, and benchmark gates.",
        ),
    ]
    first_failed_row = next((row for row in rows if row["status"] != "pass"), {})
    first_failed_source_artifacts = {
        "registry_product_layer_ready": registry_artifact_path,
        "registry_customer_facing_promotion_allowed": registry_artifact_path,
        "production_gpu_execution_environment_ready": rocm_environment_artifact_path,
        "production_output_heads_complete": output_head_gap_contract_artifact_path,
        "checkpoint_preflight_ready": checkpoint_work_order_artifact_path,
        "production_training_data_ready": training_data_artifact_path,
        "force_gpu_worker_return_receipt_ready": force_gpu_worker_return_receipt_artifact_path,
        "selected_sidecar_ready": registry_artifact_path,
    }
    production_ai_checkpoint_ready = all(row["status"] == "pass" for row in rows)
    registry_promotion_ready = bool(
        production_promotion_allowed and customer_flags_ready and mode_ready and trained_checkpoint_count > 0
    )
    post_return_validation_command = _first_row_command(handoff_packet, "run_post_regeneration_validation_chain")
    acceptance_rows = [
        _acceptance_stage(
            stage_id="production_gpu_execution_environment_acceptance",
            ready=production_gpu_execution_environment_ready,
            required_checks=["production_gpu_execution_environment_ready"],
            artifact=rocm_environment_artifact_path,
            validation_command="python3 tools/build_rocm_environment_manifest.py",
            release_effect="current worker can execute the full production GPU/HIP trajectory regeneration command",
            unlock_fields=list(ROCM_ENVIRONMENT_UNLOCK_FIELDS),
            next_action=(
                "Expose a visible ROCm/HIP AMD GPU device or hand off the full regeneration command to a GPU worker "
                "with a ready ROCm environment manifest."
            ),
        ),
        _acceptance_stage(
            stage_id="gpu_return_acceptance",
            ready=gpu_receipt_ready,
            required_checks=["force_gpu_worker_return_receipt_ready"],
            artifact=force_gpu_worker_return_receipt_artifact_path,
            validation_command="python3 tools/build_residual_force_gpu_worker_return_receipt.py",
            release_effect="returned GPU trajectory summary/manifest can be trusted as production force-label evidence",
            unlock_fields=["delta_force", "uncertainty", "abstention_reason", "stage2_route_decision"],
            next_action=(
                "Return full regeneration summary/manifest, NPZ paths, operator verification, identity coverage, "
                "and post-run force derivation validation."
            ),
        ),
        _acceptance_stage(
            stage_id="force_derivation_acceptance",
            ready=bool(
                gpu_receipt_ready
                and delta_force_derivation_validation_ready
            ),
            required_checks=["force_gpu_worker_return_receipt_ready", "delta_force_derivation_validation_ready"],
            artifact=force_derivation_validation_artifact_path,
            validation_command="python3 tools/build_residual_force_derivation_validation.py",
            release_effect="regenerated trajectory bundles can provide accepted delta_force derivation inputs",
            unlock_fields=["delta_force"],
            next_action="Rerun force derivation validation after the GPU return receipt is accepted.",
        ),
        _acceptance_stage(
            stage_id="production_training_data_acceptance",
            ready=training_data_ready,
            required_checks=["production_training_data_ready"],
            artifact=training_data_artifact_path,
            validation_command="python3 tools/build_residual_production_training_data_contract.py",
            release_effect="production supervised training data can feed checkpoint training and output-head validation",
            unlock_fields=_list(training.get("dataset_missing_output_labels")),
            next_action=str(training.get("next_required_step") or "Close production training-data failed checks."),
        ),
        _acceptance_stage(
            stage_id="production_score_model_acceptance",
            ready=score_model_ready,
            required_checks=["ready_checkpoint_count_positive", "production_output_policy_complete"],
            artifact="runs/residual_production_score_model_current.json",
            validation_command="python3 tools/train_residual_production_score_model.py",
            release_effect="trained score model advertises all required production residual outputs",
            unlock_fields=_list(registry.get("checkpoint_missing_output_fields")),
            next_action="Train or rebuild a production residual score model with the full output-head contract.",
        ),
        _acceptance_stage(
            stage_id="checkpoint_sidecar_acceptance",
            ready=selected_sidecar_ready and selected_sidecar_training_ready and selected_sidecar_force_receipt_ready,
            required_checks=[
                "selected_sidecar_ready",
                "selected_sidecar_training_contract_ready",
                "selected_sidecar_force_receipt_ready",
            ],
            artifact="runs/residual_production_checkpoint_sidecar_current.json",
            validation_command="python3 tools/build_residual_production_checkpoint_sidecar.py",
            release_effect=(
                "checkpoint sidecar binds training data, force receipt, adapter policy, uncertainty, "
                "and physics guard evidence"
            ),
            unlock_fields=_list(registry.get("selected_sidecar_missing_output_fields")),
            next_action="Build sidecar metadata with full output contract and force-receipt provenance.",
        ),
        _acceptance_stage(
            stage_id="checkpoint_preflight_acceptance",
            ready=checkpoint_preflight_ready and ready_checkpoint_count > 0,
            required_checks=["checkpoint_preflight_ready", "ready_checkpoint_count_positive"],
            artifact=checkpoint_work_order_artifact_path,
            validation_command=(
                "python3 tools/build_residual_production_checkpoint_preflight.py && "
                "python3 tools/build_residual_production_checkpoint_work_order.py"
            ),
            release_effect="checkpoint is eligible for guarded production promotion",
            next_action="Rerun checkpoint preflight after the sidecar and output contracts are ready.",
        ),
        _acceptance_stage(
            stage_id="registry_guarded_promotion_acceptance",
            ready=registry_promotion_ready,
            required_checks=[
                "registry_customer_facing_promotion_allowed",
                "trained_model_checkpoint_count_positive",
                "default_residual_mode_guarded",
            ],
            artifact=registry_artifact_path,
            validation_command=(
                "python3 tools/build_residual_model_registry.py && "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            release_effect=(
                "AI model can become the guarded production inference subject for customer-facing correction"
            ),
            next_action=registry_promotion_next_action,
        ),
    ]
    acceptance_blockers = [row for row in acceptance_rows if row["status"] != "ready"]
    first_acceptance_blocker = acceptance_blockers[0] if acceptance_blockers else {}
    check_ready_by_id = {
        "production_gpu_execution_environment_ready": production_gpu_execution_environment_ready,
        "force_gpu_worker_return_receipt_ready": gpu_receipt_ready,
        "delta_force_derivation_validation_ready": delta_force_derivation_validation_ready,
        "production_training_data_ready": training_data_ready,
        "ready_checkpoint_count_positive": ready_checkpoint_count > 0,
        "production_output_policy_complete": not _list(registry.get("checkpoint_missing_output_fields"))
        and not _list(registry.get("checkpoint_missing_adapter_output_policy_fields")),
        "selected_sidecar_ready": selected_sidecar_ready,
        "selected_sidecar_training_contract_ready": selected_sidecar_training_ready,
        "selected_sidecar_force_receipt_ready": selected_sidecar_force_receipt_ready,
        "checkpoint_preflight_ready": checkpoint_preflight_ready,
        "trained_model_checkpoint_count_positive": trained_checkpoint_count > 0,
        "default_residual_mode_guarded": mode_ready,
        "registry_customer_facing_promotion_allowed": registry_promotion_ready,
    }
    first_actionable_check_id = next(
        (
            str(item)
            for item in (first_acceptance_blocker.get("required_checks") or [])
            if str(item) and check_ready_by_id.get(str(item)) is False
        ),
        next(
            (
                str(item)
                for item in (first_acceptance_blocker.get("required_checks") or [])
                if str(item)
            ),
            "",
        ),
    )
    synthetic_check_rows = {
        "delta_force_derivation_validation_ready": {
            "observed": (
                f"force_derivation_status={force_derivation.get('status')};"
                f"delta_force_derivation_validation_ready={delta_force_derivation_validation_ready};"
                f"blocker_count={_int(force_derivation.get('blocker_count'))}"
            ),
            "required": "delta_force derivation validation is ready",
            "next_action": _text(force_derivation.get("next_required_step"))
            or "Rerun force derivation validation after the GPU return receipt is accepted.",
        },
        "ready_checkpoint_count_positive": {
            "observed": f"ready_checkpoint_count={ready_checkpoint_count}",
            "required": "ready_checkpoint_count is positive",
            "next_action": "Rerun checkpoint preflight after the sidecar and output contracts are ready.",
        },
        "production_output_policy_complete": {
            "observed": (
                "checkpoint_missing_output_fields="
                f"{','.join(str(item) for item in _list(registry.get('checkpoint_missing_output_fields')))};"
                "checkpoint_missing_adapter_output_policy_fields="
                f"{','.join(str(item) for item in _list(registry.get('checkpoint_missing_adapter_output_policy_fields')))}"
            ),
            "required": "production output policy is complete",
            "next_action": "Train or rebuild a production residual score model with the full output-head contract.",
        },
        "trained_model_checkpoint_count_positive": {
            "observed": f"trained_model_checkpoint_count={trained_checkpoint_count}",
            "required": "trained_model_checkpoint_count is positive",
            "next_action": registry_promotion_next_action,
        },
        "default_residual_mode_guarded": {
            "observed": f"default_residual_mode={registry.get('default_residual_mode')}",
            "required": "default residual mode is assist, production, or production_guarded",
            "next_action": registry_promotion_next_action,
        },
    }
    first_actionable_check_row = next(
        (row for row in rows if row.get("check_id") == first_actionable_check_id),
        synthetic_check_rows.get(first_actionable_check_id, {}),
    )
    if first_actionable_check_id == "production_gpu_execution_environment_ready":
        worker_runtime_receipt_contract = {
            "contract_ready": True,
            "artifact_id": "rocm_worker_runtime_receipt",
            "environment_manifest_artifact": rocm_environment_artifact_path,
            "gpu_return_intake_artifact": gpu_return_intake_artifact_path,
            "required_fields_or_columns": list(ROCM_WORKER_RUNTIME_RECEIPT_FIELDS),
            "required_field_count": len(ROCM_WORKER_RUNTIME_RECEIPT_FIELDS),
            "completion_rule": (
                "manifest_ready=true; rocm_stack_detected=true; torch_rocm_ready=true; "
                "amd_gpu_detected=true; visible_device_count>0; prod_mode=true; require_rust_hip=true; "
                "backend_counts includes rocm/hip production backend rows"
            ),
            "post_environment_next_stage_id": "gpu_return_acceptance",
            "post_environment_next_artifact": force_gpu_worker_return_receipt_artifact_path,
            "post_environment_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "full_regeneration_command": _text(handoff.get("full_regeneration_command"))
            or _first_row_command(handoff_packet, "run_full_regeneration_queue"),
            "guardrails": [
                "cpu_fallback_does_not_satisfy_production_inference",
                "torch_rocm_ready_required_before_full_regeneration",
                "visible_amd_gpu_required_before_full_regeneration",
                "prod_mode_and_require_rust_hip_required_in_return_summary",
                "registry_promotion_blocked_until_gpu_receipt_and_sidecar_ready",
            ],
        }
        operator_completion_packet = {
            "artifact_id": "rocm_environment_manifest_json",
            "artifact_path": rocm_environment_artifact_path,
            "packet_ready": True,
            "required_fields_or_columns": list(ROCM_ENVIRONMENT_UNLOCK_FIELDS),
            "diagnostic_commands": list(rocm_visibility_diagnostic_commands),
            "diagnostic_command_count": len(rocm_visibility_diagnostic_commands),
            "diagnostic_required_fields": list(rocm_visibility_diagnostic_required_fields),
            "diagnostic_required_field_count": len(rocm_visibility_diagnostic_required_fields),
            "diagnostic_completion_rule": _text(
                rocm_environment.get("gpu_visibility_diagnostic_completion_rule")
            ),
            "diagnostic_return_artifacts": list(rocm_visibility_diagnostic_return_artifacts),
            "torch_visibility_probe_command": _text(rocm_environment.get("gpu_visibility_torch_probe_command")),
            "completion_rule": (
                "manifest_ready=true; rocm_stack_detected=true; torch_rocm_ready=true; "
                "amd_gpu_detected=true; visible_device_count>0"
            ),
            "validation_command": "python3 tools/build_rocm_environment_manifest.py",
            "worker_runtime_receipt_contract": worker_runtime_receipt_contract,
            "worker_runtime_receipt_required_fields_or_columns": list(ROCM_WORKER_RUNTIME_RECEIPT_FIELDS),
            "worker_runtime_receipt_required_field_count": len(ROCM_WORKER_RUNTIME_RECEIPT_FIELDS),
            "worker_runtime_receipt_completion_rule": worker_runtime_receipt_contract["completion_rule"],
            "post_environment_next_stage_id": worker_runtime_receipt_contract["post_environment_next_stage_id"],
            "post_environment_next_artifact": worker_runtime_receipt_contract["post_environment_next_artifact"],
            "post_environment_validation_command": worker_runtime_receipt_contract[
                "post_environment_validation_command"
            ],
            "full_regeneration_command": worker_runtime_receipt_contract["full_regeneration_command"],
            "next_action": _text(
                first_acceptance_blocker.get("next_action")
                or rocm_environment.get("next_required_step")
            ),
            "observed": (
                f"manifest_ready={rocm_manifest_ready};"
                f"rocm_stack_detected={rocm_stack_detected};"
                f"torch_rocm_ready={rocm_torch_ready};"
                f"amd_gpu_detected={rocm_amd_gpu_detected};"
                f"visible_device_count={rocm_visible_device_count}"
            ),
        }
        operator_completion_packet_artifact = rocm_environment_artifact_path
    elif _text(first_acceptance_blocker.get("stage_id")) == "registry_guarded_promotion_acceptance":
        operator_completion_packet = {
            "artifact_id": "residual_model_registry_guarded_promotion",
            "artifact_path": registry_artifact_path,
            "packet_ready": True,
            "required_fields_or_columns": list(REGISTRY_PROMOTION_OPERATOR_COMPLETION_FIELDS),
            "diagnostic_commands": [
                "python3 tools/build_residual_model_registry.py",
                "python3 tools/build_product_production_ai_checkpoint_readiness.py",
                "python3 tools/build_product_production_ai_promotion_workbench.py",
            ],
            "diagnostic_command_count": 3,
            "diagnostic_required_fields": list(REGISTRY_PROMOTION_OPERATOR_COMPLETION_FIELDS),
            "diagnostic_required_field_count": len(REGISTRY_PROMOTION_OPERATOR_COMPLETION_FIELDS),
            "diagnostic_completion_rule": (
                "production_promotion_allowed=true; all customer-facing mutation flags true; "
                "default_residual_mode in assist/production/production_guarded; "
                "trained_model_checkpoint_count>0"
            ),
            "diagnostic_return_artifacts": [
                registry_artifact_path,
                "runs/product_production_ai_checkpoint_readiness_current.json",
                "runs/product_production_ai_promotion_workbench_current.json",
            ],
            "failed_check_ids": list(registry_promotion_missing_gate_ids),
            "validation_command": (
                "python3 tools/build_residual_model_registry.py && "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py && "
                "python3 tools/build_product_production_ai_promotion_workbench.py"
            ),
            "full_regeneration_command": _text(handoff.get("full_regeneration_command"))
            or _first_row_command(handoff_packet, "run_full_regeneration_queue"),
            "completion_rule": (
                "registry_promotion_missing_gate_count=0 and registry_promotion_currently_satisfied=true"
            ),
            "next_action": registry_promotion_next_action,
            "observed": _text(first_actionable_check_row.get("observed")),
        }
        operator_completion_packet_artifact = registry_artifact_path
    else:
        operator_completion_packet = dict(gpu_return_operator_completion_packet)
        operator_completion_packet_artifact = (
            gpu_return_intake_artifact_path if operator_completion_packet else ""
        )
    worker_runtime_receipt_contract = (
        dict(operator_completion_packet.get("worker_runtime_receipt_contract"))
        if isinstance(operator_completion_packet.get("worker_runtime_receipt_contract"), dict)
        else {}
    )
    acceptance_matrix_ready = bool(acceptance_rows)
    post_return_promotion_ladder_contract_ready = _bool(handoff.get("post_return_promotion_ladder_ready")) or _bool(
        receipt.get("handoff_post_return_promotion_ladder_current")
    )
    post_return_promotion_ladder_currently_satisfied = bool(
        post_return_promotion_ladder_contract_ready and production_ai_checkpoint_ready and not acceptance_blockers
    )
    post_return_promotion_ladder_current_blocked_stage_ids = [
        str(row["stage_id"]) for row in acceptance_blockers
    ]
    next_after_actionable_blocker = acceptance_blockers[1] if len(acceptance_blockers) > 1 else {}
    checkpoint_closure_blockers = _list(work_order.get("checkpoint_closure_blockers"))
    if not production_gpu_execution_environment_ready:
        checkpoint_closure_blockers = [
            *checkpoint_closure_blockers,
            "production_gpu_execution_environment_not_ready",
        ]
    summary = {
        "packet_type": "product_production_ai_checkpoint_readiness",
        "status": (
            "product_production_ai_checkpoint_readiness_ready"
            if production_ai_checkpoint_ready
            else "blocked_product_production_ai_checkpoint_readiness"
        ),
        "production_ai_checkpoint_ready": production_ai_checkpoint_ready,
        "production_ai_inference_subject_active": production_ai_checkpoint_ready,
        "check_count": len(rows),
        "pass_check_count": sum(1 for row in rows if row["status"] == "pass"),
        "fail_check_count": sum(1 for row in rows if row["status"] != "pass"),
        "failed_check_ids": [str(row["check_id"]) for row in rows if row["status"] != "pass"],
        "first_failed_check_id": _text(first_failed_row.get("check_id")),
        "first_failed_source_artifact": first_failed_source_artifacts.get(
            _text(first_failed_row.get("check_id")), ""
        ),
        "first_failed_observed": _text(first_failed_row.get("observed")),
        "first_failed_required": _text(first_failed_row.get("required")),
        "first_failed_next_action": _text(first_failed_row.get("next_action")),
        "product_model_layer_ready": product_model_layer_ready,
        "default_residual_mode": str(registry.get("default_residual_mode") or ""),
        "production_promotion_allowed": production_promotion_allowed,
        "registry_promotion_required_gate_ids": list(REGISTRY_PROMOTION_REQUIRED_GATE_IDS),
        "registry_promotion_missing_gate_ids": list(registry_promotion_missing_gate_ids),
        "registry_promotion_missing_gate_count": len(registry_promotion_missing_gate_ids),
        "registry_promotion_upstream_acceptance_ready": registry_promotion_upstream_acceptance_ready,
        "registry_promotion_currently_satisfied": registry_promotion_ready,
        "customer_facing_auto_correction_allowed": _bool(registry.get("customer_facing_auto_correction_allowed")),
        "customer_facing_score_mutation_allowed": _bool(registry.get("customer_facing_score_mutation_allowed")),
        "customer_facing_ranking_mutation_allowed": _bool(registry.get("customer_facing_ranking_mutation_allowed")),
        "trained_model_checkpoint_count": trained_checkpoint_count,
        "candidate_checkpoint_count": _int(work_order.get("candidate_checkpoint_count")),
        "ready_checkpoint_count": ready_checkpoint_count,
        "checkpoint_preflight_ready": checkpoint_preflight_ready,
        "production_training_data_ready": training_data_ready,
        "delta_force_derivation_validation_ready": delta_force_derivation_validation_ready,
        "force_derivation_validation_status": _text(force_derivation.get("status")),
        "force_derivation_validation_artifact_path": force_derivation_validation_artifact_path,
        "force_derivation_validation_blocker_count": _int(force_derivation.get("blocker_count")),
        "production_output_head_gap_contract_ready": output_head_gap_contract_ready,
        "production_output_heads_complete": production_output_heads_complete,
        "production_output_head_required_field_count": _int(
            output_head_gap.get("required_output_field_count")
        ),
        "production_output_head_ready_field_count": _int(
            output_head_gap.get("ready_output_field_count")
        ),
        "production_output_head_blocked_field_count": _int(
            output_head_gap.get("blocked_output_field_count")
        ),
        "production_output_head_blocked_fields": _list(output_head_gap.get("blocked_output_fields")),
        "production_output_head_first_blocked_field": _text(
            output_head_gap.get("first_blocked_output_field")
        ),
        "production_output_head_first_blocked_field_blockers": _list(
            output_head_gap.get("first_blocked_output_field_blockers")
        ),
        "production_output_head_gap_contract_artifact_path": output_head_gap_contract_artifact_path,
        "force_gpu_worker_return_receipt_ready": gpu_receipt_ready,
        "force_gpu_worker_handoff_ready": gpu_handoff_ready,
        "production_gpu_execution_environment_ready": production_gpu_execution_environment_ready,
        "production_gpu_execution_environment_artifact_path": rocm_environment_artifact_path,
        "production_gpu_execution_environment_status": _text(rocm_environment.get("status")),
        "production_gpu_rocm_manifest_ready": rocm_manifest_ready,
        "production_gpu_rocm_stack_detected": rocm_stack_detected,
        "production_gpu_rocm_torch_ready": rocm_torch_ready,
        "production_gpu_rocm_amd_gpu_detected": rocm_amd_gpu_detected,
        "production_gpu_rocm_visible_device_count": rocm_visible_device_count,
        "production_gpu_rocm_device_names": _list(rocm_environment.get("device_names")),
        "production_gpu_rocm_torch_version": _text(rocm_environment.get("torch_version")),
        "production_gpu_rocm_torch_hip_version": _text(rocm_environment.get("torch_hip_version")),
        "production_gpu_rocm_visibility_diagnostic_packet_ready": _bool(
            rocm_environment.get("gpu_visibility_diagnostic_packet_ready")
        ),
        "production_gpu_rocm_visibility_diagnostic_command_count": len(rocm_visibility_diagnostic_commands),
        "production_gpu_rocm_visibility_diagnostic_commands": list(rocm_visibility_diagnostic_commands),
        "production_gpu_rocm_visibility_diagnostic_required_fields": list(
            rocm_visibility_diagnostic_required_fields
        ),
        "production_gpu_rocm_visibility_diagnostic_required_field_count": len(
            rocm_visibility_diagnostic_required_fields
        ),
        "production_gpu_rocm_visibility_diagnostic_completion_rule": _text(
            rocm_environment.get("gpu_visibility_diagnostic_completion_rule")
        ),
        "production_gpu_rocm_visibility_diagnostic_return_artifacts": list(
            rocm_visibility_diagnostic_return_artifacts
        ),
        "production_gpu_rocm_visibility_torch_probe_command": _text(
            rocm_environment.get("gpu_visibility_torch_probe_command")
        ),
        "production_gpu_rocm_next_required_step": _text(rocm_environment.get("next_required_step")),
        "force_gpu_worker_handoff_required": _bool(handoff.get("gpu_worker_handoff_required")),
        "force_gpu_worker_operator_action_required": _bool(handoff.get("operator_action_required")),
        "force_gpu_worker_handoff_artifact_path": force_gpu_worker_handoff_artifact_path,
        "force_gpu_worker_handoff_next_required_step": _text(handoff.get("next_required_step")),
        "force_gpu_worker_operator_transfer_manifest_ready": _bool(
            handoff.get("operator_transfer_manifest_ready")
        ),
        "force_gpu_worker_operator_transfer_outbound_artifact_count": _int(
            handoff.get("operator_transfer_outbound_artifact_count")
        ),
        "force_gpu_worker_operator_transfer_outbound_artifacts": _list(
            handoff.get("operator_transfer_outbound_artifacts")
        ),
        "force_gpu_worker_operator_transfer_inbound_artifact_count": _int(
            handoff.get("operator_transfer_inbound_artifact_count")
        ),
        "force_gpu_worker_operator_transfer_inbound_artifacts": _list(
            handoff.get("operator_transfer_inbound_artifacts")
        ),
        "force_gpu_worker_operator_transfer_first_return_artifact": _text(
            handoff.get("operator_transfer_first_return_artifact")
        ),
        "force_gpu_worker_operator_transfer_return_manifest_artifact": _text(
            handoff.get("operator_transfer_return_manifest_artifact")
        ),
        "force_gpu_worker_operator_transfer_acceptance_artifact": _text(
            handoff.get("operator_transfer_acceptance_artifact")
        ),
        "force_gpu_worker_operator_transfer_acceptance_ready_key": _text(
            handoff.get("operator_transfer_acceptance_ready_key")
        ),
        "force_gpu_worker_operator_transfer_post_return_validation_command": _text(
            handoff.get("operator_transfer_post_return_validation_command")
        ),
        "force_gpu_worker_return_summary_template_payload_json": return_summary_template_payload_json,
        "force_gpu_worker_full_regeneration_command": _text(handoff.get("full_regeneration_command"))
        or _first_row_command(handoff_packet, "run_full_regeneration_queue"),
        "force_gpu_worker_post_return_validation_command": post_return_validation_command,
        "force_gpu_worker_post_return_output_contract_ready": _bool(
            handoff.get("post_return_output_contract_ready")
        )
        or _bool(receipt.get("handoff_post_return_output_contract_current")),
        "force_gpu_worker_post_return_required_production_output_fields": _list(
            handoff.get("post_return_required_production_output_fields")
            or receipt.get("handoff_post_return_required_production_output_fields")
        ),
        "force_gpu_worker_post_return_gpu_unlock_artifacts": _list(
            handoff.get("post_return_gpu_unlock_artifacts")
        ),
        "force_gpu_worker_post_return_unlock_output_fields": _list(
            handoff.get("post_return_gpu_unlock_output_fields")
            or receipt.get("handoff_post_return_gpu_unlock_output_fields")
        ),
        "force_gpu_worker_post_return_min_expected_label_rows": _int(
            handoff.get("post_return_min_expected_label_rows")
            or receipt.get("handoff_post_return_min_expected_label_rows")
        ),
        "force_gpu_worker_post_return_promotion_ladder_ready": _bool(
            handoff.get("post_return_promotion_ladder_ready")
        )
        or _bool(receipt.get("handoff_post_return_promotion_ladder_current")),
        "force_gpu_worker_post_return_promotion_ladder_contract_ready": (
            post_return_promotion_ladder_contract_ready
        ),
        "force_gpu_worker_post_return_promotion_ladder_currently_satisfied": (
            post_return_promotion_ladder_currently_satisfied
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count": len(
            post_return_promotion_ladder_current_blocked_stage_ids
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids": (
            post_return_promotion_ladder_current_blocked_stage_ids
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id": _text(
            first_acceptance_blocker.get("stage_id")
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact": _text(
            first_acceptance_blocker.get("artifact")
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command": _text(
            first_acceptance_blocker.get("validation_command")
        ),
        "force_gpu_worker_post_return_promotion_ladder_stage_count": _int(
            len(post_return_promotion_ladder)
            or receipt.get("handoff_post_return_promotion_ladder_stage_count")
        ),
        "force_gpu_worker_post_return_promotion_ladder_stage_ids": post_return_promotion_ladder_stage_ids,
        "force_gpu_worker_post_return_promotion_ladder": post_return_promotion_ladder,
        "force_gpu_worker_post_return_promotion_ladder_ready_keys": _list(
            handoff.get("post_return_promotion_ladder_ready_keys")
        ),
        "force_gpu_worker_post_return_promotion_ladder_missing_stages": _list(
            handoff.get("post_return_promotion_ladder_missing_stages")
        ),
        "force_gpu_worker_post_return_promotion_ladder_missing_ready_keys": _list(
            receipt.get("handoff_post_return_promotion_ladder_missing_ready_keys")
        ),
        "production_inference_acceptance_matrix_ready": acceptance_matrix_ready,
        "production_inference_acceptance_stage_count": len(acceptance_rows),
        "production_inference_acceptance_ready_stage_count": len(acceptance_rows) - len(acceptance_blockers),
        "production_inference_acceptance_blocked_stage_count": len(acceptance_blockers),
        "production_inference_acceptance_stage_ids": [str(row["stage_id"]) for row in acceptance_rows],
        "production_inference_acceptance_ready_stage_ids": [
            str(row["stage_id"]) for row in acceptance_rows if row["status"] == "ready"
        ],
        "production_inference_acceptance_blocked_stage_ids": [
            str(row["stage_id"]) for row in acceptance_blockers
        ],
        "production_inference_acceptance_next_stage_id": _text(first_acceptance_blocker.get("stage_id")),
        "production_inference_acceptance_next_stage_artifact": _text(first_acceptance_blocker.get("artifact")),
        "production_inference_acceptance_next_stage_validation_command": _text(
            first_acceptance_blocker.get("validation_command")
        ),
        "production_inference_acceptance_next_stage_release_effect": _text(
            first_acceptance_blocker.get("release_effect")
        ),
        "production_inference_acceptance_next_stage_unlock_fields": [
            str(item) for item in (first_acceptance_blocker.get("unlock_fields") or [])
        ],
        "production_inference_acceptance_next_stage_required_checks": [
            str(item) for item in (first_acceptance_blocker.get("required_checks") or [])
        ],
        "production_inference_acceptance_next_stage_next_action": _text(
            first_acceptance_blocker.get("next_action")
        ),
        "production_inference_actionable_blocker_stage_id": _text(
            first_acceptance_blocker.get("stage_id")
        ),
        "production_inference_actionable_blocker_check_id": first_actionable_check_id,
        "production_inference_actionable_blocker_artifact": _text(
            first_acceptance_blocker.get("artifact")
        ),
        "production_inference_actionable_blocker_observed": _text(
            first_actionable_check_row.get("observed")
        ),
        "production_inference_actionable_blocker_required": _text(
            first_actionable_check_row.get("required")
        ),
        "production_inference_actionable_blocker_next_action": _text(
            first_acceptance_blocker.get("next_action")
            or first_actionable_check_row.get("next_action")
        ),
        "production_inference_actionable_blocker_validation_command": _text(
            first_acceptance_blocker.get("validation_command")
        ),
        "production_inference_actionable_blocker_unlock_fields": [
            str(item) for item in (first_acceptance_blocker.get("unlock_fields") or [])
        ],
        "production_inference_actionable_blocker_downstream_blocked_stage_count": max(
            len(acceptance_blockers) - 1,
            0,
        ),
        "production_inference_next_after_actionable_blocker_stage_id": _text(
            next_after_actionable_blocker.get("stage_id")
        ),
        "production_inference_next_after_actionable_blocker_artifact": _text(
            next_after_actionable_blocker.get("artifact")
        ),
        "production_inference_next_after_actionable_blocker_validation_command": _text(
            next_after_actionable_blocker.get("validation_command")
        ),
        "production_inference_next_after_actionable_blocker_required_checks": [
            str(item) for item in (next_after_actionable_blocker.get("required_checks") or [])
        ],
        "production_inference_next_after_actionable_blocker_unlock_fields": [
            str(item) for item in (next_after_actionable_blocker.get("unlock_fields") or [])
        ],
        "production_inference_next_after_actionable_blocker_next_action": _text(
            next_after_actionable_blocker.get("next_action")
        ),
        "production_inference_actionable_blocker_blocks_registry_promotion": bool(
            first_acceptance_blocker
            and not registry_promotion_ready
            and _text(first_acceptance_blocker.get("stage_id")) != "registry_guarded_promotion_acceptance"
        ),
        "production_inference_actionable_operator_completion_packet_ready": bool(
            operator_completion_packet.get("packet_ready") is True
        ),
        "production_inference_actionable_operator_completion_packet_artifact": (
            operator_completion_packet_artifact
        ),
        "production_inference_actionable_operator_completion_artifact_id": _text(
            operator_completion_packet.get("artifact_id")
        ),
        "production_inference_actionable_operator_completion_artifact_path": _text(
            operator_completion_packet.get("artifact_path")
        ),
        "production_inference_actionable_operator_completion_expected_queue_rows": _int(
            operator_completion_packet.get("expected_queue_rows")
        ),
        "production_inference_actionable_operator_completion_required_fields_or_columns": [
            str(item) for item in _list(operator_completion_packet.get("required_fields_or_columns"))
        ],
        "production_inference_actionable_operator_completion_diagnostic_commands": [
            str(item) for item in _list(operator_completion_packet.get("diagnostic_commands"))
        ],
        "production_inference_actionable_operator_completion_diagnostic_command_count": _int(
            operator_completion_packet.get("diagnostic_command_count")
        ),
        "production_inference_actionable_operator_completion_diagnostic_required_fields": [
            str(item) for item in _list(operator_completion_packet.get("diagnostic_required_fields"))
        ],
        "production_inference_actionable_operator_completion_diagnostic_required_field_count": _int(
            operator_completion_packet.get("diagnostic_required_field_count")
        ),
        "production_inference_actionable_operator_completion_diagnostic_completion_rule": _text(
            operator_completion_packet.get("diagnostic_completion_rule")
        ),
        "production_inference_actionable_operator_completion_diagnostic_return_artifacts": [
            str(item) for item in _list(operator_completion_packet.get("diagnostic_return_artifacts"))
        ],
        "production_inference_actionable_operator_completion_torch_visibility_probe_command": _text(
            operator_completion_packet.get("torch_visibility_probe_command")
        ),
        "production_inference_actionable_operator_completion_failed_check_ids": [
            str(item) for item in _list(operator_completion_packet.get("failed_check_ids"))
        ],
        "production_inference_actionable_operator_completion_template_payload_json": _text(
            operator_completion_packet.get("template_payload_json")
        ),
        "production_inference_actionable_operator_completion_actual_summary_return_path": _text(
            operator_completion_packet.get("actual_summary_return_path")
        ),
        "production_inference_actionable_operator_completion_actual_manifest_return_path": _text(
            operator_completion_packet.get("actual_manifest_return_path")
        ),
        "production_inference_actionable_operator_completion_validation_command": _text(
            operator_completion_packet.get("validation_command")
        ),
        "production_inference_actionable_operator_completion_full_regeneration_command": _text(
            operator_completion_packet.get("full_regeneration_command")
        ),
        "production_inference_actionable_operator_completion_completion_rule": _text(
            operator_completion_packet.get("completion_rule")
        ),
        "production_inference_actionable_operator_completion_backend_provenance_completion_rule": _text(
            operator_completion_packet.get("backend_provenance_completion_rule")
        ),
        "production_inference_actionable_operator_completion_next_action": _text(
            operator_completion_packet.get("next_action")
        ),
        "production_inference_actionable_operator_completion_packet": operator_completion_packet,
        "production_inference_worker_runtime_receipt_contract_ready": _bool(
            worker_runtime_receipt_contract.get("contract_ready")
        ),
        "production_inference_worker_runtime_receipt_contract": worker_runtime_receipt_contract,
        "production_inference_worker_runtime_receipt_required_fields_or_columns": [
            str(item)
            for item in _list(
                operator_completion_packet.get("worker_runtime_receipt_required_fields_or_columns")
                or worker_runtime_receipt_contract.get("required_fields_or_columns")
            )
        ],
        "production_inference_worker_runtime_receipt_required_field_count": _int(
            operator_completion_packet.get("worker_runtime_receipt_required_field_count")
            or worker_runtime_receipt_contract.get("required_field_count")
        ),
        "production_inference_worker_runtime_receipt_completion_rule": _text(
            operator_completion_packet.get("worker_runtime_receipt_completion_rule")
            or worker_runtime_receipt_contract.get("completion_rule")
        ),
        "production_inference_worker_runtime_receipt_post_environment_next_stage_id": _text(
            operator_completion_packet.get("post_environment_next_stage_id")
            or worker_runtime_receipt_contract.get("post_environment_next_stage_id")
        ),
        "production_inference_worker_runtime_receipt_post_environment_next_artifact": _text(
            operator_completion_packet.get("post_environment_next_artifact")
            or worker_runtime_receipt_contract.get("post_environment_next_artifact")
        ),
        "production_inference_worker_runtime_receipt_post_environment_validation_command": _text(
            operator_completion_packet.get("post_environment_validation_command")
            or worker_runtime_receipt_contract.get("post_environment_validation_command")
        ),
        "production_inference_worker_runtime_receipt_full_regeneration_command": _text(
            operator_completion_packet.get("full_regeneration_command")
            or worker_runtime_receipt_contract.get("full_regeneration_command")
        ),
        "production_inference_worker_runtime_receipt_guardrails": [
            str(item) for item in _list(worker_runtime_receipt_contract.get("guardrails"))
        ],
        "force_gpu_worker_post_run_validation_chain_current": _bool(
            receipt.get("handoff_post_run_validation_chain_current")
        ),
        "force_gpu_worker_post_run_validation_command_count": _int(
            receipt.get("handoff_post_run_validation_command_count")
        ),
        "force_gpu_worker_post_run_validation_commands": post_run_validation_commands,
        "checkpoint_closure_blockers": checkpoint_closure_blockers,
        "checkpoint_missing_output_fields": _list(registry.get("checkpoint_missing_output_fields")),
        "checkpoint_missing_adapter_output_policy_fields": _list(
            registry.get("checkpoint_missing_adapter_output_policy_fields")
        ),
        "selected_sidecar_ready": selected_sidecar_ready,
        "selected_sidecar_status": str(registry.get("selected_sidecar_status") or ""),
        "selected_sidecar_blockers": _list(registry.get("selected_sidecar_blockers")),
        "selected_sidecar_missing_output_fields": _list(registry.get("selected_sidecar_missing_output_fields")),
        "selected_sidecar_training_contract_ready": selected_sidecar_training_ready,
        "selected_sidecar_training_contract_missing_label_fields": _list(
            registry.get("selected_sidecar_training_contract_missing_label_fields")
        ),
        "selected_sidecar_force_receipt_ready": selected_sidecar_force_receipt_ready,
        "selected_sidecar_force_receipt_operator_verified": _bool(
            registry.get("selected_sidecar_force_receipt_operator_verified")
        ),
        "selected_sidecar_force_receipt_operator_verified_true_count": _int(
            registry.get("selected_sidecar_force_receipt_operator_verified_true_count")
        ),
        "selected_sidecar_force_receipt_expected_queue_rows": _int(
            registry.get("selected_sidecar_force_receipt_expected_queue_rows")
        ),
        "gpu_receipt_blockers": _list(receipt.get("blockers")),
        "gpu_receipt_summary_manifest_bound": _bool(receipt.get("full_regeneration_summary_manifest_bound")),
        "gpu_receipt_summary_out_manifest_csv_bound": _bool(
            receipt.get("full_regeneration_summary_out_manifest_csv_bound")
        ),
        "gpu_receipt_summary_out_summary_json_bound": _bool(
            receipt.get("full_regeneration_summary_out_summary_json_bound")
        ),
        "gpu_receipt_summary_manifest_row_counts_consistent": _bool(
            receipt.get("full_regeneration_summary_manifest_row_counts_consistent")
        ),
        "gpu_receipt_summary_manifest_csv": _text(receipt.get("summary_manifest_csv")),
        "gpu_receipt_summary_out_manifest_csv": _text(receipt.get("summary_out_manifest_csv")),
        "gpu_receipt_summary_out_summary_json": _text(receipt.get("summary_out_summary_json")),
        "gpu_receipt_production_gpu_backend_provenance_ready": _bool(
            receipt.get("production_gpu_backend_provenance_ready")
        ),
        "gpu_receipt_production_gpu_backend_rows": _int(receipt.get("production_gpu_backend_rows")),
        "gpu_receipt_production_gpu_backend_non_production_rows": _int(
            receipt.get("production_gpu_backend_non_production_rows")
        ),
        "gpu_receipt_production_gpu_backend_prod_mode": _bool(
            receipt.get("production_gpu_backend_prod_mode")
        ),
        "gpu_receipt_production_gpu_backend_require_rust_hip": _bool(
            receipt.get("production_gpu_backend_require_rust_hip")
        ),
        "gpu_receipt_expected_queue_rows": _int(receipt.get("expected_queue_rows")),
        "gpu_receipt_expected_npz_count": _int(receipt.get("expected_npz_count")),
        "gpu_receipt_queue_id_count": _int(receipt.get("queue_id_count")),
        "gpu_receipt_queue_fingerprint_count": _int(receipt.get("queue_fingerprint_count")),
        "gpu_receipt_manifest_ok_row_count": _int(receipt.get("manifest_ok_row_count")),
        "gpu_receipt_manifest_row_count": _int(receipt.get("manifest_row_count")),
        "gpu_receipt_manifest_identity_row_count": _int(receipt.get("manifest_identity_row_count")),
        "gpu_receipt_manifest_matched_queue_id_count": _int(receipt.get("manifest_matched_queue_id_count")),
        "gpu_receipt_manifest_matched_expected_npz_count": _int(
            receipt.get("manifest_matched_expected_npz_count")
        ),
        "gpu_receipt_manifest_matched_queue_fingerprint_count": _int(
            receipt.get("manifest_matched_queue_fingerprint_count")
        ),
        "gpu_receipt_manifest_operator_verified": _bool(receipt.get("full_regeneration_manifest_operator_verified")),
        "gpu_receipt_operator_verified_true_count": _int(receipt.get("manifest_operator_verified_true_count")),
        "gpu_receipt_identity_coverage_ready": _bool(receipt.get("queue_manifest_identity_coverage_ready")),
        "training_data_failed_check_ids": _list(training.get("failed_check_ids")),
        "training_data_missing_output_labels": _list(training.get("dataset_missing_output_labels")),
        "registry_artifact_path": registry_artifact_path,
        "checkpoint_work_order_artifact_path": checkpoint_work_order_artifact_path,
        "training_data_artifact_path": training_data_artifact_path,
        "force_gpu_worker_return_receipt_artifact_path": force_gpu_worker_return_receipt_artifact_path,
        "next_required_step": str(
            (
                "Expose a supported AMD ROCm/HIP device on this node or move the full regeneration command "
                "to a ready GPU worker."
            )
            if not production_gpu_execution_environment_ready
            else (
                work_order.get("next_required_step")
                or registry.get("next_required_step")
                or "Close failed checkpoint readiness checks before production promotion."
            )
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": rows,
        "blockers": [row for row in rows if row["status"] != "pass"],
        "production_inference_acceptance_matrix": acceptance_rows,
    }
