#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from tools.build_residual_production_checkpoint_preflight import REQUIRED_OUTPUT_FIELDS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = "models/residual_production_score_model_current.pt"
DEFAULT_SCORE_MODEL_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_SUPERVISED_DATASET_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_ASSIST_GATE_JSON = "runs/residual_assist_promotion_gate_current.json"
DEFAULT_PUBLIC_ASSIST_GATE_JSON = "runs/public_benchmark_residual_assist_comparison_gate_current.json"
DEFAULT_TRAINING_DATA_CONTRACT_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_FORCE_GPU_RETURN_RECEIPT_JSON = "runs/residual_force_gpu_worker_return_receipt_current.json"
DEFAULT_SIDE_CAR = "models/residual_production_score_model_current.pt.json"
DEFAULT_OUT_JSON = "runs/residual_production_checkpoint_sidecar_current.json"
DEFAULT_OUT_MD = "runs/residual_production_checkpoint_sidecar_current.md"
REQUIRED_FORCE_RECEIPT_OK_STATUS_VALUES = ("ok", "ok_full_regeneration", "ok_npz_bundle", "ok_regenerated_npz")

CLAIM_BOUNDARY = (
    "Residual production checkpoint sidecar builder only; validates the local score candidate, supervised dataset, "
    "assist gates, and fail-closed adapter policy before writing sidecar metadata. It does not run docking, change "
    "rankings, promote production mode, upload, submit, email, delete, or mutate external state outside the declared "
    "sidecar/output artifact paths."
)

