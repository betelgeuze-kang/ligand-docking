#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_HEAD_GAP_JSON = "runs/residual_production_output_head_gap_contract_current.json"
DEFAULT_ENERGY_FORCE_WORK_ORDER_JSON = "runs/residual_energy_force_label_evidence_work_order_current.json"
DEFAULT_GPU_RETURN_INTAKE_JSON = "runs/product_production_ai_gpu_return_intake_current.json"
DEFAULT_FORCE_GPU_HANDOFF_JSON = "runs/residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_TRAINING_DATA_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_SCORE_MODEL_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_SIDECAR_JSON = "runs/residual_production_checkpoint_sidecar_current.json"
DEFAULT_PREFLIGHT_JSON = "runs/residual_production_checkpoint_preflight_current.json"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_OUT_JSON = "runs/residual_delta_force_closure_acceptance_packet_current.json"
DEFAULT_OUT_CSV = "runs/residual_delta_force_closure_acceptance_packet_current.csv"
DEFAULT_OUT_MD = "runs/residual_delta_force_closure_acceptance_packet_current.md"

CLAIM_BOUNDARY = (
    "Residual delta_force closure acceptance packet only; it cross-checks existing output-head, GPU-return, "
    "force-label, training-data, checkpoint, and registry evidence. It does not run GPU jobs, derive forces, train "
    "models, create checkpoints, promote production mode, widen product claims, upload, submit, email, delete, or "
    "mutate external state."
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


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = _text(value)
    return [part.strip() for part in text.split(";") if part.strip()] if text else []


def _stage_row(
    *,
    stage_id: str,
    artifact: str,
    ready_key: str,
    current_value: bool,
    required_value: bool,
    release_effect: str,
    validation_command: str,
    next_action: str,
) -> dict[str, Any]:
    passed = current_value is required_value
    return {
        "stage_id": stage_id,
        "status": "pass" if passed else "fail",
        "artifact": artifact,
        "ready_key": ready_key,
        "current_value": current_value,
        "required_value": required_value,
        "release_effect": release_effect,
        "validation_command": validation_command,
        "next_action": next_action if not passed else "",
        "release_blocker": not passed,
        "execution_enabled": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def build_residual_delta_force_closure_acceptance_packet(
    *,
    output_head_gap_packet: dict[str, Any],
    energy_force_work_order_packet: dict[str, Any],
    gpu_return_intake_packet: dict[str, Any] | None = None,
    force_gpu_handoff_packet: dict[str, Any] | None = None,
    training_data_packet: dict[str, Any] | None = None,
    score_model_packet: dict[str, Any] | None = None,
    sidecar_packet: dict[str, Any] | None = None,
    preflight_packet: dict[str, Any] | None = None,
    registry_packet: dict[str, Any] | None = None,
    output_head_gap_path: str = DEFAULT_OUTPUT_HEAD_GAP_JSON,
    energy_force_work_order_path: str = DEFAULT_ENERGY_FORCE_WORK_ORDER_JSON,
    gpu_return_intake_path: str = DEFAULT_GPU_RETURN_INTAKE_JSON,
    force_gpu_handoff_path: str = DEFAULT_FORCE_GPU_HANDOFF_JSON,
    training_data_path: str = DEFAULT_TRAINING_DATA_JSON,
    score_model_path: str = DEFAULT_SCORE_MODEL_JSON,
    sidecar_path: str = DEFAULT_SIDECAR_JSON,
    preflight_path: str = DEFAULT_PREFLIGHT_JSON,
    registry_path: str = DEFAULT_REGISTRY_JSON,
) -> dict[str, Any]:
    output_head = _summary(output_head_gap_packet)
    work_order = _summary(energy_force_work_order_packet)
    gpu_return = _summary(gpu_return_intake_packet or {})
    handoff = _summary(force_gpu_handoff_packet or {})
    training = _summary(training_data_packet or {})
    score_model = _summary(score_model_packet or {})
    sidecar = _summary(sidecar_packet or {})
    preflight = _summary(preflight_packet or {})
    registry = _summary(registry_packet or {})

    first_blocked_output_field = _text(output_head.get("first_blocked_output_field"))
    blocked_output_fields = _list(output_head.get("blocked_output_fields"))
    output_gap_ready = _bool(output_head.get("output_head_gap_contract_ready"))
    output_heads_complete = _bool(output_head.get("production_output_heads_complete"))
    delta_force_is_current_blocker = first_blocked_output_field == "delta_force" or "delta_force" in blocked_output_fields
    handoff_ready = _bool(handoff.get("gpu_worker_handoff_ready"))
    return_bundle_ready = _bool(gpu_return.get("operator_return_bundle_contract_ready"))
    packet_ready = output_gap_ready and delta_force_is_current_blocker and handoff_ready and return_bundle_ready

    post_run_validation_commands = _list(handoff.get("post_run_validation_commands")) or _list(
        gpu_return.get("post_run_validation_commands")
    )
    post_return_validation_command = _text(handoff.get("operator_transfer_post_return_validation_command")) or _text(
        gpu_return.get("post_return_validation_command")
    )
    if not post_return_validation_command and post_run_validation_commands:
        post_return_validation_command = " && ".join(post_run_validation_commands)

    stage_specs = [
        (
            "gpu_worker_return_receipt",
            DEFAULT_GPU_RETURN_INTAKE_JSON,
            "gpu_worker_return_receipt_ready",
            _bool(work_order.get("force_gpu_worker_return_receipt_ready")),
            "returned GPU summary/manifest/NPZ bundle passes the identity and backend-provenance receipt",
            "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
            _text(work_order.get("force_gpu_worker_return_receipt_next_required_step"))
            or _text(gpu_return.get("operator_return_next_artifact_completion_packet", {}).get("next_action"))
            or "Return the completed GPU summary JSON, manifest CSV, and regenerated NPZ bundles.",
        ),
        (
            "force_derivation_validation",
            "runs/residual_force_derivation_validation_current.json",
            "delta_force_derivation_validation_ready",
            _bool(work_order.get("delta_force_derivation_validation_ready")),
            "regenerated NPZ bundles are accepted as delta_force derivation inputs",
            "python3 tools/build_residual_force_derivation_validation.py",
            _text(work_order.get("force_derivation_next_required_step"))
            or "Rerun force derivation validation after GPU-returned NPZ bundles are present.",
        ),
        (
            "energy_force_label_evidence",
            energy_force_work_order_path,
            "delta_force_label_evidence_ready",
            _bool(work_order.get("delta_force_label_evidence_ready")),
            "production supervised labels include delta_force evidence",
            "python3 tools/build_residual_energy_force_label_evidence_work_order.py",
            _text(work_order.get("next_required_step")) or "Rebuild energy/force label evidence after derivation validation.",
        ),
        (
            "production_training_data_contract",
            training_data_path,
            "production_training_data_ready",
            _bool(training.get("production_training_data_ready")),
            "production training-data contract no longer blocks residual checkpoint training",
            "python3 tools/build_residual_production_training_data_contract.py",
            _text(training.get("next_required_step")) or "Rebuild the production training-data contract.",
        ),
        (
            "production_score_model",
            score_model_path,
            "score_model_production_checkpoint_ready",
            _bool(score_model.get("score_model_production_checkpoint_ready")),
            "trained score model advertises all required production outputs including delta_force",
            "python3 tools/train_residual_production_score_model.py",
            _text(score_model.get("next_required_step")) or "Retrain the residual production score model.",
        ),
        (
            "production_checkpoint_sidecar",
            sidecar_path,
            "sidecar_ready",
            _bool(sidecar.get("sidecar_ready")),
            "checkpoint sidecar binds training contract, force receipt, adapter policy, uncertainty, and guard evidence",
            "python3 tools/build_residual_production_checkpoint_sidecar.py",
            _text(sidecar.get("next_required_step")) or "Rebuild the production checkpoint sidecar.",
        ),
        (
            "production_checkpoint_preflight",
            preflight_path,
            "checkpoint_preflight_ready",
            _bool(preflight.get("checkpoint_preflight_ready")),
            "checkpoint is ready for guarded production promotion",
            "python3 tools/build_residual_production_checkpoint_preflight.py",
            _text(preflight.get("next_required_step")) or "Rerun production checkpoint preflight.",
        ),
        (
            "residual_model_registry",
            registry_path,
            "production_promotion_allowed",
            _bool(registry.get("production_promotion_allowed")),
            "AI model can become the guarded production inference subject",
            "python3 tools/build_residual_model_registry.py",
            _text(registry.get("next_required_step")) or "Rebuild the residual model registry after checkpoint preflight.",
        ),
        (
            "production_output_heads_complete",
            output_head_gap_path,
            "production_output_heads_complete",
            output_heads_complete,
            "all required production output heads are complete and published upstream",
            "python3 tools/build_residual_production_output_head_gap_contract.py",
            _text(output_head.get("next_required_step")) or "Rebuild the output-head gap contract.",
        ),
    ]
    rows = [
        _stage_row(
            stage_id=stage_id,
            artifact=artifact,
            ready_key=ready_key,
            current_value=current_value,
            required_value=True,
            release_effect=release_effect,
            validation_command=validation_command,
            next_action=next_action,
        )
        for (
            stage_id,
            artifact,
            ready_key,
            current_value,
            release_effect,
            validation_command,
            next_action,
        ) in stage_specs
    ]
    failed_rows = [row for row in rows if row["status"] != "pass"]
    first_failed = failed_rows[0] if failed_rows else {}
    closure_ready = packet_ready and not failed_rows and output_heads_complete
    status = (
        "residual_delta_force_closure_acceptance_complete"
        if closure_ready
        else "blocked_residual_delta_force_closure_acceptance_packet"
    )
    return_packet = gpu_return.get("operator_return_next_artifact_completion_packet")
    return_packet = return_packet if isinstance(return_packet, dict) else {}
    summary = {
        "packet_type": "residual_delta_force_closure_acceptance_packet",
        "status": status,
        "packet_ready": packet_ready,
        "delta_force_closure_ready": closure_ready,
        "output_head_gap_contract_ready": output_gap_ready,
        "production_output_heads_complete": output_heads_complete,
        "first_blocked_output_field": first_blocked_output_field,
        "blocked_output_fields": blocked_output_fields,
        "ready_output_field_count": _int(output_head.get("ready_output_field_count")),
        "blocked_output_field_count": _int(output_head.get("blocked_output_field_count")),
        "delta_energy_label_evidence_ready": _bool(work_order.get("delta_energy_label_evidence_ready")),
        "delta_force_label_evidence_ready": _bool(work_order.get("delta_force_label_evidence_ready")),
        "delta_force_derivation_validation_ready": _bool(
            work_order.get("delta_force_derivation_validation_ready")
        ),
        "force_gpu_worker_handoff_ready": handoff_ready,
        "operator_return_bundle_contract_ready": return_bundle_ready,
        "operator_return_required_artifact_count": _int(gpu_return.get("operator_return_required_artifact_count")),
        "operator_return_required_artifacts": _list(gpu_return.get("operator_return_required_artifacts")),
        "operator_return_next_artifact_id": _text(gpu_return.get("operator_return_next_artifact_id")),
        "operator_return_next_artifact_path": _text(gpu_return.get("operator_return_next_artifact_path")),
        "operator_return_next_artifact_failed_check_ids": _list(
            gpu_return.get("operator_return_next_artifact_failed_check_ids")
        ),
        "return_summary_required_fields": _list(return_packet.get("required_fields_or_columns"))
        or _list(handoff.get("return_summary_required_fields")),
        "return_manifest_required_columns": _list(gpu_return.get("operator_return_manifest_required_columns"))
        or _list(handoff.get("return_manifest_required_identity_rule")),
        "post_return_validation_command": post_return_validation_command,
        "post_run_validation_commands": post_run_validation_commands,
        "closure_stage_count": len(rows),
        "closure_pass_stage_count": len(rows) - len(failed_rows),
        "closure_failed_stage_count": len(failed_rows),
        "closure_failed_stage_ids": [str(row["stage_id"]) for row in failed_rows],
        "next_stage_id": _text(first_failed.get("stage_id")),
        "next_stage_artifact": _text(first_failed.get("artifact")),
        "next_stage_ready_key": _text(first_failed.get("ready_key")),
        "next_stage_validation_command": _text(first_failed.get("validation_command")),
        "next_required_step": _text(first_failed.get("next_action"))
        or "delta_force closure acceptance is complete.",
        "source_artifacts": [
            output_head_gap_path,
            energy_force_work_order_path,
            gpu_return_intake_path,
            force_gpu_handoff_path,
            training_data_path,
            score_model_path,
            sidecar_path,
            preflight_path,
            registry_path,
        ],
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Delta Force Closure Acceptance Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_ready: `{s['packet_ready']}`",
        f"- delta_force_closure_ready: `{s['delta_force_closure_ready']}`",
        f"- first_blocked_output_field: `{s['first_blocked_output_field']}`",
        f"- ready_output_field_count: `{s['ready_output_field_count']}`",
        f"- blocked_output_field_count: `{s['blocked_output_field_count']}`",
        f"- delta_force_label_evidence_ready: `{s['delta_force_label_evidence_ready']}`",
        f"- operator_return_bundle_contract_ready: `{s['operator_return_bundle_contract_ready']}`",
        f"- closure_failed_stage_ids: `{';'.join(s['closure_failed_stage_ids'])}`",
        f"- next_stage_id: `{s['next_stage_id']}`",
        f"- next_stage_artifact: `{s['next_stage_artifact']}`",
        f"- next_stage_validation_command: `{s['next_stage_validation_command']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## Closure Stages",
        "",
        "| stage | status | artifact | ready key | validation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['status']}` | `{row['artifact']}` | "
            f"`{row['ready_key']}` | `{row['validation_command']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual delta_force closure acceptance packet.")
    parser.add_argument("--output-head-gap-json", default=DEFAULT_OUTPUT_HEAD_GAP_JSON)
    parser.add_argument("--energy-force-work-order-json", default=DEFAULT_ENERGY_FORCE_WORK_ORDER_JSON)
    parser.add_argument("--gpu-return-intake-json", default=DEFAULT_GPU_RETURN_INTAKE_JSON)
    parser.add_argument("--force-gpu-handoff-json", default=DEFAULT_FORCE_GPU_HANDOFF_JSON)
    parser.add_argument("--training-data-json", default=DEFAULT_TRAINING_DATA_JSON)
    parser.add_argument("--score-model-json", default=DEFAULT_SCORE_MODEL_JSON)
    parser.add_argument("--sidecar-json", default=DEFAULT_SIDECAR_JSON)
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_delta_force_closure_acceptance_packet(
        output_head_gap_packet=_read_json_if_present(args.output_head_gap_json),
        energy_force_work_order_packet=_read_json_if_present(args.energy_force_work_order_json),
        gpu_return_intake_packet=_read_json_if_present(args.gpu_return_intake_json),
        force_gpu_handoff_packet=_read_json_if_present(args.force_gpu_handoff_json),
        training_data_packet=_read_json_if_present(args.training_data_json),
        score_model_packet=_read_json_if_present(args.score_model_json),
        sidecar_packet=_read_json_if_present(args.sidecar_json),
        preflight_packet=_read_json_if_present(args.preflight_json),
        registry_packet=_read_json_if_present(args.registry_json),
        output_head_gap_path=args.output_head_gap_json,
        energy_force_work_order_path=args.energy_force_work_order_json,
        gpu_return_intake_path=args.gpu_return_intake_json,
        force_gpu_handoff_path=args.force_gpu_handoff_json,
        training_data_path=args.training_data_json,
        score_model_path=args.score_model_json,
        sidecar_path=args.sidecar_json,
        preflight_path=args.preflight_json,
        registry_path=args.registry_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
