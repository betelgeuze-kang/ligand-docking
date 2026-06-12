#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT_READINESS_JSON = "runs/product_production_ai_checkpoint_readiness_current.json"
DEFAULT_OUT_JSON = "runs/product_production_ai_promotion_workbench_current.json"
DEFAULT_OUT_CSV = "runs/product_production_ai_promotion_workbench_current.csv"
DEFAULT_OUT_MD = "runs/product_production_ai_promotion_workbench_current.md"

CLAIM_BOUNDARY = (
    "Product production AI promotion workbench only; it reads local checkpoint-readiness, GPU receipt, training-data, "
    "sidecar, preflight, registry, architecture, and goal audit artifacts to explain the guarded promotion path. It "
    "does not run inference, train models, generate trajectories, create sidecars, create checkpoints, promote "
    "production mode, run docking, upload, submit, email, delete, or mutate external state."
)

READY_KEY_ALIASES = {
    "checkpoint_preflight_ready": ("preflight_green",),
    "score_model_production_checkpoint_ready": ("production_checkpoint_ready",),
}


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _artifact_observed_value(packet: dict[str, Any], ready_key: str) -> tuple[Any, str]:
    summary = _summary(packet)
    if ready_key in summary:
        return summary.get(ready_key), ready_key
    if ready_key in packet:
        return packet.get(ready_key), ready_key
    for alias in READY_KEY_ALIASES.get(ready_key, ()):
        if alias in summary:
            return summary.get(alias), alias
        if alias in packet:
            return packet.get(alias), alias
    return None, ""


def _stage_next_action(stage_id: str, checkpoint: dict[str, Any], stage_summary: dict[str, Any]) -> str:
    if stage_id == "gpu_return_receipt":
        return (
            _text(checkpoint.get("force_gpu_worker_handoff_next_required_step"))
            or "Run the full GPU regeneration queue and return manifest, summary, operator verification, and identity coverage."
        )
    if stage_id == "force_derivation_validation":
        return "Rerun force derivation validation after the full GPU return receipt is present."
    if stage_id == "energy_force_label_evidence":
        return "Attach accepted delta_force derivation evidence to the production label work order."
    if stage_id == "production_training_data_contract":
        return (
            _text(stage_summary.get("next_required_step"))
            or "Rebuild the production training-data contract with all required residual output labels."
        )
    if stage_id == "production_score_model":
        return "Train or rebuild the production residual score model with the full output head contract."
    if stage_id == "production_checkpoint_sidecar":
        return (
            _text(stage_summary.get("next_required_step"))
            or "Build a checkpoint sidecar that binds score outputs, training contract, GPU receipt, and guard evidence."
        )
    if stage_id == "production_checkpoint_preflight":
        return (
            _text(stage_summary.get("next_required_step"))
            or "Rerun checkpoint preflight after sidecar metadata and benchmark gates are ready."
        )
    if stage_id == "residual_model_registry":
        return "Rebuild the residual model registry after a preflight-ready checkpoint is available."
    if stage_id == "product_ai_architecture_gap_closure":
        return "Rebuild AI architecture gap closure after production checkpoint and scope blockers are closed."
    if stage_id == "product_goal_completion_audit":
        return "Rerun the product goal completion audit after all product AI and scope gates pass."
    return "Close the blocked artifact and rerun the promotion workbench."