ADAPTER_OUTPUT_POLICY = {
    "delta_score": "learned_score_residual_head",
    "corrected_score": "raw_score_plus_learned_delta_score",
    "delta_energy": "validated_energy_head_or_fail_closed_guard",
    "delta_force": "validated_force_head_or_fail_closed_guard",
    "uncertainty": "calibrated_uncertainty_head",
    "abstention_reason": "policy_output_reason_for_high_uncertainty_missing_physics_or_contract_violation",
    "stage2_route_decision": "policy_output_route_for_frozen_expensive_path_or_guarded_accept",
}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _checkpoint_payload(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = torch.load(path, map_location="cpu")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_residual_production_checkpoint_sidecar(
    *,
    checkpoint_path: str = DEFAULT_CHECKPOINT,
    score_model_packet: dict[str, Any],
    supervised_dataset_packet: dict[str, Any],
    assist_gate_packet: dict[str, Any],
    public_assist_gate_packet: dict[str, Any],
    training_data_contract_packet: dict[str, Any] | None = None,
    force_gpu_return_receipt_packet: dict[str, Any] | None = None,
    score_model_path: str = DEFAULT_SCORE_MODEL_JSON,
    supervised_dataset_path: str = DEFAULT_SUPERVISED_DATASET_JSON,
    assist_gate_path: str = DEFAULT_ASSIST_GATE_JSON,
    public_assist_gate_path: str = DEFAULT_PUBLIC_ASSIST_GATE_JSON,
    training_data_contract_path: str = DEFAULT_TRAINING_DATA_CONTRACT_JSON,
    force_gpu_return_receipt_path: str = DEFAULT_FORCE_GPU_RETURN_RECEIPT_JSON,
    sidecar_path: str = DEFAULT_SIDE_CAR,
    min_val_rows: int = 100,
    min_pr_auc: float = 0.50,
    write_sidecar: bool = True,
) -> dict[str, Any]:
    checkpoint = _resolve(checkpoint_path)
    score = _summary(score_model_packet)
    dataset = _summary(supervised_dataset_packet)
    assist = _summary(assist_gate_packet)
    public_assist = _summary(public_assist_gate_packet)
    training_contract = _summary(training_data_contract_packet or {})
    force_receipt = _summary(force_gpu_return_receipt_packet or {})
    payload = _checkpoint_payload(checkpoint)
    payload_outputs = {str(item) for item in payload.get("output_fields") or []}
    required_learned_outputs = {"delta_score", "corrected_score", "delta_energy", "delta_force", "uncertainty"}
    required_policy_outputs = {"abstention_reason", "stage2_route_decision"}
    missing_learned_outputs = sorted(required_learned_outputs - payload_outputs)
    missing_policy_outputs = sorted(required_policy_outputs - payload_outputs)
    missing_production_output_fields = [str(item) for item in score.get("missing_production_output_fields") or []]
    training_missing_label_fields = [
        str(item) for item in training_contract.get("missing_energy_force_label_fields") or []
    ]
    training_missing_output_fields = [
        str(item) for item in training_contract.get("production_missing_output_fields") or []
    ]
    best = score.get("best") if isinstance(score.get("best"), dict) else {}
    force_manifest_allowed_ok_status_values = [
        str(item) for item in force_receipt.get("manifest_allowed_ok_status_values") or []
    ]
    force_manifest_status_vocab_ready = all(
        value in force_manifest_allowed_ok_status_values for value in REQUIRED_FORCE_RECEIPT_OK_STATUS_VALUES
    )
    force_manifest_status_counts_ready = (
        _int(force_receipt.get("manifest_status_placeholder_count")) == 0
        and _int(force_receipt.get("manifest_status_invalid_count")) == 0
    )
    force_expected_queue_rows = _int(force_receipt.get("expected_queue_rows"))
    force_manifest_ok_rows = _int(force_receipt.get("manifest_ok_row_count"))
    force_operator_verified_true_count = _int(force_receipt.get("manifest_operator_verified_true_count"))
    force_manifest_row_count_ready = (
        force_expected_queue_rows > 0
        and force_manifest_ok_rows >= force_expected_queue_rows
        and force_operator_verified_true_count >= force_expected_queue_rows
    )

    checks = {
        "checkpoint_exists": checkpoint.exists(),
        "payload_has_score_outputs": not missing_learned_outputs,
        "payload_has_policy_outputs": not missing_policy_outputs,
        "score_model_trained": str(score.get("status") or "") == "residual_production_score_model_trained",
        "score_model_production_ready": score.get("production_checkpoint_ready") is True,
        "production_output_heads_complete": not missing_production_output_fields,
        "validation_rows_ready": _int(score.get("val_rows")) >= min_val_rows,
        "pr_auc_ready": _float(best.get("pr_auc")) >= min_pr_auc,
        "supervised_dataset_ready": dataset.get("production_supervised_dataset_ready") is True,
        "assist_gate_ready": assist.get("assist_promotion_allowed") is True,
        "public_assist_gate_ready": public_assist.get("assist_comparison_gate_ready") is True,
        "production_training_data_contract_ready": training_contract.get("production_training_data_ready") is True
        and str(training_contract.get("status") or "").endswith("_ready"),
        "force_gpu_return_receipt_ready": force_receipt.get("gpu_worker_return_receipt_ready") is True
        and force_receipt.get("queue_manifest_identity_coverage_ready") is True
        and force_receipt.get("full_regeneration_manifest_operator_verified") is True
        and force_manifest_status_vocab_ready
        and force_manifest_status_counts_ready
        and force_manifest_row_count_ready
        and str(force_receipt.get("status") or "").endswith("_ready"),
    }
    ready = all(checks.values())
    checksum = _sha256(checkpoint) if checkpoint.exists() else ""
    artifact_status = {
        "score_model": "ready" if checks["score_model_trained"] and checks["score_model_production_ready"] else "blocked",
        "supervised_dataset": "ready" if checks["supervised_dataset_ready"] else "blocked",
        "assist_gate": "ready" if checks["assist_gate_ready"] else "blocked",
        "public_assist_gate": "ready" if checks["public_assist_gate_ready"] else "blocked",
        "production_training_data_contract": "ready" if checks["production_training_data_contract_ready"] else "blocked",
        "force_gpu_worker_return_receipt": "ready" if checks["force_gpu_return_receipt_ready"] else "blocked",
    }
    sidecar = {
        "component_id": "topograph_corrector",
        "model_family": "protein_ligand_residual_v1",
        "checkpoint_sha256": checksum,
        "required_output_fields": list(REQUIRED_OUTPUT_FIELDS),
        "benchmark_gate_artifacts": [
            {
                "artifact": score_model_path,
                "status": artifact_status["score_model"],
                "score_model_trained": checks["score_model_trained"],
                "production_checkpoint_ready": checks["score_model_production_ready"],
            },
            {
                "artifact": supervised_dataset_path,
                "status": artifact_status["supervised_dataset"],
                "production_supervised_dataset_ready": checks["supervised_dataset_ready"],
            },
            {
                "artifact": assist_gate_path,
                "status": artifact_status["assist_gate"],
                "assist_promotion_allowed": checks["assist_gate_ready"],
            },
            {
                "artifact": public_assist_gate_path,
                "status": artifact_status["public_assist_gate"],
                "assist_comparison_gate_ready": checks["public_assist_gate_ready"],
            },
        ],
        "uncertainty_calibrated": True,
        "physics_guard_bound": True,
        "promotion_mode": "production_guarded",
        "adapter_output_policy": ADAPTER_OUTPUT_POLICY,
        "physics_guard_policy": "fail_closed_without_validated_energy_force_head_and_physics_guard_binding",
        "abstention_policy": "abstain_on_high_uncertainty_missing_physics_support_output_contract_violation_or_ood_scope",
        "production_training_data_contract_artifact": {
            "artifact": training_data_contract_path,
            "required_ready_key": "production_training_data_ready",
            "observed_status": str(training_contract.get("status") or ""),
            "observed_ready": training_contract.get("production_training_data_ready") is True,
            "observed_missing_label_fields": training_missing_label_fields,
            "observed_missing_output_fields": training_missing_output_fields,
            "observed_primary_blocker": str(training_contract.get("primary_blocker") or ""),
            "status": artifact_status["production_training_data_contract"],
        },
        "force_gpu_worker_return_receipt_artifact": {
            "artifact": force_gpu_return_receipt_path,
            "required_ready_key": "gpu_worker_return_receipt_ready",
            "required_provenance_key": "queue_manifest_identity_coverage_ready",
            "observed_status": str(force_receipt.get("status") or ""),
            "observed_ready": force_receipt.get("gpu_worker_return_receipt_ready") is True,
            "observed_provenance_ready": force_receipt.get("queue_manifest_identity_coverage_ready") is True,
            "observed_operator_verified": force_receipt.get("full_regeneration_manifest_operator_verified") is True,
            "observed_operator_verified_true_count": force_operator_verified_true_count,
            "observed_expected_queue_rows": force_expected_queue_rows,
            "observed_manifest_ok_row_count": force_manifest_ok_rows,
            "observed_manifest_status_placeholder_count": _int(
                force_receipt.get("manifest_status_placeholder_count")
            ),
            "observed_manifest_status_invalid_count": _int(force_receipt.get("manifest_status_invalid_count")),
            "observed_manifest_allowed_ok_status_values": force_manifest_allowed_ok_status_values,
            "required_manifest_allowed_ok_status_values": list(REQUIRED_FORCE_RECEIPT_OK_STATUS_VALUES),
            "status": artifact_status["force_gpu_worker_return_receipt"],
        },
    }
    sidecar_written = False
    if ready and write_sidecar:
        out = _resolve(sidecar_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        sidecar_written = True

    blockers = [name for name, ok in checks.items() if not ok]
    summary = {
        "packet_type": "residual_production_checkpoint_sidecar",
        "status": "residual_production_checkpoint_sidecar_ready" if ready else "blocked_residual_production_checkpoint_sidecar",
        "sidecar_ready": ready,
        "sidecar_written": sidecar_written,
        "checkpoint_path": checkpoint_path,
        "sidecar_path": sidecar_path,
        "checkpoint_sha256": checksum,
        "checks": checks,
        "blockers": blockers,
        "payload_output_fields": sorted(payload_outputs),
        "missing_learned_output_fields": missing_learned_outputs,
        "missing_policy_output_fields": missing_policy_outputs,
        "missing_production_output_fields": missing_production_output_fields,
        "training_contract_missing_label_fields": training_missing_label_fields,
        "training_contract_missing_output_fields": training_missing_output_fields,
        "training_contract_primary_blocker": str(training_contract.get("primary_blocker") or ""),
        "policy_output_adapter_ready": not missing_policy_outputs and score.get("policy_output_adapter_ready") is True,
        "production_training_data_contract_ready": checks["production_training_data_contract_ready"],
        "force_gpu_return_receipt_ready": checks["force_gpu_return_receipt_ready"],
        "force_gpu_return_receipt_operator_verified": force_receipt.get("full_regeneration_manifest_operator_verified") is True,
        "force_gpu_return_receipt_operator_verified_true_count": force_operator_verified_true_count,
        "force_gpu_return_receipt_expected_queue_rows": force_expected_queue_rows,
        "force_gpu_return_receipt_manifest_ok_row_count": force_manifest_ok_rows,
        "force_gpu_return_receipt_manifest_status_placeholder_count": _int(
            force_receipt.get("manifest_status_placeholder_count")
        ),
        "force_gpu_return_receipt_manifest_status_invalid_count": _int(
            force_receipt.get("manifest_status_invalid_count")
        ),
        "force_gpu_return_receipt_manifest_allowed_ok_status_values": force_manifest_allowed_ok_status_values,
        "force_gpu_return_receipt_manifest_status_vocab_ready": force_manifest_status_vocab_ready,
        "force_gpu_return_receipt_manifest_row_count_ready": force_manifest_row_count_ready,
        "production_training_data_contract_artifact": training_data_contract_path,
        "force_gpu_worker_return_receipt_artifact": force_gpu_return_receipt_path,
        "required_output_fields": list(REQUIRED_OUTPUT_FIELDS),
        "adapter_output_policy": ADAPTER_OUTPUT_POLICY,
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rerun residual production checkpoint preflight and residual model registry."
            if ready
            else f"Repair sidecar blockers: {','.join(blockers)}"
        ),
    }
    return {"summary": summary, "sidecar": sidecar}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Production Checkpoint Sidecar",
        "",
        f"- status: `{s['status']}`",
        f"- sidecar_ready: `{s['sidecar_ready']}`",
        f"- sidecar_written: `{s['sidecar_written']}`",
        f"- checkpoint_path: `{s['checkpoint_path']}`",
        f"- sidecar_path: `{s['sidecar_path']}`",
        f"- blockers: `{','.join(s['blockers'])}`",
        f"- payload_output_fields: `{','.join(s['payload_output_fields'])}`",
        f"- training_contract_missing_label_fields: `{','.join(s['training_contract_missing_label_fields'])}`",
        f"- training_contract_missing_output_fields: `{','.join(s['training_contract_missing_output_fields'])}`",
        f"- force_gpu_return_receipt_operator_verified: `{s['force_gpu_return_receipt_operator_verified']}`",
        f"- force_gpu_return_receipt_operator_verified_true_count: `{s['force_gpu_return_receipt_operator_verified_true_count']}`",
        f"- force_gpu_return_receipt_manifest_ok_row_count: `{s['force_gpu_return_receipt_manifest_ok_row_count']}`",
        f"- force_gpu_return_receipt_manifest_status_placeholder_count: `{s['force_gpu_return_receipt_manifest_status_placeholder_count']}`",
        f"- force_gpu_return_receipt_manifest_status_invalid_count: `{s['force_gpu_return_receipt_manifest_status_invalid_count']}`",
        f"- force_gpu_return_receipt_manifest_status_vocab_ready: `{s['force_gpu_return_receipt_manifest_status_vocab_ready']}`",
        f"- force_gpu_return_receipt_manifest_row_count_ready: `{s['force_gpu_return_receipt_manifest_row_count_ready']}`",
        "",
        "## Adapter Policy",
        "",
        "| output | policy |",
        "| --- | --- |",
    ]
    for key, value in s["adapter_output_policy"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build guarded production sidecar metadata for the residual score checkpoint.")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--score-model-json", default=DEFAULT_SCORE_MODEL_JSON)
    parser.add_argument("--supervised-dataset-json", default=DEFAULT_SUPERVISED_DATASET_JSON)
    parser.add_argument("--assist-gate-json", default=DEFAULT_ASSIST_GATE_JSON)
    parser.add_argument("--public-assist-gate-json", default=DEFAULT_PUBLIC_ASSIST_GATE_JSON)
    parser.add_argument("--training-data-contract-json", default=DEFAULT_TRAINING_DATA_CONTRACT_JSON)
    parser.add_argument("--force-gpu-return-receipt-json", default=DEFAULT_FORCE_GPU_RETURN_RECEIPT_JSON)
    parser.add_argument("--sidecar-path", default=DEFAULT_SIDE_CAR)
    parser.add_argument("--min-val-rows", type=int, default=100)
    parser.add_argument("--min-pr-auc", type=float, default=0.50)
    parser.add_argument("--write-sidecar", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_production_checkpoint_sidecar(
        checkpoint_path=args.checkpoint,
        score_model_packet=_read_json_if_present(args.score_model_json),
        supervised_dataset_packet=_read_json_if_present(args.supervised_dataset_json),
        assist_gate_packet=_read_json_if_present(args.assist_gate_json),
        public_assist_gate_packet=_read_json_if_present(args.public_assist_gate_json),
        training_data_contract_packet=_read_json_if_present(args.training_data_contract_json),
        force_gpu_return_receipt_packet=_read_json_if_present(args.force_gpu_return_receipt_json),
        score_model_path=args.score_model_json,
        supervised_dataset_path=args.supervised_dataset_json,
        assist_gate_path=args.assist_gate_json,
        public_assist_gate_path=args.public_assist_gate_json,
        training_data_contract_path=args.training_data_contract_json,
        force_gpu_return_receipt_path=args.force_gpu_return_receipt_json,
        sidecar_path=args.sidecar_path,
        min_val_rows=args.min_val_rows,
        min_pr_auc=args.min_pr_auc,
        write_sidecar=args.write_sidecar,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
