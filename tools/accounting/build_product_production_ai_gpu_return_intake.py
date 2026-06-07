#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HANDOFF_JSON = "runs/residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_RETURN_MANIFEST_TEMPLATE_JSON = "runs/residual_force_gpu_worker_return_manifest_template_current.json"
DEFAULT_RETURN_SUMMARY_TEMPLATE_JSON = "runs/residual_force_gpu_worker_return_summary_template_current.json"
DEFAULT_RETURN_RECEIPT_JSON = "runs/residual_force_gpu_worker_return_receipt_current.json"
DEFAULT_WORKER_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_OUT_JSON = "runs/product_production_ai_gpu_return_intake_current.json"
DEFAULT_OUT_CSV = "runs/product_production_ai_gpu_return_intake_current.csv"
DEFAULT_OUT_MD = "runs/product_production_ai_gpu_return_intake_current.md"
WORKER_ROCM_MANIFEST_COMPLETION_RULE = (
    "manifest_ready=true;rocm_stack_detected=true;torch_rocm_ready=true;amd_gpu_detected=true;visible_device_count>0"
)

CLAIM_BOUNDARY = (
    "Product production AI GPU-return intake only; it audits local handoff, manifest template, summary template, and "
    "return receipt artifacts so an operator can return the exact evidence needed for production AI promotion. It "
    "does not run GPU jobs, regenerate trajectories, derive force labels, train models, create checkpoints, promote "
    "production mode, run docking, upload, submit, email, delete, or mutate external state."
)


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


def _csv_sibling(path_like: str | Path) -> str:
    path = Path(path_like)
    return str(path.with_suffix(".csv")) if path.suffix == ".json" else str(path)