def build_product_production_ai_promotion_workbench(
    *,
    checkpoint_readiness_packet: dict[str, Any],
    checkpoint_readiness_artifact_path: str = DEFAULT_CHECKPOINT_READINESS_JSON,
) -> dict[str, Any]:
    checkpoint = _summary(checkpoint_readiness_packet)
    ladder = _list(checkpoint.get("force_gpu_worker_post_return_promotion_ladder"))
    rows: list[dict[str, Any]] = []
    for index, stage in enumerate(ladder, start=1):
        if not isinstance(stage, dict):
            continue
        stage_id = _text(stage.get("stage_id"))
        artifact = _text(stage.get("artifact"))
        ready_key = _text(stage.get("ready_key"))
        required_value = stage.get("required_value")
        artifact_packet = _read_json(artifact) if artifact else {}
        artifact_summary = _summary(artifact_packet)
        observed_value, observed_ready_key = _artifact_observed_value(artifact_packet, ready_key)
        artifact_present = bool(artifact and _resolve(artifact).is_file() and artifact_packet)
        status = "ready" if artifact_present and observed_value == required_value else "blocked"
        row = {
            "promotion_order": index,
            "stage_id": stage_id,
            "status": status,
            "artifact": artifact,
            "artifact_present": artifact_present,
            "artifact_status": artifact_summary.get("status", ""),
            "ready_key": ready_key,
            "observed_ready_key": observed_ready_key,
            "ready_key_alias_used": bool(observed_ready_key and observed_ready_key != ready_key),
            "required_value": required_value,
            "observed_value": observed_value,
            "release_effect": _text(stage.get("release_effect")),
            "next_action": "" if status == "ready" else _stage_next_action(stage_id, checkpoint, artifact_summary),
            "release_blocker": status != "ready",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_promoted": False,
            "external_state_mutated": False,
        }
        rows.append(row)

    blocked_rows = [row for row in rows if row["status"] != "ready"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    alias_used_rows = [row for row in rows if row.get("ready_key_alias_used") is True]
    production_ai_promotion_ready = bool(rows) and not blocked_rows and _bool(
        checkpoint.get("production_ai_checkpoint_ready")
    )
    summary = {
        "packet_type": "product_production_ai_promotion_workbench",
        "status": (
            "product_production_ai_promotion_workbench_ready"
            if production_ai_promotion_ready
            else "blocked_product_production_ai_promotion_workbench"
        ),
        "promotion_workbench_ready": bool(rows),
        "production_ai_promotion_ready": production_ai_promotion_ready,
        "production_ai_checkpoint_ready": _bool(checkpoint.get("production_ai_checkpoint_ready")),
        "production_ai_inference_subject_active": _bool(checkpoint.get("production_ai_inference_subject_active")),
        "production_promotion_allowed": _bool(checkpoint.get("production_promotion_allowed")),
        "default_residual_mode": _text(checkpoint.get("default_residual_mode")),
        "trained_model_checkpoint_count": _int(checkpoint.get("trained_model_checkpoint_count")),
        "candidate_checkpoint_count": _int(checkpoint.get("candidate_checkpoint_count")),
        "ready_checkpoint_count": _int(checkpoint.get("ready_checkpoint_count")),
        "checkpoint_preflight_ready": _bool(checkpoint.get("checkpoint_preflight_ready")),
        "production_training_data_ready": _bool(checkpoint.get("production_training_data_ready")),
        "gpu_handoff_ready": _bool(checkpoint.get("force_gpu_worker_handoff_ready")),
        "gpu_operator_action_required": _bool(checkpoint.get("force_gpu_worker_operator_action_required")),
        "gpu_return_receipt_ready": _bool(checkpoint.get("force_gpu_worker_return_receipt_ready")),
        "gpu_receipt_expected_queue_rows": _int(checkpoint.get("gpu_receipt_expected_queue_rows")),
        "gpu_receipt_expected_npz_count": _int(checkpoint.get("gpu_receipt_expected_npz_count")),
        "gpu_receipt_manifest_row_count": _int(checkpoint.get("gpu_receipt_manifest_row_count")),
        "gpu_receipt_manifest_ok_row_count": _int(checkpoint.get("gpu_receipt_manifest_ok_row_count")),
        "gpu_receipt_manifest_identity_row_count": _int(checkpoint.get("gpu_receipt_manifest_identity_row_count")),
        "gpu_receipt_manifest_matched_queue_id_count": _int(
            checkpoint.get("gpu_receipt_manifest_matched_queue_id_count")
        ),
        "gpu_receipt_manifest_matched_expected_npz_count": _int(
            checkpoint.get("gpu_receipt_manifest_matched_expected_npz_count")
        ),
        "gpu_receipt_manifest_matched_queue_fingerprint_count": _int(
            checkpoint.get("gpu_receipt_manifest_matched_queue_fingerprint_count")
        ),
        "gpu_receipt_manifest_operator_verified": _bool(checkpoint.get("gpu_receipt_manifest_operator_verified")),
        "gpu_receipt_operator_verified_true_count": _int(checkpoint.get("gpu_receipt_operator_verified_true_count")),
        "gpu_receipt_identity_coverage_ready": _bool(checkpoint.get("gpu_receipt_identity_coverage_ready")),
        "post_return_promotion_ladder_stage_count": len(rows),
        "post_return_promotion_ladder_ready_stage_count": len(rows) - len(blocked_rows),
        "post_return_promotion_ladder_blocked_stage_count": len(blocked_rows),
        "post_return_promotion_ladder_stage_ids": [str(row["stage_id"]) for row in rows],
        "blocked_stage_ids": [str(row["stage_id"]) for row in blocked_rows],
        "ready_key_alias_used_count": len(alias_used_rows),
        "ready_key_alias_used_stage_ids": [str(row["stage_id"]) for row in alias_used_rows],
        "first_blocked_stage_id": _text(first_blocked.get("stage_id")),
        "first_blocked_stage_artifact": _text(first_blocked.get("artifact")),
        "first_blocked_stage_ready_key": _text(first_blocked.get("ready_key")),
        "first_blocked_stage_observed_value": first_blocked.get("observed_value"),
        "checkpoint_failed_check_ids": _list(checkpoint.get("failed_check_ids")),
        "checkpoint_closure_blockers": _list(checkpoint.get("checkpoint_closure_blockers")),
        "checkpoint_missing_output_fields": _list(checkpoint.get("checkpoint_missing_output_fields")),
        "checkpoint_missing_adapter_output_policy_fields": _list(
            checkpoint.get("checkpoint_missing_adapter_output_policy_fields")
        ),
        "selected_sidecar_ready": _bool(checkpoint.get("selected_sidecar_ready")),
        "selected_sidecar_status": _text(checkpoint.get("selected_sidecar_status")),
        "selected_sidecar_blockers": _list(checkpoint.get("selected_sidecar_blockers")),
        "selected_sidecar_missing_output_fields": _list(checkpoint.get("selected_sidecar_missing_output_fields")),
        "training_data_failed_check_ids": _list(checkpoint.get("training_data_failed_check_ids")),
        "training_data_missing_output_labels": _list(checkpoint.get("training_data_missing_output_labels")),
        "force_gpu_worker_full_regeneration_command": _text(
            checkpoint.get("force_gpu_worker_full_regeneration_command")
        ),
        "force_gpu_worker_post_return_validation_command": _text(
            checkpoint.get("force_gpu_worker_post_return_validation_command")
        ),
        "force_gpu_worker_post_run_validation_command_count": _int(
            checkpoint.get("force_gpu_worker_post_run_validation_command_count")
        ),
        "force_gpu_worker_post_run_validation_commands": _list(
            checkpoint.get("force_gpu_worker_post_run_validation_commands")
        ),
        "checkpoint_readiness_artifact_path": checkpoint_readiness_artifact_path,
        "next_required_step": (
            _text(first_blocked.get("next_action"))
            or "Promotion ladder is ready; rerun checkpoint readiness and goal completion audit."
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "blockers": blocked_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# Product Production AI Promotion Workbench",
        "",
        f"- status: `{summary['status']}`",
        f"- production_ai_promotion_ready: `{summary['production_ai_promotion_ready']}`",
        f"- production_ai_checkpoint_ready: `{summary['production_ai_checkpoint_ready']}`",
        f"- default_residual_mode: `{summary['default_residual_mode']}`",
        f"- production_promotion_allowed: `{summary['production_promotion_allowed']}`",
        f"- trained_model_checkpoint_count: `{summary['trained_model_checkpoint_count']}`",
        f"- gpu_handoff_ready: `{summary['gpu_handoff_ready']}`",
        f"- gpu_return_receipt_ready: `{summary['gpu_return_receipt_ready']}`",
        f"- gpu_receipt_expected_queue_rows: `{summary['gpu_receipt_expected_queue_rows']}`",
        f"- gpu_receipt_manifest_identity_row_count: `{summary['gpu_receipt_manifest_identity_row_count']}`",
        f"- blocked_stage_ids: `{','.join(str(item) for item in summary['blocked_stage_ids'])}`",
        f"- next_required_step: `{summary['next_required_step']}`",
        "",
        "## Promotion Ladder",
        "",
        "| order | stage | status | artifact | ready_key | observed | next_action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['promotion_order']} | `{row['stage_id']}` | `{row['status']}` | "
            f"`{row['artifact']}` | `{row['ready_key']}`"
            f"{' via `' + str(row['observed_ready_key']) + '`' if row.get('ready_key_alias_used') else ''} | "
            f"`{row['observed_value']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product production AI promotion workbench.")
    parser.add_argument("--checkpoint-readiness-json", default=DEFAULT_CHECKPOINT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_production_ai_promotion_workbench(
        checkpoint_readiness_packet=_read_json(args.checkpoint_readiness_json),
        checkpoint_readiness_artifact_path=args.checkpoint_readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