def _row(
    *,
    check_id: str,
    ready: bool,
    observed: str,
    required: str,
    next_action: str,
    source_artifact: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if ready else "fail",
        "observed": observed,
        "required": required,
        "next_action": "" if ready else next_action,
        "source_artifact": source_artifact,
        "release_blocker": not ready,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _first_validation_command(commands: list[str], needle: str) -> str:
    for command in commands:
        if needle in command:
            return command
    return ""


def _acceptance_stage(
    *,
    stage_id: str,
    ready: bool,
    required_checks: list[str],
    artifact: str,
    validation_command: str,
    release_effect: str,
    unlock_fields: list[str] | None = None,
    next_action: str,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "status": "ready" if ready else "blocked",
        "required_checks": required_checks,
        "artifact": artifact,
        "validation_command": validation_command,
        "release_effect": release_effect,
        "unlock_fields": unlock_fields or [],
        "next_action": "" if ready else next_action,
        "release_blocker": not ready,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _artifact_completion_row(
    *,
    artifact_id: str,
    artifact_path: str,
    ready: bool,
    required_checks: list[str],
    blocker_by_check_id: dict[str, dict[str, Any]],
    required_fields_or_columns: list[str],
    validation_command: str,
    next_action: str,
) -> dict[str, Any]:
    failed_checks = [blocker_by_check_id[check_id] for check_id in required_checks if check_id in blocker_by_check_id]
    return {
        "artifact_id": artifact_id,
        "status": "ready" if ready else "blocked",
        "artifact_path": artifact_path,
        "required_checks": required_checks,
        "failed_check_ids": [str(row.get("check_id")) for row in failed_checks],
        "failed_check_count": len(failed_checks),
        "failed_checks": failed_checks,
        "required_fields_or_columns": required_fields_or_columns,
        "validation_command": validation_command,
        "next_action": "" if ready else next_action,
        "release_blocker": not ready,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def build_product_production_ai_gpu_return_intake(
    *,
    handoff_packet: dict[str, Any],
    return_manifest_template_packet: dict[str, Any],
    return_summary_template_packet: dict[str, Any],
    return_receipt_packet: dict[str, Any],
    worker_rocm_manifest_packet: dict[str, Any] | None = None,
    handoff_path: str = DEFAULT_HANDOFF_JSON,
    return_manifest_template_path: str = DEFAULT_RETURN_MANIFEST_TEMPLATE_JSON,
    return_summary_template_path: str = DEFAULT_RETURN_SUMMARY_TEMPLATE_JSON,
    return_receipt_path: str = DEFAULT_RETURN_RECEIPT_JSON,
    worker_rocm_manifest_path: str = DEFAULT_WORKER_ROCM_MANIFEST_JSON,
) -> dict[str, Any]:
    handoff = _summary(handoff_packet)
    manifest_template = _summary(return_manifest_template_packet)
    summary_template = _summary(return_summary_template_packet)
    receipt = _summary(return_receipt_packet)
    worker_rocm = _summary(worker_rocm_manifest_packet or {})

    handoff_ready = _bool(handoff.get("gpu_worker_handoff_ready"))
    manifest_template_ready = _bool(manifest_template.get("return_manifest_template_ready"))
    summary_template_ready = _bool(summary_template.get("return_summary_template_ready"))
    expected_queue_rows = max(
        _int(handoff.get("queue_rows")),
        _int(manifest_template.get("expected_queue_rows")),
        _int(summary_template.get("expected_queue_rows")),
        _int(receipt.get("expected_queue_rows")),
    )
    manifest_template_row_count = _int(manifest_template.get("template_row_count"))
    manifest_status_placeholder_count = _int(manifest_template.get("template_status_placeholder_count"))
    manifest_verification_placeholder_count = _int(manifest_template.get("template_verification_placeholder_count"))
    summary_template_field_count = _int(summary_template.get("template_field_count"))
    summary_template_payload_json = _text(summary_template.get("template_payload_json"))
    summary_template_required_fields = [
        _text(item) for item in _list(summary_template.get("required_summary_fields")) if _text(item)
    ]
    summary_template_required_backend_fields = [
        _text(item) for item in _list(summary_template.get("required_backend_provenance_fields")) if _text(item)
    ]
    summary_template_backend_provenance_contract_ready = bool(
        summary_template.get("backend_provenance_template_ready") is True
        and {"prod_mode", "require_rust_hip", "backend_counts"}.issubset(set(summary_template_required_fields))
        and {"prod_mode", "require_rust_hip", "backend_counts"}.issubset(
            set(summary_template_required_backend_fields)
        )
    )
    post_run_validation_commands = [
        _text(command) for command in _list(handoff.get("post_run_validation_commands")) if _text(command)
    ]
    post_return_validation_command = _text(handoff.get("post_return_validation_command")) or " && ".join(
        post_run_validation_commands
    )
    receipt_ready = _bool(receipt.get("gpu_worker_return_receipt_ready"))
    summary_returned = _bool(receipt.get("full_regeneration_summary_present"))
    summary_complete = _bool(receipt.get("full_regeneration_summary_complete"))
    summary_manifest_bound = _bool(receipt.get("full_regeneration_summary_manifest_bound"))
    summary_manifest_csv = _text(receipt.get("summary_manifest_csv"))
    summary_out_manifest_csv_present = _bool(receipt.get("full_regeneration_summary_out_manifest_csv_present"))
    summary_out_manifest_csv = _text(receipt.get("summary_out_manifest_csv"))
    summary_out_manifest_csv_bound = _bool(receipt.get("full_regeneration_summary_out_manifest_csv_bound"))
    summary_out_summary_json_bound = _bool(receipt.get("full_regeneration_summary_out_summary_json_bound"))
    summary_out_summary_json = _text(receipt.get("summary_out_summary_json"))
    summary_manifest_row_counts_consistent = _bool(
        receipt.get("full_regeneration_summary_manifest_row_counts_consistent")
    )
    production_gpu_backend_provenance_ready = _bool(receipt.get("production_gpu_backend_provenance_ready"))
    production_gpu_backend_rows = _int(receipt.get("production_gpu_backend_rows"))
    production_gpu_backend_non_production_rows = _int(
        receipt.get("production_gpu_backend_non_production_rows")
    )
    production_gpu_backend_prod_mode = _bool(receipt.get("production_gpu_backend_prod_mode"))
    production_gpu_backend_require_rust_hip = _bool(receipt.get("production_gpu_backend_require_rust_hip"))
    worker_rocm_manifest_ready = _bool(worker_rocm.get("manifest_ready"))
    worker_rocm_stack_detected = _bool(worker_rocm.get("rocm_stack_detected"))
    worker_rocm_torch_ready = _bool(worker_rocm.get("torch_rocm_ready"))
    worker_rocm_amd_gpu_detected = _bool(worker_rocm.get("amd_gpu_detected"))
    worker_rocm_visible_device_count = _int(worker_rocm.get("visible_device_count"))
    worker_rocm_device_names = [str(item) for item in _list(worker_rocm.get("device_names"))]
    worker_rocm_ready = bool(
        worker_rocm_manifest_ready
        and worker_rocm_stack_detected
        and worker_rocm_torch_ready
        and worker_rocm_amd_gpu_detected
        and worker_rocm_visible_device_count > 0
    )
    manifest_returned = _bool(receipt.get("full_regeneration_manifest_present"))
    manifest_complete = _bool(receipt.get("full_regeneration_manifest_complete"))
    manifest_npz_paths_complete = _bool(receipt.get("full_regeneration_manifest_npz_paths_complete"))
    manifest_npz_files_exist = _bool(receipt.get("full_regeneration_manifest_npz_files_exist"))
    manifest_npz_files_valid = _bool(receipt.get("full_regeneration_manifest_npz_files_valid"))
    manifest_npz_schema_valid = _bool(receipt.get("full_regeneration_manifest_npz_schema_valid"))
    manifest_npz_identity_valid = _bool(receipt.get("full_regeneration_manifest_npz_identity_valid"))
    manifest_operator_verified = _bool(receipt.get("full_regeneration_manifest_operator_verified"))
    identity_coverage_ready = _bool(receipt.get("queue_manifest_identity_coverage_ready"))
    derivation_ready = _bool(receipt.get("post_run_derivation_validation_ready"))

    rows = [
        _row(
            check_id="gpu_handoff_ready",
            ready=handoff_ready,
            observed=f"gpu_worker_handoff_ready={handoff_ready};queue_rows={_int(handoff.get('queue_rows'))}",
            required="GPU worker handoff package is ready for the prepared queue",
            next_action="Build or refresh the GPU worker handoff package.",
            source_artifact=handoff_path,
        ),
        _row(
            check_id="manifest_template_ready",
            ready=manifest_template_ready and manifest_template_row_count == expected_queue_rows,
            observed=(
                f"template_ready={manifest_template_ready};template_rows={manifest_template_row_count};"
                f"expected_queue_rows={expected_queue_rows};status_placeholders={manifest_status_placeholder_count};"
                f"operator_verification_placeholders={manifest_verification_placeholder_count}"
            ),
            required="identity-locked manifest template has one placeholder row per queue row",
            next_action="Rebuild the return manifest template before GPU execution.",
            source_artifact=return_manifest_template_path,
        ),
        _row(
            check_id="summary_template_ready",
            ready=summary_template_ready and _int(summary_template.get("expected_queue_rows")) == expected_queue_rows,
            observed=(
                f"template_ready={summary_template_ready};expected_queue_rows={_int(summary_template.get('expected_queue_rows'))};"
                f"template_field_count={summary_template_field_count};"
                f"backend_provenance_contract_ready={summary_template_backend_provenance_contract_ready}"
            ),
            required=(
                "summary template defines queue_rows, processed_rows, ok_rows, failed_rows, aborted_early, "
                "out_manifest_csv, out_summary_json, prod_mode, require_rust_hip, and backend_counts"
            ),
            next_action="Rebuild the return summary template before GPU execution.",
            source_artifact=return_summary_template_path,
        ),
        _row(
            check_id="actual_summary_returned_complete",
            ready=summary_returned and summary_complete,
            observed=(
                f"summary_present={summary_returned};summary_complete={summary_complete};"
                f"processed_rows={_int(receipt.get('summary_processed_rows'))};ok_rows={_int(receipt.get('summary_ok_rows'))};"
                f"failed_rows={_int(receipt.get('summary_failed_rows'))};aborted_early={receipt.get('summary_aborted_early')}"
            ),
            required="actual returned summary satisfies the full-regeneration completion rule",
            next_action="Return runs/residual_force_trajectory_regeneration_current_summary.json after the full GPU run.",
            source_artifact=_text(summary_template.get("actual_summary_return_path"))
            or "runs/residual_force_trajectory_regeneration_current_summary.json",
        ),
        _row(
            check_id="actual_summary_manifest_bound",
            ready=summary_manifest_bound,
            observed=(
                f"summary_manifest_csv={summary_manifest_csv};"
                f"actual_manifest_return_path={_text(summary_template.get('actual_manifest_return_path'))};"
                f"summary_manifest_bound={summary_manifest_bound}"
            ),
            required="actual returned summary points to the same manifest CSV being verified by the return receipt",
            next_action="Return a summary JSON whose out_manifest_csv or artifacts.manifest_csv matches the returned manifest CSV.",
            source_artifact=_text(summary_template.get("actual_summary_return_path"))
            or "runs/residual_force_trajectory_regeneration_current_summary.json",
        ),
        _row(
            check_id="actual_summary_out_manifest_csv_present",
            ready=summary_out_manifest_csv_present,
            observed=(
                f"summary_out_manifest_csv={summary_out_manifest_csv};"
                f"summary_out_manifest_csv_present={summary_out_manifest_csv_present}"
            ),
            required="actual returned summary includes top-level out_manifest_csv from the GPU worker summary template",
            next_action="Return a summary JSON with top-level out_manifest_csv set to the returned manifest CSV.",
            source_artifact=_text(summary_template.get("actual_summary_return_path"))
            or "runs/residual_force_trajectory_regeneration_current_summary.json",
        ),
        _row(
            check_id="actual_summary_out_manifest_csv_bound",
            ready=summary_out_manifest_csv_bound,
            observed=(
                f"summary_out_manifest_csv={summary_out_manifest_csv};"
                f"actual_manifest_return_path={_text(summary_template.get('actual_manifest_return_path'))};"
                f"summary_out_manifest_csv_bound={summary_out_manifest_csv_bound}"
            ),
            required="actual returned summary top-level out_manifest_csv matches the returned manifest CSV path",
            next_action="Return a summary JSON with top-level out_manifest_csv set to the same manifest CSV being returned.",
            source_artifact=_text(summary_template.get("actual_summary_return_path"))
            or "runs/residual_force_trajectory_regeneration_current_summary.json",
        ),
        _row(
            check_id="actual_summary_out_summary_json_bound",
            ready=summary_out_summary_json_bound,
            observed=(
                f"summary_out_summary_json={summary_out_summary_json};"
                f"actual_summary_return_path={_text(summary_template.get('actual_summary_return_path'))};"
                f"summary_out_summary_json_bound={summary_out_summary_json_bound}"
            ),
            required="actual returned summary includes top-level out_summary_json matching the returned summary JSON path",
            next_action="Return a summary JSON with top-level out_summary_json set to the returned summary JSON path.",
            source_artifact=_text(summary_template.get("actual_summary_return_path"))
            or "runs/residual_force_trajectory_regeneration_current_summary.json",
        ),
        _row(
            check_id="actual_summary_manifest_row_counts_consistent",
            ready=summary_manifest_row_counts_consistent,
            observed=(
                f"summary_processed_rows={_int(receipt.get('summary_processed_rows'))};"
                f"summary_ok_rows={_int(receipt.get('summary_ok_rows'))};"
                f"manifest_row_count={_int(receipt.get('manifest_row_count'))};"
                f"manifest_ok_row_count={_int(receipt.get('manifest_ok_row_count'))};"
                f"summary_manifest_row_counts_consistent={summary_manifest_row_counts_consistent}"
            ),
            required="actual returned summary processed/ok rows match returned manifest row/ok-row counts",
            next_action="Return a summary JSON and manifest CSV from the same full GPU regeneration run.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="production_gpu_backend_provenance",
            ready=production_gpu_backend_provenance_ready,
            observed=(
                f"production_gpu_backend_provenance_ready={production_gpu_backend_provenance_ready};"
                f"prod_mode={production_gpu_backend_prod_mode};"
                f"require_rust_hip={production_gpu_backend_require_rust_hip};"
                f"production_gpu_backend_rows={production_gpu_backend_rows};"
                f"non_production_backend_rows={production_gpu_backend_non_production_rows};"
                f"expected_queue_rows={expected_queue_rows}"
            ),
            required="actual returned summary proves production GPU/HIP backend coverage with no CPU diagnostic fallback rows",
            next_action=(
                "Return a production GPU/HIP summary from the identity-locked handoff command; CPU diagnostic "
                "runs cannot unlock checkpoint promotion."
            ),
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="worker_rocm_environment_manifest_ready",
            ready=worker_rocm_ready,
            observed=(
                f"manifest_ready={worker_rocm_manifest_ready};"
                f"rocm_stack_detected={worker_rocm_stack_detected};"
                f"torch_rocm_ready={worker_rocm_torch_ready};"
                f"amd_gpu_detected={worker_rocm_amd_gpu_detected};"
                f"visible_device_count={worker_rocm_visible_device_count};"
                f"device_names={','.join(worker_rocm_device_names)}"
            ),
            required=(
                "worker-returned ROCm/PyTorch manifest proves the same GPU worker exposed at least one "
                "visible AMD ROCm device to PyTorch"
            ),
            next_action=(
                "Run python3 tools/build_rocm_environment_manifest.py on the GPU worker after pilot/full "
                "regeneration and return runs/rocm_environment_manifest_current.json with torch_rocm_ready=true "
                "and visible_device_count>0."
            ),
            source_artifact=worker_rocm_manifest_path,
        ),
        _row(
            check_id="actual_manifest_returned_complete",
            ready=manifest_returned and manifest_complete,
            observed=(
                f"manifest_present={manifest_returned};manifest_complete={manifest_complete};"
                f"manifest_rows={_int(receipt.get('manifest_row_count'))};ok_rows={_int(receipt.get('manifest_ok_row_count'))};"
                f"status_placeholders={_int(receipt.get('manifest_status_placeholder_count'))};"
                f"status_invalid={_int(receipt.get('manifest_status_invalid_count'))}"
            ),
            required="actual returned manifest has allowed ok status for every expected queue row",
            next_action="Return the completed manifest CSV with allowed ok statuses for every regenerated row.",
            source_artifact=_text(summary_template.get("actual_manifest_return_path"))
            or "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        ),
        _row(
            check_id="actual_manifest_npz_paths_complete",
            ready=manifest_npz_paths_complete,
            observed=(
                f"npz_path_column_present={receipt.get('manifest_npz_path_column_present')};"
                f"npz_path_present_count={_int(receipt.get('manifest_npz_path_present_count'))};"
                f"npz_path_missing_count={_int(receipt.get('manifest_npz_path_missing_count'))};"
                f"ok_row_missing_npz_path_count={_int(receipt.get('manifest_ok_row_missing_npz_path_count'))};"
                f"operator_verified_missing_npz_path_count={_int(receipt.get('manifest_operator_verified_missing_npz_path_count'))}"
            ),
            required="actual returned manifest has an NPZ path on every ok and operator-verified row",
            next_action="Fill expected_regenerated_trajectory_npz, trajectory_npz, output_npz, or generated_npz for every completed manifest row.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="actual_manifest_npz_files_exist",
            ready=manifest_npz_files_exist,
            observed=(
                f"npz_file_existing_count={_int(receipt.get('manifest_npz_file_existing_count'))};"
                f"npz_file_missing_count={_int(receipt.get('manifest_npz_file_missing_count'))};"
                f"ok_row_missing_npz_file_count={_int(receipt.get('manifest_ok_row_missing_npz_file_count'))};"
                f"operator_verified_missing_npz_file_count={_int(receipt.get('manifest_operator_verified_missing_npz_file_count'))}"
            ),
            required="actual returned manifest NPZ paths resolve to local files for every ok and operator-verified row",
            next_action="Restore or return the regenerated NPZ files at the manifest paths before accepting the GPU return.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="actual_manifest_npz_files_valid",
            ready=manifest_npz_files_valid,
            observed=(
                f"npz_file_valid_count={_int(receipt.get('manifest_npz_file_valid_count'))};"
                f"npz_file_invalid_count={_int(receipt.get('manifest_npz_file_invalid_count'))};"
                f"ok_row_invalid_npz_file_count={_int(receipt.get('manifest_ok_row_invalid_npz_file_count'))};"
                f"operator_verified_invalid_npz_file_count={_int(receipt.get('manifest_operator_verified_invalid_npz_file_count'))}"
            ),
            required="actual returned manifest NPZ files are readable non-empty NPZ bundles for every ok and operator-verified row",
            next_action="Return readable NPZ bundles at the manifest paths before accepting the GPU return.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="actual_manifest_npz_schema_valid",
            ready=manifest_npz_schema_valid,
            observed=(
                f"npz_schema_valid_count={_int(receipt.get('manifest_npz_schema_valid_count'))};"
                f"npz_schema_invalid_count={_int(receipt.get('manifest_npz_schema_invalid_count'))};"
                f"ok_row_invalid_npz_schema_count={_int(receipt.get('manifest_ok_row_invalid_npz_schema_count'))};"
                f"operator_verified_invalid_npz_schema_count={_int(receipt.get('manifest_operator_verified_invalid_npz_schema_count'))};"
                "required_npz_schema_keys=protein_ca,ligand_frames"
            ),
            required="actual returned NPZ bundles contain protein_ca [P,3] and ligand_frames [T,L,3] arrays",
            next_action="Return regenerated trajectory NPZ bundles with protein_ca and ligand_frames arrays before accepting the GPU return.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="actual_manifest_npz_identity_valid",
            ready=manifest_npz_identity_valid,
            observed=(
                f"npz_identity_valid_count={_int(receipt.get('manifest_npz_identity_valid_count'))};"
                f"npz_identity_invalid_count={_int(receipt.get('manifest_npz_identity_invalid_count'))};"
                f"ok_row_invalid_npz_identity_count={_int(receipt.get('manifest_ok_row_invalid_npz_identity_count'))};"
                f"operator_verified_invalid_npz_identity_count={_int(receipt.get('manifest_operator_verified_invalid_npz_identity_count'))};"
                "required_npz_identity_keys=queue_id"
            ),
            required="actual returned NPZ bundles contain queue_id metadata matching the identity-locked manifest rows",
            next_action="Return regenerated trajectory NPZ bundles with queue_id metadata matching the prepared queue rows.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="actual_manifest_operator_verified",
            ready=manifest_operator_verified,
            observed=(
                f"operator_column_present={receipt.get('manifest_operator_verification_column_present')};"
                f"operator_verified_true_count={_int(receipt.get('manifest_operator_verified_true_count'))};"
                f"operator_placeholder_count={_int(receipt.get('manifest_operator_verification_placeholder_count'))};"
                f"operator_false_count={_int(receipt.get('manifest_operator_verification_false_count'))};"
                f"operator_invalid_count={_int(receipt.get('manifest_operator_verification_invalid_count'))}"
            ),
            required="operator_verified_npz_exists is true for every expected returned row",
            next_action="Verify each regenerated NPZ exists and mark operator_verified_npz_exists=true.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="queue_manifest_identity_coverage",
            ready=identity_coverage_ready,
            observed=(
                f"identity_coverage_ready={identity_coverage_ready};queue_identity_rows={_int(receipt.get('queue_identity_row_count'))};"
                f"manifest_identity_rows={_int(receipt.get('manifest_identity_row_count'))};"
                f"matched_queue_ids={_int(receipt.get('manifest_matched_queue_id_count'))};"
                f"matched_expected_npz={_int(receipt.get('manifest_matched_expected_npz_count'))};"
                f"matched_fingerprints={_int(receipt.get('manifest_matched_queue_fingerprint_count'))}"
            ),
            required="returned manifest covers the prepared queue by queue_id, expected/generated NPZ, or row fingerprint",
            next_action="Return the identity-locked manifest rows from the prefilled template.",
            source_artifact=return_receipt_path,
        ),
        _row(
            check_id="post_run_force_derivation_validation",
            ready=derivation_ready,
            observed=(
                f"post_run_derivation_validation_ready={derivation_ready};"
                f"post_run_derivation_npz_ready={receipt.get('post_run_derivation_npz_ready')};"
                f"post_run_derivation_samples_ready={receipt.get('post_run_derivation_samples_ready')}"
            ),
            required="force derivation validation accepts the regenerated NPZ bundles",
            next_action="Rerun residual force derivation validation after the returned NPZ bundles are present.",
            source_artifact=return_receipt_path,
        ),
    ]
    blockers = [row for row in rows if row["status"] != "pass"]
    intake_ready = all(row["status"] == "pass" for row in rows[:3])
    first_blocker = blockers[0] if blockers else {}
    return_summary_path = (
        _text(summary_template.get("actual_summary_return_path"))
        or "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    return_manifest_path = (
        _text(summary_template.get("actual_manifest_return_path"))
        or "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    required_return_artifacts = [
        return_summary_path,
        return_manifest_path,
        "regenerated NPZ bundles referenced by the returned manifest",
        "runs/residual_force_derivation_validation_current.json",
        worker_rocm_manifest_path,
    ]
    required_manifest_columns = [
        "queue_id",
        "expected_regenerated_trajectory_npz",
        "status",
        "operator_verified_npz_exists",
    ]
    validation_ladder_ready = bool(post_run_validation_commands and len(post_run_validation_commands) >= 18)
    template_acceptance_ready = intake_ready
    summary_acceptance_checks = [
        "actual_summary_returned_complete",
        "actual_summary_manifest_bound",
        "actual_summary_out_manifest_csv_present",
        "actual_summary_out_manifest_csv_bound",
        "actual_summary_out_summary_json_bound",
        "actual_summary_manifest_row_counts_consistent",
        "production_gpu_backend_provenance",
    ]
    manifest_acceptance_checks = [
        "actual_manifest_returned_complete",
        "actual_manifest_npz_paths_complete",
        "actual_manifest_npz_files_exist",
        "actual_manifest_npz_files_valid",
        "actual_manifest_npz_schema_valid",
        "actual_manifest_npz_identity_valid",
        "actual_manifest_operator_verified",
        "queue_manifest_identity_coverage",
    ]
    failed_check_ids = {str(row["check_id"]) for row in blockers}
    summary_acceptance_ready = not any(check_id in failed_check_ids for check_id in summary_acceptance_checks)
    manifest_acceptance_ready = not any(check_id in failed_check_ids for check_id in manifest_acceptance_checks)
    derivation_acceptance_ready = derivation_ready
    promotion_unlock_ready = receipt_ready and validation_ladder_ready
    acceptance_rows = [
        _acceptance_stage(
            stage_id="gpu_return_templates_preflight",
            ready=template_acceptance_ready,
            required_checks=["gpu_handoff_ready", "manifest_template_ready", "summary_template_ready"],
            artifact=f"{handoff_path};{return_manifest_template_path};{return_summary_template_path}",
            validation_command=_text(handoff.get("full_regeneration_command"))
            or "python3 tools/generate_ligand_trajectory_engine.py ...",
            release_effect="operator can run the exact identity-locked GPU regeneration queue",
            next_action="Refresh handoff, manifest template, and summary template before GPU execution.",
        ),
        _acceptance_stage(
            stage_id="returned_summary_acceptance",
            ready=summary_acceptance_ready,
            required_checks=summary_acceptance_checks,
            artifact=return_summary_path,
            validation_command=_first_validation_command(
                post_run_validation_commands, "build_residual_force_gpu_worker_return_receipt.py"
            ),
            release_effect="returned summary is complete and bound to the returned manifest",
            next_action="Return the completed GPU summary JSON with out_manifest_csv and out_summary_json bound.",
        ),
        _acceptance_stage(
            stage_id="returned_manifest_npz_acceptance",
            ready=manifest_acceptance_ready,
            required_checks=manifest_acceptance_checks,
            artifact=f"{return_manifest_path};regenerated NPZ bundles referenced by manifest",
            validation_command=_first_validation_command(
                post_run_validation_commands, "build_residual_force_gpu_worker_return_receipt.py"
            ),
            release_effect="returned manifest, NPZ bundle existence, schema, identity, and operator verification are accepted",
            next_action="Return the completed manifest and regenerated NPZ bundles with identity/operator verification.",
        ),
        _acceptance_stage(
            stage_id="force_derivation_acceptance",
            ready=derivation_acceptance_ready,
            required_checks=["post_run_force_derivation_validation"],
            artifact="runs/residual_force_derivation_validation_current.json",
            validation_command=_first_validation_command(
                post_run_validation_commands, "build_residual_force_derivation_validation.py"
            ),
            release_effect="regenerated NPZ bundles can unlock delta_force derivation labels",
            unlock_fields=["delta_force"],
            next_action="Rerun residual force derivation validation after summary, manifest, and NPZ bundles are present.",
        ),
        _acceptance_stage(
            stage_id="post_return_promotion_chain",
            ready=promotion_unlock_ready,
            required_checks=["operator_return_validation_ladder_ready", "gpu_return_artifacts_ready"],
            artifact="runs/product_production_ai_promotion_workbench_current.json",
            validation_command=post_return_validation_command,
            release_effect="post-return validation chain can advance toward training data, checkpoint sidecar, preflight, registry, and goal audit",
            unlock_fields=["delta_force", "uncertainty", "abstention_reason", "stage2_route_decision"],
            next_action="Complete GPU return acceptance, then run the post-return validation chain.",
        ),
    ]
    acceptance_blockers = [row for row in acceptance_rows if row["status"] != "ready"]
    first_acceptance_blocker = acceptance_blockers[0] if acceptance_blockers else {}
    acceptance_matrix_ready = bool(acceptance_rows) and validation_ladder_ready
    blocker_by_check_id = {
        _text(row.get("check_id")): dict(row)
        for row in blockers
        if _text(row.get("check_id"))
    }
    return_receipt_validation_command = _first_validation_command(
        post_run_validation_commands, "build_residual_force_gpu_worker_return_receipt.py"
    )
    force_derivation_validation_command = _first_validation_command(
        post_run_validation_commands, "build_residual_force_derivation_validation.py"
    )
    operator_return_artifact_completion_matrix = [
        _artifact_completion_row(
            artifact_id="returned_summary_json",
            artifact_path=return_summary_path,
            ready=summary_acceptance_ready,
            required_checks=summary_acceptance_checks,
            blocker_by_check_id=blocker_by_check_id,
            required_fields_or_columns=summary_template_required_fields,
            validation_command=return_receipt_validation_command,
            next_action="Return the completed GPU summary JSON with template fields, manifest binding, and GPU/HIP backend provenance.",
        ),
        _artifact_completion_row(
            artifact_id="returned_manifest_csv",
            artifact_path=return_manifest_path,
            ready=manifest_returned and manifest_complete and identity_coverage_ready,
            required_checks=[
                "actual_manifest_returned_complete",
                "actual_manifest_npz_paths_complete",
                "actual_manifest_operator_verified",
                "queue_manifest_identity_coverage",
            ],
            blocker_by_check_id=blocker_by_check_id,
            required_fields_or_columns=required_manifest_columns,
            validation_command=return_receipt_validation_command,
            next_action="Return the completed identity-locked manifest CSV with ok statuses, NPZ paths, and operator verification.",
        ),
        _artifact_completion_row(
            artifact_id="regenerated_npz_bundles",
            artifact_path="regenerated NPZ bundles referenced by the returned manifest",
            ready=(
                manifest_npz_paths_complete
                and manifest_npz_files_exist
                and manifest_npz_files_valid
                and manifest_npz_schema_valid
                and manifest_npz_identity_valid
            ),
            required_checks=[
                "actual_manifest_npz_paths_complete",
                "actual_manifest_npz_files_exist",
                "actual_manifest_npz_files_valid",
                "actual_manifest_npz_schema_valid",
                "actual_manifest_npz_identity_valid",
            ],
            blocker_by_check_id=blocker_by_check_id,
            required_fields_or_columns=["protein_ca", "ligand_frames", "queue_id"],
            validation_command=return_receipt_validation_command,
            next_action="Return readable NPZ bundles at the manifest paths with protein_ca, ligand_frames, and matching queue_id metadata.",
        ),
        _artifact_completion_row(
            artifact_id="post_run_force_derivation_validation",
            artifact_path="runs/residual_force_derivation_validation_current.json",
            ready=derivation_acceptance_ready,
            required_checks=["post_run_force_derivation_validation"],
            blocker_by_check_id=blocker_by_check_id,
            required_fields_or_columns=["delta_force"],
            validation_command=force_derivation_validation_command,
            next_action="Rerun residual force derivation validation after summary, manifest, and NPZ bundles are present.",
        ),
        _artifact_completion_row(
            artifact_id="worker_rocm_environment_manifest",
            artifact_path=worker_rocm_manifest_path,
            ready=worker_rocm_ready,
            required_checks=["worker_rocm_environment_manifest_ready"],
            blocker_by_check_id=blocker_by_check_id,
            required_fields_or_columns=[
                "manifest_ready",
                "rocm_stack_detected",
                "torch_rocm_ready",
                "amd_gpu_detected",
                "visible_device_count",
            ],
            validation_command="python3 tools/build_rocm_environment_manifest.py",
            next_action=(
                "Return the GPU-worker ROCm manifest generated after the pilot/full run with "
                "torch_rocm_ready=true and visible_device_count>0."
            ),
        ),
    ]
    operator_return_artifact_completion_blockers = [
        row for row in operator_return_artifact_completion_matrix if row["status"] != "ready"
    ]
    next_return_artifact = (
        operator_return_artifact_completion_blockers[0]
        if operator_return_artifact_completion_blockers
        else {}
    )
    next_artifact_completion_packet = {
        "artifact_id": _text(next_return_artifact.get("artifact_id")),
        "artifact_path": _text(next_return_artifact.get("artifact_path")),
        "packet_ready": bool(next_return_artifact),
        "template_payload_json": summary_template_payload_json,
        "template_payload": (
            dict(summary_template.get("template_payload"))
            if isinstance(summary_template.get("template_payload"), dict)
            else {}
        ),
        "expected_queue_rows": expected_queue_rows,
        "actual_summary_return_path": return_summary_path,
        "actual_manifest_return_path": return_manifest_path,
        "required_fields_or_columns": [
            str(item) for item in (next_return_artifact.get("required_fields_or_columns") or [])
        ],
        "failed_check_ids": [str(item) for item in (next_return_artifact.get("failed_check_ids") or [])],
        "validation_command": _text(next_return_artifact.get("validation_command")),
        "full_regeneration_command": _text(handoff.get("full_regeneration_command")),
        "completion_rule": (
            _text(summary_template.get("required_completion_rule"))
            if _text(next_return_artifact.get("artifact_id")) == "returned_summary_json"
            else _text(next_return_artifact.get("next_action"))
        ),
        "backend_provenance_completion_rule": (
            _text(summary_template.get("backend_provenance_completion_rule"))
            if _text(next_return_artifact.get("artifact_id")) == "returned_summary_json"
            else ""
        ),
        "next_action": _text(next_return_artifact.get("next_action")),
        "release_blocker": bool(next_return_artifact.get("release_blocker") is True),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }
    acceptance_stage_check_matrix = []
    for stage in acceptance_rows:
        required_checks = [str(item) for item in (stage.get("required_checks") or [])]
        failed_checks = [blocker_by_check_id[check_id] for check_id in required_checks if check_id in blocker_by_check_id]
        unmatched_required_checks = [
            check_id
            for check_id in required_checks
            if check_id not in blocker_by_check_id and _text(stage.get("status")) != "ready"
        ]
        acceptance_stage_check_matrix.append(
            {
                "stage_id": _text(stage.get("stage_id")),
                "status": _text(stage.get("status")),
                "artifact": _text(stage.get("artifact")),
                "required_checks": required_checks,
                "failed_check_ids": [str(row.get("check_id")) for row in failed_checks],
                "failed_check_count": len(failed_checks),
                "failed_checks": failed_checks,
                "unmatched_required_check_ids": unmatched_required_checks,
                "unmatched_required_check_count": len(unmatched_required_checks),
                "validation_command": _text(stage.get("validation_command")),
                "release_effect": _text(stage.get("release_effect")),
                "unlock_fields": [str(item) for item in (stage.get("unlock_fields") or [])],
                "next_action": _text(stage.get("next_action")),
                "release_blocker": stage.get("release_blocker") is True,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    acceptance_stage_check_blockers = [
        row for row in acceptance_stage_check_matrix if _text(row.get("status")) != "ready"
    ]
    handoff_queue_csv = _text(handoff.get("queue_csv"))
    handoff_queue_csv_sha256 = _text(handoff.get("queue_csv_sha256"))
    handoff_full_regeneration_command = _text(handoff.get("full_regeneration_command"))
    handoff_manifest_identity_rule = _text(handoff.get("return_manifest_required_identity_rule"))
    handoff_manifest_fingerprint_columns = [
        str(item) for item in _list(handoff.get("return_manifest_fingerprint_columns"))
    ]
    handoff_manifest_queue_id_columns = [
        str(item) for item in _list(handoff.get("return_manifest_queue_id_columns"))
    ]
    handoff_manifest_npz_columns = [
        str(item) for item in _list(handoff.get("return_manifest_npz_columns"))
    ]
    handoff_binding_ready = bool(
        handoff_ready
        and handoff_queue_csv
        and handoff_queue_csv_sha256
        and handoff_full_regeneration_command
        and _bool(handoff.get("return_manifest_schema_contract_ready"))
        and handoff_manifest_identity_rule
        and handoff_manifest_fingerprint_columns
        and return_manifest_path
        and return_summary_path
    )
    summary = {
        "packet_type": "product_production_ai_gpu_return_intake",
        "status": (
            "product_production_ai_gpu_return_intake_ready"
            if receipt_ready
            else "blocked_product_production_ai_gpu_return_intake"
        ),
        "gpu_return_intake_ready": intake_ready,
        "gpu_return_artifacts_ready": receipt_ready,
        "check_count": len(rows),
        "pass_check_count": len(rows) - len(blockers),
        "fail_check_count": len(blockers),
        "failed_check_ids": [str(row["check_id"]) for row in blockers],
        "operator_return_blocker_count": len(blockers),
        "first_failed_check_id": _text(first_blocker.get("check_id")),
        "first_failed_source_artifact": _text(first_blocker.get("source_artifact")),
        "first_failed_required": _text(first_blocker.get("required")),
        "first_failed_observed": _text(first_blocker.get("observed")),
        "first_failed_next_action": _text(first_blocker.get("next_action")),
        "expected_queue_rows": expected_queue_rows,
        "operator_return_bundle_contract_ready": intake_ready
        and bool(return_summary_path)
        and bool(return_manifest_path)
        and manifest_template_row_count == expected_queue_rows
        and validation_ladder_ready,
        "operator_return_required_artifacts": required_return_artifacts,
        "operator_return_required_artifact_count": len(required_return_artifacts),
        "operator_return_artifact_completion_matrix": operator_return_artifact_completion_matrix,
        "operator_return_artifact_completion_matrix_count": len(operator_return_artifact_completion_matrix),
        "operator_return_artifact_completion_blocker_matrix": operator_return_artifact_completion_blockers,
        "operator_return_artifact_completion_blocker_count": len(
            operator_return_artifact_completion_blockers
        ),
        "operator_return_next_artifact_completion_packet_ready": bool(
            next_artifact_completion_packet.get("packet_ready") is True
        ),
        "operator_return_next_artifact_completion_packet": next_artifact_completion_packet,
        "operator_return_next_artifact_id": _text(
            (operator_return_artifact_completion_blockers[0] if operator_return_artifact_completion_blockers else {}).get(
                "artifact_id"
            )
        ),
        "operator_return_next_artifact_path": _text(
            (operator_return_artifact_completion_blockers[0] if operator_return_artifact_completion_blockers else {}).get(
                "artifact_path"
            )
        ),
        "operator_return_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                (operator_return_artifact_completion_blockers[0] if operator_return_artifact_completion_blockers else {}).get(
                    "failed_check_ids"
                )
                or []
            )
        ],
        "operator_return_manifest_required_columns": required_manifest_columns,
        "operator_return_manifest_required_column_count": len(required_manifest_columns),
        "operator_return_validation_ladder_ready": validation_ladder_ready,
        "operator_return_handoff_binding_ready": handoff_binding_ready,
        "operator_return_handoff_queue_csv": handoff_queue_csv,
        "operator_return_handoff_queue_csv_sha256": handoff_queue_csv_sha256,
        "operator_return_handoff_full_regeneration_command": handoff_full_regeneration_command,
        "operator_return_handoff_return_manifest_schema_contract_ready": _bool(
            handoff.get("return_manifest_schema_contract_ready")
        ),
        "operator_return_handoff_return_manifest_required_identity_rule": handoff_manifest_identity_rule,
        "operator_return_handoff_return_manifest_fingerprint_columns": handoff_manifest_fingerprint_columns,
        "operator_return_handoff_return_manifest_queue_id_columns": handoff_manifest_queue_id_columns,
        "operator_return_handoff_return_manifest_npz_columns": handoff_manifest_npz_columns,
        "operator_acceptance_matrix_ready": acceptance_matrix_ready,
        "operator_acceptance_stage_count": len(acceptance_rows),
        "operator_acceptance_ready_stage_count": len(acceptance_rows) - len(acceptance_blockers),
        "operator_acceptance_blocked_stage_count": len(acceptance_blockers),
        "operator_acceptance_stage_ids": [str(row["stage_id"]) for row in acceptance_rows],
        "operator_acceptance_ready_stage_ids": [
            str(row["stage_id"]) for row in acceptance_rows if row["status"] == "ready"
        ],
        "operator_acceptance_blocked_stage_ids": [str(row["stage_id"]) for row in acceptance_blockers],
        "operator_acceptance_next_stage_id": _text(first_acceptance_blocker.get("stage_id")),
        "operator_acceptance_next_stage_artifact": _text(first_acceptance_blocker.get("artifact")),
        "operator_acceptance_next_stage_validation_command": _text(
            first_acceptance_blocker.get("validation_command")
        ),
        "operator_acceptance_next_stage_release_effect": _text(first_acceptance_blocker.get("release_effect")),
        "operator_acceptance_next_stage_unlock_fields": [
            str(item) for item in (first_acceptance_blocker.get("unlock_fields") or [])
        ],
        "operator_acceptance_next_stage_required_checks": [
            str(item) for item in (first_acceptance_blocker.get("required_checks") or [])
        ],
        "operator_acceptance_next_stage_next_action": _text(first_acceptance_blocker.get("next_action")),
        "operator_acceptance_stage_check_matrix": acceptance_stage_check_matrix,
        "operator_acceptance_stage_check_matrix_count": len(acceptance_stage_check_matrix),
        "operator_acceptance_current_blocked_stage_check_matrix": acceptance_stage_check_blockers,
        "operator_acceptance_current_blocked_stage_check_matrix_count": len(acceptance_stage_check_blockers),
        "handoff_ready": handoff_ready,
        "operator_action_required": not receipt_ready,
        "manifest_template_ready": manifest_template_ready,
        "manifest_template_csv": _text(manifest_template.get("template_csv")),
        "manifest_template_row_count": manifest_template_row_count,
        "manifest_status_placeholder_count": manifest_status_placeholder_count,
        "manifest_operator_verification_placeholder_count": manifest_verification_placeholder_count,
        "summary_template_ready": summary_template_ready,
        "summary_template_csv": _csv_sibling(return_summary_template_path),
        "summary_template_payload_json": summary_template_payload_json,
        "summary_template_payload": (
            dict(summary_template.get("template_payload"))
            if isinstance(summary_template.get("template_payload"), dict)
            else {}
        ),
        "summary_template_field_count": summary_template_field_count,
        "summary_template_required_fields": summary_template_required_fields,
        "summary_template_completion_rule": _text(summary_template.get("required_completion_rule")),
        "summary_template_backend_provenance_contract_ready": (
            summary_template_backend_provenance_contract_ready
        ),
        "summary_template_required_backend_provenance_fields": summary_template_required_backend_fields,
        "summary_template_backend_provenance_completion_rule": _text(
            summary_template.get("backend_provenance_completion_rule")
        ),
        "actual_summary_return_path": return_summary_path,
        "actual_manifest_return_path": return_manifest_path,
        "receipt_status": _text(receipt.get("status")),
        "receipt_blockers": _list(receipt.get("blockers")),
        "summary_returned": summary_returned,
        "summary_complete": summary_complete,
        "summary_manifest_bound": summary_manifest_bound,
        "summary_manifest_csv": summary_manifest_csv,
        "summary_out_manifest_csv_present": summary_out_manifest_csv_present,
        "summary_out_manifest_csv": summary_out_manifest_csv,
        "summary_out_manifest_csv_bound": summary_out_manifest_csv_bound,
        "summary_out_summary_json_bound": summary_out_summary_json_bound,
        "summary_out_summary_json": summary_out_summary_json,
        "summary_manifest_row_counts_consistent": summary_manifest_row_counts_consistent,
        "production_gpu_backend_provenance_ready": production_gpu_backend_provenance_ready,
        "production_gpu_backend_rows": production_gpu_backend_rows,
        "production_gpu_backend_non_production_rows": production_gpu_backend_non_production_rows,
        "production_gpu_backend_prod_mode": production_gpu_backend_prod_mode,
        "production_gpu_backend_require_rust_hip": production_gpu_backend_require_rust_hip,
        "worker_rocm_manifest_artifact": worker_rocm_manifest_path,
        "worker_rocm_manifest_ready": worker_rocm_ready,
        "worker_rocm_manifest_generation_command": _text(worker_rocm.get("manifest_generation_command"))
        or "python3 tools/build_rocm_environment_manifest.py",
        "worker_rocm_manifest_completion_rule": WORKER_ROCM_MANIFEST_COMPLETION_RULE,
        "worker_rocm_stack_detected": worker_rocm_stack_detected,
        "worker_rocm_torch_ready": worker_rocm_torch_ready,
        "worker_rocm_amd_gpu_detected": worker_rocm_amd_gpu_detected,
        "worker_rocm_visible_device_count": worker_rocm_visible_device_count,
        "worker_rocm_device_names": worker_rocm_device_names,
        "worker_rocm_next_required_step": _text(worker_rocm.get("next_required_step"))
        or (
            "Run python3 tools/build_rocm_environment_manifest.py on the GPU worker and return "
            "torch_rocm_ready=true with visible_device_count>0."
        ),
        "manifest_returned": manifest_returned,
        "manifest_complete": manifest_complete,
        "manifest_npz_paths_complete": manifest_npz_paths_complete,
        "manifest_npz_files_exist": manifest_npz_files_exist,
        "manifest_npz_files_valid": manifest_npz_files_valid,
        "manifest_npz_schema_valid": manifest_npz_schema_valid,
        "manifest_npz_identity_valid": manifest_npz_identity_valid,
        "manifest_npz_path_column_present": _bool(receipt.get("manifest_npz_path_column_present")),
        "manifest_npz_path_present_count": _int(receipt.get("manifest_npz_path_present_count")),
        "manifest_npz_path_missing_count": _int(receipt.get("manifest_npz_path_missing_count")),
        "manifest_ok_row_missing_npz_path_count": _int(receipt.get("manifest_ok_row_missing_npz_path_count")),
        "manifest_operator_verified_missing_npz_path_count": _int(
            receipt.get("manifest_operator_verified_missing_npz_path_count")
        ),
        "manifest_npz_file_existing_count": _int(receipt.get("manifest_npz_file_existing_count")),
        "manifest_npz_file_missing_count": _int(receipt.get("manifest_npz_file_missing_count")),
        "manifest_ok_row_missing_npz_file_count": _int(receipt.get("manifest_ok_row_missing_npz_file_count")),
        "manifest_operator_verified_missing_npz_file_count": _int(
            receipt.get("manifest_operator_verified_missing_npz_file_count")
        ),
        "manifest_npz_file_valid_count": _int(receipt.get("manifest_npz_file_valid_count")),
        "manifest_npz_file_invalid_count": _int(receipt.get("manifest_npz_file_invalid_count")),
        "manifest_ok_row_invalid_npz_file_count": _int(receipt.get("manifest_ok_row_invalid_npz_file_count")),
        "manifest_operator_verified_invalid_npz_file_count": _int(
            receipt.get("manifest_operator_verified_invalid_npz_file_count")
        ),
        "manifest_npz_schema_valid_count": _int(receipt.get("manifest_npz_schema_valid_count")),
        "manifest_npz_schema_invalid_count": _int(receipt.get("manifest_npz_schema_invalid_count")),
        "manifest_ok_row_invalid_npz_schema_count": _int(
            receipt.get("manifest_ok_row_invalid_npz_schema_count")
        ),
        "manifest_operator_verified_invalid_npz_schema_count": _int(
            receipt.get("manifest_operator_verified_invalid_npz_schema_count")
        ),
        "manifest_npz_identity_valid_count": _int(receipt.get("manifest_npz_identity_valid_count")),
        "manifest_npz_identity_invalid_count": _int(receipt.get("manifest_npz_identity_invalid_count")),
        "manifest_ok_row_invalid_npz_identity_count": _int(
            receipt.get("manifest_ok_row_invalid_npz_identity_count")
        ),
        "manifest_operator_verified_invalid_npz_identity_count": _int(
            receipt.get("manifest_operator_verified_invalid_npz_identity_count")
        ),
        "manifest_operator_verified": manifest_operator_verified,
        "identity_coverage_ready": identity_coverage_ready,
        "post_run_derivation_validation_ready": derivation_ready,
        "post_return_validation_command": post_return_validation_command,
        "post_run_validation_command_count": len(post_run_validation_commands)
        or _int(handoff.get("post_run_validation_command_count")),
        "post_run_validation_commands": post_run_validation_commands,
        "next_required_step": (
            "Run the full GPU regeneration, return the summary JSON and completed identity-locked manifest CSV, "
            "then rerun the post-regeneration validation chain."
            if intake_ready and not receipt_ready
            else "Repair GPU return intake templates before running or accepting the GPU return."
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": rows,
        "blockers": blockers,
        "operator_acceptance_matrix": acceptance_rows,
        "operator_acceptance_stage_check_matrix": acceptance_stage_check_matrix,
        "operator_return_artifact_completion_matrix": operator_return_artifact_completion_matrix,
        "operator_return_artifact_completion_blocker_matrix": operator_return_artifact_completion_blockers,
        "operator_return_next_artifact_completion_packet": next_artifact_completion_packet,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# Product Production AI GPU Return Intake",
        "",
        f"- status: `{summary['status']}`",
        f"- gpu_return_intake_ready: `{summary['gpu_return_intake_ready']}`",
        f"- gpu_return_artifacts_ready: `{summary['gpu_return_artifacts_ready']}`",
        f"- expected_queue_rows: `{summary['expected_queue_rows']}`",
        f"- operator_return_bundle_contract_ready: `{summary['operator_return_bundle_contract_ready']}`",
        f"- operator_return_handoff_binding_ready: `{summary['operator_return_handoff_binding_ready']}`",
        f"- operator_return_handoff_queue_csv: `{summary['operator_return_handoff_queue_csv']}`",
        f"- operator_return_handoff_queue_csv_sha256: `{summary['operator_return_handoff_queue_csv_sha256']}`",
        f"- operator_return_handoff_full_regeneration_command: `{summary['operator_return_handoff_full_regeneration_command']}`",
        f"- operator_return_handoff_return_manifest_required_identity_rule: `{summary['operator_return_handoff_return_manifest_required_identity_rule']}`",
        f"- operator_acceptance_matrix_ready: `{summary['operator_acceptance_matrix_ready']}`",
        f"- operator_acceptance_ready_stage_count: `{summary['operator_acceptance_ready_stage_count']}`",
        f"- operator_acceptance_blocked_stage_count: `{summary['operator_acceptance_blocked_stage_count']}`",
        f"- operator_acceptance_next_stage_id: `{summary['operator_acceptance_next_stage_id']}`",
        f"- operator_acceptance_next_stage_artifact: `{summary['operator_acceptance_next_stage_artifact']}`",
        f"- operator_acceptance_next_stage_validation_command: `{summary['operator_acceptance_next_stage_validation_command']}`",
        f"- operator_return_blocker_count: `{summary['operator_return_blocker_count']}`",
        f"- operator_return_artifact_completion_matrix_count: `{summary['operator_return_artifact_completion_matrix_count']}`",
        f"- operator_return_artifact_completion_blocker_count: `{summary['operator_return_artifact_completion_blocker_count']}`",
        f"- operator_return_next_artifact_completion_packet_ready: `{summary['operator_return_next_artifact_completion_packet_ready']}`",
        f"- operator_return_next_artifact_id: `{summary['operator_return_next_artifact_id']}`",
        f"- operator_return_next_artifact_path: `{summary['operator_return_next_artifact_path']}`",
        f"- operator_return_next_artifact_template_payload_json: `{summary['operator_return_next_artifact_completion_packet'].get('template_payload_json', '')}`",
        f"- first_failed_check_id: `{summary['first_failed_check_id']}`",
        f"- first_failed_source_artifact: `{summary['first_failed_source_artifact']}`",
        f"- first_failed_next_action: `{summary['first_failed_next_action']}`",
        f"- manifest_template_csv: `{summary['manifest_template_csv']}`",
        f"- summary_template_csv: `{summary['summary_template_csv']}`",
        f"- summary_template_payload_json: `{summary['summary_template_payload_json']}`",
        f"- summary_template_required_fields: `{','.join(summary['summary_template_required_fields'])}`",
        f"- summary_template_completion_rule: `{summary['summary_template_completion_rule']}`",
        f"- summary_template_backend_provenance_contract_ready: `{summary['summary_template_backend_provenance_contract_ready']}`",
        f"- summary_template_required_backend_provenance_fields: `{','.join(summary['summary_template_required_backend_provenance_fields'])}`",
        f"- actual_summary_return_path: `{summary['actual_summary_return_path']}`",
        f"- actual_manifest_return_path: `{summary['actual_manifest_return_path']}`",
        f"- summary_manifest_bound: `{summary['summary_manifest_bound']}`",
        f"- summary_out_manifest_csv_present: `{summary['summary_out_manifest_csv_present']}`",
        f"- summary_out_manifest_csv: `{summary['summary_out_manifest_csv']}`",
        f"- summary_out_manifest_csv_bound: `{summary['summary_out_manifest_csv_bound']}`",
        f"- summary_out_summary_json_bound: `{summary['summary_out_summary_json_bound']}`",
        f"- summary_out_summary_json: `{summary['summary_out_summary_json']}`",
        f"- summary_manifest_row_counts_consistent: `{summary['summary_manifest_row_counts_consistent']}`",
        f"- production_gpu_backend_provenance_ready: `{summary['production_gpu_backend_provenance_ready']}`",
        f"- production_gpu_backend_rows: `{summary['production_gpu_backend_rows']}`",
        f"- production_gpu_backend_non_production_rows: `{summary['production_gpu_backend_non_production_rows']}`",
        f"- worker_rocm_manifest_ready: `{summary['worker_rocm_manifest_ready']}`",
        f"- worker_rocm_manifest_artifact: `{summary['worker_rocm_manifest_artifact']}`",
        f"- worker_rocm_manifest_completion_rule: `{summary['worker_rocm_manifest_completion_rule']}`",
        f"- worker_rocm_visible_device_count: `{summary['worker_rocm_visible_device_count']}`",
        f"- worker_rocm_device_names: `{','.join(summary['worker_rocm_device_names'])}`",
        f"- summary_manifest_csv: `{summary['summary_manifest_csv']}`",
        f"- manifest_npz_paths_complete: `{summary['manifest_npz_paths_complete']}`",
        f"- manifest_npz_path_present_count: `{summary['manifest_npz_path_present_count']}`",
        f"- manifest_npz_files_exist: `{summary['manifest_npz_files_exist']}`",
        f"- manifest_npz_file_existing_count: `{summary['manifest_npz_file_existing_count']}`",
        f"- manifest_npz_files_valid: `{summary['manifest_npz_files_valid']}`",
        f"- manifest_npz_file_valid_count: `{summary['manifest_npz_file_valid_count']}`",
        f"- manifest_npz_schema_valid: `{summary['manifest_npz_schema_valid']}`",
        f"- manifest_npz_schema_valid_count: `{summary['manifest_npz_schema_valid_count']}`",
        f"- manifest_npz_identity_valid: `{summary['manifest_npz_identity_valid']}`",
        f"- manifest_npz_identity_valid_count: `{summary['manifest_npz_identity_valid_count']}`",
        f"- failed_check_ids: `{','.join(str(item) for item in summary['failed_check_ids'])}`",
        f"- next_required_step: `{summary['next_required_step']}`",
        "",
        "## Required Return Bundle",
        "",
        "| artifact |",
        "| --- |",
    ]
    for artifact in summary["operator_return_required_artifacts"]:
        lines.append(f"| `{artifact}` |")
    lines.extend([
        "",
        "## Return Artifact Completion Matrix",
        "",
        "| artifact | status | failed checks | validation command | next action |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in payload["operator_return_artifact_completion_matrix"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['status']}` | "
            f"`{','.join(str(item) for item in row['failed_check_ids'])}` | "
            f"`{row['validation_command']}` | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Required Manifest Columns",
            "",
            "| column |",
            "| --- |",
        ]
    )
    for column in summary["operator_return_manifest_required_columns"]:
        lines.append(f"| `{column}` |")
    lines.extend([
        "",
        "## Operator Acceptance Matrix",
        "",
        "| stage | status | artifact | validation_command | release_effect | next_action |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for row in payload["operator_acceptance_matrix"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['status']}` | `{row['artifact']}` | "
            f"`{row['validation_command']}` | {row['release_effect']} | {row['next_action']} |"
        )
    lines.extend([
        "",
        "## Checks",
        "",
        "| check | status | observed | next_action |",
        "| --- | --- | --- | --- |",
    ])
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product production AI GPU return intake readiness.")
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--return-manifest-template-json", default=DEFAULT_RETURN_MANIFEST_TEMPLATE_JSON)
    parser.add_argument("--return-summary-template-json", default=DEFAULT_RETURN_SUMMARY_TEMPLATE_JSON)
    parser.add_argument("--return-receipt-json", default=DEFAULT_RETURN_RECEIPT_JSON)
    parser.add_argument("--worker-rocm-manifest-json", default=DEFAULT_WORKER_ROCM_MANIFEST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_production_ai_gpu_return_intake(
        handoff_packet=_read_json(args.handoff_json),
        return_manifest_template_packet=_read_json(args.return_manifest_template_json),
        return_summary_template_packet=_read_json(args.return_summary_template_json),
        return_receipt_packet=_read_json(args.return_receipt_json),
        worker_rocm_manifest_packet=_read_json(args.worker_rocm_manifest_json),
        handoff_path=args.handoff_json,
        return_manifest_template_path=args.return_manifest_template_json,
        return_summary_template_path=args.return_summary_template_json,
        return_receipt_path=args.return_receipt_json,
        worker_rocm_manifest_path=args.worker_rocm_manifest_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
